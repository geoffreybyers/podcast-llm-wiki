from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from yt_dlp import YoutubeDL


@dataclass
class EpisodeMetadata:
    episode_id: str
    title: str
    channel_title: str
    published_at: str  # YYYY-MM-DD
    url: str


@dataclass
class DownloadResult:
    metadata: EpisodeMetadata
    audio_path: Path
    info_json_path: Path


def _format_date(yyyymmdd: Optional[str]) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return ""
    try:
        return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


class Downloader:
    """Wrapper around yt-dlp for playlist enumeration and audio download."""

    def __init__(self, downloads_root: Path) -> None:
        self.downloads_root = Path(downloads_root)

    def enumerate_playlist(self, playlist_url: str) -> list[EpisodeMetadata]:
        opts = {
            "extract_flat": True,
            "quiet": True,
            "skip_download": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
        entries = (info or {}).get("entries") or []
        results: list[EpisodeMetadata] = []
        for e in entries:
            if not e:
                continue
            results.append(
                EpisodeMetadata(
                    episode_id=str(e.get("id") or ""),
                    title=str(e.get("title") or ""),
                    channel_title=str(e.get("channel") or e.get("uploader") or ""),
                    published_at=_format_date(str(e.get("upload_date") or "")),
                    url=str(e.get("url") or e.get("webpage_url") or ""),
                )
            )
        return results
