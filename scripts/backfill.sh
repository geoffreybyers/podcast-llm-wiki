#!/usr/bin/env bash
#
# Backfill N episodes, one per process.
#
#   scripts/backfill.sh "Huberman Lab" 10 [gap-seconds]
#
# Why one process per episode rather than `ingest --limit N`:
#
# A long-running batch died silently partway through a 20-episode run -- no
# traceback, no ledger row left mid-flight, the log simply stopped. Cause never
# established (dmesg needs root here, so an OOM kill could not be confirmed or
# ruled out). Single-episode runs have not reproduced it. Whatever the cause, a
# fresh short-lived process per episode contains the blast radius: at worst one
# episode is lost, the ledger stays consistent, and the next run picks up where
# this one stopped.
#
# --resume on every iteration makes it self-healing: any row stuck in
# 'downloaded' or 'download_failed' from a previous run gets retried before new
# episodes are fetched. It is a no-op when nothing is stuck.
#
# Downloads run with sleeping disabled -- the gap between processes is the
# pacing. Raise GAP if 403s reappear.

set -uo pipefail

PODCAST="${1:?usage: backfill.sh <podcast-name> [count] [gap-seconds]}"
COUNT="${2:-1}"
GAP="${3:-30}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || { echo "no interpreter at $PY (set PYTHON=...)" >&2; exit 1; }
mkdir -p logs

completed=0
failed=0

for i in $(seq 1 "$COUNT"); do
    log="logs/backfill-$(date +%Y%m%d-%H%M%S).log"
    printf '[%s] run %d/%d -> %s\n' "$(date +%H:%M:%S)" "$i" "$COUNT" "$log"

    "$PY" -m podcast_llm_wiki ingest \
        --resume --limit 1 --podcast "$PODCAST" \
        --sleep-interval 0 --max-sleep-interval 0 > "$log" 2>&1
    rc=$?

    # Count transcriptions rather than test for one: a --resume run legitimately
    # does more than one episode (retry a stuck row, *then* fetch a new one), and
    # testing presence silently undercounts those.
    n=$(grep -c "Processing audio with duration" "$log")
    if [ "$n" -gt 0 ]; then
        completed=$((completed + n))
        grep -o "Processing audio with duration [0-9:.]*" "$log" |
            awk '{printf "    transcribed (%s audio)\n", $5}'
    fi

    if grep -qE "download failed|transcription failed" "$log"; then
        failed=$((failed + 1))
        printf '    FAILURE logged -- will retry on the next run\n'
    fi

    if [ "$rc" -ne 0 ]; then
        printf '    exited rc=%d\n' "$rc"
    fi

    # Playlist exhausted (and nothing was resumed): stop rather than spin.
    if grep -q "new_episodes=0" "$log" && ! grep -q "Processing audio with duration" "$log"; then
        printf '    no new episodes; stopping early\n'
        break
    fi

    [ "$i" -lt "$COUNT" ] && sleep "$GAP"
done

printf '\ndone: %d transcribed, %d failure(s) logged\n' "$completed" "$failed"
printf 'ledger: '
tail -n +3 collected.md | awk -F' \\| ' '{print $7}' | sort | uniq -c | tr '\n' ' '
printf '\n'
