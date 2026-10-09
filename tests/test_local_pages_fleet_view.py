"""Unknown fleet sections, count meaning, and standalone public label safety."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fleet_view_tests", ROOT / "tools/local-pages/fleet_view.py")
view = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(view)


def fixture():
    return {"fleet_source": "fixture producer", "at": "2026-10-09T08:00:00Z", "lanes_live": [{"lane": "lane-a", "status": "active", "tier": "standard", "cli_version": "0.162.0", "subagents_running": 0}], "lanes_parked": [], "claude_sessions": [], "tiers": {"default": "standard", "fast": [], "versions": {"default": "0.162.0"}}, "claude_subagents_running": {}, "exec_reads_in_flight": [], "pool_accounts": [], "fresh_total_pct": 32, "sdk": {}, "actions": {}}


class FleetViewTests(unittest.TestCase):
    def test_unknown_fast_map_preserves_running_tier_without_default_inference(self):
        data = fixture()
        data["tiers"]["fast"] = None
        html = view.render(data)
        self.assertIn("standard / UNKNOWN", html)

    def test_missing_and_null_roster_sections_render_unknown_not_zero(self):
        for null in [False, True]:
            with self.subTest(null=null):
                data = fixture()
                for key in ["lanes_live", "lanes_parked", "claude_sessions"]:
                    if null:
                        data[key] = None
                    else:
                        del data[key]
                html = view.render(data)
                self.assertIn("UNKNOWN</strong> live Codex lanes", html)
                self.assertIn("UNKNOWN</strong> parked", html)
                self.assertIn("UNKNOWN</strong> Claude worker sessions", html)

    def test_actual_zero_subagents_and_known_empty_roster_remain_zero(self):
        html = view.render(fixture())
        self.assertIn("<td>0</td>", html)
        self.assertIn("0</strong> parked", html)
        self.assertIn("0</strong> Claude worker sessions", html)

    def test_exec_read_records_show_named_tier(self):
        data = fixture()
        data["exec_reads_in_flight"] = [{"name": "lane-a-review", "tier": "fast"}]
        html = view.render(data)
        self.assertIn("lane-a-review", html)
        self.assertIn("fast", html)
        self.assertNotIn("&#x27;name&#x27;", html)

    def test_pool_sum_uses_per_account_reference_wording(self):
        html = view.render(fixture())
        self.assertIn("sum of per-account fresh-pool percentages (reference 200)", html)
        self.assertNotIn("fresh pool used", html)

    def test_bare_host_identifier_and_home_path_are_sanitized_standalone(self):
        identity = "-".join(["dummy", "synthetic", "user"])
        private_path = "/".join(["", "home", identity, "fixture"])
        data = fixture()
        data["lanes_live"][0]["lane"] = identity
        data["fleet_source"] = "file:" + private_path
        data["sdk"]["source"] = "file:" + private_path
        data["pool_accounts"] = [{"account": identity, "used_pct": 2}]
        with patch.object(Path, "home", return_value=Path("/synthetic") / identity):
            html = view.render(data)
        self.assertNotIn(identity, html)
        self.assertNotIn(private_path, html)
        self.assertIn("2% used", html)

    def test_missing_subagent_count_is_unknown_while_actual_zero_is_kept(self):
        data = fixture()
        data["lanes_live"][0]["subagents_running"] = None
        html = view.render(data)
        self.assertIn("<td>UNKNOWN</td>", html)
        data["lanes_live"][0]["subagents_running"] = 0
        self.assertIn("<td>0</td>", view.render(data))

    def test_unknown_pool_and_sessions_differ_from_recorded_empty_lists(self):
        data = fixture()
        data.update(pool_accounts=None, claude_sessions=[])
        data["availability"] = {"claude_sessions": {"status": "UNKNOWN", "reason": "not measured"}}
        unknown = view.render(data)
        self.assertIn("UNKNOWN</strong> Claude worker sessions", unknown)
        self.assertIn('<ul class="claude-sessions"><li>UNKNOWN</li>', unknown)
        self.assertIn('<section class="fleet-pool"><h2>Pool accounts</h2><p>UNKNOWN</p>', unknown)
        data["claude_sessions"] = [{"name": "native-agent-stack-1a", "status": "active"}]
        self.assertNotIn("+ 1 owner session", view.render(data))
        data["claude_sessions"] = []
        data.update(pool_accounts=[], availability={})
        empty = view.render(data)
        self.assertIn("0</strong> Claude worker sessions", empty)
        self.assertIn("No recorded pool accounts", empty)

    def test_legacy_empty_rosters_need_a_known_source_before_showing_zero(self):
        for source in [None, "", "not reported"]:
            with self.subTest(source=source):
                data = fixture()
                data.update(fleet_source=source, at=None, lanes_live=[], lanes_parked=[], claude_sessions=[])
                html = view.render(data)
                self.assertIn("UNKNOWN</strong> live Codex lanes", html)
                self.assertIn("UNKNOWN</strong> parked", html)
                self.assertIn("UNKNOWN</strong> Claude worker sessions", html)
                self.assertNotIn("<strong>0</strong> live Codex lanes", html)
                data["availability"] = {"claude_sessions": {"status": "reported", "source": "cc-now"}}
                self.assertIn("0</strong> Claude worker sessions", view.render(data))

    def test_partial_snapshot_lists_keep_source_availability_visible(self):
        data = fixture()
        data["availability"] = {"lanes_live": {"status": "snapshot fallback", "source": "snapshot", "read_utc": "2026-10-09T07:00:00Z", "reason": "direct section unavailable"}}
        html = view.render(data)
        self.assertIn("snapshot fallback", html)
        self.assertIn("2026-10-09T07:00:00Z", html)


if __name__ == "__main__":
    unittest.main()
