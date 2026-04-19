# docs/policies/domain_policies/

Policies about policies. These are the rules for how the `docs/policies/` folder itself is used — how policy files are named, how they are authored, how they are amended, and any other meta-rule that governs the policies tree.

> Orientation only. The rules themselves live in the numbered policy files in this folder.

## What lives here

Files in this folder are policies whose subject is the policies system — i.e., rules that apply to the authoring, naming, layout, or lifecycle of files under `docs/policies/`. If a rule governs project code, corpora, retrieval, or anything outside the policies system, it belongs in the parent `docs/policies/` folder, not here.

## File naming

Files in this folder follow the same conventions as any other policy:

- `pl-` type-prefix is required (per `../pl-002_item_numbering_convention.md` clause 4).
- Zero-padded numeric prefix after the type-prefix.
- Example: `pl-001_all_policy_filenames_use_pl_prefix.md`.

## Recursive application

The rules in this folder apply to the `docs/policies/` tree as a whole. That includes the files in this very folder — `domain_policies/` is itself under `docs/policies/`, so a policy in here that says *"all policies get a `pl-` prefix"* applies to the files in here too. This recursion is deliberate.

## Neighbors

- `../` — the main policies folder, containing cross-cutting project policies. This folder's rules govern how those files are authored and named.
