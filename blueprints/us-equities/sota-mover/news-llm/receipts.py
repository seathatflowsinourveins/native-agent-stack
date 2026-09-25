#!/usr/bin/env python3
"""Write the small committed receipts (counts and sha256 only) from the private data root.

  receipts/prepare-summary.json     prepare.py funnel, diagnostics and input hashes
  receipts/models-fetch.json        checkpoint download jobs (bytes, status)
  receipts/collection-summary.json  auction and spread coverage, HTTP tallies
  receipts/scoring-probes.json      prompt-variant and numerics probes
  receipts/scoring-status.json      the full scoring run (labels per checkpoint)

No price, return or other outcome is read or written. Refuses to write a receipt that
would contain the home directory path.
"""
import argparse
import collections
import glob
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE_ROOT = os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-llm")
MODELS_ROOT = os.path.expanduser("~/.local/share/native-agent-stack/models/chronogpt-instruct")
SCHEMA = "sota-news-llm-receipt/1"


def dump(out_dir, name, obj):
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    home = os.path.expanduser("~")
    if home and home != "/" and home in text:
        raise SystemExit(f"refusing to write {name}: it contains the home directory path")
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"wrote {name} ({len(text)} bytes)")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def prepare_summary(priv):
    r = load(os.path.join(priv, "prepare-receipt.json"))
    keys = ("started_at", "finished_at", "inputs", "asset_master", "funnel", "eligible_by_window_lane",
            "selected_by_window_lane", "selected_sessions_by_window_lane", "selected_by_session_year",
            "selected_by_checkpoint", "diagnostics", "events_file")
    return {"schema": SCHEMA, "evidence_label": "HIST", "kind": "prepare", **{k: r[k] for k in keys}}


def models_fetch(models):
    jobs = []
    for path in sorted(glob.glob(os.path.join(models, "fetch-manifest-*.json"))):
        m = load(path)
        jobs.append({"years": m["years"], "finished_at": m["finished_at"], "seconds": m["seconds"],
                     "bytes_downloaded": m["bytes_downloaded"], "bytes_verified": m["bytes_verified"],
                     "files": [{k: rec[k] for k in ("year", "file", "status", "bytes")} for rec in m["records"] if "year" in rec]})
    return {"schema": SCHEMA, "evidence_label": "HIST", "kind": "model-fetch", "jobs": jobs,
            "note": "every file sha256-verified against checkpoints.json at download",
            "bytes_downloaded_total": sum(j["bytes_downloaded"] for j in jobs)}


def ledger_counts(path):
    counts = collections.Counter()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    counts[json.loads(line).get("status", "?")] += 1
                except ValueError:
                    counts["unparseable"] += 1
    return dict(counts)


def collection_summary(priv):
    out = {"schema": SCHEMA, "evidence_label": "HIST", "kind": "collection"}
    auctions = os.path.join(priv, "auctions", "auctions-summary.json")
    if os.path.exists(auctions):
        out["auctions"] = load(auctions)
        out["auctions"]["ledger"] = ledger_counts(os.path.join(priv, "auctions", "ledger.jsonl"))
    spreads = os.path.join(priv, "spreads", "spreads-summary.json")
    if os.path.exists(spreads):
        out["spreads"] = load(spreads)
        out["spreads"]["ledger"] = ledger_counts(os.path.join(priv, "spreads", "ledger.jsonl"))
    out["http_tallies"] = [load(p) for p in sorted(glob.glob(os.path.join(priv, "http-tally-*.json")))]
    out["note"] = ("The first full auction run was stopped during materialization, before it wrote its HTTP tally; "
                   "its 5,347 requests are recorded in auctions/ledger.jsonl (all status ok).")
    return out


def summarize_progress(p):
    labels, stops, agree = collections.Counter(), collections.Counter(), [0, 0]
    for s in p["by_checkpoint"].values():
        labels.update(s["labels"])
        stops.update(s["stops"])
        if "batch1_agreement" in s:
            agree[0] += s["batch1_agreement"]["agree"]
            agree[1] += s["batch1_agreement"]["checked"]
    return labels, stops, {"agree": agree[0], "checked": agree[1]}


def scoring_probes(priv):
    probes = {}
    paths = sorted(glob.glob(os.path.join(priv, "probe", "*", "progress.json")) +
                   glob.glob(os.path.join(priv, "probe", "*", "*", "progress.json")))
    for path in paths:
        p = load(path)
        labels, stops, agree = summarize_progress(p)
        name = os.path.relpath(os.path.dirname(path), os.path.join(priv, "probe"))
        probes[name] = {
            "variant": p.get("variant", "llt_upstream_wrapper"), "dtype": p.get("dtype"), "matmul": p.get("matmul", "default"),
            "decoder": p.get("decoder", "full"), "batch_size": p.get("batch_size"), "scored": p["scored_this_run"],
            "finished": p.get("finished_at") is not None, "labels": dict(labels), "stops": dict(stops),
            "batch1_agreement": agree, "labels_by_checkpoint": {y: s["labels"] for y, s in sorted(p["by_checkpoint"].items())},
            "elapsed_seconds": p.get("elapsed_seconds"),
            "load_seconds": round(sum(s["load_seconds"] for s in p["by_checkpoint"].values()), 1),
            "max_gpu_memory_allocated_gib": p.get("max_gpu_memory_allocated_gib"),
        }
    out = {"schema": SCHEMA, "evidence_label": "HIST", "kind": "scoring-probes", "probes": probes}
    for extra in ("diagnostics.json", "fp32-selection.json"):
        path = os.path.join(priv, "probe", extra)
        if os.path.exists(path):
            out[extra.replace(".json", "").replace("-", "_")] = load(path)
    return out


def scoring_status(priv):
    runs = {}
    for name in ("progress-liquid.json", "progress-small.json", "progress.json"):
        path = os.path.join(priv, "scores", name)
        if not os.path.exists(path):
            continue
        p = load(path)
        labels, stops, agree = summarize_progress(p)
        runs[name] = {
            "progress": {k: p.get(k) for k in ("started_at", "updated_at", "finished_at", "events_in_file", "already_scored",
                                               "to_score", "scored_this_run", "events_per_second", "elapsed_seconds",
                                               "eta_seconds", "variant", "template_sha256", "dtype", "matmul", "decoder",
                                               "batch_size", "max_gpu_memory_allocated_gib")},
            "labels": dict(labels), "stops": dict(stops), "batch1_agreement": agree,
            "by_checkpoint": {y: {k: s.get(k) for k in ("to_score", "scored", "labels", "stops", "overflow", "load_seconds",
                                                         "revision", "batch1_agreement")}
                              for y, s in sorted(p["by_checkpoint"].items())},
        }
    files = {}
    totals = collections.Counter()
    for path in sorted(glob.glob(os.path.join(priv, "scores", "scores-*.jsonl"))):
        rows = 0
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    totals[json.loads(line)["label"]] += 1
                    rows += 1
                except (ValueError, KeyError):
                    continue
        files[os.path.basename(path)] = {"rows": rows}
    return {"schema": SCHEMA, "evidence_label": "HIST", "kind": "scoring-status", "runs": runs,
            "score_files": files, "labels_in_files": dict(totals), "rows_in_files": sum(totals.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--private-root", default=PRIVATE_ROOT)
    parser.add_argument("--models-root", default=MODELS_ROOT)
    parser.add_argument("--out", default=os.path.join(_HERE, "receipts"))
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    dump(args.out, "prepare-summary.json", prepare_summary(args.private_root))
    dump(args.out, "models-fetch.json", models_fetch(args.models_root))
    dump(args.out, "collection-summary.json", collection_summary(args.private_root))
    dump(args.out, "scoring-probes.json", scoring_probes(args.private_root))
    dump(args.out, "scoring-status.json", scoring_status(args.private_root))


if __name__ == "__main__":
    main()
