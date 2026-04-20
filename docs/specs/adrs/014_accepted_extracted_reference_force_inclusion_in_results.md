# ADR-014: Extracted references force-include their resolved verses in the result set alongside organic results

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

ADR-013 locks free-text query reference extraction: every query is scanned for embedded canonical references and a flat ordered set of resolved verses is produced. What happens with that set is open. Three plausible behaviors:

- **Replace organic results with extracted hits.** Discards the retrieval signal the user is also implicitly asking for ("about faith"). Rejected.
- **Filter organic results to only those that match the extracted references.** Useful for "find me hits that mention this verse", but inverts the normal retrieval semantics. Rejected for MVP.
- **Force-include extracted hits alongside the organic top-k, deduplicated.** Surfaces the verse the user named *and* the verses the retriever thinks are most relevant. Selected.

This ADR is scoped to the merge behavior alone so it can be superseded in isolation if the engineer later wants to change the extracted-set semantics (e.g., to a filter, a separate channel in the response, or a query-rewrite signal).

**Decision drivers:**

- Force-inclusion preserves the organic retrieval signal, so the eval harness continues to measure organic recall@k uncontaminated.
- Adding extracted hits is a post-retrieval merge step; it does not perturb the dense + BM25 + RRF path.
- Deduplication keeps the result set clean when an extracted reference is also organically retrieved.

## Decision

For every reference (or range) extracted per ADR-013, the resolved verses are **force-included** in the result set returned to the caller, with the following properties:

- **Alongside, not in place of.** The organic dense + BM25 + RRF top-k runs as it would have without extraction; the force-included set is added to the result.
- **Deduplicated.** If a force-included verse also appears in the organic top-k, the result contains exactly one copy of that verse, and that copy carries both the force-inclusion marker and the organic per-component scores.
- **Marked recoverably.** Each result carries a marker (e.g., `forced: true|false`) that the JSON output exposes per ADR-007's agent-first contract, so the caller can distinguish force-included hits from organically retrieved hits.
- **Does not bypass retrieval.** Organic retrieval still runs in full; force-inclusion is a post-retrieval merge step, not a short-circuit on the embedding endpoint or the BM25 index. This preserves the eval signal and keeps the query log meaningful.

The following are **implementation choices** in the query path, not fixed by this ADR. Sensible defaults are recommended; revising them does not require an ADR amendment as long as properties (a)–(d) above hold:

- The position of force-included verses in the result list (recommended default: at the top, in the order they appeared in the query).
- Whether the result count is exactly `k` (force-included verses count toward `k`, organic results fill the remainder) or `k + N_extracted` (force-included verses are additive). Recommended default: additive, so a request for `k=10` with two extracted references returns up to 12 results.
- The per-stage score fields exposed for force-included verses that did not come through organic retrieval. Recommended default: `null` for `bm25`, `dense`, `rrf`; force-inclusion is its own scoring class.

Per-result rank ordering is deterministic per ADR-007 — when multiple force-included verses share the same position class, they are ordered by their appearance order in the query; ties between organic results break by `verse_id` ascending as established in CR-001.

## Consequences

**Positive:**

- Force-inclusion gives reference-driven queries a useful path without introducing a second retrieval mode.
- The organic retrieval is undisturbed; the eval harness can still measure organic recall@k cleanly.
- Deduplication keeps the JSON contract clean: each verse appears at most once in any single response.
- The marker on each result lets a downstream agent treat force-included hits differently if it chooses (e.g., display them in a separate UI panel, or weight them differently in a downstream ranking step).

**Negative:**

- A query like `"Alma 32:21"` (just a reference, no surrounding words) now has two paths to the same result: organic retrieval will likely find Alma 32:21 anyway, and extraction will force-include it. Per dedupe, it appears once in the result with both markers. This is fine but worth being explicit about; consumers must read the marker to understand the provenance.
- Cross-book ranges inside a free-text query can balloon the force-included set. The range-expansion size cap (config-resident per ADR-011) bounds the worst case but the cost of force-including a 200-verse range is real.
- The result count contract becomes "up to `k + N_extracted`" by default rather than exactly `k`. Callers that strictly require `k` exactly must filter the result themselves or pass an extraction-disabling flag (a future-CR concern, not introduced here).

## Validation

- Unit tests cover: a query whose extracted reference is also organically retrieved (one result, both markers); a query whose extracted reference is not organically retrieved (extra result, force-inclusion marker only); a query with multiple extracted references where some overlap with organic results and some don't; a query with no extraction (no force-inclusion, organic-only result set unchanged from baseline); a query with a range whose resolved verses partially overlap organic results.
- The JSON output schema test (the ADR-007 contract test under `apps/scripvec_cli/`) is extended to assert the `forced` marker is present on every result and is `true` exactly when the verse came (or also came) from extraction.
- Query-log entries record both the extracted reference set and the final force-included verse-id set, so retroactive analysis can answer "did extraction add value to this query?"

## Links

- `docs/specs/adrs/013_accepted_free_text_query_reference_extraction.md` — produces the extracted set this ADR consumes.
- `docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md` — additive `forced` marker is consistent with the agent contract's evolution rules.
- `docs/specs/adrs/001_accepted_no_silent_failures.md` — extraction failures raise upstream; this ADR's merge step does not silently swallow anything.
- `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md` — no values stipulated here; result-count contract default is a recommendation, not a fixed value.
- `cr-001_vector_search_mvp.md` — item 4, closed by this ADR (final segment).
- `docs/principles/001_vector_retrieval.md` — eval-first; organic recall remains measurable because force-inclusion is a post-retrieval merge.

## Conflicts surfaced

- **None vs ADRs 001–013.** No conflicts.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — locked force-inclusion semantics for extracted references (alongside, deduplicated, marked, organic retrieval undisturbed); recorded recommended defaults for position, count contract, and per-stage scores as revisable implementation choices | Jeff Haskin |
