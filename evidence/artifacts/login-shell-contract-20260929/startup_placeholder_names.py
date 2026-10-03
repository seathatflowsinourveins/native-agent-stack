#!/usr/bin/env python3
"""Read the installed native Claude Code binary for the startup code that CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 runs (bubblewrap on Linux) and
print, as JSON, which paths it creates and how. Read-only: it reads the binary and prints names and booleans, never a path of this host.

The code is a loop over a fixed list of paths (home files written `${home}/<name>`, working-directory files `${cwd}/<name>`, and one
absolute path in /tmp), each opened with mkdir(dirname, {recursive: true}) and then open(path, "a").close(): append mode, so a missing
file is created empty and an existing file is never truncated. This script locates that loop by its shared /tmp file and parses the list.
usage: python3 -B startup_placeholder_names.py
"""
import json, os, re
from pathlib import Path

binary = Path(os.path.realpath(Path.home() / ".local/bin/claude"))
data = binary.read_bytes().decode("utf-8", "replace")
SHARED = "/tmp/inline-comments-buffer.jsonl"
result = {"claude": binary.name, "loops_found": 0}
for match in re.finditer(re.escape('"' + SHARED + '"'), data):
    window = data[max(0, match.start() - 1500): match.end() + 400]
    loop = re.search(r"for\(let (\w+) of\[((?:`\$\{\w+\}/[^`]+`,)+)\"" + re.escape(SHARED) + r"\"[^\]]*\]\)try\{await (\w+)\(\w+\(\1\),\{recursive:!0\}\),await\(await (\w+)\(\1,\"(\w+)\"\)\)\.close\(\)\}catch", window)
    if not loop:
        continue
    names = re.findall(r"`\$\{(\w+)\}/([^`]+)`", loop.group(2))
    result["loops_found"] += 1
    result["open_mode"] = loop.group(5)                       # "a" is append
    result["creates_parent_directories"] = True               # the mkdir(dirname, {recursive: true}) in the matched loop
    result["home_relative_names"] = [name for scope, name in names if scope == "e"]
    result["working_directory_relative_names"] = [name for scope, name in names if scope == "r"]
    result["absolute_path_outside_any_home"] = SHARED
    result["further_working_directory_names_from_a_variable"] = ".map(" in loop.group(0)
    result["bash_profile_in_list"] = ".bash_profile" in result["home_relative_names"]
    result["profile_in_list"] = ".profile" in result["home_relative_names"]
    result["bash_login_in_list"] = ".bash_login" in result["home_relative_names"]
print(json.dumps(result, indent=2))
