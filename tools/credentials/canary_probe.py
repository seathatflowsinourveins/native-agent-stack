#!/usr/bin/env python3
"""The canary probe: show that a synthetic key reached this process by inventory id, without printing the key.

    python3 -I tools/credentials/credential_run.py canary-e2e -- python3 -I tools/credentials/canary_probe.py \
        --run RUN --consumer CONSUMER --attempt N [--leak-check]

Its one secret input is CANARY_E2E_KEY, read by that hard-coded name; no option names another variable, so the probe
can never be pointed at a real key. It opens and writes no file. It prints exactly one line,
`canary-probe <consumer> attempt <n>: tag <tag>`, where the tag is the first 16 hex characters of
HMAC-SHA256(canary, "canary-proof|<run>|<consumer>|<attempt>"): only a process holding that attempt's canary can print
it (tools/credentials/canary_proof.py computes the same tag).

`--leak-check` (the systemd-user-unit consumer only) then prints the canary raw and encoded, computed here with the
standard library independently of the runner's own form list so the masker is not graded against itself: base64 and
base64url at three byte alignments, percent (quote and quote_plus, both hex cases, and quote's default safe "/"), JSON
(Python's escaping and a "\\/" form), lower- and upper-case hex; the raw form once on stderr; one form written in two
parts 0.3 s apart (longer than the runner's 100 ms idle flush); and a last raw form without a newline. Through
credential_run.py every one of them must come back as a full [REDACTED:CANARY_E2E_KEY] marker.

Exit status: 0 printed; 1 core dumps could not be turned off; 2 usage, --leak-check for another consumer, or a start
without -I (refused, never re-executed: the key is already in this environment); 3 CANARY_E2E_KEY absent.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.stderr.write("canary-probe: refused: start it with python3 -I, as in the documented command\n")
    raise SystemExit(2)

import argparse  # noqa: E402
import base64  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import resource  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402

VARIABLE = "CANARY_E2E_KEY"
CONSUMERS = ("systemd-user-unit", "fresh-claude-session", "subagent", "workflow-child", "codex-exec", "omniroute-lane")
LEAK_CHECK_CONSUMER = "systemd-user-unit"
RUN_ID = re.compile(r"cp-\d{8}t\d{6}z-[0-9a-f]{6}")
SPLIT_PAUSE_SECONDS = 0.3


def tag(canary: str, run: str, consumer: str, attempt: int) -> str:
    message = f"canary-proof|{run}|{consumer}|{attempt}".encode("ascii")
    return hmac.new(canary.encode("ascii"), message, hashlib.sha256).hexdigest()[:16]


def leak_forms(value: str) -> list:
    """The independent form corpus (the parked probe's list, abf2ce19 canary_probe.py leak_forms)."""
    raw = value.encode("ascii")
    forms = [value]
    for prefix in (b"", b"u", b"us"):
        forms += [base64.b64encode(prefix + raw).decode("ascii"), base64.urlsafe_b64encode(prefix + raw).decode("ascii")]
    for quote in (urllib.parse.quote, urllib.parse.quote_plus):
        upper = quote(value, safe="")
        forms += [upper, re.sub("%[0-9A-F]{2}", lambda match: match.group(0).lower(), upper)]
    forms.append(urllib.parse.quote(value))
    forms += [json.dumps({"key": value}), json.dumps(value)[1:-1].replace("/", "\\/"), raw.hex(), raw.hex().upper()]
    return list(dict.fromkeys(forms))


def leak_writes(value: str) -> list:
    """(descriptor, bytes, pause before) in order: what --leak-check writes after the tag line."""
    half = len(value) // 2
    return ([(1, f"form {form}\n".encode("ascii"), 0.0) for form in leak_forms(value)]
            + [(2, f"form {value}\n".encode("ascii"), 0.0), (1, f"split {value[:half]}".encode("ascii"), 0.0),
               (1, f"{value[half:]}\n".encode("ascii"), SPLIT_PAUSE_SECONDS), (1, f"tail {value}".encode("ascii"), 0.0)])


def leak_output(value: str) -> tuple:
    """(stdout, stderr) bytes of the leak check, deterministic, for the expected-marker count."""
    return tuple(b"".join(data for fd, data, _pause in leak_writes(value) if fd == stream) for stream in (1, 2))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="canary_probe.py", description=__doc__.splitlines()[0], allow_abbrev=False)
    parser.add_argument("--run", required=True)
    parser.add_argument("--consumer", required=True, choices=CONSUMERS)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--leak-check", action="store_true")
    args = parser.parse_args(argv)
    if not RUN_ID.fullmatch(args.run) or args.attempt < 1 or (args.leak_check and args.consumer != LEAK_CHECK_CONSUMER):
        sys.stderr.write("canary-probe: usage error\n")
        return 2
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        sys.stderr.write("canary-probe: refused: could not set RLIMIT_CORE to 0\n")
        return 1
    value = os.environ.get(VARIABLE)
    if not value:
        sys.stderr.write(f"canary-probe: {VARIABLE} is absent; run it through credential_run.py canary-e2e\n")
        return 3
    os.write(1, f"canary-probe {args.consumer} attempt {args.attempt}: tag {tag(value, args.run, args.consumer, args.attempt)}\n"
             .encode("ascii"))
    if args.leak_check:
        for fd, data, pause in leak_writes(value):
            time.sleep(pause)
            os.write(fd, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
