# 001 — Change-Request Naming, Template, and Lifecycle

## Rules

### File naming

1. Change-request files use the form `cr-NNN_<slug>.md`, where:
   - `cr-` is the required type-prefix (per `../../../policies/pl-002_item_numbering_convention.md` clause 4).
   - `NNN` is a zero-padded three-digit numeric prefix (per `../../../policies/pl-002_item_numbering_convention.md`). Numbers are append-only across all statuses; a number assigned to a CR never changes and is never reused.
   - `<slug>` is a short snake_case descriptor.
2. **Status is not encoded in the filename.** Status is implicit in which status subfolder the file sits in. Renaming a CR as it moves between statuses is forbidden — the file moves between folders, the name does not change.
3. Filenames otherwise comply with `../../../policies/pl-001_file_and_folder_naming_convention.md` (underscores, no spaces).

### Folder-per-status layout

4. Every change request lives inside exactly one status subfolder of `docs/specs/change_requests/`:

```
change_requests/
├── drafting/       still being composed
├── pending/        submitted; awaiting engineer decision
├── accepted/       approved; not yet prioritized for imminent work
├── staged/         approved and queued as the next CRs to pick up
├── in_progress/    approved and actively being executed
├── completed/      executed successfully; outcome recorded
├── locked/         frozen as historical record; no further edits
└── archived/       not executed — dropped or superseded; kept for the record
```

5. Status transitions happen by **moving the file between status subfolders**. No separate status index is maintained; the subfolder listing is the roster.
6. Status meanings:
   - **drafting** — the CR is still being written. Scope, motivation, and impact may still change materially.
   - **pending** — submitted to the engineer for a decision. No edits to the proposal while pending; discussion happens around it.
   - **accepted** — the engineer has approved the CR. It is ready to be scheduled, but is not yet next-up.
   - **staged** — accepted CRs queued as the next work to pick up. This is the working queue.
   - **in_progress** — actively being executed. There should rarely be more than one or two in-progress CRs at a time at solo-dev scale.
   - **completed** — executed successfully. The CR records the outcome and any deviations from the plan.
   - **locked** — frozen as a historical record. No further edits.
   - **archived** — not executed. Dropped, superseded, or deferred indefinitely. Kept so that the decision not to proceed is itself auditable.

### Required CR structure

7. Every change request **must** include, in this order:

```markdown
---
id: NNN
title: short descriptive title
status: drafting          # drafting | pending | accepted | staged | in_progress | completed | locked | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
references:
  - docs/specs/adrs/<file>.md
  - docs/policies/<file>.md
  - docs/principles/<file>.md
  - docs/roadmap/roadmap.md
---

# CR-NNN: <title>

## Summary

One paragraph. What is being proposed, in plain terms.

## Motivation

Why this change. What problem, opportunity, or decision drives it.

## Proposed change

What specifically would change. Concrete enough to implement against.

## Impact on referenced docs

Which specs, policies, ADRs, principles, or roadmap entries does this touch? Does it conflict with any of them? If it conflicts, record whether the CR should be revised or the referenced docs should be updated, and why. **Never silently land a conflicting CR.**

## Decision

Filled in when the CR reaches `accepted` or `locked`. Records who decided, when, and any conditions attached.

## Audit log

Append-only record of status transitions. Every status change adds a new line; earlier lines are never rewritten. ISO-8601 timestamps.

- YYYY-MM-DDTHH:MM:SSZ — created as `drafting`
- YYYY-MM-DDTHH:MM:SSZ — `drafting` → `pending`
- ...
```

8. The `references` field, the **Impact on referenced docs** section, and the **Audit log** section are not optional. They are how a CR stays consistent with the rest of the documentation tree and how its lifecycle stays auditable.

### Cross-referencing

9. References to a CR from any document follow `../../../policies/pl-003_change_request_references_use_filename_only.md` — cite by filename only, never by path or status folder.

## Why

- **The CR corpus is load-bearing documentation.** It is the record of what has changed, what will change, and what was considered and rejected. A shared structure makes every CR legible in the same way, and makes status a lookup instead of a search.
- **The filename is stable; the status is not.** Encoding only the number and slug in the filename keeps every cross-reference unbroken as CRs move through their lifecycle. Status-in-filename was considered and rejected because it would invalidate links on every status change.
- **Required sections catch silent conflicts.** The *Impact on referenced docs* section is the mechanism by which a CR that would contradict an ADR, a policy, or another CR is forced to surface the conflict rather than land silently.
- **The audit log keeps the lifecycle honest.** A CR that arrives in `accepted/` without an audit-log entry for each prior status is a CR whose history has been rewritten — auditability fails closed, not open.

## Examples

**Correct:**

- `docs/specs/change_requests/drafting/cr-001_vector_search_mvp.md`
- `docs/specs/change_requests/accepted/cr-002_mvp_retrieval_stack.md`
- `docs/specs/change_requests/pending/cr-003_cross_encoder_reranker.md`

**Incorrect:**

- `docs/specs/change_requests/cr-001_vector_search_mvp.md` (missing status folder)
- `docs/specs/change_requests/drafting/cr_001_vector_search_mvp.md` (underscore between `cr` and number; must be dash)
- `docs/specs/change_requests/drafting/001_vector_search_mvp.md` (missing `cr-` type-prefix)
- `docs/specs/change_requests/drafting/cr-001_drafting_vector_search_mvp.md` (status encoded in filename)

## Validation

- A listing of every status subfolder should show only files beginning with `cr-` and a `.gitkeep` where empty; other filenames are violations.
- Every CR's frontmatter `status` field matches the status subfolder it resides in. A mismatch is a bug in the CR.
- Every CR contains the eight required sections (frontmatter + Summary + Motivation + Proposed change + Impact on referenced docs + Decision + Audit log). Missing sections fail review.
