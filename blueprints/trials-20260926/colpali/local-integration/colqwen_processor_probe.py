#!/usr/bin/env python3
"""Diagnose the ColQwen2Processor TypeError of the ColPali trial (attempts 5 and 6).

Local integration probe, not an upstream test: it calls upstream library functions
(transformers.utils.hub.list_repo_templates and colpali-engine's processor
from_pretrained) directly, in the trial's environment (vidore-benchmark 5.0.0 with its
colpali-engine extra, colpali-engine 0.3.13, transformers 4.53.1), on CPU, with a fresh
private HF_HOME. It downloads processor/tokenizer files only, never model weights.

Each step prints one JSON line with the outcome. Expected outcomes are written before
the run so a wrong diagnosis shows up as a mismatch:
  A  list_repo_templates on the current main of vidore/colqwen2-v1.0 returns the template
     file name WITH its .jinja suffix (the caller then appends .jinja a second time).
  B  ColQwen2Processor.from_pretrained("vidore/colqwen2-v1.0") (main, as the 5.0.0 CLI
     calls it) raises the attempts' TypeError.
  C  the same call at 83a0134c (the last revision before the repository added
     additional_chat_templates/sentence_transformers.jinja on 2026-08-17) succeeds.
  D  ColQwen2_5_Processor.from_pretrained("vidore/colqwen2.5-v0.2") at the trial's pinned
     revision dcbe8d9c (which also carries that template file) raises the same TypeError.
  E  the same call at 6f6fcdfd (the last colqwen2.5-v0.2 revision before its template
     addition) succeeds.
"""

from __future__ import annotations

import json
import sys
import traceback
from importlib import metadata

STEPS = [
    ("A", "list_repo_templates", "vidore/colqwen2-v1.0", None, "returns ['sentence_transformers.jinja']"),
    ("B", "ColQwen2Processor", "vidore/colqwen2-v1.0", None, "TypeError"),
    ("C", "ColQwen2Processor", "vidore/colqwen2-v1.0", "83a0134c8f274b3688d8dbde26de8a5b109ad8b4", "loads"),
    ("D", "ColQwen2_5_Processor", "vidore/colqwen2.5-v0.2", "dcbe8d9cede518bce830488364ba0e40c873645b", "TypeError"),
    ("E", "ColQwen2_5_Processor", "vidore/colqwen2.5-v0.2", "6f6fcdfd1a114dfe365f529701b33d66b9349014", "loads"),
]


def emit(record: dict) -> None:
    print(json.dumps(record, sort_keys=True), flush=True)


def last_frames(error: BaseException, count: int = 2) -> list[str]:
    frames = traceback.extract_tb(error.__traceback__)[-count:]
    # Package-relative locations only; no host paths.
    result = []
    for frame in frames:
        path = frame.filename.replace("\\", "/")
        marker = "site-packages/"
        path = path.split(marker, 1)[1] if marker in path else path.rsplit("/", 1)[-1]
        result.append(f"{path}:{frame.lineno} in {frame.name}")
    return result


def main() -> int:
    emit({"step": "env", "python": sys.version.split()[0], **{
        name: metadata.version(name)
        for name in ("transformers", "huggingface_hub", "colpali_engine", "vidore_benchmark", "torch")}})
    from transformers.utils.hub import list_repo_templates
    from colpali_engine.models import ColQwen2_5_Processor, ColQwen2Processor

    classes = {"ColQwen2Processor": ColQwen2Processor, "ColQwen2_5_Processor": ColQwen2_5_Processor}
    mismatches = 0
    for step, what, repo, revision, expected in STEPS:
        record = {"step": step, "call": what, "repo": repo, "revision": revision or "main", "expected": expected}
        try:
            if what == "list_repo_templates":
                value = list_repo_templates(repo, local_files_only=False, revision=revision)
                record.update(outcome="returned", value=value)
                ok = value == ["sentence_transformers.jinja"]
            else:
                processor = classes[what].from_pretrained(repo, revision=revision)
                record.update(outcome="loaded", processor_class=type(processor).__name__,
                              has_score=hasattr(processor, "score"),
                              has_process_images=hasattr(processor, "process_images"),
                              has_process_queries=hasattr(processor, "process_queries"))
                ok = expected == "loads"
        except Exception as error:  # noqa: BLE001 - the probe records every failure
            record.update(outcome="raised", error_type=type(error).__name__,
                          message=str(error)[:200], frames=last_frames(error))
            ok = expected == type(error).__name__
        record["matches_expected"] = ok
        mismatches += 0 if ok else 1
        emit(record)
    emit({"step": "summary", "mismatches": mismatches})
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
