from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from podcast_llm_wiki.parsers.analysis_sections import (
    ConceptItem,
    ContradictionItem,
    EntityItem,
    ParsedAnalysis,
)
from podcast_llm_wiki.wiki.vault import create_vault_skeleton
from podcast_llm_wiki.wiki.writer import (
    EpisodeMeta,
    WikiWriter,
)


@pytest.fixture
def vault(tmp_vault: Path) -> Path:
    v = tmp_vault / "Test Podcast"
    create_vault_skeleton(v, podcast_name="Test Podcast", lens="Test lens.")
    return v


def _episode_meta(**overrides) -> EpisodeMeta:
    base = dict(
        episode_id="vid1",
        channel_title="Channel",
        title="Episode One",
        published_at="2026-04-20",
        url="https://x.test/vid1",
        transcription_path="/abs/transcription.md",
        analysis_path="/abs/analysis.md",
    )
    base.update(overrides)
    return EpisodeMeta(**base)


class TestCopyTranscription:
    def test_copies_to_raw_transcripts(self, vault: Path, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.write_text("transcription content")
        meta = _episode_meta()
        w = WikiWriter(vault)
        dest = w.copy_transcription(src, meta)
        assert dest.exists()
        assert dest.parent == vault / "raw" / "transcripts"
        assert dest.read_text() == "transcription content"
        assert dest.name.endswith(".md")


class TestWriteEpisodePage:
    def test_writes_episode_with_frontmatter(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        page = w.write_episode_page(
            meta,
            tldr="Three sentences. About the thesis. Why it matters.",
            insights_md="- **Insight A:** body [00:01:00]\n- **Insight B:** body [00:05:00]\n",
            entity_links=["[[Andrew Huberman]]", "[[Stanford University]]"],
            concept_links=["[[circadian rhythm]]"],
        )
        assert page.exists()
        text = page.read_text()
        assert text.startswith("---\n")
        assert "type: episode" in text
        assert "episode_id: vid1" in text
        assert "channelTitle: Channel" in text
        assert "url: https://x.test/vid1" in text
        assert "transcription_path: /abs/transcription.md" in text
        assert "analysis_path: /abs/analysis.md" in text
        assert "## TL;DR" in text
        assert "Three sentences." in text
        assert "## Key Insights" in text
        assert "**Insight A:**" in text
        assert "## Entities" in text
        assert "[[Andrew Huberman]]" in text
        assert "## Concepts" in text
        assert "[[circadian rhythm]]" in text

    def test_episode_page_path_uses_sanitized_filename(self, vault: Path) -> None:
        meta = _episode_meta(title="Bad/Slash: Title")
        w = WikiWriter(vault)
        page = w.write_episode_page(meta, tldr="x", insights_md="", entity_links=[], concept_links=[])
        assert "/" not in page.name[:-3]  # excluding ".md"

    def test_critical_pass_section_rendered_when_provided(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        page = w.write_episode_page(
            meta,
            tldr="t",
            insights_md="- **A:** body [00:01:00]",
            critical_pass_md="- **Steelman:** strong argument\n- Weak claim: citation missing",
            entity_links=[],
            concept_links=[],
        )
        text = page.read_text()
        assert "## Critical Pass" in text
        assert "**Steelman:**" in text
        assert "citation missing" in text
        # Critical Pass sits between Insights and Entities.
        assert text.index("## Key Insights") < text.index("## Critical Pass") < text.index("## Entities")

    def test_critical_pass_omitted_when_empty(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        page = w.write_episode_page(
            meta, tldr="t", insights_md="", entity_links=[], concept_links=[],
        )
        assert "## Critical Pass" not in page.read_text()


class TestUpsertComparisonPage:
    def test_creates_comparison_page(self, vault: Path) -> None:
        from podcast_llm_wiki.wiki.writer import WikiWriter
        meta = _episode_meta()
        w = WikiWriter(vault)
        c = ContradictionItem(
            claim="Claim that SAT has no predictive validity",
            prior_episode="Andrew Huberman - Prior Episode",
            resolution="unresolved",
            timestamp="00:30:00",
        )
        path = w.upsert_comparison_page(c, episode_meta=meta)
        assert path.parent == vault / "comparisons"
        text = path.read_text()
        assert text.startswith("---\n")
        assert "type: comparison" in text
        assert "comparison_type: contradiction" in text
        assert "resolution: unresolved" in text
        # Both episodes linked.
        assert f"[[{meta.base_filename()}]]" in text
        assert "[[Andrew Huberman - Prior Episode]]" in text
        assert "Claim that SAT has no predictive validity" in text

    def test_internal_contradiction_omits_prior_link(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        c = ContradictionItem(
            claim="Internal inconsistency about dosing",
            prior_episode="none",
            resolution="both-stand",
            timestamp="01:10:00",
        )
        path = w.upsert_comparison_page(c, episode_meta=meta)
        text = path.read_text()
        assert f"[[{meta.base_filename()}]]" in text
        # No "[[none]]" wikilink should be emitted.
        assert "[[none]]" not in text

    def test_appends_episode_to_existing_comparison(self, vault: Path) -> None:
        meta1 = _episode_meta(episode_id="e1", title="One")
        meta2 = _episode_meta(episode_id="e2", title="Two")
        c = ContradictionItem(
            claim="Same disputed claim across episodes",
            prior_episode="Channel - Original Episode",
            resolution="unresolved",
            timestamp="00:05:00",
        )
        w = WikiWriter(vault)
        w.upsert_comparison_page(c, episode_meta=meta1)
        path = w.upsert_comparison_page(c, episode_meta=meta2)
        text = path.read_text()
        assert f"[[{meta1.base_filename()}]]" in text
        assert f"[[{meta2.base_filename()}]]" in text
        assert len(list((vault / "comparisons").glob("*.md"))) == 1


class TestWriteVerifyQueryPage:
    def test_creates_verify_page_with_todos(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        path = w.write_verify_query_page(
            [
                "Effect size on meditation — no source given",
                'Claim that SAT has "no predictive validity" — check sample vs population',
            ],
            episode_meta=meta,
        )
        assert path.parent == vault / "queries"
        assert path.name == f"verify-{meta.base_filename()}.md"
        text = path.read_text()
        assert "type: query" in text
        assert "query_type: verify" in text
        assert f"source_episode: [[{meta.base_filename()}]]" in text
        assert "Effect size on meditation" in text
        assert "no predictive validity" in text


class TestUpdateIndexComparisonsAndQueries:
    def test_adds_comparison_and_query_entries(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        w.update_index(
            new_episodes=[(meta.base_filename(), meta.title)],
            new_comparisons=[("disputed-claim - contradiction", "SAT validity dispute")],
            new_queries=[(f"verify-{meta.base_filename()}", "facts to verify")],
        )
        idx = (vault / "index.md").read_text()
        assert "[[disputed-claim - contradiction]] — SAT validity dispute" in idx
        assert f"[[verify-{meta.base_filename()}]] — facts to verify" in idx


class TestUpsertEntityPage:
    def test_creates_new_entity_page_with_backlink(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        e = EntityItem(
            name="Andrew Huberman",
            type="person",
            context="Stanford neuroscientist hosting the show",
            timestamp="00:00:30",
        )
        path = w.upsert_entity_page(e, episode_meta=meta)
        text = path.read_text()
        assert path.parent == vault / "entities"
        assert text.startswith("---\n")
        assert "type: entity" in text
        assert "Andrew Huberman" in text
        assert "Stanford neuroscientist hosting the show" in text
        # Backlink to episode page
        assert f"[[{meta.base_filename()}]]" in text

    def test_appends_to_existing_entity_page(self, vault: Path) -> None:
        meta1 = _episode_meta(episode_id="ep1", title="One")
        meta2 = _episode_meta(episode_id="ep2", title="Two")
        e1 = EntityItem("Andrew Huberman", "person", "Host", "00:00:30")
        e2 = EntityItem("Andrew Huberman", "person", "Host again", "00:01:00")
        w = WikiWriter(vault)
        w.upsert_entity_page(e1, episode_meta=meta1)
        path = w.upsert_entity_page(e2, episode_meta=meta2)
        text = path.read_text()
        # Both episode backlinks present.
        assert f"[[{meta1.base_filename()}]]" in text
        assert f"[[{meta2.base_filename()}]]" in text
        # Single page (not duplicated).
        pages = list((vault / "entities").glob("*.md"))
        assert len(pages) == 1
        # `updated` date present (we only verify the line, not the value).
        assert "updated:" in text


class TestUpsertConceptPage:
    def test_creates_new_concept_page(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        c = ConceptItem(
            name="circadian rhythm",
            definition="24-hour biological cycle governing wakefulness",
            timestamp="00:05:00",
        )
        path = w.upsert_concept_page(c, episode_meta=meta)
        text = path.read_text()
        assert path.parent == vault / "concepts"
        assert "type: concept" in text
        assert "circadian rhythm" in text
        assert "24-hour biological cycle" in text
        assert f"[[{meta.base_filename()}]]" in text

    def test_appends_mention_for_second_episode(self, vault: Path) -> None:
        meta1 = _episode_meta(episode_id="e1", title="A")
        meta2 = _episode_meta(episode_id="e2", title="B")
        c1 = ConceptItem("dopamine", "neurotransmitter", "00:00:10")
        c2 = ConceptItem("dopamine", "see prior episode", "00:00:20")
        w = WikiWriter(vault)
        w.upsert_concept_page(c1, episode_meta=meta1)
        path = w.upsert_concept_page(c2, episode_meta=meta2)
        text = path.read_text()
        assert f"[[{meta1.base_filename()}]]" in text
        assert f"[[{meta2.base_filename()}]]" in text
        assert len(list((vault / "concepts").glob("*.md"))) == 1


class TestUpdateIndex:
    def test_adds_episode_under_episodes_section(self, vault: Path) -> None:
        meta = _episode_meta()
        w = WikiWriter(vault)
        w.update_index(
            new_episodes=[(meta.base_filename(), meta.title)],
            new_entities=[("Andrew Huberman", "Stanford neuroscientist")],
            new_concepts=[("circadian rhythm", "24-hour biological cycle")],
        )
        idx = (vault / "index.md").read_text()
        assert f"- [[{meta.base_filename()}]] — {meta.title}" in idx
        assert "[[Andrew Huberman]] — Stanford neuroscientist" in idx
        assert "[[circadian rhythm]] — 24-hour biological cycle" in idx
        # Total pages updated to 3 (1 episode + 1 entity + 1 concept).
        assert "Total pages: 3" in idx


class TestAppendLog:
    def test_appends_action_with_files_touched(self, vault: Path) -> None:
        w = WikiWriter(vault)
        w.append_log(
            action="analyze",
            subject="Channel — Episode One",
            files=[vault / "episodes" / "x.md", vault / "entities" / "y.md"],
        )
        log = (vault / "log.md").read_text()
        assert "analyze | Channel — Episode One" in log
        assert "x.md" in log
        assert "y.md" in log
