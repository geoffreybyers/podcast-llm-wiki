from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podcast_llm.transcriber import (
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
