# 001 — ADRs Lock Policies, Not Configurable Values

## Rules

1. An Architecture Decision Record (ADR) in `docs/specs/adrs/` **must not** stipulate the numeric value of any parameter that ought to be a runtime-configurable setting.
2. The same rule applies to Change Requests (CRs) in `docs/specs/change_requests/`: a CR's proposed-change text must not fix a tunable parameter's value.
3. ADRs and CRs lock **policies** and **structural decisions** — categorical choices that shape what a system *does* or *is* — not parameter values that describe what a system's settings *happen to be at a given moment*.
4. Values for tunable parameters live in the project-root configuration file. The initial seed is committed into that file; subsequent tuning is a config-file edit, not an ADR amendment or a CR revision.

## What counts as a "policy" vs a "value"

**Policy (ADR-worthy):**

- "Aggregation over chunk scores is `max`." — a categorical choice between max, mean, sum, top-k mean, etc.
- "Score fusion is full replacement, not weighted blending." — a structural choice of pipeline shape.
- "K is configurable in the project-root config file." — a structural choice about where the knob lives.
- "The reranker always returns the requested top-k, without a score floor." — a behavioral policy.

**Value (config-file concern, NOT ADR-worthy):**

- "K = 30."
- "RRF top-N = 50."
- "Chunk window = 450 tokens, overlap = 50 tokens."
- "Batch size = 32."
- "Timeout = 5 seconds."
- "Cache TTL = 24 hours."

The test is: *"If a future maintainer wanted to change this, would the right response be 'edit the ADR' or 'edit a config file'?"* If the answer is config file, the number does not belong in the ADR.

## Why

- **Stipulated values appear to carry architectural weight they do not possess.** A value embedded in an ADR or a CR acquires the gravity of a decision that should require amendment to change — when in reality it should be a one-line config tweak. Future maintainers fight the document instead of retuning the knob.
- **Values drift; policies don't.** Re-tuning K from 30 to 50 is a Tuesday-morning decision that should have no trace in the architecture record. A pipeline-shape change (e.g., introducing weighted fusion) *should* leave a trace; that is what ADRs are for.
- **Configurability is itself the decision.** The ADR decision is "this knob exists and lives at this config location." The value the knob currently holds is not the decision.
- **Audit clarity.** An ADR free of values ages well: it still describes the system's shape years later. An ADR stitched full of values is half-stale the first time anyone tunes.

## Scope

This policy applies to every document under:

- `docs/specs/adrs/`
- `docs/specs/change_requests/` — every status subfolder (`drafting/`, `pending/`, `accepted/`, `staged/`, `in_progress/`, `completed/`, `locked/`, `archived/`).

It does **not** apply to:

- Principles (`docs/principles/`), which describe dispositions rather than architectural decisions; principles may still invoke qualitative framings that happen to use numeric thresholds as illustrations.
- Roadmap entries (`docs/roadmap/`), which may reference target numbers and ranges as working assumptions or ship criteria.
- The project-root configuration file itself, which is the correct home for values.
- `config.json` manifest files inside built indexes — those are artifact snapshots that record the values that were in effect at build time, by design.
- Ship-criteria tables (e.g., recall-uplift thresholds, latency budgets, disk-size caps) in CRs — these are measurement gates, not tunable parameters. A CR may legitimately say "hybrid must beat BM25 by ≥ 5 pts recall@10" because that is the *decision bar*, not a runtime knob.

## Examples

**Correct (policy framing):**

> "Candidate count K is configurable in the project-root config file under `[reranker]` → `top_k`. Hard-coding K in module code is a code-review-grade rejection."

**Incorrect (value stipulation):**

> "Default K = 30."

**Correct reframing of a pending CR:**

> "The reranker re-scores the fused top-N hybrid results, where N is configurable in the project-root config file."

**Incorrect (original CR-003 draft):**

> "`--mode hybrid` continues to produce an RRF-fused top-N (configurable; default N = 50)."

The latter stipulates 50 in the CR text. Under this policy, the value moves to the config file and the CR text mentions only configurability.

## Validation

- At PR review, any numeric stipulation of a tunable parameter in an ADR or a CR is a review-grade rejection. The author is asked to reframe in terms of configurability and move the value to the config file.
- When an existing ADR or CR is edited, any pre-existing value stipulation should be flagged and removed as a drive-by cleanup, with the removal noted in the ADR's Amendment Log or the CR's Audit Log.
- A grep across `docs/specs/adrs/` and `docs/specs/change_requests/` for lines matching `default[ \t]*[A-Za-z_]+[ \t]*=[ \t]*[0-9]` is a coarse but useful lint for this policy.

## Reference

- `../../../specs/adrs/008_accepted_cross_encoder_reranker_defaults.md` — the ADR that motivated this policy. Its amendment log records the removal of an initial `K = 30` stipulation in accordance with this rule.
