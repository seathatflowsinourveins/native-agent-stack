"""The new WSL's definitive defaults: one default per slot, one owner per tool, and no stale generated text.

Structural checks over committed files only (evidence/artifacts/new-wsl-definitive-defaults-20261001, and the
layer-consensus record that its assembler reads last). They do not judge any pick; they hold the manifest to its own rule.
One class runs a committed program: the install plan's acceptance of the consensus row skill-authoring, against stand-ins.
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

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001"
RECORD = ROOT / "docs/decisions/2026-10-01-new-wsl-definitive-defaults.md"
SELECTION = ROOT / "evidence/artifacts/new-wsl-clean-install-selection-20261001"
CONSENSUS_ART = ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002"
CONSENSUS_RECORD = ROOT / "docs/decisions/2026-10-02-new-wsl-layer-consensus.md"
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
ROW_KINDS = {"judged", "first_round", "pinned", "project_practice", "no_blind_default_today", "added", "consensus"}
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
        cls.rows = cls.manifest["slots"]

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
        # A row is decided by the rounds (convergence.json) or added by the direct consensus (consensus.json), never both.
        self.assertEqual(set(self.decisions) & set(self.consensus_rows), set())
        self.assertEqual({row["slot_id"] for row in self.rows}, set(self.decisions) | set(self.consensus_rows))
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
            if row["row_kind"] == "consensus":
                continue  # No round decided it: it has no critic and no covering slot; its own tests are further down.
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
        added_by_layer = {}
        for added in self.convergence["added_slots"]:
            row = rows[added["slot_id"]]
            self.assertEqual(row["row_kind"], "added")
            if added["outcome"] in ("split", "not_installed"):
                # an added row that installs nothing keeps the named candidate only in its resolution
                self.assertEqual(row["repository"], "")
                self.assertTrue(row["installs_nothing_extra"])
                self.assertEqual(row["resolution"]["former_default"], added["default"])
            else:
                self.assertEqual(row["default"], added["default"]["name"])
                self.assertEqual(row["repository"], added["default"]["repository"])
            self.assertEqual(row["layer_id"], added["layer_id"])
            added_by_layer.setdefault(row["layer_id"], []).append(row["slot_id"])
        for lid, added in added_by_layer.items():
            # The consensus step places its rows after these, so the order is taken over the rows the rounds decided.
            order = [row["slot_id"] for row in self.rows if row["layer_id"] == lid and row["row_kind"] != "consensus"]
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
        for row in self.rows:
            resolution = row["resolution"]
            if resolution["outcome"] not in RESOLVED:
                continue
            with self.subTest(slot=row["slot_id"]):
                self.assertEqual(row["gpt"], stated.get(row["slot_id"]) or self.expected_gpt(row))
                self.assertEqual(row["label"], BASIS[resolution["outcome"]])
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
        # The consensus record's rule is appended whole, after the rounds' rule, and amendment 3 of its wave-2 batch after it.
        self.assertTrue(rule.endswith(" " + self.consensus["rule"] + " " + self.wave2["interim_rule"]))
        self.assertLess(rule.index("decision-round"), rule.index(self.consensus["rule"]))
        self.assertTrue(self.wave2["interim_rule"].startswith("Amendment 3 "))
        # Amendment 3 states its exception beside the no-install rule, which stays as the first round wrote it.
        self.assertEqual(self.manifest["no_install_rule"], self.foundation["no_install_rule"])
        self.assertEqual(self.manifest["no_install_rule_exception"], self.wave2["no_install_rule_exception"])
        self.assertIn("exception to the no-install rule", self.manifest["no_install_rule_exception"])

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
            exceptions.update((catalog, row["slot_id"]) for row in rows if not row["definitive"])
        self.assertEqual(exceptions, {("us-equities", "market-data-provider")})

    def test_settled_rows_are_measurements_with_verified_receipts(self):
        self.assertEqual({settlement["slot_id"] for settlement in self.settlements}, {"local-model-server"})
        self.assertEqual({row["slot_id"] for row in self.rows if row["measurement"] and row["measurement"]["returned"]},
                         {"local-model-server"})
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
        for settlement in self.settlements:
            slot = slots[settlement["slot_id"]]
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
        self.assertEqual(counts["slots"], 90)
        self.assertEqual(by_catalog, {"foundation": 70, "us-equities": 20})
        self.assertEqual(counts["layers"], 37)
        self.assertEqual(counts["installed"], 57)
        self.assertEqual(counts["interim"], 3)
        self.assertEqual(counts["by_row_kind"]["consensus"], 6)
        self.assertEqual(counts["by_state"]["resolved"], 23)
        self.assertEqual(counts["by_state"]["measurement"], 4)

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
        # Each is placed after the last row the rounds decided in its layer, in the record's order.
        for lid in sorted({row["layer_id"] for row in self.consensus_rows.values()}):
            in_layer = [row for row in self.rows if row["layer_id"] == lid]
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
        self.assertEqual(set(before), {row["slot_id"] for row in self.rows} - set(self.consensus_rows))
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
                if row["row_kind"] != "consensus":
                    # Every other field is the one the assembler builds before the consensus step; an interim (amendment 3)
                    # is the one the record gives, beside them.
                    self.assertEqual({key: value for key, value in row.items() if key not in ("amendments", "interim")},
                                     before[sid])
                    self.assertEqual(row.get("interim"), self.interims.get(sid))

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
        start, end = lines.index("### Amendments by direct consensus"), lines.index("<!-- tables:end -->")
        self.assertLess(start, end)
        table = [[cell.strip() for cell in line.split("|")[1:-1]] for line in lines[start:end] if line.startswith("| ")]
        self.assertEqual(table[:2], [["Slot", "Date", "Decision"], ["---"] * 3])
        self.assertEqual(table[2:], [[row["slot_id"], amendment["date_utc"], amendment["decision"]]
                                     for row in self.rows for amendment in row.get("amendments", [])])
        self.assertEqual(len(table) - 2, len(self.amend_rows))
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
        carried = {row["slot_id"]: row for row in self.rows if row.get("interim")}
        self.assertEqual(sorted(carried), ["code-search", "context-supply", "memory-owner"])
        self.assertEqual(sorted(carried), sorted(self.interims))
        self.assertEqual(self.manifest["counts"]["interim"], len(carried))
        assembler = load_assembler()
        for sid, row in carried.items():
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
        self.assertEqual({sid: (row["state"], row["definitive"]) for sid, row in carried.items()},
                         {"code-search": ("split", False), "context-supply": ("definitive", True),
                          "memory-owner": ("measurement", False)})
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
        ]
        for name, change, slot, message in cases:
            with self.subTest(case=name):
                self.assertTrue(attempt(change, slot).startswith(message), attempt(change, slot))


class InterimPlanChecks(unittest.TestCase):
    """The install plan's side of amendment 3, as check_plan.py and install.sh hold it. check_plan.py refuses a plan that
    does not install a recorded interim, one whose owner is not the interim's, and one whose interim install function does
    not call the acknowledgement gate first; the gate (install.sh's interim_acknowledged) refuses while an acknowledgement
    of the layer consensus's wave-2 batch is owed. Each case changes one thing in a scratch copy of the plan."""

    GATE_LINE = '  interim_acknowledged {slot} || return "$?"\n'

    def run_check(self, change_rows=None, change_install=None):
        """(exit status, output) of check_plan.py over a scratch copy of the plan and the manifest."""
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            plan_dir = scratch / "plan"
            shutil.copytree(PLAN, plan_dir, ignore=shutil.ignore_patterns("__pycache__"))
            manifest = scratch / "definitive-manifest.json"
            shutil.copy2(ART / "definitive-manifest.json", manifest)
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
        for slot in ("memory-owner", "code-search", "context-supply"):
            with self.subTest(slot=slot):
                line = self.GATE_LINE.format(slot=slot)
                code, out = self.run_check(change_install=lambda text: text.replace(line, "", 1) if line in text
                                           else self.fail(f"install.sh has no gate line for {slot}"))
                self.assertEqual(code, 1, out)
                self.assertIn(f"[interim] row {slot}: its install function in install.sh does not call "
                              f"`interim_acknowledged {slot}` before anything else", out)

    def test_an_install_script_without_the_gate_function_is_refused(self):
        code, out = self.run_check(change_install=lambda text: text.replace("interim_acknowledged() {",
                                                                            "interim_unused() {", 1))
        self.assertEqual(code, 1, out)
        self.assertIn("[interim] install.sh has no interim_acknowledged function that reads the wave-2 batch's "
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
        self.assertIn("memory-owner: refused: an interim install waits for the acknowledgements of the wave-2 batch still "
                      "owed by: claude, gpt", err)
        self.assertEqual(self.run_gate({"wave2": {"acknowledgements_owed": []}}), (0, ""))
        for broken in ({"wave2": {}}, {"wave2": {"acknowledgements_owed": "claude"}}, None):
            with self.subTest(consensus=broken):
                code, err = self.run_gate(broken, slot="code-search")
                self.assertEqual(code, 1)
                self.assertIn("code-search: refused: the acknowledgements of the wave-2 batch cannot be read", err)

    def test_the_gate_reads_the_committed_batch(self):
        owed = load(CONSENSUS_ART / "consensus.json")["wave2"]["acknowledgements_owed"]
        if not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("bash and jq are needed to run the gate")
        function = re.search(r"(?ms)^interim_acknowledged\(\) \{.*?^\}$", (PLAN / "install.sh").read_text(encoding="utf-8"))
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", f"{function.group(0)}\ninterim_acknowledged context-supply\n"],
                                env={**os.environ, "repo_root": str(ROOT)}, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1 if owed else 0, result.stderr)


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


if __name__ == "__main__":
    unittest.main()
