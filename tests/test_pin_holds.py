"""Dated holds in the platform pins files (docs/decisions/2026-10-04-codex-dated-holds.md).

A pins entry's holds[] names an older version that hosts not yet switched keep until a date, with a reason and that
version's install data. scripts/adoption_status.py --pinned-versions reports a probe that names it as held before the
date and as drift from that date on. These checks keep every checked-in hold complete and unexpired, the way
tests/test_osv_lockfile_coverage.py keeps every OSV-Scanner ignore (an id, a reason and an ignoreUntil at most 90 days
away; an ignoreUntil on or before today has expired). A hold left past its date fails here, so it is renewed with a
new date and reason or deleted. An entry carries at most one hold: a second concurrent hold is the decision record's
condition to revisit per-host pin rows. Dates compare with the status report's own clock, today's UTC date.

Structural validation only: these read the repository files. Nothing here downloads, installs or runs a hold.
"""

from datetime import date, timedelta
import copy
import json
from pathlib import Path
import re
import unittest

from scripts import adoption_status

ROOT = Path(__file__).resolve().parents[1]
PINS_FILES = sorted((ROOT / "adoption").glob("pins-*.json"))
RECORD = "docs/decisions/2026-10-04-codex-dated-holds.md"
REQUIRED_KEYS = ("version", "until", "reason", "url", "sha256")
HOLD_KEYS = {*REQUIRED_KEYS, "checksum_ref", "platform_dependency"}
HORIZON_DAYS = 90  # as an OSV-Scanner ignoreUntil (.github/osv-scanner.toml)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
INTEGRITY = re.compile(r"sha512-[A-Za-z0-9+/]{86}==\Z")


def platform_dependency_problems(name: str, hold: dict, entry: dict) -> list[str]:
    """A hold of an entry that installs a platform package carries that package for the held version, in the shape
    of the entry's own platform_dependency (adoption/bootstrap-linux.sh reads those keys)."""
    pinned, held = entry.get("platform_dependency"), hold.get("platform_dependency")
    if pinned is None and held is None:
        return []
    if not isinstance(pinned, dict) or not isinstance(held, dict):
        return [f"{name}: platform_dependency must be present on both the entry and the hold, or on neither"]
    problems = []
    if set(held) != set(pinned):
        problems.append(f"{name}: platform_dependency keys {sorted(held)} differ from the entry's {sorted(pinned)}")
    for key in ("name", "resolved_package"):
        if held.get(key) != pinned.get(key):
            problems.append(f"{name}: platform_dependency {key} differs from the entry's")
    if not str(held.get("version", "")).startswith(f"{hold.get('version')}-"):
        problems.append(f"{name}: platform_dependency version is not the held version's platform package")
    if not str(held.get("url", "")).startswith("https://"):
        problems.append(f"{name}: platform_dependency url is not https")
    if SHA256.fullmatch(str(held.get("sha256", ""))) is None:
        problems.append(f"{name}: platform_dependency sha256 is not 64 lowercase hex digits")
    if "integrity" in pinned and INTEGRITY.fullmatch(str(held.get("integrity", ""))) is None:
        problems.append(f"{name}: platform_dependency integrity is not an npm sha512 value")
    check, pinned_check = held.get("installed_binary_check"), pinned.get("installed_binary_check")
    if isinstance(pinned_check, dict):
        if not isinstance(check, dict) or set(check) != set(pinned_check) or check.get("path") != pinned_check.get("path"):
            problems.append(f"{name}: installed_binary_check differs in shape or path from the entry's")
        elif SHA256.fullmatch(str(check.get("sha256", ""))) is None:
            problems.append(f"{name}: installed_binary_check sha256 is not 64 lowercase hex digits")
    return problems


def hold_problems(pins: dict, today: date) -> list[str]:
    """Every way a pins file's holds break the policy above, as text; [] when they keep it."""
    problems, latest = [], today + timedelta(days=HORIZON_DAYS)
    tools = pins.get("tools") if isinstance(pins, dict) else None
    for entry in tools if isinstance(tools, list) else []:
        if not isinstance(entry, dict) or "holds" not in entry:
            continue
        label, holds = entry.get("id"), entry["holds"]
        if not isinstance(holds, list) or not holds:
            problems.append(f"{label}: holds must be a non-empty list (delete the key when no hold remains)")
            continue
        if len(holds) > 1:
            problems.append(f"{label}: {len(holds)} holds; a second concurrent hold means revisiting per-host pin rows "
                            f"({RECORD})")
        usable = adoption_status.pin_holds(entry)
        for hold in holds:
            if not isinstance(hold, dict):
                problems.append(f"{label}: a hold that is not an object")
                continue
            name = f"{label} hold {hold.get('version')!r}"
            for key in sorted(set(hold) - HOLD_KEYS):
                problems.append(f"{name}: unknown key {key!r}")
            for key in REQUIRED_KEYS:
                if not isinstance(hold.get(key), str) or not hold[key].strip():
                    problems.append(f"{name}: no {key}")
            if hold.get("version") == entry.get("version"):
                problems.append(f"{name}: holds the pinned version itself")
            if not str(hold.get("url", "")).startswith("https://"):
                problems.append(f"{name}: url is not https")
            if SHA256.fullmatch(str(hold.get("sha256", ""))) is None:
                problems.append(f"{name}: sha256 is not 64 lowercase hex digits")
            problems += platform_dependency_problems(name, hold, entry)
            until = hold.get("until")
            try:
                until_date = date.fromisoformat(until) if adoption_status.HOLD_DATE.fullmatch(str(until)) else None
            except ValueError:
                until_date = None
            if until_date is None:
                problems.append(f"{name}: until must be a YYYY-MM-DD date")
                continue
            if until_date <= today:
                problems.append(f"{name}: until {until} has passed; renew the hold with a new date and reason, or "
                                "delete it")
            if until_date > latest:
                problems.append(f"{name}: until more than {HORIZON_DAYS} days away")
            if hold not in usable:
                problems.append(f"{name}: scripts/adoption_status.py cannot use this hold")
    return problems


class LiveHoldTests(unittest.TestCase):
    def test_the_pins_files_are_found(self):
        self.assertIn(ROOT / "adoption/pins-linux-x86_64.json", PINS_FILES)

    def test_every_hold_is_complete_and_unexpired(self):
        today = adoption_status.utc_today()
        for path in PINS_FILES:
            with self.subTest(pins=path.name):
                self.assertEqual(hold_problems(json.loads(path.read_text(encoding="utf-8")), today), [])


class HoldPolicyMutantTests(unittest.TestCase):
    """The check above catches each way a hold can break the policy (synthetic entries, dated from a fixed today)."""

    TODAY = date(2026, 10, 4)

    def entry(self) -> dict:
        return {"id": "tool", "version": "2.0.0", "kind": "npm",
                "url": "https://registry.npmjs.org/tool/-/tool-2.0.0.tgz", "sha256": "a" * 64,
                "platform_dependency": {"name": "tool-linux-x64", "resolved_package": "tool", "version": "2.0.0-linux-x64",
                                        "url": "https://registry.npmjs.org/tool/-/tool-2.0.0-linux-x64.tgz",
                                        "sha256": "b" * 64, "integrity": "sha512-" + "A" * 86 + "==",
                                        "checksum_ref": "registry metadata",
                                        "installed_binary_check": {"path": "vendor/bin/tool", "sha256": "c" * 64}},
                "holds": [{"version": "1.9.0", "until": "2026-11-04", "reason": "hosts not yet switched",
                           "url": "https://registry.npmjs.org/tool/-/tool-1.9.0.tgz", "sha256": "d" * 64,
                           "checksum_ref": "history",
                           "platform_dependency": {
                               "name": "tool-linux-x64", "resolved_package": "tool", "version": "1.9.0-linux-x64",
                               "url": "https://registry.npmjs.org/tool/-/tool-1.9.0-linux-x64.tgz",
                               "sha256": "e" * 64, "integrity": "sha512-" + "B" * 86 + "==",
                               "checksum_ref": "registry metadata",
                               "installed_binary_check": {"path": "vendor/bin/tool", "sha256": "f" * 64}}}]}

    def problems(self, entry: dict) -> list[str]:
        return hold_problems({"tools": [entry]}, self.TODAY)

    def mutated(self, change) -> dict:
        entry = copy.deepcopy(self.entry())
        change(entry, entry["holds"][0])
        return entry

    def test_a_complete_hold_and_an_entry_without_holds_pass(self):
        self.assertEqual(self.problems(self.entry()), [])
        bare = self.entry()
        del bare["holds"]
        self.assertEqual(self.problems(bare), [])
        no_platform = self.entry()
        del no_platform["platform_dependency"], no_platform["holds"][0]["platform_dependency"]
        self.assertEqual(self.problems(no_platform), [])

    def test_the_until_date_follows_the_ignore_until_rule(self):
        for until, passes in (("2026-10-05", True), ("2027-01-02", True), ("2026-10-04", False),
                              ("2026-09-30", False), ("2027-01-03", False)):
            with self.subTest(until=until):
                entry = self.mutated(lambda _entry, hold: hold.update(until=until))
                self.assertEqual(self.problems(entry) == [], passes, self.problems(entry))

    def test_each_broken_hold_is_caught(self):
        def drop(key):
            return lambda _entry, hold: hold.pop(key)
        mutations = {
            **{f"no {key}": drop(key) for key in REQUIRED_KEYS},
            "blank reason": lambda _entry, hold: hold.update(reason="  "),
            "until not a date": lambda _entry, hold: hold.update(until="2026-11-31"),
            "until with a time": lambda _entry, hold: hold.update(until="2026-11-04T00:00:00Z"),
            "until a number": lambda _entry, hold: hold.update(until=20261104),
            "unknown key": lambda _entry, hold: hold.update(hosts=["a host"]),
            "the pin itself": lambda _entry, hold: hold.update(version="2.0.0"),
            "http url": lambda _entry, hold: hold.update(url="http://registry.npmjs.org/tool/-/tool-1.9.0.tgz"),
            "short sha256": lambda _entry, hold: hold.update(sha256="d" * 63),
            "uppercase sha256": lambda _entry, hold: hold.update(sha256="D" * 64),
            "second hold": lambda entry, hold: entry["holds"].append({**copy.deepcopy(hold), "version": "1.8.0"}),
            "empty holds": lambda entry, _hold: entry.update(holds=[]),
            "holds not a list": lambda entry, hold: entry.update(holds=hold),
            "hold not an object": lambda entry, _hold: entry.update(holds=["1.9.0"]),
            "no platform dependency": lambda _entry, hold: hold.pop("platform_dependency"),
            "platform dependency of another version":
                lambda _entry, hold: hold["platform_dependency"].update(version="2.0.0-linux-x64"),
            "platform dependency of another package":
                lambda _entry, hold: hold["platform_dependency"].update(name="other-linux-x64"),
            "platform dependency missing a key": lambda _entry, hold: hold["platform_dependency"].pop("checksum_ref"),
            "platform dependency bad integrity":
                lambda _entry, hold: hold["platform_dependency"].update(integrity="sha256-x"),
            "platform dependency bad sha256": lambda _entry, hold: hold["platform_dependency"].update(sha256="e"),
            "binary check of another path":
                lambda _entry, hold: hold["platform_dependency"]["installed_binary_check"].update(path="bin/tool"),
            "binary check bad sha256":
                lambda _entry, hold: hold["platform_dependency"]["installed_binary_check"].update(sha256="f"),
        }
        for label, change in mutations.items():
            with self.subTest(mutation=label):
                self.assertNotEqual(self.problems(self.mutated(change)), [], label)

    def test_a_second_hold_names_the_decision_record(self):
        entry = self.mutated(lambda entry, hold: entry["holds"].append({**copy.deepcopy(hold), "version": "1.8.0"}))
        self.assertTrue(any(RECORD in problem for problem in self.problems(entry)))


if __name__ == "__main__":
    unittest.main()
