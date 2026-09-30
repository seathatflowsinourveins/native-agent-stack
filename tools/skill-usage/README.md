# Skill invoke-rate report

Join `adoption/skills/manifest.json` with real, per-host measurements of whether each pinned
skill is actually invoked, on each client that lists it. It is the measurement half of the 30-day
skills trial (`trial.measurement` in the manifest); the trial's own `prune_rule` decides what a
host does with the numbers, this tool only produces them.

## Why per-skill invoke-rate needs its own tool

- **Not OTel.** Claude Code's OpenTelemetry export redacts a tool's `skill.name` attribute to the
  literal string `custom_skill` unless `OTEL_LOG_TOOL_DETAILS=1` — and that flag also exports full
  commands and tool inputs, i.e. transcript content, to reach the one field this report needs.
  Turning on OTel to get a skill name would mean exporting far more than a name and a count.
- **Not a custom hook.** A `PreToolUse`/`PostToolUse` hook could watch tool calls, but it would
  need to run continuously, write its own log outside the checkout, and reimplement exactly what
  native `/skill-doctor` already aggregates for Claude (uses, last-used, context cost). It also
  could not see anything on the Codex side: Codex has no skill-invocation event at all, so a hook
  only ever answers half the question this tool answers.
- **Not agentsview or ccusage.** Both report cost and token usage per session/model; neither
  exposes "which skill fired" as a dimension. They answer "how much did this session cost", not
  "was this skill used".
- **native `/skill-doctor`** is therefore the only source for Claude's side, and Codex's own
  `rollout-*.jsonl` transcripts (there is no equivalent event) are the only source for its side.
  Both are read here, jointly, so a trial verdict has one report instead of two disconnected ones.

## Privacy boundary

Same rule as `tools/token-report/README.md`: **no implicit search of transcripts.** `--codex-root`
is repeatable and has no default search path; Codex is reported as `"not-measured"` until at least
one root is explicitly given. The report itself contains only skill names and counts:

- no file paths (roots are counted as `roots_count`, files as `files_scanned`; neither path nor
  filename is ever written to the report);
- no session, thread or rollout ids;
- no prompt or transcript text. The Codex scan reads only two narrow signals — whether a
  tool/function call's command or arguments contain a path ending in `/<name>/SKILL.md`, and
  whether a user message contains the token `$<name>` — and keeps only the boolean/count result,
  never the matched string, the surrounding message, or any other field of the line.
- the Claude side is limited to native `/skill-doctor`'s own table (skill, source, context tokens,
  7-day tokens, uses, last used); it is never asked to read `~/.claude/skills` or any transcript.

## Commands

Claude side — capture the table once (no cost, no tool calls: it is a synthetic local command),
review it, then point the report at the file:

```sh
claude -p "/skill-doctor" --output-format json > /path/outside/checkout/skill-doctor.json
python3 tools/skill-usage/skill_usage.py \
  --claude-skill-doctor /path/outside/checkout/skill-doctor.json \
  --codex-root ~/.codex/sessions \
  --out /path/outside/checkout/skill-invoke-rate.json
```

Or let the tool run it directly. It runs exactly `claude -p "/skill-doctor" --output-format json`
with stdin from `/dev/null` and a timeout, and refuses to use the result unless the run reports
`total_cost_usd == 0` and `num_turns == 0` (both are recorded either way) — the documented shape of
that native command; anything else means the captured text did not come from that code path:

```sh
python3 tools/skill-usage/skill_usage.py --run-skill-doctor --codex-root ~/.codex/sessions
```

`--claude-skill-doctor FILE` also accepts a plain-text capture (the table as printed, no
`--output-format json`) — useful when the table was pasted rather than captured as JSON.

Common options: `--manifest PATH` (default `adoption/skills/manifest.json`), `--window N`
(repeatable; default 7 and 30 — the manifest's own `trial.window_days` is always included even if
omitted, since the prune rule is defined at that window), `--now ISO8601` (fixes the reference
time; mainly for tests), `--home DIR` (resolves the skills lock's `installedAt`, still XDG-aware:
`$XDG_STATE_HOME/skills/.skill-lock.json` wins when that variable is set to any non-empty value, as
in the skills 1.7.0 CLI, which joins both paths with Node's `path.join`), and `--json` (print
the full JSON report instead of the text table).

Nothing is written to disk unless `--out PATH` is given, and `--out` **inside this checkout is
refused** — state for this report belongs next to your other private, ungitted state, per
`docs/secret-storage.md` / `adoption/lifecycle.md`, not in the working tree.

## Recording a host receipt

The invoke-rate report is evidence for a trial review, not itself a receipt. To fold a run into
this host's evidence trail, record it with the existing tool:

```sh
python3 scripts/host_receipts.py record \
  --host-id <host>-<YYYYMMDD> --platform-id <platform> --component-id skills-trial \
  --stage use --evidence-class local_integration \
  --cmd 'python3 tools/skill-usage/skill_usage.py --run-skill-doctor --codex-root ~/.codex/sessions --json'
```

`--evidence-class local_integration` is correct here: this tool measures our own manifest against
native output, it is not an unchanged upstream test and not a synthetic fixture (those stay under
`tests/fixtures/skill_usage/`, which is never cited as host evidence).

## Reading the numbers correctly

- **Claude's `uses` is not windowed.** Only `/skill-doctor`'s `7d tokens` column carries an
  explicit window; `uses` does not say over what period. The same lifetime `uses` value is
  therefore reused for every `--window`'s zero-usage check. This is a documented gap, not a
  measured per-window value — the report's own `limits` field says so, and `claude.context_tokens`
  (`"-"` in the table = not in the current listing) is the one Claude number that *is* about
  system-prompt cost, never invocation count.
- **A window that was never scanned reads as `null`, never `0`.** If `--window` omits the
  manifest's own `trial.window_days`, the report still adds it internally (see above) and scans
  Codex at that window; but a per-skill Codex count is only ever a real zero when its window was
  actually scanned. This mirrors `tools/token-report/README.md`'s "an absent ledger is not read as
  a measured zero" rule. The same rule applies on the Claude side: a manifest skill with no row in
  the captured `/skill-doctor` table gets `claude.uses: null` and is dropped from
  `evaluated_clients`, even when it is listed (`claude_listing != "off"`) — a listed skill can
  still be missing from one particular capture (e.g. it scrolled out of a truncated table), and
  that absence is never reported as an observed zero.
- **`prune_candidates` requires an actual evaluated client.** The rule is: installed age
  `>= trial.window_days`, and zero uses in that window on *every measured client where the skill
  is enabled/listed*. A skill with `claude_listing: "off"` and `codex_enabled: false` has no
  evaluated client at all and is never a candidate — that is not the same claim as "unused". A
  skill whose age is unknown (missing from the skills-CLI lock) is likewise never a candidate,
  regardless of how old the trial itself is.
- **A disabled client's raw counts still appear.** If `codex_enabled` is `false` for a skill, its
  Codex counts are still scanned and reported (transparency), they are simply excluded from
  `evaluated_clients` and so cannot block or force a prune decision on their own.
- **Kept skills are never demoted through this report.** Per the manifest's own
  `trial.prune_rule`, a `status: "kept"` verdict winner that meets the same age/zero-usage
  condition lands in `verdict_recheck` with `"flag": "verdict re-record required"`, not in
  `prune_candidates`. Only a `status: "trial"` skill can appear in `prune_candidates`.
- **The measured listing cost is its own counter.** `claude.context_tokens` is what `/skill-doctor`
  attributes to a skill's one-line listing in the system prompt. It is evidence for *this* trial
  (is the skill worth its permanent listing cost) and must never be summed into
  `tools/token-report`'s RTK/Headroom/Context-Mode counters — those measure retrieval and context
  savings on a completely different basis, and the codebase's rule against summing overlapping
  counters applies here too.
- **Codex `counts` stay the trial's measurement; two parts of them are broken out beside them.**
  `counts` holds every rollout record of every session, as the skills trial pins it, and every flag
  (`zero_on_evaluated_clients`, `prune_eligible`) reads it. Two disjoint parts of it are reported per
  skill and window, never subtracted from it:
  - `of_which_user_config_ignored`: the own records of sessions that did not load the user config.
    A session launched with `--ignore-user-config` (the landscape sweep and blind lanes) lists every
    installed skill, the trial's `codex_enabled: false` ones included, so it is a different listing
    state. The report detects it from the session's own skill catalog as of `--now` (see
    [Codex lane report](#codex-lane-report---lanes)) and counts such sessions in
    `codex.sessions_user_config_ignored`.
  - `of_which_copied_from_parent`: the records a spawned sub-agent's rollout copied from its parent
    (ordinals below `subagent_history_start_ordinal`); the parent's own rollout holds them too.

  `counts` minus both parts is the own records of every other session. Whether the trial should
  compare only within one listing state is the trial owner's rule to record; until then no flag
  reads the parts.
- **Codex counts are two distinct signals, never merged.** `skill_md_reads` (a tool/function call
  whose command or arguments named that skill's `SKILL.md`) and `name_mentions` (a user message
  containing `$<name>`) are reported side by side; a prune decision at the trial window treats
  either being nonzero as "used".

## Codex lane report (`--lanes`)

`--lanes` reports which lanes Codex sessions actually used, the Codex counterpart of
`examples/claude-native/workflows/child-usage.mjs --lanes-sweep` (which reads Claude child
transcripts). It reads the same explicitly passed rollout roots, never a default path:

```sh
python3 tools/skill-usage/skill_usage.py --lanes --codex-root ~/.codex/sessions \
  --since 2026-09-25T17:18:00Z --until 2026-09-26T15:05:00Z --json
```

Per rollout session it counts, from records inside `[--since, --until)`: MCP calls and failures
per server (`item_completed` `McpToolCall`), shell commands (`CommandExecution`) and how many start
with `rtk`, fetch routing (hosted `web.search` page opens and searches, Context Mode
`ctx_fetch_and_index`, `curl`/`wget` in command position of the text a shell runs, with
loopback-only calls apart), file changes, function calls such as `spawn_agent` (one tool call
when an item shares its `call_id`), SKILL.md reads (the same call-payload signal as the
invoke-rate report) and the first prompt's input tokens (the first `token_count` with usage). It
also records whether a developer message carries the injected block's marker (default
`<context_window_protection>`, the opening tag of Context Mode's routing block; `--marker` for
another). A spawned sub-agent's rollout begins with records copied from its parent (ordinals below
`subagent_history_start_ordinal`); they count toward its marker and catalog, never as its calls.
`marker` keeps that meaning. `marker_inherited` and `marker_injected` split it by content item: the marker
in a record copied from the parent, or in the session's own. `marker_injected_kinds` counts the injected items
by content kind. Codex records a hook's `additionalContext` as a developer message whose
`internal_chat_message_metadata_passthrough.content_item_kinds` is `hooks.additional_context`, for a root's
SessionStart and a spawned sub-agent's SubagentStart alike
([hook_additional_context.rs:15-22](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/context/hook_additional_context.rs#L15-L22),
[hook_runtime.rs:128-154](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/hook_runtime.rs#L128-L154)
and [:848-872](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/hook_runtime.rs#L848-L872)).
A kinds list that does not align with the content items, or a kind that is not a string, reads `(none)`.
Groups add `marker_inherited_sessions`, `marker_injected_sessions`, `marker_inherited_only_sessions` and
`marker_injected_by_kind` (content items). `measurement.codex_hook_context` counts developer content items of
that kind: `inserted` and `with_marker` for the session's own, in the window of their record, and `inherited`
and `inherited_with_marker` for copied ones, once, in the window of the child's first own record, so adjacent
windows add up. The kernel's `measurement.hook_context` counts Claude `hook_additional_context` attachments
only, so it reads zero for Codex.
A tool call counts once per id (a `function_call`'s `call_id` is its item's id), in the window of
its first record, as `child-usage.mjs` counts `tool_use` ids: a call requested before `--since`
and completed inside is not counted again, so adjacent windows add up. Its shell, MCP and fetch
lanes come from its `item_completed` event and count in that event's window.

Shell, MCP and fetch counts come from `item_completed` events, an event whose persistence depends
on the rollout's history mode (`codex-rs/rollout/src/policy.rs`); `response_item` records are
persisted in every mode. The report therefore gives `sessions_by_history_mode`
(`session_meta.history_mode`) and `sessions_with_tool_calls_but_no_item_events`, the sessions
whose own records hold model tool calls but no such event: their shell, MCP and fetch lanes read
as zero. The legacy `ctx_fetch_and_index_share` compares three lanes only (hosted page opens,
`ctx_fetch_and_index` and remote `curl`/`wget`); a fetch run inside a Context Mode sandbox
(`ctx_execute` code), a `gh api` call and `fetch()` or an HTTP library in a script are in no lane.
`curl`/`wget` also counts behind the shell keywords `do`, `then`, `else`, `elif`, `if`, `while`,
`until`, `!` and `{` and behind `rtk`, `sudo`, `env`, `command`, `exec`, `time`, `nice`, `nohup`
or `timeout N`. Escaped characters and comments are data, and `$(...)` or backticks inside double
quotes or in the body of a heredoc with an unquoted delimiter still run (bash(1) QUOTING, COMMENTS
and Here Documents). This legacy counter keeps its own Python rule (`executed_text`, `fetch_kind`),
which predates the kernel's reading of heredocs inside `"$( )"` and of strings a shell runs, so it
disagrees with `measurement.m4` and with the Claude lane's `bash_curl_wget` in both directions.
Observed with the two readings side by side: the `curl` line in the heredoc of `bash -c 'cat <<EOF >
x.sh ...'` and the inner text of `bash -c "echo \"a; curl u\""` count here as a fetch and there as
data, while `echo "$(echo "a" && curl u)"` (a `"$( )"` whose inner quotes the Python scan cannot
follow) counts there as a fetch and here as none. A plain `curl` and `bash <<'EOF'` with a `curl`
line agree. The gate and every PR-A field read the kernel; the legacy counter is a historical
comparison field.

PR-A adds `actors[].measurement` and group `measurement` fields. They reuse
the existing [child-usage.mjs measurement kernel](../../examples/claude-native/workflows/README.md#pr-a-measurement-fields-2026-09-27)
through Node; lane reports now require Node as well as Python, with no extra
package install. The legacy fields above remain historical comparison fields.
`measurement.m4.routed_share` uses confirmed fetches, including nested ctx
fetches. `fetch_mentions_unconfirmed` counts possible fetches from raw
`HTTP_SCRIPT`, command-position `curl`/`wget` and `gh api` matches that no
executed-text match traces back to (the workflows README defines the rule).
`routed_share_lower_bound` adds those possible fetches to the denominator as
unrouted. **The #381 M4 >= 0.9 gate must use `routed_share_lower_bound`.**
Both shares and the separate possible-fetch count also appear under
`measurement.m4.by_carrier`; aggregation sums counts before recomputing shares.
Any possible fetch leaves M4 status `incomplete`. The source contract is
[#381 M4](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json#L2921-L2930)
and the detector reference is
[context-mode v1.0.169 routing.mjs:788–795](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L788-L795).
Ignored interpreter stdin, comments and written scripts can supply possible
fetches while contributing zero confirmed operations. The bound covers visible
detector matches; it does not certify arbitrary dynamic code.
M3/M5 use own persisted `function_call_output` and
`custom_tool_call_output` content, paired with function, custom or local-shell
calls; native `item_completed` content is the fallback. A missing context
result stays visible instead of being supplied as an empty result.
Function namespaces and legacy local-shell IDs are preserved. Strings and text
block payloads use their UTF-8 bytes; only non-text blocks use compact JSON.
Response-item output takes priority when both representations exist. Other
function results remain in M3's `other` carrier and orphan results are counted.

Nested operations inside code-mode `exec` are sandbox operations: they supply
M4 fetches, RTK command parts and MCP state observations, while only the outer
exec return contributes M3 bytes (`code_mode` carrier). Nested ctx returns do
not contribute M5 bytes unless represented by a direct model-visible ctx call.
`sandbox_operations` counts the normalized nested operations.

`measurement.cli_lanes` and `measurement.proxy` come from the same kernel
([CLI lanes by command position](../../examples/claude-native/workflows/README.md#cli-lanes-by-command-position-2026-09-28)).
Shell commands of `exec_command`, `shell_command`, `shell` and local-shell
calls and of `CommandExecution` items are read in command position; those
nested in a code-mode `exec` count under carrier `nested`. A Codex argv array is one command, not
shell text (U1 pivot D6, GPT-6 finding 11): a POSIX shell's script argument is the script itself
(`[shell, -lc, script]` as `codex-rs/core/src/shell.rs` runs it), and any other argv is
joined with each element quoted (`shlex.join`), so a metacharacter inside one element stays data and
`["echo", "qmd; rtk proxy qmd status"]` counts no lane.

The PR-A measurement reads each shell call by the shell that ran it (U3 design section 6, with the
review's finding that `shell_script` keeps its reading for the legacy lane counters):

- An argv (a `CommandExecution`'s `command`, a local-shell or `shell` call's `command`) runs its
  program directly. The program is typed by its file stem, with `/` and `\` as separators: `sh`,
  `bash`, `zsh`, `dash` and `ksh` are POSIX shells, and with `-c` among their short options the first
  non-option argument is the script (bash(1) INVOCATION: `-lc`, `-cl`, `-e -c`, and `-o pipefail -c`,
  where each `o` or `O` takes the next word). `--` or `-` ends the options, and the word after it is
  the script (bash(1) OPTIONS: "An argument of - is equivalent to --"; POSIX.1-2024 XCU sh; bash 5.2.21
  and dash run `-c -- 'script'` and `-c - 'script'` so). A long option such as `--login` leaves no
  script. `pwsh`, `powershell` and `cmd`, matched ASCII case-insensitively as Windows resolves program
  names, are not POSIX shells.
- `exec_command`'s `cmd` runs in the shell its `shell` argument names, typed as Codex types it
  ([shell_detect.rs:39-59](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/shell-command/src/shell_detect.rs#L39-L59)):
  the value, else its file stem again and again, case-sensitively. `zsh`, `bash` and `sh` are POSIX
  shells, `pwsh`, `powershell` and `cmd` are not, and any other value (or one that is not a string,
  which fails `ExecCommandArgs`) runs the OS fallback shell, `/bin/sh` on Unix and `cmd.exe` on
  Windows (`:315-334`), which the rollout does not record. Without a `shell` (absent or null) the
  session's shell runs `cmd`, read as a POSIX shell.
- A command whose text is not a POSIX script, or whose shell is not known, is unresolved and counted
  in `measurement.codex_commands` (`non_posix_shell`, `unknown_shell`). It stays a Bash call, with
  no text: its result bytes count in M3, it counts in no CLI lane, `m4.status` reads `incomplete`
  because its fetches cannot be read (the per-carrier M4 statuses count what was read), and with
  `--rtk-check` it is an explicit `rtk_parts.unknown_calls` entry (its empty text is still replayed,
  which rtk 0.50.0 answers with `No rewrite for:` and no parts). Groups force the same `m4.status`,
  since the kernel's aggregate recomputes it from the counts.
- A `CommandExecution` whose `source`
  ([protocol.rs:3534-3544](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L3534-L3544))
  is `user_shell` is the user's own command, whose output Codex records as a conversation item and
  not as a tool result (`codex-rs/core/src/tasks/user_shell.rs:190-205`, `:453-481`), and one whose
  source is `unified_exec_interaction` is an interaction with a running process (no core code sets
  that source at rust-v0.157.1, so this reading is conservative). Neither is a model tool call: no
  tool use and no result, counted only in `codex_commands.user_shell` and
  `codex_commands.exec_interactions`.
- `codex_commands` counts a call once, at its first record inside `[since, until)`, as the kernel
  keeps a call's first tool use, so adjacent windows add up. The legacy `shell_calls`,
  `rtk_prefixed_shell_calls` and `fetch` counters keep counting every `CommandExecution` with
  `shell_script`'s reading, as the historical comparison fields they are.

A measurement (not an aggregate) awaits the
kernel's `loadShellParser()` before it reads, as the kernel's own CLI does: the CLI-lane reading
needs the verified tree-sitter-bash install (`CHILD_USAGE_SHELL_PARSER`, then the ecosystem tools
directory that `shell-parser.pin.json` names), and without one `measurement.cli_lanes` is `{status:
'parser_unavailable', reason}` and no lane is counted. The unified exec header's exit code is read
up to nine digits; a longer one leaves the state `unknown` instead of raising (finding 12). Codex prints
an `i32` there (`exit_code: Option<i32>` at `codex-rs/core/src/tools/context.rs:389`, formatted at `:535`,
rust-v0.157.1), so ten digits can only come from a Windows-native Codex, whose crash statuses (an access violation
is `-1073741819`) then read `unknown`, never succeeded. On this stack (Linux) the statuses are small (0 to 255, and
-1 for a call declined before it ran). Checked by calling `exec_header_state` with `-1073741819`, `1073741819` and `3221225477` (each
`(False, "unknown")`); not checked against a Windows Codex.

A call's state comes
from its persisted item status when there is one: `failed` is failed, and
`declined` (a rejected command, exit -1 in
[events.rs:562-573](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/events.rs#L562-L573))
is failed and not executed. Without an item state, as in legacy history mode,
a shell call's output is read by the unified exec header of
[context.rs:524-548](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/context.rs#L524-L548),
and only by the lines before `Output:`. `Process exited with code 0` is
succeeded and any other exit code failed. A `Process running with session ID
N` line, a header with neither line, or an output without the header reads
`unknown`, since a rollout output never carries the success flag
([models.rs:2173-2182](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/models.rs#L2173-L2182)).
The later `write_stdin` output that reports a running process's exit is not
linked back to its call. No `shell`, `shell_command` or local-shell handler
exists at rust-v0.157.1, so their outputs have no pinned header and read
`unknown` unless an item state decides; the `Exit code: N` text that
`apply_patch` returns is not read.

Nested Codex code-mode shell curl/wget commands share M4's existing
`ctx_sandbox_fetch` bucket with context-mode sandbox curl/wget commands. Both
are remote-denominator operations; this bucket does not identify exclusive
context-mode use. This mapping follows the adapter's sandbox normalization and
the [context-mode v1.0.169 subprocess detector](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L727-L804).
Native MCP `status` supplies completion/failure state when result bytes were not persisted.

Code-mode attribution (U3 design section 7, commit 7, with the review's position, item-kind and
`web_search_call` findings) has no persisted parent field to read, so it is positional:

- An item whose id is a model call's is direct: a function, custom, local-shell or tool-search call,
  or a hosted `web_search_call`
  ([models.rs:1182-1203](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/models.rs#L1182-L1203)).
- Any other emitted item (a `CommandExecution`, an `McpToolCall` or a `web.search` `Extension`) is
  nested when an own `exec` call came earlier in its turn. A cell keeps running after `exec`
  returns, through `yield_control()` and the code-mode `wait` tool that resumes it
  ([description.rs:19-51](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/code-mode-protocol/src/description.rs#L19-L51),
  [lib.rs:51-52](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/code-mode-protocol/src/lib.rs#L51-L52)),
  so neither the exec return nor another direct call ends it; only the turn does. Every turn event
  the tool reads ends a turn: `task_started` (alias `turn_started`), `task_complete` (alias
  `turn_complete`) ([protocol.rs:1403-1415](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L1403-L1415)),
  `turn_aborted`, and the attempt ends `task_completed`, `turn_completed` and `turn_failed`.
- Such an item before its turn's first `exec`, or in a turn without one, stays direct and counts in
  `measurement.code_mode.unattributed_items`. Reasoning, message, `clock.sleep` and `FileChange`
  items are no tool calls and count nowhere, nor do the skipped `user_shell` and interaction commands.
- A `wait` call without a namespace after an `exec` of its turn is code mode: its output is the
  cell's, so its bytes count under M3's `code_mode` carrier. The multi-agent `wait_agent` stays
  `other`.
- `measurement.code_mode` counts `exec_calls`, `wait_calls`, `nested_items` and
  `unattributed_items`, each once at its first record inside `[since, until)`, and groups sum them.
- Concurrent cells are not told apart: a nested item belongs to its turn, not to one `exec`.
  A hosted web search's own item (`TurnItem::WebSearch`,
  [items.rs:57-61](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/items.rs#L57-L61))
  is not emitted, as the Claude kernel counts no server tool; this host's store holds none.

Before commit 7 an item was nested only until the exec return, the next direct model call or a turn
boundary. The rule can move `sandbox_operations`, M3 `by_carrier`, M5, the M4
`shell_fetch`/`ctx_sandbox_fetch` split and U1's `proxy.nested` and `cli_lanes` carrier `nested`. On
this host's store 271 items moved from direct to nested and 352 `wait` outputs from `other` to
`code_mode`. M3 lost 265 results, and M5 lost all 153 of its results: each came from a ctx item the
new rule nests, after an exec of its turn. `proxy.nested` gained 5, and the M4 split did not move,
since none of the moved items ran `curl` or `wget` (the differential in
[pra-u3-differential-20260929](../../evidence/artifacts/pra-u3-differential-20260929/README.md)).

Legacy history mode persists no nested tool item that this adapter reads: no `CommandExecution`,
`McpToolCall` or `web.search` `item_completed`
([policy.rs:94-112](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/rollout/src/policy.rs#L94-L112))
and no `ExecCommandEnd` (`:145`). It does keep `McpToolCallEnd` and `WebSearchEnd` events
([:123-135](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/rollout/src/policy.rs#L123-L135)),
which the adapter does not read; whether a code-mode nested MCP call emits one was not read. A
`SessionMeta` without `history_mode` is legacy
([protocol.rs:772-779](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L772-L779)).
Rows with no `session_meta`, or with a `history_mode` other than `paginated`, are read the same way (U3 design
section 7, commit 8, with the review's per-exec finding):

- An `exec` call is an unobservable span when its code has a static fetch-capable site and no nested item
  is attributed to it (an emitted item after it and before the next `exec` call or the end of its turn).
  `code_mode.legacy_unobservable_exec_calls` counts it once, in the window of its call record;
  `legacy_unobservable_sites` counts its sites. Either makes `m4.status` incomplete for the actor and its
  groups. `fetch_mentions_unconfirmed` keeps its raw-detector meaning.
- A site is the global `tools` (not a longer name, not a property such as `x.tools`) followed by a dot
  (blanks and `?.` allowed) and `exec_command`, `web__run`, or `mcp__<server>__` plus `ctx_execute`,
  `ctx_execute_file`, `ctx_batch_execute` or `ctx_fetch_and_index`, the code-mode identifiers of
  [description.rs:21 and :365-387](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/code-mode-protocol/src/description.rs#L365-L387).
  Any bracket access `tools[...]` also counts, since it can name any tool. Strings and comments are not
  told apart, and an alias (`const t = tools`) or destructuring is not seen. The scan is linear.
- This host's store is paginated throughout, so the rule changes nothing there.

#### The outer exec code (the 10e decision, 2026-09-29)

Scope item 10e left one piece open: AA:328's rule that `fetch()` or an HTTP library in a script counts as
unknown, applied to the JavaScript of a code-mode `exec` call itself (the U3 review's outer-JS finding).

- **Evidence.** At both client versions in this host's store, the code-mode isolate has no network access.
  `code-mode-protocol/src/description.rs` says "Runs raw JavaScript -- no Node, no file system, no network
  access, no console." (line 24 at rust-v0.157.1, 36650394; line 20 at rust-v0.155.1, be2951ea). And
  `code-mode-runtime/src/runtime/globals.rs:36-48`, byte-identical at both tags, installs only `tools`,
  `ALL_TOOLS`, `clearTimeout`, `setTimeout`, `text`, `image`, `audio`, `generatedImage`, `store`,
  `load`, `notify`, `yield_control` and `exit`: no `fetch`, and V8 has none of its own. A cell's network
  operation is therefore a nested tool call, which a paginated rollout persists as an item, and the
  frozen M4 population is remote fetches
  ([#381 M4](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json#L2921-L2930)).
- **Chosen.** Where the isolate was read (`NO_NETWORK_ISOLATE_CLIENTS`: 0.155.1 and 0.157.1, from
  `session_meta.cli_version`), the outer code is never a fetch. Its mentions of the kernel's
  `HTTP_SCRIPT` pattern are only counted, in `code_mode.outer_http_mentions`. For any other client,
  or a rollout naming none, an `exec` with a mention counts in
  `code_mode.outer_http_unverified_exec_calls` and makes `m4.status` incomplete for the actor and its
  groups; the fetch counts keep their meaning.
- **Alternatives.**
  - (a) The review's fallback: count each outer mention that no nested item explains as unclassifiable.
    Rejected where the isolate was read, because the mention cannot fetch and would put a non-fetch in
    M4's denominator. It would also need a persisted parent field to say which item explains it, and
    none exists (commit 7).
  - (b) The design's plan: scan nothing and record nothing. Rejected, because it hides the residual and
    is not limited to the versions that were read.
- **Residual on this host.** A count-only census up to 2026-09-29T00:00Z found 1,532 mentions in 1,091
  of 16,410 exec calls. 1,481 of them are in exec calls with a nested Context Mode code item after them,
  whose code the kernel scans itself. The other 51, in 33 calls, have no such item. All 1,620 rollouts
  name 0.155.1 (277) or 0.157.1 (1,343).
- **Overturn.** Any of these reopens the decision:
  - a pinned client whose description drops "no network access", or whose globals gain a
    network-capable function;
  - a rollout from a client that was not read (checked by the measurement itself, as above);
  - the PR-A owner's rejection, in which case alternative (a) applies.
- **Record.** `docs/decisions/` is outside this unit's paths, so the PR-A owner accepts or rejects this
  text. The census script and its counts are in
  [pra-u3-differential-20260929](../../evidence/artifacts/pra-u3-differential-20260929/README.md).

`--rtk-check` uses the same Linux gate as the Claude tool: a binary on PATH
self-reporting `rtk 0.50.0` that passes the isolated five-exclusion probe.
This checks behavior, not build identity or the qualification receipt's hash.
`--exceptions` shares the private digest-bound adjudication contract, including
validation of every supplied review class.
For Codex, observed coverage comes from explicit prefixes, since the Codex hook is held. The replay
asks `rtk hook check --agent codex` (U3 design section 5, commit 9; `rtk_parts.agent` says so): the
decision the held Codex hook would make, never evidence that one ran. rtk-ai/rtk v0.50.0 maps `codex`
to `InProcess(Host::Codex)`, which has no RTK-side permission rules, while `claude` merges the Bash
rules of the project's and the home's `.claude/settings(.local).json`
([decision.rs:196-204](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs#L196-L204),
[permissions.rs:56-67, :141-175](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/permissions.rs#L141-L175)).
Before commit 9 the Codex lane replayed with `--agent claude`, so a Claude deny rule of the machine
running the tool turned a Codex part into an unknown call. The rewrite decision is the same for both
agents ([decision.rs:61-97](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs#L61-L97)).
Add these flags to the existing `--lanes` command when measuring M6c.
M6c reads the deterministic `explicit_rtk_on_excluded_or_sensitive` zero counter;
conditional log/find forms stay in the separate advisory counters and require
the shared per-part `rtk_log_find` sidecar review described in the kernel docs.
Proxy parts stay outside the coverage denominator. `sidecar_records` reports
bound/unbound digest counts across measured rollouts without publishing records.

The U2 kernel fields of 2026-09-29 ([U2 measurement fields](../../examples/claude-native/workflows/README.md#u2-measurement-fields-2026-09-29))
appear on Codex actors too, read from the bridge's normalized rows. `call_states` (M14) and `m15` come from the
same call states (a `declined` item is a rejected call with source `declined`). `rtk_parts` splits commands
with binding decision B8's parts and adds the M1 fields `eligible_call_states` and
`observed_covered_succeeded_calls`, which M1's rtk-codex lane reads with `--rtk-check`. `final_return` is
`not_applicable` on every Codex actor: the bridge emits tool calls and results only, with no provider message
id or assistant text, so a Codex final return cannot be read here and is never reported as a zero.
`cli_lanes.lanes.*.failed` keeps U1's meaning (M14's failed is `failed - not_executed`). Three parts belong to
the Codex adapter, not the shared kernel: the Codex half of the private call ledger (`conversation.id` and
`call_id`; the kernel's `callLedger` gives a bridge row `session_id` and `owner` null), the `root_mismatch`
flag that makes a context-mode boundary refusal an M15 `binding` error, and how the approval denial
(`ReviewDecision::denied`) text reaches a rollout; the kernel classifies that text as `approval` even when the
call did not run.

`rtk_parts.d7` is the Codex-only view of D7's RTK-eligible class, computed by the kernel for Codex replay:

- It starts from the fixed-config eligible parts and drops each `git log` or `find` part that a digest-bound
  `rtk_log_find` review marks `requires_raw`, prefixed or not.
- An unreviewed `log` or `find` part stays and leaves `d7.status` incomplete, as does an unknown call.
  An unresolved command is an unknown call.
- `covered_parts` are observed, from explicit prefixes.
- `wrapped_exceptions` inherits the fixed-config `explicit_rtk_on_excluded_or_sensitive` (M6c's zero counter,
  whose classes are broader than the deployed exception list, the review's provenance finding) and adds
  `wrapped_requires_raw_parts`, the prefixed parts a review says required raw output.
- The deployed list in `adoption/templates/codex.AGENTS.template.md` names `git log` and `find` as conditional
  exceptions. The unconditional ones (`git show REV:path`, `diff`, `git branch`, `jq`, and `rtk` before
  `cd`, `export` or `source`) are already ineligible under the five exclusions, or have no rewrite.
- The fixed-config fields keep their meaning. Which of the two views M6c grades from is the M6c owner's call.

`measurement.provider_usage` differences cumulative `token_count` counters
per rollout and attempt, using inherited/pre-window snapshots only as a
baseline. Repeated totals contribute nothing. Input, cached input, cache-write
input, output, reasoning output and total tokens remain separate; cached and
cache-write input and reasoning values are subsets, never additive cost buckets.
Missing baselines, absent counters, counter regression and missing terminal
evidence leave accounting incomplete. The one exception is
`cache_write_input_tokens`: it is `serde(default)` at rust-v0.157.1
([protocol.rs:2239-2241](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L2239-L2241)),
so a rollout of an older client can lack it. Its value is then `null`, never 0, and
its absence leaves `complete` unchanged. A group total of any counter is `null` when an
actor's is. Each attempt also keeps `max_request_input_tokens`, the largest
`last_token_usage.input_tokens` of its counted snapshots (a request's own input,
for the long-context tier), or `null` without one.
Known usage remains counted for failed/interrupted turns. A native
`task_complete` with `error` is failed. Each attempt reports the configured
model and effort of its turn context when available; it does not claim
provider-resolved routing. The effort is kept whatever its name, since
`ReasoningEffort` includes `none`, `minimal`, `ultra`, `persistent` and model-defined
strings ([openai_models.rs:59-72](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/openai_models.rs#L59-L72)).
The model keeps at most one provider segment in front of its name (a gateway
route such as `cx/gpt-6-astra`). Any other shape (a path, `..`, more segments)
reads `(other)`, and a value that is not a string reads `null`.
Supply one rollout per thread; this tool does not reconcile copied files of
the same thread from multiple archives. Interrupted terminal usage that the
client never persisted cannot be reconstructed. Codex actor and group
measurements omit the inapplicable Claude `usage` object entirely.

Sources: [Codex rust-v0.157.1 native usage protocol](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L2234-L2310),
[native function namespace](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/models.rs#L1073-L1088),
[custom/local-shell calls and outputs](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/models.rs#L1060-L1165),
[code-mode emission test](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/tests/suite/code_mode.rs#L721-L760),
[nested and outer byte limits](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/tests/suite/code_mode.rs#L3436-L3752),
[MCP item state and optional result](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/app-server-protocol/src/protocol/v2/item.rs#L333-L352),
[terminal error](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L2146-L2152),
and [ccusage v20.0.24 baseline/delta parsing](https://github.com/ccusage/ccusage/blob/v20.0.24/rust/adapters/codex/src/parser.rs#L153-L350).
The project-specific measurement contract is
[#381 preregistration](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json).
Tests use synthetic transcripts (`python3 -m unittest tests.test_skill_usage`);
they are not live provider acceptance or unchanged upstream tests.

Sessions that did not load the user config are negative controls, never workers. Rollouts do not
record `--ignore-user-config` itself, so the report classifies each session by its skill catalog:
Codex applies skill enable/disable rules only from the User and SessionFlags config layers
(`codex-rs/config/src/skills_config.rs` at `rust-v0.157.1`), and `--ignore-user-config` loads the
User layer as an empty table (`codex-rs/config/src/loader/mod.rs`). A catalog that lists the
SKILL.md of a manifest skill with `codex_enabled: false` therefore means the trial's
`enabled = false` entries in the user config did not apply (`user_config: ignored`); a catalog
listing only enabled manifest skills is `applied`; no catalog is `unknown`. This needs the
rendered disable list in the host's user config; a host without it reports every session as
`applied` or `unknown`. `groups.workers` covers `applied` sessions (also split into top-level `exec`
sessions and spawned `subagent` sessions), `groups.negative_controls` the `ignored` ones.

`groups.workers_by_role` splits the workers by custom-agent role, and `actors[].role` and
`sessions_by_role` report it for every session. The role is `session_meta.agent_role`, which also reads
from `agent_type`
([protocol.rs:3153-3155](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L3153-L3155)),
else the `agent_role` (or `agent_type`) of the `source.subagent.thread_spawn` source
([:2904-2913](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L2904-L2913)),
taken from the session's first `session_meta` (a sub-agent rollout repeats its parent's meta second).
It is trimmed as the spawn handler trims it
([spawn.rs:126-130](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs#L126-L130),
Rust `str::trim`, Unicode White_Space); an empty value or one that is not a string is no role. A role
that is not name-shaped is `(other)`, a sub-agent without a role is `(none)` and every other session is
`(root)`. A V2 spawn that is not a full-history fork can carry the role `default` when a default role
file is configured
([child_config.rs:86-98](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/child_config.rs#L86-L98)).

Each sub-agent actor carries `spawn`, and `subagent_spawns` counts every state of it across the
sub-agents. The join runs in memory over every scanned rollout, inside the window or not, and
publishes states only. A child's thread id names a `SubAgentActivity` started item in its parent's
rollout, and that item's id is the `spawn_agent` call id
([spawn.rs:216-226](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs#L216-L226)).
Only the parent's own records count. A forked child's copies of them, below its start ordinal, are the parent's.
`join` takes one of these values:

- `joined`: the owner is the child's `parent_thread_id` and holds the call.
- `activity_without_spawn_call`: the owner holds no such call, as for a spawn made inside code-mode `exec`, whose
  arguments are not persisted.
- `parent_mismatch`: another thread owns the item.
- `parent_without_started_item`: the parent was scanned but holds no started `item_completed` for the child.
  A legacy rollout persists only completed `SubAgentActivity` items
  ([policy.rs:107-111](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/rollout/src/policy.rs#L107-L111))
  and keeps the others as `SubAgentActivity` events
  ([:136-139](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/rollout/src/policy.rs#L136-L139)),
  which the join does not read, so a legacy parent's children read this state.
- `parent_not_scanned`.

`requested` (`fork_turns`, `fork_n`, `role`, `model`, `effort`) comes from a joined call only and is
otherwise `unknown`. `fork_turns` is read as the spawn handler reads it
([spawn.rs:265-299](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs#L265-L299)):

- The value is trimmed, and an absent or empty one is `default_all`.
- `none` and `all` match case-insensitively.
- A positive integer string is `last_n` with `fork_n`, and anything else is `invalid`.
- The frozen launch matrix writes `fork_turns: 2`, so a positive JSON integer reads as `last_n` too. At
  rust-v0.157.1 such a call fails, because the field is a string.
- A V1 spawn (namespace `multi_agent_v1`) reads its `fork_context`: `true` is `all`, and otherwise the value is `none`.

`effective` holds the child's role, its `history`, its `turns`, the model and effort keys of its own
turn contexts, and `settings`, its first own `ThreadSettingsApplied`. `history` is `forked` when a start
ordinal exists, else `fresh`. The remaining fields compare what was requested with what ran:

- `fork_consistent` compares the requested fork with the history.
- `role_state` compares the requested role with the recorded one.
- `route_vs_request` and `route_vs_parent_turn` give, per field, `match`, `mismatch`, `not_requested` or
  `unknown`. They compare the raw strings of every own turn with the request, or with the parent's latest
  turn context before the call.
- `route_changes_within_child` says whether the child's route changed between its turns.
- `followups` counts the parent's `followup_task` calls whose target is the child's id or task path, and
  V1 `resume_agent` calls with its id
  ([multi_agents_spec.rs:217-266](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L217-L266)).
  It is `null` when the parent was not scanned.

`expected_route_basis` is per field and follows
[child_config.rs:62-99 and :196-253](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/child_config.rs#L196-L253):

- `role_file` applies to a child with a recorded role, whose role file applies last.
- `spawn_request` applies to a requested value.
- A model without an effort takes `agents_default_or_model_default` for the effort.
- Otherwise the basis is `agents_default_or_parent_turn`.

The route is client-side. A provider reroute is not persisted in rollouts, so `reroute_evidence` is always
`not_persisted_in_rollout`, and a mismatch is a state, not an error. For a child with a role, the expected
route is its role TOML, which the rollout does not hold.

The lane report keeps the same privacy boundary: server, tool-kind, skill and role names, model and
effort keys, spawn states, counts and token figures only, with sessions never named by id or path (the
spawn join's thread ids, call ids, task paths and follow-up targets stay in memory); a server, function,
originator, role or content-kind name that is not name-shaped is counted as `(other)`. Thread and call ids
leave only through the private `--call-ledger` file below. Rollout files not modified since
`--since` are skipped unread (counted as `files_skipped_unmodified`). Evidence from it is a
`local_integration` measurement of native transcripts, not a model run.

### The private call ledger (`--call-ledger`)

`--call-ledger PATH` (with `--lanes`) also writes the per-call Codex ledger that the M14 reconciler joins
with Loki's `codex.tool_result` and `codex.tool_decision` events by `(thread_id, call_id)`. It is gap G1 of
the U11 design and binding correction 1 of the U3 build. The records come from the kernel's `callLedger`,
PR-A U2's export (U2 design section 4.5; `child-usage.mjs:2793-2820` at
`claude/pra-u2-kernel-measures-2d-20260929` b2dd1eb7), run over the same normalized rows and window as the
measurement. The ledger therefore holds exactly the calls the measurement counts.

```sh
python3 tools/skill-usage/skill_usage.py --lanes --codex-root ~/.codex/sessions \
  --since 2026-09-25T17:18:00Z --until 2026-09-26T15:05:00Z --json \
  --call-ledger /private/dir/outside/any/checkout/codex-calls.jsonl
```

Each JSONL record (`schema: codex-call-ledger/1`) holds these fields:

- `thread_id`: the first `session_meta` id, the thread's conversation id.
- `call_id`: the adapter's key for the call. That is the `response_item` `call_id` (else its `id`), or
  the `item_completed` `item.id` of a `CommandExecution`, `McpToolCall` or `web.search` item. A code-mode
  `exec` and a command its JavaScript ran are therefore two calls. A paginated direct `exec_command` is
  one call, because its item carries the call's own id. An id the adapter made up for a record without
  one (`missing-N`), or a value that is not a string, is `null`.
- `owner_kind`: `exec` for a `codex exec` root and `subagent` for a spawned sub-agent. Another root is
  `other`, and rows with no `session_meta` give `null`.
- `tool`, `server`, `state`, `cause`, `native_status`, `sandbox` and `code_mode`: the kernel's fields as
  it measured the call.
  - `tool` is the normalized name, so a shell call or command item reads `Bash`.
  - `state` is U2's M14 vocabulary: `succeeded`, `failed`, `interrupted`, `rejected`, `invalid`,
    `cancelled_with_result`, `cancelled_or_unfinished` or `unknown`.
  - A code-mode `exec` reads `succeeded` once its output returned, since a rollout output carries no
    success flag.
  - `sandbox` marks a call nested in code mode, and `code_mode` an `exec` or its `wait`.
- `history_mode`: the mode the measurement read from the first `session_meta` (`paginated`, else
  `legacy`). A sub-agent takes its own meta, never the parent's copied one.
- `actor_ordinal`: the session's `ordinal` in the published `actors` list, as in U2's sweep ledger.

The file follows the rule of `frozen_checks.private_create` on main (a02ff13f,
`tools/token-e2e/frozen_checks.py:1309-1369`) and U2's `ledgerTarget`:

- It is created once, with `O_EXCL` and `O_NOFOLLOW`, at mode 0600.
- A new parent directory is made 0700.
- A path inside any git work tree (a `.git` entry beside it or above it) is refused, as is an existing
  path.
- Every refusal comes before the scan: the path, `--out` inside this checkout, `--out` naming the same
  file (the report would be written over the ledger), and a kernel that exports no `callLedger`. The file
  is written before the report is written or printed, so a refusal or a failed write exits 2 with neither.
- Without the flag nothing is probed or written.

**Dependency.** Until PR-A U2's kernel is merged with this tool, `child-usage.mjs` exports no `callLedger`.
`--call-ledger` then exits 2 with "the measurement kernel exports no callLedger" and writes nothing, and
the five real-kernel tests of `CodexCallLedger` skip. On a scratch tree of this branch with U2's kernel at
b2dd1eb7, the class's 13 tests failed first (at 00c458ba) and all 14 pass at 45a5c0c1, the 14th being the
`--out` refusal added later. The host run of that tree is in
[pra-u3-differential-20260929](../../evidence/artifacts/pra-u3-differential-20260929/README.md).

## Verify the bundle

```sh
uv run --no-project --with jsonschema --with pyyaml python -m unittest tests.test_skill_usage -v
```

Fixtures under `tests/fixtures/skill_usage/` are entirely synthetic: a hand-built manifest and
skills-lock reusing real pinned skill names, a sanitized `/skill-doctor` capture (no real cwd,
session id or host path), and hand-built `rollout-*.jsonl` lines shaped from the upstream
`codex-rs` protocol (`RolloutLine` / `RolloutItem` / `ResponseItem`, `openai/codex` at tag
`rust-v0.155.1`), not a captured transcript. The `codex_lanes/` rollouts for `--lanes` follow the
codex-cli 0.157.1 record shapes (`session_meta`, `world_state`, `event_msg` `token_count` and
`item_completed`), also hand-built. They are committed as `rollout-*.jsonl.fixture`
(the repository's `.gitignore` has a blanket `*.jsonl` rule); the test suite materializes each
one under its real name into a temporary directory before scanning it.
