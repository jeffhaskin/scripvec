# docs/specs/change_requests/

Proposed changes to scripvec — its architecture, its corpora, its specs, its tooling. A change request (CR) is a decision that has been articulated but not yet executed.

> Orientation only. If a `domain_policies/` subfolder is added later, read it before authoring a CR.

## Layout — folder-per-status

Every CR lives inside a status subfolder. Moving between statuses means **moving the file between folders** — no separate index is maintained. To see the roster, list the subfolders.

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

**Status meanings in detail:**

- **drafting** — the CR is still being written. Scope, motivation, and impact may still change materially.
- **pending** — submitted to the engineer for a decision. No edits to the proposal while pending; discussion happens around it.
- **accepted** — the engineer has approved the CR. It is ready to be scheduled, but is not yet next-up.
- **staged** — accepted CRs that are **queued as the next work to pick up.** This is the working queue. When capacity opens, a staged CR is the one chosen next.
- **in_progress** — actively being executed. There should rarely be more than one or two in_progress CRs at a time at solo-dev scale.
- **completed** — executed successfully. The CR records the outcome and any deviations from the plan.
- **locked** — frozen as a historical record. No further edits. Used when a CR represents a decision that is now immutable.
- **archived** — not executed. Dropped, superseded, or deferred indefinitely. Kept so that the decision not to proceed is itself auditable.

## File naming

```
cr_NNN_<slug>.md
```

- `cr_` — **required** type-prefix for change requests, per `../../policies/002_item_numbering_convention.md` clause 4.
- `NNN` — zero-padded number (3 digits per `../../policies/002_item_numbering_convention.md`), append-only across all statuses. The number never changes once assigned.
- `<slug>` — short snake_case descriptor.

Example: `cr_001_vector_search_mvp.md`.

**Status is not in the filename.** It is implicit in which status folder the file sits in. When status changes, the file moves between folders; the name does not change. (This is a deliberate departure from the ADR convention, where status *is* part of the filename.)

Filenames comply with `../../policies/001_file_and_folder_naming_convention.md` (underscores, no spaces).

## Template

Every CR follows this structure:

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

The `references` field, the **Impact on referenced docs** section, and the **Audit log** section are not optional — they are how a CR stays consistent with the rest of the documentation tree and how its lifecycle stays auditable.

## Neighbors

- `../adrs/` — architectural decisions. A CR that conflicts with an accepted ADR must be revised, or the ADR must be amended first. Never both silently.
- `../../roadmap/roadmap.md` — the narrative order of work. Staged CRs should reflect the roadmap's current front.
- `../vision_tree/` — the long-range vision tree a CR ultimately serves.
