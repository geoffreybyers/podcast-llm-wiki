#!/usr/bin/env bash
# Finish Gary Vee after the streams chain. The original 950-run job ended at
# run 204 when a DNS outage made every source fail and the empty enumeration
# read as "playlist exhausted" (fixed in pipeline._enumerate_sources).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
WAIT_PID="${1:-}"
if [ -n "$WAIT_PID" ]; then
    echo "[$(date +%H:%M:%S)] waiting for chain pid $WAIT_PID"
    while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 60; done
    echo "[$(date +%H:%M:%S)] chain finished"
fi
echo "[$(date +%H:%M:%S)] === Gary Vee remainder (800 runs)"
scripts/backfill.sh "Gary Vee" 800 2>&1 | sed 's/^/    /'
echo "[$(date +%H:%M:%S)] garyvee finish complete"
