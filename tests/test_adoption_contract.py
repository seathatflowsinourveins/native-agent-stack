"""Keep portable adoption references and accepted SDK dependency artifacts aligned."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AdoptionContractTests(unittest.TestCase):
    def setUp(self):
        self.adoption = json.loads((ROOT / 'adoption/manifest.json').read_text())
        self.stack = json.loads((ROOT / 'manifests/stack.json').read_text())

    def test_every_component_has_a_confined_recipe(self):
        components = {item['id'] for item in self.stack['components']}
        self.assertEqual(set(self.adoption['recipe_map']), components)
        for reference in self.adoption['recipe_map'].values():
            path = (ROOT / reference).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            self.assertTrue(path.is_file(), reference)
        for profile in self.adoption['profiles']:
            self.assertTrue(set(profile['component_ids']) <= components)

    def test_continuation_references_resolve_without_copying_gate_states(self):
        for reference in self.adoption['sources'].values():
            self.assertTrue((ROOT / reference).is_file(), reference)
        gates = json.loads((ROOT / self.adoption['sources']['open_gates']).read_text())
        identifiers = {gate['id'] for gate in gates['open_gates']}
        self.assertTrue(set(self.adoption['continuation']['next_action_refs']) <= identifiers)
        for reference in self.adoption['continuation']['research_refs']:
            path = (ROOT / reference).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            self.assertTrue(path.is_file(), reference)
        self.assertNotIn('open_gates', self.adoption)
        self.assertFalse(self.adoption['policy']['historical_acceptance_transfers'])

    def test_foundation_and_trading_continuations_keep_separate_gates(self):
        sources = self.adoption['sources']
        self.assertEqual(sources['open_gates'], sources['foundation_catalog'])
        self.assertEqual(sources['current_convergence'], sources['foundation_catalog'])
        self.assertNotEqual(sources['open_gates'], sources['trading_open_gates'])
        trading = json.loads((ROOT / sources['trading_open_gates']).read_text())
        identifiers = {gate['id'] for gate in trading['open_gates']}
        references = set(self.adoption['continuation']['trading_next_action_refs'])
        self.assertTrue(references)
        self.assertTrue(references <= identifiers)
        self.assertFalse(references & set(self.adoption['continuation']['next_action_refs']))

    def test_lock_matches_accepted_inventory_and_all_pins_have_hashes(self):
        normal = lambda value: re.sub(r'[-_.]+', '-', value).lower()
        inventory = json.loads((ROOT / 'blueprints/us-equities/supply-chain/receipt.json').read_text())
        expected = {normal(item['name']): item['version'] for item in inventory['packages']}
        text = (ROOT / self.adoption['toolchain']['sdk_lock']).read_text()
        blocks = re.split(r'(?=^[A-Za-z0-9_.-]+==)', text, flags=re.M)
        pins = {}
        for block in blocks:
            match = re.match(r'([A-Za-z0-9_.-]+)==([^\s\\]+)', block)
            if match:
                self.assertRegex(block, r'--hash=sha256:[0-9a-f]{64}')
                self.assertNotIn(normal(match[1]), pins)
                pins[normal(match[1])] = match[2]
        self.assertEqual(pins, expected)
        for reference in ['sdk_direct_requirements', 'sdk_accepted_constraints']:
            records = (ROOT / self.adoption['toolchain'][reference]).read_text()
            required = dict((normal(name), version) for name, version in re.findall(
                r'^([A-Za-z0-9_.-]+)==([^\s]+)$', records, re.M))
            self.assertTrue(required)
            self.assertTrue(required.items() <= pins.items())
            if reference == 'sdk_accepted_constraints':
                self.assertEqual(required, expected)

    def test_host_example_claims_no_live_acceptance(self):
        host = json.loads((ROOT / 'adoption/host-state.example.json').read_text())
        self.assertEqual(host['selected_components'], [])
        self.assertEqual(host['local_receipts'], [])
        for client in host['clients'].values():
            self.assertEqual(set(client.values()), {'not_checked'})


if __name__ == '__main__':
    unittest.main()
