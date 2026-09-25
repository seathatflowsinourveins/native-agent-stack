# Decision: this PC's Claude Code user profile as the catalog's new-PC baseline (2026-09-23)

**Decided by:** unit `claude-user-profile`, its own dedicated worktree,
branch `claude/claude-user-profile-20260923` (base `origin/main@95f8cb72`).

**Scope:** the machine-readable Linux/macOS pins for the `claude-code` client itself
(`adoption/pins-linux-x86_64.json`, `adoption/pins-macos-arm64.json`), the two platform
bootstrap scripts' new native-install path, the shipped user-scope profile assets
(`adoption/hooks/claude/`, `adoption/agents/claude/`, `adoption/mcp/claude-user.json`),
the settings template (`adoption/templates/claude.settings.template.json`) and the new
apply/install tooling (`tools/adoption/apply_claude_settings.py`,
`tools/adoption/install_claude_profile.py`). It reflects one specific live host
(this PC's user-scope Claude Code config) as evidence, not a claim that this is the only valid profile.

## Decision

1. **claude-code moves from an npm wrapper pin to a native pin (both platforms).**
   Evidence: the live host runs the native self-installing binary (`claude install
   2.1.280`, matching `~/codex-ecosystem/bin/bootstrap-linux.sh`'s own
   claude-code step), not the npm wrapper the prior 2.1.278 pin used. The native
   binary's linux-x64 sha256 was independently verified by downloading the actual
   binary and re-hashing it (`1e08503d...322925b`, matching both the task's given
   hash and the 2.1.280 release manifest). The darwin-arm64 checksum was cross-checked
   against `https://downloads.claude.ai/claude-code-releases/2.1.280/manifest.json`
   and, because this host cannot run the binary to prove the manifest's signature, was
   additionally confirmed by independently downloading the darwin-arm64 binary itself
   and re-hashing it byte-for-byte against the manifest's claim (`387a5c5d...055229d`
   — matches). The manifest's own `.sig` sidecar exists but this host has no published
   Anthropic public key or documented verification procedure for it, so the checksum
   is **byte-verified against the served artifact, not signature-verified**; recorded
   as a limitation in the pin's own `checksum_ref`, not hidden.
   **Overturn condition:** a documented Anthropic manifest-signature verification
   procedure and public key becomes available, or a future release's manifest
   checksum disagrees with an independently re-hashed download.
2. **DISABLE_AUTOUPDATER guidance is removed for claude-code.** The live host's
   settings carry `autoUpdatesChannel: "latest"` and no `DISABLE_AUTOUPDATER` env,
   and the native binary is explicitly designed to auto-update itself once installed.
   The pin is a floor (minimum version), not a pinned ceiling.
   **Overturn condition:** an observed native auto-update regression (a version
   change that broke a qualified workflow) on this or another host, recorded with
   the specific before/after versions.
3. **Opus 5.5 leads the coordinator/model tables; Fable 5.1 is the escalation.**
   Evidence: the live host's `~/.claude/settings.json` sets
   `modelSettings.claude-opus-5-5.effortLevel: "xhigh"` and the guard hook
   (`effort-default-guard.py`) exists specifically because a USER-scope top-level
   `effortLevel` stopped covering Opus 5.5 and later (Claude Code 2.1.251+,
   `https://code.claude.com/docs/en/settings-reference`, fetched 2026-09-23). Fable
   5.1's prior recorded qualification (coordinating a real multi-agent Workflow with
   Sonnet 5 and Opus 5 workers) is retained as the documented escalation path, not
   discarded, since Opus 5.5 has not yet been observed running that same graph shape.
   **Overturn condition:** a reproduced comparison on an actual multi-agent Workflow
   task showing Fable 5.1 (or another model) outperforms Opus 5.5 as coordinator, or
   Opus 5.5 itself is observed successfully running the same graph shape Fable 5.1 was
   qualified on.
4. **The settings template is updated to match the live host, apart from one
   documented, intentional difference.** `python3 tools/adoption/render_config.py
   --check` against the rendered template and the live `~/.claude/settings.json`
   shows byte-identical output except the two guard-hook `command` strings: the
   template quotes the script path (`python3 "${HOME}/.claude/hooks/effort-default-guard.py"
   ...`, matching this task's own literal specification, and safer for a `HOME`
   containing a space) while the live host's current file has it unquoted. This is
   recorded here rather than silently reproducing the live host's own unquoted form,
   since the quoted form is the more portable default for a new machine.
   **Overturn condition:** an observed real-world path with a space breaking the
   unquoted form (confirming the quoted default was necessary), or a decision to
   match live-host bytes exactly instead (in which case drop the quoting).
5. **Merge tool deep-merges rather than overwrites.** `tools/adoption/apply_claude_settings.py`
   merges a rendered template into a live `~/.claude/settings.json` (template scalars
   win; every nested object -- `modelSettings`, `env`, `permissions`, `enabledPlugins`,
   `statusLine` -- merges per key and lists union, so host-only rules and plugins are
   kept; `hooks` combine per event, de-duplicated across the whole event by each
   command's shell words, so the template's quoted guard path and a host's unquoted
   one are one hook; backups never overwrite an earlier backup) instead of replacing the file
   outright, because a live settings file on a real host commonly carries
   host-specific `env`/`modelSettings` entries (this host's own self-healed
   `claude-sonnet-5` entry, for example) that a naive overwrite would destroy.
   **Overturn condition:** a case where deep-merge produces an invalid or
   contradictory settings file that whole-file replacement would have avoided.
6. **Winners added to the Linux pins are Linux-only in this round.** `markitdown`,
   `tavily-cli`, `orx` (OpenResearch) and `agent-browser` were added to
   `adoption/pins-linux-x86_64.json` from this host's own installed versions, each
   independently re-downloaded and re-hashed against its own publisher's registry
   (PyPI dist digest, npm dist.integrity, or a GitHub release's own `.sha256`
   sidecar). `poppler` was investigated and found **not actually installed** on this
   host (only `poppler-data`, the encoding-data package, not `poppler-utils`'
   `pdftotext`/`pdfinfo`/`pdftoppm` binaries); rather than guess a version/hash for a
   package that is not present, it is recorded here as an open gap, not pinned. None
   of the four winners were added to `adoption/pins-macos-arm64.json`: this is a
   Linux/WSL2 host, so a macOS version/hash cannot be independently verified from
   here without guessing.
   **Overturn condition:** a macOS host (or CI runner) independently verifies and
   records the same four tools' darwin-arm64 hashes; a distro-appropriate
   `poppler-utils` apt/brew install is verified and this catalog gains a
   system-package pin mechanism to record it (none exists yet; see the pins'
   own `install_note` for why one was not invented here).

## Alternatives considered

- **Leave claude-code as an npm-wrapper pin, bump only the version number.**
  Rejected: it would no longer describe what this (or the reference
  `codex-ecosystem`) host actually runs, and the npm wrapper's own
  `platform_dependency`/postinstall-copy machinery exists specifically to work
  around npm's inability to verify a nested platform package — a problem the
  native binary does not have at all.
- **Whole-file settings replacement instead of a merge tool.** Rejected: destroys
  host-specific state (env vars, `modelSettings` for models the template does not
  mention, existing plugin/hook entries a person or another automated process
  added) that a new-PC bootstrap should preserve, not erase.
- **Guess the macOS winners' pins from the Linux versions.** Rejected: a version
  number is not evidence of a matching darwin-arm64 hash; recording an unverified
  guess would be worse than recording the gap honestly (`docs/acceptance-evidence-policy.md`).
- **Invent a generic apt/brew "system-package" pin kind to cover poppler.**
  Rejected as out of this task's bounded scope: no existing convention for
  distro-package SHA-256 verification exists in this catalog (apt's own signing is
  the trust boundary `bootstrap-linux.sh`'s fixed system-package list already
  relies on), and poppler is not even installed on this host to describe. Left as
  a documented gap rather than a speculative mechanism.

## Later decisions

- [`max` effort for every Claude child, Ultracode for the main loop](2026-09-23-max-effort-default.md)
  (2026-09-23): the shipped `adoption/agents/claude/` definitions now declare
  `effort: max` beside their task-matched models, and this repository commits a
  project `.claude/settings.json` that turns Ultracode on. Decision 3's coordinator
  (Opus 5.5 at `xhigh`) is unchanged.

## Addendum (2026-09-25): jCodeMunch registers per project, not at user scope

**Decided by:** unit `jcodemunch-project-scope`, branch
`claude/jcodemunch-project-scope-20260925` (base `origin/main@b82b4e06`).

**Decision.** [`adoption/mcp/claude-user.json`](../../adoption/mcp/claude-user.json) drops its
`jcodemunch` entry, so `tools/adoption/install_claude_profile.py` registers only `ai-memory` and
`serena` at user scope. [`adoption/bootstrap.md`](../../adoption/bootstrap.md) step 4a still
installs `jcodemunch-mcp==1.108.319`. It now documents a per-project opt-in: `claude mcp add
--scope local` for one user, or a checked-in `.mcp.json` entry for a whole project. This changes
where the server is registered. No catalog verdict or component record changes.

**Evidence** (2026-09-25, one WSL2 host, Claude Code 2.1.282):

- **The instruction loads everywhere.** A registered jCodeMunch server sends this instruction
  into the session: "This repo can be indexed by jcodemunch. Its whole tool catalog sits behind
  a 3-verb front door. Prefer it over Read/Grep/Glob/Bash for code navigation." At user scope
  that happens in every project. It contradicts agent-lab's lane routing (its `AGENTS.md`:
  `rg` for discovery and focused text search, Serena for symbols and references). This
  catalog's [handbook](../token-session-handbook.md) routes code symbols to "Serena or scoped
  jCodeMunch", and a per-project registration fits that.
- **Use.** Counted as unique `tool_use` ids on 2026-09-25, the host's 5,076 retained Claude Code
  transcripts (the oldest from 2026-09-18) hold 15 jCodeMunch calls, against 33 for Serena and
  7 for SocratiCode. The 5,059 of them modified since 2026-09-20 hold 15, 25 and 6.
- **Retrieval quality.** agent-lab's executed retrieval comparison
  (`docs/tasks/2026-09-22-executed-comparisons.md`) ran 20 sealed questions over a 30-file
  corpus, 3 repeats. SocratiCode scored span hit@5 0.85 and MRR@10 0.742; jCodeMunch scored
  0.25 and 0.148. jCodeMunch cannot index Markdown (8 of the 30 files). On the preregistered
  coverage-parity subgroup SocratiCode still led, 1.00 to 0.40. Closure stays `unresolved`
  only because SocratiCode's `restore_pass` was null, and the sealed rule treats a null on
  either arm as unresolved. The comparison supports this change; it does not retire
  jCodeMunch.
- **Host change.** On 2026-09-25 the host ran `claude mcp remove jcodemunch -s user`, and its
  `~/.claude.json` user-scope `mcpServers` now name only `ai-memory` and `serena`. It kept a
  backup of the removed entry in its codex-ecosystem state
  (`state/settings-audit-20260923/jcodemunch-user-scope-entry.json`). agent-lab keeps its
  local-scope entry: `claude mcp get jcodemunch` there reported `Local config (private to you in
  this project)` and `✔ Connected`.
- **Both opt-in forms, measured** under a temporary `CLAUDE_CONFIG_DIR` and scratch
  `CODE_INDEX_PATH`, so the host's config and jCodeMunch ledger were untouched. These are local
  integration checks on one host; their command output stayed in that session's scratch
  directory and is not retained in this catalog:
  - `claude mcp add --scope local jcodemunch -e ... -- <prefix>/bin/jcodemunch-mcp` exited 0.
    `claude mcp get` reported `✔ Connected` in that project and `No MCP server named
    "jcodemunch"` in another. One of three `get` runs crashed in Bun (segfault, exit 139); the
    other two exited 0.
  - The documented `.mcp.json` entry, with `${HOME}` in `command` and `env`, stayed `⏸ Pending
    approval` until the scratch workspace was trusted and the server approved in
    `.claude/settings.local.json`. It then reported `✔ Connected`, and the server wrote its
    index state under the expanded `CODE_INDEX_PATH`.
  - A nested default, `${ECO_INSTALL_ROOT:-${HOME}/...}`, did not expand: `✘ Failed to
    connect`.
  - The [MCP documentation](https://code.claude.com/docs/en/mcp) (fetched 2026-09-25) gives
    `${VAR}` and `${VAR:-default}` expansion in `command`, `args`, `env`, `url` and `headers`,
    the approval step for `.mcp.json` servers, and local > project > user precedence.

**Alternatives considered:**

- **Keep jCodeMunch at user scope.** Rejected. Its contradicting instruction reached every
  session, yet 5,076 retained transcripts hold 15 calls to it. It also trailed SocratiCode in
  the retrieval comparison.
- **Drop the install step, or drop jCodeMunch from the catalog.** Rejected. The
  [retained receipt](../../evidence/receipts/native-jcodemunch-20260920.json) shows byte-exact
  symbol retrieval, the comparison above is unresolved, and an opted-in project needs the
  pinned install.
- **Also remove the `route` and `order` grants from the shipped `evidence-reviewer` and
  `isolated-builder` agents.** Not done here. The grants resolve only where a project registers
  the server, and a project without it still launches the agents
  ([workflow examples](../../examples/claude-native/workflows/README.md)). That stays a
  separate keep-but-compare choice, overturned by the condition below.

**Overturn condition:** a measured task class where jCodeMunch beats `rg`, Serena and
SocratiCode, or regular jCodeMunch use in projects beyond agent-lab. Either would put it back in
the user-scope template.

**Limitations:**

- One host, one account and one Claude Code release.
- The use counts are observational counts from local transcripts, not a controlled trial.
- The comparison has n=20 on one corpus with no power calculation, and it compares retrieval
  only. Serena was not an arm.
- The installer only visits the servers the template names. A host registered from an earlier
  template keeps its user-scope `jcodemunch` entry until `claude mcp remove jcodemunch -s user`
  removes it.
