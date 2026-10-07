"""Local Option C configuration contracts, not live notification acceptance.

Native format: prometheus/alertmanager@73c6bfe7393929211294c1954f30d8ed78e4d0ad,
docs/configuration.md: route, telegram_config and inhibit_rule.
Unit events are recorded without integrations; only the unit state route notifies.
Short failures that clear before state firing have no promised recovery notice:
notify/dedup_stage.go:52-60 at the same pin.
"""
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVENT_NAMES = {"PaperLaneUnitFailed", "StackUnitFailed"}
STATE_NAMES = {"PaperLaneUnitDown", "StackUnitDown"}


class UserUnitAlertNotifierConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (ROOT / "observability/alert-lifecycle/alertmanager-events.example.json").read_text()
        )

    def route(self, receiver):
        routes = [row for row in self.config["route"]["routes"]
                  if row["receiver"] == receiver]
        self.assertEqual(len(routes), 1)
        return routes[0]

    def assert_names_match(self, matchers, expected_names):
        self.assertEqual(len(matchers), 1)
        matcher = re.fullmatch(r'alertname=~"(.*)"', matchers[0])
        self.assertIsNotNone(matcher)
        pattern = matcher.group(1)
        for name in EVENT_NAMES | STATE_NAMES | {"DaguDagFailed", "Watchdog", "OtherFailed", "OtherDown"}:
            with self.subTest(alertname=name, matchers=matchers):
                self.assertEqual(re.fullmatch(pattern, name) is not None,
                                 name in expected_names)
        for name in expected_names:
            with self.subTest(unrelated_suffix=name):
                self.assertIsNone(re.fullmatch(pattern, name + "Extra"))

    def test_event_and_state_routes_are_separate_closed_families(self):
        self.assertEqual(len(self.config["route"]["routes"]), 3)
        event = self.route("unit-event-record-only")
        state = self.route("telegram-state")
        self.assert_names_match(event["matchers"], EVENT_NAMES)
        self.assert_names_match(state["matchers"], STATE_NAMES)
        self.assertEqual(event["group_wait"], "0s")
        self.assertFalse(event.get("continue", False))
        self.assertFalse(state.get("continue", False))

    def test_unit_event_receiver_has_only_a_name_and_no_integrations(self):
        receivers = [row for row in self.config["receivers"]
                     if row["name"] == "unit-event-record-only"]
        self.assertEqual(receivers, [{"name": "unit-event-record-only"}])

    def test_dagu_keeps_its_separate_event_route(self):
        route = self.route("telegram-event")
        self.assertEqual(route["matchers"], ['alertname="DaguDagFailed"'])
        self.assertEqual(route["group_wait"], "0s")
        self.assertFalse(route.get("continue", False))

    def test_state_resolution_and_dagu_no_resolution_are_preserved(self):
        receivers = {row["name"]: row for row in self.config["receivers"]}
        self.assertEqual(len(receivers), len(self.config["receivers"]))
        self.assertEqual(set(receivers), {
            "unit-event-record-only", "telegram-event", "telegram-state",
        })
        for name, resolved in (("telegram-event", False), ("telegram-state", True)):
            configs = receivers[name]["telegram_configs"]
            self.assertEqual(len(configs), 1)
            self.assertIs(configs[0]["send_resolved"], resolved)
        self.assertEqual(self.config["route"]["receiver"], "telegram-state")

    def test_no_inhibition_can_suppress_state_delivery(self):
        self.assertNotIn("inhibit_rules", self.config)

    def test_incident_grouping_retains_family_host_and_unit(self):
        self.assertEqual(self.config["route"]["group_by"], ["alertname", "host", "unit"])
        for route in self.config["route"]["routes"]:
            self.assertNotIn("group_by", route)

    def test_receivers_contain_only_private_file_references(self):
        for receiver in self.config["receivers"]:
            for telegram in receiver.get("telegram_configs", []):
                self.assertEqual(set(telegram), {
                    "bot_token_file", "chat_id_file", "send_resolved", "parse_mode",
                })
                self.assertEqual(telegram["bot_token_file"], "private/telegram-bot-token")
                self.assertEqual(telegram["chat_id_file"], "private/telegram-chat-id")
                self.assertEqual(telegram["parse_mode"], "HTML")

    def test_disabled_deadman_is_not_in_active_example(self):
        self.assertEqual(set(self.config), {"route", "receivers"})
        serialized = json.dumps(self.config)
        self.assertNotIn("Watchdog", serialized)
        self.assertNotIn("external-deadman", serialized)


if __name__ == "__main__":
    unittest.main()
