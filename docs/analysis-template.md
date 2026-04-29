# Podcast Analysis Template

> Canonical structure for `/analyze-podcast` output. The wiki writer parses
> the `## Entities`, `## Concepts`, and `## Contradictions` sections
> programmatically using the strict ` :: ` delimiter. Any other section may be
> edited freely; format below is the contract. Angle-bracket tokens
> (`<name>`, `<claim>`, etc.) are placeholders — substitute the actual value,
> never emit the literal word.

# {{channelTitle}} — {{title}}

## TL;DR

Three sentences. The thesis, the new thing, why it matters.

## Key Insights

5–10 insights, ranked by novelty (not order of appearance). Each:

- **Bolded claim:** one-paragraph explanation. [HH:MM:SS]

## Critical Pass

- **Steelman(s) of the strongest argument(s) (1–3):** When the episode contains
  multiple distinct theses (panel disagreements, guests making several
  independent claims), steelman each separately and label by speaker. When the
  episode has one clear central thesis, just one. Cap at 3 — beyond that,
  candidates belong in *Key Insights*, not here. Never pad.
- **Weak claims / unsupported assertions:** ...
- **Factual claims requiring verification:** [bullet list]
- **Contradictions with prior episodes (if any):** `[[wikilinks]]` to other episode pages.

## Entities

Strict `::`-delimited format. Four fields: name, type, one-line context, timestamp.

```
- <name> :: <type: person|org|study|product> :: <1-line context> :: [HH:MM:SS]
```

Example:

```
- Chamath Palihapitiya :: person :: Bestie arguing for Iran JCPOA revival :: [00:34:12]
```

Only include entities meeting the page-creation thresholds in SCHEMA.md
(2+ episodes OR central to one episode). Conservative bias: skip if unsure.

## Concepts

Strict `::`-delimited format. Three fields: name, one-line definition, timestamp.

```
- <name> :: <1-line definition> :: [HH:MM:SS]
```

Example:

```
- Sedation hypothesis :: Claim that porn acts as anxiolytic rather than dopamine addiction :: [01:12:45]
```

## Contradictions

Strict `::`-delimited format. Four fields: the actual contradicting claim,
the base filename of the prior episode page in `<vault>/index.md` (or `none`
for a contradiction internal to this episode), the resolution
(`unresolved | newer-supersedes | both-stand`), and the timestamp.

```
- <claim> :: <prior_episode_base_filename> :: <resolution> :: [HH:MM:SS]
```

Example:

```
- Sacks now backs JCPOA revival after opposing it on prior episode :: All-In-Iran-Greenland-Energy :: newer-supersedes :: [01:12:04]
```

Empty section allowed (omit or leave no bullets) when no contradictions found.

## Verification Todos

Bullet list. No `::` grammar — parser only requires the `- ` prefix.

```
- <claim> — <why it matters>
```

## Follow-ups

- Open questions
- Things to look up
- Episodes to revisit
