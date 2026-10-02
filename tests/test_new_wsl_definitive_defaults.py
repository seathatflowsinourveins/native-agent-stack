"""The new WSL's definitive defaults: one default per slot, one owner per tool, and no stale generated text.

Structural checks over committed files only (evidence/artifacts/new-wsl-definitive-defaults-20261001). They do not
judge any pick; they hold the manifest to its own rule.
"""
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001"
RECORD = ROOT / "docs/decisions/2026-10-01-new-wsl-definitive-defaults.md"
SELECTION = ROOT / "evidence/artifacts/new-wsl-clean-install-selection-20261001"
ROW_KINDS = {"judged", "first_round", "pinned", "project_practice", "no_blind_default_today", "added"}
DECISION_SLOTS = {"container-engine", "isolation-container-boundary", "code-search", "memory-owner", "context-supply",
                  "local-model-server"}
ROUTING = (r"(?i)gpt-6\.1|\bsol\b at|codex lane|anthropic judge|openai judge|claude family|gpt family|astra|arbitration was attempted|"
           r"approval policy|approval review")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_key(value):
    value = (value or "").strip().lower().rstrip("/")
    if "github.com/" in value:
        return "/".join(value.split("github.com/")[1].split("/")[:2])
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
        self.assertEqual({row["slot_id"] for row in self.rows}, set(self.decisions))
        self.assertEqual(len(self.decisions), len(self.convergence["decisions"]) + len(self.convergence["added_slots"]))
        added_jobs = {d["slot_id"]: d["job"] for d in self.convergence["added_slots"]}
        owners = {}
        for row in self.rows:
            sid = row["slot_id"]
            with self.subTest(slot=sid):
                self.assertTrue(row.get("job"), sid)
                self.assertEqual(row["job"], self.convergence["jobs"].get(sid, added_jobs.get(sid)))
                self.assertIn("resolution", row)
                resolution = row["resolution"]
                self.assertIsInstance(resolution, dict)
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
        self.assertEqual(set(measurements), {"browser-tool", "event-store-and-dashboards"})

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
            self.assertEqual(row["default"], added["default"]["name"])
            self.assertEqual(row["repository"], added["default"]["repository"])
            self.assertEqual(row["layer_id"], added["layer_id"])
            added_by_layer.setdefault(row["layer_id"], []).append(row["slot_id"])
        for lid, added in added_by_layer.items():
            order = [row["slot_id"] for row in self.rows if row["layer_id"] == lid]
            self.assertEqual(order[-len(added):], added)
        for correction in self.convergence["hygiene"]:
            row = rows[correction["slot_id"]]
            self.assertEqual(row[correction["field"]], correction["value"])
            self.assertIn(correction["reason"], row["resolution"].get("reason", "") + row["label"])
            if correction["field"] == "repository":
                self.assertEqual(row["resolution"]["judged_repository"], correction["judged_as"])

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


if __name__ == "__main__":
    unittest.main()
