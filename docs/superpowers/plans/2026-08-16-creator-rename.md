# Podcast → Creator Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the user-facing "podcast" vocabulary to "creator", migrate the existing Huberman data to the new layout, register four YouTube creators, and ingest Dan Koe end-to-end.

**Architecture:** This is a rename plus config change. No download, transcribe, or ledger *logic* changes — the test suite should prove exactly that. The on-disk tree root is hardcoded in three places (`cli.py:126`, `pipeline.py:142`, `pipeline.py:173`); the config loader keys off `podcasts` in `config.py:74`; the ledger column lives in `COLLECTED_HEADER` at `ledger.py:10-14`. The Python package keeps its name.

**Tech Stack:** Python 3.12, pydantic v2, typer, pytest, yt-dlp, faster-whisper. Run tests with `.venv/bin/python -m pytest`.

## Global Constraints

- **Nothing may run while Tasks 1–6 execute.** `scripts/backfill.sh` spawns a *fresh* `python -m podcast_llm_wiki ingest` per run, so a code change lands mid-batch and the next run reads `creators/` while data still lives in `podcasts/`. Verify with `pgrep -af "backfill\.sh"` before starting, and again before Task 6.
- The Python package stays `podcast_llm_wiki`. Internal identifiers (`PodcastConfig`, `_RawPodcast`, `Config.podcasts`, `pod`, `enumerate_playlist`, `podcast_filter`) keep their names. This is a deliberate, documented inconsistency — do not "fix" it.
- Every task must leave the full suite green: `.venv/bin/python -m pytest -q`. Baseline is **140 passed, 2 deselected**.
- Never edit `collected.md` or `analysis_queue.md` by hand outside Task 6's script. They are the source of truth for 376+ episodes and are gitignored (no `git checkout` rollback).
- Commit after every task.

## File Structure

| File | Responsibility | Task |
| --- | --- | --- |
| `src/podcast_llm_wiki/config.py` | YAML keys `creators:` / `source_url` | 1 |
| `tests/fixtures/podcasts_minimal.yaml` → `creators_minimal.yaml` | Test fixture in new schema | 1 |
| `src/podcast_llm_wiki/ledger.py` | `COLLECTED_HEADER` creator column | 2 |
| `src/podcast_llm_wiki/pipeline.py` | Tree root, `pod.source_url` | 1, 3 |
| `src/podcast_llm_wiki/cli.py` | `--creator`, `creators.yaml`, tree root | 3, 4 |
| `tests/conftest.py` | `tmp_project` creates `creators/` | 3 |
| `scripts/migrate_to_creators.py` | Idempotent one-shot migration | 5 |
| `tests/unit/test_migration.py` | Rewrite-helper tests | 5 |
| `creators.yaml` | Four creator entries + lenses | 8 |
| `.claude/commands/`, `.claude/agents/`, `README.md`, `docs/` | Renamed skills/agents/docs | 7 |

---

### Task 1: Config accepts `creators:` and `source_url`

**Files:**
- Modify: `src/podcast_llm_wiki/config.py:29,44,67,74,84`
- Modify: `src/podcast_llm_wiki/pipeline.py:52`
- Rename: `tests/fixtures/podcasts_minimal.yaml` → `tests/fixtures/creators_minimal.yaml`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `PodcastConfig.source_url: str` (replaces `playlist_url`); `load_config(path)` reads the top-level `creators:` list. `Config.podcasts` attribute name is **unchanged**.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_config.py`:

```python
def test_loads_creators_key_with_source_url(tmp_path: Path) -> None:
    p = tmp_path / "creators.yaml"
    p.write_text(
        "defaults:\n"
        "  vault_root: ~/obsidian\n"
        "creators:\n"
        '  - name: "Dan Koe"\n'
        '    source_url: "https://www.youtube.com/@DanKoeTalks/videos"\n'
        "    lens: |\n"
        "      Test lens.\n"
    )
    cfg = load_config(p)
    assert len(cfg.podcasts) == 1
    assert cfg.podcasts[0].name == "Dan Koe"
    assert cfg.podcasts[0].source_url == "https://www.youtube.com/@DanKoeTalks/videos"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_config.py::test_loads_creators_key_with_source_url -v`
Expected: FAIL — `assert 0 == 1` (loader still reads `raw.get("podcasts")`, so the list is empty).

- [ ] **Step 3: Write minimal implementation**

In `config.py`, rename the field on both models (line 29 and line 44):

```python
    source_url: str
```

Update the loader docstring and key (lines 67, 74):

```python
def load_config(path: Path) -> Config:
    """Load and validate a creators.yaml file. Applies defaults to each creator."""
    raw = yaml.safe_load(Path(path).read_text())
    if raw is None:
        raw = {}

    defaults = Defaults(**(raw.get("defaults") or {}))
    podcasts: list[PodcastConfig] = []
    for entry in raw.get("creators") or []:
```

And the constructor call (line 84):

```python
                source_url=rp.source_url,
```

In `pipeline.py:52`:

```python
        episodes = self.downloader.enumerate_playlist(pod.source_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_config.py::test_loads_creators_key_with_source_url -v`
Expected: PASS

- [ ] **Step 5: Update the fixture and remaining config tests**

```bash
git mv tests/fixtures/podcasts_minimal.yaml tests/fixtures/creators_minimal.yaml
```

Rewrite `tests/fixtures/creators_minimal.yaml` to:

```yaml
defaults:
  vault_root: ~/obsidian
  max_backfill: 5
  stt_model: whisper-base
  diarization: true

creators:
  - name: "Test Podcast"
    source_url: "https://www.youtube.com/playlist?list=ABC"
    lens: |
      Test analytical lens.
```

Then in `tests/unit/test_config.py` and `tests/unit/test_pipeline.py`, replace every `podcasts:` YAML key with `creators:`, every `playlist_url:` with `source_url:`, every `playlist_url=` kwarg with `source_url=`, and every `podcasts_minimal.yaml` reference with `creators_minimal.yaml`. Find them with:

```bash
grep -rn "playlist_url\|podcasts:\|podcasts_minimal" tests/
```

Leave `cfg.podcasts` attribute accesses alone.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: **141 passed, 2 deselected** (140 old + 1 new, minus none removed — if the count differs, a test was silently dropped; investigate before continuing).

- [ ] **Step 7: Commit**

```bash
git add src/podcast_llm_wiki/config.py src/podcast_llm_wiki/pipeline.py tests/
git commit -m "Config: creators: key and source_url field

These sources are YouTube channels, not playlists. enumerate_playlist()
passes the URL straight to yt-dlp, which accepts @handle/videos unchanged,
so only the names change.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Ledger `creator` column

**Files:**
- Modify: `src/podcast_llm_wiki/ledger.py:10-14`
- Test: `tests/unit/test_ledger.py:15`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `COLLECTED_HEADER` whose first column is `creator`. Column *order and count are unchanged* (11 columns), so `EpisodeRecord.from_row`/`to_row` need no edits.

- [ ] **Step 1: Write the failing test**

Replace the assertion in `tests/unit/test_ledger.py::TestLedgerInit::test_creates_collected_md_with_header` (line 15):

```python
        assert "| creator | channelTitle |" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_ledger.py::TestLedgerInit::test_creates_collected_md_with_header -v`
Expected: FAIL — header still reads `| podcast | channelTitle |`.

- [ ] **Step 3: Write minimal implementation**

In `ledger.py:10-14`:

```python
COLLECTED_HEADER = (
    "| creator | channelTitle | title | publishedAt | url | episode_id | status "
    "| downloaded_at | transcribed_at | analyzed_at | error |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: **141 passed, 2 deselected**

- [ ] **Step 5: Commit**

```bash
git add src/podcast_llm_wiki/ledger.py tests/unit/test_ledger.py
git commit -m "Ledger: rename collected.md first column to creator

Column order and count are unchanged, so row parsing is unaffected.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: On-disk tree root becomes `creators/`

**Files:**
- Modify: `src/podcast_llm_wiki/pipeline.py:142,173`
- Modify: `src/podcast_llm_wiki/cli.py:126`
- Modify: `tests/conftest.py:12`
- Test: `tests/unit/test_pipeline.py`

**Interfaces:**
- Consumes: `PipelineConfig` unchanged from Task 1.
- Produces: audio at `<project_root>/creators/<name>/downloads/<id>.wav`, transcripts at `<project_root>/creators/<name>/transcriptions/<base> - transcription.md`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_pipeline.py` (imports `Pipeline`, `Config`, `Ledger` already exist in that module; add any that are missing):

```python
def test_audio_path_lives_under_creators(tmp_project: Path) -> None:
    p = Pipeline(
        project_root=tmp_project,
        config=Config(),
        ledger=Ledger(tmp_project),
        downloader=None,
        transcriber_factory=lambda pod: None,
    )
    assert p._audio_path("Dan Koe", "abc123") == (
        tmp_project / "creators" / "Dan Koe" / "downloads" / "abc123.wav"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_pipeline.py::test_audio_path_lives_under_creators -v`
Expected: FAIL — path contains `podcasts` where `creators` is expected.

- [ ] **Step 3: Write minimal implementation**

`pipeline.py:142` and `pipeline.py:173` — change both occurrences of:

```python
            / "podcasts"
```

to:

```python
            / "creators"
```

`cli.py:126`:

```python
        downloads_root=project_root / "creators",
```

`tests/conftest.py:12`:

```python
    (tmp_path / "creators").mkdir()
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: **142 passed, 2 deselected**

- [ ] **Step 5: Commit**

```bash
git add src/podcast_llm_wiki/pipeline.py src/podcast_llm_wiki/cli.py tests/
git commit -m "Move the on-disk tree from podcasts/ to creators/

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: CLI surface — `--creator` and `creators.yaml`

**Files:**
- Modify: `src/podcast_llm_wiki/cli.py:68,71,74`
- Test: `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: Task 3's tree root.
- Produces: `--creator` option (was `--podcast`); `--config` defaults to `creators.yaml`. The Python parameter stays named `podcast` so `podcast_filter=podcast` wiring is untouched.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_cli.py`:

```python
def test_ingest_help_exposes_creator_flag() -> None:
    from typer.testing import CliRunner

    from podcast_llm_wiki.cli import app

    result = CliRunner().invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "--creator" in result.stdout
    assert "--podcast" not in result.stdout
    assert "creators.yaml" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py::test_ingest_help_exposes_creator_flag -v`
Expected: FAIL — `--podcast` is still in the help output.

- [ ] **Step 3: Write minimal implementation**

`cli.py:67-75`:

```python
    config: Path = typer.Option(
        Path("creators.yaml"), "--config", help="Path to creators.yaml."
    ),
    project_root: Path = typer.Option(
        Path("."), "--project-root", help="Project root containing creators/, logs/, etc."
    ),
    podcast: Optional[str] = typer.Option(
        None, "--creator", help="Process only this creator (by name)."
    ),
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: **143 passed, 2 deselected**

- [ ] **Step 5: Update the backfill driver**

`scripts/backfill.sh` invokes the CLI with `--podcast`. Change that one line to `--creator`:

```bash
    "$PY" -m podcast_llm_wiki ingest \
        --resume --limit 1 --creator "$PODCAST" \
```

Verify the script's own tests still pass:

Run: `.venv/bin/python -m pytest tests/unit/test_backfill_script.py -v`
Expected: **2 passed**

- [ ] **Step 6: Commit**

```bash
git add src/podcast_llm_wiki/cli.py scripts/backfill.sh tests/unit/test_cli.py
git commit -m "CLI: --creator replaces --podcast, config defaults to creators.yaml

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Migration script and its rewrite helpers

**Files:**
- Create: `scripts/migrate_to_creators.py`
- Test: `tests/unit/test_migration.py`

**Interfaces:**
- Consumes: the new header from Task 2.
- Produces: `rewrite_ledger_header(text: str) -> str` and `rewrite_queue_paths(text: str) -> str`, both pure and idempotent; `main(project_root: Path, vault_root: Path, dry_run: bool) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_migration.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_migration.py -v`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'migrate_to_creators'`.

- [ ] **Step 3: Write minimal implementation**

Create `scripts/migrate_to_creators.py`:

```python
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

    for src, dst in moves:
        if dst.exists():
            print(f"skip (already migrated): {src.name}")
        elif not src.exists():
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
            path.write_text(after)
            print(f"rewrote: {path.name}")

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=Path("."))
    ap.add_argument("--vault-root", type=Path, default=Path("~/obsidian").expanduser())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.project_root, a.vault_root, a.dry_run))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_migration.py -v`
Expected: **5 passed**

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: **148 passed, 2 deselected**

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_to_creators.py tests/unit/test_migration.py
git commit -m "Add idempotent podcast -> creator data migration

Rewrites are pure functions with tests, including the case where an
episode title itself contains the word 'podcasts'.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Execute the migration (operational)

**Files:** none edited by hand. This task runs Task 5's script against real data.

**Interfaces:**
- Consumes: `scripts/migrate_to_creators.py` from Task 5.
- Produces: `creators.yaml`, `creators/` tree, migrated ledger and queue, renamed vault.

- [ ] **Step 1: Confirm nothing is ingesting**

```bash
pgrep -af "backfill\.sh|podcast_llm_wiki ingest" || echo "clear to migrate"
```

Expected: `clear to migrate`. **If anything is running, stop here** and wait for it to finish.

- [ ] **Step 2: Record the pre-migration baseline**

```bash
cd /home/administrator/code/podcast-llm-wiki
echo "rows:  $(( $(grep -c '^|' collected.md) - 2 ))"
echo "files: $(ls -1 'podcasts/Huberman Lab/transcriptions'/*transcription.md | wc -l)"
echo "queue: $(grep -c '^- ' analysis_queue.md)"
```

Write the three numbers down. They must be identical after the migration.

- [ ] **Step 3: Dry run**

```bash
.venv/bin/python scripts/migrate_to_creators.py --dry-run
```

Expected: four `would move` lines and two `would rewrite` lines. If any says `skip (missing)` for `podcasts/` or `collected.md`, stop and investigate.

- [ ] **Step 4: Execute**

```bash
.venv/bin/python scripts/migrate_to_creators.py
```

- [ ] **Step 5: Verify three-way consistency**

```bash
echo "rows:  $(( $(grep -c '^|' collected.md) - 2 ))"
echo "files: $(ls -1 'creators/Huberman Lab/transcriptions'/*transcription.md | wc -l)"
echo "queue: $(grep -c '^- ' analysis_queue.md)"
grep -c '^- podcasts/' analysis_queue.md || echo "no stale podcasts/ paths (good)"
head -1 collected.md
```

Expected: the same three numbers as Step 2; zero stale `podcasts/` paths; header starts `| creator |`.

- [ ] **Step 6: Update Huberman's vault_path**

In `creators.yaml`, change:

```yaml
    vault_path: "~/obsidian/Creator - Huberman Lab"
```

- [ ] **Step 7: Prove the pipeline resolves paths into the migrated tree**

Do **not** try to verify this by running `ingest` with `--limit 0`. Zero is
falsy, so it reads as "no limit" and would start a full unbounded ingest against
live channels. Verify offline instead — no network, nothing downloaded:

```bash
cd /home/administrator/code/podcast-llm-wiki
.venv/bin/python - <<'PY'
from pathlib import Path
from podcast_llm_wiki.config import load_config
from podcast_llm_wiki.ledger import Ledger
from podcast_llm_wiki.pipeline import Pipeline

root = Path(".")
cfg = load_config(Path("creators.yaml"))
p = Pipeline(
    project_root=root,
    config=cfg,
    ledger=Ledger(root),
    downloader=None,
    transcriber_factory=lambda pod: None,
)

audio = p._audio_path("Huberman Lab", "xKvlK7OqZso")
assert "creators" in audio.parts and "podcasts" not in audio.parts, audio
print("audio path ->", audio)

# The transcripts the migration moved must be where the pipeline now looks.
tdir = root / "creators" / "Huberman Lab" / "transcriptions"
print("transcripts on disk ->", len(list(tdir.glob("*transcription.md"))))

# Every queued path must resolve to a real file.
missing = [
    ln.strip()[2:]
    for ln in Path("analysis_queue.md").read_text().splitlines()
    if ln.startswith("- ") and not (root / ln.strip()[2:]).exists()
]
print("queue entries pointing at missing files:", len(missing))
assert not missing, missing[:3]
print("OK")
PY
```

Expected: the audio path contains `creators`, the transcript count matches
Step 5, and **zero** queue entries point at missing files, ending in `OK`. A
non-empty `missing` list means the queue rewrite and the tree move disagree.

- [ ] **Step 8: Commit**

```bash
git add creators.yaml creators.yaml.example
git commit -m "Migrate Huberman data to the creators/ layout

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Rename skills, agents, and docs

**Files:**
- Rename: `.claude/commands/ingest-podcast.md` → `ingest-creator.md`, `analyze-podcast.md` → `analyze-creator.md`
- Rename: `.claude/agents/podcast-ingester.md` → `creator-ingester.md`, `podcast-analyzer.md` → `creator-analyzer.md`
- Modify: `README.md`, `docs/analysis-template.md`, `docs/wiki-schema-template.md`

**Interfaces:**
- Consumes: the CLI surface from Task 4 (docs must show `--creator` and `creators.yaml`).
- Produces: `/ingest-creator` and `/analyze-creator` skills dispatching `creator-ingester` / `creator-analyzer` agents.

- [ ] **Step 1: Rename the four files**

```bash
git mv .claude/commands/ingest-podcast.md .claude/commands/ingest-creator.md
git mv .claude/commands/analyze-podcast.md .claude/commands/analyze-creator.md
git mv .claude/agents/podcast-ingester.md .claude/agents/creator-ingester.md
git mv .claude/agents/podcast-analyzer.md .claude/agents/creator-analyzer.md
```

- [ ] **Step 2: Update their contents**

In each renamed file, update the frontmatter `name:` field and every in-body reference:
- `podcast-ingester` → `creator-ingester`, `podcast-analyzer` → `creator-analyzer`
- `/ingest-podcast` → `/ingest-creator`, `/analyze-podcast` → `/analyze-creator`
- `podcasts.yaml` → `creators.yaml`, `--podcast` → `--creator`, `podcasts/` → `creators/`
- Prose "podcast" → "creator" where it refers to a configured source (leave it where it genuinely means a podcast).

Find every remaining hit with:

```bash
grep -rn "podcast" .claude/ README.md docs/ | grep -v "podcast_llm_wiki\|podcast-llm-wiki"
```

`podcast_llm_wiki` and `podcast-llm-wiki` are the package and repo names — leave those.

- [ ] **Step 3: Verify no stale references**

```bash
grep -rn "ingest-podcast\|analyze-podcast\|podcast-ingester\|podcast-analyzer\|podcasts\.yaml\|--podcast\b" .claude/ README.md docs/ scripts/ || echo "clean"
```

Expected: `clean`

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: **148 passed, 2 deselected**

- [ ] **Step 5: Commit**

```bash
git add -A .claude README.md docs
git commit -m "Rename skills, agents and docs to the creator vocabulary

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Register the four creators

**Files:**
- Modify: `creators.yaml`

**Interfaces:**
- Consumes: the `creators:` / `source_url` schema from Task 1.
- Produces: four configured creators. Only Dan Koe is ingested (Task 9).

- [ ] **Step 1: Append the four entries**

Add to `creators.yaml` under `creators:`, after the existing Huberman entry. All four share the same lens brief — actionable playbooks — differing only in domain emphasis:

```yaml
  - name: "Dan Koe"
    source_url: "https://www.youtube.com/@DanKoeTalks/videos"
    vault_path: "~/obsidian/Creator - Dan Koe"
    lens: |
      Dan Koe covers solo business, positioning, and the mental models behind
      one-person companies.

      Extract tactics and systems with their preconditions, sequencing, and any
      concrete numbers: pricing, posting cadence, offer structure, hours per
      week. Capture the reasoning behind a tactic in one or two sentences so the
      "why" survives alongside the "how."

      Flag where advice assumes an audience size, capital base, or track record
      the reader may not have — this is the most common failure mode in solo
      business advice. Note when a claim rests only on the creator's own results.

  - name: "Ali Abdaal"
    source_url: "https://www.youtube.com/@aliabdaal/videos"
    vault_path: "~/obsidian/Creator - Ali Abdaal"
    lens: |
      Ali Abdaal covers productivity systems, creator business, and study
      technique.

      Extract tactics and systems with their preconditions, sequencing, and any
      concrete numbers: tool stacks, time budgets, revenue splits, team size.
      Capture the reasoning in one or two sentences.

      Flag where advice assumes an audience size, capital base, or track record
      the reader may not have. Note when a productivity claim is presented as
      research-backed and record what the underlying study actually showed.

  - name: "Alex Hormozi"
    source_url: "https://www.youtube.com/@AlexHormozi/videos"
    vault_path: "~/obsidian/Creator - Alex Hormozi"
    lens: |
      Alex Hormozi covers offers, sales, and scaling service businesses.

      Extract tactics and systems with their preconditions, sequencing, and any
      concrete numbers: price points, margins, close rates, headcount, ad spend.
      Capture the reasoning in one or two sentences.

      Flag where advice assumes a capital base, existing deal flow, or risk
      tolerance the reader may not have. Record the business type and stage a
      tactic is meant for — advice for a $100k/yr gym rarely transfers to a
      $10M/yr agency.

  - name: "Gary Vee"
    source_url: "https://www.youtube.com/@garyvee/videos"
    vault_path: "~/obsidian/Creator - Gary Vee"
    lens: |
      Gary Vaynerchuk covers attention, social platforms, and personal brand.

      Extract tactics and systems with their preconditions, sequencing, and any
      concrete numbers: platform, format, posting volume, budget. Capture the
      reasoning in one or two sentences.

      Flag where advice assumes an audience size, capital base, or team the
      reader may not have. Much of this material is motivational rather than
      procedural — when a segment contains no actionable tactic, say so plainly
      rather than manufacturing one.
```

- [ ] **Step 2: Verify the config parses and all five load**

```bash
.venv/bin/python -c "
from pathlib import Path
from podcast_llm_wiki.config import load_config
cfg = load_config(Path('creators.yaml'))
for c in cfg.podcasts:
    print(f'{c.name:16} {c.source_url}')
print('total:', len(cfg.podcasts))
"
```

Expected: five lines (Huberman Lab plus the four) and `total: 5`.

- [ ] **Step 3: Verify each channel URL enumerates**

```bash
for u in DanKoeTalks aliabdaal AlexHormozi garyvee; do
  printf "%-14s %s\n" "$u" "$(timeout 120 .venv/bin/yt-dlp --flat-playlist --playlist-end 1 --print '%(title)s' "https://www.youtube.com/@$u/videos" 2>/dev/null | head -1)"
done
```

Expected: one real video title per channel. Empty output means the URL or network is wrong — fix before ingesting.

- [ ] **Step 4: Commit**

```bash
git add creators.yaml
git commit -m "Register Dan Koe, Ali Abdaal, Alex Hormozi and Gary Vee

All four share an actionable-playbook lens: tactics with preconditions,
sequencing and concrete numbers, flagging advice that assumes an audience
or capital base the reader lacks.

Only Dan Koe is ingested for now -- the four together are 4459 videos,
~960GB of retained audio against 528GB free.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Ingest Dan Koe (operational)

**Files:** none. This runs the pipeline.

**Interfaces:**
- Consumes: everything above.
- Produces: ~163 transcripts under `creators/Dan Koe/transcriptions/`, ledger rows, queue entries.

- [ ] **Step 1: Smoke-test a single episode**

```bash
cd /home/administrator/code/podcast-llm-wiki
.venv/bin/python -m podcast_llm_wiki ingest --creator "Dan Koe" --limit 1 --log-level INFO
```

Expected: one episode downloads and transcribes. Confirm:

```bash
ls "creators/Dan Koe/transcriptions/" | head
grep -c '| Dan Koe |' collected.md
```

Expected: one transcription file, one ledger row.

- [ ] **Step 2: Read the transcript before scaling up**

Open the file from Step 1 and check the diarization and text quality. Dan Koe's videos are largely monologue, unlike Huberman's interviews — if diarization produces noise, that is worth knowing before 162 more episodes, and `diarization: false` can be set on his entry.

- [ ] **Step 3: Launch the backfill**

```bash
nohup scripts/backfill.sh "Dan Koe" 200 60 > logs/backfill-dankoe-1.log 2>&1 &
sleep 8
pgrep -af "backfill\.sh Dan Koe"
cat logs/backfill-dankoe-1.log
```

200 runs against 163 videos leaves headroom for retries; the script stops early on `no new episodes`.

- [ ] **Step 4: Verify on completion**

```bash
echo "rows:  $(( $(grep -c '^|' collected.md) - 2 ))"
echo "dankoe: $(grep -c '| Dan Koe |' collected.md)"
echo "files: $(ls -1 'creators/Dan Koe/transcriptions'/*transcription.md | wc -l)"
echo "queue: $(grep -c '^- ' analysis_queue.md)"
```

Expected: Dan Koe rows and files agree, and the queue grew by the same amount.

---

## Not in this plan

- **Analysis of Dan Koe.** Step 4 of the spec's sequencing. It is a separate plan because the analysis path has never been run, so it needs its own design pass, not a task appended here.
- **Ingesting Ali Abdaal / Hormozi / Gary Vee.** Gated on what the Dan Koe run teaches.
- **`min_duration_sec` filter and audio cleanup.** Explicitly deferred by the spec.
