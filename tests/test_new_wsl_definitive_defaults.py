"""The new WSL's definitive defaults: one default per slot, one owner per tool, and no stale generated text.

Structural checks over committed files only (evidence/artifacts/new-wsl-definitive-defaults-20261001, and the
layer-consensus record that its assembler reads last). They do not judge any pick; they hold the manifest to its own rule.
"""
import hashlib
import json
import re
import subprocess
import sys
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


def load_assembler():
    """The assembler's functions, compiled from source so that no bytecode is written into the artifact folder."""
    path = ART / "assemble_manifest.py"
    module = types.ModuleType("assemble_manifest")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


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
        cls.consensus_rows = {row["slot_id"]: row for row in cls.consensus["add_rows"]}
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
        # The consensus record's rule is appended whole, after the rounds' rule.
        self.assertTrue(rule.endswith(" " + self.consensus["rule"]))
        self.assertLess(rule.index("decision-round"), rule.index(self.consensus["rule"]))

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
        self.assertEqual(counts["slots"], 89)
        self.assertEqual(by_catalog, {"foundation": 69, "us-equities": 20})
        self.assertEqual(counts["layers"], 37)
        self.assertEqual(counts["installed"], 56)
        self.assertEqual(counts["by_row_kind"]["consensus"], 5)
        self.assertEqual(counts["by_state"]["resolved"], 22)
        self.assertEqual(counts["by_state"]["measurement"], 4)

    def test_consensus_rows_are_the_records_rows_with_its_states(self):
        rows = {row["slot_id"]: row for row in self.rows}
        self.assertEqual(sorted(self.consensus_rows), ["credential-custody", "cross-family-review", "research-skill",
                                                       "skill-authoring", "skill-discovery"])
        self.assertEqual({row["slot_id"] for row in self.rows if row["row_kind"] == "consensus"}, set(self.consensus_rows))
        # The fields a consensus row must carry are the ones the assembler writes for a row the rounds decided.
        fields = load_assembler().ROW_FIELDS
        self.assertEqual(tuple(key for key in self.rows[0] if key != "amendments"), fields)
        for sid, recorded in self.consensus_rows.items():
            with self.subTest(slot=sid):
                self.assertEqual(rows[sid]["state"], recorded["state"])
                self.assertEqual(rows[sid], recorded)  # copied as the record gives it
                self.assertEqual(tuple(rows[sid]), fields)
        # Each is placed after the last row the rounds decided in its layer, in the record's order.
        for lid in sorted({row["layer_id"] for row in self.consensus_rows.values()}):
            in_layer = [row for row in self.rows if row["layer_id"] == lid]
            kinds = [row["row_kind"] == "consensus" for row in in_layer]
            self.assertEqual(kinds, sorted(kinds), lid)
            self.assertEqual([row["slot_id"] for row in in_layer if row["row_kind"] == "consensus"],
                             [row["slot_id"] for row in self.consensus["add_rows"] if row["layer_id"] == lid])

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
        for entry in self.consensus["amend_rows"]:
            self.assertEqual(set(entry), {"slot_id", "amendment"})
            self.assertEqual(set(entry["amendment"]) & PROTECTED, set(), entry["slot_id"])
            recorded.setdefault(entry["slot_id"], []).append(entry["amendment"])
        self.assertTrue(recorded)
        self.assertTrue(set(recorded) <= set(before), "an amendment names a row that no round decided")
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
                    # Every other field is the one the assembler builds before the consensus step.
                    self.assertEqual({key: value for key, value in row.items() if key != "amendments"}, before[sid])

    def test_consensus_records_are_the_hashed_published_copies(self):
        records = self.consensus["records"]
        copies = load(CONSENSUS_ART / "copy-notes.json")["copies"]
        named = {name: ref for name, ref in records.items() if name != "acknowledgements"}
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
        self.assertEqual(len(table) - 2, len(self.consensus["amend_rows"]))

    def test_consensus_decision_record_quotes_the_rule_and_the_owner(self):
        text = CONSENSUS_RECORD.read_text(encoding="utf-8")
        self.assertIn(self.consensus["rule"], text)
        self.assertIn(self.consensus["authorization"]["verbatim"], text)
        for sid in list(self.consensus_rows) + [entry["slot_id"] for entry in self.consensus["amend_rows"]]:
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


if __name__ == "__main__":
    unittest.main()
