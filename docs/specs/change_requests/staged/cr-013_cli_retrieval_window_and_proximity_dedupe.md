---
id: 013
title: CLI retrieval window around hits and proximity-based dedupe
status: staged
created: 2026-04-20
updated: 2026-04-20
references:
  - docs/specs/adrs/001_accepted_no_silent_failures.md
  - docs/specs/adrs/007_accepted_cli_optimized_for_ai_agents.md
  - docs/principles/001_vector_retrieval.md
  - cr-007_multiverse_window_retrieval.md
  - cr-010_scripvec_web_front_end.md
---

# CR-013: CLI retrieval window around hits and proximity-based dedupe

## Summary

Two tightly interacting features on `scripvec query`:

1. `--window N` — *retrieval window*. For each hit, include up to N adjacent verses before and after (bounded by chapter / section boundaries) as a `window` payload alongside the hit.
2. `--dedupe` / `--no-dedupe` — *proximity dedupe*. When two hits are within a configurable distance of each other, collapse them to the higher-scored one before top-K is taken. Default on.

Bundled in one CR because the two features interact: dedupe runs first, then the window is drawn around each surviving hit. Specifying them together keeps the interaction explicit rather than implicit across two CRs.

## Motivation

Verses are short and often open with pronouns or mid-thought continuations; a verse read without its neighbors can mislead. A retrieval window gives the caller enough surrounding text to judge a hit without a second query.

Separately, scripture-search results are routinely dominated by a single pericope: five of the top ten hits are contiguous verses in Alma 32, and the other five are scattered. A proximity-dedupe collapses the cluster to its single best representative, making room in top-K for genuinely different passages. The diversity gain is especially valuable for wide-net study queries.

The two features are most useful in combination (one strong hit + wide window + dedupe yields a study-grade top-3), but each is independently useful and independently togglable.

## Distinction from CR-007

CR-007 proposes *embedding* multi-verse windows on the index (document) side — a storage and retrieval-unit change. This CR is *display-side only*: the index is unchanged, retrieval is unchanged, and the window is drawn from the same verse table at query response time. The two can coexist; they address different problems:

- CR-007 asks "what unit do we match against?" — a retrieval-unit question.
- CR-013 asks "what do we return alongside each match?" — a response-shape question.

Both CRs use the word "window" for their own concept. This CR uses *retrieval window* when it needs to disambiguate; CR-007 uses *embedding window*.

## Proposed change

### Retrieval window

- `--window N` — include N verses before and N verses after each hit in the response.
- `N=0` (or absence of flag) → no window. The response is unchanged.
- Windows do not cross chapter / section boundaries. If a hit is at verse 1 of a chapter, the pre-window is clipped at 0; same for end-of-chapter on the post-window.
- The default value of `N` is in the project-root config file — no number is stipulated in this CR.

### Response shape

Each hit gains a `window` field when `--window > 0`:

```json
{
  "rank": 1,
  "verse_id": "...",
  "ref": "Alma 32:21",
  "text": "And now as I said concerning faith...",
  "window": {
    "before": [
      {"ref": "Alma 32:19", "text": "..."},
      {"ref": "Alma 32:20", "text": "..."}
    ],
    "after": [
      {"ref": "Alma 32:22", "text": "..."},
      {"ref": "Alma 32:23", "text": "..."}
    ]
  }
}
```

- `before` / `after` are lists in scripture order. They may be shorter than `N` when the hit is near a boundary.
- `window` is absent when `--window 0` or the flag is not supplied.

### Proximity dedupe

- `--dedupe` — collapse hits within `M` verses of each other to the higher-scored one. `M` is configurable in the project-root config file.
- `--no-dedupe` — skip dedupe. Every retrieved hit is eligible for top-K regardless of proximity to other hits.
- Default: dedupe **on**.

Mechanism:

1. Retrieve `k_buffer` hits (more than `k`) from the underlying retrieval path.
2. Sort by score. Walk in descending order; for each hit, if no already-kept hit is within `M` verses, keep it; otherwise drop it.
3. Cut the kept list at `k`.
4. Apply the retrieval window (if any) to the kept hits.

Dedupe runs **before** windows are drawn. That ordering matters — see next section.

### Interaction

- **Dedupe before window.** Dedupe collapses near-duplicates in the result set. Windows are then drawn around the survivors. If dedupe ran after windows, overlapping windows would each be built and then one of them thrown away — wasted work and a confusing payload mid-build.
- **Windows may still overlap.** Two surviving hits can be far enough apart to survive dedupe but close enough that their windows overlap. That is allowed — each hit's window is rendered independently. The response does not stitch windows together.
- **Proximity cutoff `M` and window size `N` are independent.** `M` is a dedupe decision (how different do two hits have to be to count as different?); `N` is a presentation decision (how much context do we show?). They are tuned separately.

### README guidance (documentation, not code)

The README for `scripvec query` must spell out:

1. The dedupe-before-window ordering, and why.
2. The recommendation that `--k` be reduced to `1`–`3` when both features are on. A single strong hit with a wide window and dedupe active gives richer study context than ten scattered narrow-window hits. This is a study-flow recommendation, not an enforced rule.
3. That `--dedupe` is on by default, and `--no-dedupe` is the escape hatch for callers who want raw retrieval ordering.

### Response fields

- Top level of the `query` response gains:

```json
{
  "dedupe": {"enabled": true, "proximity_verses": 3, "dropped": 7},
  ...
}
```

- `dropped` is the number of hits dedupe collapsed (useful for tuning).
- `proximity_verses` echoes the effective `M` used.

### Failure modes (ADR-001)

- `--window N` with negative `N` → raise.
- `--window N` with `N` larger than the longest chapter / section in the corpus → accept; each hit just clips at its boundaries.
- `--no-dedupe` on a query where the top-K is already all from one pericope → accept; the user explicitly asked for raw order.

## Impact on referenced docs

- **CR-007:** distinct concept (document-side embedding window vs. display-side retrieval window). Both can ship; neither supersedes the other. This CR's *Distinction from CR-007* section is the canonical disambiguation.
- **ADR-007:** two additive flags; additive `window` and `dedupe` response fields. No breaking change.
- **ADR-001:** explicit failure modes above.
- **CR-010 (front-end):** the front-end consumes the `window` field when the user has `--window > 0`, and independently fetches chapter/verse context for on-demand "show more" UI. The two context mechanisms are deliberately decoupled (see CR-010).
- **Principle 001:** the eval harness should be orthogonal to `--window` (window is presentation, not retrieval); and should report recall with and without `--dedupe` so dedupe's effect on ranked metrics is visible.

## Open questions

- Should dedupe and force-inclusion (ADR-014) interact? An extracted reference is force-included; does dedupe potentially drop an otherwise-retrieved neighbor of it? Proposal: force-included hits are never dedupe-dropped; neighbors of force-included hits can still be dedupe-dropped if close enough. Confirm during implementation.
- Should the window include only text, or also per-verse score for verses adjacent to the hit that *also* scored highly? Probably text-only — score-inside-window muddies the "this is context, not another hit" distinction.

## Decision

Staged.

## User stories (scrum)

*Channeled from the Scrum Lead persona. Each story is a vertical slice that delivers observable value on its own, with acceptance criteria in "when X, then Y" form. Sequencing is for dependency-clarity, not priority — the stakeholder decides what ships first. Numeric defaults for `N` (window) and `M` (proximity) are not stipulated here; they live in the project-root config file per ADR policy.*

### Intake reframe

The original ask bundles two features. Read literally it is "add two flags." Reframed to outcomes:

- **Outcome A (window):** an AI-agent caller running `scripvec query` can judge whether a hit is actually relevant without issuing a second lookup for surrounding verses.
- **Outcome B (dedupe):** an AI-agent caller running a wide-net study query gets a top-K that represents distinct passages, not a cluster of neighbors from a single pericope.
- **Outcome C (interaction & guidance):** callers who enable both features get a documented, predictable ordering (dedupe first, window second) and a README that explains the study-flow recommendation.

These are three distinct observable outcomes. They decompose into seven thin stories below.

---

### Story 1 — Retrieval window flag returns adjacent verses per hit

**User & trigger:** When an AI-agent caller runs `scripvec query "<q>" --window N` with `N > 0`, they receive, alongside each hit, up to N verses before and N verses after the hit verse, so they can judge relevance without a second query.

**Acceptance criteria:**
- When `--window N` is passed with `N > 0`, each hit in the response has a `window` field with `before` and `after` lists of `{ref, text}` objects in scripture order.
- When `--window 0` is passed, or `--window` is omitted, the response contains no `window` field on any hit (the response shape is unchanged from pre-CR baseline).
- When a hit sits at the first verse of a chapter/section, `before` is an empty list — it does not spill into the previous chapter.
- When a hit sits at the last verse of a chapter/section, `after` is an empty list — it does not spill into the next chapter.
- When `N` is larger than the longest chapter/section in the corpus, the command does not fail; each hit simply clips at its own boundaries.
- When `--window` is passed a negative integer, the CLI raises a clear error and exits non-zero (ADR-001, no silent failure).
- The default value of `N` is read from the project-root config file; no hardcoded default in code.

**Notes for engineer:** this is display-side only. The index is unchanged. The window is drawn from the verse table at response time.

---

### Story 2 — Proximity dedupe collapses near-neighbor hits by default

**User & trigger:** When an AI-agent caller runs `scripvec query "<q>"` with no dedupe flag, hits that fall within `M` verses of an already-kept higher-scored hit are dropped before top-K is taken, so the returned top-K represents distinct passages rather than a cluster.

**Acceptance criteria:**
- Dedupe is **on** by default — the user does not need to pass `--dedupe` to get it.
- When dedupe is active, the retrieval path pulls `k_buffer` candidates (more than `k`), sorts by score descending, and walks the sorted list: a hit is kept only if no already-kept hit is within `M` verses of it; otherwise it is dropped.
- After the walk, the kept list is truncated to `k`.
- `M` is read from the project-root config file; no hardcoded default in code.
- Two hits in *different chapters or different books* are never considered within `M` of each other, regardless of verse-number arithmetic.

**Notes for engineer:** `k_buffer`, the default proximity `M`, and the default `k` all live in the root config. This story does not stipulate values.

---

### Story 3 — `--no-dedupe` escape hatch returns raw retrieval order

**User & trigger:** When an AI-agent caller runs `scripvec query "<q>" --no-dedupe`, every retrieved hit is eligible for top-K regardless of its proximity to other hits, so the caller can inspect raw retrieval ordering (e.g. for eval, debugging, or deliberate pericope-study queries).

**Acceptance criteria:**
- When `--no-dedupe` is passed, no hit is dropped for proximity; top-K is taken from score-sorted raw retrieval directly.
- `--dedupe` and `--no-dedupe` are mutually exclusive flags; passing both is a CLI error.
- The top-level response's `dedupe` field (see Story 5) shows `enabled: false` in this case.
- When the top-K is already all from one pericope and the caller passed `--no-dedupe`, the command succeeds — that is what the caller asked for (ADR-001).

---

### Story 4 — Dedupe runs before window is drawn

**User & trigger:** When an AI-agent caller runs `scripvec query "<q>" --window N --dedupe` (or the default-on equivalent), dedupe is applied to the candidate hits first and the window is drawn only around the surviving kept hits, so no work is wasted on windows for hits that are about to be dropped, and the payload shape is predictable.

**Acceptance criteria:**
- In the implementation, window construction is invoked only for hits that have survived dedupe. A dropped hit never has a window built for it.
- When two surviving hits are far enough apart to survive dedupe (`> M` apart) but close enough that their windows overlap, both windows are rendered independently; the response does not stitch or de-overlap them.
- The README documents this ordering and why (see Story 7).

---

### Story 5 — Top-level `dedupe` response field reports what happened

**User & trigger:** When an AI-agent caller runs any `scripvec query`, the response carries a top-level `dedupe` object so the caller (or a downstream eval harness) can see whether dedupe ran, what proximity was used, and how many hits it collapsed — without having to infer it from payload shape.

**Acceptance criteria:**
- The `query` response has a top-level `dedupe` object with fields: `enabled` (bool), `proximity_verses` (int — the effective `M`), `dropped` (int — count of candidates dedupe collapsed).
- When `--no-dedupe` is passed, `enabled: false`, `dropped: 0`, and `proximity_verses` echoes the configured `M` (so the caller can still read the config value; nothing was applied).
- The `dedupe` field is present on every `query` response, including when `--window` is off — it is part of the envelope, not the window feature.
- ADR-007: this is an additive field; existing consumers parsing other fields are unaffected.

---

### Story 6 — Window response-shape contract on each hit

**User & trigger:** When an AI-agent caller consumes the response from `scripvec query --window N`, each hit's `window` payload has a stable, documented shape (`before`, `after`, each a list of `{ref, text}`), so downstream agents can parse without branching on edge cases.

**Acceptance criteria:**
- Each `window` has exactly two keys: `before` and `after`, both lists.
- Each list element is an object with exactly two keys: `ref` (human-readable scripture reference) and `text` (verse text).
- No per-verse score is included inside the window — `window` is context, not hits (per the CR's open-question resolution toward text-only).
- `before` and `after` are in scripture order (ascending verse numbers), not hit-centric order.
- When the window is shorter than `N` on one side due to a chapter boundary, the list is simply shorter; no padding, no null entries, no error.

---

### Story 7 — README documents ordering, study-flow recommendation, and default

**User & trigger:** When a new caller (human or agent) reads the `scripvec query` README, they learn (a) that dedupe runs before window, and why, (b) that `--k 1..3` is the recommended setting when both features are on for study-grade context, and (c) that dedupe is on by default with `--no-dedupe` as the escape hatch.

**Acceptance criteria:**
- The `scripvec query` README section contains all three points above in prose the caller can skim.
- The dedupe-before-window ordering is stated with the rationale (no wasted work, predictable payload).
- The `--k 1..3` suggestion is framed as a study-flow recommendation, not an enforced rule — the CLI does not cap or warn on `--k` above this range.
- The default-on nature of `--dedupe` and the role of `--no-dedupe` are explicitly called out.

**Notes:** documentation-only story. No code changes. Independently deliverable; can ship in parallel with or after the code stories.

---

### Deferred / open questions (not yet stories)

These items from the CR's *Open questions* section are explicitly **not** in this decomposition; they are flagged for the stakeholder to resolve before they become stories:

- **Dedupe vs. force-inclusion (ADR-014) interaction.** Proposal in CR: force-included hits are never dedupe-dropped; neighbors may be. Awaiting confirmation — will become a story once confirmed.
- **Per-verse score inside window.** CR's lean is text-only (reflected in Story 6). If stakeholder overrides, Story 6's acceptance criteria change.

### Sequencing (dependency graph, not priority)

- Story 1 is independent.
- Story 2 is independent.
- Story 3 depends on Story 2 (the dedupe machinery must exist before the opt-out flag is meaningful).
- Story 4 depends on Story 1 and Story 2 (needs both features present to define their interaction).
- Story 5 depends on Story 2 (the `dedupe` envelope field reports on the dedupe pass).
- Story 6 depends on Story 1 (contract on a payload that Story 1 introduces).
- Story 7 depends on Stories 1–5 being chosen as scope; documentation follows code shape.

The stakeholder picks the order; the graph above just guarantees no story gets picked up before its predecessors exist.

## Beads plan (bead-planning persona)

*Note on persona: the personas DB was searched for a distinct "bead planning" persona per instructions. No such entry exists in the DB as of this writing — closest retrieval results are `Scrum Lead` (≈0.96 distance), `Discipline Scout`, and `Ousterhout`. Rather than freestyle a persona from memory, the Scrum Lead — already used in step 2 for user-story decomposition — is re-channeled here with a narrower framing (story → bead, with repo-aware mechanical detail) that approximates the bead-planning role's remit. Flagged for the user in the final report.*

### How the Scrum Lead approaches bead-planning

Beads are the unit a swarm of agents picks up. A good bead is **smaller than a story** (one story may split into several beads), **mechanically unambiguous** (an agent must be able to start without a clarifying round-trip), **single-file-ish when possible** (merges cleanly with sibling beads), and **dependency-linked** so `bv`'s critical-path analysis is meaningful.

The Scrum Lead's story list from step 2 is the starting point. Each story is examined for whether it is already one-bead-sized or needs to split. Beads that touch the same file(s) are sequenced to reduce merge conflict. Documentation and test-only beads are split out into their own beads so they can be picked up independently.

### Bead list

IDs in this plan are **planning IDs** (`B1`…`Bn`); beads-DB IDs will be assigned by `br create` in step 4.

---

**B1 — CLI: add `--window N` flag + config default, validation only**
- Adds `--window` to `scripvec query` (Typer). Reads default `N` from project-root config. Validates negative N → raises via `cli/errors.py`.
- Does not yet fetch adjacent verses; just threads the validated integer through to the query pipeline.
- File(s): `cli/query_cmd.py`, config loader.
- Acceptance: CLI tests confirm flag parses; invalid input raises; default falls back to config.
- Maps to Story 1 (flag surface).

**B2 — retrieval: verse-neighbor lookup helper**
- Adds a helper that, given a `verse_id` and `N`, returns up to `N` verses before and after bounded by chapter/section — reading from the `verses` table in `corpus.sqlite`.
- Pure function, fully unit-testable against a fixture corpus including boundary cases (verse 1, last verse, N > chapter length).
- File(s): `packages/retrieval/src/scripvec_retrieval/window.py` (new).
- Acceptance: unit tests cover all Story 1 edge cases.
- Maps to Story 1 (data access).

**B3 — response: attach `window` payload to each hit when `N > 0`**
- Wires B2 into the query response builder: for each hit, when effective `N > 0`, attach `{before: [...], after: [...]}` in the shape documented by Story 6.
- When `N == 0` or flag absent, `window` field is omitted (not `null`, not `{}`).
- File(s): query response assembler.
- Acceptance: contract test asserts presence/absence and structure; text-only (no score inside window).
- Depends on: B1, B2.
- Maps to Story 1 + Story 6.

**B4 — retrieval: proximity-dedupe walk, behind a boolean + config `M`**
- Adds the dedupe machinery: pull `k_buffer`, sort desc by score, walk and keep-if-no-kept-hit-within-M-verses, truncate to `k`. Same-chapter check: two hits in different chapters/books are never within `M` of each other.
- Parameters (`M`, `k_buffer`) come from config. Function returns both the kept list and the count of dropped hits.
- File(s): `packages/retrieval/src/scripvec_retrieval/dedupe.py` (new).
- Acceptance: unit tests for (a) same-chapter collapse, (b) cross-chapter non-collapse, (c) score ordering respected, (d) `dropped` count correct.
- Maps to Story 2.

**B5 — CLI: `--dedupe` / `--no-dedupe` mutually-exclusive flags, default on**
- Adds the two flags to `scripvec query` with mutually exclusive validation (passing both → CLI error). Default: dedupe on.
- Does not yet call B4; only surfaces the boolean decision to the query pipeline.
- File(s): `cli/query_cmd.py`.
- Acceptance: CLI contract test confirms default-on, that `--no-dedupe` disables, and that passing both raises.
- Depends on: (none — flag only).
- Maps to Story 3 (flag surface).

**B6 — response: wire dedupe + emit top-level `dedupe` envelope**
- Wires B4 into the query pipeline behind the B5 flag. Adds top-level `dedupe: {enabled, proximity_verses, dropped}` object per Story 5 on every `query` response, including when `--no-dedupe` (then `enabled: false`, `dropped: 0`, `proximity_verses` still echoed).
- File(s): query orchestrator, response assembler.
- Acceptance: integration test confirms envelope shape in both on/off modes.
- Depends on: B4, B5.
- Maps to Story 2 + Story 3 + Story 5.

**B7 — interaction: enforce dedupe-before-window in the pipeline**
- Reorders the query pipeline so dedupe runs *before* window construction (B3). Window work is invoked only on survivors. Adds a pipeline-order test that fails if the order is reversed.
- File(s): query orchestrator.
- Acceptance: test confirms no `window` is constructed for a hit that dedupe drops; two surviving hits with overlapping windows both render independently.
- Depends on: B3, B6.
- Maps to Story 4.

**B8 — docs: README guidance for `scripvec query`**
- Adds (or updates) the `scripvec query` README section to cover: (1) dedupe runs before window and why; (2) `--k 1..3` study-flow recommendation when both features are on (recommendation, not enforced); (3) dedupe on by default, `--no-dedupe` as escape hatch.
- File(s): `README.md` (or the query-specific readme section; engineer picks).
- Acceptance: prose present and accurate; no code changes.
- Depends on: B1, B5 exist (so the README describes real flags), but not on B7 (docs can be written in parallel with late implementation).
- Maps to Story 7.

**B9 — eval hook: report recall with/without `--dedupe`**
- Updates the eval harness (`scripvec eval run`) to record recall@k under both dedupe-on and dedupe-off conditions, so Principle 001's expectation is met.
- Does not touch `--window` (window is presentation, orthogonal to retrieval recall).
- File(s): `packages/eval/src/scripvec_eval/run.py` (and/or metrics wiring).
- Acceptance: eval output now carries both numbers; existing eval tests still pass.
- Depends on: B4, B6.
- Maps to CR "Impact on referenced docs → Principle 001."

### Dependency graph (planning IDs)

```
B1 ──┐
     ├──> B3 ──┐
B2 ──┘         │
               ├──> B7 ──> (pipeline ordering)
B4 ──┐         │
     ├──> B6 ──┘
B5 ──┘

B8 (docs)  depends loosely on B1 + B5 (flags must exist in code first)
B9 (eval)  depends on B4 + B6
```

### Sprint / label guidance

- Suggested labels: `app-cli` (B1, B5, B8), `pkg-retrieval` (B2, B3, B4, B6, B7), `pkg-eval` (B9), `test` (on beads that add tests, i.e. B2, B3, B4, B6, B7), `authoring` (B8).
- Sprint assignment is a stakeholder decision; the planning role does not set priorities. All beads default to P1 to match the existing CR-001 precedent for in-CR work, and the stakeholder can re-priority on the board.

### Deferred from the bead plan

- The "dedupe × force-inclusion (ADR-014)" interaction is an open question in the CR — not turned into a bead here. A bead for that will be authored once the stakeholder resolves the interaction policy.

## Audit log

- 2026-04-20 — created as `staged`.
