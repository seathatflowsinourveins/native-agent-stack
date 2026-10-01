#!/usr/bin/env python3
"""Exploratory X arms (PREREGISTRATION.md A15): a cross-encoder stage over an existing arm's top 50.

Reported, never decided: no memory system accepts these models as shipped, so X is outside every Holm family.
Each reranker runs as its model card documents it, through Sentence Transformers' CrossEncoder, in BF16 on CUDA,
from the Hugging Face cache at the revision pinned in pins.json (offline):

- cross-encoder/ettin-reranker-400m-v1: CrossEncoder(model, model_kwargs={"dtype": bfloat16, "attn_implementation":
  ...}); predict((query, passage) pairs) returns raw scores (https://huggingface.co/cross-encoder/ettin-reranker-400m-v1).
- IAAR-Shanghai/MemReranker-4B: CrossEncoder(model, model_kwargs={"torch_dtype": bfloat16, ...}); default prompt
  "query" (https://huggingface.co/IAAR-Shanghai/MemReranker-4B).
- Qwen/Qwen3-Reranker-4B: CrossEncoder(model); default prompt "query"; raw logit differences
  (https://huggingface.co/Qwen/Qwen3-Reranker-4B).
- KaLM-Embedding/KaLM-Reranker-V1-Small: CrossEncoder(model, trust_remote_code=True, model_kwargs={"dtype":
  bfloat16, "chunk_size": 4}); default output P(yes) (https://huggingface.co/KaLM-Embedding/KaLM-Reranker-V1-Small).

Every card's default prompt is kept. The passage is the whole dated session ("[role] content" per turn, as the
agentmemory arms store it) and every reranker sees at most 4,096 passage tokens, the lane's input cap (KaLM's
default document cap, 1,024, is raised to it). The query is the question text. The top 50 of the base arm are
reordered by score; ties keep the base order. Rows follow the harness format, plus `base`, `reranker` and
`revision`, in <out>/x-<reranker>.jsonl; reruns resume by question id.

usage: rerank_stage.py --reranker {ettin-400m,memreranker-4b,qwen3-reranker-4b,kalm-small} --base ARM|auto
                       --results DIR [--out DIR] [--ids ...] [--limit N] [--batch-tokens 32768]
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from lme_harness import DATA, MANIFEST, MAX_RANK, dated, score, sessions_of

PINS = json.loads(Path(__file__).with_name("pins.json").read_text())
RERANKERS: dict[str, dict[str, Any]] = {
    "ettin-400m": {"repo": "cross-encoder/ettin-reranker-400m-v1", "kwargs": {}, "model_kwargs": {"attn_implementation": "sdpa"}},
    "memreranker-4b": {"repo": "IAAR-Shanghai/MemReranker-4B", "kwargs": {}, "model_kwargs": {}},
    "qwen3-reranker-4b": {"repo": "Qwen/Qwen3-Reranker-4B", "kwargs": {}, "model_kwargs": {}},
    "kalm-small": {"repo": "KaLM-Embedding/KaLM-Reranker-V1-Small", "kwargs": {"trust_remote_code": True},
                   "model_kwargs": {"chunk_size": 4}},
}
PASSAGE_TOKENS = 4096
EXCLUDED_BASES = ("A1", "x-", "dense-qwen3-bf16", "pooled-", "m1-")  # oracles, other X arms, the G0 diagnostic and
# the A16 diagnostics (pooled-store runs, M1): the base is a decision-capable arm


def revision_of(repo: str) -> str:
    return next(v["revision"] for k, v in PINS["hf_models"].items() if k.split("@")[0] == repo and "X (" in v["role"])


def best_arm(results: Path, full_ids: list[str]) -> str:
    """The arm with the highest full-track recall_all@5 among the complete arms without errors (A15: 'the best system')."""
    best, best_score = None, -1.0
    for p in sorted(results.glob("*.jsonl")):
        if p.stem.startswith(EXCLUDED_BASES) or p.stem.endswith("-fill"):
            continue
        rows = {json.loads(line)["question_id"]: json.loads(line) for line in p.open()}
        if any(qid not in rows for qid in full_ids) or any(rows[qid].get("error") for qid in full_ids):
            continue
        mean = sum(rows[qid]["metrics"]["full"]["recall_all@5"] for qid in full_ids) / len(full_ids)
        if mean > best_score:
            best, best_score = p.stem, mean
    if best is None:
        sys.exit(f"no complete, error-free arm in {results}")
    return best


def passage(s: dict) -> str:
    return dated(s, "\n\n".join(f"[{t['role']}] {t['content']}" for t in s["turns"]))


def rerank_order(scores: list[float], base: list[int]) -> list[int]:
    """Highest score first; ties keep the base order."""
    return [base[i] for i in sorted(range(len(base)), key=lambda i: (-scores[i], i))]


def batches(pairs: list[tuple], budget: int) -> list[list[int]]:
    """Length-sorted batches of pair indices whose padded size (rows x longest, estimated at 3 characters a token,
    capped at the passage cap) stays within the budget."""
    order = sorted(range(len(pairs)), key=lambda i: -len(pairs[i][1]))
    out, current = [], []
    for i in order:
        longest = min(len(pairs[current[0]][1]) // 3 if current else len(pairs[i][1]) // 3, PASSAGE_TOKENS) + 64
        if current and (len(current) + 1) * longest > budget:
            out.append(current)
            current = []
        current.append(i)
    if current:
        out.append(current)
    return out


def load(name: str):
    import torch
    from sentence_transformers import CrossEncoder
    spec = RERANKERS[name]
    model = CrossEncoder(spec["repo"], revision=revision_of(spec["repo"]), device="cuda" if torch.cuda.is_available() else "cpu",
                         local_files_only=True, max_length=PASSAGE_TOKENS,
                         model_kwargs={"dtype": torch.bfloat16} | spec["model_kwargs"], **spec["kwargs"])
    if name == "kalm-small":
        model[0].document_max_length = PASSAGE_TOKENS
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reranker", required=True, choices=sorted(RERANKERS))
    ap.add_argument("--base", default="auto")
    ap.add_argument("--results", required=True, help="the directory holding the base arm's rows")
    ap.add_argument("--out", help="where x-<reranker>.jsonl goes (default: --results)")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-tokens", type=int, default=32768)
    a = ap.parse_args()
    import torch
    manifest = json.loads(MANIFEST.read_text())
    full_ids = manifest["full_session_track"]
    results = Path(a.results)
    base = best_arm(results, full_ids) if a.base == "auto" else a.base
    base_rows = {json.loads(line)["question_id"]: json.loads(line) for line in (results / f"{base}.jsonl").open()}
    questions = [q for q in json.loads(DATA.read_text()) if q["question_id"] in set(full_ids)]
    if a.ids:
        questions = [q for q in questions if q["question_id"] in set(a.ids)]
    if a.limit:
        questions = questions[:a.limit]
    arm = f"x-{a.reranker}"
    out = Path(a.out or results) / f"{arm}.jsonl"
    done = {json.loads(line)["question_id"] for line in out.open()} if out.exists() else set()
    todo = [q for q in questions if q["question_id"] not in done]
    print(f"{arm} over {base}: {len(todo)} to run, {len(done)} already done", flush=True)
    model = load(a.reranker)
    revision = revision_of(RERANKERS[a.reranker]["repo"])
    for n, q in enumerate(todo, 1):
        by_pos = {s["pos"]: s for s in sessions_of(q)}
        top = base_rows[q["question_id"]]["ranking"][:MAX_RANK]
        pairs = [(q["question"], passage(by_pos[pos])) for pos in top]
        scores, err, t0 = [0.0] * len(pairs), None, time.perf_counter()
        try:
            for idx in batches(pairs, a.batch_tokens):
                chunk = [pairs[i] for i in idx]
                try:
                    got = model.predict(chunk, batch_size=len(chunk), show_progress_bar=False)
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    got = [s for pair in chunk for s in model.predict([pair], batch_size=1, show_progress_bar=False)]
                for i, s in zip(idx, got, strict=True):
                    scores[i] = float(s)
            ranking = rerank_order(scores, top)
        except Exception as e:  # noqa: BLE001 - recorded; the row keeps the base order
            err, ranking = f"{type(e).__name__}: {e}", top
        row = {"question_id": q["question_id"], "question_type": q["question_type"], "arm": arm, "base": base,
               "reranker": RERANKERS[a.reranker]["repo"], "revision": revision, "error": err, "attempts": 1,
               "latency_ms": (time.perf_counter() - t0) * 1000, "ranking": ranking, "metrics": score(q, ranking)}
        with out.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        if n % 25 == 0 or err:
            print(f"[{n}/{len(todo)}] {q['question_id']} err={err}", flush=True)
    print(f"{arm}: finished {len(todo)}", flush=True)


if __name__ == "__main__":
    main()
