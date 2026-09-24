#!/usr/bin/env python3
"""Build the agent-sdks gap-wave-2 receipts from the committed raw outputs, then results.json.

Every quoted result is read from evidence/.../raw/ at build time; results.json is
derived from the receipts' outcome fields (never written by hand).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EV = ROOT / "evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks"
RAW = EV / "raw"
UNITS = Path(sys.argv[1])  # gap list (g2-units.json)
CHECKED_AT = "2026-09-23T04:23:16Z"
RECHECKED_AT = "2026-09-23T04:38:53Z"  # fix round 2: worker tool turn + resume (worker-tool-runs.json finished_at)
TOOL_TURN_DEVIATION = {
    "rule": "wait while 2 or more real codex exec processes run",
    "status": "unresolved",
    "observed": "The first Codex SDK model call (tool-turn.json, 03:24:59Z) started while pgrep counted 3 processes matching 'codex exec'. "
                "A substring count can include processes that are not codex exec runs (at 04:37Z a similar substring filter matched two "
                "codex-linux-sandbox helpers); the 3 were never classified, so the rule may have been broken for this call. Later calls waited; the fix-round-2 driver classifies by argv "
                "(worker-tool-runs.json slot_checks: 1 real codex exec before each call).",
}
B = "$HOME/.cache/gap-wave2-20260923/agent-sdks"
PY_CODEX = f"{B}/codex-sdk-01551/bin/python"
ENV = "env -i HOME=$HOME PATH=$HOME/.local/share/codex-ecosystem/bin:/usr/bin:/bin"
NATIVE = "--codex-bin $HOME/.local/share/codex-ecosystem/bin/codex --codex-home $HOME/.codex"
PROBE = "blueprints/gap-wave2-20260923/foundation__agent-sdks/codex_probe.py"
WORKER = "blueprints/us-equities/workers/native_worker.py"
ISO = ("--config-override features.hooks=false --config-override features.plugin_hooks=false "
       "--config-override features.apps=false --config-override 'otel.exporter=\"none\"' "
       "--config-override 'otel.metrics_exporter=\"none\"' --config-override analytics.enabled=false")
ISO_PLUGIN = ISO + " --config-override 'plugins={\"context-mode@context-mode\"={enabled=false}}'"
C4 = ISO + " --sandbox workspace-write --approval-mode auto_review"
CM_START = "--context-mode-start $HOME/.codex/plugins/cache/context-mode/context-mode/1.0.169/start.mjs"


def raw(name: str):
    text = (RAW / name).read_text()
    return json.loads(text) if name.endswith(".json") else text


def rsha(name: str) -> str:
    return hashlib.sha256((RAW / name).read_bytes()).hexdigest()


def cite(*names: str) -> list[dict]:
    return [{"path": f"raw/{n}", "sha256": rsha(n)} for n in names]


def gaps() -> dict[int, str]:
    units = json.loads(UNITS.read_text())
    unit = next(u for u in units if u.get("layer_id") == "agent-sdks")
    return {g["index"]: g["text"] for g in unit["gaps"]}


def turn_summary(name: str) -> dict:
    d = raw(name)
    commands = [i for i in d.get("items", []) if i.get("type") == "commandExecution"]
    return {"file": name, "status": d.get("status"), "sdk_version": d.get("sdk_version"),
            "thread_mode": d.get("thread_mode"), "sandbox": d.get("sandbox"), "approval_mode": d.get("approval_mode"),
            "final_response_excerpt": (d.get("final_response") or "")[:400],
            "tool_items": [{k: i.get(k) for k in ("server", "tool", "status")} for i in d.get("items", [])
                           if i.get("type") in ("mcpToolCall", "dynamicToolCall")],
            "command_items": {"count": len(commands),
                              "commands": [{"command": (i.get("command") or "")[:220], "exitCode": i.get("exitCode"),
                                            "status": i.get("status")} for i in commands]},
            "usage_total": (d.get("usage") or {}).get("total")}


def side_effects_listing(truns: dict) -> dict:
    """Evaluate the fix-round-2 side_effects preregistration against the before/after listing (reconciliation round)."""
    se = truns.get("side_effects") or {}
    cm, ss = se.get("context-mode") or {}, se.get("sessions") or {}
    changed = cm.get("changed") or []
    stats = [c for c in changed if c.startswith("sessions/stats-pid-")]
    return {
        "preregistered_expectation": "fix_round_2.items.side_effects (04:38:21Z): with the Context Mode plugin disabled, the listing of ~/.codex/context-mode shows no file attributable to these runs; ~/.codex/sessions gains or changes only this thread's rollout (other concurrent sessions may also change files).",
        "method": "name, size and mtime listing of $HOME/.codex/context-mode and $HOME/.codex/sessions before turn 1 and after turn 2 (worker-tool-runs.json side_effects, window "
                  f"{truns.get('started_at')} to {truns.get('finished_at')}). A listing records which files appeared or changed in the window, not which process wrote them.",
        "context_mode": {"added": cm.get("added"), "added_count": len(cm.get("added") or []), "removed_count": len(cm.get("removed") or []),
                         "changed_count": len(changed), "changed_stats_pid_files": stats, "changed_other_count": len(changed) - len(stats)},
        "sessions": {"added": ss.get("added"), "changed": ss.get("changed"), "own_rollout_files": truns.get("own_rollout_files"),
                     "own_rollout_match": "thread id from worker-tool-t1.json contained in the rollout file name (run_worker_tool.py)"},
        "result": {
            "context_mode": ("not evaluated by the listing: the tree changed during the window (see counts; other Codex and Claude sessions were active on the host), "
                             "and a name/size/mtime listing cannot attribute a file to a process, so it neither detects nor rules out a file written by these runs. "
                             "The reading that these runs wrote no Context Mode file is an inference from the per-process override that disabled the plugin "
                             "(plugins={\"context-mode@context-mode\"={enabled=false}} in both commands) and from neither turn recording an mcpToolCall or commandExecution item; the listing did not detect it."),
            "sessions": ("consistent with the expectation: the one added rollout carries this thread's id; the two changed rollouts are named 00-36-33 and 00-37-08 "
                         "local time (04:36:33Z and 04:37:08Z), before turn 1 created this thread, so they are other sessions' files. Content written by these runs into "
                         "another file would not be separable from that session's own writes.")}}


def extraction_ok(name: str) -> bool:
    """All six expected values present and none null in the turn's final JSON answer."""
    text = (raw(name).get("final_response") or "").strip().strip("`")
    text = text[text.find("{"):text.rfind("}") + 1] if "{" in text else ""
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        return False
    values = []
    for key, v in answer.items():
        if isinstance(v, dict):
            v = v.get("value")
        if key in ("tool", "tool_used", "unproved_alpaca_scope"):
            continue
        values.append(v)
    wanted = [3943, 3, 0, 23, "gpt-6-astra", 0]
    return None not in values and all(values.count(w) >= wanted.count(w) for w in set(wanted))


def build() -> list[dict]:
    texts = gaps()
    prereg = json.loads((EV / "preregistration.json").read_text())
    pre = lambda i, late=None: {"written_at": prereg["written_at"], **{k: v for k, v in prereg["preregistrations"][str(i)].items()
                                                                        if k in ("expectation", "criteria")},
                                **({"late_note": late} if late else {}),
                                **({"fix_round": {"written_at": prereg["fix_round"]["written_at"], "label": prereg["fix_round"]["label"],
                                                  **prereg["fix_round"]["items"][str(i)]}}
                                   if str(i) in prereg.get("fix_round", {}).get("items", {}) else {}),
                                **({"fix_round_2": {"written_at": prereg["fix_round_2"]["written_at"], "label": prereg["fix_round_2"]["label"],
                                                    **prereg["fix_round_2"]["items"][str(i)]}}
                                   if str(i) in prereg.get("fix_round_2", {}).get("items", {}) else {}),
                                **({"errata": prereg["fix_round_2"]["errata"]} if i == 2 and "fix_round_2" in prereg else {})}
    tool, resume = raw("tool-turn.json"), raw("resume-turn.json")
    cancel, cancel_s = raw("cancel.json"), raw("cancel-streaming.json")
    claude = raw("claude-interrupt.json")
    cfg = raw("config-diff.json")
    tt1, tt2, truns = raw("worker-tool-t1.json"), raw("worker-tool-t2.json"), raw("worker-tool-runs.json")
    cmw = raw("ctxmode-c4-window.json")
    temporal = raw("temporal-restart.json")
    lg_s, lg_r = raw("langgraph-start.json"), raw("langgraph-resume.json")
    oh_f, oh_r = raw("openhands-first.json"), raw("openhands-reload.json")

    codex_cancel_cmd = (f"{ENV} timeout 400 {PY_CODEX} {PROBE} cancel {NATIVE} --workspace {B}/ws-probe "
                        f"--out {B}/runs/cancel-streaming.json --deadline 120 --interrupt-after 90 --settle 30 --effort low")
    codex_cancel_cmd0 = (f"{ENV} timeout 400 {PY_CODEX} {PROBE} cancel {NATIVE} --workspace {B}/ws-probe "
                         f"--out {B}/runs/cancel.json --deadline 120 --interrupt-after 30 --settle 30")
    claude_cmd = (f"{ENV} timeout 240 {B}/claude-sdk/bin/python blueprints/gap-wave2-20260923/foundation__agent-sdks/"
                  f"claude_probe.py --workspace {B}/ws-claude --out {B}/runs/claude-interrupt.json")
    tool_cmd = (f"{ENV} timeout 300 {PY_CODEX} {PROBE} tool-turn {NATIVE} --workspace {B}/ws-probe "
                f"--out {B}/runs/tool-turn.json --state {B}/runs/tool-state.json --deadline 180")
    resume_cmd = (f"{ENV} timeout 300 {PY_CODEX} {PROBE} resume-turn {NATIVE} --workspace {B}/ws-probe "
                  f"--out {B}/runs/resume-turn.json --state {B}/runs/tool-state.json --deadline 180")
    w1_cmd = (f"{ENV} timeout --signal=TERM --kill-after=10s 300s {PY_CODEX} {WORKER} run {NATIVE} --workspace {B}/ws-probe "
              f"--prompt {B}/runs/worker-t1.prompt --receipt {B}/runs/worker-persist-t1.json --turn-deadline-seconds 180 --persistent {ISO_PLUGIN}")
    w2_cmd = (f"{ENV} timeout --signal=TERM --kill-after=10s 300s {PY_CODEX} {WORKER} run {NATIVE} --workspace {B}/ws-probe "
              f"--prompt {B}/runs/worker-t2.prompt --receipt {B}/runs/worker-resume-t2.json --turn-deadline-seconds 180 "
              f"--resume-thread-id \"$TID\" {ISO_PLUGIN}")
    wtool_cmd = f"python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/run_worker_tool.py {B} {B}/runs"
    wtool_t1 = (f"(inside run_worker_tool.py) {ENV} timeout --signal=TERM --kill-after=10s 300s {PY_CODEX} {WORKER} run {NATIVE} "
                f"--workspace {B}/ws-probe --prompt {B}/runs/worker-tool-t1.prompt --receipt {B}/runs/worker-tool-t1.json "
                f"--turn-deadline-seconds 180 --persistent --lookup-tool {B}/runs/worker-tool-values.json {ISO_PLUGIN}")
    wtool_t2 = wtool_t1.replace("worker-tool-t1", "worker-tool-t2").replace(
        "--persistent --lookup-tool " + B + "/runs/worker-tool-values.json",
        "--resume-thread-id <thread_id from the private worker-tool-t1 receipt> --lookup-tool " + B + "/runs/worker-tool-decoy.json")
    c4 = lambda out, prompt, extra="": (f"{ENV} timeout --signal=TERM --kill-after=10s 360s {PY_CODEX} {WORKER} run {NATIVE} "
                                        f"--workspace {B}/c4-ws --prompt {B}/runs/{prompt} --receipt {B}/runs/{out} "
                                        f"--turn-deadline-seconds 300 {extra} {C4}").replace("  ", " ")
    install_codex = (f"$HOME/codex-ecosystem/bin/ecosystem-bounded-run bash -c \"uv venv --python $HOME/.local/share/codex-ecosystem/bin/python3.13 "
                     f"--no-python-downloads {B}/codex-sdk-01551 && UV_CACHE_DIR={B}/uv-cache uv pip install --python "
                     f"{B}/codex-sdk-01551/bin/python --default-index https://pypi.org/simple 'openai-codex==0.155.1'\"")

    cancel_rows = lambda d: {"streaming_observed_before_interrupt": d.get("streaming_observed_before_interrupt"),
                             "method_counts": d.get("method_counts"), "turn_status": (d.get("turn_completed") or {}).get("turn_status"),
                             "sdk_last_token_usage": d.get("last_token_usage"),
                             "rollout_entries_after_two_settle_windows": (d.get("rollout_after_second_settle") or {}).get("entries"),
                             "rollout_unchanged_between_settles": (d.get("rollout_after_settle") or {}).get("entries") == (d.get("rollout_after_second_settle") or {}).get("entries"),
                             "rate_limit_primary_used_percent_before_after": [d["limits_before"]["windows"]["primary"]["usedPercent"],
                                                                             d["limits_after"]["windows"]["primary"]["usedPercent"]]}
    claude_rows = {"init_model": (claude.get("init") or {}).get("model"), "cli_version": (claude.get("init") or {}).get("claude_code_version"),
                   "init_mcp_servers": (claude.get("init") or {}).get("mcp_servers"),
                   "streaming_observed_before_interrupt": claude.get("streaming_observed_before_interrupt"),
                   "event_type_counts": claude.get("event_type_counts"),
                   "result": {k: (claude.get("result") or {}).get(k) for k in ("subtype", "terminal_reason", "usage", "model_usage", "total_cost_usd")},
                   "session_jsonl_final_usage_per_message": (claude.get("session_log_after_second_settle") or {}).get("final_usage_per_message"),
                   "model_usage_reading": ("Unexplained, labelled as such. model_usage (921 input / 17 output, costUSD 0.001006) matches no message in the "
                                           "stream or the session JSONL (3346 input / 4 output for the one streamed message). Most likely reading, not "
                                           "confirmed: the CLI made a separate auxiliary Haiku request that completed (the bundled 2.1.280 CLI contains a "
                                           "generateSessionTitle path; num_turns is 2), while the interrupted main message never reached model_usage. If so, "
                                           "the one SDK query produced two provider requests, and model_usage cannot be read as the interrupted turn's usage."),
                   "session_log_unchanged_between_settles": (claude.get("session_log_after_settle") or {}).get("entries") == (claude.get("session_log_after_second_settle") or {}).get("entries")}

    R = []

    def add(i, slug, commands, results, outcome, evidence_class, limits, raw_files, late=None, note=None, remaining=None,
            extra=None):
        R.append({"_slug": slug, "id": f"gap-wave2-20260923/foundation/agent-sdks/{i}-{slug}", "gap_index": i,
                  "gap_text_sha256": hashlib.sha256(texts[i].encode()).hexdigest(),
                  "preregistration": pre(i, late), "commands": commands, "results": results,
                  "raw_outputs": cite(*raw_files), "outcome": outcome, "evidence_class": evidence_class,
                  **({"remaining": remaining} if remaining else {}), **({"note": note} if note else {}), **(extra or {}),
                  "limits": limits, "checked_at": CHECKED_AT})

    add(0, "judge-pin-recovery-closure",
        ["authored blueprints/gap-wave2-20260923/foundation__agent-sdks/workers-judge-pin/{pin.json,judge-prompt.md,adjudicator-prompt.md}",
         "sha256sum $HOME/code/agent-lab/.claude/agents/blind-judge.md",
         "rg -n 'artifact_acceptance_rate|recovery_case_pass_rate' $HOME/code/agent-lab/tools/compare/workers/lib/{constants,protocol}.mjs"],
        {"judge_pin": json.loads((ROOT / "blueprints/gap-wave2-20260923/foundation__agent-sdks/workers-judge-pin/pin.json").read_text())["judges"],
         "recovery_requirement_quoted": "Re-run with RECOVERY_INDICES = [4,5,6] and a budget of 3 arms x 6 = 18 submissions. (agent-lab tools/compare/workers/lib/constants.mjs)",
         "arm_B_resume_prerequisite": "native_worker.py now supports --persistent/--resume-thread-id; a resumed turn recalled the turn-1 token in a new process (gap 3 receipt), so arm B recovery is no longer 'not_supported' by construction.",
         "recovery_run": "not executed", "closure_rerun": "not executed", "summary_json_changed": False},
        "advanced", "source_review",
        ["The judge pin is a proposed protocol amendment; it binds only once sealed into a new protocol instance before judging.",
         "Recovery needs 18 submissions including 12 on two Claude arms (about 200 s each); the shared Claude account is reserved for another session's long-horizon run, so it was not run (blocker, not a capability limit).",
         "The sealed protocol 0034d6c7 and its run directories are private to the originating host phase; they were not opened here."],
        [], remaining="Seal the pin into a new workers protocol instance, run the recovery indices [4,5,6] for all three arms, rerun closure.mjs and record retain/overturn/unresolved in comparison-progress-20260922/summary.json (blocked on the reserved Claude account).")

    add(1, "cancel-usage-vs-native-logs",
        [codex_cancel_cmd0, codex_cancel_cmd, claude_cmd,
         f"python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/export_raw.py {B}/runs evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/raw"],
        {"codex_interrupt_before_output": cancel_rows(cancel), "codex_interrupt_mid_stream": cancel_rows(cancel_s),
         "claude_agent_sdk_interrupt_mid_stream": claude_rows,
         "finding": ("Both Codex interrupts return a typed turn/completed with status interrupted, but no thread/tokenUsage/updated arrives and the "
                     "native rollout's only token_count has info null; the 68 streamed deltas are not accounted anywhere local. The Claude "
                     "ResultMessage (terminal_reason aborted_streaming) reports usage all zeros; its model_usage reports a different small figure; the session "
                     "JSONL keeps the message_start snapshot (output_tokens 4) although 68 deltas streamed. Integer usedPercent did not move (12 -> 12).")},
        "advanced", "native_proven",
        ["Actual provider consumption on interruption is not observable through any of the three channels, so the gap's consumption clause stays open (outcome re-evaluated from settled to advanced in the fix round after cross-family review).",
         "codex usedPercent is an integer percentage of a weekly window; it cannot resolve one small turn (detection floor ~1% of the window).",
         "The Claude arm is one bounded call (haiku alias -> claude-haiku-4-5-20251001), the single call this unit was allowed.",
         "The Claude arm counts as one SDK query; it may have produced two provider requests (see model_usage_reading), which is disclosed against the one-bounded-call allowance.",
         "Rule deviation kept open: see rule_deviations."],
        ["cancel.json", "cancel-streaming.json", "claude-interrupt.json", "cancel.rollout-excerpt.jsonl",
         "cancel-streaming.rollout-excerpt.jsonl", "claude-interrupt.session-usage-excerpt.jsonl"],
        remaining="A provider-side consumption figure for an interrupted turn in each SDK (usage or billing data finer than integer usedPercent) and an explanation of the Claude model_usage figure; the SDK and native-log comparison itself is done.",
        extra={"rule_deviations": [TOOL_TURN_DEVIATION]})

    add(2, "worker-isolation",
        [f"{ENV} timeout 120 {PY_CODEX} {PROBE} config-diff {NATIVE} --workspace {B}/ws-probe --out {B}/runs/config-diff.json",
         tool_cmd, wtool_cmd],
        {"python_env_keys": cfg.get("python_env_keys"),
         "parent": {k: cfg["parent"][k] for k in ("features", "plugins", "mcp_status_names")} | {"hooks": len(cfg["parent"]["hooks_list"]["data"][0]["hooks"])},
         "isolated_worker": {k: cfg["isolated_worker"][k] for k in ("overrides", "features", "plugins", "mcp_status_names")} | {"hooks": len(cfg["isolated_worker"]["hooks_list"]["data"][0]["hooks"])},
         "diff_keys": sorted(cfg["diff"]),
         "tool_turn_host_mcp_tool_items": tool.get("host_mcp_tool_items"), "tool_turn_item_types": tool.get("item_types"),
         "worker_turn_item_types": sorted({i.get("type") for i in tt1.get("items", [])}),
         "detection": "The same item collection records mcpToolCall items with server names: the c4 reruns (gap 4 receipt) captured context-mode ctx_execute_file items, and the parent config lists 2 MCP servers and 13 hooks.",
         "shell_level_bypass_observed": {"source": "raw/c4-t1.json commandExecution items (workspace-write sandbox, auto_review)",
                                         "commands": [c for c in turn_summary("c4-t1.json")["command_items"]["commands"]
                                                      if any(k in c["command"] for k in ("mcporter", "start.mjs", ".codex/RTK.md", "codex-ecosystem/docs"))],
                                         "reading": "Config-level disabling of MCP servers and hooks does not stop a worker with shell access from launching host MCP tooling itself (mcporter on PATH, a readable plugin cache) or reading host instruction files; the sandbox restricts writes, not these reads."}},
        "advanced", "native_proven",
        ["Isolation used per-process -c overrides on the native CODEX_HOME, not an isolated CODEX_HOME: ~/.codex AGENTS.md, skills and auth still load. A fresh CODEX_HOME needs its own native sign-in (user action); copying auth is prohibited.",
         "Dotted -c keys do not unquote plugin ids; the plugins table is replaced as one TOML value.",
         "The config-diff arm ran at 03:24:08Z, 44 s before the preregistration was written (the preregistration's own 'about 03:23Z' note is corrected by its dated errata); raw/limits.json (03:23:46Z, no inference) is also late. The worker-turn arms are preregistered.",
         "Isolation is config-level only: a worker with a shell can still start host MCP servers and read host files (shell_level_bypass_observed)."],
        ["config-diff.json", "tool-turn.json", "worker-tool-t1.json", "c4-t1.json", "limits.json"],
        late="config-diff (03:24:08Z) and limits (03:23:46Z) arms executed before the 03:24:52Z preregistration (see limits and the preregistration errata)",
        remaining="Repeat with a fresh CODEX_HOME holding its own native sign-in and no AGENTS.md/skills, then diff against the parent; and close shell-level access to host MCP tooling (mcporter on PATH, a readable ~/.codex plugin cache, host instruction files), for example with a worker sandbox or user whose filesystem view excludes them, then show a worker cannot start a host MCP server.",
        extra={"rule_deviations": [TOOL_TURN_DEVIATION]})

    worker_tool = {"worker_sha256_at_run": truns.get("worker_sha256"),
                   "slot_checks": truns.get("slot_checks"),
                   "t1": {**turn_summary("worker-tool-t1.json"), "dynamic_tool": tt1.get("dynamic_tool"),
                          "native_runtime": tt1.get("native_runtime")},
                   "t2": {**turn_summary("worker-tool-t2.json"), "dynamic_tool": tt2.get("dynamic_tool"),
                          "native_runtime": tt2.get("native_runtime")},
                   "t2_prompt_contains_value": truns.get("t2_prompt_contains_value"),
                   "t2_final_matches_t1_value": truns.get("t2_final_matches_t1_value"),
                   "detection": "turn 2 ran with a decoy tool file: any tool call would be logged in dynamic_tool.calls and return 'decoy-not-the-value'; the turn-1 value (12 hex) is not in the turn-2 prompt",
                   "side_effects_listing": side_effects_listing(truns)}
    add(3, "persistent-resume-custom-tool",
        [wtool_cmd, wtool_t1, wtool_t2, tool_cmd, resume_cmd,
         "(superseded, uncommitted worker revision) " + w1_cmd, "(superseded) TID=<thread_id from the private worker-persist-t1 receipt>",
         "(superseded, uncommitted worker revision) " + w2_cmd],
        {"sdk_custom_tool": {"registration": "thread/start dynamicTools=[vault_lookup] via openai_codex CodexClient.request; answered by CodexClient(approval_handler=...) on item/tool/call",
                             "tool_host_calls": tool.get("tool_host_calls"), "tool_items": tool.get("tool_items"),
                             "tool_round_trip": tool.get("tool_round_trip")},
         "sdk_resume_new_process": {"resumed_thread_matches": resume.get("resumed_thread_matches"), "turns_in_thread": resume.get("turns_in_thread"),
                                    "final_answer_matches_turn1_tool_value": resume.get("final_answer_matches_turn1_tool_value"),
                                    "tool_items_in_turn2": resume.get("tool_items"),
                                    "detection": "turn 2's tool host would have answered 'not-the-value' had the model called the tool; the 12-hex value never appears in the turn-2 prompt"},
         "c4_worker_custom_tool_persistent_then_resume": worker_tool,
         "superseded_worker_receipts": {"files": ["worker-persist-t1.json", "worker-resume-t2.json"],
                                        "reading": "Produced at 03:31Z by an uncommitted intermediate revision of native_worker.py (native_runtime is a plain string there; no committed revision writes a string: the base and the first branch commit have no --persistent option or native_runtime field, and every later committed revision writes a dict). Kept for history; the fix-round-2 worker-tool receipts, run with the committed file (sha256 in worker_sha256_at_run), are the evidence for the worker arm."}},
        "settled", "native_proven",
        ["dynamicTools is an experimental app-server field absent from the SDK's typed ThreadStartParams and the high-level AsyncCodex.thread_start; native_worker.py --lookup-tool therefore uses the SDK's CodexClient (thread_start/thread_resume with JSON params, approval_handler for item/tool/call). The tool path is deny_all only.",
         "One custom tool, one call; parallel tool calls and tool errors were not exercised.",
         "Each persistent run leaves a rollout in $HOME/.codex/sessions (fix round 2: 1 added file for this thread, worker-tool-runs.json side_effects). The same listing shows 2 added and 59 changed files under $HOME/.codex/context-mode in the window (7 of them stats-pid-*.json); it cannot attribute them to a process, so 'no Context Mode file from these runs' rests on the disabled plugin, not on the listing (results.c4_worker_custom_tool_persistent_then_resume.side_effects_listing). Recent rollouts feed the Context Mode most-recent-transcript fallback that other concurrent Codex sessions use (gap 4 root cause), so a persistent worker can influence another session's project root; these runs had the plugin disabled."],
        ["worker-tool-t1.json", "worker-tool-t2.json", "worker-tool-runs.json", "worker-tool-t1.prompt", "worker-tool-t2.prompt",
         "tool-turn.json", "resume-turn.json", "tool-turn.rollout-excerpt.jsonl", "worker-persist-t1.json", "worker-resume-t2.json"],
        extra={"rechecked_at": RECHECKED_AT, "rule_deviations": [TOOL_TURN_DEVIATION]})

    c4_rows = {n: {**turn_summary(n), "extraction_success": extraction_ok(n)} for n in
               ("c4-t1.json", "c4-t2.json", "c4-t3.json", "c4-t1-root.json")}
    add(4, "c4-three-turns-rerun",
        [f"{ENV} timeout 360s {PY_CODEX} {WORKER} inspect {NATIVE} --workspace {B}/c4-ws --receipt {B}/runs/c4-inspect.json {C4}",
         c4("c4-t1.json", "c4-t1.prompt"), c4("c4-t2.json", "c4-t2.prompt"), c4("c4-t3.json", "c4-t3.prompt", CM_START),
         c4("c4-t1-root.json", "c4-t1.prompt", CM_START),
         f"python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/ctxmode_window.py {B}/runs  # fix round 2, read-only mtime scan"],
        {"per_turn": c4_rows,
         "turn_map": {"turn 1 research": ["c4-t1.json (cwd only)", "c4-t1-root.json (Context Mode root scoped to the workspace)"],
                      "turn 2 file-scope": ["c4-t2.json (cwd only)"], "turn 3 scoped override": ["c4-t3.json (root scoped; same prompt as turn 2)"]},
         "root_cause_of_cwd_only_failures": ("With cwd only, the plugin's Context Mode server resolved its project root to another concurrently active "
                                             "worktree ($HOME/code/nas-wt-codex-review96): its bundled resolver falls back to the most recent Codex transcript "
                                             "(transcriptMaxAgeMs 300000) because the plugin launches from its install dir (source: server.bundle.mjs function Et, start.mjs safeOriginalCwd)."),
         "context_mode_side_effects": {
             "method": "(a) name listings of $HOME/.codex/context-mode taken at 03:31:35Z (before c4-t1) and 03:35:03Z (after c4-t3); (b) a post-hoc read-only mtime scan for 03:31:30-03:38:00Z (covers c4-t1-root) run in fix round 2 by ctxmode_window.py",
             "name_listing_diff": cmw.get("name_listing_03_31_35Z_to_03_35_03Z"),
             "mtime_window_files": [{k: r.get(k) for k in ("path", "mtime", "candidate_runs_by_interval")}
                                    | ({"stats_total_calls": r["stats"].get("total_calls"), "stats_bytes_indexed": r["stats"].get("bytes_indexed")} if r.get("stats") else {})
                                    for r in cmw.get("mtime_window_files", [])],
             "receipt_mcp_tool_calls": cmw.get("receipt_mcp_tool_calls"),
             "reading": ("Four stats-pid files follow this unit's four c4 turns (the earlier receipt named three; stats-pid-2832580 belongs to c4-t1-root, which ran after the second listing). "
                         "For the root-scoped turns (c4-t3, c4-t1-root) stats total_calls equals the receipt's MCP call count (2, 3); for the cwd-only turns (c4-t1, c4-t2) it is larger "
                         "(6 vs 2, 15 vs 1), consistent with those servers accounting against another session's state. stats-pid-2779837 and content/c8dec9624e21bd03.db (both 03:35:44Z, "
                         "554254 bytes indexed) fall in c4-t1-root's interval but its call count (14) and indexing match no worker receipt; they are not attributed to this unit. "
                         "No session or content database was added by name in 03:31:35-03:35:03Z.")}},
        "settled", "native_proven",
        ["Prompts are reconstructions (the 2026-09-19 prompts are private; only their sha256 is published). Workspace files are copies of blueprints/us-equities/engine/receipt.json and deerflow/native-receipt.json.",
         "Host hooks, apps and OTLP export were disabled (to keep ai-memory hooks off the live store); the original c4 run had them on.",
         "auto_review approvals are not visible in the worker receipt, so whether the reviewer approved a request or none was raised is unobserved.",
         "Context Mode wrote four stats-pid-*.json files under $HOME/.codex/context-mode/sessions (left in place; see context_mode_side_effects). The enumeration cannot see content changes to existing files between the listings, nor files written in the window and rewritten later (their mtime moves out of the window); a pre-existing database written by a cwd-only turn and later by its owning session would be missed.",
         "The c4 turns ran shell commands as well as MCP calls (command_items per turn); c4-t1 read host files and started the host Context Mode server through mcporter/node itself (see gap 2)."],
        ["c4-inspect.json", "c4-t1.json", "c4-t2.json", "c4-t3.json", "c4-t1-root.json", "c4-t1.prompt", "c4-t2.prompt", "c4-t3.prompt",
         "ctxmode-c4-window.json"])

    add(6, "sdk-0155-requalification",
        [install_codex, install_codex.replace("codex-sdk-01551", "codex-sdk-01551-b") + "  # fix round, log retained",
         f"uv pip freeze --python {B}/codex-sdk-01551{{,-b}}/bin/python; codex --version",
         f"{ENV} timeout 120 {B}/codex-sdk-01551-b/bin/python {WORKER} inspect {NATIVE} --workspace {B}/c4-ws --receipt {B}/runs/c4-inspect-fresh.json "
         "--config-override features.hooks=false --config-override features.plugin_hooks=false --config-override features.apps=false",
         c4("c4-t1-root.json", "c4-t1.prompt", CM_START), wtool_cmd],
        {"fresh_prefix_install_log_excerpt": [ln for ln in raw("sdk-0155-fresh-prefix.log").splitlines()
                                              if "openai-codex" in ln or ln.startswith("codex-cli") or "install exit" in ln],
         "fresh_prefix_inspect": {k: raw("c4-inspect-fresh.json").get(k) for k in ("status", "sdk_version", "model_inference_submitted")},
         "runs_with_matching_versions": {n: {"sdk_version": raw(n).get("sdk_version"), "native_runtime": raw(n).get("native_runtime"),
                                             "status": raw(n).get("status")} for n in ("c4-t1-root.json", "c4-t3.json", "worker-tool-t2.json")},
         "native_binary": "--codex-bin $HOME/.local/share/codex-ecosystem/bin/codex -> tools/codex-package-0.155.1/bin/codex (ELF), codex-cli 0.155.1",
         "receipt_json_update": "blueprints/us-equities/workers/receipt.json gains version_requalification_20260923 (historical 0.154.0 fields unchanged)"},
        "settled", "native_proven",
        ["The adoption lock and requirements.txt still pin openai-codex 0.154.0; changing pins is the stale-pin upgrade covered by evidence/artifacts/sota-refresh-20260923/ (#87).",
         "Fresh prefix = new venv on the same WSL host, not a second machine. The first prefix's install output (which downloaded openai-codex-cli-bin, 123.9 MiB as printed by uv) was not retained; the fix-round second prefix reused the uv cache, and both freezes are identical."],
        ["c4-t1-root.json", "c4-t3.json", "worker-tool-t2.json", "c4-inspect.json", "sdk-0155-fresh-prefix.log", "c4-inspect-fresh.json"],
        note="Fix round 2: worker-tool-t2.json (committed native_worker.py) replaces worker-resume-t2.json, which came from an uncommitted intermediate revision.",
        extra={"rechecked_at": RECHECKED_AT})

    add(8, "langgraph-temporal-openhands",
        [f"python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/run_gap8.py {B} {B}/runs {B}/tmp-VB16/cli",
         "(first pass, same scripts run individually: langgraph_checkpoint.py start/resume; temporal_restart.py controller under ecosystem-bounded-run, which downloaded the Temporal CLI; openhands_local.py first/reload)"],
        {"exit_codes": {r["label"]: r["exit_code"] for r in raw("gap8-runs.json")["runs"]},
         "versions": raw("gap8-runs.json")["versions"], "temporal_cli_version": raw("gap8-runs.json").get("temporal_cli_version"),
         "langgraph": {"start": lg_s, "resume": lg_r},
         "temporal": {k: temporal.get(k) for k in ("result", "attempts", "effects", "worker1_returncode", "history_events",
                                                    "replay_failure", "negative_control_replay_failure", "server_stopped")},
         "openhands": {"first": {k: oh_f.get(k) for k in ("event_types", "execution_status", "proof_file", "llm_calls")},
                       "reload": {k: oh_r.get(k) for k in ("events_before", "events_after", "execution_status", "proof_file", "llm_calls")}}},
        "advanced", "local_integration",
        ["OpenHands ran with the SDK's own scripted TestLLM (no provider); the agent loop, terminal tool, event log and persistence reload are real, the model is not. Remote/container workspaces were not exercised.",
         "Temporal: dev server on loopback from temporalio.testing (CLI 150 MB download into the temp dir, disclosed); worker #1 SIGKILLed after the effect write; a nondeterministic negative control was flagged by Replayer (the detector works).",
         "LangGraph: no model; interrupt_before checkpoint in SQLite resumed by a second process.",
         "Retained outputs come from the fix-round driver run (run_gap8.py); the first pass (03:37-03:47Z) ran the same scripts individually, all exit 0 with the same results shape. OpenHands stderr logs are not exported (console wrapping split UUIDs past redaction)."],
        ["gap8-runs.json", "langgraph-start.json", "langgraph-resume.json", "temporal-restart.json", "openhands-first.json",
         "openhands-reload.json", "openhands-install.log"],
        remaining="An OpenHands conversation with a real model (needs a model endpoint: a provider key or subscription sign-in, not available under this unit's no-paid-API/no-credential rules) and a container/remote workspace run.")

    checklist = {"structured_events_typed": {"codex": tool.get("untyped_methods") == [], "claude": "partial (one interrupted query only)"},
                 "custom_tool_round_trip": {"codex": tool.get("tool_round_trip"), "claude": "not run"},
                 "mid_turn_interrupt": {"codex": (cancel_s.get("turn_completed") or {}).get("turn_status"), "claude": (claude.get("result") or {}).get("terminal_reason")},
                 "resume_recall": {"codex": resume.get("final_answer_matches_turn1_tool_value"), "claude": "not run"}}
    add(9, "matched-sdk-comparison",
        [tool_cmd, resume_cmd, codex_cancel_cmd, claude_cmd],
        {"checklist": checklist, "codex_event_types": tool.get("received_types_documented"),
         "claude_event_types": claude.get("event_type_counts")},
        "advanced", "native_proven",
        ["Only the Codex arm ran the full checklist. The Claude arm needs a custom-tool query, an interrupt and a resumed query (three or more calls); the unit may make one bounded Claude call, spent on the interrupt."],
        ["tool-turn.json", "resume-turn.json", "cancel-streaming.json", "claude-interrupt.json"],
        extra={"rule_deviations": [TOOL_TURN_DEVIATION]},
        remaining="Run the Claude Agent SDK arm (SDK MCP custom tool, interrupt, resume in a new process) on the same task when the Claude account is free, then score both on the checklist.")

    add(10, "codex-custom-tool-event-handling",
        [tool_cmd, "codex app-server generate-json-schema --experimental --out " + B + "/schema-exp"],
        {"tool_registration": "dynamicTools (not an MCP server)", "tool_round_trip": tool.get("tool_round_trip"),
         "received_notification_types": tool.get("method_counts"), "untyped_received": tool.get("untyped_methods"),
         "documented_notification_types_in_sdk_registry": tool.get("documented_notification_types"),
         "documented_types_not_received": tool.get("documented_types_not_received"),
         "other_server_requests": tool.get("other_server_requests"),
         "detection": "untyped = coerced to UnknownNotification by the SDK (client._coerce_notification); a validation failure would appear in untyped_received"},
        "advanced", "native_proven",
        ["One turn received 6 of the documented notification types; the rest (realtime, goals, fs, compaction, approvals, errors, ...) were not emitted, so 'every documented type handled' is not shown."],
        ["tool-turn.json"],
        extra={"rule_deviations": [TOOL_TURN_DEVIATION]},
        remaining="A turn corpus or recorded app-server stream that emits each documented notification type (or an SDK-level validation test over the upstream schema samples).")

    add(11, "cancel-billing-exactly-once",
        [codex_cancel_cmd, claude_cmd,
         f"python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/run_gap8.py {B} {B}/runs {B}/tmp-VB16/cli  # produced the retained raw/temporal-restart.json (04:22:05-04:22:37Z); it runs temporal_restart.py controller under ecosystem-bounded-run",
         f"(first pass, output replaced) timeout 600 $HOME/codex-ecosystem/bin/ecosystem-bounded-run {B}/temporal/bin/python blueprints/gap-wave2-20260923/foundation__agent-sdks/temporal_restart.py controller {B}/tmp-VB16 {B}/runs/temporal-restart.json"],
        {"codex_cancel": cancel_rows(cancel_s), "claude_cancel": claude_rows,
         "exactly_once_one_host": {"attempts": temporal.get("attempts"), "effects": temporal.get("effects"),
                                   "result": temporal.get("result"),
                                   "reading": "activity executed twice (at-least-once); the idempotency key kept the effect to one row (effectively-once)"}},
        "advanced", "local_integration",
        ["Local accounting stops after the abort (rollout and session log unchanged over two settle windows), but provider billing cessation is not observable: no billing API was used (no paid API) and usedPercent is integer-granular.",
         "Exactly-once is idempotency-keyed effectively-once on one host with one sqlite effect store; distributed recovery (multiple hosts, partitions) was not exercised."],
        ["cancel-streaming.json", "claude-interrupt.json", "temporal-restart.json", "gap8-runs.json", "cancel-streaming.rollout-excerpt.jsonl",
         "claude-interrupt.session-usage-excerpt.jsonl"],
        note="Fix round 2: the retained temporal-restart.json came from the fix-round run_gap8.py driver (attempt 1 at 04:22:08Z, inside gap8-runs.json's 04:22:05-04:22:37Z window), not the first-pass command; the commands list now says so (as receipt 8 does).",
        remaining="Provider-side billing evidence for an interrupted turn, and a multi-host recovery test.")

    add(12, "file-tool-scope-approval",
        [c4("c4-t2.json", "c4-t2.prompt"), c4("c4-t3.json", "c4-t3.prompt", CM_START)],
        {"without_override": turn_summary("c4-t2.json") | {"extraction_success": extraction_ok("c4-t2.json")},
         "with_scoped_override_and_non_interactive_approval": turn_summary("c4-t3.json") | {"extraction_success": extraction_ok("c4-t3.json")},
         "answer": "No: without the override the turn does not complete its extraction (project root bound to another active worktree). With the scoped override, workspace-write and auto_review it completes non-interactively; the 2026-09-19 approval block did not recur."},
        "advanced", "native_proven",
        ["The preregistered criterion (completes without the override) failed; outcome re-evaluated from settled to advanced in the fix round.",
         "Whether auto_review actually reviewed an approval request is not visible in the worker receipt.",
         "The default root depends on which Codex transcript was most recent; on a host with no concurrent Codex sessions it may coincide with the workspace.",
         "Side effects: the c4 turns launched the host plugin against the live $HOME/.codex/context-mode state (enumeration and its blind spots in the gap 4 receipt). Conversely, this unit's persistent rollouts in $HOME/.codex/sessions can become the most recent transcript that another concurrent session's Context Mode fallback binds to (cross-session risk, not measured)."],
        ["c4-t2.json", "c4-t3.json", "c4-t2.prompt", "c4-t3.prompt", "ctxmode-c4-window.json"],
        remaining="A no-override path in which the plugin's Context Mode root follows the worker workspace (for example an upstream per-thread project-dir setting, or a persistent worker thread that is the most recent transcript), then rerun the file turn.")

    add(13, "sdk-resume-new-process",
        [tool_cmd, resume_cmd, wtool_cmd, wtool_t1, wtool_t2],
        {"codex_sdk": {"resume_turn": {k: resume.get(k) for k in ("new_process_pid", "resumed_thread_matches", "turns_in_thread",
                                                                  "final_answer_matches_turn1_tool_value")},
                       "native_worker": {"t2_status": tt2.get("status"), "t2_thread_mode": tt2.get("thread_mode"),
                                         "t2_tool_calls": (tt2.get("dynamic_tool") or {}).get("calls"),
                                         "t2_final_matches_t1_value": truns.get("t2_final_matches_t1_value"),
                                         "committed_worker_sha256": truns.get("worker_sha256")}},
         "claude_agent_sdk": "not run (resume needs two calls; one bounded call was allowed and spent on the interrupt)"},
        "advanced", "native_proven",
        ["Codex arm only."],
        ["resume-turn.json", "worker-tool-t2.json", "worker-tool-runs.json", "worker-tool-t2.prompt"],
        note="Fix round 2: the worker arm now cites worker-tool-t2.json (committed native_worker.py); worker-resume-t2.json came from an uncommitted intermediate revision.",
        extra={"rechecked_at": RECHECKED_AT, "rule_deviations": [TOOL_TURN_DEVIATION]},
        remaining="Claude Agent SDK resume (ClaudeAgentOptions.resume) in a new process when the Claude account is free.")
    return R


def main() -> int:
    receipts = build()
    for r in receipts:
        slug = r.pop("_slug")
        (EV / f"{r['gap_index']}-{slug}.json").write_text(json.dumps(r, indent=2) + "\n")
    # Round 3 (2026-09-23 re-dispatch) adds its checks from raw/round3/ before results are derived.
    import build_round3
    build_round3.apply()
    # Round 4 (loopback provider arms) extends the receipts from raw/round4/.
    import build_round4
    build_round4.apply()
    # results.json derived from receipts on disk (never by hand).
    results = {}
    for p in sorted(EV.glob("*.json")):
        if p.name == "results.json" or p.name.startswith("preregistration"):
            continue
        rec = json.loads(p.read_text())
        results[str(rec["gap_index"])] = {"outcome": rec["outcome"], "receipt": p.name,
                                          **({"scope": rec["settled_scope"]} if rec.get("settled_scope") else {})}
    (EV / "results.json").write_text(json.dumps(dict(sorted(results.items(), key=lambda kv: int(kv[0]))), indent=2) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in results.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
