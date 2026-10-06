"""Repository-only port of the maintained Windows Terminal policy checker.

Source: nativestack-practice@a7b8018524575cabbd979e6f2e1c84ee6e94700f:
checks/check-terminal-profiles.py (SHA2567e85df7e).
Usage: python3 -B checks/check-terminal-profiles.py [fragment.json [settings-fixture.json]]
No arguments check windows/nativestack2604.json. Only explicit fixture paths
are read; native client configuration and deployed files are never discovered.
"""
import json, os, pathlib, re, sys

root = pathlib.Path(__file__).resolve().parents[1]
fixture = True
fragment = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'windows/nativestack2604.json'
settings_files = [pathlib.Path(sys.argv[2])] if len(sys.argv) > 2 else []
sys.path.insert(0, str(root / 'scripts'))
from terminal_profile_ids import FRAGMENT_FOLDER, derived_guid
profiles = json.loads(fragment.read_text(encoding='utf-8'))['profiles']
# Measured 2026-09-28 (16-bit PCM RMS, dBFS): Windows Notify System Generic -24.7 (rejected: too loud),
# Windows Ding -40.9, Windows Notify -38.1, chimes -41.1, notify -35.6, ding -50.0 (0.4 s).
QUIET_SOUNDS = {'windows ding.wav', 'windows notify.wav', 'chimes.wav', 'notify.wav', 'ding.wav'}
MEDIA = 'c:\\windows\\media\\'
MEDIA_DIR = pathlib.Path(os.environ['NATIVESTACK_MEDIA_DIR']) if os.environ.get('NATIVESTACK_MEDIA_DIR') else None

def quiet_sound(sound):
    """Exactly C:\\Windows\\Media\\<a measured file>: no subdirectory and no '..' (Windows compares case-insensitively, so this does too)."""
    low = sound.lower()
    return low.startswith(MEDIA) and low[len(MEDIA):] in QUIET_SOUNDS

def sound_present(sound):
    """Check file existence only in an explicitly selected media directory."""
    return MEDIA_DIR is None or (MEDIA_DIR / sound[len(MEDIA):]).is_file()
# openai/codex rust-v0.157.1 codex-rs/tui/src/chatwidget/notifications.rs type_name(), L72-L81.
CODEX_KINDS = {'agent-turn-complete', 'approval-requested', 'plan-mode-prompt', 'async-question'}
CODEX_WANTED = ['approval-requested', 'plan-mode-prompt', 'async-question']
errors = []
# Windows Terminal gives a fragment profile that declares no guid a stable one: UUIDv5 of the profile name under UUIDv5 of the fragment folder's name,
# both under the fragment namespace, names as UTF-16LE (Profile::_GenerateGuidForProfile and the fragment page's "Generating a new profile GUID" at
# microsoft/terminal v1.25.2733.0, dc8ae365847d41f62d1ebca93815bb00959bc12f). A settings.json override keyed to that value must be checked like one keyed to a declared guid.
def guid_problems(profiles):
    """Explicit identifiers preserve Microsoft's original fragment identity."""
    problems, seen = [], set()
    if not isinstance(profiles, list) or not profiles:
        return ['profiles: expected a nonempty array']
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            problems.append(f'profile[{index}]: expected an object')
            continue
        name, guid = profile.get('name'), profile.get('guid')
        label = f'profile[{index}]'
        if not isinstance(name, str) or not name:
            problems.append(label + ': name is required')
            continue
        try:
            expected = derived_guid(FRAGMENT_FOLDER, name)
        except UnicodeError:
            problems.append(label + ': this maintained GUID recipe supports ASCII profile names only')
            continue
        if not isinstance(guid, str) or guid.lower() != expected.lower():
            problems.append(label + ': explicit guid must match the stable fragment identity')
        elif guid.lower() in seen:
            problems.append(label + ': duplicate profile guid')
        else:
            seen.add(guid.lower())
    return problems


def check(condition, message):
    if not condition:
        errors.append(message)

errors.extend(guid_problems(profiles))
if errors:
    for message in errors:
        print('FAIL ' + message)
    sys.exit(1)

CLIENT = re.compile(r'(?:exec\s+|-lc\s+"?)(claude|codex)\b')
# A20 host-owned launchers hold session details outside Git; A19's lane
# launcher comes from the coordinator's existing lanes.json. Exact contracts
# classify their clients without reading or executing those private files.
HOST_CLIENTS = {
    'command-center-resume.sh': 'claude', 'co-op-resume.sh': 'claude',
    'codex-account-pool.sh': 'codex', 'codex-lane.sh': 'codex',
}
HOST_LAUNCHER = re.compile(r'exec\s+(?:/bin/)?bash\s+~/.local/state/native-agent-stack/lanes/([\w-]+\.sh)(?=[\s"\']|$)')

def ai_client(command):
    """claude or codex when the profile starts that client, through `exec <client>` or a bare `bash -lc "<client>"`."""
    found = CLIENT.search(command or '')
    if found:
        return found.group(1)
    wrapper = HOST_LAUNCHER.search(command or '')
    return HOST_CLIENTS.get(wrapper.group(1)) if wrapper else None

# Options an AI-client profile may not hand to its client (README "Login shell contract" gives the sources). A fixed name replaces the generated tab title and a live duplicate is renamed to a
# variant; --continue and Codex --last reopen the newest session of the launch directory, so two tabs of one directory share one transcript; --fork-session starts a
# new session on every launch; effort, settings and permission mode belong to the client, the ecosystem launcher and the host settings (AGENTS.md: no overrides through
# launch wrappers). `claude --resume` with no value or one session id and `codex resume` with no argument stay allowed.
BARRED_OPTIONS = {
    '--name': 'a fixed name replaces the generated tab title, and a second live session with it is renamed to a variant',
    '--effort': 'the client and the ecosystem launcher own the effort',
    '--settings': 'the host and project settings files own the client settings',
    '--permission-mode': 'the client and the host settings own the permission mode',
    '--continue': 'it reopens the newest session of the directory, so two tabs of one directory share one transcript',
    '--fork-session': 'it starts a new session on every launch instead of continuing one',
}
CODEX_BARRED_OPTIONS = {'--last': 'it resumes the newest session of the directory, so two tabs of one directory share one thread, and it starts a new one when none exists'}
# Claude's short spellings of --name and --continue (the installed `claude --help` lists `-n, --name` and `-c, --continue`): the same options, so refused too.
# Codex's -c means --config, which is not barred.
CLAUDE_SHORT_OPTIONS = {'-n': '--name', '-c': '--continue'}

def passed_options(client, command):
    """The barred options the command line hands to the client, as (long spelling, reason) pairs in command order. Only the words after the client's name count, so
    `bash -lc` can never read as -c; both `--name x` and `--name=x` are seen."""
    found = CLIENT.search(command or '')
    if not found:
        return []
    words = re.findall(r'(?:^|[\s"\'])(--?[A-Za-z][\w-]*)(?=[=\s"\']|$)', command[found.end():])
    if client == 'claude':
        words = [CLAUDE_SHORT_OPTIONS.get(word, word) for word in words]
    barred = {**BARRED_OPTIONS, **(CODEX_BARRED_OPTIONS if client == 'codex' else {})}
    return [(word, barred[word]) for word in dict.fromkeys(words) if word in barred]

def bell_values(profile):
    style = profile.get('bellStyle', 'audible')  # Windows Terminal's documented default
    return [style] if isinstance(style, str) else list(style)

def check_bell_flags(name, profile):
    # On Terminal main, "all" (0xffffffff) will also raise a toast once microsoft/terminal#20011 ships.
    check('all' not in bell_values(profile) and 'notification' not in bell_values(profile),
          name + ': bellStyle must list flags explicitly, never all/notification')

def bell_sounds(profile):
    """bellSound is a file location or an array of them (Windows Terminal plays one of an array at random), and Windows
    Terminal rewrites a single string as a one-element array when it saves settings.json (observed 2026-10-02 on 1.24)."""
    sound = profile.get('bellSound', '')
    return [sound] if isinstance(sound, str) else [item if isinstance(item, str) else '' for item in sound]

def check_sounds(name, profile):
    sounds = bell_sounds(profile)
    check(bool(sounds), name + ': bellSound must name a sound')
    for sound in sounds:  # every listed sound can play, so every one must pass
        check(sound.lower().startswith(MEDIA), name + ': bellSound must be an absolute local Windows sound')
        check(quiet_sound(sound), name + ': bellSound must be one of the measured quiet sounds')
        check(not quiet_sound(sound) or sound_present(sound), name + ': bellSound must name a file that exists in the Windows Media folder')

def check_ai_profile(name, profile):
    values = bell_values(profile)
    check_bell_flags(name, profile)
    # suppressApplicationTitle discards every program-sent title, so seven Claude tabs all read the same.
    check(profile.get('suppressApplicationTitle') is not True, name + ': AI-client profiles must let program titles through')
    check(values == ['audible', 'taskbar'], name + ': expected the reviewed bellStyle')
    check_sounds(name, profile)
    command = profile.get('commandline')
    for option, reason in passed_options(ai_client(command), command):  # one finding per barred option
        errors.append(name + ': the command must not pass ' + option + ' (' + reason + ')')

for profile in profiles:
    name, command = profile['name'], profile['commandline']
    if ai_client(command):
        check_ai_profile(name, profile)
    else:
        check_bell_flags(name, profile)
        # Static shells keep their title; a readline completion bell must not sound in them.
        check(bell_values(profile) == ['taskbar'], name + ': static profiles stay silent (taskbar only)')

# Every fragment profile that starts Claude (the default and its resume profile): Windows Terminal forwards a profile's environment keys through WSLENV.
for profile in profiles:
    if ai_client(profile['commandline']) == 'claude':
        check(profile.get('environment', {}).get('COLORTERM') == 'truecolor', profile['name'] + ': the profile environment must set COLORTERM=truecolor (Claude falls back to 8-bit without it)')
        check('COLORTERM' not in profile['commandline'], profile['name'] + ': use the profile environment key, not a shell wrapper')

def load_settings(path):
    """settings.json may carry comments; strip // and /* */ outside strings, then parse."""
    raw, out, i, in_string = path.read_text(encoding='utf-8-sig'), [], 0, False
    while i < len(raw):
        c = raw[i]
        if in_string:
            out.append(c)
            if c == '\\' and i + 1 < len(raw):
                i += 1
                out.append(raw[i])
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
            out.append(c)
        elif raw.startswith('//', i):
            while i < len(raw) and raw[i] != '\n':
                i += 1
            continue
        elif raw.startswith('/*', i):
            i = raw.find('*/', i + 2) + 2 if raw.find('*/', i + 2) >= 0 else len(raw)
            continue
        else:
            out.append(c)
        i += 1
    return json.loads(''.join(out))

settings_scanned = 0
fragment_ai = {(p.get('guid') or derived_guid(FRAGMENT_FOLDER, p['name'])).lower() for p in profiles if ai_client(p['commandline'])}  # a fragment profile may declare no guid
for settings_path in settings_files:
    data = load_settings(settings_path)
    listed = data['profiles']['list'] if isinstance(data['profiles'], dict) else data['profiles']
    defaults = data['profiles'].get('defaults', {}) if isinstance(data['profiles'], dict) else {}
    check(defaults.get('suppressApplicationTitle') is not True, 'settings.json defaults: must not suppress program titles for every profile')
    if 'bellStyle' in defaults:
        check_bell_flags('settings.json defaults', defaults)
    for profile in listed:
        name = 'settings.json ' + profile.get('name', profile.get('guid', '?'))
        client = ai_client(profile.get('commandline'))
        if client:
            check_ai_profile(name, profile)
        else:
            if 'bellStyle' in profile:
                check_bell_flags(name, profile)
            if profile.get('guid', '').lower() in fragment_ai:
                # a user override of a fragment AI profile may only restate the policy
                check(profile.get('suppressApplicationTitle') is not True, name + ': AI-client profiles must let program titles through')
                if 'bellStyle' in profile:
                    check(bell_values(profile) == ['audible', 'taskbar'], name + ': expected the reviewed bellStyle')
                if 'bellSound' in profile:
                    check_sounds(name, profile)
    settings_scanned += 1

if errors:
    for message in errors:
        print('FAIL ' + message)
    sys.exit(1)
print('PASS ' + str(len(profiles)) + ' profiles: AI clients let titles through, ring audible+taskbar with a quiet sound and pass none of the barred options; static shells stay silent; '
      'every Claude profile sets COLORTERM through the profile environment key' + ('' if fixture else '; Codex kinds and the deployed copy verified')
      + ('; ' + str(settings_scanned) + ' settings.json scanned (AI profiles there follow the same rules)' if settings_scanned else ''))
