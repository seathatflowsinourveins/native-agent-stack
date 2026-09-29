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
                    entry. Per-fixture fault injection: retain_after_remove
                    keeps the named artifacts ("canonical", "lock",
                    "claude-link"), remove_exit fails the remove before it
                    deletes anything, remove_cannot_run leaves the binary
                    non-executable (1) or deletes it (2) after add, so the
                    rollback cannot start, and lock_after_remove leaves the
                    lock "malformed" (truncated, entry kept) or "unreadable".
                    A set, non-blank $CLAUDE_CONFIG_DIR moves the global link
                    to $CLAUDE_CONFIG_DIR/skills, as in skills 1.7.0.

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
pointed at a second temporary directory. $CLAUDE_CONFIG_DIR is stripped the
same way, and only the tests that name it set it.
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "adoption" / "install_skills.py"
ADOPTION_MANIFEST = ROOT / "adoption" / "skills" / "manifest.json"
RUNTIME_MANIFEST = ROOT / "blueprints" / "runtime-workers" / "skills" / "manifest.json"
# A reused entry names main's adoption manifest and is matched there by its skill name.
ADOPTION_REF = "adoption/skills/manifest.json"
REUSE_PIN_KEYS = ("name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256",
                  "skill_md_bytes", "description_chars", "upstream_disable_model_invocation")


def load_installer_module():
    """The installer as a module, for load_manifest against a synthetic adoption manifest root."""
    spec = importlib.util.spec_from_file_location("install_skills_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PINNED_VERSION = "1.7.0"
INSTALL_HINT = "npm install --global --prefix <tools-root>/skills-1.7.0 skills@1.7.0"

# JavaScript trim()'s whitespace (ECMA-262 WhiteSpace and LineTerminator), used by the fake CLI;
# test_js_trim_chars_match_node checks it against node and against install_skills.JS_TRIM_CHARS.
JS_TRIM_CHARS = ("\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
                 "\u2028\u2029\u202f\u205f\u3000\ufeff")

FAKE_SKILLS_BIN_TEMPLATE = r'''#!/usr/bin/env python3
import json, os, sys, shutil, hashlib
from pathlib import Path

VERSION = "__VERSION__"
FIXTURES = __FIXTURES_JSON__
JS_TRIM_CHARS = __JS_TRIM_CHARS__

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


def claude_skills_dir(target: Path, project: bool) -> Path:
    # skills@1.7.0 npm dist/cli.mjs L1398 and L1511: a set, non-blank CLAUDE_CONFIG_DIR moves the
    # global claude-code skills folder, trimmed by JavaScript's trim() and normalized by path.join;
    # project installs keep <project>/.claude/skills.
    if project:
        return target / ".claude" / "skills"
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip(JS_TRIM_CHARS)
    joined = os.path.normpath(os.path.join(config_dir or str(target / ".claude"), "skills"))
    return Path("/" + joined.lstrip("/") if joined.startswith("//") else joined)


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
        link_dir = claude_skills_dir(target, project)
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
        os.symlink(os.path.relpath(skill_dir, link_dir), link)
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
    if fixture.get("remove_cannot_run") == 2:
        os.remove(__file__)  # The rollback's exec then fails with FileNotFoundError: the binary is gone.
    elif fixture.get("remove_cannot_run"):
        # The rollback's exec then fails with PermissionError, an OSError, as for a binary that cannot run.
        os.chmod(__file__, 0o644)
    sys.exit(0)

if argv[0] == "remove":
    name = argv[1]
    # Synthetic fault injection for independently checking cleanup artifacts.
    retained = FIXTURES.get(name, {}).get("retain_after_remove", [])
    if FIXTURES.get(name, {}).get("remove_exit"):
        print(f"fake skills remove: simulated failure for {name!r}", file=sys.stderr)
        sys.exit(FIXTURES[name]["remove_exit"])
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
    link = claude_skills_dir(target, project) / name
    if not project and "claude-link" not in retained and (link.is_symlink() or link.exists()):
        link.unlink()
    path = target / "skills-lock.json" if project else lock_path(home)
    lock = load_lock(path)
    # lock_after_remove: "malformed" leaves a truncated lock that still holds the entry;
    # "unreadable" removes the entry and then makes the lock unreadable.
    fault = FIXTURES.get(name, {}).get("lock_after_remove")
    if "lock" not in retained and fault != "malformed":
        lock.get("skills", {}).pop(name, None)
    text = json.dumps(lock)
    path.write_text(text[:-1] if fault == "malformed" else text)
    if fault == "unreadable":
        os.chmod(path, 0)
    sys.exit(0)

print(f"fake skills: unknown subcommand {argv[0]!r}", file=sys.stderr)
sys.exit(2)
'''


def write_fake_skills_bin(directory: Path, fixtures: dict, version: str = PINNED_VERSION) -> Path:
    text = FAKE_SKILLS_BIN_TEMPLATE.replace("__VERSION__", version).replace(
        "__FIXTURES_JSON__", json.dumps(fixtures)).replace("__JS_TRIM_CHARS__", ascii(JS_TRIM_CHARS))
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
        full_env.pop("CLAUDE_CONFIG_DIR", None)  # nor the global Claude link
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

    def test_project_tree_mismatch_is_refused_before_any_add(self):
        # A rollback after add cannot be relied on: on a host where Codex is detected, the native remove keeps
        # the canonical folder and lock for it (skills@7407f389 remove.ts:293-310, agents.ts:224-232).
        (self.home / ".codex").mkdir()
        other_path = {"truncated": False, "tree": [{"path": "skills/other", "type": "tree", "sha": tree_sha("x")}]}
        endpoint = f"repos/{self.skill['source']}/git/trees/{self.skill['ref']}?recursive=1"
        for label, response in (("different tree", None), ("path absent at the pinned ref", other_path)):
            with self.subTest(label):
                if response is None:
                    self.write_gh_tree(tree_sha("other"))
                else:
                    self.write_gh_responses({endpoint: (0, json.dumps(response))})
                before = calls_log(self.fake_bin)
                for mode in ((), ("--dry-run",), ("--check-only",)):
                    result = self.install(*mode)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("pinned source tree differs from the manifest tree_sha", result.stderr)
                    self.assertIn("project-skill", result.stderr)
                self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]] * 3)  # no add, no remove
                self.assertEqual(list(self.project.iterdir()), [])

    def write_drifting_fake_bin(self, **extra):
        """Installs different SKILL.md bytes than the pin, so verification after add fails and rolls back."""
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
            "skill_md": "# Drifted bytes\n", "tree_sha": self.skill["tree_sha"], **extra}})

    def test_project_rollback_preserves_other_agents_and_source_directories(self):
        self.write_drifting_fake_bin()
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
        self.write_drifting_fake_bin()
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
        projects = self.project
        for artifact in ("canonical", "lock", "claude-link"):
            with self.subTest(artifact=artifact):
                # A retained drifted copy is local content to the next run, so each case gets its own project.
                self.project = projects / artifact
                self.project.mkdir()
                self.write_drifting_fake_bin(retain_after_remove=[artifact])
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

    def test_project_rollback_with_a_malformed_lock_is_error_could_not_be_verified(self):
        self.write_drifting_fake_bin(lock_after_remove="malformed")
        result = self.install("--agent", "claude-code", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "error"})
        self.assertIn("project-skill: error: rollback could not be verified (exit 0; read-back failed: ",
                      result.stderr)
        self.assertNotIn("rolled back", result.stderr)
        self.assertFalse((self.project / ".agents/skills/project-skill").exists())

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

    def test_project_paths_the_cli_writes_must_stay_inside_the_project(self):
        # skills@7407f389 installer.ts:388 recreates <cwd>/.agents/skills/<name> with rm and mkdir
        # (installer.ts:193-200), and remove.ts:296 keeps it for another detected agent. Through a symlink,
        # or with --project-dir at --home, a project install would recreate and then roll back a global
        # skill and leave the global lock stale. Each case is refused before any skills or gh call.
        global_skills = self.home / ".agents" / "skills"
        (global_skills / "project-skill").mkdir(parents=True)
        (global_skills / "project-skill" / "SKILL.md").write_text(self.content)  # matching bytes
        global_lock = self.home / ".agents" / ".skill-lock.json"
        global_lock.write_text(json.dumps({"lockfileVersion": 3, "skills": {}}))
        (self.home / ".claude" / "skills" / "project-skill").mkdir(parents=True)
        projects, gh_log = self.project, self.bin_dir / "gh_calls.log"
        cases = (
            ("universal", ".agents/skills", global_skills),
            ("codex", ".agents", self.home / ".agents"),
            ("universal", ".claude/skills", self.home / ".claude" / "skills"),
            ("universal", "skills-lock.json", global_lock),
            ("universal", ".agents/skills", "inside"),  # a symlinked target directory, even one inside
            ("universal", ".agents/skills/project-skill", global_skills / "project-skill"),
            ("claude-code", ".claude/skills/project-skill", self.home / ".claude" / "skills" / "project-skill"),
            ("universal", None, None),  # --project-dir is --home itself
        )
        for index, (agent, relative, target) in enumerate(cases):
            with self.subTest(agent=agent, path=relative, target=str(target)):
                if relative is None:
                    self.project = self.home
                else:
                    self.project = projects / f"case-{index}"
                    link = self.project / relative
                    link.parent.mkdir(parents=True, exist_ok=True)
                    if target == "inside":
                        target = self.project / "elsewhere"
                        target.mkdir()
                    link.symlink_to(target)
                calls_before = calls_log(self.fake_bin)
                gh_before = gh_log.read_text() if gh_log.exists() else ""
                for mode in ((), ("--dry-run",), ("--check-only",)):
                    result = self.install("--agent", agent, *mode)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("project containment", result.stderr)
                self.assertEqual(calls_log(self.fake_bin), calls_before)  # not even --version ran
                self.assertEqual(gh_log.read_text() if gh_log.exists() else "", gh_before)
                self.assertEqual((global_skills / "project-skill" / "SKILL.md").read_text(), self.content)
                self.assertEqual(json.loads(global_lock.read_text()), {"lockfileVersion": 3, "skills": {}})
                self.assertFalse((self.home / "skills-lock.json").exists())

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

    def test_only_naming_a_pruned_skill_reports_it_as_pruned_not_unknown(self):
        self.skill["status"] = "pruned"
        self.manifest = self.write_manifest([self.skill])
        result = self.install("--only", "project-skill")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("pruned --only name(s)", result.stderr)
        self.assertIn("project-skill", result.stderr)
        self.assertNotIn("unknown", result.stderr)
        self.assertEqual(calls_log(self.fake_bin), [])  # rejected before even the version check

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


class GlobalRollbackReadBackTests(InstallSkillsTestCase):
    """A global rollback is read back from disk, as the project rollback is. skills 1.7.0's scoped
    `remove` keeps the canonical folder and its lock entry while any other detected agent resolves to
    that folder, and exits 0 either way (vercel-labs/skills v1.7.0 src/remove.ts L293-340). Codex reads
    the canonical folder while it exists, and the skills CLI still counts it as installed for every
    universal agent. What remains is reported as 'error' with the project path's reasons, and the
    script deletes nothing itself. Fake-CLI integration fixtures, not a native CLI run."""

    NAME = "drift-skill"
    CONTENT = "# Drifted skill\n"

    def run_drift(self, home_label: str = "home", env: dict | None = None,
                  **fixture) -> subprocess.CompletedProcess:
        """A tree mismatch after add, so the global rollback runs; each label gets its own home and binary."""
        self.home = self.tmp_path / home_label
        self.home.mkdir(exist_ok=True)
        bin_dir = self.tmp_path / f"bin-{home_label}"
        bin_dir.mkdir()
        self.fake_bin = write_fake_skills_bin(bin_dir, {self.NAME: {
            "skill_md": self.CONTENT, "tree_sha": tree_sha("actually-installed"), **fixture}})
        manifest = self.write_manifest([make_skill(self.NAME, self.CONTENT, tree_sha("pinned"))])
        return self.run_install(manifest, "--json", fake_bin=self.fake_bin, env=env)

    def artifacts(self) -> dict:
        canonical = self.home / ".agents" / "skills" / self.NAME
        link = self.home / ".claude" / "skills" / self.NAME
        return {"canonical": canonical.exists() or canonical.is_symlink(),
                "lock": self.NAME in self.lock_data().get("skills", {}),
                "claude-link": link.exists() or link.is_symlink()}

    def assert_error(self, result: subprocess.CompletedProcess, reason: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "error"})
        self.assertIn(f"{self.NAME}: error: {reason} (exit ", result.stderr)
        self.assertNotIn("rolled back", result.stderr)

    def test_retained_canonical_folder_and_lock_are_error_in_use_by_another_agent(self):
        # What skills 1.7.0 does while another universal agent is detected: both stay and remove exits 0.
        result = self.run_drift(retain_after_remove=["canonical", "lock"])
        self.assert_error(result, "rollback retained, in use by another agent")
        calls = calls_log(self.fake_bin)
        self.assertEqual([c[0] for c in calls], ["--version", "add", "remove"])
        self.assertEqual(calls[-1], ["remove", self.NAME, "-g", "-y", "-a", "claude-code", "codex"])
        self.assertEqual(self.artifacts(), {"canonical": True, "lock": True, "claude-link": False})
        # The message names what remains, and nothing was deleted by the script itself.
        self.assertIn("canonical=True, lock=True, claude-link=False", result.stderr)
        self.assertIn(str(self.home / ".agents" / "skills" / self.NAME), result.stderr)
        self.assertIn(str(self.home / ".agents" / ".skill-lock.json"), result.stderr)
        self.assertEqual((self.home / ".agents" / "skills" / self.NAME / "SKILL.md").read_text(), self.CONTENT)

    def test_each_retained_artifact_is_error_on_its_own(self):
        for artifact, reason in (("canonical", "rollback retained, in use by another agent"),
                                 ("lock", "rollback incomplete"), ("claude-link", "rollback incomplete")):
            with self.subTest(artifact=artifact):
                # A retained drifted copy is local content to the next run, so each case gets its own home.
                result = self.run_drift(f"home-{artifact}", retain_after_remove=[artifact])
                self.assert_error(result, reason)
                self.assertEqual(self.artifacts(),
                                 {key: key == artifact for key in ("canonical", "lock", "claude-link")})
                if artifact == "claude-link":
                    link = self.home / ".claude" / "skills" / self.NAME
                    self.assertFalse(link.exists(), "a dangling Claude link must still count as retained")

    def test_remove_that_exits_nonzero_is_error_rollback_incomplete(self):
        result = self.run_drift(remove_exit=1)
        self.assert_error(result, "rollback incomplete")
        self.assertIn("(exit 1; canonical=True, lock=True, claude-link=True)", result.stderr)
        self.assertEqual(self.artifacts(), {"canonical": True, "lock": True, "claude-link": True})

    def test_remove_that_cannot_run_is_error_not_an_exception(self):
        # Fixtures are embedded in the fake CLI as Python source, so flags are ints rather than JSON booleans.
        for flag, case in ((1, "not executable"), (2, "missing")):
            with self.subTest(binary=case):
                result = self.run_drift(f"home-cannot-run-{flag}", remove_cannot_run=flag)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "error"})
                self.assertIn(f"{self.NAME}: verification failed and rollback could not run (", result.stderr)
                self.assertEqual([c[0] for c in calls_log(self.fake_bin)], ["--version", "add"])
                self.assertEqual(self.fake_bin.exists(), flag == 1)

    def test_malformed_lock_after_remove_is_error_could_not_be_verified(self):
        # Both copies are gone and the remove exits 0, but a truncated lock may still hold the entry.
        result = self.run_drift(lock_after_remove="malformed")
        self.assert_error(result, "rollback could not be verified")
        self.assertIn("read-back failed: ", result.stderr)
        lock_text = (self.home / ".agents" / ".skill-lock.json").read_text()
        self.assertIn(f'"{self.NAME}"', lock_text)
        self.assertRaises(ValueError, json.loads, lock_text)
        self.assertFalse((self.home / ".agents" / "skills" / self.NAME).exists())

    @unittest.skipIf(os.geteuid() == 0, "root reads a mode-000 file")
    def test_unreadable_lock_after_remove_is_error_not_an_exception(self):
        result = self.run_drift(lock_after_remove="unreadable")
        self.assert_error(result, "rollback could not be verified")
        self.assertIn("read-back failed: [Errno 13]", result.stderr)

    def test_claude_config_dir_link_is_read_back_where_the_cli_writes_it(self):
        config_dir = self.tmp_path / "claude-config"
        result = self.run_drift(env={"CLAUDE_CONFIG_DIR": str(config_dir)}, retain_after_remove=["claude-link"])
        self.assert_error(result, "rollback incomplete")
        link = config_dir / "skills" / self.NAME
        self.assertTrue(link.is_symlink())
        self.assertIn("canonical=False, lock=False, claude-link=True", result.stderr)
        self.assertIn(f"left: {link}", result.stderr)
        self.assertFalse((self.home / ".claude").exists())

    def test_claude_config_dir_is_trimmed_and_normalized_as_the_cli_does(self):
        # dist/cli.mjs L1398 trims with JavaScript's trim() and L1511 joins with path.join, which collapses "..".
        # U+FEFF is JS whitespace; U+0085 is Python whitespace only, so it stays part of the folder name.
        config_dir = self.tmp_path / "claude-config"
        cases = (("home-dotdot", str(self.tmp_path / "missing" / ".." / "claude-config"), config_dir / "skills"),
                 ("home-bom", "\ufeff", None),
                 ("home-nel", str(config_dir) + "\u0085", Path(str(config_dir) + "\u0085") / "skills"))
        for label, value, link_dir in cases:
            with self.subTest(case=label):
                result = self.run_drift(label, env={"CLAUDE_CONFIG_DIR": value}, retain_after_remove=["claude-link"])
                self.assert_error(result, "rollback incomplete")
                link = (link_dir or self.home / ".claude" / "skills") / self.NAME
                self.assertTrue(link.is_symlink())
                self.assertIn(f"left: {link}", result.stderr)
                self.assertFalse((self.tmp_path / "missing").exists())

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_js_trim_chars_match_node(self):
        script = ('const out = []; for (let c = 0; c <= 0x10FFFF; c++) { if (c >= 0xD800 && c <= 0xDFFF) continue; '
                  'if (String.fromCodePoint(c).trim() === "") out.push(c); } console.log(JSON.stringify(out));')
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=60)
        node_set = set(json.loads(result.stdout))
        self.assertEqual({ord(c) for c in load_installer_module().JS_TRIM_CHARS}, node_set)
        self.assertEqual({ord(c) for c in JS_TRIM_CHARS}, node_set)

    def test_claude_config_dir_control_ignores_the_default_claude_folder(self):
        # Another copy under ~/.claude is not the CLI's link while CLAUDE_CONFIG_DIR is set; a blank value is unset.
        config_dir = self.tmp_path / "claude-config"
        for label, value, link_dir in (("home-config", str(config_dir), config_dir / "skills"),
                                       ("home-blank", "  ", None)):
            with self.subTest(claude_config_dir=value):
                other = self.tmp_path / label / ".claude" / "skills" / self.NAME / "SKILL.md"
                if link_dir is not None:
                    other.parent.mkdir(parents=True)
                    other.write_text("owned before this run\n")
                result = self.run_drift(label, env={"CLAUDE_CONFIG_DIR": value})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
                self.assertNotIn(": error:", result.stderr)
                self.assertEqual(self.artifacts()["canonical"], False)
                self.assertEqual(self.artifacts()["lock"], False)
                if link_dir is not None:
                    self.assertEqual(other.read_text(), "owned before this run\n")
                    self.assertTrue(link_dir.is_dir())
                    self.assertFalse((link_dir / self.NAME).exists() or (link_dir / self.NAME).is_symlink())
                else:
                    self.assertTrue((self.home / ".claude" / "skills").is_dir())
                    self.assertEqual(self.artifacts()["claude-link"], False)

    def test_control_remove_that_deletes_everything_is_rolled_back(self):
        result = self.run_drift()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
        self.assertIn("rolled back", result.stderr)
        self.assertNotIn(": error:", result.stderr)
        self.assertEqual(self.artifacts(), {"canonical": False, "lock": False, "claude-link": False})


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


class ManifestScopeAndPruneTests(InstallSkillsTestCase):
    """A manifest marked "scope": "project" never runs without --project-dir, and a pruned
    entry is never installed, in either mode."""

    def test_project_scoped_manifest_refuses_to_run_without_project_dir(self):
        skill = make_skill("scoped-skill", "# scoped\n", tree_sha("scoped"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {"scoped-skill": {"skill_md": "# scoped\n",
                                                                         "tree_sha": tree_sha("scoped")}})
        data = dict(make_manifest([skill]), scope="project")
        scoped = self.tmp_path / "scoped.json"
        scoped.write_text(json.dumps(data))
        for manifest in (scoped, RUNTIME_MANIFEST):
            for mode in ((), ("--dry-run",), ("--check-only",)):
                with self.subTest(manifest=manifest.name, mode=mode):
                    result = self.run_install(manifest, *mode, fake_bin=fake_bin)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("scoped to projects", result.stderr)
                    self.assertIn("--project-dir", result.stderr)
        self.assertEqual(calls_log(fake_bin), [])  # refused before even the version check
        self.assertFalse((self.home / ".agents").exists())
        printed = self.run_install(scoped, "--print-codex-config")  # print-only; installs nothing
        self.assertEqual(printed.returncode, 0, printed.stdout + printed.stderr)
        scoped.write_text(json.dumps(dict(data, scope="planet")))
        for mode in ((), ("--print-codex-config",)):
            with self.subTest(scope="planet", mode=mode):
                unknown = self.run_install(scoped, *mode, fake_bin=fake_bin)
                self.assertEqual(unknown.returncode, 1, unknown.stdout + unknown.stderr)
                self.assertIn("unknown manifest scope", unknown.stderr)
        self.assertEqual(calls_log(fake_bin), [])
        self.assertFalse((self.home / ".agents").exists())

    def test_pruned_entries_are_never_installed_in_global_mode_either(self):
        kept = make_skill("kept-skill", "# kept\n", tree_sha("kept"))
        pruned = dict(make_skill("pruned-skill", "# pruned\n", tree_sha("pruned")), status="pruned")
        fake_bin = write_fake_skills_bin(self.bin_dir, {
            "kept-skill": {"skill_md": "# kept\n", "tree_sha": tree_sha("kept")},
            "pruned-skill": {"skill_md": "# pruned\n", "tree_sha": tree_sha("pruned")}})
        manifest = self.write_manifest([kept, pruned])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"kept-skill": "installed"})
        self.assertEqual([call[3] for call in calls_log(fake_bin) if call[0] == "add"], ["kept-skill"])
        self.assertFalse((self.home / ".agents" / "skills" / "pruned-skill").exists())
        only = self.run_install(manifest, "--only", "pruned-skill", fake_bin=fake_bin)
        self.assertEqual(only.returncode, 1, only.stdout + only.stderr)
        self.assertIn("pruned --only name(s)", only.stderr)
        self.assertNotIn("unknown", only.stderr)


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


class ReuseRefGateTests(InstallSkillsTestCase):
    """A `reuse_ref` entry takes main's per-skill gates when the manifest is read.

    The references resolve against this checkout's adoption/skills/manifest.json, so the
    fixtures pick real entries by their current gate instead of hard-coding a name. An entry
    is matched there by its skill name, not by an array index.
    """

    def reuse(self, predicate) -> dict:
        old = next(s for s in json.loads(ADOPTION_MANIFEST.read_text())["skills"] if predicate(s))
        entry = {key: old[key] for key in REUSE_PIN_KEYS}
        entry.update(status="trial", reuse_ref=ADOPTION_REF)
        return entry

    def test_runtime_manifest_still_loads_after_main_reorders_or_inserts_entries(self):
        base = json.loads(ADOPTION_MANIFEST.read_text())
        gates = {s["name"]: (s.get("codex_enabled"), s.get("claude_listing")) for s in base["skills"]}
        base["skills"].reverse()
        base["skills"].insert(0, dict(base["skills"][0], name="inserted-main-skill"))
        root = self.tmp_path / "reordered-root"
        (root / "adoption" / "skills").mkdir(parents=True)
        (root / "adoption" / "skills" / "manifest.json").write_text(json.dumps(base))
        manifest = load_installer_module().load_manifest(RUNTIME_MANIFEST, root=root)
        reused = [s for s in manifest["skills"] if "reuse_ref" in s]
        self.assertTrue(reused)
        for skill in reused:
            self.assertEqual((skill.get("codex_enabled"), skill.get("claude_listing")), gates[skill["name"]],
                             skill["name"])

    def test_reuse_ref_without_a_same_named_main_skill_is_refused(self):
        entry = dict(self.reuse(lambda s: True), name="not-in-main")
        result = self.run_install(self.write_manifest([entry]), "--print-codex-config")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not-in-main", result.stderr)
        self.assertIn("names no single", result.stderr)

    def test_reused_skill_that_main_disables_for_codex_comes_out_disabled(self):
        off = self.reuse(lambda s: s.get("codex_enabled") is False)
        on = self.reuse(lambda s: s.get("codex_enabled") is True)
        result = self.run_install(self.write_manifest([off, on]), "--print-codex-config")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(re.findall(r'(?m)^name = "([^"]+)"$', result.stdout), [off["name"]])

    def test_reused_entry_that_restates_a_gate_is_refused(self):
        entry = self.reuse(lambda s: s.get("codex_enabled") is False)
        entry["codex_enabled"] = True  # would silently widen main's Codex gate
        result = self.run_install(self.write_manifest([entry]), "--print-codex-config")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("restates main's codex_enabled", result.stderr)
        self.assertNotIn("[[skills.config]]", result.stdout)

    def test_reuse_ref_that_drifted_from_main_is_refused_before_any_install(self):
        entry = self.reuse(lambda s: s.get("codex_enabled") is False)
        entry["tree_sha"] = tree_sha("drifted")
        manifest = self.write_manifest([entry])
        printed = self.run_install(manifest, "--print-codex-config")
        self.assertEqual(printed.returncode, 1, printed.stdout + printed.stderr)
        self.assertIn("reuse_ref", printed.stderr)
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        installed = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(installed.returncode, 1, installed.stdout + installed.stderr)
        self.assertEqual(calls_log(fake_bin), [])  # refused before even the version check


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
