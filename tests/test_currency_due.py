"""scripts/currency_due.py against fake checks in a temporary checkout (synthetic fixtures, not host evidence).

Each fake check is a small script that prints canned JSON in the shape the real script prints (receipt_staleness.py
assess(), adoption_status.py inspect_adoption(), saturation_ledger.py build_report() and runtime_skill_freshness.py
build_report()) and records the arguments it received. ThisCheckoutTests runs this checkout's real checks with
--dry-run into a temporary state directory. None of the fixtures is a recorded observation.
"""

from __future__ import annotations

import contextlib
import io
import json
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import currency_due as cd

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_DIR = ROOT / "adoption/templates/systemd"
NOW = "2026-09-30T12:00:00Z"
COMMAND = "python3 scripts/currency_due.py --dry-run"

STALENESS = "scripts/receipt_staleness.py"
PINNED = "scripts/adoption_status.py"
SATURATION = "scripts/saturation_ledger.py"
SKILLS = "tools/adoption/runtime_skill_freshness.py"

# A fake check. It records its arguments beside itself, copies a --staleness input it was given (so a test can
# see what reached saturation_ledger.py), writes spec["output_file"] to the path after --output (where
# runtime_skill_freshness.py writes its report), prints spec["stdout"] and exits spec["code"].
FAKE_CHECK = """\
import json, pathlib, sys
here = pathlib.Path(__file__)
spec = json.loads(here.with_name(here.name + ".spec.json").read_text(encoding="utf-8"))
argv = sys.argv[1:]
here.with_name(here.name + ".argv.json").write_text(json.dumps(argv), encoding="utf-8")
if "--staleness" in argv:
    received = pathlib.Path(argv[argv.index("--staleness") + 1]).read_text(encoding="utf-8")
    here.with_name(here.name + ".staleness.json").write_text(received, encoding="utf-8")
if "output_file" in spec:
    pathlib.Path(argv[argv.index("--output") + 1]).write_text(spec["output_file"], encoding="utf-8")
sys.stdout.write(spec.get("stdout", ""))
sys.exit(spec.get("code", 0))
"""


def staleness_report(*flagged):
    """receipt_staleness.py --json (assess(), receipt_staleness.py:156-164); ``flagged`` is (component, flags) pairs.
    One unflagged row is always present."""
    rows = [{"platform_id": "linux-wsl2-x86_64", "component_id": component, "current_pins": ["1.0.0"],
             "pin_source": "landscape_winner", "alias_of": [], "grandfathered": False, "receipts": 1,
             "bound_receipts": 0, "latest_bound": None, "pin_moved_hosts": ["synthetic-host/use"], "unbound": [],
             "flags": list(flags), "info": []} for component, flags in flagged]
    rows.append({"platform_id": "linux-wsl2-x86_64", "component_id": "widget", "current_pins": ["1.0.0"],
                 "pin_source": "stack_manifest", "alias_of": [], "grandfathered": False, "receipts": 1,
                 "bound_receipts": 1, "latest_bound": {"path": "evidence/hosts/synthetic.json",
                                                       "observed_at_utc": NOW, "age_days": 0, "result": "pass",
                                                       "stage": "use", "component_version": "1.0.0"},
                 "pin_moved_hosts": [], "unbound": [], "flags": [], "info": []})
    flags = ("stale", "pin_moved", "no_bound_receipt", "no_current_pin", "stack_alias")
    flagged_rows = sum(1 for row in rows if row["flags"])
    return {"generated_at_utc": NOW, "max_age_days": 30, "rows": rows,
            "flag_counts": {flag: sum(1 for row in rows if flag in row["flags"]) for flag in flags},
            "info_counts": {"stack_alias_grandfathered": 0}, "flagged": flagged_rows,
            "status": "flagged" if flagged_rows else "current"}


def pinned_report(mismatched=(), matched=("rtk",), unchecked=("context-mode",), profiles=("foundation-cpu",),
                  status="prerequisites_present"):
    """adoption_status.py --pinned-versions --json (inspect_adoption(), adoption_status.py:1282-1344)."""
    def profile(identifier):
        results = ([{"id": item, "pinned_version": "1.0.0", "checked": True, "matches_pin": True} for item in matched]
                   + [{"id": item, "pinned_version": "2.0.0", "checked": True, "matches_pin": False}
                      for item in mismatched]
                   + [{"id": item, "pinned_version": None, "checked": False, "matches_pin": None}
                      for item in unchecked])
        return {"id": identifier, "commands": [], "recipes": [], "status": status, "pinned_versions": results,
                "pinned_versions_summary": {"matched": list(matched), "mismatched": list(mismatched),
                                            "unchecked": list(unchecked)}}
    return {"schema_version": 1, "status": status,
            "platform": {"os": "linux", "architecture": "x86_64", "python": "3.13.0", "supported": True},
            "manifest": {"status": "valid", "schema_version": 1}, "profiles": [profile(item) for item in profiles],
            "errors": [], "runtime_acceptance_verified": False, "limitations": [],
            "pinned_versions_match": (not mismatched) if (matched or mismatched) else None,
            "git": {"baseline_commit": "0" * 40, "current_commit": "1" * 40, "comparison": "baseline_differs"}}


def pinned_error_report():
    """adoption_status.py's early return for an unreadable manifest (adoption_status.py:1311-1313)."""
    return {"schema_version": 1, "status": "prerequisites_missing",
            "platform": {"os": "linux", "architecture": "x86_64", "python": "3.13.0", "supported": False},
            "manifest": {"status": "invalid"}, "profiles": [],
            "errors": ["manifest is unavailable or not valid UTF-8 JSON"], "runtime_acceptance_verified": False,
            "limitations": []}


def saturation_report(layers=(), triggers=None):
    """saturation_ledger.py --report --json (build_report(), saturation_ledger.py:966-1002).
    ``layers`` is (catalog/layer_id, due, last_sweep) triples; ``triggers`` maps a layer to its current triggers."""
    triggers = triggers or {}
    rows = [{"catalog": key.split("/")[0], "layer_id": key.split("/")[1], "research_status": "on_requirement_change",
             "clean_count": 0 if due else 3, "saturation_candidate": not due, "due": due, "last_sweep": last,
             "last_counted": None, "reset": list(triggers.get(key, [])),
             "current_triggers": list(triggers.get(key, []))} for key, due, last in layers]
    return {"policy": {"K": 3, "min_gap_days": 7}, "sweeps": 1, "completed_sweeps": 1,
            "last_completed": {"sweep_id": "sweep-a", "date": "2026-09-29"},
            "inputs": {"staleness": True, "freshness": "not available", "baseline_manifest": None}, "notes": [],
            "due": [key for key, due, _ in layers if due],
            "saturation_candidates": [key for key, due, _ in layers if not due],
            "current_reopen_triggers": {key: value for key, value in triggers.items() if value}, "layers": rows}


def skills_report(states=(), cli_drift=False, errors=()):
    """runtime_skill_freshness.py --output (build_report(), runtime_skill_freshness.py:106-116)."""
    skills = [{"name": f"skill-{index}", "source": "example/skills", "path": f"skills/skill-{index}",
               "status": "selected", "pinned_ref": "a" * 40, "head_ref": "b" * 40, "pinned_tree": "c" * 40,
               "head_tree": "d" * 40, "manifest_tree_matches_pin": True, "state": state, "native_check_ref": "a" * 40,
               "native_check_advances_commit_pin": False} for index, state in enumerate(states)]
    return {"schema_version": 1, "kind": "runtime_skill_freshness_report", "checked_at": "2026-09-30T12:00:00+00:00",
            "report_only": True,
            "cli": {"pinned": "1.5.0", "latest": "v1.6.0" if cli_drift else "v1.5.0", "drift": cli_drift},
            "native_check": {"executed": False, "source": None, "pinned_version": "1.5.0", "pinned_ref": "a" * 40,
                             "reason": "synthetic"},
            "skills": skills, "errors": list(errors), "ok": not errors}


def ledger(*sweeps):
    """catalogs/saturation/ledger.json; only sweeps[].{sweep_id, date, status} matter here."""
    return {"schema_version": 1, "policy": {"K": 3, "min_gap_days": 7},
            "sweeps": [{"sweep_id": sweep_id, "date": day, "status": status} for sweep_id, day, status in sweeps]}


class Checkout:
    """A temporary checkout whose checks are fakes, with a state directory beside it (outside the checkout).
    By default nothing is due."""

    def __init__(self, test: unittest.TestCase):
        temporary = tempfile.TemporaryDirectory()
        test.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.root = base / "checkout"
        self.state = base / "state"
        self.set(STALENESS, staleness_report())
        self.set(PINNED, pinned_report())
        self.set(SATURATION, saturation_report([("foundation/workers", False, "sweep-a")]))
        self.write_ledger(ledger(("sweep-a", "2026-09-29", "completed")))

    def set(self, relative: str, report=None, *, stdout: str | None = None, code: int = 0,
            output_file: str | None = None) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FAKE_CHECK, encoding="utf-8")
        spec = {"stdout": json.dumps(report) if stdout is None else stdout, "code": code}
        if output_file is not None:
            spec["output_file"] = output_file
        path.with_name(path.name + ".spec.json").write_text(json.dumps(spec), encoding="utf-8")

    def something_due(self) -> None:
        self.set(STALENESS, staleness_report(("codex", ["pin_moved"]), ("qmd", ["stale", "pin_moved"])))
        self.set(PINNED, pinned_report(mismatched=("codex",)))
        self.set(SATURATION, saturation_report(
            [("foundation/workers", True, "sweep-a")],
            {"foundation/workers": [{"trigger": "pin_moved", "ref": "receipt_staleness:linux-wsl2-x86_64/codex"}]}))

    def write_ledger(self, data) -> None:
        path = self.root / "catalogs/saturation/ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")

    def recorded(self, relative: str, suffix: str = ".argv.json"):
        path = self.root / relative
        marker = path.with_name(path.name + suffix)
        return json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else None

    def run(self, *extra: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cd.main(["--root", str(self.root), "--state-dir", str(self.state), "--now", NOW, *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    @property
    def due_file(self) -> Path:
        return self.state / "currency-due.json"


class DueFileTests(unittest.TestCase):
    def test_nothing_due_writes_no_file(self):
        checkout = Checkout(self)
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        self.assertFalse(checkout.due_file.exists())

    def test_nothing_due_removes_an_earlier_file(self):
        checkout = Checkout(self)
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_text('{"earlier": true}\n', encoding="utf-8")
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        self.assertFalse(checkout.due_file.exists())

    def test_something_due_writes_the_document_privately_with_a_short_summary(self):
        checkout = Checkout(self)
        checkout.something_due()
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertEqual(list(document), ["generated_at", "due", "summary_line", "details"])
        self.assertEqual(document["generated_at"], NOW)
        self.assertEqual(document["due"], {"pins_behind": 1, "stale_receipts": 2, "due_layers": 0,
                                           "reopen_triggers": 1})
        self.assertEqual(document["summary_line"],
                         f"stack currency: 1 pin behind, 2 stale receipts, 1 layer with reopen triggers; "
                         f"details: {COMMAND}")
        self.assertLessEqual(len(document["summary_line"]), 160)
        self.assertEqual(stat.S_IMODE(checkout.due_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(checkout.state.stat().st_mode), 0o700)
        # The temporary file was renamed into place, not left beside it.
        self.assertEqual([path.name for path in checkout.state.iterdir()], ["currency-due.json"])

    def test_a_write_that_fails_before_the_rename_keeps_the_earlier_file(self):
        checkout = Checkout(self)
        checkout.something_due()
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_text("earlier\n", encoding="utf-8")
        with mock.patch.object(cd.os, "replace", side_effect=OSError("simulated rename failure")):
            code, _, stderr = checkout.run()
        self.assertEqual(code, 2)
        self.assertIn("simulated rename failure", stderr)
        self.assertEqual(checkout.due_file.read_text(encoding="utf-8"), "earlier\n")
        self.assertEqual([path.name for path in checkout.state.iterdir()], ["currency-due.json"])

    def test_the_state_directory_must_be_outside_the_checkout(self):
        checkout = Checkout(self)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cd.main(["--root", str(checkout.root), "--state-dir", str(checkout.root / "state"), "--now", NOW])
        self.assertEqual(raised.exception.code, 2)
        self.assertFalse((checkout.root / "state").exists())


class FailureTests(unittest.TestCase):
    def test_malformed_check_output_exits_2_and_writes_nothing(self):
        outputs = {"not JSON": "{not json", "a JSON array": "[]", "an object without the report's keys": "{}"}
        for relative in (STALENESS, PINNED, SATURATION):
            for label, text in outputs.items():
                with self.subTest(check=relative, output=label):
                    checkout = Checkout(self)
                    checkout.something_due()
                    checkout.set(relative, stdout=text)
                    code, _, stderr = checkout.run()
                    self.assertEqual(code, 2, stderr)
                    self.assertIn(Path(relative).name, stderr)
                    self.assertFalse(checkout.state.exists())

    def test_a_malformed_ledger_exits_2(self):
        checkout = Checkout(self)
        checkout.something_due()
        checkout.write_ledger("{not json")
        code, _, _ = checkout.run()
        self.assertEqual(code, 2)
        self.assertFalse(checkout.state.exists())

    def test_a_failed_run_leaves_an_earlier_file_byte_identical(self):
        checkout = Checkout(self)
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_bytes(b'{"earlier": true}\n')
        checkout.set(SATURATION, stdout="{not json")
        code, _, _ = checkout.run()
        self.assertEqual(code, 2)
        self.assertEqual(checkout.due_file.read_bytes(), b'{"earlier": true}\n')

    def test_exit_codes_follow_each_check_s_own_contract(self):
        # receipt_staleness.py and saturation_ledger.py exit 2 only when their inputs are unreadable
        # (receipt_staleness.py:236-238, saturation_ledger.py:1342-1344). adoption_status.py exits 2 whenever
        # prerequisites are missing (adoption_status.py:1400), which is not a failure of this report; its errors
        # list (adoption_status.py:1311-1316) is.
        missing = pinned_report(mismatched=("codex",), status="prerequisites_missing")
        cases = [
            ("receipt_staleness exit 2", STALENESS, {"stdout": json.dumps({"status": "error", "error": "x"}),
                                                     "code": 2}, 2),
            ("saturation_ledger exit 2", SATURATION, {"stdout": "", "code": 2}, 2),
            ("adoption_status exit 2, prerequisites missing", PINNED, {"stdout": json.dumps(missing), "code": 2}, 0),
            ("adoption_status errors", PINNED, {"stdout": json.dumps(pinned_error_report()), "code": 2}, 2),
            ("adoption_status exit 1", PINNED, {"stdout": json.dumps(pinned_report()), "code": 1}, 2),
        ]
        for label, relative, spec, expected in cases:
            with self.subTest(case=label):
                checkout = Checkout(self)
                checkout.set(relative, **spec)
                code, _, stderr = checkout.run("--dry-run")
                self.assertEqual(code, expected, stderr)


class DryRunTests(unittest.TestCase):
    def test_dry_run_prints_the_document_and_writes_nothing(self):
        checkout = Checkout(self)
        checkout.something_due()
        code, stdout, stderr = checkout.run("--dry-run", "--json")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["due"]["pins_behind"], 1)
        self.assertFalse(checkout.state.exists())

    def test_dry_run_keeps_an_earlier_file_when_nothing_is_due(self):
        checkout = Checkout(self)
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_text("earlier\n", encoding="utf-8")
        code, stdout, _ = checkout.run("--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(stdout.splitlines()[0], "stack currency: nothing due")
        self.assertEqual(checkout.due_file.read_text(encoding="utf-8"), "earlier\n")

    def test_text_output_starts_with_the_summary_line(self):
        checkout = Checkout(self)
        checkout.something_due()
        _, text, _ = checkout.run("--dry-run")
        _, raw, _ = checkout.run("--dry-run", "--json")
        self.assertEqual(text.splitlines()[0], json.loads(raw)["summary_line"])


class CountTests(unittest.TestCase):
    def document(self, checkout: Checkout, *extra: str) -> dict:
        code, stdout, stderr = checkout.run("--dry-run", "--json", *extra)
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout)

    def test_layers_are_due_once_the_monthly_sweep_cadence_has_passed(self):
        # recipes/saturation-sweep.md: "Sweep only the due layers, at most monthly ..., or sooner when a
        # reopen trigger fires"; a layer that is not a saturation candidate counts once its last completed
        # sweep is at least 30 days old, or when it has none or it cannot be dated.
        checkout = Checkout(self)
        checkout.set(SATURATION, saturation_report([
            ("foundation/thirty-days", True, "sweep-thirty"), ("foundation/twenty-nine-days", True, "sweep-29"),
            ("foundation/never-swept", True, None), ("foundation/unknown-sweep", True, "sweep-missing"),
            ("foundation/saturated", False, "sweep-thirty")]))
        checkout.write_ledger(ledger(("sweep-thirty", "2026-08-31", "completed"),
                                     ("sweep-29", "2026-09-01", "completed"),
                                     ("sweep-missing", "2026-08-01", "stopped")))
        document = self.document(checkout)
        self.assertEqual(document["due"]["due_layers"], 3)
        due = [item for item in document["details"] if item["kind"] == "due_layer"]
        self.assertEqual([item["layer"] for item in due],
                         ["foundation/thirty-days", "foundation/never-swept", "foundation/unknown-sweep"])
        self.assertEqual(due[0]["age_days"], 30)
        coverage = document["details"][-1]
        self.assertEqual(coverage["kind"], "coverage")
        self.assertEqual((coverage["due_layers_total"], coverage["sweep_cadence_days"]), (4, 30))
        # --sweep-cadence-days 0 is the plain reading: every layer the report marks due.
        self.assertEqual(self.document(checkout, "--sweep-cadence-days", "0")["due"]["due_layers"], 4)

    def test_reopen_triggers_count_layers(self):
        checkout = Checkout(self)
        trigger = {"trigger": "pin_moved", "ref": "receipt_staleness:linux-wsl2-x86_64/codex"}
        checkout.set(SATURATION, saturation_report(
            [("foundation/a", True, "sweep-a"), ("us-equities/b", True, "sweep-a")],
            {"foundation/a": [trigger, dict(trigger, ref="receipt_staleness:linux-wsl2-x86_64/qmd")],
             "us-equities/b": [trigger]}))
        document = self.document(checkout)
        self.assertEqual(document["due"]["reopen_triggers"], 2)
        reopened = {item["layer"]: item["triggers"] for item in document["details"] if item["kind"] == "reopen_trigger"}
        self.assertEqual(len(reopened["foundation/a"]), 2)

    def test_stale_receipts_are_the_report_s_flagged_rows(self):
        checkout = Checkout(self)
        checkout.set(STALENESS, staleness_report(("codex", ["pin_moved", "no_bound_receipt"]), ("qmd", ["stale"])))
        document = self.document(checkout)
        self.assertEqual(document["due"]["stale_receipts"], 2)
        flagged = [(item["component_id"], item["flags"]) for item in document["details"]
                   if item["kind"] == "stale_receipt"]
        self.assertEqual(flagged, [("codex", ["pin_moved", "no_bound_receipt"]), ("qmd", ["stale"])])

    def test_pins_behind_counts_each_mismatched_component_once(self):
        checkout = Checkout(self)
        checkout.set(PINNED, pinned_report(mismatched=("codex", "rtk"), matched=(),
                                           profiles=("foundation-cpu", "token-efficiency")))
        document = self.document(checkout)
        self.assertEqual(document["due"]["pins_behind"], 2)
        codex = next(item for item in document["details"]
                     if item["kind"] == "pin_mismatch" and item["component_id"] == "codex")
        self.assertEqual(codex["profiles"], ["foundation-cpu", "token-efficiency"])
        self.assertEqual(codex["pinned_version"], "2.0.0")
        self.assertEqual(document["details"][-1]["pins_unchecked"], 1)

    def test_every_check_gets_its_documented_arguments_and_the_same_clock(self):
        checkout = Checkout(self)
        checkout.something_due()
        self.assertEqual(checkout.run("--dry-run")[0], 0)
        root = str(checkout.root)
        self.assertEqual(checkout.recorded(STALENESS), ["--root", root, "--json", "--now", NOW])
        self.assertEqual(checkout.recorded(PINNED),
                         ["--manifest", str(checkout.root / "adoption/manifest.json"), "--pinned-versions", "--json"])
        saturation = checkout.recorded(SATURATION)
        self.assertEqual(saturation[:5], ["--root", root, "--report", "--json", "--staleness"])
        # saturation_ledger.py read receipt_staleness.py's report, as .github/workflows/saturation-tracking.yml
        # composes them, from a temporary file outside the checkout and the state directory that is gone now.
        self.assertEqual(checkout.recorded(SATURATION, ".staleness.json")["flagged"], 2)
        handed = Path(saturation[5])
        self.assertFalse(handed.exists())
        self.assertNotIn(checkout.root, handed.parents)
        self.assertNotIn(checkout.state, handed.parents)


class NetworkTests(unittest.TestCase):
    def test_network_checks_are_off_by_default(self):
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout="{}", output_file=json.dumps(skills_report(("skill-drift",), cli_drift=True)))
        code, stdout, _ = checkout.run("--dry-run", "--json")
        self.assertEqual(code, 0)
        self.assertIsNone(checkout.recorded(SKILLS))
        self.assertEqual(json.loads(stdout)["due"]["pins_behind"], 0)

    def test_network_adds_drifted_skill_pins_and_keeps_fetch_errors_unknown(self):
        # runtime_skill_freshness.py:152 counts skill-drift, repository-drift and removed-at-head as drift, and
        # :103 sets cli.drift; it exits 1 whenever its report is not ok (:154), which is not a failure here.
        checkout = Checkout(self)
        states = ("current", "skill-drift", "repository-drift", "removed-at-head", "unfetched", "invalid-pin")
        checkout.set(SKILLS, stdout='{"ok": false}', code=1, output_file=json.dumps(
            skills_report(states, cli_drift=True, errors=["gh api failed (exit 1): repos/example/skills"])))
        code, stdout, stderr = checkout.run("--dry-run", "--json", "--network")
        self.assertEqual(code, 0, stderr)
        document = json.loads(stdout)
        self.assertEqual(document["due"]["pins_behind"], 4)
        self.assertEqual(sorted(item["state"] for item in document["details"] if item["kind"] == "skill_drift"),
                         ["removed-at-head", "repository-drift", "skill-drift"])
        self.assertEqual(document["details"][-1]["skills_fetch_errors"], 1)
        arguments = checkout.recorded(SKILLS)
        self.assertEqual(arguments[:2],
                         ["--manifest", str(checkout.root / "blueprints/runtime-workers/skills/manifest.json")])
        self.assertEqual(arguments[2], "--output")

    def test_a_skills_report_that_was_not_written_exits_2(self):
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout="{}", code=1)
        code, _, _ = checkout.run("--dry-run", "--network")
        self.assertEqual(code, 2)


class SummaryLineTests(unittest.TestCase):
    def test_the_line_names_only_nonzero_counts_and_the_command(self):
        line = cd.summary_line({"pins_behind": 2, "stale_receipts": 1, "due_layers": 3, "reopen_triggers": 0})
        self.assertEqual(line, f"stack currency: 2 pins behind, 1 stale receipt, 3 layers due; details: {COMMAND}")
        self.assertEqual(cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 0)), "stack currency: nothing due")

    def test_the_line_stays_within_160_characters_and_keeps_the_command(self):
        line = cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 10 ** 40))
        self.assertLessEqual(len(line), 160)
        self.assertTrue(line.endswith(f"; details: {COMMAND}"))


class StateDirectoryTests(unittest.TestCase):
    def test_xdg_state_home_is_used_only_when_absolute(self):
        home = Path(tempfile.gettempdir()) / "synthetic-home"
        state = Path(tempfile.gettempdir()) / "synthetic-state"
        default = home / ".local/state/native-agent-stack"
        cases = [({"XDG_STATE_HOME": str(state), "HOME": str(home)}, state / "native-agent-stack"),
                 ({"XDG_STATE_HOME": "", "HOME": str(home)}, default),
                 ({"XDG_STATE_HOME": "relative/state", "HOME": str(home)}, default),
                 ({"HOME": str(home)}, default)]
        for environ, expected in cases:
            with self.subTest(environ=environ):
                self.assertEqual(cd.default_state_dir(environ), expected)


class ThisCheckoutTests(unittest.TestCase):
    def test_the_real_checks_run_dry_and_write_nothing(self):
        # The five-second budget is measured on the workstation by the acceptance command; this bound only
        # catches a pathological slowdown on slower runners.
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state"
            started = time.monotonic()
            result = subprocess.run([sys.executable, str(ROOT / "scripts/currency_due.py"), "--dry-run", "--json",
                                     "--state-dir", str(state)], capture_output=True, text=True, timeout=600,
                                    cwd=ROOT, stdin=subprocess.DEVNULL, check=False)
            elapsed = time.monotonic() - started
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            document = json.loads(result.stdout)
            self.assertEqual(list(document), ["generated_at", "due", "summary_line", "details"])
            self.assertEqual(list(document["due"]), list(cd.DUE_KEYS))
            self.assertTrue(all(isinstance(value, int) and value >= 0 for value in document["due"].values()))
            self.assertLessEqual(len(document["summary_line"]), 160)
            self.assertFalse(state.exists())
            self.assertLess(elapsed, 120)


class UnitTemplateTests(unittest.TestCase):
    def setUp(self):
        self.service = (SYSTEMD_DIR / "stack-currency.service").read_text(encoding="utf-8").splitlines()
        self.timer = (SYSTEMD_DIR / "stack-currency.timer").read_text(encoding="utf-8").splitlines()

    def test_the_service_is_a_guarded_oneshot_that_only_the_timer_starts(self):
        for setting in ("Type=oneshot", "UMask=0077", "NoNewPrivileges=true",
                        "Environment=PYTHONDONTWRITEBYTECODE=1",
                        "ExecStart=/usr/bin/python3 @REPOSITORY@/scripts/currency_due.py"):
            self.assertIn(setting, self.service)
        self.assertNotIn("[Install]", self.service)
        directives = [line for line in self.service if line and not line.startswith("#")]
        self.assertFalse(any("--network" in line for line in directives))
        # The version probes of adoption_status.py --pinned-versions resolve through PATH (shutil.which), and the
        # user manager's own PATH lacks the ecosystem bin directory.
        search_path = next(line for line in directives if line.startswith("Environment=PATH="))
        self.assertIn("%h/.local/share/codex-ecosystem/bin", search_path)

    def test_the_timer_runs_daily_catches_up_and_spreads_its_start(self):
        for setting in ("OnCalendar=daily", "Persistent=true", "RandomizedDelaySec=15m",
                        "Unit=stack-currency.service", "WantedBy=timers.target"):
            self.assertIn(setting, self.timer)


if __name__ == "__main__":
    unittest.main()
