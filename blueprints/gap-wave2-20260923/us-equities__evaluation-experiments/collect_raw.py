"""Copy the cited raw outputs from the private cache into the layer evidence directory,
replacing host paths with $HOME and UUID-shaped ids with <uuid-N>. Writes raw/MANIFEST.json
with original and published sha256. Usage: collect_raw.py CACHE_RAW EVIDENCE_DIR"""
import hashlib
import json
import re
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2]) / "raw"
FILES = """
0/contract-test.txt
0/comparison.json
0/control/stdout.txt
0/control/results.json
0/run/timeline.txt
0/run/pf-clean-1/results.json
0/run/pf-clean-1/stdout.txt
0/run/pf-clean-2/results.json
0/run/in-clean-1/logs/*.json
0/run/in-clean-1/stdout.txt
0/run/in-clean-2/logs/*.json
0/run/pf-fault/promptfooconfig.fault.yaml
0/run/pf-fault/stdout.txt
0/run/pf-fault/db-after-first.json
0/run/pf-fault/db-after-retry.json
0/run/pf-fault/results.json
0/run/pf-fault/*/logs/promptfoo-error-*.log
0/run/pf-fault-retry/stdout.txt
0/run/in-fault/logs/*.json
0/run/in-fault-noretry/logs/*.json
0/run/pf-int/stdout-1.txt
0/run/pf-int/stdout-2.txt
0/run/pf-int/db-after-interrupt.json
0/run/pf-int/db-after-resume.json
0/run/pf-int/results-interrupted.json
0/run/in-int/logs/*.json
0/run/in-int/stdout-1.txt
0/run/in-int/stdout-2.txt
1/timeline.txt
1/inspect-help.txt
1/river-snippet.txt
1/mlflow-snippet.txt
1/mlflow-health.txt
1/mlflow-experiments.json
1/mlflow-server.log
1/mteb-run.txt
1/mteb-results/summary.json
1/mteb-results/cache/results/*/*/STSBenchmark.json
1/phoenix-attempt1-server.log
1/phoenix-attempt1-roundtrip.json
1/phoenix-health.txt
1/phoenix-roundtrip.json
1/phoenix-server.log
4/runtime.txt
4/extract.txt
4/validate.json
4/exit-codes.txt
4/upstream-tests.txt
4/result-hashes.txt
4/lexical-summary.json
4/bm25-summary.json
4/lexical-details.jsonl
4/bm25-details.jsonl
4/comparison.json
5/result.json
7/validation-report.json
7/stderr.txt
8/unit-tests.txt
8/attempt1-mlflow-bind.stderr.txt
8/mlflow-bind.stderr.txt
8/readback.json
8/work/evaluate.stdout.txt
8/work/evaluate.stderr.txt
8/work/run-1/results.json
8/work/run-1/freeze.json
8/readback-fix1.json
8/mlflow-bind-fix1.stderr.txt
8/work-fix1/evaluate.stdout.txt
8/work-fix1/run-1/results.json
8/work-fix1/run-1/freeze.json
review-codex-round1.md
""".split()
TMPDIR = re.compile(r"/tmp/tmp[A-Za-z0-9_]{6,}")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
WIN = re.compile(r"(?:[A-Za-z]:[/\\]+|/mnt/[A-Za-z]/)Users[/\\]+(?!example)[A-Za-z0-9_.-]+", re.I)
HOME = re.compile(re.escape(str(Path.home())) + r"\b")
RUNHOME = re.compile(r"((?:pf|in)-[a-z0-9-]+|control)/home\b")  # per-run temp config dirs named home
uuids = {}
def sub_uuid(m):
    return "<uuid-%d>" % uuids.setdefault(m.group(0).lower(), len(uuids) + 1)
manifest = []
for pattern in FILES:
    matches = sorted(src.glob(pattern))
    if not matches:
        raise SystemExit("missing raw output: " + pattern)
    for path in matches:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        counts = {"home": len(HOME.findall(text)), "windows_user": len(WIN.findall(text)), "uuid": len(UUID.findall(text))}
        text = WIN.sub("/mnt/c/Users/example", text)
        text = HOME.sub("$HOME", text)
        text = RUNHOME.sub(r"\1/cfg-home", text)
        counts["tmpdir"] = len(TMPDIR.findall(text))
        text = TMPDIR.sub("/tmp/<tmpdir>", text)
        text = UUID.sub(sub_uuid, text)
        rel = Path(RUNHOME.sub(r"\1/cfg-home", str(path.relative_to(src))))
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        manifest.append({"path": str(rel), "original_sha256": hashlib.sha256(raw).hexdigest(), "original_bytes": len(raw),
                         "published_sha256": hashlib.sha256(text.encode()).hexdigest(), "replacements": counts})
(dst / "MANIFEST.json").write_text(json.dumps({"sanitization": "host home paths -> $HOME; per-run temp config dirs <run>/home -> <run>/cfg-home; Windows user paths -> /mnt/c/Users/example; Python tempfile dirs /tmp/tmpXXXX -> /tmp/<tmpdir>; UUID-shaped ids -> <uuid-N> (consistent mapping within this collection)",
                                               "files": manifest}, indent=1) + "\n")
print(len(manifest), "files")
