# tests/unit/test_vault.py
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm_wiki.wiki.vault import create_vault_skeleton, vault_exists


class TestCreateVaultSkeleton:
    def test_creates_all_subdirectories(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "MyPodcast"
        create_vault_skeleton(vault)
        for sub in [
            "raw/transcripts",
            "episodes",
            "entities",
            "concepts",
            "comparisons",
            "queries",
        ]:
            assert (vault / sub).is_dir(), f"missing {sub}"

    def test_writes_schema_md_with_substituted_name(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "MyPodcast"
        create_vault_skeleton(vault, podcast_name="MyPodcast", lens="Test lens.")
        schema = (vault / "SCHEMA.md").read_text()
        assert "MyPodcast" in schema
        assert "Test lens." in schema
        assert "{{podcast_name}}" not in schema
        assert "{{lens}}" not in schema

    def test_writes_initial_index_md(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "MyPodcast"
        create_vault_skeleton(vault, podcast_name="MyPodcast")
        idx = (vault / "index.md").read_text()
        assert "# Wiki Index" in idx
        assert "Total pages: 0" in idx

    def test_writes_initial_log_md(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "MyPodcast"
        create_vault_skeleton(vault, podcast_name="MyPodcast")
        log = (vault / "log.md").read_text()
        assert "# Wiki Log" in log
        assert "create | Vault initialized" in log

    def test_idempotent_does_not_overwrite(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "MyPodcast"
        create_vault_skeleton(vault, podcast_name="MyPodcast")
        (vault / "SCHEMA.md").write_text("# CUSTOM")
        create_vault_skeleton(vault, podcast_name="MyPodcast")
        assert (vault / "SCHEMA.md").read_text() == "# CUSTOM"


class TestVaultExists:
    def test_true_when_skeleton_present(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "MyPodcast"
        create_vault_skeleton(vault)
        assert vault_exists(vault) is True

    def test_false_when_missing_schema(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "Empty"
        vault.mkdir()
        assert vault_exists(vault) is False
