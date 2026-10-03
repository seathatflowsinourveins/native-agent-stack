#!/usr/bin/env python3
"""Re-run the frozen verification loop on saved dossiers whose verification returned nothing (amendment 3).

A usage-limit stop can end a dossier's verifier attempts after its writer finished: run_round.py then saves the dossier
with no verification result, and a rerun skips the saved record. For each such record this runs exactly the
verification loop of ``run_round.dossier_one``: the same verify prompt, model, tools, schema and timeout, at most one
writer repair with the same repair prompt, and a second verification. The earlier attempts stay in the record under
``verification_lost``; the raw returns of this pass are written beside the originals as ``.reverify<n>.json`` and
``.rerepair.json``. A record whose verification fails again for lack of a result stays eligible for the next pass.

Usage: reverify.py --work <private run dir> [--jobs N] [--list]
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_round as rr  # noqa: E402


def needs(record: dict) -> bool:
    rounds = record.get("verification") or []
    return bool(record.get("dossier")) and not (rounds and rounds[-1].get("result"))


def reverify(path: Path, work: Path) -> dict:
    record = rr.load(path)
    cid = record["contender"]
    if not needs(record):
        return {"contender": cid, "status": "skipped"}
    c = next(x for x in rr.contenders() if x["contender"] == cid)
    clone = work / "clones" / rr.safe(cid)
    meta = record["meta"]
    # The writer prompt and tools, built exactly as run_round.dossier_one builds them (the repair prompt extends it).
    project = {"name": c["name"], "repository": c["repository"], "extra_repositories": c.get("extra_repositories"),
               "revision": {"tag": meta.get("tag"), "commit": meta.get("commit")}}
    if meta["kind"] == "pages":
        project["pages_to_read"] = meta["pages"]
    tools = ["Read", "Grep", "Glob"] + (["WebFetch"] if meta["kind"] == "pages" else [])
    prompt = ((rr.HERE / "dossier-prompt.txt").read_text(encoding="utf-8")
              .replace("__CONTENDER__", json.dumps(project, indent=2)).replace("__UNITS__", rr.unit_context(cid)))
    schema = rr.load(rr.HERE / "dossier-schema.json")
    raw_dir = work / "raw" / "dossiers"
    lost = record.get("verification") or []
    record.setdefault("verification_lost", []).extend(lost)
    # A dossier already repaired once had lost only its second verification: it gets that one verification and no
    # further repair, so no dossier is repaired more than once. Its first round's result stays in place.
    if record.get("repaired"):
        record["verification"], rounds = [r for r in lost if r.get("round") == 1 and r.get("result")], (2,)
    else:
        record["verification"], rounds = [], (1, 2)
    for round_ in rounds:
        v_prompt = (rr.HERE / "verify-prompt.txt").read_text(encoding="utf-8").replace(
            "__DOSSIER__", json.dumps(record["dossier"], indent=2))
        verified = rr.attempt(rr.claude, v_prompt, clone, rr.JUDGE_MODEL, tools, rr.load(rr.HERE / "verify-schema.json"),
                              rr.TIMEOUT["verify"], raw_dir / f"{rr.safe(cid)}.reverify{round_}.json")
        record["verification"].append({"round": round_, "attempts": verified["attempts"],
                                       "result": verified["parsed"]})
        result = verified["parsed"] or {}
        if result.get("verdict") != "fail" or round_ == 2:
            break
        repair = (prompt + "\n\nA verifier checked your earlier dossier and found these problems; fix them and "
                  "return the full corrected dossier:\n" + json.dumps(result.get("repairs") or [], indent=2)
                  + "\n\nEarlier dossier:\n" + json.dumps(record["dossier"], indent=2))
        redone = rr.attempt(rr.claude, repair, clone, rr.WRITER_MODEL, tools, schema, rr.TIMEOUT["dossier"],
                            raw_dir / f"{rr.safe(cid)}.rerepair.json")
        record["writer"] += redone["attempts"]
        if redone["parsed"]:
            record["dossier"], record["repaired"] = redone["parsed"], True
            record["dossier"]["contender"] = cid
    rr.dump(path, record)
    last = record["verification"][-1].get("result") or {}
    return {"contender": cid, "status": last.get("verdict") or "no_result"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--list", action="store_true", help="print the records that need verification and stop")
    args = parser.parse_args(argv)
    work = args.work.resolve()
    todo = [p for p in sorted((work / "dossiers").glob("*.json")) if needs(rr.load(p))]
    if args.list:
        print(json.dumps({"need_verification": [rr.load(p)["contender"] for p in todo]}))
        return 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda p: reverify(p, work), todo))
    print(json.dumps({"stage": "reverify", "results": results}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
