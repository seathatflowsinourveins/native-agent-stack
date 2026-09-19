"""Adoption preflight boundaries; no credentials, services, or model calls."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.adoption_status import git_revision, inspect_adoption, main


class AdoptionStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        (self.root / "recipes").mkdir()
        (self.root / "recipes/README.md").write_text("Native recipe\n")
        self.path = self.root / "adoption/manifest.json"
        self.manifest = {
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "foundation-cpu", "label": "CPU foundation",
                          "required_commands": ["qmd"], "component_ids": ["qmd"],
                          "recipe_paths": ["recipes/README.md"]}],
            "default_profile": "foundation-cpu",
            "source": {"baseline_commit": "a" * 40,
                       "repository": "https://github.com/example/reference"},
        }
        self.save()
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch("scripts.adoption_status.platform.system", return_value="Linux"))
        self.enter.enter_context(patch("scripts.adoption_status.platform.machine", return_value="x86_64"))
        self.enter.enter_context(patch("scripts.adoption_status.sys.version_info", (3, 13, 7)))
        self.which = self.enter.enter_context(patch("scripts.adoption_status.shutil.which", return_value="/private/bin/qmd"))
        self.git = self.enter.enter_context(patch("scripts.adoption_status.git_revision", return_value="a" * 40))

    def save(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def inspect(self, profiles=None):
        return inspect_adoption(self.path, self.root, profiles)

    def test_present_prerequisites_do_not_claim_runtime_acceptance(self):
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["git"]["comparison"], "baseline_matches")
        self.assertEqual(result["platform"]["python"], "3.13.7")
        self.assertFalse(result["runtime_acceptance_verified"])
        self.assertNotIn("/private/bin", json.dumps(result))
        self.which.assert_called_once_with("qmd")

    def test_missing_command_and_recipe_are_reported(self):
        self.which.return_value = None
        (self.root / "recipes/README.md").unlink()
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_missing")
        self.assertFalse(result["profiles"][0]["commands"][0]["present"])
        self.assertFalse(result["profiles"][0]["recipes"][0]["present"])

    def test_unknown_profile_fails_without_probing_commands(self):
        result = self.inspect(["unknown"])
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertIn("unknown profile", result["errors"][0])
        self.which.assert_not_called()

    def test_explicit_profiles_do_not_require_unselected_commands(self):
        self.manifest["profiles"].append({"id": "gpu", "label": "GPU",
            "required_commands": ["vllm"], "component_ids": ["vllm"], "recipe_paths": []})
        self.save()
        result = self.inspect(["foundation-cpu", "foundation-cpu"])
        self.assertEqual(len(result["profiles"]), 1)
        self.which.assert_called_once_with("qmd")

    def test_unsupported_platform_or_python_blocks_readiness(self):
        for target, value in [("platform.machine", "arm64"), ("sys.version_info", (3, 12, 9))]:
            override = (patch("scripts.adoption_status." + target, return_value=value)
                        if target.startswith("platform") else patch("scripts.adoption_status." + target, value))
            with self.subTest(target=target), override:
                result = self.inspect()
                self.assertEqual(result["status"], "prerequisites_missing")
                self.assertFalse(result["platform"]["supported"])

    def test_unsafe_recipe_references_are_rejected_before_probing(self):
        for reference in (".", "../outside", "/etc/passwd", "recipes/../secret", "recipes//README.md", "C:\\secret", "recipes/./README.md"):
            with self.subTest(reference=reference):
                self.manifest["profiles"][0]["recipe_paths"] = [reference]
                self.save()
                self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
        self.which.assert_not_called()

    def test_symlink_recipe_and_symlink_parent_are_rejected(self):
        recipe = self.root / "recipes/README.md"
        recipe.unlink()
        recipe.symlink_to(self.path)
        self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
        recipe.unlink()
        recipe.parent.rmdir()
        recipe.parent.symlink_to(self.root / "adoption", target_is_directory=True)
        self.assertEqual(self.inspect()["manifest"]["status"], "invalid")

    def test_malformed_shapes_and_command_paths_are_rejected(self):
        for mutate in (lambda d: d.update(schema_version=True),
                       lambda d: d.update(profiles=[]),
                       lambda d: d["profiles"][0].update(required_commands=["/bin/qmd"]),
                       lambda d: d["profiles"][0].update(required_commands=["qmd --help"]),
                       lambda d: d["source"].update(baseline_commit="not-a-revision"),
                       lambda d: d["source"].update(repository="https://secret@example.com/repo")):
            with self.subTest(mutate=mutate):
                original = json.loads(json.dumps(self.manifest))
                mutate(self.manifest)
                self.save()
                self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
                self.manifest = original

    def test_invalid_json_and_duplicate_keys_are_bounded_errors(self):
        for raw in ('{"bad":', '{"schema_version":1,"schema_version":1}'):
            self.path.write_text(raw)
            result = self.inspect()
            self.assertEqual(result["manifest"]["status"], "invalid")
            self.assertNotIn(str(self.root), json.dumps(result))

    def test_git_difference_is_information_not_failed_acceptance(self):
        self.git.return_value = "b" * 40
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["git"]["comparison"], "baseline_differs")
        self.git.return_value = None
        self.assertEqual(self.inspect()["git"]["comparison"], "unavailable")

    def test_json_cli_does_not_emit_environment_or_credential_paths(self):
        output = io.StringIO()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "never-publish-this", "HF_TOKEN": "nor-this"}), contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertNotIn("never-publish-this", output.getvalue())
        self.assertNotIn("nor-this", output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertEqual(payload["manifest"]["status"], "valid")

    def test_missing_manifest_returns_exit_two_and_help_does_not_read(self):
        self.path.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--manifest", str(self.path), "--json"]), 2)
        with patch("scripts.adoption_status.inspect_adoption") as inspect, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        inspect.assert_not_called()

    def test_component_namespace_ids_are_supported(self):
        self.manifest["profiles"][0]["component_ids"] = ["affaan-m/ECC"]
        self.save()
        self.assertEqual(self.inspect()["status"], "prerequisites_present")

    def test_native_git_output_is_strict_and_timeout_is_bounded(self):
        with patch("scripts.adoption_status.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, f"{self.root}\n{'a' * 40}\n", "")
            self.assertEqual(git_revision(self.root), "a" * 40)
            self.assertEqual(run.call_args.kwargs["timeout"], 5)
            run.return_value = subprocess.CompletedProcess([], 0, f"/another/repository\n{'a' * 40}\n", "")
            self.assertIsNone(git_revision(self.root))
            run.return_value = subprocess.CompletedProcess([], 1, "untrusted output", "private/path/secret")
            self.assertIsNone(git_revision(self.root))
            run.side_effect = subprocess.TimeoutExpired(["git"], 5)
            self.assertIsNone(git_revision(self.root))

    def test_manifest_outside_explicit_root_is_rejected(self):
        result = inspect_adoption(self.path, self.root / "recipes")
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertIn("inside the repository root", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
