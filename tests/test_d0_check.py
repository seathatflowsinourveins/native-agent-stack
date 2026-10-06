"""Integration fixtures for CLOCK-R2; no Windows or clock writes, no census."""

import contextlib
import copy
import ctypes
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("d0_check", ROOT / "scripts/d0_check.py")
d0 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d0)


def target_snapshot():
    # Synthetic target, preserving the two observed START trigger shapes.
    return {
        "schema_version": 1, "start_type": 2, "delayed_auto_start": 0,
        "service_state": "Running", "sc_qc": "START_TYPE : 2 AUTO_START",
        "sc_query": "STATE : 4 RUNNING", "sc_triggers": "START SERVICE\nSTART SERVICE",
        "triggers": [{"key": "0", "action": 1, "type": 3},
                     {"key": "1", "action": 1, "type": 7}],
        "synchronize_time": {"state": "Ready", "enabled": True},
        "resolve_peer_backoff_minutes": 1, "resolve_peer_backoff_max_times": 7,
        "max_times_value_present": True,
    }


class PersistenceTests(unittest.TestCase):
    def test_current_delayed_configuration_is_red_without_removing_start_triggers(self):
        snapshot = target_snapshot()
        snapshot.update(delayed_auto_start=1, sc_qc="START_TYPE : 2 AUTO_START (DELAYED)",
                        resolve_peer_backoff_minutes=15)
        result = d0.windows_persistence(snapshot)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"], ["delayed_start_or_unreadable_delay",
                                               "resolve_peer_backoff_minutes_not_1"])
        self.assertEqual(result["start_triggers"], snapshot["triggers"])

    def test_target_passes_with_unidentified_type_7_start_trigger_intact(self):
        snapshot = target_snapshot()
        before = copy.deepcopy(snapshot)
        result = d0.windows_persistence(snapshot)
        self.assertTrue(result["passed"])
        self.assertEqual(result["start_triggers"], snapshot["triggers"])
        self.assertEqual(snapshot, before)

    def test_stop_trigger_is_red_even_when_service_is_currently_running(self):
        snapshot = target_snapshot()
        snapshot["triggers"].append({"key": "2", "action": 2, "type": 3})
        self.assertIn("stop_trigger_present", d0.windows_persistence(snapshot)["failures"])

    def test_scm_stop_trigger_and_delayed_marker_cannot_hide_behind_registry_read(self):
        snapshot = target_snapshot()
        snapshot.update(sc_triggers="STOP SERVICE", sc_qc="START_TYPE : 2 AUTO_START (DELAYED)")
        result = d0.windows_persistence(snapshot)
        self.assertIn("stop_trigger_present", result["failures"])
        self.assertIn("delayed_start_or_unreadable_delay", result["failures"])

    def test_every_non_automatic_start_type_fails(self):
        for value in (None, 0, 1, 3, 4, "2", True):
            with self.subTest(value=value):
                snapshot = target_snapshot()
                snapshot["start_type"] = value
                self.assertIn("start_type_not_automatic_2", d0.windows_persistence(snapshot)["failures"])

    def test_stopped_or_unknown_service_fails(self):
        for value in (None, "Stopped", "StartPending", "Unknown"):
            with self.subTest(value=value):
                snapshot = target_snapshot()
                snapshot["service_state"] = value
                self.assertIn("w32time_not_running", d0.windows_persistence(snapshot)["failures"])

    def test_task_disabled_is_recorded_without_inventing_an_enabled_requirement(self):
        snapshot = target_snapshot()
        snapshot["synchronize_time"] = {"state": "Disabled", "enabled": False}
        result = d0.windows_persistence(snapshot)
        self.assertTrue(result["passed"])
        self.assertEqual(result["synchronize_time"], snapshot["synchronize_time"])

    def test_missing_readback_is_failure(self):
        for name in ("triggers", "synchronize_time", "sc_qc", "sc_query", "sc_triggers"):
            with self.subTest(name=name):
                snapshot = target_snapshot()
                snapshot.pop(name)
                self.assertFalse(d0.windows_persistence(snapshot)["passed"])
        self.assertFalse(d0.windows_persistence(None)["passed"])

    def test_unknown_trigger_action_is_not_assumed_to_be_a_start_trigger(self):
        for action in (None, "1", 0, 7, True):
            with self.subTest(action=action):
                snapshot = target_snapshot()
                snapshot["triggers"] = [{"action": action, "type": 7}]
                self.assertFalse(d0.windows_persistence(snapshot)["passed"])

    def test_max_times_zero_and_malformed_backoff_values_fail(self):
        for field, bad in (("resolve_peer_backoff_minutes", 15),
                           ("resolve_peer_backoff_minutes", True),
                           ("resolve_peer_backoff_max_times", 0),
                           ("resolve_peer_backoff_max_times", "7")):
            with self.subTest(field=field, bad=bad):
                snapshot = target_snapshot()
                snapshot[field] = bad
                self.assertFalse(d0.windows_persistence(snapshot)["passed"])

    def test_documented_absent_max_times_default_is_recorded(self):
        snapshot = target_snapshot()
        snapshot["max_times_value_present"] = False
        self.assertTrue(d0.windows_persistence(snapshot)["passed"])


class NativeBoundaryTests(unittest.TestCase):
    def test_timex_boundary_uses_only_the_read_mask(self):
        def query(pointer):
            value = ctypes.cast(pointer, ctypes.POINTER(d0.Timex)).contents
            self.assertEqual(value.modes, 0)
            value.maxerror = 2500
            value.freq = 123
            value.status = 0x2000
            value.tick = 10000
            return 0

        library = mock.Mock()
        library.adjtimex.side_effect = query
        with mock.patch.object(d0, "timex_libc", return_value=library):
            self.assertEqual(d0.sample_timex(), {"maxerror": 2500, "freq": 123,
                                                "status": 0x2000, "tick": 10000})

    def invoke_main(self, snapshot, mode="both"):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(d0, "read_windows", return_value=snapshot), \
                mock.patch.object(d0.subprocess, "check_output", return_value="2026-10-06T00:00:00Z\n"), \
                mock.patch.object(d0, "agent_census", return_value={"agent_alive": True}) as census:
            code = d0.main(60, mode)
        return code, json.loads(output.getvalue()), census

    def test_persistence_failure_alerts_immediately_without_running_census(self):
        snapshot = target_snapshot()
        snapshot["delayed_auto_start"] = 1
        code, result, census = self.invoke_main(snapshot)
        self.assertEqual(code, 1)
        self.assertIsNone(result["agent_alive"])
        census.assert_not_called()
        self.assertIn("administrator", result["remediation"])

    def test_persistence_only_does_not_claim_agent_acceptance(self):
        code, result, census = self.invoke_main(target_snapshot(), "persistence-only")
        self.assertEqual(code, 0)
        self.assertIsNone(result["agent_alive"])
        census.assert_not_called()

    def test_both_checks_and_original_agent_only_mode_remain_distinct(self):
        code, result, census = self.invoke_main(target_snapshot())
        self.assertEqual(code, 0)
        self.assertTrue(result["agent_alive"])
        census.assert_called_once_with(60)
        code, result, census = self.invoke_main(None, "agent-only")
        self.assertEqual(code, 0)
        self.assertIsNone(result["windows_persistence"])

    def test_native_query_error_fails_closed_without_sampling(self):
        for error in (OSError("missing reader"), ValueError("malformed JSON"),
                      RuntimeError("native exit"), subprocess.TimeoutExpired("reader", 30)):
            with self.subTest(error=type(error).__name__), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(d0, "read_windows", side_effect=error), \
                    mock.patch.object(d0.subprocess, "check_output", return_value="2026-10-06T00:00:00Z"), \
                    mock.patch.object(d0, "agent_census") as census:
                self.assertEqual(d0.main(), 1)
                census.assert_not_called()


if __name__ == "__main__":
    unittest.main()
