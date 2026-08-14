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
