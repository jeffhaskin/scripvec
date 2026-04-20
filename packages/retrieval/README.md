# retrieval

The retrieval core — embedding client (the single sanctioned entry point to the ADR-005 endpoint, per ADR-006), `sqlite-vec` dense index, `BM25S` lexical index, RRF hybrid fusion, and the query path invoked by the CLI and the eval harness.

Allowed in-repo imports: `packages/corpus_ingest` and `packages/reference` (per the dependency graph in `docs/specs/adrs/003_accepted_mvp_folder_structure.md`).
