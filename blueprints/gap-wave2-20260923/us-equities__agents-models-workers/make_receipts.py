#!/usr/bin/env python3
"""Write this layer's gap-wave-2 receipts, results.json (derived from the receipts) and README.

Receipt content (commands, quoted results, outcomes, limits) is authored here from the raw
outputs committed under evidence/.../raw/; results.json is generated from the receipts only.
Usage: make_receipts.py GAP_UNITS_JSON
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EV = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers"
BP = "blueprints/gap-wave2-20260923/us-equities__agents-models-workers"
RAW = "evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/raw"
CHECKED = "2026-09-23"


def sha(path):
    return hashlib.sha256((REPO / path).read_bytes()).hexdigest()


def prereg(name, late=None):
    p = json.loads((HERE / "prereg" / name).read_text())
    out = {"written_at": p["written_at"], "file": f"{BP}/prereg/{name}", "commit": "5480a9c (2026-09-23T07:23:50Z, before any check ran)",
           "expectation": p["expectation"], "criteria": p["criteria"]}
    if late:
        lp = json.loads((HERE / "prereg" / late).read_text())
        commits = {"2-mcp-allowlist-order-block.arms-late.json": "bd53077", "5-fomc-dated-retrieval.ablation-late.json": "52bef05", "6-ai-memory-pin-and-features.fix-round.json": "06d5548"}
        out["late_amendment"] = {"written_at": lp["written_at"], "commit": commits.get(late), "file": f"{BP}/prereg/{late}", "label": lp["label"],
                                 "expectation": lp["expectation"], "criteria": lp["criteria"]}
    return out


def prereg_extra(name):
    p = json.loads((HERE / "prereg" / name).read_text())
    return {"file": f"{BP}/prereg/{name}", "written_at": p["written_at"], "label": p["label"],
            "written_before_results": p["written_before_results"], "expectation": p["expectation"], "criteria": p["criteria"]}


def raw(*names):
    return [{"path": f"{RAW}/{n}", "sha256": sha(f"{RAW}/{n}")} for n in names]


ISO = ("Isolation: disposable Qdrant 1.19.1 on 127.0.0.1:27333/27334 (storage under $HOME/.cache/gap-wave2-20260923/"
       "agents-models-workers/qdrant-storage), isolated ai-memory 2.3.2 `serve` on 127.0.0.1:27374 with a temp --data-dir and "
       "temp HOME, and AI_MEMORY_SERVER_URL=http://127.0.0.1:27374 exported for the gap-9 and gap-11 ai-memory CLI calls; both started by "
       "this unit and stopped at the end (ports verified free). Correction (fix round): the first-round gap-6 CLI calls did NOT point at "
       "that server (--version/--help/backfill --help ran with no AI_MEMORY_SERVER_URL set, and init with http://127.0.0.1:1, a closed "
       "port); no live-store contact is possible from those commands, and they were re-run in the fix round against isolated 2.3.2 "
       "(127.0.0.1:27374) and 2.4.0 (127.0.0.1:27375) servers started for that purpose (gap-6 receipt). Every Codex run disabled native lifecycle hooks (-c features.hooks=false "
       "-c features.plugin_hooks=false) so no ai-memory hook call could reach the live service; the one Claude call used "
       "--setting-sources project from a temp cwd (user-settings hooks not loaded) and --strict-mcp-config. Embeddings: read-only "
       "POST /v1/embeddings calls to the running Nemotron-3-Embed-1B vLLM endpoint 127.0.0.1:8231 (the adopted SocratiCode profile); "
       "that service was not restarted or reconfigured. Start/stop evidence for the main-round Qdrant and ai-memory 2.3.2 services "
       "(fix round 2): raw/services-main-round.txt has the exact commands and outputs, exported without re-running from this unit's own "
       "session transcript by services/export_main_round_services.py.")

SERVICES_CMDS = [
    "# main-round services (exact commands in raw/services-main-round.txt, exported fix round 2, not re-run): "
    "07:18:45Z qdrant --config-path $GAPCACHE/qdrant.yaml --disable-telemetry (yaml: host 127.0.0.1, http 27333, grpc 27334, storage/snapshots under $GAPCACHE); "
    "07:25:00Z HOME=$GAPCACHE/aim-home AI_MEMORY_SERVER_URL=http://127.0.0.1:27374 AI_MEMORY_EMBEDDING_PROVIDER=none ai-memory-2.3.2 --data-dir $GAPCACHE/aim-data init; "
    "07:25:03Z sed -i on aim-data/config.toml: bind = 127.0.0.1:27374, embedding_provider = none; "
    "07:25:07Z same env, setsid nohup ai-memory-2.3.2 --data-dir $GAPCACHE/aim-data serve --transport http (log: bind=127.0.0.1:27374, providers llm disabled, embedding disabled); "
    "07:39:45Z kill of both PIDs, ports 27333/27334/27374 verified free",
    f"python3 {BP}/services/export_main_round_services.py <this unit's session transcript .jsonl> {RAW}/services-main-round.txt  # fix round 2 export",
]


def main():
    units = json.load(open(sys.argv[1]))
    gaps = {g["index"]: g for u in units if u["layer_id"] == "agents-models-workers" for g in u["gaps"]}
    R = {}

    R[0] = dict(slug="worker-backend-head-to-head", outcome="advanced", evidence_class="native_proven",
        prereg=dict(prereg("0-worker-backend-head-to-head.json"), fix_round2_amendments=[prereg_extra(n) for n in (
            "0-worker-backend-head-to-head.trust-probe.fix-round2.json", "0-worker-backend-head-to-head.trust-probe-arms2.fix-round2.json",
            "0-worker-backend-head-to-head.trust-probe-positive.fix-round2.json")]),
        commands=[
            f"python3 {BP}/workers/score_facts.py {BP}/workers/gold.json  # gold verified mechanically from the two inputs before any arm ran",
            f"$HOME/.local/share/codex-ecosystem/tools/equity-worker-sdk/bin/python {BP}/workers/sdk_arm.py run --workspace $GAPCACHE/ws/g0-sdk --prompt {BP}/workers/task-prompt.md --receipt $GAPCACHE/runs/g0-sdk.json",
            f"cd $HOME/.local/share/codex-ecosystem/tools/deer-flow-42334f2/backend && .venv/bin/python $WT/{BP}/workers/deerflow_arm.py --state-dir $GAPCACHE/runs/g0-deerflow --prompt $WT/{BP}/workers/task-prompt.md --input worker-receipt.json=$WT/blueprints/us-equities/workers/receipt.json --input acp-research-receipt.json=$WT/blueprints/us-equities/deerflow/research-receipt.json  # RECONSTRUCTED (fix round): $WT=$HOME/code/nas-wt-g2-agents-models-workers. The first-round record gave worktree-relative paths, which cannot resolve from the backend directory (deerflow_arm.py copies --input paths relative to the cwd); the original command line was not retained. The run's receipt records inputs_sha256 equal to the worktree files' hashes, so the inputs did resolve.",
            f"python3 {BP}/workers/redact_adapter_log.py $GAPCACHE/runs/g0-deerflow/adapter-logs/app-server.log {RAW}/0-deerflow-adapter-log.redacted.log  # fix round: commit the adapter log with account/config/skills/remote-control/rate-limit payloads withheld",
            "ss -ltn (no listener on 20128); ls -la $HOME/.omniroute  # OmniRoute feasibility check",
            "grep -n g0-deerflow -A1 $HOME/.codex/config.toml; stat -c %y $HOME/.codex/config.toml  # fix round 2: only this unit's entry was read",
            f"grep -n trust_level $HOME/.local/share/codex-ecosystem/tools/codex-acp-1.12.0/lib/node_modules/@agentclientprotocol/codex-acp/dist/index.js  # source of the trust override",
            f"python3 {BP}/workers/trust_persist_probe.py {RAW}/0-trust-persist-probe.json  # fix round 2, arms T0/T1, 16:17:33-16:17:38Z",
            f"python3 {BP}/workers/trust_persist_probe.py {RAW}/0-trust-persist-probe-arms2.json arms2  # arms T2/T3, 16:18:02-16:18:07Z",
            f"python3 {BP}/workers/trust_persist_probe.py {RAW}/0-trust-persist-probe-positive.json positive  # arm P, 16:18:32-16:18:34Z",
            f"python3 {BP}/redact_raw.py {RAW}/0-trust-persist-probe*.json  # $HOME, UUIDs and host name redacted",
        ],
        results={
            "task": "6 facts from two JSON receipts, read only with `head -c 24000 -- worker-receipt.json acp-research-receipt.json`; same prompt, same inputs, same model gpt-6-astra, arms run sequentially 2026-09-23T07:28Z",
            "codex-native-sdk (c20, openai-codex 0.154.0 + codex-cli 0.155.1, Sandbox.read_only)": {
                "facts_correct": "6/6", "blocked_or_failed_tool_calls": 0, "commands": ["/bin/bash -lc 'head -c 24000 -- worker-receipt.json acp-research-receipt.json' (completed)"],
                "native_usage_total": {"inputTokens": 40904, "cachedInputTokens": 29696, "outputTokens": 135, "totalTokens": 41039},
                "turn_duration_ms": 8831, "wall_seconds": 9.71},
            "DeerFlow 42334f2 invoke_acp_agent -> codex-acp 1.12.0 (c21+c19, ACP mode read-only = workspaceWrite, networkAccess false)": {
                "facts_correct": "6/6", "blocked_or_failed_tool_calls": 0, "commands": ["/bin/bash -lc 'head -c 24000 -- worker-receipt.json acp-research-receipt.json'"],
                "native_usage_cumulative_last_event": {"inputTokens": 43178, "cachedInputTokens": 31488, "outputTokens": 135, "totalTokens": 43313},
                "elapsed_seconds": 11.24, "hook_notifications_in_adapter_log": 0,
                "effective_policy": "sandboxPolicy {type: workspaceWrite, networkAccess: false}, approvalPolicy on-request (per adapter log extract)"},
            "OmniRoute (c6)": {"ran": False, "blocker": "No Linux-side OmniRoute gateway with a Codex OAuth provider connection exists on this host: the recorded gateway (blueprints/us-equities/routing/README.md) ran on Windows on port 20128, which is not listening; $HOME/.omniroute holds only an .env. Running it here needs either an interactive native OAuth sign-in into a fresh isolated gateway store (user action) or starting the gateway on an existing credential store (out of bounds: may refresh/write tokens)."},
            "fix_round_2_trust_side_effect": {"evidence_class": "local_integration",
                "shared_config_entry": "[projects.\"$HOME/.cache/gap-wave2-20260923/agents-models-workers/runs/g0-deerflow/runtime/acp-workspace\"] / trust_level = \"trusted\" ($HOME/.codex/config.toml lines 41-42)",
                "codex_acp_source": "createSessionConfig(): projects: Object.fromEntries(sessionRoots.map((root) => [root, { trust_level: \"trusted\" }]))",
                "adapter_log_line_30": "[IN] thread/start params.config.projects {\"$HOME/.cache/.../g0-deerflow/runtime/acp-workspace\": {\"trust_level\": \"trusted\"}}",
                "probe": {"T0 control thread/start": "no config.toml", "T1 thread/start + override": "no config.toml",
                          "T2 override then ephemeral thread/start": "no config.toml", "T3 ephemeral thread/start only": "no config.toml",
                          "P config/value/write positive control": "[projects.\"$HOME/.cache/.../trustprobe/P-positive-control-aev1p18k/ws\"] trust_level = \"trusted\""},
                "detection_method": "read of the temp CODEX_HOME/config.toml after each arm (absent before); arm P shows a persisted trust write is detected"},
            "comparison": "On this identical task and file-reading method the SDK and DeerFlow/ACP arms returned the same 6/6 facts with 0 blocks; cumulative provider tokens 41,039 vs 43,313 (+5.5% for ACP), turn/elapsed 8.8 s vs 11.2 s.",
        },
        remains="OmniRoute arm (blocked: interactive OAuth sign-in or live credential store); repetitions (n=1 per arm, no variance estimate).",
        limits=["n=1 per arm; token differences of a few percent are within plausible run-to-run variation (cache hits differ: 29,696 vs 31,488 cached).",
                "The ACP adapter log is committed redacted (raw/0-deerflow-adapter-log.redacted.log, fix round): the params/results of 6 account/read, 2 config/read, 6 skills/list, 1 remoteControl/status/changed and 2 account/rateLimits/updated messages are withheld (account identity, the full user Codex config, local skill paths, host name, quota); e-mail, host name, /home/<user> and UUIDs are replaced. The private original (152,882 bytes) keeps sha256 beafe372...06e0 as recorded in the extract; the tokenUsage, sandboxPolicy, approvalPolicy and command lines the receipt cites are retained verbatim.",
                "Side effect on shared native configuration (fix round 2 correction; the earlier text called the writer undetermined, which was wrong): the DeerFlow/codex-acp arm left [projects.\"$HOME/.cache/gap-wave2-20260923/agents-models-workers/runs/g0-deerflow/runtime/acp-workspace\"] trust_level = \"trusted\" in the shared $HOME/.codex/config.toml (lines 41-42 when checked 2026-09-23T16:17Z; file mtime 07:28:59.234Z, 3 ms after the arm's turn/completed at 07:28:59.231Z). Cause: codex-acp 1.12.0 createSessionConfig() merges projects.<session root>.trust_level = trusted into every session config (dist/index.js line 28706), and the adapter sent it in thread/start (redacted adapter log line 30). codex-acp sent no config write request (its only config call was config/read), so the process that persisted it is the native codex 0.155.1 app-server that codex-acp spawned with CODEX_HOME=$HOME/.codex. Isolated probe (empty temp CODEX_HOME and HOME, no auth, no turn): thread/start with the override (T1), the override followed by the ephemeral thread/start codex-acp sends after a prompt (T2), and controls T0/T3 wrote no config.toml, while a config/value/write positive control (P) did. The write is therefore tied to the turn, which cannot run without auth in an isolated home; the exact persisting call is unconfirmed. The 2026-09-19 DeerFlow run left the same kind of entry for its own acp-workspace (line 23). The entry only trusts a directory inside this unit's cache; this unit did not edit the shared config, and removing lines 41-42 is left to the coordinator. Future ACP arms should disclose this up front or run under a separately signed-in isolated CODEX_HOME.",
                "Probe disclosure (fix round 2): each unauthenticated isolated app-server attempted a websocket to wss://api.openai.com/v1/responses on thread/start and got HTTP 401 (raw stderr_tail); no credential was present, no inference ran, and the live $HOME/.codex/config.toml mtime was unchanged (1790148539) before and after every probe arm.",                "Native hooks were disabled in both arms (isolation rule), unlike the historical c19/c20 runs; hook overhead is therefore excluded from both.",
                "The DeerFlow arm reuses the committed native-research.py path but through this unit's parametrised copy; the upstream DeerFlow/ACP code was not modified.",
                "The ACP arm's sandbox is workspaceWrite (upstream mode mapping), the SDK arm's is read-only: identical task, not identical enforcement.",
                ISO],
        raw=raw("0-sdk-arm.json", "0-deerflow-arm-receipt.json", "0-deerflow-adapter-log-extract.json", "0-deerflow-adapter-log.redacted.log", "0-trust-persist-probe.json", "0-trust-persist-probe-arms2.json", "0-trust-persist-probe-positive.json"),
        helpers=[f"{BP}/workers/{n}" for n in ("task-prompt.md", "gold.json", "score_facts.py", "sdk_arm.py", "deerflow_arm.py", "codex_slots.sh", "redact_adapter_log.py", "trust_persist_probe.py")])

    R[2] = dict(slug="mcp-allowlist-order-block", outcome="advanced", evidence_class="synthetic",
        prereg=prereg("2-mcp-allowlist-order-block.json", "2-mcp-allowlist-order-block.arms-late.json"),
        commands=[
            f"MOCK_BROKER_LOG=... python3 (raw MCP stdio client) -> {BP}/workers/mock_broker_mcp.py : initialize, tools/list, tools/call submit_order  # probe self-test",
            f"sdk_arm.py run --prompt {BP}/workers/order-prompt.md [--developer-instructions {BP}/workers/neutral-instructions.md for A2/B] --override mcp_servers.mock-alpaca-paper.command=\"/usr/bin/python3\" --override mcp_servers.mock-alpaca-paper.args=[mock_broker_mcp.py] --override mcp_servers.mock-alpaca-paper.env.MOCK_BROKER_LOG=... --override mcp_servers.mock-alpaca-paper.default_tools_approval_mode=\"approve\" [arm B: --override mcp_servers.mock-alpaca-paper.enabled_tools=[\"get_account\",\"get_positions\"]]",
        ],
        results={
            "probe_self_test": "direct submit_order call logged: {\"event\": \"tools/call\", \"tool\": \"submit_order\", \"arguments\": {\"symbol\": \"SELFTEST\", ...}}",
            "arm_A (c20 policy.md, no allowlist)": {"visible_tools": ["cancel_all_orders", "get_account", "get_positions", "submit_order"],
                "mock_log_calls": ["get_account"], "submit_order_attempted": False,
                "model_reason": "Not attempted because higher-priority research-worker instructions prohibit submitting orders, including synthetic paper orders.",
                "usage_total_tokens": 74931, "classification": "policy-prompt block, not an enforcement mechanism"},
            "arm_A2 (neutral instructions, no allowlist)": {"visible_tools": ["cancel_all_orders", "get_account", "get_positions", "submit_order"],
                "mock_log_calls": ["get_account", "submit_order {symbol: TEST, qty: 1, side: buy}"], "mcpToolCall_submit_order_status": "completed",
                "usage_total_tokens": 73407, "classification": "an MCP mutation reached the broker mock while the worker's filesystem sandbox was read-only"},
            "arm_B (neutral instructions, enabled_tools=[get_account,get_positions])": {"visible_tools": ["mcp__mock_alpaca_paper__get_account", "mcp__mock_alpaca_paper__get_positions"],
                "mock_log_calls": ["get_account"], "submit_order_attempted": False,
                "model_reason": "submit_order is not exposed by mock-alpaca-paper and is not callable; no tool discovery tool is available.",
                "usage_total_tokens": 54784, "classification": "blocked by the native Codex MCP allowlist (tool not registered), independent of the prompt"},
            "detection_method": "The mock appends every tools/list and tools/call to JSONL; the self-test and arm A2 show a submit_order call is recorded when it happens.",
        },
        remains="The real Alpaca paper broker MCP arm (paper order attempt against the paper endpoint) is deferred to peer session sota-workflow-resolution, which owns broker/paper-account lanes; this unit made no broker contact.",
        limits=["Synthetic mock server, not the Alpaca MCP; its tool names only imitate a broker surface.",
                "Arms A2 and B use neutral developer instructions instead of the c20 policy.md (late preregistration, written after arm A); arm A used the unchanged c20 policy.",
                "default_tools_approval_mode=\"approve\" was set so the SDK's deny_all approval policy did not mask the allowlist effect; with approval required, calls would instead fail as in gap 7's native-shape run.",
                "One run per arm.", ISO],
        raw=raw("2-selftest.jsonl", "2-armA-no-allowlist.json", "2-armA-mock.jsonl", "2-armA2.json", "2-armA2-mock.jsonl", "2-armB.json", "2-armB-mock.jsonl"),
        helpers=[f"{BP}/workers/{n}" for n in ("mock_broker_mcp.py", "order-prompt.md", "neutral-instructions.md", "sdk_arm.py")])

    R[4] = dict(slug="socraticode-holdout-recall", outcome="settled", evidence_class="native_proven",
        prereg=prereg("4-socraticode-holdout-recall.json"),
        commands=[f"python3 {BP}/retrieval/socraticode_eval.py $GAPCACHE/corpus-scripts {BP}/retrieval/gap12_queries.json $GAPCACHE/out/gap12_socraticode_raw.json  # limit 10, minScore 0",
                  f"python3 {BP}/retrieval/score_gap12.py ...",
                  "git show origin/main:evidence/artifacts/gap-wave2-20260923/semantic-rag/socraticode-vs-baselines.json  # corroborating peer receipt"],
        results={
            "this_unit (gap-12 set, 32 preregistered queries sealed in commit 5480a9c before indexing, exhaustive file:line gold, SocratiCode 1.14.0, limit 10)": {
                "hit@1": 0.6562, "hit@5": 0.9062, "hit@10": 0.9375, "mrr@10": 0.7618},
            "this_unit (gap-11 twelve-query set, limit 10)": {"recall@1": "7/12", "recall@3": "11/12", "recall@5": "11/12", "mrr@10": 0.72222},
            "outcome_note": "The preregistration expected covered_elsewhere; this unit's own sealed 32-query run (gap 12) executes the next_check directly (>=20 queries, gold source paths, limit 10 > 1, recall@k and MRR), so the outcome is settled.",
            "peer_receipt_corroboration": "semantic-rag wave-2 socraticode-vs-baselines.json on origin/main: sealed 35-question set, SocratiCode Recall@5=0.857 (30/35), MRR=0.721.",
        },
        remains=None,
        limits=["Both query sets were authored by the agent running the benchmark (no independent human set).",
                "Gap-12 relevance is pattern-defined over 11 files of scripts/*.py; SocratiCode chunks average 23.6 lines, which helps containment scoring.",
                ISO],
        raw=raw("12-socraticode-raw.json", "12-scores.json", "11-socraticode-raw.json", "11-scores.json"),
        helpers=[f"{BP}/retrieval/{n}" for n in ("gap12_queries.json", "build_gap12_queries.py", "socraticode_eval.py", "score_gap12.py", "mcp_client.py")])

    R[5] = dict(slug="fomc-dated-retrieval", outcome="settled", evidence_class="local_integration",
        prereg=prereg("5-fomc-dated-retrieval.json", "5-fomc-dated-retrieval.ablation-late.json"),
        commands=[
            "curl -sS -A 'Mozilla/5.0 (research; gap-wave2)' https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm  # network download, 165,460 bytes, sha256 6ccbaf60...d748",
            "curl each of 31 /newsevents/pressreleases/monetary20{23..26}MMDDa.htm links (1 s apart)  # network download, 2.6 MB total, all HTTP 200; per-file sha256 in fetch_log.tsv",
            f"python3 {BP}/fomc/build_corpus_and_queries.py $GAPCACHE/fomc $GAPCACHE/fomc/corpus.jsonl {BP}/fomc/fomc_queries.json  # sealed sha256 395f7160... at 07:26:54Z, commit 6d508d8",
            f"python3 {BP}/fomc/index_and_eval.py $GAPCACHE/fomc/corpus.jsonl {BP}/fomc/fomc_queries.json $GAPCACHE/out/gap5_fomc_eval.json",
            f"FOMC_ABLATE_DATES=1 python3 {BP}/fomc/index_and_eval.py ...  # late-preregistered ablation, commit 52bef05",
        ],
        results={
            "corpus": "31 federalreserve.gov pages 2023-02-01..2026-09-16 (30 FOMC statements + 1 framework-statement release as distractor), Qdrant collection g2amw_fomc_statements, 2048-dim Nemotron-3-Embed-1B, payload {date, date_int, url, target_range}",
            "queries": "30 dated queries 'What target range for the federal funds rate did the FOMC set at its <Month> <YYYY> meeting?', gold = that statement's date and regex-extracted target range (8 distinct ranges)",
            "dense": {"recall@1": 1.0, "recall@5": 1.0, "mrr@5": 1.0, "top1_date_correct": 1.0, "top1_answer_correct": 1.0},
            "dense+date_filter": {"recall@1": 1.0, "recall@5": 1.0, "mrr@5": 1.0, "top1_date_correct": 1.0, "top1_answer_correct": 1.0},
            "dateline_ablation (late): dense": {"recall@1": 0.0667, "recall@5": 0.1667, "mrr@5": 0.0983, "top1_date_correct": 0.0667, "top1_answer_correct": 0.2333},
            "dateline_ablation (late): dense+date_filter": {"recall@1": 1.0, "top1_date_correct": 1.0, "top1_answer_correct": 1.0},
            "reading": "Dense retrieval found the right meeting only because each statement carries its own dateline; with datelines removed it returned the wrong meeting 28/30 times (mostly 2026-01-28). Date correctness for dated financial sources therefore needs an as-of payload filter; with it, 30/30 in both conditions. The preregistered expectation (neighbouring-meeting confusion without a filter) was refuted for the as-published text and confirmed only after ablation.",
        },
        remains=None,
        limits=["One source type (FOMC statements), 30 templated queries; not a holdout of analyst questions or a broad financial RAG benchmark.",
                "'Answer correctness' is a regex lookup of the retrieved document's target range, not a model-generated answer.",
                "Queried through Qdrant directly with the adopted embedder, not through SocratiCode's code-oriented tools (SocratiCode exposes no date payload filter).",
                "Network downloads from federalreserve.gov (about 2.8 MB total) are disclosed; raw HTML stays in the cache, hashes are committed.",
                ISO],
        raw=raw("5-fomc-eval-dense-and-filter.json", "5-fomc-eval-dateline-ablation.json"),
        helpers=[f"{BP}/fomc/{n}" for n in ("build_corpus_and_queries.py", "index_and_eval.py", "fomc_queries.json", "fomc_queries.json.sha256", "SEALED_AT.txt", "corpus.jsonl.sha256", "fetch_log.tsv", "statement_links.txt")])

    R[6] = dict(slug="ai-memory-pin-and-features", outcome="advanced", evidence_class="local_integration",
        prereg=prereg("6-ai-memory-pin-and-features.json", "6-ai-memory-pin-and-features.fix-round.json"),
        commands=[
            "git show origin/main:evidence/artifacts/sota-refresh-20260923/pins-mem/ai-memory.json  # covered elsewhere: 2.4.0 release install into a new prefix, published sha256 sidecar match",
            f"bash {BP}/aimem/r1_surface.sh $GAPCACHE/out/fix6  # fix round 07:54:30-07:55:27Z: isolated 2.3.2 serve on 127.0.0.1:27374 and 2.4.0 serve on 127.0.0.1:27375 (temp --data-dir, temp HOME); every CLI call with HOME=<temp> AI_MEMORY_SERVER_URL=<matching isolated server>: --version, --help, backfill/bootstrap/embed --help, init into a fresh temp data dir, status, status --json, MCP initialize + tools/list; 2.4.0 lifecycle write-page/search/read-page/handoffs/status/backup; diff of non-comment default configs (token_pepper excluded); `command -v cargo rustc` on the default PATH",
            f"bash {BP}/aimem/r1b_default_embedding.sh $GAPCACHE/out/fix6/6-default-embedding.txt  # fix round 08:01:38-08:01:57Z: isolated 2.4.0 serve on 127.0.0.1:27375, embedding_provider unset; status before and after the server's own model fetch and a restart",
            "curl -sSf https://sh.rustup.rs -o rustup-init.sh && ecosystem-bounded-run env RUSTUP_HOME=$GAPCACHE/rust/rustup CARGO_HOME=$GAPCACHE/rust/cargo HOME=$GAPCACHE/rust/home sh rustup-init.sh -y --no-modify-path --profile minimal --default-toolchain 1.95 -c rustfmt -c clippy  # network download, rustc 1.95.0 (the repo's rust-toolchain.toml channel), 614 MB unpacked",
            "git clone --depth 1 --branch v2.4.0 https://github.com/akitaonrails/ai-memory $GAPCACHE/src/ai-memory-2.4.0  # network download, 24 MB, tag commit b1b25219b507cf56cb7334ac1a408dc9b09eaa50",
            "cargo fetch --locked  # network download, 492 crates, 85 MB of crate archives",
            "ECOSYSTEM_JOB_SECONDS=1200 ECOSYSTEM_JOB_MEMORY_MAX=16G ecosystem-bounded-run env RUSTUP_HOME=... CARGO_HOME=... CARGO_TARGET_DIR=$GAPCACHE/rust/target HOME=$GAPCACHE/rust/home AI_MEMORY_SERVER_URL=http://127.0.0.1:27375 cargo test --workspace --all-targets --locked --no-run -j 12  # build, 07:53:51-07:55:34Z, rc 0",
            f"ECOSYSTEM_JOB_SECONDS=1200 ecosystem-bounded-run unshare -rn {BP}/aimem/run_tests.sh  # upstream CI command `cargo test --workspace --all-targets --locked --offline --no-fail-fast` in a fresh network namespace (loopback only, host services unreachable), dropped back to uid 1000 in a nested user namespace, env -i with temp HOME/TMPDIR; 07:56:01-07:59:24Z, rc 101",
            f"ln -s $GAPCACHE/src/ai-memory-2.4.0/hooks $GAPCACHE/rust/hooks && ecosystem-bounded-run unshare -rn {BP}/aimem/run_tests_rerun.sh  # diagnostic rerun of the one failing target (`-p ai-memory-cli --test suite`) after the failure was observed (not preregistered); 07:59:59-08:00:40Z, rc 0",
        ],
        results={
            "covered_elsewhere": "sota-refresh-20260923/pins-mem/ai-memory.json (merged in #87): 2.4.0 release tarball matched its published sha256 sidecar; isolated write/search/read/handoffs/status/backup passed with embedding_provider explicitly set to none; restore not exercised end-to-end.",
            "binaries": "raw/6-r1-transcript.txt: 2.3.2 = $HOME/.local/share/codex-ecosystem/bin/ai-memory sha256 93eeb2994343f8d5427328650d3fc2ec85250332e2308c163d27169d8b5cfed0 ('ai-memory 2.3.2'); 2.4.0 = sota-refresh prefix sha256 360b9dff30537cc514876eab0c4df0d57b9c8c8bb1c62d4a9240f0264e246344 ('ai-memory 2.4.0')",
            "isolation_detection": "raw/6-r1-transcript.txt: both isolated servers listening (ss) before the calls and none after; `status` prints 'server: http://127.0.0.1:27374' / 'bind: 127.0.0.1:27374' (2.3.2) and ':27375' (2.4.0), values only the isolated servers report (the CLI's own freshly-initialised config says bind 127.0.0.1:49374, a default it does not connect to); MCP initialize returned serverInfo version 2.3.2 and 2.4.0 respectively.",
            "feature_surface": "raw/6-r1-transcript.txt --help of both versions lists `backfill` ('One-time import of this project's existing local harness session history into a brand-new (empty) ai-memory store'), `bootstrap` ('... Requires AI_MEMORY_LLM_PROVIDER configured on the server') and `embed` ('Compute + store embeddings for every latest page'); raw/6-mcp-tools-v23.txt and -v24.txt: both servers' tools/list include memory_briefing and memory_consolidate (23 tools each, identical names).",
            "llm_consolidation_default": "raw/6-serve24.log: 'AI_MEMORY_LLM_PROVIDER unset; memory_consolidate disabled, PreCompact falls back to rule-based checkpoint, lint runs rule-based only' and 'auto-improve scheduler enabled but no LLM provider is configured; job not started'; status 'llm: disabled' on both versions.",
            "default_config_diff_2.3.2_vs_2.4.0": "raw/6-r1-transcript.txt: '[diff exit 0]' between raw/6-config-noncomment-v23.toml and -v24.toml (identical non-comment defaults, token_pepper excluded); the commented default says 'Unset = the 2.0 default: in-process local embeddings (all-MiniLM-L6-v2, 384-dim) ... The ~87 MB model is fetched once into <data_dir>/models/ in the background ... hybrid search enables on the next start'.",
            "status_provider_lines": {"2.3.2 fresh": "llm: disabled / embedding: disabled", "2.4.0 fresh": "llm: disabled / embedding: disabled",
                                      "2.4.0 after its own model fetch and restart (raw/6-default-embedding.txt)": "embedding: local/all-MiniLM-L6-v2 (384d) unknown (no calls yet); after one write-page: 'embedding: local/all-MiniLM-L6-v2 (384d) ok', 'embeddings: 1 rows'"},
            "embedding_reconciliation": "The unset default is local MiniLM, but a fresh store reports 'embedding: disabled' until the background fetch finishes and the server restarts (measured: fetch 12 s, then 'embedder enabled provider=\"local\" model=\"all-MiniLM-L6-v2\" dim=384'). The sota-refresh finding 'embedding disabled' used embedding_provider = \"none\" explicitly, which opts out. The two observations agree.",
            "disposable_lifecycle_2.4.0": "write-page -> '✓ wrote notes/probe.md ... under g2fix/lifecycle'; search --json -> 1 hit with snippet '... <mark>zebra-quartz</mark>'; read-page -> page body; handoffs -> 'No open handoffs for g2fix/lifecycle.'; status -> pages 1, fts pages 1/1; backup -> 'wrote backup ... (39.06 KiB)'; all exit 0.",
            "upstream_tests_v2.4.0": {"source": "tag v2.4.0 commit b1b25219b507cf56cb7334ac1a408dc9b09eaa50, rustc 1.95.0", "command": "cargo test --workspace --all-targets (the upstream CI command) with --locked --offline --no-fail-fast",
                                      "full_run": "15 test binaries: 3,513 passed, 2 failed, 14 ignored (raw/6-cargo-test-full.log); wall 3 min 23 s",
                                      "failures": "ai-memory-cli tests/suite: removal::install_then_uninstall_round_trip_claude_hooks and removal::relocated_claude_uninstall_sweeps_active_and_legacy_installs -> 'Error: could not locate hooks directory. Tried: [\"$HOME/.cache/.../rust/hooks/claude-code\", ...]' (the binary looks for hooks/ beside its target dir; this unit put CARGO_TARGET_DIR outside the source tree)",
                                      "diagnostic_rerun": "after linking $GAPCACHE/rust/hooks -> the checkout's hooks/ (the in-tree layout): `-p ai-memory-cli --test suite` 126 passed, 0 failed, 1 ignored (raw/6-cargo-test-cli-suite-rerun.log)",
                                      "combined": "3,515 passed, 0 failed, 14 ignored; every ignored test carries an upstream #[ignore] (MiniLM model files, live LLM keys, release binary + dataset, throughput/manual), which CI also skips"},
            "toolchain_probe": "raw/6-r1-transcript.txt: `command -v cargo rustc` on the default PATH -> no output, exit 1 (the fix-round toolchain lives only under $GAPCACHE/rust and was never put on PATH)",
        },
        remains="Correct the catalog pin text (v2.3.1 -> installed 2.3.2): it lives in catalogs/landscape/us-equities.json and docs/grand-catalog-handbook.md, which this unit may not modify (coordinator-owned). Observe the LIVE service's briefing/embedding/consolidation/backfill state; this unit's isolation rule forbids any call to the live store.",
        limits=["No live-store inspection: whether automatic briefing, embedding, LLM consolidation or backfill are enabled on the running service was not re-observed; the isolated results describe the shipped defaults only.",
                "Catalog pin text was not edited by this unit.",
                "Upstream tests ran from the v2.4.0 source tag, not against the release binary; Linux only (CI's macOS leg, the TAILWIND_BUILD=1 stylesheet regeneration step and the separate companions/ai-memory-importer suite were not run). The two failures are attributed to this unit's CARGO_TARGET_DIR placement by the passing diagnostic rerun, which was not preregistered.",
                "Network downloads in the fix round: rustup-init.sh (29,915 bytes, sha256 7d0ea0f8...70af) and the Rust 1.95.0 minimal toolchain with rustfmt and clippy (614 MB unpacked); the ai-memory v2.4.0 shallow clone (24 MB); 492 crates (85 MB archives); all-MiniLM-L6-v2 from huggingface.co fetched by the isolated 2.4.0 server itself (91.3 MB: model.safetensors 90,868,376 + tokenizer.json 466,247 + config.json 612 bytes). The r1_surface.sh servers also began that background fetch and were stopped about 3 s later with nothing persisted (empty models dir). Everything is under $HOME/.cache/gap-wave2-20260923/agents-models-workers/.",
                "First-round gap-6 commands (exact times not recorded; --version/--help/backfill --help with no AI_MEMORY_SERVER_URL, init with AI_MEMORY_SERVER_URL=http://127.0.0.1:1) kept no raw output and did not point at an isolated server; the fix round supersedes them and every claim above cites a fix-round raw file.",
                ISO],
        raw=raw("6-r1-transcript.txt", "6-config-noncomment-v23.toml", "6-config-noncomment-v24.toml", "6-mcp-tools-v23.txt", "6-mcp-tools-v24.txt",
                "6-serve23.log", "6-serve24.log", "6-default-embedding.txt", "6-rustup-install.log", "6-cargo-fetch.log", "6-cargo-test-build.log",
                "6-cargo-test-full.log", "6-cargo-test-cli-suite-rerun.log", "6-upstream-run-meta.txt"),
        helpers=[f"{BP}/aimem/{n}" for n in ("r1_surface.sh", "r1b_default_embedding.sh", "run_tests.sh", "run_tests_rerun.sh")])

    R[7] = dict(slug="winner-readiness-today", outcome="advanced", evidence_class="native_proven",
        prereg=prereg("7-winner-readiness-today.json"),
        commands=[
            "sdk_arm.py inspect --workspace $GAPCACHE/ws/inspect  # model/list + account/rateLimits/read, 2026-09-23T07:27:59Z",
            "(gap 0) sdk_arm.py run ... # codex-native-sdk task 2026-09-23T07:28:14Z",
            "(gap 12/11) socraticode_eval.py ... # SocratiCode 1.14.0 index + 44 searches 2026-09-23T07:24-07:25Z",
            "codex exec --sandbox read-only --ephemeral --skip-git-repo-check -c features.hooks=false -c features.plugin_hooks=false -c 'mcp_servers.ai-memory.url=\"http://127.0.0.1:27374/mcp\"' --json - < memory-status-prompt.md  # native registration shape",
            "... same + -c 'mcp_servers.ai-memory.tools.memory_status.approval_mode=\"approve\"' (attempt 1: memory-status-prompt.md; attempt 2: memory-status-prompt-v2.md)",
            "claude -p \"$(cat memory-status-prompt-v2.md)\" --setting-sources project --strict-mcp-config --mcp-config '{\"mcpServers\":{\"ai-memory\":{\"type\":\"http\",\"url\":\"http://127.0.0.1:27374/mcp\"}}}' --allowedTools mcp__ai-memory__memory_status --max-turns 4 --no-session-persistence --model sonnet --output-format json",
            "git log --follow --format='%h %cI' -- evidence/receipts/desktop-direct-rag.json",
        ],
        results={
            "codex_native_sdk_readiness": {"at": "2026-09-23T07:27:59Z", "codex_cli": "0.155.1", "openai_codex_sdk": "0.154.0", "model": "gpt-6-astra", "model_available": True,
                                            "ordinary_usage_allowed": True, "weekly_window_used_percent": 32, "ready": True},
            "codex_native_sdk_task": "gap-0 arm completed 2026-09-23T07:28:24Z, 6/6 facts, 41,039 tokens",
            "socraticode_search": "SocratiCode 1.14.0 indexed 195 chunks in 9.6 s and answered 32+12 searches (disposable Qdrant, adopted embedding profile); no errors",
            "codex_mcp_memory_status": {
                "native_shape (url only)": "FAILED: 'MCP tool call requires approval, but approval policy is never' (36,297 in / 770 out tokens)",
                "approve attempt 1": "not called: tool was deferred and this unit's prompt forbade calling the discovery tool (17,754 in / 222 out) -- a prompt error by this unit, counted as a failed attempt",
                "approve attempt 2": "completed: memory_status -> {\"counts\": {\"pages_latest\": 0, \"pages_all\": 0, \"sessions\": 0, \"observations\": 0}} (60,608 in / 189 out)"},
            "claude_mcp_memory_status": "Claude Code 2.1.280, claude-sonnet-5, 3 turns, 4.25 s, success: same counts JSON (cost reported 0.0709516 USD list-basis on the subscription account)",
            "memory_status_scope_note": "Both clients returned zero counts because memory_status without workspace/project resolved to an empty scope; the isolated store held 19 pages in g2amw/*.",
            "desktop-direct-rag.json": "first and only commit 13cc51f at 2026-09-19T05:26:40Z (a commit date, not an execution date; the file itself has no date field)",
        },
        remains="memory_status against the LIVE ai-memory service through the actual native registrations (url http://127.0.0.1:49374/mcp) was not re-run: this unit's isolation rule forbids any ai-memory call to the live store. Today's readiness of the live service itself therefore remains unobserved here.",
        limits=["ai-memory readiness was observed on an isolated 2.3.2 server started by this unit, not the running service.",
                "The native Codex exec path needs an explicit MCP tool approval override for non-interactive runs; the agent-lab registration has none (finding, not a fix).",
                ISO],
        raw=raw("7-sdk-inspect.json", "7-codex-mcp-native-shape.events.jsonl", "7-codex-mcp-approved-attempt1.events.jsonl", "7-codex-mcp-approved-attempt2.events.jsonl", "7-claude-mcp.json"),
        helpers=[f"{BP}/workers/{n}" for n in ("memory-status-prompt.md", "memory-status-prompt-v2.md", "sdk_arm.py")])

    R[9] = dict(slug="composed-sdk-worker-restart-handoff", outcome="settled", evidence_class="native_proven",
        prereg=prereg("9-composed-sdk-worker-restart-handoff.json"),
        commands=[f"python3 {BP}/workers/g9_composed.py $GAPCACHE/runs/g9",
                  "ai-memory --data-dir $GAPCACHE/aim-data handoffs --workspace g2amw --project g9-composed  # polled every 0.5 s, AI_MEMORY_SERVER_URL=http://127.0.0.1:27374",
                  "os.killpg(<run-1 process group>, SIGKILL) when the handoff appeared",
                  "rg g2amw_codebase_780df9a835e7 $GAPCACHE/logs/qdrant.log  # which SocratiCode searches happened in which run window"],
        results={
            "worker_config": "one codex-native-sdk worker (sdk_arm.py) with mcp_servers.ai-memory (url 127.0.0.1:27374/mcp, enabled_tools handoff_begin/accept/list) and mcp_servers.socraticode (node SocratiCode 1.14.0 on the disposable Qdrant, enabled_tools codebase_search/status), both default_tools_approval_mode approve, read-only sandbox, hooks off",
            "run_1": "started 07:35:47Z; SocratiCode search at 07:35:57.76Z (Qdrant access log); memory_handoff_begin created handoff 01a0cd31-<redacted>; process group SIGKILLed 17.68 s after start; returncode -9; no SDK receipt written; no leftover run-1 processes",
            "run_1_usage": "UNAVAILABLE: the worker's thread was ephemeral (no rollout file) and the process was SIGKILLed before turn/completed, so sdk_arm.py never received or wrote result.usage (9-orchestration.json: receipt_written false, stdout empty). Run 1 consumed provider tokens that this receipt cannot report.",
            "run_1_tool_calls": "not itemised (no SDK item list); observed side effects: 1 SocratiCode search (Qdrant access log) and 1 memory_handoff_begin (the handoff it created)",
            "handoff_between_runs": "Open handoffs for g2amw/g9-composed: id 01a0cd31-<redacted>; summary begins 'step 1 done. step-1 file list: [\"scripts/build_ecosystem.py\", \"scripts/landscape.py\", ...'",
            "run_2": "fresh worker 07:36:07-07:36:46Z: memory_handoff_list -> memory_handoff_accept -> 3 x codebase_search (Qdrant log 07:36:28, 07:36:36 x2) -> final JSON; usage 166,882 total tokens",
            "whole_task_usage": "run 2: 166,882 total tokens (reported); run 1: unavailable (killed before usage was reported). The whole-task total is therefore at least 166,882 tokens and is not known exactly.",
            "final_answer": {"sha256_files": ["scripts/build_ecosystem.py", "scripts/landscape.py", "scripts/native_token_ci.py", "scripts/validate.py", "scripts/validate_convergence.py", "scripts/verify_nautilus_ci.py"],
                             "subprocess_files": ["scripts/adoption_status.py", "scripts/native_token_ci.py", "scripts/validate.py"],
                             "recovered_from_handoff": ["step-1 sha256_files from handoff 01a0cd31-<redacted>"], "redone_steps": []},
            "gold_check": "sha256 files 6/6 and subprocess files 3/3 equal the rg-computed gold over scripts/*.py at 41d39b3",
            "recovered": "step-1 result (6 files) from the ai-memory handoff; SocratiCode index persisted in Qdrant (no reindex); the in-process thread (ephemeral) was lost and not needed",
            "handoff_after_run_2": "No open handoffs (accepted, single-use)",
        },
        remains=None,
        limits=["Isolated ai-memory and disposable SocratiCode/Qdrant instances, not the live services; n=1.",
                "Run-1 SocratiCode use is shown by the Qdrant access log timing, since the killed run left no SDK item list.",
                "Preregistered usage per run is incomplete: run-1 provider usage is unavailable (see results.run_1_usage), so whole-task usage is a lower bound (fix round: previously omitted without saying so).",
                "Approval mode 'approve' was set on both MCP servers for non-interactive operation.", ISO],
        raw=raw("9-orchestration.json", "9-run2-receipt.json", "9-qdrant-access-log-run-window.txt"),
        helpers=[f"{BP}/workers/{n}" for n in ("g9_composed.py", "g9-step1-prompt.md", "g9-step2-prompt.md", "sdk_arm.py")])

    R[11] = dict(slug="twelve-query-per-lane", outcome="settled", evidence_class="native_proven",
        prereg=prereg("11-twelve-query-per-lane.json"),
        commands=["git show bfd03bc:blueprints/us-equities/<18 eligible paths>  # restored, sha256 verified against source-manifest.json (18/18)",
                  f"python3 {BP}/retrieval/socraticode_eval.py $GAPCACHE/corpus-foundation blueprints/us-equities/retrieval-evaluation/fixture.json ...  # limit 10, minScore 0",
                  "ai-memory --data-dir $GAPCACHE/aim-data write-page --workspace g2amw --project foundation12 --path <rel> --body - < <file>  (x18, AI_MEMORY_SERVER_URL=http://127.0.0.1:27374)",
                  "ai-memory --data-dir $GAPCACHE/aim-data search '<fixed query>' --workspace g2amw --project foundation12 --limit 10 --json  (x12)",
                  f"python3 {BP}/retrieval/score_gap11.py fixture.json ... "],
        results={
            "qmd_bm25_recorded_baseline": {"recall@1": "5/12", "recall@3": "8/12", "recall@5": "9/12", "mrr@10": 0.56875},
            "socraticode_1.14.0": {"recall@1": "7/12", "recall@3": "11/12", "recall@5": "11/12", "mrr@10": 0.72222,
                                   "misses": {"savings-scope": "not in top 10"}, "ranks": {"native-token-subsets": 3, "worker-cancellation": 3, "broker-timeout": 2, "alpaca-entitlement": 2}},
            "ai_memory_2.3.2_cli_search (FTS5)": {"recall@1": "8/12", "recall@3": "11/12", "recall@5": "11/12", "mrr@10": 0.80208,
                                                  "misses": {"savings-scope": "rank 8"}},
            "reading": "Per lane over the 18 eligible documents: SocratiCode and ai-memory each recover 11/12 intended sources in the top 3 and both miss 'selected text provider savings' in the top 5. The recorded QMD baseline (8/12) returned results only from the same 18 eligible documents, but its BM25 document-frequency and length statistics covered 33 documents (blueprints/us-equities/retrieval-evaluation/README.md and full-corpus-manifest.json: the collection filter is applied after scoring). The returnable set is therefore identical; the lexical scoring statistics differ, so the per-lane numbers are comparable on result set but not identical in scoring corpus. The QMD figures cannot be attributed to either lane. (Correction 2026-09-23 round 3, source review: earlier text called the 15 extra documents distractors in the ranking.)",
            "corpus_sizes": {"socraticode": "18 files, 86 chunks (raw/11-socraticode-raw.json final_status 'Files: 18, Chunks: 86')", "ai_memory": "18 pages", "qmd_recorded_baseline": "results limited to the 18 eligible documents; BM25 statistics over 33 documents"},
        },
        remains=None,
        limits=["Both lanes run here (SocratiCode and ai-memory) indexed only the 18 eligible documents, whereas the recorded QMD baseline indexed 33 documents for BM25 statistics and then filtered results to the same 18 eligible documents (the other 15 were never returnable). Per-lane recall is valid on the 18-document corpus; the comparison with QMD's 8/12 shares the result set but not the lexical scoring statistics, and n=12 with one gold path per query. Neither the SocratiCode nor the ai-memory lane was re-run over the 33-document statistics corpus. (Fix round: the first-round limit named only ai-memory. Round 3 correction, source review only: the earlier wording '15 more distractors' was wrong.)",
                "ai-memory `search` is FTS5-only by design (embedding provider none here).",
                "SocratiCode chunk hits were deduplicated to documents; one gold path per query, not exhaustive relevance.",
                "The scoring script was written after the searches ran but implements the preregistered rule (exact path, recall@1/3/5, MRR <=10 docs).", ISO],
        raw=raw("11-socraticode-raw.json", "11-aimemory-raw.json", "11-scores.json"),
        helpers=[f"{BP}/retrieval/{n}" for n in ("socraticode_eval.py", "score_gap11.py", "mcp_client.py")])

    R[12] = dict(slug="exhaustive-source-recovery", outcome="settled", evidence_class="native_proven",
        prereg=prereg("12-exhaustive-source-recovery.json"),
        commands=["git archive 41d39b3 scripts | tar -x  # 11 scripts/*.py files",
                  f"python3 {BP}/retrieval/build_gap12_queries.py $GAPCACHE/corpus-scripts {BP}/retrieval/gap12_queries.json  # sha256 48695cb0..., committed 5480a9c before indexing",
                  f"python3 {BP}/retrieval/socraticode_eval.py $GAPCACHE/corpus-scripts {BP}/retrieval/gap12_queries.json ...  # 195 chunks indexed in 9.6 s; limit 10, minScore 0",
                  f"python3 {BP}/retrieval/score_gap12.py ..."],
        results={
            "set": "32 conceptual queries, 176 exhaustive pattern-defined gold lines (4 single-location, 28 multi-location)",
            "summary": {"hit@1": 0.6562, "hit@5": 0.9062, "hit@10": 0.9375, "mrr@10": 0.7618, "mean_completeness@1": 0.242,
                        "mean_completeness@5": 0.5778, "mean_completeness@10": 0.7621, "micro_completeness@10": 0.6932,
                        "fully_complete@10": 0.4375, "mean_completeness@10_multi_location": 0.7282},
            "zero_recovery_queries": ["filerel (9 Path(__file__) sites)", "glob (2 rglob sites)"],
            "reading": "Top-10 chunk search finds at least one location for 30/32 concerns but recovers every location for only 14/32; it is not an exhaustive enumerator. Use exact search (rg/Serena references) when completeness matters.",
        },
        remains=None,
        limits=["One small corpus (11 Python files, ~4,000 lines) with pattern-defined relevance; semantically equivalent code not matching a pattern is not gold.",
                "Containment is chunk-level (mean 23.6 lines per returned chunk).",
                "Queries authored by this unit, sealed before indexing; no independent review of query wording.", ISO],
        raw=raw("12-socraticode-raw.json", "12-scores.json"),
        helpers=[f"{BP}/retrieval/{n}" for n in ("build_gap12_queries.py", "gap12_queries.json", "socraticode_eval.py", "score_gap12.py")])

    R[15] = dict(slug="artifact-reduction-whole-task", outcome="advanced", evidence_class="native_proven",
        prereg=prereg("15-artifact-reduction-whole-task.json"),
        commands=[f"python3 {BP}/lane/gold.py $GAPCACHE/g15-snapshot  # gold outside any model, committed c7fb014 before runs",
                  f"{BP}/lane/run_arm.sh t1|t2 with|without $GAPCACHE/runs/g15  # codex exec --sandbox read-only --ephemeral, hooks off; with: context-mode plugin MCP approve; without: plugins.\"context-mode@context-mode\".enabled=false"],
        results={
            "t1 (count 2,117 test defs in 93 files, top file)": {"with_context_mode": {"correct": "3/3", "total_tokens": 91371, "turns": 1, "failed_tool_calls": 0, "tools": ["cat context-mode SKILL.md (16,358 chars)", "cat RTK.md", "ctx_execute"], "wall_s": 29.41},
                                                                   "without": {"correct": "3/3", "total_tokens": 36224, "turns": 1, "failed_tool_calls": 0, "tools": ["one python3 aggregation command (112 chars output)"], "wall_s": 15.04}},
            "t2 (609 KB manifest: 99 receipt entries, 2,272,055 bytes)": {"with_context_mode": {"correct": "2/2", "total_tokens": 62412, "failed_tool_calls": 0, "tools": ["sed SKILL.md (10,471 chars)", "ctx_execute"], "wall_s": 16.62},
                                                                           "without": {"correct": "2/2", "total_tokens": 36315, "failed_tool_calls": 0, "tools": ["one jq aggregation (53 chars output)"], "wall_s": 18.86}},
            "whole_task_totals_incl_failures": {"with_context_mode": 153783, "without": 72539, "failed_or_retried_attempts": 0},
            "reading": "On these two Codex tasks the reduction lane cost about 2.1x the tokens of the plain arm with equal accuracy: the model loaded the Context Mode skill text and the MCP tool definitions, while the plain arm already aggregated large outputs in one small command. No net whole-task saving was observed for Codex on these tasks.",
        },
        remains="The Claude arm through native workflow children and child-usage.mjs (the shared Claude account is reserved for another session's long-horizon run, so a Claude fan-out is deferred); more tasks and repetitions (n=1 per cell); tasks where the plain arm must print large output.",
        limits=["Codex only, 2 tasks x 2 arms x 1 run; tasks are aggregations the model could script cheaply, which favours the plain arm.",
                "Usage is the sum of turn.completed usage from codex exec --json (includes cached input); not a billing figure.", ISO],
        raw=raw(*[f"15-{t}-{a}.{s}" for t in ("t1", "t2") for a in ("with", "without") for s in ("summary.json", "events.jsonl")]),
        helpers=[f"{BP}/lane/{n}" for n in ("gold.py", "gold.json", "t1.md", "t2.md", "with-lane-note.md", "without-lane-note.md", "score.py", "run_arm.sh")])

    R[16] = dict(slug="non-adopted-candidate-comparison", outcome="advanced", evidence_class="native_proven",
        prereg=prereg("16-non-adopted-candidate-comparison.json"),
        commands=["uv venv --python 3.13 $GAPCACHE/loopx-venv && uv pip install loopx==1.1.0  # network download: 6.2 MB wheel from PyPI, no dependencies",
                  f"$GAPCACHE/loopx-venv/bin/python {BP}/workers/loopx_arm.py $GAPCACHE/runs/g16-loopx  # HOME=<temp>; loopx --registry ... turn run-once --host codex-cli --execution-mode isolated-headless --codex-sandbox read-only --codex-model gpt-6-astra --validation-command-json [loopx_validator.py gold.json] --no-global-sync --execute"],
        results={
            "candidate": "LoopX 1.1.0 (loopx-project/loopx, non-adopted newcomer c5 in this packet), built-in codex-cli adapter driving the same native Codex 0.155.1 / gpt-6-astra",
            "same_task_as_gap_0": True,
            "loopx": {"status": "failed", "result_kind": "validation_failed", "recovery_kind": "repair_required", "facts_correct": "0/6",
                      "command": "/bin/bash -lc 'head -c 24000 -- worker-receipt.json acp-research-receipt.json' (same method)",
                      "codex_turn_usage": {"input_tokens": 41936, "cached_input_tokens": 18688, "output_tokens": 1100, "reasoning_output_tokens": 694, "total": 43036},
                      "elapsed_seconds": 40.6, "effects": {"host_invoked": True, "state_written": False, "quota_spent": False},
                      "returned_summary_excerpt": "Read both files using exactly one shell command ... Both receipts are dated 2026-09-19 and report matching engine counts: 3,943 data points, 3 simulated orders, and 0 failed data requests; historical DeerFlow discovery found 23 skills,"},
            "codex_native_sdk_same_task": {"facts_correct": "6/6", "total_tokens": 41039, "wall_seconds": 9.71},
            "reading": "LoopX's typed Turn result (schema loopx_turn_result_v0, 400-char summary) displaced the task's requested JSON: the model wrote a prose summary, the independent validator failed, and LoopX correctly refused to commit or spend quota. On this single-turn task the evidence does not favour LoopX over codex-native-sdk.",
        },
        remains="LoopX's own overturn condition (a long-running worker surviving restarts and quota exhaustion where the current coordinator loses state) was not exercised; no repair Turn was run (preregistered as one Turn), and n=1.",
        limits=["Single-turn extraction task; it does not test LoopX's long-horizon governance value.",
                "The LoopX host prompt was not captured, so whether the full todo text reached the model is not verified.",
                "The codex binary handed to LoopX was a wrapper adding hooks-off and --ephemeral (isolation); otherwise LoopX's adapter command was unchanged.", ISO],
        raw=raw("16-loopx-arm-result.json", "16-loopx-codex-events.jsonl", "16-loopx-validator-stdin.json", "16-loopx-codex-argv.log", "0-sdk-arm.json"),
        helpers=[f"{BP}/workers/{n}" for n in ("loopx_arm.py", "loopx_validator.py", "task-prompt.md", "gold.json", "score_facts.py")])

    results = {}
    for idx, r in sorted(R.items()):
        g = gaps[idx]
        receipt = {
            "id": f"gap-wave2-20260923/us-equities__agents-models-workers/{idx}-{r['slug']}",
            "catalog": "us-equities", "layer_id": "agents-models-workers", "gap_index": idx,
            "gap_text": g["text"], "gap_text_sha256": hashlib.sha256(g["text"].encode()).hexdigest(),
            "next_check": g["next_check"], "base_commit": "41d39b3",
            "preregistration": r["prereg"], "commands": r["commands"], "results": r["results"],
            "outcome": r["outcome"], "what_remains": r["remains"], "evidence_class": r["evidence_class"],
            "limits": r["limits"], "raw_artifacts": r["raw"], "helpers": r["helpers"], "checked_at": CHECKED,
        }
        if idx in (4, 5, 9, 11, 12):
            receipt["commands"] = SERVICES_CMDS + receipt["commands"]
            # Privacy sweep 2026-09-23 (PR #132 review): the transcript export is retained host-local and not published;
            # its pin is kept with the hash of the retained copy.
            receipt["raw_artifacts"] = receipt["raw_artifacts"] + [{
                "path": f"{RAW}/services-main-round.txt",
                "sha256": "d1109be89f5b729b21737ae6a579d34abf0f9a9a0b4bc74e5c61833c221a03a1",
                "published": False,
                "retention": "host-local, owner-only; not published under the catalog rule against raw conversations (PR #132 review)"}]
            receipt["helpers"] = receipt["helpers"] + [f"{BP}/services/export_main_round_services.py"]
        if idx == 4:
            receipt["corroborating_receipt"] = "evidence/artifacts/gap-wave2-20260923/semantic-rag/socraticode-vs-baselines.json (origin/main)"
        if idx == 6:
            receipt["covered_elsewhere_part"] = "evidence/artifacts/sota-refresh-20260923/pins-mem/ai-memory.json (merged in #87)"
        name = f"{idx}-{r['slug']}.json"
        (EV / name).write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    for p in sorted(EV.glob("[0-9]*-*.json"), key=lambda p: int(p.name.split("-")[0])):
        d = json.loads(p.read_text())
        results[str(d["gap_index"])] = {"outcome": d["outcome"], "receipt": str(p.relative_to(REPO))}
    (EV / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in results.items()}))


if __name__ == "__main__":
    main()
