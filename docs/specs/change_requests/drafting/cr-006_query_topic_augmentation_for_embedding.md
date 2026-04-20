---
id: 006
title: Query topic augmentation before embedding
status: drafting
created: 2026-04-20
updated: 2026-04-20
references:
  - cr-002_mvp_retrieval_stack.md
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md
  - docs/specs/adrs/006_accepted_serialize_embedding_calls.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-006: Query topic augmentation before embedding

## Summary

Before the dense-retrieval path embeds a user query, route the raw query through a topic-augmentation step: an LLM call that answers *"what is the topic of this request, and what is the user looking into?"* and returns a richer, denser description of the intent. The augmented text — not the raw query — is what gets embedded. The hypothesis is that a richer, topic-naming description aligns better with the verse text in embedding space than the user's surface query, especially for short, vague, or under-specified queries.

This is a query-expansion / HyDE-adjacent technique. BM25 still sees the raw query; only the dense side consumes the augmentation.

## Motivation

scripvec's MVP embeds the raw query string against a verse corpus. For terse or vague queries (`"faith"`, `"why did the church start tithing"`), the dense embedding has very little signal to align with verses that are themselves longer and topically explicit. An augmentation step that produces, say, *"This question is about the doctrinal basis and historical origin of tithing in the Latter-day Saint tradition, including relevant Old Testament precedent and 19th-century revelations."* gives the dense side substantially more surface to match against.

Why this is plausibly worth building:

- The existing eval harness (CR-002) directly measures whether augmentation moves recall@10 / nDCG@10 / MRR@10. If it does not, the change is rejected on data, not vibes.
- The change is bounded — it is one new step before the existing dense path. RRF, BM25, persistence, and CLI shape are unchanged.
- The augmentation step can be flagged on/off per query, so A/B comparison against the un-augmented baseline is trivial within the existing eval harness.

Why this is non-trivial:

- It introduces a **new external dependency** (a chat-completion endpoint) into the query path, separate from the ADR-005 embedding endpoint.
- It changes what gets embedded. That has reproducibility, drift-guard, and config-hash implications.
- Latency goes up by one LLM round-trip on every query.

## Proposed change

### Mechanism

1. The CLI / `retrieval.query()` accepts the raw query as today.
2. If augmentation is enabled (see *Toggle*), the raw query is sent to an LLM via a chat-completion endpoint with a fixed system prompt asking it to (a) name the topic of the request and (b) write a longer description of what the user is looking into. The output is a single text block.
3. The augmented text — concatenated with or replacing the raw query (see *Open questions*) — is embedded by the existing ADR-005 embed client. The 8K-token cap still applies; oversize inputs raise per ADR-005.
4. Dense top-k uses the augmented embedding. BM25 top-k continues to use the raw query unchanged.
5. RRF fusion is unchanged.

### Toggle and defaults

- A new `--augment {on|off}` flag on `scripvec query` (and a matching keyword arg on `retrieval.query()`).
- Default state (on or off) is **deferred** — it is decided after the eval harness reports recall lift from augmentation. ADR-008-style "ship as default-on once measured" is the model.
- The eval harness gains a new mode dimension so `recall@10` is reported separately for `dense+augment`, `dense` (raw), `bm25`, and `hybrid+augment` vs `hybrid` (raw). The metric the change has to clear is the same kind of held-out lift CR-002 already specifies.

### Augmentation client

- Lives in `packages/retrieval/` as a single new module — the sanctioned entry point to the chat-completion endpoint, mirroring the ADR-006 discipline around the embed client (one entry point, no parallel/concurrent calls).
- Config is env-sourced like the embed client: chat endpoint base URL, API key, model identifier. No hardcoded values. No bearer token in the repo.
- The system prompt that defines the augmentation instruction is checked into the package and is part of the config-hash manifest (so an index built against a given augmentation prompt is recognizable as such).

### Failure handling (ADR-001)

Three failure modes need explicit decisions, and none of them silently fall back to the raw query:

1. **Endpoint unreachable / non-2xx.** Loud failure — the query exits with the existing exit code 3 (upstream error) and a structured stderr error. No silent fallback to the un-augmented path; that would defeat measurement.
2. **Augmented text exceeds 8K tokens.** Loud failure per ADR-005. (The augmentation prompt should constrain the LLM, but the cap is enforced at the embed client boundary.)
3. **LLM returns an empty / malformed response.** Loud failure with a distinct error code. (Open question: is a designed retry warranted here per ADR-001 Exception 2? Probably not at MVP-of-this-feature.)

### Config-hash and drift-guard implications

The query-side embedding input is no longer a function of the query alone — it is a function of `(query, augmentation_prompt, augmentation_model, augmentation_endpoint_url)`. To preserve eval reproducibility:

- The augmentation prompt text, model identifier, and endpoint URL are added to the config-hash manifest (CR-002).
- The endpoint-drift guard (CR-002) is extended to assert the augmentation endpoint, model, and prompt match between query-time and the index's `config.json`.
- An index built with augmentation off and queried with augmentation on is a drift case. Decision: **refuse it, raise loudly.** Augmentation toggling between build-time (which doesn't matter, since verses are embedded directly) and query-time is allowed only when the toggle is part of the query call, not part of the index identity.

(Note: this CR does not propose embedding *verses* through the augmentation step — only *queries*. The verse side of the index is unchanged.)

### Logging

`data/logs/queries.jsonl` gains:
- `augmented: true|false`
- `augmentation_text` — the LLM output
- `augmentation_latency_ms`
- `augmentation_model`

This is necessary for any retroactive analysis of whether augmentation helps (mirroring the CR-005 posture toward reranker logs).

### CLI surface

- New flag on `scripvec query`: `--augment {on|off}`.
- `--augment` is **orthogonal** to `--mode` (per ADR-007). `--mode bm25 --augment on` is valid but no-ops on the augmentation step (BM25 ignores it); the CLI may either reject the combination or accept it silently — open question.
- `scripvec --version` JSON gains the augmentation prompt hash and model identifier when augmentation is enabled in the active config.
- New per-query field in the `query` output schema: `augmentation: {enabled, model, latency_ms, text}` (only present when augmentation ran). Schema change is additive per ADR-007.

## Open questions

- **Concatenate or replace?** Embed `augmented_text` alone, or embed `query + "\n" + augmented_text`? The first is the cleaner test of the hypothesis; the second hedges by keeping the user's exact words in the embedding input. Decide via eval, not first principles.
- **Should the augmentation prompt be parameterized per query type?** A doctrinal query and a phrase-memory query may want different augmentations. Probably not at first cut — one fixed prompt, measure, then split if the per-bucket eval suggests it.
- **Should this only fire on queries below some length / vagueness threshold?** Plausible but adds a heuristic; first cut runs on every query for cleaner measurement.
- **Does the augmentation endpoint inherit ADR-006's serialize discipline?** It is a different endpoint, possibly with different concurrency guarantees. ADR-006 is scoped to the embedding endpoint specifically. A separate, narrow ADR (or an explicit clause in this CR) should record whichever decision is made.
- **What is the right ship criterion?** CR-002 ships hybrid against BM25 with a recall@10 floor. The natural analogue here is: hybrid+augment beats hybrid (raw) by some recall@10 / nDCG@10 margin on the held-out set. The exact margin is a value-level decision and lives in config, not in this CR.
- **BM25 + augment combination semantics.** Per above — reject as user error, or accept and document as no-op?

## Impact on referenced docs

- **CR-002:** this CR amends the query path and the config-hash manifest; the build pipeline and storage shape are unchanged. The eval harness gains a new mode dimension; the existing metrics (recall@10/20, nDCG@10, MRR@10, latency p50/p95) are reused unchanged.
- **ADR-001 (fail loud):** every augmentation failure mode is a loud failure. No silent fallback to the raw query — that would corrupt the eval signal. Consistent.
- **ADR-005 (embedding endpoint):** the augmented text passes through the same embed client. The 8K-token cap, dim-mismatch raise, and protocol shape are unchanged. The augmented text is one more input subject to those rules.
- **ADR-006 (serialize embedding calls):** unchanged — augmentation calls go to a *different* endpoint and do not run in parallel with embed calls (they run before them, serially). Whether augmentation calls themselves must be serialized is a separate decision (see *Open questions*).
- **ADR-007 (agent-first CLI):** the new `--augment` flag and the additive `augmentation` output field follow the existing schema-change rules. Schema change is additive — no major version bump required.
- **Principle 001 (vector retrieval):** consistent. The eval harness is the gate; augmentation ships as default-on only if it lifts measured retrieval quality.

## Decision

Not yet decided. This CR is in `drafting/` pending engineer review of the proposed mechanism, the open questions, and the eval design that would gate acceptance.

## Audit log

- 2026-04-20 — created as `drafting`.
