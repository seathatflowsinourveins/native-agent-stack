"""Preregistered analysis for the LongMemEval-S retrieval tier (PREREGISTRATION.md, amendments A1-A16.3).

Reads results/<arm>.jsonl from lme_harness.py and the official runner's logs (A0 flat-bm25, A1 oracle),
restricts every arm to the frozen eligible manifest, and reports both tracks with cluster-bootstrap CIs,
cluster sign-flip randomization tests and Holm correction.

v4 implements A15.2's error control and precedence:
- error control per family (the C3 and C4 families at 0.0333 each, A16's at 0.0167) and the declared bound per
  production setting (A16.2, corrected in A16.3): layer <= 0.05 (A15 candidates <= 0.0333 through the
  intersection-union test, A16 candidates <= 0.0167); ai-memory configuration <= 0.0667 (C1 and C2 against C3 in
  the C3 family, F against C4 in the C4 family); reranker <= 0.0667 (on/off in the C3 family, an H swap in the C4
  family, only while the reranker stays on); the union bound over all decisions is 0.0833, the sum of the three
  families' alpha.
  The families are: the C3 family (the original members plus E1-E3 and G1-G3) and the C4 family (the layer
  candidates plus F1-F3 and H1-H3). A layer candidate must pass both (the A14 intersection-union test);
  A13's p = 1 treatment of unfinished members applies within each fixed family;
- precedence: the reranker (C3 against C4, production the status quo) first; H only while the reranker stays
  on, and F likewise (both wait while the reranker decision is pending); F (production with only the embedder
  changed) against C4; the layer against both families. C5 and C6 are C3-family diagnostics (A15.2); C1 and C2
  are decided against C3 as registered in A2 and A14 (A16.2), stating that they run with the reranker off.
  Among passing candidates for one setting the largest point estimate is
  chosen, reported with the paired CIs between them and labelled as selected (biased upward). The layer is one
  setting across A15 and A16: every passing layer candidate is compared on one question set (K1's subset when
  K1 passes);
- A12's 5% fallback rule on every C4-referenced decision (C4's rate on the questions compared, so on K1's subset
  for K1), on the H arms' own reranking (A15.2) and on each F arm's own reranking (A16.2);
- descriptive only: E against F at the same embedder, every arm against A0 (the preregistered baseline), G0, the
  F cache-fill passes and the X arms; an arm not named in a family before its first run makes no decision;
- A16: the memory-system family (D2h, M2 MemPalace, K1 Hindsight), Holm at alpha = 0.0167; each member is a layer
  candidate and must pass against both C3 and C4 (the intersection-union p is the larger of its two p-values).
  K1 and its references are compared on K1's preregistered subset (k1-subset.json), where C3, C4 and D2 are also
  reported. M1 (MemPalace's own raw-mode bench, rescored), the vendor harnesses and the pooled-store runs are
  diagnostics. A passing system also needs the catalog's memory-lane acceptance before adoption;
- the Mac results are descriptive; decisions are confirmatory only with --confirmatory (VelaNext);
- a production switch to a new embedder also needs the deployability gate (lane_tools.py deployability).

Review fixes (2026-09-25): an absent or incomplete oracle blocks every decision and recall_any is checked at
every k; an arm with env errors, or with more than 1% infra or unclassified error rows, is not finished and is
labelled invalid in every table; duplicate question ids are refused (the official logs too); the reproducibility
note states counts only; labels state requirements, not outcomes; --final never changes the fixed families, but
once the queue has finished it closes a decision still waiting on an unfinished member (held at p = 1) as final;
--confirmatory requires --platform VelaNext and the passed gates (oracle ceilings and v4 = v3, --gates DIR).

usage: python lme_summarize.py [--incumbent aimem-qwen3] [--results DIR] [--official-logs DIR] [--platform NAME]
                               [--confirmatory --gates DIR] [--final] [--replication DIR] [--gpu-logs DIR]
                               [--oracle-gate] [--out report]
"""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from lme_harness import DATA, HERE, KS, MANIFEST, score

PRIMARY = "recall_all@5"
SECONDARY = ["ndcg_any@5", "recall_all@10", "ndcg_any@10", "recall_any@5", "recall_any@10"]
SEED = 20260924
BOOT = 10_000
PERM = 100_000
OFFICIAL_LOGS = {"A0-official-bm25": "longmemeval_s_cleaned.json_retrievallog_session_flat-bm25",
                 "A1-official-oracle": "longmemeval_s_cleaned.json_retrievallog_session_oracle"}
PRODUCTION = "aimem-qwen3-rerank"  # A14: production reranks, so the production configuration is C4
RERANK_KEYS = ("rerank_timeouts", "rerank_failures", "rerank_invalid")
TRACK_ONLY = {"A1-official-oracle": "official", "A1b-full-oracle": "full"}
CEILINGS = {("A1-official-oracle", "official"): 416 / 419, ("A1b-full-oracle", "full"): 467 / 470}
A15_E = ["am-nemotron-8b", "am-nemotron-1b", "am-harrier-0.6b"]
A15_F = ["aimem-nemotron-8b", "aimem-nemotron-1b", "aimem-harrier-0.6b"]
A15_G = ["dense-nemotron-8b", "dense-nemotron-1b", "dense-harrier-0.6b"]
A15_H = ["aimem-qwen3-rerank-qwen3.6", "aimem-qwen3-rerank-nemotron-lightning", "aimem-qwen3-rerank-lfm2.5"]
ORIGINAL_LAYER = ["A0-official-bm25", "bm25-full", "dense-qwen3", "am-keyless", "am-minilm", "am-qwen3"]
LAYER = ORIGINAL_LAYER + A15_E + A15_G
C3_DIAGNOSTICS = ["aimem-qwen3-8b", "aimem-qwen3-0.6b"]  # C5 and C6: A15.2's C3-family size diagnostics
C3_ORIGINAL = ["aimem-fts", "aimem-minilm"]  # C1 and C2: against C3 as registered in A2 and A14 (A16.2)
# A16.2: the declared bound on a false production change, per setting, and the union across settings.
ERROR_BOUNDS = {"layer (replace ai-memory)": {"bound": 0.05, "how": "A15 layer candidates <= 0.0333 (both families, "
                                                                    "intersection-union) plus A16 candidates <= 0.0167"},
                "ai-memory configuration (C1, C2, F)": {"bound": 0.0667, "how": "C1 and C2 against C3 in the C3 family "
                                                                                "<= 0.0333 plus F against C4 in the C4 "
                                                                                "family <= 0.0333 (A16.3)"},
                "reranker (on/off, then an H swap)": {"bound": 0.0667, "how": "on/off in the C3 family <= 0.0333 plus "
                                                                              "an H swap in the C4 family <= 0.0333, "
                                                                              "considered only while the reranker stays on"},
                "across all settings (union bound)": {"bound": 0.0833, "how": "the sum of the three families' alpha; "
                                                                             "each setting is declared separately"}}
# A15.2: one family per reference arm, fixed now at its largest membership.
C3_FAMILY = ["A0-official-bm25", "bm25-full", "dense-qwen3", "aimem-fts", "aimem-minilm", PRODUCTION,
             "aimem-qwen3-8b", "aimem-qwen3-0.6b", "am-keyless", "am-minilm", "am-qwen3"] + A15_E + A15_G
C4_FAMILY = ORIGINAL_LAYER + A15_E + A15_G + A15_F + A15_H
ALPHA = 0.0333  # per family (A15.2); 0.0167 is reserved for A16
ALPHA_A16 = 0.0167
AGENTMEMORY = {"am-keyless", "am-minilm", "am-qwen3"} | set(A15_E)  # the benchmark API path (A15.2 label)
NEW_EMBEDDER = set(A15_E + A15_F + A15_G)  # a production switch also needs the deployability gate (A15.2)
D2H = "am-minilm-hooks"
G0 = "dense-qwen3-bf16"
M2, K1, M1 = "mempalace-palace", "hindsight-qwen3.6", "m1-mempalace-raw"
A16_FAMILY = [D2H, M2, K1]  # A16: fixed now at its full membership
D2 = "am-minilm"
K1_SUBSET = HERE / "k1-subset.json"
A16_DEFERRED = ("Deferred with no arm (A16): Attemory (its gate is a source and licence check of the prebuilt core), GBrain "
                "and Mem0 OSS. Rejected for this role: Honcho, OpenViking, Basic Memory and the retired Letta server.")
ADOPTION = "; adoption also requires the catalog's memory-lane acceptance (A16 production rule)"
F_FILL = [f"{arm}-fill" for arm in A15_F]
E_VS_F = list(zip(A15_E, A15_F, strict=True))  # the same embedder in both systems (A15.2, descriptive)
# One choice per setting (A15.2); A16.3 puts C1, C2 and F in one "ai-memory configuration" setting, so two
# conflicting configuration changes are never both reported as the change to make.
AIMEM_SETTING = "ai-memory configuration (C1, C2 against C3; F against C4)"
SETTINGS = {AIMEM_SETTING: C3_ORIGINAL + A15_F, "reranker LLM (H, against C4)": A15_H}
LAYER_SETTING = "layer (A0, B, D, E, G and A16's D2h, M2, K1)"  # one setting across A15 and A16 (review P5, F3)
FALLBACK_LIMIT = 0.05  # A12
ERROR_CAP = 0.01  # A15 review: more than 1% infra or unclassified error rows marks an environment-wide fault
DESCRIPTIVE = {G0: "G0 diagnostic (A15): quantization and runtime against model generation; no decision",
               M1: "M1 diagnostic (A16): MemPalace raw mode through its own benchmark, rescored with the official "
                   "evaluator; no decision"}


def pooled(arm: str) -> bool:
    """A16 pooled-store stress runs (lme_harness.py --pooled): descriptive, never decided."""
    return arm.startswith("pooled-")


def k1_subset() -> list[str]:
    return json.loads(K1_SUBSET.read_text())["question_ids"] if K1_SUBSET.exists() else []


def scope_ids(arm: str, ids: list[str], subset: list[str]) -> list[str]:
    """The questions an arm is scored on in one track: K1 runs on its preregistered subset (A16)."""
    if arm == K1:
        keep = set(subset)
        return [q for q in ids if q in keep]
    return ids


def exploratory(arm: str) -> bool:
    """X arms (rerank_stage.py): a cross-encoder over another arm's top 50, reported and never decided (A15)."""
    return arm.startswith("x-")


def load_questions() -> dict:
    return {q["question_id"]: q for q in json.loads(DATA.read_text())}


def official_log_rows(path: Path, questions: dict) -> dict:
    """Map the official runner's ranked corpus ids back to haystack positions and score both tracks."""
    rows, dups = {}, []
    for line in path.open():
        if not line.strip():
            continue
        e = json.loads(line)
        if e["question_id"] in rows:
            dups.append(e["question_id"])
        q = questions[e["question_id"]]
        free = defaultdict(list)
        for pos, sid in enumerate(q["haystack_session_ids"]):
            free[sid].append(pos)
        ranking = []
        for item in e["retrieval_results"]["ranked_items"]:
            sid = item["corpus_id"].replace("noans", "answer")
            if free[sid]:
                ranking.append(free[sid].pop(0))
        rows[e["question_id"]] = {"question_id": e["question_id"], "question_type": q["question_type"],
                                  "ranking": ranking, "metrics": score(q, ranking), "error": None,
                                  "official_log_metrics": e["retrieval_results"]["metrics"]["session"]}
    if dups:  # review (stats F6): the same refusal as load_rows
        raise ValueError(f"{path.name}: duplicate question ids {sorted(set(dups))[:10]}; two processes wrote one arm")
    return rows


def full_oracle_rows(questions: dict, ids: list[str]) -> dict:
    """Full-session oracle: every answer_session_ids position first (haystack order), then the rest."""
    rows = {}
    for qid in ids:
        q = questions[qid]
        gold = [i for i, sid in enumerate(q["haystack_session_ids"]) if sid in q["answer_session_ids"]]
        ranking = gold + [i for i in range(len(q["haystack_session_ids"])) if i not in gold]
        rows[qid] = {"question_id": qid, "question_type": q["question_type"], "ranking": ranking,
                     "metrics": score(q, ranking), "error": None}
    return rows


def load_rows(results: Path) -> dict:
    """Every <arm>.jsonl in a directory. A duplicate question id is refused, never silently overwritten."""
    arms = {}
    for p in sorted(results.glob("*.jsonl")):
        rows, dups = {}, []
        for line in p.open():
            r = json.loads(line)
            if r["question_id"] in rows:
                dups.append(r["question_id"])
            rows[r["question_id"]] = r
        if dups:
            raise ValueError(f"{p.name}: duplicate question ids {sorted(set(dups))[:10]}; two processes wrote one arm")
        arms[p.stem] = rows
    return arms


def load_arms(questions: dict, full_ids: list[str], results: Path = HERE / "results",
              official_logs: Path = HERE / "official-logs") -> dict:
    arms = {"A1b-full-oracle": full_oracle_rows(questions, full_ids)}
    for name, fname in OFFICIAL_LOGS.items():
        p = official_logs / fname
        if p.exists():
            arms[name] = official_log_rows(p, questions)
    return arms | load_rows(results)  # A15: rows converted from the official logs (lane_tools.py) also load here


def coverage_of(rows: dict, scope: list[str]) -> dict:
    """Missing and error rows by class. A4: env errors invalidate an arm; A15 review: so do more than 1% of rows
    with infra or unclassified errors (an environment-wide fault); deadline rows stay scored failures."""
    errors = [rows[qid]["error"] for qid in scope if qid in rows and rows[qid].get("error")]
    env = sum(e.startswith("env:") for e in errors)
    deadline = sum(e.startswith("deadline:") for e in errors)
    infra = sum(e.startswith("infra:") for e in errors)
    other = len(errors) - env - deadline - infra
    return {"missing": sum(qid not in rows for qid in scope), "errors": len(errors), "rows": len(rows),
            "env_errors": env, "deadline_errors": deadline, "infra_errors": infra, "other_errors": other,
            "error_cap": ERROR_CAP * len(scope)}


def invalid_reason(c: dict) -> str | None:
    if c["missing"]:
        return None  # incomplete, not invalid
    if c["env_errors"]:
        return "env errors"
    if c["infra_errors"] + c["other_errors"] > c["error_cap"]:
        return f"{c['infra_errors'] + c['other_errors']} infra or unclassified error rows, over 1%"
    return None


def clusters(ids: list[str], questions: dict) -> np.ndarray:
    """Union-find over questions that share any evidence session's conversation content (A5).

    Only the (role, content) sequence is hashed: gold annotations such as `has_answer` differ between
    questions that share a conversation and must not split its cluster.
    """
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner = {}
    for qid in ids:
        q = questions[qid]
        for sid, sess in zip(q["haystack_session_ids"], q["haystack_sessions"]):
            if sid in q["answer_session_ids"]:
                canonical = json.dumps([[t["role"], t["content"]] for t in sess], ensure_ascii=False)
                h = hashlib.sha256(canonical.encode()).hexdigest()
                if h in owner:
                    parent[find(qid)] = find(owner[h])
                else:
                    owner[h] = qid
    roots = {}
    return np.array([roots.setdefault(find(i), len(roots)) for i in ids])


def cluster_means(diff: np.ndarray, cl: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    k = cl.max() + 1
    sums, counts = np.bincount(cl, weights=diff, minlength=k), np.bincount(cl, minlength=k)
    return sums, counts


def stream(*key: str) -> np.random.Generator:
    """One generator per comparison (A13): a result never depends on which other arms are complete."""
    return np.random.default_rng([SEED, int(hashlib.sha256(":".join(key).encode()).hexdigest()[:8], 16)])


def paired(a: np.ndarray, b: np.ndarray, cl: np.ndarray, rng: np.random.Generator) -> dict:
    """Mean difference a-b with cluster bootstrap CI and cluster sign-flip randomization p-value."""
    diff = a - b
    sums, counts = cluster_means(diff, cl)
    k = len(sums)
    idx = rng.integers(0, k, size=(BOOT, k))
    boot = sums[idx].sum(1) / counts[idx].sum(1)
    obs = diff.mean()
    signs = rng.choice([-1.0, 1.0], size=(PERM, k))
    perm = (signs * sums).sum(1) / counts.sum()
    p = (np.sum(np.abs(perm) >= abs(obs) - 1e-12) + 1) / (PERM + 1)
    return {"diff": obs, "ci": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))], "p": float(p)}


def rule(full: dict, off, alpha: float = ALPHA) -> bool:
    """The preregistered rule (A2; alpha per family from A15.2): Holm p < alpha, CI above 0, at least +5 pp, and
    official track >= -2 pp."""
    return (full["p_holm"] < alpha and full["ci"][0] > 0 and full["diff"] >= 0.05
            and off is not None and off["diff"] >= -0.02)


def holm(ps: dict) -> dict:
    order = sorted(ps, key=lambda key: ps[key])
    adj, running = {}, 0.0
    for i, key in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * ps[key]))
        adj[key] = running
    return adj


def gpu_utilization(path: Path) -> dict | None:
    """Mean GPU utilization from an `nvidia-smi dmon -s u` log, or from `--query-gpu=...utilization.gpu` CSV."""
    samples = []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:  # CSV: timestamp, utilization.gpu [%], ...
            fields = [f.strip() for f in line.split(",")]
            if len(fields) > 1 and re.fullmatch(r"\d+(\.\d+)?( %)?", fields[1]):
                samples.append(float(fields[1].split()[0]))
            continue
        fields = line.split()
        while fields and re.fullmatch(r"\d{8}|\d{2}:\d{2}:\d{2}", fields[0]):
            fields = fields[1:]  # dmon -o DT prefixes the date and the time (review, lane F7)
        if len(fields) >= 2 and fields[0].isdigit() and re.fullmatch(r"\d+", fields[1]):
            samples.append(float(fields[1]))  # dmon columns: gpu, sm, mem, ...
    return {"samples": len(samples), "mean_util": float(np.mean(samples))} if samples else None


def cpu_load(path: Path) -> dict | None:
    """Mean 1-minute load and the lowest available memory from a run script load-<arm>.log (review, infra F8)."""
    loads, avail = [], []
    for line in path.read_text(errors="ignore").splitlines():
        fields = line.split()
        if len(fields) >= 5 and not line.startswith("#"):
            try:
                loads.append(float(fields[1]))
                avail.append(int(fields[4]))
            except ValueError:
                continue
    if not loads:
        return None
    return {"samples": len(loads), "mean_load1": float(np.mean(loads)), "min_mem_available_gib": min(avail) / 2**20}


def replication(other_dir: Path, arms: dict, questions: dict, tracks: dict, platform: str, other: str) -> tuple:
    """The same arm on two platforms: means, paired differences and agreement. Reported, never decided (A15)."""
    other_arms = load_rows(other_dir)
    table, lines = {}, []
    for track, ids in tracks.items():
        cl = clusters(ids, questions)
        for arm in sorted(set(arms) & set(other_arms)):
            if TRACK_ONLY.get(arm, track) != track:
                continue
            here, there = arms[arm], other_arms[arm]
            if any(qid not in here or qid not in there for qid in ids):
                continue
            a = {m: np.array([here[qid]["metrics"][track][m] for qid in ids], dtype=float) for m in (PRIMARY, "ndcg_any@5")}
            b = {m: np.array([there[qid]["metrics"][track][m] for qid in ids], dtype=float) for m in (PRIMARY, "ndcg_any@5")}
            comp = {m: paired(a[m], b[m], cl, stream(track, "replication", arm, m)) for m in (PRIMARY, "ndcg_any@5")}
            table.setdefault(arm, {})[track] = {
                "means": {platform: float(a[PRIMARY].mean()), other: float(b[PRIMARY].mean())},
                "diff": comp, "identical_primary": int(np.sum(a[PRIMARY] == b[PRIMARY])),
                "identical_top5": sum(here[qid]["ranking"][:5] == there[qid]["ranking"][:5] for qid in ids), "n": len(ids)}
    if table:
        lines += [f"## Replication: {platform} against {other} (per arm, reported only, never mixed into a decision)", "",
                  f"| arm | track | {other} {PRIMARY} | {platform} {PRIMARY} | Δ | 95% CI | Δ ndcg_any@5 | "
                  f"identical {PRIMARY} | identical top-5 |", "|---|---|---|---|---|---|---|---|---|"]
        for arm, per in table.items():
            for track, t in per.items():
                d, n = t["diff"][PRIMARY], t["diff"]["ndcg_any@5"]
                lines.append(f"| {arm} | {track} | {t['means'][other]:.3f} | {t['means'][platform]:.3f} | {d['diff']:+.3f} | "
                             f"[{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}] | {n['diff']:+.3f} | {t['identical_primary']}/{t['n']} | "
                             f"{t['identical_top5']}/{t['n']} |")
        lines.append("")
    return table, lines


def fallback_rate(rows: dict) -> tuple[int, float]:
    """A12: questions whose rerank fell back (timeout, failure or invalid scores), and their share."""
    fell = sum(1 for r in rows.values() if any(r.get(k, 0) for k in RERANK_KEYS))
    return fell, fell / max(len(rows), 1)


def oracle_gate(arms: dict, tracks: dict) -> dict:
    """A6: the oracles must reach the recall_all@5 ceilings and recall_any@k = 1.0 for every k."""
    out = {}
    for (arm, track), ceiling in CEILINGS.items():
        rows = arms.get(arm, {})
        ids = tracks[track]
        if any(qid not in rows for qid in ids):
            out[arm] = {"track": track, "pass": False, "reason": "missing or incomplete"}
            continue
        mean = {m: float(np.mean([rows[qid]["metrics"][track][m] for qid in ids]))
                for m in [PRIMARY] + [f"recall_any@{k}" for k in KS]}
        ok = abs(mean[PRIMARY] - ceiling) < 1e-9 and all(mean[f"recall_any@{k}"] == 1.0 for k in KS)
        out[arm] = {"track": track, "recall_all@5": mean[PRIMARY], "ceiling": ceiling, "pass": ok,
                    "recall_any": {k: mean[f"recall_any@{k}"] for k in KS}}
    return out


def decide(blockers: list, comps: list, waiting: list, what: str, alpha: float = ALPHA, final: bool = False) -> str:
    """One decision under the A2 rule, with A13's early-final logic.

    `comps` holds (full-track comparison, official-track comparison) pairs, one per required reference family;
    the candidate passes only if it passes in every one (A14's intersection-union test). With `final` (the queue
    has finished), a decision still waiting on unfinished members is closed with them held at p = 1.
    """
    if blockers:
        return "pending: " + "; ".join(blockers)
    if any(full is None for full, _ in comps):
        return "pending: arm not finished (missing rows, env errors, or over 1% infra or unclassified errors)"
    if all(rule(full, off, alpha) for full, off in comps):
        return f"BEATS ({what})" + (" — final before the family finished (A13)" if waiting else "")
    if waiting and final:
        return f"does not beat (final; {', '.join(waiting)} never finished, held at p = 1) ({what})"
    if waiting:
        return f"provisional: does not beat yet ({what}); final once {', '.join(waiting)} finish"
    return f"does not beat ({what})"


def repro_note(pairs: list) -> dict:
    """A13 re-run agreement, as counts only (A15.2: no causal attribution)."""
    def same(m):
        return sum(all(abs(o["metrics"][t][m] - r["metrics"][t][m]) < 1e-12 for t in ("full", "official"))
                   for o, r in pairs)
    first = [next((i for i, (x, y) in enumerate(zip(o["ranking"], r["ranking"])) if x != y), None) for o, r in pairs]
    diverging = [i + 1 for i in first if i is not None]
    rep = {"questions": len(pairs), "identical_full_ranking": sum(o["ranking"] == r["ranking"] for o, r in pairs),
           "identical_top5": sum(o["ranking"][:5] == r["ranking"][:5] for o, r in pairs),
           "same_ranked_set": sum(set(o["ranking"]) == set(r["ranking"]) for o, r in pairs),
           "first_divergent_rank_min": min(diverging) if diverging else None,
           **{f"identical_{m}": same(m) for m in (PRIMARY, "ndcg_any@5", "recall_all@10", "ndcg_any@10")}}
    if rep["identical_full_ranking"] < rep["questions"]:
        rep["note"] = (f"full rankings differ from rank {rep['first_divergent_rank_min']} down in "
                       f"{rep['questions'] - rep['identical_full_ranking']} of {rep['questions']} questions "
                       f"({rep['same_ranked_set']} keep the same ranked set); the counts do not identify a cause")
    else:
        rep["note"] = "all full rankings identical"
    return rep


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent", default="aimem-qwen3")
    ap.add_argument("--out", default=str(HERE / "report"))
    ap.add_argument("--final", action="store_true",
                    help="the run queue has finished: A15.2 fixes the families at their largest membership, so no arm "
                         "ever leaves a family; a decision still waiting on an unfinished member is closed with it held "
                         "at p = 1 (review, stats F7)")
    ap.add_argument("--results", default=str(HERE / "results"), help="the harness rows (A15: results-velanext)")
    ap.add_argument("--official-logs", default=str(HERE / "official-logs"))
    ap.add_argument("--cachewarm", default=str(HERE / "results-cachewarm"))
    ap.add_argument("--platform", default="Mac", help="label for this platform's results (A15)")
    ap.add_argument("--confirmatory", action="store_true",
                    help="decisions are confirmatory (A15.2: VelaNext only); otherwise they are descriptive")
    ap.add_argument("--replication", help="rows of the same arms from the other platform (A15)")
    ap.add_argument("--replication-platform", default="Mac")
    ap.add_argument("--gpu-logs", help="directory of gpu-<arm>.log files (A15.1)")
    ap.add_argument("--oracle-gate", action="store_true", help="check the A6 oracle ceilings only; exit 1 on failure")
    ap.add_argument("--gates", help="the gate reports (logs/gates): --confirmatory requires them to pass")
    a = ap.parse_args(argv)
    gate_report = None
    if a.confirmatory:  # review P6: only VelaNext rows after the passed gates are confirmatory
        if a.platform != "VelaNext":
            raise SystemExit(f"--confirmatory needs --platform VelaNext, not {a.platform!r} (A15.2)")
        if not a.gates:
            raise SystemExit("--confirmatory needs --gates DIR (the oracle and v4 = v3 gate reports)")
        from lane_tools import gate_status
        gate_report = gate_status(Path(a.gates))
        if not gate_report["pass"]:
            raise SystemExit("--confirmatory refused: the gates did not pass: " + "; ".join(gate_report["problems"]))
    questions = load_questions()
    manifest = json.loads(MANIFEST.read_text())
    tracks = {"full": manifest["full_session_track"], "official": manifest["official_track"]}
    arms = load_arms(questions, tracks["full"], Path(a.results), Path(a.official_logs))
    if a.oracle_gate:
        gate = oracle_gate(arms, tracks)
        print(json.dumps(gate, indent=1))
        if not gate or not all(c["pass"] for c in gate.values()):
            raise SystemExit(1)
        return {"oracle_gate": gate}
    incumbent = a.incumbent
    report: dict[str, Any] = {"incumbent": incumbent, "production": PRODUCTION, "platform": a.platform,
              "confirmatory": a.confirmatory, "final": a.final, "tracks": {}, "coverage": {}, "oracle_checks": {},
              "gates": gate_report,
              "alpha": {"C3 family": ALPHA, "C4 family": ALPHA, "A16 family": ALPHA_A16,
                        "note": "per family and per production setting; the Bonferroni bound across all settings is 0.0833"},
              "error_bounds": ERROR_BOUNDS}
    lines = [f"# LongMemEval-S retrieval tier: results ({a.platform})", "",
             f"Platform: {a.platform}; decisions are {'confirmatory' if a.confirmatory else 'descriptive (A15.2)'}. "
             f"Dataset sha256 `{manifest['dataset_sha256'][:16]}…`; protocol PREREGISTRATION.md (A1–A16.2).", ""]
    subset = k1_subset()
    for arm in OFFICIAL_LOGS:  # an absent official log still shows in the coverage table
        if arm not in arms:
            scope = tracks[TRACK_ONLY.get(arm, "full")]
            report["coverage"][arm] = coverage_of({}, scope) | {"absent": True}
    for arm, rows in arms.items():
        report["coverage"][arm] = coverage_of(rows, scope_ids(arm, tracks[TRACK_ONLY.get(arm, "full")], subset))
    complete = {arm for arm, c in report["coverage"].items() if c["rows"] and c["missing"] == 0}
    invalid = {arm: invalid_reason(report["coverage"][arm]) for arm in complete if invalid_reason(report["coverage"][arm])}
    finished = complete - set(invalid)
    report["invalid"] = invalid
    fam_state: dict[str, dict[str, Any]] = {name: {"members": members, "alpha": ALPHA, "reference": ref,
                        "unfinished": [x for x in members if x not in finished]}
                 for name, members, ref in (("C3", C3_FAMILY, incumbent), ("C4", C4_FAMILY, PRODUCTION))}
    fam_state["A16"] = {"members": A16_FAMILY, "alpha": ALPHA_A16, "reference": [incumbent, PRODUCTION],
                        "unfinished": [x for x in A16_FAMILY if x not in finished],
                        "k1_subset": {"file": K1_SUBSET.name, "questions": len(subset)}}
    report["families"] = fam_state

    def label(arm: str) -> str:
        return f"{arm} (invalid: {invalid[arm]})" if arm in invalid else arm

    for track, ids in tracks.items():
        cl = clusters(ids, questions)
        vals = {}
        for arm, rows in arms.items():
            if TRACK_ONLY.get(arm, track) != track or any(qid not in rows for qid in ids):
                continue  # incomplete or other-track arms are reported in coverage, never averaged
            vals[arm] = {m: np.array([rows[qid]["metrics"][track][m] for qid in ids], dtype=float)
                         for m in [PRIMARY] + SECONDARY}
        table = {arm: {m: float(v.mean()) for m, v in mv.items()} for arm, mv in vals.items()}
        for (arm, t), ceiling in CEILINGS.items():
            if t == track and arm in table:  # A15 review: every k, from the rows, and only for a finished oracle
                any_ok = all(float(np.mean([arms[arm][qid]["metrics"][track][f"recall_any@{k}"] for qid in ids])) == 1.0
                             for k in KS)
                report["oracle_checks"][arm] = {"recall_all@5": table[arm][PRIMARY], "ceiling": ceiling,
                                                "pass": arm in finished and abs(table[arm][PRIMARY] - ceiling) < 1e-9 and any_ok}

        def compare(reference: str, fam: list, key: tuple, holm_family: bool = True) -> dict:
            out = {}
            if reference not in vals or reference not in finished:
                return out
            for arm in fam:  # the frozen family; arms not yet finished are absent, never re-sized away
                if arm in vals and arm in finished and arm != reference:
                    out[arm] = {m: paired(vals[arm][m], vals[reference][m], cl, stream(*key, arm, m))
                                for m in (PRIMARY, "ndcg_any@5")}
            if holm_family:  # Holm over the full declared family: a member not yet finished counts as p = 1 (A13)
                adj = holm({arm: c[PRIMARY]["p"] for arm, c in out.items()} | {arm: 1.0 for arm in fam if arm not in out})
                for arm in out:
                    out[arm][PRIMARY]["p_holm"] = adj[arm]
            return out
        comps_c3 = compare(incumbent, C3_FAMILY, (track,))
        comps_c4 = compare(PRODUCTION, C4_FAMILY, (track, PRODUCTION))
        # Descriptive, never decided: every arm against A0 (the preregistered baseline), D2h, E against F.
        others = [x for x in vals if x in finished and not x.startswith("A1") and x != "A0-official-bm25"]
        vs_a0 = compare("A0-official-bm25", others, (track, "A0"), holm_family=False)
        # A16: each member against C3 and C4 on its own scope (K1: its subset); IUT p, Holm over the fixed family.
        a16 = {}
        for arm in A16_FAMILY:
            if arm not in finished or arm not in arms:
                continue
            sids = scope_ids(arm, ids, subset)
            if not sids:
                continue
            scl = clusters(sids, questions)
            for ref in (incumbent, PRODUCTION):
                if ref in finished and ref in arms and all(q in arms[ref] for q in sids):
                    va = {m: np.array([arms[arm][q]["metrics"][track][m] for q in sids], dtype=float) for m in (PRIMARY, "ndcg_any@5")}
                    vb = {m: np.array([arms[ref][q]["metrics"][track][m] for q in sids], dtype=float) for m in (PRIMARY, "ndcg_any@5")}
                    a16.setdefault(arm, {})[ref] = {m: paired(va[m], vb[m], scl, stream(track, "A16", ref, arm, m))
                                                    for m in (PRIMARY, "ndcg_any@5")} | {"n": len(sids)}
        iut = {arm: max(c[incumbent][PRIMARY]["p"], c[PRODUCTION][PRIMARY]["p"]) for arm, c in a16.items()
               if incumbent in c and PRODUCTION in c}
        adj = holm(iut | {arm: 1.0 for arm in A16_FAMILY if arm not in iut})
        for arm in iut:
            for ref in (incumbent, PRODUCTION):
                a16[arm][ref][PRIMARY]["p_holm"] = adj[arm]
                a16[arm][ref][PRIMARY]["p_iut"] = iut[arm]
        # K1's subset: C3, C4, D2 (and the other A16 arms) on the same questions; K1 against D2 is descriptive.
        sub_ids = scope_ids(K1, ids, subset)
        k1_table, k1_vs_d2 = {}, {}
        for arm in [incumbent, PRODUCTION, D2, D2H, M2, K1]:
            if arm in arms and sub_ids and all(q in arms[arm] for q in sub_ids):
                k1_table[arm] = {m: float(np.mean([arms[arm][q]["metrics"][track][m] for q in sub_ids]))
                                 for m in (PRIMARY, "ndcg_any@5", "recall_any@5")}
        if K1 in k1_table and D2 in k1_table and K1 in finished and D2 in finished:
            scl = clusters(sub_ids, questions)
            k1_vs_d2 = {m: paired(np.array([arms[K1][q]["metrics"][track][m] for q in sub_ids], dtype=float),
                                  np.array([arms[D2][q]["metrics"][track][m] for q in sub_ids], dtype=float),
                                  scl, stream(track, "K1-D2", m)) for m in (PRIMARY, "ndcg_any@5")}
        # Pooled stress runs against the same arm's per-question stores (descriptive).
        pooled_vs: dict[str, dict[str, Any]] = {}
        for arm in sorted(arms):
            base = arm.removeprefix("pooled-")
            if not pooled(arm) or base not in arms:
                continue
            sids = [q for q in scope_ids(base, ids, subset) if q in arms[arm] and q in arms[base]]
            if sids:
                pooled_vs[arm] = {"base": base, "n": len(sids)} | {
                    m: paired(np.array([arms[arm][q]["metrics"][track][m] for q in sids], dtype=float),
                              np.array([arms[base][q]["metrics"][track][m] for q in sids], dtype=float),
                              clusters(sids, questions), stream(track, "pooled", arm, m)) for m in (PRIMARY, "ndcg_any@5")}
        e_vs_f: dict[str, dict[str, Any]] = {}
        for e, f in E_VS_F:
            if e in vals and f in vals and e in finished and f in finished:
                e_vs_f[f"{e} - {f}"] = {m: paired(vals[e][m], vals[f][m], cl, stream(track, "E-F", e, m))
                                        for m in (PRIMARY, "ndcg_any@5")}
        x_vs_base: dict[str, dict[str, Any]] = {}
        for arm in sorted(vals):
            base = next(iter(arms[arm].values())).get("base") if exploratory(arm) else None
            if base in vals:
                x_vs_base[arm] = {"base": base} | {m: paired(vals[arm][m], vals[base][m], cl, stream(track, "X", arm, m))
                                                    for m in (PRIMARY, "ndcg_any@5")}
        by_type = defaultdict(dict)
        for arm, rows in arms.items():
            if arm not in vals:
                continue
            groups = defaultdict(list)
            for qid in ids:
                groups[questions[qid]["question_type"]].append(rows[qid]["metrics"][track][PRIMARY])
            for t, v in groups.items():
                by_type[t][arm] = (float(np.mean(v)), len(v))
        report["tracks"][track] = {"n": len(ids), "clusters": int(cl.max() + 1), "means": table,
                                   "invalid": sorted(x for x in table if x in invalid),
                                   "vs_c3_family": comps_c3, "vs_c4_family": comps_c4, "vs_a0_baseline": vs_a0,
                                   "a16": a16, "k1_subset": {"n": len(sub_ids), "means": k1_table, "k1_vs_d2": k1_vs_d2},
                                   "pooled_vs_per_question": pooled_vs,
                                   "e_vs_f": e_vs_f, "exploratory_vs_base": x_vs_base, "by_type": by_type,
                                   "_vals": vals, "_clusters": cl}
        lines += [f"## {track} track (n = {len(ids)}, {cl.max() + 1} evidence clusters)", "",
                  "| arm | " + " | ".join([PRIMARY] + SECONDARY) + " |",
                  "|---|" + "---|" * (1 + len(SECONDARY))]
        for arm, mv in sorted(table.items(), key=lambda kv: (kv[0] in invalid, -kv[1][PRIMARY])):
            lines.append(f"| {label(arm)} | " + " | ".join(f"{mv[m]:.3f}" for m in [PRIMARY] + SECONDARY) + " |")
        for title, cs, adjusted in (
                (f"`{incumbent}` (C3 family, Holm at α = {ALPHA}, A15.2)", comps_c3, True),
                (f"`{PRODUCTION}` (production C4; C4 family, Holm at α = {ALPHA}, A15.2)", comps_c4, True),
                ("`A0-official-bm25` (the preregistered baseline; descriptive, unadjusted p, no decision role)", vs_a0, False)):
            if not cs:
                continue
            p_head = "p (Holm)" if adjusted else "p (unadjusted)"
            lines += ["", f"Paired against {title}; cluster bootstrap 95% CI and sign-flip p:", "",
                      f"| arm | Δ recall_all@5 | 95% CI | {p_head} | Δ ndcg_any@5 | 95% CI |", "|---|---|---|---|---|---|"]
            for arm, c in sorted(cs.items(), key=lambda kv: -kv[1][PRIMARY]["diff"]):
                r, n = c[PRIMARY], c["ndcg_any@5"]
                lines.append(f"| {label(arm)} | {r['diff']:+.3f} | [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] | "
                             f"{r['p_holm' if adjusted else 'p']:.4f} | {n['diff']:+.3f} | [{n['ci'][0]:+.3f}, {n['ci'][1]:+.3f}] |")
        if a16:
            lines += ["", f"A16 memory systems against `{incumbent}` (C3) and `{PRODUCTION}` (C4); Holm over the family at "
                          f"α = {ALPHA_A16} on the intersection-union p (the larger of the two); K1 on its subset:", "",
                      "| arm | n | reference | Δ recall_all@5 | 95% CI | p | p (IUT, Holm) | Δ ndcg_any@5 |", "|---|---|---|---|---|---|---|---|"]
            for arm, per in a16.items():
                for ref, c in per.items():
                    r, n = c[PRIMARY], c["ndcg_any@5"]
                    lines.append(f"| {label(arm)} | {c['n']} | {ref} | {r['diff']:+.3f} | [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] | "
                                 f"{r['p']:.4f} | {r['p_holm']:.4f} | {n['diff']:+.3f} |" if "p_holm" in r else
                                 f"| {label(arm)} | {c['n']} | {ref} | {r['diff']:+.3f} | [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] | "
                                 f"{r['p']:.4f} | – | {n['diff']:+.3f} |")
        if k1_table:
            lines += ["", f"K1's preregistered subset (n = {len(sub_ids)}, seed 20260925, stratified by question type; A16):", "",
                      "| arm | recall_all@5 | ndcg_any@5 | recall_any@5 |", "|---|---|---|---|"]
            lines += [f"| {label(arm)} | {v[PRIMARY]:.3f} | {v['ndcg_any@5']:.3f} | {v['recall_any@5']:.3f} |" for arm, v in k1_table.items()]
            if k1_vs_d2:
                r = k1_vs_d2[PRIMARY]
                lines.append(f"\nK1 against D2 on the subset (descriptive): Δ recall_all@5 {r['diff']:+.3f} "
                             f"[{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}], p {r['p']:.4f} (unadjusted).")
        for title, cs in (("E against F at the same embedder (A15.2; descriptive)", e_vs_f),
                          ("Exploratory X (A15): a cross-encoder over its base arm's top 50, against that base", x_vs_base),
                          ("Pooled-store stress run (A16): one store of every eligible session, against the same arm's "
                           "per-question stores", pooled_vs)):
            if not cs:
                continue
            lines += ["", f"{title}; unadjusted p, never decided:", "",
                      "| comparison | Δ recall_all@5 | 95% CI | p | Δ ndcg_any@5 | 95% CI |", "|---|---|---|---|---|---|"]
            for name, c in cs.items():
                r, n = c[PRIMARY], c["ndcg_any@5"]
                shown = f"{name} (base {c['base']})" if "base" in c else name
                lines.append(f"| {shown} | {r['diff']:+.3f} | [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] | {r['p']:.4f} | "
                             f"{n['diff']:+.3f} | [{n['ci'][0]:+.3f}, {n['ci'][1]:+.3f}] |")
        lines += ["", f"{PRIMARY} by question type:", "", "| type | " + " | ".join(label(x) for x in sorted(table)) + " |",
                  "|---|" + "---|" * len(table)]
        for t in sorted(by_type):
            lines.append(f"| {t} (n={next(iter(by_type[t].values()))[1]}) | " +
                         " | ".join(f"{by_type[t][arm][0]:.3f}" if arm in by_type[t] else "–" for arm in sorted(table)) + " |")
        lines.append("")
    tf, to = report["tracks"]["full"], report["tracks"]["official"]

    def pair(family: str, arm: str) -> tuple:
        key = "vs_c3_family" if family == "C3" else "vs_c4_family"
        return tf[key].get(arm, {}).get(PRIMARY), to[key].get(arm, {}).get(PRIMARY)

    blockers = []
    for arm, _track in CEILINGS:  # A15 review: a missing or incomplete oracle blocks too
        c = report["oracle_checks"].get(arm)
        blockers.append(f"oracle check missing or incomplete: {arm}" if c is None else
                        (f"oracle check failed: {arm}" if not c["pass"] else ""))
    blockers = [b for b in blockers if b]
    need_c3 = [] if incumbent in finished else [f"{incumbent} (C3) not finished"]
    need_c4 = [] if PRODUCTION in finished else [f"production {PRODUCTION} (C4) not finished"]
    c4_fell, c4_rate = fallback_rate(arms[PRODUCTION]) if PRODUCTION in arms else (0, 0.0)
    c4_inconclusive = PRODUCTION in finished and c4_rate > FALLBACK_LIMIT
    report["rerank_fallback"] = {PRODUCTION: {"questions_with_fallback": c4_fell, "rate": c4_rate}}
    wait_c3, wait_c4 = fam_state["C3"]["unfinished"], fam_state["C4"]["unfinished"]
    decisions = {}
    # 1. The reranker (A15.2 precedence): C3 against C4, production (reranker on) the status quo.
    if blockers or need_c3 or need_c4:
        decisions[PRODUCTION] = "pending: " + "; ".join(blockers + need_c3 + need_c4)
        reranker = "pending"
    elif c4_inconclusive:
        decisions[PRODUCTION] = f"reranker decision inconclusive (A12): {c4_rate:.1%} of queries fell back"
        reranker = "inconclusive"
    else:
        c, o = pair("C3", PRODUCTION)
        rev = {"diff": -c["diff"], "ci": [-c["ci"][1], -c["ci"][0]], "p_holm": c["p_holm"]}
        rev_off = {"diff": -o["diff"]} if o else None
        waiting = [x for x in wait_c3 if x != PRODUCTION]
        if rule(rev, rev_off):
            reranker = "off"
            decisions[PRODUCTION] = ("turn the reranker OFF: C3 beats production C4 (A14, A15.2)"
                                     + (" — final before the family finished (A13)" if waiting else ""))
        elif waiting and a.final:
            reranker = "keep"
            decisions[PRODUCTION] = (f"keep the reranker (final; {', '.join(waiting)} never finished, held at p = 1): "
                                     "C3 does not beat production C4 (A14, A15.2)")
        elif waiting:
            reranker = "keep-provisional"
            decisions[PRODUCTION] = ("provisional: keep the reranker (C3 does not beat production C4 yet); final once "
                                     f"{', '.join(waiting)} finish")
        else:
            reranker = "keep"
            decisions[PRODUCTION] = "keep the reranker: C3 does not beat production C4 (A14, A15.2)"
    report["reranker_state"] = reranker
    conditional = {"keep-provisional": " — conditional on the reranker staying on (its decision is provisional)"}.get(reranker, "")
    # 2. C5 and C6: C3-family size diagnostics (A15.2). C1 and C2: against C3 as registered (A2, A14, A16.2).
    for arm in C3_DIAGNOSTICS:
        decisions[arm] = decide(blockers + need_c3, [pair("C3", arm)], wait_c3,
                                "C3-family diagnostic: ai-memory with the reranker off, against C3; not a production "
                                "decision (A15.2)", final=a.final)
    for arm in C3_ORIGINAL:
        decisions[arm] = decide(blockers + need_c3, [pair("C3", arm)], wait_c3,
                                "ai-memory configuration against C3, as registered in A2 and A14 (A16.2); it runs with "
                                "the reranker off, while production C4 reranks", final=a.final)
    # 3. The embedder (F) and 4. the reranker LLM (H), against C4, subject to the reranker decision.
    fallbacks = {}
    for arm in A15_F + A15_H:
        if arm in arms:
            fell, rate = fallback_rate(arms[arm])
            fallbacks[arm] = {"questions_with_fallback": fell, "rate": rate}
        what = ("embedder: production C4 with only the embedder changed, against C4 (A15.2)" if arm in A15_F
                else "reranker LLM: C4 with only the reranker model changed, against C4 (A15, A15.2)")
        if reranker == "off":
            decisions[arm] = ("not decided: the reranker decision turned it off, so this reranker-on configuration is "
                              "not production (A15.2 precedence)")
        elif reranker == "pending":  # review P3: F waits on the reranker decision as H does
            decisions[arm] = (f"pending: {'H' if arm in A15_H else 'F'} is decided only once the reranker decision keeps it "
                              f"on (A15.2 precedence): {'; '.join(blockers + need_c3 + need_c4)}")
        elif arm in A15_H and reranker == "inconclusive":
            decisions[arm] = f"{reranker}: H is compared only once the reranker decision keeps it on (A15.2)"
        elif c4_inconclusive:
            decisions[arm] = f"inconclusive (A12, A15.2): production C4 fell back on {c4_rate:.1%} of queries"
        elif arm in finished and fallbacks.get(arm, {}).get("rate", 0) > FALLBACK_LIMIT:  # H: A15.2; F: A16.2
            decisions[arm] = (f"inconclusive (A12, {'A15.2' if arm in A15_H else 'A16.2'}): "
                              f"{fallbacks[arm]['rate']:.1%} of this arm's queries fell back")
        else:
            d = decide(blockers + need_c3 + need_c4, [pair("C4", arm)], wait_c4, what, final=a.final)
            if d.startswith("BEATS") and arm in A15_F:
                d += "; a production switch also requires the deployability gate (A15.2)"
            decisions[arm] = d + (conditional if d.startswith(("BEATS", "provisional")) else "")
    report["rerank_fallback"] |= fallbacks
    # 5. A16: memory systems against both references, Holm over the family at alpha 0.0167.
    wait_a16 = [x for x in A16_FAMILY if x not in finished]
    sub_full = scope_ids(K1, tracks["full"], subset)
    if PRODUCTION in arms and sub_full:  # review (stats F5): C4's rate on the questions K1 is compared on
        for name, ids in (("K1 subset", sub_full), ("K1 subset, official track", scope_ids(K1, tracks["official"], subset))):
            fell, rate = fallback_rate({q: arms[PRODUCTION][q] for q in ids if q in arms[PRODUCTION]})
            report["rerank_fallback"][f"{PRODUCTION} ({name})"] = {"questions_with_fallback": fell, "rate": rate}
    k1_c4_rate = max((v["rate"] for k, v in report["rerank_fallback"].items() if k.startswith(f"{PRODUCTION} (K1")), default=0.0)
    for arm in A16_FAMILY:
        if c4_inconclusive:
            decisions[arm] = f"inconclusive (A12, A16): production C4 fell back on {c4_rate:.1%} of queries"
            continue
        if arm == K1 and PRODUCTION in finished and k1_c4_rate > FALLBACK_LIMIT:
            decisions[arm] = f"inconclusive (A12, A16): production C4 fell back on {k1_c4_rate:.1%} of K1's subset queries"
            continue
        comps = [(tf["a16"].get(arm, {}).get(ref, {}).get(PRIMARY), to["a16"].get(arm, {}).get(ref, {}).get(PRIMARY))
                 for ref in (incumbent, PRODUCTION)]
        what = ("memory system (A16), against C3 and production C4 (must beat both, IUT; Holm at α = 0.0167)"
                + ("; on K1's preregistered subset" if arm == K1 else ""))
        d = decide(blockers + need_c3 + need_c4, comps, wait_a16, what, alpha=ALPHA_A16, final=a.final)
        decisions[arm] = d + (ADOPTION if d.startswith("BEATS") else "")
    # 6. The layer: must pass both families (A14, A15.2).
    d2h_status = f"D2h's A16 decision: {decisions.get(D2H, 'not decided')}"
    for arm in LAYER:
        if c4_inconclusive:
            decisions[arm] = f"inconclusive (A12, A15.2): production C4 fell back on {c4_rate:.1%} of queries"
            continue
        what = "layer candidate, against C3 and production C4 (must beat both; A14, A15.2)"
        if arm in AGENTMEMORY:
            what += "; benchmark API path"
        d = decide(blockers + need_c3 + need_c4, [pair("C3", arm), pair("C4", arm)], sorted(set(wait_c3) | set(wait_c4)), what,
                   final=a.final)
        if d.startswith("BEATS"):
            if arm in AGENTMEMORY:
                d += f"; a switch to agentmemory also requires D2h, agentmemory's shipped hook path ({d2h_status})"
            if arm in NEW_EMBEDDER:
                d += "; a production switch also requires the deployability gate (A15.2)"
            if arm not in ("A0-official-bm25", "bm25-full", "dense-qwen3") and not arm.startswith("dense-"):
                d += ADOPTION
        decisions[arm] = d
    # Descriptive-only arms.
    for arm in arms:
        if arm in DESCRIPTIVE:
            decisions[arm] = DESCRIPTIVE[arm]
        elif arm in F_FILL:
            decisions[arm] = "F cache-fill pass (reranker off): fills the cache for its F arm; no decision (A15.2)"
        elif exploratory(arm):
            decisions[arm] = "X exploratory (A15): no system accepts this cross-encoder as shipped; no decision"
        elif pooled(arm):
            decisions[arm] = "pooled-store stress run (A16): every eligible session in one store; descriptive, no decision"
        elif arm not in decisions and arm != incumbent and not arm.startswith("A1"):
            decisions[arm] = "descriptive only: not named in a family before its first run (A15.2)"
    # Among passing candidates for one setting: the largest point estimate, labelled as selected (A15.2).
    choices: dict[str, dict[str, Any]] = {}
    fv, fcl = tf["_vals"], tf["_clusters"]
    for setting, members in SETTINGS.items():
        passing = [arm for arm in members if decisions.get(arm, "").startswith("BEATS")]
        if not passing or PRODUCTION not in fv:
            continue
        est = {arm: paired(fv[arm][PRIMARY], fv[PRODUCTION][PRIMARY], fcl, stream("full", "setting-choice-c4", arm))
               for arm in passing}  # one yardstick: production C4, on the full track
        best = max(passing, key=lambda arm: est[arm]["diff"])
        pairs = {f"{x} - {y}": paired(fv[x][PRIMARY], fv[y][PRIMARY], fcl, stream("full", "A15-choice", x, y))
                 for i, x in enumerate(passing) for y in passing[i + 1:]}
        choices[setting] = {"passing": passing, "chosen": best, "chosen_estimate_vs_c4": est[best], "estimates_vs_c4": est,
                            "note": "selected: its estimate is biased upward (A15.2)", "paired": pairs}
    # The layer is one setting (review P5, F3, F4): every passing candidate of LAYER and A16, each passed in its own
    # family, ranked against C4 on one question set (K1's subset when K1 passes, else the full track).
    passing = [arm for arm in LAYER + A16_FAMILY if decisions.get(arm, "").startswith("BEATS")]
    if passing:
        common = sub_full if K1 in passing else tracks["full"]
        ccl = clusters(common, questions)

        def vec(arm: str) -> np.ndarray:
            return np.array([arms[arm][q]["metrics"]["full"][PRIMARY] for q in common], dtype=float)

        c4v = vec(PRODUCTION)
        est = {arm: paired(vec(arm), c4v, ccl, stream("full", "layer-choice-c4", arm)) | {"n": len(common)}
               for arm in passing}
        best = max(passing, key=lambda arm: est[arm]["diff"])
        pairs = {f"{x} - {y}": paired(vec(x), vec(y), ccl, stream("full", "layer-choice", x, y)) | {"n": len(common)}
                 for i, x in enumerate(passing) for y in passing[i + 1:]}
        own = {arm: (tf["a16"].get(arm, {}).get(PRODUCTION, {}).get(PRIMARY) if arm in A16_FAMILY
                     else tf["vs_c4_family"].get(arm, {}).get(PRIMARY)) for arm in passing}
        choices[LAYER_SETTING] = {
            "passing": passing, "chosen": best, "chosen_estimate_vs_c4": est[best], "estimates_vs_c4": est,
            "context_estimates_vs_c4_own_scope": own,
            "question_set": "K1's 100-question subset (K1 passes)" if K1 in passing else "the full track",
            "note": "selected: its estimate is biased upward (A15.2)"
                    + ("; the choice uses K1's 100-question subset" if K1 in passing else ""),
            "paired": pairs}
    for ch in choices.values():
        ch["confirmatory"] = a.confirmatory
    if a.final:  # A16.3: the declared end of the queue; these members stay at p = 1 permanently
        report["final_declaration"] = {
            "declared": True, "never_finished": {name: fam["unfinished"] for name, fam in fam_state.items()},
            "invalid": {arm: why for arm, why in invalid.items()}}
    if not a.confirmatory:  # A15.2: only the VelaNext runs are confirmatory
        decisions = {arm: f"descriptive (not confirmatory, A15.2): {d}" for arm, d in decisions.items()}
    report["decisions"] = decisions
    report["choices"] = choices
    warm = Path(a.cachewarm) / f"{incumbent}.jsonl"
    if warm.exists() and incumbent in arms:  # A13: re-run of C3's first 31 questions (never analysed)
        reruns = [json.loads(line) for line in warm.open()]
        rep = repro_note([(arms[incumbent][r["question_id"]], r) for r in reruns if r["question_id"] in arms[incumbent]])
        report["reproducibility"] = rep
        lines += ["## Reproducibility (A13 re-run of C3 questions; counts only)", "",
                  f"{rep['questions']} questions re-run on fresh stores: identical {PRIMARY} {rep['identical_' + PRIMARY]}, "
                  f"ndcg_any@5 {rep['identical_ndcg_any@5']}, recall_all@10 {rep['identical_recall_all@10']}, "
                  f"ndcg_any@10 {rep['identical_ndcg_any@10']}; identical top-5 order {rep['identical_top5']}, "
                  f"identical full ranking {rep['identical_full_ranking']}; {rep['note']}.", ""]
    lines += ["## Oracle checks (A6)", ""]
    for (arm, track), ceiling in CEILINGS.items():
        c = report["oracle_checks"].get(arm)
        lines.append(f"- `{arm}`: MISSING or incomplete on the {track} track" if c is None else
                     f"- `{arm}`: recall_all@5 {c['recall_all@5']:.5f} vs ceiling {ceiling:.5f}, recall_any@k = 1 for "
                     f"every k: {'pass' if c['pass'] else 'FAIL'}")
    lines += ["", f"## Decisions ({'confirmatory' if a.confirmatory else 'descriptive'}; A2 rule; α: C3 family {ALPHA}, C4 family "
                  f"{ALPHA}, A16 family {ALPHA_A16}, per family and per production setting (A15.2, A16); the bound across "
                  "all settings is 0.0833)",
              "", "Declared bounds on a false production change, per setting (A16.2):", ""]
    lines += [f"- {setting}: ≤ {b['bound']} ({b['how']})" for setting, b in ERROR_BOUNDS.items()]
    lines += ["", f"Reranker decision first (A15.2 precedence): state `{reranker}`.", "", A16_DEFERRED, ""]
    lines += [f"- `{arm}`: {d}" for arm, d in sorted(decisions.items())]
    for arm, fb in report["rerank_fallback"].items():
        lines.append(f"- `{arm}` rerank fallbacks (A12): {fb['questions_with_fallback']} questions ({fb['rate']:.1%})")
    for setting, ch in choices.items():
        e = ch["chosen_estimate_vs_c4"]
        prefix = "" if a.confirmatory else "descriptive (not confirmatory, A15.2): "
        lines += ["", f"{prefix}Chosen {setting}: `{ch['chosen']}`, Δ {PRIMARY} against C4 {e['diff']:+.3f} "
                      f"[{e['ci'][0]:+.3f}, {e['ci'][1]:+.3f}] ({ch['note']})."]
        where = ch.get("question_set", "the full track")
        for name, c in ch["paired"].items():
            lines.append(f"- {name}: Δ {PRIMARY} {c['diff']:+.3f} [{c['ci'][0]:+.3f}, {c['ci'][1]:+.3f}] "
                         f"({where}, n = {c.get('n', len(tracks['full']))})")
    lines.append("")
    if a.replication:
        report["replication"], rep_lines = replication(Path(a.replication), arms, questions, tracks, a.platform,
                                                       a.replication_platform)
        lines += rep_lines
    if a.gpu_logs:
        gpu = {}
        for p in sorted(Path(a.gpu_logs).glob("gpu-*.log")):
            stats = gpu_utilization(p)
            if stats:
                gpu[p.stem.removeprefix("gpu-")] = stats
        report["gpu_utilization"] = gpu
        if gpu:
            lines += ["## GPU utilization per arm (A15.1, nvidia-smi every 5 s)", "", "| arm | samples | mean GPU % |",
                      "|---|---|---|"] + [f"| {arm} | {g['samples']} | {g['mean_util']:.1f} |" for arm, g in gpu.items()] + [""]
        cpu = {}
        for p in sorted(Path(a.gpu_logs).glob("load-*.log")):
            stats = cpu_load(p)
            if stats:
                arm = p.stem.removeprefix("load-")
                status = Path(a.gpu_logs) / "arms" / f"{arm}.status.json"
                overlap = json.loads(status.read_text()).get("cpu_stream_active") if status.exists() else None
                cpu[arm] = stats | {"cpu_stream_active": overlap}
        report["cpu_load"] = cpu
        if cpu:  # what was measured, not what the run script intends (review: the overlap is recorded per arm)
            lines += ["## Host load per arm (every 5 s)", "",
                      "| arm | samples | mean 1-min load | lowest available memory (GiB) | CPU stream running |",
                      "|---|---|---|---|---|"] + \
                     [f"| {arm} | {c['samples']} | {c['mean_load1']:.1f} | {c['min_mem_available_gib']:.1f} | "
                      f"{ {True: 'yes', False: 'no'}.get(c['cpu_stream_active'], 'not recorded') } |"
                      for arm, c in cpu.items()] + [""]
    lines += ["", "## Coverage", "", f"Platform: {a.platform}.", "",
              "| arm | rows | missing | errors | env | infra | other | deadline | status |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, c in report["coverage"].items():
        status = ("absent" if c.get("absent") else f"invalid: {invalid[arm]}" if arm in invalid else
                  "finished" if arm in finished else "incomplete")
        lines.append(f"| {arm} | {c['rows']} | {c['missing']} | {c['errors']} | {c['env_errors']} | {c['infra_errors']} | "
                     f"{c['other_errors']} | {c['deadline_errors']} | {status} |")
    for t in report["tracks"].values():
        t.pop("_vals"), t.pop("_clusters")
    out = Path(a.out)
    out.with_suffix(".json").write_text(json.dumps(report, indent=1, default=float))
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return report


if __name__ == "__main__":
    main()
