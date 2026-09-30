#!/usr/bin/env python3
"""Reproduce, in an isolated HOME, what CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 leaves behind on Linux with bubblewrap installed, and
whether a real ~/.bash_profile that hands off to ~/.profile survives it. The real HOME is never touched: every arm runs the
installed native binary with `env -i`, a throwaway HOME inside a private temporary directory, a dummy non-credential API value
(the run stops at the API-key check after the files are written, so no model call is made) and no settings, hooks or telemetry.

Where the client's own temporary state goes. Its per-directory state folder, file-watch probe folder, sandbox multiplexer socket and messaging
socket directory (`cc-socks`) follow its temp directory, so every arm points TMPDIR and CLAUDE_CODE_TMPDIR (documented: the client appends
/claude-<uid>/ to it) at a private directory beside the throwaway home; it is removed with the arm and the script counts what landed there by
kind. That directory must stay short. The client caps the path of its messaging socket, <dir>/cc-socks/<pid>.sock, at 103 bytes (its own constant;
Linux allows 107) and, when the path is longer, falls back to a fixed /tmp/cc-socks-<uid> directory in the real /tmp (socket_path_fallback_probe.py
shows both cases: with a 7-digit pid a private path over about 81 bytes falls back). It also prefers XDG_RUNTIME_DIR over the temp directory, so the arms
run under `env -i` and never set it. The script therefore creates its scratch directory directly under /tmp with a short name, whatever TMPDIR the
caller has, and refuses to run an arm whose socket path would be too long. One path cannot be redirected: /tmp/inline-comments-buffer.jsonl (the startup code opens a fixed list of paths in append mode, which
creates a missing file and never truncates an existing one). The script reports whether it was absent before the run and is an empty regular file
created after the run began, and removes it in that case; it cannot tell its own arms' creation from a concurrent session's, so the report says
"appeared during the run".

Measured, not assumed. The top level of the real /tmp and /tmp/claude-<uid> and the presence of the placeholder names in the real home are
recorded before and after the run. Concurrent sessions can add entries to the real /tmp inside that window, so those counts are what one run saw;
the positive observation is that each arm's private directory held the client's temporary state, whose kinds and counts vary a little between runs.

The doctor. In the stock-home arm the script also runs the installed `claude doctor` twice: with the sandbox off, and with the sandbox enabled in the
home's user settings plus a planted 0-byte, read-only proj/.claude/settings.local.json. The planted file only shows that the stale-mask warning
(since 2.1.257) is live: it is not a positive control for the scrub placeholder, which is a writable file in the home that the warning's scope, the
read-only mask files at the sandbox's deny paths, does not cover. The doctor's silence about ~/.bash_profile is therefore expected by that scope
and says nothing about whether the file is a problem.

Revised 2026-09-30 after a cross-family review: the real-home check listed neither ~/.bash_profile (the incident's file) nor the client's other startup placeholders and compared only
whether a name existed, so a new empty ~/.bash_profile outside the arms, or a truncated ~/.bashrc, left `real_home_placeholder_names_unchanged` true. It now covers the client's own
placeholder list (startup_placeholder_names.py) and compares lstat mode, size, mtime and inode of every name, without opening any file. `--selftest` shows on a temporary home that creation,
truncation, appending, replacement and a touch are each detected.

usage: python3 scrub_placeholder_probe.py [--keep|--selftest]      prints one JSON summary of counts, names and booleans; no paths, no output text
Arms: A control without the variable; B the variable with a stock Ubuntu-shaped HOME (~/.profile only); C the variable with a real
~/.bash_profile that sources ~/.profile.
"""
import hashlib, json, os, re, shutil, stat, subprocess, sys, tempfile, time
from pathlib import Path

CLAUDE = Path.home() / ".local/bin/claude"        # symlink to the native binary; the ecosystem launcher is not involved
DUMMY = "dummy-value-not-a-credential"
HAND_OFF = '# hand off to ~/.profile so a generated file can never hide it\nif [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi\n'


def listing(root):
    """Relative name -> (type, size) for every entry under root, without following links."""
    found = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            found[rel] = ("link", 0)
        elif path.is_dir():
            found[rel] = ("dir", 0)
        else:
            found[rel] = ("file", path.stat().st_size)
    return found


SHARED = Path("/tmp/inline-comments-buffer.jsonl")   # the client hard-codes /tmp, whatever TMPDIR says


def empty_dirs(root, created):
    """Created directories that hold no entry after the run."""
    return sorted(k for k, v in created.items() if v[0] == "dir" and not any(other.startswith(k + "/") for other in listing(root)))


# The client's own home placeholder list (startup_placeholder_names.py: .gitconfig, .bash_profile, .bashrc, .bash_aliases, .profile, .zshrc, .bunfig.toml, .netrc, .npmrc, .yarnrc,
# .yarnrc.yml), the login file bash reads after ~/.bash_profile, and other paths the client or its tools touch.
REAL_HOME_NAMES = [".gitconfig", ".bash_profile", ".bashrc", ".bash_aliases", ".profile", ".zshrc", ".bash_login", ".bunfig.toml", ".gitmodules", ".netrc", ".npmrc", ".yarnrc",
                   ".yarnrc.yml", ".pip", ".config/pip", ".config/git", ".config/glab-cli", ".config/anthropic", ".claude/seed-admin"]
STATE_ROOT = Path("/tmp") / f"claude-{os.getuid()}"


def real_home_state(root=None):
    """name -> None when absent, else (mode, size, mtime_ns, inode) from lstat. Creation, replacement, truncation and modification each change it; no file is opened."""
    root = Path.home() if root is None else Path(root)
    state = {}
    for name in REAL_HOME_NAMES:
        try:
            info = os.lstat(root / name)
            state[name] = (info.st_mode, info.st_size, info.st_mtime_ns, info.st_ino)
        except FileNotFoundError:
            state[name] = None
        except OSError as error:
            state[name] = ("unreadable", type(error).__name__)
    return state


def selftest():
    """Each change to a checked name must change real_home_state; an untouched home must compare equal."""
    results = {}
    with tempfile.TemporaryDirectory(prefix="ss") as raw:
        root = Path(raw)
        (root / ".bashrc").write_text("export A=1\n")
        (root / ".profile").write_text("PATH=$PATH\n")
        (root / ".zshrc").write_text("zsh\n")
        base = real_home_state(root)
        results["untouched_home_compares_equal"] = real_home_state(root) == base
        (root / ".bash_profile").write_text("")
        results["new_empty_bash_profile_detected"] = real_home_state(root) != base
        (root / ".bash_profile").unlink()
        results["removing_it_again_restores_the_state"] = real_home_state(root) == base
        (root / ".bashrc").write_text("")
        results["truncating_an_existing_file_detected"] = real_home_state(root) != base
        (root / ".bashrc").write_text("export A=1\n")
        os.utime(root / ".bashrc", ns=(base[".bashrc"][2] + 5_000_000_000, base[".bashrc"][2] + 5_000_000_000))
        results["a_touch_that_changes_only_the_mtime_detected"] = real_home_state(root) != base
        (root / ".profile").write_text("PATH=$PATH\nexport B=2\n")
        results["appending_detected"] = real_home_state(root) != base
        original = (root / ".zshrc").read_bytes()
        (root / ".zshrc").unlink()
        (root / ".zshrc").write_bytes(original)
        results["replacing_a_file_with_a_same_size_copy_detected"] = real_home_state(root) != base
    for label, startup, expect_none in (("login_path_of_a_working_home_is_measured", None, False), ("login_path_of_a_failing_startup_file_is_unmeasured", "exit 1\n", True),
                                        ("login_path_of_a_startup_file_that_exits_early_is_unmeasured", "exit 0\n", True)):
        with tempfile.TemporaryDirectory(prefix="ss") as raw:
            home = Path(raw)
            (home / ".profile").write_text('export PATH="$HOME/.local/bin:$PATH"\n')
            if startup is not None:
                (home / ".bash_profile").write_text(startup)
            results[label] = (login_path(home) is None) == expect_none and (expect_none or has_local_bin(home, login_path(home)) is True)
    print(json.dumps({"selftest": results, "all_detected_as_expected": all(results.values())}))
    return 0 if all(results.values()) else 1


def state_entries():
    return set(os.listdir(STATE_ROOT)) if STATE_ROOT.is_dir() else set()


SOCKET_PATH_LIMIT = 103   # the client's own cap on its messaging-socket path, in bytes (Linux sun_path allows 107); a longer path makes it fall back to /tmp/cc-socks-<uid>


def kind_of(name):
    if re.fullmatch(r"cc-socks(-\d+)?", name):
        return "messaging_socket_dirs"
    if re.fullmatch(r"srt-mux-\d+-\d+\.sock", name):
        return "sandbox_multiplexer_sockets"
    if name.startswith("fswatch-probe-"):
        return "file_watch_probe_dirs"
    if name.startswith("claude-"):
        return "client_state_dirs"
    return "other"


def kinds(names):
    counted = {"messaging_socket_dirs": 0, "sandbox_multiplexer_sockets": 0, "file_watch_probe_dirs": 0, "client_state_dirs": 0, "other": 0}
    for name in names:
        counted[kind_of(name)] += 1
    return counted


def private_entries(private):
    """Top-level names under the private temp directory and inside its claude-<uid> folder, by kind."""
    names = set(os.listdir(private)) if private.is_dir() else set()
    inner = private / f"claude-{os.getuid()}"
    if inner.is_dir():
        names |= set(os.listdir(inner))
    return kinds(names)


def native_doctor(home, env, planted=None):
    run = subprocess.run([str(CLAUDE.resolve()), "doctor"], cwd=home / "proj", env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    plain = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", (run.stdout + run.stderr).decode("utf-8", "replace"))
    found = re.search(r"(\d+) warnings? found", plain)
    result = {"exit": run.returncode, "warnings_found": int(found.group(1)) if found else None, "mentions_bash_profile": "bash_profile" in plain,
              "mentions_mask_stale_or_placeholder": bool(re.search(r"mask|stale|placeholder", plain, re.I))}
    if planted is not None:
        result["names_planted_stale_mask_file"] = bool(re.search(r"Stale sandbox mask files", plain)) and planted in plain
    return result


def sandbox_doctor(home, env):
    """The doctor with the sandbox enabled, and a planted stale mask file (0-byte, read-only) as the positive control."""
    (home / ".claude").mkdir(exist_ok=True)
    (home / ".claude" / "settings.json").write_text('{"sandbox": {"enabled": true}}\n')
    planted = home / "proj" / ".claude" / "settings.local.json"
    planted.parent.mkdir(exist_ok=True)
    planted.write_bytes(b"")
    planted.chmod(0o444)
    return native_doctor(home, env, planted="settings.local.json")


def login_path(home):
    """The PATH a login shell ends up with, or None when the shell failed or ended before the probe completed (the probe prints PATH=<value> and then DONE)."""
    run = subprocess.run(["/usr/bin/env", "-i", f"HOME={home}", "PATH=/usr/bin:/bin", "/bin/bash", "-lc", 'printf "PATH=%s\\nDONE\\n" "$PATH"'],
                         capture_output=True, text=True, timeout=30)
    lines = run.stdout.splitlines()
    if run.returncode != 0 or len(lines) < 2 or lines[-1] != "DONE" or not lines[0].startswith("PATH="):
        return None
    return lines[0][len("PATH="):]


def has_local_bin(home, path_value):
    return None if path_value is None else str(home / ".local/bin") in path_value.split(":")


def arm(label, scrub, real_bash_profile, base, doctor=False):
    home = Path(tempfile.mkdtemp(prefix=f"arm-{label}-", dir=base))
    private = Path(tempfile.mkdtemp(prefix="t", dir=base))   # beside the home, so the home's listing is unchanged; short, see the docstring
    if len(str(private / "cc-socks" / "9999999.sock")) > SOCKET_PATH_LIMIT:
        raise SystemExit("the private temp path is too long for the client's messaging socket: it would fall back to the real /tmp")
    (home / "proj").mkdir()
    (home / ".local/bin").mkdir(parents=True)
    (home / ".profile").write_text('export PATH="$HOME/.local/bin:$PATH"\n')
    if real_bash_profile:
        (home / ".bash_profile").write_text(HAND_OFF)
    before = listing(home)
    before_bash_profile = hashlib.sha256((home / ".bash_profile").read_bytes()).hexdigest() if real_bash_profile else None
    path_before = login_path(home)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": DUMMY, "DISABLE_AUTOUPDATER": "1",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1", "TMPDIR": str(private), "CLAUDE_CODE_TMPDIR": str(private)}
    if scrub:
        env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"
    run = subprocess.run([str(CLAUDE.resolve()), "-p", "hi", "--max-turns", "1"], cwd=home / "proj", env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, timeout=120)
    after = listing(home)
    private_kinds = private_entries(private)
    doctor_result = {"sandbox_off": native_doctor(home, env), "sandbox_on_with_planted_stale_mask_file": sandbox_doctor(home, env)} if doctor else None
    created = {k: v for k, v in after.items() if k not in before}
    zero_files = sorted(k for k, v in created.items() if v == ("file", 0))
    result = {
        "arm": label, "scrub_variable": scrub, "real_bash_profile_present_before": real_bash_profile, "client_exit": run.returncode,
        "entries_created": len(created), "empty_files_created": len(zero_files),
        "directories_created": sum(1 for v in created.values() if v[0] == "dir"),
        "empty_directories_created": len(empty_dirs(home, created)),
        "created_in_home_top_level": sorted(k for k in created if "/" not in k),
        "created_in_working_dir": sorted(k.split("/", 1)[1] for k in created if k.startswith("proj/"))[:30],
        "bash_profile_exists_after": (home / ".bash_profile").exists(),
        "bash_profile_empty_after": (home / ".bash_profile").exists() and (home / ".bash_profile").stat().st_size == 0,
        "bash_profile_mode_after": oct(stat.S_IMODE((home / ".bash_profile").stat().st_mode)) if (home / ".bash_profile").exists() else None,
        "real_bash_profile_untouched": (hashlib.sha256((home / ".bash_profile").read_bytes()).hexdigest() == before_bash_profile) if real_bash_profile and (home / ".bash_profile").exists() else None,
        "login_path_had_local_bin_before": has_local_bin(home, path_before),
        "login_path_has_local_bin_after": has_local_bin(home, login_path(home)),
    }
    if doctor_result is not None:
        result["native_doctor"] = doctor_result
    result["client_temp_entries_in_private_dir"] = private_kinds
    return home, result


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    keep = "--keep" in sys.argv
    base = Path(tempfile.mkdtemp(prefix="sp", dir="/tmp"))   # short and directly under /tmp, whatever TMPDIR the caller has
    results = []
    shared_before = SHARED.exists()
    started = time.time()
    presence_before = real_home_state()
    tmp_before, state_before = set(os.listdir("/tmp")), state_entries()
    try:
        for label, scrub, real in (("A_control_no_scrub", False, False), ("B_scrub_stock_home", True, False), ("C_scrub_real_bash_profile", True, True)):
            _, res = arm(label, scrub, real, base, doctor=(label == "B_scrub_stock_home"))
            results.append(res)
    finally:
        if not keep:
            shutil.rmtree(base, ignore_errors=True)
    new_in_tmp = {name for name in set(os.listdir("/tmp")) - tmp_before if name != SHARED.name}
    new_in_state = state_entries() - state_before
    appeared = False
    if not shared_before and SHARED.exists() and not SHARED.is_symlink():
        info = SHARED.lstat()
        appeared = stat.S_ISREG(info.st_mode) and info.st_size == 0 and info.st_ctime >= started - 1
    if appeared:
        SHARED.unlink()
    summary = {"claude": subprocess.run([str(CLAUDE.resolve()), "--version"], capture_output=True, text=True).stdout.strip(),
               "bubblewrap": shutil.which("bwrap") is not None, "bubblewrap_version": subprocess.run(["bwrap", "--version"], capture_output=True, text=True).stdout.strip(),
               "arms": results, "scratch_removed": not base.exists(), "real_home_placeholder_names_unchanged": real_home_state() == presence_before,
               "real_home_names_checked": len(REAL_HOME_NAMES), "real_home_compared_by": "lstat mode, size, mtime and inode",
               "real_home_names_changed": sorted(name for name, before in presence_before.items() if real_home_state()[name] != before),
               "real_temp_top_level_entries_new_during_run": {"in_tmp_excluding_the_shared_file": kinds(new_in_tmp), "in_tmp_claude_uid": kinds(new_in_state)},
               "shared_temp_file": {"name": SHARED.name, "present_before_run": shared_before, "appeared_during_run": appeared,
                                    "removed_by_script": appeared and not SHARED.exists(), "present_after_script": SHARED.exists()}}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
