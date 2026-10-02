#!/usr/bin/env python3
"""Build the frozen units of the clean-room definitive round from the records it continues.

Inputs (read-only): the open foundation slots of the new-WSL definitive defaults (#591,
``evidence/artifacts/new-wsl-definitive-defaults-20261001/foundation-definitive.compact.json``) and the frozen candidate
field of the blind clean-install selection (#589, ``evidence/artifacts/new-wsl-clean-install-selection-20261001/packets``).
A slot is open when it is neither definitive nor a project practice, and its first-round default was not folded
definitive by the GPT first-round verdicts (the six FOLDED slots).

Output: ``units.json``, one unit per layer, each with the layer's requirement, target hosts and the deciding
measurement the packet names; its open slots, each asked as a neutral function question (QUESTIONS, written for this
round so that no slot is named after a tool); and the layer's field of candidates, keyed F01..Fnn in a seeded order,
with the repository each one resolves to. Prior picks, labels and first-round notes are deliberately left out: the
judges see the requirement, the questions, the field and the dossiers only. ``contenders.json`` lists every distinct
candidate across the units for the deep dives.

Usage: python3 build_units.py [--check]
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULTS = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/foundation-definitive.compact.json"
PACKETS = ROOT / "evidence/artifacts/new-wsl-clean-install-selection-20261001/packets"
SEED = "new-wsl-definitive-round-20261002"
FOLDED = {"claude-code", "codex", "claude-agent-sdk", "codex-sdk-and-codex-exec-app-server", "mcporter", "mcp-inspector"}

# The #591 slot -> (neutral slot id, question, whether "no additional component" is an allowed answer).
QUESTIONS = {
    "trail-of-bits-security-skills-trailofbits-skills": (
        "task-scoped-skill-pack",
        "Which single third-party skills collection supplies task-scoped engineering and security procedures that "
        "Claude Code and Codex load per task (not the whole catalog), or none?", True),
    "sandbox-runtime-srt": (
        "enforced-command-boundary",
        "Which single tool is the default enforced boundary for agent commands that need restrictions: OS-level "
        "filesystem read and write rules and deny-by-default network, on Linux under WSL2 (and macOS)?", True),
    "serena": (
        "language-server-navigation",
        "Which single tool gives both clients exact symbol definitions, references and symbol-level edits from "
        "language servers (for example over MCP)?", False),
    "claude-plugins-official-code-intelligence-lsp-pl": (
        "client-native-lsp",
        "Which single integration adds native language-server navigation and post-edit diagnostics inside Claude "
        "Code itself, or none beyond the language-server navigation slot?", True),
    "code-search": (
        "semantic-code-search",
        "Which single system provides semantic code search over the project repositories (an embedding index and its "
        "queries) for both clients, or none?", True),
    "tobi-qmd": (
        "markdown-collection-retrieval",
        "Which single tool searches controlled Markdown collections (lexical, vector or hybrid) and reads the original "
        "bodies back, for both clients?", False),
    "mineru": (
        "document-ingestion",
        "Which single tool converts difficult-layout documents (PDF, scans, Office formats, EPUB, HTML) into Markdown "
        "or JSON for ingestion, or none?", True),
    "trafilatura": (
        "page-text-extraction",
        "Which single tool fetches chosen URLs and extracts the main text with metadata (CLI or API) for bounded, "
        "attributable retrieval, or none?", True),
    "playwright-cli": (
        "browser-interaction",
        "Which single tool gives agents bounded interaction with JavaScript-rendered pages (forms, sign-in flows, "
        "tabs, screenshots, PDF) as shell-callable steps?", False),
    "memory-owner": (
        "memory-owner",
        "Which single system owns durable memory for both Claude Code and Codex on the new host? Exactly one is "
        "installed.", False),
    "ccusage": (
        "usage-meter",
        "Which single tool measures provider usage from the local logs Claude Code and Codex write (input, output, "
        "cache-creation and cache-read tokens), or none?", True),
    "otel-collector-contrib": (
        "telemetry-ingest",
        "Which single collector is the local OTLP ingestion point and privacy filter for Claude Code and Codex "
        "telemetry?", False),
    "prometheus": (
        "metrics-store",
        "Which single store keeps the native usage metrics received over OTLP for local queries, or none?", True),
    "loki": (
        "events-store",
        "Which single store keeps the native events and logs received over OTLP for local queries, or none?", True),
    "grafana": (
        "dashboards",
        "Which single tool provides local dashboards and exploration over the metrics and events stores, or none?",
        True),
    "phoenix": (
        "route-qualification",
        "Which single tool stores traces, datasets and experiments to qualify model routes by replaying a fixed "
        "workload, or none?", True),
    "local-model-server": (
        "local-model-server",
        "Which single local model server provides optional local inference on the RTX 4090 host, or none?", True),
    "inspect-ai": (
        "labeled-evaluation",
        "Which single framework runs labeled-case evaluations with several scorers whose values are kept per "
        "sample?", False),
    "harbor-containerized-agent-e2e-runner": (
        "containerized-agent-e2e",
        "Which single runner executes containerized end-to-end task suites for the real Claude Code and Codex CLIs, "
        "each trial graded by a verifier?", False),
    "promptfoo": (
        "ci-regression-gate",
        "Which single tool is the declarative CI regression gate for prompts, skills and agents, or none?", True),
    "zizmor": (
        "workflow-policy-audit",
        "Which single tool audits GitHub Actions workflows for permission and pinning policy?", False),
    "attest": (
        "build-provenance",
        "Which single mechanism produces signed build-provenance or SBOM attestations for hosted outputs?", False),
    "syft": (
        "sbom-generation",
        "Which single tool generates SBOMs (CycloneDX or SPDX) for container images and directories?", False),
    "dependabot": (
        "dependency-updates",
        "Which single tool keeps pinned dependencies, including action references, current through pull requests?",
        False),
    "codeql-sarif": (
        "findings-publication",
        "Which single mechanism publishes static-analysis findings as code-scanning alerts tied to commit and tool, "
        "or none?", True),
    "actionlint-kjanat": (
        "workflow-correctness-lint",
        "Which single linter checks workflow syntax, expressions, action inputs and outputs, and run: scripts?",
        False),
    "dagu": (
        "workflow-engine",
        "Which single local workflow engine runs scheduled DAGs over existing commands with run history, retries and "
        "a UI, or none beyond the init system's timers?", True),
    "docker-compose": (
        "multi-service-definition",
        "Which single tool defines and runs a multi-service application (the app plus supporting services, volumes "
        "and networks) on the container engine?", False),
    "betterleaks": (
        "secret-scanner",
        "Which single tool is the main local and CI secret scanner (staged changes before each commit, history, "
        "directories)?", False),
    "trufflehog": (
        "credential-verification",
        "Which single tool complements the secret scanner by verifying found credentials against provider APIs, or "
        "none?", True),
    "git": (
        "version-control",
        "Which single version control system is the base, with native worktrees and diffs?", False),
    "gh-github-cli": (
        "github-cli",
        "Which single tool lets agents automate GitHub from the host (pull requests, checks, reviews, API)?", False),
    "worktrunk": (
        "worktree-manager",
        "Which single tool manages worktrees for agents working in parallel (create, list with CI status, merge, "
        "clean up), or none beyond native git?", True),
    "difftastic": (
        "review-structural-diff",
        "Which single tool gives structural, syntax-aware diffs for human review, or none?", True),
    "claude-code-action": (
        "github-side-agent-review",
        "Which single automation runs agent pull-request review and mention-triggered tasks on the GitHub side, or "
        "none?", True),
    "agent-structural-diff": (
        "agent-structural-diff",
        "Which single tool gives agents entity-level structural diffs, or none (line diffs suffice)?", True),
    "mise": (
        "toolchain-reproduction",
        "Which single tool installs the pinned language runtimes and CLI tools from a committed manifest on Linux "
        "x86_64 and macOS arm64?", False),
    "restic": (
        "state-backup",
        "Which single tool makes encrypted, deduplicated, verifiable backups of application state and restores "
        "them?", False),
    "chezmoi": (
        "dotfiles-reproduction",
        "Which single tool reproduces configuration and dotfiles while keeping credentials out of the transferred "
        "state, or none?", True),
    "base-distribution": (
        "base-distribution",
        "Which single base distribution image is installed on the new WSL2 host?", False),
    "gpt-gateway": (
        "gpt-gateway",
        "Which single gateway routes GPT-6-family calls from Codex and SDK workers (account pooling, routing, usage "
        "observation, request compression off unless chosen), or none (the native clients call the provider "
        "directly)?", True),
    "agent-runtime-worker": (
        "agent-runtime-worker",
        "Which single runtime worker runs autonomous coding and research tasks in an isolated sandbox, driven by "
        "GPT-6.1 Sol through its harness SDK, or none (the native clients' own workers suffice)?", True),
    "research-harnesses": (
        "deep-research-harness",
        "Which single deep-research harness gathers cited evidence for evaluation work, or none?", True),
}

# Repositories for packet candidates the frozen packets name without a GitHub URL (verified with gh api, 2026-10-02).
URL_FIXES = {
    "Trail of Bits skills": "https://github.com/trailofbits/skills",
    "Vercel agent-skills": "https://github.com/vercel-labs/agent-skills",
    "Anthropic skills (webapp-testing)": "https://github.com/anthropics/skills",
    "Anthropic webapp-testing skill": "https://github.com/anthropics/skills",
    "Glean": "https://github.com/facebookincubator/Glean",
    "trufflehog": "https://github.com/trufflesecurity/trufflehog",
    "openai/codex-plugin-cc 1.0.6": "https://github.com/openai/codex-plugin-cc",
    "native git worktree and git diff --no-index": "https://github.com/git/git",
    "nvidia/Nemotron-3-Embed-1B-BF16 (embedding model)": "https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16",
    "scip, zoekt and universal-ctags": "https://github.com/scip-code/scip",
    "Context Mode as an always-on default": "https://github.com/mksglu/context-mode",
}
EXTRA_REPOS = {"scip, zoekt and universal-ctags": ["https://github.com/sourcegraph/zoekt",
                                                   "https://github.com/universal-ctags/ctags"]}

# Candidates added to a unit's field, beyond its frozen packet.
ADDITIONS = {
    "observation-inference": [
        {"name": "ollama", "repository": "https://github.com/ollama/ollama",
         "source": "the local-model-server split of #591 named it; it is in the semantic-rag packet"}],
}

# Measurements on record that the frozen packets do not already carry, with their sources.
RECORDED = {
    "durable-memory": [
        "LongMemEval-S, session-level retrieval, 470 questions, recall_all@5, on a Mac (descriptive), with the embedder "
        "matched (all-MiniLM-L6-v2): agentmemory 0.821; ai-memory 0.496; ai-memory full-text only 0.400; dense "
        "retrieval 0.753; plain BM25 0.747. ai-memory's production configuration with its LLM reranker did not run "
        "(evidence/artifacts/memory-stack-20260925/convergence.json, neutral_measurements)."],
}

# The two cross rows have no frozen packet; their units are written for this round from the records named here.
RUNTIME_UNITS = [
    {
        "layer_id": "cross:gpt6-harnesses",
        "title": "GPT-6 harnesses: the gateway",
        "requirement": ("Route the GPT-6 family (the Codex CLI lane, the Codex SDK and other OpenAI-compatible workers) "
                        "through one local gateway that pools native accounts, preserves the requested model and "
                        "reasoning effort, records usage and leaves request compression off unless chosen; or call "
                        "the provider natively."),
        "a_deciding_comparison_would_measure": ("Run a fixed Codex task set through each arm and directly: requested "
                                                "versus upstream model and effort, success, latency, account failover "
                                                "on a 429, usage recorded once."),
        "sources": "catalogs/foundation/new-wsl-architecture-20261001.json (cross:gpt6-harnesses); the gateway "
                   "alternatives the final-catalog completeness critic found on record (docs/decisions/"
                   "2026-10-01-final-catalog.md, gap 5)",
        "field": [
            {"name": "OmniRoute", "repository": "https://github.com/diegosouzapw/OmniRoute"},
            {"name": "LiteLLM", "repository": "https://github.com/BerriAI/litellm"},
            {"name": "claude-code-router", "repository": "https://github.com/musistudio/claude-code-router"},
            {"name": "agentgateway", "repository": "https://github.com/agentgateway/agentgateway"},
            {"name": "Portkey AI Gateway", "repository": "https://github.com/Portkey-AI/gateway"},
            {"name": "Bifrost", "repository": "https://github.com/maximhq/bifrost"},
        ],
    },
    {
        "layer_id": "cross:runtime-workers",
        "title": "Runtime workers",
        "requirement": ("Run autonomous coding, planning and research tasks as isolated, resumable workers driven by "
                        "GPT-6.1 Sol (and Claude where needed) through a supported harness SDK, with sandboxing, "
                        "persistence and bounded tool access; and gather cited research evidence for evaluation "
                        "work."),
        "a_deciding_comparison_would_measure": ("Run a frozen task subset (Terminal-Bench or SWE-bench style, plus "
                                                "research questions with citation checks) through each arm with the "
                                                "same model and effort: resolution, citation precision, resume after "
                                                "a kill, isolation, complete usage."),
        "sources": "catalogs/foundation/new-wsl-architecture-20261001.json (cross:runtime-workers); the runtime "
                   "roster of PR #535 (blueprints/runtime-workers/README.md on codex/runtime-qualification-20260930); "
                   "the agent-sdks and workers packets of #589",
        "field": [
            {"name": "OpenHands software-agent-sdk", "repository": "https://github.com/OpenHands/software-agent-sdk"},
            {"name": "Codex SDK and codex exec", "repository": "https://github.com/openai/codex"},
            {"name": "Claude Agent SDK", "repository": "https://github.com/anthropics/claude-agent-sdk-python"},
            {"name": "OpenAI Agents SDK", "repository": "https://github.com/openai/openai-agents-python"},
            {"name": "Deep Agents", "repository": "https://github.com/langchain-ai/deepagents"},
            {"name": "Microsoft Agent Framework", "repository": "https://github.com/microsoft/agent-framework"},
            {"name": "LangGraph", "repository": "https://github.com/langchain-ai/langgraph"},
            {"name": "mini-swe-agent", "repository": "https://github.com/SWE-agent/mini-swe-agent"},
            {"name": "GPT Researcher", "repository": "https://github.com/assafelovic/gpt-researcher"},
            {"name": "DeerFlow", "repository": "https://github.com/bytedance/deer-flow"},
            {"name": "OpenResearch", "repository": "https://github.com/alphaXiv/OpenResearch"},
        ],
    },
]
GH = re.compile(r"^https?://github\.com/([^/\s#?]+)/([^/\s#?]+)", re.IGNORECASE)


def repo_key(url: str) -> str | None:
    m = GH.match(url or "")
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2).removesuffix('.git')}".lower()


GH_ROOT = re.compile(r"^https?://github\.com/[^/\s#?]+/[^/\s#?]+/?$", re.IGNORECASE)


def contender_id(name: str, url: str) -> str:
    """A candidate is its GitHub repository when its URL is a repository root; otherwise (a distribution image, a
    model page, a file inside another project's repository) it is its own name."""
    if GH_ROOT.match(url or ""):
        return repo_key(url)
    return "page:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def seeded(items: list, label: str) -> list:
    rnd = random.Random(hashlib.sha256(f"{SEED}:{label}".encode()).hexdigest())
    out = list(items)
    rnd.shuffle(out)
    return out


def field_from_packet(layer_id: str) -> tuple[dict, list]:
    packet = json.loads((PACKETS / (layer_id.replace(":", "_") + ".json")).read_text(encoding="utf-8"))
    seen, field = set(), []
    for c in packet["candidates"]:
        url = c.get("repository") or URL_FIXES.get(c["name"], "")
        cid = contender_id(c["name"], url)
        if cid in seen:
            continue
        seen.add(cid)
        field.append({"name": c["name"], "repository": url, "contender": cid,
                      "extra_repositories": EXTRA_REPOS.get(c["name"], []), "source": f"#589 packet {c['key']}"})
    for add in ADDITIONS.get(layer_id, []):
        cid = contender_id(add["name"], add["repository"])
        if cid not in seen:
            seen.add(cid)
            field.append({"name": add["name"], "repository": add["repository"], "contender": cid,
                          "extra_repositories": [], "source": add["source"]})
    return packet, field


def build() -> tuple[dict, dict]:
    defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    open_slots: dict[str, list] = {}
    for layer in defaults["layers"] + list(defaults.get("cross_rows") or []):
        for slot in layer.get("slots", []):
            if slot.get("definitive") or slot.get("row_kind") == "project_practice" or slot["slot_id"] in FOLDED:
                continue
            open_slots.setdefault(layer["layer_id"], []).append(slot["slot_id"])
    missing = sorted(s for slots in open_slots.values() for s in slots if s not in QUESTIONS)
    if missing:
        raise SystemExit(f"open slots without a neutral question: {missing}")
    units, contenders = [], {}
    runtime = {u["layer_id"]: u for u in RUNTIME_UNITS}
    for layer_id, slot_ids in open_slots.items():
        if layer_id in runtime:
            spec = runtime[layer_id]
            packet = {"title": spec["title"], "requirement": spec["requirement"],
                      "a_deciding_comparison_would_measure": spec["a_deciding_comparison_would_measure"],
                      "target_hosts": None}
            field = [{"name": f["name"], "repository": f["repository"],
                      "contender": contender_id(f["name"], f["repository"]), "extra_repositories": [],
                      "source": "written for this round"} for f in spec["field"]]
        else:
            packet, field = field_from_packet(layer_id)
        ordered = seeded(field, layer_id)
        for i, entry in enumerate(ordered, 1):
            entry["key"] = f"F{i:02d}"
        unit = {
            "unit_id": layer_id,
            "title": packet["title"],
            "requirement": packet["requirement"],
            "target_hosts": packet.get("target_hosts") or (
                "Primary: a new WSL2 Ubuntu-family instance on a Windows workstation, x86_64, 48 cores, 104 GB RAM, "
                "NVIDIA RTX 4090 24 GB. Secondary: macOS arm64 laptops. Users: Claude Code and Codex agent sessions "
                "on that host."),
            "a_deciding_comparison_would_measure": packet.get("a_deciding_comparison_would_measure"),
            "comparisons_on_record": list(packet.get("comparisons_on_record_where_every_named_arm_ran") or [])
            + RECORDED.get(layer_id, []),
            "slots": [{"slot_id": QUESTIONS[s][0], "source_slot": s, "question": QUESTIONS[s][1],
                       "no_additional_component_allowed": QUESTIONS[s][2]} for s in slot_ids],
            "field": [{k: e[k] for k in ("key", "name", "repository", "extra_repositories", "contender")}
                      for e in ordered],
            "field_sources": sorted({e["source"] for e in ordered}),
        }
        if layer_id in runtime:
            unit["sources"] = runtime[layer_id]["sources"]
        units.append(unit)
        for e in ordered:
            c = contenders.setdefault(e["contender"], {"contender": e["contender"], "name": e["name"],
                                                       "repository": e["repository"],
                                                       "extra_repositories": e["extra_repositories"], "units": []})
            c["units"].append(layer_id)
    units.sort(key=lambda u: u["unit_id"])
    return ({"schema_version": 1, "kind": "definitive_round_units", "seed": SEED,
             "inputs": {str(DEFAULTS.relative_to(ROOT)): hashlib.sha256(DEFAULTS.read_bytes()).hexdigest()},
             "units": units},
            {"schema_version": 1, "kind": "definitive_round_contenders",
             "contenders": sorted(contenders.values(), key=lambda c: c["contender"])})


def main() -> int:
    units, contenders = build()
    outputs = {HERE / "units.json": units, HERE / "contenders.json": contenders}
    if "--check" in sys.argv[1:]:
        stale = [p.name for p, data in outputs.items()
                 if not p.is_file() or json.loads(p.read_text(encoding="utf-8")) != data]
        if stale:
            print("stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(json.dumps({"status": "passed"}))
        return 0
    for path, data in outputs.items():
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"units": len(units["units"]), "slots": sum(len(u["slots"]) for u in units["units"]),
                      "contenders": len(contenders["contenders"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
