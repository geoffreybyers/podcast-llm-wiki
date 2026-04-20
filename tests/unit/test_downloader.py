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
