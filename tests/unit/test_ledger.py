from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm_wiki.ledger import EpisodeRecord, Ledger


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


def _sample_record(**overrides) -> EpisodeRecord:
    base = dict(
        podcast="P",
        channel_title="Channel",
        title="Title",
        published_at="2026-04-20",
        url="https://youtube.com/watch?v=abc",
        episode_id="abc",
    )
    base.update(overrides)
    return EpisodeRecord(**base)


class TestLedgerRecord:
    def test_record_downloaded_appends_row(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record())
        text = (tmp_project / "collected.md").read_text()
        assert "| P | Channel | Title |" in text
        assert "downloaded" in text

    def test_record_transcribed_updates_existing_row(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record())
        ledger.record_transcribed("abc", "/abs/path/to/transcription.md")
        text = (tmp_project / "collected.md").read_text()
        assert "transcribed" in text
        assert "/abs/path/to/transcription.md" not in text  # path lives in queue, not table

    def test_record_transcribed_appends_to_queue(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record())
        ledger.record_transcribed("abc", "/abs/path/to/transcription.md")
        queue = (tmp_project / "analysis_queue.md").read_text()
        assert "/abs/path/to/transcription.md" in queue

    def test_record_analyzed_updates_row_and_pops_queue(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record())
        ledger.record_transcribed("abc", "/p/t.md")
        ledger.record_analyzed("abc", "/p/t.md")
        text = (tmp_project / "collected.md").read_text()
        queue = (tmp_project / "analysis_queue.md").read_text()
        assert "analyzed" in text
        assert "/p/t.md" not in queue

    def test_record_failed_records_error(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_failed(
            _sample_record(),
            stage="download",
            error="HTTP 403",
        )
        text = (tmp_project / "collected.md").read_text()
        assert "download_failed" in text
        assert "HTTP 403" in text

    def test_is_known_episode(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        assert ledger.is_known_episode("abc") is False
        ledger.record_downloaded(_sample_record())
        assert ledger.is_known_episode("abc") is True


class TestLedgerResumable:
    def test_resumable_records_returns_only_downloaded_status(
        self, tmp_project: Path
    ) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        # downloaded — should be returned
        ledger.record_downloaded(_sample_record(episode_id="a", title="A"))
        # transcribed — should NOT be returned
        ledger.record_downloaded(_sample_record(episode_id="b", title="B"))
        ledger.record_transcribed("b", "/tmp/b.md")
        # download_failed — should NOT be returned
        ledger.record_failed(
            _sample_record(episode_id="c", title="C"),
            stage="download",
            error="boom",
        )

        resumable = ledger.resumable_records()
        ids = {r.episode_id for r in resumable}
        assert ids == {"a"}

    def test_resumable_records_filters_by_podcast(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record(episode_id="a", podcast="P1"))
        ledger.record_downloaded(_sample_record(episode_id="b", podcast="P2"))

        p1 = ledger.resumable_records(podcast="P1")
        assert {r.episode_id for r in p1} == {"a"}

    def test_known_episode_ids(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record(episode_id="a"))
        ledger.record_downloaded(_sample_record(episode_id="b", title="T2"))
        assert ledger.known_episode_ids() == {"a", "b"}


class TestQueueOps:
    def test_queue_peek_and_pop(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record(episode_id="a"))
        ledger.record_downloaded(_sample_record(episode_id="b", title="T2"))
        ledger.record_transcribed("a", "/p/a.md")
        ledger.record_transcribed("b", "/p/b.md")
        assert ledger.queue_peek() == "/p/a.md"
        assert ledger.queue_pop() == "/p/a.md"
        assert ledger.queue_peek() == "/p/b.md"

    def test_queue_pop_empty_returns_none(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        assert ledger.queue_pop() is None

    def test_queue_preserves_fifo_order_across_mixed_operations(self, tmp_project: Path) -> None:
        """Failed episodes don't enqueue; transcribed ones keep insertion order."""
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        rec_a = _sample_record(episode_id="a", title="A")
        rec_b = _sample_record(episode_id="b", title="B")
        rec_c = _sample_record(episode_id="c", title="C")
        ledger.record_downloaded(rec_a)
        ledger.record_downloaded(rec_c)
        ledger.record_transcribed("a", "/p/a.md")
        ledger.record_failed(rec_b, stage="download", error="boom")
        ledger.record_transcribed("c", "/p/c.md")
        queue = (tmp_project / "analysis_queue.md").read_text().splitlines()
        assert queue == ["- /p/a.md", "- /p/c.md"]

    def test_queue_remove_specific(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record(episode_id="a"))
        ledger.record_downloaded(_sample_record(episode_id="b", title="T2"))
        ledger.record_transcribed("a", "/p/a.md")
        ledger.record_transcribed("b", "/p/b.md")
        ledger.queue_remove("/p/a.md")
        assert ledger.queue_peek() == "/p/b.md"
