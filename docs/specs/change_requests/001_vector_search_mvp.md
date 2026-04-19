# 001 — Vector Search MVP

## Status
Draft. Not yet advised on by the personas below.

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

Two personas have been added to the persona database specifically for this system. Before any key decision below is locked, channel the relevant persona via `/personas` and record their position in this document.

- **The Retrieval Engineer** — `/data/projects/flywheel/personas/retrieval-engineer.md`
  - Owns: embedding model selection, vector store / ANN index choice, index configuration, baseline eval harness, hybrid-retrieval decision, reranker layering, retrieval latency budgets, instrumentation.
  - Disposition: eval-first; refuses to ship without a held-out query set and a recall@k number.

- **The Structural Corpus Retriever** — `/data/projects/flywheel/personas/structural-corpus-retriever.md`
  - Owns: retrieval unit (is verse the right unit, or is pericope better?), apparatus handling (section headings, chapter summaries, cross-references), reference normalization on query and document sides, windowed-presentation rules.
  - Disposition: treats source structure as a first-class retrieval variable; refuses to accept user-stated chunking units without interrogation.

**Sequence of advisor engagement:** Retrieval Engineer first — their inputs anchor the stack choice. Structural Corpus Retriever immediately after, to challenge corpus-structure defaults before they calcify into code. Neither in isolation.

## Key decisions (each requires advisor input before locking)

1. **Corpus source and ingest format.** Where does the canonical BoM + D&C text come from? What metadata survives? — *Structural Corpus Retriever leads; Retrieval Engineer informs.*
2. **Retrieval unit.** Verse-level is stated. Is it the *retrieval* unit or only the *display* unit? Ablate at least one alternative (e.g., pericope). — *Structural Corpus Retriever.*
3. **Apparatus handling.** What non-body text exists (chapter/section headings, verse reference markers, D&C historical context blocks, italicized editorial words)? For each: in the embedding, as separate vectors, as filterable metadata, or excluded? — *Structural Corpus Retriever.*
4. **Reference normalization.** Canonical citation handling on query and document sides ("Alma 32:21", "D&C 88:118", abbreviations, alternate forms). Implemented as a library, not a regex. — *Structural Corpus Retriever.*
5. **Embedding model.** Model choice, version pinned, cost/latency profile. Measure on this corpus, not just public leaderboards. — *Retrieval Engineer.*
6. **Vector store and index.** sqlite-vec vs. LanceDB vs. Chroma vs. pgvector etc. At MVP scale (~41K verses total across both corpora), this is small. — *Retrieval Engineer.*
7. **Baseline and eval harness.** BM25 baseline implemented first. A held-out query set of ~20–50 representative questions with graded relevance. Recall@k and nDCG reported. — *Retrieval Engineer leads; Structural Corpus Retriever contributes query-set design, since "what counts as a relevant hit" is corpus-aware.*
8. **Hybrid retrieval decision.** Pure dense vs. BM25 + dense fusion. Measure the delta. — *Retrieval Engineer.*
9. **Windowed presentation rules.** When is a single verse sufficient in the result? When should surrounding verses accompany it? Corpus-specific. — *Structural Corpus Retriever.*
10. **Interface surface.** CLI, HTTP API, or notebook? MVP chooses one. — *Open; not strongly persona-owned.*
11. **Rebuild and persistence story.** How is the index rebuilt when the embedding model changes? Versioning of artifacts. — *Retrieval Engineer.*
12. **Logging and feedback hook.** What's captured per query (query text, top-k, latency, any relevance signal) to support later quality improvement? — *Retrieval Engineer.*

## Success criteria
- A user can submit a natural-language query and receive top-k relevant verses from the BoM + D&C corpus.
- Retrieval quality is measured against a held-out query set. Recall@k and a BM25 baseline comparison are documented and checked in.
- Every key decision above has an explicit decision record in this CR with the advising persona's position cited.
- The retrieval layer is thin and legible — readable in one sitting.
- Configuration (embedding model version, chunk unit, index params, distance metric) is explicit and version-controlled.

## Open questions
- What is the canonical, license-clean source for BoM and D&C text? Any redistribution constraints?
- Is there prior-art LDS scripture search to study for a baseline comparison of result quality?
- Target MVP eval query set size: 20 queries is the floor; is 50 a reasonable aim?
- Is there any existing structured edition (JSON, XML) that preserves verse boundaries and apparatus cleanly?

## Next step
Channel both advisors in sequence via `/personas` against this CR. Record their positions inline under each Key decision. Move this CR from Draft to In Progress once the Key decisions are answered or scoped to sub-CRs.
