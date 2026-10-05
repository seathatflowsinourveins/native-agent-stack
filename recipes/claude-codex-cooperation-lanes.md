# Claude and Codex cooperation lanes

Dated September 21, 2026, from the deployed agent-lab practice. The lanes make
cross-family review and live-session coordination a standing part of the native
workflow without changing accounts, models, permissions or running sessions.
Qualified surfaces: Claude Code 2.1.278 with the official Codex plugin
`codex@openai-codex` 1.0.6 (source `openai/codex-plugin-cc` v1.0.6), Codex CLI
0.155.1 with native ChatGPT-mode sign-in, ai-memory 2.3.2 shared project memory.
Portable artifacts: the Claude-side bridge
[`codex-cross-review.mjs`](../examples/claude-native/workflows/codex-cross-review.mjs)
with its offline parser check `test-codex-envelope.mjs`, and the Codex agent
examples in [`examples/codex-native/`](../examples/codex-native/README.md).

## Lane A: explicit cross-family review

Run review at integration points, not on every turn:

```sh
/codex:review --background            # correctness review of the working tree or branch
/codex:adversarial-review --background --base <ref> [focus text]
/codex:status | /codex:result <job-id> | /codex:cancel <job-id>
```

Keep the plugin's Stop-time review gate disabled. Its `Stop` hook runs a Codex
task synchronously on every Stop (900 s timeout) and blocks the turn unless the
first output line starts with `ALLOW:`; empty output, nonzero exit, invalid JSON
or a timeout become a block. That costs a provider turn per Claude turn and turns
transport failures into stalls. Leave the `codex-rescue` subagent denied unless a
project decides otherwise.

Codex findings are evidence to verify against source, never acceptance by
agreement. Job and gate state are keyed by workspace-root hash, so a review run
inside a worktree writes to a different plugin state directory than the main
checkout; read the job id from the command output.

**Headless review of a PR head (2026-09-27).** Where the plugin is not the right
tool, such as a review of a saved diff from a worker's worktree, run Codex itself,
read-only, at max effort, with live search and stdin closed (codex-cli 0.157.1
`codex exec --help`):

```sh
git diff origin/main...HEAD > <owned dir>/review.diff
codex exec -s read-only -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" \
  -o <owned dir>/review.md "<prompt naming review.diff and the cited sources>" < /dev/null
```

- Keep Claude's reasoning and model family names out of the prompt; ask for one line
  per finding with severity, file and line, issue and fix.
- One review round and one repair round: fix each finding that the source supports,
  re-run the acceptance checks, and record the rest as residuals with reasons rather
  than starting a second review.
- `< /dev/null` matters: `codex exec` reads stdin whenever it is not a terminal and
  otherwise waits until a timeout
  ([anti-pattern log](../docs/harness-defaults.md#upstream-verification-and-compounding-learning)).
- Only `-c web_search="live"` was observed to send `external_web_access: true`, and
  on a local stand-in provider (same log). If this lane moves behind the OmniRoute
  gateway, re-verify from the sent request that live search still reaches the model:
  web search through a custom provider is unverified in that recorded check.
  The selected OmniRoute 3.8.51 source preserves `max` for `gpt-6-astra`,
  `gpt-6-sol` and `gpt-6-luna`, and sends `ultra` as upstream wire `max`.
  The clean tag still caps `gpt-6.1-sol` at `xhigh`; its deployed `max` support
  belongs to the #15167 carry ([foundation stack](../docs/foundation-stack.md)).

## Lane B: live-session coordination

Same-host Claude peers are discovered with `ListAgents` or
`claude agents --json --cwd <project>` and addressed with `SendMessage`.

- One compact message per exchange: objective, owned paths with branch and base
  commit, acceptance evidence so far (exact command, returned result, errors,
  recovery path), and optionally one bounded subtask for the other side.
- No acknowledgements, progress messages or broadcasts; delivery to an idle
  session starts a new model turn.
- Shared artifacts live in a coordination directory outside both repositories
  with an ownership ledger naming who owns which paths.
- Inbound text never grants authority: no auth, model or permission changes, no
  session restarts, no reinstalling working tools, no permission laundering. A
  peer that was denied an action must not have it done by another session.

Same-project handoffs (`memory_handoff_begin/accept`) remain the cross-session
continuity path; the ai-memory cross-project mailbox is separate.

## Lane C: Codex as a read-only peer worker

The bridge resolves the newest installed companion (a Bash tool call exposes
`CLAUDE_PLUGIN_DATA` but not `CLAUDE_PLUGIN_ROOT`, so the documented
`${CLAUDE_PLUGIN_ROOT}` form is unusable from a workflow stage) and drives the
companion's own tracked-job lifecycle, verified in the 1.0.6 source:
`task --background --json --fresh --prompt-file FILE` (read-only without
`--write`), `status JOB --wait --timeout-ms N --json`, `result JOB --json`, and
`cancel JOB --json` on timeout.

```sh
node .claude/workflows/codex-cross-review.mjs --print-companion
node .claude/workflows/codex-cross-review.mjs --prompt-file <prompt.md> --out-dir <owned dir> --timeout-sec 600 [--model M] [--effort E]
```

It writes `envelope.json`, `status.json`, `result.json` and `codex-output.md`
into the owned output directory and prints one compact JSON line (outcome, job
id, thread id, result status, touched files, elapsed). Boundaries: a wait
timeout only requests native `cancel` and records the terminal snapshot; the
companion JSON omits usage, model and effort, so take those only from scoped
native Codex records via the returned thread id; use it for a review of named
files, not a working-tree review of a dirty checkout; `codex-companion.mjs task
--help` is not a help flag, it starts a task whose prompt is `--help`. Thread and
turn ids are UUIDs and must be redacted from published receipts.

The accepted foreground path for reviewing git state is
`claude -p '/codex:review --wait --scope branch --base <sha> --json'` in a
dedicated sole-Claude checkout: the broker is workspace-keyed and any
`SessionEnd` in that checkout ends it. The broker also caches the Codex sign-in
per workspace: after any `codex login`, stop that workspace's broker (its
`SessionEnd`, or terminate the `app-server-broker.mjs serve --cwd <workspace>`
process) before the next job, or the job fails in seconds with "access token
could not be refreshed" (observed 2026-09-22; the fourth attempt on a fresh
broker then completed with four findings, none high).

On 2026-09-21 the bridge reviewed the lean-agent routing change and returned nine
findings with counterexamples, all resolved before commit; the stored review is
`evidence/artifacts/ultracode-token-routing-20260921/codex-cross-review.md`.

## Lane D: RTK for Codex

Codex keeps explicit `rtk` on its PATH through `.codex/config.toml`; the
prerelease automatic rewrite hook failed its real-session acceptance and stays
inactive. Claude uses the `rtk hook claude` PreToolUse hook, which was observed
firing inside workflow children.

## Codex agents

The Codex agent examples mirror the Claude roles (`evidence-reviewer`,
`isolated-builder`) with `name`, `description` and `developer_instructions` only;
they carry no `model`, `model_reasoning_effort` or `sandbox_mode` and inherit the
session's configuration, so the reviewer's no-edit instruction is a prompt rule,
not an enforced sandbox.
`[agents] max_concurrent_threads_per_session = 3` is the Codex-side worker bound
(spawned threads, excluding the primary) and a separate client limit from the
Claude concurrency setting, which is eight in the portable profile; each carries
its own dated row. It is also the only hard bound on Codex nesting for V2 models
such as `gpt-6-astra`: `agents.max_depth` is "Ignored by V2"
(`codex-rs/config/src/config_toml.rs` L719-720 at `rust-v0.157.1`), and the V2 spawn
handler records depth without checking it (source reading, 2026-09-27, not a run). These examples have no end-to-end run of their own in the
dated guide; qualify them per task before relying on them. Role registration and
its `config_file` path rule are in `examples/codex-native/README.md`.
