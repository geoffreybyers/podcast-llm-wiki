# podcast-llm — Design Spec

**Date:** 2026-04-20
**Status:** Approved (pending user spec review)
**Author:** Brainstormed with Claude (superpowers:brainstorming)

---

## 1. Summary

`podcast-llm` ingests YouTube podcast playlists, transcribes episodes locally with diarization, and produces structured analyses that compound into a per-podcast Karpathy-style LLM Wiki inside an Obsidian vault.

The system is a **two-tier pipeline**:

- **Tier 1 (automated, no LLM):** yt-dlp downloads new episodes → sherpa-onnx transcribes with diarization → ledger and queue update. Cron-friendly, runs on CPU or any GPU.
- **Tier 2 (Claude Code session):** `/analyze-podcast` slash command reads the next pending transcription, generates a structured analysis under a per-playlist analytical lens, and updates the corresponding Obsidian vault (entities/concepts/episodes pages, index, log) using Karpathy LLM Wiki conventions.

The Karpathy LLM Wiki structure (`SCHEMA.md`, `index.md`, `log.md`, `raw/`, `episodes/`, `entities/`, `concepts/`, `comparisons/`, `queries/`) is **baked into the project's slash command**, not delegated to a separate agent runtime. (The `episodes/` layer is a deviation from Karpathy original; rationale in §5.2.)

This will be released as a **public MIT-licensed OSS project** on GitHub.

---

## 2. Goals & Non-Goals

### Goals

- Reliable, resumable ingest of YouTube podcast playlists with no manual filename juggling.
- Diarized transcripts that read naturally and attribute speech where the format warrants it.
- Per-episode structured analyses that produce compounding cross-references in a personal knowledge base.
- One-vault-per-podcast segregation so each Obsidian graph stays focused.
- Defaults that work on a laptop (CPU or single GPU); power-user configurability without complexity bleed into the happy path.
- Reproducible setup for any user who clones the repo.

### Non-Goals (explicitly out of scope)

- Web UI, TUI, or dashboard. `collected.md` opened in Obsidian is the dashboard.
- Email / Slack / push notifications.
- Cross-vault synthesis (deferred to a future "meta vault" if ever needed).
- Real-time / live transcription.
- Non-YouTube ingestion (RSS, Spotify, Apple Podcasts) — yt-dlp handles a wide range of sources but the design assumes YouTube playlists.
- LLM-based wiki linting — the Karpathy `lint` operation is deferred to a future `/lint-vault` command.
- Automated multi-GPU concurrency by default. Single device, with an experimental `--workers N` flag for advanced users.

---

## 3. Architecture

### 3.1 Two-tier pipeline

```
┌──────────── TIER 1: AUTOMATED (cron-able, no LLM) ────────────┐
│                                                                │
│  yt-dlp ──► audio file ──► sherpa-onnx ──► diarized .md       │
│  (per playlist,                            transcription       │
│   incremental)                             + collected.md      │
│                                            update              │
│                                                                │
│  Output: transcription on disk, episode in collected.md        │
│          status="transcribed", appended to analysis_queue.md   │
└────────────────────────────────────────────────────────────────┘
                               │
                               │  (handoff via files, no IPC)
                               ▼
┌──────── TIER 2: HUMAN-IN-LOOP (Claude Code session) ──────────┐
│                                                                │
│  /analyze-podcast [N=1]                                        │
│    1. Read next N from analysis_queue.md                       │
│    2. For each:                                                │
│       - Read transcription                                     │
│       - Apply per-playlist analytical lens                     │
│       - Write analysis .md                                     │
│       - Update wiki: raw/, episodes/, entities/, concepts/,    │
│         index, log                                             │
│       - Mark "analyzed" in collected.md, pop from queue        │
│                                                                │
│  Output: analysis on disk + wiki pages written/updated         │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 Filesystem layout

**Project repo (example path: `~/dev/podcast-llm/`; users may clone anywhere):**

```
podcast-llm/
├── README.md
├── LICENSE                       (MIT)
├── pyproject.toml
├── podcasts.yaml.example         (committed; dummy config + schema)
├── podcasts.yaml                 (gitignored; user's real config)
├── collected.md                  (gitignored; master ledger)
├── analysis_queue.md             (gitignored; FIFO)
├── logs/                         (gitignored)
├── podcasts/                     (gitignored)
│   └── <podcast-name>/
│       ├── downloads/            (audio files + .info.json sidecars)
│       ├── transcriptions/       (diarized .md)
│       ├── analyses/             (per-episode analysis .md)
│       └── .archive              (yt-dlp download archive)
├── src/podcast_llm/
│   ├── __init__.py
│   ├── config.py                 (load podcasts.yaml)
│   ├── downloader.py             (yt-dlp wrapper)
│   ├── transcriber.py            (sherpa-onnx + diarization)
│   ├── ledger.py                 (collected.md + queue, atomic ops)
│   ├── pipeline.py               (orchestrator / CLI entrypoint)
│   └── parsers/
│       └── analysis_sections.py  (parse Entities/Concepts blocks)
├── docs/
│   ├── superpowers/specs/        (this file)
│   ├── wiki-schema-template.md   (per-vault SCHEMA.md template)
│   └── analysis-template.md      (canonical analysis structure)
├── .claude/
│   └── commands/
│       └── analyze-podcast.md    (slash command, ships with repo)
└── tests/
    ├── unit/
    ├── integration/              (real fixture audio, opt-in)
    └── fixtures/
        └── short-clip.wav        (~30s public-domain audio)
```

**User's Obsidian root (`~/obsidian/`, configurable per podcast):**

```
~/obsidian/
├── <Podcast Name 1>/             ← one vault per podcast
│   ├── SCHEMA.md
│   ├── index.md
│   ├── log.md
│   ├── raw/transcripts/
│   ├── episodes/
│   ├── entities/
│   ├── concepts/
│   ├── comparisons/
│   ├── queries/
│   └── .obsidian/                (created when user opens vault)
└── <Podcast Name 2>/  ...
```

### 3.3 Data flow per episode

1. yt-dlp `--flat-playlist` enumerates new episode IDs (filtered against `collected.md` and the `.archive` file).
2. New episodes are downloaded as audio (best audio → 16 kHz mono WAV) plus `.info.json` metadata sidecar.
3. Transcriber loads sherpa-onnx model + diarization pipeline, writes diarized `.md` with timestamps to `transcriptions/`.
4. Ledger appends an entry to `collected.md` (`status: transcribed`) and a path entry to `analysis_queue.md`.
5. (Later, in a Claude Code session) `/analyze-podcast` pops from queue, generates analysis, writes `analyses/<channelTitle> - <title> - analysis.md`.
6. Slash command updates the episode's vault: copies transcription to `raw/transcripts/`, writes `episodes/<...>.md`, creates/updates entity & concept pages, updates `index.md` and `log.md`.
7. Ledger marks episode `status: analyzed`.

---

## 4. Components

### 4.1 `config/podcasts.yaml`

Per-podcast configuration. Single source of truth for playlist URLs, models, lenses, and vault paths.

```yaml
defaults:
  vault_root: ~/obsidian
  max_backfill: 20            # B-style limited backfill
  stt_model: whisper-base     # safe default; CPU-tolerable
  diarization: true
  diarization_segmentation: pyannote-segmentation-3.0
  diarization_embedding: 3d-speaker

podcasts:
  - name: "All-In"
    playlist_url: "https://www.youtube.com/playlist?list=PLn5..."
    # vault_path defaults to {vault_root}/{name}
    lens: |
      Frame insights through business strategy, market dynamics, ...
    # Per-podcast model overrides allowed:
    # stt_model: whisper-medium
```

### 4.2 `src/downloader.py`

- Thin wrapper around yt-dlp.
- `--flat-playlist` to enumerate; cross-references `collected.md` + `.archive` to skip seen episodes.
- Downloads `bestaudio`, post-processes to 16 kHz mono WAV (sherpa-onnx requirement).
- Always writes `.info.json` sidecar via yt-dlp (`--write-info-json`).
- Caps per-run downloads at `max_backfill` for first-run baseline (option B from brainstorming: limited backfill + new going forward).

### 4.3 `src/transcriber.py`

- Loads sherpa-onnx ASR model + (optional) diarization pipeline once per process.
- Auto-detects device: CUDA → MPS → CPU. Logs the choice.
- Output format (per episode):

```markdown
---
episode_id: <yt id>
channelTitle: <...>
title: <...>
publishedAt: YYYY-MM-DD
url: https://...
duration_sec: <int>
transcribed_at: ISO-8601
model: whisper-base
diarization: true
---

[00:00:00] Speaker 1: ...
[00:00:18] Speaker 2: ...
...
```

- Filename: `<channelTitle> - <title> - transcription.md`. Sanitized for filesystem safety (slashes / null bytes / leading dots stripped; long titles truncated to 200 chars + episode_id suffix).

### 4.4 `src/ledger.py`

- Owns `collected.md` and `analysis_queue.md`.
- All writes via `tempfile.NamedTemporaryFile` + `os.replace` for atomicity. Cron and Claude Code can never observe a half-written file.
- `collected.md` is a markdown table:

```markdown
| podcast | channelTitle | title | publishedAt | url | status | downloaded_at | transcribed_at | analyzed_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

- `analysis_queue.md` is a plain bulleted list of absolute transcription paths in FIFO order; `/analyze-podcast` pops from the top.

### 4.5 `src/pipeline.py`

- CLI entrypoint: `python -m podcast_llm ingest [--podcast <name>] [--limit N] [--workers N]`.
- For each podcast: enumerate → download new (capped) → transcribe each → update ledger.
- `--workers` defaults to 1. Documented as experimental for users with multiple CUDA devices.
- Pre-flight checks on first run: yt-dlp installed, sherpa-onnx ONNX models available (downloaded to `~/.cache/sherpa-onnx/` if missing), each vault path exists or is created with full skeleton, GPU/CPU device verified.

### 4.6 `.claude/commands/analyze-podcast.md`

The slash command. Ships with the repo so any user who clones it gets the command in Claude Code automatically.

Responsibilities:
- Parse args: `[N]` (default 1) or `[--match <substring>]` (cherry-pick).
- Read next entry from `analysis_queue.md`; locate transcription + vault.
- If the target vault doesn't exist (e.g., user added a new podcast and ran the slash command before the pipeline pre-flight), create the full skeleton (`SCHEMA.md`, `index.md`, `log.md`, all subdirs) before proceeding. Defensive — the pipeline pre-flight (§7.6) is the primary creator, but the slash command must not fail just because pre-flight hasn't run.
- Inject per-playlist lens fragment from `podcasts.yaml` into base analysis prompt.
- Write analysis file to `analyses/`.
- Update vault per the wiki schema (§5).
- Update `collected.md` and `analysis_queue.md`.
- Surface errors clearly; never partial-update the wiki.

### 4.7 `docs/wiki-schema-template.md`

Canonical `SCHEMA.md` template the slash command writes into a vault on first use. Adapted from the Hermes llm-wiki SKILL but specialized for podcast episodes:

- Adds `episodes/` layer.
- Frontmatter includes `episode_id`, `channelTitle`, `publishedAt`, `transcription_path`, `analysis_path`.
- Tag taxonomy seeded by per-podcast lens (the slash command uses the lens to propose an initial taxonomy on vault creation).

### 4.8 `docs/analysis-template.md`

Canonical analysis file structure (see §6). Single source of truth for the format. The wiki update step parses `Entities` and `Concepts` sections programmatically — format must stay stable.

---

## 5. Wiki schema (per-vault, Karpathy-style adapted)

### 5.1 Per-vault directory layout

```
<vault>/
├── SCHEMA.md          ← domain + lens + tag taxonomy
├── index.md           ← catalog, sectioned by type
├── log.md             ← append-only action log
├── raw/transcripts/   ← copy of transcription .md (Layer 1, immutable)
├── episodes/          ← one page per episode (TL;DR + frontmatter + wikilinks)
├── entities/          ← people, orgs, products, studies cited
├── concepts/          ← ideas, mechanisms, frameworks discussed
├── comparisons/       ← agent or user-created cross-episode synthesis
└── queries/           ← filed query results worth keeping
```

### 5.2 Why `episodes/` (deviation from Karpathy original)

Each episode gets its own page acting as the join table between the raw transcript and the entities/concepts it surfaced. Without this, `[[wikilinks]]` from entity pages have nowhere natural to point back to. The episode page is a thin overview (TL;DR + key insights) with `[[links]]` to every entity/concept it touched.

### 5.3 Frontmatter (every wiki page)

```yaml
---
title: <page title>
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: episode | entity | concept | comparison | query
tags: [from per-vault taxonomy]
# Episode pages additionally:
episode_id: <yt video id>
channelTitle: <...>
publishedAt: YYYY-MM-DD
url: https://youtube.com/watch?v=...
transcription_path: <abs path in podcast-llm>
analysis_path: <abs path in podcast-llm>
---
```

### 5.4 Page creation thresholds (per Karpathy)

- Entity/concept page created only if mentioned in **2+ episodes** OR central to one episode.
- "Central to one episode" is a judgment call made by the slash command (LLM call) — a guest interview's primary subject, a study an entire episode is structured around, etc. Conservative bias: when in doubt, do **not** create a page; the next mention will trigger promotion.
- First mention (not central): just record on the episode page.
- Second mention (in any later episode): promote to its own page; retroactively link the first episode.

### 5.5 Tag taxonomy

Seeded per-vault from the analytical lens. Slash command can propose new tags but must add them to `SCHEMA.md` *before* using them. Prevents tag sprawl.

Example taxonomy (Huberman lens):
- mechanisms: dopamine, cortisol, circadian, sleep, focus, recovery
- protocols: supplementation, light-exposure, breathwork, exercise
- people: huberman, guests-by-name, scientists-cited
- studies: rct, meta-analysis, animal-model
- meta: contradiction, follow-up, controversy

### 5.6 What `/analyze-podcast` writes to the vault, in order

1. Copy transcription → `raw/transcripts/`.
2. Write/update `episodes/<channelTitle> - <title>.md` with TL;DR + insights + frontmatter.
3. For each Entity in analysis: check if page exists; if yes, append + bump `updated`; if no and threshold met, create with cross-links.
4. For each Concept in analysis: same as entities.
5. Update `index.md`: add new pages alphabetically under correct section, bump count + date.
6. Append to `log.md`: `## [YYYY-MM-DD] analyze | <episode title>` + bullet list of files touched.

---

## 6. Analysis prompt + per-playlist lens

### 6.1 Base template (every analysis, every podcast)

```markdown
# <channelTitle> — <title>

## TL;DR
3 sentences. The thesis, the new thing, why it matters.

## Key Insights (5–10)
Each insight = bolded claim + 1-paragraph explanation + [timestamp].
Ranked by novelty, not order of appearance.

## Critical Pass
- **Steelman(s) of the strongest argument(s) (1–3):** When the episode contains
  multiple distinct theses (panel disagreements, guests making several
  independent claims), steelman each separately and label by speaker. When the
  episode has one clear central thesis, just one. Cap at 3 — beyond that,
  candidates belong in *Key Insights*, not here. Never pad.
- **Weak claims / unsupported assertions:** ...
- **Factual claims requiring verification:** [bullet list]
- **Contradictions with prior episodes (if any):** [[wikilinks]]

## Entities (parsed by wiki writer)
- name :: type (person|org|study|product) :: 1-line context :: [timestamp]
- ...

## Concepts (parsed by wiki writer)
- name :: 1-line definition :: [timestamp]
- ...

## Follow-ups
Open questions, things to look up, episodes to revisit.
```

### 6.2 Strict `::`-delimited Entities/Concepts format

Non-negotiable. The wiki writer parses these sections deterministically (no LLM cost at parse time). Every analysis run produces machine-readable hooks for the deterministic wiki update.

**Parser failure mode:** if any line is malformed, the parser **aborts the wiki update entirely** for that analysis (does not partial-update). The analysis file persists; the slash command surfaces the malformed line and asks the user to either fix the analysis file in place and rerun, or skip this episode's wiki update with an explicit confirmation. Rationale: a half-updated wiki is worse than none — orphan entity pages, missing cross-links, etc.

### 6.3 Per-playlist lens injection

The slash command pulls each podcast's `lens` field from `podcasts.yaml` and prepends it to the base prompt before invoking analysis.

Initial lens examples (user's personal config; not committed):

- **All-In** (4-host panel): business strategy, market dynamics, political economy, technology trends. Disagreements ARE the signal. When panelists hold distinct positions on a topic, steelman each separately in the Critical Pass under the panelist's name. Skeptical of hot takes.
- **Huberman Lab** (science protocols): mechanism + evidence quality (RCT > observational > animal > anecdote) + dose/timing/context + contraindications. Distinguish clinical advice from speculation.
- **Modern Wisdom** (advice/psychology): actionable advice + underlying principle + concrete first action. Identify guest contradictions across episodes.
- **Diary of a CEO** (biography/decisions): formative experiences + counter-intuitive lessons + compounding decisions. Flag polished story vs. genuine struggle.

### 6.4 Long-context handling

A 2-hour episode is ~30k–50k transcript tokens. Opus 4.7 has a 200k context, so the entire transcript is passed in one shot — no chunking. Cost per episode: ~30k–50k input + 3k–5k output, comfortably within Claude Code Opus quota for ~10–20 analyses per session.

### 6.5 Failure isolation

The analysis writes to disk **before** updating the wiki. If wiki update fails (e.g., parse error on Entities), the analysis file persists, the queue entry stays, the user can retry without re-spending Opus tokens.

---

## 7. Operational concerns

### 7.1 Idempotency & resumability

- `collected.md` is the source of truth for "what's been done." Each step (downloaded / transcribed / analyzed) recorded with a timestamp.
- Re-running the pipeline on the same episode is a no-op until the relevant status field is missing or stale.
- yt-dlp gets `--download-archive <podcast>/.archive` so it never re-downloads; on resume it picks up exactly where it stopped.
- Each step writes to a `.tmp` file and atomically renames. A crash mid-write leaves no half-files.

### 7.2 Failure handling per step

| Step | Failure mode | Behavior |
| --- | --- | --- |
| Download | Private video, geo-block, removed | Record `status: download_failed` + error msg in `collected.md`; skip. Don't block playlist. |
| Transcription | CUDA OOM, model load error | Episode stays in queue with `status: download_complete`; cron retries next run. After 3 fails: park as `status: transcription_failed` for manual review. |
| Analysis | Opus rate limit, parse error on Entities | Analysis file persists, queue entry stays, `collected.md` not advanced. Rerun `/analyze-podcast` skips successful steps and retries failed one. |
| Wiki update | SCHEMA.md missing, malformed parse | Analysis preserved on disk; slash command surfaces error to user to resolve manually. |

### 7.3 Concurrency

- Default: **single transcription worker, single device.** Auto-detects CUDA → MPS → CPU. No locks, no parallelism.
- Optional `--workers N` flag for power users with multiple CUDA devices. Documented as "experimental." Each worker takes a `gpu_lock_<id>.lock` file before claiming a GPU.
- Downloads always serial (yt-dlp doesn't benefit from parallelism here; YouTube rate-limit risk).
- Analysis intrinsically serial (single Claude Code session).

### 7.4 Logging & observability

- Every pipeline run writes `logs/pipeline-YYYY-MM-DD.jsonl`: one JSON line per step (episode_id, step name, duration, status, error).
- `collected.md` doubles as the human-readable dashboard — open in Obsidian for at-a-glance status.
- Each vault's `log.md` tracks every analyze action with files touched.

### 7.5 Testing strategy

- **Unit tests (cheap, mocked):** ledger atomic ops, config parsing, `::` parser for Entities/Concepts, queue FIFO behavior, filename sanitization.
- **Integration tests (one real run, opt-in):** ~30s public-domain audio fixture in `tests/fixtures/`, real yt-dlp against a single test playlist URL with one episode, real sherpa-onnx transcription, validates file paths and ledger updates. Skipped by default in CI; runnable locally with `pytest -m integration`.
- **No LLM tests by default.** Slash command's analysis behavior is verified by user reviewing first few real outputs and tuning the lens. Locking down LLM behavior in tests is high-cost / low-value at this stage.

### 7.6 Pre-flight checks (first run)

- yt-dlp installed + version
- sherpa-onnx Python package + ONNX models present (download to `~/.cache/sherpa-onnx/` if missing — large files, multi-GB)
- Each configured vault path exists or created with full skeleton (`SCHEMA.md` / `index.md` / `log.md` / dirs)
- Device (CUDA / MPS / CPU) verified

### 7.7 Explicit non-features

- No web UI / TUI / dashboard.
- No email / Slack / push notifications.
- No "redo analysis" button — to redo, delete the analysis file, clear the `analyzed_at` field in `collected.md`, requeue.

---

## 8. OSS considerations

- **License:** MIT.
- **Personal config gitignored:** `podcasts.yaml`, `collected.md`, `analysis_queue.md`, `logs/`, `podcasts/` (the corpus). Repo ships only `podcasts.yaml.example`.
- **Repo is the tooling, not the corpus.** No transcripts/analyses ever committed.
- **Defaults aimed at the median user:** `whisper-base` STT (works on CPU, light on GPU), single device, single worker. Heavy models (`whisper-medium`, `whisper-large-v3`) documented as upgrades.
- **README as primary onboarding surface** (see §9). User flagged this as critical.
- **Use-responsibly callout in README:** yt-dlp may violate YouTube ToS depending on jurisdiction; transcripts of copyrighted podcasts shouldn't be redistributed; pyannote model has an academic license requiring HuggingFace token + acceptance. Point to upstream tools' guidance.
- **Slash command ships in repo:** `.claude/commands/analyze-podcast.md` is committed. Anyone who clones gets the command in Claude Code automatically.

---

## 9. README outline

The README is the primary onboarding surface. Structure:

1. **What it is** — one paragraph + one diagram of the two-tier flow.
2. **Why** — the Karpathy LLM Wiki vision applied to podcasts; compounding personal knowledge base instead of one-off summaries.
3. **Quickstart**
   - Prerequisites (Python 3.11+, ffmpeg, optional CUDA, Claude Code, Obsidian).
   - `git clone` → `pip install -e .` → copy `podcasts.yaml.example` → `podcasts.yaml`, edit.
   - HuggingFace token setup for pyannote (one-line CLI).
   - First run: `python -m podcast_llm ingest --limit 1` (smoke test on one episode).
4. **Configuration reference** — every key in `podcasts.yaml` documented with defaults.
5. **The `/analyze-podcast` slash command**
   - How it works in Claude Code.
   - Args (`[N]`, `[--match <substring>]`).
   - Per-playlist lens — how to write a good one + the four examples.
6. **Wiki structure & schema** — link to `wiki-schema-template.md`; brief Karpathy-style explanation.
7. **Operations**
   - Cron setup example.
   - Multi-GPU users: `--workers N` caveats.
   - Recovering from failures (transcription_failed retries, redo analysis steps).
8. **Roadmap / non-goals** — explicit so contributors don't propose features that have already been ruled out.
9. **License & responsibility** — MIT + use-responsibly callout.

---

## 10. Open questions / future work

- **`/lint-vault` slash command** — port the lint operation from the llm-wiki SKILL when wikis grow large enough to need it.
- **Cross-vault meta-vault** — only build if recurring need surfaces.
- **Non-YouTube ingest** — RSS, Spotify (via downloader plugins) deferred until requested.
- **Analysis prompt iteration** — v0 in §6 will be tuned after first 2–3 real runs; expect a v1 update with explicit examples per lens after dogfooding.
- **Episode "promote first mention to entity page" retroactive linking** — the threshold rule (§5.4) requires going back to the first-mention episode and replacing inline reference with a wikilink. Implementation must preserve original analysis text; only the episode page representation changes.

---

## 11. Sequencing for implementation

The implementation plan (next phase, via `superpowers:writing-plans`) should sequence roughly as:

1. Repo skeleton + config loader + ledger (no LLM, no audio — easy to test).
2. Downloader (real yt-dlp; real but tiny test playlist).
3. Transcriber (sherpa-onnx, no diarization first; add diarization second).
4. Pipeline orchestrator + CLI.
5. Wiki schema template + first vault skeleton creation logic.
6. Slash command: minimal version (analysis only, no wiki writes).
7. Analysis section parser (`::` format) + wiki update logic.
8. README + LICENSE + `podcasts.yaml.example`.
9. Integration test harness + fixture audio.
10. Polish, error messages, pre-flight checks.

---

## 12. References

- Karpathy LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Hermes llm-wiki SKILL (inspiration; not a runtime dependency): `~/.hermes/hermes-agent/skills/research/llm-wiki/SKILL.md`
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx
- pyannote (diarization): https://github.com/pyannote/pyannote-audio
