# ADR-002: No role-splitting inside packages at MVP scale

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

The Monorepo Architect persona (`/data/projects/flywheel/personas/monorepo_architect.md`), channeled against the scripvec MVP on 2026-04-19, endorses the Nx-style lib-type subdivision in principle: within a domain, split by role — `feature/`, `ui/`, `data-access/`, `utils/`. That subdivision is *correct at scale.* scripvec is not at that scale.

At MVP, scripvec has one developer and four small packages (`corpus_ingest`, `reference`, `retrieval`, `eval`), each with one consumer. Introducing four role-folders inside each package immediately — before any package has even one module — is ceremony without signal. It tells the next contributor (or future-self) that these subfolders are load-bearing, when in fact they would be empty or near-empty for the foreseeable future.

**Decision drivers:**

- Solo developer, greenfield. Every package starts single-consumer. Over-partitioning costs legibility now and doesn't pay off until the graph widens.
- The Nx subdivision exists to enforce import boundaries between *roles* that a team of multiple contributors might accidentally cross. With one developer, the enforcement mechanism is self-review — the subdivision is not yet load-bearing.
- Flat is better than deep at this scale; the persona is explicit about this.
- The structural debt of collapsing a prematurely-deep folder is lower than the legibility cost of navigating one while it's effectively empty.
- Deferring the split gives us a signal to listen for (size and consumer count) rather than a guess to commit to.

## Decision

Inside each MVP package (`corpus_ingest`, `reference`, `retrieval`, `eval`), do **not** sub-divide by role. Keep a flat module layout with tests co-located adjacent to the modules they cover. A package's top level contains the modules that constitute its domain; there is no `feature/`, `ui/`, `data-access/`, or `utils/` inside.

**Revisit triggers** — revisit this ADR and consider role-splitting the affected package when *any* of the following is true for that package:

- The package crosses approximately **1,000 lines of code** (exclusive of tests).
- The package gains a **second consumer** — i.e., a second app or package imports from it.
- A clear bounded-context split emerges inside the package (e.g., `retrieval` grows a UI surface that is meaningfully distinct from its query-execution core).

Until a trigger fires, resist the temptation to add role-folders speculatively. If a new module's role is genuinely ambiguous, that ambiguity is a signal that the package's domain may be miscut — address it by reshaping the package set, not by adding an internal folder.

**Exception — none currently.** The solo-dev MVP scale does not admit exceptions. If an exception becomes necessary, amend this ADR rather than quietly splitting one package.

## Consequences

**Positive:**

- Every MVP package is legible in a single `ls`; one can find any module without navigating role-folders.
- No cargo-culted empty folders teaching new contributors that ceremony is the convention.
- Package reshaping is cheaper — the more shape a package has internally, the more disruptive a split or merge becomes.
- Reviews focus on the modules, not on where in the taxonomy they belong.

**Negative:**

- When a package grows past the trigger, the split is a deliberate refactor rather than a gradual drift. That refactor has to happen — it cannot be deferred past the trigger without this ADR being amended.
- Someone scanning for a specific "role" (e.g., "where's the data-access layer?") will not find a folder with that name. The answer is "the package *is* the role boundary at this scale" — that needs to be communicated in each package's README.

## Validation

- **Per-package README states the rule.** Each package's `README.md` contains a line to the effect of *"flat layout per ADR-002; no internal role-folders until the trigger fires."* This keeps the intent visible where decisions happen.
- **Size audit at each CR boundary.** Before closing a change request that adds code, confirm no package has crossed a revisit trigger. If one has, open an ADR amendment or a sub-CR for the role split before closing.
- **Reconsider if:** the monorepo gains a second developer. A second contributor changes the calculus — role-splitting enforces boundaries that self-review no longer catches reliably.

## Links

- `/data/projects/flywheel/personas/monorepo_architect.md` — source of the recommendation; see the "Core principles" section, specifically the *"Inside a domain, then split by role"* principle and its scale caveat.
- `docs/specs/adrs/003_accepted_mvp_folder_structure.md` — defines the packages this ADR governs.
- `docs/specs/change_requests/drafting/cr_001_vector_search_mvp.md` — MVP scope.

## Conflicts surfaced

None. ADR-003 (folder structure) does not sub-divide packages internally; this ADR confirms and codifies that choice. No policy or principle requires a role-split layout.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — codifies Monorepo Architect guidance for MVP scale | Jeff Haskin |
