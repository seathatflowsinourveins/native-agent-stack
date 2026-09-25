"""Skills status checker: nonmutating, value-free checks against a fake HOME.

Local integration class: every fixture lives under a per-test temporary directory
standing in for a user's home; the real skills CLI, lock file, and Claude/Codex
homes are never touched. Fixture "hash" fields are always computed with hashlib
from fixture content at test time, never hardcoded literals, so a drift test
mutates content and lets the digest follow rather than embedding a second,
independently-typed expectation.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts import skills_status as ss

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/skills_status.py"


class SkillsStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {"HOME": str(self.home)}

    # -- fixture builders ---------------------------------------------------

    def write_canonical(self, name: str, content: bytes) -> Path:
        directory = self.home / ".agents" / "skills" / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "SKILL.md"
        path.write_bytes(content)
        return path

    def make_skill(self, name, *, claude_listing="on", codex_enabled=True,
                   description_chars=120, content=None) -> dict:
        content = content if content is not None else f"# {name}\n\nBody text for {name}.\n".encode()
        self.write_canonical(name, content)
        return {
            "name": name,
            "tree_sha": hashlib.sha1(f"tree:{name}".encode()).hexdigest(),
            "skill_md_sha256": hashlib.sha256(content).hexdigest(),
            "skill_md_bytes": len(content),
            "description_chars": description_chars,
            "claude_listing": claude_listing,
            "codex_enabled": codex_enabled,
        }

    def build_manifest(self, skills, budget=None, cli_version="1.7.0") -> dict:
        manifest = {"schema_version": 1, "cli": {"version": cli_version}, "skills": list(skills)}
        if budget is not None:
            manifest["budget"] = budget
        return manifest

    def lock_entries_for(self, skills) -> dict:
        return {s["name"]: {"source": "github", "sourceType": "github",
                            "sourceUrl": "https://example.invalid/repo", "skillPath": f"skills/{s['name']}",
                            "skillFolderHash": s["tree_sha"], "installedAt": "2026-09-25T00:00:00Z",
                            "updatedAt": "2026-09-25T00:00:00Z"} for s in skills}

    def write_lock(self, entries: dict, version=3, path: Path | None = None) -> Path:
        lock_path = path or (self.home / ".agents" / ".skill-lock.json")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"version": version, "skills": entries}))
        return lock_path

    def write_claude_link(self, name: str, kind="relative") -> Path:
        claude_skills = self.home / ".claude" / "skills"
        claude_skills.mkdir(parents=True, exist_ok=True)
        link = claude_skills / name
        canonical = self.home / ".agents" / "skills" / name
        if kind == "relative":
            link.symlink_to(f"../../.agents/skills/{name}", target_is_directory=True)
        elif kind == "absolute":
            link.symlink_to(canonical, target_is_directory=True)
        elif kind == "copy":
            shutil.copytree(canonical, link)
        elif kind == "wrong_target":
            elsewhere = self.home / "elsewhere-skill"
            elsewhere.mkdir(exist_ok=True)
            link.symlink_to(elsewhere, target_is_directory=True)
        else:
            raise ValueError(kind)
        return link

    def write_claude_settings(self, overrides: dict, extra_env_sentinel=None) -> None:
        claude_dir = self.home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings = {"skillOverrides": overrides}
        if extra_env_sentinel is not None:
            settings["env"] = {"SOME_OTHER_SETTING": extra_env_sentinel}
        (claude_dir / "settings.json").write_text(json.dumps(settings))

    def write_codex_config(self, disable_names, extra_sentinel=None) -> None:
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for name in disable_names:
            lines += ["[[skills.config]]", f'name = "{name}"', "enabled = false", ""]
        if extra_sentinel is not None:
            lines.append(f"# {extra_sentinel}")
        (codex_dir / "config.toml").write_text("\n".join(lines) + "\n")

    def setup_pair(self):
        """Two fully-wired, passing skills: alpha (on/codex-enabled), beta (name-only/codex-disabled)."""
        alpha = self.make_skill("alpha-skill", claude_listing="on", codex_enabled=True)
        beta = self.make_skill("beta-skill", claude_listing="name-only", codex_enabled=False)
        manifest = self.build_manifest([alpha, beta])
        self.write_lock(self.lock_entries_for([alpha, beta]))
        self.write_claude_link("alpha-skill")
        self.write_claude_link("beta-skill")
        self.write_claude_settings({"beta-skill": "name-only"})
        self.write_codex_config(["beta-skill"])
        return manifest, alpha, beta

    def make_fake_bin(self, version_output: str, exit_code=0) -> Path:
        script = self.tmp / "fake-skills-bin"
        script.write_text(f"#!/bin/sh\necho '{version_output}'\nexit {exit_code}\n")
        script.chmod(0o755)
        return script

    # -- call helpers ---------------------------------------------------------

    def report(self, manifest, env=None, skills_bin=None) -> dict:
        return ss.inspect(manifest, self.home, env if env is not None else self.env, skills_bin=skills_bin)

    def skill_result(self, report, name: str) -> dict:
        return next(s for s in report["skills"] if s["name"] == name)

    def run_cli(self, manifest, *extra_args, env=None):
        manifest_path = self.tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        cli_env = {"PATH": os.environ.get("PATH", ""), **(env if env is not None else self.env)}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(manifest_path), "--home", str(self.home), *extra_args],
            cwd=str(ROOT), env=cli_env, capture_output=True, text=True, timeout=60)

    # -- all-pass -------------------------------------------------------------

    def test_all_pass(self):
        manifest, alpha, beta = self.setup_pair()
        report = self.report(manifest)
        self.assertEqual(report["result"], "ok")
        for skill in report["skills"]:
            self.assertTrue(skill["pass"], skill)
        self.assertEqual(report["extra_skills"], [])
        self.assertEqual(report["unlocked_folders"], [])
        self.assertEqual(report["lock"], {"source": "default", "state": "ok", "version": 3, "version_matches": True})
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("result: ok", result.stdout)

    # -- sha drift --------------------------------------------------------------

    def test_sha_drift(self):
        manifest, alpha, beta = self.setup_pair()
        self.write_canonical("alpha-skill", b"# drifted content, not what the manifest hashed\n")
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["canonical"]["state"], "sha_mismatch")
        self.assertFalse(self.skill_result(report, "alpha-skill")["pass"])
        self.assertTrue(self.skill_result(report, "beta-skill")["pass"])
        self.assertEqual(report["result"], "fail")
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha_mismatch", result.stdout)

    def test_canonical_missing_and_wrong_type(self):
        alpha = self.make_skill("alpha-skill")
        shutil.rmtree(self.home / ".agents" / "skills" / "alpha-skill")
        manifest = self.build_manifest([alpha])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["canonical"]["state"], "missing")
        (self.home / ".agents" / "skills" / "alpha-skill").mkdir(parents=True)
        (self.home / ".agents" / "skills" / "alpha-skill" / "SKILL.md").mkdir()  # a directory, not a file
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["canonical"]["state"], "not_a_file")

    # -- lock drift ---------------------------------------------------------

    def test_lock_drift(self):
        manifest, alpha, beta = self.setup_pair()
        entries = self.lock_entries_for([alpha, beta])
        entries["alpha-skill"]["skillFolderHash"] = hashlib.sha1(b"tree:not-alpha-skill").hexdigest()
        self.write_lock(entries)
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["lock"]["state"], "hash_mismatch")
        self.assertFalse(self.skill_result(report, "alpha-skill")["pass"])
        self.assertTrue(self.skill_result(report, "beta-skill")["pass"])
        self.assertEqual(report["result"], "fail")
        self.assertEqual(self.run_cli(manifest).returncode, 1)

    def test_lock_unreadable_fails_every_skill(self):
        manifest, alpha, beta = self.setup_pair()
        (self.home / ".agents" / ".skill-lock.json").write_text("{not json")
        report = self.report(manifest)
        self.assertEqual(report["lock"]["state"], "invalid")
        self.assertEqual(self.skill_result(report, "alpha-skill")["lock"]["state"], "lock_unreadable")
        self.assertEqual(report["result"], "fail")

    # -- missing link ---------------------------------------------------------

    def test_missing_link(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_settings({})
        self.write_codex_config([])
        # No ~/.claude/skills/alpha-skill created at all.
        report = self.report(manifest)
        link = self.skill_result(report, "alpha-skill")["claude_link"]
        self.assertEqual((link["state"], link["kind"]), ("missing", "missing"))
        self.assertEqual(report["result"], "fail")

    # -- absolute link reported (still passes) --------------------------------

    def test_absolute_link_reported(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="absolute")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        link = self.skill_result(report, "alpha-skill")["claude_link"]
        self.assertEqual(link, {"state": "ok", "kind": "absolute"})
        self.assertTrue(self.skill_result(report, "alpha-skill")["pass"])
        self.assertEqual(report["result"], "ok")

    def test_relative_link_reported(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="relative")
        self.write_claude_settings({})
        self.write_codex_config([])
        link = self.skill_result(self.report(manifest), "alpha-skill")["claude_link"]
        self.assertEqual(link, {"state": "ok", "kind": "relative"})

    def test_copy_kind_is_reported_and_fails(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="copy")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        link = self.skill_result(report, "alpha-skill")["claude_link"]
        self.assertEqual((link["state"], link["kind"]), ("not_a_symlink", "copy"))
        self.assertEqual(report["result"], "fail")

    def test_wrong_target_link_fails(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="wrong_target")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["claude_link"]["state"], "wrong_target")
        self.assertEqual(report["result"], "fail")

    # -- wrong override -------------------------------------------------------

    def test_wrong_override(self):
        manifest, alpha, beta = self.setup_pair()
        self.write_claude_settings({"beta-skill": "off"})  # manifest pins beta at "name-only"
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "beta-skill")["claude_listing"],
                         {"state": "mismatch", "actual": "off"})
        self.assertFalse(self.skill_result(report, "beta-skill")["pass"])
        self.assertTrue(self.skill_result(report, "alpha-skill")["pass"])
        self.assertEqual(report["result"], "fail")
        self.assertEqual(self.run_cli(manifest).returncode, 1)

    def test_missing_override_key_defaults_to_on(self):
        on_skill = self.make_skill("on-skill", claude_listing="on")
        off_skill = self.make_skill("off-skill", claude_listing="off", codex_enabled=False)
        manifest = self.build_manifest([on_skill, off_skill])
        self.write_lock(self.lock_entries_for([on_skill, off_skill]))
        self.write_claude_link("on-skill")
        self.write_claude_link("off-skill")
        self.write_claude_settings({})  # no key for either skill: Claude's own default of "on" applies
        self.write_codex_config(["off-skill"])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "on-skill")["claude_listing"], {"state": "ok", "actual": "on"})
        self.assertEqual(self.skill_result(report, "off-skill")["claude_listing"],
                         {"state": "mismatch", "actual": "on"})
        self.assertTrue(self.skill_result(report, "on-skill")["pass"])
        self.assertFalse(self.skill_result(report, "off-skill")["pass"])

    def test_missing_settings_file_defaults_to_on(self):
        on_skill = self.make_skill("on-skill", claude_listing="on")
        manifest = self.build_manifest([on_skill])
        self.write_lock(self.lock_entries_for([on_skill]))
        self.write_claude_link("on-skill")
        self.write_codex_config([])
        # ~/.claude/settings.json is never written.
        report = self.report(manifest)
        self.assertEqual(report["claude_settings"]["state"], "ok")
        self.assertTrue(self.skill_result(report, "on-skill")["pass"])

    def test_malformed_settings_fails_every_listing_check(self):
        manifest, alpha, beta = self.setup_pair()
        (self.home / ".claude" / "settings.json").write_text("{not json")
        report = self.report(manifest)
        self.assertEqual(report["claude_settings"]["state"], "invalid")
        listing = self.skill_result(report, "alpha-skill")["claude_listing"]
        self.assertEqual(listing, {"state": "settings_unreadable", "actual": None})
        self.assertEqual(report["result"], "fail")

    # -- missing codex disable -------------------------------------------------

    def test_missing_codex_disable_no_config_file(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("gated-skill")
        self.write_claude_settings({})
        # ~/.codex/config.toml is never written.
        report = self.report(manifest)
        self.assertEqual(report["codex_config"]["state"], "missing")
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"],
                         {"state": "config_missing", "disable_entry_present": False})
        self.assertEqual(report["result"], "fail")

    def test_missing_codex_disable_entry_in_present_config(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("gated-skill")
        self.write_claude_settings({})
        self.write_codex_config([])  # config.toml exists but names no skill
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"],
                         {"state": "missing_disable_entry", "disable_entry_present": False})
        self.assertEqual(report["result"], "fail")

    def test_codex_config_invalid_toml_fails_disabled_skill(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("gated-skill")
        self.write_claude_settings({})
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "config.toml").write_text("this is not [ valid toml")
        report = self.report(manifest)
        self.assertEqual(report["codex_config"]["state"], "invalid")
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"]["state"], "config_unreadable")

    def test_codex_enabled_true_rejects_unexpected_disable_entry(self):
        skill = self.make_skill("open-skill", codex_enabled=True)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("open-skill")
        self.write_claude_settings({})
        self.write_codex_config(["open-skill"])  # should not be disabled per the manifest
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "open-skill")["codex_disable"],
                         {"state": "unexpected_disable_entry", "disable_entry_present": True})
        self.assertEqual(report["result"], "fail")

    def test_codex_enabled_true_passes_with_missing_config(self):
        skill = self.make_skill("open-skill", codex_enabled=True)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("open-skill")
        self.write_claude_settings({})
        # No ~/.codex/config.toml: trivially "no such disabling table".
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "open-skill")["codex_disable"], {"state": "ok",
                                                                                    "disable_entry_present": False})
        self.assertEqual(report["result"], "ok")

    # -- XDG lock path ----------------------------------------------------------

    def test_xdg_lock_path(self):
        manifest, alpha, beta = self.setup_pair()
        xdg_state = self.tmp / "xdg-state"
        env = {**self.env, "XDG_STATE_HOME": str(xdg_state)}
        xdg_lock, source = ss.resolve_lock_path(self.home, env)
        self.assertEqual(source, "xdg_state_home")
        (self.home / ".agents" / ".skill-lock.json").unlink()  # only the XDG-selected path may hold it now
        self.write_lock(self.lock_entries_for([alpha, beta]), path=xdg_lock)
        report = self.report(manifest, env=env)
        self.assertEqual(report["lock"], {"source": "xdg_state_home", "state": "ok", "version": 3,
                                          "version_matches": True})
        self.assertEqual(report["result"], "ok")
        result = self.run_cli(manifest, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Without XDG_STATE_HOME the default path is consulted, and it is now empty.
        default_report = self.report(manifest)
        self.assertEqual(default_report["lock"]["state"], "missing")
        self.assertEqual(default_report["result"], "fail")

    # -- extra skill warning ----------------------------------------------------

    def test_extra_skill_warning(self):
        manifest, alpha, beta = self.setup_pair()
        extra = self.make_skill("extra-skill")  # a real canonical folder the manifest never mentions
        self.write_lock(self.lock_entries_for([alpha, beta, extra]))
        report = self.report(manifest)
        self.assertEqual(report["extra_skills"], [{"name": "extra-skill", "in_agents_dir": True, "in_lock": True}])
        self.assertEqual(report["unlocked_folders"], [])
        self.assertEqual(report["result"], "ok")  # a warning, not a failure
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("extra-skill", result.stdout)

    def test_extra_skill_in_lock_only(self):
        manifest, alpha, beta = self.setup_pair()
        entries = self.lock_entries_for([alpha, beta])
        entries["ghost-skill"] = {"source": "github", "sourceType": "github", "sourceUrl": "https://example.invalid",
                                  "skillPath": "skills/ghost-skill", "skillFolderHash": "0" * 40,
                                  "installedAt": "2026-09-25T00:00:00Z", "updatedAt": "2026-09-25T00:00:00Z"}
        self.write_lock(entries)  # a lock entry with no folder on disk
        report = self.report(manifest)
        self.assertEqual(report["extra_skills"], [{"name": "ghost-skill", "in_agents_dir": False, "in_lock": True}])
        self.assertEqual(report["result"], "ok")

    # -- unlocked folders ---------------------------------------------------

    def test_unlocked_folder_reported_and_fails_its_lock_check(self):
        manifest, alpha, beta = self.setup_pair()
        entries = self.lock_entries_for([alpha, beta])
        del entries["alpha-skill"]  # the folder exists (make_skill wrote it) but the lock forgot it
        self.write_lock(entries)
        report = self.report(manifest)
        self.assertIn("alpha-skill", report["unlocked_folders"])
        self.assertEqual(self.skill_result(report, "alpha-skill")["lock"]["state"], "missing_entry")
        self.assertEqual(report["result"], "fail")

    # -- --json shape -----------------------------------------------------------

    def test_json_shape(self):
        manifest, alpha, beta = self.setup_pair()
        result = self.run_cli(manifest, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {"schema_version", "lock", "claude_settings", "codex_config", "skills",
                                     "extra_skills", "unlocked_folders", "budget", "result"})
        self.assertEqual(len(data["skills"]), 2)
        for skill in data["skills"]:
            self.assertEqual(set(skill), {"name", "pass", "canonical", "lock", "claude_link",
                                          "claude_listing", "codex_disable"})
            self.assertEqual(set(skill["claude_link"]), {"state", "kind"})
        self.assertEqual(data["result"], "ok")
        # The CLI's JSON matches a direct call for the same fixture.
        self.assertEqual(self.report(manifest)["skills"], data["skills"])

    def test_json_and_text_agree_on_failure(self):
        manifest, alpha, beta = self.setup_pair()
        self.write_canonical("alpha-skill", b"drift\n")
        json_result = self.run_cli(manifest, "--json")
        text_result = self.run_cli(manifest)
        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(text_result.returncode, 1)
        self.assertEqual(json.loads(json_result.stdout)["result"], "fail")
        self.assertIn("result: fail", text_result.stdout)

    # -- manifest loading / exit 2 --------------------------------------------

    def test_invalid_manifest_json_exits_2(self):
        path = self.tmp / "broken-manifest.json"
        path.write_text("{not valid json")
        with self.assertRaises(ss.ManifestError):
            ss.load_manifest(path)
        result = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(path), "--home", str(self.home)],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid manifest", result.stderr)

    def test_manifest_missing_required_key_exits_2(self):
        manifest, alpha, beta = self.setup_pair()
        del manifest["skills"][0]["tree_sha"]
        path = self.tmp / "manifest.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ss.ManifestError):
            ss.load_manifest(path)
        result = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(path), "--home", str(self.home)],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)

    def test_manifest_missing_file_exits_2(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(self.tmp / "nope.json"), "--home", str(self.home)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)

    def test_real_manifest_loads_and_validates(self):
        real = ss.load_manifest(ROOT / "adoption" / "skills" / "manifest.json")
        names = {s["name"] for s in real["skills"]}
        self.assertIn("gh-fix-ci", names)
        self.assertGreaterEqual(len(names), 20)

    # -- value freedom --------------------------------------------------------

    def test_output_never_includes_settings_values_or_file_contents(self):
        manifest, alpha, beta = self.setup_pair()
        sentinel = "SENTINELSK" + os.urandom(12).hex()
        self.write_claude_settings({"beta-skill": "name-only"}, extra_env_sentinel=sentinel)
        self.write_codex_config(["beta-skill"], extra_sentinel=sentinel)
        self.write_canonical("alpha-skill", f"# drifted body carrying {sentinel}\n".encode())
        report = self.report(manifest)
        self.assertEqual(report["result"], "fail")
        dumped = json.dumps(report) + ss.render_text(report)
        self.assertNotIn(sentinel, dumped)
        self.assertNotIn("drifted body", dumped)
        for args in ((), ("--json",)):
            with self.subTest(args=args):
                result = self.run_cli(manifest, *args)
                self.assertNotIn(sentinel, result.stdout)
                self.assertNotIn(sentinel, result.stderr)
                self.assertNotIn("drifted body", result.stdout)

    def test_home_path_not_echoed_in_output(self):
        manifest, alpha, beta = self.setup_pair()
        result = self.run_cli(manifest)
        self.assertNotIn(str(self.home), result.stdout)
        self.assertNotIn(str(self.home), result.stderr)

    # -- --skills-bin / cli_version --------------------------------------------

    def test_cli_version_matches(self):
        manifest, alpha, beta = self.setup_pair()  # cli.version defaults to "1.7.0"
        binary = self.make_fake_bin("1.7.0")
        report = self.report(manifest, skills_bin=str(binary))
        self.assertEqual(report["cli_version"], {"invoked": True, "exit_code": 0, "output": "1.7.0",
                                                  "matches_manifest": True})
        self.assertEqual(report["result"], "ok")

    def test_cli_version_mismatch_fails_even_if_skills_pass(self):
        manifest, alpha, beta = self.setup_pair()
        binary = self.make_fake_bin("9.9.9")
        report = self.report(manifest, skills_bin=str(binary))
        self.assertFalse(report["cli_version"]["matches_manifest"])
        self.assertEqual(report["result"], "fail")
        result = self.run_cli(manifest, "--skills-bin", str(binary))
        self.assertEqual(result.returncode, 1)

    def test_cli_version_binary_not_found(self):
        manifest, alpha, beta = self.setup_pair()
        report = self.report(manifest, skills_bin=str(self.tmp / "does-not-exist"))
        self.assertEqual(report["cli_version"], {"invoked": False, "exit_code": None, "output": None,
                                                  "matches_manifest": False})
        self.assertEqual(report["result"], "fail")

    def test_skills_bin_omitted_leaves_cli_version_out_of_report(self):
        manifest, alpha, beta = self.setup_pair()
        report = self.report(manifest)
        self.assertNotIn("cli_version", report)

    # -- budget -----------------------------------------------------------------

    def test_budget_matches_and_reports_drift_without_failing(self):
        on1 = self.make_skill("on1", claude_listing="on", description_chars=300)
        on2 = self.make_skill("on2", claude_listing="on", description_chars=200)
        off1 = self.make_skill("off1", claude_listing="off", codex_enabled=False, description_chars=50)
        manifest = self.build_manifest(
            [on1, on2, off1],
            budget={"claude_on_description_chars": 500, "claude_on_cap": 8000,
                   "codex_enabled_description_chars": 500, "codex_default_budget_chars": 8000})
        self.write_lock(self.lock_entries_for([on1, on2, off1]))
        for skill in (on1, on2, off1):
            self.write_claude_link(skill["name"])
        self.write_claude_settings({"off1": "off"})
        self.write_codex_config(["off1"])
        report = self.report(manifest)
        budget = report["budget"]
        self.assertEqual(budget["claude_on_description_chars"],
                         {"manifest": 500, "computed": 500, "matches_manifest": True})
        self.assertTrue(budget["claude_within_cap"])
        self.assertEqual(report["result"], "ok")

        manifest["budget"]["claude_on_description_chars"] = 999  # drift the recorded sum only
        drifted = self.report(manifest)
        self.assertFalse(drifted["budget"]["claude_on_description_chars"]["matches_manifest"])
        self.assertEqual(drifted["result"], "ok")  # still informational only

    def test_budget_over_cap_is_reported_but_not_a_failure(self):
        big = self.make_skill("big-on", claude_listing="on", description_chars=9000)
        manifest = self.build_manifest([big], budget={"claude_on_description_chars": 9000, "claude_on_cap": 8000,
                                                       "codex_enabled_description_chars": 9000,
                                                       "codex_default_budget_chars": 8000})
        self.write_lock(self.lock_entries_for([big]))
        self.write_claude_link("big-on")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        self.assertFalse(report["budget"]["claude_within_cap"])
        self.assertFalse(report["budget"]["codex_within_cap"])
        self.assertEqual(report["result"], "ok")


if __name__ == "__main__":
    unittest.main()
