"""Behaviour tests for scripts/thermal_guard.sh.

The guard exists because GPU1 reached 86C on 2026-09-02 with hardware thermal
slowdown active for 42 minutes -- on a liquid loop, that means heat is not being
rejected. Any run that climbs must be torn down.

On 2026-09-04 the guard fired at 75C and killed an 800-run job at run 754. The
trip was a false positive: a single bad nvidia-smi sample, taken while GPU1 was
idling at 39C drawing 6.6W. One bad reading must not cost a 29-hour job, so a
trip now requires consecutive confirmation -- while a real climb, which holds
temperature across polls, still stops the job immediately.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "thermal_guard.sh"
# Generous for a working script, short enough that a regression fails the suite
# instead of wedging it.
HARD_CAP_SEC = 90


def _fake_nvidia_smi(tmp_path: Path, temps: list[int]) -> Path:
    """An nvidia-smi stand-in returning `temps`, one reading per invocation.

    Readings past the end repeat the final value, so a sequence only has to
    spell out the part under test.
    """
    seq = tmp_path / "temps.txt"
    seq.write_text("".join(f"{t}\n" for t in temps))
    counter = tmp_path / "count.txt"

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    p = bin_dir / "nvidia-smi"
    p.write_text(
        "#!/usr/bin/env bash\n"
        f'n=$(cat "{counter}" 2>/dev/null || echo 0)\n'
        "n=$((n + 1))\n"
        f'echo "$n" > "{counter}"\n'
        f'line=$(sed -n "${{n}}p" "{seq}")\n'
        f'[ -n "$line" ] || line=$(tail -n 1 "{seq}")\n'
        'echo "$line"\n'
    )
    p.chmod(0o755)
    return bin_dir


def _fake_cli(tmp_path: Path, body: str) -> Path:
    """A stand-in for `python -m podcast_llm_wiki ingest`."""
    p = tmp_path / "fake_ingest"
    p.write_text("#!/usr/bin/env bash\n" + body)
    p.chmod(0o755)
    return p


# Lives long enough for the guard to take several temperature samples, and keeps
# writing so backfill.sh's own stall guard stays out of the way.
CHATTY = 'for i in $(seq 1 10); do echo "tick $i"; sleep 1; done\n'


def _run_guard(tmp_path: Path, temps: list[int], limit: int = 75, body: str = CHATTY):
    bin_dir = _fake_nvidia_smi(tmp_path, temps)
    env = dict(os.environ)
    env.update(
        PATH=f"{bin_dir}:{env['PATH']}",
        PYTHON=str(_fake_cli(tmp_path, body)),
        POLL_SECS="1",
        STALL_SECS="600",
        KILL_GRACE_SECS="1",
    )
    try:
        return subprocess.run(
            [str(SCRIPT), "Huberman Lab", "1", str(limit)],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=HARD_CAP_SEC,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"thermal_guard.sh did not finish within {HARD_CAP_SEC}s")


@pytest.fixture
def clean_logs():
    logs = REPO / "logs"
    before = set(logs.glob("*")) if logs.exists() else set()
    yield
    for f in set(logs.glob("*")) - before:
        f.unlink()


class TestFalsePositiveTrips:
    def test_single_spike_does_not_stop_the_job(self, tmp_path: Path, clean_logs) -> None:
        """One over-limit reading among healthy ones is a bad sample, not heat.

        This is the 2026-09-04 failure exactly: 75C reported once while the card
        idled at 39C, ending an 800-run job at run 754.
        """
        result = _run_guard(tmp_path, [40, 80, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40])

        assert "THERMAL STOP" not in result.stdout, result.stdout
        assert "GUARD_DONE" in result.stdout, result.stdout

    def test_records_the_spike_as_peak(self, tmp_path: Path, clean_logs) -> None:
        """Not tripping must not mean not noticing.

        The spike still has to surface as the peak on the *completion* path, so
        a card that flirts with the ceiling is visible in the log afterwards.
        """
        result = _run_guard(tmp_path, [40, 80, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40])

        assert "GUARD_DONE_PEAK_80C" in result.stdout, result.stdout


class TestRealClimbs:
    def test_two_consecutive_over_limit_readings_stop_the_job(
        self, tmp_path: Path, clean_logs
    ) -> None:
        """Heat holds across polls; that is what separates it from a bad sample."""
        result = _run_guard(tmp_path, [40, 80, 80])

        assert "THERMAL STOP" in result.stdout, result.stdout
        assert result.returncode == 3, result.stdout


class TestTeardownIsImmediate:
    """A trip must stop the job at once, not eventually.

    The first teardown TERMed the driver and then polled `pgrep` once a second
    for up to 20 seconds before escalating to KILL. The driver stayed alive
    inside that window and kept its loop going: on 2026-09-04 run 129 started
    *14 seconds after* the "thermal stop" line, putting the GPU straight back
    under load while the guard believed it had stopped the job.

    Signalling the driver's whole process group closes the window -- nothing is
    left to spawn a successor.
    """

    # A run that ignores TERM, standing in for a wedged CUDA or pyannote call
    # that will not unwind on a polite signal.
    WEDGED = "trap '' TERM\necho started\nsleep 45\n"

    def _elapsed_between(self, out: str, first: str, second: str) -> int:
        def at(marker: str) -> int:
            line = next(l for l in out.splitlines() if marker in l)
            h, m, s = (int(x) for x in line.split("]")[0].lstrip("[").split(":"))
            return h * 3600 + m * 60 + s

        return at(second) - at(first)

    def test_teardown_completes_promptly(self, tmp_path: Path, clean_logs) -> None:
        result = _run_guard(tmp_path, [40, 80, 80], body=self.WEDGED)

        gap = self._elapsed_between(result.stdout, "tearing down", "stopped.")
        assert gap <= 10, f"teardown took {gap}s, leaving a window to spawn a run:\n{result.stdout}"

    def test_leaves_no_surviving_run(self, tmp_path: Path, clean_logs) -> None:
        """Orphaned GPU processes have shown up after a stop before."""
        result = _run_guard(tmp_path, [40, 80, 80], body=self.WEDGED)

        survivors = subprocess.run(
            ["pgrep", "-f", str(tmp_path / "fake_ingest")],
            capture_output=True, text=True,
        )
        assert survivors.stdout.strip() == "", (
            f"run survived teardown: {survivors.stdout}\n{result.stdout}"
        )
