# 002 — Pre-staged Change Requests May Contradict Each Other

## Rules

1. Change requests in any pre-staged status — **drafting**, **pending**, or **accepted** — are allowed to contradict each other, contradict accepted ADRs, contradict accepted policies, contradict accepted CRs in `staged/`, `in_progress/`, or `completed/`, and contradict each other's proposed changes.
2. Pre-staged CRs are a **menu of possibilities**, not a roster of commitments. Their job is to surface ideas, capture trade-offs, and let the engineer compare alternatives against one another. Mutual contradiction is expected and welcome at this stage.
3. Contradiction becomes a problem only at the **staged** boundary. A CR moving from `accepted/` into `staged/` is the moment the engineer commits to executing it. At that boundary, the CR's *Impact on referenced docs* section must be reviewed: any conflict with an accepted ADR, an accepted policy, or another CR in `staged/`, `in_progress/`, or `completed/` must be resolved — by revising the CR, by amending the conflicting doc, or by archiving one of the two.
4. After a CR enters `staged/`, the no-silent-conflict rule from `pl-001_cr_naming_template_and_lifecycle.md` clause 8 applies in full. Subsequent CRs that contradict a staged-or-later CR must surface the conflict in their *Impact on referenced docs* section and be revised or archived before they themselves can stage.

## Why

- **Pre-staged CRs are inventory, not policy.** Drafting a CR is a low-cost way to record an idea, a hypothesis, or an alternative path. Forcing every drafted CR to be self-consistent with every other drafted CR would either (a) collapse the inventory to one path at a time, defeating the point, or (b) generate constant rewriting churn as new ideas land. Both outcomes destroy the value of having a menu.
- **Contradiction is information.** Two drafted CRs that propose mutually-exclusive approaches to the same problem are a useful artifact: they make the trade-off legible. Suppressing the contradiction by forcing one to be archived before the other is drafted would erase the comparison.
- **The commitment moment is staging, not drafting.** `staged/` is the working queue — the CRs the engineer has decided to actually execute. That is the right gate to enforce coherence with the rest of the documentation tree. Earlier gates would be premature; later gates would be too late.
- **The lifecycle in `pl-001` already separates ideation from commitment.** This policy makes the implication explicit so a contributor or agent does not, in good faith, refuse to draft a CR because it appears to conflict with another drafted or accepted CR.

## Scope

This policy applies to every change request under `docs/specs/change_requests/`. It modifies how clause 8 of `pl-001_cr_naming_template_and_lifecycle.md` is enforced: clause 8's "never silently land a conflicting CR" remains binding, but the *moment* at which the conflict must be resolved is the `accepted/ → staged/` transition, not earlier.

## Examples

**Allowed:**

- `cr-007_multiverse_window_retrieval.md` (drafting) and `cr-009_windowed_verse_embeddings.md` (drafting) propose structurally different responses to the same problem (verse-too-short for dense retrieval). Both are valid drafted CRs. Neither has to be archived before the other can be drafted.
- A drafted CR that contradicts an accepted ADR — e.g., a CR proposing parallel embedding calls in violation of ADR-006. Drafted is fine; staging it would require either revising the CR or amending ADR-006 first.
- An accepted CR sitting in `accepted/` whose proposed change overlaps with another accepted CR in `accepted/`. Both can sit in `accepted/` indefinitely; the conflict is forced to resolve when one of them moves into `staged/`.

**Not allowed:**

- A CR in `staged/` that silently contradicts another CR in `staged/` or `in_progress/`. The conflict must be surfaced in *Impact on referenced docs* and resolved before staging — by revising the CR, amending the conflicting CR or doc, or archiving one of them.

## Validation

- A reviewer of an `accepted/ → staged/` PR must check the CR's *Impact on referenced docs* section against every CR currently in `staged/`, `in_progress/`, or `completed/`, and against every accepted ADR and accepted policy. An undeclared conflict is a review-grade rejection.
- A drafted or accepted CR is **not** rejected for conflicting with another drafted, pending, or accepted CR. Reviewers who flag such conflicts are pointed at this policy.
