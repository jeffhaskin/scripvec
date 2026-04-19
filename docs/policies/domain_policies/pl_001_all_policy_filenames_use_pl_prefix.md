# 001 — All Policy Filenames Use the `pl_` Prefix

## Rules

1. Every policy file under `docs/policies/` **must** begin with the type-prefix `pl_`, followed by its zero-padded numeric prefix, followed by the rest of the filename. The resulting form is `pl_NNN_<rest>.md`.
2. This requirement is **recursive**: it applies to files directly under `docs/policies/` **and** to files nested in any subfolder of `docs/policies/`, including `docs/policies/domain_policies/` and any future subfolders created under `docs/policies/`.
3. A file in the policies tree that does **not** begin with `pl_` is treated as not-a-policy — either it is a README (permitted), a non-policy supporting document (permitted if its purpose is clear from context), or it is in violation of this policy and must be renamed.
4. The `pl_` prefix authorization lives in `../pl_002_item_numbering_convention.md` clause 4; this policy is the authoritative requirement for using it.

## Why

- **Visual identification.** With multiple type-prefixed document streams in the repo (`cr_` for change requests, `pl_` for policies, and potentially more), a naked-numeric filename in a search result is ambiguous about what it is. The prefix makes the type instantly legible in any listing, diff, or grep.
- **Greppable and machine-addressable.** `grep -l pl_0 docs/policies` surfaces every policy. `find docs -name 'pl_*.md'` surfaces the full policy corpus across any nested subfolder. Without the prefix, these queries require knowing the exact folder path.
- **Consistent with the established pattern.** Change requests already use `cr_` (per `../pl_002_item_numbering_convention.md`). Applying the same pattern to policies removes the inconsistency and avoids a special case.
- **Recursion prevents drift.** Nested subfolders under `docs/policies/` (such as `domain_policies/`) are still policies. Allowing them to drop the prefix would create two classes of policy file and invite confusion.

## Examples

**Correct:**

- `docs/policies/pl_001_file_and_folder_naming_convention.md`
- `docs/policies/pl_002_item_numbering_convention.md`
- `docs/policies/domain_policies/pl_001_all_policy_filenames_use_pl_prefix.md`

**Incorrect:**

- `docs/policies/001_file_and_folder_naming_convention.md` (missing `pl_`)
- `docs/policies/domain_policies/001_naming.md` (missing `pl_`; also not nested-safe)
- `docs/policies/policy_001_x.md` (wrong type-prefix; `pl_` is required)

## Exceptions

- `README.md` files in `docs/policies/` and its subfolders are **not** policies; they are orientation documents. They keep the literal name `README.md` and do **not** receive a `pl_` prefix.
- Other non-policy supporting documents (e.g., a future index or a script referenced by a policy) may live in the policies tree without a `pl_` prefix only if their non-policy nature is unambiguous. If in doubt, move the file out of `docs/policies/`.

## Validation

- A listing of `docs/policies/` and all subfolders should show only `README.md`, subfolder entries, and files beginning with `pl_`. Any other filename is either a violation or a permitted non-policy exception that must be obvious from context.
