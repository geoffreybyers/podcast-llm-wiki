from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import soundfile as sf
import torch


@dataclass
class TranscriptSegment:
    start_sec: float
    end_sec: float
    speaker: Optional[str]  # None when diarization disabled
    text: str


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    duration_sec: float
    model_name: str
    diarization: bool


def detect_device() -> str:
    """Return 'cuda', 'mps', or 'cpu' based on what torch can use."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch, "backends") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class Transcriber:
    """Orchestrates ASR + (optional) diarization to produce a TranscriptionResult.

    The actual engine adapters (sherpa-onnx for ASR, pyannote for diarization)
    are injected so this class is unit-testable without real models. Concrete
    adapters are constructed in `pipeline.py` from the per-podcast config.
    """

    def __init__(
        self,
        asr_engine,
        diar_engine,
        model_name: str,
        diarization: bool,
    ) -> None:
        self.asr_engine = asr_engine
        self.diar_engine = diar_engine
        self.model_name = model_name
        self.diarization = diarization

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        segments: list[TranscriptSegment] = list(
            self.asr_engine.transcribe_file(audio_path)
        )
        if self.diarization:
            speaker_spans = self.diar_engine.diarize_file(audio_path)
            segments = _assign_speakers(segments, speaker_spans)

        duration = max((s.end_sec for s in segments), default=0.0)
        return TranscriptionResult(
            segments=segments,
            duration_sec=duration,
            model_name=self.model_name,
            diarization=self.diarization,
        )


def _assign_speakers(
    segments: list[TranscriptSegment],
    spans: list[tuple[float, float, str]],
) -> list[TranscriptSegment]:
    """Label each ASR segment with the speaker whose span best overlaps it."""
    out: list[TranscriptSegment] = []
    for seg in segments:
        best_speaker: Optional[str] = None
        best_overlap = 0.0
        for s_start, s_end, speaker in spans:
            overlap = max(0.0, min(seg.end_sec, s_end) - max(seg.start_sec, s_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        out.append(
            TranscriptSegment(
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                speaker=best_speaker,
                text=seg.text,
            )
        )
    return out


def render_transcript_markdown(
    result: TranscriptionResult,
    *,
    episode_id: str,
    channel_title: str,
    title: str,
    published_at: str,
    url: str,
) -> str:
    """Render a TranscriptionResult as the diarized markdown file (per spec §4.3)."""
    transcribed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fm_lines = [
        "---",
        f"episode_id: {episode_id}",
        f"channelTitle: {channel_title}",
        f"title: {title}",
        f"publishedAt: {published_at}",
        f"url: {url}",
        f"duration_sec: {int(result.duration_sec)}",
        f"transcribed_at: {transcribed_at}",
        f"model: {result.model_name}",
        f"diarization: {'true' if result.diarization else 'false'}",
        "---",
        "",
    ]
    body_lines: list[str] = []
    for seg in result.segments:
        ts = _format_timestamp(seg.start_sec)
        if result.diarization and seg.speaker:
            body_lines.append(f"[{ts}] {seg.speaker}: {seg.text}")
        else:
            body_lines.append(f"[{ts}] {seg.text}")
    return "\n".join(fm_lines) + "\n" + "\n".join(body_lines) + "\n"


class SherpaOnnxAsr:
    """ASR adapter wrapping sherpa-onnx whisper bindings.

    `model_dir` should point to a directory containing the ONNX model files
    appropriate for `model_name` (e.g. whisper-base). On first use these are
    downloaded into ~/.cache/sherpa-onnx by the preflight step.
    """

    def __init__(self, model_dir: Path, model_name: str, device: str) -> None:
        import sherpa_onnx

        self.model_name = model_name
        self.device = device
        provider = "cuda" if device == "cuda" else "cpu"
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(model_dir / f"{model_name}-encoder.onnx"),
            decoder=str(model_dir / f"{model_name}-decoder.onnx"),
            tokens=str(model_dir / f"{model_name}-tokens.txt"),
            provider=provider,
        )

    def transcribe_file(self, audio_path: Path) -> list[TranscriptSegment]:
        audio, sample_rate = sf.read(str(audio_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        stream = self._recognizer.create_stream()
        stream.accept_waveform(sample_rate, audio)
        self._recognizer.decode_stream(stream)
        # Whisper returns one big result; chunk by punctuation/sentence segmentation
        # in the integration step. For now, emit a single segment covering the file.
        text = stream.result.text.strip()
        duration = len(audio) / float(sample_rate)
        return [TranscriptSegment(start_sec=0.0, end_sec=duration, speaker=None, text=text)]


class PyannoteDiarizer:
    """Diarization adapter wrapping pyannote.audio."""

    def __init__(self, segmentation_model: str, embedding_model: str, device: str) -> None:
        from pyannote.audio import Pipeline

        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
        )
        try:
            import torch as _torch

            self.pipeline.to(_torch.device(device))
        except Exception:  # noqa: BLE001
            # Some torch builds lack MPS support for all ops; fall back to CPU silently.
            pass

    def diarize_file(self, audio_path: Path) -> list[tuple[float, float, str]]:
        diarization = self.pipeline(str(audio_path))
        spans: list[tuple[float, float, str]] = []
        for turn, _track, speaker in diarization.itertracks(yield_label=True):
            spans.append((float(turn.start), float(turn.end), str(speaker)))
        return spans
