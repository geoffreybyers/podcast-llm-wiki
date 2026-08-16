# Podcast → Creator: rename and multi-creator ingest

**Date:** 2026-08-16
**Status:** Approved

## Problem

The project models everything as a "podcast", but the sources we now want are
YouTube creators who publish long-form video without a podcast format. The
vocabulary is wrong in config, CLI, on-disk layout, ledger, and vault. Separately
`playlist_url` is a misnomer: the new sources are channel URLs.

Four creators to add:

| creator | source | videos | median length |
| --- | --- | --- | --- |
| Ali Abdaal | `https://www.youtube.com/@aliabdaal/videos` | 684 | 25m |
| Dan Koe | `https://www.youtube.com/@DanKoeTalks/videos` | 163 | 31m |
| Alex Hormozi | `https://www.youtube.com/@AlexHormozi/videos` | 515 | 26m |
| Gary Vee | `https://www.youtube.com/@garyvee/videos` | 3097 | 34m |

Totals measured 2026-08-16 via `yt-dlp --flat-playlist`; lengths are from the
100 most recent uploads of each channel.

## Scope decision

Ingesting all 4459 videos would need roughly 960GB of retained audio against
528GB free, and about 50 days of GPU time at the measured Huberman rate
(~215MB and ~17min of wall clock per episode). We are therefore **not** doing a
mass ingest.

**Dan Koe only (163 videos), taken end-to-end through ingest _and_ analysis**,
before committing to the other three. He is the smallest catalogue and the
cheapest way to validate the rename and — more importantly — the analysis path,
which has never been run: 380 Huberman transcripts exist and zero have been
analyzed.

All four creators are registered in config now, because that was the ask. Only
Dan Koe is ingested.

## Sequencing

Strictly ordered; step 2 must not overlap step 1.

1. Current Huberman backfill finishes (in flight, 39 episodes remaining).
2. Rename + data migration, committed with tests.
3. Register all four creators; ingest Dan Koe only.
4. Run Dan Koe through analysis end-to-end.
5. Decide on Ali Abdaal / Hormozi / Gary Vee with that evidence in hand.

## Rename: user-facing surface only

| from | to |
| --- | --- |
| `podcasts.yaml` | `creators.yaml` |
| `--podcast` | `--creator` |
| `podcasts/` tree | `creators/` |
| ledger column `podcast` | `creator` |
| vault `Podcast - Huberman Lab` | `Creator - Huberman Lab` |
| `/ingest-podcast`, `/analyze-podcast` | `/ingest-creator`, `/analyze-creator` |
| agents `podcast-ingester`, `podcast-analyzer` | `creator-ingester`, `creator-analyzer` |

The Python package stays `podcast_llm_wiki`, and internal identifiers
(`PodcastConfig`, `pod`, `enumerate_playlist`) keep their names. Renaming them
churns every import and the whole test suite for a name no user ever sees. This
is a deliberate, documented inconsistency, not an oversight.

The on-disk tree root is hardcoded in three places — `cli.py:126`,
`pipeline.py:142`, `pipeline.py:173` — and the config loader keys off
`podcasts` in `config.py:74`.

## Config schema

- `podcasts:` → `creators:`
- `playlist_url` → `source_url`

`enumerate_playlist()` passes its argument straight to `ydl.extract_info()`,
which accepts `@handle/videos` URLs unchanged, so no download-path code changes.
Verified against all four channels on 2026-08-16.

`lens`, `vault_path`, `initial_prompt`, and the `defaults:` block are unchanged.

## Migration

One idempotent script, run only when nothing is ingesting:

1. `podcasts.yaml` → `creators.yaml` (and the `.example`)
2. `podcasts/` → `creators/`
3. `collected.md`: header cell `podcast` → `creator`
4. `analysis_queue.md`: rewrite every path prefix `podcasts/` → `creators/`
5. vault dir `Podcast - Huberman Lab` → `Creator - Huberman Lab`
6. `creators.yaml`: update Huberman's `vault_path`

The two rewrites (3, 4) get unit tests. After the moves, a post-check asserts
ledger rows, transcription files, and queue entries still agree — the same
three-way consistency check used throughout the backfill.

Rollback is `git checkout` for tracked files plus two `mv`s; no data is deleted.

## Lenses

All four are written to the same brief — **actionable playbooks**:

> Extract tactics and systems with their preconditions, sequencing, and any
> concrete numbers (pricing, cadence, team size, time budgets). Flag where advice
> assumes an audience size, capital base, or track record the reader may not
> have.

This mirrors the Huberman lens's demand for specificity (dosage, timing,
duration) without importing its science-evidence framing, which does not fit
business and creator advice.

## Testing

- New: config schema accepts `creators:` / `source_url`.
- New: ledger header rewrite; queue path rewrite.
- Updated: the existing 140 tests, for renamed flags and paths.

No behaviour changes to download, transcribe, or ledger logic — this is a rename
plus config, and the test suite should prove exactly that.

## Explicitly not building

- **`min_duration_sec` filter.** Dan Koe has zero videos under five minutes in
  the sample. Add it when Gary Vee's ~9% of short uploads actually matters.
- **Audio cleanup after transcription.** 163 episodes is ~35GB against 528GB
  free. This becomes necessary only if the large catalogues are approved, and it
  is the single biggest lever if they are.
- **Renaming the Python package.** See above.
