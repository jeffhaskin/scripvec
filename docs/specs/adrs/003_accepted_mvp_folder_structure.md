# ADR-003: MVP folder structure

## Status

ACCEPTED

## Created

2026-04-19

## Modified

2026-04-19

## Supersession

*Supersedes:* none
*Superseded by:* none

## Date

2026-04-19

## Deciders

Jeff Haskin — engineer, sole decision authority at time of record.

## Context and Decision Drivers

scripvec is a greenfield monorepo with no code. The Monorepo Architect persona, channeled on 2026-04-19, recommended a folder tree appropriate for a solo developer building an MVP retrieval system. The engineer reviewed the recommendation and approved the folder shape. This ADR records that approval and locks the structure so that the next contribution commits into the agreed shape rather than drifting.

**Decision drivers:**

- The vision (`docs/specs/vision_tree/000_overall_vision.md`) and MVP CR (`cr-001_vector_search_mvp.md`) describe a system with distinct bounded contexts: corpus ingest, citation parsing, retrieval (embeddings + index + BM25 + hybrid), and evaluation. Those are the MVP's domains.
- A future UI or other deployable is plausible; `apps/` exists now even with a single app so that the shape teaches future-self where logic lives (`packages/`) versus where wiring lives (`apps/`).
- Corpora and built indexes are artifacts, not code. They belong in a sibling of `apps/` and `packages/`, not inside either.
- Out-of-scope items from CR-001 (Q&A, Webster's 1828, commentary-as-vectors, Bible corpus) must **not** appear as empty folders. A placeholder folder teaches the next contributor that speculative work belongs there.

## Decision

The scripvec monorepo uses the following folder structure at the repository root:

```
scripvec/
  apps/
    scripvec_cli/          # the one deployable at MVP: query in, verses out
      README.md
  packages/
    corpus_ingest/         # normalized-verse records from canonical source text
      README.md
    reference/             # citation parse / normalize (e.g., "Alma 32:21", "D&C 88:118")
      README.md
    retrieval/             # embeddings, vector index, BM25, hybrid, query path
      README.md
    eval/                  # held-out query set, recall@k, nDCG harness
      README.md
  data/
    raw/                   # canonical corpus drops (gitignored past a pinned snapshot)
    indexes/               # built artifacts, versioned by config hash (gitignored)
    eval/                  # query set + graded relevance (checked in)
  docs/                    # already exists — principles/, policies/, specs/
  scripts/                 # one-off CLIs: build_index, run_eval, etc.
  README.md
  CODEOWNERS
  .editorconfig
```

**Dependency graph (linear):**

- `apps/scripvec_cli` depends on `packages/retrieval`.
- `packages/retrieval` depends on `packages/corpus_ingest` and `packages/reference`.
- `packages/eval` depends on `packages/retrieval`.
- `packages/corpus_ingest` and `packages/reference` depend on nothing in-repo.

**Naming rules specific to this structure:**

- Folder names use underscores, lowercase, per policy `pl-001_file_and_folder_naming_convention.md`.
- Packages are **peer modules** with no inherent sequence; policy `pl-002_item_numbering_convention.md` governs ordered documents, not package folders. **Packages do not carry numeric prefixes.**
- If/when distribution names become relevant (PyPI, npm), scoped names (`@scripvec/retrieval` for npm, `scripvec-retrieval` for PyPI) may differ from the folder name. The folder name remains canonical inside the repo.
- Apps are named with a `scripvec_` prefix to make their role unambiguous (`scripvec_cli`, and any future `scripvec_web`, `scripvec_api`, etc.).

**Refusals — folders that will not exist:**

- `common/`, `utils/`, `shared/`, `core/`, `lib/`, `helpers/` — no catch-all packages. If code is genuinely shared between domains, the shared surface names a new domain or belongs in one of the existing ones.
- `src/` at the repo root — that is a single-project layout; scripvec is a monorepo.
- Placeholder folders for out-of-scope CR work (`qa/`, `webster/`, `commentary/`, `bible/`) — add these folders the day their CR opens, not before.

**READMEs — two-sentence minimum on creation day.** Every package and every app gets a `README.md` on the day it is created, containing at minimum:

1. What this is — one sentence naming the bounded context.
2. What it is allowed to import — one sentence naming its allowed in-repo dependencies.

If the second sentence cannot be written, the package is not ready to exist.

**Data folder conventions:**

- `data/raw/` is gitignored except for a single pinned snapshot reference (to be defined in a later CR) — corpora are reproducible from canonical source.
- `data/indexes/` is fully gitignored — indexes are deterministic from code + config + raw corpus and should not enter git.
- `data/eval/` **is** checked in — the query set and graded relevance are authored artifacts, not reproducible outputs.

## Consequences

**Positive:**

- The dependency graph is linear and draws cleanly on a napkin. Every package has an obvious home for its concerns.
- The shape teaches future-self the apps-vs-packages axis before a second app is added, making the eventual UI addition a folder-creation, not a refactor.
- Data artifacts are segregated from code, preventing accidental imports of raw corpus paths from application code.
- Out-of-scope work has no seductive empty folder to fill; when a future CR opens, its folder is a deliberate act, not a default.

**Negative:**

- Four packages plus one app is slightly more ceremony than a single-package layout. For a solo dev this is the floor at which monorepo shape pays off; there is a small legibility cost for the convenience of the axis being visible from day one.
- The discipline of *"no placeholder folders"* must be enforced at PR time — it is easier to add a folder than to remove one.
- `CODEOWNERS` with a single developer is boilerplate, but the persona's guidance to name ownership before it's ambiguous is worth the cost.

## Validation

- **Every new file commits into one of the folders named above.** A PR that creates a new top-level folder requires an amendment to this ADR.
- **Every package has a two-sentence README.** Checked at PR review time.
- **Dependency graph health.** Periodic check (manually or via `madge` if TypeScript / `pydeps` if Python) that no cycles have formed and no disallowed imports have appeared.

## Links

- `/data/projects/flywheel/personas/monorepo_architect.md` — source of the recommendation; see "Day-one tree" and "Why this shape."
- `docs/policies/pl-001_file_and_folder_naming_convention.md` — underscore rule applied to folder names here.
- `docs/policies/pl-002_item_numbering_convention.md` — referenced in the *packages carry no numeric prefix* clause.
- `docs/specs/adrs/002_accepted_no_role_splitting_in_packages.md` — package internals stay flat.
- `docs/specs/adrs/004_accepted_mvp_tooling_floor.md` — the build/workspace tooling that operates on this structure.
- `cr-001_vector_search_mvp.md` — MVP scope; every in-scope item above has a home in this structure.

## Conflicts surfaced

None. No existing policy, principle, or spec is violated by this structure; policy 002 explicitly governs ordered documents and this ADR clarifies that packages are not ordered documents.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — locks Monorepo Architect folder recommendation | Jeff Haskin |
