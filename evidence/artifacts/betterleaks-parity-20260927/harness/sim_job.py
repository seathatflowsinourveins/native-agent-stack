#!/usr/bin/env python3
"""Local simulation of validate.yml's secret-scan-betterleaks `run:` steps (local integration helper,
scratch only; not a GitHub Actions run). Steps are cut out with tests/test_workflow_hardening.py's own
jobs()/step_block() helpers. The job sets `defaults: run: shell: bash`, which GitHub runs as
`bash --noprofile --norc -eo pipefail {0}` (docs.github.com: workflow syntax, jobs.<job_id>.steps[*].shell;
an unspecified shell would be `bash -e {0}`, without pipefail), so each run block executes with that
command, the step's env, RUNNER_TEMP pointed at a scratch directory and the checkout as cwd. A step whose
`if:` requires steps.install.outcome == 'success' is skipped when the install step failed.
Prints step names, exit codes and the last output lines (scanner logs are --redact'ed)."""
import os
import re
import subprocess
import sys
from pathlib import Path

root, runner_temp, only = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
sys.path.insert(0, str(root))
from tests.test_workflow_hardening import jobs, step_block  # noqa: E402

job = jobs((root / ".github/workflows/validate.yml").read_text(encoding="utf-8"))["secret-scan-betterleaks"]
# The command below is GitHub's for an explicit bash; refuse to simulate a job that no longer sets it.
assert re.search(r"(?m)^    defaults:\n      run:\n(?:        #.*\n)*        shell: bash[ \t]*$", job), "job shell"
names = re.findall(r"(?m)^      - name: (.+)$", job)
outcome = {}
for name in names:
    block = step_block(job, name)
    if "\n        run: |\n" not in block:
        print(f"-- {name}: uses-step, not simulated")
        continue
    if only and not any(o in name for o in only):
        continue
    # cosign keeps its TUF cache under $TUF_ROOT (default ~/.sigstore); keep it in scratch, not the real home.
    env = dict(os.environ, RUNNER_TEMP=str(runner_temp), TUF_ROOT=str(runner_temp / "tuf"),
               HOME=str(runner_temp / "home"), XDG_CACHE_HOME=str(runner_temp / "cache"))
    env_part = re.search(r"(?ms)^        env:\n(.*?)(?=^        \S)", block)
    if env_part:
        for line in env_part.group(1).splitlines():
            m = re.match(r"^          ([A-Z0-9_]+): (.*)$", line)
            if m:
                value = m.group(2).strip()
                if len(value) >= 2 and value[0] == value[-1] == "'":
                    value = value[1:-1].replace("''", "'")
                env[m.group(1)] = value
    script = "\n".join(line[10:] for line in block.split("\n        run: |\n", 1)[1].splitlines()) + "\n"
    if "steps.install.outcome == 'success'" in block and outcome.get("install") not in (None, 0):
        print(f"-- {name}: skipped (install failed)")
        continue
    proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script], cwd=root, env=env,
                          capture_output=True, text=True)
    if "id: install" in block:
        outcome["install"] = proc.returncode
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    if "fixture tests" in name:  # assertion messages can quote fixture findings; keep the summary only
        tail = [line for line in tail if re.match(r"^(Ran \d+ tests|OK|FAILED)", line)]
    tail = tail[-6:]
    print(f"-- {name}: rc={proc.returncode}")
    for line in tail:
        print("     " + re.sub(r"/tmp/\S+", "<scratch>", line)[:170])
