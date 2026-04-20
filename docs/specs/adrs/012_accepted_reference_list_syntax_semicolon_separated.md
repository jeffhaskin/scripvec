# ADR-012: Reference list syntax uses semicolon as the separator

## Status

ACCEPTED

## Created

2026-04-20

## Modified

2026-04-20

## Supersession

*Supersedes:* none
*Superseded by:* none

## Date

2026-04-20

## Deciders

Jeff Haskin — engineer, sole decision authority at time of record.

## Context and Decision Drivers

The reference parser locked by ADR-010 accepts a single canonical citation; ADR-011 extends it with a range form. Citation prose also routinely names *lists* of citations (`Alma 32:21; Moroni 7:5`). A list separator is needed; the candidates are comma, semicolon, and newline.

This ADR is scoped to the list separator alone so the choice can be superseded in isolation.

**Decision drivers:**

- Semicolon is the conventional list separator in citation prose (cf. footnotes in scripture commentary, legal citations).
- Comma is reserved for *inside* certain reference grammars in some scriptural conventions (e.g., chapter,verse in some non-LDS traditions); using it as a list separator would create avoidable ambiguity.
- Newline is implicit in many text inputs but is unfit for single-line CLI flags and free-text queries; it is rejected as a list separator at this layer.

## Decision

A list of references is one or more references or ranges (per ADR-010 and ADR-011) separated by `;`:

- `<item>(;\s*<item>)*`
- where each `<item>` is either a single reference (ADR-010) or a range (ADR-011).
- Whitespace around the semicolon is permitted; the canonical written form has a single space *after* each semicolon and no space before.

Lists are not nested. A list of lists is not a thing the grammar describes.

A malformed item raises per ADR-001, naming which item failed (by 1-based ordinal position in the list).

The result of parsing a list is a flat ordered set of resolved verses, deduplicated in canonical document order. Duplicates within the input list are silently collapsed; this is a normalization of *valid* but redundant input, not a coercion of malformed input, and is therefore not a fail-loud case.

## Consequences

**Positive:**

- The parser change to support lists is one extra production: split on `;`, parse each item independently.
- Mixed lists of single refs and ranges (`A; B - C; D`) work without grammar additions.
- Comma stays available for any future reference grammar that needs it internally.

**Negative:**

- A user who writes a comma-separated list (`Alma 32:21, Moroni 7:5`) gets an error. Documented friction.
- Newline-separated lists in pasted prose are not handled at this layer; the caller must replace newlines with semicolons before passing.

## Validation

- Unit tests cover lists of single refs, lists of ranges, mixed lists, and lists with only one item (which must be equivalent to the bare single-ref or range parse).
- Tests cover comma-separated input (negative), newline-separated input (negative), and empty list items (negative — `A; ; B` raises).
- Tests cover dedupe of duplicates within a list — `Alma 32:21; Alma 32:21` resolves to a one-element set.

## Links

- `docs/specs/adrs/010_accepted_strict_canonical_reference_parser.md` — single-reference grammar that list items must satisfy.
- `docs/specs/adrs/011_accepted_reference_range_syntax_full_endpoints.md` — range grammar that list items may use.
- `docs/specs/adrs/001_accepted_no_silent_failures.md` — malformed list items raise.
- `cr-001_vector_search_mvp.md` — item 4, partially closed by this ADR.

## Conflicts surfaced

- **None vs ADRs 001–011.** No conflicts.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — locked semicolon as the reference list separator; rejected comma and newline; required dedupe of valid duplicates | Jeff Haskin |
