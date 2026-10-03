#!/usr/bin/env python3
"""Runs skill_md.mjs (the reader) over a corpus-shaped JSON file in one batch and compares its verdicts with one or
more oracle outputs of cli_oracle.mjs.

  compare.py <skill_md.mjs> <install dir> <corpus.json> <reader-out.json> <label>=<oracle.json> ...

Prints, per oracle: the (reader, oracle) verdict pairs with counts; for pairs that agree, how many recorded names,
descriptions and display names (take) or warnings (skip) differ; and every disagreement by key. A reader "error" is its
refusal to give a verdict: the one refusal skill_md.mjs is built to give (a line break other than LF or CRLF in the
frontmatter, reason "a line break to libyaml") is listed and not counted against it; any other error is. Exit 0 when no
take/skip verdict of the reader contradicts an oracle, no other error occurred and every agreeing verdict carries the
same fields, else 1. The reader's own answer is kept in reader-out.json."""

import collections
import json
import subprocess
import sys

LINE_BREAK_REFUSAL = "a line break to libyaml"
script, install, corpus_path, reader_out = sys.argv[1:5]
oracles = [arg.split("=", 1) for arg in sys.argv[5:]]
corpus = json.load(open(corpus_path, encoding="utf-8"))


def repo_path(key: str) -> str:
    """The SKILL.md's path in its repository: after the first ':' of a corpus key; an edge case stands at
    skills/find-bugs/SKILL.md (cli_oracle.mjs names its folder so too)."""
    return "skills/find-bugs/SKILL.md" if key.startswith("edge:") else key.split(":", 1)[1]


items = [{"id": key, "path": repo_path(key), "base64": entry["base64"]} for key, entry in sorted(corpus.items())
         if "base64" in entry]
done = subprocess.run(["node", script, "--install", install], input=json.dumps({"items": items}), capture_output=True,
                      text=True, check=False)
print(f"reader: exit {done.returncode}, {len(items)} items")
try:
    response = json.loads(done.stdout)
except ValueError:
    print("reader: no JSON answer;", done.stderr.strip()[:300])
    sys.exit(1)
json.dump(response, open(reader_out, "w", encoding="utf-8"), indent=1, sort_keys=True)
print("reader:", json.dumps(response["reader"], sort_keys=True))
if done.returncode != 0:
    sys.exit(1)
reader = {result["id"]: result for result in response["results"]}
bad = 0
for label, path in oracles:
    oracle = json.load(open(path, encoding="utf-8"))
    results = oracle["results"]
    pairs, fields, disagreements = collections.Counter(), collections.Counter(), []
    for key in sorted(results):
        mine, theirs = reader[key], results[key]
        pairs[(mine["verdict"], theirs["verdict"])] += 1
        if mine["verdict"] != theirs["verdict"]:
            refusal = mine["verdict"] == "error" and LINE_BREAK_REFUSAL in (mine["reason"] or "")
            disagreements.append({"key": key, "reader": mine["verdict"], "oracle": theirs["verdict"],
                                  "counted": not refusal, "reader_reason": (mine["reason"] or "")[:160],
                                  "oracle_reason": (theirs["reason"] or "")[:160]})
            bad += 0 if refusal else 1
            continue
        compared = (("name", "description") + (("display_name",) if repo_path(key) != "SKILL.md" else ())
                    if mine["verdict"] == "take" else ("reason",))  # a root SKILL.md's display name is the CLI's clone
        for field in compared:
            if mine[field] != theirs[field]:
                fields[field] += 1
                bad += 1
                disagreements.append({"key": key, "field": field, "reader": mine[field], "oracle": theirs[field]})
    print(f"== {label}: oracle yaml {oracle['yaml_version']}, extract sha256 {oracle['extract_sha256']}, "
          f"{len(results)} compared")
    print("   (reader, oracle):", ", ".join(f"{a}/{b} {n}" for (a, b), n in sorted(pairs.items())))
    print("   field differences on agreeing verdicts:", dict(fields) or 0)
    for item in disagreements:
        print("   DIFF", json.dumps(item, ensure_ascii=True))
print("agreement:", "yes" if not bad else f"no ({bad} counted differences)")
sys.exit(1 if bad else 0)
