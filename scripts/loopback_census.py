#!/usr/bin/env python3
"""Loopback-only listener census: alert on any TCP or UDP listener that does not bind loopback.

Rule (docs/decisions/2026-10-17-loopback-listener-census.md):
- Dashboards and local services run without a password through each upstream's own no-auth mode.
- Every listener therefore binds loopback only: 127.0.0.0/8, ::1, or ::ffff:127.0.0.0/104.
- A periodic census alerts on any other listener.
- WSL here runs in mirrored networking, where a wildcard or interface bind reaches the LAN.

It reads `ss -H -l -t -u -n -p` (iproute2 ss(8)):
- -l listening sockets, -t TCP, -u UDP;
- -n numeric addresses, -p the owning process, -H no header line.

Output: one JSON line on stdout. Exit 1 when any listener breaks the rule, 0 otherwise, so a systemd OnFailure= handler
fires on a breach.

The one allowed exception is WSL's DNS tunnel at 10.255.255.254:53, the nameserver that resolv.conf names on a mirrored
WSL host.

Process names come from ss's users field when ss can see them (the user's own processes). argv is never read.

Usage: loopback_census.py [--ss-output FILE]
--ss-output reads a saved `ss -H -ltunp` output instead of running ss; the tests use it.
"""
import argparse
import datetime as dt
import ipaddress
import json
import re
import subprocess
import sys

ALLOWED = {"10.255.255.254:53"}
PROCESS = re.compile(r'\(\("([^"]+)",pid=(\d+)')


def is_loopback(address):
    """True for a local address in 127.0.0.0/8, ::1 or ::ffff:127.0.0.0/104, with or without a %scope suffix."""
    host = address.rsplit(":", 1)[0].strip("[]").split("%", 1)[0]
    if host == "*":
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or bool(mapped and mapped.is_loopback)


def census(lines):
    total, violations = 0, []
    for line in lines:
        fields = line.split()
        if len(fields) < 5:
            continue
        total += 1
        proto, address = fields[0], fields[4]
        if address in ALLOWED or is_loopback(address):
            continue
        match = PROCESS.search(line)
        process = f"{match.group(1)} pid={match.group(2)}" if match else "unknown"
        entry = {"proto": proto, "address": address, "process": process}
        if entry not in violations:
            violations.append(entry)
    return total, violations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ss-output", help="read a saved `ss -H -ltunp` output instead of running ss")
    args = parser.parse_args(argv)
    if args.ss_output:
        with open(args.ss_output, encoding="utf-8") as stream:
            text = stream.read()
    else:
        text = subprocess.run(["ss", "-H", "-l", "-t", "-u", "-n", "-p"], capture_output=True, text=True,
                              check=True).stdout
    total, violations = census(text.splitlines())
    at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(json.dumps({"check": "loopback-census", "at": at, "listeners": total, "violations": violations}))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
