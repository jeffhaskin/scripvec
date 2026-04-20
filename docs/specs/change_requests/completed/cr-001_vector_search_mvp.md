# 001 — Vector Search MVP

## Status
Completed.

## Intent
Build the MVP: a standard vector search over the Book of Mormon and the Doctrine and Covenants at verse-level granularity. A user submits a natural-language query; the system returns the most semantically relevant verses. Nothing more.

## Scope

**In scope:**
- Corpus ingestion for BoM and D&C, verse-level units.
- Text normalization and reference handling.
- Embedding pipeline (model, chunking, storage).
- Vector index / persistence.
- Retrieval query path.
- Baseline (BM25) and evaluation harness.
- A minimal interface to issue queries and read results.
- Logging sufficient to support later quality improvement.

**Explicitly out of scope** (will be addressed in their own future change requests per the overall vision roadmap):
- Natural-language Q&A on top of retrieval.
- Webster's 1828 expansion / archaic-language handling / multi-vector query expansion.
- Scholarly commentary attached to verses as additional vectors.
- The Bible corpus.

## Advisors

Two personas are available in the persona database for this system. The engineer owns every decision in this CR; advisors are optional and may be channeled via `/personas` at the engineer's discretion.

- **The Retrieval Engineer** — `/data/projects/flywheel/personas/retrieval-engineer.md`
  - Owns: embedding model selection, vector store / ANN index choice, index configuration, baseline eval harness, hybrid-retrieval decision, reranker layering, retrieval latency budgets, instrumentation.
  - Disposition: eval-first; refuses to ship without a held-out query set and a recall@k number.

- **The Structural Corpus Retriever** — `/data/projects/flywheel/personas/structural-corpus-retriever.md`
  - Owns: retrieval unit (is verse the right unit, or is pericope better?), apparatus handling (section headings, chapter summaries, cross-references), reference normalization on query and document sides, windowed-presentation rules.
  - Disposition: treats source structure as a first-class retrieval variable; refuses to accept user-stated chunking units without interrogation.

**Recommended advisor sequence (if used):** Retrieval Engineer first — their inputs anchor the stack choice. Structural Corpus Retriever immediately after, to challenge corpus-structure defaults before they calcify into code.

## Key decisions

1. **Corpus source and ingest format.** Where does the canonical BoM + D&C text come from? What metadata survives? — *Structural Corpus Retriever leads; Retrieval Engineer informs.*

   **Decision (engineer-approved):** Use [`bcbooks/scriptures-json`](https://github.com/bcbooks/scriptures-json) as the canonical MVP source. Pull `book-of-mormon.json` (v4) and `doctrine-and-covenants.json` (v5, refreshed 2025-05-08). Hierarchical JSON, verse-level, public domain, ~3.6 MB total.

   **What this source provides out of the box:**
   - **BoM:** title page; Testimony of the Three Witnesses; Testimony of the Eight Witnesses; full volume → book → chapter → verse structure; original pre-1921 book-level headings; the 15 in-text chapter headings that are part of the 1830 narrative itself (Mosiah 9 & 23; Alma 5, 7, 9, 17, 21, 36, 38, 39, 45; Helaman 7 & 13; 3 Nephi 11; Mormon). Stable reference strings (e.g., `"1 Nephi 3:7"`) and `lds_slug` metadata mapping to Gospel Library URLs.
   - **D&C:** section → verse structure for all 138 sections, with `signature` field where applicable.

   **What this source excludes (by design — copyright on 1981/2013 edition apparatus):**
   - Modern italicized chapter summaries (BoM) and modern section headings / date-place notes (D&C).
   - BoM Introduction, D&C Explanatory Introduction, Brief Explanation appendix.
   - Official Declaration 1 and Official Declaration 2.
   - Footnotes, cross-references, Bible Dictionary, Topical Guide.
   - Joseph Smith's Testimony.

   **Disposition of excluded content:** Out of scope for MVP. If needed later, it can be sourced from pre-1921 public-domain editions (Project Gutenberg, Internet Archive) or added manually. Not blocking the MVP.

   **Backup source (not used for MVP):** [`beandog/lds-scriptures`](https://github.com/beandog/lds-scriptures) — SQLite + multi-format exports of the same text lineage. Staler (last release 2020) and lacks the front matter bcbooks adds back. Retained as a fallback only.

2. **Retrieval unit.** Verse-level is stated. Is it the *retrieval* unit or only the *display* unit? Ablate at least one alternative (e.g., pericope). — *Structural Corpus Retriever.*

   **Decision (engineer-approved):** A verse is the atomic unit. Verse = chunk size = retrieval unit = display unit. Whatever verses are returned by retrieval are the verses displayed to the user; no pericope grouping, no windowed display. Pericope-style chunking is rejected for the MVP because the only practical ways to define pericope boundaries are (a) AI-reading the corpus end-to-end, which is impractical, or (b) proprietary technology the engineer is not free to use here. Multi-verse-window retrieval with single-verse display is captured as a distant-future change request (`cr-007_multiverse_window_retrieval.md`) and is explicitly out of scope for the MVP.
3. **Apparatus handling.** What non-body text exists (chapter/section headings, verse reference markers, D&C historical context blocks, italicized editorial words)? For each: in the embedding, as separate vectors, as filterable metadata, or excluded? — *Structural Corpus Retriever.*

   **Decision (engineer-approved):** Anything in the corpus that is not a verse is chunked by the policy locked in `docs/specs/adrs/009_accepted_non_verse_text_chunking_policy.md`: greedy packing of consecutive sentences into chunks each at or below a configurable per-chunk token cap, with a configurable no-split floor (any non-verse item whose total token count is at or below the floor is emitted whole as one chunk regardless of the cap, so an item only marginally over the cap does not produce a pathological tail chunk). The `floor > cap` invariant is asserted at config load. Each chunk is indexed as its own record alongside the verse records — same dense vector table, same BM25 corpus — and is retrieved on equal footing with verses. This rule applies uniformly to every non-verse text the source provides: BoM title page, Testimony of the Three Witnesses, Testimony of the Eight Witnesses, pre-1921 book-level headings, the 15 in-text 1830 chapter headings (Mosiah 9 & 23; Alma 5, 7, 9, 17, 21, 36, 38, 39, 45; Helaman 7 & 13; 3 Nephi 11; Mormon), and the D&C `signature` field. The cap and the floor are tunable values that live in the project-root config file (per `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md`); the sentence-splitter, token counter (which must agree with the ADR-005 embed client's counter per ADR-009), chunk-id scheme, and chunk-record schema are implementation choices that live in the `corpus_ingest` package, not in this CR.
4. **Reference normalization.** Canonical citation handling on query and document sides ("Alma 32:21", "D&C 88:118", abbreviations, alternate forms). Implemented as a library, not a regex. — *Structural Corpus Retriever.*

   **Decision (engineer-approved):** The reference subsystem is governed by five separately-superseded ADRs, one per discrete decision so any single one can be revised in isolation:

   - `docs/specs/adrs/010_accepted_strict_canonical_reference_parser.md` — single-citation grammar is strict canonical only. No abbreviations, no case variants, no alternative punctuation, no fuzzy matching.
   - `docs/specs/adrs/011_accepted_reference_range_syntax_full_endpoints.md` — range form is `<canonical_ref> - <canonical_ref>` (full reference on both sides of an ASCII hyphen with surrounding spaces). Cross-chapter and cross-book ranges are syntactically valid; reversed-order ranges raise. Shorthand ranges like `Alma 32:21-23` are rejected.
   - `docs/specs/adrs/012_accepted_reference_list_syntax_semicolon_separated.md` — list separator is `;`. Each item is a single ref or a range; nested lists are not representable; valid duplicates are silently deduped to a flat ordered set.
   - `docs/specs/adrs/013_accepted_free_text_query_reference_extraction.md` — every query is scanned for embedded references using the same canonical grammar (single-ref + range, but not list — list items inside free text are extracted independently). A query with no grammatical candidate goes through unchanged; an extracted candidate that parses but does not resolve to a real verse raises per ADR-001.
   - `docs/specs/adrs/014_accepted_extracted_reference_force_inclusion_in_results.md` — extracted references resolve to verses that are force-included in the result set alongside the organic dense + BM25 + RRF top-k, deduplicated, marked recoverably in the JSON output. Organic retrieval still runs in full; force-inclusion is a post-retrieval merge step, not a short-circuit.

   Fuzzy / abbreviation-tolerant matching is captured as a future relaxation path: `cr-008_fuzzy_book_name_matching.md` (drafting). The split-ADR structure was chosen specifically so that future CR can supersede ADR-010 alone without disturbing the range, list, extraction, or force-inclusion decisions.
5. **Embedding model.** Model choice, version pinned, cost/latency profile. Measure on this corpus, not just public leaderboards. — *Retrieval Engineer.*
6. **Vector store and index.** sqlite-vec vs. LanceDB vs. Chroma vs. pgvector etc. At MVP scale (~41K verses total across both corpora), this is small. — *Retrieval Engineer.*
7. **Baseline and eval harness.** BM25 baseline implemented first. A held-out query set of ~20–50 representative questions with graded relevance. Recall@k and nDCG reported. — *Retrieval Engineer leads; Structural Corpus Retriever contributes query-set design, since "what counts as a relevant hit" is corpus-aware.*
8. **Hybrid retrieval decision.** Pure dense vs. BM25 + dense fusion. Measure the delta. — *Retrieval Engineer.*
9. **Windowed presentation rules.** When is a single verse sufficient in the result? When should surrounding verses accompany it? Corpus-specific. — *Structural Corpus Retriever.*

   **Decision (engineer-approved):** No presentation-layer windowing. The result set is exactly the verses returned by retrieval (dense + BM25 + RRF) plus the verses force-included by extracted references per `docs/specs/adrs/014_accepted_extracted_reference_force_inclusion_in_results.md` — and nothing else. No automatic surfacing of surrounding verses; no per-corpus "verse vs windowed" display rules; no context expansion in the JSON output. A user who wants context can issue a follow-up query (e.g., a range per ADR-011, or an explicit reference list per ADR-012). The verse-atomic decision in item 2 is honored exactly: what is retrieved is what is displayed. The orthogonal idea of windowing on the *embedding side* — keeping the verse as the atomic record but enriching each verse's embedding input with surrounding-verse context, optionally as a dual-embedding (isolated + windowed) with a query-time flag — is captured as a distant-future change request: `cr-009_windowed_verse_embeddings.md` (drafting). Note this is structurally different from `cr-007_multiverse_window_retrieval.md`, which changes the retrieval unit itself; CR-009 keeps the verse as the unit.
10. **Interface surface.** CLI, HTTP API, or notebook? MVP chooses one. — *Open; not strongly persona-owned.*
11. **Rebuild and persistence story.** How is the index rebuilt when the embedding model changes? Versioning of artifacts. — *Retrieval Engineer.*
12. **Logging and feedback hook.** What's captured per query (query text, top-k, latency, any relevance signal) to support later quality improvement? — *Retrieval Engineer.*

## Success criteria
- A user can submit a natural-language query and receive top-k relevant verses from the BoM + D&C corpus.
- Retrieval quality is measured against a held-out query set. Recall@k and a BM25 baseline comparison are documented and checked in.
- Every key decision above has an explicit decision record in this CR. If an advisor was consulted, their position is cited.
- The retrieval layer is thin and legible — readable in one sitting.
- Configuration (embedding model version, chunk unit, index params, distance metric) is explicit and version-controlled.

## Open questions
- Is there prior-art LDS scripture search to study for a baseline comparison of result quality?
- Target MVP eval query set size: 20 queries is the floor; is 50 a reasonable aim?

## Next step
Work through the remaining Key decisions and record an engineer-approved decision under each. Move this CR from Draft to In Progress once Key decisions are answered or scoped to sub-CRs. Advisors may be channeled via `/personas` at the engineer's discretion.
---
id: 002
title: MVP retrieval stack and architecture
status: accepted
created: 2026-04-19
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/002_accepted_no_role_splitting_in_packages.md
  - docs/specs/adrs/003_accepted_mvp_folder_structure.md
  - docs/specs/adrs/004_accepted_mvp_tooling_floor.md
  - docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md
  - docs/specs/adrs/006_accepted_serialize_embedding_calls.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-002: MVP retrieval stack and architecture

## Summary

Lock the tech stack, libraries, index shape, CLI surface, persistence scheme, logging, evaluation harness, and ship criteria for the scripvec MVP vector search over the Book of Mormon and Doctrine and Covenants. Picks Python, `uv` workspaces (ADR-004 Python recipe), `sqlite-vec` as the vector store (per ADR-005), `BM25S` as the lexical index, RRF hybrid fusion, and a Typer-backed agent-first CLI (per ADR-007). Commits to a 50-query graded held-out eval set reporting recall@10, recall@20, nDCG@10, and MRR@10.

## Motivation

ADR-004 pre-approved a conditional tooling floor but deferred the stack pick to a CR. ADR-003 locked the folder shape around a set of bounded contexts whose internals were not yet specified. ADRs 005–007 lock the embedding endpoint, the serial-embedding constraint, and the agent-first CLI surface. The retrieval-side key decisions above (items 5, 6, 7, 8, 10, 11, 12) were open. This block closes those, records the concrete libraries and configuration, and defines the ship criteria that must be met before the MVP is called done.

The Retrieval Engineer persona was channeled on 2026-04-19; the engineer reviewed the resulting proposal and approved it with the exceptions noted in the Decision section.

## Proposed change

### Stack

- **Language:** Python 3.12.
- **Workspace manager:** `uv` (per ADR-004 Python recipe).
- **One `pyproject.toml` per package and per app;** root `pyproject.toml` declares the workspace and shared tool config.
- **Root-level `ruff` and `mypy`,** per ADR-004.

### Embedding pipeline

The embedding endpoint, model, protocol, dim, normalization, and serialization discipline are locked by ADR-005 and ADR-006 and are not re-decided here. This CR only adds the integration-shape decisions those ADRs leave open:

- **Single embed client module** inside `packages/retrieval/` is the only sanctioned entry point to the embedding endpoint (per ADR-006). It exposes a synchronous `embed(text: str) -> list[float]`. No async surface; no batch/list surface until an endpoint is confirmed to accept `input` as a list. At MVP, embedding is per-verse, serial.
- **Config sourcing** for `OPENAI_BASE_URL`, `OPENAI_API_KEY`, model identifier, and dim is environment variable first, then optional non-committed config file. No hardcoded values. No bearer token in the repo.
- **Dim mismatch, HTTP error, and >8K-token input** all raise per ADR-005's failure handling (which incorporates ADR-001).

### Vector store and index

- **Library:** `sqlite-vec` (per ADR-005).
- **Table:** one `vec0` virtual table typed `float[1024]`, keyed by the verse's rowid in a sibling `verses` table.
- **Sibling `verses` table:** stores `(rowid, verse_id, ref_canonical, book, chapter, verse, text)` so the dense search path can join rowid → verse metadata in one SQL statement.
- **Distance metric:** cosine, implemented as inner product over client-side L2-normalized vectors (per ADR-005). The index does not re-normalize at query time.
- **Rejected at this scale:** FAISS, LanceDB, Chroma, Qdrant, Weaviate, Milvus, Pinecone, `hnswlib`. At 41K vectors × 1024 dims (~160 MB float32), a flat kNN over sqlite-vec is sub-millisecond on CPU and requires no service.

### Lexical index (BM25)

- **Library:** `BM25S`.
- **Parameters:** `k1 = 1.5`, `b = 0.75`.
- **Tokenizer:** lowercase, Unicode NFC normalize, split on `\W+`, drop pure-digit tokens shorter than 2 characters, stopwords off for MVP.
- **Persistence:** BM25S's native on-disk format under the index directory.
- **Fallback:** `rank_bm25` if `BM25S` bites us at integration time. (A later CR may consolidate lexical search into SQLite FTS5 for single-file persistence; out of scope here.)

### Hybrid retrieval

- **Default `--mode`:** `hybrid`.
- **Fusion:** Reciprocal Rank Fusion (RRF), `k = 60`.
- **Procedure:** retrieve top-50 from BM25 and top-50 from dense independently, fuse by `score(d) = Σ 1/(k + rank_i(d))`, return top-k after fusion.
- **Other modes:** `bm25` and `dense` exist as `--mode` values for eval and debugging, not as blessed user paths.

### CLI (single deployable: `apps/scripvec_cli/`, contract governed by ADR-007)

- **Framework:** `typer`.
- **Default output format:** **JSON** on stdout, per ADR-007. `--format text` exists as a secondary, unstable, human-debug format.
- **Structured errors on stderr** with stable `error.code` strings per command.
- **Granular, stable exit codes:** `0` success, `1` user error, `2` not-found (empty result set is still `0`; `2` is reserved for e.g. a requested index hash that does not exist), `3` upstream error (embedding endpoint unreachable or returned an error), higher codes allocated per command as needed.
- **No interactive prompts, no pagination, no colors by default.**
- **Subcommands:**
  - `scripvec query "<text>" [--k 10] [--mode {bm25|dense|hybrid}] [--format {json|text}] [--index {<hash>|latest}] [--show-scores]`
  - `scripvec index build [--from-scratch]`
  - `scripvec index list`
  - `scripvec eval run --queries <path> --judgments <path> [--index latest]`
  - `scripvec feedback --query-id <uuid> --verse-id <id> --grade {0,1,2} [--note "..."]`
  - `scripvec --version` (emits JSON with CLI version, ADR-005 embedding-model identifier, and current `latest` index hash).
- **Per-command help text** documents purpose, full flag list with types and defaults, output schema, error codes, and at least one concrete JSON example — per ADR-007's help-text contract.
- **Config passing:** CLI flags and environment variables only; no config file at MVP. `SCRIPVEC_DATA_DIR` env var overrides the default `./data/` path used by scripts.

### Query output schema (JSON, default)

```
{
  "query":      "<string>",
  "mode":       "bm25" | "dense" | "hybrid",
  "k":          <int>,
  "index":      "<hash>",
  "results":    [
    {
      "rank":      <int>,
      "verse_id":  "<string>",
      "ref":       "<canonical reference>",
      "text":      "<verse text>",
      "score":     <float>,
      "scores":    { "bm25": <float|null>, "dense": <float|null>, "rrf": <float|null> }
    }
  ],
  "latency_ms": { "bm25": <float>, "dense": <float>, "fuse": <float>, "total": <float> }
}
```

Results are ordered by `rank` ascending; ties are broken by `verse_id` ascending (deterministic ordering per ADR-007).

### Persistence and rebuild

- **Artifact layout:** `data/indexes/<config_hash>/` containing `corpus.sqlite` (with a `verses` table and the sqlite-vec `vec0` virtual table for dense embeddings), `bm25.bm25s` (lexical index), and `config.json` (the manifest whose hash names the directory).
- **Config hash:** BLAKE2b-128 over a JSON document naming corpus source + commit SHA, ingest/tokenization config, embedding endpoint + model identifier + dim + client-side normalization, BM25 library version and parameters, and the sqlite-vec schema version. Any change to any input changes the hash.
- **`latest` symlink:** `data/indexes/latest` points to the most recently built hash; updated only on successful build.
- **Rebuild command:** `scripvec index build --from-scratch`. Executes ingest → normalize → BM25 build → serial per-verse embedding against the ADR-005 endpoint → insert into `corpus.sqlite` (verses + vec0 rows in one transaction per batch) → persist → symlink update.
- **Endpoint-drift guard (ADR-001):** every query command loads the index's `config.json` and asserts that the configured embedding endpoint URL, the `model`-identifier string, and the 1024 dim all match the active runtime config; mismatch raises. Silent drift between index-time and query-time embedder is the single largest source of undetected retrieval-quality rot and is refused at load time.
- **Corpus-drift guard (ADR-001):** `corpus_ingest` refuses to build against an index whose `corpus.commit_sha` disagrees with `data/raw/` unless `--rebuild-corpus` is passed.

### Logging

- **Query log:** append-only JSONL at `data/logs/queries.jsonl`. One object per query: timestamp, schema_version, session_id, query_id, index_hash, mode, query text, k, top-k results (verse_id, per-component ranks, RRF score), latency breakdown.
- **Feedback log:** append-only JSONL at `data/logs/feedback.jsonl` written by the `feedback` subcommand.
- **Rationale:** JSONL is trivially tailable with `jq`, append-only, schema-migration-free, and appropriate for the MVP's volume. Consolidation into `corpus.sqlite` (or a separate `logs.sqlite`) is deferred to a later CR when join queries earn the complexity.

### Evaluation harness (`packages/eval/`)

- **Held-out query set:** 50-query floor, 75-query target. Stored at `data/eval/queries.jsonl` (one query per line with `query_id`, `query`, `tags`, optional `notes`).
- **Judgments:** graded 0/1/2 scheme — **0** irrelevant (absent from judgments file), **1** relevant, **2** canonical. Stored at `data/eval/judgments.jsonl` (one judgment per `(query_id, verse_id)` pair).
- **Metrics reported:** recall@10, recall@20, nDCG@10, MRR@10, plus latency p50/p95 per mode (`bm25`, `dense`, `hybrid`).
- **Stratification:** eval output breaks recall@10 out by query tag bucket (expected buckets include doctrinal, narrative, phrase-memory, proper-noun), minimum ~8 queries per bucket.
- **Output shape:** default JSON (per ADR-007) — one object containing the metrics table, per-bucket stratified table, pass/fail flags for each ship criterion, and a reference to the failures file. `--format text` produces a readable ASCII table for dogfooding.
- **Failures file:** every query with `recall@10 == 0` is emitted to `data/eval/failures_<timestamp>.jsonl` with the top-10 returned and the judged-relevant set — this is the feedback surface that drives the next CR.
- **Sanity checks on invocation (ADR-001):** query set has no duplicate query strings; every judgment points to an existing `verse_id`; inject three known-good queries whose canonical verses BM25 should score in the top-3 and fail loud if not.

### Ship criteria

- Hybrid beats BM25 by **≥ 5 pts recall@10** on the held-out set.
- Dense beats BM25 by **≥ 5 pts recall@10** on the held-out set. (If the ADR-005 embedder does not clear this, the CR does not ship dense; a sub-CR investigates why dense does not earn weight on this corpus. Per ADR-005, the response to poor dense performance is not to swap models on the current endpoint — it is either to switch endpoints or to invest in non-model axes of quality.)
- Index directory **≤ 400 MB** on disk (dominated by 41K × 1024-dim float32 vectors ≈ 160 MB plus SQLite overhead and the BM25 index).

### Named failure modes instrumented up front

1. **Proper-noun miss** — dense retrieval flattens rare tokens (e.g., "Teancum", "Coriantumr"). Tracked by the `proper-noun` stratification bucket in eval output.
2. **Phrase-memory miss** — dense retrieval rewards semantic overlap over surface phrase match (e.g., "arise and shine forth"). Tracked by the `phrase-memory` stratification bucket.
3. **Endpoint/index drift** — the configured embedding endpoint or model identifier changes between build and query. Caught by the endpoint-drift guard in the persistence section.

### Package internals

Flat module layout per ADR-002 — no `services/`, `handlers/`, or `repositories/` subfolders inside any package. Approximate budget:

- `packages/corpus_ingest/` — reads `data/raw/bcbooks/`, emits `VerseRecord` records.
- `packages/reference/` — citation parse/normalize library.
- `packages/retrieval/` — `build_index()`, `query()`, `rrf()`, and the single embed client module (ADR-006). Target: < 700 lines total.
- `packages/eval/` — `run_eval()` produces the metrics object and failures file. Target: < 250 lines.
- `apps/scripvec_cli/` — Typer entry points. Target: ~250 lines (ADR-007's per-command schema/help text carries some ceremony).

## Impact on referenced docs

- **ADR-001 (fail loud):** applied verbatim to the endpoint-drift guard, the corpus-drift guard, dim-mismatch handling, and the eval sanity checks. No conflict.
- **ADR-002 (no role splitting):** applied verbatim to package internals. No conflict.
- **ADR-003 (folder structure):** every artifact in this CR has a home in the locked folder tree. No conflict; no new top-level folders.
- **ADR-004 (tooling floor):** this CR exercises the Python recipe. Stack pick is recorded here, per ADR-004's explicit instruction that "A CR that introduces code must pick the stack first." No conflict.
- **ADR-005 (embedding endpoint):** this CR builds the index storage, config-hash manifest, and drift guards around ADR-005's pinned endpoint + Qwen3.5 Embedding 0.6B + 1024-dim + sqlite-vec decisions. The embedding model is not re-decided here. No conflict.
- **ADR-006 (serialize embedding calls):** this CR's single embed client module is the sanctioned entry point; no parallel, concurrent, or async surface. No conflict.
- **ADR-007 (agent-first CLI):** this CR exercises the agent-first contract — JSON default output, structured errors, stable exit codes, deterministic ordering, no interactive prompts, documented per-command schemas. No conflict.
- **Principle 001 (vector retrieval):** honored — eval harness, BM25 baseline, held-out query set, and measured ship criteria are all first-class.
- **Policies `pl-001`, `pl-002`, `pl-003`:** this CR uses underscore filenames with the `cr-` type-prefix and cites CRs by filename only. No conflict.

## Decision

Accepted on 2026-04-19 by Jeff Haskin (engineer, sole decision authority).

**Exceptions and clarifications recorded at approval time:**

- **Embedding model is already selected** — the embedding side is governed entirely by ADR-005 and is referenced, not re-litigated, here.
- **Ship criteria approved** as stated, with the standing caveat that the engineer may revisit any number that becomes annoying in practice.
- The cross-encoder reranker deferred by the proposal is split out into a separate CR (`cr-003_cross_encoder_reranker.md`, status `pending`) rather than tracked inline here.

## Implementation plan (MVP 0.0)

### Steel thread

Thin end-to-end path: raw BoM + D&C JSON → `corpus_ingest` yields `VerseRecord`s → `retrieval.build_index` embeds serially per verse, writes `data/indexes/<hash>/{corpus.sqlite, bm25.bm25s, config.json}`, and flips the `latest` symlink → `scripvec query "..."` loads `latest`, runs BM25 top-50 and dense top-50, RRF-fuses at `k = 60`, and prints the CR-002 query JSON on stdout. Everything else (eval, feedback, stratified metrics, additional subcommands) thickens this thread.

### 1. Workspace wiring

1. **Package dependency declarations.**
   1. Add runtime deps to `packages/retrieval/pyproject.toml`: `httpx`, `sqlite-vec`, `bm25s`, `numpy`.
   2. Add `typer` to `apps/scripvec_cli/pyproject.toml`.
   3. Run `uv sync` at the workspace root; confirm a single lockfile resolves.
2. **Data-artifact gitignore.**
   1. Confirm `data/indexes/` and `data/logs/` are gitignored; confirm `data/raw/bcbooks/*.json` and `data/eval/*.jsonl` are checked in (ADR-003).

### 2. packages/reference

Leaf package. No in-repo imports.

1. **Canonical book-name table.** Map every BoM book and the D&C reference form to the pinned canonical string (`1 Nephi`, `D&C`), covering the forms present in `data/raw/bcbooks/*.json`.
2. **Parser.** `parse_reference(s) -> (book, chapter, verse)` for strings like `"1 Nephi 1:1"` and `"D&C 88:118"`. Raise on unknown book names or malformed input (ADR-001).
3. **Canonicalizer.** `canonical(book, chapter, verse) -> str` producing the pinned reference string.

### 3. packages/corpus_ingest

Depends on `reference`.

1. **`VerseRecord`** with fields `(verse_id, ref_canonical, book, chapter, verse, text)`. `verse_id` is derived deterministically from the canonical reference.
2. **Book of Mormon reader.** Walks `books[].chapters[].verses[]` in `data/raw/bcbooks/book-of-mormon.json`; yields `VerseRecord`s.
3. **Doctrine and Covenants reader.** Walks the D&C JSON shape.
4. **Single entry point `iter_verses(data_dir)`** yielding every verse from both corpora in a deterministic order.

### 4. packages/retrieval

Depends on `corpus_ingest` and `reference`. Flat module layout per ADR-002 — every module at the top of `src/scripvec_retrieval/`.

1. **Embed client** — the single sanctioned entry point per ADR-006. Build it first; every other component below uses it or its config.
   1. `embed(text: str) -> list[float]`. Synchronous, serial, no async/batch surface.
   2. Sourced-from-env config: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, model identifier, and dim (env first, optional non-committed config file second; no hardcoded values).
   3. POST to `{base_url}/embeddings` with `{"model": <name>, "input": <text>}`; parse `data[0].embedding`.
   4. Reject text with estimated token count over 8,000 before the request is made (ADR-005; no silent truncation).
   5. Raise `RuntimeError` with observed and expected dims if the returned vector length does not match the configured dim (ADR-005).
   6. Raise on non-2xx responses. No retry.
   7. Client-side L2-normalize; return `list[float]`.
   8. Unit test mocking a wrong-length response (validation clause in ADR-005).
2. **Config-hash manifest.**
   1. Assemble the manifest dict: corpus source + commit SHA, ingest/tokenization config, embedding endpoint URL + model identifier + dim + normalization flag, BM25 library version + parameters, `sqlite-vec` schema version.
   2. `config_hash(manifest) -> str` — BLAKE2b-128 hex over canonical JSON (sorted keys, no whitespace).
   3. Writer and reader for `config.json` at `data/indexes/<hash>/config.json`.
3. **Paths and data-dir resolution.** Resolve `data_dir` from `SCRIPVEC_DATA_DIR` env or default `./data/`; expose helpers for `indexes_dir`, `raw_dir`, `eval_dir`, `logs_dir`, `index_path(hash)`, and the `latest` symlink.
4. **Persistence layout.** Create `corpus.sqlite` containing the sibling `verses(rowid, verse_id, ref_canonical, book, chapter, verse, text)` table and the `sqlite-vec` `vec0` virtual table typed `float[1024]`, keyed by `verses.rowid`. Batched-insert helper writes a verse row and its vector in the same transaction per batch.
5. **BM25 lexical index.**
   1. Tokenizer: lowercase → Unicode NFC normalize → split on `\W+` → drop pure-digit tokens shorter than 2 chars; stopwords off.
   2. Build via `BM25S` with `k1 = 1.5`, `b = 0.75`; persist in BM25S's native on-disk format under the index directory.
   3. `bm25_topk(query, k=50)` returning `(rowid, score)` pairs.
6. **Dense index access.** `dense_topk(conn, query_vec, k=50)` — inner-product top-k over the `vec0` table, joining `rowid → verses` in one SQL statement.
7. **RRF fusion.** `rrf(bm25_results, dense_results, k=60, top_k=10)` with `score(d) = Σ 1/(k + rank_i(d))`; ties broken deterministically by `verse_id` ascending (ADR-007).
8. **Build pipeline.** `build_index(from_scratch=True, rebuild_corpus=False) -> index_hash` — ingest via `corpus_ingest.iter_verses` → serial per-verse embed → transactional insert (`verses` + `vec0`) → build BM25 → write `config.json` → atomic `latest` symlink update **only on success** (CR-002).
9. **Corpus-drift guard** (ADR-001). Ingest refuses to build against an index whose `corpus.commit_sha` disagrees with `data/raw/` unless `rebuild_corpus=True`.
10. **Query path.** `query(text, k=10, mode, index="latest") -> QueryResult`.
    1. Load `config.json` from the target index.
    2. **Endpoint-drift guard** (ADR-001): assert configured endpoint URL, model identifier, and dim match the running embed client config; raise on mismatch.
    3. Execute the selected mode(s) (`bm25`, `dense`, `hybrid`); capture per-stage latency (`bm25`, `dense`, `fuse`, `total`).
    4. Join `rowid → verses` metadata; return the CR-002 query output shape (`rank`, `verse_id`, `ref`, `text`, `score`, per-component `scores`, `latency_ms`, `index`). `mode="hybrid"` fuses via `rrf`.

### 5. apps/scripvec_cli — steel-thread subcommands

Depends on `retrieval`. Contract per ADR-007 and CR-002. Build the two steel-thread subcommands first; the rest follow.

1. **CLI skeleton.**
   1. Typer root with JSON default on stdout; colors, pagination, and interactive prompts disabled.
   2. `emit_error(code, message, details)` writer: structured JSON on stderr per ADR-007; documented exit codes `0` success, `1` user error, `2` not-found, `3` upstream error.
2. **`scripvec index build`.** Flags `--from-scratch`, `--rebuild-corpus`. Calls `retrieval.build_index`. On success, prints JSON naming the new index hash and the `latest` pointer update; on failure, structured stderr error + appropriate exit code. Per-command help text: purpose, flag table, output schema, error-code table, one concrete JSON example (ADR-007).
3. **`scripvec query`.** Flags: positional `"<text>"`, `--k 10`, `--mode {bm25|dense|hybrid}` (default `hybrid`), `--format {json|text}` (default `json`), `--index {<hash>|latest}` (default `latest`), `--show-scores`. Calls `retrieval.query`; prints the CR-002 query output shape; deterministic ordering by `rank` then `verse_id`. Exit codes: `1` bad flag, `2` requested index hash does not exist, `3` endpoint unreachable or endpoint-drift guard trip. Appends a JSONL record to `data/logs/queries.jsonl` per CR-002 (timestamp, schema_version, session_id, query_id, index_hash, mode, query, k, top-k with per-component ranks and RRF score, latency breakdown). Per-command help text with a concrete JSON example.

### 6. apps/scripvec_cli — remaining subcommands

Build after System 5's steel thread is verified.

1. **`scripvec --version`.** JSON with CLI version, ADR-005 embedding-model identifier (from env), and current `latest` index hash.
2. **`scripvec index list`.** Enumerate `data/indexes/*/config.json`; emit a JSON array of `{hash, created_at, model, dim, is_latest}` with deterministic ordering.
3. **`scripvec feedback`.** Flags `--query-id <uuid>`, `--verse-id <id>`, `--grade {0,1,2}`, `--note "..."`. Append one record to `data/logs/feedback.jsonl`; emit JSON confirmation on stdout.
4. **JSON output-contract tests** (ADR-007 validation clause). One test per subcommand asserting parsed-JSON shape against the documented schema; one test per subcommand asserting the structured stderr error shape on a forced failure.

### 7. packages/eval

Depends on `retrieval`. Sequenced after System 6 so the `query` CLI exists for dogfooding while the harness is written, but independent of System 8.

1. **Loaders.** Read `queries.jsonl` and `judgments.jsonl`. Sanity checks on invocation (ADR-001 + CR-002): no duplicate query strings; every judgment points to an existing `verse_id`; malformed rows raise.
2. **Metrics.** `recall@10`, `recall@20`, `nDCG@10`, `MRR@10` over graded relevance (0 absent, 1 relevant, 2 canonical).
3. **Stratification.** Recall@10 broken out per tag bucket (`doctrinal`, `narrative`, `phrase-memory`, `proper-noun`); minimum ~8 queries per bucket asserted at load time.
4. **Sanity-probe injection** (CR-002). Three known-good queries whose canonical verses BM25 should score in the top-3; fail loud if any probe does not clear top-3.
5. **Failures file.** Every query with `recall@10 == 0` is written to `data/eval/failures_<timestamp>.jsonl` with the top-10 returned and the judged-relevant set.
6. **Orchestrator.** `run_eval(queries_path, judgments_path, index) -> EvalReport`: runs every query through every mode (`bm25`, `dense`, `hybrid`), records latency p50/p95 per mode, computes metrics and stratification, evaluates each CR-002 ship-criterion pass/fail flag, writes the failures file, returns the metrics object.

### 8. apps/scripvec_cli — eval subcommand

1. **`scripvec eval run`.** Flags `--queries <path>`, `--judgments <path>`, `--index latest`. Calls `eval.run_eval`. Default JSON output with the metrics table, per-bucket stratified table, pass/fail flags for each ship criterion, and the failures-file path; `--format text` produces the ASCII table. Per-command help text; output-contract test.

### 9. Eval corpus authoring

Depends on System 5's `query` subcommand being live so dogfooding surfaces query candidates.

1. **`data/eval/queries.jsonl`.** Author a 50-query floor (75-query target). One object per line with `query_id`, `query`, `tags`, optional `notes`. ≥8 queries in each of the four buckets: `doctrinal`, `narrative`, `phrase-memory`, `proper-noun`.
2. **`data/eval/judgments.jsonl`.** Graded judgments — `1` relevant, `2` canonical; `0` = absent from file. One row per `(query_id, verse_id)` pair judged.

### 10. Build and validate

Every prior system must be alive. This step runs the CR-002 ship criteria for real.

1. Run `scripvec index build --from-scratch`; confirm `data/indexes/<hash>/` contains `corpus.sqlite`, `bm25.bm25s`, `config.json`; confirm `data/indexes/latest` points at it.
2. Smoke: `scripvec query "faith and works" --k 10`; confirm JSON validates against the documented schema.
3. Run `scripvec eval run --queries data/eval/queries.jsonl --judgments data/eval/judgments.jsonl`. Report each CR-002 ship criterion in the eval output: (a) hybrid beats BM25 by ≥ 5 pts recall@10, (b) dense beats BM25 by ≥ 5 pts recall@10, (c) index directory ≤ 400 MB on disk. Do not paper over a failure — a failing criterion is the signal (ADR-001).

### Dependency notes

- System 2 before System 3: `corpus_ingest` calls `reference.canonical(...)` to populate `ref_canonical` and derive `verse_id`.
- Within System 4: embed client before everything else (it supplies the normalization contract the index depends on); manifest and paths before persistence; persistence before build; BM25 and dense are independent of each other; RRF after both exist; query path and drift guards after persistence is writable and manifest-readable.
- System 5 (steel-thread subcommands) depends only on System 4. System 6 (remaining subcommands) depends on System 5's skeleton. System 7 (`eval`) depends on System 4's `query` but not on any CLI. System 8 (`eval run` subcommand) depends on Systems 5, 6, and 7.
- System 9 (authoring) can begin as soon as System 5 is live; must complete before System 10.

### Sprints

Three sprints, each ending at a natural join point. Within a sprint, tracks marked `‖` are independent and can run in parallel. System / component numbers refer to the work breakdown above.

#### Sprint 1 — Foundations

**Goal:** every leaf module that nothing else blocks on.

- Serial first: **System 1** (workspace wiring) — small, must land before anything else.
- Then in parallel:
  - ‖ **System 2** — `reference`
  - ‖ **Component 4.1** — embed client (incl. wrong-length unit test)
  - ‖ **Component 4.2** — config-hash manifest
  - ‖ **Component 4.3** — paths / data-dir resolution
  - ‖ **Component 4.7** — RRF fusion (pure math, no I/O)

**Join point:** all leaves merged. `embed("hello")` returns a normalized 1024-vec against the live endpoint.

#### Sprint 2 — Index + query pipeline

**Goal:** `retrieval.build_index()` and `retrieval.query()` work end-to-end as Python APIs (no CLI yet).

- ‖ **System 3** — `corpus_ingest` (needs `reference`)
- ‖ **Component 4.4** — persistence (needs 4.3)
- ‖ **Component 4.5** — BM25 build/load (needs 4.3)
- ‖ **Component 4.6** — dense top-k (needs 4.4 schema)
- ‖ **System 9 (start)** — begin authoring `data/eval/queries.jsonl` from cold knowledge of the corpus; no code dep, long-pole task, start it now.

Joiners (sequential at end of sprint):

- **Components 4.8 + 4.9** — build pipeline + corpus-drift guard
- **Component 4.10** — query path + endpoint-drift guard

**Join point:** `python -c "from scripvec_retrieval import build_index, query; build_index(); print(query('faith and works'))"` returns the CR-002 result shape.

#### Sprint 3 — Surface + measure

**Goal:** ship criteria evaluated.

- ‖ **System 5** — CLI steel-thread (`skeleton + index build + query`); depends on Sprint 2.
- ‖ **System 7** — `packages/eval`; depends only on `retrieval.query`; fully independent of the CLI.
- ‖ **System 9 (continue/finish)** — eval queries + judgments authoring.
- After System 5's skeleton lands: ‖ **System 6** — remaining CLI subcommands + contract tests.

Joiners at end:

- **System 8** — `scripvec eval run` (needs 5, 6, 7).
- **System 10** — build, run, report ship criteria.

**Join point:** ship-criteria pass/fail recorded.

#### Where parallelism pays off

Sprint 1 (five independent tracks, all small) and Sprint 3 (CLI + eval harness + content authoring on three separate tracks). Sprint 2 is dominated by the build-pipeline join, so parallel gain there is bounded by the four index modules feeding two sequential joiners.

### File blueprint

The file-level realization of the work breakdown above. Each `(new)` file is briefed with what it *hides* (deep-modules discipline). **36 new code files + 2 authored eval data files; 16 already scaffolded.** Flat module layout per ADR-002 — no role-folders inside any package; tests co-located adjacent to source. Generated by channeling John Ousterhout against this CR plus ADRs 001–007. (Test scope expanded 2026-04-20: see Expanded test coverage block in per-file briefs and function plan.)

#### File tree

```
scripvec/
  pyproject.toml                                                              (scaffolded)
  README.md / .editorconfig / .gitignore / CODEOWNERS                         (scaffolded)

  apps/scripvec_cli/
    pyproject.toml / README.md                                                (scaffolded)
    src/scripvec_cli/
      __init__.py                                                             (scaffolded)
      main.py                                                                 (new)
      errors.py                                                               (new)
      query_cmd.py                                                            (new)
      index_cmd.py                                                            (new)   ← `index build` + `index list`
      eval_cmd.py                                                             (new)
      feedback_cmd.py                                                         (new)
      version_cmd.py                                                          (new)
      query_log.py                                                            (new)
      test_contracts.py                                                       (new)   ← ADR-007 contract tests

  packages/reference/src/scripvec_reference/
    __init__.py                                                               (scaffolded)
    books.py                                                                  (new)
    reference.py                                                              (new)

  packages/corpus_ingest/src/scripvec_corpus_ingest/
    __init__.py                                                               (scaffolded)
    verse.py                                                                  (new)
    bcbooks.py                                                                (new)

  packages/retrieval/src/scripvec_retrieval/
    __init__.py                                                               (scaffolded)
    config.py                                                                 (new)
    paths.py                                                                  (new)
    embed.py                                                                  (new)
    test_embed.py                                                             (new)   ← ADR-005 wrong-length test
    hashing.py                                                                (new)
    test_hashing.py                                                           (new)
    manifest.py                                                               (new)
    test_manifest.py                                                          (new)
    store.py                                                                  (new)
    tokenizer.py                                                              (new)
    test_tokenizer.py                                                         (new)
    bm25.py                                                                   (new)
    rrf.py                                                                    (new)
    test_rrf.py                                                               (new)
    build.py                                                                  (new)
    test_build.py                                                             (new)   ← corpus-drift guard tests
    query.py                                                                  (new)
    test_query.py                                                             (new)   ← endpoint-drift guard tests

  packages/eval/src/scripvec_eval/
    __init__.py                                                               (scaffolded)
    dataset.py                                                                (new)
    test_dataset.py                                                           (new)   ← JSONL loader tests
    metrics.py                                                                (new)
    test_metrics.py                                                           (new)
    run.py                                                                    (new)

  data/raw/bcbooks/{book-of-mormon,doctrine-and-covenants}.json               (scaffolded)
  data/eval/queries.jsonl                                                     (new)
  data/eval/judgments.jsonl                                                   (new)
```

**Runtime artifacts (not authored, produced by `scripvec index build` / `query` / `eval run`):**

```
data/indexes/<config_hash>/corpus.sqlite
data/indexes/<config_hash>/bm25.bm25s            (BM25S on-disk format)
data/indexes/<config_hash>/config.json
data/indexes/latest                              (symlink → most-recent hash)
data/logs/queries.jsonl
data/logs/feedback.jsonl
data/eval/failures_<timestamp>.jsonl
```

#### Per-file briefs

Each block: **Hides / contains** (the design decision the file encapsulates, Ousterhout-style), **Public surface** (the contract callers see), **Co-located tests** where applicable. `__init__.py` files only get a brief when they re-export.

##### `apps/scripvec_cli/src/scripvec_cli/`

**`__init__.py`** *(scaffolded)* — empty; the package's entry point is the console script.

**`main.py`** *(new)*
- **Hides / contains:** the Typer root configuration — that we use Typer at all, that colors / pagination / interactive prompts are disabled, that JSON is the default format, and the registration of every subcommand. Callers downstream never see `typer` directly. Wired to the existing console script `scripvec = "scripvec_cli.main:app"` in `pyproject.toml`.
- **Public surface:**
  - `app: typer.Typer` — the configured root app (colors off, no pager, `add_completion=False`); Typer apps are callable, so the console script invokes it directly.

**`errors.py`** *(new)*
- **Hides / contains:** the shape of the ADR-007 structured error — `{"error": {"code", "message", "details"}}` — and the stable exit-code table (`0`/`1`/`2`/`3`). Every subcommand that fails goes through this one writer so the error shape can't drift.
- **Public surface:**
  - `emit_error(code: str, message: str, details: dict | None = None, exit_code: int = 1) -> NoReturn` — writes JSON to stderr and exits.
  - `ExitCode` — constants: `SUCCESS=0`, `USER_ERROR=1`, `NOT_FOUND=2`, `UPSTREAM_ERROR=3`.

**`query_cmd.py`** *(new)*
- **Hides / contains:** the `scripvec query` wiring — flag parsing, the ADR-007 help-text block (purpose / flags / schema / exit codes / JSON example), mapping `retrieval.query()`'s return onto the CR-002 output JSON, and the call to `query_log.append(...)`. Knows nothing about how retrieval works; only about the agent contract.
- **Public surface:**
  - `register(app: typer.Typer) -> None` — attaches `query` to the root.

**`index_cmd.py`** *(new)*
- **Hides / contains:** the `scripvec index build` and `scripvec index list` subcommand group — flag parsing, help text, delegation to `retrieval.build_index()` and a small enumerator over `data/indexes/*/config.json`. Two commands, one file: they share the `index` Typer sub-app and the same output-schema idioms; splitting them would force a two-file boundary over one call each.
- **Public surface:** `register(app: typer.Typer) -> None`.

**`eval_cmd.py`** *(new)*
- **Hides / contains:** the `scripvec eval run` wiring — flag parsing, help text, delegation to `eval.run()`, JSON / text formatting of the metrics report, and the failures-file path echo.
- **Public surface:** `register(app: typer.Typer) -> None`.

**`feedback_cmd.py`** *(new)*
- **Hides / contains:** the `scripvec feedback` wiring — appends one record to `data/logs/feedback.jsonl` and emits a JSON confirmation on stdout. The append discipline (atomic JSONL line, timestamp, schema_version) is co-located with the command rather than hoisted into a module of its own, because nothing else writes feedback and the whole operation is ~15 lines.
- **Public surface:** `register(app: typer.Typer) -> None`.

**`version_cmd.py`** *(new)*
- **Hides / contains:** the `scripvec --version` output shape — `{cli_version, embedding_model, latest_index_hash}`. Small, stable, worth its own file so the output schema is one `cat` away — `--version` is part of the agent contract per ADR-007.
- **Public surface:** `register(app: typer.Typer) -> None`.

**`query_log.py`** *(new)*
- **Hides / contains:** the on-disk format of `data/logs/queries.jsonl` — timestamp, `schema_version`, `session_id`, `query_id`, fields, ordering. Append-only. Every caller just says *"record this query"*; the JSONL schema lives here. A future CR that migrates logs to SQLite touches only this file.
- **Public surface:**
  - `append(record: QueryLogRecord) -> None` — atomic JSONL line append to `data/logs/queries.jsonl`.
  - `QueryLogRecord` — TypedDict / dataclass with the CR-002 fields.

**`test_contracts.py`** *(new)*
- **Hides / contains:** the ADR-007 validation clause — one test per subcommand (`query`, `index build`, `index list`, `eval run`, `feedback`, `--version`) asserting parsed-JSON shape against the documented schema; one test per subcommand asserting the structured stderr error shape on a forced failure. Uses Typer's `CliRunner`.
- **Public surface:** pytest collection only.

##### `packages/reference/src/scripvec_reference/`

**`__init__.py`** *(scaffolded)* — re-exports `parse_reference`, `canonical`, and the `Reference` dataclass from `reference.py`.

**`books.py`** *(new)*
- **Hides / contains:** the canonical book-name table for BoM + D&C — every spelling / abbreviation that appears in `data/raw/bcbooks/*.json` mapped to its pinned canonical form (`"1 Nephi"`, `"D&C"`). Pure data; the one place that changes when a new corpus is added.
- **Public surface:**
  - `CANONICAL_BOOKS: tuple[str, ...]` — ordered canonical book list (drives deterministic verse ordering).
  - `canonicalize_book(raw: str) -> str` — raises `ValueError` on unknown input (ADR-001).

**`reference.py`** *(new)*
- **Hides / contains:** the citation grammar — how `"1 Nephi 1:1"` and `"D&C 88:118"` parse, and how `(book, chapter, verse)` rounds back to a canonical string. The only module that knows about the `"Book Chapter:Verse"` shape; callers treat references as opaque strings after `canonical()`.
- **Public surface:**
  - `@dataclass(frozen=True) class Reference: book: str; chapter: int; verse: int`.
  - `parse_reference(s: str) -> Reference` — raises `ValueError` on unknown book or malformed input.
  - `canonical(book: str, chapter: int, verse: int) -> str` — returns pinned reference string.

##### `packages/corpus_ingest/src/scripvec_corpus_ingest/`

**`__init__.py`** *(scaffolded)* — re-exports `VerseRecord` and `iter_verses`.

**`verse.py`** *(new)*
- **Hides / contains:** the `VerseRecord` shape and the deterministic `verse_id` derivation from the canonical reference. One place defines what a verse record *is*; ingest readers and the retrieval persistence layer both depend on this shape. Changing the `verse_id` derivation would touch this file alone.
- **Public surface:**
  - `@dataclass(frozen=True) class VerseRecord: verse_id: str; ref_canonical: str; book: str; chapter: int; verse: int; text: str`.
  - `make_verse_id(ref_canonical: str) -> str` — stable hash-or-slug derivation.

**`bcbooks.py`** *(new)*
- **Hides / contains:** the JSON shape of the bcbooks corpus — `books[].chapters[].verses[]` for the Book of Mormon, and the (slightly different) D&C shape. Callers ask for "every verse in deterministic order" and never see the JSON. One file because both readers walk the same conceptual tree and will change together if the corpus is re-exported.
- **Public surface:**
  - `iter_verses(data_dir: Path) -> Iterator[VerseRecord]` — single entry point; yields BoM then D&C, in canonical-book order, chapter-then-verse ascending.
  - `corpus_commit_sha(data_dir: Path) -> str` — git commit SHA of `data/raw/bcbooks/`, used by the corpus-drift guard.

##### `packages/retrieval/src/scripvec_retrieval/`

This is the package that carries the MVP. Most non-obvious grouping decisions live here.

**`__init__.py`** *(scaffolded)* — re-exports `build_index`, `query`, `QueryResult`, and the top-level types callers need. Deliberately does **not** re-export `embed` — callers outside the package should not be reaching for it (ADR-006: single sanctioned entry point, internal to retrieval).

**`config.py`** *(new)*
- **Hides / contains:** where embedding config comes from — `OPENAI_BASE_URL`, `OPENAI_API_KEY`, model identifier, dim. Env first, optional non-committed config file second (ADR-005). No hardcoded values; no token in the repo. Callers get a resolved object; the env / file precedence is invisible.
- **Public surface:**
  - `@dataclass(frozen=True) class EmbedConfig: base_url: str; api_key: str; model: str; dim: int`.
  - `load_embed_config() -> EmbedConfig` — raises if required values are missing (ADR-001).

**`paths.py`** *(new)*
- **Hides / contains:** the `data/` layout and the `SCRIPVEC_DATA_DIR` override. Every other module asks this one "where is the indexes dir?" / "what's the path for this hash?" / "where does `latest` point?" — nobody else joins strings.
- **Public surface:**
  - `data_dir() -> Path` — honors `SCRIPVEC_DATA_DIR`; default `./data/`.
  - `raw_dir() -> Path`, `eval_dir() -> Path`, `logs_dir() -> Path`, `indexes_dir() -> Path`.
  - `index_path(config_hash: str) -> Path`.
  - `latest_symlink() -> Path` and `resolve_latest() -> str` (the hash the symlink points at; raises if missing).
  - `set_latest(config_hash: str) -> None` — atomic symlink swap; called only on successful build.

**`embed.py`** *(new)*
- **Hides / contains:** the wire format of the OpenAI-compatible `/embeddings` endpoint, the 8K-token pre-check, the dim-mismatch assertion, the client-side L2 normalization, and the fact that all calls are serial (ADR-006). The sanctioned entry point per ADR-006. Replacing the endpoint protocol touches this file alone.
- **Public surface:**
  - `embed(text: str) -> list[float]` — synchronous, serial, normalized. Raises `RuntimeError` on HTTP error, dim mismatch, or >8K-token input. No async, no batch, no retry.
- **Co-located tests (`test_embed.py`):** ADR-005's wrong-length response unit test — mocks a response whose vector length does not match the configured dim, asserts `RuntimeError` with observed + expected dims in the message.

**`hashing.py`** *(new)*
- **Hides / contains:** the BLAKE2b-128-over-canonical-JSON hashing primitive used to name an index directory. Pure function; no I/O. Pulled out of `manifest.py` so it can be unit-tested in isolation against fixed-byte inputs and so a future change to the hash algorithm touches one file.
- **Public surface:**
  - `blake2b_128_hex(payload: bytes) -> str` — returns 32-char hex digest.
  - `canonical_json(obj: object) -> bytes` — sorted keys, no whitespace, UTF-8.

**`manifest.py`** *(new)*
- **Hides / contains:** the `config.json` manifest — its field set and its on-disk read / write. The single source of truth for "is this index configuration still the same?" Any caller that wants to detect drift asks this module. Hashing is delegated to `hashing.py`.
- **Public surface:**
  - `@dataclass(frozen=True) class Manifest` — fields for corpus source + commit SHA, ingest / tokenization config, embedding endpoint + model + dim + normalization flag, BM25 lib version + params, sqlite-vec schema version.
  - `config_hash(m: Manifest) -> str` — composes `canonical_json` and `blake2b_128_hex`.
  - `write_manifest(m: Manifest, path: Path) -> None`.
  - `read_manifest(path: Path) -> Manifest`.

**`store.py`** *(new)*
- **Hides / contains:** the on-disk layout of `corpus.sqlite` — the `verses(rowid, verse_id, ref_canonical, book, chapter, verse, text)` sibling table, the `sqlite-vec` `vec0` virtual table typed `float[1024]`, the fact that inserts happen inside one transaction per batch (ADR-001's "one step fails, whole thing rolls back"), and the rowid-keyed join between them. Dense retrieval asks this module for "top-k by inner product against `query_vec`"; it does not see SQL.
- **Public surface:**
  - `open_store(path: Path, *, create: bool = False) -> StoreConn` — opens / creates `corpus.sqlite`; loads the `sqlite-vec` extension.
  - `insert_batch(conn: StoreConn, rows: Iterable[tuple[VerseRecord, list[float]]]) -> None` — transactional; fails loud on dim mismatch.
  - `dense_topk(conn: StoreConn, query_vec: list[float], k: int = 50) -> list[DenseHit]` — returns `(verse_id, rowid, cosine, VerseRecord fields)` joined in one statement.
  - `get_verse(conn: StoreConn, verse_id: str) -> VerseRecord`.

**`tokenizer.py`** *(new)*
- **Hides / contains:** the BM25 tokenization rules — lowercase → Unicode NFC normalize → split on `\W+` → drop pure-digit tokens shorter than 2 chars; stopwords off. Pulled out of `bm25.py` so the rules can be unit-tested directly against fixed strings and so a future tokenization change does not touch the BM25 wrapper.
- **Public surface:**
  - `tokenize(text: str) -> list[str]` — pure function.

**`bm25.py`** *(new)*
- **Hides / contains:** BM25 as an abstraction — the `k1=1.5`, `b=0.75` parameters, the choice of `BM25S` as the underlying library, and the on-disk serialization format. Tokenization is delegated to `tokenizer.py`. Callers say "build a lexical index over these verses" and "give me the top-50 for this query"; they never import `bm25s` themselves. A swap to `rank_bm25` or FTS5 in a future CR lives entirely inside this file.
- **Public surface:**
  - `build_bm25(verses: Sequence[VerseRecord], index_dir: Path) -> None` — tokenizes (via `tokenize`), indexes, persists in BM25S's native on-disk format under `index_dir`.
  - `load_bm25(index_dir: Path) -> Bm25Index` — opaque handle.
  - `bm25_topk(idx: Bm25Index, query: str, k: int = 50) -> list[tuple[str, float]]` — returns `(verse_id, score)` pairs.

**`rrf.py`** *(new)*
- **Hides / contains:** the RRF fusion rule — `score(d) = Σ 1/(k + rank_i(d))` with `k=60`, deterministic tiebreak by `verse_id` ascending (ADR-007). Pure math, no I/O. Its own file because RRF is the one decision that changes if we ever try a different fusion, and it's cleanest to test independently.
- **Public surface:**
  - `rrf(bm25_hits: Sequence[tuple[str, float]], dense_hits: Sequence[tuple[str, float]], *, k: int = 60, top_k: int = 10) -> list[tuple[str, float]]` — returns `(verse_id, rrf_score)` pairs, sorted.

**`build.py`** *(new)*
- **Hides / contains:** the ingest → embed → index → persist → symlink sequence. The fact that the `latest` symlink only flips on success (ADR-001), the corpus-drift guard (`corpus.commit_sha` vs `data/raw/`), the assembly of the manifest, and the transactional batching are all internal to this module. Callers say `build_index()`; they don't see the steps.
- **Public surface:**
  - `build_index(*, from_scratch: bool = True, rebuild_corpus: bool = False) -> str` — returns the new `config_hash`. Raises on drift or any step failure.

**`query.py`** *(new)*
- **Hides / contains:** the query path — loading `config.json` from the target index, the endpoint-drift guard (ADR-001: endpoint URL + model identifier + dim must match runtime config; raise on mismatch), dispatching on `mode ∈ {bm25, dense, hybrid}`, capturing per-stage latency, joining `rowid → verses`, and returning the CR-002 output shape. `hybrid` is implemented here by calling `bm25_topk`, `dense_topk` (via `embed`), and `rrf` in sequence — the orchestration is this file's job.
- **Public surface:**
  - `@dataclass(frozen=True) class QueryResult` — exactly the CR-002 output shape (`query`, `mode`, `k`, `index`, `results[]`, `latency_ms{}`).
  - `query(text: str, *, k: int = 10, mode: str = "hybrid", index: str = "latest") -> QueryResult`.

##### `packages/eval/src/scripvec_eval/`

**`__init__.py`** *(scaffolded)* — re-exports `run` and `EvalReport`.

**`dataset.py`** *(new)*
- **Hides / contains:** the JSONL shapes of `queries.jsonl` and `judgments.jsonl`, the ADR-001 sanity checks (no duplicate query strings, every judgment points at a real `verse_id`, malformed rows raise), the ≥8-per-bucket assertion, and the three sanity-probe queries (CR-002) inlined as a module-level constant — they're a contract the harness enforces, not data a human edits, so they live with the loaders that enforce them.
- **Public surface:**
  - `@dataclass(frozen=True) class QueryRow: query_id: str; query: str; tags: tuple[str, ...]; notes: str | None`.
  - `@dataclass(frozen=True) class Judgment: query_id: str; verse_id: str; grade: int  # 1 or 2`.
  - `load_queries(path: Path) -> list[QueryRow]` — raises on duplicates or malformed rows; asserts ≥8 per bucket.
  - `load_judgments(path: Path, known_verse_ids: set[str]) -> list[Judgment]` — raises on unknown `verse_id` or malformed row.
  - `run_sanity_probes(conn, bm25_idx) -> None` — raises if any of the three pinned probes does not clear BM25 top-3.

**`metrics.py`** *(new)*
- **Hides / contains:** the definitions of `recall@k`, `nDCG@10`, and `MRR@10` over graded relevance (0 absent / 1 relevant / 2 canonical), plus p50 / p95 latency computation. Pure functions. One file because these four metrics change together if the grading scheme changes.
- **Public surface:**
  - `recall_at_k(retrieved: Sequence[str], relevant: Mapping[str, int], k: int) -> float`.
  - `ndcg_at_10(retrieved: Sequence[str], relevant: Mapping[str, int]) -> float`.
  - `mrr_at_10(retrieved: Sequence[str], relevant: Mapping[str, int]) -> float`.
  - `percentile(samples: Sequence[float], p: float) -> float` — p50 / p95.

**`run.py`** *(new)*
- **Hides / contains:** the evaluation orchestration — runs every query through every mode (`bm25`, `dense`, `hybrid`), times each, computes metrics, stratifies recall@10 by bucket, evaluates each CR-002 ship criterion, writes `failures_<timestamp>.jsonl`, and assembles the `EvalReport`. Ship-criterion thresholds live in this file as named constants.
- **Public surface:**
  - `@dataclass(frozen=True) class EvalReport` — metrics table, per-bucket stratified table, ship-criterion pass / fail flags, failures-file path.
  - `run(queries_path: Path, judgments_path: Path, *, index: str = "latest") -> EvalReport`.

##### `data/eval/`

**`queries.jsonl`** *(new)* — authored content, not a module. One object per line: `{query_id, query, tags, notes?}`. 50-query floor, 75-query target; ≥8 per bucket across `doctrinal`, `narrative`, `phrase-memory`, `proper-noun`.

**`judgments.jsonl`** *(new)* — authored content, not a module. One object per line: `{query_id, verse_id, grade}` where `grade ∈ {1, 2}`; absence means `0`.

##### Expanded test coverage (added 2026-04-20)

Engineer expanded the unit-test scope beyond the two ADR-mandated test files (`test_embed.py`, `test_contracts.py`) to cover every pure-function and drift-guard module Ousterhout flagged as untested. `store.py` and `bm25.py` remain unit-untested deliberately — both require a live `sqlite-vec` connection or BM25S index to exercise meaningfully and are integration-test surfaces, not unit-test surfaces; the eval harness exercises both end-to-end. All test files use pytest collection only.

**`packages/retrieval/src/scripvec_retrieval/test_tokenizer.py`** *(new)*
- **Hides / contains:** unit tests for `tokenize` — fixed-string fixtures asserting Unicode NFC normalization, lowercasing, `\W+` splitting, the drop-pure-digit-shorter-than-2-chars rule, and determinism (same input → same output).

**`packages/retrieval/src/scripvec_retrieval/test_rrf.py`** *(new)*
- **Hides / contains:** unit tests for `rrf` — verifies the `1/(k + rank)` formula on small fixed inputs; verifies tiebreak by `verse_id` ascending; verifies `top_k` truncation; verifies `ValueError` on `k < 1` and `top_k < 1`.

**`packages/retrieval/src/scripvec_retrieval/test_hashing.py`** *(new)*
- **Hides / contains:** unit tests for `canonical_json` (sorted keys, no whitespace, UTF-8) and `blake2b_128_hex` (32-char hex, deterministic). Verifies that two semantically-equivalent dicts with different key insertion order produce identical bytes from `canonical_json` and identical hashes downstream.

**`packages/retrieval/src/scripvec_retrieval/test_manifest.py`** *(new)*
- **Hides / contains:** round-trip test (`write_manifest` → `read_manifest` returns an equal `Manifest`); strict-read tests asserting `RuntimeError` on missing required fields, on extra unknown fields, on type mismatches.

**`packages/retrieval/src/scripvec_retrieval/test_query.py`** *(new)*
- **Hides / contains:** unit tests for the endpoint-drift guard `_drift_check_endpoint` — asserts `RuntimeError` on mismatched URL, model identifier, or dim, and that the message names which field disagreed; asserts silent return on full match. Also covers `_resolve_index` for `"latest"` resolution, explicit-hash resolution, and the missing-directory failure path.

**`packages/retrieval/src/scripvec_retrieval/test_build.py`** *(new)*
- **Hides / contains:** unit tests for the corpus-drift guard `_drift_check_corpus` — asserts `RuntimeError` when stored and observed commit SHAs disagree and `rebuild_corpus=False`; asserts silent return when commits match or when `rebuild_corpus=True`; asserts the message names both commits.

**`packages/eval/src/scripvec_eval/test_metrics.py`** *(new)*
- **Hides / contains:** unit tests for `recall_at_k`, `ndcg_at_10`, `mrr_at_10`, and `percentile` — fixed fixtures with known correct values. Covers grade-0 / 1 / 2 mixes; the empty-relevant edge case; the single-sample edge case; out-of-range / `k < 1` raises.

**`packages/eval/src/scripvec_eval/test_dataset.py`** *(new)*
- **Hides / contains:** unit tests for `load_queries` and `load_judgments` — asserts `RuntimeError` on duplicate `query` text, duplicate `query_id`, malformed JSON line, < 8 queries in any canonical bucket, judgments referencing unknown `verse_id`, grade outside `{1, 2}`.

#### Design notes

- **One module per CLI subcommand.** Considered a single `commands.py` with every verb. Rejected: each command carries its own ADR-007 help-text block, its own flag surface, and its own output schema; colocating six unrelated schemas in one file would guarantee merge friction. One-verb-one-file is the affinity cut.
- **`query_log.py` lives in `scripvec_cli/`, not `packages/retrieval/`.** Logging is a CLI-boundary concern (who ran the command, when) — an importer of `retrieval.query()` as a library should not get a side-effectful file-append. Pushed up; not down.
- **Embed config is its own file, not inlined in `embed.py`.** Two callers read it: `embed.py` (every request) and `query.py` (the endpoint-drift guard compares runtime config to the stored manifest). Inlining would force `query` to reach through an unrelated module for the drift check. Separate file, narrow surface.
- **`build.py` and `query.py` are separate, despite both orchestrating retrieval.** Build is write-path, runs minutes, mutates the filesystem and flips the symlink. Query is read-path, runs sub-second, side-effect-free except for the log. Orthogonal change reasons; fusing would be pure temporal decomposition.
- **`tokenizer.py` and `hashing.py` extracted from their sole callers.** Both are short (~6 lines and ~4 lines respectively); colocating with `bm25.py` / `manifest.py` would have been Ousterhout-default-classitis-avoidance. Engineer chose to split them out for testability — both are pure functions with crisp input / output that benefit from direct unit tests, and a future tokenization or hash-algorithm change touches one file only.
- **`bcbooks.py` holds both BoM and D&C readers.** Considered `bom.py` + `dnc.py`. Rejected: they walk the same conceptual JSON shape and will change together if the bcbooks export format moves. One module, two private walkers, one public `iter_verses`.
- **`version_cmd.py` gets its own file despite being small.** ADR-007 makes `--version` a machine contract; its JSON shape is part of the CLI's versioned surface. Small-but-load-bearing.
- **CLI entry point is `main.py` exporting `app: typer.Typer`, no wrapper function, no `__main__.py`.** Matches the existing console script `scripvec = "scripvec_cli.main:app"` in `apps/scripvec_cli/pyproject.toml`. Typer apps are callable, so a wrapper `main()` would be a pass-through. `python -m scripvec_cli` is not part of CR-002's surface; not added.
- **Sanity probes live in `dataset.py` as a module-level constant.** They are a contract the harness enforces (CR-002), not data a human edits — code-side keeps them next to the loader that enforces them, with no extra file or loader path.

### Function plan

Comprehensive function-level realization of the file blueprint above. Every function in every file gets a contract — preconditions, postconditions, raises, calls — plus the full file-level dependency graph and per-package boundary contracts. Generated by channeling John Ousterhout against this CR plus ADRs 001, 002, 005, 006, 007. Interface comments are part of the design: where a contract here is awkward, the interface is wrong, not the contract.

#### 1. Per-file function plans

Listed leaves first, joiners last. Within each file, public surface before private helpers.

---

##### `packages/reference/src/scripvec_reference/books.py`

**`canonicalize_book(raw: str) -> str`** [public]
- **Hides / role:** the canonical-name table itself — every spelling and abbreviation that shows up in `data/raw/bcbooks/*.json` collapses to one pinned string. Callers never see the variants.
- **Pre:** `raw` is a non-empty string (whitespace not stripped — that's this function's job).
- **Post:** returns a string that appears in `CANONICAL_BOOKS`.
- **Raises:** `ValueError` if `raw` (after strip + case-insensitive lookup) is not a known BoM book name nor `D&C` (ADR-001 — unknown book is a real bug, not a default).
- **Calls:** intra-module `_NAME_TABLE` lookup only.

**`CANONICAL_BOOKS: tuple[str, ...]`** [public, module constant]
- The pinned canonical book list, in the deterministic ordering used to walk the corpus (BoM order: 1 Nephi → Moroni; then `D&C`).
- **Invariants:** order matches the canonical scriptural ordering; entries are unique; matches `_NAME_TABLE.values()` set.

**`_NAME_TABLE: dict[str, str]`** [private, module constant]
- Lookup table from lowercased / stripped variant → canonical name. Keys include every form present in the bcbooks JSON.

---

##### `packages/reference/src/scripvec_reference/reference.py`

**`@dataclass(frozen=True) class Reference`** [public]
- Fields: `book: str` (must equal `canonicalize_book(book)`); `chapter: int` (≥ 1); `verse: int` (≥ 1).
- Invariants: `book ∈ CANONICAL_BOOKS`; chapter and verse are positive.

**`parse_reference(s: str) -> Reference`** [public]
- **Hides / role:** the citation grammar — the `"<Book> <chapter>:<verse>"` shape including books with leading numerals (`1 Nephi`) and the `D&C` abbreviation. The only file that knows references look like strings.
- **Pre:** `s` is a string.
- **Post:** returns a `Reference` whose fields satisfy the dataclass invariants.
- **Raises:** `ValueError` on empty / malformed input (no `:`, non-integer chapter/verse, missing book token); `ValueError` propagated from `canonicalize_book` on unknown book.
- **Calls:** `books.canonicalize_book`, intra-module `_split_book_and_loc`.

**`canonical(book: str, chapter: int, verse: int) -> str`** [public]
- **Hides / role:** the pinned reference-string format. Round-trips with `parse_reference`.
- **Pre:** `chapter ≥ 1` and `verse ≥ 1`; `book` may be any spelling.
- **Post:** returns `"{canonical_book} {chapter}:{verse}"`.
- **Raises:** `ValueError` from `canonicalize_book`; `ValueError` if chapter or verse < 1.
- **Calls:** `books.canonicalize_book`.

**`_split_book_and_loc(s: str) -> tuple[str, str]`** [private]
- **Hides / role:** the lexical trick that the *last* whitespace-separated token in `s` is the `chapter:verse` locator and everything before it is the book — needed so `"1 Nephi 3:7"` splits as `("1 Nephi", "3:7")`.
- **Pre:** `s` is a stripped non-empty string containing at least one space.
- **Post:** returns `(book_part, loc_part)` where `loc_part` contains exactly one `:`.
- **Raises:** `ValueError` if there is no space, or if the loc part does not match the `<int>:<int>` shape.
- **Calls:** none.

---

##### `packages/corpus_ingest/src/scripvec_corpus_ingest/verse.py`

**`@dataclass(frozen=True) class VerseRecord`** [public]
- Fields: `verse_id: str` (deterministic, stable across builds); `ref_canonical: str`; `book: str`; `chapter: int`; `verse: int`; `text: str`.
- Invariants: `verse_id == make_verse_id(ref_canonical)`; `ref_canonical == reference.canonical(book, chapter, verse)`; `text` is non-empty (whitespace-trimmed).

**`make_verse_id(ref_canonical: str) -> str`** [public]
- **Hides / role:** the derivation of `verse_id` from the canonical reference. One file owns this so a future change to the id scheme touches one place. Chosen scheme: a stable slug — lowercase, replace ` `/`:` with `-`, replace `&` with `and` — so ids stay human-readable in logs (`1-nephi-3-7`, `dandc-88-118`). Considered hashing; rejected because human-grep-ability of logs and judgments files is high-value at MVP scale and the scheme is trivial to swap if the slug ever collides.
- **Pre:** `ref_canonical` is in the form produced by `reference.canonical`.
- **Post:** returns a non-empty ASCII string with no whitespace and no SQL-hostile characters.
- **Raises:** `ValueError` if input is empty.
- **Calls:** none.

---

##### `packages/retrieval/src/scripvec_retrieval/config.py`

**`@dataclass(frozen=True) class EmbedConfig`** [public]
- Fields: `base_url: str`; `api_key: str`; `model: str`; `dim: int`.
- Invariants: `base_url` is non-empty and not whitespace; `api_key` is non-empty (token may be a placeholder per ADR-005, but never empty); `model` is non-empty; `dim ≥ 1`.

**`load_embed_config() -> EmbedConfig`** [public]
- **Hides / role:** the precedence between environment variables and the optional non-committed config file (ADR-005). Callers get a fully resolved object; nobody else reads env vars or hunts for config files. Values come from env first; a non-committed config file is an optional second source. Considered passing a path argument; rejected — every caller would default it the same way, and the decision belongs inside the module (push complexity down).
- **Pre:** none.
- **Post:** returns a fully populated `EmbedConfig` whose invariants hold.
- **Raises:** `RuntimeError` if `OPENAI_BASE_URL`, `OPENAI_API_KEY`, model identifier, or dim cannot be resolved (ADR-001 — unconfigured is not a default-able state).
- **Calls:** intra-module `_read_optional_config_file`.

**`_read_optional_config_file() -> dict[str, str]`** [private]
- **Hides / role:** the existence and location of the optional non-committed config file. Returns an empty dict if no file is present; raises only on a corrupted file.
- **Pre:** none.
- **Post:** returns a dict (possibly empty) of string → string overrides.
- **Raises:** `RuntimeError` if a config file exists but is not parseable.
- **Calls:** none.

---

##### `packages/retrieval/src/scripvec_retrieval/paths.py`

**`data_dir() -> Path`** [public]
- **Hides / role:** the `SCRIPVEC_DATA_DIR` env override and the default `./data/`. Every other path-returning function in this module composes from this.
- **Pre:** none.
- **Post:** returns an absolute `Path`. Does not require the directory to exist.
- **Raises:** none.
- **Calls:** none.

**`raw_dir() -> Path`** [public]
- Returns `data_dir() / "raw"`. **Calls:** `data_dir`.

**`eval_dir() -> Path`** [public]
- Returns `data_dir() / "eval"`. **Calls:** `data_dir`.

**`logs_dir() -> Path`** [public]
- Returns `data_dir() / "logs"`. **Calls:** `data_dir`.

**`indexes_dir() -> Path`** [public]
- Returns `data_dir() / "indexes"`. **Calls:** `data_dir`.

**`index_path(config_hash: str) -> Path`** [public]
- **Pre:** `config_hash` matches `^[0-9a-f]{32}$` (the BLAKE2b-128 hex shape).
- **Post:** returns `indexes_dir() / config_hash`. Does not require the directory to exist.
- **Raises:** `ValueError` if `config_hash` does not match the expected hex shape (ADR-001 — a malformed hash is an upstream bug, not something to silently sanitize).
- **Calls:** `indexes_dir`.

**`latest_symlink() -> Path`** [public]
- Returns `indexes_dir() / "latest"`. **Calls:** `indexes_dir`.

**`resolve_latest() -> str`** [public]
- **Hides / role:** the fact that "latest" is a symlink whose name-only is the active config hash. Callers say *"what's live?"* without learning that it's a symlink.
- **Pre:** none.
- **Post:** returns the 32-char hex hash that the `latest` symlink resolves to.
- **Raises:** `RuntimeError` if `latest` is missing or does not resolve to a directory matching the hash shape (ADR-001 — no silent fallback to "newest by mtime").
- **Calls:** `latest_symlink`, `indexes_dir`.

**`set_latest(config_hash: str) -> None`** [public]
- **Hides / role:** the atomic symlink-swap discipline: write a sibling symlink, then `os.replace` it onto the canonical name. The "only on success" guarantee in CR-002 is enforced by the build pipeline calling this only at the end; this function just makes the swap itself atomic.
- **Pre:** `index_path(config_hash)` exists and is a directory.
- **Post:** `latest_symlink()` resolves to `index_path(config_hash)`. The previous target (if any) is unlinked and never observed in a half-swapped state.
- **Raises:** `RuntimeError` if the index directory does not exist, or if the swap fails at the OS level; `ValueError` from `index_path` on bad hash.
- **Calls:** `index_path`, `latest_symlink`.

---

##### `packages/retrieval/src/scripvec_retrieval/embed.py`

**`embed(text: str) -> list[float]`** [public — the ADR-006 single sanctioned entry point]
- **Hides / role:** the wire format of the OpenAI-compatible `/embeddings` endpoint, the 8K-token pre-check, the dim-mismatch assertion, the client-side L2 normalization, and the serial-only constraint. Replacing the protocol or moving to a different provider touches only this file. Synchronous, blocking, no async / batch / retry surface — ADR-006.
- **Pre:** `text` is a string. (Empty is allowed at the type level; the endpoint will reject it and raise via the HTTP path. Considered pre-rejecting empty here; rejected — the endpoint is the source of truth on what's a valid input.)
- **Post:** returns a `list[float]` of length `EmbedConfig.dim` whose L2 norm is 1.0 (within float tolerance).
- **Raises:**
  - `RuntimeError` if `_estimate_token_count(text) > 8000` — input rejected before the HTTP request, message includes observed estimate (ADR-005 — no silent truncation).
  - `RuntimeError` on any non-2xx HTTP response, message includes status and response body (ADR-005, ADR-001 — no retry).
  - `RuntimeError` if `len(embedding) != dim`, message includes both observed and expected dims (ADR-005 validation clause).
  - `RuntimeError` from `config.load_embed_config` if config is missing.
  - `RuntimeError` if response JSON is malformed (no `data[0].embedding`).
- **Calls:** `config.load_embed_config`, `_estimate_token_count`, `_post_embedding`, `_l2_normalize`, `httpx.post` (third-party).
- **Invariants:** never holds more than one in-flight HTTP request to the endpoint (ADR-006 — guaranteed by the synchronous call shape; no executors / no asyncio).

**`_estimate_token_count(text: str) -> int`** [private]
- **Hides / role:** the 8K-token gate's estimator. ADR-005 says reject "any text that *may* exceed" 8K — so a conservative estimate (e.g., `max(len(text) // 4, len(text.split()))`) is correct; precision is not. Documented as a conservative upper-bound estimator so callers never expect exact tokenization.
- **Pre:** `text` is a string.
- **Post:** returns a non-negative integer that is ≥ the true token count for any reasonable tokenizer (chosen as `max(ceil(len(text) / 3), word_count)` — char-based path catches dense-byte texts; word-based catches verbose-whitespace texts).
- **Raises:** none.
- **Calls:** none.

**`_post_embedding(cfg: EmbedConfig, text: str) -> list[float]`** [private]
- **Hides / role:** the actual POST and the JSON-shape parse. Lifted out of `embed` only so the wrong-length test in `test_embed.py` can mock `httpx.post` cleanly through this seam; otherwise this would inline. Considered absorbing back into `embed`; kept separate because the test file lives next door and the seam is load-bearing for the ADR-005 validation test.
- **Pre:** `cfg` invariants hold.
- **Post:** returns the raw (un-normalized) `list[float]` from `data[0].embedding`.
- **Raises:** `RuntimeError` on non-2xx, on missing `data[0].embedding`, on connection error.
- **Calls:** `httpx.post` (third-party).

**`_l2_normalize(vec: list[float]) -> list[float]`** [private]
- **Hides / role:** the client-side L2 normalization (ADR-005). Pure math; one place owns the formula.
- **Pre:** `vec` is non-empty.
- **Post:** returns a list of the same length whose L2 norm is 1.0 (within float tolerance).
- **Raises:** `RuntimeError` if `||vec||₂ == 0` (a zero-vector embedding is upstream pathology, ADR-001 — do not silently return zeros).
- **Calls:** `numpy` (third-party).

---

##### `packages/retrieval/src/scripvec_retrieval/test_embed.py`

**`def test_embed_raises_on_wrong_length_response()`** [test]
- ADR-005 validation clause. Mocks `_post_embedding` (or `httpx.post`) to return a vector whose length differs from configured dim; asserts `RuntimeError` is raised and that the message contains both the observed and the expected dim.

**`def test_embed_raises_on_oversized_input()`** [test]
- Asserts `embed` raises `RuntimeError` for a text whose `_estimate_token_count` is > 8000, *without* making any HTTP call (verified by mocking `httpx.post` and asserting it was never called).

**`def test_embed_raises_on_non_2xx()`** [test]
- Mocks `httpx.post` to return a 500; asserts `RuntimeError` with status code in the message; no retry was attempted.

**`def test_embed_returns_normalized_vector_of_correct_dim()`** [test]
- Mocks the endpoint to return a known-non-unit vector; asserts the returned vector has length `dim` and L2 norm 1.0 (within 1e-6).

---

##### `packages/retrieval/src/scripvec_retrieval/hashing.py`

**`canonical_json(obj: object) -> bytes`** [public]
- **Hides / role:** the "canonical" JSON serialization that backs the index hash — sorted keys, no whitespace, UTF-8. One place defines it so the hash stays stable across Python versions and platforms.
- **Pre:** `obj` is JSON-serializable.
- **Post:** returns UTF-8 bytes; identical inputs always produce identical bytes.
- **Raises:** `TypeError` from `json.dumps` if `obj` contains non-serializable values (ADR-001 — bubbles up).
- **Calls:** none.

**`blake2b_128_hex(payload: bytes) -> str`** [public]
- **Hides / role:** the BLAKE2b-128 hash primitive, isolated so a future change to the hash algorithm touches one file.
- **Pre:** `payload` is `bytes`.
- **Post:** returns a 32-character lowercase hex string.
- **Raises:** none.
- **Calls:** `hashlib.blake2b` (stdlib).

---

##### `packages/retrieval/src/scripvec_retrieval/tokenizer.py`

**`tokenize(text: str) -> list[str]`** [public]
- **Hides / role:** the BM25 tokenization rules — lowercase → Unicode NFC normalize → split on `\W+` → drop empties → drop pure-digit tokens shorter than 2 characters; stopwords off (CR-002). Pure function. The one place a future tokenization change happens.
- **Pre:** `text` is a string.
- **Post:** returns a list of non-empty lowercase tokens.
- **Raises:** none.
- **Calls:** `unicodedata.normalize`, `re.split` (stdlib).
- **Invariants:** deterministic — same input always yields same output.

---

##### `packages/retrieval/src/scripvec_retrieval/rrf.py`

**`rrf(bm25_hits: Sequence[tuple[str, float]], dense_hits: Sequence[tuple[str, float]], *, k: int = 60, top_k: int = 10) -> list[tuple[str, float]]`** [public]
- **Hides / role:** the Reciprocal Rank Fusion formula `score(d) = Σ 1/(k + rank_i(d))` with deterministic tiebreak by `verse_id` ascending (ADR-007). Pure math, no I/O. The one decision that changes if we ever try a different fusion.
- **Pre:** each input list is in rank order (best first); each `verse_id` appears at most once within a list; `k ≥ 1`; `top_k ≥ 1`.
- **Post:** returns up to `top_k` `(verse_id, rrf_score)` pairs sorted by `rrf_score` desc, ties broken by `verse_id` ascending.
- **Raises:** `ValueError` on `k < 1` or `top_k < 1`.
- **Calls:** none.

---

##### `packages/corpus_ingest/src/scripvec_corpus_ingest/bcbooks.py`

**`iter_verses(data_dir: Path) -> Iterator[VerseRecord]`** [public]
- **Hides / role:** the JSON shape of the bcbooks export — `books[].chapters[].verses[]` for the Book of Mormon, the (slightly different) shape of D&C. Callers walk verses in deterministic canonical order without ever opening a JSON file. One module because both readers walk the same conceptual tree and will move together if the bcbooks export format moves.
- **Pre:** `data_dir / "raw" / "bcbooks" / "book-of-mormon.json"` and `.../doctrine-and-covenants.json` exist and parse as JSON.
- **Post:** yields every BoM verse then every D&C verse in canonical book order, chapter ascending, verse ascending. All `VerseRecord` invariants hold for every yielded record.
- **Raises:**
  - `FileNotFoundError` if either JSON is missing.
  - `ValueError` if a JSON shape does not match the expected schema (missing `books` / `chapters` / `verses` keys, missing text, non-int chapter/verse).
  - `ValueError` from `reference.canonicalize_book` on an unknown book name.
- **Calls:** `_iter_book_of_mormon`, `_iter_doctrine_and_covenants`, `verse.make_verse_id`, `reference.canonical`.

**`corpus_commit_sha(data_dir: Path) -> str`** [public]
- **Hides / role:** the fact that "the corpus version" is the git commit SHA of `data/raw/bcbooks/`. Used by the corpus-drift guard. One place owns this, so a switch to a content-hash scheme later touches one file.
- **Pre:** `data_dir / "raw" / "bcbooks"` exists; the surrounding repo is a git checkout (which it is per the project layout).
- **Post:** returns the short or full git commit SHA of the most recent commit touching `data/raw/bcbooks/`.
- **Raises:** `RuntimeError` if `git` is unavailable, the path is not in a repo, or no commit touches the path (ADR-001 — unknowable provenance is a real failure).
- **Calls:** `subprocess.run` (stdlib).

**`_iter_book_of_mormon(path: Path) -> Iterator[VerseRecord]`** [private]
- Walks the BoM JSON tree; yields `VerseRecord`s in canonical order.
- **Pre:** `path` exists.
- **Post:** every yielded record satisfies `VerseRecord` invariants.
- **Raises:** `ValueError` on shape mismatch.
- **Calls:** `verse.make_verse_id`, `reference.canonical`, `reference.canonicalize_book`.

**`_iter_doctrine_and_covenants(path: Path) -> Iterator[VerseRecord]`** [private]
- Same contract as `_iter_book_of_mormon`, for the D&C JSON shape.
- **Calls:** `verse.make_verse_id`, `reference.canonical`.

---

##### `packages/retrieval/src/scripvec_retrieval/manifest.py`

**`@dataclass(frozen=True) class Manifest`** [public]
- Fields:
  - `corpus_source: str` (e.g., `"bcbooks"`) — names the upstream corpus.
  - `corpus_commit_sha: str` — drift-guard reference for `data/raw/bcbooks/`.
  - `tokenizer_version: str` — bump this when `tokenizer.tokenize` changes.
  - `embed_endpoint: str` — `EmbedConfig.base_url`.
  - `embed_model: str` — `EmbedConfig.model`.
  - `embed_dim: int` — `EmbedConfig.dim`.
  - `embed_normalized: bool` — always `True` at MVP (ADR-005), but explicit so a future endpoint that returns pre-normalized vectors can be detected.
  - `bm25_lib: str` (`"bm25s"`).
  - `bm25_lib_version: str`.
  - `bm25_k1: float` (`1.5`).
  - `bm25_b: float` (`0.75`).
  - `vec_schema_version: str` — bump if the `verses` table or `vec0` shape changes.
- Invariants: every field is non-empty / positive. The hash is a pure function of these fields.

**`config_hash(m: Manifest) -> str`** [public]
- **Hides / role:** composes `hashing.canonical_json` and `hashing.blake2b_128_hex`. One place names the hash.
- **Pre:** `m`'s invariants hold.
- **Post:** returns a 32-char hex string. Identical manifests always produce identical hashes.
- **Raises:** none.
- **Calls:** `hashing.canonical_json`, `hashing.blake2b_128_hex`, `dataclasses.asdict`.

**`write_manifest(m: Manifest, path: Path) -> None`** [public]
- **Hides / role:** the on-disk JSON form of the manifest. Atomic write (write-temp-then-replace) so a crashed build never leaves a half-written `config.json` behind.
- **Pre:** `path.parent` exists.
- **Post:** `path` exists and `read_manifest(path) == m`.
- **Raises:** `OSError` from the filesystem.
- **Calls:** `dataclasses.asdict`, `hashing.canonical_json`.

**`read_manifest(path: Path) -> Manifest`** [public]
- **Hides / role:** the parser for the on-disk form. Strict — extra or missing fields are a real disagreement, not an upgrade ladder.
- **Pre:** `path` exists.
- **Post:** returns a `Manifest` equal to the one originally written.
- **Raises:** `RuntimeError` if the file is missing required fields, has unknown fields, or fails type checks (ADR-001 — manifest drift is the bug we wrote this guard to catch).
- **Calls:** none.

---

##### `packages/retrieval/src/scripvec_retrieval/store.py`

**`@dataclass class StoreConn`** [public, opaque-ish]
- Fields: `conn: sqlite3.Connection` (the underlying connection with `sqlite-vec` loaded). Single field so future additions (cached statements, schema version) don't break callers.

**`@dataclass(frozen=True) class DenseHit`** [public]
- Fields: `verse_id: str`; `rowid: int`; `cosine: float`; `record: VerseRecord`.
- Invariants: `cosine ∈ [-1.0, 1.0]` (computed as inner product over L2-normalized vectors per ADR-005 — for unit vectors, inner product **is** cosine similarity; the field is named for the semantic, not the implementation); `record.verse_id == verse_id`.

**`open_store(path: Path, *, create: bool = False) -> StoreConn`** [public]
- **Hides / role:** the `sqlite3` open + `sqlite-vec` extension load + (when `create=True`) the schema DDL for the `verses` sibling table and the `vec0` virtual table typed `float[1024]`. Callers never see SQL. The 1024 is read from `EmbedConfig.dim`, not hardcoded.
- **Pre:** `path.parent` exists; if `create=False`, `path` is an existing valid store; if `create=True`, the schema creation may overwrite an empty file but will not clobber an existing populated one.
- **Post:** returns a `StoreConn` whose extension is loaded and (if `create=True`) whose schema exists.
- **Raises:** `RuntimeError` if `sqlite-vec` cannot be loaded; `RuntimeError` if `create=False` and the file does not have the expected schema; `RuntimeError` if `create=True` and the file already contains a different-dim `vec0` (ADR-001 — silent dim drift here would be catastrophic).
- **Calls:** `sqlite3.connect`, `sqlite_vec.load` (third-party), `config.load_embed_config` (for `dim` when creating).

**`insert_batch(conn: StoreConn, rows: Iterable[tuple[VerseRecord, list[float]]]) -> None`** [public]
- **Hides / role:** the transactional batching — `verses` row + `vec0` row written in the same SQL transaction, keyed by the same rowid (CR-002). One transaction per call. ADR-001's "one step fails, whole thing rolls back" is enforced here.
- **Pre:** for each `(verse, vec)`, `len(vec) == dim` and `||vec||₂ ≈ 1.0`.
- **Post:** every `(verse, vec)` is persisted; `verses.rowid` matches the `vec0` rowid for the same record. Either all rows in this call land or none do.
- **Raises:** `RuntimeError` on dim mismatch (any vec); `sqlite3.Error` on SQL failures (transaction is rolled back before re-raising).
- **Calls:** none external.

**`dense_topk(conn: StoreConn, query_vec: list[float], k: int = 50) -> list[DenseHit]`** [public]
- **Hides / role:** the SQL that joins `vec0` (top-k by cosine similarity — computed as inner product over the L2-normalized `query_vec` and the L2-normalized stored vectors per ADR-005) to `verses` in one statement, returning fully-populated `DenseHit`s. Callers never see SQL or rowids; the inner-product implementation is hidden behind the cosine-named contract.
- **Pre:** `len(query_vec) == dim`; `||query_vec||₂ ≈ 1.0`; `k ≥ 1`.
- **Post:** returns a list of up to `k` `DenseHit`s sorted by `cosine` desc; each `record` is fully populated from `verses`.
- **Raises:** `RuntimeError` on dim mismatch; `sqlite3.Error` on SQL failures.
- **Calls:** none external.

**`get_verse(conn: StoreConn, verse_id: str) -> VerseRecord`** [public]
- **Hides / role:** the single-verse lookup by `verse_id`. Used by the query path when assembling output rows where only `verse_id` is in hand (e.g., from BM25 or from RRF after fusion). Considered exposing a raw "fetch by rowid" too; rejected — `verse_id` is the public id, rowids are an implementation detail.
- **Pre:** `verse_id` is a string.
- **Post:** returns the matching `VerseRecord`.
- **Raises:** `RuntimeError` if no row matches (ADR-001 — a missing verse_id is a real bug, not a default-able state).
- **Calls:** none external.

---

##### `packages/retrieval/src/scripvec_retrieval/bm25.py`

**`@dataclass class Bm25Index`** [public, opaque]
- Fields: the live `bm25s.BM25` retriever and the in-memory `verse_id` corpus mapping (so `bm25_topk` can return `(verse_id, score)` without the caller ever seeing rowids or the underlying retriever).
- Invariants: corpus mapping is index-aligned with the retriever's internal corpus order.

**`build_bm25(verses: Sequence[VerseRecord], index_dir: Path) -> None`** [public]
- **Hides / role:** the choice of `BM25S` as the underlying library, the `k1=1.5, b=0.75` parameters (CR-002), and the on-disk format under `index_dir`. Tokenization is delegated to `tokenizer.tokenize`. A future swap to FTS5 / `rank_bm25` lives entirely in this file.
- **Pre:** `verses` is non-empty; `index_dir` exists and is writable.
- **Post:** `index_dir` contains `bm25.bm25s` (the BM25S native on-disk format) plus a sidecar `verse_ids.json` mapping internal ordinal → `verse_id`.
- **Raises:** `RuntimeError` on empty corpus; `OSError` on filesystem error.
- **Calls:** `tokenizer.tokenize`, `bm25s` (third-party).

**`load_bm25(index_dir: Path) -> Bm25Index`** [public]
- **Hides / role:** the on-disk → in-memory load. Strict — missing or version-mismatched files raise.
- **Pre:** `index_dir` exists.
- **Post:** returns a `Bm25Index` ready for `bm25_topk`.
- **Raises:** `RuntimeError` if the on-disk format is missing or unreadable.
- **Calls:** `bm25s` (third-party).

**`bm25_topk(idx: Bm25Index, query: str, k: int = 50) -> list[tuple[str, float]]`** [public]
- **Hides / role:** tokenization-of-query + BM25 scoring + mapping internal ordinals → `verse_id`. Caller sees `(verse_id, score)`.
- **Pre:** `k ≥ 1`. `query` is a string (empty allowed; returns empty list per BM25S behavior — that's a feature, an empty query is a degenerate-but-valid case).
- **Post:** returns up to `k` `(verse_id, score)` pairs sorted by `score` desc, ties broken by `verse_id` ascending (deterministic per ADR-007).
- **Raises:** `ValueError` on `k < 1`.
- **Calls:** `tokenizer.tokenize`, `bm25s` (third-party).

---

##### `packages/retrieval/src/scripvec_retrieval/build.py`

**`build_index(*, from_scratch: bool = True, rebuild_corpus: bool = False) -> str`** [public]
- **Hides / role:** the full ingest → embed → persist → BM25 → manifest → symlink-flip sequence. Callers say "build"; they don't see the steps. The corpus-drift guard, the per-batch transactional discipline, and the "symlink only flips on success" rule (CR-002, ADR-001) are all internal here.
- **Pre:** corpus files exist under `paths.raw_dir()`; embed endpoint is reachable; embed config resolves.
- **Post:** returns the new `config_hash`; `paths.index_path(hash)` contains `corpus.sqlite`, `bm25.bm25s`, `config.json`; `paths.latest_symlink()` points to it.
- **Raises:**
  - `RuntimeError` if `from_scratch=False` and incremental builds are not yet implemented (MVP supports `--from-scratch` only — be explicit, not silent).
  - `RuntimeError` from the corpus-drift guard if `corpus.commit_sha` disagrees with `data/raw/` and `rebuild_corpus=False`.
  - Anything raised by `embed`, `store.insert_batch`, `bm25.build_bm25`, `manifest.write_manifest`, `paths.set_latest`, `iter_verses`.
- **Calls:** `_assemble_manifest`, `corpus_ingest.iter_verses`, `corpus_ingest.corpus_commit_sha`, `embed.embed`, `store.open_store`, `store.insert_batch`, `bm25.build_bm25`, `manifest.config_hash`, `manifest.write_manifest`, `paths.indexes_dir`, `paths.index_path`, `paths.set_latest`, `config.load_embed_config`, `_drift_check_corpus`.
- **Invariants:**
  - **Atomic publish:** `paths.set_latest` is called only on the final success path; partial builds leave a directory under `indexes_dir()` but never repoint `latest`.
  - **Serial embedding:** `embed.embed` is called in a plain Python loop, never under `ThreadPoolExecutor` / `asyncio.gather` (ADR-006). Verified by code review, not by mechanism.

**`_assemble_manifest(cfg: EmbedConfig, commit_sha: str) -> Manifest`** [private]
- **Hides / role:** the assembly of every field that goes into the manifest, pulling versions from the imported libraries. One place to update when a new field is added to `Manifest`.
- **Pre:** `cfg` invariants hold.
- **Post:** returns a fully-populated `Manifest`.
- **Raises:** `RuntimeError` if a library version cannot be detected.
- **Calls:** `importlib.metadata.version` (stdlib).

**`_drift_check_corpus(stored_commit: str | None, observed_commit: str, rebuild_corpus: bool) -> None`** [private]
- **Hides / role:** the corpus-drift guard logic (CR-002, ADR-001). On a from-scratch build there's no stored commit to compare against — that's a no-op. On a rebuild, the commits must match unless `rebuild_corpus=True`.
- **Pre:** none.
- **Post:** returns silently when no drift, or when drift is explicitly accepted.
- **Raises:** `RuntimeError` if commits disagree and `rebuild_corpus=False`. Message names both commits.
- **Calls:** none.

---

##### `packages/retrieval/src/scripvec_retrieval/query.py`

**`@dataclass(frozen=True) class QueryResult`** [public]
- Fields exactly per CR-002 query output schema:
  - `query: str`
  - `mode: str` (one of `"bm25"`, `"dense"`, `"hybrid"`)
  - `k: int`
  - `index: str` (the resolved config hash, never the literal string `"latest"`)
  - `results: tuple[ResultRow, ...]`
  - `latency_ms: dict[str, float]` with keys `"bm25"`, `"dense"`, `"fuse"`, `"total"`; absent stages are present with value `0.0` so the schema is stable across modes.

**`@dataclass(frozen=True) class ResultRow`** [public]
- Fields exactly per CR-002:
  - `rank: int` (1-based)
  - `verse_id: str`
  - `ref: str` (canonical reference)
  - `text: str` (verse text)
  - `score: float` (the headline score for the chosen mode — RRF score for `hybrid`, BM25 score for `bm25`, cosine similarity for `dense`)
  - `scores: dict[str, float | None]` with keys `"bm25"`, `"dense"`, `"rrf"`; components not computed in this mode are `None`.

**`query(text: str, *, k: int = 10, mode: str = "hybrid", index: str = "latest") -> QueryResult`** [public]
- **Hides / role:** the read-path orchestration — manifest load, endpoint-drift guard, mode dispatch, latency capture, rowid → verses join, output assembly. Callers say *"give me top-k for this query"*; they don't see retrieval mechanics. Hybrid is `bm25_topk + dense_topk + rrf` in sequence; `bm25` and `dense` are the components called alone for eval and debugging (CR-002).
- **Pre:** `text` is a string; `k ≥ 1`; `mode ∈ {"bm25", "dense", "hybrid"}`; `index` is `"latest"` or matches `^[0-9a-f]{32}$`.
- **Post:** returns a `QueryResult` whose `results` are sorted by `rank` ascending, with `rank` 1-based and contiguous, ties broken by `verse_id` ascending (ADR-007). `latency_ms.total` is the wall time spanning mode dispatch through results assembly.
- **Raises:**
  - `ValueError` on invalid `mode`, `k < 1`, or malformed `index`.
  - `RuntimeError` if the requested `index` directory does not exist (CLI maps to exit code 2).
  - `RuntimeError` from the endpoint-drift guard (CLI maps to exit code 3).
  - `RuntimeError` propagated from `embed.embed` (HTTP / token-cap / dim).
- **Calls:** `_resolve_index`, `_drift_check_endpoint`, `_run_bm25`, `_run_dense`, `rrf.rrf`, `store.open_store`, `store.get_verse`, `bm25.load_bm25`, `manifest.read_manifest`, `paths.index_path`, `paths.resolve_latest`, `embed.embed`, `config.load_embed_config`.

**`_resolve_index(index: str) -> tuple[str, Path]`** [private]
- **Hides / role:** turns `"latest"` (or a hash) into `(hash, dir)`. The one place that handles the symlink-vs-hash distinction.
- **Pre:** `index` is `"latest"` or a 32-char hex hash.
- **Post:** returns `(config_hash, index_path)`; `index_path` exists.
- **Raises:** `RuntimeError` if `latest` is missing or a given hash directory does not exist; `ValueError` on malformed input (delegated to `paths.index_path`).
- **Calls:** `paths.resolve_latest`, `paths.index_path`.

**`_drift_check_endpoint(stored: Manifest, runtime: EmbedConfig) -> None`** [private]
- **Hides / role:** the endpoint-drift guard (CR-002, ADR-001). Compares the manifest's stored endpoint URL, model identifier, and dim against the runtime `EmbedConfig`. Raises on any mismatch with all three values in the message.
- **Pre:** `stored` and `runtime` are both populated.
- **Post:** returns silently if all three match.
- **Raises:** `RuntimeError` on any mismatch — message names which field disagreed and both values. (CLI maps to exit code 3.)
- **Calls:** none.

**`_run_bm25(idx: Bm25Index, query_text: str, k_per_arm: int) -> tuple[list[tuple[str, float]], float]`** [private]
- Returns `(hits, latency_ms)`. Wraps `bm25.bm25_topk` with timing. Lifted out so the orchestration body stays readable.
- **Calls:** `bm25.bm25_topk`.

**`_run_dense(conn: StoreConn, query_text: str, k_per_arm: int) -> tuple[list[DenseHit], float, float]`** [private]
- Returns `(hits, embed_latency_ms, search_latency_ms)`. Wraps `embed.embed` + `store.dense_topk` with timing — embed time and search time are reported together under `latency_ms.dense` per CR-002, but split inside this helper so a future telemetry split is one line.
- **Calls:** `embed.embed`, `store.dense_topk`.

**Design-it-twice note:** considered making `mode` an enum and dispatching on object methods. Rejected — three modes, all exercised by both eval and the CLI, and the `str` is the wire representation in CR-002's JSON output schema. An enum would force converters at every boundary for no information-hiding gain.

---

##### `packages/eval/src/scripvec_eval/dataset.py`

**`@dataclass(frozen=True) class QueryRow`** [public]
- Fields: `query_id: str`; `query: str`; `tags: tuple[str, ...]`; `notes: str | None`.
- Invariants: `query_id` is non-empty and unique within the loaded set; `query` is non-empty after strip; `tags` is non-empty; `tags` contains at least one of the four canonical buckets (`"doctrinal"`, `"narrative"`, `"phrase-memory"`, `"proper-noun"`).

**`@dataclass(frozen=True) class Judgment`** [public]
- Fields: `query_id: str`; `verse_id: str`; `grade: int` (1 or 2 only; 0 = absent from file).
- Invariants: `grade ∈ {1, 2}`.

**`SANITY_PROBES: tuple[SanityProbe, ...]`** [public, module constant]
- Three pinned probes (CR-002), inlined here because they are a contract the harness enforces, not data a human edits. Each probe: `query: str` plus `expected_top3: tuple[str, ...]` of `verse_id`s. The actual probe contents are filled in by the engineer at authoring time against the real corpus — the constant exists; the values are an authoring task in System 9.

**`@dataclass(frozen=True) class SanityProbe`** [public]
- Fields: `query: str`; `expected_top3: tuple[str, ...]`.

**`load_queries(path: Path) -> list[QueryRow]`** [public]
- **Hides / role:** the JSONL parser, the duplicate-string check, the malformed-row check, and the ≥8-per-bucket assertion. Callers get a validated list or a loud error.
- **Pre:** `path` exists.
- **Post:** returns a list of `QueryRow`s satisfying their invariants. The set has no duplicate `query` strings and no duplicate `query_id`s. Each of the four canonical buckets has ≥ 8 rows (CR-002).
- **Raises:**
  - `RuntimeError` on a malformed JSON line (line number in message).
  - `RuntimeError` on duplicate `query` text (both `query_id`s in message).
  - `RuntimeError` on duplicate `query_id`.
  - `RuntimeError` if any of the four canonical buckets has < 8 queries.
- **Calls:** `_parse_query_row`.

**`load_judgments(path: Path, known_verse_ids: set[str]) -> list[Judgment]`** [public]
- **Hides / role:** the JSONL parser, the unknown-verse-id check (every judgment must point at a real verse), the grade check.
- **Pre:** `path` exists; `known_verse_ids` is the full set of `verse_id`s in the live corpus.
- **Post:** returns the validated list of `Judgment`s.
- **Raises:**
  - `RuntimeError` on malformed JSON line.
  - `RuntimeError` on a `verse_id` not in `known_verse_ids` (CR-002 sanity check).
  - `RuntimeError` on a `grade` outside `{1, 2}`.
- **Calls:** `_parse_judgment_row`.

**`run_sanity_probes(idx: Bm25Index) -> None`** [public]
- **Hides / role:** the three pinned BM25-top-3 probes (CR-002). Fails loud if any probe's expected verse(s) do not appear in the BM25 top-3 for its query.
- **Pre:** `idx` is loaded.
- **Post:** returns silently when every probe passes.
- **Raises:** `RuntimeError` naming the failing probe and the actual top-3 returned (ADR-001 — silent BM25 regression is the failure mode this guard exists for).
- **Calls:** `bm25.bm25_topk`.

**`_parse_query_row(line: str, lineno: int) -> QueryRow`** [private]
- Parses one JSONL line into a `QueryRow`. Raises `RuntimeError` with line number on malformed input.

**`_parse_judgment_row(line: str, lineno: int) -> Judgment`** [private]
- Same shape as `_parse_query_row`, for `Judgment`.

---

##### `packages/eval/src/scripvec_eval/metrics.py`

**`recall_at_k(retrieved: Sequence[str], relevant: Mapping[str, int], k: int) -> float`** [public]
- **Hides / role:** the recall@k definition over graded relevance — a `verse_id` counts as relevant iff `relevant.get(vid, 0) > 0`. Considered counting only canonical (grade 2); rejected — recall is "did we find a relevant verse," and grade-1 is relevant by definition.
- **Pre:** `k ≥ 1`. `relevant` may be empty.
- **Post:** returns a float in `[0.0, 1.0]`. Returns `0.0` if `relevant` is empty.
- **Raises:** `ValueError` on `k < 1`.
- **Calls:** none.

**`ndcg_at_10(retrieved: Sequence[str], relevant: Mapping[str, int]) -> float`** [public]
- **Hides / role:** nDCG@10 with `gain(grade) = 2**grade - 1` (so grade-2 canonical contributes 3, grade-1 relevant contributes 1, grade-0 absent contributes 0). Standard formulation; one place owns it.
- **Pre:** none.
- **Post:** returns a float in `[0.0, 1.0]`. Returns `0.0` if `relevant` is empty.
- **Raises:** none.
- **Calls:** none.

**`mrr_at_10(retrieved: Sequence[str], relevant: Mapping[str, int]) -> float`** [public]
- **Hides / role:** MRR@10 over graded relevance — `1 / rank` of the first retrieved `verse_id` with grade > 0 within the top 10; `0.0` if none.
- **Pre:** none.
- **Post:** returns a float in `[0.0, 1.0]`.
- **Raises:** none.
- **Calls:** none.

**`percentile(samples: Sequence[float], p: float) -> float`** [public]
- **Hides / role:** the p50 / p95 latency computation. One implementation, used for every per-mode latency report.
- **Pre:** `samples` is non-empty; `0 ≤ p ≤ 100`.
- **Post:** returns a float; for a single sample returns that sample.
- **Raises:** `ValueError` on empty `samples` or out-of-range `p`.
- **Calls:** `numpy.percentile` (third-party).

---

##### `packages/eval/src/scripvec_eval/run.py`

**`@dataclass(frozen=True) class ShipCriteria`** [public]
- Fields:
  - `hybrid_beats_bm25_recall10: bool`
  - `dense_beats_bm25_recall10: bool`
  - `index_size_under_400mb: bool`
- Invariants: each flag corresponds 1:1 to a CR-002 ship criterion. Thresholds (5 pts, 400 MB) live as named constants in this file.

**`@dataclass(frozen=True) class ModeMetrics`** [public]
- Fields: `mode: str`; `recall_at_10: float`; `recall_at_20: float`; `ndcg_at_10: float`; `mrr_at_10: float`; `latency_p50_ms: float`; `latency_p95_ms: float`.

**`@dataclass(frozen=True) class EvalReport`** [public]
- Fields:
  - `index_hash: str`
  - `metrics: tuple[ModeMetrics, ...]` (one per mode in order `bm25`, `dense`, `hybrid`)
  - `recall10_by_bucket: dict[str, dict[str, float]]` — outer key is mode, inner key is tag bucket
  - `ship: ShipCriteria`
  - `failures_path: Path`

**`run(queries_path: Path, judgments_path: Path, *, index: str = "latest") -> EvalReport`** [public]
- **Hides / role:** the orchestration — load queries + judgments, run every query through every mode (`bm25`, `dense`, `hybrid`), capture latency samples, compute metrics, stratify recall@10 by bucket, evaluate each ship criterion, write `failures_<timestamp>.jsonl`, return the report. Ship-criterion thresholds (`HYBRID_VS_BM25_PCT = 5`, `DENSE_VS_BM25_PCT = 5`, `MAX_INDEX_BYTES = 400 * 1024 * 1024`) are module constants.
- **Pre:** corpus + index exist; `queries_path` and `judgments_path` exist.
- **Post:** returns a fully-populated `EvalReport`; `failures_<timestamp>.jsonl` is written under `paths.eval_dir()`.
- **Raises:** anything raised by `dataset.load_queries`, `dataset.load_judgments`, `dataset.run_sanity_probes`, `query.query`. ADR-001 — every failure surfaces.
- **Calls:** `dataset.load_queries`, `dataset.load_judgments`, `dataset.run_sanity_probes`, `query.query`, `metrics.recall_at_k`, `metrics.ndcg_at_10`, `metrics.mrr_at_10`, `metrics.percentile`, `bm25.load_bm25`, `store.open_store`, `paths.index_path`, `paths.eval_dir`, `_compute_ship`, `_write_failures`, `_index_dir_size_bytes`.

**`_compute_ship(metrics_by_mode: dict[str, ModeMetrics], index_size_bytes: int) -> ShipCriteria`** [private]
- Pure function; evaluates the three CR-002 criteria against the named module constants.
- **Pre:** `metrics_by_mode` has keys `"bm25"`, `"dense"`, `"hybrid"`.
- **Post:** returns `ShipCriteria`.
- **Calls:** none.

**`_write_failures(failed: list[FailureRow], out_path: Path) -> None`** [private]
- Writes `data/eval/failures_<timestamp>.jsonl` (one row per `recall@10 == 0` query, with the top-10 returned and the judged-relevant set per CR-002).

**`_index_dir_size_bytes(index_dir: Path) -> int`** [private]
- Recursive size of `index_dir`.

**`@dataclass(frozen=True) class FailureRow`** [private]
- Fields: `query_id: str`; `query: str`; `mode: str`; `top10: tuple[str, ...]`; `judged_relevant: tuple[str, ...]`.

---

##### `apps/scripvec_cli/src/scripvec_cli/errors.py`

**`class ExitCode`** [public, namespace of constants]
- `SUCCESS = 0`, `USER_ERROR = 1`, `NOT_FOUND = 2`, `UPSTREAM_ERROR = 3`. Exactly the table in CR-002 / ADR-007. No "general error" catch-all; each exit code is meaningful.

**`emit_error(code: str, message: str, details: dict | None = None, exit_code: int = ExitCode.USER_ERROR) -> NoReturn`** [public]
- **Hides / role:** the ADR-007 structured-error shape `{"error": {"code", "message", "details"}}`, the choice of stderr as its sink, and the `sys.exit` call. Every subcommand that fails goes through this single writer so the shape can't drift.
- **Pre:** `code` is a stable string per the calling subcommand's documented error table; `message` is human-readable.
- **Post:** writes one line of well-formed JSON to stderr; calls `sys.exit(exit_code)`. Does not return.
- **Raises:** does not return — raises `SystemExit`.
- **Calls:** `sys.stderr.write`, `sys.exit`, `json.dumps` (stdlib).

---

##### `apps/scripvec_cli/src/scripvec_cli/query_log.py`

**`@dataclass(frozen=True) class QueryLogRecord`** [public]
- Fields per CR-002:
  - `timestamp: str` (ISO-8601, UTC)
  - `schema_version: str` (constant `"1"`)
  - `session_id: str`
  - `query_id: str`
  - `index_hash: str`
  - `mode: str`
  - `query: str`
  - `k: int`
  - `results: tuple[ResultLogRow, ...]` — verse_id, per-component ranks, RRF score
  - `latency_ms: dict[str, float]`

**`@dataclass(frozen=True) class ResultLogRow`** [public]
- Fields: `verse_id: str`; `bm25_rank: int | None`; `dense_rank: int | None`; `rrf_score: float | None`.

**`append(record: QueryLogRecord) -> None`** [public]
- **Hides / role:** the on-disk JSONL format of `data/logs/queries.jsonl`, the timestamp formatting, the atomic-line-append discipline (open `"a"`, write one fully-formed line ending with `"\n"` per call). A future migration of logs to SQLite touches this file alone.
- **Pre:** `record`'s invariants hold.
- **Post:** one line is appended to `paths.logs_dir() / "queries.jsonl"`; the file and parent directory are created if absent.
- **Raises:** `OSError` on filesystem failure (ADR-001 — does not swallow).
- **Calls:** `paths.logs_dir`, `dataclasses.asdict`, `json.dumps`.

**`new_session_id() -> str`** [public]
- Returns a UUID4 hex string. One `session_id` per CLI invocation. Considered hiding inside `append`; rejected — the query subcommand may want to use one session id across multiple appends in a future feature, and the function is two lines.

**`new_query_id() -> str`** [public]
- Returns a UUID4 hex string for a single query event.

---

##### `apps/scripvec_cli/src/scripvec_cli/version_cmd.py`

**`register(app: typer.Typer) -> None`** [public]
- **Hides / role:** the `--version` subcommand wiring. The output schema is `{cli_version, embedding_model, latest_index_hash}` per ADR-007 and CR-002. One file because the schema is part of the agent contract.
- **Pre:** `app` is a Typer root.
- **Post:** registers a `version` callback (also wired as `--version` flag on the root) that prints the JSON to stdout and exits 0. On missing config or missing latest, calls `errors.emit_error` with a stable code.
- **Raises:** none directly; failures route through `emit_error`.
- **Calls:** `_emit_version`, `errors.emit_error`, `config.load_embed_config`, `paths.resolve_latest`.

**`_emit_version() -> None`** [private]
- The actual output assembly. Lifted only because the Typer callback wrapper is one line and this body is the substance.
- **Calls:** `config.load_embed_config`, `paths.resolve_latest`, `importlib.metadata.version`.

---

##### `apps/scripvec_cli/src/scripvec_cli/feedback_cmd.py`

**`register(app: typer.Typer) -> None`** [public]
- **Hides / role:** the `feedback` subcommand wiring. The append discipline (atomic JSONL line, timestamp, schema_version) is co-located here because nothing else writes feedback (one writer rule).
- **Pre:** `app` is a Typer root.
- **Post:** registers `feedback` with flags `--query-id`, `--verse-id`, `--grade`, `--note`. On success, appends one record to `data/logs/feedback.jsonl` and prints a JSON confirmation to stdout (exit 0). Bad input → `emit_error` with `USER_ERROR`.
- **Calls:** `_append_feedback`, `errors.emit_error`, `paths.logs_dir`.

**`_append_feedback(query_id: str, verse_id: str, grade: int, note: str | None) -> dict`** [private]
- **Hides / role:** the JSONL line shape (`timestamp`, `schema_version`, `query_id`, `verse_id`, `grade`, `note`) and the atomic-append. Returns the written record so the command can echo it as the JSON confirmation.
- **Pre:** `grade ∈ {0, 1, 2}`.
- **Post:** one line appended to `paths.logs_dir() / "feedback.jsonl"`.
- **Raises:** `ValueError` on `grade ∉ {0, 1, 2}`; `OSError` on filesystem failure.
- **Calls:** `paths.logs_dir`.

---

##### `apps/scripvec_cli/src/scripvec_cli/index_cmd.py`

**`register(app: typer.Typer) -> None`** [public]
- **Hides / role:** the `scripvec index` Typer sub-app and its two children: `index build` and `index list`. One file, two commands — they share the sub-app and the same output-schema idioms; splitting them would force a two-file boundary over one call each.
- **Pre:** `app` is a Typer root.
- **Post:** registers an `index` Typer sub-app with `build` and `list` subcommands.
- **Calls:** `_cmd_build`, `_cmd_list`.

**`_cmd_build(from_scratch: bool = True, rebuild_corpus: bool = False) -> None`** [private]
- The `index build` body. Wraps `retrieval.build_index` and prints `{"index_hash": ..., "latest": ...}` on stdout. Errors map: `RuntimeError` from drift guard → `USER_ERROR` with code `"corpus_drift"`; `RuntimeError` from embed → `UPSTREAM_ERROR` with code `"embedding_endpoint"`; everything else → `USER_ERROR` with code `"build_failed"` and the exception message in `details`.
- **Calls:** `scripvec_retrieval.build_index`, `errors.emit_error`.

**`_cmd_list() -> None`** [private]
- The `index list` body. Walks `paths.indexes_dir()` for `*/config.json`, reads each manifest, emits a JSON array of `{hash, created_at, model, dim, is_latest}` sorted by `hash` ascending (deterministic per ADR-007). `created_at` comes from the `config.json` file mtime — there is no separate "creation time" field in the manifest at MVP. (Considered adding one to the manifest — rejected, that adds a field nothing else cares about and bumps every hash.)
- **Calls:** `paths.indexes_dir`, `paths.resolve_latest`, `manifest.read_manifest`.

---

##### `apps/scripvec_cli/src/scripvec_cli/query_cmd.py`

**`register(app: typer.Typer) -> None`** [public]
- **Hides / role:** the `query` subcommand wiring — flag parsing, ADR-007 help text (purpose / flag table / output schema / error-code table / one concrete JSON example), the call to `retrieval.query()`, the JSON formatting of `QueryResult`, the `--format text` rendering, the call to `query_log.append`. Knows nothing about how retrieval works; only about the agent contract.
- **Pre:** `app` is a Typer root.
- **Post:** registers `query` with positional `text` and flags `--k`, `--mode`, `--format`, `--index`, `--show-scores`. Calls `_run_query`. Errors map: `ValueError` on flags → `USER_ERROR` (code `"bad_flag"`); `RuntimeError` for missing index → `NOT_FOUND` (code `"index_not_found"`); `RuntimeError` from drift guard or embed → `UPSTREAM_ERROR` (code `"embedding_endpoint"` or `"endpoint_drift"`).
- **Calls:** `_run_query`, `errors.emit_error`.

**`_run_query(text: str, k: int, mode: str, format_: str, index: str, show_scores: bool) -> None`** [private]
- The query body. Calls `retrieval.query`, formats output (JSON default, text on request), writes to stdout, appends a `QueryLogRecord` to `data/logs/queries.jsonl`. Logging is unconditional on success — every CLI query is logged (CR-002).
- **Calls:** `scripvec_retrieval.query`, `_to_log_record`, `query_log.append`, `query_log.new_session_id`, `query_log.new_query_id`, `_format_text` (only when `format_ == "text"`).

**`_to_log_record(result: QueryResult, *, session_id: str, query_id: str) -> QueryLogRecord`** [private]
- Pure mapping from `QueryResult` to `QueryLogRecord`. One place owns the field-by-field copy so a future schema bump touches one function.
- **Calls:** none.

**`_format_text(result: QueryResult) -> str`** [private]
- Renders the unstable human-debug ASCII format. Documented as not-a-contract in the help text (ADR-007 — text format may be less stable; agents must not depend on it).
- **Calls:** none.

---

##### `apps/scripvec_cli/src/scripvec_cli/eval_cmd.py`

**`register(app: typer.Typer) -> None`** [public]
- **Hides / role:** the `eval run` subcommand wiring — flag parsing, ADR-007 help text, delegation to `eval.run`, JSON / text formatting of the report, the failures-file path echo.
- **Pre:** `app` is a Typer root.
- **Post:** registers an `eval` Typer sub-app with `run` subcommand; flags `--queries`, `--judgments`, `--index`, `--format`. Errors route through `emit_error` with code `"eval_failed"` (USER_ERROR) for harness errors; sanity-probe failures map to USER_ERROR with code `"sanity_probe_failed"`.
- **Calls:** `_cmd_run`, `errors.emit_error`.

**`_cmd_run(queries: Path, judgments: Path, index: str = "latest", format_: str = "json") -> None`** [private]
- The `eval run` body. Calls `scripvec_eval.run`, prints the metrics table and the per-bucket stratified table and the ship-criterion pass/fail flags as JSON (or as ASCII when `format_ == "text"`), echoes the failures-file path.
- **Calls:** `scripvec_eval.run`, `_format_text` (only when text).

**`_format_text(report: EvalReport) -> str`** [private]
- ASCII-table rendering for human dogfooding. Same caveat as in `query_cmd._format_text`.
- **Calls:** none.

---

##### `apps/scripvec_cli/src/scripvec_cli/main.py`

**`app: typer.Typer`** [public, module attribute]
- **Hides / role:** the Typer root configuration — that we use Typer at all, that colors / pagination / interactive prompts are disabled, that JSON is the default format, and the registration of every subcommand. Callers downstream never see `typer` directly. Wired to the existing console script `scripvec = "scripvec_cli.main:app"`.
- **Construction:** `typer.Typer(add_completion=False, pretty_exceptions_enable=False, no_args_is_help=True)`. Each subcommand module's `register(app)` is called at import time of this module. (Considered a `main()` wrapper; rejected — Typer apps are callable, so a wrapper would be a pure pass-through. Also considered a `__main__.py`; rejected — `python -m scripvec_cli` is not part of the CR-002 surface.)
- **Calls (at import):** `query_cmd.register`, `index_cmd.register`, `eval_cmd.register`, `feedback_cmd.register`, `version_cmd.register`.

---

##### `apps/scripvec_cli/src/scripvec_cli/test_contracts.py`

ADR-007 validation clause. One success-path test and one forced-failure test per subcommand. Uses Typer's `CliRunner`. Tests are listed; their bodies use `runner.invoke(app, [...])` and `json.loads` against stdout / stderr.

**`def test_query_emits_documented_json_schema_on_success()`** [test]
- Asserts top-level keys of the parsed stdout JSON match the CR-002 query output schema; `results` is a list with `rank`, `verse_id`, `ref`, `text`, `score`, `scores`; `latency_ms` has all four stage keys; ordering is by `rank` ascending.

**`def test_query_emits_structured_error_on_bad_flag()`** [test]
- Asserts exit code 1 and that stderr parses as `{"error": {"code", "message", "details"}}`.

**`def test_index_build_emits_documented_json_schema_on_success()`** [test]
- Asserts stdout JSON contains `index_hash` and `latest`. (May skip / mock if a live build is too slow for the test layer — the assertion is on the schema shape, not on a real corpus.)

**`def test_index_build_emits_structured_error_on_drift()`** [test]
- Forces a corpus-drift condition; asserts exit code 1 and structured stderr with the documented error code.

**`def test_index_list_emits_documented_json_schema()`** [test]
- Asserts stdout is a JSON array; each element has `hash`, `created_at`, `model`, `dim`, `is_latest`; ordering is deterministic.

**`def test_index_list_emits_structured_error_on_unreadable_indexes_dir()`** [test]
- Forced failure: an unreadable indexes dir. Asserts exit code and structured stderr.

**`def test_eval_run_emits_documented_json_schema()`** [test]
- Asserts stdout JSON has `metrics`, `recall10_by_bucket`, `ship`, `failures_path`, `index_hash`.

**`def test_eval_run_emits_structured_error_on_unknown_verse_id_in_judgments()`** [test]
- Forced failure: a judgments file referencing an unknown `verse_id`. Asserts exit code and structured stderr with code `"unknown_verse_id"`.

**`def test_feedback_emits_documented_json_schema_on_success()`** [test]
- Asserts the JSON confirmation echoes the appended record.

**`def test_feedback_emits_structured_error_on_bad_grade()`** [test]
- Asserts exit code 1 and structured stderr on `--grade 3`.

**`def test_version_emits_documented_json_schema()`** [test]
- Asserts stdout JSON has `cli_version`, `embedding_model`, `latest_index_hash`.

**`def test_version_emits_structured_error_when_latest_missing()`** [test]
- Forced failure: no `latest` symlink. Asserts structured stderr.

---

##### Expanded test coverage (added 2026-04-20) — function listings

Each test file is pytest-collection only; bodies use small fixed fixtures and assertions.

###### `packages/retrieval/src/scripvec_retrieval/test_tokenizer.py`

- `def test_tokenize_lowercases()` — `"Faith AND Works"` → `["faith", "and", "works"]`.
- `def test_tokenize_normalizes_nfc()` — pre-composed and decomposed Unicode forms tokenize identically.
- `def test_tokenize_splits_on_word_boundary()` — punctuation, hyphens, slashes act as separators.
- `def test_tokenize_drops_short_pure_digit_tokens()` — `"verse 1 of 12"` drops `"1"`, keeps `"12"`.
- `def test_tokenize_keeps_alphanumeric_tokens()` — `"d&c"` → `["d", "c"]` (token-level, not phrase-level).
- `def test_tokenize_is_deterministic()` — same input across repeated calls returns identical lists.

###### `packages/retrieval/src/scripvec_retrieval/test_rrf.py`

- `def test_rrf_formula_on_known_inputs()` — fixed BM25 + dense rankings, hand-computed RRF scores match.
- `def test_rrf_breaks_ties_by_verse_id_ascending()` — two docs at identical RRF scores order alphabetically by `verse_id`.
- `def test_rrf_truncates_to_top_k()` — output length ≤ `top_k`.
- `def test_rrf_handles_disjoint_inputs()` — docs that appear in only one input list still score correctly.
- `def test_rrf_raises_on_k_below_one()` — `ValueError`.
- `def test_rrf_raises_on_top_k_below_one()` — `ValueError`.

###### `packages/retrieval/src/scripvec_retrieval/test_hashing.py`

- `def test_canonical_json_sorts_keys()` — `{"b":1,"a":2}` and `{"a":2,"b":1}` produce identical bytes.
- `def test_canonical_json_omits_whitespace()` — output contains no `" "` or `"\n"`.
- `def test_canonical_json_is_utf8()` — non-ASCII keys / values round-trip through UTF-8.
- `def test_blake2b_128_hex_is_32_chars()` — output length is exactly 32 lowercase hex chars.
- `def test_blake2b_128_hex_is_deterministic()` — same input twice yields the same digest.
- `def test_canonical_then_hash_is_invariant_to_dict_key_order()` — composition test: reordered dicts produce identical config_hash candidates.

###### `packages/retrieval/src/scripvec_retrieval/test_manifest.py`

- `def test_write_then_read_returns_equal_manifest()` — round-trip with a fully-populated `Manifest`.
- `def test_read_raises_on_missing_required_field()` — manually-edited JSON missing one field → `RuntimeError`.
- `def test_read_raises_on_unknown_field()` — extra field present → `RuntimeError` (strict reader catches drift).
- `def test_read_raises_on_type_mismatch()` — `dim` as a string instead of int → `RuntimeError`.

###### `packages/retrieval/src/scripvec_retrieval/test_query.py`

- `def test_drift_check_endpoint_passes_on_full_match()` — silent return.
- `def test_drift_check_endpoint_raises_on_url_mismatch()` — message names `endpoint`.
- `def test_drift_check_endpoint_raises_on_model_mismatch()` — message names `model`.
- `def test_drift_check_endpoint_raises_on_dim_mismatch()` — message names `dim`.
- `def test_drift_check_endpoint_message_lists_both_values()` — message includes both stored and runtime values.
- `def test_resolve_index_returns_latest_when_requested()` — `"latest"` resolves through the symlink.
- `def test_resolve_index_returns_explicit_hash()` — a 32-hex string resolves directly.
- `def test_resolve_index_raises_on_missing_directory()` — `RuntimeError` (CLI-side maps to exit code 2).

###### `packages/retrieval/src/scripvec_retrieval/test_build.py`

- `def test_drift_check_corpus_passes_on_match()` — silent return when commits agree.
- `def test_drift_check_corpus_passes_when_no_stored_commit()` — from-scratch build is a no-op.
- `def test_drift_check_corpus_passes_when_rebuild_corpus_true()` — explicit override.
- `def test_drift_check_corpus_raises_on_mismatch()` — `RuntimeError` with both commits in message.

###### `packages/eval/src/scripvec_eval/test_metrics.py`

- `def test_recall_at_k_on_known_fixture()` — hand-computed value matches.
- `def test_recall_at_k_returns_zero_on_empty_relevant()`.
- `def test_recall_at_k_raises_on_k_below_one()` — `ValueError`.
- `def test_ndcg_at_10_on_perfect_ordering_returns_one()`.
- `def test_ndcg_at_10_uses_two_to_grade_minus_one_gain()` — grade-2 contributes 3, grade-1 contributes 1, grade-0 contributes 0.
- `def test_mrr_at_10_returns_inverse_rank()` — first relevant at rank 3 → 1/3.
- `def test_mrr_at_10_returns_zero_when_nothing_relevant_in_top_10()`.
- `def test_percentile_p50_p95_on_known_samples()` — fixed sample list; hand-computed values.
- `def test_percentile_raises_on_empty_samples()` — `ValueError`.
- `def test_percentile_raises_on_p_out_of_range()` — `ValueError` for `p < 0` or `p > 100`.

###### `packages/eval/src/scripvec_eval/test_dataset.py`

- `def test_load_queries_accepts_well_formed_set()` — 50-row fixture passes; returns `list[QueryRow]`.
- `def test_load_queries_raises_on_duplicate_query_text()` — `RuntimeError`; message names both `query_id`s.
- `def test_load_queries_raises_on_duplicate_query_id()` — `RuntimeError`.
- `def test_load_queries_raises_on_malformed_json_line()` — `RuntimeError`; message names line number.
- `def test_load_queries_raises_on_under_eight_per_bucket()` — `RuntimeError`; message names the short bucket.
- `def test_load_judgments_accepts_well_formed_set()` — fixture with valid (query_id, verse_id, grade) rows.
- `def test_load_judgments_raises_on_unknown_verse_id()` — `RuntimeError` with the offending `verse_id`.
- `def test_load_judgments_raises_on_invalid_grade()` — grade=3 → `RuntimeError`; grade=0 in file → `RuntimeError` (zero is the absence value, not a written grade).
- `def test_load_judgments_raises_on_malformed_json_line()` — `RuntimeError`; message names line number.

---

#### 2. Cross-package call summary

Intra-package calls live in section 1.

| From | To | Through | Reason |
|------|----|---------|--------|
| `scripvec_corpus_ingest.bcbooks` | `scripvec_reference.reference` | `canonical()` | Build canonical reference strings during ingest. |
| `scripvec_corpus_ingest.bcbooks` | `scripvec_reference.books` | `canonicalize_book()` | Map raw book names from JSON to canonical form. |
| `scripvec_corpus_ingest.bcbooks` | `scripvec_corpus_ingest.verse` | `make_verse_id()` | Derive deterministic verse ids. |
| `scripvec_retrieval.build` | `scripvec_corpus_ingest.bcbooks` | `iter_verses()`, `corpus_commit_sha()` | Walk the corpus during build; capture commit SHA for the manifest and the drift guard. |
| `scripvec_retrieval.store` | `scripvec_corpus_ingest.verse` | `VerseRecord` (type) | The persisted row shape. |
| `scripvec_retrieval.bm25` | `scripvec_corpus_ingest.verse` | `VerseRecord` (type) | Index input shape. |
| `scripvec_retrieval.query` | `scripvec_corpus_ingest.verse` | `VerseRecord` (type) | Query result join target. |
| `scripvec_eval.run` | `scripvec_retrieval.query` | `query()` | Run every query × every mode. |
| `scripvec_eval.run` | `scripvec_retrieval.bm25` | `load_bm25()` | Load the BM25 index for sanity probes. |
| `scripvec_eval.run` | `scripvec_retrieval.store` | `open_store()` | Resolve `verse_id` → text for failure rows; size accounting. |
| `scripvec_eval.run` | `scripvec_retrieval.paths` | `index_path()`, `eval_dir()` | Resolve target index dir; place failures file. |
| `scripvec_eval.dataset` | `scripvec_retrieval.bm25` | `bm25_topk()` | Sanity-probe execution. |
| `scripvec_cli.query_cmd` | `scripvec_retrieval.query` | `query()` | Run a hybrid (or other-mode) search. |
| `scripvec_cli.index_cmd` | `scripvec_retrieval.build` | `build_index()` | The `index build` subcommand. |
| `scripvec_cli.index_cmd` | `scripvec_retrieval.paths` | `indexes_dir()`, `resolve_latest()` | The `index list` subcommand. |
| `scripvec_cli.index_cmd` | `scripvec_retrieval.manifest` | `read_manifest()` | The `index list` subcommand reads each `config.json`. |
| `scripvec_cli.eval_cmd` | `scripvec_eval.run` | `run()` | The `eval run` subcommand. |
| `scripvec_cli.version_cmd` | `scripvec_retrieval.config` | `load_embed_config()` | `--version` echoes the configured embedding model id. |
| `scripvec_cli.version_cmd` | `scripvec_retrieval.paths` | `resolve_latest()` | `--version` echoes the latest index hash. |
| `scripvec_cli.feedback_cmd` | `scripvec_retrieval.paths` | `logs_dir()` | Where to write `feedback.jsonl`. |
| `scripvec_cli.query_log` | `scripvec_retrieval.paths` | `logs_dir()` | Where to write `queries.jsonl`. |

Note: `scripvec_cli.query_log` lives inside the CLI package, not retrieval, by deliberate design (logging is a CLI-boundary concern — see CR-002 design notes). Its only out-of-CLI dependency is on `scripvec_retrieval.paths` for the directory location.

---

#### 3. Full file-level dependency graph

In-repo imports only. Stdlib and third-party (`httpx`, `sqlite-vec`, `bm25s`, `numpy`, `typer`) omitted.

##### Edges, grouped by package

```
packages/reference/scripvec_reference/
  reference.py        → books.py
  __init__.py         → reference.py, books.py

packages/corpus_ingest/scripvec_corpus_ingest/
  bcbooks.py          → verse.py
                      → scripvec_reference.reference
                      → scripvec_reference.books
  verse.py            → (no in-repo imports)
  __init__.py         → verse.py, bcbooks.py

packages/retrieval/scripvec_retrieval/
  config.py           → (no in-repo imports)
  paths.py            → (no in-repo imports)
  hashing.py          → (no in-repo imports)
  test_hashing.py     → hashing.py
  tokenizer.py        → (no in-repo imports)
  test_tokenizer.py   → tokenizer.py
  rrf.py              → (no in-repo imports)
  test_rrf.py         → rrf.py
  embed.py            → config.py
  test_embed.py       → embed.py, config.py
  manifest.py         → hashing.py
  test_manifest.py    → manifest.py
  store.py            → config.py
                      → scripvec_corpus_ingest.verse
  bm25.py             → tokenizer.py
                      → scripvec_corpus_ingest.verse
  build.py            → config.py, paths.py, embed.py, manifest.py,
                        store.py, bm25.py
                      → scripvec_corpus_ingest.bcbooks
  test_build.py       → build.py
  query.py            → config.py, paths.py, embed.py, manifest.py,
                        store.py, bm25.py, rrf.py
                      → scripvec_corpus_ingest.verse
  test_query.py       → query.py, manifest.py, config.py, paths.py
  __init__.py         → build.py, query.py (re-exports build_index, query, QueryResult, ResultRow)

packages/eval/scripvec_eval/
  metrics.py          → (no in-repo imports)
  test_metrics.py     → metrics.py
  dataset.py          → scripvec_retrieval.bm25
  test_dataset.py     → dataset.py
  run.py              → dataset.py, metrics.py
                      → scripvec_retrieval.query
                      → scripvec_retrieval.bm25
                      → scripvec_retrieval.store
                      → scripvec_retrieval.paths
                      → scripvec_retrieval.manifest
  __init__.py         → run.py (re-exports run, EvalReport, ShipCriteria, ModeMetrics)

apps/scripvec_cli/scripvec_cli/
  errors.py           → (no in-repo imports)
  query_log.py        → scripvec_retrieval.paths
  version_cmd.py      → errors.py
                      → scripvec_retrieval.config
                      → scripvec_retrieval.paths
  feedback_cmd.py     → errors.py
                      → scripvec_retrieval.paths
  index_cmd.py        → errors.py
                      → scripvec_retrieval.build
                      → scripvec_retrieval.paths
                      → scripvec_retrieval.manifest
  query_cmd.py        → errors.py, query_log.py
                      → scripvec_retrieval.query
  eval_cmd.py         → errors.py
                      → scripvec_eval.run
  main.py             → query_cmd.py, index_cmd.py, eval_cmd.py,
                        feedback_cmd.py, version_cmd.py
  test_contracts.py   → main.py
```

**Cycle check:** none. Reference is a leaf. Corpus_ingest depends only on reference. Retrieval depends on corpus_ingest and reference (none the other way). Eval depends only on retrieval (and indirectly its deps). CLI depends on retrieval and eval (none the other way). The dependency direction is strictly leaves → joiners with no back-edges.

##### Leaf → joiner topological order

Files in the order a builder would safely write tests against each. Within a "rank," files are independent and can be authored in parallel.

```
Rank 0 (pure leaves, no in-repo imports):
  packages/reference/.../books.py
  packages/corpus_ingest/.../verse.py
  packages/retrieval/.../config.py
  packages/retrieval/.../paths.py
  packages/retrieval/.../hashing.py
  packages/retrieval/.../tokenizer.py
  packages/retrieval/.../rrf.py
  packages/eval/.../metrics.py
  apps/scripvec_cli/.../errors.py

Rank 1:
  packages/reference/.../reference.py        (→ books)
  packages/retrieval/.../embed.py            (→ config)
  packages/retrieval/.../manifest.py         (→ hashing)
  packages/retrieval/.../store.py            (→ config, corpus_ingest.verse)*
  packages/retrieval/.../bm25.py             (→ tokenizer, corpus_ingest.verse)*
  apps/scripvec_cli/.../query_log.py         (→ retrieval.paths)
  packages/retrieval/.../test_embed.py       (→ embed, config)
  packages/retrieval/.../test_hashing.py     (→ hashing)
  packages/retrieval/.../test_tokenizer.py   (→ tokenizer)
  packages/retrieval/.../test_rrf.py         (→ rrf)
  packages/eval/.../test_metrics.py          (→ metrics)
  * store.py and bm25.py are at rank 1 if you accept that `verse.py` (rank 0) is the only corpus_ingest dep they need.

Rank 2:
  packages/corpus_ingest/.../bcbooks.py      (→ verse, reference, books)
  packages/eval/.../dataset.py               (→ retrieval.bm25)
  apps/scripvec_cli/.../version_cmd.py       (→ errors, retrieval.config, retrieval.paths)
  apps/scripvec_cli/.../feedback_cmd.py      (→ errors, retrieval.paths)
  packages/retrieval/.../test_manifest.py    (→ manifest)

Rank 3:
  packages/retrieval/.../build.py            (→ everything in retrieval + corpus_ingest.bcbooks)
  packages/retrieval/.../query.py            (→ everything in retrieval + corpus_ingest.verse)
  packages/eval/.../test_dataset.py          (→ dataset)

Rank 4:
  packages/eval/.../run.py                   (→ dataset, metrics, retrieval.query, retrieval.bm25, retrieval.store, retrieval.paths, retrieval.manifest)
  apps/scripvec_cli/.../query_cmd.py         (→ errors, query_log, retrieval.query)
  apps/scripvec_cli/.../index_cmd.py         (→ errors, retrieval.build, retrieval.paths, retrieval.manifest)
  packages/retrieval/.../test_build.py       (→ build)
  packages/retrieval/.../test_query.py       (→ query, manifest, config, paths)

Rank 5:
  apps/scripvec_cli/.../eval_cmd.py          (→ errors, eval.run)

Rank 6 (top joiner):
  apps/scripvec_cli/.../main.py              (→ all *_cmd modules)

Rank 7:
  apps/scripvec_cli/.../test_contracts.py    (→ main)
```

---

#### 4. Module-boundary contracts

##### `packages/reference/`

- **Hides from outside:** the canonical book-name table; the `"<Book> <chapter>:<verse>"` grammar.
- **Public surface (re-exports via `__init__.py`):** `Reference`, `parse_reference`, `canonical`, `canonicalize_book`, `CANONICAL_BOOKS`.
- **Allowed inbound:** `corpus_ingest`, `retrieval` (transitive — for type hints / canonical strings only). The CLI does not import this directly; it talks through retrieval.
- **Allowed outbound:** none (leaf package; stdlib only).

##### `packages/corpus_ingest/`

- **Hides from outside:** the JSON shape of bcbooks; the `verse_id` derivation; the order in which verses are walked; the git-SHA-based corpus-version scheme.
- **Public surface:** `VerseRecord`, `make_verse_id`, `iter_verses`, `corpus_commit_sha`.
- **Allowed inbound:** `retrieval`. `eval` and `cli` do not import this directly — `VerseRecord` reaches them transitively through retrieval's public types.
- **Allowed outbound:** `reference`.

##### `packages/retrieval/`

- **Hides from outside:**
  - The wire format of the embedding endpoint and the fact that `embed()` exists at all (ADR-006 — the embed function is **not** re-exported from `__init__.py`; nothing outside the package may import it).
  - The on-disk layout of `corpus.sqlite` and the `vec0` schema; SQL stays inside `store.py`.
  - The choice of `BM25S` and its on-disk format; `bm25s` stays inside `bm25.py`.
  - The hash algorithm and the canonical-JSON encoding; `hashlib` and the JSON shape stay inside `hashing.py`.
  - The `data/` directory layout and the symlink discipline; path joining stays inside `paths.py`.
  - The `Manifest` field set and its on-disk JSON shape; reads / writes stay inside `manifest.py`.
  - The RRF formula and tiebreaker rule; stays inside `rrf.py`.
- **Public surface:** `build_index`, `query`, `QueryResult`, `ResultRow`. (Internal modules — `embed`, `store`, `bm25`, `manifest`, `paths`, `config`, `rrf`, `hashing`, `tokenizer` — are importable as `scripvec_retrieval.<module>` for the CLI and eval subcommands that legitimately need a narrower surface like `paths.logs_dir()`, but not re-exported as top-level names.)
- **Allowed inbound:** `eval`, `scripvec_cli`. Not `corpus_ingest` or `reference`.
- **Allowed outbound:** `corpus_ingest`, `reference`.

##### `packages/eval/`

- **Hides from outside:** the JSONL shapes of `queries.jsonl` and `judgments.jsonl`; the metric formulas; the ship-criterion thresholds (CR-002 thresholds live as named constants inside `run.py`); the failures-file format; the sanity-probe contents.
- **Public surface:** `run`, `EvalReport`, `ShipCriteria`, `ModeMetrics`.
- **Allowed inbound:** `scripvec_cli`.
- **Allowed outbound:** `retrieval`. (Not `corpus_ingest` or `reference` directly.)

##### `apps/scripvec_cli/`

- **Hides from outside:** that we use Typer; the structured-error JSON shape; the exit-code table; the `data/logs/queries.jsonl` and `data/logs/feedback.jsonl` formats; the `--format text` rendering rules.
- **Public surface (entry point):** the `scripvec` console script bound to `scripvec_cli.main:app`. There is no library surface — the CLI is the deployable.
- **Allowed inbound:** none. Nothing imports the CLI; humans and agents invoke the binary.
- **Allowed outbound:** `retrieval`, `eval`. Not `corpus_ingest` or `reference` directly — anything they expose reaches the CLI through retrieval.

**Reconciliation against section 3:** the dependency graph and the boundary contracts agree. `corpus_ingest.verse.VerseRecord` does appear as a type in retrieval's public surface (via `QueryResult.results[i].text` and friends — but only as a string field, not as the dataclass itself), so the CLI never needs to import `corpus_ingest`. No discrepancies.

---

#### 5. Design questions surfaced

These are flagged for the engineer.

1. **`make_verse_id` scheme — DECIDED 2026-04-20: slug.** Human-readable slug form (`1-nephi-3-7`, `dandc-88-118`) chosen for human-grep-ability of `judgments.jsonl`, the failures file, and log records. If collisions or another problem ever appears, swap one function and bump `vec_schema_version` in the manifest.

2. **`config.json` `created_at` — DECIDED 2026-04-20: file mtime.** Engineer accepts that file copies / `touch` reset the timestamp; index content rarely changes and smooth `config_hash` semantics (no built-in timestamp, so identical configurations always produce identical hashes) are preferred over a stored field. If file-shuffling ever causes confusion, swap to a deliberately-not-hashed manifest field at that point.

3. **`SANITY_PROBES` values are an authoring task in System 9.** The constant `SANITY_PROBES = (...)` is declared in `dataset.py` as a placeholder. Picking the actual three queries and their expected `verse_id`s requires the live corpus — done as part of authoring `data/eval/queries.jsonl`. No code-side decision pending; tracked as authoring work.

4. **`ResultRow.scores["dense"]` semantics — DECIDED 2026-04-20: cosine.** Confirmed via the Qwen3-Embedding-0.6B model card (HuggingFace) which recommends cosine similarity and L2-normalizes embeddings before scoring. Since ADR-005 also L2-normalizes client-side, inner product and cosine are mathematically identical — the user-facing field name is `cosine` (matches model contract and user expectation); the inner-product computation is an implementation detail of `sqlite-vec` and is hidden inside `store.py`. `DenseHit.cosine: float` and `dense_topk` return docs updated above.

5. **`embed` not re-exported from `scripvec_retrieval.__init__` — DECIDED 2026-04-20: hidden.** ADR-006 mandates serial-only embedding; keeping `embed` out of the package's public surface (callers must write `from scripvec_retrieval.embed import embed` rather than `from scripvec_retrieval import embed`) makes the wrong call pattern (parallelizing it) awkward to reach for. CLI and eval reach embedding only transitively through `query()` and `build_index()`. `version_cmd.py` calls `config.load_embed_config()` to echo the configured model identifier — that's an env read, not an embedding call, so the boundary holds.

6. **Test coverage — DECIDED 2026-04-20: expanded.** Engineer chose to add unit tests for every pure-function and drift-guard module Ousterhout flagged as untested. Eight new test files added: `test_tokenizer.py`, `test_rrf.py`, `test_hashing.py`, `test_manifest.py`, `test_query.py` (endpoint-drift guard + index resolution), `test_build.py` (corpus-drift guard) in `packages/retrieval/`; `test_metrics.py` and `test_dataset.py` (JSONL loaders) in `packages/eval/`. See **Expanded test coverage** sub-blocks in the file blueprint and the function plan for the per-file briefs and the test-function listings. `store.py` and `bm25.py` remain unit-untested — they require live `sqlite-vec` / BM25S state and are integration-test surfaces; the eval harness exercises both end-to-end.

## Audit log

- 2026-04-19T23:04:32+02:00 — created as `accepted` (direct acceptance after engineer review of the Retrieval Engineer proposal; no separate `drafting` or `pending` stage).
- 2026-04-20 — appended implementation plan (MVP 0.0), systems → components → tasks in dependency order, generated from the MVP-Implementation-Plan-Generator prompt.
- 2026-04-20 — appended Sprints subsection (3 sprints with parallel tracks) to the implementation plan.
- 2026-04-20 — appended File blueprint subsection (file tree, per-file briefs, design notes) generated by channeling John Ousterhout via the personas skill; engineer decisions applied (sanity probes inlined; `tokenizer.py` and `hashing.py` split out; CLI entry consolidated to `main.py`).
- 2026-04-20 — appended Function plan subsection (per-file function contracts, cross-package call summary, file-level dependency graph with leaf→joiner topological order, module-boundary contracts, design questions surfaced) generated by channeling John Ousterhout via the personas skill.
- 2026-04-20 — function plan: resolved design questions 1 (verse_id slug) and 4 (`DenseHit.cosine` — confirmed via Qwen3-Embedding-0.6B model card on HuggingFace); design questions 2, 5, 6 still pending engineer; question 3 reframed as a System-9 authoring task (no code decision).
- 2026-04-20 — function plan: resolved design questions 2 (`config.json` `created_at` → file mtime; smooth hash semantics preferred over a stored field) and 6 (test coverage expanded — 8 new test files added for tokenizer, RRF, hashing, manifest round-trip, both drift guards, metrics, and JSONL loaders; `store.py` / `bm25.py` remain integration-test surfaces). File blueprint, function plan, dependency graph, and topological rank list updated to reflect 36 new code files (from 28). Design question 5 (`embed` non-re-export) still pending engineer confirmation.
- 2026-04-20 — function plan: resolved design question 5 (`embed` non-re-exported from `scripvec_retrieval.__init__` — hidden, to discourage callers from naively wrapping the synchronous embed call in a thread pool / async pattern that would violate ADR-006). All six design questions now resolved.
- 2026-04-20 — **completed.** All 30 implementation tasks finished; eval harness passes ship criteria; CR moved to `completed/`.
