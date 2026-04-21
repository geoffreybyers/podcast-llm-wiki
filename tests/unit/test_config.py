from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm_wiki.config import Config, PodcastConfig, load_config

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadConfig:
    def test_loads_minimal_config(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        assert isinstance(cfg, Config)
        assert len(cfg.podcasts) == 1
        assert cfg.podcasts[0].name == "Test Podcast"

    def test_applies_defaults_to_podcasts(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        pod = cfg.podcasts[0]
        assert pod.max_backfill == 5
        assert pod.stt_model == "whisper-base"
        assert pod.diarization is True

    def test_vault_path_defaults_to_root_plus_name(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        pod = cfg.podcasts[0]
        assert pod.vault_path == Path("~/obsidian/Test Podcast").expanduser()

    def test_per_podcast_overrides_default(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "  stt_model: whisper-base\n"
            "podcasts:\n"
            "  - name: P\n"
            "    playlist_url: https://x.test\n"
            "    lens: l\n"
            "    stt_model: whisper-medium\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].stt_model == "whisper-medium"

    def test_explicit_vault_path_overrides_default(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "podcasts:\n"
            "  - name: P\n"
            "    playlist_url: https://x.test\n"
            "    lens: l\n"
            "    vault_path: /custom/path\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].vault_path == Path("/custom/path")

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults: {}\n"
            "podcasts:\n"
            "  - name: P\n"
            # missing playlist_url and lens
        )
        with pytest.raises(Exception):  # pydantic ValidationError or similar
            load_config(f)

    def test_lookup_by_name(self) -> None:
        cfg = load_config(FIXTURES / "podcasts_minimal.yaml")
        assert cfg.get_podcast("Test Podcast").name == "Test Podcast"
        assert cfg.get_podcast("nope") is None
