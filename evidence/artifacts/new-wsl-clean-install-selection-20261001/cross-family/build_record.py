#!/usr/bin/env python3
"""Public record of the cross-family (GPT-6.1 Sol) blind run from its private originals.

Reads the private run directory written by run_xfam.py (judge and critic returns, codex event streams, the run
summary), audits every web search, opened page and command for the project's own repositories and local paths,
applies each critic's verdict to its judge's selection exactly as agreement-rule.txt defines G, and writes:

- selection-gpt.json: per layer, the GPT picks after the critic, the judge's picks when the critic revised them,
  not-selected reasons, exclusions, failed fact checks and the critic's issues;
- run-record.json: every process attempt with its exit, duration and returned usage, key-coverage findings, the
  contamination audit and the sha256 of each private original.

Paths of the private scratch directory are rewritten to their published names. Usage:
build_record.py <private run dir> <this folder>
"""
import hashlib
import json
import re
import sys
from pathlib import Path

PRIVATE, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OWN = re.compile(r"seathatflowsinourveins|native-agent-stack", re.IGNORECASE)
LOCAL = re.compile(r"(?:/Users/|/home/|~/|/private/|/tmp/)[^\s'\"]*")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(text: str) -> str:
    """Rewrite private scratch paths to the published file names."""
    text = re.sub(r"[^\s'\"(]*/input/packets/", "packets/", text)
    return re.sub(r"[^\s'\"(]*/input/facts/", "cross-family/facts/", text)


def clean(value):
    if isinstance(value, str):
        return publish(value)
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def audit(events: Path, input_dir: str) -> dict:
    searches, pages, commands, flags = 0, 0, 0, []
    for line in events.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        kind = item.get("type")
        if kind == "web_search":
            action = item.get("action") or {}
            text = json.dumps([item.get("query"), action])
            if action.get("type") == "search":
                searches += 1
            elif action.get("type") in ("open_page", "find_in_page", "open"):
                pages += 1
            if OWN.search(text):
                flags.append({"kind": "web_search", "detail": publish(text)[:300]})
        elif kind == "command_execution":
            commands += 1
            command = item.get("command") or ""
            outside = [p for p in LOCAL.findall(command) if input_dir not in p]
            if OWN.search(command) or outside:
                flags.append({"kind": "command", "detail": publish(command)[:300]})
    return {"web_searches": searches, "pages_opened": pages, "commands": commands, "flags": flags}


def main() -> int:
    results = json.loads((PRIVATE / "out" / "results.json").read_text(encoding="utf-8"))
    summary = json.loads((PRIVATE / "out" / "summary.json").read_text(encoding="utf-8"))
    assignment = json.loads((PRIVATE / "prereg" / "assignment.json").read_text(encoding="utf-8"))
    input_dir = str(PRIVATE / "input")
    judge_of = {layer: j["judge"] for j in assignment["judges"] for layer in j["packets"]}
    group_of = {jid: g["group"] for g in assignment["groups"] for jid in g["judges"]}
    critic_layers = {}
    for group in assignment["groups"]:
        critic = results.get("C-" + group["group"]) or {}
        for entry in critic.get("layers", []):
            critic_layers[entry["layer_id"]] = entry
    layers = []
    for layer_id, jid in judge_of.items():
        judged = next((l for l in (results.get(jid) or {}).get("layers", []) if l.get("layer_id") == layer_id), None)
        if judged is None:
            layers.append({"layer_id": layer_id, "judge": jid, "status": "missing", "picks": []})
            continue
        critic = critic_layers.get(layer_id)
        verdict = critic["verdict"] if critic else "no_critic_return"
        picks = judged["selection"]
        entry = {"layer_id": layer_id, "judge": jid, "critic": "C-" + group_of[jid], "critic_verdict": verdict}
        if critic and verdict == "revised" and critic.get("revised_selection"):
            entry["judge_picks"] = [{k: p.get(k) for k in ("key", "name", "repository")} for p in picks]
            picks = [{"key": p["key"], "name": p["name"], "repository": p["repository"], "role": p.get("why", ""),
                      "install_command": "", "install_source": "", "confidence": ""} for p in critic["revised_selection"]]
        entry["status"] = "compare" if verdict == "undetermined" else "recommended"
        entry["picks"] = [{k: p.get(k) for k in ("key", "name", "repository", "role", "install_command",
                                                  "install_source", "confidence")} for p in picks]
        entry.update({
            "close_call": judged.get("close_call"),
            "deciding_head_to_head": (critic or {}).get("deciding_head_to_head") or judged.get("deciding_head_to_head"),
            "deciding_comparison": judged.get("deciding_comparison"),
            "not_selected": judged.get("not_selected", []),
            "excluded": judged.get("excluded", []),
            "evidence": {p["key"]: p.get("evidence", []) for p in judged["selection"]},
            "failed_fact_checks": [c for c in (critic or {}).get("fact_checks", []) if not c.get("holds")],
            "fact_checks_run": len((critic or {}).get("fact_checks", [])),
            "critic_issues": (critic or {}).get("issues", []),
            "stronger_candidates": (critic or {}).get("stronger_candidates", []),
        })
        layers.append(clean(entry))
    audits = {}
    originals = {}
    for path in sorted((PRIVATE / "out").glob("*")):
        if path.is_file():
            originals[path.name] = sha(path)
        if path.name.endswith(".events.jsonl"):
            audits[path.name.split(".")[0] + "." + path.name.split(".")[1]] = audit(path, input_dir)
    flagged = {k: v["flags"] for k, v in audits.items() if v["flags"]}
    record = {
        "kind": "cross_family_blind_selection",
        "family": "OpenAI GPT-6.1 Sol through Codex CLI 0.159.3, model_reasoning_effort=max, live web search, read-only "
                  "sandbox, ephemeral sessions",
        "run": {"model": summary["model"], "effort": summary["effort"], "finished_at": summary["finished_at"],
                "processes": len({r["run_id"] for r in summary["records"] if "attempt" in r}),
                "attempts": sum(1 for r in summary["records"] if "attempt" in r)},
        "contamination_audit": {"status": "clean" if not flagged else "flagged", "flagged": flagged},
        "layers": layers,
    }
    run_record = {
        "kind": "cross_family_run_record",
        "records": clean(summary["records"]),
        "audit": clean(audits),
        "private_originals_sha256": originals,
    }
    (OUT / "selection-gpt.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "run-record.json").write_text(json.dumps(run_record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"layers": len(layers), "contamination": record["contamination_audit"]["status"],
                      "attempts": record["run"]["attempts"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
