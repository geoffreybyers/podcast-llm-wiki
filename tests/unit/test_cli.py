# tests/unit/test_cli.py
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from podcast_llm.cli import app


def test_ingest_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output.lower()


def test_ingest_command_loads_config(tmp_path: Path, monkeypatch) -> None:
    cfg_path = tmp_path / "podcasts.yaml"
    cfg_path.write_text(
        "defaults:\n"
        f"  vault_root: {tmp_path}/obsidian\n"
        "  max_backfill: 1\n"
        "podcasts:\n"
        "  - name: T\n"
        "    playlist_url: https://x.test\n"
        "    lens: l\n"
    )

    # Spy on Pipeline.ingest_all to avoid real network/model calls.
    called = {}

    def fake_ingest(self) -> None:
        called["yes"] = True

    monkeypatch.setattr("podcast_llm.cli.Pipeline.ingest_all", fake_ingest)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "--config", str(cfg_path),
            "--project-root", str(tmp_path),
            "--skip-preflight",
        ],
    )
    assert result.exit_code == 0, result.output
    assert called.get("yes") is True
