# docs/specs/adrs/

Architecture Decision Records (ADRs) for scripvec. Each file captures one architectural decision — its context, the decision itself, and its consequences — in a form that outlives the conversation that produced it.

## Required reading before touching this folder

**Before adding, modifying, or removing any ADR in this folder, read the ADR domain policies at `../../policies/domain_policies/adrs/`.** Those policies govern what belongs inside an ADR and what does not. The canonical example is `pl-001_adrs_lock_policies_not_values.md`, which forbids stipulating numeric values for tunable parameters inside ADRs or CRs.

This requirement is not optional. An ADR change that violates a domain policy is a review-grade rejection — authored or edited by a human, by an agent, or by the engineer themselves. Reading the domain policies is how the author knows ahead of time whether their change is in bounds.

When a new ADR domain policy is added under `../../policies/domain_policies/adrs/`, every subsequent ADR touch is subject to it. There is no grandfathering of in-progress ADR drafts that predate a policy — the policy applies at the moment the ADR is committed.

## What lives here

One markdown file per architectural decision. An ADR records a categorical choice about the system's shape — a library pick, a protocol pick, a structural discipline, a pipeline topology, a failure posture. It does not record tunable parameter values (see `pl-001_adrs_lock_policies_not_values.md`), transient project state, or work-in-progress notes.

## File naming

```
NNN_<status>_<slug>.md
```

- `NNN` — zero-padded three-digit number, append-only across the ADR sequence, per `../../policies/pl-002_item_numbering_convention.md`.
- `<status>` — one of `drafting`, `pending`, `accepted`, `superseded`. Status **is** part of the ADR filename (a deliberate departure from CRs, where status is folder-implicit).
- `<slug>` — short snake_case descriptor of the decision.
- No type-prefix: ADRs are the default numeric stream in their folder. Per `../../policies/pl-002_item_numbering_convention.md` clause 4, no `adr-` type-prefix is currently authorized.

Example: `008_accepted_cross_encoder_reranker_defaults.md`.

Filenames comply with `../../policies/pl-001_file_and_folder_naming_convention.md` (underscores, no spaces).

## Required structure

Every ADR carries the following sections, in order. Omitting any of them is a review-grade rejection:

- **Status** — the current status (uppercase): `DRAFTING`, `PENDING`, `ACCEPTED`, `SUPERSEDED`.
- **Created** — ISO date of initial authoring.
- **Modified** — ISO date of most recent amendment.
- **Supersession** — `*Supersedes:*` and `*Superseded by:*` lines, each either naming another ADR or `none`.
- **Date** — the decision date (usually matches `Created` at initial authoring).
- **Deciders** — the human or humans with decision authority at record time.
- **Context and Decision Drivers** — why this decision is being made; the forces at play.
- **Decision** — what is decided. The load-bearing section. Expresses policies and structural choices, not tunable values (see `pl-001_adrs_lock_policies_not_values.md`).
- **Consequences** — positive and negative downstream effects.
- **Validation** — how the decision is checked in code, review, or tests.
- **Links** — the other ADRs, CRs, principles, policies, or external references this ADR composes with.
- **Conflicts surfaced** — any tension this ADR creates or acknowledges with other accepted docs. `None.` is an acceptable value.
- **Amendment Log** — append-only table of edits with `Date | Type | Change | Author`. `Type` is typically `created`, `amended`, `accepted`, `superseded`.

## Status lifecycle

- **DRAFTING** — actively being composed. Content may still change materially.
- **PENDING** — submitted; awaiting decision.
- **ACCEPTED** — the decision is in force. Every accepted ADR is binding on all downstream work.
- **SUPERSEDED** — the decision has been replaced by a later ADR. The file is retained as history; the `Superseded by:` line names its replacement.

Status transitions are recorded in the Amendment Log. An ADR is not renamed to reflect a status change at the same rate as its `Status` field — by convention the filename's `<status>` reflects the current status and is updated when status changes (unlike CRs, where status is folder-implicit).

## Neighbors

- `../change_requests/` — change requests. A CR that conflicts with an accepted ADR must be revised, or the ADR must be amended first. Never both silently. See `../../policies/pl-003_change_request_references_use_filename_only.md` for citation rules.
- `../vision_tree/` — the long-range vision tree the architecture ultimately serves.
- `../../policies/domain_policies/adrs/` — **the domain policies that govern this folder's content.** Required reading before any edit here.
- `../../principles/` — the philosophical dispositions the architecture expresses. Principles inform ADRs; ADRs express principles operationally.
- `../../roadmap/roadmap.md` — the narrative order of work, built on top of the architecture these ADRs record.
