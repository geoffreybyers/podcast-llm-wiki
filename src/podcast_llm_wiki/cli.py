# src/podcast_llm_wiki/cli.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

# Load secrets (HF_TOKEN, future API keys) from .env at project root, if present.
# Does nothing when the file is absent; never overwrites existing env vars.
load_dotenv()

from podcast_llm_wiki.config import load_config
from podcast_llm_wiki.downloader import Downloader
from podcast_llm_wiki.ledger import Ledger
from podcast_llm_wiki.logging_setup import configure_logging
from podcast_llm_wiki.pipeline import Pipeline
from podcast_llm_wiki.preflight import run_all
from podcast_llm_wiki.transcriber import (
    FasterWhisperAsr,
    PyannoteDiarizer,
    Transcriber,
    detect_device,
)

app = typer.Typer(help="podcast-llm-wiki: ingest podcast playlists into a Karpathy LLM Wiki.")


@app.callback(invoke_without_command=True)
def main() -> None:
    """podcast-llm-wiki CLI."""
    pass


def _build_transcriber_factory(model_cache_dir: Path):
    device = detect_device()

    def factory(pod):
        asr = FasterWhisperAsr(
            model_name=pod.stt_model,
            device=device,
            cache_dir=model_cache_dir,
            initial_prompt=pod.initial_prompt,
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
        Path("creators.yaml"), "--config", help="Path to creators.yaml."
    ),
    project_root: Path = typer.Option(
        Path("."), "--project-root", help="Project root containing creators/, logs/, etc."
    ),
    podcast: Optional[str] = typer.Option(
        None, "--creator", help="Process only this creator (by name)."
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
    resume: bool = typer.Option(
        False,
        "--resume/--no-resume",
        help="Before fetching new episodes: transcribe rows stuck in 'downloaded' and retry rows in 'download_failed'.",
    ),
    cookies_from_browser: Optional[str] = typer.Option(
        None,
        "--cookies-from-browser",
        help=(
            "Pass yt-dlp cookies from a local browser to bypass YouTube bot checks. "
            "Accepts yt-dlp's spec: BROWSER[+KEYRING][:PROFILE][::CONTAINER], e.g. "
            "'firefox' or 'firefox:/path/to/profile'. Give a PROFILE if the browser's "
            "default profile is not the one signed in to YouTube."
        ),
    ),
    sleep_interval: float = typer.Option(
        60.0,
        "--sleep-interval",
        help="Minimum seconds to sleep before each download. 0 (with --max-sleep-interval 0) disables.",
    ),
    max_sleep_interval: float = typer.Option(
        300.0,
        "--max-sleep-interval",
        help="Upper bound for the randomized pre-download sleep. Raised to --sleep-interval if lower.",
    ),
) -> None:
    """Run Tier 1: download new episodes and transcribe them."""
    today = __import__("datetime").date.today().isoformat()
    configure_logging(
        project_root / "logs" / f"pipeline-{today}.jsonl",
        console_level=log_level,
    )

    cfg = load_config(config)

    if not skip_preflight:
        run_all(podcasts=cfg.podcasts)

    ledger = Ledger(project_root)
    downloader = Downloader(
        downloads_root=project_root / "creators",
        cookies_from_browser=cookies_from_browser,
        sleep_interval=sleep_interval,
        max_sleep_interval=max_sleep_interval,
    )
    pipeline = Pipeline(
        project_root=project_root,
        config=cfg,
        ledger=ledger,
        downloader=downloader,
        transcriber_factory=_build_transcriber_factory(model_cache_dir),
        podcast_filter=podcast,
        limit=limit,
        resume=resume,
    )
    pipeline.ingest_all()
