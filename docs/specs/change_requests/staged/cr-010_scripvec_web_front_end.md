---
id: 010
title: Scripvec web front-end calling the CLI
status: staged
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
  - cr-011_cli_scripture_scope_filters.md
  - cr-012_cli_mode_aware_similarity_floor.md
  - cr-013_cli_retrieval_window_and_proximity_dedupe.md
  - cr-014_cli_vector_exclude_filter.md
  - cr-015_cli_power_user_retrieval_knobs.md
---

# CR-010: Scripvec web front-end calling the CLI

## Summary

Build a web front-end for scripvec that is a thin layer over the existing CLI. The front-end runs the CLI as a subprocess, consumes its JSON output, and renders scripture search results in a study-oriented UI. No separate backend service is introduced — the CLI is the backend.

## Motivation

The CLI is already well-shaped for programmatic consumption (ADR-007): every command takes all of its options in a single non-interactive invocation and emits structured JSON. That shape is a natural fit for a thin web front-end that can present the same capability to a human reader studying scripture.

Treating the CLI as the backend avoids a second interface surface for the same retrieval logic — every feature that ships in the CLI is automatically reachable from the front-end, and every CLI option (see the staged CLI CRs in the references) is a candidate for a UI control.

## Proposed change

### Architecture

- A new app at `apps/scripvec_web/` (name open). Separate from `apps/scripvec_cli/`.
- The front-end invokes `scripvec query` (and, where appropriate, `scripvec index list`, `scripvec version`) as subprocesses.
- Responses are consumed as JSON per ADR-007 and rendered in the UI.
- No HTTP service shim over the CLI is introduced at MVP; if one is needed later (e.g., for remote hosting), it is a separate CR.

### UI surface

- A query input with controls that mirror the CLI options as they ship: mode, volume/book/range (cr-011), similarity floor (cr-012), retrieval window and dedupe (cr-013), exclude text (cr-014), hybrid weight and cross-reference expansion (cr-015).
- A results panel rendering each hit with its reference, verse text, score (when `--show-scores` is on), and any per-hit payload the CLI returns (window, cross-references, etc.).
- A feedback control on each hit that shells out to `scripvec feedback`.

### Chapter / verse context display — not driven by `--window`

The front-end will include the ability to display surrounding chapter or verse context around each search hit. **This feature is not powered by the CLI's retrieval window option (cr-013).** The two are independent axes:

- `--window` (cr-013) returns ±N verses bundled inside each search result. That is a *search-time* payload — it travels with the hit in the JSON response.
- The front-end's context display is an *on-demand* lookup. After rendering a search result, the front-end independently queries the corpus database by canonical reference to fetch the desired span of verses (a whole chapter, ±N verses, etc.). The search response itself stays lean.

This split is intentional:

1. Keeps the search response small and predictable regardless of how much context the user wants to see.
2. Lets the UI make presentation choices (show full chapter, collapse to ±3, etc.) without re-running the search.
3. Lets the CLI stay focused on retrieval; chapter-by-reference lookups are a different query shape and do not belong in the query response.

Both mechanisms coexist: a user who turns on `--window` sees the CLI-bundled window in the payload, *and* can still expand to a full chapter via the front-end's on-demand lookup. The two do not conflict, and neither replaces the other.

### CLI contract stability

The front-end depends on the JSON shape defined by ADR-007 and extended by the staged CLI CRs. Any breaking change to that shape must go through ADR-007's schema-change rules; the front-end treats additive fields as no-ops until it adds rendering for them.

## Impact on referenced docs

- **ADR-007:** the front-end is the first non-agent consumer of the ADR-007 contract. The contract itself is not changed — the front-end is another client of it. If the front-end needs fields that do not exist yet, those fields land via CLI CRs (one of cr-011..cr-015 or a new CR), not via ad-hoc additions here.
- **Principle 001:** the front-end does not add a second retrieval path; it renders the CLI's retrieval output. Eval remains a CLI concern.
- **cr-011..cr-015:** the front-end is the primary human consumer of these flags. Any UI control maps to exactly one CLI flag. Surface parity is the design goal; where a CLI flag has no natural UI control, the UI exposes the flag name in a "raw" override input so power users can still reach it.

## Decision

Staged.

## Audit log

- 2026-04-20 — created as `staged`.
