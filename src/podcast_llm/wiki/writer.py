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

    def write_episode_page(
        self,
        meta: EpisodeMeta,
        *,
        tldr: str,
        insights_md: str,
        entity_links: list[str],
        concept_links: list[str],
    ) -> Path:
        today = date.today().isoformat()
        frontmatter = (
            "---\n"
            f"title: {meta.channel_title} — {meta.title}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "type: episode\n"
            "tags: [episode]\n"
            f"episode_id: {meta.episode_id}\n"
            f"channelTitle: {meta.channel_title}\n"
            f"publishedAt: {meta.published_at}\n"
            f"url: {meta.url}\n"
            f"transcription_path: {meta.transcription_path}\n"
            f"analysis_path: {meta.analysis_path}\n"
            "---\n\n"
        )
        body = (
            f"# {meta.channel_title} — {meta.title}\n\n"
            "## TL;DR\n"
            f"{tldr.strip()}\n\n"
            "## Key Insights\n"
            f"{insights_md.strip()}\n\n"
            "## Entities\n"
            + "\n".join(f"- {link}" for link in entity_links)
            + ("\n\n" if entity_links else "\n")
            + "## Concepts\n"
            + "\n".join(f"- {link}" for link in concept_links)
            + "\n"
        )
        page = self.vault / "episodes" / f"{meta.base_filename()}.md"
        atomic_write(page, frontmatter + body)
        return page
