# docs/policies/domain_policies/

Domain-scoped policies — rules that govern a specific repository sub-system of the meta-layer (the policies system itself, the ADR system, the change-request system, and similar). Each sub-domain whose rules are non-trivial gets its own sub-folder. Cross-cutting project rules (those that govern code, corpora, retrieval, or anything outside the meta-layer) belong in the parent `docs/policies/` folder, not here.

> Orientation only. The rules themselves live in the numbered policy files under each sub-domain.

## Layout

```
domain_policies/
├── pl-001_all_policy_filenames_use_pl_prefix.md   # policies-about-policies, top-level for historical reasons
└── adrs/                                          # domain policies for ADRs and CRs
    └── pl-001_adrs_lock_policies_not_values.md
```

Additional sub-domains (e.g., `change_requests/`, `roadmap/`) may be added later when they accumulate their own rules.

## What lives here

Files under this tree are policies whose subject is a repository meta-system — i.e., rules that apply to the authoring, naming, layout, content, or lifecycle of files in a particular docs sub-tree. If a rule governs project code, corpora, retrieval, or anything outside the meta-layer, it belongs in the parent `docs/policies/` folder, not here.

## File naming

Files in this folder follow the same conventions as any other policy:

- `pl-` type-prefix is required (per `../pl-002_item_numbering_convention.md` clause 4).
- Zero-padded numeric prefix after the type-prefix.
- Example: `pl-001_all_policy_filenames_use_pl_prefix.md`.

## Recursive application

The rules in this tree apply to whichever docs sub-system they name. Some of those rules — notably the `pl-` filename prefix rule — also apply recursively to files inside this folder and its sub-folders. A policy in here that says *"all policies get a `pl-` prefix"* applies to the files in here and in every sub-domain sub-folder too. This recursion is deliberate.

## Neighbors

- `../` — the main policies folder, containing cross-cutting project policies. This folder's rules govern how those files are authored and named.
