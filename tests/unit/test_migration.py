"""Tests for the one-shot podcast -> creator data migration."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from migrate_to_creators import rewrite_ledger_header, rewrite_queue_paths, rewrite_config_keys, main
from podcast_llm_wiki.config import load_config


def test_rewrites_ledger_header_column() -> None:
    text = (
        "| podcast | channelTitle | title |\n"
        "| --- | --- | --- |\n"
        "| Huberman Lab | Andrew Huberman | A podcast about podcasts |\n"
    )
    out = rewrite_ledger_header(text)
    assert out.startswith("| creator | channelTitle | title |\n")
    # Only the header changes -- body text that happens to say "podcast" stays.
    assert "A podcast about podcasts" in out


def test_ledger_header_rewrite_is_idempotent() -> None:
    text = "| podcast | channelTitle |\n| --- | --- |\n"
    assert rewrite_ledger_header(rewrite_ledger_header(text)) == rewrite_ledger_header(text)


def test_rewrites_queue_path_prefixes() -> None:
    text = (
        "- podcasts/Huberman Lab/transcriptions/A - transcription.md\n"
        "- podcasts/Huberman Lab/transcriptions/B - transcription.md\n"
    )
    out = rewrite_queue_paths(text)
    assert out == (
        "- creators/Huberman Lab/transcriptions/A - transcription.md\n"
        "- creators/Huberman Lab/transcriptions/B - transcription.md\n"
    )


def test_queue_rewrite_leaves_other_text_alone() -> None:
    """A title containing the word 'podcasts' must not be rewritten."""
    text = "- podcasts/Huberman Lab/transcriptions/Why podcasts win - transcription.md\n"
    out = rewrite_queue_paths(text)
    assert out == "- creators/Huberman Lab/transcriptions/Why podcasts win - transcription.md\n"


def test_queue_rewrite_is_idempotent() -> None:
    text = "- podcasts/X/transcriptions/A.md\n"
    assert rewrite_queue_paths(rewrite_queue_paths(text)) == rewrite_queue_paths(text)


def test_main_dry_run_performs_no_moves_or_writes(tmp_path: Path) -> None:
    """--dry-run must not move files or write anything."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Create source files and directories
    (project_root / "podcasts.yaml").write_text("podcasts: config\n")
    (project_root / "podcasts.yaml.example").write_text("example: config\n")
    (project_root / "podcasts").mkdir()
    (project_root / "podcasts" / "test.txt").write_text("audio data\n")
    (vault_root / "Podcast - Huberman Lab").mkdir()
    (vault_root / "Podcast - Huberman Lab" / "note.md").write_text("# Notes\n")
    (project_root / "collected.md").write_text("| podcast | channelTitle |\n| --- | --- |\n")
    (project_root / "analysis_queue.md").write_text("- podcasts/Huberman Lab/transcriptions/A.md\n")

    # Run with dry-run
    result = main(project_root, vault_root, dry_run=True)

    # Verify: no moves occurred
    assert result == 0
    assert (project_root / "podcasts.yaml").exists()
    assert not (project_root / "creators.yaml").exists()
    assert (project_root / "podcasts").exists()
    assert not (project_root / "creators").exists()
    assert (vault_root / "Podcast - Huberman Lab").exists()
    assert not (vault_root / "Creator - Huberman Lab").exists()

    # Verify: no writes occurred
    assert (project_root / "collected.md").read_text() == "| podcast | channelTitle |\n| --- | --- |\n"
    assert (project_root / "analysis_queue.md").read_text() == "- podcasts/Huberman Lab/transcriptions/A.md\n"

    # Verify: no backups created
    assert not (project_root / "collected.md.bak").exists()
    assert not (project_root / "analysis_queue.md.bak").exists()


def test_main_real_run_moves_and_rewrites(tmp_path: Path) -> None:
    """A real run should move files and rewrite the ledgers."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Create source files and directories
    (project_root / "podcasts.yaml").write_text("podcasts: config\n")
    (project_root / "podcasts.yaml.example").write_text("example: config\n")
    (project_root / "podcasts").mkdir()
    (project_root / "podcasts" / "test.txt").write_text("audio data\n")
    (vault_root / "Podcast - Huberman Lab").mkdir()
    (vault_root / "Podcast - Huberman Lab" / "note.md").write_text("# Notes\n")
    collected_before = "| podcast | channelTitle |\n| --- | --- |\n| Huberman Lab | Andrew |\n"
    (project_root / "collected.md").write_text(collected_before)
    queue_before = "- podcasts/Huberman Lab/transcriptions/A.md\n"
    (project_root / "analysis_queue.md").write_text(queue_before)

    # Run without dry-run
    result = main(project_root, vault_root, dry_run=False)

    # Verify: files were moved
    assert result == 0
    assert not (project_root / "podcasts.yaml").exists()
    assert (project_root / "creators.yaml").exists()
    # Note: creators.yaml is now rewritten with config keys changed
    assert (project_root / "creators.yaml").read_text() == "creators: config\n"
    assert not (project_root / "podcasts").exists()
    assert (project_root / "creators").exists()
    assert (project_root / "creators" / "test.txt").read_text() == "audio data\n"
    assert not (vault_root / "Podcast - Huberman Lab").exists()
    assert (vault_root / "Creator - Huberman Lab").exists()

    # Verify: ledgers were rewritten
    collected_after = (project_root / "collected.md").read_text()
    assert collected_after.startswith("| creator | channelTitle |\n")
    assert "A podcast about podcasts" not in collected_after  # only header changed
    queue_after = (project_root / "analysis_queue.md").read_text()
    assert "- creators/Huberman Lab/transcriptions/A.md\n" in queue_after

    # Verify: backups were created with original contents
    assert (project_root / "collected.md.bak").exists()
    assert (project_root / "collected.md.bak").read_text() == collected_before
    assert (project_root / "analysis_queue.md.bak").exists()
    assert (project_root / "analysis_queue.md.bak").read_text() == queue_before
    assert (project_root / "creators.yaml.bak").exists()
    assert (project_root / "creators.yaml.bak").read_text() == "podcasts: config\n"


def test_main_rerun_after_migration_is_idempotent(tmp_path: Path) -> None:
    """Re-running after a completed migration should be safe and return 0."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Create already-migrated state
    (project_root / "creators.yaml").write_text("creators: config\n")
    (project_root / "creators.yaml.example").write_text("example: config\n")
    (project_root / "creators").mkdir()
    (project_root / "creators" / "test.txt").write_text("audio data\n")
    (vault_root / "Creator - Huberman Lab").mkdir()
    (vault_root / "Creator - Huberman Lab" / "note.md").write_text("# Notes\n")
    collected_after_migration = "| creator | channelTitle |\n| --- | --- |\n| Huberman Lab | Andrew |\n"
    (project_root / "collected.md").write_text(collected_after_migration)
    queue_after_migration = "- creators/Huberman Lab/transcriptions/A.md\n"
    (project_root / "analysis_queue.md").write_text(queue_after_migration)

    # Run again
    result = main(project_root, vault_root, dry_run=False)

    # Verify: idempotent, returns 0
    assert result == 0
    # Nothing moved (already migrated)
    assert (project_root / "creators.yaml").read_text() == "creators: config\n"
    # Contents unchanged
    assert (project_root / "collected.md").read_text() == collected_after_migration
    assert (project_root / "analysis_queue.md").read_text() == queue_after_migration


def test_main_ambiguous_state_returns_error(tmp_path: Path) -> None:
    """Both src and dst existing is ambiguous and dangerous. Should error and not proceed."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Create ambiguous state: both podcasts/ and creators/ exist
    (project_root / "podcasts.yaml").write_text("podcasts: config\n")
    (project_root / "creators.yaml").write_text("creators: config\n")
    (project_root / "podcasts").mkdir()
    (project_root / "creators").mkdir()
    (vault_root / "Podcast - Huberman Lab").mkdir()
    (vault_root / "Creator - Huberman Lab").mkdir()
    collected_before = "| podcast | channelTitle |\n| --- | --- |\n"
    (project_root / "collected.md").write_text(collected_before)
    (project_root / "analysis_queue.md").write_text("- podcasts/X/transcriptions/A.md\n")

    # Run - should error
    result = main(project_root, vault_root, dry_run=False)

    # Verify: error returned
    assert result == 1

    # Verify: no moves occurred
    assert (project_root / "podcasts.yaml").exists()
    assert (project_root / "creators.yaml").exists()
    assert (project_root / "podcasts").exists()
    assert (project_root / "creators").exists()
    assert (vault_root / "Podcast - Huberman Lab").exists()
    assert (vault_root / "Creator - Huberman Lab").exists()

    # Verify: no rewrites occurred
    assert (project_root / "collected.md").read_text() == collected_before
    assert (project_root / "analysis_queue.md").read_text() == "- podcasts/X/transcriptions/A.md\n"

    # Verify: no backups created
    assert not (project_root / "collected.md.bak").exists()
    assert not (project_root / "analysis_queue.md.bak").exists()


def test_main_backup_created_on_rewrite(tmp_path: Path) -> None:
    """Backups should be created with original contents before rewriting."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Already migrated file structure
    (project_root / "creators.yaml").write_text("creators: config\n")
    (project_root / "creators.yaml.example").write_text("creators: example\n")
    (project_root / "creators").mkdir(parents=True, exist_ok=True)
    (vault_root / "Creator - Huberman Lab").mkdir(parents=True, exist_ok=True)

    collected_content = "| podcast | channelTitle |\n| --- | --- |\n"
    (project_root / "collected.md").write_text(collected_content)
    queue_content = "- podcasts/X/A.md\n"
    (project_root / "analysis_queue.md").write_text(queue_content)

    # First run creates backups
    result = main(project_root, vault_root, dry_run=False)
    assert result == 0
    assert (project_root / "collected.md.bak").read_text() == collected_content
    assert (project_root / "analysis_queue.md.bak").read_text() == queue_content

    # Modify the content to simulate file getting corrupted
    collected_corrupted = "corrupted content\n"
    (project_root / "collected.md").write_text(collected_corrupted)

    # Re-run should NOT overwrite the backup
    result = main(project_root, vault_root, dry_run=False)
    assert result == 0
    # Backup still has original content
    assert (project_root / "collected.md.bak").read_text() == collected_content


def test_rewrite_config_keys_top_level() -> None:
    """Rewrites top-level 'podcasts:' key to 'creators:'."""
    text = "podcasts:\n  - name: Huberman Lab\n"
    out = rewrite_config_keys(text)
    assert out.startswith("creators:\n")
    assert "  - name: Huberman Lab\n" in out


def test_rewrite_config_keys_playlist_url_to_source_url() -> None:
    """Rewrites 'playlist_url:' to 'source_url:' preserving indentation."""
    text = (
        "defaults:\n"
        "  playlist_url: https://example.com\n"
        "creators:\n"
        "  - name: Test\n"
        "    playlist_url: https://youtube.com\n"
    )
    out = rewrite_config_keys(text)
    # Note: defaults.playlist_url may not exist, but in entries it does
    assert "    source_url: https://youtube.com\n" in out
    # Should not have playlist_url anymore
    assert "playlist_url:" not in out


def test_rewrite_config_keys_preserves_lens_prose() -> None:
    """Lens blocks containing 'podcast'/'podcasts' must be left unchanged."""
    text = (
        "podcasts:\n"
        "  - name: Huberman Lab\n"
        "    source_url: https://youtube.com/@hubermanlab\n"
        "    lens: |\n"
        "      This is a podcast about science and health. The host discusses\n"
        "      podcasts from other creators, neuroscience podcasts, and how\n"
        "      podcasts can help listeners with podcast subscriptions.\n"
        "    playlist_url: https://old.url\n"
    )
    out = rewrite_config_keys(text)
    # Top-level key and field key should be rewritten
    assert out.startswith("creators:\n")
    assert "    source_url: https://youtube.com/@hubermanlab\n" in out
    # But the lens prose should be completely unchanged
    assert (
        "      This is a podcast about science and health. The host discusses\n"
        "      podcasts from other creators, neuroscience podcasts, and how\n"
        "      podcasts can help listeners with podcast subscriptions.\n" in out
    )


def test_rewrite_config_keys_is_idempotent() -> None:
    """Rewriting config keys twice equals one rewrite."""
    text = (
        "podcasts:\n"
        "  - name: Test\n"
        "    playlist_url: https://example.com\n"
    )
    once = rewrite_config_keys(text)
    twice = rewrite_config_keys(once)
    assert once == twice


def test_main_rewrites_yaml_config_files(tmp_path: Path) -> None:
    """main() should rewrite creators.yaml and creators.yaml.example config keys."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Already-migrated state (moves are already done)
    (vault_root / "Creator - Huberman Lab").mkdir(parents=True, exist_ok=True)
    (project_root / "creators").mkdir(parents=True, exist_ok=True)

    # Old-style creators.yaml with 'podcasts:' key and 'playlist_url:' field
    yaml_content = (
        "defaults:\n"
        "  vault_root: ~/obsidian\n"
        "podcasts:\n"
        "  - name: Huberman Lab\n"
        "    playlist_url: https://www.youtube.com/@hubermanlab/videos\n"
        "    lens: |\n"
        "      Neuroscience and health podcast exploring human potential.\n"
        "      Discusses science, psychology, neuroscience podcasts and more.\n"
    )
    (project_root / "creators.yaml").write_text(yaml_content)
    (project_root / "creators.yaml.example").write_text(yaml_content)

    # Create dummy ledger files (already migrated)
    (project_root / "collected.md").write_text("| creator | channelTitle |\n| --- | --- |\n")
    (project_root / "analysis_queue.md").write_text("- creators/Huberman Lab/transcriptions/A.md\n")

    # Run migration
    result = main(project_root, vault_root, dry_run=False)
    assert result == 0

    # Verify both YAML files were rewritten
    yaml_after = (project_root / "creators.yaml").read_text()
    assert yaml_after.startswith("defaults:\n  vault_root: ~/obsidian\ncreators:\n")
    assert "    source_url: https://www.youtube.com/@hubermanlab/videos\n" in yaml_after
    # Lens prose should be untouched
    assert "Discusses science, psychology, neuroscience podcasts and more.\n" in yaml_after
    # Old keys should not exist
    assert "podcasts:" not in yaml_after
    assert "playlist_url:" not in yaml_after

    # Verify example was also rewritten
    example_after = (project_root / "creators.yaml.example").read_text()
    assert example_after.startswith("defaults:\n  vault_root: ~/obsidian\ncreators:\n")
    assert "    source_url: https://www.youtube.com/@hubermanlab/videos\n" in example_after
    assert "playlist_url:" not in example_after

    # Verify backups were created with original content
    assert (project_root / "creators.yaml.bak").exists()
    assert (project_root / "creators.yaml.bak").read_text() == yaml_content
    assert (project_root / "creators.yaml.example.bak").exists()
    assert (project_root / "creators.yaml.example.bak").read_text() == yaml_content

    # Verify the rewritten YAML can be loaded with load_config
    cfg = load_config(project_root / "creators.yaml")
    assert len(cfg.podcasts) == 1
    assert cfg.podcasts[0].name == "Huberman Lab"
    assert cfg.podcasts[0].source_url == "https://www.youtube.com/@hubermanlab/videos"
