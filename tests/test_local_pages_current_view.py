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


if __name__ == "__main__":
    unittest.main()
