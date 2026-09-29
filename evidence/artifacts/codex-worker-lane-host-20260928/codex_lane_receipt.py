"""Run the Codex worker lane's two non-mutating checks from the repository root and keep a sanitized receipt of each:
`tools/adoption/apply_codex_lane.py` (a dry run: nothing under the Codex home is written) and
`tools/adoption/prove_codex_lane.py` (the static proof, without --live). The raw argument vector, times, exit code,
stdout and stderr stay in PRIVATE; OUT gets the same with #406's sanitization
(evidence/artifacts/codex-worker-lane-host-20260927/README.md, "Retention and sanitization"). With --sanitize-only,
it sanitizes the named text files into OUT instead of running anything.

usage: codex_lane_receipt.py REPO PRIVATE OUT
       codex_lane_receipt.py --sanitize-only OUT FILE...
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = str(Path.home())
RULES = [
    (re.compile(re.escape(HOME)), "~"),
    (re.compile(r"/tmp/[^\s'\"),\]]+"), "<scratch>"),
    (re.compile(r"\d{8}T\d{6}Z-[a-z0-9]+"), "<private-run>"),
    (re.compile(r"sha256:[0-9a-f]{64}"), "sha256:<private-config-version>"),
    (re.compile(r"\b[0-9a-f]{64}\b"), "<private-file-sha256>"),
]


def sanitize(text):
    for rx, new in RULES:
        text = rx.sub(new, text)
    assert Path.home().name not in text, "the host user name is left"
    return text


def utc(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


if sys.argv[1] == "--sanitize-only":
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for f in sys.argv[3:]:
        (out / Path(f).name).write_text(sanitize(Path(f).read_text()))
        print("sanitized", Path(f).name)
    sys.exit(0)

repo, private, out = (Path(a) for a in sys.argv[1:4])
private.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)
rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
summary = []
for name, argv in (("dry-run", ["python3", "tools/adoption/apply_codex_lane.py"]),
                   ("prove", ["python3", "tools/adoption/prove_codex_lane.py"])):
    start = time.time()
    p = subprocess.run(argv, cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    end = time.time()
    record = {"argv": argv, "cwd": "<repository root>", "revision": rev, "start": utc(start), "end": utc(end),
              "exit": p.returncode}
    (private / f"{name}.json").write_text(json.dumps({**record, "cwd": str(repo), "stdout": p.stdout,
                                                      "stderr": p.stderr}, indent=1))
    header = "\n".join(f"# {k}: {v}" for k, v in record.items())
    (out / f"{name}.txt").write_text(sanitize(f"{header}\n# stdout:\n{p.stdout}# stderr:\n{p.stderr}"))
    summary.append({"check": name, **record})
    print(name, "exit", p.returncode, record["start"], record["end"])
(out / "runs.json").write_text(json.dumps(summary, indent=1) + "\n")
