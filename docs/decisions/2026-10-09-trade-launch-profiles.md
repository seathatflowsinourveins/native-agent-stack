# Trade profiles use the clients' native worktree sessions

`Trade - Claude` and `Trade - Codex` start from the US-equities **main checkout**,
bound by the CC to `<TRADE_PROJECT>` (the host's `~/code/us-equities-trading`).
The CC performs its one-time trust confirmation and applies the checked-in
Windows Terminal fragment with a backup and inverse. Native client worktree
sessions then own checkout creation, trust binding and lifecycle.

The external-worktree design at the first PR head is superseded by the CC's
2026-10-09 verdict. Claude Code's pinned changelog states that nested git
repositories no longer inherit parent trust; each repository needs its own
confirmation. Reusing the client's native worktree interface from the trusted
main checkout is the supported route. The profile no longer creates its own
worktree/branch, uses Worktrunk, or embeds a date-format `%` in the command line.

## Refresh and launch

The login shell checks `git status --porcelain`. Only a successful clean result
allows `git fetch origin main` followed by `git merge --ff-only origin/main`.
Dirty state, status/fetch failure or an unavailable fast-forward emits one line
and continues to the client in that same main checkout. Refresh output is
suppressed so the fallback stays finite. It never merges over local changes or
blocks client startup because a repository refresh failed.

- Claude: `exec env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN claude --worktree`.
- Codex: `exec codex --worktree -c model_reasoning_effort=ultra -c service_tier=priority`.

Claude's two inherited credential variables are removed without reading their
values. The selected model remains the client's configured model. Codex effort
matches the existing `adoption/templates/codex.config.template.toml` interactive
`ultra` default; there is no Trade-specific reduction to `max`. Priority remains
an explicit per-launch tier supported by the pinned client. No client session,
lane tag, custom launcher or permission policy is selected by the profile.

`<PROJECT>` still belongs to the original five generic profiles, which keep
their exact default/resume behavior. `<DISTRO>` and `<WSL_USER>` are unchanged.
`<TRADE_PROJECT>` points specifically to the trading main checkout rather than
a lane's worktree. Host paths and GUIDs are not committed.

## Runtime, cleanup and acceptance

There is no pre-launch `uv sync`. On first project use, `uv run --locked`
synchronizes the native session worktree's environment from its delivered
`pyproject.toml` and `uv.lock`; the runtime slice owns those package/default-group
pins. The CC records that first-sync elapsed time once during host acceptance.

Cleanup stays with the clients. Claude's `/exit` offers Remove worktree and,
at the pinned release, stops the servers/shells it started there before removal.
Codex uses its managed-worktree lifecycle; its pinned manager refuses deletion
of the current checkout or a checkout carrying local/ignored files. A startup
failure keeps its checkout and gives the native `git worktree remove` recovery
instruction. This record does not promise automatic deletion of every Codex
checkout. No cleanup script, forced deletion or external worktree manager is
added.

The CC's host facts are retained as reported observations: `wt`, `uv`, `claude`
and `codex` are on the login PATH; trading main has `pyproject.toml` and `uv.lock`
with dev/lint/validation groups; it has no `.config/wt.toml`. The profiles only
need Git and the native clients to start. Actual first-launch acceptance remains
with the CC: skills/plugins listed, `nautilus_trader`/`alpaca`/`edgar`/`duckdb`
import through the native project runtime, one permitted MCP call, and no manual
commands. This change makes no market-data call and adds no protocol landing
condition or frozen trading CI edit.

Local tests execute the exact shell with real Git and inert client executables.
They verify main-checkout cwd, native flags, clean fast-forward, dirty skips,
failed-fetch/non-fast-forward fallbacks, credential-variable removal, no lane
tag and no `%` in the command line. They are fixture integration, not a live
Windows Terminal/native-client/trust/runtime/MCP result.

## Versioned sources

- Installed **Claude Code 2.1.295**, selected login-PATH `claude --version` and
  TTY `claude --help`, read 2026-10-09: `-w, --worktree [name]` creates a new git
  worktree for the session. Piped help here omitted that option; TTY help and the
  pinned installed binary both contain it. No session was launched to inspect it.
- **anthropics/claude-code v2.1.295**, full commit
  `602df92bf481ed904533e95c09f740f40aab5aed`,
  [CHANGELOG.md:3215](https://github.com/anthropics/claude-code/blob/602df92bf481ed904533e95c09f740f40aab5aed/CHANGELOG.md#L3215)
  for per-repository trust,
  [CHANGELOG.md:801](https://github.com/anthropics/claude-code/blob/602df92bf481ed904533e95c09f740f40aab5aed/CHANGELOG.md#L801)
  for `/exit` worktree removal, and
  [CHANGELOG.md:6877](https://github.com/anthropics/claude-code/blob/602df92bf481ed904533e95c09f740f40aab5aed/CHANGELOG.md#L6877)
  for introducing `--worktree`/`-w`. Tagged changelog blob
  `bf5498e82d135de9021e53b4ead8be2d8f7e30e4` was fetched 2026-10-09.
- Selected login-PATH **Codex 0.161.0**, `codex --version`/`codex --help`, read
  2026-10-09: `--worktree` runs the session in a new managed Git worktree.
  Pin **openai/codex 979011409de0a60b52f179721948e65531d26144**,
  [config schema](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/config.schema.json),
  [native startup/trust recovery](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/tui/src/worktree_startup.rs#L47),
  and [native removal](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/worktree/src/lib.rs#L284).
  The selected 0.161.0 PATH command is the cited client; a newer direct-home
  executable found on this host is not substituted for that version.
- **Astral uv**, installed 0.12.22;
  [project command execution](https://docs.astral.sh/uv/concepts/projects/run/),
  fetched 2026-10-09, confirms that `uv run` updates the project environment
  before the command. `--locked` preserves the delivered lock boundary.
- Existing native fragment/profile format is retained from the first head.
  This revision's client behavior is bound to installed-version help and tagged
  source above rather than a changing live CLI documentation page.
