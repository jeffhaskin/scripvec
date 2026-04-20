---
id: 016
title: Speaker / author tagging per verse
status: drafting
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
---

# CR-016: Speaker / author tagging per verse

## Summary

Tag each verse in the index with its speaker or author (e.g., Nephi, Alma, Moroni, the Lord, Joseph Smith) so that queries can filter by who is speaking. Adds a `--speaker <name>` filter to `scripvec query` that drops hits whose tagged speaker does not match.

## Motivation

Who is speaking a verse materially changes how a reader receives it. Studying what *Moroni* says about faith is a different exercise than studying what *Alma* says about faith. A study tool gains a lot from scoping on speaker.

## Why this is distant-future

Assigning speakers to the entire corpus (> 10,000 verses) requires an LLM pass, because speaker is not cleanly available as structured metadata in the source text — it must be inferred from narrative context. At corpus scale that is an expensive one-time inferencing run, with quality-audit burden on top. Parked here so the idea is not lost.

## Decision

Not yet decided. Drafting.

## Audit log

- 2026-04-20 — created as `drafting`.
