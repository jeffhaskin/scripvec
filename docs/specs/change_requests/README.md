# docs/specs/change_requests/

Proposed changes to scripvec — its architecture, its corpora, its specs, its tooling. A change request (CR) is a decision that has been articulated but not yet executed.

> Orientation only. The rules that govern change requests — filename form, required sections, status-folder layout, and cross-referencing — live in `domain_policies/` and take precedence over top-level policies for CR matters per `../../policies/pl-004_cr_domain_policies_govern_crs.md`.

## Layout

Change requests live in one of eight status subfolders. The current file sits in whichever subfolder matches its status; status transitions are file moves between folders.

```
change_requests/
├── drafting/       still being composed
├── pending/        submitted; awaiting engineer decision
├── accepted/       approved; not yet prioritized for imminent work
├── staged/         approved and queued as the next CRs to pick up
├── in_progress/    approved and actively being executed
├── completed/      executed successfully; outcome recorded
├── locked/         frozen as historical record; no further edits
├── archived/       not executed — dropped or superseded; kept for the record
└── domain_policies/  policies that govern this folder itself
```

Folder-per-status keeps the roster visible as a directory listing. Status meanings, filename form, and the required CR template are specified authoritatively in `domain_policies/pl-001_cr_naming_template_and_lifecycle.md`.

## Neighbors

- `domain_policies/` — authoritative rules for CR authoring, naming, lifecycle, and cross-referencing.
- `../adrs/` — architectural decisions. A CR that conflicts with an accepted ADR must be revised, or the ADR must be amended first. Never both silently.
- `../../roadmap/roadmap.md` — the narrative order of work. Staged CRs should reflect the roadmap's current front.
- `../vision_tree/` — the long-range vision tree a CR ultimately serves.
