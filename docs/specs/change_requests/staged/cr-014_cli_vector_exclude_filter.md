---
id: 014
title: CLI vector-based exclude filter
status: staged
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md
  - docs/specs/adrs/006_accepted_serialize_embedding_calls.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-014: CLI vector-based exclude filter

## Summary

Add `--exclude <text>` to `scripvec query`. The exclude text is embedded through the ADR-005 embed client; a separate vector search retrieves its most-similar verses; those verses form an exclusion set that is subtracted from the main query's results before top-K is taken. The filter is semantic, not lexical — it excludes passages that are *thematically* close to the exclude text, not just passages that mention the same words.

## Motivation

Scripture study queries are often dominated by one famous passage. A query for "faith" returns Alma 32 and Hebrews 11 at the top and crowds out less-canonical material. The user wants to study faith *besides* the well-known passages — but "besides" is not cleanly expressible as a lexical negation, because the user may not know exactly which passages to exclude until they see them.

A vector-based exclude solves this: the user provides a short description of the material to exclude (`"faith is the substance of things hoped for"`, `"mustard seed"`, `"experiment on the word"`), and the system excludes everything thematically near it. The result set is what remains — material on the same topic but away from the dominant pericope.

This is different from a lexical negation in search engines (`faith -Hebrews`): lexical negation excludes by keyword, this excludes by embedding-space proximity. The two are complementary; this CR adds only the vector form.

## Proposed change

### Flag

- `--exclude <text>` — the exclude text. A single positional string. Absent means no exclusion.

### Mechanism

1. Embed the exclude text via the ADR-005 embed client (same model, endpoint, and 8K-token cap as the main query's dense path).
2. Perform a vector search for the top-`M` most-similar verses to the exclude embedding. `M` is configurable in the project-root config file; not stipulated here.
3. The `M` verse IDs form the exclusion set.
4. The main query retrieves `k + exclusion_buffer` hits internally; hits whose `verse_id` is in the exclusion set are dropped; top-K is taken from what remains.

### ADR-006 serialization

`--exclude` adds a second embed call per query. Per ADR-006, embed calls must be serialized — the main query's embed and the exclude embed run sequentially, not in parallel. Net latency per query with `--exclude`: roughly two embed round-trips plus the two vector searches.

The order of the two embed calls is an implementation detail. Interleaving with the BM25 path under hybrid mode is allowed — the constraint is "no parallel embed calls," not "exclude strictly after main."

### Mode interaction

- `--mode dense`: exclusion set is subtracted from the dense result list before top-K.
- `--mode hybrid`: the exclusion set is subtracted from both the BM25 stream and the dense stream before RRF fusion. RRF then fuses the two filtered streams as usual.
- `--mode bm25`: `--exclude` is rejected with a user error per ADR-001. BM25 has no vector notion of "near" to exclude against. Silent no-op would violate ADR-001. A lexical-negation variant is a separate CR if it is ever wanted.

### Response

- The JSON response gains an `excluded` block:

```json
{
  "exclude": {
    "text": "faith is the substance of things hoped for",
    "set_size": 25,
    "excluded_verse_ids": ["..."]
  },
  ...
}
```

- `set_size` is the applied `M`.
- `excluded_verse_ids` lists the actual excluded verses so the caller can audit what the filter caught (and tune the exclude text if the wrong material was caught).
- The block is absent when `--exclude` is not supplied.

### Failure modes (ADR-001)

- Empty `--exclude` string → raise.
- Exclude text exceeds ADR-005's 8K-token cap → raise per ADR-005.
- Embed endpoint unreachable on the exclude call → raise per ADR-001 with the existing upstream-error exit code 3. No silent fallback to the un-excluded result.
- `--exclude` with `--mode bm25` → raise.
- Exclusion set consumes the entire main top-`k + buffer` (i.e., no hits survive) → not a failure. Return empty results with the `exclude` block populated.

### CLI surface

- One additive flag, one additive response block.
- No new config keys at the CLI level — `M` lives in the project-root config file already.

## Impact on referenced docs

- **ADR-005:** second consumer of the embed client per query. No new endpoint surface.
- **ADR-006:** second embed call; subject to the serialization discipline. This CR explicitly tests the edge: two embed calls on one query must still run serially.
- **ADR-007:** one additive flag; one additive response block. No breaking change.
- **ADR-001:** explicit loud-failure paths for all surfaced error modes.
- **Principle 001:** eval impact is open — running the existing eval queries with a stock exclude text may or may not move the numbers. A new eval dimension is not forced by this CR; the feature's value is user-facing, not recall-facing.

## Alternatives considered

- **Lexical exclusion under BM25 (`"-Hebrews"` style).** Rejected for this CR. Mixing lexical-negation and vector-exclusion under one flag would conflate two different mechanics. A lexical exclude is a separate CR if the use case emerges.
- **Exclude by reference (e.g., `--exclude-ref "Alma 32"`).** Useful and structurally simpler. Left as a follow-up — easy to add alongside, not a substitute for the vector form.

## Open questions

- Should `--exclude` accept multiple values (space- or semicolon-separated) for multi-anchor exclusion? Probably yes eventually; first cut is single-string to keep the mechanism simple.
- Should the exclusion set be union-only, or threshold-gated (only exclude verses whose similarity to the exclude text is above some floor)? Threshold-gated reduces false-positive exclusion but adds a knob. Decide after first usage.
- Does `--exclude` force-interact with ADR-014's force-inclusion? An extracted reference that lands in the exclusion set: which wins? Proposal: force-include wins (ADR-014 is explicit user intent via reference), with a log entry noting the override. Confirm during implementation.

## Decision

Staged.

## User stories (scrum)

*Channelled via the Scrum Lead persona. Outcome first, then vertical slices. Each story delivers observable end-to-end value and can in principle ship on its own. Sequencing is dependency-ordered, not priority-ordered — the stakeholder decides priority.*

**Original ask (verbatim, for audit):** Add `--exclude <text>` to `scripvec query`; embed the text through the ADR-005 client, vector-search its top-`M` neighbors, subtract that set from the main query's results before top-K. Semantic exclusion, not lexical.

**Reframed outcome:** A scripture-study user running a vector query can name a pericope-shaped "avoid zone" in natural language, and the ranked result list they receive is drawn from thematically related material that is *not* near that zone — without crowding from the one famous passage that usually dominates the topic.

---

### Story 1 — Accept and surface the `--exclude` flag

**Who / when:** When an AI agent or human user runs `scripvec query "<main>" --exclude "<avoid>"` under `--mode dense` (the default), they receive a result set with the thematically-near-exclude verses filtered out and an `exclude` block in the JSON response describing what was filtered.

**Acceptance criteria:**
- `--exclude <text>` is accepted as a single positional string on `scripvec query`.
- Absent `--exclude`: response JSON does not contain an `exclude` block (key not present, not `null`).
- Present `--exclude` under `--mode dense`:
  - The exclude text is embedded via the ADR-005 embed client, using the same model, endpoint, and 8K-token cap as the main query's dense path.
  - A vector search retrieves the top-`M` most-similar verses to the exclude embedding, where `M` is read from the project-root config file.
  - Those `M` `verse_id`s form the exclusion set.
  - The main dense query internally retrieves `k + exclusion_buffer` hits; hits whose `verse_id` is in the exclusion set are dropped; the final list is the top-`K` of what remains.
  - Response JSON includes `exclude.text` (echo of input), `exclude.set_size` (equal to applied `M`), and `exclude.excluded_verse_ids` (the actual IDs excluded).
- No silent failure: if the embed call for the exclude text errors, the CLI raises per ADR-001 with upstream-error exit code 3 — no fallback to un-excluded results.

**Out of scope for this story:** hybrid-mode interaction, bm25-mode rejection, empty-result handling, force-include precedence. Each has its own story.

---

### Story 2 — Honor ADR-006 serialization with a second embed call

**Who / when:** When a query runs with `--exclude`, the two embed calls (main query dense + exclude) execute sequentially, never in parallel, preserving the ADR-006 discipline that already applies to the single-embed case.

**Acceptance criteria:**
- A contract test exercises `scripvec query` with `--exclude` and verifies — by instrumenting or mocking the embed client — that at most one embed request is in flight at any instant.
- The test covers both `--mode dense` (main-embed + exclude-embed) and `--mode hybrid` (main-embed + exclude-embed interleaved with BM25 work). BM25 work *may* overlap with embeds; embed-with-embed *must not*.
- Order of the two embed calls is not fixed by the test — the test asserts non-overlap, not ordering.
- Observable latency per query with `--exclude` is approximately two embed round-trips plus two vector searches, reported in existing latency telemetry fields. (No numeric target; telemetry present.)

**Out of scope:** performance targets, retry policy on embed failure.

---

### Story 3 — Extend exclusion to hybrid mode

**Who / when:** When a user runs `scripvec query "<main>" --exclude "<avoid>" --mode hybrid`, the exclusion set is subtracted from *both* the BM25 stream and the dense stream before RRF fusion; the ranked output contains no verse whose `verse_id` is in the exclusion set.

**Acceptance criteria:**
- Under `--mode hybrid` with `--exclude`, the exclusion set is computed exactly as in Story 1 (single vector search against the exclude embedding, top-`M` from config).
- The exclusion set is applied to the BM25 result stream *and* the dense result stream *before* RRF fusion runs.
- RRF fuses the two already-filtered streams; no excluded verse can re-enter via the other stream.
- Response JSON `exclude` block is present and populated identically to Story 1; no hybrid-specific extra fields.
- No excluded verse appears anywhere in the final top-`K`.

**Out of scope:** changes to RRF weighting or `k + exclusion_buffer` sizing for hybrid (use the same policy as Story 1).

---

### Story 4 — Reject `--exclude` under BM25 mode loudly

**Who / when:** When a user runs `scripvec query "<main>" --exclude "<avoid>" --mode bm25`, the CLI raises a user-facing error and exits non-zero — it does not silently drop the flag and does not silently pretend to apply it.

**Acceptance criteria:**
- `--exclude` combined with `--mode bm25` produces a clear error message naming both the flag and the mode, and stating that vector exclusion has no BM25 analog.
- Exit code is the ADR-001 user-error exit code (match whatever `scripvec` already uses for invalid flag combinations — do not invent a new one).
- No query is executed; no embed call is made; no vector search runs.
- A contract test covers this path.

**Out of scope:** a future lexical-negation BM25 variant (explicitly deferred in the CR).

---

### Story 5 — Validate the exclude text itself

**Who / when:** When a user supplies `--exclude` with malformed or oversized input, they get a specific, actionable error at the CLI boundary — before any embed call is attempted.

**Acceptance criteria:**
- Empty `--exclude` string (`--exclude ""`) raises with a message naming the flag and the empty-string problem.
- Exclude text exceeding the ADR-005 8K-token cap raises per ADR-005, using the same error path the main-query dense path uses for oversized input.
- Whitespace-only `--exclude` is treated as empty (raise).
- Contract tests cover each case.
- In all three cases: no embed call is made, and exit code reflects user-input error, not upstream error.

**Out of scope:** tokenization-library choice; reuse whatever the main query dense path uses to measure against the 8K cap.

---

### Story 6 — Exclusion-set-wipes-results is a valid empty, not a failure

**Who / when:** When the exclusion set happens to cover every candidate in the main query's `k + exclusion_buffer` window, the user receives an empty `results` array and a fully-populated `exclude` block — not an error.

**Acceptance criteria:**
- Main query produces `k + exclusion_buffer` hits; all are in the exclusion set. Response has `results: []` and exit code 0.
- `exclude` block is populated with `text`, `set_size`, and `excluded_verse_ids` exactly as in non-empty cases.
- No warning text is emitted on stderr unless the CLI already emits warnings in analogous "no-results" cases. (Do not introduce new stderr chatter here.)
- Contract test covers this case by constructing an exclude text that, against the fixture corpus, wipes the main query's window.

**Out of scope:** expanding `exclusion_buffer` adaptively when results would be empty — leave as a future tuning decision.

---

### Story 7 — Resolve force-include vs. exclude collision deterministically

**Who / when:** When a future force-inclusion flow (ADR-014 / follow-on CR) lands a verse via explicit user reference, and that same verse is in the current query's exclusion set, the force-included verse wins — because the reference is explicit user intent — and the override is logged.

**Acceptance criteria:**
- When a verse is in both the force-include set and the exclusion set, it appears in the final results (force-include wins).
- A log entry (at the level the CLI already uses for retrieval diagnostics) notes the verse ID, that a force-include overrode an exclusion, and the exclude text that flagged it.
- The `exclude.excluded_verse_ids` list reflects what was *attempted* to be excluded, including verses overridden by force-include — so the caller can still audit what the filter caught.
- Contract test covers the collision case.
- This story is **blocked on clarification** until the force-include mechanism (ADR-014 or its implementing CR) is merged. Marked blocked; dependency must be named on the board.

**Out of scope until unblocked:** implementation. The acceptance criteria stand as the contract to satisfy once force-include exists.

---

### Stakeholder questions surfaced during decomposition

These are **not** story content — they are clarifications the Scrum Lead routes back to the stakeholder before any story is pulled.

1. **Multi-anchor exclude (`--exclude A --exclude B` or `--exclude "A; B"`):** The CR flags this as "probably yes eventually." Is single-string enough for MVP, or do you want multi-anchor as a story now? (Recommendation: defer — adds combinatorics to the exclusion-set computation.)
2. **Threshold-gated exclusion (only exclude above some similarity floor):** Same posture from the CR. Is the first cut strictly "top-`M` union," or should there be a floor knob from day one? (Recommendation: defer; ship top-`M` union first, add threshold if false-positive exclusion is observed in usage.)
3. **`exclusion_buffer` default:** Named as a config value but not a numeric target in this CR. Confirm it lives in the project-root config alongside `M` before Story 1 starts.

---

### Sequencing (dependency order, not priority)

- Story 5 (validation) is independent — it can ship first or last; it blocks no other story.
- Story 1 (dense path) is the foundation; Stories 2, 3, 4, 6 depend on it.
- Story 2 (serialization test) depends on Story 1 but could be written against a stub.
- Story 3 (hybrid) depends on Story 1.
- Story 4 (bm25 rejection) is independent of Story 1 in implementation but shares the flag-parsing surface — ship alongside Story 1 for a coherent CLI surface.
- Story 6 (empty-after-exclusion) depends on Story 1; small.
- Story 7 (force-include collision) is blocked on the force-include CR; do not pull until unblocked.

The stakeholder picks the order within these constraints.

## Beads plan (bead-planning persona)

*Persona note: no dedicated "bead-planning" persona exists in the personas DB (verified with multiple queries — closest match was Scrum Lead at distance 1.048 and Discipline Scout at 1.003, neither purpose-built for bead planning). The voice below is a synthesis grounded in (a) the Scrum Lead's decomposition discipline, (b) the Discipline Scout's dependency-graph sensibility, and (c) the project memory reference at `reference_beads_tool.md` describing the `br` tool in the planning pipeline. Flagged here so the gap is visible; the user may want to add a first-class bead-planning persona.*

### Principles for this plan

- **One file, one bead.** A bead that touches more than one implementation file should be split — it makes dependency-linking and parallel swarming legible.
- **Tests are their own beads.** A test bead depends on the module it tests; pairing test and impl in one bead invites skipped tests.
- **Dependencies are DAG edges, not suggestions.** If bead B cannot start until bead A lands, express it as `A blocks B`. Keep the graph acyclic.
- **Priority is about blocking, not importance.** A bead that unblocks four other beads deserves a higher priority than an equally-important leaf.
- **Label for swarming.** Existing labels in this repo: `app-cli`, `pkg-retrieval`, `pkg-eval`, `test`, `sprint-N`. Reuse them. Add `cr-014` so every bead for this CR is filterable as a set.
- **Size them small.** A bead that looks bigger than a single focused sitting should split. Swarm workers pick up small beads cleanly.
- **Story 7 (force-include collision) is deferred.** It is blocked on a separate CR. Do not plan beads for it in this CR — just mark it as out of scope and let that CR produce its own beads.

### Bead inventory

Format: `ID-slug (priority) — title — depends on [IDs]`. IDs are local placeholders (`B1` … `B13`) that map to whatever `sv-xxx` IDs the `br` CLI hands back at creation time.

| Local ID | Priority | Title | Labels | Depends on | Covers story |
|----------|----------|-------|--------|------------|--------------|
| B1 | 1 | `config`: add `exclude_m` and `exclude_buffer` to project-root config schema | `pkg-retrieval`, `cr-014` | — | S1, S3 prereq |
| B2 | 1 | `retrieval/exclude.py`: `compute_exclusion_set(text, M)` — embed + vector-search + return `list[str]` | `pkg-retrieval`, `cr-014` | B1 | S1 |
| B3 | 1 | `retrieval/exclude.py`: `filter_by_exclusion(hits, exclusion_set)` — drop hits whose verse_id is in set | `pkg-retrieval`, `cr-014` | — | S1 |
| B4 | 1 | `cli/query.py`: accept `--exclude <text>` flag and thread through to retrieval layer (dense mode only in this bead) | `app-cli`, `cr-014` | B1, B2, B3 | S1 |
| B5 | 1 | `cli/query.py`: add `exclude` block to JSON response (`text`, `set_size`, `excluded_verse_ids`) under dense mode | `app-cli`, `cr-014` | B4 | S1 |
| B6 | 1 | `cli/query.py`: reject `--exclude` with `--mode bm25` as user error per ADR-001 | `app-cli`, `cr-014` | — | S4 |
| B7 | 1 | `cli/query.py`: validate `--exclude` input (empty, whitespace-only, >8K tokens) before embed call | `app-cli`, `cr-014` | — | S5 |
| B8 | 1 | `retrieval/hybrid.py`: apply exclusion set to both BM25 and dense streams *before* RRF fusion under `--mode hybrid` | `pkg-retrieval`, `cr-014` | B2, B3, B4 | S3 |
| B9 | 2 | `cli/test_exclude_contracts.py`: contract tests for dense-mode `--exclude` happy path, empty-results case, JSON shape | `app-cli`, `test`, `cr-014` | B4, B5 | S1, S6 |
| B10 | 2 | `cli/test_exclude_contracts.py`: contract test for BM25 rejection | `app-cli`, `test`, `cr-014` | B6 | S4 |
| B11 | 2 | `cli/test_exclude_contracts.py`: contract tests for input validation (empty / whitespace / oversize) | `app-cli`, `test`, `cr-014` | B7 | S5 |
| B12 | 2 | `retrieval/test_hybrid_exclude.py`: contract test that exclusion is applied pre-RRF in hybrid mode | `pkg-retrieval`, `test`, `cr-014` | B8 | S3 |
| B13 | 2 | `retrieval/test_embed_serialization.py`: contract test asserting embed calls never overlap when `--exclude` is used (dense + hybrid) | `pkg-retrieval`, `test`, `cr-014` | B4, B8 | S2 |

### Dependency DAG (edges `A → B` mean "A blocks B")

```
B1 ──► B2 ──► B4 ──► B5 ──► B9
        │      │      │
        │      │      └────► B13 (with B8)
        │      └─► B8 ──► B12
        │             └──► B13
        └────────► B3 ──► B4
B6 ──► B10
B7 ──► B11
```

Roots (no predecessors): **B1, B3, B6, B7**. These four can be picked up in parallel on day one. B1 is the smallest and unblocks the most — start it first, but B3, B6, B7 do not need to wait.

Leaves (nothing depends on them): **B5, B9, B10, B11, B12, B13**. All contract tests land as leaves, which is correct — tests are the last thing the DAG gates on.

### Deliberate non-inclusions

- No bead for force-include collision (Story 7). Blocked on external CR; leave to that CR's bead plan.
- No bead for threshold-gated exclusion or multi-anchor exclude. Those are deferred per the CR's Open Questions.
- No docs-update bead. The CR itself is the doc; if ADR-007's response-shape fixture file needs updating, that's inside B5.
- No performance bead. Per project memory `feedback_no_speed_targets.md`, no latency targets in ship criteria; telemetry is already in Story 2's acceptance and lands inside B13.

### Handoff to bead-writing persona

The next persona takes this table and creates the beads in the `br` database. Each row becomes one `br create` invocation with `--type task`, the listed priority and labels, and a description that quotes the covered story's acceptance criteria. Dependencies are added with `br dep add <blockee> <blocker>`. The `sv-xxx` IDs that `br` returns replace the `B1..B13` placeholders on the board — the DAG shape is preserved by the dep edges, not by the IDs.

## Audit log

- 2026-04-20 — created as `staged`.
