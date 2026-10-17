"""Tests for the interim amendment by direct consensus in the definitive manifest's assembler.

Amendment 3 names a direct consensus that carries both families' acknowledgements as an interim's authority
(evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py, the interim rule's comment). So a family
batch may amend a row's interim, as an owner batch does, through the same amend_interim step; the amendment is recorded in
the row's amendments with the interim values it replaced, and overturned stays the record of the owner's decisions. As for
wave 2's interims, the gate on the acknowledgements is held where installing happens, not in the assembler: install.sh's
interim_acknowledged refuses every interim install while a batch owes one, and a direct-consensus batch lands only with
both acknowledgements recorded (the last test).
"""

from __future__ import annotations

import json
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001"
CONSENSUS = ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json"
ACK = "https://github.com/example/example/pull/1#issuecomment-{}"


def load_assembler():
    """Compiled from source, as tests/test_new_wsl_definitive_defaults.py's load_source does, so no bytecode is written
    into the artifact folder."""
    path = ART / "assemble_manifest.py"
    module = types.ModuleType("assemble_manifest_amendment_tests")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


class ConsensusInterimAmendmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assembler = load_assembler()
        cls.consensus = json.loads(CONSENSUS.read_text(encoding="utf-8"))
        cls.wave2_memory = next(entry for entry in cls.consensus["wave2"]["interim_rows"] if entry["slot_id"] == "memory-owner")

    def rows_with_the_wave2_interim(self):
        _, _, rows, _, _ = self.assembler.assemble_rows()
        by_slot = {row["slot_id"]: row for row in rows}
        self.assembler.apply_interims(rows, by_slot, [json.loads(json.dumps(self.wave2_memory))])
        return rows, by_slot

    @staticmethod
    def batch(acknowledged=("claude", "gpt"), date="2026-10-16"):
        acks = [{"family": family, "url": ACK.format(index), "at": f"{date}T00:00:00Z", "covers": "the amendment"}
                for index, family in enumerate(acknowledged)]
        return {"date_utc": date, "acknowledgements": acks,
                "acknowledgements_owed": sorted({"claude", "gpt"} - set(acknowledged))}

    @staticmethod
    def entry(**interim):
        return {"slot_id": "memory-owner",
                "amendment": {"date_utc": "2026-10-16", "by": "direct consensus of both model families", "decision": "move"},
                "interim": interim or {"default": "ai-memory 2.6.6", "pin": "tag v2.6.6 = commit abc"}}

    def test_it_amends_the_interim_and_keeps_the_replaced_values(self):
        rows, by_slot = self.rows_with_the_wave2_interim()
        before = json.loads(json.dumps(by_slot["memory-owner"]["interim"]))
        entry = self.entry()
        self.assembler.apply_consensus_interim_amendments(rows, by_slot, "wave6", self.batch(), [entry])
        row = by_slot["memory-owner"]
        self.assertEqual(row["interim"], {**before, **entry["interim"]})
        # Recorded beside the decided fields, in the row's direct-consensus amendments, with what it replaced; overturned stays
        # the owner decisions' record.
        self.assertEqual(row["amendments"][-1], {**entry["amendment"],
                                                  "interim_replaced": {key: before[key] for key in entry["interim"]}})
        self.assertNotIn("overturned", row)

    def test_it_amends_configuration_key_by_key_and_replaces_the_sources(self):
        # A version amendment corrects what the new route makes false: configuration key by key (the keys it names, each
        # one the interim carries; the others stay), and the sources as a whole list. What it replaced is recorded.
        rows, by_slot = self.rows_with_the_wave2_interim()
        before = json.loads(json.dumps(by_slot["memory-owner"]["interim"]))
        entry = self.entry(configuration={"listen": "127.0.0.1 on the host allocation's memory port"},
                           sources=["https://example.com/v3"])
        self.assembler.apply_consensus_interim_amendments(rows, by_slot, "wave6", self.batch(), [entry])
        interim = by_slot["memory-owner"]["interim"]
        self.assertEqual(interim["configuration"], {**before["configuration"],
                                                    "listen": "127.0.0.1 on the host allocation's memory port"})
        self.assertEqual(interim["sources"], ["https://example.com/v3"])
        self.assertEqual(by_slot["memory-owner"]["amendments"][-1]["interim_replaced"],
                         {"configuration": {"listen": before["configuration"]["listen"]}, "sources": before["sources"]})

    def test_the_records_pass_while_the_acknowledgements_are_owed(self):
        # The assembler applies the amendment as wave 2's interims are applied; install.sh holds the installs instead.
        rows, by_slot = self.rows_with_the_wave2_interim()
        self.assembler.apply_consensus_interim_amendments(rows, by_slot, "wave6", self.batch(()), [self.entry()])
        self.assertEqual(by_slot["memory-owner"]["interim"]["default"], "ai-memory 2.6.6")

    def test_it_is_refused_outside_the_rule(self):
        cases = [
            ("a field the rule does not let it amend", self.batch(), self.entry(authority={"kind": "x"}), None,
             "consensus memory-owner: an interim amendment changes only default, repository, pin, label, decided_by, "
             "open_acceptance_gates, configuration, sources"),
            ("a configuration key the interim does not carry", self.batch(), self.entry(configuration={"port": "1"}), None,
             "consensus memory-owner: an interim amendment changes only configuration keys the interim carries, not port"),
            ("a configuration that is not a table of text", self.batch(), self.entry(configuration={"listen": 1}), None,
             "consensus memory-owner: an interim amendment needs a non-empty configuration"),
            ("an empty configuration", self.batch(), self.entry(configuration={}), None,
             "consensus memory-owner: an interim amendment needs a non-empty configuration"),
            ("sources that are not a list of text", self.batch(), self.entry(sources="https://example.com"), None,
             "consensus memory-owner: an interim amendment needs a non-empty sources"),
            ("a label of another kind", self.batch(), self.entry(label="definitive default"), None,
             "consensus memory-owner: an interim's label starts with 'interim install'"),
            ("an amendment dated apart from its batch", self.batch(date="2026-10-17"), self.entry(), None,
             "consensus memory-owner: the amendment is dated 2026-10-16, and its batch 2026-10-17"),
            ("a row the owner already amended", self.batch(), self.entry(), lambda row: row.update(overturned={}),
             "consensus memory-owner: the row's interim already carries an amendment"),
            ("a second consensus amendment of the interim", self.batch(), self.entry(),
             lambda row: row.setdefault("amendments", []).append({"interim_replaced": {}}),
             "consensus memory-owner: the row's interim already carries an amendment"),
            ("a row with no interim", self.batch(), self.entry(), lambda row: row.pop("interim"),
             "consensus memory-owner: an interim amendment needs a row that carries an interim"),
        ]
        for name, batch, entry, mutate, message in cases:
            with self.subTest(name):
                rows, by_slot = self.rows_with_the_wave2_interim()
                if mutate:
                    mutate(by_slot["memory-owner"])
                with self.assertRaises(ValueError) as caught:
                    self.assembler.apply_consensus_interim_amendments(rows, by_slot, "wave6", batch, [entry])
                self.assertEqual(str(caught.exception), message)

    def test_an_entry_carries_only_its_slot_amendment_and_interim(self):
        rows, by_slot = self.rows_with_the_wave2_interim()
        entry = {**self.entry(), "owner_default": {}}
        with self.assertRaises(ValueError) as caught:
            self.assembler.apply_consensus_interim_amendments(rows, by_slot, "wave6", self.batch(), [entry])
        self.assertEqual(str(caught.exception), "consensus memory-owner: a consensus interim amendment is its slot_id, "
                                                "its amendment and its interim")

    def test_every_direct_consensus_batch_owes_no_acknowledgement(self):
        # The merge guard: an owed acknowledgement makes install.sh's interim_acknowledged refuse every interim install on a
        # fresh host, so a direct-consensus batch lands only with both families' acknowledgements recorded.
        for name, batch in self.assembler.wave_batches(self.consensus):
            if not self.assembler.is_owner_batch(batch):
                with self.subTest(name):
                    self.assertEqual(batch["acknowledgements_owed"], [])


if __name__ == "__main__":
    unittest.main()
