#!/usr/bin/env python3
"""c22 matched arm: scikit-learn TimeSeriesSplit(gap=...) run on the SAME frozen
blueprints/us-equities/research-evaluation/plan.json inputs and the SAME metric
(reserved-segment selected-candidate mean_net_cost_proxy_label, and development
fold/ledger counts) as the skfolio WalkForward receipt at
blueprints/us-equities/research-evaluation/receipt.json.

This reuses evaluate.py's unmodified helper functions (verify_inputs, load_panel,
label, choose, summaries) so the label/selection/cost logic is byte-identical to
the accepted skfolio study; only the splitter changes.

Preregistered metric (fixed before running): for each arm, report (a) development
fold count, (b) total ledger record count, (c) the reserved-segment chosen
candidate, and (d) that candidate's reserved mean_net_cost_proxy_label. A result
counts as "matches skfolio" only if (c) and (d) are identical; a different chosen
candidate or a materially different net-of-cost mean is a genuine divergence, not
noise.
"""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent.parent / "us-equities" / "research-evaluation"


def load_evaluate_module():
    spec = importlib.util.spec_from_file_location("research_evaluate", EVAL_DIR / "evaluate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    import pandas as pd
    from sklearn.model_selection import TimeSeriesSplit
    import sklearn

    ev = load_evaluate_module()
    if importlib.metadata.version("scikit-learn") != sklearn.__version__:
        raise ValueError("version metadata mismatch")

    root, out = args.lean_source.resolve(), args.out.resolve()
    if out.exists():
        raise ValueError("use a fresh output directory")
    out.mkdir(parents=True, mode=0o700)

    plan = json.loads((EVAL_DIR / "plan.json").read_text())
    plan_sha256 = digest(EVAL_DIR / "plan.json")
    if plan_sha256 != "b8d1beba6eddd0388957ca0d9e9c46ebfb2ca538f076419d5a8dcaaaf82be4a7":
        raise ValueError("plan.json is not the frozen file the receipt scored")

    input_receipt = ev.verify_inputs(root, plan["inputs"])
    panel, dates, auxiliary, counts = ev.load_panel(root, plan)
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    anchor = eligible[0]

    def episodes(indices):
        return [int(i) for i in indices if (i - anchor) % 5 == 0]

    def prefix(cutoff):
        size = next((i for i, d in enumerate(dates) if d >= cutoff), len(dates))
        return {s: rows[:size] for s, rows in panel.items()}

    cost = Decimal(plan["round_trip_cost_fraction"])
    candidates = plan["candidates"]
    frame = pd.DataFrame(
        {"session": [dates[i] for i in eligible]},
        index=pd.to_datetime([dates[i] for i in eligible]),
    )
    spec = plan["splitter"]
    # Matched arm c22: same 252/63/6 shape, expressed with scikit-learn's own
    # TimeSeriesSplit(gap=...) purge instead of skfolio's WalkForward. TimeSeriesSplit
    # has no reduce_test; n_splits is chosen so the fixed 63-session test windows tile
    # the eligible span from the end, the closest native equivalent to WalkForward's
    # reduce_test=True behavior at the tail.
    n_samples = len(frame)
    train_size, test_size, purge = spec["train_size"], spec["test_size"], spec["purged_size"]
    n_splits = (n_samples - train_size - purge) // test_size
    if n_splits < 1:
        raise ValueError("not enough eligible sessions for any TimeSeriesSplit fold")
    splitter = TimeSeriesSplit(n_splits=n_splits, max_train_size=train_size, test_size=test_size, gap=purge)

    development_panel = prefix(plan["reserved_start"])
    folds = []
    all_rows = []

    def evaluate_fold(name, train, test, eval_panel):
        cutoff = dates[int(test[0])]
        training_panel = prefix(cutoff)
        training = [ev.label(training_panel, i, c, cost) for i in episodes(train) for c in candidates]
        if any(r["status"] != "observed" for r in training):
            raise ValueError("incomplete training label")
        selection = ev.choose(training, plan["selection_candidates"], cutoff)
        selection.update({
            "id": name,
            "train_first": dates[int(train[0])], "train_last": dates[int(train[-1])],
            "test_first": cutoff, "test_last": dates[int(test[-1])],
            "train_sessions": len(train), "test_sessions": len(test),
        })
        evaluation = [ev.label(eval_panel, i, c, cost) for i in episodes(test) for c in candidates]
        for phase, records in [("train", training), ("evaluation", evaluation)]:
            all_rows.extend(dict(r, fold=name, phase=phase) for r in records)
        summary = ev.summaries(evaluation, candidates)
        selected = summary[selection["chosen"]]
        return dict(selection, all_candidates=summary, selected=selected)

    fold_specs = list(splitter.split(frame))
    for j, (train, test) in enumerate(fold_specs):
        folds.append(evaluate_fold(
            "sklearn-development-" + str(j + 1),
            [eligible[int(i)] for i in train],
            [eligible[int(i)] for i in test],
            development_panel,
        ))

    reserved_train = eligible[-(train_size + purge):-purge]
    heldout = evaluate_fold("sklearn-reserved-2021q1", reserved_train, reserved, panel)

    unchanged = ev.verify_inputs(root, plan["inputs"]) == input_receipt
    result = {
        "kind": "sklearn-timeseriessplit-matched-arm-c22",
        "sklearn_version": sklearn.__version__,
        "splitter_params": {"n_splits": n_splits, "max_train_size": train_size, "test_size": test_size, "gap": purge},
        "plan_sha256": plan_sha256,
        "development_fold_count": len(folds),
        "ledger_records": len(all_rows),
        "reserved": heldout,
        "inputs_unchanged": unchanged,
    }
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "development_fold_count": len(folds),
        "ledger_records": len(all_rows),
        "reserved_selection": heldout["chosen"],
        "reserved_selected_metrics": heldout["selected"],
        "reserved_all_candidates": heldout["all_candidates"],
        "inputs_unchanged": unchanged,
    }, indent=2))


if __name__ == "__main__":
    main()
