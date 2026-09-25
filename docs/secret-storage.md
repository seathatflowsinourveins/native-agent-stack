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
| `sec-contact` | SEC/EDGAR contact string. This is private personal data, not an auth secret | required now | `<store>/sec-contact.env` | `SEC_USER_AGENT` (optional: `EDGAR_IDENTITY`) |
| `databento` | Databento API key | only when you buy it | `<store>/databento.env` | `DATABENTO_API_KEY` |
| `typesafe` | Typesafe key, for the live-judge mode of `gap_crosswalk.py` only | only when you pay for it | `<store>/typesafe.env` | `TYPESAFE_API_KEY` |
| `omniroute` | OmniRoute local gateway key | optional | `<store>/omniroute.env` | `OMNIROUTE_API_KEY` |
| `grafana-admin` | Local Grafana admin account and secret key | generated locally | `~/.config/ecosystem-observability/ecosystem-grafana.env` | `GF_SECURITY_*` |
| `nativestack-generation-key` | Host service key | generated locally | `~/.config/nativestack/generation.key` | none |
| `claude-native`, `codex-native`, `gh-native` | Native sign-ins | stored by each tool | each tool's own store | none |
| `ibkr-gateway` | IB Gateway / TWS login | typed in at login, nothing stored | none | none |
| `github-actions` | `FOUNDATION_RESTORE_FIXTURE_20260920` and the per-job `github.token` | CI only | GitHub's encrypted secret store | none locally |

`<store>` means `${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`.

These should stay unset on the host, and child processes should never get
them: `GITHUB_TOKEN`, `GH_TOKEN`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`CODEX_API_KEY`, `HF_TOKEN`, `QDRANT_API_KEY`, `MASSIVE_API_KEY`, the alias
names `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`, `TWS_*`/`IBKR_ACCOUNT_ID`, and the
names that appear only in catalogs (`MISTRAL_`, `PREFECT_`, `MC_`, `MSB_`,
`PAPERCLIP_`, `OPENROUTER_API_KEY`). The checker lists any that are set, by
name only.

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
- **Stored keys:** `tools/credentials/set_credential.py <inventory-id>` accepts only operator-supplied entries (required, optional or paid) whose file sits directly in the store. It asks for each variable with hidden input, and refuses if the terminal cannot hide input. It writes `export NAME=value` lines atomically: a `0600` file in the `0700` store, outside Git, written through a directory handle opened without following symlinks. To replace an existing file you type `replace`, also hidden.
- **Paper rate limit:** `tools/credentials/alpaca_rate_limit_probe.py` sends one read-only `GET /v2/account` to the fixed paper host. It follows no redirect, reads no response body and places no order. It saves only the HTTP status and the `x-ratelimit-*` headers, under `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/rate-limit/`, where a later session can read them. `x-ratelimit-limit` is Alpaca's own per-account calls-per-minute figure (200 on the standard tier), so measuring it never needs order traffic. Agents may run it with `--env-file "$PAPER_ENV_FILE"`.

Live broker keys are out of scope for this repository. Live trading is handled outside it, and no tool here accepts a live endpoint.

## Picking up in a new session

Put the file paths, never the values, in your shell startup file once:

```sh
# ~/.bashrc or ~/.zshrc: pointers only; no credential value is exported
_nas_store="${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack"
export PAPER_ENV_FILE="$_nas_store/alpaca-paper.env"
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

While that child runs, any process running under your uid can read its
environment through `/proc/<pid>/environ` or `ps e`. Prefer the `--env-file`
consumers.

## Setting up a new host (WSL2 or macOS)

Values never go through an agent, a chat, a gist, GitHub or shell history.

1. Clone, then run `python3 scripts/adoption_status.py` and
   `python3 scripts/credential_status.py`. Both only inspect the host and change
   nothing.
2. Sign in natively yourself: run `claude`, `codex login --device-auth`,
   `gh auth login` and then `gh auth setup-git`. Start IB Gateway/TWS
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
   Linux/WSL2, install the native binary from the pinned release archive
   (`gitleaks_8.30.1_linux_x64.tar.gz`, checked against the release's
   `gitleaks_8.30.1_checksums.txt`; pinned in
   [`wsl-native-tools/pins.json`](../blueprints/convergence-practice/wsl-native-tools/pins.json)).
   Then install `ecosystem-bounded-run`, `gitleaks-guarded` and the `gitleaks`
   link beside them as in
   [`adoption/tools/README.md`](../adoption/tools/README.md#install-on-a-new-linuxwsl2-host).
   `gitleaks-guarded` runs `$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1/gitleaks`
   unless `GITLEAKS_NATIVE` names another path. An install that unpacked the
   binary to `tools/gitleaks-8.30.1/payload/gitleaks` needs either
   `GITLEAKS_NATIVE` or the relative link below. The link needs no environment
   change, so sessions that are already running use it too:
   ```sh
   ECO_INSTALL_ROOT="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
   # Only for the payload/ layout:
   ln -s payload/gitleaks "$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1/gitleaks"
   # Then, for every layout:
   command -v gitleaks                 # $ECO_INSTALL_ROOT/bin/gitleaks
   readlink "$(command -v gitleaks)"   # $ECO_INSTALL_ROOT/bin/gitleaks-guarded
   gitleaks version                    # 8.30.1; `version` execs the native binary and starts no scan
   ```
   On macOS, the bounded front end is `gitleaks-guarded-macos` (same README,
   macOS section). The hook calls `gitleaks` by name there too, so check what
   `command -v gitleaks` resolves to: a hook run that reaches the native binary
   is unbounded.

   **5b. Enable the hook** in each clone, which replaces `.git/hooks` for that
   clone, and run it once with nothing staged:
   ```sh
   git config core.hooksPath scripts/git-hooks
   scripts/git-hooks/pre-commit; echo "exit=$?"   # "no leaks found", exit=0
   ```
   That run shows the hook starts and exits cleanly with the `gitleaks` that
   5a checked. It scans nothing, so it is not evidence that the scan finds a
   secret.
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

## Threat model and what each guard stops

| Layer | Stops | Does not stop |
| --- | --- | --- |
| Store outside every worktree, plus `.gitignore` for `.env*`, `*.env`, `*.key`, `*.pem` and native-store names | committing a credential by accident | a value pasted into a tracked file |
| `scripts/git-hooks/pre-commit` (gitleaks on staged changes) | known secret shapes in a commit, before it is made | `--no-verify`; clones where `core.hooksPath` is not set; values with no recognizable shape |
| CI gitleaks (`validate.yml`), GitHub secret scanning and push protection (public repo) | pushes and history that contain known provider patterns | anything not yet pushed; custom formats. This layer only reacts after the fact |
| Project `.claude/settings.json` deny rules | Claude's Read/Edit tools on the listed paths; `printenv`, `env`, `gh auth token`, `git credential fill`, `gh auth git-credential` | Python or other subprocesses that open the files themselves; forms that do not match the rule text; sessions started outside this repository |
| `scripts/hooks/secret_path_guard.py` (PreToolUse, Bash; project settings and, through the profile installer, user settings) | commands that name a store path; read `/proc/*/environ` in any spelling; dump the environment; reference a secret variable; trace a process; print a native token (`gh auth token`, `--show-token`, and the credential-helper forms `git credential fill`, `git credential-<helper> get`, `gh auth git-credential` that `gh auth setup-git` enables); run a reader (`cat`, `sed`, `awk`, `jq`, ...) or search (`grep`, `rg`, `ag`, `ack`, `git grep`, `find -exec` with a reader) on a pointer variable, a `.env`/`*.env` file or a secret variable **name**; redirect a pointer variable into a command; turn on shell tracing or verbose mode (`bash -x`, `sh -x`, `set -x`, `set -v`, `set -o xtrace`) in a command that sources a credential file; dump the environment (`env`, `printenv`, `export -p`, `declare -p/-x`, inline `os.environ`) after sourcing one | a program that imports a loader and prints the result, obfuscated or renamed paths, a script file that sources and traces on its own, and anything else that is not literal text in the command |
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
agent read access to the **paper-only** keys as a residual risk. Live broker
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
withdrawn. The settings template sets all five to `"false"`, so
`apply_claude_settings.py` writes them off on a new host.

Recommendation, as a user decision: keep tool-content and raw-body logging
(and tool details) off for as long as broker keys exist on the host. Turning
any of them on is a deliberate choice to copy tool traffic into the local
store; the checker then reports `claude_telemetry_logs_content: true`.

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
(skipped in CI and on a host without it).

For a host that does not use the template, merge the same rules by hand under
`permissions.deny` in `~/.claude/settings.json`:

```json
"Read(~/.config/native-agent-stack/**)", "Edit(~/.config/native-agent-stack/**)",
"Read(~/.config/ecosystem-observability/*.env)", "Read(~/.config/nativestack/*.key)",
"Read(~/.claude/.credentials.json)", "Read(~/.codex/auth.json)",
"Read(~/.config/gh/hosts.yml)", "Read(//proc/*/environ)",
"Bash(printenv)", "Bash(printenv *)", "Bash(env)", "Bash(gh auth token *)",
"Bash(git credential fill*)", "Bash(gh auth git-credential *)"
```

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
  OAuth apps in GitHub settings.
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
- tracked files with credential-shaped basenames;
- whether `core.hooksPath` points at `scripts/git-hooks`;
- whether gitleaks is on `PATH`;
- whether the project guard file exists.

`--client-guards` parses `~/.claude/settings.json` and `~/.codex/config.toml`
and reports only booleans: user deny rules for the store, the user secret-guard
hook (registered and installed), the Claude sandbox, whether Claude Code
telemetry logs content (`claude_telemetry_logs_content`, plus one boolean per
flag; key names and truthiness only), and whether Codex uses
`inherit = "none"`. The exit status is 1 only when a **required** entry
is unsafe.

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
