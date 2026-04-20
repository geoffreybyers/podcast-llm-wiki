# tests/unit/test_analysis_sections.py
from __future__ import annotations

import pytest

from podcast_llm.parsers.analysis_sections import (
    ConceptItem,
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
