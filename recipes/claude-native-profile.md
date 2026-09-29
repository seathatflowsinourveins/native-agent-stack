# Native Claude profile and foundation practice

This is the selected September 20, 2026 native profile for the existing
foundation. It combines the native client, task-scoped instructions, selected
upstream skills, existing context tools and bounded workers. It does not require
another scheduler, gateway, SDK or complete plugin bundle at session startup.

The [September 21 native Ultracode qualification](../docs/native-ultracode-20260921.md)
extends this baseline with Fable-led Workflow execution, task-matched models,
background-session messaging and native dashboards. Use its
[dedicated profile](claude-native-ultracode.md) for substantial parallel tasks;
the dated profile below remains evidence for the earlier setup.

The [community candidate review](../docs/community-native-practice.md) records
source revisions, merits and exclusions. The [foundation catalog](../catalogs/foundation/manifest.json)
retains all sixteen layers and their actual acceptance boundaries. Installation,
native discovery, task correctness, interactive behavior and measured efficiency
are separate results.

Use the [native dashboard access guide](../docs/native-dashboards.md) for the
installed upstream observation interfaces, passwordless loopback setup and
actual browser/API results. Hosted Insight enrollment is separate.
Use the [native data guide](../docs/native-dashboard-data.md) for memory/RAG,
upstream graph and session views, source dates and separately scoped savings.

## Native installation and terminal entry

Reuse a working native installation. For a new Linux/WSL machine, follow the
[official installer](https://code.claude.com/docs/en/setup) and the pinned
`claude-code` recipe in [the installation table](README.md). The accepted runtime
for this profile is 2.1.278; a later release needs its own selected checks.
Run `claude --version` and `claude doctor` from the intended project. Complete
the native sign-in flow; do not copy authentication stores from another PC.

Launch `claude` in the selected repository. This PC already has an
`ecosystem-claude --project /absolute/project` launcher that selects its existing
native scope and refreshes usage on return. That host launcher is a local
integration, not an upstream Claude executable and not installed by this recipe.
On another PC, native `claude` is sufficient; retain any accepted local launcher.

For Windows Terminal, add a named profile with the distro, WSL user and project resolved on that PC. The
[fragment example](../examples/claude-native/windows-terminal.fragment.example.json) carries the Shell, Codex and
Claude set; its install steps, the login-shell check and the Claude Code notification overlay are in
[the Linux/WSL2 page](../adoption/platforms/linux-wsl2.md#windows-terminal-profiles-and-the-login-shell). The
Claude entry, with its settings explained below:

```json
{
  "name": "Claude Code (Ubuntu)",
  "commandline": "wsl.exe -d Ubuntu-24.04 -u <wsl-user> --cd /absolute/project --exec /bin/bash -lc \"exec claude\"",
  "startingDirectory": "%USERPROFILE%",
  "hidden": false,
  "environment": { "COLORTERM": "truecolor" },
  "tabTitle": "Claude Code (Ubuntu)",
  "bellStyle": ["audible", "taskbar"],
  "bellSound": "C:\\Windows\\Media\\Windows Ding.wav",
  "closeOnExit": "graceful"
}
```

Use the actual distro, WSL user and project (`startingDirectory` is only the Windows-side working directory of `wsl.exe`; `--cd` sets the Linux one). If the accepted local launcher is selected instead, run it in place of
`claude` and append its `--project /absolute/project` option. `closeOnExit: graceful` closes the tab on a normal
exit and keeps a failed start open with its exit code visible (the default `automatic` behaves the same for a process
Terminal launches itself,
[profile termination behavior](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/profile-advanced#profile-termination-behavior)).
Preserve other profiles and the user's terminal default. Windows Terminal
already supports Shift+Enter; use the official
[terminal configuration](https://code.claude.com/docs/en/terminal-config) only
for a demonstrated keyboard/display problem. Shell or tmux customizations are
not prerequisites.

Tab titles, bell and colour in those profiles (measured on one host; reasons, sources and
limits in [the 2026-09-28 terminal decision](../docs/decisions/2026-09-28-terminal-experience.md)):

- Do not set `suppressApplicationTitle` on a Claude or Codex profile. It discards every
  program-sent title, so all tabs read the same. Leave it off, keep `tabTitle` as the
  initial title and `tabColor` as the static identity, and each session shows its own
  native title (Claude's AI session title and busy spinner; Codex's `terminal_title`).
  A settings reload applies the change to open tabs at their next title write. Static
  shell profiles may keep a fixed title; give them `"bellStyle": ["taskbar"]` so a readline
  completion bell stays silent.
- BEL is the only bell or notification signal Windows Terminal acts on (`DECPS` plays notes
  but raises no bell indicator, and a hook cannot send it): it does not handle
  plain OSC 9 text, OSC 777 or OSC 99 in 1.24 stable or the 1.25 preview, and `OSC 9;4` only
  sets tab and taskbar progress state. The default `bellStyle`,
  `audible`, gives a sound and a tab bell icon that stays until the tab is focused. Write
  an explicit array such as `["audible", "taskbar"]`, never `"all"` (on Terminal `main`
  `"all"` will also raise a toast), and choose a quiet `bellSound`: the Windows Ding sound
  measured 16 dB quieter (RMS) than Windows Notify System Generic.
- To be alerted only when a decision is pending, set `preferredNotifChannel` to
  `notifications_disabled` and add one `Notification` hook whose matcher is the exact list `permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input|quota_auto_resume_stale|quota_auto_resume_disabled|worker_permission_prompt|push_notification` and whose command is `jq -nc --arg s "$(printf '\a')" '{terminalSequence:$s}'`. The dialog
  types (permission, elicitation and an agent-team setup question) wait until you have been
  unresponsive for about 6 s; `agent_needs_input` also fires when a background session starts
  waiting while agent view is open; the quota types fire when the quota event occurs; `worker_permission_prompt` (a teammate needs permission) and `push_notification` (the model's own PushNotification: without this type its "come back" signal rings nothing, and with it the bell rings once, in a native probe. The tool sends nothing while the client judges you present. The rule, read from the binary: once the terminal has sent a focus report, its last state decides, and a tab last reported focused counts as present however long you are away, so a push, and its bell, reach you when the tab or window was last reported unfocused, not when you left a focused tab; before any report, 60 s without input counts as away. `CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK` bypasses the check, so a push is then also sent while you watch. Whether Windows Terminal reports focus for a background tab was not measured. With Remote Control connected the tool also needs the mobile-push setting `agentPushNotifEnabled`, and it exists only where the server-side flag `tengu_kairos_push_notifications` is on) are not in the hooks reference: they come from the installed binary, which knows 17 notification types, all of them valid matcher values (the other nine stay quiet on purpose, each with its reason in the scan's table; see the decision). The same hook covered a pending `AskUserQuestion` and plan
  approval in a native probe. In Codex set
  `[tui] notifications = ["approval-requested", "plan-mode-prompt", "async-question"]`.
- Agent teams: the default `in-process` display works in any terminal, Windows Terminal included (in-process teammates run inside the lead's terminal per the same page, so the lead's own alerts ring in its tab; an alert a teammate raises, such as `worker_permission_prompt`, was not observed here). Split panes need tmux or iTerm2 and are opt-in through `teammateMode` ([display modes](https://code.claude.com/docs/en/agent-teams#choose-a-display-mode)); the same page's limitations say "Split-pane mode isn't supported in VS Code's integrated terminal, Windows Terminal, or Ghostty" (it may mean native panes, and tmux inside WSL is outside its stated support and unmeasured for teams here), so none is configured. What was measured is narrower: tmux 3.4 forwards a pane's BEL to the outer terminal by default (a pty in the probe; `bell-action any` and `visual-bell off` are its defaults) and `bell-action none` or `visual-bell on` stops it.  The team hooks `TeammateIdle`, `TaskCreated` and `TaskCompleted` (exit 2 gives feedback) are the upstream quality gates and are not configured on this host.
- Claude Code draws in 256 colours under WSL because `COLORTERM` is unset, although Windows
  Terminal renders 24-bit. Add `"environment": { "COLORTERM": "truecolor" }` to its profile:
  Windows Terminal sets the key on the launched process and adds it to `WSLENV`, so the `--exec` command line above stays unchanged. A profile's own `environment` replaces `profiles.defaults.environment` instead of merging with it, so copy any variables the defaults set into it. Codex promotes truecolor itself when
  `WT_SESSION` is set.
- If the profile starts a login shell (`bash -lc`), bash reads only the first of `~/.bash_profile`, `~/.bash_login` and
  `~/.profile` (`bash(1)` INVOCATION), so a file created at one of the first two names hides the PATH and `~/.bashrc` that
  `~/.profile` provides. `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` on Linux with bubblewrap does exactly that: it pre-creates empty
  placeholder files for missing protected paths, `~/.bash_profile` among them, and leaves them (anthropics/claude-code #76236 and
  #78072; reproduced on 2.1.284). Keep a real `~/.bash_profile` that hands off to `~/.profile`
  (`if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi`), never an empty one, and probe the way the profile starts, with a clean
  environment (`env -i HOME="$HOME" PATH=<distro default> /bin/bash -lc 'command -v claude'`): a probe from a shell that already has
  PATH passes even when the login files are broken. Do not put a fixed `-n` or `--name` in a shared profile, because every tab would
  carry the fixed name or a variant of it instead of its own generated title; use `/rename` in a tab.

For the matching Codex entry, add a separate `Codex (Ubuntu)` profile using the
same distro/project and the installed native `codex` executable. On this host,
the accepted `ecosystem-codex --project /absolute/project` launcher selects the
existing native Linux home. Preserve Desktop's separate home and native sign-in.
Both named profiles are now installed on the recorded host. Open them through
[Windows Terminal's upstream command interface](https://learn.microsoft.com/en-us/windows/terminal/command-line-arguments):

```sh
wt.exe -w 0 new-tab -p "Claude Code (Ubuntu)"
wt.exe -w 0 new-tab -p "Codex (Ubuntu)"
```

Both commands returned exit 0, and separate interactive Claude 2.1.278 and
Codex 0.155.1 processes were observed in the intended project on distinct TTYs.
The [terminal observation](../evidence/receipts/native-terminal-profiles-20260920.json)
records that narrow result. Opening the client does not complete sign-in or prove
interactive commands/HUD; use the session's native flow. If `wt.exe` is unavailable
as a WSL execution alias, Microsoft's documented `cmd.exe /c wt.exe` entry is the
portable fallback. Do not repeatedly run either command unless another tab is wanted.

## Small persistent contract; selected upstream skills

Merge the [short instruction example](../examples/claude-native/CLAUDE.md) into
the user's existing `~/.claude/CLAUDE.md`, preserving independent preferences and
managed imports. Since the [2026-09-26 cleanup](../docs/decisions/2026-09-26-harness-rules-cleanup.md)
the example states each rule once under section headings, so replace an earlier
merged copy of it as a whole instead of merging line by line, which would state
rules twice. The example changed after `v2026.09.26.2`: its top rule became the
five-step [upstream-verification procedure](../docs/harness-defaults.md#upstream-verification-and-compounding-learning)
at about the same length, so a host at that tag merges the earlier text; replace
it the same way. Keep project-specific tests, memory scope and domain policy in
that project's `CLAUDE.md`/`AGENTS.md`. Do not preload this catalog or duplicate
the installed tool inventory in every worker.

ECC's requested `everything-claude-code` URL resolves to `affaan-m/ECC`. The two selected
skills, `skills/search-first` and `skills/iterative-retrieval`, install at the same reviewed
revision as before, `2b6e839771e53096d8451a213d40dc64ec8acac0`, but now through the pinned
`skills` CLI declared in [`adoption/skills/manifest.json`](../adoption/skills/manifest.json)
(see [the 2026-09-25 trial record](../docs/decisions/2026-09-25-skills-trial-and-usage.md)),
not the superseded Codex-only installer route below:

```sh
python3 tools/adoption/install_skills.py --skills-bin <tools-root>/skills-1.7.0/bin/skills   # installs every manifest entry, including both ECC skills
python3 scripts/skills_status.py --skills-bin <tools-root>/skills-1.7.0/bin/skills          # confirms both are installed at 2b6e839...
```

This puts both skills in the global lock (`~/.agents/.skill-lock.json`, or
`$XDG_STATE_HOME/skills/.skill-lock.json` when that variable is set), with the canonical copy at
`~/.agents/skills/search-first/` and `~/.agents/skills/iterative-retrieval/`. On a host with no
earlier link, Claude gets a **relative** symlink, `~/.claude/skills/<name> ->
../../.agents/skills/<name>`, created automatically. A host that already had this recipe's earlier
manual **absolute** links keeps them: the CLI leaves an existing link that resolves to the
canonical folder (measured on nativestack-5975wx-20260925, 2026-09-25), and
`scripts/skills_status.py` reports `link=ok(absolute)`, which works the same. Codex reads
`~/.agents/skills` directly with no separate link, and neither client needs a manual linking step
any more. Compare the lock's `skillFolderHash` for each skill against
the manifest's `tree_sha`; a mismatch means a later, uncompared install moved the copy off the
reviewed revision.

### Superseded history: the Codex-only installer route (pre-2026-09-25)

Before the pinned `skills` CLI, Codex's own installer script populated a shared skills
directory, and Claude's copy had to be linked to it by hand:

```sh
python3 /absolute/codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo affaan-m/ECC --ref 2b6e839771e53096d8451a213d40dc64ec8acac0 \
  --path skills/search-first skills/iterative-retrieval \
  --dest "$HOME/.agents/skills"
```

Resolving the installer's actual path was required, since it refused an existing destination and
would not preserve project customizations by overwriting them. Claude's official
[skill directory](https://code.claude.com/docs/en/skills) is `~/.claude/skills`; on Linux/WSL,
the missing Claude skill directory then had to be linked to the installed shared directory by
hand, checking for an existing destination first, and the installed files compared against the
recorded source hashes in the candidate review. Claude still loads the skill body only when
invoked; available skill names/descriptions still have context cost either way.

Do not install the full ECC hooks/rules/plugin collection over the existing
RTK, Context Mode and ai-memory lifecycle handlers. The selected reference
repository `shanraisshan/claude-code-best-practice` supplies reviewed guidance,
not a runtime daemon. A source review is its relevant acceptance level.

## Supported quality defaults

For the selected native Codex 0.155.1 and GPT-6-Astra, this host saves the same
quality-oriented reasoning setting already selected in Desktop:

```toml
model = "gpt-6-astra"
model_reasoning_effort = "ultra"
```

Merge only the effort field into the intended Codex home. Preserve the native and
Desktop homes, account, model, permissions and project configuration. The installed
upstream `codex debug models --bundled` catalog explicitly supports `ultra` for
this model; its unconfigured native default is `low`. Generic API effort tables
are not the native client's complete model-specific catalog. Fresh native
`config/read` calls through the official SDK returned `ultra` in both homes,
including this project's configuration layers, without starting a model turn.

For Claude Code 2.1.278, merge this field into the existing user settings:

```json
{"effortLevel": "xhigh"}
```

Retain the selected `opus[1m]` model. The installed persistent schema accepts
`low`, `medium`, `high` and `xhigh`; `max` is a session-selected effort, not a
valid persisted `effortLevel`. Native adaptive thinking already applies when
`alwaysThinkingEnabled` is absent or true. Preserve that default and avoid fixed
thinking-token or global effort environment overrides. See [Claude model
configuration](https://code.claude.com/docs/en/model-config) and
[settings lifecycle](https://code.claude.com/docs/en/settings).

**2026-09-23 correction: the top-level `effortLevel` above stops covering Opus
5.5 and later.** Per the same settings-reference docs (fetched 2026-09-23), a
USER-scope top-level `effortLevel` applies only to Opus 5, Fable 5.1 and
earlier models; Opus 5.5 (`claude-opus-5-5`) and later ignore it and start at
their own default (observed: `medium`). Project, local and managed settings'
top-level `effortLevel` are unaffected by this and still apply to every
model. To keep Opus 5.5 at `xhigh` in USER settings, save a per-model entry
instead (what `/effort xhigh` writes once the model is active):

```json
{
  "effortLevel": "xhigh",
  "modelSettings": {
    "claude-opus-5-5": {"effortLevel": "xhigh"}
  }
}
```

The top-level `effortLevel` is still worth keeping for Fable 5.1 and any
earlier model a session might fall back to; it is simply not sufficient by
itself once Opus 5.5 is the active model. This host's own
`adoption/hooks/claude/effort-default-guard.py` (installed at
`~/.claude/hooks/effort-default-guard.py`) automates exactly this: it warns
at `SessionStart` when the resolved effort for the active model is below
`xhigh`, and at `SessionEnd` it self-heals a `modelSettings.<model>.effortLevel`
save when the session ran below `xhigh` only because no level was ever saved
for that model anywhere -- it never overwrites a level someone (or a prior
run) deliberately saved, even a low one. Claude Code discards `SessionEnd`
hook output, so a self-heal also leaves a one-line notice file in
`~/.claude/effort-default-guard.notices/`. The next `SessionStart` that
reports its model resolves its own warning first, then claims each notice with
an atomic rename, prints it once and deletes it only after printing; a start
that loses the claim prints nothing for that notice, and notices older than 7
days are deleted unseen.

**2026-09-28: what the `xhigh` pins decide.** For Opus 5.5 the platform guidance
makes `medium` the default and reserves `xhigh` and `max` for work where a
quality gain was measured; "start with `xhigh`" is the Opus 4.7 and 4.8 advice
([prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5),
[effort](https://platform.claude.com/docs/en/build-with-claude/effort), read
2026-09-27). The `xhigh` saves above carry the user's quality requirement, and
their reach is narrow. In user settings the top-level `effortLevel` never sets
Opus 5.5's level, and the per-model key sets it only while Ultracode is off and
neither `--effort` nor `CLAUDE_CODE_EFFORT_LEVEL` overrides it; an Ultracode
session already runs its coordinator at `xhigh`
([model configuration](https://code.claude.com/docs/en/model-config),
[settings reference](https://code.claude.com/docs/en/settings-reference),
[environment variables](https://code.claude.com/docs/en/env-vars)). No recorded
measurement tests them. M7 of the
[2026-09-24 sweep](../docs/decisions/2026-09-24-community-sweep.md#keep-but-compare)
covers child roles only; the
[2026-09-27 review](../docs/decisions/2026-09-28-community-sweep.md#amendments-to-the-2026-09-24-rows)
adds a session-level arm with Ultracode off for these pins.

**2026-09-29 correction: on Claude Code 2.1.284 the per-model key applies under
Ultracode, and Ultracode sets nothing.** Native probes
([receipt](../evidence/receipts/claude-model-effort-probes-20260929.json)) found that a
Sonnet 5.5 session with no saved level ran at `medium` under `ultracode: true`; that a
per-model level (`low`, passed with `--settings` in the probe) won over `ultracode: true` for both Sonnet 5.5
and Opus 5.5; and that a project settings file's top-level `effortLevel` or a
`modelSettings` entry of `xhigh` raised the Sonnet 5.5 session to `xhigh`. The statement
above that an Ultracode session already runs its coordinator at `xhigh` held before
2.1.284 (it was measured on 2.1.281), and so did "a `max` session turns Ultracode orchestration off": on 2.1.284 the reminder stayed
present at `max` (an indicator, not proof of workflow behaviour). Save the pin for every model the agents bind (`claude-opus-5-5` and
`claude-sonnet-5-5`), or commit `effortLevel: xhigh` in the project file; the guard now
follows the measurement (an unsaved model warns at `SessionStart` and heals at
`SessionEnd`, `ultracode` or not). The
[dispatch record](../docs/decisions/2026-09-29-sonnet-5-5-dispatch.md) has the rest.

**2026-09-29, later: the terminal default is `max`, through the ecosystem launcher.** The user asked for `max` as the default. A saved
`max` is still not accepted, and `CLAUDE_CODE_EFFORT_LEVEL` would override every child's own effort, so the launcher that `install_native`
writes adds `--effort max` only when nothing chose an effort (a terminal, no `-p`, no `--effort`, no `CLAUDE_CODE_EFFORT_LEVEL`, a client
at 2.1.284 or newer). `claude --effort xhigh` opts out, and the saved per-model `xhigh` above stays the fallback for launches that skip
the launcher (IDE, desktop, web). The choice rests on the user's requirement, not on a measured gain here
([decision record](../docs/decisions/2026-09-29-max-default-effort.md), [receipt](../evidence/receipts/claude-max-default-effort-20260929.json)).

Saved effort defaults apply to fresh sessions. Already-open sessions can retain
their previous selection; Claude supports `/effort` for the current session.
Do not interrupt active work to reload a default. [Codex worker settings](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [Claude subagent frontmatter](https://code.claude.com/docs/en/sub-agents)
can override effort/model inheritance, so do not claim all workers run at the
coordinator's effort. The short global instruction example makes task-based
acceptance, original-source verification and independent review persistent.

**2026-09-23: Claude children run at `max`; the coordinator stays at
Ultracode.** Re-measured on Claude Code 2.1.281: a persisted `max` is still
silently dropped. With `--settings '{"ultracode":false,"effortLevel":"max"}'`
the session ran at `xhigh`, while the same key at `high` ran at `high` (probes
Q1 and Q2); for `modelSettings.<model>.effortLevel` the installed schema and
the docs reject `max` as well. A session started with `--effort max` or
`CLAUDE_CODE_EFFORT_LEVEL=max` ran at `max` with Ultracode orchestration off (2.1.281; on 2.1.284 the reminder stayed present).
`/effort max` was not probed; the docs say Claude Code applies `max` to the
current session only
([model configuration](https://code.claude.com/docs/en/model-config), fetched
2026-09-23). Never set `CLAUDE_CODE_EFFORT_LEVEL`: any value overrides every
child's frontmatter and workflow-stage effort, and on 2.1.281 any value other than
`xhigh` also turned Ultracode off (from 2.1.284 it stays on). The shipped [agent definitions](../adoption/agents/claude/)
therefore declare `effort: max` beside their task-matched models (Sonnet for
`source-scout` and Opus for every other shipped role; `isolated-builder` and
`stack-verifier` declare Opus since 2026-09-27, per item 1 of the
[settings decision](../docs/decisions/2026-09-27-claude-harness-settings.md);
Haiku is not routed), and workflow stages pass
`effort: 'max'` explicitly: a stage without its own effort inherited the
coordinator's `xhigh` on 2.1.281 unless its agent's frontmatter sets one, and a stage's
effort overrides the frontmatter (probe Q3). Verify each child's resolved
effort in its transcript rather than inferring it from a definition. The
[Ultracode recipe](claude-native-ultracode.md#child-effort-max-under-an-ultracode-coordinator)
has the per-stage rule and the
[decision record](../docs/decisions/2026-09-23-max-effort-default.md) has the
probes, alternatives and overturn conditions.

The [settings receipt](../evidence/receipts/native-quality-defaults-20260920.json)
records supported values, effective configuration and preservation checks. More
reasoning can increase time and tokens; no quality improvement or savings is
established until the actual task is evaluated.

**2026-09-28: fast mode is a per-session choice.** `/fast` persists
`fastMode: true` to user settings, so later sessions start with it on. On
subscription plans fast mode bills usage credits, which must be turned on, and
the first enable in a conversation bills the whole context at the uncached
fast-mode rate, so enable it at session start
([fast mode](https://code.claude.com/docs/en/fast-mode)). Use `/fast` only for
interactive, latency-sensitive sessions, and turn it off before workflows and
long autonomous runs. Keep `fastMode` out of the settings template;
`fastModePerSessionOptIn: true` is the documented way to make each session start
with it off ([settings reference](https://code.claude.com/docs/en/settings-reference#fastmode)).

**2026-09-28: bypass mode runs here outside its documented condition.** The
[permission modes](https://code.claude.com/docs/en/permission-modes) page says of
`bypassPermissions`: "Only use this mode in isolated environments like
containers, VMs, or dev containers without internet access", and that it "offers
no protection against prompt injection or unintended actions" (see also
[development containers](https://code.claude.com/docs/en/devcontainer) on running
it only in isolated containers). This host runs bypass on bare WSL2
with the `/mnt` automount, network access and no Bash sandbox. The mode is the
user's 2026-09-22 decision, and that decision is still open. Under bypass, deny
rules and PreToolUse denials still block, explicit ask rules and critical-path
`rm`/`rmdir` still prompt, allow rules have no effect, and protected-path writes
are allowed (for example to `.git`, `.claude` other than `.claude/worktrees`,
`.husky` and `.vscode`). The denies and the secret-path guard therefore stop
accidents and are not a security boundary
([threat model](../docs/secret-storage.md#threat-model-and-what-each-guard-stops)).
Auto mode (PS-8 in the
[harness rules convergence](../docs/harness-rules-convergence-20260922.md)) and
the native Bash sandbox
([M1](../docs/decisions/2026-09-24-community-sweep.md#keep-but-compare)) remain
the alternatives.

## Architectural token practice

- Preserve the requested model and native cache, compaction and deferred MCP
  discovery. Match retrieval and worker scope to the actual task.
- Process large logs/data in code and return the required fields with recovery
  locations. Known focused reads can cost less than an indexed retrieval.
- Delegate independent work with explicit input/output contracts. Use owned
  writing checkouts and one integration owner; include worker usage and retries.
- Reuse checkpoints and accepted results. Design idempotency for each new
  external effect. Existing Dagu/systemd recovery does not prove arbitrary
  application or broker replay.
- Keep current native clients as defaults. Use the accepted Codex SDK when a
  programmatic workflow needs it; Claude SDK/DeerFlow additions require their
  own settings/tool/scope/usage contract. Multiple orchestration layers must
  not retry the same effect independently.

These choices follow [Claude cost guidance](https://code.claude.com/docs/en/costs),
[Claude subagents](https://code.claude.com/docs/en/sub-agents), the
[Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) and the existing
[native harness contract](../docs/harness-defaults.md). No default savings
percentage follows from enabling them.

### Session context commands

Checked against the Claude Code docs on 2026-09-27 and the linked pages re-read
on 2026-09-28 (client 2.1.283).

- **Rewind instead of stacking corrections.** Rewind (double-tap Escape or
  `/rewind`) and re-prompt rather than adding corrections on top of a wrong
  turn; a rewind returns to a prefix that is already cached
  ([prompt caching](https://code.claude.com/docs/en/prompt-caching#rewinding-the-conversation)).
  After more than two corrections on one issue, `/clear`
  ([best practices](https://code.claude.com/docs/en/best-practices)). Record a
  failed attempt that is evidence before rewinding. Rewind restores only
  Claude's file-tool edits made in this session. It does not restore Bash
  changes, the edits of any subagent other than a foreground forked skill
  (Agent-tool and workflow children included), other sessions' edits in most
  cases, or symlinked and hard-linked paths
  ([checkpointing limits](https://code.claude.com/docs/en/checkpointing#limitations)).
  Use git for those: commits in owned worktrees stay the recovery path.
- **Name each workstream.** Name each workstream with `/rename <name>` or start
  it with `--name <name>`, and return with `/resume`. A bare `/clear` keeps that
  name; `/clear <name>` names the conversation you are leaving, and the new one
  starts unnamed ([sessions](https://code.claude.com/docs/en/sessions#name-your-sessions)).
  Resume within the same wave, not across days: Context Mode deletes a
  session's store seven days after that session started
  ([session store](../docs/token-session-handbook.md#context-mode-executor-and-session-store)).
- **Summarize part of the conversation.** In the rewind menu, Summarize from
  here (2.1.32 or later) compresses the conversation from the selected message
  onward, and Summarize up to here (2.1.141 or later) compresses what came
  before it. Both take optional focus text, and the original messages stay in
  the transcript
  ([rewind and summarize](https://code.claude.com/docs/en/checkpointing#rewind-and-summarize)).
- **Side questions with `/btw`.** Use `/btw` for questions about what the
  session already knows. It has no tools, and its answer never enters the
  conversation history
  ([side questions](https://code.claude.com/docs/en/interactive-mode#side-questions-with-%2Fbtw)).
  Use a subagent to find out something new.

## Native acceptance and review

Inside an authenticated interactive Claude session, use `/context all`, `/mcp`
and `/usage` to inspect loaded context, connections and usage. Retain their
actual output. `/compact` performs model summarization. Run it at a natural
break, such as between tasks, rather than letting auto-compaction fire
mid-task, and compact before stepping away rather than after: after the cache
lifetime the summarization request reprocesses the whole history uncached.
Give it a focus that names what to keep and what to drop, for example
`/compact keep the acceptance commands, their exit codes and the open gaps; drop the exploratory reads`,
then verify that the next task still has its facts
([prompt caching](https://code.claude.com/docs/en/prompt-caching),
[what survives compaction](https://code.claude.com/docs/en/context-window#what-survives-compaction),
[Opus 5.5 compaction note](https://claude.com/blog/claude-opus-5-5-built-for-coding-sessions-that-use-more-context)).
Do not treat a headless prompt containing `/context` as a zero-cost inspection
command.

For an independent file review, retain inherited tools so the installed hooks
and the reviewer's available capabilities agree. Use a bounded prompt that
explicitly prohibits edits, shell commands, delegation and unrelated reads:

```sh
claude -p --output-format stream-json --verbose --include-hook-events \
  --max-turns 12 --permission-prompts none < review-prompt.txt
```

Use a trusted checkout and a bounded, explicit file list. Capture stdout/stderr
privately, preserve a deadline and the returned exit code, and require one
successful final result plus a grounded report. Inspect the actual `system:init`
tool inventory and tool calls; a prompt contract is not an operating-system
sandbox. Print mode skips the workspace trust dialog and silently ignores a
settings file that fails validation, dropping the whole file (installed
`claude --help`, 2.1.283), so a headless run can start without that file's deny
rules, hooks and permission mode. `system:init` has no settings-source field:
before trusting a result, check its `permissionMode` and `plugins` and, with
`--include-hook-events`, that the expected guard hook events fired. `--bare`
never reads OAuth or the keychain (installed `claude --help`, 2.1.283), and the
[headless docs](https://code.claude.com/docs/en/headless) say it will become the
default for `-p` in a future release. On a host signed in with a subscription
and on the `latest` channel, check each new CHANGELOG entry for that change
before relying on unattended `claude -p`; keep-but-compare
[M6](../docs/decisions/2026-09-24-community-sweep.md#keep-but-compare) selects
the replacement flag set. If enforced read-only access is required, select a
separately qualified
isolation boundary. The older receipt's restricted Read/Glob/Grep invocation is
historical evidence, not the default for every installed hook combination; see
[restricted-worker compatibility](../docs/restricted-worker-compatibility.md).
An SDK is unnecessary
for a single native review. A launcher must keep its own notices on stderr so
the upstream JSON/JSONL stream remains parseable whenever a native child runs.
The local launcher's `--check` mode prints a plain-text diagnostic and starts no
native stream. Installed plugin hooks can contribute guidance even when this
particular review disables MCP servers; count that overhead rather than claiming
that tool restriction removes every startup token.

Keep Codex and Claude reviews independent before comparing findings. Resolve
supported disagreements using the source and relevant checks. Reviewer agreement
alone is not correctness or an independent test. Record complete native usage,
including failed attempts, and preserve unknowns. Use the existing token report
after meaningful changes; do not add its native estimates to provider totals.

Plan mode is optional: use it when the approach is uncertain, the change spans
several files or the code is unfamiliar, and skip it when the diff fits in one
sentence ([best practices](https://code.claude.com/docs/en/best-practices)).
Under this profile's `bypassPermissions` default, an interactive terminal
session does not enforce plan mode's blocks: Claude is only instructed to plan,
and an edit it attempts runs without prompting. Plan mode
keeps its blocks in `-p`, Agent SDK and VS Code chat sessions, and explicit ask
rules and critical-path `rm`/`rmdir` still prompt
([permission modes](https://code.claude.com/docs/en/permission-modes), re-read
2026-09-28). Because plan mode is an instruction here, entering it in a
coordinator can reach running workflow children; resume paused workflow units
afterwards (recorded 2026-09-27, consistent with the permission-modes page but
not re-observed). Plan mode is not a read-only guard here.

## Adoption, maintenance and rollback

Back up the current instruction file and terminal settings before merging.
Record the selected skill source hashes, actual command results, changed files
and preserved client settings. Restore only owned changes when rolling back;
remove only the two skill directories/links introduced by this adoption.
Keep the existing scheduled catalog maintenance and GitHub validation workflow.
Another framework or newer release needs a task-relevant reason and evidence.

## Recorded host results — September 20, 2026

| Check | Returned or independently checked result |
| --- | --- |
| `claude install 2.1.278` | Exit 0; standard native executable installed. Existing launcher retained. |
| `claude doctor` | No installation issues found after PATH repair. Intentional RAG embedding-prefix whitespace remains reported. |
| Pinned ECC skill installer | Both selected skills installed; source hashes match and native Claude initialization lists both. |
| Windows Terminal profile | One named Claude profile added; existing profiles, order and default preserved. Interactive use reached the native first-run sign-in screen. |
| Native Claude file review | Exit 0; successful result with actual Read/Glob/Grep tool inventory. Reported input, cache creation/read and output sum to 389,351 tokens. |
| Official Codex SDK file review | Exit 0; successful native read-only review. Total input plus output: 129,552 tokens; cached input is already included. |
| Short global instruction artifact | 1,175 → 418 tokens with installed tiktoken 0.14.0 / o200k_base: 757 fewer tokens for this exact artifact pair. |
| Local launcher checks | 20 passed, with no model requests. These verify the local integration, not upstream Claude behavior. |

Both reviews produced source-grounded findings that were resolved and checked.
Their different workloads are not a performance comparison. Their usage excludes
the coordinator, research and other workers. The instruction reduction is not a
provider saving or a per-session/lifetime counter. That review did not exercise
interactive `/context`, `/usage`, `/compact` or HUD behavior. The
[subsequent closure review](../docs/foundation-closure-20260921.md) records a fresh
authenticated session, context/usage views, six connected MCP servers and live
HUD rendering. Its observations supersede the earlier sign-in/context/usage/HUD
gap; automatic compaction remains a separate boundary.

Exact commands, returned output, hashes and scope are recorded in
[the profile receipt](../evidence/receipts/native-claude-profile-20260920.json) and
[command manifest](../evidence/artifacts/native-claude-profile-20260920/selected-commands.json).
This recipe is a reproducible guideline, not a claim that every future host or
every optional SDK has passed E2E.
