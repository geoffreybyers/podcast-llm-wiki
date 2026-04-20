from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


def atomic_write(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Write `content` to `target` atomically.

    Writes to a temp file in the same directory, then renames over `target`.
    Concurrent readers never observe a partial write. Creates parent dirs.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def sanitize_filename(name: str, *, episode_id: str | None = None) -> str:
    """Sanitize a filename for safe filesystem use.

    Stub for Task 1.2.
    """
    raise NotImplementedError
