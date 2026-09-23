"""Exercise the real manual-run source guards; no native recovery is executed."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / 'blueprints/convergence-practice'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActiveRecoveryPlanTests(unittest.TestCase):
    def test_default_application_plan_passes_actual_dispatch_source_guard(self):
        folder = BLUEPRINTS / 'offhost-app-state'
        module = load_module('active_app_plan', folder / 'run.py')
        trial = object.__new__(module.Trial)
        trial.plan = json.loads((folder / 'plan.json').read_text())
        trial.verify_frozen()

    def test_default_restic_hosted_plan_passes_actual_dispatch_source_guard(self):
        folder = BLUEPRINTS / 'offhost-restore'
        module = load_module('active_restic_plan', folder / 'verify.py')
        plan = module.load(folder / 'hosted-plan.json')
        self.assertEqual(plan['preparation_plan_sha256'], module.digest(folder / 'plan.json'))
        module.verify_sources(plan)

    def test_path_safety_is_pinned_and_a_changed_helper_trips_verify_frozen(self):
        # Round-3 security review, finding C: scripts/path_safety.py must be
        # pinned in frozen_sources, not merely adopted by the checks it
        # backs. Confirms the pin is present, then confirms a changed helper
        # (simulated by corrupting the recorded hash, since editing the real
        # checked-in file would not be reverted) trips verify_frozen().
        folder = BLUEPRINTS / 'offhost-app-state'
        module = load_module('active_app_plan_tamper', folder / 'run.py')
        trial = object.__new__(module.Trial)
        trial.plan = json.loads((folder / 'plan.json').read_text())
        entries = {entry['path']: entry for entry in trial.plan['frozen_sources']}
        self.assertIn('scripts/path_safety.py', entries)

        tampered = json.loads(json.dumps(trial.plan))
        tampered_entry = next(e for e in tampered['frozen_sources'] if e['path'] == 'scripts/path_safety.py')
        tampered_entry['sha256'] = '0' * 64
        trial.plan = tampered
        with self.assertRaisesRegex(ValueError, 'frozen local source differs: scripts/path_safety.py'):
            trial.verify_frozen()

    def test_path_safety_is_pinned_and_a_changed_helper_trips_verify_sources(self):
        folder = BLUEPRINTS / 'offhost-restore'
        module = load_module('active_restic_plan_tamper', folder / 'verify.py')
        plan = module.load(folder / 'hosted-plan.json')
        entries = {entry['path']: entry for entry in plan['frozen_sources']}
        self.assertIn('scripts/path_safety.py', entries)

        tampered_entry = next(e for e in plan['frozen_sources'] if e['path'] == 'scripts/path_safety.py')
        tampered_entry['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'frozen source changed: scripts/path_safety.py'):
            module.verify_sources(plan)
