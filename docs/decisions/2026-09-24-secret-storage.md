# Decision: secret storage for seamless pickup without exposure (2026-09-24)

**Scope:** where every credential this stack uses lives on a host, how later
sessions find it, and which repository guards keep values out of Git, GitHub
and agent commands. This decision extends
[`2026-09-22-broker-credential-handling.md`](2026-09-22-broker-credential-handling.md)
and does not replace it. The operator runbook is
[`../secret-storage.md`](../secret-storage.md), and the inventory is
[`../../adoption/credential-inventory.json`](../../adoption/credential-inventory.json).

## Context

These facts were verified on 2026-09-24 from source, docs or `stat`. No value
was read.

- Only the callers of `runner.py` fail closed on file mode, owner and location.
  Five consumers still read the Alpaca pair from environment variables (item
  A1 of the 2026-09-24 community sweep).
- The repository is public, and GitHub secret scanning and push protection are
  enabled on it. CI runs gitleaks 8.30.1. No local pre-commit gate was active,
  and there was no project `.claude/` guard.
- The repository's gap-wave2 measurement on codex-cli 0.155.1 found
  broker-prefixed variable names in the launcher environment on 2026-09-23.
  It also found that only `shell_environment_policy.inherit = "none"` removed
  them from Codex shells.

## Decision

1. **Store:** one plaintext file per provider at
   `${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack/<provider>.env`. The
   files are `0600` inside a `0700` directory, owned by the user, outside every
   worktree, and hold `export NAME=value` lines. Repository code parses these
   files and never sources them. The SEC contact recipe is the documented
   exception. The self-generated Grafana and nativestack secrets stay where
   they are, because they already meet the rule. Native sign-ins (Claude,
   Codex, gh, IB Gateway) stay in each tool's own store and are never copied
   between hosts. CI secrets stay in GitHub.
2. **Pickup:** the shell startup file exports only pointer variables
   (`PAPER_ENV_FILE`, `SEC_CONTACT_ENV`, `PIT_*_ENV_PATH`). Existing recipes
   take `--env-file "$PAPER_ENV_FILE"` unchanged. A loader that defaults to the
   conventional path is a follow-up.
3. **Inventory and checker:** `adoption/credential-inventory.json` lists names,
   classes, lanes, status, path templates and loaders, and never values.
   `scripts/credential_status.py` checks the host against it using `lstat`,
   the Git index and environment variable names only, and never opens a
   credential file.
4. **Git side:** `.gitignore` covers `.env*`, `*.env`, `*.key`, `*.pem` and the
   native-store basenames. A tracked `scripts/git-hooks/pre-commit` runs
   `gitleaks git --pre-commit --staged --redact` and fails closed when gitleaks
   is missing. It is activated per clone with `core.hooksPath`. The CI scans
   and push protection stay in place. Nothing is ever committed encrypted.
5. **Agent side:** a tracked `.claude/settings.json` holds deny rules only, plus
   the `scripts/hooks/secret_path_guard.py` PreToolUse hook. Both are
   described as guards against **accidental** exposure, not as a boundary.
   The same deny rules also go into user settings, as a host step. For Codex,
   the host step is `[shell_environment_policy] inherit = "core"` (documented),
   or `"none"` (measured), and it must be re-measured with the canary probe.

| Class | Store | Loaded by |
| --- | --- | --- |
| Alpaca paper pair | `<store>/alpaca-paper.env` | `--env-file` parsers (runner, market_research, collect_daily, mover-early-entry, extreme-gainer-audit, pit-availability). Five environment-only consumers wait on A1 |
| SEC contact (personal data) | `<store>/sec-contact.env` | sourced by the catalyst-provenance recipe; parsed by pit-availability |
| Databento, Typesafe, OmniRoute | `<store>/<provider>.env`, created only when used | each consuming process, and only that process |
| Grafana admin and nativestack key | unchanged, `0600`, self-generated | systemd `EnvironmentFile=` (recorded inconsistency); host service |
| Claude, Codex, gh, IBKR | native stores, or an interactive login | the tool itself |
| Actions secret and `github.token` | GitHub | workflows |

## Threat model, stated plainly

The earlier draft of this decision called the deny rules "the hard floor".
That is withdrawn. The Claude Code permissions docs (fetched 2026-09-24) say
Read/Edit deny rules do not apply to "arbitrary subprocesses that read or write
files indirectly", and that Bash rules are "not a security boundary around the
program". An agent running as the same uid in `bypassPermissions` mode can
therefore still read the paper keys, for example with a Python one-liner that
calls a loader through `$PAPER_ENV_FILE`. The hook test suite records that
command as an expected pass-through rather than claiming to stop it. Codex has
no documented per-path read deny.

The decision accepts this residual risk for **paper-only** keys. Live keys are
out of scope.

The only OS-level floor is the Claude Code sandbox (`sandbox.enabled`,
`allowUnsandboxedCommands: false`, `credentials.files` deny). It is deferred
until a measured profile exists. The measurement has to include the network
allowlist, gh, git push, codex and the paper runner, and has to show that
sandboxed commands cannot reach the user systemd bus.

Recorded boundaries: Windows-side reads over `\\wsl.localhost`; values in a
child's environment, which the same uid can read through `/proc/<pid>/environ`
and `ps e`; and output-retaining stores (transcripts, RTK recall, context-mode,
ai-memory, OTEL tool-content logging). Incident handling purges these.

## Measured (local integration class, 2026-09-24)

- Checker and hook unit tests run against temporary fixtures that hold
  synthetic sentinel values. The tests assert that the sentinels never appear
  in output, and that the checker never opens a store file.
- The pre-commit gate test uses a temporary repository and a synthetic
  AWS-shaped key generated at test time. The gate blocked the commit with the
  key redacted, a clean commit passed, and the gate failed closed with no
  gitleaks on `PATH`.
- `.claude/settings.json` validates against the schemastore
  `claude-code-settings.json` schema (draft-07, 0 errors).
- Headless Claude Code 2.1.281 runs in `bypassPermissions`, with the Haiku
  model, harmless probes only:
  - `printenv` was blocked by the deny rule;
  - `ls` of the store path was blocked by the hook;
  - the Read tool on a gitignored `.env.probe` was denied;
  - **`cat .env.probe` ran despite `Read(.env.*)`**, with or without the `!`
    carve-outs. That contradicts the docs' statement that `cat` is covered, so
    the hook now blocks readers on `.env` files.
- The runbook's synthetic fail-closed check was run: `runner.py preflight` on
  a `0644` synthetic file exited 3 with `error_type: SafetyError` and no value
  in the output.

Not tested: the sandbox, Codex environment policy changes, the user-level
snippets, macOS, and any real credential.

## Alternatives rejected

- **sops+age ciphertext committed to the repository:** the repository is
  public, so the ciphertext would be published permanently for offline attack.
  The age identity is itself a same-user plaintext key. It would add two tools
  to guard about four secrets.
- **direnv or `.envrc`:** exports secrets into every shell and every agent
  session started in the directory.
- **Exports in shell rc files:** leak through `/proc/<pid>/environ`, `ps` and
  every child process. Codex passes `*KEY*`, `*SECRET*` and `*TOKEN*` names
  through by default. This was already rejected on 2026-09-22.
- **systemd-creds:** the host runs systemd 255, which has no `--user`
  encryption, and there is no TPM on WSL2 and no macOS equivalent.
- **OS keychain, or pass/GPG:** WSL2 has no Secret Service. An unlocked
  keychain or a cached gpg-agent decrypts for any process of the same user.
  A keychain would also break parity between WSL2 and macOS.
- **1Password CLI:** paid, and it still injects values into the environment.
  **Bitwarden Secrets Manager:** its access token has to be stored locally,
  which moves the same problem one level up.
  **OpenBao:** unjustified for one operator.
- **One combined env file:** every process would load every secret.
- **Push protection alone:** reacts only after the fact, covers only known
  patterns, and is free only while the repository is public.

## Evidence that would overturn this decision

- A paper or live runner runs unattended as a user unit on systemd 256 or
  later: measure `systemd-creds --user` with `LoadCredentialEncrypted=`.
- One secret is shared by several hosts or services, or there is more than
  one operator: re-evaluate Bitwarden Secrets Manager or OpenBao.
- An agent reads a credential value despite the guards: enable the measured
  sandbox profile and route agent-started runs through fixed, user-owned
  units.
- gitleaks, push protection or secret scanning finds a listed value in any
  history.
- The repository becomes private: the pre-commit gate becomes the primary
  control, and paid Secret Protection gets costed.
- Claude Code stops applying deny rules in `bypassPermissions`, or stops
  loading project hooks. Codex removes `inherit` or changes its default.
- The checker's assumptions about `stat` and uid fail on macOS APFS.

## Evidence class

`local_integration`, plus a docs and source review. No provider was called
and no credential value was read.
