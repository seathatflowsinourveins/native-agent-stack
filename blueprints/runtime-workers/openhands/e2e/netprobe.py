"""Containment probe for the O1 topology (phase-2 plan section 1, P0-P2); stdlib only.

A locally composed integration check, not an upstream test and not a model
run. host.run_probe starts it in the pinned agent-server image with the
recipe's docker_args hardening, with only the venv, /recipe (read-only) and
a dedicated output directory mounted:

- mode gw, on <stem>-gw: P0, the negative control. The vehicle must see the
  gateway (GET /v1/models -> 200 + CLIENT_API) and its management exposure
  (GET /api/settings -> MANAGEMENT).
- mode int, on <stem>-int: P1, only the proxy's three /v1 routes answer and
  every other method or target gets the proxy's own 403 with no route-class
  header; then P2, every TCP connect to a host-side address fails, public
  names and host.docker.internal do not resolve, gw and the server do, and
  no interface other than lo has an IPv6 address.

Raw request targets go through http.client, which sends them verbatim (the
equivalent of curl --path-as-is). Only the status code, the route-class
value class and errno names are kept; response bodies and all other headers
are never read. The probe exits nonzero on the first unexpected result;
host.run_probe re-derives every verdict from the written observations with
the evaluate_* functions below. P3-P5 are live model calls, documented in
README "Isolation probe"; p3_control_call is a skeleton and never runs here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures
import errno
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket


# OmniRoute's response header separating gateway answers from proxy denials
# (plan F18); only these values are kept, anything else is "<other>".
ROUTE_CLASS = "x-omniroute-route-class"
ROUTE_CLASSES = ("CLIENT_API", "MANAGEMENT")
GATEWAY_HOST = "10.0.2.2"  # host loopback as seen from containers (rootlesskit docs/network.md:88)
PROXY_HOST, PROXY_PORT = "gw", 8081
DENIED = (
    *(("GET", target) for target in (
        "/api/settings", "/api/providers", "/api/keys", "/dashboard", "/v1/ws", "/v1/alpha/search",
        "/v1/files", "/V1/models", "/v1/models/", "/v1/responses/x", "/v1/../api/settings",
        "/v1/%2e%2e/api/settings", "/v1/models/../../api/keys", "//api/settings", "/codex/responses",
        "/api/v1/responses", "/v1/models?x=1", "/v1/models?0")),
    *(("POST", target) for target in (
        "/responses", "/chat/completions", "/api/v1/responses", "/api/settings/require-login",
        "/v1/responses?provider=x")),
    ("DELETE", "/v1/models"), ("PUT", "/v1/responses"), ("GET", "/v1/responses"),
)
# (host, port, method, target, expected status or None for any, expected route class or None for absent)
P1_EXPECTED = ((PROXY_HOST, PROXY_PORT, "GET", "/v1/models", 200, "CLIENT_API"),
               *((PROXY_HOST, PROXY_PORT, method, target, 403, None) for method, target in DENIED))
UNRESOLVABLE = ("example.com", "github.com", "host.docker.internal")
# Plan P2 fixed addresses; the host adds its own IPv4 addresses and the
# attempt networks' gateways (host.probe_targets).
FIXED_ADDRESSES = ("10.0.2.2", "10.0.2.3", "172.17.0.1", "10.0.0.1", "10.255.255.254")
EXTRA_PORTS = (53,)
SERVER_NAME = re.compile(r"rw-openhands-[a-z0-9-]{1,64}-(?:control|engines-on)-server")
UPSTREAM_PORTS = (20128, 20129)
HTTP_TIMEOUT = 10.0
CONNECT_TIMEOUT = 2.0
WORKERS = 64
IF_INET6 = "/proc/net/if_inet6"


def p0_expected(upstream_port):
    if upstream_port not in UPSTREAM_PORTS:
        raise ValueError("gateway_port_required")
    return ((GATEWAY_HOST, upstream_port, "GET", "/v1/models", 200, "CLIENT_API"),
            (GATEWAY_HOST, upstream_port, "GET", "/api/settings", None, "MANAGEMENT"))


def dns_expected(server):
    if not isinstance(server, str) or not SERVER_NAME.fullmatch(server):
        raise ValueError("attempt_server_name_required")
    return (*((name, False) for name in UNRESOLVABLE), (PROXY_HOST, True), (server, True))


def error_name(exc):
    if isinstance(exc, socket.gaierror):
        names = {getattr(socket, name): name for name in dir(socket) if name.startswith("EAI_")}
        return names.get(exc.errno, "gaierror")
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, OSError) and exc.errno in errno.errorcode:
        return errno.errorcode[exc.errno]
    return type(exc).__name__


def route_class(value):
    return None if value is None else value if value in ROUTE_CLASSES else "<other>"


def http_probe(host, port, method, target, *, timeout=HTTP_TIMEOUT):
    """One request with a raw target; the body is never read."""
    record = {"host": host, "port": port, "method": method, "target": target,
              "status": None, "route_class": None, "error": None}
    body = b"{}" if method == "POST" else None
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request(method, target, body=body,
                            headers={"Content-Type": "application/json"} if body is not None else {})
        response = connection.getresponse()
        record.update(status=response.status, route_class=route_class(response.getheader(ROUTE_CLASS)))
    except (OSError, http.client.HTTPException) as exc:
        record["error"] = error_name(exc)
    finally:
        connection.close()
    return record


def connect_probe(address, port, *, timeout=CONNECT_TIMEOUT):
    """One TCP connect to an IPv4 literal; no name resolution."""
    record = {"address": address, "port": port, "connected": False, "error": None}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((address, port))
            record["connected"] = True
        except OSError as exc:
            record["error"] = error_name(exc)
    return record


def connect_all(pairs, *, timeout=CONNECT_TIMEOUT, workers=WORKERS):
    """A bounded concurrent batch; results keep the order of pairs."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda pair: connect_probe(*pair, timeout=timeout), pairs))


def resolve(name):
    try:
        found = socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)
        return {"name": name, "resolved": bool(found), "error": None}
    except OSError as exc:
        return {"name": name, "resolved": False, "error": error_name(exc)}


def ipv6_summary(text):
    """Classify /proc/net/if_inet6 rows: address, ifindex, prefix, scope, flags, name."""
    rows = [line.split() for line in text.splitlines() if line.strip()]
    if any(len(row) != 6 or not re.fullmatch(r"[0-9a-f]{32}", row[0]) for row in rows):
        raise ValueError("unexpected_if_inet6_format")
    other = [row for row in rows if row[5] != "lo"]
    return {"available": True, "loopback": len(rows) - len(other), "non_loopback": len(other),
            "link_local": sum(int(row[3], 16) == 0x20 for row in other)}


def read_ipv6():
    try:
        with open(IF_INET6) as stream:
            return ipv6_summary(stream.read())
    except FileNotFoundError:
        return {"available": False, "loopback": 0, "non_loopback": 0, "link_local": 0}


def http_matches(record, expected):
    host, port, method, target, status, route = expected
    return (isinstance(record, dict) and record.get("host") == host and record.get("port") == port
            and record.get("method") == method and record.get("target") == target and record.get("error") is None
            and type(record.get("status")) is int and (status is None or record["status"] == status)
            and record.get("route_class") == route)


def evaluate_http(records, expected):
    records = records if isinstance(records, list) else []
    matched = sum(http_matches(record, item) for record, item in zip(records, expected))
    return {"requests": len(expected), "observed": len(records), "matched": matched,
            "passed": len(records) == len(expected) == matched}


def count(value):
    return value if type(value) is int and value >= 0 else None


def evaluate_p2(p2, addresses, ports, server):
    p2 = p2 if isinstance(p2, dict) else {}
    pairs = [(address, port) for address in addresses for port in ports]
    connects = p2.get("connects") if isinstance(p2.get("connects"), list) else []
    aligned = len(connects) == len(pairs) and all(
        isinstance(record, dict) and (record.get("address"), record.get("port")) == pair
        for record, pair in zip(connects, pairs))
    connected = sum(not isinstance(record, dict) or record.get("connected") is not False for record in connects)
    errors = Counter(record.get("error") if isinstance(record, dict) and isinstance(record.get("error"), str)
                     and re.fullmatch(r"[A-Za-z_]{1,32}", record["error"]) else "<other>"
                     for record in connects if isinstance(record, dict) and record.get("connected") is False)
    expected = dns_expected(server)
    dns = p2.get("dns") if isinstance(p2.get("dns"), list) else []
    dns_matched = sum(isinstance(record, dict) and record.get("name") == name and record.get("resolved") is ok
                      for record, (name, ok) in zip(dns, expected))
    ipv6 = p2.get("ipv6") if isinstance(p2.get("ipv6"), dict) else {}
    non_loopback = count(ipv6.get("non_loopback"))
    return {"connects": len(pairs), "observed": len(connects), "connected": connected,
            "errors": dict(sorted(errors.items())), "dns": len(expected), "dns_matched": dns_matched,
            "ipv6_non_loopback": non_loopback, "ipv6_link_local": count(ipv6.get("link_local")),
            "ipv6_loopback": count(ipv6.get("loopback")),
            "passed": (aligned and connected == 0 and len(dns) == len(expected) == dns_matched
                       and non_loopback == 0)}


def evaluate(gw, internal, upstream_port, addresses, ports, server):
    """The host's verdict, re-derived from both observation files."""
    p0 = evaluate_http(gw.get("p0") if isinstance(gw, dict) else None, p0_expected(upstream_port))
    p1 = evaluate_http(internal.get("p1") if isinstance(internal, dict) else None, P1_EXPECTED)
    p2 = evaluate_p2(internal.get("p2") if isinstance(internal, dict) else None, addresses, ports, server)
    return {"p0": p0, "p1": p1, "p2": p2, "passed": p0["passed"] and p1["passed"] and p2["passed"]}


def p3_control_call(*_args, **_kwargs):
    """Skeleton only; P3 is a live model call and is never run by this recipe yet.

    From a throwaway container on <stem>-int with the recipe's LLM config:
    one SDK call with one tool definition through gw to the control arm, also
    sending a forged X-Correlation-Id, X-Forwarded-For and one x-omniroute-*
    header; then a second call with a query string, which must get the
    proxy's 403 and no call_logs row. The call_logs row must show
    /v1/responses, 200, cx/gpt-6-astra-max, effort max requested and sent
    upstream, and the proxy's fixed run id as the correlation value. The
    streamed tool call must parse and its usage equal the row; record the
    client peer the gateway logged (F10) and the proxy access log lines.
    """
    raise NotImplementedError("p3_is_a_documented_skeleton_not_run")


def run_http(observations, key, expected):
    records = observations.setdefault(key, [])
    for item in expected:
        record = http_probe(*item[:4])
        records.append(record)
        if not http_matches(record, item):
            return 1
    return 0


def run_p2(observations, addresses, ports, server):
    p2 = observations.setdefault("p2", {})
    # One bounded batch, recorded whole and evaluated in order.
    p2["connects"] = connect_all([(address, port) for address in addresses for port in ports])
    if any(record.get("connected") is not False for record in p2["connects"]):
        return 1
    p2["dns"] = []
    for name, resolvable in dns_expected(server):
        record = resolve(name)
        p2["dns"].append(record)
        if record.get("resolved") is not resolvable:
            return 1
    p2["ipv6"] = read_ipv6()
    return 0 if p2["ipv6"].get("non_loopback") == 0 else 1


def parse_addresses(text):
    addresses = [part for part in text.split(",") if part]
    for value in addresses:
        ipaddress.IPv4Address(value)  # ValueError for anything but an IPv4 literal
    if not addresses:
        raise ValueError("probe_addresses_required")
    return addresses


def parse_ports(text):
    ports = [int(part) if re.fullmatch(r"[0-9]{1,5}", part) else -1 for part in text.split(",") if part]
    if not ports or any(not 0 < port < 65536 for port in ports):
        raise ValueError("probe_ports_required")
    return ports


def write_observations(path, observations):
    """0644 whatever the umask, so the host user can read what UID 10001 wrote."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o644)
        stream.write(json.dumps(observations, indent=1) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("mode", choices=("gw", "int"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--upstream-port", type=int, choices=UPSTREAM_PORTS)
    parser.add_argument("--server")
    parser.add_argument("--addresses", default="")
    parser.add_argument("--ports", default="")
    args = parser.parse_args(argv)
    if args.mode == "gw":
        expected = p0_expected(args.upstream_port)
    else:
        dns_expected(args.server)
        addresses, ports = parse_addresses(args.addresses), parse_ports(args.ports)
    observations = {"probe": "netprobe-v1", "mode": args.mode}
    try:
        if args.mode == "gw":
            return run_http(observations, "p0", expected)
        return run_http(observations, "p1", P1_EXPECTED) or run_p2(observations, addresses, ports, args.server)
    finally:
        write_observations(args.out, observations)


if __name__ == "__main__":
    raise SystemExit(main())
