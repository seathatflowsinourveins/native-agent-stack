# Selected native Claude workflows and agents

These are project-authored saved scripts and agent definitions for the upstream
Claude Workflow runtime. The saved workflow scripts and the original source-scout,
evidence-reviewer and isolated-builder definitions derive from the deployed agent-lab
files in the retained portable qualification. Since 2026-09-23 every stage and agent
binds effort `max`, models unchanged
([decision](../../../docs/decisions/2026-09-23-max-effort-default.md)).
`review-changes.js`, `readiness-audit.js` and `layer-verdict-lane.js` are
byte-identical to agent-lab `b31f640` (the `max` change is agent-lab #43; the lane is
pinned at agent-lab `e070125` in `vendored-lanes.json`). The
qualification ran at the earlier efforts (Sonnet/medium, Opus/high); no native
run at `max` is recorded yet. These are local integration assets, not upstream
tests. The separate `semantic-evidence-reviewer` example received a later
explicit Opus declaration and reporting instruction to satisfy the combined
portable contract; that change has local checks and no new native provider
qualification. Since 2026-09-26 this catalog diverges from agent-lab in four
definitions: `isolated-builder` holds only Serena's read tools and preloads context-mode
(its verification-before-completion preload was removed on 2026-09-28 with that skill's
trial, [skills-trial record](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md#addendum-2026-09-28-verification-before-completion-removed-conflict-rule));
`stack-researcher`, `stack-verifier` and
`security-reviewer` are new roles with local checks and no native run recorded yet.
The new builder preload also has no native qualification
([decision](../../../docs/decisions/2026-09-26-stack-agents-role-dispatch.md)).
## Byte-identity check

`SHA256SUMS` in this directory (`sha256sum -- *.mjs *.js *.json`, excluding
`README.md` and `SHA256SUMS` itself) is checked byte-for-byte by the
`validate` workflow's "Check example workflow byte identity" step
(`.github/workflows/validate.yml`) on every push and pull request. It is
refreshed on purpose whenever one of these example files changes: regenerate
it with the same command from this directory and commit the new file in the
same change as the edited example. An unexplained mismatch on an unrelated PR
means one of these files changed without an intentional update here.

Use [the native recipe](../../../recipes/claude-native-ultracode.md)
for settings, authoring, worker models and lifecycle boundaries, and
[the cooperation lanes](../../../recipes/claude-codex-cooperation-lanes.md) for
the Codex side.

## Adopt

1. Copy `agents/` into the destination project's `.claude/agents/` and the
   `.js`/`.mjs` files here into `.claude/workflows/`. Preserve existing
   same-name files until their differences are reviewed.
2. Copy `contract.config.json` beside the workflows and point its paths at the
   project: `settings` (the project's `.claude/settings.json`, merged from
   [`ultracode.settings.json`](../ultracode.settings.json)), `instructions` (the
   file that carries the sizing sentence and the `effort: 'max'` stage rule,
   for example `AGENTS.md`),
   `contract_doc` (a document holding this README's `## Workflow contract`
   section) and, when the project keeps usage receipts, `usage_receipts_dir`,
   `routing_doc` and `task_record`. A configured path that does not exist fails
   the suites; nothing is skipped silently.
3. Give the session a permission source that covers the Workflow tool. A headless
   `claude -p` run of a saved workflow is refused ("Review dynamic workflow before
   running", observed in the 2026-09-21 qualification, see
   [the routing guide](../../../docs/ultracode-token-routing-20260921.md)) when the
   loaded settings carry no permission mode or allow rule for it; keep that rule in
   user settings or the launch flag, since the portable settings file selects no
   permission mode. A `claude -p` run also stops waiting for its background
   workflow once `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` of idle time passes after
   the final turn (default 600000, 10 minutes; `0` waits indefinitely; Claude Code
   2.1.182 or later; [environment variables](https://code.claude.com/docs/en/env-vars)).
   Set it for any run that can outlast that, and bound the run externally when you
   set `0`.
4. Start a fresh native session or run `/reload-skills`, then invoke a saved
   workflow by name with explicit `args`. Load the bundled `/workflow-authoring`
   skill before editing a script.

MCP lanes (Serena, SocratiCode, jCodeMunch, QMD, Context Mode, ai-memory) are granted by
name and stay deferred behind `ToolSearch`; a project without one of them still
launches the agents with the remaining tools. Without Context Mode the reviewer
reads the inventoried files in full and marks diff-dependent claims unverifiable.

## Agents

| Agent | Model, effort | Tools | Use |
| --- | --- | --- | --- |
| `source-scout` | Sonnet, max | Read, Grep, Glob, Bash; no project instructions loaded | exact extraction, inventories, running the acceptance commands a task names (raw through `rtk proxy` where `rtk` is installed) |
| `evidence-reviewer` | Opus, max | Read, Glob, Grep, ToolSearch and named read-only MCP tools; no Bash, Edit or Write | independent review from source and recorded evidence |
| `security-reviewer` | Opus, max | Same named read tools as evidence-reviewer behind ToolSearch; no Bash, Edit, Write, WebFetch or Skill; `security-best-practices` preloaded | adversarial security review, including agent permission and tool-surface widening; reports findings, never fixes |
| `isolated-builder` | Opus, max, in the coordinator-created worktree its brief names | Read, Edit, Write, Glob, Grep, Bash, ToolSearch and named MCP read tools (no Serena symbol-edit tool); `context-mode:context-mode` preloaded | a bounded implementation from a clear contract |
| `stack-researcher` | Opus, max | Read, Glob, Grep, Bash, WebSearch, ToolSearch and named Context Mode, QMD, ai-memory, Serena and jCodeMunch read tools; no Edit, Write, WebFetch or Skill | research from the web, documentation, repository and catalog, returned inline |
| `stack-verifier` | Opus, max | Read, Glob, Grep, Bash, ToolSearch and named Context Mode tools; no project instructions; no Edit, Write, WebFetch or Skill | re-running named commands and deciding claims from their output and source; never fixes |

Context Mode `ctx_execute*` can run commands, so the reviewers' read-only rule
there is an instruction, not a sandbox; the same holds for the Bash of the
scout, the researcher and the verifier. Two
more definitions ship here. `semantic-evidence-reviewer` (Opus, max; Read, Glob,
Grep; the `typesafe-ai` skill) is project-local to agent-lab and published
separately. `blind-lane-reviewer` (Opus, max; Read, Glob and Grep; no preloaded
skill and no project instructions) is the agent every `layer-verdict-lane` stage
names, vendored byte-identical from agent-lab `e070125` and pinned in
`vendored-lanes.json`. The contract suite covers every file in `agents/`.

## Workflows

- `review-changes`: supply a base reference, owned source paths and exact check
  commands. `source-scout` inventories the diff and runs the checks; `evidence-reviewer`
  refutes or confirms every behavior claim from source; a second `source-scout`
  re-runs every check without seeing the first result, and the script compares
  exit codes and quoted totals. Acceptance requires every claim confirmed exactly
  once with evidence, every requested path inventoried, every requested check with
  exactly one nonblank result and exit zero in both runs, and no defects or
  verification gaps. Refuted or corrected claims require coordinator resolution;
  incomplete evidence fails closed.
- `readiness-audit`: supply document paths, read-only commands and a question.
  `source-scout` readers observe each source; the verifier stays on the default
  workflow child because it must re-run commands with Bash (the vendored script
  predates `stack-verifier`, which ad-hoc verification stages use). Omitted, unexecuted,
  missing or unverifiable evidence cannot complete the audit; a complete audit can
  conclude that the project is not ready.
- `layer-verdict-lane`: this catalog's own Claude lane of the layer-verdict
  convergence, vendored byte-identical under `SHA256SUMS`. After
  `tools/sota-convergence/lane_packets.py` writes the packets, pass `repo`,
  `packets` (`{catalog, layer_id, path, sha256}`), the lane `prompt` and the
  `launch` identity (`tools/sota-convergence/claude_lane_args.py` prints all
  four). Every stage runs as `blind-lane-reviewer` (Read, Glob and Grep, no
  skills, no project instructions): per packet one proposal, two lenses that
  try to refute it and one revision round after a refutation. It writes
  nothing; `tools/sota-convergence/claude_lane.py` collects the result and
  `record_verdicts.py` applies the rules (see
  `docs/decisions/2026-09-23-verdict-integrity.md`). It needs the vendored
  `examples/claude-native/agents/blind-lane-reviewer.md`, so a project that does
  not record layer verdicts can leave it out.

Both workflows retain native model/schema errors and missing results. Claims and
returned source summaries remain model judgments; deterministic coverage checks
cannot prove they are true. Arguments are trusted coordinator inputs, not
instructions copied from web pages or retrieved memory.

## Usage accounting

After a run, `node .claude/workflows/child-usage.mjs <transcript dir printed by
the Workflow tool>` or `--latest` returns each child's requested and resolved
model, effort, provider-returned usage and first-prompt size, and exits 1 when a
child returned null, was substituted, resolved no model or inherited the
coordinator model. Since 2026-09-29 it also exits 1 when a child's return is
incomplete: an empty result, a result that is only a wait notice, or a
background task the child left running at its final message (`return_quality`,
`final_return` and `issues` per child; see
[U2 measurement fields](#u2-measurement-fields-2026-09-29)). The counters are provider-returned and are not comparable
to RTK, Context Mode, jCodeMunch or Headroom estimates.

Each child also carries a `lanes` object read from its own transcript
(`child-usage.mjs` changed after `v2026.09.26.2` to add it): tool calls,
Bash calls, MCP calls per server (`mcp__<server>__<tool>`), Skill calls by skill,
ToolSearch calls and the tools they loaded, RTK hook rewrites (a `PreToolUse:Bash`
row from `rtk hook` whose stdout carries `updatedInput`) and `rtk` commands the model
typed itself, fetch routing (`WebFetch`, `ctx_fetch_and_index`, `curl`/`wget` in command
position of the text a shell runs, also behind a shell keyword such as `do` or `then`,
so quoted text and heredoc bodies count only under `sh -c`, `eval`, `ssh` or a shell
heredoc, escaped characters and comments never count, and `$(...)` or backticks inside
double quotes or an unquoted heredoc still run (bash(1) QUOTING, COMMENTS and Here
Documents), with loopback-only calls apart; in these legacy lane counters a fetch run inside a Context Mode sandbox, a
`gh api` call or an HTTP call in a script is in no lane, so `ctx_fetch_and_index_share`
compares those three lanes only), the
SubagentStart hook types, and whether an
injected block's marker (default `<context_window_protection>`, the opening tag of
Context Mode's routing block; `--marker <text>` for another) sits in the first
prompt or in SubagentStart hook context. A marker inside tool input or output does
not count. `--rtk-db <RTK history.db>` also joins each Bash call to RTK's
`hook_decisions` row by `tool_use_id`, opened read-only through `node:sqlite`
(Node 22.13 or later); `allow` plus `ask` is RTK's own "covered" outcome.

### PR-A measurement fields (2026-09-27)

`lanes.measurement` in a run, and `actors[].measurement` plus each group's
`measurement` in a sweep, compute the preregistered M3/M4/M5 fields. A sweep
also reads main transcript JSONL files under its explicit roots and reports
them in `main`, separately from child populations. Use the project directory
as a root to include the native `<session>.jsonl` next to `<session>/subagents`.
Actor ordinals are local to the supplied roots; private run/task identity joins
remain the caller's responsibility. Existing lane counters remain available
for comparison with historical receipts; their three-lane fetch share is **not M4**.

```sh
node examples/claude-native/workflows/child-usage.mjs --lanes-sweep \
  --root "${CLAUDE_ROOT}" --since "${SINCE}" --until "${UNTIL}" \
  --rtk-check --rtk-db "${RTK_DB_PATH}" --exceptions "${PRIVATE_EXCEPTIONS}" \
  --call-ledger "${PRIVATE_LEDGER}"
```

`--call-ledger` writes the private per-call ledger (below) to a new file; stdout
is the same with or without it and holds no call or session ids.

#### U2 measurement fields (2026-09-29)

PR-A items 1, 4, 5, 6 and 7, protocol M15, binding decisions B5, B8 and B9 and
the U2 corrections add these fields to every measurement (`actors[].measurement`,
each group's and `main`'s `measurement`, and run mode's `lanes.measurement`).
Their host scans, upstream sources (URL, fetch time, sha256 and the sentence each
rule rests on) and the base-versus-U2 differential are in
[`evidence/artifacts/pra-u2-differential-20260929`](../../../evidence/artifacts/pra-u2-differential-20260929/README.md).
The per-rule citations sit beside each rule in `child-usage.mjs`.

**Hook context (item 1).** `hook_context.inserted` counts `hook_additional_context`
rows and `inserted_blocks` their content entries (one per hook whose context
Claude Code delivered), per event in `by_event` and `blocks_by_event`. A claim
is a `hook_success` row whose stdout asks for context and is never an insertion:
`claimed_by_event` counts JSON stdout with `hookSpecificOutput.additionalContext`
on any event, and `claimed_plain_stdout` plain stdout on the four events whose
plain stdout Claude Code adds (`UserPromptSubmit`, `UserPromptExpansion`,
`SessionStart`, `PostModelSwitch`; [hooks](https://code.claude.com/docs/en/hooks), "Exit code 0").
Other `hook_*` rows are counted apart in `other_hook_rows`. An MCP hook name
too long for `(other)` is folded to `<Event>:mcp__<server>` (`hook_names_folded`).
Aggregates add `actors_with_insertion`. M12 reads `measurement.hook_context`
(`inserted` 0 on blind actors), not the legacy SubagentStart flag.

**Loaded, never called (item 5).** `loaded` counts the tool references a
ToolSearch result returned per MCP server, and `loaded_not_called` those of
servers the actor attempted no call on in the window (references, the #432
unit). Aggregates add `loaded_actors` and `loaded_not_called_actors`: actors
per server, the unit of the historical "Loaded, never called" baseline row.

**Large-result shapes and section-1 figures (item 4).** Every sizes object
(`m3`, `m5`, `by_carrier.*`, `exceptions.*`) counts, among its results over
5,120 bytes, `large_json` (the trimmed payload opens with `[` or `{` and
parses), `large_uniform_keys` (an array, or the one value of a one-key object,
of at least five objects with one key set), `large_uniform_flat` (those whose
values are all primitive; TOON v4.1.1 README, "All objects have identical fields
with primitive values"), and `large_shape_unknown` (a non-text block, a result
without its call, or a wrapper this reading cannot remove), so 0 never stands
for "not inspected". The payload is the result text, text blocks joined with
nothing, after its carrier's wrapper: the code echo context-mode puts before
`ctx_execute` and `ctx_execute_file` output, and the line numbers of a Read.
Aggregates add the AA §1 per-actor figures: `shell_web_large_results_per_actor`
(nearest-rank percentiles of Bash, rtk proxy and WebFetch results over the
limit), `actors_with_mcp_call`, `actors_with_non_ctx_mcp_call` and
`actors_with_ctx_results`.

**Complete usage (B9, U2 correction 1).** Each `usage.messages[]` row adds
`cache_creation_5m`, `cache_creation_1h`, `speed`, `service_tier` and
`inference_geo`, each null when the record lacks it, never 0; the combined cache
creation counter and the deduplication by message id are unchanged.
`usage.iterations[]` entries of type `advisor_message` (an advisor
sub-inference, billed at its own model's rates and outside the top-level
counters) are `usage.advisor_iterations`, summed in `advisor_totals` and
`totals_including_advisor`. `usage.complete` is false, with
`usage.iteration_issues` naming the reason, when a message carries an entry this
reading cannot read, when its top-level counters differ from the sum of its
`message` entries, or when an advisor result has no usage or an advisor call no
result ([beta Messages API](https://platform.claude.com/docs/en/api/beta/messages/create),
`BetaIterationsUsage`; [advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool), "Usage and billing").

**Call states (item 7, M14).** `call_states` gives every call attempted in the
window one state in the sealed M14 names, per actor and per MCP server
(`by_server`):

| Field | Calls |
| --- | --- |
| `attempted` | every call; `attempted = executed + rejected + invalid + cancelled_with_result + cancelled_or_unfinished + unknown` |
| `executed` | `succeeded + failed + interrupted` |
| `rejected` | never ran by a decision, split in `rejected_by_source`: `config`, `hook`, `user`, `other`, `declined` (the OTel `tool_decision` sources) |
| `invalid` | a `<tool_use_error>` the client raised before running the call |
| `cancelled_with_result` | the client's "Cancelled" or "Not run" results, kept apart until a Loki probe shows whether such a call emits `tool_result` |
| `cancelled_or_unfinished` | no result and no native status: the sealed "(no result)" state |
| `unknown` | an outcome an adapter could not read |
| `decided` | null: a transcript cannot observe the `tool_decision` event |

`background` and `sandbox` flag calls within those states. `calls_without_result`
keeps its published meaning: `cancelled_or_unfinished` plus the no-result calls
a native status decided. `mcp_states` stays the #432 reading, a legacy view, and
`cli_lanes.lanes.*.failed` keeps U1's meaning (`is_error` calls, `not_executed`
a subset), so M14's failed for a lane is `failed - not_executed`.

**The private call ledger.** `--call-ledger <file>` writes one JSON line per
attempted call: `session_id`, `owner` (the agent id, `main`, or null for a row
with neither, such as a Codex bridge row), `tool_use_id`, `tool`, `server`,
`state`, `cause`, `native_status`, `background`, `sandbox`, `code_mode` and
`m15_class`, plus `actor_ordinal` in a sweep (the published actor's number) and
`label` and `superseded` in run mode. The join key is (session_id, tool_use_id),
as the E2E README's M14 row requires. The file is created, never written over
(an existing file is refused, so its mode never stands for 0600), with mode
0600, in an existing directory outside every git work tree; a refusal exits 2
before any output. Run-mode stdout holds agent ids and the transcript directory
by design, but no tool_use_id or sessionId value.

**M15 infrastructure-error classes.** `m15.by_server[server]` classifies every
attempted MCP call (`mcpErrorClass`; each template is anchored and read by a
linear scan; the sources are the kernel comments and `sources.json`):

| Class | Group | Source |
| --- | --- | --- |
| `approval` | infrastructure | openai/codex rust-v0.157.1 `core/src/mcp_tool_call.rs:1612` |
| `boundary`, `binding` | infrastructure | context-mode v1.0.169 `src/server.ts:1196-1201` (`binding` when the Codex adapter flags a root mismatch) |
| `timeout` | infrastructure | the client's MCP idle timeout ([MCP](https://code.claude.com/docs/en/mcp)); `server.ts:1872, :2152, :3815` |
| `module` | infrastructure | a ModuleNotFoundError or `Cannot find module` in the exit's stderr |
| `connection` | infrastructure | "MCP server ... is not connected"; SDK 1.30.1 "Connection closed" |
| `server_error`, `storage_directory`, `usage_error`, `invalid_arguments`, `unmatched` | new class (our misuse until reproduced) | `server.ts` error texts; `session/db.ts`; MCP -32602 |
| `outcome_unknown`, `invoked_command_exit_indexed`, `echo_mismatch` | unknown | no result or state; an indexed exit; output without its code echo |
| `policy_deny`, `remote_fetch`, `search_throttle`, `rejected`, `invalid`, `cancelled_with_result` | unassigned: graded as errors until Amendment 4 assigns them | the deny firewall, fetch failures, search throttling, M14 states |
| `invoked_command_exit` | excluded (the frozen M15 row: "A non-zero exit from the command the child ran is excluded") | the command's own exit |

Grading reads `rate_upper_bound`, the ceiling: every attempted call that neither
succeeded nor ended in the invoked command's own exit. The frozen M15 row names
six infrastructure classes and none of the unassigned ones, so until a dated
amendment (Amendment 4) assigns them, they count as errors (the U2 design 5.3;
binding decisions: the harder-to-pass reading). A server whose every call fails
with the client's "No such tool available" `<tool_use_error>` (an `invalid`
call) therefore reads 1. The ceiling is a residual, so a class a later template
adds counts too. `unassigned_errors` is that residual after the named groups, and
`over_threshold` is the verdict on the ceiling's count
(`(attempted - succeeded - invoked_command_exit) * 100 > attempted`). Rates are
rounded to four places, so a grader compares the counts, never the rounded rate.
`rate` counts infrastructure, new-class and unknown calls (B2: an unknown is not
a success), which is the rate if Amendment 4 finds the unassigned classes not
infrastructure. `rate_lower_bound` also counts the unknowns as successes.
`threshold_sensitive` marks a server whose `rate_lower_bound` and
`rate_upper_bound` fall on different sides of `m15.threshold` (0.01): its
verdict depends on the unknowns or on the class assignment.
`every_error_classified` is the `classify_every_ctx_error` criterion (no
`unmatched`, no `echo_mismatch`).

**Incomplete returns (item 6).** In run mode each child adds `return_quality`,
its journal result read as `empty`, `wait_notice` or `ok` (null for no result):
a string as it is, the E2E `{ answer, evidence }` schema by its `answer`, any
other value by its leaves (to depth 6 and 10,000 values; `wait_notice` needs at
least one string and every non-blank string a wait notice). A wait notice has no
upstream definition: the trimmed text has at most 400 characters and its first
sentence is, after at most three non-word characters and at most two of `still`,
`now`, `I'll`, `I will`, `I'm`, `I am`, `let me`, `we'll`, `we will`, "wait" or
"waiting" and then "for", "on" or "until" (a linear word scanner). Every
measurement adds `final_return`: `status` (`measured`; `not_applicable` when no
row carries a provider message id, as with the Codex bridge's rows;
`unobserved` when a row lies at or after `--until`), the final assistant row's
kind (`text`, `tool_use` or `other`), `empty_text` and `wait_notice` for a final
text, and `background_started`, `background_pending` and
`background_pending_with_events`. A background task starts with a Bash
`backgroundTaskId`, a Monitor or Workflow `taskId`, or an async Agent's
`agentId`, and ends with a `<task-notification>` whose `<status>` is
`completed`, `failed`, `killed` or `stopped`, or with a TaskStop that names it;
a Monitor event (no status) ends nothing. A foreground subagent's background
command "stops when that subagent gives its final response"
([tools reference](https://code.claude.com/docs/en/tools-reference), "Background commands"),
so a pending task's result never reached the return. The child's `issues` then
hold `empty result`, `wait-notice result` or `returned with N background
task(s) that had no completion notification`, which make it and its run
incomplete (exit 1); a superseded attempt keeps them as ordinary issues.
Aggregates count actors by status and final kind, sum the counters and add
`actors_with_background_pending`; an actor that ran past the window end is
counted in `final_return.unobserved`, never as a zero.

#### CLI lanes by command position (2026-09-28)

`measurement.cli_lanes` counts the CLI lanes of the #381 Gate A plan (PR-A item 3):
`toon`, `repomix`, `markitdown`, `qmd`, `headroom`, `jcodemunch-mcp`,
`codebase-memory-mcp`, `ai-memory`, `serena`, `context-mode`, `mcporter` and
`rtk_proxy`. A lane is the exact basename of its executable at the
`manifests/stack.json` pin (`serena` or `serena-agent` for Serena; `rtk`
followed by `proxy` for `rtk_proxy`), from each package's own bin or script
declaration (cited in `child-usage.mjs` at `LANE_EXECUTABLES`). Two
lane-membership decisions (2026-09-28): `gcm`, the separate Groq CLI that the
jcodemunch-mcp package also installs, and `serena-hooks`, Serena's hook entry
point, are **not** lane executables. Server starts such as
`headroom mcp serve` or `npx -y repomix --mcp` are lane calls.

`commandInvocations(command)` (exported) reads the text of a shell call with the
[tree-sitter-bash](https://github.com/tree-sitter/tree-sitter-bash) grammar and returns one record for each
command it finds, in source order. That is the parser
[openai/codex rust-v0.157.1](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/shell-command/src/bash.rs)
uses for the same job (`tree-sitter-bash = "0.25"`,
[`codex-rs/Cargo.toml:522`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/Cargo.toml#L522)):
`try_parse_shell` (:13), `parse_shell_lc_plain_commands` (:124) and `parse_plain_command_from_node` (:162) walk the
`command` nodes and read a word only from a `word`, `number`, `string`, `raw_string` or `concatenation` node, so a
word with an expansion is unknown. This reading walks the same tree. It differs in what it does with the words
(wrappers, runners and shells are followed to the program they run) and in a tree with an error, which Codex
rejects whole (:140) and this reading still reads where it is valid; `parse_errors` counts those calls.

**Provisioning and fail-closed.** Nothing is vendored. [`shell-parser.pin.json`](shell-parser.pin.json) pins
`web-tree-sitter` 0.27.0 and `tree-sitter-bash` 0.25.1 by npm integrity and by the sha256 of the six files the loader
runs, and records the install command (`npm install --prefix <directory> --ignore-scripts --no-audit --no-fund
--save-exact web-tree-sitter@0.27.0 tree-sitter-bash@0.25.1`). `loadShellParser(dir)` takes the directory from its
argument, then the CLI's `--shell-parser <dir>`, then `CHILD_USAGE_SHELL_PARSER`, then
`~/.local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1`. It checks every pinned file and both integrity values
of the install's `package-lock.json` before it runs any of it (it imports a private copy of the bytes it hashed, so
the hashed bytes are the executed bytes) and returns `{ ok: true, versions, wasm_sha256 }` or `{ ok: false, reason }`,
the reason being `not_installed`, `hash_mismatch`, `load_error` or `not_loaded` (a process that never awaited the
loader); no path is reported. Without a verified parser nothing is read and no lane is ever counted from a text
scanner: `commandInvocations` returns `null`, `cli_lanes` is `{ status: 'parser_unavailable', reason }`, and
`measurement.proxy` keeps the earlier prefix rule with `rule: 'prefix_fallback'` (`invocations` and `in_ctx_code` are
then `null`). An explicit `--shell-parser` that cannot be honored exits 2; a missing default or environment install
leaves the rest of a report unchanged. In an aggregate `cli_lanes.status` is `measured`, `incomplete`
(`actors_measured` and `actors_unmeasured` name the split, and the sums are lower bounds), `parser_unavailable` or
`not_measured`, and `proxy.rule` is `command_position`, `prefix_fallback` or `mixed`. A measured `cli_lanes.parser`
holds the two versions and the two `.wasm` sha256 values. The pin records tree-sitter-bash v0.25.1 as tag commit
`a06c2e44` ("Regenerate parser for 0.25.1") although the npm package was published from the commit before it,
`80132668`; the pinned `.wasm` is the npm tarball's file (see the
[decision record](../../../docs/decisions/2026-09-29-shell-command-parser.md)). No workflow, adoption script or
manifest installs the parser yet (a follow-up outside this change), so on CI the lane tests skip and only the
fail-closed tests run: CI proves the gate, not lane counts.

**What is read.**

- Every `command` node counts wherever it sits: inside substitutions (in strings, arithmetic expansions, arrays and
  the unquoted-delimiter heredoc bodies a shell expands), process substitutions, subshells, compound statements, the
  conditions and bodies of `if`, `while`, `for` and `case`, pipelines, lists, negations and redirected statements. A
  function body counts where it is defined, once, whether or not the function is called and however often; every
  branch of a `case` and both sides of `&&` and `||` count, since this is a static reading of the text, not a trace.
  Never a command: array elements, `case` patterns, `[[ ]]` operands, function names, `for` values, comments and the
  words of a program that is not a lane.
- A word is a literal or unknown. Quotes and escapes resolve as bash does (a backslash inside double quotes stays
  unless it precedes `$`, a backquote, `"`, `\` or a newline; `$'...'` is decoded). An expansion, a glob, a brace
  expansion or a tilde expansion makes it unknown, except that a tilde prefix keeps a program's name
  (`~/bin/qmd`). An unknown word in program position is an unresolved program and never a lane. Two words with no
  blank between them are one word.
- Shell strings: `bash|sh|dash|zsh|ksh -c STRING` reads the first operand after the options as a script (`-n`, `-D`
  and `-o noexec` run nothing; `--` and `-` end the options; the operands after the script are `$0` and positional
  parameters, data). `eval WORDS` joins its literal words with blanks and reads the result. A script with an
  expansion is read with a placeholder for the unknown text (`eval 'qmd $X'` counts qmd; `eval '$X'` is unresolved).
  `ssh` runs the words after its destination on the remote host, whose lanes count only in `remote_invocations`
  (a remote `bash` is a record of its own). Strings nest to 32 levels; the text of a deeper level is one
  unresolved record.
- Standard input: a heredoc or here-string that feeds a shell reading its script from standard input (no `-c`, no
  file operand, or `-s`) is read as that script. The owner is found through every wrapper below and `rtk proxy`,
  and is the last command of a list, pipeline or negation; `xargs` consumes the input instead. The
  body of any other heredoc is data, except the `$( )` and backquote substitutions of an unquoted-delimiter body,
  which the outer shell runs; a shell that reads an unquoted body reads it after that expansion.
- `rtk proxy` resolves its program as `execvp` does, with no shell: only real executables (`env`, `timeout`, `nice`,
  `nohup`, `stdbuf`, `xargs`, `sudo`) act as wrappers there; `command`, `exec` and `!` run no lane, `time` is
  unresolved (an executable on hosts that have GNU time), and an expansion in its one argument leaves the program
  unresolved. The same holds after any wrapper that is itself an executable (`env`, `nice`, `nohup`, `stdbuf`,
  `timeout`, `xargs`, `sudo`, and the builtin `exec`, which replaces the shell with one): the next word is run with
  `execvp`, so `env eval qmd` and `nohup command qmd` run nothing; `command` and `time` are the shell's own and
  pass a builtin on (`command eval x` runs).
- Where tree-sitter-bash 0.25.1 reads bash differently, the reading repairs it, each repair checked by a run of
  real bash (below): a `!` after another `!` or after `time` is negation, not a command name; a backquoted body whose
  backslash precedes `$`, a backquote or `\` is unescaped and read again; the words after a redirection's target are
  arguments of its command (`nice 2>&1 qmd`); `time` may be followed by `!` and assignment words; a heredoc with no
  delimiter line ends at the end of the text; a word the grammar cut (`a=$x/$y-$z`) is one word; a line that begins
  with a backslash starts a command of its own; and the commands the grammar joined to the previous one (an unquoted
  `==` before `;`, `&&`, `|` or a newline, or a redirection after a heredoc operator followed by `|` or `;`) start
  again at the separator or newline.
- An ERROR node and everything under it are skipped, and the call counts once in `parse_errors`; the valid parts of
  the tree still count.

**Checked against real bash.** `tests/test_command_position_oracle.py` runs generated and hand-written shell texts under
real bash 5.2 with `env -i`, a temporary HOME and working directory, a `PATH` of logging stubs (the lane executables,
mcporter and rtk) and symlinks to `env`, `timeout`, `nice`, `nohup`, `stdbuf`, `xargs`, `cat`, `bash`, `sh` and `dash`,
and requires the lanes that ran to equal the lanes the kernel reads. The claim covers what a run can show: an alias, a
function never called, a branch or loop a run does not reach, `exec`, `sudo`, `ssh` and the shapes in the limits below
are left out of the generators, not out of this text. It skips with a message when the parser or bash is missing.
`evidence/artifacts/pra-u1-differential-20260929` holds the differential of this reading against the scanner reading it
replaced, on the tests' covering commands, seeded fuzz inputs and this host's real commands, with every difference
classified (counts only).

Each command's words are then resolved past `NAME=value` assignments, through:

- wrappers: `timeout`, `env` (including `-S`), `nice`, `stdbuf`, `command`, `exec`, `time`, `nohup`, `sudo` and
  `xargs`, with the options their POSIX, GNU coreutils 9.4 and sudo 1.9.15p5 synopses list (`time` is bash's reserved
  word, so a `!` and assignment words may follow its options). `command -v`/`-V` and sudo's list, edit and validate
  modes run nothing;
- package runners: `npx`, `bunx`, `bun x`, `pnpm dlx` and `yarn dlx` map an npm package to its lane; `uvx`,
  `uv tool run` and `pipx run` map a PyPI project; `--package`, `--from` and `--spec` name the executable itself;
  and `python -m markitdown` counts for markitdown. `npx markitdown` names a different npm package and has no lane;
- `rtk proxy`, as in
  [rtk v0.50.0 src/main.rs](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L68-L90)
  and its [proxy dispatch](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L3008-L3042).
  `-v`, `--verbose`, `--ultra-compact` and `--skip-env` may precede `proxy`. After it, `--ultra-compact`, `--skip-env`,
  `-h` and one `--` still bind. The installed rtk 0.50.0 runs a `-v` there as the program. rtk runs the proxied
  command with no shell, and one quoted argument is shell-split, so `rtk proxy 'qmd search x'` counts for both
  `rtk_proxy` and `qmd`.

A program word with an expansion (`$QMD`, `"$(which qmd)"`), or one behind an
option the reading does not know (bash's `exec -a`, GNU `xargs -P`, an unlisted
runner option), is counted in `unresolved_programs` and never becomes a lane.
Lookups (`command -v qmd`, `type`, `which`, `hash`), data (`grep -n qmd`,
`git commit -m "use toon"`, `echo 'rtk proxy ls'`, a heredoc that writes a
script), registrations (`claude mcp add context-mode -- npx -y context-mode`)
and `rtk` filters (`rtk git status`) invoke no lane.

Fields per actor, summed in each group, which also adds `actors_with_success`
per lane (actors with at least one succeeded call of the lane):

- `lanes.<lane>`: `calls` are calls with at least one local, non-excluded
  invocation of the lane, and `invocations` count those invocations. The call
  states `succeeded`, `failed`, `unfinished`, `unknown` and `interrupted`
  partition `calls`. `not_executed` counts the failed calls that never ran, and
  `background` the succeeded calls that only started. `ambiguous` counts calls
  with more than one simple command or a background `&`, whose one state covers
  every command: `qmd search x || true` reads succeeded and ambiguous.
  `via_mcporter` counts calls that reached the lane through an mcporter alias.
  `by_carrier` splits calls into `bash`, `rtk_proxy`, `ctx` and `nested`
  (sandbox-nested Codex commands).
- `mcporter_downstream.<server>`: `calls` and the same states for mcporter
  calls. The key is the server's name when it is one of the stack's own servers
  (`codebase-memory`, `context-mode`, `jcodemunch`, `serena`, `socraticode`,
  `qmd`, `headroom`, `ai-memory`: `manifests/stack.json:280`, `:407`, `:629` and
  `:966` name three of them, the other five are the U1 pivot decision's list,
  see its [record](../../../docs/decisions/2026-09-29-shell-command-parser.md)).
  Any other server reads `(other)`, an HTTP selector or `--http-url` `(http)`, an
  ad-hoc stdio command `(stdio)`, and a call whose server no name can be read
  for `(unresolved)`. No host, id or other string reaches the output, and
  `program` in a record is set only for a lane executable or a name the reading
  interprets itself (a wrapper, a shell, `eval`, `ssh`, `rtk`).
- `excluded_version_help.<lane>`: invocations whose own words (up to `--`; for
  `rtk proxy`, rtk's words before the proxied program) include `--version` or
  `--help`. The pinned aliases are rtk's clap `-V` and `-h`, and mcporter's own
  rule, which is not the same: mcporter takes the first word after its global
  flags as the command, and `--help`, `-h`, `help` (or no command word) there
  prints help while `--version`, `-v` or `-V` there prints the version
  ([openclaw/mcporter v0.14.1 `src/cli.ts:137-145`](https://github.com/openclaw/mcporter/blob/v0.14.1/src/cli.ts#L137-L145),
  `src/cli/help-output.ts:200-210`); every subcommand handler then removes help
  tokens from its whole argument list with no `--` boundary
  (`src/cli/flag-utils.ts:34-41`), so a help token anywhere excludes the call
  (`mcporter call linear.x -- --help` is excluded) while a version token after
  the command is an ordinary unknown flag (`mcporter call linear.x --version`
  is a call). A bare `mcporter` prints help and counts here. So does
  `rtk --version`, under `rtk_proxy`. Other tools' `-h` or `-V` count as calls.
- `calls_with_lane_invocation`, `unresolved_programs`, `remote_invocations` and
  `parse_errors`. `remote_invocations` counts lane invocations in a string or
  heredoc that `ssh` runs on another host; these count in no lane.
  `parse_errors` counts the calls whose text, or a script the reading read
  again, has a syntax error (once per call, however many nodes); an error
  hides only the text under it.

mcporter follows the [v0.14.1 CLI](https://github.com/openclaw/mcporter/tree/v0.14.1/src/cli)
(`cli.ts`, `command-inference.ts`, `call-arguments.ts`, `call-command.ts`).
`lanes.mcporter` counts only operations other than a call: list (including a
bare server name or a URL), auth, vault, resource, serve, daemon and the
generators. A call counts for its downstream server, never for mcporter. It
reaches a lane only through the alias map seeded from `manifests/stack.json`
(`codebase-memory` to `codebase-memory-mcp` at :280, `context-mode` to
`context-mode` at :407), and then counts in both places.

The server follows mcporter's own precedence:

- `--http-url`, `--sse` and `--stdio` win, because an ad-hoc server turns
  `--server` into a name hint;
- then `--server`/`--mcp`, or the server of a leading `server.tool(...)`
  expression;
- then the first positional, promoted to stdio when it holds a blank or starts
  as a path, and split at its first dot;
- a later `server=` or `server:` argument sets a server not yet set.

The first positional is the selector even when it holds `=`, so
`mcporter call server=linear tool=x` names a server `server=linear`, which
reads `(other)`. Ad-hoc flags without `--http-url` or `--stdio` fail upstream
and read `(unresolved)`. Tool and server auto-correction ([call-heuristic.md](https://github.com/openclaw/mcporter/blob/v0.14.1/docs/call-heuristic.md))
means the typed selector may not be the server called. A configured server
whose URL matches an HTTP selector is reused upstream, but still reads `(http)`
here.

Call states follow the call's result, since the #381 Gate A plan defines
"successful" as a tool_result that is not an error. With no result, a persisted native
status decides (a Codex item's completed, failed or declined); otherwise the
call is unfinished. `is_error` true is failed. The call is also not_executed
when the client records that it never ran, where it was observed (Claude Code
transcripts; no documented schema covers these shapes, and a count-only recount of
5,074 transcript files on 2026-09-29 gave the numbers below):

- the result row carries a `toolDenialKind` (`permission-rule` 817, `user-rejected`
  50, `cancelled` 1, `automode-unavailable` 1): every client denial, and none of
  them a failed command;
- the result content opens with `<tool_use_error>` (a validation or blocked call),
  with `The user doesn't want to proceed` (a rejection: 43 rows, 43 with a
  `toolDenialKind`, 41 with a `toolUseResult` of `User rejected tool use`)
  or with `The server-side auto mode classifier gave no verdict` (1 row: its own
  text says the check failed, not the action, and the action may be tried again);
- the transcript row's `toolUseResult`, less an `Error: ` prefix, opens with
  `PreToolUse:`, `Permission for` or `User rejected tool use`;
- an adapter marks the call declined.

A host hook's own refusal text (`This agent is isolated`, 209 rows, all Bash, all
`is_error`, none with a `toolDenialKind`) is left as a failed call: its meaning is
the hook's, not the client's. A result whose `toolUseResult.interrupted` is true
is the state `interrupted` (the command started and was cut short), not
succeeded; 0 of the Bash results of the recount carry it, so that state is
exercised only by a synthetic fixture. `is_error` false is succeeded, or unknown
when an adapter sets `native_state: "unknown"` on the result. Neither client
records a separate exit status for each command in a call, and `is_error` false
does not mean exit 0. It also covers a nonzero exit that Claude Code interprets
(`returnCodeInterpretation`, such as grep's "No matches found") and
context-mode's soft fail
([exit 1 with output](https://github.com/mksglu/context-mode/blob/v1.0.169/src/exit-classify.ts#L15-L33)).
`evidence/artifacts/pra-u1-differential-20260929/states-count.mjs` repeats the recount.

Against #381 M14 the states map as follows:

- `calls` are attempted calls;
- `not_executed` are decided and rejected, or cancelled, before execution;
- `succeeded` plus `failed` less `not_executed` are executed calls;
- `unfinished` are calls without a result;
- `interrupted` are calls that started and were cut short: executed, and neither
  succeeded nor failed, so add them to that formula when they occur.

The static reading cannot see (counts are of this host's 136,361 distinct real
commands, count-only, from `shape-counts.mjs` and the differential in
`evidence/artifacts/pra-u1-differential-20260929`):

- aliases;
- shell functions called by name or through a variable: a function body counts
  where it is defined, so a function called twice counts once and one never
  called counts;
- which side of `&&`, `||`, `if` or `case` a run reaches: every side counts;
- a program a variable names (`$QMD`, `eval '$X'`), unresolved and never a lane,
  and the text a variable stands for inside a script (`bash -c "$cmd"`);
- scripts and Makefile or npm targets that call a lane;
- unknown wrappers and launchers (`setsid`, `bwrap`, `find -exec`, `watch`,
  `parallel`): 1 real command loses a lane to `setsid` in the differential;
- an option a wrapper's table does not list, read as unresolved (`nice -5`,
  GNU `xargs -P4` and `--replace`, `exec -a`);
- a heredoc a pipe feeds to a shell (`cat <<EOF | bash`), a heredoc attached to a
  compound command, and a command string that is a substitution's output, such as
  `bash -c "$(cat <<'EOF' ... EOF)"` (5 real commands: the script reads as one
  unresolved program, so its lanes are not counted, and M4 reads it as data);
- subprocesses of non-shell code (ctx_execute in Python or JavaScript, Codex
  code-mode JavaScript);
- how often `xargs` runs its utility.

It also has these reading limits, most of them limits of the grammar
(tree-sitter-bash 0.25.1):

- an ERROR node hides what is under it: 247 of the real commands have a parse
  error (`parse_errors`), and a lane inside one is not counted. Of the 247, 31
  name a lane (a lane word anywhere in the text) and 216 do not. Of the 31, 4
  still read a lane from the valid parts of their tree; in 13 the lane word
  follows plain words (`echo qmd`: an argument), in 13 it stands where a command
  name could but the tree puts it in a comment, a heredoc body, a string or an
  assignment value, and in 1 it stands there inside an ERROR node (a comment in
  a heredoc body). No lost call is confirmed, and the upper bound is 5 of the
  6,527 commands that read a lane (decision record, "What would overturn it");
- a heredoc operator that begins a statement (`<<'EOF' cat`) is read as two
  redirections and its body as commands (0 of 15,128 real commands with a
  heredoc); several heredoc operators on one line can be an error (2 real
  commands); a heredoc ends at a body line that only begins with its delimiter
  (2 real commands); a shell heredoc whose first body line begins with a
  backslash and continues with a pipe reads its lanes correctly but can report an
  ERROR, so `parse_errors` over-counts that shape;
- two backquote substitutions in one command after one that holds an escaped
  backquote are merged by the grammar, and a word after `2>&-` is an ERROR;
- coproc and non-POSIX shells are not read.

Shapes the grammar reads wrongly, repaired here, are rare on this host and are
counted so a later host can compare (commands with the shape): a command named `!`
0, a backquoted body with an escaped backquote, `$` or backslash 0, words folded
into a redirection 500 (1 with a lane word), `time` before an assignment or `!`
12, a heredoc with no delimiter line 0 of 15,128, and words the grammar cut in
two 4,837 (37 with a lane word after the cut).

**What the parser costs.** `commandInvocations` takes time linear in the length of the text on every shape measured but two
(`scaling` in `counts.json`; `test-child-usage.mjs` checks 9 of the shapes at n = 8,000 to 64,000). The tree is read with a cursor when a node has more
than 16 children, because `node.child(i)` and `fieldNameForChild(i)` cost O(i) per call in web-tree-sitter 0.27.0: a flat run of unclosed constructs or of
comments is one wide node, and the reading had taken four times as long for twice the text (`'(('.repeat(n) + 'qmd'`, 64,003 characters: 7.4 s, now
63 ms). Two shapes are quadratic inside tree-sitter-bash's parse, which no reading changes (`parse_ms` in `scaling` is the parse alone and takes the reading's time): a
run of unclosed array assignments (`a=( `: 12.6 s at 64,000 characters) and a run of here-document operators with no delimiter (`<<`: 23.2 s at
64,000). Nothing on this host comes near: its largest command has 49,096 characters, at most 71 heredoc operators and 12 array openers, and
`commandInvocations` took at most 12.3 ms on any of the 136,361 real commands (`timing` in `counts.json`, round 1's kernel). A parse budget that marks such a text unresolved is a follow-up.

**Changed meanings.** `measurement.proxy.calls`, M3 `by_carrier.rtk_proxy` and
`m4.by_carrier` now use this command-position rule, where a prefix rule
(`^\s*rtk\s+proxy`) applied before. `cd repo && rtk proxy pytest` and
`FOO=1 rtk proxy pytest` are now rtk proxy calls, and `echo 'rtk proxy ls'`
never was one. Receipts from before this change (the #369 era) are not
directly comparable; `proxy.prefix_rule_calls` keeps the old count for that
comparison.

`m3` covers every result carrier, including `rtk proxy` (a Bash call that runs
`rtk proxy` in command position, as defined under CLI lanes), with `results`, `bytes`,
`large_results`, `large_bytes`, `large_result_share`, `large_byte_share` and
`max_bytes`. Large means strictly greater than 5,120 UTF-8 bytes. This tool's
content-byte rule measures strings directly and sums the UTF-8 bytes of `text`
fields in text blocks, with no wrapper, escaping or separator bytes. Non-text
blocks use compact JSON individually. Equal text therefore has equal size in a
Bash string and a ctx text-block array. The citation to context-mode v1.0.169's
[UTF-8 accounting](https://github.com/mksglu/context-mode/blob/v1.0.169/src/session/extract.ts#L1060-L1069)
supports UTF-8 accounting only; this rule is local and does not serialize a
hook `tool_response` object. Provider tokens remain separate.
`by_carrier` includes exception bytes; `m3`
excludes them. Group `m3_large_results_per_actor` gives nearest-rank percentiles.
`m5` includes **all** ctx results, even M3 exceptions, so a single enormous ctx
result cannot hide behind a low count share. No threshold verdict is inferred
from choosing a ctx tool. Missing calls/results and parse errors remain visible.

The three exception classes come from
[#381 preregistration](../../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json).
A successful Read followed by a successful Edit/Write of the same exact path
and cwd in that actor's observed transcript is automatic. No future row beyond
`--until` qualifies it. Other exceptions require a reviewed private JSON array
passed with `--exceptions`. Each record has `transcript_sha256` (SHA-256 of
the exact file bytes), `tool_use_id`, `exception`, and a nonempty `witness`.
Allowed classes are `read_of_subsequently_edited_file`,
`original_source_quoted_or_line_cited`, and `exact_bytes_required_by_frozen_check`.
The tool validates binding and vocabulary; the reviewer establishes semantic
truth. Sidecars, identifiers and witness text are never echoed. A mismatched
digest removes no bytes. An entry may instead carry `proxy_purpose: "acceptance"`
and a witness; this classifies M6 without granting an M3 exception.
Every supplied `exception`, `proxy_purpose` and `rtk_log_find` field must be
valid, and at least one must be present. A valid class does not mask a malformed
sibling; present null fields are invalid.
Top-level `sidecar_records.bound` and `.unbound` count records whose digest
matches at least one measured transcript or none, respectively. Each sidecar
record counts once across actors. A bound digest does not prove a call exists,
a witness is correct or an exception was applied; the exception counters show
actual removals. Skipped/out-of-window transcripts cannot bind a record.

The legacy `transcripts_found`, `transcripts_skipped_unmodified` and
`parse_errors` remain child-only, preserving the #369 comparison population.
`main_transcripts_found`, `main_transcripts_skipped_unmodified` and
`main_parse_errors` describe main files separately; `all_transcripts_found`
is their combined discovery count.

`m4` counts confirmed, statically visible remote operations, including individual `requests` in
`ctx_fetch_and_index`, shell commands in `ctx_batch_execute`, and literal
subprocess commands in JavaScript/Python ctx code. Loopback fetches are separate.
The existing `ctx_sandbox_fetch` bucket includes both context-mode sandbox
curl/wget commands and nested Codex code-mode shell curl/wget commands from the
[shared adapter](../../../tools/skill-usage/README.md). It measures sandbox
execution, not exclusive use of context-mode; both stay in the remote denominator.
Script HTTP calls, dynamic URL fetches and `gh api` are `unclassifiable` and
stay in the denominator; over 10% makes the metric `incomplete`. The regression
of one indexed fetch plus nineteen sandbox curls therefore reports 5%.
Detection follows the [#381 M4 definition](../../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json#L2921-L2930)
and extends the maintained
[context-mode v1.0.169 routing detector](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L788-L795)
and the existing shell-text parser. Before inline-HTTP matching, data heredoc
bodies and shell comments are removed and quoted argument syntax is neutralized.
Quoted Python `-c` (including combined flags ending in `c`), Node
`-e`/`--eval`/`-p`/`--print`, Deno `eval`, Bun `-e`/`--eval`, and ctx JS/Python
code remain visible to the script detector, including dynamic URLs (kept
unclassifiable). A heredoc body is source only when the simple command that
contains its `<<` operator runs stdin as source. That command is the text
between the nearest control operators around the operator, with quotes removed
and redirection words and their targets dropped, so a pipe, list or redirection
after the heredoc (`bash <<'EOF' 2>&1 | tail -n 5`, `> log.txt`, `&& ...`) does
not replace it. A `<<` inside quotes, a comment or `$(( ))` opens no heredoc.
Inside double quotes the text from `$(` to the matching `)` is a command whose
tokens are read recursively
([POSIX.1-2024 XCU 2.6.3](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_06_03)):
quotes inside it do not end the string, and a heredoc inside it resolves like
any other, so the body of the usual `git commit -m "$(cat <<'EOF' ... EOF)"` is
data whatever quotes or parentheses it holds. A quoted string that a shell runs
(`bash -c '...'`, `sh -c "..."`, `eval`, `ssh host '...'`) is analyzed as that
shell's input, with its own heredocs, quotes, comments and nested run strings.
A double-quoted one first loses the backslashes the outer shell removes before
`$`, `` ` ``, `"`, `\` and newline
([XCU 2.2.3](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_02_03)),
and a heredoc the outer shell already resolved inside its `"$( )"` is not read
twice. A raw detector match is never dropped: it moves between the confirmed
counts and `fetch_mentions_unconfirmed` and stays in the denominator of
`routed_share_lower_bound`, unless it is now confirmed as a loopback fetch,
which leaves it. A match with no raw counterpart can appear or disappear: a
nested run string (`ssh host 'bash -c "curl ..."'`) or an escaped command word
(`"$(\curl ...)"`) now adds a confirmed fetch, and a match the old reading
created in text it misread as executed is gone (the `\curl` in
`echo "$(echo " ; \curl ...")"`, which bash prints as data), so the lower bound
can rise there. Remaining limits: a backquoted span inside double quotes in data is kept as it is, so a heredoc or quoted separator in it
is not resolved (one inside a run string is read, and so is a run string right after an opening backquote); outside
quotes a backquoted span is read as plain command text, so a quote that it leaves open runs past its closing backquote;
a `case` pattern's `)` inside a double-quoted `"$( )"` ends the substitution early; analyses nested more than 32 levels
deep read as data; and text that bash rejects as incomplete (an unterminated quote, backquote or `$(`) is read to the end
of the command as that construct, so its counts can move in either direction.

**M4 stays text-based, and the lanes do not read this text.** The M4 reading (`executedText`, `executedTrace`,
`fetchKind`, `m4`) mirrors and extends the routing detector of context-mode v1.0.169, because the #381 M4 gate counts
what that detector would have routed; replacing it with a parser would change what M4 means. The CLI lanes read the
tree-sitter-bash tree of the call instead (above), so the two readings of "what runs" can differ on odd inputs. M4 also
differs from the detector on purpose where real bash and dash disagree with the detector's reading (each checked with a
stub `curl` under both shells):

- the substitutions and backquotes inside a double-quoted run string are executed by the outer shell before the inner
  shell sees the text, so a `bash -c "cat <<'EOF'` whose body holds `$(curl u)` is a confirmed fetch;
- the body of an unquoted heredoc that a shell reads is expanded by the outer shell first;
- a heredoc operator after a closed `"$( )"` in the same command keeps its reader (`FOO="$(pwd)" bash <<'EOF'` is a
  shell heredoc), and an escaped blank or metacharacter before `#` is data, not a comment;
- a run keyword that the 512-character tail window of the linear scanner loses makes the command's next unrecognized
  quote count once as unclassifiable, never as silence.

Limits that remain: `bash -c "$(cat <<'EOF' ... EOF)"` (the substitution's output is the script, so its body reads as
data, a possible fetch, and the lower bound may under-count it; 5 real commands); an unquoted arithmetic expansion with
blanks before a heredoc operator (`A=$(( 1 + 2 )) bash <<EOF`); a data heredoc with an unquoted delimiter finds only
paren-free substitutions with its regular expression (`$(curl $(date))` misses the outer `curl`); a newline read as a
blank in `bash` newline `-c "x"`; and a heredoc that a quote or `"$( )"` carries over lines has its head on an earlier
line, so its heredoc reads as a possible fetch. The text scanners read in linear time (a run of 64,000 unclosed `((`
takes under 150 ms, and its time plus 5 ms at 64,000 stays under 8 times that at 16,000: `test-child-usage.mjs`), and so does the reading of the lanes (below, "What the parser costs"). The repeated reading is cheap and
is not cached: over this host's 136,361 distinct real commands `measureTranscript` of one Bash call took 44 s in all
(mean 0.32 ms, p99 1.2 ms, at most 10.9 ms), of which `executedText` is 0.07 ms plain and 0.09 ms with inline HTTP,
`fetchKind` 0.08 ms and `commandInvocations` 0.13 ms (`evidence/artifacts/pra-u1-differential-20260929/timing.mjs`).
Python or Node read stdin with no script operand or with `-`; the retained
explicit stdin forms apply to other interpreters. A shell reads its script from
stdin unless `-c` supplies a command string or an operand names a script file:
`-s` keeps stdin, a shell's `-` equals `--`, `-o`/`+o`/`-O`/`+O` take a name,
`--rcfile`/`--init-file` take a file, and `-n` reads without executing
(POSIX sh OPTIONS/STDIN, bash(1) 5.2 OPTIONS/ARGUMENTS). `ssh` runs stdin in the
remote login shell when no remote command follows the destination, or when the
remote command itself reads stdin as source; `-n`, `-f`, `-N`, `-s`, `-W`, `-O`,
`-G`, `-V` and `-Q` never do ([OpenSSH ssh(1)](https://man.openbsd.org/ssh)).
Python `-c`/`-m`, Node `-e`/`-p`, and script-file invocations leave their stdin
as data. Each retained body is analyzed separately so its quoting or shift
syntax cannot consume later shell commands or data heredocs. The legacy
`bash_curl_wget` lane uses the same rule. Upstream strips every heredoc.
Entrypoint references:
[Python](https://docs.python.org/3.13/using/cmdline.html#interface-options),
[Node](https://nodejs.org/docs/v24.21.0/api/cli.html#-),
[POSIX sh](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/sh.html),
[Deno](https://docs.deno.com/runtime/reference/cli/eval/), and
[Bun](https://bun.sh/docs/runtime).
Shell-fed source heredocs retain executed commands. A grep pattern containing
`fetch(`, a comment, or a heredoc writing a script gives zero confirmed fetches.

`fetch_mentions_unconfirmed` separately counts raw detector matches that the
executed-text analysis did not confirm, per command/code input: `HTTP_SCRIPT`
matches anywhere in the raw text, `curl`/`wget` in command position of the raw
text (a line start, or after `;`, `&`, `|`, `(`, a backtick or `$(`, also behind
a shell keyword or wrapper as in the legacy lane), and `gh api` at a line start
or after a separator. An executed-text match confirms a raw match only when it
traces back to that raw offset; matches the analysis creates (backslash-newline
joins, unescaping, quoted strings a shell runs) confirm nothing. These are
possible fetches, including data-only mentions such as a heredoc that writes a
script, not confirmed operations.
The count and both shares are reported in `m4` and `m4.by_carrier[carrier]`,
where a Bash call's carrier is `rtk_proxy` when it runs `rtk proxy` in command
position (CLI lanes), and `bash` otherwise:

- `routed_share = ctx_fetch_and_index / remote_fetches` uses confirmed fetches.
- `routed_share_lower_bound = ctx_fetch_and_index / (remote_fetches + fetch_mentions_unconfirmed)`
  treats every possible fetch as unrouted. **The #381 M4 >= 0.9 gate must read
  `routed_share_lower_bound`.** Confirmed-only share cannot establish that gate.

For one routed fetch plus either a Python shift-syntax parser miss or a Node
comment containing an apostrophe before `fetch`, the confirmed share is 1,
the unconfirmed count is 1, and the lower bound is 0.5. A `curl` in a heredoc
whose command does not run stdin (`ssh -n host <<'EOF'`, `cat <<'EOF' > run.sh`)
gives the same values. Dropping a raw detector match from confirmed analysis, or
confirming a created match in its place, therefore cannot inflate the gate's
share. Counts are summed before shares are recomputed across actors; shares
retain the existing four-decimal reporting convention, so the gate should
compare the integer counts. Any unconfirmed mention leaves M4 status
`incomplete`; a zero denominator gives null for its respective share.

This is a lower bound against these raw detector patterns, not against every
possible runtime request. A `curl` inside a quoted string the parser does not
treat as run (`ssh -o Opt=value host 'curl ...'`, `watch 'curl ...'`), behind
`xargs`, `find -exec` or an unrecognized wrapper, or passed to a subprocess
inside interpreter code, is in neither count. Loops, dynamic code, external
scripts, aliases and nonliteral subprocess arguments still require separate
observation. The static detector cannot prove the absence of fetches in
arbitrary code.

`--rtk-check` enables M-R1/M6c in `rtk_parts` on Linux, using **a binary on PATH
self-reporting `rtk 0.50.0` that passes the five-exclusion probe**, an isolated
temporary five-exclusion configuration from
[the adopted recipe](../../../recipes/README.md#native-context-mode-and-hooks),
and native `rtk hook check --agent claude` on every simple part and whole call.
`measureTranscript`'s `rtkAgent` option names the agent instead: `claude` by default,
or `codex`, which the Codex bridge (`tools/skill-usage/skill_usage.py --lanes`) passes
since PR-A U3; any other value is refused. The option `unresolvedBash` (a non-negative integer, 0 by default) is how a caller
that could not resolve some Bash calls to shell text (the Codex bridge, for `pwsh`, `powershell`, `cmd` or a shell the
rollout does not name) reports them: each is added to `rtk_parts.unknown_calls`, never beyond the Bash calls there are,
so B8's 5 percent rule, `unknown_call_share` and the D7 status below come from the kernel alone. rtk 0.50.0 maps `codex` to
`InProcess(Host::Codex)`, which has no RTK-side permission rules, while `claude`
merges the Bash rules of the project's and the home's `.claude/settings(.local).json`,
so a Claude replay depends on the working directory and HOME and a Codex one does not
([decision.rs:196-204](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs#L196-L204),
[permissions.rs:141-175](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/permissions.rs#L141-L175)).
Each agent has its own checker and five-exclusion probe; the `claude` checker is
unchanged, and Claude output was byte-identical across the change with `--rtk-check`
([pra-u3-differential-20260929](../../../evidence/artifacts/pra-u3-differential-20260929/README.md)).
On the claude path rtk 0.50.0 prints a once-a-day "No hook installed" warning on
stderr when a Claude directory registers no rtk hook
([hook_check.rs:26-35, :88-135](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/hook_check.rs#L88-L135)).
The probe then reads that answer as an error, and the replay is `unavailable` for
that process.
No transcript command executes. Sources:
[native check](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L2940-L2952),
[lexer](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/lexer.rs#L488-L526),
[pipeline rules](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1087-L1345),
and [consumer rules](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1451-L1494).
These sources identify the reference implementation. The runtime gate does not
compare the binary hash with the [qualification receipt](../../../evidence/receipts/rtk-050-qualification-20260925.json)
and therefore does not establish that the binary is the qualified pinned build.
The adapter retains every part; upstream's analytics splitter stops at the
first pipe. Native refusals, exclusions and consumers requiring raw input are
outside eligibility. Redirection is recognized using the splitter's quote state;
a quoted `>` is data. The native check decides standalone eligibility, including
its accepted `2>/dev/null` form. `coverage` and `call_coverage` use observed
command prefixes/recorded hook rewrites, while `replayed_*` fields describe
potential routing under the fixed config. Replay never proves execution.

Parts (binding decision B8, 2026-09-29): `shellParts` (exported) reads a command
unit by unit with the frame machine of the M4 text reading (quotes, escapes,
comments, `$(( ))` and `(( ))`, `"$( )"`, subshells and backquotes, and the
redirections `>&`, `<&`, `&>` and `>|`, which are not part boundaries), and a
here-document body is data: it begins after the first newline no quote holds at
its operator's frame depth or shallower and ends at its delimiter line (any
word, quotes removed; `<<-` strips leading tabs) or at the end of the text, as
GNU bash 5.2.21 and dash read it. A top-level body belongs to no part's text.
rtk v0.50.0 rewrites no command that holds a here-document or `$((`
([`rewrite_command_precompiled`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs)),
so such a call's eligible parts, unknown before B8, now count as observed
uncovered. A call M-R1 still cannot classify (its text cannot be read, the hook's
rewrite or the replay has another number of parts, or a check fails) is one
`unknown_calls`, however many parts it has, and adds nothing to the part
counters; `unknown_call_share` is `unknown_calls / calls`. `status` is
`incomplete` (M-R1 not evaluable, never a pass) only when unknown calls exceed 5%
of the Bash calls, compared on the counts (`unknown_calls * 20 > calls`), and
`measured` otherwise, when M-R1 is evaluated on the parsed parts; an aggregate
applies that rule to its summed counts. The explicit-rtk, log/find and proxy
counters read the command's own parts, so they also count a call whose replay
cannot be classified, but never one whose text cannot be read: M-R3's zero
counter covers the parsed calls, and `unknown_calls` says how many it cannot.

M1's rtk-claude lane (binding decision B5): `eligible_call_states` gives the M14
state (the `call_states.by_server` keys) of every Bash call with at least one
eligible part, and `observed_covered_succeeded_calls` counts those with an
eligible part observed covered whose state is `succeeded` (a background run
included): the per-child-task success signal. A child-task is an opportunity
when `eligible_calls > 0`; `unavailable` and `not_measured` mean incomplete,
never zero. A child whose Bash calls are all unknown has no eligible call, so a
grader that holds unknowns unsuccessful (B2) reads its `unknown_calls` too.
M6c and M1 need `--rtk-check`.
`explicit_rtk_on_excluded_or_sensitive` is the deterministic zero counter used
by M-R3 and M6c: the five exclusions, `cd`/`export`/`source`, adopted by-design
refusals, file-target redirects and raw-input pipelines. Conditional log/find
forms contribute only to `explicit_rtk_log_find_advisory`, not this zero counter
or an additional exclusion. Syntax cannot establish complete-history intent or
path existence ([adopted conditional exceptions](../../../adoption/templates/codex.AGENTS.template.md)).
The advisory is partitioned into `log_find_permitted_parts`,
`log_find_requires_raw_parts` and `log_find_unresolved_parts`. Resolve it in the
same digest-bound sidecar with a witness and `rtk_log_find: [{"part": 1,
"disposition": "permitted"}]` (or `"requires_raw"`); `part` is the one-based
position among all command segments. M-R3/M6c's deterministic zero is not full
exception clearance while advisory parts are unresolved or require raw output.
These semantic adjudications never change the fixed-config eligible denominator.

With `rtkAgent: 'codex'`, `rtk_parts` also carries `d7`, the Codex-only view of
D7's RTK-eligible class; Claude output has no `d7` and its fields are unchanged.

- `d7` starts from the fixed-config eligible parts and drops each `git log` or `find`
  part, prefixed or not, whose `rtk_log_find` review says `requires_raw`.
- A `permitted` part stays. An unreviewed part stays too, but sets `d7.status` to
  `incomplete`, as an unknown call does.
- `covered_parts`, `coverage`, `eligible_calls`, `all_covered_calls` and
  `call_coverage` read the kept parts as the fixed-config fields read theirs.
- `wrapped_exceptions` is `explicit_rtk_on_excluded_or_sensitive` plus
  `wrapped_requires_raw_parts`, the prefixed parts a review says required raw
  output. M6c's zero counter therefore keeps its classes, which are broader than
  the [deployed exception list](../../../adoption/templates/codex.AGENTS.template.md).
- `d7.status` keeps the harder reading than `rtk_parts.status`: it is `incomplete` when any call was unknown or any
  unreviewed `log` or `find` part stays, however few, while `rtk_parts.status` tolerates B8's 5 percent. An
  amendment may relax that with a dated rationale.
- `aggregateMeasurements` sums `d7` over the measurements that carry it; its status is `measured` only when every
  actor's `d7` is, so it does not depend on how calls are split across actors, and `rtk_parts.status` of the same
  aggregate applies B8 to the summed counts.
- Which view M6c grades from, the fixed-config fields or `d7`, is the M6c owner's call.

Every `rtk proxy` part is counted in `proxy_parts` and excluded from M-R1/M6c's
eligible population, including an otherwise eligible `git diff --stat`.
`rtk_parts` and `proxy_parts` keep their prefix rule (a part that starts with
`rtk proxy`), because they model rtk's own per-part rewrite. The legacy
`rtk.model_typed` lane keeps its own prefix rule too (a command that starts with `rtk`).
This follows #381's separate acceptance/raw-proxy population. M6 still requires
acceptance/exception justification; excluding a proxy from coverage does not
justify it or remove its output from M3.
A different self-reported version, a non-Linux platform or a failed exclusion
probe reports `unavailable`; omitted replay is `not_measured`.
`rtk.not_logged_share` needs the read-only DB join.

`measurement.proxy` is M6's population: the Bash calls carried by rtk proxy
under the command-position rule of the CLI lanes, with sandbox-nested Codex
calls included as before. It reports acceptance/exception adjudications and
unclassified calls, and adds four fields:

- `invocations`: the rtk proxy invocations in those calls;
- `nested`: the sandbox-nested calls among them;
- `in_ctx_code`: ctx_execute or ctx_batch_execute calls whose shell code runs
  rtk proxy;
- `prefix_rule_calls`: the Bash calls whose command starts with `rtk proxy`,
  the rule used before, kept for comparison.

`in_ctx_code` is reported but left out of M6. That is a decision (2026-09-28)
against the Gate A plan's M6 row: its population is the Bash children, and
RTK's hook does not rewrite commands run inside ctx (the plan's rtk row), so
the one-lane RTK rule does not reach ctx code. Newly counted calls such as
`cd repo && rtk proxy pytest` arrive without a review. They read unclassified
until a digest-bound sidecar classifies them, so M6 can fall below 100%.

`usage.messages` deduplicates Claude messages and reports model, effort and
ordinary input, cache creation, cache read and output separately, with ordinals
instead of message IDs. Streamed updates use the largest counter total, following
[ccusage v20.0.24](https://github.com/ccusage/ccusage/blob/v20.0.24/rust/adapters/claude/src/daily.rs#L410-L523).
Windowed messages subtract their prior snapshot; absent counters remain null.
`usage.complete` describes accounting, not successful task completion. Failed
and interrupted attempts still contribute known usage. These numbers cannot be
added to byte measurements or tool savings estimates. The cache tier split,
the service fields and advisor iterations are under
[U2 measurement fields](#u2-measurement-fields-2026-09-29).

`hook_context` counts every inserted `hook_additional_context` by event/name,
separately from stdout claims and marker presence. Stdout alone no longer sets
the legacy SubagentStart insertion flag. `mcp_states` distinguishes attempts,
success, failure and unfinished calls; persisted Codex item status supplies state
when result bytes are absent. `sandbox_operations` counts normalized nested
code-mode operations, whose results return to code. They contribute M4/RTK/MCP
state observations but no M3/M5 context bytes or missing-context-result counts.
The outer exec return is measured once as carrier `code_mode`, and so is the output
of a code-mode `wait` call that resumes a running cell. The Codex adapter decides
which operations are nested: since PR-A U3, an item without a model call id is nested
when an own `exec` call came earlier in its turn. It also counts
`measurement.code_mode` and marks legacy-mode spans it cannot observe
([Codex side](../../../tools/skill-usage/README.md)).
`loaded_not_called` counts loaded server
references without an attempted call by that actor. These implement PR-A's
review controls; the per-call reconciliation ledger for rejected, cancelled and
unfinished calls is `--call-ledger`, with `call_states` as its published counts
(see [U2 measurement fields](#u2-measurement-fields-2026-09-29)), and none of them
is an E2E acceptance verdict. Synthetic controls run through
`python3 -m unittest tests.test_token_measurement tests.test_child_usage_suite`.

`--lanes-sweep --root <dir> [--root <dir> ...] --since <ISO> --until <ISO>` aggregates
the same lanes over every workflow and Agent-tool child transcript under explicit
roots (a Claude config's `projects/` directory, one project or one session),
counting only rows inside the window: a call counts in the window of its first row,
a ToolSearch load in the window of its result and an RTK rewrite in the window of its
hook row, so adjacent windows add up. It groups by spawn path, agent type, spawn path
within agent type (`by_spawn_and_agent_type`: spawn-path totals mix agent types, so
compare a lane between spawn paths within one agent type) and anonymous session
ordinal, keeps `blind-*`
children apart as negative controls, and prints names and counts only: no paths,
ids, labels or transcript text, and a name that is not name-shaped (a path passed as
a skill name, say) is counted as `(other)`. An actor that ran past the window end
(`children_ran_past_window_end`) has its final return outside the window:
`final_return.status` is `unobserved`, and aggregates count it in
`final_return.unobserved`. There is no default root, and a root that
is not a readable directory exits 2. The Codex counterpart is `tools/skill-usage/skill_usage.py --lanes`
in this catalog.

`codex-cross-review.mjs` drives the official Codex companion's tracked-job
lifecycle for a read-only cross-family review (lane C in the cooperation recipe).

## Local checks

From this directory:

```sh
node check-syntax.mjs review-changes.js readiness-audit.js layer-verdict-lane.js
node test-envelope.mjs            # envelope semantics plus the static contract below
node test-contract-mutations.mjs  # each listed defect must fail the suite on its named assertion
node test-child-usage.mjs         # child-usage.mjs against synthetic transcript rows
node test-usage-receipts.mjs      # the shipped receipts re-derive every figure the contract section quotes
node test-codex-envelope.mjs      # companion result-envelope parser
```

The CLI-lane reading needs the pinned tree-sitter-bash install (see CLI lanes). Without it `test-child-usage.mjs`
prints a SKIP notice for its lane checks and the Python lane tests skip; the fail-closed parser tests always run. From
the repository root, with the install:

```sh
python3 -m unittest tests.test_token_measurement tests.test_child_usage_suite tests.test_skill_usage tests.test_command_position_oracle
```

The suites use stubbed model responses or synthetic rows; they are local
integration fixtures, not native provider execution. `test-usage-receipts.mjs`
binds the shipped receipts (run ids, figures, the builder commit) to this
documentation; an adopting project keeps those receipts beside its own or drops
that one file, it is evidence rather than a generic tool. The static contract fails
a saved workflow whose worker packet drifts from the shared text, whose stage
omits `model` or `effort` or binds an effort other than `max`, whose `MODEL`
record differs from the model and effort its stages bind, whose routing differs
from the reviewed table, or whose `agent(` is written where the scanner cannot
see it; an agent definition that omits model or effort, carries an effort other
than one `effort: max` line, grants a bare `mcp__server` prefix, grants MCP tools
without `ToolSearch`, declares frontmatter `isolation`, or can edit files without the
body's refusal to edit outside an owned, coordinator-prepared checkout; a reviewer,
researcher or verifier whose tool surface differs from its reviewed list, and a
builder granted any Serena tool outside the read set; a routing
table that restates an agent's model or effort differently from its file; a role
table that maps a role to another agent;
project settings that set `CLAUDE_CODE_EFFORT_LEVEL` or cap effort below `max`;
and project instructions that do not state the `effort: 'max'` literal. Measured
native results and remaining boundaries are in
[the dated guide](../../../docs/ultracode-token-routing-20260921.md).


## Workflow contract

Applies to the coordinator and every Workflow/Agent child (project agents and `.claude/workflows/` scripts embed it):

- **One context lane per artifact class.** Known source identifiers: focused `rg`/Serena read. Indexed Markdown: scoped QMD BM25. Unfamiliar or conceptual code: SocratiCode. Prior decisions: ai-memory. Large command output: Context Mode. Choose one lane per artifact; do not chain compressors, and verify original source before editing or judging retrieved text.
- **Worker packet.** Bounded objective, explicit source paths, allowed effects (no writes except what an acceptance command named in the task itself produces, unless a worktree is owned), and a small return schema with source-cited fields. No word-count instructions; no whole-repository or transcript pastes.
- **Brief contract (2026-09-27).** Each brief states the objective and why; the owned scope and what each sibling covers, with no overlap; the starting sources and what is already settled or excluded; allowed effects and stop conditions; a bounded output schema with an evidence class per claim; a tool-call budget scaled to the task (about 3-10 calls for a fact, 10-15 per agent in a comparison); and a completion criterion. Its source is the [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): "Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries". A writer's brief also tells the writer not to make an existing test or check pass by deleting, skipping, weakening or rewriting it, or by special-casing that test's inputs, unless the brief names that test change; the writer reports a test that looks wrong, with its failing output, instead of working around it (2026-09-28; [prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#avoid-focusing-on-passing-tests-and-hardcoding)). Name only the one rule a stage needs; never paste session history or CLAUDE.md. The [SubagentStart carrier](../../../docs/decisions/2026-09-27-token-lanes-subagent-start.md) injects a token-lane block matched to each non-blind child's role (a named role with a `tools:` allowlist gets only the lanes it grants, `semantic-evidence-reviewer` gets none, other types the full block; [agent-type table](../../../docs/token-session-handbook.md#token-lanes-carried-into-subagents)), but its native acceptance covers Agent-tool children only, and the [hooks reference](https://code.claude.com/docs/en/hooks#subagentstart) lists Agent-tool spawns, resumes and in-process teammates. Saved-workflow packets and agent bodies therefore keep their lane text until a native Workflow-child run shows the block in a stage's first prompt.
- **Stable policy prefix.** Keep the shared contract text byte-identical across saved workflows (asserted by `test-envelope.mjs`) and vary only the task packet. What the provider was observed to reuse across children is the agent type's system prompt and tool definitions, per model; identical packet text alone has no measured cache effect. Reuse one agent type and model for sibling workers, and preserve deferred tool discovery and compaction. Sibling stages share one prompt-cache prefix only when model, effort, agent type, tools, output schema and working directory all match (official workflows doc, fetched 2026-09-22); keep them identical and leave `CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS` at its 5,000 ms default.
- **Task-matched models at effort max.** Set model and effort explicitly per stage: Opus for design, research, review, verification, adjudication, synthesis and any build without a written contract's tests, and Sonnet for exact extraction, inventories, running named acceptance commands (`source-scout`) and the bounded fan-out units of [the Sonnet 5.5 section](#sonnet-55-fan-out-units-and-the-default-child-model-2026-09-29) (the user's 2026-09-27 rule put Opus on design, build, research, review, verification and synthesis and Sonnet or Haiku only on pure command wrappers, mechanical extraction and probes; on 2026-09-28 the user permitted Sonnet 5.5 for large Ultracode fan-outs and suitable tasks, which that section bounds; Haiku is not routed, though a trivial probe may use it), and every saved stage and project agent at effort `max` (since 2026-09-23), with the coordinator at `max` in a terminal session started through the ecosystem `claude` launcher and at xhigh, saved per model, where the launcher is not used ([decision record](../../../docs/decisions/2026-09-29-max-default-effort.md), which says the default rests on the user's requirement and not on a measured gain here; on 2.1.281 the coordinator stayed at xhigh because a `max` session turned ultracode's orchestration off, and from 2.1.284 Ultracode stays on at any effort level). A stage with no `effort` of its own runs at its agent's frontmatter effort, else at the effort the session was given explicitly (`--effort`, `/effort` or the model picker), else at its model's saved level or default (on 2.1.281 it inherited the coordinator's xhigh), and a stage's own effort overrides the frontmatter, so every `agent()` call, ad-hoc ones included, passes `effort: 'max'`. Never set `CLAUDE_CODE_EFFORT_LEVEL`: any value overrides every child's frontmatter and stage effort (on 2.1.281 any value other than `xhigh` also turned ultracode's orchestration off; on 2.1.284 the Ultracode reminder stayed present at `max`). These effort rules were probed on Claude Code 2.1.281 on 2026-09-23 and re-probed on 2.1.284 on 2026-09-29 (`docs/decisions/2026-09-23-max-effort-default.md` and its addendum; receipt `claude-model-effort-probes-20260929`). Record requested and resolved child model and effort, and treat nulls, schema retries, stub payloads and substitutions as incomplete results. The routing table below is the default; `test-envelope.mjs` fails a saved workflow or project agent that omits model or effort or binds an effort other than `max`.
- **Dispatch by role.** Every new or ad-hoc `agent()` stage names the `agentType` of its role in [the role table](#dispatch-by-role-2026-09-26); a stage with `general-purpose` or no `agentType` carries a `// dispatch: <reason>` comment beside the call. The saved scripts keep their reviewed routing, since they are vendored byte-identical (the `readiness-audit` verify stage runs as the default child).
- **Usage accounting.** Count each client separately: native `/usage`, `claude agents`/`/workflows` journals, `ccusage` offline reports and `ecosystem-token-report refresh`. Never sum RTK, Context Mode, jCodeMunch, Headroom and provider counters, and never state a savings percentage from a fixture. After a Workflow run, `node .claude/workflows/child-usage.mjs <Transcript dir printed by the Workflow tool>` (or `--latest`) returns each child's requested and resolved model, effort, provider-returned usage and first-prompt size, and exits 1 when a child is null, substituted, named no model or ran an older model than its alias documents (the client resolves a family alias to the lead's exact model when the lead belongs to that family, so a `sonnet` child under a lead pinned to an older Sonnet is flagged too; keep the lead on the alias). An attempt that returned nothing and that the runtime re-ran under the same journal key (a Workflow pauses at a usage limit and re-runs its waiting agents after the reset) is listed under `superseded_attempts`, not as a lost child, and its usage still counts in `by_resolved_model`. Usage such an attempt holds that cannot be counted (an assistant message without provider usage or without a resolved model, or no transcript at all) is its `usage_issues`, and it leaves the run incomplete. Advisor usage lies outside these totals (2026-09-28): subagents inherit the configured advisor ([advisor](https://code.claude.com/docs/en/advisor)), the API reports each advisor call as a `usage.iterations[]` entry of type `advisor_message` and keeps top-level usage executor-only ([advisor tool usage](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool#usage-and-billing)), and a run-mode child's `usage` and `by_resolved_model` read only the top-level counters (since 2026-09-29 `lanes.measurement.usage` also reports the advisor iterations, as `advisor_iterations` and `totals_including_advisor`). A count-only scan of one host found 1,018 advisor iterations in 660 of 2,912 subagent transcripts ([receipt](../../../evidence/receipts/claude-advisor-usage-scan-20260928.json)). Take complete session usage from `/usage`, which includes advisor usage, and hold the advisor state equal across comparison arms with `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` or `/advisor off`.
- **Cross-family review.** Explicit `/codex:review` or `/codex:adversarial-review --background` at integration points (see `recipes/claude-codex-cooperation-lanes.md`); findings are verified against source, not accepted by agreement.
- **Opt-in and limits.** The `ultracode` keyword starts a workflow only from a prompt typed in the session; it is inert from `-p`, an unstamped SDK prompt, a scheduled task or a relayed comment, so a headless run invokes a saved workflow by name under a settings source whose permission mode or allow rule (`Workflow` or `Workflow(<name>)`) covers the tool. Scripts take no mid-run user input, no `import()` and no `Date.now()`, `Math.random()` or argless `new Date()` (pass timestamps through `args`; run a stage that needs sign-off as its own workflow); one `parallel()`/`pipeline()` call takes at most 4,096 items and a run at most 1,000 agents.
- **Failure and replay.** On resume a failed or stopped agent runs again together with every agent started after it, completed ones included, and a run with nothing cached has nothing to resume; native failure, cancel and recovery remain documented but unobserved (open gate in `docs/native-ultracode-20260921.md`).
- **Agent allowlists and skill preloads.** Block a specific command with a `permissions.deny` Bash rule, never with a specifier inside an agent's `disallowedTools`, which removes the whole tool. A child `skills:` entry preloads the full skill text into its first prompt. Targeted builder and security-reviewer preloads are documented configurations with their own first-prompt sizes unmeasured and preregistered alongside the researcher/verifier rows in the [decision record](../../../docs/decisions/2026-09-26-stack-agents-role-dispatch.md). The [listing-state addendum](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-listing-state-and-agent-preload) probed preload viability on Claude Code 2.1.283 for a pinned, table-listed skill; the builder's plugin-scoped `context-mode:context-mode` preload instead relies on its installed `SKILL.md` carrying no invocation-disabling frontmatter. Neither is a repeat native probe of these specific configurations. The separate Read/Glob/Grep reviewer probe of 2026-09-22 measured 15,059 tokens with one skill; that figure does not qualify these new configurations.
- **Version gates.** A rule that depends on a client version names the version observed when it was recorded. This section was checked against `claude --version` 2.1.278 on 2026-09-22; the official docs fetched that day gate the settings-file size guideline at 2.1.219, `/workflow-authoring` at 2.1.248 and the concurrency setting at 2.1.269. The excerpts those fetches returned (including the stagger default above) are retained in `evidence/artifacts/harness-rules-convergence-20260922/official-doc-excerpts.json`.

### Dispatch by role (2026-09-26)

Name the role's `agentType` on each stage beside an explicit `model` and `effort: 'max'`; the stage's `model` overrides the agent's own default (the official workflows doc counts it as the per-invocation model). Each agent's body carries its role's lanes, so the packet carries only the task. Semantic (TypeSafe) reviews and layer-verdict lane stages keep the agents the routing table below names; a stage no role fits runs as the default child with a `// dispatch: <reason>` comment beside the call.

| Role | `agentType` | Model, effort | Use |
| --- | --- | --- | --- |
| scout | `source-scout` | Sonnet, max | exact extraction, inventories and the acceptance commands a task names |
| researcher | `stack-researcher` | Opus, max | web, documentation, repository and catalog research; pages through `ctx_fetch_and_index`; findings returned inline |
| builder | `isolated-builder` | Opus, max | a bounded implementation in the owned checkout the coordinator prepared at the exact base and named in the brief; its handoff runs the three registry test methods `tests.test_osv_lockfile_coverage.LockfileInventoryTests.test_every_tracked_lockfile_and_manifest_is_listed`, `tests.test_blind_checkout.RepositoryClassificationTests.test_every_blueprint_value_under_a_label_key_is_classified` and `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests.test_all_published_workflows_are_listed_and_covered` with zizmor on `PATH`, where a skip is not a pass (the same three that `scripts/git-hooks/pre-push` runs on the tip commit of each pushed ref) |
| reviewer | `evidence-reviewer` | Opus, max | independent review from source and recorded evidence, running no commands |
| security | `security-reviewer` | Opus, max | adversarial security review from original source, including agent tool grants; security-best-practices preloaded; never fixes or runs acceptance commands |
| verifier | `stack-verifier` | Opus, max | re-running named commands and deciding claims from their output and source; never fixes |
| adjudicator | `blind-adjudicator` | Opus, max | one anonymous two-return layer-verdict disagreement |

The researcher, verifier and security rows, and the builder's new preload, are unmeasured: their first-prompt size, lane use, correctness and billed cost against `general-purpose` stages are preregistered, with the result that would overturn this table, in [the decision record](../../../docs/decisions/2026-09-26-stack-agents-role-dispatch.md).

### Sonnet 5.5 fan-out units and the default child model (2026-09-29)

Since Claude Code 2.1.284 the `sonnet` alias is Sonnet 5.5 on the Anthropic API and the `opus` alias is Opus 5.5 ([decision record](../../../docs/decisions/2026-09-29-sonnet-5-5-dispatch.md); native probes: receipt `claude-model-effort-probes-20260929`). An older client routes `sonnet` to Sonnet 5, and `child-usage.mjs` accepts that as its documented resolution, so check `claude --version` for 2.1.284 or later before routing a stage to `sonnet`. The role table keeps each role's default model. A stage may override it with `model: 'sonnet'` at effort `max`, only for a fan-out unit whose output an executable oracle or a later Opus stage checks:

- shell, test, build and lint runs, and the acceptance commands a task names;
- exact extraction, inventories, counts and log analysis, each finding with a file:line locator that the consumer re-reads;
- migrations, refactors and scaffolds from a written contract in an owned checkout, gated by the contract's tests and followed by an Opus review;
- first-pass breadth research whose claims an Opus stage then checks (the [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) is an Opus lead over Sonnet subagents).

Design, research beyond first-pass breadth, adversarial review, verification of claims against source, security review, adjudication, synthesis and any build without a written contract's tests stay `opus` at `max`: Anthropic's [Sonnet 5.5 system card](https://www.anthropic.com/claude-sonnet-5-5-system-card) puts Opus 5.5 ahead on the honesty and reckless-tool-use audits and as the less self-preferring grader (sections 6.2.2, 6.2.3 and 6.3.1).

- **Evidence for the split.** Terminal-Bench 4.0 gives Sonnet 5.5 70.6% and Opus 5.5 66.4% in Anthropic's runs (Claude Code `--bare`, 5 trials per task; card section 8.5), 63.6% against 59.6% at Artificial Analysis (mini-swe-agent), and 53.03% against 61.62% at Vals AI (Terminus 2). The three evaluations disagree, and they differ in harness, operator, effort pairing and fallback share (Anthropic's own 4.2-point gap is inside its ±2.5 and ±2.6 standard errors; Vals' 8.6-point Opus lead is outside its ±1.0 and ±1.5), so the split rests on the oracle and the checks above, not on a Terminal-Bench score.
- **Bulk only.** Anthropic's [cost guide](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence) found that, in its measured orchestrator and worker configurations, a second model paid off only to cap the cost tail on routine work and for input larger than one context; on work one model could do alone, that model at lower effort was cheaper every time. A fan-out is for bulk or over-context work, and the first run of a new fan-out class sweeps effort before adding the second model.
- **Every stage names its model.** A stage that names none runs its definition's model, else `CLAUDE_CODE_SUBAGENT_MODEL`, else the lead's model (Sonnet 5.5 under a Sonnet 5.5 lead; [documented order](https://code.claude.com/docs/en/env-vars)). The template and the portable settings file set `CLAUDE_CODE_SUBAGENT_MODEL=opus`, the default for a subagent, teammate or workflow agent that no per-call model or definition names, and `child-usage.mjs` exits 1 for a child whose stage named no model or that ran an older model than its alias documents. `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` stays unset: with it Claude Code ignores every definition's and stage's model, which would defeat the Sonnet overrides above ([sub-agents](https://code.claude.com/docs/en/sub-agents#run-every-subagent-on-one-model)).
- **Effort.** The `ultracode` setting does not set effort on 2.1.284 (`--effort ultracode` still starts at xhigh; [model-config](https://code.claude.com/docs/en/model-config#adjust-effort-level)): a Sonnet 5.5 session with no saved level ran at medium. In headless probes with no explicit effort a child on another model ran at that model's saved level or default; under an explicit effort children inherited it: in the interactive session, whose effort a model picker had set to `max`, every child that named no effort ran at `max`, an Opus 5.5 child included, and so did two project agents whose definitions declare `effort: max`; in a headless `--effort max` session an unnamed subagent and a stage that named none ran at `max` while a project agent whose frontmatter says `medium` stayed at `medium` ([max-default receipt](../../../evidence/receipts/claude-max-default-effort-20260929.json), cases F5 to F7). Every stage names `effort: 'max'`. A terminal session started through the ecosystem `claude` launcher starts at `max` (`claude --effort xhigh` opts out); the settings pin each current model at xhigh for sessions that skip the launcher and for headless runs that pass no `--effort`. That default rests on the user's requirement, not on a measured gain here ([decision record](../../../docs/decisions/2026-09-29-max-default-effort.md)): the card reports Sonnet 5.5 lower at `max` than at xhigh on its FrontierCode coding benchmark (46.2% against 52.1% on Main; section 8.4), which is why the first run of a coding class sweeps effort.
- **Teammates.** Name the model at spawn: `sonnet` for an execution or exploration teammate, `opus` for a judgment teammate. An unnamed teammate takes its definition's model, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the lead's.
- **Siblings.** Keep the workers of one `parallel()` or `pipeline()` group on one model, effort, agent type, tool set, output schema and working directory so they share one prompt-cache prefix ([workflows](https://code.claude.com/docs/en/workflows#prompt-caching-in-a-fan-out)), and put the Opus verifiers in the next stage.

### Role routing and child prompt size (2026-09-21)

Spawning a child has a fixed prompt cost before any work. Run ids, the extraction command and saved `child-usage.mjs` outputs are in `docs/ultracode-token-routing-20260921.md`. Measured on this host with one identical one-command task, Sonnet 5/low, provider-returned first-request tokens (`input + cache_read + cache_creation`); these are exact artifact comparisons for that task, not a lifetime or per-task savings rate:

| Child | First prompt | Why |
| --- | --- | --- |
| default workflow subagent (no `agentType`) | 42,396 | all built-in tools, skills listing, CLAUDE.md hierarchy, deferred MCP names |
| `evidence-reviewer` with bare `mcp__server` grants (previous) | 42,220 | a server-prefix grant without `ToolSearch` loads every schema of four servers eagerly, write tools included |
| named MCP tools, no `ToolSearch` (probe) | 21,565 | ten schemas still eager |
| named MCP tools plus `ToolSearch` (probe of the shape the reviewer and builder adopted) | 12,164 | ten named grants and a one-sentence body; lanes stay deferred; ToolSearch returned only the granted tools and nothing for `replace_content`/`ctx_purge` |
| `source-scout` (four built-ins, `omitClaudeMd`) | 8,048 | role rules live in the agent body |

In real runs the adopted definitions, with their full grants and bodies plus the task packet, started at 17,535 (`evidence-reviewer`, packet including the inventory) and 17,864 (`isolated-builder`, before its new preload). Sibling children launched together each wrote their own cache (first-request cache read 0); a repeat spawn of the same agent type about two minutes later read 34,591 of 42,091 tokens from cache. Children use the 5-minute cache class, so `subagentPromptCacheTtl` stays at its five-minute default: the one-hour class only pays for a child that idles more than five minutes between requests.

Effort column since 2026-09-23: every child role runs at `max` with its task-matched model, and the coordinator runs at `max` in a terminal session started through the ecosystem launcher and at xhigh, saved per model, elsewhere (2026-09-29). The prompt-size figures above predate this change.

| Task class | Agent / stage | Model, effort | Lanes |
| --- | --- | --- | --- |
| Requirements, decomposition, integration, hard judgments | coordinator | Opus 5.5, max from the launcher, else saved xhigh, under `ultracode` (on 2.1.281 a `max` session turned its orchestration off; a Sonnet 5.5 coordinator, the user's choice, sends each judgment to an `opus` stage); Fable 5.1 as an explicit escalation | all, one per artifact |
| Exact extraction, inventory, running acceptance commands | `source-scout` | Sonnet, max | `rg`/focused Read, `qmd search`, `jq` pipelines, RTK-filtered Bash with `rtk proxy` recovery; acceptance commands run raw through `rtk proxy` where `rtk` is installed. Bash is granted, so its read-only rule is an instruction, not a sandbox |
| Web, documentation, repository and catalog research | `stack-researcher` | Opus, max | WebSearch, then `ctx_fetch_and_index` and `ctx_search`, with no WebFetch (the lane a default child used when told to on 2026-09-21: 1 fetch, 5 searches, 8 requests); Context Mode for large output; `rg`/Read plus Serena and jCodeMunch reads for code; `qmd query`/`get`; ai-memory query; all deferred and returned inline. Bash is granted, so its read-only rule is an instruction |
| Implementation from a clear contract | `isolated-builder` (coordinator-created worktree) | Opus, max | Edit and Write in the owned checkout the brief names, after checking that it is not the coordinator's own checkout and sits at the stated base (no frontmatter `isolation` since 2026-09-27); named Serena read tools, SocratiCode, jCodeMunch, Context Mode, ai-memory, all deferred. Serena binds the parent session's project at startup, so its symbol-edit tools, removed on 2026-09-26, would edit that checkout rather than the worktree. Preloads `context-mode:context-mode` (its `verification-before-completion` preload was removed on 2026-09-28); first-prompt size is unmeasured for this configuration |
| Independent review from source and recorded evidence | `evidence-reviewer` | Opus, max | named Serena, SocratiCode, jCodeMunch and ai-memory read tools plus Context Mode `ctx_execute*`, all deferred. No Bash, Edit, Write or symbol-edit tool; `ctx_execute*` can still run commands in the working tree, so file safety there is an instruction, not a sandbox |
| Adversarial security review of a supplied diff or artifact | `security-reviewer` | Opus, max | Same named read tools as evidence-reviewer behind ToolSearch; `security-best-practices` preloaded. No Bash, Edit, Write, WebFetch or Skill; Context Mode and jCodeMunch read-only use remains an instruction. None yet: first-prompt size, lane use, correctness and cost are preregistered in the [decision record](../../../docs/decisions/2026-09-26-stack-agents-role-dispatch.md) |
| Review of supplied semantic (TypeSafe) judgments against original source | `semantic-evidence-reviewer` | Opus, max | Read, Glob, Grep and the `typesafe-ai` skill preloaded (first prompt 15,059 in the 2026-09-22 probe); no MCP grants, Bash or writes |
| Layer-verdict lane stages: propose, refute and re-check one stripped packet from its repository root | `blind-lane-reviewer` | Opus, max | Read, Glob and Grep; no preloaded skill and no project instructions (`omitClaudeMd`); used by `layer-verdict-lane` |
| Layer-verdict adjudication: judge, or refute a judgment on, one anonymous two-return disagreement input | `blind-adjudicator` | Opus, max | Read, Glob and Grep; no preloaded skill and no project instructions (`omitClaudeMd`); used by the catalog's adjudication lane |
| Verification that must re-run commands | `stack-verifier` | Opus, max | acceptance commands raw through `rtk proxy`; Context Mode `ctx_execute*`, `ctx_batch_execute` and `ctx_search` to count in code; no project instructions (`omitClaudeMd`), Edit or Write, and it never fixes. Bash is granted, so its read-only rule is an instruction |
| A stage no role fits, with its reason beside the call; the vendored `readiness-audit` verify stage | default workflow subagent | Opus, max | full tools, skills listing and project instructions; pays the 42k prompt deliberately |
| Cross-family review | `/codex:review` lanes | Codex | see `recipes/claude-codex-cooperation-lanes.md`; usage is not in the Claude journal |

Haiku is not routed. In the same-packet trial the Opus verifier scored the Sonnet/medium inventory 14/14 lane rows and the Haiku inventory 9/14, including a quote attributed to a file that does not contain it; Haiku also ignored the requested effort and used more requests (22 vs 17). Overturn this with a repeat trial in which Haiku returns no unanchored citation on two distinct extraction packets. RTK and ai-memory hooks were observed firing inside workflow children (`rtk hook claude` rewrote child Bash calls). Context Mode's PreToolUse and PostToolUse hooks run for child tool calls too (dated 2026-09-26, Claude Code 2.1.283 with Context Mode 1.0.169 at `6f0cc684`): Claude Code runs plugin hooks inside subagents and adds `agent_id` and `agent_type` to their input ([hooks](https://code.claude.com/docs/en/hooks)). Context Mode then skips, by design, its redirects to `ctx_*` tools (WebFetch, curl or wget, inline HTTP, gradle, mvn and sbt), because a subagent may not have those tools (`hooks/pretooluse.mjs:167-171`, `hooks/core/routing.mjs:28-29, 666-668`; upstream #794 and #834); its guidance and the `ctx_*` security checks still apply (the Bash, Grep and smaller-Read tips once per session, the large-Read tip on every Read over 50,000 bytes; `hooks/core/routing.mjs:121-144, 839-871`). Its routing block is injected only at SessionStart and into an Agent tool call's prompt (`hooks/sessionstart.mjs:49, 166`; `hooks/core/routing.mjs:894-918`), so a Workflow child does not receive it and its Context Mode use depends on the packet and agent text. Child events land in the parent's session store ([session notes](../../../docs/token-session-handbook.md#context-mode-executor-and-session-store)). Repomix, guarded Headroom and TOON stay coordinator-side: workers read focused ranges instead of packed sources, Context Mode already owns large worker output (no chained compressors), and a Workflow script has no filesystem or CLI access to run a TOON conversion on the packets it passes.

## SOTA references (2026-09-27 review)

The [2026-09-27 review](../../../docs/decisions/2026-09-28-community-sweep.md) of 22
pinned community Claude Code repositories against the primary Claude Code, platform
and CHANGELOG sources is the reference set behind this README's 2026-09-28 changes:
the background-wait ceiling in Adopt step 3, the test-integrity clause of the brief
contract and the advisor note under usage accounting. Its
[community pins](../../../docs/decisions/2026-09-28-community-sweep.md#community-pins)
carry full commit SHAs, where stars are discovery metadata and not evidence, and its
[primary sources](../../../docs/decisions/2026-09-28-community-sweep.md#primary-sources)
carry read dates. Its keep-but-compare rows name the comparison that would change a
rule here, such as the effort arms for the child roles.
