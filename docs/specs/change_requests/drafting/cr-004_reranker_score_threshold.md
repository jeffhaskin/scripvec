---
id: 004
title: Reranker low-score drop threshold from retroactive distribution analysis
status: drafting
created: 2026-04-19
updated: 2026-04-19
references:
  - docs/specs/adrs/008_accepted_cross_encoder_reranker_defaults.md
  - cr-003_cross_encoder_reranker.md
  - cr-002_mvp_retrieval_stack.md
  - docs/principles/001_vector_retrieval.md
---

# CR-004: Reranker low-score drop threshold from retroactive distribution analysis

## Summary

Introduce a low-score drop policy for the cross-encoder reranker. The default set by ADR-008 is "return the top-k by `rerank_score` regardless of absolute value." This CR replaces that default with a data-driven cutoff — either an absolute score floor, a per-query relative drop (e.g., any result whose `rerank_score` is more than Δ below the top result), or both — picked from a retroactive analysis of the `rerank_score` distribution captured in production query logs after CR-003 has been in use long enough to have accumulated a statistically meaningful sample.

## Motivation

ADR-008 deliberately ships CR-003 with no score threshold so that the output schema stays stable while the engineer accumulates data. "Return always" is a conservative default — it never drops a result the caller might have wanted — but it also surfaces confidently-irrelevant results when the retrieval stage produces poor candidates. The long-run correct behavior is to drop those results, not display them.

Picking a threshold from first principles at rollout would be guesswork: `rerank_score` is not calibrated across queries, and the absolute score range for "clearly relevant" vs "clearly irrelevant" on scripvec's corpus and query mix is unknown until it is measured. This CR parks the work as a well-defined next step that activates once the score distribution can be characterized from real queries — not from a synthetic held-out.

## Proposed change

### Prerequisites

- CR-003 has been accepted and the reranker has been in the live query path long enough for `data/logs/queries.jsonl` to contain a statistically adequate sample of `rerank_score` values. A working definition: at least a few hundred distinct queries across the expected query-tag buckets (doctrinal, narrative, phrase-memory, proper-noun), with corresponding `rerank_score` arrays per result.
- The `scripvec feedback` surface from CR-002 has accumulated enough graded feedback to let the analysis correlate `rerank_score` with observed relevance, at least for a subset of queries.

### Analysis

- Load all `rerank_score` values from `data/logs/queries.jsonl` across a specified window (e.g., last N days or last M queries).
- Partition by the query-tag buckets used in CR-002's stratified eval.
- For each bucket, characterize:
  - Score distribution of all results (histogram, quantiles).
  - Score distribution of results that were recorded as relevant (grade 1 or 2) via `scripvec feedback` vs results left unmarked or graded 0.
  - Within a single query's result list, the score *gap* between the top result and each successive result, as a per-query relative signal.
- Pick one or both of:
  - An **absolute score floor** (drop any result with `rerank_score < T_abs`), where `T_abs` is chosen so that a large majority of known-irrelevant results are cut while a small minority of known-relevant results are not.
  - A **per-query relative drop** (drop any result whose `rerank_score` is more than Δ below the top result of the same query), where Δ is chosen to preserve the elbow of the per-query score curve.

### Change

- Add a threshold-drop stage to the reranker pipeline, applied after the reranker has scored the top-K candidates and before truncation to the user's top-k.
- Configuration in the project-root config file under `[reranker]`:
  - `score_floor = <float>` — drop results below this absolute value. `null` = no absolute floor.
  - `relative_drop = <float>` — drop results whose score is more than this below the top result. `null` = no relative drop.
- CLI flag override: `--rerank-score-floor <float>` and `--rerank-relative-drop <float>`, per-invocation. `off` disables.
- Output schema (ADR-007, CR-002): add a `dropped_below_threshold` integer field to the top-level query output so agents can tell that fewer-than-k results is a deliberate threshold action, not an empty retrieval.
- The zero-results case remains exit code `2` per ADR-007; a below-k case with `dropped_below_threshold > 0` remains exit code `0`.

### Acceptance gate

- The chosen thresholds must preserve at least 95% of known-relevant results (grade 1 or 2) from the analysis window.
- The chosen thresholds must reduce the count of known-irrelevant results (unlabeled or grade 0, controlling for sampling) by at least 30% in aggregate across the buckets.
- No query-tag bucket may individually lose more than 5% of its known-relevant results.

If no threshold choice satisfies all three gates, the CR is archived with the measurement recorded — "return always" remains the default.

## Impact on referenced docs

- **ADR-008:** this CR relaxes its "return always, no low-score drop" default. The relaxation is the explicit extension point ADR-008 anticipated, so no ADR amendment is required beyond noting the CR's outcome.
- **CR-003:** additive. The reranker pipeline grows one post-reranker stage. No conflict.
- **CR-002:** query output schema grows one additive field (`dropped_below_threshold`). Non-breaking per ADR-007's schema-evolution rules.
- **Principle 001 (vector retrieval):** consistent — threshold is picked from measurement, not intuition.

## Decision

Not yet decided. Awaiting accumulation of production query logs and feedback data sufficient to characterize the `rerank_score` distribution.

## Audit log

- 2026-04-19T00:00:00Z — created as `drafting`.
