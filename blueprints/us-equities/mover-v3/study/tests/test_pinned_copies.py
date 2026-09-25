"""run_discipline.pinned_copies and the import rule (review round 7 F6; review round 8 E1 adds duckdb)."""
import ast
import hashlib
import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
REPO = STUDY.parents[3]
ALLOWED = {"numpy", "pandas", "exchange_calendars", "duckdb"}
INTERNAL = {"core", "pinned", "fetch", "tests", "run"}
FORBIDDEN_NAMES = ("close_hhmm", "fee_rates", "sell_fees", "net_return", "net_return_np", "fetch_one", "ibkr_commission")


def segments(src: str) -> dict:
    lines = src.splitlines(keepends=True)
    out = {}
    for node in ast.parse(src).body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for n in names:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            out[n] = "".join(lines[start - 1: node.end_lineno])
    return out


def study_py_files():
    return sorted(p for p in STUDY.rglob("*.py") if "__pycache__" not in p.parts)


class PinnedCopies(unittest.TestCase):
    def test_each_copy_matches_its_blob(self):
        listing = json.loads((STUDY / "pinned_copies.json").read_text())
        self.assertEqual(len(listing["copies"]), 5)
        for c in listing["copies"]:
            raw = subprocess.check_output(["git", "-C", str(REPO), "cat-file", "blob", c["git_blob"]])
            header = f"blob {len(raw)}\0".encode()
            self.assertEqual(hashlib.sha1(header + raw).hexdigest(), c["git_blob"], c["source_path"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), c["sha256"], c["source_path"])
            listed = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", f"{c['commit']}:{c['source_path']}"],
                                             text=True).strip()
            self.assertEqual(listed, c["git_blob"])
            src, copy = segments(raw.decode()), segments((STUDY / c["copy"]).read_text())
            for name in c["definitions"]:
                self.assertIn(name, copy, f"{c['copy']} lacks {name}")
                self.assertEqual(copy[name], src[name], f"{c['copy']}:{name} is not byte-identical")
            self.assertEqual(set(copy), set(c["definitions"]), f"{c['copy']} holds unlisted definitions")

    def test_protocol_blob_pins_match_listing(self):
        proto = (STUDY.parent / "protocol-core-draft.json").read_text()
        for c in json.loads((STUDY / "pinned_copies.json").read_text())["copies"]:
            self.assertIn(c["git_blob"], proto, c["source_path"])


class ImportRule(unittest.TestCase):
    def test_static_imports_are_stdlib_allowed_or_internal(self):
        stdlib = set(sys.stdlib_module_names)
        for path in study_py_files():
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module.split(".")[0]]
                for m in mods:
                    self.assertTrue(m in stdlib or m in ALLOWED or m in INTERNAL or m == "__future__",
                                    f"{path.relative_to(STUDY)} imports {m}")

    def test_forbidden_pinned_functions_are_never_defined_or_called(self):
        for path in study_py_files():
            if path.name == "test_pinned_copies.py":
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.Name, ast.Attribute)):
                    name = getattr(node, "name", None) or getattr(node, "id", None) or getattr(node, "attr", None)
                    self.assertNotIn(name, FORBIDDEN_NAMES, f"{path.relative_to(STUDY)} uses {name}")

    def test_no_module_outside_the_tree_is_loaded(self):
        for path in study_py_files():
            rel = path.relative_to(STUDY)
            if rel.parts[0] in ("core", "pinned", "fetch") or rel.name == "run.py":
                importlib.import_module(".".join(rel.with_suffix("").parts))
        for name, mod in list(sys.modules.items()):
            f = getattr(mod, "__file__", None)
            if f and str(Path(f).resolve()).startswith(str(REPO)):
                self.assertTrue(str(Path(f).resolve()).startswith(str(STUDY)), f"{name} loaded from {f}")


if __name__ == "__main__":
    unittest.main()
