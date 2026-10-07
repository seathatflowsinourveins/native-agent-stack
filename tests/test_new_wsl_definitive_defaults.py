"""The new WSL's definitive defaults: one default per slot, one owner per tool, and no stale generated text.

Structural checks over committed files only (evidence/artifacts/new-wsl-definitive-defaults-20261001, and the
layer-consensus record that its assembler reads last). They do not judge any pick; they hold the manifest to its own rule.
Two classes run committed programs against stand-ins: the install plan's acceptance of the consensus row skill-authoring,
and the statusline row's helper commands and acceptance.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from tests.test_adoption_bootstrap import sha256sum_checks_like_gnu  # helpers only; its test classes run there

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001"
RECORD = ROOT / "docs/decisions/2026-10-01-new-wsl-definitive-defaults.md"
SELECTION = ROOT / "evidence/artifacts/new-wsl-clean-install-selection-20261001"
CONSENSUS_ART = ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002"
CONSENSUS_RECORD = ROOT / "docs/decisions/2026-10-02-new-wsl-layer-consensus.md"
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
ROW_KINDS = {"judged", "first_round", "pinned", "project_practice", "no_blind_default_today", "added", "consensus",
             "owner_decision"}
# Amendment 4 (wave 3, 2026-10-04): the slots the owner's decision adds, and the rows it gives an owner default or whose
# interim it amends. What a decision replaced stays on its row under overturned.
WAVE3_OWNER_ADDED = ["command-output", "output-compression", "code-index", "code-graph", "repo-packing", "structured-data",
                     "doc-conversion", "api-docs", "trace-viewer", "token-lane-carriers"]
# Round 2's record, rows table (2026-10-04-final-architecture-round2.md:23-28),
# and consensus.wave5, preserve the original batches and add these owners.
WAVE5_OWNER_ADDED = ["lm-program-optimization", "skill-vetting", "mcp-protocol-conformance", "trajectory-analysis"]
OWNER_ADDED = WAVE3_OWNER_ADDED + WAVE5_OWNER_ADDED
WAVE5_OWNER_DEFAULTS = {"agent-messaging", "playwright-cli"}
OWNER_DEFAULTS = {"context-supply", "ccusage", "session-analytics", "promptfoo"} | WAVE5_OWNER_DEFAULTS
OWNER_INTERIM = {"code-search"}
# What the rounds decided on a row: an amendment by direct consensus is recorded beside these and carries none of them.
PROTECTED = {"default", "state", "definitive", "repository", "installs_nothing_extra", "row_kind"}
PRIVATE_SHAPES = (r"/home/[a-z][a-z0-9_-]*/|/mnt/[a-z]/Users/|/tmp/claude-\d+/|-home-[a-z]",
                  r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")
DECISION_SLOTS = {"container-engine", "isolation-container-boundary", "code-search", "memory-owner", "context-supply",
                  "local-model-server"}
RESOLVED = ("final", "installed_on_critic", "not_installed", "split")
BASIS = {"final": "both families: the Claude record and the blind GPT samples",
         "installed_on_critic": "kept or added on a blind critic's verdict",
         "not_installed": "not installed: resolved by the rule or a blind critic",
         "split": "split: decided by the named measurement, nothing installed until it returns"}
ROUTING = (r"(?i)gpt-6\.1|\bsol\b at|codex lane|anthropic judge|openai judge|claude family|gpt family|astra|arbitration was attempted|"
           r"approval policy|approval review")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_key(value):
    value = (value or "").strip().lower().rstrip("/")
    parts = urlsplit(value)
    if parts.netloc in ("github.com", "www.github.com"):
        return "/".join(parts.path.strip("/").split("/")[:2])
    return value


def converged_key(slot):
    picks = []
    for family in ("claude", "gpt"):
        fam = slot.get("families", {}).get(family, {})
        if fam.get("critic_verdict") != "converged":
            return None
        if "decider_defaults" in fam:
            key = fam.get("default_key")
            if not key or fam["decider_defaults"] != [key] * 2:
                return None
        else:
            # The trading compact document retains the agreed names rather than finalist keys.
            names = fam.get("defaults_named", fam.get("defaults", []))
            if fam.get("deciders_agree") is not True or len(names) != 1:
                return None
            key = names[0]
            if fam.get("default_after_review") and fam["default_after_review"]["name"] != key:
                return None
        picks.append(key)
    return picks[0] if picks[0] == picks[1] else None


def load_source(path, name):
    """A module compiled from source, so that no bytecode is written into an artifact folder."""
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def load_assembler():
    """The assembler's functions."""
    return load_source(ART / "assemble_manifest.py", "assemble_manifest")


class Manifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load(ART / "definitive-manifest.json")
        cls.foundation = load(ART / "foundation-definitive.compact.json")
        cls.trading = load(ART / "trading/trading-definitive.compact.json")
        cls.settlements = load(ART / "settlements.json")
        cls.convergence = load(ART / "convergence.json")
        cls.decisions = {d["slot_id"]: d for d in cls.convergence["decisions"] + cls.convergence["added_slots"]}
        cls.combined = load(ROOT / cls.convergence["combined"]["path"])
        cls.consensus = load(CONSENSUS_ART / "consensus.json")
        # The record's own rows and amendments, then its wave-2 batch's (2026-10-03), in the order the assembler applies them.
        cls.wave2 = cls.consensus["wave2"]
        cls.added_rows = cls.consensus["add_rows"] + cls.wave2["add_rows"]
        cls.amend_rows = cls.consensus["amend_rows"] + cls.wave2["amend_rows"]
        cls.consensus_rows = {row["slot_id"]: row for row in cls.added_rows}
        cls.interims = {entry["slot_id"]: entry["interim"] for entry in cls.wave2["interim_rows"]}
        # The wave-3 batch (2026-10-04, amendment 4): the owner's rows, and its owner defaults and interim amendment.
        cls.wave3 = cls.consensus["wave3"]
        cls.wave4 = cls.consensus["wave4"]
        cls.wave5 = cls.consensus["wave5"]
        cls.owner_rows = {row["slot_id"]: row for batch in (cls.wave3, cls.wave5) for row in batch["add_rows"]}
        cls.owner_amends = {entry["slot_id"]: entry for batch in (cls.wave3, cls.wave4, cls.wave5)
                            for entry in batch["amend_rows"]}
        # Independent expected order: original source layers, then each batch's
        # recorded additions within its layer, rather than generated row order.
        cls.owner_order = [row["slot_id"]
                           for layer in cls.foundation["layers"] + cls.foundation.get("cross_rows", [])
                           for row in cls.owner_rows.values() if row["layer_id"] == layer["layer_id"]]
        cls.rows = cls.manifest["slots"]

    def as_decided(self, row):
        """The row as the rounds or an earlier batch decided it: an owner default (amendment 4) puts back the fields it
        replaced and the interim it dropped, and an interim the owner amended gets its replaced values back."""
        kept = row.get("overturned")
        if not kept:
            return row
        decided = {key: value for key, value in row.items() if key != "overturned"}
        decided.update(kept.get("fields", {}))
        if "interim" in kept:
            decided["interim"] = (kept["interim"] if "fields" in kept or "interim" not in row
                                  else {**row["interim"], **kept["interim"]})
        return decided

    def source_slots(self):
        for catalog, doc in (("foundation", self.foundation), ("us-equities", self.trading)):
            for layer in doc["layers"] + doc.get("cross_rows", []):
                for slot in layer.get("slots", []):
                    for part in slot.get("roles") or [slot]:
                        sid = slot["slot_id"] if part is slot else f"{slot['slot_id']}/{part['slot_id']}"
                        yield catalog, layer["layer_id"], sid, part

    def test_manifest_is_current(self):
        result = subprocess.run([sys.executable, str(ART / "assemble_manifest.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_record_tables_are_current(self):
        result = subprocess.run([sys.executable, str(ART / "render_tables.py"), "--check", str(RECORD)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_layer_of_both_catalogs_is_present_once(self):
        layers = [(l["catalog"], l["layer_id"]) for l in self.manifest["layers"]]
        self.assertEqual(len(layers), len(set(layers)))
        ownership = load(SELECTION / "ownership.json")
        foundation = {l["layer_id"] for l in self.manifest["layers"] if l["catalog"] == "foundation"}
        self.assertTrue({l["layer_id"] for l in ownership["layers"]} <= foundation)
        self.assertTrue({"cross:gpt6-harnesses", "cross:runtime-workers", "cross:credential-practice",
                         "cross:convergence-practice", "cross:wsl-distro"} <= foundation)
        trading = [l["layer_id"] for l in self.manifest["layers"] if l["catalog"] == "us-equities"]
        self.assertEqual(len(trading), 12)
        self.assertEqual(self.manifest["counts"]["layers"], 37)

    def test_every_slot_has_exactly_one_default_or_says_why_not(self):
        keys = [(r["catalog"], r["layer_id"], r["slot_id"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)), "a slot appears twice")
        for row in self.rows:
            self.assertIn(row["row_kind"], ROW_KINDS)
            if row["row_kind"] == "no_blind_default_today":
                self.assertEqual(row["default"], "")
                self.assertTrue(row["label"], row["slot_id"])
            else:
                self.assertTrue(row["default"], row["slot_id"])
                # One default means one: the wording that this change retires must not come back.
                self.assertIsNone(re.search(r"\bone of\b|\bcompare:", row["default"], re.I), row["default"])

    def test_every_row_has_state_and_measurement(self):
        for row in self.rows:
            with self.subTest(slot=row["slot_id"]):
                self.assertIn("state", row)
                self.assertIn("measurement", row)
                self.assertIn(row["state"], ("", "definitive", "resolved", "split", "measurement"))
                if row["state"] in ("split", "measurement"):
                    self.assertIsInstance(row["measurement"], dict)
                    self.assertEqual(set(row["measurement"]), {"returned", "receipts"})
                    self.assertIsInstance(row["measurement"]["returned"], bool)
                    self.assertIsInstance(row["measurement"]["receipts"], list)
                else:
                    self.assertIsNone(row["measurement"])
                if row["definitive"]:
                    self.assertEqual(row["state"], "definitive")
                if row["row_kind"] == "pinned":
                    self.assertEqual(row["state"], "")

    def test_every_row_has_job_and_resolution(self):
        # A row is decided by the rounds (convergence.json), added by the direct consensus or added by the owner's decision
        # (consensus.json), never two of them.
        self.assertEqual(set(self.decisions) & set(self.consensus_rows), set())
        self.assertEqual(set(self.owner_rows) & (set(self.decisions) | set(self.consensus_rows)), set())
        self.assertEqual({row["slot_id"] for row in self.rows},
                         set(self.decisions) | set(self.consensus_rows) | set(self.owner_rows))
        self.assertEqual(len(self.decisions), len(self.convergence["decisions"]) + len(self.convergence["added_slots"]))
        added_jobs = {d["slot_id"]: d["job"] for d in self.convergence["added_slots"]}
        owners = {}
        for row in self.rows:
            sid = row["slot_id"]
            with self.subTest(slot=sid):
                self.assertTrue(row.get("job"), sid)
                self.assertIn("resolution", row)
                resolution = row["resolution"]
                self.assertIsInstance(resolution, dict)
                if row["row_kind"] == "consensus":
                    self.assertEqual(row["job"], self.consensus_rows[sid]["job"])
                    self.assertEqual(resolution, self.consensus_rows[sid]["resolution"])
                    self.assertNotIn(resolution["outcome"], RESOLVED + ("kept",))
                elif row["row_kind"] == "owner_decision":
                    self.assertEqual(row["job"], self.owner_rows[sid]["job"])
                    self.assertEqual(resolution, self.owner_rows[sid]["resolution"])
                    self.assertEqual(resolution["outcome"], "added_by_owner_decision")
                elif sid in OWNER_DEFAULTS:
                    # The owner default's resolution is the batch's; the rounds' resolution stays under overturned.
                    self.assertEqual(resolution, self.owner_amends[sid]["owner_default"]["resolution"])
                    self.assertEqual(row["job"], self.convergence["jobs"].get(sid, added_jobs.get(sid)))
                    self.assertEqual(row["overturned"]["fields"]["resolution"]["outcome"], self.decisions[sid]["outcome"])
                else:
                    self.assertEqual(row["job"], self.convergence["jobs"].get(sid, added_jobs.get(sid)))
                    self.assertEqual(resolution["outcome"], self.decisions[sid]["outcome"])
                    for key in ("by", "votes", "covered_by", "arms", "deciding_measurement", "measurement_id"):
                        if key in self.decisions[sid]:
                            self.assertEqual(resolution[key], self.decisions[sid][key])
                if row["default"] and not row["installs_nothing_extra"]:
                    self.assertNotIn(row["job"], owners, f"{sid}: job already owned by {owners.get(row['job'])}")
                    owners[row["job"]] = sid

    def test_first_round_foundation_rows_have_an_outcome(self):
        for row in self.rows:
            if row["catalog"] != "foundation" or row["row_kind"] != "first_round":
                continue
            # An owner default (amendment 4) keeps the round's outcome under overturned; the round's record is checked there.
            row = self.as_decided(row)
            with self.subTest(slot=row["slot_id"]):
                resolution = row["resolution"]
                self.assertIn(resolution["outcome"], ("final", "installed_on_critic", "not_installed", "split", "kept"))
                if resolution["outcome"] == "kept":
                    self.assertTrue(resolution["reason"])
                else:
                    self.assertIn(row["state"], ("definitive", "resolved", "split"))
                if row["state"] == "split":
                    self.assertTrue(resolution["measurement_id"])
                    self.assertTrue(resolution["deciding_measurement"])

    def test_pending_measurements_install_nothing(self):
        for row in self.rows:
            if row["state"] == "split" or (row["measurement"] and not row["measurement"]["returned"]):
                with self.subTest(slot=row["slot_id"]):
                    self.assertEqual(row["repository"], "")
                    self.assertTrue(row["installs_nothing_extra"])
                    self.assertFalse(row["definitive"])
                    self.assertTrue(row["default"].startswith("Not installed"))
                    if row["resolution"]["outcome"] == "split":
                        self.assertEqual(row["measurement"], {"returned": False, "receipts": []})
                        self.assertGreaterEqual(len(row["resolution"]["arms"]), 2)

    def test_shared_measurement_ids_have_identical_arms(self):
        measurements = {}
        for row in self.rows:
            # Wave 5 keeps the unstarted browser/messaging splits under overturned.
            row = self.as_decided(row)
            resolution = row["resolution"]
            if resolution["outcome"] == "split":
                mid = resolution["measurement_id"]
                if mid in measurements:
                    self.assertEqual(resolution["arms"], measurements[mid], row["slot_id"])
                measurements[mid] = resolution["arms"]
        self.assertEqual(set(measurements), {"browser-tool", "event-store-and-dashboards", "local-generation-model",
                                             "embedding-model", "agent-messaging"})

    def test_data_final_rows_match_the_combined_final_list(self):
        combined = {layer["layer_id"]: layer for layer in self.combined["rows"]}
        for row in self.rows:
            if row["resolution"]["outcome"] != "final":
                continue
            with self.subTest(slot=row["slot_id"]):
                self.assertEqual(row["state"], "definitive")
                self.assertTrue(row["definitive"])
                repository = row["resolution"].get("judged_repository", row["repository"])
                repos = {repository_key(repo) for repo in repository.split(";") if repository_key(repo)}
                self.assertTrue(repos)
                final = {repository_key(repo) for repo in combined[row["layer_id"]]["final"]}
                self.assertTrue(repos <= final, f"{row['slot_id']}: {repos - final}")

    def test_critic_evidence_and_covering_slots_are_valid(self):
        rows = {row["slot_id"]: row for row in self.rows}
        for row in self.rows:
            if row["row_kind"] in ("consensus", "owner_decision"):
                continue  # No round decided it: it has no critic and no covering slot; its own tests are further down.
            # An owner default (amendment 4) keeps the round's resolution, with its critic and covering slots, under overturned.
            row = self.as_decided(row)
            sid, resolution = row["slot_id"], row["resolution"]
            decision = self.decisions[sid]
            with self.subTest(slot=sid):
                if resolution["outcome"] in ("installed_on_critic", "split"):
                    self.assertIn("critic", decision)
                if "critic" in decision:
                    evidence = resolution["evidence"]
                    self.assertEqual(evidence, decision["critic"])
                    path = ROOT / evidence["path"]
                    self.assertTrue(path.is_file(), sid)
                    self.assertEqual(sha(path), evidence["sha256"], sid)
                if resolution["outcome"] == "installed_on_critic":
                    self.assertEqual(row["state"], "resolved")
                    self.assertFalse(row["definitive"])
                if resolution["outcome"] in ("not_installed", "split"):
                    self.assertEqual(set(resolution["former_default"]), {"name", "repository"})
                    self.assertTrue(resolution["former_default"]["name"])
                if resolution["outcome"] == "not_installed":
                    self.assertEqual(row["state"], "resolved")
                    self.assertFalse(row["definitive"])
                    self.assertEqual(row["repository"], "")
                    self.assertTrue(row["installs_nothing_extra"])
                    self.assertEqual(row["default"], "Not installed: " + decision["reason"])
                    covered = resolution["covered_by"]
                    if covered != "not needed":
                        self.assertIsInstance(covered, list)
                        self.assertTrue(covered)
                        for owner in covered:
                            self.assertIn(owner, rows, sid)
                            self.assertTrue(rows[owner]["default"], owner)
                            self.assertFalse(rows[owner]["installs_nothing_extra"], owner)

    def test_added_slots_and_hygiene_preserve_the_decisions(self):
        rows = {row["slot_id"]: row for row in self.rows}
        settled = {settlement["slot_id"]: settlement for settlement in self.settlements}
        added_by_layer = {}
        for added in self.convergence["added_slots"]:
            # An owner default (amendment 4) keeps the added slot's decided fields under overturned.
            row = self.as_decided(rows[added["slot_id"]])
            self.assertEqual(row["row_kind"], "added")
            if added["outcome"] in ("split", "not_installed"):
                # an added row keeps the named candidate in its resolution
                self.assertEqual(row["resolution"]["former_default"], added["default"])
                if added["slot_id"] in settled:
                    # a split whose measurement returned carries the settlement's default (settlements.json)
                    settlement = settled[added["slot_id"]]
                    self.assertEqual(added["outcome"], "split")
                    self.assertEqual((row["default"], row["repository"]),
                                     (settlement["default"]["name"], settlement["default"]["repository"]))
                    self.assertFalse(row["installs_nothing_extra"])
                else:
                    # an added row that installs nothing keeps the named candidate only in its resolution
                    self.assertEqual(row["repository"], "")
                    self.assertTrue(row["installs_nothing_extra"])
            else:
                self.assertEqual(row["default"], added["default"]["name"])
                self.assertEqual(row["repository"], added["default"]["repository"])
            self.assertEqual(row["layer_id"], added["layer_id"])
            added_by_layer.setdefault(row["layer_id"], []).append(row["slot_id"])
        for lid, added in added_by_layer.items():
            # The consensus step and the owner's batch place their rows after these, so the order is taken over the rows the
            # rounds decided.
            order = [row["slot_id"] for row in self.rows
                     if row["layer_id"] == lid and row["row_kind"] not in ("consensus", "owner_decision")]
            self.assertEqual(order[-len(added):], added)
        for correction in self.convergence["hygiene"]:
            row = rows[correction["slot_id"]]
            self.assertEqual(row[correction["field"]], correction["value"])
            self.assertIn(correction["reason"], row["resolution"].get("reason", "") + row["label"])
            if correction["field"] == "repository":
                self.assertEqual(row["resolution"]["judged_repository"], correction["judged_as"])

    def compact_values(self, row):
        """The claude status, gpt status and label that the compact input gave the slot (or role) a row came from."""
        sources = [part for catalog, layer, sid, part in self.source_slots()
                   if catalog == row["catalog"] and layer == row["layer_id"]
                   and (row["slot_id"] == sid or row["slot_id"].startswith(sid + "/"))]
        self.assertEqual(len(sources), 1, row["slot_id"])
        part = sources[0]
        status = {}
        for family in ("claude", "gpt"):
            block = (part.get("families") or {}).get(family) or part.get(family)
            status[family] = block.get("status", "returned") if isinstance(block, dict) else "not judged"
        return {"claude": status["claude"], "gpt": status["gpt"], "label": part.get("label") or part.get("reason", "")}

    def expected_gpt(self, row):
        """The GPT family's current status on a resolved row, worked out from combined.json alone."""
        layer = next(layer for layer in self.combined["rows"] if layer["layer_id"] == row["layer_id"])
        resolution = row["resolution"]
        if resolution["outcome"] == "final":
            return ("returned: at least two of three blind GPT samples" if layer["g1_counted"]
                    else "returned: both blind Sol-ultra orders")
        repository = resolution.get("former_default", {}).get("repository", row["repository"])
        named = {repository_key(repo): count for key in ("claude_only", "gpt_only", "single_gpt_votes") for repo, count in layer[key]}
        if repository_key(repository) in named:
            return f"returned: {named[repository_key(repository)]} of {layer['gpt_samples_present']} blind GPT samples"
        if row["row_kind"] == "added":
            return "returned: named by the critic or the added-slot round, not by the layer's blind samples"
        # A first-round default that installs nothing has no repository for a sample to name.
        return f"returned: 0 of {layer['gpt_samples_present']} blind GPT samples"

    def test_no_family_status_is_stale(self):
        for row in self.rows:
            with self.subTest(slot=row["slot_id"]):
                for family in ("claude", "gpt"):
                    self.assertNotIn("in progress", row[family])
                    if row["resolution"]["outcome"] in RESOLVED:
                        self.assertFalse(row[family].startswith("pending"), f"{row['slot_id']}: {family}: {row[family]}")

    def test_resolved_rows_keep_their_first_round_record(self):
        for row in self.rows:
            resolution = row["resolution"]
            if resolution["outcome"] not in RESOLVED:
                continue
            with self.subTest(slot=row["slot_id"]):
                if row["row_kind"] == "added":
                    self.assertNotIn("first_round_record", resolution)
                else:
                    self.assertIn("first_round_record", resolution)
                    self.assertEqual(resolution["first_round_record"], self.compact_values(row))

    def test_resolved_rows_state_their_current_family_status(self):
        # A decision may state the GPT side itself (a row with no repository for a sample to name); otherwise it is computed.
        stated = {d["slot_id"]: d["gpt_status"] for d in self.convergence["decisions"] + self.convergence["added_slots"]
                  if d.get("gpt_status")}
        self.assertEqual(sorted(stated), ["agent-structural-diff"])
        settled = {settlement["slot_id"]: settlement["label"] for settlement in self.settlements}
        for row in self.rows:
            resolution = row["resolution"]
            if resolution["outcome"] not in RESOLVED:
                continue
            with self.subTest(slot=row["slot_id"]):
                self.assertEqual(row["gpt"], stated.get(row["slot_id"]) or self.expected_gpt(row))
                # A split whose measurement returned is labelled by its settlement; every other resolved row by its basis.
                returned = bool(row["measurement"] and row["measurement"]["returned"])
                self.assertEqual(returned, row["slot_id"] in settled)
                self.assertEqual(row["label"], settled[row["slot_id"]] if returned else BASIS[resolution["outcome"]])
                if row["row_kind"] == "added":
                    self.assertEqual(row["claude"], "not judged in the first round")
                else:
                    self.assertEqual(row["claude"], self.compact_values(row)["claude"])
        forms = [row["gpt"] for row in self.rows if row["resolution"]["outcome"] == "final"]
        self.assertEqual(forms.count("returned: both blind Sol-ultra orders"), 5)
        self.assertEqual(forms.count("returned: at least two of three blind GPT samples"), 23)

    def test_decision_rule_states_the_current_rule(self):
        rule = self.manifest["decision_rule"]
        self.assertIn("combination rule", rule)
        self.assertIn("RULE.md", rule)
        self.assertIn(self.convergence["rule"]["path"], rule)
        self.assertIn("amendment 1", rule)
        self.assertIn("decision-round", rule)
        self.assertNotEqual(rule, self.foundation["decision_rule"])
        self.assertEqual(self.manifest.get("decision_rule_before_amendment_2"), self.foundation["decision_rule"])
        # The consensus record's rule is appended whole, after the rounds' rule, then amendment 3 of its wave-2 batch and
        # amendment 4 of wave 3, reused unchanged by wave 5 and appended only once.
        self.assertTrue(rule.endswith(" " + self.consensus["rule"] + " " + self.wave2["interim_rule"] + " "
                                      + self.wave3["owner_rule"]))
        self.assertEqual(self.wave5["owner_rule"], self.wave3["owner_rule"])
        self.assertEqual(rule.count(self.wave3["owner_rule"]), 1)
        self.assertLess(rule.index("decision-round"), rule.index(self.consensus["rule"]))
        self.assertTrue(self.wave2["interim_rule"].startswith("Amendment 3 "))
        self.assertTrue(self.wave3["owner_rule"].startswith("Amendment 4 "))
        # Each amendment states its exception beside the no-install rule, which stays as the first round wrote it.
        self.assertEqual(self.manifest["no_install_rule"], self.foundation["no_install_rule"])
        self.assertEqual(self.manifest["no_install_rule_exception"],
                         self.wave2["no_install_rule_exception"] + " " + self.wave3["no_install_rule_exception"])
        # Wave 5 changes the owner-rule preamble, while repeating the same
        # exception; the manifest records the identical exception once.
        self.assertEqual(self.wave5["no_install_rule_exception"], self.wave3["no_install_rule_exception"])
        self.assertEqual(self.manifest["no_install_rule_exception"].count(self.wave3["no_install_rule_exception"]), 1)
        self.assertIn("exception to the no-install rule", self.manifest["no_install_rule_exception"])
        self.assertIn("second exception to the no-install rule", self.wave3["no_install_rule_exception"])

    def test_counts_include_states_and_installed_rows(self):
        counts = self.manifest["counts"]
        self.assertTrue({"layers", "slots", "definitive", "by_row_kind", "by_state", "installed"} <= set(counts))
        states, kinds = {}, {}
        for row in self.rows:
            state = row["state"] or "open"
            states[state] = states.get(state, 0) + 1
            kinds[row["row_kind"]] = kinds.get(row["row_kind"], 0) + 1
        self.assertEqual(counts["by_state"], states)
        self.assertEqual(counts["by_row_kind"], kinds)
        self.assertEqual(counts["slots"], len(self.rows))
        self.assertEqual(counts["installed"], sum(1 for row in self.rows if row["default"] and not row["installs_nothing_extra"]))

    def test_amendment_one_partitions_the_committed_samples(self):
        affected = {"semantic-rag", "document-retrieval", "web-research", "durable-memory", "token-efficiency",
                    "code-navigation", "quality-evaluation"}
        combined = {layer["layer_id"]: layer for layer in self.combined["rows"]}
        folder = (ROOT / self.convergence["combined"]["path"]).parent / "sol-ultra-round"
        for lid in sorted(affected):
            with self.subTest(layer=lid):
                layer = combined[lid]
                self.assertIs(layer["g1_counted"], False)
                self.assertEqual(layer["gpt_samples_present"], 2)
                self.assertEqual(layer["orders_present"], 2)
                claude = set()
                for catalog, source_layer, sid, slot in self.source_slots():
                    if catalog != "foundation" or source_layer != lid:
                        continue
                    default = slot.get("default") or {}
                    for pick in default if isinstance(default, list) else [default]:
                        claude.update(repository_key(repo) for repo in pick.get("repository", "").split(";") if repository_key(repo))
                samples = []
                for n in (1, 2):
                    doc = load(folder / f"order-{n}" / f"{lid}.json")
                    self.assertTrue(doc["layers"], lid)
                    samples.append({repository_key(pick.get("repository")) or pick.get("name", "").lower()
                                    for source in doc["layers"] for pick in source.get("selection", [])})
                union = claude | samples[0] | samples[1]
                votes = {repo: sum(repo in sample for sample in samples) for repo in union}
                expected = {"final": {repo for repo in claude if votes[repo] == 2},
                            "claude_only": {repo for repo in claude if votes[repo] < 2},
                            "gpt_only": {repo for repo in union - claude if votes[repo] == 2},
                            "single_gpt_votes": {repo for repo in union - claude if votes[repo] < 2}}
                actual = {"final": set(layer["final"])}
                for key in ("claude_only", "gpt_only", "single_gpt_votes"):
                    actual[key] = {repo for repo, count in layer[key]}
                    for repo, count in layer[key]:
                        self.assertEqual(count, votes[repo], repo)
                self.assertEqual(actual, expected)
                self.assertEqual(sum(map(len, actual.values())), len(union))
                self.assertEqual(set().union(*actual.values()), union)
                for repo in layer["final"]:
                    self.assertEqual(votes[repo], 2, repo)

    def test_no_tool_is_owned_by_two_layers(self):
        owners = {}
        for row in self.rows:
            if row["default"] and not row["installs_nothing_extra"]:
                owners.setdefault(row["default"].lower(), []).append((row["catalog"], row["layer_id"]))
        self.assertEqual({k: v for k, v in owners.items() if len(v) > 1}, {})

    def test_definitive_only_when_both_families_converged(self):
        for row in self.rows:
            if row["definitive"]:
                if row["resolution"]["outcome"] == "final":
                    continue  # The separate combined-file check covers the blind GPT round's rule.
                sources = [part for catalog, layer, sid, part in self.source_slots()
                           if catalog == row["catalog"] and layer == row["layer_id"]
                           and (row["slot_id"] == sid or row["slot_id"].startswith(sid + "/"))]
                self.assertEqual(len(sources), 1, row["slot_id"])
                self.assertTrue(converged_key(sources[0]), row["slot_id"])
        for layer in self.foundation["layers"] + self.foundation["cross_rows"]:
            for slot in layer["slots"]:
                families = slot.get("families", {})
                if slot["row_kind"] == "judged":
                    names = {f["key"]: f["name"] for f in load(ART / "packets" / f"{slot['slot_id']}.order-1.json")["finalists"]}
                    claude, gpt = families["claude"], families["gpt"]
                    # A family is converged only when its two deciders and its critic name the same finalist.
                    for fam in (claude, gpt):
                        if fam["status"] == "converged":
                            # The status is derived; the critic's own verdict and both votes must back it.
                            self.assertEqual(fam["critic_verdict"], "converged", slot["slot_id"])
                            self.assertEqual(fam["decider_defaults"], [fam["default_key"]] * 2, slot["slot_id"])
                    # The row's pick is the finalist the Claude family's key names, wherever the row keeps it.
                    if slot.get("split"):
                        picks = {b["family"]: b["name"] for b in slot["split_between"]}
                        self.assertEqual(picks, {"claude": names[claude["default_key"]], "gpt": names[gpt["default_key"]]})
                    elif slot.get("decided_by_measurement_at_user_request"):
                        self.assertEqual(slot["blind_round_pick"]["name"], names[claude["default_key"]])
                    else:
                        self.assertEqual(slot["default"]["name"], names[claude["default_key"]], slot["slot_id"])
                if slot["definitive"]:
                    self.assertEqual(slot["row_kind"], "judged", slot["slot_id"])
                    self.assertEqual(families["claude"]["status"], "converged")
                    self.assertEqual(families["gpt"]["status"], "converged")
                    self.assertEqual(families["claude"]["default_key"], families["gpt"]["default_key"])
                    self.assertEqual([families["claude"]["critic_verdict"], families["gpt"]["critic_verdict"]], ["converged"] * 2)
                    self.assertEqual(families["claude"]["decider_defaults"] + families["gpt"]["decider_defaults"],
                                     [families["claude"]["default_key"]] * 4)
        for layer in self.trading["layers"]:
            for slot in layer.get("slots", []):
                for part in slot.get("roles") or [slot]:
                    if part.get("definitive"):
                        families = part["families"]
                        self.assertEqual(families["claude"]["status"], "converged", slot["slot_id"])
                        self.assertEqual(families["gpt"]["status"], "converged", slot["slot_id"])
        self.assertEqual(self.manifest["counts"]["definitive"], sum(1 for r in self.rows if r["definitive"]))

    def test_converged_slots_are_definitive_except_the_known_trading_slot(self):
        exceptions = set()
        for catalog, layer, sid, slot in self.source_slots():
            # The user took memory out of the blind round; its measurement decides the install.
            if sid == "memory-owner" or not converged_key(slot):
                continue
            rows = [row for row in self.rows if row["catalog"] == catalog and row["layer_id"] == layer
                    and (row["slot_id"] == sid or row["slot_id"].startswith(sid + "/"))]
            self.assertTrue(rows, sid)
            # The rounds' result is the row as they decided it; an owner default (amendment 4) is never definitive itself.
            exceptions.update((catalog, row["slot_id"]) for row in rows if not self.as_decided(row)["definitive"])
        self.assertEqual(exceptions, {("us-equities", "market-data-provider")})
        # The one converged slot whose default the owner replaced: definitive as the rounds decided it, kept under overturned.
        overturned = [row["slot_id"] for row in self.rows if (row.get("overturned") or {}).get("fields", {}).get("definitive")]
        self.assertEqual(overturned, ["context-supply"])
        self.assertIs(next(row for row in self.rows if row["slot_id"] == "context-supply")["definitive"], False)

    def test_settled_rows_are_measurements_with_verified_receipts(self):
        # The model server by its gate (a row of the decision round), and the two local-model slots by their measurement
        # (rows that the convergence decisions added and split).
        settled = {"local-model-server", "local-generation-model", "embedding-model"}
        self.assertEqual({settlement["slot_id"] for settlement in self.settlements}, settled)
        self.assertEqual({row["slot_id"] for row in self.rows if row["measurement"] and row["measurement"]["returned"]},
                         settled)
        for settlement in self.settlements:
            rows = [row for row in self.rows if row["slot_id"] == settlement["slot_id"]]
            self.assertEqual(len(rows), 1, settlement["slot_id"])
            row = rows[0]
            self.assertFalse(row["definitive"], row["slot_id"])
            self.assertEqual(row["state"], "measurement")
            self.assertEqual(row["default"], settlement["default"]["name"])
            self.assertTrue(row["repository"], row["slot_id"])
            self.assertEqual(row["repository"], settlement["default"]["repository"])
            self.assertFalse(row["installs_nothing_extra"])
            self.assertIs(row["measurement"]["returned"], True)
            self.assertTrue(row["measurement"]["receipts"])
            self.assertEqual(row["measurement"]["receipts"], settlement["receipts"])
            self.assertEqual(row["label"], settlement["label"])
            self.assertIn(settlement["settled_by"], row["label"])
            self.assertIn("one workstation", row["label"])
            self.assertIn("not a merit acceptance", row["label"])
            for receipt in row["measurement"]["receipts"]:
                path = ROOT / receipt["path"]
                self.assertTrue(path.is_file(), receipt["path"])
                self.assertEqual(sha(path), receipt["sha256"], receipt["path"])
            self.assertEqual(settlement["limits"], load(ROOT / settlement["receipts"][-1]["path"])["limitations"])

    def test_settled_split_tables_preserve_the_blind_picks(self):
        lines = RECORD.read_text(encoding="utf-8").splitlines()
        slots = {slot["slot_id"]: slot for layer in self.foundation["layers"] for slot in layer["slots"]}
        added = {decision["slot_id"] for decision in self.convergence["added_slots"]}
        for settlement in self.settlements:
            slot = slots.get(settlement["slot_id"])
            if slot is None:
                # A slot the convergence decisions added has no blind picks of its own: its layer row shows the settled
                # default, the measurement state and the settlement as its basis.
                self.assertIn(settlement["slot_id"], added)
                line = next(line for line in lines if re.match(r"\| [^|]+ \| " + re.escape(settlement["slot_id"]) + r" \|", line))
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                self.assertEqual(cells[3:], [settlement["default"]["name"], "measurement", "settled by the preregistered measurement"])
                continue
            if slot.get("split"):
                line = next(line for line in lines if line.startswith(f"| {slot['slot_id']} |"))
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                self.assertEqual(cells[1], settlement["default"]["name"])
                self.assertEqual(cells[2], settlement["label"])
                for pick in slot["split_between"]:
                    self.assertIn(pick["name"], cells[3 if pick["family"] == "claude" else 4])

    def test_memory_and_code_search_measurements_have_not_returned(self):
        rows = {row["slot_id"]: row for row in self.rows if row["catalog"] == "foundation"}
        for sid, state in (("memory-owner", "measurement"), ("code-search", "split")):
            row = rows[sid]
            self.assertEqual(row["state"], state, sid)
            self.assertEqual(row["measurement"], {"returned": False, "receipts": []}, sid)
            self.assertTrue(row["installs_nothing_extra"], sid)
            self.assertFalse(row["definitive"], sid)

    def test_the_decision_round_covers_its_six_slots(self):
        judged = {s["slot_id"]: s for l in self.foundation["layers"] for s in l["slots"] if s["row_kind"] == "judged"}
        self.assertEqual(set(judged), DECISION_SLOTS)
        for slot in judged.values():
            self.assertTrue(slot["overturn_check"])
            self.assertTrue(slot["evidence"], slot["slot_id"])
            self.assertEqual(len(slot["families"]["claude"]["decider_defaults"]), 2)
            self.assertTrue(slot["label"].startswith(("default on", "no-install default", "split between", "decided by measurement")))
            if slot.get("decided_by_measurement_at_user_request"):
                # The user took the slot out of the blind round: nothing installs ahead of the measurement, and the
                # round's pick stays on the row without being called definitive.
                self.assertFalse(slot["definitive"])
                self.assertTrue(slot["default"]["installs_nothing_extra"])
                self.assertTrue(slot["blind_round_pick"]["name"])
                self.assertTrue(slot["decided_by_measurement_at_user_request"]["candidates"])
            elif slot.get("split"):
                # A split installs nothing and names both families' picks and the measurement that decides.
                self.assertFalse(slot["definitive"])
                self.assertTrue(slot["default"]["installs_nothing_extra"])
                self.assertEqual({b["family"] for b in slot["split_between"]}, {"claude", "gpt"})
                self.assertNotEqual(slot["split_between"][0]["name"], slot["split_between"][1]["name"])
                self.assertTrue(slot["deciding_measurement"]["claude_critic"] and slot["deciding_measurement"]["gpt_critic"])
            elif slot["default"]["installs_nothing_extra"]:
                self.assertEqual(slot["decided_on"], "no_install_baseline")

    def test_a_default_on_documented_fit_says_so(self):
        for layer in self.foundation["layers"]:
            for slot in layer["slots"]:
                if (slot["row_kind"] == "judged" and slot["could_not_separate"] and slot["decided_on"] != "no_install_baseline"
                        and not slot.get("split") and not slot.get("decided_by_measurement_at_user_request")):
                    self.assertIn("documented fit", slot["label"])

    def test_memory_default_carries_its_qualifications(self):
        memory = [s for l in self.foundation["layers"] for s in l["slots"] if s["slot_id"] == "memory-owner"][0]
        notes = " ".join(memory["qualifications_from_independent_fact_read"])
        for phrase in ("measured retrieval adverse", "0.821", "0.570", "0.496", "0.400", "AI_MEMORY_EMBEDDING_PROVIDER=local", "0.666",
                       "cascades across scopes"):
            self.assertIn(phrase, notes)

    def test_engine_row_carries_the_fact_its_deciders_did_not_weigh(self):
        engine = [s for l in self.foundation["layers"] for s in l["slots"] if s["slot_id"] == "container-engine"][0]
        notes = " ".join(engine["qualifications_from_independent_fact_read"])
        for phrase in ("41492", "isolateDistroCgroup=false", "re-decision"):
            self.assertIn(phrase, notes)

    def test_sources_match_the_committed_inputs(self):
        sources = self.foundation["sources"]
        self.assertEqual(sources["first_round_selection_sha256"], sha(SELECTION / "selection.json"))
        self.assertEqual(sources["ownership_sha256"], sha(SELECTION / "ownership.json"))
        self.assertEqual(sources["decision_round_preregistration_sha256"], sha(ART / "preregistration.json"))
        self.assertEqual(self.manifest["sources"]["foundation"]["sha256"], sha(ART / "foundation-definitive.compact.json"))
        self.assertEqual(self.manifest["sources"]["us-equities"]["sha256"], sha(ART / "trading/trading-definitive.compact.json"))
        self.assertEqual(self.manifest["sources"]["settlements"]["sha256"], sha(ART / "settlements.json"))
        self.assertEqual(self.manifest["sources"]["convergence"]["sha256"], sha(ART / "convergence.json"))
        for source in ("rule", "combined"):
            ref = self.convergence[source]
            self.assertEqual(self.manifest["sources"][source], ref)
            self.assertEqual(sha(ROOT / ref["path"]), ref["sha256"])
        consensus = CONSENSUS_ART / "consensus.json"
        self.assertEqual(self.manifest["sources"]["consensus"],
                         {"path": consensus.relative_to(ROOT).as_posix(), "sha256": sha(consensus)})

    def test_preregistered_inputs_are_the_committed_ones(self):
        prereg = load(ART / "preregistration.json")
        self.assertEqual(prereg["criteria_sha256"], sha(ART / "criteria.txt"))
        self.assertEqual(prereg["criteria_sha256"], sha(SELECTION / "criteria.txt"), "the criteria changed between the rounds")
        self.assertEqual(prereg["decide_prompt_sha256"], sha(ART / "decide-prompt.txt"))
        self.assertEqual(prereg["critic_prompt_sha256"], sha(ART / "decide-critic-prompt.txt"))
        self.assertEqual(len(prereg["packets_sha256"]), 12)
        for name, digest in prereg["packets_sha256"].items():
            self.assertEqual(digest, sha(ART / "packets" / name), name)

    def test_packets_hold_two_orders_of_the_same_finalists_and_no_reviewer_identity(self):
        for slot in DECISION_SLOTS:
            one, two = (load(ART / "packets" / f"{slot}.order-{n}.json") for n in (1, 2))
            keys = [[f["key"] for f in p["finalists"]] for p in (one, two)]
            self.assertNotEqual(keys[0], keys[1], slot)
            by_key = [sorted(p["finalists"], key=lambda f: f["key"]) for p in (one, two)]
            self.assertEqual(by_key[0], by_key[1], f"{slot}: the two orders hold different finalists")
            self.assertEqual({k: v for k, v in one.items() if k != "finalists"}, {k: v for k, v in two.items() if k != "finalists"})
            # Reviewer-routing wording would tell a decider which family wrote a note. One leak is known and recorded
            # (the memory packet's second-reviewer evidence gaps); nothing else may carry such wording.
            scrubbed = json.loads(json.dumps(one))
            leaked = scrubbed["first_round"].pop("second_reviewer_evidence_gaps", None)
            text = json.dumps(scrubbed)
            self.assertIsNone(re.search(ROUTING, text), slot)
            if leaked is not None and re.search(ROUTING, json.dumps(leaked)):
                self.assertEqual(slot, "memory-owner")
                self.assertIn("routing wording", (ART / "README.md").read_text(encoding="utf-8"))

    def test_no_host_path_or_user_name_in_the_artifact(self):
        for path in sorted(ART.rglob("*")):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"/home/[a-z][a-z0-9_-]*/|/mnt/[a-z]/Users/|/tmp/claude-\d+/|-home-[a-z]", text),
                                  str(path.relative_to(ROOT)))
                # The publication rule: nothing shaped like a local session identifier.
                self.assertIsNone(re.search(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", text, re.I), str(path.relative_to(ROOT)))

    def test_trading_rows_carry_their_stage_and_no_install_flag(self):
        stages, nothing = {}, {}
        for layer in self.trading["layers"]:
            for slot in layer.get("slots", []):
                for part in slot.get("roles") or [slot]:
                    sid = slot["slot_id"] if part is slot else f"{slot['slot_id']}/{part['slot_id']}"
                    stages[sid] = part.get("decision_stage") or slot.get("decision_stage")
                    default = part.get("default")
                    if isinstance(default, dict):
                        nothing[sid] = default.get("installs_nothing_extra")
        rows = {r["slot_id"]: r for r in self.rows if r["catalog"] == "us-equities"}
        for sid, stage in stages.items():
            for row_id, row in rows.items():
                if row_id == sid or row_id.startswith(sid + "/"):
                    if stage == "first_round":
                        self.assertEqual(row["row_kind"], "first_round", row_id)
                    elif stage == "decision_round":
                        self.assertEqual(row["row_kind"], "judged", row_id)
        self.assertTrue(rows["market-data-provider"]["installs_nothing_extra"])
        for sid, flag in nothing.items():
            if sid in rows and flag is not None:
                self.assertEqual(rows[sid]["installs_nothing_extra"], bool(flag), sid)
        # The lane's own flag for a default that coincides with its record reaches the manifest row unchanged.
        flags = {}
        for layer in self.trading["layers"]:
            for slot in layer.get("slots", []):
                for part in slot.get("roles") or [slot]:
                    sid = slot["slot_id"] if part is slot else f"{slot['slot_id']}/{part['slot_id']}"
                    if part.get("lane_record"):
                        flags[sid] = part["lane_record"]["coincides"]
        for row_id, row in rows.items():
            for sid, flag in flags.items():
                if row_id == sid or row_id.startswith(sid + "/"):
                    self.assertIs(row["coincides_with_lane_record"], flag, row_id)
        judged = [r for r in rows.values() if r["row_kind"] in ("judged", "first_round")]
        self.assertEqual(sum(1 for r in judged if r["coincides_with_lane_record"] is True), 9)
        self.assertEqual(sum(1 for r in judged if r["coincides_with_lane_record"] is False), 6)
        counts = self.trading["counts"]
        judged_rows = [r for r in rows.values() if r["row_kind"] in ("judged", "first_round")]
        self.assertEqual(len(judged_rows), counts["default_rows"])

    def test_trading_rows_are_the_trading_lanes(self):
        self.assertIn("trading lane", self.trading["owner"])
        self.assertEqual(len(self.trading["layers"]), 12)
        pinned = {p["name"] for p in self.trading["pinned_requirements"]}
        self.assertTrue(any("NautilusTrader 2.0.0rc5" in name for name in pinned))

    # The layer consensus of 2026-10-02: rows added, and amendments recorded, by a direct consensus of the two families.

    def test_counts_after_the_layer_consensus(self):
        counts, by_catalog = self.manifest["counts"], {}
        for row in self.rows:
            by_catalog[row["catalog"]] = by_catalog.get(row["catalog"], 0) + 1
        # 90 before wave 3, ten wave-3 owner rows, and four round-2 rows in wave 5.
        self.assertEqual(counts["slots"], 104)
        self.assertEqual(by_catalog, {"foundation": 84, "us-equities": 20})
        self.assertEqual(counts["layers"], 37)
        # 56 after the layer consensus, 57 with its wave-2 statusline row, 59 with the two local-model slots settled by their
        # measurement (2026-10-03), 72 with wave 3, 73 with Promptfoo, then six wave-5 installs.
        self.assertEqual(counts["installed"], 79)
        # Three interims under amendment 3; the context-supply owner default replaced one of them.
        self.assertEqual(counts["interim"], 2)
        self.assertEqual(counts["by_row_kind"]["consensus"], 6)
        self.assertEqual(counts["by_row_kind"]["owner_decision"], 14)
        # 23, the ten wave-3 owner rows, context-supply, the four wave-5 owner rows and the two wave-5 owner defaults (agent-messaging, playwright-cli) = 40.
        self.assertEqual(counts["by_state"]["resolved"], 40)
        self.assertEqual(counts["by_state"]["definitive"], 30)
        self.assertEqual(counts["definitive"], 30)
        self.assertEqual(counts["by_state"]["measurement"], 6)
        self.assertEqual(counts["by_state"]["split"], 3)

    def test_consensus_rows_are_the_records_rows_with_its_states(self):
        rows = {row["slot_id"]: row for row in self.rows}
        self.assertEqual(sorted(self.consensus_rows), ["credential-custody", "cross-family-review", "research-skill",
                                                       "skill-authoring", "skill-discovery", "statusline"])
        self.assertEqual({row["slot_id"] for row in self.rows if row["row_kind"] == "consensus"}, set(self.consensus_rows))
        # The fields a consensus row must carry are the ones the assembler writes for a row the rounds decided.
        fields = load_assembler().ROW_FIELDS
        self.assertEqual(tuple(key for key in self.rows[0] if key != "amendments"), fields)
        amended = {}
        for entry in self.amend_rows:
            amended.setdefault(entry["slot_id"], []).append(entry["amendment"])
        for sid, recorded in self.consensus_rows.items():
            with self.subTest(slot=sid):
                self.assertEqual(rows[sid]["state"], recorded["state"])
                # Copied as the record gives it; a later amendment (the wave-2 batch amends one) is recorded beside it.
                self.assertEqual({key: value for key, value in rows[sid].items() if key != "amendments"}, recorded)
                self.assertEqual(rows[sid].get("amendments"), amended.get(sid))
                self.assertEqual(tuple(key for key in rows[sid] if key != "amendments"), fields)
        # Each is placed after the last row the rounds decided in its layer, in the record's order (an owner row of the later
        # wave-3 batch follows them; its own test is further down).
        for lid in sorted({row["layer_id"] for row in self.consensus_rows.values()}):
            in_layer = [row for row in self.rows if row["layer_id"] == lid and row["row_kind"] != "owner_decision"]
            kinds = [row["row_kind"] == "consensus" for row in in_layer]
            self.assertEqual(kinds, sorted(kinds), lid)
            self.assertEqual([row["slot_id"] for row in in_layer if row["row_kind"] == "consensus"],
                             [row["slot_id"] for row in self.added_rows if row["layer_id"] == lid])

    def test_no_consensus_row_is_definitive(self):
        for row in self.rows:
            if row["row_kind"] != "consensus":
                continue
            with self.subTest(slot=row["slot_id"]):
                self.assertIs(row["definitive"], False)
                self.assertNotEqual(row["state"], "definitive")
                self.assertIn("direct consensus", row["label"])
                self.assertEqual(row["resolution"]["by"], "direct consensus of both model families")
                self.assertTrue(row["resolution"]["sources"])
                if row["measurement"] is not None:
                    # A consensus row that waits names what decides it and installs nothing meanwhile.
                    self.assertEqual(row["measurement"], {"returned": False, "receipts": []})
                    self.assertTrue(row["resolution"]["deciding_measurement"])
                    self.assertTrue(row["resolution"]["measurement_id"])
                    self.assertTrue(row["installs_nothing_extra"])

    def test_amendments_leave_the_rows_as_the_rounds_decided_them(self):
        _, _, decided, _, _ = load_assembler().assemble_rows()
        before = {row["slot_id"]: row for row in decided}
        self.assertEqual(set(before), {row["slot_id"] for row in self.rows} - set(self.consensus_rows) - set(self.owner_rows))
        recorded = {}
        for entry in self.amend_rows:
            self.assertEqual(set(entry), {"slot_id", "amendment"})
            self.assertEqual(set(entry["amendment"]) & PROTECTED, set(), entry["slot_id"])
            self.assertNotIn("interim", entry["amendment"])
            recorded.setdefault(entry["slot_id"], []).append(entry["amendment"])
        self.assertTrue(recorded)
        # The record's own amendments name rows the rounds decided; the wave-2 batch also amends a row the record added.
        self.assertTrue({entry["slot_id"] for entry in self.consensus["amend_rows"]} <= set(before),
                        "an amendment names a row that no round decided")
        self.assertTrue(set(recorded) <= set(before) | set(self.consensus_rows), "an amendment names an unknown row")
        for row in self.rows:
            sid = row["slot_id"]
            with self.subTest(slot=sid):
                if sid in recorded:
                    self.assertEqual(row["amendments"], recorded[sid])
                    for amendment in row["amendments"]:
                        for key in ("date_utc", "by", "decision"):
                            self.assertTrue(amendment[key], key)
                else:
                    self.assertNotIn("amendments", row)
                if row["row_kind"] not in ("consensus", "owner_decision"):
                    # Every other field is the one the assembler builds before the consensus step; an interim (amendment 3)
                    # is the one the record gives, beside them. An owner default or an owner's interim amendment
                    # (amendment 4) keeps what it replaced under overturned, so the row as decided is still these fields.
                    decided_row = self.as_decided(row)
                    self.assertEqual({key: value for key, value in decided_row.items() if key not in ("amendments", "interim")},
                                     before[sid])
                    self.assertEqual(decided_row.get("interim"), self.interims.get(sid))
                    self.assertEqual("overturned" in row, sid in OWNER_DEFAULTS | OWNER_INTERIM)

    def test_consensus_records_are_the_hashed_published_copies(self):
        records = self.consensus["records"]
        copies = load(CONSENSUS_ART / "copy-notes.json")["copies"]
        named = {name: ref for name, ref in records.items() if name != "acknowledgements"}
        # The Claude lane's review of the Codex lane's scoped dispositions is hashed like the copies but is not one: it was
        # written in the folder from the review as returned, so copy-notes.json, which accounts for the copies, omits it.
        review = named.pop("claude_review_held_topics")
        self.assertEqual(review["path"], (CONSENSUS_ART / "claude-review-held-topics.md").relative_to(ROOT).as_posix())
        self.assertNotIn(Path(review["path"]).name, copies)
        self.assertEqual(sha(ROOT / review["path"]), review["sha256"])
        self.assertEqual(sorted(Path(ref["path"]).name for ref in named.values()), sorted(copies))
        for name, ref in named.items():
            path = ROOT / ref["path"]
            with self.subTest(record=name):
                self.assertTrue(path.is_file())
                self.assertEqual(sha(path), ref["sha256"])
                self.assertEqual(copies[path.name]["sha256"], ref["sha256"])
        # Both families' acknowledgements are on record; they are links to pull-request comments, not hashed files.
        self.assertEqual({ack["family"] for ack in records["acknowledgements"]}, {"claude", "gpt"})
        for ack in records["acknowledgements"]:
            self.assertTrue(ack["url"].startswith("https://github.com/"), ack["url"])
        # Each acknowledgement says what its comment covers, in time order. The scoped dispositions are in the Codex
        # lane's note of 18:57:10Z: the Claude lane agreed to them from the note, before its review (5959684384), and the
        # Codex lane recorded receipt of that agreement (5959996494).
        acknowledgements = records["acknowledgements"]
        self.assertEqual([(ack["family"], ack["url"].rsplit("-", 1)[1]) for ack in acknowledgements],
                         [("claude", "5958766754"), ("gpt", "5959059286"), ("gpt", "5959205007"),
                          ("claude", "5959684384"), ("gpt", "5959996494")])
        self.assertEqual([ack["at"] for ack in acknowledgements], sorted(ack["at"] for ack in acknowledgements))
        for ack in acknowledgements:
            self.assertTrue(ack["covers"].strip(), ack["url"])
        by_id = {ack["url"].rsplit("-", 1)[1]: ack["covers"] for ack in acknowledgements}
        self.assertIn("claude_review_held_topics", by_id["5959684384"])
        self.assertIn("2026-10-02T18:57:10Z", by_id["5959684384"])
        self.assertIn("5959684384", by_id["5959996494"])

    def test_consensus_labels_follow_the_rule(self):
        """The rule's label clause, in the labels' own words: every consensus row names the direct consensus of both
        families; a row whose install waits says that its gate or its measurement decides and that nothing is installed
        until it returns, and every other row says that it is not a blind round and not a measurement. Acceptance gates
        that an installed or resolved row still has to pass are its open acceptance gates and do not hold its install."""
        self.assertIn("listed as its open acceptance gates and do not hold its install", self.consensus["rule"])
        rows = [row for row in self.rows if row["row_kind"] == "consensus"]
        self.assertEqual(len(rows), len(self.consensus_rows))
        for row in rows:
            label, resolution = row["label"], row["resolution"]
            with self.subTest(slot=row["slot_id"]):
                self.assertTrue(label.startswith("both families by direct consensus"), label)
                self.assertNotIn("open_gates", resolution)
                if row["state"] == "measurement":
                    self.assertRegex(label, r"; (?:an activation gate|the named measurement) decides\b")
                    self.assertTrue(label.endswith(", nothing installed until it returns"), label)
                    self.assertNotIn("not a blind round", label)
                    self.assertTrue(resolution["deciding_measurement"])
                    self.assertNotIn("open_acceptance_gates", resolution)
                else:
                    self.assertTrue(label.endswith("; not a blind round, not a measurement"), label)
                    self.assertNotIn("decides", label)
                    self.assertNotIn("deciding_measurement", resolution)
        gated = {row["slot_id"]: row for row in rows if "open_acceptance_gates" in row["resolution"]}
        self.assertEqual(sorted(gated), ["cross-family-review", "skill-authoring", "skill-discovery", "statusline"])
        for sid, row in gated.items():
            with self.subTest(gated=sid):
                # Installed or resolved, not waiting: the gates are acceptance on the destination, not a hold on the install.
                self.assertNotIn(row["state"], ("measurement", "split"))
                self.assertIsNone(row["measurement"])
                self.assertTrue(row["resolution"]["open_acceptance_gates"])

    def test_consensus_carries_the_reviews_qualifications_without_changing_a_decision(self):
        """Three facts of the Claude lane's review qualify the credential-guard amendment and two held topics: the
        comparison pins HOL Guard 3.17.2 or later; AgentCompass's Claude adapter writes its API key in plaintext; Docker's
        apt channel already carries Compose 5.6.0 and nothing holds the package. The decisions stay as they were."""
        amendment = next(entry["amendment"] for entry in self.consensus["amend_rows"] if entry["slot_id"] == "credential-guard")
        held = {topic["topic"]: topic for topic in self.consensus["held_without_a_row_change"]}
        expected = {
            "credential-guard": (amendment, ("3.17.2 or later", "21:12:17Z", "topic 1, claim 10")),
            "evaluation harness": (held["evaluation harness"], ("plaintext", "/tmp", "0600", "topic 2, omission 2")),
            "Docker Compose 5.6.0": (held["Docker Compose 5.6.0"], ("5.6.0", "only at install time", "topic 4, omission 2")),
        }
        for name, (item, phrases) in expected.items():
            with self.subTest(item=name):
                text = " ".join(item["qualifications"])
                for phrase in phrases:
                    self.assertIn(phrase, text)
        self.assertEqual(amendment["decision"], "keep the guard; hold one enforcement comparison")
        self.assertEqual(held["evaluation harness"]["decision"],
                         "keep Inspect AI 0.3.273 and Harbor 0.23; AgentCompass 1.0.0 only for an identified unmet evaluation requirement")
        self.assertEqual(held["Docker Compose 5.6.0"]["decision"],
                         "qualify the update; the selected 5.5.1 stays until the owner of that review accepts it")
        # The amendment carries its qualification into the manifest beside the row; the row's own fields do not change.
        guard = next(row for row in self.rows if row["slot_id"] == "credential-guard")
        carried = next(item for item in guard["amendments"] if item["decision"] == amendment["decision"])
        self.assertEqual(carried["qualifications"], amendment["qualifications"])

    def test_tables_show_consensus_rows_by_their_label_and_list_the_amendments(self):
        lines = RECORD.read_text(encoding="utf-8").splitlines()
        for sid, row in self.consensus_rows.items():
            with self.subTest(slot=sid):
                line = next(line for line in lines if line.startswith(f"| {row['layer_id']} | {sid} |"))
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                self.assertEqual(cells[4], row["state"])
                self.assertEqual(cells[5], row["label"])
                self.assertNotIn("**", cells[3])
        # The owner decisions of amendment 4 have their own table, after the amendments.
        start, end = lines.index("### Amendments by direct consensus"), lines.index("### Owner decisions (amendment 4)")
        self.assertLess(start, end)
        self.assertLess(end, lines.index("<!-- tables:end -->"))
        table = [[cell.strip() for cell in line.split("|")[1:-1]] for line in lines[start:end] if line.startswith("| ")]
        self.assertEqual(table[:2], [["Slot", "Date", "Decision"], ["---"] * 3])
        self.assertEqual(table[2:], [[row["slot_id"], amendment["date_utc"], amendment["decision"]]
                                     for row in self.rows for amendment in row.get("amendments", [])])
        self.assertEqual(len(table) - 2, len(self.amend_rows))
        start, end = lines.index("### Owner decisions (amendment 4)"), lines.index("<!-- tables:end -->")
        table = [[cell.strip() for cell in line.split("|")[1:-1]] for line in lines[start:end] if line.startswith("| ")]
        self.assertEqual(table[:2], [["Slot", "Date", "Decision", "Replaced"], ["---"] * 4])
        self.assertEqual([cells[0] for cells in table[2:]],
                         self.owner_order + [row["slot_id"] for row in self.rows if row.get("overturned")])
        for cells in table[2:]:
            with self.subTest(owner_table=cells[0]):
                self.assertEqual(cells[1], "2026-10-04")
                if cells[0] in self.owner_rows:
                    self.assertEqual(cells[2:], ["added: " + self.owner_rows[cells[0]]["default"], "nothing: a row the owner added"])
                else:
                    self.assertEqual(cells[2], self.owner_amends[cells[0]]["amendment"]["decision"])
        replaced = {cells[0]: cells[3] for cells in table[2:]}
        self.assertTrue(replaced["context-supply"].startswith("**No context-supply layer: the usage meter only** (definitive, kept)"))
        self.assertIn("the interim context-mode 1.0.169", replaced["context-supply"])
        self.assertEqual(replaced["code-search"], "the interim semble 0.6.1")
        # The interim installs of amendment 3 have their own table, before the amendments.
        start = lines.index("### Interim installs (amendment 3)")
        stop = lines.index("### Amendments by direct consensus")
        table = [[cell.strip() for cell in line.split("|")[1:-1]] for line in lines[start:stop] if line.startswith("| ")]
        self.assertEqual(table[0], ["Slot", "Date", "Interim", "Authority", "Decided by"])
        self.assertEqual(table[2:], [[row["slot_id"], row["interim"]["date_utc"], row["interim"]["default"],
                                      row["interim"]["authority"]["kind"].replace("_", " "), row["interim"]["decided_by"]]
                                     for row in self.rows if row.get("interim")])

    def test_consensus_decision_record_quotes_the_rule_and_the_owner(self):
        text = CONSENSUS_RECORD.read_text(encoding="utf-8")
        self.assertIn(self.consensus["rule"], text)
        self.assertIn(self.wave2["interim_rule"], text)
        self.assertIn(self.wave2["no_install_rule_exception"], text)
        self.assertIn(self.consensus["authorization"]["verbatim"], text)
        for sid in list(self.consensus_rows) + [entry["slot_id"] for entry in self.amend_rows] + list(self.interims):
            self.assertIn(f"`{sid}`", text, sid)
        for sentence in self.consensus["not_established"]:
            self.assertIn(sentence, text)
        # The earlier record points to this one outside its generated tables.
        earlier = RECORD.read_text(encoding="utf-8")
        outside = earlier[:earlier.index("<!-- tables:begin")] + earlier[earlier.index("<!-- tables:end -->"):]
        self.assertIn(CONSENSUS_RECORD.name, outside)

    def test_no_host_path_or_user_name_in_the_consensus_folder(self):
        for path in sorted(CONSENSUS_ART.rglob("*")):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(re.search(PRIVATE_SHAPES[0], text), str(path.relative_to(ROOT)))
                self.assertIsNone(re.search(PRIVATE_SHAPES[1], text, re.I), str(path.relative_to(ROOT)))

    # Amendment 3 (wave 2, 2026-10-03): interim installs on rows whose decided default installs nothing.

    def test_interims_are_the_records_beside_the_decided_rows(self):
        _, _, decided, _, _ = load_assembler().assemble_rows()
        before = {row["slot_id"]: row for row in decided}
        rows = {row["slot_id"]: row for row in self.rows}
        # The wave-2 batch recorded three interims. The wave-3 owner default on context-supply (amendment 4) replaced one,
        # which stays under overturned, and the owner widened code-search's to both arms of its confirmatory.
        self.assertEqual(sorted(self.interims), ["code-search", "context-supply", "memory-owner"])
        carried = {row["slot_id"]: row for row in self.rows if row.get("interim")}
        self.assertEqual(sorted(carried), ["code-search", "memory-owner"])
        self.assertEqual(self.manifest["counts"]["interim"], len(carried))
        assembler = load_assembler()
        for sid in self.interims:
            row = self.as_decided(rows[sid])
            with self.subTest(slot=sid):
                self.assertEqual(row["interim"], self.interims[sid])
                # The row stays as the rounds decided it, and its decided default installs nothing.
                self.assertEqual({key: value for key, value in row.items() if key not in ("interim", "amendments")}, before[sid])
                self.assertFalse(assembler.installs(row))
                self.assertTrue(assembler.installs_now(row))
                self.assertTrue(set(assembler.INTERIM_FIELDS) <= set(row["interim"]))
                self.assertTrue(row["interim"]["repository"].startswith("https://"))
                for ref in row["interim"]["records"]:
                    self.assertEqual(sha(ROOT / ref["path"]), ref["sha256"])
        # The protected rows keep their decided states: one split, one waiting measurement, one definitive no-install row.
        self.assertEqual({sid: (self.as_decided(rows[sid])["state"], self.as_decided(rows[sid])["definitive"])
                          for sid in self.interims},
                         {"code-search": ("split", False), "context-supply": ("definitive", True),
                          "memory-owner": ("measurement", False)})
        # memory-owner is the wave-2 interim unchanged; code-search's carries the owner's amendment over it.
        self.assertEqual(rows["memory-owner"]["interim"], self.interims["memory-owner"])
        change = self.owner_amends["code-search"]["interim"]
        self.assertEqual(rows["code-search"]["interim"], {**self.interims["code-search"], **change})
        self.assertEqual(rows["code-search"]["overturned"]["interim"], {key: self.interims["code-search"][key] for key in change})
        self.assertEqual(rows["code-search"]["interim"]["default"], "semble 0.6.1 + SocratiCode 1.15.0")
        # context-supply installs its owner default now, and its wave-2 interim is kept whole under overturned.
        self.assertNotIn("interim", rows["context-supply"])
        self.assertEqual(rows["context-supply"]["overturned"]["interim"], self.interims["context-supply"])
        self.assertTrue(assembler.installs(rows["context-supply"]))
        # The browser hold and the local-model rows carry no interim.
        for sid in ("playwright-cli", "local-generation-model", "embedding-model"):
            self.assertNotIn("interim", next(row for row in self.rows if row["slot_id"] == sid))

    def test_interim_labels_name_their_authority_and_what_decides(self):
        """The rule's label clause for an interim: it starts with 'interim install', names its authority and what decides it,
        and claims no consensus, measurement or blind result it does not have."""
        self.assertIn("its label starts with 'interim install'", self.wave2["interim_rule"])
        for sid, interim in self.interims.items():
            label, authority = interim["label"], interim["authority"]
            with self.subTest(slot=sid):
                self.assertTrue(label.startswith("interim install on the owner's "), label)
                self.assertEqual(authority["kind"], "owner_decision")
                self.assertRegex(label, r"\bdecides\b")
                self.assertIn("not a blind result", label)
                self.assertNotIn("consensus", label)
                self.assertTrue(authority["decision"].strip() and authority["relayed_by"].strip())
                self.assertEqual(set(interim["reviews"]), {"claude", "gpt"})
                self.assertTrue(interim["decided_by"].strip())
        # The GPT family's standing position is carried as it was: it disagreed on the context layer and recommended the
        # holds that the owner's decision lifted; the owner's own words are quoted where the relaying record quotes them.
        self.assertIn("disagreed", self.interims["context-supply"]["reviews"]["gpt"])
        for sid in ("memory-owner", "code-search"):
            self.assertIn("hold", self.interims[sid]["reviews"]["gpt"])
        self.assertIn("context mode", self.interims["context-supply"]["authority"]["verbatim"])
        self.assertIn("definitive", self.interims["context-supply"]["label"])
        self.assertIn("never removed automatically", self.interims["context-supply"]["decided_by"])
        # The memory server listens where the host and client templates point (wave-2 synthesis X5), not on 21374.
        self.assertIn("127.0.0.1:29374", self.interims["memory-owner"]["configuration"]["listen"])

    def test_no_installed_job_is_owned_twice_with_the_interims(self):
        assembler = load_assembler()
        owners = {}
        for row in self.rows:
            if assembler.installs_now(row):
                self.assertNotIn(row["job"], owners, f"{row['slot_id']} and {owners.get(row['job'])}")
                owners[row["job"]] = row["slot_id"]

    def test_the_wave2_batch_names_the_acknowledgements_it_owes(self):
        assembler = load_assembler()
        acknowledged = assembler.acknowledged_families(self.wave2["acknowledgements"])
        self.assertEqual(self.wave2["acknowledgements_owed"], sorted(set(assembler.FAMILIES) - acknowledged))
        self.assertEqual(self.manifest["consensus_wave2"]["acknowledgements_owed"], self.wave2["acknowledgements_owed"])
        self.assertEqual(self.manifest["consensus_wave2"]["acknowledgements"], self.wave2["acknowledgements"])
        for name, ref in self.wave2["records"].items():
            with self.subTest(record=name):
                self.assertEqual(sha(ROOT / ref["path"]), ref["sha256"])
        # A wave-2 row or amendment says that its acknowledgements are owed while they are.
        if self.wave2["acknowledgements_owed"]:
            for row in self.wave2["add_rows"]:
                self.assertIn("acknowledgements owed", row["label"])
            for entry in self.wave2["amend_rows"]:
                self.assertIn("acknowledgements owed", entry["amendment"]["by"])

    def test_the_assembler_refuses_an_interim_outside_the_rule(self):
        assembler = load_assembler()
        record = self.wave2["interim_rows"][0]

        def attempt(change, slot="memory-owner"):
            _, _, rows, _, _ = assembler.assemble_rows()
            by_slot = {row["slot_id"]: row for row in rows}
            entry = json.loads(json.dumps(record))
            entry["slot_id"] = slot
            change(entry, by_slot)
            with self.assertRaises(ValueError) as caught:
                assembler.apply_interims(rows, by_slot, [entry])
            return str(caught.exception)

        cases = [
            ("a row whose decided default installs", lambda e, b: None, "serena",
             "consensus serena: an interim installs only on a row whose decided default installs nothing"),
            ("an unknown slot", lambda e, b: None, "no-such-slot", "consensus no-such-slot: interim for unknown slot"),
            ("a missing authority", lambda e, b: e["interim"].pop("authority"), "memory-owner",
             "consensus memory-owner: an interim carries its fields: missing ['authority']; unknown []"),
            ("an unknown field", lambda e, b: e["interim"].update(state="definitive"), "memory-owner",
             "consensus memory-owner: an interim carries its fields: missing []; unknown ['state']"),
            ("an authority of another kind", lambda e, b: e["interim"]["authority"].update(kind="consensus"), "memory-owner",
             "consensus memory-owner: an interim's authority is one of owner_decision, direct_consensus, not consensus"),
            ("an owner's decision without its decision", lambda e, b: e["interim"]["authority"].pop("decision"), "memory-owner",
             "consensus memory-owner: the owner's decision needs its decision"),
            ("a direct consensus with one acknowledgement",
             lambda e, b: e["interim"].update(authority={"kind": "direct_consensus", "acknowledgements": [
                 {"family": "claude", "url": "https://github.com/example/example/pull/1#issuecomment-1"}]}), "memory-owner",
             "consensus memory-owner: a direct consensus needs an acknowledgement of each family"),
            ("one family's review missing", lambda e, b: e["interim"]["reviews"].pop("gpt"), "memory-owner",
             "consensus memory-owner: an interim records each family's review"),
            ("a records file whose hash differs", lambda e, b: e["interim"]["records"][0].update(sha256="0" * 64),
             "memory-owner", "consensus memory-owner interim: evidence sha256 mismatch"),
            ("no records", lambda e, b: e["interim"].update(records=[]), "memory-owner",
             "consensus memory-owner: an interim names its hashed records"),
            ("a repository that is not an https URL", lambda e, b: e["interim"].update(repository="akitaonrails/ai-memory"),
             "memory-owner", "consensus memory-owner: an interim names its repository by an https URL"),
            ("a blank pin", lambda e, b: e["interim"].update(pin=" "), "memory-owner",
             "consensus memory-owner: an interim needs a non-empty pin"),
            ("a job an installed row owns", lambda e, b: b["memory-owner"].update(job=b["serena"]["job"]), "memory-owner",
             "consensus memory-owner: installed job also owned by serena"),
            ("a second interim on the row", lambda e, b: b["memory-owner"].update(interim={"default": "x"}), "memory-owner",
             "consensus memory-owner: duplicate interim"),
            # The owner's decision is resolved in the hashed record its relayed_by names (review of 2026-10-03, minor 2).
            ("a decision relayed in another form",
             lambda e, b: e["interim"]["authority"].update(relayed_by="the owner, by word of mouth"), "memory-owner",
             "consensus memory-owner: the owner's decision is relayed by '<records file> owner_decisions[<n>]'"),
            ("a decision relayed by a file that is not a hashed record",
             lambda e, b: e["interim"]["authority"].update(relayed_by="other-records.json owner_decisions[0]"),
             "memory-owner", "consensus memory-owner: the owner's decision is relayed by other-records.json, which is not "
                             "one of the interim's hashed records"),
            ("a decision relayed by an entry the record lacks",
             lambda e, b: e["interim"]["authority"].update(relayed_by="wave2-records.json owner_decisions[9]"),
             "memory-owner", "consensus memory-owner: wave2-records.json has no owner_decisions[9]"),
            ("a relayed decision that names neither the slot nor the owner",
             lambda e, b: e["interim"]["authority"].update(relayed_by="wave2-records.json owner_decisions[1]"),
             "memory-owner", "consensus memory-owner: wave2-records.json owner_decisions[1] names neither the slot nor "
                             "ai-memory"),
            ("a decision dated otherwise than the entry it relays",
             lambda e, b: e["interim"]["authority"].update(date_utc="2026-10-04"), "memory-owner",
             "consensus memory-owner: the owner's decision is dated 2026-10-04, and the entry it relays 2026-10-03"),
            # The browser hold stays: the owner's decision that lifted two holds kept this one, so it names no browser owner.
            ("an interim on the held browser row",
             lambda e, b: e["interim"].update(repository="https://github.com/microsoft/playwright-cli"), "playwright-cli",
             "consensus playwright-cli: wave2-records.json owner_decisions[0] names neither the slot nor playwright-cli"),
            # A mention is not an authorization (the Codex root lane's read of b6828c7d, finding 1): the kept browser hold
            # names crawl4ai as a candidate to measure first, which the mention check alone took for the owner's authority.
            ("a browser interim for the tool the kept hold names to measure first",
             lambda e, b: e["interim"].update(repository="https://github.com/unclecode/crawl4ai"), "playwright-cli",
             "consensus playwright-cli: wave2-records.json owner_decisions[0] authorizes no install or use of "
             "https://github.com/unclecode/crawl4ai in the slot playwright-cli"),
            ("a repository the decision authorizes, in another slot it authorizes",
             lambda e, b: e["interim"].update(repository="https://github.com/MinishLab/semble"), "memory-owner",
             "consensus memory-owner: wave2-records.json owner_decisions[0] authorizes no install or use of "
             "https://github.com/MinishLab/semble in the slot memory-owner"),
        ]
        for name, change, slot, message in cases:
            with self.subTest(case=name):
                self.assertTrue(attempt(change, slot).startswith(message), attempt(change, slot))

    def test_an_owner_decision_authorizes_only_the_exact_pairs_its_record_lists(self):
        """An owner's decision authorizes an interim only where the record that relays it lists the interim's exact slot
        and repository under an affirmative action (the Codex root lane's read of b6828c7d, finding 1). The negative
        control: the browser interim that the mention check alone admitted is refused, and so is an entry whose grant is
        missing, of another action, slot or repository, while the unchanged entry still admits its interim."""
        assembler = load_assembler()
        ref = self.wave2["records"]["wave2_records"]
        record = load(ROOT / ref["path"])
        # Each recorded interim is one listed pair of the entry its authority relays, under the decision's own verb.
        for sid, interim in self.interims.items():
            with self.subTest(slot=sid):
                index = int(re.fullmatch(r"wave2-records\.json owner_decisions\[([0-9]+)\]",
                                         interim["authority"]["relayed_by"]).group(1))
                grants = [grant for grant in record["owner_decisions"][index]["authorizes"] if grant["slot_id"] == sid]
                self.assertEqual([(grant["action"], grant["repository"]) for grant in grants],
                                 [({"memory-owner": "install", "code-search": "install", "context-supply": "use"}[sid],
                                   interim["repository"])])
                self.assertIn(grants[0]["action"], assembler.AUTHORIZING_ACTIONS)
        # The old input: the kept browser hold names crawl4ai as a token, which is all the mention check asked for, and no
        # entry lists the browser slot or crawl4ai.
        self.assertRegex(record["owner_decisions"][0]["decision"].lower(), r"(?<![a-z0-9])crawl4ai(?![a-z0-9])")
        listed = [(grant["slot_id"], grant["repository"]) for entry in record["owner_decisions"] for grant in entry["authorizes"]]
        self.assertFalse([pair for pair in listed if pair[0] == "playwright-cli" or "crawl4ai" in pair[1]], listed)
        crawl = json.loads(json.dumps(self.interims["memory-owner"]))
        crawl["repository"] = "https://github.com/unclecode/crawl4ai"
        with self.assertRaises(ValueError) as caught:
            assembler.relayed_decision("playwright-cli", crawl, crawl["authority"])
        self.assertEqual(str(caught.exception), "consensus playwright-cli: wave2-records.json owner_decisions[0] authorizes "
                                                "no install or use of https://github.com/unclecode/crawl4ai in the slot "
                                                "playwright-cli")
        # A scratch copy of the record, changed in the one grant the memory interim rests on.
        interim = self.interims["memory-owner"]

        def attempt(change):
            with tempfile.TemporaryDirectory() as scratch:
                copy = Path(scratch) / ref["path"]
                copy.parent.mkdir(parents=True)
                doc = json.loads(json.dumps(record))
                change(doc["owner_decisions"][0])
                copy.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                assembler.ROOT = Path(scratch)
                try:
                    return assembler.relayed_decision("memory-owner", interim, interim["authority"])
                finally:
                    assembler.ROOT = ROOT

        self.assertEqual(attempt(lambda entry: None), record["owner_decisions"][0])
        refusal = ("consensus memory-owner: wave2-records.json owner_decisions[0] authorizes no install or use of "
                   "https://github.com/akitaonrails/ai-memory in the slot memory-owner")
        for name, change in (
                ("no authorizes", lambda entry: entry.pop("authorizes")),
                ("a hold, not an affirmative action", lambda entry: entry["authorizes"][0].update(action="hold")),
                ("another slot", lambda entry: entry["authorizes"][0].update(slot_id="embedding-model")),
                ("another repository", lambda entry: entry["authorizes"][0].update(
                    repository="https://github.com/akitaonrails/ai-memory-fork"))):
            with self.subTest(change=name):
                with self.assertRaises(ValueError) as caught:
                    attempt(change)
                self.assertEqual(str(caught.exception), refusal)

    # Amendment 4 (wave 3, 2026-10-04): the owner's decision adds rows and gives owner defaults; what it replaces stays.

    def test_owner_rows_are_the_batchs_rows_after_their_layer(self):
        assembler = load_assembler()
        rows = {row["slot_id"]: row for row in self.rows}
        self.assertEqual(list(self.owner_rows), OWNER_ADDED)
        self.assertEqual([row["slot_id"] for row in self.rows if row["row_kind"] == "owner_decision"], self.owner_order)
        for sid, recorded in self.owner_rows.items():
            row = rows[sid]
            with self.subTest(slot=sid):
                # Copied as the batch gives it, with the manifest's row fields.
                self.assertEqual(row, recorded)
                self.assertEqual(tuple(row), assembler.ROW_FIELDS)
                expected_layer = {
                    "lm-program-optimization": "cross:gpt6-harnesses",
                    "skill-vetting": "instructions-skills",
                    "mcp-protocol-conformance": "mcp-surfaces",
                    "trajectory-analysis": "quality-evaluation",
                }.get(sid, "token-efficiency")
                self.assertEqual((row["catalog"], row["layer_id"]), ("foundation", expected_layer))
                # Installed now, resolved, never definitive, and labelled as what it is.
                self.assertTrue(assembler.installs(row))
                self.assertEqual((row["state"], row["definitive"], row["measurement"]), ("resolved", False, None))
                batch_number = 5 if sid in WAVE5_OWNER_ADDED else 3
                self.assertTrue(row["label"].startswith(f"owner decision of 2026-10-04 (wave {batch_number}, amendment 4)"), row["label"])
                self.assertIn("not a blind result, a consensus or a measurement" if batch_number == 5 else
                              "not a blind round, not a consensus and not a measurement", row["label"])
                self.assertTrue(row["repository"].startswith("https://github.com/"), row["repository"])
                resolution = row["resolution"]
                self.assertEqual((resolution["outcome"], resolution["batch"]),
                                 ("added_by_owner_decision", f"wave{batch_number}"))
                for key in ("by", "reason", "pin", "install", "overturn"):
                    self.assertTrue(resolution[key].strip(), key)
                self.assertTrue(resolution["open_acceptance_gates"])
                self.assertIn("removes nothing by itself", resolution["overturn"])
                if batch_number == 3:
                    self.assertTrue(resolution["usage_rules"])
                else:
                    # Wave-5 added rows carry usage/qualification in install and
                    # open gates; its amended defaults also carry usage_rules.
                    self.assertTrue(resolution["install"])
                    self.assertTrue(resolution["open_acceptance_gates"])
                self.assertIn(self.consensus[f"wave{batch_number}"]["records"]["decision_record"]["path"],
                              resolution["sources"])
                for family in ("claude", "gpt"):
                    if batch_number == 3:
                        self.assertTrue(row[family].startswith("not judged"), row[family])
                    else:
                        # Round 2 carries its deciders/critic and Opus verification,
                        # while still resolving on the owner's repository-quality rule.
                        prefix = "Opus verification of decide round 2" if family == "claude" else "decide round 2"
                        self.assertTrue(row[family].startswith(prefix), row[family])
        # After every other row of the layer, in the batch's order.
        for layer_id in {row["layer_id"] for row in self.owner_rows.values()}:
            in_layer = [row["slot_id"] for row in self.rows if row["layer_id"] == layer_id]
            added = [sid for sid, row in self.owner_rows.items() if row["layer_id"] == layer_id]
            self.assertEqual(in_layer[-len(added):], added, layer_id)

    def test_owner_pins_are_the_repository_pins(self):
        """The original owner pins follow the host stack; wave 5 adds destination owners without moving host pins."""
        stack = {component["id"]: component["version"] for component in load(ROOT / "manifests/stack.json")["components"]}
        components = {"command-output": "rtk", "output-compression": "headroom", "code-index": "jcodemunch-mcp",
                      "code-graph": "codebase-memory-mcp", "repo-packing": "repomix", "structured-data": "toon",
                      "doc-conversion": "markitdown", "api-docs": "context-hub", "trace-viewer": "otel-tui",
                      "ccusage": "ccusage", "session-analytics": "agentsview", "context-supply": "context-mode",
                      "promptfoo": "promptfoo"}
        self.assertEqual(set(components), set(WAVE3_OWNER_ADDED) - {"token-lane-carriers"}
                         | (OWNER_DEFAULTS - WAVE5_OWNER_DEFAULTS))
        rows = {row["slot_id"]: row for row in self.rows}
        for sid, component in components.items():
            with self.subTest(slot=sid):
                self.assertRegex(rows[sid]["default"], r"(?<![0-9.])" + re.escape(stack[component]) + r"(?![0-9.])")
        interim = rows["code-search"]["interim"]["default"]
        self.assertIn("SocratiCode " + stack["socraticode"], interim)
        self.assertIn("semble 0.6.1", interim)
        wave5 = {r["slot_id"]: r for r in self.wave5["add_rows"]}
        wave5.update({e["slot_id"]: e["owner_default"] for e in self.wave5["amend_rows"]})
        self.assertEqual(set(wave5), set(WAVE5_OWNER_ADDED) | WAVE5_OWNER_DEFAULTS)
        for sid, recorded in wave5.items():
            with self.subTest(destination_pin=sid):
                self.assertEqual(rows[sid]["default"], recorded["default"])
                self.assertEqual(rows[sid]["resolution"]["pin"], recorded["resolution"]["pin"])

    def test_owner_defaults_keep_what_they_replace(self):
        assembler = load_assembler()
        _, _, decided, _, _ = assembler.assemble_rows()
        before = {row["slot_id"]: row for row in decided}
        rows = {row["slot_id"]: row for row in self.rows}
        self.assertEqual({sid for sid, row in rows.items() if (row.get("overturned") or {}).get("fields")}, OWNER_DEFAULTS)
        self.assertEqual({sid for sid, row in rows.items() if row.get("overturned")}, OWNER_DEFAULTS | OWNER_INTERIM)
        self.assertEqual(set(self.owner_amends), OWNER_DEFAULTS | OWNER_INTERIM)
        for sid in sorted(OWNER_DEFAULTS):
            row, entry = rows[sid], self.owner_amends[sid]
            default = entry["owner_default"]
            with self.subTest(slot=sid):
                # The decided default installed nothing; the owner default installs its owner and is not definitive.
                self.assertFalse(assembler.installs(before[sid]))
                self.assertTrue(assembler.installs(row))
                self.assertEqual({key: row[key] for key in ("default", "repository", "label", "claude", "gpt", "resolution")},
                                 {key: default[key] for key in ("default", "repository", "label", "claude", "gpt", "resolution")})
                self.assertEqual((row["state"], row["definitive"], row["measurement"], row["installs_nothing_extra"]),
                                 ("resolved", False, None, False))
                self.assertEqual(row["resolution"]["outcome"], "owner_default")
                batch_number = 5 if sid in WAVE5_OWNER_DEFAULTS else 4 if sid == "promptfoo" else 3
                self.assertTrue(row["label"].startswith(f"owner decision of 2026-10-04 (wave {batch_number}, amendment 4)"), row["label"])
                # What it replaced is kept: the decided fields, an interim it dropped, and the amendment that replaced them.
                kept = row["overturned"]
                self.assertEqual(kept["fields"], {key: before[sid][key] for key in assembler.OVERTURNED_FIELDS})
                self.assertEqual(kept["amendment"], entry["amendment"])
                self.assertEqual("interim" in kept, default["replaces_interim"])
                # The job and the row kind stay the rounds'.
                self.assertEqual((row["job"], row["row_kind"]), (before[sid]["job"], before[sid]["row_kind"]))
        self.assertEqual({sid for sid in OWNER_DEFAULTS if self.owner_amends[sid]["owner_default"]["replaces_interim"]},
                         {"context-supply"})

    def test_the_owner_batch_rests_on_the_hashed_record_that_relays_the_order(self):
        batch, authority = self.wave3, self.wave3["authority"]
        self.assertEqual((batch["acknowledgements"], batch["acknowledgements_owed"]), ([], []))
        self.assertEqual((authority["kind"], authority["date_utc"]), ("owner_decision", batch["date_utc"]))
        ref = batch["records"]["decision_record"]
        self.assertEqual(ref["path"], authority["relayed_by"])
        self.assertEqual(ref["path"], "docs/decisions/2026-10-04-token-full-stack-owner-default.md")
        self.assertEqual(sha(ROOT / ref["path"]), ref["sha256"])
        text = (ROOT / ref["path"]).read_text(encoding="utf-8")
        self.assertIn(authority["verbatim"], text)
        self.assertTrue(authority["verbatim"].startswith("WE NEED TO ENABLE FULL SOTA STACKS FOR THE TOKEN EFFICIENCY REPOS "))
        for sid in WAVE3_OWNER_ADDED + sorted((OWNER_DEFAULTS - {"promptfoo"} - WAVE5_OWNER_DEFAULTS) | OWNER_INTERIM):
            self.assertIn(f"`{sid}`", text, sid)
        for key in ("owner_rule", "no_install_rule_exception"):
            self.assertIn(batch[key], text, key)
        self.assertIn("net_provider_savings", text)
        # The manifest carries the batch's date, meaning, acknowledgements and authority as recorded.
        carried = self.manifest["consensus_wave3"]
        self.assertEqual(carried, {"date_utc": batch["date_utc"], "meaning": batch["meaning"],
                                   "authority": {key: authority[key] for key in ("kind", "date_utc", "relayed_by")},
                                   "acknowledgements": [], "acknowledgements_owed": []})
        # The 2026-10-01 record points to the owner's record outside its generated tables.
        earlier = RECORD.read_text(encoding="utf-8")
        outside = earlier[:earlier.index("<!-- tables:begin")] + earlier[earlier.index("<!-- tables:end -->"):]
        self.assertIn(Path(ref["path"]).name, outside)
        # The additive fix-wave uses the same hashed owner-batch contract for Promptfoo.
        batch = self.wave4
        ref = batch["records"]["decision_record"]
        self.assertEqual(sha(ROOT / ref["path"]), ref["sha256"])
        text = (ROOT / ref["path"]).read_text(encoding="utf-8")
        self.assertIn(batch["authority"]["verbatim"], text)
        self.assertIn("`promptfoo`", text)
        self.assertIn("https://github.com/promptfoo/promptfoo", text)
        self.assertEqual((batch["acknowledgements"], batch["acknowledgements_owed"]), ([], []))
        batch = self.wave5
        ref = batch["records"]["decision_record"]
        self.assertEqual(ref["path"], "docs/decisions/2026-10-04-final-architecture-round2.md")
        self.assertEqual(sha(ROOT / ref["path"]), ref["sha256"])
        text = (ROOT / ref["path"]).read_text(encoding="utf-8")
        self.assertIn(batch["authority"]["verbatim"], text)
        for sid in WAVE5_OWNER_ADDED + sorted(WAVE5_OWNER_DEFAULTS):
            self.assertIn(f"`{sid}`", text, sid)
        self.assertEqual((batch["acknowledgements"], batch["acknowledgements_owed"]), ([], []))

    def test_the_assembler_refuses_an_owner_batch_outside_amendment_4(self):
        """Negative controls: each case changes one thing in a scratch copy of the layer-consensus record and the assembler
        refuses it with its message; the unchanged copy assembles."""
        assembler = load_assembler()
        consensus = load(CONSENSUS_ART / "consensus.json")
        serena_job = next(row["job"] for row in self.rows if row["slot_id"] == "serena")

        def attempt(change):
            doc = json.loads(json.dumps(consensus))
            change(doc)
            with tempfile.TemporaryDirectory() as scratch:
                path = Path(scratch) / "consensus.json"
                path.write_text(json.dumps(doc), encoding="utf-8")
                assembler.CONSENSUS = path
                try:
                    _, _, rows, layers, _ = assembler.assemble_rows()
                    assembler.apply_consensus(rows, layers)
                    return None
                except ValueError as error:
                    return str(error)
                finally:
                    assembler.CONSENSUS = CONSENSUS_ART / "consensus.json"

        self.assertIsNone(attempt(lambda doc: None))

        def w3(doc):
            return doc["wave3"]

        def added(doc, sid="command-output"):
            return next(row for row in doc["wave3"]["add_rows"] if row["slot_id"] == sid)

        def amended(doc, sid):
            return next(entry for entry in doc["wave3"]["amend_rows"] if entry["slot_id"] == sid)

        record = "docs/decisions/2026-10-04-token-full-stack-owner-default.md"
        cases = [
            ("a misspelt batch key", lambda d: d.update(wave_3=d.pop("wave3")),
             "consensus wave_3: a batch is named wave<n> with n at least 2"),
            ("an unknown batch field", lambda d: w3(d).update(extra=1), "consensus wave3: an owner batch needs exactly "),
            ("an owed acknowledgement", lambda d: w3(d).update(acknowledgements_owed=["gpt"]),
             "consensus wave3: an owner batch owes no acknowledgement; its authority is the owner's decision"),
            ("an authority of another kind", lambda d: w3(d)["authority"].update(kind="direct_consensus"),
             "consensus wave3: an owner batch's authority is an owner_decision, not direct_consensus"),
            ("an authority without its words", lambda d: w3(d)["authority"].pop("verbatim"),
             "consensus wave3: the owner's decision needs exactly kind, date_utc, decision, verbatim, relayed_by, rule_basis"),
            ("an authority dated otherwise", lambda d: w3(d)["authority"].update(date_utc="2026-10-05"),
             "consensus wave3: the owner's decision is dated 2026-10-05, and the batch 2026-10-04"),
            ("a relaying record that is not hashed", lambda d: w3(d)["authority"].update(relayed_by="docs/other.md"),
             "consensus wave3: the owner's decision is relayed by docs/other.md, which is not one of the batch's hashed records"),
            ("a relaying record whose hash differs", lambda d: w3(d)["records"]["decision_record"].update(sha256="0" * 64),
             f"consensus wave3.records.decision_record: evidence sha256 mismatch: {record}"),
            ("words the record does not quote", lambda d: w3(d)["authority"].update(verbatim="INSTALL EVERYTHING"),
             f"consensus wave3: {record} does not quote the owner's words verbatim"),
            ("a slot the record does not name", lambda d: added(d).update(slot_id="unnamed-slot"),
             f"consensus wave3: {record} does not name the slot unnamed-slot"),
            ("a repository the record does not name", lambda d: added(d).update(repository="https://github.com/example/unnamed"),
             f"consensus wave3: {record} does not name the repository https://github.com/example/unnamed"),
            ("a definitive owner row", lambda d: added(d).update(definitive=True),
             "consensus command-output: an owner row is never definitive"),
            ("an owner row of the consensus kind", lambda d: added(d).update(row_kind="consensus"),
             "consensus command-output: an added row must have row_kind owner_decision, not consensus"),
            ("an owner row that installs nothing", lambda d: added(d).update(installs_nothing_extra=True),
             "consensus command-output: an owner row is resolved, waits for no measurement and installs its default"),
            ("an owner row without its label", lambda d: added(d).update(label="installed by default"),
             "consensus command-output: an owner row's label starts with 'owner decision'"),
            ("an owner row with another outcome", lambda d: added(d)["resolution"].update(outcome="final"),
             "consensus command-output: an owner row has the outcome added_by_owner_decision"),
            ("an owner row of another batch", lambda d: added(d)["resolution"].update(batch="wave2"),
             "consensus command-output: the resolution names the batch wave2, not wave3"),
            ("an owner row without its overturn check", lambda d: added(d)["resolution"].update(overturn=" "),
             "consensus command-output: an owner decision's resolution needs a non-empty overturn"),
            ("an owner row whose job an installed row owns", lambda d: added(d).update(job=serena_job),
             f"consensus command-output: installed job also owned by serena: {serena_job}"),
            ("an owner default on a row that installs", lambda d: amended(d, "ccusage").update(slot_id="mineru"),
             "consensus mineru: an owner default replaces only a decided default that installs nothing"),
            ("an owner default that misstates its interim",
             lambda d: amended(d, "ccusage")["owner_default"].update(replaces_interim=True),
             "consensus ccusage: replaces_interim must say whether the row carries an interim"),
            ("an owner default without its label", lambda d: amended(d, "ccusage")["owner_default"].update(label="meter"),
             "consensus ccusage: an owner default's label starts with 'owner decision'"),
            ("an owner default with a missing field", lambda d: amended(d, "ccusage")["owner_default"].pop("gpt"),
             "consensus ccusage: an owner default carries exactly default, repository, label, claude, gpt, replaces_interim, "
             "resolution"),
            ("an owner default with another outcome",
             lambda d: amended(d, "ccusage")["owner_default"]["resolution"].update(outcome="final"),
             "consensus ccusage: an owner default has the outcome owner_default"),
            ("an amendment dated otherwise", lambda d: amended(d, "ccusage")["amendment"].update(date_utc="2026-10-05"),
             "consensus ccusage: the amendment is dated 2026-10-05, and its batch 2026-10-04"),
            ("an amendment that carries a decided field", lambda d: amended(d, "ccusage")["amendment"].update(default="x"),
             "consensus ccusage: an amendment's own text cannot carry default"),
            ("an amendment with both an owner default and an interim",
             lambda d: amended(d, "ccusage").update(interim={"default": "x"}),
             "consensus ccusage: an owner amendment is its slot_id, its amendment and one owner_default or interim"),
            ("a second owner amendment of a row",
             lambda d: w3(d)["amend_rows"].append(json.loads(json.dumps(amended(d, "ccusage")))),
             "consensus ccusage: the row already carries an owner amendment"),
            ("an interim amendment on a row without an interim", lambda d: amended(d, "code-search").update(slot_id="mineru"),
             "consensus mineru: an interim amendment needs a row that carries an interim"),
            ("an interim amendment of its authority",
             lambda d: amended(d, "code-search")["interim"].update(authority={"kind": "owner_decision"}),
             "consensus code-search: an interim amendment changes only default, repository, pin, label, decided_by, "
             "open_acceptance_gates"),
            ("an interim amendment without the interim label",
             lambda d: amended(d, "code-search")["interim"].update(label="both arms"),
             "consensus code-search: an interim's label starts with 'interim install'"),
        ]
        for name, change, message in cases:
            with self.subTest(case=name):
                refusal = attempt(change)
                self.assertIsNotNone(refusal, name)
                self.assertTrue(refusal.startswith(message), refusal)


class InterimPlanChecks(unittest.TestCase):
    """The install plan's side of amendment 3, as check_plan.py and install.sh hold it. check_plan.py refuses a plan that
    does not install a recorded interim, one whose owner is not the interim's, one whose interim install function does
    not call the acknowledgement gate first, and one that gates a row without an interim (an owner default of amendment 4);
    the gate (install.sh's interim_acknowledged) refuses while any batch of the layer consensus (wave2, wave3, ...) owes an
    acknowledgement. Each case changes one thing in a scratch copy of the plan."""

    GATE_LINE = '  interim_acknowledged {slot} || return "$?"\n'

    def test_chrome_privileged_declaration_cannot_drift_from_the_helper(self):
        def stale(rows):
            if "prerequisite_steps" in rows["playwright-cli"]:
                rows["playwright-cli"]["prerequisite_steps"][0]["command"] = "dpkg -i unverified-current.deb"
        code, out = self.run_check(change_rows=stale)
        self.assertEqual(code, 1, out)
        self.assertIn("privileged prerequisite declaration differs", out)

    def run_check(self, change_rows=None, change_install=None, change_manifest=None):
        """(exit status, output) of check_plan.py over a scratch copy of the plan and the manifest."""
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            plan_dir = scratch / "plan"
            shutil.copytree(PLAN, plan_dir, ignore=shutil.ignore_patterns("__pycache__"))
            manifest = scratch / "definitive-manifest.json"
            shutil.copy2(ART / "definitive-manifest.json", manifest)
            if change_manifest:
                data = load(manifest)
                change_manifest(data)
                manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            if change_rows:
                for name in ("install-plan.json", "owners.json"):    # the two files list the same rows
                    data = load(plan_dir / name)
                    change_rows({row["slot"]: row for row in data["owners"]})
                    (plan_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            if change_install:
                path = plan_dir / "install.sh"
                path.write_text(change_install(path.read_text(encoding="utf-8")), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(PLAN / "check_plan.py"), "--plan-dir", str(plan_dir),
                                     "--manifest", str(manifest)], capture_output=True, text=True, timeout=180)
        return result.returncode, result.stdout + result.stderr

    def test_messaging_cannot_hide_under_another_slots_selector(self):
        code, out = self.run_check(change_install=lambda text: text.replace(
            "if selected 'agent-messaging'; then run_slot 'agent-messaging'; fi",
            "if selected 'sandbox-runtime-srt'; then run_slot 'agent-messaging'; fi"))
        self.assertEqual(code, 1, out)
        self.assertIn("install.sh never runs row agent-messaging", out)

    def test_the_unchanged_copy_passes(self):
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("OK: "), out)

    def test_promptfoo_cannot_override_the_manifest_exclusion(self):
        def exclude(data):
            row = next(r for r in data["slots"] if r["slot_id"] == "promptfoo")
            row.update(default="Not installed: prompt and provider evaluation is owned by Inspect AI; neither blind Sol-ultra order picked it",
                       repository="", installs_nothing_extra=True, state="resolved",
                       resolution={"outcome": "not_installed"})
        code, out = self.run_check(change_manifest=exclude)
        self.assertEqual(code, 1, out)
        self.assertIn("[manifest]", out)
        self.assertIn("promptfoo", out)

    def test_an_interim_the_plan_does_not_install_is_refused(self):
        code, out = self.run_check(change_rows=lambda rows: rows["code-search"].update(installed=False))
        self.assertEqual(code, 1, out)
        self.assertIn("[manifest] row code-search: the manifest records an interim install, and the plan does not install "
                      "it", out)

    def test_a_plan_owner_that_is_not_the_interims_is_refused(self):
        code, out = self.run_check(change_rows=lambda rows: rows["memory-owner"].update(owner="agentmemory 0.9.0"))
        self.assertEqual(code, 1, out)
        self.assertIn("[manifest] row memory-owner: owner/repository differ from the manifest's interim's "
                      "default/repository", out)

    def test_an_interim_install_function_without_the_gate_first_is_refused(self):
        for slot in ("memory-owner", "code-search"):
            with self.subTest(slot=slot):
                line = self.GATE_LINE.format(slot=slot)
                code, out = self.run_check(change_install=lambda text: text.replace(line, "", 1) if line in text
                                           else self.fail(f"install.sh has no gate line for {slot}"))
                self.assertEqual(code, 1, out)
                self.assertIn(f"[interim] row {slot}: its install function in install.sh does not call "
                              f"`interim_acknowledged {slot}` before anything else", out)

    def test_an_owner_default_installs_without_the_gate_and_a_gate_on_it_is_refused(self):
        """context-supply's owner default (wave 3, amendment 4) replaced its interim: its install function has no gate
        call, and a plan that puts the gate back on it, or on an owner row, is refused (the gate would hold an install
        that its authority, the owner's decision, does not hold)."""
        body = re.search(r"(?ms)^context-supply\(\) \{\n(.*?)^\}$", (PLAN / "install.sh").read_text(encoding="utf-8")).group(1)
        self.assertNotIn("interim_acknowledged", body)
        for slot in ("context-supply", "command-output"):
            with self.subTest(slot=slot):
                header = f"{slot}() {{\n"
                code, out = self.run_check(change_install=lambda text: text.replace(
                    header, header + self.GATE_LINE.format(slot=slot), 1))
                self.assertEqual(code, 1, out)
                self.assertIn(f"[interim] row {slot}: its install function in install.sh calls `interim_acknowledged`, but "
                              "the manifest records no interim for it", out)

    def test_an_install_script_without_the_gate_function_is_refused(self):
        code, out = self.run_check(change_install=lambda text: text.replace("interim_acknowledged() {",
                                                                            "interim_unused() {", 1))
        self.assertEqual(code, 1, out)
        self.assertIn("[interim] install.sh has no interim_acknowledged function that reads the wave batches' "
                      "acknowledgements_owed", out)

    def run_gate(self, consensus, slot="memory-owner"):
        """(exit status, stderr) of install.sh's own gate function, cut from the script, with repo_root at a scratch folder
        whose consensus.json is `consensus` (None: no file)."""
        if not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("bash and jq are needed to run the gate")
        function = re.search(r"(?ms)^interim_acknowledged\(\) \{.*?^\}$", (PLAN / "install.sh").read_text(encoding="utf-8"))
        self.assertIsNotNone(function)
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / CONSENSUS_ART.relative_to(ROOT) / "consensus.json"
            path.parent.mkdir(parents=True)
            if consensus is not None:
                path.write_text(json.dumps(consensus), encoding="utf-8")
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", f"{function.group(0)}\ninterim_acknowledged {slot}\n"],
                                    env={**os.environ, "repo_root": scratch}, capture_output=True, text=True, timeout=60)
        return result.returncode, result.stderr

    def test_the_gate_refuses_while_an_acknowledgement_is_owed_and_passes_once_none_is(self):
        code, err = self.run_gate({"wave2": {"acknowledgements_owed": ["claude", "gpt"]}})
        self.assertEqual(code, 1)
        self.assertIn("memory-owner: refused: an interim install waits for the acknowledgements still owed by the wave "
                      "batches: wave2: claude, gpt", err)
        self.assertEqual(self.run_gate({"wave2": {"acknowledgements_owed": []}}), (0, ""))
        # Every batch is read (wave 3, 2026-10-04): a later batch that owes one refuses, and none owing passes.
        code, err = self.run_gate({"wave2": {"acknowledgements_owed": []}, "wave3": {"acknowledgements_owed": ["gpt"]}})
        self.assertEqual(code, 1)
        self.assertIn("memory-owner: refused: an interim install waits for the acknowledgements still owed by the wave "
                      "batches: wave3: gpt", err)
        code, err = self.run_gate({"wave2": {"acknowledgements_owed": ["claude"]}, "wave3": {"acknowledgements_owed": ["gpt"]}})
        self.assertEqual(code, 1)
        self.assertIn("wave batches: wave2: claude; wave3: gpt", err)
        self.assertEqual(self.run_gate({"wave2": {"acknowledgements_owed": []}, "wave3": {"acknowledgements_owed": []}}),
                         (0, ""))
        # The same inputs the client configuration's owed_acknowledgements refuses (tests/test_new_wsl_client_config.py,
        # AcknowledgementGateTests), a later batch that cannot be read, a misspelt batch key, and a file that is not there.
        for broken in ({}, {"wave2": {}}, {"wave2": {"acknowledgements_owed": "claude"}},
                       {"wave2": {"acknowledgements_owed": [""]}},
                       {"wave2": {"acknowledgements_owed": []}, "wave3": {}},
                       {"wave2": {"acknowledgements_owed": []}, "wave_3": {"acknowledgements_owed": ["gpt"]}}, None):
            with self.subTest(consensus=broken):
                code, err = self.run_gate(broken, slot="code-search")
                self.assertEqual(code, 1)
                self.assertIn("code-search: refused: the acknowledgements of the wave batches cannot be read", err)

    def test_the_gate_reads_the_committed_batch(self):
        consensus = load(CONSENSUS_ART / "consensus.json")
        owed = [family for key, batch in consensus.items() if re.fullmatch(r"wave[0-9]+", key)
                for family in batch["acknowledgements_owed"]]
        if not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("bash and jq are needed to run the gate")
        function = re.search(r"(?ms)^interim_acknowledged\(\) \{.*?^\}$", (PLAN / "install.sh").read_text(encoding="utf-8"))
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", f"{function.group(0)}\ninterim_acknowledged code-search\n"],
                                env={**os.environ, "repo_root": str(ROOT)}, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1 if owed else 0, result.stderr)
        # The owner's batch owes none; the wave-2 batch's owed acknowledgements are what the committed gate reports.
        self.assertEqual(consensus["wave3"]["acknowledgements_owed"], [])
        if owed:
            self.assertIn("wave2: " + ", ".join(consensus["wave2"]["acknowledgements_owed"]), result.stderr)


class SkillAuthoringAcceptance(unittest.TestCase):
    """The install plan's acceptance of the consensus row skill-authoring, run against stand-ins.

    The record's reason for the row is that no same-name copy of skill-creator is placed beside the one Codex embeds.
    The program that accept.sh runs for the row is run here as accept.sh runs it (bash -euo pipefail -c), with a stub
    npx that prints a canned listing and records its arguments, a canned lock file and a scratch HOME. The expected state
    passes, and each condition of the program, planted on its own, fails it. The fixtures are our own: the stub does not
    exercise the installer's listing logic, and nothing is installed.
    """

    WANT = "3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6"
    LISTING_ARGS = "--yes skills@1.7.0 list -g --json"
    SKILL = "---\nname: skill-creator\n---\n"

    @classmethod
    def setUpClass(cls):
        if not (shutil.which("bash") and shutil.which("jq")):
            raise unittest.SkipTest("bash and jq are needed to run the acceptance program")
        row = next(r for r in load(PLAN / "install-plan.json")["owners"] if r["slot"] == "skill-authoring")
        cls.program = row["acceptance"]["post_install"]["command"]

    def run_case(self, agents=("Claude Code",), folder_hash=None, plant=(), codex_home=False, errexit=True):
        """The program's exit status for one state, the arguments the stub npx received, and the program's stderr.

        HOME is <scratch>/home and, with codex_home, CODEX_HOME is <scratch>/codex-home; `plant` holds (kind, path under
        the scratch folder) pairs, where kind is "folder" (a skill folder) or "dangling" (a link to nothing). Without
        errexit the program runs without -e."""
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            home, stub = scratch / "home", scratch / "bin"
            (home / ".agents/skills/find-skills").mkdir(parents=True)  # another skill in the shared directory
            embedded = home / ".codex/skills/.system/skill-creator"  # where Codex keeps its embedded skills
            embedded.mkdir(parents=True)
            (embedded / "SKILL.md").write_text(self.SKILL, encoding="utf-8")
            listing = [{"name": "find-skills", "scope": "global", "agents": ["Claude Code", "Codex"]}]
            if agents is not None:
                listing.append({"name": "skill-creator", "scope": "global", "agents": list(agents)})
            (scratch / "listing.json").write_text(json.dumps(listing), encoding="utf-8")
            lock = {"version": 3, "skills": {"skill-creator": {"skillFolderHash": folder_hash or self.WANT}}}
            (home / ".agents/.skill-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            for kind, relative in plant:
                path = scratch / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if kind == "folder":
                    path.mkdir()
                    (path / "SKILL.md").write_text(self.SKILL, encoding="utf-8")
                else:
                    path.symlink_to(scratch / "nowhere")
            stub.mkdir()
            (stub / "npx").write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >"$STUB_DIR/args"\ncat "$STUB_DIR/listing.json"\n',
                                      encoding="utf-8")
            (stub / "npx").chmod(0o755)
            env = {key: value for key, value in os.environ.items()
                   if key not in ("XDG_STATE_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "BASH_ENV", "ENV")}
            env.update(HOME=str(home), PATH=f"{stub}{os.pathsep}{os.environ.get('PATH', '')}", STUB_DIR=str(scratch))
            if codex_home:
                env["CODEX_HOME"] = str(scratch / "codex-home")
            result = subprocess.run(["bash", "-euo" if errexit else "-uo", "pipefail", "-c", self.program], env=env,
                                    capture_output=True, text=True, timeout=60)
            args = scratch / "args"
            return result.returncode, args.read_text(encoding="utf-8").strip() if args.exists() else None, result.stderr

    def test_the_program_is_the_one_accept_sh_runs(self):
        checker = load_source(PLAN / "check_plan.py", "check_plan")
        functions = checker.functions((PLAN / "accept.sh").read_text(encoding="utf-8"))
        self.assertEqual(checker.checks_of(functions["skill-authoring"]),
                         [("post_install", "skill-authoring", "smoke", self.program)])

    def test_the_expected_state_passes_and_the_listing_has_no_agent_filter(self):
        # Listed for Claude Code alone, the recorded tree hash, another skill in the shared directory and Codex's
        # embedded copy under skills/.system.
        status, args, stderr = self.run_case()
        self.assertEqual(status, 0, stderr)
        self.assertEqual(args, self.LISTING_ARGS)

    def test_each_planted_condition_fails_the_program(self):
        cases = {
            "the listing names Codex as well": dict(agents=("Claude Code", "Codex")),
            "the listing names Codex alone": dict(agents=("Codex",)),
            "the listing has no skill-creator": dict(agents=None),
            "the lock records another tree hash": dict(folder_hash="0" * 40),
            "a copy in the installer's shared directory": dict(plant=[("folder", "home/.agents/skills/skill-creator")]),
            "a dangling link in the installer's shared directory": dict(plant=[("dangling", "home/.agents/skills/skill-creator")]),
            "a copy in Codex's skills directory": dict(plant=[("folder", "home/.codex/skills/skill-creator")]),
            "a dangling link in Codex's skills directory": dict(plant=[("dangling", "home/.codex/skills/skill-creator")]),
            "a copy in the skills directory under CODEX_HOME": dict(codex_home=True,
                                                                    plant=[("folder", "codex-home/skills/skill-creator")]),
        }
        for name, case in cases.items():
            with self.subTest(case=name):
                status, args, stderr = self.run_case(**case)
                self.assertEqual(status, 1, stderr)
                self.assertEqual(args, self.LISTING_ARGS)

    def test_the_directory_conditions_do_not_rest_on_errexit(self):
        # Before bash 4.1 (macOS /bin/bash is 3.2) a failing [[ ]] does not stop a set -e script (bash NEWS, bash-4.1,
        # item j). The directory test is therefore the program's last command, and without -e its status is still the
        # program's: each planted copy or link fails the program on any bash.
        cases = {
            "a copy in the installer's shared directory": dict(plant=[("folder", "home/.agents/skills/skill-creator")]),
            "a dangling link in the installer's shared directory": dict(plant=[("dangling", "home/.agents/skills/skill-creator")]),
            "a copy in Codex's skills directory": dict(plant=[("folder", "home/.codex/skills/skill-creator")]),
            "a dangling link in Codex's skills directory": dict(plant=[("dangling", "home/.codex/skills/skill-creator")]),
            "a copy in the skills directory under CODEX_HOME": dict(codex_home=True,
                                                                    plant=[("folder", "codex-home/skills/skill-creator")]),
        }
        for name, case in cases.items():
            with self.subTest(case=name):
                status, _, stderr = self.run_case(errexit=False, **case)
                self.assertEqual(status, 1, stderr)


class StatuslineInstallAndAcceptance(unittest.TestCase):
    """The install plan's statusline row (claude-hud 0.10.0): its helper commands and its acceptance, against stand-ins.

    Review of 2026-10-03 ("Run claude-hud setup before wiring its copied launcher"): the row stopped after the plugin
    install, while the status line Claude Code runs names the launcher that upstream's helper copies to
    <config dir>/plugins/claude-hud/statusline.mjs, and the acceptance ran the cached launcher directly, so it passed with
    that copy missing. The row now runs the helper (scripts/setup.mjs inspect, then install, with --shell posix) and adds
    refreshInterval 5 when absent; the acceptance runs the configured command. Review of 2026-10-03 at 99a2e3c6: the
    helper keeps an earlier claude-hud statusLine with its refreshInterval (setup.mjs L94), and the acceptance, which
    required exactly 5, rejected that installed configuration; it now takes any positive integer, the settings schema's
    integer with minimum 1, and install then acceptance run on one scratch home. Review of 2026-10-03 at 06f6259f (macOS
    run 37141171758): the exact-one check of the cached versions compared the `wc -l` count as a string, which BSD and
    macOS wc pad; it now compares numbers, and stand-ins print both formats. Each program here is the row's own string
    in install-plan.json, run as install.sh and accept.sh run it (bash -euo pipefail -c), with a scratch HOME, a PATH of
    links to the system tools the programs use and a stand-in runtime that records its arguments and, as node does for a
    script file that is not there, fails unless its argument exists, else prints two lines. The fixtures are our own:
    upstream's helper and launcher do not run here.
    """

    INTERVAL_CHECK = '(.statusLine.refreshInterval | type == "number" and . >= 1 and . == floor)'
    INTERVAL_CHECK_BEFORE_REVIEW = ".statusLine.refreshInterval == 5"
    COUNT_CHECK = '"$versions" -eq 1'
    COUNT_CHECK_BEFORE_REVIEW = '"$versions" == 1'
    # The two printf formats of a `wc -l` count read from stdin: GNU coreutils prints the bare number; BSD and macOS wc
    # print " %7ju" (apple-oss-distributions/text_cmds@592aaf8a wc/wc.c L214-215), so one line reads "       1".
    WC_FORMATS = {"unpadded": "%d\\n", "padded": " %7d\\n"}

    TOOLS = ("bash", "sh", "jq", "ls", "wc", "cmp", "readlink", "mktemp", "chmod", "mv", "rm", "cat")
    LAUNCHER = "// claude-hud 0.10.0 launcher (stand-in)\n"
    RUNTIME = ('#!/bin/sh\nprintf \'%s\\n\' "$*" >>"${STUB_LOG:-/dev/null}"\ncase "$1" in */setup.mjs) exit 0 ;; esac\n'
               '[ -f "$1" ] || { printf "Error: Cannot find module %s\\n" "$1" >&2; exit 1; }\n'
               'cat >/dev/null\nprintf \'HUD line 1\\nHUD line 2\\n\'\n')

    @classmethod
    def setUpClass(cls):
        cls.tools = {name: shutil.which(name) for name in cls.TOOLS}
        if not all(cls.tools.values()):
            raise unittest.SkipTest(f"needs {', '.join(n for n, p in cls.tools.items() if not p)} to run the programs")
        cls.row = next(r for r in load(PLAN / "install-plan.json")["owners"] if r["slot"] == "statusline")
        cls.program = cls.row["acceptance"]["post_install"]["command"]
        cls.helper, cls.refresh = cls.row["commands"][2:]

    def run_program(self, program, scratch, runtime=True):
        """(exit status, stderr, the runtime's recorded calls) of one program, with HOME at <scratch>/home."""
        bin_dir = scratch / "bin"
        bin_dir.mkdir(exist_ok=True)
        for name, path in self.tools.items():
            if not (bin_dir / name).exists():
                (bin_dir / name).symlink_to(path)
        if runtime and not (bin_dir / "node").exists():
            (bin_dir / "node").write_text(self.RUNTIME, encoding="utf-8")
            (bin_dir / "node").chmod(0o755)
        log = scratch / "calls"
        env = {"HOME": str(scratch / "home"), "PATH": str(bin_dir), "STUB_LOG": str(log), "LANG": "C"}
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", program], env=env, capture_output=True, text=True,
                                timeout=60)
        calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return result.returncode, result.stderr, calls

    def cache(self, scratch, version="0.10.0", marketplace="claude-hud"):
        scripts = scratch / "home/.claude/plugins/cache" / marketplace / "claude-hud" / version / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "statusline.mjs").write_text(self.LAUNCHER, encoding="utf-8")
        (scripts / "setup.mjs").write_text("// stand-in\n", encoding="utf-8")
        return scripts

    def test_the_programs_are_the_ones_the_scripts_run(self):
        checker = load_source(PLAN / "check_plan.py", "check_plan")
        accept = checker.functions((PLAN / "accept.sh").read_text(encoding="utf-8"))
        self.assertEqual(checker.checks_of(accept["statusline"]), [("post_install", "statusline", "smoke", self.program)])
        install = checker.functions((PLAN / "install.sh").read_text(encoding="utf-8"))
        self.assertEqual(checker.run_commands("statusline", install, set()), self.row["commands"])

    def test_the_helper_runs_inspect_then_install_from_the_one_pinned_cache(self):
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            scripts = self.cache(scratch)
            status, stderr, calls = self.run_program(self.helper, scratch)
            self.assertEqual(status, 0, stderr)
            self.assertEqual(calls, [f"{scripts}/setup.mjs inspect --shell posix", f"{scripts}/setup.mjs install --shell posix"])
        for name, plant, message in (
                ("no cached 0.10.0", lambda scratch: self.cache(scratch, version="0.9.0"), "not in exactly one marketplace"),
                ("0.10.0 in two marketplaces", lambda scratch: (self.cache(scratch), self.cache(scratch, marketplace="m2")),
                 "not in exactly one marketplace"),
                ("no node or bun", lambda scratch: self.cache(scratch), "no node or bun")):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                plant(scratch)
                status, stderr, calls = self.run_program(self.helper, scratch, runtime=name != "no node or bun")
                self.assertEqual(status, 1, stderr)
                self.assertIn(message, stderr)
                self.assertEqual(calls, [])

    def skip_without_gnu_coreutils(self):
        chmod = subprocess.run([self.tools["chmod"], "--version"], capture_output=True, text=True)
        if "GNU coreutils" not in chmod.stdout:
            self.skipTest("the command uses GNU chmod --reference and readlink -f, as on the plan's Ubuntu")

    def test_refresh_interval_5_is_added_only_when_absent_in_the_file_itself(self):
        self.skip_without_gnu_coreutils()
        status_line = {"type": "command", "command": "'/x/node' '/x/statusline.mjs'"}
        for name, before, link in (("absent", status_line, False), ("absent, through a link", status_line, True),
                                   ("present", dict(status_line, refreshInterval=3), False)):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                config = scratch / "home/.claude"
                config.mkdir(parents=True)
                target = scratch / "dotfiles/settings.json" if link else config / "settings.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                text = json.dumps({"theme": "dark", "statusLine": before}, indent=2) + "\n"
                target.write_text(text, encoding="utf-8")
                target.chmod(0o640)
                if link:
                    (config / "settings.json").symlink_to(target)
                status, stderr, _ = self.run_program(self.refresh, scratch)
                self.assertEqual(status, 0, stderr)
                if "refreshInterval" in before:
                    self.assertEqual(target.read_text(encoding="utf-8"), text)
                else:
                    self.assertEqual(load(target), {"theme": "dark", "statusLine": dict(before, refreshInterval=5)})
                self.assertEqual(target.stat().st_mode & 0o777, 0o640)
                self.assertEqual((config / "settings.json").is_symlink(), link)
                self.assertEqual(sorted(p.name for p in target.parent.iterdir()), ["settings.json"])  # no temporary left

    def plant(self, scratch, launcher="same", refresh=5, second_version=False, run_cached=False):
        """A scratch home as the plugin install and upstream's helper leave it: the cached 0.10.0, its user-scope entry, the
        launcher copy (setup.mjs L79-80) and a statusLine that runs it, with an earlier claude-hud statusLine's other keys
        kept (L94), here refreshInterval. Returns the settings.json path."""
        config = scratch / "home/.claude"
        scripts = self.cache(scratch)
        if second_version:
            self.cache(scratch, version="0.9.0")
        (config / "plugins/installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"claude-hud@claude-hud": [{"scope": "user", "version": "0.10.0"}]}}), encoding="utf-8")
        copy = config / "plugins/claude-hud/statusline.mjs"
        if launcher is not None:
            copy.parent.mkdir(parents=True)
            copy.write_text(self.LAUNCHER if launcher == "same" else "// another version's launcher\n", encoding="utf-8")
        runs = scripts / "statusline.mjs" if run_cached else copy
        status_line = {"type": "command", "command": f"'{scratch}/bin/node' '{runs}'"}
        if refresh is not None:
            status_line["refreshInterval"] = refresh
        settings = config / "settings.json"
        settings.write_text(json.dumps({"theme": "dark", "statusLine": status_line}), encoding="utf-8")
        return settings

    def stand_in_wc(self, bin_dir, form):
        """A wc in <bin_dir> that takes only -l on stdin, counts with the system wc and prints the count in WC_FORMATS[form],
        whatever the system wc's own format; run_program keeps it in place of the link to the system wc."""
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "wc").write_text(
            '#!/bin/sh\n[ "$#" -eq 1 ] && [ "$1" = -l ] || { echo "stand-in wc: only -l on stdin" >&2; exit 2; }\n'
            f"""printf '{self.WC_FORMATS[form]}' "$(( $('{self.tools["wc"]}' -l) ))"\n""", encoding="utf-8")
        (bin_dir / "wc").chmod(0o755)

    def acceptance(self, program=None, wc=None, **state):
        """The acceptance's exit status and stderr for one state of a scratch home; `wc`, a key of WC_FORMATS, runs it with
        the stand-in wc that prints that format."""
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            self.plant(scratch, **state)
            if wc is not None:
                self.stand_in_wc(scratch / "bin", wc)
            status, stderr, _ = self.run_program(program or self.program, scratch)
            return status, stderr

    def install_then_accept(self, before, program=None):
        """(settings.json as planted, as install leaves it, the acceptance's exit status and stderr) on one scratch home.

        The helper's writes are planted (see plant; refreshInterval `before`, None for absent); then the row's helper
        command (the stand-in runtime) and its refreshInterval command run as install.sh runs them, and the acceptance
        reads the file they leave."""
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            settings = self.plant(scratch, refresh=before)
            planted = settings.read_text(encoding="utf-8")
            for step in (self.helper, self.refresh):
                status, stderr, _ = self.run_program(step, scratch)
                self.assertEqual(status, 0, stderr)
            installed = settings.read_text(encoding="utf-8")
            status, stderr, _ = self.run_program(program or self.program, scratch)
            return planted, installed, status, stderr

    def test_the_acceptance_passes_what_install_leaves_an_added_5_or_a_kept_earlier_value(self):
        self.skip_without_gnu_coreutils()
        for name, before, after in (("absent before install: 5 added", None, 5), ("an earlier claude-hud 3: kept", 3, 3)):
            with self.subTest(case=name):
                planted, installed, status, stderr = self.install_then_accept(before)
                expected = json.loads(planted)
                expected["statusLine"]["refreshInterval"] = after
                self.assertEqual(json.loads(installed), expected)
                if before is not None:
                    self.assertEqual(installed, planted)  # the refreshInterval command leaves the file as it was
                self.assertEqual(status, 0, stderr)

    def test_the_interval_check_before_the_review_rejected_the_kept_value(self):
        """Negative control: the same install-then-acceptance run with the check as it was at 99a2e3c6 (exactly 5)."""
        self.skip_without_gnu_coreutils()
        self.assertEqual(self.program.count(self.INTERVAL_CHECK), 1)
        before_review = self.program.replace(self.INTERVAL_CHECK, self.INTERVAL_CHECK_BEFORE_REVIEW)
        for before, passes in ((None, True), (3, False)):
            with self.subTest(before=before):
                _, _, status, stderr = self.install_then_accept(before, before_review)
                self.assertEqual(status == 0, passes, stderr)

    def test_the_acceptance_passes_the_wired_state_and_fails_each_planted_condition(self):
        for refresh in (5, 1, 3):
            with self.subTest(passes=f"refreshInterval {refresh}"):
                status, stderr = self.acceptance(refresh=refresh)
                self.assertEqual(status, 0, stderr)
        cases = {
            "the copied launcher the configured command runs is missing (the reviewed case)": dict(launcher=None),
            "no refreshInterval": dict(refresh=None),
            "a non-numeric refreshInterval": dict(refresh="five"),
            "a refreshInterval in a string": dict(refresh="5"),
            "a zero refreshInterval": dict(refresh=0),
            "a negative refreshInterval": dict(refresh=-5),
            "a fractional refreshInterval": dict(refresh=2.5),
            "the copied launcher is another version's": dict(launcher="other"),
            "a second cached version": dict(second_version=True),
            "the configured command runs the cached launcher, not the copy": dict(run_cached=True),
        }
        for name, case in cases.items():
            with self.subTest(case=name):
                status, stderr = self.acceptance(**case)
                self.assertNotEqual(status, 0, stderr)

    def test_the_acceptance_takes_the_count_padded_or_not_and_still_requires_one_version(self):
        """macOS run 37141171758 (at 2f5d8b01): the wired state with refreshInterval 5, 1 and 3 exited 1 there, with an empty
        stderr. Here each wc format runs through its stand-in, so the case does not rest on the host's own wc."""
        self.assertEqual(self.program.count(self.COUNT_CHECK), 1)
        for form in self.WC_FORMATS:
            for refresh in (5, 1, 3):
                with self.subTest(wc=form, passes=f"refreshInterval {refresh}"):
                    status, stderr = self.acceptance(wc=form, refresh=refresh)
                    self.assertEqual(status, 0, stderr)
            with self.subTest(wc=form, fails="a second cached version"):
                status, stderr = self.acceptance(wc=form, second_version=True)
                self.assertNotEqual(status, 0, stderr)

    def test_the_count_check_before_the_review_rejected_the_padded_count(self):
        """Negative control: the wired state, with the exact-one check as it was at 06f6259f (a string comparison)."""
        before_review = self.program.replace(self.COUNT_CHECK, self.COUNT_CHECK_BEFORE_REVIEW)
        for form, passes in (("unpadded", True), ("padded", False)):
            with self.subTest(wc=form):
                status, stderr = self.acceptance(before_review, wc=form)
                self.assertEqual(status == 0, passes, stderr)


class LocalModelAcceptance(unittest.TestCase):
    """Run the actual CURRENT-provider commands against independent HTTP fixtures.

    NVIDIA@d1f2f257 README:100-129 defines 4096/L2/query/passage;
    vLLM@db9527a docs/serving/online_serving/openai_compatible_server.md
    defines the native HTTP API. These are synthetic integration controls.
    """

    MODEL = "nvidia/Nemotron-3-Embed-8B-BF16"

    def row(self):
        return next(row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]
                    if row["slot"] == "embedding-model")

    def models(self):
        return {"data": [{"id": self.MODEL}]}

    def vectors(self):
        vector = [1.0] + [0.0] * 4095
        return {"model": self.MODEL, "data": [
            {"index": 0, "embedding": list(vector)},
            {"index": 1, "embedding": list(vector)},
        ]}

    def run_program(self, scratch, command, models, vectors=None, curl_exit=0):
        stub = scratch / "bin"
        stub.mkdir()
        (scratch / "models.json").write_text(json.dumps(models))
        (scratch / "vectors.json").write_text(json.dumps(vectors or self.vectors()))
        curl = stub / "curl"
        curl.write_text("#!/usr/bin/env python3\n" + r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
root = Path(os.environ["MODEL_FIXTURE"])
url = args[-1]
body = args[args.index("--data-binary") + 1] if "--data-binary" in args else None
with (root / "calls.jsonl").open("a") as out:
    out.write(json.dumps({"url": url, "body": body}) + "\n")
if int(os.environ["CURL_FIXTURE_EXIT"]):
    sys.exit(int(os.environ["CURL_FIXTURE_EXIT"]))
assert url in ("http://127.0.0.1:28231/v1/models", "http://127.0.0.1:28231/v1/embeddings")
destination = Path(args[args.index("--output") + 1])
destination.write_bytes((root / ("models.json" if url.endswith("/models") else "vectors.json")).read_bytes())
''')
        curl.chmod(0o755)
        env = {key: value for key, value in os.environ.items() if key not in ("BASH_ENV", "ENV")}
        env.update(MODEL_FIXTURE=str(scratch), CURL_FIXTURE_EXIT=str(curl_exit),
                   PYTHONOPTIMIZE="1",
                   XDG_STATE_HOME=str(scratch / "state"), HOME=str(scratch / "home"),
                   PATH=f"{stub}{os.pathsep}{os.environ.get('PATH', '')}")
        return subprocess.run(["bash", "-euo", "pipefail", "-c", command], env=env,
                              capture_output=True, text=True, timeout=60)

    def test_the_programs_are_the_ones_accept_sh_runs(self):
        checker = load_source(PLAN / "check_plan.py", "current_model_checker")
        row = self.row()
        install = checker.functions((PLAN / "install.sh").read_text())
        accept = checker.functions((PLAN / "accept.sh").read_text())
        self.assertEqual(checker.run_commands("embedding-model", install, set()), row["commands"])
        self.assertEqual(row["commands"], [row["acceptance"]["post_install"]["command"]])
        native_checks = {stage: program for stage, slot, kind, program in checker.checks_of(accept["embedding-model"])}
        for stage in ("post_install", "service_health"):
            self.assertEqual(row["acceptance"][stage]["command"], native_checks[stage])

    def test_current_identity_positive_and_mismatch_or_unavailable_controls(self):
        cases = [
            ("selected", self.models(), 0, 0),
            ("other model", {"data": [{"id": "retired/Qwen"}]}, 0, 1),
            ("empty registry", {"data": []}, 0, 1),
            ("ambiguous registry", {"data": [{"id": self.MODEL}, {"id": "other"}]}, 0, 1),
            ("missing registry", {"error": "unavailable"}, 0, 1),
            ("failed transport", self.models(), 7, 1),
        ]
        for name, reply, exit_code, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                result = self.run_program(Path(scratch), self.row()["commands"][0], reply, curl_exit=exit_code)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected:
                    self.assertIn("needs_owner:", result.stderr)

    def test_actual_http_health_requires_identity_indices_dimensions_finiteness_and_normalization(self):
        cases = {"selected": self.vectors()}
        wrong = self.vectors(); wrong["model"] = "other"; cases["wrong model"] = wrong
        wrong = self.vectors(); wrong["data"][1]["index"] = 0; cases["duplicate index"] = wrong
        wrong = self.vectors(); wrong["data"][0]["embedding"].pop(); cases["wrong dimensions"] = wrong
        wrong = self.vectors(); wrong["data"][0]["embedding"][0] = float("nan"); cases["nonfinite"] = wrong
        wrong = self.vectors(); wrong["data"][0]["embedding"] = [True] + [False] * 4095; cases["bool vector"] = wrong
        wrong = self.vectors(); wrong["data"][0]["embedding"] = [0.0] * 4096; cases["zero vector"] = wrong
        wrong = self.vectors(); wrong["data"][0]["embedding"][0] = 2.0; cases["unnormalized"] = wrong
        for name, reply in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                path = Path(scratch)
                result = self.run_program(path, self.row()["acceptance"]["service_health"]["command"],
                                          self.models(), reply)
                self.assertEqual(result.returncode, 0 if name == "selected" else 1, result.stderr)
                calls = [json.loads(line) for line in (path / "calls.jsonl").read_text().splitlines()]
                self.assertEqual([item["url"] for item in calls],
                                 ["http://127.0.0.1:28231/v1/models", "http://127.0.0.1:28231/v1/embeddings"])
                payload = json.loads(calls[1]["body"])
                self.assertEqual(payload["model"], self.MODEL)
                self.assertEqual(payload["input"], ["query: current provider integration fixture",
                                                   "passage: current provider integration fixture"])
                outputs = list((path / "state/new-wsl-native-stack/acceptance/embedding-model").glob("current.*/*.json"))
                self.assertEqual(len(outputs), 2)
                self.assertTrue(all(item.stat().st_mode & 0o777 == 0o600 for item in outputs))


class ModelServerGuard(unittest.TestCase):
    """Retirement means no executable server/model path; history remains immutable."""

    def test_retired_rows_have_no_executable_install_or_acceptance(self):
        import tomllib
        rows = {row["slot"]: row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]}
        checker = load_source(PLAN / "check_plan.py", "retired_model_checker")
        for filename in ("install.sh", "accept.sh"):
            functions = checker.functions((PLAN / filename).read_text())
            self.assertNotIn("local-model-server", functions)
            self.assertNotIn("local-generation-model", functions)
            self.assertNotIn("model_server_answers", functions)
        for slot in ("local-model-server", "local-generation-model"):
            row = rows[slot]
            self.assertFalse(row["installed"])
            self.assertEqual(row["route"], "none")
            self.assertEqual(row["commands"], [])
            self.assertEqual(row["acceptance"], {})
            self.assertEqual(row["config_paths"], [])
            self.assertIsNone(row["service"])
            self.assertFalse(any(row["needs"].values()))
            self.assertEqual(row["retired_by"], "2026-10-06-retrieval-first-local-models")
        self.assertNotIn("ollama", tomllib.loads((PLAN / "mise.toml").read_text())["tools"])

    def test_historical_unit_is_preserved_and_never_copied(self):
        self.assertEqual(hashlib.sha256((PLAN / "config/ollama.service").read_bytes()).hexdigest(),
                         "5e8e8bc42306f2d1ebc6da912e34daa28c6ce73eccf793d3155851733dccc6db")
        rows = {row["slot"]: row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]}
        self.assertEqual(set(rows["local-model-server"]["historical_config_assets"]),
                         {"ollama.env.example", "ollama.service"})
        installer = (PLAN / "install.sh").read_text()
        for asset in ("ollama.env.example", "ollama.service"):
            self.assertNotIn(f"copy_config '{asset}'", installer)


class PromptfooGatewayTopologyConfiguration(unittest.TestCase):
    """Synthetic native-config loading; no gateway, provider or account calls."""

    def render(self, topology, env=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(PLAN / "config/promptfoo-gateway.cjs", root / "promptfoo-gateway.cjs")
            (root / "gpt-gateway-topology.json").write_text(json.dumps(topology))
            return subprocess.run(
                ["node", "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))",
                 str(root / "promptfoo-gateway.cjs")],
                env={**{key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ},
                     **(env or {})}, capture_output=True, text=True, timeout=10,
            )

    def topology(self):
        return {"gateway": {"endpoint": "http://127.0.0.1:21128/v1"},
                "pool_fallback": {"model": "fixture/gpt-a", "model_reasoning_effort": "xhigh"},
                "promptfoo": {"claude_model": "fixture/claude-a"}}

    def test_both_providers_follow_changed_canonical_routes_on_the_owned_endpoint(self):
        import copy
        original = self.topology()
        changed = copy.deepcopy(original)
        changed["pool_fallback"]["model"] = "fixture/gpt-b"
        changed["promptfoo"]["claude_model"] = "fixture/claude-b"
        for topology in (original, changed):
            with self.subTest(topology=topology):
                result = self.render(topology)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(result.stdout)
                self.assertEqual([p["id"] for p in config["providers"]],
                                 ["openai:chat:" + topology["pool_fallback"]["model"],
                                  "openai:chat:" + topology["promptfoo"]["claude_model"]])
                self.assertEqual({p["config"]["apiBaseUrl"] for p in config["providers"]},
                                 {topology["gateway"]["endpoint"]})
                self.assertFalse(config["sharing"])
                self.assertEqual(config["providers"][0]["config"]["reasoning_effort"], "xhigh")
                self.assertNotIn("reasoning_effort", config["providers"][1]["config"])
                self.assertTrue(all(p["config"]["omitDefaults"] for p in config["providers"]))

    def test_synthetic_node_load_does_not_inherit_unrelated_ambient_variables(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {"PROMPTFOO_AMBIENT_FIXTURE": "synthetic-unused-ambient"}):
            with mock.patch("subprocess.run", wraps=subprocess.run) as run:
                result = self.render(self.topology())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PROMPTFOO_AMBIENT_FIXTURE", run.call_args.kwargs["env"])
        self.assertLessEqual(set(run.call_args.kwargs["env"]), {"PATH", "TMPDIR"})

    def test_config_keeps_only_the_inventory_key_pointer(self):
        sentinel = "SYNTHETIC_UNUSED_ENVIRONMENT_VALUE"
        result = self.render(self.topology(), {"OMNIROUTE_API_KEY": sentinel})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(sentinel, result.stdout + result.stderr)
        config = json.loads(result.stdout)
        self.assertNotIn("env", config)
        inventory = load(ROOT / "adoption/credential-inventory.json")
        entry = next(r for r in inventory["entries"] if r["id"] == "omniroute")
        for provider in config["providers"]:
            self.assertEqual(provider["config"]["apiKeyEnvar"], "OMNIROUTE_API_KEY")
            self.assertIn(provider["config"]["apiKeyEnvar"], entry["variables"])
            self.assertNotIn("apiKey", provider["config"])
            self.assertFalse(provider["config"]["apiKeyRequired"])
            self.assertFalse(provider["config"]["useDefaultApiKey"])

    def test_native_client_result_oracles_require_the_frozen_pair(self):
        import copy
        expected = ["openai:chat:fixture/gpt-a", "openai:chat:fixture/claude-a"]
        native = {"tool": "run_evaluation", "success": True, "data": {
            "eval": {"status": "completed"},
            "configuration": {"options": {"cache": False, "share": False}},
            "results": {"totalEvals": 2, "stats": {"successes": 2, "failures": 0, "errors": 0},
                        "results": [{"provider": {"id": value}, "eval": {"success": True}}
                                    for value in expected]}}}
        for client in ("claude", "codex"):
            for case in ("valid", "reordered", "other-gpt", "other-claude", "two-gpt", "failed"):
                with self.subTest(client=client, case=case):
                    result = copy.deepcopy(native)
                    rows = result["data"]["results"]["results"]
                    if case == "reordered":
                        rows.reverse()
                    elif case == "other-gpt":
                        rows[0]["provider"]["id"] = "openai:chat:fixture/gpt-b"
                    elif case in ("other-claude", "two-gpt"):
                        rows[1]["provider"]["id"] = "openai:chat:fixture/" + (
                            "claude-b" if case == "other-claude" else "gpt-b")
                    elif case == "failed":
                        result["data"]["results"]["stats"]["failures"] = 1
                    if client == "claude":
                        events = [{"type": "assistant", "message": {"content": [{
                            "type": "tool_use", "name": "mcp__promptfoo__run_evaluation", "id": "fixture-call"}]}},
                                  {"type": "user", "message": {"content": [{
                                      "type": "tool_result", "tool_use_id": "fixture-call", "content": json.dumps(result)}]}},
                                  {"type": "result", "is_error": False}]
                    else:
                        events = [{"type": "item.completed", "item": {
                            "type": "mcp_tool_call", "server": "promptfoo", "tool": "run_evaluation",
                            "status": "completed", "error": None,
                            "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}},
                                  {"type": "turn.completed"}]
                    observed = subprocess.run(
                        ["jq", "-s", "-e", "--arg", "client", client, "--argjson", "expected",
                         json.dumps(expected), "-f", str(PLAN / "config/promptfoo-session.jq")],
                        input="\n".join(json.dumps(event) for event in events),
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(observed.returncode, 0 if case in ("valid", "reordered") else 1,
                                     observed.stderr)

    def test_missing_placeholder_and_duplicate_routes_fail_closed(self):
        import copy
        baseline = self.topology()
        for field, bad_value in (("endpoint", None), ("endpoint", "gateway.example.com"),
                                 ("endpoint", "https://gateway.example.com/v1"),
                                 ("endpoint", "http://127.0.0.1:21991/v1"),
                                 ("endpoint", "http://127.0.0.1.example.com:21128/v1"),
                                 ("endpoint", "http://evil.example:21128/v1?gateway.example.com"),
                                 ("endpoint", "http://127.0.0.1:21128@evil.example/v1"),
                                 ("endpoint", "http://evil.example:21128/127.0.0.1/v1"),
                                 ("endpoint", "http://127.0.0.1:21128/v1#ignored"),
                                 ("endpoint", "http://127.0.0.1:21128/v1?ignored=1"),
                                 ("endpoint", "https://127.0.0.1:21128/v1"),
                                 ("gpt", None), ("gpt", "your-gpt-model-id"),
                                 ("gpt", "fixture/gpt\x00a"),
                                 ("claude", None), ("claude", "your-claude-model-id"),
                                 ("claude", "fixture/gpt-a"), ("claude", "fixture/claude a")):
            with self.subTest(field=field, bad_value=bad_value):
                topology = copy.deepcopy(baseline)
                target, key = {"endpoint": ("gateway", "endpoint"),
                               "gpt": ("pool_fallback", "model"),
                               "claude": ("promptfoo", "claude_model")}[field]
                topology[target][key] = bad_value
                result = self.render(topology)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("plan gateway topology must declare", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_explicit_owner_pending_is_78_before_config_loading(self):
        import copy
        import importlib.util
        import shlex
        command = next(row for row in load(PLAN / "install-plan.json")["owners"]
                       if row["slot"] == "promptfoo")["acceptance"]["after_sign_in"]["command"]
        preflight = command.split('\nexpected="', 1)[0]
        spec = importlib.util.spec_from_file_location("pending_plan_checker", PLAN / "check_plan.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        functions = checker.functions((PLAN / "accept.sh").read_text())
        dispatcher = functions["check"]
        tokens = shlex.split(functions["promptfoo"], comments=True)
        pending_kind = tokens[tokens.index(command) + 1]
        self.assertEqual(pending_kind, "needs_owner")
        pending = self.topology()
        pending["promptfoo"] = {}
        pending["gateway"]["claude_route"] = "pending canonical owner decision; no guessed binding"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            # A poison config proves the preflight does not load it or run providers.
            (root / "config/promptfoo-gateway.cjs").write_text('throw new Error("CONFIG_LOADED");')
            for case in ("pending", "supplied-bad-route", "missing-ownership", "wrong-port",
                         "endpoint-array", "promptfoo-array", "promptfoo-string", "promptfoo-null", "gpt-nul"):
                with self.subTest(case=case):
                    topology = copy.deepcopy(pending)
                    if case == "supplied-bad-route":
                        topology["promptfoo"]["claude_model"] = "your-claude-model-id"
                    elif case == "missing-ownership":
                        del topology["gateway"]["claude_route"]
                    elif case == "wrong-port":
                        topology["gateway"]["endpoint"] = "http://127.0.0.1:20128/v1"
                    elif case == "endpoint-array":
                        topology["gateway"]["endpoint"] = [topology["gateway"]["endpoint"]]
                    elif case.startswith("promptfoo-"):
                        topology["promptfoo"] = {"promptfoo-array": [], "promptfoo-string": "bad",
                                                 "promptfoo-null": None}[case]
                    elif case == "gpt-nul":
                        topology["pool_fallback"]["model"] = "fixture/gpt\x00a"
                    (root / "config/gpt-gateway-topology.json").write_text(json.dumps(topology))
                    program = preflight + '\nnode "$gateway"'
                    stage = ('stage=after_sign_in; failed=0; prepare_path() { :; };\ncheck() {\n' +
                             dispatcher + '\n}\ncheck promptfoo smoke ' + shlex.quote(program) +
                             ' ' + pending_kind + '\nexit "$failed"')
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", stage],
                                            env={"PATH": os.environ["PATH"], "HOME": str(root),
                                                 "plan_dir": str(root)},
                                            capture_output=True, text=True, timeout=10)
                    if case == "pending":
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "promptfoo | after_sign_in | needs_owner (78)\n")
                        self.assertIn("needs_owner:", result.stderr)
                        self.assertNotIn("CONFIG_LOADED", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertNotIn("needs_owner (78)", result.stdout)
                        self.assertNotIn("needs_user", result.stdout)


class FixwaveAcceptanceRepairs(unittest.TestCase):
    """Local regression checks of native argv, task paths and owned alias migration."""

    def row(self, slot):
        return next(r for r in load(PLAN / "install-plan.json")["owners"] if r["slot"] == slot)

    def test_gateway_example_retention_and_nonregular_preflight(self):
        # Independent filesystem control of the preflight seam and copy_config:
        # native-agent-stack@84c79f7f:install.sh:82-126.
        command = self.row("gpt-gateway")["commands"][0]
        loop_start = command.index('for gateway_name in "gpt-gateway-topology.json"')
        loop_end = command.index('; for gateway_name in omniroute-serve.sh', loop_start)
        staged_loop = command[loop_start:loop_end]
        install_text = (PLAN / "install.sh").read_text()
        copy_start = install_text.index("copy_config() {")
        copy_end = install_text.index("\n}\n", copy_start) + 3
        copy_function = install_text[copy_start:copy_end]
        guard = 'gateway_asset_known() { return 1; }; gateway_needs_owner() { printf "needs_owner: %s\\n" "$1" >&2; exit 1; }; '
        for mode in ("regular", "symlink", "dangling", "directory", "unknown_asset"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                plan_dir, config_root = root / "plan", root / "config"
                (plan_dir / "config").mkdir(parents=True)
                config_root.mkdir()
                (plan_dir / "config/omniroute.env.example").write_bytes(b"approved example\n")
                target = config_root / "omniroute.env.example"
                retained = b"operator example bytes\n"
                external = root / "outside-example"
                if mode in ("regular", "unknown_asset"):
                    target.write_bytes(retained)
                elif mode in ("symlink", "dangling"):
                    if mode == "symlink":
                        external.write_bytes(retained)
                    target.symlink_to(external)
                else:
                    target.mkdir()
                if mode == "unknown_asset":
                    (config_root / "gpt-gateway-topology.json").write_bytes(retained)
                env = {"PATH": os.environ["PATH"], "plan_dir": str(plan_dir), "config_root": str(config_root)}
                result = subprocess.run(
                    ["bash", "-euo", "pipefail", "-c", copy_function + "\n" + guard + staged_loop + "; copy_config omniroute.env.example"],
                    env=env, capture_output=True, text=True, timeout=10,
                )
                if mode == "regular":
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("retained", result.stderr)
                    self.assertEqual(target.read_bytes(), retained)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("needs_owner", result.stderr)
                    if mode in ("symlink", "dangling"):
                        self.assertTrue(target.is_symlink())
                        self.assertEqual(os.readlink(target), str(external))
                        if mode == "symlink":
                            self.assertEqual(external.read_bytes(), retained)
                    elif mode == "directory":
                        self.assertTrue(target.is_dir())
                    else:
                        self.assertEqual(target.read_bytes(), retained)
                        self.assertEqual((config_root / "gpt-gateway-topology.json").read_bytes(), retained)

    def test_hcom_start_capture_selects_one_native_base_name(self):
        # hcom@2c5f343: start.rs:843-848 deliberately repeats the marker;
        # tests/support/mod.rs:949-959 selects its first occurrence.
        command = self.row("agent-messaging")["acceptance"]["post_install"]["command"]
        begin = command.index('sender="$(')
        end = command.index('\n"${isolated[@]}" "$hcom_binary" send "@$recipient"')
        selection = command[begin:end]
        cases = [
            ("repeated bootstrap", "[hcom:nova]\nbootstrap\n[hcom:nova]\n",
             "[hcom:luna]\nbootstrap\n[hcom:luna]\n", ("nova", "luna")),
            ("native trim", "  [hcom:nova]\n[hcom:nova]\n", "\t[hcom:luna]\n", ("nova", "luna")),
            ("native base characters", "[hcom:_7]\n[hcom:_7]\n", "[hcom:2lane]\n", ("_7", "2lane")),
            ("trailing bootstrap", "[hcom:nova] continued\n[hcom:nova]\n", "[hcom:luna]\n", ("nova", "luna")),
            ("empty capture", "", "[hcom:luna]\n", None),
            ("empty marker", "[hcom:]\n", "[hcom:luna]\n", None),
            ("invalid base", "[hcom:bad-name]\n", "[hcom:luna]\n", None),
            ("uppercase base", "[hcom:Nova]\n", "[hcom:luna]\n", None),
            ("first marker invalid", "[hcom:bad-name]\n[hcom:nova]\n", "[hcom:luna]\n", None),
            ("same identity", "[hcom:nova]\n", "[hcom:nova]\n", None),
            ("narrative marker", "bootstrap mentions [hcom:nova]\n", "[hcom:luna]\n", None),
        ]
        for name, sender, recipient, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "sender.txt").write_text(sender)
                (root / "recipient.txt").write_text(recipient)
                env = {"PATH": os.environ["PATH"], "smoke": str(root), "TMPDIR": str(root)}
                result = subprocess.run(
                    ["bash", "-euo", "pipefail", "-c", selection + '\nprintf "%s\\n" "$sender" "$recipient"'],
                    env=env, capture_output=True, text=True, timeout=10,
                )
                if expected is None:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(tuple(result.stdout.splitlines()), expected)

    def test_skillspector_scans_bind_the_native_topology_model_and_keep_report_gates(self):
        # Local integration fixture for the native SKILLSPECTOR_MODEL carrier.
        # No Codex sign-in, scan provider, credential store or model is contacted.
        command = self.row("skill-vetting")["acceptance"]["after_sign_in"]["command"]
        self.assertIn('"$plan_dir/config/gpt-gateway-topology.json"', command)
        cases = [
            ("native", {"model_provider": "openai", "model": "fixture-native"}, "complete", "fixture-native"),
            ("canonical change", {"model_provider": "openai", "model": "fixture-next"}, "complete", "fixture-next"),
            ("empty", {"model_provider": "openai", "model": ""}, "complete", None),
            ("missing model", {"model_provider": "openai"}, "complete", None),
            ("wrong type", {"model_provider": "openai", "model": 42}, "complete", None),
            ("wrong provider", {"model_provider": "omniroute", "model": "fixture-native"}, "complete", None),
            ("incomplete malicious", {"model_provider": "openai", "model": "fixture-native"}, "bad-incomplete", None),
            ("incomplete safe", {"model_provider": "openai", "model": "fixture-native"}, "safe-incomplete", None),
            ("obsolete findings field", {"model_provider": "openai", "model": "fixture-native"}, "bad-legacy-field", None),
            ("malformed issues", {"model_provider": "openai", "model": "fixture-native"}, "bad-issues-type", None),
            ("safe no meta needed", {"model_provider": "openai", "model": "fixture-native"}, "safe-no-meta", "fixture-native"),
            ("safe static only", {"model_provider": "openai", "model": "fixture-native"}, "safe-no-calls", None),
            ("safe partial calls", {"model_provider": "openai", "model": "fixture-native"}, "safe-partial-calls", None),
            ("safe boolean counters", {"model_provider": "openai", "model": "fixture-native"}, "safe-bool-calls", None),
            ("safe findings", {"model_provider": "openai", "model": "fixture-native"}, "safe-issues", None),
            ("malicious static only", {"model_provider": "openai", "model": "fixture-native"}, "bad-no-calls", None),
            ("malicious partial calls", {"model_provider": "openai", "model": "fixture-native"}, "bad-partial-calls", None),
            ("malicious missing meta", {"model_provider": "openai", "model": "fixture-native"}, "bad-no-meta", None),
            ("safe degraded", {"model_provider": "openai", "model": "fixture-native"}, "safe-degraded", None),
        ]
        for name, route, report_case, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binary = root / "bin"
                binary.mkdir()
                config = root / "plan/config"
                config.mkdir(parents=True)
                (config / "gpt-gateway-topology.json").write_text(json.dumps({
                    "sol_max": route, "pool_fallback": {"model": "cx/fixture-unrelated", "model_reasoning_effort": "xhigh"},
                }))
                (binary / "codex").write_text("#!/bin/sh\n[ \"$*\" = 'login status' ]\n")
                (binary / "uv").write_text("#!/bin/sh\n[ \"$*\" = 'tool dir' ] || exit 42\nprintf '%s\\n' \"$FIXTURE_UV_TOOLS\"\n")
                (binary / "skillspector").write_text(
                    "#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\n"
                    "assert os.environ['SKILLSPECTOR_PROVIDER'] == 'codex_cli'\n"
                    "args=sys.argv[1:]; bad='malicious_skill' in args[1]\n"
                    "with open(os.environ['FIXTURE_CALLS'],'a') as f: f.write(json.dumps({'model':os.environ.get('SKILLSPECTOR_MODEL'),'bad':bad})+'\\n')\n"
                    "case=os.environ['FIXTURE_REPORT_CASE']\n"
                    "complete=not ((bad and case=='bad-incomplete') or (not bad and case=='safe-incomplete'))\n"
                    "report={'analysis_completeness':{'is_complete':complete},'execution_successful':True,'issues':[{'fixture':True}] if bad else [],"
                    "'metadata':{'llm_requested':True,'llm_available':True,'meta_analysis_applied':bad,'llm_calls_attempted':3,'llm_calls_succeeded':3}}\n"
                    "if bad and case=='bad-legacy-field': report['findings']=report.pop('issues')\n"
                    "if bad and case=='bad-issues-type': report['issues']='invalid'\n"
                    "if not bad and case=='safe-no-calls': report['metadata'].update(llm_calls_attempted=0,llm_calls_succeeded=0)\n"
                    "if not bad and case=='safe-partial-calls': report['metadata']['llm_calls_succeeded']=2\n"
                    "if not bad and case=='safe-bool-calls': report['metadata'].update(llm_calls_attempted=True,llm_calls_succeeded=True)\n"
                    "if not bad and case=='safe-issues': report['issues']=[{'fixture':True}]\n"
                    "if bad and case=='bad-no-calls': report['metadata'].update(llm_calls_attempted=0,llm_calls_succeeded=0)\n"
                    "if bad and case=='bad-partial-calls': report['metadata']['llm_calls_succeeded']=2\n"
                    "if bad and case=='bad-no-meta': report['metadata']['meta_analysis_applied']=False\n"
                    "if not bad and case=='safe-degraded': report['metadata']['llm_degraded']=True\n"
                    "Path(args[args.index('--output')+1]).write_text(json.dumps(report))\n"
                    "sys.exit(1 if bad else 0)\n"
                )
                for path in binary.iterdir():
                    path.chmod(0o755)
                tools = root / "uv-tools"
                (tools / "skillspector/bin").mkdir(parents=True)
                (tools / "skillspector/bin/python").symlink_to(sys.executable)
                calls = root / "calls.jsonl"
                env = {"PATH": str(binary) + os.pathsep + os.environ["PATH"], "TMPDIR": str(root),
                       "plan_dir": str(root / "plan"), "config_root": str(root / "unpopulated-client-config"),
                       "tool_root": str(root / "tools"), "XDG_STATE_HOME": str(root / "state"),
                       "FIXTURE_UV_TOOLS": str(tools), "FIXTURE_CALLS": str(calls), "FIXTURE_REPORT_CASE": report_case}
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                        env=env, capture_output=True, text=True, timeout=15)
                observed = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
                if expected is not None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(observed, [{"model": expected, "bad": True}, {"model": expected, "bad": False}])
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    if report_case == "complete":
                        self.assertEqual(observed, [], "Invalid topology reached a provider scan")

    def test_conformance_release_cli_is_not_resolved_from_the_same_named_source_package(self):
        # npm@bfacd33 libnpmexec:49-60 can select an unbuilt same-name checkout.
        # Exercise the real row's working-directory transition with fixture CLIs.
        command = self.row("mcp-protocol-conformance")["acceptance"]["post_install"]["command"]
        probe = subprocess.run(["unshare", "--user", "--map-root-user", "--pid", "--fork", "--mount-proc",
                                "--kill-child", "true"], capture_output=True, timeout=10)
        if probe.returncode:
            self.skipTest("Unprivileged namespace unavailable; native acceptance remains fail-closed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tools/mcp-conformance-source-0.2.0-alpha.11"
            source.mkdir(parents=True)
            (source / "package.json").write_text(json.dumps({
                "name": "@modelcontextprotocol/conformance", "version": "0.2.0-alpha.11",
                "bin": {"conformance": "dist/index.js"},
            }))
            neutral = root / "plan"
            neutral.mkdir()
            (neutral / "config").mkdir()
            (neutral / "config/mcp-conformance-accept.sh").write_bytes((PLAN / "config/mcp-conformance-accept.sh").read_bytes())
            binaries = root / "bin"
            binaries.mkdir()
            for executable in ("npm", "npx"):
                script = binaries / executable
                script.write_text(
                    "#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\n"
                    "name=Path(sys.argv[0]).name; cwd=Path.cwd(); args=sys.argv[1:]\n"
                    "with open(os.environ['FIXTURE_CALLS'],'a') as f: f.write(json.dumps({'tool':name,'args':args,'cwd':str(cwd)})+'\\n')\n"
                    "if name=='npx' and (cwd/'package.json').is_file():\n"
                    " print('conformance: not found (same-named source package)',file=sys.stderr); sys.exit(127)\n"
                )
                script.chmod(0o755)
            calls = root / "calls.jsonl"
            env = {"PATH": str(binaries) + os.pathsep + os.environ["PATH"], "TMPDIR": str(root),
                   "tool_root": str(root / "tools"), "plan_dir": str(neutral), "FIXTURE_CALLS": str(calls),
                   "HOME": os.environ["HOME"], "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root)}
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual([c["args"] for c in observed if c["tool"] == "npm"],
                             [["ci", "--ignore-scripts"], ["run", "check"], ["test"]])
            release, = [c for c in observed if c["tool"] == "npx" and "list" in c["args"]]
            self.assertEqual(release["cwd"], str(neutral))
            self.assertEqual(release["args"], ["--offline", "--yes", "--ignore-scripts", "@modelcontextprotocol/conformance@0.2.0-alpha.11",
                                               "list", "--requirements", "2026-07-28"])

    def test_scout_scoped_dispatch_does_not_reinstall_the_inspect_owner(self):
        text = (PLAN / "install.sh").read_text()
        dispatch = text[text.index("if selected 'playwright-cli';"):]
        for slot in ("trajectory-analysis", "inspect-ai"):
            with self.subTest(slot=slot):
                prelude = '''
selected() { [[ "$only" == "$1" ]]; }
named() { selected "$1"; }
run_slot() { printf '%s\\n' "$1"; }
measured_slot() { if selected "$1"; then run_slot "$1"; fi; }
needs_docker=false
failed=0
'''
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", prelude + dispatch],
                                        env={"PATH": os.environ["PATH"], "only": slot},
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [slot])

    def test_scout_alias_migration_preserves_foreign_executables(self):
        command = next(c for c in self.row("trajectory-analysis")["commands"] if "scout_alias=" in c)
        cases = ("absent", "previous owner", "current owner", "foreign file", "foreign link", "dangling")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binary = root / "bin"
                binary.mkdir()
                tools = root / "uv-tools"
                for name in ("inspect-ai", "inspect-scout", "foreign"):
                    (tools / name / "bin").mkdir(parents=True)
                    (tools / name / "bin/scout").write_text("fixture")
                alias = binary / "scout"
                if case == "previous owner":
                    alias.symlink_to(tools / "inspect-ai/bin/scout")
                elif case == "current owner":
                    alias.symlink_to(tools / "inspect-scout/bin/scout")
                elif case == "foreign file":
                    alias.write_text("foreign bytes")
                elif case in ("foreign link", "dangling"):
                    alias.symlink_to(tools / "foreign/bin/scout" if case == "foreign link" else root / "missing/scout")
                before = alias.lstat() if alias.is_symlink() or alias.exists() else None
                target = os.readlink(alias) if alias.is_symlink() else None
                calls = root / "install-called"
                uv = binary / "uv"
                uv.write_text("#!/bin/sh\nif [ \"$*\" = 'tool dir --bin' ]; then printf '%s\\n' \"$FIXTURE_BIN\"; "
                              "elif [ \"$*\" = 'tool dir' ]; then printf '%s\\n' \"$FIXTURE_TOOLS\"; "
                              "else : > \"$FIXTURE_CALLED\"; fi\n")
                uv.chmod(0o755)
                env = {"PATH": str(binary) + os.pathsep + os.environ["PATH"], "TMPDIR": str(root),
                       "tool_root": str(root / "tools"), "FIXTURE_BIN": str(binary),
                       "FIXTURE_TOOLS": str(tools), "FIXTURE_CALLED": str(calls)}
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                        env=env, capture_output=True, text=True, timeout=10)
                allowed = case in ("absent", "previous owner", "current owner")
                self.assertEqual(result.returncode == 0, allowed, result.stderr)
                self.assertEqual(calls.exists(), allowed)
                if before is not None:
                    after = alias.lstat()
                    self.assertEqual((after.st_ino, after.st_mtime_ns, after.st_mode),
                                     (before.st_ino, before.st_mtime_ns, before.st_mode))
                    if target is not None:
                        self.assertEqual(os.readlink(alias), target)
                    else:
                        self.assertEqual(alias.read_text(), "foreign bytes")

    def test_research_post_install_binds_landed_model_metadata_without_relaxing_keyless_gates(self):
        import copy
        command = self.row("research-harnesses")["acceptance"]["post_install"]["command"]
        program = command.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
        active = {"models": [{"name": "gpt-runtime", "use": "langchain_openai:ChatOpenAI",
                              "model": "cx/gpt-6.1-sol-max", "base_url": "http://127.0.0.1:21128/v1",
                              "supports_reasoning_effort": False}],
                  "tools": [{"name": "web_search", "use": "deerflow.community.ddg_search.tools:web_search_tool"}]}
        cases = [("landed metadata", active, True)]
        for field, value in (("model", "cx/gpt-6.1-sol"), ("base_url", "http://127.0.0.1:1/v1"),
                             ("supports_reasoning_effort", True), ("reasoning_effort", "xhigh")):
            wrong = copy.deepcopy(active)
            wrong["models"][0][field] = value
            cases.append((field, wrong, False))
        wrong = copy.deepcopy(active)
        wrong["tools"][0]["use"] = "deerflow.community.tavily.tools:web_search_tool"
        cases.append(("provider custody", wrong, False))
        for name, config, expected in cases:
            with self.subTest(name=name):
                driver = '''import json,sys,types,os
data=json.loads(sys.argv[1])
client=types.ModuleType("deerflow.client")
class Client:
 def __init__(self,**kwargs): assert kwargs['config_path']==os.environ['DEER_FLOW_CONFIG_PATH']
 def list_models(self): return {'models':[{'name':'gpt-runtime'}]}
client.DeerFlowClient=Client
app=types.ModuleType("deerflow.config.app_config")
class Config:
 def model_dump(self): return data
app.get_app_config=lambda:Config()
sys.modules['deerflow.client']=client
sys.modules['deerflow.config.app_config']=app
exec(sys.stdin.read())
'''
                result = subprocess.run([sys.executable, "-c", driver, json.dumps(config)], input=program,
                                        env={"PATH": os.environ["PATH"], "DEER_FLOW_CONFIG_PATH": "fixture-public.yaml"},
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, expected, result.stderr)

    def capture_claude(self, slot):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "claude"
            binary.write_text(
                "#!/usr/bin/env python3\nimport fcntl,json,os,sys\n"
                "assert os.environ.get('CLAUDE_CODE_DISABLE_BACKGROUND_TASKS') == '1'\n"
                "with open(os.environ['NATIVE_STACK_CLAUDE_SESSION_LOCK'], 'a') as lock:\n"
                " try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                " except BlockingIOError: pass\n"
                " else: raise AssertionError('Fresh Claude command ran without the shared lock')\n"
                "print(json.dumps(sys.argv[1:]), file=sys.stderr)\nsys.exit(42)\n")
            binary.chmod(0o755)
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                   "plan_dir": str(PLAN), "repo_root": str(ROOT), "XDG_STATE_HOME": str(root / "state"),
                   "NATIVE_STACK_CLAUDE_SESSION_LOCK": str(root / "fixture-claude-session.lock")}
            result = subprocess.run(["bash", "-euo", "pipefail", "-c",
                                     self.row(slot)["acceptance"]["after_sign_in"]["command"]],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 42, result.stderr)
            # The program redirects the native stream into its private run directory.
            stderr = next((root / "state").rglob("claude.stderr")).read_text()
            return json.loads(stderr)

    def test_deer_flow_synthetic_stream_oracle_and_cold_native_argv(self):
        import copy
        # Synthetic records of bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e:
        # client.py:491-538,1191-1223; tui/cli.py:274-285; ddg_search/tools.py:190-191.
        # Local integration tests: no provider call or upstream acceptance.
        url = "https://example.org/fixture-source"
        final = f"Supported fixture answer [source]({url}).\n"
        baseline = [
            {"type": "messages-tuple", "data": {"type": "ai", "id": "planner",
             "content": "Planner draft https://example.org/planner-only\n"}},
            {"type": "messages-tuple", "data": {"type": "ai", "id": "search",
             "content": "", "tool_calls": [{"id": "search-1", "name": "web_search", "args": {"query": "fixture"}}]}},
            {"type": "messages-tuple", "data": {"type": "tool", "id": "result",
             "name": "web_search", "tool_call_id": "search-1", "content": json.dumps([
                 {"title": "Fixture source", "url": url, "snippet": "Substantive public source content for this fixture."}])}},
            {"type": "messages-tuple", "data": {"type": "ai", "id": "final", "content": "Supported fixture answer [source]("}},
            {"type": "messages-tuple", "data": {"type": "ai", "id": "final", "content": f"{url}).\n"}},
            {"type": "messages-tuple", "data": {"type": "ai", "id": "empty-tail", "content": ""}},
            {"type": "end", "data": {"usage": {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}}},
        ]
        cases = ("valid", "missing_end", "unmatched_id", "wrong_tool", "error_only",
                 "short_result", "foreign_citation", "zero_usage", "string_usage",
                 "bool_usage", "duplicate_end", "empty_complete", "empty_native_failure",
                 "empty_unmatched", "empty_wrong_query", "native_failure_with_results", "malformed_stream",
                 "malformed_data", "malformed_call", "malformed_result", "malformed_end")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                events = copy.deepcopy(baseline)
                native_rc = 75 if case in ("empty_native_failure", "native_failure_with_results") else 0
                if case == "missing_end":
                    events.pop()
                elif case == "unmatched_id":
                    events[2]["data"]["tool_call_id"] = "unrelated-call"
                elif case == "wrong_tool":
                    events[1]["data"]["tool_calls"][0]["name"] = "read_file"
                elif case == "error_only":
                    events[2]["data"]["content"] = json.dumps({"error": "Fixture search provider failed", "url": url})
                elif case == "short_result":
                    events[2]["data"]["content"] = json.dumps([
                        {"title": "Fixture source", "url": url, "snippet": "Too short"}])
                elif case == "foreign_citation":
                    events[0]["data"]["content"] = f"Intermediate planner cited {url}\n"
                    events[4]["data"]["content"] = "https://example.org/unreturned-source).\n"
                elif case in ("zero_usage", "string_usage", "bool_usage"):
                    events[-1]["data"]["usage"]["total_tokens"] = {"zero_usage": 0, "string_usage": "17", "bool_usage": True}[case]
                elif case == "duplicate_end":
                    events.append(copy.deepcopy(events[-1]))
                if case == "malformed_data":
                    events[2]["data"] = ["not a native message object"]
                elif case == "malformed_call":
                    events[1]["data"]["tool_calls"] = [{"name": "web_search", "args": {"query": "fixture"}}]
                elif case == "malformed_result":
                    events[2]["data"]["content"] = json.dumps([{"title": 42, "url": url, "snippet": None}])
                elif case == "malformed_end":
                    events[-1]["data"] = ["not a native end object"]
                if case.startswith("empty_"):
                    events[2]["data"]["content"] = json.dumps({"error": "No results found", "query": "fixture"})
                    if case == "empty_native_failure":
                        events.pop()
                    elif case == "empty_unmatched":
                        events[2]["data"]["tool_call_id"] = "unrelated-call"
                    elif case == "empty_wrong_query":
                        events[2]["data"]["content"] = json.dumps({"error": "No results found", "query": "another query"})
                tool_root = root / "data/new-wsl-native-stack/tools"
                native = tool_root / "deer-flow/backend/.venv/bin/deerflow"
                native.parent.mkdir(parents=True)
                config = root / "config with spaces.yaml"
                # Same ModuleType/exec(stdin) seam as the adjacent metadata fixture.
                # CPython 3.13 json docs: default JSON is a YAML 1.0/1.1/1.2 subset.
                # This synthetic codec tests the unchanged header mutation, not PyYAML.
                reader = native.with_name("python")
                reader.write_text(
                    f"#!{sys.executable}\n"
                    "import json, sys, types\n"
                    "assert sys.argv[1] == '-'\n"
                    "sys.argv = sys.argv[1:]\n"
                    "yaml = types.ModuleType('yaml')\n"
                    "yaml.safe_load = json.loads\n"
                    "yaml.safe_dump = json.dumps\n"
                    "sys.modules['yaml'] = yaml\n"
                    "exec(sys.stdin.read())\n")
                reader.chmod(0o755)
                config.write_text(json.dumps({"models": [{"name": "gpt-runtime",
                    "model": "cx/gpt-6.1-sol", "reasoning_effort": "xhigh",
                    "base_url": "http://127.0.0.1:21128/v1", "fixture_option": "preserved"}]}))
                temporary = root / "tmp"
                temporary.mkdir()
                native_record = root / "native.json"
                carrier = root / "unused-fixture-carrier.py"
                carrier.write_text("raise SystemExit('Keyless route must not invoke a credential carrier')\n")
                native.write_text(
                    "#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\n"
                    "keys = ['HOME', 'TMPDIR', 'DEER_FLOW_PROJECT_ROOT', 'DEER_FLOW_HOME', 'DEER_FLOW_CONFIG_PATH']\n"
                    "record = {'argv': sys.argv[1:], 'cwd': os.getcwd(), "
                    "'environment': {k: os.environ.get(k) for k in keys}, "
                    "'names': sorted(os.environ), "
                    "'jina_empty': os.environ.get('JINA_API_KEY') == '', "
                    "'tavily_empty': os.environ.get('TAVILY_API_KEY') == ''}\n"
                    f"Path({str(native_record)!r}).write_text(json.dumps(record))\n"
                    f"events = {events!r}\n"
                    "for event in events:\n    print(json.dumps(event))\n"
                    + ("print('malformed synthetic line')\n" if case == "malformed_stream" else "")
                    + f"raise SystemExit({native_rc})\n")
                native.chmod(0o755)
                query = "public fixture query 'with spaces'"
                env = {"PATH": os.environ["PATH"], "HOME": str(root / "inherited-home"), "LANG": "C.UTF-8",
                       "XDG_DATA_HOME": str(root / "data"), "XDG_STATE_HOME": str(root / "state"),
                       "XDG_CONFIG_HOME": str(root / "config"), "TMPDIR": str(temporary),
                       "DEER_FLOW_CONFIG_PATH": str(config), "NATIVE_STACK_CREDENTIAL_RUNNER": str(carrier),
                       "FIXTURE_PARENT_SENTINEL": "must-be-dropped", "JINA_API_KEY": "synthetic-unused",
                       "TAVILY_API_KEY": "synthetic-inherited-unused"}
                result = subprocess.run(["bash", str(PLAN / "config/deer-flow-research.sh"), query],
                                        env=env, capture_output=True, text=True, timeout=20)
                expected_rc = 0 if case == "valid" else native_rc or 1
                self.assertEqual(result.returncode, expected_rc, result.stderr)
                runs = list((root / "state/native-agent-stack/research/deer-flow").glob("run.*"))
                self.assertEqual(len(runs), 1)
                run = runs[0]
                seen = json.loads(native_record.read_text())
                self.assertEqual(seen["argv"], ["--recursion-limit", "100", "--json", query])
                self.assertEqual(Path(seen["cwd"]), run.resolve())
                self.assertEqual(seen["environment"], {
                    "HOME": str(run / "home"), "TMPDIR": str(temporary),
                    "DEER_FLOW_PROJECT_ROOT": str(tool_root / "deer-flow"),
                    "DEER_FLOW_HOME": str(run / "state"), "DEER_FLOW_CONFIG_PATH": str(run / "config.yaml")})
                observed = json.loads((run / "config.yaml").read_text())["models"][0]
                self.assertEqual(observed["default_headers"],
                                 {"x-omniroute-session-id": "deerflow-" + run.name})
                self.assertEqual(observed["model"], "cx/gpt-6.1-sol")
                self.assertEqual(observed["reasoning_effort"], "xhigh")
                self.assertEqual(observed["fixture_option"], "preserved")
                self.assertNotIn("default_headers", json.loads(config.read_text())["models"][0])
                self.assertTrue(seen["jina_empty"])
                self.assertTrue(seen["tavily_empty"])
                self.assertTrue({"FIXTURE_PARENT_SENTINEL", "NATIVE_STACK_CREDENTIAL_RUNNER",
                                 "XDG_STATE_HOME"}.isdisjoint(seen["names"]))
                raw = (run / "events.jsonl").read_text().splitlines()
                self.assertEqual([json.loads(line) for line in raw if line.startswith("{")], events)
                self.assertTrue((run / "answer.md").is_file())
                proof = json.loads((run / "integration-check.json").read_text())
                self.assertEqual(proof["native_exit_code"], native_rc)
                self.assertEqual(proof["integration_exit_code"], expected_rc)
                self.assertEqual(proof["acceptance_status"], "passed" if case == "valid" else "failed")
                expected_empty = 1 if case in ("empty_complete", "empty_native_failure") else 0
                self.assertEqual(proof["matched_provider_empty_results"], expected_empty)
                if expected_empty:
                    self.assertEqual(proof["provider_status"], "empty_results")
                    self.assertEqual(proof["matched_search_failures"], 0)
                self.assertEqual(proof["answer_status"], "final_cited" if case == "valid" else "unqualified_last_text")
                if case in ("missing_end", "empty_native_failure", "duplicate_end", "malformed_end"):
                    self.assertIsNone(proof["native_end_usage"])
                if native_rc:
                    self.assertEqual(proof["gatherer_status"], "native_failed")
                    self.assertIn("native_cli_failed", proof["failure_reasons"])
                if case == "empty_complete":
                    self.assertEqual(proof["gatherer_status"], "complete")
                    self.assertEqual(proof["native_end_usage"], baseline[-1]["data"]["usage"])
                if case.startswith("malformed_"):
                    self.assertEqual(proof["malformed_event_lines"], 1)
                    self.assertEqual(proof["gatherer_status"], "stream_invalid")
                if case == "valid":
                    self.assertEqual((run / "answer.md").read_text(), final)
                    self.assertIn(final, result.stdout)
                    self.assertNotIn("planner-only", result.stdout)
                    self.assertEqual(proof["matched_search_successes"], 1)
                    self.assertEqual(proof["matched_search_failures"], 0)
                    self.assertEqual(proof["final_answer_citations_in_results"], 1)
                    self.assertEqual(proof["native_end_usage"], baseline[-1]["data"]["usage"])
                else:
                    self.assertIn("Native DeerFlow acceptance failed", result.stderr)

    def test_original_fresh_recipes_reject_incomplete_foreground_shell_results(self):
        import ast
        import copy
        rows = {slot: self.row(slot)["acceptance"]["after_sign_in"]["command"]
                for slot in ("worktrunk", "difftastic", "mcp-inspector", "cross-family-review")}
        helper = (PLAN / "config/srt-client-accept.sh").read_text()
        rows["sandbox-runtime-srt"] = helper
        for slot, command in rows.items():
            start = command.index("def completed_foreground_shell_calls(events):")
            rest = command[start:]
            end = next((m.start() for m in re.finditer(r"(?m)^(?!def completed_foreground_shell_calls)(?:def |events =|c, g =)", rest)), len(rest))
            function = ast.parse(rest[:end]).body[0]
            namespace = {}
            exec(compile(ast.Module(body=[function], type_ignores=[]), "<synthetic foreground oracle>", "exec"), namespace)
            baseline = [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "call", "name": "Bash",
                     "input": {"command": "public fixture command", "run_in_background": False}}]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "call", "content": "Completed fixture output\n"}]}},
            ]
            for case in ("valid", "requested_background", "automatic_background", "timeout",
                         "tool_error", "unlinked", "missing", "empty", "soft_exit",
                         "automatic_timeout", "manual_background", "message_background"):
                with self.subTest(slot=slot, case=case):
                    events = copy.deepcopy(baseline)
                    if case == "requested_background":
                        events[0]["message"]["content"][0]["input"]["run_in_background"] = True
                    elif case == "automatic_background":
                        events[1]["message"]["content"][0]["content"] += "Command running in background with ID: fixture\n"
                    elif case in ("automatic_timeout", "manual_background", "message_background"):
                        header = {"automatic_timeout": "Command did not complete within its 10s timeout and was moved to the background (ID: fixture).",
                                  "manual_background": "Command was manually backgrounded by user with ID: fixture",
                                  "message_background": "Command was moved to the background (ID: fixture)."}[case]
                        events[1]["message"]["content"][0]["content"] += header + "\n"
                    elif case == "timeout":
                        events[1]["message"]["content"][0]["content"] += "_(timed out after 1000 ms)_\n"
                    elif case == "tool_error":
                        events[1]["message"]["content"][0]["is_error"] = True
                    elif case == "unlinked":
                        events[1]["message"]["content"][0]["tool_use_id"] = "another-call"
                    elif case == "missing":
                        events.pop()
                    elif case == "empty":
                        events[1]["message"]["content"][0]["content"] = ""
                    elif case == "soft_exit":
                        events[1]["message"]["content"][0]["content"] = "Prepared only\nExit code: 1\n"
                    # Metadata is not a tool event; exercise every failure gate with it present.
                    events[:0] = [{"type": "system", "subtype": "permission_denied", "message": value}
                                  for value in ("Native notice", None, [], 1, True)]
                    self.assertEqual(namespace["completed_foreground_shell_calls"](events),
                                     {"call"} if case in ("valid", "empty") else set())
            # A quoted marker in source text is not a native partial-output header.
            baseline[1]["message"]["content"][0]["content"] = '+    markers = ("Exit code:",)\n'
            self.assertEqual(namespace["completed_foreground_shell_calls"](baseline), {"call"})

    def test_research_completion_includes_final_recipe_assertions(self):
        import ast
        import shlex
        program = self.row("research-harnesses")["acceptance"]["after_sign_in"]["command"]
        block = next(b for b in re.findall(r"<<'PY'\n(.*?)\nPY", program, re.S)
                     if "def native_commands" in b)
        nodes = []
        for node in ast.parse(block).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple):
                break  # Artifact checks have their own independently constructed fixtures.
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                nodes.append(node)
        expected = [
            f"bash '{ROOT / 'tools/research/gpt_researcher.sh'}' 'synthetic query'",
            f"bash '{PLAN / 'config/deer-flow-research.sh'}' 'synthetic query'",
        ]
        markers = ["native-stage-complete:fixture:gptr", "native-stage-complete:fixture:deerflow"]
        for client in ("claude", "codex"):
            for case in ("valid", "native_polling", "in_progress_only", "mcp_timeout", "missing_gpt", "wrong_helper", "missing_marker"):
                with self.subTest(client=client, case=case), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "stream.jsonl"
                    events = []
                    for i, command in enumerate(expected):
                        if case == "missing_gpt" and i == 0:
                            continue
                        if case == "wrong_helper" and i == 0:
                            command = command.replace("gpt_researcher.sh", "gpt-researcher.sh")
                        output = "" if case == "missing_marker" and i == 0 else markers[i] + "\n"
                        if client == "claude":
                            events.extend([
                                {"type": "assistant", "message": {"content": [{
                                    "type": "tool_use", "id": f"call-{i}", "name": "Bash",
                                    "input": {"command": command}}]}},
                                {"type": "user", "message": {"content": [{
                                    "type": "tool_result", "tool_use_id": f"call-{i}",
                                    "content": output, "is_error": False}]}},
                            ])
                        else:
                            item = {"id": f"call-{i}", "type": "command_execution", "command": command,
                                    "status": "completed", "exit_code": 0, "aggregated_output": output}
                            if case in ("native_polling", "in_progress_only"):
                                pending = {**item, "status": "in_progress", "exit_code": None,
                                           "aggregated_output": ""}
                                events.extend([{"type": "item.started", "item": pending},
                                               {"type": "item.updated", "item": pending}])
                                if case == "in_progress_only" and i == 0:
                                    continue  # Later disk output cannot finish this native item.
                            if case == "mcp_timeout" and i == 0:
                                args = {"language": "shell", "code": command, "timeout": 600000}
                                events.extend([
                                    {"type": "item.started", "item": {"id": f"call-{i}", "type": "mcp_tool_call",
                                     "server": "context-mode", "tool": "ctx_execute", "arguments": args}},
                                    {"type": "item.completed", "item": {"id": f"call-{i}", "type": "mcp_tool_call",
                                     "server": "context-mode", "tool": "ctx_execute", "arguments": args,
                                     "status": "failed", "error": {"message": "timed out awaiting tools/call after 300s"}}}
                                ])
                            else:
                                events.append({"type": "item.completed", "item": item})
                    events.append({"type": "result", "subtype": "success", "is_error": False}
                                  if client == "claude" else {"type": "turn.completed"})
                    path.write_text("\n".join(json.dumps(e) for e in events))
                    namespace = {"json": json, "shlex": shlex, "Path": Path, "re": re,
                                 "sys": types.SimpleNamespace(argv=[
                                     "fixture", directory, "unused-marker", str(path), client,
                                     *expected, *markers])}
                    code = compile(ast.Module(body=nodes, type_ignores=[]), "synthetic-complete-research-gate", "exec")
                    valid = case in ("valid", "native_polling") or (client == "claude" and
                                case in ("in_progress_only", "mcp_timeout"))
                    if valid:
                        exec(code, namespace)
                    else:
                        with self.assertRaisesRegex(AssertionError, "No completed native GPT Researcher call"):
                            exec(code, namespace)


    def test_research_native_transport_data_preserves_claude_prompt_and_commands(self):
        import shlex
        program = self.row("research-harnesses")["acceptance"]["after_sign_in"]["command"]
        block = "  gpt_marker=" + program.split("  gpt_marker=", 1)[1].split(
            '  if [[ "$client" == claude ]]; then', 1)[0]
        legacy = ("Use native-stack-research to complete BOTH real gatherers using foreground shell calls "
                  "with 1560000 ms timeouts, waiting for each to finish. Execute each supplied command once. "
                  "If a call fails, inspect its retained receipt/stdout/stderr, report the actual failure and stop; "
                  "do not retry or switch providers. Run these exact commands with their supplied keyless public "
                  "config and isolated state. Inspect the retained call stdout/stderr in the supplied per-client "
                  "state and both resulting reports; print their run directories. Preflight/import checks are insufficient.")
        for client in ("claude", "codex"):
            env = {k: os.environ[k] for k in ("PATH", "TMPDIR") if k in os.environ}
            env.update(client=client, session="/synthetic/session", client_state="/synthetic/state",
                       repo_root=str(ROOT), plan_dir=str(PLAN))
            capture = block + "\n" + shlex.join([
                sys.executable, "-c", "import json,sys;print(json.dumps(sys.argv[1:]))"
            ]) + ' "$prompt" "$gpt_command" "$deer_command"'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", capture],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            prompt, gpt_command, deer_command = json.loads(result.stdout)
            prefix, commands = prompt.split("\n", 1)
            self.assertEqual(commands, gpt_command + "\n" + deer_command)
            self.assertIn("Execute each supplied command once.", prefix)
            self.assertIn("do not retry or switch providers", prefix)
            self.assertIn("keyless public config and isolated state", prefix)
            if client == "claude":
                self.assertEqual(prefix, legacy)
            else:
                self.assertIn("native exec_command with yield_time_ms=30000", prefix)
                self.assertIn("write_stdin (empty chars, yield_time_ms=30000)", prefix)
                self.assertIn("until its final exit", prefix)
                self.assertIn("Do not run these long commands through an MCP tool", prefix)
                self.assertNotIn("600000 ms", prefix)


    def test_research_claude_queue_is_outside_execution_budget_and_background_is_disabled(self):
        import shlex
        program = self.row("research-harnesses")["acceptance"]["after_sign_in"]["command"]
        line = next(x.strip() for x in program.splitlines() if "claude -p" in x)
        launch = line.split("&& ", 1)[1].split(") >", 1)[0]
        self.assertNotIn("timeout 3300 flock", launch)
        with tempfile.TemporaryDirectory(prefix="ns-research-argv-") as temp:
            root = Path(temp)
            binaries = root / "bin"
            binaries.mkdir()
            fixture = ("#!"+sys.executable+"\n"
                       "import json,os,sys\nfrom pathlib import Path\n"
                       "name=Path(sys.argv[0]).name; args=sys.argv[1:]\n"
                       "chain=json.loads(os.environ.get('FIXTURE_CHAIN','[]')); chain.append([name,*args])\n"
                       "if name == 'claude':\n"
                       " print(json.dumps({'chain':chain,'argv':args,'background':os.environ.get('CLAUDE_CODE_DISABLE_BACKGROUND_TASKS')}))\n"
                       "else:\n"
                       " os.environ['FIXTURE_CHAIN']=json.dumps(chain)\n"
                       " command=args[3:] if name == 'flock' else args[1:]\n"
                       " os.execvpe(command[0],command,os.environ)\n")
            for name in ("flock", "timeout", "claude"):
                path = binaries / name
                path.write_text(fixture)
                path.chmod(0o755)
            lock = root / "private.lock"
            env = {"PATH":str(binaries)+os.pathsep+os.environ["PATH"],
                   "HOME":str(root), "NATIVE_STACK_CLAUDE_SESSION_LOCK":str(lock),
                   "plan_dir":str(PLAN), "prompt":"frozen supplied commands"}
            result = subprocess.run(["bash","-euo","pipefail","-c",launch],
                                    env=env,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            observed = json.loads(result.stdout)
            queue, execution, client = observed["chain"]
            self.assertEqual(queue[:4],["flock","-w","3600",str(lock)])
            self.assertEqual(queue[4:6],["timeout","3300"])
            self.assertEqual(execution[:4],["timeout","3300","env","CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1"])
            self.assertEqual(client[0],"claude")
            self.assertEqual(observed["background"],"1")
            self.assertEqual(observed["argv"][0],"-p")
            self.assertEqual(observed["argv"][observed["argv"].index("--max-turns")+1],"48")

    def test_research_skill_uses_working_native_default_and_long_foreground_wait(self):
        skill = (PLAN / "config/research-harnesses-skill.md").read_text()
        self.assertNotIn("/absolute/path/",skill)
        self.assertNotIn("DEER_FLOW_CONFIG_PATH=",skill)
        self.assertNotIn("configuration supplied by the coordinator",skill)
        self.assertNotIn("Tavily",skill)
        self.assertIn("1500 seconds per call",skill)
        self.assertIn("1560000 ms",skill)
        self.assertIn("wait for its final exit",skill)
        self.assertIn("two independent research outputs",skill)

    def test_foreground_native_completion_rejects_background_and_partial_results(self):
        import ast
        import copy
        import shlex
        # Synthetic native records exercise the repository integration boundary.
        # Codex rust-v0.160.0:exec_events.rs:161,286; context-mode@6f0cc684:
        # src/server.ts:1844; src/exit-classify.ts:22. These are not upstream acceptance.
        expected = "bash '/public/source.sh' 'query with spaces'"
        for slot in ("agent-runtime-worker", "research-harnesses"):
            program = self.row(slot)["acceptance"]["after_sign_in"]["command"]
            block = next(b for b in re.findall(r"<<'PY'\n(.*?)\nPY", program, re.S)
                         if "def native_commands" in b)
            function = next(n for n in ast.parse(block).body if isinstance(n, ast.FunctionDef)
                            and n.name == "native_commands")
            namespace = {"json": json, "shlex": shlex, "Path": Path, "re": re}
            exec(compile(ast.Module(body=[function], type_ignores=[]), "synthetic-native-oracle", "exec"), namespace)
            oracle = namespace["native_commands"]
            for client in ("claude", "codex"):
                for route in ("shell", "mcp"):
                    for case in ("valid", "background", "partial", "wrong_command", "tool_error", "native_failure", "soft_failure", "marker_echo_only", "automatic_timeout", "manual_background", "message_background"):
                        with self.subTest(slot=slot, client=client, route=route, case=case), tempfile.TemporaryDirectory() as directory:
                            args = {"language": "shell", "code": expected} if route == "mcp" else {"command": expected}
                            if client == "claude":
                                tool = {"type": "tool_use", "id": "call-1", "name": "mcp__context_mode__ctx_execute" if route == "mcp" else "Bash", "input": args}
                                result = {"type": "tool_result", "tool_use_id": "call-1", "content": "Fixture operation completed", "is_error": False}
                                events = [{"message": {"content": [tool]}}, {"message": {"content": [result]}},
                                          {"type": "result", "subtype": "success", "is_error": False}]
                                events[:0] = [{"type": "system", "subtype": "permission_denied",
                                              "message": value}
                                             for value in ("Native notice", None, [], 1, True)]
                                if case == "background":
                                    args["background" if route == "mcp" else "run_in_background"] = True
                                elif case == "partial":
                                    result["content"] = "_(process backgrounded after 30 seconds)_" if route == "mcp" else "Command running in background with ID: fixture"
                                elif case == "tool_error":
                                    result["is_error"] = True
                                elif case == "native_failure":
                                    events[-1]["is_error"] = True
                            else:
                                if route == "mcp":
                                    initial = {"id": "call-1", "type": "mcp_tool_call", "server": "context-mode", "tool": "ctx_execute", "arguments": args}
                                    result = {"isError": False, "content": [{"type": "text", "text": "Fixture operation completed"}]}
                                    item = {**initial, "status": "completed", "result": result}
                                    events = [{"type": "item.started", "item": copy.deepcopy(initial)}, {"type": "item.completed", "item": item}, {"type": "turn.completed"}]
                                    if case == "background":
                                        args["background"] = True
                                        events[0]["item"]["arguments"]["background"] = True
                                    elif case == "partial":
                                        result["content"][0]["text"] = "_(timed out after 30 seconds)_"
                                    elif case == "tool_error":
                                        result["isError"] = True
                                else:
                                    item = {"type": "command_execution", "command": expected, "status": "completed", "exit_code": 0, "aggregated_output": "Fixture operation completed"}
                                    args = item
                                    events = [{"type": "item.completed", "item": item}, {"type": "turn.completed"}]
                                    if case in ("background", "partial"):
                                        item["status"] = "in_progress"
                                    elif case == "tool_error":
                                        item["exit_code"] = 1
                                if case == "native_failure":
                                    events[-1]["type"] = "turn.failed"
                            if case == "wrong_command":
                                args["code" if route == "mcp" else "command"] = expected.replace("source.sh", "unrelated.sh")
                            if case in ("automatic_timeout", "manual_background", "message_background"):
                                header = {"automatic_timeout": "Command did not complete within its 10s timeout and was moved to the background (ID: fixture).",
                                          "manual_background": "Command was manually backgrounded by user with ID: fixture",
                                          "message_background": "Command was moved to the background (ID: fixture)."}[case]
                                text = "Fixture operation completed\n" + header
                                if client == "claude":
                                    result["content"] = text
                                elif route == "mcp":
                                    result["content"][0]["text"] = text
                                else:
                                    item["aggregated_output"] = text
                            if case in ("soft_failure", "marker_echo_only"):
                                text = "Prepared only" if case == "soft_failure" else "```shell\nprintf '%s\\n' 'Fixture operation completed'\n```\nPrepared only"
                                if client == "claude":
                                    result["content"] = text
                                elif route == "mcp":
                                    result["content"][0]["text"] = text
                                else:
                                    item["aggregated_output"] = text
                            path = Path(directory) / "native.jsonl"
                            path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
                            if case == "native_failure":
                                with self.assertRaises(AssertionError):
                                    oracle(path, client, [expected], ["Fixture operation completed"])
                            else:
                                self.assertEqual(oracle(path, client, [expected], ["Fixture operation completed"]), [expected] if case == "valid" else [])

    def test_worker_recipe_keeps_bus_bindings_in_an_empty_environment(self):
        # A local systemd stand-in tests native argument and public bus-binding custody.
        # systemd@v259.5:src/shared/bus-util.c:273-300,510-540; no output wrapper is required.
        line = next(l for l in self.row("agent-runtime-worker")["acceptance"]["after_sign_in"]["command"].splitlines()
                    if l.startswith("  printf -v worker_command "))
        with tempfile.TemporaryDirectory(prefix="worker recipe ") as directory:
            root = Path(directory)
            cfg, state, run, binaries = [root / p for p in ("config space", "state space", "run space", "bin")]
            for path in (cfg, state, run / "tmp", binaries):
                path.mkdir(parents=True)
            worker = cfg / "worker.py"
            worker.write_text(
                "import json, sys\nfrom pathlib import Path\n"
                "assert sys.argv[1:] == ['--prepare', 'fixture-job']\n"
                f"p=Path({str(state / 'fixture-job')!r}); (p/'workspace').mkdir(parents=True)\n"
                "(p/'run-report.json').write_text(json.dumps({'success':True,'requests_to_model':2}))\n"
                "(p/'workspace/result.txt').write_text('55\\n')\n")
            bus = binaries / "systemctl"
            bus.write_text(
                f"#!{sys.executable}\nimport os, sys\n"
                "assert sys.argv[1:] == ['--user','start','--wait','openhands-job@fixture-job.service']\n"
                f"assert os.environ['XDG_RUNTIME_DIR'] == {str(root / 'runtime space')!r}\n"
                f"assert os.environ['DBUS_SESSION_BUS_ADDRESS'] == {'unix:path='+str(root / 'runtime space/bus')!r}\n"
                f"assert os.environ['TMPDIR'] == {str(run / 'tmp')!r}\n")
            bus.chmod(0o755)
            environment = {"PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                           "cfg": str(cfg), "worker_state": str(state), "run": str(run), "id": "fixture-job",
                           "XDG_RUNTIME_DIR": str(root / "runtime space"),
                           "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(root / "runtime space/bus")}
            command = subprocess.run(["bash", "-euo", "pipefail", "-c", line + '\nprintf "%s" "$worker_command"'],
                                     env=environment, capture_output=True, text=True, check=True).stdout
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                    env={"PATH": environment["PATH"]}, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Completed worker job: 55; positive model responses: 2", result.stdout)

    def test_variadic_tool_values_do_not_consume_the_prompt(self):
        for slot in ("difftastic", "worktrunk"):
            with self.subTest(slot=slot):
                argv = self.capture_claude(slot)
                prompt = next(a for a in argv if "Use your shell tool" in a)
                self.assertLess(argv.index(prompt), argv.index("--allowedTools"))

    def test_alert_closed_port_requires_failed_connect_and_no_listener(self):
        from unittest.mock import patch
        command = self.row("alerting")["acceptance"]["after_sign_in"]["command"]
        start = command.index("import socket\nimport subprocess\n")
        check = command[start:command.index("\nPY", start)]
        # Execute the actual plan predicate. Errno alone cannot prove no listener.
        for errno, listener, ss_failed in ((111, "", False), (11, "", False),
                                           (0, "", False), (111, "LISTEN fixture\n", False),
                                           (11, "", True)):
            with self.subTest(errno=errno, listener=bool(listener), ss_failed=ss_failed):
                with patch("socket.socket") as sock, patch("subprocess.run") as ss:
                    sock.return_value.__enter__.return_value.connect_ex.return_value = errno
                    ss.return_value.stdout = listener
                    if ss_failed:
                        ss.side_effect = subprocess.CalledProcessError(1, "ss")
                    if errno != 0 and not listener and not ss_failed:
                        exec(compile(check, "<actual-alert-closed-port-predicate>", "exec"), {})
                        ss.assert_called_once_with(["ss", "-ltnH", "sport = :21997"],
                                                   check=True, capture_output=True, text=True)
                    else:
                        with self.assertRaises((AssertionError, subprocess.CalledProcessError)):
                            exec(compile(check, "<actual-alert-closed-port-predicate>", "exec"), {})

    def test_fresh_sessions_use_bounded_native_cli_and_keep_context(self):
        for slot in ("difftastic", "worktrunk"):
            with self.subTest(slot=slot):
                argv = self.capture_claude(slot)
                self.assertEqual(argv[0], "-p")
                self.assertIn("Use your shell tool", argv[1])
                self.assertEqual(argv[argv.index("--max-turns") + 1], "48")
                instruction_file = Path(argv[argv.index("--append-system-prompt-file") + 1])
                self.assertEqual(instruction_file, PLAN / "config/acceptance-execution-instructions.txt")
                self.assertIn("supplied execution or review", instruction_file.read_text())
                self.assertIn("Do not request background execution", instruction_file.read_text())
                self.assertNotIn("--bare", argv)
                self.assertNotIn("--disable-slash-commands", argv)

    def test_every_fresh_claude_command_uses_the_shared_lock(self):
        plan = json.loads((PLAN / "install-plan.json").read_text())
        callers = {r["slot"]: a.get("command") or "" for r in plan["owners"]
                   for a in r["acceptance"].values() if isinstance(a, dict)
                   and "claude -p" in (a.get("command") or "")}
        callers["sandbox-runtime-srt"] = (PLAN / "config/srt-client-accept.sh").read_text()
        self.assertEqual(len(callers), 13)
        for slot, command in callers.items():
            with self.subTest(slot=slot):
                if slot == "cross-family-review":
                    line = next(line for line in command.splitlines()
                                if 'flock -w 3600' in line and '"${claude_review_argv[@]}"' in line)
                    self.assertIn("claude_review_argv=(claude -p ", command)
                else:
                    line = next(line for line in command.splitlines() if "claude -p" in line)
                    self.assertIn("flock -w 3600", line[:line.index("claude -p")])
                self.assertIn("native-agent-stack/coordination/ns2604-coop/claude-session.lock", line)


    def test_cross_review_binds_actual_argv_to_native_session_metadata(self):
        import copy
        import uuid
        command = self.row("cross-family-review")["acceptance"]["after_sign_in"]["command"]
        proof = command.split("<<'BINDING'\n", 1)[1].split("\nBINDING\n", 1)[0]
        self.assertEqual(command.count("timeout --kill-after=15s 1200s"), 2)
        self.assertIn('"${gpt_review_argv[@]}" < /dev/null', command)
        self.assertIn('"${claude_review_argv[@]}" < "$run_dir/gpt-authored.diff"', command)
        self.assertNotIn("Deliver the review in this session as the requested structured object:", command)
        thread = str(uuid.UUID(int=1))
        gpt = ["codex", "exec", "-m", "gpt-6.1-sol", "-c", 'review_model="gpt-6.1-sol"', "-c", 'model_reasoning_effort="max"',
               "review", "Review read-only immutable Claude-authored commit synthetic-fixture"]
        claude = ["claude", "-p", "Frozen fixture review", "--model", "opus", "--effort", "max", "--max-turns", "48", "--tools", "Read,Glob,Grep",
                  "--disallowedTools", "Workflow,Agent,mcp__*", "--permission-mode", "dontAsk"]
        cases = ("valid", "gpt_model", "gpt_effort", "claude_model", "claude_effort", "claude_turns",
                 "claude_plan", "missing_tools", "expanded_tools", "missing_mcp_denial", "duplicate_tools",
                 "changed_target", "commit_target", "ephemeral", "duplicate_model",
                 "missing_thread", "invalid_thread", "missing_rollout", "metadata_model",
                 "metadata_effort", "missing_context", "missing_claude_init", "missing_child", "wrong_parent", "wrong_source", "ambiguous_child")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                ga, ca = copy.deepcopy(gpt), copy.deepcopy(claude)
                context = {"type": "turn_context", "payload": {"model": "gpt-6.1-sol", "effort": "max"}}
                if case == "gpt_model":
                    ga[ga.index("-m") + 1] = "different-model"
                elif case == "gpt_effort":
                    ga[ga.index('model_reasoning_effort="max"')] = 'model_reasoning_effort="high"'
                elif case == "claude_model":
                    ca[ca.index("--model") + 1] = "sonnet"
                elif case == "claude_effort":
                    ca[ca.index("--effort") + 1] = "high"
                elif case == "claude_turns":
                    ca[ca.index("--max-turns") + 1] = "4"
                elif case == "claude_plan":
                    ca[ca.index("--permission-mode") + 1] = "plan"
                elif case == "missing_tools":
                    index = ca.index("--tools")
                    del ca[index:index + 2]
                elif case == "expanded_tools":
                    ca[ca.index("--tools") + 1] = "Read,Glob,Grep,Bash,EnterPlanMode"
                elif case == "missing_mcp_denial":
                    ca[ca.index("--disallowedTools") + 1] = "Workflow,Agent"
                elif case == "duplicate_tools":
                    ca.extend(["--tools", "Bash"])
                elif case == "changed_target":
                    ga[-1] = "Unbound mutable repository review"
                elif case in ("commit_target", "ephemeral", "duplicate_model"):
                    inserted = {"commit_target": ["--commit", "synthetic-sha"], "ephemeral": ["--ephemeral"],
                                "duplicate_model": ["-m", "different-model"]}[case]
                    ga[2:2] = inserted
                elif case == "metadata_model":
                    context["payload"]["model"] = "different-model"
                elif case == "metadata_effort":
                    context["payload"]["effort"] = "high"
                (root / "gpt-review.argv.json").write_text(json.dumps(ga))
                (root / "claude-review.argv.json").write_text(json.dumps(ca))
                events = [] if case == "missing_thread" else [
                    {"type": "thread.started", "thread_id": "invalid" if case == "invalid_thread" else thread}]
                (root / "gpt-review.jsonl").write_text("\n".join(json.dumps(event) for event in events))
                initial = [] if case == "missing_claude_init" else [
                    {"type": "system", "subtype": "init", "model": "claude-opus-5-5"}]
                (root / "claude-review.jsonl").write_text("\n".join(json.dumps(event) for event in initial))
                native = root / "codex" / "sessions" / "2026" / "10" / "05"
                native.mkdir(parents=True)
                rollout = native / ("rollout-synthetic-" + thread + ".jsonl")
                parent = {"type": "session_meta", "payload": {"id": thread, "cli_version": "0.160.0", "model_provider": "fixture"}}
                metadata = [{"type": "session_meta", "payload": {"cli_version": "0.160.0", "model_provider": "fixture",
                             "parent_thread_id": thread, "source": {"subagent": "review"}}}]
                if case == "wrong_parent":
                    metadata[0]["payload"]["parent_thread_id"] = str(uuid.UUID(int=3))
                elif case == "wrong_source":
                    metadata[0]["payload"]["source"] = {"subagent": "compact"}
                if case != "missing_context":
                    metadata.append(context)
                if case != "missing_rollout":
                    rollout.write_text(json.dumps(parent))
                    if case != "missing_child":
                        child = native / ("rollout-synthetic-" + str(uuid.UUID(int=2)) + ".jsonl")
                        child.write_text("\n".join(json.dumps(event) for event in metadata))
                    if case == "ambiguous_child":
                        extra = native / ("rollout-synthetic-" + str(uuid.UUID(int=4)) + ".jsonl")
                        extra.write_text("\n".join(json.dumps(event) for event in metadata))
                checked = subprocess.run([sys.executable, "-c", proof, str(root)],
                                         env={**{key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ},
                                              "CODEX_HOME": str(root / "codex")},
                                         capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode == 0, case == "valid", checked.stderr)
                if case == "valid":
                    bound = json.loads((root / "review-binding.json").read_text())
                    self.assertEqual(bound["gpt"]["target_type"], "custom")
                    self.assertEqual(bound["gpt"]["native_turn_contexts"], [context["payload"]])
                    self.assertIsNone(bound["claude"]["effort_from_native_init"])
                    self.assertIn("independent owner observation", bound["gateway_wire_model_effort"])
                    self.assertEqual(bound["observation_deadline_seconds"]["sequential_total"], 2400)

    def test_retired_rows_cannot_reintroduce_commands_or_prerequisites(self):
        # Use the same unchanged-copy checker; assert its independent retirement
        # gate, even when the source-only plan awaits #810's settlement metadata.
        fixture = InterimPlanChecks()
        for slot, key, value in (
            ("local-model-server", "commands", ["ollama serve"]),
            ("local-generation-model", "acceptance", {"post_install": {"kind": "smoke", "command": "ollama run retired"}}),
            ("local-model-server", "installed", True),
        ):
            def change(rows, slot=slot, key=key, value=value):
                rows[slot][key] = value
            with self.subTest(slot=slot, field=key):
                code, output = fixture.run_check(change_rows=change)
                self.assertNotEqual(code, 0)
                self.assertIn(f"[{slot}] retired slot must have no installation", output)

    def test_historical_ollama_unit_is_rejected_as_an_install_consumer(self):
        fixture = InterimPlanChecks()
        def change(text):
            return text.replace("embedding-model() {", "embedding-model() {\n  copy_config 'ollama.service'", 1)
        code, output = fixture.run_check(change_install=change)
        self.assertNotEqual(code, 0)
        self.assertIn("retired Ollama assets must never be installed", output)

    def test_current_qmd_lexical_stage_requires_existing_index_and_known_document(self):
        row = self.row("tobi-qmd")
        command = row["acceptance"]["after_sign_in"]["command"]
        cases = [
            ("known", [{"file": "qmd://foundation-docs/harness-defaults.md", "score": 0.5}], True, 0),
            ("empty", [], True, 1),
            ("different document", [{"file": "qmd://foundation-docs/other.md", "score": 0.5}], True, 1),
            ("wrong collection", [{"file": "qmd://other/harness-defaults.md", "score": 0.5}], True, 1),
            ("boolean score", [{"file": "qmd://foundation-docs/harness-defaults.md", "score": True}], True, 1),
            ("missing index", [], False, 1),
        ]
        for name, results, existing, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                cache, config, stub = root / "cache", root / "config", root / "bin"
                stub.mkdir()
                if existing:
                    (cache / "qmd").mkdir(parents=True)
                    (config / "qmd").mkdir(parents=True)
                    (cache / "qmd/native-agent-stack-catalog-lex.sqlite").write_bytes(b"regenerable fixture")
                    (config / "qmd/native-agent-stack-catalog-lex.yml").write_text("collections: {}\n")
                (root / "reply.json").write_text(json.dumps(results))
                qmd = stub / "qmd"
                qmd.write_text("#!/usr/bin/env python3\n" + r'''
import json, os, sys
from pathlib import Path
root = Path(os.environ["QMD_FIXTURE"])
args = sys.argv[1:]
assert args[:2] == ["--index", "native-agent-stack-catalog-lex"]
assert os.environ.get("QMD_FORCE_CPU") == "1" and "INDEX_PATH" not in os.environ
assert args[2] in ("status", "search"), "no embed/update/pull is permitted"
with (root / "calls.jsonl").open("a") as out:
    out.write(json.dumps(args) + "\n")
if args[2] == "search":
    assert args[args.index("-c") + 1] == "foundation-docs" and "--json" in args
    print((root / "reply.json").read_text())
else:
    print("fixture lexical status")
''')
                qmd.chmod(0o755)
                env = {key: value for key, value in os.environ.items()
                       if key not in ("BASH_ENV", "ENV", "QMD_CONFIG_DIR")}
                env.update(QMD_FIXTURE=str(root), XDG_CACHE_HOME=str(cache), XDG_CONFIG_HOME=str(config),
                           PYTHONOPTIMIZE="1",
                           XDG_STATE_HOME=str(root / "state"), HOME=str(root / "home"),
                           INDEX_PATH="MUST_BE_REMOVED", PATH=f"{stub}{os.pathsep}{os.environ.get('PATH', '')}")
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", command], env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, expected, result.stderr)
                if existing:
                    calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
                    self.assertEqual([args[2] for args in calls], ["status", "search"])
                else:
                    self.assertFalse((root / "calls.jsonl").exists())
                    self.assertFalse((cache / "qmd").exists())
                    self.assertIn("needs_owner:", result.stderr)

    def test_prometheus_health_requires_exact_plan_startup_features(self):
        row = self.row("prometheus")
        self.assertEqual(row["service"]["enable_features"],
                         ["created-timestamp-zero-ingestion", "promql-extended-range-selectors"])
        command = row["acceptance"]["service_health"]["command"]
        proof = command.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
        cases = {
            "valid": {"status": "success", "data": {"enable-feature": ",".join(row["service"]["enable_features"])}},
            "superset": {"status": "success", "data": {"enable-feature": "created-timestamp-zero-ingestion,promql-extended-range-selectors,extra-fixture-feature"}},
            "missing_both": {"status": "success", "data": {"enable-feature": ""}},
            "missing_zero": {"status": "success", "data": {"enable-feature": "promql-extended-range-selectors"}},
            "missing_range": {"status": "success", "data": {"enable-feature": "created-timestamp-zero-ingestion"}},
            "near_names": {"status": "success", "data": {"enable-feature": "created-timestamp-zero-ingestion-extra,promql-extended-range-selectors-extra"}},
            "bad_type": {"status": "success", "data": {"enable-feature": True}},
            "bad_data": {"status": "success", "data": None},
            "missing_flags": {"status": "success", "data": {}},
            "failed_request": {"status": "error", "data": {"enable-feature": ",".join(row["service"]["enable_features"])}},
            "malformed": None,
        }
        for case, response in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                flags = root / "native-flags.json"
                flags.write_text("not JSON" if case == "malformed" else json.dumps(response))
                checked = subprocess.run([sys.executable, "-c", proof, str(PLAN / "install-plan.json"), str(flags)],
                                         env={k: os.environ[k] for k in ("PATH", "TMPDIR") if k in os.environ},
                                         capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode == 0, case in ("valid", "superset"), checked.stderr)


    def test_claude_review_actual_argv_keeps_frozen_read_only_contract(self):
        import shlex
        program = self.row("cross-family-review")["acceptance"]["after_sign_in"]["command"]
        assignment = next(line for line in program.splitlines() if line.startswith("claude_review_argv=("))
        base, head = "3" * 40, "4" * 40
        env = {k: os.environ[k] for k in ("PATH", "TMPDIR") if k in os.environ}
        env.update(plan_dir=str(PLAN), gpt_base=base, gpt_head=head)
        capture = assignment + "\n" + shlex.join([
            sys.executable, "-c", "import json,sys;print(json.dumps(sys.argv[1:]))"
        ]) + ' "${claude_review_argv[@]}"'
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", capture],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(result.stdout)
        self.assertEqual(argv[:3], ["claude", "-p",
            f"Review this GPT-authored diff read-only; report file:line correctness findings. "
            f"The immutable base is {base} and head is {head}. "
            "Read the original repository files for each finding. Do not edit or publish."])
        expected = {"--tools": "Read,Glob,Grep", "--disallowedTools": "Workflow,Agent,mcp__*",
                    "--permission-mode": "dontAsk", "--max-turns": "48", "--model": "opus", "--effort": "max"}
        for flag, value in expected.items():
            self.assertEqual(argv.count(flag), 1)
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]),
                         json.loads((PLAN / "cross-review-delivery.schema.json").read_text()))
        self.assertEqual(program.count("timeout --kill-after=15s 1200s"), 2)

    def test_review_requires_delivered_head_bound_native_structured_output(self):
        import copy
        import shlex
        command = self.row("cross-family-review")["acceptance"]["after_sign_in"]["command"]
        self.assertIn("--json-schema", command)
        proof = command.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        claude_head, gpt_head = "1" * 40, "2" * 40
        gpt = [{"type": "item.completed", "item": {"type": "command_execution", "status": "completed",
                "exit_code": 0, "command": shlex.join(["git", "-C", str(ROOT), "show", claude_head])}},
               {"type": "item.completed", "item": {"type": "agent_message", "text": "Delivered GPT review"}},
               {"type": "turn.completed"}]
        report = {"reviewed_head": gpt_head, "verdict": "findings",
                  "findings": [{"file": "fixture.py", "line": 8, "description": "Concrete fixture defect"}],
                  "summary": "Completed review of the immutable fixture."}
        cases = ("valid_findings", "valid_no_findings", "valid_native_system_metadata", "status_only", "list_output", "wrong_head", "missing_head",
                 "inconsistent_verdict", "unknown_verdict", "string_findings", "bool_line", "zero_line",
                 "blank_file", "blank_description", "blank_summary", "unexpected_field", "native_failure",
                 "duplicate_terminal", "native_error", "workflow_handoff", "background_terminated")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                delivered = copy.deepcopy(report)
                if case == "valid_no_findings":
                    delivered.update(verdict="no_findings", findings=[])
                elif case == "wrong_head":
                    delivered["reviewed_head"] = claude_head
                elif case == "missing_head":
                    del delivered["reviewed_head"]
                elif case == "inconsistent_verdict":
                    delivered["verdict"] = "no_findings"
                elif case == "unknown_verdict":
                    delivered["verdict"] = "started"
                elif case == "string_findings":
                    delivered["findings"] = "None"
                elif case in ("bool_line", "zero_line"):
                    delivered["findings"][0]["line"] = True if case == "bool_line" else 0
                elif case in ("blank_file", "blank_description"):
                    delivered["findings"][0][case.removeprefix("blank_")] = " "
                elif case == "blank_summary":
                    delivered["summary"] = " "
                elif case == "unexpected_field":
                    delivered["status"] = "started"
                terminal = {"type": "result", "subtype": "success", "is_error": False,
                            "result": "Review complete", "structured_output": delivered}
                if case == "status_only":
                    del terminal["structured_output"]
                elif case == "list_output":
                    terminal["structured_output"] = []
                elif case == "native_failure":
                    terminal.update(subtype="error_max_turns", is_error=True)
                claude = [terminal]
                if case == "valid_native_system_metadata":
                    claude[:0] = [{"type": "system", "subtype": "permission_denied",
                                   "message": "Synthetic native permission notice", "tool_name": tool}
                                  for tool in ("Read", "Grep")]
                elif case == "duplicate_terminal":
                    claude.append(copy.deepcopy(terminal))
                elif case == "native_error":
                    claude.insert(0, {"type": "error", "error": "Synthetic native failure"})
                elif case == "workflow_handoff":
                    claude.insert(0, {"type": "assistant", "message": {"content": [
                        {"type": "tool_use", "id": "handoff", "name": "Workflow", "input": {}}]}})
                (root / "gpt-review.jsonl").write_text("\n".join(json.dumps(e) for e in gpt))
                (root / "claude-review.jsonl").write_text("\n".join(json.dumps(e) for e in claude))
                (root / "claude-review.stderr").write_text(
                    "Terminated background workflow at session exit\n" if case == "background_terminated" else "")
                checked = subprocess.run(["python3", "-c", proof, str(root), claude_head, str(ROOT), gpt_head],
                                         capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode == 0, case in ("valid_findings", "valid_no_findings", "valid_native_system_metadata"), checked.stderr)
                self.assertEqual((root / "claude-review.json").exists(), checked.returncode == 0)

    def test_inspector_native_metadata_preserves_linked_recipe_requirement(self):
        import hashlib
        import shlex
        command = self.row("mcp-inspector")["acceptance"]["after_sign_in"]["command"]
        proof = next(b for b in re.findall(r"<<'PY'\n(.*?)\nPY", command, re.S)
                     if "Frozen Inspector recipe changed" in b)
        for case in ("valid", "missing_result", "tool_error", "wrong_recipe"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "probe.sh").write_text("Synthetic frozen probe\n")
                digest = hashlib.sha256((root / "probe.sh").read_bytes()).hexdigest()
                recipe = shlex.join(["bash", str(root / "probe.sh"), str(root), "claude"])
                events = [{"type": "system", "subtype": "permission_denied", "message": value}
                          for value in ("Native notice", None, [], 1, True)]
                events.append({"type": "assistant", "message": {"content": [{
                    "type": "tool_use", "id": "probe", "name": "Bash", "input": {
                        "command": recipe if case != "wrong_recipe" else "bash /different/probe.sh"}}]}})
                if case != "missing_result":
                    events.append({"type": "user", "message": {"content": [{
                        "type": "tool_result", "tool_use_id": "probe", "is_error": case == "tool_error",
                        "content": "INSPECTOR_CLI_OK\nINSPECTOR_WEB_OK\nINSPECTOR_STOPPED\n"}]}})
                events.append({"type": "result", "subtype": "success", "is_error": False})
                (root / "claude.jsonl").write_text("\n".join(json.dumps(e) for e in events))
                (root / "claude-tools.json").write_text(json.dumps({"tools": [{"name": "fixture"}]}))
                (root / "claude-page.html").write_text("<html>synthetic fixture</html>")
                (root / "claude-env.txt").write_text("false\n")
                checked = subprocess.run(["python3", "-c", proof, str(root), "claude", digest],
                                         capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode == 0, case == "valid", checked.stderr)

    def test_skill_listing_uses_regular_capture_and_cleans_up_on_failure(self):
        native_jq = shutil.which("jq")
        self.assertIsNotNone(native_jq)
        command = self.row("skill-discovery")["acceptance"]["post_install"]["command"]
        for case in ("valid", "missing_claude", "missing_codex", "empty", "malformed", "producer_failure", "wrong_hash"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binaries, scratch, state = root / "bin", root / "tmp", root / "state"
                for p in (binaries, scratch, state / "skills"):
                    p.mkdir(parents=True)
                trace = root / "trace.jsonl"
                lock = state / "skills/.skill-lock.json"
                lock.write_text(json.dumps({"skills": {"find-skills": {"skillFolderHash":
                    "wrong" if case == "wrong_hash" else "76a98a285cb0434f3d39e1a873823556330e398b"}}}))
                npx = binaries / "npx"
                npx.write_text("#!" + sys.executable + "\n" + """
import json, os, stat, sys
assert sys.argv[1:] == ['--yes', 'skills@1.7.0', 'list', '-g', '-a', 'claude-code', 'codex', '--json']
assert stat.S_ISREG(os.fstat(1).st_mode), 'listing stdout must be a regular file'
with open(os.environ['FIXTURE_TRACE'], 'a') as stream:
    stream.write(json.dumps(['producer', os.readlink('/proc/self/fd/1')]) + '\\n')
case = os.environ['FIXTURE_CASE']
agents = ['Claude Code', 'Codex']
if case == 'missing_claude': agents.remove('Claude Code')
if case == 'missing_codex': agents.remove('Codex')
if case == 'malformed': print('{broken')
elif case != 'empty': print(json.dumps([{'name':'find-skills', 'agents':agents}]))
sys.exit(42 if case == 'producer_failure' else 0)
""")
                npx.chmod(0o755)
                jq = binaries / "jq"
                jq.write_text("#!" + sys.executable + "\n" + """
import json, os, stat, sys
path = sys.argv[-1]
assert stat.S_ISREG(os.stat(path).st_mode)
with open(os.environ['FIXTURE_TRACE'], 'a') as stream:
    stream.write(json.dumps(['reader', path]) + '\\n')
os.execv(os.environ['FIXTURE_JQ'], [os.environ['FIXTURE_JQ'], *sys.argv[1:]])
""")
                jq.chmod(0o755)
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                    env={"HOME": str(root / "home"), "XDG_STATE_HOME": str(state),
                         "TMPDIR": str(scratch), "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                         "FIXTURE_TRACE": str(trace), "FIXTURE_CASE": case, "FIXTURE_JQ": native_jq},
                    capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode == 0, case == "valid", result.stderr)
                observations = [json.loads(s) for s in trace.read_text().splitlines()]
                capture = observations[0][1]
                readers = [item[1] for item in observations if item[0] == "reader" and item[1] != str(lock)]
                self.assertTrue(all(path == capture for path in readers))
                if case == "valid":
                    self.assertEqual(readers, [capture, capture])
                self.assertEqual(list(scratch.iterdir()), [])

    def test_agentsview_sync_wakes_idle_backend_and_health_remains_discriminating(self):
        cases = ("valid", "sync_failure", "stopped", "unresponsive",
                 *(f"{issue}:{agent}" for issue in ("empty_sessions", "wrong_agent", "zero_messages", "empty_days", "zero_usage")
                   for agent in ("claude", "codex")))
        command = self.row("session-analytics")["acceptance"]["service_health"]["command"]
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binary = root / "eco/bin/agentsview"
                binary.parent.mkdir(parents=True)
                trace = root / "trace.jsonl"
                binary.write_text("#!" + sys.executable + "\n" + """
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
case = os.environ['FIXTURE_CASE']
trace = Path(os.environ['FIXTURE_TRACE'])
active = trace.with_suffix('.active')
with trace.open('a') as stream:
    stream.write(json.dumps(argv) + '\\n')
if argv == ['sync']:
    if case == 'sync_failure': sys.exit(42)
    if case != 'stopped': active.write_text('fixture backend awake')
elif argv == ['daemon', 'status']:
    if not active.exists(): print('agentsview not running')
    elif case == 'unresponsive': print('agentsview running at fixture; not responding')
    else: print('agentsview running at fixture')
else:
    agent = argv[argv.index('--agent') + 1]
    issue = case.removesuffix(':' + agent) if case.endswith(':' + agent) else ''
    if argv[:2] == ['session', 'list']:
        sessions = [{'agent': 'foreign' if issue == 'wrong_agent' else agent,
                     'message_count': 0 if issue == 'zero_messages' else 1}]
        print(json.dumps({'sessions': [] if issue == 'empty_sessions' else sessions}))
    elif argv[:2] == ['usage', 'daily']:
        totals = dict(inputTokens=1, outputTokens=0, cacheReadTokens=0, cacheCreationTokens=0)
        if issue == 'zero_usage': totals['inputTokens'] = 0
        print(json.dumps({'daily': [] if issue == 'empty_days' else [{}], 'totals':totals}))
    else: sys.exit(8)
""")
                binary.chmod(0o755)
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                    env={"PATH": os.environ["PATH"], "HOME": str(root / "home"), "ECO_ROOT": str(root / "eco"),
                         "XDG_STATE_HOME": str(root / "state"), "TMPDIR": str(root),
                         "FIXTURE_CASE": case, "FIXTURE_TRACE": str(trace)},
                    capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode == 0, case == "valid", result.stderr)
                calls = [json.loads(s) for s in trace.read_text().splitlines()]
                self.assertEqual(calls[0], ["sync"])
                if case == "sync_failure":
                    self.assertEqual(calls, [["sync"]])
                    self.assertEqual(result.returncode, 42)
                else:
                    self.assertEqual(calls[1], ["daemon", "status"])
                if case == "valid":
                    self.assertEqual([(a[0], a[1] if len(a) > 1 else "") for a in calls],
                                                                          [("sync", ""), ("daemon", "status"), ("session", "list"),
                                      ("usage", "daily"), ("session", "list"), ("usage", "daily")])

    def test_betterleaks_native_test_output_survives_discarded_stdout(self):
        helper = PLAN / "config/betterleaks-accept.sh"
        for code in (0, 42):
            with self.subTest(upstream_exit=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binaries = root / "bin"
                binaries.mkdir()
                for name, program in {
                    "git": """import sys
from pathlib import Path
if 'clone' in sys.argv: Path(sys.argv[-1]).mkdir()
elif 'rev-parse' in sys.argv: print('81aff7a638638aae3a659845d089043e1d8fe9ac')
else: sys.exit(8)
""",
                    "mise": """import os,sys
assert sys.argv[1:5] == ['exec','go@1.25.12','--','make']
assert sys.argv[-1] == 'test'
print('=== RUN SyntheticUpstreamOutput')
print('--- SKIP SyntheticUpstreamSkip')
sys.exit(int(os.environ['FIXTURE_UPSTREAM_EXIT']))
""",
                    "betterleaks": """import os,sys
from pathlib import Path
assert sys.argv[1] == 'dir' and '--redact' in sys.argv and '--no-banner' in sys.argv
Path(os.environ['FIXTURE_SCAN_MARKER']).write_text('native scan reached')
""",
                }.items():
                    binary = binaries / name
                    binary.write_text("#!" + sys.executable + "\n" + program)
                    binary.chmod(0o755)
                marker = root / "scan.txt"
                result = subprocess.run(["bash", str(helper)],
                    env={"PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                         "TMPDIR": str(root), "plan_dir": str(root),
                         "FIXTURE_UPSTREAM_EXIT": str(code), "FIXTURE_SCAN_MARKER": str(marker)},
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=20)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn("=== RUN SyntheticUpstreamOutput", result.stderr)
                self.assertIn("--- SKIP SyntheticUpstreamSkip", result.stderr)
                self.assertEqual(marker.exists(), code == 0)

    def test_srt_checker_requires_exact_completed_recipe_and_unique_controls(self):
        import copy
        import shlex
        helper = (PLAN / "config/srt-client-accept.sh").read_text()
        checker = helper.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        recipe = helper.split("srt_native_recipe=\"$(cat <<'SRT'\n", 1)[1].split("\nSRT\n", 1)[0]
        positives = ("HELLO", "READ_CONTROL", "WRITE_CONTROL", "NETWORK_CONTROL", "ALLOW_WRITE",
                     "ALLOW_WRITE_VERIFY", "APPEND_CONTROL", "APPEND_VERIFY", "WRITE_DIGEST_CONTROL")
        good = ["hello world", *(f"SRT_{p}_EXIT=0" for p in positives),
                "SRT_DENY_READ_EXIT=13", "SRT_DENY_WRITE_EXIT=13", "SRT_DENY_NETWORK_EXIT=13",
                "SRT_ALLOW_WRITE_CONTROL=passed", "SRT_DENY_WRITE_PRESERVATION=passed", "SRT_NATIVE_USE_OK"]
        cases = ("valid", "text_blocks", "wrapped", "zero_deny", "negative_deny", "large_deny", "malformed_deny",
                 "duplicate_deny", "missing_positive", "duplicate_positive", "nonzero_positive",
                 "missing_preservation", "missing_terminal", "duplicate_terminal", "native_error",
                 "native_failure", "missing_result", "tool_error", "wrong_recipe", "unlinked",
                 "background", "partial", "in_progress", "marker_only_command")
        for client in ("claude", "codex"):
            for case in cases:
                with self.subTest(client=client, case=case), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "events.jsonl"
                    output = "\n".join(good) + "\n"
                    for bad, value in (("zero_deny", "0"), ("negative_deny", "-1"),
                                       ("large_deny", "256"), ("malformed_deny", "1x")):
                        if case == bad:
                            output = output.replace("SRT_DENY_READ_EXIT=13", "SRT_DENY_READ_EXIT=" + value)
                    if case == "duplicate_deny":
                        output += "SRT_DENY_READ_EXIT=13\n"
                    elif case == "missing_positive":
                        output = output.replace("SRT_HELLO_EXIT=0\n", "")
                    elif case == "duplicate_positive":
                        output += "SRT_HELLO_EXIT=0\n"
                    elif case == "nonzero_positive":
                        output = output.replace("SRT_HELLO_EXIT=0", "SRT_HELLO_EXIT=42")
                    elif case == "missing_preservation":
                        output = output.replace("SRT_DENY_WRITE_PRESERVATION=passed\n", "")
                    elif case == "partial":
                        output += "Command running in background with ID: fixture\n"
                    command = shlex.join(["rtk", "proxy", "bash", "-lc", recipe]) if case == "wrapped" else recipe
                    if case == "wrong_recipe":
                        command = command.replace('srt echo "hello world"', 'srt echo "different operation"')
                    elif case == "marker_only_command":
                        command = "printf '%s\\n' " + shlex.quote(recipe)
                    if client == "claude":
                        use = {"type": "tool_use", "id": "run", "name": "Bash", "input": {
                            "command": command, "run_in_background": case == "background"}}
                        returned = {"type": "tool_result", "tool_use_id": "other" if case == "unlinked" else "run",
                                    "content": [{"type": "text", "text": output}] if case == "text_blocks" else output,
                                    "is_error": case == "tool_error"}
                        events = [{"type": "assistant", "message": {"content": [use]}},
                                  {"type": "user", "message": {"content": [returned]}}]
                        terminal = {"type": "result", "subtype": "success", "is_error": False}
                        if case == "native_failure":
                            terminal.update(subtype="error_max_turns", is_error=True)
                        if case in ("missing_result", "in_progress"):
                            events.pop()
                    else:
                        item = {"type": "command_execution", "command": command,
                                "status": "in_progress" if case in ("in_progress", "background", "partial") else "completed",
                                "exit_code": 42 if case == "tool_error" else 0, "aggregated_output": output}
                        events = [{"type": "item.started" if case in ("missing_result", "unlinked") else "item.completed",
                                   "item": item}]
                        terminal = {"type": "turn.failed" if case == "native_failure" else "turn.completed"}
                    if case != "missing_terminal":
                        events.append(terminal)
                    if case == "duplicate_terminal":
                        events.append(copy.deepcopy(terminal))
                    if case == "native_error":
                        events.append({"type": "error", "error": "Synthetic native failure"})
                    events[:0] = [{"type": "system", "subtype": "permission_denied", "message": value}
                                  for value in ("Native notice", None, [], 1, True)]
                    path.write_text("\n".join(json.dumps(e) for e in events))
                    result = subprocess.run(["python3", "-c", checker, str(path), client, recipe],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode == 0, case in ("valid", "text_blocks", "wrapped"), result.stderr)

    def test_srt_recipe_preserves_each_step_exit_when_errexit_is_suppressed(self):
        helper = (PLAN / "config/srt-client-accept.sh").read_text()
        recipe = helper.split("srt_native_recipe=\"$(cat <<'SRT'\n", 1)[1].split("\nSRT\n", 1)[0]
        cases = ("valid", "HELLO", "READ_CONTROL", "WRITE_CONTROL", "NETWORK_CONTROL",
                 "ALLOW_WRITE", "ALLOW_WRITE_VERIFY", "APPEND_CONTROL", "APPEND_VERIFY",
                 "WRITE_DIGEST_CONTROL", "AFTER_DIGEST")
        for case in cases:
            with self.subTest(failing_step=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                binaries, allowed = root / "bin", root / "allowed"
                binaries.mkdir()
                allowed.mkdir()
                protected, read, policy = root / "protected.txt", root / "read.txt", root / "policy.json"
                protected.write_text("synthetic protected file\n")
                read.write_text("synthetic readable file\n")
                policy.write_text("{}\n")
                program = """
import hashlib, os, subprocess, sys
from pathlib import Path
name, args, case = Path(sys.argv[0]).name, sys.argv[1:], os.environ['FIXTURE_CASE']
fail = False
if name == 'srt':
    if args[0] == 'echo':
        print('hello world')
        fail = case == 'HELLO'
    else:
        args = args[2:]
        if args[0] == '--': args = args[1:]
        if args[0] in ('cat', 'curl') or args[-1] == os.environ['SRT_ACCEPT_DENY_WRITE']:
            sys.exit(13)
        label = 'APPEND_CONTROL' if '>>' in args[2] else 'ALLOW_WRITE'
        if case == label: sys.exit(42)
        sys.exit(subprocess.run(args).returncode)
elif name == 'curl':
    fail = case == 'NETWORK_CONTROL'
elif name == 'sh':
    status = subprocess.run(['/bin/sh', *args]).returncode
    fail = case == 'WRITE_CONTROL' and 'unsandboxed control' in args[1]
    if not fail: sys.exit(status)
elif name in ('cat', 'tail'):
    path = Path(args[-1])
    text = path.read_text()
    if name == 'tail': text = text.splitlines()[-1] + '\\n'
    sys.stdout.write(text)
    label = 'APPEND_VERIFY' if name == 'tail' else ('READ_CONTROL' if str(path) == os.environ['SRT_ACCEPT_DENY_READ'] else 'ALLOW_WRITE_VERIFY')
    fail = case == label
elif name == 'sha256sum':
    path = Path(args[-1])
    print(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + str(path))
    count = Path(os.environ['FIXTURE_HASH_COUNT'])
    previous = int(count.read_text()) if count.exists() else 0
    count.write_text(str(previous + 1))
    fail = case == ('WRITE_DIGEST_CONTROL' if previous == 0 else 'AFTER_DIGEST')
sys.exit(42 if fail else 0)
"""
                for name in ("srt", "cat", "tail", "curl", "sh", "sha256sum"):
                    binary = binaries / name
                    binary.write_text("#!" + sys.executable + "\n" + program)
                    binary.chmod(0o755)
                # Calling a function in an if condition suppresses Bash's implicit errexit.
                # This intentionally challenges each explicit per-step guard.
                wrapped = "probe() {\n" + recipe + "\n}\nif probe; then exit 0; else exit \"$?\"; fi"
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", wrapped],
                    env={"PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                         "SRT_ACCEPT_POLICY": str(policy), "SRT_ACCEPT_DENY_READ": str(read),
                         "SRT_ACCEPT_DENY_WRITE": str(protected), "SRT_ACCEPT_ALLOWED_DIR": str(allowed),
                         "SRT_ACCEPT_DENIED_URL": "https://synthetic.invalid",
                         "FIXTURE_CASE": case, "FIXTURE_HASH_COUNT": str(root / "hash-count")},
                    capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0 if case == "valid" else 42, result.stderr)
                self.assertEqual("SRT_NATIVE_USE_OK" in result.stdout, case == "valid")

    def test_inspect_example_resolves_from_its_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "inspect-ai-0.3.273"
            checkout.mkdir()
            binary = root / "inspect"
            binary.write_text("#!/usr/bin/env python3\nimport os,sys\nassert os.getcwd().endswith('/inspect-ai-0.3.273')\nassert sys.argv[2] == 'examples/theory_of_mind.py'\nsys.exit(42)\n")
            binary.chmod(0o755)
            result = subprocess.run(["bash", "-euo", "pipefail", "-c",
                                     self.row("inspect-ai")["acceptance"]["after_sign_in"]["command"]],
                                    env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                                         "tool_root": str(root), "XDG_STATE_HOME": str(root / "state")},
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 42, result.stderr)

    def test_srt_fixture_bindings_survive_an_empty_child_environment(self):
        import shlex
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixtures ' $literal"
            fixture.mkdir()
            allowed = fixture / "allowed"
            allowed.mkdir()
            paths = {"SRT_ACCEPT_POLICY": fixture / "policy.json",
                     "SRT_ACCEPT_DENY_READ": fixture / "read.txt",
                     "SRT_ACCEPT_DENY_WRITE": fixture / "write.txt",
                     "SRT_ACCEPT_ALLOWED_DIR": allowed}
            for path in list(paths.values())[:3]:
                path.write_text("synthetic fixture\n")
            binary = root / "codex"
            binary.write_text("#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(42)\n")
            binary.chmod(0o755)
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                   "SRT_ACCEPT_CLIENT": "codex", "SRT_ACCEPT_FIXTURE_ROOT": str(fixture),
                   "XDG_STATE_HOME": str(root / "state"), **{k: str(v) for k, v in paths.items()}}
            result = subprocess.run(["bash", str(PLAN / "config/srt-client-accept.sh")],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 42, result.stderr)
            argv = json.loads(next((root / "state").rglob("events.jsonl")).read_text())
            self.assertIn("--skip-git-repo-check", argv)
            self.assertEqual(argv[argv.index("-C") + 1], str(fixture))
            bindings = argv[-1].split("\n\n", 1)[1].split('srt echo "hello world"', 1)[0]
            probe = subprocess.run(["bash", "-c", bindings + '\nprintf "%s\\n" "$SRT_ACCEPT_POLICY" "$SRT_ACCEPT_DENY_READ" "$SRT_ACCEPT_DENY_WRITE" "$SRT_ACCEPT_ALLOWED_DIR"'],
                                   env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, timeout=20)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(probe.stdout.splitlines(), [str(p) for p in paths.values()])
            child = subprocess.run(["bash", "-c", bindings + "\npython3 -c " +
                                    shlex.quote('import os; print(os.environ.get("TMPDIR"))')],
                                   env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, timeout=20)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertEqual(child.stdout.strip(), str(allowed))

    def test_owned_old_agentsview_links_migrate_but_foreign_aliases_are_retained(self):
        # 2026-10-06 known-alias migration fixtures retain the superseded launcher versions.
        cases = (
            ("old binary", "0.43.0", "agentsview", False),
            ("old launcher", "0.43.0", "launcher", False),
            ("current binary", "0.44.0", "agentsview", False),
            ("current launcher", "0.44.0", "launcher", False),
            ("foreign symlink", None, None, False),
            ("regular aliases", None, None, True),
        )
        row = self.row("session-analytics")
        self.assertEqual(row["release"], "v0.44.0")
        self.assertIn("agentsview_0.44.0_linux_amd64.tar.gz", row["commands"][0])
        self.assertIn("037ea7a46d52e06b20363b4aa7cd7f28e32f31d8215803d6e9a0c96bac5818e3",
                      row["commands"][0])
        for name, version, executable, regular in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                eco = root / "eco"
                current = eco / "tools/agentsview-0.44.0"
                foreign = version is None
                target = root / "foreign" if foreign else eco / f"tools/agentsview-{version}" / executable
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("retained fixture")
                aliases = (eco / "bin/agentsview", root / ".local/bin/agentsview")
                for alias in aliases:
                    alias.parent.mkdir(parents=True, exist_ok=True)
                    if regular:
                        alias.write_text("regular fixture")
                    else:
                        alias.symlink_to(target)
                package = root / "release"
                package.mkdir()
                (package / "agentsview").write_text("current archive fixture")
                (package / "agentsview").chmod(0o755)
                archive = eco / "downloads/agentsview-0.44.0/agentsview_0.44.0_linux_amd64.tar.gz"
                archive.parent.mkdir(parents=True)
                subprocess.run(["tar", "-czf", str(archive), "-C", str(package), "agentsview"], check=True)
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", row["commands"][1]],
                                        env={"PATH": os.environ["PATH"], "TMPDIR": str(root),
                                             "HOME": str(root), "ECO_ROOT": str(eco), "plan_dir": str(PLAN)},
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 1 if foreign else 0, result.stderr)
                for alias in aliases:
                    if regular:
                        self.assertFalse(alias.is_symlink())
                        self.assertEqual(alias.read_text(), "regular fixture")
                    else:
                        self.assertEqual(alias.resolve(), target if foreign else current / "launcher")
                if foreign:
                    self.assertEqual(target.read_text(), "retained fixture")
                    self.assertFalse((current / "agentsview").exists(), "Foreign refusal extracted the archive")
                else:
                    self.assertEqual((current / "agentsview").read_text(), "current archive fixture")
                    self.assertEqual((current / "launcher").read_bytes(),
                                     (PLAN / "config/agentsview.sh").read_bytes())
                    if version == "0.43.0":
                        self.assertEqual(target.read_text(), "retained fixture")


    def test_inspector_probe_rejects_env_drift_and_port_collision_and_cleans_up(self):
        for inherited, occupied in (("false", "none"), ("true", "none"), (None, "none"),
                                    ("false", "LISTEN"), ("false", "ESTAB"), ("false", "BOUND-INACTIVE")):
            with self.subTest(inherited=inherited, occupied=occupied), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                pid = root / "web.pid"
                binaries = {
                    "npx": "#!/usr/bin/env python3\nimport json,os,sys,time\nfrom pathlib import Path\nif '--cli' in sys.argv:\n print(json.dumps({'tools':[{'name':'fixture'}]}))\nelse:\n Path(os.environ['INSPECTOR_TEST_PID']).write_text(str(os.getpid()))\n time.sleep(300)\n",
                    "curl": "#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nif not Path(os.environ['INSPECTOR_TEST_PID']).exists(): sys.exit(7)\nPath(sys.argv[sys.argv.index('--output')+1]).write_text('<html>fixture</html>')\n",
                    "ss": "#!/bin/sh\ncase \"$*\" in *-tan*) state=\"$INSPECTOR_TEST_OCCUPIED\";; *) state=LISTEN; [ \"$INSPECTOR_TEST_OCCUPIED\" = LISTEN ] || exit 0;; esac\nif [ \"$state\" != none ]; then printf '%s 0 128 127.0.0.1:16399 0.0.0.0:*\\n' \"$state\"; fi\n",
                }
                for name, body in binaries.items():
                    binary = root / name
                    binary.write_text(body)
                    binary.chmod(0o755)
                env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                       "INSPECTOR_TEST_PID": str(pid), "INSPECTOR_TEST_OCCUPIED": occupied}
                env.pop("MCP_AUTO_OPEN_ENABLED", None)
                if inherited is not None:
                    env["MCP_AUTO_OPEN_ENABLED"] = inherited
                result = subprocess.run(["bash", str(PLAN / "inspector-client-probe.sh"), str(root), "claude"],
                                        env=env, capture_output=True, text=True, timeout=20)
                succeeds = inherited == "false" and occupied == "none"
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)
                if succeeds:
                    self.assertIn("INSPECTOR_STOPPED", result.stdout)
                    self.assertEqual((root / "claude-env.txt").read_text().strip(), "false")
                    with self.assertRaises(ProcessLookupError):
                        os.kill(int(pid.read_text()), 0)
                else:
                    self.assertNotIn("INSPECTOR_WEB_OK", result.stdout)
                    self.assertFalse(pid.exists())

    def test_native_review_allows_completed_analysis_failure_but_rejects_incomplete_and_session_failure(self):
        import copy
        import shlex
        command = self.row("cross-family-review")["acceptance"]["after_sign_in"]["command"]
        proof = command.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        sha = "8c32a84b246da66e43a6188c973741b09329e223"
        gpt_sha = "b9dbe3c5a09cdefca435cd78c7f3dad46ca883a4"
        delivered = {"reviewed_head": gpt_sha, "verdict": "no_findings", "findings": [],
                     "summary": "No correctness defects found in the supplied immutable diff."}
        gpt = [
            {"type": "item.completed", "item": {"id": "read", "type": "command_execution",
             "status": "completed", "exit_code": 0,
             "command": shlex.join(["git", "-C", str(ROOT), "show", sha])}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Review text"}},
            {"type": "turn.completed"},
        ]
        baseline = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "analysis", "name": "Bash",
                 "input": {"command": "public receipt analysis", "run_in_background": False}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "analysis", "is_error": True,
                 "content": "Exit code 1\nSyntaxError: invalid public analysis expression\n"}]}},
            {"type": "result", "subtype": "success", "is_error": False, "result": "Review text", "structured_output": delivered},
        ]
        cases = ("read", "glob", "grep", "recovered_read", "write", "edit", "enter_plan", "exit_plan",
                 "workflow", "agent", "ordinary_failure", "ordinary_127", "timeout_124", "signal_130", "kill_137",
                 "interrupt_143", "extended_255", "error_zero", "missing_exit", "timeout_text",
                 "abort_xml", "requested_background", "automatic_background", "unlinked",
                 "missing_result", "mcp_error", "session_error", "empty_review", "missing_final")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                events = copy.deepcopy(baseline)
                call = events[0]["message"]["content"][0]
                result = events[1]["message"]["content"][0]
                codes = {"ordinary_127": 127, "timeout_124": 124, "signal_130": 130,
                         "kill_137": 137, "interrupt_143": 143, "extended_255": 255, "error_zero": 0}
                if case in ("read", "glob", "grep", "recovered_read"):
                    call["name"] = {"read": "Read", "glob": "Glob", "grep": "Grep",
                                    "recovered_read": "Read"}[case]
                    call["input"] = {"file_path": "/synthetic/original.py"}
                    result.update(is_error=False, content="Original source text without a shell footer")
                    if case == "recovered_read":
                        result.update(is_error=True, content="Native file-not-found error")
                        corrected = copy.deepcopy(events[:2])
                        corrected[0]["message"]["content"][0]["id"] = "corrected-read"
                        corrected[1]["message"]["content"][0].update(
                            tool_use_id="corrected-read", is_error=False, content="Correct original source")
                        events[2:2] = corrected
                elif case in ("write", "edit", "enter_plan", "exit_plan", "workflow", "agent"):
                    call["name"] = {"write": "Write", "edit": "Edit", "enter_plan": "EnterPlanMode",
                                    "exit_plan": "ExitPlanMode", "workflow": "Workflow", "agent": "Agent"}[case]
                    result.update(is_error=False, content="Forbidden tool completed")
                elif case in codes:
                    result["content"] = f"Exit code {codes[case]}\nRetained failed analysis\n"
                elif case == "missing_exit":
                    result["content"] = "An unresolved tool error\n"
                elif case == "timeout_text":
                    result["content"] += "Command timed out after 600000 milliseconds\n"
                elif case == "abort_xml":
                    result["content"] += "<error>Command was aborted before completion</error>\n"
                elif case == "requested_background":
                    call["input"]["run_in_background"] = True
                elif case == "automatic_background":
                    result["content"] += "Command running in background with ID: fixture\n"
                elif case == "unlinked":
                    result["tool_use_id"] = "another-call"
                elif case == "missing_result":
                    events.pop(1)
                elif case == "mcp_error":
                    call["name"] = "mcp__context_mode__ctx_execute"
                    call["input"] = {"language": "shell", "code": "public receipt analysis"}
                elif case == "session_error":
                    events[-1]["is_error"] = True
                    events[-1]["result"] = "Native session limit"
                elif case == "empty_review":
                    events[-1]["result"] = ""
                elif case == "missing_final":
                    events.pop()
                root = Path(directory)
                (root / "claude-review.stderr").write_text("")
                (root / "gpt-review.jsonl").write_text("\n".join(json.dumps(e) for e in gpt))
                (root / "claude-review.jsonl").write_text("\n".join(json.dumps(e) for e in events))
                checked = subprocess.run(["python3", "-c", proof, str(root), sha, str(ROOT), gpt_sha],
                                         capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode == 0, case in ("read", "glob", "grep", "recovered_read"),
                                 checked.stderr)

    def test_native_review_source_proof_rejects_echo_and_partial_mcp_results(self):
        import copy
        command = self.row("cross-family-review")["acceptance"]["after_sign_in"]["command"]
        proof = command.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        sha = "8c32a84b246da66e43a6188c973741b09329e223"
        gpt_sha = "b9dbe3c5a09cdefca435cd78c7f3dad46ca883a4"
        delivered = {"reviewed_head": gpt_sha, "verdict": "no_findings", "findings": [],
                     "summary": "No correctness defects found in the supplied immutable diff."}
        args = {"language": "shell", "code": f"git -C {ROOT} show {sha}"}
        initial = {"id": "source", "type": "mcp_tool_call", "server": "context-mode",
                   "tool": "ctx_execute", "arguments": args, "status": "in_progress"}
        completed = {**initial, "status": "completed", "error": None,
                     "result": {"content": [{"type": "text", "text": "Indexed immutable Git output"}]}}
        baseline = [{"type": "item.started", "item": initial},
                    {"type": "item.completed", "item": completed},
                    {"type": "item.completed", "item": {"type": "agent_message", "text": "Review text"}},
                    {"type": "turn.completed"}]
        for mutation in ("none", "echo", "timeout", "background", "failed", "missing_start", "different_start"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                events = copy.deepcopy(baseline)
                end = events[1]["item"]
                if mutation == "echo":
                    end["arguments"]["code"] = f"printf 'show {sha}'"
                elif mutation == "timeout":
                    end["result"]["content"][0]["text"] += "\n_(timed out after 60000ms — partial output shown above)_"
                elif mutation == "background":
                    end["arguments"]["background"] = True
                elif mutation == "failed":
                    end["status"] = "failed"
                elif mutation == "missing_start":
                    events.pop(0)
                elif mutation == "different_start":
                    events[0]["item"]["server"] = "other-server"
                (root / "claude-review.stderr").write_text("")
                (root / "gpt-review.jsonl").write_text("\n".join(json.dumps(e) for e in events))
                (root / "claude-review.jsonl").write_text(json.dumps(
                    {"type": "result", "subtype": "success", "is_error": False, "result": "Review text", "structured_output": delivered}))
                result = subprocess.run(["python3", "-c", proof, str(root), sha, str(ROOT), gpt_sha],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode == 0, mutation == "none", result.stderr)


    def test_review_snapshots_detect_same_status_worktree_and_index_edits(self):
        import shlex
        command = self.row("cross-family-review")["acceptance"]["after_sign_in"]["command"]
        snapshot_commands = [line.split(" > ", 1)[0] for line in command.splitlines()
                             if line.endswith('> "$run_dir/worktree-before.diff"')
                             or line.endswith('> "$run_dir/index-before.diff"')]
        self.assertEqual(len(snapshot_commands), 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)
            def snapshots():
                return [subprocess.check_output(shlex.split(line), cwd=root) for line in snapshot_commands]
            git("init", "-q")
            file = root / "fixture"
            file.write_text("original\n")
            git("add", "fixture")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--no-gpg-sign", "-qm", "fixture")
            file.write_text("indexed\n")
            git("add", "fixture")
            file.write_text("dirty\n")
            status = git("status", "--porcelain=v1", "-z")
            before = snapshots()
            file.write_text("different dirty\n")
            self.assertEqual(git("status", "--porcelain=v1", "-z"), status)
            working_edit = snapshots()
            self.assertNotEqual(working_edit[0], before[0])
            self.assertEqual(working_edit[1], before[1])
            git("add", "fixture")
            file.write_text("different dirty\nextra\n")
            git("add", "fixture")
            file.write_text("different dirty\n")
            self.assertEqual(git("status", "--porcelain=v1", "-z"), status)
            index_edit = snapshots()
            self.assertEqual(index_edit[0], working_edit[0])
            self.assertNotEqual(index_edit[1], working_edit[1])


if __name__ == "__main__":
    unittest.main()
