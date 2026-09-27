# Stage 1 client layer on mac-coordinator-64gb-20260925 (2026-09-27)

Host request [#382](https://github.com/seathatflowsinourveins/native-agent-stack/issues/382):
native-agent-stack becomes this Mac's client-layer writer (Stage 1 of the
[2026-09-27 staged decision](../../../docs/decisions/2026-09-27-mac-single-writer-staged.md)).
Stage 1's own install steps stopped, restarted, reconfigured or replaced no
`local.agent-ecosystem.*` service or Ollama (see "Service continuity" below) — narrower than
"no running service touched": every receipt's model turn below is a real client turn on
this host's live, already-running `ai-memory` service, and does write to it (see
"Memory-store writes during recording"). The coordinator session applied the client layer
on this Mac; this document and the [host receipts](#host-receipts) below are the evidence
PR for that work. **The coordinator session and this evidence-PR session are the same
Claude Code session** (every receipt below, from the coordinator's original recordings
through this PR's own, carries the identical `recorded_by.identity_sha256`): where this
document says a line was re-run or reproduced in "this session" at a later point, that is
this same session corroborating its own earlier observation over time, not a second,
independent observer — see "Host receipts" below and the PR's Review section for what an
independent review of this evidence still requires. Facts below are sanitized to names,
counts and booleans; where a line was re-run in this session, later, rather than only read
from an earlier retained capture, it says so.

## Backup and rollback

Before any write, the coordinator copied `~/.claude` and `~/.codex` (settings, hooks,
plugins, skills, agents) to a private, dated, `0700` folder outside every worktree: 4,516
files, manifest sha256 `a7478603be747dfd52a18dd05f4f0d80510af5bd736c7af4581c0e7cd6b2c5c4`.
The backup folder's path is not recorded here (personal path).

**Never in the backup, and never touched by either step below:** credentials (the Codex
credential store `~/.codex/auth.json`; Claude Code's own native credential store, not a file
this backup or rollback names), transcripts, sessions, history files or caches, for both
clients. Neither step deletes any of these: the removal step immediately below runs `rm` (or
`skills remove`) only on the specific Stage 1 files and skills its table names, never on a
credential, transcript, session, history or cache path; the restore step further below runs
no `rm` or `rsync --delete` at all (see the note at that step).

**Order: removal first, then restore — not the reverse.** The two steps undo different
things. Removal deletes what Stage 1 *added*: files and registrations the backup, by
construction, never held a prior copy of, so restoring cannot touch them. Restore overwrites
live files with the backup's pre-Stage-1 copies (settings.json, config.toml, and so on) *in
place*. Running restore first would rewrite exactly the live state — hook and MCP
registrations, config values — that the removal table below was built from by reading this
host, before removal has used that state to confirm exactly what is still there to delete;
doing removal first, while that state is still live, avoids masking it. This is also the
order the two steps appear in below.

### Removal (what Stage 1 added)

Undo each with its own native command (all read-only to verify first: `claude plugin list`,
`claude mcp list`, `codex mcp list`, `codex plugin list`):

| Stage 1 addition | Native removal |
| --- | --- |
| The 10 catalog agents ([`adoption/agents/claude/`](../../../adoption/agents/claude/)) under `~/.claude/agents/` | `rm ~/.claude/agents/{blind-adjudicator,blind-judge,blind-lane-reviewer,evidence-reviewer,isolated-builder,security-reviewer,semantic-evidence-reviewer,source-scout,stack-researcher,stack-verifier}.md` |
| Two guard hooks under `~/.claude/hooks/` — of the four files [`tools/adoption/install_claude_profile.py`](../../../tools/adoption/install_claude_profile.py)'s `HOOKS` map (lines 48-53) can place; see note below | `rm ~/.claude/hooks/secret_path_guard.py`; `rm ~/.claude/hooks/effort-default-guard.py` (their `hooks` entries in `settings.json` go with the settings restore below) |
| Every file under `~/.claude/workflows/` (13 files; see note below) — never the directory itself | one `rm` per file, listed below |
| The `context-mode`, `claude-hud` and `codex` Claude plugins | `claude plugin uninstall context-mode@context-mode`, `claude plugin uninstall claude-hud@claude-hud`, `claude plugin uninstall codex@openai-codex` |
| The `serena` user-scope Claude MCP registration | `claude mcp remove serena -s user` |
| The Codex MCP servers `serena`, `headroom` and `qmd` | `codex mcp remove serena`, `codex mcp remove headroom`, `codex mcp remove qmd` |
| The Codex `context-mode` plugin | `codex plugin remove context-mode@context-mode` |
| `~/.codex/RTK.md` | `rm ~/.codex/RTK.md` (the inline RTK block this file's text was copied into, inside `~/.codex/AGENTS.md` — a pre-existing file, see "Codex" below — needs manual editing to remove; deleting `AGENTS.md` itself would remove more than Stage 1 added) |
| The `updater.autoUpdateEnabled` key this session wrote into `~/.codex/app-server-daemon/settings.json` (whether the file existed before Stage 1 is not recorded; see note below) | conditional, not a blind `rm` — see note below |
| The 28 skills pinned in [`adoption/skills/manifest.json`](../../../adoption/skills/manifest.json), the skills@1.7.0 manifest Stage 1 installed | one `skills remove <name> -g -y` per skill, listed below |

**Hooks.** The `HOOKS` map names four files it can place under `~/.claude/hooks/`:
`effort-default-guard.py`, `secret_path_guard.py`, `token-lanes-block.md` and
`token-lanes-subagent-start.py`. Only the first two exist on this host (sha256-verified equal
to their repository source, `adoption/hooks/claude/effort-default-guard.py` and
`scripts/hooks/secret_path_guard.py`); the other two were added to that map by
[#378](https://github.com/seathatflowsinourveins/native-agent-stack/issues/378)
(`0c33b37a`) after Stage 1's own install ran on this host, so there is nothing to remove for
them here. A third file also lives in `~/.claude/hooks/`, `context-mode-cache-heal.mjs` —
that one is not this installer's own: per the [macOS template findings](#macos-template-findings)
above, it is registered by the `context-mode` plugin itself, and goes with that plugin's own
removal command in the table above, not with these two.

**`~/.claude/workflows/`.** `ls -la ~/.claude/workflows` lists 13 files. Compared by name and
sha256 against this repository's own
[`examples/claude-native/workflows/`](../../../examples/claude-native/workflows) (whose own
`README.md` and `SHA256SUMS` are documentation, not installed files, so they are not expected
here): all 13 names match, and 12 match by sha256 exactly. The 13th, `contract.config.json`,
does not match by sha256 because it is a per-host *render* of that same template — this
host's own absolute paths in place of the template's relative ones — the same gap the
[macOS template findings](#macos-template-findings) above record ("User-scope workflows need
absolute contract paths, which `test-contract-mutations` rejects"), not a different file.
Every file present is therefore accounted for as Stage 1's own; there is nothing in this
directory today that is the user's own to preserve, and all 13 are named individually below,
never the directory itself:

```sh
rm ~/.claude/workflows/check-syntax.mjs
rm ~/.claude/workflows/child-usage.mjs
rm ~/.claude/workflows/codex-cross-review.mjs
rm ~/.claude/workflows/contract.config.json
rm ~/.claude/workflows/layer-verdict-lane.js
rm ~/.claude/workflows/readiness-audit.js
rm ~/.claude/workflows/review-changes.js
rm ~/.claude/workflows/test-child-usage.mjs
rm ~/.claude/workflows/test-codex-envelope.mjs
rm ~/.claude/workflows/test-contract-mutations.mjs
rm ~/.claude/workflows/test-envelope.mjs
rm ~/.claude/workflows/test-usage-receipts.mjs
rm ~/.claude/workflows/vendored-lanes.json
```

Any file that later appears in `~/.claude/workflows/` outside this list of 13 names is the
user's own and stays; re-run the same name-and-sha256 comparison against
`examples/claude-native/workflows/` before assuming otherwise.

**`~/.codex/app-server-daemon/settings.json`.** This Mac's coordinator session wrote this
file during Stage 1 with `{"updater": {"autoUpdateEnabled": false}}` — read directly again in
this round-2 fix pass, still exactly that one key and value. Whether the file existed before
Stage 1 is not recorded, so rollback must not delete it blindly: if the private backup holds
a copy, the restore step below already puts that copy back (its `codex/` rsync is not
`--delete`d, so it only overwrites, never skips, this path); if the backup holds no such
file, remove only the key Stage 1 is known to have written, not the file:

```sh
if [ -f "<dated-backup>/codex/app-server-daemon/settings.json" ]; then
  : # nothing to do here — the restore step's rsync of <dated-backup>/codex/ already restores it
else
  python3 -c "
import json, pathlib
p = pathlib.Path.home() / '.codex/app-server-daemon/settings.json'
d = json.loads(p.read_text())
d.get('updater', {}).pop('autoUpdateEnabled', None)
p.write_text(json.dumps(d, indent=2) + chr(10))
"
fi
```

**Skills.** The skills@1.7.0 CLI's `remove` needs `-g` for global scope: Stage 1 installed
these skills globally, and without `-g` the CLI acts on the current directory's *project*
skills instead, not the global ones Stage 1 placed
(`docs/decisions/2026-09-25-skills-trial-and-usage.md:43`, verbatim: "`skills remove <name>
-g -y` (no `-a`) removes the canonical copy, both links and the lock entry" — the same call
this repository's own installer runs on a mismatched install,
[`tools/adoption/install_skills.py`](../../../tools/adoption/install_skills.py) lines 17-21
and its `remove` call at line 196). The `skills` binary is the `skills@1.7.0` CLI that
[`adoption/skills/manifest.json`](../../../adoption/skills/manifest.json)'s `cli` block pins
(`"version": "1.7.0"`), resolved as `skills` first on `PATH` — there is no separate
`<skills-bin>` path to look up (the [Skills](#skills) section below's own `--skills-bin` flag
names this same binary, just not by a fixed path). `DISABLE_TELEMETRY=1` matches the
manifest's own `cli.env` and what the installer sets. There
is no bulk form here, only one call per skill
([`adoption/lifecycle.md`](../../../adoption/lifecycle.md):100, verbatim: "Never uninstall
all user tools to roll back one package"):

```sh
DISABLE_TELEMETRY=1 skills remove typesafe-ai -g -y
DISABLE_TELEMETRY=1 skills remove gh-fix-ci -g -y
DISABLE_TELEMETRY=1 skills remove security-best-practices -g -y
DISABLE_TELEMETRY=1 skills remove iterative-retrieval -g -y
DISABLE_TELEMETRY=1 skills remove search-first -g -y
DISABLE_TELEMETRY=1 skills remove diagnosing-bugs -g -y
DISABLE_TELEMETRY=1 skills remove tdd -g -y
DISABLE_TELEMETRY=1 skills remove codebase-design -g -y
DISABLE_TELEMETRY=1 skills remove resolving-merge-conflicts -g -y
DISABLE_TELEMETRY=1 skills remove grill-me -g -y
DISABLE_TELEMETRY=1 skills remove improve-codebase-architecture -g -y
DISABLE_TELEMETRY=1 skills remove verification-before-completion -g -y
DISABLE_TELEMETRY=1 skills remove security-threat-model -g -y
DISABLE_TELEMETRY=1 skills remove gh-address-comments -g -y
DISABLE_TELEMETRY=1 skills remove semgrep -g -y
DISABLE_TELEMETRY=1 skills remove codeql -g -y
DISABLE_TELEMETRY=1 skills remove supply-chain-risk-auditor -g -y
DISABLE_TELEMETRY=1 skills remove agentic-actions-auditor -g -y
DISABLE_TELEMETRY=1 skills remove property-based-testing -g -y
DISABLE_TELEMETRY=1 skills remove modern-python -g -y
DISABLE_TELEMETRY=1 skills remove sarif-parsing -g -y
DISABLE_TELEMETRY=1 skills remove fp-check -g -y
DISABLE_TELEMETRY=1 skills remove mcp-builder -g -y
DISABLE_TELEMETRY=1 skills remove frontend-design -g -y
DISABLE_TELEMETRY=1 skills remove agent-browser -g -y
DISABLE_TELEMETRY=1 skills remove find-skills -g -y
DISABLE_TELEMETRY=1 skills remove variant-analysis -g -y
DISABLE_TELEMETRY=1 skills remove writing-for-agents -g -y
```

### Restore (what Stage 1 overwrote)

**The one-line form** (restores only what the backup holds, in place, over the live trees;
adds and overwrites, never moves or deletes anything):

```sh
rsync -a <backup>/claude/ ~/.claude/ ; cp -p <backup>/claude.json ~/.claude.json ; rsync -a <backup>/codex/ ~/.codex/
```

Spelled out:

```sh
rsync -a "<dated-backup>/claude/" ~/.claude/
cp -p "<dated-backup>/claude.json" ~/.claude.json
rsync -a "<dated-backup>/codex/" ~/.codex/
```

No `--delete` on either `rsync`, and no `rm` anywhere in this step: every command only adds
a file the backup holds or overwrites a live file with the backup's copy, so a wrong
`<dated-backup>` path, a partial run, or stopping partway through never deletes anything —
worst case, an unwritable destination or a missing source makes one line fail (non-zero
exit) while leaving every live file exactly as it was, and the remaining lines are still
safe to run. That independence is also why the one-line form above joins its three commands
with `;` rather than `&&`: a missing `claude.json` backup (see below) would make only the
`cp` fail, and an `&&` chain would then skip the second `rsync` for no reason it needs to —
each command's own success or failure here is independent of the others, matching the
spelled-out form below it. The coordinator's report does not state whether the 4,516-file
manifest covers a sibling `claude.json` next to its `claude/` and `codex/` folders (this
session did not re-hash the private manifest to check); the `cp -p` line is included on a
best-effort basis regardless — a missing source makes only that one `cp` fail, touching
nothing, and the two `rsync` lines are unaffected either way.

This restores Stage 1's own overwrites (settings.json, config.toml and the other files the
backup held before Stage 1 touched them); it was never going to remove anything Stage 1
*added* — the backup, by construction, never had a prior copy of an addition to restore,
which is exactly why removal comes first, above.

`apply_claude_settings.py` also wrote its own timestamped backup of the pre-Stage-1
`~/.claude/settings.json`, separate from the private folder backup above; restoring that
one file undoes every `settings.json` edit (both guard hooks' registration, the plugin and
MCP entries, `effortLevel`, etc.) in a single step, but it does not uninstall the plugin,
MCP-server or skill payloads themselves — those still need the removal commands above.

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
session later re-ran `launchctl list | grep -E 'agent-ecosystem|native-stack'` while
preparing this PR (over an hour after the coordinator's "after" capture, and — see the
intro above — the same Claude Code session as the one that took it): all three running
PIDs were still the exact same PIDs as both the "before" and "after" captures, and
`maintenance` was still not running with the same last exit code, which is stronger
continuity evidence over time than a single before/after pair, though still this one
session's own observations rather than a second observer's. The "Before" and "After"
columns above are the coordinator's own earlier captures, relayed here rather than
re-observed at the time (the same situation as the backup manifest above, and, being an
earlier point in time, not something even this same session can go back and re-verify);
only the "This session, live" column is something this session directly watched happen
just now. See the PR's evidence-class table: this claim is `source_review` overall, not
`native_proven`, for exactly that reason.

## Headless read-back (names and counts only)

A headless `claude -p --output-format stream-json --verbose` turn from a scratch working
directory, parsed for its `init` event:

- `permissionMode`: `bypassPermissions`; `model`: `claude-opus-5-5[1m]`
- agents: 18; skills: 67; plugins: 11; MCP servers: 5 (all `connected`); slash commands: 107; tools: 118

This session's own [claude-code host receipt](#host-receipts) reproduced the same shape
(18/67/11/5-connected/107/118) from a fresh scratch turn later, so the counts are
reproducible over time by this session, not only a one-off capture — not a second,
independent observer's confirmation (see the intro above).

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

**MCP servers: config.toml declares eight, the live surface has ten** (`native_proven`: the
codex receipt's own `codex mcp list --json` check counts both). `config.toml` has eight
`[mcp_servers.*]` tables (`ai-memory`, `context-mode`, `headroom`, `node_repl`,
`openaiDeveloperDocs`, `qmd`, `serena`, `socraticode`); the receipt's check confirms all
eight are present live (`declared` is a subset of `live`, which gates the command's exit
code), but the live listing also has two servers `config.toml` does not declare: `cua_repl`
(enabled) and `codex_app` (disabled), both printed by the receipt as
`live_only_not_in_config_toml`. **Their provenance is `source_review`, not
`native_proven`:** the receipt's `mcp list` command prints only each server's name,
`enabled` state and transport, never where it came from. This session separately read each
plugin's own `.mcp.json` under `~/.codex/plugins/cache/openai-bundled/` directly and found
each server declared by a Codex plugin enabled in `config.toml`'s `[plugins."*@*"]` tables
(`unified-computer-use@openai-bundled` and `codex-app-tools@openai-bundled` respectively),
installed from the ChatGPT desktop app's bundled `openai-bundled` marketplace, not from
this repository's Stage 1 install — a claim no command in any receipt backs. `config.toml`
enables 13 plugins in total (its `[plugins."*@*"]` entries), including `unified-computer-use`,
`computer-use`, `chrome` and `browser`; every Codex turn on this host — including a
`codex exec --sandbox read-only` receipt command — has these plugin-provided tools
available under `approval_policy = "never"`, because the read-only sandbox bounds the
agent's own shell commands, not plugin tools. The same is true of a *declared* server
Stage 1 approved individually: `config.toml`'s own `[mcp_servers.context-mode]` table sets
`default_tools_approval_mode = "approve"`
([`adoption/templates/codex.config.template.toml` lines 115-119](../../../adoption/templates/codex.config.template.toml)),
which is equally outside `--sandbox read-only`'s scope and runs shell commands of its own
(`ctx_execute`) as a separate process, by that same template's own comment (lines 105-114).
See "Memory-store writes during recording" below for what this means for the codex
receipt's exec turn specifically. Whether this extra surface is accepted for a
never/danger-full-access profile is an open question for the owner, not decided here; this
README previously described the live listing as matching config.toml, which undercounted
it, and no longer does.

`app-server-daemon` `updater.autoUpdateEnabled`: `false` (per the coordinator's report, and
confirmed again by a direct read of the file in this round-2 fix pass — still exactly
`{"updater": {"autoUpdateEnabled": false}}` — since that setting lives under `CODEX_HOME`
outside the profile files this document otherwise reads directly; stays `source_review` and
unverified by any receipt — the codex receipt proves only `features.daemon_auto_start = false`, a different
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

## Memory-store writes during recording

Every model turn behind a host receipt below is a real client turn on this host's live,
already-running `local.agent-ecosystem.ai-memory` service (see "Service continuity"
above), not a synthetic or isolated one. Both clients' user-scope lifecycle hooks are
wired to that service (["Token-efficiency / client-wiring coverage"](#token-efficiency--client-wiring-coverage)
above: `ai-memory hook events present` for Claude, `hooks feature on` for Codex, the
latter cross-checked live by the codex receipt's `codex features list` command), and they
fire on these turns: the claude-code receipt's headless `claude -p` turn and the codex
receipt's `codex exec` turn each write a new session and project into ai-memory's own
store (agent-tagged `claude-code`/`codex` respectively), named after that turn's own
scratch `mktemp` directory. Codex's `--ephemeral` flag governs only that run's own session
history (whether it can later be resumed or forked); it does not disable these hooks or
stop this write. Neither `scripts/host_receipts.py` nor any command in any receipt below
cleans up these writes: they are left in the production ai-memory store, as ordinary
session pages, for the owner to review or remove.

This corrects two claims made elsewhere that this fact contradicts:

- The current `claude-code--use--20260927-3` receipt's own limitations (its own text,
  frozen — a receipt changes only by recording a new superseding generation) end with
  "fixture-only input in a fresh mktemp directory, **no mutation evidenced**." That
  sentence is true of the fixture's own scratch directory, but "no mutation evidenced" is
  not something any command in that receipt checks: its checker records tool *names*
  (`tool_use_names`), never tool inputs or outputs, and nothing in it compares any state
  before and after the turn. Read plainly, "no mutation evidenced" could suggest nothing
  changed; in fact the turn did write to the ai-memory store, as above, and this receipt is
  not evidence either way for anything else.
- The superseded `codex--use--20260927-3` receipt's claim text (and this README, before
  this revision) described its exec turn as overriding "sandbox to read-only **for
  safety**." As the "Codex" section above now states, `--sandbox read-only` bounds only
  the shell commands Codex's own agent loop runs directly; it does not bound the declared
  `context-mode` MCP server (approved individually, `default_tools_approval_mode =
  "approve"`) or Codex's plugin-provided tools, both of which run outside it. Calling that
  flag a safety boundary on the whole turn overstated what it does. The current
  `codex--use--20260927-4` receipt (see "Host receipts" below) drops "for safety" and
  states this scope explicitly in its own claim and limitations, and its own exec turn
  fires the same ai-memory hooks the first bullet above describes.

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

Seven receipts under
[`evidence/hosts/mac-coordinator-64gb-20260925/`](../../hosts/mac-coordinator-64gb-20260925/),
all `evidence_class: native_proven`, `stage: use`, `result: pass`, `layer_refs:
foundation/native-clients`, `second_physical_machine: true`. Each component's receipts form
one superseding chain per host/component/stage/date; only the latest generation is current
evidence, and the schema keeps every earlier generation byte-identical rather than deleting
it. claude-code's current generation is `-3` (original, then `-2`, then `-3`); codex's is
`-4` (original, then `-2`, `-3`, then `-4` — recorded in this review-fix pass so its
positive control gates on, and prints, a `command_execution` that actually references the
fixture, rather than the first successful `command_execution` of any kind; see the findings
below):

| Receipt | Component / version run | What it backs |
| --- | --- | --- |
| [`...--claude-code--use--20260927.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927.json) | claude-code 2.1.283 | superseded twice; version was only a flag here, not a retained command |
| [`...--claude-code--use--20260927-2.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927-2.json) | claude-code 2.1.283 | superseded by `-3` (review findings: the claim asserted a Read-tool check and a `claude mcp list` failure-mode the commands did not perform; see below) |
| [`...--claude-code--use--20260927-3.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--claude-code--use--20260927-3.json) | claude-code 2.1.283 | current. `command -v`/`readlink -f`/`--version`; a headless `claude -p` turn (random-fixture line-count positive control, matched, plus an in-transcript negative control on a deliberately wrong count, correctly rejected) that also scans the transcript's own `tool_use` events and fails unless a `Read` call is present (it does not check what that `Read` call's input was, only that its name appears among the used tools); and a `claude mcp list` whose own exit code is captured with no shell pipe, failing unless it is 0 and every reported server's status contains `Connected` (5 servers, all Connected). Its own limitations end "no mutation evidenced" — see "Memory-store writes during recording" above for why that is not a check this receipt runs |
| [`...--codex--use--20260927.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927.json) | codex-cli 0.158.0-alpha.2.1 | superseded three times; version was only a flag here, not a retained command |
| [`...--codex--use--20260927-2.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927-2.json) | codex-cli 0.158.0-alpha.2.1 | superseded by `-3` (review findings: the version-check command's exit code was actually a later `echo`'s, not `codex --version`'s; the claim named a specific model command that was not checked; `approval_policy`/`sandbox_mode` were claimed without a live check; the mcp-list check's summary line and the `socraticode` row fell outside the 400-char excerpt — `cua_repl` and `codex_app` were inside it, not cut off; see below) |
| [`...--codex--use--20260927-3.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927-3.json) | codex-cli 0.158.0-alpha.2.1 | superseded by `-4` (review findings: the positive control's checker accepted the first successful `command_execution` in the transcript, whichever it was — this generation's own retained excerpt shows a plugin `SKILL.md` read satisfied it, with no relation to the fixture; `mcp list`/`features list` piped codex's own stderr into the JSON/text parse and discarded codex's own exit code behind `python3`'s exit code; the claim called `--sandbox read-only` a safety boundary though it does not bound the declared `context-mode` MCP server or Codex's plugin-provided tools; see below and "Memory-store writes during recording" above) |
| [`...--codex--use--20260927-4.json`](../../hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--codex--use--20260927-4.json) | codex-cli 0.158.0-alpha.2.1 | current. Version/channel check whose exit code is `codex --version`'s own; `codex exec --skip-git-repo-check --sandbox read-only --ephemeral` (random-fixture positive control gated on, and printing, a `command_execution` event whose own command text contains the fixture's filename and exited 0 — not merely the first successful `command_execution`, whichever it is — plus an in-transcript negative control on a deliberately wrong count, correctly rejected; both `event_kinds`, per top-level event type, and `item_kinds`, per completed item type, are printed); `codex mcp list --json` and `codex features list`, both now run with `set -o pipefail` and codex's own stderr discarded before the parse instead of merged into it (declared ⊆ live gates the exit code together with codex's own; any live-only server is disclosed, not a failure — this run: `cua_repl`, `codex_app`; the receipt's own line naming which plugin provides each, `unified-computer-use@openai-bundled` and `codex-app-tools@openai-bundled` respectively, carries no evidence-class label of its own — that plugin-to-server mapping is `source_review`, same as the marketplace-origin claim beside it, both read from each plugin's own `.mcp.json`, not from this command's name/enabled/transport-only output; see "Codex" above). No longer claims `approval_policy`/`sandbox_mode`, and no longer calls `--sandbox read-only` a safety boundary (see "Codex" and "Memory-store writes during recording" above) |

Both installed builds are newer than the current catalog pins (claude-code 2.1.278, codex
0.155.1), so every `-2` and later receipt uses `--allow-unbound-version` and does not by
itself change either component's `macos-arm64` `platform_status` (still `untested`); that
needs independent review plus the matrix flip rule in
[`docs/component-evidence-matrix.md`](../../../docs/component-evidence-matrix.md).

**A compliant independent review of these receipts cannot return `agree`, by construction,
and this PR's merge does not wait on that being fixed.** `docs/contributing-evidence.md`
section 3, step 8's four review points (`docs/contributing-evidence.md:340-363`) include, as
point 4, "bound to the winner": the receipt's
`tool_versions` must match the landscape winner's pin. The current claude-code `-3` and
codex `-4` receipts are both `--allow-unbound-version`; the tested codex is the ChatGPT
app's bundled alpha build, which cannot bind to an `openai/codex` release pin at all, at any
version. So a review that adequacy-checks all four points must record `needs_changes` on
point 4, which — per `contributing-evidence.md` — withholds `accepted` regardless of the
other three points. The Opus same-host review and the workstation's GPT-6 cross-family
review requested in this PR's Review section can only adequacy-check points 1-3 (layer
role, positive control, backed claims); point 4 fails by construction, so these receipts
stay informational and are not expected to reach `accepted` through this PR. The route to
bound, `accepted`-eligible evidence is installing the pinned official `claude-code` 2.1.278
and `openai/codex` 0.155.1 releases and re-recording. For claude-code alone, moving the
landscape pin forward through the re-record process in `docs/contributing-evidence.md`
section 4 is a second route; it is not one for codex, whose tested build is a
ChatGPT-bundled alpha and not an `openai/codex` release at all — no landscape pin change
makes a non-`openai/codex` build bind to an `openai/codex` pin, so only installing the
pinned official release closes this for codex.

Three findings surfaced while recording the codex receipts, from this session's own
observation, not all backed by a retained command:

- **Distribution channel.** The first command's `file_type` and
  `chatgpt_app_reference_count` lines (backed by that retained command) show
  `~/.local/bin/codex` is a shell script that references `ChatGPT.app`, without printing
  its contents. That the script's own comment reads "the ChatGPT-bundled Codex through the
  app's declared entrypoint", and that the tested `codex-cli 0.158.0-alpha.2.1` is
  therefore the ChatGPT desktop app's bundled build rather than a separately downloaded
  `openai/codex` release, is this session's own direct read of the script's text
  (`source_review`): no command in any receipt generation prints that comment, only the
  file-type line and the redacted reference count.
- **`codex exec` needs `< /dev/null`** (an unretained observation from this session, not a
  new finding: no retained command in any receipt generation runs `codex exec` without
  `< /dev/null` to show the alternative). Without redirected stdin, `codex exec` blocks
  indefinitely on "Reading additional input from stdin...". This is documented upstream
  behavior, not new to this host or this codex-cli build:
  [`evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/README.md`](../gap-wave2-20260923/foundation__quality-evaluation/README.md)
  traces the same blocking `read_to_end` on stdin to `codex-cli` 0.155.1's own
  `resolve_root_prompt` (tag `rust-v0.155.1`, `codex-rs/exec/src/lib.rs`). Every exec command
  in every receipt generation already redirects stdin from `/dev/null`.
- **The superseded `-3` receipt's positive control accepted the wrong command** (fixed in
  `-4`, above). Its checker recorded the first `command_execution` item that exited 0,
  whichever it was, as the printed "proof" text; this run's own retained excerpt shows that
  was a plugin's `SKILL.md` read (`cat
  ~/.codex/plugins/cache/context-mode/context-mode/1.0.169/skills/context-mode/SKILL.md`),
  unrelated to the fixture the positive control exists to count. The turn's final answer
  was still correct on its own terms (the model's own arithmetic on the fixture, checked
  against the actual line count), but the *printed command text* was not evidence of how it
  got that answer. `-4`'s checker instead requires and prints a `command_execution` whose
  own text contains the fixture's filename.

## macOS template findings

From the coordinator's Stage 1 run, plus this session's own checks where noted:

- The settings template's ai-memory 2.4.1 hooks were not merged; the live hooks reach the
  running ai-memory 19b6429 build and its own store instead.
- The rtk hook is wired (Claude's `PreToolUse` `Bash` matcher runs `rtk hook claude`) and
  needs rtk >= 0.50.0 plus a five-entry `exclude_commands` list. This session's own check
  found **both** rtk builds present on this host: a `mise`-managed install at 0.49.0, and
  the ecosystem install at 0.50.0 (`~/.local/share/codex-ecosystem/bin/rtk`, itself a
  symlink into a `-staging` tree). A plain interactive shell resolves the mise-managed
  0.49.0. This session read `~/.claude/settings.json`'s own `env.PATH` value and re-ran
  `command -v rtk`/`rtk --version` with exactly that `PATH` (the environment Claude Code
  gives its hooks, including `rtk hook claude`): it resolves to the ecosystem install and
  reports **rtk 0.50.0**, so the "done here" holds for hook execution specifically, not
  for every possible invocation of the bare `rtk` command on this host. **This check ran
  directly in this session, not through either receipt: neither receipt's own retained
  `commands` runs an rtk command, so its result is quoted here but not retained the way a
  receipt's output is. This claim is `source_review`, not `native_proven` (relabeled on
  review; the PR's evidence-class table matches).**
- The context-mode cache-heal hook is registered by the plugin itself, not by the settings
  template.
- The Qdrant URL wired into this profile is `127.0.0.1:6333`, not the template's `16333`
  (checked directly in this session against this host's live `codex mcp list --json`
  output). **The codex receipt's own retained `mcp list` command deliberately never prints
  a server's URL or any other connection detail, to avoid capturing MCP server config in
  the receipt (see its `limitations`), so this value is not itself in any retained command
  output. This claim is `source_review`, not `native_proven` (relabeled on review; the
  PR's evidence-class table matches).**
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

- This document and its `-2` and later receipt generations are the evidence-PR session's
  own work (claude-code's `-3` and codex's `-3`/`-4` generations were recorded in later
  review-fix passes on 2026-09-27, applying this PR's own review findings); the
  client-layer install itself (backup, agents/guard/MCP install, settings render/apply,
  skills/plugins/workflows, Codex wiring) was performed earlier by this same session,
  acting as coordinator, and is reported here from its retained outputs, not re-run end to
  end within this document. Where a line was re-checked here, later, it says so above — see
  the intro's note that the coordinator session and this evidence-PR session are the same
  session, not two observers.
- Every receipt generation carries only the recorder's self-review; `accepted` needs an
  independent review from a separate session (requested in the PR). See "Host receipts"
  above for why the current claude-code `-3` and codex `-4` generations cannot reach
  `agree` from any reviewer, by construction, regardless of who reviews them (both are
  `--allow-unbound-version`).
- No `platform_status` is changed by this PR. `adoption/manifest.json`'s macOS platform
  profile status is a separate, maintainer-judgment field this PR does not touch.
- Counts, booleans, file names and, in the current `-3` claude-code and `-4` codex receipts,
  tool names and item-type tallies appear; no session id, uuid, working-directory path, MCP
  server command/args/env, or personal path appears in this document or in any receipt's
  retained command output. Only one of the two prints a command line at all: the `-4` codex
  receipt captures the one `command_execution` its positive control gates on, with its
  scratch directory replaced by `<scratch>` in the printed text; the `-3` claude-code
  receipt's own retained output has no command line anywhere in it, only the `tool_use_names`
  its transcript scan records (see "Host receipts" above for both).
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
