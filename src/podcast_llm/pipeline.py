# src/podcast_llm/pipeline.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from podcast_llm.config import Config, PodcastConfig
from podcast_llm.downloader import Downloader, EpisodeMetadata
from podcast_llm.ledger import EpisodeRecord, Ledger
from podcast_llm.transcriber import Transcriber, render_transcript_markdown
from podcast_llm.utils.filesystem import atomic_write, sanitize_filename

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

        # Lazily build the transcriber once per podcast (loads heavy models).
        transcriber: Optional[Transcriber] = None

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

            audio_path = (
                self.project_root
                / "podcasts"
                / pod.name
                / "downloads"
                / f"{ep.episode_id}.wav"
            )

            try:
                result = transcriber.transcribe(audio_path)
            except Exception as exc:  # noqa: BLE001
                log.exception("transcription failed: %s", ep.episode_id)
                self.ledger.record_failed(rec, stage="transcription", error=str(exc))
                continue

            md = render_transcript_markdown(
                result,
                episode_id=ep.episode_id,
                channel_title=ep.channel_title,
                title=ep.title,
                published_at=ep.published_at,
                url=ep.url,
            )
            base = sanitize_filename(
                f"{ep.channel_title} - {ep.title}",
                episode_id=ep.episode_id,
            )
            transcription_path = (
                self.project_root
                / "podcasts"
                / pod.name
                / "transcriptions"
                / f"{base} - transcription.md"
            )
            atomic_write(transcription_path, md)
            self.ledger.record_transcribed(ep.episode_id, str(transcription_path))
