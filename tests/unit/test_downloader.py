from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podcast_llm.downloader import (
    DownloadResult,
    Downloader,
    EpisodeMetadata,
)


class TestEnumeratePlaylist:
    @patch("podcast_llm.downloader.YoutubeDL")
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

    @patch("podcast_llm.downloader.YoutubeDL")
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

    @patch("podcast_llm.downloader.YoutubeDL")
    def test_handles_empty_playlist(self, mock_ydl_cls) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=Path("/tmp/dl"))
        episodes = d.enumerate_playlist("https://youtube.com/playlist?list=ABC")
        assert episodes == []


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
    @patch("podcast_llm.downloader.YoutubeDL")
    def test_downloads_audio_to_podcast_subdir(
        self, mock_ydl_cls, tmp_path: Path
    ) -> None:
        ep = _sample_episode("vid1", title="Episode One")

        # Pretend yt-dlp wrote files at expected paths.
        downloads_root = tmp_path / "downloads"
        podcast_dir = downloads_root / "P"
        podcast_dir.mkdir(parents=True)
        audio_path = podcast_dir / "vid1.wav"
        info_path = podcast_dir / "vid1.info.json"
        audio_path.write_bytes(b"RIFF")
        info_path.write_text("{}")

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 0
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=downloads_root)
        result = d.download_episode(ep, podcast_name="P")

        assert isinstance(result, DownloadResult)
        assert result.audio_path == audio_path
        assert result.info_json_path == info_path

        # Verify yt-dlp was configured to write to podcast_dir with .info.json sidecar
        call_opts = mock_ydl_cls.call_args[0][0]
        assert call_opts["writeinfojson"] is True
        assert "outtmpl" in call_opts
        assert str(podcast_dir) in call_opts["outtmpl"]

    @patch("podcast_llm.downloader.YoutubeDL")
    def test_raises_on_yt_dlp_nonzero_exit(self, mock_ydl_cls, tmp_path: Path) -> None:
        ep = _sample_episode("vid1")
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = 1
        mock_ydl_cls.return_value = mock_ydl

        d = Downloader(downloads_root=tmp_path / "downloads")
        with pytest.raises(RuntimeError, match="yt-dlp"):
            d.download_episode(ep, podcast_name="P")
