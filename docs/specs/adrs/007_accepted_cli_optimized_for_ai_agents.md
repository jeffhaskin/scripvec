# ADR-007: CLI optimized for AI agents as the primary user

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

scripvec will expose a command-line interface. CR-001's "minimal interface to issue queries and read results" will, at MVP, be a CLI living in `apps/scripvec_cli/` (per ADR-003).

The primary consumer of that CLI is **not a human sitting at a terminal.** It is an AI agent — a higher-level program (LLM-driven or otherwise) that constructs commands, parses output, decides what to do next, and composes scripvec's retrieval primitives into larger workflows. Humans will use the CLI for debugging, ad-hoc queries, and building the eval harness, but they are the **secondary** user class. The design must optimize for the primary class.

AI-agent consumption and human consumption pull the CLI in opposite directions on nearly every design axis:

| Axis                       | Human-first                     | Agent-first                                  |
|----------------------------|---------------------------------|----------------------------------------------|
| Default output format      | Pretty text, columns, colors    | Structured (JSON), stable schema             |
| Error surface              | Friendly messages on stderr     | Structured error object, parseable           |
| Interactivity              | Prompts, confirmations          | None                                         |
| Progress indication        | TTY spinners, overwriting       | Newline-delimited events or silent           |
| Pagination                 | Paged output in a terminal      | Full output in one read                      |
| Color / ANSI               | Colored by default on a TTY     | Off by default, honors `NO_COLOR`            |
| Help text                  | Brief and encouraging           | Thorough, covers edge cases                  |
| Command composition        | Idiomatic to the shell          | Predictable, no hidden stateful side effects |
| Output ordering            | Whatever reads well             | Deterministic                                |
| Exit codes                 | Often 0/1                       | Documented, granular, stable                 |

This ADR picks the agent-first column across the board.

**Decision drivers:**

- The AI-agent workflows scripvec is built to enable (query composition, retrieval-augmented generation, automated eval-set curation, pipeline automation) require a machine contract, not a human-nice rendering.
- ADR-001 (fail loud) is easier to uphold when errors are structured — an agent can read a structured error and decide, where a stderr string requires regex parsing that inevitably goes wrong.
- Stability matters more to agents than to humans. An agent's prompt or orchestration code encodes the CLI's contract; silent changes to flag names, output shape, or exit codes break agents in ways humans would have noticed immediately.
- Writing an agent-optimized CLI and then exposing a human layer on top is cheap. Writing a human-optimized CLI and retrofitting a machine interface later is expensive, because the human interface tends to leak undocumented behaviors that agents have already come to depend on.

## Decision

scripvec's CLI is optimized for AI agents as the primary user. Every design choice below is binding on the initial CLI and on every future command added to it.

### Output contract

- **Default output format is JSON.** Every command emits a well-formed JSON value on stdout by default. No leading/trailing prose, no banners, no cosmetic decoration.
- **A schema is documented per command.** Every command's help text names the fields and types of its output object. Schema changes are versioned (a new field is additive; a removed or renamed field is a breaking change requiring an ADR amendment and a major CLI version bump).
- **Output ordering is deterministic.** When a command returns a list (e.g., top-k search results), the order is specified (rank, then a stable tiebreaker) and preserved across invocations on the same inputs.
- **A `--format text` flag exists for human debugging.** It is never the default. Text format may be less stable; agents must not depend on it.
- **No colors, spinners, or TTY-dependent rendering by default.** Color is off unless explicitly requested with `--color always`. `NO_COLOR` is honored.
- **No pagination.** Every command prints its full output in one stream. If a caller wants to page, they pipe through `less`.

### Error contract

- **Errors are structured JSON on stderr**, with fields: `{"error": {"code": "<stable_code>", "message": "<human>", "details": {...}}}`. Stable error codes are part of the CLI's contract and documented per command.
- **Exit codes are documented and granular.** `0` = success, `1` = user error (bad input, unknown flag), `2` = not-found (e.g., no results), `3` = upstream error (e.g., embedding endpoint unreachable), and so on. Exit codes are stable across versions.
- **No partial-success exit codes.** Consistent with ADR-001: a command either succeeds fully or fails loudly. A command that returns an empty result set is a success (exit 0); a command that cannot complete its work is a failure (non-zero).

### Interaction contract

- **No interactive prompts. Ever.** No "are you sure?", no password reads from a TTY, no `input()` calls in any code path reachable from the CLI.
- **No reliance on environment ambient state.** Anything a command needs comes from explicit flags or explicit environment variables documented in the help text. No reading of the current working directory for implicit config, no `~/.scripvecrc`, no XDG-style probing at MVP.
- **No persistent background processes, no daemons, no file locks that an agent would have to know about.** Each command is a single short-lived invocation.

### Command-design contract

- **One command, one verb.** `scripvec query "..."` returns results. `scripvec ingest` builds an index. `scripvec eval` runs the harness. No compound commands where flags silently switch which verb is actually run.
- **Flags are orthogonal.** A flag does one thing; it does not change the meaning of another flag.
- **Help text is thorough.** `scripvec <cmd> --help` includes: purpose, full flag list with types and defaults, output schema, error codes, and at least one concrete example of input and JSON output. Verbosity is a feature here, not a flaw.
- **Version output is machine-readable.** `scripvec --version` prints a JSON object with the CLI version, the pinned embedding-model identifier (per ADR-005), and the index-config hash. An agent that depends on a specific index version can check without parsing prose.

### What this ADR does *not* require

- No requirement to support every possible structured format (YAML, TOML, etc.). JSON is the contract.
- No requirement for a streaming protocol. All CLI output is a single JSON value — commands that produce many results return an array, not newline-delimited objects. (A future ADR may introduce NDJSON if a use case demands it.)
- No requirement to be fast. Agent-first does not mean low-latency; ADR-006 forbids parallel embedding calls, which is a latency constraint this ADR accepts.

## Consequences

**Positive:**

- Agents get a stable, parseable contract. Writing an orchestration layer against scripvec is a matter of calling the CLI and reading JSON — no screen-scraping, no regex over stderr, no guessing at exit code meanings.
- ADR-001's fail-loud posture composes with this ADR: a loud failure from scripvec arrives at the agent as a structured error, not as a surprise exception the agent has to classify.
- Integration tests for scripvec can assert on JSON output, not on pretty-print strings. Tests stay useful as the CLI evolves.
- Humans who want a nicer view can pipe to `jq`, pass `--format text`, or write a thin wrapper. The primary contract stays clean.

**Negative:**

- The CLI will feel austere to a human using it directly. Colors, progress bars, and "helpful" error prose are deliberately absent by default. This is the correct trade-off for the primary user class, but it will surprise anyone who assumes human-first CLI conventions.
- Every new command carries more ceremony: output schema, stable error codes, machine-readable examples. This is a real cost on feature velocity. It is the cost of keeping the agent contract honest.
- `--format text` as a secondary format tempts scope creep. The text format must stay explicitly "for humans, unstable" so the primary contract does not get diluted.

## Validation

- **Every CLI command has a documented output schema and a documented error-code table in its `--help` output.** Checked at PR review time.
- **Every CLI command is tested against its JSON output contract.** Tests assert on parsed JSON, not on string output.
- **No `input()`, no `click.confirm`, no `inquirer`-style prompts, no `rich.Progress` in CLI-reachable code paths.** Checked by code review and, where practical, by a lint rule.
- **Breaking schema or error-code changes require an amendment to this ADR and a major CLI version bump.** Non-breaking additions (a new output field, a new error code) do not.

## Links

- `docs/specs/adrs/001_accepted_no_silent_failures.md` — structured errors are the agent-facing expression of fail-loud.
- `docs/specs/adrs/003_accepted_mvp_folder_structure.md` — the CLI lives in `apps/scripvec_cli/` as the MVP's one deployable.
- `docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md` — `--version` output surfaces the pinned embedding model identifier.
- `docs/specs/adrs/006_accepted_serialize_embedding_calls.md` — latency implications the CLI accepts rather than fights.
- `cr-001_vector_search_mvp.md` — the "minimal interface" referenced in that CR is this CLI.

## Conflicts surfaced

None. ADR-001 (fail loud) and ADR-006 (serialize embedding calls) are reinforced, not conflicted, by the agent-first surface.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-19 | created | initial authoring — CLI primary-user contract, agent-first defaults | Jeff Haskin |
