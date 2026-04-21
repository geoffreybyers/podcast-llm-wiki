# src/podcast_llm_wiki/wiki/vault.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from podcast_llm_wiki.utils.filesystem import atomic_write

VAULT_SUBDIRS = (
    "raw/transcripts",
    "episodes",
    "entities",
    "concepts",
    "comparisons",
    "queries",
)

# Located relative to this source file: ../../../docs/wiki-schema-template.md
_REPO_ROOT_HINTS = (
    Path(__file__).resolve().parents[3] / "docs" / "wiki-schema-template.md",
)

_INDEX_TEMPLATE = """# Wiki Index

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Read this first to find relevant pages for any query.
> Last updated: {created} | Total pages: 0

## Episodes

## Entities

## Concepts

## Comparisons

## Queries
"""

_LOG_TEMPLATE = """# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, update, query, lint, create, archive, delete
> When this file exceeds 500 entries, rotate: rename to log-YYYY.md, start fresh.

## [{created}] create | Vault initialized
- Created with podcast-llm-wiki
"""


def _find_schema_template() -> Optional[Path]:
    for hint in _REPO_ROOT_HINTS:
        if hint.exists():
            return hint
    return None


def _render_schema(podcast_name: str, lens: str, created_date: str) -> str:
    template_path = _find_schema_template()
    if template_path is None:
        # Last-resort minimal schema if the template isn't available (e.g., installed via pip
        # without docs/). Keep parity with the canonical template's structure.
        body = (
            "# Wiki Schema — {{podcast_name}}\n\n"
            "## Analytical Lens\n\n{{lens}}\n"
        )
    else:
        body = template_path.read_text()
    return (
        body.replace("{{podcast_name}}", podcast_name)
        .replace("{{lens}}", lens or "")
        .replace("{{created_date}}", created_date)
    )


def create_vault_skeleton(
    vault_path: Path,
    *,
    podcast_name: str = "",
    lens: str = "",
) -> None:
    """Ensure `vault_path` has the full Karpathy LLM Wiki skeleton.

    Idempotent: existing files are never overwritten. Missing files and dirs
    are created.
    """
    vault_path = Path(vault_path)
    vault_path.mkdir(parents=True, exist_ok=True)
    for sub in VAULT_SUBDIRS:
        (vault_path / sub).mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    schema_path = vault_path / "SCHEMA.md"
    if not schema_path.exists():
        atomic_write(
            schema_path,
            _render_schema(podcast_name or vault_path.name, lens, today),
        )

    index_path = vault_path / "index.md"
    if not index_path.exists():
        atomic_write(index_path, _INDEX_TEMPLATE.format(created=today))

    log_path = vault_path / "log.md"
    if not log_path.exists():
        atomic_write(log_path, _LOG_TEMPLATE.format(created=today))


def vault_exists(vault_path: Path) -> bool:
    """Return True if `vault_path` contains a full Karpathy LLM Wiki skeleton."""
    vault_path = Path(vault_path)
    return (vault_path / "SCHEMA.md").exists()
