"""Pending synthetic fixture checks; source edited without running in quiet window."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
