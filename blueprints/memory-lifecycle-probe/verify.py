#!/usr/bin/env python3
"""Validate useful native returned content against the frozen synthetic corpus."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "evidence/artifacts/memory-lifecycle-probe-20260921"
corpus_path = Path(__file__).with_name("corpus.json")
corpus = json.loads(corpus_path.read_text())
events = json.loads((ART / "commands.json").read_text())
by_label = {event["label"]: event for event in events}
checks = []


def check(name, passed):
    checks.append({"name": name, "passed": bool(passed)})


def payload(label):
    return json.loads(by_label[label]["stdout"])


def results(label):
    data = payload(label)
    return data if isinstance(data, list) else data["results"]


def body(label):
    data = payload(label)
    return data.get("body", data.get("content", ""))


check("frozen corpus hash unchanged", hashlib.sha256(corpus_path.read_bytes()).hexdigest()
      == (ART / "frozen-corpus-sha256.txt").read_text().split()[0])
for tool in ("ai", "basic"):
    for q in corpus["queries"]:
        found = results(f"{tool}-search-{q['query']}")
        check(f"{tool}: {q['query']} returns one matching note and expected fact",
              len(found) == 1 and q["expected_slug"] in json.dumps(found)
              and q["expected_fact"] in json.dumps(found))
        check(f"{tool}: full read preserves {q['expected_slug']} fact",
              q["expected_fact"] in body(f"{tool}-read-{q['expected_slug']}"))
    updated = results(f"{tool}-search-updated")
    check(f"{tool}: updated search returns violet and 19 days",
          len(updated) == 1 and "violet" in json.dumps(updated) and "19 days" in json.dumps(updated))
    check(f"{tool}: old amber query returns no results", results(f"{tool}-search-old") == [])
    check(f"{tool}: updated full read contains new fact, excludes old fact",
          "19 days" in body(f"{tool}-read-updated") and "17 days" not in body(f"{tool}-read-updated"))
    check(f"{tool}: deleted Juniper query returns no results", results(f"{tool}-search-deleted") == [])
    stage = "restart" if tool == "ai" else "reindex"
    check(f"{tool}: after {stage}, full read retains new fact",
          "19 days" in body(f"{tool}-after-{stage}-updated"))
    remaining = results(f"{tool}-after-{stage}-remaining")
    check(f"{tool}: after {stage}, remaining cobalt fact is searchable",
          len(remaining) == 1 and "12 knots" in json.dumps(remaining))
    check(f"{tool}: after {stage}, deleted Juniper query stays empty",
          results(f"{tool}-after-{stage}-deleted") == [])

completed = [event for event in events if "exit_code" in event]
check("all recorded lifecycle commands exited successfully", all(e["exit_code"] == 0 for e in completed))
summary = {
    "evidence_class": "tiny synthetic native CLI lifecycle comparison",
    "accepted_evidence_sources": {"ai_memory": "Corrected second run, explicit embedding_provider=none", "basic_memory": "Original run, explicit semantic_search_enabled=false; reused unchanged"},
    "passed": sum(c["passed"] for c in checks),
    "total": len(checks),
    "completed_command_count": len(completed),
    "checks": checks,
    "ai_memory_recovery": "Not run: inspected upstream restore/reindex guard scans all same-name processes, beyond the authorized isolated state. No guard bypass.",
    "basic_memory_recovery": "Full search index rebuild exercised; this is not loss-of-database restore.",
    "limits": ["Lexical fixture only, no semantic quality claim", "No concurrency/crash/schema migration test", "No agent hooks or real memory", "Single host/run; startup costs and different architectures confound timing comparisons", "Accepted runs explicitly disable embeddings and configure no LLM provider; network egress was not instrumented", "Initial ai-memory attempt failed no-model-download constraint and is retained separately"]
}
(ART / "verification.json").write_text(json.dumps(summary, indent=2) + "\n")
print(f"{summary['passed']}/{summary['total']} content checks passed across {len(completed)} native command processes")
raise SystemExit(0 if all(c["passed"] for c in checks) else 1)
