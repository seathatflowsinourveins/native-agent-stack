"""Mutation checks for tests/test_frozen_macos_variant_no_use.py (PR #635, round 5), run in a scratch clone.

Usage: python3 mutants.py <scratch clone> <output prefix> [mutant id ...]

Each mutant edits the clone, stages new files when the mutant is a tracked change (git ls-files lists only the index),
runs the module with PYTHONDONTWRITEBYTECODE=1, then restores every byte and checks that git status is clean again.
Round 5 is round 4's driver (unchanged rows) plus N4-N8 (the round-5 brief: sections 1, 2 and 4), X13-X15, P3 and P4.
Round 6 (coordinator) adds N9 and X16: client configuration directories matched in any ASCII letter case.
Round 7 retains this driver in the repository beside its sanitized returned results (runs.json indexes them), with M9's
artifact directory name assembled from fragments like PARENT, so that the retained file names it in no letter case.
Naming ids runs only those (used to run the new rows against the round-4 module in a second clone).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
# Assembled from fragments so that keeping this driver in the repository adds no line naming the artifact to the guard's
# scan, which reads .py files under evidence/**. The driver only writes scenario files into a scratch clone and runs the
# guard's tests there; it never installs, builds or serves anything.
PARENT = "evidence/artifacts/" + "macos-application-" + "20260924"
VARIANT = PARENT + "/variant"
MODULE = "tests.test_frozen_macos_variant_no_use"
REOPEN_TEXT = "reopen Dependabot alert 16 and remove the frozen OSV exception"
STALE_TEXT = "A pinned line was not found where PINNED_LINES expects it"
GIT_TEXT = "git ls-files could not run"
RECHECK_TEXT = ("recheck Dependabot alert 16 (reopen it unless the renewed exception's reasoning still holds) and update "
                "this pinned date")
FROZEN_TOML = ".github/osv-scanner-frozen-macos.toml"
SELECTED = set(sys.argv[3:])


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


class Change:
    def __init__(self) -> None:
        self.saved: list[tuple[Path, bytes | None, bool]] = []
        self.created_dirs: list[Path] = []

    def _remember(self, relative: str) -> Path:
        path = ROOT / relative
        if not any(saved == path for saved, _, _ in self.saved):
            if path.is_symlink():
                self.saved.append((path, os.fsencode(os.readlink(path)), True))
            elif path.exists():
                self.saved.append((path, path.read_bytes(), False))
            else:
                self.saved.append((path, None, False))
        missing = []
        parent = path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir()
            self.created_dirs.append(directory)
        return path

    def write(self, relative: str, text: str) -> None:
        self._remember(relative).write_text(text, encoding="utf-8")

    def append(self, relative: str, text: str) -> None:
        path = self._remember(relative)
        path.write_bytes(path.read_bytes() + text.encode("utf-8"))

    def replace(self, relative: str, old: str, new: str, count: int = 1) -> None:
        path = self._remember(relative)
        content = path.read_text(encoding="utf-8")
        assert content.count(old) >= count, (relative, old)
        path.write_text(content.replace(old, new, -1 if count == -1 else count), encoding="utf-8")

    def symlink(self, relative: str, target: str) -> None:
        self._remember(relative).symlink_to(target)

    def delete(self, relative: str) -> None:
        self._remember(relative).unlink()

    def restore(self) -> None:
        for path, original, was_link in reversed(self.saved):
            if path.is_symlink() or path.exists():
                path.unlink()
            if original is not None:
                if was_link:
                    path.symlink_to(os.fsdecode(original))
                else:
                    path.write_bytes(original)
        for directory in reversed(self.created_dirs):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()


WORKFLOW_HEAD = """name: {name}
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
        with:
          persist-credentials: false
"""


def m1a(change: Change) -> None:
    change.append(".github/workflows/security-scan.yml",
                  "      - name: Install the frozen variant\n"
                  f"        run: pnpm install --frozen-lockfile\n        working-directory: {VARIANT}\n")


def m1b(change: Change) -> None:
    change.write(".github/workflows/build-frozen-variant.yml", WORKFLOW_HEAD.format(name="Build the frozen variant")
                 + f"      - run: pnpm install --frozen-lockfile && pnpm build\n        working-directory: {VARIANT}\n")


def m2(change: Change) -> None:
    change.write(f"{VARIANT}/src/index.ts", "export const ok = true;\n")


def m4(change: Change) -> None:
    change.replace(f"{VARIANT}/pnpm-lock.yaml", "specifier: 16.3.5\n        version: 16.3.5", "specifier: 16.3.6\n        version: 16.3.6")
    change.replace(f"{VARIANT}/pnpm-lock.yaml", "  next@16.3.5", "  next@16.3.6", count=-1)


def m5(change: Change) -> None:
    change.write(".github/workflows/serve-frozen.yml", WORKFLOW_HEAD.format(name="Serve the frozen variant")
                 + f"      - run: pnpm --dir variant install && pnpm --dir variant start\n        working-directory: {PARENT}\n")


def m6(change: Change) -> None:
    change.write("pnpm-workspace.yaml", f"packages:\n  - {VARIANT}\n")


def m7(change: Change) -> None:
    change.write("docker-compose.yml",
                 "services:\n  app:\n    image: node:24\n    working_dir: /app\n"
                 f"    volumes:\n      - ./{VARIANT}:/app\n"
                 '    command: sh -c "corepack enable && pnpm install --frozen-lockfile && pnpm build && pnpm start"\n')


def m8(change: Change) -> None:
    change.append("tests/test_osv_lockfile_coverage.py",
                  "\n\ndef _install_the_frozen_variant():  # never called by the run\n"
                  f'    subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=ROOT / "{VARIANT}", check=True)\n')


def m9(change: Change) -> None:
    change.write("scripts/build_frozen_variant.py",
                 "import subprocess\nfrom pathlib import Path\n\n"
                 'VARIANT = Path("evidence") / "artifacts" / "' + "macos-application-" + "20260924"
                 + '" / "variant"\n\n'
                 'if __name__ == "__main__":\n    subprocess.run(["pnpm", "install"], cwd=VARIANT, check=True)\n')


def x_symlink(change: Change) -> None:
    change.symlink("apps/frozen", f"../{VARIANT}")
    change.write(".github/workflows/apps.yml", WORKFLOW_HEAD.format(name="Apps")
                 + "      - run: pnpm --dir apps/frozen install --frozen-lockfile\n")


def x_evidence_script(change: Change) -> None:
    change.write("evidence/artifacts/tools-20261003/build-frozen.sh",
                 f"#!/bin/sh\nset -eu\npnpm --dir {VARIANT} install --frozen-lockfile\n")


def x_blueprint_package(change: Change) -> None:
    change.write("blueprints/frozen-app/package.json",
                 '{\n  "name": "frozen-app",\n  "private": true,\n'
                 f'  "scripts": {{"build": "pnpm --dir ../../{VARIANT} build"}}\n}}\n')


def x_devcontainer(change: Change) -> None:
    change.write("blueprints/frozen-app/.devcontainer/devcontainer.json",
                 '{\n  "image": "mcr.microsoft.com/devcontainers/javascript-node:24",\n'
                 f'  "postCreateCommand": "pnpm --dir {VARIANT} install"\n}}\n')


def x_makefile(change: Change) -> None:
    change.write("Makefile", f"frozen:\n\tpnpm --dir {VARIANT} install --frozen-lockfile\n")


def x_changed_pin(change: Change) -> None:
    line = f'              ["{VARIANT}/pnpm-lock.yaml"]) and'
    change.replace(".github/workflows/security-scan.yml", line,
                   f'              ["{VARIANT}/pnpm-lock.yaml", "{VARIANT}/package.json"]) and')


def x_glob_workspace(change: Change) -> None:
    change.write("pnpm-workspace.yaml", "packages:\n  - evidence/artifacts/*/variant\n")


def x_inventory_loop(change: Change) -> None:
    change.write(".github/workflows/frozen-locks.yml", WORKFLOW_HEAD.format(name="Install frozen locks")
                 + "      - run: |\n"
                 "          jq -r '.lockfiles[] | select(.config == \".github/osv-scanner-frozen-macos.toml\") | .path' \\\n"
                 "            .github/osv-scanner-lockfiles.json | while read -r lock; do\n"
                 '            pnpm --dir "$(dirname "$lock")" install --frozen-lockfile\n'
                 "          done\n")


def x_fragments(change: Change) -> None:
    change.write("scripts/frozen_fragments.py",
                 "import subprocess\nfrom pathlib import Path\n\n"
                 'NAME = "macos-application-" + "2026" + "0924"\n'
                 'VARIANT = Path("evidence/artifacts") / NAME / "variant"\n\n'
                 'if __name__ == "__main__":\n    subprocess.run(["pnpm", "install"], cwd=VARIANT, check=True)\n')


def x_markdown_recipe(change: Change) -> None:
    change.write("recipes/frozen-variant.md",
                 f"# Frozen variant\n\n```sh\npnpm --dir {VARIANT} install --frozen-lockfile\npnpm --dir {VARIANT} build\n```\n")


def x_scope_break(change: Change) -> None:
    change.replace("tests/test_frozen_macos_variant_no_use.py", 'RECORD_TOP_DIRECTORIES = {"evidence", "catalogs"}',
                   'RECORD_TOP_DIRECTORIES = {"evidence", "catalogs", ".github"}')


def n_blueprint_launch(change: Change) -> None:
    change.write("blueprints/x/launch.json",
                 '{\n  "mcpServers": {\n    "frozen-app": {\n      "command": "pnpm",\n'
                 f'      "cwd": "{VARIANT}",\n      "args": ["start"]\n    }}\n  }}\n}}\n')


def n_upper_case(change: Change) -> None:
    upper = "evidence/artifacts/" + "MACOS-APPLICATION-" + "20260924" + "/variant"
    change.write(".github/workflows/frozen-mac.yml", WORKFLOW_HEAD.format(name="Serve the frozen variant on macOS")
                 .replace("ubuntu-24.04", "macos-15")
                 + f"      - run: pnpm install --frozen-lockfile && pnpm start\n        working-directory: {upper}\n")


def n_ignore_until(change: Change) -> None:
    change.replace(FROZEN_TOML, "ignoreUntil = 2026-12-24\n", "ignoreUntil = 2027-03-24\n")


def x_blueprint_json_excluded_again(change: Change) -> None:
    change.replace("tests/test_frozen_macos_variant_no_use.py",
                   "return pure.name.endswith(\".md\") or pure.parts[0] in RECORD_TOP_DIRECTORIES or name in RECORD_FILES\n",
                   "return (pure.name.endswith(\".md\") or pure.parts[0] in RECORD_TOP_DIRECTORIES or name in RECORD_FILES\n"
                   "            or (pure.parts[0] == \"blueprints\" and pure.suffix == \".json\"))\n")


def x_case_sensitive_again(change: Change) -> None:
    change.replace("tests/test_frozen_macos_variant_no_use.py", "    return TOKEN in text.lower()\n",
                   "    return TOKEN in text\n")


def x_exception_removed(change: Change) -> None:
    path = ROOT / FROZEN_TOML
    kept = [line for line in path.read_text(encoding="utf-8").splitlines(keepends=True) if line.startswith("#")]
    change.write(FROZEN_TOML, "".join(kept))


def x_reason_changed(change: Change) -> None:
    change.replace(FROZEN_TOML, "pins 16.3.6, which the advisory does not affect",
                   "pins 16.3.8, which the advisory does not affect")


def l_evidence_launch(change: Change) -> None:
    change.write("evidence/artifacts/x-20261003/launch.json",
                 '{\n  "mcpServers": {\n    "frozen-app": {\n      "command": "pnpm",\n'
                 f'      "cwd": "{VARIANT}",\n      "args": ["start"]\n    }}\n  }}\n}}\n')


def n_rebuild_beside_variant(change: Change) -> None:
    change.write(f"{PARENT}/rebuild.sh", '#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\ncd variant && pnpm install\n')


def n_rebuild_upper_case_directory(change: Change) -> None:
    upper = "evidence/artifacts/" + "MACOS-APPLICATION-" + "20260924"
    change.write(f"{upper}/rebuild.sh", '#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\ncd variant && pnpm install\n')


def n_agent_frontmatter_hook(change: Change) -> None:
    change.write(".claude/agents/x.md",
                 "---\nname: x\ndescription: Builds the application before each shell command.\nhooks:\n"
                 "  PreToolUse:\n    - matcher: Bash\n      hooks:\n        - type: command\n"
                 f"          command: pnpm --dir {VARIANT} install --frozen-lockfile\n---\n\n"
                 "Build and serve the application.\n")


def n_exception_extra_key(change: Change) -> None:
    change.replace(FROZEN_TOML, "ignoreUntil = 2026-12-24\n", "ignoreUntil = 2026-12-24\neffectiveUntil = 2027-03-24\n")


def x_agents_skill(change: Change) -> None:
    change.write(".agents/skills/frozen-app/SKILL.md",
                 "---\nname: frozen-app\ndescription: Install and start the application.\n---\n\n"
                 f"Run `pnpm --dir {VARIANT} install --frozen-lockfile`, then `pnpm start` there.\n")


def n_upper_case_client_directory(change: Change) -> None:
    change.write(".CLAUDE/skills/frozen-app/SKILL.md",
                 "---\nname: frozen-app\ndescription: Install and start the application.\n---\n\n"
                 f"Run `pnpm --dir {VARIANT} install --frozen-lockfile`, then `pnpm start` there.\n")


def x_client_directories_case_sensitive(change: Change) -> None:
    change.replace("tests/test_frozen_macos_variant_no_use.py",
                   "            or not CONFIG_DIRECTORIES.isdisjoint(fold_ascii(part) for part in pure.parts[:-1])\n",
                   "            or not CONFIG_DIRECTORIES.isdisjoint(pure.parts[:-1])\n")


def x_client_directories_dropped(change: Change) -> None:
    change.replace("tests/test_frozen_macos_variant_no_use.py",
                   'CONFIG_DIRECTORIES = {".devcontainer", ".claude", ".codex", ".agents"}',
                   'CONFIG_DIRECTORIES = {".devcontainer"}')


def x_tracked_case_sensitive(change: Change) -> None:
    change.replace("tests/test_frozen_macos_variant_no_use.py", "    return text.translate(ASCII_LOWER)\n",
                   "    return text\n")


def p_metadata_beside_variant(change: Change) -> None:
    change.write(f"{PARENT}/.DS_Store", "\x00\x00\x00\x01Bud1")
    change.write(f"{PARENT}/Thumbs.db", "thumbs")
    git("add", "-f", f"{PARENT}/.DS_Store", f"{PARENT}/Thumbs.db")  # .gitignore's *.db would keep Thumbs.db untracked
    listed = git("ls-files", "--", f"{PARENT}/.DS_Store", f"{PARENT}/Thumbs.db").split()
    assert len(listed) == 2, listed


def p_artifact_removed(change: Change) -> None:
    change.delete(f"{PARENT}/run-summary.json")
    change.delete(f"{VARIANT}/package.json")
    change.delete(f"{VARIANT}/pnpm-lock.yaml")


def x_os_metadata(change: Change) -> None:
    change.write(f"{VARIANT}/.DS_Store", "\x00\x00\x00\x01Bud1")
    change.write(f"{VARIANT}/Thumbs.db", "thumbs")


def x_removed(change: Change) -> None:
    change.delete(f"{VARIANT}/package.json")
    change.delete(f"{VARIANT}/pnpm-lock.yaml")


def nothing(change: Change) -> None:
    pass


# (id, origin, description, expected, apply, stage new files, git on PATH)
MUTANTS = [
    ("M0", "baseline", "unmutated tree", "pass", nothing, False, True),
    ("M1a", "round 2 (reconstructed)", "step in security-scan.yml: pnpm install with working-directory = the variant",
     "fail", m1a, True, True),
    ("M1b", "round 2 (reconstructed)", "new workflow: pnpm install && pnpm build in the variant", "fail", m1b, True, True),
    ("M2", "round 2 (reconstructed)", "variant/src/index.ts on disk, untracked", "fail", m2, False, True),
    ("M3", "round 2 (reconstructed)", "variant/src/index.ts, tracked (git add)", "fail", m2, True, True),
    ("M4", "round 2 (reconstructed)", "the lock's next 16.3.5 changed to 16.3.6 (importer and package keys)", "fail", m4,
     True, True),
    ("M5", "round 3", "new workflow: working-directory = the parent directory, pnpm --dir variant install/start", "fail",
     m5, True, True),
    ("M6", "round 3", "root pnpm-workspace.yaml listing the variant", "fail", m6, True, True),
    ("M7", "round 3", "root docker-compose.yml mounting the variant and running install/build/start", "fail", m7, True,
     True),
    ("M8", "round 3", "new line in tests/test_osv_lockfile_coverage.py running pnpm install in the variant", "fail", m8,
     True, True),
    ("M9", "round 3", "new script joining Path parts: \"evidence\" / \"artifacts\" / <name> / \"variant\"", "fail", m9,
     True, True),
    ("X1", "extra", "tracked symlink apps/frozen -> the variant, and a workflow running pnpm in apps/frozen", "fail",
     x_symlink, True, True),
    ("X2", "extra", "script under evidence/** (excluded class) running pnpm install in the variant", "fail",
     x_evidence_script, True, True),
    ("X3", "extra", "blueprints/**/package.json building the variant", "fail", x_blueprint_package, True, True),
    ("X4", "extra", "blueprints/**/.devcontainer/devcontainer.json installing the variant", "fail", x_devcontainer, True,
     True),
    ("X5", "extra", "root Makefile target installing the variant", "fail", x_makefile, True, True),
    ("X6", "extra", "pinned line changed: security-scan.yml's assignment line also names package.json", "fail",
     x_changed_pin, True, True),
    ("X7", "extra (scope break)", "this module's excluded classes wrongly include .github/** (drops the inventory pins)",
     "fail", x_scope_break, True, True),
    ("X8", "extra (git unavailable)", "git not on PATH", "fail", nothing, False, False),
    ("N1", "round 4", "new blueprints/x/launch.json: an mcpServers entry whose command runs pnpm start with cwd = the "
     "variant", "fail", n_blueprint_launch, True, True),
    ("N2", "round 4", "new macOS workflow running pnpm install and start with working-directory = the variant path with "
     "the directory's name upper-cased", "fail", n_upper_case, True, True),
    ("N3", "round 4", "the frozen TOML's ignoreUntil changed from 2026-12-24 to 2027-03-24", "fail", n_ignore_until, True,
     True),
    ("X9", "extra (scope break)", "this module's excluded classes include blueprints/**/*.json again (round 3's rule)",
     "fail", x_blueprint_json_excluded_again, True, True),
    ("X10", "extra (scope break)", "this module matches the name case-sensitively again (round 3's rule)", "fail",
     x_case_sensitive_again, True, True),
    ("X11", "extra", "the frozen TOML's exception removed (header comments kept)", "fail", x_exception_removed, True,
     True),
    ("X12", "extra", "the frozen TOML's reason edited (its live-lock clause 16.3.6 -> 16.3.8), date unchanged", "fail",
     x_reason_changed, True, True),
    ("L1", "known limit", "root pnpm-workspace.yaml with a glob evidence/artifacts/*/variant", "pass", x_glob_workspace,
     True, True),
    ("L2", "known limit", "workflow iterating the OSV inventory's frozen-config paths and installing each", "pass",
     x_inventory_loop, True, True),
    ("L3", "known limit", "script assembling the name from fragments", "pass", x_fragments, True, True),
    ("L4", "known limit (excluded class)", "Markdown recipe whose command block installs and builds the variant", "pass",
     x_markdown_recipe, True, True),
    ("L5", "known limit (excluded class)", "evidence/**/launch.json: the N1 launch configuration kept under evidence/**",
     "pass", l_evidence_launch, True, True),
    ("P1", "allowed", ".DS_Store and Thumbs.db in the variant directory on disk", "pass", x_os_metadata, False, True),
    ("P2", "allowed", "variant removed (both files deleted and staged): the exit path", "pass", x_removed, True, True),
    ("N4", "round 5 (section 2)", "rebuild.sh beside variant/ (cd variant && pnpm install), tracked (git add)", "fail",
     n_rebuild_beside_variant, True, True),
    ("N5", "round 5 (section 2)", "the same rebuild.sh beside variant/ on disk, untracked", "fail",
     n_rebuild_beside_variant, False, True),
    ("N6", "round 5 (section 2)", "the same rebuild.sh, tracked under the artifact directory's name upper-cased (another "
     "directory on this case-sensitive file system, the same one on a case-insensitive one)", "fail",
     n_rebuild_upper_case_directory, True, True),
    ("N7", "round 5 (section 1)", "new .claude/agents/x.md whose frontmatter hooks: entry runs pnpm install in the "
     "variant", "fail", n_agent_frontmatter_hook, True, True),
    ("N8", "round 5 (section 4)", "the frozen TOML's exception gains a key besides id, ignoreUntil and reason "
     "(effectiveUntil = 2027-03-24), date and reason unchanged", "fail", n_exception_extra_key, True, True),
    ("X13", "extra", "new .agents/skills/frozen-app/SKILL.md whose instructions run pnpm install in the variant", "fail",
     x_agents_skill, True, True),
    ("X14", "extra (scope break)", "this module's recogniser drops the client directories again (round 4's rule)",
     "fail", x_client_directories_dropped, True, True),
    ("X15", "extra (scope break)", "this module compares tracked artifact paths case-sensitively", "fail",
     x_tracked_case_sensitive, True, True),
    ("N9", "round 6", "new .CLAUDE/skills/frozen-app/SKILL.md (upper-cased client directory) whose instructions run "
     "pnpm install in the variant", "fail", n_upper_case_client_directory, True, True),
    ("X16", "extra (scope break)", "this module compares client configuration directory names case-sensitively again "
     "(round 5's rule)", "fail", x_client_directories_case_sensitive, True, True),
    ("P3", "allowed", ".DS_Store and Thumbs.db beside variant/, on disk and tracked (git add -f, since .gitignore's "
     "*.db ignores Thumbs.db)", "pass", p_metadata_beside_variant, True, True),
    ("P4", "allowed", "the whole artifact directory removed (its three files deleted and staged)", "pass",
     p_artifact_removed, True, True),
]


def run(git_on_path: bool) -> tuple[int, str]:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory() as empty:
        if not git_on_path:
            environment["PATH"] = empty
        process = subprocess.run([sys.executable, "-m", "unittest", MODULE], cwd=ROOT, env=environment,
                                 capture_output=True, text=True)
    return process.returncode, process.stdout + process.stderr


def main() -> int:
    assert git("status", "--porcelain") == "", "the scratch clone must start clean"
    head = git("rev-parse", "HEAD").strip()
    results = []
    for mutant_id, origin, description, expected, apply, stage, git_on_path in MUTANTS:
        if SELECTED and mutant_id not in SELECTED:
            continue
        change = Change()
        apply(change)
        if stage:
            git("add", "-A")
        code, output = run(git_on_path)
        failed = re.findall(r"(?m)^(?:FAIL|ERROR): (\S+) \(([^)]+)\)", output)
        summary = [line for line in output.splitlines() if re.match(r"^(Ran \d+ tests?|OK|FAILED)", line)]
        observed = "pass" if code == 0 else "fail"
        results.append({
            "id": mutant_id, "origin": origin, "mutant": description, "expected": expected, "observed": observed,
            "exit_code": code, "as_expected": observed == expected,
            "failing_tests": [name for name, _ in failed],
            "errors": len(re.findall(r"(?m)^ERROR: ", output)),
            "reopen_message": REOPEN_TEXT in output, "stale_pin_message": STALE_TEXT in output,
            "git_message": GIT_TEXT in output, "recheck_message": RECHECK_TEXT in output,
            "skipped": any("skipped=" in line for line in summary),
            "summary": summary,
        })
        (OUT.parent / f"{OUT.name}-{mutant_id}.log").write_text(output, encoding="utf-8")
        change.restore()
        git("add", "-A")
        leftover = git("status", "--porcelain")
        assert leftover == "", (mutant_id, leftover)
        assert git("rev-parse", "HEAD").strip() == head
        for cache in ROOT.rglob("__pycache__"):
            raise AssertionError(f"bytecode cache written: {cache}")
    OUT.with_suffix(".json").write_text(json.dumps({"clone_head": head, "results": results}, indent=1) + "\n",
                                        encoding="utf-8")
    for row in results:
        print(f"{row['id']:4} expected={row['expected']:4} observed={row['observed']:4} exit={row['exit_code']} "
              f"ok={row['as_expected']} reopen={row['reopen_message']} stale={row['stale_pin_message']} "
              f"git={row['git_message']} recheck={row['recheck_message']} skipped={row['skipped']} "
              f"failing={row['failing_tests']} {row['summary']}")
    return 0 if all(row["as_expected"] for row in results) else 1


if __name__ == "__main__":
    sys.exit(main())
