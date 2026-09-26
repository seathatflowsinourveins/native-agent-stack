"""Reproduce delta.json scanner_comparison: rebuild its fixtures and run both pinned scanners under an open() trace.

usage: python3 scanner_compare.py DELTA_JSON SKILL_SCANNER_DIR SKILL_SECURITY_DIR WORK_DIR OUT_JSON

  SKILL_SCANNER_DIR   skills/skill-scanner of a getsentry/skills checkout at c2f99a5b04b4cd992ec3022d7c2c3e23e938d241
  SKILL_SECURITY_DIR  skills/skill-security of a superagent-ai/skills checkout at 0da315b873ed141025fa601ed6e0ebe0c878d5af
  WORK_DIR            a scratch directory outside any checkout; fixtures go to WORK_DIR/fx/<name>, the canary
                      file to WORK_DIR/outside (both are recreated)

skill-scanner runs as `uv run --no-project --with pyyaml` (its PEP 723 block needs PyYAML); skill-security
runs on python3 with `-f json`. Each scanner process carries a sys.addaudithook that logs every opened path,
so the output says whether the scanner read a file resolving outside the fixture. A marker that exists only
in the outside canary file shows whether that file's text reached the scanner's stdout. The output keeps
counts, rule titles, skill-security's own score, band and default verdict, and booleans; no host path.
"""
import json
import os
import runpy
import shutil
import subprocess
import sys

MARKER = "CANARY-OUTSIDE-7F3A"


def trace(log_path: str, script: str, args: list) -> None:
    """Run SCRIPT as __main__ while logging the resolved path of every file it opens."""
    log = open(log_path, "w", encoding="utf-8")

    def hook(event, hook_args):
        if event == "open" and hook_args and isinstance(hook_args[0], (str, bytes, os.PathLike)):
            log.write(os.path.realpath(os.fsdecode(hook_args[0])) + "\n")
            log.flush()

    sys.addaudithook(hook)
    sys.argv = [script] + args
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    runpy.run_path(script, run_name="__main__")


def build(comparison: dict, work: str) -> list:
    fx, outside = os.path.join(work, "fx"), os.path.join(work, "outside")
    for path in (fx, outside):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(outside)
    for rel, text in comparison["outside_files"].items():
        with open(os.path.join(outside, rel), "w", encoding="utf-8") as handle:
            handle.write(text)
    for name, files in comparison["fixtures"].items():
        for rel, text in files.items():
            path = os.path.join(fx, name, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
    for rel, target in comparison["symlinks"].items():
        link = os.path.join(fx, rel)
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(target, link)
        assert os.path.realpath(link).startswith(outside + os.sep), rel
    return sorted(comparison["fixtures"])


def opened_outside(log_path: str, outside: str) -> bool:
    with open(log_path, encoding="utf-8") as handle:
        return any(line.startswith(outside + os.sep) for line in handle)


def summarize_skill_scanner(stdout: str, rc: int) -> dict:
    try:
        data = json.loads(stdout)
    except ValueError:
        return {"error": "no JSON on stdout", "rc": rc}
    findings = data.get("findings", [])
    counts = {k.lower(): v for k, v in (data.get("finding_counts") or {}).items() if v}
    return {
        "counts": counts,
        "at_least_one_high_or_critical": bool(counts.get("critical") or counts.get("high")),
        "highest_finding_severity": next((s for s in ("critical", "high", "medium", "low") if counts.get(s)), None),
        "titles": sorted({f"{f.get('severity')}:{f.get('category')}:"
                          f"{f.get('description', '').split(' (resolves to')[0][:60]}" for f in findings}),
        "symlink_reported": any(f.get("type") == "Symlink Detected" for f in findings),
        "rc": rc,
    }


def summarize_skill_security(stdout: str, rc: int) -> dict:
    try:
        data = json.loads(stdout)
    except ValueError:
        return {"error": "no JSON on stdout", "rc": rc}
    findings = data.get("findings", [])
    counts = {k.lower(): v for k, v in ((data.get("summary") or {}).get("by_severity") or {}).items() if v}
    risk = data.get("risk") or {}
    return {
        "counts": counts,
        "at_least_one_high_or_critical": bool(counts.get("critical") or counts.get("high")),
        "risk_score": risk.get("score"),
        "risk_band": risk.get("severity"),
        "default_verdict": risk.get("recommendation"),
        "titles": sorted({f"{f.get('severity')}:{f.get('rule_id')}:{f.get('title', '')[:60]}" for f in findings}),
        "symlink_reported": any("symlink" in f"{f.get('rule_id', '')} {f.get('title', '')}".lower() for f in findings),
        "rc": rc,
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--trace":
        trace(sys.argv[2], sys.argv[3], sys.argv[4:])
        return
    delta, scanner_dir, security_dir, work, out = sys.argv[1:6]
    work = os.path.realpath(work)
    outside = os.path.join(work, "outside")
    comparison = json.load(open(delta, encoding="utf-8"))["scanner_comparison"]
    me = os.path.abspath(__file__)
    scanner = os.path.join(os.path.realpath(scanner_dir), "scripts", "scan_skill.py")
    security = os.path.join(os.path.realpath(security_dir), "scripts", "scan.py")
    rows = []
    for name in build(comparison, work):
        target = os.path.join(work, "fx", name)
        log_a, log_b = os.path.join(work, f"open-a-{name}.log"), os.path.join(work, f"open-b-{name}.log")
        run = dict(capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL, cwd=work)
        proc_a = subprocess.run(["uv", "run", "--no-project", "--quiet", "--with", "pyyaml", "python", me,
                                 "--trace", log_a, scanner, target], **run)
        proc_b = subprocess.run([sys.executable, me, "--trace", log_b, security, target, "-f", "json"], **run)
        a = summarize_skill_scanner(proc_a.stdout, proc_a.returncode)
        b = summarize_skill_security(proc_b.stdout, proc_b.returncode)
        for result, proc, log in ((a, proc_a, log_a), (b, proc_b, log_b)):
            result["opened_a_file_outside_the_fixture"] = opened_outside(log, outside)
            result["canary_marker_in_stdout"] = MARKER in proc.stdout
        rows.append({"name": name, "expected_malicious": name.startswith("m"),
                     "getsentry_skill_scanner": a, "superagent_skill_security": b})
    text = json.dumps(rows, indent=1)
    assert work not in text, "a host path reached the output"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


if __name__ == "__main__":
    main()
