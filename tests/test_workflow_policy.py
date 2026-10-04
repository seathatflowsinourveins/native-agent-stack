"""Least-privilege tripwire for every GitHub Actions workflow (docs/decisions/2026-10-04-ci-least-privilege.md).

The resolver pushes agent-written commits to branches of this repository, and their pull_request runs execute that
code. A check inside the commit under test cannot protect against that commit: bounded job 004 (GPT Sol, cross-family
consensus) put the primary control in a trusted gate before the push (the OpenHands resolver, #489). This module is
the regression layer for main.

It parses every workflow with a strict YAML-subset loader that needs no third-party package (CI's interpreters do not
all carry PyYAML). Any construct outside the subset (anchor, alias, tag, flow mapping other than `{}`, duplicate key,
tab indentation, document marker, multi-line flow scalar) is reported as an `unparseable` violation instead of being
guessed at, and the loader is cross-checked against PyYAML wherever PyYAML is importable. The rules in RULES then run
on the parsed workflows, so the secrets rule reads values as GitHub does, after YAML decoding (the raw text stays a
second net); each rule has planted workflows, written to a temporary directory, that fail with exactly that rule
named. zizmor runs with --no-config --no-ignores, so no file in a commit can suppress its findings; the zizmor
classes keep that so and add a pedantic-persona pass over the five audits the consensus names.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
ZIZMOR = shutil.which("zizmor")

RULES = {
    "unparseable": "the file is outside the strict YAML subset or is not a workflow",
    "workflow-permissions-missing": "the workflow has no top-level permissions",
    "workflow-permissions-not-empty": "the top-level permissions are not `{}`",
    "pull-request-write-scope": "a job that runs on pull_request holds a write scope or id-token: write",
    "id-token-write": "id-token: write outside a job that attests provenance on a non-pull_request event",
    "dangerous-trigger": "a pull_request_target or workflow_run trigger",
    "pull-request-secret": "a secret other than GITHUB_TOKEN in a workflow that runs on pull_request",
    "checkout-persist-credentials": "actions/checkout without persist-credentials: false",
    "runner-label": "a runs-on that is not one literal label from GitHub's documented hosted-runner list",
    "job-timeout": "a job without an integer timeout-minutes",
    "pull-request-cache-write": "a cache write, or a write-capable cache-mode, in a job that runs on pull_request",
    "pull-request-cache-mode": "a job that runs on pull_request without cache-mode none or read",
    "workflow-concurrency": "the workflow has no concurrency group",
}

# Events whose runs execute a pull request's code: `pull_request` itself, and `workflow_call`, whose caller may be a
# pull_request workflow (sota-sources-gate.yml is called from one).
PULL_REQUEST_EVENTS = {"pull_request", "workflow_call"}
DANGEROUS_EVENTS = {"pull_request_target", "workflow_run"}
# The one condition accepted as keeping a job or step off pull_request runs: a top-level `&&` conjunct of its `if:`.
EXCLUDES_PULL_REQUEST = "github.event_name != 'pull_request'"
# An exact allowlist, not a pattern: the standard GitHub-hosted runner labels in the ubuntu, windows and macos
# families, as GitHub's "GitHub-hosted runners" reference lists them
# (https://docs.github.com/en/actions/reference/runners/github-hosted-runners, "Standard GitHub-hosted runners for
# public repositories"; source github/docs data/reusables/actions/supported-github-runners.md and
# single-cpu-table-row.md at 2bd66de8cea336061c9ea060c9b37385136e6ab3, last changed 2026-09-17 by eb8f32b5dd88, read
# 2026-10-04). Left out: `xcode-27` (public preview, outside the three families) and larger runners, whose Linux and
# Windows labels are names an organization chooses. A self-hosted runner never matches a label here only by shape;
# adopting a new hosted label is a reviewed change to this set.
HOSTED_RUNNER_LABELS = frozenset({
    "ubuntu-slim", "ubuntu-latest", "ubuntu-26.04", "ubuntu-24.04", "ubuntu-22.04",
    "ubuntu-26.04-arm", "ubuntu-24.04-arm", "ubuntu-22.04-arm",
    "windows-latest", "windows-2025", "windows-2025-vs2026", "windows-2022", "windows-11-arm", "windows-11-vs2026-arm",
    "macos-latest", "macos-26", "macos-15", "macos-14", "macos-26-intel", "macos-15-intel",
})
ATTEST_ACTIONS = {"actions/attest", "actions/attest-build-provenance", "actions/attest-sbom"}
# actions/checkout reads the input with core.getBooleanInput: YAML 1.2 core-schema spellings only.
FALSE = {"false", "False", "FALSE"}

# Workflows whose exact bytes a recovery plan binds (tests/test_active_recovery_plans.py checks the plans' frozen_sources
# against the checkout). Moving either to `permissions: {}` or adding a concurrency group needs that binding refreshed
# in the same change, as docs/decisions/2026-09-26-token-workflow-hardening.md did; both are workflow_dispatch-only and
# keep a workflow-level `contents: read`. Each maps to the file that records its SHA-256, and
# test_hash_bound_exemptions_are_still_bound fails once the binding moves on, so the exemption cannot outlive it.
HASH_BOUND = {
    "native-offhost-app-state.yml": "blueprints/convergence-practice/offhost-app-state/plan.json",
    "native-offhost-restore.yml": "blueprints/convergence-practice/offhost-restore/hosted-plan.json",
}
EXEMPTIONS = {
    "workflow-permissions-not-empty": {name: "recovery-plan binding (HASH_BOUND)" for name in HASH_BOUND},
    "workflow-concurrency": {
        **{name: "recovery-plan binding (HASH_BOUND)" for name in HASH_BOUND},
        "catalog-freshness.yml": "job-scoped group on propose, its only writer; freshness reads only and may overlap "
                                 "(tests/test_catalog_freshness_propose.py)",
    },
    "pull-request-cache-mode": {
        "adoption-bootstrap.yml:bootstrap-macos": "saves its model cache on push, schedule and workflow_dispatch "
                                                  "only; cache-mode takes no expression",
    },
}
# Every write grant in the repository, by job. A new one is a reviewed change to this inventory.
WRITE_GRANTS = {
    "catalog-freshness.yml:propose": ["contents: write", "pull-requests: write"],
    "publish-catalog.yml:publish": ["id-token: write", "attestations: write"],
    "publish-catalog.yml:release": ["contents: write"],
    "saturation-tracking.yml:issue": ["issues: write"],
    "scorecard.yml:analysis": ["security-events: write"],
    "security-scan.yml:osv-sarif-upload": ["security-events: write"],
    "security-scan.yml:zizmor-sarif-upload": ["security-events: write"],
}


# --------------------------------------------------------------------------- strict YAML subset


class UnsupportedYAML(ValueError):
    """A construct outside the strict subset. The checker reports it as a violation; it never skips the file."""


_KEY = re.compile(r"""(?P<key>"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[A-Za-z0-9_$][A-Za-z0-9_.$/-]*):(?=[ ]|$)[ ]*""")
_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
            "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": "\u2028",
            "P": "\u2029"}


class _Loader:
    """Block mappings and sequences, plain and single-line quoted scalars, flow sequences of scalars, the empty
    mapping `{}`, and `|`/`>` block scalars without an indentation indicator. Scalars stay strings: `on` stays a key,
    `false` stays "false", and `5` stays "5"."""

    def __init__(self, text):
        # GitHub reads a workflow with a byte-order mark or CRLF line ends as it reads the plain file.
        self.lines = text.removeprefix("﻿").replace("\r\n", "\n").split("\n")
        self.i = 0

    def error(self, index, message):
        raise UnsupportedYAML(f"line {index + 1}: {message}")

    def load(self):
        index = self._next()
        if index is None:
            self.error(0, "empty document")
        if self._indent(index) != 0:
            self.error(index, "the document does not start at column 0")
        value = self._block(0)
        index = self._next()
        if index is not None:
            self.error(index, "content after the top-level mapping")
        return value

    def _next(self):
        while self.i < len(self.lines):
            stripped = self.lines[self.i].strip()
            if stripped and not stripped.startswith("#"):
                return self.i
            self.i += 1
        return None

    def _indent(self, index):
        line = self.lines[index]
        rest = line.lstrip(" ")
        if rest.startswith("\t"):
            self.error(index, "a tab in indentation")
        return len(line) - len(rest)

    def _is_dash(self, index, indent):
        text = self.lines[index][indent:]
        return text == "-" or text.startswith("- ")

    def _block(self, indent):
        index = self._next()
        return self._sequence(indent) if self._is_dash(index, indent) else self._mapping(indent)

    def _node(self, parent, indentless=False):
        """The block value after a key or dash at column `parent`, or None when nothing is nested under it."""
        index = self._next()
        if index is None:
            return None
        indent = self._indent(index)
        if indent > parent:
            return self._block(indent)
        if indentless and indent == parent and self._is_dash(index, indent):
            return self._sequence(indent)
        return None

    def _mapping(self, indent):
        result = {}
        while (index := self._next()) is not None:
            current = self._indent(index)
            if current < indent:
                break
            if current > indent:
                self.error(index, "unexpected indentation")
            if self._is_dash(index, indent):
                self.error(index, "a sequence entry where a mapping key belongs")
            text = self.lines[index][indent:]
            if text.startswith(("---", "...", "%", "? ")):
                self.error(index, "a document marker, directive or complex key")
            match = _KEY.match(text)
            if not match:
                self.error(index, "not a `key: value` entry")
            key = self._scalar(match.group("key"), index) if match.group("key")[0] in "\"'" else match.group("key")
            if key in result:
                self.error(index, f"duplicate key {key!r}")
            self.i = index + 1
            result[key] = self._value(text[match.end():], indent, index, indentless=True)
        return result

    def _sequence(self, indent):
        result = []
        while (index := self._next()) is not None:
            current = self._indent(index)
            if current < indent or (current == indent and not self._is_dash(index, indent)):
                break
            if current > indent:
                self.error(index, "unexpected indentation")
            rest = self.lines[index][indent + 1:]
            item = rest.lstrip(" ")
            column = indent + 1 + len(rest) - len(item)
            if not item or item.startswith("#"):
                self.i = index + 1
                result.append(self._node(indent))
            elif item == "-" or item.startswith("- "):
                self.error(index, "a nested sequence on one line")
            elif _KEY.match(item):
                # `- key: value` opens a mapping whose keys sit at the item's column.
                self.lines[index] = " " * column + item
                result.append(self._mapping(column))
            else:
                self.i = index + 1
                result.append(self._value(item, indent, index))
        return result

    def _value(self, text, parent, index, indentless=False):
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            return self._node(parent, indentless)
        if stripped[0] in "|>":
            return self._block_scalar(stripped, parent, index)
        value = self._scalar(stripped, index)
        following = self._next()
        if following is not None and self._indent(following) > parent:
            self.error(following, "a continuation line: multi-line flow scalars are outside the subset")
        return value

    def _scalar(self, text, index):
        first = text[0]
        if first in "&*!%@`":
            self.error(index, f"{first!r} starts an anchor, alias, tag or reserved indicator")
        if first == '"':
            value, end = self._double(text, index)
        elif first == "'":
            value, end = self._single(text, index)
        elif first == "[":
            value, end = self._flow_sequence(text, index)
        elif first == "{":
            match = re.match(r"\{[ ]*\}", text)
            if not match:
                self.error(index, "a flow mapping other than {}")
            value, end = {}, match.end()
        else:
            comment = re.search(r"[ \t]#", text)
            value = (text[:comment.start()] if comment else text).rstrip()
            if re.match(r"[-?:](?:[ \t]|$)", value) or re.search(r":(?:[ \t]|$)", value):
                self.error(index, "an indicator inside a plain scalar")
            return value
        tail = text[end:].strip()
        if tail and not tail.startswith("#"):
            self.error(index, "text after a quoted scalar or flow collection")
        return value

    def _double(self, text, index):
        out, k = [], 1
        while k < len(text):
            char = text[k]
            if char == '"':
                return "".join(out), k + 1
            if char == "\\":
                code = text[k + 1:k + 2]
                if code in _ESCAPES:
                    out.append(_ESCAPES[code])
                    k += 2
                    continue
                width = {"x": 2, "u": 4, "U": 8}.get(code)
                digits = text[k + 2:k + 2 + width] if width else ""
                if not width or not re.fullmatch(r"[0-9A-Fa-f]+", digits) or len(digits) != width:
                    self.error(index, "an escape outside the YAML double-quoted set")
                out.append(chr(int(digits, 16)))
                k += 2 + width
                continue
            out.append(char)
            k += 1
        self.error(index, "a double-quoted scalar that does not close on its line")

    def _single(self, text, index):
        out, k = [], 1
        while k < len(text):
            if text[k] == "'":
                if text[k + 1:k + 2] == "'":
                    out.append("'")
                    k += 2
                    continue
                return "".join(out), k + 1
            out.append(text[k])
            k += 1
        self.error(index, "a single-quoted scalar that does not close on its line")

    def _flow_sequence(self, text, index):
        items, k, start = [], 1, 1
        while k < len(text):
            char = text[k]
            if char in "'\"":
                k = (self._single if char == "'" else self._double)(text[k:], index)[1] + k
                continue
            if char in "[{":
                self.error(index, "a nested flow collection")
            if char in ",]":
                items.append(text[start:k].strip())
                start = k + 1
                if char == "]":
                    break
            k += 1
        else:
            self.error(index, "a flow sequence that does not close on its line")
        if items and not items[-1]:
            items.pop()  # `[a, b]` and `[a, b,]` alike; `[]` is empty
        if any(not item for item in items):
            self.error(index, "an empty flow sequence entry")
        values = []
        for item in items:
            if item[0] in "'\"":
                value, end = (self._single if item[0] == "'" else self._double)(item, index)
                if item[end:].strip():
                    self.error(index, "text after a quoted flow entry")
                values.append(value)
            elif item[0] in "&*!%@`#|>-?:" or ": " in item or " #" in item:
                self.error(index, "an indicator inside a flow sequence entry")
            else:
                values.append(item)
        return values, k + 1

    def _block_scalar(self, header, parent, index):
        match = re.fullmatch(r"([|>])([+-]?)(?:[ \t]+#.*)?", header)
        if not match:
            self.error(index, "a block scalar header with an indentation indicator or trailing text")
        style, chomping = match.groups()
        body, content, k = [], None, index + 1
        while k < len(self.lines):
            line = self.lines[k]
            if not line.strip():
                if line and content is not None and len(line) > content:
                    self.error(k, "a whitespace-only block scalar line wider than its indentation")
                body.append("")
                k += 1
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= parent:
                break
            if content is None:
                content = indent
            elif indent < content:
                self.error(k, "a block scalar line less indented than its first line")
            body.append(line[content:])
            k += 1
        self.i = k
        trailing = len(body) - len("\n".join(body).rstrip("\n").split("\n")) if any(body) else len(body)
        lines = body[:len(body) - trailing]
        if style == ">":
            if any(not line or line[0] in " \t" for line in lines):
                self.error(index, "a folded block scalar with blank or more-indented lines")
            text = " ".join(lines)
        else:
            text = "\n".join(lines)
        if not lines:
            return "\n" * trailing if chomping == "+" else ""
        if chomping == "-":
            return text
        if chomping == "+":
            return text + "\n" + "\n" * trailing
        return text + "\n"


def load_workflow(text):
    """The workflow as dicts, lists and strings; UnsupportedYAML for anything outside the subset."""
    document = _Loader(text).load()
    if not isinstance(document, dict) or "on" not in document or not isinstance(document.get("jobs"), dict) \
            or not document["jobs"] or not all(isinstance(job, dict) for job in document["jobs"].values()):
        raise UnsupportedYAML("not a workflow: a mapping with `on` and a non-empty `jobs` mapping of jobs")
    return document


# --------------------------------------------------------------------------- policy


def triggers(document):
    on = document["on"]
    if isinstance(on, str):
        return [on]
    if isinstance(on, (list, dict)) and all(isinstance(event, str) for event in on):
        return list(on)
    raise UnsupportedYAML("`on` is not an event name, a list of them or a mapping")


def top_level_conjuncts(expression):
    """The top-level `&&` operands of an expression, or None when a top-level `||` makes no operand binding."""
    parts, depth, quoted, start, k = [], 0, False, 0, 0
    while k < len(expression):
        char = expression[k]
        if quoted:
            if char == "'":
                if expression[k + 1:k + 2] == "'":
                    k += 2
                    continue
                quoted = False
        elif char == "'":
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression.startswith("||", k):
            return None
        elif depth == 0 and expression.startswith("&&", k):
            parts.append(expression[start:k])
            start = k + 2
            k += 2
            continue
        k += 1
    parts.append(expression[start:])
    return [" ".join(part.split()) for part in parts]


def excludes_pull_request(condition):
    """True only when an `if:` provably keeps its job or step off pull_request runs. The value must be one whole
    `${{ ... }}` expression or a bare expression. actions/runner splits a value that mixes literal text with `${{ }}`
    into segments and evaluates it as a `format()` string (TemplateReader.ParseScalar,
    src/Sdk/DTObjectTemplating/ObjectTemplating/TemplateReader.cs at d7bc179baf11), and a non-empty string is truthy,
    so a mixed value such as `${{ !cancelled() }} && github.event_name != 'pull_request'` excludes nothing."""
    if not isinstance(condition, str):
        return False
    expression = condition.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2]
    if "${{" in expression or "}}" in expression:
        return False
    conjuncts = top_level_conjuncts(expression.strip())
    return conjuncts is not None and EXCLUDES_PULL_REQUEST in conjuncts


def writes(permissions):
    """The write grants of a permissions value. A form this module does not recognise counts as a write."""
    if permissions == {} or permissions == "read-all":
        return []
    if isinstance(permissions, dict):
        return [f"{scope}: write" if access == "write" else f"{scope}: {access!r}"
                for scope, access in permissions.items() if access not in ("read", "none")]
    return [repr(permissions)]


def action(step):
    uses = step.get("uses") if isinstance(step, dict) else None
    return uses.split("@", 1)[0].lower() if isinstance(uses, str) else None


def cache_writes(step):
    """Why a step can write the Actions cache, or None. actions/cache saves in its post step; setup-go caches by
    default (its action.yml: `cache: default true`) and setup-node whenever package.json names a package manager
    (`package-manager-cache: default true`); the other setup actions cache only when `cache` is set."""
    name, inputs = action(step), (step.get("with") or {}) if isinstance(step, dict) else {}
    if not isinstance(inputs, dict):
        return "a `with` that is not a mapping"
    if name == "actions/cache":
        return "actions/cache restores and saves; use actions/cache/restore"
    if name == "actions/cache/save":
        return "actions/cache/save"
    if name == "actions/setup-go" and inputs.get("cache") not in FALSE:
        return "actions/setup-go without cache: false"
    if name == "actions/setup-node" and (inputs.get("cache") or inputs.get("package-manager-cache") not in FALSE):
        return "actions/setup-node with a cache or without package-manager-cache: false"
    if name in {"actions/setup-python", "actions/setup-java", "actions/setup-dotnet"} \
            and inputs.get("cache") not in (None, "", *FALSE):
        return f"{name} with a cache"
    return None


def secret_references(text):
    """Every secrets reference in one string other than secrets.GITHUB_TOKEN: `secrets.NAME` anywhere, `secrets:
    inherit`, and the bare context inside an expression (`toJSON(secrets)`, `secrets['NAME']`). GitHub does not
    allow the secrets context in an `if:` condition."""
    found = [match.group(0) for match in re.finditer(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_-]*)", text, re.IGNORECASE)
             if match.group(1).upper() != "GITHUB_TOKEN"]
    found += [match.group(0) for match in re.finditer(r"\bsecrets[ \t]*:[ \t]*inherit\b", text, re.IGNORECASE)]
    for expression in re.finditer(r"\$\{\{(.*?)\}\}", text, re.DOTALL):
        found += [f"${{{{{expression.group(1)}}}}}" for _ in re.finditer(r"\bsecrets\b(?!\.[A-Za-z_])",
                                                                         expression.group(1), re.IGNORECASE)]
    return found


def decoded_strings(node):
    """Every mapping key, mapping value and sequence item of the parsed document, after YAML decoding: escapes in
    double-quoted scalars resolved and block scalars folded, which is what GitHub evaluates."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from decoded_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from decoded_strings(item)
    elif isinstance(node, str):
        yield node


def inherited_secrets(node):
    """Every `secrets: inherit` pair, matched on decoded keys and values (so `"\\u0073ecrets": inherit` counts)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() == "secrets" and isinstance(value, str) and value.strip().lower() == "inherit":
                yield "secrets: inherit"
            yield from inherited_secrets(value)
    elif isinstance(node, list):
        for item in node:
            yield from inherited_secrets(item)


def workflow_secret_references(document, text):
    """The pull-request-secret rule's input: references in the decoded values first, since `"\\u0073ecrets.X"`
    decodes to `secrets.X` and hides from any raw-text search; then the raw text as a second net that also covers
    comments (fail closed)."""
    found = [reference for value in decoded_strings(document) for reference in secret_references(value)]
    found += list(inherited_secrets(document))
    found += [reference for reference in secret_references(text) if reference not in found]
    return found


class Violation(tuple):
    def __new__(cls, rule, workflow, where, detail):
        assert rule in RULES, rule
        return super().__new__(cls, (rule, workflow, where, detail))

    rule = property(lambda self: self[0])
    workflow = property(lambda self: self[1])
    where = property(lambda self: self[2])

    def __str__(self):
        return f"{self[1]}{':' + self[2] if self[2] else ''}: {self[0]} ({RULES[self[0]]}): {self[3]}"


def raw_violations(name, text):
    """Every rule a workflow breaks, before exemptions."""
    try:
        document = load_workflow(text)
        events = triggers(document)
    except UnsupportedYAML as error:
        return [Violation("unparseable", name, "", str(error))]
    found = []
    add = lambda rule, where, detail: found.append(Violation(rule, name, where, detail))
    pull_request = bool(PULL_REQUEST_EVENTS & set(events))
    for event in sorted(DANGEROUS_EVENTS & set(events)):
        add("dangerous-trigger", "", event)
    if "permissions" not in document:
        add("workflow-permissions-missing", "", "no top-level permissions")
    elif document["permissions"] != {}:
        add("workflow-permissions-not-empty", "", repr(document["permissions"]))
    if isinstance(document.get("permissions"), dict) and document["permissions"].get("id-token") == "write":
        add("id-token-write", "", "id-token: write at the workflow level")
    if "concurrency" not in document and events != ["workflow_call"]:
        add("workflow-concurrency", "", "no top-level concurrency")
    if pull_request:
        for reference in workflow_secret_references(document, text):
            add("pull-request-secret", "", reference)
    workflow_cache_mode = document.get("cache-mode")
    for job_id, job in document["jobs"].items():
        on_pull_request = pull_request and not excludes_pull_request(job.get("if"))
        if "permissions" in job:
            permissions = job["permissions"]
        else:
            permissions = document.get("permissions", "<the repository's default token>")
        granted = writes(permissions)
        if on_pull_request and granted:
            add("pull-request-write-scope", job_id, ", ".join(granted))
        steps = job.get("steps") or []
        if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
            add("unparseable", job_id, "steps is not a list of mappings")
            continue
        if isinstance(permissions, dict) and permissions.get("id-token") == "write" \
                and (on_pull_request or not any(action(step) in ATTEST_ACTIONS for step in steps)):
            add("id-token-write", job_id, "id-token: write without an attestation step off pull_request")
        if "uses" not in job:
            runner = job.get("runs-on")
            if not isinstance(runner, str) or runner not in HOSTED_RUNNER_LABELS:
                add("runner-label", job_id, repr(runner))
            timeout = job.get("timeout-minutes")
            if not (isinstance(timeout, str) and timeout.isdigit() and 1 <= int(timeout) <= 360):
                add("job-timeout", job_id, repr(timeout))
        for number, step in enumerate(steps, 1):
            if action(step) == "actions/checkout":
                inputs = step.get("with") if isinstance(step.get("with"), dict) else {}
                if inputs.get("persist-credentials") not in FALSE:
                    add("checkout-persist-credentials", f"{job_id}:step {number}",
                        repr(inputs.get("persist-credentials")))
            reason = cache_writes(step)
            if on_pull_request and reason and not excludes_pull_request(step.get("if")):
                add("pull-request-cache-write", f"{job_id}:step {number}", reason)
        cache_mode = job.get("cache-mode", workflow_cache_mode)
        if on_pull_request:
            if cache_mode in ("write", "write-only"):
                add("pull-request-cache-write", job_id, f"cache-mode: {cache_mode}")
            elif cache_mode not in ("none", "read"):
                add("pull-request-cache-mode", job_id, f"cache-mode: {cache_mode!r}")
    return found


def exempt(violation):
    names = EXEMPTIONS.get(violation.rule, {})
    job = violation.where.split(":", 1)[0]
    return violation.workflow in names or f"{violation.workflow}:{job}" in names


def violations(name, text):
    return [violation for violation in raw_violations(name, text) if not exempt(violation)]


def workflow_files(directory):
    """Every file GitHub runs as a workflow: both extensions it accepts."""
    return sorted(path for pattern in ("*.yml", "*.yaml") for path in directory.glob(pattern))


def check_directory(directory):
    return [violation for path in workflow_files(directory)
            for violation in violations(path.name, path.read_text(encoding="utf-8"))]


# --------------------------------------------------------------------------- planted controls

CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
BASE = f"""name: Planted control

on:
  pull_request:
  push:
    branches: [main]

permissions: {{}}
cache-mode: none

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.event.pull_request.number || github.run_id }}}}
  cancel-in-progress: ${{{{ github.event_name == 'pull_request' }}}}

jobs:
  check:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - name: Check out
        uses: {CHECKOUT}
        with:
          persist-credentials: false
      - name: Test
        run: echo "$GITHUB_SHA"
"""
EXTRA_JOB = """
  upload:
    needs: check
    if: ${{ !cancelled() && github.event_name != 'pull_request' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      contents: read
      security-events: write
    steps:
      - name: Upload
        run: echo upload
"""
ATTEST_WORKFLOW = f"""name: Planted attestation

on:
  push:
    tags:
      - 'v*'

permissions: {{}}

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: false

jobs:
  publish:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      contents: read
      id-token: write
      attestations: write
    steps:
      - name: Check out
        uses: {CHECKOUT}
        with:
          persist-credentials: false
      - name: Attest
        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
        with:
          subject-path: dist/archive.tar.gz
"""
CACHE_STEPS = """      - name: Restore
        id: restore
        uses: actions/cache/restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with:
          path: model.bin
          key: model-1
      - name: Save
        if: github.event_name != 'pull_request' && steps.restore.outputs.cache-hit != 'true'
        uses: actions/cache/save@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with:
          path: model.bin
          key: ${{ steps.restore.outputs.cache-primary-key }}
"""


def mutate(text, old, new):
    assert text.count(old) == 1, f"the planted base no longer contains {old!r} exactly once"
    return text.replace(old, new)


# (name, rule the planted file breaks, its text). Each fails with exactly that rule and nothing else.
PLANTED = [
    ("missing-permissions", "workflow-permissions-missing", mutate(BASE, "permissions: {}\n", "")),
    ("workflow-level-read", "workflow-permissions-not-empty",
     mutate(BASE, "permissions: {}\n", "permissions:\n  contents: read\n")),
    ("workflow-level-read-all", "workflow-permissions-not-empty", mutate(BASE, "permissions: {}\n", "permissions: read-all\n")),
    ("job-contents-write", "pull-request-write-scope", mutate(BASE, "      contents: read\n", "      contents: write\n")),
    ("job-write-all", "pull-request-write-scope",
     mutate(BASE, "    permissions:\n      contents: read\n", "    permissions: write-all\n")),
    ("upload-guard-with-or", "pull-request-write-scope",
     mutate(BASE + EXTRA_JOB, "if: ${{ !cancelled() && github.event_name != 'pull_request' }}",
            "if: ${{ always() || github.event_name != 'pull_request' }}")),
    # Repair round 1 (job-005, P2): a value mixing literal text with ${{ }} is a format() string, truthy on a PR.
    ("upload-guard-mixed-literal-and-expression", "pull-request-write-scope",
     mutate(BASE + EXTRA_JOB, "if: ${{ !cancelled() && github.event_name != 'pull_request' }}",
            "if: ${{ !cancelled() }} && github.event_name != 'pull_request'")),
    ("id-token-without-attestation", "id-token-write",
     mutate(ATTEST_WORKFLOW, "      - name: Attest\n        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 "
                             "# v4.2.2\n        with:\n          subject-path: dist/archive.tar.gz\n", "")),
    ("pull-request-target", "dangerous-trigger", mutate(BASE, "  pull_request:\n", "  pull_request_target:\n")),
    ("workflow-run", "dangerous-trigger",
     mutate(BASE, "  pull_request:\n  push:\n    branches: [main]\n",
            "  workflow_run:\n    workflows: [Validate]\n    types: [completed]\n")),
    ("named-secret", "pull-request-secret",
     mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: echo "$TOKEN"\n        env:\n          TOKEN: ${{ secrets.NPM_TOKEN }}')),
    ("whole-secrets-context", "pull-request-secret",
     mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: echo "$ALL"\n        env:\n          ALL: ${{ toJSON(secrets) }}')),
    # Repair round 1 (job-005, P1): references that only YAML decoding reveals, and block scalars.
    ("secret-behind-a-u-escape", "pull-request-secret",
     mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: echo "$TOKEN"\n        env:\n'
                                              '          TOKEN: "${{ \\u0073ecrets.NPM_TOKEN }}"')),
    ("secret-behind-an-x-escape", "pull-request-secret",
     mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: echo "$TOKEN"\n        env:\n'
                                              '          TOKEN: "${{ \\x73ecrets.NPM_TOKEN }}"')),
    ("secret-in-a-folded-block-scalar", "pull-request-secret",
     mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: echo "$TOKEN"\n        env:\n'
                                              '          TOKEN: >-\n            ${{\n            secrets.NPM_TOKEN }}')),
    ("secret-in-a-literal-block-scalar", "pull-request-secret",
     mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: |\n          echo "${{ secrets.NPM_TOKEN }}"')),
    ("secrets-inherit-under-a-quoted-key", "pull-request-secret",
     BASE + '\n  called:\n    uses: ./.github/workflows/called.yml\n    permissions:\n      contents: read\n'
            '    "secrets": inherit\n'),
    ("secrets-inherit-under-an-escaped-key", "pull-request-secret",
     BASE + '\n  called:\n    uses: ./.github/workflows/called.yml\n    permissions:\n      contents: read\n'
            '    "\\u0073ecrets": inherit\n'),
    ("checkout-without-with", "checkout-persist-credentials",
     mutate(BASE, "        with:\n          persist-credentials: false\n", "")),
    ("checkout-persisting", "checkout-persist-credentials",
     mutate(BASE, "persist-credentials: false", "persist-credentials: true")),
    ("self-hosted", "runner-label", mutate(BASE, "runs-on: ubuntu-24.04", "runs-on: self-hosted")),
    ("runner-list", "runner-label", mutate(BASE, "runs-on: ubuntu-24.04", "runs-on: [self-hosted, linux]")),
    ("dynamic-runner", "runner-label", mutate(BASE, "runs-on: ubuntu-24.04", "runs-on: ${{ github.event.inputs.runner }}")),
    # Repair round 1 (job-005, P2): shaped like a hosted label, but not on GitHub's list.
    ("hosted-style-unlisted-label", "runner-label", mutate(BASE, "runs-on: ubuntu-24.04", "runs-on: ubuntu-owned-private")),
    ("no-timeout", "job-timeout", mutate(BASE, "    timeout-minutes: 5\n", "")),
    ("expression-timeout", "job-timeout", mutate(BASE, "timeout-minutes: 5", "timeout-minutes: ${{ inputs.minutes }}")),
    ("combined-cache-action", "pull-request-cache-write",
     mutate(BASE, "      - name: Test\n", CACHE_STEPS.replace("actions/cache/restore@", "actions/cache@", 1)
            + "      - name: Test\n")),
    ("unguarded-save", "pull-request-cache-write",
     mutate(BASE, "      - name: Test\n", CACHE_STEPS.replace(
         "        if: github.event_name != 'pull_request' && steps.restore.outputs.cache-hit != 'true'\n", "")
            + "      - name: Test\n")),
    ("save-guard-mixed-literal-and-expression", "pull-request-cache-write",
     mutate(BASE, "      - name: Test\n", CACHE_STEPS.replace(
         "if: github.event_name != 'pull_request' && steps.restore.outputs.cache-hit != 'true'",
         "if: ${{ steps.restore.outputs.cache-hit != 'true' }} && github.event_name != 'pull_request'")
            + "      - name: Test\n")),
    ("setup-go-default-cache", "pull-request-cache-write",
     mutate(BASE, "      - name: Test\n", "      - name: Go\n        uses: actions/setup-go@"
            "b7ad1dad31e06c5925ef5d2fc7ad053ef454303e # v7.0.0\n        with:\n          go-version: '1.27.0'\n"
            "      - name: Test\n")),
    ("cache-mode-write", "pull-request-cache-write", mutate(BASE, "cache-mode: none\n", "cache-mode: write\n")),
    ("cache-mode-default", "pull-request-cache-mode", mutate(BASE, "cache-mode: none\n", "")),
    ("no-concurrency", "workflow-concurrency",
     mutate(BASE, "concurrency:\n  group: ${{ github.workflow }}-${{ github.event.pull_request.number || "
                  "github.run_id }}\n  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n\n", "")),
    ("anchor-and-alias", "unparseable",
     mutate(BASE, "    timeout-minutes: 5\n    permissions:\n      contents: read\n",
            "    timeout-minutes: 5\n    permissions: &read\n      contents: read\n    env: *read\n")),
    ("duplicate-permissions-key", "unparseable",
     mutate(BASE, "permissions: {}\n", "permissions: {}\npermissions: write-all\n")),
    ("flow-mapping", "unparseable",
     mutate(BASE, "    permissions:\n      contents: read\n", "    permissions: {contents: write}\n")),
    ("tab-indentation", "unparseable", mutate(BASE, "    timeout-minutes: 5\n", "\ttimeout-minutes: 5\n")),
    ("multi-line-plain-scalar", "unparseable",
     mutate(BASE, "    runs-on: ubuntu-24.04\n", "    runs-on: ubuntu-24.04\n      self-hosted\n")),
    ("tag", "unparseable", mutate(BASE, "permissions: {}\n", "permissions: !!map {}\n")),
]
# Variants that must pass: each guard the rules accept, exercised once.
ACCEPTED = [
    ("base", BASE),
    ("guarded-upload-job", BASE + EXTRA_JOB),
    ("attestation-off-pull-request", ATTEST_WORKFLOW),
    ("restore-and-guarded-save", mutate(mutate(BASE, "      - name: Test\n", CACHE_STEPS + "      - name: Test\n"),
                                        "cache-mode: none\n", "cache-mode: read\n")),
    ("github-token-secret", mutate(BASE, 'run: echo "$GITHUB_SHA"',
                                   'run: echo "$TOKEN"\n        env:\n          TOKEN: ${{ secrets.GITHUB_TOKEN }}')),
    ("reusable-workflow-without-concurrency",
     mutate(mutate(BASE, "  pull_request:\n  push:\n    branches: [main]\n", "  workflow_call:\n"),
            "concurrency:\n  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}\n"
            "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n\n", "")),
]


# --------------------------------------------------------------------------- tests


def _yaml():
    try:
        import yaml
    except ImportError:
        return None
    return yaml


def same(mine, theirs):
    """The loader's string-scalar tree against PyYAML's YAML 1.1 tree (PyYAML resolves `on` to True, `5` to 5)."""
    if isinstance(theirs, dict):
        if not isinstance(mine, dict) or len(mine) != len(theirs):
            return False
        keys = {("on" if key is True else str(key)): value for key, value in theirs.items()}
        return keys.keys() == mine.keys() and all(same(mine[key], keys[key]) for key in mine)
    if isinstance(theirs, list):
        return isinstance(mine, list) and len(mine) == len(theirs) and all(map(same, mine, theirs))
    if theirs is None:
        return mine is None or mine in ("", "~", "null", "Null", "NULL")
    if isinstance(theirs, bool):
        return isinstance(mine, str) and mine.lower() in (("true", "yes", "on") if theirs else ("false", "no", "off"))
    if isinstance(theirs, int):
        return isinstance(mine, str) and re.fullmatch(r"[-+]?[0-9_]+", mine) is not None \
            and int(mine.replace("_", "")) == theirs
    if isinstance(theirs, float):
        return isinstance(mine, str) and float(mine) == theirs
    return mine == str(theirs)


class StrictLoaderTests(unittest.TestCase):
    def test_every_workflow_parses_in_the_strict_subset(self):
        names = []
        for path in workflow_files(WORKFLOWS):
            with self.subTest(workflow=path.name):
                load_workflow(path.read_text(encoding="utf-8"))
                names.append(path.name)
        self.assertGreaterEqual(len(names), 21)

    def test_the_loader_agrees_with_pyyaml(self):
        yaml = _yaml()
        if yaml is None:
            self.skipTest("PyYAML not importable here; the strict loader is the only parser")
        texts = [(path.name, path.read_text(encoding="utf-8")) for path in workflow_files(WORKFLOWS)]
        texts += [(name, text) for name, rule, text in PLANTED if rule != "unparseable"] + ACCEPTED
        for name, text in texts:
            with self.subTest(workflow=name):
                self.assertTrue(same(load_workflow(text), yaml.safe_load(text)), name)

    def test_constructs_outside_the_subset_are_rejected(self):
        cases = {
            "alias": "a: &x 1\nb: *x\n", "tag": "a: !!str 1\n", "flow mapping": "a: {b: 1}\n",
            "duplicate key": "a: 1\na: 2\n", "tab": "a:\n\tb: 1\n", "document marker": "---\na: 1\n",
            "multi-line plain": "a: b\n  c\n", "multi-line quoted": "a: 'b\n  c'\n", "merge key": "<<: {}\n",
            "indentation indicator": "a: |2\n   b\n", "complex key": "? a\n: b\n", "nested flow": "a: [[1]]\n",
            "plain with colon": "a: b: c\n", "folded blank line": "a: >-\n  b\n\n  c\n",
        }
        for name, text in cases.items():
            with self.subTest(construct=name), self.assertRaises(UnsupportedYAML):
                _Loader(text).load()

    def test_crlf_line_ends_and_a_byte_order_mark_parse_like_the_plain_file(self):
        plain = load_workflow(BASE)
        self.assertEqual(load_workflow("﻿" + BASE.replace("\n", "\r\n")), plain)
        self.assertEqual(violations("crlf.yml", BASE.replace("\n", "\r\n")), [])

    def test_block_scalars_and_flow_entries_keep_their_text(self):
        document = _Loader("a: |\n  x\n    y\n\nb: >-\n  p\n  q\nc: [one, 'two, three', \"f\\u00f6\"]\nd: {}\n"
                           "e: |-\n  z\n").load()
        self.assertEqual(document, {"a": "x\n  y\n", "b": "p q", "c": ["one", "two, three", "f\u00f6"], "d": {},
                                    "e": "z"})


class RepositoryPolicyTests(unittest.TestCase):
    def test_every_workflow_meets_every_rule(self):
        self.assertEqual([str(violation) for violation in check_directory(WORKFLOWS)], [])

    def test_each_exemption_is_still_needed(self):
        # An exemption whose rule no longer fires is dead and must go, so this set cannot grow silently.
        raw = {(violation.rule, violation.workflow, violation.where.split(":", 1)[0])
               for path in workflow_files(WORKFLOWS)
               for violation in raw_violations(path.name, path.read_text(encoding="utf-8"))}
        for rule, names in EXEMPTIONS.items():
            for name in names:
                workflow, _, job = name.partition(":")
                with self.subTest(rule=rule, exemption=name):
                    self.assertTrue(any(r == rule and w == workflow and (not job or j == job) for r, w, j in raw))

    def test_hash_bound_exemptions_are_still_bound(self):
        for name, binding in HASH_BOUND.items():
            with self.subTest(workflow=name):
                digest = hashlib.sha256((WORKFLOWS / name).read_bytes()).hexdigest()
                self.assertIn(digest, (ROOT / binding).read_text(encoding="utf-8"),
                              f"{binding} no longer binds {name}: move it to `permissions: {{}}` with a concurrency "
                              "group and drop it from HASH_BOUND")

    def test_write_grants_are_the_reviewed_inventory(self):
        grants = {}
        for path in workflow_files(WORKFLOWS):
            document = load_workflow(path.read_text(encoding="utf-8"))
            for job_id, job in document["jobs"].items():
                granted = writes(job.get("permissions", document.get("permissions")))
                if granted:
                    grants[f"{path.name}:{job_id}"] = granted
        self.assertEqual(grants, WRITE_GRANTS)

    def test_no_job_pushes_with_a_persisted_credential(self):
        # The one job that pushes keeps persist-credentials: false and sends the token for that command alone.
        pushers = set()
        for path in workflow_files(WORKFLOWS):
            for job_id, job in load_workflow(path.read_text(encoding="utf-8"))["jobs"].items():
                runs = "\n".join(step.get("run", "") for step in job.get("steps", []))
                if re.search(r"(?m)^\s*git(?:\s+-c\s+\S+)*\s+push\b", runs):
                    pushers.add(f"{path.name}:{job_id}")
        self.assertEqual(pushers, {"catalog-freshness.yml:propose"})
        propose = load_workflow((WORKFLOWS / "catalog-freshness.yml").read_text(encoding="utf-8"))["jobs"]["propose"]
        push = next(step for step in propose["steps"] if "git push" in step.get("run", ""))
        self.assertIn("GIT_CONFIG_VALUE_0=", push["run"])
        self.assertIn("::add-mask::", push["run"])

    def test_pull_request_jobs_hold_no_secret_and_no_write(self):
        # The direct form of the consensus' first residual: list what a pull_request run can reach.
        for path in workflow_files(WORKFLOWS):
            text = path.read_text(encoding="utf-8")
            document = load_workflow(text)
            if not PULL_REQUEST_EVENTS & set(triggers(document)):
                continue
            with self.subTest(workflow=path.name):
                self.assertEqual(secret_references(text), [])
                for job_id, job in document["jobs"].items():
                    if not excludes_pull_request(job.get("if")):
                        self.assertEqual(writes(job.get("permissions", document.get("permissions"))), [], job_id)


class PlantedViolationTests(unittest.TestCase):
    """Negative controls: each planted workflow sits alone in a temporary directory and fails with its rule named."""

    def check_planted(self, name, text, extension=".yml"):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / f"{name}{extension}").write_text(text, encoding="utf-8")
            return check_directory(Path(temporary))

    def test_every_rule_has_a_planted_violation(self):
        self.assertEqual({rule for _, rule, _ in PLANTED}, set(RULES))

    def test_each_planted_workflow_fails_with_exactly_its_rule(self):
        for name, rule, text in PLANTED:
            with self.subTest(planted=name):
                found = self.check_planted(name, text)
                self.assertEqual({violation.rule for violation in found}, {rule}, [str(v) for v in found])
                self.assertTrue(all(RULES[rule] in str(violation) for violation in found))

    def test_the_accepted_variants_pass(self):
        for name, text in ACCEPTED:
            with self.subTest(variant=name):
                self.assertEqual([str(violation) for violation in self.check_planted(name, text)], [])

    def test_a_workflow_level_id_token_grant_breaks_both_permission_rules(self):
        # No planted file can break id-token-write alone at the workflow level: any top-level grant is also not `{}`.
        text = mutate(ATTEST_WORKFLOW, "permissions: {}\n", "permissions:\n  id-token: write\n")
        self.assertEqual({violation.rule for violation in self.check_planted("workflow-id-token", text)},
                         {"workflow-permissions-not-empty", "id-token-write"})

    def test_only_a_whole_or_bare_expression_can_exclude_pull_requests(self):
        # Repair round 1 (job-005, P2): actions/runner evaluates a mixed literal/expression value as a format() string.
        accepted = ("github.event_name != 'pull_request'",
                    "${{ github.event_name != 'pull_request' }}",
                    "${{ !cancelled() && github.event_name != 'pull_request' }}",
                    "github.event_name != 'pull_request' && steps.restore.outputs.cache-hit != 'true'")
        refused = ("${{ !cancelled() }} && github.event_name != 'pull_request'",
                   "github.event_name != 'pull_request' && ${{ !cancelled() }}",
                   "${{ !cancelled() }} && ${{ github.event_name != 'pull_request' }}",
                   "${{ always() || github.event_name != 'pull_request' }}",
                   "github.event_name!='pull_request'", None, "")
        for condition in accepted:
            with self.subTest(accepted=condition):
                self.assertTrue(excludes_pull_request(condition))
        for condition in refused:
            with self.subTest(refused=condition):
                self.assertFalse(excludes_pull_request(condition))

    def test_an_escaped_reference_hides_from_the_raw_scan_but_not_from_the_rule(self):
        # Repair round 1 (job-005, P1): the rule reads decoded values; the raw scan stays as a second net.
        for name in ("secret-behind-a-u-escape", "secret-behind-an-x-escape", "secrets-inherit-under-a-quoted-key",
                     "secrets-inherit-under-an-escaped-key"):
            text = next(text for planted, _, text in PLANTED if planted == name)
            with self.subTest(planted=name):
                self.assertEqual(secret_references(text), [], "the raw text alone shows no reference")
                self.assertTrue(workflow_secret_references(load_workflow(text), text))

    def test_the_runner_allowlist_is_exact(self):
        # Repair round 1 (job-005, P2): a set of documented labels, not a prefix pattern.
        self.assertIn("ubuntu-24.04", HOSTED_RUNNER_LABELS)
        self.assertIn("macos-15", HOSTED_RUNNER_LABELS)
        for label in ("ubuntu-owned-private", "ubuntu-24.04-gpu", "macos-15-large", "windows-latest-8-cores",
                      "self-hosted", "Ubuntu-24.04", " ubuntu-24.04"):
            with self.subTest(label=label):
                self.assertNotIn(label, HOSTED_RUNNER_LABELS)

    def test_a_secret_named_in_prose_is_not_a_reference_but_one_in_a_comment_is(self):
        self.assertEqual(secret_references("# no secrets. The job reads secrets, tokens and keys.\n"), [])
        self.assertEqual(secret_references("# ${{ secrets.NPM_TOKEN }}\n"), ["secrets.NPM_TOKEN"])
        self.assertEqual(secret_references("x: ${{ secrets.GITHUB_TOKEN }}\n"), [])
        self.assertEqual(len(secret_references("x: ${{ secrets['NPM_TOKEN'] }}\n")), 1)

    def test_a_yaml_extension_is_checked_too(self):
        found = self.check_planted("missing-permissions", PLANTED[0][2], extension=".yaml")
        self.assertEqual({violation.rule for violation in found}, {"workflow-permissions-missing"})

    def test_exemptions_follow_the_file_name_not_the_rule(self):
        # The named exemptions apply to the repository's own files only: the same text under another name fails.
        text = (WORKFLOWS / "native-offhost-restore.yml").read_text(encoding="utf-8")
        self.assertEqual(violations("native-offhost-restore.yml", text), [])
        self.assertEqual({violation.rule for violation in self.check_planted("renamed", text)},
                         {"workflow-permissions-not-empty", "workflow-concurrency"})


FIVE_AUDITS = ("excessive-permissions", "dangerous-triggers", "cache-poisoning", "artipacked", "template-injection")
ZIZMOR_PLANTED = {
    "excessive-permissions": mutate(mutate(BASE, "permissions: {}\n", "permissions: write-all\n"),
                                    "    permissions:\n      contents: read\n", ""),
    "dangerous-triggers": mutate(BASE, "  pull_request:\n", "  pull_request_target:\n"),
    "cache-poisoning": mutate(mutate(ATTEST_WORKFLOW, "      - name: Attest\n",
                                     "      - name: Set up Node with a dependency cache\n        uses: actions/setup-node@"
                                     "820762786026740c76f36085b0efc47a31fe5020 # v7.0.0\n        with:\n"
                                     "          node-version: '24'\n          cache: npm\n      - name: Attest\n"),
                              "name: Planted attestation", "name: Planted release"),
    "artipacked": mutate(BASE, "        with:\n          persist-credentials: false\n", ""),
    "template-injection": mutate(BASE, 'run: echo "$GITHUB_SHA"', 'run: echo "${{ github.event.pull_request.title }}"'),
}


def zizmor_findings(path, cwd, persona="pedantic"):
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN"} and not key.startswith("ZIZMOR_")}
    result = subprocess.run(
        [ZIZMOR, "--offline", "--no-config", "--no-ignores", "--no-progress", "--persona", persona,
         "--strict-collection", "--format", "json", "--cache-dir", str(cwd / "cache"), str(path)],
        cwd=cwd, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode not in (0, 11, 12, 13, 14):
        raise AssertionError(f"zizmor failed (exit {result.returncode}): {result.stderr[:2000]}")
    return json.loads(result.stdout)


class ZizmorConfigurationTests(unittest.TestCase):
    """zizmor reads no configuration and honours no ignore comment in CI, so a commit cannot suppress a finding; the
    regular-persona gate in validate.yml fails on every finding (exit 11-14)."""

    def invocations(self):
        found = []
        for path in workflow_files(WORKFLOWS):
            for job_id, job in load_workflow(path.read_text(encoding="utf-8"))["jobs"].items():
                for step in job.get("steps", []):
                    command = re.sub(r"\\\n\s*", " ", step.get("run", ""))
                    for line in command.splitlines():
                        if re.search(r"(?:^|[\s;&|(])zizmor\s", line) and not line.lstrip().startswith("#"):
                            found.append((f"{path.name}:{job_id}", line.strip()))
        return found

    def test_every_zizmor_invocation_loads_no_config_and_honours_no_ignore(self):
        found = self.invocations()
        self.assertEqual(sorted(name for name, _ in found),
                         ["security-scan.yml:zizmor-online", "validate.yml:validate"])
        for name, line in found:
            with self.subTest(invocation=name):
                self.assertRegex(line, r"(?:^|\s)--no-config(?:\s|$)")
                self.assertRegex(line, r"(?:^|\s)--no-ignores(?:\s|$)")
                self.assertNotRegex(line, r"(?:^|\s)(?:-c|--config)[\s=]")

    def test_no_configuration_file_ignore_comment_or_environment_override_exists(self):
        # zizmor's local discovery (docs/configuration.md at v1.30.1): .github/zizmor.yml, .github/zizmor.yaml,
        # zizmor.yml, zizmor.yaml. --no-config already ignores them; their absence keeps a reader from assuming one.
        for name in (".github/zizmor.yml", ".github/zizmor.yaml", "zizmor.yml", "zizmor.yaml"):
            self.assertFalse((ROOT / name).exists(), name)
        for path in workflow_files(WORKFLOWS):
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotRegex(text, r"zizmor:\s*ignore")
                # ZIZMOR_CONFIG, ZIZMOR_OFFLINE and ZIZMOR_NO_ONLINE_AUDITS would each weaken the gate silently.
                self.assertNotRegex(text, r"\bZIZMOR_[A-Z_]+")

    def test_the_analyzer_stays_pinned_by_hash(self):
        requirements = (ROOT / ".github/requirements-ci.txt").read_text(encoding="utf-8")
        self.assertRegex(requirements, r"(?m)^zizmor==1\.30\.1 \\\n(?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n)+")
        install = next(step["run"] for step in load_workflow((WORKFLOWS / "validate.yml").read_text(encoding="utf-8"))
                       ["jobs"]["validate"]["steps"] if "requirements-ci.txt" in step.get("run", ""))
        self.assertIn("--require-hashes", install)


@unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
class ZizmorPedanticAuditTests(unittest.TestCase):
    """The five audits the consensus names, at the pedantic persona: the regular gate misses some of their shapes (a
    single job under a workflow-level write-all, measured with zizmor 1.30.1 on 2026-10-04)."""

    def test_no_workflow_has_a_finding_from_the_five_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            findings = zizmor_findings(WORKFLOWS, Path(temporary))
        hits = sorted({(finding["ident"], json.dumps(finding["locations"][0]["symbolic"]["key"]))
                       for finding in findings if finding["ident"] in FIVE_AUDITS})
        self.assertEqual(hits, [])

    def test_each_planted_audit_fixture_fires(self):
        self.assertEqual(set(ZIZMOR_PLANTED), set(FIVE_AUDITS))
        for ident, text in ZIZMOR_PLANTED.items():
            with self.subTest(audit=ident), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "planted.yml"
                path.write_text(text, encoding="utf-8")
                self.assertIn(ident, {finding["ident"] for finding in zizmor_findings(path, Path(temporary))})

    def test_the_regular_gate_misses_the_single_job_write_all(self):
        # Why this pass exists beside validate.yml's regular-persona gate.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "planted.yml"
            path.write_text(ZIZMOR_PLANTED["excessive-permissions"], encoding="utf-8")
            regular = zizmor_findings(path, Path(temporary), persona="regular")
        self.assertNotIn("excessive-permissions", {finding["ident"] for finding in regular})


if __name__ == "__main__":
    unittest.main()
