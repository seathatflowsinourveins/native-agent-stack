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
