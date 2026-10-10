"""Native plugin provenance and parent skill discovery, using fixture homes."""
import contextlib
import hashlib
import io
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import install_claude_profile as profile
import install_skills
from scripts import skills_status

TARGETS = {"security-audit", "gh-fix-ci", "gh-address-comments", "frontend-design", "typesafe-ai",
           "security-best-practices", "security-threat-model"}


class NativePluginTests(unittest.TestCase):
    def test_plugin_pin_uses_native_metadata_and_never_the_skills_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            root = home / ".claude/plugins/cache/fixture/claude-api/pinned"
            root.mkdir(parents=True)
            (root / "skills/claude-api").mkdir(parents=True)
            raw = b"---\nname: claude-api\ndescription: fixture\n---\n"
            (root / "skills/claude-api/SKILL.md").write_bytes(raw)
            skill = {"name": "claude-api", "native_plugin": "claude-api@fixture", "path": "skills/claude-api",
                     "ref": "a" * 40, "skill_md_sha256": hashlib.sha256(raw).hexdigest()}
            registry = home / ".claude/plugins/installed_plugins.json"
            registry.write_text(json.dumps({"version": 2, "plugins": {"claude-api@fixture": [{"scope": "user",
                "installPath": str(root), "gitCommitSha": "a" * 40, "installedAt": "2026-10-10T00:00:00Z"}]}}))
            status = skills_status.native_plugin_status(skill, home, {})
            self.assertEqual("ok", status["state"])
            self.assertEqual("2026-10-10T00:00:00Z", status["installed_at"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual("ok", install_skills.process_skill(skill, home, "must-not-run", True, False, True))
            manifest = home / "plugin-manifest.json"
            manifest.write_text(json.dumps({"skills": [skill], "cli": {"version": "1.7.0"}}))
            with contextlib.redirect_stdout(io.StringIO()), patch.object(install_skills, "verify_skills_bin", side_effect=AssertionError("Vercel CLI must not run")):
                self.assertEqual(0, install_skills.main(["--manifest", str(manifest), "--home", str(home), "--check-only"]))
            self.assertFalse((home / ".agents/skills/claude-api").exists())
            skill["ref"] = "b" * 40
            self.assertEqual("pin_mismatch", skills_status.native_plugin_status(skill, home, {})["state"])


class ParentRoutingTests(unittest.TestCase):
    def test_project_router_discovery_uses_the_single_authored_source(self):
        router = ROOT / ".claude/skills/native-skill-routing"
        self.assertFalse(router.is_symlink())
        self.assertTrue((router / "SKILL.md").is_file())
        self.assertEqual((router / "SKILL.md").read_bytes(), profile.ROUTING_SKILL_SRC.read_bytes())

    def test_profile_installs_only_the_measured_security_audit_route(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual("installed", profile.install_routing_skill(home, False))
                self.assertEqual("skipped", profile.install_routing_skill(home, False))
            path = home / ".claude/skills/native-skill-routing/SKILL.md"
            text = path.read_text()
            self.assertIn("description:", text)
            self.assertIn("Skill", text)
            self.assertIn("security-audit", text)
            for name in TARGETS - {"security-audit"}:
                self.assertNotIn(name, text)
            self.assertNotIn("disable-model-invocation: true", text)
            path.write_text("local edit")
            with self.assertRaises(profile.InstallError):
                profile.install_routing_skill(home, False)
            self.assertEqual("local edit", path.read_text())

    def test_native_eval_staging_preserves_target_bytes_and_runs_no_model(self):
        spec = importlib.util.spec_from_file_location("stage_routing_eval", ROOT / "tools/skill-usage/stage_routing_eval.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            for row in json.loads((ROOT / "adoption/skills/manifest.json").read_text())["skills"]:
                if row["name"] in TARGETS:
                    # Byte-matching fixture selection is supplied from the public
                    # installed skill surface; never account/client configuration.
                    source = Path.home() / ".agents/skills" / row["name"] / "SKILL.md"
                    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != row["skill_md_sha256"]:
                        self.skipTest("pinned installed skills unavailable for native staging integration")
                    destination = home / ".agents/skills" / row["name"]
                    destination.mkdir(parents=True)
                    (destination / "SKILL.md").write_bytes(source.read_bytes())
            dest = Path(temp) / "staged"
            self.assertEqual(7, module.stage(dest, home))
            self.assertEqual(7, len(list((dest / "evals").glob("*/prompt.md"))))
            for name in TARGETS:
                self.assertEqual((home / ".agents/skills" / name / "SKILL.md").read_bytes(),
                                 (dest / "skills" / name / "SKILL.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
