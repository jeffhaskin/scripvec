---
id: 007
title: Multi-verse window retrieval with single-verse display
status: drafting
created: 2026-04-20
updated: 2026-04-20
references:
  - cr-001_vector_search_mvp.md
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-007: Multi-verse window retrieval with single-verse display

## Summary

Embed multi-verse windows on the document side while continuing to *display* single verses to the user. Each window is a small, fixed-size span of consecutive verses (e.g., 3-verse or 5-verse windows). Dense retrieval scores windows; the system then selects the best single verse inside the winning window for display. BM25 is unaffected.

The hypothesis: a window of consecutive verses gives the embedder enough surrounding context to "understand" the passage, which a single verse often lacks. Returning the best verse inside the winning window keeps the user-facing unit unchanged.

## Motivation

CR-001 locks the MVP at verse-level retrieval and verse-level display. Verses average roughly 30 words; that is short for a sentence-embedding model to land semantically rich neighbors. A common pattern in scripture-search systems is to embed a sliding multi-verse window so each vector carries more context, but to surface only the best single verse inside the matched window so the reader-facing unit is unchanged.

This CR is captured as a distant-future idea, deliberately *out of scope* for the MVP per CR-001's verse-level decision. It exists as a placeholder so the idea is not lost and can be picked up after the MVP is shipped and measured.

## Proposed change

### Mechanism (sketch — not yet decided)

1. **Window definition.** Fixed-size sliding windows over consecutive verses inside a chapter (or section, for D&C). Window size is a tunable value (3 verses? 5? per-corpus?) — lives in the config file, not this CR.
2. **Window embedding.** Each window is embedded as one vector via the ADR-005 embed client. Verse text is concatenated with a small separator; windows do not cross chapter / section boundaries.
3. **Window index.** A second `vec0` table (or a column in the existing one) stores window vectors keyed by `(window_id)`, with a sibling `windows` table mapping `window_id → (book, chapter, start_verse, end_verse)`.
4. **Dense retrieval.** Top-k is computed over windows, not verses.
5. **Best-verse selection.** For each winning window, pick the single verse to surface. Open question — sub-options include:
   - Embed each verse inside the window separately at query time and pick the best by similarity.
   - Pick the verse whose surface form most overlaps the query (BM25-style, intra-window).
   - Pick the centermost verse of the window.
   - Always return the entire window.
6. **BM25 unchanged.** Lexical retrieval continues to score verses, not windows.
7. **RRF fusion.** Mixing window-scored dense hits with verse-scored BM25 hits requires deciding the join key (verse_id post-selection? window_id?). Open.

### Why this is non-trivial

- Adds a second indexed unit (windows) on top of verses. Storage roughly doubles.
- Window-size choice interacts with chapter/section boundaries, which are uneven across the corpus.
- Best-verse selection inside a window is itself a retrieval problem with its own quality risks.
- Eval design changes: graded judgments are currently keyed on `verse_id`; if the system returns a window or a window-derived verse, the judgment scheme must be re-validated.

### Toggle and defaults

- A new `--retrieve-on {verse|window}` flag on `scripvec query`. Default is `verse` (the CR-001 MVP behavior).
- Eval harness gains a new mode dimension: window-based dense, window-based hybrid, vs the verse-based baselines from CR-002.
- Ships as default only after measured recall@10 / nDCG@10 lift on the held-out set.

## Open questions

- Window size — fixed across corpus, or per-corpus (BoM vs D&C)?
- Whether windows should overlap and by how much.
- Best-verse selection algorithm (see *Mechanism* item 5).
- Whether window embeddings replace verse embeddings or sit alongside them.
- Eval scheme — judge windows directly, or judge the best-verse-inside-window output?
- Index size and rebuild cost — windowed embedding ~Nx the per-verse cost depending on stride.

## Impact on referenced docs

- **CR-001:** this CR explicitly relaxes CR-001's verse-only retrieval decision. CR-001 stands as the MVP; this CR is the next step beyond it.
- **ADR-005 (embedding endpoint):** unchanged — windows are just longer inputs to the same embed client. The 8K-token cap and dim-mismatch raise apply unchanged.
- **ADR-007 (agent-first CLI):** the new flag and any additive output fields follow the existing schema-change rules.
- **Principle 001 (vector retrieval):** consistent. Eval gates acceptance.

## Decision

Not yet decided. Distant-future idea; parked here so it is not lost. Pick up only after the MVP ships and the eval harness is producing comparable numbers.

## Audit log

- 2026-04-20 — created as `drafting`. Captured at the engineer's request while deciding CR-001 item 2 (retrieval unit) in favor of pure verse-level chunking.
