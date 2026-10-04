"""Tests for the OpenHands resolver's trusted pre-push gate (resolver/push_gate.py).

Decision record amendment of 2026-10-04 (docs/decisions/2026-09-28-openhands-resolver-isolation.md):
option 1 with enforcement before execution, in trusted harness code. These are our local
integration checks with synthetic fixture repositories, local git, a fake zizmor and, where it
is installed at the pinned version, the real zizmor (docs/acceptance-evidence-policy.md). They are
not upstream acceptance, and nothing reaches GitHub. Owner names and paths are fixture values.
"""

import contextlib
from collections import Counter
import fnmatch
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import hermetic_git_environment
from tests.test_runtime_worker_openhands_resolver import (
    FAKE_GITLEAKS, FINAL_MESSAGE, ORIGIN, REAL_GIT, RUN_ID, FakeTools, ResolverGitHub, commit_all, full_export,
    load_resolver, planted_base, run_git, write_file)

ROOT = Path(__file__).resolve().parents[1]
RESOLVER = "blueprints/runtime-workers/openhands/resolver"
ENFORCING = (f"{RESOLVER}/push_gate.py", f"{RESOLVER}/patch_policy.py", f"{RESOLVER}/gate_reads.py",
             f"{RESOLVER}/gh_harness.py")
# The zizmor version the gate enforces, read from the file and with the pattern the gate uses
# (push_gate.ZIZMOR_PIN_FILE, push_gate.ZIZMOR_PIN), so a pin bump moves these tests with it and the real-zizmor test
# keeps running against the newly pinned release instead of skipping.
PIN = re.search(r"^zizmor==(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\b",
                (ROOT / ".github/requirements-ci.txt").read_text(encoding="utf-8"), re.M)["version"]
CHECKOUT_SHA = "08c6903cd8c0fde910a37f88322edcfb5dd907a8"

CI_WORKFLOW = f"""name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions: {{}}
jobs:
  check:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@{CHECKOUT_SHA} # v5.0.0
        with:
          persist-credentials: false
      - name: Gate script
        run: python3 scripts/check_gate.py --config policy/gate.toml
      - name: Policy tests
        run: |
          # scripts/commented_only.py is named in a comment only
          python3 -m unittest tests.test_policy -v
      - name: Whole suite
        run: python3 -m unittest
      - uses: ./tools/ci-action
"""

NIGHTLY_WORKFLOW = """name: nightly
on:
  schedule:
    - cron: "0 5 * * *"
  workflow_dispatch:
permissions: {}
jobs:
  nightly:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - run: python3 scripts/nightly_only.py
"""

CI_ACTION = """name: ci-action
description: Fixture composite action
runs:
  using: composite
  steps:
    - name: Run the fixture check
      run: bash tools/ci-action/run.sh
      shell: bash
"""

GATE_FILES = {
    ".github/workflows/ci.yml": CI_WORKFLOW,
    ".github/workflows/nightly.yml": NIGHTLY_WORKFLOW,
    ".github/requirements-ci.txt": f"zizmor=={PIN} \\\n    --hash=sha256:{'0' * 64}\n",
    "tools/ci-action/action.yml": CI_ACTION,
    "tools/ci-action/run.sh": "echo checked\n",
    "scripts/check_gate.py": "import gate_helpers\n\nprint(gate_helpers.VALUE)\n",
    "scripts/gate_helpers.py": "VALUE = 1\n",
    "scripts/nightly_only.py": "print('nightly')\n",
    "scripts/commented_only.py": "print('comment')\n",
    "policy/gate.toml": "strict = true\n",
    "tests/__init__.py": "",
    # A test module imports the code it tests; that code is not a gate (src/app.py stays editable).
    "tests/test_policy.py": "import src.app\n\nWORKFLOWS = '.github/workflows'\n",
    "tests/helpers.py": "",
    "docs/a.md": "a\n",
    "docs/guide.md": "guide\n",
    "docs/CODEOWNERS": "* @fixture-owner\n",
    "CODEOWNERS": "* @fixture-owner\n",
    "src/app.py": "print('app')\n",
    "AGENTS.md": "# Rules\n",
}


class GateFixture:
    """A bare fixture origin whose main carries the three enforcing files, the trusted checkout
    the gate runs from (a clone of that main), and agent clones with planted commits."""

    def __init__(self, root, overrides=None):
        self.root = Path(root)
        self.work = self.root / "origin-work"
        self.work.mkdir(parents=True)
        run_git(self.work, "init", "-q", "-b", "main")
        contents = {**GATE_FILES, **(overrides or {})}
        for rel in ENFORCING:
            contents[rel] = (ROOT / rel).read_bytes()
        for rel, data in contents.items():
            if data is not None:
                write_file(self.work, rel, data)
        self.base = commit_all(self.work, "base")
        self.bare = self.root / "origin.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(self.work), str(self.bare)], check=True,
                       capture_output=True, env=hermetic_git_environment())
        self.trusted = self.clone("trusted")
        self.count = 0

    def clone(self, name):
        path = self.root / name
        subprocess.run(["git", "clone", "-q", str(self.bare), str(path)], check=True, capture_output=True,
                       env=hermetic_git_environment())
        return path

    def advance(self, edits):
        """A new main commit in the origin; returns its id."""
        for rel, data in edits.items():
            write_file(self.work, rel, data)
        commit = commit_all(self.work, "later")
        run_git(self.work, "push", "-q", str(self.bare), "HEAD:main")
        return commit

    def agent_commit(self, edits, *, commits=1):
        """An agent clone with `commits` commits on main applying `edits` (None deletes a file)."""
        self.count += 1
        clone = self.clone(f"agent-{self.count}")
        head = None
        for number in range(commits):
            for rel, data in edits.items():
                if data is None:
                    (clone / rel).unlink()
                else:
                    write_file(clone, rel, data if number == 0 else f"{data}{number}\n")
            head = commit_all(clone, f"agent {number}")
        return clone, head


def load_gate(checkout):
    """push_gate.py from `checkout`, under a fresh module name (registered, as the harness reads it)."""
    path = Path(checkout) / RESOLVER / "push_gate.py"
    name = f"push_gate_fixture_{secrets.token_hex(6)}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FAKE_ZIZMOR = """#!{python}
import json, os, sys
argv = sys.argv[1:]
inputs = sorted(os.path.relpath(os.path.join(top, name), ".") for top, _, names in os.walk(".") for name in names)
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": argv, "inputs": inputs, "env": sorted(os.environ)}}) + "\\n")
if argv == ["--version"]:
    sys.stdout.write({version!r})
    sys.exit(0)
sys.stdout.write({output!r})
sys.exit({code})
"""


def fake_zizmor(root, *, version=f"zizmor {PIN}\n", output="[]", code=0):
    """A stand-in zizmor: answers --version, logs its argv and the files it was given, prints `output`."""
    path = Path(root) / f"zizmor-{secrets.token_hex(3)}"
    log = Path(root) / f"{path.name}.jsonl"
    path.write_text(FAKE_ZIZMOR.format(python=sys.executable, log=str(log), version=version, output=output, code=code),
                    encoding="utf-8")
    path.chmod(0o755)
    return str(path), log


def zizmor_calls(log):
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def finding(ident, path):
    return {"ident": ident, "desc": "fixture", "url": "https://docs.zizmor.sh/audits/", "ignored": False,
            "determinations": {"confidence": "High", "severity": "High", "persona": "Regular"}, "fixes": [],
            "locations": [{"symbolic": {"key": {"Local": {"given_path": f"./{path}"}}}}]}


def installed_zizmor():
    """The installed zizmor when it is the pinned version, else None (the real-zizmor test skips)."""
    path = shutil.which("zizmor")
    if not path:
        return None
    try:
        version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return path if version.strip() == f"zizmor {PIN}" else None


# The construct of adoption-bootstrap.yml's `changes` step (main e0c329ae9): path globs in bash arrays,
# compared with `git diff --name-only` output through `case` patterns. The listed files are neither
# run nor read; the gate must not protect them, and must keep protecting any list used another way.
FILTER_SCRIPT = """PATTERNS=(
  'scripts/listed_only.py'
  'tools/listed/*'
)
OTHER=(
  "docs/a.md"
)
match=false
while IFS= read -r -d '' file; do
  for pattern in "${PATTERNS[@]}"; do
    case "$file" in
      $pattern) match=true ;;
    esac
  done
  for pattern in "${OTHER[@]}"; do
    case "$file" in
      ${pattern})
        other=true
        break ;;
    esac
  done
done < "$diff_file"
echo "Matched (PATTERNS): $match" >> "$GITHUB_STEP_SUMMARY"
"""

FILTER_STEP = """      - name: Detect changed paths
        shell: bash
        run: |
""" + "".join(f"          {line}\n" if line else "\n" for line in FILTER_SCRIPT.splitlines())

# Cross-family review P1 of 2026-10-04: the derivation missed data that CI-run gate code reads, such as
# blueprints/convergence-practice/contract.schema.json, which scripts/validate_convergence.py reads
# as `read_json(CONTRACT / "contract.schema.json")` with `CONTRACT = REPO / "blueprints/convergence-practice"`.
# READ_FORMS holds every read form gate_reads models, for the reader alone. READ_POLICY is that
# shape in a fixture repository's gate step: a schema under a module constant, here imported from a
# helper module, and TOML, YAML, f-string and glob reads; the step also runs a shell script that
# names its data file.
READ_FORMS = '''import csv
import json
import os
import tomllib
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
HERE = Path(__file__).parent
CONTRACT = REPO / "policy/contract"
TABLE = (("alpha", ("table", "alpha.json")), ("beta", ("table", "beta.json")))


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv):
    schema = read_json(CONTRACT / "contract.schema.json")
    with open(REPO / "policy" / "rules.toml", "rb") as handle:
        rules = tomllib.load(handle)
    workflow = yaml.safe_load((REPO / "policy/ci.yaml").read_text(encoding="utf-8"))
    rows = list(csv.reader(open(os.path.join(os.path.dirname(__file__), "..", "policy", "rows.csv"))))
    local = (HERE / "local.json").read_bytes()
    limits = (REPO / f"policy/limits-{rules['tier']}.json").read_text()
    checks = [read_json(path) for path in sorted((REPO / "policy" / "checks").glob("*.json"))]
    sets = [path.read_text() for path in (REPO / "policy" / "sets").iterdir()]
    for name in ("one.json", "two.json"):
        (REPO / "policy" / "pair" / name).read_text()
    for _, (directory, leaf) in TABLE:
        (REPO / "policy" / directory / leaf).read_text()
    augmented = REPO / "policy"
    augmented /= "augmented.json"
    received = Path(argv[1]) / "policy" / "received.json"
    subjects = [(REPO / name).read_text() for name in rules["subjects"]]
    outside = Path("/etc/hostname").read_text()
    return schema, workflow, rows, local, limits, checks, sets, augmented.read_text(), received, subjects, outside


def normalized(rel):
    rel = os.path.normpath(rel)
    return (REPO / rel).read_text()


def unresolved():
    globals()["TARGET"] = "policy/target.json"
    return (REPO / TARGET).read_text()  # noqa: F821
'''

READ_POLICY = '''import json
import tomllib
from pathlib import Path

import yaml

from gate_paths import CONTRACT_DIR

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / CONTRACT_DIR


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main():
    schema = read_json(CONTRACT / "contract.schema.json")
    with open(REPO / "policy" / "rules.toml", "rb") as handle:
        rules = tomllib.load(handle)
    workflow = yaml.safe_load((REPO / "policy/ci.yaml").read_text(encoding="utf-8"))
    limits = read_json(REPO / f"policy/limits-{rules['tier']}.json")
    checks = [read_json(path) for path in sorted((REPO / "policy" / "checks").glob("*.json"))]
    subjects = [(REPO / name).read_text(encoding="utf-8") for name in rules["subjects"]]
    return schema, workflow, limits, checks, subjects
'''

# A gate script that reads one code file as data (hashes and copies a workflow script, as
# tools/adoption/install_claude_profile.py does since main's #679) and runs another through a
# module-local wrapper. The data file's text names src/app.py and docs/a.md; neither is read by CI.
INSTALL_LANES = '''import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "tools" / "lane.js"
sys.path.insert(0, str(ROOT / "tools/lib"))


def run_check(script):
    return subprocess.run([sys.executable, str(script)], check=True)


def main(dest):
    import lane_rules  # from the directory put on sys.path above, imported lazily

    digest = hashlib.sha256(LANE.read_bytes()).hexdigest()
    shutil.copy2(LANE, Path(dest) / LANE.name)
    run_check(ROOT / "scripts" / "lane_check.py")
    lane_rules.check()
    return digest


if __name__ == "__main__":
    print(main(sys.argv[1]))
'''

READS_FILES = {
    ".github/workflows/ci.yml": CI_WORKFLOW + """      - name: Gate data
        run: |
          python3 scripts/read_policy.py
          bash scripts/check_shell.sh
          python3 scripts/install_lanes.py "$RUNNER_TEMP"
""",
    "scripts/install_lanes.py": INSTALL_LANES,
    # Imported through the directory install_lanes.py puts on sys.path (acceptance probe of 2026-10-04
    # on 7c1d24cc5: verdict_review_gate.py imports record_verdicts the same way).
    "tools/lib/lane_rules.py": ('import json\nfrom pathlib import Path\n\n\ndef check():\n'
                                '    return json.loads((Path(__file__).resolve().parents[2] / "policy" / '
                                '"lane_rules.json").read_text())\n'),
    "policy/lane_rules.json": "{}\n",
    "tools/lane.js": "const target = 'src/app.py';\nconst notes = require('fs').readFileSync('docs/a.md');\n",
    "scripts/lane_check.py": ('import json\nfrom pathlib import Path\n\n'
                              'print(json.loads((Path(__file__).resolve().parents[1] / "policy" / "lane.json")'
                              '.read_text()))\n'),
    "policy/lane.json": "{}\n",
    "scripts/read_policy.py": READ_POLICY,
    "scripts/gate_paths.py": 'CONTRACT_DIR = "policy/contract"\n',
    "scripts/check_shell.sh": "grep -q strict policy/shell.txt\npython3 scripts/inner_check.py\n",
    # Run by the shell script, not by the step: gate code all the same.
    "scripts/inner_check.py": ('import json\nfrom pathlib import Path\n\n'
                               'print(json.loads((Path(__file__).resolve().parents[1] / "policy" / "inner.json")'
                               '.read_text()))\n'),
    "policy/inner.json": "{}\n",
    "policy/contract/contract.schema.json": '{"type": "object", "required": ["id"]}\n',
    "policy/rules.toml": 'tier = "strict"\nsubjects = ["docs/guide.md"]\n',
    "policy/ci.yaml": "checks: [one]\n",
    "policy/limits-strict.json": "{}\n",
    "policy/checks/one.json": "{}\n",
    "policy/shell.txt": "strict\n",
}

# Calls that execute code, and reads of code as data, for GateReads.executed alone.
EXEC_FORMS = '''import hashlib
import importlib.util
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

from helpers import run_it

ROOT = Path(__file__).resolve().parents[1]


def run_script(path):
    return subprocess.run([sys.executable, str(path)], check=True)


class Runner:
    def command(self, label, argv):
        return subprocess.run(argv, check=False)


RUNNER = ("bash", "scripts/bound.sh")


def main(name, dest):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "direct.py")], check=True)
    subprocess.run(["bash", "scripts/direct.sh"], check=True)
    cmd = [sys.executable, str(ROOT / "scripts" / "argv.py")]
    subprocess.run(cmd, check=True)
    subprocess.run(RUNNER, check=True)
    run_script(ROOT / "scripts" / "wrapped.py")
    Runner().command("lane", ["node", str(ROOT / "tools" / "lane.mjs")])
    run_it(ROOT / "scripts" / "helped.py")
    runpy.run_path(str(ROOT / "scripts" / "run_path.py"))
    spec = importlib.util.spec_from_file_location("loaded", ROOT / "scripts" / "loaded.py")
    exec(compile((ROOT / "scripts" / "compiled.py").read_text(), "compiled", "exec"))
    digest = hashlib.sha256((ROOT / "tools" / "hashed.js").read_bytes()).hexdigest()
    shutil.copy2(ROOT / "tools" / "copied.js", dest)
    source = (ROOT / "scripts" / "parsed.py").read_text()
    subprocess.run([sys.executable, str(ROOT / "scripts" / name)], check=True)
    return spec, digest, source
'''

# A read the reader cannot resolve: the name is bound through globals(), which it does not model.
UNRESOLVED_FILES = {
    ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/read_unknown.py\n",
    "scripts/read_unknown.py": ('from pathlib import Path\n\nREPO = Path(__file__).resolve().parents[1]\n'
                                'globals()["TARGET"] = "policy/target.json"\n'
                                'print((REPO / TARGET).read_text(encoding="utf-8"))  # noqa: F821\n'),
    "policy/target.json": "{}\n",
}


class WorkflowReaderTests(unittest.TestCase):
    """push_gate's text-level workflow reader, interpolation scan and unittest discovery."""

    @classmethod
    def setUpClass(cls):
        cls.g = load_gate(ROOT)

    def test_values_are_read_in_every_supported_form(self):
        text = ("on: [push, pull_request]\n"
                "defaults:\n  run:\n    working-directory: tools/x\n"
                "jobs:\n  a:\n    steps:\n"
                "      - run: |\n          python3 scripts/a.py\n\n          echo done\n        shell: bash\n"
                "      - run: >-\n          python3 scripts/b.py\n          --flag\n"
                "      - run: \"python3 scripts/c.py\"\n"
                "      - run: 'python3 scripts/d.py'\n"
                "      - run: python3 scripts/e.py\n          --long\n"
                "      - uses: ./tools/action # local\n"
                "      - uses: actions/github-script@v7\n        with:\n          script: |\n            core.info('x')\n"
                "      - env:\n          BODY: |\n            run: not a key\n        run: echo env\n")
        facts = self.g.scan_workflow(text)
        self.assertEqual(facts.triggers, frozenset({"push", "pull_request"}))
        self.assertEqual(facts.runs, ["python3 scripts/a.py\n\necho done\n", "python3 scripts/b.py --flag\n",
                                      "python3 scripts/c.py", "python3 scripts/d.py", "python3 scripts/e.py --long",
                                      "echo env"])
        self.assertEqual(facts.scripts, ["core.info('x')\n"])
        self.assertEqual(facts.working_dirs, ["tools/x"])
        self.assertEqual(facts.local_uses, ["./tools/action"])

    def test_triggers_are_listed_or_unknown(self):
        cases = {"on: push\n": frozenset({"push"}),
                 "on:\n  schedule:\n    - cron: '0 5 * * *'\n  workflow_dispatch:\n": frozenset({"schedule",
                                                                                         "workflow_dispatch"}),
                 "on:\n  - push\n  - pull_request\n": frozenset({"push", "pull_request"}),
                 "'on':\n  pull_request:\n    paths: ['a/**']\n": frozenset({"pull_request"}),
                 "on: {push: {branches: [main]}}\n": None,
                 "name: no triggers\n": None}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.g._triggers(text.splitlines()), expected)

    def test_constructs_that_could_hide_a_value_fail_closed(self):
        for text in ("jobs:\n  a:\n    steps:\n      - {run: python3 x.py}\n",
                     "jobs:\n  a:\n    steps:\n      - run: *shared\n",
                     "x: &shared python3 x.py\njobs:\n  a:\n    steps:\n      - <<: *base\n",
                     "jobs:\n  a:\n    steps:\n      - run: !!str python3 x.py\n",
                     "jobs:\n  a:\n    with: {script: x}\n",
                     "a: 1\n---\nb: 2\n",
                     "\trun: x\n"):
            with self.subTest(text=text):
                with self.assertRaises(self.g.WorkflowSyntaxError):
                    self.g.scan_workflow(text)

    def test_untrusted_event_text_is_found_in_expressions(self):
        flagged = ["echo ${{ github.event.pull_request.title }}", "echo ${{ github.event.issue.body }}",
                   "echo ${{ github.head_ref }}", "echo ${{ github.event.pull_request.head.ref }}",
                   "echo ${{ github.event.commits[0].message }}", "echo ${{ github.event.comment.body }}",
                   "# ${{ github.event.review.body }}"]
        safe = ["echo ${{ github.event.pull_request.number }}", "echo \"$TITLE\"", "echo ${{ github.sha }}",
                "echo ${{ github.ref }}", "echo ${{ steps.x.outputs.title }}"]
        for text in flagged:
            with self.subTest(text=text):
                self.assertTrue(self.g.untrusted_interpolations(text))
        for text in safe:
            with self.subTest(text=text):
                self.assertEqual(self.g.untrusted_interpolations(text), [])

    def lists(self, script):
        return [script[start:end].split("=", 1)[0] for start, end in self.g.pattern_lists(script)]

    def test_lists_used_only_as_case_patterns_are_set_aside(self):
        self.assertEqual(self.lists(FILTER_SCRIPT), ["PATTERNS", "OTHER"])
        blanked = self.g._without_pattern_lists(FILTER_SCRIPT)
        self.assertNotIn("scripts/listed_only.py", blanked)
        self.assertIn("for pattern in", blanked)  # only the list literals are blanked

    def test_a_list_used_any_other_way_keeps_its_names(self):
        loop = 'for pattern in "${PATTERNS[@]}"; do\n'
        variants = {
            "the loop variable is run": FILTER_SCRIPT.replace(loop, loop + '  python3 "$pattern"\n', 1),
            "the loop variable is read elsewhere": FILTER_SCRIPT + 'echo "$pattern"\n',
            "the list is expanded outside a loop": FILTER_SCRIPT + 'printf "%s\\n" "${PATTERNS[@]}" > list.txt\n',
            "an element is expanded directly": FILTER_SCRIPT + 'cat "${PATTERNS[0]}"\n',
            "the list is appended to": FILTER_SCRIPT + "PATTERNS+=('scripts/more.py')\n",
            "an element is assigned": FILTER_SCRIPT + "PATTERNS[2]='scripts/more.py'\n",
            "the list is read into": FILTER_SCRIPT + 'read -ra PATTERNS <<< "a b"\n',
            "the script uses eval": FILTER_SCRIPT + 'eval "true"\n',
            "the script uses indirect expansion": FILTER_SCRIPT + 'ref=PATTERNS; echo "${!ref}"\n',
            "the script uses a nameref": FILTER_SCRIPT + "declare -n ref=PATTERNS\n",
            "an element expands": FILTER_SCRIPT.replace("'tools/listed/*'", '"$HOME/listed"'),
            "an element substitutes": FILTER_SCRIPT.replace("'tools/listed/*'", "$(ls scripts)"),
            "the list has no loop": FILTER_SCRIPT.replace(loop, 'for pattern in "${OTHER[@]}"; do\n', 1),
        }
        for name, script in variants.items():
            with self.subTest(variant=name):
                self.assertNotIn("PATTERNS", self.lists(script))
                self.assertIn("scripts/listed_only.py", self.g._without_pattern_lists(script))

    def test_the_recorded_rule_is_the_most_specific_whatever_the_order(self):
        for order in (("ci_named", "ci_discovered", "ci_import"), ("ci_import", "ci_discovered", "ci_named")):
            with self.subTest(order=order):
                item = self.g.CiProtected()
                for rule in order:
                    item.add_prefix("tests", rule)
                    item.add_file("tests/test_a.py", rule)
                self.assertEqual((item.prefixes["tests"], item.files["tests/test_a.py"]),
                                 ("ci_discovered", "ci_discovered"))
                first, second = self.g.CiProtected(), self.g.CiProtected()
                first.add_prefix("tools/x", order[0])
                second.add_prefix("tools/x", order[-1])
                merged = self.g.Protected([first, second], set())
                self.assertEqual(merged.rule("tools/x/y.py"), "ci_named")

    def test_unittest_discovery_follows_packages_only(self):
        blobs = {"tests/__init__.py", "tests/test_a.py", "tests/helpers.py", "tests/sub/__init__.py",
                 "tests/sub/test_b.py", "tests/plain/test_c.py", "test_root.py", "tools/t/test_d.py",
                 "tools/t/test_e.py"}
        self.assertEqual(self.g.discovered(blobs, ".", "test*.py"),
                         ({"tests/test_a.py", "tests/sub/test_b.py", "test_root.py"}, {"tests"}))
        self.assertEqual(self.g.discovered(blobs, "tools/t", "test_d.py"), ({"tools/t/test_d.py"}, set()))
        runs = self.g._unittest_runs("python3 -m unittest\npython3 -m unittest -v >log 2>&1\n"
                                     "python3 -m unittest tests.test_a\n"
                                     "python3 -m unittest discover -s tools/t -p 'test_d.py' -q\n"
                                     "python3 -m unittest discover tools/t test_e.py\n"
                                     "python3 -m unittest \\\n  -v\n")
        self.assertEqual(runs, [(".", "test*.py"), (".", "test*.py"), ("tools/t", "test_d.py"),
                                ("tools/t", "test_e.py"), (".", "test*.py")])


class GateReadsTests(unittest.TestCase):
    """gate_reads and the derivation's data reads (rule ci_read) on in-memory trees, without git."""

    @classmethod
    def setUpClass(cls):
        cls.g = load_gate(ROOT)
        cls.gr = cls.g.gate_reads

    def reads(self, source, tracked, path="scripts/check.py"):
        blobs = {path, *tracked}
        return self.gr.GateReads(path, source).reads(blobs, self.g.patch_policy.parent_dirs(blobs))

    def inventory(self, item):
        """Interpret reported paths with stdlib fnmatch; never a push-policy decision."""
        class Inventory:
            def rule(_, path):
                if path in item.files:
                    return item.files[path]
                for prefix, rule in item.prefixes.items():
                    if path.startswith(prefix + "/"):
                        return rule
                for pattern, rule in item.globs.items():
                    if fnmatch.fnmatchcase(path, pattern):
                        return rule
                return None
        return Inventory()

    def derive(self, files):
        return self.g.derive_ci_protected(self.g.patch_policy.MemoryTree({**GATE_FILES, **files})).advisory

    def derive_read(self, source):
        return self.derive({
            ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
            "scripts/check.py": source,
            "policy/strict.json": "{}\n",
        })

    def test_iterating_imported_literal_constants_reports_each_path(self):
        # Main 89cf253c0: from scripts import new_host_grand_list as g; g.LEDGERS.items().
        constants = ('LEDGERS = {"one": "policy/one.json", "two": "policy/two.json"}\n'
                     'KEY_PATHS = {"policy/one.json": 1, "policy/two.json": 2}\n'
                     'PATHS = ["policy/one.json", "policy/two.json"]\n'
                     'TUPLE_PATHS = ("policy/one.json", "policy/two.json")\n')
        forms = (
            'for key, rel in g.LEDGERS.items():\n    (ROOT / rel).read_text()\n',
            'data = {key: (ROOT / rel).read_text() for key, rel in g.LEDGERS.items()}\n',
            'for rel in g.LEDGERS.values():\n    (ROOT / rel).read_text()\n',
            'for rel in g.KEY_PATHS.keys():\n    (ROOT / rel).read_text()\n',
            'for rel in g.PATHS:\n    (ROOT / rel).read_text()\n',
            'for rel in g.TUPLE_PATHS:\n    (ROOT / rel).read_text()\n',
        )
        constants_reader = self.gr.GateReads("scripts/gate_constants.py", constants)

        def imported(module, name, level):
            return constants_reader.module_value(name) if module == "scripts.gate_constants" and not level \
                else (self.gr.UNKNOWN,)

        for form in forms:
            with self.subTest(form=form):
                source = ('from pathlib import Path\nfrom scripts import gate_constants as g\n'
                          'ROOT = Path(__file__).resolve().parents[1]\n' + form)
                derived = self.derive({
                    ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
                    "scripts/check.py": source,
                    "scripts/gate_constants.py": constants,
                    "policy/one.json": "{}\n",
                    "policy/two.json": "{}\n",
                    "policy/other.json": "{}\n",
                })
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.unclassified, [])
                self.assertEqual(derived.globs, {})
                reported = self.inventory(derived)
                for path in ("policy/one.json", "policy/two.json"):
                    self.assertEqual(reported.rule(path), "ci_read")
                self.assertIsNone(reported.rule("policy/other.json"))
                # Observe the caller alone as well: the helper's literal strings must not mask
                # a dropped read in the loop or comprehension.
                blobs = {"scripts/check.py", "policy/one.json", "policy/two.json", "policy/other.json"}
                reader = self.gr.GateReads("scripts/check.py", source, imported=imported)
                self.assertEqual(reader.reads(blobs, self.g.patch_policy.parent_dirs(blobs)),
                                 ({"scripts/check.py", "policy/one.json", "policy/two.json"}, set(), set(), set()))

    def test_iterating_an_unresolved_mapping_keeps_the_read_visible(self):
        for package in ("absent_package", "scripts"):
            with self.subTest(package=package):
                source = ('from pathlib import Path\nfrom ' + package + ' import gate_constants as g\n'
                          'ROOT = Path(__file__).resolve().parents[1]\n'
                          'for key, rel in g.LEDGERS.items():\n    (ROOT / rel).read_text()\n')
                derived = self.derive({
                    ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
                    "scripts/check.py": source,
                    "scripts/gate_constants.py": 'LEDGERS = build_mapping()\n',
                    "policy/strict.json": "{}\n",
                })
                self.assertEqual(derived.unresolved, ["scripts/check.py:5"])
                self.assertEqual(derived.globs, {})
                self.assertIsNone(self.inventory(derived).rule("policy/strict.json"))

    def test_computed_relative_fstring_read_reports_fixed_glob(self):
        # Cross-family read 489b: the push workflow runs this script, so its policy input is gate data.
        derived = self.derive_read('import sys\nopen(f"policy/{sys.argv[1]}.json").read()\n')
        self.assertEqual(derived.unresolved, [])
        self.assertEqual(derived.globs, {"policy/*.json": "ci_read"})
        self.assertEqual(self.inventory(derived).rule("policy/added.json"), "ci_read")
        self.assertIsNone(self.inventory(derived).rule("policy/added.toml"))

    def test_computed_path_division_read_reports_fixed_glob(self):
        derived = self.derive_read('import sys\nfrom pathlib import Path\nname = sys.argv[1]\n'
                                   '(Path("policy") / f"{name}.json").read_text()\n')
        self.assertEqual(derived.unresolved, [])
        self.assertEqual(derived.globs, {"policy/*.json": "ci_read"})
        self.assertEqual(self.inventory(derived).rule("policy/added.json"), "ci_read")
        self.assertIsNone(self.inventory(derived).rule("policy/added.toml"))

    def test_computed_os_path_join_read_reports_fixed_glob(self):
        derived = self.derive_read('import os\nimport sys\nopen(os.path.join("policy", sys.argv[1])).read()\n')
        self.assertEqual(derived.unresolved, [])
        self.assertEqual(derived.globs, {"policy/*": "ci_read"})
        self.assertEqual(self.inventory(derived).rule("policy/added.toml"), "ci_read")
        self.assertIsNone(self.inventory(derived).rule("other/added.toml"))

    def test_environment_base_read_is_unclassified_at_script_line(self):
        derived = self.derive_read('import os\nopen(os.path.join(os.environ["POLICY_ROOT"], "rules.json")).read()\n')
        self.assertEqual(derived.unresolved, [])
        self.assertEqual(derived.unclassified, ["scripts/check.py:2"])

    def test_whole_argv_read_stays_an_editable_subject(self):
        derived = self.derive_read('import sys\nopen(sys.argv[1]).read()\n')
        self.assertEqual(derived.unresolved, [])
        self.assertEqual(derived.globs, {})
        self.assertEqual(derived.unclassified, [])
        self.assertIsNone(self.inventory(derived).rule("policy/strict.json"))

    def test_fixed_directory_constructions_keep_each_runtime_segment_in_the_glob(self):
        forms = {
            'open("policy/" + name + ".json").read()': ("policy/*.json", "policy/new.json", "policy/new.toml"),
            'open("policy/%s.json" % name).read()': ("policy/*.json", "policy/new.json", "policy/new.toml"),
            'open("policy/{}.json".format(name)).read()': ("policy/*.json", "policy/new.json", "policy/new.toml"),
            'Path("policy", name).read_text()': ("policy/*", "policy/new.json", "other/new.json"),
            'Path("policy").joinpath(name).read_text()': ("policy/*", "policy/new.json", "other/new.json"),
            '(Path("policy") / name).with_suffix(".json").read_text()':
                ("policy/*.json", "policy/new.json", "policy/new.toml"),
            '(Path("policy") / name).with_stem("rules").read_text()':
                ("policy/rules*", "policy/rules.json", "policy/other.json"),
            'Path("policy/old.json").with_name(f"{name}.json").read_text()':
                ("policy/*.json", "policy/new.json", "policy/new.toml"),
            'open(f"policy/{name}/rules-{name}.json").read()':
                ("policy/*/rules-*.json", "policy/set/rules-new.json", "policy/set/other.json"),
            # b8eb9352b also protects policy/ as a prefix for the embedded Path / name.
            'open(f"{Path(\'policy\') / name}.json").read()':
                ("policy/*.json", "policy/new.json", "other/new.json"),
        }
        for expression, (glob, matching, nonmatching) in forms.items():
            with self.subTest(expression=expression):
                derived = self.derive_read('import sys\nfrom pathlib import Path\nname = sys.argv[1]\n'
                                           + expression + '\n')
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.globs, {glob: "ci_read"})
                reported = self.inventory(derived)
                self.assertEqual(reported.rule(matching), "ci_read")
                self.assertIsNone(reported.rule(nonmatching))

    def test_runtime_only_computed_reads_are_visible_and_argv_compositions_stay_subjects(self):
        forms = ('f"{get_base()}{sys.argv[1]}"', 'get_base() + sys.argv[1]',
                 'Path(environ["R"]) / sys.argv[1]')
        for expression in forms:
            for read in (f'open({expression}).read()', f'Path({expression}).read_text()'):
                with self.subTest(read=read):
                    derived = self.derive_read('import sys\nfrom pathlib import Path\nfrom os import environ\n'
                                               + read + '\n')
                    self.assertEqual(derived.unresolved, [])
                    self.assertEqual(derived.unclassified, ["scripts/check.py:4"])
                    self.assertEqual(derived.globs, {})
        for expression in ('sys.argv[1]', 'f"{sys.argv[1]}{sys.argv[2]}"', 'sys.argv[1] + sys.argv[2]'):
            for read in (f'open({expression}).read()', f'Path({expression}).read_text()'):
                with self.subTest(subject=read):
                    derived = self.derive_read('import sys\nfrom pathlib import Path\n' + read + '\n')
                    self.assertEqual((derived.unresolved, derived.unclassified, derived.globs), ([], [], {}))

    def test_opaque_enumerations_are_unclassified(self):
        for expression in ('Path(os.environ["R"]).glob("*.json")',
                           'Path(os.environ["R"]).rglob("*.json")',
                           'Path(os.environ["R"]).iterdir()', 'os.listdir(os.environ["R"])'):
            with self.subTest(expression=expression):
                derived = self.derive_read('import os\nfrom pathlib import Path\n' + expression + '\n')
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.unclassified, ["scripts/check.py:3"])

    def test_named_opaque_path_constructions_stay_visible_without_a_read_sink(self):
        # The path-building expressions must remain visible when a helper reads them later.
        derived = self.derive_read('import os\nfrom pathlib import Path\n'
                                   'target = Path(os.environ["ROOT"]) / "policy" / "received.json"\n'
                                   'read_policy(target)\n')
        self.assertEqual(derived.files.get("policy/received.json"), "ci_read")
        self.assertEqual(derived.unresolved, [])
        self.assertIn("scripts/check.py:3", derived.unclassified)
        derived = self.derive_read('import os, sys\nfrom pathlib import Path\n'
                                   'root = Path(os.environ["ROOT"]) / "policy"\n'
                                   'target = root / sys.argv[1]\nread_policy(target)\n')
        self.assertIn("scripts/check.py:4", derived.unclassified)
        derived = self.derive_read('ratio = get_seconds() / 60\n')
        self.assertEqual((derived.unresolved, derived.unclassified), ([], []))

    def test_join_aliases_and_leading_dot_report_normalized_fixed_globs(self):
        forms = {
            'open(join("./policy", sys.argv[1])).read()': "policy/*",
            'open(osp.join("./policy", sys.argv[1])).read()': "policy/*",
            'open("/".join(["./policy", sys.argv[1]])).read()': "policy/*",
            'open(f"./policy/{sys.argv[1]}.json").read()': "policy/*.json",
            '(Path("./policy") / f"{sys.argv[1]}.json").read_text()': "policy/*.json",
        }
        for expression, glob in forms.items():
            with self.subTest(expression=expression):
                derived = self.derive_read('import sys\nfrom pathlib import Path\nfrom os.path import join\n'
                                           'import os.path as osp\n' + expression + '\n')
                self.assertEqual(derived.globs, {glob: "ci_read"})
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.unclassified, [])
                reported = self.inventory(derived)
                self.assertEqual(reported.rule("policy/added.json"), "ci_read")
                self.assertIsNone(reported.rule("other/added.json"))
        derived = self.derive_read('import sys\nopen(f"../policy/{sys.argv[1]}.json").read()\n')
        self.assertEqual(derived.globs, {})
        self.assertEqual(derived.unresolved, [])
        self.assertEqual(derived.unclassified, ["scripts/check.py:2"])

    def test_received_literal_inventory_survives_opaque_and_unknown_bases(self):
        for base in ('os.environ["ROOT"]', 'os.getenv("ROOT")', 'Path.cwd()', 'get_base()', 'UNKNOWN_BASE'):
            for expression in (f'(Path({base}) / "policy" / "received.json").read_text()',
                               f'Path({base}, "policy", "received.json").read_text()',
                               f'open(os.path.join({base}, "policy", "received.json")).read()'):
                with self.subTest(expression=expression):
                    derived = self.derive_read('import os\nfrom pathlib import Path\n' + expression + '\n')
                    self.assertEqual(derived.files.get("policy/received.json"), "ci_read")
                    self.assertEqual(derived.unresolved, [])
                    self.assertEqual(derived.unclassified, ["scripts/check.py:3"])

    def test_collapsed_execution_keeps_the_legacy_literal_tail(self):
        source = ('import os, sys, subprocess\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n'
                  + ''.join(f'target = f"{{ROOT}}/scripts/check{i}-{{os.environ[\"CHECK\"]}}.py"\n'
                            for i in range(33))
                  + 'subprocess.run([sys.executable, target])\n')
        reader = self.gr.GateReads("scripts/check.py", source)
        self.assertEqual(reader.module_value("target")[0].tail, "literal")
        self.assertEqual(self.derive_read(source).unresolved, ["scripts/check.py:37"])

    def test_embedded_unknown_root_reads_keep_all_legacy_locations(self):
        source = ('from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n'
                  'def read():\n    return Path(\n        ROOT / TARGET\n    ).read_text()\n')
        self.assertEqual(self.derive_read(source).unresolved, ["scripts/check.py:4", "scripts/check.py:5"])

    def test_with_suffix_and_stem_narrow_exact_reads_but_keep_execution_diagnostics(self):
        for method, argument, result in (("with_suffix", ".json", "policy/check.json"),
                                          ("with_stem", "rules", "policy/rules.py")):
            with self.subTest(method=method):
                derived = self.derive_read('from pathlib import Path\n'
                                           f'Path("policy/check.py").{method}("{argument}").read_text()\n')
                self.assertEqual(derived.globs, {})
                reported = self.inventory(derived)
                self.assertEqual(reported.rule(result), "ci_read")
                self.assertIsNone(reported.rule("policy/check_extra.py"))
                executed = self.derive_read('import subprocess\nfrom pathlib import Path\n'
                                            f'subprocess.run([Path(__file__).{method}("{argument}")])\n')
                self.assertEqual(executed.unresolved, ["scripts/check.py:3"])

    def test_opaque_bases_joined_with_a_fixed_tail_are_unclassified(self):
        for expression in ('(Path(os.environ["POLICY_ROOT"]) / "rules.json").read_text()',
                           'open(os.path.join(os.getenv("POLICY_ROOT"), "rules.json")).read()',
                           'open(os.path.join(get_base(), "rules.json")).read()',
                           'open(f"{os.environ[\'POLICY_ROOT\']}/rules.json").read()'):
            with self.subTest(expression=expression):
                derived = self.derive_read('import os\nfrom pathlib import Path\n' + expression + '\n')
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.unclassified, ["scripts/check.py:3"])

    def test_computed_read_without_a_fixed_directory_is_unclassified(self):
        for expression in ('open(f"{sys.argv[1]}.json").read()',
                           'open(os.path.join(get_base(), sys.argv[1])).read()',
                           'Path(get_base(), sys.argv[1]).read_text()',
                           'open(os.environ["PATH_TEMPLATE"] % sys.argv[1]).read()',
                           'open(os.environ["PATH_TEMPLATE"].format(sys.argv[1])).read()',
                           'Path(os.environ["PATH_TEMPLATE"].format(sys.argv[1])).read_text()',
                           'open(get_base() / sys.argv[1]).read()'):
            with self.subTest(expression=expression):
                derived = self.derive_read('import os, sys\nfrom pathlib import Path\n' + expression + '\n')
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.unclassified, ["scripts/check.py:3"])

    def test_whole_runtime_subjects_keep_their_selector_reported(self):
        for source in ('import sys\nfrom pathlib import Path\nPath(sys.argv[1]).read_text()\n',
                       'import sys\nopen(sys.stdin.readline().strip()).read()\n',
                       'from pathlib import Path\nname = Path("policy/selector.txt").read_text().strip()\n'
                       'open(name).read()\n'):
            with self.subTest(source=source):
                derived = self.derive_read(source)
                self.assertEqual(derived.unresolved, [])
                self.assertEqual(derived.globs, {})
                self.assertIsNone(self.inventory(derived).rule("policy/strict.json"))
                if "selector.txt" in source:
                    self.assertEqual(derived.files.get("policy/selector.txt"), "ci_read")

    def test_every_read_form_resolves_to_repository_paths(self):
        tracked = {"policy/contract/contract.schema.json", "policy/rules.toml", "policy/ci.yaml", "policy/rows.csv",
                   "policy/limits-strict.json", "policy/checks/one.json", "policy/sets/a.json", "policy/pair/one.json",
                   "policy/pair/two.json", "policy/table/alpha.json", "policy/table/beta.json", "policy/target.json",
                   "docs/guide.md"}
        files, prefixes, globs, unresolved = self.reads(READ_FORMS, tracked)
        self.assertEqual(files, {
            "scripts/check.py",  # Path(__file__) itself
            "policy/contract/contract.schema.json",  # a module constant joined in a function, read by a helper
            "policy/rules.toml",  # open() and tomllib.load
            "policy/ci.yaml",  # Path.read_text and yaml.safe_load
            "policy/rows.csv",  # os.path.join over os.path.dirname(__file__) and "..", then csv.reader
            "scripts/local.json",  # Path(__file__).parent; untracked, so an agent could add it
            "policy/pair/one.json", "policy/pair/two.json",  # a loop over a literal tuple
            "policy/table/alpha.json", "policy/table/beta.json",  # destructured from a constant table
            "policy/augmented.json",  # `/=`
            "policy/received.json",  # literals under a received base, read as repository-relative
            "policy/target.json",  # a path literal
        })
        self.assertEqual(prefixes, {"policy/sets"})  # iterdir: the whole directory
        self.assertEqual(globs, {"policy/limits-*.json", "policy/checks/*.json"})  # the f-string and glob shapes
        # The file rules["subjects"] selects (docs/guide.md) is the check's subject and stays editable;
        # policy/rules.toml, which selects it, is reported above. So is a parameter, also after
        # `rel = os.path.normpath(rel)`. The name bound through globals() cannot be resolved, so the
        # gate reports this reader diagnostic without refusing the commit.
        line = READ_FORMS.splitlines().index("    return (REPO / TARGET).read_text()  # noqa: F821") + 1
        self.assertEqual(unresolved, {f"scripts/check.py:{line}"})

    def test_the_derivation_follows_imported_constants_and_script_text(self):
        derived = self.derive(READS_FILES)
        self.assertEqual(derived.unresolved, [])
        expected = {"policy/contract/contract.schema.json": "ci_read", "policy/rules.toml": "ci_read",
                    "policy/ci.yaml": "ci_read", "policy/shell.txt": "ci_read", "scripts/read_policy.py": "ci_read",
                    "scripts/inner_check.py": "ci_read", "policy/inner.json": "ci_read",
                    # The workflow script read as data is reported; the check run through a wrapper is
                    # followed, so what it reads is reported too.
                    "scripts/install_lanes.py": "ci_read", "tools/lane.js": "ci_read",
                    "scripts/lane_check.py": "ci_read", "policy/lane.json": "ci_read",
                    # A module imported lazily from the directory a gate script puts on sys.path is gate
                    # code, so the data it reads is reported.
                    "tools/lib/lane_rules.py": "ci_import", "policy/lane_rules.json": "ci_read"}
        for path, rule in expected.items():
            with self.subTest(path=path):
                self.assertEqual(derived.files.get(path), rule)
        enforced = self.g.derive_ci_protected(self.g.patch_policy.MemoryTree({**GATE_FILES, **READS_FILES}))
        for path, rule in (("scripts/read_policy.py", "ci_named"), ("scripts/check_shell.sh", "ci_named"),
                           ("scripts/gate_paths.py", "ci_import"), ("scripts/install_lanes.py", "ci_named")):
            self.assertEqual(self.g.Protected([enforced], set()).rule(path), rule)
        self.assertIsNone(self.g.Protected([enforced.advisory], set()).rule("policy/inner.json"))
        self.assertEqual(derived.syspath, {"tools/lib"})
        self.assertEqual(derived.globs, {"policy/limits-*.json": "ci_read", "policy/checks/*.json": "ci_read"})
        reported = self.inventory(derived)
        # src/app.py and docs/a.md are only named in the text of tools/lane.js, which no gate code runs.
        for path, rule in (("policy/checks/added.json", "ci_read"), ("policy/limits-lax.json", "ci_read"),
                           ("docs/guide.md", None), ("src/app.py", None), ("docs/a.md", None)):
            with self.subTest(path=path):
                self.assertEqual(reported.rule(path), rule)

    def test_only_code_a_gate_script_runs_is_followed(self):
        # Merge round of 2026-10-04: main's #679 made tools/adoption/install_claude_profile.py read
        # three examples/claude-native/workflows/*.js files to hash and copy them. Following every
        # code file gate code reads took the names in their text, so all of blueprints/ became
        # reported. A code file is followed only when a call that executes code receives it.
        tracked = {"scripts/direct.py", "scripts/direct.sh", "scripts/wrapped.py", "tools/lane.mjs",
                   "scripts/helped.py", "scripts/run_path.py", "scripts/loaded.py", "scripts/compiled.py",
                   "tools/hashed.js", "tools/copied.js", "scripts/parsed.py", "scripts/helpers.py",
                   "scripts/argv.py", "scripts/bound.sh"}
        blobs = {"scripts/check.py", *tracked}
        dirs = self.g.patch_policy.parent_dirs(blobs)
        reader = self.gr.GateReads("scripts/check.py", EXEC_FORMS)
        executed, computed = reader.executed(blobs, dirs)
        self.assertEqual(executed, {
            "scripts/direct.py",  # subprocess.run with sys.executable
            "scripts/direct.sh",  # a path string in an argv list
            "scripts/argv.py",  # an argv list bound to a local name (acceptance probe of 2026-10-04)
            "scripts/bound.sh",  # an argv tuple bound to a module constant
            "scripts/wrapped.py",  # through a module-local wrapper function
            "tools/lane.mjs",  # through a method that passes its argv on
            "scripts/helped.py",  # a function imported from outside the standard library
            "scripts/run_path.py", "scripts/loaded.py",  # runpy.run_path, importlib's file loader
            "scripts/compiled.py",  # exec(compile(...)) of the file's text
        })
        line = EXEC_FORMS.splitlines().index(
            '    subprocess.run([sys.executable, str(ROOT / "scripts" / name)], check=True)') + 1
        self.assertEqual(computed, {f"scripts/check.py:{line}"})  # any file under scripts/ may run
        # Hashed, copied or parsed code is data: reported as a file, not followed.
        self.assertLessEqual({"tools/hashed.js", "tools/copied.js", "scripts/parsed.py"},
                             reader.reads(blobs, dirs)[0])

    def test_reads_the_reader_cannot_resolve_are_reported(self):
        self.assertEqual(self.derive(UNRESOLVED_FILES).unresolved, ["scripts/read_unknown.py:5"])
        # Without the helper module, the imported constant is unknown, so both reads built on it are
        # unresolved rather than taken as subjects.
        lines = READ_POLICY.splitlines()
        missing = {path: data for path, data in READS_FILES.items() if path != "scripts/gate_paths.py"}
        self.assertEqual(self.derive(missing).unresolved,
                         [f"scripts/read_policy.py:{lines.index('CONTRACT = REPO / CONTRACT_DIR') + 1}",
                          f"scripts/read_policy.py:"
                          f"{lines.index('    schema = read_json(CONTRACT / \"contract.schema.json\")') + 1}"])
        # A gate script this interpreter cannot parse is unresolved too, since CI's interpreter may be
        # newer and run it.
        broken = {**READS_FILES, "scripts/inner_check.py": "def check(:\n    pass\n"}
        self.assertEqual(self.g.derive_ci_protected(
            self.g.patch_policy.MemoryTree({**GATE_FILES, **broken})).unresolved, ["scripts/inner_check.py:0"])
        # A gate script that runs a file chosen at run time may run any file under the directory.
        chosen = INSTALL_LANES.replace('run_check(ROOT / "scripts" / "lane_check.py")',
                                       'run_check(ROOT / "scripts" / sys.argv[2])')
        line = chosen.splitlines().index('    run_check(ROOT / "scripts" / sys.argv[2])') + 1
        self.assertEqual(self.derive({**READS_FILES, "scripts/install_lanes.py": chosen}).unresolved,
                         [f"scripts/install_lanes.py:{line}"])


class RepositoryWorkflowTests(unittest.TestCase):
    """The gate's reader and derivation on this repository's own workflows."""

    @classmethod
    def setUpClass(cls):
        cls.g = load_gate(ROOT)
        cls.files = sorted((ROOT / ".github/workflows").glob("*.y*ml"))

    def test_no_workflow_interpolates_untrusted_event_text_into_a_run_or_script_step(self):
        # Brief item 3: PR text never reaches an executable step. The gate refuses such a
        # workflow (pr_text_interpolated) and zizmor's template-injection audit is the second check.
        self.assertTrue(self.files)
        for path in self.files:
            facts = self.g.scan_workflow(path.read_text(encoding="utf-8"))
            for text in [*facts.runs, *facts.scripts]:
                with self.subTest(workflow=path.name):
                    self.assertEqual(self.g.untrusted_interpolations(text), [])

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML is not installed for this interpreter")
    def test_the_reader_matches_pyyaml_on_every_workflow(self):
        import yaml

        def walk(node, found):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("run", "script") and isinstance(value, str):
                        found[key].append(value.strip())
                    elif key == "working-directory" and isinstance(value, str):
                        found["working-directory"].append(value.strip())
                    elif key == "uses" and isinstance(value, str) and value.startswith("./"):
                        found["uses"].append(value.strip())
                    walk(value, found)
            elif isinstance(node, list):
                for value in node:
                    walk(value, found)

        for path in self.files:
            text = path.read_text(encoding="utf-8")
            expected = {"run": [], "script": [], "working-directory": [], "uses": []}
            data = yaml.safe_load(text)
            walk(data, expected)
            facts = self.g.scan_workflow(text)
            with self.subTest(workflow=path.name):
                self.assertEqual(sorted(text.strip() for text in facts.runs), sorted(expected["run"]))
                self.assertEqual(sorted(text.strip() for text in facts.scripts), sorted(expected["script"]))
                self.assertEqual(sorted(facts.working_dirs), sorted(expected["working-directory"]))
                self.assertEqual(sorted(facts.local_uses), sorted(expected["uses"]))
                triggers = data.get(True, data.get("on"))
                self.assertEqual(facts.triggers, frozenset(triggers) if isinstance(triggers, (dict, list))
                                 else frozenset([triggers]))

    @classmethod
    def derived(cls):
        """This checkout's HEAD tree and its derivation, computed once for the class."""
        if not hasattr(cls, "_derived"):
            tree = cls.g.patch_policy.GitTree(ROOT, "HEAD", git=REAL_GIT)
            cls._derived = (tree, cls.g.derive_ci_protected(tree))
        return cls._derived

    def test_the_derivation_protects_the_ci_gate_files(self):
        tree, derived = self.derived()
        protected = self.g.Protected([derived], self.g.policy_tests(tree))
        self.assertEqual(derived.interpolations, [])
        expected = {"scripts/validate.py": "ci_named", ".gitleaks.toml": "ci_named",
                    "tests/test_workflow_hardening.py": "workflow_policy_test",
                    # The merged workflow set names tests/: both b8eb9352b and the new reader
                    # give the stronger ci_named rule in place of ci_discovered on this tree.
                    "tests/test_brand_new_module.py": "ci_named", ".github/workflows/validate.yml": "github",
                    "CODEOWNERS": "codeowners", f"{RESOLVER}/push_gate.py": "gate_code",
                    f"{RESOLVER}/gate_reads.py": "gate_code",
                    "blueprints/runtime-workers/openhands/resolver.py": "gate_code",
                    # Cross-family review P1 of 2026-10-04: scripts/validate_convergence.py reads this
                    # schema as read_json(CONTRACT / "contract.schema.json").
                    "blueprints/convergence-practice/contract.schema.json": "ci_read",
                    # Acceptance probe of 2026-10-04 on 7c1d24cc5: validate.yml runs
                    # scripts/verdict_review_gate.py, which puts tools/sota-convergence on sys.path and
                    # imports record_verdicts; that imports export_isolation_check lazily, which imports
                    # blind_checkout, and blind_checkout reads this label file.
                    "catalogs/foundation/automation.json": "ci_read",
                    "blueprints/runtime-workers/openhands/README.md": None}
        for path, rule in expected.items():
            with self.subTest(path=path):
                if rule == "ci_read":
                    self.assertIsNone(protected.rule(path))
                    self.assertIn(path, derived.advisory.files)
                else:
                    self.assertEqual(protected.rule(path), rule)
        # A file a step only lists as a `case` pattern (adoption-bootstrap.yml's `changes` step and its
        # MACOS_PATTERNS globs, main e0c329ae9) adds no explicit workflow category. Read-derived
        # execution and sys.path inventories remain advisory even when those paths also occur here.
        self.assertIsNone(derived.files.get("scripts/credential_boot_receipt.py"))
        self.assertEqual(derived.prefixes.get("tools/sota-convergence"), "ci_import")
        # The schedule-only workflow's script is not reachable from a push or its PR.
        self.assertNotIn(".github/workflows/practice-references-freshness.yml", derived.workflows)
        self.assertIn(".github/workflows/validate.yml", derived.workflows)

    def test_advisory_baseline_and_explicit_categories_stay_bounded_on_this_repository(self):
        # The monitoring baseline is stable under line-only changes. It is neither a
        # complete read inventory nor an enforcement/enablement requirement.
        tree, derived = self.derived()
        advisory = derived.advisory
        print(json.dumps({"advisory_gate_reads": self.g.advisory_gate_reads([derived])}, sort_keys=True))
        baseline = json.loads((ROOT / "blueprints/runtime-workers/openhands/evidence/"
                               "unclassified-gate-reads-20261004.json").read_text())
        def scripts(locations):
            return Counter(location.rsplit(":", 1)[0] for location in locations)

        def shapes_by_script(shapes):
            return Counter((location.rsplit(":", 1)[0], tuple(values)) for location, values in shapes.items())

        self.assertEqual(scripts(advisory.unclassified), scripts(baseline["unclassified"]))
        self.assertEqual(shapes_by_script(advisory.unclassified_shapes),
                         shapes_by_script(baseline["unclassified_shapes"]))
        self.assertEqual(len(advisory.unclassified), baseline["count"])
        self.assertNotIn("", derived.prefixes)
        self.assertTrue(all(self.g.gate_reads.static_dir(pattern) for pattern in derived.globs), derived.globs)
        protected = self.g.Protected([derived], self.g.policy_tests(tree))
        blobs = [path for path, entry in tree.entries().items() if entry[1] == "blob"]
        working = [path for path in blobs if not path.startswith(("evidence/", "tests/", ".github/"))]
        covered = [path for path in working if protected.rule(path)]
        self.assertLessEqual(len(covered), len(working) // 4, f"{len(covered)} of {len(working)}")
        # The resolver's main working area stays editable, apart from the gate's own code.
        blueprints = [path for path in working
                      if path.startswith("blueprints/") and protected.rule(path) != "gate_code"]
        covered = [path for path in blueprints if protected.rule(path)]
        self.assertLessEqual(len(covered), len(blueprints) // 50, sorted(covered))
        self.assertEqual(derived.unresolved, [])


class PushGateTests(unittest.TestCase):
    """PushGate.check on planted agent commits in fixture clones (local git, fake zizmor)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="push-gate-")).resolve()
        cls.fixture = GateFixture(cls.tmp / "shared")
        cls.module = load_gate(cls.fixture.trusted)
        cls.zizmor, cls.zizmor_log = fake_zizmor(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gate(self, zizmor=None, module=None):
        return (module or self.module).PushGate(git=REAL_GIT, zizmor=self.zizmor if zizmor is None else zizmor)

    def check(self, edits, *, fixture=None, gate=None, commits=1, base=None):
        fixture = fixture or self.fixture
        clone, head = fixture.agent_commit(edits, commits=commits)
        return (gate or self.gate()).check(str(clone), base=base or fixture.base, head=head), head

    def test_a_benign_commit_passes_and_records_the_trusted_commit(self):
        record, head = self.check({"docs/a.md": "a\nmore\n"})
        trusted = run_git(self.fixture.trusted, "rev-parse", "HEAD").stdout.decode().strip()
        self.assertEqual((record["status"], record["reasons"], record["paths"]), ("pass", [], []), record)
        self.assertEqual((record["commit"], record["base"], record["trusted_commit"]), (head, self.fixture.base, trusted))
        self.assertEqual(record["zizmor"], {"version": PIN, "findings": 0, "failing": []})
        self.assertEqual(record["protected"]["workflows"], 2)  # ci.yml and its local action

    def test_protected_changes_are_refused_with_their_rule(self):
        cases = {
            ".github/workflows/ci.yml": ({".github/workflows/ci.yml": CI_WORKFLOW + "# edited\n"}, "github"),
            ".github/actions/new/action.yml": ({".github/actions/new/action.yml": CI_ACTION}, "github"),
            "CODEOWNERS": ({"CODEOWNERS": "* @someone-else\n"}, "codeowners"),
            "docs/CODEOWNERS": ({"docs/CODEOWNERS": None}, "codeowners"),
            "src/CODEOWNERS": ({"src/CODEOWNERS": "* @someone-else\n"}, "codeowners"),
            "scripts/check_gate.py": ({"scripts/check_gate.py": "print('weakened')\n"}, "ci_named"),
            "policy/gate.toml": ({"policy/gate.toml": "strict = false\n"}, "ci_named"),
            "scripts/gate_helpers.py": ({"scripts/gate_helpers.py": "VALUE = 0\n"}, "ci_import"),
            "tools/ci-action/action.yml": ({"tools/ci-action/action.yml": CI_ACTION + "# edited\n"},
                                           "ci_local_action"),
            "tools/ci-action/run.sh": ({"tools/ci-action/run.sh": "exit 0\n"}, "ci_named"),
            "tests/test_policy.py": ({"tests/test_policy.py": "WORKFLOWS = '.github'\nSKIP = True\n"},
                                     "workflow_policy_test"),
            "tests/test_added.py": ({"tests/test_added.py": "import os\n"}, "ci_discovered"),
            "tests/helpers.py": ({"tests/helpers.py": "x = 1\n"}, "ci_discovered"),
            f"{RESOLVER}/push_gate.py": ({f"{RESOLVER}/push_gate.py": "# replaced\n"}, "gate_code"),
        }
        for name, (edits, rule) in cases.items():
            with self.subTest(path=name):
                record, _ = self.check(edits)
                self.assertEqual(record["status"], "fail")
                self.assertIn("protected_path", record["reasons"])
                self.assertIn({"path": name, "rule": rule, "known": name in GATE_FILES or name in ENFORCING},
                              record["paths"])

    def test_paths_no_reachable_workflow_executes_pass(self):
        for name in ("scripts/nightly_only.py", "scripts/commented_only.py", "src/app.py"):
            with self.subTest(path=name):
                record, _ = self.check({name: "print('changed')\n"})
                self.assertEqual((record["status"], record["reasons"]), ("pass", []), record)

    def filter_fixture(self, step):
        listed = {"scripts/listed_only.py": ("import sys\nfrom pathlib import Path\n\n"
                                             "sys.path.insert(0, str(Path(__file__).resolve().parent))\n"),
                  "scripts/neighbour.py": "VALUE = 2\n", "tools/listed/run.py": "print('listed')\n"}
        fixture = GateFixture(self.tmp / f"filter-{secrets.token_hex(3)}",
                              {".github/workflows/ci.yml": CI_WORKFLOW + step, **listed})
        return fixture, self.gate(module=load_gate(fixture.trusted))

    def test_paths_a_step_only_lists_as_case_patterns_stay_editable(self):
        fixture, gate = self.filter_fixture(FILTER_STEP)
        for name in ("scripts/listed_only.py", "scripts/neighbour.py", "tools/listed/run.py"):
            with self.subTest(path=name):
                record, _ = self.check({name: "print('changed')\n"}, fixture=fixture, gate=gate)
                self.assertEqual((record["status"], record["reasons"]), ("pass", []), record)
        # The step's real gate script stays protected beside the list.
        record, _ = self.check({"scripts/check_gate.py": "print('weakened')\n"}, fixture=fixture, gate=gate)
        self.assertIn({"path": "scripts/check_gate.py", "rule": "ci_named", "known": True}, record["paths"])

    def test_a_list_the_step_also_runs_stays_protected(self):
        loop = '          for pattern in "${PATTERNS[@]}"; do\n'
        runs = FILTER_STEP.replace(loop, loop + '            python3 "$pattern"\n', 1)
        fixture, gate = self.filter_fixture(runs)
        for name, rule in (("scripts/listed_only.py", "ci_named"), ("scripts/neighbour.py", "ci_import")):
            with self.subTest(path=name):
                record, _ = self.check({name: "print('changed')\n"}, fixture=fixture, gate=gate)
                self.assertEqual((record["status"], record["reasons"]), ("fail", ["protected_path"]))
                self.assertIn({"path": name, "rule": rule, "known": True}, record["paths"])

    def test_zizmor_audits_exactly_the_commits_workflows_and_actions_with_the_trusted_flags(self):
        zizmor, log = fake_zizmor(self.tmp)
        record, _ = self.check({"tools/extra/action.yml": CI_ACTION}, gate=self.gate(zizmor))
        self.assertEqual(record["status"], "pass", record)
        version, audit = zizmor_calls(log)
        self.assertEqual(version["argv"], ["--version"])
        self.assertEqual(audit["argv"], ["--no-config", "--no-ignores", "--persona", "regular", "--strict-collection",
                                         "--offline", "--collect=all", "--no-exit-codes", "--format", "json", "."])
        self.assertEqual(audit["inputs"], [".github/requirements-ci.txt", ".github/workflows/ci.yml",
                                           ".github/workflows/nightly.yml", "tools/ci-action/action.yml",
                                           "tools/extra/action.yml"])
        self.assertFalse({"GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN"} & set(audit["env"]))

    def test_zizmor_findings_fail_the_gate_only_for_the_five_audits(self):
        for ident in ("excessive-permissions", "dangerous-triggers", "cache-poisoning", "artipacked",
                      "template-injection"):
            with self.subTest(ident=ident):
                zizmor, _ = fake_zizmor(self.tmp, output=json.dumps([finding(ident, "tools/extra/action.yml")]))
                record, _ = self.check({"tools/extra/action.yml": CI_ACTION}, gate=self.gate(zizmor))
                self.assertEqual((record["status"], record["reasons"]), ("fail", ["zizmor_finding"]))
                self.assertEqual(record["zizmor"]["failing"], [ident])
                self.assertIn({"path": "tools/extra/action.yml", "rule": "zizmor_finding", "known": False},
                              record["paths"])
        zizmor, _ = fake_zizmor(self.tmp, output=json.dumps([finding("unpinned-uses", ".github/workflows/ci.yml")]))
        record, _ = self.check({"docs/a.md": "b\n"}, gate=self.gate(zizmor))
        self.assertEqual((record["status"], record["zizmor"]["findings"], record["zizmor"]["failing"]), ("pass", 1, []))

    def test_an_unavailable_or_wrong_zizmor_fails_closed(self):
        missing = str(self.tmp / "no-such-zizmor")
        wrong, _ = fake_zizmor(self.tmp, version="zizmor 1.29.0\n")
        garbled, _ = fake_zizmor(self.tmp, version="not zizmor\n")
        crashing, _ = fake_zizmor(self.tmp, code=1)
        invalid, _ = fake_zizmor(self.tmp, output="{not json")
        cases = {missing: "zizmor_unavailable", "": "zizmor_unavailable", "relative/zizmor": "zizmor_unavailable",
                 garbled: "zizmor_unavailable", wrong: "zizmor_version_mismatch", crashing: "zizmor_failed",
                 invalid: "zizmor_output_invalid"}
        for zizmor, reason in cases.items():
            with self.subTest(reason=reason, zizmor=Path(zizmor).name):
                record, _ = self.check({"docs/a.md": "b\n"}, gate=self.gate(zizmor))
                self.assertEqual((record["status"], record["reasons"]), ("fail", [reason]))
        record, _ = self.check({"docs/a.md": "b\n"}, gate=self.module.PushGate(git=REAL_GIT, zizmor=None))
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["zizmor_unavailable"]))

    def test_the_gate_refuses_to_run_from_inside_the_agent_tree(self):
        clone, head = self.fixture.agent_commit({"docs/a.md": "b\n"})
        planted = load_gate(clone)  # the agent clone carries a copy of the gate at the same path
        zizmor, log = fake_zizmor(self.tmp)
        record = planted.PushGate(git=REAL_GIT, zizmor=zizmor).check(str(clone), base=self.fixture.base, head=head)
        self.assertEqual((record["status"], record["reasons"], record["trusted_commit"]),
                         ("fail", ["gate_inside_agent_tree"], None))
        self.assertEqual(zizmor_calls(log), [])
        # The trusted gate refuses too when the result directory holding the clone also holds it.
        record = self.gate().check(str(clone), base=self.fixture.base, head=head,
                                   agent_trees=(str(self.fixture.root),))
        self.assertEqual(record["reasons"], ["gate_inside_agent_tree"])
        # So does a tool that lies inside an agent tree.
        inside = clone / "zizmor"
        shutil.copy(zizmor, inside)
        record = self.gate(str(inside)).check(str(clone), base=self.fixture.base, head=head)
        self.assertEqual(record["reasons"], ["tool_inside_agent_tree"])

    def test_a_gate_file_that_differs_from_the_trusted_commit_refuses(self):
        for rel in ENFORCING:
            with self.subTest(path=rel):
                fixture = GateFixture(self.tmp / f"modified-{secrets.token_hex(3)}")
                with open(fixture.trusted / rel, "a", encoding="utf-8") as handle:
                    handle.write("# an uncommitted local change\n")
                record, _ = self.check({"docs/a.md": "b\n"}, fixture=fixture,
                                       gate=self.gate(module=load_gate(fixture.trusted)))
                self.assertEqual((record["status"], record["reasons"]), ("fail", ["gate_file_modified"]))

    def test_a_trusted_checkout_off_main_refuses(self):
        fixture = GateFixture(self.tmp / f"offmain-{secrets.token_hex(3)}")
        write_file(fixture.trusted, "docs/local.md", "local\n")
        commit_all(fixture.trusted, "local commit, never on main")
        record, _ = self.check({"docs/a.md": "b\n"}, fixture=fixture, gate=self.gate(module=load_gate(fixture.trusted)))
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["trusted_copy_not_on_main"]))

    def test_a_stale_trusted_gate_refuses_when_main_changed_the_gate(self):
        fixture = GateFixture(self.tmp / f"stale-{secrets.token_hex(3)}")
        stale = load_gate(fixture.trusted)
        newer = fixture.advance({ENFORCING[1]: (ROOT / ENFORCING[1]).read_text(encoding="utf-8") + "# reviewed\n"})
        clone, head = fixture.agent_commit({"docs/a.md": "b\n"})
        record = self.gate(module=stale).check(str(clone), base=newer, head=head)
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["gate_differs_from_base"]))

    def test_a_trusted_root_that_is_no_checkout_refuses(self):
        plain = self.tmp / f"plain-{secrets.token_hex(3)}"
        for rel in ENFORCING:
            write_file(plain, rel, (ROOT / rel).read_bytes())
        clone, head = self.fixture.agent_commit({"docs/a.md": "b\n"})
        record = load_gate(plain).PushGate(git=REAL_GIT, zizmor=self.zizmor).check(str(clone), base=self.fixture.base,
                                                                                   head=head)
        self.assertEqual(record["status"], "fail")
        self.assertIn(record["reasons"][0], {"trusted_root_not_a_checkout", "gate_file_modified"})

    def test_the_commit_must_be_the_single_child_of_its_base(self):
        record, _ = self.check({"docs/a.md": "b\n"}, commits=2)
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["commit_not_single_child_of_base"]))

    def test_untrusted_interpolation_in_a_reachable_workflow_refuses_every_commit(self):
        injected = CI_WORKFLOW.replace("run: python3 -m unittest\n",
                                       "run: echo \"${{ github.event.pull_request.title }}\"\n")
        fixture = GateFixture(self.tmp / f"inject-{secrets.token_hex(3)}", {".github/workflows/ci.yml": injected})
        record, _ = self.check({"docs/a.md": "b\n"}, fixture=fixture, gate=self.gate(module=load_gate(fixture.trusted)))
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["pr_text_interpolated"]))
        self.assertIn({"path": ".github/workflows/ci.yml", "rule": "pr_text_interpolation", "known": True},
                      record["paths"])

    def test_a_workflow_the_reader_cannot_read_fails_closed(self):
        unreadable = CI_WORKFLOW.replace("      - uses: ./tools/ci-action\n", "      - {run: python3 x.py}\n")
        fixture = GateFixture(self.tmp / f"unread-{secrets.token_hex(3)}", {".github/workflows/ci.yml": unreadable})
        record, _ = self.check({"docs/a.md": "b\n"}, fixture=fixture, gate=self.gate(module=load_gate(fixture.trusted)))
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["workflow_unsupported_yaml"]))

    def test_invalid_arguments_refuse(self):
        clone, head = self.fixture.agent_commit({"docs/a.md": "b\n"})
        for kwargs in ({"base": "HEAD", "head": head}, {"base": self.fixture.base, "head": "x" * 40}):
            with self.subTest(kwargs=kwargs):
                record = self.gate().check(str(clone), **kwargs)
                self.assertEqual(record["reasons"], ["invalid_arguments"])
        self.assertEqual(self.gate().check("relative", base=self.fixture.base, head=head)["reasons"],
                         ["invalid_arguments"])

    @unittest.skipUnless(installed_zizmor(), f"zizmor {PIN} is not on PATH")
    def test_the_installed_pinned_zizmor_refuses_a_planted_template_injection(self):
        injected = CI_ACTION.replace("run: bash tools/ci-action/run.sh",
                                     "run: echo \"${{ github.event.pull_request.title }}\"")
        gate = self.gate(installed_zizmor())
        benign, _ = self.check({"docs/a.md": "b\n"}, gate=gate)
        self.assertEqual((benign["status"], benign["zizmor"]["version"], benign["zizmor"]["failing"]),
                         ("pass", PIN, []), benign)
        record, _ = self.check({"tools/extra/action.yml": injected}, gate=gate)
        self.assertEqual((record["status"], record["reasons"], record["zizmor"]["failing"]),
                         ("fail", ["zizmor_finding"], ["template-injection"]), record)
        self.assertIn({"path": "tools/extra/action.yml", "rule": "zizmor_finding", "known": False}, record["paths"])


class GateDataReadTests(unittest.TestCase):
    """PushGate.check where the gate step reads policy data (cross-family review P1 of 2026-10-04)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="push-gate-reads-")).resolve()
        cls.fixture = GateFixture(cls.tmp / "reads", READS_FILES)
        cls.zizmor, _ = fake_zizmor(cls.tmp)
        cls.gate = load_gate(cls.fixture.trusted).PushGate(git=REAL_GIT, zizmor=cls.zizmor)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, edits, *, fixture=None, gate=None):
        fixture = fixture or self.fixture
        clone, head = fixture.agent_commit(edits)
        return (gate or self.gate).check(str(clone), base=fixture.base, head=head)

    def test_derived_reads_are_advisory_and_cannot_refuse(self):
        record = self.check({"policy/contract/contract.schema.json": "{}\n"})
        self.assertEqual((record["status"], record["reasons"], record["paths"]), ("pass", [], []))
        advisory = record["advisory_gate_reads"]
        self.assertEqual(advisory["mode"], "monitoring_only")
        self.assertIn("policy/contract/contract.schema.json", advisory["files"])
        self.assertIn("policy/limits-*.json", advisory["globs"])

    def test_unparseable_gate_scripts_still_refuse(self):
        files = {**UNRESOLVED_FILES, "scripts/read_unknown.py": "this is invalid Python!\n"}
        fixture = GateFixture(self.tmp / f"parse-{secrets.token_hex(3)}", files)
        gate = load_gate(fixture.trusted).PushGate(git=REAL_GIT, zizmor=self.zizmor)
        record = self.check({"docs/guide.md": "changed\n"}, fixture=fixture, gate=gate)
        self.assertEqual((record["status"], record["reasons"]), ("fail", ["gate_input_unresolved"]))
        self.assertEqual(record["unresolved"], ["scripts/read_unknown.py:0"])

    def test_data_a_gate_script_reads_is_advisory(self):
        cases = {
            "policy/contract/contract.schema.json": '{"type": "object"}\n',  # the requirement dropped
            "policy/rules.toml": 'tier = "lax"\nsubjects = []\n',
            "policy/ci.yaml": "checks: []\n",
            "policy/limits-strict.json": '{"max": 0}\n',
            "policy/limits-lax.json": "{}\n",  # a new file the f-string can select
            "policy/checks/one.json": '{"skip": true}\n',
            "policy/checks/added.json": "{}\n",  # a new file the glob reads
            "policy/shell.txt": "lax\n",  # named by the shell script the step runs
            "policy/inner.json": '{"skip": true}\n',  # read by a script that script runs
            "tools/lane.js": "// replaced\n",  # read as data: hashed and copied
            "policy/lane.json": '{"skip": true}\n',  # read by a script a gate script runs through a wrapper
            "policy/lane_rules.json": '{"skip": true}\n',  # read by a module imported through sys.path
        }
        for name, data in cases.items():
            with self.subTest(path=name):
                record = self.check({name: data})
                self.assertEqual((record["status"], record["reasons"]), ("pass", []), record)
                self.assertEqual(record["paths"], [])
                inventory = record["advisory_gate_reads"]
                self.assertTrue(name in inventory["files"] or
                                any(name.startswith(prefix + "/") for prefix in inventory["prefixes"]) or
                                any(fnmatch.fnmatchcase(name, pattern) for pattern in inventory["globs"]), name)

    def test_the_files_the_data_selects_and_unrelated_files_stay_editable(self):
        # docs/guide.md is the subject policy/rules.toml selects: the check reads it to judge it, so it
        # stays editable while the selecting file is reported. src/app.py and docs/a.md are only
        # named in tools/lane.js, which gate code reads as data and never runs.
        for name in ("docs/guide.md", "src/app.py", "docs/a.md"):
            with self.subTest(path=name):
                record = self.check({name: "changed\n"})
                self.assertEqual((record["status"], record["reasons"], record["paths"]), ("pass", [], []), record)
                self.assertEqual(record["protected"]["globs"], 0)
                self.assertEqual(record["advisory_gate_reads"]["globs_count"], 2)

    def test_unresolved_reads_are_advisory_and_do_not_refuse(self):
        fixture = GateFixture(self.tmp / f"unresolved-{secrets.token_hex(3)}", UNRESOLVED_FILES)
        gate = load_gate(fixture.trusted).PushGate(git=REAL_GIT, zizmor=self.zizmor)
        record = self.check({"docs/guide.md": "changed\n"}, fixture=fixture, gate=gate)
        self.assertEqual((record["status"], record["reasons"]), ("pass", []), record)
        self.assertEqual(record["advisory_gate_reads"]["unresolved"], ["scripts/read_unknown.py:5"])
        self.assertEqual(record["paths"], [])

    def test_environment_base_is_reported_without_refusing_commit(self):
        files = {
            ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
            "scripts/check.py": 'import os\nopen(os.path.join(os.environ["POLICY_ROOT"], "rules.json")).read()\n',
        }
        fixture = GateFixture(self.tmp / f"environment-{secrets.token_hex(3)}", files)
        gate = load_gate(fixture.trusted).PushGate(git=REAL_GIT, zizmor=self.zizmor)
        record = self.check({"docs/guide.md": "changed\n"}, fixture=fixture, gate=gate)
        self.assertEqual((record["status"], record["reasons"], record["paths"]), ("pass", [], []), record)
        self.assertEqual(record["advisory_gate_reads"]["unclassified"], ["scripts/check.py:2"])
        self.assertEqual(record["advisory_gate_reads"]["unclassified_count"], 1)

    def test_computed_execution_is_advisory(self):
        for piece in ('os.environ["CHECK"]', 'get_check()'):
            for path in (f'f"{{ROOT}}/scripts/{{{piece}}}.py"', f'ROOT + "/scripts/" + {piece} + ".py"'):
                with self.subTest(path=path):
                    files = {
                        ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
                        "scripts/check.py": ('import os, sys, subprocess\nfrom pathlib import Path\n'
                                             'ROOT = Path(__file__).resolve().parents[1]\n'
                                             f'subprocess.run([sys.executable, {path}])\n'),
                    }
                    fixture = GateFixture(self.tmp / f"execute-{secrets.token_hex(3)}", files)
                    gate = load_gate(fixture.trusted).PushGate(git=REAL_GIT, zizmor=self.zizmor)
                    record = self.check({"docs/guide.md": "changed\n"}, fixture=fixture, gate=gate)
                    self.assertEqual((record["status"], record["reasons"]), ("pass", []))
                    self.assertEqual(record["advisory_gate_reads"]["unresolved"], ["scripts/check.py:4"])
                    self.assertEqual(record["paths"], [])

    def test_received_literal_edits_are_advisory_under_opaque_bases(self):
        for base in ('os.environ["ROOT"]', 'os.getenv("ROOT")', 'Path.cwd()', 'get_base()'):
            for path in (f'Path({base}) / "policy" / "received.json"',
                         f'Path({base}, "policy", "received.json")',
                         f'os.path.join({base}, "policy", "received.json")'):
                with self.subTest(path=path):
                    files = {
                        ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
                        "scripts/check.py": ('import os\nfrom pathlib import Path\n' + f'open({path}).read()\n'),
                        "policy/received.json": "{}\n",
                    }
                    fixture = GateFixture(self.tmp / f"received-{secrets.token_hex(3)}", files)
                    gate = load_gate(fixture.trusted).PushGate(git=REAL_GIT, zizmor=self.zizmor)
                    record = self.check({"policy/received.json": "changed\n"}, fixture=fixture, gate=gate)
                    self.assertEqual((record["status"], record["reasons"]), ("pass", []))
                    self.assertEqual(record["paths"], [])
                    self.assertIn("policy/received.json", record["advisory_gate_reads"]["files"])
                    self.assertEqual(record["advisory_gate_reads"]["unclassified"], ["scripts/check.py:3"])

    def test_count_is_unknown_when_derivation_never_ran(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            record = self.gate.check("relative", base="a" * 40, head="b" * 40)
        self.assertEqual(record["reasons"], ["invalid_arguments"])
        self.assertIsNone(record["advisory_gate_reads"]["unclassified_count"])
        self.assertEqual(json.loads(output.getvalue()), {"advisory_gate_reads": record["advisory_gate_reads"]})
        [summary] = load_resolver()._recipe("receipt").push_gate_summary([record])
        self.assertIsNone(summary["advisory_gate_reads"]["unclassified_count"])
        self.assertEqual(summary["advisory_gate_reads"]["unclassified_omitted"], 0)

    def test_gate_prints_and_receipt_records_unclassified_reads(self):
        files = {
            ".github/workflows/ci.yml": CI_WORKFLOW + "      - run: python3 scripts/check.py\n",
            "scripts/check.py": ('import os, sys\n'
                                 'open(os.path.join(os.environ["POLICY_ROOT"], "rules.json")).read()\n'
                                 'open(f"{sys.argv[1]}.json").read()\n'),
        }
        fixture = GateFixture(self.tmp / f"visible-{secrets.token_hex(3)}", files)
        gate = load_gate(fixture.trusted).PushGate(git=REAL_GIT, zizmor=self.zizmor)
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            record = self.check({"docs/guide.md": "changed\n"}, fixture=fixture, gate=gate)
        self.assertEqual((record["status"], record["reasons"]), ("pass", []), record)
        expected = {"unclassified": ["scripts/check.py:2", "scripts/check.py:3"], "unclassified_count": 2,
                    "unclassified_shapes": {"scripts/check.py:3": ["*.json"]}}
        self.assertEqual(json.loads(output.getvalue())["advisory_gate_reads"], record["advisory_gate_reads"])
        [receipt] = load_resolver()._recipe("receipt").push_gate_summary([record])
        for key, value in expected.items():
            with self.subTest(field=key):
                self.assertEqual(receipt["advisory_gate_reads"][key], value)

        # The empty residual remains visible on a gate run with no unclassified input.
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            clean = self.check({"docs/guide.md": "changed\n"})
        empty = {"unclassified": [], "unclassified_count": 0, "unclassified_shapes": {}}
        self.assertEqual({key: json.loads(output.getvalue())["advisory_gate_reads"][key] for key in empty}, empty)
        self.assertEqual({key: clean["advisory_gate_reads"][key] for key in empty}, empty)


class HarnessPushGateTests(unittest.TestCase):
    """GhHarness.push and run with the trusted gate: refusals happen before any push argv."""

    @classmethod
    def setUpClass(cls):
        cls.r = load_resolver()
        cls.h = cls.r.gh_harness
        cls.tmp = Path(tempfile.mkdtemp(prefix="push-gate-harness-")).resolve()
        cls.fixture = GateFixture(cls.tmp / "shared")
        cls.module = load_gate(cls.fixture.trusted)
        cls.reads = GateFixture(cls.tmp / "reads", READS_FILES)
        cls.reads_module = load_gate(cls.reads.trusted)
        cls.zizmor, _ = fake_zizmor(cls.tmp)
        cls.tools = FakeTools(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def harness(self, calls, gate):
        def runner(args, **kwargs):
            argv = list(args[1:])
            calls.append(argv)
            if argv[-5:] == ["remote", "get-url", "--push", "--all", "origin"]:
                return subprocess.CompletedProcess(list(args), 0, ORIGIN + "\n", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        home = self.tmp / f"home-{secrets.token_hex(3)}"
        home.mkdir()
        return self.h.GhHarness(self.tools.gh, git=REAL_GIT, base_env=planted_base(home), runner=runner,
                                workdir=self.h.private_workdir(str(self.tmp)), push_gate=gate)

    def test_a_planted_workflow_commit_is_refused_before_any_push(self):
        clone, head = self.fixture.agent_commit({".github/workflows/ci.yml": CI_WORKFLOW + "# planted\n"})
        calls = []
        harness = self.harness(calls, self.module.PushGate(git=REAL_GIT, zizmor=self.zizmor))
        with self.assertRaises(self.h.HarnessRefused) as refused:
            harness.push(str(clone), "openhands/issue-12", base=self.fixture.base, head=head)
        self.assertEqual(refused.exception.reason, "push_gate_refused")
        self.assertFalse(any("push" in argv for argv in calls), calls)
        self.assertEqual(harness.writes, [])
        [record] = harness.gates
        self.assertEqual((record["status"], record["commit"], record["reasons"]), ("fail", head, ["protected_path"]))
        self.assertEqual(record["paths"], [{"path": ".github/workflows/ci.yml", "rule": "github", "known": True}])

    def test_a_schema_edit_is_advisory_and_does_not_block_the_mock_push(self):
        clone, head = self.reads.agent_commit({"policy/contract/contract.schema.json": '{"type": "object"}\n'})
        calls = []
        harness = self.harness(calls, self.reads_module.PushGate(git=REAL_GIT, zizmor=self.zizmor))
        harness.push(str(clone), "openhands/issue-12", base=self.reads.base, head=head)
        self.assertEqual(calls[-1][-1], f"{head}:refs/heads/openhands/issue-12")
        self.assertEqual(harness.writes, [{"op": "push", "exit_code": 0}])
        [record] = harness.gates
        self.assertEqual((record["status"], record["reasons"], record["paths"]), ("pass", [], []))
        self.assertIn("policy/contract/contract.schema.json", record["advisory_gate_reads"]["files"])

    def test_a_passing_commit_is_pushed_by_its_exact_name(self):
        clone, head = self.fixture.agent_commit({"docs/a.md": "b\n"})
        calls = []
        harness = self.harness(calls, self.module.PushGate(git=REAL_GIT, zizmor=self.zizmor))
        harness.push(str(clone), "openhands/issue-12", base=self.fixture.base, head=head)
        self.assertEqual(calls[-1][-1], f"{head}:refs/heads/openhands/issue-12")
        self.assertEqual(harness.writes, [{"op": "push", "exit_code": 0}])
        self.assertEqual([record["status"] for record in harness.gates], ["pass"])

    def test_the_harness_never_pushes_a_commit_the_gate_did_not_pass(self):
        clone, head = self.fixture.agent_commit({"docs/a.md": "b\n"})
        push = self.h.op_push(str(clone), "openhands/issue-12", head, gh=self.tools.gh)
        calls = []
        with self.assertRaises(self.h.HarnessRefused) as refused:
            self.harness(calls, self.module.PushGate(git=REAL_GIT, zizmor=self.zizmor)).run(push)
        self.assertEqual(refused.exception.reason, "push_not_gated")
        for call in (lambda harness: harness.run(push),
                     lambda harness: harness.push(str(clone), "openhands/issue-12", base=self.fixture.base, head=head)):
            with self.assertRaises(self.h.HarnessRefused) as refused:
                call(self.harness(calls, None))
            self.assertEqual(refused.exception.reason, "push_gate_missing")
        self.assertEqual(calls, [])

    def test_the_harness_refuses_a_gate_loaded_from_the_agent_tree(self):
        clone, head = self.fixture.agent_commit({"docs/a.md": "b\n"})
        planted = load_gate(clone)

        class Approving(planted.PushGate):
            """A gate class defined beside the planted module that would approve anything."""

            def check(self, *args, **kwargs):  # pragma: no cover - must never run
                raise AssertionError("the harness ran a gate from inside the agent tree")

        Approving.__module__ = planted.__name__
        calls = []
        harness = self.harness(calls, Approving(git=REAL_GIT, zizmor=self.zizmor))
        with self.assertRaises(self.h.HarnessRefused):
            harness.push(str(clone), "openhands/issue-12", base=self.fixture.base, head=head)
        self.assertEqual(harness.gates[0]["reasons"], ["gate_inside_agent_tree"])
        self.assertFalse(any("push" in argv for argv in calls))


class ReceiptProjectionTests(unittest.TestCase):
    """receipt.push_gate_summary: codes, hashes and counts; model-chosen paths are only counted."""

    @classmethod
    def setUpClass(cls):
        cls.receipt = load_resolver()._recipe("receipt")

    def test_only_known_repository_paths_and_codes_reach_the_receipt(self):
        record = {"commit": "c" * 40, "base": "a" * 40, "trusted_commit": "b" * 40, "status": "fail",
                  "reasons": ["protected_path", "zizmor_finding", "Not A Code", 7],
                  "paths": [{"path": "CODEOWNERS", "rule": "codeowners", "known": True},
                            {"path": ".github/workflows/new-name chosen by the model.yml", "rule": "github",
                             "known": False},
                            {"path": "../outside", "rule": "ci_named", "known": True},
                            {"path": "tests/x.py", "rule": "invented_rule", "known": True}],
                  "paths_omitted": 3,
                  "zizmor": {"version": PIN, "findings": 2, "failing": ["template-injection", "BAD IDENT"]}}
        [summary] = self.receipt.push_gate_summary([record, "not a record"])
        advisory = summary.pop("advisory_gate_reads")
        self.assertEqual(advisory["mode"], "monitoring_only")
        self.assertIsNone(advisory["unclassified_count"])
        self.assertEqual(advisory["unclassified"], [])
        self.assertEqual(summary, {
            "status": "fail", "commit": "c" * 40, "base": "a" * 40, "trusted_commit": "b" * 40,
            "reasons": ["protected_path", "zizmor_finding"],
            "paths": [{"path": "CODEOWNERS", "rule": "codeowners"}], "unnamed_paths": 6,
            "zizmor": {"version": PIN, "findings": 2, "failing": ["template-injection"]}})
        self.assertEqual(self.receipt.push_gate_summary(None), [])
        self.assertEqual(self.receipt.push_gate_summary([{"status": "maybe", "commit": "HEAD"}])[0]["status"], None)

    def test_unclassified_count_and_omissions_survive_receipt_filtering(self):
        record = {"advisory_gate_reads": {"unclassified_count": 7,
                  "unclassified": ["scripts/check.py:2", "scripts/other.py:3", "../outside.py:4", "bad name.py:5"],
                  "unclassified_shapes": {"scripts/check.py:2": ["policy/*.json", "*.json arbitrary message", "*.json\n"],
                                          "scripts/other.py:3": ["policy/[ab]*.json", "policy/*.json;message"]}}}
        [envelope] = self.receipt.push_gate_summary([record])
        summary = envelope["advisory_gate_reads"]
        self.assertEqual(summary["unclassified_count"], 7)
        self.assertEqual(summary["unclassified_omitted"], 5)
        self.assertEqual(summary["unclassified"], ["scripts/check.py:2", "scripts/other.py:3"])
        self.assertEqual(summary["unclassified_shapes"],
                         {"scripts/check.py:2": ["policy/*.json"], "scripts/other.py:3": ["policy/[ab]*.json"]})

    def test_read_inventory_stays_in_the_advisory_receipt(self):
        record = {"status": "pass", "reasons": [], "paths": [],
                  "advisory_gate_reads": {"files": ["policy/contract.schema.json"], "files_count": 1,
                                          "prefixes": ["policy/checks"], "prefixes_count": 1,
                                          "globs": ["policy/*.json"], "globs_count": 1,
                                          "unresolved": ["scripts/read_unknown.py:5"], "unresolved_count": 1}}
        [summary] = self.receipt.push_gate_summary([record])
        self.assertEqual((summary["status"], summary["reasons"], summary["paths"]), ("pass", [], []))
        advisory = summary["advisory_gate_reads"]
        for field in ("files", "prefixes", "globs", "unresolved"):
            self.assertEqual(advisory[field], record["advisory_gate_reads"][field])
            self.assertEqual(advisory[field + "_count"], 1)
        self.assertEqual(advisory["mode"], "monitoring_only")


class AttemptPushGateTests(unittest.TestCase):
    """ResolverAttempt.finish with the trusted gate: the outcome keeps one gate record per commit."""

    @classmethod
    def setUpClass(cls):
        cls.r = load_resolver()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="push-gate-attempt-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixture = GateFixture(self.tmp / "origin")
        self.gate_module = load_gate(self.fixture.trusted)
        self.zizmor, _ = fake_zizmor(self.tmp)
        self.tools = FakeTools(self.tmp)
        self.gitleaks = self.tmp / "bin/gitleaks"
        self.gitleaks.write_text(FAKE_GITLEAKS.format(python=sys.executable, log=str(self.tmp / "gitleaks.jsonl")),
                                 encoding="utf-8")
        self.gitleaks.chmod(0o755)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def attempt(self, github, owned):
        attempt = self.r.ResolverAttempt(
            number=12, title="Fix the widget", base_sha=self.fixture.base, branch="openhands/issue-12",
            owned_paths=owned, lane="lane:foundation", instruction="Resolve issue 12.\n", run_id=RUN_ID,
            gh=self.tools.gh, git=REAL_GIT, gitleaks=str(self.gitleaks), gitleaks_config=str(ROOT / ".gitleaks.toml"),
            host_paths=[str(self.tmp / "state")], user_name="fixtureuser", base_env=planted_base(self.home),
            runner=github, clone_url=str(self.fixture.bare),
            gate=self.gate_module.PushGate(git=REAL_GIT, zizmor=self.zizmor))
        attempt.session_sink(secrets.token_urlsafe(32))
        return attempt

    def result_for(self, name):
        result = self.tmp / "state/runs" / RUN_ID / name
        result.mkdir(parents=True, mode=0o700)
        return result

    def patch_for(self, edits):
        work = self.fixture.clone(f"work-{secrets.token_hex(3)}")
        for relative, data in edits.items():
            write_file(work, relative, data)
        return full_export(work, self.fixture.base)

    def test_an_owned_codeowners_change_is_refused_before_the_push(self):
        github = ResolverGitHub(base=self.fixture.base)
        outcome = self.attempt(github, ["CODEOWNERS"]).finish(
            self.result_for("codeowners"), patch_text=self.patch_for({"CODEOWNERS": "* @fixture-owner\n* @other\n"}),
            final_message=FINAL_MESSAGE)
        self.assertEqual((outcome["status"], outcome["failure_stage"], outcome["reasons"]),
                         (None, "push", ["push_gate_refused"]), outcome)
        self.assertEqual((outcome["writes"], github.pushes), ([], []))
        self.assertFalse(any(argv[:2] == ["pr", "create"] for argv in github.seen))
        [record] = outcome["push_gate"]
        self.assertEqual((record["status"], record["reasons"], record["paths"]),
                         ("fail", ["protected_path"], [{"path": "CODEOWNERS", "rule": "codeowners", "known": True}]))
        trusted = run_git(self.fixture.trusted, "rev-parse", "HEAD").stdout.decode().strip()
        self.assertEqual((record["base"], record["trusted_commit"]), (self.fixture.base, trusted))

    def test_a_benign_attempt_pushes_the_gated_commit_and_records_the_pass(self):
        github = ResolverGitHub(base=self.fixture.base)
        outcome = self.attempt(github, ["docs"]).finish(
            self.result_for("benign"), patch_text=self.patch_for({"docs/a.md": "a\nnew line\n"}),
            final_message=FINAL_MESSAGE)
        self.assertEqual(outcome["status"], "pr_opened", outcome)
        head = outcome["head"]
        self.assertEqual(github.pushes, [{"refspec": f"{head}:refs/heads/openhands/issue-12", "head": head}])
        self.assertEqual([(record["status"], record["commit"]) for record in outcome["push_gate"]], [("pass", head)])


if __name__ == "__main__":
    unittest.main()
