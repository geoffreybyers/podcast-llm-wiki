from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.ledger import EpisodeRecord, Ledger


class TestLedgerInit:
    def test_creates_collected_md_with_header(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        text = (tmp_project / "collected.md").read_text()
        assert "| podcast | channelTitle |" in text
        assert "| --- |" in text

    def test_creates_empty_queue_file(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        assert (tmp_project / "analysis_queue.md").exists()

    def test_ensure_initialized_is_idempotent(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.ensure_initialized()
        # Just verify no exception and files remain.
        assert (tmp_project / "collected.md").exists()
