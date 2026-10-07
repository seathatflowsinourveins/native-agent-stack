# Linux/WSL2 x86_64 — status: accepted

## Get the catalog

Clone the catalog and check out its attested release tag before running any
step below (see [`adoption/bootstrap.md`](../bootstrap.md) step 0 for the
full detail, including `gh attestation verify` for a downloaded release
archive):

```sh
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git
cd native-agent-stack
python3 scripts/release_due.py   # on the default branch: steps main documents that the pinned release lacks
tag="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_tag'])")"
commit="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_commit'])")"
git checkout "$tag"
if test "$(git rev-parse HEAD)" = "$commit"; then echo "at $tag ($commit)"; else echo "error: $tag is not the pinned release commit $commit" >&2; false; fi
```

That checkout target is `adoption/manifest.json` `source.release_tag` (or a
later tag), confirmed at `source.release_commit` and published with SLSA
build provenance by `.github/workflows/publish-catalog.yml`. Read both values
before the checkout, as above: the release's own manifest names the release
before it, so `scripts/release_due.py` runs on the default branch. Do
**not** check out `source.baseline_commit`: that field predates `adoption/`
and `tools/adoption/` entirely and is never a checkout target (Codex
cross-family review finding, `codex-review-72`; `codex-review-64` is the
separate promotion-gate cross-family review finding);
[`scripts/adoption_status.py`](../../scripts/adoption_status.py) uses
`baseline_commit` only as the comparison point for its
`baseline_matches`/`baseline_differs` `git` result, never as something a
reader should check out.

`platform_profiles` entry `linux-wsl2-x86_64` in [`adoption/manifest.json`](../manifest.json),
evidence at [`adoption/receipt.json`](../receipt.json). This is the initial and
only accepted target platform; `adoption/manifest.json` `supported_platforms`
stays Linux/x86_64/Python 3.13 only (see
[`adoption/README.md`](../README.md), "The initial target is Linux/WSL2
x86_64").

## What is accepted here

[`adoption/receipt.json`](../receipt.json) records native uv 0.12.17
recreating all 36 accepted SDK distributions in a fresh
Linux/Python 3.13.15 prefix on the existing WSL host, exact
name/version match after an uncached reinstall, and useful local SDK/data
checks passing; Codex required sign-in on first inspection and passed
discovery/allowance checks after native device sign-in. This is a fresh
prefix on the existing host, not a second physical machine — the receipt's
own `scope.second_physical_machine` is `false`.

[`docs/portable-userspace-install-20260921.md`](../../docs/portable-userspace-install-20260921.md)
additionally qualified pinned Claude/Codex installation, four token tools and
two ECC skills inside a fresh official Ubuntu Base 24.04.5 filesystem on the
existing WSL kernel: the unchanged token fixture runner passed 41 native
commands and 14 semantic checks, with repeat-install, overwrite-protection and
rollback checks passing in scope. That page's own boundary applies here too:
fresh Linux userspace on the existing WSL kernel is not a booted new PC, an
independent kernel, or a full-foundation deployment.

## vLLM pin: 0.30.0 (0.29.0 fails on WSL)

The working WSL vLLM pin is **0.30.0** since 2026-09-25
([`evidence/receipts/vllm-030-switch-20260925.json`](../../evidence/receipts/vllm-030-switch-20260925.json)).
0.30.0 carries the pinned-memory fallback for WSL (vllm-project/vllm PR
#56908) and closes GHSA-25q3-v2hm-8vpf and GHSA-5fj9-pfhr-6j48. On the
NativeStack RTX 4090 host it served the same Nemotron-3-Embed-1B-BF16 files
with embeddings and code-index results identical to 0.25.0, first on an
owned instance and then in production; 0.25.0 stays installed for rollback.
Version **0.29.0 failed real startup with "UVA is not available"** on this
WSL GPU path (unified virtual addressing unsupported by the WSL GPU driver
surface at that release).
[`adoption/lifecycle.md`](../lifecycle.md) records this exactly: "The working
WSL vLLM pin is 0.30.0 since 2026-09-25, qualified against 0.25.0 on the same
host before the switch; 0.25.0 stays installed for rollback. Version 0.29.0
failed real startup with unavailable UVA support. Preserve the accepted
environment and model/vector data; repeating installation until the version
number is newer would not resolve such a compatibility failure, so a new
version is qualified on an owned instance first." Do not bump this pin on a new
WSL host without first re-testing any newer release's startup on that host's
actual GPU/driver combination; a newer upstream version number is not by
itself evidence the WSL UVA gap closed.

## Ordered steps for a new Linux/WSL2 host

1. Follow [`adoption/bootstrap.md`](../bootstrap.md) steps 1–3 (prerequisites,
   `bootstrap-linux.sh --profile <id>`, native sign-in).
   `adoption/bootstrap-linux.sh` and its `claude-code` pin
   changed after `v2026.09.24.1`: at that tag the pin is 2.1.280 and the
   script reinstalls it even over a newer Claude Code, so a re-run
   downgrades a native auto-updated install. On main the pin is 2.1.284 and a floor: the script
   keeps a `~/.local/bin/claude` whose `--version` reports 2.1.284 or newer
   (logging `Kept installed claude-code <version>`, with nothing downloaded
   or installed) and runs the checksum-verified install only when that
   launcher is missing, older or unreadable. The pin also changed after `v2026.09.26.2`,
   where it is 2.1.281: 2.1.284 is the first Claude Code release whose
   `sonnet` alias resolves to Sonnet 5.5 (on the Anthropic API; an older client routes it to Sonnet 5; [model-config](https://code.claude.com/docs/en/model-config)),
   so a launcher reporting 2.1.281 to 2.1.283 now takes the
   checksum-verified install.
   Its version report changed after `v2026.09.24.1`: that release, and
   every earlier one, runs `--version` on every file in
   `$ECO_INSTALL_ROOT/bin` and blocks on `context-mode`, which serves MCP on
   stdin instead, so run such a release's script with `</dev/null` (step 2 of
   [`adoption/bootstrap.md`](../bootstrap.md) has the details and the
   `mcp-inspector` case).
   The script and its rtk and markitdown pins changed after `v2026.09.25.2` (#291): at that tag rtk was pinned at 0.49.0 and the script printed no such reminder at all; after that tag the pin became 0.50.0 and, after installing rtk, the script started printing a reminder unless `~/.config/rtk/config.toml` already has the Claude-hook `exclude_commands` key. It changed after `v2026.09.26`, which already pins rtk 0.50.0 but still checks only for the original two-entry key and does not detect a duplicate `exclude_commands` line; here the reminder fires unless the key appears exactly once with all five entries from [the RTK hook recipe](../../recipes/README.md#native-context-mode-and-hooks) are present, exactly once, and, since #314, unless the installed `rtk hook check` also leaves the recipe's probes unrewritten (rtk can ignore a TOML-valid file, for example one with a `[tracking]` table that lacks `history_days`). The script never writes that file. Its pins file's rtk `install_note` also changed after `v2026.09.26` (`pins-linux-x86_64.json`, text only).
   The script's socraticode and headroom installs changed after `v2026.09.26` too (as did headroom's `install_note`): it now passes `--ignore-scripts` for socraticode's `ignore_scripts: true` pin, a field the tag's script ignores, so there npm runs every install script in socraticode's dependency tree, and it now downloads headroom's pinned wheel, verifies its `sha256` and installs that file, where the tag's script resolves `headroom-ai[mcp]==0.37.0` from the index without reading the wheel or its hash (step 2 of [`adoption/bootstrap.md`](../bootstrap.md)).
   Its pins file also changed after `v2026.09.25.2` in a second way:
   `pins-linux-x86_64.json` changed after `v2026.09.26.2` in its `codex` entry (0.155.1 to 0.157.1 on 2026-09-26, then to 0.159.2 on 2026-09-30, 0.159.3 on 2026-10-01 and the repository 0.160.0 pair on 2026-10-03; a host at that tag installs 0.155.1, and 0.157.1 needs the Codex template's `daemon_auto_start = false` before its first interactive launch, which the template keeps for 0.159.2, where the feature is still listed as stable and on) and in its `claude-code` entry (2.1.281 to 2.1.284, described earlier in this step). The [October 3 receipt](../../evidence/artifacts/runtime-sdk-20261003/receipt.json) retains completed 0.160.0 native-account and gateway markers on the existing host as a compatibility attempt; original invocation/timing evidence is incomplete; the shared launcher and daemon still run 0.159.3 until a coordinated switch.
   `pins-linux-x86_64.json` now pins `repomix`, `toon`,
   `headroom`, `ccusage`, `serena` and `socraticode` too, completing the
   `token-efficiency` profile's Linux coverage (step 2 of
   [`adoption/bootstrap.md`](../bootstrap.md) has the details).
   Its `ai-memory` and `mcporter` pins also changed after `v2026.09.25.2` (2.3.2 to 2.4.1 and 0.13.13 to 0.14.1); before an existing ai-memory service restarts on 2.4.1, follow [upgrading an existing store](../../recipes/README.md#upgrading-an-existing-store).
   On 2026-10-03, the Linux pins changed after `v2026.09.26.2` again: `orx` 0.2.7 to 0.2.15 (URL, hash and note); a host at that tag keeps OpenResearch 0.2.7. The pins file is also changed after `v2026.10.05.1`, which still pins 0.2.7. W1 held mcporter at Linux 0.14.1 on 2026-10-03 after its 0.14.2 compatibility attempt. The current Linux pin follows main's 2026-10-04 move to 0.14.2 in #693; [that receipt](../../evidence/receipts/mcporter-0142-qualification-20261004.json) retains its limitations. See [W1 qualification](../../docs/decisions/2026-10-03-currency-wave-w1.md) before treating scratch evidence as a host switch.
2. Recreate the SDK only for the `research-runtime` profile using
   [`adoption/sdk/README.md`](../sdk/README.md)'s transitive lock; retain the
   same exact-match and uncached-reinstall checks as
   [`adoption/receipt.json`](../receipt.json).
3. Render configs with [`tools/adoption/render_config.py`](../../tools/adoption/render_config.py)
   (`adoption/bootstrap.md` step 4) using this host's own
   `adoption/hosts/<host>.json`. For tab titles, alerts and the login shell of Windows Terminal profiles, see
   [Windows Terminal profiles and the login shell](#windows-terminal-profiles-and-the-login-shell) (added after `v2026.09.26.2`).
4. Start selected `systemd --user` units per
   [`adoption/lifecycle.md`](../lifecycle.md#native-client-integration-and-process-lifecycle);
   never stop the shared MCPorter daemon to clean up another component.
5. Run `uv run --no-project --python 3.13 python scripts/adoption_status.py --profile <id> --json` (changed after
   `v2026.09.23.1`, which runs plain `python3`: Ubuntu 24.04's `python3` is 3.12,
   which the manifest does not support; run this form there too) and record
   the per-host receipt (`adoption/bootstrap.md` steps 6–7).
6. Contribute what ran: record host receipts with `scripts/host_receipts.py`
   from a branch of current `main`, refresh the generated matrix and grand
   list, and open a PR, following
   [`docs/contributing-evidence.md`](../../docs/contributing-evidence.md).
7. When a newer release is pinned, follow
   [moving a host to a new release](../update.md#moving-a-host-to-a-new-release).

## Windows-side commands from WSL

Lessons from work on the WSL workstation in September 2026; the links give the
upstream behavior behind each.

**Prerequisite: PowerShell 7 installed on the Windows host.** A stock Windows installation does not include it.
This guidance uses [PowerShell v7.6.6](https://github.com/PowerShell/PowerShell/releases/tag/v7.6.6)
(2026-09-08; current stable release checked 2026-10-04). Run
`winget install --id Microsoft.PowerShell --source winget --installer-type wix --version 7.6.6` in a Windows command shell
([Microsoft's install instructions](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.6#install-powershell-using-winget),
[WinGet install reference: `--version` selects an exact version](https://learn.microsoft.com/en-us/windows/package-manager/winget/install#options)).
WinGet defaults to MSIX since 7.6; `--installer-type wix` selects the MSI installation, whose default directory is
`C:\Program Files\PowerShell\7`
([installation options](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.6#install-the-msi-package-with-command-line-options)).
If `/mnt/c/Program Files/PowerShell/7/pwsh.exe` is absent, stop the Windows-side steps and install it first. When WinGet
is unavailable, download the **7.6.6 MSI** from the [reviewed release](https://github.com/PowerShell/PowerShell/releases/tag/v7.6.6)
and follow [Microsoft's MSI installation steps](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.6#install-the-msi-package):
double-click it and follow the prompts, retaining the default directory; run the version gate before resuming
([Microsoft's installer steps, lines 84–92](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/docs-conceptual/install/install-powershell-on-windows.md#L84-L92)).
Before any Windows-side block, run the [PowerShell version gate from bash in the workstation distribution](linux-wsl2-new-distro.md#powershell-version-gate-before-w1).
It prints and records `$PSVersionTable.PSVersion` from this exact executable and permits only 7.6.6 or a later stable
7.6 patch. An older version takes
`winget upgrade --id Microsoft.PowerShell --source winget --installer-type wix --version 7.6.6` in a Windows command
shell ([WinGet upgrade reference](https://learn.microsoft.com/en-us/windows/package-manager/winget/upgrade#options)),
or the 7.6.6 MSI fallback when WinGet is unavailable; rerun the gate and retain its new version log before continuing.
Do not fall back to Windows PowerShell 5.1. NativeStack disables `appendWindowsPath`, so invoke the quoted absolute
path below even when Windows has the executable on its PATH.

- Do not pipe a script to `pwsh.exe -Command -`. PowerShell reads
  standard input one statement at a time, as if typed at the prompt, and does
  not run a statement that fails to parse
  ([about_pwsh, -Command](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_pwsh?view=powershell-7.6#-command---c)),
  so a multi-line block can be dropped without an error. Write a `.ps1` file
  and run it with
  `'/mnt/c/Program Files/PowerShell/7/pwsh.exe' -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(wslpath -w step.ps1)"`.
  `-File` takes the script path and must follow the other launcher options;
  `-NonInteractive` makes prompts fail instead of hanging
  ([about_pwsh, -File](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_pwsh?view=powershell-7.6#-file---f),
  [about_pwsh, -NonInteractive](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_pwsh?view=powershell-7.6#-noninteractive---noni)).
- Strip `\r` and `\0` from Windows-side output before comparing or parsing it,
  for example with `tr -d '\r\0'`. Windows programs end lines with CRLF, and
  `wsl.exe` writes UTF-16 unless `WSL_UTF8=1` is set
  ([`WslClient.cpp` at 2.7.14](https://github.com/microsoft/WSL/blob/2.7.14/src/windows/common/WslClient.cpp#L1843-L1852)).
- `Get-ChildItem -Filter 'name.*'` also matches an extensionless `name`: the
  filter follows Win32 wildcard rules, in which `.*` also matches no extension
  ([.NET `FileSystemName`](https://github.com/dotnet/runtime/blob/v10.0.0/src/libraries/System.Private.CoreLib/src/System/IO/Enumeration/FileSystemName.cs#L139)).
  Before any `Remove-Item`, select with `-LiteralPath` or an exact list of
  names and print that list. `Remove-Item` deletes permanently; it does not use
  the Recycle Bin
  ([PowerShell#6801](https://github.com/PowerShell/PowerShell/issues/6801)).
- A long script passed inline, as in `wsl.exe -d <distro> -- bash -lc '...'`,
  can fail with `Argument list too long`: Linux refuses a single argument of
  128 KiB or more (measured on the workstation's WSL kernel: 131,071 bytes
  ran, 131,072 did not), and a Windows command line is limited to 32,767
  characters
  ([CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)).
  `/dev/stdin` could not be reopened by path across the interop boundary
  either. Pipe the script to `bash -s` instead:
  `wsl.exe -d <distro> -- bash -s < script.sh`.

## A new distro from the official Ubuntu WSL image

Added after `v2026.09.26.2`. [A new distro from the official Ubuntu WSL image](linux-wsl2-new-distro.md) creates a
second WSL 2 distribution on this Windows host from Canonical's `ubuntu-24.04.5-wsl-amd64.wsl`, after checking the file
against both published sha256 values. cloud-init gives it a passwordless default user before its first launch, and the page
proves systemd, linger and the user bus before the bootstrap runs there. It changes nothing for the other distributions:
no `.wslconfig` edit, no `wsl --update`, never `wsl --shutdown`, and the default distribution stays as it is. The
decisions, their alternatives, the command table and the open questions are in
[the 2026-10-01 record](../../docs/decisions/2026-10-01-new-wsl-distro-recipe.md).

## Windows Terminal profiles and the login shell

Added after `v2026.09.26.2`: `adoption/templates/claude.settings.linux-wsl2.overlay.json`, the profile example
[`examples/claude-native/windows-terminal.fragment.example.json`](../../examples/claude-native/windows-terminal.fragment.example.json)
and `scripts/adoption_status.py --login-shell`. `adoption/templates/codex.config.template.toml` changed after
`v2026.09.26.2` too: it adds a `[tui] notifications` list. A host pinned to that release has none of them until a release
carries them ([moving a host to a new release](../update.md#moving-a-host-to-a-new-release)). The decision, its evidence and
its limits are in [the 2026-09-28 terminal decision](../../docs/decisions/2026-09-28-terminal-experience.md).

A Windows Terminal profile that starts a client with `bash -lc "exec claude"` gets its PATH from the Bash login shell, and a
login shell reads only the first of `~/.bash_profile`, `~/.bash_login` and `~/.profile`
([Bash startup files](https://www.gnu.org/software/bash/manual/bash.html#Bash-Startup-Files); bash 5.3 `shell.c`
`execute_profile_file`). A file at one of the first two names, even an empty one, therefore hides `~/.profile` and every PATH
entry it adds, and the tab ends with `exec: claude: not found` (exit 127). With `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` on Linux
with bubblewrap, Claude Code creates such an empty `~/.bash_profile` and leaves it
([anthropics/claude-code#76236](https://github.com/anthropics/claude-code/issues/76236)).

1. Keep no empty `~/.bash_profile` or `~/.bash_login`. On a host that sets that variable, make `~/.bash_profile` a real file that
   hands off:
   `if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi`. Bootstrap writes no shell startup file; this stays the
   operator's edit.
2. Check without running anything:
   `uv run --no-project --python 3.13 python scripts/adoption_status.py --profile <id> --login-shell --json`. It stats the three
   files and reports a state each, the file a login shell reads first and `profile_read` (`false` when an empty or unusable earlier file hides `~/.profile` or `~/.profile` is itself unusable; `null` when an earlier file has content, because whether it hands off is not read). It proves
   no PATH. Prove that with the profile's own launch shape, from Windows or through WSL interop:
   `wsl.exe -d <DISTRO> -u <WSL_USER> --exec /bin/bash -lc 'type -P claude codex'` must print both paths (`type -P` finds files, where `command -v` also accepts a shell function, which the profile's `exec` cannot start; `type -P` can still print a stale hashed or a non-executable path, so the doctor's check also requires the printed path to be an executable regular file). A probe from a shell
   that already has PATH passes even when the login files are broken.
3. Merge the Claude Code overlay (added after `v2026.09.26.2`) into the live settings: `python3 tools/adoption/apply_claude_settings.py --template
   adoption/templates/claude.settings.linux-wsl2.overlay.json --dry-run`, then the same without `--dry-run` (it backs the file up
   first). It sets `preferredNotifChannel` to `notifications_disabled` and adds one `Notification` hook that rings the
   terminal bell only when Claude Code needs the person (a permission or elicitation dialog, an agent waiting for input, a quota event, or the model's own push notification, which a local session sends only when the client judges you away (a remote workspace skips that check): once the terminal has sent a focus report its last state decides, so a tab last reported focused counts as present however long you are gone, and before any report 60 s without input counts as away; `CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK` bypasses the check); the hook runs `jq`, which the bootstrap already requires. Windows Terminal 1.24 acts on no notification sequence but BEL. The merge de-duplicates hooks by command anywhere in the event, so it never changes the matcher of a `Notification` hook that already runs the same command: if the overlay's matcher changes later, edit or remove that group first and merge again (`evidence/artifacts/notification-types-20260929/replace_bell_group.py <checkout> local [--apply]` does that on a private copy, after a backup, and refuses a group it cannot replace without losing something). `evidence/artifacts/wsl-terminal-defaults-20260929/overlay_noop_check.py` prints whether exactly one group holds the command and whether its matcher equals the overlay's.
4. Render the Codex template as usual (`tools/adoption/render_config.py`; step 3 above): its `[tui] notifications` list asks for a notification on an approval, a plan-mode prompt or a question (`request_user_input` questions notify as `plan-mode-prompt`; `async-question` covers the asynchronous questions added after 0.155.1), and not when a turn finishes. Codex loads a misspelled kind
   without an error and never notifies for it; the comment above the list names the source file that defines the kinds.
5. Copy the profile example, replace `<DISTRO>`, `<WSL_USER>` and `<PROJECT>`, and save it as UTF-8 to
   `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\native-agent-stack\<name>.json`
   ([JSON fragment extensions](https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions)). The page says a GUID is "optional, but strongly encouraged"; the example declares none because this repository's publication scan treats any UUID as a session identifier. Windows Terminal then derives a stable one from the folder name and the profile name (the page's UUIDv5 recipe gives the same value if you must reference a profile by it), so keep the folder name and the profile names fixed once installed: renaming either gives the profile a new identity, and a `settings.json` override or a `defaultProfile` keyed to the old GUID stops applying. Windows Terminal merges fragments on every settings load
   and watches only `settings.json`, so touch that file after adding or editing one. The example sets no `suppressApplicationTitle` on the Claude and Codex profiles, so each tab shows the title its
   client sends; gives them an explicit `bellStyle` array (never `"all"`) and a quiet `bellSound`; and sets `COLORTERM` through the profile's `environment` key. **Precedence** (microsoft/terminal v1.24.11911.0, `SettingsLoader::FinalizeLayering`, source read, not run here): a profile's own value, then `profiles.defaults`, then the fragment's profile. A profile that only a fragment defines therefore loses to `profiles.defaults` for every key `defaults` sets: if your `defaults` set `suppressApplicationTitle`, `bellStyle`, `bellSound` or `environment`, the example's values for those keys do not apply, and so the titles, the quiet bell or `COLORTERM` are not what the example advertises. Remove those keys from `defaults`, or put the values in the `settings.json` entry for the profile's own (derived) GUID, which does beat `defaults`. A profile's own `environment` also completely replaces `profiles.defaults.environment` instead of merging with it ([profile-advanced](https://github.com/MicrosoftDocs/terminal/blob/main/TerminalDocs/customize-settings/profile-advanced.md), "Environment variables"), so in such an entry copy the variables the defaults set. The practice repository's host check refuses a `defaults` that suppresses titles or rings `all`; it does not compare `defaults.environment`.

Measured on one workstation (Windows Terminal 1.24, Claude Code 2.1.284, Codex 0.157.1, before the Linux pin moved to 0.159.2). A new host collects its own evidence.

The example also carries two resume profiles, `WSL - Codex - resume` and `WSL - Claude - resume`, each right after the profile of its client. They run `exec codex resume` and `exec claude --resume`, which open the client's own session picker, and nothing resumes until you choose a row. Each picker starts with the sessions of the profile's `--cd` directory (Codex: the launch directory; Claude Code: the current worktree) and can be widened from inside it ([Codex `resume_picker.rs` at `rust-v0.160.0`](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/tui/src/resume_picker.rs#L676-L689); [Claude Code sessions](https://code.claude.com/docs/en/sessions)), and the default profiles are unchanged and still start a new session.

Windows Terminal re-saves `settings.json` in its own layout, written from its settings model with four-space indentation, and writes a single `bellSound` string back as a one-element array (`microsoft/terminal` `v1.24.11911.0`: `CascadiaSettingsSerialization.cpp` L1602 writes the file, and `JsonUtils.h` L359-L389 reads a lone string as a list of one while L549-L551 always writes an array), so a check that reads that file must accept both forms.

## Listeners and ports

- All WSL 2 distributions share one network namespace
  ([About WSL](https://learn.microsoft.com/en-us/windows/wsl/about)), so
  `ss -ltnp` in one distribution lists the other distributions' listeners too,
  without a process. Attribute a listener to its distribution, unit and
  upstream documentation before labelling it. On the WSL workstation on
  2026-09-25, `127.0.0.1:49374`, this repository's default ai-memory port, was
  held by another distribution, and that host's scoped `nativestack-memory`
  unit binds `127.0.0.1:49474`. The ai-memory MCP registration and the
  rendered hook commands (`AI_MEMORY_URL` in the host's
  `adoption/hosts/<host>.json`) must name the port the host's own ai-memory
  unit binds. The user-scope template `adoption/mcp/claude-user.json` keeps
  the default 49374. That template changed after `v2026.10.05.1`:
  SocratiCode's model/dimensions are Nemotron-3-Embed-8B/4096,
  with portable endpoint defaults retained; the target host registers its
  own endpoints. Its comment gives the remove-then-add sequence for
  another port. That template changed after `v2026.09.24.1`: serena runs
  `${ECO_ROOT}/bin/serena` instead of a `serena-context` wrapper, and
  jcodemunch is no longer registered at user scope (a per-project opt-in in
  `adoption/bootstrap.md` step 4a).
- With `networkingMode=mirrored`, a wildcard (`*` or `0.0.0.0`) listener can be
  reached from the local network
  ([mirrored mode](https://learn.microsoft.com/en-us/windows/wsl/networking#mirrored-mode-networking))
  unless the Hyper-V firewall blocks it. WSL 2.0.9 and later turn that
  firewall on by default on Windows 11 22H2 and later
  ([WSL and firewall](https://learn.microsoft.com/en-us/windows/wsl/networking#wsl-and-firewall)),
  and the mirrored-mode page opens inbound connections only by changing the
  firewall's settings or adding a firewall rule. Bind services to `127.0.0.1`
  and check `ss -ltnp` after each start.
- The observability backend renders fixed loopback ports. When another
  distribution holds one, run `observability/backends/configure.py` with
  `--port-overrides` (changed after `v2026.09.25.2`, which lacks the option).
  The renderer keeps the map, so a later re-render does not reset the moved ports.
  Its Prometheus unit also changed after `v2026.09.26.2`: it adds
  `--enable-feature=created-timestamp-zero-ingestion,promql-extended-range-selectors`
  for per-process token counters, and its `ecosystem-prometheus.yml` drops the
  per-process Codex histogram buckets at scrape. See
  [its README](../../observability/backends/README.md).
- vLLM listens on a wildcard port even with `--host 127.0.0.1`. vLLM 0.25.0
  initializes `torch.distributed` over TCP on a single GPU too (its
  `UniProcExecutor` passes a `tcp://` init method), and PyTorch's `TCPStore`
  listens on all interfaces by default. vLLM documents this as known,
  intended PyTorch behavior and says to firewall the internal ports
  ([security guidance at v0.25.0](https://github.com/vllm-project/vllm/blob/v0.25.0/docs/usage/security.md#security-and-firewalls-protecting-exposed-vllm-systems)).
  On the WSL workstation on 2026-09-25 (vLLM 0.25.0, torch 2.11.0, API server
  on `127.0.0.1:18231`), `ss -ltnp` showed the engine-core process
  (`VLLM::EngineCor`) listening on `*:24706`. Treat this as a known upstream
  limitation that the Hyper-V firewall mitigates only while it blocks inbound
  connections: keep that firewall on and its inbound default at block.

## Boundaries

Executable presence, a passed `--version`, or this document being valid does
not establish account readiness, service health, or model-mediated behavior
on a new WSL host — each new host repeats its own native sign-in and at least
one bounded useful call (`adoption/README.md`, "Native verification tiers").
