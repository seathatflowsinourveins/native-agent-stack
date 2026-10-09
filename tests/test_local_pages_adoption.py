"""Source-shape and HTML contracts for the read-only adoption view."""

import copy
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_pages_adoption_view", ROOT / "tools/local-pages/adoption_view.py")
view = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(view)


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.current = []
            self.tables.append(self.current)
        elif tag == "tr":
            self.row = []
            self.current.append(self.row)
        elif tag in ("th", "td"):
            self.cell = ""

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None

    def handle_data(self, text):
        if self.cell is not None:
            self.cell += text


def fixture():
    return {
        "schema": "adoption-now/1", "generated_utc": "2026-10-08T23:42:51Z", "window_hours": 24,
        "claude_total_sessions": 63, "codex_total_conversations": 841,
        "layers": {
            "session context and token efficiency": {"servers": {"context-mode": {"claude_calls": 10, "claude_sessions": 2, "codex_calls": 9, "codex_conversations": 3}}},
            "code intelligence": {"servers": {"socraticode": {"claude_calls": 2, "claude_sessions": 1, "codex_calls": 1, "codex_conversations": 1}}},
            "browser": {"servers": {}},
        },
        "claude_by_role": {
            "native-agent-stack-1a": {"servers": {"plugin_context-mode_context-mode": {"calls": 7, "sessions": 1}, "context-mode": {"calls": 3, "sessions": 1}, "plugin_socraticode_socraticode": {"calls": 2, "sessions": 1}}, "sessions": 1, "tool_calls": 30},
            "other Claude sessions": {"servers": {}, "sessions": 2, "tool_calls": 5},
            "review-replay (transient)": {"servers": {}, "sessions": 3, "tool_calls": 4},
        },
        "codex_by_lane": {"mahe": {"conversations": 2, "servers": {"plugin_context-mode_context-mode": {"calls": 9, "conversations": 2}}}},
    }


class AdoptionTests(unittest.TestCase):
    def parse(self, html):
        parser = Tables()
        parser.feed(html)
        return parser.tables

    def test_exact_aliases_associate_to_layer_without_double_count(self):
        tables = self.parse(view.roles(fixture()))
        owner = tables[0][1]
        self.assertEqual(owner, ["owner session (reports to CC)", "1", "10", "2", "0"])
        self.assertEqual(tables[1][1], ["mahe", "2", "9", "0", "0"])
        self.assertEqual(len(tables[2]) - 1, 4)

    def test_owner_session_has_exact_display_label_in_both_client_groups(self):
        document = fixture()
        document["codex_by_lane"]["native-agent-stack-1a"] = {"conversations": 1, "servers": {}}
        html = view.roles(document)
        self.assertNotIn("native-agent-stack-1a", html)
        self.assertEqual(html.count("owner session (reports to CC)"), 5)
        self.assertIn("other Claude sessions", html)
        self.assertIn("review-replay (transient)", html)

    def test_sparse_missing_record_is_zero_but_missing_count_is_unknown(self):
        document = fixture()
        document["claude_by_role"]["other Claude sessions"]["servers"] = {"context-mode": {"sessions": None}}
        document["codex_by_lane"]["mahe"]["servers"] = None
        tables = self.parse(view.roles(document))
        self.assertEqual(tables[0][2][2:], ["not reported", "0", "0"])
        self.assertEqual(tables[1][1][2:], ["not reported"] * 3)
        document["layers"]["browser"]["servers"] = None
        summary = self.parse(view.summary(document))[0]
        self.assertEqual(summary[-1], ["browser", "not reported", "not reported"])

    def test_invalid_server_map_never_becomes_zero(self):
        for invalid in ([], "unknown", 0):
            document = fixture()
            document["claude_by_role"]["other Claude sessions"]["servers"] = invalid
            with self.assertRaises(ValueError):
                view.roles(document)
        document = fixture()
        del document["layers"]["browser"]["servers"]
        with self.assertRaises(ValueError):
            view.summary(document)

    def test_counts_hours_and_time_are_validated(self):
        for invalid in (-1, 1.5, True, "1"):
            document = fixture()
            document["layers"]["browser"]["servers"] = {"chrome-devtools": {"claude_calls": invalid}}
            with self.assertRaises(ValueError):
                view.validate(document)
        for invalid in (0, -1, True, None, "24"):
            document = fixture()
            document["window_hours"] = invalid
            with self.assertRaises(ValueError):
                view.validate(document)
        for invalid in ("bad", "2026-10-08T23:42:51", "2026-10-08T23:42:51+04:00"):
            document = fixture()
            document["generated_utc"] = invalid
            with self.assertRaises(ValueError):
                view.validate(document)
        document = fixture()
        document["claude_total_sessions"] = None
        self.assertIn("not reported Claude sessions", view.summary(document))

    def test_all_134_published_codex_rows_are_accessible(self):
        document = fixture()
        document["codex_by_lane"] = {f"historic-lane-{i}": {"conversations": i, "servers": {}} for i in range(134)}
        html = view.roles(document)
        tables = self.parse(html)
        self.assertEqual(len(tables[1]) - 1, 134)
        self.assertIn("Codex: 134 published labels", html)
        self.assertIn("historic-lane-133", html)
        self.assertNotIn("<details open", html)
        self.assertIn('scope="col"', html)
        self.assertIn('scope="row"', html)
        self.assertIn("<caption>", html)

    def test_labels_are_escaped_and_sensitive_free_text_is_excluded(self):
        document = fixture()
        document["codex_by_lane"] = {label: {"conversations": 1, "servers": {}, "prompt": "PRIVATE-PROMPT", "task": "PRIVATE-TASK"} for label in ["review & replay", "lane<script>", "owner@example.test", "abcdefghijklmnopqrstuvwx1234567890"]}
        document["method"] = "PRIVATE-PROMPT"
        html = view.roles(document) + view.summary(document)
        self.assertIn("review &amp; replay", html)
        for forbidden in ("<script>", "owner@example.test", "abcdefghijklmnopqrstuvwx1234567890", "PRIVATE-PROMPT", "PRIVATE-TASK"):
            self.assertNotIn(forbidden, html)

    def test_rendering_is_read_only_and_preserves_observation_time(self):
        document = fixture()
        before = copy.deepcopy(document)
        html = view.summary(document) + view.roles(document)
        self.assertEqual(document, before)
        self.assertIn('datetime="2026-10-08T23:42:51Z"', html)
        self.assertIn("Last 24 hours", html)
        self.assertIn("Zero means no recorded calls in this window", html)
        self.assertIn("do not establish adoption acceptance", html)

    def test_conflicting_alias_layers_are_rejected(self):
        document = fixture()
        document["layers"]["browser"]["servers"] = {"plugin_context-mode_context-mode": {"claude_calls": 1}}
        with self.assertRaises(ValueError):
            view.validate(document)

    def test_similar_server_substrings_do_not_gain_alias_membership(self):
        document = fixture()
        document["codex_by_lane"]["mahe"]["servers"] = {"context-mode-not-the-server": {"calls": 100}}
        table = self.parse(view.roles(document))[1]
        self.assertEqual(table[1][2:], ["0", "0", "0"])

    def test_producer_codex_roles_are_preferred_to_instance_labels(self):
        document = fixture()
        document["codex_by_role"] = {"g5-stars-gap": {"conversations": 2, "servers": {"context-mode": {"calls": 9, "conversations": 2}}}}
        html = view.roles(document)
        self.assertIn("g5-stars-gap", html)
        self.assertNotIn("mahe", html)
        self.assertIn("Codex: 1 published roles", html)

    def test_instance_label_fallback_is_explicitly_dated(self):
        html = view.roles(fixture())
        self.assertIn("recorded instance labels", html)
        self.assertIn("2026-10-08T23:42:51Z", html)

    def test_explicit_unavailable_projection_is_unknown_without_false_zero(self):
        document = {"schema": "adoption-now/1", "status": "UNREPORTED", "reason": "published adoption source unavailable", "generated_utc": None, "window_hours": None, "layers": None, "claude_by_role": None, "codex_by_lane": None, "claude_total_sessions": None, "codex_total_conversations": None}
        view.validate(document)
        html = view.summary(document) + view.roles(document)
        self.assertIn("UNKNOWN", html)
        self.assertIn("published adoption source unavailable", html)
        self.assertNotIn("0 Claude sessions", html)
        self.assertNotIn("Last None hours", html)

    def test_shared_identity_projection_keeps_raw_memberships_and_counts(self):
        document = fixture()
        identity = "-".join(["dummy", "synthetic", "user"])
        document["codex_by_role"] = {identity: {"conversations": 3, "servers": {"context-mode": {"calls": 17, "conversations": 3}}}}
        before = copy.deepcopy(document)
        with patch.object(Path, "home", return_value=Path("/synthetic") / identity):
            html = view.roles(document)
        self.assertNotIn(identity, html)
        self.assertEqual(self.parse(html)[1][1][1:3], ["3", "17"])
        self.assertEqual(document, before)


if __name__ == "__main__":
    unittest.main()
