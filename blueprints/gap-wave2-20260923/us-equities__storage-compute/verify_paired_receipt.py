#!/usr/bin/env python3
"""Gap 6 helper: check that the committed paired Astra->Claude receipt records an
executed research-pair run and that its hashes bind the committed files.

Detection: each check compares a receipt field with a recomputed value or an
exact expected literal, so a missing role, a non-completed status, a wrong model
or a changed file makes the corresponding check false.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
d = root / "adoption/paired"
r = json.loads((d / "receipt.json").read_text())
h = lambda p: hashlib.sha256((d / p).read_bytes()).hexdigest()
a, c, dg = r["data"]["astra"], r["data"]["claude"], r["data"]["dagu"]
claude_report = json.loads((d / "claude.report.json").read_text())
astra_report = json.loads((d / "astra.report.json").read_text())
spec = importlib.util.spec_from_file_location("run_worker", root / "blueprints/us-equities/research-runtime/run_worker.py")
rw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw)
packet = json.loads((d / "packet.json").read_text())
astra_prompt = rw.native_prompt(packet, None)
claude_prompt = rw.native_prompt(packet, astra_report)
checks = {
    "research_pair_status_succeeded": dg["research_pair"]["status"] == "succeeded" and dg["research_pair"]["exit_code"] == 0,
    "native_history_status_verified": dg.get("native_history_status_verified") is True,
    "astra_completed_gpt_6_astra": a["status"] == "completed" and a["configured_model"] == "gpt-6-astra" and a["process_exit_code"] == 0,
    "claude_completed_claude_opus_5": c["status"] == "completed" and c["reported_models"] == ["claude-opus-5"] and c["process_exit_code"] == 0,
    "both_roles_workflow_astra_then_claude": a["workflow"] == c["workflow"] == "astra_then_claude",
    "same_packet_both_roles": a["packet_sha256"] == c["packet_sha256"] == h("packet.json"),
    "astra_report_hash_matches_file": a["report_sha256"] == h("astra.report.json"),
    "claude_report_hash_matches_file": c["report_sha256"] == h("claude.report.json"),
    "both_reports_validated": a["report_validation"] == c["report_validation"] == "citations_values_units_and_scope_passed",
    "usage_recorded_both_roles": bool(a["usage"]["total"]["totalTokens"]) and bool(c["usage"]["total_tokens"]),
    "model_calls_two": r["model_calls"] == 2,
    "astra_prompt_reconstructs": hashlib.sha256(astra_prompt.encode()).hexdigest() == a["prompt_sha256"] and len(astra_prompt.encode()) == a["prompt_bytes"],
    "claude_prompt_embeds_accepted_astra_report": hashlib.sha256(claude_prompt.encode()).hexdigest() == c["prompt_sha256"] and len(claude_prompt.encode()) == c["prompt_bytes"],
}
out = {"receipt": "adoption/paired/receipt.json", "receipt_sha256": h("receipt.json"),
       "file_sha256": {p: h(p) for p in ("astra.report.json", "claude.report.json", "packet.json", "observation.json")},
       "checks": checks, "all_pass": all(checks.values()),
       "research_pair_window_utc": [dg["research_pair"]["started_at"], dg["research_pair"]["finished_at"]],
       "models": [a["configured_model"], c["reported_models"]],
       "usage": {"astra_total_tokens": a["usage"]["total"]["totalTokens"], "claude_total_tokens": c["usage"]["total_tokens"]},
       "claude_report_keys": sorted(claude_report) if isinstance(claude_report, dict) else None,
       "astra_report_keys": sorted(astra_report) if isinstance(astra_report, dict) else None}
print(json.dumps(out, indent=1))
sys.exit(0 if out["all_pass"] else 1)
