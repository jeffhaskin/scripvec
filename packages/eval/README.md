# eval

The evaluation harness — runs the held-out query set in `data/eval/` against a built index, reports recall@10, recall@20, nDCG@10, MRR@10, and latency percentiles per mode, and emits a failures file for the queries that miss.

Allowed in-repo imports: `packages/retrieval` (per the dependency graph in `docs/specs/adrs/003_accepted_mvp_folder_structure.md`).
