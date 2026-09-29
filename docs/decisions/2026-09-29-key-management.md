# Decision: key management, part 1: every key of record in its 0600 store file, the kernel keyring as transport only (2026-09-29)

**Scope.** Where a provider key of record lives on a host, and the first change
of the D1 key-management design: before a planned kernel restart, the one key
that lived only in the kernel keyring (Tavily) moves into the file store. This
record extends [2026-09-24 secret storage](2026-09-24-secret-storage.md), whose
file store it keeps, and replaces the 2026-09-26 memory-only placement of
Tavily. The runbook is [`../secret-storage.md`](../secret-storage.md), the
inventory is
[`../../adoption/credential-inventory.json`](../../adoption/credential-inventory.json).
Later changes of the same design append dated sections at the end; the change
that adds the key injector amends this record. Built on branch
`claude/key-tavily-persist-20260929`, stacked on PR #481 (base `b40b3596`).

## Context

Verified on 2026-09-29 from source and tests. No value was read.

- The kernel keyring is memory only. `scripts/kernel_keyring.py` stores a
  `user` key named `native-agent-stack:<name>`, and a kernel restart erases it
  (on WSL2: `wsl --shutdown`, a Windows restart or update, or the idle VM
  stopping; [Lifetime](../secret-storage.md#kernel-keyring-transport-and-per-boot-spare-2026-09-29)).
  A restart of the workstation is planned for the evening of 2026-09-29.
- One inventory key lived only there: `tavily` (`tavily_api_key`, the
  operator's 2026-09-26 decision). The Alpaca paper pairs are in 0600 files;
  their keyring copies (`alpaca-paper-{1,2}-{id,secret}`) are duplicates that
  the restart erases, and this change leaves them alone.
- `kernel_keyring.py exec <name> <VAR> -- <command>` starts the command with
  its own environment plus exactly one credential-named variable
  (`_exec()`), so a writer started that way receives the key without an
  agent, a prompt or a command line seeing it.
- The guard hook's `check()` passes the exact chain command below at this
  branch's base; `tests/test_secret_path_guard.py` now pins it in `ALLOWED`,
  and `test_documented_keyring_commands_pass` checks the copy in the runbook.

## Dated reading of the user's instructions

Dated reading (2026-09-29, designer 1, for the coordinator):

- On 2026-09-29 the user said "the key can be store with env so no key is
  loss" and "handle the key with seamless sota env practice always" (the
  coordinator's design brief). These state a rule for every key.
- They post-date the 2026-09-26 memory-only placement of Tavily. They also
  post-date the 2026-09-28 "don't store in files" for the keys pasted in chat
  (the Alpaca pairs), which the user already reversed by moving both pairs
  into 0600 files.
- **Reading:** Tavily moves to the 0600 file store, and the keyring keeps at
  most a per-boot spare. The design's root research unit called the two
  instructions conflicting and left the move to the user; this reading
  resolves the conflict by recency and by the user's stated goal that no key
  is lost.
- **Overturn:** if the user restates memory-only for Tavily, the row reverts
  to `kernel_keyring`, now carrying the `memory_only_lost_on_restart`
  warning, and the file is removed by the user or by a tracked removal tool
  built at that time.

## Decision

1. **Store of record.** Every key of record is a `0600` file of
   `export NAME=value` lines in the `0700` store
   `${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`, as decided on
   2026-09-24. Tavily's row becomes `private_env_file` `<store>/tavily.env`,
   still optional; it is rotated with
   `tools/credentials/open_credential_terminal.sh tavily`.
2. **The kernel keyring is a transport only.** `kernel_keyring.py exec`
   hands a key to one command, and a key stored there is a spare that lasts
   until the next kernel restart. No key of record lives only there, and a
   required `kernel_keyring` row is an inventory error in
   `scripts/credential_status.py`, which `scripts/validate.py` and
   `set_credential.py` also run. New keys never go through the keyring.
3. **The one move from the keyring into a file**, run once by the
   coordinator after review, before the restart, from a checkout whose
   inventory already lists the file:

   ```sh
   python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- python3 -I -S tools/credentials/set_credential.py tavily --from-env
   ```

   `set_credential.py --from-env`, built from the existing writer:
   - refuses unless both `sys.flags.isolated` and `sys.flags.no_site` are
     set, and never re-executes in this mode. The check runs before the
     module's re-exec block, because whatever ran at start-up ran beside the
     value: `-I` ignores `PYTHONPATH`, the `PYTHON*` variables and the user
     site directory, and `-S` also skips `site`, which runs the `.pth` lines
     of the interpreter's own `site-packages` even under `-I` (the
     coordinator's independent review of the first version, which accepted
     `-I` alone);
   - stores only an entry that declares exactly one variable, because a
     pair's provenance cannot be proven from an inherited environment;
   - pops the variable, then refuses an absent, empty or out-of-grammar
     value with the existing `encode()` rules;
   - is create-only: an existing name is refused before anything is
     written, even before `open_store()` could create the store or tighten
     its mode, and the final `os.link` fails with `EEXIST` rather than
     replace a file that appeared in between;
   - writes its temporary file as a dot-file (`.tavily.env.<16 hex>.tmp`),
     which a kill before the link leaves behind; the checker lists it as
     `undeclared_store_file` and never counts it as the stored key;
   - prints only `tavily: stored`.

   The store directory checks are the existing `open_store()`.
4. **The checker** reports a `kernel_keyring` row as `unchecked` with
   persistence `memory_only` and the warning `memory_only_lost_on_restart`,
   and lists, by name only, store files that no row claims
   (`undeclared_store_file`) and live `native-agent-stack:*` keys of the uid
   that no row claims (`undeclared_keyring_key`, from `/proc/keys`). Both
   are warnings.
5. **Not in this change.** A loader that reads the Tavily file, units that
   use such a loader, the Claude native mask and Codex proxy injection
   layers, and a canary harness belong to later changes of the design. The
   paper units and the paper env files are unchanged. Until a loader lands,
   Tavily works through the keyring copy until the restart and then has no
   key; Tavily is not the default web lane, so that gap is accepted.

## Alternatives considered so far

- **dotenvx `run`** (dotenvx 2.31.1, GitHub release of 2026-09-27; the
  binary's checksum matched the release's `checksums.txt`). *Measured* on
  2026-09-29 against this store format, with a synthetic canary in a scratch
  directory (the coordinator's session notes `kw/spike-dotenvx.md`, not in
  this repository): it loads `export NAME=value` lines, bare and quoted;
  redaction is opt-in (`--redact`) and covers raw values only; without `-q`
  its banner prints the env file's full path on stderr; and `run` executed a
  `$(...)` placed in a hand-edited value. It would still need a shim
  (inventory id to file, declared variables only, always `-q`, refuse values
  holding `$`, a backtick or a backslash) and a pinned per-platform binary,
  and it does not change where the key of record lives, which is the
  restart problem. Not adopted here; its redactor design is a reference for
  a later masker.
- **The kernel keyring alone** (`scripts/kernel_keyring.py`, the 2026-09-26
  placement). Memory only, so a key held only there is lost at every kernel
  restart and has no durable record. Kept as a transport and a per-boot
  spare.
- **systemd `LoadCredential=`** (systemd.exec(5), current documentation for
  systemd 262). It reads a credential from a file path or an `AF_UNIX`
  socket into the unit's read-only `$CREDENTIALS_DIRECTORY`, backed by
  non-swappable memory where possible. It needs a source file, so it changes
  how a unit receives a key, not where the key of record lives: mitigating
  only. The 2026-09-29 research sweep reports plain `LoadCredential=` working
  in user units on this host's systemd 255.4-1ubuntu8.17; this record does
  not re-measure that, and the paper units stay unchanged.

## Evidence class

- *Local integration*, synthetic values in temporary stores:
  `tests/test_credential_tools.py` (`StoreFromEnvTests`, twelve tests, and
  the second paper account's prefix hint) and
  `tests/test_credential_status.py` (the tavily file row, memory-only rows,
  the required-row error and both coverage lists). Each new behaviour failed
  before its implementation, except the dot-file name of the temporary file,
  which the first version already had and a mutation pins. Eight mutations
  of the writer are each caught by the intended test: abbreviations allowed,
  `os.replace` for `os.link`, re-execution instead of refusal, no pop, no
  isolation check, a temporary name without the leading dot, no pre-write
  existence check, and `-I` accepted without `-S`.
- *Controls*: a `sitecustomize` module on `PYTHONPATH` runs, and sees the
  variable, in a start without `-I`, and not under `-I -S`. In a throwaway
  venv, a `site-packages` `.pth` line records each interpreter start: a plain
  start records one non-isolated start that saw the value (so nothing was
  re-executed), `-I` alone records an isolated start that saw the value (the
  reason `-I` alone is refused), and `-I -S` records nothing and stores the
  file.
- *Upstream source and documentation*: the `/proc/keys` line format from
  linux v6.18 `security/keys/proc.c` (`proc_keys_show()`) and
  `security/keys/user_defined.c` (`user_describe()`); Python's `-I`
  (implies `-E`, `-P` and `-s`) and `-S`
  (<https://docs.python.org/3/using/cmdline.html#cmdoption-I>, `#cmdoption-S`);
  systemd.exec(5) for `LoadCredential=`.
- *Measured once in a session scratch directory, no committed receipt*: the
  dotenvx spike.
- *Not yet observed*: the chain on the host, the checker's `/proc/keys`
  parser against a real kernel's key list (the tests use a fixture in the
  upstream format), and the kernel restart itself.

## Known limits

- `-I -S` stops start-up code from a poisoned environment and from
  `site-packages`, but not a modified standard library: on a uv-managed
  Python under the home directory the same uid can write that too. That uid
  can already read the keyring and the store directly, so the threat model
  is unchanged.
- Popping the variable keeps it from any child of the writer, but Linux
  still shows the start-up environment in `/proc/<pid>/environ` to the same
  uid and root while the short writer runs, as for every `exec` command.
- A temporary file left by a kill holds the value until the operator
  deletes it; the checker names it, but nothing removes it automatically.

## Overturn

- The user restates memory-only for Tavily: the row reverts as in the dated
  reading above.
- A store that keeps a key through a kernel restart without a same-uid
  plaintext file and without a password or a per-session unlock (the user's
  2026-09-28 passwordless decision), for example `systemd-creds --user` with
  `LoadCredentialEncrypted=` on systemd 256 or later, is measured on this
  host: compare it with the 0600 file on restart survival, unattended use,
  same-uid readability and agent exposure.
- Any part of a value is found in a transcript, log or tool output after a
  `--from-env` run: stop using the mode, rotate the key, and type keys only
  through `open_credential_terminal.sh`.

## Boot receipt (2026-09-29)

The second restart safeguard of the same design (D1 PR-3), built on branch
`claude/key-boot-receipt-20260929`, stacked on the change above (base
`76ade87c`). The runbook is
[Restart check](../secret-storage.md#restart-check-2026-09-29).

**Decision.**

1. `scripts/credential_boot_receipt.py record` writes one value-free receipt
   per start of the user's service manager, to
   `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/credential-boot/<UTC stamp>-<boot id prefix>.json`:
   a 0600 file in a 0700 directory, written as a `mkstemp` dot-file and
   linked into place, so no receipt is ever replaced. It prints one line of
   counts. The receipt holds the boot id, uptime, systemd version, linger
   (`loginctl show-user --property=Linger`), the checkout revision, the
   checker's rows reduced to ids, statuses, store kinds, path templates,
   states, findings and warnings, each file row's `lstat` mode, size and
   `mtime_ns`, the coverage names, the names of this uid's live
   `native-agent-stack:*` keys, and `claude_user_guard_matches_pin`.
2. `compare` diffs the latest two receipts by state and by the names of
   changed fingerprint fields. It exits 1 when a required or optional file
   row that was `ok` is no longer `ok` or has no row, 2 without a readable
   receipt, and 0 otherwise; a single receipt is reported as the baseline.
3. `adoption/templates/systemd/credential-boot-receipt.service` runs `record`
   as a `Type=oneshot` wanted by `default.target`, from `@REPOSITORY@`, which
   the workstation renders to its live clone as it does for its other units:
   never the working checkout, whose revision moves, and never a build
   worktree, which a merge deletes. With linger on it runs at every
   user-manager start with no login and no unlock. It has no `Environment=`,
   `EnvironmentFile=` or `LoadCredential=` line. It is rendered by hand with
   the repository's existing `@REPOSITORY@` convention; no render tool was
   added.
4. `credential_status.py --client-guards` gains
   `claude_user_guard_matches_pin`: the sha256 of the installed user-scope
   guard against the guard's line in the checkout's
   `adoption/hooks/claude/SHA256SUMS`. The guard is opened with `O_NOFOLLOW`
   and hashed only when it is a regular file, so the check opens no store
   file even through a planted link; only the boolean leaves it.

**From the leak-path review.** The local receipt keeps each file's size,
which shows a truncated or emptied file. No printed, sanitised or published
form carries it, because a one-variable file's size gives its value's
length: `compare` names changed fields and never prints their values. No
content hash of any kind is recorded, because a hash of a short or guessable
value, such as the SEC contact identity, is an offline test for it. A
temporary or dot file that a killed writer leaves in the store is listed by
name in the `undeclared_store_file` warning, and so in the receipt.

**Alternatives.**

- A content hash per file would also catch a changed value of the same size
  and mtime, but it is the offline test above; rejected.
- A login hook or a `.profile` line runs only after a login, which the
  restart check must not need.
- `LoadCredential=` or an environment file for this unit: the unit needs no
  value, so it is given none.

**Evidence class.**

- *Local integration*, synthetic stores in temporary directories:
  `tests/test_credential_boot_receipt.py` (14 tests: the key allowlist;
  canaries absent in raw, base64, hex, percent-encoded and hashed forms from
  the receipt, the printed line, stderr and `compare`; modes; no replacement;
  the ok-to-missing, ok-to-unsafe and vanished-row regressions; a restart
  compared by name and state; the `-I` re-run; the unit pin; the runbook
  commands under the guard) and `tests/test_credential_status.py` (the pin
  boolean). Each new behaviour failed before its implementation, and twelve
  mutations of the tool are each caught by the intended test.
- *Text check of the unit*: its directive list is pinned, and
  `systemd-analyze --user verify` on a rendered copy exited 0 on this host
  (systemd 255.4). Nothing was installed, enabled or started.
- *Not yet observed*: the unit on the host, a receipt written at a real boot,
  and the restart itself. The Mac form, a `RunAtLoad` LaunchAgent, is
  documented, not run; `boot_id` is null there.

**Overturn.**

- A real restart where `compare` misreports a file that survived, or where
  the oneshot has not run before the first session: fix the comparison or
  the unit's ordering, and record the observation.
- A store that keeps keys through a restart without a same-uid plaintext
  file (the overturn above) replaces the file rows whose fingerprints this
  receipt compares.
