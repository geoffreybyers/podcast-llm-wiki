from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from podcast_llm.parsers.analysis_sections import (
    ConceptItem,
    EntityItem,
    ParsedAnalysis,
)
from podcast_llm.utils.filesystem import atomic_write, sanitize_filename


@dataclass
class EpisodeMeta:
    episode_id: str
    channel_title: str
    title: str
    published_at: str
    url: str
    transcription_path: str
    analysis_path: str

    def base_filename(self) -> str:
        return sanitize_filename(
            f"{self.channel_title} - {self.title}",
            episode_id=self.episode_id,
        )


class WikiWriter:
    """Performs the post-analysis wiki updates per spec §5.6."""

    def __init__(self, vault_path: Path) -> None:
        self.vault = Path(vault_path)

    def copy_transcription(self, source: Path, meta: EpisodeMeta) -> Path:
        dest_dir = self.vault / "raw" / "transcripts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{meta.base_filename()}.md"
        shutil.copyfile(source, dest)
        return dest
