"""Checks for the 2026-09-27 token-stack card bundle (evidence/artifacts/token-stack-cards-20260927)."""

import contextlib
import copy
import getpass
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "evidence/artifacts/token-stack-cards-20260927"
READINGS = BUNDLE / "counter-readings.json"
README = BUNDLE / "README.md"
PRIVATE_INPUT_SECTION = "## Claims with retained readings and claims resting on private inputs"
# Card figures with no ledger reading behind them (rtk shortfall_cause); the README must list each one.
UNBACKED_FIGURES = ("39.2%", "16,493")


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"token_stack_cards_{name}", BUNDLE / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readme_section(heading):
    text = README.read_text(encoding="utf-8")
    start = text.find(heading + "\n")
    if start < 0:
        return None
    following = text.find("\n## ", start + len(heading))
    return text[start:following if following >= 0 else len(text)]


def snapshot_entries():
    """Every native_snapshot entry in the cards, keyed by its JSON pointer inside the bundle."""
    entries = {}
    for path in sorted((BUNDLE / "cards").glob("*.json")):
        if path.name == "index.json":
            continue
        card = json.loads(path.read_text(encoding="utf-8"))
        for index, entry in enumerate(card["adapted_performance"].get("native_snapshot") or []):
            entries[f"cards/{path.name}#/adapted_performance/native_snapshot/{index}"] = entry
    return entries


def basis_quotes(basis):
    """The reading fields a snapshot's basis text quotes after its ' | ' separators."""
    quoted = {}
    for part in basis.split(" | "):
        if part.startswith("kind: "):
            quoted["kind"] = part[len("kind: "):]
        elif part.startswith("session_estimated_saved="):
            quoted["session_estimated_saved"] = int(part.split("=", 1)[1])
    return quoted


def identical(entry, reading):
    metrics = reading["metrics"]
    return (reading["tool"] == entry["tool"] and reading["scope"] == entry["scope"]
            and reading["observed_at"] == entry["observed_utc"] and reading["success"] == 1
            and metrics["saved"] == entry["saved"]
            and basis_quotes(entry["basis"]) == {key: metrics[key] for key in ("kind", "session_estimated_saved")
                                                 if key in metrics})


def unmatched(entries, readings):
    """Pointers of snapshot entries without exactly one identical reading that names them."""
    return sorted(pointer for pointer, entry in entries.items()
                  if [reading["card_entry"] for reading in readings if identical(entry, reading)] != [pointer])


class CounterReadingTests(unittest.TestCase):
    """counter-readings.json backs every card native_snapshot figure with a sanitized ledger row."""

    def test_every_native_snapshot_entry_has_an_identical_ledger_reading(self):
        entries = snapshot_entries()
        readings = json.loads(READINGS.read_text(encoding="utf-8"))["readings"]
        self.assertEqual(len(entries), 5)
        self.assertEqual(unmatched(entries, readings), [])
        self.assertEqual(sorted(reading["card_entry"] for reading in readings), sorted(entries))

    def test_changing_one_reading_breaks_the_match(self):
        readings = json.loads(READINGS.read_text(encoding="utf-8"))["readings"]
        for field, change in (("saved", lambda reading: reading["metrics"].update(saved=reading["metrics"]["saved"] + 1)),
                              ("scope", lambda reading: reading.update(scope=reading["scope"] + " ")),
                              ("observed_at", lambda reading: reading.update(observed_at="2026-09-26T22:54:10+00:00"))):
            with self.subTest(field=field):
                changed = copy.deepcopy(readings)
                change(changed[0])
                self.assertEqual(unmatched(snapshot_entries(), changed), [changed[0]["card_entry"]])

    def test_readings_publish_only_the_sanitized_fields(self):
        document = json.loads(READINGS.read_text(encoding="utf-8"))
        for reading in document["readings"]:
            self.assertEqual(set(reading), {"ledger_snapshot_id", "tool", "scope", "observed_at", "success",
                                            "metrics", "card_entry"})
            self.assertIs(type(reading["ledger_snapshot_id"]), int)
            self.assertLessEqual(set(reading["metrics"]), {"saved", "kind", "session_estimated_saved"})
        text = READINGS.read_text(encoding="utf-8")
        for label, pattern in (("uuid", r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"),
                               ("e-mail", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
                               ("home path", r"/(?:home|Users)/[A-Za-z0-9_.-]+"),
                               ("home-relative path", r"(?<![\w$.~/-])~/"),
                               ("session temp path", r"/tmp/claude-"),
                               ("evidence column", r"\"evidence\"|\"raw\"|\"argv\"")):
            with self.subTest(pattern=label):
                self.assertIsNone(re.search(pattern, text, re.I))
        user = getpass.getuser()
        if len(user) > 2:
            self.assertIsNone(re.search(r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])", text))

    def test_readme_names_backed_and_private_input_figures(self):
        section = readme_section(PRIVATE_INPUT_SECTION)
        self.assertIsNotNone(section, "README needs the backed/private-input section")
        for reading in json.loads(READINGS.read_text(encoding="utf-8"))["readings"]:
            with self.subTest(reading=reading["ledger_snapshot_id"]):
                self.assertIn(f"{reading['metrics']['saved']:,}", section)
                self.assertRegex(section, rf"\| {reading['ledger_snapshot_id']} \|")
        for figure in UNBACKED_FIGURES:
            with self.subTest(figure=figure):
                self.assertIn(figure, section)
        # The unbacked figures rest on the private rtk.json input the Reproduce table identifies by sha256.
        rtk_input = re.search(r"^\| `rtk\.json` \| \d+ \| `([0-9a-f]{64})` \|$", README.read_text(encoding="utf-8"),
                              re.M)
        self.assertIsNotNone(rtk_input)
        self.assertIn(rtk_input.group(1), section)


class BundleInputNameTests(unittest.TestCase):
    """tools/bundle.py keys every input by the basename it was given."""

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def run_bundle(self, returned_name):
        bundle = load_tool("bundle")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.write(base / "cards/fixture-tool.json", {
                "tool": "fixture-tool", "e2e_returned_results": {"records_shown": [{"id": "fixture-01"}]},
                "gpt6_review": {"verdict": "aligned", "findings": [], "resolutions": [], "harness": {},
                                "final_verdict": {"verdict": "adapted", "summary": "Fixture card",
                                                  "claims_verified": []}}})
            self.write(base / "cards/index.json", [{"tool": "fixture-tool"}])
            invoke = self.write(base / "invoke.json", {"tools": {}})
            returned = self.write(base / returned_name, {
                "captured_at": "2026-09-26T22:53:19Z", "scope": "fixture",
                "records": [{"id": "fixture-01", "command": {"argv": ["echo", "fixture"]},
                             "observation": "fixture output", "status": "pass"}]})
            raw = returned.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                code = bundle.main(["--cards", str(base / "cards"), "--invoke", str(invoke),
                                    "--returned-results", str(returned), "--repo-root", str(ROOT),
                                    "--out", str(base / "out")])
            self.assertEqual(code, 0)
            subset = json.loads((base / "out/returned-results-subset.json").read_text(encoding="utf-8"))
        return subset["source"], raw

    def test_the_canonical_returned_results_name_is_recorded_unchanged(self):
        source, raw = self.run_bundle("returned-results.json")
        self.assertEqual(source, {"name": "returned-results.json", "captured_at": "2026-09-26T22:53:19Z",
                                  "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "records": 1})

    def test_a_renamed_returned_results_file_is_keyed_by_its_supplied_basename(self):
        source, raw = self.run_bundle("returned-results-renamed.json")
        self.assertEqual(source, {"name": "returned-results-renamed.json", "captured_at": "2026-09-26T22:53:19Z",
                                  "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "records": 1})


if __name__ == "__main__":
    unittest.main()
