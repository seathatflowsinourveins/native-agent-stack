#!/usr/bin/env python3
"""Local integration check (thin), not an upstream test: pair two actionlint JSON reports.

Reads the output of actionlint's documented JSON template, -format '{{json .}}' (docs/usage.md in
rhysd/actionlint v1.7.12 and kjanat/actionlint v1.17.0), for the same files from two binaries.
Diagnostics are paired on (filepath, line, column, kind) first and their messages compared second,
so a reworded finding at the same position is reported once as "reworded" instead of once as
removed and once as new. A second pass pairs what is left on (filepath, line, kind, message) with a
different column as "relocated" (kjanat/actionlint v1.11.0 reports ShellCheck findings at their
exact YAML source location instead of the run: key; CHANGELOG.md at v1.17.0). Prints one JSON
object; the classification of each unpaired, reworded or relocated diagnostic (new true positive,
new false positive, default-config change, removed) is a reviewed judgment recorded in the receipt,
not computed here.

Usage: compare.py OLD.json NEW.json
"""
import json
import sys
from collections import defaultdict


def load(path):
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    by_key = defaultdict(list)
    for item in report:
        by_key[(item["filepath"], item["line"], item["column"], item["kind"])].append(item["message"])
    return by_key


def main(old_path, new_path):
    old, new = load(old_path), load(new_path)
    result = {"identical": [], "reworded": [], "relocated": [], "only_old": [], "only_new": []}
    for key in sorted(set(old) | set(new)):
        old_messages, new_messages = sorted(old.get(key, [])), sorted(new.get(key, []))
        same = [m for m in old_messages if m in new_messages]
        rest_old = [m for m in old_messages if m not in same]
        rest_new = [m for m in new_messages if m not in same]
        entry = {"filepath": key[0], "line": key[1], "column": key[2], "kind": key[3]}
        result["identical"] += [{**entry, "message": m} for m in same]
        while rest_old and rest_new:
            result["reworded"].append({**entry, "old_message": rest_old.pop(0), "new_message": rest_new.pop(0)})
        result["only_old"] += [{**entry, "message": m} for m in rest_old]
        result["only_new"] += [{**entry, "message": m} for m in rest_new]
    for item in list(result["only_old"]):
        match = next((other for other in result["only_new"]
                      if all(other[field] == item[field] for field in ("filepath", "line", "kind", "message"))), None)
        if match is not None:
            result["only_old"].remove(item)
            result["only_new"].remove(match)
            moved = {field: value for field, value in item.items() if field != "column"}
            result["relocated"].append({**moved, "old_column": item["column"], "new_column": match["column"]})
    result["counts"] = {name: len(items) for name, items in result.items()}
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == "__main__":
    main(*sys.argv[1:3])
