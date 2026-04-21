from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm_wiki.utils.filesystem import atomic_write, sanitize_filename


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


class TestSanitizeFilename:
    def test_replaces_path_separators(self) -> None:
        assert sanitize_filename("a/b\\c") == "a-b-c"

    def test_strips_null_bytes(self) -> None:
        assert sanitize_filename("a\x00b") == "ab"

    def test_strips_leading_dots(self) -> None:
        assert sanitize_filename("...hidden") == "hidden"

    def test_truncates_long_names_with_episode_id(self) -> None:
        long_title = "x" * 250
        result = sanitize_filename(long_title, episode_id="abc12345")
        # Truncation reserves room for " - <episode_id>" suffix.
        assert result.endswith(" - abc12345")
        assert len(result) <= 220

    def test_truncates_long_names_without_episode_id(self) -> None:
        long_title = "y" * 250
        result = sanitize_filename(long_title)
        assert len(result) <= 200

    def test_preserves_short_names(self) -> None:
        assert sanitize_filename("Episode 1: Foo") == "Episode 1- Foo"

    def test_strips_trailing_dots_and_whitespace(self) -> None:
        assert sanitize_filename("name.   ") == "name"
