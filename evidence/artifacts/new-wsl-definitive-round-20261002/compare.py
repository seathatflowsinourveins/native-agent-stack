#!/usr/bin/env python3
"""Compare the clean-room round's outcome with the definitive manifest of #602, row by row (amendment 2).

The definitive manifest on main is the install record; this round neither replaces nor extends it. Each round slot maps
to the manifest row its ``source_slot`` names (43 of 43). The verdicts below were fixed before any decision of the round
existed:

- ``agree`` / ``contest``: the row is resolved for the install (state ``definitive`` or ``resolved``) and the round
  reached a definitive pick; ``agree`` when the pick is the row's repository, or NONE on a row that installs nothing.
- ``nominates``: the row waits for its named measurement (state ``split``); the round's definitive pick is recorded for
  that measurement and settles nothing by itself.
- ``cross_check``: a measurement row (the memory owner waits for the head-to-head; the local model server was settled
  by its gate); the measurement stands, and ``matches`` says whether the round's pick is the row's.
- ``pin_agree`` / ``pin_conflict``: a row the owner pinned (empty state); a conflict is put to the user and the pin
  stays.
- ``not_settled``: the round left the slot unsettled after adjudication; its finalists and settling measurement are
  listed.

Manifest rows that no round slot maps to are listed under ``not_covered``. A ``contest`` is a hand-off to the
manifest's owner; nothing here changes the manifest.

Usage: compare.py [--manifest-ref <commit>] [--selection selection.json] [--out audit-of-manifest.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
MANIFEST_REF = "675bdd51c96af28aa98012d9e4ff772a77a38f3d"  # the merge commit of #602
MANIFEST_SHA256 = "894dff866e2e6f332d6927879ca89b81a7da67d066664122f163e23707c4205b"
# Page contenders carry a shared download page as their repository; the manifest row names the release itself.
ALIASES = {"releases.ubuntu.com/26.04.1": "page:ubuntu-26-04-1-lts-canonical-wsl-image"}
RESOLVED = ("definitive", "resolved")


def norm(url: str | None) -> str:
    """owner/name for a GitHub repository URL, host/path for any other URL (amendment 5: parsed, not matched as text)."""
    raw = (url or "").strip()
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[len("www."):]
    path = parsed.path.strip("/").lower()
    if path.endswith(".git"):
        path = path[:-4]
    if host == "github.com":
        return path
    return f"{host}/{path}" if path else host


def manifest_rows(ref: str) -> tuple[dict, str]:
    raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{MANIFEST}"], capture_output=True,
                         check=True).stdout
    rows = {r["slot_id"]: r for r in json.loads(raw)["slots"] if r.get("catalog") == "foundation"}
    return rows, hashlib.sha256(raw).hexdigest()


def row_picks(row: dict, field: list) -> set:
    """The row's pick as round contender ids, or {"NONE"} for a row that names no repository.

    Amendment 4: a row's pick is the repository it names. ``installs_nothing_extra`` is not a NONE pick: it also marks
    picks that run on GitHub rather than on the host (actions/attest, Dependabot)."""
    repos = [norm(p) for p in (row.get("repository") or "").split(" ; ") if p.strip()]
    if not repos:
        return {"NONE"}
    by_repo = {norm(f["repository"]): f["contender"] for f in field}
    return {ALIASES.get(p) or by_repo.get(p) or f"unlisted:{p}" for p in repos}


def verdict(row: dict, out: dict, field: list) -> dict:
    state = row.get("state") or ""
    keys = {f["key"]: f["contender"] for f in field}
    picks = row_picks(row, field)
    entry = {"manifest_row": row["slot_id"], "manifest_state": state or "pinned", "manifest_pick": sorted(picks),
             "round_status": out["status"], "round_basis": out.get("basis")}
    if out["status"] == "measurement":
        return dict(entry, verdict="not_settled", finalists=[keys.get(k, k) for k in out.get("finalists") or []],
                    settling_measurement=out.get("settling_measurement"))
    pick = "NONE" if out.get("default") == "NONE" else out.get("contender")
    entry["round_pick"] = pick
    if state in RESOLVED:
        return dict(entry, verdict="agree" if pick in picks else "contest")
    if state == "split":
        return dict(entry, verdict="nominates", manifest_measurement=row.get("measurement"))
    if state == "measurement":
        return dict(entry, verdict="cross_check", matches=pick in picks)
    return dict(entry, verdict="pin_agree" if pick in picks else "pin_conflict")


def compare(selection: dict, units: list, rows: dict) -> dict:
    fields = {u["unit_id"]: u["field"] for u in units}
    sources = {(u["unit_id"], s["slot_id"]): s["source_slot"] for u in units for s in u["slots"]}
    result, mapped = [], set()
    for unit in selection["units"]:
        for slot in unit["slots"]:
            source = sources[(unit["unit_id"], slot["slot_id"])]
            mapped.add(source)
            result.append({"unit_id": unit["unit_id"], "slot_id": slot["slot_id"],
                           **verdict(rows[source], slot["outcome"], fields[unit["unit_id"]])})
    counts: dict = {}
    for r in result:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    not_covered = [{"layer_id": r["layer_id"], "slot_id": r["slot_id"], "state": r.get("state") or "pinned",
                    "default": r.get("default")} for sid, r in sorted(rows.items()) if sid not in mapped]
    return {"counts": counts, "rows": result, "not_covered": not_covered}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--manifest-ref", default=MANIFEST_REF)
    parser.add_argument("--selection", type=Path, default=HERE / "selection.json")
    parser.add_argument("--out", type=Path, default=HERE / "audit-of-manifest.json")
    args = parser.parse_args(argv)
    rows, digest = manifest_rows(args.manifest_ref)
    if args.manifest_ref == MANIFEST_REF and digest != MANIFEST_SHA256:
        print(f"manifest at {MANIFEST_REF} has sha256 {digest}, not the one amendment 2 recorded", file=sys.stderr)
        return 1
    data = json.loads((HERE / "units.json").read_text(encoding="utf-8"))
    units = data["units"] if isinstance(data, dict) else data
    report = compare(json.loads(args.selection.read_text(encoding="utf-8")), units, rows)
    record = {"schema_version": 1, "kind": "definitive_round_audit_of_manifest", "rule": "compare.py, amendment 2",
              "manifest": {"path": MANIFEST, "ref": args.manifest_ref, "sha256": digest}, **report}
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "not_covered": len(report["not_covered"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
