# tests/unit/test_analysis_sections.py
from __future__ import annotations

import pytest

from podcast_llm_wiki.parsers.analysis_sections import (
    ConceptItem,
    ContradictionItem,
    EntityItem,
    MalformedSectionError,
    parse_analysis,
)

GOOD = """\
# Channel — Episode

## TL;DR
Sentence one. Sentence two. Sentence three.

## Key Insights (5–10)
- **Claim:** explanation [00:01:23]

## Critical Pass
- **Steelman:** ...

## Entities
- Andrew Huberman :: person :: Stanford neuroscientist hosting :: [00:00:30]
- Stanford University :: org :: Affiliated institution :: [00:01:10]

## Concepts
- circadian rhythm :: 24-hour biological cycle governing wakefulness :: [00:05:00]
- dopamine :: neurotransmitter linked to motivation :: [00:08:42]

## Contradictions
- Claims X contradicts prior position on X :: Channel - Prior Episode :: unresolved :: [00:30:00]
- Internal contradiction within this episode :: none :: both-stand :: [01:10:00]

## Verification Todos
- Effect size on meditation study — the 40% figure is cited without source
- Claim that SAT has "no predictive validity" — check population vs sample

## Follow-ups
- ...
"""


def test_parses_entities() -> None:
    parsed = parse_analysis(GOOD)
    assert len(parsed.entities) == 2
    e0 = parsed.entities[0]
    assert isinstance(e0, EntityItem)
    assert e0.name == "Andrew Huberman"
    assert e0.type == "person"
    assert e0.context == "Stanford neuroscientist hosting"
    assert e0.timestamp == "00:00:30"


def test_parses_concepts() -> None:
    parsed = parse_analysis(GOOD)
    assert len(parsed.concepts) == 2
    c0 = parsed.concepts[0]
    assert isinstance(c0, ConceptItem)
    assert c0.name == "circadian rhythm"
    assert c0.definition == "24-hour biological cycle governing wakefulness"
    assert c0.timestamp == "00:05:00"


def test_rejects_malformed_entity_line() -> None:
    bad = GOOD.replace(
        "- Andrew Huberman :: person :: Stanford neuroscientist hosting :: [00:00:30]",
        "- Andrew Huberman | person | bad delimiters | [00:00:30]",
    )
    with pytest.raises(MalformedSectionError) as exc:
        parse_analysis(bad)
    assert "entities" in str(exc.value).lower()
    # Message should include the offending line for the user to fix.
    assert "Andrew Huberman" in str(exc.value)


def test_rejects_entity_with_wrong_field_count() -> None:
    bad = GOOD.replace(
        "- Andrew Huberman :: person :: Stanford neuroscientist hosting :: [00:00:30]",
        "- Andrew Huberman :: person :: missing context-and-timestamp",
    )
    with pytest.raises(MalformedSectionError):
        parse_analysis(bad)


def test_rejects_concept_with_wrong_field_count() -> None:
    bad = GOOD.replace(
        "- circadian rhythm :: 24-hour biological cycle governing wakefulness :: [00:05:00]",
        "- circadian rhythm :: only-definition",
    )
    with pytest.raises(MalformedSectionError):
        parse_analysis(bad)


def test_missing_entities_section_returns_empty_list() -> None:
    no_entities = GOOD.split("## Entities")[0] + GOOD.split("## Concepts", 1)[1]
    no_entities = "## Concepts" + no_entities
    parsed = parse_analysis(no_entities)
    assert parsed.entities == []


def test_blank_line_in_section_is_ok() -> None:
    spaced = GOOD.replace(
        "## Entities\n",
        "## Entities\n\n",
    )
    parsed = parse_analysis(spaced)
    assert len(parsed.entities) == 2


def test_parses_contradictions() -> None:
    parsed = parse_analysis(GOOD)
    assert len(parsed.contradictions) == 2
    c0 = parsed.contradictions[0]
    assert isinstance(c0, ContradictionItem)
    assert c0.claim == "Claims X contradicts prior position on X"
    assert c0.prior_episode == "Channel - Prior Episode"
    assert c0.resolution == "unresolved"
    assert c0.timestamp == "00:30:00"
    # Internal contradictions use the literal 'none' sentinel.
    assert parsed.contradictions[1].prior_episode == "none"
    assert parsed.contradictions[1].resolution == "both-stand"


def test_parses_verification_todos() -> None:
    parsed = parse_analysis(GOOD)
    assert len(parsed.verification_todos) == 2
    assert parsed.verification_todos[0].startswith("Effect size on meditation")
    assert "SAT" in parsed.verification_todos[1]


def test_missing_contradictions_section_returns_empty_list() -> None:
    stripped = GOOD.split("## Contradictions")[0] + "## Follow-ups\n- ...\n"
    parsed = parse_analysis(stripped)
    assert parsed.contradictions == []
    assert parsed.verification_todos == []


def test_rejects_contradiction_with_wrong_field_count() -> None:
    bad = GOOD.replace(
        "- Claims X contradicts prior position on X :: Channel - Prior Episode :: unresolved :: [00:30:00]",
        "- Claims X :: too-few-fields :: [00:30:00]",
    )
    with pytest.raises(MalformedSectionError):
        parse_analysis(bad)


def test_rejects_contradiction_with_invalid_resolution() -> None:
    bad = GOOD.replace(
        "- Claims X contradicts prior position on X :: Channel - Prior Episode :: unresolved :: [00:30:00]",
        "- Claims X contradicts prior position on X :: Channel - Prior Episode :: maybe :: [00:30:00]",
    )
    with pytest.raises(MalformedSectionError) as exc:
        parse_analysis(bad)
    assert "resolution" in str(exc.value).lower()


def test_verification_todos_ignore_non_bullet_lines() -> None:
    # A stray paragraph inside the section (e.g., prose) should be ignored gracefully.
    mangled = GOOD.replace(
        "## Verification Todos\n- Effect size",
        "## Verification Todos\nSome prose here.\n- Effect size",
    )
    parsed = parse_analysis(mangled)
    assert len(parsed.verification_todos) == 2
