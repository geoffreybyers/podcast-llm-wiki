"""Shared pytest fixtures for podcast-llm tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temporary directory mimicking the project root layout."""
    (tmp_path / "podcasts").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary directory acting as the parent for vaults (~/obsidian)."""
    vault_root = tmp_path / "obsidian"
    vault_root.mkdir()
    return vault_root
