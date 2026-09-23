#!/usr/bin/env python3
"""Stronger re-check of the paper-arm rounds from committed raw files only (fix round after
the Codex review of 58b2ba0..49278fa). Usage: recheck_paper_arm.py <round> [<round> ...]
Prints PASS/FAIL lines and a JSON summary; runs no workload and contacts nothing.
"""
import collections, datetime, glob, json, re, sys

RAW = "evidence/artifacts/gap-wave2-20260923/us-equities__observability-hosting/raw"
summary = {}


def res(path):
    try:
        return json.load(open(path)).get("data", {}).get("result", [])
    except Exception:
        return []


for n in sys.argv[1:]:
    D = f"{RAW}/paper-arm-round{n}"
    out = []
    ok = lambda c, *m: out.append(" ".join(["PASS" if c else "FAIL", *map(str, m)]))
    steps = open(f"{D}/logs/steps.txt").read().splitlines()
    mark = next(l.split("=", 1)[1] for l in steps if l.startswith("MARK="))
    steplog = [l for p in sorted(glob.glob(f"{D}/dagu-step-logs/*")) for l in open(p, errors="replace").read().splitlines()]
    marklines = [l for l in steplog if mark in l]

    # (a) exact, operation-specific restic/diff exit lines (timestamp prefix, then the exact record)
    for rec in ("backup exit=0", "check exit=0", "restore exit=0", "hot check exit=0", "hot restore exit=0"):
        ok(any(re.fullmatch(r"\[[^\]]+\] " + re.escape(rec), l) for l in steps), "exact line:", rec)
    for rec in ("diff -rq work exit=0 lines=0", "diff -rq dagu exit=0 lines=0"):
        ok(any(re.fullmatch(r"\[[^\]]+\] " + re.escape(rec), l) for l in steps), "exact line:", rec)

    # (b) Loki bodies: multiset equals step-log MARK lines; (ts, body) pairs retained
    pairs = lambda t: [(v[0], v[1]) for s in res(f"{D}/logs/loki-{t}.json") for v in s["values"]]
    want = collections.Counter(marklines)
    pre = set(pairs("before-kill"))
    for t in ("before-kill", "after-restart", "restored"):
        got = collections.Counter(b for _, b in pairs(t))
        ok(bool(want) and got == want, "loki body multiset equals step-log MARK lines", t, sum(got.values()), sum(want.values()))
        if t != "before-kill":
            ok(bool(pre) and pre <= set(pairs(t)), "loki pre-kill (ts, body) pairs all present", t)

    # (c) span-metric values per span name equal across stages
    sv = lambda t: {x["metric"].get("span_name"): x["value"][1] for x in res(f"{D}/logs/prom-spans-{t}.json")}
    base = sv("before-kill")
    ok(len(base) == 3, "span series before kill", base)
    for t in ("after-restart", "restored"):
        ok(sv(t) == base, "span values equal to pre-kill", t, sv(t))

    # (d) hot snapshot overlaps the workload and holds a consistent mid-run journal
    ev = [json.loads(l) for l in steplog if l.startswith('{"mark"')]
    start = next((e["at"] for e in ev if e["kind"] == "paper_sim_start"), None)
    end = next((e["at"] for e in ev if e["kind"] == "paper_sim_end"), None)
    hot = open(f"{D}/logs/restic-hot.log").read()
    m = re.search(r"restoring snapshot \w+ of \[[^\]]*\] at (\S+ \S+) (-\d{4})", hot)
    snap = None
    if m:
        ts, off = m.group(1), m.group(2)
        snap = datetime.datetime.strptime(ts[:26] + off, "%Y-%m-%d %H:%M:%S.%f%z").timestamp()
    ok(None not in (snap, start, end) and start < snap < end, "hot snapshot time inside workload window", start, snap, end)
    j = json.load(open(f"{D}/logs/journal-check.json"))
    ok(j["hot"].get("integrity") == "ok", "hot journal integrity", j["hot"])
    out.append(f"INFO hot vs cold journal counts: hot={j['hot'].get('counts')} cold={j['cold'].get('counts')}")
    summary[n] = out

for n, out in summary.items():
    print(f"== round {n}")
    print("\n".join(out))
print(json.dumps({n: {"pass": sum(l.startswith("PASS") for l in o), "fail": sum(l.startswith("FAIL") for l in o)} for n, o in summary.items()}))
