# Secret guard hook fails closed — 2026-10-08

Both repository declarations of the secret-path guard's PreToolUse hook now carry
`"onFailure": "block"`: the project hook in `.claude/settings.json` and the user
template hook in `adoption/templates/claude.settings.template.json`. No other
hook declares the key. Routing, effort, memory and output hooks keep the client's
default, so one of them that fails still lets the action through.

## Why

Without the key, Claude Code treats a hook exit code other than 0 and 2 as a
non-blocking error and runs the tool call. The hooks reference says so under
"Other exit codes" and adds that exit code 1, the conventional failure code,
does not block either. The guard already turns its own exceptions into exit 2
(`guard_error`, `scripts/hooks/secret_path_guard.py:5208-5213`). That handling
cannot cover failures outside the script's own code: `python3` missing, an
import-time error, the hook's 10 s timeout, or a killed process. In each of
those cases the Bash command the guard should have read ran unread. With the
key, each of them blocks the call.

## Sources

- [anthropics/claude-code `CHANGELOG.md`](https://github.com/anthropics/claude-code/blob/602df92bf481ed904533e95c09f740f40aab5aed/CHANGELOG.md#L5)
  at commit `602df92bf481ed904533e95c09f740f40aab5aed` (file SHA256
  `c0b1f9aa313a8021d863ec0053c047b0acc792d74e04af9c7741d3ecd23c3d1a`, the same
  bytes as `main` when it was read on 2026-10-08). Entry `## 2.1.295`, line 5:
  "Added `onFailure: "block"` for command and HTTP hooks: a hook that can't
  start, times out, or exits with an unexpected code blocks the action instead
  of letting it through".
- The installed client, 2.1.295 (binary SHA256
  `4503bfe11a6c7fcc1e0b39b5e0d347c04248f750b03b0977b3ad6b531fe6f358`). Its
  settings schema declares `onFailure` on the command and HTTP hook entries. Its
  hook runner skips the key for a command hook marked `async` or `asyncRewake`,
  and ignores it on `Stop`, `SubagentStop`, `TaskCompleted` and `TeammateIdle`,
  where it logs `not blocking (onFailure: "block" is ignored on <event>)`. The
  guard is a synchronous PreToolUse hook, so neither limit applies to it.
- [Hooks reference](https://code.claude.com/docs/en/hooks.md) as read on
  2026-10-08 (SHA256 prefix `35ad60ec53127980`): "Other exit codes" and "Disable
  or remove hooks". The page does not mention `onFailure` yet, so the changelog
  and the installed client are the sources for the key.

## Evidence on this host

Each run was one `claude -p --model claude-haiku-5-5 --strict-mcp-config
--mcp-config <file holding {"mcpServers":{}}> --no-session-persistence
--output-format stream-json --verbose --include-hook-events` session. The
prompt came on stdin: "Run the shell command: echo guard-probe-ok. Reply with
the command's output only." Every session started in its own throwaway project
directory under `~/.cache/guard-onfailure-probe.8Yr9uu`, outside the checkout.
That directory's `.claude/settings.json` held the probe hook (PreToolUse,
matcher `Bash`) and a PostToolUse recorder on `Bash` that appends its input to a
file only when the call really ran. In cases A, B and E to H the probe command
first touches a marker file, so that file shows the hook started. The host's
own user hooks ran as well; for every Bash call they gave five PreToolUse
responses, all exit 0. The two outcome columns below come from the recorder
file and the tool result.

| Case | Probe hook command | `onFailure` | Hook outcome | Bash ran | Tool result |
| --- | --- | --- | --- | --- | --- |
| A | `python3 -c "raise SystemExit(3)"` | absent | exit 3, error | yes | `guard-probe-ok` |
| B | `python3 -c "raise SystemExit(3)"` | `"block"` on the hook entry | exit 3, error | no | `PreToolUse:Bash hook error: [...]: failed; blocking because onFailure is "block"` |
| C | a command that does not exist | absent | exit 127, `not found` | yes | `guard-probe-ok` |
| D | a command that does not exist | `"block"` on the hook entry | exit 127, `not found` | no | `...: failed; blocking because onFailure is "block"`, then the `not found` line |
| E (control) | `python3 -c "raise SystemExit(3)"` | `"block"` on the matcher group | exit 3, error | yes | `guard-probe-ok` |
| F (control) | `true` | `"block"` on the hook entry | exit 0 | yes | `guard-probe-ok` |
| G (control) | `sleep 30`, `timeout: 2` | absent | cancelled | yes | `guard-probe-ok` |
| H (control) | `sleep 30`, `timeout: 2` | `"block"` on the hook entry | cancelled | no, on both attempts | `...: timed out; blocking because onFailure is "block"` |
| B on 2.1.294 | as B | `"block"` on the hook entry | exit 3, error | yes | `guard-probe-ok` |
| I | as A, from a `--settings` file | absent | exit 3, error | yes | `guard-probe-ok` |
| J | as B, from a `--settings` file | `"block"` on the hook entry | exit 3, error | no | `...: failed; blocking because onFailure is "block"` |
| A on 2.1.284 | as A | absent | no project hook ran | yes | `guard-probe-ok` |
| B on 2.1.284 | as B | `"block"` on the hook entry | no project hook ran | yes | `guard-probe-ok` |
| K on 2.1.284 | as I | absent | exit 3, error | yes | `guard-probe-ok` |
| L on 2.1.284 | as J | `"block"` on the hook entry | exit 3, error | yes | `guard-probe-ok` |
| L on 2.1.295 (control) | as J | `"block"` on the hook entry | exit 3, error | no | `...: failed; blocking because onFailure is "block"` |
| M | `python3 -c "raise SystemExit(1)"`, from a `--settings` file | absent | exit 1, error | yes | `guard-probe-ok` |
| N | as M | `"block"` on the hook entry | exit 1, error | no | `...: failed; blocking because onFailure is "block"` |

The 2.1.295 runs A to H took place from 22:13:34Z to 22:15:19Z, I and J from
22:48:13Z to 22:48:27Z, and the 2.1.294 run, with `DISABLE_AUTOUPDATER=1` set,
at 22:31:21Z on 2026-10-08. In I and J the hooks came from a file passed with
`--settings`, and the session's project directory held no settings file. Every
session exited 0, and no session's stderr held anything beyond the client's
notice that the folder was not trusted (I and J: empty). SHA256 prefixes of the
stream-json transcripts: A `55a6fdbc9acac222`, B `4d695eb732685eff`, C
`7825e8860a0510ad`, D `0d638e62cedeea3d`, E `c15ee9f7746debbc`, F
`734cd6d06ff2d6ed`, G `39ba3f6a06b5e730`, H `89e6d8a62445b240`, B on 2.1.294
`a4c8f5c59c8e578b`, I `117d346bf32e86ae`, J `fc89390dbb8b2d0b`. The transcripts
carry session identifiers and host paths, so they stay in the throwaway
directory and are not part of the repository.

The rows on 2.1.284 cover the repository's pinned client floor
(`adoption/pins-linux-x86_64.json`, entry `claude-code`). That binary was
fetched from the pin's URL into a scratch directory, and its SHA256 matched the
pin. Those runs, and the 2.1.295 control, took place on 2026-10-09 from
00:10:16Z to 00:11:45Z, all with `DISABLE_AUTOUPDATER=1`.
- 2.1.284 predates `claude-haiku-5-5` (it logged `unrecognized_model`), so K and
  the two L rows used `claude-sonnet-5-5`.
- On 2.1.284, A and B from the project settings file ran no project hook at
  all: no marker file and no recorder file, with or without the key. Bash
  still ran.
  - The same happened when A and B were rerun with `claude-sonnet-5-5` at
    00:31Z, so the model was not the cause.
  - Every run printed the client's notice that the folder was not trusted. On
    2.1.294, project hooks ran under the same notice.
  - So on 2.1.284 the key was exercised only from a `--settings` file (K and
    L). Its project and user scopes were not exercised.
- SHA256 prefixes: A on 2.1.284 `92acdd41a3d7237d` (Sonnet rerun
  `c8c7516e1b5a6783`), B on 2.1.284 `7e83fb28a120906c` (Sonnet rerun
  `4bbd43446e320e0c`), K `e13a8b5ab75536c8`, L on 2.1.284 `4969ed23c38f3793`,
  L on 2.1.295 `323cb40766f2721c`, M `12895f408901c36e`, N `a31a8e1a3a015efb`.
  These transcripts are kept with the probe scripts outside the repository.

M and N ran on 2.1.295 from a `--settings` file, at 00:31:42Z and 00:31:49Z.
They use exit 1, the guard's own failure code. Without the key the call ran;
with the key it was blocked. The two Sonnet reruns of A and B (00:31:24Z and
00:31:32Z) and M and N all ran with `DISABLE_AUTOUPDATER=1`. Each run's client
version is its binary's `--version`, printed by the runner: 2.1.284 for the A
and B reruns, 2.1.295 for M and N.

What the runs show:

- The key goes on the hook entry. On the matcher group it does nothing (E).
- The key works from a project settings file (B, D, H) and from a `--settings`
  file (J). The template is a user settings file. That source was not run here,
  because a probe must not edit the live user settings. It has the same hook
  shape, and the client reads the key off the hook entry whatever file declared
  it; that part is source review.
- A hook that succeeds is unaffected (F). The template's guard command still
  exits 0 when no guard file is installed, so a host without the guard is not
  blocked; `test_rendered_hook_blocks_after_install_and_is_inert_before` keeps
  covering that.
- A timeout blocks with the key (H) and lets the call through without it (G).
- 2.1.294 (from a project settings file) and 2.1.284 (from a `--settings` file
  only) load the settings, ignore the key and run the call (rows "B on 2.1.294"
  and "L on 2.1.284"); 2.1.284 is the repository's pinned floor. A host on an
  older client keeps the earlier, fail-open behaviour.
- The guard's own exit codes other than 0 and 2 now block too, on 2.1.295 and
  later. Exit 1 ran the call without the key and was blocked with it (M, N).
  The guard's `main()` returns 1 when the hook input is not readable JSON
  (`scripts/hooks/secret_path_guard.py:5184-5188`), so that case is now blocked.

The guard took a median of 74 ms per call (largest 77 ms) on `git status` and
87 ms (largest 92 ms) on an 8 KB pipeline, 15 calls each on this host. That is
far inside its 10 s timeout.

## Risk

A broken guard now blocks every Bash call in every session that loads the
setting. That is the purpose of the change, and it means a bad guard release
stops shell work until it is fixed or the key is removed. The user-scope copy
of the guard is installed only through `tools/adoption/install_claude_profile.py`,
which verifies the file against `adoption/hooks/claude/SHA256SUMS`. The project
hook runs the checkout's own `scripts/hooks/secret_path_guard.py`.
`tests/test_secret_path_guard.py` covers the guard's behaviour.

The [SchemaStore Claude Code settings schema](https://json.schemastore.org/claude-code-settings.json),
as read on 2026-10-08 (SHA256 prefix `6d4a6e3c7adedffc`), lists the
command-hook fields with `additionalProperties: false` and has no `onFailure`.
An editor that validates against the `$schema` line may therefore flag the key.
Claude Code itself accepts it, and no check in this repository validates
settings against that schema.

Existing texts describe the behaviour without the key:
- in the guard: its docstring at `scripts/hooks/secret_path_guard.py:88-89` and
  its comments at `:5195`, `:5203` and `:5209`;
- the dated accounts in `docs/secret-storage.md`: lines 1165-1170 ("An internal
  error blocks; a timeout does not"), 1202 and 1208.

All of them remain true for clients before 2.1.295 and for any guard hook entry
without the key, which includes an existing host's user-level guard hook until
the key is added to it (see "Applying it to a host"). The guard is
checksum-pinned, so its text stays as written. The secret-storage texts also
stay as written, except for one dated note added on line 1165 (on the same
line, so no later line moves). The note points here and states the same
condition: the key on the hook entry, not the client version alone.

## Applying it to a host

A new-WSL build takes the template's whole hook object, because each hook piece
carries its object (`tools/adoption/new_wsl_client_config.py`,
`settings_pieces`). So a new host gets the key. The command
`python3 -B tools/adoption/new_wsl_client_config.py --render --host example --out <scratch dir>`
exited 0, and the `settings.json` it wrote carries `onFailure: "block"` on the
guard hook and on none of its other 15 command hooks.

`tools/adoption/apply_claude_settings.py` merges hooks by command and keeps the
existing hook object. On a host that already runs the guard, applying the new
template therefore leaves the live hook without the key. A merge of the
rendered template run once against such a host and once against an empty file
gave these guard objects: the existing host kept `type`, `command` and
`timeout`; the empty file gained `onFailure: "block"`. On an existing host the
live change is one key added to the guard's PreToolUse `Bash` hook object in
`~/.claude/settings.json`. The client's file watcher normally picks it up
without a restart. Carrying keys the template declares into an existing hook object would
change the merge contract its tests pin, so it is left as an open point here.

Three more open points:
- No test pins the key in the new-WSL render. The render above was a single run.
- `scripts/credential_status.py` checks that a user PreToolUse hook runs the
  guard and that the guard file exists. It does not check the key.
- On 2.1.284, no project-settings hook ran in an untrusted folder in `-p`
  mode, with or without the key (A and B, both models). On that client a
  checkout's own guard hook may therefore not run in that state. This
  predates the key and is not changed by it.

## Inverse

Revert the two-line hunk in both files, and in the live user settings where it
was applied:
1. Delete the `"onFailure": "block"` line.
2. Delete the comma that ends the line before it, so `"timeout": 10,` becomes
   `"timeout": 10`. A trailing comma is invalid JSON, and these files also hold
   the permission rules.
3. Check that each file still parses: `python3 -m json.tool <file> >/dev/null`.

Per the hooks reference, the file watcher normally picks up the edit in the
running session.

To recover a session whose guard is broken, edit the settings file outside
Bash: the guard's matcher is `Bash` only, so the file-editing tools still work.
Remove the key, or fix or remove the guard entry. For a single run with every
hook off, the hooks reference documents `--settings '{"disableAllHooks": true}'`,
which takes precedence over project and local settings. `disableAllHooks` does
not reach hooks set in managed settings.

## Tests

`tests/test_install_claude_profile.py`, `SecretGuardProfileTests`, has a new
method, `test_only_the_secret_guard_hook_fails_closed`. It walks every command
hook in `.claude/settings.json` and in every JSON file under `adoption/`. Each
hook that runs `secret_path_guard.py` must carry `onFailure: "block"`, no other
hook may carry the key, and both known declarations must be found. Four
mutations each fail the method and were reverted byte for byte: either guard
without the key, the template's `rtk` hook with it, and the effort guard with it.
No existing test expectation changes.

| Claim | Evidence class | Command / receipt |
| --- | --- | --- |
| The key blocks a failing, missing or timed-out PreToolUse command hook on 2.1.295, and only on the hook entry | `native_proven` | Runs A to J above |
| The same holds when a user settings file declares the hook | `source_review` | One hook schema for every settings file; no user-scope run |
| 2.1.294 ignores the key in a project settings file without rejecting it | `native_proven` | Row "B on 2.1.294" above |
| 2.1.284 (the pinned floor) ignores the key in a `--settings` file without rejecting it; its project and user scopes were not exercised | `native_proven` (`--settings` only) | Rows K and L on 2.1.284; A and B on 2.1.284 ran no project hook |
| Exit 1 blocks with the key and runs the call without it on 2.1.295 | `native_proven` | Rows M and N |
| The key exists for command and HTTP hooks; it is skipped for async hooks and four events | `source_review` | Changelog 2.1.295; installed 2.1.295 binary |
| Only the guard hooks carry the key | `local_integration` | New test method and its four mutations |
| The merge path does not carry the key to an existing host | `local_integration` | `merge_settings` run against both base files |

## Addendum (2026-10-09): a missing guard script now blocks

This record kept one fail-open path on purpose: the template's guard command exited 0 when no guard file was installed,
so a host without the guard was not blocked, and `onFailure` never fires on exit 0. The Claude Code native practice
review of 2026-10-09 (`docs/decisions/2026-10-09-claude-code-native-practice.md`, slot `hooks`, in its own pull request) found that every supported
install route places the guard before the settings that call it (`adoption/bootstrap.md` runs the `claude-profile`
step before `claude-settings`, and the new-WSL render copies the checksum-verified hook files with the settings). A
missing script after install is therefore removal or damage.

The template command now refuses when the script is missing:
`f="${HOME}/.claude/hooks/secret_path_guard.py"; [ -f "$$f" ] && exec python3 "$$f"; exec python3 -c '<print the refusal; exit 2>' "$$f"`.
It runs only `[` and `python3`, the command words the new-WSL renderer admits for a practice hook
(`tools/adoption/new_wsl_client_config.py` `BASE_COMMAND_WORDS`). Exit 2 blocks a PreToolUse call on every client
version, so this part does not depend on `onFailure`. One test
contract changes, declared: `test_rendered_hook_blocks_after_install_and_is_inert_before` becomes
`test_rendered_hook_blocks_before_and_after_install`; before install it now expects exit 2 and the refusal text, and
the after-install assertions are unchanged.

The command center applied the same command to this host's user settings at 2026-10-09T06:20:30Z, after testing it
in isolated temporary home directories (missing script: exit 2 with the refusal; passing stub: 0; blocking stub: 2).
Raising the pinned client floor from 2.1.284 to 2.1.295, so that `onFailure` is honoured on every host at the floor,
is a separate change owned by the currency lane.
