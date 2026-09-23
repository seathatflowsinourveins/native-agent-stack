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
   and re-hashing it byte-for-byte against the manifest's claim (`387a5c5d...2925b`
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
   win; `modelSettings` and `env` merge per key; `hooks` combine per event,
   de-duplicated by each hook's own `command` string) instead of replacing the file
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
