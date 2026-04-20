from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from podcast_llm.utils.filesystem import atomic_write

COLLECTED_HEADER = (
    "| podcast | channelTitle | title | publishedAt | url | status "
    "| downloaded_at | transcribed_at | analyzed_at | error |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


@dataclass
class EpisodeRecord:
    podcast: str
    channel_title: str
    title: str
    published_at: str
    url: str
    episode_id: str
    status: str = ""  # downloaded | download_complete | transcribed | analyzed | *_failed
    downloaded_at: str = ""
    transcribed_at: str = ""
    analyzed_at: str = ""
    error: str = ""
    transcription_path: Optional[str] = None


class Ledger:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.collected_path = self.project_root / "collected.md"
        self.queue_path = self.project_root / "analysis_queue.md"

    def ensure_initialized(self) -> None:
        if not self.collected_path.exists():
            atomic_write(self.collected_path, COLLECTED_HEADER)
        if not self.queue_path.exists():
            atomic_write(self.queue_path, "")
