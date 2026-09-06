#!/usr/bin/env bash
#
# Run a backfill under a hard thermal ceiling.
#
#   scripts/thermal_guard.sh "Gary Vee" 800 [limit_c]
#
# GPU1 reached 86C on 2026-09-02 with hardware thermal slowdown active for 42
# minutes. The cards are liquid cooled, so that temperature means the loop is
# not rejecting heat, not that a fan died. Until that is resolved, no run is
# allowed to climb: at LIMIT the whole job is torn down immediately.
#
# Polls every 5s rather than every minute because the ramp from idle to 80C
# took only a few minutes under load -- a slow poll would overshoot the ceiling
# before noticing it.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

CREATOR="${1:?usage: thermal_guard.sh <creator> [count] [limit_c]}"
COUNT="${2:-800}"
LIMIT="${3:-75}"
POLL="${POLL_SECS:-5}"

# A trip needs this many *consecutive* over-limit readings. On 2026-09-04 a
# single bad nvidia-smi sample reported 75C while GPU1 idled at 39C drawing
# 6.6W, and that one reading ended an 800-run job at run 754 after 29 hours.
# Real heat holds across polls; a bad sample does not. Two readings 5s apart
# still stop a genuine climb well inside the ramp that took minutes to reach
# 80C, so this costs nothing in protection.
STRIKES="${THERMAL_STRIKES:-2}"

stamp() { date +%H:%M:%S; }
log="logs/backfill-guarded-$(date +%Y%m%d-%H%M%S).log"

# How long the whole process group gets to exit on TERM before it is killed.
GRACE="${TEARDOWN_GRACE_SECS:-5}"

echo "[$(stamp)] starting $CREATOR ($COUNT runs), thermal ceiling ${LIMIT}C, poll ${POLL}s"
# setsid puts the driver in its own process group, so teardown can signal the
# driver and every run it spawned in one call. Without that the driver had to be
# hunted by pid while it was still free to start the next run.
setsid scripts/backfill.sh "$CREATOR" "$COUNT" > "$log" 2>&1 &
BF=$!
PGID="$(ps -o pgid= -p "$BF" 2>/dev/null | tr -d ' ')"
echo "[$(stamp)] driver pid $BF (pgid ${PGID:-unknown}) -> $log"

peak=0
over=0
teardown() {
    reason="$1"
    echo "[$(stamp)] $reason -- tearing down"
    # The whole group at once: the driver dies with its runs, so there is no
    # interval in which it is alive and free to launch a successor. The old
    # teardown polled for up to 20s before escalating, and a run started 14s
    # into that window on 2026-09-04.
    if [ -n "$PGID" ] && [ "$PGID" != "$$" ]; then
        kill -TERM "-$PGID" 2>/dev/null
        for _ in $(seq 1 "$GRACE"); do
            kill -0 "-$PGID" 2>/dev/null || break
            sleep 1
        done
        # A wedged CUDA or pyannote call will not unwind on TERM alone.
        kill -KILL "-$PGID" 2>/dev/null
    else
        # No process group to work with; fall back to the driver's own tree.
        echo "[$(stamp)] WARNING: no pgid for driver $BF, falling back to pid kill"
        pkill -TERM -P "$BF" 2>/dev/null
        kill -KILL "$BF" 2>/dev/null
    fi
    echo "[$(stamp)] stopped. peak observed ${peak}C"
}

while kill -0 "$BF" 2>/dev/null; do
    t=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | sort -rn | head -1)
    case "$t" in ''|*[!0-9]*) sleep "$POLL"; continue;; esac
    [ "$t" -gt "$peak" ] && peak="$t"
    if [ "$t" -ge "$LIMIT" ]; then
        over=$((over + 1))
        if [ "$over" -lt "$STRIKES" ]; then
            echo "[$(stamp)] over limit (${t}C >= ${LIMIT}C) reading ${over}/${STRIKES} -- confirming"
            sleep "$POLL"
            continue
        fi
        echo "[$(stamp)] THERMAL STOP: GPU hit ${t}C (limit ${LIMIT}C) on ${over} consecutive readings"
        teardown "thermal limit reached"
        echo "[$(stamp)] THERMAL_STOP_${t}C"
        exit 3
    fi
    # One healthy reading clears the count: only an unbroken run trips.
    over=0
    sleep "$POLL"
done
echo "[$(stamp)] driver finished on its own. peak observed ${peak}C"
echo "[$(stamp)] GUARD_DONE_PEAK_${peak}C"
