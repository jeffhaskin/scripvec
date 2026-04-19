# 002 — Item Numbering Convention

## Rules

1. All sequentially numbered items in this repo — policies, change requests, ADRs, vision-tree entries, and any other numbered item type — carry a zero-padded numeric prefix that uniquely identifies the item within its sequence.
2. The default filename form is `NNN_<rest>.md` — zero-padded numeric prefix, underscore, rest of the name.
3. Specific item types **may** carry a type-prefix before the numeric prefix. When a type-prefix is used, the filename form is `<type>_NNN_<rest>.md`. The type-prefix is a short, lowercase, snake_case identifier.
4. Type-prefixes currently authorized (update this list when adding or removing a type-prefix):
   - **Change requests** — `cr_` is **required**. Example: `cr_001_vector_search_mvp.md`.
5. Use **three digits** by default (e.g., `001_`, `042_`, `999_`). Extend to **four digits** only when a sequence exceeds 999 entries.
6. The numeric prefix is **append-only** across a sequence. Once assigned, a number is never reused, never renumbered, and never changes — even if the file is renamed, moved between folders, or superseded.

## Examples

- `001_file_and_folder_naming_convention.md` (policy — no type-prefix)
- `002_item_numbering_convention.md` (policy — no type-prefix)
- `cr_001_vector_search_mvp.md` (change request — `cr_` required)
- `001_accepted_no_silent_failures.md` (ADR — no type-prefix currently authorized)
- `000_overall_vision.md` (vision tree — no type-prefix)
