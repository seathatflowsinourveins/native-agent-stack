"""Ledger of a gap-evidence wave keyed to the gap crosswalk (offline, deterministic).

Reads the crosswalk at catalogs/landscape/gap-crosswalk-92bb279.json and the wave's receipts
under evidence/artifacts/<wave>/<layer_id>/*.json (default) or <wave>/<catalog>__<layer_id>/*.json
(--dir-style catalog__layer, where gap_refs may omit layer_id; results.json is skipped), and writes
a ledger plus a summary page:

  python3 tools/sota-convergence/gap_wave_ledger.py --wave gap-wave2-20260923 --owner gap-resolution [--check]
  python3 tools/sota-convergence/gap_wave_ledger.py --wave gap-wave2-20260923 --owner agent-lab-17 --dir-style catalog__layer

Status per crosswalk gap: settled / advanced / not_settled from the receipts' settles_gap
(true / partially / false), or from a receipt's per_gap_settles entry ("<layer>:<index>") when it
has one, best over the receipts that name the gap. A receipt naming several
gaps carries one settles_gap value, so it credits each named gap at most "advanced": only a
single-gap receipt can settle a gap. Gaps the owner was assigned but no receipt names are
"not_run". Nothing here changes a verdict.
"""
import argparse
import hashlib
import json
import pathlib
import sys

CROSSWALK = "catalogs/landscape/gap-crosswalk-92bb279.json"
RANK = {"not_run": 0, "not_settled": 1, "advanced": 2, "settled": 3}
SETTLES = {"true": "settled", "partially": "advanced", "false": "not_settled"}


def settle_key(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    key = str(value).strip().split(" ")[0].strip("(),").lower()
    if key not in SETTLES:
        raise SystemExit(f"unknown settles_gap value {value!r}")
    return key


def _receipt_dirs(base, dir_style):
    """(directory, default layer_id) pairs. "layer": <layer_id>/ (no "__"); "catalog__layer":
    <catalog>__<layer_id>/, where gap_refs entries may omit layer_id."""
    for directory in sorted(p for p in base.iterdir() if p.is_dir()):
        if dir_style == "layer" and "__" not in directory.name:
            yield directory, directory.name
        elif dir_style == "catalog__layer" and "__" in directory.name:
            yield directory, directory.name.split("__", 1)[1]


def _refs(data, default_layer, path):
    refs = []
    for g in data["gap_refs"]:
        if isinstance(g, dict) and "gap_index" in g:
            refs.append((g.get("layer_id", default_layer), int(g["gap_index"])))
        elif isinstance(g, int):
            refs.append((default_layer, g))
        else:
            raise SystemExit(f"{path}: unrecognised gap_refs entry {g!r}")
    return refs


def load_receipts(root, wave, dir_style="layer"):
    base = root / "evidence/artifacts" / wave
    out = []
    for directory, default_layer in _receipt_dirs(base, dir_style):
        for path in sorted(directory.glob("*.json")):
            if path.name == "results.json":
                continue  # a per-layer index, not a receipt
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "gap_refs" not in data:
                continue
            refs = _refs(data, default_layer, path)
            per_gap = {k: settle_key(v) for k, v in (data.get("per_gap_settles") or {}).items()}
            for key in per_gap:
                if key not in {f"{l}:{i}" for l, i in refs}:
                    raise SystemExit(f"{path}: per_gap_settles names {key}, which is not in gap_refs")
            vi = data.get("verdict_impact") or {}
            calls = data.get("model_calls") or []
            out.append({
                "path": str(path.relative_to(root)), "id": data.get("id"),
                "source_revision": data.get("source_revision"), "gap_refs": [list(r) for r in refs],
                "settles_gap": data.get("settles_gap"), "settles_key": settle_key(data.get("settles_gap")),
                "per_gap_settles": per_gap,
                "direction": vi.get("direction"), "evidence_class": data.get("evidence_class"),
                "model_calls": sum(int(c.get("count", 0) or 0) for c in calls if isinstance(c, dict)),
            })
    return out


def build(root, wave, owner, dir_style="layer"):
    crosswalk = json.loads((root / CROSSWALK).read_text(encoding="utf-8"))
    receipts = load_receipts(root, wave, dir_style)
    rev = crosswalk["source_revision"]
    for r in receipts:
        if not rev.startswith(str(r["source_revision"])[:7]):
            raise SystemExit(f"{r['path']}: source_revision {r['source_revision']} is not the crosswalk's {rev}")
    by_gap = {}
    for r in receipts:
        for layer, index in r["gap_refs"]:
            credit = SETTLES[r["per_gap_settles"].get(f"{layer}:{index}", r["settles_key"])]
            if len(r["gap_refs"]) > 1 and credit == "settled":
                credit = "advanced"
            by_gap.setdefault((layer, index), []).append((r["path"], credit))
    known = {(l["layer_id"], g["index"]) for l in crosswalk["layers"] for g in l["gaps"]}
    unknown = sorted(k for k in by_gap if k not in known)
    if unknown:
        raise SystemExit(f"receipts name gaps absent from the crosswalk: {unknown}")
    layers, counts = [], {}
    for layer in crosswalk["layers"]:
        if layer["owner"] != owner:
            continue
        gaps = []
        for gap in layer["gaps"]:
            if gap["category"] != "executable_now" or gap["status"] == "settled_by_receipt":
                continue
            hits = by_gap.get((layer["layer_id"], gap["index"]), [])
            status = max((c for _, c in hits), key=RANK.get, default="not_run")
            counts[status] = counts.get(status, 0) + 1
            gaps.append({"index": gap["index"], "text": gap["text"], "next_check": gap.get("next_check"),
                         "status": status, "receipts": [{"path": p, "credit": c} for p, c in hits]})
        layers.append({"catalog": layer["catalog"], "layer_id": layer["layer_id"], "gaps": gaps})
    doc = {
        "schema_version": 1, "id": f"{wave}--{owner}", "wave": wave, "owner": owner,
        "source_revision": rev, "crosswalk": CROSSWALK,
        "crosswalk_sha256": hashlib.sha256((root / CROSSWALK).read_bytes()).hexdigest(),
        "rule": ("status is the best credit over the receipts naming the gap; settles_gap true/partially/false "
                 "credit settled/advanced/not_settled, but a receipt naming several gaps credits each at most "
                 "advanced; not_run means no receipt names the gap. No verdict changes here."),
        "counts": dict(sorted(counts.items())), "layers": layers,
        "receipts": sorted(({k: v for k, v in r.items() if k != "settles_key" and not (k == "per_gap_settles" and not v)}
                             for r in receipts), key=lambda r: r["path"]),
    }
    return doc


def render(doc):
    lines = [f"# Gap evidence wave `{doc['wave']}` ({doc['owner']} layers)", "",
             f"This page summarizes [`catalogs/landscape/{doc['id']}.json`](../catalogs/landscape/{doc['id']}.json). "
             f"It records the executed checks for the `executable_now` gaps the [crosswalk](gap-crosswalk-92bb279.md) "
             f"assigned to `{doc['owner']}`, keyed to the rows at `{doc['source_revision'][:7]}`. "
             "Each receipt was reviewed by an Opus evidence reviewer and corrected in one fix round. No verdict changes here.", "",
             f"Rule: {doc['rule']}", "", "## Totals", "", "| Status | Gaps |", "| --- | ---: |"]
    lines += [f"| {k} | {doc['counts'].get(k, 0)} |" for k in ("settled", "advanced", "not_settled", "not_run")]
    lines += ["", f"Receipts: {len(doc['receipts'])}; native model calls recorded: "
              f"{sum(r['model_calls'] for r in doc['receipts'])}.", "",
              "## Per gap", "", "| Layer | Gap | Status | Receipts |", "| --- | ---: | --- | --- |"]
    for layer in doc["layers"]:
        for gap in layer["gaps"]:
            links = ", ".join(f"[{pathlib.Path(r['path']).stem}](../{r['path']})" for r in gap["receipts"]) or "none"
            lines.append(f"| {layer['layer_id']} | {gap['index']} | {gap['status']} | {links} |")
    refute = [r for r in doc["receipts"] if r["direction"] == "refutes_incumbent"]
    lines += ["", "## Receipts that refute the incumbent", ""]
    lines += [f"- [{pathlib.Path(r['path']).stem}](../{r['path']}) ({r['settles_gap']})" for r in refute] or ["None."]
    lines += ["", "## Limits", "",
              "- A status records what a receipt shows about the gap text at the source revision; a later re-record needs a new crosswalk.",
              "- `not_run` gaps stayed open for the reasons recorded in the units' results (budget, shared-account window, or a check that needs the user).", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    ap.add_argument("--wave", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dir-style", choices=("layer", "catalog__layer"), default="layer",
                    help="receipt directory layout: <layer_id>/ (default) or <catalog>__<layer_id>/")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    doc = build(root, args.wave, args.owner, args.dir_style)
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    page = render(doc)
    out, md = root / f"catalogs/landscape/{doc['id']}.json", root / f"docs/{doc['id']}.md"
    if args.check:
        ok = out.exists() and md.exists() and out.read_text(encoding="utf-8") == text and md.read_text(encoding="utf-8") == page
        print(json.dumps({"status": "checked" if ok else "stale", "counts": doc["counts"]}))
        return 0 if ok else 1
    out.write_text(text, encoding="utf-8")
    md.write_text(page, encoding="utf-8")
    print(json.dumps({"status": "written", "counts": doc["counts"], "receipts": len(doc["receipts"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
