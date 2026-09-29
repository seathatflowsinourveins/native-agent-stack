"""Checks for the 2026-09-27 token-stack card bundle (evidence/artifacts/token-stack-cards-20260927)."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "evidence/artifacts/token-stack-cards-20260927"


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"token_stack_cards_{name}", BUNDLE / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BundleInputNameTests(unittest.TestCase):
    """tools/bundle.py keys every input by the basename it was given."""

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def run_bundle(self, returned_name):
        bundle = load_tool("bundle")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.write(base / "cards/fixture-tool.json", {
                "tool": "fixture-tool", "e2e_returned_results": {"records_shown": [{"id": "fixture-01"}]},
                "gpt6_review": {"verdict": "aligned", "findings": [], "resolutions": [], "harness": {},
                                "final_verdict": {"verdict": "adapted", "summary": "Fixture card",
                                                  "claims_verified": []}}})
            self.write(base / "cards/index.json", [{"tool": "fixture-tool"}])
            invoke = self.write(base / "invoke.json", {"tools": {}})
            returned = self.write(base / returned_name, {
                "captured_at": "2026-09-26T22:53:19Z", "scope": "fixture",
                "records": [{"id": "fixture-01", "command": {"argv": ["echo", "fixture"]},
                             "observation": "fixture output", "status": "pass"}]})
            raw = returned.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                code = bundle.main(["--cards", str(base / "cards"), "--invoke", str(invoke),
                                    "--returned-results", str(returned), "--repo-root", str(ROOT),
                                    "--out", str(base / "out")])
            self.assertEqual(code, 0)
            subset = json.loads((base / "out/returned-results-subset.json").read_text(encoding="utf-8"))
        return subset["source"], raw

    def test_the_canonical_returned_results_name_is_recorded_unchanged(self):
        source, raw = self.run_bundle("returned-results.json")
        self.assertEqual(source, {"name": "returned-results.json", "captured_at": "2026-09-26T22:53:19Z",
                                  "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "records": 1})

    def test_a_renamed_returned_results_file_is_keyed_by_its_supplied_basename(self):
        source, raw = self.run_bundle("returned-results-renamed.json")
        self.assertEqual(source, {"name": "returned-results-renamed.json", "captured_at": "2026-09-26T22:53:19Z",
                                  "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "records": 1})


if __name__ == "__main__":
    unittest.main()
