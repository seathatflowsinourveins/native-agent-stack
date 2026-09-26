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
`$XDG_STATE_HOME/skills/.skill-lock.json` wins when set to an absolute path), and `--json` (print
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

Shell, MCP and fetch counts come from `item_completed` events, an event whose persistence depends
on the rollout's history mode (`codex-rs/rollout/src/policy.rs`); `response_item` records are
persisted in every mode. The report therefore gives `sessions_by_history_mode`
(`session_meta.history_mode`) and `sessions_with_tool_calls_but_no_item_events`, the sessions
whose own records hold model tool calls but no such event: their shell, MCP and fetch lanes read
as zero. `ctx_fetch_and_index_share` compares three lanes only (hosted page opens,
`ctx_fetch_and_index` and remote `curl`/`wget`); a fetch run inside a Context Mode sandbox
(`ctx_execute` code), a `gh api` call and `fetch()` or an HTTP library in a script are in no lane.
`curl`/`wget` also counts behind the shell keywords `do`, `then`, `else`, `elif`, `if`, `while`,
`until`, `!` and `{` and behind `rtk`, `sudo`, `env`, `command`, `exec`, `time`, `nice`, `nohup`
or `timeout N`.

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
