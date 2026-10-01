#!/usr/bin/env python3
"""First-line embedder evaluation: upstream mteb running LMEB's LongMemEval task (user directive, 2026-09-25).

Runs the pinned mteb release (2.21.8) unmodified: its model registry entry for each model (loader, prompts,
max sequence length and revision, which are the settings of the published leaderboard result), its
`LongMemEval` task (LMEB, dataset mteb/LongMemEval at 9dc1a8fd, main score nDCG@10, the mean over its six
subsets), and its own evaluator. The score is set next to the published leaderboard value from
embeddings-benchmark/results (pins.json "mteb.published"), so each row either reproduces the leaderboard or
shows by how much it does not. The in-system arms stay the basis of every system-level decision; this
evaluation decides nothing.

    mteb_lmeb.py --model REPO --out DIR [--batch-size 16] [--revision SHA]
    mteb_lmeb.py --summary --out DIR   # the table of every model's reproduction
    mteb_lmeb.py --dry-load            # load the task's data and report its size (setup: online, once; gates: offline)

Everything runs offline (HF_HUB_OFFLINE=1, HF_DATASETS_OFFLINE=1, TRANSFORMERS_OFFLINE=1) against the Hugging Face
cache that setup_velanext.sh filled and verified; setup loads the task once online, right after the verification,
so the datasets cache exists, and the gates check that it loads offline. The mteb result JSON stays in
DIR/mteb-cache; DIR/<model>.json is the lane's row.
"""
import argparse
import json
import sys
import time
from pathlib import Path

PINS = json.loads(Path(__file__).with_name("pins.json").read_text())
TASK = "LongMemEval"
TASK_REVISION = "9dc1a8fdcf9b5676f87c2cdccac021988f6ff5af"
ORDER = ["nvidia/Nemotron-3-Embed-8B-BF16", "nvidia/Nemotron-3-Embed-1B-BF16", "microsoft/harrier-oss-v1-0.6b",
         "Qwen/Qwen3-Embedding-4B", "Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-8B",
         "sentence-transformers/all-MiniLM-L6-v2"]


def slug(repo: str) -> str:
    return repo.replace("/", "__")


def subset_scores(scores: dict) -> dict:
    """{hf_subset: main_score} from an mteb TaskResult's `scores` (split -> list of score dicts)."""
    return {s.get("hf_subset", "default"): float(s["main_score"]) for s in scores.get("test", [])}


def row_for(repo: str, revision: str, subsets: dict, mteb_version: str, seconds: float) -> dict:
    published = PINS["mteb"]["published"].get(repo, {})
    ours = 100 * sum(subsets.values()) / len(subsets) if subsets else None
    return {"model": repo, "revision": revision, "task": TASK, "task_dataset_revision": TASK_REVISION,
            "mteb_version": mteb_version, "subsets": subsets, "score": ours,
            "published": published.get("score"), "published_revision": published.get("revision"),
            "published_url": published.get("url"),
            "delta": None if ours is None or published.get("score") is None else round(ours - published["score"], 2),
            "evaluation_s": round(seconds)}


def summary(out: Path) -> str:
    rows = [json.loads(p.read_text()) for p in sorted(out.glob("*.json")) if not p.name.startswith("_")]
    by_model = {r["model"]: r for r in rows}
    lines = ["| model | revision | LMEB LongMemEval nDCG@10 (ours) | published | Δ | mteb | time |", "|---|---|---|---|---|---|---|"]
    for repo in ORDER:
        r = by_model.get(repo)
        if r is None:
            pub = PINS["mteb"]["published"][repo]["score"]
            lines.append(f"| {repo} | – | not run | {pub:.2f} | – | – | – |")
            continue
        ours = "–" if r["score"] is None else f"{r['score']:.2f}"
        delta = "–" if r["delta"] is None else f"{r['delta']:+.2f}"
        lines.append(f"| {repo} | {r['revision'][:10]} | {ours} | {r['published']:.2f} | {delta} | {r['mteb_version']} | "
                     f"{r['evaluation_s']} s |")
    return "\n".join(lines)


def dry_load(get_task=None) -> dict:
    """The pinned task's data, loaded through mteb itself (review pins P7): the revision and the size of each split."""
    if get_task is None:
        import mteb
        get_task = mteb.get_task
    task = get_task(TASK)
    if task.metadata.dataset["revision"] != TASK_REVISION:
        raise SystemExit(f"{TASK} is at {task.metadata.dataset['revision']}, not {TASK_REVISION}")
    task.load_data()
    sizes = {}
    for name in ("corpus", "queries", "relevant_docs"):
        data = getattr(task, name, None)
        if data is not None:
            try:
                sizes[name] = len(data)
            except TypeError:
                sizes[name] = None
    return {"task": TASK, "revision": TASK_REVISION, "loaded": True, "sizes": sizes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=ORDER)
    ap.add_argument("--revision", help="default: mteb's registry revision (the published result's)")
    ap.add_argument("--out")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--dry-load", action="store_true", help="load the pinned task's data only, and report its size")
    a = ap.parse_args()
    if a.dry_load:
        print(json.dumps(dry_load()))
        return
    if not a.out:
        sys.exit("--out is required")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.summary:
        text = summary(out)
        (out / "_summary.md").write_text(text + "\n")
        print(text)
        return
    if not a.model:
        sys.exit("--model is required")
    import mteb
    task = mteb.get_task(TASK)
    if task.metadata.dataset["revision"] != TASK_REVISION:
        sys.exit(f"mteb {mteb.__version__} ships {TASK} at {task.metadata.dataset['revision']}, not {TASK_REVISION}")
    meta = mteb.get_model_meta(a.model)
    revision = a.revision or meta.revision
    model = mteb.get_model(a.model, revision=revision)
    t0 = time.perf_counter()
    result = mteb.evaluate(model, tasks=[task], encode_kwargs={"batch_size": a.batch_size},
                           cache=mteb.ResultCache(out / "mteb-cache"), overwrite_strategy="only-missing")
    task_result = result.task_results[0]
    row = row_for(a.model, revision, subset_scores(task_result.scores), mteb.__version__, time.perf_counter() - t0)
    (out / f"{slug(a.model)}.json").write_text(json.dumps(row, indent=1))
    print(json.dumps(row, indent=1), flush=True)


if __name__ == "__main__":
    main()
