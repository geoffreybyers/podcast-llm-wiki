from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podcast_llm_wiki.downloader import (
    DownloadResult,
    Downloader,
    EpisodeMetadata,
    _published_at_from_info_json,
)


class TestCookiesFromBrowser:
    """yt-dlp's spec is BROWSER[+KEYRING][:PROFILE][::CONTAINER].

    Profile support matters in practice: a browser's *default* profile is often
    not the one signed in to YouTube, and passing just the browser name silently
    picks the default — looking like cookies were applied when they weren't.
    """

    def test_no_cookies_by_default(self) -> None:
        assert Downloader(downloads_root=Path("/tmp"))._cookies_opt() == {}

    def test_bare_browser_name(self) -> None:
        d = Downloader(downloads_root=Path("/tmp"), cookies_from_browser="firefox")
        assert d._cookies_opt() == {"cookiesfrombrowser": ("firefox", None, None, None)}

    def test_browser_with_profile(self) -> None:
        d = Downloader(
            downloads_root=Path("/tmp"),
            cookies_from_browser="firefox:/home/u/.mozilla/firefox/abc.Profile 4",
        )
        assert d._cookies_opt() == {
            "cookiesfrombrowser": (
                "firefox",
                "/home/u/.mozilla/firefox/abc.Profile 4",
                None,
                None,
            )
        }

    def test_browser_with_keyring(self) -> None:
        d = Downloader(downloads_root=Path("/tmp"), cookies_from_browser="brave+gnomekeyring")
        assert d._cookies_opt() == {
            "cookiesfrombrowser": ("brave", None, "GNOMEKEYRING", None)
        }

    def test_browser_with_container(self) -> None:
        d = Downloader(downloads_root=Path("/tmp"), cookies_from_browser="firefox::Personal")
        assert d._cookies_opt() == {
            "cookiesfrombrowser": ("firefox", None, None, "Personal")
        }

    def test_name_is_normalized(self) -> None:
        d = Downloader(downloads_root=Path("/tmp"), cookies_from_browser="  FireFox  ")
        assert d._cookies_opt()["cookiesfrombrowser"][0] == "firefox"


class TestThrottleOpts:
    """Randomized pause before each download, to avoid IP-level 403/429.

    Applied to downloads only. Playlist enumeration passes skip_download, so
    yt-dlp would never sleep for it anyway, and adding the keys there would only
    be misleading.
    """

    def test_defaults_are_60_to_300_seconds(self) -> None:
        opts = Downloader(downloads_root=Path("/tmp"))._throttle_opts()
        assert opts == {"sleep_interval": 60.0, "max_sleep_interval": 300.0}

    def test_overridable(self) -> None:
        d = Downloader(
            downloads_root=Path("/tmp"), sleep_interval=5, max_sleep_interval=10
        )
        assert d._throttle_opts() == {"sleep_interval": 5.0, "max_sleep_interval": 10.0}

    def test_zero_disables_sleeping(self) -> None:
        d = Downloader(downloads_root=Path("/tmp"), sleep_interval=0, max_sleep_interval=0)
        assert d._throttle_opts() == {}

    def test_max_below_min_is_raised_to_min(self) -> None:
        """yt-dlp requires max >= min; a bad pair would otherwise raise mid-run."""
        d = Downloader(
            downloads_root=Path("/tmp"), sleep_interval=120, max_sleep_interval=30
        )
        assert d._throttle_opts() == {"sleep_interval": 120.0, "max_sleep_interval": 120.0}

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_download_passes_sleep_opts(self, mock_ydl_cls, tmp_path: Path) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 0
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=tmp_path)
        ep = EpisodeMetadata(
            episode_id="vid1", title="T", channel_title="C",
            published_at="2026-01-01", url="https://x.test",
        )
        d.download_episode(ep, podcast_name="P")

        opts = mock_ydl_cls.call_args.args[0]
        assert opts["sleep_interval"] == 60.0
        assert opts["max_sleep_interval"] == 300.0

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_enumerate_does_not_sleep(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        mock_ydl_cls.return_value = mock_ydl

        Downloader(downloads_root=Path("/tmp")).enumerate_playlist("https://x.test")

        opts = mock_ydl_cls.call_args.args[0]
        assert "sleep_interval" not in opts


class TestEnumeratePlaylist:
    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_returns_episode_metadata_list(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "vid1",
                    "title": "Episode One",
                    "channel": "Test Channel",
                    "upload_date": "20260101",
                    "url": "https://youtube.com/watch?v=vid1",
                },
                {
                    "id": "vid2",
                    "title": "Episode Two",
                    "channel": "Test Channel",
                    "upload_date": "20260201",
                    "url": "https://youtube.com/watch?v=vid2",
                },
            ]
        }
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/playlist?list=ABC")

        assert len(episodes) == 2
        assert episodes[0].episode_id == "vid1"
        assert episodes[0].title == "Episode One"
        assert episodes[0].channel_title == "Test Channel"
        assert episodes[0].published_at == "2026-01-01"

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_uses_flat_playlist_option(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        d.enumerate_playlist("https://youtube.com/playlist?list=ABC")

        # Verify YoutubeDL was constructed with extract_flat: True (or similar)
        call_args = mock_ydl_cls.call_args[0][0]
        assert call_args.get("extract_flat") is True

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_handles_empty_playlist(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/playlist?list=ABC")
        assert episodes == []

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_entry_channel_takes_precedence(self, mock_ydl_cls) -> None:
        """Entry-level channel should win over top-level channel (playlist behavior)."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "channel": "Top Channel",
            "uploader": "Top Uploader",
            "entries": [
                {
                    "id": "vid1",
                    "title": "Episode One",
                    "channel": "Entry Channel",
                    "upload_date": "20260101",
                    "url": "https://youtube.com/watch?v=vid1",
                },
            ]
        }
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/playlist?list=ABC")

        assert len(episodes) == 1
        assert episodes[0].channel_title == "Entry Channel"

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_falls_back_to_top_level_channel_when_entry_has_neither(
        self, mock_ydl_cls
    ) -> None:
        """When entry has no channel/uploader, use top-level channel (channel URL case)."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "channel": "Dan Koe",
            "uploader": "Top Uploader",
            "entries": [
                {
                    "id": "vid1",
                    "title": "The Writing System That Saved My Brain",
                    "channel": None,
                    "uploader": None,
                    "upload_date": "20260101",
                    "url": "https://youtube.com/watch?v=vid1",
                },
            ]
        }
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://www.youtube.com/@Handle/videos")

        assert len(episodes) == 1
        assert episodes[0].channel_title == "Dan Koe"

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_falls_back_to_top_level_uploader_when_no_channel(
        self, mock_ydl_cls
    ) -> None:
        """When entry and top-level have no channel, use top-level uploader."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "channel": None,
            "uploader": "Creator Name",
            "entries": [
                {
                    "id": "vid1",
                    "title": "Episode One",
                    "channel": None,
                    "uploader": None,
                    "upload_date": "20260101",
                    "url": "https://youtube.com/watch?v=vid1",
                },
            ]
        }
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://www.youtube.com/@Handle/videos")

        assert len(episodes) == 1
        assert episodes[0].channel_title == "Creator Name"

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_empty_string_when_nothing_anywhere(self, mock_ydl_cls) -> None:
        """When no channel/uploader found anywhere, should be empty string, not crash."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "channel": None,
            "uploader": None,
            "entries": [
                {
                    "id": "vid1",
                    "title": "Episode One",
                    "channel": None,
                    "uploader": None,
                    "upload_date": "20260101",
                    "url": "https://youtube.com/watch?v=vid1",
                },
            ]
        }
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/watch?v=vid1")

        assert len(episodes) == 1
        assert episodes[0].channel_title == ""


def _sample_episode(eid: str, title: str = "T") -> EpisodeMetadata:
    return EpisodeMetadata(
        episode_id=eid,
        title=title,
        channel_title="C",
        published_at="2026-01-01",
        url=f"https://youtube.com/watch?v={eid}",
    )


class TestFilterNew:
    def test_filters_out_known_ids(self) -> None:
        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = [_sample_episode("a"), _sample_episode("b"), _sample_episode("c")]
        result = d.filter_new(episodes, known_ids={"b"})
        assert [e.episode_id for e in result] == ["a", "c"]

    def test_caps_at_max_backfill(self) -> None:
        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = [_sample_episode(f"e{i}") for i in range(10)]
        result = d.filter_new(episodes, known_ids=set(), max_backfill=3)
        assert len(result) == 3
        # Caps from the front (most recent first if caller passed sorted-newest-first).
        assert [e.episode_id for e in result] == ["e0", "e1", "e2"]

    def test_no_cap_when_max_backfill_none(self) -> None:
        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = [_sample_episode(f"e{i}") for i in range(10)]
        result = d.filter_new(episodes, known_ids=set(), max_backfill=None)
        assert len(result) == 10


class TestDownloadEpisode:
    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_downloads_audio_to_podcast_subdir(
        self, mock_ydl_cls, tmp_path: Path
    ) -> None:
        ep = _sample_episode("vid1", title="Episode One")

        # Pretend yt-dlp wrote files at expected paths.
        downloads_root = tmp_path / "downloads"
        podcast_dir = downloads_root / "P"
        audio_dir = podcast_dir / "downloads"
        audio_dir.mkdir(parents=True)
        audio_path = audio_dir / "vid1.wav"
        info_path = audio_dir / "vid1.info.json"
        audio_path.write_bytes(b"RIFF")
        # Real info.json with a timestamp — exercise the enrichment path.
        info_path.write_text('{"timestamp": 1776340852}')

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 0
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=downloads_root)
        result = d.download_episode(ep, podcast_name="P")

        assert isinstance(result, DownloadResult)
        assert result.audio_path == audio_path
        assert result.info_json_path == info_path
        # published_at enriched from info.json timestamp (1776340852 → 2026-04-16 UTC).
        assert result.metadata.published_at == "2026-04-16"

        # Verify yt-dlp was configured to write to podcast_dir with .info.json sidecar
        call_opts = mock_ydl_cls.call_args[0][0]
        assert call_opts["writeinfojson"] is True
        assert "outtmpl" in call_opts
        assert str(audio_dir) in call_opts["outtmpl"]

    @patch("podcast_llm_wiki.downloader.YoutubeDL")
    def test_raises_on_yt_dlp_nonzero_exit(self, mock_ydl_cls, tmp_path: Path) -> None:
        ep = _sample_episode("vid1")
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 1
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=tmp_path / "downloads")
        with pytest.raises(RuntimeError, match="yt-dlp"):
            d.download_episode(ep, podcast_name="P")


class TestPublishedAtEnrichment:
    def test_prefers_timestamp_over_upload_date(self, tmp_path: Path) -> None:
        info_path = tmp_path / "vid1.info.json"
        # timestamp → 2026-04-16 UTC; upload_date set to a different date to
        # confirm preference for timestamp.
        info_path.write_text('{"timestamp": 1776340852, "upload_date": "20250101"}')
        assert _published_at_from_info_json(info_path) == "2026-04-16"

    def test_falls_back_to_upload_date_when_no_timestamp(self, tmp_path: Path) -> None:
        info_path = tmp_path / "vid1.info.json"
        info_path.write_text('{"upload_date": "20260416"}')
        assert _published_at_from_info_json(info_path) == "2026-04-16"

    def test_returns_empty_when_neither_present(self, tmp_path: Path) -> None:
        info_path = tmp_path / "vid1.info.json"
        info_path.write_text("{}")
        assert _published_at_from_info_json(info_path) == ""

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        info_path = tmp_path / "does_not_exist.info.json"
        assert _published_at_from_info_json(info_path) == ""

    def test_returns_empty_on_malformed_json(self, tmp_path: Path) -> None:
        info_path = tmp_path / "vid1.info.json"
        info_path.write_text("{not json")
        assert _published_at_from_info_json(info_path) == ""
