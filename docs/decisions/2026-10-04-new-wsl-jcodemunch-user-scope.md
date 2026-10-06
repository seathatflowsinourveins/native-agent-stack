# Decision: jCodeMunch is registered at user scope on NativeStack2604 (2026-10-04)

**Decided by:** the user, on 2026-10-04, in reply to a note of the You-should-know side agent ("The new WSL registers the
jCodeMunch code-lookup tool per project, so new projects and worktrees start without it ... Decide which you want:
per-project setup, or one registration for all projects on the new WSL"): "we need to set up all the sota repos, mcp
tools, harness rules, upstream cc native hooks and beyond, resolute them cleanly for future session to make sure their
seamless pick up and thier native workflow enhanced with the sota practice". The command center (session
`wsl-architecture-design`) read it as the choice of one registration for every project and agreed; session
native-agent-stack-99's unit U8 carried it out.

**Scope:**

- `adoption/new-wsl/templates/claude-user.mcp.additions.json` and `codex.config.additions.toml`: the server, at user
  scope, with its env block;
- `adoption/new-wsl/client-config-map.json`: the `code-index` slot entry for it;
- the note of the install plan's `code-index` row, the builder tests, the counts of
  `docs/decisions/2026-10-02-new-wsl-client-configuration.md` and two lines of `docs/token-session-handbook.md`.

## Decision

NativeStack2604 registers `jcodemunch` once, at user scope, for Claude Code and for Codex, while the `code-index` slot
installs jcodemunch (`jcodemunch-mcp 1.108.319`). Every fresh session on the host then starts with the tool connected, in
a new project and in a new worktree alike.

- **NativeStack:** its Claude Code already has the server at user scope (`claude mcp get jcodemunch`: "User config
  (available in all your projects)", connected), with the opt-out below and three local switches that turn off context
  providers, git blame and AI summaries; those three are not carried, so 2604 keeps upstream's defaults for them. Its Codex
  config does not register the server yet: the shared Codex user template carries the entry now, and registering it on
  NativeStack is one of the host steps of the NativeStack-clean record.

- **Registration:** the pinned README (jgravelle/jcodemunch-mcp at 8f7b34ab, README.md L119-122) documents
  `claude mcp add -s user jcodemunch jcodemunch-mcp` after `uv tool install jcodemunch-mcp`. Codex gets
  `[mcp_servers.jcodemunch]` with the same console script.
- **Savings counter:** upstream's default is an anonymous savings counter (README.md L225). Its documented opt-out is
  `JCODEMUNCH_SHARE_SAVINGS=0` in the server's env block (CONFIGURATION.md L229-233 and SECURITY.md L311 at the same
  revision), which both registrations carry, as the per-project registration did.
- **The Codex entry** is the one `adoption/templates/project.codex.config.template.toml` registers per project, at user
  scope: a 60 s start-up allowance, `enabled_tools` naming the three verbs of the front door (`route`, `menu`, `order`),
  and `default_tools_approval_mode = "approve"`, because the tools carry no MCP annotations and a `never` policy refuses
  an unapproved call. The approval mode is an authorization piece: written only with `--with-authorization-settings`,
  and only while the `code-index` slot installs jcodemunch.
- **Not run:** `jcodemunch-mcp init`, which writes enforcement hooks and a prompt policy into the client.
- **Shared templates:** this record first registered the server through the 2604 additions only. The NativeStack-clean change
  (`docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md`, decision 6) moves the same entries into
  `adoption/mcp/claude-user.json` and the Codex user template, because the repository's tests make the two user-scope sets mirror
  each other, so every host that installs the profile from the shared templates now gets the server; the per-project forms of
  `adoption/bootstrap.md` remain for a project that wants its own registration. The record counts moved to 404 pieces, 354 wired, 35 not wired and
  15 authorization, and the carrier entries that the same decision removes from the map bring them to 393 pieces, 354 wired,
  24 not wired and 15 authorization (the builder's `--check` at that head).

## The cost, measured

The Harbor E2E of 2026-09-30 (Harbor 0.23.0, 36 SWE-bench Verified tasks, every tool installed as upstream documents it,
Claude Code 2.1.285 with Sonnet 5.5 at effort medium, one repetition; frozen at
`~/.local/state/native-agent-stack/harbor-e2e-20260929`, RESULTS.md) measured the jcodemunch arm at **1.387 times the
cost of the lean arm** (95% CI 1.230 to 1.553, Holm p = 0.0006), a resolve rate of 0.750 against 0.778 (no significant
difference) and the tool used in 33 of 36 trials. Two limits of that number:

- the arm was upstream's faithful adoption, `init` with its hooks and prompt policy; this record registers the server
  without `init`, a configuration that was not measured (the earlier bare-registration pilot used the tool in 2 of 7 trials);
- it covers single-session tasks on Sonnet 5.5 at medium effort; long sessions, large monorepos and Opus at max effort
  were not tested.

The command center re-runs the A/B at the operating point (Opus 5.5 at max effort, Claude Code 2.1.289, current tool
releases); its result decides which tools stay in the default at all.

## What it overturns, for this distribution

- the addendum of 2026-09-25 in `docs/decisions/2026-09-23-claude-user-profile.md` ("jCodeMunch registers per project, not
  at user scope"): the server's instruction ("Prefer it over Read/Grep/Glob/Bash for code navigation") now reaches every
  session, which that record found contradicts the catalog's own retrieval routing, and its use was 15 calls against 33 for
  Serena and 7 for SocratiCode in 5,076 transcripts;
- decision 2 of `docs/decisions/2026-09-25-codex-mcp-scope.md` and F6 of `docs/decisions/2026-09-26-token-practice-f1-f9.md`
  ("jcodemunch stays project-scoped").

Those reasons still describe real costs. The user's directive, that every fresh session starts with the tools ready, ranks
above them.

## Alternatives considered

- **Per project** (the earlier rule, and finding F1 of the independent read of PR 684): a new project starts without the
  tool, and Claude Code's local scope is keyed to the path, so each worktree needs its own registration.
- **A checked-in `.mcp.json` per repository:** covers a repository's worktrees, not a new project, and is a decision for
  every lane that owns a repository.
- **`jcodemunch-mcp init`:** the measured arm; not run.

## What would overturn it

The user's instruction to remove a tool, or to narrow its scope, in the default. The command center's A/B at the operating
point informs that instruction; it does not change this record by itself.
