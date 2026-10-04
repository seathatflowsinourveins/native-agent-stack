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

## Addendum 2026-10-04: launcher grammar of GNU and uutils coreutils

**Decision.** The guard reads a launcher the way both coreutils
implementations do, because Ubuntu 26.04 ships uutils (rust-coreutils 0.8.0,
with the multi-call binary `/usr/bin/coreutils`) as its coreutils.

- After `timeout`'s duration, both word readings step over the options and
  the `--` that uutils still reads there. `timeout 5 -- CMD` runs CMD on
  uutils and exits 127 on GNU.
- The current reading also reads:
  - an unambiguous prefix of a long option of `timeout`, `nice`, `stdbuf`
    and `env` (`--sig`, `--adj`);
  - env's value options of both implementations (`-a`/`--argv0`,
    `-f`/`--file`, `--env0-from`);
  - an env cluster that a value letter ends (`-vu NAME`);
  - `coreutils UTIL` as `UTIL`.
- The prior reading keeps c26800f3's env table, so a command refused
  before stays refused. A replay of 6,582 commands (test strings, fenced
  documentation lines and blocks, a launcher matrix) against the base
  guard found 0 loosened, 0 reason changes and 0 documented commands newly
  refused.

**Verified** from sources read 2026-10-04, cited in the guard beside each
table:

- uutils `src/uu/timeout/src/timeout.rs`, where `uu_app` sets
  `.trailing_var_arg(true)` (line 177 at 0.8.0, 171 at 0.10.0, 173 at 0.12.0)
  and `.infer_long_args(true)`;
- uutils 0.8.0's `env.rs`, `nice.rs`, `stdbuf.rs`, `nohup.rs`,
  `src/bin/coreutils.rs` and `src/common/validation.rs`;
- GNU coreutils `src/timeout.c` (`getopt_long` with `"+fk:ps:v"`), `env.c`,
  `nice.c`, `stdbuf.c` and `nohup.c` at v9.7 and v9.12;
- the rust-coreutils 0.8.0-0ubuntu3 file list for resolute.

**Measured** with the official uutils 0.8.0 release binary (its sha256
matches the release's published digest) beside GNU 9.4, with only `echo` as
the started command:

- uutils runs `timeout 5 -- CMD`, `timeout -k 2 5 -- CMD`,
  `timeout 5 -s KILL CMD`, `timeout 5 -v CMD`, `env -a NAME CMD` and
  `env -f FILE CMD`, where GNU exits 127 or 125;
- both run the abbreviated forms and `env -vu NAME CMD`;
- both exit 127 for `timeout -- 5 -- CMD` and `timeout 5 -- -- CMD`;
- on Linux an argv0 override does not choose the multi-call binary's
  utility, because `binary_path` reads the executed path.

**Alternatives rejected.**

- Reading GNU's grammar alone leaves the uutils forms open on the new hosts.
- Refusing every `timeout ... --` blocks harmless commands such as
  `timeout 5 -- ls`.
- A separate K4 tightening would duplicate the walk that every rule,
  `find -exec`, the keyring exec and `rtk proxy` share.

**Would overturn it.**

- uutils drops `trailing_var_arg` or `infer_long_args` from these launchers.
- Either implementation adds a launcher option that takes a value.
- A documented command is refused only because of this reading.
  `timeout -- 5 -- CMD`, which runs nothing on either implementation, is
  refused on purpose.

**Open.**

- `env -S STRING` followed by more words.
- Long-option prefixes of the launchers outside coreutils (C sudo, xargs,
  time, ionice, the systemd launchers), which were not audited here.
  sudo-rs v0.2.15 matches long options exactly.
- GNU's single-binary `coreutils --coreutils-prog=NAME`, and other
  multi-call binaries.
- The lane counter in `examples/claude-native/workflows/child-usage.mjs`,
  which reads `timeout` the GNU way.

**Evidence class.**

- Pinned source review.
- `local_integration` unit tests, failing first at `f77a35eb`.
- A local differential replay.
- A local run of the release binary on Ubuntu 24.04.

Ubuntu 26.04 was not run here. The coordinator's measurement there (uutils
0.8.0 runs `timeout 5 -- CMD`, GNU 9.7 exits 127) is cited, not reproduced.

## Addendum 2026-10-04: PR #685 bounded repair

**Action served.** Protect credential output in the foundation's agent shell
hook, which supports the research and runtime work. This repair starts at
`385e3f6584d2524c8407d44a7a9ae0ddd1316cd1` and resolves the three P1 findings
and the reported P2 controls from that revision's review. A second authorized
round starts at `a7888d3107d5d5cec1868ca08b67522a026dda83` (round-one content
`f33afee2`, pin and registry `a7888d31`) and corrects the independent Opus
review's uutils findings, including an incorrect harmless-command allowance.

**Sources selected with search-first.** GNU coreutils `v9.12`
(`c0f8514d9891`), uutils coreutils `0.8.0`, `0.10.0` and `0.12.0`, and glibc
`glibc-2.42`, read on 2026-10-04. The installed GNU env reports `9.4`;
that version observation is separate from the pinned source review. GNU's
`v9.12` NEWS identifies its September 14 stable release. No dependency or
host installation was changed. The existing diagnosing-bugs and tdd skills
fit this repair; the agreed seam is `check()` in the existing unittest module.

- [GNU timeout.c](https://github.com/coreutils/coreutils/blob/v9.12/src/timeout.c#L522-L565)
  stops option parsing before the duration. Both parser paths now preserve
  the following hyphen-leading executable path, including `-/printenv`,
  while retaining the uutils post-duration option/separator reading.
  [glibc execvpe.c](https://github.com/bminor/glibc/blob/glibc-2.42/posix/execvpe.c#L81-L89)
  confirms direct execution when the path contains a slash.
- [GNU env.c](https://github.com/coreutils/coreutils/blob/v9.12/src/env.c#L603-L811),
  [uutils 0.8.0 env.rs](https://github.com/uutils/coreutils/blob/0.8.0/src/uu/env/src/env.rs#L558-L644),
  [0.10.0 env.rs](https://github.com/uutils/coreutils/blob/0.10.0/src/uu/env/src/env.rs#L575-L709)
  and [0.12.0 env.rs](https://github.com/uutils/coreutils/blob/0.12.0/src/uu/env/src/env.rs#L611-L749)
  define different option grammars. GNU getopt stops before assignment
  operands, accepts abbreviated long options and short clusters, and
  restarts option parsing after inserting split words before trailing argv.
  Uutils preprocesses the original argv before clap, continues after words
  containing `=`, and expands only literal `--split-string`, `-S`, `-vS`
  and `-vvS` prefixes. The target's 0.10.0 and reviewed 0.12.0 also consume
  separate payloads for those literal options. Clap accepts other inferred
  split spellings but discards their payload without expansion; no remaining
  program means an environment dump. Generated split options are likewise
  consumed by clap rather than recursively pre-expanded.
  The guard's current reading expands GNU argv; its prior reading provides
  the independent uutils backstop. Either refusal wins. Their literal string
  splitter handles quotes, ASCII whitespace, comments and env escapes from
  GNU env.c and [uutils split_iterator.rs](https://github.com/uutils/coreutils/blob/0.12.0/src/uu/env/src/split_iterator.rs).
  P2 acceptance: `env -vS "ls -l"` passes; `env --split "ls -l"` is refused
  because uutils dumps the environment. Invalid split strings and inherited
  variable expansion are refused as `env_split_unclassified`; the guard does
  not inspect inherited values. The prior raw env no-command backstop also
  remains to preserve main's refusals, including conservative refusals of
  supported split syntax without a separate command operand.
- [GNU coreutils.c](https://github.com/coreutils/coreutils/blob/v9.12/src/coreutils.c#L145-L176)
  specifies `--coreutils-prog=NAME` and `--coreutils-prog-shebang=NAME`.
  The guard reads the selected utility and its arguments, discarding the
  shebang's script operand. The existing `find` file-reader check recognizes
  the selected reader without copying each action's remaining argv.

These changes close the earlier addendum's split-string and GNU dispatch
open notes. The other launcher families remain outside this bounded repair.

**Returned local evidence.** All command strings are inert test input; no
refused launcher command or credential file was executed or read.

- The three new test methods fail against the exact starting guard with
  111 failing subtests and no errors: timeout 39, env 48, dispatch 24.
  They pass with the repair. The first smaller fixture set produced 90
  failing subtests; those runs are separate, not cumulative counts.
- Follow-up controls first exposed three failed `find` dispatch subtests
  and six failed env option/assignment-state subtests. Both are fixed and
  retained in the same methods. Ordinary `README.md` reads and harmless
  split-string commands serve as negative controls.
- The plain local `python3 -m unittest tests.test_secret_path_guard` run
  returned one installed-hook parity failure (88 tests, two skips).
  The user-scope hook predates this branch. The repository suite passes in
  its existing CI mode, which skips that host-install comparison. The host
  copy is not changed in this owned worktree repair.
- The branch/job did not retain the original ad-hoc 6,582-command replay
  script or full corpus. A native Python unittest adapter replays 3,028
  frozen fixture/document commands from `385e3f65`, plus 33 review rows
  and P2 controls: **3,061 distinct commands**, **114 newly refused**,
  **0 loosened**, **0 reason changes**, **0 errors**, versus the PR's
  original main baseline `f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5`.
  Corpus SHA256: `5d8be2ac060d9435654e6a89e281021c0787be3c60ef4a3bf409d757fd39f2a4`.
  Against the intermediate starting head, the same corpus has 30 new
  refusals and two allowances, then classified as P2 false refusals.
  That round-one classification was incorrect for `env --split "ls -l"`;
  round two restores its refusal. This is a scoped replay, not reproduction
  of the historical count.

**Round-two returned evidence.** The GNU and uutils source readings are
distinct from execution on the target distribution; no new uutils host
acceptance is claimed.

- The final two env review methods fail against the exact `a7888d31` guard
  with **95 failing subtests, 0 errors**, and pass with this repair. The
  initial narrower rows produced 80 failing subtests; the counts are
  separate snapshots. The assignment cases cover `-S`, `-vS` and
  `--split-string=`, attached and separate payloads, nested env and wrapper
  calls, a file reader and a tracer. The two invalid `--split` allow
  controls are now refusal rows; `env -vS "ls -l"` remains allowed.
- The P2-4 row now includes a harmless trailing `EXAMPLE_OTHER`. At
  `385e3f65`, the old row is refused while the extended row passes; the
  repaired guard refuses the extended row as `environment_dump`.
- The first expanded replay exposed six round-one allowances that main
  had refused. Restoring the prior raw no-command backstop fixes them;
  harmless controls retain trailing operands where that backstop applies.
  The failed replay artifacts remain separate from the final result.
- The regenerated native unittest replay uses **3,028** fixture/document
  commands frozen at `a7888d31` and the actual inputs to all four current
  `test_review_685_*` methods: **3,257 distinct commands**. Against
  `f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5`, it returns **232 newly
  refused, 0 loosened**; against `a7888d31`, **95 newly refused,
  0 loosened**. Both comparisons have **0 reason changes, 0 errors**.
  Corpus SHA256:
  `8b075817aff195ca28e7d1fcc723517737b3732d5e83d4a7c8618762cf2fc028`.
- With `CI=true` and the requested `TMPDIR`, the full guard suite returns
  **89 tests, 3 skips, 0 failures**. CI skips the installed-hook comparison;
  two other skips are the existing mutation-driver adapter controls. The
  requested temporary directory is absent and outside this worker's
  writable roots, so Python uses its `/tmp` fallback. The host hook and
  temporary-directory configuration are not changed.

**Completeness check.** This round covers GNU abbreviated/clustered split
options, uutils literal prefixes, assignment continuation, original versus
generated argv, nested launchers and controls with trailing operands. It
retains the independent raw env fallback and the round-one timeout and GNU
dispatch protections. The original historical replay corpus and live target
host execution remain unavailable evidence; the scoped replay and pinned
source review do not substitute for them. The two proven testing/parser
mistakes are recorded in the [anti-pattern log](../harness-defaults.md#anti-pattern-log).
- The temporary repair artifacts retain the returned red/green logs and
  `replay.py` / `replay.json`. `python3 scripts/validate.py` is required
  after the final scoped evidence hash registration. It checks structural
  consistency separately from parser behavior.

**Repair anti-pattern log.**

| Proven mistake | Correction / source |
| --- | --- |
| Assuming every hyphen-leading word after timeout's duration is only an option | Preserve executable paths; GNU timeout and glibc direct-path execution |
| Treating an env split payload as an ordinary option value or one executable name | Expand literal argv and append trailing arguments; GNU and uutils split implementations |
| Inferring an environment dump solely because an option walk consumed a harmless split command | Locate the effective command and retain harmless controls |
| Assuming positional uutils dispatch covers GNU's single binary | Read both exact GNU dispatch spellings, including the script-operand difference |
| A draft fixture escaped quotes at the env grammar layer and named a different executable | Correct the fixture to quote the executable; retain the final starting-revision red run |

**Completeness critic and limits.** Both timeout parser paths, clustered and
abbreviated env forms with trailing argv, nested launchers, GNU's shebang
dispatch, and harmless controls are covered. The GNU
[env-S upstream tests](https://github.com/coreutils/coreutils/blob/v9.12/tests/env/env-S.pl)
were inspected as grammar references, not executed as upstream acceptance.
These results are `local_integration` checks and pinned source review;
neither Ubuntu 26.04 nor GNU's single-binary release was executed here.
Generic `find -exec` environment-printer detection is an existing separate
gap: its ordinary path classifies file readers. Invalid or inherited-value
split strings remain an explicit conservative refusal. Full original replay
availability and host-install parity remain coordinator follow-up conditions.
