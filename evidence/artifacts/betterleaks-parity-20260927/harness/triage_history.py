#!/usr/bin/env python3
"""Value-blind triage of every git-mode betterleaks finding (local integration helper). Same method as
triage.py, but each line is read from its historical commit and relocated by byte offset (betterleaks
reports byte columns). Prints rule, file, line, the key text with long tokens masked and a value
descriptor (length, classes, shape markers); never a value, commit or fingerprint. Findings in the
generated explorer HTML (6-13 MB single lines) are aggregated by key text and value class."""
import collections
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

report, repo, rules_toml = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rules = {r["id"]: r for r in tomllib.loads(rules_toml.read_text())["rules"]}
LONG = re.compile(r"[A-Za-z0-9+/=_.-]{12,}")


def describe(v):
    shape = re.sub(r"[a-z]", "a", re.sub(r"[A-Z]", "A", re.sub(r"[0-9]", "9", v)))
    flags = [f for f, p in (("shell-expansion", r"\$\{?[A-Za-z_]|\$\("), ("printf", r"%[sd]"),
                            ("code-expr", r"^\s*[+.]|[+]\s*$|\w\(.*\)")) if re.search(p, v)]
    words = [w for w in ("local", "test", "secret", "passw", "example", "dummy", "fake", "changeme", "placeholder",
                         "replace", "your") if w in v.lower()]
    return f"len={len(v)} shape={shape if len(shape) <= 40 else shape[:40] + '...'} flags={flags} words={words}"


rows, explorer = [], collections.Counter()
for f in json.loads(report.read_text()):
    raw = subprocess.run(["git", "show", f"{f['Commit']}:{f['File']}"], cwd=repo, capture_output=True).stdout
    line = raw.split(b"\n")[f["StartLine"] - 1]
    rx = re.compile(rules[f["RuleID"]]["regex"])
    seg = line[max(0, f["StartColumn"] - 9): f["EndColumn"] + 8].decode("utf-8", "replace")
    m = rx.search(seg)
    if not m:
        rows.append((f["RuleID"], f["File"], f["StartLine"], "relocation-failed", ""))
        continue
    if f["RuleID"] == "generic-credential-uri":
        g = m.groupdict()
        host = g.get("host") or ""
        hc = ("loopback" if re.match(r"(localhost|127\.|\[::1\])", host) else
              "example-domain" if re.search(r"example\.(com|org|net)|\.test$|\.invalid$", host) else "other")
        rows.append((f["RuleID"], f["File"], f["StartLine"], f"{g['scheme']}://<user len={len(g.get('username') or '')}>:<pw>@<{hc}>",
                     describe(g["password"])))
        continue
    idx = next(i for i in range(1, rx.groups + 1) if m.group(i) is not None)
    if f["File"] == "docs/ecosystem/index.html":
        v = m.group(idx)
        vc = "hex64" if re.fullmatch(r"[0-9a-f]{64}", v) else "hex40" if re.fullmatch(r"[0-9a-f]{40}", v) else describe(v)
        explorer[(f["RuleID"], LONG.sub(lambda t: f"<tok{len(t.group(0))}>", m.group(0)[: m.start(idx) - m.start()]).strip(), vc)] += 1
        continue
    key = LONG.sub(lambda t: f"<tok{len(t.group(0))}>", m.group(0)[: m.start(idx) - m.start()]).strip()[-40:]
    rows.append((f["RuleID"], f["File"], f["StartLine"], key, describe(m.group(idx))))
for row in sorted(rows, key=lambda r: (r[1], r[2])):
    print(" | ".join(str(x) for x in row))
for (rule, key, vc), n in explorer.items():
    print(f"{rule} | docs/ecosystem/index.html | {n} findings | {key} | {vc}")
