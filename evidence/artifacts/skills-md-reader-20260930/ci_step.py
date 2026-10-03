#!/usr/bin/env python3
"""Checks the CI provisioning of the yaml pin without CI: (1) the sha256 of each file skills-yaml.pin.json lists is the
sha256 of that file in the registry tarball whose sha512 is the pin's integrity; (2) the `run: |` script of the step of
.github/workflows/validate.yml that reads the pin, run as the runner runs it (bash -e over the script file) with the
given npm first on PATH, in a scratch workspace that holds only the pin, installs into RUNNER_TEMP and exports
LANDSCAPE_SWEEP_SKILLS_YAML through the GITHUB_ENV file; (3) skill_md.mjs, run with the given node on that install,
reports the pinned package, integrity and pin sha256.

  ci_step.py <checkout> <scratch dir> <npm bin dir> <node binary> <yaml tarball>

Prints one JSON object; exit 0 when all three hold."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

checkout, scratch, npm_bin, node, tarball = (Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4],
                                              Path(sys.argv[5]))
PIN_REL = "tools/sota-convergence/landscape-sweep/skills-yaml.pin.json"
pin_bytes = (checkout / PIN_REL).read_bytes()
pin = json.loads(pin_bytes)

raw = tarball.read_bytes()
integrity = "sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode()
with tarfile.open(tarball) as archive:
    members = {member.name[len("package/"):]: archive.extractfile(member).read()
               for member in archive.getmembers() if member.isfile()}
matched = sum(hashlib.sha256(members.get(rel[len("node_modules/yaml/"):], b"")).hexdigest() == want["sha256"]
              for rel, want in pin["files"].items())

lines = (checkout / ".github/workflows/validate.yml").read_text(encoding="utf-8").split("\n")
index = next(i for i, line in enumerate(lines) if PIN_REL in line and not line.lstrip().startswith("#"))
start = next(i for i in range(index, -1, -1) if lines[i].startswith("      - "))
end = next((i for i in range(index + 1, len(lines)) if lines[i].startswith("      - ")), len(lines))
step = lines[start:end]
run_at = next(i for i, line in enumerate(step) if line.startswith("        run: |"))
body = []
for line in step[run_at + 1:]:
    if line.strip() and not line.startswith("          "):
        break
    body.append(line[10:])
workspace, runner_temp = scratch / "workspace", scratch / "runner-temp"
(workspace / PIN_REL).parent.mkdir(parents=True, exist_ok=True)
(workspace / PIN_REL).write_bytes(pin_bytes)
runner_temp.mkdir(parents=True, exist_ok=True)
(scratch / "github-env").write_text("", encoding="utf-8")
(scratch / "step.sh").write_text("\n".join(body).rstrip("\n") + "\n", encoding="utf-8")
env = {**os.environ, "PATH": f"{npm_bin}{os.pathsep}{os.environ.get('PATH', '')}", "RUNNER_TEMP": str(runner_temp),
       "GITHUB_ENV": str(scratch / "github-env")}
done = subprocess.run(["bash", "--noprofile", "--norc", "-e", str(scratch / "step.sh")], cwd=workspace, env=env,
                      capture_output=True, text=True, timeout=600, check=False)
exported = (scratch / "github-env").read_text(encoding="utf-8")
directory = exported.partition("LANDSCAPE_SWEEP_SKILLS_YAML=")[2].strip()
npm_version = subprocess.run([str(Path(npm_bin) / "npm"), "--version"], capture_output=True, text=True).stdout.strip()
reader = subprocess.run([node, str(checkout / "tools/sota-convergence/landscape-sweep/skill_md.mjs")],
                        input='{"items": []}', capture_output=True, text=True, timeout=120, check=False,
                        env={**os.environ, "LANDSCAPE_SWEEP_SKILLS_YAML": directory})
record = json.loads(reader.stdout)["reader"] if reader.stdout.strip() else {}
node_version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
result = {
    "tarball_sha512_is_the_pinned_integrity": integrity == pin["package"]["integrity"],
    "pinned_files_matching_the_tarball": f"{matched} of {len(pin['files'])}",
    "step": {"npm": npm_version, "exit": done.returncode,
             "exported": exported.replace(str(runner_temp), "<runner-temp>").strip()},
    "reader": {"node": node_version, "exit": reader.returncode, "record": record,
               "pin_sha256_is_this_pin": record.get("pin_sha256") == hashlib.sha256(pin_bytes).hexdigest()},
}
print(json.dumps(result, indent=1))
ok = (result["tarball_sha512_is_the_pinned_integrity"] and matched == len(pin["files"]) and done.returncode == 0
      and directory and record.get("ok") is True and result["reader"]["pin_sha256_is_this_pin"])
sys.exit(0 if ok else 1)
