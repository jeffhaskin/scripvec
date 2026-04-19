# scripvec roadmap

> **For any agent (human or AI) editing this file:** before proposing a change to the roadmap, **cross-reference it against every accepted ADR in `../specs/adrs/`**. If a proposed roadmap entry conflicts with an accepted ADR — in ordering, scope, posture, tooling, or any other way — **stop and seek engineer feedback.** Do not silently resolve the conflict by editing either the roadmap or the ADR. Surface the conflict, name it plainly, and let the engineer decide how to reconcile.

This file plans out scripvec's direction and the order in which systems are to be built. It is narrative and sequential: it names the milestones, systems, or initiatives the project is working toward, and the order they are expected to be tackled.

---

## How to read this file

- The roadmap is **intent**, not commitment. Order can change; individual items can be dropped, reshaped, or resequenced.
- The **accepted** ADRs in `../specs/adrs/` are the fixed points. The roadmap must stay consistent with them.
- Discrete, reviewable work items live as CRs in `../specs/change_requests/`. A roadmap line becomes one or more CRs when it is concrete enough to propose.
- The **vision** in `../specs/vision_tree/000_overall_vision.md` is the long-range aspiration the roadmap serves; it is not itself roadmap content.

## How to edit this file

1. Read every accepted ADR in `../specs/adrs/` first.
2. If the change you have in mind conflicts with an accepted ADR in any way — scope, ordering, posture, tooling, naming — **escalate to the engineer.** Do not edit silently in either direction.
3. If there is no conflict, make the edit and record it in the amendment log at the bottom of this file.
4. When a roadmap line matures into proposable work, open a CR under `../specs/change_requests/drafting/` that cites the roadmap line in its `references` frontmatter.

---

## Current direction

scripvec builds a verse-level semantic retrieval system over Latter-day Saint scripture, starting with the Book of Mormon and the Doctrine and Covenants. The MVP is a pure retrieval stack — query in, ranked verses out — with a disciplined eval harness from day one. Beyond the MVP, the system grows along two axes: (1) adding richer query-time understanding (Q&A, archaic-language expansion) and (2) enlarging the corpus surface (scholarly commentary as multi-vector sources, then the Bible).

Correctness and measurability dominate velocity: every addition must justify itself against the eval harness, not against vibes.

---

## Planned sequence

The order below reflects current intent. Each entry is a direction, not a commitment; each becomes one or more CRs when it is concrete enough to propose.

1. **MVP — verse-level vector search on Book of Mormon + D&C.**
   - CR in flight: `cr-001_vector_search_mvp.md`.
   - Includes corpus ingest, reference normalization, embedding pipeline, vector index, BM25 baseline, eval harness, minimal interface, logging.

2. **Natural-language Q&A on top of retrieval.**
   - Q&A layer that composes retrieval with an answering model. Out of scope for the MVP CR; will be proposed as its own CR once the MVP's retrieval quality is measured.

3. **Webster's 1828 expansion / archaic-language handling.**
   - Query-side expansion for archaic or period-specific vocabulary (e.g., Webster's 1828 dictionary as a query-time rewrite or multi-vector expansion source). Corpus-aware; will require a dedicated eval slice.

4. **Scholarly commentary as multi-vector sources.**
   - Per-verse or per-pericope commentary attached to the retrieval graph as additional vectors or filterable metadata. Depends on the retrieval-unit decision in CR-001 and any apparatus-handling decisions that follow from it.

5. **Bible corpus.**
   - Extend the retrieval stack to cover the Bible. The last corpus in the stated vision, not the first — sequencing is deliberate, so the retrieval approach is proven on the smaller and structurally more consistent LDS-specific canon first.

---

## MVP 0.0 — first cut of real code

> *The documents are done. The rules are set. Starting here, the bytes of this project become code, not prose.*

This is the ordered build plan for the first end-to-end cut of scripvec. It is a walking skeleton: every part is real, nothing is stubbed, and the scope is exactly what is already locked by ADRs 001–008 and CR-002 — nothing more. When this plan is done, `scripvec query "..."` returns ranked verses against a real index built from the real corpus, `scripvec eval run` emits real metrics, and the CR-002 ship criteria either pass or fail loudly per ADR-001.

Execution is linear — each phase depends on the one above it.

1. **Workspace scaffolding.** Fill in `pyproject.toml` for every package under `packages/*` and the app under `apps/scripvec_cli/` with real dependencies (`typer`, `httpx`, `sqlite-vec`, `bm25s`, `numpy`). Confirm `uv sync` resolves at the root. No application code yet.

2. **`packages/reference/`.** Citation parse and canonicalize (`parse_reference`, `canonical`). Leaf package, no in-repo imports. Covers the BoM and D&C reference forms present in `data/raw/bcbooks/`.

3. **`packages/corpus_ingest/`.** Walks `data/raw/bcbooks/{book-of-mormon,doctrine-and-covenants}.json` and emits `VerseRecord(verse_id, ref_canonical, book, chapter, verse, text)`. Uses `reference` for canonical strings. Leaf-plus-one in the dependency graph.

4. **`packages/retrieval/`.** The core. Flat module layout per ADR-002:
   - Single embed client module — synchronous `embed(text) -> list[float]`, env-sourced config, serial only (ADR-006), client-side L2-normalized (ADR-005). This is the only sanctioned entry point to the embedding endpoint.
   - Config-hash manifest — BLAKE2b-128 over the manifest named in CR-002.
   - `build_index()` — ingest → embed serially per verse → insert into `corpus.sqlite` (`verses` table + `vec0 float[1024]`) → build `bm25.bm25s` → write `config.json` → update the `latest` symlink on success.
   - `query()` — load index, BM25S top-50 and dense inner-product top-50, RRF fuse at `k = 60`, return top-k with per-component scores and a latency breakdown.
   - Endpoint-drift and corpus-drift guards (ADR-001).

5. **`packages/eval/`.** `run_eval(queries, judgments, index)` — executes every query through the full query path, computes recall@10, recall@20, nDCG@10, MRR@10 per mode, stratifies recall@10 by tag bucket, emits the metrics object and a failures file at `data/eval/failures_<ts>.jsonl`. Sanity checks per CR-002 run on entry.

6. **`apps/scripvec_cli/`.** Typer entry points for every subcommand in CR-002 (`query`, `index build`, `index list`, `eval run`, `feedback`, `--version`). JSON default output (ADR-007), structured stderr errors, granular exit codes, deterministic ordering, per-command help text with the documented schema and an example. Query and feedback events append to `data/logs/*.jsonl`.

7. **Eval corpus.** Author `data/eval/queries.jsonl` (50-query floor) and `data/eval/judgments.jsonl` (graded 1/2; 0 = absent) spanning the four stratification buckets (`doctrinal`, `narrative`, `phrase-memory`, `proper-noun`), at least 8 queries per bucket.

8. **Build and validate.** Run `scripvec index build --from-scratch`, then `scripvec eval run --queries data/eval/queries.jsonl --judgments data/eval/judgments.jsonl`. Smoke `scripvec query "faith and works" --k 10`. Report each CR-002 ship criterion as pass or fail in the eval output; do not paper over a failure.

---

## Amendment log

Append-only record of roadmap edits. Earlier lines are never rewritten.

| Date | Change | Author |
|------|--------|--------|
| 2026-04-19 | created — initial roadmap capturing MVP through Bible per overall vision | Jeff Haskin |
| 2026-04-20 | added — MVP 0.0 build plan, the first ordered implementation sequence | Jeff Haskin |
