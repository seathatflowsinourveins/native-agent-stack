"""E1/E2 token E2E receipts: dated adjudication contracts and reproduced answer oracles.

Receipts, corrected only by append-only dated errata (recorded fields stay as recorded):
- E1: evidence/artifacts/token-e2e-ultracode-20260925/receipt.json (#296, catalog f5812d3f)
- E2: evidence/artifacts/token-e2e-ultracode-laptop-20260926/receipt.json (#316, catalog 9a8257cd)

Sources: docs/acceptance-evidence-policy.md, "Discriminating controls" (a pass counts only after
the same check failed with its condition absent; a vacuous pass is recorded as untested); the
2026-09-27 cross-family GPT-6 review of both receipts (its status table and findings, applied
here); evidence/artifacts/token-e2e-codex-20260926/receipt.json#/corrections_to_296 (QMD answered
from a wrong document); the E2 README's Repomix finding, whose root cause is the first-line
signature regex of repomix v1.18.1 src/core/treeSitter/parseStrategies/PythonParseStrategy.ts
L81-86 (https://github.com/yamadashy/repomix/blob/v1.18.1/src/core/treeSitter/parseStrategies/PythonParseStrategy.ts#L81).

The oracle tests rebuild every answer check that pinned Git content can reproduce: the blob at
the receipt's catalog revision is hash-matched to the receipt's recorded baseline where that
baseline is one file (or its byte count where it is a concatenation), the retained answer is run
through the oracle, and a wrong answer must fail the same oracle. These are 2026-09-27 local
integration checks against pinned Git content, not controls the historical runs recorded, so they
never upgrade a row's task acceptance. The ast-grep baselines concatenate files in `grep -rl`
order, which Git cannot reproduce, so only their byte counts are checked. E2's Context Mode and
QMD targets live in another repository, so no oracle here covers them; they stay partial.
"""

import ast
import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E1_DIR = ROOT / "evidence/artifacts/token-e2e-ultracode-20260925"
E2_DIR = ROOT / "evidence/artifacts/token-e2e-ultracode-laptop-20260926"
ADJUDICATED_ON = "2026-09-27"
# The review's vocabulary: task acceptance as committed, not installation or observed invocation.
TASK_ACCEPTANCE = {"partial", "retracted_later", "untested", "unsupported"}
# The review's status table, E1 column, keyed by each row's "tool" field.
E1_STATUS = {
    "rtk": "partial", "context-mode": "partial", "headroom": "partial", "jcodemunch": "partial",
    "qmd": "retracted_later", "serena": "partial", "socraticode": "partial", "ai-memory": "untested",
    "repomix": "retracted_later", "toon": "partial", "ast-grep": "partial", "codebase-memory": "partial",
    "context-hub": "partial", "markitdown": "partial", "agentsview": "partial", "otel-tui": "partial",
}
# E2 column; codebase-memory, agentsview and otel-tui were not exercised in E2.
E2_STATUS = {
    "rtk": "retracted_later", "context-mode": "partial", "headroom": "partial", "jcodemunch": "partial",
    "qmd": "partial", "serena": "partial", "socraticode": "partial", "ai-memory": "partial",
    "repomix": "unsupported", "toon": "partial", "ast-grep": "partial", "context-hub": "partial",
    "markitdown": "partial",
}
# Whether a failing run of the check (a wrong answer, a mutated input) is recorded in E2 itself.
# None: not applicable, because the recorded check already failed on the task answer.
E2_CONTROL = {
    "rtk": False, "context-mode": False, "headroom": True, "jcodemunch": False, "qmd": False,
    "serena": None, "socraticode": True, "ai-memory": True, "repomix": None, "toon": True,
    "ast-grep": False, "context-hub": True, "markitdown": True,
}
E1_SHA256_BEFORE_ERRATA = "8b28bf87f8da27aa5a73e36a4ede1b7707ee4e4b21f31b397f1de1197061897b"
E2_SHA256_BEFORE_ERRATA = "f186f4a192efafb3182185093abf87a7bb7d5b157bfe0d783dfe5df83f38c9f8"
# repomix v1.18.1 PythonParseStrategy.getFunctionSignature (L81-86): tested on a def's first line only.
REPOMIX_FIRST_LINE_SIGNATURE = re.compile(r"def\s+(\w+)\s*\((.*?)\)(\s*->\s*[^:]+)?:")


def load(directory):
    with (directory / "receipt.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def row(receipt, tool):
    matches = [entry for entry in receipt["tools"] if entry["tool"] == tool]
    if len(matches) != 1:
        raise AssertionError(f"expected one {tool!r} row, found {len(matches)}")
    return matches[0]


def require_commit(revision):
    """The git executable, or skip when this checkout lacks Git or the pinned commit.

    Same guard as tests/test_adoption_status.py RetainedEvidenceTests; CI's validate job
    checks out full history (fetch-depth: 0), so the pinned commits are present there.
    """
    git = shutil.which("git")
    if git is None:
        raise unittest.SkipTest("needs git")
    probe = subprocess.run([git, "-C", str(ROOT), "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"],
                           capture_output=True, stdin=subprocess.DEVNULL)
    if probe.returncode != 0:
        raise unittest.SkipTest(f"needs pinned commit {revision} (a full-history checkout)")
    return git


def git_blob(revision, path):
    git = require_commit(revision)
    shown = subprocess.run([git, "-C", str(ROOT), "show", f"{revision}:{path}"],
                           capture_output=True, stdin=subprocess.DEVNULL, check=True)
    return shown.stdout


def git_python_files(revision, directory):
    git = require_commit(revision)
    listed = subprocess.run([git, "-C", str(ROOT), "ls-tree", "-r", "--name-only", revision, f"{directory}/"],
                            capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True)
    return [path for path in listed.stdout.split() if path.endswith(".py")]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---- Oracles (each returns True for PASS) --------------------------------------------------------

def top_level_functions(source):
    tree = ast.parse(source)
    return [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def inventory_oracle(claimed_count, claimed_names, source):
    """A complete top-level inventory: the claimed count, and exactly the source's names, each once."""
    actual = top_level_functions(source)
    return (claimed_count == len(actual) and len(claimed_names) == len(actual)
            and set(claimed_names) == set(actual))


def historical_subset_check(claimed_count, claimed_names, source):
    """E1's recorded check as the E2 verifier describes it: every answered name exists in the source."""
    return set(claimed_names) <= set(top_level_functions(source))


def repomix_dropped_functions(source):
    """Top-level defs whose first physical line fails repomix v1.18.1's signature regex."""
    lines = source.decode("utf-8").split("\n")
    tree = ast.parse(source)
    return [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not REPOMIX_FIRST_LINE_SIGNATURE.search(lines[node.lineno - 1])]


def symbol_location_oracle(start, end, signature, source, name):
    """The answer names the unique def's exact line range and its def-line signature."""
    tree = ast.parse(source)
    defs = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name]
    if len(defs) != 1:
        return False
    node = defs[0]
    line = source.decode("utf-8").split("\n")[node.lineno - 1].strip()
    expected = line[len("def "):].rstrip(":") if line.startswith("def ") else None
    return (start, end, signature) == (node.lineno, node.end_lineno, expected)


def subprocess_run_calls(revision):
    """{path under scripts/ without .py: count} of subprocess.run(...) calls at revision, from CPython's AST."""
    counts = {}
    for path in git_python_files(revision, "scripts"):
        tree = ast.parse(git_blob(revision, path))
        found = sum(1 for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "run" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess")
        if found:
            counts[path[len("scripts/"):-len(".py")]] = found
    return counts


def call_count_oracle(total, files, per_file, actual):
    """Totals match, and every listed file's count matches (a truncated listing checks what it shows)."""
    return (total == sum(actual.values()) and files == len(actual)
            and all(actual.get(stem) == count for stem, count in per_file.items()))


def h2_headings(source):
    return [line[3:] for line in source.decode("utf-8").split("\n") if line.startswith("## ")]


def heading_oracle(count, headings, source):
    actual = h2_headings(source)
    return count == len(actual) and headings == actual[:len(headings)]


def release_step_oracle(document_text):
    """A document that says how a host pins a release names the manifest's source.release_tag."""
    return "release_tag" in document_text


def answer_quotes_present(quotes, document_text):
    """E1's recorded QMD check: text quoted from the retrieved document appears in that document."""
    return all(quote in document_text for quote in quotes)


# ---- Receipt contracts (append-only, dated) -------------------------------------------------------

class ReceiptAdjudicationContracts(unittest.TestCase):
    def check_adjudications(self, receipt, statuses):
        self.assertEqual([entry["tool"] for entry in receipt["tools"]], list(statuses))
        for entry in receipt["tools"]:
            with self.subTest(tool=entry["tool"]):
                verdict = entry.get("adjudication")
                self.assertIsInstance(verdict, dict, "no dated adjudication on this row")
                self.assertEqual(verdict.get("as_of"), ADJUDICATED_ON)
                self.assertIn(verdict.get("task_acceptance"), TASK_ACCEPTANCE)
                self.assertEqual(verdict.get("task_acceptance"), statuses[entry["tool"]])
                self.assertTrue(str(verdict.get("basis", "")).strip())

    def test_every_e1_row_carries_the_reviewed_task_acceptance(self):
        receipt = load(E1_DIR)
        self.check_adjudications(receipt, E1_STATUS)
        for entry in receipt["tools"]:
            with self.subTest(tool=entry["tool"]):
                # E1 recorded no failing run for any of its 16 checks.
                self.assertIs(entry["adjudication"].get("bad_input_control_recorded"), False)

    def test_every_e2_row_carries_the_reviewed_task_acceptance(self):
        receipt = load(E2_DIR)
        self.check_adjudications(receipt, E2_STATUS)
        for entry in receipt["tools"]:
            with self.subTest(tool=entry["tool"]):
                self.assertIs(entry["adjudication"].get("bad_input_control_recorded"), E2_CONTROL[entry["tool"]])

    def test_retractions_keep_the_recorded_outcomes(self):
        # A dated adjudication supersedes; it never rewrites what the run recorded.
        receipt = load(E1_DIR)
        qmd, repomix, memory = row(receipt, "qmd"), row(receipt, "repomix"), row(receipt, "ai-memory")
        self.assertIs(qmd["quality_check"]["passed"], True)
        self.assertEqual(repomix["quality_check"]["output"], "count=47 PASS")
        self.assertTrue(memory["quality_check"]["output"].startswith("PASS base_empty=True"))
        self.assertEqual(qmd["adjudication"].get("failure_mode"), "wrong_document")
        self.assertIn("evidence/artifacts/token-e2e-codex-20260926/receipt.json#/corrections_to_296/0",
                      qmd["adjudication"].get("evidence", []))
        self.assertEqual(repomix["adjudication"].get("failure_mode"), "incomplete_inventory")
        self.assertEqual(memory["adjudication"].get("correctness"), "untested")

    def test_errata_are_dated_and_name_the_pre_erratum_bytes(self):
        for directory, before in ((E1_DIR, E1_SHA256_BEFORE_ERRATA), (E2_DIR, E2_SHA256_BEFORE_ERRATA)):
            with self.subTest(receipt=directory.name):
                errata = load(directory).get("errata")
                self.assertIsInstance(errata, dict)
                self.assertRegex(errata.get("written_at", ""), r"^2026-09-27T\d\d:\d\d:\d\dZ$")
                self.assertEqual(errata.get("receipt_sha256_before_errata"), before)
                self.assertTrue(errata.get("items"))
                self.assertEqual(set(errata.get("task_acceptance_vocabulary", {})), TASK_ACCEPTANCE)
        # The preregistration froze E1 by these bytes as a historical source identity (its README:579).
        prereg = json.loads((ROOT / "evidence/artifacts/token-adoption-e2e-20260926/preregistration.json")
                            .read_text(encoding="utf-8"))
        frozen = {source["path"]: source["sha256"] for source in prereg["receipt_sources"]}
        self.assertEqual(frozen[str(E1_DIR.relative_to(ROOT) / "receipt.json")], E1_SHA256_BEFORE_ERRATA)

    def test_errata_evidence_references_resolve(self):
        # Repository-relative paths, optionally with a JSON pointer (#/...) or a test id (::Class).
        for directory in (E1_DIR, E2_DIR):
            receipt = load(directory)
            references = [ref for item in receipt["errata"]["items"] for ref in item.get("evidence", [])]
            references += [ref for entry in receipt["tools"] for ref in entry["adjudication"].get("evidence", [])]
            self.assertTrue(references)
            for reference in references:
                if "://" in reference:
                    continue
                with self.subTest(receipt=directory.name, reference=reference):
                    target, _, anchor = reference.replace("::", "#", 1).partition("#")
                    path = (ROOT / target).resolve()
                    self.assertTrue(path.is_relative_to(ROOT))
                    self.assertTrue(path.is_file(), reference)
                    if anchor.startswith("/"):
                        value = json.loads(path.read_text(encoding="utf-8"))
                        for part in anchor[1:].split("/"):
                            value = value[int(part)] if isinstance(value, list) else value[part]
                    elif anchor:
                        self.assertIn(f"class {anchor}(", path.read_text(encoding="utf-8"))

    def test_socraticode_counts_an_abridged_transcription(self):
        entry = row(load(E2_DIR), "socraticode")
        self.assertEqual(entry["adjudication"].get("tool_output_provenance"), "abridged_transcription")

    def test_readmes_carry_the_dated_corrections(self):
        e1 = (E1_DIR / "README.md").read_text(encoding="utf-8")
        for phrase in ("**Correction (2026-09-27)", "Repomix", "ai-memory", "no recorded failing control"):
            with self.subTest(readme="E1", phrase=phrase):
                self.assertIn(phrase, e1)
        e2 = (E2_DIR / "README.md").read_text(encoding="utf-8")
        for phrase in ("## Erratum (2026-09-27)", "no recorded failing control", "abridged transcription"):
            with self.subTest(readme="E2", phrase=phrase):
                self.assertIn(phrase, e2)


# ---- Reproduced answer oracles with failing controls ----------------------------------------------

class E1RepomixInventoryOracle(unittest.TestCase):
    """E1 recorded `count=47 PASS` for the top-level functions of scripts/host_requests.py."""

    def setUp(self):
        self.entry = row(load(E1_DIR), "repomix")
        self.revision = load(E1_DIR)["catalog_revision"]
        self.source = git_blob(self.revision, "scripts/host_requests.py")

    def test_baseline_is_the_pinned_pair_of_files(self):
        pair = self.source + git_blob(self.revision, "scripts/credential_status.py")
        self.assertEqual(sha256(pair), self.entry["exact_comparison"]["baseline_sha256"])
        self.assertEqual(len(pair), self.entry["exact_comparison"]["baseline_bytes"])

    def test_recorded_answer_fails_a_complete_inventory(self):
        claimed = int(re.search(r"\((\d+) total;", self.entry["answer_excerpt"]).group(1))
        actual = top_level_functions(self.source)
        self.assertEqual((claimed, len(actual)), (47, 48))
        answered = [name for name in actual if name != "status_body"]
        # The recorded (subset) check passes the incomplete answer; the complete-inventory oracle rejects it.
        self.assertTrue(historical_subset_check(claimed, answered, self.source))
        self.assertFalse(inventory_oracle(claimed, answered, self.source))
        # Positive control: the complete inventory passes the same oracle.
        self.assertTrue(inventory_oracle(len(actual), actual, self.source))
        # Controls that keep the correct count but get the names wrong (2026-09-27 GPT-6 review finding).
        controls = {
            "one name missing": answered,
            "one name duplicated": [*answered, answered[0]],
            "one name invented": [*answered, "not_a_function"],
            "no names": [],
        }
        for label, names in controls.items():
            with self.subTest(control=label):
                self.assertFalse(inventory_oracle(len(actual), names, self.source))

    def test_repomix_first_line_regex_predicts_the_dropped_definitions(self):
        self.assertEqual(repomix_dropped_functions(self.source), ["status_body"])
        other = git_blob(self.revision, "scripts/credential_status.py")
        self.assertEqual(repomix_dropped_functions(other), ["inspect"])


class JCodeMunchLocationOracle(unittest.TestCase):
    """E1 and E2 answered register_file's location from get_symbol_source over the same blob."""

    CASES = (
        (E1_DIR, r"lines (\d+)-(\d+) \(end_line=\d+\)", r"^(register_file\([^)]*\) -> \w+) is defined"),
        (E2_DIR, r"lines (\d+)-(\d+) \(\d+ lines\)", r"Signature: `def (register_file\([^)]*\) -> \w+)`"),
    )

    def test_recorded_answers_pass_and_wrong_answers_fail(self):
        for directory, lines_pattern, signature_pattern in self.CASES:
            receipt = load(directory)
            entry = row(receipt, "jcodemunch")
            source = git_blob(receipt["catalog_revision"], "scripts/host_receipts.py")
            with self.subTest(receipt=directory.name, check="baseline"):
                self.assertEqual(sha256(source), entry["exact_comparison"]["baseline_sha256"])
            start, end = map(int, re.search(lines_pattern, entry["answer_excerpt"]).groups())
            signature = re.search(signature_pattern, entry["answer_excerpt"]).group(1)
            with self.subTest(receipt=directory.name, check="recorded answer"):
                self.assertTrue(symbol_location_oracle(start, end, signature, source, "register_file"))
            controls = {
                "start off by one": (start + 1, end, signature),
                "end off by one": (start, end - 1, signature),
                "return type changed": (start, end, signature.replace("-> None", "-> bool")),
                "parameter dropped": (start, end, signature.replace(", relative_path: str", "")),
            }
            for label, (bad_start, bad_end, bad_signature) in controls.items():
                with self.subTest(receipt=directory.name, control=label):
                    self.assertFalse(symbol_location_oracle(bad_start, bad_end, bad_signature, source,
                                                            "register_file"))


class AstGrepCallOracle(unittest.TestCase):
    """E1 and E2 answered subprocess.run call counts per file from ast-grep's compact JSON."""

    def parse(self, directory):
        receipt = load(directory)
        entry = row(receipt, "ast-grep")
        text = entry["answer_excerpt"]
        total, files = map(int, re.search(r"(\d+) subprocess\.run\(\S*\) calls across (\d+) files", text).groups())
        per_file = {stem: int(count) for stem, count in
                    re.findall(r"scripts/(\w+)\.py: (\d+)", text) or re.findall(r"(\w+)\.py \((\d+)\)", text)}
        return receipt, entry, total, files, per_file

    def test_recorded_answers_pass_and_wrong_answers_fail(self):
        for directory, listed in ((E1_DIR, 9), (E2_DIR, 11)):
            receipt, entry, total, files, per_file = self.parse(directory)
            actual = subprocess_run_calls(receipt["catalog_revision"])
            with self.subTest(receipt=directory.name, check="listing parsed"):
                self.assertEqual(len(per_file), listed)
            with self.subTest(receipt=directory.name, check="recorded answer"):
                self.assertTrue(call_count_oracle(total, files, per_file, actual))
            with self.subTest(receipt=directory.name, check="baseline bytes"):
                # The baseline concatenates the matching files in grep -rl order; only its size is reproducible.
                size = sum(len(git_blob(receipt["catalog_revision"], f"scripts/{stem}.py")) for stem in actual)
                self.assertEqual(size, entry["exact_comparison"]["baseline_bytes"])
            first = sorted(per_file)[0]
            dropped = dict(per_file)
            del dropped[first]
            controls = {
                "one count inflated": (total, files, {**per_file, first: per_file[first] + 1}),
                "one call missed": (total - 1, files, {**per_file, first: per_file[first] - 1}),
                "one file dropped": (total - per_file[first], files - 1, dropped),
                "one file invented": (total + 1, files + 1, {**per_file, "not_a_script": 1}),
            }
            for label, (bad_total, bad_files, bad_listing) in controls.items():
                with self.subTest(receipt=directory.name, control=label):
                    self.assertFalse(call_count_oracle(bad_total, bad_files, bad_listing, actual))


class E1ContextModeHeadingOracle(unittest.TestCase):
    """E1 answered the handbook's '## ' heading count and first headings via ctx_execute_file."""

    def test_recorded_answer_passes_and_wrong_answers_fail(self):
        receipt = load(E1_DIR)
        entry = row(receipt, "context-mode")
        source = git_blob(receipt["catalog_revision"], "docs/grand-catalog-handbook.md")
        self.assertEqual(sha256(source), entry["exact_comparison"]["baseline_sha256"])
        text = entry["answer_excerpt"]
        count = int(re.search(r"has (\d+) lines starting with", text).group(1))
        headings = re.findall(r"\d+\. ## (.*?)(?=\\n|$)", text)
        self.assertEqual(len(headings), 7)  # the retained excerpt is truncated inside the eighth
        self.assertTrue(heading_oracle(count, headings, source))
        controls = {
            "count off by one": (count + 1, headings),
            "two headings swapped": (count, [headings[1], headings[0], *headings[2:]]),
            "one heading renamed": (count, [*headings[:-1], headings[-1] + " and more"]),
        }
        for label, (bad_count, bad_headings) in controls.items():
            with self.subTest(control=label):
                self.assertFalse(heading_oracle(bad_count, bad_headings, source))


class E1QmdDocumentOracle(unittest.TestCase):
    """E1 answered 'which document says how a new machine pins a release' with a catalog document."""

    def test_recorded_answer_names_a_document_without_the_release_step(self):
        receipt = load(E1_DIR)
        entry = row(receipt, "qmd")
        answered = re.search(r"^Document: (\S+\.md)", entry["answer_excerpt"]).group(1)
        document = git_blob(receipt["catalog_revision"], answered)
        self.assertEqual(sha256(document), entry["exact_comparison"]["baseline_sha256"])
        text = document.decode("utf-8")
        # E1's recorded check held the answer's own quotes against the retrieved document: circular.
        quote = next(line for line in text.split("\n") if "runtime-target.json" in line)
        self.assertTrue(answer_quotes_present([quote], text))
        self.assertFalse(release_step_oracle(text))
        # Positive control: the document the Codex run named (corrections_to_296) passes.
        update = git_blob(receipt["catalog_revision"], "adoption/update.md").decode("utf-8")
        self.assertTrue(release_step_oracle(update))
        # The catalog index the worker queried held only the two us-equities collections.
        scope = entry["upstream_stats_reported_by_worker"]
        self.assertIn("catalogs/us-equities", scope)
        self.assertIn("blueprints/us-equities", scope)
        self.assertNotIn("adoption", scope)


if __name__ == "__main__":
    unittest.main()
