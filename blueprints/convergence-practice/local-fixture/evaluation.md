# Frozen public-document retrieval replay

This is an executed integration fixture using the unchanged Agent Retrieval Bench
v0.2.1 lexical and BM25 APIs, not a held-out external benchmark or a live native
search acceptance check. The independently authored fixture selected 15 public
repository documents and froze 24 natural questions before ranking. The author
could read the documents; neither queries, labels nor cutoffs were tuned after
seeing these results. All source bytes come from the immutable native-agent-stack
commit `bf99d340f798bf72cc3104619edc482882eb423d`.

| Native ranker | Positive denominator | Recall@1 | Recall@3 | Recall@5 | Full-ranking MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical | 20 | 0.80 | 1.00 | 1.00 | 0.90 |
| BM25 | 20 | 0.95 | 1.00 | 1.00 | 0.9666666667 |

Recall is the macro mean of each case's fraction of exact gold file paths found
within the first k unique file paths. Each of these 20 positives has one gold
file. MRR uses the first gold file in the full ranking. Cutoffs 1, 3 and 5 were
chosen before scoring this small corpus; Recall@20 would be trivial for 15 files.
There is no significance or general superiority claim. The paired mean differences
(BM25 minus lexical) are +0.15 Recall@1 and +0.0666666667 MRR, with zero difference
at Recall@3 and Recall@5.

Four expected-abstention cases have no gold file and are explicitly excluded from
the positive metric denominator. Both native rankers returned all 15 files for
each of those four cases. Their complete rankings are retained, with `metrics:
null`. There is no abstention policy, score threshold, abstention accuracy, answer
generation or answer-quality assessment. The fixture's `boundary_files` are
explanatory labels and never become gold targets.

The maximum raw document character length, 9,777, was selected as the chunk size
before scoring. Native `chunks_for_file` produced exactly 15 file chunks and the
recipe checked that every normalized complete file body was preserved. Queries
were passed verbatim to the native rankers. BM25 retains native k1=1.5 and b=0.75;
lexical retains its native path/basename/symbol bonuses and unique-token
normalization. Algorithm details and exact release provenance are in the
[external evaluation](../arb-trace2code/README.md).

The two sequential ranker-loop observations were approximately 0.0673 seconds
(lexical) and 0.0738 seconds (BM25), covering their 24 rankings and metric work.
These are single warm process observations, excluding source loading, with no
controlled latency comparison. No model, provider, active index, daemon, native
account, private document or durable memory was accessed or changed.

`rankings.json` retains 48 full file rankings and the exact per-case
and macro metrics. `evaluation-receipt.json` records source/input/code hashes,
parameters and checks. The frozen questions and corpus manifest are alongside
this document; no source document bodies are copied into this packet. The very
small, source-authored corpus can establish executable integration and inspectable
retrieval behavior, not real-user retrieval quality, abstention, production search
acceptance, token savings or a new installed default.

## Reproduce with the native APIs

Use the pinned `upstream/` checkout and dependency-free `runtime/` environment from
the [external replay recipe](../arb-trace2code/README.md), in the same scratch
working directory. Confirm the checkout is clean and its HEAD is
`b487f3866cc13dd971819cb902517a6a50282404`. No optional dependencies are needed.
Point `STACK_REPOSITORY` to a clone of
[the public reference repository](https://github.com/seathatflowsinourveins/native-agent-stack)
that contains the frozen commit and this published fixture. Set
`FIXTURE_DIRECTORY` to its `blueprints/convergence-practice/local-fixture` directory
and `REPLAY_OUTPUT` to a new output file in scratch. The source working tree's
current branch is immaterial: each document is read with `git show` at the fixed
commit and checked against its exact frozen hash.

Save the following fixture-specific recipe verbatim as `local_doc_replay.py` in
scratch. Its SHA256 is
`557b8cf4b3123d3e0c3dfc9d688950d75cc446f3bc162825eff24708fa78ab4d`.
It calls the upstream chunker, rankers and metrics directly; it is not a reusable
adapter or a replacement retrieval implementation. Subprocess input is an
argument array, source paths are canonical relative paths, and a hash or corpus
mismatch stops the run. The output uses exclusive creation to preserve earlier
observations.

```python
"""Replay one frozen documentation fixture with unmodified ARB v0.2.1 APIs."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path, PurePosixPath

from agent_retrieval_bench.baseline import (
    rank_chunks_for_ranker,
    recall_at,
    sample_metrics,
    unique_ranked_paths,
)
from agent_retrieval_bench.corpus import chunks_for_file

BASE = "bf99d340f798bf72cc3104619edc482882eb423d"
FIXTURE_SHA = "aea5e9616fb19eb1d2fd58ecfadf88ff087d7d2e79b4a70bc9f88207af9d0402"
MANIFEST_SHA = "7bb986160b332e205208b6767b95b6f019423ffed1f50843534ff7e4272fdded"
REPO = "seathatflowsinourveins/native-agent-stack"


def checked_bytes(raw, expected):
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Frozen input hash mismatch")
    return raw


def source_path(value):
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts or ":" in value
            or "\\" in value or value != path.as_posix()):
        raise ValueError("Source path is not a canonical relative path")
    return value


def main():
    fixture_dir = Path(os.environ["FIXTURE_DIRECTORY"])
    source_repo = Path(os.environ["STACK_REPOSITORY"])
    output = Path(os.environ["REPLAY_OUTPUT"])
    fixture = json.loads(checked_bytes((fixture_dir / "fixture.json").read_bytes(), FIXTURE_SHA))
    manifest = json.loads(checked_bytes(
        (fixture_dir / "corpus-manifest.json").read_bytes(), MANIFEST_SHA))
    if fixture["base_commit"] != BASE or manifest["base_commit"] != BASE:
        raise ValueError("Frozen base commit mismatch")
    documents = []
    for item in manifest["files"]:
        path = source_path(item["path"])
        raw = subprocess.run(
            ["git", "-C", str(source_repo), "show", f"{BASE}:{path}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        ).stdout
        checked_bytes(raw, item["source_sha256"])
        if len(raw) != item["utf8_bytes"]:
            raise ValueError("Frozen document length mismatch")
        documents.append((path, raw.decode("utf-8")))
    paths = {path for path, _ in documents}
    if len(documents) != 15 or len(paths) != 15 or len(fixture["queries"]) != 24:
        raise ValueError("Frozen corpus or query count mismatch")
    maximum = max(len(text) for _, text in documents)
    chunks = []
    for path, text in documents:
        native = chunks_for_file(REPO, BASE, path, text, max_chunk_chars=maximum)
        if native[0]["text"] != text.replace("\r\n", "\n").replace("\r", "\n").strip():
            raise ValueError("Native chunker did not preserve full normalized file body")
        chunks.extend(native)
    rows = []
    timings = {}
    for ranker in ("lexical", "bm25"):
        start = time.monotonic()
        for query in fixture["queries"]:
            gold = set(query["expected_files"])
            if not gold.issubset(paths) or query["expected_abstention"] != (not gold):
                raise ValueError("Frozen gold labels are inconsistent")
            ranked = rank_chunks_for_ranker(query["query"], chunks, ranker)
            files = unique_ranked_paths(ranked)
            if set(files) != paths or len(files) != 15:
                raise ValueError("Native ranking changed the candidate universe")
            metrics = None
            if gold:
                native_metrics = sample_metrics(sorted(gold), ranked)
                metrics = {f"Recall@{k}": recall_at(gold, files, k) for k in (1, 3, 5)}
                metrics["MRR"] = native_metrics["MRR"]
            rows.append({
                "sample_id": query["id"], "ranker": ranker,
                "expected_abstention": query["expected_abstention"],
                "gold_files": sorted(gold), "ranked_files": files,
                "metrics": metrics,
            })
        timings[ranker] = time.monotonic() - start
    summaries = {}
    for ranker in ("lexical", "bm25"):
        positives = [row for row in rows if row["ranker"] == ranker and row["metrics"]]
        negatives = [row for row in rows if row["ranker"] == ranker
                     and row["expected_abstention"]]
        if len(positives) != 20 or len(negatives) != 4:
            raise ValueError("Frozen positive or negative denominator mismatch")
        summaries[ranker] = {
            "positive_samples": 20, "negative_samples_excluded_from_positive_metrics": 4,
            "macro_metrics": {key: sum(row["metrics"][key] for row in positives) / 20
                              for key in ("Recall@1", "Recall@3", "Recall@5", "MRR")},
            "negative_rankings_returned": sum(bool(row["ranked_files"]) for row in negatives),
            "abstention_policy": None, "abstention_accuracy": None,
            "wall_seconds": timings[ranker],
        }
    result = {
        "schema_version": 1, "base_commit": BASE, "fixture_sha256": FIXTURE_SHA,
        "corpus_manifest_sha256": MANIFEST_SHA,
        "documents": 15, "chunks": len(chunks), "max_chunk_chars": maximum,
        "full_body_normalization": "Native CRLF/CR to LF and surrounding whitespace strip only.",
        "query_transform": "None: original fixture query string passed verbatim to native ranker.",
        "summaries": summaries, "results": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("documents", "chunks", "max_chunk_chars",
                                                "summaries")}, indent=2))


if __name__ == "__main__":
    main()
```

After setting the three environment variables above, run:

```sh
PYTHONPATH=upstream/src runtime/bin/python local_doc_replay.py
```

The executed command used those same three environment variables with private
scratch locations. Exact locations are deliberately omitted from public evidence.
Compare rankings and metrics, allowing the recorded timing values to differ.
The receipt retains the exact source file hash of this executed recipe. The input
guards were checked against changed fixture bytes, changed corpus bytes and
traversal paths before execution; known Recall and MRR examples and independent
rank-based recomputation also passed. This is a bounded documented analysis
recipe, not a new installed component or a general-purpose adapter test suite.
