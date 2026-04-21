# src/podcast_llm_wiki/parsers/analysis_sections.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

DELIM = "::"

VALID_RESOLUTIONS = frozenset({"unresolved", "newer-supersedes", "both-stand"})


class MalformedSectionError(ValueError):
    """Raised when a strict section line is not parseable.

    Per spec §6.2: the parser aborts the wiki update entirely on any malformed
    line — never partial-update. Applies to Entities, Concepts, and
    Contradictions.
    """


@dataclass
class EntityItem:
    name: str
    type: str
    context: str
    timestamp: str


@dataclass
class ConceptItem:
    name: str
    definition: str
    timestamp: str


@dataclass
class ContradictionItem:
    claim: str
    prior_episode: str  # base filename of existing episode page, or "none"
    resolution: str  # one of VALID_RESOLUTIONS
    timestamp: str


@dataclass
class ParsedAnalysis:
    entities: list[EntityItem] = field(default_factory=list)
    concepts: list[ConceptItem] = field(default_factory=list)
    contradictions: list[ContradictionItem] = field(default_factory=list)
    verification_todos: list[str] = field(default_factory=list)


_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_TIMESTAMP_RE = re.compile(r"^\[?(\d{2}:\d{2}:\d{2})\]?$")


def _extract_section(lines: list[str], heading: str) -> list[str]:
    """Return the body lines (no heading, no trailing blanks) of ``## heading``.

    If the heading isn't present, returns []. Stops at the next ``##`` heading.
    """
    target = heading.strip().lower()
    in_section = False
    out: list[str] = []
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            if in_section:
                break
            if m.group(1).strip().lower().startswith(target):
                in_section = True
                continue
        elif in_section:
            out.append(line)
    # Strip leading/trailing blank lines.
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _parse_timestamp_field(raw: str) -> str:
    raw = raw.strip()
    m = _TIMESTAMP_RE.match(raw)
    if not m:
        raise ValueError(f"timestamp must look like [HH:MM:SS], got: {raw!r}")
    return m.group(1)


def _parse_entity_line(line: str) -> EntityItem:
    if not line.startswith("- "):
        raise MalformedSectionError(
            f"entities: line must start with '- ', got: {line!r}"
        )
    body = line[2:]
    parts = [p.strip() for p in body.split(DELIM)]
    if len(parts) != 4:
        raise MalformedSectionError(
            f"entities: expected 4 fields separated by ' :: ', got {len(parts)} in line: {line!r}"
        )
    name, etype, context, ts = parts
    try:
        ts_parsed = _parse_timestamp_field(ts)
    except ValueError as e:
        raise MalformedSectionError(f"entities: {e} in line: {line!r}") from e
    return EntityItem(name=name, type=etype, context=context, timestamp=ts_parsed)


def _parse_concept_line(line: str) -> ConceptItem:
    if not line.startswith("- "):
        raise MalformedSectionError(
            f"concepts: line must start with '- ', got: {line!r}"
        )
    body = line[2:]
    parts = [p.strip() for p in body.split(DELIM)]
    if len(parts) != 3:
        raise MalformedSectionError(
            f"concepts: expected 3 fields separated by ' :: ', got {len(parts)} in line: {line!r}"
        )
    name, definition, ts = parts
    try:
        ts_parsed = _parse_timestamp_field(ts)
    except ValueError as e:
        raise MalformedSectionError(f"concepts: {e} in line: {line!r}") from e
    return ConceptItem(name=name, definition=definition, timestamp=ts_parsed)


def _parse_contradiction_line(line: str) -> ContradictionItem:
    if not line.startswith("- "):
        raise MalformedSectionError(
            f"contradictions: line must start with '- ', got: {line!r}"
        )
    body = line[2:]
    parts = [p.strip() for p in body.split(DELIM)]
    if len(parts) != 4:
        raise MalformedSectionError(
            f"contradictions: expected 4 fields separated by ' :: ', got {len(parts)} in line: {line!r}"
        )
    claim, prior_episode, resolution, ts = parts
    if resolution not in VALID_RESOLUTIONS:
        raise MalformedSectionError(
            f"contradictions: resolution must be one of {sorted(VALID_RESOLUTIONS)}, got {resolution!r} in line: {line!r}"
        )
    try:
        ts_parsed = _parse_timestamp_field(ts)
    except ValueError as e:
        raise MalformedSectionError(f"contradictions: {e} in line: {line!r}") from e
    return ContradictionItem(
        claim=claim,
        prior_episode=prior_episode,
        resolution=resolution,
        timestamp=ts_parsed,
    )


def parse_analysis(text: str) -> ParsedAnalysis:
    """Parse the strict Entities/Concepts sections from a finished analysis.

    On any malformed line in either section, raises MalformedSectionError
    immediately. The wiki writer then aborts wiki update entirely.
    """
    lines = text.splitlines()

    entities: list[EntityItem] = []
    for raw in _extract_section(lines, "Entities"):
        if not raw.strip():
            continue
        entities.append(_parse_entity_line(raw))

    concepts: list[ConceptItem] = []
    for raw in _extract_section(lines, "Concepts"):
        if not raw.strip():
            continue
        concepts.append(_parse_concept_line(raw))

    contradictions: list[ContradictionItem] = []
    for raw in _extract_section(lines, "Contradictions"):
        if not raw.strip():
            continue
        contradictions.append(_parse_contradiction_line(raw))

    verification_todos: list[str] = []
    for raw in _extract_section(lines, "Verification Todos"):
        stripped = raw.strip()
        if stripped.startswith("- "):
            verification_todos.append(stripped[2:].strip())

    return ParsedAnalysis(
        entities=entities,
        concepts=concepts,
        contradictions=contradictions,
        verification_todos=verification_todos,
    )
