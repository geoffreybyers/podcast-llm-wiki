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


_FORBIDDEN = re.compile(r"[/\\:*?\"<>|]")
_NULLS = re.compile(r"\x00")

# Total filename budget excluding extension. POSIX allows 255 but we leave headroom
# for " - transcription.md" / " - analysis.md" suffixes added by callers.
MAX_FILENAME_LEN = 200


def sanitize_filename(name: str, *, episode_id: str | None = None) -> str:
    """Make `name` safe to use as a filename component.

    - Replaces path separators and shell-unsafe chars with `-`.
    - Strips null bytes, leading dots, trailing whitespace/dots.
    - Truncates to MAX_FILENAME_LEN; if `episode_id` provided, reserves room
      and appends ` - <episode_id>` so truncated names remain unique.
    """
    cleaned = _NULLS.sub("", name)
    cleaned = _FORBIDDEN.sub("-", cleaned)
    cleaned = cleaned.lstrip(".")
    cleaned = cleaned.rstrip(" .")

    if episode_id:
        suffix = f" - {episode_id}"
        budget = MAX_FILENAME_LEN - len(suffix)
        if len(cleaned) > budget:
            cleaned = cleaned[:budget].rstrip(" .") + suffix
        elif len(cleaned) + len(suffix) > MAX_FILENAME_LEN:
            cleaned = cleaned[:budget].rstrip(" .") + suffix
    elif len(cleaned) > MAX_FILENAME_LEN:
        cleaned = cleaned[:MAX_FILENAME_LEN].rstrip(" .")

    return cleaned
