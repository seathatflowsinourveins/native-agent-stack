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
path is not recorded here (personal path).

**Rollback, one line:** copy the dated backup's `claude/`, `claude.json` and `codex/` back
over `~/.claude`, `~/.claude.json` and `~/.codex` (`apply_claude_settings.py` also left its
own timestamped `settings.json` backup alongside the live one).

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
continuity evidence than a single before/after pair.

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
API) since that file is a self-reported counter, not plugin logic:

| Plugin | Reviewed revision | Coordinator's observation | This session's fresh re-run |
| --- | --- | --- | --- |
| `context-mode@context-mode` | `6f0cc684` | ahead, `stats.json` only | still ahead, `stats.json` only (at a newer commit again — the plugin keeps self-updating that one file) |
| `claude-hud@claude-hud` | `ef5f1c8b` | exact match | exact match |
| `codex@openai-codex` | `db52e28f` | exact match | exact match |

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
- Top-level `status`: `prerequisites_missing` only because this profile's manifest entry
  declares `supported_platforms: ["linux-x86_64"]`; every individual command and recipe
  check underneath still reports present. This is a manifest-scoping gap, not a missing
  tool.

## Codex

Config read directly from this host's own `~/.codex/config.toml` in this session:
`approval_policy = "never"`, `sandbox_mode = "danger-full-access"`,
`features.daemon_auto_start = false`, `features.hooks = true`, and eight `[mcp_servers.*]`
entries (`ai-memory`, `context-mode`, `headroom`, `node_repl`, `openaiDeveloperDocs`,
`qmd`, `serena`, `socraticode`). The [codex host receipt](#host-receipts) below
independently cross-checks the live `codex features list` and `codex mcp list --json`
output against these same config.toml values rather than only reading the file.

`app-server-daemon` `updater.autoUpdateEnabled`: `false` (per the coordinator's report;
not independently re-checked in this session, since that setting lives under `CODEX_HOME`
outside the profile files this session read).

`shell_environment_policy.set` carries the pinned `PATH`, `RTK_TELEMETRY_DISABLED=1` and
`MCP_AUTO_OPEN_ENABLED=false` (per the coordinator's report).

RTK.md was inlined into `~/.codex/AGENTS.md` from a scratch-home `rtk init -g --codex`; the
generated unqualified Codex hook from that scratch run was not installed. 16
`[[skills.config]]` disable entries were added (all per the coordinator's report).

## Host value file

`adoption/hosts/mac-coordinator-64gb-20260925.json` was rendered from the measured
hardware profile, but it carries personal paths, so **it stays private and is not
committed**.

## Host receipts

Four receipts under
[`evidence/hosts/mac-coordinator-64gb-20260925/`](../../hosts/mac-coordinator-64gb-20260925/),
all `evidence_class: native_proven`, `stage: use`, `result: pass`, `layer_refs:
foundation/native-clients`, `second_physical_machine: true`:

| Receipt | Component / version run | What it backs |
| --- | --- | --- |
| [`...--claude-code--use--20260927.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927.json) | claude-code 2.1.283 | superseded once (see next row); version was only a flag here, not a retained command |
| [`...--claude-code--use--20260927-2.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927-2.json) | claude-code 2.1.283 | `command -v`/`readlink -f`/`--version`, a headless `claude -p` turn (random-fixture line-count positive control, matched) and `claude mcp list` (5 servers, all Connected) |
| [`...--codex--use--20260927.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927.json) | codex-cli 0.158.0-alpha.2.1 | superseded once (see next row); version was only a flag here, not a retained command |
| [`...--codex--use--20260927-2.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927-2.json) | codex-cli 0.158.0-alpha.2.1 | version/channel check, `codex exec --skip-git-repo-check --sandbox read-only --ephemeral` (random-fixture positive control via a real `command_execution` event, matched), `codex mcp list --json` and `codex features list` cross-checked live against `config.toml` |

Both installed builds are newer than the current catalog pins (claude-code 2.1.278, codex
0.155.1), so both receipts use `--allow-unbound-version` and do not by themselves change
either component's `macos-arm64` `platform_status` (still `untested`); that needs
independent review plus the matrix flip rule in
[`docs/component-evidence-matrix.md`](../../../docs/component-evidence-matrix.md).

Two findings surfaced while recording the codex receipt, backed by the receipt's own
retained commands:

- **Distribution channel.** `~/.local/bin/codex` is a POSIX shell script whose own comment
  says it runs "the ChatGPT-bundled Codex through the app's declared entrypoint"; the
  tested `codex-cli 0.158.0-alpha.2.1` is the ChatGPT desktop app's bundled build, not a
  separately downloaded `openai/codex` release. The receipt shows this with a file-type
  line and a redacted reference count, not the launcher's contents.
- **`codex exec` needs `< /dev/null`.** Without redirected stdin, `codex exec` blocks
  indefinitely on "Reading additional input from stdin..." before doing any work, on this
  host and this codex-cli build, even for a prompt passed as a CLI argument with no `-`
  and no piped stdin. Every exec command in the receipt redirects stdin from `/dev/null`.

## macOS template findings

From the coordinator's Stage 1 run, plus this session's own checks where noted:

- The settings template's ai-memory 2.4.1 hooks were not merged; the live hooks reach the
  running ai-memory 19b6429 build and its own store instead.
- The rtk hook is wired (independently confirmed in this session: Claude's `PreToolUse`
  `Bash` matcher runs `rtk hook claude`) and needs rtk >= 0.50.0 plus a five-entry
  `exclude_commands` list. This session's own check found **both** rtk builds present on
  this host: a `mise`-managed install at 0.49.0, and the ecosystem install at 0.50.0
  (`~/.local/share/codex-ecosystem/bin/rtk`, itself a symlink into a `-staging` tree). Since
  `~/.claude/settings.json`'s `env.PATH` lists the ecosystem `bin` directory before
  `.local/bin`, hooks that Claude Code runs (including `rtk hook claude`) resolve rtk
  0.50.0; a plain interactive shell without that override resolves the mise-managed 0.49.0.
  The "done here" therefore holds for hook execution specifically, not for every possible
  invocation of the bare `rtk` command on this host.
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
- The two pre-existing agent-ecosystem agents (`ecosystem-researcher`, `ecosystem-worker`)
  fail the workflow contract's tools-allowlist checks.
- User-scope workflows need absolute contract paths, which `test-contract-mutations`
  rejects.
- `secret_path_guard` false-positives on Python `set(` inside a Bash heredoc.
- iTerm2 is not installed; Ghostty is, the documented alternative. `/terminal-setup` is
  left to the operator.

## Limits

- This document and its two `-2` receipts are the evidence-PR session's own work; the
  client-layer install itself (backup, agents/guard/MCP install, settings render/apply,
  skills/plugins/workflows, Codex wiring) was performed by the coordinator session and is
  reported here from its retained outputs, not re-run end to end by this session. Where a
  line was independently re-checked here, it says so above.
- Both host receipts carry only the recorder's self-review; `accepted` needs an
  independent review from a separate session (requested in the PR).
- No `platform_status` is changed by this PR. `adoption/manifest.json`'s macOS platform
  profile status is a separate, maintainer-judgment field this PR does not touch.
- Counts, booleans and file names only: no session id, uuid, working-directory path, MCP
  server command/args/env, or personal path appears in this document or in either
  receipt's retained command output.
