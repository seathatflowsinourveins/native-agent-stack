"""Tests for tools/adoption/install_skills.py against a fake 'skills' CLI.

The fake executable (write_fake_skills_bin) is a small stdlib-only Python
script written into its own temp directory per test. It emulates just enough
of the real `skills` CLI (v1.7.0) to exercise install_skills.py end to end:

  --version         prints the pinned version.
  add <url> --skill <name> -g -y -a claude-code codex
                    writes home/.agents/skills/<name>/SKILL.md and a relative
                    home/.claude/skills/<name> symlink from a per-test fixture
                    map keyed by skill name, then records a matching lock
                    entry (skillFolderHash = the fixture's tree_sha) at
                    home/.agents/.skill-lock.json or, when $XDG_STATE_HOME is
                    set, $XDG_STATE_HOME/skills/.skill-lock.json -- the same
                    rule install_skills.py itself applies when reading it
                    back, so a test that sets $XDG_STATE_HOME exercises both
                    sides of that contract at once.
  remove <name> -g -y -a claude-code codex
                    deletes the canonical folder, the symlink and the lock
                    entry.

Every invocation is also appended to calls.log next to the fake script
(independent of --home), so tests can assert not just the outcome but
whether, how often and with what arguments install_skills.py actually
invoked the binary -- in particular that an idempotent skip and a refused
local-modified skill never invoke it at all.

install_skills.py is run as a real subprocess (like tests/test_render_config.py's
`run()` helper) rather than imported, since the behavior under test is what it
does across process boundaries with a real (fake) CLI. $XDG_STATE_HOME is
stripped from the child environment by default so a variable already set on
the host running these tests can never redirect a lock-file write outside the
test's own temporary directory; only the dedicated XDG test re-adds it,
pointed at a second temporary directory.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "adoption" / "install_skills.py"

PINNED_VERSION = "1.7.0"
INSTALL_HINT = "npm install --global --prefix <tools-root>/skills-1.7.0 skills@1.7.0"

FAKE_SKILLS_BIN_TEMPLATE = r'''#!/usr/bin/env python3
import json, os, sys, shutil, hashlib
from pathlib import Path

VERSION = "__VERSION__"
FIXTURES = __FIXTURES_JSON__

LOG = Path(__file__).resolve().parent / "calls.log"
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")


def lock_path(home: Path) -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "skills" / ".skill-lock.json"
    return home / ".agents" / ".skill-lock.json"


def load_lock(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"lockfileVersion": 3, "skills": {}}


argv = sys.argv[1:]
if not argv:
    sys.exit(2)

if argv[0] == "--version":
    print(f"skills/{VERSION}")
    sys.exit(0)

home = Path(os.environ["HOME"])
project = "-g" not in argv
target = Path.cwd() if project else home

if argv[0] == "add":
    url = argv[1]
    name = argv[argv.index("--skill") + 1]
    if name not in FIXTURES:
        print(f"fake skills add: no fixture for {name!r}", file=sys.stderr)
        sys.exit(1)
    fixture = FIXTURES[name]
    skill_dir = target / ".agents" / "skills" / name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(fixture["skill_md"], encoding="utf-8")
    if not project or "claude-code" in argv:
        link_dir = target / ".claude" / "skills"
        link_dir.mkdir(parents=True, exist_ok=True)
        link = link_dir / name
        # skills@7407f389 installer.ts:254-264 removes an existing directory
        # before creating the alias. The wrapper must protect local content.
        if link.is_symlink():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        elif link.exists():
            link.unlink()
        os.symlink(os.path.join("..", "..", ".agents", "skills", name), link)
    path = target / "skills-lock.json" if project else lock_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = load_lock(path)
    lock.setdefault("skills", {})[name] = {
        "source": "github", "sourceType": "github", "sourceUrl": url,
        "skillPath": fixture.get("path", name), "skillFolderHash": fixture["tree_sha"],
        "installedAt": "2026-09-25T00:00:00Z", "updatedAt": "2026-09-25T00:00:00Z",
    }
    if project:
        # Native v1.7.0 local-lock.ts:15-37: no skillFolderHash here.
        lock = {"version": 1, "skills": lock["skills"]}
        lock["skills"][name] = {
            "source": fixture.get("source", f"example/{name}"), "sourceType": "github",
            "ref": fixture.get("ref", "a" * 40),
            "skillPath": fixture.get("path", f"skills/{name}") + "/SKILL.md",
            "computedHash": hashlib.sha256(b"SKILL.md" + fixture["skill_md"].encode()).hexdigest(),
        }
    path.write_text(json.dumps(lock))
    sys.exit(0)

if argv[0] == "remove":
    name = argv[1]
    # Synthetic fault injection for independently checking cleanup artifacts.
    retained = FIXTURES.get(name, {}).get("retain_after_remove", [])
    if project:
        # Relevant subset of skills@7407f389 remove.ts:209-333. A same-named
        # OpenClaw source directory is a removal target even if not detected.
        agent_dirs = {"universal": ".agents/skills", "codex": ".agents/skills",
                      "claude-code": ".claude/skills", "cursor": ".cursor/skills",
                      "openclaw": "skills"}
        targets = argv[argv.index("-a") + 1:] if "-a" in argv else list(agent_dirs)
        canonical = target / ".agents" / "skills" / name
        for agent in targets:
            path = target / agent_dirs[agent] / name
            if path == canonical:
                continue
            if agent == "claude-code" and "claude-link" in retained:
                continue
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        # Fixture detection is deliberately limited to a Codex home marker.
        # remove.ts:293-310 retains canonical data and lock for another agent.
        if "codex" not in targets and (home / ".codex").exists() and canonical.exists():
            sys.exit(0)
    if "canonical" not in retained:
        shutil.rmtree(target / ".agents" / "skills" / name, ignore_errors=True)
    link = target / ".claude" / "skills" / name
    if not project and (link.is_symlink() or link.exists()):
        link.unlink()
    path = target / "skills-lock.json" if project else lock_path(home)
    lock = load_lock(path)
    if "lock" not in retained:
        lock.get("skills", {}).pop(name, None)
    path.write_text(json.dumps(lock))
    sys.exit(0)

print(f"fake skills: unknown subcommand {argv[0]!r}", file=sys.stderr)
sys.exit(2)
'''


def write_fake_skills_bin(directory: Path, fixtures: dict, version: str = PINNED_VERSION) -> Path:
    text = FAKE_SKILLS_BIN_TEMPLATE.replace("__VERSION__", version).replace(
        "__FIXTURES_JSON__", json.dumps(fixtures))
    path = directory / "skills"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def calls_log(fake_bin: Path) -> list[list[str]]:
    log = fake_bin.parent / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_skill(name: str, skill_md: str, tree_sha: str, codex_enabled: bool = True) -> dict:
    return {
        "name": name,
        "source": f"example/{name}",
        "url": f"https://github.com/example/{name}/tree/{'a' * 40}/skills/{name}",
        "ref": "a" * 40,
        "path": f"skills/{name}",
        "tree_sha": tree_sha,
        "skill_md_sha256": sha256_text(skill_md),
        "skill_md_bytes": len(skill_md.encode("utf-8")),
        "description_chars": 10,
        "upstream_disable_model_invocation": False,
        "license": "MIT",
        "official": False,
        "audits": {"gen_agent_trust_hub": "Pass", "socket": "Pass", "snyk": "Pass",
                   "url": f"https://skills.sh/example/{name}", "checked_at": "2026-09-25"},
        "status": "trial",
        "gap": "test fixture",
        "claude_listing": "on",
        "codex_enabled": codex_enabled,
    }


def make_manifest(skills: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "kind": "skills_trial_manifest",
        "checked_at": "2026-09-25",
        "cli": {
            "package": "skills",
            "version": PINNED_VERSION,
            "source": "https://github.com/vercel-labs/skills/tree/v1.7.0",
            "install": INSTALL_HINT,
            "env": {"DISABLE_TELEMETRY": "1"},
            "lock_path": "$XDG_STATE_HOME/skills/.skill-lock.json when XDG_STATE_HOME is set, "
                         "else ~/.agents/.skill-lock.json",
        },
        "skills": skills,
    }


def tree_sha(label: str) -> str:
    """A deterministic 40-hex string distinct per label; not a real git tree SHA."""
    return hashlib.sha1(label.encode("utf-8")).hexdigest()


class InstallSkillsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.home = self.tmp_path / "home"
        self.home.mkdir()
        self.bin_dir = self.tmp_path / "bin"
        self.bin_dir.mkdir()

    def write_manifest(self, skills: list[dict]) -> Path:
        path = self.tmp_path / "manifest.json"
        path.write_text(json.dumps(make_manifest(skills)))
        return path

    def run_install(self, manifest: Path, *extra: str, env: dict | None = None,
                    fake_bin: Path | None = None) -> subprocess.CompletedProcess:
        full_env = dict(os.environ)
        full_env.pop("XDG_STATE_HOME", None)  # never let the host redirect the lock write
        full_env.update(env or {})
        args = [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--home", str(self.home)]
        if fake_bin is not None:
            args += ["--skills-bin", str(fake_bin)]
        args += list(extra)
        return subprocess.run(args, capture_output=True, text=True, check=False, env=full_env, timeout=60)

    def lock_data(self, xdg_state_home: Path | None = None) -> dict:
        path = (Path(xdg_state_home) / "skills" / ".skill-lock.json") if xdg_state_home \
            else (self.home / ".agents" / ".skill-lock.json")
        return json.loads(path.read_text()) if path.is_file() else {}


class DryRunTests(InstallSkillsTestCase):
    def test_dry_run_changes_nothing_and_exits_zero(self):
        skill = make_skill("fresh-skill", "# Fresh\n", tree_sha("fresh"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {"fresh-skill": {"skill_md": "# Fresh\n",
                                                                        "tree_sha": tree_sha("fresh")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--dry-run", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("would run", result.stdout)
        self.assertFalse((self.home / ".agents").exists())
        self.assertFalse((self.home / ".claude").exists())
        self.assertEqual(calls_log(fake_bin), [["--version"]])  # only the version check ran


class ProjectInstallTests(InstallSkillsTestCase):
    """CLI seam: project cwd/lock, source-tree verification and scoped rollback.

    Fake gh returns independently selected source-tree metadata. These are
    integration fixtures, not a native CLI run or upstream acceptance.
    """

    def setUp(self):
        super().setUp()
        self.project = self.tmp_path / "project with spaces"
        self.project.mkdir()
        self.content = "# Project skill\n"
        self.skill = make_skill("project-skill", self.content, tree_sha("project"))
        self.manifest = self.write_manifest([self.skill])
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {
            "project-skill": {"skill_md": self.content, "tree_sha": self.skill["tree_sha"]}})
        self.write_gh_tree(self.skill["tree_sha"])

    def write_gh_tree(self, sha):
        data = {"truncated": False, "tree": [{"path": self.skill["path"], "type": "tree", "sha": sha}]}
        endpoint = f"repos/{self.skill['source']}/git/trees/{self.skill['ref']}?recursive=1"
        self.write_gh_responses({endpoint: (0, json.dumps(data))})

    def write_gh_responses(self, responses):
        gh = self.bin_dir / "gh"
        gh.write_text("""#!/usr/bin/env python3
import json, sys
from pathlib import Path
responses = """ + repr(responses) + """
directory = Path(__file__).resolve().parent
calls = directory / "calls.log"
mutations = [json.loads(line) for line in calls.read_text().splitlines()
             if json.loads(line)[0] in ("add", "remove")] if calls.exists() else []
with (directory / "gh_calls.log").open("a") as log:
    log.write(json.dumps({"args": sys.argv[1:], "mutations": mutations}) + "\\n")
code, response = responses[sys.argv[2]]
print(response)
sys.exit(code)
""")
        gh.chmod(0o755)

    def install(self, *extra):
        return self.run_install(
            self.manifest, "--project-dir", str(self.project), "--agent", "universal", *extra,
            fake_bin=self.fake_bin,
            env={"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]})

    def test_project_install_uses_project_cwd_local_lock_and_explicit_agent(self):
        result = self.install("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "installed"})
        self.assertEqual((self.project / ".agents/skills/project-skill/SKILL.md").read_text(), self.content)
        self.assertFalse((self.home / ".agents").exists())
        lock = json.loads((self.project / "skills-lock.json").read_text())
        self.assertNotIn("skillFolderHash", lock["skills"]["project-skill"])
        self.assertEqual(calls_log(self.fake_bin)[1], [
            "add", self.skill["url"], "--skill", "project-skill", "-y", "-a", "universal"])
        again = self.install("--json")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads(again.stdout)["skills"], {"project-skill": "ok"})
        self.assertEqual([c[0] for c in calls_log(self.fake_bin)], ["--version", "add", "--version"])

    def test_check_only_reports_missing_without_installing(self):
        result = self.install("--check-only", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "missing-or-drifted"})
        self.assertEqual(calls_log(self.fake_bin), [["--version"]])
        self.assertFalse((self.project / "skills-lock.json").exists())

    def test_project_preflight_failure_on_later_source_changes_nothing(self):
        projects = self.project
        for same_source in (False, True):
            for failure in ("unavailable", "invalid-json", "truncated"):
                with self.subTest(same_source=same_source, failure=failure):
                    self.project = projects / f"{same_source}-{failure}"
                    self.project.mkdir()
                    second = make_skill("second-skill", "# Second\n", tree_sha("second"))
                    if same_source:
                        second["source"] = self.skill["source"]
                        second["ref"] = "b" * 40
                        second["url"] = f"https://github.com/{second['source']}/tree/{second['ref']}/{second['path']}"
                    self.manifest = self.write_manifest([self.skill, second])
                    self.fake_bin = write_fake_skills_bin(self.bin_dir, {
                        s["name"]: {"skill_md": content, "tree_sha": s["tree_sha"],
                                    "source": s["source"], "ref": s["ref"], "path": s["path"]}
                        for s, content in ((self.skill, self.content), (second, "# Second\n"))})
                    failed_response = {"unavailable": (1, "fixture API failure"),
                                       "invalid-json": (0, "not JSON"),
                                       "truncated": (0, json.dumps({"truncated": True, "tree": []}))}[failure]
                    self.write_gh_responses({
                        f"repos/{self.skill['source']}/git/trees/{self.skill['ref']}?recursive=1":
                            (0, json.dumps({"tree": [{"path": self.skill["path"], "type": "tree", "sha": self.skill["tree_sha"]}]})),
                        f"repos/{second['source']}/git/trees/{second['ref']}?recursive=1": failed_response})
                    before = calls_log(self.fake_bin)
                    result = self.install()
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("unverified (gh unavailable)" if failure == "unavailable" else "unverified", result.stderr)
                    self.assertNotIn("did not match", result.stderr)
                    self.assertNotIn("rolled back", result.stderr)
                    self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]])
                    self.assertEqual(list(self.project.iterdir()), [])

    def test_project_fetches_each_selected_source_ref_before_any_add(self):
        second = make_skill("second-skill", "# Second\n", tree_sha("second"))
        second["source"] = self.skill["source"]
        second["url"] = f"https://github.com/{second['source']}/tree/{second['ref']}/{second['path']}"
        third = make_skill("third-skill", "# Third\n", tree_sha("third"))
        self.manifest = self.write_manifest([self.skill, second, third])
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {
            s["name"]: {"skill_md": content, "tree_sha": s["tree_sha"],
                        "source": s["source"], "ref": s["ref"], "path": s["path"]}
            for s, content in ((self.skill, self.content), (second, "# Second\n"), (third, "# Third\n"))})
        responses = {}
        for group in ((self.skill, second), (third,)):
            skill = group[0]
            responses[f"repos/{skill['source']}/git/trees/{skill['ref']}?recursive=1"] = (
                0, json.dumps({"tree": [{"path": s["path"], "type": "tree", "sha": s["tree_sha"]} for s in group]}))
        self.write_gh_responses(responses)
        result = self.install("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        gh_calls = [json.loads(line) for line in (self.bin_dir / "gh_calls.log").read_text().splitlines()]
        self.assertEqual([c["args"] for c in gh_calls], [["api", endpoint] for endpoint in responses])
        self.assertTrue(all(not call["mutations"] for call in gh_calls), gh_calls)
        self.assertEqual(json.loads(result.stdout)["skills"],
                         {"project-skill": "installed", "second-skill": "installed", "third-skill": "installed"})

    def test_project_tree_mismatch_rolls_back_only_in_project(self):
        self.write_gh_tree(tree_sha("other"))
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[-1], ["remove", "project-skill", "-y", "-a", "universal"])
        self.assertFalse((self.project / ".agents/skills/project-skill").exists())
        self.assertFalse((self.home / ".agents").exists())

    def test_project_rollback_preserves_other_agents_and_source_directories(self):
        for agent, targets in (("universal", ["universal"]),
                               ("codex", ["universal", "codex"]),
                               ("claude-code", ["universal", "claude-code"])):
            with self.subTest(agent=agent):
                sentinels = []
                for directory in ("skills", ".cursor/skills"):
                    sentinel = self.project / directory / "project-skill" / "LOCAL.md"
                    sentinel.parent.mkdir(parents=True, exist_ok=True)
                    sentinel.write_text("owned before this run\n")
                    sentinels.append(sentinel)
                self.write_gh_tree(tree_sha("other"))
                result = self.install("--agent", agent)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("rolled back", result.stderr)
                calls = calls_log(self.fake_bin)
                self.assertEqual(calls[-1], ["remove", "project-skill", "-y", "-a", *targets])
                self.assertEqual(calls[-2][calls[-2].index("-a"):], calls[-1][calls[-1].index("-a"):])
                for sentinel in sentinels:
                    self.assertEqual(sentinel.read_text(), "owned before this run\n")
                self.assertFalse((self.project / ".agents/skills/project-skill").exists())
                link = self.project / ".claude/skills/project-skill"
                self.assertFalse(link.exists() or link.is_symlink())
                self.assertNotIn("project-skill", json.loads((self.project / "skills-lock.json").read_text())["skills"])

    def test_project_rollback_reports_canonical_retained_for_another_agent(self):
        (self.home / ".codex").mkdir()
        self.write_gh_tree(tree_sha("other"))
        result = self.install("--agent", "claude-code", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "error"})
        self.assertIn("rollback retained, in use by another agent", result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[-1],
                         ["remove", "project-skill", "-y", "-a", "universal", "claude-code"])
        self.assertTrue((self.project / ".agents/skills/project-skill").is_dir())
        self.assertIn("project-skill", json.loads((self.project / "skills-lock.json").read_text())["skills"])
        link = self.project / ".claude/skills/project-skill"
        self.assertFalse(link.exists() or link.is_symlink())
        self.assertEqual([call[0] for call in calls_log(self.fake_bin)], ["--version", "add", "remove"])

    def test_project_rollback_checks_each_artifact_independently(self):
        self.write_gh_tree(tree_sha("other"))
        for artifact in ("canonical", "lock", "claude-link"):
            with self.subTest(artifact=artifact):
                self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
                    "skill_md": self.content, "tree_sha": self.skill["tree_sha"],
                    "retain_after_remove": [artifact]}})
                result = self.install("--agent", "claude-code", "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "error"})
                self.assertNotIn("rolled back", result.stderr)
                canonical = self.project / ".agents/skills/project-skill"
                link = self.project / ".claude/skills/project-skill"
                lock = json.loads((self.project / "skills-lock.json").read_text())["skills"]
                self.assertEqual(canonical.exists(), artifact == "canonical")
                self.assertEqual("project-skill" in lock, artifact == "lock")
                self.assertEqual(link.is_symlink(), artifact == "claude-link")
                if artifact == "claude-link":
                    self.assertFalse(link.exists(), "dangling Claude link must still count as retained")

    def test_wrong_source_ref_or_path_is_not_accepted_even_when_bytes_match(self):
        for field, value in (("source", "other/repo"), ("ref", "b" * 40), ("path", "elsewhere/skill")):
            with self.subTest(field=field):
                self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
                    "skill_md": self.content, "tree_sha": self.skill["tree_sha"], field: value}})
                result = self.install()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("rolled back", result.stderr)

    def test_project_byte_mismatch_rolls_back(self):
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
            "skill_md": "# Wrong content\n", "tree_sha": self.skill["tree_sha"]}})
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)

    def test_project_dry_run_and_unlocked_local_refusal_are_nonmutating(self):
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.project / ".agents").exists())
        folder = self.project / ".agents/skills/project-skill"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("local content")
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("local-modified", result.stderr)
        self.assertEqual((folder / "SKILL.md").read_text(), "local content")
        self.assertEqual(calls_log(self.fake_bin), [["--version"], ["--version"]])

    def test_explicit_project_claude_target_keeps_canonical_directory(self):
        result = self.install("--agent", "claude-code")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[1][-3:], ["-a", "universal", "claude-code"])
        again = self.install("--agent", "claude-code", "--json")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads(again.stdout)["skills"], {"project-skill": "ok"})
        self.assertEqual([c[0] for c in calls_log(self.fake_bin)], ["--version", "add", "--version"])

    def test_project_claude_directory_is_protected_with_or_without_lock(self):
        projects = self.project
        for locked in (False, True):
            for content_kind in ("local", "matching", "missing"):
                with self.subTest(locked=locked, content=content_kind):
                    self.project = projects / f"locked-{locked}-{content_kind}"
                    self.project.mkdir()
                    if locked:
                        first = self.install()
                        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                    local = self.project / ".claude/skills/project-skill"
                    local.mkdir(parents=True)
                    (local / "LOCAL.md").write_text("hand-written support file\n")
                    if content_kind != "missing":
                        (local / "SKILL.md").write_text(self.content if content_kind == "matching" else "local edits\n")
                    before = calls_log(self.fake_bin)
                    for mode in ((), ("--dry-run",), ("--check-only",)):
                        result = self.install("--agent", "claude-code", "--json", *mode)
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "local-modified"})
                        self.assertFalse(local.is_symlink())
                        self.assertEqual((local / "LOCAL.md").read_text(), "hand-written support file\n")
                    self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]] * 3)
                    forced = self.install("--agent", "claude-code", "--force", "--json")
                    self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
                    self.assertEqual(json.loads(forced.stdout)["skills"], {"project-skill": "installed"})
                    self.assertTrue(local.is_symlink())
                    self.assertEqual(local.resolve(), (self.project / ".agents/skills/project-skill").resolve())
                    self.assertEqual((local / "SKILL.md").read_text(), self.content)

    def test_project_claude_foreign_symlink_requires_force(self):
        projects = self.project
        for locked in (False, True):
            with self.subTest(locked=locked):
                self.project = projects / f"locked-{locked}"
                self.project.mkdir()
                if locked:
                    self.assertEqual(self.install().returncode, 0)
                local = self.project / ".claude/skills/project-skill"
                local.parent.mkdir(parents=True)
                foreign = self.project / "hand-written-skill"
                local.symlink_to(foreign)  # dangling foreign link still belongs to the user
                before = calls_log(self.fake_bin)
                result = self.install("--agent", "claude-code", "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "local-modified"})
                self.assertEqual(local.readlink(), foreign)
                self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]])
                forced = self.install("--agent", "claude-code", "--force")
                self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
                self.assertEqual(local.resolve(), (self.project / ".agents/skills/project-skill").resolve())

    def test_adding_claude_target_to_existing_universal_install_creates_its_link(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        link = self.project / ".claude/skills/project-skill"
        self.assertFalse(link.exists())
        check = self.install("--agent", "claude-code", "--check-only")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        second = self.install("--agent", "claude-code")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertTrue(link.is_symlink())

    def test_pruned_skills_are_not_reinstalled(self):
        self.skill["status"] = "pruned"
        self.manifest = self.write_manifest([self.skill])
        result = self.install("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {})
        self.assertEqual(calls_log(self.fake_bin), [["--version"]])

    def test_relative_binary_is_resolved_before_changing_to_project_directory(self):
        result = self.run_install(
            self.manifest, "--project-dir", str(self.project), "--agent", "universal",
            fake_bin=Path(os.path.relpath(self.fake_bin, Path.cwd())),
            env={"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.project / ".agents/skills/project-skill/SKILL.md").is_file())

    def test_global_default_add_arguments_remain_exact(self):
        result = self.run_install(self.manifest, fake_bin=self.fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[1], ["add", self.skill["url"], "--skill", "project-skill",
                                                       "-g", "-y", "-a", "claude-code", "codex"])

    def test_help_describes_project_authentication_and_scoped_global_rollback(self):
        result = self.install("--help")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        help_text = " ".join(result.stdout.split())
        self.assertIn("gh uses its own configured authentication", help_text)
        self.assertIn("script itself never reads, prints or passes a token", help_text)
        self.assertNotIn("never reads a credential store", help_text)
        self.assertIn("skills remove <name> -g -y -a claude-code codex", help_text)


class IdempotentSkipTests(InstallSkillsTestCase):
    def test_matching_folder_and_lock_is_skipped_without_invoking_the_binary(self):
        content = "# Already installed\n"
        skill = make_skill("steady-skill", content, tree_sha("steady"))
        skill_dir = self.home / ".agents" / "skills" / "steady-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        lock_dir = self.home / ".agents"
        lock_dir.mkdir(exist_ok=True)
        (lock_dir / ".skill-lock.json").write_text(json.dumps(
            {"lockfileVersion": 3, "skills": {"steady-skill": {"skillFolderHash": tree_sha("steady")}}}))
        fake_bin = write_fake_skills_bin(self.bin_dir, {})  # no fixtures needed: add must never run
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertEqual(calls_log(fake_bin), [["--version"]])


class AddAndVerifyTests(InstallSkillsTestCase):
    def test_fresh_install_is_verified_and_reported_installed(self):
        content = "# New skill\n"
        skill = make_skill("new-skill", content, tree_sha("new"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"new-skill": {"skill_md": content, "tree_sha": tree_sha("new")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("installed", result.stdout)
        calls = calls_log(fake_bin)
        self.assertEqual([c[0] for c in calls], ["--version", "add"])
        skill_md = self.home / ".agents" / "skills" / "new-skill" / "SKILL.md"
        self.assertEqual(skill_md.read_text(), content)
        link = self.home / ".claude" / "skills" / "new-skill"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), os.path.join("..", "..", ".agents", "skills", "new-skill"))
        self.assertEqual(self.lock_data()["skills"]["new-skill"]["skillFolderHash"], tree_sha("new"))

    def test_second_run_of_a_fresh_install_is_then_an_idempotent_skip(self):
        content = "# New skill\n"
        skill = make_skill("new-skill", content, tree_sha("new"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"new-skill": {"skill_md": content, "tree_sha": tree_sha("new")}})
        manifest = self.write_manifest([skill])
        first = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("ok", second.stdout)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add", "--version"])


class MismatchRollbackTests(InstallSkillsTestCase):
    def test_tree_sha_mismatch_after_add_rolls_back_and_exits_one(self):
        content = "# Drifted skill\n"
        # The manifest pins one tree; the (fake) upstream installs matching bytes but records a
        # different skillFolderHash, as if the tag had moved or the CLI resolved the wrong tree.
        skill = make_skill("drift-skill", content, tree_sha("pinned"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"drift-skill": {"skill_md": content, "tree_sha": tree_sha("actually-installed")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)
        calls = calls_log(fake_bin)
        self.assertEqual([c[0] for c in calls], ["--version", "add", "remove"])
        # The rollback is scoped to exactly the agents the install wrote for, never to every agent (#405).
        self.assertEqual(calls[2], ["remove", "drift-skill", "-g", "-y", "-a", "claude-code", "codex"])
        self.assertEqual(calls[1][calls[1].index("-a"):], calls[2][calls[2].index("-a"):])
        # The fake remove handler actually deleted what add wrote.
        self.assertFalse((self.home / ".agents" / "skills" / "drift-skill").exists())
        self.assertFalse((self.home / ".claude" / "skills" / "drift-skill").exists())
        self.assertNotIn("drift-skill", self.lock_data().get("skills", {}))

    def test_skill_md_bytes_mismatch_after_add_also_rolls_back(self):
        skill = make_skill("bytes-skill", "# Expected\n", tree_sha("bytes"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"bytes-skill": {"skill_md": "# Something else entirely\n",
                                            "tree_sha": tree_sha("bytes")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add", "remove"])


class LocalModifiedTests(InstallSkillsTestCase):
    def setUp(self):
        super().setUp()
        self.pinned_content = "# Pinned upstream content\n"
        self.skill = make_skill("hand-installed", self.pinned_content, tree_sha("hand"))
        skill_dir = self.home / ".agents" / "skills" / "hand-installed"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# A locally hand-edited copy\n", encoding="utf-8")
        # No lock entry at all: exactly the "installed by hand before the manifest existed" case.

    def test_unlocked_local_modification_is_refused_without_force(self):
        fake_bin = write_fake_skills_bin(self.bin_dir, {})  # must never be asked to add/remove
        manifest = self.write_manifest([self.skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("local-modified", result.stderr)
        self.assertEqual(calls_log(fake_bin), [["--version"]])
        # The local copy is untouched.
        self.assertEqual((self.home / ".agents" / "skills" / "hand-installed" / "SKILL.md").read_text(),
                         "# A locally hand-edited copy\n")

    def test_unlocked_folder_without_skill_md_is_refused_as_local_modified(self):
        # A canonical folder that exists but has no SKILL.md at all (e.g. an
        # unrelated file dropped there by hand, or a partial install) must still
        # be refused as (b), not fall through to "install": `skills add` recreates
        # its target directory from scratch, so treating this like a fresh (c)
        # install would silently discard whatever is actually in the folder.
        skill = make_skill("no-skill-md", "# Would-be pinned content\n", tree_sha("no-skill-md"))
        skill_dir = self.home / ".agents" / "skills" / "no-skill-md"
        skill_dir.mkdir(parents=True)
        (skill_dir / "OTHER_FILE.md").write_text("unrelated local content\n", encoding="utf-8")
        fake_bin = write_fake_skills_bin(self.bin_dir, {})  # must never be asked to add/remove
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("local-modified", result.stderr)
        self.assertEqual(calls_log(fake_bin), [["--version"]])
        # The unrelated local file survives untouched, and no SKILL.md was fabricated.
        self.assertEqual((skill_dir / "OTHER_FILE.md").read_text(), "unrelated local content\n")
        self.assertFalse((skill_dir / "SKILL.md").exists())

    def test_an_unlocked_but_byte_identical_copy_is_not_local_modified(self):
        # Same setup, but the on-disk SKILL.md already matches the manifest exactly: (b) says this
        # is safe to bring under lock management, not a local edit to protect.
        skill_dir = self.home / ".agents" / "skills" / "hand-installed"
        (skill_dir / "SKILL.md").write_text(self.pinned_content, encoding="utf-8")
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"hand-installed": {"skill_md": self.pinned_content, "tree_sha": tree_sha("hand")}})
        manifest = self.write_manifest([self.skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add"])

    def test_force_overwrites_a_genuine_local_modification(self):
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"hand-installed": {"skill_md": self.pinned_content, "tree_sha": tree_sha("hand")}})
        manifest = self.write_manifest([self.skill])
        result = self.run_install(manifest, "--force", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("installed", result.stdout)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add"])
        self.assertEqual((self.home / ".agents" / "skills" / "hand-installed" / "SKILL.md").read_text(),
                         self.pinned_content)


class XdgStateHomeLockPathTests(InstallSkillsTestCase):
    def test_lock_is_read_and_written_under_xdg_state_home_when_set(self):
        xdg = self.tmp_path / "xdg-state"
        xdg.mkdir()
        content = "# XDG-pathed skill\n"
        skill = make_skill("xdg-skill", content, tree_sha("xdg"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"xdg-skill": {"skill_md": content, "tree_sha": tree_sha("xdg")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, env={"XDG_STATE_HOME": str(xdg)}, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("installed", result.stdout)
        xdg_lock = xdg / "skills" / ".skill-lock.json"
        self.assertTrue(xdg_lock.is_file())
        self.assertEqual(json.loads(xdg_lock.read_text())["skills"]["xdg-skill"]["skillFolderHash"],
                         tree_sha("xdg"))
        self.assertFalse((self.home / ".agents" / ".skill-lock.json").exists())

    def test_second_run_under_the_same_xdg_state_home_is_an_idempotent_skip(self):
        xdg = self.tmp_path / "xdg-state"
        xdg.mkdir()
        content = "# XDG-pathed skill\n"
        skill = make_skill("xdg-skill", content, tree_sha("xdg"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"xdg-skill": {"skill_md": content, "tree_sha": tree_sha("xdg")}})
        manifest = self.write_manifest([skill])
        first = self.run_install(manifest, env={"XDG_STATE_HOME": str(xdg)}, fake_bin=fake_bin)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_install(manifest, env={"XDG_STATE_HOME": str(xdg)}, fake_bin=fake_bin)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("ok", second.stdout)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add", "--version"])


class PrintCodexConfigTests(InstallSkillsTestCase):
    def test_prints_only_codex_disabled_skills_and_never_touches_the_binary(self):
        on_skill = make_skill("codex-on", "# on\n", tree_sha("on"), codex_enabled=True)
        off_skill = make_skill("codex-off", "# off\n", tree_sha("off"), codex_enabled=False)
        manifest = self.write_manifest([on_skill, off_skill])
        result = self.run_install(manifest, "--print-codex-config",
                                  fake_bin=Path("/nonexistent/skills-binary"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[[skills.config]]', result.stdout)
        self.assertIn('name = "codex-off"', result.stdout)
        self.assertIn("enabled = false", result.stdout)
        self.assertNotIn("codex-on", result.stdout)

    def test_multiple_disabled_skills_each_get_their_own_table(self):
        skills = [make_skill(f"off-{i}", f"# {i}\n", tree_sha(f"off-{i}"), codex_enabled=False)
                  for i in range(3)]
        manifest = self.write_manifest(skills)
        result = self.run_install(manifest, "--print-codex-config")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("[[skills.config]]"), 3)
        for i in range(3):
            self.assertIn(f'name = "off-{i}"', result.stdout)


class VersionRefusalTests(InstallSkillsTestCase):
    def test_wrong_version_is_refused_before_any_skill_is_touched(self):
        skill = make_skill("irrelevant", "# x\n", tree_sha("irrelevant"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {}, version="1.6.0")
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(PINNED_VERSION, result.stderr)
        self.assertIn(INSTALL_HINT, result.stderr)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version"])

    def test_missing_binary_is_refused_with_the_install_hint(self):
        skill = make_skill("irrelevant", "# x\n", tree_sha("irrelevant"))
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=Path("/nonexistent/skills-binary"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(INSTALL_HINT, result.stderr)


class OnlyFilterTests(InstallSkillsTestCase):
    def test_only_limits_processing_to_the_named_skill(self):
        wanted = make_skill("wanted", "# wanted\n", tree_sha("wanted"))
        other = make_skill("other", "# other\n", tree_sha("other"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {
            "wanted": {"skill_md": "# wanted\n", "tree_sha": tree_sha("wanted")},
            "other": {"skill_md": "# other\n", "tree_sha": tree_sha("other")},
        })
        manifest = self.write_manifest([wanted, other])
        result = self.run_install(manifest, "--only", "wanted", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.home / ".agents" / "skills" / "wanted").exists())
        self.assertFalse((self.home / ".agents" / "skills" / "other").exists())

    def test_unknown_only_name_fails_cleanly(self):
        skill = make_skill("known", "# known\n", tree_sha("known"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--only", "nope", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("nope", result.stderr)
        self.assertEqual(calls_log(fake_bin), [])  # rejected before even the version check


class JsonOutputTests(InstallSkillsTestCase):
    def test_json_output_is_compact_and_value_free(self):
        content = "# json skill\n"
        skill = make_skill("json-skill", content, tree_sha("json"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"json-skill": {"skill_md": content, "tree_sha": tree_sha("json")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["skills"]["json-skill"], "installed")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["dry_run"])
        # No absolute host path, sha256 or URL leaks into the compact summary.
        self.assertNotIn(str(self.home), result.stdout)
        self.assertNotIn(skill["skill_md_sha256"], result.stdout)
        self.assertNotIn(skill["url"], result.stdout)


if __name__ == "__main__":
    unittest.main()
