#!/usr/bin/env python3
"""Helpers for the VelaNext lane (setup_velanext.sh, run_velanext.sh). Standard library only, except where noted.

    lane_tools.py fetch-hf    [--select serve,mteb,rerank,minilm] download pinned Hugging Face files and verify them
                                                                  (needs huggingface_hub: the embed venv)
    lane_tools.py verify-hf   [--select ...]                     re-verify the pinned files in the HF cache
    lane_tools.py install-minilm --lme-home DIR --node-modules DIR...  copy the verified MiniLM files for C2, D2, D2h
    lane_tools.py verify-ollama MODELS_DIR                       check every pinned Ollama manifest and GGUF digest
    lane_tools.py gguf-blob MODELS_DIR NAME                      print the GGUF blob path of a pinned Ollama model
    lane_tools.py official-rows --logs DIR --out DIR             official runner logs -> harness rows (official venv)
    lane_tools.py arm-status ROWS [--limit-fallback 0.05] [--subset FILE]  rows, duplicates, error classes; exit 3
                                                                  on a stop condition (env errors, >1% infra/other,
                                                                  >1% degraded questions, fallbacks)
    lane_tools.py v3-equivalence A B                             identical rankings, or exit 1 (A15.2)
    lane_tools.py subsample [--n 100]                            the deployability gate's fixed question subsample
    lane_tools.py deployability --reference G --candidate G [--rows-reference R --rows-candidate R]
    lane_tools.py proxy-snapshot URL OUT [--since T]             the A13 proxy's /__stats, saved
    lane_tools.py vendor-parse --ai-memory DIR --agentmemory DIR [--mempalace FILE] [--amb FILE] --results DIR --out FILE
    lane_tools.py sanitize SRC DST                               copy for commit: redact, then refuse leftovers
    lane_tools.py check-private FILE...                          exit 1 on a home path, UUID or token
    lane_tools.py receipt --out FILE [--results DIR] [--logs DIR]  the environment receipt (A15)
    lane_tools.py k1-subset --data FILE [--out FILE | --check FILE]  K1's preregistered stratified subset (A16)
    lane_tools.py pooled-pick --results DIR                      the top two systems' arms for the pooled run (A16)
    lane_tools.py m1-rows --log FILE --out DIR                   MemPalace's own bench log -> rows rescored with the
                                                                  official evaluator (M1, A16; official venv)
    lane_tools.py modelfile-args FILE                            a pinned Modelfile's parameters as llama-server flags
    lane_tools.py ollama-check BINARY                            the pinned Ollama: path, sha256, Go vcs.revision
    lane_tools.py v3-shim HOME --official D --aimem B --agentmemory D  the paths the verbatim v3 hard-codes, as links
    lane_tools.py llama-placement LOG [--props JSON] --tag TAG   the effective context and GPU/CPU placement of a
                                                                  llama-server LLM, from its log (A16 open item)
"""
import argparse
import base64
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "pins.json").read_text())
# Review (pins P3, lane F8): the lane installs everything under its own prefix and never touches the workstation's
# production layout (~/.local/share/agent-ecosystem: its ollama/current, models and tools).
BENCH = Path(os.environ.get("LME_BENCH_ROOT", Path.home() / ".local/share/lme-bench"))
V3_CHECK_IDS = HERE / "reference/v3-check-ids.txt"
SELECT = {  # which pinned Hugging Face files each lane stage needs
    "serve": ("E1, F1", "E2, F2", "E3, F3", "G0 ("),
    "mteb": ("mteb LMEB",),
    "rerank": ("X (",),
    "minilm": ("C2 (", "D2, D2h"),
    "data": ("mteb LMEB LongMemEval task data",),
    "hindsight": ("K1 (",),
}
FALLBACK_LIMIT = 0.05
ERROR_CAP = 0.01
PRIVATE = [
    (re.compile(r"/(?:Users)/[^/\s\"']+"), "a macOS home path"),
    (re.compile(r"/(?:home)/[^/\s\"']+"), "a Linux home path"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "a UUID"),
    (re.compile(r"\b(hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}|"
                r"xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})\b"), "a token"),
    (re.compile(r"(?i)\bbearer\s+(?!lme-bench-token\b)[A-Za-z0-9._-]{16,}"), "a bearer token"),
]


# ---------------------------------------------------------------- pins and checksums

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_sha1_file(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def file_ok(path: Path, spec: dict) -> bool:
    if not path.exists():
        return False
    if "sha256" in spec:
        return sha256_file(path) == spec["sha256"]
    return git_sha1_file(path) == spec["git_sha1"]


def selected(select: str) -> list[tuple[str, str, dict, str]]:
    """(repo, revision, entry, kind) for the chosen stages."""
    wanted = [marker for key in select.split(",") for marker in SELECT[key]]
    out = []
    for kind, table in (("model", PINS["hf_models"]), ("dataset", PINS.get("hf_datasets", {}))):
        for key, entry in table.items():
            if any(m in entry["role"] for m in wanted):
                repo, rev = key.split("@")
                out.append((repo, rev, entry, kind))
    return out


def fetch_hf(select: str, verify_only: bool = False, pin_main: bool = False) -> int:
    """Download (or re-verify) the pinned files. With pin_main, refs/main names the pinned revision, so a program
    that loads a model by name alone (Hindsight's SentenceTransformer and CrossEncoder, A16) resolves exactly the
    pinned snapshot offline (HF_HUB_OFFLINE=1)."""
    bad = 0
    for repo, rev, entry, kind in selected(select):
        if pin_main and not verify_only:
            from huggingface_hub import constants
            ref = Path(constants.HF_HUB_CACHE) / f"{kind}s--{repo.replace('/', '--')}" / "refs/main"
            ref.parent.mkdir(parents=True, exist_ok=True)
            ref.write_text(rev)
        for name, spec in entry["files"].items():
            if verify_only:
                from huggingface_hub import try_to_load_from_cache
                path = try_to_load_from_cache(repo, name, revision=rev, repo_type=kind)
                path = Path(path) if isinstance(path, str) else None
            else:
                from huggingface_hub import hf_hub_download
                path = Path(hf_hub_download(repo, name, revision=rev, repo_type=kind))
            ok = path is not None and file_ok(path, spec)
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {repo}@{rev[:10]} {name}", flush=True)
    print(f"{bad} file(s) failed verification")
    return 1 if bad else 0


def install_minilm(lme_home: Path, node_modules: list[Path]) -> int:
    """Copy the verified MiniLM files: ai-memory's local embedder (C2) and agentmemory's transformers.js cache (D2)."""
    from huggingface_hub import try_to_load_from_cache
    bad = 0
    for key, dests in (("sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                        [lme_home / "models/all-MiniLM-L6-v2"]),
                       ("Xenova/all-MiniLM-L6-v2@751bff37182d3f1213fa05d7196b954e230abad9",
                        [nm / "@huggingface/transformers/.cache/Xenova/all-MiniLM-L6-v2" for nm in node_modules])):
        repo, rev = key.split("@")
        for name, spec in PINS["hf_models"][key]["files"].items():
            src = try_to_load_from_cache(repo, name, revision=rev)
            if not isinstance(src, str) or not file_ok(Path(src), spec):
                print(f"BAD {repo} {name}: not in the verified cache (run fetch-hf --select minilm)")
                bad += 1
                continue
            for dest in dests:
                target = dest / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not (target.exists() and file_ok(target, spec)):
                    shutil.copyfile(src, target)
                print(f"ok  {target}")
    return 1 if bad else 0


def ollama_manifest_path(models: Path, name: str) -> Path:
    if name.startswith("hf.co/"):
        repo_tag = name.removeprefix("hf.co/")
        repo, tag = repo_tag.rsplit(":", 1)
        return models / "manifests" / "hf.co" / repo / tag
    model, tag = name.split(":") if ":" in name else (name, "latest")
    return models / "manifests" / "registry.ollama.ai" / "library" / model / tag


def verify_ollama(models: Path, names: list[str] | None = None) -> int:
    bad = 0
    for name, pin in PINS["ollama_models"].items():
        if names and name not in names:
            continue
        path = ollama_manifest_path(models, name)
        problems = []
        if not path.exists():
            problems.append("not pulled")
        else:
            raw = path.read_bytes()
            if "manifest" in pin and "sha256:" + hashlib.sha256(raw).hexdigest() != pin["manifest"]:
                problems.append("manifest digest differs")
            layers = {layer["mediaType"].rsplit(".", 1)[-1]: layer for layer in json.loads(raw)["layers"]}
            model = layers.get("model", {})
            if model.get("digest") != pin["gguf"]:
                problems.append(f"GGUF layer {model.get('digest', '')[:19]} is not {pin['gguf'][:19]}")
            for kind, digest in (pin.get("layers") or {}).items():  # review pins P5: template, params, license
                if layers.get(kind, {}).get("digest") != digest:
                    problems.append(f"{kind} layer differs from {digest[:19]}")
            blob = models / "blobs" / pin["gguf"].replace(":", "-")
            if not blob.exists() or blob.stat().st_size != pin["size"]:
                problems.append("GGUF blob missing or of the wrong size")
        bad += bool(problems)
        print(f"{'ok ' if not problems else 'BAD'} {name} {'; '.join(problems)}", flush=True)
    return 1 if bad else 0


# ---------------------------------------------------------------- rows

def read_rows(path: Path) -> tuple[dict, list]:
    rows, dups = {}, []
    for line in path.open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["question_id"] in rows:
            dups.append(r["question_id"])
        rows[r["question_id"]] = r
    return rows, dups


def arm_status(path: Path, scope: list[str], fallback_limit: float | None = None) -> dict:
    """The run script's stop conditions (LANE.md): env errors, over 1% infra or unclassified errors, duplicates,
    and, for arms that rerank, more than 5% fallbacks (A12)."""
    rows, dups = read_rows(path) if path.exists() else ({}, [])
    errors = [rows[q]["error"] for q in scope if q in rows and rows[q].get("error")]
    env = sum(e.startswith("env:") for e in errors)
    deadline = sum(e.startswith("deadline:") for e in errors)
    nonenv = len(errors) - env - deadline
    fell = sum(1 for r in rows.values() if any(r.get(k, 0) for k in ("rerank_timeouts", "rerank_failures", "rerank_invalid")))
    degraded = sum(1 for q in scope if q in rows and rows[q].get("failed_operations"))  # A16 K1: failed retains
    st = {"rows": len(rows), "missing": sum(q not in rows for q in scope), "duplicates": sorted(set(dups)),
          "env_errors": env, "deadline_errors": deadline, "infra_or_other_errors": nonenv,
          "fallback_questions": fell, "fallback_rate": fell / max(len(rows), 1), "degraded_questions": degraded,
          "deadline_rate": deadline / max(len(scope), 1)}
    reasons = []
    if env:
        reasons.append(f"{env} env errors (A4: the arm is invalid until a full rerun)")
    if nonenv > ERROR_CAP * len(scope):
        reasons.append(f"{nonenv} infra or unclassified errors, over 1% (suspected environment-wide fault)")
    if dups:
        reasons.append(f"duplicate rows for {len(set(dups))} questions")
    if degraded > ERROR_CAP * len(scope):
        reasons.append(f"{degraded} questions with failed memory operations, over 1% (suspected environment fault)")
    if fallback_limit is not None and st["fallback_rate"] > fallback_limit:
        reasons.append(f"{st['fallback_rate']:.1%} rerank fallbacks, over {fallback_limit:.0%} (A12)")
    st["stop"] = reasons
    st["warnings"] = ([f"{deadline} deadline rows, over 1% (scored failures under A4; check for a stalled service)"]
                      if deadline > ERROR_CAP * len(scope) else [])
    return st


def v3_equivalence(a: Path, b: Path, ids: list[str]) -> dict:
    """A15.2: v4 must reproduce v3's rankings exactly on the listed questions. Each listed question must be in both
    files, once, without an error and with a non-empty ranking, and the rankings must be equal (review P6)."""
    if not ids:
        return {"identical": False, "checked": [], "reasons": {"*": "no question ids to check"}}
    ra, da = read_rows(a) if a.exists() else ({}, [])
    rb, db_ = read_rows(b) if b.exists() else ({}, [])
    reasons = {}
    for q in ids:
        if q not in ra or q not in rb:
            reasons[q] = "missing"
        elif q in da or q in db_:
            reasons[q] = "duplicate rows"
        elif ra[q].get("error") or rb[q].get("error"):
            reasons[q] = f"error row: {ra[q].get('error') or rb[q].get('error')}"[:200]
        elif not ra[q].get("ranking") or not rb[q].get("ranking"):
            reasons[q] = "empty ranking"
        elif ra[q]["ranking"] != rb[q]["ranking"]:
            reasons[q] = "rankings differ"
    return {"identical": not reasons, "checked": list(ids), "reasons": reasons}


def gate_status(gates: Path, ids: list[str] | None = None) -> dict:
    """The gates a confirmatory arm or report needs (A6, A15.2): the oracle ceilings, and v4 reproducing v3 on the
    20 C1 and 20 B1 questions, each file present and passing (review P6)."""
    ids = ids or V3_CHECK_IDS.read_text().split()
    problems, hashes = [], {}
    for name in ("oracle.json", "v3-v4-aimem-fts.json", "v3-v4-bm25-full.json"):
        path = gates / name
        if not path.exists():
            problems.append(f"{name} missing")
            continue
        hashes[name] = sha256_file(path)
        try:
            d = json.loads(path.read_text())
        except ValueError:
            problems.append(f"{name} unreadable")
            continue
        if name == "oracle.json":
            if not d or not all(isinstance(c, dict) and c.get("pass") for c in d.values()):
                problems.append("oracle ceilings not reached")
        elif not d.get("identical") or d.get("checked") != ids:
            problems.append(f"{name}: v4 does not reproduce v3 on the listed questions")
    return {"pass": not problems, "problems": problems, "sha256": hashes}


K1_SEED, K1_SIZE = 20260925, 100


def k1_subset(types: dict[str, str], n: int = K1_SIZE, seed: int = K1_SEED) -> dict:
    """A16: K1's preregistered subset of the full-session track, stratified by question type (seed 20260925).

    Proportional allocation by largest remainder (exact fractions; ties go to the type name that sorts first);
    inside each type the questions with the smallest sha256("<seed>:<question id>") are taken. No random
    number generator is involved, so the subset is the same on every Python and library version.
    """
    strata: dict[str, list[str]] = {}
    for qid, qtype in types.items():
        strata.setdefault(qtype, []).append(qid)
    total = len(types)
    exact = {t: Fraction(n * len(ids), total) for t, ids in strata.items()}
    quota = {t: math.floor(x) for t, x in exact.items()}
    for t in sorted(strata, key=lambda t: (-(exact[t] - quota[t]), t))[:n - sum(quota.values())]:
        quota[t] += 1

    def key(qid: str) -> str:
        return hashlib.sha256(f"{seed}:{qid}".encode()).hexdigest()

    chosen = {t: sorted(sorted(ids, key=key)[:quota[t]]) for t, ids in strata.items()}
    return {"amendment": "A16", "seed": seed, "size": n, "population": total,
            "population_track": "full_session_track (eligible-manifest.json)",
            "method": "proportional allocation by question type (largest remainder, ties by type name); within each "
                      "type the smallest sha256('<seed>:<question_id>')",
            "quotas": dict(sorted(quota.items())), "strata": {t: sorted(ids) for t, ids in sorted(strata.items())},
            "question_ids": sorted(q for ids in chosen.values() for q in ids)}


def subsample(full_ids: list[str], n: int = 100) -> list[str]:
    """The deployability gate's fixed subsample (A15.2): the n full-track ids with the smallest sha256(id)."""
    return sorted(full_ids, key=lambda q: hashlib.sha256(f"A15.2 deployability {q}".encode()).hexdigest())[:n]


def deployability(reference: dict, candidate: dict, threshold: float, rows_ref: dict | None = None,
                  rows_cand: dict | None = None, ids: list[str] | None = None) -> dict:
    """A15.2: the deployable artifact reproduces the reference gate vectors (cosine >= 0.999) and stays within
    1 pp of the reference recall_all@5 on the fixed 100-question subsample."""
    def vectors(g):
        gv = g["gate_vectors"]
        return gv["texts_sha256"], [list(memoryview(base64.b64decode(v)).cast("f")) for v in gv["vectors_b64"]]
    ta, va = vectors(reference)
    tb, vb = vectors(candidate)
    if ta != tb:
        return {"pass": False, "reason": "different gate texts"}
    cos = [sum(x * y for x, y in zip(u, v, strict=True)) / math.sqrt(sum(x * x for x in u) * sum(y * y for y in v))
           for u, v in zip(va, vb, strict=True)]
    out = {"min_cosine": min(cos), "vectors_pass": min(cos) >= threshold}
    if rows_ref is not None and rows_cand is not None:
        if not ids:
            return out | {"pass": False, "reason": "no subsample ids for the row comparison"}
        missing = [q for q in ids if q not in rows_ref or q not in rows_cand]
        if missing:
            return out | {"pass": False, "reason": f"{len(missing)} subsample questions missing"}
        mean = {name: sum(r[q]["metrics"]["full"]["recall_all@5"] for q in ids) / len(ids)
                for name, r in (("reference", rows_ref), ("candidate", rows_cand))}
        out |= {"subsample": len(ids), "recall_all@5": mean, "delta_pp": 100 * (mean["candidate"] - mean["reference"]),
                "subsample_pass": abs(mean["candidate"] - mean["reference"]) <= 0.01}
    out["pass"] = out["vectors_pass"] and out.get("subsample_pass", True)
    return out


# ---------------------------------------------------------------- A16

A16_SYSTEMS = {"ai-memory": ["aimem-qwen3", "aimem-qwen3-rerank"], "agentmemory": ["am-minilm-hooks"],
               "MemPalace": ["mempalace-palace"], "Hindsight": ["hindsight-qwen3.6"]}
LLM_INGEST = {"Hindsight"}  # A16.1: systems that run an LLM on every ingest
C4_ARM, K1_ARM = "aimem-qwen3-rerank", "hindsight-qwen3.6"
POOLED_LIMIT_S = 24 * 3600  # A16.1


def point_estimate(rows: dict, c4: dict, scope: list[str]) -> float:
    """The confirmatory point estimate (A15.2, A16): full-track recall_all@5 against production C4 on the arm's
    own scope (its paired mean difference; C4 against itself is 0)."""
    return sum(rows[q]["metrics"]["full"]["recall_all@5"] - c4[q]["metrics"]["full"]["recall_all@5"]
               for q in scope) / len(scope)


def pooled_ingest_estimate(rows: dict, scope: list[str], pool_size: int, budget_s: float,
                           sessions_of: dict[str, int] | None = None) -> dict:
    """A16.1: pooled ingest time from the K1 per-session rate. The rate comes from rows that finished ingest; rows
    that hit the ingest deadline (errors "deadline: ingest...") are counted at the full budget with their haystack's
    session count, as a lower bound on the rate, and the larger estimate is used. A query deadline is not an ingest
    deadline. Session counts come from each row, or from the dataset (sessions_of) when a row has none."""
    def n(q: str) -> int:
        return int(rows[q].get("sessions") or (sessions_of or {}).get(q) or 0)

    done = [q for q in scope if q in rows and not rows[q].get("error") and n(q) and rows[q].get("ingest_s") is not None]
    late = [q for q in scope if q in rows and str(rows[q].get("error") or "").startswith("deadline: ingest")]
    spent = sum(rows[q]["ingest_s"] for q in done)
    finished = spent / sum(n(q) for q in done) if done else None
    bound = ((spent + budget_s * len(late)) / max(sum(n(q) for q in done + late), 1)) if (done or late) else None
    rates = [x for x in (finished, bound) if x is not None]
    rate = max(rates) if rates else None
    return {"rate_s_per_session": rate, "rate_finished_rows": finished, "rate_lower_bound_with_deadlines": bound,
            "rows_finished": len(done), "rows_ingest_deadline": len(late),
            "sessions_ingest_deadline": sum(n(q) for q in late), "pool_sessions": pool_size,
            "estimate_s": rate * pool_size if rate is not None else None, "limit_s": POOLED_LIMIT_S}


def pooled_pick(results: Path, full_ids: list[str], subset_ids: list[str], pool_size: int, n: int = 2,
                k1_budget_s: float = 180 * 60, sessions_of: dict[str, int] | None = None) -> dict:
    """A16.1: the pooled-store run covers the top two systems by the confirmatory point estimate. Each system is
    represented by its best finished, valid arm (C3 or C4 for ai-memory, D2h, M2, K1). A16.3: every system is
    scored against C4 on one question set, K1's subset when K1 is a candidate, else the full track. A system that
    runs an LLM on every ingest is replaced by the next system when its estimated pooled ingest, from its K1
    per-session rate, exceeds 24 hours."""
    c4_path = results / f"{C4_ARM}.jsonl"
    if not c4_path.exists():
        return {"picked": [], "ranked": [], "skipped": [], "reason": "production C4 has no rows"}
    c4, _ = read_rows(c4_path)
    subset = [q for q in full_ids if q in set(subset_ids)]
    valid: dict[str, dict[str, Any]] = {}
    for system, arms in A16_SYSTEMS.items():
        for arm in arms:
            p = results / f"{arm}.jsonl"
            if not p.exists():
                continue
            own = subset if arm == K1_ARM else full_ids
            st = arm_status(p, own)
            if st["missing"] or st["stop"] or any(q not in c4 for q in own):
                continue
            valid[arm] = {"system": system, "rows": read_rows(p)[0], "own": own}
    common = subset if K1_ARM in valid else full_ids  # A16.3: one question set for every candidate
    ranked: list[dict[str, Any]] = []
    for system in A16_SYSTEMS:
        best: dict[str, Any] | None = None
        for arm, v in valid.items():
            if v["system"] != system:
                continue
            est = point_estimate(v["rows"], c4, common)
            if best is None or est > best["estimate_vs_c4"]:
                best = {"system": system, "arm": arm, "estimate_vs_c4": est, "question_set": len(common),
                        "estimate_vs_c4_own_scope": point_estimate(v["rows"], c4, v["own"]),
                        "_rows": v["rows"], "_scope": v["own"]}
        if best:
            ranked.append(best)
    ranked.sort(key=lambda b: (-b["estimate_vs_c4"], b["system"]))
    picked, skipped = [], []
    for b in ranked:
        if len(picked) == n:
            break
        if b["system"] in LLM_INGEST:
            b["pooled_ingest"] = pooled_ingest_estimate(b["_rows"], b["_scope"], pool_size, k1_budget_s, sessions_of)
            est = b["pooled_ingest"]["estimate_s"]
            if est is None or est > POOLED_LIMIT_S:
                skipped.append({k: v for k, v in b.items() if not k.startswith("_")} |
                               {"reason": "estimated pooled ingest over 24 h (A16.1)" if est else "no ingest rate"})
                continue
        picked.append(b)
    clean = [{k: v for k, v in b.items() if not k.startswith("_")} for b in ranked]
    return {"picked": [{k: v for k, v in b.items() if not k.startswith("_")} for b in picked], "ranked": clean,
            "skipped": skipped, "question_set": "K1's subset" if common is subset else "the full track",
            "rule": "A16.1 and A16.3: top two by the point estimate against C4 on one question set; an LLM-on-ingest "
                    "system over 24 h of estimated pooled ingest is replaced by the next"}


def modelfile_args(path: Path) -> tuple[int, list[str]]:
    """A pinned Modelfile's PARAMETER lines as llama-server flags: (per-slot context, sampling flags)."""
    flags = {"temperature": "--temp", "top_k": "--top-k", "top_p": "--top-p", "min_p": "--min-p",
             "presence_penalty": "--presence-penalty", "repeat_penalty": "--repeat-penalty"}
    ctx, out = None, []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[0] != "PARAMETER":
            continue
        if parts[1] == "num_ctx":
            ctx = int(parts[2])
        elif parts[1] in flags:
            out += [flags[parts[1]], parts[2]]
        else:
            raise SystemExit(f"{path}: no llama-server flag for PARAMETER {parts[1]}")
    if ctx is None:
        raise SystemExit(f"{path}: no num_ctx")
    return ctx, out


PLACEMENT = re.compile(r"llama_params_fit|load_tensors: (offloaded|\s+\S+ model buffer size)|llama_context: (n_ctx|n_seq_max|"
                       r"n_ctx_seq|flash_attn)|llama_kv_cache|memory breakdown|\|\s+- (CUDA|Host)|-ot |override|"
                       r"tensor .* buffer type overridden")


def llama_placement(log: str, props: dict | None, tag: str) -> dict:
    """The effective context and GPU/CPU placement of an LLM served by llama-server (A16: H1, H2 and K1's LLM with
    MoE expert offload), from the server's own log lines and /props."""
    lines = [ln.strip() for ln in log.splitlines() if PLACEMENT.search(ln)]
    overridden = sum("buffer type overridden" in ln for ln in lines)
    ctx = next((int(m.group(1)) for ln in lines if (m := re.search(r"n_ctx_seq\s*=\s*(\d+)", ln))), None)
    offloaded = next((m.group(0) for ln in lines if (m := re.search(r"offloaded \d+/\d+ layers to GPU", ln))), None)
    out = {"tag": tag, "server": "llama.cpp llama-server (expert offload by --fit)", "n_ctx_seq": ctx,
           "layers_offloaded": offloaded, "tensors_overridden_to_cpu": overridden,
           "log_lines": [ln for ln in lines if "buffer type overridden" not in ln][:80]}
    if props:
        settings = props.get("default_generation_settings") or {}
        out["props"] = {"n_ctx": settings.get("n_ctx") or props.get("n_ctx"), "total_slots": props.get("total_slots"),
                        "model_path": Path(str(props.get("model_path", ""))).name,
                        "params": {k: (settings.get("params") or {}).get(k) for k in
                                   ("temperature", "top_k", "top_p", "min_p", "presence_penalty", "repeat_penalty")}}
    return out


# ---------------------------------------------------------------- vendor harnesses

def vendor_parse(aimem_dir: Path | None, am_dir: Path | None, results: Path, full_ids: list[str],
                 m1_log: Path | None = None, amb: Path | None = None, subset_ids: list[str] | None = None) -> dict:
    """Each vendor's own LongMemEval harness, run unmodified, next to the lane's metric for the same configuration."""
    out = {"ai_memory": {}, "agentmemory": {}, "mempalace": {}, "hindsight": {}}
    if m1_log and m1_log.exists():  # A16 M1: MemPalace raw mode, its own session recall_any@k over its questions
        entries = [json.loads(line) for line in m1_log.open() if line.strip()]
        sess = [e["retrieval_results"]["metrics"]["session"] for e in entries]
        own = {k: sum(m[k] for m in sess) / len(sess) for k in ("recall_any@5", "recall_any@10") if sess}
        ids = set(full_ids)
        ours = [m for e, m in zip(entries, sess, strict=True) if e["question_id"] in ids]
        m1 = results / "m1-mempalace-raw.jsonl"
        rescored = None
        if m1.exists():
            rows, _ = read_rows(m1)
            inside = [q for q in full_ids if q in rows]
            if inside:
                rescored = {k: sum(rows[q]["metrics"]["full"][k] for q in inside) / len(inside)
                            for k in ("recall_any@5", "recall_all@5")} | {"n": len(inside)}
        out["mempalace"]["raw"] = {"harness": own | {"n": len(sess)},
                                   "harness_recall_any_at_5_on_our_470": (sum(m["recall_any@5"] for m in ours) / len(ours))
                                   if ours else None,
                                   "published": PINS["mempalace"]["published"],
                                   "ours_official_evaluator": rescored,
                                   "note": "benchmarks/longmemeval_bench.py --mode raw, unmodified (its R@5 is session "
                                           "recall_any@5 over all 500 questions); rescored by the official evaluator on "
                                           "the eligible manifest as m1-mempalace-raw"}
    if amb and amb.exists():  # A16: Hindsight's agent-memory-benchmark (AMB), LLM-judged QA accuracy
        rep = json.loads(amb.read_text())
        per_q = {r["query_id"]: r for r in rep.get("results", [])}
        ids = [q for q in (subset_ids or []) if q in per_q]
        k1 = results / "hindsight-qwen3.6.jsonl"
        ours = None
        if k1.exists():
            rows, _ = read_rows(k1)
            inside = [q for q in (subset_ids or []) if q in rows]
            if inside:
                ours = {k: sum(rows[q]["metrics"]["full"][k] for q in inside) / len(inside)
                        for k in ("recall_any@5", "recall_all@5")} | {"n": len(inside)}
        out["hindsight"]["amb"] = {"harness": {"accuracy": rep.get("accuracy"), "correct": rep.get("correct"),
                                               "total_queries": rep.get("total_queries")},
                                   "harness_accuracy_on_k1_subset": (sum(bool(per_q[q].get("correct")) for q in ids) / len(ids))
                                   if ids else None, "n": len(ids),
                                   "published": PINS["hindsight"]["amb"]["published"],
                                   "ours": {"hindsight-qwen3.6": ours},
                                   "note": "AMB at Hindsight's own AMB_REF, unmodified, hindsight-http against K1's server; "
                                           "answer and judge by the local Qwen3.6 (the published runs use Gemini), so the "
                                           "accuracy is a reproduction under a different judge, not the published figure"}
    ours = {}
    for arm in ("aimem-fts", "aimem-minilm", "am-keyless", "am-minilm"):
        p = results / f"{arm}.jsonl"
        if p.exists():
            rows, _ = read_rows(p)
            ids = [q for q in full_ids if q in rows]
            if ids:
                ours[arm] = {k: sum(rows[q]["metrics"]["full"][k] for q in ids) / len(ids)
                             for k in ("recall_any@5", "recall_any@10", "recall_all@5")} | {"n": len(ids)}
    for mode, arm in (("none", "aimem-fts"), ("local", "aimem-minilm")):
        reports = sorted((aimem_dir / mode).glob("*-retrieval/report.json")) if aimem_dir else []
        if reports:
            rep = json.loads(reports[-1].read_text())
            overall = rep.get("slices", {}).get("overall", {})
            out["ai_memory"][mode] = {"harness": {"hit_at": overall.get("hit_at"), "recall_at": overall.get("recall_at"),
                                                  "n": overall.get("n") or overall.get("questions")},
                                      "published": PINS["ai_memory"]["vendor_eval"]["published"],
                                      "ours": {arm: ours.get(arm)},
                                      "note": "the harness scores LongMemEval-S v1 (not the cleaned set) with its own "
                                              "exclusions; hit@k is recall_any@k"}
    for mode, arm in (("bm25", "am-keyless"), ("hybrid", "am-minilm")):
        # Review (pins P2): only the lane's own copy, taken from a run that wrote it after the stage started; the
        # checkout's tracked benchmark/data files are the vendor's committed results and are never read.
        p = am_dir / f"{mode}.json" if am_dir else None
        if p and p.exists():
            rep = json.loads(p.read_text())
            per_q = {r["question_id"]: r for r in rep.get("per_question", [])}
            ids = [q for q in full_ids if q in per_q]
            restricted = sum(per_q[q]["recall_any_at_5"] for q in ids) / len(ids) if ids else None
            out["agentmemory"][mode] = {"harness": {k: rep.get(k) for k in ("questions", "recall_any_at_5", "recall_any_at_10",
                                                                            "ndcg_at_10", "mrr")},
                                        "harness_recall_any_at_5_on_our_470": restricted,
                                        "published": PINS["agentmemory"]["vendor_bench"]["published"],
                                        "ours": {arm: ours.get(arm)},
                                        "note": "in-process indexes, whole sessions (first 512 characters embedded); "
                                                "the harness keeps abstention questions"}
    return out


# ---------------------------------------------------------------- sanitizing

def find_private(text: str) -> list[str]:
    """Where private-looking text is, never the text itself (review, lane F5: a printed match leaks a token)."""
    out = []
    for rx, what in PRIVATE:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
            out.append(f"{what} at line {line}, column {col}")
    return out


def redact(text: str, home: str) -> str:
    if home and home != "/":
        text = text.replace(home, "~")
    text = re.sub(r"/(home|Users)/[^/\s\"']+", "~", text)
    return PRIVATE[2][0].sub("<uuid>", text)


def sanitize(src: Path, dst: Path) -> list[str]:
    """Copy SRC into DST for commit: text files redacted (home paths, usernames, UUIDs). Fails closed (review,
    lane F5): the copy is built in a staging directory beside DST and moved into place only when nothing private
    is left; otherwise nothing is written to DST and only the files, kinds and positions are returned."""
    home = os.path.expanduser("~")
    problems = []
    dst.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{dst.name}.stage-", dir=dst.parent))
    try:
        for p in sorted(src.rglob("*")):
            if p.is_dir() or p.name.endswith((".lock", ".partial", ".sqlite", ".sqlite-wal", ".sqlite-shm")):
                continue
            rel = p.relative_to(src)
            try:
                text = p.read_text()
            except UnicodeDecodeError:
                problems.append(f"{rel}: binary file not copied")
                continue
            clean = redact(text, home)
            found = find_private(clean)
            problems += [f"{rel}: {x}" for x in found]
            if not found:
                target = stage / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(clean)
        if problems:
            return problems
        if dst.exists():
            shutil.rmtree(dst)
        os.replace(stage, dst)
        return []
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ---------------------------------------------------------------- receipt

def run(cmd: list[str], timeout: float = 60, env: dict | None = None) -> str:
    """stdout and stderr (llama-server prints its version on stderr; review, lane F7)."""
    try:
        return subprocess.run(cmd, capture_output=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              timeout=timeout, env=None if env is None else os.environ | env).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"unavailable: {type(e).__name__}"


def layout(bench: Path | None = None) -> dict:
    """Every lane path under the lane's own prefix, derived from the pins (the scripts use the same names)."""
    b = bench or BENCH
    am = PINS["ai_memory"]
    return {"bench": b, "lme_home": Path(os.environ.get("LME_HOME", b / "longmemeval")),
            "uv": b / f"tools/uv-{PINS['uv']['version']}/uv",
            "node": b / f"tools/node-v{PINS['node']['version']}/bin/node",
            "llama": b / f"tools/llama.cpp-{PINS['llama_cpp']['build']}",
            "ai_memory_dir": b / f"tools/ai-memory-{am['workspace_version']}+{am['commit'][:7]}",
            "ai_memory_src": b / "src/ai-memory", "rustc": b / "tools/rust/cargo/bin/rustc",
            "agentmemory": b / "agentmemory", "iii": b / "agentmemory/bin/iii",
            "ollama": b / f"ollama/v{PINS['ollama']['version']}/bin/ollama", "ollama_models": b / "ollama/models",
            "amb": b / "src/agent-memory-benchmark"}


def stamps(bench: Path) -> dict:
    """The archive digest or commit recorded next to each installed tree (setup_velanext.sh stamp files)."""
    return {str(p.relative_to(bench)): p.read_text().strip() for p in sorted(bench.glob("**/.archive-sha256"))
            if "node_modules" not in p.parts}


def ollama_on_disk(models: Path) -> dict:
    """The manifest and layer digests actually in the lane's store for every pinned model (review pins P5)."""
    out = {}
    for name in PINS["ollama_models"]:
        path = ollama_manifest_path(models, name)
        if not path.exists():
            out[name] = None
            continue
        raw = path.read_bytes()
        layers = {layer["mediaType"].rsplit(".", 1)[-1]: layer["digest"] for layer in json.loads(raw)["layers"]}
        out[name] = {"manifest": "sha256:" + hashlib.sha256(raw).hexdigest(), "layers": layers}
    return out


def receipt(results: Path | None, logs: Path | None) -> dict:
    lay = layout()
    lme = lay["lme_home"]
    gpu = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,pci.bus_id", "--format=csv,noheader"])
    smi = run(["nvidia-smi"])
    cuda = re.search(r"CUDA Version:\s*([\d.]+)", smi)
    rec = {"platform": "VelaNext (WSL2)", "os": run(["sh", "-c", ". /etc/os-release && echo $PRETTY_NAME"]),
           "kernel": platform.release(), "machine": platform.machine(),
           "cpu": run(["sh", "-c", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2"]).strip(),
           "logical_cpus": os.cpu_count(),
           "memory_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
           if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names else None,
           "gpu": gpu.split(", ")[0] if gpu else None, "gpu_driver": gpu.split(", ")[1] if gpu.count(",") >= 1 else None,
           "gpu_memory": gpu.split(", ")[2] if gpu.count(",") >= 2 else None, "cuda_driver_api": cuda.group(1) if cuda else None,
           "repo_commit": run(["git", "-C", str(HERE), "rev-parse", "HEAD"]),
           "repo_dirty": bool(run(["git", "-C", str(HERE), "status", "--porcelain", "--", "."])),
           "files_sha256": {p.name: sha256_file(p) for p in sorted(HERE.glob("*.py")) + [HERE / "pins.json", HERE / "embed_gates.json",
                                                                                     HERE / "eligible-manifest.json", HERE / "PREREGISTRATION.md",
                                                                                     HERE / "k1-subset.json"]},
           "pins": {k: PINS[k] for k in ("dataset", "official", "ai_memory", "agentmemory", "iii", "ollama", "llama_cpp", "node", "uv",
                                         "mempalace", "hindsight", "python")},
           "ollama_models": PINS["ollama_models"],
           "hf_revisions": {k: v["role"] for k, v in PINS["hf_models"].items()},
           "layout": {k: str(v) for k, v in lay.items()}, "install_stamps": stamps(lay["bench"])}
    llama_env = {}
    if (lay["llama"] / "LD_LIBRARY_PATH").exists():
        llama_env = {"LD_LIBRARY_PATH": (lay["llama"] / "LD_LIBRARY_PATH").read_text().strip()}
    tools = {"ai_memory": ([str(lay["ai_memory_dir"] / "ai-memory"), "--version"], None),
             "iii": ([str(lay["iii"]), "--version"], None),
             "ollama": ([str(lay["ollama"]), "--version"], None),
             "node": ([str(lay["node"]), "--version"], None),
             "llama_server": ([str(lay["llama"] / "llama-server"), "--version"], llama_env),
             "uv": ([str(lay["uv"]) if lay["uv"].exists() else "uv", "--version"], None),
             "rustc": ([str(lay["rustc"]), "--version"], None)}
    rec["versions"] = {k: run(cmd, env=env) for k, (cmd, env) in tools.items()}
    rec["uv_binary"] = str(lay["uv"]) if lay["uv"].exists() else "uv on PATH (the pinned uv is missing)"
    binaries = {"ai_memory": lay["ai_memory_dir"] / "ai-memory", "ollama": lay["ollama"],
                "llama_server": lay["llama"] / "llama-server"}
    rec["binaries"] = {k: {"realpath": str(v.resolve()), "sha256": sha256_file(v.resolve())} if v.exists() else None
                       for k, v in binaries.items()}
    rec["ollama_on_disk"] = ollama_on_disk(lay["ollama_models"])
    rec["ollama_binary"] = ollama_check(lay["ollama"]) if lay["ollama"].exists() else None
    rec["ai_memory_source"] = {"commit": run(["git", "-C", str(lay["ai_memory_src"]), "rev-parse", "HEAD"]),
                               "dirty": bool(run(["git", "-C", str(lay["ai_memory_src"]), "status", "--porcelain"])),
                               "SOURCE": (lay["ai_memory_dir"] / "SOURCE").read_text()
                               if (lay["ai_memory_dir"] / "SOURCE").exists() else None}
    probe = ("import json, sys, importlib.metadata as m\n"
             "out = {'python': sys.version.split()[0]}\n"
             "for p in ('torch', 'transformers', 'sentence-transformers', 'numpy', 'mteb', 'huggingface-hub', 'openai',\n"
             "          'mempalace', 'chromadb', 'onnxruntime', 'hindsight-api', 'hindsight-api-slim', 'pg0-embedded',\n"
             "          'hindsight-client', 'amb', 'setuptools', 'langdetect'):\n"
             "    try:\n        out[p] = m.version(p)\n    except m.PackageNotFoundError:\n        pass\n"
             "try:\n    import torch\n    out['torch_cuda'] = torch.version.cuda\n    out['cudnn'] = torch.backends.cudnn.version()\n"
             "    out['cuda_available'] = torch.cuda.is_available()\nexcept ImportError:\n    pass\n"
             "print(json.dumps(out))")
    venvs = {v: lme / v / "bin/python" for v in (".venv-official", ".venv-embed", ".venv-mempalace", ".venv-hindsight")}
    venvs["amb"] = lay["amb"] / ".venv/bin/python"
    for name, py in venvs.items():
        text = run([str(py), "-c", probe])
        try:
            rec[name] = json.loads(text)
        except ValueError:
            rec[name] = text
    if logs:
        def load(kind: str) -> dict:
            out = {}
            for f in sorted((logs / kind).glob("*.json")) if (logs / kind).exists() else []:
                try:
                    out[f.name] = json.loads(f.read_text())
                except ValueError:
                    out[f.name] = "unreadable"
            return out
        rec["gates"], rec["cache_stats"], rec["llm_effective"] = load("gates"), load("cache"), load("ollama")
        for g in rec["gates"].values():  # the vectors are for the deployability gate, not the receipt
            if isinstance(g, dict):
                g.pop("gate_vectors", None)
        rec["batch_invariance_max_deviation"] = {name: g.get("batch_invariance", {}).get("max_deviation")
                                                 for name, g in rec["gates"].items() if isinstance(g, dict)}
    if results:
        rec["rows"] = {p.stem: sum(1 for _ in p.open()) for p in sorted(results.glob("*.jsonl"))}
        report = results / "report.json"
        if report.exists():  # A16.3: the declared end of the queue and every member that never finished
            r = json.loads(report.read_text())
            rec["final_declaration"] = r.get("final_declaration")
    return rec


def go_vcs_revision(binary: Path) -> str | None:
    """The vcs.revision a Go binary's embedded build info records (as `go version -m` prints), read directly."""
    marker, tail = b"vcs.revision=", b""
    with binary.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            data = tail + block
            i = data.find(marker)
            if i >= 0 and len(data) >= i + len(marker) + 40:
                found = data[i + len(marker):i + len(marker) + 40]
                return found.decode() if re.fullmatch(rb"[0-9a-f]{40}", found) else None
            tail = data[-(len(marker) + 40):]
    return None


def ollama_check(binary: Path, bench: Path | None = None) -> dict:
    """The Ollama the run executes: the pinned version directory's binary, executable, and built from the pinned
    commit (its Go build info; review pins P3). An absent revision is recorded, not a failure (the asset's sha256
    was verified at setup)."""
    lay = layout(bench)
    want_dir = lay["ollama"].parent.parent.resolve()
    real = binary.resolve()
    rev = go_vcs_revision(real) if real.exists() else None
    problems = []
    if not os.access(real, os.X_OK):
        problems.append(f"{real} is not executable")
    if want_dir not in real.parents:
        problems.append(f"{real} is not under the pinned {want_dir}")
    if rev is not None and rev != PINS["ollama"]["commit"]:
        problems.append(f"built from {rev}, not the pinned {PINS['ollama']['commit']}")
    return {"realpath": str(real), "vcs_revision": rev, "pinned_commit": PINS["ollama"]["commit"],
            "sha256": sha256_file(real) if real.exists() else None, "pass": not problems, "problems": problems}


V3_PATHS = {"src/LongMemEval": "official", "tools/ai-memory-2.5.0-19b6429/ai-memory": "aimem",
            "bench/agentmemory": "agentmemory"}


def v3_shim(home: Path, official: Path, aimem: Path, agentmemory: Path) -> dict:
    """A home in which the verbatim v3 harness finds the lane's installs at the paths it hard-codes
    (~/.local/share/agent-ecosystem/...), so v3 runs unmodified without ever reading the production layout."""
    targets = {"official": official, "aimem": aimem, "agentmemory": agentmemory}
    out = {}
    for rel, key in V3_PATHS.items():
        link = home / ".local/share/agent-ecosystem" / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(targets[key])
        out[str(link.relative_to(home))] = str(targets[key])
    return out


def ram_check(meminfo: str, blob_bytes: int, headroom_gib: float) -> dict:
    """Before an LLM with CPU-offloaded experts: the WSL VM must hold the whole GGUF plus headroom (review, infra F8;
    WSL2 caps the VM at half the host's RAM unless .wslconfig sets memory=)."""
    kb = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(\w+):\s+(\d+) kB", meminfo, re.M)}
    total, avail = kb.get("MemTotal", 0) * 1024, kb.get("MemAvailable", 0) * 1024
    need = blob_bytes + int(headroom_gib * 2**30)
    return {"mem_total_gib": round(total / 2**30, 1), "mem_available_gib": round(avail / 2**30, 1),
            "blob_gib": round(blob_bytes / 2**30, 1), "headroom_gib": headroom_gib, "pass": total >= need}


def pool_size(data: Path, full_ids: list[str]) -> int:
    wanted = set(full_ids)
    seen = set()
    for q in json.loads(data.read_text()):
        if q["question_id"] in wanted:
            seen.update(q["haystack_session_ids"])
    return len(seen)


# ---------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch-hf", "verify-hf"):
        p = sub.add_parser(name)
        p.add_argument("--select", default="serve,mteb,rerank,minilm,data")
        p.add_argument("--pin-main", action="store_true", help="point refs/main at the pinned revision (A16 K1)")
    p = sub.add_parser("install-minilm")
    p.add_argument("--lme-home", required=True)
    p.add_argument("--node-modules", nargs="+", required=True)
    p = sub.add_parser("verify-ollama")
    p.add_argument("models")
    p.add_argument("names", nargs="*")
    p = sub.add_parser("gguf-blob")
    p.add_argument("models")
    p.add_argument("name")
    p = sub.add_parser("official-rows")
    p.add_argument("--logs", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("arm-status")
    p.add_argument("rows")
    p.add_argument("--track", default="full", choices=("full", "official"))
    p.add_argument("--limit-fallback", type=float)
    p.add_argument("--subset", help="score the stop conditions on this question subset (A16 K1)")
    p = sub.add_parser("v3-equivalence")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--ids-file", default=str(V3_CHECK_IDS), help="the listed questions (the gate: 20 C1 and 20 B1 ids)")
    p.add_argument("--first", type=int, help="check only the first N listed ids (the slot smoke uses 8)")
    p = sub.add_parser("gates-check")
    p.add_argument("gates")
    p = sub.add_parser("ollama-check")
    p.add_argument("binary")
    p = sub.add_parser("v3-shim")
    p.add_argument("home")
    p.add_argument("--official", required=True)
    p.add_argument("--aimem", required=True)
    p.add_argument("--agentmemory", required=True)
    p = sub.add_parser("ram-check")
    p.add_argument("blob")
    p.add_argument("--headroom-gib", type=float, default=16.0)
    p = sub.add_parser("subsample")
    p.add_argument("--n", type=int, default=100)
    p = sub.add_parser("deployability")
    p.add_argument("--reference", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--rows-reference")
    p.add_argument("--rows-candidate")
    p = sub.add_parser("proxy-snapshot")
    p.add_argument("url")
    p.add_argument("out")
    p.add_argument("--since", type=float)
    p = sub.add_parser("vendor-parse")
    p.add_argument("--ai-memory")
    p.add_argument("--agentmemory")
    p.add_argument("--mempalace", help="M1: MemPalace's own benchmark log (JSONL)")
    p.add_argument("--amb", help="AMB's result JSON for K1's subset")
    p.add_argument("--results", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("sanitize")
    p.add_argument("src")
    p.add_argument("dst")
    p = sub.add_parser("check-private")
    p.add_argument("files", nargs="+")
    p = sub.add_parser("receipt")
    p.add_argument("--out", required=True)
    p.add_argument("--results")
    p.add_argument("--logs")
    p = sub.add_parser("k1-subset")
    p.add_argument("--data", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--out")
    g.add_argument("--check")
    p = sub.add_parser("pooled-pick")
    p.add_argument("--results", required=True)
    p.add_argument("--data", required=True, help="the dataset, for the pooled session count")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("m1-rows")
    p.add_argument("--log", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("modelfile-args")
    p.add_argument("file")
    p = sub.add_parser("llama-placement")
    p.add_argument("log")
    p.add_argument("--props")
    p.add_argument("--tag", required=True)
    a = ap.parse_args()
    manifest = json.loads((HERE / "eligible-manifest.json").read_text())
    if a.cmd in ("fetch-hf", "verify-hf"):
        sys.exit(fetch_hf(a.select, verify_only=a.cmd == "verify-hf", pin_main=a.pin_main))
    elif a.cmd == "install-minilm":
        sys.exit(install_minilm(Path(a.lme_home), [Path(x) for x in a.node_modules]))
    elif a.cmd == "verify-ollama":
        sys.exit(verify_ollama(Path(a.models), a.names))
    elif a.cmd == "gguf-blob":
        blob = Path(a.models) / "blobs" / PINS["ollama_models"][a.name]["gguf"].replace(":", "-")
        if not blob.exists():
            sys.exit(f"{a.name}: {blob} is missing")
        print(blob)
    elif a.cmd == "official-rows":
        from lme_summarize import OFFICIAL_LOGS, load_questions, official_log_rows
        questions = load_questions()
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, fname in OFFICIAL_LOGS.items():
            p = Path(a.logs) / fname
            if p.exists():
                rows = official_log_rows(p, questions)
                with (out / f"{name}.jsonl").open("w") as fh:
                    for r in rows.values():
                        fh.write(json.dumps(r | {"arm": name}) + "\n")
                print(f"{name}: {len(rows)} rows")
    elif a.cmd == "arm-status":
        scope = manifest["full_session_track" if a.track == "full" else "official_track"]
        if a.subset:
            keep = set(json.loads(Path(a.subset).read_text())["question_ids"])
            scope = [q for q in scope if q in keep]
        st = arm_status(Path(a.rows), scope, a.limit_fallback)
        print(json.dumps(st))
        sys.exit(3 if st["stop"] else 0)
    elif a.cmd == "v3-equivalence":
        ids = Path(a.ids_file).read_text().split()
        if a.first:
            ids = ids[:a.first]
        elif Path(a.ids_file).resolve() == V3_CHECK_IDS.resolve() and len(ids) != 20:
            sys.exit(f"{a.ids_file}: expected the gate's 20 question ids (run as C1 and as B1), found {len(ids)}")
        res = v3_equivalence(Path(a.a), Path(a.b), ids)
        print(json.dumps(res))
        sys.exit(0 if res["identical"] else 1)
    elif a.cmd == "gates-check":
        res = gate_status(Path(a.gates))
        print(json.dumps(res))
        sys.exit(0 if res["pass"] else 1)
    elif a.cmd == "ollama-check":
        res = ollama_check(Path(a.binary))
        print(json.dumps(res))
        sys.exit(0 if res["pass"] else 1)
    elif a.cmd == "v3-shim":
        print(json.dumps(v3_shim(Path(a.home), Path(a.official), Path(a.aimem), Path(a.agentmemory))))
    elif a.cmd == "ram-check":
        res = ram_check(Path("/proc/meminfo").read_text(), Path(a.blob).stat().st_size, a.headroom_gib)
        print(json.dumps(res))
        sys.exit(0 if res["pass"] else 1)
    elif a.cmd == "subsample":
        print("\n".join(subsample(manifest["full_session_track"], a.n)))
    elif a.cmd == "deployability":
        ref, cand = json.loads(Path(a.reference).read_text()), json.loads(Path(a.candidate).read_text())
        gates = json.loads((HERE / "embed_gates.json").read_text())
        rows_ref = read_rows(Path(a.rows_reference))[0] if a.rows_reference else None
        rows_cand = read_rows(Path(a.rows_candidate))[0] if a.rows_candidate else None
        res = deployability(ref, cand, gates["deployability_min_cosine"], rows_ref, rows_cand,
                            subsample(manifest["full_session_track"]))
        print(json.dumps(res, indent=1))
        sys.exit(0 if res["pass"] else 1)
    elif a.cmd == "proxy-snapshot":
        url = a.url.rstrip("/") + "/__stats" + (f"?since={a.since}" if a.since else "")
        with urllib.request.urlopen(url, timeout=30) as resp:
            Path(a.out).write_bytes(resp.read())
    elif a.cmd == "vendor-parse":
        subset = json.loads((HERE / "k1-subset.json").read_text())["question_ids"]
        res = vendor_parse(Path(a.ai_memory) if a.ai_memory else None, Path(a.agentmemory) if a.agentmemory else None,
                           Path(a.results), manifest["full_session_track"],
                           Path(a.mempalace) if a.mempalace else None, Path(a.amb) if a.amb else None, subset)
        Path(a.out).write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    elif a.cmd == "sanitize":
        problems = sanitize(Path(a.src), Path(a.dst))
        for x in problems:
            print("PRIVATE?", x)
        sys.exit(1 if problems else 0)
    elif a.cmd == "check-private":
        found = [f"{f}: {x}" for f in a.files for x in find_private(Path(f).read_text(errors="replace"))]
        for x in found:
            print(x)
        sys.exit(1 if found else 0)
    elif a.cmd == "k1-subset":
        wanted = set(manifest["full_session_track"])
        types = {q["question_id"]: q["question_type"] for q in json.loads(Path(a.data).read_text())
                 if q["question_id"] in wanted}
        if len(types) != len(wanted):
            sys.exit(f"the dataset lacks {len(wanted) - len(types)} manifest questions")
        res = k1_subset(types)
        text = json.dumps(res, indent=1) + "\n"
        if a.out:
            Path(a.out).write_text(text)
            print(f"{a.out}: {len(res['question_ids'])} questions, quotas {res['quotas']}")
        else:
            same = json.loads(Path(a.check).read_text()) == res
            print(json.dumps({"k1_subset_reproduced": same}))
            sys.exit(0 if same else 1)
    elif a.cmd == "pooled-pick":
        subset = json.loads((HERE / "k1-subset.json").read_text())["question_ids"]
        full = manifest["full_session_track"]
        wanted = set(full)
        counts = {q["question_id"]: len(q["haystack_session_ids"]) for q in json.loads(Path(a.data).read_text())
                  if q["question_id"] in wanted}
        res = pooled_pick(Path(a.results), full, subset, pool_size(Path(a.data), full), sessions_of=counts)
        print(json.dumps(res, indent=1) if a.json else "\n".join(b["arm"] for b in res["picked"]))
    elif a.cmd == "m1-rows":
        from lme_summarize import load_questions, official_log_rows
        rows = official_log_rows(Path(a.log), load_questions())
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "m1-mempalace-raw.jsonl").open("w") as fh:
            for r in rows.values():
                fh.write(json.dumps(r | {"arm": "m1-mempalace-raw"}) + "\n")
        print(f"m1-mempalace-raw: {len(rows)} rows")
    elif a.cmd == "modelfile-args":
        ctx, flags = modelfile_args(Path(a.file))
        print(ctx, " ".join(flags))
    elif a.cmd == "llama-placement":
        props = json.loads(Path(a.props).read_text()) if a.props and Path(a.props).exists() else None
        print(json.dumps(llama_placement(Path(a.log).read_text(errors="ignore"), props, a.tag), indent=1))
    elif a.cmd == "receipt":
        rec = receipt(Path(a.results) if a.results else None, Path(a.logs) if a.logs else None)
        text = redact(json.dumps(rec, indent=1, default=str), os.path.expanduser("~"))
        Path(a.out).write_text(text)
        print(f"receipt written: {a.out}")


if __name__ == "__main__":
    main()
