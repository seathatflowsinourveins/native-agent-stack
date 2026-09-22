"""Keep portable adoption references and accepted SDK dependency artifacts aligned."""
import json
import re
import subprocess
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

    def test_platform_profiles_stay_linux_accepted_and_macos_drafted(self):
        profiles = {row['id']: row for row in self.adoption['platform_profiles']}
        self.assertEqual(profiles['linux-wsl2-x86_64']['status'], 'accepted')
        self.assertEqual(profiles['linux-wsl2-x86_64']['evidence_ref'], 'adoption/receipt.json')
        self.assertEqual(profiles['macos-arm64']['status'], 'drafted_not_accepted')
        self.assertIsNone(profiles['macos-arm64']['evidence_ref'])
        for row in profiles.values():
            self.assertTrue({'id', 'os', 'architecture', 'status', 'doc', 'evidence_ref'} <= set(row))
            self.assertTrue((ROOT / row['doc']).is_file(), row['doc'])
        # supported_platforms stays Linux-only; a drafted macOS profile does not
        # change what adoption_status.py reports as this host's supported platform.
        self.assertEqual(
            [(item['os'], item['architecture']) for item in self.adoption['supported_platforms']],
            [('linux', 'x86_64')],
        )

    def test_macos_arm64_foundation_profile_uses_plain_command_names(self):
        by_id = {row['id']: row for row in self.adoption['profiles']}
        profile = by_id['macos-arm64-foundation']
        components = {item['id'] for item in self.stack['components']}
        self.assertTrue(set(profile['component_ids']) <= components)
        for name in profile['required_commands']:
            self.assertRegex(name, r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')

    def test_host_example_claims_no_live_acceptance(self):
        host = json.loads((ROOT / 'adoption/host-state.example.json').read_text())
        self.assertEqual(host['selected_components'], [])
        self.assertEqual(host['local_receipts'], [])
        for client in host['clients'].values():
            self.assertEqual(set(client.values()), {'not_checked'})

    def test_bootstrap_step_zero_checks_out_the_attested_release_not_the_pre_adoption_baseline(self):
        """Codex cross-family review finding (codex-review-64): adoption/bootstrap.md
        step 0 used to check out `source.baseline_commit`
        (8f1da51757e925d319e2a50f080b02742e7e7168), a revision that predates
        `adoption/` and `tools/adoption/` entirely, so every later step on that page
        failed. Step 0 must check out `source.release_tag` (an attested release, at
        or after `source.release_commit`, which must actually contain both
        directories -- verified below with `git cat-file` on the named commit, not
        by trusting the manifest's own claim), and `baseline_commit` must remain
        exactly what it always meant (the pre-adoption comparison point
        `scripts/adoption_status.py` uses), never a checkout target."""
        source = self.adoption['source']
        self.assertIn('release_tag', source)
        self.assertIn('release_commit', source)
        self.assertEqual(source['baseline_commit'], '8f1da51757e925d319e2a50f080b02742e7e7168')

        bootstrap_text = (ROOT / 'adoption/bootstrap.md').read_text()
        step_zero_start = bootstrap_text.index('Step 0')
        step_zero = bootstrap_text[step_zero_start:step_zero_start + 1500]
        self.assertIn("['source']['release_tag']", step_zero)
        self.assertNotIn("['source']['baseline_commit']", step_zero)

        for path in ('adoption/bootstrap.md', 'tools/adoption/render_config.py'):
            result = subprocess.run(
                ['git', 'cat-file', '-e', f"{source['release_commit']}:{path}"],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(
                result.returncode, 0,
                f"source.release_commit ({source['release_commit']}) must contain {path} "
                f"(git cat-file -e failed: {result.stderr.strip()})",
            )
        # The pre-adoption baseline_commit is the actual regression case: it must
        # NOT contain these paths, confirming step 0's fix was necessary in the
        # first place (this is checking real git history, not a synthetic fixture).
        for path in ('adoption', 'tools/adoption'):
            result = subprocess.run(
                ['git', 'cat-file', '-e', f"{source['baseline_commit']}:{path}"],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"source.baseline_commit ({source['baseline_commit']}) unexpectedly contains "
                f"{path}; if this now passes, baseline_commit is no longer a reason to avoid "
                "checking it out in step 0 and this test (and the doc fix it guards) should be reviewed",
            )


if __name__ == '__main__':
    unittest.main()
