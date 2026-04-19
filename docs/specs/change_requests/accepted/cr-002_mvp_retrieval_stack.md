---
id: 002
title: MVP retrieval stack and architecture
status: accepted
created: 2026-04-19
updated: 2026-04-19
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/002_accepted_no_role_splitting_in_packages.md
  - docs/specs/adrs/003_accepted_mvp_folder_structure.md
  - docs/specs/adrs/004_accepted_mvp_tooling_floor.md
  - docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md
  - docs/specs/adrs/006_accepted_serialize_embedding_calls.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - cr-001_vector_search_mvp.md
  - docs/principles/001_vector_retrieval.md
---

# CR-002: MVP retrieval stack and architecture

## Summary

Lock the tech stack, libraries, index shape, CLI surface, persistence scheme, logging, evaluation harness, and ship criteria for the scripvec MVP vector search over the Book of Mormon and Doctrine and Covenants. Picks Python, `uv` workspaces (ADR-004 Python recipe), `sqlite-vec` as the vector store (per ADR-005), `BM25S` as the lexical index, RRF hybrid fusion, and a Typer-backed agent-first CLI (per ADR-007). Commits to a 50-query graded held-out eval set reporting recall@10, recall@20, nDCG@10, and MRR@10.

## Motivation

ADR-004 pre-approved a conditional tooling floor but deferred the stack pick to a CR. ADR-003 locked the folder shape around a set of bounded contexts whose internals were not yet specified. ADRs 005–007 lock the embedding endpoint, the serial-embedding constraint, and the agent-first CLI surface. CR-001 listed the retrieval-side key decisions (items 5, 6, 7, 8, 10, 11, 12) as open. This CR closes those, records the concrete libraries and configuration, and defines the ship criteria that must be met before the MVP is called done.

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
- **`cr-001_vector_search_mvp.md`:** this CR closes the Retrieval-Engineer-owned key decisions (items 5, 6, 7, 8, 10, 11, 12). CR-001 remains in `drafting/` with its Structural-Corpus-Retriever-owned decisions still open. No conflict.
- **Policies `pl-001`, `pl-002`, `pl-003`:** this CR uses underscore filenames with the `cr-` type-prefix and cites CRs by filename only. No conflict.

## Decision

Accepted on 2026-04-19 by Jeff Haskin (engineer, sole decision authority).

**Exceptions and clarifications recorded at approval time:**

- **Embedding model is already selected** — the embedding side is governed entirely by ADR-005 and is referenced, not re-litigated, here.
- **Ship criteria approved** as stated, with the standing caveat that the engineer may revisit any number that becomes annoying in practice.
- The cross-encoder reranker deferred by the proposal is split out into a separate CR (`cr-003_cross_encoder_reranker.md`, status `pending`) rather than tracked inline here.

## Audit log

- 2026-04-19T23:04:32+02:00 — created as `accepted` (direct acceptance after engineer review of the Retrieval Engineer proposal; no separate `drafting` or `pending` stage).
