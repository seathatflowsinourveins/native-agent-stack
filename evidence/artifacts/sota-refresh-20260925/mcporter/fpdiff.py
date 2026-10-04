#!/usr/bin/env python3
"""Diff the read-only production fingerprints taken before and after the arms."""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
labels = ["before", "after-y-attempt1", "after-y", "after-x", "final"]
fps = {l: json.loads((HERE / "fp" / f"{l}.json").read_text()) for l in labels}


def flat(d, p=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flat(v, f"{p}/{k}"))
    else:
        out[p] = json.dumps(d, sort_keys=True)
    return out


fb = flat(fps["before"])
lines = []
for l in labels[1:]:
    fl = flat(fps[l])
    ch = [k for k in sorted(set(fb) | set(fl)) if fb.get(k) != fl.get(k) and k not in ("/at_utc", "/label")]
    lines.append(f"== before ({fps['before']['at_utc']}) -> {l} ({fps[l]['at_utc']}): {len(ch)} changed keys")
    for k in ch:
        lines.append(f"    {k}: {(fb.get(k) or 'absent')[:90]} -> {(fl.get(k) or 'absent')[:90]}")
text = "\n".join(lines)
(HERE / "fp-diff.txt").write_text(text + "\n")
print(text)
