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

    def _entity_page_path(self, name: str) -> Path:
        return self.vault / "entities" / f"{sanitize_filename(name)}.md"

    def _concept_page_path(self, name: str) -> Path:
        return self.vault / "concepts" / f"{sanitize_filename(name)}.md"

    def upsert_entity_page(
        self,
        entity: EntityItem,
        *,
        episode_meta: EpisodeMeta,
    ) -> Path:
        path = self._entity_page_path(entity.name)
        backlink = f"[[{episode_meta.base_filename()}]]"
        today = date.today().isoformat()

        if path.exists():
            existing = path.read_text()
            # Bump updated date and append a new mention if this episode isn't already linked.
            existing = _replace_frontmatter_field(existing, "updated", today)
            if backlink not in existing:
                appended_block = (
                    f"\n## Mention in {backlink} (at {entity.timestamp})\n"
                    f"{entity.context}\n"
                )
                existing = existing.rstrip() + "\n" + appended_block
            atomic_write(path, existing)
            return path

        frontmatter = (
            "---\n"
            f"title: {entity.name}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "type: entity\n"
            f"entity_type: {entity.type}\n"
            "tags: [entity]\n"
            "---\n\n"
        )
        body = (
            f"# {entity.name}\n\n"
            f"**Type:** {entity.type}\n\n"
            "## Mentions\n"
            f"## Mention in {backlink} (at {entity.timestamp})\n"
            f"{entity.context}\n"
        )
        atomic_write(path, frontmatter + body)
        return path

    def upsert_concept_page(
        self,
        concept: ConceptItem,
        *,
        episode_meta: EpisodeMeta,
    ) -> Path:
        path = self._concept_page_path(concept.name)
        backlink = f"[[{episode_meta.base_filename()}]]"
        today = date.today().isoformat()

        if path.exists():
            existing = path.read_text()
            existing = _replace_frontmatter_field(existing, "updated", today)
            if backlink not in existing:
                appended_block = (
                    f"\n## Mention in {backlink} (at {concept.timestamp})\n"
                    f"{concept.definition}\n"
                )
                existing = existing.rstrip() + "\n" + appended_block
            atomic_write(path, existing)
            return path

        frontmatter = (
            "---\n"
            f"title: {concept.name}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "type: concept\n"
            "tags: [concept]\n"
            "---\n\n"
        )
        body = (
            f"# {concept.name}\n\n"
            f"**Definition:** {concept.definition}\n\n"
            "## Mentions\n"
            f"## Mention in {backlink} (at {concept.timestamp})\n"
            f"{concept.definition}\n"
        )
        atomic_write(path, frontmatter + body)
        return path


def _replace_frontmatter_field(text: str, key: str, new_value: str) -> str:
    """Replace `key: <value>` line inside the leading YAML frontmatter block."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    fm_block = text[4:end]
    new_lines: list[str] = []
    replaced = False
    for line in fm_block.splitlines():
        if line.startswith(f"{key}:"):
            new_lines.append(f"{key}: {new_value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}: {new_value}")
    return "---\n" + "\n".join(new_lines) + text[end:]
