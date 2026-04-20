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

    def update_index(
        self,
        *,
        new_episodes: list[tuple[str, str]] = (),
        new_entities: list[tuple[str, str]] = (),
        new_concepts: list[tuple[str, str]] = (),
    ) -> Path:
        index_path = self.vault / "index.md"
        text = index_path.read_text() if index_path.exists() else _DEFAULT_INDEX
        text = _insert_under_section(text, "Episodes", [
            f"- [[{name}]] — {summary}" for name, summary in new_episodes
        ])
        text = _insert_under_section(text, "Entities", [
            f"- [[{name}]] — {summary}" for name, summary in new_entities
        ])
        text = _insert_under_section(text, "Concepts", [
            f"- [[{name}]] — {summary}" for name, summary in new_concepts
        ])
        text = _bump_index_total(text)
        text = _replace_index_last_updated(text, date.today().isoformat())
        atomic_write(index_path, text)
        return index_path

    def append_log(
        self,
        *,
        action: str,
        subject: str,
        files: Iterable[Path],
    ) -> Path:
        log_path = self.vault / "log.md"
        existing = log_path.read_text() if log_path.exists() else "# Wiki Log\n"
        today = date.today().isoformat()
        block = [f"\n## [{today}] {action} | {subject}"]
        for f in files:
            try:
                rel = Path(f).relative_to(self.vault)
            except ValueError:
                rel = Path(f)
            block.append(f"- {rel}")
        atomic_write(log_path, existing.rstrip() + "\n" + "\n".join(block) + "\n")
        return log_path


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


_DEFAULT_INDEX = (
    "# Wiki Index\n\n"
    "> Last updated: 1970-01-01 | Total pages: 0\n\n"
    "## Episodes\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n"
)


def _insert_under_section(text: str, section: str, lines: list[str]) -> str:
    if not lines:
        return text
    lines = sorted(lines)
    needle = f"## {section}\n"
    idx = text.find(needle)
    if idx == -1:
        # Section missing — append at end.
        return text.rstrip() + "\n\n" + needle + "\n".join(lines) + "\n"
    after_heading = idx + len(needle)
    # Find next heading (or EOF) to scope insertion to this section.
    next_heading = text.find("\n## ", after_heading)
    if next_heading == -1:
        block = text[after_heading:]
        head, tail = block, ""
    else:
        head = text[after_heading:next_heading + 1]
        tail = text[next_heading + 1:]
    # Existing items in the section (lines starting with "- ").
    existing_items = [ln for ln in head.splitlines() if ln.startswith("- ")]
    merged = sorted(set(existing_items + lines))
    new_section = "\n".join(merged) + ("\n" if merged else "")
    return text[:after_heading] + new_section + ("\n" if tail and not tail.startswith("\n") else "") + tail


def _bump_index_total(text: str) -> str:
    import re as _re

    def repl(m):
        # Walk all "- [[" lines to count current total.
        total = sum(1 for line in text.splitlines() if line.startswith("- [["))
        return f"Total pages: {total}"

    return _re.sub(r"Total pages: \d+", repl, text, count=1)


def _replace_index_last_updated(text: str, today: str) -> str:
    import re as _re

    return _re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {today}", text, count=1)
