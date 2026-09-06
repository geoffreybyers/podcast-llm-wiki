#!/usr/bin/env bash
#
# Run the remaining /streams backlogs after the Gary Vee job finishes.
#
# Sequential by design: two concurrent transcription jobs would put both GPUs
# under sustained load, and GPU1 already reaches 85C with hardware thermal
# throttle events on a single job.
#
# Counts are exact, not generous. Each creator's run count equals its new-item
# count so a run cannot spill into a backlog nobody asked for -- Peterson in
# particular has 801 un-ingested /videos entries sitting behind its 17 streams.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

WAIT_PID="${1:-}"
if [ -n "$WAIT_PID" ]; then
    echo "[$(date +%H:%M:%S)] waiting for pid $WAIT_PID (Gary Vee) to finish"
    while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 60; done
    echo "[$(date +%H:%M:%S)] Gary Vee driver exited"
fi

# Gary Vee tops up first: its driver was launched for 950 runs before the
# /streams tab was attached, leaving 985 total items.
run() {
    echo "[$(date +%H:%M:%S)] === $1 ($2 runs)"
    scripts/backfill.sh "$1" "$2" 2>&1 | sed 's/^/    /'
}
run "Gary Vee"          60
run "Ali Abdaal"         9
run "Alex Hormozi"      11
run "Jordan B Peterson" 17
echo "[$(date +%H:%M:%S)] chain complete"
