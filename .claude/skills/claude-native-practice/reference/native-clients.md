# Native client (`native-clients`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## client-core

**Status:** default. **Default:** Native installer build on the latest auto-update channel (`autoUpdatesChannel` unset or `latest`)

- **Route:** `claude install` or the documented install.sh; background sessions move to a new version through the daemon or `claude respawn`
- **Alternatives, ranked:** 1. `stable` channel plus `minimumVersion` after an observed regression; 2. Exact-version install with `DISABLE_AUTOUPDATER` for a frozen host
- **Rejected:** npm global install (deprecated since 2.1.15); `DISABLE_UPDATES` on this host
- **Evidence:** setup.md install and update sections; settings-reference.md `autoUpdatesChannel`; CHANGELOG@v2.1.295 L7262 (npm deprecation, 2.1.15)
- **Supersedes:** M51 reconfirmed
- **Overturn when:** An observed auto-update regression breaks a qualified workflow (then `stable` plus `minimumVersion`), or Anthropic changes the default channel.

## instruction-files

**Status:** default (scoped). **Default:** `CLAUDE.md` that imports `@AGENTS.md`, Claude-only lines below the import, and `paths:`-scoped `.claude/rules`

- **Route:** The four-rule core stays the only always-loaded text (G6a); practice lives in skills, hooks and docs
- **Alternatives, ranked:** 1. Project-instructions setting `claude-md-and-agents-md`; 2. AGENTS.md read directly (2.1.277+) without a CLAUDE.md
- **Rejected:** SessionStart hook that prints AGENTS.md; Prose telling Claude to read AGENTS.md; `<important if>` conditional tags; Telegraphic compression of the core (M20)
- **Evidence:** memory.md import and AGENTS.md sections; memory-O7 (2.1.293: path-scoped rules also load on Write, Edit and single-file Bash views)
- **Notes:** The core loads twice per session on this host (user CLAUDE.md and the AGENTS.md import) and a third time when files under examples/claude-native/ are touched; AN-12's `claudeMdExcludes` entry is still unapplied. The token cost is unmeasured.
- **Supersedes:** M2 (wider rule triggers); MI-7 sizes are dated history
- **Overturn when:** A paired same-task run shows the import pattern loses adherence against an alternative, or a release changes AGENTS.md handling.

## auto-memory

**Status:** default (scoped). **Default:** Native auto memory on, in the default directory, with `MEMORY.md` kept as a short index

- **Route:** Reaches the interactive coordinator, `-p` workers and forks; Agent-tool subagents do not load it; the cross-client memory of record stays in durable-memory (ai-memory)
- **Alternatives, ranked:** 1. `autoMemoryEnabled: false` per project; 2. `autoMemoryDirectory` from user, `--settings` or managed scope only
- **Rejected:** thedotmack/claude-mem over native memory (no measured gain); Repository-tracked auto memory (a repository-supplied `autoMemoryDirectory` is inert)
- **Evidence:** memory.md auto-memory section; memory-O9 (2.1.284: markup neutralized in MEMORY.md); settings-reference `autoMemoryDirectory` scope
- **Supersedes:** The 'index about 22 KB' note of the 2026-10-04 dispatch record (now about 3 KB)
- **Overturn when:** Paired runs show auto memory lowers quality, or dropping the index keeps quality at lower cost; or a release changes its defaults.

## settings-permissions

**Status:** default (scoped). **Default:** Native layered settings (managed > `--settings` > local > project > user) with deny-first rules

- **Route:** Deny rules block in every mode, bypass included; the host's `bypassPermissions` default is the owner's standing choice and is not reopened here
- **Alternatives, ranked:** 1. `auto` mode (unconfigured interactive sessions start in it since 2.1.285); 2. `dontAsk` with `--permission-prompts none` for headless review; 3. `permissions.blockReadsOutsideWorkingDirectories`
- **Rejected:** `bypassPermissions` or `auto` in project settings; Model-backed PermissionRequest auto-approve hooks; Managed settings on this single-owner host
- **Evidence:** settings.md precedence; permissions.md deny-first evaluation; permission-modes.md; settings-permissions-O7, O15, O16
- **Notes:** Under bypass, writes to `.claude` and `.git` are auto-approved and no deny rule covers the guard's own files; any non-interactive run skips the trust dialog. The docs limit bypass to isolated containers or VMs; the recipe records bypass as an open owner decision (recipes/claude-native-profile.md:367).
- **Supersedes:** M46 evidence sentence (auto start mode, 2.1.285); AN-20 list of what still blocks under bypass
- **Overturn when:** The owner reopens the permission mode, a release changes precedence or rule evaluation, or an incident shows a deny or hook gap.

## config-managers

**Status:** default. **Default:** Native settings layering as the profile and provider switch

- **Route:** `--settings` and `--setting-sources` per session; `CLAUDE_CONFIG_DIR` from the shell for a separate profile (it starts without the host's deny rules and guard hooks); provider keys only in user settings or an out-of-repo `--settings` file
- **Alternatives, ranked:** 1. `claude import --dry-run` to preview another client's config; 2. musistudio/claude-code-router, only if the owner adopts a non-Anthropic route
- **Rejected:** farion1231/cc-switch; UfoMiao/zcf; router-for-me/CLIProxyAPI; dyoshikawa/rulesync as a switcher
- **Evidence:** settings.md `--settings`; env-vars.md `CLAUDE_CONFIG_DIR` (shell, user or managed only)
- **Notes:** `forceLoginMethod: gateway` in user settings is unconfirmed: the v2.1.295 CHANGELOG and the current docs disagree on its scope. Adjudicated: the native default stands; the refuter's correction only adds that claude-code-router already has a recorded disposition.
- **Overturn when:** A measured native gap: a profile or provider switch native layering cannot express.

## hooks

**Status:** default (scoped). **Default:** Settings command hooks, with `onFailure: "block"` on each guard hook entry

- **Route:** Needs client 2.1.295 or later; the guard wrapper must also refuse when its script is missing (proposal with the command center)
- **Alternatives, ranked:** 1. hookify (anthropics/claude-plugins-official); 2. Skill-scoped frontmatter hooks
- **Rejected:** lasso-security/claude-hooks; Plugin mods as guards; Prompt or agent hooks as security guards; `onFailure` on the matcher group (no effect)
- **Evidence:** hooks-O9 (2.1.295 onFailure); docs/decisions/2026-10-08-guard-hook-fails-closed.md probe cases
- **Notes:** The repository's pinned floor is 2.1.284 (adoption/pins-linux-x86_64.json), which ignores `onFailure`; the template wrapper exits 0 when the guard script is missing. Only managed-settings hooks resist `disableAllHooks`.
- **Supersedes:** M40 refined; M28 refined (onFailure does not make Stop gates fail closed)
- **Overturn when:** A release changes `onFailure` semantics, or reruns of the record's cases B, D, H and N on a newer client let the call through.

## statusline

**Status:** default (scoped). **Default:** Native `statusLine` (command and `refreshInterval`), fed the session JSON

- **Route:** One pinned renderer behind a fixed launcher path; the template's bash glob wrapper retires in favour of the host's node launcher
- **Alternatives, ranked:** 1. jarrodwatts/claude-hud (current renderer); 2. sirmalloc/ccstatusline; 3. A script from `/statusline` or the docs examples
- **Rejected:** The pre-0.10.0 bash glob wrapper in the template; Status lines that parse the transcript
- **Evidence:** statusline.md; statusline-O7 (2.1.293 subagentStatusLine agentType)
- **Notes:** The renderer runs outside the sandbox with full user access and receives `transcript_path`; pin it and run it through a fixed launcher. Adjudicated: native default, claude-hud ranked first; the refuter upheld it. Owed: the M14 idle check on 2.1.295 at refreshInterval 5 for both renderers.
- **Supersedes:** M14 premise (claude-hud 0.8.0 git calls)
- **Overturn when:** claude-hud stops releasing or its CI stays red, or the M14 idle check shows index rewrites or lock contention that ccstatusline avoids.

## checkpoints-rewind

**Status:** default (scoped). **Default:** Native checkpointing (`/rewind`, Esc Esc) with Git as the permanent history

- **Route:** Covers the interactive coordinator's file-tool edits; `-p` workers get none unless `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true`; subagent and Workflow edits are not restored
- **Alternatives, ranked:** 1. `/branch` or `--fork-session`; 2. SDK file checkpointing for `-p` workers that need rewind
- **Rejected:** Turning checkpointing off; Checkpoints as version control
- **Evidence:** checkpointing.md; claude-directory.md retention (cleanupPeriodDays default 30); checkpoints-rewind-O6, O7, O8
- **Notes:** `cleanupPeriodDays: 3650` keeps plaintext transcripts and pre-edit snapshots for about ten years: an exposure window for any secret a tool read. Retention is the owner's choice; the record gives the trade-off and a recommended value.
- **Overturn when:** A measured footprint or an owner retention decision, or a release changes what checkpoints restore.

## model-effort-routing

**Status:** recommendation (owner's choice). **Default:** Native per-role model and effort: subagent and skill frontmatter, the Agent tool's `model` and `effort` (2.1.292+), per-model `modelSettings`, and `--model`/`--effort` on headless jobs

- **Route:** Opus 5.5 for judgment and build; Sonnet 5.5 or Haiku 5.5 only for a task class with a frozen paired A/B at parity; keep `CLAUDE_CODE_EFFORT_LEVEL` and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` unset, because they override frontmatter and per-call effort; Codex lanes through the gateway for fan-out research
- **Alternatives, ranked:** 1. Re-run failed attempts at a higher effort; 2. Native advisor pairing
- **Rejected:** musistudio/claude-code-router; `opusplan` as a default; A global `CLAUDE_CODE_EFFORT_LEVEL` pin; A cheaper subagent default without an A/B; `MAX_THINKING_TOKENS` caps
- **Evidence:** sub-agents.md model resolution order; model-effort-O3, O5, O7; Measured here: promptfoo three-model extraction A/B, 60/60 each (one fixture class); #840 Haiku trial; Designed, not measured: J4 tiering (Opus census, Haiku sample, sealed 5% Opus re-read)
- **Notes:** Model choices are the owner's; this row is a recommendation. The M7 effort sweep (high, xhigh, max on our tasks) is owed.
- **Supersedes:** R52 (Ultracode is a separate toggle since 2.1.284); AN-05 (`sonnet` resolves to Sonnet 5.5); M7 extended with Anthropic's published effort priors
- **Overturn when:** The M7 sweep shows a lower effort at quality parity for a task class, or max scoring below xhigh; or a newer model release.
