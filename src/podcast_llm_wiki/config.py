from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class Defaults(BaseModel):
    vault_root: Path = Path("~/obsidian")
    max_backfill: int = 20
    stt_model: str = "whisper-base"
    diarization: bool = True
    diarization_segmentation: str = "pyannote-segmentation-3.0"
    diarization_embedding: str = "3d-speaker"

    @field_validator("vault_root", mode="before")
    @classmethod
    def expand(cls, v: object) -> Path:
        return Path(str(v)).expanduser() if v is not None else v


class PodcastConfig(BaseModel):
    name: str
    playlist_url: str
    lens: str
    vault_path: Path
    max_backfill: int
    stt_model: str
    diarization: bool
    diarization_segmentation: str
    diarization_embedding: str


class _RawPodcast(BaseModel):
    """Shape of a podcast entry as written in YAML before defaults are applied."""

    name: str
    playlist_url: str
    lens: str
    vault_path: Optional[Path] = None
    max_backfill: Optional[int] = None
    stt_model: Optional[str] = None
    diarization: Optional[bool] = None
    diarization_segmentation: Optional[str] = None
    diarization_embedding: Optional[str] = None


class Config(BaseModel):
    defaults: Defaults = Field(default_factory=Defaults)
    podcasts: list[PodcastConfig] = Field(default_factory=list)

    def get_podcast(self, name: str) -> Optional[PodcastConfig]:
        for p in self.podcasts:
            if p.name == name:
                return p
        return None


def load_config(path: Path) -> Config:
    """Load and validate a podcasts.yaml file. Applies defaults to each podcast."""
    raw = yaml.safe_load(Path(path).read_text())
    if raw is None:
        raw = {}

    defaults = Defaults(**(raw.get("defaults") or {}))
    podcasts: list[PodcastConfig] = []
    for entry in raw.get("podcasts") or []:
        rp = _RawPodcast(**entry)
        vault_path = (
            Path(str(rp.vault_path)).expanduser()
            if rp.vault_path is not None
            else defaults.vault_root / rp.name
        )
        podcasts.append(
            PodcastConfig(
                name=rp.name,
                playlist_url=rp.playlist_url,
                lens=rp.lens,
                vault_path=vault_path,
                max_backfill=rp.max_backfill if rp.max_backfill is not None else defaults.max_backfill,
                stt_model=rp.stt_model or defaults.stt_model,
                diarization=rp.diarization if rp.diarization is not None else defaults.diarization,
                diarization_segmentation=rp.diarization_segmentation or defaults.diarization_segmentation,
                diarization_embedding=rp.diarization_embedding or defaults.diarization_embedding,
            )
        )
    return Config(defaults=defaults, podcasts=podcasts)
