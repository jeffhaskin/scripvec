# ADR-011: Reference range syntax requires a full canonical reference on both sides of the dash

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

The reference parser locked by ADR-010 accepts a single canonical citation. Real-world citation prose also routinely names *ranges* of verses. The conventional shorthand (`Alma 32:21-23`, or with cross-chapter `Alma 32:21-33:5`) requires special-case parsing of the dash and contextual carry of the book name across the dash. A full-reference-both-sides form (`Alma 32:21 - Alma 32:23`) is parser-trivial: two independent invocations of the ADR-010 single-reference parser separated by a delimiter check.

This ADR is scoped to the range *syntax* alone so it can be superseded in isolation if the engineer later decides to accept shorthand ranges in addition to or instead of the full-reference form.

**Decision drivers:**

- Full-reference-both-sides has zero parser ambiguity. The single-ref parser is invoked twice.
- Cross-chapter and (syntactically) cross-book ranges fall out for free; no special handling.
- Any future shorthand acceptance is additive — it would not invalidate the full-reference form, only extend the grammar — so locking the full-reference form does not foreclose a later relaxation.

## Decision

A range is exactly:

- `<canonical_ref> - <canonical_ref>`
- where each `<canonical_ref>` is a full canonical reference parseable by ADR-010,
- and the delimiter is an ASCII hyphen-minus (`-`) with one or more ASCII spaces on each side. Canonical written form has exactly one space on each side.

The following are rejected:

- Shorthand ranges (`Alma 32:21-23`, `Alma 32:21-33:5`).
- En-dash (`–`), em-dash (`—`), or hyphen with no surrounding whitespace.
- Ranges with a partial endpoint (a chapter:verse pair without a book token).

Cross-chapter and cross-book ranges are **syntactically valid** because the grammar imposes no relationship between the endpoints' books or chapters. Whether a given cross-book range makes scriptural sense is the caller's concern, not the parser's.

A range whose endpoints parse but whose order is reversed in canonical document order (B precedes A) raises per ADR-001 — that is a malformed input, not a queryable state. An empty range is not representable.

Range *resolution* (expanding a range to its inclusive set of verses in canonical document order) is an implementation concern in `packages/reference/`. A range-expansion size cap, if introduced, is a value that lives in the project-root config file per `pl-001_adrs_lock_policies_not_values.md`, not in this ADR.

## Consequences

**Positive:**

- The parser change to support ranges is one extra production: "two single-refs separated by ` - `." No book-name carry, no dash special-casing.
- Cross-chapter and cross-book ranges are free.
- A future relaxation to accept shorthand ranges is additive; this ADR does not block it.

**Negative:**

- A user who writes the conventional shorthand `Alma 32:21-23` gets an error. Documented friction; same trade-off as ADR-010.
- The verbose form is longer to type.

## Validation

- Unit tests cover the full-reference range form (positive) and every shorthand variant (`Alma 32:21-23`, `Alma 32:21-33:5`, en-dash, em-dash, no-whitespace) (negative).
- Tests cover cross-chapter, cross-book, and reversed-order cases.

## Links

- `docs/specs/adrs/010_accepted_strict_canonical_reference_parser.md` — the single-reference grammar this ADR builds on.
- `docs/specs/adrs/001_accepted_no_silent_failures.md` — reversed-order ranges raise.
- `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md` — any range-expansion-size cap is config-resident.
- `cr-001_vector_search_mvp.md` — item 4, partially closed by this ADR.

## Conflicts surfaced

- **None vs ADRs 001–010.** No conflicts.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — locked full-reference-both-sides range syntax with ASCII-hyphen delimiter; rejected shorthand ranges, en-dash, em-dash, partial endpoints, and reversed-order ranges | Jeff Haskin |
