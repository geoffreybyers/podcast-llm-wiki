from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from podcast_llm.utils.filesystem import atomic_write

COLLECTED_HEADER = (
    "| podcast | channelTitle | title | publishedAt | url | episode_id | status "
    "| downloaded_at | transcribed_at | analyzed_at | error |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escape_cell(value: str) -> str:
    """Escape pipe and newline so the value fits in a single markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ").strip()


@dataclass
class EpisodeRecord:
    podcast: str
    channel_title: str
    title: str
    published_at: str
    url: str
    episode_id: str
    status: str = ""
    downloaded_at: str = ""
    transcribed_at: str = ""
    analyzed_at: str = ""
    error: str = ""

    def to_row(self) -> str:
        cells = [
            _escape_cell(self.podcast),
            _escape_cell(self.channel_title),
            _escape_cell(self.title),
            _escape_cell(self.published_at),
            _escape_cell(self.url),
            _escape_cell(self.episode_id),
            _escape_cell(self.status),
            _escape_cell(self.downloaded_at),
            _escape_cell(self.transcribed_at),
            _escape_cell(self.analyzed_at),
            _escape_cell(self.error),
        ]
        return "| " + " | ".join(cells) + " |\n"

    @classmethod
    def from_row(cls, row: str) -> "EpisodeRecord":
        # Strip leading/trailing pipe and whitespace, split on " | ".
        body = row.strip()
        if body.startswith("|"):
            body = body[1:]
        if body.endswith("|"):
            body = body[:-1]
        cells = [c.strip().replace("\\|", "|") for c in body.split(" | ")]
        # Pad to expected length in case of trailing empty cells trimmed by some editor.
        while len(cells) < 11:
            cells.append("")
        return cls(
            podcast=cells[0],
            channel_title=cells[1],
            title=cells[2],
            published_at=cells[3],
            url=cells[4],
            episode_id=cells[5],
            status=cells[6],
            downloaded_at=cells[7],
            transcribed_at=cells[8],
            analyzed_at=cells[9],
            error=cells[10],
        )


class Ledger:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.collected_path = self.project_root / "collected.md"
        self.queue_path = self.project_root / "analysis_queue.md"

    # --- init ---

    def ensure_initialized(self) -> None:
        if not self.collected_path.exists():
            atomic_write(self.collected_path, COLLECTED_HEADER)
        if not self.queue_path.exists():
            atomic_write(self.queue_path, "")

    # --- collected.md ---

    def _read_records(self) -> list[EpisodeRecord]:
        if not self.collected_path.exists():
            return []
        lines = self.collected_path.read_text().splitlines()
        # Skip 2-line header (header row + separator).
        records: list[EpisodeRecord] = []
        for line in lines[2:]:
            if not line.strip():
                continue
            records.append(EpisodeRecord.from_row(line))
        return records

    def _write_records(self, records: list[EpisodeRecord]) -> None:
        body = COLLECTED_HEADER + "".join(r.to_row() for r in records)
        atomic_write(self.collected_path, body)

    def record_downloaded(self, rec: EpisodeRecord) -> None:
        self.ensure_initialized()
        records = self._read_records()
        existing = next((r for r in records if r.episode_id == rec.episode_id), None)
        if existing is None:
            rec.status = "downloaded"
            rec.downloaded_at = _now_iso()
            records.append(rec)
        else:
            existing.status = "downloaded"
            existing.downloaded_at = _now_iso()
        self._write_records(records)

    def record_transcribed(self, episode_id: str, transcription_path: str) -> None:
        records = self._read_records()
        for r in records:
            if r.episode_id == episode_id:
                r.status = "transcribed"
                r.transcribed_at = _now_iso()
                break
        else:
            raise KeyError(f"unknown episode_id: {episode_id}")
        self._write_records(records)
        self._queue_append(transcription_path)

    def record_analyzed(self, episode_id: str, transcription_path: str) -> None:
        records = self._read_records()
        for r in records:
            if r.episode_id == episode_id:
                r.status = "analyzed"
                r.analyzed_at = _now_iso()
                break
        else:
            raise KeyError(f"unknown episode_id: {episode_id}")
        self._write_records(records)
        self.queue_remove(transcription_path)

    def record_failed(self, rec: EpisodeRecord, stage: str, error: str) -> None:
        self.ensure_initialized()
        records = self._read_records()
        existing = next((r for r in records if r.episode_id == rec.episode_id), None)
        status = f"{stage}_failed"
        if existing is None:
            rec.status = status
            rec.error = error
            records.append(rec)
        else:
            existing.status = status
            existing.error = error
        self._write_records(records)

    def is_known_episode(self, episode_id: str) -> bool:
        return any(r.episode_id == episode_id for r in self._read_records())

    def known_episode_ids(self) -> set[str]:
        return {r.episode_id for r in self._read_records()}

    # --- analysis_queue.md ---

    def _queue_lines(self) -> list[str]:
        if not self.queue_path.exists():
            return []
        return [
            line[2:] if line.startswith("- ") else line
            for line in self.queue_path.read_text().splitlines()
            if line.strip()
        ]

    def _write_queue(self, paths: list[str]) -> None:
        body = "".join(f"- {p}\n" for p in paths)
        atomic_write(self.queue_path, body)

    def _queue_append(self, path: str) -> None:
        paths = self._queue_lines()
        if path not in paths:
            paths.append(path)
            self._write_queue(paths)

    def queue_peek(self) -> Optional[str]:
        paths = self._queue_lines()
        return paths[0] if paths else None

    def queue_pop(self) -> Optional[str]:
        paths = self._queue_lines()
        if not paths:
            return None
        head = paths[0]
        self._write_queue(paths[1:])
        return head

    def queue_remove(self, path: str) -> None:
        paths = [p for p in self._queue_lines() if p != path]
        self._write_queue(paths)
