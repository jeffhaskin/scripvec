# docs/specs/change_requests/domain_policies/

Policies that govern change requests — how CR files are named, what sections every CR must contain, how status transitions work, and any other meta-rule that applies to the CR system itself.

> Orientation only. The rules themselves live in the numbered policy files in this folder.

## What lives here

Files in this folder are policies whose subject is the change-request system — i.e., rules that apply to authoring, naming, layout, lifecycle, or cross-referencing of files under `docs/specs/change_requests/`. If a rule governs project code, corpora, retrieval, or anything outside the change-request system, it belongs in `../../../policies/`, not here.

## Precedence

Per `../../../policies/pl-004_cr_domain_policies_govern_crs.md`, the policies in this folder govern change requests. Where a rule here conflicts with a top-level policy under `docs/policies/`, the rule here wins within the CR domain.

## File naming

Files in this folder use the `pl-` type-prefix and zero-padded numeric prefix, consistent with the rest of the policy corpus — e.g., `pl-001_cr_naming_template_and_lifecycle.md`.

## Neighbors

- `../` — the change-requests folder this domain policy governs.
- `../../../policies/` — top-level policies. CR domain policies take precedence over top-level policies within the CR domain per `pl-004`; where a CR domain policy is silent, top-level policies continue to apply.
- `../../../policies/domain_policies/` — the parallel construct for the policies system itself.
