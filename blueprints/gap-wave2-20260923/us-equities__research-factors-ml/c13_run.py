#!/usr/bin/env python3
"""Build c13 prompts, run codex exec sequentially, and score the seeded-defect findings."""
import json, subprocess, sys, hashlib, time, re, os
from pathlib import Path
HERE = Path(__file__).resolve().parent / "c13_fixture"
spec = json.loads((HERE / "defects.json").read_text())
fixture = (HERE / "momentum_backtest.py").read_text().splitlines()
numbered = "\n".join("%3d  %s" % (i + 1, l) for i, l in enumerate(fixture))
task = spec["prompt_control"].replace("CATEGORIES", json.dumps(spec["categories_offered"])) + "\n\nmomentum_backtest.py:\n" + numbered + "\n"

def skill_text(cts):
    base = Path(cts) / "skills/backtest-expert"
    parts = ["=== SKILL.md ===\n" + (base / "SKILL.md").read_text()]
    for ref in sorted((base / "references").glob("*.md")):
        parts.append("=== references/" + ref.name + " ===\n" + ref.read_text())
    return "\n\n".join(parts)

def score(findings):
    detected = {}
    matched = set()
    for d in spec["seeded"]:
        hits = [i for i, f in enumerate(findings) if f.get("category") in d["categories"] and any(lo <= int(f.get("line", -1)) <= hi for lo, hi in d["line_ranges"])]
        detected[d["id"]] = bool(hits)
        matched.update(hits)
    return {"detected": detected, "detected_count": sum(detected.values()), "findings": len(findings), "out_of_range": len(findings) - len(matched)}

def main():
    cts, work, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=True)
    prompts = {"control": task, "skill": spec["prompt_skill_prefix"] + skill_text(cts) + "\n\n=== TASK ===\n" + task}
    for k, v in prompts.items():
        (out / ("prompt-" + k + ".txt")).write_text(v)
    results = []
    for run in ["control-1", "skill-1", "control-2", "skill-2"]:
        while int(subprocess.run("pgrep -f '^codex exec' | wc -l", shell=True, capture_output=True, text=True).stdout.strip() or 0) >= 2:
            time.sleep(20)
        arm = run.split("-")[0]
        last = out / (run + ".last.txt")
        t0 = time.time()
        p = subprocess.run(["timeout", "900", "codex", "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check", "-C", str(work), "-o", str(last), "-"],
                           input=prompts[arm], capture_output=True, text=True)
        (out / (run + ".stderr.txt")).write_text(p.stderr)
        (out / (run + ".stdout.txt")).write_text(p.stdout)
        text = last.read_text() if last.exists() else ""
        m = re.search(r"\[.*\]", text, re.S)
        try:
            findings = json.loads(m.group(0)) if m else []
            parse = "ok" if m else "no_json"
        except json.JSONDecodeError:
            findings, parse = [], "invalid_json"
        model = re.search(r"^model:\s*(.+)$", p.stderr + p.stdout, re.M)
        results.append({"run": run, "arm": arm, "exit": p.returncode, "duration_s": round(time.time() - t0, 1), "parse": parse,
                        "model": model.group(1).strip() if model else None, "last_message_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        **score(findings)})
        print(json.dumps(results[-1]), flush=True)
    (out / "scores.json").write_text(json.dumps({"spec_sha256": hashlib.sha256((HERE / "defects.json").read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256((HERE / "momentum_backtest.py").read_bytes()).hexdigest(), "runs": results}, indent=1) + "\n")

if __name__ == "__main__":
    main()
