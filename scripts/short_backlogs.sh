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
# Ceiling defaults to 80C rather than the guard's own 75C: the 2026-09-05 Gary
# Vee run peaked at 74C with zero thermal-throttle samples, so 75C left one
# degree of margin and would stop a long job over nothing.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
CEILING="${CEILING:-80}"

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
