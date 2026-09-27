# Stage 1 client layer on mac-coordinator-64gb-20260925 (2026-09-27)

Host request [#382](https://github.com/seathatflowsinourveins/native-agent-stack/issues/382):
native-agent-stack becomes this Mac's client-layer writer (Stage 1 of the
[2026-09-27 staged decision](../../../docs/decisions/2026-09-27-mac-single-writer-staged.md)),
with no running service touched. The coordinator session applied the client layer on this
Mac; this document and the [host receipts](#host-receipts) below are the evidence PR for
that work. Facts below are sanitized to names, counts and booleans; where a line was
independently re-run in this evidence-PR session rather than only read from the
coordinator's retained output, it says so.

## Backup and rollback

Before any write, the coordinator copied `~/.claude` and `~/.codex` (settings, hooks,
plugins, skills, agents) to a private, dated, `0700` folder outside every worktree: 4,516
files, manifest sha256 `a7478603be747dfd52a18dd05f4f0d80510af5bd736c7af4581c0e7cd6b2c5c4`.
`auth.json`, transcripts, sessions, history and caches were excluded. The backup folder's
path is not recorded here (personal path). **Not confirmed by this session:** whether the
4,516-file manifest also covers `~/.claude.json` (a separate file, not under `~/.claude`,
that holds the user-scope MCP registration Stage 1 changed) is not stated in the
coordinator's report, and this session did not re-hash the private manifest to check either
way.

**Rollback (unrehearsed on this host; replaces Stage 1's additions instead of merging over
them):**

```sh
mv ~/.claude ~/.claude.pre-rollback && mv ~/.codex ~/.codex.pre-rollback
rsync -a --delete \
  --exclude 'auth.json' --exclude 'transcripts/' --exclude 'sessions/' \
  --exclude 'history*' --exclude '*cache*' \
  "<dated-backup>/claude/" ~/.claude/
rsync -a --delete "<dated-backup>/codex/" ~/.codex/
# ~/.claude.json: restore from the backup only once it is confirmed to be in the manifest
# (see above); otherwise leave the live ~/.claude.json alone.
cp ~/.claude.pre-rollback/auth.json ~/.claude/auth.json 2>/dev/null
rsync -a ~/.claude.pre-rollback/transcripts/ ~/.claude/transcripts/ 2>/dev/null
rsync -a ~/.claude.pre-rollback/sessions/ ~/.claude/sessions/ 2>/dev/null
rm -rf ~/.claude.pre-rollback ~/.codex.pre-rollback
```

The previous one-line "copy the backup's files back over `~/.claude`/`~/.codex`" merges
rather than replaces: Stage 1 added agents, guard hooks, skills, plugins and workflows (see
below), and a copy-over leaves every one of those additions in place, so following it would
not actually undo Stage 1. The `rsync --delete` form above removes what Stage 1 added while
keeping the excluded files. `apply_claude_settings.py` also left its own timestamped
`settings.json` backup alongside the live one, independent of the manifest above.

## Service continuity

`launchctl list | grep -E 'agent-ecosystem|native-stack'` before and after the Stage 1
work showed the same four labels, unchanged:

| Label | Before | After | This session, live |
| --- | --- | --- | --- |
| `local.agent-ecosystem.ai-memory` | PID present, last exit 0 | PID present, last exit 0 | same PID, last exit 0 |
| `local.agent-ecosystem.maintenance` | not running, last exit 1 | not running, last exit 1 | not running, last exit 1 |
| `local.agent-ecosystem.ollama` | PID present, last exit 0 | PID present, last exit 0 | same PID, last exit 0 |
| `local.agent-ecosystem.qdrant` | PID present, last exit 0 | PID present, last exit 0 | same PID, last exit 0 |

No `local.agent-ecosystem.*` service or Ollama was stopped, replaced or duplicated. This
session independently re-ran `launchctl list | grep -E 'agent-ecosystem|native-stack'`
while preparing this PR (over an hour after the coordinator's "after" capture): all three
running PIDs were still the exact same PIDs as both the "before" and "after" captures, and
`maintenance` was still not running with the same last exit code, which is stronger
continuity evidence than a single before/after pair. The "Before" and "After" columns above
are the coordinator's own captures, relayed here and not independently re-verifiable by this
session (the same situation as the backup manifest above); only the "This session, live"
column is something this session directly watched happen. See the PR's evidence-class
table: this claim is `source_review` overall, not `native_proven`, for exactly that reason.

## Headless read-back (names and counts only)

A headless `claude -p --output-format stream-json --verbose` turn from a scratch working
directory, parsed for its `init` event:

- `permissionMode`: `bypassPermissions`; `model`: `claude-opus-5-5[1m]`
- agents: 18; skills: 67; plugins: 11; MCP servers: 5 (all `connected`); slash commands: 107; tools: 118

This session's own [claude-code host receipt](#host-receipts) independently reproduced the
same shape (18/67/11/5-connected/107/118) from a fresh scratch turn, so the counts are
reproducible, not a one-off capture.

## Plugin revision check

Compares each installed plugin's `installed_plugins.json` `gitCommitSha` against the
revision `recipes/README.md` names as reviewed, allowing "ahead of the reviewed revision
in `stats.json` only" (confirmed by diffing the two revisions through the GitHub compare
API) since that file is a self-reported counter, not plugin logic. Neither the
coordinator's check nor this evidence-PR session's first re-run recorded the installed
`gitCommitSha` or the compare API's `{status, files}` result (`adoption/bootstrap.md`
step 4a asks for both); a later review-fix pass records them for the first time in the
rightmost column below. This whole claim is `source_review`, not `native_proven`:

| Plugin | Reviewed revision | Coordinator's observation | Evidence-PR session's re-run | Review-fix pass (2026-09-27): installed SHA + compare API |
| --- | --- | --- | --- | --- |
| `context-mode@context-mode` | `6f0cc6841c687e754059f36714a11233fda1a02b` | ahead, `stats.json` only (SHA not retained) | still ahead, `stats.json` only, at a newer commit again — the plugin keeps self-updating that one file (SHA not retained) | installed `a2fda46b3cb82753f8c2d67953c881a0dd48b648`; `gh api repos/mksglu/context-mode/compare/6f0cc6841c687e754059f36714a11233fda1a02b...a2fda46b3cb82753f8c2d67953c881a0dd48b648` returned `{"status":"ahead","files":["stats.json"]}` |
| `claude-hud@claude-hud` | `ef5f1c8b167572ad1443c70629763ea8780af96b` | exact match (SHA not retained) | exact match (SHA not retained) | installed `ef5f1c8b167572ad1443c70629763ea8780af96b` — exact match, no compare call needed |
| `codex@openai-codex` | `db52e28f4d9ded852ab3942cea316258ae4ef346` | exact match (SHA not retained) | exact match (SHA not retained) | installed `db52e28f4d9ded852ab3942cea316258ae4ef346` — exact match, no compare call needed |

Three checks at three different times on this host saw three different `context-mode`
installed revisions, each "ahead, `stats.json` only" of the reviewed revision: the plugin's
marketplace tracks its default branch, not a pin, so this result holds only for the moment
each check was taken, not as a standing fact about the install.

## Skills

`DISABLE_TELEMETRY=1 python3 scripts/skills_status.py --skills-bin <ecosystem skills
binary>`: **ok, 28/28**.

## Token-efficiency / client-wiring coverage

`scripts/adoption_status.py --profile token-efficiency --client-wiring --json`, with the
ecosystem tool prefix first on `PATH`:

- `profiles[token-efficiency].status`: `prerequisites_present` (all 13 profile commands and
  4 recipes present).
- `client_wiring.complete`: `true` (Claude: rtk hook wired, ai-memory hook events present,
  context-mode plugin enabled, subagent-spawn depth and workflow concurrency set, no
  `CLAUDE_CODE_EFFORT_LEVEL` override, agent-teams off; Codex: rtk instructions present,
  context-mode plugin enabled, `serena`/`socraticode`/`ai-memory` all registered, hooks
  feature on with matching trusted-hash counts).
- Top-level `status`: `prerequisites_missing` only because `adoption/manifest.json`'s
  `supported_platforms` (manifest-wide, not per-profile: linux/x86_64/Python 3.13) does not
  match this macOS arm64 host; every individual command and recipe check for this profile
  still reports present. This is the manifest's stated intended platform for now — macOS is
  separately `drafted_not_accepted` in the same manifest's `platform_profiles` — not a
  per-profile scoping gap and not a missing tool. Run with
  `uv run --no-project --python 3.13 python scripts/adoption_status.py ...` per
  [bootstrap.md](../../../adoption/bootstrap.md) step 6, matching the manifest's Python.

## Codex

Config read directly from this host's own `~/.codex/config.toml` in this session:
`approval_policy = "never"`, `sandbox_mode = "danger-full-access"`,
`features.daemon_auto_start = false`, `features.hooks = true`. These four values are
`source_review` (a direct file read, not a live check): no command in either codex receipt
checks `approval_policy` or `sandbox_mode` live, and the codex receipt's own exec turn
explicitly runs under `--sandbox read-only`, not `danger-full-access`, so this README does
not claim those two as `native_proven`. `features.daemon_auto_start`/`features.hooks` *are*
cross-checked live by the [codex host receipt](#host-receipts) below (`codex features list`
against config.toml).

**MCP servers: config.toml declares eight, the live surface has ten.** `config.toml` has
eight `[mcp_servers.*]` tables (`ai-memory`, `context-mode`, `headroom`, `node_repl`,
`openaiDeveloperDocs`, `qmd`, `serena`, `socraticode`); the codex receipt's own
`codex mcp list --json` check confirms all eight are present live (`declared` is a subset
of `live`, which gates the command's exit code), but the live listing also has two servers
`config.toml` does not declare: `cua_repl` (enabled) and `codex_app` (disabled), both
printed by the receipt as `live_only_not_in_config_toml`. Each comes from a Codex plugin
enabled in `config.toml`'s `[plugins."*@*"]` tables (`unified-computer-use@openai-bundled`
and `codex-app-tools@openai-bundled` respectively; each plugin's own `.mcp.json` under
`~/.codex/plugins/cache/openai-bundled/` declares its server), installed from the ChatGPT
desktop app's bundled `openai-bundled` marketplace, not from this repository's Stage 1
install. `config.toml` enables 13 plugins in total (its `[plugins."*@*"]` entries), including
`unified-computer-use`, `computer-use`, `chrome` and `browser`; every Codex turn on this
host — including a `codex exec --sandbox read-only` receipt command — has these
plugin-provided tools available under `approval_policy = "never"`, since the read-only
sandbox restricts shell commands, not plugin tools. Whether this extra surface is accepted
for a never/danger-full-access profile is an open question for the owner, not decided here;
this README previously described the live listing as matching config.toml, which undercounted
it, and no longer does.

`app-server-daemon` `updater.autoUpdateEnabled`: `false` (per the coordinator's report; not
independently re-checked in this session, since that setting lives under `CODEX_HOME`
outside the profile files this session read; stays `source_review` and unverified by any
receipt — the codex receipt proves only `features.daemon_auto_start = false`, a different
setting).

`shell_environment_policy.set` carries the pinned `PATH`, `RTK_TELEMETRY_DISABLED=1` and
`MCP_AUTO_OPEN_ENABLED=false` (per the coordinator's report).

RTK.md was inlined into `~/.codex/AGENTS.md` from a scratch-home `rtk init -g --codex`; the
generated unqualified Codex hook from that scratch run was not installed. 16
`[[skills.config]]` disable entries were added (all per the coordinator's report).

The Codex binary every command above runs, `~/.local/bin/codex`, is a launcher into the
ChatGPT desktop app's bundled build (see "Distribution channel" below); an app update can
replace it with no receipt, independent of `features.daemon_auto_start` or the updater
setting above. Not remedied here; a pinned, separately downloaded `openai/codex` release
placed first on `PATH` would close this gap.

## Cross-host coordination

The coordinator applied two settings from
[Remote Control](https://code.claude.com/docs/en/remote-control) and
[cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), both at
**user scope** (`~/.claude/settings.json`, so every session on this Mac, not only the
coordinator's): `remoteControlAtStartup: true` and `crossSessionInbound: "accept"`. The same
user-scope settings file also sets `defaultMode: "bypassPermissions"` and
`skipDangerousModePermissionPrompt: true`; no `isolatePeerMachines` key is set (this README
does not describe what that key does; see the Claude Code docs above for that).

The [Stage 1 decision record](../../../docs/decisions/2026-09-27-mac-single-writer-staged.md)
approves `crossSessionInbound: "accept"` on the premise that "a message cannot approve a
prompt, change configuration or run a command, and each host's own permissions apply." On
this host, every session currently runs under `bypassPermissions`, so "each host's own
permissions" means an idle session that receives a message starts a new model turn (per
[the cooperation recipe](../../../recipes/claude-native-ultracode.md)) whose Bash, Write and
MCP calls then run with no prompt. This is disclosed here as the applied configuration and
its interaction with the profile's permission mode, not as a recommendation. The owner has
approved `crossSessionInbound: "accept"`; either confirming the accepted risk in the
decision record or scoping it to only the participating sessions (the recipe's own
guidance — opt in per session with `claude --settings
'{"crossSessionInbound":"accept"}'` rather than user-wide) is an open decision for the
owner, not resolved by this PR. This claim (the applied values and their scope) is
`source_review`: read directly from `~/.claude/settings.json` in this session, not exercised
by a receipt.

## Host value file

`adoption/hosts/mac-coordinator-64gb-20260925.json` was rendered from the measured
hardware profile, but it carries personal paths, so **it stays private and is not
committed**.

## Host receipts

Six receipts under
[`evidence/hosts/mac-coordinator-64gb-20260925/`](../../hosts/mac-coordinator-64gb-20260925/),
all `evidence_class: native_proven`, `stage: use`, `result: pass`, `layer_refs:
foundation/native-clients`, `second_physical_machine: true`. Each component's `-3` generation
supersedes `-2`, which supersedes the original; only the `-3` file is current evidence, and
the schema keeps the earlier generations byte-identical rather than deleting them:

| Receipt | Component / version run | What it backs |
| --- | --- | --- |
| [`...--claude-code--use--20260927.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927.json) | claude-code 2.1.283 | superseded twice; version was only a flag here, not a retained command |
| [`...--claude-code--use--20260927-2.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927-2.json) | claude-code 2.1.283 | superseded by `-3` (review findings: the claim asserted a Read-tool check and a `claude mcp list` failure-mode the commands did not perform; see below) |
| [`...--claude-code--use--20260927-3.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927-3.json) | claude-code 2.1.283 | `command -v`/`readlink -f`/`--version`; a headless `claude -p` turn (random-fixture line-count positive control, matched, plus an in-transcript negative control on a deliberately wrong count, correctly rejected) that also scans the transcript's own `tool_use` events and fails unless a `Read` call is present; and a `claude mcp list` whose own exit code is captured with no shell pipe, failing unless it is 0 and every reported server's status contains `Connected` (5 servers, all Connected) |
| [`...--codex--use--20260927.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927.json) | codex-cli 0.158.0-alpha.2.1 | superseded twice; version was only a flag here, not a retained command |
| [`...--codex--use--20260927-2.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927-2.json) | codex-cli 0.158.0-alpha.2.1 | superseded by `-3` (review findings: the version-check command's exit code was actually a later `echo`'s, not `codex --version`'s; the claim named a specific model command that was not checked; `approval_policy`/`sandbox_mode` were claimed without a live check; the mcp-list check's summary line and two live-only servers fell outside the 400-char excerpt; see below) |
| [`...--codex--use--20260927-3.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927-3.json) | codex-cli 0.158.0-alpha.2.1 | version/channel check whose exit code is now `codex --version`'s own; `codex exec --skip-git-repo-check --sandbox read-only --ephemeral` (random-fixture positive control via a real `command_execution` event, matched — the event's own command text is captured and printed rather than assumed — plus an in-transcript negative control on a deliberately wrong count, correctly rejected); `codex mcp list --json` (declared ⊆ live gates the exit code; the summary line now prints first, and any live-only server is disclosed, not a failure — this run: `cua_repl`, `codex_app`); `codex features list` cross-checked live against `config.toml`. No longer claims `approval_policy`/`sandbox_mode` (see Codex section above) |

Both installed builds are newer than the current catalog pins (claude-code 2.1.278, codex
0.155.1), so all four `-2`/`-3` receipts use `--allow-unbound-version` and do not by
themselves change either component's `macos-arm64` `platform_status` (still `untested`);
that needs independent review plus the matrix flip rule in
[`docs/component-evidence-matrix.md`](../../../docs/component-evidence-matrix.md).

**A compliant independent review of these receipts cannot return `agree`, by construction,
and this PR's merge does not wait on that being fixed.** `docs/contributing-evidence.md`'s
four review points include "bound to the winner": the receipt's `tool_versions` must match
the landscape winner's pin. Both `-3` receipts are `--allow-unbound-version` (point 3
above), and the tested codex is the ChatGPT app's bundled alpha build, which cannot bind to
an `openai/codex` release pin at all. So a review that adequacy-checks all four points must
record `needs_changes` on point 4, which — per `contributing-evidence.md` — withholds
`accepted` regardless of the other three points. The Opus same-host review and the
workstation's GPT-6 cross-family review requested in this PR's Review section can only
adequacy-check points 1-3 (layer role, positive control, backed claims); point 4 fails by
construction, so these receipts stay informational and are not expected to reach `accepted`
through this PR. The route to bound, `accepted`-eligible evidence is either installing the
pinned official `claude-code` 2.1.278 and `openai/codex` 0.155.1 releases and re-recording,
or moving the landscape pins forward through the re-record process in
`docs/contributing-evidence.md` section 4.

Two findings surfaced while recording the codex receipt, from this session's own
observation, not all backed by a retained command:

- **Distribution channel** (backed by the receipt's own retained command 1).
  `~/.local/bin/codex` is a POSIX shell script whose own comment says it runs "the
  ChatGPT-bundled Codex through the app's declared entrypoint"; the tested
  `codex-cli 0.158.0-alpha.2.1` is the ChatGPT desktop app's bundled build, not a separately
  downloaded `openai/codex` release. The receipt shows this with a file-type line and a
  redacted reference count, not the launcher's contents.
- **`codex exec` needs `< /dev/null`** (an unretained observation from this session, not a
  new finding: no retained command in either receipt generation runs `codex exec` without
  `< /dev/null` to show the alternative). Without redirected stdin, `codex exec` blocks
  indefinitely on "Reading additional input from stdin...". This is documented upstream
  behavior, not new to this host or this codex-cli build:
  [`evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/README.md`](../gap-wave2-20260923/foundation__quality-evaluation/README.md)
  traces the same blocking `read_to_end` on stdin to `codex-cli` 0.155.1's own
  `resolve_root_prompt` (tag `rust-v0.155.1`, `codex-rs/exec/src/lib.rs`). Every exec command
  in both receipts already redirects stdin from `/dev/null`.

## macOS template findings

From the coordinator's Stage 1 run, plus this session's own checks where noted:

- The settings template's ai-memory 2.4.1 hooks were not merged; the live hooks reach the
  running ai-memory 19b6429 build and its own store instead.
- The rtk hook is wired (independently confirmed in this session: Claude's `PreToolUse`
  `Bash` matcher runs `rtk hook claude`) and needs rtk >= 0.50.0 plus a five-entry
  `exclude_commands` list. This session's own check found **both** rtk builds present on
  this host: a `mise`-managed install at 0.49.0, and the ecosystem install at 0.50.0
  (`~/.local/share/codex-ecosystem/bin/rtk`, itself a symlink into a `-staging` tree). A
  plain interactive shell resolves the mise-managed 0.49.0. This session read
  `~/.claude/settings.json`'s own `env.PATH` value and re-ran `command -v rtk`/`rtk
  --version` with exactly that `PATH` (the environment Claude Code gives its hooks,
  including `rtk hook claude`): it resolves to the ecosystem install and reports **rtk
  0.50.0**, confirming the "done here" holds for hook execution specifically, not for
  every possible invocation of the bare `rtk` command on this host.
- The context-mode cache-heal hook is registered by the plugin itself, not by the settings
  template.
- The Qdrant URL wired into this profile is `127.0.0.1:6333` (independently confirmed in
  this session via `codex mcp list --json`'s `socraticode` entry), not the template's
  `16333`.
- No Homebrew on this host.
- No OTel collector is running yet, so telemetry exports fail silently.
- `mcp_oauth_credentials_store` was left at its default.
- `codebase-memory` has no macOS pin.
- The user-scope context-mode MCP registration duplicated the plugin's own server and was
  removed.
- The two pre-existing `local.agent-ecosystem` agents (user scope, `~/.claude/agents/`, not
  tracked in this repository and predating this PR) fail the tools-allowlist rules this
  repository's own `test-envelope.mjs` holds its project agents to: `ecosystem-worker.md`
  has `isolation: worktree` and no `tools:` line at all, so (per Claude Code's documented
  subagent behavior) it inherits every tool, including Serena's symbol-edit tools that
  `docs/decisions/2026-09-26-stack-agents-role-dispatch.md` deliberately withheld from
  `isolated-builder` for the same worktree-isolation reason; `ecosystem-researcher.md`
  grants `Bash`, `WebFetch`, `WebSearch` and the wildcard `mcp__openaiDeveloperDocs__*` (a
  bare-server wildcard, not an explicit per-tool grant), where the role table excludes
  `WebFetch`. Both run under this profile's `bypassPermissions` default, so neither prompts
  before using these tools. Tracked as
  [#394](https://github.com/seathatflowsinourveins/native-agent-stack/issues/394); not
  fixed by this PR, since neither file is in this repository's diff.
- User-scope workflows need absolute contract paths, which `test-contract-mutations`
  rejects.
- `secret_path_guard` false-positives on Python `set(` inside a Bash heredoc.
- iTerm2 is not installed; Ghostty is, the documented alternative. `/terminal-setup` is
  left to the operator.

## Limits

- This document and its `-2`/`-3` receipts are the evidence-PR session's own work (the
  `-3` generations were recorded in a later, review-fix pass on 2026-09-27, applying this
  PR's own review findings); the client-layer install itself (backup, agents/guard/MCP
  install, settings render/apply, skills/plugins/workflows, Codex wiring) was performed by
  the coordinator session and is reported here from its retained outputs, not re-run end to
  end by this session. Where a line was independently re-checked here, it says so above.
- All four current receipts (`-2` superseded, `-3` current, per component) carry only the
  recorder's self-review; `accepted` needs an independent review from a separate session
  (requested in the PR). See "Host receipts" above: a compliant review of the `-3`
  generations cannot return `agree` regardless, because both are `--allow-unbound-version`.
- No `platform_status` is changed by this PR. `adoption/manifest.json`'s macOS platform
  profile status is a separate, maintainer-judgment field this PR does not touch.
- Counts, booleans, file names and (in the `-3` receipts) tool names and one sanitized
  shell command line appear; no session id, uuid, working-directory path, MCP server
  command/args/env, or personal path appears in this document or in any receipt's retained
  command output (the `-3` receipts replace the scratch directory with `<scratch>` in the
  one command line they print).
- Host request [#382](https://github.com/seathatflowsinourveins/native-agent-stack/issues/382)
  still carries the `request:blocked` label as of this PR. Its status comment (written by
  `scripts/host_requests.py`, updated 2026-09-27T05:08:09Z) gives the reason: "Claude Code's
  auto-mode classifier refused `install_claude_profile.py` as Self-Modification: this
  session may not write its own `~/.claude` or `~/.codex` until the user adds a permission
  rule or gives an explicit, specific approval," noting only the private backup as done
  before that block. The receipts and live host state in this PR show the agents, hooks,
  skills, plugins, MCP servers and Codex config this classifier initially refused to write
  are now present and working, so the block was evidently resolved on a later attempt (most
  plausibly the "explicit, specific approval" the message names), but this session did not
  witness that and the issue's label was never updated to reflect it. Reconciling the label
  with the outcome is for the coordinator or a maintainer, not decided here.
