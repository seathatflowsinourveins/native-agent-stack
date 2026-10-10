#!/usr/bin/env python3
"""Stage unchanged installed skills for CC-owned native plugin eval; run no model."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("security-audit", "gh-fix-ci", "gh-address-comments", "frontend-design", "typesafe-ai",
           "security-best-practices", "security-threat-model")


def stage(destination, home):
    if destination.exists():
        raise ValueError("choose a new staging directory")
    manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
    selected = {row["name"]: row for row in manifest["skills"]}
    sources = {name: home / ".agents/skills" / name for name in TARGETS}
    for name, source in sources.items():
        if hashlib.sha256((source / "SKILL.md").read_bytes()).hexdigest() != selected[name]["skill_md_sha256"]:
            raise ValueError("an installed target differs from the manifest pin")
    destination.mkdir(parents=True)
    (destination / ".claude-plugin").mkdir()
    (destination / ".claude-plugin/plugin.json").write_text(json.dumps({"name": "native-routing-eval", "version": "0.0.0"}) + "\n")
    for name, source in sources.items():
        shutil.copytree(source, destination / "skills" / name, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".venv", "node_modules"))
    router = ROOT / "adoption/skills/claude-routing"
    (destination / "skills/native-skill-routing").mkdir(parents=True)
    shutil.copyfile(ROOT / ".claude/skills/native-skill-routing/SKILL.md", destination / "skills/native-skill-routing/SKILL.md")
    shutil.copytree(router / "evals", destination / "evals")
    return len(sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    try:
        print(json.dumps({"targets_staged": stage(args.out, args.home), "model_calls": 0}))
        return 0
    except (OSError, ValueError):
        print("routing eval staging unavailable; verify the seven installed pins")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
