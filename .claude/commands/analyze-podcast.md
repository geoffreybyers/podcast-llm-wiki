---
description: Orchestrates analysis of one or more pending podcast transcriptions. Each episode runs in its own `podcast-analyzer` subagent so the main context window stays clean. Serial execution (no queue/ledger races).
---

# /analyze-podcast

You are a **thin orchestrator**. The actual per-episode work — reading the transcription, generating the analysis, updating the vault, updating the ledger — lives in the `podcast-analyzer` subagent. Your job is to pick targets from the queue and dispatch.

## Arguments

- `[N]` — number of episodes to analyze in this run (default: `1`).
- `[--match <substring>]` — instead of FIFO, pick the first queued transcription whose path contains `<substring>` (case-insensitive). Implies `N=1` unless `N` is also passed (in which case `N` matching entries are chosen from the queue in order).

## Procedure

### 1. Resolve targets

Read `analysis_queue.md`. Each line is a relative transcription path (may have a `- ` prefix — strip it).

- If `--match` given: filter to lines containing `<substring>` (case-insensitive). Take the first `N` (default 1).
- Else: take the first `N` lines.
- If the resulting list is empty: report `"queue empty"` (or `"no match for <substring>"`) and STOP. Do nothing else.

Do NOT read any transcription file in the orchestrator. Just hand the path to the subagent.

### 2. Dispatch subagents serially

For each target path, in order, call the `podcast-analyzer` subagent:

```
Agent(
  subagent_type="podcast-analyzer",
  description="Analyze <short title>",
  prompt="""
transcription_path: <relative path>

Run the full per-episode procedure. Return only the summary block.
""",
)
```

Wait for each subagent to finish before dispatching the next. **Serial, not parallel** — parallel subagents race on `analysis_queue.md` and `collected.md`.

If a subagent returns a failure summary (`✗ …`), STOP. Do not dispatch further subagents. Surface the failure to the user and ask how to proceed.

### 3. Aggregate and report

After all (or until first failure), print one line per episode summarizing the subagent's result:

```
Analyzed N/M episodes:
  ✓ <channel> — <title>  (E entities, C concepts, F files)
  ✓ <channel> — <title>  (E entities, C concepts, F files)
  ✗ <title>  stage=<stage>  error=<one line>
```

Append any contradictions or notes the subagents surfaced (keep it tight — one extra bullet each, not a full dump).

## Hard rules

- Do NOT read transcriptions in the orchestrator. The whole point is to keep the main context clean.
- Do NOT run subagents in parallel — queue/ledger writes will race.
- Do NOT touch `analysis_queue.md`, `collected.md`, or the vault from the orchestrator. That's the subagent's job.
- Do NOT continue past a subagent failure without user confirmation.
