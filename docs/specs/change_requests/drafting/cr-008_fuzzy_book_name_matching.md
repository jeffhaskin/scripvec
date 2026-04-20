---
id: 008
title: Fuzzy / typo-tolerant book name matching for the reference parser
status: drafting
created: 2026-04-20
updated: 2026-04-20
references:
  - cr-001_vector_search_mvp.md
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/010_accepted_strict_canonical_reference_parser.md
  - docs/specs/adrs/013_accepted_free_text_query_reference_extraction.md
---

# CR-008: Fuzzy / typo-tolerant book name matching for the reference parser

## Summary

Relax the strict-canonical-only book-name matching locked by ADR-010 to also accept near-misses — common abbreviations (`1 Ne`, `DC`), case variants (`1 nephi`, `1 NEPHI`), and small typos (`Almma`, `Nehpi`) — by mapping them onto the canonical book table at parse time. The strict canonical grammar of ADR-010 remains the *target*; this CR adds an alias / fuzz layer in front of it.

## Motivation

ADR-010 deliberately locks the parser to canonical-only book names so the MVP surface is small, the test matrix is bounded, and "we don't understand this input" is a real bug per ADR-001. That posture is correct for the engineer-as-primary-user MVP. It is friction for any user (or agent) who types the conventional shorthand or makes a one-character typo.

Why it might be worth the cost later:

- The shorthand forms (`1 Ne`, `DC`, `D and C`) appear constantly in scriptural commentary and citation prose. A pasted citation from any source is likely to use them.
- ADR-013's free-text extractor would also gain coverage: `"see DC 88:118"` would extract today only if the canonical form `D&C 88:118` happened to appear; with fuzz it would extract from the natural prose form.
- Typo tolerance is a small UX win that costs little if implemented carefully.

Why it is non-trivial:

- Fuzz introduces ambiguity. `Mor` could be Mormon or Moroni. `Hel` could be Helaman (one entry) but is at least unambiguous. Disambiguation rules accumulate.
- Silent acceptance of a guess violates ADR-001's fail-loud posture unless the disambiguation is deterministic and the alias map is auditable.
- A fuzz layer that accepts too much will silently rebind a reference the user did not mean.

## Proposed change

### Mechanism (sketch — not yet decided)

Two layers, in this order:

1. **Alias table.** A pinned mapping from common abbreviations and case variants (`1 ne`, `1 NEPHI`, `dc`, `d and c`, `d&c`) to canonical book names. Lookup is case-insensitive against this table; a hit produces an unambiguous canonical book name. The table is data, not heuristics.
2. **Fuzz layer (optional, gated).** For inputs that miss the alias table, an edit-distance match against the union of canonical names + alias keys. Accept only if exactly one canonical name is within a small edit distance threshold; otherwise raise per ADR-001. The threshold is a configurable value, not stipulated here.

The strict canonical grammar of ADR-010 is the target — both layers produce a canonical book name that the existing parser then consumes. The single-reference, range, and list grammars (ADR-010, ADR-011, ADR-012) are unchanged.

### Toggle and defaults

- A new `--fuzz {strict|alias|fuzzy}` flag on `scripvec query` and a matching keyword arg on `retrieval.query()`.
- `strict` (the ADR-010 default) — alias and fuzz both off; only verbatim canonical names accepted.
- `alias` — alias table on, fuzz off. The "permissive but auditable" middle ground; recommended default if this CR ships.
- `fuzzy` — alias table on, edit-distance fuzz on. Recommended only when the engineer explicitly opts in; the failure mode of silently rebinding a typo to the wrong book is real.

Default level (`strict` vs `alias`) is **deferred** — it is decided after the alias table is authored and shaken out against representative input.

### Failure handling (ADR-001)

- Alias table miss with fuzz off → raise (same as today's strict-only behavior).
- Fuzz layer ambiguous match (more than one canonical within threshold) → raise, listing the candidates.
- Fuzz layer accepted (exactly one match within threshold) → log the resolution at info level for auditability; proceed with the canonical name.
- Free-text extraction (ADR-013) inherits the same fuzz settings; an extracted candidate that resolves via fuzz is logged as such in the query log.

## Open questions

- **Alias table scope.** Just the well-known shorthand forms, or also non-LDS scriptural conventions (e.g., `Doctrine and Covenants` spelled out)? A bigger table is more permissive but more maintenance.
- **Edit-distance metric.** Levenshtein, Damerau-Levenshtein, Jaro-Winkler? Each produces slightly different ambiguity profiles for short strings.
- **Fuzz only on the book token, or also on chapter / verse numerics?** Almost certainly only the book token — typo-tolerance on chapter / verse numbers introduces unbounded ambiguity.
- **Should the fuzz layer also fire on the canonical book table directly** (so a typo of a canonical name resolves), or only on the alias keys?
- **Eval impact.** Does fuzz materially change the recall numbers from the held-out query set, or is it a pure UX win invisible to eval?

## Impact on referenced docs

- **ADR-010:** this CR proposes a relaxation of ADR-010's strict-only posture. If accepted, ADR-010 either gets amended with the alias / fuzz carve-out, or is *superseded* by a new ADR that incorporates the relaxation. The split-ADR structure of ADRs 010–014 was chosen specifically to make this kind of localized supersession clean.
- **ADR-013:** the extractor's grammar tightens or loosens with the parser; whatever the parser accepts in `--fuzz` mode, the extractor accepts in extraction.
- **ADR-001:** the fuzz layer's ambiguity-raise and audit-log behavior are explicit applications of fail-loud; the ADR-001 posture is honored.
- **ADR-007:** the new `--fuzz` flag and any added log fields are additive schema changes, consistent with the agent contract's evolution rules.

## Decision

Not yet decided. Drafting; gated on the engineer choosing to widen the parser surface beyond the ADR-010 strict baseline.

## Audit log

- 2026-04-20 — created as `drafting`. Captured at the engineer's request while ADRs 010–014 were locking the strict-canonical reference subsystem; explicitly named as a future relaxation path so the strict default is not foreclosed.
