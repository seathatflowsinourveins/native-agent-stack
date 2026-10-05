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
OWNER_ADDED = ["command-output", "output-compression", "code-index", "code-graph", "repo-packing", "structured-data",
               "doc-conversion", "api-docs", "trace-viewer", "token-lane-carriers"]
OWNER_DEFAULTS = {"context-supply", "ccusage", "session-analytics", "promptfoo"}
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
        cls.owner_rows = {row["slot_id"]: row for row in cls.wave3["add_rows"]}
        cls.wave4 = cls.consensus["wave4"]
        cls.owner_amends = {entry["slot_id"]: entry for batch in (cls.wave3, cls.wave4)
                            for entry in batch["amend_rows"]}
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
        # amendment 4 of its wave-3 batch (the owner's decision of 2026-10-04), in the batches' order.
        self.assertTrue(rule.endswith(" " + self.consensus["rule"] + " " + self.wave2["interim_rule"] + " "
                                      + self.wave3["owner_rule"]))
        self.assertEqual(rule.count(self.wave3["owner_rule"]), 1)
        self.assertLess(rule.index("decision-round"), rule.index(self.consensus["rule"]))
        self.assertTrue(self.wave2["interim_rule"].startswith("Amendment 3 "))
        self.assertTrue(self.wave3["owner_rule"].startswith("Amendment 4 "))
        # Each amendment states its exception beside the no-install rule, which stays as the first round wrote it.
        self.assertEqual(self.manifest["no_install_rule"], self.foundation["no_install_rule"])
        self.assertEqual(self.manifest["no_install_rule_exception"],
                         self.wave2["no_install_rule_exception"] + " " + self.wave3["no_install_rule_exception"])
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
        # 90 before the wave-3 batch, and its ten owner rows (2026-10-04).
        self.assertEqual(counts["slots"], 100)
        self.assertEqual(by_catalog, {"foundation": 80, "us-equities": 20})
        self.assertEqual(counts["layers"], 37)
        # 56 after the layer consensus, 57 with its wave-2 statusline row, 59 with the two local-model slots settled by their
        # measurement (2026-10-03), 72 with wave 3, and 73 with the wave-4 Promptfoo owner default.
        self.assertEqual(counts["installed"], 73)
        # Three interims under amendment 3; the context-supply owner default replaced one of them.
        self.assertEqual(counts["interim"], 2)
        self.assertEqual(counts["by_row_kind"]["consensus"], 6)
        self.assertEqual(counts["by_row_kind"]["owner_decision"], 10)
        # 23, the ten owner rows, and context-supply, no longer definitive (ccusage and session-analytics stay resolved).
        self.assertEqual(counts["by_state"]["resolved"], 34)
        self.assertEqual(counts["by_state"]["definitive"], 30)
        self.assertEqual(counts["definitive"], 30)
        self.assertEqual(counts["by_state"]["measurement"], 6)
        self.assertEqual(counts["by_state"]["split"], 5)

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
                         OWNER_ADDED + [row["slot_id"] for row in self.rows if row.get("overturned")])
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
        self.assertEqual([row["slot_id"] for row in self.rows if row["row_kind"] == "owner_decision"], OWNER_ADDED)
        for sid, recorded in self.owner_rows.items():
            row = rows[sid]
            with self.subTest(slot=sid):
                # Copied as the batch gives it, with the manifest's row fields.
                self.assertEqual(row, recorded)
                self.assertEqual(tuple(row), assembler.ROW_FIELDS)
                self.assertEqual((row["catalog"], row["layer_id"]), ("foundation", "token-efficiency"))
                # Installed now, resolved, never definitive, and labelled as what it is.
                self.assertTrue(assembler.installs(row))
                self.assertEqual((row["state"], row["definitive"], row["measurement"]), ("resolved", False, None))
                batch_number = 4 if sid == "promptfoo" else 3
                self.assertTrue(row["label"].startswith(f"owner decision of 2026-10-04 (wave {batch_number}, amendment 4)"), row["label"])
                self.assertIn("not a blind round, not a consensus and not a measurement", row["label"])
                self.assertTrue(row["repository"].startswith("https://github.com/"), row["repository"])
                resolution = row["resolution"]
                self.assertEqual((resolution["outcome"], resolution["batch"]), ("added_by_owner_decision", "wave3"))
                for key in ("by", "reason", "pin", "install", "overturn"):
                    self.assertTrue(resolution[key].strip(), key)
                self.assertTrue(resolution["open_acceptance_gates"] and resolution["usage_rules"])
                self.assertIn("removes nothing by itself", resolution["overturn"])
                self.assertIn("docs/decisions/2026-10-04-token-full-stack-owner-default.md", resolution["sources"])
                for family in ("claude", "gpt"):
                    self.assertTrue(row[family].startswith("not judged"), row[family])
        # After every other row of the layer, in the batch's order.
        in_layer = [row["slot_id"] for row in self.rows if row["layer_id"] == "token-efficiency"]
        self.assertEqual(in_layer[-len(OWNER_ADDED):], OWNER_ADDED)

    def test_owner_pins_are_the_repository_pins(self):
        """Each owner row and owner default names the version manifests/stack.json records: the batch moves no pin."""
        stack = {component["id"]: component["version"] for component in load(ROOT / "manifests/stack.json")["components"]}
        components = {"command-output": "rtk", "output-compression": "headroom", "code-index": "jcodemunch-mcp",
                      "code-graph": "codebase-memory-mcp", "repo-packing": "repomix", "structured-data": "toon",
                      "doc-conversion": "markitdown", "api-docs": "context-hub", "trace-viewer": "otel-tui",
                      "ccusage": "ccusage", "session-analytics": "agentsview", "context-supply": "context-mode",
                      "promptfoo": "promptfoo"}
        self.assertEqual(set(components), set(OWNER_ADDED) - {"token-lane-carriers"} | OWNER_DEFAULTS)
        rows = {row["slot_id"]: row for row in self.rows}
        for sid, component in components.items():
            with self.subTest(slot=sid):
                self.assertRegex(rows[sid]["default"], r"(?<![0-9.])" + re.escape(stack[component]) + r"(?![0-9.])")
        interim = rows["code-search"]["interim"]["default"]
        self.assertIn("SocratiCode " + stack["socraticode"], interim)
        self.assertIn("semble 0.6.1", interim)

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
                batch_number = 4 if sid == "promptfoo" else 3
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
        for sid in OWNER_ADDED + sorted((OWNER_DEFAULTS - {"promptfoo"}) | OWNER_INTERIM):
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
    """The install plan's checks of the two local-model rows, run against stand-ins.

    The programs that accept.sh runs for local-generation-model and embedding-model, and the local-model-server row's
    after_sign_in smoke check (one embedding call to the settled embedder), are run as accept.sh runs them
    (bash -euo pipefail -c), with a scratch HOME and model store and with stub ollama and curl programs that print canned
    answers. The expected state passes, and each planted condition fails it. The fixtures are our own: no model server
    answers and no model runs. The embedder's library manifest is not published (the registry's copy carries its build
    path), so its case writes a stand-in manifest and puts that file's digest in place of the pinned one, after checking
    that the program names the pinned digest once.

    The files checks run `sha256sum --check --status`. Where this host's sha256sum rejects those options (the probe
    sha256sum_checks_like_gnu from tests/test_adoption_bootstrap.py: macOS's /sbin/sha256sum prints its usage and
    exits 1), a scratch sha256sum runs `shasum -a 256` in its place, as that module's run_install_pin does. A failed
    case's message carries the program's exit code, stdout and stderr.

    accept.sh itself runs the server row's after_sign_in stage once, with a scratch HOME and the stub curl: until the
    embedding-model row's model is in the store it prints skipped (step F9 runs that stage without any model row).
    """

    PINNED_LIBRARY = "ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d"
    SWIFT_FILE = "1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786"
    EMBEDDER_LAYER = "06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439"

    @classmethod
    def setUpClass(cls):
        for tool in ("bash", "jq") if sha256sum_checks_like_gnu() else ("bash", "jq", "shasum"):
            if shutil.which(tool) is None:
                raise unittest.SkipTest(f"{tool} is needed to run the acceptance programs")
        rows = {r["slot"]: r for r in load(PLAN / "install-plan.json")["owners"]}
        cls.generation = rows["local-generation-model"]["acceptance"]
        cls.embedding = rows["embedding-model"]["acceptance"]
        cls.server = rows["local-model-server"]["acceptance"]

    @staticmethod
    def table(num_ctx, quantization):
        """The two rows of `ollama show` that the checks read, padded as its table pads them."""
        return (f"  Model\n    quantization        {quantization}     \n\n"
                f"  Parameters\n    temperature          1        \n    num_ctx              {num_ctx}    \n\n")

    @staticmethod
    def store(scratch, model, tag, text):
        path = scratch / "home/.ollama/models/manifests/registry.ollama.ai/library" / model / tag
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_program(self, program, scratch, show="", reply=""):
        """The finished process of `program`, run as accept.sh runs it with the stubs first on PATH."""
        stub = scratch / "bin"
        stub.mkdir(exist_ok=True)
        (stub / "show.txt").write_text(show, encoding="utf-8")
        (stub / "reply.json").write_text(reply, encoding="utf-8")
        for name, canned in (("ollama", "show.txt"), ("curl", "reply.json")):
            (stub / name).write_text(f'#!/bin/sh\ncat "$STUB_DIR/{canned}"\n', encoding="utf-8")
            (stub / name).chmod(0o755)
        if not sha256sum_checks_like_gnu():
            (stub / "sha256sum").write_text('#!/bin/sh\nexec shasum -a 256 "$@"\n', encoding="utf-8")
            (stub / "sha256sum").chmod(0o755)
        env = {key: value for key, value in os.environ.items() if key not in ("OLLAMA_MODELS", "BASH_ENV", "ENV")}
        env.update(HOME=str(scratch / "home"), tool_root=str(scratch / "tools"), STUB_DIR=str(stub),
                   PATH=f"{stub}{os.pathsep}{os.environ.get('PATH', '')}")
        return subprocess.run(["bash", "-euo", "pipefail", "-c", program], env=env, capture_output=True, text=True,
                              timeout=60)

    @staticmethod
    def outcome(name, result):
        """A case's assertion message: its name, and the program's exit code, stdout and stderr."""
        return f"{name}: exit {result.returncode}\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"

    def test_the_programs_are_the_ones_accept_sh_runs(self):
        checker = load_source(PLAN / "check_plan.py", "check_plan")
        functions = checker.functions((PLAN / "accept.sh").read_text(encoding="utf-8"))
        for slot, acceptance in (("local-generation-model", self.generation), ("embedding-model", self.embedding)):
            self.assertEqual(checker.checks_of(functions[slot]),
                             [(stage, slot, "smoke", acceptance[stage]["command"]) for stage in ("post_install", "service_health")])
        self.assertIn(("after_sign_in", "local-model-server", "smoke", self.server["after_sign_in"]["command"]),
                      checker.checks_of(functions["local-model-server"]))

    def test_the_generation_files_check(self):
        cases = {"the expected state": (None, 0), "another 64k Modelfile": ("modelfile", 1),
                 "another model layer": ("layer", 1), "no created model": ("missing", 1)}
        for name, (change, want) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                models = scratch / "tools/ollama-models"
                models.mkdir(parents=True)
                for modelfile in ("swift-iq3s-s2o.Modelfile", "swift-iq3s-s2o-64k.Modelfile"):
                    shutil.copy(PLAN / "models" / modelfile, models / modelfile)
                if change == "modelfile":
                    (models / "swift-iq3s-s2o-64k.Modelfile").write_text("FROM swift-iq3s-s2o\nPARAMETER num_ctx 65536\n")
                if change != "missing":
                    layer = "0" * 64 if change == "layer" else self.SWIFT_FILE
                    self.store(scratch, "swift-iq3s-s2o-64k", "latest", json.dumps({"layers": [{"digest": "sha256:" + layer}]}))
                result = self.run_program(self.generation["post_install"]["command"], scratch)
                self.assertEqual(result.returncode == 0, want == 0, self.outcome(name, result))

    def test_the_embedding_files_check(self):
        program = self.embedding["post_install"]["command"]
        self.assertEqual(program.count(self.PINNED_LIBRARY), 1)
        library = '{"schemaVersion":2,"stand-in":true}'
        program = program.replace(self.PINNED_LIBRARY, hashlib.sha256(library.encode()).hexdigest())
        cases = {"the expected state": (None, 0), "another library manifest": ("library", 1),
                 "another derived layer": ("layer", 1)}
        for name, (change, want) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                self.store(scratch, "qwen3-embedding", "0.6b", library + ("\n" if change == "library" else ""))
                layer = "1" * 64 if change == "layer" else self.EMBEDDER_LAYER
                self.store(scratch, "qwen3-embedding-8k", "latest", json.dumps({"layers": [{"digest": "sha256:" + layer}]}))
                result = self.run_program(program, scratch)
                self.assertEqual(result.returncode == 0, want == 0, self.outcome(name, result))

    def test_the_service_checks(self):
        answer = json.dumps({"model": "swift-iq3s-s2o-64k", "response": "ready", "done": True})
        vector = json.dumps({"model": "qwen3-embedding-8k", "embeddings": [[0.01] * 1024]})
        generation, embedding = self.generation["service_health"]["command"], self.embedding["service_health"]["command"]
        cases = {
            "generation: the expected state": (generation, self.table(64000, "IQ3_S"), answer, 0),
            "generation: another context": (generation, self.table(65536, "IQ3_S"), answer, 1),
            "generation: another quantization": (generation, self.table(64000, "Q4_K_M"), answer, 1),
            "generation: an empty answer": (generation, self.table(64000, "IQ3_S"), json.dumps({"response": "", "done": True}), 1),
            "embedding: the expected state": (embedding, self.table(8192, "Q8_0"), vector, 0),
            "embedding: the server-wide context": (embedding, self.table(64000, "Q8_0"), vector, 1),
            "embedding: 512 dimensions": (embedding, self.table(8192, "Q8_0"), json.dumps({"embeddings": [[0.01] * 512]}), 1),
        }
        for name, (program, show, reply, want) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                (scratch / "home").mkdir()
                result = self.run_program(program, scratch, show, reply)
                self.assertEqual(result.returncode == 0, want == 0, self.outcome(name, result))

    def test_the_server_smoke_check(self):
        """The server row's after_sign_in check embeds with the settled embedder and runs or pulls no other model."""
        program = self.server["after_sign_in"]["command"]
        self.assertEqual(re.findall(r'"model":"([^"]*)"', program), ["qwen3-embedding-8k"])
        for absent in ("ollama run", "ollama pull", "embeddinggemma"):
            self.assertNotIn(absent, program)
        cases = {
            "one vector": (json.dumps({"model": "qwen3-embedding-8k", "embeddings": [[0.01] * 1024]}), 0),
            "no vector": (json.dumps({"model": "qwen3-embedding-8k", "embeddings": []}), 1),
            # the answer handleScheduleError gives a missing model (server/routes.go:3226-3227 at v0.35.0)
            "an error answer": (json.dumps({"error": 'model "qwen3-embedding-8k" not found, try pulling it first'}), 1),
        }
        for name, (reply, want) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                (scratch / "home").mkdir()
                result = self.run_program(program, scratch, reply=reply)
                self.assertEqual(result.returncode == 0, want == 0, self.outcome(name, result))

    def run_accept(self, scratch, reply):
        """The finished `accept.sh --only local-model-server --stage after_sign_in`, with a scratch HOME and the stub curl."""
        stub = scratch / "bin"
        stub.mkdir(exist_ok=True)
        (stub / "reply.json").write_text(reply, encoding="utf-8")
        (stub / "curl").write_text('#!/bin/sh\ncat "$STUB_DIR/reply.json"\n', encoding="utf-8")
        (stub / "curl").chmod(0o755)
        dropped = ("OLLAMA_MODELS", "BASH_ENV", "ENV", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "MISE_SHIMS_DIR", "MISE_DATA_DIR")
        env = {key: value for key, value in os.environ.items() if key not in dropped}
        env.update(HOME=str(scratch / "home"), STUB_DIR=str(stub), PATH=f"{stub}{os.pathsep}{os.environ.get('PATH', '')}")
        return subprocess.run(["bash", str(PLAN / "accept.sh"), "--only", "local-model-server", "--stage", "after_sign_in"],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_the_server_smoke_check_waits_for_the_embedding_row(self):
        """Until the embedding-model row has created qwen3-embedding-8k, accept.sh prints skipped for the stage, not a failure.

        Step F9 runs the server row's after_sign_in check without installing a model row (each installs only when named).
        Once the derived model's manifest is in the store that the embedding row's post_install check reads, the check runs.
        """
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("accept.sh refuses to run as root")
        vector = json.dumps({"model": "qwen3-embedding-8k", "embeddings": [[0.01] * 1024]})
        cases = {
            "no embedder in the store": (False, vector, "skipped", 0),
            "the embedder, one vector": (True, vector, "0", 0),
            "the embedder, no vector": (True, json.dumps({"model": "qwen3-embedding-8k", "embeddings": []}), "1", 1),
        }
        for name, (created, reply, printed, status) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                (scratch / "home").mkdir()
                if created:
                    self.store(scratch, "qwen3-embedding-8k", "latest",
                               json.dumps({"layers": [{"digest": "sha256:" + self.EMBEDDER_LAYER}]}))
                result = self.run_accept(scratch, reply)
                self.assertEqual((result.stdout, result.returncode),
                                 (f"local-model-server | after_sign_in | {printed}\n", status), self.outcome(name, result))
                if not created:
                    self.assertIn("install the embedding-model row first", result.stderr, self.outcome(name, result))


class ModelServerGuard(unittest.TestCase):
    """install.sh's guard before either local-model row downloads, pulls or creates anything, run against stand-ins.

    Both rows install what was measured on Ollama 0.35.0, so model_server_answers requires that the server answers
    `ollama ls` and that GET /api/version reports 0.35.0 (docs/api.md:1821-1843 and server/routes.go:2023 at v0.35.0).
    The function, read from install.sh as check_plan.py reads it, runs under bash -euo pipefail with stub ollama and curl
    programs first on PATH. The fixtures are our own: no model server answers.
    """

    @classmethod
    def setUpClass(cls):
        for tool in ("bash", "jq"):
            if shutil.which(tool) is None:
                raise unittest.SkipTest(f"{tool} is needed to run the guard")
        checker = load_source(PLAN / "check_plan.py", "check_plan")
        install = checker.functions((PLAN / "install.sh").read_text(encoding="utf-8"))
        cls.guard = install["model_server_answers"]
        cls.rows = {slot: install[slot] for slot in ("local-generation-model", "embedding-model")}

    def run_guard(self, scratch, listed, reply, curl_exit=0):
        """The finished guard, with a stub `ollama` whose `ls` succeeds when `listed` and a stub `curl` that prints `reply`."""
        stub = scratch / "bin"
        stub.mkdir()
        (stub / "reply.json").write_text(reply, encoding="utf-8")
        (stub / "ollama").write_text(f"#!/bin/sh\nexit {0 if listed else 1}\n", encoding="utf-8")
        (stub / "curl").write_text(f'#!/bin/sh\n[ {curl_exit} -eq 0 ] || exit {curl_exit}\ncat "$STUB_DIR/reply.json"\n',
                                   encoding="utf-8")
        for name in ("ollama", "curl"):
            (stub / name).chmod(0o755)
        env = {key: value for key, value in os.environ.items() if key not in ("BASH_ENV", "ENV")}
        env.update(STUB_DIR=str(stub), PATH=f"{stub}{os.pathsep}{os.environ.get('PATH', '')}")
        program = f"model_server_answers() {{\n{self.guard}\n}}\nmodel_server_answers"
        return subprocess.run(["bash", "-euo", "pipefail", "-c", program], env=env, capture_output=True, text=True,
                              timeout=60)

    def test_both_rows_run_the_guard_before_any_command(self):
        for slot, body in self.rows.items():
            lines = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("#")]
            with self.subTest(slot=slot):
                self.assertEqual(lines[:2], ['refresh_path || return "$?"', 'model_server_answers || return "$?"'])

    def test_the_server_must_answer_and_report_the_measured_version(self):
        cases = {
            "0.35.0": (True, json.dumps({"version": "0.35.0"}), 0, 0),
            "another version": (True, json.dumps({"version": "0.36.0"}), 0, 1),
            "an answer without a version": (True, json.dumps({"error": "not found"}), 0, 1),
            "the version request fails": (True, "", 7, 1),
            "no server answers": (False, json.dumps({"version": "0.35.0"}), 0, 1),
        }
        for name, (listed, reply, curl_exit, want) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                result = self.run_guard(Path(scratch), listed, reply, curl_exit)
                message = f"{name}: exit {result.returncode}\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                self.assertEqual(result.returncode, want, message)
                if name == "another version":
                    self.assertIn("reports version 0.36.0, not 0.35.0", result.stderr, message)


if __name__ == "__main__":
    unittest.main()
