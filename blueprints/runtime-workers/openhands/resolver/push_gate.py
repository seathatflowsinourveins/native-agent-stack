"""Trusted pre-push gate for the OpenHands resolver (decision record amendment of 2026-10-04).

Option 1 of docs/decisions/2026-09-28-openhands-resolver-isolation.md lets this
repository's CI run the agent's commit. A check inside that CI cannot protect against the
commit under test: a push runs `push` workflows from the pushed commit ("This includes
workflows that are not merged into the default branch", GitHub "Events that trigger
workflows", push), and a same-repository pull request gets no fork boundary (same page,
"Workflows in forked repositories"; "Any user with write access to your repository has
read access to all secrets configured in your repository", GitHub "Secure use reference").
So GhHarness.push calls PushGate.check on the exact commit, and pushes only a commit it
passed (gh_harness.GhHarness.run refuses any other push).

For the diff of the commit against its base (git-diff-tree(1), renames off, so both names
of a rename count), check() refuses a change to:
- `.github/**`, and a file named CODEOWNERS anywhere (rule `github`, `codeowners`);
- the resolver's gate and harness code: resolver/** and resolver.py (`gate_code`);
- workflow-policy tests: tests/**.py files whose text names `.github`
  (`workflow_policy_test`);
- every file a workflow the push or its draft PR can start executes or reads as a gate,
  derived from the workflow files by derive_ci_protected: the files, directories and
  modules its `run:` steps name (`ci_named`), the import closure of the gate scripts they
  name (`ci_import`; test modules are protected but not traced), the test modules,
  start directories and packages unittest discovery reaches (`ci_discovered`), local
  actions and reusable workflows (`ci_local_action`), and the data those gate scripts
  read (`ci_read`, gate_reads.py; cross-family review P1 of 2026-10-04): the files they
  address, the directory or glob a computed path resolves under, and the paths a gate
  script in another language names.
It refuses every commit while a gate script's read cannot be resolved (`gate_input_unresolved`,
rule `unresolved_read`: it fails closed by refusing, since that read could be any file). It
also refuses a `run:` or `script:` text that interpolates untrusted event text
(`pr_text_interpolated`), and it runs the zizmor version CI pins on the commit's workflows
and actions with this module's own flags (no configuration file, no ignore comments); an
excessive-permissions, dangerous-triggers, cache-poisoning, artipacked or
template-injection finding refuses (`zizmor_finding`), and an unavailable zizmor fails closed.

Immutable to the agent: this module, its siblings patch_policy.py and gate_reads.py and the
rules above run from the checkout this file sits in (TRUSTED_ROOT, from __file__ only, never
from an argument or the environment). check() refuses when that checkout or a tool lies inside an
agent tree, when an enforcing file differs from the trusted commit's blob, when the trusted
commit is not on main's history at the base, or when the base's enforcing files differ
from the trusted ones (a stale gate). Every check returns one record; the harness journals
it (GhHarness.gates) and the driver keeps it in resolver-outcome.json.

Local composition. Sources: GitHub "Events that trigger workflows", "Secure use
reference", "Script injections" (the untrusted-context endings) and "Workflow syntax"
(steps[*].run, steps[*].working-directory, defaults.run.working-directory, local
`uses: ./`), read 2026-10-04; docs.zizmor.sh/audits (all five audits work offline) and the
installed zizmor 1.30.1 `--help`; docs.python.org unittest "Test Discovery" (default
pattern test*.py; since 3.11 a subdirectory is searched only when it has __init__.py) and
CPython Lib/unittest/loader.py `_find_test_path` (VALID_MODULE_NAME, fnmatch). The text
readers reuse patch_policy's reviewed derivation (names_in_text, executable_lines,
python_references; plan section 2 step 6), and the workflow reader follows the text-level
precedent of tests/test_workflow_hardening.py (jobs, unittest_invocations,
runs_whole_suite), because neither this host's interpreter nor CI's has PyYAML.
"""
from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile

GATE_FILE = Path(__file__).resolve()
RESOLVER_DIR = "blueprints/runtime-workers/openhands/resolver"
DRIVER = "blueprints/runtime-workers/openhands/resolver.py"
GATE_RELATIVE = f"{RESOLVER_DIR}/push_gate.py"
# The checkout this file sits in. Never taken from an argument, the environment or cwd.
TRUSTED_ROOT = GATE_FILE.parents[4]
# The files that decide what is refused: this module, the derivation it reuses and the
# harness that calls it. Each must equal the trusted commit's blob and the base's.
ENFORCING_FILES = (GATE_RELATIVE, f"{RESOLVER_DIR}/patch_policy.py", f"{RESOLVER_DIR}/gate_reads.py",
                   f"{RESOLVER_DIR}/gh_harness.py")


def _sibling(name):
    """Load resolver/<name>.py from beside this file under a per-path name.

    As resolver.py _load: importlib's "importing a source file directly" recipe; the
    module is registered before it runs, because dataclasses look it up there.
    """
    path = GATE_FILE.parent / f"{name}.py"
    module_name = f"openhands_push_gate_{name}_{hashlib.sha256(str(path).encode()).hexdigest()[:12]}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


patch_policy = _sibling("patch_policy")
gate_reads = _sibling("gate_reads")

SHA = re.compile(r"[0-9a-f]{40}")
GIT_ENV = patch_policy.GIT_ENV
STATUSES = ("pass", "fail")
MAX_PATHS = 200

# Triggers that neither a push to an agent branch nor its draft PR (nor the driver's review
# and comment) can start; a workflow with any other trigger, or with triggers this reader
# cannot list, counts as reachable. `workflow_call` stays in: a reachable caller or a
# ruleset can run it.
UNREACHABLE_TRIGGERS = frozenset({"schedule", "workflow_dispatch", "repository_dispatch"})
# GitHub "Script injections": untrusted github-context values "typically end with body,
# default_branch, email, head_ref, label, message, name, page_name, ref, and title".
UNTRUSTED_ENDINGS = frozenset({"body", "default_branch", "email", "head_ref", "label", "message", "name",
                               "page_name", "ref", "title"})
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
EVENT_PATH = re.compile(r"\bgithub\.(?:event(?P<path>(?:\.[A-Za-z0-9_*-]+|\[[^\]]*\])*)|(?P<head_ref>head_ref)\b)")

# zizmor: the pin CI installs, read from the trusted commit, and this module's own flags.
# CI runs `zizmor --no-config --no-ignores --persona regular --strict-collection .`
# (.github/workflows/validate.yml); the gate adds offline mode (no token reaches it, and the
# five audits work offline), collection that ignores .gitignore files, tool-failure-only
# exit codes and JSON output.
ZIZMOR_PIN_FILE = ".github/requirements-ci.txt"
ZIZMOR_PIN = re.compile(r"^zizmor==(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\b", re.M)
ZIZMOR_VERSION = re.compile(r"zizmor (?P<version>[0-9]+\.[0-9]+\.[0-9]+)\s*")
ZIZMOR_FLAGS = ("--no-config", "--no-ignores", "--persona", "regular", "--strict-collection", "--offline",
                "--collect=all", "--no-exit-codes", "--format", "json")
ZIZMOR_FAILING = frozenset({"excessive-permissions", "dangerous-triggers", "cache-poisoning", "artipacked",
                            "template-injection"})
ACTION_FILES = ("action.yml", "action.yaml")

# CPython Lib/unittest/loader.py: VALID_MODULE_NAME, and fnmatch(basename, pattern).
VALID_MODULE_NAME = re.compile(r"[_a-z]\w*\.py$", re.IGNORECASE)
# tests/test_workflow_hardening.py:799-825 (SHELL_BREAK, QUIET_FLAGS, runs_whole_suite).
SHELL_BREAK = {"|", "||", "&&", ";", ">", ">>", "2>&1", "&>", "2>", "<"}
QUIET_FLAGS = {"-v", "-q", "-b", "-f", "-c", "--verbose", "--quiet", "--buffer", "--failfast", "--catch",
               "--locals"}
UNITTEST = re.compile(r"\bpython(?:3(?:\.[0-9]+)?)? -m unittest\b([^\n]*)")
CD = re.compile(r"(?:^|[\s;&|(])cd[ \t]+([^\s;&|)]+)")


class GateError(Exception):
    """A condition that stops the check. `reason` is a stable code."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class WorkflowSyntaxError(GateError):
    """A workflow or action this reader cannot read with certainty; the gate fails closed."""


# -- Text-level workflow reader (no PyYAML on this host's interpreter or CI's)

KEY_LINE = re.compile(r"^(?P<indent> *)(?P<dash>(?:- +)*)(?P<key>[A-Za-z0-9_][A-Za-z0-9_.-]*|\"[^\"\n]*\"|'[^'\n]*')"
                      r":(?:[ ]+(?P<value>.*?))?[ ]*$")
KEYS_OF_INTEREST = ("run", "script", "working-directory", "uses")
INTEREST_ANYWHERE = re.compile(r"(?:^|[\s{,])(?:run|script|working-directory|uses)\s*:")
BLOCK_INDICATOR = re.compile(r"[|>](?:[1-9][+-]?|[+-][1-9]?)?")


def _strip_comment(value):
    """A plain or quoted inline value without its trailing comment (YAML: ` #` outside quotes)."""
    quote = None
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'" and (index == 0 or value[index - 1] in " :[{,"):
            quote = char
        elif char == "#" and (index == 0 or value[index - 1] in " \t"):
            return value[:index].rstrip()
    return value.rstrip()


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    return value


class WorkflowFacts:
    """What the gate needs from one workflow or action file."""

    def __init__(self, triggers, runs, scripts, working_dirs, local_uses):
        self.triggers, self.runs, self.scripts = triggers, runs, scripts
        self.working_dirs, self.local_uses = working_dirs, local_uses


def _triggers(lines):
    """The top-level `on:` event names; None when they cannot be listed (then reachable)."""
    for index, line in enumerate(lines):
        found = re.match(r"^(?:on|\"on\"|'on'):(?:[ ]+(.*))?$", line.rstrip())
        if not found:
            continue
        value = _strip_comment(found.group(1) or "")
        if value:
            if value.startswith("[") and value.endswith("]") and "{" not in value:
                return frozenset(_unquote(item.strip()) for item in value[1:-1].split(",") if item.strip())
            if re.fullmatch(r"[A-Za-z_]+|\"[A-Za-z_]+\"|'[A-Za-z_]+'", value):
                return frozenset({_unquote(value)})
            return None
        names, child = [], None
        for later in lines[index + 1:]:
            if not later.strip() or later.lstrip().startswith("#"):
                continue
            indent = len(later) - len(later.lstrip(" "))
            if indent == 0:
                break
            child = indent if child is None else child
            if indent != child:
                continue
            item = re.match(r"^ *(?:- +)?(?:\"([A-Za-z_]+)\"|'([A-Za-z_]+)'|([A-Za-z_]+))[ ]*(?::|$|#)", later)
            if not item:
                return None
            names.append(next(group for group in item.groups() if group))
        return frozenset(names) if names else None
    return None


def _fold(content):
    """A `>` block scalar's lines, folded (YAML 1.2.2 section 8.1.3): a break between two
    lines at the content indentation becomes a space, an empty line stays a break, and
    breaks next to more-indented lines are kept."""
    pieces, previous, empty = [], None, 0
    for line in content:
        if not line.strip():
            empty += 1
            continue
        kind = "more" if line[:1] in (" ", "\t") else "normal"
        if previous is None:
            pieces.append("\n" * empty)
        elif previous == kind == "normal":
            pieces.append(" " if not empty else "\n" * empty)
        else:
            pieces.append("\n" * (empty + 1))
        pieces.append(line)
        previous, empty = kind, 0
    return "".join(pieces)


def _flow_depth(text):
    """Open `[`/`{` minus closed ones, outside quotes: 0 when a flow collection is complete."""
    depth, quote = 0, None
    for char in text:
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
    return depth


def scan_workflow(text):
    """Read `run`, `script`, `working-directory` and local `uses` values, and the triggers.

    Local composition after tests/test_workflow_hardening.py's text-level readers. A
    value is inline (plain, single- or double-quoted, continued on more-indented lines)
    or a `|`/`>` block scalar, whose content is every following line indented at least
    as far as its first non-empty line (YAML 1.2.2 section 8.1.1); block scalars and flow
    collections under every other key are skipped whole, so their content is never read
    as keys. A key of interest inside a flow collection, aliases, merge keys, tags, tab
    indentation and a second document refuse (workflow_unsupported_yaml), so a value is
    never silently missed.
    """
    lines = text.splitlines()
    if any(line[:1] == "\t" for line in lines):
        raise WorkflowSyntaxError("workflow_unsupported_yaml")
    runs, scripts, working_dirs, local_uses = [], [], [], []
    index, seen_key = 0, False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if stripped == "..." or (stripped.startswith("---") and seen_key):
            raise WorkflowSyntaxError("workflow_unsupported_yaml")
        if stripped.startswith("---"):
            index += 1
            continue
        found = KEY_LINE.match(line)
        if not found:
            if INTEREST_ANYWHERE.search(_strip_comment(stripped)) or re.match(r"^(?:-[ ]*)?[&*!{\[]", stripped):
                raise WorkflowSyntaxError("workflow_unsupported_yaml")
            index += 1
            continue
        seen_key = True
        key = _unquote(found.group("key"))
        value = _strip_comment(found.group("value") or "")
        interesting = key in KEYS_OF_INTEREST
        if key == "<<" or value.startswith(("&", "*", "!")):
            raise WorkflowSyntaxError("workflow_unsupported_yaml")
        column = len(found.group("indent")) + len(found.group("dash"))
        index += 1
        if value.startswith(("{", "[")):
            flow = value
            while _flow_depth(flow) > 0 and index < len(lines):
                flow += " " + _strip_comment(lines[index].strip())
                index += 1
            if interesting or _flow_depth(flow) != 0 or INTEREST_ANYWHERE.search(flow):
                raise WorkflowSyntaxError("workflow_unsupported_yaml")
            continue
        if BLOCK_INDICATOR.fullmatch(value):
            explicit = re.search(r"[1-9]", value)
            content, indent = [], column + int(explicit.group()) if explicit else None
            while index < len(lines):
                later = lines[index]
                if later.strip():
                    width = len(later) - len(later.lstrip(" "))
                    if indent is None:
                        if width <= column:
                            break
                        indent = width
                    if width < indent:
                        break
                    content.append(later[indent:])
                else:
                    content.append("")
                index += 1
            text_value = (_fold(content) if value.startswith(">") else "\n".join(content)).rstrip("\n") + "\n"
        else:
            parts = [value]
            quote = value[0] if value.startswith(("\"", "'")) else None
            closed = quote is None or (len(value) > 1 and value.endswith(quote))
            while (interesting or not closed) and index < len(lines):
                later = lines[index]
                width = len(later) - len(later.lstrip(" "))
                if not later.strip():
                    if closed:
                        break
                    parts.append("")
                    index += 1
                    continue
                if closed and (width <= column or KEY_LINE.match(later) or later.lstrip().startswith(("- ", "#"))):
                    break
                parts.append(later.strip())
                index += 1
                if quote and later.rstrip().endswith(quote):
                    closed = True
            if not closed:
                raise WorkflowSyntaxError("workflow_unsupported_yaml")
            text_value = _unquote(" ".join(part for part in parts if part).strip())
        if not interesting or not text_value.strip():
            continue  # an empty value is a mapping key, such as defaults.run
        if key == "run":
            runs.append(text_value)
        elif key == "script":
            scripts.append(text_value)
        elif key == "working-directory":
            working_dirs.append(text_value.strip())
        elif key == "uses" and text_value.strip().startswith("./"):
            local_uses.append(text_value.strip())
    return WorkflowFacts(_triggers(lines), runs, scripts, working_dirs, local_uses)


def _relative(value):
    """A repository-relative path from a workflow value, or None (expressions, absolute paths, `..`)."""
    value = _unquote(value.strip())
    value = re.sub(r"^(?:\$\{\{\s*github\.workspace\s*\}\}|\$GITHUB_WORKSPACE|\$\{GITHUB_WORKSPACE\})/?", "", value)
    if "${{" in value or value.startswith(("/", "~", "$")):
        return None
    normalized = posixpath.normpath(value) if value else "."
    if normalized == "." or normalized == "":
        return ""
    if normalized.startswith("..") or "\\" in normalized:
        return None
    return normalized


def untrusted_interpolations(text):
    """Every `${{ }}` expression in `text` that reads an untrusted github-context value.

    Template expansion happens before the step runs, so a shell comment does not
    protect a value: the raw text is scanned.
    """
    found = []
    for expression in EXPRESSION.finditer(text):
        for reference in EVENT_PATH.finditer(expression.group(1)):
            if reference.group("head_ref"):
                found.append(reference.group(0))
                continue
            segments = [part for part in re.split(r"[.\[\]'\"]+", reference.group("path") or "") if part]
            names = [part for part in segments if part != "*"]
            if names and names[-1] in UNTRUSTED_ENDINGS:
                found.append(reference.group(0))
    return found


# -- The CI-executed set

def _unittest_runs(text):
    """(start, pattern) for each unittest discovery a run text starts (whole suite or `discover`).

    tests/test_workflow_hardening.py:803-825: no module or pattern arguments, or `discover`;
    `-s`, `-p` and `-t` may also be positional, in that order (unittest command-line help).
    """
    runs = []
    for found in UNITTEST.finditer(text.replace("\\\n", " ")):
        args = []
        for token in found.group(1).split():
            if token in SHELL_BREAK or token.startswith((">", "2>", "|", ";", "&", ")")):
                break
            args.append(_unquote(token))
        rest = [arg for arg in args if arg not in QUIET_FLAGS]
        if not rest:
            runs.append((".", "test*.py"))
            continue
        if rest[0] != "discover":
            continue
        options, positional, index = {}, [], 1
        while index < len(rest):
            arg = rest[index]
            name, has_value, attached = arg.partition("=")
            if name in ("-s", "--start-directory", "-p", "--pattern", "-t", "--top-level-directory"):
                value = attached if has_value else (rest[index + 1] if index + 1 < len(rest) else "")
                index += 1 if has_value else 2
                options[name.lstrip("-")[0]] = value
                continue
            if not arg.startswith("-"):
                positional.append(arg)
            index += 1
        start = options.get("s") or (positional[0] if positional else ".")
        pattern = options.get("p") or (positional[1] if len(positional) > 1 else "test*.py")
        runs.append((start, pattern))
    return runs


def _unittest_modules(text):
    """The dotted test names (`tests.test_x` or `tests.test_x.Case`) unittest invocations name."""
    names = []
    for found in UNITTEST.finditer(text.replace("\\\n", " ")):
        args = []
        for token in found.group(1).split():
            if token in SHELL_BREAK or token.startswith((">", "2>", "|", ";", "&", ")")):
                break
            args.append(_unquote(token))
        if args[:1] == ["discover"] or any(arg == "discover" for arg in args if not arg.startswith("-")):
            continue
        names += [arg for arg in args if not arg.startswith("-") and patch_policy._DOTTED.fullmatch(arg)]
    return names


def discovered(blobs, start, pattern):
    """unittest discovery from `start` with `pattern`, over a tree's blob names.

    The start directory's own modules, and the modules of every package below it that is
    reached through packages only (a directory is entered when it has __init__.py:
    Python 3.11 "Test Discovery"). Returns (module files, top package directories).
    """
    start = "" if start in (".", "./", "") else _relative(start)
    if start is None:
        return set(), set()
    files, packages = set(), set()
    for blob in blobs:
        directory, name = posixpath.split(blob)
        if start and not (directory == start or directory.startswith(start + "/")):
            continue
        below = directory[len(start) + 1:] if start else directory
        chain, ok = [], True
        if below:
            parts = below.split("/")
            for end in range(1, len(parts) + 1):
                package = posixpath.join(start, *parts[:end]) if start else "/".join(parts[:end])
                if f"{package}/__init__.py" not in blobs:
                    ok = False
                    break
                chain.append(package)
        if not ok:
            continue
        if chain:
            packages.add(chain[0])
        if VALID_MODULE_NAME.match(name) and fnmatch.fnmatchcase(name, pattern):
            files.add(blob)
    return files, packages


def _rooted(blobs, dirs, root):
    if not root:
        return blobs, dirs
    prefix = root + "/"
    return ({path[len(prefix):] for path in blobs if path.startswith(prefix)},
            {path[len(prefix):] for path in dirs if path.startswith(prefix)})


ARRAY_LITERAL = re.compile(r"(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)=\(")
FILTER_HAZARDS = re.compile(r"\beval\b|\$\{!|\b(?:declare|typeset|local)[ \t]+-[A-Za-z]*n")


def _literal_list_end(code, start):
    """The index of the `)` that closes a bash array literal holding only literal words, or None.

    Single-quoted words, double-quoted words without `$`, backquote or backslash, and plain
    words are literal; anything else (an expansion, a substitution, an escape, an operator)
    makes the list not literal.
    """
    quote, index = None, start
    while index < len(code):
        char = code[index]
        if quote:
            if char == quote:
                quote = None
            elif quote == '"' and char in "$`\\":
                return None
        elif char in "'\"":
            quote = char
        elif char == ")":
            return index
        elif char in "$`\\(;&|<>":
            return None
        index += 1
    return None


def pattern_lists(code):
    """Spans of the bash array literals a script uses only as `case` patterns.

    Such a list names paths to compare with other paths, as the `changes` step of
    adoption-bootstrap.yml compares `git diff --name-only` output with its PATTERNS and
    MACOS_PATTERNS globs; the step neither runs nor reads the listed files. A list
    qualifies only when every condition below holds; otherwise its words stay names, so
    the derivation keeps failing closed:
    - the script has no `eval`, no indirect expansion (`${!`) and no nameref;
    - the array is assigned once, as a literal list (_literal_list_end), and nothing else
      writes it (`NAME=`, `NAME+=`, `NAME[i]=`, read, mapfile, readarray, unset, declare);
    - each expansion of the array is `"${NAME[@]}"` in a `for VAR in "${NAME[@]}"` header;
    - each expansion of each such VAR is a `case` arm pattern: `$VAR)` or `${VAR})` at the
      start of a line.
    """
    if FILTER_HAZARDS.search(code):
        return []
    spans = []
    for found in ARRAY_LITERAL.finditer(code):
        name = found.group(1)
        end = _literal_list_end(code, found.end())
        if end is None:
            continue
        span = (found.start(1), end + 1)
        outside = code[:span[0]] + " " * (span[1] - span[0]) + code[span[1]:]
        if re.search(rf"(?:^|[\s;&|(]){name}(?:\[[^\]\n]*\])?\+?=", outside, re.M):
            continue
        if re.search(rf"\b(?:read|mapfile|readarray|unset|declare|typeset|local|readonly)\b[^\n;]*\b{name}\b", outside):
            continue
        expansions = re.findall(rf"\$\{{[#!]?{name}\b[^}}]*\}}|\${name}\b", outside)
        loops = re.findall(rf"\bfor[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+in[ \t]+\"\$\{{{name}\[@\]\}}\"", outside)
        if not loops or len(expansions) != len(loops):
            continue
        if all(len(re.findall(rf"\$\{{?{var}\b", outside))
               == len(re.findall(rf"(?m)^[ \t]*\$\{{?{var}\}}?[ \t]*\)", outside)) for var in set(loops)):
            spans.append(span)
    return spans


def _without_pattern_lists(code):
    """`code` with the words of its pattern-only lists blanked (pattern_lists), for name extraction."""
    for start, end in pattern_lists(code):
        code = code[:start] + " " * (end - start) + code[end:]
    return code


# When several rules derive the same path or prefix, the record names the most specific reason,
# whatever order the workflows are read in: a local action or unittest discovery runs the file,
# a step names it, or a gate script imports it.
RULE_PRECEDENCE = ("ci_local_action", "ci_discovered", "ci_named", "ci_import", "ci_read")

# Every rule a refused path can carry, with the phrase the agent's instructions use for it
# (cross-family review P2 of 2026-10-04). skills/resolver/SKILL.md and
# resolver.resolver_instruction state each phrase and STOP_AND_REPORT, and a test keeps them, this
# map and the receipt's rule set in step, so no rule reaches the gate without reaching the
# instructions. unresolved_read is the gate's own failure (a read it cannot resolve), not a path the
# agent chose.
AGENT_RULE_PHRASES = {
    "github": ".github/",
    "codeowners": "CODEOWNERS",
    "gate_code": "blueprints/runtime-workers/openhands/resolver",
    "workflow_policy_test": "tests/",
    "ci_discovered": "tests/",
    "ci_named": "CI runs or reads",
    "ci_import": "CI runs or reads",
    "ci_read": "CI runs or reads",
    "ci_local_action": "CI runs or reads",
    "pr_text_interpolation": "pull-request or issue text",
    "zizmor_finding": "workflow or action",
}
GATE_ONLY_RULES = frozenset({"unresolved_read"})
STOP_AND_REPORT = ("including a new or changed test, change nothing: stop and report which file would need to "
                   "change and why")


def _stronger(current, rule):
    if current is None or RULE_PRECEDENCE.index(rule) < RULE_PRECEDENCE.index(current):
        return rule
    return current


class CiProtected:
    """The derived set for one tree: exact files, directory prefixes and path globs (fnmatch,
    `*` also matching "/"), each with its rule."""

    def __init__(self):
        self.files, self.prefixes, self.globs, self.workflows, self.interpolations = {}, {}, {}, [], []
        self.unresolved = []  # "<gate file>:<line>" of reads gate_reads.GateReads could not resolve

    def add_file(self, path, rule):
        self.files[path] = _stronger(self.files.get(path), rule)

    def add_prefix(self, path, rule):
        if path:
            self.prefixes[path] = _stronger(self.prefixes.get(path), rule)

    def add_glob(self, pattern, rule):
        if pattern:
            self.globs[pattern] = _stronger(self.globs.get(pattern), rule)


def derive_ci_protected(tree):
    """Every repository path a workflow the push or its PR can start executes or reads.

    Reachable workflows are .github/workflows/*.yml|yaml with a trigger outside
    UNREACHABLE_TRIGGERS (or unlisted triggers), plus the local reusable workflows and
    actions they use. For each `run:` or `script:` text, without its whole-line comments
    (patch_policy.executable_lines): the names patch_policy.names_in_text finds from the
    repository root, from each working directory and from each `cd` target, leaving out the
    words of lists used only as `case` patterns (pattern_lists); unittest
    discovery (its start directory and the packages it enters); and the import closure
    (patch_policy.python_references) of each Python file named that is not a test module.
    Raises WorkflowSyntaxError when a reachable file cannot be read.
    """
    entries = tree.entries()
    blobs = {path for path, entry in entries.items() if entry[1] == "blob"}
    dirs = patch_policy.parent_dirs(entries)
    result = CiProtected()
    workflows = sorted(path for path in blobs if posixpath.dirname(path) == ".github/workflows"
                       and path.endswith((".yml", ".yaml")))
    queue = []
    for path in workflows:
        facts = scan_workflow(tree.read(path).decode("utf-8", "replace"))
        if facts.triggers is None or facts.triggers - UNREACHABLE_TRIGGERS:
            queue.append((path, facts))
    seen = {path for path, _ in queue}
    named_python, test_modules = set(), set()
    while queue:
        path, facts = queue.pop(0)
        result.workflows.append(path)
        roots = [""]
        for value in facts.working_dirs:
            relative = _relative(value)
            if relative is None:
                continue
            if relative:
                roots.append(relative)
                result.add_prefix(relative, "ci_named")
        for text in [*facts.runs, *facts.scripts]:
            result.interpolations += [(path, expression) for expression in untrusted_interpolations(text)]
            code = patch_policy.executable_lines(text.encode("utf-8"))
            text_roots = list(roots)
            for target in CD.findall(code):
                relative = _relative(target.strip("\"'"))
                if relative and relative in dirs:
                    text_roots.append(relative)
                    result.add_prefix(relative, "ci_named")
            named_code = _without_pattern_lists(code)
            for root in dict.fromkeys(text_roots):
                rooted_blobs, rooted_dirs = _rooted(blobs, dirs, root)
                for kind, name in patch_policy.names_in_text(named_code, rooted_blobs, rooted_dirs):
                    full = f"{root}/{name}" if root else name
                    if kind == "dir":
                        result.add_prefix(full, "ci_named")
                    else:
                        result.add_file(full, "ci_named")
                        if full.endswith(".py"):
                            named_python.add(full)
            for name in _unittest_modules(code):
                test_modules |= patch_policy.resolve_module(name.split("."), ("",), blobs, dirs)
            for start, pattern in _unittest_runs(code):
                for root in dict.fromkeys(roots):
                    joined = posixpath.normpath(posixpath.join(root, start)) if root else start
                    files, packages = discovered(blobs, joined, pattern)
                    test_modules |= files
                    for module in files:
                        result.add_file(module, "ci_discovered")
                    for package in packages:
                        result.add_prefix(package, "ci_discovered")
                    start_dir = _relative(joined)
                    if start_dir and start_dir in dirs:
                        result.add_prefix(start_dir, "ci_discovered")
        for use in facts.local_uses:
            relative = _relative(use)
            if not relative:
                continue
            if relative in blobs and relative.startswith(".github/workflows/"):
                result.add_file(relative, "ci_local_action")
                if relative not in seen:
                    seen.add(relative)
                    queue.append((relative, scan_workflow(tree.read(relative).decode("utf-8", "replace"))))
                continue
            result.add_prefix(relative, "ci_local_action")
            for name in ACTION_FILES:
                action = f"{relative}/{name}"
                if action in blobs and action not in seen:
                    seen.add(action)
                    queue.append((action, scan_workflow(tree.read(action).decode("utf-8", "replace"))))
    # Gate scripts' imports judge the change; a test module's imports are the code it tests,
    # which CI runs whatever is protected (the record's accepted residual), so test modules
    # are protected themselves but not traced.
    pending, traced = sorted(named_python - test_modules), set(test_modules)
    while pending:
        path = pending.pop()
        if path in traced or path not in blobs:
            continue
        traced.add(path)
        try:
            files, rule_dirs = patch_policy.python_references(path, tree.read(path), blobs, dirs)
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue  # it cannot run, so it imports nothing; the file itself stays protected
        for name in files:
            result.add_file(name, "ci_import")
            pending.append(name)
        for name in rule_dirs:
            result.add_prefix(name, "ci_import")
    _add_gate_reads(result, tree, blobs, dirs, sorted(traced - test_modules), test_modules)
    return result


def _add_gate_reads(result, tree, blobs, dirs, gate_python, test_modules):
    """The data CI-run gate code reads (cross-family review P1 of 2026-10-04).

    The gate code starts as the Python files traced so far that are not test modules (the
    named scripts and their import closure) and the other code files a step names or a gate
    script imports. gate_reads.GateReads reads a Python file; a `from module import NAME` of a
    repository module is resolved in that module, as patch_policy.resolve_module finds it
    (CPython's import order). A code file in another language counts the tracked paths its
    text names (patch_policy.names_in_text, the run-step rule, without pattern-only lists).
    Every file gate code reads is protected (ci_read). A code file is gate code too, and is
    followed in turn to a fixpoint (its reads, its imports through
    patch_policy.python_references, rule ci_import, or the names in its text), only when gate
    code runs it: a code file in another language runs, or hands on, every code file its text
    names; a Python file runs what reaches a call that executes code
    (gate_reads.GateReads.executed). A code file that Python gate code only reads, such as a
    workflow script it hashes and copies, is data: protected, not followed (2026-10-05, after
    main's #679 made tools/adoption/install_claude_profile.py read
    examples/claude-native/workflows/*.js). Test modules are protected but not followed: what
    they read, like what they import, is mostly the code and data under test (decision
    record, residual risks). The gate fails closed (PushGate.check, gate_input_unresolved) on
    a read the reader leaves unresolved, on an executing call whose argument is a computed
    location (any file there may run), and on a gate Python file it cannot parse or that
    nests too deeply for it, since CI's interpreter may run what this one cannot read."""
    analyzers, active, entries = {}, set(), tree.entries()

    def analyzer(path):
        """The file's GateReads, or None when it cannot be read (unresolved)."""
        if path not in analyzers:
            try:
                analyzers[path] = gate_reads.GateReads(
                    path, tree.read(path).decode("utf-8", "surrogateescape"),
                    imported=lambda module, name, level: imported(path, module, name, level))
            except (SyntaxError, ValueError, RecursionError):
                analyzers[path] = None
        return analyzers[path]

    def imported(path, module, name, level):
        here = posixpath.dirname(path)
        if level:
            base = here.split("/") if here else []
            if level - 1 > len(base):
                return (gate_reads.UNKNOWN,)
            roots = ("/".join(base[:len(base) - (level - 1)]),)
        else:
            roots = tuple(dict.fromkeys((here, "")))
        parts = [part for part in module.split(".") if part]
        found = sorted(patch_policy.resolve_module(parts, roots, blobs, dirs), key=len) if parts else []
        target = found[-1] if found else None
        key = (target, name)
        if target is None or key in active:
            return (gate_reads.UNKNOWN,)
        other = analyzer(target)
        if other is None:
            return (gate_reads.UNKNOWN,)
        active.add(key)
        try:
            return other.module_value(name)
        finally:
            active.discard(key)

    def is_code(path):
        return posixpath.splitext(path)[1] in patch_policy.CODE_SUFFIXES or entries[path][0] == "100755"

    queue = [*gate_python, *sorted(path for path, rule in result.files.items()
                                   if rule in ("ci_named", "ci_import") and not path.endswith(".py"))]
    done, followed = set(test_modules), set(gate_python)
    while queue:
        path = queue.pop(0)
        if path in done or path not in blobs:
            continue
        done.add(path)
        named, runs = [], []
        if path.endswith(".py"):
            reader = analyzer(path)
            try:
                if reader is None:
                    raise RecursionError  # unparseable here or too deep: unresolved
                files, prefixes, globs, unresolved = reader.reads(blobs, dirs)
                executed, computed = reader.executed(blobs, dirs)
            except RecursionError:
                result.unresolved.append(f"{path}:0")
                continue
            for name in prefixes:
                result.add_prefix(name, "ci_read")
            for pattern in globs:
                result.add_glob(pattern, "ci_read")
            result.unresolved.extend(sorted(unresolved | computed))
            named, runs = sorted(files | executed), sorted(executed)
            if path not in followed:  # reached by a name or a read: its imports run too
                try:
                    imports, import_dirs = patch_policy.python_references(path, tree.read(path), blobs, dirs)
                except (SyntaxError, ValueError, UnicodeDecodeError):
                    imports, import_dirs = (), ()
                    result.unresolved.append(f"{path}:0")
                for name in imports:
                    result.add_file(name, "ci_import")
                    queue.append(name)
                for name in import_dirs:
                    result.add_prefix(name, "ci_import")
        elif is_code(path):
            text = _without_pattern_lists(patch_policy.executable_lines(tree.read(path)))
            for kind, name in patch_policy.names_in_text(text, blobs, dirs):
                if kind == "dir":
                    result.add_prefix(name, "ci_read")
                else:
                    named.append(name)
            runs = named
        for name in named:
            result.add_file(name, "ci_read")
        for name in runs:
            if name in blobs and name not in done and (name.endswith(".py") or is_code(name)):
                queue.append(name)


def policy_tests(tree, cache=None):
    """Workflow-policy tests: tests/**.py files whose text names `.github`.

    A GitTree's candidates are read in one `git cat-file --batch` (git-cat-file(1)), and
    `cache` (object id to result) spares the blobs the trusted, base and head trees share.
    """
    cache = {} if cache is None else cache
    entries = tree.entries()
    candidates = {path: entry[2] for path, entry in entries.items()
                  if entry[1] == "blob" and path.startswith("tests/") and path.endswith(".py")}
    if isinstance(tree, patch_policy.GitTree):
        missing = sorted({oid for oid in candidates.values() if oid not in cache})
        if missing:
            out = subprocess.run([tree.git, "-C", tree.repo, "cat-file", "--batch"], capture_output=True,
                                 input=("\n".join(missing) + "\n").encode("ascii"), env=dict(GIT_ENV), timeout=300,
                                 check=False)
            if out.returncode != 0:
                raise GateError("git_failed")
            data, position = out.stdout, 0
            for oid in missing:
                end = data.index(b"\n", position)
                header = data[position:end].split()
                if len(header) != 3 or header[0].decode("ascii") != oid or header[1] != b"blob":
                    raise GateError("git_failed")
                size = int(header[2])
                cache[oid] = b".github" in data[end + 1:end + 1 + size]
                position = end + 1 + size + 1
        return {path for path, oid in candidates.items() if cache[oid]}
    return {path for path in candidates if b".github" in tree.read(path)}


def static_rule(path):
    """The rule a path breaks by name alone, compared case-folded (patch_policy.fold)."""
    folded = patch_policy.fold(path)
    parts = folded.split("/")
    if parts[0] == ".github":
        return "github"
    if parts[-1] == "codeowners":
        return "codeowners"
    resolver_dir = patch_policy.fold(RESOLVER_DIR)
    if folded == patch_policy.fold(DRIVER) or folded.startswith(resolver_dir + "/"):
        return "gate_code"
    return None


class Protected:
    """The union of the rules over the trusted, base and head trees."""

    def __init__(self, derived, tests):
        self.files, self.prefixes, self.globs = {}, {}, {}
        for item in derived:
            for path, rule in item.files.items():
                key = patch_policy.fold(path)
                self.files[key] = _stronger(self.files.get(key), rule)
            for path, rule in item.prefixes.items():
                key = patch_policy.fold(path)
                self.prefixes[key] = _stronger(self.prefixes.get(key), rule)
            for pattern, rule in getattr(item, "globs", {}).items():
                key = patch_policy.fold(pattern)
                self.globs[key] = _stronger(self.globs.get(key), rule)
        for path in tests:
            self.files[patch_policy.fold(path)] = "workflow_policy_test"

    def rule(self, path):
        rule = static_rule(path)
        if rule:
            return rule
        folded = patch_policy.fold(path)
        if folded in self.files:
            return self.files[folded]
        parts = folded.split("/")
        for end in range(len(parts) - 1, 0, -1):
            prefix = "/".join(parts[:end])
            if prefix in self.prefixes:
                return self.prefixes[prefix]
        for pattern, rule in self.globs.items():
            if fnmatch.fnmatchcase(folded, pattern):  # `*` also matches "/" (Lib/fnmatch.py translate)
                return rule
        return None


# -- The gate

def _git(git, repo, *args, check=True, binary=False):
    completed = subprocess.run([git, "-C", str(repo), *args], capture_output=True, env=dict(GIT_ENV), timeout=120,
                               check=False, stdin=subprocess.DEVNULL)
    if check and completed.returncode != 0:
        raise GateError("git_failed")
    if binary:
        return completed
    return completed.stdout.decode("utf-8", "surrogateescape").strip()


def _within(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return os.path.commonpath([path, root]) == root


class PushGate:
    """The trusted gate. `git` and `zizmor` are absolute executables given by the coordinator."""

    def __init__(self, *, git, zizmor, timeout=600):
        self.git, self.zizmor, self.timeout = git, zizmor, timeout

    def trusted_identity(self, agent_trees=()):
        """Where the gate runs from: the checks that need no clone. Returns the trusted commit."""
        trees = [os.path.realpath(tree) for tree in agent_trees]
        locations = [str(GATE_FILE), str(TRUSTED_ROOT), *(str(TRUSTED_ROOT / rel) for rel in ENFORCING_FILES)]
        if any(_within(location, tree) for location in locations for tree in trees):
            raise GateError("gate_inside_agent_tree")
        tools = [tool for tool in (self.git, self.zizmor) if isinstance(tool, str) and tool]
        if any(_within(tool, tree) for tool in tools for tree in trees):
            raise GateError("tool_inside_agent_tree")
        if not (isinstance(self.git, str) and os.path.isabs(self.git) and os.access(self.git, os.X_OK)):
            raise GateError("git_unavailable")
        if GATE_FILE != TRUSTED_ROOT / GATE_RELATIVE:
            raise GateError("gate_not_at_its_path")
        try:
            top = _git(self.git, TRUSTED_ROOT, "rev-parse", "--show-toplevel")
            commit = _git(self.git, TRUSTED_ROOT, "rev-parse", "--verify", "HEAD^{commit}")
        except GateError:
            raise GateError("trusted_root_not_a_checkout") from None
        if os.path.realpath(top) != str(TRUSTED_ROOT) or not SHA.fullmatch(commit):
            raise GateError("trusted_root_not_a_checkout")
        for rel in ENFORCING_FILES:
            expected = _git(self.git, TRUSTED_ROOT, "rev-parse", "--verify", "--quiet", f"{commit}:{rel}", check=False)
            actual = _git(self.git, TRUSTED_ROOT, "hash-object", "--no-filters", "--", str(TRUSTED_ROOT / rel),
                          check=False)
            if not expected or expected != actual:
                raise GateError("gate_file_modified")
        return commit

    def check(self, clone, *, base, head, agent_trees=()):
        """One record for the exact commit `head` of `clone` against `base`. Never raises."""
        record = {"commit": head, "base": base, "status": "fail", "reasons": [], "paths": [],
                  "trusted_commit": None, "protected": None,
                  "zizmor": {"version": None, "findings": None, "failing": []}}
        reasons, paths = [], {}
        try:
            if not (isinstance(clone, str) and os.path.isabs(clone) and all(isinstance(sha, str) and SHA.fullmatch(sha)
                                                                             for sha in (base, head))):
                raise GateError("invalid_arguments")
            record["trusted_commit"] = trusted = self.trusted_identity([clone, *agent_trees])
            self._check_commit(clone, base, head, trusted, reasons)
            trusted_tree = patch_policy.GitTree(TRUSTED_ROOT, trusted, git=self.git)
            base_tree = patch_policy.GitTree(clone, base, git=self.git)
            head_tree = patch_policy.GitTree(clone, head, git=self.git)
            changed = self._changed(clone, base, head)
            try:
                derived = [derive_ci_protected(tree) for tree in (trusted_tree, base_tree, head_tree)]
                shared = {}
                protected = Protected(derived, set().union(*(policy_tests(tree, shared) for tree in
                                                              (trusted_tree, base_tree, head_tree))))
                record["protected"] = {"workflows": len(set().union(*(item.workflows for item in derived))),
                                       "files": len(protected.files), "prefixes": len(protected.prefixes),
                                       "globs": len(protected.globs)}
                for path in changed:
                    rule = protected.rule(path)
                    if rule:
                        paths.setdefault(path, rule)
                if any(rule for rule in paths.values()):
                    reasons.append("protected_path")
                # A gate read the reader could not resolve (gate_reads: a computed path at the root
                # whose part is of unknown origin) could be any file, so the gate fails closed by
                # refusing the commit rather than protecting the whole tree.
                unresolved = sorted(set().union(*(item.unresolved for item in derived)))
                if unresolved:
                    reasons.append("gate_input_unresolved")
                    record["unresolved"] = unresolved[:MAX_PATHS]
                    for location in unresolved:
                        paths.setdefault(location.rsplit(":", 1)[0], "unresolved_read")
                interpolated = sorted({workflow for item in (derived[0], derived[2])
                                       for workflow, _ in item.interpolations})
                if interpolated:
                    reasons.append("pr_text_interpolated")
                    for workflow in interpolated:
                        paths.setdefault(workflow, "pr_text_interpolation")
            except GateError as error:
                reasons.append(error.reason)
            self._zizmor(trusted_tree, head_tree, record, reasons, paths)
            known = set(base_tree.entries()) | set(trusted_tree.entries())
        except GateError as error:
            reasons.append(error.reason)
            known = set()
        except Exception as error:  # noqa: BLE001 - any other failure refuses: the gate fails closed
            reasons.append("gate_error_" + re.sub(r"[^a-z0-9_]", "", type(error).__name__.lower())[:40])
            known = set()
        ordered = sorted(paths.items())
        record["paths"] = [{"path": path, "rule": rule, "known": path in known} for path, rule in ordered[:MAX_PATHS]]
        if len(ordered) > MAX_PATHS:
            record["paths_omitted"] = len(ordered) - MAX_PATHS
        record["reasons"] = list(dict.fromkeys(reasons))
        record["status"] = "pass" if not record["reasons"] else "fail"
        return record

    def _check_commit(self, clone, base, head, trusted, reasons):
        """The commit is the base's one child; the trusted gate is main's current reviewed copy."""
        listed = _git(self.git, clone, "rev-list", "--parents", "-n", "1", "--end-of-options", head, check=False)
        if listed.split()[:1] != [head]:
            raise GateError("commit_unknown")
        if listed.split()[1:] != [base]:
            reasons.append("commit_not_single_child_of_base")
        ancestor = _git(self.git, clone, "merge-base", "--is-ancestor", trusted, base, check=False, binary=True)
        if ancestor.returncode != 0:
            raise GateError("trusted_copy_not_on_main")
        for rel in ENFORCING_FILES:
            at_base = _git(self.git, clone, "rev-parse", "--verify", "--quiet", f"{base}:{rel}", check=False)
            trusted_blob = _git(self.git, TRUSTED_ROOT, "rev-parse", "--verify", "--quiet", f"{trusted}:{rel}",
                                check=False)
            if not at_base or at_base != trusted_blob:
                raise GateError("gate_differs_from_base")

    def _changed(self, clone, base, head):
        """git-diff-tree(1): every path the commit adds, deletes, modifies or retypes; renames off."""
        out = _git(self.git, clone, "diff-tree", "-r", "-z", "--name-only", "--no-renames", "--no-commit-id",
                   base, head, binary=True)
        if out.returncode != 0:
            raise GateError("diff_failed")
        return sorted({name.decode("utf-8", "surrogateescape") for name in out.stdout.split(b"\0") if name})

    def _zizmor(self, trusted_tree, head_tree, record, reasons, paths):
        """The pinned zizmor on the commit's workflows and actions; every failure is a refusal."""
        try:
            pin = ZIZMOR_PIN.search(trusted_tree.read(ZIZMOR_PIN_FILE).decode("utf-8", "replace"))
        except (KeyError, subprocess.SubprocessError):
            pin = None
        if not pin:
            reasons.append("zizmor_pin_missing")
            return
        executable = self.zizmor
        if not (isinstance(executable, str) and os.path.isabs(executable) and os.path.isfile(executable)
                and os.access(executable, os.X_OK)):
            reasons.append("zizmor_unavailable")
            return
        with tempfile.TemporaryDirectory(prefix="push-gate-") as scratch:
            home, work = Path(scratch) / "home", Path(scratch) / "input"
            home.mkdir(mode=0o700)
            work.mkdir(mode=0o700)
            env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "LANG": "C.UTF-8", "NO_COLOR": "1"}
            try:
                version = subprocess.run([executable, "--version"], cwd=work, env=env, capture_output=True, text=True,
                                         timeout=60, check=False, stdin=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                reasons.append("zizmor_unavailable")
                return
            found = ZIZMOR_VERSION.fullmatch(version.stdout) if version.returncode == 0 else None
            if not found:
                reasons.append("zizmor_unavailable")
                return
            record["zizmor"]["version"] = found["version"]
            if found["version"] != pin["version"]:
                reasons.append("zizmor_version_mismatch")
                return
            written = 0
            for path, (mode, kind, _) in sorted(head_tree.entries().items()):
                if kind != "blob" or mode not in ("100644", "100755"):
                    continue
                if not (path.startswith(".github/") or posixpath.basename(path) in ACTION_FILES):
                    continue
                if path.startswith("/") or ".." in path.split("/"):
                    continue
                target = work / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(head_tree.read(path))
                written += 1
            if not written:
                reasons.append("zizmor_no_inputs")
                return
            try:
                audited = subprocess.run([executable, *ZIZMOR_FLAGS, "."], cwd=work, env=env, capture_output=True,
                                         text=True, timeout=self.timeout, check=False, stdin=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                reasons.append("zizmor_failed")
                return
        if audited.returncode != 0:
            reasons.append("zizmor_failed")
            return
        try:
            findings = json.loads(audited.stdout)
        except ValueError:
            findings = None
        if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
            reasons.append("zizmor_output_invalid")
            return
        record["zizmor"]["findings"] = len(findings)
        failing = set()
        for finding in findings:
            ident = finding.get("ident")
            if ident not in ZIZMOR_FAILING:
                continue
            failing.add(ident)
            for location in finding.get("locations") or []:
                local = (((location or {}).get("symbolic") or {}).get("key") or {}).get("Local") or {}
                given = local.get("given_path") or local.get("verbatim_path")
                if isinstance(given, str):
                    relative = _relative(given)
                    if relative:
                        paths.setdefault(relative, "zizmor_finding")
        record["zizmor"]["failing"] = sorted(failing)
        if failing:
            reasons.append("zizmor_finding")
