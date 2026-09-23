#!/usr/bin/env python3
"""Round 4: add the loopback-provider checks to the receipts (agent-sdks gap wave, 2026-09-23).

Called from build_receipts.main() after build_round3.apply() and before results.json is derived.
Every quoted value is read from raw/round4/ at build time. Receipts whose outcome or limits change keep
the earlier values under `pre_round_4_outcome`, `pre_round_4_remaining` and `pre_round_4_limits`.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

EV = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks"
RAW4 = EV / "raw/round4"
PREREG = "preregistration-round4.json"
H = "blueprints/gap-wave2-20260923/foundation__agent-sdks"
C = "$HOME/.cache/gap-wave2-20260923/agent-sdks"
R = C + "/round4"
CODEX_BIN = "$HOME/.local/share/codex-ecosystem/bin/codex"
CODEX_PY = C + "/codex-sdk-01551/bin/python"
CLAUDE_ENV = ("env -i PATH=/usr/bin:/bin HOME=" + R + "/claude-home CLAUDE_CONFIG_DIR=" + R + "/claude-home/.claude "
              "ANTHROPIC_BASE_URL=http://127.0.0.1:28431 ANTHROPIC_API_KEY=dummy-local ANTHROPIC_DEFAULT_HAIKU_MODEL=qwen3-4b "
              "ANTHROPIC_DEFAULT_SONNET_MODEL=qwen3-4b ANTHROPIC_DEFAULT_OPUS_MODEL=qwen3-4b ANTHROPIC_SMALL_FAST_MODEL=qwen3-4b "
              "CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 DISABLE_TELEMETRY=1 "
              "DISABLE_AUTOUPDATER=1 DISABLE_ERROR_REPORTING=1 " + C + "/claude-sdk/bin/python")
OH_ENV = ("env -i PATH=/usr/bin:/bin HOME=" + R + "/oh-home OPENHANDS_SUPPRESS_BANNER=1 LITELLM_LOCAL_MODEL_COST_MAP=True "
          + C + "/openhands/bin/python")
PODMAN = "podman --root " + R + "/podman/root --runroot /tmp/r4p.XXXX --tmpdir " + R + "/podman/tmp --events-backend none"
PROVIDER_CMDS = [
    "ECOSYSTEM_JOB_SECONDS=1200 $HOME/codex-ecosystem/bin/ecosystem-bounded-run env -u HF_TOKEN HF_HOME=" + C + "/hf "
    "HF_HUB_DISABLE_TELEMETRY=1 $HOME/.local/share/codex-ecosystem/tools/vllm-0.25.0/bin/python -c \"from huggingface_hub import snapshot_download; snapshot_download("
    "'Qwen/Qwen3-4B-Instruct-2507-FP8', revision='8591804019c8b22094c3b5b4454e0edc05dffc98')\"  # 4.9 GB download from huggingface.co",
    "ECOSYSTEM_JOB_MEMORY_HIGH=10G ECOSYSTEM_JOB_MEMORY_MAX=14G ECOSYSTEM_JOB_SECONDS=10800 ECOSYSTEM_JOB_TASKS_MAX=1024 "
    "$HOME/codex-ecosystem/bin/ecosystem-bounded-run " + R + "/serve.sh  # contents in raw/round4/serve.sh (pasta netns, "
    "only 127.0.0.1:28431 forwarded); three earlier launches failed or were replaced, logs retained",
    "kill -TERM <vllm api-server pid inside the pasta namespace>  # stop at 14:37:38Z; nvidia-smi before/after in raw/round4/gpu-before.txt, gpu-after.txt",
    "(review fix round) the same serve.sh restarted at about 14:56:36Z and stopped the same way at 15:03:19Z; gpu-before-fix.txt, gpu-after-fix.txt",
    "(second review fix) " + H + "/r4_fix2_remote.sh restarted it at 15:46:08Z; its stop step failed and the api-server was "
    "stopped by pid at 15:49:59Z (see receipt 8, round_4.results.provider_stop_rule_gpu)",
]


def raw(name: str):
    return json.loads((RAW4 / name).read_text())


# Privacy sweep 2026-09-23 (PR #132 review): retained host-local and not published (see export_round4.PRIVATE).
PRIVATE4 = {"vllm-procs-after-fix2-manual.txt", "oh-server-procs-after-fix2-manual.txt"}
PRIVATE4_DIR = Path.home() / ".local/state/agent-lab-17/private-evidence/gap-wave2-20260923/foundation__agent-sdks/raw/round4"
RETENTION = "host-local, owner-only; not published under the catalog rule against machine-specific active client configuration and personal paths (PR #132 review)"


def cite(*names: str) -> list[dict]:
    out = []
    for n in names:
        entry = {"path": f"raw/round4/{n}", "sha256": hashlib.sha256(((PRIVATE4_DIR if n in PRIVATE4 else RAW4) / n).read_bytes()).hexdigest()}
        if n in PRIVATE4:
            entry.update({"published": False, "retention": RETENTION})
        out.append(entry)
    return out


def iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def prereg(arm: str) -> dict:
    p = json.loads((EV / PREREG).read_text())
    return {"file": PREREG, "written_at": p["written_at"], "written_window": p["written_window"],
            "written_at_note": p["written_at_note"], **p["arms"][arm]}


def codex_cancel(name: str) -> dict:
    d = raw(name)
    t = d["turn2_interrupt"]
    totals = [e for e in t["rollout"]["entries"] if "total" in e]
    return {
        "file": name,
        "turn_status": t["turn_completed"]["turn_status"],
        "streaming_observed_before_interrupt": t["streaming_observed_before_interrupt"],
        "provider_interrupted_request": {"prompt_tokens": t["provider_delta_before_to_settle1"]["vllm:prompt_tokens_total"],
                                         "generation_tokens": t["provider_delta_before_to_settle1"]["vllm:generation_tokens_total"],
                                         "generation_tokens_at_interrupt_sample": t["provider_delta_before_to_interrupt"]["vllm:generation_tokens_total"],
                                         "finished_by_reason_delta": t["provider_delta_before_to_settle1"]["finished_by_reason"]},
        "running_right_after_turn_completed": t["samples"]["after_completed_1s"].get("vllm:num_requests_running"),
        "running_at_settle1": t["running_at_settle1"],
        "settle1_seconds_after_interrupt": round(t["samples"]["settle1"]["at"] - t["interrupt_requested_at"], 2),
        "generation_settle1_to_settle2": t["provider_delta_settle1_to_settle2"]["vllm:generation_tokens_total"],
        "consumption_stopped": t["consumption_stopped"],
        "sdk_thread_token_usage_total_after_interrupt": (t["sdk_token_usage_notifications"][-1]["total"]
                                                         if t["sdk_token_usage_notifications"] else None),
        "rollout_last_total_after_abort": totals[-1]["total"] if totals else None,
        "rollout_abort_event": [e for e in t["rollout"]["entries"] if e.get("event") == "turn_aborted"],
        "turn1_provider_vs_rollout": {"provider_prompt": d["turn1"]["provider_delta"]["vllm:prompt_tokens_total"],
                                      "provider_generation": d["turn1"]["provider_delta"]["vllm:generation_tokens_total"],
                                      "rollout_total_input": totals[-1]["total"]["input_tokens"] if totals else None,
                                      "rollout_total_output": totals[-1]["total"]["output_tokens"] if totals else None},
    }


def claude_cancel(name: str) -> dict:
    d = raw(name)
    t = d["turn2_interrupt"]
    res = t["result"]
    return {
        "file": name,
        "terminal_reason": res["terminal_reason"], "result_subtype": res["subtype"],
        "streaming_observed_before_interrupt": t["streaming_observed_before_interrupt"],
        "provider_interrupted_request": {"prompt_tokens": t["provider_delta_before_to_settle1"]["vllm:prompt_tokens_total"],
                                         "generation_tokens": t["provider_delta_before_to_settle1"]["vllm:generation_tokens_total"],
                                         "generation_tokens_at_interrupt_sample": t["provider_delta_before_to_interrupt"]["vllm:generation_tokens_total"],
                                         "finished_by_reason_delta": t["provider_delta_before_to_settle1"]["finished_by_reason"]},
        "running_right_after_result": t["samples"]["after_result_1s"].get("vllm:num_requests_running"),
        "running_at_settle1": t["running_at_settle1"],
        "settle1_seconds_after_interrupt": round(t["samples"]["settle1"]["at"] - t["interrupt_requested_at"], 2),
        "generation_settle1_to_settle2": t["provider_delta_settle1_to_settle2"]["vllm:generation_tokens_total"],
        "consumption_stopped": t["consumption_stopped"],
        "result_usage_input_output": [res["usage"].get("input_tokens"), res["usage"].get("output_tokens")],
        "result_model_usage": {k: [v.get("inputTokens"), v.get("outputTokens")] for k, v in res["model_usage"].items()},
        "turn1_provider_prompt_generation": [d["turn1"]["provider_delta"]["vllm:prompt_tokens_total"],
                                             d["turn1"]["provider_delta"]["vllm:generation_tokens_total"]],
        "session_jsonl_final_usage_per_message": d["session_log"]["final_usage_per_message"],
        "stream_usage_events": t["stream_usage_events"],
    }


CODEX_FIRST = ("codex-session.json", "codex-session-rep2.json", "codex-session-rep3.json")
CLAUDE_FIRST = ("claude-session.json", "claude-session-rep2.json", "claude-session-rep3.json")
# Review fix round (preregistered 14:55:50Z): the same session phase rerun with --tap (every notification or raw
# CLI message recorded before routing/parsing), 3 trials per SDK, plus one tapped resume each.
CODEX_FIX = ("codex-session-fix1.json", "codex-session-fix2.json", "codex-session-fix3.json")
CLAUDE_FIX = ("claude-session-fix1.json", "claude-session-fix2.json", "claude-session-fix3.json")
CODEX_RUNS = CODEX_FIRST + CODEX_FIX
CLAUDE_RUNS = CLAUDE_FIRST + CLAUDE_FIX
# The cited remote run is the second-fix rerun with the committed r4_openhands.py (openhands-remote-fix2.json);
# openhands-remote.json came from a pre-commit working-tree revision without the workspace read-back.
OH_RUNS = ("openhands-local.json", "openhands-remote-fix2.json", "openhands-container-fix.json")
OH_EARLIER = ("openhands-container.json", "openhands-remote.json")
SESSION_CMDS = [
    f"{CODEX_PY} {H}/r4_codex.py session --codex-bin {CODEX_BIN} --codex-home {R}/codex-home --workspace {R}/ws-codex "
    f"--state {R}/private/codex-state.json --out {R}/codex-session.json  # and -rep2/-rep3 with their own state files",
    f"{CLAUDE_ENV} {H}/r4_claude.py session --workspace {R}/ws-claude --state {R}/private/claude-state.json "
    f"--out {R}/claude-session.json  # and -rep2/-rep3",
    f"(fix round) the same two commands with --tap, state codex-state-fix<i>.json / claude-state-fix<i>.json and "
    f"outputs codex-session-fix<i>.json / claude-session-fix<i>.json for i = 1, 2, 3",
]
RESUME_CMDS = [
    f"{CODEX_PY} {H}/r4_codex.py resume --codex-bin {CODEX_BIN} --codex-home {R}/codex-home --workspace {R}/ws-codex "
    f"--state {R}/private/codex-state.json --out {R}/codex-resume.json",
    f"{CLAUDE_ENV} {H}/r4_claude.py resume --workspace {R}/ws-claude --state {R}/private/claude-state.json "
    f"--out {R}/claude-resume.json",
    f"(fix round) the same two resume commands with --tap, state *-state-fix1.json, outputs codex-resume-fix1.json "
    f"and claude-resume-fix1.json",
]
LOCAL_LIMIT = ("The provider is an open-weight model (Qwen3-4B-Instruct-2507-FP8) on a vLLM server this unit started; "
               "neither the hosted OpenAI nor the hosted Anthropic service was involved, so hosted-model behaviour and "
               "hosted billing are not shown.")


def cancel_block() -> dict:
    cx = [codex_cancel(n) for n in CODEX_RUNS]
    cl = [claude_cancel(n) for n in CLAUDE_RUNS]
    return {"codex_sdk": cx, "claude_agent_sdk": cl,
            "all_consumption_stopped": all(r["consumption_stopped"] for r in cx + cl),
            "all_running_zero_at_settle1": all(r["running_at_settle1"] == 0 for r in cx + cl),
            "detector": {
                "method": "vLLM Prometheus counters read over /metrics; for every completed (not interrupted) request "
                          "the counter deltas equal the client-reported usage, so the counters see consumption "
                          "that the clients also see",
                "codex_turn1_counter_equals_rollout_total": all(
                    r["turn1_provider_vs_rollout"]["provider_prompt"] == r["turn1_provider_vs_rollout"]["rollout_total_input"]
                    and r["turn1_provider_vs_rollout"]["provider_generation"] == r["turn1_provider_vs_rollout"]["rollout_total_output"]
                    for r in cx),
                "claude_turn1_counter_equals_model_usage": all(
                    r["turn1_provider_prompt_generation"] == next(iter(r["result_model_usage"].values())) for r in cl),
                "openhands_counter_equals_sdk_metrics": all(
                    raw(n)["provider_delta"]["vllm:prompt_tokens_total"] == raw(n)["sdk_metrics"]["accumulated_token_usage"]["prompt_tokens"]
                    and raw(n)["provider_delta"]["vllm:generation_tokens_total"] == raw(n)["sdk_metrics"]["accumulated_token_usage"]["completion_tokens"]
                    for n in OH_RUNS + OH_EARLIER),
                "inline_control_not_retained": "Two direct /v1/chat/completions control requests (120 and 200 tokens) "
                                               "matched the counters exactly (between 14:18:57Z and about 14:20:20Z); their output was printed to the "
                                               "terminal only and is not a retained file, so the retained detector is the "
                                               "completed-request equality above.",
                "natural_finish_detector": "a request that ends by itself increments request_success_total "
                                           "(stop/length, seen for every completed turn); the interrupted requests added "
                                           "no finished_reason count, so they did not end naturally. vLLM 0.25.0 also did "
                                           "not count them under finished_reason=abort."},
            "sampling_note": sampling_note(cx, cl)}


def sampling_note(cx: list, cl: list) -> str:
    runs = cx + cl
    still = sum(1 for r in cx if r["running_right_after_turn_completed"]) + sum(1 for r in cl if r["running_right_after_result"])
    s1 = [r["settle1_seconds_after_interrupt"] for r in runs]
    extra = [r["provider_interrupted_request"]["generation_tokens"] - r["provider_interrupted_request"]["generation_tokens_at_interrupt_sample"]
             for r in runs]
    return (f"The sample named after_completed_1s/after_result_1s is taken immediately (about 0.01-0.03 s) after the SDK "
            f"reported the terminal state; num_requests_running was still 1 there in {still} of {len(runs)} runs (the "
            f"server-side abort lags the client) and 0 at settle1 in "
            f"{sum(1 for r in runs if r['running_at_settle1'] == 0)} of {len(runs)}. Settle1 falls {min(s1)}-{max(s1)} s "
            f"after the interrupt request, so the preregistered 'within 10 s' holds only to within that sampling slack. "
            f"Between the interrupt sample and settle1, {min(extra):g}-{max(extra):g} further tokens were generated.")


def ranges(b: dict) -> dict:
    def rng(rows, key):
        v = [r["provider_interrupted_request"][key] for r in rows]
        return f"{min(v):g}-{max(v):g}"
    return {"codex_prompt": rng(b["codex_sdk"], "prompt_tokens"), "codex_gen": rng(b["codex_sdk"], "generation_tokens"),
            "claude_prompt": rng(b["claude_agent_sdk"], "prompt_tokens"),
            "claude_gen": rng(b["claude_agent_sdk"], "generation_tokens")}


def gap1() -> tuple[dict, str, str, list]:
    b = cancel_block()
    g = ranges(b)
    block = {
        "preregistration": prereg("gap_1_and_11_cancel_consumption"),
        "commands": PROVIDER_CMDS + SESSION_CMDS,
        "raw_outputs": cite(*CODEX_RUNS, *CLAUDE_RUNS, "claude-session.usage-excerpt.jsonl", "codex-home__config.toml",
                            "serve.sh", "vllm.log", "dl.log", "codex-session-attempt1.json"),
        "results": {**b,
                    "reading": f"Provider-side consumption of each interrupted request is now measured (Codex SDK: "
                               f"{g['codex_prompt']} prompt and {g['codex_gen']} generated tokens; Claude Agent SDK: "
                               f"{g['claude_prompt']} prompt and {g['claude_gen']} generated tokens; {len(b['codex_sdk'])} "
                               "trials per SDK). No client channel reports the generated tokens: the Codex "
                               "thread/tokenUsage notification and the rollout's last token_count (written just before "
                               "turn_aborted) repeat the pre-interrupt total; the Claude ResultMessage usage is 0/0, its model_usage equals the "
                               "completed turn-1 requests only, and the session JSONL keeps the interrupted message's "
                               "input count (equal to the provider's prompt count) with output 0. This supports the round-3 "
                               "inference that model_usage leaves the interrupted request out.",
                    "account_use": "none: the fresh CODEX_HOME has no auth.json (account/read: account null, "
                                   "requiresOpenaiAuth false); Claude ran with a dummy key, temp HOME and CLAUDE_CONFIG_DIR "
                                   "(apiKeySource ANTHROPIC_API_KEY)",
                    "attempt_1": "The first Codex session (14:20Z) failed: the small model refused the essay prompt, so "
                                 "turn 2 ended before the interrupt (JSON-RPC 'no active turn to interrupt'). The prompt "
                                 "was changed to a long listing for both SDKs before any Claude run; the attempt is retained."},
        "evidence_class": "local_integration",
        "limits": [LOCAL_LIMIT,
                   "Provider consumption is a vLLM counter on one host; it does not say how OpenAI or Anthropic bill an "
                   "aborted stream.",
                   "Six trials per SDK (three first-pass, three tapped fix-round reruns); the Codex prompt carries about 10.8k tokens of Codex system prompt and tools, the "
                   "Claude CLI about 0.5k with tools=[] and setting_sources=[], so the two SDKs' prompt counts are not "
                   "comparable."],
        "checked_at": iso(max(raw(n)["finished_at"] for n in CODEX_RUNS + CLAUDE_RUNS + OH_RUNS + OH_EARLIER)),
    }
    remaining = ("Hosted-provider consumption for an interrupted turn (OpenAI and Anthropic usage or billing data finer "
                 "than integer usedPercent). Round 4 measured it at a local provider only; the SDK and native-log "
                 "comparison is done for both SDKs.")
    limits = ["Hosted consumption on interruption is still not observable here: subscription sign-in exposes no usage "
              "API beyond integer usedPercent, and paid APIs are excluded (round 1).",
              "Round 4 shows, at a local provider, that the interrupted request's generated tokens reach no SDK or "
              "native-log channel in either SDK; the same omission for the hosted services is an inference."]
    return block, "advanced", remaining, limits


def gap9() -> tuple[dict, str, str | None, list]:
    cx, cl = raw("codex-session.json"), raw("claude-session.json")
    cxr, clr = raw("codex-resume.json"), raw("claude-resume.json")
    cxrf, clrf = raw("codex-resume-fix1.json"), raw("claude-resume-fix1.json")
    cx_taps = {n: raw(n)["tap"] for n in CODEX_FIX + ("codex-resume-fix1.json",)}
    cl_taps = {n: raw(n)["tap"] for n in CLAUDE_FIX + ("claude-resume-fix1.json",)}
    reps_cx = [raw(n)["turn1"]["tool_round_trip"] for n in CODEX_RUNS]
    reps_cl = [raw(n)["turn1"]["tool_round_trip"] for n in CLAUDE_RUNS]
    check = {
        "structured_events_typed": {
            "method": "fix round: every Codex notification tapped before routing (MessageRouter.route_notification) and "
                      "every raw Claude CLI message tapped before parsing (message_parser.parse_message); untyped = "
                      "UnknownNotification (Codex) or dropped as None (Claude)",
            "codex": all(not t["tapped_untyped"] and not t["tapped_undocumented"] for t in cx_taps.values()),
            "claude": all(not t["dropped_or_untyped"] for t in cl_taps.values()),
            "detectors_fire": {"codex": all(all(t["detector"].values()) for t in cx_taps.values()),
                               "claude": all(t["detector"]["unknown_type_dropped_as_none"] for t in cl_taps.values())},
            "tapped_totals": {"codex": {n: t["tapped_total"] for n, t in cx_taps.items()},
                              "claude": {n: t["raw_total"] for n, t in cl_taps.items()}},
            "claude_raw_kinds": sorted({k for t in cl_taps.values() for k in t["raw_counts"]}),
            "first_pass_turn_routed_only": {
                "codex_untyped": sorted({m for n in CODEX_FIRST for m in raw(n)["turn1"]["untyped_methods"] + raw(n)["turn2_interrupt"]["untyped_methods"]} | set(cxr["untyped_methods"])),
                "claude_untyped": sorted({m for n in CLAUDE_FIRST for m in raw(n)["turn1"]["untyped"] + raw(n)["turn2_interrupt"]["untyped"]} | set(clr["untyped"])),
                "note": "first-pass collectors saw only turn-routed Codex notifications and only messages the Claude "
                        "SDK yielded (the review's finding 2); kept for reference, not used for the outcome"}},
        "custom_tool_round_trip": {"codex": all(reps_cx), "claude": all(reps_cl),
                                   "trials": {"codex": reps_cx, "claude": reps_cl}},
        "mid_turn_interrupt": {"codex": [codex_cancel(n)["turn_status"] for n in CODEX_RUNS],
                               "claude": [claude_cancel(n)["terminal_reason"] for n in CLAUDE_RUNS],
                               "provider_request_ended": all(codex_cancel(n)["running_at_settle1"] == 0 for n in CODEX_RUNS)
                                                         and all(claude_cancel(n)["running_at_settle1"] == 0 for n in CLAUDE_RUNS)},
        "resume_recall_new_process": {
            "codex": cxr["resume_recall"] and cxrf["resume_recall"], "claude": clr["resume_recall"] and clrf["resume_recall"],
            "runs": {"codex": [cxr["resume_recall"], cxrf["resume_recall"]], "claude": [clr["resume_recall"], clrf["resume_recall"]]},
            "detail": {"codex": {k: cxr[k] for k in ("resumed_same_thread", "answer_contains_turn1_value",
                                                     "answer_contains_decoy", "tool_calls_in_resume")},
                       "claude": {k: clr[k] for k in ("resumed_same_session", "answer_contains_turn1_value",
                                                      "answer_contains_decoy", "tool_calls_in_resume")},
                       "new_process": {"codex": cxr["pid"] != cx["pid"] and cxrf["pid"] != raw("codex-session-fix1.json")["pid"],
                                       "claude": clr["pid"] != cl["pid"] and clrf["pid"] != raw("claude-session-fix1.json")["pid"]}}},
    }
    ok = (check["structured_events_typed"]["codex"] and check["structured_events_typed"]["claude"]
          and all(check["structured_events_typed"]["detectors_fire"].values())
          and check["custom_tool_round_trip"]["codex"] and check["custom_tool_round_trip"]["claude"]
          and all(s == "interrupted" for s in check["mid_turn_interrupt"]["codex"])
          and all(s == "aborted_streaming" for s in check["mid_turn_interrupt"]["claude"])
          and check["mid_turn_interrupt"]["provider_request_ended"]
          and check["resume_recall_new_process"]["codex"] and check["resume_recall_new_process"]["claude"]
          and all(check["resume_recall_new_process"]["detail"]["new_process"].values()))
    block = {
        "preregistration": prereg("gap_9_matched_comparison"),
        "commands": PROVIDER_CMDS + SESSION_CMDS + RESUME_CMDS,
        "raw_outputs": cite(*CODEX_RUNS, *CLAUDE_RUNS, "codex-resume.json", "claude-resume.json", "claude-resume.stderr",
                            "codex-resume-fix1.json", "claude-resume-fix1.json", "claude-fix.stderr",
                            "codex-home__config.toml"),
        "results": {
            "checklist": check, "all_items_pass_both_sdks": ok,
            "task": "one fixed task for both SDKs: turn 1 calls vault_lookup(key=alpha) and replies with its random "
                    "value; turn 2 asks for a long listing and is interrupted about 4 s after the first text delta; a new "
                    "process resumes the thread/session with a decoy tool value and asks for the turn-1 value",
            "registration": {"codex": "thread/start dynamicTools (item/tool/call answered by the SDK approval handler)",
                             "claude": "create_sdk_mcp_server in-process tool, allowed_tools=['mcp__vault__vault_lookup'], "
                                       "tools=[] (no built-in tools), setting_sources=[]"},
            "event_type_counts": {"codex_turn1": cx["turn1"]["method_counts"], "codex_turn2": cx["turn2_interrupt"]["method_counts"],
                                  "claude_turn1": cl["turn1"]["event_counts"], "claude_turn2": cl["turn2_interrupt"]["event_counts"]},
            "claude_init": cl.get("init"),
            "observations": ["Claude's init listed only the SDK tool and the in-process 'vault' server (no account MCP "
                             "server, unlike round 1 on the native sign-in).",
                             "The Claude CLI printed '[claude-code:unrecognized_model]' for qwen3-4b (claude-resume.stderr) "
                             "and proceeded.",
                             "Both SDKs' completed-request usage equals the provider counters (receipt 1, round_4.detector)."],
        },
        "evidence_class": "local_integration",
        "limits": [LOCAL_LIMIT,
                   "Tool round trip and interrupt ran in six trials per SDK (three tapped); resume ran twice per SDK "
                   "(one tapped).",
                   "The Claude tap sees the message stream the SDK parses; the CLI's control-protocol messages are "
                   "handled before parsing and are not part of it.",
                   "The checklist is the round-1 checklist (typed events, custom-tool round trip, interrupt status, "
                   "resume recall); it does not score latency or cost."],
        "checked_at": iso(max(raw(n)["finished_at"] for n in CODEX_RUNS + CLAUDE_RUNS + (
            "codex-resume.json", "claude-resume.json", "codex-resume-fix1.json", "claude-resume-fix1.json"))),
    }
    limits = [LOCAL_LIMIT + " Hosted-model pairings (gpt-6-astra with Codex, a Claude model with the Claude Agent SDK) "
              "are not compared here; round 1's hosted Codex arm and single hosted Claude interrupt remain the only "
              "hosted observations.",
              "Claude Code 2.1.280 flags the model as unrecognized; features that depend on Claude model identity "
              "(thinking blocks, for example) are not exercised."]
    return block, ("settled" if ok else "advanced"), (None if ok else "see round_4.results.checklist"), limits


GPU_FILES = ("gpu-before.txt", "gpu-after.txt", "gpu-before-fix.txt", "gpu-after-fix.txt", "gpu-before-fix2.txt",
             "gpu-during-fix2.txt", "gpu-after-fix2.txt", "gpu-after-fix2-manual.at", "gpu-after-fix2-manual.txt",
             "compute-apps-before-fix2.txt", "compute-apps-during-fix2.txt", "compute-apps-after-fix2.txt",
             "compute-apps-after-fix2-manual.txt", "vllm-procs-before-fix2.txt", "vllm-procs-after-fix2.txt",
             "oh-server-procs-after-fix2.txt", "vllm-pid-fix2.txt", "vllm-start-fix2.txt", "vllm-ready-fix2.txt",
             "vllm-stop-fix2.txt", "fix2-manual-stop.txt", "vllm-stop-fix2-manual.txt", "vllm-procs-after-fix2-manual.txt",
             "oh-server-procs-after-fix2-manual.txt", "procs-after-fix2-recheck.txt", "vllm-fix2.log")


def gpu_stop_rule() -> dict:
    """Preregistered stop rule (round 4): the vLLM server is stopped and its GPU memory release is checked."""
    def mib(name: str) -> int:
        return int((RAW4 / name).read_text().split()[0])

    b, d, a_script, a_manual = mib("gpu-before-fix2.txt"), mib("gpu-during-fix2.txt"), mib("gpu-after-fix2.txt"), mib("gpu-after-fix2-manual.txt")
    recheck = (RAW4 / "procs-after-fix2-recheck.txt").read_text()
    apps_rows = {n: [ln for ln in (RAW4 / n).read_text().splitlines()[1:] if ln.strip()]
                 for n in ("compute-apps-before-fix2.txt", "compute-apps-during-fix2.txt", "compute-apps-after-fix2.txt",
                           "compute-apps-after-fix2-manual.txt")}
    rise, fall = d - b, d - a_manual
    process_gone = ("1146122 absent" in recheck and "1155940 absent" in recheck
                    and recheck.split("pgrep [v]llm serve Qwen3-4B:")[1].split("pgrep")[0].strip() == "none")
    evaluated = process_gone and rise > 0 and fall >= 0.8 * rise
    return {
        "first_stop_14_37_38Z": {"before_mib": mib("gpu-before.txt"), "after_mib": mib("gpu-after.txt"),
                                 "evaluation": "aggregate pair only (no reading while the server ran); cannot confirm release"},
        "review_fix_stop_15_03_19Z": {"before_mib": mib("gpu-before-fix.txt"), "after_mib": mib("gpu-after-fix.txt"),
                                      "evaluation": "aggregate pair only; after is 232 MiB above before, which these readings "
                                                    "cannot attribute (other GPU users, including the host's embedding vLLM, "
                                                    "share the card; with no unit server running the total was "
                                                    f"{b} MiB at 15:46:08Z). The rule was not evaluated at the time and "
                                                    "cannot confirm release for this stop. After the fact, "
                                                    "vllm-procs-before-fix2.txt (pgrep for the unit's model path at "
                                                    "15:46:08Z) is 'none', so that server process had exited by then."},
        "second_fix_stop": {
            "before_mib": b, "during_mib": d, "after_script_stop_mib": a_script, "after_manual_stop_mib": a_manual,
            "after_manual_stop_at": (RAW4 / "gpu-after-fix2-manual.at").read_text().strip(),
            "rise_mib": rise, "fall_mib": fall,
            "criterion": "the unit's vLLM process is gone and memory.used falls back by at least 80% of the during-minus-before rise",
            "unit_vllm_and_agent_server_processes_gone": process_gone,
            "released_in_aggregate": evaluated,
            "script_stop_failure": "r4_fix2_remote.sh's stop step selected pid 1146119, most likely pasta (/usr/bin/pasta "
                                   "re-execs /usr/bin/pasta.avx2, so its comm was not 'pasta' and the comm filter did not "
                                   "skip it; inference, the comm was not recorded). The vLLM api-server kept running "
                                   "(vllm-procs-after-fix2.txt, gpu-after-fix2.txt at 18424 MiB) and the script's "
                                   "vllm-stop-fix2.txt time is when its wait loop gave up, not a stop. The api-server "
                                   "(1146122) and agent-server (1155940) were then stopped by pid at 15:49:59Z, about 2 min 43 s after the "
                                   "conversation finished (15:47:16Z). The script's agent-server kill had also missed: its pid file "
                                   "held 1155939, the setsid launcher, not the server (1155940). While both kept running, the host "
                                   "listeners stayed 127.0.0.1:28431 and 127.0.0.1:28432 only (fix2-listeners-after.txt); after pasta "
                                   "exited, an ss -ltnp call attributed the forwarded 127.0.0.1:28431 socket to the vllm process (printed "
                                   "to the terminal only, not a retained file). vllm-fix2.log "
                                   "shows '[shutdown] API server: shutdown triggered' at 11:49:59 local time (15:49:59Z). "
                                   "The manual wait loop then self-matched its own pgrep pattern and timed out after 120 s "
                                   "(fix2-manual-stop.txt 'wait exit 124'; vllm-procs-after-fix2-manual.txt and "
                                   "oh-server-procs-after-fix2-manual.txt list only that shell). procs-after-fix2-recheck.txt "
                                   "is the valid check: /proc entries for both pids absent and a non-self-matching pgrep "
                                   "('[v]llm serve .*Qwen3-4B') returns none.",
            "per_process_attribution": {"method": "nvidia-smi --query-compute-apps", "rows": apps_rows,
                                        "note": "On this WSL host the query lists no row for the host's running embedding "
                                                "vLLM, and while the unit's server ran it listed only '114, [Not Found], [N/A]' "
                                                "(no name or memory). That row appeared only while the unit's server ran and "
                                                "was gone after the manual stop, but it cannot be tied to the process, so "
                                                "per-process release is not attributable here."}},
        "limit": "Aggregate memory.used is shared by every GPU user on the host; the second-fix pair shows a fall matching "
                 "the rise, which is consistent with release, not a per-process proof.",
    }


def gap8() -> tuple[dict, str, str | None, list]:
    loc, rem, con = raw("openhands-local.json"), raw("openhands-remote-fix2.json"), raw("openhands-container-fix.json")
    con1, rem1 = raw("openhands-container.json"), raw("openhands-remote.json")
    gpu_rule = gpu_stop_rule()
    att = raw("openhands-local-attempt1.json")
    proof = (RAW4 / "podman-exec-proof-fix.txt").read_text()
    before = set((RAW4 / "fix-listeners-before.txt").read_text().split())
    during = set((RAW4 / "fix-listeners-during.txt").read_text().split())
    during2 = set((RAW4 / "fix-listeners-during2.txt").read_text().split())
    inside = (RAW4 / "fix-container-listeners.txt").read_text().split("\n")
    clog = (RAW4 / "podman-container-fix.log").read_text()
    listen = {"host_added_at_server_start": sorted(during - before), "host_removed_at_server_start": sorted(before - during),
              "host_added_after_conversation": sorted(during2 - before),
              "container_listeners": [ln for ln in inside if ln.strip()],
              "vscode_disabled_in_log": "VSCode is disabled in configuration" in clog,
              "vscode_started_in_log": "VSCode server started" in clog}
    listen_ok = (listen["host_added_at_server_start"] == ["127.0.0.1:28433"] and listen["host_added_after_conversation"] == ["127.0.0.1:28433"]
                 and not any(ln.split()[-1] == "8001" for ln in listen["container_listeners"])
                 and listen["vscode_disabled_in_log"] and not listen["vscode_started_in_log"])
    def pick(d):
        return {k: d.get(k) for k in ("status", "conversation_class", "execution_status", "tool_names",
                                      "proof_file_has_token", "workspace_cat", "sdk_metrics", "provider_delta")}
    ok = (all(d["status"] == "ok" and d["execution_status"].endswith("FINISHED") and d["proof_file_has_token"]
              for d in (loc, rem, con))
          and rem.get("conversation_class") == "RemoteConversation" and con.get("conversation_class") == "RemoteConversation"
          and all((d.get("workspace_cat") or {}).get("stdout_has_token") for d in (rem, con))
          and all(d["provider_delta"]["vllm:generation_tokens_total"] > 0 for d in (loc, rem, con))
          and listen_ok and proof.strip().startswith("oh-r4-"))
    block = {
        "preregistration": prereg("gap_8_openhands_real_model"),
        "commands": PROVIDER_CMDS + [
            f"{OH_ENV} {H}/r4_openhands.py local {R}/oh-ws-local2 {R}/oh-persist2 {R}/openhands-local.json  # exit 0",
            f"ECOSYSTEM_JOB_SECONDS=900 $HOME/codex-ecosystem/bin/ecosystem-bounded-run bash -c \"uv venv --python "
            f"$HOME/.local/share/codex-ecosystem/bin/python3.13 --no-python-downloads {C}/oh-agent-server && "
            f"UV_CACHE_DIR={C}/uv-cache uv pip install --python {C}/oh-agent-server/bin/python --default-index "
            "https://pypi.org/simple 'openhands-agent-server==1.49.4' 'openhands-sdk==1.49.4' 'openhands-tools==1.49.4'\"  # exit 0, 490 MB prefix",
            f"(cwd {R}/oh-server-cwd) env -i PATH={C}/oh-agent-server/bin:/usr/bin:/bin HOME={R}/oh-server-home "
            f"OPENHANDS_SUPPRESS_BANNER=1 LITELLM_LOCAL_MODEL_COST_MAP=True {C}/oh-agent-server/bin/agent-server --host 127.0.0.1 --port 28432",
            f"(run 1, pre-commit working-tree revision of r4_openhands.py without the workspace read-back; not the committed script) "
            f"{OH_ENV} {H}/r4_openhands.py remote {R}/oh-ws-remote {R}/oh-persist-remote-unused {R}/openhands-remote.json http://127.0.0.1:28432  # exit 0",
            f"(second review fix, cited remote run) bash {H}/r4_fix2_remote.sh  # committed in 994c085 before running; "
            "restarts serve.sh, starts a fresh agent-server on 127.0.0.1:28432 with the same env -i command (cwd "
            f"{R}/oh-server-cwd-fix2, HOME {R}/oh-server-home-fix2) and runs {OH_ENV} {H}/r4_openhands.py remote "
            f"{R}/oh-ws-remote-fix2 {R}/oh-persist-remote-unused {R}/openhands-remote-fix2.json http://127.0.0.1:28432 "
            "with the committed script (git hash-object d9360477c09e..., equal to HEAD's blob); driver exit 0, r4_openhands exit 0",
            "(second review fix, manual stop after the script's stop step failed) kill -TERM 1146122 1155940  # vLLM api-server and agent-server pids from ps, 15:49:59Z",
            f"ECOSYSTEM_JOB_SECONDS=1200 $HOME/codex-ecosystem/bin/ecosystem-bounded-run {PODMAN} pull "
            "ghcr.io/openhands/agent-server@sha256:5b84b74a821dff19fc49ca157f284c0b4c9bd5b8623e468b17f57b22dee81061  "
            "# tag 1.49.4-python, amd64; 1168 MB compressed download from ghcr.io, 3.1 GB on disk; exit 0",
            f"(run 1, rule deviation) {PODMAN} run -d --name r4-oh-agent-server --network host c8abc05c6d73 --host 127.0.0.1 --port 28433  # exit 0; VSCode bound 0.0.0.0:8001 on the host network",
            f"(run 1) {OH_ENV} {H}/r4_openhands.py container /tmp/r4ws {R}/oh-persist-container-unused {R}/openhands-container.json http://127.0.0.1:28433  # exit 0",
            f"(run 1) {PODMAN} exec r4-oh-agent-server sh -c 'cat /tmp/r4ws/proof.txt; hostname'; {PODMAN} stop -t 10 r4-oh-agent-server; {PODMAN} rm r4-oh-agent-server",
            "(fix round) ss -ltnH | awk '{print $4}' | sort > fix-listeners-before.txt",
            f"(fix round) {PODMAN} run -d --name r4-oh-fix --network pasta:-T,28431 -p 127.0.0.1:28433:8000 -e OH_ENABLE_VSCODE=false c8abc05c6d73 --host 0.0.0.0 --port 8000  # exit 0",
            "(fix round) ss -ltnH | awk '{print $4}' | sort > fix-listeners-during.txt  # and fix-listeners-during2.txt after the conversation",
            f"(fix round) {PODMAN} exec r4-oh-fix python3 -c '<list LISTEN sockets from /proc/net/tcp and tcp6>' > fix-container-listeners.txt",
            f"(fix round) {OH_ENV} {H}/r4_openhands.py container /tmp/r4ws {R}/oh-persist-container-unused {R}/openhands-container-fix.json http://127.0.0.1:28433  # exit 0",
            f"(fix round) {PODMAN} exec r4-oh-fix sh -c 'cat /tmp/r4ws/proof.txt; hostname'  # exit 0 -> podman-exec-proof-fix.txt",
            "ls /tmp/r4ws  # on the host: No such file or directory (the file exists only in the container)",
            f"(fix round) {PODMAN} logs r4-oh-fix > podman-container-fix.log; {PODMAN} stop -t 10 r4-oh-fix; {PODMAN} rm r4-oh-fix; podman unshare rm -rf /tmp/r4p.XXXX",
            "kill -TERM <agent-server pid>  # the loopback agent-server process",
        ],
        "raw_outputs": cite("openhands-local.json", "openhands-local-attempt1.json", "openhands-remote.json",
                            "openhands-remote-fix2.json", "openhands-remote-fix2.exit", "r4_openhands-hash-fix2.txt",
                            "fix2-driver.log", "fix2-listeners-before.txt", "fix2-listeners-during.txt",
                            "fix2-listeners-after.txt", "fix2-listeners-after-manual.txt", *GPU_FILES,
                            "openhands-container.json", "podman-exec-proof.txt", "podman-pull.log", "podman-run.log",
                            "podman-container.log", "oh-agent-server-install.log", "openhands-container-fix.json",
                            "podman-exec-proof-fix.txt", "podman-run-fix.log", "podman-container-fix.log",
                            "fix-listeners-before.txt", "fix-listeners-during.txt", "fix-listeners-during2.txt",
                            "fix-container-listeners.txt"),
        "results": {
            "local": pick(loc), "remote_agent_server_process": pick(rem), "official_container": pick(con),
            "remote_run_1": {**pick(rem1), "provenance": "openhands-remote.json (14:30:50-14:31:03Z) was produced by a "
                             "working-tree revision of r4_openhands.py that predates the committed one (first committed in "
                             "69fa1bb at 14:43:17Z, never changed since). The committed script always writes workspace_cat or "
                             "workspace_cat_error for a non-local run that ends ok; this output has neither, so the workspace "
                             "read-back was not run in run 1. Found by the independent Opus review of the round-4 fix round. "
                             "Run 1 is retained; the cited remote run is the second-fix rerun (openhands-remote-fix2.json), "
                             "which used the committed script."},
            "remote_listeners_second_fix": {
                "host_added_during": sorted(set((RAW4 / "fix2-listeners-during.txt").read_text().split())
                                            - set((RAW4 / "fix2-listeners-before.txt").read_text().split())),
                "host_after_manual_stop_equals_before": (RAW4 / "fix2-listeners-after-manual.txt").read_text()
                                                        == (RAW4 / "fix2-listeners-before.txt").read_text()},
            "provider_stop_rule_gpu": gpu_rule,
            "container_image": {"ref": "ghcr.io/openhands/agent-server:1.49.4-python", "amd64_digest":
                                "sha256:5b84b74a821dff19fc49ca157f284c0b4c9bd5b8623e468b17f57b22dee81061",
                                "image_id_prefix": "c8abc05c6d73", "user": "openhands (uid 10001)",
                                "build_git_ref": "refs/tags/v1.49.4"},
            "container_proof_via_podman_exec": proof.strip().startswith("oh-r4-"),
            "container_listeners_fix_round": listen, "container_listeners_ok": listen_ok,
            "container_run_1": {**pick(con1), "rule_deviation": "run 1 used --network host; the image's VSCode service "
                                "started on 0.0.0.0:8001 in the host network namespace for about a minute (podman-container.log: "
                                "'VSCode server started successfully on port 8001'). The fix-round rerun replaces it as evidence."},
            "attempt_1": {"tool_names": att["tool_names"], "proof_file_has_token": att["proof_file_has_token"],
                          "note": "The model first tried /proof.txt (permission denied), then wrote ~/proof.txt in the "
                                  "temp HOME; the prompt then named the absolute target path. Model-quality failure, retained."},
            "all_three_real_model_conversations_ok": ok,
            "round_1_langgraph_temporal": "unchanged (receipt results above): LangGraph SQLite checkpoint resumed in a new "
                                          "process; Temporal worker SIGKILL, restart and clean replay with a flagged negative control.",
        },
        "evidence_class": "local_integration",
        "limits": [LOCAL_LIMIT,
                   "The cited container run (fix round) used rootless podman's pasta network: only 127.0.0.1:28433 was "
                   "published on the host, the container reached the model through a pasta -T 28431 forward, and VSCode "
                   "was disabled (OH_ENABLE_VSCODE=false). OpenHands' DockerWorkspace class was not used: the image was "
                   "started by podman directly and reached through Workspace(host=...).",
                   "Exit codes 0 were observed in the shell for every command above; the JSON outputs record status ok, which "
                   "r4_openhands.py maps to exit 0. There is no separate exit-code file for round 4 except the "
                   "second-fix remote rerun (openhands-remote-fix2.exit, fix2-driver.log).",
                   "The provider stop-rule readings are aggregate memory.used values; see "
                   "round_4.results.provider_stop_rule_gpu for all three stops and the failed scripted stop.",
                   "The agent-server console log and the client stderr files are not exported (rich console wrapping)."],
        "checked_at": iso(max(d["finished_at"] for d in (loc, rem, con, con1, rem1))),
        "rule_deviations": [
            "vLLM launch 3 (about 14:16-14:18Z) ran on the host network; its engine's torch-distributed store listened on a "
            "wildcard port until it was stopped and relaunched inside a pasta namespace (vllm-attempt3-hostnet.log).",
            "Container run 1 (about 14:32:35-14:33:25Z) exposed the image's VSCode service on 0.0.0.0:8001 through "
            "--network host; found by the cross-family review, rerun in the fix round."],
    }
    limits = [LOCAL_LIMIT,
              "OpenHands ran with a 4B open-weight model; round 1's TestLLM run remains the persistence-reload evidence.",
              "LangGraph ran without a model (checkpointing only); Temporal ran on one host (see receipt 11 for the "
              "round-4 paused-worker test)."]
    return block, ("settled" if ok else "advanced"), (None if ok else "see round_4.results"), limits


def gap10() -> dict:
    e1, e2 = raw("codex-events.json"), raw("codex-events2.json")
    r3 = json.loads((EV / "raw/round3/events-turn.json").read_text())["received_documented"]
    union = sorted(set(r3) | set(e1["received_documented"]) | set(e2["received_documented"]))
    return {
        "preregistration": prereg("gap_10_more_native_types"),
        "commands": PROVIDER_CMDS + [
            f"{CODEX_PY} {H}/r4_codex.py events --codex-bin {CODEX_BIN} --codex-home {R}/codex-home --workspace "
            f"{R}/ws-codex-events --state {R}/private/events-state.json --out {R}/codex-events.json",
            f"{CODEX_PY} {H}/r4_codex.py events2 --codex-bin {CODEX_BIN} --codex-home {R}/codex-home --workspace "
            f"{R}/ws-codex-events2 --state {R}/private/events2-state.json --out {R}/codex-events2.json --deadline 240"],
        "raw_outputs": cite("codex-events.json", "codex-events2.json"),
        "results": {
            "events": {k: e1.get(k) for k in ("received_documented_count", "received_documented", "untyped_methods",
                                              "steps", "notes_txt_created")},
            "events2": {k: e2.get(k) for k in ("received_documented_count", "received_documented", "untyped_methods",
                                               "received_undocumented", "steps", "other_server_requests", "collector")},
            "union_rounds_3_4": {"count": len(union), "of": e2["documented_types"], "types": union,
                                 "not_received": e2["documented_types"] - len(union)},
            "untyped_in_round_4": sorted(set(e1["untyped_methods"]) | set(e2["untyped_methods"])),
            "not_received_note": "Not received: account/login and account/updated, authRecovery, oauth and "
                                 "externalAgentConfig (need a sign-in or would read the real ~/.claude), 13 realtime "
                                 "types (audio session), 2 Windows types, guardian/autoApprovalReview/safety/moderation/"
                                 "model reroute and verification (hosted-model features), reasoning deltas (the local "
                                 "model emits none), hook/*, mcpServer/event stream and mcpToolCall/progress (no hook or "
                                 "MCP server configured in the fresh home), plan/diff/fileChange/commandExecution item "
                                 "deltas (the model did not call update_plan; apply_patch and shell ran without them in "
                                 "this run), thread/compacted (compaction ran, the notification did not arrive), "
                                 "thread/closed, thread/reverted (rollback refused: 'paginated threads do not support "
                                 "thread/rollback'), project/changed and thread/project/updated (project/create "
                                 "rejected the roots shape), thread/attachment/updated and thread/environment/*.",
        },
        "remaining": f"Native receipt of the other {e2['documented_types'] - len(union)} documented notification types "
                     "(listed in round_4.results.union_rounds_3_4 by complement), several of which need a signed-in "
                     "account, a realtime session, Windows, hooks or an MCP server.",
        "evidence_class": "local_integration",
        "limits": ["The events2 collector wraps the SDK's private MessageRouter.route_notification to see turn-routed "
                   "notifications of turns the script never subscribed to; it observes what the SDK receives, but it "
                   "uses a private attribute.",
                   "The Codex app-server in the `events` phase ran with the parent HOME (CODEX_HOME was fresh); "
                   "`events2` set HOME to a temp directory.",
                   LOCAL_LIMIT],
        "checked_at": iso(e2["finished_at"]),
    }


def gap11() -> tuple[dict, str, str, list]:
    z1, z2 = raw("temporal-zombie-run1.json"), raw("temporal-zombie.json")
    b = cancel_block()
    block = {
        "preregistration": {"cancel": prereg("gap_1_and_11_cancel_consumption"), "zombie": prereg("gap_11_zombie_worker")},
        "commands": PROVIDER_CMDS + SESSION_CMDS + [
            f"ECOSYSTEM_JOB_SECONDS=600 $HOME/codex-ecosystem/bin/ecosystem-bounded-run {C}/temporal/bin/python "
            f"{H}/temporal_zombie.py controller {R}/temporal-zombie {C}/tmp-VB16/cli {R}/temporal-zombie.json  "
            "# run 2 (cited); run 1 used the first revision of the activity, output temporal-zombie-run1.json"],
        "raw_outputs": cite("temporal-zombie.json", "temporal-zombie__worker-A.err",
                            "temporal-zombie-run1.json", "temporal-zombie-run1__worker-A.err",
                            *CODEX_RUNS, *CLAUDE_RUNS),
        "results": {
            "cancel_consumption": {k: b[k] for k in ("all_consumption_stopped", "all_running_zero_at_settle1", "detector",
                                                     "sampling_note")},
            "cancel_per_run": {"codex_sdk": [{k: r[k] for k in ("turn_status", "provider_interrupted_request",
                                                               "generation_settle1_to_settle2", "running_at_settle1")}
                                             for r in b["codex_sdk"]],
                               "claude_agent_sdk": [{k: r[k] for k in ("terminal_reason", "provider_interrupted_request",
                                                                      "generation_settle1_to_settle2", "running_at_settle1")}
                                                    for r in b["claude_agent_sdk"]]},
            "zombie_run_2": {"checks": z2["checks"], "result": z2["result"], "attempts": z2["attempts"],
                             "writes": z2["writes"], "effects": z2["effects"], "effects_nokey_rows": len(z2["effects_nokey"]),
                             "workflow_status_after_resume": z2["workflow_status_after_resume"],
                             "worker_a_log": z2["worker_a_log_lines_mentioning_completion_or_not_found"],
                             "replay_failure": z2["replay_failure"]},
            "zombie_run_2_reading": "While worker A was frozen, the server timed out attempt 1 (heartbeat timeout 3 s) and "
                                    "handed attempts 2 and 3 to A's already-open poll, where they also timed out; attempt 4 "
                                    "ran on worker B and completed the workflow. After SIGCONT, A executed the stale "
                                    "attempts 1, 2 and 3: every keyed write was refused (keyed_applied 0, 1 keyed row) while "
                                    "the unkeyed control gained 4 duplicate rows (5 total). Attempt 1 wrote twice because a "
                                    "cancellation landed after its commit and the harness retry ran again (a harness "
                                    "artifact, also refused). Worker A's log shows the SDK completing the stale attempts 2 "
                                    "and 3 as failed after a worker-side CancelledError; the server's response to those late "
                                    "completions was not observed. The history holds one activity scheduled/started/"
                                    "completed triple, the workflow result is attempt 4 from worker B, and the replay is clean.",
            "retry_on_worker_b": {"attempt": int(z2["result"]["activity"].split("attempt=")[1].split()[0]),
                                  "pid_is_worker_b": f"pid={z2['worker_b_pid']}" in z2["result"]["activity"],
                                  "note": "the raw check key 'attempt2_on_worker_b' tests attempt >= 2 on worker B; the "
                                          "retry that ran there was attempt 4"},
            "zombie_run_1": {"checks": z1["checks"], "writes": z1["writes"], "effects_nokey_rows": len(z1["effects_nokey"]),
                             "reading": "First revision (no retry of the stale write): after SIGCONT the SDK injected a "
                                        "CancelledError into A's resumed thread inside the effect transaction, which rolled "
                                        "back before commit, so no stale write landed and the unkeyed control stayed at 1 row. "
                                        "The detector could not fire in that run; run 2 makes the stale write land."},
        },
        "evidence_class": "local_integration",
        "limits": [LOCAL_LIMIT,
                   "SIGSTOP/SIGCONT on one host stands in for a partition or pause; no second host, network partition "
                   "between hosts, clock skew or server failover was tested.",
                   "Effectively-once comes from the idempotency key in one SQLite store; the server does not prevent a "
                   "zombie from executing its side effect (run 2).",
                   "Whether the server rejected worker A's late completions is not observed; only the worker-side log and "
                   "the unchanged history are."],
        "checked_at": iso(max(z2["worker_a_resumed_at"],
                              max(raw(n)["finished_at"] for n in CODEX_RUNS + CLAUDE_RUNS + OH_RUNS + OH_EARLIER))),
    }
    remaining = ("Hosted-provider billing cessation for an interrupted turn, and recovery across real hosts (network "
                 "partition, server failover). Round 4 showed consumption stopping at a local provider for both SDKs and "
                 "effectively-once effects under a paused worker on one host.")
    limits = ["Hosted billing is not observable here (no billing API, integer usedPercent).",
              "Distributed recovery is shown only on one host (SIGKILL restart in round 1, SIGSTOP zombie in round 4).",
              "Exactly-once means one keyed effect row with at-least-once execution; the unkeyed control duplicates."]
    return block, "advanced", remaining, limits


def gap0() -> dict:
    return {"note": "Not run in round 4 (preregistered). The recovery needs 12 submissions on the Claude arms with Claude "
                    "models; the loopback open-weight provider cannot stand in for the protocol's arms, and the shared "
                    "Claude account stays reserved. comparison-progress-20260922/summary.json unchanged.",
            "preregistration": prereg("gap_0"), "checked_at": "2026-09-23T14:12:27Z"}


def apply() -> None:
    def load(prefix: str) -> tuple[Path, dict]:
        p = next(EV.glob(f"{prefix}-*.json"))
        return p, json.loads(p.read_text())

    def update(prefix, block, outcome, remaining, limits, evidence_class=None):
        p, r = load(prefix)
        r["round_4"] = block
        if outcome != r["outcome"]:
            r["pre_round_4_outcome"] = r["outcome"]
        r["pre_round_4_remaining"] = r.pop("remaining", None)
        r["pre_round_4_limits"] = r.pop("limits")
        r["outcome"], r["limits"] = outcome, limits
        if remaining:
            r["remaining"] = remaining
        if evidence_class and evidence_class != r["evidence_class"]:
            r["pre_round_4_evidence_class"] = r["evidence_class"]
            r["evidence_class"] = evidence_class
        r["checked_at"] = block["checked_at"]
        p.write_text(json.dumps(r, indent=2) + "\n")

    update("1", *gap1())
    b9, o9, rem9, lim9 = gap9()
    update("9", b9, o9, rem9, lim9, evidence_class="local_integration")
    if o9 == "settled":
        p, r = load("9")
        r["settled_scope"] = ("SDK-level comparison on one fixed task with the same open-weight model and loopback "
                              "provider for both SDKs; hosted-model pairings not compared")
        p.write_text(json.dumps(r, indent=2) + "\n")
    b8, o8, rem8, lim8 = gap8()
    update("8", b8, o8, rem8, lim8)
    if o8 == "settled":
        p, r = load("8")
        r["settled_scope"] = ("OpenHands with a local open-weight model (local, loopback agent-server and official "
                              "container image); LangGraph and Temporal on one host")
        p.write_text(json.dumps(r, indent=2) + "\n")
    b10 = gap10()
    p, r = load("10")
    r["pre_round_4_remaining"] = r["remaining"]
    r["remaining"] = b10.pop("remaining")
    r["round_4"] = b10
    r["checked_at"] = b10["checked_at"]
    p.write_text(json.dumps(r, indent=2) + "\n")
    update("11", *gap11())
    p, r = load("0")
    r["round_4"] = gap0()
    p.write_text(json.dumps(r, indent=2) + "\n")
