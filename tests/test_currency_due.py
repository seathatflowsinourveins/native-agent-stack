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
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import currency_due as cd

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_DIR = ROOT / "adoption/templates/systemd"
NOW = "2026-09-30T12:00:00Z"
NOW_DATETIME = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
# The cwd-relative form of the command; a notice names the checkout's own copy of the script (Checkout.command).
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


def skills_report(states=(), cli_drift=False, errors=(), cli_unknown=False):
    """runtime_skill_freshness.py --output (build_report(), runtime_skill_freshness.py:106-116). ``cli_unknown`` is the
    release fetch that failed: cli.latest and cli.drift stay None (build_report() starts them so, :100). The
    ``manifest_tree_matches_pin`` value follows compare_skill() (:77-79): None when nothing was fetched, False for
    an invalid pin."""
    skills = [{"name": f"skill-{index}", "source": "example/skills", "path": f"skills/skill-{index}",
               "status": "selected", "pinned_ref": "a" * 40, "head_ref": "b" * 40, "pinned_tree": "c" * 40,
               "head_tree": "d" * 40,
               "manifest_tree_matches_pin": None if state == "unfetched" else state != "invalid-pin",
               "state": state, "native_check_ref": "a" * 40, "native_check_advances_commit_pin": False}
              for index, state in enumerate(states)]
    cli = ({"pinned": "1.5.0", "latest": None, "drift": None} if cli_unknown else
           {"pinned": "1.5.0", "latest": "v1.6.0" if cli_drift else "v1.5.0", "drift": cli_drift})
    return {"schema_version": 1, "kind": "runtime_skill_freshness_report", "checked_at": "2026-09-30T12:00:00+00:00",
            "report_only": True,
            "cli": cli,
            "native_check": {"executed": False, "source": None, "pinned_version": "1.5.0", "pinned_ref": "a" * 40,
                             "reason": "synthetic"},
            "skills": skills, "errors": list(errors), "ok": not errors}


def ledger(*sweeps):
    """catalogs/saturation/ledger.json; only sweeps[].{sweep_id, date, status} matter here."""
    return {"schema_version": 1, "policy": {"K": 3, "min_gap_days": 7},
            "sweeps": [{"sweep_id": sweep_id, "date": day, "status": status} for sweep_id, day, status in sweeps]}


def json_paths(node, prefix=()):
    """The path (a tuple of keys and indexes) to every value nested inside ``node``, not ``node`` itself."""
    if isinstance(node, dict):
        children = list(node.items())
    elif isinstance(node, list):
        children = list(enumerate(node))
    else:
        return
    for key, child in children:
        yield (*prefix, key)
        yield from json_paths(child, (*prefix, key))


def short_temp_base() -> str:
    """The shortest writable temporary base among TMPDIR (tempfile.gettempdir()) and /tmp. macOS runners put TMPDIR
    under /private/var/folders/..., long enough to push a fixture checkout's absolute command out of the
    160-character notice line, which changes the line's form and fails the exact-text assertions; the tests that
    need a long path build one on purpose."""
    candidates = [tempfile.gettempdir(), "/tmp"]
    usable = [c for c in candidates if os.path.isdir(c) and os.access(c, os.W_OK)]
    return min(usable, key=lambda c: len(os.path.realpath(c)))


class Checkout:
    """A temporary checkout whose checks are fakes, with a state directory beside it (outside the checkout).
    By default nothing is due."""

    def __init__(self, test: unittest.TestCase, name: str = "checkout"):
        temporary = tempfile.TemporaryDirectory(dir=short_temp_base())
        test.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.root = base / name
        self.state = base / "state"
        # The checkout's own copy of the script, which the notice's command names by its absolute path.
        self.script = self.root / "scripts/currency_due.py"
        self.script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "scripts/currency_due.py", self.script)
        self.set(STALENESS, staleness_report())
        self.set(PINNED, pinned_report())
        self.set(SATURATION, saturation_report([("foundation/workers", False, "sweep-a")]))
        self.write_ledger(ledger(("sweep-a", "2026-09-29", "completed")))
        # The user manager's answer that run() hands the script instead of this host's: {unit: properties}, or a string
        # saying why it could not be asked. No unit by default.
        self.units = {}

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

    def command(self, *options: str) -> str:
        """The command a notice written for this checkout ends with."""
        return cd.join_command(["python3", cd.notice_path(self.script), "--dry-run", *options])

    def run(self, *extra: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                mock.patch.object(cd, "query_units", lambda units, systemctl="systemctl": self.units):
            code = cd.main(["--root", str(self.root), "--state-dir", str(self.state), "--now", NOW, *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def write_record(self, name: str, record) -> None:
        """A status record in the state directory, as the backup and restore-check DAGs write it."""
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.state / name).write_text(record if isinstance(record, str) else json.dumps(record), encoding="utf-8")

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
        self.assertEqual(list(document), ["generated_at", "root", "due", "summary_line", "details_command",
                                          "details"])
        self.assertEqual(document["generated_at"], NOW)
        self.assertEqual(document["due"], {"pins_behind": 1, "stale_receipts": 2, "due_layers": 0,
                                           "reopen_triggers": 1, "host_alerts": 0})
        # The counts give way to the command when TMPDIR makes the checkout's path long (SummaryLineTests covers
        # the shortening), so the exact text is checked around the command.
        self.assertTrue(document["summary_line"].startswith("stack currency: 1 pin behind, 2 stale receipts, 1 layer"),
                        document["summary_line"])
        self.assertTrue(document["summary_line"].endswith(f"; details: {checkout.command()}"),
                        document["summary_line"])
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

    def test_a_malformed_pinned_versions_field_exits_2_and_writes_nothing(self):
        # adoption_status.py:1258-1263,1331 always sets pinned_versions, a list of {"id": str, ...}, beside the
        # summary. `True or []` used to reach a loop and raise TypeError, which is exit 1 with a traceback, not 2.
        def report_with(value):
            report = pinned_report(mismatched=("codex",))
            report["profiles"][0]["pinned_versions"] = value
            return report

        malformed = {"a boolean": True, "a number": 1, "a string": "codex", "an object": {"id": "codex"},
                     "a list of numbers": [1], "an entry whose id is a list": [{"id": ["codex"]}],
                     "an entry without an id": [{"pinned_version": "1.0.0"}], "null": None}
        for label, value in malformed.items():
            with self.subTest(pinned_versions=label):
                checkout = Checkout(self)
                checkout.set(PINNED, report_with(value))
                code, _, stderr = checkout.run()
                self.assertEqual(code, 2, stderr)
                self.assertIn("adoption_status.py", stderr)
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


class AggregateShapeTests(unittest.TestCase):
    """aggregate() reads nested fields of four JSON reports. Whatever type one of them has, it either ignores the field
    or raises CheckError (exit 2); any other exception would be exit 1 with a traceback."""

    REPLACEMENTS = (None, True, 0, -1, 1.5, "x", [], {}, [None], [[]], {"a": None})

    @staticmethod
    def reports() -> dict:
        trigger = {"trigger": "pin_moved", "ref": "receipt_staleness:linux-wsl2-x86_64/codex"}
        return {"receipts": staleness_report(("codex", ["pin_moved"])),
                "pins": pinned_report(mismatched=("codex",)),
                "layers": saturation_report([("foundation/workers", True, "sweep-a")],
                                            {"foundation/workers": [trigger]}),
                "skills": skills_report(("skill-drift", "invalid-pin", "unfetched", "current"), cli_drift=True,
                                        errors=["gh api failed (exit 1): repos/example/skills/commits/HEAD"]),
                "sweep_dates": {"sweep-a": "2026-08-01"}}

    def test_a_wrong_typed_field_is_ignored_or_a_check_error(self):
        # The unmodified reports: codex's pin, a drifted skill, an invalid skill pin and the skills CLI make four.
        document = cd.aggregate(self.reports(), NOW_DATETIME, NOW, 30)
        self.assertEqual(document["due"], {"pins_behind": 4, "stale_receipts": 1, "due_layers": 1,
                                           "reopen_triggers": 1, "host_alerts": 0})
        exercised = 0
        for name in ("receipts", "pins", "layers", "skills"):
            for path in json_paths(self.reports()[name]):
                for value in self.REPLACEMENTS:
                    reports = self.reports()
                    parent = reports[name]
                    for key in path[:-1]:
                        parent = parent[key]
                    parent[path[-1]] = value
                    with self.subTest(report=name, path=path, value=value):
                        try:
                            document = cd.aggregate(reports, NOW_DATETIME, NOW, 30)
                        except cd.CheckError:
                            continue
                        cd.render_text(document)
                        exercised += 1
        self.assertGreater(exercised, 500)


class NetworkTests(unittest.TestCase):
    def test_network_checks_are_off_by_default(self):
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout="{}", output_file=json.dumps(skills_report(("skill-drift",), cli_drift=True)))
        code, stdout, _ = checkout.run("--dry-run", "--json")
        self.assertEqual(code, 0)
        self.assertIsNone(checkout.recorded(SKILLS))
        self.assertEqual(json.loads(stdout)["due"]["pins_behind"], 0)

    def test_network_adds_drifted_and_invalid_skill_pins_and_keeps_fetch_errors_unknown(self):
        # runtime_skill_freshness.py:152 counts skill-drift, repository-drift and removed-at-head as drift, and
        # :103 sets cli.drift; it exits 1 whenever its report is not ok (:154), which is not a failure here. An
        # invalid-pin is a fetched answer (:78-79: the manifest's tree is not the tree at the pinned ref), so it
        # counts too; an unfetched skill and a failed fetch stay unknown.
        checkout = Checkout(self)
        states = ("current", "skill-drift", "repository-drift", "removed-at-head", "unfetched", "invalid-pin")
        checkout.set(SKILLS, stdout='{"ok": false}', code=1, output_file=json.dumps(
            skills_report(states, cli_drift=True, errors=["gh api failed (exit 1): repos/example/skills"])))
        code, stdout, stderr = checkout.run("--dry-run", "--json", "--network")
        self.assertEqual(code, 0, stderr)
        document = json.loads(stdout)
        self.assertEqual(document["due"]["pins_behind"], 5)
        self.assertEqual(sorted(item["state"] for item in document["details"] if item["kind"] == "skill_drift"),
                         ["removed-at-head", "repository-drift", "skill-drift"])
        self.assertEqual([item["state"] for item in document["details"] if item["kind"] == "skill_pin_invalid"],
                         ["invalid-pin"])
        coverage = document["details"][-1]
        self.assertEqual((coverage["skills_fetch_errors"], coverage["skills_unresolved"], coverage["skills_complete"]),
                         (1, 1, False))
        arguments = checkout.recorded(SKILLS)
        self.assertEqual(arguments[:2],
                         ["--manifest", str(checkout.root / "blueprints/runtime-workers/skills/manifest.json")])
        self.assertEqual(arguments[2], "--output")

    def test_a_skills_report_that_was_not_written_exits_2(self):
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout="{}", code=1)
        code, _, _ = checkout.run("--dry-run", "--network")
        self.assertEqual(code, 2)


class IncompleteSkillCheckTests(unittest.TestCase):
    """A skill check that could not answer is unknown, and unknown is not "nothing due" (the check's own report says
    "Incomplete fetches remain unknown", runtime_skill_freshness.py:134). It must never remove the notice an earlier
    run wrote. The timer does not pass --network; these are the runs that do."""

    FETCH_ERROR = "gh api failed (exit 1): repos/example/skills/commits/HEAD"
    EARLIER = b'{"earlier": true}\n'

    def incomplete_reports(self) -> dict:
        return {
            "a failed fetch": skills_report(("unfetched",), errors=[self.FETCH_ERROR]),
            "an unfetched skill that names no error": skills_report(("current", "unfetched")),
            "a state this script does not know": skills_report(("current", "state-of-a-newer-check")),
            "a failed release fetch": skills_report(("current",), cli_unknown=True, errors=[self.FETCH_ERROR]),
            "an unknown release that names no error": skills_report(("current",), cli_unknown=True),
            "an error beside skills that were all fetched": skills_report(
                ("current",), errors=["cli pin: version None is not a release version"]),
        }

    def skills_checkout(self, report: dict) -> Checkout:
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout='{"ok": false}', code=1, output_file=json.dumps(report))
        return checkout

    def test_an_incomplete_check_keeps_the_earlier_due_file_byte_identical(self):
        for label, report in self.incomplete_reports().items():
            with self.subTest(case=label):
                checkout = self.skills_checkout(report)
                checkout.state.mkdir(mode=0o700)
                checkout.due_file.write_bytes(self.EARLIER)
                code, stdout, stderr = checkout.run("--network")
                self.assertEqual(code, 0, stderr)
                self.assertEqual(checkout.due_file.read_bytes(), self.EARLIER)
                self.assertEqual([path.name for path in checkout.state.iterdir()], ["currency-due.json"])
                self.assertIn("nothing known due", stdout)
                self.assertIn("kept", stdout)

    def test_an_incomplete_check_creates_no_due_file(self):
        for label, report in self.incomplete_reports().items():
            with self.subTest(case=label):
                checkout = self.skills_checkout(report)
                code, stdout, stderr = checkout.run("--network")
                self.assertEqual(code, 0, stderr)
                self.assertFalse(checkout.state.exists())
                self.assertIn("nothing known due", stdout)

    def test_a_complete_check_with_nothing_due_still_removes_the_earlier_file(self):
        # The control: it is the incompleteness, not --network, that keeps the file.
        checkout = self.skills_checkout(skills_report(("current", "current")))
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_bytes(self.EARLIER)
        code, stdout, stderr = checkout.run("--network")
        self.assertEqual(code, 0, stderr)
        self.assertFalse(checkout.due_file.exists())
        self.assertIn("stack currency: nothing due", stdout)

    def test_an_incomplete_check_still_writes_what_the_other_checks_found(self):
        checkout = self.skills_checkout(skills_report(("unfetched",), errors=[self.FETCH_ERROR]))
        checkout.something_due()
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_bytes(self.EARLIER)
        code, stdout, stderr = checkout.run("--network")
        self.assertEqual(code, 0, stderr)
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertEqual(document["due"], {"pins_behind": 1, "stale_receipts": 2, "due_layers": 0,
                                           "reopen_triggers": 1, "host_alerts": 0})
        coverage = document["details"][-1]
        self.assertEqual((coverage["skills_complete"], coverage["skills_fetch_errors"], coverage["skills_unresolved"]),
                         (False, 1, 1))
        self.assertEqual([item["error"] for item in document["details"] if item["kind"] == "skills_probe_error"],
                         [self.FETCH_ERROR])
        self.assertIn("incomplete", stdout)

    def test_an_invalid_pin_is_a_finding_that_replaces_the_earlier_file(self):
        # runtime_skill_freshness.py:78-79: the pinned ref was fetched and the manifest's tree is not its tree.
        checkout = self.skills_checkout(skills_report(("current", "invalid-pin")))
        checkout.state.mkdir(mode=0o700)
        checkout.due_file.write_bytes(self.EARLIER)
        code, _, stderr = checkout.run("--network")
        self.assertEqual(code, 0, stderr)
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertEqual(document["due"]["pins_behind"], 1)
        invalid = [item for item in document["details"] if item["kind"] == "skill_pin_invalid"]
        self.assertEqual([(item["skill"], item["state"]) for item in invalid], [("skill-1", "invalid-pin")])
        self.assertIs(document["details"][-1]["skills_complete"], True)
        self.assertEqual(document["summary_line"], f"stack currency: 1 pin behind; details: {checkout.command('--network')}")

    def test_a_dry_run_headline_says_nothing_known_due_and_lists_the_error(self):
        checkout = self.skills_checkout(skills_report(("unfetched",), errors=[self.FETCH_ERROR]))
        code, text, stderr = checkout.run("--dry-run", "--network")
        self.assertEqual(code, 0, stderr)
        lines = text.splitlines()
        self.assertEqual(lines[0], "stack currency: nothing known due, skill check incomplete")
        self.assertTrue(any(self.FETCH_ERROR in line for line in lines))
        self.assertTrue(any(line.startswith("coverage:") and "incomplete" in line for line in lines))
        self.assertFalse(checkout.state.exists())


class DetailsCommandTests(unittest.TestCase):
    """The command that ends the notice must print the details of the run that wrote it from any working directory:
    it names the inspected checkout's own copy of the script by its absolute path and repeats the options that
    change what a run reports, --network and a non-default --sweep-cadence-days."""

    def notice(self, checkout: Checkout, *options: str) -> dict:
        code, _, stderr = checkout.run(*options)
        self.assertEqual(code, 0, stderr)
        return json.loads(checkout.due_file.read_text(encoding="utf-8"))

    def literal_command(self, checkout: Checkout, document: dict) -> list[str]:
        """The command a reader of the notice's line runs, read from an unrelated working directory: the line's own
        command, or, when the line points at the due-file, the details_command of that file."""
        summary = document["summary_line"]
        self.assertIn("; details: ", summary)
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, True)
        tail = summary.split("; details: ", 1)[1]
        if tail.startswith("cat "):
            # The literal printed command, as a process from the unrelated directory: it prints the document. A
            # shell expands a word-initial ~ and a quoted $XDG_STATE_HOME; subprocess does not.
            words = [os.path.expandvars(os.path.expanduser(word)) if word.startswith(("~/", "$XDG_STATE_HOME"))
                     else word for word in shlex.split(tail)]
            self.assertEqual(words[0], "cat")
            result = subprocess.run(words, cwd=elsewhere, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            pointed = json.loads(result.stdout)
            self.assertEqual(pointed["details_command"], document["details_command"])
            self.assertEqual(pointed["root"], str(checkout.root))
            tail = pointed["details_command"]
        command = shlex.split(tail)
        self.assertEqual(command, shlex.split(document["details_command"]), summary)
        self.assertEqual(command[0], "python3")
        return command

    def run_elsewhere(self, checkout: Checkout, command: list[str]) -> dict:
        """The literal command as a process from an unrelated working directory: the path in the command, not the
        cwd, chooses the checkout (the SessionStart hook prints the line in whatever project a session starts in)."""
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, True)
        # A shell expands a word-initial ~ (the script's path and a --root value); subprocess does not. A checkout
        # whose state directory comes from XDG_STATE_HOME (state None) passes no --state-dir: the process inherits
        # the variable, as the session that prints the line has it.
        words = [os.path.expanduser(word) if word.startswith("~/") else word for word in command[1:]]
        state = ["--state-dir", str(checkout.state)] if checkout.state is not None else []
        result = subprocess.run([sys.executable, *words, "--json", "--now", NOW, *state],
                                cwd=elsewhere, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def reproduced(self, checkout: Checkout, document: dict) -> dict:
        """Run the notice's own command in this checkout (in process) and as a process from an unrelated working
        directory, and return the document it prints."""
        command = self.literal_command(checkout, document)
        self.assertEqual(command[:3], ["python3", cd.notice_path(checkout.script), "--dry-run"], command)
        code, stdout, stderr = checkout.run(*command[2:], "--json")
        self.assertEqual(code, 0, stderr)
        document = json.loads(stdout)
        self.assertEqual(self.run_elsewhere(checkout, command)["due"], document["due"])
        return document

    def test_skill_drift_alone_is_reproduced_by_the_command_in_the_notice(self):
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout="{}", output_file=json.dumps(skills_report(("skill-drift",))))
        document = self.notice(checkout, "--network")
        self.assertEqual(document["due"], {"pins_behind": 1, "stale_receipts": 0, "due_layers": 0,
                                           "reopen_triggers": 0, "host_alerts": 0})
        self.assertEqual(document["summary_line"], f"stack currency: 1 pin behind; details: {checkout.command('--network')}")
        again = self.reproduced(checkout, document)
        self.assertEqual((again["due"], again["summary_line"]), (document["due"], document["summary_line"]))
        # Without the option the same command sees nothing, which is why the notice has to name it.
        self.assertEqual(json.loads(checkout.run("--dry-run", "--json")[1])["due"]["pins_behind"], 0)

    def test_a_non_default_cadence_is_reproduced_by_the_command_in_the_notice(self):
        checkout = Checkout(self)
        # Swept the day before NOW: not yet due at the default 30 days, due at 0.
        checkout.set(SATURATION, saturation_report([("foundation/workers", True, "sweep-a")]))
        document = self.notice(checkout, "--sweep-cadence-days", "0")
        self.assertEqual(document["due"]["due_layers"], 1)
        self.assertEqual(document["summary_line"],
                         f"stack currency: 1 layer due; details: {checkout.command('--sweep-cadence-days', '0')}")
        again = self.reproduced(checkout, document)
        self.assertEqual((again["due"], again["summary_line"]), (document["due"], document["summary_line"]))
        self.assertEqual(json.loads(checkout.run("--dry-run", "--json")[1])["due"]["due_layers"], 0)

    def test_both_options_are_named_and_the_line_keeps_its_limit(self):
        checkout = Checkout(self)
        checkout.something_due()
        checkout.set(SKILLS, stdout="{}", output_file=json.dumps(skills_report(("skill-drift",))))
        document = self.notice(checkout, "--network", "--sweep-cadence-days", "7")
        self.assertTrue(document["summary_line"].endswith(f"; details: {checkout.command('--network', '--sweep-cadence-days', '7')}"),
                        document["summary_line"])
        self.assertLessEqual(len(document["summary_line"]), 160)
        self.assertEqual(self.reproduced(checkout, document)["due"], document["due"])

    def test_options_that_do_not_change_the_counts_are_not_repeated(self):
        checkout = Checkout(self)
        checkout.something_due()
        # checkout.run adds --root, --state-dir and --now; --json and --dry-run are output modes.
        document = self.notice(checkout, "--json")
        self.assertTrue(document["summary_line"].endswith(f"; details: {checkout.command()}"),
                        document["summary_line"])

    def test_a_checkout_without_the_script_is_named_by_root(self):
        checkout = Checkout(self)
        checkout.script.unlink()
        command = shlex.split(cd.details_command(checkout.root, True, 7))
        self.assertEqual(command, ["python3", cd.notice_path(Path(cd.__file__).resolve()), "--dry-run",
                                   "--root", cd.notice_path(checkout.root), "--network", "--sweep-cadence-days", "7"])

    def test_the_root_form_is_reproduced_from_an_unrelated_directory(self):
        checkout = Checkout(self)
        checkout.something_due()
        checkout.script.unlink()
        document = self.notice(checkout)
        command = self.literal_command(checkout, document)
        self.assertEqual(command[2:5], ["--dry-run", "--root", cd.notice_path(checkout.root)])
        again = self.run_elsewhere(checkout, command)
        self.assertEqual((again["due"], again["root"]), (document["due"], str(checkout.root)))

    def test_a_path_under_the_home_directory_is_written_with_a_tilde(self):
        with mock.patch.object(Path, "home", return_value=Path("/h/u")):
            self.assertEqual(cd.notice_path(Path("/h/u/code/stack/scripts/currency_due.py")),
                             "~/code/stack/scripts/currency_due.py")
            self.assertEqual(cd.notice_path(Path("/h/u")), "/h/u")
            self.assertEqual(cd.notice_path(Path("/srv/stack/scripts/currency_due.py")),
                             "/srv/stack/scripts/currency_due.py")
            # A quoted ~ is not expanded by the shell, so a path that needs quoting stays absolute.
            self.assertEqual(cd.notice_path(Path("/h/u/my code/scripts/currency_due.py")),
                             "/h/u/my code/scripts/currency_due.py")
            # The ~ token stays unquoted in the command; a path with a space is quoted and absolute.
            self.assertEqual(cd.join_command(["python3", "~/code/stack/scripts/currency_due.py", "--dry-run"]),
                             "python3 ~/code/stack/scripts/currency_due.py --dry-run")
            self.assertEqual(shlex.split(cd.details_command(Path("/h/u/my code"), False, 30)),
                             ["python3", cd.notice_path(Path(cd.__file__).resolve()), "--dry-run",
                              "--root", "/h/u/my code"])

    def test_a_command_that_leaves_the_counts_no_room_gives_way_to_cat_of_the_due_file(self):
        # A checkout path this long leaves "1 pin behind" no room beside the absolute command, so the line ends
        # with `cat <due-file>`, a short runnable command that prints the document (command and checkout included);
        # nothing cwd-relative is ever printed.
        checkout = Checkout(self, "c" * 110)
        checkout.something_due()
        document = self.notice(checkout)
        self.assertTrue(document["summary_line"].endswith(f"; details: cat {cd.notice_path(checkout.due_file)}"),
                        document["summary_line"])
        self.assertTrue(document["summary_line"].startswith("stack currency: 1 pin behind, 2 stale receipts"))
        self.assertLessEqual(len(document["summary_line"]), 160)
        self.assertNotIn(COMMAND, document["summary_line"])
        command = self.literal_command(checkout, document)
        self.assertEqual(command[:3], ["python3", cd.notice_path(checkout.script), "--dry-run"])
        self.assertEqual(self.run_elsewhere(checkout, command)["due"], document["due"])

    def test_summary_line_takes_the_pointer_only_when_the_counts_would_not_fit(self):
        due = dict.fromkeys(cd.DUE_KEYS, 0)
        due["pins_behind"] = 1
        pointer = "cat ~/.local/state/native-agent-stack/currency-due.json"
        fits = "python3 /checkout/scripts/currency_due.py --dry-run"
        self.assertEqual(cd.summary_line(due, fits, pointers=[pointer]),
                         f"stack currency: 1 pin behind; details: {fits}")
        too_long = "python3 " + "/c" * 60 + "/scripts/currency_due.py --dry-run"
        self.assertEqual(cd.summary_line(due, too_long, pointers=[pointer]),
                         f"stack currency: 1 pin behind; details: {pointer}")
        # A resolved path too long for cat gives way to the symbolic XDG pointer; the line never exceeds 160.
        long_pointer = "cat " + "/s" * 70 + "/currency-due.json"
        line = cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 10 ** 6), too_long, pointers=[long_pointer, cd.XDG_POINTER])
        self.assertTrue(line.endswith(f"; details: {cd.XDG_POINTER}"), line)
        self.assertLessEqual(len(line), 160)
        self.assertEqual(cd.XDG_POINTER, 'cat "$XDG_STATE_HOME"/native-agent-stack/currency-due.json')
        # With nothing runnable that fits, the run fails rather than emit a non-runnable or over-long line.
        with self.assertRaises(cd.CheckError):
            cd.summary_line(due, too_long, pointers=[long_pointer])
        # Nothing due never needs a command.
        self.assertEqual(cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 0), too_long, pointers=[long_pointer]),
                         "stack currency: nothing due")

    def test_a_long_xdg_state_home_gives_the_symbolic_pointer_that_runs_from_anywhere(self):
        # A 140-character XDG_STATE_HOME basename (the review's case) with a long checkout path: the writer exits 0,
        # writes the file, and the line ends with the symbolic pointer, which the literal-command replay runs from
        # an unrelated directory with the variable set (as the session that prints the line has it).
        checkout = Checkout(self, "c" * 110)
        checkout.something_due()
        base = checkout.state.parent / ("s" * 140)
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(base)}):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cd.main(["--root", str(checkout.root), "--now", NOW])
            self.assertEqual(code, 0, stderr.getvalue())
            due_file = base / "native-agent-stack" / "currency-due.json"
            document = json.loads(due_file.read_text(encoding="utf-8"))
            self.assertLessEqual(len(document["summary_line"]), 160)
            self.assertTrue(document["summary_line"].endswith(f"; details: {cd.XDG_POINTER}"),
                            document["summary_line"])
            self.assertTrue(document["summary_line"].startswith("stack currency: 1 pin behind, 2 stale receipts"))
            self.assertEqual(document["root"], str(checkout.root))
            checkout.state = None  # the replay inherits XDG_STATE_HOME instead of naming the long directory
            command = self.literal_command(checkout, document)
            self.assertEqual(self.run_elsewhere(checkout, command)["due"], document["due"])

    def test_a_long_explicit_state_directory_keeps_the_primary_command_when_it_fits(self):
        # A short checkout with a 140-character state-directory basename: the primary command fits, so the
        # notice is written normally and its literal command runs from an unrelated directory.
        checkout = Checkout(self)
        checkout.something_due()
        base = checkout.state.parent / ("s" * 140)
        code, _, stderr = checkout.run("--state-dir", str(base))
        self.assertEqual(code, 0, stderr)
        checkout.state = base
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertTrue(document["summary_line"].endswith(f"; details: {checkout.command()}"),
                        document["summary_line"])
        self.assertEqual(self.reproduced(checkout, document)["due"], document["due"])

    def test_no_runnable_command_at_all_fails_the_due_run_and_still_clears_a_stale_notice(self):
        # A long checkout path with a long explicit state directory: nothing runnable fits the line, so a run with
        # something due fails (exit 2, nothing written) instead of emitting a non-runnable line, while a run with
        # nothing due still removes an obsolete due-file.
        checkout = Checkout(self, "c" * 110)
        base = checkout.state.parent / ("s" * 140)
        base.mkdir(mode=0o700)
        (base / "currency-due.json").write_text('{"earlier": true}\n', encoding="utf-8")
        code, _, stderr = checkout.run("--state-dir", str(base))
        self.assertEqual(code, 0, stderr)
        self.assertFalse((base / "currency-due.json").exists())
        checkout.something_due()
        code, _, stderr = checkout.run("--state-dir", str(base))
        self.assertEqual(code, 2, stderr)
        self.assertIn("no runnable details command fits", stderr)
        self.assertFalse((base / "currency-due.json").exists())

    def test_the_next_step_points_at_what_is_due(self):
        # A skill pin that drifted is not something scripts/adoption_status.py --pinned-versions can report.
        checkout = Checkout(self)
        checkout.set(SKILLS, stdout="{}", output_file=json.dumps(skills_report(("skill-drift",))))
        _, text, _ = checkout.run("--dry-run", "--network")
        self.assertEqual(text.splitlines()[-1], "next: skill pins: blueprints/runtime-workers/skills/README.md")
        checkout = Checkout(self)
        checkout.set(PINNED, pinned_report(mismatched=("codex",)))
        _, text, _ = checkout.run("--dry-run")
        self.assertEqual(text.splitlines()[-1], "next: pins: python3 scripts/adoption_status.py --pinned-versions")

    def test_the_cadence_option_is_bounded_so_the_command_stays_short(self):
        checkout = Checkout(self)
        for value in ("-1", "36501"):
            with self.subTest(value=value):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    cd.main(["--root", str(checkout.root), "--state-dir", str(checkout.state), "--now", NOW,
                             "--sweep-cadence-days", value])
                self.assertEqual(raised.exception.code, 2)
        self.assertEqual(checkout.run("--dry-run", "--sweep-cadence-days", "36500")[0], 0)


class SummaryLineTests(unittest.TestCase):
    def test_the_line_names_only_nonzero_counts_and_the_command(self):
        line = cd.summary_line({"pins_behind": 2, "stale_receipts": 1, "due_layers": 3, "reopen_triggers": 0})
        self.assertEqual(line, f"stack currency: 2 pins behind, 1 stale receipt, 3 layers due; details: {COMMAND}")
        line = cd.summary_line({"pins_behind": 0, "stale_receipts": 0, "due_layers": 0, "reopen_triggers": 0,
                                "host_alerts": 1})
        self.assertEqual(line, f"stack currency: 1 host alert; details: {COMMAND}")
        self.assertEqual(cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 0)), "stack currency: nothing due")

    def test_the_line_stays_within_160_characters_and_keeps_the_command(self):
        line = cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 10 ** 40))
        self.assertLessEqual(len(line), 160)
        self.assertTrue(line.endswith(f"; details: {COMMAND}"))

    def test_the_line_ends_with_the_command_it_is_given_within_160_characters(self):
        command = f"{COMMAND} --network --sweep-cadence-days 36500"
        line = cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 10 ** 40), command)
        self.assertLessEqual(len(line), 160)
        self.assertTrue(line.endswith(f"; details: {command}"))
        due = dict.fromkeys(cd.DUE_KEYS, 0) | {"pins_behind": 1}
        self.assertEqual(cd.summary_line(due, command), f"stack currency: 1 pin behind; details: {command}")

    def test_an_incomplete_check_with_nothing_found_is_not_reported_as_nothing_due(self):
        line = cd.summary_line(dict.fromkeys(cd.DUE_KEYS, 0), complete=False)
        self.assertEqual(line, "stack currency: nothing known due, skill check incomplete")


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


class HostAlertTests(unittest.TestCase):
    """The host's own alerts (wave-2 lifecycle ruling, changes 7 and 8) from synthetic status records and unit states;
    the clock is NOW, 2026-09-30T12:00:00Z."""

    @staticmethod
    def record(success: str | None = "2026-09-30T05:00:00Z", result: str = "ok", exit_code: int = 0,
               attempt: str = "2026-09-30T05:00:00Z") -> dict:
        record = {"last_attempt": {"result": result, "exit_code": exit_code, "time": attempt}}
        if success is not None:
            record["last_success"] = {"snapshot_id": "a1b2c3d4", "time": success}
        return record

    @staticmethod
    def unit(state: str = "active", enabled: str = "enabled", sub: str = "running", result: str = "success") -> dict:
        return {"UnitFileState": enabled, "ActiveState": state, "SubState": sub, "Result": result}

    def document(self, checkout: Checkout) -> dict:
        code, stdout, stderr = checkout.run("--dry-run", "--json")
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout)

    def alerts(self, checkout: Checkout) -> list:
        return [item for item in self.document(checkout)["details"]
                if item["kind"].startswith(("backup_", "restore_check_", "unit_", "dagu_"))]

    def test_no_record_and_no_enabled_unit_is_no_alert(self):
        document = self.document(Checkout(self))
        self.assertEqual(document["due"]["host_alerts"], 0)
        coverage = document["details"][-1]
        self.assertEqual((coverage["host_units"], coverage["backup_record"], coverage["restore_record"]),
                         ("checked", "absent", "absent"))

    def test_a_fresh_backup_and_restore_check_are_no_alert(self):
        checkout = Checkout(self)
        checkout.write_record(cd.BACKUP_RECORD, self.record("2026-09-29T13:00:00Z"))          # 47 h before NOW
        checkout.write_record(cd.RESTORE_RECORD, self.record("2026-09-23T13:00:00Z"))         # 7 days before NOW
        self.assertEqual(self.alerts(checkout), [])

    def test_a_failed_or_partial_backup_is_an_alert_beside_the_last_success_it_keeps(self):
        for result, exit_code in (("failed", 1), ("partial", 3), ("ok", 3)):
            with self.subTest(result=result, exit_code=exit_code):
                checkout = Checkout(self)
                checkout.write_record(cd.BACKUP_RECORD, self.record(result=result, exit_code=exit_code))
                self.assertEqual(self.alerts(checkout), [{"kind": "backup_failed", "result": result,
                                                          "exit_code": exit_code, "time": "2026-09-30T05:00:00Z"}])

    def test_a_backup_older_than_48_hours_or_never_successful_is_overdue(self):
        for success, expected in (("2026-09-28T11:00:00Z", 49), (None, None)):
            with self.subTest(success=success):
                checkout = Checkout(self)
                checkout.write_record(cd.BACKUP_RECORD, self.record(success))
                self.assertEqual(self.alerts(checkout), [{"kind": "backup_overdue", "last_success": success,
                                                          "age_hours": expected, "max_age_hours": 48}])

    def test_a_restore_check_older_than_8_days_or_failed_is_an_alert(self):
        checkout = Checkout(self)
        checkout.write_record(cd.RESTORE_RECORD, self.record("2026-09-21T11:00:00Z", result="failed", exit_code=1))
        self.assertEqual([item["kind"] for item in self.alerts(checkout)],
                         ["restore_check_failed", "restore_check_overdue"])

    def test_an_unreadable_record_is_an_alert_and_not_an_error_of_the_run(self):
        for text, error in (("{not json", "not JSON"), ("[]", "not a JSON object")):
            with self.subTest(text=text):
                checkout = Checkout(self)
                checkout.write_record(cd.BACKUP_RECORD, text)
                self.assertEqual(self.alerts(checkout), [{"kind": "backup_record_unreadable", "error": error}])
        checkout = Checkout(self)
        checkout.write_record(cd.BACKUP_RECORD, {"last_success": {"snapshot_id": "a", "time": "2026-09-30T05:00:00Z"}})
        self.assertEqual(self.alerts(checkout), [{"kind": "backup_record_unreadable", "error": "no last_attempt object"}])

    def test_an_enabled_unit_that_failed_or_hit_its_start_limit_and_an_inactive_dagu_are_alerts(self):
        checkout = Checkout(self)
        checkout.units = {"omniroute.service": self.unit("failed", sub="failed", result="start-limit-hit"),
                          "ollama.service": self.unit("inactive", enabled="disabled", sub="dead"),
                          "ai-memory.service": self.unit(),
                          "ecosystem-otelcol.service": self.unit("activating", sub="auto-restart", result="exit-code"),
                          "dagu.service": self.unit("inactive", sub="dead")}
        self.assertEqual(self.alerts(checkout), [
            {"kind": "unit_not_active", "unit": "omniroute.service", "active_state": "failed", "sub_state": "failed",
             "result": "start-limit-hit"},
            {"kind": "dagu_not_active", "unit": "dagu.service", "active_state": "inactive", "sub_state": "dead",
             "result": "success"}])
        # A unit this host does not enable (Ollama before the GPU handover) and one that is restarting are no alert.

    def test_a_user_manager_that_cannot_be_asked_is_coverage_not_an_alert(self):
        checkout = Checkout(self)
        checkout.units = "no systemctl on this host"
        document = self.document(checkout)
        self.assertEqual(document["due"]["host_alerts"], 0)
        self.assertEqual(document["details"][-1]["host_units"], "no systemctl on this host")

    def test_host_alerts_write_the_notice_and_the_details_name_them(self):
        checkout = Checkout(self)
        checkout.write_record(cd.BACKUP_RECORD, self.record(result="failed", exit_code=1))
        checkout.units = {"dagu.service": self.unit("failed", sub="failed", result="exit-code")}
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertEqual(document["due"]["host_alerts"], 2)
        self.assertTrue(document["summary_line"].startswith("stack currency: 2 host alerts; details: "),
                        document["summary_line"])
        text = cd.render_text(document)
        self.assertIn("  backup: the last attempt ended failed (exit code 1) at 2026-09-30T05:00:00Z", text)
        self.assertIn("  unit: dagu.service is enabled and failed (failed, result exit-code)", text)
        self.assertIn("units: systemctl --user status <unit>", text)
        self.assertIn("backups: dagu history restic-backup", text)

    def test_query_units_reads_the_blocks_of_systemctl_show_and_names_why_it_could_not_ask(self):
        with tempfile.TemporaryDirectory(dir=short_temp_base()) as temporary:
            showing = Path(temporary) / "systemctl"
            showing.write_text("#!/bin/sh\nprintf 'Id=omniroute.service\\nUnitFileState=enabled\\nActiveState=failed\\n"
                               "SubState=failed\\nResult=start-limit-hit\\n\\nId=dagu.service\\nUnitFileState=enabled\\n"
                               "ActiveState=active\\nSubState=running\\nResult=success\\n'\n", encoding="utf-8")
            showing.chmod(0o755)
            states = cd.query_units(("omniroute.service", "dagu.service"), str(showing))
            self.assertEqual(states["omniroute.service"]["Result"], "start-limit-hit")
            self.assertEqual(states["dagu.service"]["ActiveState"], "active")
            refusing = Path(temporary) / "refusing"
            refusing.write_text("#!/bin/sh\necho 'Failed to connect to bus: No medium found' >&2\nexit 1\n",
                                encoding="utf-8")
            refusing.chmod(0o755)
            self.assertEqual(cd.query_units(("dagu.service",), str(refusing)),
                             "systemctl --user show exited 1: Failed to connect to bus: No medium found")
            self.assertEqual(cd.query_units(("dagu.service",), str(Path(temporary) / "absent")),
                             "no systemctl on this host")


class SurfaceWatchTests(unittest.TestCase):
    """The sixth count: scripts/upstream_surface_watch.py's latest.json in the state directory's surface-watch/,
    read offline, counted only while its data is at most three days old (synthetic reports in the watch's shape, not
    watch output; tests/test_upstream_surface_watch.py FreshnessTests feeds real watch output to surface_findings)."""

    KEYS = ["claude:setting:newSetting", "claude:env:CLAUDE_CODE_NEW", "codex:feature:brand_new"]
    MALFORMED_BYTES = {"huge integer": (b'{"integer":' + b"9" * 5000 + b"}", {"error": "not JSON"}),
                       "lone surrogate": (b'{"value":"\xed\xa0\x80"}', {"error": "unreadable (UnicodeDecodeError)"}),
                       "NUL": (b'{"value":"\x00"}', {"error": "not JSON"}),
                       "BOM": (b"\xef\xbb\xbf{}", {"error": "not JSON"})}

    def test_bounded_malformed_json_inputs_are_unreadable_records(self):
        """Synthetic fixtures, not upstream tests: integer limits and malformed UTF-8/JSON cannot escape read_record."""
        for label, (raw, expected) in self.MALFORMED_BYTES.items():
            with self.subTest(report=label):
                checkout = Checkout(self)
                self.report(checkout)
                path = checkout.state / cd.SURFACE_DIR / cd.SURFACE_FILE
                self.assertLess(len(raw), cd.RECORD_MAX_BYTES)
                path.write_bytes(raw)
                self.assertEqual(cd.read_record(path), expected)

    def test_bounded_malformed_reports_do_not_crash_currency_or_clear_the_notice(self):
        """Local integration check, not an upstream test: every malformed report keeps known findings and exits zero."""
        for label, (raw, _) in self.MALFORMED_BYTES.items():
            with self.subTest(report=label):
                checkout = Checkout(self)
                self.report(checkout)
                checkout.due_file.write_bytes(b'{"earlier": true}\n')
                before = checkout.due_file.read_bytes()
                (checkout.state / cd.SURFACE_DIR / cd.SURFACE_FILE).write_bytes(raw)
                code, stdout, stderr = checkout.run()
                self.assertEqual(code, 0, stderr)
                self.assertEqual(checkout.due_file.read_bytes(), before)
                self.assertIn("surface watch unreadable", stdout)
                self.assertLessEqual(len(stdout.split(" (kept ", 1)[0]), 160)

    def test_a_path_encoding_error_is_an_unreadable_record(self):
        """Synthetic fixture, not an upstream test: a UnicodeError during file access is an unreadable record."""
        checkout = Checkout(self)
        self.assertEqual(cd.read_record(checkout.state / "\ud800"), {"error": "unreadable (UnicodeEncodeError)"})

    @staticmethod
    def source(name: str, origin: str, fetched_utc: str, cross_check: bool = False) -> dict:
        return {"source": name, "url": f"https://example.com/{name}", "version": None, "fetched_utc": fetched_utc,
                "sha256": "0" * 64, "bytes": 1, "origin": origin, "required": not cross_check,
                "cross_check": cross_check}

    def report(self, checkout: Checkout, generated_at: str = "2026-09-29T12:00:00Z", unreviewed=None,
               raw: str | None = None, sources=None, run_at: str | None = None) -> None:
        path = checkout.state / "surface-watch" / "latest.json"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if sources is None:
            sources = [self.source("claude-env-vars-page", "network", generated_at)]
        document = {"schema_version": 1, "generated_at": generated_at, "run_at": run_at or generated_at, "new": [],
                    "removed": [], "stage_changed": [], "unreviewed": self.KEYS if unreviewed is None else unreviewed,
                    "coverage": {"mode": "network", "from_cache": [], "sources": sources},
                    "summary_line": "surface watch: 3 unreviewed of 3 new; details: python3 x --dry-run"}
        path.write_text(raw if raw is not None else json.dumps(document), encoding="utf-8")

    def document(self, checkout: Checkout) -> dict:
        code, stdout, stderr = checkout.run("--dry-run", "--json")
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout)

    def test_no_watch_report_is_a_coverage_note_and_no_count(self):
        checkout = Checkout(self)
        document = self.document(checkout)
        self.assertEqual(list(document["due"]), list(cd.DUE_KEYS))
        coverage = document["details"][-1]
        self.assertEqual((coverage["surface_watch"], coverage["surface_watch_reason"]),
                         ("surface watch not run", "no latest.json"))
        _, text, _ = checkout.run("--dry-run")
        self.assertIn("surface watch not run (no latest.json)", text)

    def test_a_lost_report_after_a_watch_run_keeps_the_previous_findings(self):
        """Local integration check, not an upstream test: deleting latest.json preserves the earlier notice."""
        checkout = Checkout(self)
        self.report(checkout)
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        before = checkout.due_file.read_bytes()
        report = checkout.state / cd.SURFACE_DIR / cd.SURFACE_FILE
        report.unlink()
        self.assertEqual(stat.S_IMODE(report.parent.stat().st_mode), 0o700)
        code, stdout, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        self.assertTrue(checkout.due_file.exists(), stdout)
        self.assertEqual(checkout.due_file.read_bytes(), before)
        line = stdout.split(" (kept ", 1)[0]
        self.assertEqual(line, f"stack currency: nothing known due, surface watch stale; details: {checkout.command()}")
        self.assertLessEqual(len(line), 160)
        document = self.document(checkout)
        self.assertEqual(document["details"][-1]["surface_watch"], "surface watch stale")

    def test_an_observed_watch_without_a_usable_report_writes_no_empty_notice(self):
        """Synthetic fixtures, not upstream tests: missing, unreadable and non-regular reports are gaps."""
        for label, contents in (("missing", None), ("unreadable", b"{not json"), ("directory", None),
                                ("fifo", None), ("dangling symlink", None)):
            with self.subTest(report=label):
                checkout = Checkout(self)
                report = checkout.state / cd.SURFACE_DIR / cd.SURFACE_FILE
                report.parent.mkdir(mode=0o700, parents=True)
                if contents is not None:
                    report.write_bytes(contents)
                elif label == "directory":
                    report.mkdir()
                elif label == "fifo":
                    os.mkfifo(report)
                elif label == "dangling symlink":
                    report.symlink_to(report.parent / "lost.json")
                code, stdout, stderr = checkout.run()
                self.assertEqual(code, 0, stderr)
                self.assertFalse(checkout.due_file.exists())
                self.assertTrue(stdout.startswith("stack currency: nothing known due, surface watch "), stdout)
                self.assertIn("(no due-file)", stdout)
                line = stdout.split(" (no due-file)", 1)[0]
                self.assertTrue(line.endswith(f"; details: {checkout.command()}"), line)
                self.assertLessEqual(len(line), 160)

    def test_a_fresh_report_adds_the_sixth_count_and_writes_the_notice(self):
        checkout = Checkout(self)
        self.report(checkout)
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertEqual(document["due"], {"pins_behind": 0, "stale_receipts": 0, "due_layers": 0,
                                           "reopen_triggers": 0, "host_alerts": 0, "surface_unreviewed": 3})
        line = document["summary_line"]
        self.assertTrue(line.startswith("stack currency: 3 unreviewed upstream switches; details: "), line)
        self.assertTrue(line.endswith(f"; details: {checkout.command()}"), line)
        self.assertLessEqual(len(line), 160)
        found = next(item for item in document["details"] if item["kind"] == "surface_unreviewed")
        self.assertEqual((found["count"], found["keys"], found["generated_at"]), (3, self.KEYS, "2026-09-29T12:00:00Z"))
        self.assertEqual(document["details"][-1]["surface_watch"], "fresh")
        _, text, _ = checkout.run("--dry-run")
        self.assertIn("upstream switches: 3 new without a disposition (watch of 2026-09-29T12:00:00Z)", text)
        self.assertIn("upstream switches: python3 scripts/upstream_surface_watch.py --dry-run", text)

    def test_the_count_joins_the_others_in_the_line(self):
        checkout = Checkout(self)
        checkout.something_due()
        self.report(checkout)
        line = self.document(checkout)["summary_line"]
        self.assertTrue(line.startswith("stack currency: 1 pin behind, 2 stale receipts, 1 layer"), line)
        self.assertLessEqual(len(line), 160)

    def test_the_report_counts_for_three_days_and_no_longer(self):
        cases = {"2026-09-27T12:00:00Z": 3, "2026-09-27T11:59:59Z": None, "2026-09-30T12:59:00Z": 3,
                 "2026-09-30T13:00:01Z": None}
        for generated_at, expected in cases.items():
            with self.subTest(generated_at=generated_at):
                checkout = Checkout(self)
                self.report(checkout, generated_at)
                document = self.document(checkout)
                self.assertEqual(document["due"].get("surface_unreviewed"), expected)
                coverage = document["details"][-1]
                if expected is None:
                    self.assertEqual(coverage["surface_watch"], "surface watch stale")
                    self.assertIn(generated_at, coverage["surface_watch_reason"])

    def test_a_report_is_aged_by_its_oldest_cached_source_not_by_generated_at_alone(self):
        # H1: a --network run whose fetch fell back to the cache is as old as that cache. The watch writes
        # generated_at so; this report says otherwise, and the per-source records still age it. A cross-check from
        # the cache is report-only and does not.
        old, fresh = "2026-09-26T12:00:00Z", "2026-09-30T06:00:00Z"
        cases = {
            "a required source from the cache": ([self.source("claude-env-vars-page", "network", fresh),
                                                  self.source("claude-mods-overview-page",
                                                              "cache; the network fetch failed: OSError: x", old)],
                                                 None),
            "an offline replay": ([self.source("claude-env-vars-page", "cache", old)], None),
            "a cross-check from the cache": ([self.source("claude-env-vars-page", "network", fresh),
                                              self.source("xc-chenrui-lifecycle", "cache", old, cross_check=True)],
                                             3),
        }
        for label, (sources, expected) in cases.items():
            with self.subTest(case=label):
                checkout = Checkout(self)
                self.report(checkout, fresh, sources=sources)
                document = self.document(checkout)
                self.assertEqual(document["due"].get("surface_unreviewed"), expected)
                coverage = document["details"][-1]
                if expected is None:
                    self.assertEqual(coverage["surface_watch"], "surface watch stale")
                    self.assertIn(f"data of {old} is more than 3 days old", coverage["surface_watch_reason"])

    def test_an_unreadable_report_is_an_incomplete_check_never_an_error(self):
        cases = {"not JSON": "{not json", "an array": "[]",
                 "no unreviewed list": json.dumps({"generated_at": NOW, "unreviewed": "x"}),
                 "keys that are not strings": json.dumps({"generated_at": NOW, "unreviewed": [1]}),
                 "no time": json.dumps({"generated_at": "yesterday", "unreviewed": []}),
                 "no per-source records": json.dumps({"generated_at": NOW, "unreviewed": []}),
                 "a cached source without a time": json.dumps({"generated_at": NOW, "unreviewed": [], "coverage": {
                     "sources": [{"source": "s", "origin": "cache", "fetched_utc": None}]}}),
                 "nested too deeply": "[" * 200000 + "]" * 200000}
        for label, raw in cases.items():
            with self.subTest(report=label):
                checkout = Checkout(self)
                self.report(checkout, raw=raw)
                code, stdout, stderr = checkout.run()
                self.assertEqual(code, 0, stderr)
                self.assertFalse(checkout.due_file.exists())
                self.assertIn("(no due-file)", stdout)
                document = self.document(checkout)
                self.assertNotIn("surface_unreviewed", document["due"])
                self.assertEqual(document["details"][-1]["surface_watch"], "surface watch output unreadable")
                self.assertEqual(document["summary_line"], "stack currency: nothing known due, surface watch "
                                                           f"unreadable; details: {checkout.command()}")

    def test_a_stale_or_unreadable_report_keeps_the_earlier_due_file_and_never_says_nothing_due(self):
        # M4: a report that exists but could not answer is a check that could not answer, as an incomplete skill
        # check is: the earlier notice stays byte-identical and the line names the gap with a runnable command.
        for label, change in (("stale", lambda c: self.report(c, "2026-09-26T12:00:00Z")),
                              ("future-dated", lambda c: self.report(c, "2026-09-30T14:00:00Z")),
                              ("unreadable", lambda c: self.report(c, raw="{not json"))):
            with self.subTest(report=label):
                checkout = Checkout(self)
                change(checkout)
                checkout.state.mkdir(parents=True, exist_ok=True)
                checkout.due_file.write_text('{"earlier": true}\n', encoding="utf-8")
                before = checkout.due_file.read_bytes()
                code, stdout, stderr = checkout.run()
                self.assertEqual(code, 0, stderr)
                self.assertEqual(checkout.due_file.read_bytes(), before)
                self.assertIn(f"(kept {checkout.due_file})", stdout)
                line = stdout.split(" (kept ", 1)[0]
                self.assertTrue(line.startswith("stack currency: nothing known due, surface watch "), line)
                self.assertNotIn("nothing due", line.replace("nothing known due", ""))
                self.assertTrue(line.endswith(f"; details: {checkout.command()}"), line)
                self.assertLessEqual(len(line), 160)
                _, text, _ = checkout.run("--dry-run")
                self.assertIn("surface watch: journalctl --user -u upstream-surface-watch.service", text)

    def test_a_missing_report_stays_silent_and_nothing_due_still_clears_the_notice(self):
        # No latest.json: the watch unit may not be installed on this host, so it is only the coverage note.
        checkout = Checkout(self)
        checkout.state.mkdir(parents=True, exist_ok=True)
        checkout.due_file.write_text('{"earlier": true}\n', encoding="utf-8")
        code, stdout, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        self.assertFalse(checkout.due_file.exists())
        self.assertTrue(stdout.startswith("stack currency: nothing due (removed "), stdout)

    def test_a_stale_report_beside_other_counts_writes_them_and_names_the_gap(self):
        checkout = Checkout(self)
        checkout.something_due()
        self.report(checkout, "2026-09-26T12:00:00Z")
        code, stdout, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        self.assertIn("; surface watch stale", stdout)
        document = json.loads(checkout.due_file.read_text(encoding="utf-8"))
        self.assertNotIn("surface_unreviewed", document["due"])
        self.assertTrue(document["summary_line"].startswith("stack currency: 1 pin behind"), document["summary_line"])
        self.assertEqual(document["details"][-1]["surface_watch"], "surface watch stale")

    def test_the_gap_line_keeps_the_skill_only_form_and_its_limit(self):
        zero = {key: 0 for key in cd.DUE_KEYS}
        command = "python3 ~/code/native-agent-stack-live/scripts/currency_due.py --dry-run --network"
        self.assertEqual(cd.summary_line(zero, command, False), "stack currency: nothing known due, skill check "
                                                                 "incomplete")
        self.assertEqual(cd.summary_line(zero, command, True, [], ("surface watch stale",)),
                         f"stack currency: nothing known due, surface watch stale; details: {command}")
        short = "python3 ~/live/scripts/currency_due.py --dry-run --network"
        self.assertEqual(cd.summary_line(zero, short, False, [], ("surface watch stale",)),
                         "stack currency: nothing known due, skill check incomplete, surface watch stale; details: "
                         f"{short}")
        # Both gaps and this command exceed 160 characters: the line keeps the gaps and drops the command.
        self.assertEqual(cd.summary_line(zero, command, False, [], ("surface watch stale",)),
                         "stack currency: nothing known due, skill check incomplete, surface watch stale")
        long_line = cd.summary_line(zero, "python3 " + "z" * 150 + " --dry-run", True, ["cat /x"],
                                    ("surface watch stale",))
        self.assertEqual(long_line, "stack currency: nothing known due, surface watch stale")

    def test_read_record_is_bounded_and_never_raises(self):
        # L3: deep nesting (RecursionError in the json module), an oversized file, a directory and a FIFO (whose read
        # would block) are each an unreadable record, never a traceback.
        with tempfile.TemporaryDirectory(dir=short_temp_base()) as scratch:
            base = Path(scratch)
            deep = base / "deep.json"
            deep.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
            self.assertEqual(cd.read_record(deep), {"error": "not JSON"})
            big = base / "big.json"
            big.write_bytes(b" " * (cd.RECORD_MAX_BYTES + 1))
            self.assertEqual(cd.read_record(big), {"error": f"larger than {cd.RECORD_MAX_BYTES} bytes"})
            self.assertEqual(cd.read_record(base), {"error": "not a regular file"})
            fifo = base / "fifo"
            os.mkfifo(fifo)
            self.assertEqual(cd.read_record(fifo), {"error": "not a regular file"})
            self.assertIsNone(cd.read_record(base / "absent.json"))
            self.assertEqual(cd.read_record(base / "absent.json" / "below"), None)

    def test_a_fresh_report_with_nothing_unreviewed_is_zero_and_clears_the_notice(self):
        checkout = Checkout(self)
        self.report(checkout, unreviewed=[])
        checkout.due_file.write_text('{"earlier": true}\n', encoding="utf-8")
        code, _, stderr = checkout.run()
        self.assertEqual(code, 0, stderr)
        self.assertFalse(checkout.due_file.exists())
        self.assertEqual(self.document(checkout)["due"]["surface_unreviewed"], 0)

    def test_the_report_is_read_offline(self):
        import socket

        def refuse(*args, **kwargs):
            raise AssertionError("currency_due.py opened a socket")

        checkout = Checkout(self)
        self.report(checkout)
        with mock.patch.object(socket, "socket", side_effect=refuse), \
                mock.patch.object(socket, "create_connection", side_effect=refuse):
            document = self.document(checkout)
        self.assertEqual(document["due"]["surface_unreviewed"], 3)

    def test_a_direct_aggregate_without_a_state_directory_checks_nothing(self):
        document = cd.aggregate(AggregateShapeTests.reports(), NOW_DATETIME, NOW, 30)
        self.assertNotIn("surface_unreviewed", document["due"])
        self.assertIsNone(document["details"][-1]["surface_watch"])

    def test_the_line_keeps_its_limit_with_all_six_counts(self):
        due = {key: 9999 for key in cd.COUNT_KEYS}
        line = cd.summary_line(due, "python3 ~/code/native-agent-stack-live/scripts/currency_due.py --dry-run")
        self.assertLessEqual(len(line), 160)
        self.assertTrue(line.endswith("; details: python3 ~/code/native-agent-stack-live/scripts/currency_due.py "
                                      "--dry-run"))


class ThisCheckoutTests(unittest.TestCase):
    def test_the_real_checks_run_dry_and_write_nothing(self):
        # The five-second budget is measured on the workstation by the acceptance command; this bound only
        # catches a pathological slowdown on slower runners.
        with tempfile.TemporaryDirectory(dir=short_temp_base()) as temporary:
            state = Path(temporary) / "state"
            started = time.monotonic()
            result = subprocess.run([sys.executable, str(ROOT / "scripts/currency_due.py"), "--dry-run", "--json",
                                     "--state-dir", str(state)], capture_output=True, text=True, timeout=600,
                                    cwd=ROOT, stdin=subprocess.DEVNULL, check=False)
            elapsed = time.monotonic() - started
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            document = json.loads(result.stdout)
            self.assertEqual(list(document), ["generated_at", "root", "due", "summary_line", "details_command",
                                          "details"])
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

    def test_the_command_in_the_notice_names_exactly_the_flags_the_service_passes(self):
        # ExecStart is "<interpreter> <script> <flags>"; a run with those flags must end its notice with the
        # command that runs the details with the same flags, so that the notice can be reproduced.
        execstart = next(line for line in self.service if line.startswith("ExecStart="))
        flags = shlex.split(execstart.removeprefix("ExecStart="))[2:]
        checkout = Checkout(self)
        checkout.something_due()
        code, _, stderr = checkout.run(*flags)
        self.assertEqual(code, 0, stderr)
        summary = json.loads(checkout.due_file.read_text(encoding="utf-8"))["summary_line"]
        self.assertEqual(shlex.split(summary.split("; details: ", 1)[1])[2:], ["--dry-run", *flags])

    def test_the_service_runs_the_surface_watch_first_and_never_waits_on_its_success(self):
        # Wants= is weak and After= only orders (systemd.unit(5)); a hard dependency would let a failed watch block
        # the currency run.
        self.assertIn("Wants=upstream-surface-watch.service", self.service)
        self.assertIn("After=upstream-surface-watch.service", self.service)
        directives = [line for line in self.service if line and not line.startswith("#")]
        hard = ("Requires=", "Requisite=", "BindsTo=", "PartOf=", "Upholds=")
        self.assertFalse([line for line in directives if line.startswith(hard)])
        self.assertLess(directives.index("After=upstream-surface-watch.service"), directives.index("[Service]"))

    def test_the_surface_watch_is_a_guarded_networked_oneshot_that_only_the_currency_service_starts(self):
        watch = (SYSTEMD_DIR / "upstream-surface-watch.service").read_text(encoding="utf-8").splitlines()
        for setting in ("Type=oneshot", "UMask=0077", "NoNewPrivileges=true", "Environment=PYTHONDONTWRITEBYTECODE=1",
                        "ExecStart=/usr/bin/python3 @REPOSITORY@/scripts/upstream_surface_watch.py --network"):
            self.assertIn(setting, watch)
        self.assertNotIn("[Install]", watch)
        directives = [line for line in watch if line and not line.startswith("#")]
        self.assertTrue(any(line.startswith("TimeoutStartSec=") for line in directives))
        search_path = next(line for line in directives if line.startswith("Environment=PATH="))
        self.assertIn("%h/.local/share/codex-ecosystem/bin", search_path)  # gh and codex resolve through PATH
        self.assertTrue((ROOT / "scripts/upstream_surface_watch.py").is_file())
        # The watch writes the directory this script reads.
        from scripts import upstream_surface_watch as usw
        self.assertEqual(usw.default_state_dir({"HOME": "/h"}), cd.default_state_dir({"HOME": "/h"}) / cd.SURFACE_DIR)
        self.assertEqual(usw.LATEST_FILE, cd.SURFACE_FILE)

    def test_the_timer_runs_daily_catches_up_and_spreads_its_start(self):
        for setting in ("OnCalendar=daily", "Persistent=true", "RandomizedDelaySec=15m",
                        "Unit=stack-currency.service", "WantedBy=timers.target"):
            self.assertIn(setting, self.timer)


if __name__ == "__main__":
    unittest.main()
