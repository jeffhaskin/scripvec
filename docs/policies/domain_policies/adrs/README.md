# docs/policies/domain_policies/adrs/

Domain policies scoped to the Architecture Decision Record (ADR) system at `docs/specs/adrs/`. These are the meta-rules for how ADRs are authored, what belongs inside them, and what does not.

> Orientation only. The rules themselves live in the numbered policy files in this folder.

## What lives here

Files in this folder are policies whose subject is the ADR system — rules that govern the content, scope, authoring, or lifecycle of files under `docs/specs/adrs/`. Change Requests (`docs/specs/change_requests/`) sit in a closely-related domain and may be in-scope here by explicit extension in a policy's text (see `pl-001_adrs_lock_policies_not_values.md` for the canonical example). Rules about project code, corpora, retrieval, or anything outside the ADR/CR meta-layer belong elsewhere — either in a different domain sub-folder or in the top-level `docs/policies/` folder.

## File naming

Policies in this folder follow the repository's standard policy conventions:

- `pl-` type-prefix is required (per `../../pl-002_item_numbering_convention.md` clause 4, enforced recursively by `../pl-001_all_policy_filenames_use_pl_prefix.md`).
- Zero-padded numeric prefix after the type-prefix; the numeric sequence inside this sub-folder starts at 001 and is append-only within the sub-folder.
- Example: `pl-001_adrs_lock_policies_not_values.md`.

## Neighbors

- `../pl-001_all_policy_filenames_use_pl_prefix.md` — the recursive-naming rule that covers files in this folder too.
- `../` — other domain-policy sub-folders and the parent README that orients them.
- `../../` — the main policies folder, which hosts cross-cutting project policies.
- `../../../specs/adrs/` — the ADR corpus these policies govern.
