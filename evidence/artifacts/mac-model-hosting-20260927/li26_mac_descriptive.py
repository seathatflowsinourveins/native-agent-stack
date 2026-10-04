#!/usr/bin/env python3
"""Descriptive li26 summary of this Mac's Metal runs (host request #379).

Scores each run's private eval/metrics.json with the frozen blueprint's own functions
(analyze.py: counts, filing_scores, micro_f1, macro_f1, paired_bootstrap with the plan's
resamples, seed and alpha). The Mac is not the preregistered host, so this is description,
never a replacement decision or a parity claim. The output holds no document text, no
per-filing data and no paths.

    python3 -B li26_mac_descriptive.py --runs DIR            # print the summary JSON
    python3 -B li26_mac_descriptive.py --runs DIR --check F  # re-derive and compare with F

metrics.json's "profile" field repeats the plan's declaration for the arm; ARGV below is
what actually ran on this Mac (full Metal offload; C2 without --n-cpu-ffn).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BLUEPRINT = ROOT / "blueprints/convergence-practice/local-inference-latest-20260926"
COMMON = ("--ctx-size 8192 --parallel 1 --gpu-layers 99 --fit off --threads 6 --threads-batch 6 "
          "--batch-size 512 --ubatch-size 128 --cache-ram 0 --no-webui --offline")
RUNS = {  # label -> (run directory name, llama.cpp build, extra flags)
    "C0@b11057": ("c0-metal-20260927", "b11057 (59657a613), the macOS pin", ""),
    "C0@b11146": ("c0-metal-b11146-20260927", "b11146 (7fe450e19), the plan's runtime", ""),
    "C2@b11146": ("c2-metal-b11146-20260927", "b11146 (7fe450e19), the plan's runtime",
                  "--spec-type draft-mtp --spec-draft-n-max 3"),
}
PAIRS = (
    ("C0@b11146", "C2@b11146", "MTP drafting on the same build and flags"),
    ("C0@b11057", "C0@b11146", "runtime build b11057 -> b11146 with the same model and flags"),
)

_spec = importlib.util.spec_from_file_location("li26_analyze", BLUEPRINT / "analyze.py")
analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze)


def meta(run_dir: Path) -> dict:
    out = {}
    for line in (run_dir / "meta.txt").read_text().splitlines():
        head, sep, rest = line.partition(" ")
        if head in ("start", "end") and sep:
            out[head] = rest
        elif "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def memory_kills(run_dir: Path) -> int:
    """memorystatus kill lines in the run window, excluding the `log show` command's own entry."""
    path = run_dir / "jetsam.log"
    if not path.exists():
        return -1
    return sum(1 for line in path.read_text().splitlines()
               if re.search(r"memorystatus_kill|killing", line, re.I) and "log run noninteractively" not in line)


def peak_rss_mib(run_dir: Path):
    peak = None
    path = run_dir / "memory-samples.txt"
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                peak = max(peak or 0, int(parts[1]) // 1024)
    return peak


def summary(metrics: dict, run_dir: Path, label: str) -> dict:
    filings = metrics["filings"]
    n = len(filings)
    triples = [analyze.counts(f["gold"], f["predicted"]) for f in filings]
    scores = [analyze.filing_scores(f["gold"], f["predicted"]) for f in filings]
    macro, per_code = analyze.macro_f1([f["gold"] for f in filings], [f["predicted"] for f in filings])
    speeds = [f["predicted_per_second"] for f in filings if f.get("http_status") == 200
              and (f.get("predicted_n") or 0) >= 1 and isinstance(f.get("predicted_per_second"), (int, float))]
    ttft = [f["prompt_ms"] for f in filings if f.get("http_status") == 200 and isinstance(f.get("prompt_ms"), (int, float))]
    m = meta(run_dir)
    _, build, extra = RUNS[label]
    return {
        "argv": f"llama-server --model Qwen3.8-27B-UD-Q4_K_M.gguf --alias li26-{label[:2].lower()} {COMMON} {extra}".strip(),
        "runtime": build, "build_info": (metrics.get("server") or {}).get("build_info"),
        "n": n, "status": metrics["status"], "events": metrics["events"],
        "micro_f1": round(analyze.micro_f1(triples), 4),
        "macro_f1": round(macro, 4) if macro is not None else None, "macro_codes": len(per_code),
        "exact_match_rate": round(sum(s["exact"] for s in scores) / n, 4) if n else None,
        "json_valid_rate": round(sum(f["parse_status"] == "valid" for f in filings) / n, 4) if n else 0.0,
        "errors": sum(f.get("error") not in (None, "not_attempted") for f in filings),
        "not_attempted": sum(f.get("error") == "not_attempted" for f in filings),
        "median_decode_tokens_per_second": round(statistics.median(speeds), 2) if speeds else None,
        "median_ttft_ms": round(statistics.median(ttft)) if ttft else None,
        "server_peak_rss_mib": peak_rss_mib(run_dir), "memory_kills": memory_kills(run_dir),
        "window_local": [m.get("start"), m.get("end")],
    }


def derive(runs_dir: Path) -> dict:
    raw = (BLUEPRINT / "plan.json").read_bytes()
    plan = json.loads(raw)
    rule = plan["decision_rule"]
    boot = rule["bootstrap"]
    out = {"kind": "li26_mac_metal_descriptive", "host_id": "mac-coordinator-64gb-20260925", "parity": False,
           "plan_sha256": hashlib.sha256(raw).hexdigest(), "prompt_sha256": plan["prompt_sha256"],
           "model": "unsloth/Qwen3.8-27B-GGUF@4ca720788d1e01f1bff70c033e0d0028fd02e502 Qwen3.8-27B-UD-Q4_K_M.gguf",
           "profile_note": "metrics.json's profile field repeats the plan's declaration; argv is what ran here",
           "runs": {}, "pairs": []}
    loaded = {}
    for label, (name, _, _) in RUNS.items():
        path = runs_dir / name / "eval" / "metrics.json"
        if not path.exists():
            out["runs"][label] = {"state": "missing"}
            continue
        metrics = json.loads(path.read_text())
        if metrics.get("plan_sha256") != out["plan_sha256"] or metrics.get("prompt_sha256") != plan["prompt_sha256"]:
            raise SystemExit(f"{label}: different plan or prompt")
        loaded[label] = metrics
        out["runs"][label] = summary(metrics, runs_dir / name, label)
    for control, arm, isolates in PAIRS:
        if control not in loaded or arm not in loaded:
            out["pairs"].append({"control": control, "arm": arm, "state": "missing"})
            continue
        c, a = loaded[control]["filings"], loaded[arm]["filings"]
        if [(f["accession"], tuple(f["gold"])) for f in c] != [(f["accession"], tuple(f["gold"])) for f in a]:
            raise SystemExit(f"{arm} is not paired with {control}")
        b = analyze.paired_bootstrap([analyze.counts(f["gold"], f["predicted"]) for f in c],
                                     [analyze.counts(f["gold"], f["predicted"]) for f in a],
                                     boot["resamples"], boot["seed"], boot["alpha"])
        rc, ra = out["runs"][control], out["runs"][arm]
        out["pairs"].append({
            "control": control, "arm": arm, "isolates": isolates, "n": len(c),
            "delta_micro_f1": round(b["point"], 4), "ci95": [round(b["lower"], 4), round(b["upper"], 4)],
            "identical_predictions": sum(sorted(x["predicted"] or []) == sorted(y["predicted"] or [])
                                         and x["parse_status"] == y["parse_status"] for x, y in zip(c, a)),
            "decode_speedup": round(ra["median_decode_tokens_per_second"] / rc["median_decode_tokens_per_second"], 3),
            "criteria_descriptive": {
                "noninferior_micro_f1": b["lower"] >= rule["noninferiority_margin"],
                "faster_median_decode": ra["median_decode_tokens_per_second"] > rc["median_decode_tokens_per_second"],
                "json_valid_rate": ra["json_valid_rate"] >= rule["json_valid_min"],
                "run_clean": ra["status"] == "completed" and not ra["events"] and ra["errors"] == 0
                             and ra["not_attempted"] == 0 and ra["memory_kills"] == 0,
            },
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=Path, required=True, help="the private mac-runs state directory")
    parser.add_argument("--check", type=Path, help="committed summary to compare with")
    args = parser.parse_args()
    derived = json.dumps(derive(args.runs), indent=2, sort_keys=True) + "\n"
    if args.check:
        same = args.check.read_text() == derived
        d = json.loads(derived)
        print(json.dumps({"matches_committed": same, "sha256": hashlib.sha256(derived.encode()).hexdigest(),
                          "runs": {k: {x: v.get(x) for x in ("micro_f1", "json_valid_rate", "median_decode_tokens_per_second",
                                                             "median_ttft_ms", "errors", "memory_kills")}
                                   for k, v in d["runs"].items()},
                          "pairs": [{x: p.get(x) for x in ("control", "arm", "delta_micro_f1", "ci95", "identical_predictions",
                                                           "decode_speedup")} for p in d["pairs"]]}, sort_keys=True))
        return 0 if same else 1
    sys.stdout.write(derived)
    return 0


if __name__ == "__main__":
    sys.exit(main())
