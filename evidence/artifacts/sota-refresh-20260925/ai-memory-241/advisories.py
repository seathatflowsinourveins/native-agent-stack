#!/usr/bin/env python3
"""Query GitHub's reviewed advisory DB for every registry crate in a Cargo.lock."""
import json, subprocess, sys, tomllib, time
lock = tomllib.load(open(sys.argv[1], 'rb'))
pkgs = sorted({(p['name'], p['version']) for p in lock['package'] if str(p.get('source', '')).startswith('registry+')})
hits = {}
batch = []
def flush(batch):
    affects = ",".join(f"{n}@{v}" for n, v in batch)
    r = subprocess.run(["gh", "api", "-X", "GET", "/advisories", "-f", "ecosystem=rust", "-f", f"affects={affects}",
                        "-f", "per_page=100"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh api failed: {r.stderr[:300]}")
    for adv in json.loads(r.stdout):
        hits[adv['ghsa_id']] = {"severity": adv.get('severity'), "published_at": adv.get('published_at'),
                                "withdrawn_at": adv.get('withdrawn_at'),
                                "packages": sorted({v['package']['name'] for v in adv.get('vulnerabilities', [])})}
for p in pkgs:
    batch.append(p)
    if len(batch) == 40:
        flush(batch); batch = []
if batch:
    flush(batch)
print(json.dumps({"lockfile": sys.argv[1].split('/')[-1], "registry_crates": len(pkgs), "advisory_hits": hits,
                  "checked_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}))
