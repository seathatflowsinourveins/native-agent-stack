"""Draft-contract checks for the Gate B criterion: local structural validation, not a model run.

Reference seam: tests/test_gpt6_lane_compression_ab_preregistration.py at 73fc873e (#431) and
tests/test_compaction_window_ab_preregistration.py at 452f7b14 (#416). The checks cover the honest-draft
flags, the section order, agreement of the prose and the JSON on every load-bearing value, the absence of any
result or seal, a harness for every arm, a disposition for every review finding, and every `path:line` citation
against the pinned main commit (the file exists there, and each cited range holds its recorded needle).
"""

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/gate-b-gpt6-route"
PINNED_MAIN = "11648f9a9d900b285866510ba1be4fcdfb58295b"
SECTIONS = [
    "Scope and the decision gated",
    "Arms, each with its harness, pins and what it can run today",
    "Task set",
    "Metrics and usage accounting (counted once)",
    "Pass rule",
    "Statistics",
    "Owner and roles",
    "Freeze and amendment procedure",
    "Budget and capacity",
    "What each consumer does with each outcome",
    "Alternatives considered, and the comparison that would overturn this",
    "User decisions required (numbered, each with a recommended default)",
    "Sources (pins, URLs, file:line)",
    "Decisions taken in the repair",
    "Repair-round dispositions",
    "Appendix A: sizing and power script",
]
# Every finding of the two refuters that needs a disposition (refute:method confirmed or unverified items and the
# CLAIM-3 gap; refute:citations refuted, unverified and the stale F23), plus the gaps this repair found.
FINDINGS = (
    {f"CLAIM-{i}" for i in range(1, 7)}
    | {"F-IDENT", "F-FPRINT", "F-GUARD", "F-CWD", "F-SEARCH", "F-D2", "F-UNSEALED", "F-E1", "F-SCORER",
       "F-LOCALCODE", "F-TIMEBOX", "F-INFORM", "F-CITE-ENV", "F-SCHEMA-BYTES", "F-ARGV-LIST", "F-TIMEOUT",
       "F-BLOCK", "F-GATEA", "GAP"}
    | {f"F{i:02d}" for i in range(1, 24)}
    | {f"U{i:02d}" for i in range(1, 10)}
    | {"R-CALIB", "R-CACHEWRITE", "R-ROLLOUT-SCOPE", "R-CONV-RECORD"}
)
ACTIONS = {"fixed", "reworded", "declined", "user-decision"}
OUTCOMES = {"void", "incomplete", "stage0_native", "ni", "inferior", "inconclusive", "unpowered", "time_box"}
CITATION = re.compile(
    r"(?<![\w@:/.-])((?:docs|tools|scripts|blueprints|evidence|adoption|catalogs|manifests|tests|\.github)/"
    r"[\w./-]*\w|AGENTS\.md):(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)")


def load():
    data = json.loads((BLUEPRINT / "preregistration.json").read_text(encoding="utf-8"))
    prose = (BLUEPRINT / "PREREGISTRATION.md").read_text(encoding="utf-8")
    return data, prose


def section(prose, title):
    match = re.search(r"^## " + re.escape(title) + r"\n(.*?)(?=^## |\Z)", prose, re.M | re.S)
    if match is None:
        raise AssertionError(f"section {title!r} missing")
    return match.group(1)


def table_rows(text, key_pattern=r"`([^`]+)`"):
    """Rows of the Markdown tables in text whose first cell matches key_pattern: {key: [cells...]}."""
    rows = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = re.fullmatch(key_pattern, cells[0])
        if match:
            rows[match.group(1)] = cells[1:]
    return rows


def literal(cell):
    return json.loads(cell.strip("`"))


def ranges(spec):
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        out.append((int(lo), int(hi or lo)))
    return out


def normal(text):
    return " ".join(text.split())


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


class GateBPreregistrationTests(unittest.TestCase):
    def test_draft_contract(self):
        # Fail first at the public document boundary, before either file exists.
        self.assertTrue((BLUEPRINT / "preregistration.json").is_file(), "preregistration.json does not exist yet")
        self.assertTrue((BLUEPRINT / "PREREGISTRATION.md").is_file(), "PREREGISTRATION.md does not exist yet")
        data, prose = load()
        self.assertEqual(data["status"], "DRAFT")
        self.assertIs(data["frozen"], False)
        self.assertIs(data["run_started"], False)
        self.assertIs(data["execution_authorized"], False)
        self.assertIsNone(data["results"])
        self.assertEqual(data["lane"], "lane:foundation")
        self.assertEqual(data["pinned_main"], PINNED_MAIN)
        self.assertIn("**Status: DRAFT.** Not frozen, not run, and execution is not authorized.", prose[:600])
        self.assertIn(PINNED_MAIN[:8], prose)

    def test_no_result_seal_or_admission_is_recorded(self):
        data, _ = load()
        sealing = data["sealing"]
        for key in ("sealed_at", "execution_revision", "sealing_amendment", "hash_table", "fingerprint_readback",
                    "sizing_amendment", "seal_author"):
            self.assertIsNone(sealing[key], key)
        self.assertEqual(data["amendments"]["log"], [])
        self.assertEqual(data["statistics"]["planning_results"]["kind"], "planning simulation, not a result")
        self.assertIsNone(data["statistics"]["sizing"]["selected_n"])
        self.assertIsNone(data["statistics"]["sizing"]["selected_alpha_boot"])
        self.assertEqual(data["gated_decisions"]["D2"]["this_cohort"], "pending")
        self.assertIsNone(data["tasks"]["stageC"]["frozen_row"])
        for decision in data["user_decisions"]:
            self.assertIsNone(decision["recorded"], decision["number"])

    def test_section_order(self):
        data, prose = load()
        headings = re.findall(r"^## (.+)$", prose, re.M)
        self.assertEqual(headings, SECTIONS)
        self.assertEqual(data["sections"], SECTIONS)

    def test_every_arm_names_a_harness_and_agrees(self):
        data, prose = load()
        arms = {arm["id"]: arm for arm in data["arms"]}
        self.assertEqual(set(arms), {"A", "B", "C"})
        rows = table_rows(section(prose, SECTIONS[1]))
        fields = ("harness", "model", "provider", "base_url", "effort", "codex_home", "working_dir",
                  "skip_git_repo_check")
        for arm_id, arm in arms.items():
            self.assertTrue(arm["harness"].strip(), arm_id)
            self.assertTrue(arm["harness_class"] in {"upstream runner with local integration",
                                                     "recipe-local integration"}, arm_id)
            self.assertEqual(rows[arm_id], [arm[field] for field in fields], arm_id)
        self.assertEqual(arms["A"]["model"], "gpt-6-astra")
        self.assertEqual(arms["B"]["model"], "cx/gpt-6-astra")
        self.assertEqual(arms["B"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(arms["A"]["skip_git_repo_check"], "true")
        self.assertEqual(arms["B"]["skip_git_repo_check"], "true")
        self.assertIn("--ignore-user-config", arms["A"]["launcher_inserts"])
        self.assertIn("--profile stack-worker", arms["B"]["launcher_inserts"])
        self.assertIs(arms["C"]["decides_d2_this_cohort"], False)

    def test_frozen_values_agree(self):
        data, prose = load()
        rows = table_rows(section(prose, "Statistics"))
        frozen = data["frozen_values"]
        self.assertEqual(set(rows), set(frozen))
        for key, cells in rows.items():
            self.assertEqual(literal(cells[0]), frozen[key], key)
        stats = data["statistics"]
        self.assertEqual(stats["alpha"], frozen["alpha"])
        self.assertEqual(stats["delta"]["default"], frozen["delta_default"])
        self.assertEqual(stats["delta"]["alternative"], frozen["delta_alternative"])
        self.assertEqual(stats["step"], frozen["step"])
        self.assertEqual(stats["exact_fallback"]["switch_nonzero"], frozen["switch_nonzero"])
        self.assertEqual(stats["paired_net_test"]["n_resamples"], frozen["bootstrap_resamples"])
        self.assertEqual(stats["paired_net_test"]["seed"], frozen["bootstrap_seed"])
        self.assertEqual(stats["sizing"]["n_grid"], frozen["n_grid"])
        self.assertEqual(stats["sizing"]["alpha_boot_grid"], frozen["alpha_boot_grid"])
        self.assertEqual(stats["sizing"]["target_power"], frozen["target_power"])
        self.assertEqual(stats["sizing"]["required_laws"], frozen["required_laws"])
        self.assertEqual(stats["sizing"]["calibration_bound"], frozen["calibration_bound"])
        planning = stats["planning_results"]
        self.assertEqual(planning["delta_0.05"]["n"], frozen["planning_n_delta_005"])
        self.assertEqual(planning["delta_0.05"]["alpha_boot"], frozen["planning_alpha_boot_delta_005"])
        self.assertEqual(planning["delta_0.10"]["n"], frozen["planning_n_delta_010"])
        self.assertEqual(planning["delta_0.10"]["alpha_boot"], frozen["planning_alpha_boot_delta_010"])
        self.assertEqual(data["tasks"]["stage0"]["model_runs"], frozen["stage0_model_runs"])
        self.assertEqual(data["tasks"]["stage0"]["repeats_K"], frozen["stage0_repeats"])
        self.assertEqual(data["tasks"]["pilot"]["packets"], frozen["pilot_packets"])
        self.assertEqual(data["tasks"]["pilot"]["calibration_band"], frozen["pilot_band"])
        self.assertEqual(data["pass_rule"]["informative_band"], frozen["informative_band"])
        self.assertEqual(data["pass_rule"]["time_box"]["days_after_seal"], frozen["time_box_days"])
        self.assertEqual(data["harness"]["evaluate_options"]["timeoutMs"], frozen["timeout_ms"])
        self.assertEqual(data["pass_rule"]["block"]["stage1_packets_per_block"], frozen["block_packets"])

    def test_decision_table_is_total_and_agrees(self):
        data, prose = load()
        table = {row["outcome"]: row for row in data["pass_rule"]["decision_table"]}
        self.assertEqual(set(table), OUTCOMES)
        columns = data["consumer_actions"]["columns"]
        self.assertEqual([c["id"] for c in columns],
                         ["omniroute", "native_decided", "native_inconclusive", "native_untested", "open"])
        column_ids = {c["id"] for c in columns}
        md_rows = table_rows(section(prose, "Pass rule"))
        for outcome, row in table.items():
            self.assertIn(row["column"], column_ids, outcome)
            self.assertEqual(md_rows[outcome][2:5], [row["d1"], row["gate_b"], row["convergence"]], outcome)
            self.assertIn(row["d1"].split(" ")[0], {"native", "omniroute", "unchanged"}, outcome)
        passed = sorted(o for o, row in table.items() if row["gate_b"].startswith("passed"))
        self.assertEqual(passed, sorted(data["gate_b_passed"]["passed_outcomes"]))
        self.assertEqual(sorted(o for o, row in table.items() if row["gate_b"] == "open"),
                         sorted(data["gate_b_passed"]["open_outcomes"]))
        self.assertEqual({table[o]["column"] for o in ("void", "incomplete")}, {"open"})
        consumers = data["consumer_actions"]["rows"]
        self.assertGreaterEqual(len(consumers), 10)
        md_consumers = table_rows(section(prose, "What each consumer does with each outcome"),
                                  key_pattern=r"`([^`]+)`.*")
        self.assertEqual(set(md_consumers), {consumer["id"] for consumer in consumers})
        for consumer in consumers:
            self.assertEqual(set(consumer["actions"]), column_ids, consumer["id"])
            for column in column_ids:
                self.assertTrue(consumer["actions"][column].strip(), (consumer["id"], column))
            self.assertEqual(len(md_consumers[consumer["id"]]), len(columns), consumer["id"])
            self.assertTrue(all(cell for cell in md_consumers[consumer["id"]]), consumer["id"])

    def test_user_decisions_agree(self):
        data, prose = load()
        decisions = data["user_decisions"]
        self.assertEqual([d["number"] for d in decisions], list(range(1, len(decisions) + 1)))
        rows = table_rows(section(prose, SECTIONS[11]), key_pattern=r"(\d+)")
        self.assertEqual(set(rows), {str(d["number"]) for d in decisions})
        for decision in decisions:
            self.assertIn(decision["decider"], {"owner", "user"})
            self.assertTrue(decision["default"].strip())
            self.assertEqual(rows[str(decision["number"])][1], decision["decider"], decision["number"])
        owner = next(d for d in decisions if d["id"] == "accountable_owner")
        self.assertEqual(owner["decider"], "user")
        self.assertIn("native-agent-stack-2d", owner["default"])
        self.assertIn("ecosystem-roadmap-2026", owner["alternative"])

    def test_every_review_finding_has_a_disposition(self):
        data, prose = load()
        rows = data["repair_round"]["dispositions"]
        self.assertEqual({row["id"] for row in rows}, FINDINGS)
        self.assertEqual(len(rows), len(FINDINGS))
        md_rows = table_rows(section(prose, "Repair-round dispositions"))
        for row in rows:
            self.assertIn(row["action"], ACTIONS, row["id"])
            self.assertTrue(row["where"].strip() and row["note"].strip(), row["id"])
            self.assertEqual(md_rows[row["id"]][0], row["action"], row["id"])
            if row["action"] == "user-decision":
                self.assertIn(row["user_decision"], {d["number"] for d in data["user_decisions"]}, row["id"])
        taken = data["repair_round"]["decisions_taken"]
        self.assertTrue(taken)
        taken_md = section(prose, "Decisions taken in the repair")
        for item in taken:
            self.assertIn(f"**{item['id']}.**", taken_md)

    def test_appendix_script_and_output_match_their_hashes(self):
        data, prose = load()
        appendix = section(prose, SECTIONS[-1])
        blocks = re.findall(r"```(\w*)\n(.*?)```", appendix, re.S)
        self.assertEqual([kind for kind, _ in blocks], ["python", "text"])
        stats = data["statistics"]
        self.assertEqual(hashlib.sha256(blocks[0][1].encode("utf-8")).hexdigest(), stats["appendix_script_sha256"])
        self.assertEqual(hashlib.sha256(blocks[1][1].encode("utf-8")).hexdigest(), stats["appendix_output_sha256"])
        self.assertIn(f"smallest n in the grid with P(NI) >= 0.80 under every required law: "
                      f"{stats['planning_results']['delta_0.05']['n']}", blocks[1][1])
        self.assertIn(f"calibrated alpha' = {stats['planning_results']['delta_0.05']['alpha_boot']}", blocks[1][1])

    def test_citations_resolve_at_the_pinned_main_commit(self):
        if not (ROOT / ".git").exists():
            self.skipTest("not a Git checkout")
        probe = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", PINNED_MAIN + "^{commit}"],
                               capture_output=True, text=True)
        self.assertEqual(probe.returncode, 0,
                         f"pinned main {PINNED_MAIN} is not in this clone; fetch the full history")
        data, prose = load()
        cited = {(path, spec) for text in [prose, *strings(data)] for path, spec in CITATION.findall(text)}
        checks = {(row["path"], row["lines"]): row for row in data["citation_checks"]}
        self.assertEqual(sorted(cited - set(checks)), [], "citations without a recorded needle")
        self.assertEqual(sorted(set(checks) - cited), [], "needles for citations the files no longer make")
        cache = {}
        for (path, spec), row in sorted(checks.items()):
            if path not in cache:
                shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{PINNED_MAIN}:{path}"],
                                       capture_output=True, text=True)
                self.assertEqual(shown.returncode, 0, f"{path} does not exist at {PINNED_MAIN[:8]}")
                cache[path] = shown.stdout.splitlines()
            lines = cache[path]
            spans = ranges(spec)
            self.assertEqual(len(row["needles"]), len(spans), f"{path}:{spec}")
            for (lo, hi), needle in zip(spans, row["needles"]):
                self.assertTrue(1 <= lo <= hi <= len(lines), f"{path}:{spec} is outside the file")
                self.assertIn(normal(needle), normal(" ".join(lines[lo - 1:hi])), f"{path}:{lo}-{hi}")


if __name__ == "__main__":
    unittest.main()
