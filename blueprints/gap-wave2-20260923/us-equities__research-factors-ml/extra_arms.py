#!/usr/bin/env python3
"""Fix round 4 (gap 5): the six remaining candidates on the frozen SPY/QQQ/IWM data.

--arm export | haystack | docling | ray | timesfm | st | qlib
`export` runs in the plan venv and writes frozen_ohlcv.json via fcmp.load_ohlcv (which
cross-checks evaluate.load_panel after evaluate.verify_inputs). Every other arm refuses
to run unless the export's sha256 equals --export-sha256. Each arm prints one JSON
object with pass/fail fields as preregistered in preregistration.json fix round 4.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EVAL_DIR = REPO / "blueprints/us-equities/research-evaluation"
TIMESFM = ("google/timesfm-2.5-200m-pytorch", "1d952420fba87f3c6dee4f240de0f1a0fbc790e3")
MINILM = ("sentence-transformers/all-MiniLM-L6-v2", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41")
FCMP_FORECASTS_SHA = "8829d98c059f377713882ea56cec4b27c0ff5bd0e0b96087c95ca741edeb9d14"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ver(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def load(a):
    got = sha(a.export)
    if got != a.export_sha256:
        raise SystemExit("export sha256 mismatch: " + got)
    return json.loads(a.export.read_text())


def month_docs(data):
    """One document per (asset, month) 2015-01..2020-12."""
    docs = []
    for asset in data["assets"]:
        rows = data["ohlcv"][asset]
        last = {}
        for r in rows:
            last[r["date"][:7]] = r["close"]
        months = sorted(last)
        for prev, m in zip(months, months[1:]):
            if "2015-01" <= m <= "2020-12":
                ret = 100 * (last[m] / last[prev] - 1)
                docs.append({"asset": asset, "month": m,
                             "text": "%s %s: monthly close-to-close return %+.2f%%, last close %.2f USD." % (asset, m, ret, last[m])})
    return docs


def momentum_decision(close, dates, t, lookback):
    best, pick = 0.0, "cash"
    for asset in sorted(close):
        m = close[asset][t] / close[asset][t - lookback] - 1
        if m > best:
            best, pick = m, asset
    return pick


def ray_picks(dates, data):
    eligible = [i for i, d in enumerate(dates) if data["eligible_start"] <= d <= data["development_end"]]
    decisions = [t for t in eligible if (t - eligible[0]) % 5 == 0]
    return decisions[::len(decisions) // 40][:40]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True)
    p.add_argument("--lean-source", type=Path)
    p.add_argument("--export", type=Path, required=True)
    p.add_argument("--export-sha256")
    p.add_argument("--tmp", type=Path)
    p.add_argument("--fcmp-forecasts", type=Path)
    p.add_argument("--device", default="cpu")
    p.add_argument("--expected", type=Path)
    p.add_argument("--expected-sha256")
    a = p.parse_args()
    out = {"arm": a.arm}

    if a.arm == "export":
        sys.path.insert(0, str(EVAL_DIR))
        sys.path.insert(0, str(HERE))
        import evaluate as ev
        import fcmp
        plan = json.loads((EVAL_DIR / "plan.json").read_text())
        root = a.lean_source.resolve()
        ev.verify_inputs(root, plan["inputs"])
        panel, dates, _x, _y = ev.load_panel(root, plan)
        ohlcv = fcmp.load_ohlcv(root, plan, panel)
        a.export.write_text(json.dumps({"plan_sha256": ev.digest(EVAL_DIR / "plan.json"), "assets": plan["assets"],
                                        "eligible_start": plan["eligible_start"], "development_end": plan["development_end"],
                                        "dates": dates, "ohlcv": ohlcv}, sort_keys=True) + "\n")
        out.update(sessions=len(dates), first=dates[0], last=dates[-1], export_sha256=sha(a.export))
        print(json.dumps(out, sort_keys=True))
        return

    if a.arm == "expected":
        # Fix round 5: momentum20 decisions from evaluate.weights (Decimal), independent of momentum_decision().
        sys.path.insert(0, str(EVAL_DIR))
        import evaluate as ev
        plan = json.loads((EVAL_DIR / "plan.json").read_text())
        root = a.lean_source.resolve()
        ev.verify_inputs(root, plan["inputs"])
        panel, dates, _x, _y = ev.load_panel(root, plan)
        data = load(a)
        if data["dates"] != dates:
            raise SystemExit("export dates differ from evaluate.load_panel")
        exp = {}
        for t in ray_picks(dates, data):
            w = ev.weights(panel, t, "momentum20")
            exp[dates[t]] = next(iter(w)) if w else "cash"
        a.expected.write_text(json.dumps(exp, sort_keys=True) + "\n")
        out.update(dates=len(exp), expected_sha256=sha(a.expected), distribution={k: list(exp.values()).count(k) for k in sorted(set(exp.values()))})
        print(json.dumps(out, sort_keys=True))
        return

    data = load(a)
    out["export_sha256"] = a.export_sha256
    dates = data["dates"]
    close = {k: [r["close"] for r in v] for k, v in data["ohlcv"].items()}

    if a.arm == "haystack":
        from haystack import Document, Pipeline
        from haystack.document_stores.in_memory import InMemoryDocumentStore
        from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
        docs = month_docs(data)
        store = InMemoryDocumentStore()
        store.write_documents([Document(content=d["text"], meta={"asset": d["asset"], "month": d["month"]}) for d in docs])
        pipe = Pipeline()
        pipe.add_component("retriever", InMemoryBM25Retriever(document_store=store, top_k=1))
        hits, misses = 0, []
        for d in docs:
            top = pipe.run({"retriever": {"query": d["asset"] + " " + d["month"]}})["retriever"]["documents"][0]
            if (top.meta["asset"], top.meta["month"]) == (d["asset"], d["month"]):
                hits += 1
            else:
                misses.append([d["asset"] + " " + d["month"], top.meta["asset"] + " " + top.meta["month"]])
        neg = pipe.run({"retriever": {"query": "SPY 1999-01"}})["retriever"]["documents"][0]
        # Fix round 5: permuted-meta control; each document carries the next document's key.
        store_p = InMemoryDocumentStore()
        store_p.write_documents([Document(content=d["text"], meta={"asset": docs[(i + 1) % len(docs)]["asset"], "month": docs[(i + 1) % len(docs)]["month"]}) for i, d in enumerate(docs)])
        ret_p = InMemoryBM25Retriever(document_store=store_p, top_k=1)
        perm_hits = 0
        for d in docs:
            tp = ret_p.run(query=d["asset"] + " " + d["month"])["documents"][0]
            perm_hits += (tp.meta["asset"], tp.meta["month"]) == (d["asset"], d["month"])
        out["permuted_meta_control"] = {"top1_hits": perm_hits, "detects_failure": perm_hits <= 5}
        out.update(version=ver("haystack-ai"), documents=store.count_documents(), top1_hits=hits, queries=len(docs), misses=misses[:20],
                   negative_control={"query": "SPY 1999-01", "top1": neg.meta["asset"] + " " + neg.meta["month"],
                                     "detected_nonmatch": (neg.meta["asset"], neg.meta["month"]) != ("SPY", "1999-01")},
                   passed=hits == len(docs) and (neg.meta["asset"], neg.meta["month"]) != ("SPY", "1999-01"))

    elif a.arm == "docling":
        from docling.document_converter import DocumentConverter
        a.tmp.mkdir(parents=True, exist_ok=False)
        last = {}
        for d, c in zip(dates, close["SPY"]):
            last[d[:7]] = c
        months = sorted(last)
        rows = [["month", "close", "return_pct"]]
        for prev, m in zip(months, months[1:]):
            if m.startswith("2020-"):
                rows.append([m, "%.2f" % last[m], "%+.2f" % (100 * (last[m] / last[prev] - 1))])
        html = "<html><body><table>" + "".join(
            "<tr>" + "".join(("<th>%s</th>" if i == 0 else "<td>%s</td>") % v for v in r) + "</tr>" for i, r in enumerate(rows)) + "</table></body></html>"
        (a.tmp / "spy2020.html").write_text(html)
        (a.tmp / "spy2020.csv").write_text("\n".join(",".join(r) for r in rows) + "\n")
        conv = DocumentConverter()
        res = {}

        def compare(got, ref):
            return sum(1 for gr, rr in zip(got, ref) for g, r in zip(gr, rr) if g != r) + abs(len(got) - len(ref)) * 3

        for name in ("spy2020.html", "spy2020.csv"):
            doc = conv.convert(str(a.tmp / name)).document
            df = doc.tables[0].export_to_dataframe(doc=doc)
            got = [[str(c) for c in df.columns]] + [[str(v) for v in r] for r in df.itertuples(index=False)]
            perturbed = [r[:] for r in rows]
            perturbed[5][1] = "%.2f" % (float(perturbed[5][1]) + 0.01)
            res[name] = {"tables": len(doc.tables), "shape": [len(got), len(got[0]) if got else 0],
                         "mismatches": compare(got, rows), "negative_control_mismatches": compare(got, perturbed), "first_rows": got[:3]}
        out.update(version=ver("docling"), cells_per_format=len(rows) * 3, formats=res,
                   passed=all(v["mismatches"] == 0 and v["negative_control_mismatches"] == 1 and v["shape"] == [13, 3] for v in res.values()))

    elif a.arm == "ray":
        import socket
        import urllib.request
        import ray
        from ray import serve
        picks = ray_picks(dates, data)
        expected = {dates[t]: momentum_decision(close, dates, t, 20) for t in picks}
        ev_expected = None
        if a.expected:
            if sha(a.expected) != a.expected_sha256:
                raise SystemExit("expected sha256 mismatch")
            ev_expected = json.loads(a.expected.read_text())
        wrong = {dates[t]: momentum_decision(close, dates, t, 19) for t in picks}
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        ray.init(num_cpus=2, include_dashboard=False, _temp_dir=str(a.tmp), log_to_driver=False)
        try:
            serve.start(http_options={"host": "127.0.0.1", "port": port})

            @serve.deployment(num_replicas=1, ray_actor_options={"num_cpus": 1})
            class Momentum:
                def __init__(self, close, dates):
                    self.close, self.index = close, {d: i for i, d in enumerate(dates)}

                def decide(self, date, lookback=20):
                    return momentum_decision(self.close, None, self.index[date], lookback)

                async def __call__(self, request):
                    return {"decision": self.decide(request.query_params["date"])}

            handle = serve.run(Momentum.bind(close, dates), name="momentum", route_prefix="/momentum")
            got = {d: handle.decide.remote(d).result() for d in expected}
            probe = sorted(expected)[7]
            http = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/momentum?date=%s" % (port, probe), timeout=30).read())
            # Fix round 5: positive control for the cleanup probe; exact process-name match, so shells do not self-match.
            import subprocess
            out["running_process_counts"] = {n: len(subprocess.run(["pgrep", "-x", n], capture_output=True, text=True).stdout.split()) for n in ("raylet", "gcs_server")}
        finally:
            serve.shutdown()
            ray.shutdown()
        agree = sum(got[d] == expected[d] for d in expected)
        neg = sum(wrong[d] != expected[d] for d in expected)
        if ev_expected is not None:
            out["evaluate_weights_agree"] = sum(got[d] == ev_expected[d] for d in expected)
            out["helper_vs_evaluate_agree"] = sum(expected[d] == ev_expected[d] for d in expected)
            out["expected_sha256"] = a.expected_sha256
        out.update(version=ver("ray"), port=port, dates=len(expected), handle_agree=agree, http={"date": probe, "got": http["decision"], "expected": expected[probe]},
                   negative_control_lookback19_disagreements=neg, negative_control_can_detect=neg > 0,
                   picks_distribution={k: list(expected.values()).count(k) for k in sorted(set(expected.values()))},
                   passed=agree == len(expected) and http["decision"] == expected[probe])

    elif a.arm == "timesfm":
        import numpy as np
        import torch
        import timesfm
        if sha(a.fcmp_forecasts) != FCMP_FORECASTS_SHA:
            raise SystemExit("fcmp forecasts sha256 mismatch")
        rows = json.loads(a.fcmp_forecasts.read_text())
        index = {d: i for i, d in enumerate(dates)}
        torch.manual_seed(0)
        m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(TIMESFM[0], revision=TIMESFM[1])
        m.compile(timesfm.ForecastConfig(max_context=512, max_horizon=32, normalize_inputs=True))
        ctx, keys_ok = [], True
        for r in rows:
            t = index[r["decision"]]
            keys_ok &= dates[t + 5] == r["target"] and abs(math.log(close[r["asset"]][t + 5] / close[r["asset"]][t]) - r["r"]) < 1e-12
            ctx.append(np.array(close[r["asset"]][t - 251:t + 1], dtype=np.float32))
        point, _q = m.forecast(horizon=5, inputs=ctx)
        off_ok = True  # Fix round 5: offset-key control (decision index t+1) must fail the key/target check.
        for r in rows:
            t = index[r["decision"]] + 1
            off_ok &= dates[t + 5] == r["target"] and abs(math.log(close[r["asset"]][t + 5] / close[r["asset"]][t]) - r["r"]) < 1e-12
        out["offset_key_control"] = {"keys_and_targets_identical": bool(off_ok), "detects_failure": not off_ok}
        pred = np.log(point[:, 4].astype(np.float64)) - np.array([math.log(close[r["asset"]][index[r["decision"]]]) for r in rows])
        truth = np.array([r["r"] for r in rows])
        folds = sorted({r["fold"] for r in rows}, key=lambda f: (f.startswith("reserved"), int(f.split("-")[1]) if f.startswith("development") else 0))
        per = {}
        for mname, vec in (("timesfm_2p5", pred), ("naive", np.array([r["naive"] for r in rows])), ("chronos_bolt_small", np.array([r["chronos_bolt_small"] for r in rows]))):
            per[mname] = {f: float(np.mean(np.abs(vec[[i for i, r in enumerate(rows) if r["fold"] == f]] - truth[[i for i, r in enumerate(rows) if r["fold"] == f]]))) for f in folds}
        dev = [f for f in folds if f.startswith("development")]
        rng = np.random.default_rng(20260923)
        boot = rng.integers(0, len(dev), size=(10000, len(dev)))

        def interval(x, y):
            d = np.array([per[x][f] - per[y][f] for f in dev])
            lo, hi = np.percentile(d[boot].mean(axis=1), [2.5, 97.5])
            return {"mean_diff": float(d.mean()), "ci95": [float(lo), float(hi)], "folds_a_better": int((d < 0).sum()),
                    "verdict": "a_better" if hi < 0 else "b_better" if lo > 0 else "no_difference_resolved"}

        out.update(version=ver("timesfm"), torch=ver("torch"), device=str(next(m.model.parameters()).device) if hasattr(m, "model") else None,
                   pin=TIMESFM, tasks=len(rows), keys_and_targets_identical=bool(keys_ok), all_finite=bool(np.isfinite(pred).all()),
                   per_fold_mae=per, dev_mean_fold_mae={k: float(np.mean([v[f] for f in dev])) for k, v in per.items()},
                   reserved_mae={k: v["reserved-2021q1"] for k, v in per.items()},
                   pairwise_dev_bootstrap={"timesfm_2p5_vs_naive": interval("timesfm_2p5", "naive"),
                                           "timesfm_2p5_vs_chronos_bolt_small": interval("timesfm_2p5", "chronos_bolt_small")},
                   forecasts_sha256=hashlib.sha256(json.dumps([round(float(x), 12) for x in pred]).encode()).hexdigest(),
                   passed=bool(keys_ok) and bool(np.isfinite(pred).all()) and len(rows) == 783)

    elif a.arm == "st":
        import numpy as np
        from sentence_transformers import SentenceTransformer
        docs = month_docs(data)
        model = SentenceTransformer(MINILM[0], revision=MINILM[1], device=a.device)
        e1 = model.encode([d["text"] for d in docs], normalize_embeddings=True, convert_to_numpy=True)
        e2 = model.encode([d["text"] for d in docs], normalize_embeddings=True, convert_to_numpy=True)
        q = model.encode([d["asset"] + " " + d["month"] for d in docs], normalize_embeddings=True, convert_to_numpy=True)
        # Fix round 5: perturbed-text control; changing the last-close digits must move the embeddings.
        e3 = model.encode([d["text"].replace(" USD.", "9 USD.") for d in docs], normalize_embeddings=True, convert_to_numpy=True)
        out["perturbed_text_control"] = {"max_abs_diff": float(np.abs(e1 - e3).max()), "detects_failure": float(np.abs(e1 - e3).max()) > 1e-5}
        top = (q @ e1.T).argmax(axis=1)
        hits = int(sum(int(top[i]) == i for i in range(len(docs))))
        out.update(version=ver("sentence-transformers"), pin=MINILM, device=a.device, dim=int(e1.shape[1]), documents=len(docs),
                   repeat_max_abs_diff=float(np.abs(e1 - e2).max()), top1_key_accuracy=hits / len(docs), top1_hits=hits,
                   passed=int(e1.shape[1]) == 384 and float(np.abs(e1 - e2).max()) <= 1e-5)

    elif a.arm == "qlib":
        import subprocess
        import numpy as np
        import pandas as pd
        a.tmp.mkdir(parents=True, exist_ok=False)
        csv_dir, qdir = a.tmp / "csv", a.tmp / "qlib"
        csv_dir.mkdir()
        for asset, rows in data["ohlcv"].items():
            pd.DataFrame(rows).assign(symbol=asset).to_csv(csv_dir / (asset + ".csv"), index=False)
        dump = subprocess.run([sys.executable, str(a.tmp.parent / "dump_bin.py"), "dump_all", "--data_path", str(csv_dir), "--qlib_dir", str(qdir),
                               "--include_fields", "open,high,low,close,volume", "--date_field_name", "date", "--symbol_field_name", "symbol",
                               "--max_workers", "1"], capture_output=True, text=True)
        if dump.returncode:
            raise SystemExit("dump_bin failed: " + dump.stderr[-2000:])
        import qlib
        from qlib.data import D
        qlib.init(provider_uri=str(qdir), region="us", expression_cache=None, dataset_cache=None, kernels=1)
        feats = D.features(data["assets"], ["$close", "$close/Ref($close,20)-1"], start_time=data["eligible_start"], end_time=data["development_end"], freq="day")
        feats.columns = ["close", "mom20"]
        n, bad, bad_shift, checked, bad_strict, bad_shift_strict = 0, 0, 0, 0, 0, 0
        for asset in data["assets"]:
            s = pd.Series(close[asset], index=pd.to_datetime(dates))
            ref = pd.DataFrame({"close": s, "mom20": s / s.shift(20) - 1}).loc[data["eligible_start"]:data["development_end"]]
            code = [c for c in feats.index.get_level_values(0).unique() if c.upper() == asset][0]
            got = feats.xs(code, level=0).reindex(ref.index)
            for col in ("close", "mom20"):
                g, r = got[col].to_numpy(dtype=float), ref[col].to_numpy(dtype=float)
                sh = ref[col].shift(1).to_numpy(dtype=float)
                checked += len(r)
                bad += int((~np.isclose(g, r, rtol=1e-5, atol=1e-6 if col == "mom20" else 0)).sum())
                bad_shift += int((~np.isclose(g[1:], sh[1:], rtol=1e-5, atol=1e-6 if col == "mom20" else 0)).sum())
                # Fix round 5: the preregistered rule, rtol=1e-5 with atol=0, is the criterion of record.
                bad_strict += int((~np.isclose(g, r, rtol=1e-5, atol=0)).sum())
                bad_shift_strict += int((~np.isclose(g[1:], sh[1:], rtol=1e-5, atol=0)).sum())
            n += len(ref)
        out.update(version=ver("pyqlib"), python=sys.version.split()[0], dump_bin_sha256=sha(a.tmp.parent / "dump_bin.py"), rows=n, values_checked=checked,
                   mismatches=bad, negative_control_shift1_mismatches=bad_shift, codes=[str(c) for c in feats.index.get_level_values(0).unique()],
                   mismatches_rtol_only=bad_strict, negative_control_shift1_mismatches_rtol_only=bad_shift_strict,
                   passed_atol_deviation=bad == 0 and bad_shift > 0 and n > 0,
                   passed=bad_strict == 0 and bad_shift_strict > 0 and n > 0)
    else:
        raise SystemExit("unknown arm")
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
