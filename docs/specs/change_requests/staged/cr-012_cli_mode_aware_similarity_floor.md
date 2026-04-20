---
id: 012
title: CLI mode-aware similarity floor on query results
status: staged
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-012: CLI mode-aware similarity floor on query results

## Summary

Add a `--floor` flag to `scripvec query` that drops results below a score threshold before top-K is returned. Because BM25, dense, and hybrid RRF scores live on different numeric scales, the flag's interpretation is mode-aware: absolute cosine similarity under `--mode dense`, relative-to-top-hit ratio under `--mode bm25` and `--mode hybrid`. The result set may contain fewer than K hits (possibly zero) when the floor culls low-scoring tail.

## Motivation

Top-K returns a fixed count regardless of how bad the tail gets. For a study query where only two verses are genuinely relevant, the CLI still returns K=10 results, and positions 3–10 are noise. A similarity floor lets the caller cap irrelevance rather than padding the response with tail matches.

A naive "minimum score" flag does not work across modes:

- **Dense** scores are cosine similarities in a bounded range (roughly [0.0, 1.0] for this embedder). An absolute threshold is meaningful.
- **BM25** scores are unbounded and corpus-dependent. An absolute threshold is meaningful only if the caller knows the corpus-specific score distribution — almost no caller does.
- **Hybrid RRF** scores are rank-based (sum of `1/(k + rank)` across retrievers). They are meaningful for ordering but carry no similarity interpretation. An absolute floor would be nonsense.

So the flag is one name with three semantics, chosen per mode, documented on the flag.

## Proposed change

### Flag

- `--floor <value>` — numeric threshold. Interpretation depends on `--mode`:
  - **`--mode dense`**: absolute cosine similarity. Drop results whose dense score is `< value`. Sensible values are in `[0.0, 1.0]`; out-of-range raises per ADR-001.
  - **`--mode bm25`**: relative ratio. Drop results whose BM25 score is `< value × top_hit_bm25_score`. `--floor 0.3` keeps hits within 30% of the top hit's BM25 score. Sensible values are in `[0.0, 1.0]`.
  - **`--mode hybrid`**: relative ratio, same semantics as BM25 mode, but applied to the RRF score. `--floor 0.5` keeps hits whose RRF score is at least half the top hit's RRF score.

The flag is valid under every mode; it never silently no-ops.

### Output

- The result set may contain `0 <= n <= k` results.
- The JSON response adds two echoing fields so callers can audit what happened:

```json
{
  "floor": {
    "value": 0.3,
    "interpretation": "relative",
    "effective_threshold": 7.42
  },
  ...
}
```

- `interpretation` is `"absolute"` under dense, `"relative"` under bm25 and hybrid.
- `effective_threshold` is the concrete cutoff score in the mode's native units (useful for debugging why the response is short).
- When `--floor` is not supplied, `floor` is `null`.

### Defaults and ergonomics

- `--floor` has no default — absence of the flag means no floor.
- A `--floor 0.0` (or `0`) is equivalent to absence of the flag and is accepted as a no-op.

### Failure modes (ADR-001)

- `--floor` value outside `[0.0, 1.0]` → raise with explicit message naming the mode and the accepted range.
- `--floor` value with obviously-wrong intent (negative, non-numeric) → raise.
- All-hits-culled is **not** a failure — it is a legitimate result. The response is an empty `results` list with the `floor` field populated so the caller can see why.

## Alternative considered

Splitting into `--floor-abs` and `--floor-rel` so the caller names the semantics explicitly. Rejected for MVP: doubles the flag surface for a rarely-touched knob, and the mode-aware single flag is already well-documented by the `interpretation` field in the response. If user confusion surfaces from the field, revisit.

## Impact on referenced docs

- **ADR-007:** one additive flag; one additive response field. No breaking change.
- **ADR-001:** every out-of-range or malformed input is a loud failure. An empty result set is not a failure.
- **Principle 001:** the eval harness should optionally run with a floor applied so recall / nDCG numbers can be interpreted under a floor regime; orthogonal to this CR.

## Open questions

- Does a `--floor` with `--mode hybrid` interact cleanly with the reranker (cr-003, if it ships)? Probably — the floor applies to the final score used for ordering, whether that is RRF or rerank. To be confirmed when the reranker stages.
- Is there a user-facing metaphor better than `interpretation: "absolute" | "relative"`? (`"cosine"` vs `"ratio"`, maybe.) Resolve during implementation.

## Decision

Staged.

## User stories (scrum)

*Channeling the Scrum Lead persona: outcome before solution, vertical slices only, observable acceptance criteria, INVEST as a floor.*

Before decomposing, let me name what I'm reading. The stakeholder asked for a `--floor` flag, which is a solution phrased as a proposal. The underlying outcome is: *callers driving the CLI want to cap irrelevance at the tail of top-K, rather than be forced to eyeball a padded result list.* The mode-aware semantics are a design constraint, not the outcome — they exist because BM25, dense, and hybrid scores live on different scales. That distinction matters for how I slice.

Each slice below is independently demoable end-to-end: a real `scripvec query` command runs, a real JSON response comes back, the feature is observable without stubbing. I've kept the "malformed input raises" story separate from the "in-range threshold culls results" story because they answer different questions and can be picked up independently.

### Story 1 — Dense-mode absolute floor culls low-similarity tail

**As** a caller running `scripvec query --mode dense`,
**when** I pass `--floor 0.55`,
**I want** the response to contain only hits whose cosine similarity is `>= 0.55`,
**so that** the tail of weakly-related verses does not pad the result set.

Acceptance criteria:
- Given a dense query that would return K=10 hits with scores ranging from 0.82 down to 0.31, when I pass `--floor 0.55`, then the `results` array contains only the hits with score `>= 0.55`.
- The `floor` field in the response is populated: `{"value": 0.55, "interpretation": "absolute", "effective_threshold": 0.55}`.
- When no hits pass the floor, `results` is an empty list (not an error), and the `floor` field is still populated so the caller can see why.
- When `--floor` is omitted, the `floor` field in the response is `null`.
- `--floor 0.0` and `--floor 0` both behave identically to omitting the flag — all hits pass, `floor.value` is `0.0`, `effective_threshold` is `0.0`.

### Story 2 — BM25-mode relative floor keeps hits within a ratio of the top score

**As** a caller running `scripvec query --mode bm25`,
**when** I pass `--floor 0.3`,
**I want** the response to contain only hits whose BM25 score is at least `0.3 × top_hit_bm25_score`,
**so that** I can bound the drop-off without needing to know the corpus-specific BM25 scale.

Acceptance criteria:
- Given a BM25 query whose top hit scores 24.7, when I pass `--floor 0.3`, then every hit in `results` has a BM25 score `>= 7.41` (0.3 × 24.7).
- The `floor` field is `{"value": 0.3, "interpretation": "relative", "effective_threshold": 7.41}` (or the actual numeric cutoff in the mode's native units).
- When the query returns zero hits at all (top hit does not exist), `effective_threshold` is reported as `0.0` and `results` is empty; no divide-by-top error.
- `--floor 1.0` keeps only hits tied with the top score.
- `--floor 0.0` is a no-op; all hits pass.

### Story 3 — Hybrid-mode relative floor applies to RRF scores

**As** a caller running `scripvec query --mode hybrid`,
**when** I pass `--floor 0.5`,
**I want** the response to contain only hits whose RRF score is `>= 0.5 × top_hit_rrf_score`,
**so that** the same ratio-based intuition from BM25 mode carries over to hybrid mode without me having to learn a different knob.

Acceptance criteria:
- Given a hybrid query whose top hit has RRF score 0.0312, when I pass `--floor 0.5`, then every hit in `results` has an RRF score `>= 0.0156`.
- The `floor` field is `{"value": 0.5, "interpretation": "relative", "effective_threshold": 0.0156}`.
- The cutoff is applied to the *final ordering score* (RRF today; whatever replaces it later if a reranker lands), not to any component score.
- `--floor 0.0` is a no-op; all hits pass.

### Story 4 — Out-of-range and malformed `--floor` values raise loudly

**As** a caller who fat-fingers a floor value,
**when** I pass `--floor 1.5`, `--floor -0.2`, or `--floor abc`,
**I want** the CLI to exit with a clear error message naming the mode and the accepted range,
**so that** I don't get a silently-truncated response that hides the mistake (per ADR-001).

Acceptance criteria:
- `--floor 1.5` exits non-zero with a message that names the current mode and states the accepted range is `[0.0, 1.0]`.
- `--floor -0.2` exits non-zero with the same message.
- `--floor abc` (non-numeric) exits non-zero with a parse error naming the flag.
- No partial result is emitted on the failure path — the error is loud, not a warning.
- The error message is consistent across `--mode dense`, `--mode bm25`, and `--mode hybrid` (the range is the same under all three modes).

### Story 5 — Response shape documents the floor so callers can audit

**As** an AI-agent caller that just received a short result set,
**when** I inspect the response,
**I want** the `floor` field to tell me the value I passed, which interpretation applied, and the concrete effective threshold,
**so that** I can explain to myself or a downstream step why the response is shorter than K (per ADR-007).

Acceptance criteria:
- Every successful response carries a top-level `floor` key, either populated or `null`.
- `floor.interpretation` is exactly `"absolute"` under dense mode and exactly `"relative"` under bm25 and hybrid modes.
- `floor.effective_threshold` is a number in the mode's native score units and matches the cutoff actually applied.
- When `results` is empty because of the floor, nothing else in the response shape changes — the caller's parser should not branch on "empty vs non-empty results".
- A test fixture captures the full response JSON under each of: no floor, floor keeps all, floor culls some, floor culls all. Snapshotted so future drift is visible.

### Sequencing note (not a priority call)

Stories 1–3 are independent of each other — each mode's floor logic can be built, tested, and demoed on its own. Story 4 (validation) depends on *any one* of 1–3 being in place so the flag exists to be validated; it does not need all three. Story 5 (response shape) is structurally shared across 1–3 and is cheapest to land alongside Story 1 since dense is the simplest semantic.

Prioritization is the stakeholder's call. I'm flagging that Story 5 is load-bearing for the ADR-007 audit posture, and that Story 4 is load-bearing for the ADR-001 no-silent-failures posture — both are non-negotiable for "done" on this CR even if the mode-specific stories ship incrementally.

### Open questions surfaced to stakeholder

- The CR's open question about `"cosine"` vs `"ratio"` as friendlier labels for `interpretation` — I've left the acceptance criteria on `"absolute"` / `"relative"` as written in the CR. If the label changes, Story 5's criteria shift with it. Flagging so the decision isn't forgotten at implementation time.
- The CR's open question about reranker interaction (cr-003) is not in scope here; Story 3 is written against RRF as the final hybrid score. If a reranker ships, a follow-up story adjusts what "final ordering score" means — that's a new decomposition, not a patch to this one.

## Beads plan (bead-planning persona)

*Note on persona sourcing: the personas DB was searched for "bead planning" / "bead writing" / related queries and no dedicated bead-planning persona exists in the DB. The closest available match returned by the DB is the Scrum Lead profession, which is channeled here for dependency-linked work-item planning. The substitution is logged in the CR audit log.*

*Channeling the Scrum Lead to convert user stories into bead-shaped work items: each bead is a discrete, swarm-pickable task with explicit dependencies, observable acceptance criteria, and no hidden solutioning.*

The beads below map the five user stories onto the beads tracker. The mapping is not one-story-one-bead — some stories cleanly collapse into a single bead, others split because the story mixes "add the plumbing" with "wire it to a mode." I've preferred more, thinner beads over fewer fat ones, same discipline as vertical-slicing stories. Dependencies flow forward: a bead that needs another bead's output blocks on it.

### Bead B1 — Add `--floor` flag surface and validation to `scripvec query`

**Slice:** CLI flag parsing + input validation only. No semantic effect on results yet.

**Depends on:** nothing.

**Acceptance criteria:**
- `scripvec query --floor <value>` accepts a numeric value.
- Values outside `[0.0, 1.0]` raise with a message naming the current `--mode` and the accepted range `[0.0, 1.0]`.
- Non-numeric values raise a parse error naming the flag.
- `--floor 0.0` and `--floor 0` parse successfully and are stored as the same internal value.
- Absence of `--floor` leaves the internal floor config as "not set" (distinct from `0.0`, since the response shape differs).
- A contract test covers each of: valid in-range, boundary `0.0`, boundary `1.0`, out-of-range high, out-of-range low, non-numeric, absent.

**Rationale:** landing the flag surface first lets every downstream bead (B2/B3/B4) be a thin semantic patch. Also satisfies Story 4's ADR-001 posture independently of which mode is wired first.

---

### Bead B2 — Dense-mode absolute floor: cull results below cosine threshold

**Slice:** applies `--floor` under `--mode dense` only. BM25 and hybrid still ignore the value (tracked in B3/B4).

**Depends on:** B1.

**Acceptance criteria:**
- Under `--mode dense`, hits with cosine score `< floor.value` are dropped before top-K is returned.
- `--floor 0.0` is a no-op; behavior is identical to absence of the flag except that the response `floor` field is populated with `value: 0.0`.
- When all hits are culled, `results` is an empty list; no error.
- Unit test: fixture query returning hits at `[0.82, 0.71, 0.55, 0.42, 0.31]`, `--floor 0.55` keeps three hits.
- Unit test: all-culled case returns empty `results` with `floor` populated.

---

### Bead B3 — BM25-mode relative floor: cull results below `value × top_hit_score`

**Slice:** applies `--floor` under `--mode bm25`.

**Depends on:** B1. Independent of B2.

**Acceptance criteria:**
- Under `--mode bm25`, hits with score `< floor.value × top_hit_bm25_score` are dropped before top-K is returned.
- When the underlying query returns zero hits (no top hit exists), `effective_threshold` is `0.0` and `results` is empty; no divide-by-zero or other error.
- `--floor 1.0` keeps only hits tied with the top score.
- `--floor 0.0` is a no-op.
- Unit test: fixture query with top hit 24.7, `--floor 0.3` drops all hits below 7.41.
- Unit test: zero-hit query with `--floor 0.5` returns empty results cleanly.

---

### Bead B4 — Hybrid-mode relative floor: cull results below `value × top_hit_rrf_score`

**Slice:** applies `--floor` under `--mode hybrid`, operating on the final RRF score.

**Depends on:** B1. Independent of B2 and B3.

**Acceptance criteria:**
- Under `--mode hybrid`, hits with RRF score `< floor.value × top_hit_rrf_score` are dropped before top-K is returned.
- The cutoff is applied to the *final ordering score* currently used for hybrid (RRF today), not to any component score.
- `--floor 0.0` is a no-op.
- Unit test: fixture hybrid query with top RRF 0.0312, `--floor 0.5` drops all hits below 0.0156.

---

### Bead B5 — Response shape: populate `floor` field with value, interpretation, effective_threshold

**Slice:** JSON response schema change. Adds `floor` as a top-level key on every response.

**Depends on:** B1. Should land alongside or immediately after the first mode-specific bead (B2 is simplest).

**Acceptance criteria:**
- Every response carries top-level `floor` key.
- When `--floor` is absent, `floor` is `null`.
- When `--floor` is set, `floor` is an object with `value`, `interpretation`, `effective_threshold`.
- `interpretation` is exactly `"absolute"` under dense, exactly `"relative"` under bm25 and hybrid.
- `effective_threshold` is the concrete cutoff score in the mode's native units (cosine for dense; BM25 score for bm25; RRF score for hybrid).
- When `--floor` is set but `results` is empty (all-culled or zero-hit), the `floor` field is still populated with the same shape.
- Snapshot fixtures under: no-floor, floor-keeps-all, floor-culls-some, floor-culls-all — one per mode once B2/B3/B4 land.

**Rationale:** separating the response-shape bead from the semantic beads lets the JSON contract be reviewed independently of the cutoff logic.

---

### Bead B6 — CLI contract tests pinning ADR-001 and ADR-007 posture

**Slice:** contract tests that fail loudly if `--floor` drifts from spec.

**Depends on:** B1, B2, B3, B4, B5.

**Acceptance criteria:**
- Test that every out-of-range / malformed `--floor` value exits non-zero with the expected message (ADR-001).
- Test that the response always carries the `floor` key (null or populated) and matches the snapshot shape (ADR-007).
- Tests are wired into the same `cli/test_contracts.py` harness as existing CLI contract tests.
- Failure output on mismatch names the drifted field, not just "assertion failed".

---

### Bead B7 — Docs: flag reference and mode-aware semantics

**Slice:** user-facing documentation entry for `--floor`.

**Depends on:** B2, B3, B4 (to describe real behavior, not aspirational).

**Acceptance criteria:**
- `--floor` is listed in the CLI help text for `scripvec query` with a one-line summary that mentions mode-dependence.
- Long-form docs (wherever CLI flags are documented in this repo) describe:
  - dense mode: absolute cosine; `[0.0, 1.0]`
  - bm25 mode: relative to top hit
  - hybrid mode: relative to top hit's RRF score
- The response's `floor` field is documented with an example JSON block.
- Out-of-range values are documented as errors, not warnings.

---

### Dependency graph (concise)

```
B1 (flag surface)
├── B2 (dense semantic)
├── B3 (bm25 semantic)
├── B4 (hybrid semantic)
└── B5 (response shape)    [can parallel B2]

B6 (contract tests)  depends on B1, B2, B3, B4, B5
B7 (docs)            depends on B2, B3, B4
```

B2, B3, B4 are independent of each other and can be picked up by three different swarm agents in parallel once B1 lands. B5 can ship alongside any one of them. B6 gates the CR as "done" from an ADR-conformance standpoint. B7 gates it as "done" from a user-facing standpoint.

### Notes surfaced from Scrum-Lead channel

- No estimates or story points on these beads — the Scrum Lead persona deprioritizes effort estimation entirely, and the project's memory note on beads does not require them either.
- The interpretation-label open question (`"absolute"/"relative"` vs `"cosine"/"ratio"`) is embedded in B5's acceptance criteria as written. If the label changes before B5 is picked up, update B5's criteria; don't paper over with a mapping layer.
- A hypothetical future reranker (cr-003) would patch B4 only; a new bead would replace B4's definition of "final ordering score". Not a dependency for this CR.

## Audit log

- 2026-04-20 — created as `staged`.
- 2026-04-20 — user stories added (Scrum Lead persona channeled).
- 2026-04-20 — beads plan added. Personas DB had no "bead planning" / "bead writing" entries; Scrum Lead (top DB match for planning-related queries) was used as a substitute and the substitution is noted in the Beads plan section.
