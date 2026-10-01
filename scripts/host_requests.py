#!/usr/bin/env python3
"""Track GitHub host requests for one host role: list, poll, claim and report.

A request is a GitHub issue that carries a role's request label from adoption/host-roles.json,
opened with .github/ISSUE_TEMPLATE/workstation-request.yml or with ``gh issue create`` and a body
from ``compose``, which renders the form's layout. Every host signs in as the same owner account,
so GitHub cannot tell hosts apart: the requesting host is routing data inside the body, and trust
rests only on the author (the owner, author_association OWNER, user.type User, no GitHub App).
Labels, titles and body text never grant trust; an issue form applies its labels for anyone. No
output of this tool carries an untrusted item's title or requesting-host text (WITHHELD stands in),
so a coordinator session can read it without taking in text a stranger wrote. ``status
--show-untrusted-text`` is the one opt-in exception, for a person reading a terminal directly; a
session must never pass it, and the text it prints must never be pasted back into a session.

This tool never executes, evaluates or forwards issue text to a model. A coordinator session on
the target host reads a request and decides what to run. All GitHub I/O is the native gh CLI
(``gh api`` with list arguments, no shell, the token stays inside gh); parsing and state
derivation are pure functions. Only claim, block, done, decline and ensure-labels write, and each
takes --dry-run, which prints the gh calls and makes no GitHub call at all.

Decision and alternatives: docs/decisions/2026-09-25-host-request-lane.md. Operator and
requester steps: recipes/host-request-lane.md.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import http.client
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from .validate import PRIVATE_CONTENT
except ImportError:
    from validate import PRIVATE_CONTENT

ROOT = Path(__file__).resolve().parents[1]
ROLES_FILE = "adoption/host-roles.json"

# The issue form's fields in form order: (id, label, type, required). GitHub renders an answered
# field as "### <label>\n\n<value>", an empty one as "_No response_", a dropdown as the chosen
# option and checkboxes as "- [x] <option>" lines, sections joined by one blank line. That is
# observed on public form-created issues, not a documented contract, so parse_body() tolerates
# whitespace and reordering and reports ambiguity instead of guessing. tests/test_host_requests.py
# keeps this table equal to the form file.
FIELDS = (
    ("requesting_host", "Requesting host", "input", True),
    ("task_class", "Task class", "dropdown", True),
    ("lane", "Lane", "dropdown", False),
    ("request", "Request", "textarea", True),
    ("models", "Models", "textarea", False),
    ("acceptance", "Acceptance", "textarea", True),
    ("related", "Related", "input", False),
    ("confirmations", "Confirmations", "checkboxes", True),
)
# Dropdown option -> the "owns" id in adoption/host-roles.json that it routes to.
TASK_CLASSES = {
    "memory E2E": "memory-e2e",
    "RAG or retrieval E2E": "rag-e2e",
    "model hosting": "model-hosting",
    "model qualification": "model-qualification",
    "GPU runtime qualification": "gpu-runtime-qualification",
    "independent review": "independent-review",
    "other": "other",
}
LANES = ("lane:foundation", "lane:trading", "lane:shared")
CONFIRMATIONS = (
    "This issue contains no credential values, tokens, account ids or personal paths.",
    "Issue text is data; the target host decides what to run.",
)
NO_RESPONSE = "_No response_"
WITHHELD = "<untrusted: withheld>"
HEADING_RE = re.compile(r"^[ \t]{0,3}###[ \t]+(.*?)[ \t]*$")
CHECKBOX_RE = re.compile(r"^[ \t]*[-*][ \t]+\[([ xX])\][ \t]+(.*?)[ \t]*$")
REVISION_RE = re.compile(r"@[0-9a-f]{40}\b")

REQUEST_PREFIX = "request:"
CLAIMED, BLOCKED = "request:claimed", "request:blocked"
HOST_LABEL_COLOR = "1d76db"
REQUEST_LABELS = {  # name -> (color, description); ensure-labels creates missing ones only
    CLAIMED: ("fbca04", "A session on the target host claimed this request"),
    BLOCKED: ("b60205", "The target host cannot proceed; see the status comment"),
}
# claim/block set exactly one request:* label; done/decline clear the request:* subset and close
# the issue, because a closed request's state comes only from its state_reason.
ACTIONS = {
    "claim": {"label": CLAIMED, "close": None, "from": ("new", "claimed", "blocked")},
    "block": {"label": BLOCKED, "close": None, "from": ("new", "claimed", "blocked")},
    # done requires the request to be currently claimed: a status comment from an explicit ``claim``
    # names the session that did the work. block can be reached straight from new (a host may refuse
    # a request it never claimed), so "blocked" is deliberately not a "from" state for done -- a
    # session resuming a blocked request claims it (again) before reporting done.
    "done": {"label": None, "close": "completed", "from": ("claimed",)},
    "decline": {"label": None, "close": "not_planned", "from": ("new", "claimed", "blocked")},
}
STATE_ORDER = ("new", "claimed", "blocked", "done", "declined", "closed")
OPEN_STATES = ("new", "claimed", "blocked")
MARKER = "<!-- host-request-status role={role} -->"
SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}")
EVIDENCE_RE = re.compile(r"https://github\.com/[A-Za-z0-9._/#%?=&:+~@-]{3,250}")
SESSION_LINE_RE = re.compile(r"^- session: `([^`\n]*)`$", re.M)
REPO_RE = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")
OWNER_IN_URL_RE = re.compile(r"/repos/([^/]+)/[^/]+(?:/|$)")
NOTIFY_TOPIC_RE = re.compile(r"/[A-Za-z0-9_-]{1,64}")
NOTIFY_HOSTS = ("127.0.0.1", "localhost")
NOTIFY_CAP = 10
CLOSED_WINDOW_DAYS = 14
PER_PAGE = 100
MAX_PAGES = 10
GH_TIMEOUT = 60
EXIT_GH, EXIT_USAGE, EXIT_REFUSED = 1, 2, 3


class GhError(RuntimeError):
    """A gh call failed; the message is bounded and never echoes a token (gh does not print it)."""


class Refused(RuntimeError):
    """A write was refused before any write call: untrusted item, wrong role or state."""


class UsageError(ValueError):
    """Invalid local input (arguments, files, state directory)."""


# ---------------------------------------------------------------------------------------------
# Pure helpers


def clean(value, limit: int) -> str:
    """Printable single-line text: control and format characters (including bidi overrides) become
    spaces, whitespace collapses, and at most ``limit`` characters remain."""
    if value is None:
        return ""
    text = "".join(" " if unicodedata.category(ch).startswith("C") else ch for ch in str(value))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: max(limit - 3, 0)].rstrip() + "..."


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.timezone.utc)


def human_age(seconds: int) -> str:
    if seconds < 3600:
        return f"{max(seconds, 0) // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def private_findings(text: str) -> list[str]:
    """Which scripts/validate.py private-content patterns ``text`` matches (never the match)."""
    return [description for description, pattern in PRIVATE_CONTENT if pattern.search(text)]


def load_roles(root: Path = ROOT) -> dict:
    document = json.loads((root / ROLES_FILE).read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise UsageError(f"{ROLES_FILE}: schema_version must be 1")
    return document


def role_spec(roles: dict, role: str) -> dict:
    spec = roles.get("roles", {}).get(role)
    if spec is None:
        raise UsageError(f"unknown role {role!r}; known: {', '.join(sorted(roles.get('roles', {})))}")
    return spec


def requester_status(host: str | None, roles: dict) -> dict:
    """Whether ``host`` is a listed peer. Unknown hosts are flagged, not rejected."""
    peers = {peer["host_id"]: peer for peer in roles.get("peers", [])}
    peer = peers.get(host or "")
    return {"known": peer is not None, "superseded_by": (peer or {}).get("superseded_by")}


def label_names(item: dict) -> list[str]:
    names = []
    for label in item.get("labels") or []:
        name = label.get("name") if isinstance(label, dict) else label
        if isinstance(name, str):
            names.append(name)
    return names


def item_kind(item: dict) -> str:
    return "pr" if "pull_request" in item else "issue"


def repository_owner(item: dict) -> str | None:
    """The repository owner's login from the item's own API URLs (issues: repository_url;
    comments: issue_url)."""
    for key in ("repository_url", "issue_url", "url"):
        match = OWNER_IN_URL_RE.search(str(item.get(key) or ""))
        if match:
            return match.group(1)
    return None


def trust(item: dict) -> tuple[bool, list[str]]:
    """Whether an issue, pull request or comment is the owner account's own. Fails closed on any
    missing field. Nothing else (labels, title, body, a requesting-host value) grants trust."""
    reasons = []
    if item.get("author_association") != "OWNER":
        reasons.append(f"author_association is {clean(item.get('author_association'), 32) or 'missing'}")
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    if user.get("type") != "User":
        reasons.append(f"user.type is {clean(user.get('type'), 32) or 'missing'}")
    if "performed_via_github_app" not in item:
        reasons.append("performed_via_github_app is missing")
    elif item["performed_via_github_app"] is not None:
        reasons.append("created through a GitHub App")
    owner = repository_owner(item)
    if owner is None or str(user.get("login") or "").lower() != owner.lower():
        reasons.append("author is not the repository owner")
    return not reasons, reasons


def derive_state(item: dict) -> str:
    """new | claimed | blocked from the request:* label of an open item; done | declined from a
    closed item's state_reason (completed | not_planned); any other closed reason (duplicate, or a
    pull request's null) is ``closed``. Nothing else is read."""
    if item.get("state") == "closed":
        return {"completed": "done", "not_planned": "declined"}.get(item.get("state_reason"), "closed")
    names = label_names(item)
    if BLOCKED in names:
        return "blocked"
    if CLAIMED in names:
        return "claimed"
    return "new"


def _normalize_label(text: str) -> str:
    return " ".join(text.split())


def parse_body(body: str | None) -> dict:
    """Split a form-rendered body into {field id: value or None}. Only a line that is exactly a
    known field heading starts a section, so other headings a requester types stay inside the
    value; the first occurrence of each field wins, which keeps the single-line fields at the top
    (requesting host, task class, lane) exact. ``_No response_`` and blank values are None; the
    checkboxes field is the list of checked options. ``warnings`` lists duplicate, out-of-order
    and missing required fields."""
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    by_label = {_normalize_label(label): field_id for field_id, label, _, _ in FIELDS}
    kinds = {field_id: kind for field_id, _, kind, _ in FIELDS}
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in text.split("\n"):
        match = HEADING_RE.match(line)
        field_id = by_label.get(_normalize_label(match.group(1))) if match else None
        if field_id is None:
            sections[-1][1].append(line)
        else:
            sections.append((field_id, []))
    values: dict = {field_id: None for field_id, _, _, _ in FIELDS}
    seen: list[str] = []
    warnings = []
    for field_id, lines in sections[1:]:
        if field_id in seen:
            warnings.append(f"duplicate heading: {field_id}")
            continue
        seen.append(field_id)
        value = "\n".join(lines).strip()
        if kinds[field_id] == "checkboxes":
            values[field_id] = [match.group(2) for match in map(CHECKBOX_RE.match, value.split("\n"))
                                if match and match.group(1) in "xX"]
        else:
            values[field_id] = None if value in ("", NO_RESPONSE) else value
    order = [field_id for field_id, _, _, _ in FIELDS]
    if seen != sorted(seen, key=order.index):
        warnings.append("headings out of form order")
    warnings.extend(f"missing field: {field_id}" for field_id, _, _, required in FIELDS
                    if required and field_id not in seen)
    values["warnings"] = warnings
    return values


def render_body(values: dict) -> str:
    """The issue form's rendering of ``values`` (field id -> text; confirmations -> checked
    options), which parse_body() reads back unchanged."""
    sections = []
    for field_id, label, kind, _ in FIELDS:
        value = values.get(field_id)
        if kind == "checkboxes":
            checked = set(value or ())
            text = "\n".join(f"- [{'x' if option in checked else ' '}] {option}" for option in CONFIRMATIONS)
        else:
            text = (value or "").strip() or NO_RESPONSE
        sections.append(f"### {label}\n\n{text}")
    return "\n\n".join(sections)


def request_fields(body: str | None, roles: dict) -> dict:
    """The routing fields shown for a request. Values are untrusted data: the requesting host is
    cleaned and bounded, the task class is reported only as a known option's id."""
    parsed = parse_body(body)
    host = clean(parsed.get("requesting_host"), 64) or None
    requester = requester_status(host, roles)
    task = parsed.get("task_class")
    return {
        "requesting_host": host,
        "known_requester": requester["known"],
        "requester_superseded_by": requester["superseded_by"],
        "task_class": TASK_CLASSES.get(clean(task, 64)) or ("unrecognized" if task else None),
        "parse_warnings": parsed["warnings"],
    }


def summarize(item: dict, roles: dict, now: dt.datetime, *, reveal_untrusted: bool = False) -> dict:
    """``reveal_untrusted`` is the ``status --show-untrusted-text`` escape hatch: it shows an
    untrusted item's real title and requesting host instead of WITHHELD. It must default to False
    everywhere else (poll, lanes), since only a human explicitly reading a terminal opts into it."""
    kind = item_kind(item)
    trusted, reasons = trust(item)
    created = parse_time(item.get("created_at")) or now
    age = int((now - created).total_seconds())
    fields = request_fields(item.get("body"), roles) if kind == "issue" else {
        "requesting_host": None, "known_requester": False, "requester_superseded_by": None,
        "task_class": None, "parse_warnings": []}
    if not trusted and not reveal_untrusted:  # a stranger's free text; the task class is an allowlisted id
        fields.update(requesting_host=WITHHELD if fields["requesting_host"] else None,
                      known_requester=False, requester_superseded_by=None)
    return {
        "number": item.get("number"),
        "kind": kind,
        "title": clean(item.get("title"), 120) if trusted or reveal_untrusted else WITHHELD,
        "state": derive_state(item),
        "trusted": trusted,
        "untrusted_reasons": reasons,
        **fields,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "closed_at": item.get("closed_at"),
        "age_seconds": age,
        "age": human_age(age),
        "url": item.get("html_url"),
    }


def poll_record(summary: dict) -> dict:
    """The per-item state poll keeps: no title and no body text. The requesting host is kept only
    when it is a listed peer and the task class only as a known option id, and neither for an
    untrusted item, whose body may name a real peer."""
    trusted = summary["trusted"]
    return {
        "kind": summary["kind"],
        "state": summary["state"],
        "trusted": trusted,
        "requesting_host": summary["requesting_host"] if trusted and summary["known_requester"] else "unknown",
        "task_class": summary["task_class"] if trusted and summary["task_class"] in TASK_CLASSES.values() else "unknown",
        "updated_at": summary["updated_at"],
    }


def diff_states(previous: dict, current: dict, *, baseline: bool = False) -> list[dict]:
    """One event per new item, state change or updated_at change, in issue-number order.
    ``baseline`` (no previous state file) marks every event so the first poll notifies nobody."""
    events = []
    for number in sorted(current, key=int):
        record, before = current[number], previous.get(number)
        base = {"number": int(number), "kind": record["kind"], "state": record["state"],
                "trusted": record["trusted"], "requesting_host": record["requesting_host"],
                "task_class": record["task_class"], "updated_at": record["updated_at"]}
        if before is None:
            event = {"event": "new", **base}
        elif before.get("state") != record["state"]:
            event = {"event": "state", "from": before.get("state"), **base}
        elif before.get("updated_at") != record["updated_at"]:
            event = {"event": "updated", **base}
        else:
            continue
        if baseline:
            event["baseline"] = True
        events.append(event)
    return events


def notice(event: dict) -> str:
    """The fixed one-line notice: allowlisted values only, never a title or body text."""
    label = event["state"] if event["event"] == "state" else event["event"]
    line = f"#{event['number']} {label} from {event['requesting_host']} ({event['task_class']})"
    return line if event["trusted"] else line + " untrusted"


def check_notify_url(url: str) -> str:
    """Accept only a loopback ntfy topic URL: http, host 127.0.0.1 or localhost, a single topic
    path segment, no credentials, query or fragment."""
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise UsageError(f"--notify-url is not a valid URL: {error}") from None
    if (parts.scheme != "http" or parts.hostname not in NOTIFY_HOSTS or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or not NOTIFY_TOPIC_RE.fullmatch(parts.path) or (port is not None and not 0 < port < 65536)):
        raise UsageError("--notify-url must be http://127.0.0.1[:PORT]/TOPIC or http://localhost[:PORT]/TOPIC")
    return url


def lane_hygiene(items: list[dict]) -> dict:
    """docs/lanes.md: every pull request carries exactly one of the three lane labels, and a
    lane:shared one needs the other lane's acknowledgement (listed, not checked here). An
    untrusted item's title is WITHHELD, as in status."""
    report = {"open_pull_requests": 0, "open_issues": 0, "pull_requests_missing_lane": [],
              "pull_requests_with_multiple_lanes": [], "pull_requests_with_unknown_lane": [],
              "lane_shared_needing_acknowledgement": [], "host_labelled": []}
    for item in sorted(items, key=lambda entry: entry.get("number") or 0):
        names = label_names(item)
        lanes = sorted(name for name in names if name.startswith("lane:"))
        hosts = sorted(name for name in names if name.startswith("host:"))
        entry = {"number": item.get("number"), "kind": item_kind(item),
                 "title": clean(item.get("title"), 120) if trust(item)[0] else WITHHELD}
        if entry["kind"] == "pr":
            report["open_pull_requests"] += 1
            if not lanes:
                report["pull_requests_missing_lane"].append(entry)
            elif len(lanes) > 1:
                report["pull_requests_with_multiple_lanes"].append({**entry, "lanes": lanes})
            unknown = [name for name in lanes if name not in LANES]
            if unknown:
                report["pull_requests_with_unknown_lane"].append({**entry, "lanes": unknown})
            if "lane:shared" in lanes:
                report["lane_shared_needing_acknowledgement"].append(entry)
        else:
            report["open_issues"] += 1
        if hosts:
            report["host_labelled"].append({**entry, "labels": hosts})
    return report


def status_body(role: str, host_id: str, state: str, session: str, when: dt.datetime, *,
                reason: str | None = None, evidence: str | None = None,
                previous_session: str | None = None) -> str:
    lines = [MARKER.format(role=role), f"**Host request status: {state}**", "",
             f"- host: `{host_id}` (role `{role}`)", f"- session: `{session}`"]
    if previous_session:
        lines.append(f"- previous session: `{previous_session}`")
    lines.append(f"- updated: {iso(when)}")
    if reason:
        lines.append(f"- reason: {reason}")
    if evidence:
        lines.append(f"- evidence: {evidence}")
    lines += ["", "Written by `scripts/host_requests.py`. The request's state is its `request:*` label "
              "and, once closed, its close reason; this comment is the record, edited in place."]
    return "\n".join(lines)


def find_status_comment(comments: list[dict], role: str) -> dict | None:
    """The owner's own status comment for ``role``. Untrusted comments that copy the marker are
    ignored, so they are never edited or adopted."""
    marker = MARKER.format(role=role)
    for comment in comments:
        if str(comment.get("body") or "").lstrip().startswith(marker) and trust(comment)[0]:
            return comment
    return None


def planned_labels(item: dict, action: str) -> list[str]:
    """The issue's labels with the request:* subset replaced by the action's one label (or none)."""
    kept = [name for name in label_names(item) if not name.startswith(REQUEST_PREFIX)]
    target = ACTIONS[action]["label"]
    return kept + ([target] if target else [])


def check_actionable(item: dict, role_label: str, action: str) -> None:
    trusted, reasons = trust(item)
    number = item.get("number")
    if not trusted:
        raise Refused(f"#{number} is untrusted ({'; '.join(reasons)}); it is never claimable")
    if role_label not in label_names(item):
        raise Refused(f"#{number} does not carry {role_label}")
    if action in ("done", "decline") and item_kind(item) == "pr":
        raise Refused(f"#{number} is a pull request: merge or close it natively (claim and block still apply)")
    state = derive_state(item)
    if state not in ACTIONS[action]["from"]:
        raise Refused(f"#{number} is {state}; {action} applies to {' or '.join(ACTIONS[action]['from'])}")


def label_plan(roles: dict) -> list[dict]:
    specs = [{"name": spec["request_label"], "color": HOST_LABEL_COLOR,
              "description": clean(f"Request for the {role} host ({spec['host_id']})", 100)}
             for role, spec in sorted(roles.get("roles", {}).items())]
    specs += [{"name": name, "color": color, "description": description}
              for name, (color, description) in REQUEST_LABELS.items()]
    return specs


# ---------------------------------------------------------------------------------------------
# GitHub I/O


def gh_environment() -> dict:
    environment = dict(os.environ)
    environment.update({"GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "NO_COLOR": "1"})
    return environment


class Gh:
    """``gh api`` in this checkout, so the {owner}/{repo} placeholders resolve from its remote
    (``--repo`` overrides them). ``runner`` is subprocess.run or a test double."""

    def __init__(self, runner=subprocess.run, *, repo: str | None = None, executable: str = "gh", cwd: Path = ROOT):
        self.runner, self.repo, self.executable, self.cwd = runner, repo, executable, cwd

    def endpoint(self, path: str) -> str:
        return f"repos/{self.repo or '{owner}/{repo}'}/{path}"

    def argv(self, method: str, path: str, payload=None) -> list[str]:
        argv = [self.executable, "api"]
        if method != "GET":
            argv += ["--method", method]
        argv.append(self.endpoint(path))
        if payload is not None:
            argv += ["--input", "-"]
        return argv

    def call(self, method: str, path: str, payload=None):
        argv = self.argv(method, path, payload)
        try:
            process = self.runner(argv, input="" if payload is None else json.dumps(payload),
                                  capture_output=True, text=True, timeout=GH_TIMEOUT, cwd=str(self.cwd),
                                  env=gh_environment(), check=False)
        except (OSError, subprocess.SubprocessError) as error:
            raise GhError(f"gh api {method} {path}: {type(error).__name__}: {clean(error, 200)}") from None
        if process.returncode != 0:
            raise GhError(f"gh api {method} {path} exited {process.returncode}: {clean(process.stderr, 300)}")
        if not (process.stdout or "").strip():
            return None
        try:
            return json.loads(process.stdout)
        except ValueError:
            raise GhError(f"gh api {method} {path}: response is not JSON") from None

    def pages(self, path: str, query: dict) -> tuple[list, bool]:
        """Every page of a list endpoint (at most MAX_PAGES of PER_PAGE); True when capped."""
        items: list = []
        for page in range(1, MAX_PAGES + 1):
            batch = self.call("GET", f"{path}?{urllib.parse.urlencode({**query, 'per_page': PER_PAGE, 'page': page})}")
            if not isinstance(batch, list):
                raise GhError(f"gh api GET {path}: expected a JSON array")
            items.extend(batch)
            if len(batch) < PER_PAGE:
                return items, False
        return items, True


def fetch_role_items(gh: Gh, label: str, now: dt.datetime) -> tuple[list[dict], bool]:
    """Open issues and pull requests carrying ``label``, plus those closed in the last
    CLOSED_WINDOW_DAYS (``since`` filters on updated_at, so closed_at is checked here)."""
    cutoff = now - dt.timedelta(days=CLOSED_WINDOW_DAYS)
    opened, capped_open = gh.pages("issues", {"labels": label, "state": "open"})
    closed, capped_closed = gh.pages("issues", {"labels": label, "state": "closed", "since": iso(cutoff)})
    merged = {item["number"]: item for item in opened if isinstance(item, dict) and "number" in item}
    for item in closed:
        closed_at = parse_time(item.get("closed_at")) if isinstance(item, dict) else None
        if closed_at is not None and closed_at >= cutoff and "number" in item:
            merged[item["number"]] = item
    return list(merged.values()), capped_open or capped_closed


def role_status(gh: Gh, roles: dict, role: str, now: dt.datetime, *, reveal_untrusted: bool = False) -> dict:
    spec = role_spec(roles, role)
    items, truncated = fetch_role_items(gh, spec["request_label"], now)
    summaries = sorted((summarize(item, roles, now, reveal_untrusted=reveal_untrusted) for item in items),
                       key=lambda entry: (STATE_ORDER.index(entry["state"]), entry["number"] or 0))
    counts = {state: sum(1 for entry in summaries if entry["state"] == state) for state in STATE_ORDER}
    counts["untrusted"] = sum(1 for entry in summaries if not entry["trusted"])
    return {"role": role, "host_id": spec["host_id"], "request_label": spec["request_label"],
            "generated_at": iso(now), "closed_window_days": CLOSED_WINDOW_DAYS, "truncated": truncated,
            "counts": counts, "items": summaries}


def send_notice(url: str, message: str, opener=None) -> None:
    """POST one fixed-format line to a loopback ntfy topic: no proxy, no redirect."""

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(check_notify_url(url), data=message.encode("utf-8"), method="POST",
                                     headers={"Content-Type": "text/plain; charset=utf-8"})
    with opener.open(request, timeout=5) as response:
        response.read(1024)


# ---------------------------------------------------------------------------------------------
# Poll state


def default_state_file(role: str, environment=None) -> Path:
    environment = os.environ if environment is None else environment
    base = environment.get("XDG_STATE_HOME") or ""
    if not os.path.isabs(base):  # the XDG spec ignores a relative value
        base = os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(base) / "native-agent-stack" / "host-requests" / f"{role}.json"


def load_state(path: Path, role: str) -> dict | None:
    """The previous poll's items, or None when there is no usable state (a first poll)."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        print(f"host_requests: ignoring unreadable state {path.name}: {type(error).__name__}", file=sys.stderr)
        return None
    if not isinstance(document, dict) or document.get("role") != role or not isinstance(document.get("items"), dict):
        print(f"host_requests: ignoring state {path.name}: not a {role} poll state", file=sys.stderr)
        return None
    return document["items"]


def write_state(path: Path, document: dict) -> None:
    """Atomic replace: a 0600 temporary file in the same 0700 directory, fsync, os.replace. A
    missing directory is created 0700; an existing one open to group or others is refused, never
    chmod-ed (it could be a shared directory)."""
    directory = path.parent
    if not directory.exists():
        directory.mkdir(mode=0o700, parents=True)
    mode = stat.S_IMODE(directory.stat().st_mode)
    if mode & 0o077:
        raise UsageError(f"state directory {directory} has mode {mode:04o}; it must be 0700")
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(document, handle, indent=1, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


# ---------------------------------------------------------------------------------------------
# Commands


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def read_text_file(path: str, label: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise UsageError(f"{label}: cannot read {path}: {type(error).__name__}") from None


def cmd_roles(args, context) -> int:
    roles = context["roles"]
    if args.json:
        print(json.dumps(roles, indent=2, sort_keys=True))
        return 0
    for role, spec in sorted(roles["roles"].items()):
        credentials = ", ".join(spec.get("credentials") or []) or "none"
        print(f"{role}: {spec['host_id']} label {spec['request_label']}; owns {', '.join(spec['owns'])}; "
              f"credential rows {credentials}")
    for peer in roles.get("peers", []):
        superseded = f" (superseded by {peer['superseded_by']})" if peer.get("superseded_by") else ""
        print(f"peer: {peer['host_id']}{superseded}")
    return 0


def cmd_parse(args, context) -> int:
    parsed = parse_body(read_text_file(args.body_file, "--body-file"))
    if args.json:
        print(json.dumps(parsed, indent=2, sort_keys=True))
        return 0
    for field_id, _, _, _ in FIELDS:
        value = parsed[field_id]
        shown = "; ".join(value) if isinstance(value, list) else (value if value is not None else "-")
        print(f"{field_id}: {clean(shown, 200)}")
    for warning in parsed["warnings"]:
        print(f"warning: {warning}")
    return 0


def cmd_compose(args, context) -> int:
    if not args.confirm:  # the web form will not submit without both boxes; neither does compose
        raise UsageError("pass --confirm to tick the form's two required confirmations after checking the text: "
                         + " ".join(f"({index}) {text}" for index, text in enumerate(CONFIRMATIONS, 1))
                         + " compose checks the scripts/validate.py private-content patterns, and none of them "
                         "recognizes an account id.")
    roles = context["roles"]
    spec = role_spec(roles, args.to)
    task = next((label for label, slug in TASK_CLASSES.items() if args.task_class in (label, slug)), None)
    if task is None:
        raise UsageError(f"--task-class must be one of: {', '.join(TASK_CLASSES)}")
    values = {
        "requesting_host": clean(args.requester, 64),
        "task_class": task,
        "lane": args.lane,
        "request": read_text_file(args.request_file, "--request-file").strip(),
        "models": read_text_file(args.models_file, "--models-file").strip() if args.models_file else None,
        "acceptance": read_text_file(args.acceptance_file, "--acceptance-file").strip(),
        "related": clean(args.related, 200) if args.related else None,
        "confirmations": list(CONFIRMATIONS),
    }
    if not values["requesting_host"]:
        raise UsageError("--from is empty")
    for field_id in ("request", "acceptance"):
        if not values[field_id]:
            raise UsageError(f"--{field_id}-file is empty")
    labels = {_normalize_label(label) for _, label, _, _ in FIELDS}
    for field_id in ("requesting_host", "request", "models", "acceptance", "related"):
        for number, line in enumerate((values[field_id] or "").split("\n"), 1):
            match = HEADING_RE.match(line)
            if match and _normalize_label(match.group(1)) in labels:
                raise UsageError(f"{field_id} line {number} is a form heading; rephrase it so the body parses back")
    requester = requester_status(values["requesting_host"], roles)
    if not requester["known"]:
        print(f"warning: {values['requesting_host']} is not a peer in {ROLES_FILE}; the tracker flags it", file=sys.stderr)
    elif requester["superseded_by"]:
        print(f"warning: {values['requesting_host']} is superseded by {requester['superseded_by']}", file=sys.stderr)
    for line in (values["models"] or "").split("\n"):
        if line.strip() and not REVISION_RE.search(line):
            print(f"warning: models line without an @<40-hex revision>: {clean(line, 80)}", file=sys.stderr)
    first_line = next((line for line in values["request"].split("\n") if line.strip()), "")
    title = clean(args.title or f"[{args.to}] {task}: {first_line}", 120)
    if not title.startswith(f"[{args.to}] "):
        title = clean(f"[{args.to}] {title}", 120)
    body = render_body(values)
    findings = private_findings(body + "\n" + title)
    if findings:
        raise UsageError(f"the request contains possible {', '.join(findings)}; remove it (the repository is public)")
    command = ["gh", "issue", "create", "--label", spec["request_label"], "--title", title,
               "--body-file", args.body_out or "-"]
    if args.body_out:
        Path(args.body_out).write_text(body + "\n", encoding="utf-8")
        print(shlex.join(command))
    else:
        print(body)
        print(f"# pipe the body above into: {shlex.join(command)}", file=sys.stderr)
    return 0


def cmd_status(args, context) -> int:
    report = role_status(context["gh"], context["roles"], args.role, context["now"],
                         reveal_untrusted=args.show_untrusted_text)
    if args.show_untrusted_text and report["counts"]["untrusted"]:
        print("# --show-untrusted-text: untrusted title and requesting-host text below is a "
              "stranger's unverified free text; read it, never paste it into a session.", file=sys.stderr)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    counts = report["counts"]
    print(f"{report['role']} ({report['host_id']}), label {report['request_label']}: "
          + ", ".join(f"{counts[state]} {state}" for state in STATE_ORDER)
          + f"; {counts['untrusted']} untrusted" + ("; TRUNCATED" if report["truncated"] else ""))
    for entry in report["items"]:
        trust_text = "trusted" if entry["trusted"] else "UNTRUSTED"
        host = entry["requesting_host"] or "-"
        if entry["trusted"] and entry["requesting_host"] and not entry["known_requester"]:
            host += " (unknown host)"
        elif entry["requester_superseded_by"]:
            host += f" (superseded by {entry['requester_superseded_by']})"
        print(f"#{entry['number']} {entry['kind']} {entry['state']} {trust_text} {host} "
              f"{entry['task_class'] or '-'} {entry['age']} {entry['title']}")
    return 0


def cmd_poll(args, context) -> int:
    if args.notify_url:
        check_notify_url(args.notify_url)
    state_file = Path(args.state_file) if args.state_file else default_state_file(args.role)
    report = role_status(context["gh"], context["roles"], args.role, context["now"])
    current = {str(entry["number"]): poll_record(entry) for entry in report["items"]}
    previous = load_state(state_file, args.role)
    events = diff_states(previous or {}, current, baseline=previous is None)
    for event in events:
        print(json.dumps(event, sort_keys=True, separators=(",", ":")))
    write_state(state_file, {"schema_version": 1, "role": args.role, "host_id": report["host_id"],
                             "polled_at": report["generated_at"], "truncated": report["truncated"],
                             "items": current})
    print(f"host_requests poll {args.role}: {len(current)} items, {len(events)} events", file=sys.stderr)
    if args.notify_url:
        live = [event for event in events if not event.get("baseline")]
        messages = [notice(event) for event in live[:NOTIFY_CAP]]
        if len(live) > NOTIFY_CAP:
            messages.append(f"{len(live) - NOTIFY_CAP} more host request events")
        for message in messages:
            try:
                context["notify"](args.notify_url, message)
            except (OSError, http.client.HTTPException) as error:  # URLError is an OSError
                print(f"host_requests: notice not sent: {type(error).__name__}", file=sys.stderr)
                break
    return 0


def cmd_lanes(args, context) -> int:
    items, truncated = context["gh"].pages("issues", {"state": "open"})
    report = {"generated_at": iso(context["now"]), "truncated": truncated,
              **lane_hygiene([item for item in items if isinstance(item, dict)])}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print(f"{report['open_pull_requests']} open pull requests, {report['open_issues']} open issues"
          + ("; TRUNCATED" if truncated else ""))
    sections = (("missing a lane label", "pull_requests_missing_lane"),
                ("with several lane labels", "pull_requests_with_multiple_lanes"),
                ("with an unknown lane label", "pull_requests_with_unknown_lane"),
                ("lane:shared, needing the other lane's acknowledgement", "lane_shared_needing_acknowledgement"),
                ("carrying a host:* label", "host_labelled"))
    for heading, key in sections:
        print(f"{heading}: {len(report[key])}")
        for entry in report[key]:
            extra = ", ".join(entry.get("lanes") or entry.get("labels") or [])
            print(f"  #{entry['number']} {entry['kind']} {entry['title']}" + (f" [{extra}]" if extra else ""))
    return 0


def print_call(gh: Gh, method: str, path: str, payload=None, note: str | None = None) -> None:
    print(shlex.join(gh.argv(method, path, payload)))
    if payload is not None:
        print(f"#   stdin: {json.dumps(payload, sort_keys=True)}")
    if note:
        print(f"#   {note}")


def cmd_transition(args, context) -> int:
    gh, roles, action, number = context["gh"], context["roles"], args.command, args.number
    session = args.session
    if session is not None and not SESSION_RE.fullmatch(session):
        raise UsageError("--session must be 1-64 characters of letters, digits and . _ : @ -")
    reason = clean(getattr(args, "reason", None), 300) or None
    if action in ("block", "decline") and not reason:
        raise UsageError(f"{action} needs a non-empty --reason")
    evidence = getattr(args, "evidence", None)
    if evidence is not None and not EVIDENCE_RE.fullmatch(evidence):
        raise UsageError("--evidence must be an https://github.com/ link (the pull request or receipt)")
    if args.dry_run and not args.role:
        raise UsageError("--dry-run makes no GitHub call, so pass --role")
    if args.dry_run:
        spec = role_spec(roles, args.role)
        state = {"claim": "claimed", "block": "blocked", "done": "done", "decline": "declined"}[action]
        labels = [f"<labels on #{number} except request:*>"] + ([ACTIONS[action]["label"]] if ACTIONS[action]["label"] else [])
        payload = {"labels": labels}
        if ACTIONS[action]["close"]:
            payload.update(state="closed", state_reason=ACTIONS[action]["close"])
        body = status_body(args.role, spec["host_id"], state, session or "<session from the status comment>",
                           context["now"], reason=reason, evidence=evidence)
        print("# dry run: no GitHub call is made; <...> marks a value the real run reads first")
        print_call(gh, "GET", f"issues/{number}", note=(
            f"refuse unless trusted (OWNER, user.type User, no GitHub App, the repository owner), labelled "
            f"{spec['request_label']} and {' or '.join(ACTIONS[action]['from'])}"))
        print_call(gh, "GET", f"issues/{number}/comments?per_page={PER_PAGE}&page=1",
                   note=f"find the owner's comment that starts with {MARKER.format(role=args.role)}"
                   + ("; refuse a claimed request whose comment names another session, unless --takeover"
                      if action == "claim" else ""))
        print_call(gh, "POST", f"issues/{number}/comments", {"body": body},
                   note="or PATCH issues/comments/<status comment id> when that comment exists")
        print_call(gh, "PATCH", f"issues/{number}", payload)
        return 0
    item = gh.call("GET", f"issues/{number}")
    if not isinstance(item, dict):
        raise GhError(f"gh api GET issues/{number}: expected a JSON object")
    role = args.role
    if role is None:
        matches = [name for name, spec in roles["roles"].items() if spec["request_label"] in label_names(item)]
        if len(matches) != 1:
            raise Refused(f"#{number} carries {len(matches)} role labels; pass --role")
        role = matches[0]
    spec = role_spec(roles, role)
    check_actionable(item, spec["request_label"], action)
    comments, _ = gh.pages(f"issues/{number}/comments", {})
    existing = find_status_comment([comment for comment in comments if isinstance(comment, dict)], role)
    recorded = SESSION_LINE_RE.search(str((existing or {}).get("body") or ""))
    holder = recorded.group(1) if recorded and SESSION_RE.fullmatch(recorded.group(1)) else None
    if session is None:
        session = holder or "unknown"
    # A claimed request belongs to the session its status comment names: that session may claim it
    # again (idempotent), any other needs --takeover. Nobody works on a blocked request, so any
    # session may claim it to resume. Without compare-and-swap, two claims at once can still race.
    if action == "claim" and derive_state(item) == "claimed" and holder != session and not getattr(args, "takeover", False):
        raise Refused(f"#{number} is claimed by session {holder}; pass --takeover to replace that claim" if holder
                      else f"#{number} is labelled claimed but no owner status comment names a session; "
                           "pass --takeover to claim it")
    previous = holder if holder not in (None, "unknown", session) else None
    state = {"claim": "claimed", "block": "blocked", "done": "done", "decline": "declined"}[action]
    body = status_body(role, spec["host_id"], state, session, context["now"], reason=reason, evidence=evidence,
                       previous_session=previous)
    findings = private_findings(body)
    if findings:
        raise Refused(f"the status comment would contain possible {', '.join(findings)}")
    # The comment goes first: if the label or close call then fails, rerunning the same command
    # edits the comment again and completes the transition.
    if existing is not None:
        gh.call("PATCH", f"issues/comments/{existing['id']}", {"body": body})
    else:
        gh.call("POST", f"issues/{number}/comments", {"body": body})
    payload = {"labels": planned_labels(item, action)}
    if ACTIONS[action]["close"]:
        payload.update(state="closed", state_reason=ACTIONS[action]["close"])
    gh.call("PATCH", f"issues/{number}", payload)
    print(json.dumps({"number": number, "action": action, "state": state, "role": role,
                      "comment": "edited" if existing is not None else "created",
                      "labels": payload["labels"], "previous_session": previous}, sort_keys=True))
    return 0


def cmd_ensure_labels(args, context) -> int:
    gh, specs = context["gh"], label_plan(context["roles"])
    if args.dry_run:
        print("# dry run: no GitHub call is made")
        print_call(gh, "GET", f"labels?per_page={PER_PAGE}&page=1")
        for spec in specs:
            print_call(gh, "POST", "labels", spec, note="only when the label is missing")
        return 0
    existing, _ = gh.pages("labels", {})
    names = {label.get("name") for label in existing if isinstance(label, dict)}
    created = []
    for spec in specs:
        if spec["name"] not in names:
            gh.call("POST", "labels", spec)
            created.append(spec["name"])
    print(json.dumps({"created": created, "present": sorted(spec["name"] for spec in specs if spec["name"] in names)},
                     sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", help="OWNER/NAME; default: this checkout's remote, as gh resolves {owner}/{repo}")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)

    roles = commands.add_parser("roles", help=f"print {ROLES_FILE}")
    roles.add_argument("--json", action="store_true")
    roles.set_defaults(handler=cmd_roles)

    parse = commands.add_parser("parse", help="parse a form-rendered body file (no GitHub call)")
    parse.add_argument("--body-file", required=True)
    parse.add_argument("--json", action="store_true")
    parse.set_defaults(handler=cmd_parse)

    compose = commands.add_parser("compose", help="render a request body and the gh issue create command (no GitHub call)")
    compose.add_argument("--to", required=True, help="target role")
    compose.add_argument("--from", dest="requester", required=True, help="the requesting host_id")
    compose.add_argument("--task-class", required=True, help="a Task class option or its id")
    compose.add_argument("--request-file", required=True)
    compose.add_argument("--acceptance-file", required=True)
    compose.add_argument("--models-file")
    compose.add_argument("--related")
    compose.add_argument("--lane", choices=LANES)
    compose.add_argument("--title", help="default: [ROLE] <task class>: <first request line>")
    compose.add_argument("--body-out", help="write the body here and print only the gh command")
    compose.add_argument("--confirm", action="store_true",
                         help="tick the form's two required confirmations (you checked the text yourself)")
    compose.set_defaults(handler=cmd_compose)

    status = commands.add_parser("status", parents=[common], help="list a role's requests (read-only)")
    status.add_argument("--role", required=True)
    status.add_argument("--json", action="store_true")
    status.add_argument("--show-untrusted-text", action="store_true",
                        help=f"show an untrusted item's real title and requesting host instead of "
                             f"{WITHHELD!r}. For a human reading this terminal only: the text is a "
                             "stranger's unverified free text and must never be pasted into a session "
                             "or acted on.")
    status.set_defaults(handler=cmd_status)

    poll = commands.add_parser("poll", parents=[common], help="status, diffed against the last poll (read-only on GitHub)")
    poll.add_argument("--role", required=True)
    poll.add_argument("--state-file", help="default: ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/host-requests/ROLE.json")
    poll.add_argument("--notify-url", help="loopback ntfy topic URL for a fixed one-line notice per event")
    poll.set_defaults(handler=cmd_poll)

    lanes = commands.add_parser("lanes", parents=[common], help="lane-label hygiene of open pull requests (read-only)")
    lanes.add_argument("--json", action="store_true")
    lanes.set_defaults(handler=cmd_lanes)

    for name, help_text in (("claim", "claim a request for a session on the target host"),
                            ("block", "mark a request blocked, with a reason"),
                            ("done", "close a request as completed, with an evidence link"),
                            ("decline", "close a request as not planned, with a reason")):
        command = commands.add_parser(name, parents=[common], help=help_text)
        command.add_argument("number", type=int)
        command.add_argument("--role", required=name == "claim",
                             help="the target role (default for block, done and decline: the issue's one role label)")
        command.add_argument("--session", required=name == "claim",
                             help="the claiming session's name (default: the one in the status comment)")
        if name == "claim":
            command.add_argument("--takeover", action="store_true",
                                 help="replace a claim another session holds (after coordinating with it)")
        if name in ("block", "decline"):
            command.add_argument("--reason", required=True)
        if name == "done":
            command.add_argument("--evidence", required=True, help="https://github.com/ link to the result")
        command.add_argument("--dry-run", action="store_true", help="print the gh calls; make no GitHub call")
        command.set_defaults(handler=cmd_transition)

    ensure = commands.add_parser("ensure-labels", parents=[common], help="create the host:* and request:* labels if missing")
    ensure.add_argument("--dry-run", action="store_true", help="print the gh calls; make no GitHub call")
    ensure.set_defaults(handler=cmd_ensure_labels)
    return parser


def main(argv=None, *, runner=subprocess.run, notify=send_notice, now=None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if getattr(args, "repo", None) and not REPO_RE.fullmatch(args.repo):
            raise UsageError("--repo must be OWNER/NAME")
        context = {"roles": load_roles(root), "now": now or now_utc(), "notify": notify,
                   "gh": Gh(runner, repo=getattr(args, "repo", None), cwd=root)}
        return args.handler(args, context)
    except GhError as error:
        print(f"host_requests: {error}", file=sys.stderr)
        return EXIT_GH
    except Refused as error:
        print(f"host_requests: refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (UsageError, OSError, ValueError) as error:
        print(f"host_requests: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
