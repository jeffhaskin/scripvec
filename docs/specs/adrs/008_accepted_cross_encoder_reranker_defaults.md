# ADR-008: Cross-encoder reranker operating defaults

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

`cr-003_cross_encoder_reranker.md` (pending) proposes a cross-encoder reranker on top of the RRF-fused hybrid retrieval stack locked by `cr-002_mvp_retrieval_stack.md`. CR-003 specifies the integration shape (flag, output schema additions, candidate models, eval-lift gate) but leaves four *operational policies* under-specified: the configurability posture for quantitative parameters (candidate count K foremost among them), long-document handling, score fusion between the reranker and the first stage, and result thresholding.

Those four policies shape what the reranker *does*, not merely that it exists. Locking them before CR-003 is finalized narrows the CR-003 decision to a single binary — does the configured reranker clear the eval-lift gate — and prevents policy drift introduced later by code review rather than ADR.

**Scope note — what this ADR does and does not lock.** This ADR locks *policies* and *structural decisions* about the reranker: that K is configurable, that long-document aggregation is `max`, that fusion is full replacement, that results are always returned. It does **not** stipulate the numeric value of any tunable parameter. Values for K, chunk window, chunk overlap, the RRF top-N that feeds the reranker, or any other tunable knob live in the project-root config file — not in this ADR, not in any other ADR, and not in any CR's proposed-change text. ADRs stipulating values that ought to be configurable settings are a category error and are rejected at authoring time.

**Decision drivers:**

- **Parameter choices should be falsifiable and replaceable without code changes.** A default buried in a module is a migration event each time it is tuned; a default in a project-root config file is a one-line bump. A value stipulated in an ADR or CR is worse than both — it appears to have architectural weight it does not possess.
- **Chunk aggregation has literature consensus.** MaxP is the established cross-encoder baseline for long-document scoring (Dai & Callan, SIGIR 2019). Deviating from it without measurement is unjustified in an eval-first posture (principle 001).
- **Score fusion also has literature consensus.** Every reference stack — sentence-transformers Retrieve-and-Re-Rank, Cohere Rerank, LlamaIndex, Vespa — ships full replacement of the first-stage order. Weighted blending is reserved for cases where the reranker is weaker than the first stage on a given domain; this is not the expected regime for `bge-reranker-base` on English scripture.
- **Low-score thresholding and reranker-specific eval both depend on data that does not yet exist.** The correct disposition is to ship a conservative default (always return the requested top-k, fly blind on reranker-specific quality) and defer the data-dependent tuning to separate CRs that activate once production logs have accumulated.

## Decision

The cross-encoder reranker introduced by CR-003 operates with the following defaults. Each is binding on CR-003 at acceptance time and on every reranker-affecting change thereafter.

### 1. Candidate count K — configurable at the project root

- **K is configurable.** The number of top-ranked RRF-fused candidates handed to the reranker is exposed in a project-root config file under `[reranker]` → `top_k`. The reranker returns the top-k (user-requested) by `rerank_score` out of those K candidates.
- **The exact filename and format of the config file are left to CR-003 to finalize;** the *location* (project root) and the *key name* (`reranker.top_k`) are what this ADR fixes.
- **Hard-coding K in module code is a code-review-grade rejection.** Reading from the config file is the only sanctioned path.
- **This ADR does not stipulate a value for K.** The initial seed and any subsequent tuning are a config-file concern, not an ADR concern. Likewise for every other quantitative reranker-shaping parameter — the RRF top-N that feeds the reranker (currently referenced as `N = 50` in CR-003's draft), the chunk window size, the chunk overlap. None of those values are fixed by this ADR or by any CR's proposed-change text; they all live in the project-root config file.

### 2. Long-document handling — chunk-then-max-pool (MaxP)

- A candidate whose tokenized length exceeds the reranker's input cap (512 tokens for `bge-reranker-base` and `ms-marco-MiniLM-L-6-v2`) is split into overlapping chunks. Each chunk is scored by the reranker as `(query, chunk_text)`. The document's reranker score is the **maximum** of its chunk scores.
- The aggregation function is **fixed at `max` by this ADR** as a policy. Changing it to anything else (mean, top-k mean, log-sum-exp, sum) requires an ADR amendment. The chunk window size and overlap, being tunable quantitative parameters, are configurable under `[reranker]` → `chunking` in the project-root config file; their values are not fixed by this ADR.
- Most Book of Mormon verses fit well under 512 tokens and skip chunking entirely. Longer D&C sections are the primary chunking surface.
- Rationale: MaxP is the canonical cross-encoder passage-aggregation baseline (Dai & Callan, "Deeper Text Understanding for IR with Contextual Neural Language Modeling," SIGIR 2019; PARADE, arXiv:2008.09093). Its assumption — "a document is relevant if any part of it answers the query" — is a good prior for scripture, where a single verse inside a long section is often what satisfies the query. The BAAI FlagEmbedding docs and model card for `bge-reranker-base` do not prescribe an aggregation function; they inherit the generic cross-encoder convention, which is MaxP.
- Known weakness: MaxP can be noisy when a single out-of-context chunk scores spuriously high on surface overlap. If that failure mode becomes observable via user feedback (CR-005), a follow-up ADR may switch the default to top-k mean. This ADR does not pre-authorize that switch.

### 3. Score fusion — full replacement

- The reranker's score **replaces** the RRF-fused order for the final top-k returned to the caller. No weighted blending of `rerank_score` with `rrf_score`, `bm25_score`, or `dense_score`.
- The per-stage scores (`rrf`, `bm25`, `dense`, `rerank_score`) remain present in the CR-002 query output schema, so a downstream agent may implement its own fusion if it later chooses. The default ordering is pure cross-encoder.
- Rationale: every major reference stack ships pure replacement — sentence-transformers Retrieve-and-Re-Rank, Cohere Rerank, LlamaIndex node postprocessors, Vespa multi-phase ranking. Cross-encoder scores are not calibrated across queries (Cohere's documentation explicitly cautions against cross-query score comparison); weighted blending therefore mixes non-commensurable scalars, which introduces a calibration problem without evidence of uplift on well-trained cross-encoders like `bge-reranker-base`.

### 4. Result threshold — return always, no low-score drop

- The reranker returns the top-k by `rerank_score` regardless of absolute score value. A low-scoring result set is preferred to an empty one when candidates exist.
- Empty result sets remain possible only when the first-stage retrieval returns zero candidates; that case is a `0` exit code with an empty `results` array per ADR-007, not a reranker-introduced error surface.
- A low-score drop policy is **deliberately deferred** to `cr-004_reranker_score_threshold.md` (drafting), which will pick a cutoff from a retroactive analysis of the score distribution once production query logs have accumulated.

### 5. Eval posture — ship flying blind on reranker-specific quality

- CR-002's eval harness (50–75 queries with graded 0/1/2 judgments) covers the retrieval pipeline and is the basis for CR-003's acceptance gate (≥ 3 pts nDCG@10 lift over hybrid). That gate is honored.
- Beyond the CR-003 gate, scripvec ships **without reranker-specific eval visibility**: no bespoke reranker test set, no chunked-MaxP-specific held-out, no calibration study of `rerank_score` per query-bucket.
- This is a conscious trade-off: building a reranker-tuned eval corpus before data exists would slow delivery without producing load-bearing insight. Production query logs and `scripvec feedback` entries are the forward-looking data source.
- The remediation — a retroactive reranker quality analysis against the accumulated logs — is deferred to `cr-005_reranker_retroactive_quality_analysis.md` (drafting).

## Consequences

**Positive:**

- K lives in exactly one place (the project-root config file) and nowhere else. Re-tuning is a one-line change in one file, not a code search, and never an ADR amendment.
- MaxP has canonical precedent; engineer defensibility against "why not mean-pool?" rests on the literature, not improvisation.
- Full replacement matches every reference stack. Agent orchestration code needs only `rerank_score` for ordering, and the per-stage scores remain available for downstream logic that wants them.
- "Return always" keeps the output schema stable across all relevance ranges. An agent consuming the CLI never has to distinguish "no results because threshold" from "no results because retrieval empty" — only the latter is possible.
- The two deferred decisions (threshold, reranker eval) are carried by named CRs (cr-004, cr-005), so the deferral is auditable rather than lost.

**Negative:**

- Whatever value K holds at any given time, a too-small K may leave recall@10 uplift on the table for queries where the top answer sits past the RRF cutoff. Without reranker-specific eval data, the gap is not measurable at rollout. CR-005 is where it eventually gets characterized.
- MaxP is known to be vulnerable to a single spuriously-high chunk on long documents. D&C sections are the most exposed surface. If this becomes observable via user feedback, CR-005 is the container for a MaxP → top-k-mean proposal.
- Full replacement commits the top-k order entirely to the cross-encoder. If `bge-reranker-base` has pockets where it is weaker than RRF (e.g., proper-noun queries dominated by BM25), that weakness surfaces directly as ranking regression rather than being dampened by a blend. CR-003's eval gate is the gate; CR-005 is the observability tail.
- "Flying blind on reranker tuning" is a decision that requires discipline. Contributors and agents must not quietly introduce a score threshold or fusion weight outside of CR-004 / CR-005.

## Validation

- The reranker module in `packages/retrieval/` reads K from the project-root config file. A hard-coded K is rejected at code review.
- MaxP aggregation is a single named function (`aggregate_chunk_scores(scores: list[float]) -> float`) whose body is `return max(scores)`. Unit-tested with representative inputs. Changing its body is an ADR amendment.
- The CLI output schema continues to expose `rerank_score` alongside `rrf`, `bm25`, `dense` per CR-002 and ADR-007, so full replacement is visible to callers and reversible downstream.
- A unit test asserts that for any K candidates and any reranker score distribution, exactly `min(k, len(candidates))` results are returned. No code path drops results for being below a score floor.
- The config file is part of the artifact contract: it is read at reranker init, and its relevant keys are included in the CR-002 `config.json` BLAKE2b hash so that drift between config and index state is refused loudly per ADR-001.

## Links

- `docs/specs/adrs/001_accepted_no_silent_failures.md` — the reranker module inherits the fail-loud posture; config-reading and chunking errors raise rather than coerce.
- `docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md` — the reranker is a separate local model and does not traffic the embedding endpoint; the 8K-token embed cap does not apply to reranker inputs.
- `docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md` — `rerank_score` is an additive JSON field per the agent-first contract.
- `cr-002_mvp_retrieval_stack.md` — query output schema and `config.json` hash this ADR composes with.
- `cr-003_cross_encoder_reranker.md` — the CR whose operational parameters this ADR pre-configures.
- `cr-004_reranker_score_threshold.md` — deferred low-score drop policy (drafting).
- `cr-005_reranker_retroactive_quality_analysis.md` — deferred reranker-specific quality analysis (drafting).
- `docs/principles/001_vector_retrieval.md` — eval-first disposition; this ADR knowingly defers reranker-specific eval to cr-005 rather than blocking on it.

## Research citations

- Dai & Callan, "Deeper Text Understanding for IR with Contextual Neural Language Modeling," SIGIR 2019 — establishes MaxP as the passage-aggregation baseline.
- PARADE: Passage Representation Aggregation for Document Reranking (arXiv:2008.09093) — surveys aggregation strategies and motivates MaxP as the unsupervised default.
- BAAI `bge-reranker-base` model card and FlagEmbedding documentation — silent on aggregation, inherits the generic cross-encoder convention.
- sentence-transformers Retrieve-and-Re-Rank (Reimers / SBERT) — ships pure replacement.
- Cohere Rerank documentation and reranking-best-practices — pure replacement; cross-query score comparison explicitly cautioned against.
- LlamaIndex node postprocessors reference — reranker postprocessors replace node scores by default.
- Vespa cross-encoder multi-phase ranking (Bergum) — replacement at the global phase.

## Conflicts surfaced

- **CR-003's provisional `N = 50`.** Per this ADR's scope note, no ADR or CR should stipulate the value of a tunable parameter. CR-003 is still `pending` and must be updated at acceptance time so its proposed-change text expresses the RRF-top-N that feeds the reranker as "configurable in the project-root config file" — with the initial seed value recorded in that file — rather than stipulating `N = 50` in the CR itself. This ADR does not edit CR-003 directly; the edit happens when CR-003 transitions out of `pending`.
- **CR-002's "CLI flags and environment variables only; no config file at MVP."** This ADR introduces a project-root config file scoped to the reranker. No strict conflict — CR-002's "no config file at MVP" applied to the MVP retrieval stack, and the reranker is post-MVP (per CR-003). The project-root config file is introduced by this ADR for the reranker only; generalizing it to other subsystems is explicitly out of scope here and would require its own CR or ADR.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — locked configurability of K, MaxP chunk aggregation, full-replacement score fusion, return-always threshold, and the fly-blind-on-reranker-tuning posture compensated by cr-004 and cr-005 | Jeff Haskin |
| 2026-04-19 | amended | removed stipulated numeric values (K, chunk window, chunk overlap) from the ADR; clarified that ADRs lock policies, not values, and that the ADR's scope does not extend to any other CR or ADR's stipulated parameter values (including CR-003's `N = 50`) | Jeff Haskin |
