"""Preregistered analysis for the LongMemEval-S retrieval tier (PREREGISTRATION.md, amendments A1-A14).

Reads results/<arm>.jsonl from lme_harness.py and the official runner's logs (A0 flat-bm25, A1 oracle),
restricts every arm to the frozen eligible manifest, and reports both tracks with cluster-bootstrap CIs,
cluster sign-flip randomization tests and Holm correction against C3 (aimem-qwen3) and, for layer candidates, production C4 (A14).

usage: python lme_summarize.py [--incumbent aimem-qwen3] [--out report]
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from lme_harness import DATA, HERE, MANIFEST, score

PRIMARY = "recall_all@5"
SECONDARY = ["ndcg_any@5", "recall_all@10", "ndcg_any@10", "recall_any@5", "recall_any@10"]
SEED = 20260924
BOOT = 10_000
PERM = 100_000
OFFICIAL_LOGS = {"A0-official-bm25": "longmemeval_s_cleaned.json_retrievallog_session_flat-bm25",
                 "A1-official-oracle": "longmemeval_s_cleaned.json_retrievallog_session_oracle"}
# The frozen comparison family against the incumbent (A4, A8, A9). C4 (rerank) joins only if complete.
FAMILY_REQUIRED = ["A0-official-bm25", "bm25-full", "dense-qwen3", "aimem-fts", "aimem-minilm",
                   "aimem-qwen3-0.6b", "aimem-qwen3-8b", "am-keyless", "am-minilm", "am-qwen3"]
FAMILY_OPTIONAL = ["aimem-qwen3-rerank"]
LAYER_CANDIDATES = {"A0-official-bm25", "bm25-full", "dense-qwen3", "am-keyless", "am-minilm", "am-qwen3"}
# A14: production reranks, so the production configuration is C4. Layer candidates must beat C3 and C4.
PRODUCTION = "aimem-qwen3-rerank"
LAYER_FAMILY = ["A0-official-bm25", "bm25-full", "dense-qwen3", "am-keyless", "am-minilm", "am-qwen3"]
RERANK_KEYS = ("rerank_timeouts", "rerank_failures", "rerank_invalid")
TRACK_ONLY = {"A1-official-oracle": "official", "A1b-full-oracle": "full"}
CEILINGS = {("A1-official-oracle", "official"): 416 / 419, ("A1b-full-oracle", "full"): 467 / 470}


def load_questions() -> dict:
    return {q["question_id"]: q for q in json.loads(DATA.read_text())}


def official_log_rows(path: Path, questions: dict) -> dict:
    """Map the official runner's ranked corpus ids back to haystack positions and score both tracks."""
    rows = {}
    for line in path.open():
        e = json.loads(line)
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


def load_arms(questions: dict, full_ids: list[str]) -> dict:
    arms = {"A1b-full-oracle": full_oracle_rows(questions, full_ids)}
    for name, fname in OFFICIAL_LOGS.items():
        p = HERE / "official-logs" / fname
        if p.exists():
            arms[name] = official_log_rows(p, questions)
    for p in sorted((HERE / "results").glob("*.jsonl")):
        rows = {}
        for line in p.open():
            r = json.loads(line)
            rows[r["question_id"]] = r
        arms[p.stem] = rows
    return arms


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


def rule(full: dict, off) -> bool:
    """The preregistered rule (A2): Holm p < 0.05, CI above 0, at least +5 pp, and official track >= -2 pp."""
    return (full["p_holm"] < 0.05 and full["ci"][0] > 0 and full["diff"] >= 0.05
            and off is not None and off["diff"] >= -0.02)


def holm(ps: dict) -> dict:
    order = sorted(ps, key=ps.get)
    adj, running = {}, 0.0
    for i, key in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * ps[key]))
        adj[key] = running
    return adj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent", default="aimem-qwen3")
    ap.add_argument("--out", default=str(HERE / "report"))
    ap.add_argument("--final", action="store_true",
                    help="the run queue has finished: optional arms that are absent leave the family (A12)")
    a = ap.parse_args()
    questions = load_questions()
    manifest = json.loads(MANIFEST.read_text())
    tracks = {"full": manifest["full_session_track"], "official": manifest["official_track"]}
    arms = load_arms(questions, tracks["full"])
    report = {"incumbent": a.incumbent, "tracks": {}, "coverage": {}, "oracle_checks": {}}
    lines = ["# LongMemEval-S retrieval tier: results", "",
             f"Dataset sha256 `{manifest['dataset_sha256'][:16]}…`; protocol PREREGISTRATION.md (A1–A14).", ""]
    for arm, rows in arms.items():
        scope = tracks[TRACK_ONLY.get(arm, "full")]
        missing = [qid for qid in scope if qid not in rows]
        errors = [rows[qid]["error"] for qid in scope if qid in rows and rows[qid].get("error")]
        report["coverage"][arm] = {"missing": len(missing), "errors": len(errors), "rows": len(rows),
                                   "env_errors": sum(1 for e in errors if e.startswith("env:"))}
    complete = {arm for arm, c in report["coverage"].items() if c["missing"] == 0}
    finished = {arm for arm in complete if not report["coverage"][arm]["env_errors"]}
    # A13: until the queue finishes, the family is its largest possible form, and every member not yet
    # finished is held at p = 1. A pass under those conditions holds for any final family.
    family = FAMILY_REQUIRED + [arm for arm in FAMILY_OPTIONAL if arm in finished or not a.final]
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
            if t == track and arm in table:
                any_ok = all(table[arm][f"recall_any@{k}"] == 1.0 for k in (5, 10))
                report["oracle_checks"][arm] = {"recall_all@5": table[arm][PRIMARY], "ceiling": ceiling,
                                                "pass": abs(table[arm][PRIMARY] - ceiling) < 1e-9 and any_ok}
        def compare(reference: str, fam: list, key: tuple) -> dict:
            out = {}
            if reference not in vals or reference not in finished:
                return out
            for arm in fam:  # the frozen family; arms not yet finished are absent, never re-sized away
                if arm in vals and arm in finished:
                    out[arm] = {m: paired(vals[arm][m], vals[reference][m], cl, stream(*key, arm, m))
                                for m in (PRIMARY, "ndcg_any@5")}
            # Holm over the full declared family: a member not yet finished counts as p = 1 (A13).
            adj = holm({arm: c[PRIMARY]["p"] for arm, c in out.items()} | {arm: 1.0 for arm in fam if arm not in out})
            for arm in out:
                out[arm][PRIMARY]["p_holm"] = adj[arm]
            return out
        comps = compare(a.incumbent, family, (track,))
        comps_prod = compare(PRODUCTION, LAYER_FAMILY, (track, PRODUCTION))
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
                                   "vs_incumbent": comps, "vs_production": comps_prod, "by_type": by_type}
        lines += [f"## {track} track (n = {len(ids)}, {cl.max() + 1} evidence clusters)", "",
                  "| arm | " + " | ".join([PRIMARY] + SECONDARY) + " |",
                  "|---|" + "---|" * (1 + len(SECONDARY))]
        for arm, mv in sorted(table.items(), key=lambda kv: -kv[1][PRIMARY]):
            lines.append(f"| {arm} | " + " | ".join(f"{mv[m]:.3f}" for m in [PRIMARY] + SECONDARY) + " |")
        for ref, cs in ((a.incumbent, comps), (f"{PRODUCTION} (production, A14)", comps_prod)):
            if not cs:
                continue
            lines += ["", f"Paired against `{ref}` (cluster bootstrap 95% CI; sign-flip p, Holm within this family):", "",
                      "| arm | Δ recall_all@5 | 95% CI | p (Holm) | Δ ndcg_any@5 | 95% CI |", "|---|---|---|---|---|---|"]
            for arm, c in sorted(cs.items(), key=lambda kv: -kv[1][PRIMARY]["diff"]):
                r, n = c[PRIMARY], c["ndcg_any@5"]
                lines.append(f"| {arm} | {r['diff']:+.3f} | [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] | "
                             f"{r['p_holm']:.4f} | {n['diff']:+.3f} | [{n['ci'][0]:+.3f}, {n['ci'][1]:+.3f}] |")
        lines += ["", f"{PRIMARY} by question type:", "", "| type | " + " | ".join(sorted(table)) + " |",
                  "|---|" + "---|" * len(table)]
        for t in sorted(by_type):
            lines.append(f"| {t} (n={next(iter(by_type[t].values()))[1]}) | " +
                         " | ".join(f"{by_type[t][arm][0]:.3f}" if arm in by_type[t] else "–" for arm in sorted(table)) + " |")
        lines.append("")
    decisions = {}
    tf, to = report["tracks"]["full"], report["tracks"]["official"]
    full, off = tf["vs_incumbent"], to["vs_incumbent"]
    fullp, offp = tf["vs_production"], to["vs_production"]
    blockers = [] if a.incumbent in finished else [f"{a.incumbent} (C3) not finished (or has env errors)"]
    blockers += [f"oracle check failed: {arm}" for arm, c in report["oracle_checks"].items() if not c["pass"]]
    unfinished = [arm for arm in family if arm not in finished]
    unfinished_prod = [arm for arm in LAYER_FAMILY if arm not in finished]
    for arm in family:
        if arm == PRODUCTION:
            continue  # the reranker decision follows
        if blockers:
            decisions[arm] = "pending: " + "; ".join(blockers)
            continue
        if arm not in full:
            decisions[arm] = "pending: arm not finished (or has env errors)"
            continue
        beats = rule(full[arm][PRIMARY], off.get(arm, {}).get(PRIMARY))
        waiting = unfinished
        if arm in LAYER_FAMILY:  # A14: must beat production (C4) as well as C3
            if PRODUCTION not in finished:
                decisions[arm] = (f"pending: production {PRODUCTION} (C4) not finished; against C3 alone it "
                                  f"{'passes' if beats else 'does not pass'} (A14)")
                continue
            beats = beats and rule(fullp[arm][PRIMARY], offp.get(arm, {}).get(PRIMARY))
            waiting = sorted(set(unfinished) | set(unfinished_prod))
            what = "layer candidate: beats C3 and production C4"
        else:
            what = "ai-memory configuration, against C3"
        if beats:
            decisions[arm] = f"BEATS ({what})" + (" — final before the family finished (A13)" if waiting else "")
        elif waiting:
            decisions[arm] = f"provisional: does not beat yet ({what}); final once {', '.join(waiting)} finish"
        else:
            decisions[arm] = f"does not beat ({what})"
    # A14 reranker decision: production (C4) keeps the reranker unless C3 beats it; A12's fallback rule applies.
    if not blockers and PRODUCTION in full:
        c, o = full[PRODUCTION][PRIMARY], off.get(PRODUCTION, {}).get(PRIMARY)
        rev = {"diff": -c["diff"], "ci": [-c["ci"][1], -c["ci"][0]], "p_holm": c["p_holm"]}
        rev_off = {"diff": -o["diff"]} if o else None
        rows = arms[PRODUCTION]
        fell = sum(1 for r in rows.values() if any(r.get(k, 0) for k in RERANK_KEYS))
        rate = fell / max(len(rows), 1)
        report["rerank_fallback"] = {"questions_with_fallback": fell, "rate": rate}
        if rate > 0.05:
            decisions[PRODUCTION] = f"reranker decision inconclusive (A12): {rate:.1%} of queries fell back"
        elif rule(rev, rev_off):
            decisions[PRODUCTION] = ("turn the reranker OFF: C3 beats production C4 (A14)"
                                     + (" — final before the family finished (A13)" if unfinished else ""))
        elif unfinished:
            decisions[PRODUCTION] = (f"provisional: keep the reranker (C3 does not beat production C4 yet); final once "
                                     f"{', '.join(unfinished)} finish")
        else:
            decisions[PRODUCTION] = "keep the reranker: C3 does not beat production C4 (A14)"
    elif PRODUCTION in family:
        decisions[PRODUCTION] = "pending: " + ("; ".join(blockers) if blockers else "C4 not finished")
    report["decisions"] = decisions
    warm = HERE / "results-cachewarm" / f"{a.incumbent}.jsonl"
    if warm.exists() and a.incumbent in arms:  # A13: re-run of C3's first 31 questions (never analysed)
        reruns = [json.loads(line) for line in warm.open()]
        pairs = [(arms[a.incumbent][r["question_id"]], r) for r in reruns if r["question_id"] in arms[a.incumbent]]
        def same(m):
            return sum(all(abs(o["metrics"][t][m] - r["metrics"][t][m]) < 1e-12 for t in ("full", "official"))
                       for o, r in pairs)
        rep = {"questions": len(pairs), "identical_full_ranking": sum(o["ranking"] == r["ranking"] for o, r in pairs),
               "identical_top5": sum(o["ranking"][:5] == r["ranking"][:5] for o, r in pairs),
               **{f"identical_{m}": same(m) for m in (PRIMARY, "ndcg_any@5", "recall_all@10", "ndcg_any@10")}}
        report["reproducibility"] = rep
        lines += ["## Reproducibility (A13 re-run of C3 questions)", "",
                  f"{rep['questions']} questions re-run on fresh stores: identical {PRIMARY} {rep['identical_' + PRIMARY]}, "
                  f"ndcg_any@5 {rep['identical_ndcg_any@5']}, recall_all@10 {rep['identical_recall_all@10']}, "
                  f"ndcg_any@10 {rep['identical_ndcg_any@10']}; identical top-5 order {rep['identical_top5']}, "
                  f"identical full ranking {rep['identical_full_ranking']}. ai-memory's lower-ranked order is not "
                  "deterministic run to run.", ""]
    lines += ["## Oracle checks (A6)", ""] + [f"- `{arm}`: recall_all@5 {c['recall_all@5']:.5f} vs ceiling "
                                               f"{c['ceiling']:.5f} — {'pass' if c['pass'] else 'FAIL'}"
                                               for arm, c in report["oracle_checks"].items()]
    lines += ["", "## Decision (preregistered rule, A2)", ""] + [f"- `{arm}`: {d}" for arm, d in sorted(decisions.items())]
    lines += ["", "## Coverage", "", "| arm | rows | missing | errors | env errors |", "|---|---|---|---|---|"] + \
             [f"| {arm} | {c['rows']} | {c['missing']} | {c['errors']} | {c['env_errors']} |"
              for arm, c in report["coverage"].items()]
    out = Path(a.out)
    out.with_suffix(".json").write_text(json.dumps(report, indent=1, default=float))
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
