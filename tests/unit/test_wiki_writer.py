from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from podcast_llm.parsers.analysis_sections import (
    ConceptItem,
    EntityItem,
    ParsedAnalysis,
)
from podcast_llm.wiki.vault import create_vault_skeleton
from podcast_llm.wiki.writer import (
    EpisodeMeta,
    WikiWriter,
)


@pytest.fixture
def vault(tmp_vault: Path) -> Path:
    v = tmp_vault / "Test Podcast"
    create_vault_skeleton(v, podcast_name="Test Podcast", lens="Test lens.")
    return v


def _episode_meta(**overrides) -> EpisodeMeta:
    base = dict(
        episode_id="vid1",
        channel_title="Channel",
        title="Episode One",
        published_at="2026-04-20",
        url="https://x.test/vid1",
        transcription_path="/abs/transcription.md",
        analysis_path="/abs/analysis.md",
    )
    base.update(overrides)
    return EpisodeMeta(**base)


class TestCopyTranscription:
    def test_copies_to_raw_transcripts(self, vault: Path, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.write_text("transcription content")
        meta = _episode_meta()
        w = WikiWriter(vault)
        dest = w.copy_transcription(src, meta)
        assert dest.exists()
        assert dest.parent == vault / "raw" / "transcripts"
        assert dest.read_text() == "transcription content"
        assert dest.name.endswith(".md")
