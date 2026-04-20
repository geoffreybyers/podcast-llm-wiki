# src/podcast_llm/preflight.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import yt_dlp

from podcast_llm.wiki.vault import create_vault_skeleton

log = logging.getLogger(__name__)


class PreflightError(RuntimeError):
    pass


def check_yt_dlp() -> None:
    """Confirm yt-dlp is importable and log its version."""
    version = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    log.info("yt-dlp version: %s", version)


def check_vault_skeletons(vault_paths: Iterable[Path]) -> None:
    """Ensure each vault directory has the full Karpathy LLM Wiki skeleton."""
    for path in vault_paths:
        create_vault_skeleton(path)


def run_all(*, vault_paths: Iterable[Path]) -> None:
    check_yt_dlp()
    check_vault_skeletons(vault_paths)
