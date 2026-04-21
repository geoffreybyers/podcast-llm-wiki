"""Real-pipeline smoke test. Skipped by default.

Run with: pytest -m integration

Requires:
- A small audio fixture at tests/fixtures/short-clip.wav (16kHz mono,
  ~30 seconds, public-domain content).
- faster-whisper installed; the model will auto-download on first use into
  ~/.cache/faster-whisper/.
- (Optional) HuggingFace token configured for pyannote.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm_wiki.transcriber import (
    FasterWhisperAsr,
    PyannoteDiarizer,
    Transcriber,
    detect_device,
    render_transcript_markdown,
)

FIXTURE_AUDIO = Path(__file__).parent.parent / "fixtures" / "short-clip.wav"
MODEL_CACHE = Path("~/.cache/faster-whisper").expanduser()


@pytest.mark.integration
@pytest.mark.skipif(not FIXTURE_AUDIO.exists(), reason="fixture audio missing")
def test_transcribe_short_clip_no_diarization() -> None:
    device = detect_device()
    asr = FasterWhisperAsr(model_name="small.en", device=device, cache_dir=MODEL_CACHE)
    transcriber = Transcriber(
        asr_engine=asr,
        diar_engine=None,
        model_name="small.en",
        diarization=False,
    )
    result = transcriber.transcribe(FIXTURE_AUDIO)
    assert result.segments
    assert result.duration_sec > 0


@pytest.mark.integration
@pytest.mark.skipif(not FIXTURE_AUDIO.exists(), reason="fixture audio missing")
def test_render_smoke() -> None:
    """Render path works on a synthetic TranscriptionResult — useful when
    faster-whisper isn't installed but you want to exercise output formatting."""
    from podcast_llm_wiki.transcriber import TranscriptSegment, TranscriptionResult

    result = TranscriptionResult(
        segments=[TranscriptSegment(0.0, 30.0, None, "smoke text")],
        duration_sec=30.0,
        model_name="small.en",
        diarization=False,
    )
    out = render_transcript_markdown(
        result,
        episode_id="smoke",
        channel_title="C",
        title="T",
        published_at="2026-04-20",
        url="https://x",
    )
    assert "smoke text" in out
