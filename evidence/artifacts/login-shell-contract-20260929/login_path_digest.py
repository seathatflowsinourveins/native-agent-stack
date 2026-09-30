#!/usr/bin/env python3
"""Print the number of entries and a SHA-256 prefix of the PATH that a login shell ends up with, started the way the doctor's check
starts one: `env -i` with HOME, USER, LOGNAME, SHELL and the distro default PATH (from /etc/environment), then `/bin/bash -lc`.
Record the output before and after a change to the login startup files: an unchanged digest shows the change altered nothing. The
digest input is the PATH string with no trailing newline (unchanged from the first version, so old and new digests compare). Prints entry
counts and a digest only, no paths.

Revised 2026-09-30 after a cross-family review: the first version hashed whatever the login shell printed, so a startup file that failed or
exited before the PATH was printed produced the SHA-256 of an empty string with exit 0, and two such failed probes compared equal. The probe now
prints its record between two lines that carry a random nonce (`BEGIN-<nonce>`, the PATH, `END-<nonce>`); anything else (a nonzero exit, a marker missing or repeated) is a measurement
error: a JSON line with `measurement_error`, exit 1, no digest. `--selftest` runs the measurement against temporary homes (a working one, `exit 1`, `exit 0` before the
probe, and `exec /bin/true`, which replaces the shell before the probe) and exits 1 unless the working home measures and every failing one is refused.

Revised again 2026-09-30 after the re-check of that repair: it took the first `PATH=` line of the output, so a startup file that printed one had its own text hashed (two different PATHs
compared equal) and a newline inside a PATH component cut it short. A startup file cannot know the nonce, the payload is read as bytes (no newline translation) and the digest covers all of it.
`--selftest` adds a startup file that logs a `PATH=` line, one that prints a plain line, one that prints a non-UTF-8 byte, two different PATHs, and a newline inside a component (ten checks in all).

usage: python3 -B login_path_digest.py [--selftest]
"""
import hashlib, json, os, secrets, subprocess, sys, tempfile
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
    nonce = secrets.token_hex(8)   # a startup file cannot know it, so what it prints cannot pass for the probe's own record
    begin, end = f"BEGIN-{nonce}\n".encode(), f"\nEND-{nonce}\n".encode()
    try:
        run = subprocess.run(["/usr/bin/env", "-i", f"HOME={home}", f"USER={user}", f"LOGNAME={user}", "SHELL=/bin/bash", f"PATH={default_path}",
                              "/bin/bash", "-lc", f'printf "BEGIN-{nonce}\\n%s\\nEND-{nonce}\\n" "$PATH"'], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"measurement_error": f"the login shell did not run ({type(error).__name__})"}
    if run.returncode != 0:
        return {"measurement_error": "the login shell exited nonzero", "bash_exit": run.returncode}
    out = run.stdout
    if out.count(begin) != 1 or out.count(end) != 1 or out.index(begin) + len(begin) > out.index(end):
        return {"measurement_error": "the login shell ended before the PATH probe completed", "bash_exit": run.returncode}
    printed = out[out.index(begin) + len(begin):out.index(end)]   # the whole payload, newlines inside a component included
    return {"login_path_entries": len(printed.split(b":")), "login_path_sha256_prefix": hashlib.sha256(printed).hexdigest()[:16],
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

    def digest(startup, path_line):
        with tempfile.TemporaryDirectory(prefix="digest-selftest-") as raw:
            home = Path(raw)
            (home / ".profile").write_text(path_line)
            if startup is not None:
                (home / ".bash_profile").write_text(startup)
            return measure(home)

    first = digest(None, 'PATH="/synthetic/first:$PATH"\n')
    second = digest(None, 'PATH="/synthetic/second:$PATH"\n')
    noisy = digest('echo "PATH=logged-before-the-final-path"\n. "$HOME/.profile"\n', 'PATH="/synthetic/first:$PATH"\n')
    newline = digest(None, "PATH=$'/synthetic/with\\nnewline':\"$PATH\"\n")
    hello = digest('echo hello\n. "$HOME/.profile"\n', 'PATH="/synthetic/first:$PATH"\n')
    binary = digest("printf '\\377\\n'\n. \"$HOME/.profile\"\n", 'PATH="/synthetic/first:$PATH"\n')
    measured_all = all("measurement_error" not in got for got in (first, second, noisy, newline, hello, binary))
    for label, ok in (("the four homes measure", measured_all),
                      ("two different PATHs give different digests", measured_all and first["login_path_sha256_prefix"] != second["login_path_sha256_prefix"]),
                      ("a startup file that logs a PATH= line first does not change the digest of the same PATH", measured_all and noisy["login_path_sha256_prefix"] == first["login_path_sha256_prefix"]),
                      ("a plain output line before the probe leaves a healthy home measurable and its digest unchanged", measured_all and hello["login_path_sha256_prefix"] == first["login_path_sha256_prefix"]),
                      ("a non-UTF-8 byte in a startup file's output is not a crash and does not change the digest", measured_all and binary["login_path_sha256_prefix"] == first["login_path_sha256_prefix"]),
                      ("a newline inside a PATH component stays one entry and changes the digest", measured_all and newline["login_path_entries"] == first["login_path_entries"]
                       and newline["login_path_sha256_prefix"] != first["login_path_sha256_prefix"])):
        if not ok:
            problems.append(label)
    print(json.dumps({"selftest_cases": 10, "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    result = measure(Path.home())
    print(json.dumps(result))
    sys.exit(1 if "measurement_error" in result else 0)
