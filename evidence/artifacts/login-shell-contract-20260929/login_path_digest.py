#!/usr/bin/env python3
"""Print the number of entries and a SHA-256 prefix of the PATH that a login shell ends up with, started the way the doctor's check
starts one: `env -i` with HOME, USER, LOGNAME, SHELL and the distro default PATH (from /etc/environment), then `/bin/bash -lc`.
Record the output before and after a change to the login startup files: an unchanged digest shows the change altered nothing. The
digest input is the printed PATH string with no trailing newline. Prints entry counts and a digest only, no paths.
usage: python3 -B login_path_digest.py
"""
import hashlib, json, os, subprocess
from pathlib import Path

home = Path.home()
user = os.environ.get("USER", home.name)
default_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
try:
    for line in Path("/etc/environment").read_text().splitlines():
        if line.startswith("PATH="):
            default_path = line[len("PATH="):].strip("\"'")
except OSError:
    pass
printed = subprocess.run(["/usr/bin/env", "-i", f"HOME={home}", f"USER={user}", f"LOGNAME={user}", "SHELL=/bin/bash", f"PATH={default_path}",
                          "/bin/bash", "-lc", 'printf "%s" "$PATH"'], capture_output=True, text=True, timeout=30).stdout
entries = printed.split(":")
print(json.dumps({"login_path_entries": len(entries), "login_path_sha256_prefix": hashlib.sha256(printed.encode()).hexdigest()[:16],
                  "distro_default_path_entries": len(default_path.split(":"))}))
