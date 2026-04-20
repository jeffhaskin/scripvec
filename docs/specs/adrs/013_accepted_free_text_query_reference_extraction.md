# ADR-013: Free-text queries are scanned for embedded references using the canonical grammar

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

`cr-001_vector_search_mvp.md` item 4 leaves open whether the system scans free-text queries (e.g., `"what does Alma 32:21 say about faith"`) for embedded scriptural references. Pure dense + BM25 retrieval may miss the cited verse because surface overlap is dominated by the wrapper words. Reusing the canonical reference grammar (ADRs 010–012) for an extraction pass closes that gap with bounded complexity — no new parser, no second grammar.

This ADR is scoped to *extraction* alone — what is scanned, what is extracted, what is rejected. The downstream behavior on extracted references (force-inclusion in the result set) is locked separately by ADR-014 so each can be superseded independently.

**Decision drivers:**

- A single grammar for both standalone parsing and free-text extraction means one parser, one rule set, one debugging surface.
- Extraction is a pre-retrieval step that is cheap and deterministic; it does not interfere with the organic dense + BM25 + RRF path.
- A query containing nothing the grammar recognizes is a valid free-text query, not a malformed reference; that case must not raise.

## Decision

Every query handed to `retrieval.query()` is scanned for substrings matching:

- The single-reference grammar of ADR-010, **and**
- The range grammar of ADR-011.

Lists (ADR-012) are **not** extracted as a unit from inside a free-text query; each list item is independently extracted as a separate match. This keeps the extractor's matching to two productions instead of three.

The extractor uses the **same canonical grammar** as the standalone-reference parser — same canonical book table, same case-sensitivity, same delimiter rules. There is no second parser, no looser rules for extraction.

Behavior on each input class:

- A query that contains **no matching substring** goes through unchanged. The organic retrieval path runs as if no extraction were enabled. This is **not a silent failure** — it is the correct behavior when the input contains nothing the grammar recognizes as a reference.
- A query whose extracted candidate parses grammatically (`Alma 32:99`) but **does not resolve to a real verse** raises per ADR-001. A grammatical-looking reference that does not exist is an upstream bug or a typo, not a queryable state.
- A free-text fragment that does not match the grammar (e.g., `Alma 32`, `Alma chapter 32`, `the 32nd chapter of Alma`) is simply not extracted. The grammar is the authority on what counts as a candidate.
- An extracted candidate that *partially* matches (e.g., `Alma 32:21` followed immediately by garbage characters): the extractor consumes only the longest matching substring; the remaining characters stay in the query as text. This is a parsing rule, not a coercion of input.

The extractor returns a flat ordered set of resolved verses (deduplicated in canonical document order, like ADR-012's list resolution). Downstream behavior on this set is governed by ADR-014.

The query log captures the extraction outcome — extracted reference substrings, resolved verse ids, dedupe collisions — so downstream eval can attribute result quality to extraction vs. organic retrieval.

## Consequences

**Positive:**

- The same grammar serves both standalone parsing and free-text extraction. One parser, one rule set, one debugging surface.
- Extraction adds a small, deterministic pre-retrieval step. It does not perturb the organic retrieval path.
- The "no candidate found, no raise" rule keeps the system usable for the common case (most queries are pure prose with no embedded references).

**Negative:**

- A typing user who writes `Alma 32:99` (typo: chapter only goes to 43) crashes the whole query rather than degrading to organic-only. This is the right call per ADR-001 (silent fallback would mask real bugs), but it is a sharper UX than a permissive system.
- An overly aggressive extraction match could fire on incidental substrings that *look* like references in some unlikely contexts. The canonical-only grammar (ADR-010) makes this very rare in practice — `<canonical_book> <int>:<int>` does not show up in normal English prose by accident.
- Cross-book / cross-chapter ranges inside a free-text query expand to potentially large verse sets. The range-expansion size cap (a config-resident value per ADR-011) caps the worst case.

## Validation

- Unit tests cover: a query with no grammatical candidate (no extraction, no raise); a query with one single reference (one extraction); a query with one range (one extraction whose resolution is the range); a query with multiple references (multiple extractions); a query with a grammatical-but-nonexistent reference (raise); a query with a partial-match fragment (extract longest substring, leave the rest as text).
- The canonical book table used by the extractor is asserted to be the same instance as the one used by the standalone parser.
- Query-log entries include the `extracted_references` field per CR-001 / former-CR-002 logging contract.

## Links

- `docs/specs/adrs/010_accepted_strict_canonical_reference_parser.md` — single-reference grammar reused for extraction.
- `docs/specs/adrs/011_accepted_reference_range_syntax_full_endpoints.md` — range grammar reused for extraction.
- `docs/specs/adrs/012_accepted_reference_list_syntax_semicolon_separated.md` — list grammar is *not* applied during extraction; each item is extracted independently.
- `docs/specs/adrs/001_accepted_no_silent_failures.md` — grammatical-but-nonexistent extracted references raise.
- `docs/specs/adrs/014_accepted_extracted_reference_force_inclusion_in_results.md` — what is done with the extracted set.
- `cr-001_vector_search_mvp.md` — item 4, partially closed by this ADR.

## Conflicts surfaced

- **None vs ADRs 001–012.** No conflicts.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — locked free-text reference extraction using the canonical single-reference and range grammars; rejected list grammar inside free text; defined fail-loud and no-candidate behaviors | Jeff Haskin |
