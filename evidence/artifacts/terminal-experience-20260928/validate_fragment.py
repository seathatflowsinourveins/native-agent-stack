#!/usr/bin/env python3
"""Validate Windows Terminal fragment profiles against doc/cascadia/profiles.schema.json at the installed tag.
usage: validate_fragment.py <fragment.json> [<fragment.json> ...]"""
import json, subprocess, sys, tempfile
from pathlib import Path

TAG = "v1.24.11911.0"
SCHEMA_CACHE = Path(tempfile.gettempdir()) / ("wt-profiles.schema." + TAG + ".json")  # never next to the script: the artifacts folder is tracked

def schema():
    if not SCHEMA_CACHE.exists():
        raw = subprocess.run(
            ["gh", "api", "repos/microsoft/terminal/contents/doc/cascadia/profiles.schema.json?ref=" + TAG,
             "-H", "Accept: application/vnd.github.raw"], capture_output=True, text=True, check=True).stdout
        SCHEMA_CACHE.write_text(raw, encoding="utf-8")
    return json.loads(SCHEMA_CACHE.read_text(encoding="utf-8"))

def main(paths):
    import jsonschema
    sch = schema()
    profile_schema = {"$schema": sch["$schema"], "$ref": "#/$defs/Profile", "$defs": sch["$defs"]}
    validator = jsonschema.validators.validator_for(profile_schema)  # the tag's schema declares draft 2020-12, where $ref siblings apply
    print("validator:", validator.__name__)
    bad = 0
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8-sig"))
        for prof in data.get("profiles", []):
            errs = sorted(validator(profile_schema).iter_errors(prof), key=lambda e: list(e.path))
            print(("OK   " if not errs else "FAIL ") + Path(p).name + " :: " + prof.get("name", "?"))
            for e in errs[:5]:
                bad += 1
                print("       ", list(e.path), e.message[:160])
            cl = prof.get("commandline", "")
            if "printf" in cl or "COLORTERM" in cl:
                print("        decoded commandline:", cl)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
