# Codex capability gate

The #381 capability gate asks whether a GPT-6 worker that runs `codex exec --profile stack-worker` can complete the
token tools' reads with the approvals and bindings the lane configures. Each gate runs real Codex sessions on the host
against the real MCP servers. It checks each tool's returned result and the source identity, never the model's claim,
and it keeps negative controls that must fail.

| Gate | Question | Gate rows (must pass) | Controls (must fail) |
|---|---|---|---|
| `jcodemunch` | In the main checkout, does one `order` call (`search_symbols` with `repo`) complete and return the symbol's signature? | 2 fixtures × 3 | `prompt` approval, disabled server (× 2 fixtures) |
| `ai-memory` | Does one `memory_query` call complete under approval policy `never`? This is decision [F7](../../docs/decisions/2026-09-26-token-practice-f1-f9.md#f7-codex-mcp-approval-2026-09-26). | 2 fixtures × 3 | `prompt` approval, disabled server (× 2 fixtures) |
| `m13` | With two sessions running at once in two worktrees, does each tool class, called without a cwd, read its own worktree's file? | 20 repetitions × 2 worktrees | disabled context-mode; context-mode bound to the other worktree (3 × 2 each) |

M13's classes are:
- the shell tool;
- `ctx_execute` without a cwd;
- `ctx_execute_file` with a relative path;
- `ctx_index` then `ctx_search`;
- serena `find_symbol`.

A gate row passes only when every class returns that row's own fresh token and no other:
- the token must come from a completed, error-free call made the way the brief prescribes: the relative path, no cwd or
  directory change, no absolute path and no token typed into the arguments;
- `ctx_search` counts only after a `ctx_index` of the fixture under the same source, and both must complete;
- any other token in any call of the class, completed or failed, means a wrong root or a stale result.

## Run

```sh
python3 tools/capability-gate/run_gate.py {jcodemunch,ai-memory,m13} [--keep]
```

**Prerequisites:**
- promptfoo 0.123.1 on `PATH`, or `CAPABILITY_GATE_PROMPTFOO`;
- codex-cli 0.157.1 as `codex`, or `CAPABILITY_GATE_CODEX`;
- the `stack-worker` profile in the Codex home;
- the Loki of [observability/backends](../../observability/backends/README.md), or `CAPABILITY_GATE_LOKI`.

The `jcodemunch` gate runs in the main checkout, because its jcodemunch server table lives in that checkout's
host-only project `.codex/config.toml`. `m13` creates two detached worktrees at `HEAD` and removes them afterwards.

**Output.** The first line is the verdict with counts per arm and per Loki reconciliation, and fits in the
400-character excerpt that `scripts/host_receipts.py record` keeps. For `m13`, one line of class tallies per arm
follows. Exit 0 means that:
- every arm produced exactly its expected rows (jcodemunch and ai-memory: 6 gate rows and 2 per control; m13: 40
  gate rows and 6 per control), each in its own conversation;
- every gate row passed;
- every control row failed by assertion, not by a provider error, with the outcome below, while the tools that control
  does not touch kept working;
- every row's MCP call count equals its Codex `codex.tool_result` count in Loki.

| Control | Predicted outcome |
|---|---|
| `prompt` approval | Every call to the server was refused with Codex's "MCP tool call requires approval, but approval policy is never" ([`mcp_tool_call.rs#L1612`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/mcp_tool_call.rs#L1612)); none completed. |
| Disabled server (jcodemunch, ai-memory) | No call to the server. |
| Disabled context-mode (m13) | No context-mode class called; the shell and serena classes read their own token. |
| context-mode bound to the other worktree (m13) | Each context-mode class, called as prescribed, returns the other tree's token, an error or nothing; the shell and serena classes read their own token. |

**Privacy:**
- promptfoo's database, its log files, the results file and the run log stay in a private temporary directory that
  is deleted unless `--keep` is given. Inherited `PROMPTFOO_*` settings are dropped and `PROMPTFOO_LOG_DIR` is pinned
  inside that directory
  ([`src/logger.ts#L227`](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/logger.ts#L227) honors it);
- telemetry, sharing and caching are off;
- the output holds counts only: no model text, tool results or conversation ids.

## How it works

- **Driver:** [promptfoo 0.123.1](https://github.com/promptfoo/promptfoo/tree/0.123.1), the version pinned in
  `manifests/stack.json`, with its `openai:codex-sdk` provider
  ([docs](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/providers/openai-codex-sdk.md)).
  - `working_dir` becomes the bundled `@openai/codex-sdk` 0.153.4's `--cd`, the same flag as `codex exec -C`.
  - `inherit_process_env: true` gives Codex the environment of a normal shell launch.
  - Model and effort are left to the profile.
- **Profile launcher.** [`codex-profile-exec`](codex-profile-exec) inserts `--profile "$CODEX_PROFILE"` after `exec`.
  The provider has no profile key, and codex-cli 0.157.1 rejects `-c profile=...`.
- **Scoring:** promptfoo's own assertions.
  - `trajectory:tool-used` checks the tool spans, for example exactly one `mcp jcodemunch/*` call
    ([reference](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/configuration/expected-outputs/deterministic.md#trajectorytool-used)).
  - The JavaScript assertions in [`assertions.js`](assertions.js) read the tool results from the provider's raw
    items: `response.raw`, `src/providers/openai/codex-sdk.ts:2430`.
  - The detail they look for is absent from the task text, and each assertion checks that absence against the
    rendered prompt.
- **M13 rows.**
  - [`m13_tests.js`](m13_tests.js) generates the rows, interleaved a, b, a, b.
  - promptfoo runs them in that order with two in flight (`async.forEachOfLimit`, `src/evaluator.ts:4102`), so the
    two worktrees' sessions overlap.
  - [`m13_hooks.js`](m13_hooks.js) is a `beforeEach` extension hook. It writes each row's fresh token into
    `.cg/<rep>/` of that row's worktree just before its session starts (`src/evaluator.ts:3587`).
- **Invoke counts.** They come from Codex's own OTel export, not from the transcript.
  - Runs through the SDK arrive in Loki as `service_name="codex_sdk_ts"`, because the SDK sets
    `CODEX_INTERNAL_ORIGINATOR_OVERRIDE`. Lane runs arrive as `codex_exec`.
  - `conversation_id` is the thread id. MCP records are keyed on `tool_namespace` (`mcp__<server>`).
  - The query filters `event_name="codex.tool_result"` in Loki; a label filter also matches structured metadata
    ([Loki v3.7.8](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/get-started/labels/structured-metadata.md#L74)).
    On the 2026-09-27 smoke window it returned the same 604 tool results as filtering the whole service stream.
  - `query_range` returns timestamps from `start` inclusive to `end` exclusive
    ([`loki-http-api.md#L474-L475`](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/reference/loki-http-api.md#L474-L475)).
    A full page continues from its last timestamp and drops records already seen, and a full page within one
    timestamp fails the run.

## Decision

Why promptfoo and native OTel, the alternatives and the overturn conditions are in the dated decision record
[`docs/decisions/2026-09-27-capability-gate-harness.md`](../../docs/decisions/2026-09-27-capability-gate-harness.md).

## Evidence class and limitations

A gate run is `native_proven` for the tools it names: real Codex sessions on this host against the real servers. The
assertions, hook and wrapper are documented local integration code. Promptfoo and Loki are upstream.

- **Sub-agents.** M13 covers two concurrent top-level sessions. Spawned sub-agents, which the M13 definition also
  names, are not covered.
- **Overlap.** At two in flight, two rows of one worktree can overlap in time. Per-repetition paths make that
  harmless, but not every moment has exactly one session per worktree.
- **Wrong-root index and search.** Under the wrong-root control, `ctx_index` reports that it indexed the fixture,
  and `ctx_search` under the same source then returns no results (6 of 6 rows in both 2026-09-27 M13 smokes). The
  control shows that the own token is not returned. It does not show which tree's file was indexed.
- **Shell class.** It is scored, but not reconciled against Loki. Codex's `functions.exec`, `exec_command` and `wait`
  envelope records do not map one-to-one to shell items, and that is a collector follow-up.
- **Originator.** SDK runs log as `codex_sdk_ts`, not the lane's `codex_exec`. Everything else is the lane's own
  profile.
- **`order`, not `route`.** The jcodemunch fixtures call `order` with explicit `search_symbols` arguments.
  - At jcodemunch-mcp 1.108.319, `route` with a `repo` runs its top action with the whole task text as the query
    (`shape_execute_args`, `counter.py:616-630`).
  - In the 2026-09-27 smoke, `route` with the sentence tasks "find the function register_file in
    scripts/host_receipts.py" and "find the function profile_servers_without_base in ..." completed in one call in
    6 of 6 runs. Neither symbol was in any of its 10 results.
  - `route` also has no default repository, so the fixtures pass `repo`.
  - The gate tests the tool binding and approval, not the lane's guidance about `route`.
- **Fixtures.** Each checks a detail of the current code: register_file's `relative_path: str`,
  profile_servers_without_base's `profile_bytes: bytes`, and memory_query's `hits` list. Update the fixture when that
  code changes.
- **Timing.** Loki keeps 72 hours, so the reconciliation runs at the end of each gate run.
