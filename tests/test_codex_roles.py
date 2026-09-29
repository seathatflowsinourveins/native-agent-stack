"""Tests for tools/adoption/codex_roles.py: the pure helpers of the two Codex role carriers (design 3.2 of U13).

Structural validation and synthetic controls only; nothing here starts Codex. The helpers are the ones the installer
(tools/adoption/apply_codex_lane.py), the static roles row of tools/adoption/prove_codex_lane.py and
tests/test_codex_agents.py share. A test imports the module through roles(), so a missing module fails by
assertion, not by ImportError. The rules of structural_problems and the byte rules of byte_problems are exercised in
tests/test_codex_agents.py, next to the pinned rows and the mutation table.
"""

import hashlib
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

SOURCE = ROOT / "adoption" / "agents" / "codex"
NAMES = ("stack-researcher.toml", "stack-verifier.toml")
GOOD_ROWS = {
    "stack-researcher.toml": "ac77b1624fc0ac264ff5b9807e05889d20137440dea9c016441bba38b1ea8c00",
    "stack-verifier.toml": "281d7e8b985414d072396cc613a75adb3740570ebaaefd1a437ff2c099d5f2bd",
}


def roles(test):
    """The module under test, or a failure by assertion when it has not been written yet."""
    try:
        import codex_roles
    except ImportError:
        test.fail("tools/adoption/codex_roles.py missing")
    return codex_roles


def sums_text(rows):
    return "".join(f"{digest}  {name}\n" for name, digest in rows.items())


class Sha256SumsTests(unittest.TestCase):
    """sha256sums(path): the strict reader of a sha256sum-format file (`<64 lowercase hex>  <name>` per line)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="codex-roles-sums-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, text):
        path = self.tmp / "SHA256SUMS"
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_shipped_file_reads_as_the_two_pinned_rows(self):
        module = roles(self)
        self.assertEqual(module.sha256sums(SOURCE / "SHA256SUMS"), GOOD_ROWS)

    def test_a_missing_trailing_newline_is_read(self):
        module = roles(self)
        self.assertEqual(module.sha256sums(self.write(sums_text(GOOD_ROWS).rstrip("\n"))), GOOD_ROWS)

    def test_a_missing_file_is_an_oserror_and_never_a_value(self):
        module = roles(self)
        with self.assertRaises(OSError):
            module.sha256sums(self.tmp / "absent")

    def test_each_malformed_line_is_refused_with_a_message_that_holds_no_text(self):
        module = roles(self)
        row = GOOD_ROWS["stack-researcher.toml"]
        cases = {
            "one space": f"{row} stack-researcher.toml\n",
            "binary mode marker": f"{row} *stack-researcher.toml\n",
            "three spaces": f"{row}   stack-researcher.toml\n",
            "63 hex digits": f"{row[:-1]}  stack-researcher.toml\n",
            "65 hex digits": f"{row}0  stack-researcher.toml\n",
            "uppercase hex": f"{row.upper()}  stack-researcher.toml\n",
            "not hex": f"{'g' * 64}  stack-researcher.toml\n",
            "empty name": f"{row}  \n",
            "name with a directory part": f"{row}  ../stack-researcher.toml\n",
            "name with a backslash": f"{row}  a\\b.toml\n",
            "name with trailing space": f"{row}  stack-researcher.toml \n",
            "name with a leading star": f"{row}  *stack-researcher.toml\n",
            "blank line": sums_text(GOOD_ROWS).replace("\n", "\n\n", 1),
            "prose": "not a checksum line\n",
            "duplicate name": f"{row}  stack-researcher.toml\n{row}  stack-researcher.toml\n",
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValueError) as caught:
                    module.sha256sums(self.write(text))
                self.assertNotIn("stack-researcher", str(caught.exception))
                self.assertNotIn(row[:16], str(caught.exception))

    def test_the_reader_accepts_what_sha256sum_check_strict_accepts(self):
        # Control against the coreutils oracle: every case above the reader refuses is also refused by
        # `sha256sum --check --strict`, and the shipped file is accepted by both.
        import subprocess
        module = roles(self)
        if not shutil.which("sha256sum"):
            self.skipTest("sha256sum is not on PATH")
        shutil.copy(SOURCE / NAMES[0], self.tmp / NAMES[0])
        good = self.write(f"{GOOD_ROWS[NAMES[0]]}  {NAMES[0]}\n")
        self.assertEqual(module.sha256sums(good), {NAMES[0]: GOOD_ROWS[NAMES[0]]})
        for text in (f"{GOOD_ROWS[NAMES[0]]} {NAMES[0]}\n", "not a checksum line\n"):
            self.write(text)
            got = subprocess.run(["sha256sum", "--check", "--strict", "SHA256SUMS"], cwd=self.tmp,
                                 capture_output=True, text=True, check=False)
            self.assertNotEqual(got.returncode, 0, text)


class SourceProblemsTests(unittest.TestCase):
    """source_problems(directory): the rule ids each carrier of a source directory breaks, for the installer's
    precondition. Exact id sets: source_missing, sha256sums_names, sha256_row, toml_parse and the structural ids."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="codex-roles-source-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.directory = self.tmp / "source"
        self.directory.mkdir()
        for name in (*NAMES, "SHA256SUMS"):
            shutil.copyfile(SOURCE / name, self.directory / name)

    def repin(self, name, data):
        """Write `data` as the carrier `name` and pin its new digest in SHA256SUMS (a consistent edit)."""
        (self.directory / name).write_bytes(data)
        rows = {**GOOD_ROWS, name: hashlib.sha256(data).hexdigest()}
        (self.directory / "SHA256SUMS").write_text(sums_text(rows), encoding="utf-8")

    def problems(self):
        return roles(self).source_problems(self.directory)

    def clean(self):
        return {name: [] for name in NAMES}

    def test_the_shipped_directory_has_no_problem(self):
        self.assertEqual(roles(self).source_problems(SOURCE), self.clean())
        self.assertEqual(roles(self).source_problems(), self.clean())  # the default is the shipped directory

    def test_one_flipped_byte_breaks_only_its_row(self):
        data = (self.directory / NAMES[1]).read_bytes()
        changed = data.replace(b"your output", b"your Output", 1)
        self.assertNotEqual(changed, data)
        (self.directory / NAMES[1]).write_bytes(changed)
        self.assertEqual(self.problems(), {NAMES[0]: [], NAMES[1]: ["sha256_row"]})

    def test_a_changed_row_breaks_only_that_file(self):
        rows = dict(GOOD_ROWS, **{NAMES[0]: "0" * 64})
        (self.directory / "SHA256SUMS").write_text(sums_text(rows), encoding="utf-8")
        self.assertEqual(self.problems(), {NAMES[0]: ["sha256_row"], NAMES[1]: []})

    def test_a_missing_or_unreadable_sums_file_breaks_both(self):
        both = ["sha256_row", "sha256sums_names"]
        (self.directory / "SHA256SUMS").unlink()
        self.assertEqual(self.problems(), {name: both for name in NAMES})
        (self.directory / "SHA256SUMS").write_text("not a checksum line\n", encoding="utf-8")
        self.assertEqual(self.problems(), {name: both for name in NAMES})

    def test_a_third_or_missing_name_in_the_sums_file_is_a_names_problem(self):
        third = {**GOOD_ROWS, "stack-x.toml": "1" * 64}
        (self.directory / "SHA256SUMS").write_text(sums_text(third), encoding="utf-8")
        self.assertEqual(self.problems(), {name: ["sha256sums_names"] for name in NAMES})
        (self.directory / "SHA256SUMS").write_text(sums_text({NAMES[0]: GOOD_ROWS[NAMES[0]]}), encoding="utf-8")
        self.assertEqual(self.problems(), {NAMES[0]: ["sha256sums_names"], NAMES[1]: ["sha256_row", "sha256sums_names"]})

    def test_a_missing_carrier_is_source_missing(self):
        (self.directory / NAMES[0]).unlink()
        self.assertEqual(self.problems(), {NAMES[0]: ["source_missing"], NAMES[1]: []})

    def test_a_file_that_is_not_toml_is_named(self):
        self.repin(NAMES[0], (self.directory / NAMES[0]).read_bytes() + b"\n[[[\n")
        self.assertEqual(self.problems(), {NAMES[0]: ["toml_parse"], NAMES[1]: []})

    def test_a_consistent_edit_that_breaks_a_structural_rule_is_still_refused(self):
        # The row was re-pinned with the file, so the digest agrees; the structural rules are what stop it.
        data = (self.directory / NAMES[0]).read_bytes()
        anchor = b"You do not spawn, message or follow up with other agents."
        self.assertEqual(data.count(anchor), 1)
        self.repin(NAMES[0], data.replace(anchor, anchor + b" Use ToolSearch.", 1))
        self.assertEqual(self.problems(), {NAMES[0]: ["claude_only_name"], NAMES[1]: []})
        # A renamed role: the name field no longer equals the stem.
        data = (self.directory / NAMES[1]).read_bytes()
        self.repin(NAMES[1], data.replace(b'name = "stack-verifier"', b'name = "stack-verifier-x"', 1))
        self.assertEqual(self.problems()[NAMES[1]], ["name_stem"])

    def test_the_result_names_rule_ids_only(self):
        (self.directory / NAMES[0]).write_bytes(b"secret-looking text \xff\n")
        found = self.problems()
        for ids in found.values():
            for rule in ids:
                self.assertRegex(rule, r"^[a-z0-9_]+$")


class ModuleSurfaceTests(unittest.TestCase):
    """The names of design 3.2 exist and mean what the design says."""

    def test_names_and_paths(self):
        module = roles(self)
        self.assertEqual(tuple(module.ROLE_FILES), NAMES)
        self.assertEqual(Path(module.ROLES_SOURCE), SOURCE)

    def test_developer_instructions_and_pins_of_the_shipped_carriers(self):
        module = roles(self)
        for name in NAMES:
            with self.subTest(file=name):
                data = tomllib.loads((SOURCE / name).read_text(encoding="utf-8"))
                self.assertEqual(module.developer_instructions(data), data["developer_instructions"])
                self.assertEqual(tuple(module.role_pins(data)), ("gpt-6-astra", "max"))
                self.assertEqual(module.developer_instructions({}), "")
                self.assertEqual(tuple(module.role_pins({})), (None, None))


if __name__ == "__main__":
    unittest.main()
