#!/usr/bin/env python3
"""Controls for the login-shell PATH check that the NativeStack practice repository's `nativestack doctor` runs.

`login_shell_check` below is that doctor's function (practice repository, which has no remote, so the code is kept here) with the home directory made a parameter so the
controls can run against temporary homes. Every Windows Terminal profile on the host starts `/bin/bash -lc`; bash reads only the FIRST of ~/.bash_profile, ~/.bash_login and
~/.profile that exists and is readable (bash(1) INVOCATION), and Ubuntu's /etc/profile leaves PATH alone, so the probe starts from the distro default PATH (/etc/environment)
and not from the caller's PATH. That approximates what `wsl.exe --exec` hands a login shell: WSL's own default ends in /usr/lib/wsl/lib where /etc/environment ends in
/snap/bin (a login shell adds /snap/bin itself); the four names checked resolve the same either way.

Revised 2026-09-30 after a cross-family review found four ways the earlier check gave a wrong answer (each is a control below, and `previous_check` keeps the earlier predicate so the
run shows the controls tell the two apart): (1) it passed when a startup file exited 0 before the probe loop ran, because no output meant "nothing missing": the probe now prints
FOUND or MISSING for every name and a final DONE, and anything less fails; (2) `command -v` accepts a shell function, which the profiles' `exec claude` cannot start: `type -P`
finds files only; (3) it called an empty ~/.bash_login a shadow even when a real ~/.bash_profile comes first and bash never reads ~/.bash_login: only the first startup file bash
would read can shadow ~/.profile; (4) the login shell's exit code alone was trusted;
and a second re-check found (5) that `type -P` can print a path that the profile's `exec` cannot start: a stale hashed pathname (a startup file's `hash -p /gone/claude claude`; `exec` uses the same
entry and fails with 127) or, when no executable matches, a non-executable regular file that bash falls back to (a mode-0644 `claude` on PATH; `exec` exits 126). A name therefore counts as found only
when the resolved path is an executable regular file.

usage: python3 -B login_shell_check_controls.py [--real-host]
Prints one JSON summary of booleans and names; temporary homes only, removed afterwards. --real-host also runs the check on the running user's own home (read-only).
"""
import json, os, stat, subprocess, sys, tempfile
from pathlib import Path

NAMES = ["claude", "codex", "nativestack", "rtk"]
STARTUP_ORDER = (".bash_profile", ".bash_login", ".profile")


def command(argv, timeout=20):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout)
        return {"exit": result.returncode, "stdout": result.stdout.decode(errors="replace")}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit": None, "stdout": "", "error": type(error).__name__}


def distro_default_path():
    default_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    try:
        for line in Path("/etc/environment").read_text().splitlines():
            if line.startswith("PATH="):
                default_path = line[len("PATH="):].strip("\"'")
    except OSError:
        pass
    return default_path


def first_startup_file(home):
    """The file a bash login shell reads: the first of ~/.bash_profile, ~/.bash_login, ~/.profile that exists and is readable."""
    for name in STARTUP_ORDER:
        path = home / name
        if path.is_file() and os.access(path, os.R_OK):
            return path
    return None


def login_shell_check(home, wanted=NAMES):
    user = os.environ.get("USER", home.name)
    probe = ("for c in " + " ".join(wanted) + '; do if p=$(type -P "$c") && [ -n "$p" ] && [ -f "$p" ] && [ -x "$p" ]; then echo "FOUND:$c"; else echo "MISSING:$c"; fi; done; echo DONE')
    result = command(["/usr/bin/env", "-i", f"HOME={home}", f"USER={user}", f"LOGNAME={user}", "SHELL=/bin/bash", f"PATH={distro_default_path()}", "/bin/bash", "-lc", probe])
    lines = result["stdout"].splitlines()
    found = [line[len("FOUND:"):] for line in lines if line.startswith("FOUND:")]
    missing = [line[len("MISSING:"):] for line in lines if line.startswith("MISSING:")]
    completed = bool(lines) and lines[-1] == "DONE" and sorted(found + missing) == sorted(wanted)
    first = first_startup_file(home)
    shadows = [first.name] if first is not None and first.name in (".bash_profile", ".bash_login") and first.stat().st_size == 0 else []
    return {"pass": result["exit"] == 0 and completed and not missing and not shadows, "missing_in_login_shell": missing,
            "empty_files_shadowing_profile": shadows, "probe_completed": completed, "exit": result["exit"]}


def previous_check(home, wanted=NAMES):
    """The check as it stood before the 2026-09-30 revision (kept only so the controls can show that they tell it from the revised one)."""
    user = os.environ.get("USER", home.name)
    result = command(["/usr/bin/env", "-i", f"HOME={home}", f"USER={user}", f"LOGNAME={user}", "SHELL=/bin/bash", f"PATH={distro_default_path()}",
                      "/bin/bash", "-lc", "for c in " + " ".join(wanted) + '; do command -v "$c" >/dev/null || echo "MISSING:$c"; done'])
    missing = [line[len("MISSING:"):] for line in result["stdout"].splitlines() if line.startswith("MISSING:")]
    shadows = [name for name in (".bash_profile", ".bash_login") if (home / name).is_file() and (home / name).stat().st_size == 0]
    return {"pass": result["exit"] == 0 and not missing and not shadows, "missing_in_login_shell": missing, "empty_files_shadowing_profile": shadows}


def fake_home(build):
    tmp = tempfile.TemporaryDirectory(prefix="login-shell-check-")
    home = Path(tmp.name)
    (home / "bin").mkdir()
    for name in NAMES:
        exe = home / "bin" / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    (home / ".profile").write_text('PATH="$HOME/bin:$PATH"\n')
    build(home)
    return tmp, home


HAND_OFF = 'if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi\n'


def case(label, build, expect_pass, expect_shadow, expect_missing, expect_completed=True, previous_pass=None):
    tmp, home = fake_home(build)
    try:
        got = login_shell_check(home)
        before = previous_check(home)
    finally:
        tmp.cleanup()
    ok = (got["pass"] == expect_pass and got["empty_files_shadowing_profile"] == expect_shadow and sorted(got["missing_in_login_shell"]) == sorted(expect_missing)
          and got["probe_completed"] == expect_completed)
    row = {"case": label, "as_expected": ok, **got}
    if previous_pass is not None:
        row["earlier_check_said_pass"] = before["pass"]
        row["earlier_check_was_wrong_here"] = before["pass"] == previous_pass and before["pass"] != expect_pass
        row["as_expected"] = ok and row["earlier_check_was_wrong_here"]
    return row


def main():
    cases = [
        case("A profile only", lambda h: None, True, [], []),
        case("B empty .bash_profile (the incident)", lambda h: (h / ".bash_profile").write_text(""), False, [".bash_profile"], NAMES),
        case("C real .bash_profile handing off to .profile", lambda h: (h / ".bash_profile").write_text(HAND_OFF), True, [], []),
        case("D empty .bash_login", lambda h: (h / ".bash_login").write_text(""), False, [".bash_login"], NAMES),
        case("E no startup files", lambda h: (h / ".profile").unlink(), False, [], NAMES),
        case("F healthy .bash_profile beside an empty .bash_login that bash never reads", lambda h: ((h / ".bash_profile").write_text(HAND_OFF), (h / ".bash_login").write_text("")),
             True, [], [], previous_pass=False),
        case("G non-empty .bash_profile that exits 0 before the probe runs", lambda h: (h / ".bash_profile").write_text("exit 0\n"), False, [], [], expect_completed=False, previous_pass=True),
        case("H .bash_profile that exits 1", lambda h: (h / ".bash_profile").write_text("exit 1\n"), False, [], [], expect_completed=False),
        case("I a shell function named claude while no executable is on PATH", lambda h: (h / ".bash_profile").write_text("claude() { :; }\n"), False, [], NAMES),
        case("J a startup file hashes claude to a path that does not exist (hash -p, after the hand-off: assigning PATH flushes the hash): type -P prints the stale path", lambda h: (h / ".bash_profile").write_text(HAND_OFF + "hash -p /nonexistent/claude claude\n"),
             False, [], ["claude"], previous_pass=True),
        case("K a non-executable claude on PATH (mode 0644): type -P falls back to it and exec exits 126", lambda h: (h / "bin" / "claude").chmod(0o644), False, [], ["claude"]),
    ]
    summary = {"cases": cases, "all_cases_as_expected": all(c["as_expected"] for c in cases)}
    if "--real-host" in sys.argv:
        summary["real_host"] = login_shell_check(Path.home())
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_cases_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
