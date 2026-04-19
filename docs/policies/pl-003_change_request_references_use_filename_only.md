# 003 — Change-Request References Use Filename Only

## Rules

1. **Any** document in this repository that references a change request (under `docs/specs/change_requests/`) **must** cite the CR by its **filename only** — e.g., `cr-001_vector_search_mvp.md` — never by its full or partial path.
2. A reference **must not** include any status-folder segment (`drafting/`, `pending/`, `staged/`, `accepted/`, `in_progress/`, `completed/`, `locked/`, `archived/`).
3. A reference **may** additionally cite the CR by its **ID** (e.g., "CR-001") for prose readability; the filename remains the canonical, machine-greppable link.

This rule applies to every document type — ADRs, roadmap entries, other CRs, specs, principles, READMEs, and anything else that may need to link to a change request.

## Why

The CR **filename is stable**. Per policy 002, the numeric prefix is append-only (never reused, never renumbered); per policy 002 clause 4, the `cr-` type-prefix is required; and per the change-requests README, status is not in the filename. Filenames therefore never change for the life of the CR.

The CR **path is not stable**. CRs move between status subfolders as they progress through their lifecycle. Any document that cited a CR's path at authoring time would become silently wrong the moment the CR's status changed. Silent staleness in cross-references — especially in accepted ADRs or a living roadmap — is exactly the kind of rot this policy prevents.

## Examples

**Correct:**

- `` See CR-001 (`cr-001_vector_search_mvp.md`) — MVP scope. ``
- `` - `cr-001_vector_search_mvp.md` — MVP scope. ``

**Incorrect:**

- `` - `docs/specs/change_requests/drafting/cr-001_vector_search_mvp.md` — MVP scope. ``
- `` - `docs/specs/change_requests/cr-001_vector_search_mvp.md` ``
- `` - `change_requests/drafting/cr-001_vector_search_mvp.md` ``

## Finding the file

A reader who wants to open a CR cited by filename uses the repository's existing search — `find docs/specs/change_requests -name '<filename>'`, or the equivalent in their editor. The status-folder segment, when needed, is recovered by one search; the cost of that search is strictly lower than the cost of silently-stale references scattered across the docs tree.
