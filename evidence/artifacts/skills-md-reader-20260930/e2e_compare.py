#!/usr/bin/env python3
"""Compares the reader's verdicts with the installed skills CLI run end to end: `skills add <fixture> --list`, where the
fixture holds every corpus SKILL.md as skills/c<NNNN>/SKILL.md (fixture-index.json maps the folder to its corpus key)
plus two planted copies, zz-planted-invalid (no description: the CLI must warn) and zz-planted-valid (a unique name: the
CLI must list it).

  e2e_compare.py <fixture-index.json> <reader-out.json> <cli stdout> <cli stderr>

The CLI prints "Skipped <path> - <reason>" (with a warning sign and an em dash) for every copy parseSkillMd skips, and
lists each name it found once ("Found N skills", then the names; discoverSkills keeps the first copy of each name).
Prints the counts and every difference; exit 0 when the skipped folders and their warnings equal the reader's skips, the
listed names equal the reader's taken names, both planted controls behave, and every reader "error" is its line-break
refusal (which is left out of the comparison and reported with the CLI's own verdict)."""

import json
import re
import sys

WARNING, DASH = "⚠ Skipped ", " — "
LINE_BREAK_REFUSAL = "a line break to libyaml"
index = json.load(open(sys.argv[1], encoding="utf-8"))
reader = {item["id"]: item for item in json.load(open(sys.argv[2], encoding="utf-8"))["results"]}
ansi = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
stdout = ansi.sub("", open(sys.argv[3], encoding="utf-8").read())
stderr = ansi.sub("", open(sys.argv[4], encoding="utf-8").read())

skipped = {}
for chunk in stderr.split(WARNING)[1:]:
    path, _, reason = chunk.partition(DASH)
    folder = path.rstrip("/").split("/")[-2]
    # The yaml package's own warnings (process.emitWarning, "(node:<pid>) [TAG_RESOLVE_FAILED] YAMLWarning: ...") reach
    # stderr between the CLI's lines; each starts a line, after the line break console.warn adds to the reason.
    cut = reason.find("\n(node:")
    reason = reason[:cut] if cut >= 0 else reason[:-1] if reason.endswith("\n") else reason
    skipped[folder] = reason
found = re.search(r"Found (\d+) skills?", stdout)
listed = set(re.findall("^│    (\\S.*?)\\s*$", stdout, flags=re.M))

errors = {folder: key for folder, key in index.items() if reader[key]["verdict"] == "error"}
reader_skips = {folder: reader[key]["reason"] for folder, key in index.items() if reader[key]["verdict"] == "skip"}
reader_names = {reader[key]["name"] for key in index.values() if reader[key]["verdict"] == "take" and reader[key]["name"]}
# discoverSkills keeps one skill per name (seenNames), so of the copies whose name sanitizes to "" the CLI lists only the
# first it walks, under its folder's name (getSkillDisplayName).
empty_named = {folder for folder, key in index.items() if reader[key]["verdict"] == "take" and not reader[key]["name"]}
cli_skips = {folder: reason for folder, reason in skipped.items() if folder in index and folder not in errors}
problems = []
for folder, key in sorted(errors.items()):
    print(f"reader error ({key}): the CLI {'skips it' if folder in skipped else 'takes it'}")
    if LINE_BREAK_REFUSAL not in (reader[key]["reason"] or ""):
        problems.append(f"{folder}: a reader error other than the line-break refusal: {reader[key]['reason'][:120]}")
if set(cli_skips) != set(reader_skips):
    problems.append(f"skipped folders differ: CLI only {sorted(set(cli_skips) - set(reader_skips))}, "
                    f"reader only {sorted(set(reader_skips) - set(cli_skips))}")
problems += [f"{folder}: warning differs" for folder in sorted(set(cli_skips) & set(reader_skips))
             if cli_skips[folder] != reader_skips[folder]]
corpus_listed = listed - {"zz-planted-valid-7f3a"} - empty_named
if len(listed & empty_named) != (1 if empty_named else 0):
    problems.append(f"{len(listed & empty_named)} of the {len(empty_named)} copies with an empty name are listed")
error_takes = [folder for folder in errors if folder not in skipped]
extra = corpus_listed - reader_names  # a copy the reader leaves without a verdict may add a name the CLI lists
if reader_names - corpus_listed or len(extra) > len(error_takes):
    problems.append(f"listed names differ: CLI only {sorted(extra)[:10]}, "
                    f"reader only {sorted(reader_names - corpus_listed)[:10]}")
controls = {"planted invalid warned": "zz-planted-invalid" in skipped,
            "planted valid listed": "zz-planted-valid-7f3a" in listed,
            "found count = listed names": bool(found) and int(found.group(1)) == len(listed)}
problems += [f"control failed: {name}" for name, ok in controls.items() if not ok]
planted = [folder for folder in skipped if folder not in index]
print(f"CLI: Found {found.group(1) if found else '?'} skills, {len(listed)} names listed, {len(skipped)} warnings "
      f"({len(cli_skips)} compared, {len(skipped) - len(cli_skips) - len(planted)} on copies the reader gives no "
      f"verdict, {len(planted)} planted)")
print(f"reader: {len(index) - len(reader_skips) - len(errors)} take ({len(reader_names)} distinct non-empty names, "
      f"{len(empty_named)} empty), {len(reader_skips)} skip, {len(errors)} error")
print("controls:", json.dumps(controls))
for problem in problems:
    print("DIFF", problem)
print("agreement:", "yes" if not problems else "no")
sys.exit(1 if problems else 0)
