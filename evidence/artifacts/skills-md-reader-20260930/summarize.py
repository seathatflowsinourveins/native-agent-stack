#!/usr/bin/env python3
"""Writes counts.json, the compact result of one run.sh run: tool and package versions, the corpus, every comparison
recomputed from the retained outputs, the edge cases one by one, the yaml version delta, every step's exit status, the
negative controls, and the sha256 and size of each retained raw output (kept outside the repository: the corpus text,
the CLI's raw output and the per-file oracle answers). Digests sit in {"sha256": ...} objects of their own.

  summarize.py <scratch> <checkout commit> <out counts.json>
"""

import collections
import hashlib
import json
import re
import sys
from pathlib import Path

scratch, commit, out_path = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
out = scratch / "out"
LINE_BREAK_REFUSAL = "a line break to libyaml"


def text(name):
    return (out / name).read_text(encoding="utf-8")


def load(name):
    return json.loads(text(name))


def json_stream(raw):
    decoder, position, items = json.JSONDecoder(), 0, []
    while position < len(raw):
        while position < len(raw) and raw[position].isspace():
            position += 1
        if position >= len(raw):
            break
        item, position = decoder.raw_decode(raw, position)
        items.append(item)
    return items


def digest(path):
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


steps = []
for line in (scratch / "log.txt").read_text(encoding="utf-8").splitlines():
    name, start, end, status, command = line.split("\t", 4)
    steps.append({"step": name, "start_utc": start, "end_utc": end, "exit": int(status.split()[1]), "command": command})
exits = {step["step"]: step["exit"] for step in steps}

versions = text("versions.stdout").split()
packs = {item["id"]: item for item in json.loads(text("pack.stdout"))}
registry = json_stream(text("registry.stdout"))
corpus_lines = text("corpus.stdout").splitlines()
sources = [{"source": line.split(":")[0], "skill_md": int(line.split(": ")[1].split()[0])}
           for line in corpus_lines if line.endswith(" SKILL.md")]
totals = dict(re.findall(r"(total|regular|fetch_failures) (\d+)", corpus_lines[-2]))
index_sha256 = corpus_lines[-1].split()[1]


def compare(reader_name, oracle_name):
    reader = {item["id"]: item for item in load(reader_name)["results"]}
    oracle = load(oracle_name)
    pairs, fields, refusals, counted = collections.Counter(), collections.Counter(), 0, 0
    for key, theirs in oracle["results"].items():
        mine = reader[key]
        pairs[f"{mine['verdict']}/{theirs['verdict']}"] += 1
        if mine["verdict"] != theirs["verdict"]:
            if mine["verdict"] == "error" and LINE_BREAK_REFUSAL in (mine["reason"] or ""):
                refusals += 1
            else:
                counted += 1
            continue
        path = "skills/find-bugs/SKILL.md" if key.startswith("edge:") else key.split(":", 1)[1]
        compared = (("name", "description") + (("display_name",) if path != "SKILL.md" else ())
                    if mine["verdict"] == "take" else ("reason",))
        for field in compared:
            if mine[field] != theirs[field]:
                fields[field] += 1
    return {"oracle_yaml": oracle["yaml_version"], "compared": len(oracle["results"]),
            "pairs_reader_oracle": dict(sorted(pairs.items())), "line_break_refusals": refusals,
            "contradictions": counted, "field_differences": dict(fields)}


def e2e(name):
    lines = text(f"e2e-compare-{name}.stdout").splitlines()
    found = next(line for line in lines if line.startswith("CLI:"))
    return {"cli": found[len("CLI: "):], "reader": next(line for line in lines if line.startswith("reader:"))[8:],
            "controls": json.loads(next(line for line in lines if line.startswith("controls:"))[10:]),
            "agreement": lines[-1] == "agreement: yes", "exit": exits[f"e2e-compare-{name}"],
            "cli_exit": exits[f"e2e-{name}"]}


result = {
    "schema_version": 1,
    "checkout_commit": commit,
    "run_start_utc": steps[0]["start_utc"], "run_end_utc": steps[-1]["end_utc"],
    "tools": {"node": versions[0], "npm": versions[1], "git": versions[4], "python": versions[6]},
    "packages": {
        "skills@1.7.0": {"integrity": packs["skills@1.7.0"]["integrity"], "shasum": packs["skills@1.7.0"]["shasum"],
                         "dependencies": registry[0]["dependencies"], "git_head": registry[0]["gitHead"],
                         "dist_cli_mjs": {"sha256": load("oracle-cli-corpus.json")["cli_mjs_sha256"]},
                         "oracle_extract": {"sha256": load("oracle-cli-corpus.json")["extract_sha256"]},
                         "yaml_its_install_resolved": text("cli-yaml-version.stdout").strip()},
        "yaml@2.9.0": {"integrity": packs["yaml@2.9.0"]["integrity"], "git_head": registry[2]["gitHead"]},
        "yaml@2.9.1": {"integrity": packs["yaml@2.9.1"]["integrity"], "git_head": registry[3]["gitHead"]},
        "yaml_dist_tags": registry[1],
    },
    "reader": {key: value for key, value in load("reader-corpus.json")["reader"].items() if key != "pin_sha256"}
    | {"pin": {"sha256": load("reader-corpus.json")["reader"]["pin_sha256"]}},
    "corpus": {"sources": sources, "total": int(totals["total"]), "regular_files": int(totals["regular"]),
               "fetch_failures": int(totals["fetch_failures"]), "index": {"sha256": index_sha256},
               "skipped_by_the_cli": [{"key": key, "warning": value["reason"]} for key, value in
                                      sorted(load("oracle-cli-corpus.json")["results"].items())
                                      if value["verdict"] == "skip"]},
    "comparisons": {
        name: {"reader_vs_cli_parseSkillMd_with_its_installed_yaml": compare(f"reader-{name}.json", f"oracle-cli-{name}.json"),
               "reader_vs_cli_parseSkillMd_with_yaml_2.9.0": compare(f"reader-{name}.json", f"oracle-290-{name}.json"),
               "reader_vs_skills_add_list_end_to_end": e2e(name),
               "compare_exit": exits[f"compare-{name}"]}
        for name in ("corpus", "edge")},
    "edge_cases": {key[len("edge:"):]: {"reader": mine["verdict"], "cli": load("oracle-cli-edge.json")["results"][key]["verdict"]}
                   for key, mine in sorted((item["id"], item) for item in load("reader-edge.json")["results"])},
    "yaml_2.9.0_vs_2.9.1": {"cli_parseSkillMd_results": {
                                line.split()[0]: {"compared": int(line.split()[1]), "differing": int(line.split()[-1])}
                                for line in text("oracle-versions.stdout").splitlines()},
                            "random_multi_line_scalars": json.loads(text("yaml-random.stdout")),
                            "random_exit": exits["yaml-random"]},
    "negative_controls": {
        "control-sanitize": {"expect": "exit 1 (a reader without stripTerminalEscapes in sanitizeMetadata)",
                             "exit": exits["control-sanitize"]},
        "control-typeof": {"expect": "exit 1 (a reader without parseSkillMd's string check)",
                           "exit": exits["control-typeof"]},
        "control-flip": {"expect": "exit 1 (one corpus skip flipped to take before the end-to-end comparison)",
                         "exit": exits["control-flip"]},
        "control-tampered": {"expect": "exit 3 and hash_mismatch (one byte appended to the installed composer.js)",
                             "exit": exits["control-tampered"], "answer": json.loads(text("control-tampered.stdout"))},
        "mutants_applied": text("control-mutants.stdout").strip(),
    },
    "steps": [{"step": step["step"], "exit": step["exit"]} for step in steps],
    "retained_outside_the_repository": {
        name: digest(path) for name, path in sorted(
            [("corpus.json", scratch / "corpus.json"), ("edge.json", scratch / "edge.json")]
            + [(item.name, item) for item in out.iterdir() if item.is_file()])},
}
out_path.write_text(json.dumps(result, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
print(json.dumps({"steps": len(steps), "nonzero": {k: v for k, v in exits.items() if v}}, sort_keys=True))
