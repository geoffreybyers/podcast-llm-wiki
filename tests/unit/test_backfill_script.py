"""Behaviour tests for scripts/backfill.sh's stall guard.

The guard exists because one ingest run went silent for 11 hours mid-diarization
and blocked the remaining runs of a 20-episode batch. The first attempt at a fix
used a fixed wall-clock ceiling, which was wrong: `--resume` drains the whole
backlog of stuck rows in a single process, so a healthy run legitimately took
90+ minutes to transcribe five episodes and got killed for it.

Silence -- not duration -- is what distinguishes the pathology. These tests pin
both directions of that distinction.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "backfill.sh"
# Generous enough that a working script always finishes well inside it; short
# enough that a regression (script ignores the stall knobs) fails instead of
# wedging the suite.
HARD_CAP_SEC = 60


def _fake_cli(tmp_path: Path, name: str, body: str) -> Path:
    """A stand-in for `python -m podcast_llm_wiki ingest`."""
    p = tmp_path / name
    p.write_text("#!/usr/bin/env bash\n" + body)
    p.chmod(0o755)
    return p


def _run_backfill(fake: Path, **env_overrides) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        PYTHON=str(fake),
        STALL_SECS="3",
        POLL_SECS="1",
        KILL_GRACE_SECS="1",
    )
    env.update({k: str(v) for k, v in env_overrides.items()})
    try:
        return subprocess.run(
            [str(SCRIPT), "Huberman Lab", "1", "1"],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=HARD_CAP_SEC,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"backfill.sh did not finish within {HARD_CAP_SEC}s -- the stall "
            "guard did not act on STALL_SECS"
        )


@pytest.fixture
def clean_logs():
    """Remove log files the script creates, so tests don't litter logs/."""
    logs = REPO / "logs"
    before = set(logs.glob("*")) if logs.exists() else set()
    yield
    for f in set(logs.glob("*")) - before:
        f.unlink()


def test_kills_a_run_that_goes_silent(tmp_path: Path, clean_logs) -> None:
    """A process producing no output past the stall window is killed."""
    fake = _fake_cli(tmp_path, "hang", "sleep 600\n")

    result = _run_backfill(fake)

    assert "STALL" in result.stdout, result.stdout
    assert "done:" in result.stdout


def test_lets_a_slow_but_writing_run_finish(tmp_path: Path, clean_logs) -> None:
    """A run that keeps logging must survive past the stall window.

    This is the multi-episode `--resume` case a wall-clock ceiling killed.
    """
    fake = _fake_cli(
        tmp_path,
        "chatty",
        "for i in $(seq 1 8); do echo \"Processing audio with duration 01:00.000\"; sleep 1; done\n",
    )

    result = _run_backfill(fake)

    assert "STALL" not in result.stdout, result.stdout
    assert "exited rc=" not in result.stdout, result.stdout


class TestStallAllowanceScalesWithEpisodeLength:
    """A flat 45m silence window is wrong for a 10h51m episode.

    Gary Vee's "How To Master Social Media Marketing" (4pL7AUjgWL4) is 10h51m of
    audio. faster-whisper logs nothing between "Detected language" and the end
    of the transcript, so the run looked silent for far longer than 2700s and
    was killed for it -- three times, on runs 752, 753 and 754. The episode
    stayed queued, so the next run picked the same one and the job made no
    further progress until the guard stopped it.

    Silence is still the right signal; it just has to be measured against how
    much audio the run actually announced. Observed throughput on this box is
    6-7x realtime including download, so a floor of 2x leaves a wide margin
    while still bounding a genuine wedge.
    """

    def test_long_episode_survives_the_flat_window(self, tmp_path: Path, clean_logs) -> None:
        fake = _fake_cli(
            tmp_path,
            "long",
            'echo "Processing audio with duration 10:51:03.092"\nsleep 6\n',
        )

        result = _run_backfill(fake, STALL_SECS=3)

        assert "STALL" not in result.stdout, result.stdout

    def test_short_episode_keeps_the_flat_floor(self, tmp_path: Path, clean_logs) -> None:
        """Scaling must never shorten the window below the configured floor."""
        fake = _fake_cli(
            tmp_path,
            "short",
            'echo "Processing audio with duration 00:04.000"\nsleep 30\n',
        )

        result = _run_backfill(fake, STALL_SECS=3)

        assert "STALL" in result.stdout, result.stdout

    def test_a_wedge_is_still_caught_on_a_long_episode(self, tmp_path: Path, clean_logs) -> None:
        """The allowance is generous, not unbounded -- 11h of silence still dies."""
        fake = _fake_cli(
            tmp_path,
            "wedged",
            'echo "Processing audio with duration 00:20.000"\nsleep 40\n',
        )

        result = _run_backfill(fake, STALL_SECS=3, STALL_SPEED_FLOOR=2)

        assert "STALL" in result.stdout, result.stdout
