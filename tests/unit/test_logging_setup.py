# tests/unit/test_logging_setup.py
from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path

import pytest

from podcast_llm_wiki.logging_setup import configure_logging


@pytest.fixture(autouse=True)
def _reset_root_logging():
    """Each test gets a clean root logger; restore caller state on teardown."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_capture = logging.raiseExceptions
    for h in saved_handlers:
        root.removeHandler(h)
    try:
        yield
    finally:
        for h in root.handlers[:]:
            root.removeHandler(h)
            h.close()
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)
        logging.captureWarnings(False)
        logging.raiseExceptions = saved_capture


def _read_jsonl(path: Path) -> list[dict]:
    for h in logging.getLogger().handlers:
        h.flush()
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_writes_json_line_for_project_logger(tmp_path: Path) -> None:
    log_path = tmp_path / "pipeline.jsonl"
    configure_logging(log_path)
    logging.getLogger("podcast_llm_wiki.test").info(
        "hello", extra={"episode_id": "vid1", "stage": "download"}
    )

    lines = _read_jsonl(log_path)
    assert len(lines) == 1
    assert lines[0]["msg"] == "hello"
    assert lines[0]["level"] == "INFO"
    assert lines[0]["logger"] == "podcast_llm_wiki.test"
    assert lines[0]["episode_id"] == "vid1"
    assert lines[0]["stage"] == "download"
    assert "ts" in lines[0]


def test_captures_third_party_loggers(tmp_path: Path) -> None:
    """Third-party libs (httpx, faster_whisper) must land in the JSONL file,
    not leak to stderr where they would bypass our formatter."""
    log_path = tmp_path / "pipeline.jsonl"
    configure_logging(log_path)
    logging.getLogger("httpx").info("HTTP Request: HEAD https://example/")
    logging.getLogger("faster_whisper").info("Processing audio with duration 01:35:43.829")

    lines = _read_jsonl(log_path)
    loggers = {line["logger"] for line in lines}
    assert "httpx" in loggers
    assert "faster_whisper" in loggers


def test_captures_warnings_as_structured_records(tmp_path: Path) -> None:
    log_path = tmp_path / "pipeline.jsonl"
    configure_logging(log_path)
    warnings.warn("pyannote reproducibility warning", UserWarning)

    lines = _read_jsonl(log_path)
    assert any(
        line["logger"] == "py.warnings" and "pyannote reproducibility warning" in line["msg"]
        for line in lines
    )


def test_idempotent_on_repeat_call(tmp_path: Path) -> None:
    log_path = tmp_path / "pipeline.jsonl"
    configure_logging(log_path)
    configure_logging(log_path)

    root = logging.getLogger()
    file_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path
    ]
    assert len(file_handlers) == 1


def test_respects_file_level_filter(tmp_path: Path) -> None:
    log_path = tmp_path / "pipeline.jsonl"
    configure_logging(log_path, file_level="WARNING", console_level="INFO")
    log = logging.getLogger("podcast_llm_wiki.test")
    log.info("not in file")
    log.warning("in file")

    lines = _read_jsonl(log_path)
    msgs = [line["msg"] for line in lines]
    assert "in file" in msgs
    assert "not in file" not in msgs
