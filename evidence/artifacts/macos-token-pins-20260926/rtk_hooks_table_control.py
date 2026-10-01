"""Control for the rtk exclusion instruction: a second [hooks] table against the value set inside the one table.

Usage, from the repository root:
  python3 evidence/artifacts/macos-token-pins-20260926/rtk_hooks_table_control.py \
      --rtk <rtk 0.50.0 linux-x86_64 binary> <empty scratch directory>

The GPT-6 verification of this change found that adoption/platforms/macos-arm64.md told a reader to
replace an existing `exclude_commands` line with recipes/README.md's block, whose first line is the
`[hooks]` header. The page, the recipe, adoption/bootstrap.md and the macOS rtk pin's install_note
now say: inside the existing `[hooks]` table, replace the key's whole value (or add the key when the
table lacks it), and add the header only when the file has no `[hooks]` table. This harness applies
both instructions, as text edits, to four starting files and lets rtk read each result:
  old  the key, every line of it, replaced by the recipe's whole block, header included; with no
       key to replace (the last two files), the block added at the end;
  new  the key's whole value replaced inside the existing [hooks] table, the key added under an
       existing header that lacks it, and the block with its header added only when there is no
       [hooks] table.
The old instruction is not applied to the file without a [hooks] table: there it adds the same block
as the new one. Each result is written to the config file rtk reads with HOME set to a scratch
directory, then `rtk config` (the file it read, then the effective config or the error) and
`rtk hook check "git show HEAD:x | tail -n 5"` run against it.

It fails closed. It refuses (exit 2) a binary whose sha256 differs from the "extracted rtk sha256"
line of rtk-config-path.txt (the binary from the release archive pinned in
adoption/pins-linux-x86_64.json, verified there) or that does not report `rtk 0.50.0`. It exits 0
only when every old result makes `rtk config` exit 1 with "duplicate key `hooks` in document root"
while the hook rewrites the probe, every new result makes `rtk config` exit 0 with the four entries
and the starting file's other settings while the hook leaves the probe alone ("No rewrite for",
exit 1), and rtk wrote no file but the config; exit 1 otherwise. Every check prints a [check: ...]
line.

local_integration: a harness written for this change, not an upstream test. No network, nothing
installed, and no Mac ran it: on macOS only the file's location differs (rtk-config-path.txt). The
scratch directory is printed as <scratch>.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = "git show HEAD:x | tail -n 5"
BLOCK = re.compile(r"```toml\n(\[hooks\]\nexclude_commands = \[.*?\n\])\n```", re.S)
DUPLICATE = "duplicate key `hooks` in document root"
STARTS = {
    "the 2026-09-25 two-entry key": '[hooks]\nexclude_commands = ["^git show [^ ]*:", "diff"]\n',
    "a multi-line key beside another [hooks] key, after a [tracking] table": (
        '[tracking]\nenabled = true\nhistory_days = 30\n\n'
        '[hooks]\nexclude_commands = [\n  "^git show [^ ]*:",\n  "diff",\n]\nsuppress_hook_warning = true\n'),
    "a [hooks] table without the key": "[hooks]\nsuppress_hook_warning = true\n",
    "no [hooks] table": "[tracking]\nenabled = true\nhistory_days = 30\n",
}
# Settings of each starting file that the new result must keep, as `rtk config` prints them.
KEPT = {
    "a multi-line key beside another [hooks] key, after a [tracking] table": (
        "history_days = 30", "suppress_hook_warning = true"),
    "a [hooks] table without the key": ("suppress_hook_warning = true",),
    "no [hooks] table": ("history_days = 30",),
}

checks = 0
failures = 0


def check(description: str, ok: bool) -> None:
    global checks, failures
    checks += 1
    failures += 0 if ok else 1
    print(f"[check: {description}: {'ok' if ok else 'FAILED'}]")


def key_span(lines: list[str]):
    """First and last line index of the exclude_commands key, or None. Covers the two shapes the
    starting files use: a one-line value, and a value whose closing ] stands alone on a later line."""
    for first, line in enumerate(lines):
        if re.match(r"\s*exclude_commands\s*=", line):
            if line.rstrip().endswith("]"):
                return first, first
            last = next(index for index in range(first + 1, len(lines)) if lines[index].strip() == "]")
            return first, last
    return None


def append(text: str, block: str) -> str:
    return text + ("\n" if text else "") + block


def old_instruction(text: str, block: str) -> str:
    lines = text.splitlines(keepends=True)
    span = key_span(lines)
    if span is None:
        return append(text, block)
    first, last = span
    return "".join(lines[:first]) + block + "".join(lines[last + 1:])


def new_instruction(text: str, block: str) -> str:
    key = block.split("\n", 1)[1]  # the block without its [hooks] header line
    lines = text.splitlines(keepends=True)
    span = key_span(lines)  # in these starting files a key sits in the [hooks] table
    if span is not None:
        first, last = span
        return "".join(lines[:first]) + key + "".join(lines[last + 1:])
    header = next((index for index, line in enumerate(lines) if line.strip() == "[hooks]"), None)
    if header is not None:
        return "".join(lines[:header + 1]) + key + "".join(lines[header + 1:])
    return append(text, block)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rtk", required=True, type=Path)
    parser.add_argument("scratch", type=Path)
    args = parser.parse_args()
    repo = Path.cwd()
    if not (repo / "recipes/README.md").is_file() or not args.scratch.is_dir() or any(args.scratch.iterdir()):
        print("run from the repository root with an empty scratch directory", file=sys.stderr)
        return 2
    scratch = args.scratch.resolve()

    def clean(text: str) -> str:
        return text.replace(str(scratch), "<scratch>")

    retained = (HERE / "rtk-config-path.txt").read_text(encoding="utf-8")
    expected_sha = re.search(r"^extracted rtk sha256 ([0-9a-f]{64})$", retained, re.M).group(1)
    binary = scratch / "bin/rtk"
    binary.parent.mkdir()
    shutil.copyfile(args.rtk, binary)
    binary.chmod(0o755)
    actual_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    home = scratch / "scratch-home"
    home.mkdir()
    environment = {"HOME": str(home), "PATH": "/usr/bin:/bin", "RTK_TELEMETRY_DISABLED": "1"}

    def rtk(*argv: str) -> tuple[int, str]:
        result = subprocess.run([str(binary), *argv], capture_output=True, text=True, timeout=60,
                                env=environment, stdin=subprocess.DEVNULL, check=False)
        return result.returncode, (result.stdout + result.stderr).rstrip("\n")

    status, version = rtk("--version")
    print(f"# rtk exclusion instruction: a second [hooks] table against the value set inside the one table, "
          f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"# Python {platform.python_version()}; scratch directory shown as <scratch>; no network, nothing installed")
    print(f"# rtk binary copied to <scratch>/bin/rtk: sha256 {actual_sha}; `rtk --version`: {version} (exit {status})")
    print(f"# expected sha256 {expected_sha}, the \"extracted rtk sha256\" line of rtk-config-path.txt")
    if actual_sha != expected_sha or (status, version) != (0, "rtk 0.50.0"):
        print("REFUSED: not the pinned rtk 0.50.0 linux-x86_64 binary; nothing was checked")
        return 2
    block = BLOCK.search((repo / "recipes/README.md").read_text(encoding="utf-8")).group(1) + "\n"
    entries = [line.strip().rstrip(",") for line in block.splitlines()[2:-1]]
    print(f"# recipes/README.md block (sha256 {hashlib.sha256(block.encode()).hexdigest()}), {len(entries)} entries:")
    print(block, end="")
    print("# environment of every rtk run: env -i HOME=<scratch>/scratch-home PATH=/usr/bin:/bin RTK_TELEMETRY_DISABLED=1")
    config = home / ".config/rtk/config.toml"
    config.parent.mkdir(parents=True)

    for start, text in STARTS.items():
        for instruction, edit in (("old", old_instruction), ("new", new_instruction)):
            if instruction == "old" and start == "no [hooks] table":
                print(f"\n## {start}: the old instruction adds the same block as the new one here; not repeated")
                continue
            result = edit(text, block)
            config.write_text(result, encoding="utf-8")
            print(f"\n## {start}, {instruction} instruction")
            print("### starting file")
            print(text, end="")
            print(f"### {clean(str(config))} after the {instruction} instruction")
            print(result, end="")
            status, output = rtk("config")
            print(f"$ rtk config\n{clean(output)}\n[exit {status}]")
            loaded = status == 0 and output.split("\n", 1)[0] == f"Config: {config}"
            if instruction == "old":
                check(f"{start}, old: rtk config exits 1 with {DUPLICATE!r}", status == 1 and DUPLICATE in output)
            else:
                check(f"{start}, new: rtk config exits 0 and reads the file", loaded)
                check(f"{start}, new: the effective config holds the four entries",
                      loaded and all(entry in output for entry in entries))
                for setting in KEPT.get(start, ()):
                    check(f"{start}, new: the effective config keeps {setting!r}", loaded and setting in output)
            status, output = rtk("hook", "check", PROBE)
            print(f"$ rtk hook check {PROBE!r}\n{clean(output)}\n[exit {status}]")
            if instruction == "old":
                check(f"{start}, old: the hook rewrites the probe with its defaults",
                      (status, output) == (0, f"rtk {PROBE}"))
            else:
                check(f"{start}, new: the hook leaves the probe alone",
                      (status, output) == (1, f"No rewrite for: {PROBE}"))

    written = sorted(path.relative_to(home).as_posix() for path in home.rglob("*") if path.is_file())
    print(f"\n## files under <scratch>/scratch-home afterwards\n{written}")
    check("rtk wrote no file but the config", written == [".config/rtk/config.toml"])
    print("\n## result")
    if failures:
        print(f"FAIL: {failures} of {checks} checks did not hold")
        return 1
    print(f"PASS: all {checks} checks held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
