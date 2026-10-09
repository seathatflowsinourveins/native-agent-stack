"""Privacy and actual source chronology in the command-center current view."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_HOME = "/".join(["", "home", "synthetic-user"])
SYNTHETIC_MAC_HOME = "/".join(["", "Users", "synthetic-user"])
SYNTHETIC_SESSION = "-".join(["01234567", "89ab", "cdef", "0123", "456789abcdef"])
SYNTHETIC_TASK = "-".join(["task", "abcd1234", "ef5678"])
SPEC = importlib.util.spec_from_file_location("local_current_view_tests", ROOT / "tools/local-pages/current_view.py")
current = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(current)


class CurrentViewTests(unittest.TestCase):
    def setUp(self):
        self.view = {"schema": "cc-now/1", "updated_utc": "2026-10-09T06:00:00Z", "timezone_for_display": "America/New_York", "headline": "Current " + SYNTHETIC_HOME + "/project " + SYNTHETIC_SESSION, "readiness": {"start_gates_met": 1, "start_gates_total": 2, "estimate_percent": 50, "basis": SYNTHETIC_TASK + " " + SYNTHETIC_MAC_HOME + "/review"}, "gates": [{"id": "G4a", "state": "MET", "what": "Read " + SYNTHETIC_HOME + "/receipt", "blocks_start": True}, {"id": "G4b", "state": "OPEN", "what": "Pending " + SYNTHETIC_TASK, "blocks_start": False}], "next_events": [{"utc": "2026-10-09T07:00:00Z", "what": "Inspect " + SYNTHETIC_HOME + "/event"}], "waiting_on_owner": [{"what": "Read https://chatgpt.com/c/private-item at " + SYNTHETIC_HOME + "/owner", "link": "https://chatgpt.com/c/private-item"}], "workstation": {"windows_available_gib": 10, "wsl_available_gib": 20, "swap_used_gib": 0, "read_utc": "2026-10-09T05:00:00Z", "codex_pool": SYNTHETIC_HOME + "/metadata"}}
        self.workstation = {key: {"value_gib": self.view["workstation"][key], "source": "source " + SYNTHETIC_HOME + "/telemetry", "read_utc": "2026-10-09T05:00:00Z"} for key in ("windows_available_gib", "wsl_available_gib", "swap_used_gib")}

    def test_every_current_view_text_uses_the_shared_portable_recipe(self):
        text = current.render(self.view, self.workstation)
        for private in [SYNTHETIC_HOME, SYNTHETIC_MAC_HOME, SYNTHETIC_SESSION, SYNTHETIC_TASK, "https://chatgpt.com/c/private-item"]:
            self.assertNotIn(private, text)
        self.assertIn("${USER_HOME}", text)
        self.assertIn("${LOCAL_SESSION_ID}", text)
        self.assertIn("${LOCAL_TASK_HANDLE}", text)

    def test_owner_account_artifact_links_remain_sanitized_text(self):
        for link in ["https://claude.ai/artifact/private-id", "https://chatgpt.com/c/private-id", "https://chat.openai.com/c/private-id", "https://%63hatgpt.com/c/private-id"]:
            with self.subTest(link=link):
                rendered = current.owner_link({"link": link, "what": "Inspect " + link})
                self.assertNotIn('<a href=', rendered)
                self.assertNotIn("private-id", rendered)

    def test_public_owner_link_is_sanitized_and_escaped(self):
        rendered = current.owner_link({"link": "https://example.org/source", "what": "Review <source> " + SYNTHETIC_HOME + "/item"})
        self.assertIn('href="https://example.org/source"', rendered)
        self.assertIn("&lt;source&gt;", rendered)
        self.assertNotIn(SYNTHETIC_HOME, rendered)
        for link in ["javascript:alert(1)", "https://user:password@example.org/private"]:
            self.assertNotIn('<a href=', current.owner_link({"link": link, "what": "Source"}))

    def test_unverified_or_unreported_native_state_never_counts_as_superseded(self):
        self.assertFalse(current.superseded("G4", "UNVERIFIED", self.view))
        for state in [None, "", "UNREPORTED", "not reported"]:
            with self.subTest(state=state):
                self.assertFalse(current.superseded("G4", state, self.view, source_utc="2026-10-08T05:00:00Z", source_status="RECORDED"))
        self.assertFalse(current.superseded("G4", "READY", self.view, source_utc="2026-10-08T05:00:00Z", source_status="UNVERIFIED"))

    def test_timestamp_order_and_offsets_determine_supersession(self):
        for date in ["2026-10-09T06:00:00Z", "2026-10-09T02:00:00-04:00", "2026-10-09T07:00:00Z", "not-a-time", "2026-10-08", None]:
            with self.subTest(date=date):
                self.assertFalse(current.superseded("G4", "READY", self.view, source_utc=date, source_status="RECORDED"))
        self.assertTrue(current.superseded("G4", "READY", self.view, source_utc="2026-10-09T01:59:59-04:00", source_status="RECORDED"))

    def test_split_gates_require_older_recorded_source_and_changed_state(self):
        self.assertTrue(current.superseded("G4", "MET", self.view, source_utc="2026-10-08T06:00:00Z", source_status="RECORDED"))
        self.assertFalse(current.superseded("G4a", "MET", self.view, source_utc="2026-10-08T06:00:00Z", source_status="RECORDED"))
        self.assertFalse(current.superseded("G5", "READY", self.view, source_utc="2026-10-08T06:00:00Z", source_status="RECORDED"))
        self.assertFalse(current.superseded("G4", "READY", self.view))

    def test_owner_link_changed_by_portable_projection_is_plain_text(self):
        for fragment in [SYNTHETIC_HOME + "/receipt", SYNTHETIC_SESSION, SYNTHETIC_TASK]:
            with self.subTest(fragment=fragment):
                link = "https://example.org/source/" + fragment
                html = current.owner_link({"link": link, "what": "Read " + link})
                self.assertNotIn('<a href=', html)
                self.assertNotIn(fragment, html)
        self.assertIn('<a href="https://example.org/source">', current.owner_link({"link": "https://example.org/source", "what": "Read source"}))

    def test_differs_and_superseded_share_one_bounded_split_gate_matcher(self):
        self.assertTrue(current.differs("G4", "READY", self.view))
        self.assertFalse(current.differs("G4a", "MET", self.view))
        self.assertFalse(current.differs("G4", "UNVERIFIED", self.view))
        self.assertFalse(current.differs("G4", "UNKNOWN", self.view))
        self.assertFalse(current.differs("G4", None, self.view))
        for extra in ["G4other", "G40", "G4abc", "G4a-extra"]:
            with self.subTest(extra=extra):
                view = {**self.view, "gates": [{"id": extra, "state": "MET"}]}
                self.assertFalse(current.differs("G4", "READY", view))
                self.assertFalse(current.superseded("G4", "READY", view, source_utc="2026-10-08T06:00:00Z"))

    def test_now_stamp_and_metric_reads_show_new_york_before_utc(self):
        html = current.render(self.view, self.workstation)
        stamp = html.split('class="current-stamp"', 1)[1].split('</p>', 1)[0]
        self.assertIn("02:00:00 EDT", stamp)
        self.assertLess(stamp.index("02:00:00 EDT"), stamp.index("06:00:00 UTC"))
        readings = html.split('class="reading-meta"', 1)[1]
        self.assertIn("01:00:00 EDT", readings)
        self.assertLess(readings.index("01:00:00 EDT"), readings.index("05:00:00 UTC"))
        self.assertIn('datetime="2026-10-09T05:00:00Z"', readings)

    def test_unknown_metric_read_time_stays_explicitly_unreported(self):
        self.workstation["windows_available_gib"]["read_utc"] = None
        html = current.render(self.view, self.workstation)
        first = html.split('class="reading-meta"', 1)[1].split('</small>', 1)[0]
        self.assertIn("not reported", first)
        self.assertNotIn('datetime="None"', first)
        self.assertNotIn(self.view["updated_utc"], first)
    def test_optional_memory_totals_require_finite_positive_numeric_bounds(self):
        for invalid in [None, False, "32", -1, 0, 9, float("nan"), float("inf")]:
            with self.subTest(invalid=invalid):
                self.view["workstation"]["windows_total_gib"] = invalid
                current.validate(self.view)
                self.workstation["windows_total_gib"] = {"value_gib": invalid, "source": "fixture total", "read_utc": "2026-10-09T05:00:00Z"}
                text = current.render(self.view, self.workstation)
                self.assertIn("total unknown", text)
                self.assertNotIn('class="memory-total"', text)
                self.assertIn("Windows available", text)
        self.view["workstation"]["windows_total_gib"] = 32
        current.validate(self.view)

    def test_metric_render_rejects_wrong_total_type_and_timezone_naive_metadata(self):
        self.workstation["windows_total_gib"] = {"value_gib": "32", "source": "fixture total", "read_utc": "2026-10-09T05:00:00Z"}
        self.assertIn("total unknown", current.render(self.view, self.workstation))
        self.workstation["windows_total_gib"]["value_gib"] = 32
        self.workstation["windows_total_gib"]["read_utc"] = "2026-10-09T05:00:00"
        self.assertIn("total unknown", current.render(self.view, self.workstation))
        self.workstation["windows_total_gib"]["read_utc"] = "2026-10-09T04:00:00Z"
        rendered = current.render(self.view, self.workstation)
        self.assertIn("32.0 GiB total", rendered)
        self.assertIn('datetime="2026-10-09T04:00:00Z"', rendered)
        self.assertNotIn("total unknown", rendered)

    def test_tiny_positive_swap_never_rounds_to_zero(self):
        self.workstation["swap_used_gib"]["value_gib"] = 1 / 1024 ** 3
        html = current.render(self.view, self.workstation)
        self.assertIn("<strong>1</strong> byte", html)
        self.assertNotIn("<strong>0.0</strong> MiB", html)


if __name__ == "__main__":
    unittest.main()
