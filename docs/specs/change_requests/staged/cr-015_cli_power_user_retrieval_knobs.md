---
id: 015
title: CLI power-user retrieval knobs — hybrid weighting and cross-reference expansion
status: staged
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-015: CLI power-user retrieval knobs — hybrid weighting and cross-reference expansion

## Summary

Two power-user flags on `scripvec query`:

1. `--hybrid-weight <lexical:dense>` — override the default BM25/dense balance in RRF fusion. Valid only with `--mode hybrid`.
2. `--cross-ref-expand N` — for each top-K result, surface up to N cross-referenced verses (from the scripture's footnote metadata) as companion hits nested under their parent result. Requires the corpus to carry cross-reference metadata; fails loud when it does not.

Both are retrieval-tuning knobs targeting users doing close study, not casual browsing. They are explicitly additive — neither changes defaults; both are no-ops unless the flag is supplied.

## Motivation

**Hybrid weighting.** Scripture queries have a wide lexical-vs-semantic character: a phrase-memory query ("a more excellent way") is almost purely lexical; a topical query ("what does scripture say about patience under affliction") is almost purely semantic. A fixed RRF weighting is a compromise that fits neither extreme. Exposing the weight as a per-query flag lets a power user bias retrieval toward whichever side suits the query, without rebuilding the index and without editing the config between queries.

**Cross-reference expansion.** LDS scripture carries a dense network of editor-curated cross-references between verses (footnotes). Those cross-references are the scripture's own statement of *"these verses are related"* — a signal orthogonal to both BM25 and dense similarity. Surfacing cross-references from each top hit extends the study trail: a user who finds Alma 32:21 also sees the footnote-linked verses on faith in Hebrews, D&C 8, etc., without running a second query.

This is a retrieval-adjacent feature, not a retrieval-replacement feature: companions are attached to their parent hits, not injected into the top-K ranking.

## Proposed change

### Hybrid weight flag

- `--hybrid-weight <lexical:dense>` — colon-separated pair of non-negative numbers, e.g. `1:1`, `2:1`, `1:3`.
- The pair is applied to RRF's rank contribution per retriever: each retriever's contribution is multiplied by its weight before summing. Equivalent to a weighted RRF.
- Default weight (when the flag is absent) lives in the project-root config file. No numeric value is stipulated here.
- Valid only with `--mode hybrid`. Under `--mode bm25` or `--mode dense` the flag is a user error per ADR-001 — silent no-op would hide the caller's intent.
- The response echoes the applied weight so callers can see what ran.

```json
{
  "hybrid_weight": {"lexical": 2, "dense": 1},
  ...
}
```

- Echoed as `null` when the flag was not supplied (default from config was used) — or as the config default with a `from_config: true` marker. Implementation picks one; decide during implementation.

### Cross-reference expansion flag

- `--cross-ref-expand N` — per-hit cap. Up to `N` cross-referenced verses per parent hit surface as companions. `N=0` (or absence of flag) means no companions.
- Companions attach to their parent in the JSON response, not the top-K ranking:

```json
{
  "results": [
    {
      "rank": 1,
      "verse_id": "alma-32-21",
      "ref": "Alma 32:21",
      "text": "...",
      "cross_references": [
        {"ref": "Hebrews 11:1", "text": "...", "tag": "footnote_a"},
        {"ref": "Ether 12:6",  "text": "...", "tag": "footnote_b"}
      ]
    }
  ]
}
```

- Companions are ordered by the corpus's own footnote ordering (not re-scored).
- If a hit has more cross-references than `N`, the first `N` in footnote order are taken. (Re-ranking cross-references by retrieval score is a future enhancement, not scope here.)

### Dependency on corpus metadata

`--cross-ref-expand` depends on the index carrying cross-reference metadata — a per-verse list of `(target_verse_id, tag)` tuples sourced from the scripture's footnotes. If the current index does not carry this metadata, `--cross-ref-expand N > 0` raises per ADR-001 with the message:

> `cross-reference metadata not present in this index — rebuild with cross-reference ingestion enabled`

The ingestion pipeline change that adds cross-reference metadata to the index is out of scope for this CR. This CR specifies only the CLI contract; when the corpus gains the data, the flag becomes functional with no CLI change. The cross-reference ingestion effort is a separate CR to be drafted when the corpus source is identified.

### Failure modes (ADR-001)

- `--hybrid-weight` with `--mode {bm25,dense}` → raise with specific message.
- `--hybrid-weight` malformed (not `<non_negative>:<non_negative>`, or both zero) → raise.
- `--cross-ref-expand N` with negative `N` → raise.
- `--cross-ref-expand N > 0` on an index without cross-reference metadata → raise with the message above.

### CLI surface

- Two additive flags.
- Two additive response fields (`hybrid_weight` echo, per-hit `cross_references` list).
- No new config keys introduced at the CLI layer — the default hybrid weight lives in the project-root config; cross-reference metadata is an index-build concern.

## Impact on referenced docs

- **ADR-007:** additive flags; additive response fields. No breaking change.
- **ADR-001:** explicit loud-failure paths.
- **Principle 001:** the eval harness gains a natural extension: sweep `--hybrid-weight` across a few values on the existing held-out set and report recall/nDCG per weight. The sweep is not forced by this CR but is the obvious next use of the knob.

## Open questions

- Should `--hybrid-weight` accept a free-form weight string (e.g., `0.7:0.3`) or be restricted to integer ratios (`7:3`)? Integer ratios are simpler to parse and equivalent in expressive power; free-form floats are ergonomic. Pick during implementation; either is additive.
- When cross-reference metadata exists but a specific hit has no cross-references, the `cross_references` field is `[]` vs. absent. Pick one for consistency.
- Should companions be deduplicated against the main `results` list (a companion that also appears as a top-K hit is suppressed from the companion list)? Probably yes — duplicate rendering is confusing. Confirm during implementation.

## Decision

Staged.

## User stories (scrum)

*Channeled by the Scrum Lead persona. Stories are vertical slices, each demoable on its own. Acceptance criteria are observable. Sequencing is dependency-forward, not priority.*

### Intake note

The stakeholder asked for "power-user retrieval knobs" and proposed two specific flags. I accept both as outcomes because the CR already reverse-engineers the job-to-be-done: (a) let a close-study user re-balance lexical-vs-semantic per query without rebuilding, and (b) let that user follow footnote-curated cross-references as a companion trail on each hit. The ingestion half of (b) is explicitly out of scope — this CR is CLI contract only. That means I have one functional outcome (weighting) and one contract-only outcome (cross-ref surface + loud failure when metadata is absent). I'm decomposing both into thin vertical slices that each stand on their own demo.

### Story 1 — Validate and parse `--hybrid-weight`

**As** a CLI user invoking `scripvec query --mode hybrid --hybrid-weight <lexical:dense>`,
**I want** the flag to be parsed and validated before any retrieval runs,
**so that** malformed input or wrong-mode usage surfaces immediately per ADR-001.

**Acceptance criteria:**
- When `--hybrid-weight 2:1` is supplied with `--mode hybrid`, parsing succeeds and the parsed pair is available to the fusion step.
- When `--hybrid-weight` is supplied with `--mode bm25` or `--mode dense`, the CLI raises with a message naming the conflict (flag vs. mode) and exits non-zero.
- When the value is malformed (not `<non_negative>:<non_negative>`, e.g. `foo`, `1:`, `-1:2`, `1:2:3`) the CLI raises with a message that shows the rejected input.
- When both numbers are zero (`0:0`) the CLI raises — that's a degenerate fusion weight.
- Both integer ratios (`2:1`) and free-form floats (`0.7:0.3`) are accepted, per the open question resolved toward the more ergonomic option. Document the chosen form in the error message.
- No query runs if validation fails.

**Out of scope:** applying the weight in RRF — that is Story 2.

### Story 2 — Apply weighted RRF in hybrid mode

**As** a close-study user running a phrase-memory or topical query,
**I want** the parsed `--hybrid-weight` to actually bias the RRF fusion,
**so that** my per-query lexical-vs-semantic balance takes effect.

**Acceptance criteria:**
- When `--mode hybrid --hybrid-weight 1:1` is used, results match the current default-weighted RRF behavior (regression check against a canned query set).
- When the weight is skewed heavily lexical (`--hybrid-weight 10:1`), a canned lexical-heavy query (e.g. exact phrase from scripture) produces a ranking closer to the BM25-only ranking for that query than the `1:1` case.
- When the weight is skewed heavily dense (`--hybrid-weight 1:10`), a canned semantic query produces a ranking closer to the dense-only ranking than the `1:1` case.
- The flag has no effect (defaults still used) when it is not supplied.
- Existing non-hybrid modes remain byte-identical to prior output for the same inputs.

**Out of scope:** echoing the applied weight in the response — that is Story 3.

### Story 3 — Echo the applied hybrid weight in the response

**As** an AI-agent caller per ADR-007,
**I want** the JSON response to tell me which weight actually ran,
**so that** I can log, compare, and reproduce runs without guessing at defaults.

**Acceptance criteria:**
- When `--hybrid-weight` is supplied, the response contains a top-level `hybrid_weight` object with `lexical` and `dense` numeric fields matching the parsed input.
- When the flag is absent, the response contains a `hybrid_weight` entry whose shape makes it unambiguous that the config default was used. Implementation picks one of the two forms specified in the CR (`null` or `{..., "from_config": true}`) and documents the choice — the test pins the chosen form.
- The echo field is present on `--mode hybrid` only; on `--mode bm25`/`--mode dense` the field is absent (the knob does not apply there).
- A schema/contract test under `cli/test_contracts.py` (or equivalent) covers all three cases.

### Story 4 — Validate `--cross-ref-expand N` input

**As** a CLI user invoking `scripvec query --cross-ref-expand N`,
**I want** bad values rejected loudly before any retrieval runs,
**so that** I don't get silent empty-companion lists that hide real errors.

**Acceptance criteria:**
- `--cross-ref-expand 0` and absence of the flag behave identically: no companion surfacing attempted, no `cross_references` field appended.
- `--cross-ref-expand N` for any negative `N` raises with a message naming the rejected value.
- `--cross-ref-expand N` for non-integer `N` raises.
- `--cross-ref-expand N` is accepted regardless of `--mode` (lexical, dense, or hybrid — cross-refs are retrieval-mode-agnostic).
- No query runs if validation fails.

**Out of scope:** actually surfacing companions — that is Story 5 / Story 6.

### Story 5 — Loud-fail when metadata is absent (ADR-001)

**As** a user running `--cross-ref-expand N > 0` on an index built without cross-reference metadata,
**I want** the command to fail loudly with a fix-it message,
**so that** I don't silently get empty companion lists and mistake that for "no cross-references exist."

**Acceptance criteria:**
- When `--cross-ref-expand N > 0` is supplied and the current index does not carry cross-reference metadata, the CLI raises with exactly the message:
  > `cross-reference metadata not present in this index — rebuild with cross-reference ingestion enabled`
- The detection is a property of the index (a capability flag or schema marker), not a per-verse check — absent metadata at the index level trips the failure immediately, before retrieval.
- The failure is non-zero exit and surfaces on stderr (or the agent-facing error channel per ADR-007), not buried in a successful JSON body.
- A contract test simulates an index-without-metadata and asserts the exact message.

**Out of scope:** the ingestion pipeline that *adds* the metadata — explicitly deferred to a separate CR.

### Story 6 — Attach cross-reference companions to hits

**As** a close-study user following footnote trails,
**I want** each top-K hit to carry up to `N` cross-reference companions nested under it,
**so that** I see the scripture's own editor-curated related verses without running a second query.

**Acceptance criteria:**
- When an index *does* carry cross-reference metadata and `--cross-ref-expand N > 0` is supplied, each result in `results[]` carries a `cross_references` field.
- Companions are ordered by the corpus's own footnote ordering; no re-scoring.
- If a hit has more than `N` cross-references, the first `N` in footnote order are taken.
- Each companion entry contains `ref`, `text`, and `tag` (e.g. `footnote_a`).
- Companions are attached nested, never injected into the top-K ranking itself — `rank` values on the parent results are unaffected.
- The shape `{ref, text, tag}` is locked by contract test.
- The behavior for "hit has zero cross-references" is decided and pinned: either `cross_references: []` everywhere (consistent) or field absent on zero-companion hits (compact). Implementation picks one; the contract test enforces it.
- If a candidate companion already appears in the top-K `results[]`, it is suppressed from that hit's `cross_references` list (dedup against the primary ranking). This is the resolution of the CR's third open question.

### Story 7 — Document both flags in CLI help and examples

**As** an AI-agent caller (ADR-007) discovering the tool via `--help`,
**I want** both flags documented with their valid value shapes, failure cases, and a one-line example each,
**so that** I can form a correct invocation on the first try without reading source.

**Acceptance criteria:**
- `scripvec query --help` lists `--hybrid-weight` and `--cross-ref-expand` with one-line descriptions and example values.
- `--hybrid-weight` help text names its dependency on `--mode hybrid`.
- `--cross-ref-expand` help text names its dependency on index cross-reference metadata and points to the exact error message users will see if it's missing.
- The help output remains stable (no churn from unrelated flags) so the contract tests covering help text stay tight.

### Sequencing

```
Story 1 (parse) ─┐
                 ├─► Story 2 (apply in RRF) ──► Story 3 (echo in response)
                 │
Story 4 (parse) ─┼─► Story 5 (loud-fail when metadata absent)
                 │
                 └─► Story 6 (attach companions when metadata present)

Story 7 (help/docs) depends on 1, 2, 4 — flag surfaces must exist before they can be documented.
```

Stories 3, 5, 6, and 7 are independent of each other once their prerequisites land — they can pick up in any order.

### Tradeoffs surfaced, not decided

- **Hybrid-weight format (integer ratio vs. free-form float).** Either is additive; the stakeholder picks at implementation time. I recommend free-form floats for ergonomics but flag that integer ratios parse more robustly.
- **Default-echo form (`null` vs. `{…, "from_config": true}`).** The CR explicitly leaves this to implementation. Both are testable; the stakeholder picks one and the contract test pins it.
- **Empty-companions shape (`[]` vs. absent).** Same — pick one, pin it.

None of these are mine to decide. The stories are written so any of the three choices slot in without re-decomposition.

## Beads plan (bead-planning persona)

*Persona note: a DB search for "bead planning" and "bead writing" returned no dedicated persona (top hits all had distance > 1.0 and were not topical matches). The closest actual match in the DB for "decompose user stories into dependency-linked, swarm-ready work items" is the Scrum Lead (distance 0.778 on the initial scrum query, 0.920 on the decomposition query). Channeling Scrum Lead here in a bead-planning posture — same dispositions (vertical slices, INVEST, observable acceptance criteria) applied one level down: stories → beads instead of outcomes → stories.*

### Planning posture

Each bead is a unit of swarm-ready work: picked up by a single engineer (or agent), finishable without cross-chat, with its own acceptance criteria. Dependencies are explicit; nothing runs ahead of what it needs. I keep the vertical-slice discipline — a bead that can't be demoed on its own is a subtask hiding inside one, and it gets folded into a valuable parent.

I'm also holding one architectural observation: Stories 1–3 share a fusion subsystem and Stories 4–6 share a CLI+metadata path. Within each cluster the beads must order; across clusters they are independent and can swarm.

### Bead list

Tags I'll use: `cr-015`, plus one of `hybrid-weight` | `cross-ref-expand` | `docs` to slice by feature area.

---

**BEAD A — Parse and validate `--hybrid-weight` flag**
- **From:** Story 1
- **Type:** task
- **Priority:** P2
- **Labels:** `cr-015`, `hybrid-weight`, `cli`
- **Description:** Add `--hybrid-weight <lexical:dense>` to `scripvec query`. Parser accepts either integer ratios or free-form floats (decide and document in the help text). Validation raises per ADR-001 on: (a) flag used with `--mode bm25` or `--mode dense`, (b) malformed value, (c) `0:0`. No retrieval runs if validation fails.
- **Acceptance criteria:**
  - `scripvec query --mode hybrid --hybrid-weight 2:1 "…"` parses successfully; the parsed `(2.0, 1.0)` pair is visible to downstream fusion code (unit test confirms).
  - `scripvec query --mode bm25 --hybrid-weight 1:1 "…"` exits non-zero with a message naming the mode/flag conflict.
  - Malformed inputs (`foo`, `1:`, `-1:2`, `0:0`, `1:2:3`) each exit non-zero with a message that includes the rejected input.
  - A chosen format (integer-ratio or free-form float) is documented in `--help` and pinned in a contract test.
- **Depends on:** none.

**BEAD B — Apply weighted RRF in hybrid fusion**
- **From:** Story 2
- **Type:** task
- **Priority:** P2
- **Labels:** `cr-015`, `hybrid-weight`, `retrieval`
- **Description:** Multiply each retriever's RRF rank contribution by its weight before summing. Default weight (when the flag is absent) comes from the project-root config file — no new config key introduced here; reuse whatever key holds the current default balance.
- **Acceptance criteria:**
  - `--hybrid-weight 1:1` produces output byte-identical to the prior default-weighted RRF on a canned query set (regression test).
  - `--hybrid-weight 10:1` on a lexical-heavy canned query produces a ranking closer to BM25-only than the `1:1` case does (rank-distance metric, checked against a fixture).
  - `--hybrid-weight 1:10` on a semantic canned query produces a ranking closer to dense-only than `1:1` does.
  - `--mode bm25` and `--mode dense` outputs are byte-identical to prior outputs for the same inputs.
- **Depends on:** BEAD A (blocks).

**BEAD C — Echo applied `hybrid_weight` in JSON response**
- **From:** Story 3
- **Type:** task
- **Priority:** P3
- **Labels:** `cr-015`, `hybrid-weight`, `contract`
- **Description:** Add `hybrid_weight` to the top-level response for `--mode hybrid`. When the flag is supplied, the field carries `{"lexical": N, "dense": M}`. When the flag is absent, the field carries a chosen sentinel (either `null` or `{"lexical": D, "dense": E, "from_config": true}`) — pick one at implementation time and pin. Field is absent on `--mode bm25` / `--mode dense`.
- **Acceptance criteria:**
  - Contract test under `cli/test_contracts.py` covers (a) flag supplied, (b) flag absent with `--mode hybrid`, (c) non-hybrid mode (field absent).
  - Help text documents the echo field.
- **Depends on:** BEAD A, BEAD B (blocks).

**BEAD D — Parse and validate `--cross-ref-expand N`**
- **From:** Story 4
- **Type:** task
- **Priority:** P2
- **Labels:** `cr-015`, `cross-ref-expand`, `cli`
- **Description:** Add `--cross-ref-expand N` to `scripvec query`. `N=0` and absence are equivalent no-ops. Validation raises on negative `N` or non-integer `N`. Accepted regardless of `--mode`.
- **Acceptance criteria:**
  - `--cross-ref-expand 0` and flag-absent both produce identical output (no `cross_references` field added; test asserts JSON equality).
  - `--cross-ref-expand -1`, `--cross-ref-expand abc` each exit non-zero with a message including the rejected input.
  - `--cross-ref-expand 3` is accepted under all three modes (bm25, dense, hybrid).
- **Depends on:** none.

**BEAD E — Loud-fail when index lacks cross-reference metadata**
- **From:** Story 5
- **Type:** task
- **Priority:** P2
- **Labels:** `cr-015`, `cross-ref-expand`, `adr-001`, `contract`
- **Description:** Detect at the index-level (capability flag / schema marker) whether cross-reference metadata is present. If `--cross-ref-expand N > 0` is used against an index that lacks it, raise with the exact message: `cross-reference metadata not present in this index — rebuild with cross-reference ingestion enabled`. Error surfaces on stderr/agent-error-channel, not in a successful JSON body.
- **Acceptance criteria:**
  - Contract test simulates an index-without-metadata and asserts the exact error string, non-zero exit.
  - Detection is O(1) at index open — no per-verse scan.
  - When an index *does* carry metadata, this check is a no-op and does not block retrieval.
- **Depends on:** BEAD D (blocks) — flag must parse before the failure path engages.

**BEAD F — Attach cross-reference companions to each top-K hit**
- **From:** Story 6
- **Type:** task
- **Priority:** P2
- **Labels:** `cr-015`, `cross-ref-expand`, `contract`
- **Description:** For indices carrying cross-reference metadata, when `--cross-ref-expand N > 0`, append `cross_references` to each result in `results[]`. Companions ordered by footnote order, capped at `N`, shape `{ref, text, tag}`, nested under their parent (never injected into top-K). Dedup: companions that are themselves in the primary `results[]` are suppressed from that hit's companion list. Pin the empty-companions convention (`[]` vs. absent) by contract test.
- **Acceptance criteria:**
  - Fixture index with known cross-references produces exactly the expected `cross_references` arrays at `N=3` (contract test).
  - `rank` fields on parent results are unaffected by companion expansion (regression test).
  - Dedup behavior covered by a fixture where a verse appears both as a top-K hit and as another hit's cross-reference; the companion entry is suppressed.
  - Empty-companions shape is consistent with the chosen convention (`[]` everywhere OR field absent on zero-companion hits), pinned by test.
- **Depends on:** BEAD D (blocks).

**BEAD G — Document both flags in CLI help and add examples**
- **From:** Story 7
- **Type:** task
- **Priority:** P3
- **Labels:** `cr-015`, `docs`
- **Description:** Update `scripvec query --help` and any agent-facing docs to list `--hybrid-weight` and `--cross-ref-expand` with one-line descriptions, value-shape examples, mode/metadata dependencies, and the exact error messages users will see when they misuse the flags.
- **Acceptance criteria:**
  - `scripvec query --help` output shows both flags with examples and dependency notes.
  - `--hybrid-weight` help names `--mode hybrid` requirement.
  - `--cross-ref-expand` help names the index metadata requirement and quotes the exact failure message.
  - Contract test pins the help-text substrings so they can't drift silently.
- **Depends on:** BEAD A, BEAD B, BEAD D (blocks) — flag surfaces and semantics must exist before they can be documented.

### Dependency graph

```
BEAD A ──► BEAD B ──► BEAD C           (hybrid-weight track)
   │         │
   │         └─────────────────┐
   └─────────────┐             │
                 ▼             ▼
BEAD D ──► BEAD E              ├──► BEAD G   (docs — needs A, B, D done)
    │                          │
    └────► BEAD F ─────────────┘
```

### Swarm plan

- **Parallel lane 1 (hybrid-weight):** A → B → C. A single agent can own the whole lane, or hand off at each boundary.
- **Parallel lane 2 (cross-ref-expand):** D → {E, F}. E and F are independent once D lands.
- **Cross-cutting tail:** G waits on A, B, D (help text needs both flag surfaces plus the working hybrid fusion). C, E, F can land before G.
- A and D are the only true starters — both have zero dependencies and can pick up immediately in parallel.

### What I'm deliberately not encoding as beads

- The open questions (integer-vs-float weight format, null-vs-marker echo shape, `[]`-vs-absent empty companions) are deferred to implementation per the CR. Each bead's acceptance criteria say "decide and pin" rather than pre-committing. An extra bead for each decision would be ceremony, not progress.
- The cross-reference ingestion CR is explicitly out of scope — no bead here.
- A recall/nDCG sweep across `--hybrid-weight` values (the "natural eval-harness extension" mentioned under Principle 001) is not forced by this CR and does not become a bead. It belongs in a future CR if and when the eval harness lands.

## Audit log

- 2026-04-20 — created as `staged`.
