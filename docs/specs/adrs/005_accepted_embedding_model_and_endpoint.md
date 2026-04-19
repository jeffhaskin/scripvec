# ADR-005: Embedding model and endpoint

## Status

ACCEPTED

## Created

2026-04-19

## Modified

2026-04-19

## Supersession

*Supersedes:* none
*Superseded by:* none

## Date

2026-04-19

## Deciders

Jeff Haskin — engineer, sole decision authority at time of record.

## Context and Decision Drivers

The MVP retrieval pipeline (`cr-001_vector_search_mvp.md`) requires an embedding model to convert verse text and query text into vectors. The choice of model, API protocol, and endpoint has second-order consequences for cost, determinism, reproducibility, and evaluation. It needs to be locked before ingest or eval code is written, because embeddings are the unit of persistence — the indexed corpus is dim-pinned and model-pinned, and changing any of those requires a full re-embed.

**Decision drivers:**

- **Cost stability.** At MVP scale (~41K verses across BoM + D&C) the per-token cost of a public commercial API would be low in absolute terms, but every re-embed during eval iteration is a full pass. A self-hosted endpoint removes the cost from the iteration loop.
- **Determinism and availability.** A pinned model on a known endpoint gives a reproducible embedding function. Commercial providers silently update model versions; that incompatibility with *"the eval harness stays honest"* (ADR-001, principle 001) is load-bearing wrong for scripvec's posture.
- **Protocol portability.** An OpenAI-compatible `/embeddings` endpoint is the lingua franca of the embedding ecosystem. A later migration to any OpenAI-compatible provider (OpenAI itself, Voyage, local Ollama, another self-host) is a base-URL + model-name change, not a protocol rewrite.
- **Model is determined by the upstream endpoint, not a scripvec-side selection.** The endpoint serves **Qwen3.5 Embedding 0.6B** as its embedding model. scripvec does not choose the model comparatively; it accepts what the endpoint provides and builds around it. A sub-1B-parameter model at 1024-dim is sufficient at the MVP corpus scale (~41K verses) to beat BM25 on semantic queries while keeping the sqlite-vec index small — this ADR records that the fixed model is fit for purpose at this scale, not that it was picked from a shortlist.
- **Single-concurrency constraint.** The chosen endpoint serves one embedding request at a time. That shapes the ingest loop (serial, not parallel) but has no practical effect on query latency at MVP scale.

## Decision

The MVP embedding stack is:

- **Endpoint base URL:** `https://delphi.tail2a835b.ts.net/v1`
- **API protocol:** OpenAI-compatible `/embeddings` (POST JSON with `{"model": <name>, "input": <text>}`; response `{"data": [{"embedding": [...]}]}`).
- **Model:** **Qwen3.5 Embedding 0.6B.** The API identifier sent in the `model` field of the embeddings request is `qwen3-embedding-0.6b` — this is the endpoint's handle for Qwen3.5 Embedding 0.6B. **The model is fixed by the upstream endpoint. It is not a scripvec-side choice and cannot be swapped without switching endpoints entirely.**
- **Embedding dimension:** 1024 (pinned; see *Consequences* below).
- **Authentication:** bearer-token header is required by the protocol; the endpoint currently accepts a placeholder value. Code **must not** hardcode any token string — configuration lives in environment variables (`OPENAI_BASE_URL`, `OPENAI_API_KEY`) or a non-committed config file read at startup.
- **Input size cap:** 8,000 tokens per request. Any text that may exceed this must be rejected up front — no silent truncation, per ADR-001.
- **Client-side normalization:** every vector returned by the endpoint is L2-normalized in the client before persistence. Downstream similarity computations are therefore inner-products (equivalent to cosine on unit vectors) and the index does not need to re-normalize at query time.
- **Storage:** vectors are stored in a `sqlite-vec` `vec0` virtual table typed `float[1024]`.

### What is pinned and what is configurable

- **Pinned in code:** the protocol shape, the 1024-dim assumption in the sqlite-vec schema, and the requirement that the returned vector length match the pinned dim (mismatch is a loud failure, not a coercion).
- **Configurable at runtime:** base URL, API key, the `model`-identifier string sent in the request, and the dim. These live in config/env so that a future *endpoint* migration does not require a code change. Changing the dim, or switching to an endpoint that serves a different underlying model, invalidates the stored index and requires a full re-embed.
- **Not a scripvec-side choice:** the *actual* embedding model. It is whatever the configured endpoint serves. Today that is Qwen3.5 Embedding 0.6B. There is no scripvec-level lever for selecting a different model on the current endpoint.

### Failure handling

Consistent with ADR-001:

- HTTP errors from the endpoint raise. No retry-with-backoff at MVP unless a future ADR explicitly authorizes it as Exception 2.
- A vector whose length does not match the pinned dim raises a `RuntimeError` with the observed and expected dims in the message.
- A text input over the 8K-token cap is rejected before the request is made. Chunking/pooling is not performed silently — if a caller needs it, it must be an authored feature with its own module.

## Consequences

**Positive:**

- Embedding cost is zero per request at runtime (the endpoint is self-hosted), so eval-harness iteration is not cost-gated.
- The model is version-pinned on the endpoint, so the embedding function is reproducible. Re-running the eval harness a month from now on the same corpus produces the same vectors.
- OpenAI-compatible protocol makes a future provider swap a configuration change, not a rewrite.
- `qwen3-embedding-0.6b` at 1024 dims is small enough to hold the full 41K-verse corpus in memory during any batch operation if needed, and sqlite-vec handles the persistence with no additional service.
- Client-side L2 normalization simplifies downstream math — cosine and inner product are interchangeable.

**Negative:**

- **Endpoint dependency.** Scripvec's ingest and query paths depend on network access to `delphi.tail2a835b.ts.net`. If the endpoint is offline, ingest and live query both fail loud (correct per ADR-001, but inconvenient for offline development). A future ADR may authorize a local fallback model if this friction outweighs its cost.
- **Dim is load-bearing.** The 1024-dim pin is encoded in the sqlite-vec schema. Changing to a different model (even another Qwen variant) with a different dim requires dropping and rebuilding the index. This is the standard trade-off for any vector store and is not specific to this choice.
- **Model is fixed, not chosen.** The endpoint serves Qwen3.5 Embedding 0.6B and only that. The eval harness (per CR-001) measures whether the pipeline — *with this fixed model* — meets the retrieval quality bar. A poor eval result is not resolvable by swapping models on the current endpoint; the response would be to switch endpoints (which means accepting whatever model the new endpoint serves), or to invest in non-model axes of quality (reranking, chunking, hybrid retrieval, apparatus handling).
- **Single-concurrency endpoint.** Ingest cannot parallelize embedding requests. At ~41K verses this is a small cost (seconds to low-minutes per full pass depending on throughput), but it shapes any future batch operations.

## Validation

- **The retrieval package reads base URL, API key, model name, and dim from config/env.** No hardcoded values. Reviewed at creation of the package's config module.
- **Vector-dim mismatch is asserted on every embed call.** Any response whose length does not match the pinned dim raises. Covered by a unit test that mocks a wrong-length response.
- **Re-embed workflow is documented in the retrieval package README.** The workflow: (1) change the config value, (2) run the index rebuild script from `scripts/`, (3) re-run the eval harness. No silent index state is tolerated across model changes.

## Links

- `cr-001_vector_search_mvp.md` — MVP scope; this ADR locks the embedding side of the retrieval pipeline.
- `docs/specs/adrs/001_accepted_no_silent_failures.md` — governs failure handling in the embed client: dim mismatches, oversized inputs, and HTTP errors all raise rather than coerce.
- `docs/specs/adrs/003_accepted_mvp_folder_structure.md` — the embedding client lives inside `packages/retrieval/`; config lives at the repo root or in env.
- `docs/specs/adrs/004_accepted_mvp_tooling_floor.md` — if the MVP ships on the Python path, the embed client uses `sqlite-vec` via the standard Python bindings; config comes from `pyproject.toml`-declared deps and env variables.
- `docs/principles/001_vector_retrieval.md` — the eval-first disposition is why the model choice is treated as falsifiable by the eval harness, not a settled default.

## Conflicts surfaced

None. ADR-001's no-silent-failures posture is incorporated directly into the failure-handling section above; no other accepted ADR, policy, or principle is in tension with this decision.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — locks MVP embedding endpoint, protocol, model, and dim | Jeff Haskin |
