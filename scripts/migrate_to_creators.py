#!/usr/bin/env python3
"""One-shot podcast -> creator migration. Idempotent; safe to re-run.

Moves the data tree and vault, and rewrites the two ledger files in place.
Run only when nothing is ingesting -- backfill.sh spawns a fresh CLI process
per run, so an in-flight batch would race these edits.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from podcast_llm_wiki.utils.filesystem import atomic_write

LEDGER_OLD_HEADER = "| podcast | channelTitle |"
LEDGER_NEW_HEADER = "| creator | channelTitle |"
QUEUE_OLD_PREFIX = "- podcasts/"
QUEUE_NEW_PREFIX = "- creators/"


def rewrite_ledger_header(text: str) -> str:
    """Rename the first column in collected.md's header row only."""
    if not text.startswith(LEDGER_OLD_HEADER):
        return text
    return text.replace(LEDGER_OLD_HEADER, LEDGER_NEW_HEADER, 1)


def rewrite_queue_paths(text: str) -> str:
    """Repoint analysis_queue.md entries at the creators/ tree."""
    return "".join(
        QUEUE_NEW_PREFIX + line[len(QUEUE_OLD_PREFIX):]
        if line.startswith(QUEUE_OLD_PREFIX)
        else line
        for line in text.splitlines(keepends=True)
    )


def main(project_root: Path, vault_root: Path, dry_run: bool) -> int:
    moves = [
        (project_root / "podcasts.yaml", project_root / "creators.yaml"),
        (project_root / "podcasts.yaml.example", project_root / "creators.yaml.example"),
        (project_root / "podcasts", project_root / "creators"),
        (vault_root / "Podcast - Huberman Lab", vault_root / "Creator - Huberman Lab"),
    ]
    rewrites = [
        (project_root / "collected.md", rewrite_ledger_header),
        (project_root / "analysis_queue.md", rewrite_queue_paths),
    ]

    # Check for ambiguous state: src and dst both existing
    for src, dst in moves:
        if src.exists() and dst.exists():
            print(f"ERROR: ambiguous state - both exist: {src} and {dst}")
            return 1

    for src, dst in moves:
        # Three-way decision per move
        if dst.exists() and not src.exists():
            # Genuinely already migrated
            print(f"skip (already migrated): {src.name}")
        elif not src.exists():
            # Source missing, destination missing
            print(f"skip (missing): {src}")
        elif dry_run:
            print(f"would move: {src} -> {dst}")
        else:
            src.rename(dst)
            print(f"moved: {src} -> {dst}")

    for path, fn in rewrites:
        if not path.exists():
            print(f"skip (missing): {path}")
            continue
        before = path.read_text()
        after = fn(before)
        if before == after:
            print(f"unchanged: {path.name}")
        elif dry_run:
            print(f"would rewrite: {path.name}")
        else:
            # Create backup with original contents if it doesn't exist
            backup_path = path.with_suffix(path.suffix + ".bak")
            if not backup_path.exists():
                atomic_write(backup_path, before)
            atomic_write(path, after)
            print(f"rewrote: {path.name}")

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=Path("."))
    ap.add_argument("--vault-root", type=Path, default=Path("~/obsidian").expanduser())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.project_root, a.vault_root, a.dry_run))
