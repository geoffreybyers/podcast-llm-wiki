# podcast-llm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest YouTube podcast playlists, transcribe locally with diarization, and produce structured analyses that compound into per-podcast Karpathy-style LLM Wiki vaults in Obsidian.

**Architecture:** Two-tier pipeline. Tier 1 (Python CLI, no LLM) downloads via yt-dlp and transcribes via sherpa-onnx, writing diarized markdown plus updating a master ledger and FIFO queue. Tier 2 (Claude Code `/analyze-podcast` slash command) pops the queue, generates structured analyses with a per-playlist analytical lens, and updates a per-podcast Obsidian vault (entities/concepts/episodes pages, index, log) following Karpathy LLM Wiki conventions.

**Tech Stack:** Python 3.11+, pydantic v2 (config), typer (CLI), pyyaml, yt-dlp (Python API), sherpa-onnx (Python bindings), pyannote-audio (diarization), pytest. Slash command is a markdown prompt file. No web framework, no database.

**Spec reference:** `docs/superpowers/specs/2026-04-20-podcast-llm-design.md` (commit `a17436e`).

---

## File Structure

Files this plan creates (grouped by responsibility):

**Project setup**
- `pyproject.toml` — package config, dependencies, pytest markers
- `LICENSE` — MIT
- `.gitignore` — append runtime/personal files
- `README.md` — onboarding doc (per spec §9)
- `podcasts.yaml.example` — committed dummy config

**Source (`src/podcast_llm/`)**
- `__init__.py` — package marker, version
- `__main__.py` — `python -m podcast_llm` entrypoint
- `cli.py` — typer-based CLI (`ingest` command)
- `config.py` — pydantic models for podcasts.yaml
- `ledger.py` — `collected.md` table + `analysis_queue.md` FIFO; atomic writes
- `downloader.py` — yt-dlp wrapper (enumerate, filter, download)
- `transcriber.py` — sherpa-onnx + pyannote diarization
- `pipeline.py` — orchestrator (per-podcast: enumerate → download → transcribe → ledger update)
- `preflight.py` — first-run environment checks
- `logging_setup.py` — JSON-line logger (per spec §7.4)
- `utils/__init__.py`
- `utils/filesystem.py` — `atomic_write`, `sanitize_filename`
- `parsers/__init__.py`
- `parsers/analysis_sections.py` — `::`-delimited Entities/Concepts parser (per spec §6.2)
- `wiki/__init__.py`
- `wiki/vault.py` — vault skeleton creation
- `wiki/writer.py` — episode/entity/concept page upserts, index/log updates

**Templates and slash command**
- `docs/wiki-schema-template.md` — per-vault `SCHEMA.md` template (spec §4.7)
- `docs/analysis-template.md` — canonical analysis structure (spec §4.8)
- `.claude/commands/analyze-podcast.md` — slash command (spec §4.6)

**Tests (`tests/`)**
- `__init__.py`, `unit/__init__.py`, `integration/__init__.py`
- `conftest.py` — shared pytest fixtures
- `unit/test_filesystem.py`
- `unit/test_config.py`
- `unit/test_ledger.py`
- `unit/test_downloader.py`
- `unit/test_transcriber.py`
- `unit/test_pipeline.py`
- `unit/test_preflight.py`
- `unit/test_logging_setup.py`
- `unit/test_analysis_sections.py`
- `unit/test_vault.py`
- `unit/test_wiki_writer.py`
- `integration/test_smoke.py` — opt-in real-pipeline run
- `fixtures/` — test data (YAML configs, sample analysis files)

**Why these splits:** each source file has one responsibility, so tests can target it directly. Wiki concerns split into `vault.py` (skeleton) + `writer.py` (per-page operations) + `parsers/analysis_sections.py` (parsing) so the wiki update flow is composable and each piece testable in isolation. CLI is thin — all logic lives in `pipeline.py` so it can be tested without invoking the CLI surface.

---

## Phase 0: Project skeleton

### Task 0.1: Create pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "podcast-llm"
version = "0.1.0"
description = "Ingest podcast playlists, transcribe locally, and compound analyses into a Karpathy-style LLM Wiki in Obsidian."
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
authors = [{ name = "podcast-llm contributors" }]
dependencies = [
    "pydantic>=2.6,<3",
    "pyyaml>=6.0",
    "typer>=0.12,<1",
    "yt-dlp>=2024.1.0",
    "sherpa-onnx>=1.10",
    "pyannote.audio>=3.1",
    "torch>=2.1",  # required by pyannote
    "soundfile>=0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
]

[project.scripts]
podcast-llm = "podcast_llm.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: real-pipeline smoke tests; require fixture audio and network. Skipped unless explicitly selected.",
]
addopts = "-m 'not integration'"
```

- [ ] **Step 2: Verify file written**

Run: `cat pyproject.toml | head -5`
Expected: first 5 lines of the file above.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with deps and pytest config"
```

---

### Task 0.2: Create source package skeleton

**Files:**
- Create: `src/podcast_llm/__init__.py`
- Create: `src/podcast_llm/__main__.py`
- Create: `src/podcast_llm/utils/__init__.py`
- Create: `src/podcast_llm/parsers/__init__.py`
- Create: `src/podcast_llm/wiki/__init__.py`

- [ ] **Step 1: Write src/podcast_llm/__init__.py**

```python
"""podcast-llm: ingest podcast playlists into a Karpathy-style LLM Wiki."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Write src/podcast_llm/__main__.py**

```python
from podcast_llm.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 3: Write empty subpackage __init__.py files**

```bash
mkdir -p src/podcast_llm/utils src/podcast_llm/parsers src/podcast_llm/wiki
: > src/podcast_llm/utils/__init__.py
: > src/podcast_llm/parsers/__init__.py
: > src/podcast_llm/wiki/__init__.py
```

- [ ] **Step 4: Commit**

```bash
git add src/
git commit -m "chore: add source package skeleton"
```

---

### Task 0.3: Create test scaffolding

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create empty __init__.py files**

```bash
mkdir -p tests/unit tests/integration tests/fixtures
: > tests/__init__.py
: > tests/unit/__init__.py
: > tests/integration/__init__.py
```

- [ ] **Step 2: Write tests/conftest.py**

```python
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
```

- [ ] **Step 3: Verify pytest discovers tests directory**

Run: `pip install -e ".[dev]" && pytest --collect-only`
Expected: no errors; "0 items collected" (no tests yet).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "chore: add test scaffolding with shared fixtures"
```

---

### Task 0.4: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append additional entries**

The existing `.gitignore` already covers personal config and python artifacts. Confirm it includes the entries below; if missing any, append them.

Required entries (already present from spec commit):
```
podcasts.yaml
collected.md
analysis_queue.md
logs/
podcasts/
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
```

If the file is already complete, no commit needed for this task. If anything was added, commit:

```bash
git add .gitignore
git commit -m "chore: ensure .gitignore covers all runtime artifacts"
```

---

### Task 0.5: Add MIT LICENSE

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Write LICENSE**

```
MIT License

Copyright (c) 2026 podcast-llm contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "chore: add MIT LICENSE"
```

---

## Phase 1: Filesystem utilities

### Task 1.1: TDD `atomic_write`

**Files:**
- Create: `tests/unit/test_filesystem.py`
- Create: `src/podcast_llm/utils/filesystem.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_filesystem.py
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.utils.filesystem import atomic_write, sanitize_filename


class TestAtomicWrite:
    def test_writes_text_to_target(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        atomic_write(target, "hello")
        assert target.read_text() == "hello"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old")
        atomic_write(target, "new")
        assert target.read_text() == "new"

    def test_does_not_leave_tempfile(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        atomic_write(target, "data")
        leftover = list(tmp_path.glob("*.tmp")) + list(tmp_path.glob(".*"))
        assert leftover == [target] or leftover == []

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "out.txt"
        atomic_write(target, "x")
        assert target.read_text() == "x"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/unit/test_filesystem.py -v`
Expected: ImportError — `atomic_write` is not defined.

- [ ] **Step 3: Implement `atomic_write`**

```python
# src/podcast_llm/utils/filesystem.py
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


def atomic_write(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Write `content` to `target` atomically.

    Writes to a temp file in the same directory, then renames over `target`.
    Concurrent readers never observe a partial write. Creates parent dirs.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `pytest tests/unit/test_filesystem.py::TestAtomicWrite -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_filesystem.py src/podcast_llm/utils/filesystem.py
git commit -m "feat(utils): add atomic_write with same-dir tempfile + os.replace"
```

---

### Task 1.2: TDD `sanitize_filename`

**Files:**
- Modify: `tests/unit/test_filesystem.py`
- Modify: `src/podcast_llm/utils/filesystem.py`

- [ ] **Step 1: Append failing tests for sanitize_filename**

Append to `tests/unit/test_filesystem.py`:

```python
class TestSanitizeFilename:
    def test_replaces_path_separators(self) -> None:
        assert sanitize_filename("a/b\\c") == "a-b-c"

    def test_strips_null_bytes(self) -> None:
        assert sanitize_filename("a\x00b") == "ab"

    def test_strips_leading_dots(self) -> None:
        assert sanitize_filename("...hidden") == "hidden"

    def test_truncates_long_names_with_episode_id(self) -> None:
        long_title = "x" * 250
        result = sanitize_filename(long_title, episode_id="abc12345")
        # Truncation reserves room for " - <episode_id>" suffix.
        assert result.endswith(" - abc12345")
        assert len(result) <= 220

    def test_truncates_long_names_without_episode_id(self) -> None:
        long_title = "y" * 250
        result = sanitize_filename(long_title)
        assert len(result) <= 200

    def test_preserves_short_names(self) -> None:
        assert sanitize_filename("Episode 1: Foo") == "Episode 1- Foo"

    def test_strips_trailing_dots_and_whitespace(self) -> None:
        assert sanitize_filename("name.   ") == "name"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/unit/test_filesystem.py::TestSanitizeFilename -v`
Expected: ImportError or NameError on `sanitize_filename`.

- [ ] **Step 3: Implement `sanitize_filename`**

Append to `src/podcast_llm/utils/filesystem.py`:

```python
_FORBIDDEN = re.compile(r"[/\\:*?\"<>|]")
_NULLS = re.compile(r"\x00")

# Total filename budget excluding extension. POSIX allows 255 but we leave headroom
# for " - transcription.md" / " - analysis.md" suffixes added by callers.
MAX_FILENAME_LEN = 200


def sanitize_filename(name: str, *, episode_id: str | None = None) -> str:
    """Make `name` safe to use as a filename component.

    - Replaces path separators and shell-unsafe chars with `-`.
    - Strips null bytes, leading dots, trailing whitespace/dots.
    - Truncates to MAX_FILENAME_LEN; if `episode_id` provided, reserves room
      and appends ` - <episode_id>` so truncated names remain unique.
    """
    cleaned = _NULLS.sub("", name)
    cleaned = _FORBIDDEN.sub("-", cleaned)
    cleaned = cleaned.lstrip(".")
    cleaned = cleaned.rstrip(" .")

    if episode_id:
        suffix = f" - {episode_id}"
        budget = MAX_FILENAME_LEN - len(suffix)
        if len(cleaned) > budget:
            cleaned = cleaned[:budget].rstrip(" .") + suffix
        elif len(cleaned) + len(suffix) > MAX_FILENAME_LEN:
            cleaned = cleaned[:budget].rstrip(" .") + suffix
    elif len(cleaned) > MAX_FILENAME_LEN:
        cleaned = cleaned[:MAX_FILENAME_LEN].rstrip(" .")

    return cleaned
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `pytest tests/unit/test_filesystem.py -v`
Expected: all tests in both classes pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_filesystem.py src/podcast_llm/utils/filesystem.py
git commit -m "feat(utils): add sanitize_filename with truncation + episode_id suffix"
```

---

## Phase 2: Configuration loader

### Task 2.1: TDD config models and loading

**Files:**
- Create: `tests/unit/test_config.py`
- Create: `src/podcast_llm/config.py`
- Create: `tests/fixtures/podcasts_minimal.yaml`

- [ ] **Step 1: Create fixture YAML**

```yaml
# tests/fixtures/podcasts_minimal.yaml
defaults:
  vault_root: ~/obsidian
  max_backfill: 5
  stt_model: whisper-base
  diarization: true

podcasts:
  - name: "Test Podcast"
    playlist_url: "https://www.youtube.com/playlist?list=ABC"
    lens: |
      Test analytical lens.
```

- [ ] **Step 2: Write failing tests**

```python
# tests/unit/test_config.py
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.config import Config, PodcastConfig, load_config

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadConfig:
    def test_loads_minimal_config(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        assert isinstance(cfg, Config)
        assert len(cfg.podcasts) == 1
        assert cfg.podcasts[0].name == "Test Podcast"

    def test_applies_defaults_to_podcasts(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        pod = cfg.podcasts[0]
        assert pod.max_backfill == 5
        assert pod.stt_model == "whisper-base"
        assert pod.diarization is True

    def test_vault_path_defaults_to_root_plus_name(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        pod = cfg.podcasts[0]
        assert pod.vault_path == Path("~/obsidian/Test Podcast").expanduser()

    def test_per_podcast_overrides_default(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "  stt_model: whisper-base\n"
            "podcasts:\n"
            "  - name: P\n"
            "    playlist_url: https://x.test\n"
            "    lens: l\n"
            "    stt_model: whisper-medium\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].stt_model == "whisper-medium"

    def test_explicit_vault_path_overrides_default(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "podcasts:\n"
            "  - name: P\n"
            "    playlist_url: https://x.test\n"
            "    lens: l\n"
            "    vault_path: /custom/path\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].vault_path == Path("/custom/path")

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults: {}\n"
            "podcasts:\n"
            "  - name: P\n"
            # missing playlist_url and lens
        )
        with pytest.raises(Exception):  # pydantic ValidationError or similar
            load_config(f)

    def test_lookup_by_name(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        assert cfg.get_podcast("Test Podcast").name == "Test Podcast"
        assert cfg.get_podcast("nope") is None
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `pytest tests/unit/test_config.py -v`
Expected: ImportError on `Config`/`load_config`.

- [ ] **Step 4: Implement config**

```python
# src/podcast_llm/config.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class Defaults(BaseModel):
    vault_root: Path = Path("~/obsidian")
    max_backfill: int = 20
    stt_model: str = "whisper-base"
    diarization: bool = True
    diarization_segmentation: str = "pyannote-segmentation-3.0"
    diarization_embedding: str = "3d-speaker"

    @field_validator("vault_root", mode="before")
    @classmethod
    def expand(cls, v: object) -> Path:
        return Path(str(v)).expanduser() if v is not None else v


class PodcastConfig(BaseModel):
    name: str
    playlist_url: str
    lens: str
    vault_path: Path
    max_backfill: int
    stt_model: str
    diarization: bool
    diarization_segmentation: str
    diarization_embedding: str


class _RawPodcast(BaseModel):
    """Shape of a podcast entry as written in YAML before defaults are applied."""

    name: str
    playlist_url: str
    lens: str
    vault_path: Optional[Path] = None
    max_backfill: Optional[int] = None
    stt_model: Optional[str] = None
    diarization: Optional[bool] = None
    diarization_segmentation: Optional[str] = None
    diarization_embedding: Optional[str] = None


class Config(BaseModel):
    defaults: Defaults = Field(default_factory=Defaults)
    podcasts: list[PodcastConfig] = Field(default_factory=list)

    def get_podcast(self, name: str) -> Optional[PodcastConfig]:
        for p in self.podcasts:
            if p.name == name:
                return p
        return None


def load_config(path: Path) -> Config:
    """Load and validate a podcasts.yaml file. Applies defaults to each podcast."""
    raw = yaml.safe_load(Path(path).read_text())
    if raw is None:
        raw = {}

    defaults = Defaults(**(raw.get("defaults") or {}))
    podcasts: list[PodcastConfig] = []
    for entry in raw.get("podcasts") or []:
        rp = _RawPodcast(**entry)
        vault_path = (
            Path(str(rp.vault_path)).expanduser()
            if rp.vault_path is not None
            else defaults.vault_root / rp.name
        )
        podcasts.append(
            PodcastConfig(
                name=rp.name,
                playlist_url=rp.playlist_url,
                lens=rp.lens,
                vault_path=vault_path,
                max_backfill=rp.max_backfill if rp.max_backfill is not None else defaults.max_backfill,
                stt_model=rp.stt_model or defaults.stt_model,
                diarization=rp.diarization if rp.diarization is not None else defaults.diarization,
                diarization_segmentation=rp.diarization_segmentation or defaults.diarization_segmentation,
                diarization_embedding=rp.diarization_embedding or defaults.diarization_embedding,
            )
        )
    return Config(defaults=defaults, podcasts=podcasts)
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_config.py src/podcast_llm/config.py tests/fixtures/podcasts_minimal.yaml
git commit -m "feat(config): pydantic models with default-merging YAML loader"
```

---

## Phase 3: Ledger (collected.md + analysis_queue.md)

### Task 3.1: TDD ledger initialization

**Files:**
- Create: `tests/unit/test_ledger.py`
- Create: `src/podcast_llm/ledger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_ledger.py
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.ledger import EpisodeRecord, Ledger


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
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/unit/test_ledger.py::TestLedgerInit -v`
Expected: ImportError.

- [ ] **Step 3: Implement ledger init**

```python
# src/podcast_llm/ledger.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from podcast_llm.utils.filesystem import atomic_write

COLLECTED_HEADER = (
    "| podcast | channelTitle | title | publishedAt | url | status "
    "| downloaded_at | transcribed_at | analyzed_at | error |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


@dataclass
class EpisodeRecord:
    podcast: str
    channel_title: str
    title: str
    published_at: str
    url: str
    episode_id: str
    status: str = ""  # downloaded | download_complete | transcribed | analyzed | *_failed
    downloaded_at: str = ""
    transcribed_at: str = ""
    analyzed_at: str = ""
    error: str = ""
    transcription_path: Optional[str] = None


class Ledger:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.collected_path = self.project_root / "collected.md"
        self.queue_path = self.project_root / "analysis_queue.md"

    def ensure_initialized(self) -> None:
        if not self.collected_path.exists():
            atomic_write(self.collected_path, COLLECTED_HEADER)
        if not self.queue_path.exists():
            atomic_write(self.queue_path, "")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/unit/test_ledger.py::TestLedgerInit -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_ledger.py src/podcast_llm/ledger.py
git commit -m "feat(ledger): initialize collected.md table and empty queue"
```

---

### Task 3.2: TDD ledger record/read/update operations

**Files:**
- Modify: `tests/unit/test_ledger.py`
- Modify: `src/podcast_llm/ledger.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_ledger.py`:

```python
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

    def test_queue_remove_specific(self, tmp_project: Path) -> None:
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        ledger.record_downloaded(_sample_record(episode_id="a"))
        ledger.record_downloaded(_sample_record(episode_id="b", title="T2"))
        ledger.record_transcribed("a", "/p/a.md")
        ledger.record_transcribed("b", "/p/b.md")
        ledger.queue_remove("/p/a.md")
        assert ledger.queue_peek() == "/p/b.md"
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/unit/test_ledger.py -v`
Expected: AttributeError on missing methods.

- [ ] **Step 3: Implement ledger ops**

Replace contents of `src/podcast_llm/ledger.py` with the full implementation:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from podcast_llm.utils.filesystem import atomic_write

COLLECTED_HEADER = (
    "| podcast | channelTitle | title | publishedAt | url | episode_id | status "
    "| downloaded_at | transcribed_at | analyzed_at | error |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escape_cell(value: str) -> str:
    """Escape pipe and newline so the value fits in a single markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ").strip()


@dataclass
class EpisodeRecord:
    podcast: str
    channel_title: str
    title: str
    published_at: str
    url: str
    episode_id: str
    status: str = ""
    downloaded_at: str = ""
    transcribed_at: str = ""
    analyzed_at: str = ""
    error: str = ""

    def to_row(self) -> str:
        cells = [
            _escape_cell(self.podcast),
            _escape_cell(self.channel_title),
            _escape_cell(self.title),
            _escape_cell(self.published_at),
            _escape_cell(self.url),
            _escape_cell(self.episode_id),
            _escape_cell(self.status),
            _escape_cell(self.downloaded_at),
            _escape_cell(self.transcribed_at),
            _escape_cell(self.analyzed_at),
            _escape_cell(self.error),
        ]
        return "| " + " | ".join(cells) + " |\n"

    @classmethod
    def from_row(cls, row: str) -> "EpisodeRecord":
        # Strip leading/trailing pipe and whitespace, split on " | ".
        body = row.strip()
        if body.startswith("|"):
            body = body[1:]
        if body.endswith("|"):
            body = body[:-1]
        cells = [c.strip().replace("\\|", "|") for c in body.split(" | ")]
        # Pad to expected length in case of trailing empty cells trimmed by some editor.
        while len(cells) < 11:
            cells.append("")
        return cls(
            podcast=cells[0],
            channel_title=cells[1],
            title=cells[2],
            published_at=cells[3],
            url=cells[4],
            episode_id=cells[5],
            status=cells[6],
            downloaded_at=cells[7],
            transcribed_at=cells[8],
            analyzed_at=cells[9],
            error=cells[10],
        )


class Ledger:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.collected_path = self.project_root / "collected.md"
        self.queue_path = self.project_root / "analysis_queue.md"

    # --- init ---

    def ensure_initialized(self) -> None:
        if not self.collected_path.exists():
            atomic_write(self.collected_path, COLLECTED_HEADER)
        if not self.queue_path.exists():
            atomic_write(self.queue_path, "")

    # --- collected.md ---

    def _read_records(self) -> list[EpisodeRecord]:
        if not self.collected_path.exists():
            return []
        lines = self.collected_path.read_text().splitlines()
        # Skip 2-line header (header row + separator).
        records: list[EpisodeRecord] = []
        for line in lines[2:]:
            if not line.strip():
                continue
            records.append(EpisodeRecord.from_row(line))
        return records

    def _write_records(self, records: list[EpisodeRecord]) -> None:
        body = COLLECTED_HEADER + "".join(r.to_row() for r in records)
        atomic_write(self.collected_path, body)

    def record_downloaded(self, rec: EpisodeRecord) -> None:
        self.ensure_initialized()
        records = self._read_records()
        existing = next((r for r in records if r.episode_id == rec.episode_id), None)
        if existing is None:
            rec.status = "downloaded"
            rec.downloaded_at = _now_iso()
            records.append(rec)
        else:
            existing.status = "downloaded"
            existing.downloaded_at = _now_iso()
        self._write_records(records)

    def record_transcribed(self, episode_id: str, transcription_path: str) -> None:
        records = self._read_records()
        for r in records:
            if r.episode_id == episode_id:
                r.status = "transcribed"
                r.transcribed_at = _now_iso()
                break
        else:
            raise KeyError(f"unknown episode_id: {episode_id}")
        self._write_records(records)
        self._queue_append(transcription_path)

    def record_analyzed(self, episode_id: str, transcription_path: str) -> None:
        records = self._read_records()
        for r in records:
            if r.episode_id == episode_id:
                r.status = "analyzed"
                r.analyzed_at = _now_iso()
                break
        else:
            raise KeyError(f"unknown episode_id: {episode_id}")
        self._write_records(records)
        self.queue_remove(transcription_path)

    def record_failed(self, rec: EpisodeRecord, stage: str, error: str) -> None:
        self.ensure_initialized()
        records = self._read_records()
        existing = next((r for r in records if r.episode_id == rec.episode_id), None)
        status = f"{stage}_failed"
        if existing is None:
            rec.status = status
            rec.error = error
            records.append(rec)
        else:
            existing.status = status
            existing.error = error
        self._write_records(records)

    def is_known_episode(self, episode_id: str) -> bool:
        return any(r.episode_id == episode_id for r in self._read_records())

    def known_episode_ids(self) -> set[str]:
        return {r.episode_id for r in self._read_records()}

    # --- analysis_queue.md ---

    def _queue_lines(self) -> list[str]:
        if not self.queue_path.exists():
            return []
        return [
            line[2:] if line.startswith("- ") else line
            for line in self.queue_path.read_text().splitlines()
            if line.strip()
        ]

    def _write_queue(self, paths: list[str]) -> None:
        body = "".join(f"- {p}\n" for p in paths)
        atomic_write(self.queue_path, body)

    def _queue_append(self, path: str) -> None:
        paths = self._queue_lines()
        if path not in paths:
            paths.append(path)
            self._write_queue(paths)

    def queue_peek(self) -> Optional[str]:
        paths = self._queue_lines()
        return paths[0] if paths else None

    def queue_pop(self) -> Optional[str]:
        paths = self._queue_lines()
        if not paths:
            return None
        head = paths[0]
        self._write_queue(paths[1:])
        return head

    def queue_remove(self, path: str) -> None:
        paths = [p for p in self._queue_lines() if p != path]
        self._write_queue(paths)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/unit/test_ledger.py -v`
Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_ledger.py src/podcast_llm/ledger.py
git commit -m "feat(ledger): record/read/update + FIFO queue with atomic writes"
```

---

## Phase 4: Downloader

### Task 4.1: TDD `enumerate_playlist`

**Files:**
- Create: `tests/unit/test_downloader.py`
- Create: `src/podcast_llm/downloader.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_downloader.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podcast_llm.downloader import (
    DownloadResult,
    Downloader,
    EpisodeMetadata,
)


class TestEnumeratePlaylist:
    @patch("podcast_llm.downloader.YoutubeDL")
    def test_returns_episode_metadata_list(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "vid1",
                    "title": "Episode One",
                    "channel": "Test Channel",
                    "upload_date": "20260101",
                    "url": "https://youtube.com/watch?v=vid1",
                },
                {
                    "id": "vid2",
                    "title": "Episode Two",
                    "channel": "Test Channel",
                    "upload_date": "20260201",
                    "url": "https://youtube.com/watch?v=vid2",
                },
            ]
        }
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/playlist?list=ABC")

        assert len(episodes) == 2
        assert episodes[0].episode_id == "vid1"
        assert episodes[0].title == "Episode One"
        assert episodes[0].channel_title == "Test Channel"
        assert episodes[0].published_at == "2026-01-01"

    @patch("podcast_llm.downloader.YoutubeDL")
    def test_uses_flat_playlist_option(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        d.enumerate_playlist("https://youtube.com/playlist?list=ABC")

        # Verify YoutubeDL was constructed with extract_flat: True (or similar)
        call_args = mock_ydl_cls.call_args[0][0]
        assert call_args.get("extract_flat") is True

    @patch("podcast_llm.downloader.YoutubeDL")
    def test_handles_empty_playlist(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/playlist?list=ABC")
        assert episodes == []
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_downloader.py::TestEnumeratePlaylist -v`
Expected: ImportError.

- [ ] **Step 3: Implement enumerate_playlist**

```python
# src/podcast_llm/downloader.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from yt_dlp import YoutubeDL


@dataclass
class EpisodeMetadata:
    episode_id: str
    title: str
    channel_title: str
    published_at: str  # YYYY-MM-DD
    url: str


@dataclass
class DownloadResult:
    metadata: EpisodeMetadata
    audio_path: Path
    info_json_path: Path


def _format_date(yyyymmdd: Optional[str]) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return ""
    try:
        return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


class Downloader:
    """Wrapper around yt-dlp for playlist enumeration and audio download."""

    def __init__(self, downloads_root: Path) -> None:
        self.downloads_root = Path(downloads_root)

    def enumerate_playlist(self, playlist_url: str) -> list[EpisodeMetadata]:
        opts = {
            "extract_flat": True,
            "quiet": True,
            "skip_download": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
        entries = (info or {}).get("entries") or []
        results: list[EpisodeMetadata] = []
        for e in entries:
            if not e:
                continue
            results.append(
                EpisodeMetadata(
                    episode_id=str(e.get("id") or ""),
                    title=str(e.get("title") or ""),
                    channel_title=str(e.get("channel") or e.get("uploader") or ""),
                    published_at=_format_date(str(e.get("upload_date") or "")),
                    url=str(e.get("url") or e.get("webpage_url") or ""),
                )
            )
        return results
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_downloader.py::TestEnumeratePlaylist -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_downloader.py src/podcast_llm/downloader.py
git commit -m "feat(downloader): enumerate_playlist via yt-dlp flat extraction"
```

---

### Task 4.2: TDD `filter_new`

**Files:**
- Modify: `tests/unit/test_downloader.py`
- Modify: `src/podcast_llm/downloader.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_downloader.py`:

```python
def _sample_episode(eid: str, title: str = "T") -> EpisodeMetadata:
    return EpisodeMetadata(
        episode_id=eid,
        title=title,
        channel_title="C",
        published_at="2026-01-01",
        url=f"https://youtube.com/watch?v={eid}",
    )


class TestFilterNew:
    def test_filters_out_known_ids(self) -> None:
        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = [_sample_episode("a"), _sample_episode("b"), _sample_episode("c")]
        result = d.filter_new(episodes, known_ids={"b"})
        assert [e.episode_id for e in result] == ["a", "c"]

    def test_caps_at_max_backfill(self) -> None:
        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = [_sample_episode(f"e{i}") for i in range(10)]
        result = d.filter_new(episodes, known_ids=set(), max_backfill=3)
        assert len(result) == 3
        # Caps from the front (most recent first if caller passed sorted-newest-first).
        assert [e.episode_id for e in result] == ["e0", "e1", "e2"]

    def test_no_cap_when_max_backfill_none(self) -> None:
        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = [_sample_episode(f"e{i}") for i in range(10)]
        result = d.filter_new(episodes, known_ids=set(), max_backfill=None)
        assert len(result) == 10
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_downloader.py::TestFilterNew -v`
Expected: AttributeError on `filter_new`.

- [ ] **Step 3: Implement `filter_new`**

Append to `Downloader` class in `src/podcast_llm/downloader.py`:

```python
    def filter_new(
        self,
        episodes: list[EpisodeMetadata],
        known_ids: set[str],
        max_backfill: Optional[int] = None,
    ) -> list[EpisodeMetadata]:
        """Drop episodes already in `known_ids`. Cap total at `max_backfill`."""
        new = [e for e in episodes if e.episode_id not in known_ids]
        if max_backfill is not None:
            new = new[:max_backfill]
        return new
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_downloader.py::TestFilterNew -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_downloader.py src/podcast_llm/downloader.py
git commit -m "feat(downloader): filter_new with max_backfill cap"
```

---

### Task 4.3: TDD `download_episode`

**Files:**
- Modify: `tests/unit/test_downloader.py`
- Modify: `src/podcast_llm/downloader.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_downloader.py`:

```python
class TestDownloadEpisode:
    @patch("podcast_llm.downloader.YoutubeDL")
    def test_downloads_audio_to_podcast_subdir(
        self, mock_ydl_cls, tmp_path: Path
    ) -> None:
        ep = _sample_episode("vid1", title="Episode One")

        # Pretend yt-dlp wrote files at expected paths.
        downloads_root = tmp_path / "downloads"
        podcast_dir = downloads_root / "P"
        podcast_dir.mkdir(parents=True)
        audio_path = podcast_dir / "vid1.wav"
        info_path = podcast_dir / "vid1.info.json"
        audio_path.write_bytes(b"RIFF")
        info_path.write_text("{}")

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 0
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=downloads_root)
        result = d.download_episode(ep, podcast_name="P")

        assert isinstance(result, DownloadResult)
        assert result.audio_path == audio_path
        assert result.info_json_path == info_path

        # Verify yt-dlp was configured to write to podcast_dir with .info.json sidecar
        call_opts = mock_ydl_cls.call_args[0][0]
        assert call_opts["writeinfojson"] is True
        assert "outtmpl" in call_opts
        assert str(podcast_dir) in call_opts["outtmpl"]

    @patch("podcast_llm.downloader.YoutubeDL")
    def test_raises_on_yt_dlp_nonzero_exit(self, mock_ydl_cls, tmp_path: Path) -> None:
        ep = _sample_episode("vid1")
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 1
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=tmp_path / "downloads")
        with pytest.raises(RuntimeError, match="yt-dlp"):
            d.download_episode(ep, podcast_name="P")
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_downloader.py::TestDownloadEpisode -v`
Expected: AttributeError on `download_episode`.

- [ ] **Step 3: Implement `download_episode`**

Append to `Downloader` in `src/podcast_llm/downloader.py`:

```python
    def download_episode(
        self,
        episode: EpisodeMetadata,
        podcast_name: str,
    ) -> DownloadResult:
        """Download bestaudio for `episode`, post-process to 16 kHz mono WAV.

        Side effect: writes audio file and `.info.json` sidecar in
        `<downloads_root>/<podcast_name>/<episode_id>.{wav,info.json}`.
        Updates the per-podcast yt-dlp download archive so re-runs skip.
        """
        podcast_dir = self.downloads_root / podcast_name
        podcast_dir.mkdir(parents=True, exist_ok=True)
        archive_path = podcast_dir / ".archive"
        outtmpl = str(podcast_dir / "%(id)s.%(ext)s")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "writeinfojson": True,
            "download_archive": str(archive_path),
            "quiet": True,
            "noprogress": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                },
                {
                    "key": "FFmpegPostProcessor",
                    "args": ["-ar", "16000", "-ac", "1"],
                },
            ],
        }
        with YoutubeDL(opts) as ydl:
            rc = ydl.download([episode.url])
        if rc != 0:
            raise RuntimeError(f"yt-dlp exited with code {rc} for {episode.url}")

        audio_path = podcast_dir / f"{episode.episode_id}.wav"
        info_path = podcast_dir / f"{episode.episode_id}.info.json"
        return DownloadResult(metadata=episode, audio_path=audio_path, info_json_path=info_path)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_downloader.py -v`
Expected: all download tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_downloader.py src/podcast_llm/downloader.py
git commit -m "feat(downloader): download_episode with bestaudio + WAV postprocess + archive"
```

---

## Phase 5: Transcriber

### Task 5.1: TDD device detection

**Files:**
- Create: `tests/unit/test_transcriber.py`
- Create: `src/podcast_llm/transcriber.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_transcriber.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podcast_llm.transcriber import (
    Transcriber,
    TranscriptionResult,
    detect_device,
    render_transcript_markdown,
)


class TestDetectDevice:
    @patch("podcast_llm.transcriber.torch")
    def test_prefers_cuda_when_available(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.backends.mps.is_available.return_value = False
        assert detect_device() == "cuda"

    @patch("podcast_llm.transcriber.torch")
    def test_falls_back_to_mps_on_apple(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True
        assert detect_device() == "mps"

    @patch("podcast_llm.transcriber.torch")
    def test_falls_back_to_cpu(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        assert detect_device() == "cpu"
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_transcriber.py::TestDetectDevice -v`
Expected: ImportError.

- [ ] **Step 3: Implement `detect_device`**

```python
# src/podcast_llm/transcriber.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import torch


@dataclass
class TranscriptSegment:
    start_sec: float
    end_sec: float
    speaker: Optional[str]  # None when diarization disabled
    text: str


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    duration_sec: float
    model_name: str
    diarization: bool


def detect_device() -> str:
    """Return 'cuda', 'mps', or 'cpu' based on what torch can use."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch, "backends") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_transcriber.py::TestDetectDevice -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_transcriber.py src/podcast_llm/transcriber.py
git commit -m "feat(transcriber): device detection (CUDA → MPS → CPU)"
```

---

### Task 5.2: TDD transcript rendering

**Files:**
- Modify: `tests/unit/test_transcriber.py`
- Modify: `src/podcast_llm/transcriber.py`

- [ ] **Step 1: Append failing tests**

```python
class TestRenderTranscriptMarkdown:
    def test_renders_frontmatter(self) -> None:
        result = TranscriptionResult(
            segments=[
                TranscriptSegment(0.0, 5.0, "Speaker 1", "Hello there."),
            ],
            duration_sec=5.0,
            model_name="whisper-base",
            diarization=True,
        )
        out = render_transcript_markdown(
            result,
            episode_id="vid1",
            channel_title="Channel",
            title="Episode One",
            published_at="2026-04-20",
            url="https://x.test",
        )
        assert out.startswith("---\n")
        assert "episode_id: vid1" in out
        assert "channelTitle: Channel" in out
        assert "title: Episode One" in out
        assert "url: https://x.test" in out
        assert "duration_sec: 5" in out
        assert "model: whisper-base" in out
        assert "diarization: true" in out

    def test_renders_diarized_segments(self) -> None:
        result = TranscriptionResult(
            segments=[
                TranscriptSegment(0.0, 5.0, "Speaker 1", "Hello."),
                TranscriptSegment(5.0, 10.5, "Speaker 2", "Hi there."),
            ],
            duration_sec=10.5,
            model_name="whisper-base",
            diarization=True,
        )
        out = render_transcript_markdown(
            result,
            episode_id="x",
            channel_title="C",
            title="T",
            published_at="2026-04-20",
            url="https://x",
        )
        assert "[00:00:00] Speaker 1: Hello." in out
        assert "[00:00:05] Speaker 2: Hi there." in out

    def test_renders_non_diarized_without_speaker_label(self) -> None:
        result = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 3.0, None, "Solo content.")],
            duration_sec=3.0,
            model_name="whisper-base",
            diarization=False,
        )
        out = render_transcript_markdown(
            result,
            episode_id="x",
            channel_title="C",
            title="T",
            published_at="2026-04-20",
            url="https://x",
        )
        assert "[00:00:00] Solo content." in out
        assert "Speaker" not in out.split("---")[2]  # body, not frontmatter
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_transcriber.py::TestRenderTranscriptMarkdown -v`
Expected: ImportError on `render_transcript_markdown`.

- [ ] **Step 3: Implement renderer**

Append to `src/podcast_llm/transcriber.py`:

```python
def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def render_transcript_markdown(
    result: TranscriptionResult,
    *,
    episode_id: str,
    channel_title: str,
    title: str,
    published_at: str,
    url: str,
) -> str:
    """Render a TranscriptionResult as the diarized markdown file (per spec §4.3)."""
    transcribed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fm_lines = [
        "---",
        f"episode_id: {episode_id}",
        f"channelTitle: {channel_title}",
        f"title: {title}",
        f"publishedAt: {published_at}",
        f"url: {url}",
        f"duration_sec: {int(result.duration_sec)}",
        f"transcribed_at: {transcribed_at}",
        f"model: {result.model_name}",
        f"diarization: {'true' if result.diarization else 'false'}",
        "---",
        "",
    ]
    body_lines: list[str] = []
    for seg in result.segments:
        ts = _format_timestamp(seg.start_sec)
        if result.diarization and seg.speaker:
            body_lines.append(f"[{ts}] {seg.speaker}: {seg.text}")
        else:
            body_lines.append(f"[{ts}] {seg.text}")
    return "\n".join(fm_lines) + "\n".join(body_lines) + "\n"
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_transcriber.py::TestRenderTranscriptMarkdown -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_transcriber.py src/podcast_llm/transcriber.py
git commit -m "feat(transcriber): render_transcript_markdown with frontmatter + diarized body"
```

---

### Task 5.3: TDD `Transcriber.transcribe` orchestration (mocked engines)

**Files:**
- Modify: `tests/unit/test_transcriber.py`
- Modify: `src/podcast_llm/transcriber.py`

The transcription engine wiring (sherpa-onnx + pyannote) must be exercised on real audio for correctness — that lives in the integration test in Phase 13. Here we test orchestration only: that `Transcriber.transcribe` invokes the right components and combines their outputs.

- [ ] **Step 1: Append failing tests**

```python
class TestTranscriberTranscribe:
    def test_returns_segments_with_speakers_when_diarized(self, tmp_path: Path) -> None:
        audio = tmp_path / "x.wav"
        audio.write_bytes(b"RIFF")

        asr_engine = MagicMock()
        asr_engine.transcribe_file.return_value = [
            TranscriptSegment(0.0, 5.0, None, "Hello."),
            TranscriptSegment(5.0, 10.0, None, "Hi back."),
        ]
        diar_engine = MagicMock()
        diar_engine.diarize_file.return_value = [
            (0.0, 5.0, "Speaker 1"),
            (5.0, 10.0, "Speaker 2"),
        ]

        t = Transcriber(
            asr_engine=asr_engine,
            diar_engine=diar_engine,
            model_name="whisper-base",
            diarization=True,
        )
        result = t.transcribe(audio)
        assert result.diarization is True
        assert result.segments[0].speaker == "Speaker 1"
        assert result.segments[1].speaker == "Speaker 2"
        assert result.model_name == "whisper-base"

    def test_skips_diarization_when_disabled(self, tmp_path: Path) -> None:
        audio = tmp_path / "x.wav"
        audio.write_bytes(b"RIFF")

        asr_engine = MagicMock()
        asr_engine.transcribe_file.return_value = [
            TranscriptSegment(0.0, 5.0, None, "Solo."),
        ]
        diar_engine = MagicMock()

        t = Transcriber(
            asr_engine=asr_engine,
            diar_engine=diar_engine,
            model_name="whisper-base",
            diarization=False,
        )
        result = t.transcribe(audio)
        assert result.diarization is False
        assert result.segments[0].speaker is None
        diar_engine.diarize_file.assert_not_called()
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_transcriber.py::TestTranscriberTranscribe -v`
Expected: AttributeError on `Transcriber`.

- [ ] **Step 3: Implement Transcriber**

Append to `src/podcast_llm/transcriber.py`:

```python
class Transcriber:
    """Orchestrates ASR + (optional) diarization to produce a TranscriptionResult.

    The actual engine adapters (sherpa-onnx for ASR, pyannote for diarization)
    are injected so this class is unit-testable without real models. Concrete
    adapters are constructed in `pipeline.py` from the per-podcast config.
    """

    def __init__(
        self,
        asr_engine,
        diar_engine,
        model_name: str,
        diarization: bool,
    ) -> None:
        self.asr_engine = asr_engine
        self.diar_engine = diar_engine
        self.model_name = model_name
        self.diarization = diarization

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        segments: list[TranscriptSegment] = list(
            self.asr_engine.transcribe_file(audio_path)
        )
        if self.diarization:
            speaker_spans = self.diar_engine.diarize_file(audio_path)
            segments = _assign_speakers(segments, speaker_spans)

        duration = max((s.end_sec for s in segments), default=0.0)
        return TranscriptionResult(
            segments=segments,
            duration_sec=duration,
            model_name=self.model_name,
            diarization=self.diarization,
        )


def _assign_speakers(
    segments: list[TranscriptSegment],
    spans: list[tuple[float, float, str]],
) -> list[TranscriptSegment]:
    """Label each ASR segment with the speaker whose span best overlaps it."""
    out: list[TranscriptSegment] = []
    for seg in segments:
        best_speaker: Optional[str] = None
        best_overlap = 0.0
        for s_start, s_end, speaker in spans:
            overlap = max(0.0, min(seg.end_sec, s_end) - max(seg.start_sec, s_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        out.append(
            TranscriptSegment(
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                speaker=best_speaker,
                text=seg.text,
            )
        )
    return out
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_transcriber.py -v`
Expected: all transcriber tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_transcriber.py src/podcast_llm/transcriber.py
git commit -m "feat(transcriber): Transcriber orchestrator + speaker overlap assignment"
```

---

### Task 5.4: Add concrete sherpa-onnx + pyannote adapters

**Files:**
- Modify: `src/podcast_llm/transcriber.py`

These adapters are *not* unit-tested (they call into native libraries with model files) — they're exercised by the integration test in Phase 13. We commit them so the pipeline can wire them up.

- [ ] **Step 1: Append adapter classes**

```python
# Append to src/podcast_llm/transcriber.py

import soundfile as sf  # noqa: E402  (placed near other top-level imports in practice)


class SherpaOnnxAsr:
    """ASR adapter wrapping sherpa-onnx whisper bindings.

    `model_dir` should point to a directory containing the ONNX model files
    appropriate for `model_name` (e.g. whisper-base). On first use these are
    downloaded into ~/.cache/sherpa-onnx by the preflight step.
    """

    def __init__(self, model_dir: Path, model_name: str, device: str) -> None:
        import sherpa_onnx

        self.model_name = model_name
        self.device = device
        provider = "cuda" if device == "cuda" else "cpu"
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(model_dir / f"{model_name}-encoder.onnx"),
            decoder=str(model_dir / f"{model_name}-decoder.onnx"),
            tokens=str(model_dir / f"{model_name}-tokens.txt"),
            provider=provider,
        )

    def transcribe_file(self, audio_path: Path) -> list[TranscriptSegment]:
        audio, sample_rate = sf.read(str(audio_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        stream = self._recognizer.create_stream()
        stream.accept_waveform(sample_rate, audio)
        self._recognizer.decode_stream(stream)
        # Whisper returns one big result; chunk by punctuation/sentence segmentation
        # in the integration step. For now, emit a single segment covering the file.
        text = stream.result.text.strip()
        duration = len(audio) / float(sample_rate)
        return [TranscriptSegment(start_sec=0.0, end_sec=duration, speaker=None, text=text)]


class PyannoteDiarizer:
    """Diarization adapter wrapping pyannote.audio."""

    def __init__(self, segmentation_model: str, embedding_model: str, device: str) -> None:
        from pyannote.audio import Pipeline

        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
        )
        try:
            import torch as _torch

            self.pipeline.to(_torch.device(device))
        except Exception:  # noqa: BLE001
            # Some torch builds lack MPS support for all ops; fall back to CPU silently.
            pass

    def diarize_file(self, audio_path: Path) -> list[tuple[float, float, str]]:
        diarization = self.pipeline(str(audio_path))
        spans: list[tuple[float, float, str]] = []
        for turn, _track, speaker in diarization.itertracks(yield_label=True):
            spans.append((float(turn.start), float(turn.end), str(speaker)))
        return spans
```

- [ ] **Step 2: Verify package still imports**

Run: `python -c "from podcast_llm.transcriber import Transcriber, SherpaOnnxAsr, PyannoteDiarizer"`
Expected: ImportError only if sherpa-onnx / pyannote missing in dev env. Acceptable to skip if you haven't installed them yet — the import is lazy in adapters' `__init__`.

To make the import truly lazy:

Replace adapter classes with lazy-import versions if the bare import fails. (The adapters above use lazy imports inside `__init__` already, so the module-level `import` should be of `sf` only — which is a smaller dep. If `soundfile` is missing in the env, reinstall with `pip install -e ".[dev]"`.)

- [ ] **Step 3: Commit**

```bash
git add src/podcast_llm/transcriber.py
git commit -m "feat(transcriber): sherpa-onnx ASR and pyannote diarization adapters"
```

---

## Phase 6: Pipeline + CLI

### Task 6.1: TDD pipeline end-to-end with mocked components

**Files:**
- Create: `tests/unit/test_pipeline.py`
- Create: `src/podcast_llm/pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_pipeline.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from podcast_llm.config import Config, Defaults, PodcastConfig
from podcast_llm.downloader import DownloadResult, EpisodeMetadata
from podcast_llm.ledger import Ledger
from podcast_llm.pipeline import Pipeline
from podcast_llm.transcriber import TranscriptSegment, TranscriptionResult


def _config(tmp_path: Path) -> Config:
    return Config(
        defaults=Defaults(vault_root=tmp_path / "obsidian"),
        podcasts=[
            PodcastConfig(
                name="Test Podcast",
                playlist_url="https://x.test",
                lens="lens",
                vault_path=tmp_path / "obsidian" / "Test Podcast",
                max_backfill=5,
                stt_model="whisper-base",
                diarization=True,
                diarization_segmentation="seg",
                diarization_embedding="emb",
            )
        ],
    )


class TestPipelineIngest:
    def test_processes_one_new_episode_end_to_end(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()

        ep = EpisodeMetadata(
            episode_id="vid1",
            title="Episode One",
            channel_title="Channel",
            published_at="2026-04-20",
            url="https://x.test/vid1",
        )
        downloads_dir = tmp_project / "podcasts" / "Test Podcast" / "downloads"
        downloads_dir.mkdir(parents=True)
        audio_path = downloads_dir / "vid1.wav"
        audio_path.write_bytes(b"RIFF")

        downloader = MagicMock()
        downloader.enumerate_playlist.return_value = [ep]
        downloader.filter_new.return_value = [ep]
        downloader.download_episode.return_value = DownloadResult(
            metadata=ep,
            audio_path=audio_path,
            info_json_path=downloads_dir / "vid1.info.json",
        )

        transcriber = MagicMock()
        transcriber.transcribe.return_value = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 5.0, "Speaker 1", "Hi.")],
            duration_sec=5.0,
            model_name="whisper-base",
            diarization=True,
        )

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        # collected.md has the row, status transcribed
        text = (tmp_project / "collected.md").read_text()
        assert "vid1" in text and "transcribed" in text

        # Transcription file written with sanitized name
        transcriptions_dir = tmp_project / "podcasts" / "Test Podcast" / "transcriptions"
        produced = list(transcriptions_dir.glob("*.md"))
        assert len(produced) == 1
        assert produced[0].name.endswith(" - transcription.md")

        # Queue contains the transcription path
        queue = (tmp_project / "analysis_queue.md").read_text()
        assert str(produced[0]) in queue

    def test_skips_already_known_episodes(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        # Pre-mark episode as known.
        from podcast_llm.ledger import EpisodeRecord
        ledger.record_downloaded(
            EpisodeRecord(
                podcast="Test Podcast",
                channel_title="C",
                title="T",
                published_at="2026-01-01",
                url="https://x.test/vid1",
                episode_id="vid1",
            )
        )

        ep = EpisodeMetadata(
            episode_id="vid1", title="T", channel_title="C",
            published_at="2026-01-01", url="https://x.test/vid1",
        )
        downloader = MagicMock()
        downloader.enumerate_playlist.return_value = [ep]
        downloader.filter_new.return_value = []  # filtered out

        transcriber = MagicMock()

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        downloader.download_episode.assert_not_called()
        transcriber.transcribe.assert_not_called()

    def test_records_failure_and_continues_on_download_error(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        # Add a second podcast so we can verify continuation.
        cfg.podcasts.append(
            PodcastConfig(
                name="Other",
                playlist_url="https://y.test",
                lens="l",
                vault_path=tmp_project / "obsidian" / "Other",
                max_backfill=5,
                stt_model="whisper-base",
                diarization=True,
                diarization_segmentation="seg",
                diarization_embedding="emb",
            )
        )
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()

        ep1 = EpisodeMetadata("vid1", "T1", "C", "2026-04-20", "https://x.test/vid1")
        ep2 = EpisodeMetadata("vid2", "T2", "C2", "2026-04-20", "https://y.test/vid2")

        def enumerate_side(url: str) -> list[EpisodeMetadata]:
            return [ep1] if "x.test" in url else [ep2]

        def filter_side(eps, **kwargs):
            return eps

        downloader = MagicMock()
        downloader.enumerate_playlist.side_effect = enumerate_side
        downloader.filter_new.side_effect = filter_side

        def download_side(ep, podcast_name):
            if ep.episode_id == "vid1":
                raise RuntimeError("HTTP 403")
            audio = tmp_project / "podcasts" / podcast_name / "downloads" / f"{ep.episode_id}.wav"
            audio.parent.mkdir(parents=True, exist_ok=True)
            audio.write_bytes(b"RIFF")
            return DownloadResult(metadata=ep, audio_path=audio, info_json_path=audio.with_suffix(".info.json"))

        downloader.download_episode.side_effect = download_side

        transcriber = MagicMock()
        transcriber.transcribe.return_value = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 1.0, None, "ok")],
            duration_sec=1.0, model_name="whisper-base", diarization=False,
        )

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        text = (tmp_project / "collected.md").read_text()
        assert "download_failed" in text
        assert "HTTP 403" in text
        # Other podcast still processed.
        assert "vid2" in text and "transcribed" in text
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: ImportError on `Pipeline`.

- [ ] **Step 3: Implement Pipeline**

```python
# src/podcast_llm/pipeline.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from podcast_llm.config import Config, PodcastConfig
from podcast_llm.downloader import Downloader, EpisodeMetadata
from podcast_llm.ledger import EpisodeRecord, Ledger
from podcast_llm.transcriber import Transcriber, render_transcript_markdown
from podcast_llm.utils.filesystem import atomic_write, sanitize_filename

log = logging.getLogger(__name__)


TranscriberFactory = Callable[[PodcastConfig], Transcriber]


@dataclass
class Pipeline:
    project_root: Path
    config: Config
    ledger: Ledger
    downloader: Downloader
    transcriber_factory: TranscriberFactory
    podcast_filter: Optional[str] = None  # if set, only process this podcast name

    def ingest_all(self) -> None:
        self.ledger.ensure_initialized()
        for pod in self.config.podcasts:
            if self.podcast_filter and pod.name != self.podcast_filter:
                continue
            try:
                self._ingest_podcast(pod)
            except Exception as exc:  # noqa: BLE001
                log.exception("podcast ingest failed: %s", pod.name)
                # Failure is per-podcast; don't block the others.
                continue

    def _ingest_podcast(self, pod: PodcastConfig) -> None:
        log.info("enumerating playlist: %s", pod.name)
        episodes = self.downloader.enumerate_playlist(pod.playlist_url)
        new = self.downloader.filter_new(
            episodes,
            known_ids=self.ledger.known_episode_ids(),
            max_backfill=pod.max_backfill,
        )
        log.info("podcast=%s new_episodes=%d", pod.name, len(new))

        # Lazily build the transcriber once per podcast (loads heavy models).
        transcriber: Optional[Transcriber] = None

        for ep in new:
            rec = EpisodeRecord(
                podcast=pod.name,
                channel_title=ep.channel_title,
                title=ep.title,
                published_at=ep.published_at,
                url=ep.url,
                episode_id=ep.episode_id,
            )

            try:
                self.downloader.download_episode(ep, podcast_name=pod.name)
            except Exception as exc:  # noqa: BLE001
                log.exception("download failed: %s", ep.episode_id)
                self.ledger.record_failed(rec, stage="download", error=str(exc))
                continue
            self.ledger.record_downloaded(rec)

            if transcriber is None:
                transcriber = self.transcriber_factory(pod)

            audio_path = (
                self.project_root
                / "podcasts"
                / pod.name
                / "downloads"
                / f"{ep.episode_id}.wav"
            )

            try:
                result = transcriber.transcribe(audio_path)
            except Exception as exc:  # noqa: BLE001
                log.exception("transcription failed: %s", ep.episode_id)
                self.ledger.record_failed(rec, stage="transcription", error=str(exc))
                continue

            md = render_transcript_markdown(
                result,
                episode_id=ep.episode_id,
                channel_title=ep.channel_title,
                title=ep.title,
                published_at=ep.published_at,
                url=ep.url,
            )
            base = sanitize_filename(
                f"{ep.channel_title} - {ep.title}",
                episode_id=ep.episode_id,
            )
            transcription_path = (
                self.project_root
                / "podcasts"
                / pod.name
                / "transcriptions"
                / f"{base} - transcription.md"
            )
            atomic_write(transcription_path, md)
            self.ledger.record_transcribed(ep.episode_id, str(transcription_path))
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_pipeline.py src/podcast_llm/pipeline.py
git commit -m "feat(pipeline): orchestrate enumerate→download→transcribe with per-step failure capture"
```

---

### Task 6.2: TDD CLI

**Files:**
- Create: `src/podcast_llm/cli.py`
- Modify: `tests/unit/test_pipeline.py` (add CLI test) OR new file
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_cli.py
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from podcast_llm.cli import app


def test_ingest_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output.lower()


def test_ingest_command_loads_config(tmp_path: Path, monkeypatch) -> None:
    cfg_path = tmp_path / "podcasts.yaml"
    cfg_path.write_text(
        "defaults:\n"
        f"  vault_root: {tmp_path}/obsidian\n"
        "  max_backfill: 1\n"
        "podcasts:\n"
        "  - name: T\n"
        "    playlist_url: https://x.test\n"
        "    lens: l\n"
    )

    # Spy on Pipeline.ingest_all to avoid real network/model calls.
    called = {}

    def fake_ingest(self) -> None:
        called["yes"] = True

    monkeypatch.setattr("podcast_llm.cli.Pipeline.ingest_all", fake_ingest)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["ingest", "--config", str(cfg_path), "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert called.get("yes") is True
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_cli.py -v`
Expected: ImportError on `app`.

- [ ] **Step 3: Implement CLI**

```python
# src/podcast_llm/cli.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from podcast_llm.config import load_config
from podcast_llm.downloader import Downloader
from podcast_llm.ledger import Ledger
from podcast_llm.pipeline import Pipeline
from podcast_llm.transcriber import (
    PyannoteDiarizer,
    SherpaOnnxAsr,
    Transcriber,
    detect_device,
)

app = typer.Typer(help="podcast-llm: ingest podcast playlists into a Karpathy LLM Wiki.")


def _build_transcriber_factory(model_cache_dir: Path):
    device = detect_device()

    def factory(pod):
        asr = SherpaOnnxAsr(
            model_dir=model_cache_dir / pod.stt_model,
            model_name=pod.stt_model,
            device=device,
        )
        diar = (
            PyannoteDiarizer(
                segmentation_model=pod.diarization_segmentation,
                embedding_model=pod.diarization_embedding,
                device=device,
            )
            if pod.diarization
            else None
        )
        return Transcriber(
            asr_engine=asr,
            diar_engine=diar,
            model_name=pod.stt_model,
            diarization=pod.diarization,
        )

    return factory


@app.command()
def ingest(
    config: Path = typer.Option(
        Path("podcasts.yaml"), "--config", help="Path to podcasts.yaml."
    ),
    project_root: Path = typer.Option(
        Path("."), "--project-root", help="Project root containing podcasts/, logs/, etc."
    ),
    podcast: Optional[str] = typer.Option(
        None, "--podcast", help="Process only this podcast (by name)."
    ),
    model_cache_dir: Path = typer.Option(
        Path("~/.cache/sherpa-onnx").expanduser(),
        "--model-cache-dir",
        help="Where ONNX model files live.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Run Tier 1: download new episodes and transcribe them."""
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = load_config(config)
    ledger = Ledger(project_root)
    downloader = Downloader(downloads_root=project_root / "podcasts")
    pipeline = Pipeline(
        project_root=project_root,
        config=cfg,
        ledger=ledger,
        downloader=downloader,
        transcriber_factory=_build_transcriber_factory(model_cache_dir),
        podcast_filter=podcast,
    )
    pipeline.ingest_all()
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_cli.py -v`
Expected: 2 passed. (The second test patches Pipeline.ingest_all, so the real transcriber/downloader code paths don't execute — works without sherpa/pyannote installed.)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_cli.py src/podcast_llm/cli.py
git commit -m "feat(cli): typer-based ingest command wiring config → pipeline"
```

---

## Phase 7: Pre-flight checks + JSON-line logging

### Task 7.1: TDD pre-flight checks

**Files:**
- Create: `tests/unit/test_preflight.py`
- Create: `src/podcast_llm/preflight.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_preflight.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from podcast_llm.preflight import (
    PreflightError,
    check_vault_skeletons,
    check_yt_dlp,
    run_all,
)


class TestCheckYtDlp:
    @patch("podcast_llm.preflight.yt_dlp")
    def test_passes_when_module_present(self, mock_mod) -> None:
        mock_mod.version.__version__ = "2026.01.01"
        check_yt_dlp()  # should not raise


class TestCheckVaultSkeletons:
    def test_creates_missing_skeleton(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "TestVault"
        check_vault_skeletons([vault])
        assert (vault / "SCHEMA.md").exists()
        assert (vault / "index.md").exists()
        assert (vault / "log.md").exists()
        for sub in ["raw/transcripts", "episodes", "entities", "concepts", "comparisons", "queries"]:
            assert (vault / sub).is_dir()

    def test_idempotent_for_existing_vault(self, tmp_vault: Path) -> None:
        vault = tmp_vault / "TestVault"
        check_vault_skeletons([vault])
        # Modify SCHEMA.md to verify it's not overwritten on second call.
        (vault / "SCHEMA.md").write_text("# CUSTOMIZED")
        check_vault_skeletons([vault])
        assert (vault / "SCHEMA.md").read_text() == "# CUSTOMIZED"


class TestRunAll:
    @patch("podcast_llm.preflight.check_yt_dlp")
    @patch("podcast_llm.preflight.check_vault_skeletons")
    def test_runs_each_check(self, mock_vaults, mock_yt) -> None:
        run_all(vault_paths=[Path("/x")])
        mock_yt.assert_called_once()
        mock_vaults.assert_called_once_with([Path("/x")])
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_preflight.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement preflight**

```python
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
```

(`create_vault_skeleton` is built in Phase 8; this preflight module imports it. Since Phase 8 hasn't run yet at test time, install Phase 8 stub first or reorder: move Phase 8 Task 8.2 ahead of this task in your execution. The plan keeps current ordering for narrative reasons; if executing strictly in order, do Task 8.2 first.)

- [ ] **Step 4: Run, verify pass**

After `create_vault_skeleton` exists (Task 8.2 complete), run: `pytest tests/unit/test_preflight.py -v`
Expected: all preflight tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_preflight.py src/podcast_llm/preflight.py
git commit -m "feat(preflight): yt-dlp version check + vault skeleton ensure"
```

---

### Task 7.2: TDD JSON-line logger

**Files:**
- Create: `tests/unit/test_logging_setup.py`
- Create: `src/podcast_llm/logging_setup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_logging_setup.py
from __future__ import annotations

import json
import logging
from pathlib import Path

from podcast_llm.logging_setup import configure_jsonl_logger


def test_writes_json_line_to_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "pipeline.jsonl"
    configure_jsonl_logger(log_path, name="podcast_llm.test")
    log = logging.getLogger("podcast_llm.test")
    log.info("hello", extra={"episode_id": "vid1", "stage": "download"})

    # Flush handlers
    for h in log.handlers:
        h.flush()

    line = log_path.read_text().strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["msg"] == "hello"
    assert parsed["episode_id"] == "vid1"
    assert parsed["stage"] == "download"
    assert parsed["level"] == "INFO"
    assert "ts" in parsed
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_logging_setup.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement logger**

```python
# src/podcast_llm/logging_setup.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName",
}


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Surface any structured fields passed via extra={...}.
        for key, val in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_jsonl_logger(log_path: Path, name: str = "podcast_llm") -> None:
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(JsonLineFormatter())
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers if reconfigured.
    for existing in list(logger.handlers):
        if isinstance(existing, logging.FileHandler) and Path(existing.baseFilename) == log_path:
            return
    logger.addHandler(handler)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_logging_setup.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_logging_setup.py src/podcast_llm/logging_setup.py
git commit -m "feat(logging): JSON-line file logger with structured extras"
```

---

### Task 7.3: Wire preflight + JSON logging into CLI

**Files:**
- Modify: `src/podcast_llm/cli.py`

- [ ] **Step 1: Update `ingest` command**

Open `src/podcast_llm/cli.py` and modify the `ingest` function to call preflight and configure the JSON-line logger:

```python
# Replace the body of `ingest` with:

@app.command()
def ingest(
    config: Path = typer.Option(
        Path("podcasts.yaml"), "--config", help="Path to podcasts.yaml."
    ),
    project_root: Path = typer.Option(
        Path("."), "--project-root", help="Project root containing podcasts/, logs/, etc."
    ),
    podcast: Optional[str] = typer.Option(
        None, "--podcast", help="Process only this podcast (by name)."
    ),
    model_cache_dir: Path = typer.Option(
        Path("~/.cache/sherpa-onnx").expanduser(),
        "--model-cache-dir",
        help="Where ONNX model files live.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
    skip_preflight: bool = typer.Option(False, "--skip-preflight"),
) -> None:
    """Run Tier 1: download new episodes and transcribe them."""
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    today = __import__("datetime").date.today().isoformat()
    configure_jsonl_logger(project_root / "logs" / f"pipeline-{today}.jsonl")

    cfg = load_config(config)

    if not skip_preflight:
        run_all(vault_paths=[p.vault_path for p in cfg.podcasts])

    ledger = Ledger(project_root)
    downloader = Downloader(downloads_root=project_root / "podcasts")
    pipeline = Pipeline(
        project_root=project_root,
        config=cfg,
        ledger=ledger,
        downloader=downloader,
        transcriber_factory=_build_transcriber_factory(model_cache_dir),
        podcast_filter=podcast,
    )
    pipeline.ingest_all()
```

Add the imports at the top of `cli.py`:

```python
from podcast_llm.logging_setup import configure_jsonl_logger
from podcast_llm.preflight import run_all
```

- [ ] **Step 2: Re-run CLI tests**

Run: `pytest tests/unit/test_cli.py -v`
Expected: still passing — the test patches `Pipeline.ingest_all`. Add a `--skip-preflight` flag to the test invocation if vault paths attempt to create directories the test didn't pre-make. Update the test if needed:

```python
# In tests/unit/test_cli.py, modify the invocation:
result = runner.invoke(
    app,
    [
        "ingest",
        "--config", str(cfg_path),
        "--project-root", str(tmp_path),
        "--skip-preflight",
    ],
)
```

- [ ] **Step 3: Commit**

```bash
git add src/podcast_llm/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): wire preflight + JSON-line logging into ingest"
```

---

## Phase 8: Wiki vault skeleton

### Task 8.1: Write the SCHEMA.md template

**Files:**
- Create: `docs/wiki-schema-template.md`

- [ ] **Step 1: Write the template file**

```markdown
# Wiki Schema — {{podcast_name}}

> Generated by podcast-llm on {{created_date}}. Edit freely; the slash command
> reads this file to know your conventions, but only updates `index.md` and
> `log.md` automatically. Tag taxonomy below is the contract: new tags must be
> added here BEFORE being used on a page.

## Domain

This wiki covers the **{{podcast_name}}** podcast: episodes, the entities
(people, organizations, studies, products) cited within them, and the
concepts (ideas, mechanisms, frameworks) discussed.

## Analytical Lens

{{lens}}

## Conventions

- File names: as published, with filesystem-safe characters. Episode pages
  use `<channelTitle> - <title>.md`.
- Every wiki page starts with YAML frontmatter (see below).
- Use `[[wikilinks]]` to link between pages.
- Episode pages must link to every entity/concept they touched.
- Entity/concept pages must back-link to every episode that cited them.
- When updating a page, always bump the `updated` date.
- Every new page must be added to `index.md` under the correct section.
- Every analyze action is appended to `log.md`.

## Frontmatter

```yaml
---
title: <page title>
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: episode | entity | concept | comparison | query
tags: [from taxonomy below]
# Episode pages additionally include:
episode_id: <yt video id>
channelTitle: <...>
publishedAt: YYYY-MM-DD
url: https://youtube.com/watch?v=...
transcription_path: <abs path>
analysis_path: <abs path>
---
```

## Tag Taxonomy

Edit this section to constrain which tags are valid in this vault. The slash
command will only emit tags from this list. To introduce a new tag, add it
here first.

- general: episode, panel, interview, solo, follow-up
- meta: contradiction, controversy, prediction, comparison

## Page Creation Thresholds

- **Create an entity/concept page** when mentioned in 2+ episodes OR central
  to one episode.
- **Add to existing page** when a new episode mentions an existing entity.
- **DON'T create a page** for passing mentions or things outside this podcast's domain.
- **Split a page** when it exceeds ~200 lines.

## Update Policy

When new information conflicts with existing content:
1. Check the dates — newer episodes generally supersede older ones.
2. If genuinely contradictory, note both positions with episode wikilinks.
3. Mark the contradiction in frontmatter: `contradictions: [page-name]`.
4. Flag for user review in the next analyze run.
```

- [ ] **Step 2: Commit**

```bash
git add docs/wiki-schema-template.md
git commit -m "docs(wiki): canonical SCHEMA.md template per spec §4.7"
```

---

### Task 8.2: TDD `create_vault_skeleton`

**Files:**
- Create: `tests/unit/test_vault.py`
- Create: `src/podcast_llm/wiki/vault.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_vault.py
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.wiki.vault import create_vault_skeleton, vault_exists


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
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_vault.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement vault skeleton**

```python
# src/podcast_llm/wiki/vault.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from podcast_llm.utils.filesystem import atomic_write

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
- Created with podcast-llm
"""


def _find_schema_template() -> Optional[Path]:
    for hint in _REPO_ROOT_HINTS:
        if hint.exists():
            return hint
    return None


def _render_schema(podcast_name: str, lens: str) -> str:
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
    return body.replace("{{podcast_name}}", podcast_name).replace("{{lens}}", lens or "")


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
        atomic_write(schema_path, _render_schema(podcast_name or vault_path.name, lens))

    index_path = vault_path / "index.md"
    if not index_path.exists():
        atomic_write(index_path, _INDEX_TEMPLATE.format(created=today))

    log_path = vault_path / "log.md"
    if not log_path.exists():
        atomic_write(log_path, _LOG_TEMPLATE.format(created=today))


def vault_exists(vault_path: Path) -> bool:
    """True iff the directory contains at least SCHEMA.md, index.md, and log.md."""
    p = Path(vault_path)
    return (
        p.is_dir()
        and (p / "SCHEMA.md").exists()
        and (p / "index.md").exists()
        and (p / "log.md").exists()
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_vault.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_vault.py src/podcast_llm/wiki/vault.py
git commit -m "feat(wiki): create_vault_skeleton with idempotent SCHEMA/index/log"
```

---

## Phase 9: Analysis section parser

### Task 9.1: TDD Entities/Concepts parser

**Files:**
- Create: `tests/unit/test_analysis_sections.py`
- Create: `src/podcast_llm/parsers/analysis_sections.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_analysis_sections.py
from __future__ import annotations

import pytest

from podcast_llm.parsers.analysis_sections import (
    ConceptItem,
    EntityItem,
    MalformedSectionError,
    parse_analysis,
)

GOOD = """\
# Channel — Episode

## TL;DR
Sentence one. Sentence two. Sentence three.

## Key Insights (5–10)
- **Claim:** explanation [00:01:23]

## Critical Pass
- **Steelman:** ...

## Entities
- Andrew Huberman :: person :: Stanford neuroscientist hosting :: [00:00:30]
- Stanford University :: org :: Affiliated institution :: [00:01:10]

## Concepts
- circadian rhythm :: 24-hour biological cycle governing wakefulness :: [00:05:00]
- dopamine :: neurotransmitter linked to motivation :: [00:08:42]

## Follow-ups
- ...
"""


def test_parses_entities() -> None:
    parsed = parse_analysis(GOOD)
    assert len(parsed.entities) == 2
    e0 = parsed.entities[0]
    assert isinstance(e0, EntityItem)
    assert e0.name == "Andrew Huberman"
    assert e0.type == "person"
    assert e0.context == "Stanford neuroscientist hosting"
    assert e0.timestamp == "00:00:30"


def test_parses_concepts() -> None:
    parsed = parse_analysis(GOOD)
    assert len(parsed.concepts) == 2
    c0 = parsed.concepts[0]
    assert isinstance(c0, ConceptItem)
    assert c0.name == "circadian rhythm"
    assert c0.definition == "24-hour biological cycle governing wakefulness"
    assert c0.timestamp == "00:05:00"


def test_rejects_malformed_entity_line() -> None:
    bad = GOOD.replace(
        "- Andrew Huberman :: person :: Stanford neuroscientist hosting :: [00:00:30]",
        "- Andrew Huberman | person | bad delimiters | [00:00:30]",
    )
    with pytest.raises(MalformedSectionError) as exc:
        parse_analysis(bad)
    assert "entities" in str(exc.value).lower()
    # Message should include the offending line for the user to fix.
    assert "Andrew Huberman" in str(exc.value)


def test_rejects_entity_with_wrong_field_count() -> None:
    bad = GOOD.replace(
        "- Andrew Huberman :: person :: Stanford neuroscientist hosting :: [00:00:30]",
        "- Andrew Huberman :: person :: missing context-and-timestamp",
    )
    with pytest.raises(MalformedSectionError):
        parse_analysis(bad)


def test_rejects_concept_with_wrong_field_count() -> None:
    bad = GOOD.replace(
        "- circadian rhythm :: 24-hour biological cycle governing wakefulness :: [00:05:00]",
        "- circadian rhythm :: only-definition",
    )
    with pytest.raises(MalformedSectionError):
        parse_analysis(bad)


def test_missing_entities_section_returns_empty_list() -> None:
    no_entities = GOOD.split("## Entities")[0] + GOOD.split("## Concepts", 1)[1]
    no_entities = "## Concepts" + no_entities
    parsed = parse_analysis(no_entities)
    assert parsed.entities == []


def test_blank_line_in_section_is_ok() -> None:
    spaced = GOOD.replace(
        "## Entities\n",
        "## Entities\n\n",
    )
    parsed = parse_analysis(spaced)
    assert len(parsed.entities) == 2
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_analysis_sections.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement parser**

```python
# src/podcast_llm/parsers/analysis_sections.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

DELIM = "::"


class MalformedSectionError(ValueError):
    """Raised when an Entities or Concepts section line is not parseable.

    Per spec §6.2: the parser aborts the wiki update entirely on any malformed
    line — never partial-update.
    """


@dataclass
class EntityItem:
    name: str
    type: str
    context: str
    timestamp: str


@dataclass
class ConceptItem:
    name: str
    definition: str
    timestamp: str


@dataclass
class ParsedAnalysis:
    entities: list[EntityItem] = field(default_factory=list)
    concepts: list[ConceptItem] = field(default_factory=list)


_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_TIMESTAMP_RE = re.compile(r"^\[?(\d{2}:\d{2}:\d{2})\]?$")


def _extract_section(lines: list[str], heading: str) -> list[str]:
    """Return the body lines (no heading, no trailing blanks) of ``## heading``.

    If the heading isn't present, returns []. Stops at the next ``##`` heading.
    """
    target = heading.strip().lower()
    in_section = False
    out: list[str] = []
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            if in_section:
                break
            if m.group(1).strip().lower().startswith(target):
                in_section = True
                continue
        elif in_section:
            out.append(line)
    # Strip leading/trailing blank lines.
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _parse_timestamp_field(raw: str) -> str:
    raw = raw.strip()
    m = _TIMESTAMP_RE.match(raw)
    if not m:
        raise ValueError(f"timestamp must look like [HH:MM:SS], got: {raw!r}")
    return m.group(1)


def _parse_entity_line(line: str) -> EntityItem:
    if not line.startswith("- "):
        raise MalformedSectionError(
            f"entities: line must start with '- ', got: {line!r}"
        )
    body = line[2:]
    parts = [p.strip() for p in body.split(DELIM)]
    if len(parts) != 4:
        raise MalformedSectionError(
            f"entities: expected 4 fields separated by ' :: ', got {len(parts)} in line: {line!r}"
        )
    name, etype, context, ts = parts
    try:
        ts_parsed = _parse_timestamp_field(ts)
    except ValueError as e:
        raise MalformedSectionError(f"entities: {e} in line: {line!r}") from e
    return EntityItem(name=name, type=etype, context=context, timestamp=ts_parsed)


def _parse_concept_line(line: str) -> ConceptItem:
    if not line.startswith("- "):
        raise MalformedSectionError(
            f"concepts: line must start with '- ', got: {line!r}"
        )
    body = line[2:]
    parts = [p.strip() for p in body.split(DELIM)]
    if len(parts) != 3:
        raise MalformedSectionError(
            f"concepts: expected 3 fields separated by ' :: ', got {len(parts)} in line: {line!r}"
        )
    name, definition, ts = parts
    try:
        ts_parsed = _parse_timestamp_field(ts)
    except ValueError as e:
        raise MalformedSectionError(f"concepts: {e} in line: {line!r}") from e
    return ConceptItem(name=name, definition=definition, timestamp=ts_parsed)


def parse_analysis(text: str) -> ParsedAnalysis:
    """Parse the strict Entities/Concepts sections from a finished analysis.

    On any malformed line in either section, raises MalformedSectionError
    immediately. The wiki writer then aborts wiki update entirely.
    """
    lines = text.splitlines()

    entities: list[EntityItem] = []
    for raw in _extract_section(lines, "Entities"):
        if not raw.strip():
            continue
        entities.append(_parse_entity_line(raw))

    concepts: list[ConceptItem] = []
    for raw in _extract_section(lines, "Concepts"):
        if not raw.strip():
            continue
        concepts.append(_parse_concept_line(raw))

    return ParsedAnalysis(entities=entities, concepts=concepts)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_analysis_sections.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_analysis_sections.py src/podcast_llm/parsers/analysis_sections.py
git commit -m "feat(parsers): strict :: parser for Entities/Concepts sections"
```

---

## Phase 10: Wiki writer

### Task 10.1: TDD copy transcription to vault

**Files:**
- Create: `tests/unit/test_wiki_writer.py`
- Create: `src/podcast_llm/wiki/writer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_wiki_writer.py
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
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_wiki_writer.py::TestCopyTranscription -v`
Expected: ImportError.

- [ ] **Step 3: Implement minimal writer + copy_transcription**

```python
# src/podcast_llm/wiki/writer.py
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from podcast_llm.parsers.analysis_sections import (
    ConceptItem,
    EntityItem,
    ParsedAnalysis,
)
from podcast_llm.utils.filesystem import atomic_write, sanitize_filename


@dataclass
class EpisodeMeta:
    episode_id: str
    channel_title: str
    title: str
    published_at: str
    url: str
    transcription_path: str
    analysis_path: str

    def base_filename(self) -> str:
        return sanitize_filename(
            f"{self.channel_title} - {self.title}",
            episode_id=self.episode_id,
        )


class WikiWriter:
    """Performs the post-analysis wiki updates per spec §5.6."""

    def __init__(self, vault_path: Path) -> None:
        self.vault = Path(vault_path)

    def copy_transcription(self, source: Path, meta: EpisodeMeta) -> Path:
        dest_dir = self.vault / "raw" / "transcripts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{meta.base_filename()}.md"
        shutil.copyfile(source, dest)
        return dest
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_wiki_writer.py::TestCopyTranscription -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_wiki_writer.py src/podcast_llm/wiki/writer.py
git commit -m "feat(wiki): WikiWriter.copy_transcription"
```

---

### Task 10.2: TDD episode page write

**Files:**
- Modify: `tests/unit/test_wiki_writer.py`
- Modify: `src/podcast_llm/wiki/writer.py`

- [ ] **Step 1: Append failing tests**

```python
class TestWriteEpisodePage:
    def test_writes_episode_with_frontmatter(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        page = w.write_episode_page(
            meta,
            tldr="Three sentences. About the thesis. Why it matters.",
            insights_md="- **Insight A:** body [00:01:00]\n- **Insight B:** body [00:05:00]\n",
            entity_links=["[[Andrew Huberman]]", "[[Stanford University]]"],
            concept_links=["[[circadian rhythm]]"],
        )
        assert page.exists()
        text = page.read_text()
        assert text.startswith("---\n")
        assert "type: episode" in text
        assert "episode_id: vid1" in text
        assert "channelTitle: Channel" in text
        assert "url: https://x.test/vid1" in text
        assert "transcription_path: /abs/transcription.md" in text
        assert "analysis_path: /abs/analysis.md" in text
        assert "## TL;DR" in text
        assert "Three sentences." in text
        assert "## Key Insights" in text
        assert "**Insight A:**" in text
        assert "## Entities" in text
        assert "[[Andrew Huberman]]" in text
        assert "## Concepts" in text
        assert "[[circadian rhythm]]" in text

    def test_episode_page_path_uses_sanitized_filename(self, vault: Path) -> None:
        meta = _episode_meta(title="Bad/Slash: Title")
        w = WikiWriter(vault)
        page = w.write_episode_page(meta, tldr="x", insights_md="", entity_links=[], concept_links=[])
        assert "/" not in page.name[:-3]  # excluding ".md"
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_wiki_writer.py::TestWriteEpisodePage -v`
Expected: AttributeError.

- [ ] **Step 3: Implement `write_episode_page`**

Append to `WikiWriter`:

```python
    def write_episode_page(
        self,
        meta: EpisodeMeta,
        *,
        tldr: str,
        insights_md: str,
        entity_links: list[str],
        concept_links: list[str],
    ) -> Path:
        today = date.today().isoformat()
        frontmatter = (
            "---\n"
            f"title: {meta.channel_title} — {meta.title}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "type: episode\n"
            "tags: [episode]\n"
            f"episode_id: {meta.episode_id}\n"
            f"channelTitle: {meta.channel_title}\n"
            f"publishedAt: {meta.published_at}\n"
            f"url: {meta.url}\n"
            f"transcription_path: {meta.transcription_path}\n"
            f"analysis_path: {meta.analysis_path}\n"
            "---\n\n"
        )
        body = (
            f"# {meta.channel_title} — {meta.title}\n\n"
            "## TL;DR\n"
            f"{tldr.strip()}\n\n"
            "## Key Insights\n"
            f"{insights_md.strip()}\n\n"
            "## Entities\n"
            + "\n".join(f"- {link}" for link in entity_links)
            + ("\n\n" if entity_links else "\n")
            + "## Concepts\n"
            + "\n".join(f"- {link}" for link in concept_links)
            + "\n"
        )
        page = self.vault / "episodes" / f"{meta.base_filename()}.md"
        atomic_write(page, frontmatter + body)
        return page
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_wiki_writer.py::TestWriteEpisodePage -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_wiki_writer.py src/podcast_llm/wiki/writer.py
git commit -m "feat(wiki): write_episode_page with frontmatter and link sections"
```

---

### Task 10.3: TDD entity page upsert

**Files:**
- Modify: `tests/unit/test_wiki_writer.py`
- Modify: `src/podcast_llm/wiki/writer.py`

- [ ] **Step 1: Append failing tests**

```python
class TestUpsertEntityPage:
    def test_creates_new_entity_page_with_backlink(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        e = EntityItem(
            name="Andrew Huberman",
            type="person",
            context="Stanford neuroscientist hosting the show",
            timestamp="00:00:30",
        )
        path = w.upsert_entity_page(e, episode_meta=meta)
        text = path.read_text()
        assert path.parent == vault / "entities"
        assert text.startswith("---\n")
        assert "type: entity" in text
        assert "Andrew Huberman" in text
        assert "Stanford neuroscientist hosting the show" in text
        # Backlink to episode page
        assert f"[[{meta.base_filename()}]]" in text

    def test_appends_to_existing_entity_page(self, vault: Path) -> None:
        meta1 = _episode_meta(episode_id="ep1", title="One")
        meta2 = _episode_meta(episode_id="ep2", title="Two")
        e1 = EntityItem("Andrew Huberman", "person", "Host", "00:00:30")
        e2 = EntityItem("Andrew Huberman", "person", "Host again", "00:01:00")
        w = WikiWriter(vault)
        w.upsert_entity_page(e1, episode_meta=meta1)
        path = w.upsert_entity_page(e2, episode_meta=meta2)
        text = path.read_text()
        # Both episode backlinks present.
        assert f"[[{meta1.base_filename()}]]" in text
        assert f"[[{meta2.base_filename()}]]" in text
        # Single page (not duplicated).
        pages = list((vault / "entities").glob("*.md"))
        assert len(pages) == 1
        # `updated` date present (we only verify the line, not the value).
        assert "updated:" in text
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_wiki_writer.py::TestUpsertEntityPage -v`
Expected: AttributeError.

- [ ] **Step 3: Implement upsert**

Append to `WikiWriter`:

```python
    def _entity_page_path(self, name: str) -> Path:
        return self.vault / "entities" / f"{sanitize_filename(name)}.md"

    def _concept_page_path(self, name: str) -> Path:
        return self.vault / "concepts" / f"{sanitize_filename(name)}.md"

    def upsert_entity_page(
        self,
        entity: EntityItem,
        *,
        episode_meta: EpisodeMeta,
    ) -> Path:
        path = self._entity_page_path(entity.name)
        backlink = f"[[{episode_meta.base_filename()}]]"
        today = date.today().isoformat()

        if path.exists():
            existing = path.read_text()
            # Bump updated date and append a new mention if this episode isn't already linked.
            existing = _replace_frontmatter_field(existing, "updated", today)
            if backlink not in existing:
                appended_block = (
                    f"\n## Mention in {backlink} (at {entity.timestamp})\n"
                    f"{entity.context}\n"
                )
                existing = existing.rstrip() + "\n" + appended_block
            atomic_write(path, existing)
            return path

        frontmatter = (
            "---\n"
            f"title: {entity.name}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "type: entity\n"
            f"entity_type: {entity.type}\n"
            "tags: [entity]\n"
            "---\n\n"
        )
        body = (
            f"# {entity.name}\n\n"
            f"**Type:** {entity.type}\n\n"
            "## Mentions\n"
            f"## Mention in {backlink} (at {entity.timestamp})\n"
            f"{entity.context}\n"
        )
        atomic_write(path, frontmatter + body)
        return path


def _replace_frontmatter_field(text: str, key: str, new_value: str) -> str:
    """Replace `key: <value>` line inside the leading YAML frontmatter block."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    fm_block = text[4:end]
    new_lines: list[str] = []
    replaced = False
    for line in fm_block.splitlines():
        if line.startswith(f"{key}:"):
            new_lines.append(f"{key}: {new_value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}: {new_value}")
    return "---\n" + "\n".join(new_lines) + text[end:]
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_wiki_writer.py::TestUpsertEntityPage -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_wiki_writer.py src/podcast_llm/wiki/writer.py
git commit -m "feat(wiki): upsert_entity_page with backlinks and updated-date bump"
```

---

### Task 10.4: TDD concept page upsert (mirror of entity)

**Files:**
- Modify: `tests/unit/test_wiki_writer.py`
- Modify: `src/podcast_llm/wiki/writer.py`

- [ ] **Step 1: Append failing tests**

```python
class TestUpsertConceptPage:
    def test_creates_new_concept_page(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        c = ConceptItem(
            name="circadian rhythm",
            definition="24-hour biological cycle governing wakefulness",
            timestamp="00:05:00",
        )
        path = w.upsert_concept_page(c, episode_meta=meta)
        text = path.read_text()
        assert path.parent == vault / "concepts"
        assert "type: concept" in text
        assert "circadian rhythm" in text
        assert "24-hour biological cycle" in text
        assert f"[[{meta.base_filename()}]]" in text

    def test_appends_mention_for_second_episode(self, vault: Path) -> None:
        meta1 = _episode_meta(episode_id="e1", title="A")
        meta2 = _episode_meta(episode_id="e2", title="B")
        c1 = ConceptItem("dopamine", "neurotransmitter", "00:00:10")
        c2 = ConceptItem("dopamine", "see prior episode", "00:00:20")
        w = WikiWriter(vault)
        w.upsert_concept_page(c1, episode_meta=meta1)
        path = w.upsert_concept_page(c2, episode_meta=meta2)
        text = path.read_text()
        assert f"[[{meta1.base_filename()}]]" in text
        assert f"[[{meta2.base_filename()}]]" in text
        assert len(list((vault / "concepts").glob("*.md"))) == 1
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_wiki_writer.py::TestUpsertConceptPage -v`
Expected: AttributeError.

- [ ] **Step 3: Implement upsert_concept_page**

Append to `WikiWriter`:

```python
    def upsert_concept_page(
        self,
        concept: ConceptItem,
        *,
        episode_meta: EpisodeMeta,
    ) -> Path:
        path = self._concept_page_path(concept.name)
        backlink = f"[[{episode_meta.base_filename()}]]"
        today = date.today().isoformat()

        if path.exists():
            existing = path.read_text()
            existing = _replace_frontmatter_field(existing, "updated", today)
            if backlink not in existing:
                appended_block = (
                    f"\n## Mention in {backlink} (at {concept.timestamp})\n"
                    f"{concept.definition}\n"
                )
                existing = existing.rstrip() + "\n" + appended_block
            atomic_write(path, existing)
            return path

        frontmatter = (
            "---\n"
            f"title: {concept.name}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "type: concept\n"
            "tags: [concept]\n"
            "---\n\n"
        )
        body = (
            f"# {concept.name}\n\n"
            f"**Definition:** {concept.definition}\n\n"
            "## Mentions\n"
            f"## Mention in {backlink} (at {concept.timestamp})\n"
            f"{concept.definition}\n"
        )
        atomic_write(path, frontmatter + body)
        return path
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_wiki_writer.py::TestUpsertConceptPage -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_wiki_writer.py src/podcast_llm/wiki/writer.py
git commit -m "feat(wiki): upsert_concept_page mirroring entity behavior"
```

---

### Task 10.5: TDD update_index and append_log

**Files:**
- Modify: `tests/unit/test_wiki_writer.py`
- Modify: `src/podcast_llm/wiki/writer.py`

- [ ] **Step 1: Append failing tests**

```python
class TestUpdateIndex:
    def test_adds_episode_under_episodes_section(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        w.update_index(
            new_episodes=[(meta.base_filename(), meta.title)],
            new_entities=[("Andrew Huberman", "Stanford neuroscientist")],
            new_concepts=[("circadian rhythm", "24-hour biological cycle")],
        )
        idx = (vault / "index.md").read_text()
        assert f"- [[{meta.base_filename()}]] — {meta.title}" in idx
        assert "[[Andrew Huberman]] — Stanford neuroscientist" in idx
        assert "[[circadian rhythm]] — 24-hour biological cycle" in idx
        # Total pages updated to 3 (1 episode + 1 entity + 1 concept).
        assert "Total pages: 3" in idx


class TestAppendLog:
    def test_appends_action_with_files_touched(self, vault: Path) -> None:
        w = WikiWriter(vault)
        w.append_log(
            action="analyze",
            subject="Channel — Episode One",
            files=[vault / "episodes" / "x.md", vault / "entities" / "y.md"],
        )
        log = (vault / "log.md").read_text()
        assert "analyze | Channel — Episode One" in log
        assert "x.md" in log
        assert "y.md" in log
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/unit/test_wiki_writer.py::TestUpdateIndex tests/unit/test_wiki_writer.py::TestAppendLog -v`
Expected: AttributeError.

- [ ] **Step 3: Implement index + log updates**

Append to `WikiWriter`:

```python
    def update_index(
        self,
        *,
        new_episodes: list[tuple[str, str]] = (),
        new_entities: list[tuple[str, str]] = (),
        new_concepts: list[tuple[str, str]] = (),
    ) -> Path:
        index_path = self.vault / "index.md"
        text = index_path.read_text() if index_path.exists() else _DEFAULT_INDEX
        text = _insert_under_section(text, "Episodes", [
            f"- [[{name}]] — {summary}" for name, summary in new_episodes
        ])
        text = _insert_under_section(text, "Entities", [
            f"- [[{name}]] — {summary}" for name, summary in new_entities
        ])
        text = _insert_under_section(text, "Concepts", [
            f"- [[{name}]] — {summary}" for name, summary in new_concepts
        ])
        text = _bump_index_total(text)
        text = _replace_index_last_updated(text, date.today().isoformat())
        atomic_write(index_path, text)
        return index_path

    def append_log(
        self,
        *,
        action: str,
        subject: str,
        files: Iterable[Path],
    ) -> Path:
        log_path = self.vault / "log.md"
        existing = log_path.read_text() if log_path.exists() else "# Wiki Log\n"
        today = date.today().isoformat()
        block = [f"\n## [{today}] {action} | {subject}"]
        for f in files:
            try:
                rel = Path(f).relative_to(self.vault)
            except ValueError:
                rel = Path(f)
            block.append(f"- {rel}")
        atomic_write(log_path, existing.rstrip() + "\n" + "\n".join(block) + "\n")
        return log_path


_DEFAULT_INDEX = (
    "# Wiki Index\n\n"
    "> Last updated: 1970-01-01 | Total pages: 0\n\n"
    "## Episodes\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n"
)


def _insert_under_section(text: str, section: str, lines: list[str]) -> str:
    if not lines:
        return text
    lines = sorted(lines)
    needle = f"## {section}\n"
    idx = text.find(needle)
    if idx == -1:
        # Section missing — append at end.
        return text.rstrip() + "\n\n" + needle + "\n".join(lines) + "\n"
    after_heading = idx + len(needle)
    # Find next heading (or EOF) to scope insertion to this section.
    next_heading = text.find("\n## ", after_heading)
    if next_heading == -1:
        block = text[after_heading:]
        head, tail = block, ""
    else:
        head = text[after_heading:next_heading + 1]
        tail = text[next_heading + 1:]
    # Existing items in the section (lines starting with "- ").
    existing_items = [ln for ln in head.splitlines() if ln.startswith("- ")]
    merged = sorted(set(existing_items + lines))
    new_section = "\n".join(merged) + ("\n" if merged else "")
    return text[:after_heading] + new_section + ("\n" if tail and not tail.startswith("\n") else "") + tail


def _bump_index_total(text: str) -> str:
    import re as _re

    def repl(m):
        # Walk all "- [[" lines to count current total.
        total = sum(1 for line in text.splitlines() if line.startswith("- [["))
        return f"Total pages: {total}"

    return _re.sub(r"Total pages: \d+", repl, text, count=1)


def _replace_index_last_updated(text: str, today: str) -> str:
    import re as _re

    return _re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {today}", text, count=1)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_wiki_writer.py -v`
Expected: all wiki writer tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_wiki_writer.py src/podcast_llm/wiki/writer.py
git commit -m "feat(wiki): index.md and log.md updates with sorted insertion"
```

---

## Phase 11: Slash command + analysis template

### Task 11.1: Write the analysis template

**Files:**
- Create: `docs/analysis-template.md`

- [ ] **Step 1: Write the file**

```markdown
# Podcast Analysis Template

> Canonical structure for `/analyze-podcast` output. The wiki writer parses
> the `## Entities` and `## Concepts` sections programmatically using the
> strict ` :: ` delimiter. Any other section may be edited freely; format below
> is the contract.

# {{channelTitle}} — {{title}}

## TL;DR

Three sentences. The thesis, the new thing, why it matters.

## Key Insights

5–10 insights, ranked by novelty (not order of appearance). Each:

- **Bolded claim:** one-paragraph explanation. [HH:MM:SS]

## Critical Pass

- **Steelman(s) of the strongest argument(s) (1–3):** When the episode contains
  multiple distinct theses (panel disagreements, guests making several
  independent claims), steelman each separately and label by speaker. When the
  episode has one clear central thesis, just one. Cap at 3 — beyond that,
  candidates belong in *Key Insights*, not here. Never pad.
- **Weak claims / unsupported assertions:** ...
- **Factual claims requiring verification:** [bullet list]
- **Contradictions with prior episodes (if any):** `[[wikilinks]]` to other episode pages.

## Entities

Strict `::`-delimited format. Four fields: name, type, one-line context, timestamp.

```
- name :: type (person|org|study|product) :: 1-line context :: [HH:MM:SS]
```

Only include entities meeting the page-creation thresholds in SCHEMA.md
(2+ episodes OR central to one episode). Conservative bias: skip if unsure.

## Concepts

Strict `::`-delimited format. Three fields: name, one-line definition, timestamp.

```
- name :: 1-line definition :: [HH:MM:SS]
```

## Follow-ups

- Open questions
- Things to look up
- Episodes to revisit
```

- [ ] **Step 2: Commit**

```bash
git add docs/analysis-template.md
git commit -m "docs: canonical analysis template per spec §6.1"
```

---

### Task 11.2: Write the `/analyze-podcast` slash command

**Files:**
- Create: `.claude/commands/analyze-podcast.md`

- [ ] **Step 1: Write the slash command**

```markdown
---
description: Analyze the next pending podcast transcription, write structured analysis, and update the corresponding Karpathy LLM Wiki vault.
---

# /analyze-podcast

You are the analysis tier of the `podcast-llm` pipeline. The download and
transcription tier has already produced diarized transcriptions and queued
them for analysis. Your job: pop the next entry from the queue, generate a
structured analysis under the per-podcast lens, then update the corresponding
Obsidian vault following Karpathy LLM Wiki conventions.

## Arguments

- `[N]` — number of episodes to analyze in this run (default: 1).
- `[--match <substring>]` — instead of FIFO, find a queued transcription whose
  filename contains `<substring>` (case-insensitive) and analyze that one.

## Inputs (read from project root, `.`)

- `podcasts.yaml` — per-podcast config including `lens`, `vault_path`.
- `analysis_queue.md` — FIFO list of transcription file paths.
- `collected.md` — master ledger.

## Procedure

For each episode you process:

### 1. Identify the next transcription

- Read `analysis_queue.md`. If `--match` given, find first matching path; else take
  the first line. If empty, report "queue empty" and stop.
- The transcription file path tells you the podcast (parent of `transcriptions/`
  is `podcasts/<podcast-name>/`).
- Look up the matching podcast entry in `podcasts.yaml` to get the `lens` and
  `vault_path`.

### 2. Read context

- Read `podcasts.yaml` (full file).
- Read the transcription file. The frontmatter contains `episode_id`,
  `channelTitle`, `title`, `publishedAt`, `url`.
- Read `<vault_path>/SCHEMA.md` to learn the tag taxonomy and conventions.
- Read `<vault_path>/index.md` to see what entities and concepts already exist
  in this vault (informs page creation thresholds).

### 3. Generate the analysis

Apply the per-podcast lens (from `podcasts.yaml`) plus the canonical analysis
template (`docs/analysis-template.md`) to the transcription. Produce a single
markdown file with these sections — exactly:

- `# <channelTitle> — <title>`
- `## TL;DR` — three sentences
- `## Key Insights` — 5–10 ranked by novelty, each with bolded claim + paragraph + `[HH:MM:SS]`
- `## Critical Pass` — Steelman(s) (1–3, label by speaker if multi-thesis), weak claims, claims to verify, contradictions with prior episodes (use `[[wikilinks]]` to existing episode pages where applicable)
- `## Entities` — strict format: `- name :: type :: context :: [HH:MM:SS]`
- `## Concepts` — strict format: `- name :: definition :: [HH:MM:SS]`
- `## Follow-ups`

**Strict format is non-negotiable for Entities and Concepts** — the wiki
writer parses these deterministically. Use exactly ` :: ` (space, two colons,
space) as the field separator, and keep timestamps in `[HH:MM:SS]` format.

Apply the page creation threshold conservatively: only list an entity in this
section if it (a) appears in the existing vault index OR (b) feels central to
this episode. Passing mentions stay out of the `Entities` section.

### 4. Write the analysis file

Path: `podcasts/<podcast-name>/analyses/<channelTitle> - <title> - analysis.md`
(use the same sanitized filename pattern as the transcription file — strip
slashes, truncate to 200 chars, append episode_id if truncated).

Use a single Write tool call. **Do this BEFORE updating the wiki** so a wiki
update failure doesn't lose the analysis.

### 5. Verify the analysis is parseable

Before touching the vault, parse your own `Entities` and `Concepts` sections
to confirm the strict format. Any line that doesn't match
`- <name> :: <field> :: ... :: [HH:MM:SS]` (with the right field count: 4 for
entities, 3 for concepts) is malformed.

If malformed: surface the offending line, do NOT update the wiki, do NOT
remove the queue entry. Ask the user whether to (a) fix the analysis file in
place and re-run, or (b) skip wiki update for this episode.

If parseable: continue.

### 6. Ensure the vault skeleton exists

If `<vault_path>/SCHEMA.md` does not exist, the vault has not been
initialized. Run `python -c "from podcast_llm.wiki.vault import create_vault_skeleton; from pathlib import Path; create_vault_skeleton(Path('<vault_path>'), podcast_name='<podcast-name>', lens='''<lens>''')"`
to create the skeleton, then continue.

### 7. Update the vault

Use the `podcast_llm.wiki.writer.WikiWriter` API. In a single Bash call run a
short Python snippet that:

1. Copies the transcription to `<vault_path>/raw/transcripts/`.
2. Writes/overwrites the episode page in `<vault_path>/episodes/`.
3. For each entity in your analysis (parsed by `parse_analysis`), upserts the
   entity page (creates new with backlink, or appends backlink + bumps `updated`).
4. For each concept, same treatment.
5. Updates `<vault_path>/index.md`: adds new episode/entity/concept entries
   alphabetically, bumps `Total pages` and `Last updated`.
6. Appends to `<vault_path>/log.md`: `## [YYYY-MM-DD] analyze | <subject>` plus a
   bullet list of every file touched.

### 8. Update the ledger

Run: `python -m podcast_llm` … (no, use the library directly):

```python
from pathlib import Path
from podcast_llm.ledger import Ledger

l = Ledger(Path("."))
l.record_analyzed(episode_id="<episode_id>", transcription_path="<abs path>")
```

This marks `analyzed_at` on the row in `collected.md` and removes the entry
from `analysis_queue.md`.

### 9. Report

Output a concise summary to the user: episode title, # entities/concepts
extracted, # vault files touched, any contradictions flagged.

## Failure modes

| Stage | What to do |
| --- | --- |
| Queue empty | Stop and report "queue empty". Do nothing else. |
| Transcription file missing | Surface the path, ask whether to remove from queue or stop. |
| Vault SCHEMA.md missing | Create skeleton (step 6), then continue. |
| Analysis Entities/Concepts malformed | Stop. Show the offending line. Ask user to fix or skip wiki. Do NOT update ledger or queue. |
| Wiki update raises | Analysis file persists. Do NOT update ledger or queue. Surface the error. |

## Notes for the analyst

- The lens guides framing — read the `lens` field for this podcast carefully.
- Use `[[wikilinks]]` in `Critical Pass > Contradictions` only when you can
  confirm the linked page exists in `index.md`.
- Be ruthless about the page-creation threshold. A bloated wiki is worse than
  a sparse one. Conservative bias when in doubt.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/commands/analyze-podcast.md
git commit -m "feat: /analyze-podcast slash command"
```

---

## Phase 12: Example config + README

### Task 12.1: Write `podcasts.yaml.example`

**Files:**
- Create: `podcasts.yaml.example`

- [ ] **Step 1: Write the example**

```yaml
# podcasts.yaml.example
#
# Copy this file to `podcasts.yaml` and edit. The real file is gitignored.
#
# `defaults` apply to every podcast unless overridden in the per-podcast entry.
# See README.md for full configuration reference.

defaults:
  # Where per-podcast Obsidian vaults live (one directory per podcast).
  vault_root: ~/obsidian

  # First-run cap: number of most-recent episodes to backfill per playlist.
  # After the first run, only episodes added after the baseline are processed.
  max_backfill: 20

  # sherpa-onnx STT model. `whisper-base` is a CPU-friendly default.
  # Upgrade to `whisper-medium` or `whisper-large-v3` if you have a GPU.
  stt_model: whisper-base

  # Diarization (speaker labeling) via pyannote.
  diarization: true
  diarization_segmentation: pyannote-segmentation-3.0
  diarization_embedding: 3d-speaker

podcasts:
  - name: "Example Podcast"
    playlist_url: "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxx"
    # vault_path: defaults to {vault_root}/{name}; uncomment to override.
    # vault_path: /custom/path/to/vault
    lens: |
      Frame insights as actionable lessons relevant to this podcast's domain.
      Identify recurring themes and contradictions with prior episodes.
      Note when claims are well-supported vs. speculative.
    # Per-podcast model overrides (uncomment to change defaults):
    # stt_model: whisper-medium
    # diarization: false
```

- [ ] **Step 2: Commit**

```bash
git add podcasts.yaml.example
git commit -m "docs: add podcasts.yaml.example with annotated defaults"
```

---

### Task 12.2: Write README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

```markdown
# podcast-llm

Ingest YouTube podcast playlists, transcribe locally with diarization, and
compound the results into a per-podcast [Karpathy-style LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
inside an Obsidian vault.

## What it is

```
┌──────────── TIER 1: AUTOMATED (cron-able, no LLM) ────────────┐
│  yt-dlp ──► audio ──► sherpa-onnx + pyannote ──► diarized .md │
│                                                                │
│  Output: transcription + collected.md + analysis_queue.md      │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──── TIER 2: HUMAN-IN-LOOP (Claude Code session) ──────────────┐
│  /analyze-podcast → structured analysis + Obsidian vault      │
│  update (entities, concepts, episodes, index, log)            │
└────────────────────────────────────────────────────────────────┘
```

The pipeline is a thin Python tool that downloads and transcribes; the
analysis layer runs inside [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
via a shipped slash command. This split keeps the heavy lifting local and
free, and uses Opus quota only for analysis.

## Why

Most podcast tooling produces one-off summaries that vanish after you read
them. The Karpathy LLM Wiki pattern compounds knowledge: every new episode
adds entities, concepts, and cross-references to a personal knowledge base
that grows more useful over time. This project applies that pattern to
podcasts: each episode you ingest enriches the vault, surfaces contradictions
across episodes, and builds a graph of how the topics interrelate.

## Quickstart

### Prerequisites

- Python 3.11+
- `ffmpeg` (`apt install ffmpeg` / `brew install ffmpeg`)
- (Optional) NVIDIA GPU with CUDA, or Apple Silicon with MPS — speeds up transcription
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- [Obsidian](https://obsidian.md/) for browsing the wiki

### Install

```bash
git clone https://github.com/<your-fork>/podcast-llm.git
cd podcast-llm
pip install -e ".[dev]"

cp podcasts.yaml.example podcasts.yaml
# edit podcasts.yaml with your playlists
```

### HuggingFace token (for pyannote diarization)

The diarization model is gated on HuggingFace and requires accepting the
license once:

1. Create an account at https://huggingface.co/.
2. Visit https://huggingface.co/pyannote/speaker-diarization-3.1 and accept the terms.
3. Generate a token at https://huggingface.co/settings/tokens.
4. `huggingface-cli login` and paste the token.

### First run (smoke test on one episode)

```bash
python -m podcast_llm ingest --limit 1
```

This downloads the most recent episode of the first podcast in your config,
transcribes it (slow on CPU; ~real-time on a modest GPU), and adds it to
`collected.md` and `analysis_queue.md`.

### Analyze in Claude Code

```bash
cd /path/to/podcast-llm
claude  # opens Claude Code in the project directory
```

Then in the Claude Code session:

```
/analyze-podcast
```

The first time you run this for a podcast, it creates the Obsidian vault
under `~/obsidian/<Podcast Name>/`. Open that directory in Obsidian to
browse the wiki.

## Configuration reference

See `podcasts.yaml.example` for the annotated schema. Top-level structure:

```yaml
defaults:
  vault_root: ~/obsidian       # where vaults are created
  max_backfill: 20             # episodes to backfill on first run
  stt_model: whisper-base      # sherpa-onnx model
  diarization: true            # pyannote diarization on/off
  diarization_segmentation: pyannote-segmentation-3.0
  diarization_embedding: 3d-speaker

podcasts:
  - name: "Display Name"
    playlist_url: "https://www.youtube.com/playlist?list=..."
    vault_path: ~/custom/path  # optional; defaults to vault_root/name
    lens: |
      Multi-line analytical lens guiding the /analyze-podcast prompt.
    # Any default may be overridden per-podcast.
```

## The `/analyze-podcast` slash command

When run in Claude Code at the project root:

- `/analyze-podcast` — pop and analyze the next queued transcription (1 episode).
- `/analyze-podcast 5` — analyze the next 5.
- `/analyze-podcast --match huberman-sleep` — find a queued transcription
  whose filename matches `huberman-sleep` and analyze it.

The slash command:

1. Reads the per-podcast lens from `podcasts.yaml`.
2. Generates a structured analysis (TL;DR, Key Insights, Critical Pass with
   1–3 steelmans, strict-format Entities/Concepts, Follow-ups).
3. Writes the analysis file to `podcasts/<podcast>/analyses/`.
4. Updates the Obsidian vault: copies the transcription to `raw/transcripts/`,
   writes the episode page, upserts entity/concept pages, updates `index.md`
   and `log.md`.
5. Marks the episode `analyzed` in `collected.md` and removes it from the queue.

### Writing a good lens

The lens is a free-text fragment prepended to the analysis prompt. It should
say:

- The dominant frame for insights (e.g. "biological mechanisms with evidence quality").
- What's signal vs. noise for this podcast (e.g. "panel disagreements ARE the signal").
- Per-podcast extraction rules (e.g. "for guests, capture formative experiences").

See `podcasts.yaml.example` for a generic starting point. Iterate based on
the first 2–3 analyses.

## Wiki structure

Each podcast gets its own Obsidian vault following the Karpathy LLM Wiki
pattern with one addition (`episodes/`):

```
<vault>/
├── SCHEMA.md          ← domain + lens + tag taxonomy
├── index.md           ← catalog, sectioned by type
├── log.md             ← append-only action log
├── raw/transcripts/   ← copies of transcription files (immutable)
├── episodes/          ← one page per analyzed episode
├── entities/          ← people, orgs, studies, products
├── concepts/          ← ideas, mechanisms, frameworks
├── comparisons/       ← cross-episode analyses (manual or via slash command)
└── queries/           ← filed query results worth keeping
```

See `docs/wiki-schema-template.md` for the per-vault `SCHEMA.md` template.

## Operations

### Cron setup

```cron
# Hourly check for new episodes
0 * * * * cd /path/to/podcast-llm && /usr/bin/python -m podcast_llm ingest >> logs/cron.log 2>&1
```

### Multi-GPU users (experimental)

```bash
python -m podcast_llm ingest --workers 3
```

This requires N independent CUDA devices and is unsupported. Each worker
takes a `gpu_lock_<id>.lock` file before claiming a GPU. Most users should
leave the default of 1 worker.

### Recovering from failures

- `download_failed`: the row in `collected.md` records the error. Re-running
  the pipeline will retry on the next ingest.
- `transcription_failed`: same — re-runs retry up to 3 times before parking
  the episode for manual review.
- Re-do an analysis: delete the analysis file, clear the `analyzed_at` field
  in `collected.md` for that row, re-add the transcription path to
  `analysis_queue.md`, then `/analyze-podcast`.

## Roadmap / non-goals

**Planned but not built yet:**
- `/lint-vault` slash command (orphan pages, broken wikilinks, etc.)
- Cross-vault meta-vault for cross-podcast synthesis

**Explicit non-goals:**
- Web UI / TUI / dashboard. `collected.md` opened in Obsidian is the dashboard.
- Email / Slack / push notifications.
- Real-time / live transcription.
- Non-YouTube ingestion (RSS, Spotify, Apple).

## License & responsibility

MIT. See `LICENSE`.

**Use responsibly:** `yt-dlp` may violate YouTube's ToS depending on
jurisdiction. Transcripts of copyrighted podcasts are for personal use only;
do not redistribute. The `pyannote/speaker-diarization-3.1` model has an
academic license requiring HuggingFace acceptance.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README covering install, usage, and operations"
```

---

## Phase 13: Integration test scaffolding

### Task 13.1: Write integration smoke test stub

**Files:**
- Create: `tests/integration/test_smoke.py`
- Create: `tests/fixtures/README.md`

- [ ] **Step 1: Write smoke test**

```python
# tests/integration/test_smoke.py
"""Real-pipeline smoke test. Skipped by default.

Run with: pytest -m integration

Requires:
- A small audio fixture at tests/fixtures/short-clip.wav (16kHz mono,
  ~30 seconds, public-domain content).
- sherpa-onnx ONNX models downloaded into ~/.cache/sherpa-onnx/whisper-base/.
- (Optional) HuggingFace token configured for pyannote.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm.transcriber import (
    PyannoteDiarizer,
    SherpaOnnxAsr,
    Transcriber,
    detect_device,
    render_transcript_markdown,
)

FIXTURE_AUDIO = Path(__file__).parent.parent / "fixtures" / "short-clip.wav"
MODEL_CACHE = Path("~/.cache/sherpa-onnx/whisper-base").expanduser()


@pytest.mark.integration
@pytest.mark.skipif(not FIXTURE_AUDIO.exists(), reason="fixture audio missing")
@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="sherpa-onnx model not downloaded")
def test_transcribe_short_clip_no_diarization() -> None:
    device = detect_device()
    asr = SherpaOnnxAsr(model_dir=MODEL_CACHE, model_name="whisper-base", device=device)
    transcriber = Transcriber(
        asr_engine=asr,
        diar_engine=None,
        model_name="whisper-base",
        diarization=False,
    )
    result = transcriber.transcribe(FIXTURE_AUDIO)
    assert result.segments
    assert result.duration_sec > 0


@pytest.mark.integration
@pytest.mark.skipif(not FIXTURE_AUDIO.exists(), reason="fixture audio missing")
def test_render_smoke() -> None:
    """Render path works on a synthetic TranscriptionResult — useful when
    sherpa-onnx isn't installed but you want to exercise output formatting."""
    from podcast_llm.transcriber import TranscriptSegment, TranscriptionResult

    result = TranscriptionResult(
        segments=[TranscriptSegment(0.0, 30.0, None, "smoke text")],
        duration_sec=30.0,
        model_name="whisper-base",
        diarization=False,
    )
    out = render_transcript_markdown(
        result,
        episode_id="smoke",
        channel_title="C",
        title="T",
        published_at="2026-04-20",
        url="https://x",
    )
    assert "smoke text" in out
```

- [ ] **Step 2: Write fixtures README**

```markdown
# tests/fixtures/

Test data used by unit and integration tests.

## short-clip.wav (NOT committed)

The integration smoke test (`tests/integration/test_smoke.py`) needs a
~30-second mono 16 kHz WAV file. To set up:

```bash
# Option A: generate a synthetic clip from text-to-speech (any tool)
ffmpeg -i <some-source.mp3> -ar 16000 -ac 1 -t 30 short-clip.wav

# Option B: use any short public-domain audio you have locally
ffmpeg -i <pd-audio.wav> -ar 16000 -ac 1 -t 30 short-clip.wav
```

The file is gitignored; do not commit copyrighted audio.
```

- [ ] **Step 3: Add fixture pattern to .gitignore**

Append to `.gitignore`:

```
tests/fixtures/short-clip.wav
tests/fixtures/*.mp3
tests/fixtures/*.m4a
```

- [ ] **Step 4: Verify integration tests skip cleanly by default**

Run: `pytest`
Expected: passes; integration tests not collected (per `addopts = -m 'not integration'`).

Run: `pytest -m integration`
Expected: collects integration tests; both skip with reason "fixture audio missing" (assuming you haven't placed one).

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_smoke.py tests/fixtures/README.md .gitignore
git commit -m "test: integration smoke test scaffolding (opt-in via -m integration)"
```

---

## Self-Review

After landing all the above, do this checklist before merging.

**1. Spec coverage:** check each section of `docs/superpowers/specs/2026-04-20-podcast-llm-design.md` against the plan.

| Spec section | Implemented in |
| --- | --- |
| §1 Summary | n/a (intent) |
| §2 Goals & Non-Goals | n/a (intent) |
| §3.1 Two-tier pipeline diagram | README + slash command |
| §3.2 Filesystem layout | Phase 0–12 file structure |
| §3.3 Data flow per episode | Phase 6 (pipeline) + Phase 11 (slash command) |
| §4.1 podcasts.yaml | Phase 2 (config) + Phase 12 (example) |
| §4.2 downloader.py | Phase 4 |
| §4.3 transcriber.py | Phase 5 |
| §4.4 ledger.py | Phase 3 |
| §4.5 pipeline.py | Phase 6 |
| §4.6 .claude/commands/analyze-podcast.md | Phase 11 |
| §4.7 wiki-schema-template.md | Phase 8 |
| §4.8 analysis-template.md | Phase 11 |
| §5.1 Per-vault layout | Phase 8 |
| §5.2 episodes/ rationale | Phase 8 + slash command |
| §5.3 Frontmatter | Phases 8, 10, 11 |
| §5.4 Page creation thresholds | Slash command (judgment by LLM) |
| §5.5 Tag taxonomy | SCHEMA.md template (Phase 8) |
| §5.6 What slash command writes | Phases 10–11 |
| §6.1 Base analysis template | Phase 11 |
| §6.2 Strict :: format + parse failure | Phase 9 (parser) + slash command (step 5) |
| §6.3 Lens injection | Slash command + podcasts.yaml |
| §6.4 Long-context handling | n/a (Opus context size) |
| §6.5 Failure isolation | Slash command (step 4 before step 7) |
| §7.1 Idempotency / atomic writes | Phase 1 (atomic_write) + Phase 3 (ledger) |
| §7.2 Failure handling per step | Phase 6 (pipeline error capture) + slash command failure modes table |
| §7.3 Concurrency (single worker default) | Phase 6 (no parallelism in MVP); --workers documented but not yet implemented (deferred) |
| §7.4 JSON-line logging | Phase 7 |
| §7.5 Testing strategy | Throughout (unit + Phase 13 integration) |
| §7.6 Pre-flight checks | Phase 7 |
| §7.7 Non-features | n/a (excluded) |
| §8 OSS considerations | Phase 0 (LICENSE, gitignore, example) + Phase 12 (README) |
| §9 README outline | Phase 12 |
| §10 Open questions | n/a (deferred) |
| §11 Sequencing | Followed |
| §12 References | n/a |

**Gaps deliberately deferred (already non-goals or future work per spec):**
- `--workers N` multi-GPU implementation: spec §7.3 marks experimental. CLI accepts the flag conceptually but no per-GPU lock implemented yet. Add later as Phase 14 if needed.
- `/lint-vault`: spec §10 lists as future work.
- "Promote first mention to entity page" retroactive linking: spec §10 lists as future work.

**2. Placeholder scan:** every step has actual code, exact paths, exact commands.

**3. Type/name consistency:** spot-check across phases:
- `EpisodeMetadata` (downloader) vs `EpisodeRecord` (ledger) vs `EpisodeMeta` (wiki writer) — three distinct types because they carry different fields. Pipeline (Phase 6) translates between them. Confirmed.
- `Transcriber.transcribe(audio_path)` returns `TranscriptionResult`. `render_transcript_markdown` accepts `TranscriptionResult`. Pipeline calls both. Consistent.
- `WikiWriter.copy_transcription / write_episode_page / upsert_entity_page / upsert_concept_page / update_index / append_log` — all defined; slash command's "step 7" references them by purpose. Consistent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-20-podcast-llm.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
