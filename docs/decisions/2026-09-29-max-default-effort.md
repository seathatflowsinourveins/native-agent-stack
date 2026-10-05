# Decision: effort max for interactive terminal launches, through the launcher (2026-09-29)

**Decided by:** session `native-agent-stack-03` on host `nativestack-5975wx-20260925`, for the user's requests of
2026-09-23 ("effort max and ultracode default for all future workflow and github, max quality"), 2026-09-29 ("please set
up the default effort to max quality, all setting tuned to latest sota converged highest quality of our claude code
setting") and 2026-09-29 ("please resolute our max quality setting, finalize e2e with sota repos upstream"). Checked
against Claude Code 2.1.284, the latest release when this was written (binary sha256 in the receipt); branch
`claude/max-default-effort-20260929`, rebased onto `origin/main@ba31dcd0`. It acts on the third overturn condition of the
[2026-09-23 max-effort record](2026-09-23-max-effort-default.md), which 2.1.284 meets, and leaves that record as history
for 2.1.281. That record's 2026-09-29 addendum (#479, the Sonnet 5.5 dispatch change) found the same condition met by the
Ultracode-reminder indicator but "not adopted: the coordinator stays at xhigh, and moving it to `max` is left to the user"; this
record is that move, made on the user's 2026-09-29 request and limited to interactive launches through the launcher.

**Scope:**

- the claude launcher that `install_native` writes, in `adoption/bootstrap-linux.sh` and `adoption/bootstrap-macos.sh`
  (identical copies, as `tests/test_adoption_bootstrap.py` requires), and the tests that pin its behaviour;
- the bootstrap and macOS platform notes that describe the launcher;
- the receipt [`claude-max-default-effort-20260929`](../../evidence/receipts/claude-max-default-effort-20260929.json);
- one host file, applied by hand with a backup and a read-back: `~/.local/share/codex-ecosystem/bin/claude`.

The wording of the coordinator rule in `AGENTS.md`, the portable and host `CLAUDE.md`, the recipes and the workflows README
belongs to the session that owns the Sonnet 5.5 and Opus 5.5 dispatch change (its `lane:shared` follow-up waits for this record's
merge); this record gives it the rule to state. The effort guard, the settings files and every agent definition are unchanged by
this branch. The saved `xhigh` levels that #479 added stay as they are: they are the fallback in point 2 below.

**How the effort guard sees a launcher session.** `adoption/hooks/claude/effort-default-guard.py` resolves the level from the
settings files, so it cannot see a `--effort` flag. Its SessionEnd branch returns at once when the transcript's effort is `xhigh` or
higher, so a session at `max` never triggers a save. Its SessionStart warning fires when a model resolves to no level or to one below `xhigh` in the
settings files; on a host or model with no saved level it would warn even though the launcher runs the session at `max`. That
warning is advisory and this branch leaves the guard alone; the host's user settings hold saved levels for both current models.

## Decision

1. **Interactive terminal launches through the ecosystem launcher start at effort `max`.** The launcher adds `--effort max`
   only when nothing has chosen an effort: stdin and stdout are a terminal, no `-p`/`--print` (also as a short-flag cluster such
   as `-pc`), no `--effort`/`--effort=`, `CLAUDE_CODE_EFFORT_LEVEL` unset, nothing after a `--`, and a client that reports
   2.1.284 or newer (the release that keeps Ultracode on at `max`; a `max` session on 2.1.281 turned orchestration off). Ultracode
   stays on (`ultracode: true` in the user and project settings). The scan does not know which options take a value, so an
   operand that equals one of those flags (`--system-prompt --effort`) also suppresses the default: the safe direction.
2. **Saved per-model `xhigh` stays as the fallback.** Claude Code cannot save `max`, so a launch that does not go through the
   launcher (the IDE extensions, the desktop app, the web client, a host whose bin directory is `~/.local/bin`, a direct call
   of `~/.local/bin/claude`) starts at the saved level.
3. **`CLAUDE_CODE_EFFORT_LEVEL` stays unset at every scope.** It overrides every child's own effort, so a stage that asks for
   `low` or an agent whose definition says `medium` would run at `max` (cases E2 and E4 below), and its settings `env` entry is
   reapplied to sessions that are already running.
4. **Headless runs are unchanged.** A `claude -p` call keeps the saved level unless it passes `--effort` itself; the sealed
   measurement runs and every probe that pins a level stay as they are. An explicit `--effort <level>` always wins, so
   `claude --effort xhigh` is the one-word opt-out for a session.
5. **Children are unchanged.** Project agents declare `effort: max` and workflow stages pass `effort: 'max'`; a stage or an
   unnamed subagent that names none inherits the session's effort, now `max` for an interactive session.
6. **GitHub and cloud sessions:** a future Actions job on `claude-code-action` asks for max with `claude_args: '--effort max'`
   and relies on the committed project setting `ultracode: true`; on 2.1.284 that combination keeps Ultracode on (cases F1 and
   F5 measured it from the user settings), so the 2026-09-23 rule against `--effort max` beside Ultracode no longer applies.
   No Actions run was executed for this record.

Applied to this host on 2026-09-29: first as a 911-byte version, then replaced at about 02:22Z (the receipt's `recorded_at_utc`) by the repaired version
after the cross-family review below. The launcher went from 165 to 1,810 bytes (sha256 `22c2d518…0f45d26` to `f48eb134…0a2cd5`, mode
0755); the original and the first version stay beside it as `claude.bak-20260929-max-default` and `…-v1`. The native binary it execs is
`~/.local/bin/claude`, 2.1.284. `~/.claude/settings.json` was not touched (its sha256 was the same before and after every probe).

## Evidence

**Why the 2026-09-23 reasons no longer hold.** That record kept the coordinator at `xhigh` because a `max` session turned
Ultracode's orchestration off (P1 and P2, Claude Code 2.1.281). Primary sources fetched 2026-09-29 say otherwise for 2.1.284:

- [CHANGELOG 2.1.284](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md) (repository `main` at `dec92bc8`, latest release
  `v2.1.284` of 2026-09-28): "Changed Ultracode into its own toggle in `/effort` (Tab, or `/effort ultracode [on|off]`): it no
  longer forces xhigh effort and stays on at any effort level".
- [Settings reference, `ultracode`](https://code.claude.com/docs/en/settings-reference#ultracode): "The key doesn't change the
  session's effort level: ultracode runs at whichever level the session uses."
- The installed 2.1.284 binary's Ultracode gate is `function sKn(e){return Je().ultracode===!0||J$e(e)==="ultracode"}`: the
  setting or an ultracode choice, with no effort term (receipt, `binary_schema`).

**Why `max` cannot be saved and the variable is the wrong tool.**

- [Model configuration](https://code.claude.com/docs/en/model-config): "`max` isn't accepted as a level in either key" (`effortLevel`
  and `modelSettings`), and "Unless you set it through the `CLAUDE_CODE_EFFORT_LEVEL` environment variable, Claude Code applies
  `max` to the current session only." The installed schema agrees: both keys are `z(["low","medium","high","xhigh"]).optional().catch(void 0)`.
- [Environment variables](https://code.claude.com/docs/en/env-vars): the variable "Takes precedence over `--effort`, `/effort`, and
  the `modelSettings` and `effortLevel` settings", and values under a settings file's `env` key "are reapplied to a running
  session when the file changes".
- [`--effort`](https://code.claude.com/docs/en/model-config): "pass a level name to set it for a single session when launching
  Claude Code": the flag the launcher adds.
- Prior art for a flag-adding wrapper: `Ramsbaby/jarvis`, `infra/bin/claude-xhigh.sh` (blob `66e75106`, 1,536 bytes; the repository was
  pushed 2026-09-28 and is not archived; found by a GitHub code search on 2026-09-29, the only wrapper of this kind it returned)
  starts Claude Code with `--effort xhigh` for skills where reasoning depth is decisive. This launcher differs: it is the default
  `claude`, adds the flag only when nothing chose an effort, and checks the client version.
- No documented key sets a model's default effort: the binary's `defaultEffort` is a computed field of its model listing, and the
  docs name only an organization default for managed deployments.

**Measured on this host** (Claude Code 2.1.284; model and effort read from each transcript's own per-message record; every headless
row re-derived from the raw transcripts by an independent verifier, 17 of 17 matching; details and limits in the receipt):

| Case | Launch | Recorded effort | Ultracode reminder |
| --- | --- | --- | --- |
| C1, C2 | no flag, Sonnet 5.5 and Opus 5.5, host settings (saved `xhigh`, `ultracode: true`) | `xhigh`, `xhigh` | present |
| F1, F2 | `--effort max` | `max`, `max` | present |
| F3, F4 | `--effort max --effort low`, `--effort low --effort max` | `low`, `max` (the last flag wins) | present |
| F5 | `--effort max`; a Workflow with one stage naming no effort and one naming `low` | main `max`; stages `max` and `low` | present |
| F6, F7 | `--effort max`; an unnamed subagent, a project agent whose frontmatter says `medium` | `max`, `medium` | present |
| C3, C4 | `--effort max --settings '{"ultracode":false}'`, the same Workflow | `max`; stages `max` and `low` | absent |
| E1 to E4 | `CLAUDE_CODE_EFFORT_LEVEL=max` through the `--settings` env layer; the same children; an explicit `--effort low` | `max`; the `low` stage and the `medium` agent become `max`; `--effort low` becomes `max` | present |
| H1, H2 | Haiku 4.5 with and without `--effort max` | no effort field either way; exit 0, empty stderr | absent |
| I1 to I4 | interactive Sonnet 5.5 in a terminal through a login shell: no flag; the same session after `/effort xhigh`; `--effort xhigh`; `claude -p` in a terminal | `max`; `max` then `xhigh`; `xhigh`; `xhigh` | present |

The interactive cases ran through a login shell on the launcher installed on this host. A first version of the launcher passed the same
four cases (with the generated file ahead on `PATH` and again once installed) before a cross-family review sent it back for repair; the
repaired version was then installed and the four cases rerun, and those rows are the ones in the receipt. The Windows Terminal profile is reported to start `claude` through
`bash -lc "exec claude"` (its settings live on the Windows side and were not read here); a login shell on this host resolves
`claude` to the ecosystem launcher first. The repository tests pass: a 27-case table on real
pseudo-terminals (both bootstrap scripts; it includes the short-flag clusters `-pc` and `-cp`, `--`, empty and multi-line
arguments and clients from 2.1.281 to 3.0.1), nine broken launchers that the table must reject, and the two bootstrap modules
(the receipt records 241 tests, 32 skipped, exit 0 on the first head; the merged head's suites ran 290 tests with 33 skipped locally
and green in CI, which the receipt does not record).

**What the vendor and third-party measurements say about `max`** (sources read 2026-09-29 by a research workflow, then every claim
re-fetched by an independent verifier: 30 of 40 confirmed, 10 corrected as written here, none unsupported). The default rests on the
user's requirement, not on a measured gain on this repository's work; these are the numbers behind the caution.

- **Guidance.** The Anthropic guidance cited here does not recommend `max` as the general default for Sonnet 5.5 or Opus 5.5. The Claude
  Code model-configuration page says `max` "may show diminishing returns and is prone to overthinking, so test before adopting it
  broadly"; the platform effort page says, for Sonnet 5.5, "Use `xhigh` or `max` only where your evals show a quality gain" and, for
  Opus 5.5, "Run an effort sweep on your own evals". The Opus 5.5 system card (§§8.14.3 to 8.14.4, pp. 209 to 210) says `xhigh` achieves
  similar performance to `max` (GDPval-AA 1820 against 1846, AA-Briefcase 1780 against 1822) using about 51% fewer output tokens on
  GDPval-AA and 41% fewer on AA-Briefcase.
- **Sonnet 5.5 (this host's session model), `max` against `xhigh`.** Higher: Terminal-Bench 4.0 run by Anthropic in `--bare` mode
  (which skips automatic discovery of skills, subagents, plugins, MCP servers, hooks and `CLAUDE.md`) 70.6% against 61.5% ($12.54
  against $5.30 per attempt); the same benchmark in a third-party harness 63.6% against 57.1%
  (Artificial Analysis, on a pre-release deployment it says it will re-run); CursorBench 55.5 against 53.1 (the vendor's page: "small
  differences in scores may not be statistically meaningful"); GDPval-AA +119 Elo and AA-Briefcase +65 Elo, the latter with 95%
  intervals that do not overlap. **Lower:** FrontierCode v1.1 (Cognition, full Claude Code harness): Main 46.2% against 52.1% and
  Extended 59.1% against 64.4%, below `high` on both subsets. On Main `max` used about 12.6 times the tokens per task (the leaderboard
  data's `tokens` field: 595,651 against 47,385), $20.78 against $1.59 and 62 against 13 minutes; on Extended 474,549 against 37,536
  tokens, $16.29 against $1.24 and 51.7 against 10.4 minutes. 4.65% of the `max` Main runs and 3.37% of the Extended runs were flagged
  for unfair internet use and scored zero, against none at `xhigh`. Anthropic's launch page (footnote 2) reports that at `max`
  Sonnet 5.5 more often ran Claude Code's code-review skill, which splits the review across many subagents, and that in two cases
  Cognition examined this led to a timeout or to extra edits beyond the task's scope, and so to a lower score; it does not say how
  much of the aggregate loss those cases explain. Artificial Analysis calls `high` the most competitive Sonnet 5.5 setting on cost.
- **Opus 5.5, `max` against `xhigh`.** Gains vary by benchmark: Terminal-Bench 4.0 64.8% against 66.4% ("within noise" per
  Anthropic) and identical in the third-party harness; CursorBench 57.8 against 56.0; FrontierCode Main 54.4 against 51.4 (its best level
  is `medium`, 54.6) and an effective tie on Extended (63.58% against 63.53%, with `medium` and `high` above both); Zapier
  AutomationBench, with default fallbacks (refused tasks rerun through Anthropic's fallback routing), 42.47% against 35.77%, a gain of
  6.7 points or about 18.7% relative; AA-Briefcase +42 Elo. Cost per task 1.5 to 2.8 times. The card also reports that Opus 5.5 acted on
  instructions hidden in text a user pasted in about 2% of attempts at its default reasoning effort and about 7.4% at `max`, all
  blocked by product mitigations.
- **Reading (inference, not a measurement here).** For Sonnet 5.5 the direction of the effort effect differs between Terminal-Bench
  (Anthropic, `--bare`) and FrontierCode (Cognition, full Claude Code): `max` wins the first and loses the second. The two differ in
  benchmark, tasks and evaluation conditions, so these results do not isolate the effect of skills or subagents; Anthropic's own
  explanation for the second is the two-case footnote above. This host runs Sonnet 5.5 with skills, subagents, plugins and MCP servers
  loaded, which is closer to the full-client condition than to `--bare`. For Opus 5.5 the gains vary by benchmark and come at higher
  cost; their value for this repository remains unmeasured. The launcher makes the user's requirement the default and keeps
  `--effort xhigh` as the one-word opt-out until the sweep below reports.

## Other quality settings audited (2026-09-29)

A research unit compared 36 Claude Code settings, environment variables and behaviours that change the quality or completeness of
the model's work with the host's values (the docs and the 2.1.282 to 2.1.284 changelog as fetched, plus a bounded read of the
installed binary); an independent verifier re-fetched every row (31 confirmed, 5 corrected). Nothing else needs to change: the host
already holds the quality-preserving values (`CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1` and `switchModelsOnFlag: false`, the native
auto-compact default, `ultracode: true`, saved `xhigh` per model, no thinking-budget caps), and each 5.5 model's default maximum
output already equals its 128,000-token cap, so a `CLAUDE_CODE_MAX_OUTPUT_TOKENS` pin would change nothing. No settings file was
edited by this record. Levers left as the user's decisions, none applied:

- `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT=0` opts out of a server-side experiment that can shorten the system prompt; the client does not
  show whether it is on for these models, and the shorter prompt may be the better one.
- `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` (default 2048) truncates long MCP tool descriptions and server instructions; raising it
  restores them at a token cost that the token-efficiency measurements would notice.
- `availableModels` (rejected for this profile by the 2026-09-25 fallback-guard record), the advisor model (`opus` against Fable 5.1,
  an entitlement and cost choice) and `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` at user scope (1500 in the project settings only).

## Alternatives considered

- **`CLAUDE_CODE_EFFORT_LEVEL=max` in the settings `env` or the shell.** Rejected: measured to flatten every child's own effort
  (E2, E4) and to override an explicit `--effort` (E3); reapplied to running sessions when the file changes; the runbook of the
  sealed token-stack measurement run asserts at launch that the variable is unset.
- **Keep `xhigh` saved and do nothing else.** Rejected: contrary to the user's stated requirement of `max` for the main loop.
- **A saved `max` in `effortLevel` or `modelSettings`.** Not available: the schema drops it silently.
- **A shell alias in an rc file.** Rejected: the agents may not edit those files (user deny rules), and an alias is not expanded
  by `bash -lc "exec claude"`, the route the Windows Terminal profile takes.
- **A model catalog default.** Not available: no documented user-settable key; the binary's `defaultEffort` is derived.
- **Injecting `--effort max` into headless runs too.** Rejected: it would change every probe and measurement that relies on the
  saved level, and the sealed runs pin their own flags.
- **`/effort max` typed by hand each session.** Kept as the manual path; it is session-only and easy to forget.

## Coverage and limits

The default reaches every terminal launch that resolves `claude` to `$eco/bin/claude`. It does not reach the VS Code and
JetBrains extensions, the desktop app, the web client, a host whose bin directory is `~/.local/bin` (`install_native` writes no
launcher there), or a call of `~/.local/bin/claude` itself. A session that already runs is unchanged until it is restarted.
A re-run of either bootstrap script rewrites the launcher from the same text, so the change survives it.

## Overturn conditions

Revisit this record when any of these happens:

- Claude Code saves `max` in `effortLevel` or `modelSettings`: move the default to the saved per-model level and retire the
  launcher branch;
- a measured effort sweep on this repository's own tasks (the M7 arms of the
  [2026-09-28 sweep record](2026-09-28-community-sweep.md#amendments-to-the-2026-09-24-rows)) shows that `max` gives no gain, or a
  loss, for a model or role at higher cost: the result goes to the user as a recommendation, and this launcher then gains a
  per-model rule or is removed (it lowers no role by itself). That sweep should include Sonnet 5.5 at `xhigh` against `max` on
  this repository's change-and-review tasks in the full client, because the two Claude Code results for that model point in opposite
  directions (Terminal-Bench in `--bare` mode, FrontierCode in the full client);
- usage limits block work at `max`;
- `max` overthinking, or the extra subagent and skill activity the vendor reports at `max`, is observed to regress a gated result;
- a release changes how `--effort` interacts with Ultracode or with children's effort: repeat the probes in the receipt after
  every Claude Code upgrade before relying on this.

## Limitations

- **One host, one release.** The probes ran once each on one account with Claude Code 2.1.284. The interactive cases are one
  Sonnet 5.5 session each, driven through tmux.
- **The variable route was simulated** through the `--settings` env layer, not a shell export or the user settings file; the
  reapplication of settings `env` to running sessions is documented, not probed.
- **The Workflow tool result is only a launch receipt.** Execution of the Workflow cases is shown by the child transcripts, the
  workflow journal and the completion notification. The Ultracode reminder is an indicator, not proof of orchestration.
- **Answer quality was not measured here.** Nothing in this record shows that `max` improves results on this repository's work.
- **No Actions, IDE, desktop, web or macOS run.** The macOS launcher is generated by the identical function and tested against the
  same table in CI; a Mac session repeats the interactive check from the receipt.
- **Peer sessions' launches.** A pty or tmux probe that starts `claude` without `--effort` now starts at `max`; a probe that
  measures a default must pass `--effort` or use `-p`.

## Reviews

- **Cross-family review, one round (2026-09-29).** A read-only GPT-6 run (`codex exec -s read-only`, `gpt-6-astra`, effort max, live
  search) reviewed the launcher, its tests and the docs and returned five findings, each checked against source:
  1. single-dash clusters such as `-pc` and `-cp`, which the installed parser reads as print mode, still received the flag: fixed
     (`-p* | -[!-]*p*`; the first repair used a glob that missed `-pc`, and the new table caught it);
  2. `--` and an operand that equals an option name suppressed the default: `--` now ends the scan, and the value-taking-option
     case is a documented limit with a test that asserts the safe direction;
  3. both bootstrap pins were still 2.1.281, where `--effort max` turned orchestration off: the launcher now checks the client
     version and adds the flag only at 2.1.284 or newer (the pin floor moved separately, #477);
  4. the pty helper left a timed-out child running and could leak the slave descriptor: it now kills, reaps and closes on every
     path;
  5. the argument recorder was lossy for empty and multi-line arguments: the stub records JSON.
  One repair round followed; the reviewer's own suggestion (respect value-taking options) was not adopted because the launcher
  cannot know a client's option table. The probes and the receipt were regenerated on the repaired launcher, and the host file was
  replaced by the repaired version (the first version stays beside it as `claude.bak-20260929-max-default-v1`).
- **Cross-family fact-check of the vendor section (2026-09-29).** A second read-only GPT-6 run with live search (same flags) checked
  the section above against its sources and returned nine wording corrections (five low, four medium): a claim about "no Anthropic
  source", the `xhigh` token saving stated without the similar-performance context, the FrontierCode token, cost and time figures
  given for Main only, Anthropic's two-case footnote read as an aggregate explanation, "a tie" on Extended, the Zapier figures
  without their "default fallbacks" label, `--bare` described as loading nothing, "the two sweeps disagree" read as a controlled
  comparison, and "at best a small gain" for Opus 5.5. The coordinator re-fetched Cognition's `data.json`, Anthropic's Sonnet 5.5
  launch page and Zapier's leaderboard (version 1.0.6) for the figures and applied all nine. One suggestion, naming Cognition's
  `tokens` field as output tokens, could not be confirmed from the fetched sources, so the section says "the leaderboard data's
  `tokens` field".
- **Independent verification.** The vendor evidence (40 claims) and the settings audit (36 rows) were each re-checked by a second
  research agent that re-fetched every source: 30 and 31 confirmed, 10 and 5 corrected as written above, none unsupported. The
  seventeen headless probe rows were re-derived from the raw transcripts by a verifier with its own extraction code (17 of 17
  matched); the concerns it raised are in the receipt's limitations.

## Repository rule relocated verbatim (2026-10-05)

- This repository commits `.claude/settings.json` with Ultracode on and `effortLevel: xhigh`, the saved fallback for any model. A terminal session started through the ecosystem `claude` launcher runs the coordinator at `max` (the launcher adds `--effort max` only when nothing chose an effort and the client is 2.1.284 or newer; `claude --effort xhigh` opts out). On Claude Code 2.1.284 Ultracode stays on at any effort level and the `ultracode` setting sets none, so a `max` session keeps its workflow orchestration on; the `max` default rests on the user's requirement, not on a measured gain here. Headless `-p` runs pass `--effort` per call site, and `CLAUDE_CODE_EFFORT_LEVEL` stays unset at every scope (any value overrides every child's effort). Pass `effort: 'max'` with an explicit task-matched `model` on every ad-hoc workflow `agent()` call: a stage that names no effort runs at its agent's frontmatter effort, else at the effort the session was given explicitly (`--effort`, `/effort`, the model picker), else at its model's saved level or default, and one that names no model takes its definition's model, else `CLAUDE_CODE_SUBAGENT_MODEL` (`opus`), else the lead's. `opus` takes judgment; `sonnet` (Sonnet 5.5) takes fan-out units that an executable oracle or a later Opus stage checks (`examples/claude-native/workflows/README.md`, "Sonnet 5.5 fan-out units"). Probes and overturn conditions: `docs/decisions/2026-09-29-max-default-effort.md`, `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md` and `docs/decisions/2026-09-23-max-effort-default.md`.
