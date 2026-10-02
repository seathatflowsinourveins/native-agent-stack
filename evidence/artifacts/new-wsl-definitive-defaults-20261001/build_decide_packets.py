#!/usr/bin/env python3
"""Build the decision-round slot packets: one default per contested slot.

Inputs (read-only): the round-one layer packets on main, the sanitized round-one returns (judges and critics),
the second reviewer's parity return for durable memory, and one on-record comparison for the context-supply slot.
Outputs: packets/<slot>.order-1.json and .order-2.json (same content, finalists in two seeded orders) and
preregistration.json with the sha256 of every input the deciders see. Reviewer identities are not written.
"""
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(sys.argv[1])
MAIN = sys.argv[2]
ROUND1 = Path(sys.argv[3])
SECOND = Path(sys.argv[4])
PKT = "evidence/artifacts/new-wsl-clean-install-selection-20261001/packets"


def show(path):
    return subprocess.run(["git", "-C", str(REPO), "show", f"{MAIN}:{path}"], check=True, capture_output=True, text=True).stdout


def packet(layer):
    return json.loads(show(f"{PKT}/{layer}.json"))


r1 = json.loads(ROUND1.read_text())
JUDGED = {l["layer_id"]: l for g in r1["groups"] for l in g["judged"]}
CRITIC = {l["layer_id"]: l for g in r1["groups"] for l in g["critique"]["layers"]}
second = json.loads(SECOND.read_text())["layers"][0]


def notes(layer, needles):
    """Round-one notes about the named finalists in one layer: the reviewer's role or reason text and its cited facts."""
    out = []
    j = JUDGED[layer]
    for kind, rows, field in (("selected", j["selection"], "role"), ("not selected", j["not_selected"], "reason")):
        for row in rows:
            if any(n.lower() in row["name"].lower() for n in needles):
                item = {"about": row["name"], "first_round_status": kind, "note": row[field]}
                if row.get("basis"):
                    item["cited_facts"] = [{"url": b["url"], "shows": b["shows"]} for b in row["basis"]]
                out.append(item)
    return out


def critic(layer):
    c = CRITIC[layer]
    return {"findings": c["findings"], "checked_facts": c["checked_facts"], "deciding_comparison": c["deciding_comparison"]}


def cand(layer, needle):
    for c in packet(layer)["candidates"]:
        if needle.lower() in c["name"].lower():
            return {"name": c["name"], "repository": c["repository"]}
    raise SystemExit(f"no candidate {needle!r} in {layer}")


HARBOR = ("This project's own run on an upstream harness (Harbor v0.23.0, built-in claude_code agent; 288 trials on 36 SWE-bench Verified tasks; "
          "one repetition per arm and task; Sonnet 5.5 at medium effort; short single-session tasks, no subagents; list-price cost estimate). "
          "Whole-task cost against the no-tool base: Headroom 0.39.1 0.983, RTK 1.027 and Serena 1.063, all inconclusive (their intervals include 1, as the A/A control's does); "
          "Context Mode, jcodemunch and the full stack +30% to +39% (intervals above 1). Complete provider tokens, paired on tasks both arms solved: "
          "Headroom 0.867 (0.775 to 0.971); RTK 0.955 (0.847 to 1.078); Context Mode +18%; jcodemunch +41%. sqz did not run. "
          "The arm wrappers and analysis script are local integration code; the prompt cache was not controlled per trial.")

SLOTS = [
    {"slot_id": "container-engine", "layer": "hosting-services",
     "question": "Which single container engine does the new host install? Docker Compose is already settled as the multi-service definition.",
     "finalists": [cand("hosting-services", "Podman"), cand("hosting-services", "Docker Engine")],
     "first_round": {"reviewer_notes": notes("hosting-services", ["Podman", "Docker Engine", "Docker Compose"]) + notes("isolation", ["Podman", "Docker Engine"]),
                     "critic": critic("hosting-services"), "related_critic_findings": CRITIC["isolation"]["findings"],
                     "evidence_gaps": JUDGED["hosting-services"]["evidence_gaps"]},
     "context": "Tools that other layers' first-round selections or the user's named runtime workers run in containers: Inspect AI, Harbor, gVisor (an isolation finalist), "
                "OpenHands software-agent-sdk, DeerFlow. Check what each one's upstream documentation requires before relying on it. "
                "The base distribution is Ubuntu 26.04.1 LTS under WSL2 with systemd; 24.04.5 is the fallback."},
    {"slot_id": "isolation-container-boundary", "layer": "isolation",
     "question": "sandbox-runtime (filesystem and network rules) and Worktrunk (edit separation) are settled. For untrusted workloads that also need a container or VM boundary "
                 "with resource limits, which single option does the new host use?",
     "finalists": [{"name": "No additional component: rootless containers on the container engine that the hosting layer installs", "repository": "", "installs_nothing_extra": True},
                   cand("isolation", "gVisor"), cand("isolation", "boxlite"), cand("isolation", "microsandbox")],
     "first_round": {"reviewer_notes": notes("isolation", ["sandbox-runtime", "Podman", "Docker Engine", "gVisor", "boxlite", "microsandbox"]),
                     "critic": critic("isolation"), "evidence_gaps": JUDGED["isolation"]["evidence_gaps"]},
     "context": "The container engine is decided in a separate slot of this round (Podman with Quadlet, or Docker Engine in rootless mode)."},
    {"slot_id": "code-search", "layer": "semantic-rag",
     "question": "Which single engine answers conceptual code questions for Claude Code and Codex sessions on the new host?",
     "finalists": [cand("semantic-rag", "SocratiCode"), cand("semantic-rag", "semble"),
                   dict(cand("semantic-rag", "next-plaid"), name="ColGREP (next-plaid), with LateOn-Code or LateOn-Code-edge")],
     "first_round": {"reviewer_notes": notes("semantic-rag", ["SocratiCode", "semble", "next-plaid", "ollama"]),
                     "critic": critic("semantic-rag"), "evidence_gaps": JUDGED["semantic-rag"]["evidence_gaps"]},
     "context": "An engine that needs an embedding service makes the host install and run that service as well; the local model server is decided in a separate slot."},
    {"slot_id": "memory-owner", "layer": "durable-memory",
     "question": "Which single system owns durable memory for both Claude Code and Codex on the new host? Exactly one is installed.",
     "finalists": [cand("durable-memory", "ai-memory"), cand("durable-memory", "Hindsight"), cand("durable-memory", "agentmemory (rohitg00)"), cand("durable-memory", "deja-vu")],
     "first_round": {"reviewer_notes": notes("durable-memory", ["ai-memory", "Hindsight", "agentmemory", "deja-vu"]),
                     "critic": critic("durable-memory"), "evidence_gaps": JUDGED["durable-memory"]["evidence_gaps"],
                     "second_reviewer_notes": [
                         {"about": s["name"], "first_round_status": "selected", "note": s["role"],
                          "cited_facts": [{"url": b["url"], "shows": b["shows"]} for b in s.get("basis", [])]} for s in second["selection"]] + [
                         {"about": s["name"], "first_round_status": "not selected", "note": s["reason"]} for s in second["not_selected"] if "Hindsight" in s["name"]],
                     "second_reviewer_evidence_gaps": second["evidence_gaps"]},
     "context": "Two independent first-round reviewers read the same packet. Both kept ai-memory, agentmemory and deja-vu as finalists; one also kept Hindsight."},
    {"slot_id": "context-supply", "layer": "token-efficiency",
     "question": "ccusage is settled as the provider-usage meter. Which single context-supply option does the new host install for Claude Code and Codex sessions?",
     "finalists": [{"name": "No context-supply layer: the usage meter only", "repository": "", "installs_nothing_extra": True},
                   cand("token-efficiency", "rtk"), cand("token-efficiency", "sqz"), cand("token-efficiency", "Headroom")],
     "first_round": {"reviewer_notes": notes("token-efficiency", ["RTK", "rtk", "sqz", "Headroom", "Context Mode", "ccusage"]),
                     "critic": critic("token-efficiency"), "evidence_gaps": JUDGED["token-efficiency"]["evidence_gaps"]},
     "extra_on_record": [HARBOR],
     "context": "The requirement's own metric is complete provider usage and cost per solved task at equal task success, not a tool's own artifact-reduction estimate."},
    {"slot_id": "local-model-server", "layer": "observation-inference",
     "question": "Which single local model server does the new host install for the optional local inference route? State also whether it can serve embeddings "
                 "to a code-search engine that needs an embedding endpoint, so that one server covers both roles.",
     "finalists": [cand("observation-inference", "llama.cpp"), cand("semantic-rag", "ollama"), cand("observation-inference", "vllm"), cand("observation-inference", "SGLang")],
     "first_round": {"reviewer_notes": notes("observation-inference", ["llama.cpp", "vllm", "SGLang"]) + notes("semantic-rag", ["ollama", "vLLM"]),
                     "critic": critic("observation-inference"), "evidence_gaps": JUDGED["observation-inference"]["evidence_gaps"]},
     "context": "The code-search slot is decided in the same round among SocratiCode (documented embedding providers: Ollama, OpenAI-compatible, Google, LM Studio, LiteLLM), "
                "semble and ColGREP (both embed in-process). The route is optional under the requirement: Claude Code and Codex keep their native model accounts."},
]

out = HERE / "packets"
out.mkdir(exist_ok=True)
hashes = {}
for s in SLOTS:
    p = packet(s["layer"])
    names = sorted(f["name"].lower() for f in s["finalists"])
    assert len(set(names)) == len(names), s["slot_id"]
    keyed = [dict(key=f"F{i + 1}", **f) for i, f in enumerate(sorted(s["finalists"], key=lambda f: f["name"].lower()))]
    base = {"slot_id": s["slot_id"], "layer_id": s["layer"], "title": p["title"], "requirement": p["requirement"], "slot_question": s["question"],
            "a_deciding_comparison_would_measure": p["a_deciding_comparison_would_measure"], "target_hosts": p["target_hosts"], "context": s["context"],
            "comparisons_on_record_where_every_named_arm_ran": p["comparisons_on_record_where_every_named_arm_ran"] + s.get("extra_on_record", []),
            "first_round": s["first_round"]}
    orders = []
    for n in (1, 2):
        order = keyed[:]
        random.Random(f"decide:{s['slot_id']}:{n}").shuffle(order)
        orders.append(order)
    if [f["key"] for f in orders[0]] == [f["key"] for f in orders[1]]:
        orders[1] = orders[1][::-1]
    for n, order in enumerate(orders, 1):
        doc = dict(base)
        doc["finalists"] = order
        text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
        path = out / f"{s['slot_id']}.order-{n}.json"
        path.write_text(text, encoding="utf-8")
        hashes[path.name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        print(path.name, len(text), [f["key"] for f in order])

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
prereg = {
    "schema_version": 1, "kind": "decision-round-preregistration", "recorded_at": sys.argv[5],
    "purpose": "one default per contested slot for the new WSL clean install; every other finalist is recorded as an alternative with the comparison that would replace the default",
    "trigger": "the user's first-hand directive of 2026-10-01 about 20:35Z: a definitive converged architecture with evidence from upstream evaluations and no 'one of' slots",
    "source_main": MAIN, "round_one_returns_sha256": sha(ROUND1), "second_reviewer_return_sha256": sha(SECOND),
    "criteria_sha256": sha(HERE / "criteria.txt"), "decide_prompt_sha256": sha(HERE / "decide-prompt.txt"), "critic_prompt_sha256": sha(HERE / "decide-critic-prompt.txt"),
    "packets_sha256": hashes,
    "dispatch": "per slot: two independent deciders (finalists in two seeded orders), then one adversarial critic; each model family runs the same packets and prompts",
    "decision_rule": "a slot's default is definitive when both deciders of both families name it and both critics return converged; a split is settled by the measurement the critics name",
    "excluded_evidence": "the project's adoption records; a comparison on record is included only where every named arm ran",
    "not_claimed": "no candidate is installed or measured by this round; a default decided on documented fit says so",
}
(HERE / "preregistration.json").write_text(json.dumps(prereg, indent=1) + "\n", encoding="utf-8")
print("preregistration written;", len(hashes), "packets")
