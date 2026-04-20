# src/podcast_llm/preflight.py
from __future__ import annotations

import logging
from typing import Iterable

import yt_dlp

from podcast_llm.config import PodcastConfig
from podcast_llm.wiki.vault import create_vault_skeleton

log = logging.getLogger(__name__)


class PreflightError(RuntimeError):
    pass


def check_yt_dlp() -> None:
    """Confirm yt-dlp is importable and log its version."""
    version = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    log.info("yt-dlp version: %s", version)


def check_vault_skeletons(podcasts: Iterable[PodcastConfig]) -> None:
    """Ensure each podcast's vault has the full skeleton with populated SCHEMA.md."""
    for pod in podcasts:
        create_vault_skeleton(pod.vault_path, podcast_name=pod.name, lens=pod.lens)


def run_all(*, podcasts: Iterable[PodcastConfig]) -> None:
    check_yt_dlp()
    check_vault_skeletons(podcasts)
