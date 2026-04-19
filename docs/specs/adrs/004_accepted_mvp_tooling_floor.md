# ADR-004: MVP tooling floor — conditional on language stack

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

The Monorepo Architect persona, channeled on 2026-04-19, recommended a tooling floor appropriate for a solo-dev monorepo, deliberately *conditional* on the language stack. The engineer approved both conditional recipes. This ADR locks them so that when the stack is picked, the tooling follows without further debate.

**Decision drivers:**

- The tooling floor is the set of primitives that future packages assume. Locking it removes a class of bikeshed from every future CR.
- Two stacks are plausible for scripvec's retrieval MVP — Python (the honest default for sqlite-vec / FAISS / sentence-transformers / BM25 libraries) or TypeScript. Either could ship. Mixing is worse than either.
- Overinvested tooling (Nx, Poetry plugins, custom generators) costs legibility and slows iteration. At solo-dev scale, the floor should be *enough to enforce boundaries and cache builds*, and no more.
- The stack choice itself is deferred to a separate decision; this ADR commits only to *what follows* that choice.

## Decision

### Stack choice is deferred

The language stack for scripvec MVP is **not** locked by this ADR. A separate ADR or change request must select the stack before implementation begins. Mixing stacks within a package is prohibited by this ADR; mixing across packages (e.g., a Python retrieval package and a TypeScript CLI) is permitted only if a future ADR explicitly authorizes it with a demonstrated reason.

### If the MVP is implemented in Python

- **Workspace manager:** `uv` workspaces. No Poetry, no Hatch at the workspace level, no pip-tools pinning on top.
- **One `pyproject.toml` per package.** Each package in `packages/` and each app in `apps/` declares its own `pyproject.toml` with its dependencies and Python-version constraint. A root `pyproject.toml` declares the workspace and any tool-level config that is truly shared.
- **Linting and typing at the root:**
  - `ruff` configured once at the repo root, applied to every package.
  - `mypy` configured once at the repo root, applied to every package.
  - Per-package overrides only when a demonstrably good reason exists, recorded in that package's README.
- **No build tool beyond `uv`.** No Make, no Nx, no Bazel. If caching becomes the bottleneck, the next step is revisiting this ADR — not adding a layer.
- **Import boundaries:** enforced via package dependency declarations (a package can only import from packages it lists as dependencies in its `pyproject.toml`). A lint rule or a custom check may be added later if drift is observed.

### If the MVP is implemented in TypeScript

- **Workspace manager:** `pnpm workspaces`.
- **Build orchestrator:** `Turborepo`. Not Nx.
- **One `package.json` per package.** Root `package.json` declares the workspace.
- **Shared `tsconfig.base.json` at the root** with path aliases mapping each in-repo package to its source (e.g., `@scripvec/retrieval` → `packages/retrieval/src`). Every package extends it.
- **Import boundaries via ESLint `no-restricted-imports`** (or the Turborepo-native equivalent if simpler). Cross-boundary imports that violate the dependency graph in ADR-003 are rejected at lint time.

### Refusals — tooling that will not be adopted

- **Nx.** Appropriate for graph-scale problems; scripvec does not have a graph-scale problem. If the graph ever hurts, revisit this ADR rather than adopting Nx by default.
- **Poetry.** `uv` is the chosen Python workspace tool. Poetry is not adopted as an alternative, even in a single package.
- **Root-level `src/`.** Enforced by ADR-003.
- **Catch-all shared packages (`common`, `utils`, `core`, `lib`, `helpers`).** Enforced by ADR-003. Tooling does not create them either.
- **Deep relative imports (`../../../`).** Path aliases (TS) or intra-package absolute imports (Python) only. A relative import that leaves a package is a bug.

## Consequences

**Positive:**

- Future CRs spend zero words on "what tool should we use" at the workspace level.
- The tooling floor matches the persona's guidance: enough to enforce boundaries and cache builds, not so much that the tooling becomes its own project.
- Stack switching (should Python prove wrong or TypeScript prove wrong) has a clean migration target — the alternative recipe is pre-approved.

**Negative:**

- Two recipes mean two maintenance surfaces in this ADR. If either toolchain changes materially, the recipe must be amended.
- The refusal of Nx / Poetry is a hard constraint; a future need that they would naturally fit must first justify amending this ADR.
- Root-level `ruff` / `mypy` configs can occasionally conflict with a package's local needs. The resolution is to document the tension in the package's README and, if it recurs, revisit this ADR — not to silently break the root config.

## Validation

- **A CR that introduces code must pick the stack first.** The stack choice is pre-validated against this ADR — the chosen recipe applies verbatim.
- **Every `pyproject.toml` (Python path) or `package.json` (TS path) is reviewed at creation time** to confirm it extends the root config and does not introduce alternative tooling.
- **`ruff` / `mypy` / `eslint` errors fail CI** (once CI exists). No packages are exempt without a README-documented and ADR-amended justification.

## Links

- `/data/projects/flywheel/personas/monorepo_architect.md` — source of the recommendation; see "Tooling floor — conditional, because stack is undecided."
- `docs/specs/adrs/003_accepted_mvp_folder_structure.md` — the structure this tooling operates on.
- `docs/specs/adrs/002_accepted_no_role_splitting_in_packages.md` — tooling enforces inter-package boundaries; intra-package structure stays flat.
- `cr-001_vector_search_mvp.md` — MVP scope whose implementation will invoke the chosen recipe.

## Conflicts surfaced

None. No existing policy or ADR selects a conflicting tooling path. ADR-003's *no numeric prefixes on packages* clause is consistent with both recipes — package folder names are language-agnostic.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — locks conditional tooling recipes per Monorepo Architect guidance | Jeff Haskin |
