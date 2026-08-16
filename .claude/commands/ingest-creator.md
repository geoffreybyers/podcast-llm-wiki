---
description: Ingest N episodes of a creator. If the creator isn't in creators.yaml yet, give it a YouTube URL and the command registers it (yaml entry, vault skeleton) before ingesting. Dispatches the `creator-ingester` subagent to keep faster-whisper / yt-dlp output out of the main context.
---

# /ingest-creator

You are a **thin orchestrator**. The actual ingest work — running the CLI, watching it finish, parsing the ledger — lives in the `creator-ingester` subagent. Your job is to resolve the target (and register a new creator if needed) and then dispatch.

## Arguments

Parse the user's message (appended after the slash command) for:

- `<creator-name>` — **required**. Matched **exact, case-sensitive** against `creators[].name` in `creators.yaml`. If the user gave the name with different casing than what's in the yaml, correct to the yaml's casing before proceeding. If no name at all is given, STOP and ask the user which creator.
- `[N]` — number of episodes to ingest this run. Default `1`.
- `--url <youtube-url>` — required only when the creator name is not already in `creators.yaml`. Accepts any URL yt-dlp accepts (playlist, `/@handle`, `/channel/`, single video).

## Procedure

### 1. Resolve target

Read `creators.yaml`. Walk `creators[].name`.

- **Exists:** go to step 3.
- **Missing, no `--url`:** STOP. Tell the user: `"'<name>' is not in creators.yaml — re-run with --url <youtube-url> to register it."` Do not invent a URL. Do not guess at a close-match existing creator — ask.
- **Missing, `--url` given:** go to step 2.

### 2. Register new creator

**a. Elicit a lens.** Ask the user in plain prose: `"One-paragraph analytical lens for <name>? (Or say 'generic' and I'll use a default.)"` Wait for their reply.
- If they paste a lens: use it verbatim.
- If they say `"generic"` (or similar): use this default:
  ```
  Frame insights as actionable lessons relevant to this creator's domain.
  Identify recurring themes and contradictions with prior episodes.
  Note when claims are well-supported vs. speculative.
  ```

**b. URL sanity check.** Confirm the URL starts with `http` and contains `youtube.com` or `youtu.be`. If it doesn't, surface the URL back to the user and ask them to confirm before proceeding.

**c. Append an entry to `creators.yaml`.** Use a templated block, appended at the end of the file. This preserves existing comments and formatting (no yaml round-trip).

Template (note the indentation — `lens:` is 4 spaces in; the lens body is 8 spaces in, under the `|` block scalar):

```
  - name: "<Name>"
    source_url: "<URL>"
    vault_path: "~/obsidian/Creator - <Name>"
    lens: |
        <lens line 1>
        <lens line 2>
```

Append with a leading blank line so the new entry is separated from the previous one. Use the `Edit` tool to append before the file's trailing newline, or re-`Write` the full file if simpler.

**d. Post-append validation.** Run the config loader against the new file:

```bash
.venv/bin/python -c "from pathlib import Path; from podcast_llm_wiki.config import load_config; load_config(Path('creators.yaml')); print('ok')"
```

If this prints anything other than `ok` (i.e. it raises), **revert the append** (restore the file's prior state) and report the parse error to the user. Do not proceed to step 3.

No other setup is needed. The ingest CLI's preflight will create the vault skeleton (`SCHEMA.md`, `index.md`, `log.md`, subdirs) on first run, and the downloader/transcriber create `creators/<name>/downloads/` and `transcriptions/` when they first write.

### 3. Dispatch the subagent

```
Agent(
  subagent_type="creator-ingester",
  description="Ingest <N> episodes of <name>",
  prompt="""
creator_name: <Name>
limit: <N>

Run the full ingest procedure. Return only the summary block.
""",
)
```

One subagent call, one creator. Wait for it to finish.

### 4. Report

Relay the subagent's summary to the user verbatim (it's already shaped for this). If the subagent reports zero new episodes, say `"up to date"`.

If this was a new-creator registration, prepend one line: `"Registered '<name>' in creators.yaml."`

## Hard rules

- Do NOT run the ingest CLI from the orchestrator. That's the subagent's job — keeps yt-dlp / faster-whisper stdout out of the main context.
- Do NOT append to `creators.yaml` unless the user gave `--url` AND the name isn't already present. Never silently rename or merge.
- Do NOT proceed past step 2d if the post-append `load_config` check fails. Revert, report, stop.
- Do NOT guess a lens — ask. Only use the generic default when the user says so.
- Do NOT pass `--skip-preflight` to the CLI. Preflight is what creates the vault skeleton for newly-registered creators.
