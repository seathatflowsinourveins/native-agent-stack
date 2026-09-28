#!/usr/bin/env python3
"""Value-blind triage of redacted betterleaks findings (local integration helper, scratch only).

Reads the --redact'ed JSON report for rule/file/line/column positions, re-reads that line from the
scanned tree, re-applies the rule's upstream regex (betterleaks v1.8.1 config/betterleaks.toml, commit
5eab4833) to locate the secret group, and prints only derived facts: the matched text with the value
replaced by a descriptor, the value's length and character classes, placeholder/expansion markers, and
the length and character classes of the text left of the match. It never prints a candidate value.
The recorded triage printed that left text with only 12-character tokens masked, which would have shown
a shorter credential or a spaced passphrase verbatim (repair-round review); it now prints the same
descriptor as for the value, as triage_history.py does.
"""
import json
import re
import sys
import tomllib
from pathlib import Path

report, tree, rules_toml = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rules = {r["id"]: r for r in tomllib.loads(rules_toml.read_text())["rules"]}
MARKERS = ("example", "dummy", "fake", "test", "changeme", "xxx", "***", "redact", "placeholder",
           "secret", "passw", "sample", "synthetic", "not-a", "notreal", "hunter2", "local")
LONG = re.compile(r"[A-Za-z0-9+/=_.-]{12,}")


def describe(value: str) -> str:
    classes = [name for name, pat in (("lower", r"[a-z]"), ("upper", r"[A-Z]"), ("digit", r"[0-9]"),
                                      ("punct", r"[^A-Za-z0-9]")) if re.search(pat, value)]
    flags = []
    if re.search(r"\$\{?[A-Za-z_]|\$\(", value):
        flags.append("shell-expansion")
    if re.search(r"\{[A-Za-z_][A-Za-z0-9_.]*\}", value):
        flags.append("format-field")
    if re.fullmatch(r"[0-9a-f]+", value):
        flags.append("hex")
    hits = [m for m in MARKERS if m in value.lower()]
    if hits:
        flags.append("markers=" + ",".join(hits))
    return f"<value len={len(value)} classes={'+'.join(classes)}{' ' + ' '.join(flags) if flags else ''}>"


def mask(text: str) -> str:
    return LONG.sub(lambda m: f"<tok len={len(m.group(0))}>", text)


for f in json.loads(report.read_text()):
    rule = rules[f["RuleID"]]
    line = (tree / f["File"]).read_text(errors="replace").splitlines()[f["StartLine"] - 1]
    start, end = f["StartColumn"] - 1, f["EndColumn"]
    rx = re.compile(rule["regex"])
    found = None
    for m in rx.finditer(line):
        if m.start() <= start + 1 and m.end() >= end - 1:
            found = m
            break
    if found is None:
        print(f"{f['RuleID']} {f['File']}:{f['StartLine']} regex-relocation-failed; left={describe(line[max(0, start - 60):start])}")
        continue
    if f["RuleID"] == "generic-credential-uri":
        g = found.groupdict()
        host = g.get("host") or ""
        host_class = ("loopback" if re.match(r"(localhost|127\.|\[::1\])", host) else
                      "example-domain" if re.search(r"example\.(com|org|net)|\.test$|\.invalid$|\.example$", host) else
                      "placeholder" if re.search(r"[<{$]", host) else "other")
        shown = f"{g['scheme']}://<user len={len(g.get('username') or '')}>:{describe(g['password'])}@<host {host_class}>"
    else:
        idx = next(i for i in range(1, (found.re.groups or 0) + 1) if found.group(i) is not None)
        value = found.group(idx)
        shown = mask(line[found.start():found.start(idx)]) + describe(value) + mask(line[found.end(idx):found.end()])
    print(f"{f['RuleID']} {f['File']}:{f['StartLine']}\n    match: {shown}\n    left : {describe(line[max(0, found.start() - 70):found.start()])}")
