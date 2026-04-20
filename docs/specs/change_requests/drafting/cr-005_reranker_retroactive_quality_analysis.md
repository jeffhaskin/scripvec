---
id: 005
title: Retroactive reranker quality analysis against accumulated query logs
status: drafting
created: 2026-04-19
updated: 2026-04-19
references:
  - docs/specs/adrs/008_accepted_cross_encoder_reranker_defaults.md
  - cr-003_cross_encoder_reranker.md
  - cr-004_reranker_score_threshold.md
  - cr-002_mvp_retrieval_stack.md
  - docs/principles/001_vector_retrieval.md
---

# CR-005: Retroactive reranker quality analysis against accumulated query logs

## Summary

After the cross-encoder reranker (CR-003) has been in the live query path long enough to accumulate a meaningful sample of production queries and user feedback, run a retroactive quality analysis against the logs. The analysis validates — or refutes — ADR-008's defaults (K = 30, MaxP chunk aggregation, full-replacement score fusion) on scripvec's actual query stream, and produces a characterization of reranker quality that fills the eval-visibility gap ADR-008 knowingly accepted at rollout.

## Motivation

ADR-008 ships the reranker with deliberate eval opacity: CR-003's acceptance gate (≥ 3 pts nDCG@10 lift on the CR-002 held-out set) is honored, but no reranker-specific eval set, no calibration study, and no chunked-MaxP-specific validation exist at rollout. ADR-008 calls this "flying blind on reranker-specific quality" and defers the remediation to this CR.

The defaults locked by ADR-008 are informed priors, not measured outcomes. K = 30 is plausible but not load-bearing-proven. MaxP has literature precedent but has not been tested on scripture-shaped long documents (D&C sections with surface keyword overlap). Full replacement is the reference stack's default but has not been measured against scripvec's proper-noun-heavy query tail. This CR is how those priors become measurements.

## Proposed change

### Prerequisites

- CR-003 has been accepted and the reranker has been in production long enough to accumulate a few hundred distinct queries across the expected query-tag buckets (doctrinal, narrative, phrase-memory, proper-noun).
- `data/logs/queries.jsonl` contains the full per-query record: query text, mode, per-stage scores (`bm25`, `dense`, `rrf`, `rerank_score`), chunk counts and per-chunk scores where chunking occurred, and result ranks.
- `data/logs/feedback.jsonl` (populated via `scripvec feedback`) contains a non-trivial graded sample.

### Analysis axes

Each axis is scoped to answer a specific question about an ADR-008 default. The CR is a success if each question is answered "default holds" or "default should change to X," with supporting numbers.

1. **K = 30 — does it leave recall on the table?**
   - For the sample, re-run retrieval with K = 50 and K = 100 offline, rerank, and compare the top-k outputs to what was shipped with K = 30.
   - Measure how often a non-trivially differently-ranked result appears in the K > 30 run. Cross-reference with `scripvec feedback` grades.
   - Outcome: keep K = 30, raise to 50, raise to 100, or accept measurement-bounded uncertainty.

2. **MaxP — does it misfire on long D&C sections?**
   - Restrict to queries where at least one candidate required chunking.
   - For each, recompute the document score under alternative aggregations (top-3 mean, mean, log-sum-exp) using the stored per-chunk scores in the log.
   - Measure: does an alternative aggregation promote any feedback-confirmed-relevant result that MaxP demoted, or vice versa? Measure aggregate and per-bucket.
   - Outcome: keep MaxP, propose a MaxP → top-k-mean swap ADR, or propose a per-bucket aggregation choice.

3. **Full replacement — are there queries where RRF was right and the reranker was wrong?**
   - Compare the rerank-ordered top-k against the RRF-ordered top-k for the same queries.
   - Identify divergences where feedback grades indicate RRF's top was relevant and the reranker displaced it.
   - Measure the rate of this failure mode, per bucket.
   - Outcome: keep full replacement, propose a per-bucket fallback (e.g., for proper-noun queries, defer to RRF), or propose a weighted blend ADR with measured α.

4. **Threshold candidates — what does the `rerank_score` distribution look like?**
   - The analysis feeds directly into CR-004 and should share tooling.
   - Report score distributions per bucket, per grade-label where labels exist.

### Deliverables

- A report file at `data/analyses/reranker_quality_<date>.md` with per-axis measurements, plots or tabulated histograms, and a verdict per ADR-008 default.
- If any axis argues for a default change, the report names the ADR or CR that would carry that change. It does not land the change; it recommends it.
- The raw analysis code lives in `packages/eval/` as a one-shot script, not a new CLI command.

### Non-goals

- This CR does not change any default. It measures. Changes are landed by whatever ADR or CR the report recommends.
- This CR does not build a bespoke reranker eval set. It uses the data already being logged, plus `scripvec feedback`. A bespoke labeled set is a separate future effort if the retroactive analysis is insufficient on its own.

## Impact on referenced docs

- **ADR-008:** informed by this CR's output. If any default is overturned, ADR-008 gets an Amendment Log entry at that time.
- **CR-003:** the eval-gate numbers in CR-003 are based on a synthetic held-out; this CR supplements them with production-stream measurements. No conflict.
- **CR-004:** shares tooling with this CR's axis 4 and is informed by axis 4's output. If CR-004 is executed first, its score-distribution characterization feeds here; if this CR is executed first, axis 4 is a prerequisite for CR-004.
- **CR-002:** the eval harness infrastructure (`packages/eval/`) hosts the analysis script. No schema change.
- **Principle 001 (vector retrieval):** consistent — this CR is the mechanism by which ADR-008's knowingly-deferred evaluation becomes real.

## Decision

Not yet decided. Awaiting accumulation of production query logs and feedback data sufficient to support the four analysis axes.

## Audit log

- 2026-04-19T00:00:00Z — created as `drafting`.
