from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    return "\n".join(fm_lines) + "\n".join(body_lines) + "\n"
