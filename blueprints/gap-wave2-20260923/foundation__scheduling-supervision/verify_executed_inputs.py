#!/usr/bin/env python3
"""Relate the helper-script hashes each run froze at start to the committed scripts.

After the runs, the committed scripts had their literal host home paths replaced with
`Path.home()` expressions (publication hygiene). This check re-applies the inverse,
purely mechanical substitution to each committed file and reports whether it reproduces
the hash the run froze. Anything else is reported as a mismatch.

Usage: verify_executed_inputs.py [--rev GIT_REV] RUN_RECORD.json KEY [RUN_RECORD.json KEY ...]
  --rev compares against the helper as committed at GIT_REV instead of the working tree
  (fix round 1: the original runs are checked against b7aec6b, where the helpers they ran
  were committed, because the fix round changed several helpers afterwards)
  (KEY is the dotted path to the {filename: sha256} map inside the record)
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
H = str(Path.home())
INVERSE = [
    ('Path.home() / ".local/share/codex-ecosystem/bin/dagu"', f'Path("{H}/.local/share/codex-ecosystem/bin/dagu")'),
    ('CODEX_BIN_DIR = str(Path.home() / ".local/share/codex-ecosystem/bin")', f'CODEX_BIN_DIR = "{H}/.local/share/codex-ecosystem/bin"'),
    ('Path.home() / ".cache/gap-wave2-20260923/scheduling-supervision/challengers"', f'Path("{H}/.cache/gap-wave2-20260923/scheduling-supervision/challengers")'),
    ('Path.home() / ".cache/gap-wave2-20260923/scheduling-supervision/go-setup"', f'Path("{H}/.cache/gap-wave2-20260923/scheduling-supervision/go-setup")'),
    ('Run under $HOME/codex-ecosystem/bin/ecosystem-bounded-run', f'Run under {H}/codex-ecosystem/bin/ecosystem-bounded-run'),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def locate(name):
    for base in (HERE, HERE / "challenger"):
        if (base / name).exists():
            return base / name
    return None


def committed_text(path, rev):
    if rev is None:
        return path.read_text()
    root = HERE.parents[2]
    return subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path.relative_to(root)}"],
                          capture_output=True, text=True, check=True).stdout


def main():
    report = []
    args, rev = sys.argv[1:], None
    if args[:1] == ["--rev"]:
        rev, args = args[1], args[2:]
    for record_path, key in zip(args[::2], args[1::2]):
        value = json.loads(Path(record_path).read_text())
        for part in key.split("."):
            value = value[part]
        for name, frozen in sorted(value.items()):
            path = locate(name)
            if path is None:
                report.append({"record": Path(record_path).parent.name + "/" + Path(record_path).name, "file": name, "status": "not a committed helper"})
                continue
            text = committed_text(path, rev)
            if sha(text.encode()) == frozen:
                status = "identical"
            else:
                inverse = text
                for new, old in INVERSE:
                    inverse = inverse.replace(new, old)
                status = "identical after inverse home-path substitution" if sha(inverse.encode()) == frozen else "MISMATCH"
            report.append({"record": Path(record_path).parent.name + "/" + Path(record_path).name, "key": key, "file": name, "status": status,
                           "compared_with": f"git {rev}" if rev else "working tree"})
    print(json.dumps(report, indent=2).replace(H, "$HOME"))


if __name__ == "__main__":
    main()
