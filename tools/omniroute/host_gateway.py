#!/usr/bin/env python3
"""Print, check or atomically write this host's gateway record.

The shared block is the approved host-gateway v2 contract, unchanged. The
adapter implements gateway-default-resolution revision 3.1, A4, section 5.
This fills the machine-scoped configuration gap identified by the upstream
research; a TCP probe or anonymous OmniRoute health response is not identity.

Native API sources (read 2026-10-07):
https://docs.python.org/3.11/library/os.html#os.replace
https://docs.python.org/3.11/library/tempfile.html#tempfile.mkstemp
https://docs.python.org/3.11/library/subprocess.html#subprocess.run
https://github.com/systemd/systemd/blob/main/man/machine-id.xml
"""

import argparse
import datetime
import hashlib
import ipaddress
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import tempfile
import urllib.parse

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

GATEWAY_FLAGS = {"--base-url": lambda value: value}
GATEWAY_VARIABLES = ()  # print's repeatable --variable supplies this adapter's tuple
GATEWAY_OVERRIDES = ()
GATEWAY_HOMES = ()
WINDOWS_NETSTAT = pathlib.Path("/mnt/c/Windows/System32/netstat.exe")


class GatewayNotVerifiable(RuntimeError):
    """The required native observation is unavailable; it cannot prove absence."""


def record_path():
    """Use the same passwd-home location as the shared reader."""
    try:
        import pwd
        home = pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError):
        raise GatewayRefused("this context has no passwd home for a host gateway record") from None
    return home / HOST_GATEWAY_RECORD


def _native(run, argv):
    try:
        reply = run(argv, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        raise GatewayNotVerifiable(f"{pathlib.Path(argv[0]).name} could not be read from this context") from None
    if reply.returncode != 0:
        raise GatewayNotVerifiable(f"{pathlib.Path(argv[0]).name} exited {reply.returncode}")
    if not isinstance(reply.stdout, str):
        raise GatewayNotVerifiable(f"{pathlib.Path(argv[0]).name} returned no readable table")
    return reply.stdout


def _socket_address(value):
    try:
        address, number = value.rsplit(":", 1)
        port = int(number)
        if not 0 < port <= 65535:
            raise ValueError
        return address.strip("[]"), port
    except (ValueError, AttributeError):
        raise GatewayNotVerifiable("listener output has an unparseable local address") from None


def _ss_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        columns = line.split()
        if len(columns) < 5 or columns[0] != "LISTEN":
            raise GatewayNotVerifiable("ss output is not a header-free LISTEN table")
        address, port = _socket_address(columns[3])
        pids = [int(number) for number in re.findall(r"\bpid=(\d+)", line)]
        rows.append({"address": address, "port": port, "pids": pids})
    return rows


def native_listeners(port, platform, run):
    if platform.startswith("linux"):
        rows = _ss_rows(_native(run, ["ss", "-4ltnpH", f"sport = :{port}"]))
        return [(row["address"], pid) for row in rows if row["port"] == port
                for pid in (row["pids"] or [None])]
    if platform == "darwin":
        text = _native(run, ["lsof", "-nP", f"-iTCP@127.0.0.1:{port}", "-sTCP:LISTEN", "-Fpc"])
        pids = []
        for line in text.splitlines():
            if line.startswith("p"):
                try:
                    pids.append(int(line[1:]))
                except ValueError:
                    raise GatewayNotVerifiable("lsof returned an unparseable process id") from None
        return [("127.0.0.1", pid) for pid in pids]
    raise GatewayRefused("this platform has no supported gateway ownership check")


def native_unit_of(pid):
    try:
        lines = pathlib.Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8").splitlines()
        groups = [line.split(":", 2)[2] for line in lines if line.startswith("0::")]
        if len(groups) != 1:
            raise ValueError
        return groups[0].rstrip("/").rsplit("/", 1)[-1]
    except (OSError, IndexError, ValueError):
        raise GatewayNotVerifiable("the listener's cgroup is not visible from this context") from None


def _owner(endpoint, unit, platform, listeners, unit_of, run):
    if platform == "darwin":
        try:
            pinned = _native(run, ["scutil", "--get", "HostName"]).strip()
        except GatewayNotVerifiable:
            pinned = ""
        if not pinned or pinned != socket.gethostname():
            raise GatewayRefused("pin it first: sudo scutil --set HostName <name>")
    port = urllib.parse.urlsplit(endpoint).port
    try:
        observed = list(listeners(port) if listeners is not None else native_listeners(port, platform, run))
    except OSError:
        raise GatewayNotVerifiable("the local listener table is not visible from this context") from None
    if len(observed) != 1:
        raise GatewayRefused("ownership needs exactly one local IPv4 listener")
    address, pid = observed[0]
    if address not in ("127.0.0.1", "0.0.0.0"):
        raise GatewayRefused("ownership needs exactly one local IPv4 listener")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise GatewayRefused("the local listener shows no process in this distribution")
    if unit:
        try:
            own_unit = (unit_of or native_unit_of)(pid)
        except OSError:
            raise GatewayNotVerifiable("the listener's cgroup is not visible from this context") from None
        if own_unit != unit:
            raise GatewayRefused("the listener is not in the named unit's cgroup")
    return {"address": address, "pid": pid, "unit": unit}


def write_record(args, platform, listeners, unit_of, run):
    if os.getuid() == 0:
        raise GatewayRefused("run the host gateway writer as its owning user, never uid 0")
    machine = installation_id()  # required on every platform; Darwin awaits D8
    if args.unit is not None and not args.unit.strip():
        raise GatewayRefused("a unit name must not be blank")
    if args.from_topology is not None:
        try:
            topology = json.loads(pathlib.Path(args.from_topology).read_text(encoding="utf-8"))
            endpoint = gateway_endpoint(topology["gateway"]["endpoint"])
        except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
            raise GatewayRefused("the topology does not contain a readable gateway.endpoint in the contract") from None
    else:
        endpoint = gateway_endpoint(f"http://127.0.0.1:{args.port}/v1")
    owner = _owner(endpoint, args.unit, platform, listeners, unit_of, run)
    record = {"schema": HOST_GATEWAY_SCHEMA, "host": socket.gethostname(),
              "machine_id_sha256": machine, "endpoint": endpoint, "unit": args.unit}
    if args.unit is None:
        name = _native(run, ["ps", "-p", str(owner["pid"]), "-o", "comm="]).strip()
        if not name:
            raise GatewayNotVerifiable("the listener's process name is not visible")
        record["process"] = name
    path = record_path()
    try:
        if path.exists() and not args.replace:
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
                unchanged = previous["host"] == record["host"] and previous["endpoint"] == endpoint
            except (ValueError, KeyError, TypeError):
                unchanged = False
            if not unchanged:
                raise GatewayRefused("an existing host or endpoint differs; use --replace to change it")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".gateway-", suffix=".json", dir=path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fchmod(stream.fileno(), 0o600)
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                pathlib.Path(temporary).unlink(missing_ok=True)
    except OSError as error:
        raise GatewayRefused(f"the host gateway record could not be written ({type(error).__name__}); old record kept") from None
    return record


def _windows_rows(run):
    rows = []
    for protocol in ("tcp", "tcpv6"):
        text = _native(run, [str(WINDOWS_NETSTAT), "-ano", "-p", protocol])
        table = []
        for line in text.splitlines():
            columns = line.split()
            if not columns or line.strip() == "Active Connections" or columns[0] == "Proto":
                continue
            if (len(columns) != 5 or columns[0] != "TCP"
                    or columns[3] not in {"LISTENING", "ESTABLISHED", "TIME_WAIT", "CLOSE_WAIT", "SYN_SENT",
                                          "SYN_RECEIVED", "FIN_WAIT_1", "FIN_WAIT_2", "LAST_ACK", "CLOSING", "CLOSED",
                                          "DELETE_TCB"}):
                raise GatewayNotVerifiable(f"netstat {protocol} has an unparseable row or state")
            if columns[3] == "LISTENING":
                address, port = _socket_address(columns[1])
                try:
                    pid = int(columns[4])
                    if pid <= 0:
                        raise ValueError
                except ValueError:
                    raise GatewayNotVerifiable(f"netstat {protocol} has an unparseable process id") from None
                table.append({"address": address, "port": port, "pid": pid, "table": protocol})
        if not table:
            raise GatewayNotVerifiable(f"netstat {protocol} read no parseable LISTENING row; Windows absence is not verifiable")
        rows.extend(table)
    return rows


def check_record(args, platform, listeners, unit_of, run):
    endpoint = recorded_gateway()
    try:
        record = json.loads(record_path().read_text(encoding="utf-8"))
        unit = record.get("unit")
        if unit is not None and (not isinstance(unit, str) or not unit.strip()):
            raise ValueError
        if gateway_endpoint(record["endpoint"]) != endpoint:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise GatewayRefused("the host gateway record changed or has a malformed unit; run check again") from None
    if platform.startswith("linux") and unit:
        text = _native(run, ["systemctl", "--user", "show", "-p", "MainPID", "--value", unit]).strip()
        try:
            pid = int(text)
        except ValueError:
            pid = 0
        if pid <= 0 or not pathlib.Path(f"/proc/{pid}").exists():
            raise GatewayNotVerifiable("not verifiable from this context")
    owner = _owner(endpoint, unit, platform, listeners, unit_of, run)
    result = {"ok": True, "endpoint": endpoint, "owner": owner,
              "checked_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if args.codex_profile is not None:
        tomllib = _toml()
        try:
            profile = tomllib.loads(pathlib.Path(args.codex_profile).read_text(encoding="utf-8"))
            result["profile_match"] = gateway_endpoint(profile["model_providers"]["omniroute"]["base_url"]) == endpoint
        except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
            result["profile_match"] = False
        result["ok"] = result["ok"] and result["profile_match"]
    legacy_ports = list(dict.fromkeys(args.legacy_port))
    for port in legacy_ports:
        if not 0 < port <= 65535:
            raise GatewayRefused("a legacy port must be between 1 and 65535")
    windows_exists = WINDOWS_NETSTAT.exists()
    windows = _windows_rows(run) if windows_exists else []
    if any(row["port"] == urllib.parse.urlsplit(endpoint).port for row in windows):
        result["ok"] = False
    if legacy_ports:
        linux = _ss_rows(_native(run, ["ss", "-ltnH"])) if platform.startswith("linux") else []
        result["legacy_ports"] = []
        for port in legacy_ports:
            local = [row for row in linux if row["port"] == port]
            remote = [row for row in windows if row["port"] == port]
            result["legacy_ports"].append({"port": port, "linux": local, "windows": remote,
                                           "windows_read": windows_exists})
            if local or remote:
                result["ok"] = False
    return result


def main(argv=None, *, platform=sys.platform, listeners=None, unit_of=None, run=subprocess.run):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("print", allow_abbrev=False)
    show.add_argument("--root", action="store_true")
    show.add_argument("--base-url")
    show.add_argument(HOST_GATEWAY_OVERRIDE, dest="reason")
    show.add_argument("--variable", action="append", default=[])
    check = commands.add_parser("check", allow_abbrev=False)
    check.add_argument("--codex-profile", type=pathlib.Path)
    check.add_argument("--legacy-port", action="append", type=int, default=[])
    write = commands.add_parser("write", allow_abbrev=False)
    location = write.add_mutually_exclusive_group(required=True)
    location.add_argument("--from-topology", type=pathlib.Path)
    location.add_argument("--port", type=int)
    write.add_argument("--unit")
    write.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "print":
            gateway = resolve_gateway(args.base_url, args.reason, tuple(args.variable))
            print(gateway["endpoint"][:-3] if args.root else gateway["endpoint"])
            return 0
        if args.command == "write":
            record = write_record(args, platform, listeners, unit_of, run)
            print(json.dumps(record, sort_keys=True))
            return 0
        result = check_record(args, platform, listeners, unit_of, run)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 2
    except GatewayNotVerifiable as error:
        if args.command == "check":
            result = {"ok": False, "owner": "not verifiable from this context",
                      "windows_read": False, "error": str(error),
                      "checked_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            if args.legacy_port:
                result["legacy_ports"] = [{"port": port, "windows_read": False, "linux": None, "windows": None}
                                          for port in dict.fromkeys(args.legacy_port)]
            print(json.dumps(result, sort_keys=True))
            return 3
        print(f"gateway refused: {error}", file=sys.stderr)
        return 2
    except GatewayRefused as error:
        print(f"gateway refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
