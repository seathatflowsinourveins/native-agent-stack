# Decision: token-stack release review; upstream integration paths differ from ours, and Mac pins move with Mac qualification (2026-09-29)

**Decided by:** session `os-b4` on host `mac-coordinator-64gb-20260925`, for the user's direction of 2026-09-29: "the repos upstream itself is
sourceof truth, how to install adapt them need to be sota upstream aligned, otherwise the trail e2e practice itself cannot be the evidance, the
truly upstream deep dived clean install is needed". It follows the token-stack winner record (#508). This record is a review and a sequence; the
sequence in the last section is this session's recommendation, not a user decision.

**Scope:** this record only. It reads each member's upstream, records what upstream supports for install and client integration and which
tests and evals it ships, and sequences pin moves. It changes no pin file, bootstrap script, client setting, carrier text or install, and it
executes no member. Lane: `lane:foundation`.

## What changed from the plan

The approved plan proposed refreshing the Mac pin file in this slice. The repository's own invariant prevents that. Mac pins equal the Linux
pins except for lags recorded in `MAC_PIN_LAGS_LINUX` (`tests/test_adoption_bootstrap_macos.py:255-266`), each tied to a Linux qualification
receipt, because "the Mac keeps its own qualified version until a Mac qualifies the new one". A Mac-only bump would fail
`test_shared_components_keep_the_linux_pinned_version` or edit the lag table without a Mac qualification. So the pin file moves with each
member's Mac qualification, and members where upstream is ahead of both hosts move Linux first. The user's requirement stands: the trial e2e is
evidence only on an upstream-aligned install, and the alignment gaps below are what the clean install closes.

## Method

Read on 2026-09-29 at the tags named in Sources: upstream README, changelog or release notes, and package manifest scripts. Latest releases came
from `gh release view`. For Serena, tool classes in `src/serena/tools/*.py` were compared at v1.7.0 and at the pinned commit. Nothing was
executed.

## The five members with an integration gap or a pin decision

### Serena: channel differs, pin decision

- **Pin and latest:** `2.0.0.dev0 @ c6fbd1c5` (a 2026-09-18 merge commit) on both hosts; latest release v1.7.0 (2026-08-09); GPL-3.0-or-later.
- **Upstream supports:** `uv tool install -p 3.13 serena-agent` (PyPI), `serena init`, then a client launch command from its client docs. Its
  `docs/04-evaluation` holds an evaluation methodology, prompts and results for Claude Code, Codex and other clients.
- **Here:** `uv tool install git+https://github.com/oraios/serena@c6fbd1c5`. The recipe says "Upstream declares `2.0.0.dev0`; the commit is the
  identity" and records no reason for a dev commit (`recipes/README.md:109`).
- **Comparison:** the pinned commit has one tool class more than v1.7.0 (`SerenaReplTool`), and it adds an `EditApiMixin` base to the editing
  tools, an internal change this comparison does not characterize. All 24 Serena tools a session here uses exist at v1.7.0.
- **Recommendation:** both hosts move to `serena-agent==1.7.0`, unless a recorded reason keeps the dev commit. Linux qualifies first because the
  pin is shared.

### SocratiCode: integration path differs

- **Pin and latest:** 1.14.0 on the Mac, 1.15.0 on Linux; latest v1.16.0 (2026-09-28); AGPL-3.0-only.
- **Upstream supports:** native plugins are the recommended path. Claude Code: `claude plugin marketplace add giancarloerra/socraticode`, then
  `claude plugin install --scope user socraticode@socraticode`. Codex: `codex plugin marketplace add giancarloerra/socraticode --ref main`, then
  `codex plugin add socraticode@socraticode`. The plugins bundle the MCP server, workflow skills and agent instructions; a direct MCP install has
  the engine only, and a duplicate standalone server is removed with `claude mcp remove socraticode`. The default needs Docker for Qdrant and
  Ollama; on macOS a native Ollama gives Metal, and `QDRANT_MODE=external` uses an existing Qdrant.
- **Here:** standalone MCP registrations in the Claude user scope and in the Codex config, so upstream's skills and instructions are not
  installed.
- **Changes 1.14.0 to 1.16.0:** no breaking change is listed. 1.15.0 lets the plugin's engine specification be pinned and fixes PHP graph edges;
  1.16.0 adds an opt-in Git-triggered refresh and setup guides.
- **Upstream tests:** vitest unit, integration and e2e suites (`npm run test:unit`, `test:integration`, `test:e2e`); e2e needs Docker, Qdrant and
  Ollama.

### QMD: Claude Code integration missing on this Mac

- **Pin and latest:** 2.8.3 on both hosts, equal to the latest release (2026-08-16); MIT.
- **Upstream supports:** `npm install @tobilu/qmd` (Node 22 or newer; on macOS Homebrew SQLite for extension support); MCP tools `query`, `get`,
  `multi_get`, `status`; for Claude Code the plugin is recommended (`claude plugin marketplace add tobi/qmd`, `claude plugin install
  qmd@qmd`). Models download on first use.
- **Here:** the CLI comes from the earlier install prefix and QMD is registered as an MCP server for Codex only. It is not in the Claude user-scope
  MCP registry or the plugin list on this Mac (project-scoped `.mcp.json` files were not inspected), although
  `adoption/agents/claude/stack-researcher.md:4` grants `mcp__qmd__*` and the token carrier tells agents to load it. That is a candidate cause
  for low Claude-side QMD use, to be tested in the root-cause step.
- **Upstream tests:** `npm test` (types, vitest on Node, tests on Bun) and `npm run test:package`, a packaging smoke test.

### RTK: version current, Codex path to verify

- **Pin and latest:** 0.50.0 on both hosts, equal to the latest release (2026-09-24); Apache-2.0.
- **Upstream supports:** Homebrew (recommended), an install script, `cargo install --git` and release binaries; `rtk init -g` installs the
  Claude Code PreToolUse hook; `rtk init -g --codex` installs a Codex PreToolUse hook that rewrites input (`updatedInput`) plus an `AGENTS.md`
  block.
- **Here:** the release tarball with publisher checksums, which is an upstream artifact. The Claude hook matches upstream. Codex uses explicit
  `rtk` commands and the Codex worker lane's global `AGENTS.md` block (`docs/token-practice.md:44-52`).
- **To verify:** RTK documents `updatedInput` for Codex, while Context Mode's compatibility table lists Codex hooks as unable to modify
  arguments. Only a test on the installed Codex decides whether the explicit-command adaptation stays.
- **Upstream tests:** Rust unit tests via `cargo`; upstream CI runs `cargo build --release` and `cargo audit`.

### Context Mode: aligned on Claude Code

- **Pin and latest:** 1.0.169 on both hosts, equal to the latest release (2026-06-29); Elastic-2.0 (source-available).
- **Upstream supports:** the Claude Code plugin marketplace (recommended: `/plugin marketplace add mksglu/context-mode`, `/plugin install
  context-mode@context-mode`); for Codex a plugin with `plugin_hooks`, or a manual fallback (`npm install -g context-mode`, `[features] hooks =
  true`, `[mcp_servers.context-mode]`, and a `hooks.json` calling `context-mode hook codex ...`).
- **Here:** the Claude plugin at 1.0.169. The `context-mode-cache-heal.mjs` SessionStart hook is deployed by the plugin itself, for
  anthropics/claude-code#46915, and is not a local addition. The coverage check reports the Codex plugin enabled.
- **Upstream tests and evals:** `npm test` (vitest, with a build first) and `npm run benchmark`, `test:use-cases`, `test:compare`,
  `test:ecosystem`; its `BENCHMARK.md` lists 21 scenarios.

## Other members

Equal to the latest official release on 2026-09-29, so no move: markitdown 0.1.8 (2026-09-21), ccusage 20.0.26 (2026-09-27), repomix 1.18.1
(2026-09-21), toon 4.1.1 (2026-08-05), jcodemunch-mcp 1.108.319 (2026-09-16; in `manifests/stack.json`, with no Mac pin entry yet), ast-grep 0.45.3
(2026-08-31; not in the Mac pin file), claude-code 2.1.284 (2026-09-28).

Behind:

- **mcporter:** Mac 0.13.13, Linux 0.14.1 = latest (2026-09-24). 0.14.1 fixes daemon `--log-servers` filtering, hides Windows console windows and
  refreshes dependencies. The Mac lag is recorded; it moves after its own qualification.
- **headroom:** 0.37.0 on both hosts; latest v0.39.1 (2026-09-26). 0.39.0 adds a description of what CCR compression dropped, a `protect_messages`
  hook that vetoes compression per message, and exact cache-read cost in savings rollups. Its proxy token-rate limiter could refuse
  large-context requests indefinitely, fixed in 0.39.1. The target is 0.39.1, never 0.39.0. Linux qualifies first.
- **codex:** Mac 0.155.1, Linux 0.157.1; latest rust-v0.159.0 (2026-09-29). The roadmap records a deliberate hold
  (`docs/decisions/2026-09-28-ecosystem-roadmap.md:334`); the Mac qualifies 0.157.1 first under #382.
- **ai-memory:** Mac 2.3.2, Linux 2.4.1 = latest v2.4.1 (2026-09-25); production is a local 2.5-pre build. Not decided here.

## Recommended pin sequence

1. No move for members equal to the latest official release.
2. The Mac catches up to a Linux-qualified pin, each with its own Mac qualification receipt and its lag entry removed in the same change:
   mcporter 0.14.1, socraticode 1.15.0, codex 0.157.1.
3. Upstream ahead of both hosts: Linux qualifies first with the upstream suites (the pattern of #446), then the Mac. Serena `serena-agent`
   1.7.0, headroom 0.39.1, socraticode 1.16.0.
4. Integration-path changes are decided in the clean-install slice against upstream docs at the target pin: the SocratiCode plugins, the QMD
   plugin for Claude Code, the Context Mode plugin for Codex, and RTK's Codex hook.
5. A failed qualification keeps the last qualified pin and records the failed step and its output.

**Handoff:** the workstation coordinator owns the Linux pins and their qualification. Serena 1.7.0, headroom 0.39.1 and socraticode 1.16.0 are
mirrored as a comment on the pull request that carries this record. No carrier, role body or Gate A window input changes here.

## Alternatives considered

- **Refresh the Mac pin file now.** Not chosen: it breaks the Mac and Linux pin invariant or changes the lag table without a Mac qualification.
- **Move every pin to the latest release without qualification.** Not chosen: the freshness policy upgrades only after release review and
  acceptance, and a newer release is information, not a reason.

## What would overturn this

- A Mac qualification of a target version that passes upstream's suite and the use-stage receipts: that member's pin moves in that change.
- A recorded reason to keep Serena's dev commit, such as a behavior the release lacks.
- A Codex 0.157.1 test showing that RTK's `--codex` hook works, which retires the explicit-command adaptation.

## Limitations

- Upstream documents were read at the tags in Sources and nothing was executed. Statements such as RTK's Codex hook and Context Mode's Codex
  compatibility are upstream claims, unverified on this host, and they conflict.
- The Serena comparison counts tool classes in source at two refs. It does not show runtime behavior between the release and the dev commit.
- Licenses are as each project declares them, not a legal review. Latest-release facts are as of 2026-09-29.

## Sources

- Upstream at the named tags: [rtk v0.50.0](https://github.com/rtk-ai/rtk/tree/v0.50.0),
  [context-mode v1.0.169](https://github.com/mksglu/context-mode/tree/v1.0.169), [serena v1.7.0](https://github.com/oraios/serena/tree/v1.7.0) and
  commit [c6fbd1c5](https://github.com/oraios/serena/commit/c6fbd1c5932df2494ffa0020af5a9fbe80b82143),
  [SocratiCode v1.16.0](https://github.com/giancarloerra/SocratiCode/tree/v1.16.0) with its `CHANGELOG.md`,
  [qmd v2.8.3](https://github.com/tobi/qmd/tree/v2.8.3), [headroom v0.39.1](https://github.com/headroomlabs-ai/headroom/releases/tag/v0.39.1),
  [mcporter v0.14.1](https://github.com/openclaw/mcporter/releases/tag/v0.14.1).
- Latest releases read with `gh release view`: markitdown, ccusage, repomix, toon, jcodemunch-mcp, ast-grep, codex, claude-code, ai-memory.
- Repository at `origin/main` `df412368`: `tests/test_adoption_bootstrap_macos.py`, `adoption/pins-macos-arm64.json`,
  `adoption/pins-linux-x86_64.json`, `manifests/stack.json`, `recipes/README.md`, `docs/token-practice.md`,
  `adoption/agents/claude/stack-researcher.md`, `docs/decisions/2026-09-28-ecosystem-roadmap.md`.
