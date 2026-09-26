"""Wrong-input controls for this directory's two harnesses: each control holds only when the harness refuses.

Usage, from the repository root:
  python3 evidence/artifacts/macos-token-pins-20260926/fail_closed_controls.py --bash32 <bash 3.2 binary> \
      [--rtk-check <harness>] [--red-green <harness>] <empty scratch directory>

--rtk-check and --red-green default to rtk_config_path_check.sh and reminder_path_red_green.py in
this directory; the -run1 copies are those harnesses before they failed closed. Three controls:
  crate  the rtk check with a `curl` first on PATH that re-compresses each crate it saves from
         static.crates.io with two empty tar blocks appended: the same files under a sha256 that
         is not Cargo.lock's. It holds when both crates reached the harness altered, the harness
         compared each altered sha256 with Cargo.lock's checksum (the unaltered crate's) and
         printed MISMATCH, exited nonzero and extracted neither crate.
  bash5  the red/green harness, from this tree, with --bash32 naming the host's bash, which is
         not 3.2. It holds when the harness exits nonzero and does not report PASS.
  skip   the red/green harness with a real bash 3.2, from a copy of this tree whose test file has
         one added line, @unittest.skip on PortedFunctionsUnderRealBash32Tests. It holds when the
         harness exits nonzero and does not report PASS.
Each control prints the harness's output (stdout, then stderr) and one line per check. Paths are
sanitized: the scratch directory as <work>, the repository as <repo>, the bash 3.2 binary as
<bash-VERSION> and the home directory as ~; the harnesses sanitize their own paths first (the rtk
check shows its scratch directory, <work>/crate, as <scratch>). Exits 0 only when every control
holds, 1 otherwise.

local_integration: a harness written for this change. The crate control uses the network the rtk
check uses (github.com, static.crates.io); nothing is installed and no Mac runs anything.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = "tests/test_adoption_bootstrap_macos.py"
SKIPPED_CLASS = "class PortedFunctionsUnderRealBash32Tests(unittest.TestCase):\n"
SKIP_LINE = '@unittest.skip("fail-closed control: every bash 3.2 test skipped")\n'
CRATES = ("dirs-5.0.1.crate", "dirs-sys-0.4.1.crate")
BASH32_VERSION = re.compile(r"GNU bash, version (3\.2\.\d+)")
CRATE_LINE = re.compile(r"^(\S+\.crate) sha256 ([0-9a-f]{64}); Cargo\.lock checksum ([0-9a-f]{64}): (MATCH|MISMATCH)$",
                        re.M)
# The crate control's curl: runs the real curl, then rewrites each static.crates.io crate it saved as
# the same tar stream plus two empty 512-byte blocks, recompressed, and logs both sha256 values.
CURL_SHIM = """#!/bin/sh
set -eu
{real} "$@"
out= url=
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    *) url="$1"; shift ;;
  esac
done
case "$url" in
  https://static.crates.io/crates/*)
    before=$(sha256sum "$out" | cut -d' ' -f1)
    {{ gzip -dc "$out"; head -c 1024 /dev/zero; }} | gzip -n -9 >"$out.altered"
    mv "$out.altered" "$out"
    printf '%s %s %s\\n' "${{out##*/}}" "$before" "$(sha256sum "$out" | cut -d' ' -f1)" >>{log}
    ;;
esac
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_line(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout.splitlines() or [""])[0]


class Controls:
    def __init__(self, repo: Path, work: Path, bash32: Path):
        self.repo, self.work, self.bash32 = repo, work, bash32
        self.bash32_version = first_line([str(bash32), "--version"])
        match = BASH32_VERSION.match(self.bash32_version)
        self.bash32_label = f"<bash-{match.group(1)}>" if match else "<bash32>"
        self.replacements = [(str(work), "<work>"), (str(repo), "<repo>"), (str(bash32), self.bash32_label),
                             (str(Path.home()), "~")]
        self.failed: list[str] = []

    def clean(self, text: str) -> str:
        for old, new in self.replacements:
            text = text.replace(old, new)
        return re.sub(re.escape(tempfile.gettempdir()) + r"/tmp[A-Za-z0-9_]+", "<tmp>", text)

    def run(self, command: list[str], cwd: Path, env: dict[str, str] | None = None, shown_env: str = ""):
        shown = ["python3" if part == sys.executable else part for part in command]
        print(self.clean(f"$ cd {cwd} && {shown_env}{' '.join(shown)}"))
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=1800)
        if result.stdout:
            print(self.clean(result.stdout).rstrip("\n"))
        if result.stderr:
            print("[stderr]")
            print(self.clean(result.stderr).rstrip("\n"))
        print(f"[exit {result.returncode}]")
        return result

    def check(self, control: str, description: str, held: bool) -> None:
        print(self.clean(f"[check: {description}: {'ok' if held else 'FAILED'}]"))
        if not held and control not in self.failed:
            self.failed.append(control)

    def crate(self, harness: Path) -> None:
        print("\n## crate: the rtk check against altered crates")
        shim, scratch, log = self.work / "crate-shim", self.work / "crate", self.work / "crate-shim.log"
        shim.mkdir()
        scratch.mkdir()
        real = shutil.which("curl")
        if real is None:
            self.check("crate", "a real curl is on PATH", False)
            return
        (shim / "curl").write_text(CURL_SHIM.format(real=shlex.quote(real), log=shlex.quote(str(log))))
        (shim / "curl").chmod(0o755)
        env = dict(os.environ, PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
        result = self.run(["bash", str(harness), str(scratch)], self.repo, env, "PATH=<work>/crate-shim:$PATH ")
        altered = {}
        if log.exists():
            print("the curl shim's log (crate, sha256 as fetched, sha256 as handed on):")
            print(self.clean(log.read_text()).rstrip("\n"))
            altered = {fields[0]: (fields[1], fields[2]) for fields in
                       (line.split() for line in log.read_text().splitlines()) if len(fields) == 3}
        self.check("crate", "the curl shim altered both crates",
                   all(name in altered and altered[name][0] != altered[name][1] for name in CRATES))
        compared = {name: (actual, locked, verdict) for name, actual, locked, verdict in CRATE_LINE.findall(result.stdout)}
        for name in CRATES:
            before, after = altered.get(name, ("", ""))
            self.check("crate", f"the harness compared the altered {name} with Cargo.lock's checksum, the "
                                "unaltered crate's, and printed MISMATCH",
                       name in compared and compared[name] == (after, before, "MISMATCH"))
        self.check("crate", "the harness exited nonzero", result.returncode != 0)
        self.check("crate", "the harness extracted neither crate",
                   not any((scratch / name.removesuffix(".crate")).exists() for name in CRATES))

    def bash5(self, harness: Path) -> None:
        print("\n## bash5: the red/green harness given a bash that is not 3.2")
        host_bash = shutil.which("bash")
        version = first_line([host_bash, "--version"]) if host_bash else ""
        print(f"host bash: {host_bash} ({version})")
        self.check("bash5", "the host bash is not bash 3.2", bool(version) and not BASH32_VERSION.match(version))
        result = self.run([sys.executable, str(harness), "--bash32", str(host_bash)], self.repo)
        self.check("bash5", "the harness exited nonzero", result.returncode != 0)
        self.check("bash5", "the harness did not report PASS", "# result: PASS" not in result.stdout)

    def skip(self, harness: Path) -> None:
        print("\n## skip: the red/green harness with a real bash 3.2, every bash 3.2 test skipped")
        print(f"--bash32: {self.bash32_label} ({self.bash32_version})")
        self.check("skip", "--bash32 is GNU bash 3.2", bool(BASH32_VERSION.match(self.bash32_version)))
        lines = (self.repo / TESTS).read_text(encoding="utf-8").splitlines(keepends=True)
        self.check("skip", f"{TESTS} declares PortedFunctionsUnderRealBash32Tests exactly once",
                   lines.count(SKIPPED_CLASS) == 1)
        if lines.count(SKIPPED_CLASS) != 1:
            return
        tree = self.work / "skip-tree"
        shutil.copytree(self.repo, tree, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        at = lines.index(SKIPPED_CLASS)
        (tree / TESTS).write_text("".join([*lines[:at], SKIP_LINE, *lines[at:]]), encoding="utf-8")
        print(f"<work>/skip-tree is this tree with one line added to {TESTS} (line {at + 1}, above the "
              f"PortedFunctionsUnderRealBash32Tests class): {SKIP_LINE.strip()}")
        result = self.run([sys.executable, str(harness), "--bash32", str(self.bash32)], tree)
        self.check("skip", "the harness exited nonzero", result.returncode != 0)
        self.check("skip", "the harness did not report PASS", "# result: PASS" not in result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bash32", required=True, type=Path, help="a bash 3.2 binary")
    parser.add_argument("--rtk-check", type=Path, default=HERE / "rtk_config_path_check.sh")
    parser.add_argument("--red-green", type=Path, default=HERE / "reminder_path_red_green.py")
    parser.add_argument("scratch", type=Path, help="an empty scratch directory")
    args = parser.parse_args()
    repo = Path.cwd().resolve()
    if not (repo / TESTS).is_file() or not (repo / "recipes/README.md").is_file():
        parser.error("run from the repository root")
    work = args.scratch.resolve()
    if not work.is_dir() or any(work.iterdir()):
        parser.error("the scratch directory must exist and be empty")
    rtk_check, red_green, bash32 = args.rtk_check.resolve(), args.red_green.resolve(), args.bash32.resolve()
    controls = Controls(repo, work, bash32)
    print(f"# fail-closed controls for the rtk check and the red/green harness, "
          f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    print(f"# Python {sys.version.split()[0]}; the scratch directory is shown as <work>")
    for label, path in (("--rtk-check", rtk_check), ("--red-green", red_green)):
        print(controls.clean(f"# {label} {path} sha256 {sha256(path)}"))
    controls.crate(rtk_check)
    controls.bash5(red_green)
    controls.skip(red_green)
    held = [name for name in ("crate", "bash5", "skip") if name not in controls.failed]
    print(f"\n# result: {'PASS' if not controls.failed else 'FAIL'} (controls held: {', '.join(held) or 'none'}; "
          f"did not hold: {', '.join(controls.failed) or 'none'})")
    return 0 if not controls.failed else 1


if __name__ == "__main__":
    sys.exit(main())
