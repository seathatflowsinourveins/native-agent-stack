"""Shared frozen-input loading for the portfolio-risk gap-wave-2 runners.

Reuses the unchanged research-evaluation evaluate.py loader (hash-verified LEAN inputs,
calendar and corporate-action checks) so every runner sees the same frozen panel.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVAL_DIR = ROOT / "blueprints/us-equities/research-evaluation"
PLAN_SHA256 = "b8d1beba6eddd0388957ca0d9e9c46ebfb2ca538f076419d5a8dcaaaf82be4a7"
LEAN_DEFAULT = Path(os.environ.get("LEAN_SOURCE") or Path.home() / ".local/share/codex-ecosystem/tools/lean-985ef30")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_evaluate():
    spec = importlib.util.spec_from_file_location("research_evaluate", EVAL_DIR / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_panel(lean_source=LEAN_DEFAULT):
    ev = load_evaluate()
    plan_path = EVAL_DIR / "plan.json"
    if digest(plan_path) != PLAN_SHA256:
        raise ValueError("plan.json is not the frozen file")
    plan = json.loads(plan_path.read_text())
    root = Path(lean_source).resolve()
    inputs = ev.verify_inputs(root, plan["inputs"])
    panel, dates, auxiliary, counts = ev.load_panel(root, plan)
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    return {"ev": ev, "plan": plan, "root": root, "inputs": inputs, "panel": panel, "dates": dates,
            "eligible": eligible, "reserved": reserved,
            "evaluate_sha256": digest(EVAL_DIR / "evaluate.py"), "plan_sha256": PLAN_SHA256}


def inputs_unchanged(frozen):
    return frozen["ev"].verify_inputs(frozen["root"], frozen["plan"]["inputs"]) == frozen["inputs"]


def price_frame(frozen, indices, field="close"):
    import pandas as pd
    dates, panel, assets = frozen["dates"], frozen["panel"], frozen["plan"]["assets"]
    idx = pd.to_datetime([dates[i] for i in indices])
    return pd.DataFrame({a: [float(panel[a][i][field]) for i in indices] for a in assets}, index=idx)


def dev_returns(frozen):
    from skfolio.preprocessing import prices_to_returns
    return prices_to_returns(price_frame(frozen, frozen["eligible"]))


def reserved_frames(frozen):
    """Reserved fit window (last 252 dev sessions before a 6-session exclusion) and 2021Q1 test window."""
    from skfolio.preprocessing import prices_to_returns
    spec = frozen["plan"]["splitter"]
    train_idx = frozen["eligible"][-(spec["train_size"] + spec["purged_size"]):-spec["purged_size"]]
    return (prices_to_returns(price_frame(frozen, train_idx)),
            prices_to_returns(price_frame(frozen, frozen["reserved"])), train_idx)


def walkforward(frozen):
    from skfolio.model_selection import WalkForward
    spec = frozen["plan"]["splitter"]
    return WalkForward(**{k: spec[k] for k in ["train_size", "test_size", "purged_size", "reduce_test"]})


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
