"""Tests for the one-shot podcast -> creator data migration."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from migrate_to_creators import rewrite_ledger_header, rewrite_queue_paths


def test_rewrites_ledger_header_column() -> None:
    text = (
        "| podcast | channelTitle | title |\n"
        "| --- | --- | --- |\n"
        "| Huberman Lab | Andrew Huberman | A podcast about podcasts |\n"
    )
    out = rewrite_ledger_header(text)
    assert out.startswith("| creator | channelTitle | title |\n")
    # Only the header changes -- body text that happens to say "podcast" stays.
    assert "A podcast about podcasts" in out


def test_ledger_header_rewrite_is_idempotent() -> None:
    text = "| podcast | channelTitle |\n| --- | --- |\n"
    assert rewrite_ledger_header(rewrite_ledger_header(text)) == rewrite_ledger_header(text)


def test_rewrites_queue_path_prefixes() -> None:
    text = (
        "- podcasts/Huberman Lab/transcriptions/A - transcription.md\n"
        "- podcasts/Huberman Lab/transcriptions/B - transcription.md\n"
    )
    out = rewrite_queue_paths(text)
    assert out == (
        "- creators/Huberman Lab/transcriptions/A - transcription.md\n"
        "- creators/Huberman Lab/transcriptions/B - transcription.md\n"
    )


def test_queue_rewrite_leaves_other_text_alone() -> None:
    """A title containing the word 'podcasts' must not be rewritten."""
    text = "- podcasts/Huberman Lab/transcriptions/Why podcasts win - transcription.md\n"
    out = rewrite_queue_paths(text)
    assert out == "- creators/Huberman Lab/transcriptions/Why podcasts win - transcription.md\n"


def test_queue_rewrite_is_idempotent() -> None:
    text = "- podcasts/X/transcriptions/A.md\n"
    assert rewrite_queue_paths(rewrite_queue_paths(text)) == rewrite_queue_paths(text)
