#!/usr/bin/env python3
"""GPT-6 (Codex CLI) job runner for the landscape sweep; codex_call.sh is its command-line front.

  codex_call.sh [--work-dir DIR] start  <job-id> <prompt-file> <schema-file>
  codex_call.sh [--work-dir DIR] wait   <job-id> [seconds]    default 540; prints "done exit=N" or "running"
  codex_call.sh [--work-dir DIR] result <job-id>              one JSON line: status, exit, started, finished,
                                                              usage, usage_status, output_text, stderr_tail,
                                                              limit, limit_marker, model, effort, request_effort, web_search,
                                                              codex_version, inputs, attempts, quota, failure, route

`start` detaches one job and returns at once. The job waits for a semaphore slot (an fcntl lock on
<lock dir>/slot-<n>, held by the runner and by codex itself, so a killed runner never frees a slot early), then runs
this, in the empty directory <work-dir>/empty, bounded to 4000 s by default (exit 124 on timeout):

  codex exec --ignore-user-config --disable apps --skip-git-repo-check -s read-only -m gpt-6-astra \
    -c model_reasoning_effort="max" -c web_search="live" \
    --output-schema <job>/schema.json -o <job>/last.json --json - < <job>/stdin.txt

The native command uses Codex's built-in OpenAI provider. staged.json codex.effort and
codex.web_search override the shown defaults; supported values follow the pinned 0.159.2 model catalog and
WebSearchMode enum (disabled, cached, indexed, live). Both lanes keep upstream's default connection retries.

Gateway provider (staged.json codex.provider "omniroute", build_args.py --gpt6-provider omniroute): the runner sets
CODEX_HOME to the staged lane-local home <work-dir>/codex-home instead, drops --ignore-user-config (that home IS the
configuration: the OmniRoute provider block plus the token MCP servers) and adds `-p <profile>` (the stack-worker
profile layered over it), so the command becomes `codex exec -p stack-worker --skip-git-repo-check -s read-only
-m cx/gpt-6-astra ...`. The provider key comes from the variable codex.api_key_env (OMNIROUTE_API_KEY) in the
operator's environment. For a keyless loopback gateway, codex.api_key_placeholder ("local-loopback") fills an
unset variable, because Codex's env_key only needs it to exist. Without either, a job ends with exit 6 before codex
starts. The quota gate reads the native login only, so it is refused for a gateway lane. A lane staged on a chained
OmniRoute instance names its model with a node alias in
front (`-m sharedgw/gpt-6-astra-max`), and its static provider headers (codex.http_headers, OmniRoute's per-request
switches only, for example x-omniroute-compression = allow-lossy; build_args.py --omniroute-header) sit in the lane
home's [model_providers.omniroute] http_headers. The runner refuses to start when that table differs from
codex.http_headers, and records the headers in each job's inputs.json. The comparison needs tomllib (Python 3.11+):
older interpreters refuse every gateway lane with a home to scan; native-only lanes retain Python 3.9 support.

--ignore-user-config keeps the host's Codex config out of the native lane, the sandbox is read-only, and the actual
Codex attempt receives an EOF-bounded private stdin file. Every other child keeps stdin at /dev/null, so a detached
runner or model-free helper cannot wait on the caller's terminal. The default effort stays max. A lane may stage ultra;
the lane stager chooses per the current GPT worker standard. Blind or isolated review lanes must stay at max,
because ultra auto-delegates in multi-agent v2 (openai/codex rust-v0.159.2,
codex-rs/core/src/session/multi_agents.rs:77-103). Ultra resolves to the catalog's multi_agent_reasoning_effort,
else max for an ultra-capable catalog model: Astra and Sol 6.1 send xhigh on root requests, while retaining proactive
delegation (codex-rs/models-manager/models.json:22,196; protocol/src/openai_models/reasoning_effort.rs:12-35;
core/src/client.rs:863-872). inputs.json and result distinguish staged effort from request_effort. Codex runs without the caller's RUST_LOG,
so its stderr carries only
its default `error`-level diagnostics (EXEC_DEFAULT_LOG_FILTER, codex-rs/exec/src/lib.rs at rust-v0.155.1): at
trace level Codex logs model response data (codex-rs/codex-api/src/sse/responses.rs), which could quote any text. The model and slot count come from <work-dir>/staged.json (build_args.py
--gpt6-model / --slots / --lock-dir); defaults gpt-6-astra, 3 slots, <work-dir>/locks. The codex binary is the one
on PATH.

Opt-in native failover (staged.json codex.fallback, build_args.py --gpt6-fallback omniroute): a native limit or
quota gate archives the native attempt unchanged, writes LIMIT-native with its reason and reported reset time,
and reruns the same prompt/schema at the same effort in the held slot and total deadline. The transport-only inline
provider keeps --ignore-user-config and the caller's CODEX_HOME/AGENTS.md, enables standalone web search, disables
shell snapshots, excludes OMNIROUTE_API_KEY from model-run shells, and uses cx/<native model>-<request effort>
where the pinned gateway supports that reasoning alias. inputs.json stays
byte-identical; route.json and result.route describe the actual route and OmniRoute's /alpha/search backend.
While LIMIT-native exists, a no-model account/rateLimits/read probe precedes each new job: only explicit
ordinaryUsageAllowed true removes that marker; otherwise the job goes directly to the gateway. No reset credit is
consumed. Gateway 429s count only in error/turn.failed events and write LIMIT with reason "gateway pool 429".

Usage limit without fallback: when Codex reports "hit your usage limit", or an HTTP 429 that carries no usage-limit body ("exceeded
retry limit, last status: 429 Too Many Requests"; Codex retries no 429, so it prints that for the first one:
codex-rs/model-provider-info/src/lib.rs, codex-api/src/api_bridge.rs and protocol/src/error.rs at rust-v0.159.3), the
job ends with exit 3 and writes <work-dir>/LIMIT. A pooled gateway answers 429 when its accounts are exhausted, as it
did for nine jobs on 2026-09-29 while the workflow went on spending Claude stages; the report cannot tell that from a
brief rate limit, so the marker holds a reason and no reset time. While that file exists no job starts and jobs still
waiting for a slot end with exit 3, so the coordinator can stop and notify. Only Codex's own error reports count: the
`error` / `turn.failed` events that `codex exec --json` prints on stdout (openai/codex rust-v0.155.1,
codex-rs/exec/src/exec_events.rs and event_processor_with_jsonl_output.rs), and,
only when no turn completed, an ERROR/Error line on stderr (gateway HTTP 429s require JSON events). Model content (item.* events: messages, web results,
cited pages) never counts: on 2026-09-26 a grep of the whole event stream matched a cited README's "Usage
limitation" and set the marker falsely.

Quota gate (optional; off unless staged.json codex.quota_stop_percent is set, a number above 0 and at most 100):
after a job gets its slot and before every attempt, the runner runs `codex_quota.py --json --gate <percent>` (the
copy build_args.py staged beside this file, else the checkout's scripts/codex_quota.py), which reads the account's
usage snapshot through `codex app-server` (account/rateLimits/read) and exits 3 when a window's used_percent reaches
the percent, rateLimitReachedType is set or ordinaryUsageAllowed is false. Exit 3 is refused like a usage limit: the
job ends with exit 3 before codex starts unless its staged fallback continues it, and <work-dir>/LIMIT (when absent) and the job's stderr.txt get the
reason, so the coordinator can report the reset time. Every probe is recorded in <job>/quota.json (`result` gives
its summary as `quota`); a probe that fails (no codex, timeout after codex.quota_timeout_s, default 30 s, an error
answer, a missing script) is recorded and never blocks the job.

Transient recovery: a Codex capacity error is retried by this harness at most twice, with capped exponential
backoff and jitter (30 s base, 120 s cap); upstream Codex itself treats this error as terminal. After 1800 s without
a complete non-error JSONL event, the process group is stopped (exit 125), the failure is retained, and the job retries
once. Reconnect error notices do not count as progress. codex.idle_timeout_s and codex.timeout_s (defaults 1800 s /
4000 s) are configurable; ultra defaults to 4200 s / 14400 s only when each value is absent. An ultra idle timeout
of 3600 s or less is refused before initial state changes: upstream multi-agent wait can block for 3600 s by default
(rust-v0.159.2, codex-rs/core/src/config/mod.rs:257; tools/handlers/multi_agents_v2/wait.rs:53-64). The total budget
starts after the slot wait, includes the version check, every quota probe, attempts and backoff, and a retry or
backoff requires at least 300 s remaining after its delay. At the deadline a completed turn gets kill_grace_s to
exit cleanly and write -o before termination. Usage/HTTP-429 LIMIT handling takes precedence. These harness settings
live in staged.json, not Codex config. Codex rides out shorter connection outages; the watchdog bounds longer ones
(codex-rs/core/src/responses_retry.rs:71-96). Ad-hoc longer lanes stage timeout_s and use a matching caller wait;
the sweep's 8 * 540 s wrapper cannot accommodate the ultra default or long queues.

Ultra or any collab/sub-agent JSONL item marks usage_status primary_thread_only, retaining the numbers without
claiming complete delegated usage. Exec only forwards primary-thread token updates (rust-v0.159.2,
codex-rs/exec/src/lib.rs:1636-1638; event_processor_with_jsonl_output.rs:509-511,533-535).

A job is bound to its inputs: <job>/inputs.json holds the sha256 of its prompt and schema, the model, the effort and
request_effort and the web search mode (an absent mode means live for older records). It also binds apps=false:
--disable apps applies to every future attempt, independent of the caller's config. An older
input with no apps field is not equivalent and is archived unchanged before a rerun. Each attempt's exact argv is
kept privately in argv.json (mode 0600), alongside its returned events and archived with them. The raw prompt stays
in prompt.txt; stdin.txt (mode 0600) holds the same UTF-8 bytes the former argv path delivered after universal-newline
reading and stripping only trailing LF characters. route.json records this prompt transport and its delivered
byte count and hash after actual spawn. The raw bound prompt hash and earlier artifacts remain unchanged.
A primary OmniRoute job also binds the resolved gateway's endpoint, source and reason; a historical record without
that tuple cannot be reused for a new primary gateway run. Native inputs omit the tuple, including transport-only
fallback inputs whose separate route receipt remains checked before reuse.
Success requires exit 0, a turn.completed event
and a non-empty -o output file. Exit 0 without that evidence becomes exit 126, failure kind incomplete. A successful
attempt for the same inputs is not rerun ("already done"). Any other earlier
attempt (failed, refused, or done for different inputs, as after a Workflow resume regenerated the prompt) is moved
unchanged to <job>/attempts/<n>/ and the job starts again; `result` lists every earlier attempt with its exit and
usage ("unavailable" when Codex reported none), so failed attempts stay counted. A job that is still running is left
alone ("already running"), or refused (exit 2) when it runs for different inputs.
If staged settings change between input binding and launch, the runner refuses with exit 2, failure kind
inputs_changed, including invalid restaging. Every recorded nonzero terminal exit writes failure.json, exit and done.
Initial invalid settings are refused before job state changes; refusing different inputs for a running job leaves
its owned state alone. The recorded model, effort and search mode always describe the invocation that ran.

Work dir: --work-dir, else this file's directory when build_args.py staged it there (staged.json present), else
$SWEEP_WORK_DIR. It must lie outside every git repository: Codex would otherwise load that repository's AGENTS.md
into the lane. Standard library only; Linux and macOS (Python 3.9+).
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import ipaddress
import io
import json
import math
import os
import pathlib
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# --- host-gateway contract v2 (identical in every holder; tests/test_host_gateway_contract.py) ---
# needs (stdlib, Python >= 3.9): argparse, hashlib, ipaddress, json, os, pathlib, socket, sys, urllib.parse;
# tomllib (3.11+) and pwd are imported lazily, inside the functions that need them
HOST_GATEWAY_SCHEMA = "native-agent-stack/host-gateway/v1"
HOST_GATEWAY_RECORD = ".config/agent-stack-host/gateway.json"  # under the passwd home; never $HOME or XDG
HOST_GATEWAY_WRITER = "tools/omniroute/host_gateway.py write"
HOST_GATEWAY_OVERRIDE = "--unrecorded-gateway-reason"
LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")
ENDPOINT_OVERRIDE_KEYS = frozenset({"openai_base_url", "chatgpt_base_url", "model_provider", "model_providers",
                                    "profile", "profiles"})  # Codex's own endpoint denylist
CODEX_ENDPOINT_KEYS = ("base_url", "openai_base_url", "chatgpt_base_url")  # a loopback value under these is a route
_RECORD_WHERE = f"the passwd home's {HOST_GATEWAY_RECORD} (not $HOME)"
_OVERRIDE_FIX = f"pass the gateway flag together with {HOST_GATEWAY_OVERRIDE} TEXT"


class GatewayRefused(ValueError):
    """No endpoint may be used; the message says what was checked and what to run."""


def gateway_endpoint(value):
    """The one shape contract: exactly http://127.0.0.1:<port>/v1 (a trailing slash is dropped)."""
    if isinstance(value, str) and "${" in value:
        raise GatewayRefused(f"{value!r} is an unexpanded variable; set it, or leave it empty for this host's record")
    try:
        parts = urllib.parse.urlsplit(value.strip())
        port = parts.port
        ok = (parts.scheme == "http" and port is not None and port > 0 and parts.netloc == f"127.0.0.1:{port}"
              and not parts.query and not parts.fragment and parts.path.rstrip("/") == "/v1")
    except (AttributeError, TypeError, ValueError):
        ok = False
    if not ok:
        raise GatewayRefused(f"{value!r} is not a gateway endpoint; write it as http://127.0.0.1:<port>/v1")
    return f"http://127.0.0.1:{port}/v1"


def loopback_port(value):
    """The port of an http(s) URL whose host is any loopback or unspecified spelling; otherwise None."""
    try:
        parts = urllib.parse.urlsplit(value.strip())
        port, host = parts.port, (parts.hostname or "").rstrip(".")
        if parts.scheme not in ("http", "https") or port is None or not host:
            return None
        if host == "localhost" or host.endswith(".localhost"):
            return port
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = ipaddress.ip_address(socket.inet_aton(host))  # short IPv4 forms such as 127.1
        address = getattr(address, "ipv4_mapped", None) or address
        return port if address.is_loopback or address.is_unspecified else None
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def installation_id():
    """sha256 of this installation's /etc/machine-id (machine-id(5): 32 lowercase hex digits). There is no default."""
    try:
        text = pathlib.Path("/etc/machine-id").read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise GatewayRefused(f"/etc/machine-id cannot be read here ({type(error).__name__}), so no host gateway "
                             f"record can be bound to this installation; {_OVERRIDE_FIX}") from None
    if len(text) != 32 or text.strip("0123456789abcdef") or not text.strip("0"):
        raise GatewayRefused(f"/etc/machine-id is not a 32-digit lowercase hex id; {_OVERRIDE_FIX}")
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def recorded_gateway():
    """This host's own gateway, as its writer recorded it. There is no default."""
    try:
        import pwd
    except ImportError:
        raise GatewayRefused(f"this platform has no passwd database and so no host gateway record; "
                             f"{_OVERRIDE_FIX}") from None
    try:
        home = pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        raise GatewayRefused("this uid has no passwd entry in this context (a user namespace or container); "
                             f"{_OVERRIDE_FIX}") from None
    try:
        text = (home / HOST_GATEWAY_RECORD).read_text(encoding="utf-8")
    except FileNotFoundError:
        try:
            visible = home.is_dir()
        except OSError:
            visible = False
        if not visible:
            raise GatewayRefused("the passwd home is not visible in this context (a sandbox); run outside it, "
                                 f"or {_OVERRIDE_FIX}") from None
        raise GatewayRefused(f"no host gateway record at {_RECORD_WHERE}. If this host runs a gateway: python3 "
                             f"<checkout>/{HOST_GATEWAY_WRITER} --port <PORT> --unit <UNIT>. If it has none: "
                             f"{_OVERRIDE_FIX}") from None
    except OSError as error:
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} exists but cannot be read here "
                             f"({error.strerror}); run outside the sandbox, or {_OVERRIDE_FIX}") from None
    try:
        record = json.loads(text)
        host, endpoint, machine = record["host"], record["endpoint"], record["machine_id_sha256"]
        if (record.get("schema") != HOST_GATEWAY_SCHEMA or not isinstance(host, str) or not isinstance(endpoint, str)
                or not isinstance(machine, str) or len(machine) != 64 or machine.strip("0123456789abcdef")):
            raise ValueError  # a missing, null, empty or malformed machine_id_sha256 is malformed
    except (AttributeError, KeyError, TypeError, ValueError):
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} is malformed or has another schema; "
                             f"rewrite it: python3 <checkout>/{HOST_GATEWAY_WRITER} --replace --port <PORT>") from None
    if host != socket.gethostname():
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} was written under another host name; "
                             f"if this host runs a gateway: python3 <checkout>/{HOST_GATEWAY_WRITER} --replace "
                             "--port <PORT>")
    if machine != installation_id():  # installation_id() refuses when this installation's machine id cannot be read
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} was written by another installation "
                             f"(the machine id differs); python3 <checkout>/{HOST_GATEWAY_WRITER} --replace "
                             "--port <PORT>")
    try:
        return gateway_endpoint(endpoint)
    except GatewayRefused:
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} names an endpoint outside the "
                             "contract") from None


def resolve_gateway(explicit, reason, variables):
    """The rule. Returns {endpoint, source, reason} or raises GatewayRefused."""
    explicit = explicit if isinstance(explicit, str) and explicit.strip() else None  # empty means no flag
    if explicit is not None:
        explicit = gateway_endpoint(explicit)
    if reason is not None:
        if explicit is None or not reason.strip():
            raise GatewayRefused(f"{HOST_GATEWAY_OVERRIDE} needs an explicit gateway and a non-blank reason")
        return {"endpoint": explicit, "source": "unrecorded", "reason": reason.strip()}
    recorded = recorded_gateway()
    if explicit is not None and explicit != recorded:
        raise GatewayRefused(f"{explicit} is not this host's recorded gateway ({recorded}); to use it "
                             f"deliberately add {HOST_GATEWAY_OVERRIDE} TEXT")
    port = urllib.parse.urlsplit(recorded).port
    for name in variables:
        found = loopback_port(os.environ.get(name) or "")
        if found is not None and found != port:
            raise GatewayRefused(f"{name} names a loopback gateway on port {found}, not this host's recorded "
                                 f"gateway ({recorded}); unset it (env -u {name} ...), or pass the gateway "
                                 f"explicitly with {HOST_GATEWAY_OVERRIDE} TEXT")
    return {"endpoint": recorded, "source": "host-record", "reason": None}


def _toml():
    try:
        import tomllib
    except ImportError:
        raise GatewayRefused("this Python has no tomllib (3.11+), so the endpoint check cannot run; use Python "
                             "3.11 or later for a gateway run") from None
    return tomllib


def refuse_endpoint_overrides(overrides):
    """A generic Codex -c value may not choose or redefine a provider endpoint; only the gateway flag may."""
    if not overrides:
        return
    tomllib = _toml()
    for override in overrides:
        try:
            keys = set(tomllib.loads(override)) & ENDPOINT_OVERRIDE_KEYS
        except (TypeError, tomllib.TOMLDecodeError):
            raise GatewayRefused(f"{override!r} is not a KEY=TOML override") from None
        if keys:
            raise GatewayRefused(f"{override!r} sets {', '.join(sorted(keys))}; an endpoint is chosen only by "
                                 "the gateway flag and this host's record")


def home_endpoint_ports(home):
    """(file:key, port) for each loopback endpoint that a Codex home's *config.toml files name."""
    paths = sorted(pathlib.Path(home).glob("*config.toml"))
    if not paths:
        return []
    tomllib, found = _toml(), []
    for path in paths:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise GatewayRefused(f"{path.name} in the Codex home cannot be read or parsed "
                                 f"({type(error).__name__}); fix it before a gateway run") from None
        stack = [((), data)]
        while stack:
            keys, node = stack.pop()
            if isinstance(node, dict):
                stack.extend(((*keys, key), value) for key, value in node.items())
            elif isinstance(node, str) and keys and keys[-1] in CODEX_ENDPOINT_KEYS:
                port = loopback_port(node)
                if port is not None:
                    found.append((path.name + ":" + ".".join(keys), port))
    return found


def refuse_home_endpoints(home, gateway, variables=()):
    """C1 for the Codex-home channel: a home may name no loopback endpoint but the run's gateway."""
    found = home_endpoint_ports(home)
    if not found:
        return  # no loopback route in the home: no record is read
    gateway = gateway or resolve_gateway(None, None, variables)
    port = urllib.parse.urlsplit(gateway["endpoint"]).port
    for where, other in found:
        if other != port:
            raise GatewayRefused(f"the Codex home names a loopback gateway on port {other} ({where}), not "
                                 f"{gateway['endpoint']}; use a Codex home that names this run's gateway or none")


def probe_gateway(endpoint, timeout=3.0):
    """A bounded TCP connect before any side effect: on mirrored WSL an unbound loopback port hangs."""
    try:
        socket.create_connection(("127.0.0.1", urllib.parse.urlsplit(endpoint).port), timeout=timeout).close()
    except OSError as error:
        raise GatewayRefused(f"gateway {endpoint} did not accept a TCP connection within {timeout:g} s "
                             f"({type(error).__name__}); start this host's gateway unit, then run python3 "
                             "<checkout>/tools/omniroute/host_gateway.py check") from None


def child_env(env):
    """A child's environment with loopback exempt from every proxy (NO_PROXY and no_proxy)."""
    env = dict(env)
    for name in ("NO_PROXY", "no_proxy"):
        entries = [item.strip() for item in (env.get(name) or "").split(",") if item.strip()]
        env[name] = ",".join(entries + [host for host in LOOPBACK_NO_PROXY if host not in entries])
    return env


def gateway_check(argv, flags, variables, overrides=(), homes=()):
    """--gateway-check, called at module top before any SDK import: resolve, print one JSON line, exit 0 or 2.
    flags maps each gateway flag of the holder to a function that returns a /v1 URL from the flag's value;
    overrides names its generic Codex -c flags and homes its Codex-home flags, which are checked too."""
    names = ("--gateway-check", HOST_GATEWAY_OVERRIDE, *flags, *overrides, *homes)
    pre = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    pre.add_argument("--gateway-check", action="store_true")
    pre.add_argument(HOST_GATEWAY_OVERRIDE, dest="reason")
    for index, flag in enumerate(flags):
        pre.add_argument(flag, dest=f"gateway_{index}")
    for index, flag in enumerate(overrides):
        pre.add_argument(flag, dest=f"override_{index}", action="append", default=[])
    for index, flag in enumerate(homes):
        pre.add_argument(flag, dest=f"home_{index}")
    known, rest = pre.parse_known_args(argv)
    if not known.gateway_check:
        return
    try:
        for item in rest:
            name = item.split("=", 1)[0]
            if name.startswith("--") and any(full != name and full.startswith(name) for full in names):
                raise GatewayRefused(f"{name} is an abbreviation; spell the option in full")
        values = [getattr(known, f"gateway_{index}") for index in range(len(flags))]
        given = [convert(value) for convert, value in zip(flags.values(), values) if value and value.strip()]
        results = [resolve_gateway(value, known.reason, variables) for value in given]
        result = results[0] if results else resolve_gateway(None, known.reason, variables)
        refuse_endpoint_overrides([item for index in range(len(overrides))
                                   for item in getattr(known, f"override_{index}")])
        for index in range(len(homes)):
            if getattr(known, f"home_{index}"):
                refuse_home_endpoints(getattr(known, f"home_{index}"), result, variables)
    except GatewayRefused as error:
        print(f"gateway refused: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps({"gateway": result}, sort_keys=True))
    raise SystemExit(0)
# --- end host-gateway contract v2 ---

GATEWAY_VARIABLES = ("OPENAI_BASE_URL",)

HERE = Path(__file__).resolve().parent
STAGED = "staged.json"
DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_EFFORT = "max"
DEFAULT_WEB_SEARCH = "live"
# Harness budgets: 1800 s idle clears the observed 473 s of healthy JSONL silence. The sweep wrapper waits
# 8 * 540 = 4320 s (sweep.js:92); 4000 s plus the default probe/backstop (30 + 30), version check (60),
# and completion/termination grace (10 + 10) is 4140 s. The shared deadline also includes probes and version.
# Native transport idle is different: SSE events / websocket messages, not exec items (rust-v0.159.2,
# codex-rs/codex-api/src/sse/responses.rs:528-537; codex-rs/codex-api/src/endpoint/responses_websocket.rs:688-714).
DEFAULTS = {"slots": 3, "timeout_s": 4000.0, "wait_poll_s": 10.0, "slot_poll_s": 5.0, "kill_grace_s": 10.0,
            "quota_timeout_s": 30.0, "idle_timeout_s": 1800.0, "capacity_max_retries": 2,
            "capacity_backoff_s": 30.0, "capacity_backoff_max_s": 120.0}
# ReasoningEffort also has none/minimal/persistent/custom; only accept levels the pinned catalog supports
# (rust-v0.159.2, codex-rs/protocol/src/openai_models.rs:59-71). Catalog slugs and effort arrays:
# codex-rs/models-manager/models.json:4,178,355,527,695,837,979,1121,1238,1349,1475 at rust-v0.159.2.
REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
MODEL_EFFORTS = {name: REASONING_EFFORTS for name in (
    "gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-5.6-sol", "gpt-5.6-terra",
    "gpt-daybreak-blue-latest", "gpt-daybreak-red-latest")}
MODEL_EFFORTS.update({"gpt-6-luna": REASONING_EFFORTS[:-1], "gpt-5.6-luna": REASONING_EFFORTS[:-1],
                      "codex-auto-review": REASONING_EFFORTS[:-1], "gpt-5.5": REASONING_EFFORTS[:-2]})
# Extracted from openai/codex rust-v0.159.2, codex-rs/models-manager/models.json:
# astra:22, 6.1-sol:196, 6-sol:373, 6-luna:545, 5.6-sol:713, 5.6-terra:855, 5.6-luna:997,
# 5.5:1367, auto-review:1493; Daybreak blocks:1121,1238 omit
# the optional field (codex-rs/protocol/src/openai_models.rs:510).
MODEL_MULTI_AGENT_EFFORTS = {"gpt-6-astra": "xhigh", "gpt-6.1-sol": "xhigh", "gpt-6-sol": None,
                            "gpt-5.6-sol": None, "gpt-5.6-terra": None,
                            "gpt-6-luna": None, "gpt-5.6-luna": None, "gpt-5.5": None,
                            "codex-auto-review": None, "gpt-daybreak-blue-latest": None,
                            "gpt-daybreak-red-latest": None}
ULTRA_IDLE_TIMEOUT_S, ULTRA_TIMEOUT_S = 4200.0, 14400.0
MULTI_AGENT_WAIT_CAP_S = 3600.0  # rust-v0.159.2, codex-rs/core/src/config/mod.rs:257,
# codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs:53-64.
RETRY_MIN_REMAINING_S = 300.0
# rust-v0.159.2, codex-rs/protocol/src/config_types.rs:371-382 (upstream default cached; harness default live).
# Live web search: `--search` before exec (and no flag) sends external_web_access false, a cached index; only
# web_search="live" sends true (evidence/artifacts/sota-refresh-20260926/codex/results/websearch-*.json).
WEB_SEARCH_MODES = ("disabled", "cached", "indexed", "live")
# Harness policy; Codex treats ServerOverloaded as terminal (rust-v0.159.2,
# codex-rs/protocol/src/error.rs:384-412). These are not Codex configuration keys.
CAPACITY_PHRASE = re.compile(r"\bSelected model is at capacity\.", re.IGNORECASE)
QUOTA_SCRIPT = "codex_quota.py"
QUOTA_BACKSTOP_S = 30.0  # beyond the probe's own deadline, for a probe that itself hangs
LIMIT_PHRASE = re.compile(r"hit your usage limit", re.IGNORECASE)
# Codex's report of an HTTP 429 whose body is not a usage-limit body: RetryLimitReachedError's Display ("exceeded retry
# limit, last status: {status}, request id: {id}", codex-rs/protocol/src/error.rs at rust-v0.157.1). Codex retries no
# 429 (retry_429 is false for every provider, codex-rs/model-provider-info/src/lib.rs) and codex-api/src/api_bridge.rs
# builds this error in its 429 arm, so the report appears at the first 429, whether the route is exhausted or briefly
# rate limited. A gateway that answers 429 carries no usage-limit body, so this is the report a pooled route gives when
# its accounts are exhausted. The pattern names the status, so a report for any other status stays a fault.
RETRY_LIMIT_429 = re.compile(r"exceeded retry limit, last status: 429\b", re.IGNORECASE)
LIMIT_PATTERNS = (("usage", LIMIT_PHRASE), ("http_429", RETRY_LIMIT_429))
# Codex's own error lines: "ERROR: ...", "Error: ..." (eprintln) or a tracing record "<timestamp> ERROR <target>: ...".
STDERR_ERROR_LINE = re.compile(r"^(?:\S+\s+)?(?:ERROR|Error)\b")
# Prompts use the upstream '-' stdin path: openai/codex@rust-v0.160.1,
# codex-rs/exec/src/lib.rs:191-193,2252-2275,2288-2290. Linux's MAX_ARG_STRLEN
# (/usr/include/linux/binfmts.h, 32 pages) limits argv transport, not model content.
JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# Kept equal to build_args.MODEL_NAME: at most one provider segment, e.g. "cx/gpt-6-astra" or the framework
# instance's "sharedgw/gpt-6-astra-max". Codex strips one namespace for metadata lookup, and only one of letters,
# digits, '_' and '-'; another slug gets fallback metadata (openai/codex rust-v0.157.1,
# codex-rs/models-manager/src/manager.rs L763-780).
MODEL_NAME = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9_-]{0,31}/)?[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# Kept equal to build_args.py, which cites their sources: a gateway lane's static provider headers (staged.json
# codex.http_headers, rendered as model_providers.<provider>.http_headers in the lane home) are OmniRoute's per-request
# switches only, since other x-omniroute-* headers carry secrets, with printable ASCII values.
OMNIROUTE_REQUEST_HEADERS = ("x-omniroute-compression", "x-omniroute-no-cache", "x-omniroute-no-memory",
                             "x-omniroute-strip-reasoning")
HEADER_VALUE = re.compile(r"[!#-\[\]-~](?:[ !#-\[\]-~]{0,126}[!#-\[\]-~])?")
PROVIDERS = ("native", "omniroute")
FALLBACK_KEY_ENV = "OMNIROUTE_API_KEY"
FALLBACK_SEARCH_BACKEND = "omniroute:/alpha/search"
# HouMinXi/OmniRoute@0585aba5589d5a1f49243a13a8db249558e7c9e3,
# open-sse/executors/codex/reasoningSuffix.ts:11-19,35-62. Low through xhigh aliases strip any base;
# max strips only these exact models. Ultra is resolved by the native client before choosing the suffix.
FALLBACK_MAX_ALIAS_MODELS = frozenset(("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-6-astra",
                                       "gpt-6-sol", "gpt-6-luna", "gpt-6.1-sol"))
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")
PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# Everything one attempt writes; an earlier attempt's files move together to attempts/<n>/.
ATTEMPT_FILES = ("events.jsonl", "stderr.txt", "last.json", "started", "finished", "exit", "slot", "model",
                 "codex_version", "done", "prompt.txt", "schema.json", "inputs.json", "runner.log", "quota.json",
                 "failure.json", "route.json", "argv.json", "stdin.txt")
EXIT_LIMIT, EXIT_TIMEOUT, EXIT_NO_CODEX, EXIT_REFUSED = 3, 124, 127, 2
EXIT_NO_KEY = 6  # a gateway lane whose API key variable is unset in the runner's environment
EXIT_IDLE = 125
EXIT_INCOMPLETE = 126  # exit 0 without a completed turn and non-empty output


class UsageError(Exception):
    """A refusal before any job state changes (bad arguments, work dir inside a repository)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inside_repository(path: Path) -> Path | None:
    """The nearest directory at or above path that holds a git repository marker: a .git directory with a HEAD entry
    (a file, or a symlink, which git allows to point at an unborn branch), or a non-empty .git file (a worktree's or
    submodule's gitdir pointer). An empty .git is not one. Codex's Linux
    sandbox creates empty .git mount targets under its writable roots, /tmp included, while a sandboxed command runs,
    and removes them afterwards (codex-rs/linux-sandbox/src/bwrap.rs at rust-v0.157.1, SyntheticMountTarget). A work
    directory under /tmp would otherwise be refused at random whenever another Codex job writes on the same host."""
    for candidate in (path, *path.parents):
        marker = candidate / ".git"
        try:
            head = marker / "HEAD"
            if head.is_file() or head.is_symlink() or (marker.is_file() and marker.stat().st_size > 0):
                return candidate
        except OSError:  # the marker vanished between the checks: a synthetic target being removed
            continue
    return None


def resolve_work_dir(explicit: str | None, script_dir: Path = HERE) -> Path:
    """--work-dir, else the staged copy's own directory, else $SWEEP_WORK_DIR; never inside a repository."""
    if explicit:
        base = Path(explicit)
    elif (script_dir / STAGED).is_file():
        base = script_dir
    elif os.environ.get("SWEEP_WORK_DIR"):
        base = Path(os.environ["SWEEP_WORK_DIR"])
    else:
        raise UsageError("no work directory: pass --work-dir, set SWEEP_WORK_DIR, or run the copy build_args.py "
                         "staged into the work directory")
    base = base.expanduser().resolve()
    if not base.is_dir():
        raise UsageError(f"work directory {base} does not exist")
    repo = inside_repository(base)
    if repo is not None:
        raise UsageError(f"work directory {base} is inside the git repository {repo}; use a directory outside "
                         "every repository")
    return base


def settings(base: Path) -> dict:
    staged = {}
    if (base / STAGED).is_file():
        staged = (json.loads((base / STAGED).read_text(encoding="utf-8")) or {}).get("codex") or {}
    overrides = staged.get("config_overrides", [])
    if not isinstance(overrides, list) or not all(isinstance(value, str) for value in overrides):
        raise GatewayRefused("codex.config_overrides must be a list of KEY=TOML strings")
    refuse_endpoint_overrides(overrides)
    if staged.get("apps", False) is not False:
        raise UsageError("codex.apps must be false: this research lane does not use app connectors")
    defaults = dict(DEFAULTS)
    if staged.get("effort") == "ultra":
        defaults.update(idle_timeout_s=ULTRA_IDLE_TIMEOUT_S, timeout_s=ULTRA_TIMEOUT_S)
    out = {key: type(value)(staged.get(key, value)) for key, value in defaults.items()}
    for key in ("timeout_s", "idle_timeout_s", "capacity_backoff_s", "capacity_backoff_max_s"):
        if not math.isfinite(out[key]) or out[key] <= 0:
            raise UsageError(f"codex.{key} must be finite and above 0")
    if not 0 <= out["capacity_max_retries"] <= 10:
        raise UsageError("codex.capacity_max_retries must be between 0 and 10")
    if out["slots"] < 1:
        raise UsageError("codex.slots must be at least 1")
    lock_dir = Path(staged.get("lock_dir") or "locks").expanduser()
    out["lock_dir"] = lock_dir if lock_dir.is_absolute() else base / lock_dir
    out["model"] = str(staged.get("model") or DEFAULT_MODEL)
    namespace, slash, rest = out["model"].partition("/")
    if slash and ("/" in rest or not re.fullmatch(r"[A-Za-z0-9_-]+", namespace)):
        raise UsageError("codex.model may have one provider segment, of letters, digits, '_' and '-' only: Codex "
                         "strips only such a namespace, and any other slug gets fallback metadata "
                         "(openai/codex rust-v0.157.1, codex-rs/models-manager/src/manager.rs L763-780)")
    if not MODEL_NAME.fullmatch(out["model"]):
        raise UsageError(f"codex.model {out['model']!r} is not a model name")
    # Match the catalog's longest slug prefix, then one simple provider namespace (rust-v0.159.2,
    # codex-rs/models-manager/src/manager.rs:745-800); a catalog model takes only its catalog levels. A model outside
    # the catalog gets fallback metadata with no levels (codex-rs/models-manager/src/model_info.rs:98-106). Codex sends
    # any other effort unchanged, but resolves ultra to the model's multi-agent effort, else max, else medium
    # (codex-rs/protocol/src/openai_models/reasoning_effort.rs:10-35), so ultra there would run at medium: refuse it.
    names = (out["model"], rest) if slash else (out["model"],)
    supported = next((MODEL_EFFORTS[slug] for name in names
                      for slug in sorted(MODEL_EFFORTS, key=len, reverse=True) if name.startswith(slug)),
                     REASONING_EFFORTS[:-1])
    out["effort"] = staged.get("effort", DEFAULT_EFFORT)
    if out["effort"] not in supported:
        raise UsageError(f"codex.effort {out['effort']!r} is not supported by the rust-v0.159.2 catalog for "
                         f"codex.model {out['model']!r}; supported: {', '.join(supported) or 'none'}")
    out["request_effort"] = request_effort(out["model"], out["effort"])
    if out["effort"] == "ultra" and out["idle_timeout_s"] <= MULTI_AGENT_WAIT_CAP_S:
        raise UsageError("an ultra lane needs codex.idle_timeout_s above 3600 s: upstream multi-agent wait may "
                         "block for 3600 s (rust-v0.159.2, codex-rs/core/src/config/mod.rs:257; "
                         "codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs:53-64)")
    out["web_search"] = staged.get("web_search", DEFAULT_WEB_SEARCH)
    if out["web_search"] not in WEB_SEARCH_MODES:
        raise UsageError(f"codex.web_search {out['web_search']!r} must be one of {', '.join(WEB_SEARCH_MODES)}")
    stop = staged.get("quota_stop_percent")
    if stop is not None and (isinstance(stop, bool) or not isinstance(stop, (int, float)) or not 0 < stop <= 100):
        raise UsageError(f"codex.quota_stop_percent {stop!r} must be a number above 0 and at most 100 (or absent)")
    out["quota_stop_percent"] = None if stop is None else float(stop)
    if not 0 < out["quota_timeout_s"] <= 600:
        raise UsageError("codex.quota_timeout_s must be above 0 and at most 600")
    out.update(lane_settings(base, staged))
    if out["codex_home"] is not None and out["quota_stop_percent"] is not None:
        raise UsageError("codex.quota_stop_percent reads the native Codex login's usage; it cannot gate a gateway "
                         "provider's account pool, so it must be absent when codex.provider is not native")
    out["fallback"] = staged.get("fallback")
    if out["fallback"] is not None:
        fallback = out["fallback"]
        if not isinstance(fallback, dict) or fallback.get("provider") != "omniroute":
            raise UsageError("codex.fallback must stage the omniroute provider")
        if out["provider"] != "native" or "/" in out["model"]:
            raise UsageError("codex.fallback needs the native provider and a model without a provider segment")
        fallback_model(out["model"], out["request_effort"])
        out["gateway"] = staged_gateway(staged, fallback.get("base_url"))
        out["fallback"] = {"provider": "omniroute", "base_url": out["gateway"]["endpoint"]}
    out["apps"] = False
    return out


def staged_gateway(staged: dict, endpoint) -> dict:
    """Validate the carried endpoint anew; only a named staged exception supplies an override reason."""
    metadata = staged.get("gateway")
    reason = None
    if metadata is not None:
        if not isinstance(metadata, dict) or metadata.get("source") not in ("host-record", "unrecorded"):
            raise GatewayRefused("codex.gateway must identify host-record or unrecorded provenance")
        if gateway_endpoint(metadata.get("endpoint")) != gateway_endpoint(endpoint):
            raise GatewayRefused("codex.gateway.endpoint differs from the staged provider endpoint; restage")
        if metadata["source"] == "unrecorded":
            reason = metadata.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise GatewayRefused("codex.gateway with source unrecorded needs a non-blank reason")
        elif metadata.get("reason") is not None:
            raise GatewayRefused("codex.gateway with source host-record must carry a null reason")
    return resolve_gateway(endpoint, reason, GATEWAY_VARIABLES)


def lane_settings(base: Path, staged: dict) -> dict:
    """The GPT-6 lane's provider. native (the default) runs Codex with --ignore-user-config against the caller's
    login. A gateway provider (omniroute) runs Codex with CODEX_HOME set to the staged lane-local home
    <work-dir>/<codex_home>: its config.toml (the provider block and the token MCP servers) and its profile file are
    the lane's whole configuration, and the provider's API key comes from the named environment variable. Its static
    provider headers (codex.http_headers) must be the ones that config.toml carries."""
    provider = str(staged.get("provider") or "native")
    if provider not in PROVIDERS:
        raise UsageError(f"codex.provider {provider!r} must be one of {', '.join(PROVIDERS)}")
    headers = staged.get("http_headers")
    if headers is not None and not isinstance(headers, dict):
        raise UsageError("codex.http_headers must be a table of header names and values; restage with build_args.py")
    for name, value in (headers or {}).items():
        if name not in OMNIROUTE_REQUEST_HEADERS:  # never echoed: a refused name may be anything
            raise UsageError(f"codex.http_headers may hold only OmniRoute's per-request switches "
                             f"({', '.join(OMNIROUTE_REQUEST_HEADERS)}): other headers can carry a secret; restage "
                             "with build_args.py")
        if not (isinstance(value, str) and HEADER_VALUE.fullmatch(value)):
            raise UsageError(f"codex.http_headers {name}: the value must be 1-128 printable ASCII characters without "
                             "'\"' or '\\' and without a space at either end; restage with build_args.py")
    headers = dict(sorted((headers or {}).items()))
    lane = {"provider": provider, "codex_home": None, "profile": None, "api_key_env": None,
            "api_key_placeholder": None, "http_headers": headers, "gateway": None}
    if provider == "native":
        if headers:
            raise UsageError("codex.http_headers needs a gateway provider: the native lane has no provider block")
        return lane
    gateway = staged_gateway(staged, staged.get("base_url"))
    home = staged.get("codex_home")
    if not isinstance(home, str) or not home or Path(home).is_absolute() or ".." in Path(home).parts:
        raise UsageError("codex.codex_home must name a directory inside the work directory")
    if not (base / home / "config.toml").is_file():
        raise UsageError(f"codex.codex_home {home!r} holds no config.toml; restage with build_args.py")
    refuse_home_endpoints(base / home, gateway, GATEWAY_VARIABLES)
    profile = staged.get("profile")
    if profile is not None and not (isinstance(profile, str) and PROFILE_NAME.fullmatch(profile)):
        raise UsageError(f"codex.profile {profile!r} is not a profile name")
    if profile is not None and not (base / home / f"{profile}.config.toml").is_file():
        raise UsageError(f"codex.profile {profile!r} has no {profile}.config.toml in the lane home; restage")
    key = staged.get("api_key_env")
    if not isinstance(key, str) or not ENV_NAME.fullmatch(key):
        raise UsageError("codex.api_key_env must name the environment variable that holds the provider key")
    placeholder = staged.get("api_key_placeholder")
    if placeholder is not None and not (isinstance(placeholder, str) and PROFILE_NAME.fullmatch(placeholder)):
        raise UsageError("codex.api_key_placeholder must be a short plain token (a keyless loopback gateway's value)")
    carried = lane_home_headers(base / home / "config.toml", provider)
    if carried is None and headers:
        raise UsageError("comparing codex.http_headers with the lane home config.toml needs Python 3.11+ (tomllib); "
                         "run the harness with a newer python3, or restage without --omniroute-header")
    if carried is not None and carried != headers:
        raise UsageError(f"the lane home config.toml does not carry the staged provider headers (codex.http_headers "
                         f"{sorted(headers)}, model_providers.{provider}.http_headers "
                         f"{sorted(carried) if isinstance(carried, dict) else carried!r}); restage with build_args.py")
    lane.update(codex_home=base / home, profile=profile, api_key_env=key, api_key_placeholder=placeholder,
                base_url=gateway["endpoint"], gateway=gateway)
    return lane


def lane_home_headers(config: Path, provider: str):
    """model_providers.<provider>.http_headers in the lane home's config.toml, {} when absent. None without tomllib
    (Python 3.9 and 3.10): lane_settings then refuses staged headers and skips the check for a header-less lane."""
    try:
        import tomllib
    except ImportError:
        return None
    try:
        parsed = tomllib.loads(config.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise UsageError(f"the lane home config.toml is not valid TOML ({error}); restage with build_args.py") from None
    providers = parsed.get("model_providers")
    table = providers.get(provider) if isinstance(providers, dict) else None
    headers = table.get("http_headers") if isinstance(table, dict) else None
    return {} if headers is None else headers


def job_dir(base: Path, job: str) -> Path:
    if not JOB_ID.fullmatch(job or ""):
        raise UsageError(f"job id {job!r} must match {JOB_ID.pattern}")
    return base / "gpt6" / job


def read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None


def write_atomic(path: Path, text: str, *, private: bool = False) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    if private:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(text)
    else:
        temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def try_lock(fd: int) -> bool:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as error:
        if error.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
            return False
        raise


def open_lock(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o644)


def exit_code(directory: Path) -> int | None:
    text = read(directory / "exit")
    try:
        return int(text.strip()) if text is not None else None
    except ValueError:
        return None


def finish(directory: Path, code: int, failure_kind: str | None = None, *, terminal: bool = True) -> None:
    if code != 0:
        record = read_json(directory / "failure.json")
        if failure_kind is not None or not isinstance(record, dict) or record.get("exit") != code:
            record = {"kind": failure_kind or "exit", "exit": code, "retryable": False,
                      "retrying": False, "delay_s": None}
        elif terminal:
            record["retrying"] = False
            record["delay_s"] = None
        write_atomic(directory / "failure.json", json.dumps(record, sort_keys=True) + "\n")
    write_atomic(directory / "finished", utc_now() + "\n")
    write_atomic(directory / "exit", f"{code}\n")
    if terminal:
        (directory / "done").touch()


def running(directory: Path) -> bool:
    """True while a runner or its codex holds the job lock."""
    if not (directory / "job.lock").exists():
        return False
    fd = open_lock(directory / "job.lock")
    try:
        if try_lock(fd):
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        return True
    finally:
        os.close(fd)


def events(directory: Path) -> list[dict]:
    out = []
    for line in (read(directory / "events.jsonl") or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            out.append(event)
    return out


def completion_error(directory: Path) -> str | None:
    """Exit 0 alone is insufficient; completion JSONL and the final output are independent evidence."""
    # Completed turns emit turn.completed and enable -o output (rust-v0.159.2,
    # codex-rs/exec/src/event_processor_with_jsonl_output.rs:525-536,631-635). The writer can leave empty content or
    # warn on failure (codex-rs/exec/src/event_processor.rs:31-46). The npm wrapper can exit 0 after SIGTERM
    # (codex-cli/bin/codex.js:270-293); exec can also exit without completion on a closed event stream
    # (codex-rs/exec/src/lib.rs:1251-1252,1318-1326). Check all three signals before accepting success.
    missing = []
    if not any(event.get("type") == "turn.completed" for event in events(directory)):
        missing.append("missing turn.completed")
    if not (read(directory / "last.json") or "").strip():
        missing.append("missing or empty -o output file")
    return "; ".join(missing) or None


def attempt_outcome(directory: Path) -> tuple[int | None, dict | None]:
    """Report legacy false successes as failures, while retaining their original files unchanged."""
    code, failure = exit_code(directory), read_json(directory / "failure.json")
    reason = completion_error(directory) if code == 0 else None
    if reason:
        code, failure = EXIT_INCOMPLETE, {"kind": "incomplete", "exit": EXIT_INCOMPLETE, "reason": reason,
                                          "retryable": False, "retrying": False, "delay_s": None}
    return code, failure


def turn_usage(directory: Path) -> dict | None:
    """Summed `turn.completed` usage, or None when Codex reported no usage (no turn completed)."""
    usage, reported = {}, False
    for event in events(directory):
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            reported = True
            for key, value in event["usage"].items():
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
    return usage if reported else None


def limit_kind(directory: Path, provider: str | None = None) -> str | None:
    """"usage" when Codex itself reported the usage limit, "http_429" when it reported an HTTP 429 without one: in an
    `error` / `turn.failed` event, or, when none matched and no turn completed, in one of its own error lines on stderr.
    A completed turn was not limited, whatever a diagnostic line quotes. Within one source (events, else stderr) a
    usage-limit report wins over a 429 report."""
    if provider is None:
        provider = (read_json(directory / "route.json") or read_json(directory / "inputs.json") or {}).get("provider")
    parsed = events(directory)
    kinds = set()
    for event in parsed:
        if event.get("type") == "error":
            message = event.get("message")
        elif event.get("type") == "turn.failed" and isinstance(event.get("error"), dict):
            message = event["error"].get("message")
        else:
            continue  # item.* events carry model content: never evidence of a limit
        if isinstance(message, str):
            kinds.update(kind for kind, pattern in LIMIT_PATTERNS if pattern.search(message))
    if provider != "omniroute" and not kinds and not any(event.get("type") == "turn.completed" for event in parsed):
        for line in (read(directory / "stderr.txt") or "").splitlines():
            if STDERR_ERROR_LINE.match(line):
                kinds.update(kind for kind, pattern in LIMIT_PATTERNS if pattern.search(line))
    return "usage" if "usage" in kinds else ("http_429" if kinds else None)


def limit_error(directory: Path) -> bool:
    """Codex itself reported a limit (see limit_kind)."""
    return limit_kind(directory) is not None


def capacity_error(directory: Path) -> bool:
    """Match Codex error reports, never quoted model or web content, as in limit_kind."""
    parsed = events(directory)
    for event in parsed:
        message = (event.get("message") if event.get("type") == "error" else
                   (event["error"].get("message") if event.get("type") == "turn.failed"
                    and isinstance(event.get("error"), dict) else None))
        if isinstance(message, str) and CAPACITY_PHRASE.search(message):
            return True
    return not any(e.get("type") == "turn.completed" for e in parsed) and any(
        STDERR_ERROR_LINE.match(line) and CAPACITY_PHRASE.search(line)
        for line in (read(directory / "stderr.txt") or "").splitlines())


def codex_env(lane: dict | None = None) -> dict:
    """The caller's environment without Rust tracing settings (see the module docstring). For a gateway lane,
    CODEX_HOME points at the staged lane-local home, never at the caller's; the key variable passes through as it is
    and is never written anywhere."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("RUST_LOG")}
    if lane is not None:
        if lane.get("codex_home") is not None:
            env["CODEX_HOME"] = str(lane["codex_home"])
        if not (env.get(lane["api_key_env"]) or "").strip() and lane.get("api_key_placeholder"):
            env[lane["api_key_env"]] = lane["api_key_placeholder"]  # keyless loopback gateway; a real key wins
    return child_env(env)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fallback_model(model: str, effort: str) -> str:
    """The pinned OmniRoute suffix must select the native request effort; unsupported aliases are refused."""
    if effort not in ("low", "medium", "high", "xhigh") and not (
            effort == "max" and model in FALLBACK_MAX_ALIAS_MODELS):
        raise UsageError(f"codex.fallback has no OmniRoute reasoning alias for {model!r} at request effort {effort!r}")
    return f"cx/{model}-{effort}"


def request_effort(model: str, effort: str) -> str:
    """Ultra resolves per request; other effort values pass through (rust-v0.159.2,
    codex-rs/protocol/src/openai_models/reasoning_effort.rs:12-35; codex-rs/core/src/client.rs:863-872)."""
    if effort != "ultra":
        return effort
    names = (model, model.partition("/")[2]) if "/" in model else (model,)
    for name in names:
        for slug in sorted(MODEL_EFFORTS, key=len, reverse=True):
            if name.startswith(slug):
                return MODEL_MULTI_AGENT_EFFORTS.get(slug) or "max"
    return "max"  # settings() refuses ultra for models outside the catalog


def same_inputs(bound: dict | None, current: dict) -> bool:
    """Older inputs omit request_effort; derive it without changing their retained bytes."""
    if not isinstance(bound, dict):
        return bound is None and current is None
    normalized = dict(bound)
    normalized.setdefault("request_effort", request_effort(bound.get("model", DEFAULT_MODEL),
                                                          bound.get("effort", DEFAULT_EFFORT)))
    return normalized == current


def usage_status(directory: Path, usage: dict | None) -> str:
    """Exec reports primary-thread totals; delegated usage is not proven complete (rust-v0.159.2,
    codex-rs/exec/src/lib.rs:1636-1638; event_processor_with_jsonl_output.rs:509-511,533-535).
    JSONL collab_tool_call is declared in codex-rs/exec/src/exec_events.rs:106,124."""
    inputs = read_json(directory / "inputs.json") or {}
    delegated = inputs.get("effort") == "ultra"
    for event in events(directory):
        item = event.get("item")
        types = (event.get("type", ""), item.get("type", "") if isinstance(item, dict) else "")
        delegated = delegated or any(isinstance(kind, str) and
                                     any(part in kind.lower() for part in ("collab", "sub_agent", "subagent"))
                                     for kind in types)
    return "primary_thread_only" if delegated else ("reported" if usage is not None else "unavailable")


def job_inputs(prompt: bytes, schema: bytes, model: str, provider: str = "native",
               http_headers: dict | None = None, effort: str = DEFAULT_EFFORT,
               web_search: str = DEFAULT_WEB_SEARCH, gateway: dict | None = None) -> dict:
    inputs = {"prompt_sha256": sha256_hex(prompt), "schema_sha256": sha256_hex(schema), "model": model,
              "effort": effort, "request_effort": request_effort(model, effort), "apps": False}
    if web_search != DEFAULT_WEB_SEARCH:  # old records used live implicitly; preserve valid same-input reuse
        inputs["web_search"] = web_search
    if provider != "native":  # a gateway run never reuses a native job's result, or the other way round
        inputs["provider"] = provider
    if provider == "omniroute" and gateway is not None:
        # E1's host-gateway contract v2 resolves this endpoint/source/reason tuple.
        # codex_argv sends its endpoint as a dotted -c provider override (openai/codex
        # rust-v0.160.1 `codex exec --help`), making it part of the invocation identity.
        # Older records without it stay unchanged and cannot match a new primary run.
        inputs["gateway"] = {field: gateway[field] for field in ("endpoint", "source", "reason")}
    if http_headers:  # other provider headers (another compression plan, say) make another run
        inputs["http_headers"] = dict(sorted(http_headers.items()))
    return inputs


def read_json(path: Path):
    text = read(path)
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return None


def prompt_stdin_bytes(raw_prompt: bytes) -> bytes:
    """Preserve the former Path.read_text(utf-8).rstrip('\n') delivery, not the raw-file representation.

    TextIOWrapper uses the same UTF-8/universal-newline read as Path.read_text.
    Codex's stdin path returns its input untrimmed (rust-v0.160.1 exec/src/lib.rs:2275),
    so this holder must retain its existing LF-only stripping before delivery."""
    with io.TextIOWrapper(io.BytesIO(raw_prompt), encoding="utf-8") as source:
        return source.read().rstrip("\n").encode("utf-8")


def archive_attempt(directory: Path, *, keep_runner_log: bool = False) -> int | None:
    """Move an earlier attempt's files, unchanged, to attempts/<n>/ (n = 1, 2, ...); None when there was none."""
    present = [name for name in ATTEMPT_FILES if (directory / name).exists()
               and not (keep_runner_log and name == "runner.log")]
    if not present:
        return None
    attempts = directory / "attempts"
    attempts.mkdir(exist_ok=True)
    number = 1 + max((int(p.name) for p in attempts.iterdir() if p.name.isdigit()), default=0)
    target = attempts / str(number)
    target.mkdir()
    for name in present:
        os.replace(directory / name, target / name)
    return number


def codex_argv(codex: str, directory: Path, model: str, prompt: str, lane: dict | None = None,
               version: str | None = None, effort: str = DEFAULT_EFFORT,
               web_search: str = DEFAULT_WEB_SEARCH) -> list[str]:
    if lane is not None and lane.get("codex_home") is not None:
        # The lane-local CODEX_HOME is the whole configuration, so --ignore-user-config (which drops
        # $CODEX_HOME/config.toml) must not be passed; the profile layers <profile>.config.toml over it (profile-v2).
        head = [codex, "exec", *(["-p", lane["profile"]] if lane.get("profile") else [])]
        # This holder's endpoint pin outranks other configuration only if T17p's
        # real-CLI, project-layer control passes at the reviewed head.
        head.extend(["-c", f'model_providers.omniroute.base_url={json.dumps(lane["base_url"])}'])
    else:
        head = [codex, "exec", "--ignore-user-config"]
    if lane is not None and lane.get("transport_only"):
        # Supported inline provider overrides (openai/codex rust-v0.159.3 model-provider-info/src/lib.rs).
        # Keep the native CODEX_HOME/AGENTS.md and --ignore-user-config; no lane home or MCP profile loads.
        provider = {"name": "OmniRoute", "base_url": lane["base_url"], "env_key": FALLBACK_KEY_ENV,
                    "wire_api": "responses", "requires_openai_auth": False, "supports_standalone_web_search": True}
        block = "{ " + ", ".join(f"{key} = {json.dumps(value)}" for key, value in provider.items()) + " }"
        head.extend(["-c", 'model_provider="omniroute"', "-c", f"model_providers.omniroute={block}",
                     "-c", "features.standalone_web_search=true", "-c", "features.shell_snapshot=false",
                     "-c", f'shell_environment_policy.filters.{FALLBACK_KEY_ENV}="exclude"'])
    # Keep the built-in provider defaults (rust-v0.159.2, codex-rs/model-provider-info/src/lib.rs:492-510).
    # Codex rides out an outage shorter than idle_timeout_s; a longer one is stopped by the watchdog and
    # retried once, budget permitting (codex-rs/core/src/responses_retry.rs:71-96). Error notices are not progress.
    # Installed openai/codex rust-v0.160.1 `codex exec --help`: --disable apps
    # is equivalent to -c features.apps=false, even with --ignore-user-config.
    return [*head, "--disable", "apps", "--skip-git-repo-check", "-s", "read-only",
            "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", f'web_search="{web_search}"',
            "--output-schema", str(directory / "schema.json"), "-o", str(directory / "last.json"), "--json", "-"]


def retire(directory: Path) -> None:
    """Archive a finished attempt without starting a new one (skipped while a runner holds the job)."""
    lock_fd = open_lock(directory / "job.lock")
    try:
        if try_lock(lock_fd):
            archive_attempt(directory)
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def start(base: Path, job: str, prompt_file: str, schema_file: str) -> int:
    directory = job_dir(base, job)
    prompt_bytes = Path(prompt_file).read_bytes()
    schema_bytes = Path(schema_file).read_bytes()
    try:
        config = settings(base)  # initial invalid staging is refused before state changes
    except GatewayRefused:
        raise  # route refusals preserve every existing attempt and spawn nothing
    except (UsageError, ValueError, TypeError, OSError) as error:
        if (directory / "inputs.json").exists() and not running(directory):
            lock_fd = open_lock(directory / "job.lock")
            try:
                if try_lock(lock_fd):
                    saved = {name: (directory / name).read_bytes() for name in ("prompt.txt", "schema.json", "inputs.json")
                             if (directory / name).exists()}
                    archive_attempt(directory)
                    for name, data in saved.items():
                        (directory / name).write_bytes(data)
                    write_atomic(directory / "stderr.txt", "staged settings changed after input binding: " + str(error) + "\n")
                    finish(directory, EXIT_REFUSED, "inputs_changed")
            finally:
                os.close(lock_fd)
            print(f"not started {job}: staged settings changed after input binding", file=sys.stderr)
            return EXIT_REFUSED
        raise
    inputs = job_inputs(prompt_bytes, schema_bytes, config["model"], config["provider"], config["http_headers"],
                        config["effort"], config["web_search"], gateway=config["gateway"])
    if (directory / "done").exists() and exit_code(directory) == 0:
        matches = same_inputs(read_json(directory / "inputs.json"), inputs)
        route = read_json(directory / "route.json") or {}
        if route.get("fallback_from") == "native":
            fallback = config["fallback"]
            matches = (matches and fallback is not None and route.get("provider") == fallback["provider"]
                       and route.get("base_url") == fallback["base_url"]
                       and route.get("gateway_model") == fallback_model(config["model"], config["request_effort"])
                       and route.get("gateway_effort") == config["request_effort"])
        if matches and completion_error(directory) is None:
            print(f"already done: {job}")
            return 0
        if not matches:
            print(f"inputs changed since {job} finished; its attempt is kept under attempts/")
    directory.mkdir(parents=True, exist_ok=True)
    lock_fd = open_lock(directory / "job.lock")
    if not try_lock(lock_fd):
        os.close(lock_fd)
        bound = read_json(directory / "inputs.json")
        if bound is not None and not same_inputs(bound, inputs):
            print(f"already running with different inputs: {job}; not started")
            return EXIT_REFUSED
        print(f"already running: {job}")
        return 0
    try:
        archive_attempt(directory)
        (directory / "prompt.txt").write_bytes(prompt_bytes)
        (directory / "schema.json").write_bytes(schema_bytes)
        write_atomic(directory / "inputs.json", json.dumps(inputs, sort_keys=True) + "\n")
        if (base / "LIMIT").exists():
            text = f"LIMIT marker present; refusing to start {job}"
            reason = limit_reason(base)
            write_atomic(directory / "stderr.txt", text + (f" ({reason})" if reason else "") + "\n")
            finish(directory, EXIT_LIMIT, "limit")
            print(text)
            if reason:
                print(f"LIMIT: {reason}")
            return EXIT_LIMIT
        problem = None
        try:
            json.loads(schema_bytes)
        except ValueError:
            problem = (EXIT_REFUSED, f"schema {schema_file} is not JSON")
        if problem is None and not prompt_stdin_bytes(prompt_bytes):
            problem = (EXIT_REFUSED, "prompt is empty after its existing UTF-8 and LF-only normalization")
        if problem is None and shutil.which("codex") is None:
            problem = (EXIT_NO_CODEX, "codex is not on PATH")
        if problem is not None:
            write_atomic(directory / "stderr.txt", problem[1] + "\n")
            finish(directory, problem[0], "no_codex" if problem[0] == EXIT_NO_CODEX else "refused")
            print(f"not started {job}: {problem[1]}")
            return problem[0]
        (base / "empty").mkdir(exist_ok=True)
        try:
            with open(directory / "runner.log", "wb") as log:
                subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--work-dir", str(base), "run", job],
                                 cwd=str(base), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True, pass_fds=(lock_fd,),
                                 env={**os.environ, "SWEEP_JOB_LOCK_FD": str(lock_fd)})
        except OSError as error:
            write_atomic(directory / "stderr.txt", f"the job runner could not start ({type(error).__name__})\n")
            finish(directory, EXIT_REFUSED, "refused")
            print(f"not started {job}: the job runner could not start")
            return EXIT_REFUSED
    finally:
        os.close(lock_fd)  # the detached runner keeps its inherited copy, so the job stays locked
    print(f"started {job}")
    return 0


def acquire_slot(base: Path, config: dict) -> tuple[int | None, int | None]:
    config["lock_dir"].mkdir(parents=True, exist_ok=True)
    while True:
        for number in range(1, config["slots"] + 1):
            fd = open_lock(config["lock_dir"] / f"slot-{number}")
            if try_lock(fd):
                return fd, number
            os.close(fd)
        time.sleep(config["slot_poll_s"])
        if (base / "LIMIT").exists():
            return None, None


def codex_version(codex: str) -> str | None:
    try:
        done = subprocess.run([codex, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (done.stdout or "").strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def quota_script(script_dir: Path = HERE) -> Path | None:
    """The copy build_args.py staged beside this file; in the checkout (no staged.json here), scripts/codex_quota.py."""
    staged = script_dir / QUOTA_SCRIPT
    if staged.is_file():
        return staged
    if (script_dir / STAGED).is_file() or len(script_dir.parents) <= 2:
        return None  # a staged runner uses only its own frozen copy
    checkout = script_dir.parents[2] / "scripts" / QUOTA_SCRIPT
    return checkout if checkout.is_file() else None


def quota_gate(base: Path, directory: Path, config: dict, deadline: float | None = None) -> str | None:
    """Run the quota probe with --gate and record it in <job>/quota.json; the reason when the gate is reached, else
    None. A failed probe is recorded and never blocks the job."""
    percent = config["quota_stop_percent"]
    record = {"checked_at": utc_now(), "stop_percent": percent, "status": "probe_failed", "exit": None,
              "report": None}
    remaining = deadline - time.monotonic() if deadline is not None else math.inf
    helper_timeout = min(config["quota_timeout_s"], remaining)
    parent_timeout = min(config["quota_timeout_s"] + QUOTA_BACKSTOP_S, remaining)
    script = quota_script()
    if remaining <= 0:
        record["error"] = "the job deadline expired before the quota probe could start"
    elif script is None:
        record["error"] = f"{QUOTA_SCRIPT} is neither beside the runner nor in the checkout's scripts/"
    else:
        try:
            done = subprocess.run([sys.executable, "-B", str(script), "--json",
                                   *(["--gate", repr(float(percent))] if percent is not None else []),
                                   "--timeout", repr(float(helper_timeout))],
                                  cwd=str(base / "empty"), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=parent_timeout, env=codex_env(), check=False)
            lines = (done.stdout or "").strip().splitlines()
            try:
                report = json.loads(lines[-1]) if lines else None
            except ValueError:
                report = None
            record.update(exit=done.returncode, report=report if isinstance(report, dict) else None)
            if done.returncode in (0, 3) and record["report"] is not None:
                record["status"] = "gate" if done.returncode == 3 else "ok"
            else:
                error = (record["report"] or {}).get("error")
                record["error"] = (f"{error.get('stage')}: {error.get('message')}" if isinstance(error, dict)
                                   else (done.stderr or "").strip()[-400:] or f"exit {done.returncode}")
        except subprocess.TimeoutExpired:
            record["error"] = f"the quota probe did not finish within {parent_timeout:g} s"
        except (OSError, subprocess.SubprocessError) as error:
            record["error"] = f"the quota probe could not run ({type(error).__name__})"
    write_atomic(directory / "quota.json", json.dumps(record, sort_keys=True) + "\n")
    if record["status"] != "gate":
        return None
    reasons = ((record["report"] or {}).get("gate") or {}).get("reasons") or []
    return "; ".join(str(reason) for reason in reasons) or "the quota gate was reached"


def quota_summary(directory: Path) -> dict | None:
    record = read_json(directory / "quota.json")
    if not isinstance(record, dict):
        return None
    report = record.get("report") if isinstance(record.get("report"), dict) else {}
    return {"status": record.get("status"), "stop_percent": record.get("stop_percent"),
            "checked_at": record.get("checked_at"), "used_percent": report.get("used_percent"),
            "resets_at_utc": report.get("resets_at_utc"),
            "reasons": (report.get("gate") or {}).get("reasons") if isinstance(report.get("gate"), dict) else None,
            "error": record.get("error")}


def mark_limit(base: Path, text: str, *, marker: str = "LIMIT") -> None:
    """Create the lane marker holding text; keep an existing marker's original reason."""
    try:
        fd = os.open(base / marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


def limit_reason(base: Path) -> str:
    return " ".join((read(base / "LIMIT") or "").split())[:400]


def mark_native_limit(base: Path, directory: Path, reason: str | None = None) -> str:
    """Keep the native reason and its reported reset time; an unknown reset stays unknown."""
    if reason is None:
        messages = []
        for event in events(directory):
            message = (event.get("message") if event.get("type") == "error" else
                       (event.get("error") or {}).get("message") if event.get("type") == "turn.failed"
                       and isinstance(event.get("error"), dict) else None)
            if isinstance(message, str) and any(pattern.search(message) for _, pattern in LIMIT_PATTERNS):
                messages.append(message)
        if not messages:
            messages = [line for line in (read(directory / "stderr.txt") or "").splitlines()
                        if STDERR_ERROR_LINE.match(line) and any(pattern.search(line) for _, pattern in LIMIT_PATTERNS)]
        reason = next((message for message in messages if LIMIT_PHRASE.search(message)),
                      messages[-1] if messages else "native Codex limit")
    reset = re.search(r"try again at\s+([^\n]+)", reason, re.IGNORECASE)
    quota = quota_summary(directory) or {}
    record = {"reason": reason, "reset_time": reset[1] if reset else quota.get("resets_at_utc")}
    mark_limit(base, json.dumps(record, sort_keys=True), marker="LIMIT-native")
    return reason


def refresh_native_limit(base: Path, directory: Path, config: dict, deadline: float) -> None:
    """A no-model account/rateLimits/read probe; only explicit ordinaryUsageAllowed true clears the marker.

    Percentages and reset timestamps are not recovery evidence (openai/codex rust-v0.159.3,
    app-server-protocol/src/protocol/v2/account.rs, GetAccountRateLimitsResponse).
    """
    quota_gate(base, directory, {**config, "quota_stop_percent": None}, deadline)
    record = read_json(directory / "quota.json") or {}
    report = record.get("report") or {}
    if record.get("status") == "ok" and report.get("ordinary_usage_allowed") is True:
        (base / "LIMIT-native").unlink(missing_ok=True)


def fallback_route(base: Path, config: dict, *, reason: str | None = None,
                   native_attempt: int | None = None) -> dict:
    """Select the transport separately from bound native inputs; its receipt is written after process launch."""
    marker = read_json(base / "LIMIT-native") or {}
    model = config["model"]
    gateway_model = fallback_model(model, config["request_effort"])
    route = {"provider": "omniroute", "fallback_from": "native",
             "reason": reason or marker.get("reason") or "LIMIT-native marker present",
             "native_model": model, "gateway_model": gateway_model, "native_attempt": native_attempt,
             "base_url": config["fallback"]["base_url"], "gateway_effort": config["request_effort"],
             "search_backend": FALLBACK_SEARCH_BACKEND}
    return {**config, **config["fallback"], "model": gateway_model, "transport_only": True,
            "api_key_env": FALLBACK_KEY_ENV, "api_key_placeholder": "local-loopback", "quota_stop_percent": None,
            "route": route}


def signal_group(pgid: int, signum: int) -> bool:
    """killpg for the job's own process group; False when nothing took the signal. ESRCH: the group is gone. EPERM:
    on Darwin, killpg skips zombies and reports EPERM when a still-existing group has no other member
    (apple-oss-distributions/xnu xnu-12377.121.6, bsd/kern/kern_sig.c, killpg1: the `p_stat != SZOMB` filter and
    `nfound > 0 ? 0 : EPERM`), so the group only holds members that have already exited; Linux signals a zombie
    silently. Every member is this runner's own descendant, so EPERM never means a live process of another user."""
    try:
        os.killpg(pgid, signum)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def group_alive(pgid: int) -> bool:
    return signal_group(pgid, 0)


def stop_group(process: subprocess.Popen, grace_s: float) -> None:
    """TERM the job's whole process group, then KILL whatever is left of it after the grace period, including
    children that ignore TERM after Codex itself has exited (they would keep the slot and job locks)."""
    pgid = process.pid
    signal_group(pgid, signal.SIGTERM)
    end = time.monotonic() + grace_s
    while time.monotonic() < end:
        if process.poll() is not None and not group_alive(pgid):
            return
        time.sleep(0.1)
    signal_group(pgid, signal.SIGKILL)
    process.wait()


def wait_process(process: subprocess.Popen, directory: Path, config: dict, deadline: float) -> tuple[int, str | None]:
    """Bound the whole invocation and silence in complete non-error JSONL events; stderr is not progress."""
    last_event = time.monotonic()
    pending = b""
    completed = False
    with open(directory / "events.jsonl", "rb") as activity:
        while process.poll() is None:
            pending += activity.read()
            lines = pending.split(b"\n")
            pending = lines.pop()
            for line in lines:
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                # Unbounded reconnects emit StreamError -> Error(will_retry=true) -> JSONL type="error"
                # (rust-v0.159.2, codex-rs/core/src/session/mod.rs:5030-5035;
                # codex-rs/app-server/src/bespoke_event_handling.rs:1054-1070;
                # codex-rs/exec/src/event_processor_with_jsonl_output.rs:447-458). Notices are not progress.
                if isinstance(event, dict) and isinstance(event.get("type"), str) and event["type"] != "error":
                    last_event = time.monotonic()
                    completed = completed or event["type"] == "turn.completed"
            now = time.monotonic()
            if now >= deadline:
                if completed:
                    # exec emits turn.completed, shuts down, then writes -o (rust-v0.159.2,
                    # codex-rs/exec/src/lib.rs:1318-1321; event_processor_with_jsonl_output.rs:631-636).
                    try:
                        return process.wait(timeout=config["kill_grace_s"]), None
                    except subprocess.TimeoutExpired:
                        pass
                stop_group(process, config["kill_grace_s"])
                return EXIT_TIMEOUT, "timeout"
            if now - last_event >= config["idle_timeout_s"]:
                stop_group(process, config["kill_grace_s"])
                return EXIT_IDLE, "idle"
            try:
                return process.wait(timeout=min(1.0, deadline - now,
                                                config["idle_timeout_s"] - (now - last_event))), None
            except subprocess.TimeoutExpired:
                pass
    return process.returncode, None


def run(base: Path, job: str) -> int:
    directory = job_dir(base, job)
    lock_fd = int(os.environ.get("SWEEP_JOB_LOCK_FD", "-1"))
    config_error = None
    try:
        config = settings(base)
    except GatewayRefused as error:
        if lock_fd < 0:
            raise  # a hand-run refusal creates no lock or receipt
        # start already owns this inherited lock and has bound the fresh snapshot.
        # Retain the refusal through the existing inputs_changed terminal path below.
        config_error = error
    except (UsageError, ValueError, TypeError, OSError) as error:
        config_error = error
    if lock_fd < 0:  # started by hand, not by `start`
        lock_fd = open_lock(directory / "job.lock")
        if not try_lock(lock_fd):
            os.close(lock_fd)
            print(f"already running: {job}")
            return 0
    if config_error is not None:
        write_atomic(directory / "stderr.txt", "staged settings changed after input binding: " + str(config_error) + "\n")
        finish(directory, EXIT_REFUSED, "inputs_changed")
        os.close(lock_fd)
        return EXIT_REFUSED
    slot_fd = None
    try:
        slot_fd, slot = acquire_slot(base, config)
        return run_attempts(base, job, directory, config, lock_fd, slot_fd, slot)
    except (UsageError, ValueError, TypeError, OSError) as error:
        write_atomic(directory / "stderr.txt", f"runner refused: {error}\n")
        finish(directory, EXIT_REFUSED, "refused")
        return EXIT_REFUSED
    finally:
        if slot_fd is not None:
            os.close(slot_fd)
        os.close(lock_fd)


def run_attempts(base: Path, job: str, directory: Path, config: dict, lock_fd: int,
                 slot_fd: int | None, slot: int | None) -> int:
    if slot_fd is None or (base / "LIMIT").exists():
        reason = limit_reason(base)
        write_atomic(directory / "stderr.txt", "LIMIT marker present; the job did not start"
                     + (f" ({reason})" if reason else "") + "\n")
        finish(directory, EXIT_LIMIT, "limit")
        return EXIT_LIMIT
    prompt_bytes = (directory / "prompt.txt").read_bytes()
    schema_bytes = (directory / "schema.json").read_bytes()
    bound = read_json(directory / "inputs.json")
    if bound is not None and not same_inputs(bound, job_inputs(
            prompt_bytes, schema_bytes,
            config["model"], config["provider"], config["http_headers"], config["effort"], config["web_search"],
            gateway=config["gateway"])):
        # start and the detached runner read staged.json separately; never execute under another input identity.
        write_atomic(directory / "stderr.txt", "staged settings changed after input binding; start the job again\n")
        finish(directory, EXIT_REFUSED, "inputs_changed")
        return EXIT_REFUSED
    prompt_bytes_delivered = prompt_stdin_bytes(prompt_bytes)
    if not prompt_bytes_delivered:
        write_atomic(directory / "stderr.txt", "prompt is empty after its existing UTF-8 and LF-only normalization\n")
        finish(directory, EXIT_REFUSED, "refused")
        return EXIT_REFUSED
    prompt_transport = {"kind": "stdin", "delivered_bytes": len(prompt_bytes_delivered),
                        "delivered_sha256": sha256_hex(prompt_bytes_delivered)}
    write_atomic(directory / "model", config["model"] + "\n")
    deadline = time.monotonic() + config["timeout_s"]  # includes version, every probe, attempts and backoff
    codex = shutil.which("codex")
    if codex is None:
        write_atomic(directory / "stderr.txt", "codex is not on PATH\n")
        finish(directory, EXIT_NO_CODEX, "no_codex")
        return EXIT_NO_CODEX
    lane = config if config["codex_home"] is not None else None
    if lane is not None and not (os.environ.get(lane["api_key_env"]) or "").strip() and not lane["api_key_placeholder"]:
        write_atomic(directory / "stderr.txt", f"{lane['api_key_env']} is not set in the runner's environment; start "
                     "the harness with the gateway key loaded from its store by pointer (docs/secret-storage.md)\n")
        finish(directory, EXIT_NO_KEY, "no_key")
        return EXIT_NO_KEY
    version = codex_version(codex)
    if version:
        write_atomic(directory / "codex_version", version + "\n")
    prompt = prompt_bytes_delivered.decode("utf-8")  # same delivered text as the former argv path
    (base / "empty").mkdir(exist_ok=True)
    saved = {name: (directory / name).read_bytes() for name in ("prompt.txt", "schema.json", "inputs.json")
             if (directory / name).exists()}
    attempt_config = config
    if config["fallback"] is not None and (base / "LIMIT-native").exists():
        refresh_native_limit(base, directory, config, deadline)
        if (base / "LIMIT-native").exists():
            attempt_config = fallback_route(base, config)
            lane = attempt_config
    capacity_retries = idle_retries = 0
    native_failure = None
    gateway_started = False
    while True:
        if (base / "LIMIT").exists():
            if native_failure is not None:
                archive_attempt(directory, keep_runner_log=True)
                for name, data in saved.items():
                    (directory / name).write_bytes(data)
            write_atomic(directory / "stderr.txt", "LIMIT marker present; retry did not start\n")
            finish(directory, EXIT_LIMIT, "limit")
            return EXIT_LIMIT
        if attempt_config["quota_stop_percent"] is not None:
            reason = quota_gate(base, directory, attempt_config, deadline)
            if reason is not None:
                text = (f"quota gate: {reason}; codex.quota_stop_percent {config['quota_stop_percent']:g}; checked "
                        f"{utc_now()} before {job} started")
                write_atomic(directory / "stderr.txt", text + "\n")
                if config["fallback"] is not None:
                    mark_native_limit(base, directory, text)
                    finish(directory, EXIT_LIMIT, "quota", terminal=False)
                    native_failure = "quota"
                    attempt_config = fallback_route(base, config, reason=text)
                    lane = attempt_config
                    continue
                mark_limit(base, text)
                finish(directory, EXIT_LIMIT, "quota")
                return EXIT_LIMIT
        if (base / "LIMIT").exists():
            write_atomic(directory / "stderr.txt", "LIMIT marker present; attempt did not start\n")
            finish(directory, EXIT_LIMIT, "limit")
            return EXIT_LIMIT
        remaining = deadline - time.monotonic()
        if native_failure is not None and remaining < RETRY_MIN_REMAINING_S:
            # Keep the latest native limit as terminal, including after earlier capacity/idle retries.
            finish(directory, EXIT_LIMIT, native_failure)
            return EXIT_LIMIT
        if (capacity_retries or idle_retries) and remaining < RETRY_MIN_REMAINING_S:
            # A probe can spend the retry reserve, even past the deadline. Keep the original failure.
            write_atomic(directory / "failure.json", json.dumps(previous_record, sort_keys=True) + "\n")
            finish(directory, previous_code)
            return previous_code
        if remaining <= 0:
            finish(directory, EXIT_TIMEOUT, "timeout")
            return EXIT_TIMEOUT
        if attempt_config.get("transport_only") and not gateway_started and remaining < RETRY_MIN_REMAINING_S:
            finish(directory, EXIT_LIMIT, "limit")
            return EXIT_LIMIT
        if native_failure is not None:
            # Archive only after the hold and reserve checks; otherwise the native limit stays terminal.
            number = archive_attempt(directory, keep_runner_log=True)
            for name, data in saved.items():
                (directory / name).write_bytes(data)
            attempt_config["route"]["native_attempt"] = number
            native_failure = None
        # No HTTP or model request is made by this bounded connect. Native-only
        # attempts do not probe an unused fallback; each actual gateway spawn does.
        if attempt_config["provider"] == "omniroute":
            probe_gateway(attempt_config["gateway"]["endpoint"])
        argv = codex_argv(codex, directory, attempt_config["model"], prompt, lane, version,
                          config["effort"], config["web_search"])
        # Paths and arguments stay private. The prompt travels on stdin, never argv.
        write_atomic(directory / "argv.json", json.dumps(argv, ensure_ascii=False) + "\n", private=True)
        write_atomic(directory / "stdin.txt", prompt, private=True)
        # A prepared file avoids a blocking pipe writer and exposes EOF immediately.
        # Popen accepts a file object (Python subprocess docs); the existing watchdog
        # can observe and cancel the child from its first moment, including a reader failure.
        with open(directory / "events.jsonl", "wb") as output, open(directory / "stderr.txt", "wb") as errors, \
                open(directory / "stdin.txt", "rb") as source:
            process = subprocess.Popen(argv,
                                       cwd=str(base / "empty"), stdin=source, stdout=output, stderr=errors,
                                       pass_fds=(slot_fd, lock_fd), start_new_session=True, env=codex_env(lane))
            try:
                write_atomic(directory / "started", utc_now() + "\n")
                write_atomic(directory / "slot", f"{slot}\n")
                write_atomic(directory / "model", attempt_config["model"] + "\n")
                if version:
                    write_atomic(directory / "codex_version", version + "\n")
                route = {"provider": attempt_config["provider"], **(attempt_config.get("route") or {}),
                         "prompt_transport": prompt_transport}
                write_atomic(directory / "route.json", json.dumps(route, sort_keys=True) + "\n")
                if attempt_config.get("route") is not None:
                    gateway_started = True
                code, failure = wait_process(process, directory, config, deadline)
            except BaseException:
                # Metadata/reader/watchdog failure after spawn must not orphan the
                # child or let its inherited semaphore descriptors escape cleanup.
                stop_group(process, config["kill_grace_s"])
                raise
        kind = limit_kind(directory, attempt_config["provider"])
        incomplete = completion_error(directory) if code == 0 else None
        if kind is not None and config["fallback"] is not None and attempt_config["provider"] == "native":
            reason = mark_native_limit(base, directory)
            finish(directory, EXIT_LIMIT, kind, terminal=False)
            native_failure = kind
            attempt_config = fallback_route(base, config, reason=reason)
            lane = attempt_config
            continue
        if kind == "http_429" and attempt_config["provider"] == "omniroute":
            mark_limit(base, f"gateway pool 429; first seen {utc_now()} in {job}; no reset time is reported; "
                       "the report cannot distinguish pool exhaustion from a transient 429; read the gateway pool "
                       "and remove this file when it has capacity")
        elif kind == "http_429":
            mark_limit(base, f"HTTP 429 from the route (Codex retries no 429), first seen {utc_now()} in {job}; the report "
                       "carries no reset time and cannot tell an exhausted pool from a brief rate limit: read the account "
                       "pool (scripts/codex_quota.py for a native login, the gateway for a pooled route) and remove this "
                       "file when it has capacity")
        if kind is not None:
            (base / "LIMIT").touch()
            code, failure = EXIT_LIMIT, kind
        elif incomplete:
            code, failure = EXIT_INCOMPLETE, "incomplete"
        elif code != 0 and failure is None:
            failure = "capacity" if capacity_error(directory) else "exit"
        retry, delay = False, 0.0
        if failure == "capacity" and capacity_retries < config["capacity_max_retries"]:
            delay = min(config["capacity_backoff_max_s"],
                        config["capacity_backoff_s"] * 2 ** capacity_retries * random.uniform(0.9, 1.1))
            retry = True
        elif failure == "idle" and idle_retries == 0:
            retry = True
        retry = (retry and not (base / "LIMIT").exists()
                 and deadline - time.monotonic() - delay >= RETRY_MIN_REMAINING_S)
        if failure is not None:
            record = {"kind": failure, "exit": code, "retryable": failure in ("capacity", "idle"),
                      "retrying": retry, "delay_s": delay if retry else None}
            if failure == "incomplete":
                record["reason"] = incomplete
            write_atomic(directory / "failure.json", json.dumps(record, sort_keys=True) + "\n")
        finish(directory, code, terminal=not retry)
        if not retry:
            return code
        if failure == "capacity":
            capacity_retries += 1
        else:
            idle_retries += 1
        # Do not start a sleep or retry with less than 300 s after the delay. A LIMIT during backoff wins.
        pause_end = time.monotonic() + delay
        while time.monotonic() < pause_end and not (base / "LIMIT").exists():
            time.sleep(min(1.0, max(0.0, pause_end - time.monotonic())))
        if (base / "LIMIT").exists():
            # Preserve the original failed attempt before recording the refused retry.
            archive_attempt(directory, keep_runner_log=True)
            for name, data in saved.items():
                (directory / name).write_bytes(data)
            write_atomic(directory / "stderr.txt", "LIMIT marker present; retry did not start\n")
            finish(directory, EXIT_LIMIT, "limit")
            return EXIT_LIMIT
        if deadline - time.monotonic() < RETRY_MIN_REMAINING_S:
            finish(directory, code)
            return code
        previous_code, previous_record = code, record
        # Retain the failed attempt before restarting, without advertising an intermediate done.
        # runner.log belongs to the still-running supervisor; keep its open file in the current directory.
        archive_attempt(directory, keep_runner_log=True)
        for name, data in saved.items():
            (directory / name).write_bytes(data)


def wait(base: Path, job: str, seconds: float) -> int:
    directory = job_dir(base, job)
    poll_s = DEFAULTS["wait_poll_s"]
    if not (directory / "done").exists():
        try:
            poll_s = settings(base)["wait_poll_s"]
        except (UsageError, ValueError, TypeError):
            pass  # invalid restaging must not prevent observing the runner's inputs_changed receipt
    end = time.monotonic() + seconds
    while not (directory / "done").exists():
        if not running(directory):
            # The runner writes done before it releases the job lock (flock(2): the lock goes when its last
            # descriptor closes). A free lock therefore means finished, never started or dead, and done says which:
            # a job that finishes between the check above and the lock check is done, not "not running".
            if (directory / "done").exists():
                break
            # Never started (a refused start) or its runner died: nothing will write done.
            print("done exit=none (the job is not running)")
            return 0
        remaining = end - time.monotonic()
        if remaining <= 0:
            print("running")
            return 0
        time.sleep(min(poll_s, remaining))
    code, _ = attempt_outcome(directory)
    print(f"done exit={'none' if code is None else code}")
    return 0


def compact(text: str | None) -> str | None:
    if text is None:
        return None
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
    except ValueError:
        return text


def result(base: Path, job: str) -> dict:
    directory = job_dir(base, job)
    done = (directory / "done").exists()
    code, failure = attempt_outcome(directory)
    out = {"status": ("done" if code == 0 else "failed") if done else ("running" if running(directory) else "not_running"),
           "exit": code,
           "started": (read(directory / "started") or "").strip() or None,
           "finished": (read(directory / "finished") or "").strip() or None}
    usage = turn_usage(directory)
    out["usage"] = usage or {}
    out["usage_status"] = usage_status(directory, usage)
    out["output_text"] = compact(read(directory / "last.json"))
    stderr = read(directory / "stderr.txt")
    out["stderr_tail"] = stderr[-400:] if stderr is not None else None
    out["limit"] = limit_error(directory)
    out["limit_marker"] = (base / "LIMIT").exists()
    inputs = read_json(directory / "inputs.json") or {}
    out["model"] = (read(directory / "model") or "").strip() or inputs.get("model", DEFAULT_MODEL)
    out["codex_version"] = (read(directory / "codex_version") or "").strip() or None
    out["inputs"] = read_json(directory / "inputs.json")
    out["effort"] = (out["inputs"] or {}).get("effort", DEFAULT_EFFORT)
    out["request_effort"] = inputs.get("request_effort", request_effort(out["model"], out["effort"]))
    out["web_search"] = (out["inputs"] or {}).get("web_search", DEFAULT_WEB_SEARCH)
    out["attempts"] = [attempt_summary(path) for path in sorted(
        (p for p in (directory / "attempts").glob("*") if p.name.isdigit()), key=lambda p: int(p.name))]
    out["quota"] = quota_summary(directory)
    out["route"] = read_json(directory / "route.json")
    out["failure"] = failure
    return out


def attempt_summary(path: Path) -> dict:
    usage = turn_usage(path)
    code, failure = attempt_outcome(path)
    return {"attempt": int(path.name), "exit": code,
            "started": (read(path / "started") or "").strip() or None,
            "finished": (read(path / "finished") or "").strip() or None,
            "usage": usage, "usage_status": usage_status(path, usage),
            "limit": limit_error(path), "inputs": read_json(path / "inputs.json"),
            "quota": quota_summary(path), "failure": failure, "route": read_json(path / "route.json")}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit = None
    if argv[:1] == ["--work-dir"]:
        if len(argv) < 2:
            print("--work-dir needs a directory", file=sys.stderr)
            return EXIT_REFUSED
        explicit, argv = argv[1], argv[2:]
    elif argv and argv[0].startswith("--work-dir="):
        explicit, argv = argv[0].split("=", 1)[1], argv[1:]
    command, rest = (argv[0], argv[1:]) if argv else ("", [])
    arity = {"start": (3, 3), "wait": (1, 2), "result": (1, 1), "run": (1, 1), "gateway-check": (0, 1)}
    if command not in arity or not arity[command][0] <= len(rest) <= arity[command][1]:
        print("usage: codex_call.sh [--work-dir DIR] start <job-id> <prompt-file> <schema-file> | "
              "wait <job-id> [seconds] | result <job-id> | gateway-check <work-dir>", file=sys.stderr)
        return EXIT_REFUSED
    try:
        if command == "gateway-check" and rest:
            if explicit is not None:
                raise UsageError("gateway-check names its work directory only once")
            explicit = rest[0]
        base = resolve_work_dir(explicit)
        if command == "gateway-check":
            config = settings(base)
            output = {"gateway": config["gateway"]}
            if config["gateway"] is None:
                output["provider"] = "native"
            print(json.dumps(output, sort_keys=True))
            return 0  # resolution only: no probe, directory write or subprocess
        if command == "start":
            return start(base, *rest)
        if command == "run":
            return run(base, rest[0])
        if command == "wait":
            return wait(base, rest[0], float(rest[1]) if len(rest) > 1 else 540.0)
        print(json.dumps(result(base, rest[0])))
        return 0
    except GatewayRefused as error:
        print(f"gateway refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (UsageError, ValueError, TypeError, OSError) as error:
        print(f"codex_call.sh: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
