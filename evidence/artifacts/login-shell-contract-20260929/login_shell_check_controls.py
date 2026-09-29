#!/usr/bin/env python3
"""Controls for the login-shell PATH check that the NativeStack practice repository's `nativestack doctor` runs.

`login_shell_check` below is that doctor's function (practice repository commit 512c3e3, which has no remote, so the code is kept
here) with the home directory made a parameter so the controls can run against temporary homes. Every Windows Terminal profile on the
host starts `/bin/bash -lc`; bash reads only the first of ~/.bash_profile, ~/.bash_login and ~/.profile (bash(1) INVOCATION), and
Ubuntu's /etc/profile leaves PATH alone, so the probe starts from the distro default PATH (/etc/environment) and not from the caller's PATH.
That approximates what `wsl.exe --exec` hands a login shell: WSL's own default ends in /usr/lib/wsl/lib where /etc/environment ends in
/snap/bin (a login shell adds /snap/bin itself); the four names checked resolve the same either way.

usage: python3 -B login_shell_check_controls.py [--real-host]
Prints one JSON summary of booleans and names; temporary homes only, removed afterwards. --real-host also runs the check on the
running user's own home (read-only).
"""
import json, os, stat, subprocess, sys, tempfile
from pathlib import Path

NAMES = ["claude", "codex", "nativestack", "rtk"]


def command(argv, timeout=20):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout)
        return {"exit": result.returncode, "stdout": result.stdout.decode(errors="replace")}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit": None, "stdout": "", "error": type(error).__name__}


def login_shell_check(home, wanted=NAMES):
    default_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    try:
        for line in Path("/etc/environment").read_text().splitlines():
            if line.startswith("PATH="):
                default_path = line[len("PATH="):].strip("\"'")
    except OSError:
        pass
    user = os.environ.get("USER", home.name)
    result = command(["/usr/bin/env", "-i", f"HOME={home}", f"USER={user}", f"LOGNAME={user}", "SHELL=/bin/bash", f"PATH={default_path}",
                      "/bin/bash", "-lc", "for c in " + " ".join(wanted) + '; do command -v "$c" >/dev/null || echo "MISSING:$c"; done'])
    missing = [line[len("MISSING:"):] for line in result["stdout"].splitlines() if line.startswith("MISSING:")]
    shadows = [name for name in (".bash_profile", ".bash_login") if (home / name).is_file() and (home / name).stat().st_size == 0]
    return {"pass": result["exit"] == 0 and not missing and not shadows, "missing_in_login_shell": missing,
            "empty_files_shadowing_profile": shadows, "exit": result["exit"]}


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


def case(label, build, expect_pass, expect_shadow, expect_missing):
    tmp, home = fake_home(build)
    try:
        got = login_shell_check(home)
    finally:
        tmp.cleanup()
    ok = got["pass"] == expect_pass and got["empty_files_shadowing_profile"] == expect_shadow and sorted(got["missing_in_login_shell"]) == sorted(expect_missing)
    return {"case": label, "as_expected": ok, **got}


def main():
    cases = [
        case("A profile only", lambda h: None, True, [], []),
        case("B empty .bash_profile (the incident)", lambda h: (h / ".bash_profile").write_text(""), False, [".bash_profile"], NAMES),
        case("C real .bash_profile handing off to .profile", lambda h: (h / ".bash_profile").write_text('if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi\n'), True, [], []),
        case("D empty .bash_login", lambda h: (h / ".bash_login").write_text(""), False, [".bash_login"], NAMES),
        case("E no startup files", lambda h: (h / ".profile").unlink(), False, [], NAMES),
    ]
    summary = {"cases": cases, "all_cases_as_expected": all(c["as_expected"] for c in cases)}
    if "--real-host" in sys.argv:
        summary["real_host"] = login_shell_check(Path.home())
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_cases_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
