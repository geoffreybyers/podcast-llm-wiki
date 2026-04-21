# tests/unit/test_logging_setup.py
from __future__ import annotations

import json
import logging
from pathlib import Path

from podcast_llm_wiki.logging_setup import configure_jsonl_logger


def test_writes_json_line_to_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "pipeline.jsonl"
    configure_jsonl_logger(log_path, name="podcast_llm_wiki.test")
    log = logging.getLogger("podcast_llm_wiki.test")
    log.info("hello", extra={"episode_id": "vid1", "stage": "download"})

    # Flush handlers
    for h in log.handlers:
        h.flush()

    line = log_path.read_text().strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["msg"] == "hello"
    assert parsed["episode_id"] == "vid1"
    assert parsed["stage"] == "download"
    assert parsed["level"] == "INFO"
    assert "ts" in parsed
