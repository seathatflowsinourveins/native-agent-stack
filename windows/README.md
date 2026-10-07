# NativeStack2604 Terminal fragment

`nativestack2604.json` is a portable repository projection of the operator's
2026-10-06 fragment. Windows Terminal reads it from the `NativeStack` fragment
folder. Keep that folder and the existing profile names: their explicit GUIDs
use Microsoft's documented nested UUIDv5 derivation, preserving the identities
that Terminal previously generated for the nine profiles without GUIDs. The
token lane intentionally takes a new derived identity: the older explicit
identity in `lanes.json` is hidden by a settings override at deploy. Other
NativeStack2604 entries from the `NativeStack` source are hidden only when their
GUID is absent from the canonical fragment; the sixteen canonical profiles,
other sources and old NativeStack profiles are preserved.

The portable projection deliberately omits the nine source `tabTitle` values:
their initial title falls back to the profile name, while applications may
change AI titles. It also omits `closeOnExit: "graceful"`, using Terminal's
`automatic` default, which behaves as `graceful` for processes Terminal launches.
These are documented departures from the 2026-09-28 experience record, rather
than a claim that those source fields were copied. The four lane titles remain.
These defaults apply only without user, GUID-specific or `profiles.defaults`
overrides, which this recipe preserves.

The source checker is ported from
`nativestack-practice@a7b8018524575cabbd979e6f2e1c84ee6e94700f:checks/check-terminal-profiles.py`.
It checks repository files by default, never discovers native client settings,
and accepts an optional, explicitly selected settings fixture. Its maintained
GUID recipe supports the ASCII names carried here. It is a local integration
check; its synthetic controls and a repository PASS do not establish deployment,
session continuity, audible volume or Windows UI acceptance.

```sh
rtk proxy nice -n 19 python3 -B checks/check-terminal-profiles.py
rtk proxy nice -n 19 python3 -B -m unittest tests.test_terminal_fragment tests.test_validate tests.test_native_token_ci tests.test_windows_terminal_defaults
rtk proxy nice -n 19 python3 scripts/validate.py
```

## Host-owned launch contracts

No credential, account selection, session identifier, client name, effort,
permission setting or machine-specific home path is carried in the fragment.
Ordinary resume profiles open the native session pickers. These special profiles
delegate to the co-op's launchers outside Git; file presence does not prove their
session binding:

| Profile | Launcher under `~/.local/state/native-agent-stack/lanes/` | Owner contract |
| --- | --- | --- |
| Command center (resume) | `command-center-resume.sh` | Start the maintained command-center Claude session in its owned project. |
| Co-op (resume) | `co-op-resume.sh` | Resume the existing co-op Claude session, including after restart. |
| Codex - account pool | `codex-account-pool.sh` | Start the owner's native Codex account-pool route; sign-in stays native and outside the command line. |
| Librarium | `librarium.sh` | Resolve the P1-CLI clone and vault binding, then start its documented workflow. Cwd is DEFERRED; profile stays hidden until that owner supplies the contract. |

`Librarium course` remains the distinct `~/code/librarium-course` project.
Operations calls the byte-identical upstream `ops-entry.sh`, which reports
`nativestack doctor`'s actual exit code and opens a shell. Local Chat calls the
existing `nativestack chat`. Their installed CLI availability remains a P1-CLI
dependency, not a new passed claim.

The four Codex lane profiles use the existing `codex-lane.sh` and
`codex-{root,runtime,token,trading}-lane.prompt.txt` locators in that same private
lane directory. The owner must stage them on 2604 before launching them. Repoint
HTTP gateway references from 20128 to 21128 only after verifying their role.
21129 is the WebSocket listener of the 21128 process; it is not a replacement
for the old independent HTTP `omniroute-fw` service on 20129. References to that
service remain DEFERRED to Phase 3. No prompt body is invented or committed here.
The four lane entries have a separate commit so a later tab-orchestration
decision can remove or reshape them without undoing the base fragment.

## Co-op host apply, read-back and rollback

These are operator commands, **not executed by this repository lane**. Run from
the reviewed repository on NativeStack2604. The co-op first supplies and
verifies the three special launchers above; keep the live special profiles until
that replacement is ready. Independently confirm the right sessions resume.
The apply refuses before copying unless all visible launcher/prompt, native CLI
and project-directory dependencies exist. These checks establish presence only;
the owner still verifies the special session bindings. Librarium stays hidden
with its P1-CLI contract deferred. Keep the old NativeStack fragments and
profiles until R2; the obsolete 2604 identity is hidden without deleting its
source fragment. No Terminal or OS restart is required.

Before deployment, a **human operator** must retain the original private
fragment for rollback and verify the special-session replacement. The observed
original contains inline authentication, so no AI/co-op step may read or copy it
or its backup. Use the human's existing backup and custody process. The agent-safe
recipe backs up settings, records whether the target existed, and copies only
the public repository fragment. Restoring a preexisting private fragment is a
human step; do not treat the automatic settings rollback as full restoration.

Use the installed Windows PowerShell only to locate LocalAppData; the existing
Python checker supplies its maintained JSONC parser, avoiding a new dependency
or a second parser. Only a default-profile or obsolete-profile override change
requires rewriting settings. An already correct name or GUID default alone
does not bypass obsolete-profile hiding. With no effective change, the exact
JSONC bytes remain; when a change is required, other parsed values remain but
comments and formatting become JSON. Backups retain the exact original bytes
for rollback. The packaged Terminal settings path below exists
on the observed host; another installation must first identify its own path.

```sh
cd "$(git rev-parse --show-toplevel)"
rtk proxy nice -n 19 python3 -B - <<'PY'
import datetime, json, os, pathlib, runpy, shutil, subprocess, sys
root = pathlib.Path.cwd()
fragment = root / 'windows/nativestack2604.json'
lane_root = pathlib.Path.home() / '.local/state/native-agent-stack/lanes'
for name in ('command-center-resume.sh', 'co-op-resume.sh', 'codex-account-pool.sh',
             'codex-lane.sh', 'codex-root-lane.prompt.txt',
             'codex-runtime-lane.prompt.txt', 'codex-token-lane.prompt.txt',
             'codex-trading-lane.prompt.txt'):
    assert (lane_root / name).is_file(), 'Owner launcher missing: ' + name
for name in ('claude', 'codex', 'nativestack'):
    subprocess.run(['/bin/bash', '-lc', 'command -v ' + name + ' >/dev/null'], check=True)
project = pathlib.Path.home() / 'code/native-agent-stack'
assert project.is_dir(), 'Native stack project directory missing'
assert (pathlib.Path.home() / 'code/librarium-course').is_dir(), 'Course project missing'
assert (project / 'windows/ops-entry.sh').read_bytes() == (root / 'windows/ops-entry.sh').read_bytes(), 'Reviewed Operations entry missing'
local = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
    '[Environment]::GetFolderPath("LocalApplicationData")'], text=True).strip()
local = pathlib.Path(subprocess.check_output(['wslpath', '-u', local], text=True).strip())
target = local / 'Microsoft/Windows Terminal/Fragments/NativeStack/NativeStack2604.json'
settings = local / 'Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json'
assert settings.is_file(), 'Identify the installed Terminal settings path first'
sys.argv = [str(root / 'checks/check-terminal-profiles.py'), str(fragment), str(settings)]
os.environ['NATIVESTACK_MEDIA_DIR'] = '/mnt/c/Windows/Media'
checker = runpy.run_path(sys.argv[0])  # validates explicit inputs before mutation
data = checker['load_settings'](settings)
canonical = json.loads(fragment.read_text(encoding='utf-8'))['profiles']
legacy = target.parent / 'lanes.json'
legacy_profiles = []
if legacy.is_file():
    # The separately sourced lane fragment contains no inline account-pool auth.
    # Read only this known source, never the private live special-role fragment.
    legacy_data = checker['load_settings'](legacy)
    assert isinstance(legacy_data.get('profiles'), list), 'Legacy lane profiles malformed'
    legacy_profiles = [{key: profile[key] for key in ('name', 'guid') if key in profile}
                       for profile in legacy_data['profiles']]
project_settings = runpy.run_path(str(root / 'scripts/terminal_profile_ids.py'))['project_terminal_settings']
projected, changed = project_settings(data, canonical,
    legacy_native_stack_profiles=legacy_profiles)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup = pathlib.Path.home() / '.local/state/native-agent-stack/coordination' / ('terminal-profiles-' + stamp)
backup.mkdir(parents=True, exist_ok=False)
shutil.copy2(settings, backup / 'settings.json.before')
if target.exists():
    (backup / 'fragment-restore-is-human-owned').touch()
else:
    (backup / 'fragment-was-absent').touch()
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(fragment, target)
if changed:
    settings.write_text(json.dumps(projected, indent=2) + '\n', encoding='utf-8')
else:
    assert settings.read_bytes() == (backup / 'settings.json.before').read_bytes()
assert target.read_bytes() == fragment.read_bytes()  # target is now the public fragment
readback = checker['load_settings'](settings)
assert readback == projected
assert not project_settings(readback, canonical,
    legacy_native_stack_profiles=legacy_profiles)[1], 'Settings projection not idempotent'
sys.argv = [str(root / 'checks/check-terminal-profiles.py'), str(target), str(settings)]
runpy.run_path(sys.argv[0])  # explicit deployed fragment/settings/media read-back
print('Fragment/default/obsolete-profile read-back PASS; settings changed:', changed,
      '; rollback directory:', backup)
PY
```

After apply, repeat the checker with explicit fragment/settings paths and
`NATIVESTACK_MEDIA_DIR=/mnt/c/Windows/Media` to check actual sound-file presence.
The co-op opens the Command center, Co-op and account-pool profiles through
Terminal and records that each starts the intended existing session/route.
Also inspect the profile picker: exactly one visible Codex token lane, preserved
old NativeStack entries, default Claude, audible+taskbar AI bells,
Claude truecolor and static taskbar bells. These operator observations are still
pending and need their own dated receipt. The declaration checker cannot prove
native session identity, a sound playing, or a title changing in the UI.

Agent-safe rollback in the same Python/LocalAppData context above, with `backup` set to the
exact directory printed by the apply command:

```python
shutil.copy2(backup / 'settings.json.before', settings)
if (backup / 'fragment-was-absent').is_file():
    target.unlink(missing_ok=True)
else:
    assert (backup / 'fragment-restore-is-human-owned').is_file()
    print('Human operator must restore the original private fragment; do not read/copy it here')
assert settings.read_bytes() == (backup / 'settings.json.before').read_bytes()
if (backup / 'fragment-was-absent').is_file():
    assert not target.exists()
```

Sources: Microsoft's [fragment extensions](https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions)
(updated 2025-11-12, checked 2026-10-06), [default profile](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/startup)
(updated 2022-11-03, checked 2026-10-06), and the Terminal
[v1.25.2733.0 release](https://github.com/microsoft/terminal/releases/tag/v1.25.2733.0)
(2026-10-02; `dc8ae365847d41f62d1ebca93815bb00959bc12f:doc/cascadia/profiles.schema.json`).
At that pin, `CascadiaSettingsSerialization.cpp:370-371,915,1074-1092`
establishes folder-source ownership and GUID merging; the schema's `hidden`,
`tabTitle` and `closeOnExit` fields supply the settings override and defaults.
The source/transformations receipt is
`evidence/receipts/windows-terminal-2604-fragment-20261006.json`.
