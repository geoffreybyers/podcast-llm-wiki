from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
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


def _published_at_from_info_json(info_path: Path) -> str:
    """Return ISO date (YYYY-MM-DD, UTC) from a yt-dlp info.json.

    Prefers `timestamp` (precise epoch) over `upload_date` (date-only).
    Returns "" on any parse failure — caller decides whether to fall back
    to a previous value.
    """
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ""
    ts = data.get("timestamp")
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""
    upload_date = data.get("upload_date")
    if isinstance(upload_date, str) and upload_date:
        return _format_date(upload_date)
    return ""


class Downloader:
    """Wrapper around yt-dlp for playlist enumeration and audio download."""

    def __init__(
        self,
        downloads_root: Path,
        cookies_from_browser: Optional[str] = None,
        sleep_interval: float = 60.0,
        max_sleep_interval: float = 300.0,
    ) -> None:
        self.downloads_root = Path(downloads_root)
        self.cookies_from_browser = cookies_from_browser
        self.sleep_interval = float(sleep_interval)
        self.max_sleep_interval = float(max_sleep_interval)

    def _throttle_opts(self) -> dict:
        """Randomized pause before each download, to stay under YouTube's radar.

        Sustained back-to-back downloads from one IP draw HTTP 403s — observed
        roughly 9-10 episodes into consecutive batches. yt-dlp sleeps a random
        interval in [sleep_interval, max_sleep_interval] before each download,
        which breaks up the machine-gun request pattern.

        Costs real wall-clock: at the 60-300s default, a 30-episode backfill
        spends around 90 minutes sleeping. Set both to 0 to disable.
        """
        if self.sleep_interval <= 0 and self.max_sleep_interval <= 0:
            return {}
        return {
            "sleep_interval": self.sleep_interval,
            # yt-dlp requires max >= min and raises if not; clamp rather than
            # let a bad config pair blow up partway through a long run.
            "max_sleep_interval": max(self.max_sleep_interval, self.sleep_interval),
        }

    def _cookies_opt(self) -> dict:
        # yt-dlp expects a 4-tuple: (browser, profile, keyring, container), which
        # it exposes on its own CLI as BROWSER[+KEYRING][:PROFILE][::CONTAINER].
        #
        # PROFILE is worth supporting rather than always passing None: a browser's
        # default profile is frequently *not* the one signed in to YouTube, and
        # yt-dlp falls back to the default silently — so the run looks like it is
        # using cookies while actually staying anonymous, and the 403s continue.
        if not self.cookies_from_browser:
            return {}

        spec = self.cookies_from_browser.strip()
        container = None
        if "::" in spec:
            spec, container = spec.split("::", 1)
        profile = None
        if ":" in spec:
            spec, profile = spec.split(":", 1)
        keyring = None
        if "+" in spec:
            spec, keyring = spec.split("+", 1)
            keyring = keyring.strip().upper() or None

        return {
            "cookiesfrombrowser": (
                spec.strip().lower(),
                profile.strip() or None if profile else None,
                keyring,
                container.strip() or None if container else None,
            )
        }

    def _ytdlp_extra_opts(self) -> dict:
        # Enable JS runtime + remote n-sig solver. No-op until YouTube issues
        # an n-challenge; when it does (common for newer videos), downloads
        # 404 with "Requested format is not available" without these.
        #
        # player_client=web_embedded pins the one client that still hands back
        # real format URLs. On 2026-08-18 the default client stack stopped
        # working in two different ways at once:
        #
        #   anonymous -> media CDN 403s (an IP-wide gate; every modern video,
        #     any channel, all player_clients)
        #   signed in -> YouTube forces SABR streaming and binds a GVS PO token
        #     to the video id. yt-dlp ships no PO token provider, so every
        #     format comes back without a URL and extraction dies with
        #     "The page needs to be reloaded" (yt-dlp issue #12482).
        #
        # web_embedded sidestepped both and needed no cookies -- but it cannot
        # fetch videos whose owner disabled embedding ("Playback on other
        # websites has been disabled"). That is rare on some channels and
        # endemic on others: it killed 47 of the first 96 Alex Hormozi videos
        # on 2026-08-21 and stalled the backfill completely.
        #
        # mweb handles embed-disabled videos, "Video unavailable", and the IP
        # gate alike -- but only once a PO token provider is installed
        # (bgutil-ytdlp-pot-provider plus its built Node server; without it,
        # mweb returns "Requested format is not available"). web_embedded stays
        # as a fallback for anything mweb cannot resolve.
        return {
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "extractor_args": {
                "youtube": {"player_client": ["mweb", "web_embedded"]}
            },
        }

    def enumerate_playlist(self, playlist_url: str) -> list[EpisodeMetadata]:
        opts = {
            "extract_flat": True,
            "quiet": True,
            "skip_download": True,
            **self._cookies_opt(),
            **self._ytdlp_extra_opts(),
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
                    channel_title=str(
                        e.get("channel")
                        or e.get("uploader")
                        or info.get("channel")
                        or info.get("uploader")
                        or ""
                    ),
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
        `<downloads_root>/<podcast_name>/downloads/<episode_id>.{wav,info.json}`.
        Updates the per-podcast yt-dlp download archive so re-runs skip.
        """
        podcast_dir = self.downloads_root / podcast_name
        audio_dir = podcast_dir / "downloads"
        audio_dir.mkdir(parents=True, exist_ok=True)
        archive_path = podcast_dir / ".archive"
        outtmpl = str(audio_dir / "%(id)s.%(ext)s")

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
            ],
            # Resample to 16 kHz mono; faster-whisper expects 16 kHz input.
            "postprocessor_args": {
                "ffmpeg": ["-ar", "16000", "-ac", "1"],
            },
            **self._cookies_opt(),
            **self._ytdlp_extra_opts(),
            **self._throttle_opts(),
        }
        with YoutubeDL(opts) as ydl:
            rc = ydl.download([episode.url])
        if rc != 0:
            raise RuntimeError(f"yt-dlp exited with code {rc} for {episode.url}")

        audio_path = audio_dir / f"{episode.episode_id}.wav"
        info_path = audio_dir / f"{episode.episode_id}.info.json"

        # Flat playlist enumeration doesn't include upload_date; yt-dlp's
        # info.json sidecar does. Enrich from disk if we can.
        enriched_date = _published_at_from_info_json(info_path)
        if enriched_date:
            episode = EpisodeMetadata(
                episode_id=episode.episode_id,
                title=episode.title,
                channel_title=episode.channel_title,
                published_at=enriched_date,
                url=episode.url,
            )
        return DownloadResult(metadata=episode, audio_path=audio_path, info_json_path=info_path)
