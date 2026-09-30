#!/usr/bin/env python3
"""Print the number of entries and a SHA-256 prefix of the PATH that a login shell ends up with, started the way the doctor's check
starts one: `env -i` with HOME, USER, LOGNAME, SHELL and the distro default PATH (from /etc/environment), then `/bin/bash -lc`.
Record the output before and after a change to the login startup files: an unchanged digest shows the change altered nothing. The
digest input is the PATH string with no trailing newline (unchanged from the first version, so old and new digests compare). Prints entry
counts and a digest only, no paths.

Revised 2026-09-30 after a cross-family review: the first version hashed whatever the login shell printed, so a startup file that failed or
exited before the PATH was printed produced the SHA-256 of an empty string with exit 0, and two such failed probes compared equal. The probe now
prints `PATH=<value>` and then `DONE`; anything else (a nonzero exit, no DONE, no PATH line) is a measurement error: a JSON line with
`measurement_error`, exit 1, no digest. `--selftest` runs the measurement against temporary homes (a working one, `exit 1`, `exit 0` before the
probe, and `exec /bin/true`, which replaces the shell before the probe) and exits 1 unless the working home measures and every failing one is refused.

usage: python3 -B login_path_digest.py [--selftest]
"""
import hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path


def distro_default_path():
    default_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    try:
        for line in Path("/etc/environment").read_text().splitlines():
            if line.startswith("PATH="):
                default_path = line[len("PATH="):].strip("\"'")
    except OSError:
        pass
    return default_path


def measure(home):
    """The measurement dict for a home, or {"measurement_error": reason} when the login shell did not reach the end of the probe."""
    user = os.environ.get("USER", home.name)
    default_path = distro_default_path()
    try:
        run = subprocess.run(["/usr/bin/env", "-i", f"HOME={home}", f"USER={user}", f"LOGNAME={user}", "SHELL=/bin/bash", f"PATH={default_path}",
                              "/bin/bash", "-lc", 'printf "PATH=%s\\nDONE\\n" "$PATH"'], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"measurement_error": f"the login shell did not run ({type(error).__name__})"}
    lines = run.stdout.splitlines()
    if run.returncode != 0:
        return {"measurement_error": "the login shell exited nonzero", "bash_exit": run.returncode}
    if len(lines) < 2 or lines[-1] != "DONE" or not lines[0].startswith("PATH="):
        return {"measurement_error": "the login shell ended before the PATH probe completed", "bash_exit": run.returncode}
    printed = lines[0][len("PATH="):]
    return {"login_path_entries": len(printed.split(":")), "login_path_sha256_prefix": hashlib.sha256(printed.encode()).hexdigest()[:16],
            "distro_default_path_entries": len(default_path.split(":"))}


def selftest():
    problems = []
    for label, startup, should_measure in (("a home that works", None, True), ("a startup file that exits 1", "exit 1\n", False),
                                           ("a startup file that exits 0 before the probe", "exit 0\n", False), ("a startup file that replaces the shell with a program that prints nothing", "exec /bin/true\n", False)):
        with tempfile.TemporaryDirectory(prefix="digest-selftest-") as raw:
            home = Path(raw)
            (home / ".profile").write_text('PATH="$HOME/bin:$PATH"\n')
            if startup is not None:
                (home / ".bash_profile").write_text(startup)
            got = measure(home)
        measured = "measurement_error" not in got
        if measured != should_measure:
            problems.append(f"{label}: measured={measured}, expected {should_measure}")
    print(json.dumps({"selftest_cases": 4, "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    result = measure(Path.home())
    print(json.dumps(result))
    sys.exit(1 if "measurement_error" in result else 0)
