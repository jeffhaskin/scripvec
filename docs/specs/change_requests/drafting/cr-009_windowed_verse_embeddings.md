---
id: 009
title: Windowed verse embeddings — embed each verse together with surrounding-verse context
status: drafting
created: 2026-04-20
updated: 2026-04-20
references:
  - cr-001_vector_search_mvp.md
  - cr-007_multiverse_window_retrieval.md
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md
  - docs/principles/001_vector_retrieval.md
---

# CR-009: Windowed verse embeddings — embed each verse together with surrounding-verse context

## Summary

Keep the verse as the atomic retrieval and display unit (per CR-001 item 2), but compute each verse's embedding over a *window* of text: the verse itself plus 1–3 verses of context before and after it. The record stored in the dense index is still keyed by `verse_id` and the surface text returned to the caller is still the verse alone — only the *embedding input* changes. Optional extension: store both an isolated-text embedding and a windowed embedding for every verse, exposed via a query-time flag so the caller (or eval) can compare the two at request time.

## Motivation

CR-001 item 2 fixes the retrieval unit at the verse level. The trade-off recorded there: verses are short (~30 words on average), which often gives a sentence-embedding model too little signal to find good semantic neighbors. CR-007 captures one response to that trade-off — change the retrieval unit to a multi-verse window. This CR captures a different response: keep the retrieval unit at the verse, but enrich each verse's *embedding input* with surrounding context so the embedder has more signal to work with.

The two CRs are deliberately separate because they are structurally different choices:

- **CR-007 — Multi-verse window retrieval.** The unit *retrieved on* changes. There is one record per window, not one per verse. Top-k returns windows; a downstream step picks the best verse inside the winning window for display.
- **CR-009 (this CR) — Windowed verse embeddings.** The unit retrieved on stays the verse (one record per verse, keyed by `verse_id`). What changes is the text fed into the embedder for that record: verse N's embedding is computed over `[verse N-w, …, verse N, …, verse N+w]` for some context width `w`. The display unit and the result-set contract are unchanged from CR-001 item 2.

CR-007 may be the wrong call if it complicates eval (judgments are keyed on `verse_id`) and result-shape contracts. CR-009 is a smaller surgical change — same record schema, same query path, same JSON output — that asks the embedder to see more context per record.

Why this is plausibly worth building:

- The existing eval harness (CR-001 / former-CR-002) directly measures whether windowed embeddings move recall@10 / nDCG@10 / MRR@10 over the isolated-verse baseline. If they do not, the change is rejected on data, not vibes.
- Per-verse record schema, query path, RRF fusion, force-inclusion (ADR-014), and the JSON output contract are all unchanged.
- BM25 is unchanged — it continues to score the verse's own text, not the window. Hybrid retrieval mixes a wider-context dense signal with a verse-precise lexical signal, which is plausibly the best of both.

Why this is non-trivial:

- The embedding input for every verse changes, so every prior index built with isolated-verse embeddings becomes drift-incompatible. The CR-001 endpoint-drift / corpus-drift guards refuse silent crossover.
- Window text crosses verse boundaries inside the same chapter / section, and may or may not be allowed to cross chapter / section boundaries — that is a structural decision this CR has to make.
- The optional dual-embedding mode doubles the dense-index storage and doubles the embedding cost at build time.

## Proposed change

### Mechanism (single-embedding mode)

1. **Window definition.** For each verse N inside its chapter (or section, for D&C), the embedding input is the concatenation of verses `[N - w, …, N, …, N + w]`, where `w` is the configurable context width (recommended initial range: 1–3). Verses outside the window range (when N is near the start or end of the chapter / section) are simply omitted — the window shrinks at the edges rather than padding or wrapping.
2. **Boundary policy.** Windows do **not** cross chapter / section boundaries. A verse near the end of a chapter has a smaller forward window; a verse near the start has a smaller backward window. Cross-boundary spillover is rejected because chapter / section breaks are themselves a meaningful structural signal in scripture.
3. **Concatenation format.** Verses inside the window are joined with a fixed separator (space, newline, or a special token). The separator is an implementation choice that affects embedding quality and lives in `corpus_ingest`; it is not a tunable config value.
4. **Token cap.** The 8K-token cap on the embed client (ADR-005) still applies. A window that exceeds the cap raises (per ADR-005). With `w ≤ 3`, this should never happen in practice on the BoM / D&C corpora; the guard is a safety check, not a load-bearing constraint.
5. **Record schema.** Unchanged from CR-001. One record per verse, keyed by `verse_id`. The window only affects the embedding bytes stored at that record; the surface text and metadata are the verse alone.

### Optional extension — dual-embedding mode

Each verse stores **two** embeddings: the isolated-verse embedding (the CR-001 baseline) and the windowed embedding (this CR). At query time, a `--embedding {isolated|windowed}` flag selects which embedding column the dense top-k searches against.

- Storage: roughly doubles the dense-index size (two `vec0` columns instead of one).
- Build cost: roughly doubles the embed-call count.
- Query cost: unchanged — only one of the two columns is searched per query.
- Eval value: significant — the harness can A/B the two embeddings against the same query set without rebuilding the index.

The dual-embedding extension is the recommended target if the engineer wants to *measure* windowed embeddings against isolated embeddings on the held-out set before committing one or the other as the default.

### Config-hash and drift-guard implications

The embedding input for every verse changes. The CR-001 `config.json` manifest gains:

- `embedding_window_width` — the value of `w`.
- `embedding_window_cross_boundaries` — `false` per the boundary policy above (kept in the manifest so a future relaxation is auditable).
- `embedding_window_separator` — the concatenation separator.
- For dual-embedding mode, a column tag identifying which embedding belongs to which `vec0` column.

Any change to any of these changes the index hash. The CR-001 endpoint-drift guard refuses silent crossover between an index built with windowed embeddings and a runtime configured for isolated embeddings (and vice versa).

### BM25 is unchanged

This CR does not touch the lexical index. BM25 continues to score the verse's own text on its own. The hybrid RRF fusion (per CR-001 / former-CR-002) mixes a wider-context dense signal with a verse-precise lexical signal — which is plausibly a better hybrid than two signals that both see the same text.

### Query path is unchanged (single-embedding mode)

In single-embedding mode, the query path, output schema, force-inclusion semantics (ADR-014), and JSON contract are all unchanged. The dense top-k searches the (windowed) embedding column; everything downstream is as today.

In dual-embedding mode, the only change is the new `--embedding` flag and the manifest tag identifying the two columns.

### Toggle and defaults

- `--embedding {isolated|windowed}` flag on `scripvec query` (dual-embedding mode only).
- Default value (`isolated` vs `windowed`) is **deferred** — it is decided after the eval harness reports recall lift from windowed embeddings.
- The eval harness gains a new mode dimension so `recall@10`, `recall@20`, `nDCG@10`, and `MRR@10` are reported separately for `dense+isolated`, `dense+windowed`, `hybrid+isolated`, and `hybrid+windowed`.

## Open questions

- **Single-embedding or dual-embedding mode for the first cut?** Single is simpler (one column, no flag, no schema change to `--version` output). Dual is more measurable (the eval can A/B without two builds).
- **Window width `w`.** A value, lives in config. Initial seed range 1–3; the eval harness picks the value. Whether `w` should be different for BoM (often narrative, short verses) vs D&C (often dense doctrinal blocks, longer verses) is a per-corpus value question.
- **Symmetric vs asymmetric windows.** Always `w` before and `w` after, or sometimes `w` before and `0` after (e.g., for the first verse of a chapter)? The boundary-shrink policy in *Mechanism* item 2 implicitly chooses asymmetric-at-edges; explicitly confirming this is worth doing.
- **Concatenation separator.** Plain space, newline, special token (e.g., `[SEP]`)? The Qwen3.5 Embedding model card may have a recommendation; otherwise pick by eval.
- **Cross-boundary spillover.** Is the boundary policy ("never cross chapter / section boundaries") the right call? An argument for crossing: continuity at a chapter boundary often matters semantically. An argument against: chapter / section breaks are an authorial signal that should be respected. Decide via eval.
- **Interaction with non-verse-chunk records (ADR-009).** Does the window enrichment apply to non-verse chunks too, or only to verse records? Recommended: only to verses — non-verse chunks are already multi-sentence and have plenty of context.
- **Build cost.** `w = 3` and dual-embedding mode means six neighbor reads per verse plus an extra full-corpus embed pass. At ~41K verses on the MVP corpus this is bounded but not free; the engineer is self-hosted so build-time isn't a ship criterion, but it is a real number worth knowing.

## Impact on referenced docs

- **CR-001:** this CR keeps item 2's verse-atomic decision intact. It modifies only the embedding-input policy that CR-001's build pipeline currently treats as "embed verse text alone." The endpoint-drift / corpus-drift guards in CR-001 absorb the window parameters into the config hash so silent drift is refused.
- **CR-007:** this CR is the *alternative* to CR-007. CR-007 changes the retrieval unit to a window; this CR keeps the unit at the verse and changes only the embedding input. Both should not ship simultaneously — the engineer picks one or the other based on eval. (Both could ship sequentially, with this CR first as the smaller change; CR-007 only if windowed embeddings under-deliver and the engineer wants to try the full retrieval-unit change.)
- **ADR-005 (embedding endpoint):** unchanged — windows are just longer inputs to the same embed client. The 8K-token cap and dim-mismatch raise apply unchanged.
- **ADR-006 (serialize embedding calls):** unchanged. Build pipeline still embeds serially per record; per-record cost goes up because the input is longer, not because there are more records (in single-embedding mode).
- **ADR-014 (force-inclusion):** unchanged. Force-included verses are still verses; the windowed-embedding change does not alter the result-set contract.
- **`docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md`:** the window width, the cross-boundary policy, the separator, and any future tunables introduced here are values that live in the project-root config file.
- **Principle 001 (vector retrieval):** consistent. The eval harness gates acceptance.

## Decision

Not yet decided. Distant-future idea; parked here so it is not lost. Pick up only after the MVP ships and the eval harness is producing comparable numbers — at which point this CR and CR-007 are the two named alternatives for moving the dense recall number, and the choice is made on eval rather than first principles.

## Audit log

- 2026-04-20 — created as `drafting`. Captured at the engineer's request while deciding CR-001 item 9 (windowed presentation rules) in favor of "the result set is the result set, no presentation-layer windowing." This CR documents the *embedding-side* windowing alternative — distinct from CR-007's retrieval-unit windowing — so the idea is preserved for a future eval-driven choice.
