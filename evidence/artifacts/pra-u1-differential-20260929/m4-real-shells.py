"""The M4 fixtures of the U1 pivot under REAL shells, against the kernel. Counts only.

    python3 m4-real-shells.py --repo <checkout> [--control silent-curl]

The fixture lists of tests/test_token_measurement.py (D7: a double-quoted run string expanded by the outer shell first; R1: a heredoc operator
after a closed "$( )"; R3: an escaped blank before a #; the expansion of an unquoted heredoc body; a run string after an opening backquote)
each carry the number of times a stub `curl` ran when the command ran under bash 5.2 and dash. This script runs every command of every list
under both shells (a PATH that holds only stubs and symlinks to the real bash, dash, cat, pwd and date; a temporary HOME and working directory;
10 seconds; no standard input; output discarded). The stub curl and wget log each call; the stub ssh logs nothing and runs `sh` on the words
after its destination, else on its standard input, which is what a remote login shell does (OpenSSH ssh(1)).

A fixture agrees when the stub ran the documented number of times in both shells, and the kernel's fetchKind reads a fetch exactly when it did
(R1_MULTILINE is the documented limit: a construct that runs over lines carries its command's head on an earlier line, so the kernel reads
the body as data, a possible fetch, never a confirmed one, although curl ran). It prints counts (fixtures, agreements, disagreements, by list)
and exits 1 when any fixture disagrees. --control silent-curl makes the stubs log nothing: every fixture that should run curl then
disagrees, which shows that the probe can fail.
"""
import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--control", choices=["silent-curl"])
args = parser.parse_args()
repo = Path(args.repo).resolve()
sys.path.insert(0, str(repo))
os.chdir(repo)
fixtures = importlib.import_module("tests.test_token_measurement")
GROUPS = {  # list -> the number of curl runs documented for each of its commands
    "D7_EXECUTED": 1, "D7_INNER": 1, "D7_TWICE": 2, "D7_DATA": 0, "R1_EXECUTED": 1, "R1_MULTILINE": 1, "R1_DATA": 0,
    "HD_ONCE": 1, "HD_TWICE": 2, "HD_DATA": 0, "BQ_ONCE": 1, "BQ_DATA": 0, "R3_EXECUTED": 1,
}
DOCUMENTED_LIMIT = "R1_MULTILINE"
shells = {name: shutil.which(name) for name in ("bash", "dash", "cat", "pwd", "date")}
missing = [name for name, path in shells.items() if path is None]
if missing:
    sys.exit("m4-real-shells: not installed: " + ", ".join(missing))

work = Path(tempfile.mkdtemp(prefix="m4-real-shells-"))
try:
    bin_dir, home, log = work / "bin", work / "home", work / "log"
    bin_dir.mkdir()
    home.mkdir()
    stub = "#!/bin/sh\n" + ("" if args.control else 'echo "$0 $*" >> "$STUB_LOG"\n')
    for name in ("curl", "wget"):
        (bin_dir / name).write_text(stub)
        (bin_dir / name).chmod(0o755)
    (bin_dir / "ssh").write_text('#!/bin/sh\nwhile [ $# -gt 0 ]; do case "$1" in -*) shift;; *) break;; esac; done\nshift\nif [ $# -gt 0 ]; then exec sh -c "$*"; else exec sh; fi\n')
    (bin_dir / "ssh").chmod(0o755)
    for name, real in (("bash", shells["bash"]), ("sh", shells["dash"]), ("dash", shells["dash"]), ("cat", shells["cat"]), ("pwd", shells["pwd"]), ("date", shells["date"])):
        os.symlink(real, bin_dir / name)

    def runs(shell, text):
        log.write_text("")
        env = {"PATH": str(bin_dir), "HOME": str(home), "STUB_LOG": str(log), "LC_ALL": "C"}
        try:
            subprocess.run([shells[shell], "-c", text], env=env, cwd=home, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        except subprocess.TimeoutExpired:
            return -1
        return len([line for line in log.read_text().splitlines() if line.strip()])

    commands = [(name, command) for name in GROUPS for command in getattr(fixtures, name)]
    (work / "commands.json").write_text(json.dumps([command for _, command in commands]))
    kernel = (repo / "examples/claude-native/workflows/child-usage.mjs").as_uri()
    script = f"import * as k from {json.dumps(kernel)}\nimport {{ readFileSync }} from 'node:fs'\n" \
             f"console.log(JSON.stringify(JSON.parse(readFileSync({json.dumps(str(work / 'commands.json'))}, 'utf8')).map((c) => k.fetchKind(c) !== null)))\n"
    done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=120, check=False)
    if done.returncode:
        sys.exit("m4-real-shells: the kernel failed: " + done.stderr[-400:])
    confirmed = json.loads(done.stdout)

    report = {"fixtures": len(commands), "agree": 0, "disagree": 0, "control": args.control, "groups": {}}
    for (name, command), kernel_confirmed in zip(commands, confirmed):
        want = GROUPS[name]
        bash_runs, dash_runs = runs("bash", command), runs("dash", command)
        expect_confirmed = bash_runs > 0 and name != DOCUMENTED_LIMIT
        ok = bash_runs == want and dash_runs == want and kernel_confirmed == expect_confirmed
        group = report["groups"].setdefault(name, {"fixtures": 0, "agree": 0})
        group["fixtures"] += 1
        group["agree"] += ok
        report["agree" if ok else "disagree"] += 1
finally:
    shutil.rmtree(work, ignore_errors=True)
print(json.dumps(report))
sys.exit(1 if report["disagree"] else 0)
