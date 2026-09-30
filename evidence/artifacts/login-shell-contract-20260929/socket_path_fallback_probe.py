#!/usr/bin/env python3
"""Does the installed client write its messaging-socket directory into the real /tmp when the private temp directory it was given is too long?

The client keeps one Unix socket per session at <dir>/cc-socks/<pid>.sock, where <dir> is XDG_RUNTIME_DIR when that is set and its temp directory
(CLAUDE_CODE_TMPDIR, else TMPDIR) otherwise. It caps that socket path at 103 bytes, a constant of the client (Linux itself allows 107), and when the
path is longer it falls back to a fixed /tmp/cc-socks-<uid> directory (measured against the installed 2.1.284 binary: the fallback appears in the real
/tmp). With a 7-digit pid, a private directory path over about 81 bytes therefore falls back. Redirecting TMPDIR and CLAUDE_CODE_TMPDIR only helps
while the private path is short, and XDG_RUNTIME_DIR must be left unset (the client prefers it over the temp directory).

Two runs of the same throwaway-home scrub start (`env -i`, no XDG_RUNTIME_DIR, a dummy non-credential API value; the run stops at the API-key
check): a private directory 17 bytes long (a 39-byte socket path) and one 99 bytes long (a 121-byte socket path). Each records the top-level names that
appeared in the real /tmp, where the `cc-socks` directory landed and whether a fallback directory already existed before the run (then the run is not
conclusive and says so: a fallback directory that is already there cannot appear). A fallback directory that appeared is removed only when it is an
empty directory owned by this user and named cc-socks or cc-socks-<uid>; the shared /tmp/inline-comments-buffer.jsonl is reported (present before,
appeared during the run, removed by the script) and removed only when it was absent before and is an empty regular file created after the run began.
Prints counts and booleans; no paths.
usage: python3 -B socket_path_fallback_probe.py
"""
import json, os, re, shutil, stat, subprocess, tempfile, time
from pathlib import Path

CLAUDE = Path.home() / ".local/bin/claude"
LIMIT = 103                         # the client's own cap on the socket path, in bytes
SHARED = Path("/tmp/inline-comments-buffer.jsonl")
FALLBACK = re.compile(r"cc-socks(-\d+)?")


def run(label, private_parts):
    base = Path(tempfile.mkdtemp(prefix="sp", dir="/tmp"))
    home = base / "h"
    (home / "proj").mkdir(parents=True)
    private = base.joinpath(*private_parts)
    private.mkdir(parents=True)
    before = set(os.listdir("/tmp"))
    fallback_before = sorted(name for name in before if FALLBACK.fullmatch(name))
    shared_before = SHARED.exists()
    started = time.time()
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": "dummy-value-not-a-credential", "DISABLE_AUTOUPDATER": "1",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
           "TMPDIR": str(private), "CLAUDE_CODE_TMPDIR": str(private)}
    assert "XDG_RUNTIME_DIR" not in env
    subprocess.run([str(CLAUDE.resolve()), "-p", "hi", "--max-turns", "1"], cwd=home / "proj", env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    appeared = sorted(set(os.listdir("/tmp")) - before - {base.name, SHARED.name})
    in_private = sorted(p.name for p in private.rglob("cc-socks*"))
    fallback_new = [name for name in appeared if FALLBACK.fullmatch(name)]
    removed = 0
    for name in fallback_new:
        target = Path("/tmp") / name
        info = target.lstat()
        if stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not os.listdir(target):
            target.rmdir()
            removed += 1
    socket_path_bytes = len(str(private / "cc-socks" / "1234567.sock"))
    shutil.rmtree(base, ignore_errors=True)
    shared_appeared = False
    if not shared_before and SHARED.exists() and not SHARED.is_symlink():
        info = SHARED.lstat()
        shared_appeared = stat.S_ISREG(info.st_mode) and info.st_size == 0 and info.st_ctime >= started - 1
        if shared_appeared:
            SHARED.unlink()
    return {"run": label, "private_dir_path_bytes": len(str(private)), "socket_path_bytes_with_a_7_digit_pid": socket_path_bytes,
            "exceeds_the_clients_socket_path_cap": socket_path_bytes > LIMIT,
            "cc_socks_in_private_dir": len(in_private), "cc_socks_fallback_dirs_appeared_in_real_tmp": len(fallback_new),
            "fallback_dir_already_present_before_the_run": bool(fallback_before), "conclusive": not fallback_before,
            "other_new_names_in_real_tmp": len(appeared) - len(fallback_new), "fallback_dirs_removed_after_assertions": removed,
            "shared_temp_file": {"present_before_run": shared_before, "appeared_during_run": shared_appeared, "removed_by_script": shared_appeared and not SHARED.exists()}}


results = [run("short private path", ["t"]), run("long private path", ["x" * 40, "y" * 40, "z"])]
print(json.dumps({"socket_path_cap_bytes": LIMIT, "runs": results}, indent=2))
