#!/usr/bin/env python3
"""Purge/embargo/fold-boundary arms around the unmodified research-evaluation helpers.

Imports label/choose/summaries/load_panel/verify_inputs from
blueprints/us-equities/research-evaluation/evaluate.py without changing them.
Arms:
  Z-check : purged_size=0, embargo=0; the 'incomplete training label' check that
            evaluate.main also performs fires first (expected to raise)
  Z-leaky : purged_size=0, embargo=0, training labels may cross into the test
            window and the overlap check is bypassed (labelled leaky reference)
  P6      : plan purged_size=6, embargo=0 (must reproduce the accepted receipt)
  P6E5    : purged_size=6, embargo=5 sessions dropped from each training tail,
            and evaluation labels whose exit is after the fold's last test
            session are censored (fold-boundary rule)
  Z-choose  (fix round 3): purge 0 with the full segment panel, so overlapping
            training labels are observed and unmodified evaluate.choose must raise
  P6-assert (fix round 3): plan P6 with the P6E5 fold-boundary assertion enforced
            and no censoring (expected AssertionError)
Every arm also runs the fold-boundary audit in report mode so the detector's
ability to see crossings is shown on the arms that have them.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO / "blueprints/us-equities/research-evaluation"
sys.path.insert(0, str(EVAL_DIR))
import evaluate as ev  # noqa: E402

ARMS = {
    "Z-check": {"purged_size": 0, "embargo": 0, "fold_censor": False, "leaky": False},
    "Z-leaky": {"purged_size": 0, "embargo": 0, "fold_censor": False, "leaky": True},
    "P6": {"purged_size": 6, "embargo": 0, "fold_censor": False, "leaky": False},
    "P6E5": {"purged_size": 6, "embargo": 5, "fold_censor": True, "leaky": False},
    # Fix round 3 arms (negative controls for the detectors themselves).
    "Z-choose": {"purged_size": 0, "embargo": 0, "fold_censor": False, "leaky": False, "full_panel": True},
    "P6-assert": {"purged_size": 6, "embargo": 0, "fold_censor": False, "leaky": False, "enforce": True},
}


def choose_leaky(rows, candidates, cutoff):
    """evaluate.choose without its first overlap check (leaky reference arm only)."""
    grouped = {c: [Decimal(r["net_proxy"]) for r in rows if r["candidate"] == c] for c in candidates}
    means = {c: sum(x) / len(x) for c, x in grouped.items()}
    chosen = max(candidates, key=lambda c: means[c])
    return {"chosen": chosen, "training_episode_count": len(grouped[chosen]),
            "scores": {c: str(v) for c, v in means.items()}, "evaluation_cutoff": cutoff,
            "latest_training_exit": max(r["exit"] for r in rows)}


def boundary_audit(dates, training, evaluation, cutoff, test_last, embargo):
    """Count label windows that cross a fold boundary (report mode)."""
    index = {d: i for i, d in enumerate(dates)}
    cut = index[cutoff]
    train_obs = [r for r in training if r["status"] == "observed"]
    crossing_train = [r for r in train_obs if index[r["exit"]] >= cut]
    inside_embargo = [r for r in train_obs if cut - index[r["exit"]] - 1 < embargo]
    eval_obs = [r for r in evaluation if r["status"] == "observed"]
    crossing_eval = [r for r in eval_obs if r["exit"] > test_last or r["decision"] < cutoff]
    return {"training_labels_crossing_test_start": len(crossing_train),
            "training_labels_inside_embargo": len(inside_embargo),
            "evaluation_labels_crossing_fold_end": len(crossing_eval),
            "min_sessions_between_training_exit_and_cutoff": (min(cut - index[r["exit"]] - 1 for r in train_obs) if train_obs else None)}


def run_arm(name, spec, root, plan):
    from skfolio.model_selection import WalkForward
    import pandas as pd
    panel, dates, auxiliary, counts = ev.load_panel(root, plan)
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    anchor = eligible[0]
    cost = Decimal(plan["round_trip_cost_fraction"])
    candidates = plan["candidates"]

    def episodes(indices):
        return [int(i) for i in indices if (i - anchor) % 5 == 0]

    def prefix(cutoff):
        size = next((i for i, d in enumerate(dates) if d >= cutoff), len(dates))
        return {s: rows[:size] for s, rows in panel.items()}

    purge, embargo = spec["purged_size"], spec["embargo"]
    frame = pd.DataFrame({"session": [dates[i] for i in eligible]}, index=pd.to_datetime([dates[i] for i in eligible]))
    splitter = WalkForward(train_size=252, test_size=63, purged_size=purge, reduce_test=True)
    development_panel = prefix(plan["reserved_start"])
    folds, ledger = [], 0

    def fold(fname, train, test, eval_panel, segment_panel):
        cutoff = dates[int(test[0])]
        test_last = dates[int(test[-1])]
        if embargo:
            train = train[:-embargo]
        training_panel = segment_panel if (spec["leaky"] or spec.get("full_panel")) else prefix(cutoff)
        training = [ev.label(training_panel, i, c, cost) for i in episodes(train) for c in candidates]
        if any(r["status"] != "observed" for r in training):
            raise ValueError("incomplete training label")
        selection = (choose_leaky if spec["leaky"] else ev.choose)(training, plan["selection_candidates"], cutoff)
        evaluation = [ev.label(eval_panel, i, c, cost) for i in episodes(test) for c in candidates]
        audit_before = boundary_audit(dates, training, evaluation, cutoff, test_last, embargo)
        if spec["fold_censor"] or spec.get("enforce"):
            if spec["fold_censor"]:
                evaluation = [dict(r, status="censored", reason="exit after fold test_last")
                              if r["status"] == "observed" and r["exit"] > test_last else r for r in evaluation]
            audit_after = boundary_audit(dates, training, evaluation, cutoff, test_last, embargo)
            # Enforced assertions for the purged/embargoed arm.
            if audit_after["training_labels_crossing_test_start"] or audit_after["training_labels_inside_embargo"] \
                    or audit_after["evaluation_labels_crossing_fold_end"]:
                raise AssertionError("development label window crosses a fold boundary: " + fname)
        else:
            audit_after = None
        summary = ev.summaries(evaluation, candidates)
        return {"id": fname, "chosen": selection["chosen"], "scores": selection["scores"],
                "train_first": dates[int(train[0])], "train_last": dates[int(train[-1])],
                "test_first": cutoff, "test_last": test_last, "train_sessions": len(train),
                "training_episode_count": selection["training_episode_count"],
                "boundary_audit_before_censor": audit_before, "boundary_audit_enforced": audit_after,
                "selected": summary[selection["chosen"]], "records": len(training) + len(evaluation),
                "training_net_labels": {c: [r["net_proxy"] for r in training if r["candidate"] == c] for c in plan["selection_candidates"]}}

    for j, (train, test) in enumerate(splitter.split(frame)):
        f = fold("development-" + str(j + 1), [eligible[int(i)] for i in train], [eligible[int(i)] for i in test],
                 development_panel, development_panel)
        folds.append(f)
        ledger += f["records"]
    reserved_train = eligible[-(252 + purge):len(eligible) - purge]
    heldout = fold("reserved-2021q1", reserved_train, reserved, panel, panel)
    ledger += heldout["records"]
    return {"arm": name, "spec": spec, "development_fold_count": len(folds), "ledger_records": ledger,
            "folds": folds, "reserved": heldout}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("skfolio") != "1.2.9":
        raise ValueError("use the accepted skfolio version")
    root = args.lean_source.resolve()
    plan = json.loads((EVAL_DIR / "plan.json").read_text())
    inputs = ev.verify_inputs(root, plan["inputs"])
    args.out.mkdir(parents=True, exist_ok=False)
    results = {"plan_sha256": ev.digest(EVAL_DIR / "plan.json"), "evaluate_py_sha256": ev.digest(EVAL_DIR / "evaluate.py"),
               "runner_sha256": ev.digest(__file__),
               "versions": {p: importlib.metadata.version(p) for p in ["skfolio", "pandas", "numpy", "scikit-learn"]},
               "arms": {}}
    for name, spec in ARMS.items():
        try:
            results["arms"][name] = run_arm(name, spec, root, plan)
            results["arms"][name]["status"] = "completed"
        except (ValueError, AssertionError) as exc:
            results["arms"][name] = {"arm": name, "spec": spec, "status": "raised", "error": type(exc).__name__ + ": " + str(exc)}
    results["inputs_unchanged"] = ev.verify_inputs(root, plan["inputs"]) == inputs
    arms = results["arms"]
    comparison = []
    for k in range(max(len(a.get("folds", [])) for a in arms.values())):
        row = {"fold": k + 1}
        for name in ["Z-leaky", "P6", "P6E5"]:
            a = arms[name]
            if a["status"] == "completed" and k < len(a["folds"]):
                f = a["folds"][k]
                row[name] = {"chosen": f["chosen"], "test": [f["test_first"], f["test_last"]]}
        comparison.append(row)
    results["selection_comparison"] = comparison
    results["reserved_selection"] = {n: a["reserved"]["chosen"] for n, a in arms.items() if a["status"] == "completed"}
    (args.out / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    brief = {n: ({"status": a["status"], "folds": a.get("development_fold_count"), "ledger_records": a.get("ledger_records"),
                  "reserved": a.get("reserved", {}).get("chosen"),
                  "reserved_mean_net": a.get("reserved", {}).get("selected", {}).get("mean_net_cost_proxy_label"),
                  "eval_crossings_before_censor": sum(f["boundary_audit_before_censor"]["evaluation_labels_crossing_fold_end"] for f in a.get("folds", [])),
                  "train_crossings": sum(f["boundary_audit_before_censor"]["training_labels_crossing_test_start"] for f in a.get("folds", []))}
                 if a["status"] == "completed" else {"status": a["status"], "error": a["error"]}) for n, a in arms.items()}
    print(json.dumps({"arms": brief, "inputs_unchanged": results["inputs_unchanged"],
                      "results_sha256": hashlib.sha256((args.out / "results.json").read_bytes()).hexdigest()}, indent=1))


if __name__ == "__main__":
    main()
