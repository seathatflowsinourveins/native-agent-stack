#!/usr/bin/env python3
"""The canary probe: show that a synthetic key reached this process by inventory id, without printing the key.

    python3 -I tools/credentials/credential_run.py canary-e2e -- python3 -I tools/credentials/canary_probe.py --run <id> --consumer <consumer>

Its one secret input is CANARY_E2E_KEY, read by that hard-coded name. No option names another variable, so the probe
can never be pointed at a real key. The other names it reads are locations only (XDG_RUNTIME_DIR, XDG_STATE_HOME,
HOME), to find the run directory that tools/credentials/canary_e2e.py made.

It prints one line, `canary-probe <consumer>: tag <first 16 hex>`. The tag is HMAC-SHA256 keyed with the canary over
`<run>|<consumer>|<nonce>`, where the nonce is the one the harness wrote for this consumer when it armed the run. A tag
from an earlier arming, another consumer or another run therefore fails `canary_e2e.py verify`. The full tag goes to
<run directory>/tags/<consumer>.tag where the probe can write it; a Codex sandbox may refuse that write, and the
printed line is then the only channel.

Exit status: 0 when the tag was printed; 3 when CANARY_E2E_KEY is absent; 4 when the run's nonce cannot be read; 2 for a
usage error or a start without -I; 1 when core dumps cannot be turned off (RLIMIT_CORE 0 is set first).

`--leak-check` is for the systemd-user-unit consumer only, whose output returns through systemd-run's pipe to the
harness and never to a client. After the tag line it prints the canary raw and encoded: base64 and base64url at three
byte alignments, percent (quote and quote_plus, both hex cases, and quote's default safe "/"), JSON (Python's escaping
and a "\\/" form), lower- and upper-case hex, one form written in two parts with a pause between them, and a last line
without a newline. Under credential_run.py every one of them must come back masked. The forms are computed here with
the standard library, independently of the runner's own list, so the check does not grade the masker against itself.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    # The key is already in this interpreter's environment, so whatever ran at start-up ran beside it: refuse rather than
    # re-execute (set_credential.py --from-env makes the same choice).
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
from pathlib import Path  # noqa: E402

VARIABLE = "CANARY_E2E_KEY"  # the only secret input, by name; there is no option to read another
CONSUMERS = ("fresh-claude-session", "subagent", "workflow-child", "codex-exec", "omniroute-lane", "systemd-user-unit")
LEAK_CHECK_CONSUMER = "systemd-user-unit"
RUN_ID = re.compile(r"canary-[0-9]{8}t[0-9]{6}z-[0-9a-f]{6}")
NONCE = re.compile(r"[0-9a-f]{32}")
TAG_LINE = re.compile(r"canary-probe (?P<consumer>[a-z-]+): tag (?P<prefix>[0-9a-f]{16})\b")
PREFIX_HEX = 16
SPLIT_PAUSE_SECONDS = 0.3  # longer than the runner's 100 ms idle flush, so a held partial value is tested


def run_directories(run: str, env=None) -> list:
    """Where canary_e2e.py keeps the run: the runtime directory (tmpfs), or the state directory for a run prepared with
    --keep-across-restart. An unset or relative XDG_RUNTIME_DIR means /run/user/<uid>, and an unset or relative
    XDG_STATE_HOME means $HOME/.local/state (XDG Base Directory Specification)."""
    env = os.environ if env is None else env
    runtime = env.get("XDG_RUNTIME_DIR") or ""
    if not os.path.isabs(runtime):
        runtime = f"/run/user/{os.getuid()}"
    state = env.get("XDG_STATE_HOME") or ""
    if not os.path.isabs(state):
        state = os.path.join(env.get("HOME") or str(Path.home()), ".local", "state")
    return [Path(runtime, "native-agent-stack", "canary", run), Path(state, "native-agent-stack", "canary", "keep", run)]


def tag(canary: str, run: str, consumer: str, nonce: str) -> str:
    """HMAC-SHA256 keyed with the canary over run|consumer|nonce, as 64 lowercase hex characters."""
    message = f"{run}|{consumer}|{nonce}".encode("ascii")
    return hmac.new(canary.encode("ascii"), message, hashlib.sha256).hexdigest()


def leak_forms(value: str) -> list:
    """The lines --leak-check prints after `form `: the value raw and in the encodings a careless command uses."""
    raw = value.encode("ascii")
    forms = [value]
    for prefix in (b"", b"u", b"us"):  # the three byte alignments
        forms.append(base64.b64encode(prefix + raw).decode("ascii"))
        forms.append(base64.urlsafe_b64encode(prefix + raw).decode("ascii"))
    for quote in (urllib.parse.quote, urllib.parse.quote_plus):
        upper = quote(value, safe="")
        forms += [upper, re.sub("%[0-9A-F]{2}", lambda match: match.group(0).lower(), upper)]
    forms.append(urllib.parse.quote(value))  # quote()'s default safe="/"
    forms += [json.dumps({"key": value}), json.dumps(value)[1:-1].replace("/", "\\/")]
    forms += [raw.hex(), raw.hex().upper()]
    return list(dict.fromkeys(forms))


def read_nonce(run: str, consumer: str, env=None):
    """The nonce the harness wrote for this consumer, or None. Only this small file is read, never a pattern file."""
    for directory in run_directories(run, env):
        try:
            with open(directory / "nonce" / consumer, "rb") as handle:
                text = handle.read(64).decode("ascii", "replace").strip()
        except OSError:
            continue
        return text if NONCE.fullmatch(text) else None
    return None


def write_tag(run: str, consumer: str, full: str, env=None):
    """Write the full tag to <run directory>/tags/<consumer>.tag (0600, replaced atomically). An error code or None."""
    for directory in run_directories(run, env):
        tags = directory / "tags"
        if not tags.is_dir():
            continue
        temporary = tags / f".{consumer}.{os.getpid()}.tmp"
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                os.write(fd, (full + "\n").encode("ascii"))
            finally:
                os.close(fd)
            os.replace(temporary, tags / f"{consumer}.tag")
            return None
        except OSError as error:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            return type(error).__name__
    return "no_tag_directory"


def emit_leak_forms(value: str) -> None:
    """Print the forms on stdout, the raw form on stderr as well, a split write and an unterminated last line."""
    for form in leak_forms(value):
        os.write(1, f"form {form}\n".encode("ascii"))
    os.write(2, f"form {value}\n".encode("ascii"))
    half = len(value) // 2
    os.write(1, f"split {value[:half]}".encode("ascii"))
    time.sleep(SPLIT_PAUSE_SECONDS)
    os.write(1, f"{value[half:]}\n".encode("ascii"))
    os.write(1, f"tail {value}".encode("ascii"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="canary_probe.py", description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="the run id that canary_e2e.py prepare printed")
    parser.add_argument("--consumer", required=True, choices=CONSUMERS)
    parser.add_argument("--leak-check", action="store_true",
                        help=f"print the canary's forms after the tag ({LEAK_CHECK_CONSUMER} only)")
    args = parser.parse_args(argv)
    say = f"canary-probe {args.consumer}"
    if not RUN_ID.fullmatch(args.run):
        sys.stderr.write(f"{say}: usage error: --run is not a canary run id\n")
        return 2
    if args.leak_check and args.consumer != LEAK_CHECK_CONSUMER:
        sys.stderr.write(f"{say}: usage error: --leak-check is only for {LEAK_CHECK_CONSUMER}, the run the harness owns\n")
        return 2
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        sys.stderr.write(f"{say}: refused: could not set RLIMIT_CORE to 0\n")
        return 1
    value = os.environ.get(VARIABLE)
    if not value:
        sys.stderr.write(f"{say}: {VARIABLE} is absent; run it through credential_run.py canary-e2e\n")
        return 3
    nonce = read_nonce(args.run, args.consumer)
    if nonce is None:
        sys.stderr.write(f"{say}: the run's nonce for this consumer cannot be read\n")
        return 4
    full = tag(value, args.run, args.consumer, nonce)
    os.write(1, f"{say}: tag {full[:PREFIX_HEX]}\n".encode("ascii"))
    problem = write_tag(args.run, args.consumer, full)
    if problem is not None:
        sys.stderr.write(f"{say}: tag file not written ({problem}); the printed line is the channel\n")
    if args.leak_check:
        emit_leak_forms(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
