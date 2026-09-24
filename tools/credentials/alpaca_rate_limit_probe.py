#!/usr/bin/env python3
"""Read-only Alpaca paper trading-API rate-limit probe.

Sends exactly one GET /v2/account to the fixed paper host and reports the HTTP status
and the x-ratelimit-* response headers. That is Alpaca's own statement of the account's
calls-per-minute limit (200 on the standard tier), so no order is ever needed to measure
it. The probe never reads the response body, never follows a redirect, never prints
account identifiers or credentials, and can send no other request. Live accounts are out
of scope for this repository (docs/secret-storage.md).

    python3 tools/credentials/alpaca_rate_limit_probe.py --env-file "$PAPER_ENV_FILE" --out RESULT.json
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import credential_status as cs  # noqa: E402

HOST = "https://paper-api.alpaca.markets"
PATH = "/v2/account"
USER_AGENT = "native-agent-stack-rate-limit-probe/1"
TOKEN = re.compile(r"^[A-Za-z0-9._+/=-]{8,256}$")
NAMES = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")


class Refused(Exception):
    """A safety rule refused the probe; the message never contains a value."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None  # a 30x surfaces as HTTPError; credentials are never re-sent elsewhere


def paper_store_file(env=None, root: Path = ROOT) -> Path:
    inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    entry = next(e for e in inventory["entries"] if e["id"] == "alpaca-paper")
    return cs.expand_template(entry["store"]["path_template"], os.environ if env is None else env)


def _check_token(name: str, value: str) -> str:
    if not TOKEN.match(value or ""):
        raise Refused(f"{name}: empty or not a plain key token")
    return value


def read_env_file(path: Path, uid: int | None = None) -> tuple[str, str]:
    """Store rules plus a post-open identity check (no TOCTOU swap, no FIFO hang)."""
    uid = os.getuid() if uid is None else uid
    try:
        before = os.lstat(path)
        directory = os.lstat(path.parent)
    except FileNotFoundError:
        raise Refused("credential file not found; store it first with set_credential.py") from None
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise Refused("credential path is not a regular file")
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != uid or stat.S_IMODE(directory.st_mode) != 0o700:
        raise Refused("credential directory must be a 0700 directory owned by you")
    if cs.git_worktree_of(path.parent) is not None:
        raise Refused("credential file is inside a Git worktree")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (info.st_ino, info.st_dev) != (before.st_ino, before.st_dev) or not stat.S_ISREG(info.st_mode):
            raise Refused("credential file changed while it was checked")
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise Refused("credential file must be mode 0600, owned by you, with one link")
        raw = handle.read(65536)
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Refused("credential file is not ASCII") from None
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return tuple(_check_token(n, values.get(n, "")) for n in NAMES)  # type: ignore[return-value]


def interpret(limit: str | None) -> str:
    if limit is None:
        return "no x-ratelimit-limit header returned"
    try:
        value = int(limit)
    except ValueError:
        return "unparseable x-ratelimit-limit"
    return "200 calls/min: standard tier" if value == 200 else f"{value} calls/min"


def probe(key_id: str, key_value: str, *, opener=None, now=None) -> dict:
    opener = opener or urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(HOST + PATH, method="GET", headers={
        "APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": key_value, "User-Agent": USER_AGENT,
        "Accept": "application/json"})
    result = {"account": "paper", "host": HOST.split("//", 1)[1], "request": f"GET {PATH}",
              "observed_at_utc": (now or datetime.now(timezone.utc)).isoformat()}
    try:
        response = opener.open(request, timeout=15)
        status, headers = response.status, response.headers
        response.close()  # the body is never read
    except urllib.error.HTTPError as error:
        status, headers = error.code, error.headers
        error.close()
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as error:
        return {**result, "http_status": None, "error": type(error).__name__,
                "rate_limit_headers": {}, "interpretation": "request failed before a response"}
    limits = {k.lower(): v for k, v in (headers.items() if headers else []) if k.lower().startswith("x-ratelimit")}
    return {**result, "http_status": status, "rate_limit_headers": limits,
            "interpretation": interpret(limits.get("x-ratelimit-limit"))
            + ("" if status == 200 else f" (HTTP {status}: check the paper key)")}


def write_private(out: Path, text: str) -> None:
    """Write via a fresh temp file and replace: never follows or truncates a symlink target."""
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")  # 0600, O_EXCL
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, out)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--env-file", type=Path, help="paper credential file (default: the alpaca-paper entry)")
    parser.add_argument("--out", type=Path, help="also write the non-secret result JSON here (mode 0600)")
    args = parser.parse_args(argv)
    try:
        key_id, key_value = read_env_file(args.env_file or paper_store_file())
        result = probe(key_id, key_value)
        del key_id, key_value
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        write_private(args.out, text + "\n")
    ok = result["http_status"] == 200 and "x-ratelimit-limit" in result["rate_limit_headers"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
