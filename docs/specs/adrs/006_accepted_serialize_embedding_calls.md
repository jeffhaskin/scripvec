# ADR-006: Serialize all embedding-server calls

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

ADR-005 locks the embedding endpoint and model. The upstream embedding server is **single-request**: it cannot serve more than one embedding request at a time. Concurrent calls to it fail, corrupt state, or produce undefined behavior. This is a property of the server, not a preference on scripvec's side.

Given that constraint, any code in scripvec that reaches the embedding endpoint with more than one in-flight request at a time is a bug — not a performance choice with a trade-off. This ADR records the constraint explicitly so that no future component (ingest, eval, query, batch re-embed, background jobs) re-discovers it by causing an incident.

**Decision drivers:**

- The endpoint serves one request at a time. Parallelism at the call site does not yield throughput; it yields failures.
- scripvec must fail loud on any embedding error (per ADR-001). Silent failures from concurrent calls are the worst case — they can produce wrong vectors that silently pass dim checks and corrupt the index.
- There is no operational pressure at MVP scale (~41K verses) to parallelize embedding. Serial ingest completes in minutes; serial queries are sub-second per embed call.
- Codifying the constraint up front is cheap. Retrofitting it after a concurrent pattern has been written is expensive.

## Decision

Every embedding-server call from scripvec is **synchronous and serialized**. At any given moment, at most one embedding request is in flight from scripvec to the endpoint.

**What this means, concretely:**

- **No parallelism.** No `concurrent.futures.ThreadPoolExecutor`, no `multiprocessing.Pool`, no `Promise.all`, no fan-out-then-join.
- **No concurrency.** No `asyncio.gather` across embedding calls, no `await Promise.all`, no spawning of parallel embedding tasks.
- **No asynchronous calls to the embedding server.** The embed function is a blocking synchronous call. Even when the surrounding application uses async for other concerns (HTTP server, UI, I/O), the embedding call is serialized and awaited to completion before any next embedding call begins.
- **No request pipelining.** One request, one response, then the next.
- **No background "pre-embed" worker that races the foreground path.** If a background task embeds text, it holds the serialization discipline with the foreground path — typically via a process-wide mutex or by running in the same serial loop.

This rule applies to **every** caller of the embedding endpoint: ingest, query, eval, scripts, one-off utilities, notebooks, and any future component. There is no fast path that bypasses it.

**Exception — none.** There are no exceptions to this rule, now or anticipated. If a future requirement appears to need parallel embedding (e.g., batch corpus rebuild), the correct response is not an exception here — it is either (a) acceptance of serial throughput, or (b) a new ADR authorizing a different endpoint with different concurrency guarantees.

## Consequences

**Positive:**

- Embedding-server failures stay correlated with individual requests, not with contention. A failure points at the input that caused it, not at a race.
- ADR-001's fail-loud posture stays honest. No ambiguous state from two in-flight requests colliding.
- The ingest pipeline, query path, and eval harness can all treat the embed function as a straightforward blocking call. No task queues, no semaphores, no concurrency primitives to review.
- The code is simpler. There is no "is this the fast path?" branching on concurrency.

**Negative:**

- Ingest throughput is bounded by the endpoint's serial latency. At MVP scale (~41K verses) this is a known, acceptable cost — a full re-embed is a one-time or rare event, not a hot path.
- Future features that would naturally parallelize (e.g., a web UI accepting many concurrent queries) must queue embedding calls through a shared serializer. This is a real design constraint on those features.
- Developers and agents working on scripvec must resist the instinct to add `asyncio.gather` / `ThreadPoolExecutor` patterns around embed calls, even when such patterns are idiomatic in the surrounding language. Reviews must catch this.

## Validation

- **Code review gates every new call site of the embed function.** Any PR that introduces a new embedding call must demonstrate serial invocation. Parallel / async patterns wrapping embed calls are rejected.
- **Lint or import audit for concurrency primitives around embed calls.** `asyncio.gather`, `ThreadPoolExecutor`, `Promise.all`, or equivalents applied to the embed function are a lint-grade rejection. A future linter check may enforce this automatically.
- **Single embed-client module.** All embedding calls go through one module in `packages/retrieval/` (per ADR-003). That module does not expose an async or parallel API surface. If a caller imports anything but the synchronous embed function, it is not using the sanctioned entry point.

## Links

- `docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md` — the endpoint whose single-request constraint this ADR codifies.
- `docs/specs/adrs/001_accepted_no_silent_failures.md` — concurrent calls would produce silent or ambiguous failures; this ADR keeps the fail-loud posture enforceable.
- `docs/specs/adrs/003_accepted_mvp_folder_structure.md` — the embed client lives in `packages/retrieval/` and is the single sanctioned entry point.
- `cr-001_vector_search_mvp.md` — MVP scope, which includes every caller of the embedding endpoint.

## Conflicts surfaced

None. ADR-005 already noted single-concurrency as a property of the endpoint; this ADR turns the note into a binding constraint on all callers.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — forbids parallel / concurrent / async embedding calls | Jeff Haskin |
