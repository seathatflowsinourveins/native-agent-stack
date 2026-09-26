#!/usr/bin/env python3
"""Rerun this directory's three checks and retain how each ran.

The first runs (2026-09-26, 02:27Z to 02:34Z) kept their output but not all of their provenance. This driver
reruns each check once, unchanged, and prints what the first runs did not keep:

- `binding`: runs `binding_check.py` (this directory's copy, byte for byte) with this interpreter;
- `template`: runs `template_readback.py` the same way, after hashing the template, the host values and the
  renderer it reads from the checkout;
- `upstream`: copies the context-mode plugin clone into the work directory, prints the copy's
  `git rev-parse HEAD` and `git status --porcelain`, restores the tracked files that status lists from `HEAD`,
  prints the status again, and runs upstream's own `npm test` for the three resolver test files there. Its
  environment is only PATH (node's directory, /usr/bin, /bin), HOME and TMPDIR in the work directory, LANG,
  TZ=UTC, NO_COLOR and npm's update check turned off, so no client or CI variable of the caller reaches the
  tests.

Each prints its command, the environment (`upstream`), the interpreter or the node and npm versions, the UTC
start and end, the exit status and the sha256 of every script it ran. The check's stdout goes to --out byte
for byte (`binding`, `template`: each script already prints placeholders instead of paths) or, for
`upstream`, stdout and stderr as one stream with the work directory as `<work>`, the scratch home in it as
`<work-home>` and the home directory as `~`. The driver refuses to write output that still holds a UUID or a
home path. It writes only under --work, which must be empty, and --out.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
TEST_FILES = ("tests/util/codex-session-cwd-resolution.test.ts", "tests/util/project-dir.test.ts",
              "tests/integration/project-dir-strict.test.ts")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOME = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+")


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Output:
    """Printed lines with the given paths replaced, longest first; nothing is printed before the check ends."""

    def __init__(self, replacements: list[tuple[str, str]]):
        self.replacements = sorted(replacements, key=lambda pair: len(pair[0]), reverse=True)
        self.lines: list[str] = []

    def clean(self, text: str) -> str:
        for real, placeholder in self.replacements:
            text = text.replace(real, placeholder)
        return text

    def add(self, text: str) -> None:
        self.lines.append(self.clean(text))

    @staticmethod
    def refuse_unsanitized(text: str, what: str) -> None:
        if UUID.search(text) or HOME.search(text):
            raise SystemExit(f"unsanitized {what}: a UUID or a home path is left; nothing was written")

    def emit(self) -> None:
        text = "\n".join(self.lines) + "\n"
        self.refuse_unsanitized(text, "provenance")
        sys.stdout.write(text)


def run_script(output: Output, script: str, arguments: list[str], out: Path) -> int:
    """Run one of this directory's scripts with this interpreter; its stdout goes to ``out`` unchanged."""
    argv = [sys.executable, str(HERE / script), *arguments]
    output.add(f"command: python {script} {' '.join(arguments)}")
    output.add(f"interpreter: Python {sys.version.split()[0]}; {script} sha256 {sha256(HERE / script)}")
    start = utc()
    completed = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, check=False)
    end = utc()
    Output.refuse_unsanitized(completed.stdout.decode("utf-8", "replace"), "stdout")
    out.write_bytes(completed.stdout)
    output.add(f"UTC: {start} to {end}; exit status: {completed.returncode}; stderr: {len(completed.stderr)} bytes")
    output.add(f"stdout: {out.name}, sha256 {hashlib.sha256(completed.stdout).hexdigest()}, "
               f"{len(completed.stdout)} bytes")
    return completed.returncode


def git(repository: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repository), *args], capture_output=True, text=True, check=True).stdout


def upstream(output: Output, args: argparse.Namespace, work: Path) -> int:
    clone, home = work / "clone", work / "home"
    home.mkdir()
    shutil.copytree(args.plugin_src, clone, symlinks=True)
    output.add(f"copied the plugin clone {args.plugin_src} to <work>/clone")
    output.add(f"copy of the plugin clone: git rev-parse HEAD: {git(clone, 'rev-parse', 'HEAD').strip()}")
    changed = git(clone, "status", "--porcelain").splitlines()
    output.add(f"git status --porcelain before the restore: {changed}")
    tracked = [line[3:] for line in changed if line[:2] in (" M", "M ", "MM", " D")]
    if tracked:
        subprocess.run(["git", "-C", str(clone), "checkout", "HEAD", "--", *tracked], check=True,
                       capture_output=True)
    output.add(f"restored from HEAD: {tracked}")
    output.add(f"git status --porcelain before the run: {git(clone, 'status', '--porcelain').splitlines()}")
    node_dir = args.node.resolve().parent
    (work / "tmp").mkdir()
    env = {"PATH": f"{node_dir}{os.pathsep}/usr/bin{os.pathsep}/bin", "HOME": str(home), "TMPDIR": str(work / "tmp"),
           "LANG": "C.UTF-8", "TZ": "UTC", "NO_COLOR": "1", "npm_config_update_notifier": "false"}
    versions = {tool: subprocess.run([str(node_dir / tool), "--version"], capture_output=True, text=True,
                                     env=env).stdout.strip() for tool in ("node", "npm")}
    output.add(f"node {versions['node']}, npm {versions['npm']}")
    argv = ["npm", "test", "--", *TEST_FILES, "--reporter=verbose"]
    output.add(f"command (working directory: <work>/clone): {' '.join(argv)}")
    output.add("environment (nothing else): " + ", ".join(f"{key}={value}" for key, value in env.items()))
    start = utc()
    completed = subprocess.run(argv, cwd=clone, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, check=False)
    end = utc()
    output.add(f"UTC: {start} to {end}; exit status: {completed.returncode}")
    output.add(f"git status --porcelain after the run: {git(clone, 'status', '--porcelain').splitlines()}")
    text = output.clean(completed.stdout.rstrip() + "\n")
    Output.refuse_unsanitized(text, "npm output")
    args.out.write_text(text)
    output.add(f"npm stdout and stderr: {args.out.name}, sha256 {sha256(args.out)}")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("check", choices=("binding", "template", "upstream"))
    parser.add_argument("--work", type=Path, required=True, help="an empty scratch directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plugin-src", type=Path, help="binding, upstream: the Codex plugin clone of context-mode")
    parser.add_argument("--npm-src", type=Path, help="binding: the pinned npm install's package directory")
    parser.add_argument("--node", type=Path, help="binding, upstream: the node executable")
    parser.add_argument("--checkout", type=Path, help="template: this repository")
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_dir() or any(work.iterdir()):
        raise SystemExit("--work must be an empty directory")
    output = Output([(str(work), "<work>"), (str(work / "home"), "<work-home>"), (sys.executable, "<python>"),
                     (str(Path.home()), "~"),
                     *([(str(args.node.resolve().parent), "<node-dir>")] if args.node else []),
                     *([(str(args.checkout.resolve()), "<this repository>")] if args.checkout else [])])
    output.add(f"# {args.check} rerun with retained provenance (2026-09-26)")
    output.add(f"provenance_rerun.py sha256 {sha256(Path(__file__))}")
    if args.check == "binding":
        status = run_script(output, "binding_check.py",
                            ["--plugin-src", str(args.plugin_src), "--npm-src", str(args.npm_src), "--node",
                             str(args.node), "--work", str(work)], args.out)
    elif args.check == "template":
        checkout = args.checkout.resolve()
        for relative in ("adoption/templates/codex.config.template.toml", "adoption/hosts/example.json",
                         "tools/adoption/render_config.py"):
            output.add(f"{relative} sha256 {sha256(checkout / relative)}")
        status = run_script(output, "template_readback.py",
                            ["--checkout", str(checkout), "--plugin", str(args.plugin_src), "--work", str(work)],
                            args.out)
    else:
        status = upstream(output, args, work)
    output.emit()
    return status


if __name__ == "__main__":
    sys.exit(main())
