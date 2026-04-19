---
id: 003
title: Cross-encoder reranker on fused results
status: pending
created: 2026-04-19
updated: 2026-04-19
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - cr-002_mvp_retrieval_stack.md
  - docs/principles/001_vector_retrieval.md
---

# CR-003: Cross-encoder reranker on fused results

## Summary

Extend the MVP retrieval stack (CR-002) with a cross-encoder reranker applied to the top-N RRF-fused hybrid results. The reranker consumes `(query, verse_text)` pairs and re-scores them with a pairwise model; the reranked order replaces the RRF order for the final top-k returned to the caller. The addition is gated on a measured lift against the existing held-out eval set.

## Motivation

Under the Retrieval Engineer's priors, a cross-encoder reranker on the top-50 of a BM25 + dense RRF fusion is the single largest quality lift typically available after hybrid retrieval — commonly 3–10 points of nDCG@10 on top of the fusion baseline. The lift is free in ranking quality but not free in latency, model surface area, or ablation time, so it was deferred out of MVP scope (see CR-002's Decision section).

This CR parks the work as a well-defined next step so that the first post-MVP quality effort is not a fresh design exercise but a measured ablation against an already-instrumented eval set.

## Proposed change

### Candidate models

First two to measure, in order:

1. `BAAI/bge-reranker-base` — natural first pick; well-trained general-purpose cross-encoder.
2. `cross-encoder/ms-marco-MiniLM-L-6-v2` — long-standing reference cross-encoder; lower latency, lower ceiling.

The reranker is local (no endpoint round-trip) — it is a direct consumer of `transformers` / `sentence-transformers` cross-encoder interfaces, not of the ADR-005 embedding endpoint. Pin the chosen model's revision SHA and add it to the index-side `config.json` so the drift guard from CR-002 covers it.

### Integration point

- `--mode hybrid` continues to produce an RRF-fused top-N (configurable; default N=50).
- New flag: `--rerank {off|on}` on `scripvec query`. Default at roll-in: `on`. During the ablation phase, the eval harness runs both on and off.
- Reranker re-scores the fused top-N using pairwise `(query, verse_text)` scoring; returns the top-k by reranker score.
- `--mode {bm25,dense,hybrid}` without the flag behaves exactly as in CR-002 — the reranker is additive, not a replacement.
- Output schema (JSON, per ADR-007): add a `rerank_score` field to each result object when `--rerank on`, and a `reranker` section to the top-level `latency_ms` object.

### Eval harness extension

Add `hybrid+rerank` as a reported row alongside `bm25`, `dense`, and `hybrid (rrf)` in the eval output. Report the same metrics (recall@10, recall@20, nDCG@10, MRR@10, p50_ms, p95_ms). Preserve the query-bucket stratification from CR-002. Structured JSON output per ADR-007; `--format text` continues to produce a human-readable ASCII table.

### Artifact and config

- Reranker becomes a second pinned model entry in the index-side `config.json` (under a new `reranker` key). The BLAKE2b config hash grows to include it.
- `scripvec index build` downloads the reranker alongside the embedder so a cold build is a single command.
- Logs: add `rerank_score` per returned result to the query log schema; bump `schema_version`.

### Acceptance gate

Before moving from `pending` → `accepted`, the reranker must clear:

- **≥ 3 pts nDCG@10** over the existing `hybrid (rrf)` baseline on the held-out eval set.

If `bge-reranker-base` fails the lift gate, the CR pivots to `ms-marco-MiniLM-L-6-v2`. If that also fails, the CR is archived with the measured numbers recorded.

## Impact on referenced docs

- **ADR-001 (fail loud):** the drift guard extends to cover the reranker revision SHA. No conflict.
- **ADR-007 (agent-first CLI):** new fields are additive to the existing JSON schema; no breaking change. No conflict.
- **CR-002:** this CR is strictly additive. The `--mode` semantics, RRF fusion defaults, and eval metrics are unchanged; `--rerank` is a new, independent flag. No conflict.
- **Principle 001 (vector retrieval):** the CR is gated on measured lift against the same held-out set — consistent with the eval-first disposition.

## Decision

Not yet decided. Awaiting engineer attention when MVP is shipped and the held-out eval set has produced its first baseline numbers.

## Audit log

- 2026-04-19T23:04:32+02:00 — created as `pending`.
