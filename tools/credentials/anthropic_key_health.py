#!/usr/bin/env python3
"""Health of each Anthropic API key slot: stored or not, accepted or not, and its organization, spending no tokens.

    python3 tools/credentials/anthropic_key_health.py                         # every slot, one line each
    python3 tools/credentials/anthropic_key_health.py --slot anthropic-api-5  # only this slot (repeatable)
    python3 tools/credentials/anthropic_key_health.py --json                  # machine-readable

The slots are the inventory entries anthropic-api and anthropic-api-<n> (adoption/credential-inventory.json) that keep
ANTHROPIC_API_KEY alone in a private env file, in inventory order. For each one:

1. `credential_run.py <slot> --check` starts nothing and states whether the slot's file is stored (ok), missing or
   unsafe. A slot that is not stored starts no child and sends no request.
2. For a stored slot, `credential_run.py <slot> --only ANTHROPIC_API_KEY -- <python> -I -S <this file> --probe`. The
   key reaches only that child's environment, through the runner, which masks it in the child's output; this process
   never holds it. The request headers other than the key go to the child as JSON on its standard input, so no argv
   carries a value or a request detail. The child builds the key header from its own environment, sends
   GET /v1/models and GET /v1/organizations/me to the fixed API host, follows no redirect, reads no response body,
   and prints one JSON line: each response's HTTP status (only the error's type name when no response came) and the
   first eight characters of the anthropic-organization-id response header of GET /v1/models.

Neither request uses tokens. The report never holds a key or a piece of one, an organization name or a response body.
Exit status: 0 when every stored slot's GET /v1/models answered 2xx; 1 when a stored slot's did not, or a slot is
unsafe or could not be checked; 2 for a usage error. A slot that is not stored is reported and fails nothing.

A port of the command center's cc-tools/anthropic_key_health.sh (2026-10-10) without its organization-name read and
its admin-key probe (GET /v1/organizations/api_keys). The HTTP side follows tools/credentials/alpaca_rate_limit_probe.py
(no redirect, no body read, error type only) and the runner contract is tools/credentials/credential_run.py's. The
response header is documented under "Response headers" in https://platform.claude.com/docs/en/api/overview and the
organization endpoint under "Accessing organization info" in
https://platform.claude.com/docs/en/manage-claude/admin-api (both read 2026-10-10). Practice and rules:
docs/secret-storage.md#key-practice-2026-10-10.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not (sys.flags.isolated and sys.flags.no_site):
    # Re-run isolated, as credential_run.py does: -I ignores PYTHONPATH, the PYTHON* variables and the user site
    # directory, and -S also skips site, whose .pth lines run even under -I.
    os.execv(sys.executable, [sys.executable, "-I", "-S", os.path.abspath(__file__), *sys.argv[1:]])

import http.client  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "adoption" / "credential-inventory.json"
RUNNER = ROOT / "tools" / "credentials" / "credential_run.py"
SLOT = re.compile(r"anthropic-api(?:-[0-9]+)?")
KEY_VARIABLE = "ANTHROPIC_API_KEY"
API_HOST = "https://api.anthropic.com"
ENDPOINTS = (("models", "/v1/models"), ("organization", "/v1/organizations/me"))
# The headers the parent hands the child on stdin. The child accepts these names and no other, so neither the key nor
# any other credential header can arrive that way; the key header is built from the child's environment alone.
REQUEST_HEADERS = {"anthropic-version": "2023-06-01", "user-agent": "native-agent-stack-anthropic-key-health/1"}
ALLOWED_HEADERS = frozenset(REQUEST_HEADERS)
HEADER_VALUE = re.compile(r"[ -~]{1,200}")  # printable ASCII only: nothing that could end or split a header line
ORGANIZATION_HEADER = "anthropic-organization-id"
PREFIX = re.compile(r"[0-9A-Za-z-]{8}")
PLAIN = re.compile(r"[A-Za-z0-9 _.,:;()<>/-]{1,200}")
REQUEST_SECONDS = 20.0
RUNNER_SECONDS = 120.0  # one --check, or one probe of two requests of at most REQUEST_SECONDS each
MAX_SPEC_BYTES = 4096
CHECK_LINE = re.compile(r"(?P<id>[a-z0-9-]+): (?P<state>ok|missing|unsafe|refused)(?P<rest>.*)")
FAILING_STATES = ("unsafe", "refused", "error")
USAGE = """usage:
  anthropic_key_health.py [--slot <inventory-id>]... [--json]
Reports, per anthropic-api slot: stored or not, the GET /v1/models status and what it says about the key, the
GET /v1/organizations/me status, and the first eight characters of the organization id. No tokens are spent and no
key, organization name or response body is printed. See docs/secret-storage.md#key-practice-2026-10-10."""


class UsageError(Exception):
    """A usage error (exit 2). The message never repeats a word the caller typed: a value typed in the wrong place
    would otherwise be echoed."""


class Refused(Exception):
    """The probe child refused its input. The message is a reason code, never a value."""


# --------------------------------------------------------------------------- the probe child (holds the key)

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None  # a 30x surfaces as HTTPError; the key is never re-sent anywhere


def read_spec(data: bytes) -> dict:
    """The request headers from the parent: exactly {"headers": {name: value}}, every name in ALLOWED_HEADERS and
    anthropic-version among them."""
    if len(data) > MAX_SPEC_BYTES:
        raise Refused("spec_too_large")
    try:
        spec = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("spec_not_json") from None
    if not isinstance(spec, dict) or set(spec) != {"headers"} or not isinstance(spec["headers"], dict):
        raise Refused("spec_shape")
    headers = {}
    for name, value in spec["headers"].items():
        if not isinstance(name, str) or name.lower() not in ALLOWED_HEADERS:
            raise Refused("header_not_allowed")  # the name is not repeated
        if not isinstance(value, str) or not HEADER_VALUE.fullmatch(value):
            raise Refused("header_value_not_plain")
        headers[name.lower()] = value
    if "anthropic-version" not in headers:
        raise Refused("anthropic_version_missing")
    return headers


def probe(headers: dict, environ, *, opener=None) -> dict:
    """GET each endpoint with the key from environ. Only HTTP statuses, error type names and the organization id prefix
    (from the response header of GET /v1/models) come back; no response body is read."""
    key = environ.get(KEY_VARIABLE, "")
    if not key:
        return {"error": "key_absent"}
    opener = opener or urllib.request.build_opener(_NoRedirect())
    result = {"organization_id_prefix": None}
    for name, path in ENDPOINTS:
        request = urllib.request.Request(API_HOST + path, method="GET", headers={**headers, "x-api-key": key})
        try:
            response = opener.open(request, timeout=REQUEST_SECONDS)
            status, response_headers = response.status, response.headers
            response.close()  # the body is never read
        except urllib.error.HTTPError as error:
            status, response_headers = error.code, error.headers
            error.close()
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as error:
            result[name] = {"status": None, "error": type(error).__name__}
            continue
        result[name] = {"status": status if isinstance(status, int) else None}
        if name == "models" and response_headers is not None:
            prefix = (response_headers.get(ORGANIZATION_HEADER) or "").strip()[:8]
            result["organization_id_prefix"] = prefix if PREFIX.fullmatch(prefix) else None
    return result


def probe_main(stdin, stdout, environ, *, opener=None) -> int:
    """The --probe child: request headers as JSON on stdin, the key in environ, one JSON line on stdout."""
    try:
        result = probe(read_spec(stdin.read(MAX_SPEC_BYTES + 1)), environ, opener=opener)
    except Refused as refusal:
        result = {"error": str(refusal)}
    except Exception as error:  # no traceback and no message: either could quote what was being handled
        result = {"error": "unexpected_" + type(error).__name__}
    stdout.write(json.dumps(result, sort_keys=True) + "\n")
    stdout.flush()
    return 1 if "error" in result else 0


# --------------------------------------------------------------------------- the parent (never holds a key)

def slots(inventory_path: Path = INVENTORY) -> list:
    """The anthropic-api slots that keep ANTHROPIC_API_KEY alone in a private env file, in inventory order."""
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    return [entry["id"] for entry in inventory["entries"]
            if SLOT.fullmatch(entry["id"]) and entry["store"]["kind"] == "private_env_file"
            and entry["variables"] == [KEY_VARIABLE]]


def check_command(slot: str) -> list:
    return [sys.executable, str(RUNNER), slot, "--check"]


def probe_command(slot: str) -> list:
    """The runner and the probe child. Neither part holds a value or a request detail."""
    return [sys.executable, str(RUNNER), slot, "--only", KEY_VARIABLE, "--",
            sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--probe"]


def spec() -> bytes:
    """What the child reads on stdin."""
    return json.dumps({"headers": REQUEST_HEADERS}, sort_keys=True).encode("utf-8")


def plain(text, fallback: str = "unprintable"):
    return text if isinstance(text, str) and PLAIN.fullmatch(text) else fallback


def runner_note(stderr: bytes):
    """The runner's own first message (it carries the id, names and reason codes, never a value), or None."""
    lines = stderr.decode("utf-8", "replace").splitlines()
    return plain(lines[0], None) if lines and lines[0].startswith("credential_run: ") else None


def status_class(status) -> str:
    return f"{status // 100}xx" if isinstance(status, int) and 100 <= status <= 599 else "none"


def validity(status) -> str:
    """What GET /v1/models says about the key: valid (2xx), invalid (401: a wrong, disabled or revoked key), forbidden
    (403), rate_limited (429), server_error (5xx), unexpected (any other status) or unreachable (no response)."""
    if not isinstance(status, int):
        return "unreachable"
    if 200 <= status <= 299:
        return "valid"
    named = {401: "invalid", 403: "forbidden", 429: "rate_limited"}
    return named.get(status, "server_error" if 500 <= status <= 599 else "unexpected")


def check(slot: str, run) -> dict:
    """Stored, not stored, unsafe, refused or error, from the runner's --check line; nothing is started."""
    try:
        done = run(check_command(slot), stdin=subprocess.DEVNULL, capture_output=True, timeout=RUNNER_SECONDS)
    except subprocess.TimeoutExpired:
        return {"state": "error", "detail": "check_timed_out"}
    lines = done.stdout.decode("utf-8", "replace").splitlines()
    match = CHECK_LINE.fullmatch(lines[0]) if lines else None
    if match is None or match["id"] != slot:
        return {"state": "error", "detail": runner_note(done.stderr) or f"check_unreadable (exit {done.returncode})"}
    state, rest = match["state"], match["rest"]
    if state == "ok":
        if done.returncode == 0 and f" {KEY_VARIABLE} " in rest + " ":
            return {"state": "stored"}
        return {"state": "error", "detail": f"check_unexpected (exit {done.returncode})"}
    detail = re.match(r" \(([^()]*)\)", rest)
    return {"state": "not stored" if state == "missing" else state,
            "detail": plain(detail.group(1)) if detail else ""}


def probe_slot(slot: str, run) -> dict:
    """The child's JSON line for a stored slot, or {"error": reason} when there is none to read."""
    try:
        done = run(probe_command(slot), input=spec(), capture_output=True, timeout=RUNNER_SECONDS)
    except subprocess.TimeoutExpired:
        return {"error": "probe_timed_out"}
    lines = [line for line in done.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1]) if lines else None
    except ValueError:
        result = None
    if not isinstance(result, dict):
        return {"error": runner_note(done.stderr) or f"probe_output_unreadable (exit {done.returncode})"}
    return result


def health(selected: list, run=subprocess.run) -> list:
    """One row per slot. Only known fields of checked types are kept from the child's line."""
    rows = []
    for slot in selected:
        row = {"id": slot, **check(slot, run)}
        if row["state"] == "stored":
            result = probe_slot(slot, run)
            models = result.get("models") if isinstance(result.get("models"), dict) else {}
            organization = result.get("organization") if isinstance(result.get("organization"), dict) else {}
            status = models.get("status") if isinstance(models.get("status"), int) else None
            organization_status = organization.get("status") if isinstance(organization.get("status"), int) else None
            prefix = result.get("organization_id_prefix")
            row.update({"models_status": status, "status_class": status_class(status), "validity": validity(status),
                        "organization_status": organization_status,
                        "organization_id_prefix": prefix if isinstance(prefix, str) and PREFIX.fullmatch(prefix)
                        else None})
            for field, value in (("error", result.get("error")), ("models_error", models.get("error")),
                                 ("organization_error", organization.get("error"))):
                if value is not None:
                    row[field] = plain(value)
        rows.append(row)
    return rows


def render(row: dict) -> str:
    slot, state = row["id"], row["state"]
    if state == "not stored":
        return f"{slot}: not stored"
    if state != "stored":
        return f"{slot}: {state}" + (f" ({row['detail']})" if row.get("detail") else "")
    if row.get("error"):
        return f"{slot}: stored; probe failed ({row['error']})"

    def shown(status, error) -> str:
        return str(status) if status is not None else "no response" + (f" ({error})" if error else "")

    return (f"{slot}: stored; {row['validity']} (GET /v1/models "
            f"{shown(row['models_status'], row.get('models_error'))}, {row['status_class']}); "
            f"GET /v1/organizations/me {shown(row['organization_status'], row.get('organization_error'))}; "
            f"organization {row['organization_id_prefix'] or '?'}")


def exit_code(rows: list) -> int:
    failed = any(row["state"] in FAILING_STATES or (row["state"] == "stored" and row.get("validity") != "valid")
                 for row in rows)
    return 1 if failed else 0


def parse_args(argv: list):
    """(slots, as_json), or None for --help."""
    selected, as_json, rest = [], False, list(argv)
    while rest:
        word = rest.pop(0)
        if word in ("-h", "--help"):
            return None
        if word == "--json":
            as_json = True
        elif word == "--slot":
            if not rest:
                raise UsageError("--slot needs an inventory id")
            slot = rest.pop(0)
            if slot not in selected:
                selected.append(slot)
        else:
            raise UsageError("unknown argument (it is not repeated here)")
    return selected, as_json


def main(argv=None, *, run=subprocess.run, stdout=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv == ["--probe"]:
        return probe_main(sys.stdin.buffer, sys.stdout, os.environ)
    out = sys.stdout if stdout is None else stdout
    try:
        request = parse_args(argv)
        if request is None:
            print(USAGE, file=out)
            return 0
        selected, as_json = request
        try:
            known = slots()
        except (OSError, ValueError, KeyError, TypeError):
            print("anthropic_key_health: the credential inventory is unreadable; "
                  "check it with python3 scripts/credential_status.py", file=sys.stderr)
            return 1
        if any(slot not in known for slot in selected):
            raise UsageError("--slot takes one of: " + ", ".join(known))  # the unknown word is not repeated
    except UsageError as error:
        print(f"anthropic_key_health: usage error: {error}\n{USAGE}", file=sys.stderr)
        return 2
    rows = health(selected or known, run)
    if as_json:
        checked = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(json.dumps({"checked_utc": checked, "slots": rows}, indent=2, sort_keys=True), file=out)
    else:
        for row in rows:
            print(render(row), file=out)
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main())
