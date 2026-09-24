#!/usr/bin/env python3
"""Round 3: add the round-3 checks to the receipts written by build_receipts.py.

Called from build_receipts.main() after the round-1/fix-round receipts are written and before
results.json is derived. Every quoted value is read from raw/round3/ at build time. Receipts whose
outcome changes keep their earlier `remaining` and `limits` under `round_1_remaining` and
`round_1_limits`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EV = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks"
RAW3 = EV / "raw/round3"
PREREG = "preregistration-round3.json"
DRIVER = "python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/round3.py"
NS = ("pasta --config-net -T none -U none -t none -u none --no-map-gw --quiet -- unshare --mount --pid --fork "
      "--mount-proc bash blueprints/gap-wave2-20260923/foundation__agent-sdks/iso_ns.sh STAGE PROFILE -- CMD "
      "(issued by round3.py for every in-namespace command)")
EXPECTED = {"engine_data_points": 3943, "engine_simulated_orders": 3, "engine_failed_data_requests": 0,
            "deerflow_upstream_skill_count": 23, "acp_configured_model": "gpt-6-astra", "acp_prompt_calls": 0}
REVIEW2 = "round3_review2_fix"


def raw(name: str):
    return json.loads((RAW3 / name).read_text())


def cite(*names: str) -> list[dict]:
    return [{"path": f"raw/round3/{n}", "sha256": hashlib.sha256((RAW3 / n).read_bytes()).hexdigest()} for n in names]


def items(worker: dict) -> dict:
    its = worker.get("items") or []
    return {"item_types": sorted({i.get("type") for i in its}),
            "mcp_tool_items": [{"server": i.get("server"), "tool": i.get("tool"), "status": i.get("status")}
                               for i in its if i.get("type") == "mcpToolCall"],
            "command_items": [{"command": (i.get("command") or "")[:160], "exitCode": i.get("exitCode"),
                               "status": i.get("status")} for i in its if i.get("type") == "commandExecution"]}


def summary(name: str) -> dict:
    s = dict(raw(name)["summary"])
    s.pop("config_top_level_keys", None)
    return s


def prereg(gap: str, fix: bool = False, review2: int | None = None) -> dict:
    p = json.loads((EV / PREREG).read_text())
    out = {"file": PREREG, "written_at": p["written_at"], **p["preregistrations"][gap]}
    if fix:
        out["fix"] = {"written_at": p["round3_fix"]["written_at"], "label": p["round3_fix"]["label"],
                      **p["round3_fix"]["gap_2"]}
    if review2 is not None:
        r2 = p[REVIEW2]
        out["review2_fix"] = {"written_at": r2["written_at"], "label": r2["label"],
                              "plan": r2["findings_and_plan"][review2 - 1]}
    return out


def plugins_dir_check(worker: dict) -> dict:
    """Review-2 fix 3: evaluate 'no plugins directory created under the stage home'."""
    lst = raw("review2-stage-home-listing.json")
    st = lst["stages"]
    ls_out = [i.get("aggregatedOutput") or "" for i in worker.get("items") or []
              if i.get("type") == "commandExecution" and "ls -A" in (i.get("command") or "")]
    codex_listing = [o.split("$HOME/.codex:\n", 1)[1].split("\n") for o in ls_out if "$HOME/.codex:\n" in o]
    worker_saw_plugins = any("plugins" in lines for lines in codex_listing)
    holds = (not st["bare-np"]["plugins_dir"] and st["bare"]["plugins_dir"]
             and bool(codex_listing) and not worker_saw_plugins)
    return {"listed_at": lst["listed_at"], "label": "post-hoc listing (after the runs), not taken during them",
            "plugins_dir_by_stage": {k: v["plugins_dir"] for k, v in st.items()},
            "bare_np_entries": st["bare-np"]["entries"],
            "worker_ls_codex_home_listings": len(codex_listing),
            "worker_ls_shows_plugins": worker_saw_plugins,
            "detection": "The bare stage (same launcher, plugins not disabled) has a plugins/ directory, so the listing "
                         "detects one when present; the worker's own `ls -A ~/.codex` inside the namespace is a second, "
                         "in-run observation.",
            "criterion_holds": holds}


def parent_exposure() -> dict:
    """Review-2 fix 1: what the no-override parent snapshot could reach on the live home."""
    parent = raw("config-parent.json")
    hooks = [{"event": h.get("eventName"), "source": h.get("source"), "plugin": h.get("pluginId")}
             for e in (parent.get("hooks") or {}).get("data") or [] for h in (e or {}).get("hooks") or []]
    probe = raw("review2-otel-probe.json")
    ps, pc = probe["parent_sequence"], probe["positive_control"]
    return {
        "run": "round3.py config, parent arm: iso_config.py with the native binary against the live $HOME/.codex and no "
               "config overrides (" + parent["started_at"] + " to " + parent["finished_at"] + "); requests: initialize, "
               "config/read, hooks/list, skills/list; no thread/start, no turn",
        "hooks_active": hooks,
        "hooks_reading": "All 6 are Context Mode plugin hooks on thread or turn events (sessionStart, userPromptSubmit, "
                         "preToolUse, postToolUse, preCompact, stop); no ai-memory hook is registered in that home. No "
                         "thread was started, so none of these events should have occurred. Source/config reading only: "
                         "no hook-firing probe was run (its only detector would be a before/after listing of "
                         "$HOME/.codex/context-mode, which concurrent sessions also write).",
        "otlp_endpoints_active": parent["summary"]["otel"],
        "otlp_reproduction": {
            "source": "raw/round3/review2-otel-probe.json (blueprints/.../otel_probe.py)",
            "method": "same request sequence and binary, live home, hooks and plugin hooks off, both OTLP endpoints "
                      "redirected to a loopback listener started and stopped by the probe",
            "parent_sequence_requests": [{k: h[k] for k in ("method", "path", "bytes", "t_rel")} for h in ps["hits"]],
            "positive_control_requests": [{k: h[k] for k in ("method", "path", "bytes", "t_rel")} for h in pc["hits"]],
            "effective_endpoint_redirected": "127.0.0.1:" in str(ps["effective"]["otel"]),
        },
        "reading": "The reproduction posted one OTLP metrics and one OTLP logs request within 0.3 s of start, so the "
                   "original parent snapshot most likely sent comparable data to the local OTLP viewer on "
                   "127.0.0.1:14318 (listening when checked at review time; its state at 12:59Z was not recorded). That "
                   "is a write to a running local service, which the unit's rules exclude; the viewer was not queried "
                   "to confirm it. The staged runs set otel exporters to none (receipt config summaries).",
    }


def gap2() -> tuple[dict, str, str | None, list[str]]:
    ctl = raw("step-worker-bare-np.json")
    first, fixed = raw("bare-worker-iso.json"), raw("bare-np-worker-iso.json")
    block = {
        "preregistration": {**prereg("2", fix=True, review2=3),
                            "review2_fix_parent_exposure": prereg("2", review2=1)["review2_fix"]},
        "commands": [f"{DRIVER} stage", f"{DRIVER} controls", f"{DRIVER} config", f"{DRIVER} worker-bare",
                     f"{DRIVER} mcp-startup  (late: no-inference diagnostic after the events turn)",
                     f"{DRIVER} stage-np", f"{DRIVER} config-np", f"{DRIVER} mcp-startup-np", f"{DRIVER} worker-bare-np", NS,
                     "(review-2 fix) python3 blueprints/gap-wave2-20260923/foundation__agent-sdks/stage_listing.py "
                     "evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/raw/round3/review2-stage-home-listing.json",
                     "(review-2 fix) env -i HOME=$HOME PATH=$HOME/.local/share/codex-ecosystem/bin:/usr/bin:/bin timeout 180 "
                     "$HOME/.cache/gap-wave2-20260923/agent-sdks/codex-sdk-01551/bin/python "
                     "blueprints/gap-wave2-20260923/foundation__agent-sdks/otel_probe.py "
                     "$HOME/.local/share/codex-ecosystem/bin/codex $HOME/.codex "
                     "$HOME/.cache/gap-wave2-20260923/agent-sdks/review2 $HOME/.cache/gap-wave2-20260923/agent-sdks/review2/otel-probe.json "
                     "(output copied to raw/round3/review2-otel-probe.json)"],
        "raw_outputs": cite("step-controls.json", "step-config.json", "config-parent.json", "bare-config-iso.json",
                            "step-worker-bare.json", "bare-worker-iso.json", "bare-worker-iso.prompt",
                            "step-mcp-startup.json", "bare-mcp-startup.json", "step-config-np.json",
                            "bare-np-config-iso.json", "step-mcp-startup-np.json", "bare-np-mcp-startup.json",
                            "step-worker-bare-np.json", "bare-np-worker-iso.json", "bare-np-worker-iso.prompt",
                            "review2-stage-home-listing.json", "review2-otel-probe.json"),
        "results": {
            "a_controls_outside_vs_inside": ctl["controls_differ"],
            "a_detection": "The outside run of the same iso_controls.sh is the positive control: mcporter resolves, "
                           "6 Context Mode start.mjs files are found, the unit's own loopback listener answers.",
            "b_parent_snapshot_native_home": summary("config-parent.json"),
            "b_parent_note": "mcpServerStatus/list was skipped for the parent so that no host MCP server was started; "
                             "round 1 (raw/config-diff.json) recorded the parent's codex_apps and context-mode servers.",
            "b_parent_exposure": parent_exposure(),
            "b_isolated_first_stage": summary("bare-config-iso.json"),
            "b_isolated_first_stage_thread_time_mcp": raw("bare-mcp-startup.json"),
            "b_isolated_no_plugin_stage": summary("bare-np-config-iso.json"),
            "b_isolated_no_plugin_stage_thread_time_mcp": raw("bare-np-mcp-startup.json"),
            "c_worker_first_stage": {"status": first.get("status"), **items(first)},
            "c_worker_no_plugin_stage": {"status": fixed.get("status"), "sandbox": fixed.get("sandbox"),
                                          "approval_mode": fixed.get("approval_mode"),
                                          "config_overrides": fixed.get("config_overrides"), **items(fixed),
                                          "final_response_excerpt": (fixed.get("final_response") or "")[-700:]},
            "c_detection": "The same item collection recorded 5 context-mode mcpToolCall items and the mcporter/node "
                           "shell bypass in round 1 (raw/c4-t1.json).",
            "finding_provider_plugins": "A fresh CODEX_HOME downloaded the account's remote curated plugins (9, about "
                                        "41 MB) on first start; openai-developers 1.3.0 then ran an MCP server named "
                                        "openai-api-key-local-confirmation at thread start (first stage). Setting "
                                        "features.plugins, features.remote_plugin and "
                                        "features.skill_mcp_dependency_install to false removed it (no-plugin stage).",
        },
        "checked_at": raw("step-worker-bare-np.json")["finished_at"],
    }
    r = block["results"]
    plugins = plugins_dir_check(fixed)
    r["b_plugins_directory"] = plugins
    # Strict acceptance (review fix 1): expected values on both sides, not merely a difference.
    expect_in = {"mcporter_on_path": "no", "context_mode_start_mjs": "absent",
                 "context_mode_start_mjs_found_under_home": "0", "codex_home_agents_md": "absent",
                 "claude_dir": "absent", "agent_lab_checkout": "absent", "ecosystem_bin": "absent",
                 "windows_drive": "absent", "user_bus": "absent", "own_loopback_listener": "unreachable"}
    expect_out = {"context_mode_start_mjs": "exists", "codex_home_agents_md": "exists", "claude_dir": "exists",
                  "agent_lab_checkout": "exists", "own_loopback_listener": "reached"}
    inside, outside = ctl["controls_inside"], ctl["controls_outside"]
    controls_ok = (ctl["controls_inside_run"]["exit_code"] == 0
                   and all(inside.get(k) == v for k, v in expect_in.items())
                   and inside.get("node_start_mjs_exit") not in (None, "0")
                   and all(outside.get(k) == v for k, v in expect_out.items())
                   and str(outside.get("mcporter_on_path", "")).startswith("yes:")
                   and int(outside.get("context_mode_start_mjs_found_under_home", "0")) > 0)

    def host_access_failed(cmds: list[dict]) -> bool:
        for c in cmds:
            text = c["command"]
            tries = ("mcporter" in text or "127.0.0.1" in text or ("node " in text and "start.mjs" in text))
            if tries and c["exitCode"] == 0:
                return False
        return True

    worker = r["c_worker_no_plugin_stage"]
    r["acceptance"] = {"controls_expected_values": controls_ok,
                       "worker_host_access_commands_all_failed": host_access_failed(worker["command_items"]),
                       "worker_mcp_tool_items": len(worker["mcp_tool_items"]),
                       "no_plugins_directory_in_no_plugin_stage": plugins["criterion_holds"],
                       "rule": "controls match the expected inside and outside values; every worker command that tries "
                               "mcporter, the loopback listener or node start.mjs exits non-zero; zero mcpToolCall items; "
                               "thread-time MCP status empty; no plugins directory under the no-plugin stage home "
                               "(review-2 fix: evaluated from a post-hoc listing and the worker's own ls)"}
    ok = (controls_ok and r["acceptance"]["worker_host_access_commands_all_failed"]
          and not r["b_isolated_no_plugin_stage"]["mcp_servers_configured"]
          and not r["b_isolated_no_plugin_stage_thread_time_mcp"]["startup_status"]
          and not r["b_isolated_no_plugin_stage_thread_time_mcp"]["mcp_status_after_thread_start"]
          and r["b_isolated_no_plugin_stage"]["hook_count"] == 0
          and not r["b_isolated_no_plugin_stage"]["codex_home_instruction_files"]
          and worker["status"] == "completed"
          and not worker["mcp_tool_items"]
          and plugins["criterion_holds"])
    limits = [
        "The staging CODEX_HOME shares the native sign-in: auth.json is bind-mounted read-only inside the namespace "
        "(never copied; the staging file is an empty placeholder). A token refresh would fail rather than write.",
        "Isolation comes from the launcher (pasta + unshare + iso_ns.sh), not from native_worker.py, whose CodexConfig env "
        "still overlays the parent environment; a caller must launch the worker this way to get it.",
        "Provider-side built-in tools stay available to the model (web__run, image_gen__imagegen, clock__curr_time); "
        "outbound internet is open, only host loopback and the host filesystem are cut off. /usr, /etc and /usr/local/bin/node "
        "remain visible.",
        "In the no-plugin stage the model wrote /tmp/isolation-probe-find-errors (namespace tmpfs, discarded on exit) and "
        "reported it as a deviation.",
        "Round-3 downloads: remote curated plugins, about 41 MB into each of the bare, events and ctxmode staging homes "
        "(none in the no-plugin stage); the jsonschema wheel for the gap-10 check.",
    ]
    return block, ("settled" if ok else "advanced"), None if ok else "see round_3 results", limits


def gap10() -> dict:
    ev, sd = raw("events-turn.json"), raw("schema-dispatch.json")["summary"]
    return {
        "preregistration": prereg("10"),
        "commands": [f"{DRIVER} events", f"{DRIVER} schema", NS,
                     "(schema step) codex app-server generate-json-schema --experimental --out $HOME/.cache/gap-wave2-20260923/agent-sdks/round3/schema"],
        "raw_outputs": cite("step-events.json", "events-turn.json", "step-schema.json", "schema-dispatch.json",
                            "native-schema-servernotification.json", "step-schema-attempt1.json",
                            "step-schema-attempt2.json", "step-schema-attempt3.json", "step-schema-attempt4.json",
                            "step-schema-attempt5-prereview.json"),
        "results": {
            "native_turn": {k: ev.get(k) for k in ("turn_status", "received_documented_count", "received_documented",
                                                    "received_undocumented", "untyped_methods", "server_requests",
                                                    "final_answer_has_tool_value", "notes_txt_created")},
            "native_turn_item_types": sorted({i["type"] for i in ev.get("completed_items", [])}),
            "native_turn_note": "Round 1 received 6 documented types; this turn received the counts above. No plan update "
                                "(turn/plan/updated) arrived although the prompt asked for one. The two "
                                "mcpServer/startupStatus/updated notifications came from the provider-delivered "
                                "openai-api-key-local-confirmation server (gap 2 round 3).",
            "synthetic_schema_dispatch": sd,
            "synthetic_note": "Samples are generated from the native 0.155.1 schema (only the first valid branch of each "
                              "oneOf/anyOf, so not every item variant), validated with jsonschema 4.26.0, then passed to the "
                              "SDK's CodexClient._coerce_notification and, one at a time, to a fresh MessageRouter with the "
                              "matching turn, login or global consumer registered; `delivered` counts both variants of all "
                              "82 methods received by that consumer. The negative control (drop one "
                              "required field) turned 79 of 80 untyped; thread/project/updated stayed typed, so the SDK "
                              "model is more lenient than the native schema there. The generator failed or produced invalid "
                              "samples in the first attempts (a crash on boolean subschemas, then 72, 79 and 82 methods "
                              "with valid samples as oneOf merging was fixed). Attempt 5 (pre-review) routed only minimal "
                              "samples without consumers; after the cross-family review the delivery check was added and "
                              "the cited run is the post-review rerun.",
        },
        "remaining": "Native receipt of the other documented notification types (69 not seen in any native turn here), "
                     "for example through a recorded app-server stream covering realtime, approvals, goals, hooks, fs and errors.",
        "checked_at": raw("step-schema.json")["finished_at"],
    }


def gap12() -> tuple[dict, bool]:
    w = raw("ctxmode-c4-t2-iso.json")
    final = w.get("final_response") or ""
    try:  # review-2 fix 4: compare parsed fields, not substrings
        parsed = json.loads(final)
    except ValueError:
        parsed = {}
    field_check = {k: {"expected": v, "got": parsed.get(k), "match": parsed.get(k) == v} for k, v in EXPECTED.items()}
    ok_values = bool(parsed) and all(c["match"] for c in field_check.values())
    it = items(w)
    step = raw("step-worker-ctxmode.json")
    block = {
        "preregistration": prereg("12", review2=4),
        "commands": [f"{DRIVER} stage", f"{DRIVER} config", f"{DRIVER} worker-ctxmode", NS],
        "raw_outputs": cite("step-worker-ctxmode.json", "ctxmode-c4-t2-iso.json", "ctxmode-c4-t2.prompt",
                            "ctxmode-config-iso.json", "step-config.json"),
        "results": {
            "configuration": "isolated CODEX_HOME with the Context Mode plugin copied from the installed plugin cache and "
                             "enabled; hooks off; persistent worker thread; workspace-write; auto_review; no "
                             "--context-mode-start and no mcp_servers override",
            "config_overrides": w.get("config_overrides"), "thread_mode": w.get("thread_mode"),
            "status": w.get("status"), "sandbox": w.get("sandbox"), "approval_mode": w.get("approval_mode"),
            **it, "final_response_excerpt": final[:600], "extraction_success": ok_values,
            "extraction_field_check": field_check,
            "extraction_detection": "The final response is parsed as JSON and each of the six fields is compared by name "
                                    "and value (review-2 fix; the earlier substring test could not catch a wrong 3/0/0).",
            "isolated_context_mode_files": step.get("iso_context_mode_files"),
            "isolated_rollouts": len(step.get("iso_sessions") or []),
            "reading": "The plugin's Context Mode root falls back to the most recent rollout in CODEX_HOME/sessions. In the "
                       "isolated home that rollout is the worker's own persistent thread, so the root is the workspace and "
                       "the file tool resolves ./engine-receipt.json without an override.",
        },
        "checked_at": step["finished_at"],
    }
    ok = (ok_values and w.get("status") == "completed" and not w.get("config_overrides")
          and any(m["server"] == "context-mode" and m["tool"] == "ctx_execute_file" and m["status"] == "completed"
                  for m in it["mcp_tool_items"]))
    return block, ok


def gap13() -> tuple[dict, bool]:
    c = raw("claude-resume.json")
    block = {
        "preregistration": prereg("13", review2=2),
        "commands": [f"{DRIVER} claude-resume",
                     "(inside) env -i HOME=$HOME PATH=$HOME/.local/share/codex-ecosystem/bin:/usr/bin:/bin timeout 240 "
                     "$HOME/.cache/gap-wave2-20260923/agent-sdks/claude-sdk/bin/python "
                     "blueprints/gap-wave2-20260923/foundation__agent-sdks/claude_resume.py --session-file <private round-1 "
                     "output> --workspace $HOME/.cache/gap-wave2-20260923/agent-sdks/ws-claude --out <private>"],
        "raw_outputs": cite("step-claude-resume.json", "claude-resume.json", "claude-resume.session-appended-excerpt.jsonl"),
        "results": {k: c.get(k) for k in ("prompt", "prompt_mentions_subject", "answer", "answer_names_subject", "status",
                                          "session_jsonl_lines_before", "session_jsonl_lines_after")}
                   | {"result": {k: (c.get("result") or {}).get(k) for k in ("subtype", "is_error", "num_turns",
                                                                            "session_id_equals_resumed", "total_cost_usd")},
                      "model": (c.get("init") or {}).get("model"),
                      "detection": "The subject appears only in the round-1 first message; a failed resume starts an "
                                   "empty session, which cannot name it."},
        "checked_at": "2026-09-23T13:01:16Z",
    }
    ok = bool(c.get("answer_names_subject")) and not c.get("prompt_mentions_subject") \
        and (c.get("result") or {}).get("session_id_equals_resumed") is True
    return block, ok


def apply() -> None:
    def load(prefix: str) -> tuple[Path, dict]:
        p = next(EV.glob(f"{prefix}-*.json"))
        return p, json.loads(p.read_text())

    # Gap 2
    p, r = load("2")
    block, outcome, remaining, limits = gap2()
    r["round_3"] = block
    if outcome != r["outcome"]:
        r["round_1_outcome"] = r["outcome"]
    r["round_1_remaining"], r["round_1_limits"] = r.pop("remaining", None), r.pop("limits")
    r["outcome"], r["limits"] = outcome, limits
    if remaining:
        r["remaining"] = remaining
    r["checked_at"] = block["checked_at"]
    p.write_text(json.dumps(r, indent=2) + "\n")
    # Gap 10 (stays advanced)
    p, r = load("10")
    block = gap10()
    r["round_1_remaining"] = r["remaining"]
    r["remaining"] = block.pop("remaining")
    r["round_3"] = block
    r["evidence_class_note"] = "native_proven for the native turns; the round-3 schema dispatch is synthetic"
    r["checked_at"] = block["checked_at"]
    p.write_text(json.dumps(r, indent=2) + "\n")
    # Gap 12
    p, r = load("12")
    block, ok = gap12()
    r["round_3"] = block
    if ok:
        r["round_1_outcome"], r["outcome"] = r["outcome"], "settled"
        r["round_1_remaining"] = r.pop("remaining")
        r["round_1_limits"] = r["limits"]
        r["settled_scope"] = ("isolated CODEX_HOME whose only recent rollout is the worker's persistent thread; the "
                              "shared native home without an override is not settled")
        r["limits"] = [
            "The no-override path is shown in an isolated CODEX_HOME, where the worker's persistent rollout is the only "
            "recent transcript. In the shared native home the fallback binds to whichever session wrote the most recent "
            "rollout (round 1: another worktree), so a shared-home no-override run can still fail; use the scoped "
            "--context-mode-start override there (round 1: completes with auto_review).",
            "Whether auto_review reviewed any request is not visible in the worker receipt; the approval clause is closed "
            "in the sense that no approval block recurred.",
            "The ctxmode staging home also downloaded the provider's remote curated plugins (about 41 MB); the turn "
            "called only context-mode tools.",
        ]
    r["checked_at"] = block["checked_at"]
    p.write_text(json.dumps(r, indent=2) + "\n")
    # Gap 13
    p, r = load("13")
    block, ok = gap13()
    r["round_3"] = block
    if ok:
        r["round_1_outcome"], r["outcome"] = r["outcome"], "settled"
        r["round_1_remaining"] = r.pop("remaining")
        r["round_1_limits"] = r["limits"]
        res = r.get("results") or {}
        if "claude_agent_sdk" in res:  # review-2 fix 2: no stale top-level 'not run'
            res["claude_agent_sdk_round_1"] = res["claude_agent_sdk"]
            res["claude_agent_sdk"] = ("run in round 3: see round_3.results (resumed the round-1 session in a new "
                                       "process; the answer names the subject only the round-1 first message contained)")
        r["limits"] = [
            "Claude arm: one bounded haiku query (claude-haiku-4-5-20251001), the single Claude call of this dispatch; "
            "round 1 of this unit made one other. It resumed the round-1 interrupted session, whose turn 1 was a user "
            "prompt plus a partial, interrupted answer.",
            "The Claude init still listed the account-level claude.ai Claude Docs MCP server with setting_sources=[] "
            "(same as round 1).",
        ]
    r["checked_at"] = block["checked_at"]
    p.write_text(json.dumps(r, indent=2) + "\n")
    # Gap 1: observation only
    p, r = load("1")
    c = raw("claude-resume.json")
    mu = next(iter(((c.get("result") or {}).get("model_usage") or {}).values()), {})
    u = (c.get("result") or {}).get("usage") or {}
    r["round_3_observation"] = {
        "source": cite("claude-resume.json", "claude-resume.session-appended-excerpt.jsonl"),
        "completed_query_usage": {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens")},
        "completed_query_model_usage": {"inputTokens": mu.get("inputTokens"), "outputTokens": mu.get("outputTokens")},
        "difference": {"input": (mu.get("inputTokens") or 0) - (u.get("input_tokens") or 0),
                       "output": (mu.get("outputTokens") or 0) - (u.get("output_tokens") or 0)},
        "reading": "On a completed query, model_usage exceeds the message usage by 921 input / 17 output tokens, the same "
                   "figures as round 1's whole model_usage on the interrupted query. That fits one auxiliary request of "
                   "about that size per query, and it suggests the interrupted main request's consumption was left out of "
                   "round 1's model_usage. Two observations, one model: an inference, not a measurement of provider "
                   "consumption; the gap's consumption clause stays open.",
    }
    p.write_text(json.dumps(r, indent=2) + "\n")
    # Gap 9: note only
    p, r = load("9")
    r["round_3_note"] = ("The Claude Agent SDK resume in a new process now ran (gap 13 round 3, raw/round3/claude-resume.json), "
                         "on a different task. The matched run still lacks the Claude custom tool and interrupt on the same "
                         "fixed task and the checklist scoring.")
    p.write_text(json.dumps(r, indent=2) + "\n")


if __name__ == "__main__":
    apply()
