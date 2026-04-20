---
id: 011
title: CLI scripture scope filters — volume, book, and chapter-or-section range
status: staged
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/specs/adrs/010_accepted_strict_canonical_reference_parser.md
  - docs/specs/adrs/011_accepted_reference_range_syntax_full_endpoints.md
  - docs/specs/adrs/012_accepted_reference_list_syntax_semicolon_separated.md
  - docs/specs/adrs/014_accepted_extracted_reference_force_inclusion_in_results.md
  - docs/principles/001_vector_retrieval.md
---

# CR-011: CLI scripture scope filters — volume, book, and chapter-or-section range

## Summary

Add three composable scope filters to `scripvec query`: `--volume`, `--book`, and `--range`. Filters compose hierarchically (coarse to fine) and drop out-of-scope hits before top-K is taken. They are structural / metadata filters, not score-based, and they do not change how retrieval itself runs — the index is queried in full, then scope is applied.

## Motivation

Scripture study is frequently scoped. A reader studying the atonement in the Book of Mormon does not want D&C verses leaking in; a reader reviewing Alma's sermon on faith does not want Isaiah chapters of 2 Nephi dominating. Today's CLI has no scope control beyond `--k`; it treats the whole index as the search space for every query.

The three levels correspond to the natural structure of LDS scripture:

- **Volume** — Book of Mormon, Doctrine and Covenants (and, later, additional canonical volumes).
- **Book** — the named books inside a volume. Applies to volumes that subdivide (Book of Mormon has 15 books); does not apply to volumes that do not (D&C has sections only).
- **Range** — a chapter / section range or list within a volume or book, expressed in the ADR-010 canonical reference grammar.

Each level is independently useful and each is also useful in combination (e.g., volume + range to scope to "Alma 30–42" without repeating the volume).

## Proposed change

### Flags

- `--volume <name>` — canonical volume name (`book_of_mormon`, `doctrine_and_covenants`, etc.). Omitted means "all volumes in the index."
- `--book <name>` — canonical book name per ADR-010. Omitted means "all books in the scoped volume(s)."
- `--range <reference_or_list>` — a chapter/section range or list per ADR-010/ADR-011/ADR-012. Examples: `Alma 30-42`, `D&C 76`, `2 Nephi 31:1-21`, `Alma 32; 34:15-41`.

All three flags can be present on the same query. They compose hierarchically.

### Semantics

1. Retrieval runs over the full index. Scope is applied *after* retrieval, before the top-K cut.
2. A hit is kept iff it falls inside the intersection of the supplied scope filters.
3. ADR-014's force-inclusion of extracted references still applies — but only within the scoped set. A reference extracted from the query text that falls outside the scope is dropped with a log entry (ADR-014's force is about *including*, not about *overriding scope*).
4. Enough buffer is retrieved internally so that top-K is still filled after scope drops. If the scope is small enough that fewer than K hits survive, the response returns however many survive (possibly zero).

### Volume / book / range consistency

- `--book` with a volume that has no books (D&C) is a user error per ADR-001. Error message is specific: `"D&C has sections, not books; use --range instead"`.
- `--book <name>` with `--volume <v>` where `<name>` does not belong to `<v>` is a user error per ADR-001.
- `--range <ref>` with `--volume` or `--book` that contradicts the reference (e.g., `--book alma --range "Helaman 5"`) is a user error per ADR-001.
- Unknown volume name → raise.
- Unknown book name → raise. (If cr-008 ships and fuzz is enabled, fuzz resolves first; see cr-008 for interaction.)
- Malformed range → raise per ADR-010's grammar.

### CLI surface

- Three additive flags on `scripvec query`.
- The `query` JSON response gains a `scope` field echoing the applied filters (with canonical-form names), so callers can verify what was scoped:

```json
{
  "scope": {"volume": "book_of_mormon", "book": "alma", "range": "30-42"},
  ...
}
```

- Fields in `scope` are `null` when the corresponding flag was not supplied.

### Why post-retrieval, not pre-retrieval

Two options were considered for *where* scope is applied:

1. **Pre-retrieval:** narrow the index before search. Requires either per-scope indexes (storage blow-up) or SQL-level filtering on the vector search (couples retrieval to the scope predicate).
2. **Post-retrieval:** search the full index, filter the results. Simpler; the retrieval layer stays unchanged.

Post-retrieval is the first cut. It wastes some work (hits that would have scored high get dropped) but keeps the retrieval stack clean. If profiling later shows the waste is meaningful, a pre-retrieval path can be added as a separate CR.

## Impact on referenced docs

- **ADR-010, ADR-011, ADR-012:** `--range` is a direct consumer of the canonical reference grammar. No change to the grammar.
- **ADR-014:** force-inclusion behavior is preserved, but bounded by scope. This is a tightening of ADR-014's scope of effect, recorded here so a future reader sees the interaction.
- **ADR-007:** three additive flags; `scope` is an additive field in the response. No breaking change.
- **ADR-001:** every scope-consistency failure is a loud failure with a specific message.
- **Principle 001:** eval harness gains the ability to stratify by scope (useful for diagnosing whether retrieval quality differs across volumes/books), though that is out of scope for this CR.

## Open questions

- Should `--volume` / `--book` / `--range` also be accepted as environment variables for default-scoping across a terminal session? Probably not — per ADR-007 every invocation is self-contained. Flagged for completeness.
- How does `scripvec feedback` relate to scoped queries? A feedback entry should probably record the scope under which the hit was retrieved, so retroactive quality analysis can stratify by scope. Additive log field; decide when feedback schema is next touched.

## Decision

Staged.

## User stories (scrum)

*Channeled via the Scrum Lead persona (profession; `personas` DB).
The stakeholder asked for three composable scope filters. Before
decomposing I want to be sure the outcome is "a reader can narrow the
search space to the slice of scripture they are studying, with loud
failures when the scope is self-contradictory." The CR confirms that.
All stories below are vertical slices a user could observe end-to-end;
I have deliberately split scope-consistency errors and the scope-echo
field into their own stories because either can ship alone and each
delivers independent user-visible value.*

### Story A — Volume-scoped query

**When** a reader runs `scripvec query "..." --volume book_of_mormon`,
**then** the response contains only hits from the Book of Mormon.

Acceptance criteria:

- `--volume <name>` accepts a canonical volume name per ADR-010.
- Hits from any other volume are dropped after retrieval, before top-K.
- If fewer than K hits survive the scope, the response returns however
  many survive (possibly zero). The caller is not silently padded from
  out-of-scope results.
- Unknown volume name raises per ADR-001 with a specific message.
- Omitting `--volume` preserves today's behavior (all volumes).

### Story B — Book-scoped query inside a subdividing volume

**When** a reader runs `scripvec query "..." --book alma`,
**then** the response contains only hits from the book of Alma.

Acceptance criteria:

- `--book <name>` accepts a canonical book name per ADR-010.
- Book scope applies within whatever volume scope is in effect (or all
  volumes if no `--volume` was supplied and the book name is unique
  across volumes).
- Passing `--book` against a volume that has no books (D&C) raises with
  exactly the message `"D&C has sections, not books; use --range
  instead"` per ADR-001.
- Unknown book name raises per ADR-001. (If cr-008 ships and fuzz is
  enabled, fuzz resolves first; see cr-008 for interaction.)
- Passing `--book` for a book that does not belong to the supplied
  `--volume` raises per ADR-001.

### Story C — Range-scoped query inside a volume or book

**When** a reader runs `scripvec query "..." --range "Alma 30-42"`,
**then** the response contains only hits that fall inside Alma 30–42
inclusive.

Acceptance criteria:

- `--range <ref>` accepts any valid ADR-010 / ADR-011 / ADR-012
  reference or list (e.g., `Alma 30-42`, `D&C 76`, `2 Nephi 31:1-21`,
  `Alma 32; 34:15-41`).
- Malformed range raises per ADR-010's grammar (specific parse error,
  not a generic "invalid input").
- Range bounds are verse-inclusive where verses are specified and
  chapter-inclusive where they are not, matching ADR-011.
- A range that contradicts a supplied `--volume` or `--book` raises per
  ADR-001 (e.g., `--book alma --range "Helaman 5"`).

### Story D — Composed scope: volume + book + range

**When** a reader runs
`scripvec query "..." --volume book_of_mormon --book alma --range "30-42"`,
**then** the response contains only hits that fall inside the
intersection of all three filters.

Acceptance criteria:

- All three flags compose hierarchically: a hit is kept iff it falls
  inside every supplied filter.
- Any pair of the three flags must also work (volume+book,
  volume+range, book+range). A single flag in isolation is covered by
  Stories A/B/C.
- Internal retrieval widens the candidate pool enough that top-K is
  still filled after scope drops when the scoped slice is large enough
  to support it.

### Story E — Scope echoed in the query response

**When** a reader runs any scoped query,
**then** the response JSON has a `scope` object that shows the applied
filters in canonical form.

Acceptance criteria:

- `scope` is always present in the query response object.
- Each of `scope.volume`, `scope.book`, `scope.range` is the canonical
  normalized form of what was passed, or `null` if that flag was
  omitted.
- The field is additive per ADR-007 and does not break any existing
  consumer of the response.
- Example from the CR holds:
  `{"scope": {"volume": "book_of_mormon", "book": "alma", "range": "30-42"}}`.

### Story F — ADR-014 extracted references stay bounded by scope

**When** a reader runs a scoped query whose query text contains an
extracted reference that falls *outside* the supplied scope,
**then** the extracted reference is dropped from force-inclusion and
a log entry records the drop.

Acceptance criteria:

- Force-inclusion per ADR-014 still applies for extracted references
  that fall *inside* the scope.
- Extracted references outside the scope are dropped, not silently
  injected into the result set.
- A log entry records the dropped reference and the scope that excluded
  it, so a reader can see why force-inclusion did not take effect.
- Unscoped queries (no `--volume`, `--book`, or `--range`) preserve
  ADR-014's behavior unchanged.

### Story G — Loud failure on self-contradictory scope

**When** a reader supplies scope flags that contradict each other,
**then** the CLI exits non-zero with a specific, actionable error
message per ADR-001.

Acceptance criteria:

- `--book` against D&C → exact message
  `"D&C has sections, not books; use --range instead"`.
- `--book` whose canonical volume is not the supplied `--volume` →
  message names both the book and the conflicting volume.
- `--range` whose reference is outside the supplied `--volume` or
  `--book` → message names the conflicting filter and the reference.
- Unknown volume, unknown book, and malformed range each raise with
  their own distinct message.
- No scope-consistency failure is silent; all produce a non-zero exit
  and a message that names the specific conflict.

### Sequencing note (not prioritization)

The parser in ADR-010/011/012 is a prerequisite for Story C and
therefore for D; it is assumed already in place. Story E (scope echo)
is independent of A/B/C and can ship alongside any of them.
Story F depends on A/B/C existing first so there is a scope to bound
against. Story G depends on the catalog knowledge used by A/B/C but
its error-surfacing is otherwise independent. The stakeholder picks
what ships first; my job is to surface the dependencies, not order them.

## Beads plan (bead-planning persona)

*No dedicated "bead planning" persona exists in the `personas` DB as
of this CR (searches for "bead planning", "bead", "swarm-ready
dependency linked work items", and related queries all returned
distance > 1.0 against every profession and person in the DB). The
closest operational adjacency is the Scrum Lead's step 7 (sequence
for clarity, leave prioritization to the stakeholder) applied to a
work-item graph rather than a story list. The plan below is written
in that voice: take each user story from step 2 and split it into the
smallest executable work items the swarm can pick up, with explicit
dependency edges so `bv`'s PageRank/critical-path analysis has a
graph to score.*

*Gap surfaced in the final report so a "bead-planning" persona can be
authored separately if desired.*

### Plan principles

- **One bead = one pull request-sized change.** If a bead looks like
  two PRs, split it.
- **Dependencies are structural, not sequential preference.** A bead
  depends on another only if it cannot be merged without the other.
- **Acceptance criteria travel with the bead body**, copied from the
  parent story so the swarm does not have to chase back to the CR.
- **Parent-child edges link beads to the CR** via an epic or label so
  the scope of this CR is grepable after the fact.
- **Tests live in the same bead as the code they cover**, per the
  prevailing pattern in this repo's existing `sv-*` beads (e.g.,
  `retrieval/embed.py + test`).

### Shared foundation beads

**F1. Scope types and canonical normalization**
*Files:* `retrieval/scope.py` + test.
*What:* Define `Scope` dataclass with `volume | None`, `book | None`,
`range | None`. Canonicalize each field using the ADR-010 book/volume
catalog and the ADR-010/011/012 reference parser.
*Why:* Every later bead consumes this type. Splitting it out keeps
the consumers small.
*Depends on:* `reference/books.py`, `reference/reference.py` (both
already in the DB as `sv-y3n`, `sv-6ma`).
*Acceptance:* `Scope.from_flags(volume=..., book=..., range=...)`
returns a canonicalized `Scope` or raises a typed error.

**F2. Scope-consistency validation**
*Files:* `retrieval/scope.py` (extended) + test.
*What:* Validate that the three fields do not contradict each other.
Raise with the specific messages required by Story G: the D&C-books
message verbatim; book-not-in-volume; range-outside-volume-or-book;
unknown volume; unknown book; malformed range.
*Why:* ADR-001 requires loud, message-specific failures.
*Depends on:* F1.
*Acceptance:* every error case in Story G is covered by a unit test
that asserts the exact message substring.

**F3. Post-retrieval scope filter**
*Files:* `retrieval/scope_filter.py` + test.
*What:* Given a list of candidate hits (verse rows with volume / book
/ chapter / verse fields) and a canonical `Scope`, drop hits outside
the scope. Preserve order within kept hits.
*Why:* This is the engine Stories A/B/C/D all sit on.
*Depends on:* F1.
*Acceptance:* tests cover volume-only, book-only, range-only, and the
three pairwise compositions plus the triple; edge cases include
inclusive boundaries at chapter start / end and at verse-specified
range endpoints.

**F4. Retrieval buffer widening**
*Files:* `retrieval/query.py` (extend existing) + test.
*What:* Before applying scope, retrieve more than K candidates so the
top-K survives typical scope drops. Size of the buffer is a
configurable value living in the project-root config file per the
policy that ADRs do not stipulate numeric values.
*Why:* Without this, scoped queries under-fill top-K in the common
case.
*Depends on:* F3, `sv-il6` (existing `retrieval/query.py + test`).
*Acceptance:* a scoped query whose scope keeps more than K hits
returns exactly K; a scoped query whose scope keeps fewer than K
returns all that survive, not a pad.

### Story-slice beads

**A1. `--volume` flag wired into `scripvec query`**
*Files:* `cli/query_cmd.py` + test (contract test in
`cli/test_contracts.py`).
*What:* Thread a `--volume` flag through the Typer command, build a
`Scope(volume=...)` via F1, validate via F2, pass to the retrieval
path to apply F3 / F4. Pass-through unchanged when `--volume` is
absent.
*Depends on:* F1, F2, F3, F4, `sv-vt9`, `sv-aw1`.
*Acceptance:* Story A's acceptance criteria.

**B1. `--book` flag wired into `scripvec query`**
*Files:* `cli/query_cmd.py` + test.
*What:* Thread `--book`. Reuse F1/F2/F3.
*Depends on:* A1 (same CLI file; A1 establishes the pattern B1 mirrors).
*Acceptance:* Story B's acceptance criteria, including the D&C
message verbatim.

**C1. `--range` flag wired into `scripvec query`**
*Files:* `cli/query_cmd.py` + test.
*What:* Thread `--range`, accepting the full ADR-010/011/012 grammar.
Reuse F1/F2/F3.
*Depends on:* A1, `sv-6ma` (`reference/reference.py` grammar).
*Acceptance:* Story C's acceptance criteria, including all listed
example inputs parsing.

**D1. Composition contract test**
*Files:* `cli/test_contracts.py`.
*What:* Black-box tests for every pairwise and triple combination of
the three flags, asserting the intersection semantic.
*Depends on:* A1, B1, C1.
*Acceptance:* Story D's acceptance criteria.

**E1. `scope` echoed in query response JSON**
*Files:* `cli/query_cmd.py` (response shaping) + test.
*What:* Add `scope` object with canonical-form fields or `null`
per flag-absence. Additive per ADR-007.
*Depends on:* F1 (canonicalization), A1 (for a command to shape the
response of).
*Acceptance:* Story E's acceptance criteria; the CR's example JSON
roundtrips.

**F-story. ADR-014 extracted-reference bounding**
*Files:* `retrieval/query.py` + test.
*What:* Where ADR-014 force-inclusion runs, intersect the extracted
references with the `Scope` from F1 before forcing. Log dropped
references with their scope-conflict reason.
*Depends on:* F1, F3, `sv-il6`.
*Acceptance:* Story F's acceptance criteria; unscoped queries remain
byte-identical to pre-CR behavior.

**G1. Error-message contract tests**
*Files:* `cli/test_contracts.py`.
*What:* For each Story G failure case, assert non-zero exit and the
required message substring. This is a test-only bead; the messages
themselves are produced by F2.
*Depends on:* F2, A1, B1, C1.
*Acceptance:* Story G's acceptance criteria, exhaustively.

### Dependency graph (summary)

```
sv-y3n, sv-6ma ──► F1 ──► F2 ──► G1
                    │
                    ├──► F3 ──► F4 ──► A1 ──► B1
                    │                   │      │
                    │                   │      └──► D1
                    │                   └──► C1 ──►┘
                    │                          │
                    │                          └──► E1
                    └──► F-story (via F3, sv-il6)
```

### Labels, priority, and epic

- Label every bead in this CR with `cr-011` for grepability.
- Label scope-specific beads with `scope-filters`.
- Priority: P1 by default (matches the existing `sv-*` convention in
  this workspace); stakeholder may downgrade any of them.
- If the workspace supports epics, create an epic `cr-011` and attach
  every bead above to it as parent-child.

## Audit log

- 2026-04-20 — created as `staged`.
