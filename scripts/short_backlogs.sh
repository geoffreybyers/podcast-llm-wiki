#!/usr/bin/env bash
#
# Finish the four short creator backlogs, sequentially, each under the thermal
# guard.
#
#   scripts/short_backlogs.sh
#
# Sequential by design: two concurrent transcription jobs put both GPUs under
# sustained load, and this box has a history of GPU1 heat problems. One creator
# at a time.
#
# Counts are exact, not generous -- each equals the creator's measured remaining
# count on 2026-09-08, so a run cannot spill into a backlog nobody asked for.
# Jordan B Peterson is deliberately absent: its 820 un-ingested entries are a
# multi-day job and must be started explicitly, not swept up by this chain.
#
# Ceiling stays at the guard's conservative 75C. An 80C ceiling was tried on
# 2026-09-08 and tripped at 81C after 27 minutes, three episodes in. That was a
# real climb, not a bad sample: at an identical power band (190-215W) GPU1 ran
# 71.0C avg / 78C peak that evening against 67.5C / 73C on 2026-09-05, and GPU0
# -- a different card doing only desktop work -- was 5C warmer too. Both cards
# warming at the same load points at ambient or case airflow, not at one card's
# loop. Until that is resolved the equilibrium sits near 78-80C, so no ceiling
# in this range lets a long job run; fix the heat or lower the power cap rather
# than raising this number. Override deliberately with CEILING=... if needed.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
CEILING="${CEILING:-75}"

run() {
    echo "[$(date +%H:%M:%S)] === $1 ($2 runs, ceiling ${CEILING}C)"
    scripts/thermal_guard.sh "$1" "$2" "$CEILING" 2>&1 | sed 's/^/    /'
    rc=${PIPESTATUS[0]}
    if [ "$rc" -eq 3 ]; then
        echo "[$(date +%H:%M:%S)] THERMAL STOP during $1 -- aborting chain"
        exit 3
    fi
}

run "Alex Hormozi" 12
run "Ali Abdaal"   10
run "Huberman Lab"  3
run "Dan Koe"       1
echo "[$(date +%H:%M:%S)] short-backlog chain complete"
