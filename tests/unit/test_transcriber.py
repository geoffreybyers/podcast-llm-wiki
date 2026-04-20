from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from podcast_llm.transcriber import (
    FasterWhisperAsr,
    TranscriptSegment,
    TranscriptionResult,
    detect_device,
    render_transcript_markdown,
)


class TestDetectDevice:
    @patch("podcast_llm.transcriber.torch")
    def test_prefers_cuda_when_available(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.backends.mps.is_available.return_value = False
        assert detect_device() == "cuda"

    @patch("podcast_llm.transcriber.torch")
    def test_falls_back_to_mps_on_apple(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True
        assert detect_device() == "mps"

    @patch("podcast_llm.transcriber.torch")
    def test_falls_back_to_cpu(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        assert detect_device() == "cpu"


class TestRenderTranscriptMarkdown:
    def test_renders_frontmatter(self) -> None:
        result = TranscriptionResult(
            segments=[
                TranscriptSegment(0.0, 5.0, "Speaker 1", "Hello there."),
            ],
            duration_sec=5.0,
            model_name="whisper-base",
            diarization=True,
        )
        out = render_transcript_markdown(
            result,
            episode_id="vid1",
            channel_title="Channel",
            title="Episode One",
            published_at="2026-04-20",
            url="https://x.test",
        )
        assert out.startswith("---\n")
        assert "episode_id: vid1" in out
        assert "channelTitle: Channel" in out
        assert "title: Episode One" in out
        assert "url: https://x.test" in out
        assert "duration_sec: 5" in out
        assert "model: whisper-base" in out
        assert "diarization: true" in out

    def test_renders_diarized_segments(self) -> None:
        result = TranscriptionResult(
            segments=[
                TranscriptSegment(0.0, 5.0, "Speaker 1", "Hello."),
                TranscriptSegment(5.0, 10.5, "Speaker 2", "Hi there."),
            ],
            duration_sec=10.5,
            model_name="whisper-base",
            diarization=True,
        )
        out = render_transcript_markdown(
            result,
            episode_id="x",
            channel_title="C",
            title="T",
            published_at="2026-04-20",
            url="https://x",
        )
        assert "[00:00:00] Speaker 1: Hello." in out
        assert "[00:00:05] Speaker 2: Hi there." in out
        # Blank line separates YAML frontmatter from body (Obsidian convention).
        assert "---\n\n[00:00:00]" in out

    def test_renders_non_diarized_without_speaker_label(self) -> None:
        result = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 3.0, None, "Solo content.")],
            duration_sec=3.0,
            model_name="whisper-base",
            diarization=False,
        )
        out = render_transcript_markdown(
            result,
            episode_id="x",
            channel_title="C",
            title="T",
            published_at="2026-04-20",
            url="https://x",
        )
        assert "[00:00:00] Solo content." in out
        assert "Speaker" not in out.split("---")[2]  # body, not frontmatter


class TestTranscriberTranscribe:
    def test_returns_segments_with_speakers_when_diarized(self, tmp_path: Path) -> None:
        audio = tmp_path / "x.wav"
        audio.write_bytes(b"RIFF")

        asr_engine = MagicMock()
        asr_engine.transcribe_file.return_value = [
            TranscriptSegment(0.0, 5.0, None, "Hello."),
            TranscriptSegment(5.0, 10.0, None, "Hi back."),
        ]
        diar_engine = MagicMock()
        diar_engine.diarize_file.return_value = [
            (0.0, 5.0, "Speaker 1"),
            (5.0, 10.0, "Speaker 2"),
        ]

        from podcast_llm.transcriber import Transcriber

        t = Transcriber(
            asr_engine=asr_engine,
            diar_engine=diar_engine,
            model_name="whisper-base",
            diarization=True,
        )
        result = t.transcribe(audio)
        assert result.diarization is True
        assert result.segments[0].speaker == "Speaker 1"
        assert result.segments[1].speaker == "Speaker 2"
        assert result.model_name == "whisper-base"

    def test_skips_diarization_when_disabled(self, tmp_path: Path) -> None:
        audio = tmp_path / "x.wav"
        audio.write_bytes(b"RIFF")

        asr_engine = MagicMock()
        asr_engine.transcribe_file.return_value = [
            TranscriptSegment(0.0, 5.0, None, "Solo."),
        ]
        diar_engine = MagicMock()

        from podcast_llm.transcriber import Transcriber

        t = Transcriber(
            asr_engine=asr_engine,
            diar_engine=diar_engine,
            model_name="whisper-base",
            diarization=False,
        )
        result = t.transcribe(audio)
        assert result.diarization is False
        assert result.segments[0].speaker is None
        diar_engine.diarize_file.assert_not_called()


class TestFasterWhisperAsr:
    @patch("podcast_llm.transcriber.WhisperModel")
    def test_transcribe_file_returns_segments(self, mock_model_cls) -> None:
        mock_model = MagicMock()
        mock_segments = iter(
            [
                SimpleNamespace(start=0.0, end=5.0, text=" hello "),
                SimpleNamespace(start=5.0, end=10.0, text="world"),
            ]
        )
        mock_info = SimpleNamespace(language="en")
        mock_model.transcribe.return_value = (mock_segments, mock_info)
        mock_model_cls.return_value = mock_model

        asr = FasterWhisperAsr(model_name="small.en", device="cpu")
        segments = asr.transcribe_file(Path("/tmp/fake.wav"))

        assert len(segments) == 2
        assert segments[0].start_sec == 0.0
        assert segments[0].end_sec == 5.0
        assert segments[0].text == "hello"
        assert segments[0].speaker is None
        assert segments[1].start_sec == 5.0
        assert segments[1].end_sec == 10.0
        assert segments[1].text == "world"
        assert segments[1].speaker is None

        mock_model.transcribe.assert_called_once()
        call_kwargs = mock_model.transcribe.call_args.kwargs
        assert call_kwargs.get("vad_filter") is True
        assert call_kwargs.get("beam_size") == 5

    @patch("podcast_llm.transcriber.ctranslate2")
    @patch("podcast_llm.transcriber.WhisperModel")
    def test_cpu_picks_int8_when_supported(self, mock_model_cls, mock_ct2) -> None:
        mock_ct2.get_supported_compute_types.return_value = {"int8", "int8_float32", "float32"}
        FasterWhisperAsr(model_name="small.en", device="cpu")

        mock_model_cls.assert_called_once()
        call_kwargs = mock_model_cls.call_args.kwargs
        assert call_kwargs.get("compute_type") == "int8"
        assert call_kwargs.get("device") == "cpu"

    @patch("podcast_llm.transcriber.ctranslate2")
    @patch("podcast_llm.transcriber.WhisperModel")
    def test_cuda_prefers_float16_when_supported(self, mock_model_cls, mock_ct2) -> None:
        mock_ct2.get_supported_compute_types.return_value = {
            "float32",
            "float16",
            "int8_float16",
            "int8",
        }
        FasterWhisperAsr(model_name="small.en", device="cuda")

        call_kwargs = mock_model_cls.call_args.kwargs
        assert call_kwargs.get("compute_type") == "float16"
        assert call_kwargs.get("device") == "cuda"

    @patch("podcast_llm.transcriber.ctranslate2")
    @patch("podcast_llm.transcriber.WhisperModel")
    def test_cuda_falls_back_when_float16_unavailable(self, mock_model_cls, mock_ct2) -> None:
        # Mimics ctranslate2 4.7 on CUDA-13 driver: no float16 kernels.
        mock_ct2.get_supported_compute_types.return_value = {"float32", "int8_float32", "int8"}
        FasterWhisperAsr(model_name="small.en", device="cuda")

        call_kwargs = mock_model_cls.call_args.kwargs
        assert call_kwargs.get("compute_type") == "int8_float32"
        assert call_kwargs.get("device") == "cuda"
