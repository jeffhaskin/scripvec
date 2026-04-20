---
id: 017
title: FunctionGemma-270M schema-bounded dispatcher integration (brainstorm)
status: drafting
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - cr-010_scripvec_web_front_end.md
---

# CR-017: FunctionGemma-270M schema-bounded dispatcher integration (brainstorm)

## Summary

Brainstorm incorporating the FunctionGemma-270M model — available at the shared flywheel inferencing server — as a schema-bounded natural-language-to-action dispatcher for scripvec. The model cannot invent free-form text; it can only fill values against a schema you provide. Candidate uses include front-end natural-language-to-CLI-flag translation and backend action dispatch.

## Why this could fit scripvec

- The scripvec CLI is ADR-007-shaped: every subcommand and flag is fully specified, every value is either a constrained enum (mode, volume, book, format) or a bounded scalar (integers, strings). That is exactly the schema regime FunctionGemma excels at.
- The web front-end (cr-010) would benefit from a "just tell it what you want" input that translates natural language into a `scripvec query` invocation — `"verses where Moroni talks about faith, skipping the famous Hebrews passages"` → `--mode hybrid --speaker Moroni --exclude "Hebrews 11"`. FunctionGemma is a strong fit because it cannot hallucinate flags that do not exist in the schema.

## Distant-future; parked

This CR exists only so the idea is not lost. No mechanism, no acceptance gate, no timeline. Pick up when the CLI surface has stabilized and the front-end is past its own MVP.

## Decision

Not yet decided. Drafting.

## Audit log

- 2026-04-20 — created as `drafting`.
