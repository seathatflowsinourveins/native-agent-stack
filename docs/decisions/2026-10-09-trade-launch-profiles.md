# Trade profiles launch fresh worktrees with the locked runtime

The Trade terminal profiles need to open a new US-equities project session with
the selected runtime already synced. The generic WSL profiles still serve their
existing project and resume pickers; Trade has a separate project placeholder.

The checked-in Windows Terminal fragment adds `Trade - Claude` and
`Trade - Codex`. `<TRADE_PROJECT>` is the US-equities repository path in WSL;
`<PROJECT>` remains the generic profiles' project. `<DISTRO>` and `<WSL_USER>`
retain their existing meaning. Host-specific values are applied by the CC, with
the host fragment's backup and inverse, rather than committed here.

Each Trade launch follows the installed upstream commands:

1. Fetch `origin/main` from the Trade project directory.
2. `wt switch --create` creates a `foundation/trade-<client>-<UTC>-<pid>` branch
   from `origin/main`. The timestamp and launcher process ID keep simultaneous
   tabs distinct; no branch/session is resumed automatically.
3. Worktrunk's `-x sh -- -c` starts a thin shell in that new worktree. It runs
   `uv sync --locked` and then replaces itself with the native client. Sync
   failure ends the launch before the client starts.

The branch prefix follows the US-equities repository's existing foundation
branch contract. The profile invokes the client directly and assigns no hcom
lane tag. It does not attach to ns-movers, ns-seeds or paper-open-e2e. The generic
five profiles and their resume ordering remain intact.

Trade Codex supplies `-c model_reasoning_effort=max -c service_tier=priority`.
The selected model remains the client's configured model. The installed
0.161.0 schema supports explicit `priority`; official documentation records
that the older `fast` spelling maps to that request value. These settings are
per-launch arguments and do not rewrite a user configuration.

Trade Claude uses the native interactive client after sync, removing inherited
`ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` variables without reading their
values. It retains the existing truecolor/tab/bell policy. No model API key,
custom sandbox, permission policy, security workflow or subscription-funded
headless process is introduced. The CC performs any real Claude launch and
Claude-family read under the standing launch rule.

T1 owns the runtime dependency group and its default selection: a plain
`uv sync --locked` must install that delivered runtime. T4/T5/T6 own the MCP,
plugins and skill copies that native clients discover from the Trade worktree.
The profile does not embed alternate installations, runtime paths or skill
registries. These environment changes do not add a north-star protocol landing
condition, and this change does not edit UET's frozen CI or protocol files.

## Lifecycle and host acceptance

The CC's host acceptance launches each profile once, records the initial
`uv sync --locked` elapsed time, and confirms a fresh worktree and no fixed hcom
lane identity. The delivered runtime imports `nautilus_trader`, `alpaca`,
`edgar` and `duckdb`; the session lists the selected skills/plugins and performs
one permitted MCP call with no commands typed by hand. Local fixture-client
tests prove the launch sequence, cwd, distinct worktrees and sync-failure
behavior; they are not a Windows Terminal or authenticated native-client run.

After the session has ended, the CC/operator cleans up its selected merged
Trade worktree with `wt remove <branch>`. For an explicitly idle, clean
unmerged Trade tree, `wt remove --no-delete-branch <branch>` preserves the
branch. Worktrunk keeps its default dirty-tree checks; this change adds no
background cleanup hook, forced deletion or process-reaping command. Active
lane worktrees and protected paper work are not cleanup targets.

## SOTA sources

- Installed **Worktrunk v0.80.0**, [max-sixty/worktrunk at
  b49ca7eea9b03145791a5b94eccaf9c59412ed37](https://github.com/max-sixty/worktrunk/tree/b49ca7eea9b03145791a5b94eccaf9c59412ed37).
  `wt switch --help` and `wt remove --help` verify the supported create/base,
  execute-program/argument, cwd and cleanup interfaces. Official
  [switch](https://worktrunk.dev/switch/) and
  [remove](https://worktrunk.dev/remove/) documentation fetched 2026-10-09.
- **OpenAI Codex 0.161.0**, pin
  [979011409de0a60b52f179721948e65531d26144](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/config.schema.json).
  Installed `codex --version`, versioned config schema and official
  [CLI overrides](https://developers.openai.com/codex/cli/reference/) and
  [configuration reference](https://developers.openai.com/codex/config-reference/),
  fetched 2026-10-09, establish the effort/service-tier arguments. Availability
  and actual model-request execution remain the host acceptance boundary.
- **Astral uv**, installed 0.12.22;
  [official `uv sync` CLI](https://docs.astral.sh/uv/reference/cli/#uv-sync),
  fetched 2026-10-09. `--locked` checks the existing lock; the native runtime
  group, managed Python and package pins are delivered by the trading runtime
  slice, rather than reselected in a terminal profile.
- [Microsoft Windows Terminal JSON fragment extensions](https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions),
  fetched 2026-10-09. The existing fragment/profile format, generated GUID
  behavior, visibility, title and bell settings are retained.

The design uses Worktrunk's shipped worktree/execution lifecycle and uv's
shipped sync command. A small command composition in the existing fragment is
sufficient; no replacement launcher framework, hcom process launcher or
runtime manager is built.
