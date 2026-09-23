#!/usr/bin/env python3
"""Copy the cited raw outputs of this layer's runs into the evidence directory with host paths replaced.

Home directory -> $HOME, host name -> <host>. Records source and published sha256 in inputs/raw-index.json.
Usage: publish_raw.py EVIDENCE_DIR RUNS_DIR
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

EV, RUNS = Path(sys.argv[1]), Path(sys.argv[2])
HOME = os.path.expanduser("~")
HOST = socket.gethostname()
DVC, STO, LIN = "dvc-20260923T050541Z", "stores-fix2-20260923T054530Z", "lineage-fix-20260923T053153Z"
STO2 = "stores-fix-20260923T053213Z"  # fix round 1, superseded by fix round 2 (recovery predicate); kept as history
STO1, LIN1 = "stores-20260923T051425Z", "lineage-20260923T051940Z"  # round 1, superseded after the Codex review; kept as history
C03, ICE3, LIN3 = "c03-fix3-20260923T132058Z", "iceberg-retry-fix3-20260923T132130Z", "lineage-verify-fix3"  # fix round 3 (preregistration-fixround3.json)
LIN4 = "lineage-verify-fix4"  # fix round 4 (preregistration-fixround4.json L5.3)
C = RUNS.parent

ITEMS = {
    "raw/dvc": [f"{DVC}/{n}" for n in (
        "run.log", "attempt1-run.log", "attempt2-run.log", "comparison.json",
        "git-pre-delete.sha256", "git-post-checkout.sha256", "git-post-force.sha256",
        "identity-pre-delete.sha256", "identity-post-checkout.sha256", "identity-post-force.sha256",
        "add-pre-delete.sha256", "add-post-checkout.sha256", "add-materialize.json", "add-restored-ns_select.json",
        "first-ns-snapshot.json", "forced-ns-snapshot.json", "first-pit-snapshot.json", "forced-pit-snapshot.json",
        "local.sha256")]
    + [f"{DVC}/restored-rerun/{n}" for n in ("ns_select.json", "ns_quarantine.json", "pit_select.json", "pit_quarantine.json",
                                              "id_select.json", "ns_materialize.json", "pit_snapshot.json", "id_ledger.json")]
    + [f"{DVC}/git-repro-out/{n}" for n in ("ns_select.json", "ns_quarantine.json", "pit_select.json", "pit_quarantine.json")]
    + [f"{DVC}/identity-repro-out/id_select.json"]
    + [f"{DVC}/local/{n}" for n in ("ns_select.json", "ns_quarantine.json", "pit_select.json", "pit_quarantine.json", "id_select.json",
                                     "ns_materialize.json", "pit_snapshot.json", "id_ledger.json")]
    + [f"{DVC}/repo-git/dvc.lock", f"{DVC}/repo-identity/dvc.lock"],
    "raw/stores": [f"{STO}/{n}" for n in ("run.log", "baseline.json", "dvc.json", "iceberg.json", "arctic.json")]
    + [f"{STO}/conc30-{a}-{r}.json" for a in ("baseline", "dvc", "iceberg", "arctic") for r in (1, 2)],
    "raw/stores-fixround1": [f"{STO2}/{n}" for n in ("run.log", "baseline.json", "dvc.json", "iceberg.json", "arctic.json")]
    + [f"{STO2}/conc30-{a}-{r}.json" for a in ("baseline", "dvc", "iceberg", "arctic") for r in (1, 2)],
    "raw/stores-round1": [f"{STO1}/{n}" for n in ("run.log", "attempt1-run.log", "attempt2-run.log", "baseline.json", "dvc.json", "iceberg.json", "arctic.json")]
    + [f"{STO1}/conc30-{a}-{r}.json" for a in ("baseline", "dvc", "iceberg", "arctic") for r in (1, 2)],
    "raw/lineage": [f"{LIN}/{n}" for n in ("run.log", "work/emit.json", "work/readback.json", "work/openlineage-events.ndjson")],
    "raw/lineage-round1": [f"{LIN1}/{n}" for n in ("run.log", "attempt1-run.log", "attempt2-run.log", "netprobe-control.log",
                                                   "work/emit.json", "work/readback.json", "work/openlineage-events.jsonl")],
    "raw/install": ["../install.log"],
    "raw/dvc-fixround3": [f"{C03}/{n}" for n in ("run.log", "pre-delete.sha256", "b-post-checkout.sha256", "c-post-checkout.sha256",
                                                "d-post-checkout.sha256", "e-tampered.sha256", "e-post-force-checkout.sha256", "repo-git/dvc.lock")],
    "raw/stores-fixround3": [f"{ICE3}/{n}" for n in ("run.log", "conc30-iceberg-1.json", "conc30-iceberg-2.json")]
    + [f"{ICE3}/conc30-iceberg-{r}/conc-{t}.stderr" for r in (1, 2) for t in ("a", "b")],
    "raw/lineage-fixround3": [f"{LIN3}/{n}" for n in ("run.log", "verify.json")],
    "raw/lineage-fixround4": [f"{LIN4}/{n}" for n in ("run.log", "verify.json")],
    "raw/fixround5-timeline": ["fixround5-timeline/timeline.json"],  # fix round 5: L5.3b(iii) change timeline (extract_fixround4_timeline.py)
    "raw/review-fixround3-codex": [f"review-fix3-codex/{n}" for n in ("prompt.txt", "review.out", "review-stderr.txt")],
}


WINUSER = "/mnt/c/Users/" + os.path.basename(HOME)
# Privacy sweep 2026-09-23 (PR #132 review): the host username is also replaced, as a whole word.
USER_RE = __import__("re").compile(r"(?<![A-Za-z0-9])" + __import__("re").escape(os.path.basename(HOME)) + r"(?![A-Za-z0-9])")
import re as _re
UUID_RE = _re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", _re.I)
UUID_MAP = {}


def redact_uuids(text):
    """Replace each UUID (OpenLineage runIds and similar) with a stable placeholder, the same across all published files."""
    def sub(m):
        key = m.group(0).lower()
        if key not in UUID_MAP:
            # Not UUID-shaped: scripts/validate.py rejects any UUID-shaped string in published files (fix round 3 tried
            # valid-format placeholder UUIDs and the publication validator refused them; see receipt 5, L5.2 amendment).
            UUID_MAP[key] = f"uuid-redacted-{len(UUID_MAP) + 1:02d}"
        return UUID_MAP[key]
    return UUID_RE.sub(sub, text)


def sha(b):
    return hashlib.sha256(b).hexdigest()


index = []
for sub, names in ITEMS.items():
    for name in names:
        src = (RUNS / name).resolve()
        raw = src.read_bytes()
        text = raw.decode()
        pub = text.replace(HOME, "$HOME").replace(HOST, "<host>").replace(WINUSER, "/mnt/c/Users/example")
        pub = USER_RE.sub("<user>", redact_uuids(pub))
        rel_parts = Path(name).parts
        dest_name = "__".join(p for p in rel_parts[1:] if p != "..") if rel_parts[0] != ".." else rel_parts[-1]
        if dest_name in ("dvc.lock",):
            dest_name = rel_parts[1] + "__dvc.lock"
        if dest_name.endswith(".jsonl"):
            dest_name = dest_name[:-1].replace(".json", ".ndjson")  # .jsonl is gitignored in this repository
        dest = EV / sub / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(pub)
        index.append({"path": str(dest.relative_to(EV)), "source": "$HOME/" + str(src.relative_to(HOME)),
                      "source_sha256": sha(raw), "sha256": sha(pub.encode()), "bytes": len(pub.encode()),
                      "sanitized": pub != text})
freezes = {}
for v in ("core", "iceberg", "arctic", "mlflow"):
    import subprocess
    out = subprocess.run(["uv", "pip", "freeze", "--python", str(C / f"venv-{v}/bin/python")], capture_output=True, text=True).stdout
    dest = EV / "raw/install" / f"venv-{v}.freeze.txt"
    dest.write_text(out)
    index.append({"path": str(dest.relative_to(EV)), "source": f"uv pip freeze --python $HOME/.cache/gap-wave2-20260923/identity-provenance/venv-{v}/bin/python",
                  "source_sha256": sha(out.encode()), "sha256": sha(out.encode()), "bytes": len(out.encode()), "sanitized": False})
spec = C / "spec/OpenLineage-2-0-2.json"
dest = EV / "raw/install/OpenLineage-2-0-2.json"
dest.write_bytes(spec.read_bytes())
index.append({"path": str(dest.relative_to(EV)), "source": "https://openlineage.io/spec/2-0-2/OpenLineage.json (curl, 2026-09-23T05:18Z)",
              "source_sha256": sha(spec.read_bytes()), "sha256": sha(spec.read_bytes()), "bytes": spec.stat().st_size, "sanitized": False})
leftover = [i["path"] for i in index if HOME in (EV / i["path"]).read_text() or HOST in (EV / i["path"]).read_text()]
(EV / "inputs" / "raw-index.json").write_text(json.dumps({"schema_version": 1, "replacements": {"home_directory": "$HOME", "host_name": "<host>",
                                                                  "windows_user_dir": "/mnt/c/Users/example",
                                                                  "user_name": "<user>",
                                                                  "uuids": f"{len(UUID_MAP)} distinct UUIDs (OpenLineage runIds etc.) -> uuid-redacted-NN, one stable mapping across all published files; checks ran on the originals (source_sha256)"},
                                               "files": index, "unsanitized_leftovers": leftover}, indent=2) + "\n")
print(len(index), "files; leftovers:", leftover)
