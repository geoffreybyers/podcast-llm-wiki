# tests/unit/test_preflight.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from podcast_llm_wiki.config import PodcastConfig
from podcast_llm_wiki.preflight import (
    PreflightError,
    check_vault_skeletons,
    check_yt_dlp,
    run_all,
)


def _pod(vault: Path, *, name: str = "TestPod", lens: str = "Test lens.") -> PodcastConfig:
    return PodcastConfig(
        name=name,
        playlist_url="https://x.test",
        lens=lens,
        vault_path=vault,
        max_backfill=5,
        stt_model="whisper-base",
        diarization=True,
        diarization_segmentation="seg",
        diarization_embedding="emb",
    )


class TestCheckYtDlp:
    @patch("podcast_llm_wiki.preflight.yt_dlp")
    def test_passes_when_module_present(self, mock_mod) -> None:
        mock_mod.version.__version__ = "2026.01.01"
        check_yt_dlp()  # should not raise


class TestCheckVaultSkeletons:
    def test_creates_missing_skeleton(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "TestVault"
        check_vault_skeletons([_pod(vault)])
        assert (vault / "SCHEMA.md").exists()
        assert (vault / "index.md").exists()
        assert (vault / "log.md").exists()
        for sub in ["raw/transcripts", "episodes", "entities", "concepts", "comparisons", "queries"]:
            assert (vault / sub).is_dir()

    def test_populates_schema_with_name_and_lens(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "TestVault"
        check_vault_skeletons([_pod(vault, name="My Podcast", lens="Focus on X.")])
        schema = (vault / "SCHEMA.md").read_text()
        assert "My Podcast" in schema
        assert "Focus on X." in schema
        assert "{{podcast_name}}" not in schema
        assert "{{lens}}" not in schema
        assert "{{created_date}}" not in schema

    def test_idempotent_for_existing_vault(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "TestVault"
        check_vault_skeletons([_pod(vault)])
        # Modify SCHEMA.md to verify it's not overwritten on second call.
        (vault / "SCHEMA.md").write_text("# CUSTOMIZED")
        check_vault_skeletons([_pod(vault)])
        assert (vault / "SCHEMA.md").read_text() == "# CUSTOMIZED"


class TestRunAll:
    @patch("podcast_llm_wiki.preflight.check_yt_dlp")
    @patch("podcast_llm_wiki.preflight.check_vault_skeletons")
    def test_runs_each_check(self, mock_vaults, mock_yt, tmp_path: Path) -> None:
        pods = [_pod(tmp_path / "v")]
        run_all(podcasts=pods)
        mock_yt.assert_called_once()
        mock_vaults.assert_called_once_with(pods)
