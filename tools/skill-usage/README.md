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
and Here Documents). This legacy counter keeps its own Python rule (`executed_text`), which predates
the kernel's reading of heredocs inside `"$( )"` and of strings a shell runs, so on those shapes it
can disagree with `measurement.m4` and with the Claude lane's `bash_curl_wget`: a `curl` line in the
heredoc of `bash -c 'cat <<EOF > x.sh ...'` counts here as a fetch and there as data.

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
nested in a code-mode `exec` count under carrier `nested`. A call's state comes
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
The adapter uses direct response call IDs first; other items in an open exec
span are sandbox operations until its return, the next direct model call or a
turn boundary. This local span rule covers the retained fixture. Interleaved or
resumed cells without a persisted parent association need independent review.

`--rtk-check` uses the same Linux gate as the Claude tool: a binary on PATH
self-reporting `rtk 0.50.0` that passes the isolated five-exclusion probe.
This checks behavior, not build identity or the qualification receipt's hash.
`--exceptions` shares the private digest-bound adjudication contract, including
validation of every supplied review class.
For Codex, observed coverage comes from explicit prefixes; the replay fields
are hypothetical Claude-hook routing, never evidence a Codex hook ran.
Add these flags to the existing `--lanes` command when measuring M6c.
M6c reads the deterministic `explicit_rtk_on_excluded_or_sensitive` zero counter;
conditional log/find forms stay in the separate advisory counters and require
the shared per-part `rtk_log_find` sidecar review described in the kernel docs.
Proxy parts stay outside the coverage denominator. `sidecar_records` reports
bound/unbound digest counts across measured rollouts without publishing records.

`measurement.provider_usage` differences cumulative `token_count` counters
per rollout and attempt, using inherited/pre-window snapshots only as a
baseline. Repeated totals contribute nothing. Input, cached input, output,
reasoning output and total tokens remain separate; cached/reasoning values
are subsets, never additive cost buckets. Missing baselines, absent counters,
counter regression and missing terminal evidence leave accounting incomplete.
Known usage remains counted for failed/interrupted turns. A native
`task_complete` with `error` is failed. Each attempt reports a configured
model/effort when available; it does not claim provider-resolved routing.
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

The lane report keeps the same privacy boundary: server, tool-kind and skill names, counts and
token figures only, with sessions never named by id or path; a server, function or originator
name that is not name-shaped is counted as `(other)`. Rollout files not modified since
`--since` are skipped unread (counted as `files_skipped_unmodified`). Evidence from it is a
`local_integration` measurement of native transcripts, not a model run.

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
