# src/podcast_llm_wiki/pipeline.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from podcast_llm_wiki.config import Config, PodcastConfig
from podcast_llm_wiki.downloader import Downloader, EpisodeMetadata
from podcast_llm_wiki.ledger import EpisodeRecord, Ledger
from podcast_llm_wiki.transcriber import Transcriber, render_transcript_markdown
from podcast_llm_wiki.utils.filesystem import atomic_write, sanitize_filename

log = logging.getLogger(__name__)


TranscriberFactory = Callable[[PodcastConfig], Transcriber]


@dataclass
class Pipeline:
    project_root: Path
    config: Config
    ledger: Ledger
    downloader: Downloader
    transcriber_factory: TranscriberFactory
    podcast_filter: Optional[str] = None  # if set, only process this podcast name
    limit: Optional[int] = None  # if set, process at most N new episodes per podcast
    resume: bool = False  # if True, transcribe rows stuck in 'downloaded' before processing new episodes

    def ingest_all(self) -> None:
        self.ledger.ensure_initialized()
        for pod in self.config.podcasts:
            if self.podcast_filter and pod.name != self.podcast_filter:
                continue
            try:
                self._ingest_podcast(pod)
            except Exception as exc:  # noqa: BLE001
                log.exception("podcast ingest failed: %s", pod.name)
                # Failure is per-podcast; don't block the others.
                continue

    def _ingest_podcast(self, pod: PodcastConfig) -> None:
        # Lazily build the transcriber once per podcast (loads heavy models).
        transcriber: Optional[Transcriber] = None

        if self.resume:
            transcriber = self._resume_podcast(pod, transcriber)

        log.info("enumerating playlist: %s", pod.name)
        episodes = self.downloader.enumerate_playlist(pod.playlist_url)
        new = self.downloader.filter_new(
            episodes,
            known_ids=self.ledger.known_episode_ids(),
            max_backfill=pod.max_backfill,
        )
        if self.limit is not None:
            new = new[: self.limit]
        log.info("podcast=%s new_episodes=%d", pod.name, len(new))

        for ep in new:
            rec = EpisodeRecord(
                podcast=pod.name,
                channel_title=ep.channel_title,
                title=ep.title,
                published_at=ep.published_at,
                url=ep.url,
                episode_id=ep.episode_id,
            )

            try:
                dl = self.downloader.download_episode(ep, podcast_name=pod.name)
            except Exception as exc:  # noqa: BLE001
                log.exception("download failed: %s", ep.episode_id)
                self.ledger.record_failed(rec, stage="download", error=str(exc))
                continue
            # Flat playlist enumeration doesn't include upload_date; the
            # downloader enriches metadata from the info.json sidecar after
            # the download succeeds. Thread that through to the ledger row
            # and downstream rendering.
            if dl.metadata.published_at:
                rec.published_at = dl.metadata.published_at
                ep = dl.metadata
            self.ledger.record_downloaded(rec)

            if transcriber is None:
                transcriber = self.transcriber_factory(pod)

            self._transcribe_and_record(pod, rec, transcriber)

    def _resume_podcast(
        self, pod: PodcastConfig, transcriber: Optional[Transcriber]
    ) -> Optional[Transcriber]:
        """Transcribe rows stuck in 'downloaded' and retry 'download_failed' rows."""
        failed = self.ledger.failed_download_records(podcast=pod.name)
        if failed:
            log.info("podcast=%s retry_failed_downloads=%d", pod.name, len(failed))
            for rec in failed:
                ep = EpisodeMetadata(
                    episode_id=rec.episode_id,
                    title=rec.title,
                    channel_title=rec.channel_title,
                    published_at=rec.published_at,
                    url=rec.url,
                )
                try:
                    dl = self.downloader.download_episode(ep, podcast_name=pod.name)
                except Exception as exc:  # noqa: BLE001
                    log.exception("retry download failed: %s", rec.episode_id)
                    self.ledger.record_failed(rec, stage="download", error=str(exc))
                    continue
                if dl.metadata.published_at:
                    rec.published_at = dl.metadata.published_at
                self.ledger.record_downloaded(rec)
                if transcriber is None:
                    transcriber = self.transcriber_factory(pod)
                self._transcribe_and_record(pod, rec, transcriber)

        stuck = self.ledger.resumable_records(podcast=pod.name)
        if not stuck:
            return transcriber
        log.info("podcast=%s resumable_episodes=%d", pod.name, len(stuck))

        for rec in stuck:
            audio_path = self._audio_path(pod.name, rec.episode_id)
            if not audio_path.exists():
                log.warning(
                    "resume: skipping %s — WAV missing at %s",
                    rec.episode_id,
                    audio_path,
                )
                continue
            if transcriber is None:
                transcriber = self.transcriber_factory(pod)
            self._transcribe_and_record(pod, rec, transcriber)
        return transcriber

    def _audio_path(self, podcast_name: str, episode_id: str) -> Path:
        return (
            self.project_root
            / "podcasts"
            / podcast_name
            / "downloads"
            / f"{episode_id}.wav"
        )

    def _transcribe_and_record(
        self, pod: PodcastConfig, rec: EpisodeRecord, transcriber: Transcriber
    ) -> None:
        audio_path = self._audio_path(pod.name, rec.episode_id)
        try:
            result = transcriber.transcribe(audio_path)
        except Exception as exc:  # noqa: BLE001
            log.exception("transcription failed: %s", rec.episode_id)
            self.ledger.record_failed(rec, stage="transcription", error=str(exc))
            return

        md = render_transcript_markdown(
            result,
            episode_id=rec.episode_id,
            channel_title=rec.channel_title,
            title=rec.title,
            published_at=rec.published_at,
            url=rec.url,
        )
        base = sanitize_filename(
            f"{rec.channel_title} - {rec.title}",
            episode_id=rec.episode_id,
        )
        transcription_path = (
            self.project_root
            / "podcasts"
            / pod.name
            / "transcriptions"
            / f"{base} - transcription.md"
        )
        atomic_write(transcription_path, md)
        self.ledger.record_transcribed(rec.episode_id, str(transcription_path))
