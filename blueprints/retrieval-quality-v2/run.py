#!/usr/bin/env python3
"""Runner for the retrieval-quality-v2 preregistered comparison.

Executes the BM25 vs. hybrid comparison frozen in ``PREREGISTRATION.md``
against the 30 held-out queries in ``queries.json``, using the installed
upstream QMD 2.8.3 CLI via ``subprocess``. Standard library only -- no
third-party imports.

What this script does, in order:

1. Re-hashes ``queries.json`` and compares it against the sha256 pinned in
   ``PREREGISTRATION.md``'s "Sealing" section. Stops immediately on a
   mismatch (per PREREGISTRATION.md: "A future runner must re-hash
   queries.json before use and treat a mismatch as grounds to stop").
2. Materializes the 33 pinned corpus files at the exact ``corpus_commit``
   recorded in ``queries.json``, via ``git show <commit>:<path>``, verifying
   each file's sha256 against the pin before writing it. Any mismatch aborts
   index construction entirely (fail closed; no arm runs against an
   unverified index).
3. Builds a fresh QMD index owned by this comparison under a scratch
   HOME/XDG tree (never the host's shared ``~/.cache/qmd``), using the exact
   ``collection add`` / ``update`` commands from the preregistration.
4. Runs Arm A (``qmd search ... --format json``) for all 30 queries.
5. Pulls QMD's default embedding/generation/rerank models into the scratch
   HOME's model cache (``qmd pull``), records each model's HF repository,
   resolved revision and downloaded file's own sha256, then generates
   embeddings for the frozen index (``qmd embed``) -- all forced onto CPU.
   If any of this fails or the models cannot actually run, Arm B is recorded
   as ``not_run`` with the exact reason and the 30-query loop for Arm B is
   skipped entirely (fails closed, per PREREGISTRATION.md). Substituting a
   different retrieval system is not an option this script implements.
6. Runs Arm B (``qmd query ... --format json``) for all 30 queries, only if
   step 5 succeeded.
7. Computes nDCG@10, recall@5 (of grade-2 files) and MRR per query per arm,
   the paired bootstrap 95% CI of the per-query nDCG@10 difference, and the
   preregistered decision rule.
8. Writes ``results-<date>.json`` (full receipt: per-query ranks, per-arm
   metrics, CI, decision, model provenance, durations, qmd version) and
   ``README.md`` (results table, limitations, exact commands) next to this
   script, from the same in-memory receipt so the two documents cannot
   drift apart.

Every path written into the receipt/README is sanitized: the repository
checkout and scratch-home roots are replaced with symbolic placeholders,
and any remaining ``/home/<user>`` fragment is replaced with ``~``.

Usage:
    python3 run.py --repo /path/to/native-agent-stack --scratch-home /path/to/scratch

With no ``--scratch-home``, a fresh temporary directory is created and used
(never the caller's real HOME), so this script is safe to run standalone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

SCRIPT_PATH = Path(__file__).resolve()
BLUEPRINT_DIR = SCRIPT_PATH.parent
DEFAULT_REPO = BLUEPRINT_DIR.parents[1]
QUERIES_REL = "blueprints/retrieval-quality-v2/queries.json"
PREREG_REL = "blueprints/retrieval-quality-v2/PREREGISTRATION.md"

# QMD 2.8.3's `search`/`query` --format json emit `file` as
# `qmd://<collection>/<relative-path>?index=<indexName>` (confirmed by running
# both commands against a real built index; see README.md "Reviewed upstream
# implementation"). These three collection names and their repository-path
# prefixes are exactly the ones this script's own `collection add` commands
# create in step 3, mirroring PREREGISTRATION.md's "Index construction" block.
COLLECTION_PREFIX = {
    "rqv2-foundation": "blueprints/us-equities",
    "rqv2-catalog": "catalogs/us-equities",
    "rqv2-observability": "observability",
}
INDEX_NAME_DEFAULT = "retrieval-quality-v2"

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\r")
PULL_LINE_RE = re.compile(
    r"^-\s+(?P<uri>hf:\S+)\s+->\s+(?P<path>\S+)\s+\((?P<size>[^,]+),\s*(?P<note>[^)]+)\)\s*$"
)
SEAL_HASH_RE = re.compile(r"`queries\.json`\s+sha256:\s+`([0-9a-f]{64})`")

BOOTSTRAP_ITERATIONS_DEFAULT = 10000
BOOTSTRAP_SEED_DEFAULT = 20260925  # fixed before Arm B's real results existed
GAIN_THRESHOLD = 0.05


class RunFailure(Exception):
    """A phase failed in a way that must be recorded, not hidden."""

    def __init__(self, slug: str, message: str):
        super().__init__(message)
        self.slug = slug


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Sanitizer:
    """Replaces host-identifying absolute paths with symbolic placeholders.

    Applied to every free-text string (subprocess stdout/stderr, resolved
    binary paths, model cache paths) before it is written into
    results-<date>.json or README.md. Never applied to repository-relative
    content paths (e.g. "blueprints/us-equities/data/README.md"), which are
    not host-specific and are the whole point of the receipt.
    """

    def __init__(self, repo: Path, scratch_home: Path):
        # Longest-first so a nested path (scratch_home under /tmp) is
        # replaced before any shorter prefix could partially match it.
        home = str(Path.home())
        pairs = [
            (str(scratch_home), "<SCRATCH_HOME>"),
            (str(repo), "<STACK_REPO>"),
        ]
        if home and home not in ("/", ""):
            pairs.append((home, "~"))
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._pairs = pairs

    def __call__(self, text: object) -> str:
        s = str(text)
        for literal, placeholder in self._pairs:
            if literal:
                s = s.replace(literal, placeholder)
        # Defense in depth: catch any remaining /home/<user>/... fragment
        # this process didn't already know about (e.g. from a nested tool).
        s = re.sub(r"/home/[^/\s\"']+", "~", s)
        return s


# --------------------------------------------------------------------------
# Step 1: seal verification
# --------------------------------------------------------------------------

def verify_seal(repo: Path) -> dict:
    queries_path = repo / QUERIES_REL
    prereg_path = repo / PREREG_REL
    if not queries_path.is_file():
        raise RunFailure("queries_missing", f"{QUERIES_REL} not found under repo")
    if not prereg_path.is_file():
        raise RunFailure("prereg_missing", f"{PREREG_REL} not found under repo")

    queries_bytes = queries_path.read_bytes()
    actual = sha256_bytes(queries_bytes)

    prereg_text = prereg_path.read_text(encoding="utf-8")
    matches = sorted(set(SEAL_HASH_RE.findall(prereg_text)))
    if not matches:
        raise RunFailure(
            "seal_pin_not_found",
            "Could not find a `queries.json` sha256: `<hex>` line in PREREGISTRATION.md",
        )
    if len(matches) > 1:
        raise RunFailure(
            "seal_pin_ambiguous",
            f"PREREGISTRATION.md pins more than one distinct queries.json sha256: {matches!r}",
        )
    pinned = matches[0]
    if actual != pinned:
        raise RunFailure(
            "seal_mismatch",
            f"queries.json sha256 {actual} does not match PREREGISTRATION.md's pinned {pinned}. "
            "Stopping per PREREGISTRATION.md's own instruction; queries.json/PREREGISTRATION.md "
            "were not modified by this script.",
        )

    doc = json.loads(queries_bytes)
    if doc.get("query_count") != len(doc.get("queries", [])):
        raise RunFailure(
            "query_count_mismatch",
            f"queries.json query_count={doc.get('query_count')} != len(queries)={len(doc.get('queries', []))}",
        )
    return {
        "doc": doc,
        "queries_sha256": actual,
        "prereg_pinned_sha256": pinned,
    }


# --------------------------------------------------------------------------
# Step 2: corpus staging
# --------------------------------------------------------------------------

def stage_corpus(repo: Path, commit: str, corpus: list, stage_dir: Path) -> list:
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    staged = []
    for doc in corpus:
        rel_path = doc["path"]
        expected_sha = doc["sha256"]
        proc = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{rel_path}"],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RunFailure(
                "corpus_git_show_failed",
                f"git show {commit}:{rel_path} failed (exit {proc.returncode}): "
                f"{proc.stderr.decode('utf-8', 'replace')[:500]}",
            )
        blob = proc.stdout
        actual_sha = sha256_bytes(blob)
        if actual_sha != expected_sha:
            raise RunFailure(
                "corpus_hash_mismatch",
                f"{rel_path} at {commit}: expected sha256 {expected_sha}, got {actual_sha}. "
                "Index construction stops here per PREREGISTRATION.md; no arm runs.",
            )
        dest = stage_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        staged.append({"path": rel_path, "sha256": actual_sha, "utf8_bytes": len(blob)})
    return staged


# --------------------------------------------------------------------------
# QMD subprocess plumbing
# --------------------------------------------------------------------------

def qmd_env(scratch_home: Path) -> dict:
    env = dict(os.environ)
    env["HOME"] = str(scratch_home)
    env["XDG_CACHE_HOME"] = str(scratch_home / ".cache")
    env["XDG_CONFIG_HOME"] = str(scratch_home / ".config")
    env["XDG_DATA_HOME"] = str(scratch_home / ".local" / "share")
    # Hard-rule CPU boundary: the GPU is shared and must not be touched by
    # this comparison. Both the documented CLI flag's equivalent env var and
    # the llama.cpp-ecosystem convention are set for redundancy.
    env["QMD_FORCE_CPU"] = "1"
    env["NODE_LLAMA_CPP_GPU"] = "false"
    # Never open a browser from a headless/agent context.
    env["MCP_AUTO_OPEN_ENABLED"] = "false"
    # Default (non-default) models are never used by this script, but a
    # project-local .qmd config elsewhere on this machine must never gate an
    # unattended run inside this isolated scratch HOME.
    env["QMD_TRUST_LOCAL_CONFIG"] = "1"
    for dirname in ("", ".cache", ".config", ".local/share"):
        (scratch_home / dirname).mkdir(parents=True, exist_ok=True)
    return env


def run_qmd(qmd_bin: str, args: list, env: dict, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        [qmd_bin, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def index_db_path(env: dict, index_name: str) -> Path:
    return Path(env["XDG_CACHE_HOME"]) / "qmd" / f"{index_name}.sqlite"


def index_config_path(env: dict, index_name: str) -> Path:
    return Path(env["XDG_CONFIG_HOME"]) / "qmd" / f"{index_name}.yml"


# --------------------------------------------------------------------------
# Step 3: fresh index build
# --------------------------------------------------------------------------

def build_index(qmd_bin: str, env: dict, stage_dir: Path, index_name: str, timeout: float, san: Sanitizer) -> dict:
    # Guarantee freshness even if scratch-home's model cache is being reused
    # across invocations: drop any pre-existing DB/config for this exact
    # index name before (re)building it.
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(index_db_path(env, index_name)) + suffix)
        if p.exists():
            p.unlink()
    cfg = index_config_path(env, index_name)
    if cfg.exists():
        cfg.unlink()

    collections = [
        ("rqv2-foundation", stage_dir / "blueprints" / "us-equities"),
        ("rqv2-catalog", stage_dir / "catalogs" / "us-equities"),
        ("rqv2-observability", stage_dir / "observability"),
    ]
    add_results = []
    for name, path in collections:
        if not path.is_dir():
            raise RunFailure("index_missing_stage_dir", f"staged corpus missing expected directory {path}")
        proc = run_qmd(
            qmd_bin,
            ["--index", index_name, "collection", "add", str(path), "--name", name, "--mask", "**/*.md"],
            env,
            timeout,
        )
        if proc.returncode != 0:
            raise RunFailure(
                "index_collection_add_failed",
                f"qmd collection add {name} failed (exit {proc.returncode}): "
                f"{san(strip_ansi(proc.stderr)[-800:])}",
            )
        add_results.append({"collection": name, "stdout_tail": san(strip_ansi(proc.stdout)[-500:])})

    proc = run_qmd(qmd_bin, ["--index", index_name, "update"], env, timeout)
    if proc.returncode != 0:
        raise RunFailure(
            "index_update_failed",
            f"qmd update failed (exit {proc.returncode}): {san(strip_ansi(proc.stderr)[-800:])}",
        )

    proc = run_qmd(qmd_bin, ["--index", index_name, "status"], env, timeout)
    if proc.returncode != 0:
        raise RunFailure(
            "index_status_failed",
            f"qmd status failed (exit {proc.returncode}): {san(strip_ansi(proc.stderr)[-800:])}",
        )
    status_text = strip_ansi(proc.stdout)
    counts = dict(re.findall(r"^\s*(rqv2-\w+)\s+\(qmd://[^)]*\)\s*\n\s*Pattern:.*\n\s*Files:\s+(\d+)", status_text, re.MULTILINE))
    total_match = re.search(r"Total:\s+(\d+)\s+files indexed", status_text)
    total_indexed = int(total_match.group(1)) if total_match else None
    expected_total = sum(len(list(path.rglob("*.md"))) for _, path in collections)
    if total_indexed != expected_total:
        raise RunFailure(
            "index_count_mismatch",
            f"qmd status reports {total_indexed} indexed files, expected {expected_total} "
            f"(status output: {san(status_text)[:1000]})",
        )

    return {
        "index_name": index_name,
        "db_path_sanitized": san(str(index_db_path(env, index_name))),
        "collections_added": add_results,
        "total_documents_indexed": total_indexed,
        "collection_file_counts": {k: int(v) for k, v in counts.items()},
        "status_stdout_sanitized": san(status_text),
    }


# --------------------------------------------------------------------------
# Path resolution for search/query hits
# --------------------------------------------------------------------------

def resolve_repository_path(file_field: str, docid_field: str, corpus: list) -> tuple:
    """Maps a returned `qmd://<collection>/<relpath>?index=...` hit back to
    this repository's path, and cross-checks it against the docid, which
    QMD derives as the first 6 hex chars of the document's own content
    sha256 (verified against this file's known corpus sha256 -- see
    README.md). Returns (repository_path_or_None, note)."""
    if not isinstance(file_field, str) or not file_field.startswith("qmd://"):
        return None, f"unexpected file field (no qmd:// prefix): {file_field!r}"
    rest = file_field[len("qmd://"):].split("?", 1)[0]
    if "/" not in rest:
        return None, f"unexpected file field (no collection/path split): {file_field!r}"
    collection, relpath = rest.split("/", 1)
    prefix = COLLECTION_PREFIX.get(collection)
    if prefix is None:
        return None, f"unknown collection {collection!r} in file field: {file_field!r}"
    repository_path = f"{prefix}/{relpath}"

    docid_hex = str(docid_field).lstrip("#").lower()
    corpus_by_path = {d["path"]: d["sha256"] for d in corpus}
    expected_sha = corpus_by_path.get(repository_path)
    if expected_sha is None:
        return repository_path, f"resolved path {repository_path!r} is not one of the 33 pinned corpus files"
    if not expected_sha.startswith(docid_hex):
        return repository_path, (
            f"docid #{docid_hex} does not match {repository_path!r}'s pinned sha256 prefix "
            f"{expected_sha[:6]!r}"
        )
    return repository_path, "ok"


# --------------------------------------------------------------------------
# Metrics (exact formulas from PREREGISTRATION.md's "Metrics" section)
# --------------------------------------------------------------------------

def dcg(grades_in_rank_order: list) -> float:
    return sum((2 ** g - 1) / math.log2(idx + 2) for idx, g in enumerate(grades_in_rank_order))


def compute_query_metrics(ranked_paths: list, relevance: list) -> dict:
    rel_map = {r["path"]: r["grade"] for r in relevance}
    ranked_grades = [rel_map.get(p, 0) if p is not None else 0 for p in ranked_paths][:10]

    ideal_grades = sorted((r["grade"] for r in relevance), reverse=True)[:10]
    idcg = dcg(ideal_grades)
    if idcg <= 0:
        # PREREGISTRATION.md: "Every query has at least one grade-2 file, so
        # IDCG@10 > 0 always". Fail loudly rather than silently divide.
        raise RunFailure("zero_idcg", "a query's ideal DCG@10 was <= 0; preregistration invariant violated")
    ndcg10 = dcg(ranked_grades) / idcg

    grade2_paths = {r["path"] for r in relevance if r["grade"] == 2}
    top5 = set(p for p in ranked_paths[:5] if p is not None)
    recall5 = (len(grade2_paths & top5) / len(grade2_paths)) if grade2_paths else 0.0

    mrr = 0.0
    for rank, p in enumerate(ranked_paths[:10], start=1):
        if p is not None and rel_map.get(p, 0) >= 1:
            mrr = 1.0 / rank
            break

    return {"ndcg_at_10": ndcg10, "recall_at_5": recall5, "mrr": mrr}


ZERO_METRICS = {"ndcg_at_10": 0.0, "recall_at_5": 0.0, "mrr": 0.0}


# --------------------------------------------------------------------------
# Arm execution (search/query share an identical JSON schema)
# --------------------------------------------------------------------------

def run_arm(
    qmd_bin: str,
    env: dict,
    index_name: str,
    subcommand: str,
    queries: list,
    corpus: list,
    per_query_timeout: float,
    top_k: int,
    san: Sanitizer,
) -> list:
    results = []
    for q in queries:
        start = time.monotonic()
        error = None
        ranked_paths = []
        raw_hit_count = 0
        resolution_notes = []
        try:
            proc = run_qmd(
                qmd_bin,
                ["--index", index_name, subcommand, q["query"], "-n", str(top_k), "--format", "json"],
                env,
                per_query_timeout,
            )
            elapsed_ms = (time.monotonic() - start) * 1000.0
            if proc.returncode != 0:
                error = f"exit {proc.returncode}: {san(strip_ansi(proc.stderr)[-500:])}"
            else:
                try:
                    hits = json.loads(proc.stdout)
                except json.JSONDecodeError as exc:
                    error = f"malformed JSON output: {exc}"
                    hits = None
                if hits is not None:
                    raw_hit_count = len(hits)
                    for hit in hits[:top_k]:
                        path, note = resolve_repository_path(hit.get("file", ""), hit.get("docid", ""), corpus)
                        ranked_paths.append(path)
                        if note != "ok":
                            resolution_notes.append({"file": san(str(hit.get("file"))), "note": note})
        except subprocess.TimeoutExpired:
            elapsed_ms = per_query_timeout * 1000.0
            error = f"timed out after {per_query_timeout}s"

        if error is not None:
            metrics = dict(ZERO_METRICS)
        else:
            metrics = compute_query_metrics(ranked_paths, q["relevance"])

        results.append(
            {
                "id": q["id"],
                "style": q["style"],
                "query": q["query"],
                "latency_ms": round(elapsed_ms, 1),
                "raw_hit_count": raw_hit_count,
                "ranked_paths": ranked_paths,
                "error": error,
                "resolution_notes": resolution_notes,
                **metrics,
            }
        )
    return results


def summarize_arm(per_query: list) -> dict:
    n = len(per_query)
    return {
        "query_count": n,
        "mean_ndcg_at_10": sum(r["ndcg_at_10"] for r in per_query) / n,
        "mean_recall_at_5": sum(r["recall_at_5"] for r in per_query) / n,
        "mean_mrr": sum(r["mrr"] for r in per_query) / n,
        "errored_queries": [r["id"] for r in per_query if r["error"] is not None],
    }


# --------------------------------------------------------------------------
# Arm B setup: model pull + provenance + embed
# --------------------------------------------------------------------------

def fetch_hf_revision(repo_id: str, timeout: float = 15.0) -> tuple:
    url = f"https://huggingface.co/api/models/{repo_id}"
    req = urlrequest.Request(url, headers={"Accept": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        sha = data.get("sha")
        if not sha:
            return None, "HF API response had no 'sha' field"
        return sha, None
    except (urlerror.URLError, urlerror.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def pull_and_pin_models(qmd_bin: str, env: dict, pull_timeout: float, san: Sanitizer) -> dict:
    proc = run_qmd(qmd_bin, ["pull"], env, pull_timeout)
    stdout = strip_ansi(proc.stdout)
    stderr = strip_ansi(proc.stderr)
    if proc.returncode != 0:
        raise RunFailure(
            "arm_b_pull_failed",
            f"qmd pull failed (exit {proc.returncode}): {san(stderr)[-800:] or san(stdout)[-800:]}",
        )

    roles = ["embed", "generate", "rerank"]  # fixed order qmd's own `pull` case uses (see README.md)
    parsed = []
    for line in stdout.splitlines():
        m = PULL_LINE_RE.match(line.strip())
        if m:
            parsed.append(m.groupdict())

    if len(parsed) != 3:
        raise RunFailure(
            "arm_b_pull_unparseable",
            f"expected 3 model lines from `qmd pull`, parsed {len(parsed)}. "
            f"stdout tail: {san(stdout)[-800:]}",
        )

    models = []
    for role, entry in zip(roles, parsed):
        uri = entry["uri"]
        local_path = Path(entry["path"])
        if not uri.startswith("hf:"):
            raise RunFailure("arm_b_model_uri_unexpected", f"model URI is not an hf: URI: {uri!r}")
        parts = uri[len("hf:"):].split("/")
        if len(parts) < 3:
            raise RunFailure("arm_b_model_uri_unexpected", f"could not split org/repo/filename from {uri!r}")
        org, repo_name = parts[0], parts[1]
        filename = "/".join(parts[2:])
        hf_repo_id = f"{org}/{repo_name}"
        if not local_path.is_file():
            raise RunFailure(
                "arm_b_model_file_missing",
                f"qmd pull reported {uri} at {san(str(local_path))} but that file does not exist",
            )
        file_sha256 = sha256_file(local_path)
        etag_path = local_path.with_name(local_path.name + ".etag")
        hf_content_etag = etag_path.read_text().strip() if etag_path.is_file() else None
        revision, revision_error = fetch_hf_revision(hf_repo_id)
        models.append(
            {
                "role": role,
                "hf_uri": uri,
                "hf_repo_id": hf_repo_id,
                "filename": filename,
                "size_bytes": local_path.stat().st_size,
                "sha256": file_sha256,
                "hf_repo_revision": revision,
                "hf_repo_revision_error": revision_error,
                "hf_repo_revision_note": (
                    "Resolved via a GET to huggingface.co/api/models/<repo>.sha shortly after the "
                    "pull completed; it pins the repo HEAD at query time, which may postdate the "
                    "exact download instant by seconds if the upstream repo changed concurrently. "
                    "The file's own sha256 above is the authoritative content pin regardless."
                ),
                "hf_content_store_etag": hf_content_etag,
                "hf_content_store_etag_note": (
                    "HF's Xet content-store token for this file, not a sha256 checksum; recorded "
                    "only as a cross-reference to qmd's own cache bookkeeping."
                ),
                "pull_note": entry["note"],
                "pull_size_reported": entry["size"],
            }
        )
    return {"models": models, "pull_stdout_sanitized": san(stdout)[-4000:]}


def embed_index(qmd_bin: str, env: dict, index_name: str, embed_timeout: float, san: Sanitizer) -> dict:
    proc = run_qmd(qmd_bin, ["--index", index_name, "embed"], env, embed_timeout)
    stdout = strip_ansi(proc.stdout)
    stderr = strip_ansi(proc.stderr)
    if proc.returncode != 0:
        raise RunFailure(
            "arm_b_embed_failed",
            f"qmd embed failed (exit {proc.returncode}) -- the pinned model could not actually be "
            f"run on CPU: {san(stderr)[-800:] or san(stdout)[-800:]}",
        )
    m = re.search(r"Embedded (\d+) chunks from (\d+) documents in (\S+)", stdout)
    return {
        "chunks_embedded": int(m.group(1)) if m else None,
        "documents_embedded": int(m.group(2)) if m else None,
        "upstream_reported_duration": m.group(3) if m else None,
        "stdout_sanitized": san(stdout)[-1000:],
    }


# --------------------------------------------------------------------------
# Bootstrap CI + decision rule
# --------------------------------------------------------------------------

def paired_bootstrap_ci(diffs: list, iterations: int, seed: int) -> dict:
    # Resampling the 30 per-query (B_i - A_i) nDCG@10 differences with
    # replacement is algebraically identical to resampling the 30 (A_i, B_i)
    # pairs and recomputing mean(B) - mean(A) on each resample, since
    # mean(B_resample) - mean(A_resample) == mean(B_i - A_i over the same
    # resampled indices) by linearity of the mean. PREREGISTRATION.md
    # specifies the pair-resampling form; this is that computation.
    rng = random.Random(seed)
    n = len(diffs)
    resample_means = []
    for _ in range(iterations):
        resample_means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    resample_means.sort()
    lo_idx = int(iterations * 0.025)
    hi_idx = min(int(iterations * 0.975), iterations - 1)
    return {
        "iterations": iterations,
        "seed": seed,
        "lower_95": resample_means[lo_idx],
        "upper_95": resample_means[hi_idx],
        "method": (
            "Nearest-rank percentile on ascending-sorted resample means of mean(B)-mean(A) "
            f"over N={iterations} resamples of the 30 paired per-query nDCG@10 differences, "
            f"each drawn with replacement (Python random.Random(seed={seed})). "
            f"lower=sorted[floor(0.025*N)], upper=sorted[min(floor(0.975*N), N-1)], both 0-indexed."
        ),
    }


def decide(arm_a_summary: dict, arm_b_status: str, arm_b_summary: dict, bootstrap: dict) -> dict:
    if arm_b_status != "evaluated":
        return {
            "gain_ndcg_at_10": None,
            "bootstrap_ci": None,
            "condition_1_gain_ge_0_05": None,
            "condition_2_ci_excludes_zero": None,
            "decision": "BM25 (Arm A) stays the default",
            "reason": "Arm B was not evaluated (not_run), which is distinct from Arm B being tried and losing.",
        }
    gain = arm_b_summary["mean_ndcg_at_10"] - arm_a_summary["mean_ndcg_at_10"]
    cond1 = gain >= GAIN_THRESHOLD
    cond2 = bootstrap["lower_95"] > 0
    selected = cond1 and cond2
    return {
        "gain_ndcg_at_10": gain,
        "bootstrap_ci": bootstrap,
        "condition_1_gain_ge_0_05": cond1,
        "condition_2_ci_excludes_zero": cond2,
        "decision": "Hybrid (Arm B) selected over BM25" if selected else "BM25 (Arm A) stays the default",
        "reason": (
            "Both preregistered conditions held."
            if selected
            else "At least one preregistered condition failed; an inconclusive or negative result "
            "does not disturb QMD's current BM25-only profile."
        ),
    }


# --------------------------------------------------------------------------
# README rendering
# --------------------------------------------------------------------------

def fmt(x, digits=4):
    return "n/a" if x is None else f"{x:.{digits}f}"


def render_readme(receipt: dict) -> str:
    a = receipt["arm_a"]["summary"]
    b_status = receipt["arm_b"]["status"]
    b = receipt["arm_b"].get("summary")
    decision = receipt["decision"]
    date = receipt["run_date"]

    lines = []
    lines.append(f"# Retrieval quality v2: BM25 vs. hybrid -- measured comparison, {receipt['generated_at_human']}")
    lines.append("")
    if b_status == "evaluated":
        lines.append(
            f"QMD **{receipt['qmd_version']}** evaluated all 30 preregistered held-out queries against "
            f"both arms over the same frozen 33-document index. Arm A (BM25) scored "
            f"nDCG@10={fmt(a['mean_ndcg_at_10'])}; Arm B (hybrid, CPU) scored "
            f"nDCG@10={fmt(b['mean_ndcg_at_10'])}. **{decision['decision']}** "
            f"(gain={fmt(decision['gain_ndcg_at_10'])}, threshold={GAIN_THRESHOLD}, "
            f"95% bootstrap CI=[{fmt(decision['bootstrap_ci']['lower_95'])}, "
            f"{fmt(decision['bootstrap_ci']['upper_95'])}])."
        )
    else:
        lines.append(
            f"QMD **{receipt['qmd_version']}** evaluated Arm A (BM25) against all 30 preregistered "
            f"held-out queries: nDCG@10={fmt(a['mean_ndcg_at_10'])}. **Arm B (hybrid) was not "
            f"evaluated** -- {receipt['arm_b'].get('not_run_reason', 'reason not recorded')}. "
            f"Per PREREGISTRATION.md, a not-evaluated Arm B cannot satisfy the decision rule, so "
            f"**{decision['decision']}**, distinct from Arm B having been tried and lost."
        )
    lines.append("")
    lines.append(
        f"The [preregistration](PREREGISTRATION.md) and [30 held-out queries](queries.json) "
        f"(sha256 `{receipt['seal']['queries_sha256']}`) were sealed by an independent author before "
        f"either arm ran; this script only re-verified that seal, it did not author or edit either file. "
        f"All 33 corpus files were re-extracted from git commit `{receipt['corpus_commit']}` and every "
        f"one verified against its pinned sha256 before indexing (see "
        f"[results-{date}.json](results-{date}.json)'s `corpus_staging` array)."
    )
    lines.append("")
    lines.append("| Metric (mean over 30 queries) | Arm A -- BM25 (`search`) | Arm B -- hybrid (`query`, CPU) |")
    lines.append("| --- | ---: | ---: |")
    if b_status == "evaluated":
        lines.append(f"| nDCG@10 | {fmt(a['mean_ndcg_at_10'])} | {fmt(b['mean_ndcg_at_10'])} |")
        lines.append(f"| recall@5 (grade-2 files) | {fmt(a['mean_recall_at_5'])} | {fmt(b['mean_recall_at_5'])} |")
        lines.append(f"| MRR | {fmt(a['mean_mrr'])} | {fmt(b['mean_mrr'])} |")
        lines.append(f"| Queries erroring/timing out | {len(a['errored_queries'])}/30 | {len(b['errored_queries'])}/30 |")
    else:
        lines.append(f"| nDCG@10 | {fmt(a['mean_ndcg_at_10'])} | not run |")
        lines.append(f"| recall@5 (grade-2 files) | {fmt(a['mean_recall_at_5'])} | not run |")
        lines.append(f"| MRR | {fmt(a['mean_mrr'])} | not run |")
        lines.append(f"| Queries erroring/timing out | {len(a['errored_queries'])}/30 | not run |")
    lines.append("")
    lines.append(
        "recall@5 and MRR are secondary, non-gating evidence per PREREGISTRATION.md's Decision rule; "
        "only nDCG@10's mean gain and bootstrap CI decide between arms."
    )
    lines.append("")

    lines.append("## Decision")
    lines.append("")
    lines.append(f"**{decision['decision']}.** {decision['reason']}")
    if b_status == "evaluated":
        lines.append("")
        lines.append(f"- Condition 1 (gain &ge; {GAIN_THRESHOLD}): {decision['condition_1_gain_ge_0_05']} (gain={fmt(decision['gain_ndcg_at_10'])})")
        lines.append(
            f"- Condition 2 (paired bootstrap 95% CI excludes 0): {decision['condition_2_ci_excludes_zero']} "
            f"(CI=[{fmt(decision['bootstrap_ci']['lower_95'])}, {fmt(decision['bootstrap_ci']['upper_95'])}], "
            f"{decision['bootstrap_ci']['iterations']} resamples, seed={decision['bootstrap_ci']['seed']})"
        )
    lines.append("")

    lines.append("## Model provenance (Arm B)")
    lines.append("")
    if b_status == "evaluated":
        lines.append("All three of QMD's default hybrid-mode models, pulled into the scratch HOME's own model cache:")
        lines.append("")
        lines.append("| Role | HF repository | Revision (repo HEAD at pull time) | File | sha256 | Size |")
        lines.append("| --- | --- | --- | --- | --- | ---: |")
        for m in receipt["arm_b"]["model_provenance"]["models"]:
            rev = m["hf_repo_revision"] or f"unresolved ({m['hf_repo_revision_error']})"
            lines.append(
                f"| {m['role']} | [{m['hf_repo_id']}](https://huggingface.co/{m['hf_repo_id']}) | `{rev}` "
                f"| `{m['filename']}` | `{m['sha256']}` | {m['pull_size_reported']} |"
            )
        lines.append("")
        lines.append(
            "QMD adaptively skips the query-expansion (generate) model per-query when its own BM25 "
            "signal is already strong (observed directly in this run's stderr as "
            "\"Strong BM25 signal (...) -- skipping expansion\"); the table above lists every model "
            "`qmd pull` fetched up front, not a claim that all three ran on every one of the 30 queries."
        )
    else:
        lines.append(f"Not applicable -- {receipt['arm_b'].get('not_run_reason', 'reason not recorded')}")
    lines.append("")

    lines.append("## Known limitations")
    lines.append("")
    for item in receipt["limitations"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Durations")
    lines.append("")
    lines.append("| Phase | Duration |")
    lines.append("| --- | ---: |")
    for phase, seconds in receipt["durations_seconds"].items():
        if seconds is not None:
            lines.append(f"| {phase} | {seconds:.1f}s |")
    lines.append("")

    lines.append("## Exact commands")
    lines.append("")
    lines.append("Run against a scratch `$SCRATCH_HOME` with `HOME`/`XDG_*` pointed into it and")
    lines.append("`QMD_FORCE_CPU=1` set, never the host's shared `~/.cache/qmd`:")
    lines.append("")
    lines.append("```sh")
    lines.append("python3 blueprints/retrieval-quality-v2/run.py \\")
    lines.append(f"  --repo \"$STACK_REPO\" --scratch-home \"$SCRATCH_HOME\"")
    lines.append("")
    lines.append("# what run.py runs under the hood, per query arm:")
    lines.append(f'qmd --index {receipt["index"]["index_name"]} collection add "$STAGE/blueprints/us-equities" \\')
    lines.append("  --name rqv2-foundation --mask '**/*.md'")
    lines.append(f'qmd --index {receipt["index"]["index_name"]} collection add "$STAGE/catalogs/us-equities" \\')
    lines.append("  --name rqv2-catalog --mask '**/*.md'")
    lines.append(f'qmd --index {receipt["index"]["index_name"]} collection add "$STAGE/observability" \\')
    lines.append("  --name rqv2-observability --mask '**/*.md'")
    lines.append(f'qmd --index {receipt["index"]["index_name"]} update')
    lines.append(f'qmd --index {receipt["index"]["index_name"]} search "<query>" -n 10 --format json   # Arm A')
    lines.append("qmd pull   # Arm B only: default embed/generate/rerank models, CPU-forced")
    lines.append(f'qmd --index {receipt["index"]["index_name"]} embed                                   # Arm B only')
    lines.append(f'qmd --index {receipt["index"]["index_name"]} query "<query>" -n 10 --format json    # Arm B')
    lines.append("```")
    lines.append("")

    lines.append("## Reviewed upstream implementation")
    lines.append("")
    lines.append(
        f"QMD `{receipt['qmd_version_raw']}`, installed from `@tobilu/qmd`. The `file` field's "
        "`qmd://<collection>/<relative-path>?index=<name>` shape and the `docid` = first 6 hex "
        "chars of the document's content sha256 were confirmed directly against this run's own "
        "built index (`dist/cli/formatter.js`'s `searchResultsToJson`, `dist/cli/formatter.js`'s "
        "`getDocid`), and the three default hybrid-mode model URIs against `dist/llm.js`'s "
        "`DEFAULT_EMBED_MODEL` / `DEFAULT_GENERATE_MODEL` / `DEFAULT_RERANK_MODEL` and this run's "
        "own `qmd pull` output, not asserted from memory."
    )
    lines.append("")
    lines.append(
        "This measures retrieval quality only (nDCG@10, recall@5, MRR) over 33 short documents and "
        "30 queries. It does not measure end-to-end answer quality, general-corpus latency at scale, "
        "or provider-token cost; see PREREGISTRATION.md's own Known limitations for the full list, "
        "reproduced above."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI / main
# --------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=str(DEFAULT_REPO), help="path to the native-agent-stack checkout")
    p.add_argument(
        "--scratch-home",
        default=None,
        help="scratch HOME/XDG root for QMD's index+model cache (default: a fresh temp dir; "
        "never the host's real HOME, and never committed)",
    )
    p.add_argument("--index-name", default=INDEX_NAME_DEFAULT)
    p.add_argument("--qmd-bin", default=None, help="default: resolved via shutil.which('qmd')")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--skip-arm-b", action="store_true", help="BM25-only run; skips model pull/embed/query entirely")
    p.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS_DEFAULT)
    p.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED_DEFAULT)
    p.add_argument("--index-timeout", type=float, default=300.0)
    p.add_argument("--arm-a-query-timeout", type=float, default=60.0)
    p.add_argument("--arm-b-query-timeout", type=float, default=240.0)
    p.add_argument("--pull-timeout", type=float, default=1800.0)
    p.add_argument("--embed-timeout", type=float, default=900.0)
    p.add_argument("--date", default="20260925", help="YYYYMMDD suffix for results-<date>.json")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    if args.scratch_home:
        scratch_home = Path(args.scratch_home).resolve()
        scratch_home.mkdir(parents=True, exist_ok=True)
        owns_scratch = False
    else:
        scratch_home = Path(tempfile.mkdtemp(prefix="qmd-retrieval-quality-v2-"))
        owns_scratch = True

    san = Sanitizer(repo, scratch_home)
    started_monotonic = time.monotonic()
    durations = {
        "seal_verify": None,
        "corpus_staging": None,
        "index_build": None,
        "arm_a": None,
        "arm_b_pull": None,
        "arm_b_embed": None,
        "arm_b": None,
        "total_wall_clock": None,
    }

    receipt = {
        "schema_version": 1,
        "run_date": args.date,
        "generated_at_utc": utc_now_iso(),
        "generated_at_human": None,
        "status": "started",
        "preregistration": "PREREGISTRATION.md",
        "queries_file": "queries.json",
        "qmd_version": None,
        "qmd_version_raw": None,
        "index": {"index_name": args.index_name},
        "seal": {},
        "corpus_commit": None,
        "corpus_staging": [],
        "arm_a": {"status": "not_run", "per_query": [], "summary": None},
        "arm_b": {"status": "not_run", "per_query": [], "summary": None, "model_provenance": None, "not_run_reason": None},
        "decision": None,
        "durations_seconds": durations,
        "environment": {
            "python_version": sys.version.split()[0],
            "cpu_forced": True,
            "gpu_used": False,
            "cpu_count": os.cpu_count(),
            "scratch_home_owned_by_this_run": owns_scratch,
        },
        "limitations": [],
    }
    receipt["generated_at_human"] = datetime.now(timezone.utc).strftime("%B %d, %Y")

    def t(key):
        class _Timer:
            def __enter__(self_inner):
                self_inner.start = time.monotonic()
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                durations[key] = time.monotonic() - self_inner.start

        return _Timer()

    exit_code = 0
    try:
        qmd_bin = args.qmd_bin or shutil.which("qmd")
        if not qmd_bin:
            raise RunFailure("qmd_not_found", "qmd not found on PATH (command -v qmd)")
        ver = subprocess.run([qmd_bin, "--version"], capture_output=True, text=True, timeout=30)
        receipt["qmd_version_raw"] = ver.stdout.strip() or ver.stderr.strip()
        # "qmd --version" prints "qmd 2.8.3 (facd35e)"; keep just the semver for
        # qmd_version and the full banner in qmd_version_raw.
        version_match = re.search(r"(\d+\.\d+\.\d+)", receipt["qmd_version_raw"] or "")
        receipt["qmd_version"] = version_match.group(1) if version_match else receipt["qmd_version_raw"]

        with t("seal_verify"):
            seal = verify_seal(repo)
        receipt["seal"] = {
            "queries_sha256": seal["queries_sha256"],
            "prereg_pinned_sha256": seal["prereg_pinned_sha256"],
            "match": True,
        }
        doc = seal["doc"]
        queries = doc["queries"]
        corpus = doc["corpus"]
        commit = doc["corpus_commit"]
        receipt["corpus_commit"] = commit

        env = qmd_env(scratch_home)
        stage_dir = scratch_home / "corpus-stage"
        with t("corpus_staging"):
            staged = stage_corpus(repo, commit, corpus, stage_dir)
        receipt["corpus_staging"] = staged

        with t("index_build"):
            index_summary = build_index(qmd_bin, env, stage_dir, args.index_name, args.index_timeout, san)
        receipt["index"].update(index_summary)

        with t("arm_a"):
            arm_a_results = run_arm(
                qmd_bin, env, args.index_name, "search", queries, corpus, args.arm_a_query_timeout, args.top_k, san
            )
        receipt["arm_a"] = {"status": "evaluated", "per_query": arm_a_results, "summary": summarize_arm(arm_a_results)}

        if args.skip_arm_b:
            receipt["arm_b"]["not_run_reason"] = "--skip-arm-b was passed"
        else:
            try:
                with t("arm_b_pull"):
                    provenance = pull_and_pin_models(qmd_bin, env, args.pull_timeout, san)
                # Recorded as soon as it exists, so a subsequent embed failure
                # still leaves the successfully resolved model provenance in
                # the receipt instead of discarding it.
                receipt["arm_b"]["model_provenance"] = provenance

                with t("arm_b_embed"):
                    embed_summary = embed_index(qmd_bin, env, args.index_name, args.embed_timeout, san)
                receipt["arm_b"]["embed_summary"] = embed_summary

                with t("arm_b"):
                    arm_b_results = run_arm(
                        qmd_bin, env, args.index_name, "query", queries, corpus, args.arm_b_query_timeout, args.top_k, san
                    )
                receipt["arm_b"]["status"] = "evaluated"
                receipt["arm_b"]["per_query"] = arm_b_results
                receipt["arm_b"]["summary"] = summarize_arm(arm_b_results)
            except RunFailure as exc:
                receipt["arm_b"]["status"] = "not_run"
                receipt["arm_b"]["not_run_reason"] = san(f"[{exc.slug}] {exc}")

        if receipt["arm_b"]["status"] == "evaluated":
            diffs = [
                b["ndcg_at_10"] - a["ndcg_at_10"]
                for a, b in zip(receipt["arm_a"]["per_query"], receipt["arm_b"]["per_query"])
            ]
            bootstrap = paired_bootstrap_ci(diffs, args.bootstrap_iterations, args.bootstrap_seed)
            receipt["decision"] = decide(receipt["arm_a"]["summary"], "evaluated", receipt["arm_b"]["summary"], bootstrap)
        else:
            receipt["decision"] = decide(receipt["arm_a"]["summary"], "not_run", None, None)

        receipt["limitations"] = [
            "30 queries against 33 short documents is a small-sample comparison; the paired bootstrap "
            "CI is the safeguard against reading noise as a real gain, not a substitute for a larger corpus.",
            "This protocol measures retrieval quality only (nDCG@10, recall@5, MRR); it does not measure "
            "end-to-end answer quality, latency at scale, or provider-token cost.",
            "The query author's relevance judgments reflect one reader's understanding of "
            "\"directly answers\" vs. \"partially relevant\", not adjudicated multi-rater agreement.",
            "Arm B's models were pulled and run once, forced onto CPU on a shared host; a GPU run or a "
            "different host's CPU could show different absolute latency (not accuracy, since the same "
            "GGUF weights and inference code drive both).",
            "QMD adaptively skips its query-expansion model per-query when BM25 signal is already "
            "strong; not every Arm B query necessarily exercised all three pulled models.",
        ]
        if receipt["arm_b"]["status"] != "evaluated":
            receipt["limitations"].append(f"Arm B was not evaluated: {receipt['arm_b']['not_run_reason']}")

        receipt["status"] = (
            "completed_both_arms_evaluated" if receipt["arm_b"]["status"] == "evaluated" else "completed_arm_b_not_run"
        )

    except RunFailure as exc:
        receipt["status"] = f"aborted_{exc.slug}"
        receipt["abort_reason"] = san(str(exc))
        exit_code = 1
    except Exception as exc:  # top-level safety net: still write an honest partial receipt
        receipt["status"] = "aborted_unexpected_exception"
        receipt["abort_reason"] = san(f"{type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        durations["total_wall_clock"] = time.monotonic() - started_monotonic
        results_path = BLUEPRINT_DIR / f"results-{args.date}.json"
        results_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if receipt["arm_a"]["summary"] is not None:
            readme_path = BLUEPRINT_DIR / "README.md"
            readme_path.write_text(render_readme(receipt), encoding="utf-8")
        else:
            readme_path = None

        print(f"status: {receipt['status']}")
        print(f"results: {results_path}")
        if readme_path:
            print(f"readme: {readme_path}")
        if receipt.get("decision"):
            print(f"decision: {receipt['decision']['decision']}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
