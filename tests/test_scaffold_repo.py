"""tools/adoption/scaffold_repo.py and the scaffold it writes (adoption/scaffold/).

- The scaffold's AGENTS.md carries the block after the native-agent-stack:top-rule marker of
  adoption/templates/codex.AGENTS.template.md byte for byte, so the two move together; a one-word drift is caught.
- CLAUDE.md is the `@AGENTS.md` import and one comment line, nothing else.
- The scaffold is exactly six files, one of them rendered for the host.
- Against real temporary directories: a fresh directory gets every file, a rerun changes nothing, a modified file is
  skipped (exit 3) and kept while an absent one is still created, --force overwrites it keeping its mode, --dry-run
  writes nothing and exits as a real run would, a symlink is never written through, a main commit that lacks the gate
  is refused before any write, and a template value that would break the TOML is refused.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import scaffold_repo  # noqa: E402

SCAFFOLD = ROOT / "adoption/scaffold"
CODEX_AGENTS_TEMPLATE = ROOT / "adoption/templates/codex.AGENTS.template.md"
TOP_RULE_MARKER = "<!-- native-agent-stack:top-rule -->\n"
A_COMMIT = "0123456789abcdef0123456789abcdef01234567"  # not in any checkout: the gate check reports it unchecked
VALUES = ["--set", "ECO_ROOT=/opt/eco", "--set", "HOST_PATH=/usr/bin:/bin", "--set", "CODE_INDEX_PATH=/opt/index"]
EXPECTED = {"AGENTS.md", "CLAUDE.md", ".agents/skills/README.md", ".github/pull_request_template.md",
            ".github/workflows/sota-sources.yml", ".codex/config.toml"}


def top_rule_block(text: str) -> str:
    """From the end of the top-rule marker line to the next native-agent-stack marker."""
    start = text.index(TOP_RULE_MARKER) + len(TOP_RULE_MARKER)
    return text[start:text.index("<!-- native-agent-stack:", start)]


def run(target: Path, *extra: str, env=None) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = scaffold_repo.main(["--target", str(target), "--main-sha", A_COMMIT, *VALUES, *extra],
                                  env=env if env is not None else {"HOME": "/home/example"})
    return code, out.getvalue(), err.getvalue()


def tree(directory: Path) -> dict:
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in sorted(directory.rglob("*")) if path.is_file()}


def rows(output: str) -> dict:
    """{file: status label} from the printed table."""
    found = {}
    for line in output.splitlines():
        for label in ("would create", "would overwrite", "created", "overwritten", "unchanged", "skipped"):
            if line.startswith(label + " "):
                found[line[len(label):].split()[0]] = label
    return found


class ScaffoldContentTests(unittest.TestCase):
    def test_agents_md_carries_the_codex_templates_top_rule_block_byte_for_byte(self):
        scaffold = (SCAFFOLD / "AGENTS.md").read_text(encoding="utf-8")
        template = CODEX_AGENTS_TEMPLATE.read_text(encoding="utf-8")
        for text in (scaffold, template):
            self.assertEqual(text.count(TOP_RULE_MARKER), 1)
        block = top_rule_block(template)
        self.assertTrue(block.startswith("Top rule: research convergence first;"), block[:80])
        self.assertEqual(top_rule_block(scaffold), block)

    def test_a_drifted_top_rule_is_caught(self):
        scaffold = (SCAFFOLD / "AGENTS.md").read_text(encoding="utf-8")
        block = top_rule_block(CODEX_AGENTS_TEMPLATE.read_text(encoding="utf-8"))
        for old, new in (("research convergence first", "research first"), ("that turn.\n", "that turn. \n")):
            with self.subTest(drift=new):
                self.assertEqual(scaffold.count(old), 1)
                self.assertNotEqual(top_rule_block(scaffold.replace(old, new)), block)

    def test_claude_md_is_only_the_agents_md_import_and_one_comment(self):
        lines = (SCAFFOLD / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "@AGENTS.md")
        self.assertTrue(lines[1].startswith("<!-- ") and lines[1].endswith(" -->"), lines[1])
        self.assertEqual(lines[1].count("-->"), 1)

    def test_the_scaffold_is_exactly_six_files_and_only_the_workflow_is_a_template(self):
        files = scaffold_repo.scaffold_files(A_COMMIT, "codex = true\n")
        self.assertEqual({name for name, _ in files}, EXPECTED)
        self.assertEqual(len(files), len(EXPECTED))
        self.assertEqual(files[-1][0], ".codex/config.toml")
        templates = [path.relative_to(SCAFFOLD).as_posix() for path in SCAFFOLD.rglob("*" + scaffold_repo.TEMPLATE_SUFFIX)]
        self.assertEqual(templates, [".github/workflows/sota-sources.yml.template"])

    def test_the_default_host_path_is_the_example_hosts_never_this_processs_path(self):
        example = json.loads((ROOT / "adoption/hosts/example.json").read_text(encoding="utf-8"))
        values = scaffold_repo.codex_values(None, [], {"HOME": "/home/example",
                                                        "PATH": "/mnt/c/Users/example/bin:/usr/bin"})
        self.assertEqual(values["HOST_PATH"], example["HOST_PATH"])
        self.assertEqual(values["ECO_ROOT"], "/home/example/.local/share/codex-ecosystem")
        self.assertEqual(values["CODE_INDEX_PATH"], "/home/example/.code-index")
        values = scaffold_repo.codex_values(None, [], {"HOME": "/home/example", "ECO_INSTALL_ROOT": "/opt/eco",
                                                        "CODE_INDEX_PATH": "/opt/index"})
        self.assertEqual((values["ECO_ROOT"], values["CODE_INDEX_PATH"]), ("/opt/eco", "/opt/index"))


class ScaffoldRunTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.target = self.base / "repo"
        self.target.mkdir()

    def test_a_fresh_directory_gets_every_file(self):
        code, out, err = run(self.target)
        self.assertEqual(code, 0, out + err)
        written = tree(self.target)
        self.assertEqual(set(written), EXPECTED)
        self.assertEqual(rows(out), {name: "created" for name in EXPECTED})
        self.assertIn("summary: 6 created", out)
        for name in ("AGENTS.md", "CLAUDE.md", ".agents/skills/README.md", ".github/pull_request_template.md"):
            self.assertEqual(written[name], (SCAFFOLD / name).read_bytes(), name)
        workflow = written[".github/workflows/sota-sources.yml"].decode("utf-8")
        self.assertIn(f"sota-sources-gate.yml@{A_COMMIT}\n", workflow)
        self.assertNotIn("<sha>", workflow)
        config = tomllib.loads(written[".codex/config.toml"].decode("utf-8"))
        self.assertEqual(config["shell_environment_policy"]["set"]["PATH"], "/opt/eco/bin:/usr/bin:/bin")
        self.assertEqual(config["mcp_servers"]["jcodemunch"]["command"], "/opt/eco/bin/jcodemunch-mcp")
        self.assertEqual(config["mcp_servers"]["jcodemunch"]["env"]["CODE_INDEX_PATH"], "/opt/index")
        self.assertIn("commit not in this checkout, unchecked", out)
        for path in self.target.rglob("*"):
            if path.is_file():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644, path)

    def test_a_rerun_changes_nothing(self):
        self.assertEqual(run(self.target)[0], 0)
        before = {path: path.stat().st_mtime_ns for path in self.target.rglob("*")}
        code, out, err = run(self.target)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(rows(out), {name: "unchanged" for name in EXPECTED})
        self.assertIn("summary: 6 unchanged", out)
        self.assertEqual({path: path.stat().st_mtime_ns for path in self.target.rglob("*")}, before)

    def test_a_modified_file_is_refused_and_kept_while_an_absent_one_is_created(self):
        self.assertEqual(run(self.target)[0], 0)
        (self.target / "AGENTS.md").write_text("# Our own rules\n", encoding="utf-8")
        (self.target / "CLAUDE.md").unlink()
        code, out, _ = run(self.target)
        self.assertEqual(code, scaffold_repo.EXIT_REFUSED)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "# Our own rules\n")
        self.assertEqual((self.target / "CLAUDE.md").read_bytes(), (SCAFFOLD / "CLAUDE.md").read_bytes())
        self.assertEqual(rows(out)["AGENTS.md"], "skipped")
        self.assertEqual(rows(out)["CLAUDE.md"], "created")
        self.assertIn("differs from the scaffold; --force overwrites it", out)

    def test_force_overwrites_a_modified_file_and_keeps_its_mode(self):
        self.assertEqual(run(self.target)[0], 0)
        agents = self.target / "AGENTS.md"
        agents.write_text("# Our own rules\n", encoding="utf-8")
        agents.chmod(0o600)
        code, out, err = run(self.target, "--force")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(rows(out)["AGENTS.md"], "overwritten")
        self.assertEqual(agents.read_bytes(), (SCAFFOLD / "AGENTS.md").read_bytes())
        self.assertEqual(stat.S_IMODE(agents.stat().st_mode), 0o600)

    def test_dry_run_writes_nothing_and_exits_as_a_real_run_would(self):
        code, out, err = run(self.target, "--dry-run")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertEqual(rows(out), {name: "would create" for name in EXPECTED})
        self.assertIn("DRY RUN: nothing is written.", out)
        (self.target / "CLAUDE.md").write_text("@README.md\n", encoding="utf-8")
        code, out, _ = run(self.target, "--dry-run")
        self.assertEqual(code, scaffold_repo.EXIT_REFUSED)
        self.assertEqual(tree(self.target), {"CLAUDE.md": b"@README.md\n"})
        code, out, _ = run(self.target, "--dry-run", "--force")
        self.assertEqual((code, rows(out)["CLAUDE.md"]), (0, "would overwrite"))
        self.assertEqual(tree(self.target), {"CLAUDE.md": b"@README.md\n"})

    def test_a_symlink_is_never_written_through_even_with_force(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "AGENTS.md").write_text("elsewhere\n", encoding="utf-8")
        (self.target / "AGENTS.md").symlink_to(outside / "AGENTS.md")
        (self.target / ".github").symlink_to(outside, target_is_directory=True)
        code, out, _ = run(self.target, "--force")
        self.assertEqual(code, scaffold_repo.EXIT_REFUSED)
        self.assertEqual(tree(outside), {"AGENTS.md": b"elsewhere\n"})
        self.assertEqual(rows(out)["AGENTS.md"], "skipped")
        self.assertEqual(rows(out)[".github/workflows/sota-sources.yml"], "skipped")
        self.assertIn("AGENTS.md is a symlink; nothing is written through it", out)
        self.assertIn(".github is a symlink; nothing is written through it", out)
        self.assertEqual((self.target / "CLAUDE.md").read_bytes(), (SCAFFOLD / "CLAUDE.md").read_bytes())

    def test_a_main_commit_without_the_gate_is_refused_before_any_write(self):
        root = subprocess.run(["git", "-C", str(ROOT), "rev-list", "--max-parents=0", "HEAD"],
                              capture_output=True, text=True, check=False).stdout.split()
        if not root:
            self.skipTest("no root commit reachable in this clone")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scaffold_repo.main(["--target", str(self.target), "--main-sha", root[-1], *VALUES],
                                      env={"HOME": "/home/example"})
        self.assertEqual(code, scaffold_repo.EXIT_USAGE)
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertIn("MISSING at that commit", out.getvalue())
        self.assertIn("would call a missing file", err.getvalue())
        self.assertEqual(rows(out.getvalue()), {name: "would create" for name in EXPECTED})  # the plan, not a result

    def test_unusable_inputs_are_refused_before_any_write(self):
        for extra in (["--set", 'HOST_PATH=/usr/bin"x'], ["--set", "ECO_ROOT=relative/eco"],
                      ["--set", "CODE_INDEX_PATH=/opt/a\\b"], ["--set", "NOEQUALS"]):
            with self.subTest(extra=extra):
                code, _, err = run(self.target, *extra)
                self.assertEqual(code, scaffold_repo.EXIT_USAGE)
                self.assertIn("refused:", err)
                self.assertEqual(list(self.target.iterdir()), [])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(scaffold_repo.main(["--target", str(self.target), "--main-sha", "main", *VALUES]),
                             scaffold_repo.EXIT_USAGE)
            self.assertEqual(scaffold_repo.main(["--target", str(self.base / "missing"), "--main-sha", A_COMMIT]),
                             scaffold_repo.EXIT_USAGE)
            self.assertEqual(scaffold_repo.main(["--target", str(ROOT), "--main-sha", A_COMMIT]),
                             scaffold_repo.EXIT_USAGE)
        self.assertIn("this catalog checkout", err.getvalue())

    def test_the_command_line_dry_run(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/adoption/scaffold_repo.py"), "--target",
                                 str(self.target), "--dry-run", "--main-sha", A_COMMIT, *VALUES],
                                capture_output=True, text=True, timeout=120, check=False,
                                env={**os.environ, "HOME": "/home/example"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(rows(result.stdout), {name: "would create" for name in EXPECTED})
        self.assertEqual(list(self.target.iterdir()), [])


class MainCommitTests(unittest.TestCase):
    """The default <sha> and the gate check, against canned git answers."""

    @staticmethod
    def answers(mapping: dict):
        def git(*args):
            key = " ".join(args)
            returncode, stdout = mapping.get(key, (128, ""))
            return subprocess.CompletedProcess(["git", *args], returncode, stdout, "")
        return git

    def test_the_default_is_origins_main_from_ls_remote(self):
        with mock.patch.object(scaffold_repo, "git", self.answers(
                {"ls-remote origin refs/heads/main": (0, f"{A_COMMIT}\trefs/heads/main\n")})):
            self.assertEqual(scaffold_repo.main_sha(None), A_COMMIT)
        for answer in ((0, ""), (2, f"{A_COMMIT}\trefs/heads/main\n"), (0, "abc\trefs/heads/main\n"),
                       (0, f"{A_COMMIT}\trefs/heads/main\n{A_COMMIT}\trefs/heads/other\n")):
            with self.subTest(answer=answer), mock.patch.object(scaffold_repo, "git", self.answers(
                    {"ls-remote origin refs/heads/main": answer})), self.assertRaises(scaffold_repo.Unusable):
                scaffold_repo.main_sha(None)
        with self.assertRaises(scaffold_repo.Unusable):
            scaffold_repo.main_sha(A_COMMIT.upper())

    def test_the_gate_is_present_absent_or_unchecked(self):
        commit = f"cat-file -e {A_COMMIT}^{{commit}}"
        gate = f"cat-file -e {A_COMMIT}:{scaffold_repo.GATE_FILE}"
        for mapping, state in (({commit: (0, ""), gate: (0, "")}, "present"), ({commit: (0, "")}, "absent"),
                               ({}, "unknown")):
            with self.subTest(state=state), mock.patch.object(scaffold_repo, "git", self.answers(mapping)):
                self.assertEqual(scaffold_repo.gate_state(A_COMMIT), state)


if __name__ == "__main__":
    unittest.main()
