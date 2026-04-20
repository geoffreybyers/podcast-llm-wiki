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
