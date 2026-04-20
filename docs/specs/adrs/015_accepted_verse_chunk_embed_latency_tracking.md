# ADR-015: Verse-chunk embedding-call latency is timed and a running average is maintained

## Status

ACCEPTED

## Created

2026-04-20

## Modified

2026-04-20

## Supersession

*Supersedes:* none
*Superseded by:* none

## Date

2026-04-20

## Deciders

Jeff Haskin — engineer, sole decision authority at time of record.

## Context and Decision Drivers

ADR-005 locks the embedding endpoint and ADR-006 locks the serial discipline of the single sanctioned embed client. Both ADRs leave open the question of *what telemetry the embed client carries about itself*. CR-001's logging conventions cover the *query* path (`data/logs/queries.jsonl`) and the *feedback* path (`data/logs/feedback.jsonl`) but say nothing about per-call embed-side timing.

The engineer wants explicit visibility into per-verse-chunk embedding latency: time from initiating the embed request to receiving the embedding back. Knowing this number, and how it drifts over time, is foundational input for capacity planning, endpoint-health monitoring, and any future decision about whether to switch endpoints (per ADR-005's posture — "the response to poor dense performance is not to swap models on the current endpoint, it is either to switch endpoints or to invest in non-model axes of quality"; "when to switch endpoints" is exactly the question this telemetry informs).

The telemetry is **scoped narrowly** to verse-chunk embeddings (one embed call per verse, ~41K calls per full build). It is **not** collected for:

- User-query embeddings — those are part of the query path and already measured end-to-end via CR-001's `data/logs/queries.jsonl` latency breakdown.
- Non-verse-chunk embeddings (ADR-009 sentence-packed chunks of canonical non-verse text) — those have variable input size and would skew a per-call average computed over fixed-shape verse inputs.

Narrow scope is the point. A single, stable, per-verse-chunk number is comparable across builds and across endpoint changes; mixing query-time embeds and variable-size non-verse chunks into the same average destroys that comparability.

**Scope note — what this ADR does and does not lock.** This ADR locks the *policy*: that per-verse-chunk embed-call latency is measured and a running average is maintained, updated on every verse-chunk embed call. It does **not** stipulate the storage format, the file location, the exact persisted shape of the running average, the rolling-window size (if any), or any other tunable. Per `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md`, those values live in the project-root config file and / or are implementation choices in `packages/retrieval/`. The instrumentation surface is fixed by this ADR; the storage representation is not.

**Decision drivers:**

- **Latency drift is the leading indicator of endpoint health.** A jump in per-call latency precedes most observable quality regressions on a self-hosted embedding endpoint. Capturing it cheaply, at the source, is the right hook.
- **The telemetry must live at the embed client** — the only sanctioned entry point per ADR-006. Any other location would either duplicate the timing logic (bug surface) or rely on callers remembering to time the call (omission surface).
- **Scope-to-verse-chunks-only** is what makes the average load-bearing. Mixed-population averages are noise.
- **A running average is sufficient telemetry for the MVP.** Per-call timings can also be persisted (cheap, append-only) for retroactive analysis, but the headline number — "what is the current per-call latency" — must be available without scanning the log.

## Decision

The single sanctioned embed client (per ADR-006) is instrumented as follows. Each clause is binding on the embed-client module in `packages/retrieval/` and on every change to it thereafter.

### 1. What is timed

For every embed call made on behalf of a **verse chunk** during index build, the client measures wall-clock elapsed time between the moment the HTTP request is initiated to the configured endpoint (per ADR-005) and the moment the parsed embedding (post dim-mismatch check, post normalization) is returned to the caller. The timing covers the request, the network round-trip, and the client-side post-processing required to return a normalized vector — not just the network leg.

### 2. What is excluded

- **User-query embeddings** are not timed by this telemetry. The query path already records its own latency breakdown (`bm25`, `dense`, `fuse`, `total`) per CR-001's `data/logs/queries.jsonl` schema; that surface is the right one for query-side measurement.
- **Non-verse-chunk embeddings** (ADR-009 sentence-packed chunks) are not timed by this telemetry. Their input size is variable, which would distort a fixed-shape per-call average.
- **Re-embed calls during eval** that re-process verses are timed if and only if they are still verse-chunk embed calls (i.e., the same shape as a build-time per-verse embed). Eval-side dense re-encoding of a query string is not a verse-chunk embed and is excluded.

The exclusion is enforced **at the embed-client surface**: the embed client receives a marker (or has two narrow public entry points — one for verse-chunk embeds, one for everything else) that determines whether the timing is recorded. The exact mechanism is an implementation choice; the contract is that the recorded population contains exactly verse-chunk embed calls and nothing else.

### 3. Where the timing data lives

Each timing is appended to an on-disk store under the project's logs directory, alongside the existing `queries.jsonl` and `feedback.jsonl` per CR-001's logging conventions. The exact filename and on-disk format are implementation choices, not stipulated here. The append discipline matches the existing logging contract: append-only, schema-versioned, no in-place rewrites.

A separate, **constantly-updated running average** is maintained. The average is updated on every verse-chunk embed call — incrementally (not by re-scanning the log on each update). The on-disk representation of the running average — whether it is a small JSON file holding `(count, sum, mean)` tuples, a row in a SQLite scratch table, or another shape — is an implementation choice, not stipulated here. The contract is:

- The running average reflects every verse-chunk embed call ever made under the active configuration. (See clause 4 for what "active configuration" means.)
- Reading the current average is a single-file (or single-row) read, not a log-scan.
- Updating the running average on each call is constant-time.
- The running average survives process restart. A crash mid-build does not corrupt the average; partial state is repairable from the append-only log.

### 4. Configuration scoping

The running average is **per active embed configuration**: the `(endpoint URL, model identifier, dim, normalization flag)` tuple from ADR-005. A change to any of these resets the running average — the old number is no longer comparable. The previous configuration's average is not deleted; it is retained for audit but is not the live value.

The exact representation of "per-configuration" — whether it is a hash-keyed file, a stored field on the running-average state, or another mechanism — is an implementation choice. The contract is that latency numbers from before an endpoint or model change are not silently averaged in with numbers from after.

### 5. Failure handling (ADR-001 application)

- A failed embed call (HTTP error, dim mismatch, oversize input — all of which raise per ADR-005) **does not contribute** to the timing or the average. Only successful calls are timed and recorded.
- A failure to write the timing record or update the running average **does not** raise — the embed call itself succeeded and the caller's contract is honored. Telemetry-write failures are themselves logged at warn level and the embed client continues. This is one of the rare carve-outs from ADR-001's fail-loud posture, justified because telemetry failure must not silently degrade build success: an embed that succeeded and a verse that was indexed correctly should not be retried because a log file was momentarily unwritable.
- A corrupt running-average file at startup raises per ADR-001 — corruption of state is a real bug, not a silently-recoverable one. The append-only log is the recovery path: re-derive the running average from the log if needed, then continue.

### 6. Visibility

The current running average is exposed via a CLI surface so the engineer (or an agent) can read it without poking at files. The exact subcommand placement — a `scripvec stats embed` command, a field on `scripvec --version`, a flag on `scripvec index list` — is an implementation choice. The contract is that the average is queryable from the CLI per ADR-007's agent-first contract (JSON output, structured schema).

## Consequences

**Positive:**

- A single, stable per-verse-chunk latency number is always available, comparable across builds and across endpoint configurations.
- Endpoint drift surfaces in this number before it surfaces in retrieval quality.
- The telemetry lives at the single sanctioned embed-client surface, so adding it is a one-file change and there is no possibility of a caller bypassing the instrumentation.
- The narrow scope (verse chunks only) means the average is load-bearing rather than a mixed-population mean of noise.
- The append-only log keeps full per-call history available for retroactive analysis without growing the running-average update path beyond constant time.

**Negative:**

- The embed client carries a small, persistent side effect on every verse-chunk call. The cost is bounded (one stat update, one append) but it is not nil.
- The configuration-scoping rule (clause 4) means an endpoint or model change resets the running average. Comparing numbers across a model change requires reading the prior-configuration's retained average separately, not just reading "the" average.
- The carve-out in clause 5 (telemetry-write failure does not raise) is a deliberate departure from ADR-001's fail-loud posture and must be justified each time it is read; the justification is recorded inline so the discipline is auditable.
- Eval-side or future-CR-introduced embed paths must explicitly opt in or out of the verse-chunk classification. A new caller that forgets to set the marker would either pollute the verse-chunk average (if defaulted in) or be silently excluded from telemetry (if defaulted out). The default direction is an implementation choice; whichever it is, it must be visible in code review.

## Validation

- A unit test asserts that a successful verse-chunk embed call increments the running-average count and updates the mean.
- A unit test asserts that a successful user-query embed call does **not** update the verse-chunk running average.
- A unit test asserts that a successful non-verse-chunk embed call (ADR-009 chunk) does not update the verse-chunk running average.
- A unit test asserts that a failed embed call (mocked HTTP error or wrong-length response) does not increment the count and does not update the mean.
- A unit test asserts that a configuration change (different endpoint URL, model identifier, dim, or normalization flag) starts a new running average, leaving the prior-configuration average retained but not live.
- A unit test asserts that the running average survives process restart against a fixture timing log.
- The CLI surface that exposes the running average has a contract test under `apps/scripvec_cli/` per ADR-007: JSON-shape assertion, structured-error assertion on a forced failure.

## Links

- `docs/specs/adrs/001_accepted_no_silent_failures.md` — fail-loud posture; this ADR carves out a single, justified exception in clause 5 (telemetry-write failures do not raise).
- `docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md` — the endpoint and model identity that scopes the running average per clause 4.
- `docs/specs/adrs/006_accepted_serialize_embedding_calls.md` — the single sanctioned embed-client surface; this ADR's instrumentation lives at exactly that surface.
- `docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md` — the running average is exposed via the CLI per the agent-first contract.
- `docs/specs/adrs/009_accepted_non_verse_text_chunking_policy.md` — non-verse chunks are explicitly excluded from this telemetry per clause 2.
- `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md` — storage format, file location, and any rolling-window size are values, not stipulated here.
- `cr-001_vector_search_mvp.md` — the embed client and logging conventions this ADR composes with. CR-001 is bound by this ADR at its embed-client implementation surface; no CR-001 amendment is required.

## Conflicts surfaced

- **None vs ADRs 001–014.** This ADR is purely additive on the embed-client surface; ADRs 005 and 006 are unmodified, and the carve-out from ADR-001 in clause 5 is named and justified inline.
- **CR-001 (staged) is unmodified by this ADR.** The instrumentation requirement falls on the embed-client implementation that CR-001's System 4 component 4.1 will produce. Per the established pattern (ADR-008 bound CR-003 at acceptance time without rewriting CR-003), the staged CR-001 inherits this ADR's binding without an audit-log entry of its own; the binding is auditable via this ADR's existence.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — locked verse-chunk-only timing of every successful embed call, a per-configuration running average updated incrementally on each call, append-only log of per-call timings, CLI exposure of the live average, and the single carve-out from ADR-001 fail-loud for telemetry-write failure | Jeff Haskin |
