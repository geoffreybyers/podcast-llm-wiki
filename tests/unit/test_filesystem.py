from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.utils.filesystem import atomic_write, sanitize_filename


class TestAtomicWrite:
    def test_writes_text_to_target(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        atomic_write(target, "hello")
        assert target.read_text() == "hello"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old")
        atomic_write(target, "new")
        assert target.read_text() == "new"

    def test_does_not_leave_tempfile(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        atomic_write(target, "data")
        leftover = list(tmp_path.glob("*.tmp")) + list(tmp_path.glob(".*"))
        assert leftover == [target] or leftover == []

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "out.txt"
        atomic_write(target, "x")
        assert target.read_text() == "x"
