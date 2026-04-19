# ADR-001: Fail loud — no silent fallbacks, no graceful degradation

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

scripvec is a greenfield retrieval system built by a solo developer, initially with no end-users other than the developer. In that regime, the cost of a loud failure is *"the engineer sees an error and fixes it."* The cost of a silent fallback is *"retrieval quality rots undetected, the eval harness lies, and the system ships a regression that nobody notices for weeks."*

Given that asymmetry, loud failures are strictly preferable to silent degradation. Most defensive-programming patterns from larger systems — catching exceptions and returning defaults, substituting safe values, swallowing errors to keep the system running — actively *hide* the failures that matter most. For a retrieval system in particular, the failures that matter most are the ones that produce *plausible-looking* output with wrong semantics. Those are invisible to anyone who isn't actively evaluating them.

**Decision drivers:**

- The eval harness is the system's conscience. A silently swallowed error during corpus ingest, reference normalization, or embedding produces a corpus that *looks* indexed but returns wrong results. Principle 001 (`docs/principles/001_vector_retrieval.md`) is explicit that unmeasured retrieval quality is the failure mode to fear.
- The noisiest surfaces — embedding API calls, vector index builds, citation parsing, BM25 tokenization, corpus-format edge cases — are exactly the surfaces that can produce "successful" output with wrong data if an exception is swallowed.
- With one user (the developer), there is no operational cost to being noisy. Nobody is paged unnecessarily by loud failures at this scale.
- Retrofitting strict error discipline into a codebase full of catch-and-default patterns is expensive. Establishing the posture up front is cheap.

*Technical story:* this principle is established at project inception and is referenced as a foundational constraint throughout the architecture specs.

## Decision

When an invariant is violated, the system fails with a clear, immediate error rather than silently degrading. This applies to every component in every package and app.

**What this means:**

- Unknown or unexpected inputs raise errors, not fall back to defaults.
- Exception handlers do not swallow errors and return substitute values.
- Type mismatches, schema mismatches, format errors, and missing required data are detected and raised at the point of occurrence.
- Fallbacks, when they exist, are **intentional feature sets** — designed, specified, implemented, and tested as first-class behavior. In practice that means most fallbacks are deferred to the distant future unless the engineer decides otherwise.

**Exception 1 — System boundaries.** At explicit system boundaries (the CLI interface exposed by `apps/scripvec_cli`, any HTTP or notebook interface added later, the eval harness's report output), errors are caught and translated into structured error responses for the caller. This is not a fallback — it is error reporting. The error is still surfaced; it is formatted for the transport. Internal components between boundaries never catch and swallow.

**Exception 2 — Designed retry/dedupe, scoped and explicit.** If, in the future, a designed retry or dedupe mechanism is introduced (e.g., retrying a transient embedding-API error with exponential backoff, deduping corpus-ingest writes by source-document hash), it must be authored as a first-class feature in a specific module, referenced in that module's README, and named explicitly here via an amendment to this ADR. No currently-scoped code qualifies for this exception.

**The test:** if removing an exception handler would cause a crash that reveals a real bug, the handler should not exist. If a default value masks a configuration error, the default should not exist. If a comment like *"just in case X happens"* appears without citing this ADR and naming explicit engineer authorization for that specific fallback, the code is wrong.

## Consequences

**Positive:**

- Failures are detected at the point of occurrence, not hours later through degraded output.
- Every error produces a clear signal — a crash, an error log, a CLI exit code — that can be surfaced immediately during development and in eval runs.
- The eval harness stays honest. A corpus ingest step that fails to normalize a citation fails the ingest, rather than being silently dropped and corrupting the indexed corpus.
- Debugging is straightforward. Errors point to the source, not to a downstream symptom of an upstream swallowed failure.
- Retrieval quality regressions surface as crashes or eval deltas, not as plausible-but-wrong results.

**Negative:**

- Less resilient to transient errors — a single bad verse record crashes the ingest run rather than guessing at the record's shape.
- Development requires more discipline. Every new component must consider every error path, and *"catch and continue"* is not an option.
- Error rates become meaningful. The developer must be prepared for error spikes during implementation; each spike is a previously-hidden failure surfacing.
- Some convenient "best effort" patterns are prohibited. For example, a partial embedding pass (some verses embedded, others skipped) is not allowed without an explicit authorized design for that partial outcome.

## Validation

- **Audit all `try/except` (Python) and `catch` (TypeScript) blocks during implementation and in code review.** Each must either translate an error at a boundary (Exception 1), be an explicitly authorized designed retry/dedupe (Exception 2, currently empty), or be removed.
- **Linters flag broad catch-alls.** `except Exception` / bare `except:` in Python and broad `catch (_)` in TypeScript are caught in CI once CI exists.

## Links

- `docs/principles/001_vector_retrieval.md` — the eval-first disposition underwrites this ADR; a silent fallback in the retrieval path invalidates every eval number.
- `cr-001_vector_search_mvp.md` — MVP scope; this ADR governs every component listed in that CR.

## Conflicts surfaced

None. No existing spec, policy, principle, or change request conflicts with this ADR.

## Amendment Log

*Add an entry for every change made after Locked status, or when unlocking back to Proposed.*

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — adapted from Enlighten ADR-001 | Jeff Haskin |
