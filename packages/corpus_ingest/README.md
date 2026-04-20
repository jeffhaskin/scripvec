# corpus_ingest

Reads canonical scripture source files under `data/raw/` and emits normalized verse records (verse_id, canonical reference, book, chapter, verse, text) for downstream retrieval and evaluation code to consume.

Allowed in-repo imports: none — `corpus_ingest` is a leaf package in the dependency graph per `docs/specs/adrs/003_accepted_mvp_folder_structure.md`.
