from __future__ import annotations

from pathlib import Path

import pytest

from podcast_llm_wiki.config import Config, PodcastConfig, load_config

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadConfig:
    def test_loads_minimal_config(self) -> None:
        cfg = load_config(FIXTURES / "creators_minimal.yaml")
        assert isinstance(cfg, Config)
        assert len(cfg.podcasts) == 1
        assert cfg.podcasts[0].name == "Test Podcast"

    def test_applies_defaults_to_podcasts(self) -> None:
        cfg = load_config(FIXTURES / "creators_minimal.yaml")
        pod = cfg.podcasts[0]
        assert pod.max_backfill == 5
        assert pod.stt_model == "whisper-base"
        assert pod.diarization is True

    def test_vault_path_defaults_to_root_plus_name(self) -> None:
        cfg = load_config(FIXTURES / "creators_minimal.yaml")
        pod = cfg.podcasts[0]
        assert pod.vault_path == Path("~/obsidian/Test Podcast").expanduser()

    def test_per_podcast_overrides_default(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "  stt_model: whisper-base\n"
            "creators:\n"
            "  - name: P\n"
            "    source_url: https://x.test\n"
            "    lens: l\n"
            "    stt_model: whisper-medium\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].stt_model == "whisper-medium"

    def test_initial_prompt_defaults_to_none(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "creators:\n"
            "  - name: P\n"
            "    source_url: https://x.test\n"
            "    lens: l\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].initial_prompt is None

    def test_per_podcast_initial_prompt(self, tmp_path: Path) -> None:
        """Seeding only works when the prompt matches the show's own intro,
        so it is set per-podcast rather than globally."""
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  initial_prompt: Generic, default.\n"
            "creators:\n"
            "  - name: P\n"
            "    source_url: https://x.test\n"
            "    lens: l\n"
            "    initial_prompt: Welcome to Show P, where we do things.\n"
            "  - name: Q\n"
            "    source_url: https://y.test\n"
            "    lens: l\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].initial_prompt == "Welcome to Show P, where we do things."
        # Q inherits the default rather than silently getting P's prompt.
        assert cfg.podcasts[1].initial_prompt == "Generic, default."

    def test_explicit_vault_path_overrides_default(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "creators:\n"
            "  - name: P\n"
            "    source_url: https://x.test\n"
            "    lens: l\n"
            "    vault_path: /custom/path\n"
        )
        cfg = load_config(f)
        assert cfg.podcasts[0].vault_path == Path("/custom/path")

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            "defaults: {}\n"
            "creators:\n"
            "  - name: P\n"
            # missing source_url and lens
        )
        with pytest.raises(Exception):  # pydantic ValidationError or similar
            load_config(f)

    def test_lookup_by_name(self) -> None:
        cfg = load_config(FIXTURES / "creators_minimal.yaml")
        assert cfg.get_podcast("Test Podcast").name == "Test Podcast"
        assert cfg.get_podcast("nope") is None

    def test_loads_creators_key_with_source_url(self, tmp_path: Path) -> None:
        p = tmp_path / "creators.yaml"
        p.write_text(
            "defaults:\n"
            "  vault_root: ~/obsidian\n"
            "creators:\n"
            '  - name: "Dan Koe"\n'
            '    source_url: "https://www.youtube.com/@DanKoeTalks/videos"\n'
            "    lens: |\n"
            "      Test lens.\n"
        )
        cfg = load_config(p)
        assert len(cfg.podcasts) == 1
        assert cfg.podcasts[0].name == "Dan Koe"
        assert cfg.podcasts[0].source_url == "https://www.youtube.com/@DanKoeTalks/videos"
