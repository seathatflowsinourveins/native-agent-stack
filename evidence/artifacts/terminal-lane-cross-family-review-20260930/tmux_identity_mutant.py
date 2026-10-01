#!/usr/bin/env python3
"""Does the `--selftest` of a tmux probe notice when the command-line clause of `server_identity` is deleted? (finding F7 of the post-merge read, 2026-09-30). That clause, `socket not in cmdline`, is the only check that refuses
ANOTHER tmux server whose pid is answered by mistake or by a lie: without it the probe would signal a server that is not its own. The script runs the unmutated probe's selftest (it must pass), then a temporary copy under
/var/tmp with the clause removed (its selftest must FAIL, and the failing check must be the shutdown-failure control). Prints the exit status and the control lines of both runs. Exit 0 when the unmutated selftest passed and
the mutated one failed in the shutdown-failure control, 1 otherwise. Needs tmux. usage: tmux_identity_mutant.py <checkout> <bell|sync>"""
import subprocess
import sys
import tempfile
from pathlib import Path

checkout, which = Path(sys.argv[1]).resolve(), sys.argv[2]
relative = {"bell": "evidence/artifacts/notification-types-20260929/tmux_bell_probe.py", "sync": "evidence/artifacts/terminal-lane-cross-family-review-20260930/tmux_sync_probe.py"}[which]
text = (checkout / relative).read_text(encoding="utf-8")
CLAUSE = ' or socket not in (Path("/proc") / str(pid) / "cmdline").read_bytes()'
assert text.count(CLAUSE) == 1, f"the command-line clause was not found exactly once ({text.count(CLAUSE)})"
results = {}
for label, body in (("unmutated", text), ("command-line clause removed", text.replace(CLAUSE, ""))):
    with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="tim-") as raw:
        path = Path(raw) / "probe.py"
        path.write_text(body, encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(path), "--selftest"], capture_output=True, text=True, timeout=600)
    control = [line for line in run.stdout.splitlines() if "shutdown-failure control" in line]
    summary = [line for line in run.stdout.splitlines() if line.startswith("selftest:")]
    results[label] = (run.returncode, control)
    print(f"{which}, {label}: exit {run.returncode} | {summary} | control lines {[line.split(':')[0] for line in control]}")
unmutated_ok = results["unmutated"][0] == 0
mutant_caught = results["command-line clause removed"][0] != 0 and any(line.startswith("FAIL") for line in results["command-line clause removed"][1])
print(f"the unmutated selftest passes: {unmutated_ok}; the mutant is caught by the shutdown-failure control: {mutant_caught}")
sys.exit(0 if unmutated_ok and mutant_caught else 1)
