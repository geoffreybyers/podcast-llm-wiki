# tests/unit/test_pipeline.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from podcast_llm_wiki.config import Config, Defaults, PodcastConfig
from podcast_llm_wiki.downloader import DownloadResult, EpisodeMetadata
from podcast_llm_wiki.ledger import Ledger
from podcast_llm_wiki.pipeline import Pipeline
from podcast_llm_wiki.transcriber import TranscriptSegment, TranscriptionResult


def _config(tmp_path: Path) -> Config:
    return Config(
        defaults=Defaults(vault_root=tmp_path / "obsidian"),
        podcasts=[
            PodcastConfig(
                name="Test Podcast",
                playlist_url="https://x.test",
                lens="lens",
                vault_path=tmp_path / "obsidian" / "Test Podcast",
                max_backfill=5,
                stt_model="whisper-base",
                diarization=True,
                diarization_segmentation="seg",
                diarization_embedding="emb",
            )
        ],
    )


class TestPipelineIngest:
    def test_processes_one_new_episode_end_to_end(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()

        ep = EpisodeMetadata(
            episode_id="vid1",
            title="Episode One",
            channel_title="Channel",
            published_at="2026-04-20",
            url="https://x.test/vid1",
        )
        downloads_dir = tmp_project / "podcasts" / "Test Podcast" / "downloads"
        downloads_dir.mkdir(parents=True)
        audio_path = downloads_dir / "vid1.wav"
        audio_path.write_bytes(b"RIFF")

        downloader = MagicMock()
        downloader.enumerate_playlist.return_value = [ep]
        downloader.filter_new.return_value = [ep]
        downloader.download_episode.return_value = DownloadResult(
            metadata=ep,
            audio_path=audio_path,
            info_json_path=downloads_dir / "vid1.info.json",
        )

        transcriber = MagicMock()
        transcriber.transcribe.return_value = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 5.0, "Speaker 1", "Hi.")],
            duration_sec=5.0,
            model_name="whisper-base",
            diarization=True,
        )

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        # collected.md has the row, status transcribed
        text = (tmp_project / "collected.md").read_text()
        assert "vid1" in text and "transcribed" in text

        # Transcription file written with sanitized name
        transcriptions_dir = tmp_project / "podcasts" / "Test Podcast" / "transcriptions"
        produced = list(transcriptions_dir.glob("*.md"))
        assert len(produced) == 1
        assert produced[0].name.endswith(" - transcription.md")

        # Queue contains the transcription path
        queue = (tmp_project / "analysis_queue.md").read_text()
        assert str(produced[0]) in queue

    def test_skips_already_known_episodes(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()
        # Pre-mark episode as known.
        from podcast_llm_wiki.ledger import EpisodeRecord
        ledger.record_downloaded(
            EpisodeRecord(
                podcast="Test Podcast",
                channel_title="C",
                title="T",
                published_at="2026-01-01",
                url="https://x.test/vid1",
                episode_id="vid1",
            )
        )

        ep = EpisodeMetadata(
            episode_id="vid1", title="T", channel_title="C",
            published_at="2026-01-01", url="https://x.test/vid1",
        )
        downloader = MagicMock()
        downloader.enumerate_playlist.return_value = [ep]
        downloader.filter_new.return_value = []  # filtered out

        transcriber = MagicMock()

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        downloader.download_episode.assert_not_called()
        transcriber.transcribe.assert_not_called()

    def test_limit_caps_new_episodes_per_podcast(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()

        eps = [
            EpisodeMetadata(
                episode_id=f"vid{i}", title=f"E{i}", channel_title="C",
                published_at="2026-04-20", url=f"https://x.test/vid{i}",
            )
            for i in range(3)
        ]

        def download_side(ep, podcast_name):
            audio = tmp_project / "podcasts" / podcast_name / "downloads" / f"{ep.episode_id}.wav"
            audio.parent.mkdir(parents=True, exist_ok=True)
            audio.write_bytes(b"RIFF")
            return DownloadResult(metadata=ep, audio_path=audio, info_json_path=audio.with_suffix(".info.json"))

        downloader = MagicMock()
        downloader.enumerate_playlist.return_value = eps
        downloader.filter_new.return_value = eps
        downloader.download_episode.side_effect = download_side

        transcriber = MagicMock()
        transcriber.transcribe.return_value = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 1.0, None, "x")],
            duration_sec=1.0, model_name="whisper-base", diarization=False,
        )

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
            limit=1,
        )
        p.ingest_all()

        assert downloader.download_episode.call_count == 1
        assert transcriber.transcribe.call_count == 1

    def test_enriches_published_at_from_download_result(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()

        # ep from flat enumeration has a stale/blank published_at.
        ep = EpisodeMetadata(
            episode_id="vid1",
            title="Episode One",
            channel_title="Channel",
            published_at="",
            url="https://x.test/vid1",
        )
        downloads_dir = tmp_project / "podcasts" / "Test Podcast" / "downloads"
        downloads_dir.mkdir(parents=True)
        audio_path = downloads_dir / "vid1.wav"
        audio_path.write_bytes(b"RIFF")

        # Downloader returns an enriched metadata with the real date.
        enriched = EpisodeMetadata(
            episode_id=ep.episode_id,
            title=ep.title,
            channel_title=ep.channel_title,
            published_at="2026-04-16",
            url=ep.url,
        )

        downloader = MagicMock()
        downloader.enumerate_playlist.return_value = [ep]
        downloader.filter_new.return_value = [ep]
        downloader.download_episode.return_value = DownloadResult(
            metadata=enriched,
            audio_path=audio_path,
            info_json_path=downloads_dir / "vid1.info.json",
        )

        transcriber = MagicMock()
        transcriber.transcribe.return_value = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 1.0, None, "hi")],
            duration_sec=1.0,
            model_name="whisper-base",
            diarization=False,
        )

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        # Ledger row carries the enriched date.
        text = (tmp_project / "collected.md").read_text()
        assert "2026-04-16" in text
        assert "vid1" in text and "transcribed" in text

        # Markdown frontmatter carries the enriched date.
        transcriptions_dir = tmp_project / "podcasts" / "Test Podcast" / "transcriptions"
        produced = list(transcriptions_dir.glob("*.md"))
        assert len(produced) == 1
        md = produced[0].read_text()
        assert "publishedAt: 2026-04-16" in md

    def test_records_failure_and_continues_on_download_error(self, tmp_project: Path) -> None:
        cfg = _config(tmp_project)
        # Add a second podcast so we can verify continuation.
        cfg.podcasts.append(
            PodcastConfig(
                name="Other",
                playlist_url="https://y.test",
                lens="l",
                vault_path=tmp_project / "obsidian" / "Other",
                max_backfill=5,
                stt_model="whisper-base",
                diarization=True,
                diarization_segmentation="seg",
                diarization_embedding="emb",
            )
        )
        ledger = Ledger(tmp_project)
        ledger.ensure_initialized()

        ep1 = EpisodeMetadata("vid1", "T1", "C", "2026-04-20", "https://x.test/vid1")
        ep2 = EpisodeMetadata("vid2", "T2", "C2", "2026-04-20", "https://y.test/vid2")

        def enumerate_side(url: str) -> list[EpisodeMetadata]:
            return [ep1] if "x.test" in url else [ep2]

        def filter_side(eps, **kwargs):
            return eps

        downloader = MagicMock()
        downloader.enumerate_playlist.side_effect = enumerate_side
        downloader.filter_new.side_effect = filter_side

        def download_side(ep, podcast_name):
            if ep.episode_id == "vid1":
                raise RuntimeError("HTTP 403")
            audio = tmp_project / "podcasts" / podcast_name / "downloads" / f"{ep.episode_id}.wav"
            audio.parent.mkdir(parents=True, exist_ok=True)
            audio.write_bytes(b"RIFF")
            return DownloadResult(metadata=ep, audio_path=audio, info_json_path=audio.with_suffix(".info.json"))

        downloader.download_episode.side_effect = download_side

        transcriber = MagicMock()
        transcriber.transcribe.return_value = TranscriptionResult(
            segments=[TranscriptSegment(0.0, 1.0, None, "ok")],
            duration_sec=1.0, model_name="whisper-base", diarization=False,
        )

        p = Pipeline(
            project_root=tmp_project,
            config=cfg,
            ledger=ledger,
            downloader=downloader,
            transcriber_factory=lambda pod: transcriber,
        )
        p.ingest_all()

        text = (tmp_project / "collected.md").read_text()
        assert "download_failed" in text
        assert "HTTP 403" in text
        # Other podcast still processed.
        assert "vid2" in text and "transcribed" in text
