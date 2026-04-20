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

    def filter_new(
        self,
        episodes: list[EpisodeMetadata],
        known_ids: set[str],
        max_backfill: Optional[int] = None,
    ) -> list[EpisodeMetadata]:
        """Drop episodes already in `known_ids`. Cap total at `max_backfill`."""
        new = [e for e in episodes if e.episode_id not in known_ids]
        if max_backfill is not None:
            new = new[:max_backfill]
        return new

    def download_episode(
        self,
        episode: EpisodeMetadata,
        podcast_name: str,
    ) -> DownloadResult:
        """Download bestaudio for `episode`, post-process to 16 kHz mono WAV.

        Side effect: writes audio file and `.info.json` sidecar in
        `<downloads_root>/<podcast_name>/<episode_id>.{wav,info.json}`.
        Updates the per-podcast yt-dlp download archive so re-runs skip.
        """
        podcast_dir = self.downloads_root / podcast_name
        podcast_dir.mkdir(parents=True, exist_ok=True)
        archive_path = podcast_dir / ".archive"
        outtmpl = str(podcast_dir / "%(id)s.%(ext)s")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "writeinfojson": True,
            "download_archive": str(archive_path),
            "quiet": True,
            "noprogress": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                },
                {
                    "key": "FFmpegPostProcessor",
                    "args": ["-ar", "16000", "-ac", "1"],
                },
            ],
        }
        with YoutubeDL(opts) as ydl:
            rc = ydl.download([episode.url])
        if rc != 0:
            raise RuntimeError(f"yt-dlp exited with code {rc} for {episode.url}")

        audio_path = podcast_dir / f"{episode.episode_id}.wav"
        info_path = podcast_dir / f"{episode.episode_id}.info.json"
        return DownloadResult(metadata=episode, audio_path=audio_path, info_json_path=info_path)
