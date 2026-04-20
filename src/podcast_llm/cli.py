# src/podcast_llm/cli.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from podcast_llm.config import load_config
from podcast_llm.downloader import Downloader
from podcast_llm.ledger import Ledger
from podcast_llm.logging_setup import configure_jsonl_logger
from podcast_llm.pipeline import Pipeline
from podcast_llm.preflight import run_all
from podcast_llm.transcriber import (
    FasterWhisperAsr,
    PyannoteDiarizer,
    Transcriber,
    detect_device,
)

app = typer.Typer(help="podcast-llm: ingest podcast playlists into a Karpathy LLM Wiki.")


@app.callback(invoke_without_command=True)
def main() -> None:
    """podcast-llm CLI."""
    pass


def _build_transcriber_factory(model_cache_dir: Path):
    device = detect_device()

    def factory(pod):
        asr = FasterWhisperAsr(
            model_name=pod.stt_model,
            device=device,
            cache_dir=model_cache_dir,
        )
        diar = (
            PyannoteDiarizer(
                segmentation_model=pod.diarization_segmentation,
                embedding_model=pod.diarization_embedding,
                device=device,
            )
            if pod.diarization
            else None
        )
        return Transcriber(
            asr_engine=asr,
            diar_engine=diar,
            model_name=pod.stt_model,
            diarization=pod.diarization,
        )

    return factory


@app.command()
def ingest(
    config: Path = typer.Option(
        Path("podcasts.yaml"), "--config", help="Path to podcasts.yaml."
    ),
    project_root: Path = typer.Option(
        Path("."), "--project-root", help="Project root containing podcasts/, logs/, etc."
    ),
    podcast: Optional[str] = typer.Option(
        None, "--podcast", help="Process only this podcast (by name)."
    ),
    model_cache_dir: Path = typer.Option(
        Path("~/.cache/faster-whisper").expanduser(),
        "--model-cache-dir",
        help="Where faster-whisper model files are cached.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
    skip_preflight: bool = typer.Option(False, "--skip-preflight"),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Process at most N new episodes per podcast (smoke-test friendly)."
    ),
) -> None:
    """Run Tier 1: download new episodes and transcribe them."""
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    today = __import__("datetime").date.today().isoformat()
    configure_jsonl_logger(project_root / "logs" / f"pipeline-{today}.jsonl")

    cfg = load_config(config)

    if not skip_preflight:
        run_all(podcasts=cfg.podcasts)

    ledger = Ledger(project_root)
    downloader = Downloader(downloads_root=project_root / "podcasts")
    pipeline = Pipeline(
        project_root=project_root,
        config=cfg,
        ledger=ledger,
        downloader=downloader,
        transcriber_factory=_build_transcriber_factory(model_cache_dir),
        podcast_filter=podcast,
        limit=limit,
    )
    pipeline.ingest_all()
