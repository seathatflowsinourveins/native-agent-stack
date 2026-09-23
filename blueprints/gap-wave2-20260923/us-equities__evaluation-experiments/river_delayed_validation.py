"""Gap 7: river 0.26.1 progressive validation with delayed labels on retained LEAN SPY daily data.

Usage: river_delayed_validation.py REPO LEAN_SOURCE > validation-report.json
Label: sign of open[t+6]/open[t+1]-1 (research-evaluation/plan.json label), known at open t+6.
Features at close t: trailing close returns over 1, 5 and 20 sessions.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import river
from river import base, compose, dummy, evaluate, linear_model, metrics, preprocessing

repo, lean = Path(sys.argv[1]), Path(sys.argv[2])
plan = json.loads((repo / "blueprints/us-equities/research-evaluation/plan.json").read_text())
NAME = "Data/equity/usa/daily/spy.zip"
raw = (lean / NAME).read_bytes()
if hashlib.sha256(raw).hexdigest() != plan["inputs"][NAME]:
    raise SystemExit("input hash mismatch")  # verified before parsing
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    text = z.read(z.namelist()[0]).decode()
rows = []
for r in csv.reader(io.StringIO(text)):
    day = dt.datetime.strptime(r[0], "%Y%m%d %H:%M")
    if plan["data_start"] <= day.date().isoformat() <= plan["reserved_end"]:
        rows.append({"date": day, "open": int(r[1]) / 10000, "close": int(r[4]) / 10000})


def stream():
    for t in range(20, len(rows) - 6):
        c = rows[t]["close"]
        x = {"date": rows[t]["date"], "label_at": rows[t + 6]["date"],
             "ret1": c / rows[t - 1]["close"] - 1, "ret5": c / rows[t - 5]["close"] - 1,
             "ret20": c / rows[t - 20]["close"] - 1}
        yield x, rows[t + 6]["open"] / rows[t + 1]["open"] - 1 > 0


class CausalityProbe(base.Classifier):
    """Wraps a classifier; records any label learned before its label_at has been reached.

    Detection: every learned (label_at) must be <= the date of the next question asked.
    """
    def __init__(self, inner):
        self.inner, self.pending, self.violations, self.learned = inner, [], 0, 0

    def predict_one(self, x):
        self._check(x["date"]); return self.inner.predict_one(x)

    def predict_proba_one(self, x):
        self._check(x["date"]); return self.inner.predict_proba_one(x)

    def _check(self, now):
        self.violations += sum(label_at > now for label_at in self.pending); self.pending = []

    def learn_one(self, x, y):
        self.learned += 1; self.pending.append(x["label_at"]); self.inner.learn_one(x, y)


def model(kind):
    select = compose.Select("ret1", "ret5", "ret20")
    if kind == "logistic":
        return select | preprocessing.StandardScaler() | linear_model.LogisticRegression()
    return dummy.PriorClassifier()


def run(kind, delay):
    probe = CausalityProbe(model(kind))
    metric = metrics.Accuracy() + metrics.LogLoss()
    checkpoints = []
    # With no delay river's fast path needs moment=None too (standard online validation).
    moment = "date" if delay is not None else None
    for cp in evaluate.iter_progressive_val_score(stream(), probe, metric, moment=moment, delay=delay, step=250):
        checkpoints.append({"step": cp["Step"], "Accuracy": metric[0].get(), "LogLoss": metric[1].get()})
    return {"model": kind, "delay": delay_name[id(delay)], "final": {"Accuracy": metric[0].get(), "LogLoss": metric[1].get()},
            "labels_learned": probe.learned, "causality_violations": probe.violations, "checkpoints": checkpoints}


label_delay = lambda x, _y: x["label_at"] - x["date"]
delay_name = {id(label_delay): "label_at - date (t+6 open)", id(None): "None (immediate standard online validation)"}
samples = sum(1 for _ in stream())
positives = sum(y for _, y in stream())
report = {"kind": "river_progressive_validation_report", "river": river.__version__,
          "input": {"path": NAME, "sha256": plan["inputs"][NAME], "hash_verified_before_parse": True,
                    "sessions": len(rows), "first": rows[0]["date"].date().isoformat(), "last": rows[-1]["date"].date().isoformat()},
          "stream": {"samples": samples, "positive_labels": positives, "features": ["ret1", "ret5", "ret20"],
                     "label": "open[t+6]/open[t+1]-1 > 0", "moment": "session date t", "step": 250},
          "runs": [run("logistic", label_delay), run("logistic", None), run("prior", label_delay)],
          "probe_detection": "CausalityProbe counts labels whose label_at is later than the next question's date; the immediate run is the positive control."}
print(json.dumps(report, indent=1, default=str))
