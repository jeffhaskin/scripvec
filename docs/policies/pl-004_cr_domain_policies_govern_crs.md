# 004 — Change-Request Domain Policies Govern Change Requests

## Rules

1. The authoritative rules for change-request authoring, naming, templating, lifecycle, cross-referencing, and any other CR-specific concern live in `docs/specs/change_requests/domain_policies/`.
2. Those domain policies **govern** change requests. Where a rule in `docs/specs/change_requests/domain_policies/` conflicts with a top-level policy under `docs/policies/`, the CR domain policy wins within the change-request domain.
3. Top-level policies continue to apply to change requests **only where no CR domain policy addresses the same concern**. Nothing in this policy exempts change requests from top-level policies that the CR domain policies are silent about.
4. This policy **supersedes `pl-001_file_and_folder_naming_convention.md`** for change requests: where a CR domain policy defines a naming or layout rule that differs from the top-level pl-001 rule, the CR domain policy is authoritative. Top-level pl-001 remains unchanged and continues to govern every domain other than change requests.

## Why

- **Locality beats repo-wide generality for load-bearing domains.** The change-request corpus is a distinct system with its own lifecycle, filename form, required sections, and cross-referencing rules. Placing those rules close to the artifacts they govern — in a domain-policies folder adjacent to the CRs themselves — makes them discoverable and easier to keep consistent with how CRs are actually written.
- **One authoritative location per concern.** Prior to this policy, CR-specific rules were mixed between top-level policies and the CR README. That split invited silent drift between the two. Consolidating CR rules into `change_requests/domain_policies/` gives every CR rule exactly one home.
- **Predictable precedence.** When a rule appears in both a top-level policy and a CR domain policy, a reader must know which wins. This policy makes that deterministic: inside the CR domain, domain policies win.

## Scope

- **Applies to:** files under `docs/specs/change_requests/` — i.e., every change request and every orientation or policy document that governs them.
- **Does not apply to:** any other document type (ADRs, the roadmap, principles, source code, corpora). Those continue to be governed by the top-level policies in `docs/policies/` unless and until a future domain-policy carve-out is created for them.

## Examples

- A CR domain policy specifies `cr-NNN_<slug>.md` as the required filename form for change requests. Top-level `pl-001` requires underscores instead of spaces across all files and folders. There is no conflict — the CR form uses underscores in the slug — but if a future tension arose, the CR domain policy would prevail within the CR domain.
- A CR domain policy specifies eight required sections for every CR. No top-level policy addresses CR sections. The CR domain policy is authoritative on its own terms; top-level policies have nothing to say.
- A top-level policy defines repository-wide date formatting. The CR domain policies are silent on date formatting. The top-level policy applies to CRs (per rule 3 above).

## Created

- 2026-04-19T23:04:32+02:00 — initial authoring.
