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
   The same deny rules and the same hook ship in the managed Claude user
   profile: `tools/adoption/install_claude_profile.py` installs the hook
   (sha256-pinned in `adoption/hooks/claude/SHA256SUMS`) and the settings
   template carries the rules and the hook registration, so the documented
   installer deploys them on every new host. The hook searches reader and
   search commands for secret variable names and credential files, and blocks
   shell tracing or environment dumps around sourcing a credential file.
   For Codex, the host step is `[shell_environment_policy] inherit = "none"`
   plus explicit non-secret `set` entries, the only value the repository
   measured to remove every broker variable. `"core"` is documented but
   unmeasured. This setting controls environment inheritance, not file reads.

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
ai-memory, and OpenTelemetry/Loki whenever a Claude Code content flag is
on). Incident handling purges these, and a key pasted into a prompt or passed
through a tool call is rotated. `credential_status.py --client-guards`
reports the content flags as booleans. On 2026-09-24 this host had telemetry
on and all five content flags explicitly false in `~/.claude/settings.json`;
the earlier statement that tool-content and raw-body logging were enabled is
withdrawn. Keeping them off while broker keys exist is recommended and is the
user's decision.

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

- The extended hook has a test per blocked form (secret-name searches,
  `git grep`, `find -exec` readers, `*.env` files, tracing while sourcing,
  environment dumps after sourcing, `/proc` environ spellings) and a
  66-command negative corpus of ordinary repository and shell work.
- The profile tests install both hooks into a temporary home, check that
  `SHA256SUMS` verifies like `sha256sum -c`, and run the rendered template
  hook through `sh`: it exits 0 while the guard is not installed and blocks
  with exit 2 once it is.

Not tested: the sandbox, Codex environment policy changes (the Codex
evidence is the gap-wave2 canary receipt), a live Claude session with the
user-level hook, macOS, and any real credential.

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

## Addendum 2026-09-25: Hugging Face native sign-in

**Decision.** The Hugging Face token stays in `hf`'s own store, like the other
native sign-ins. The operator runs `hf auth login` in their own terminal on
each host and pastes a fine-grained token made for that host, with read
access to public gated repositories only. The inventory lists both files `hf`
writes: `huggingface-native` for `$HF_HOME/token` and
`huggingface-native-stored` for `$HF_HOME/stored_tokens`. Their template uses
huggingface_hub's own default,
`${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}`, which the checker
now expands. `HUGGING_FACE_HUB_TOKEN` joins `HF_TOKEN` in `must_not_be_set`.
`HF_TOKEN_PATH` stays unset, and the checker reports it by name. The guard and
the deny rules cover `hf auth token`, both files, and reads through `$HF_HOME`
or `$HF_TOKEN_PATH`. Agents use the sign-in only through `hf`, for
revision-pinned downloads and checksum verification. The runbook section is
[Hugging Face sign-in](../secret-storage.md#hugging-face-sign-in).

**Verified** from the installed huggingface_hub 1.32.0 source and the same
files at the upstream `v2.0.0` tag, commit
`97c5f5f2030c2df01b60548f7d357970a106cd7d` (the annotated tag object
`90b2aaf9889bb098d8fca575687ec8be02508959` dereferenced to that commit; read
only, via `gh api repos/huggingface/huggingface_hub/git/ref/tags/v2.0.0` then
`git/tags/<that object sha>`, both fetched 2026-09-25). Token precedence is
OIDC, then `HF_TOKEN`, then `HUGGING_FACE_HUB_TOKEN`, then the file. Both files are written `0600`
and their directory is set to `0700`. `hf auth token` prints the token. The
paste login reads the token with `getpass` and never writes a git credential;
only an explicit `--add-to-git-credential` (with `--token`, or on
`hf auth switch`) does. The browser login
requests a device code with only the client id and saves the refresh token it
gets back.

**Alternatives rejected.**

- A file in the private store (`<store>/huggingface.env`) loaded as
  `HF_TOKEN`: every consumer would hold the value in its process environment,
  and huggingface_hub consumers already read the native file.
- The default browser login: its OAuth token's permissions are not the
  operator's choice, and a refresh token is stored beside it.
- One token shared by all hosts: one revocation would stop every host.
- Denying `hf` as a whole: agents need `hf download` and `hf cache verify`
  for revision-pinned acquisition.

**Would overturn it.** huggingface_hub moves tokens into an OS keyring or
changes their paths or modes; an agent obtains the value despite the guard,
in which case gated downloads move to operator-only runs; or Hugging Face
offers a narrower token than fine-grained read access to gated repositories.

**Evidence class.** Docs and source review plus `local_integration` unit tests
with synthetic sentinel files. No token was created, read or used.
