# src/podcast_llm_wiki/logging_setup.py
from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from pathlib import Path

_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName",
}


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(
    jsonl_path: Path,
    console_level: str = "INFO",
    file_level: str = "INFO",
) -> None:
    """Wire root logging: JSONL file capture + plain stderr echo.

    Attaching to the root logger means third-party libraries (httpx,
    faster_whisper, pyannote) land in the JSONL file as structured lines
    instead of leaking to stderr where they would bypass our formatter.
    `captureWarnings` folds `warnings.warn` calls into the same pipeline.

    Idempotent: re-calling with the same jsonl_path is a no-op.
    """
    jsonl_path = Path(jsonl_path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    levels = logging.getLevelNamesMapping()
    file_lvl = levels.get(file_level.upper(), logging.INFO)
    console_lvl = levels.get(console_level.upper(), logging.INFO)

    root = logging.getLogger()
    # Root must not filter below what any handler wants to emit.
    root.setLevel(min(file_lvl, console_lvl))

    for h in root.handlers:
        if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == jsonl_path:
            return

    fh = logging.FileHandler(jsonl_path, encoding="utf-8")
    fh.setLevel(file_lvl)
    fh.setFormatter(JsonLineFormatter())
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(console_lvl)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(sh)

    logging.captureWarnings(True)
