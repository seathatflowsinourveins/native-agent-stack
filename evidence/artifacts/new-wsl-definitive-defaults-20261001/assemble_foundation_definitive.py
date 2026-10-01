#!/usr/bin/env python3
"""Assemble the foundation half of the new-WSL definitive manifest: one default per slot.

Inputs:
  <repo>            a checkout holding evidence/artifacts/new-wsl-clean-install-selection-20261001/{selection,ownership}.json
  <decision-dir>    the decision round's directory: claude-returns.json, gpt/<slot>.order-N.json, gpt/<slot>.critic.json,
                    preregistration.json
  <out-dir>         where foundation-definitive.json (full) and foundation-definitive.compact.json are written

Rule (preregistered in <decision-dir>/preregistration.json): a slot's default is definitive when both deciders of both
model families name it and both critics return converged. A layer the first round settled with one judge and one critic
keeps that pick as its default and stays not definitive until the second family's first-round verdict agrees.
Nothing is installed or measured by this script or by the rounds it reads.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

REPO, DEC, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SEL_DIR = REPO / "evidence/artifacts/new-wsl-clean-install-selection-20261001"
PLACEHOLDER = "<definitive-defaults-20261001>/"
SCRATCH = re.compile(r"/tmp/claude-\d+/[^\s\"']*?/scratchpad")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


selection = json.loads((SEL_DIR / "selection.json").read_text(encoding="utf-8"))
ownership = json.loads((SEL_DIR / "ownership.json").read_text(encoding="utf-8"))
claude = json.loads((DEC / "claude-returns.json").read_text(encoding="utf-8"))
prereg = json.loads((DEC / "preregistration.json").read_text(encoding="utf-8"))
SEL = {l["layer_id"]: l for l in selection["layers"]}
OWN = {l["layer_id"]: l for l in ownership["layers"]}

# The decision round's slots and the layer that owns each.
SLOT_LAYER = {
    "container-engine": "hosting-services",
    "isolation-container-boundary": "isolation",
    "code-search": "semantic-rag",
    "memory-owner": "durable-memory",
    "context-supply": "token-efficiency",
    "local-model-server": "observation-inference",
}
# First-round picks that another layer owns, or that a decision slot replaces (substring of the pick's name, per layer).
NOT_A_SLOT_HERE = {
    "workers": ["claude-code", "Codex native workers", "Worktrunk"],
    "isolation": ["Worktrunk", "Podman"],
    "semantic-rag": ["SocratiCode", "semble", "ollama"],
    "durable-memory": ["ai-memory", "Hindsight", "agentmemory", "deja-vu"],
    "token-efficiency": ["rtk"],
    "observation-inference": ["llama.cpp"],
    "scheduling-supervision": ["systemd"],
    "hosting-services": ["Podman", "Docker Engine"],
    "git-github-automation": ["sem "],
    "cross:wsl-distro": ["24.04.5"],
}
# Independent fact read of the memory slot by the Gate A owner's session (Claude family, not a vote), 2026-10-01.
MEMORY_QUALIFICATIONS = [
    "Label: default on documented fit; measured retrieval adverse. Confidence medium-low.",
    "The measured record is adverse on retrieval (evidence/artifacts/memory-stack-20260925/convergence.json; LongMemEval-S recall_all@5, 470 "
    "questions, descriptive): agentmemory 0.9.29 over its REST path 0.821 with the MiniLM embedder and 0.617 keyless; ai-memory (a 2.5 "
    "pre-release, reranker off) 0.570 with Qwen3 embeddings, 0.496 with the same MiniLM embedder and 0.400 with full-text search only; plain "
    "BM25 0.747. The packet gave the deciders only the pair 0.821 against 0.570 (paired difference +0.251, interval +0.203 to +0.299). Limits: "
    "agentmemory over REST and not its hooks, different capture, ai-memory's reranker and hook path not run.",
    "Embeddings are off by default. In the shipped zero-LLM configuration the vendor's own figures are hit@5 0.666 and recall@5 0.536; "
    "0.815 and 0.677 need AI_MEMORY_EMBEDDING_PROVIDER=local. The install must set that variable or declare zero-LLM as the shipped configuration.",
    "Handoff routing: upstream's design note says a pending handoff is claimed by whichever session starts next. The fix (upstream issue 959) "
    "was on a branch and not in v2.5.2 when read; the managed-Codex fix (issue 987) was on main and not in v2.5.2. Install the release that "
    "carries both, or document --no-daemon for managed Codex runs and the handoff caveat.",
    "Purge is not scope-contained: it cascades across scopes and its preview omits some mailbox and reference effects.",
    "LLM consolidation is opt-in; without a provider the summaries are rule-based.",
    "No challenger documents better handoff routing, so these facts qualify the default and do not decide the slot.",
]
CONTEXT_SUPPLY_NOTES = [
    "The deciding metric is the requirement's own: provider cost per solved task at equal task success, not a tool's artifact estimate and not billed cost alone.",
    "RTK v0.44.1's billed-cost change of -2.7% (-5.6 to -0.1), pooled over three models, excludes zero, but on cost per solved task the same study reads "
    "0.968 (0.937 to 1.004), with -2.3% (-7.4 to +2.1) on its frozen holdout and -0.1% (-9.3 to +7.8) in its Opus replication.",
    "The evidence covers short single-session tasks. The multi-agent regime is untested, and the re-aimed Gate A run is this default's overturn check; it runs on "
    "a rehearsal distribution, not on the clean install.",
    "The GPT family converged on the no-install rule without re-reading the published studies (page fetching was refused on its side); one of its "
    "deciders said the unverified interval could change the decision. The Gate A owner re-read the paper on 2026-10-01 and found the figures exact. "
    "A rerun of the GPT critic with page access is requested.",
]
ENGINE_NOTES = [
    "One material fact was not weighed in this slot. The isolation slot's critic found microsoft/WSL issue 41492 (open): rootless Docker cannot "
    "start a container after WSL moved the cgroup tree. The reports are on 2.9.9, 2.9.10 and a master build; the stable 3.0.1 (2026-09-29) "
    "carries the same change, and whether it fixes the failure is not verified. A WSL contributor suggests isolateDistroCgroup=false and reports "
    "rootless Podman working; Moby's fix was open and unmerged. No engine-slot decider or critic cited it.",
    "The same critic noted that the WSL 3.0.1 release notes announce WSL containers as generally available; no packet covered that option.",
    "The default holds for the WSL 2.7 line, which predates the change. A re-decision with both facts in the packet is requested from both "
    "families, and before any WSL update the rehearsal first checks that the chosen engine starts a rootless container on that exact version.",
    "Rootless Docker is also what the source host runs, so incumbency cannot be ruled out as an influence on this pick.",
]
SLOT_NOTES = {"memory-owner": MEMORY_QUALIFICATIONS, "context-supply": CONTEXT_SUPPLY_NOTES, "container-engine": ENGINE_NOTES}
# A slot the user took out of the blind round's hands. The round's pick is kept on the row, but it is not installed
# ahead of the measurement the user asked for.
USER_DECIDED_BY_MEASUREMENT = {
    "memory-owner": {
        "request": "The user asked on 2026-10-01, after reading why ai-memory was picked over Hindsight, that the best system be installed "
                   "(naming Hindsight, cognee and OpenViking), and had decided on 2026-09-30 that the memory head-to-head deploys its best-scoring "
                   "eligible system with no protected incumbent.",
        "measurement": "The memory layer's preregistered head-to-head (Memory layer S3, revision 7, pull request 526; a draft until its freeze): "
                       "each system hosted through its upstream deployment with GPT-6 as its model backbone and as answerer and judge, the "
                       "agent-memory-benchmark harness unmodified, LongMemEval-V2 as the main usefulness test against a no-memory control, and a "
                       "symmetric merit rule in which ai-memory competes with no protected status.",
        "candidates": ["agentmemory", "Hindsight", "OpenViking", "cognee", "MemPalace", "Basic Memory", "memsearch", "ai-memory",
                       "deja-vu (a finalist of the blind round, added at the freeze)"],
        "rule": "the head-to-head's best-scoring eligible system is installed; the incumbent is not kept by default (the user's decision of "
                "2026-09-30, in the head-to-head's record)",
        "blocked_on": "the GPT gateway's capacity (its cached limits read 0 remaining on all six accounts at the 2026-10-01T20:59Z sync) and the "
                      "freeze of the preregistration with current pins",
    },
}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def scrub(x):
    """Replace the decision directory's host path with a placeholder; no host path or user name leaves this file."""
    if isinstance(x, str):
        x = x.replace(str(DEC) + "/", PLACEHOLDER)
        # A worker's scratch directory names the host user and the session; neither leaves this file.
        return SCRATCH.sub("<scratchpad>", x)
    if isinstance(x, list):
        return [scrub(v) for v in x]
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    return x


def packet(slot):
    return json.loads((DEC / "packets" / f"{slot}.order-1.json").read_text(encoding="utf-8"))


def key_of(slot, name):
    """Map a returned name to its finalist key by longest shared prefix with a finalist's name."""
    best, best_n = None, 0
    low = name.lower()
    for f in packet(slot)["finalists"]:
        fn = f["name"].lower()
        n = 0
        for a, b in zip(low, fn):
            if a != b:
                break
            n += 1
        if n > best_n:
            best, best_n = f["key"], n
    return best if best_n >= 4 else None


def converged(slot, decider_keys, critic):
    """A family is converged only when its critic returned converged on a valid finalist and both of its deciders
    returned and named that same finalist (agreement in both orders, Zheng et al. 2023, section 3.4)."""
    if not critic or critic["verdict"] != "converged" or len(decider_keys) != 2:
        return False
    valid = {f["key"] for f in packet(slot)["finalists"]}
    critic_key = key_of(slot, critic["default_after_review"]["name"])
    return critic_key in valid and decider_keys == [critic_key, critic_key]


def family_claude(slot):
    s = claude["slots"][slot]
    decs = [s["decisions"].get(o) for o in ("order-1", "order-2")]
    crit = s["critique"]
    keys = [d["default"]["key"] for d in decs if d]
    return {"round": 2, "run": claude["run"], "method": "two deciders in seeded orders plus one critic",
            "decider_defaults": keys, "critic_verdict": crit["verdict"] if crit else None,
            "default_key": key_of(slot, crit["default_after_review"]["name"]) if crit else None,
            "status": "converged" if converged(slot, keys, crit) else "returned"}, decs, crit


def family_gpt(slot):
    decs = []
    for n in (1, 2):
        p = DEC / "gpt" / f"{slot}.order-{n}.json"
        decs.append(json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.stat().st_size else None)
    p = DEC / "gpt" / f"{slot}.critic.json"
    crit = json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.stat().st_size else None
    keys = [key_of(slot, d["default"]["name"]) if d["default"].get("key") in (None, "") else d["default"]["key"] for d in decs if d]
    if converged(slot, keys, crit):
        status = "converged"
    elif crit:
        status = "returned: " + crit["verdict"]
    elif keys:
        status = f"pending: {len(keys)} of 2 deciders returned, critic not returned"
    else:
        status = "pending"
    return {"round": 2, "method": "two deciders in seeded orders plus one critic, GPT-6.1 Sol at ultra through native codex exec",
            "decider_defaults": keys, "critic_verdict": crit["verdict"] if crit else None,
            "default_key": key_of(slot, crit["default_after_review"]["name"]) if crit else None, "status": status}, decs, crit


def label_for(dec):
    if dec["decided_on"] == "no_install_baseline":
        return "no-install default: no challenger showed a gain on the requirement's metric with an interval excluding zero"
    if dec["could_not_separate"]:
        return "default on documented fit; nothing measured separates the finalists"
    return "default on " + dec["decided_on"].replace("_", " ")


def decided_slot(slot):
    pk = packet(slot)
    names = {f["key"]: f for f in pk["finalists"]}
    c_fam, c_decs, c_crit = family_claude(slot)
    g_fam, g_decs, g_crit = family_gpt(slot)
    d1 = c_decs[0]
    default_key = c_fam["default_key"] or d1["default"]["key"]
    fin = names[default_key]
    facts, seen = [], {}
    for d in c_decs:
        for f in d["deciding_facts"]:
            if f["fact"] not in seen:
                seen[f["fact"]] = 1
                facts.append({"fact": f["fact"], "url": f["url"], "rechecked_by_decider": f["rechecked_now"]})
    corrections = [{"family": "claude", "claim": c["claim"]} for c in c_crit["checked_facts"] if not c["holds"]]
    if g_crit:
        corrections += [{"family": "gpt", "claim": c["claim"]} for c in g_crit["checked_facts"] if not c["holds"]]
    definitive = (c_fam["status"] == "converged" and g_fam["status"] == "converged" and c_fam["default_key"] == g_fam["default_key"])
    agree_so_far = bool(g_fam["decider_defaults"]) and all(k == default_key for k in g_fam["decider_defaults"])
    row = {
        "slot_id": slot, "row_kind": "judged", "question": pk["slot_question"], "definitive": definitive,
        "default": {"name": fin["name"], "repository": fin.get("repository", ""),
                    "installs_nothing_extra": bool(fin.get("installs_nothing_extra")),
                    "install_command": d1["default"]["install_command"], "install_source": d1["default"]["install_source"]},
        "label": label_for(d1), "decided_on": d1["decided_on"], "could_not_separate": d1["could_not_separate"],
        "decided_by_criterion": d1["decided_by_criterion"],
        "alternatives": [{"name": a["name"], "reason": a["reason"]} for a in d1["alternatives"]],
        "evidence": facts, "corrections_by_critics": corrections,
        "overturn_check": c_crit["overturn_check"],
        "overturn_check_gpt": g_crit["overturn_check"] if g_crit else None,
        "critic_findings": {"claude": c_crit["findings"], "gpt": g_crit["findings"] if g_crit else None},
        "families": {"claude": c_fam, "gpt": g_fam},
        "families_agree_so_far": agree_so_far,
    }
    if slot in SLOT_NOTES:
        row["qualifications_from_independent_fact_read"] = SLOT_NOTES[slot]
    if g_fam["decider_defaults"] and not agree_so_far:
        other = sorted({names[k]["name"] for k in g_fam["decider_defaults"] if k and k != default_key})
        row["split_note"] = ("the GPT family's returned decider(s) name " + ", ".join(other) + "; if its critic keeps that, the slot is split "
                             "and the measurement the critics name decides it")
    if slot in USER_DECIDED_BY_MEASUREMENT:
        over = USER_DECIDED_BY_MEASUREMENT[slot]
        row["blind_round_pick"] = dict(row["default"], agreed_by_both_families=definitive,
                                       label="default on documented fit; measured retrieval adverse; medium-low confidence")
        row["blind_round_overturn_check"] = row["overturn_check"]
        row["overturn_check"] = over["rule"]
        row["definitive"] = False
        row["decided_by_measurement_at_user_request"] = over
        row["default"] = {"name": "Not installed until the memory head-to-head returns (the blind round's documented-fit pick is " + fin["name"] + ")",
                          "repository": "", "installs_nothing_extra": True, "install_command": "", "install_source": ""}
        row["label"] = ("decided by measurement at the user's request: the best-scoring eligible system of the memory head-to-head is installed, "
                        "with no protected incumbent")
    if g_crit and g_fam["default_key"] and g_fam["default_key"] != default_key and c_fam["status"] == "converged":
        # Both families returned and they differ. The record does not pick between them: nothing installs for the slot
        # until the measurement the critics named returns (the U11 design's no-selection outcome: neither arm, with the
        # layer's function left to the clients' built-in tools).
        theirs = names[g_fam["default_key"]]
        row["split"] = True
        row["split_between"] = [
            {"family": "claude", "name": fin["name"], "repository": fin.get("repository", ""),
             "install_command": d1["default"]["install_command"], "install_source": d1["default"]["install_source"]},
            {"family": "gpt", "name": theirs["name"], "repository": theirs.get("repository", ""),
             "install_command": g_decs[0]["default"]["install_command"], "install_source": g_decs[0]["default"]["install_source"]}]
        row["default"] = {"name": "Not installed until the deciding measurement returns (the families split between "
                                  + fin["name"] + " and " + theirs["name"] + ")",
                          "repository": "", "installs_nothing_extra": True, "install_command": "", "install_source": ""}
        row["label"] = "split between the model families; the measurement the critics named decides, before the clean install"
        row["split_note"] = ("the Claude family converged on " + fin["name"] + " and the GPT family converged on " + theirs["name"]
                             + "; until the measurement returns nothing is installed for this slot and the clients' built-in tools cover it")
        row["deciding_measurement"] = {"claude_critic": c_crit["overturn_check"], "gpt_critic": g_crit["overturn_check"]}
    return row


def first_round_slot(layer, pick):
    lay = SEL[layer]
    return {
        "slot_id": slug(pick["name"])[:48], "row_kind": "first_round", "definitive": False,
        "default": {"name": pick["name"], "repository": pick["repository"], "installs_nothing_extra": False,
                    "install_command": pick["install_command"], "install_source": pick["install_source"]},
        "role": pick["role"],
        "label": "first-round pick: one blind judge, critic verdict " + lay["critic_verdict"]
                 + ("; the judge flagged a close call" if lay["judge_close_call"] else ""),
        "overturn_check": lay["deciding_comparison"],
        "families": {"claude": {"round": 1, "run": selection["run"]["workflow_run"], "method": "one judge plus one critic per group of layers",
                                "critic_verdict": lay["critic_verdict"], "status": "returned"},
                     "gpt": {"round": 1, "status": "pending: the blind GPT-6.1 Sol run over the 21 first-round packets is in progress"}},
    }


layers = []
for own in ownership["layers"]:
    lid = own["layer_id"]
    lay = SEL[lid]
    skip = NOT_A_SLOT_HERE.get(lid, [])
    slots = [first_round_slot(lid, p) for p in lay["selection"] if not any(s.lower() in p["name"].lower() for s in skip)]
    for slot, owner in SLOT_LAYER.items():
        if owner == lid:
            slots.append(decided_slot(slot))
    if lid == "git-github-automation":
        slots.append({"slot_id": "agent-structural-diff", "row_kind": "first_round", "definitive": False,
                      "default": {"name": "Not installed: git diff and difftastic cover diffs", "repository": "", "installs_nothing_extra": True,
                                  "install_command": "", "install_source": ""},
                      "label": "no-install default: the first round kept sem only if a comparison shows a gain",
                      "alternatives": [{"name": "sem (Ataraxy-Labs/sem)", "reason": "Its only evidence is a vendor benchmark against raw git diff, never against "
                                        "difftastic, and a Linux test suite in its CI is not established."}],
                      "overturn_check": lay["deciding_comparison"],
                      "families": {"claude": {"round": 1, "run": selection["run"]["workflow_run"], "critic_verdict": lay["critic_verdict"], "status": "returned"},
                                   "gpt": {"round": 1, "status": "pending: the blind GPT-6.1 Sol run over the 21 first-round packets is in progress"}}})
    if lid == "cross:wsl-distro":
        fb = [p for p in lay["selection"] if "24.04.5" in p["name"]]
        for s in slots:
            if "26-04" in s["slot_id"]:
                s["slot_id"] = "base-distribution"
                s["alternatives"] = [{"name": p["name"], "reason": "the fallback when 26.04.1 fails the rehearsal"} for p in fb]
    owns = [s["default"]["name"] for s in slots if not s["default"]["installs_nothing_extra"]]
    layers.append({"layer_id": lid, "owns": owns, "uses": own["uses"], "slots": slots,
                   "fact_corrections_first_round": lay.get("fact_corrections", [])})

CROSS = [
    {"layer_id": "cross:gpt6-harnesses", "owns": ["OmniRoute (the GPT gateway)"],
     "uses": ["Codex (native-clients)", "Codex SDK (agent-sdks)"],
     "slots": [{"slot_id": "gpt-gateway", "row_kind": "pinned", "definitive": False,
                "default": {"name": "OmniRoute", "repository": "https://github.com/diegosouzapw/OmniRoute", "installs_nothing_extra": False,
                            "install_command": "", "install_source": "pinned by the install profile; a fresh keyed gateway on the new distribution"},
                "label": "pinned by the user's directive: the GPT lane runs GPT-6.1 Sol through the gateway",
                "status_notes": ["never judged blind; its candidate field holds two members",
                                 "the gateway's cached provider limits read 0 remaining on all six accounts at the 2026-10-01T20:59Z sync",
                                 "no committed gateway configuration names a GPT-6.1 Sol model id; the last gateway canary returned HTTP 429, cause unknown"],
                "overturn_check": "a blind round over a full candidate field for the gateway role, then the same decision round"}]},
    {"layer_id": "cross:runtime-workers", "owns": ["OpenHands software-agent-sdk", "GPT Researcher", "DeerFlow"],
     "uses": ["OmniRoute (cross:gpt6-harnesses)", "the container engine (hosting-services)", "Harbor and Inspect AI (quality-evaluation) for graded tasks"],
     "slots": [
         {"slot_id": "agent-runtime-worker", "row_kind": "pinned", "definitive": False,
          "default": {"name": "OpenHands software-agent-sdk", "repository": "https://github.com/OpenHands/software-agent-sdk",
                      "installs_nothing_extra": False, "install_command": "", "install_source": "pinned by the install profile"},
          "label": "named by the user's directive of 2026-10-01; the source host's selection of record",
          "status_notes": ["never judged blind", "no run on GPT-6.1 Sol through the gateway is on record",
                           "the recipe on pull request 535 rejects the Sol model id; a bounded repair is requested there"],
          "overturn_check": "a blind round over the runtime-worker field, then the same decision round"},
         {"slot_id": "research-harnesses", "row_kind": "pinned", "definitive": False,
          "default": {"name": "GPT Researcher and DeerFlow, kept as two independent evidence gatherers", "repository":
                      "https://github.com/assafelovic/gpt-researcher ; https://github.com/bytedance/deer-flow", "installs_nothing_extra": False,
                      "install_command": "", "install_source": "pinned by the install profile"},
          "label": "both named by the user's directive of 2026-10-01 for the evaluation work",
          "status_notes": ["two tools for one job is deliberate here: each gathers evidence with its own retrieval stack, as the two model families do for judgment",
                           "never judged blind; no model run of either is on record on this host", "the recipes on pull request 535 reject the Sol model id",
                           "upstream's default retriever for GPT Researcher is a keyed search service; the project's rule prefers a free retriever"],
          "overturn_check": "if one general-purpose research worker must be the single default, a blind round over the research-harness field decides it"}]},
    {"layer_id": "cross:credential-practice", "owns": ["the command and secret-path guard (this repository)"],
     "uses": ["betterleaks and trufflehog (secrets-credentials)"],
     "slots": [{"slot_id": "credential-guard", "row_kind": "project_practice", "definitive": False,
                "default": {"name": "Command and secret-path guard (K4)", "repository": "https://github.com/seathatflowsinourveins/native-agent-stack",
                            "installs_nothing_extra": False, "install_command": "", "install_source": "this repository's adoption profile"},
                "label": "the project's own practice, not a third-party repository; settled by its closure record, not by a blind round",
                "overturn_check": "the canary end-to-end run on the new distribution"}]},
    {"layer_id": "cross:convergence-practice", "owns": ["the convergence practice and its validators (this repository)"], "uses": [],
     "slots": [{"slot_id": "convergence-validators", "row_kind": "project_practice", "definitive": False,
                "default": {"name": "Convergence practice and its validators", "repository": "https://github.com/seathatflowsinourveins/native-agent-stack",
                            "installs_nothing_extra": False, "install_command": "", "install_source": "this repository"},
                "label": "the project's own practice, not a third-party repository; settled by its closure record",
                "overturn_check": "a validator defect found by an independent review"}]},
]

judged = [s for l in layers for s in l["slots"] if s["row_kind"] == "judged"]
doc = {
    "schema_version": 1, "kind": "layer-ownership-with-definitive-defaults", "catalog": "foundation", "date_utc": "2026-10-01",
    "owner": "foundation lane (sota-default-harness-setup)",
    "rule": ownership["rule"],
    "decision_rule": prereg["decision_rule"],
    "no_install_rule": "an option that installs nothing extra is the default unless measured evidence shows a challenger's gain on the requirement's own metric with an interval that excludes zero",
    "definitive_now": sorted(s["slot_id"] for s in judged if s["definitive"]),
    "not_definitive_judged": sorted(s["slot_id"] for s in judged if not s["definitive"]),
    "not_claimed": "no candidate is installed or measured by these rounds; a default decided on documented fit says so; a definitive default is the slot's "
                   "install decision, not a merit acceptance: the full-field re-vote, the measured comparison and new-host acceptance stay separate",
    "row_kinds": {"judged": "decided blind in the decision round: two deciders per family in seeded orders, then one critic per family",
                  "first_round": "the first blind round's pick (one judge, one critic); stays the default until the second family's first-round verdict returns",
                  "pinned": "named by the user; carried as a requirement and not judged",
                  "project_practice": "the project's own code or practice; settled by its closure record"},
    "sources": {"first_round_selection_sha256": sha(SEL_DIR / "selection.json"), "ownership_sha256": sha(SEL_DIR / "ownership.json"),
                "decision_round_preregistration_sha256": sha(DEC / "preregistration.json"),
                "claude_returns_sha256": sha(DEC / "claude-returns.json"),
                "gpt_returns_sha256": {p.name: sha(p) for p in sorted((DEC / "gpt").glob("*.order-*.json")) + sorted((DEC / "gpt").glob("*.critic.json"))
                                       if p.stat().st_size}},
    "path_placeholder": PLACEHOLDER + " is the decision round's private directory (packets, returns, preregistration)",
    "layers": layers, "cross_rows": CROSS,
    "comparison_order_superseded": "the decision round replaces the install-the-arms order; measurements that back or overturn a default run on the "
                                   "workstation or on a rehearsal distribution, never on the clean WSL",
}
doc = scrub(doc)
text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
assert "/home/" not in text and "/tmp/claude-" not in text, "host path left in the document"
assert not re.search(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", text), "a session identifier is left in the document"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "foundation-definitive.json").write_text(text, encoding="utf-8")


def compact_slot(s):
    keep = {k: s[k] for k in ("slot_id", "row_kind", "definitive", "default", "label", "overturn_check") if k in s}
    for k in ("question", "role", "decided_on", "could_not_separate", "split_note", "status_notes", "qualifications_from_independent_fact_read",
              "families_agree_so_far", "split", "split_between", "deciding_measurement", "blind_round_pick",
              "decided_by_measurement_at_user_request", "blind_round_overturn_check"):
        if k in s:
            keep[k] = s[k]
    if "alternatives" in s:
        keep["alternatives"] = [{"name": a["name"], "reason": a["reason"][:400]} for a in s["alternatives"]]
    if "evidence" in s:
        keep["evidence"] = s["evidence"]
    if "critic_findings" in s:
        keep["critic_findings"] = s["critic_findings"]
    if "overturn_check_gpt" in s:
        keep["overturn_check_gpt"] = s["overturn_check_gpt"]
    if "corrections_by_critics" in s:
        keep["corrections_by_critics"] = s["corrections_by_critics"]
    if "families" in s:
        keep["families"] = {f: {k: v for k, v in d.items() if k in ("round", "run", "status", "critic_verdict", "decider_defaults", "default_key")}
                            for f, d in s["families"].items()}
    return keep


compact = {k: v for k, v in doc.items() if k not in ("layers", "cross_rows")}
compact["kind"] = "layer-ownership-with-definitive-defaults (compact view of foundation-definitive.json)"
compact["full_document_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
compact["layers"] = [{"layer_id": l["layer_id"], "owns": l["owns"], "uses": l["uses"], "slots": [compact_slot(s) for s in l["slots"]],
                      "fact_corrections_first_round": l["fact_corrections_first_round"]} for l in doc["layers"]]
compact["cross_rows"] = [{"layer_id": l["layer_id"], "owns": l["owns"], "uses": l["uses"], "slots": [compact_slot(s) for s in l["slots"]]}
                         for l in doc["cross_rows"]]
ctext = json.dumps(compact, ensure_ascii=False, indent=1) + "\n"
(OUT / "foundation-definitive.compact.json").write_text(ctext, encoding="utf-8")
print("layers", len(layers), "| cross rows", len(CROSS), "| slots", sum(len(l["slots"]) for l in layers) + sum(len(l["slots"]) for l in CROSS))
print("definitive now:", doc["definitive_now"], "| judged not definitive:", doc["not_definitive_judged"])
print("full", len(text.encode("utf-8")), "bytes sha256", compact["full_document_sha256"])
print("compact", len(ctext.encode("utf-8")), "bytes sha256", hashlib.sha256(ctext.encode("utf-8")).hexdigest())
