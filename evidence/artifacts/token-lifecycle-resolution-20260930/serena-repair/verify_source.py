#!/usr/bin/env python3
"""Compare installed Serena schema-generating source with immutable upstream Git blobs.

Source: https://github.com/oraios/serena/tree/c6fbd1c5932df2494ffa0020af5a9fbe80b82143
This is independent source identity evidence, not an upstream behavioral test.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


PIN = "c6fbd1c5932df2494ffa0020af5a9fbe80b82143"
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
started = datetime.now(timezone.utc).isoformat()
argv = ["rtk", "gh", "api", f"repos/oraios/serena/git/trees/{PIN}?recursive=1"]
result = subprocess.run(argv, capture_output=True, check=True)
tree = json.loads(result.stdout)
assert tree["sha"] == PIN and not tree["truncated"]
binary = Path(shutil.which("serena")).resolve()
python = binary.read_text().splitlines()[0].removeprefix("#!")
discovery = subprocess.run(
    [python, "-c", "import pathlib, serena, interprompt, json, importlib.metadata as m; "
     "print(json.dumps({'roots': {'serena': str(pathlib.Path(serena.__file__).parent), "
     "'interprompt': str(pathlib.Path(interprompt.__file__).parent)}, "
     "'versions': {d.metadata['Name']: d.version for d in m.distributions()}}))"],
    env={key: os.environ[key] for key in ("HOME", "PATH") if key in os.environ},
    capture_output=True, check=True,
)
installed = json.loads(discovery.stdout)
rows = []
for file in tree["tree"]:
    parts = file["path"].split("/")
    if (file["type"] != "blob" or len(parts) < 3 or parts[0] != "src"
            or parts[1] not in installed["roots"]
            or not (file["path"].endswith(".py") or "/resources/" in file["path"])):
        continue
    local = Path(installed["roots"][parts[1]]).joinpath(*parts[2:])
    content = local.read_bytes() if local.is_file() else None
    actual = (hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
              if content is not None else None)
    rows.append({"path": file["path"], "upstream_git_blob_sha1": file["sha"],
                 "installed_git_blob_sha1": actual, "matches": file["sha"] == actual})
report = {"evidence_class": "independent_source_identity", "upstream_revision": PIN,
          "source": f"https://github.com/oraios/serena/tree/{PIN}",
          "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
          "tree_command": {"argv": argv, "exit_code": result.returncode,
                           "stdout_raw_sha256": hashlib.sha256(result.stdout).hexdigest(),
                           "stderr": result.stderr.decode()},
          "package_discovery_exit_code": discovery.returncode,
          "distribution_versions": installed["versions"], "files": rows,
          "limits": ["Only src/serena and src/interprompt Python files and resource files are compared",
                     "Dependency source is not locked by Serena's upstream installation; these versions describe this run",
                     "Source identity does not establish the origin of the historical golden response hash"]}
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"source_files_compared": len(rows), "mismatches": [r["path"] for r in rows if not r["matches"]],
                  "upstream_revision": PIN, "tree_exit_code": result.returncode}))
raise SystemExit(0 if rows and all(row["matches"] for row in rows) else 1)
