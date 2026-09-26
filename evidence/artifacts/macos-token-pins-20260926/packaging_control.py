"""Control for the packaging requirement: both digest harnesses under a Python that cannot import `packaging`.

Usage, from the repository root, with such a Python:
  <python without packaging> evidence/artifacts/macos-token-pins-20260926/packaging_control.py <empty scratch directory>

Runs, with this interpreter, against adoption/pins-macos-arm64.json and adoption/pins-linux-x86_64.json:
  before  verify_pins.py, the harness of runs 3 and 4 and the negative control, which reads the network as usual;
  after   verify_pins_fail_closed.py.
It refuses (exit 2) an interpreter that can import packaging. It exits 0 only when the control holds both
ways: before prints its "packaging not importable" note, has no requires_python check line and still
reports PASS with exit 0 (the defect the GPT-6 verification found), and after exits 2 with its message on
stderr, prints nothing on stdout and leaves its fetch directory empty. Exit 1 otherwise. Paths are printed
relative to the repository, and the scratch directory as <scratch>.

local_integration: a harness written for this change. The network is used read-only by the before run,
nothing is installed, and no Mac runs anything.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = ("adoption/pins-macos-arm64.json", "adoption/pins-linux-x86_64.json")
NOTE = "  (packaging not importable; requires_python not evaluated)"
CHECK_LINE = "headroom: requires_python admits 3.13"
REFUSAL = "verify_pins_fail_closed.py needs the packaging module"


def main() -> int:
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir() or any(Path(sys.argv[1]).iterdir()):
        print("usage: packaging_control.py <empty scratch directory>", file=sys.stderr)
        return 2
    repo = Path.cwd().resolve()
    if not all((repo / path).is_file() for path in PINS):
        print("run from the repository root", file=sys.stderr)
        return 2
    scratch = Path(sys.argv[1]).resolve()
    print(f"# verify_pins.py and verify_pins_fail_closed.py without the packaging module, "
          f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"# Python {platform.python_version()}; importlib.util.find_spec('packaging') -> "
          f"{importlib.util.find_spec('packaging')}")
    if importlib.util.find_spec("packaging") is not None:
        print("REFUSED: this interpreter can import packaging, so the control would show nothing")
        return 2
    held = []
    for label, harness in (("before", "verify_pins.py"), ("after", "verify_pins_fail_closed.py")):
        fetch = scratch / label
        fetch.mkdir()
        relative = (HERE / harness).relative_to(repo).as_posix()
        result = subprocess.run([sys.executable, relative, *PINS, str(fetch)], capture_output=True, text=True,
                                timeout=1800, check=False, stdin=subprocess.DEVNULL, cwd=repo)
        stdout = result.stdout.replace(str(scratch), "<scratch>")
        stderr = result.stderr.replace(str(scratch), "<scratch>").replace(str(repo), "<checkout>")
        print(f"\n=== {label}: python3 {relative} {' '.join(PINS)} <scratch>/{label}: stdout (exit {result.returncode}) ===")
        print(stdout, end="")
        print(f"=== {label}: stderr ===")
        print(stderr, end="")
        written = sorted(path.relative_to(fetch).as_posix() for path in fetch.rglob("*"))
        print(f"=== {label}: <scratch>/{label} holds {len(written)} entries afterwards ===")
        lines = result.stdout.splitlines()
        if label == "before":
            ok = (result.returncode == 0 and NOTE in lines and not any(CHECK_LINE in line for line in lines)
                  and bool(lines) and lines[-1] == "# result: PASS (0 mismatches)")
            print(f"[check: before skips the requires_python check and still reports PASS with exit 0: "
                  f"{'held' if ok else 'did not hold'}]")
        else:
            ok = result.returncode == 2 and result.stdout == "" and REFUSAL in result.stderr and written == []
            print(f"[check: after exits 2 on stderr before any output or download: {'held' if ok else 'did not hold'}]")
        held.append(ok)
    print("\n# result: " + ("PASS: the control held both ways" if all(held) else "FAIL"))
    return 0 if all(held) else 1


if __name__ == "__main__":
    sys.exit(main())
