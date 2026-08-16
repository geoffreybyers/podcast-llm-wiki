# podcast-llm-wiki

Ingest YouTube creator playlists, transcribe locally with diarization, and
compound the results into a per-creator [Karpathy-style LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
inside an Obsidian vault.

![Obsidian graph view of a vault after several Huberman Lab episodes — episodes, entities, and concepts emerge as interlinked nodes.](docs/images/vault-graph.png)

## What it is

```
┌──────────── TIER 1: AUTOMATED (cron-able, no LLM) ────────────┐
│  yt-dlp ──► audio ──► faster-whisper + pyannote ──► diarized .md │
│                                                                │
│  Output: transcription + collected.md + analysis_queue.md      │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──── TIER 2: HUMAN-IN-LOOP (Claude Code session) ──────────────┐
│  /analyze-creator → structured analysis + Obsidian vault      │
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
creators: each episode you ingest enriches the vault, surfaces contradictions
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
git clone https://github.com/geoffreybyers/podcast-llm-wiki.git
cd podcast-llm-wiki
pip install -e ".[dev]"

# NVIDIA GPU only — pins the CUDA 12 torch stack (see below).
pip install -r requirements-cuda.txt

cp creators.yaml.example creators.yaml
# edit creators.yaml with your playlists
```

**If you transcribe on an NVIDIA GPU, do not skip `requirements-cuda.txt`.**
faster-whisper runs on `ctranslate2`, which is built against CUDA 12 and loads
`libcublas.so.12` on its first encode. Plain `pip install torch` now resolves to
a cu130 wheel shipping `libcublas.so.13`. The mismatch is invisible at import
and at model load — the model constructs fine — and only surfaces once a real
transcription starts, after the episode has already downloaded:

```
RuntimeError: Library libcublas.so.12 is not found or cannot be loaded
```

The pinned wheels are the same versions pip picks by default, rebuilt against
CUDA 12.6. Nothing is downgraded. Delete the file once ctranslate2 ships a
CUDA 13 build.

### HuggingFace access (only if you enable diarization)

Skip this section if you're running with `diarization: false` — transcription
with faster-whisper does not need a HuggingFace token.

The pyannote diarization pipeline loads **three** separate gated repositories.
You must accept the license on each (same HF account). Metadata fetches
succeed the instant you click "Accept"; actual weight downloads unlock a few
seconds later.

1. Create an account at https://huggingface.co/.
2. Accept the license on each of these (follow the link, click "Agree and
   access"; fill the contact form if shown):
   - https://huggingface.co/pyannote/speaker-diarization-3.1 — the pipeline
   - https://huggingface.co/pyannote/segmentation-3.0 — segmentation backbone
   - https://huggingface.co/pyannote/speaker-diarization-community-1 —
     speaker embedding + PLDA weights
3. Generate a read-scope token at https://huggingface.co/settings/tokens.
4. Put it in a `.env` file at the repo root:

   ```bash
   cp .env.example .env
   # then edit .env and paste your token after HF_TOKEN=
   ```

   `.env` is gitignored. `podcast-llm-wiki` loads it automatically on startup, so
   the same file works from an interactive shell and from cron.

Why three? pyannote's `speaker-diarization-3.1` pipeline delegates to a
separate segmentation model and a separate embedding/PLDA model; each is a
distinct HF repo with its own license prompt. If you skip any, the pipeline
crashes with `GatedRepoError` on first use.

### First run (smoke test on one episode)

```bash
python -m podcast_llm_wiki ingest --limit 1 --creator "Your Creator Name"
```

`--limit 1` caps each creator at one new episode per run. Combined with
`--creator` (which scopes the run to a single entry from `creators.yaml`),
this downloads exactly one episode, transcribes it (slow on CPU; ~real-time
on a modest GPU), and adds it to `collected.md` and `analysis_queue.md`.

### Analyze in Claude Code

```bash
cd /path/to/podcast-llm-wiki
claude  # opens Claude Code in the project directory
```

Then in the Claude Code session:

```
/analyze-creator
```

The first time you run this for a creator, it creates the Obsidian vault
under `~/obsidian/<Creator Name>/`. Open that directory in Obsidian to
browse the wiki.

## Configuration reference

See `creators.yaml.example` for the annotated schema. Top-level structure:

```yaml
defaults:
  vault_root: ~/obsidian       # where vaults are created
  max_backfill: 20             # episodes to backfill on first run
  stt_model: small.en          # faster-whisper model
  diarization: true            # pyannote diarization on/off
  diarization_segmentation: pyannote-segmentation-3.0
  diarization_embedding: 3d-speaker

creators:
  - name: "Display Name"
    source_url: "https://www.youtube.com/playlist?list=..."
    vault_path: ~/custom/path  # optional; defaults to vault_root/name
    initial_prompt: "..."      # optional; see below
    lens: |
      Multi-line analytical lens guiding the /analyze-creator prompt.
    # Any default may be overridden per-creator.
```

### `initial_prompt` — fixing unpunctuated openings

Whisper occasionally locks into unpunctuated, all-lowercase output at an
episode's cold open and stays that way for several minutes before recovering.
It inherits style from its conditioning context, and at the very start there
isn't any.

Setting `initial_prompt` to the show's scripted intro fixes it. Measured on a
Huberman Lab episode, in punctuation marks per 100 words over the first six
minutes:

| `initial_prompt` | opening | rest of episode |
| --- | --- | --- |
| unset | 0 | 15 |
| a generic punctuated sentence | 1 | 14 |
| the show's real intro text | **15** | 15 |

The prompt works by supplying correct *preceding context*, not by demonstrating
punctuation — so it must closely match what the episode actually opens with.
A generic sentence does nothing. This is why there's no global default: use the
show's boilerplate intro, which is stable across episodes.

(`condition_on_previous_text=False` also fixes the opening, at 10, but drops the
body to 10 as well. The prompt is the better trade, so the pipeline keeps
conditioning on.)

## The `/analyze-creator` slash command

When run in Claude Code at the project root:

- `/analyze-creator` — pop and analyze the next queued transcription (1 episode).
- `/analyze-creator 5` — analyze the next 5.
- `/analyze-creator --match huberman-sleep` — find a queued transcription
  whose filename matches `huberman-sleep` and analyze it.

The slash command:

1. Reads the per-creator lens from `creators.yaml`.
2. Generates a structured analysis (TL;DR, Key Insights, Critical Pass with
   1–3 steelmans, strict-format Entities/Concepts, Follow-ups).
3. Writes the analysis file to `creators/<creator>/analyses/`.
4. Updates the Obsidian vault: copies the transcription to `raw/transcripts/`,
   writes the episode page, upserts entity/concept pages, updates `index.md`
   and `log.md`.
5. Marks the episode `analyzed` in `collected.md` and removes it from the queue.

### Writing a good lens

The lens is a free-text fragment prepended to the analysis prompt. It should
say:

- The dominant frame for insights (e.g. "biological mechanisms with evidence quality").
- What's signal vs. noise for this creator (e.g. "panel disagreements ARE the signal").
- Per-creator extraction rules (e.g. "for guests, capture formative experiences").

See `creators.yaml.example` for a generic starting point. Iterate based on
the first 2–3 analyses.

## Wiki structure

Each creator gets its own Obsidian vault following the Karpathy LLM Wiki
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
0 * * * * cd /path/to/podcast-llm-wiki && /usr/bin/python -m podcast_llm_wiki ingest >> logs/cron.log 2>&1
```

### Multi-GPU hosts

If your box has multiple GPUs, **set `CUDA_DEVICE_ORDER=PCI_BUS_ID`** in your
shell rc or service unit file. CUDA's default is `FASTEST_FIRST`, which can
reorder devices so that `CUDA_VISIBLE_DEVICES=2` does not land on the card
`nvidia-smi` calls "GPU 2". Setting `PCI_BUS_ID` aligns CUDA enumeration
with `nvidia-smi`, which is what you almost always want.

```bash
# ~/.zshrc or ~/.bashrc
export CUDA_DEVICE_ORDER=PCI_BUS_ID
```

Multi-worker parallelism (`--workers N` with per-GPU locks) is planned but not
yet implemented. Current runtime is single-worker. Track progress in the
roadmap below.

### Avoiding YouTube rate limits

Sustained back-to-back downloads from one IP draw `HTTP Error 403: Forbidden`.
In practice this showed up roughly 9–10 episodes into consecutive batches.

By default the pipeline sleeps a random 60–300 seconds before each download,
which breaks up the request pattern:

```bash
--sleep-interval 60 --max-sleep-interval 300   # defaults
--sleep-interval 0  --max-sleep-interval 0     # disable
```

This is a real wall-clock cost: at the defaults a 30-episode backfill spends
roughly 90 minutes sleeping, on top of download and transcription time. For a
large backfill that's usually the right trade — a 403 costs a retry anyway, and
the ledger makes resuming cheap. For a one-episode smoke test, pass `0`.

Sleeping applies to downloads only; playlist enumeration is a single request.

If 403s persist, `--cookies-from-browser` sends a logged-in session:

```bash
--cookies-from-browser firefox
--cookies-from-browser "firefox:/path/to/Xyz.Profile 4"   # non-default profile
```

Pass a PROFILE when the browser's default profile isn't the one signed in to
YouTube — otherwise yt-dlp silently falls back to it and the run stays
anonymous. Note that cookies tie bulk downloads to that Google account, which
carries a real risk of the account being flagged; a throwaway account avoids
putting a real one at stake.

### Recovering from failures

- `download_failed`: the row in `collected.md` records the error. Re-running
  the pipeline will retry on the next ingest.
- `transcription_failed`: same — re-runs retry up to 3 times before parking
  the episode for manual review.
- Re-do an analysis: delete the analysis file, clear the `analyzed_at` field
  in `collected.md` for that row, re-add the transcription path to
  `analysis_queue.md`, then `/analyze-creator`.

## Roadmap / non-goals

**Planned but not built yet:**
- `/lint-vault` slash command (orphan pages, broken wikilinks, etc.)
- Cross-vault meta-vault for cross-creator synthesis

**Explicit non-goals:**
- Web UI / TUI / dashboard. `collected.md` opened in Obsidian is the dashboard.
- Email / Slack / push notifications.
- Real-time / live transcription.
- Non-YouTube ingestion (RSS, Spotify, Apple).

## License & responsibility

MIT. See `LICENSE`.

**Use responsibly:** `yt-dlp` may violate YouTube's ToS depending on
jurisdiction. Transcripts of copyrighted creator content are for personal use
only; do not redistribute. The `pyannote/speaker-diarization-3.1` model has an
academic license requiring HuggingFace acceptance.
