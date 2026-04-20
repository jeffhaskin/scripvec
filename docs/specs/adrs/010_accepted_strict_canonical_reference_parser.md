# ADR-010: Reference parser accepts strict canonical citations only

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

`cr-001_vector_search_mvp.md` item 4 leaves open how tolerant the reference parser is when a user (or an agent) supplies a scriptural citation. Three rough postures: canonical-only, abbreviation-tolerant, fuzzy-matching. This ADR closes that question for the canonical-only posture and is intentionally narrow so it can be superseded in isolation if the engineer later wants to widen acceptance.

**Scope note — what this ADR does and does not lock.** This ADR locks the *grammar* and *strictness* of the reference parser for a single citation. Range syntax (ADR-011), list syntax (ADR-012), free-text extraction (ADR-013), and force-inclusion semantics (ADR-014) are scoped separately so each can be superseded in isolation. The pinned canonical book table is data that lives in `packages/reference/`; it is not a tunable config knob and is not stipulated here.

**Decision drivers:**

- Scripvec is a vector / hybrid retrieval surface first; reference-driven queries are a useful-but-secondary path. A strict parser keeps the surface minimal, the test matrix small, and matches ADR-001's "we don't understand this input" posture.
- A wider parser introduces ambiguity (e.g., `Mor` could be Mormon or Moroni). Disambiguation rules accumulate into a maintenance burden the MVP does not need.
- Fuzzy matching (Levenshtein / casefold) is a different decision with different failure modes and is captured as a future change request (`cr-008_fuzzy_book_name_matching.md`).

## Decision

The reference parser accepts **exactly** one grammar for a single citation:

- `<canonical_book> <chapter>:<verse>`
- `<canonical_book>` is a verbatim entry in the pinned canonical book table (case-sensitive).
- `<chapter>` and `<verse>` are positive integers without leading zeros.

The following are **rejected loudly** when the input is being parsed as a single reference:

- Abbreviations (`1 Ne`, `DC`, `D and C`, `Alm`).
- Alternative punctuation between chapter and verse (`.` for `:`, `,` for `:`, etc.).
- Case variants of the canonical book (`1 nephi`, `1 NEPHI`, `D&c`).
- Leading-zero chapter or verse numbers (`Alma 32:021`).
- Whitespace shapes other than ASCII space between book and chapter (no tab, no NBSP, no double-space — though leading and trailing whitespace on the input are stripped).
- Fuzzy / Levenshtein near-matches.

Per ADR-001, rejection is a raised error naming what was expected, not a silent coercion. A free-text query that is not being parsed as a single reference is governed by ADR-013, not this ADR — extraction has its own rules.

The pinned canonical book table is data inside `packages/reference/`. Adding new accepted strings (e.g., a future spelling that bcbooks adopts, or a new corpus that introduces new books) is a code-edit, not a config change.

## Consequences

**Positive:**

- The grammar is small enough to enumerate in a single page and test exhaustively.
- "Did the system understand my reference?" has a binary answer.
- No class of input silently misroutes — either the parser accepted it verbatim, or the user / agent got a clear error.
- Parser code stays under a few dozen lines; the test matrix is bounded by the size of the canonical book table.

**Negative:**

- A user who writes the conventional shorthand `1 Ne 3:7` gets an error rather than a graceful interpretation. This is a deliberate trade-off — the engineer is the primary user, agents are the secondary user, and both can be told the grammar — but it is friction that a hypothetical future GUI consumer would feel.
- Fuzzy matching of typos (`Almma 32:21`) is not available. A typo crashes the parse rather than producing a best-guess suggestion. Users / agents must type carefully or request fuzzy matching via the future CR.

## Validation

- Unit tests cover every accepted canonical book name (positive) and a representative set of explicitly rejected variants (`1 Ne`, `1 NEPHI`, `dc`, `Alma 32.21`, `Alma 32:021`) (negative).
- A grep across `packages/reference/` for any case-insensitive or fuzzy primitive (`.lower()`, `casefold`, `fuzz.`, `levenshtein`, `difflib`) is a coarse but useful lint for this ADR's strictness.

## Links

- `docs/specs/adrs/001_accepted_no_silent_failures.md` — the parser inherits fail-loud.
- `docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md` — strict, predictable input acceptance matches the agent-first contract.
- `docs/specs/adrs/011_accepted_reference_range_syntax_full_endpoints.md` — range grammar built on top of this single-reference grammar.
- `docs/specs/adrs/012_accepted_reference_list_syntax_semicolon_separated.md` — list grammar built on top of this single-reference grammar.
- `docs/specs/adrs/013_accepted_free_text_query_reference_extraction.md` — free-text extraction reuses this grammar.
- `cr-001_vector_search_mvp.md` — item 4, partially closed by this ADR.
- `cr-008_fuzzy_book_name_matching.md` — future CR that may relax the strictness this ADR locks.

## Conflicts surfaced

- **CR-001 item 4** explicitly mentions "abbreviations, alternate forms" as parser concerns. This ADR rejects both. CR-001 item 4 is updated at the same time this ADR is committed to record the strict-only decision and to point at this ADR.
- **None vs ADRs 001–009.** No conflicts.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — locked strict canonical citation grammar; rejected abbreviations, alternative punctuation, case variants, leading-zero numbers, fuzzy matching | Jeff Haskin |
