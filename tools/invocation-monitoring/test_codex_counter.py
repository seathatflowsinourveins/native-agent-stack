"""Synthetic Q6 controls; never native organic-use or upstream acceptance.

Native identity shapes: openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb
codex-rs/protocol/src/models.rs:1061-1159, protocol.rs:1948-1960,2179-2184.
Oracle reuse: native-agent-stack@57b9476d tools/skill-usage/skill_usage.py:1336-1342
and tests/test_skill_usage.py:3259-3278: outer exec and nested command are two
calls; missing-N adapter IDs are null; original calls/results join before masks.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

_SPEC = importlib.util.spec_from_file_location("codex_counter", Path(__file__).with_name("codex_counter.py"))
c = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(c)


class CounterChecks(unittest.TestCase):
    def test_native_command_read_attempts_and_shell_argv(self):
        name = "/tmp/skills/.system/openai-docs/SKILL.md"
        counts, unknown = c.shell_reads(["/bin/bash", "-lc", f"env X=1 rtk proxy sed -n '1,9p' {name}"])
        self.assertEqual(counts, {"openai-docs": 1})
        self.assertEqual(unknown, 0)
        self.assertEqual(c.shell_reads(["rtk", "cat", name])[0], {"openai-docs": 1})
        self.assertEqual(c.shell_reads(["rtk", "proxy", "head", "-n", "8", name])[0], {"openai-docs": 1})
        self.assertEqual(c.shell_reads(["/bin/bash", "-lc", f"rtk cat {name}; rtk tail {name}"])[0], {"openai-docs": 1})
        self.assertEqual(c.shell_reads(["rtk", "--shell", "cat", name])[0], {"openai-docs": 1})
        self.assertEqual(c.shell_reads(["env", "X=1", "rtk", "proxy", "cat", name])[0], {"openai-docs": 1})
        self.assertEqual(c.shell_reads(f"X=1 rtk proxy cat {name}")[0], {"openai-docs": 1})
        for invalid in (["proxy", "cat", name], ["--shell", "cat", name], ["--unknown", "cat", name], ["unknown", "proxy", "cat", name], ["rtk", "--unknown", "cat", name], ["rtk", "env", "cat", name], ["X=1", "cat", name], ["rtk", "X=1", "cat", name], ["X=1"]):
            with self.subTest(invalid=invalid):
                self.assertEqual(c.shell_reads(invalid)[0], {})
        self.assertEqual(c.shell_reads(f"false && rtk cat {name}")[0], {})
        self.assertEqual(c.shell_reads(f"echo '{name}' && rtk cat {name}")[0], {})
        self.assertEqual(c.shell_reads(f"X='cat {name}'")[0], {})
        self.assertEqual(c.shell_reads(f"echo '{name}'")[0], {})
        self.assertEqual(c.shell_reads(["printf", ";", "cat", name])[0], {})
        self.assertEqual(c.shell_reads(["python3", "-c", f"open('{name}')"])[0], {})
        self.assertEqual(c.shell_reads(["python3", "-c", f"example = 'cat {name}'; open('{name}')"])[0], {})
        self.assertEqual(c.shell_reads(f"python3 - <<'PY'\ncat {name}\nPY")[0], {})
        self.assertEqual(c.shell_reads(["rtk", "sed", "-e", name, "/tmp/ordinary.txt"])[0], {})
        self.assertEqual(c.item_reads({"type": "McpToolCall", "tool": "ctx_execute", "arguments": {"language": "python", "code": f"open('{name}')"}}), ({}, 0))
        self.assertEqual(c.item_reads({"type": "McpToolCall", "tool": "ctx_execute", "arguments": {"language": "shell", "code": f"cat {name}"}}), ({}, 0))
        self.assertEqual(c.item_reads({"type": "McpToolCall", "tool": "ctx_execute", "arguments": {"language": "javascript", "code": "tools.mcp__serena__search({})"}}), ({}, 0))
        self.assertEqual(c.item_reads({"type": "CommandExecution", "command": ["rtk", "cat", name], "exit_code": 1})[0], {"openai-docs": 1})

    def test_native_window_fork_identity_duplicates_and_excluded_extension(self):
        since, until = c.instant("2026-10-06T13:55:00Z"), c.instant("2026-10-06T15:25:00Z")
        def row(ordinal, kind, payload, timestamp="2026-10-06T14:00:00Z"):
            return {"ordinal": ordinal, "type": kind, "payload": payload, "timestamp": timestamp}
        def item(ordinal, ident, item_type, **kw):
            return row(ordinal, "event_msg", {"type": "item_completed", "item": {"id": ident, "type": item_type, **kw}})
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "sessions"; home.mkdir()
            root = home / "rollout-root.jsonl"
            child = home / "rollout-child.jsonl"
            copied = home / "rollout-clone.jsonl"
            root_rows = [row(0, "session_meta", {"id": "root", "cwd": "/misleading/lane"}), item(1, "one", "CommandExecution", command="echo example"), item(2, "two", "Extension", kind="web.search"), row(3, "event_msg", {"type": "user_message", "message": "Use serena; <skill>openai-docs</skill>"}), item(4, "three", "McpToolCall", server="serena", tool="search", status="failed"), item(5, "boundary", "CommandExecution", command="echo", timestamp="ignored")]
            root_rows[-1]["timestamp"] = "2026-10-06T15:25:00Z"
            child_rows = [row(0, "session_meta", {"id": "child", "source": {"subagent": {"thread_spawn": {"parent_thread_id": "root"}}}, "subagent_history_start_ordinal": 3}), item(1, "copied", "CommandExecution", command="echo"), item(3, "four", "McpToolCall", server="context-mode", tool="ctx_execute", arguments={"language": "javascript", "code": "tools.fake();"})]
            for path, rows in ((root, root_rows), (child, child_rows), (copied, root_rows)):
                path.write_text("\n".join(json.dumps(r) for r in rows))
            result = c.scan([root, child, copied], {"root": {"lane": "real", "identity_source": "hcom_live"}}, {}, {}, since, until, home)
            self.assertEqual(result["totals"]["raw"]["counts"]["cmd"], 1)
            self.assertNotIn("web_search", result["totals"]["raw"]["counts"])
            self.assertNotIn("item:Extension", result["totals"]["raw"]["counts"])
            self.assertEqual(result["totals"]["raw"]["counts"]["mcp:context-mode"], 1)
            self.assertEqual(result["totals"]["organic"]["counts"]["mcp:serena"], 0)
            self.assertEqual(result["diagnostics"]["fork_copied_rows_excluded"], 1)
            self.assertEqual(result["duplicate_owner_files"], 1)
            self.assertEqual(result["threads"]["child"]["canonical_root"], "root")
            self.assertEqual(result["totals"]["raw"]["skill_command_read_attempts"], {})
            self.assertEqual(result["totals"]["raw"]["skill_user_injections"], {"openai-docs": 1})
            self.assertNotIn("misleading", result["by_lane"])
            excluded = c.scan([root, child], {"root": {"lane": "real", "identity_source": "hcom_live"}}, {}, {}, since, until, home, {"real": [(since, until, "relaunch_first_turn")]})
            self.assertEqual(excluded["totals"]["organic"]["counts"]["cmd"], 0)
            self.assertEqual(excluded["totals"]["raw"]["counts"]["cmd"], 1)
            self.assertGreater(excluded["diagnostics"]["excluded_relaunch_first_turn"], 0)

    def test_private_home_discovery_prunes_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            native = state / "sdk" / "codex-home" / "sessions"
            auth = state / "auth" / "sessions"
            for directory in (native, auth):
                directory.mkdir(parents=True); (directory / "rollout-one.jsonl").write_text("")
            homes = c.discover(state / "default", state)
            self.assertIn(native, homes)
            self.assertNotIn(auth, homes)


PIN = "57b9476db9d9c422d947c7c974d2c05f1ecff30b"


def proof(pointer=""):
    return {"path": "fixtures/q6-controls.json", "pointer": pointer,
            "sha256": "b" * 64, "source_commit": PIN}


def native_row(kind, payload, at="2026-10-07T02:01:00Z", ordinal=5):
    return {"type": kind, "payload": payload, "timestamp": at, "ordinal": ordinal}


def started(turn, at="2026-10-07T02:01:00Z", ordinal=3, root_turn=None):
    return native_row("event_msg", {"type": "task_started", "turn_id": turn,
                                    "root_turn_id": root_turn}, at, ordinal)


def finished(turn, at="2026-10-07T02:02:00Z", ordinal=9):
    return native_row("event_msg", {"type": "task_complete", "turn_id": turn}, at, ordinal)


def command(ident="cmd-1", command="echo fixture", status="completed", turn="work", ordinal=5):
    return native_row("event_msg", {"type": "item_completed", "thread_id": "owner",
                                    "turn_id": turn, "item": {"id": ident, "type": "CommandExecution",
                                    "source": "agent", "command": command, "status": status,
                                    "exit_code": 1 if status == "failed" else 0,
                                    "aggregated_output": "fixture"}}, ordinal=ordinal)


def mcp(ident="mcp-1", server="serena", tool="search", turn="work", ordinal=6, owner="owner"):
    return native_row("event_msg", {"type": "item_completed", "thread_id": owner,
                                    "turn_id": turn, "item": {"id": ident, "type": "McpToolCall",
                                    "server": server, "tool": tool, "status": "completed",
                                    "arguments": {}, "result": {"content": [{"type": "text", "text": "fixture"}]}}}, ordinal=ordinal)


def function(ident, name="exec_command", args=None, response_id=None, namespace=None):
    payload = {"type": "function_call", "call_id": ident, "name": name,
               "arguments": json.dumps(args or {"cmd": "echo fixture"})}
    if response_id is not None:
        payload["id"] = response_id
    if namespace is not None:
        payload["namespace"] = namespace
    return native_row("response_item", payload)


def returned(ident, custom=False, output=None):
    return native_row("response_item", {"type": "custom_tool_call_output" if custom else "function_call_output",
                                       "call_id": ident, "output": output or "Wall time: 0.1 seconds\nProcess exited with code 0\nOutput:\nfixture"}, ordinal=7)


def records(*calls, owner="owner", parent=None):
    meta = {"id": owner, "source": "cli", "cli_version": "0.160.1", "history_mode": "paginated"}
    if parent:
        meta["source"] = {"subagent": {"thread_spawn": {"parent_thread_id": parent}}}
    return [native_row("session_meta", meta, "2026-10-07T01:58:00Z", 0),
            started("bootstrap", "2026-10-07T01:58:01Z", 1),
            finished("bootstrap", "2026-10-07T01:59:00Z", 2),
            started("work"), *calls, finished("work")]


def turn_control(owner="owner", turn="work"):
    return {"owner_id": owner, "turn_id": turn, "requested": False, "smoke": False,
            "classification_ref": proof("/turns/0/classification"), "context_complete": True,
            "context_refs": [], "named_tools": [], "mask_ref": proof("/turns/0/mask")}


def inputs(*streams):
    batches, sources, turns = [], {}, []
    for index, stream in enumerate(streams):
        source_id = "source-" + str(index)
        encoded = "\n".join(json.dumps(r, sort_keys=True) for r in stream).encode()
        sha = hashlib.sha256(encoded).hexdigest()
        owner = stream[0]["payload"]["id"]
        batches.append({"source_id": source_id, "records": stream, "sha256": sha})
        source_ref = {**proof(), "sha256": sha}
        sources[source_id] = {"owner_id": owner, "native_source": True, "history_complete": True,
                              "source_ref": source_ref, "history_ref": proof("/history")}
        for turn in {r.get("payload", {}).get("turn_id") for r in stream} - {None}:
            if not any(t["owner_id"] == owner and t["turn_id"] == turn for t in turns):
                turns.append(turn_control(owner, turn))
    tools = {
        "command": {"kind": "command", "native_names": ["Bash"], "prompt_names": ["bash", "exec_command"]},
        "rtk": {"kind": "rtk", "native_names": ["rtk"], "prompt_names": ["rtk"]},
        "openai-docs-read": {"kind": "skill_read_attempt", "native_names": ["openai-docs"], "prompt_names": ["openai-docs"]},
        "serena": {"kind": "mcp", "native_names": ["mcp__serena__search"], "prompt_names": ["serena", "mcp__serena__search"]},
        "context-mode": {"kind": "mcp", "native_names": ["mcp__context-mode__ctx_execute"], "prompt_names": ["context-mode", "mcp__context-mode__ctx_execute"]},
        "exec": {"kind": "native", "native_names": ["exec"], "prompt_names": ["exec"]},
        "apply_patch": {"kind": "native", "native_names": ["apply_patch"], "prompt_names": ["apply_patch"]},
    }
    return batches, {"schema": c.CONTROL_SCHEMA, "policy_ref": proof("/policy"),
                     "masks_ref": proof("/masks"), "sources": sources, "turns": turns,
                     "tools": tools, "relaunch_masks": []}


class OrganicControlChecks(unittest.TestCase):
    since = c.instant("2026-10-07T02:00:00Z")
    until = c.instant("2026-10-07T02:10:00Z")

    def run_controls(self, streams, change=None):
        batches, controls = inputs(*streams)
        if change:
            change(batches, controls)
        return c.qualify_records(batches, since=self.since, until=self.until, controls=controls)

    def test_normal_second_turn_retains_failed_skill_read_as_attempt(self):
        result = self.run_controls([records(command(command="rtk cat /fixture/skills/openai-docs/SKILL.md", status="failed"), mcp())])
        self.assertEqual(result["status"], "controls_complete")
        self.assertEqual(result["native_call_attempts"], 2)
        for key in ("command", "rtk", "openai-docs-read", "serena"):
            self.assertEqual(result["by_tool"][key]["organic_count"], 1)
        self.assertEqual(result["native_call_states"], {"failed": 1, "succeeded": 1})
        self.assertIn("no READY", result["claim"])
        self.assertNotIn("skill_activations", result)

    def test_requested_and_smoke_are_explicit_all_class_exclusions(self):
        calls = [command(command="rtk cat /fixture/skills/openai-docs/SKILL.md"), mcp(),
                 native_row("response_item", {"type": "custom_tool_call", "name": "apply_patch", "call_id": "custom", "input": "fixture"}), returned("custom", True, "fixture")]
        for flag in ("requested", "smoke"):
            with self.subTest(flag=flag):
                result = self.run_controls([records(*calls)], lambda _, control: next(t for t in control["turns"] if t["turn_id"] == "work").update({flag: True}))
                self.assertEqual(result["native_call_attempts"], 3)
                for key in ("command", "rtk", "openai-docs-read", "serena", "apply_patch"):
                    self.assertEqual(result["by_tool"][key]["organic_count"], 0)
                    self.assertEqual(result["by_tool"][key]["reasons"][flag], 1)

    def test_absent_classifier_or_provenance_is_unknown_not_false(self):
        for field in ("requested", "smoke", "classification_ref"):
            with self.subTest(field=field):
                result = self.run_controls([records(command())], lambda _, control: next(t for t in control["turns"] if t["turn_id"] == "work").pop(field))
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])
                self.assertEqual(result["by_tool"]["command"]["reasons"]["run_classification_unknown"], 1)

    def test_smoke_prose_does_not_supply_a_classifier(self):
        text = native_row("event_msg", {"type": "user_message", "turn_id": "work", "message": "Run the integration smoke now"})
        result = self.run_controls([records(text, command())], lambda _, control: next(t for t in control["turns"] if t["turn_id"] == "work").pop("smoke"))
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_first_native_turn_all_classes_and_relaunch_masks(self):
        stream = records(command(command="rtk cat /fixture/skills/openai-docs/SKILL.md"), mcp())
        stream = [stream[0], *stream[3:]]  # work is now the first native turn
        result = self.run_controls([stream])
        for key in ("command", "rtk", "openai-docs-read", "serena"):
            self.assertEqual(result["by_tool"][key]["organic_count"], 0)
            self.assertEqual(result["by_tool"][key]["reasons"]["first_native_turn"], 1)
        def relaunch(_, control):
            control["relaunch_masks"] = [{"owner_id": "owner", "turn_id": "work", "ref": proof("/relaunch")}]
        result = self.run_controls([records(command(), mcp())], relaunch)
        for key in ("command", "serena"):
            self.assertEqual(result["by_tool"][key]["organic_count"], 0)
            self.assertIn("relaunch_first_turn", result["by_tool"][key]["reasons"])

    def test_history_or_native_source_absence_cannot_certify_first_turn(self):
        for field in ("history_complete", "history_ref", "native_source", "source_ref"):
            with self.subTest(field=field):
                result = self.run_controls([records(command())], lambda _, control: control["sources"]["source-0"].pop(field))
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_late_full_turn_names_mask_only_the_relevant_tools(self):
        late = native_row("event_msg", {"type": "user_message", "turn_id": "work", "message": "Use rtk, openai-docs and serena"}, ordinal=8)
        result = self.run_controls([records(command(command="rtk cat /fixture/skills/openai-docs/SKILL.md"), mcp(), mcp("ctx", "context-mode", "ctx_execute"), late)])
        for key in ("rtk", "openai-docs-read", "serena"):
            self.assertEqual(result["by_tool"][key]["organic_count"], 0)
            self.assertEqual(result["by_tool"][key]["reasons"]["named_turn"], 1)
        for key in ("command", "context-mode"):
            self.assertEqual(result["by_tool"][key]["organic_count"], 1)

    def test_native_command_name_masks_the_entire_turn(self):
        late = native_row("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Use exec_command"}]}, ordinal=8)
        result = self.run_controls([records(command(), late)])
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 0)

    def test_explicit_referenced_context_masks_and_unresolved_context(self):
        def referenced(_, control):
            next(t for t in control["turns"] if t["turn_id"] == "work")["context_refs"] = [{"ref": proof("/cooperation/task"), "resolved": True, "named_tools": ["serena"]}]
        result = self.run_controls([records(command(), mcp())], referenced)
        self.assertEqual(result["by_tool"]["serena"]["organic_count"], 0)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 1)
        def unresolved(batch, control):
            referenced(batch, control)
            next(t for t in control["turns"] if t["turn_id"] == "work")["context_refs"][0]["resolved"] = False
        result = self.run_controls([records(command(), mcp())], unresolved)
        self.assertIsNone(result["by_tool"]["serena"]["organic_count"])
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_parent_attribution_and_copied_prefix_use_native_root_turn(self):
        parent = records(command(), native_row("event_msg", {"type": "user_message", "turn_id": "work", "message": "Use serena"}, ordinal=8))
        child = records(owner="child", parent="owner")
        child[0]["payload"]["subagent_history_start_ordinal"] = 5
        child = [child[0], command("parent-copy", ordinal=1),
                 started("child-first", ordinal=5, root_turn="work"), finished("child-first", ordinal=6),
                 started("child-work", ordinal=7, root_turn="work"), mcp("child-mcp", turn="child-work", ordinal=8, owner="child"), finished("child-work", ordinal=9)]
        def bind_parent(_, control):
            for turn in control["turns"]:
                if turn["owner_id"] == "child":
                    turn.update({"parent_turn": {"owner_id": "owner", "turn_id": "work"}, "parent_ref": proof("/parent")})
        result = self.run_controls([parent, child], bind_parent)
        self.assertEqual(result["native_call_attempts"], 2)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 1)
        self.assertEqual(result["by_tool"]["serena"]["organic_count"], 0)
        def missing(batch, control):
            bind_parent(batch, control)
            next(t for t in control["turns"] if t["turn_id"] == "child-work").pop("parent_ref")
        result = self.run_controls([parent, child], missing)
        self.assertIsNone(result["by_tool"]["serena"]["organic_count"])
        self.assertIn("parent_attribution_unknown", result["by_tool"]["serena"]["reasons"])

    def test_fork_missing_ordinal_and_missing_root_turn_are_unknown(self):
        parent = records(command())
        child = records(mcp(owner="child"), owner="child", parent="owner")
        child[0]["payload"]["subagent_history_start_ordinal"] = 1
        for changed in ("root", "ordinal"):
            with self.subTest(changed=changed):
                altered = copy.deepcopy(child)
                if changed == "ordinal":
                    altered[-2].pop("ordinal")
                def bind(_, control):
                    for turn in control["turns"]:
                        if turn["owner_id"] == "child":
                            turn.update({"parent_turn": {"owner_id": "owner", "turn_id": "work"}, "parent_ref": proof("/parent")})
                result = self.run_controls([parent, altered], bind)
                self.assertIsNone(result["by_tool"]["serena"]["organic_count"])

    def test_function_custom_completion_join_keeps_outer_exec_distinct(self):
        outer = native_row("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "outer", "input": "return await tools.exec_command({cmd:'echo fixture'});"})
        result = self.run_controls([records(function("direct"), returned("direct"), command("direct"),
                                            outer, command("nested"), returned("outer", True, "fixture"),
                                            function("mcp-direct", "search", {}, namespace="mcp__serena"), returned("mcp-direct", output="fixture"), mcp("mcp-direct"))])
        self.assertEqual(result["native_call_attempts"], 4)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 2)
        self.assertEqual(result["by_tool"]["exec"]["organic_count"], 1)
        self.assertEqual(result["by_tool"]["serena"]["organic_count"], 1)

    def test_proven_response_id_alias_dedups_only_with_original_link(self):
        for linked, expected in ((True, 1), (False, 2)):
            with self.subTest(linked=linked):
                response = function("native-call", response_id="ui-item" if linked else None)
                result = self.run_controls([records(response, returned("native-call"), command("ui-item"))])
                self.assertEqual(result["native_call_attempts"], expected)
                self.assertEqual(result["by_tool"]["command"]["organic_count"], expected)

    def test_duplicate_files_dedup_owner_id_but_distinct_owners_do_not(self):
        stream = records(function("native-call"), returned("native-call"))
        duplicate = self.run_controls([stream, copy.deepcopy(stream)])
        self.assertEqual(duplicate["native_call_attempts"], 1)
        self.assertEqual(duplicate["diagnostics"]["duplicate_native_calls"], 1)
        other = records(function("native-call"), returned("native-call"), owner="independent")
        separate = self.run_controls([stream, other])
        self.assertEqual(separate["native_call_attempts"], 2)

    def test_missing_ids_and_invalid_function_id_fallback_remain_unknown(self):
        for mode in ("no-id", "id-without-required-call-id"):
            with self.subTest(mode=mode):
                response = function("native-call")
                response["payload"].pop("call_id")
                if mode != "no-id":
                    response["payload"]["id"] = "response-only"
                result = self.run_controls([records(response)])
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])
                self.assertEqual(result["by_tool"]["command"]["native_attempts"], 1)
        no_item_id = command(); no_item_id["payload"]["item"].pop("id")
        result = self.run_controls([records(no_item_id)])
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_unjoined_results_unfinished_calls_and_new_format_are_unknown(self):
        for call in (returned("orphan"), function("unfinished"),
                     native_row("response_item", {"type": "tool_search_call", "call_id": "new", "arguments": "{}", "execution": "client"})):
            with self.subTest(kind=call["payload"]["type"]):
                result = self.run_controls([records(call)])
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_source_hash_ref_and_owner_mismatch_are_not_accepted(self):
        for field, replacement in (("owner_id", "other"), ("source_ref", proof()), ("history_ref", {"path": "not-a-reference"})):
            with self.subTest(field=field):
                result = self.run_controls([records(command())], lambda _, control: control["sources"]["source-0"].update({field: replacement}))
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_original_records_are_not_pruned_before_maintained_ledger(self):
        stream = records(function("original"), returned("original"), command("original"))
        batches, control = inputs(stream)
        next(t for t in control["turns"] if t["turn_id"] == "work")["requested"] = True
        with mock.patch.object(c._USAGE, "measure_codex_records", wraps=c._USAGE.measure_codex_records) as measure:
            result = c.qualify_records(batches, since=self.since, until=self.until, controls=control)
        self.assertEqual(measure.call_count, 1)
        self.assertIs(measure.call_args.args[0], stream)
        self.assertEqual(len(measure.call_args.args[0]), len(stream))
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 0)

    def test_window_uses_original_call_not_a_later_completion(self):
        early = function("early")
        early["timestamp"] = "2026-10-07T01:59:59Z"
        result = self.run_controls([records(early, returned("early"), command("early"))])
        self.assertEqual(result["native_call_attempts"], 0)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 0)

    def test_proven_alias_preserves_original_call_window(self):
        early = function("early", response_id="ui-early")
        early["timestamp"] = "2026-10-07T01:59:59Z"
        result = self.run_controls([records(early, returned("early"), command("ui-early"))])
        self.assertEqual(result["native_call_attempts"], 0)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 0)

    def test_alias_original_after_until_cannot_enter_window(self):
        late = function("native-late", response_id="ui-late")
        late["timestamp"] = "2026-10-07T02:10:00Z"
        outcome = returned("native-late")
        outcome["timestamp"] = "2026-10-07T02:10:01Z"
        result = self.run_controls([records(command("ui-late"), late, outcome)])
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["native_call_attempts"], 0)
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_original_alias_and_result_join_across_same_owner_sources(self):
        original = records(function("C", response_id="R"))
        completion = records(command("R"), returned("C"))
        result = self.run_controls([original, completion])
        self.assertEqual(result["status"], "controls_complete")
        self.assertEqual(result["native_call_attempts"], 1)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 1)
        self.assertEqual(result["native_call_states"], {"succeeded": 1})

    def test_unsupported_completed_call_variants_are_unknown(self):
        # protocol/src/items.rs:46-78 at d27764b: these are call/execution
        # variants, not a proof that the legacy bridge supports their payloads.
        for kind in ("DynamicToolCall", "CollabAgentToolCall", "WebSearch", "ImageView", "Extension", "ImageGeneration", "FileChange"):
            with self.subTest(kind=kind):
                call = native_row("event_msg", {"type": "item_completed", "thread_id": "owner", "turn_id": "work", "item": {"id": "unsupported", "type": kind}})
                result = self.run_controls([records(call)])
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_primary_documented_non_call_completions_are_not_invocations(self):
        for kind in ("UserMessage", "FunctionCallOutput", "HookPrompt", "AgentMessage", "Plan", "Reasoning", "ContextCompaction"):
            with self.subTest(kind=kind):
                other = native_row("event_msg", {"type": "item_completed", "thread_id": "owner", "turn_id": "work", "item": {"id": "non-call", "type": kind}})
                result = self.run_controls([records(command(), other)])
                self.assertEqual(result["status"], "controls_complete")
                self.assertEqual(result["native_call_attempts"], 1)
                self.assertEqual(result["by_tool"]["command"]["organic_count"], 1)

    def test_reference_pointer_invalid_escape_is_unknown(self):
        def invalid(_, control):
            control["policy_ref"]["pointer"] = "/invalid~2escape"
        result = self.run_controls([records(command())], invalid)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_conflicting_native_representation_is_unknown(self):
        result = self.run_controls([records(function("call", response_id="alias"), returned("call"), mcp("alias"))])
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])
        good, bad = records(command()), records(command(status="failed"))
        result = self.run_controls([good, bad])
        self.assertEqual(result["status"], "unknown")
        self.assertIn("conflicting_native_representation", result["diagnostics"])

    def test_declined_native_attempt_is_not_an_executed_invocation(self):
        result = self.run_controls([records(command(status="declined"))])
        self.assertEqual(result["by_tool"]["command"]["native_attempts"], 1)
        self.assertEqual(result["by_tool"]["command"]["organic_count"], 0)
        self.assertEqual(result["by_tool"]["command"]["reasons"]["native_not_executed"], 1)

    def test_native_owner_and_turn_context_ids_are_required(self):
        for field in ("thread_id", "turn_id"):
            with self.subTest(field=field):
                call = command()
                call["payload"].pop(field)
                if field == "turn_id":
                    # No active native turn can supply attribution either.
                    stream = [records()[0], call]
                else:
                    stream = records(call)
                result = self.run_controls([stream])
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["by_tool"]["command"]["organic_count"])

    def test_hosted_search_completion_joins_or_remains_unknown(self):
        response = native_row("response_item", {"type": "web_search_call", "id": "search", "status": "completed"})
        completion = native_row("event_msg", {"type": "item_completed", "thread_id": "owner", "turn_id": "work",
                "item": {"type": "Extension", "kind": "web.search", "id": "search", "action": {"type": "search", "query": "fixture"}}})
        def add_tool(_, control):
            control["tools"]["web"] = {"kind": "native", "native_names": ["WebSearch"], "prompt_names": ["web-search"]}
        result = self.run_controls([records(response, completion)], add_tool)
        self.assertEqual(result["native_call_attempts"], 1)
        self.assertEqual(result["by_tool"]["web"]["organic_count"], 1)
        result = self.run_controls([records(response)], add_tool)
        self.assertIsNone(result["by_tool"]["web"]["organic_count"])

    def test_prompt_metadata_does_not_name_a_tool(self):
        prompt = native_row("event_msg", {"type": "user_message", "turn_id": "work", "message": "Review the implementation", "metadata": {"unrelated_owner": "serena"}})
        result = self.run_controls([records(prompt, mcp())])
        self.assertEqual(result["by_tool"]["serena"]["organic_count"], 1)

    def test_malformed_policy_and_empty_census_are_distinct(self):
        batches, control = inputs(records(command()))
        with self.assertRaises(ValueError):
            c.qualify_records(batches, since=self.since, until=self.until, controls={})
        result = c.qualify_records([], since=self.since, until=self.until, controls=control)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["by_tool"]["command"]["organic_count"])


if __name__ == "__main__":
    unittest.main()
