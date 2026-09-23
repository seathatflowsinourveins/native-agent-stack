#!/usr/bin/env python3
"""Write the Claude lane's returns from one layer-verdict-lane workflow result.

The Claude lane runs as a Claude Code workflow (vendored byte for byte at
``examples/claude-native/workflows/layer-verdict-lane.js``; its agent-lab source
is ``.claude/workflows/layer-verdict-lane.js``). The workflow returns
``{lane, model, layers: [{catalog, layer_id, packet_sha256, final, ...}], lost}``
and writes nothing itself. This script is the step that turns that result into
``<work-dir>/claude/<catalog>__<layer_id>.json`` files for ``record_verdicts.py``,
adding the two runner-owned fields a new-wave Claude return must carry
(2026-09-23 peer audit), never taken from the model:

- ``model.family`` is ``"anthropic"``; ``model.name`` is ``--resolved-model``
  when given (the resolved child model, for example ``claude-opus-5-5`` from
  ``child-usage.mjs --latest``), else the workflow's bound alias.
- ``provenance`` is ``{workflow_path, workflow_sha256, agentlab_commit}``:
  the workflow path relative to the agent-lab checkout, the sha256 of those
  bytes, and that checkout's ``HEAD``. The script refuses (exit 2) when the
  workflow file differs from ``HEAD`` or its sha256 is not the vendored
  ``examples/claude-native/workflows/SHA256SUMS`` entry, so a return always
  names bytes a catalog-only host can rerun.

A layer whose workflow chain produced no ``final`` object, and every ``lost``
packet, is listed on stdout and gets no file: ``record_verdicts.py`` then records
that lane as ``missing`` in the run manifest. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG_ROOT = HERE.parent.parent
VENDORED_SUMS = CATALOG_ROOT / "examples" / "claude-native" / "workflows" / "SHA256SUMS"
DEFAULT_WORKFLOW = ".claude/workflows/layer-verdict-lane.js"
LANE_FAMILY = "anthropic"


class ProvenanceError(Exception):
    """The workflow bytes cannot be named reproducibly (exit 2)."""


def vendored_sums(path: Path = VENDORED_SUMS) -> dict:
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            sums[name.lstrip("*")] = digest
    return sums


def git(agentlab_root: Path, *args) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(agentlab_root), *args], capture_output=True, text=True,
                              check=False)
    except FileNotFoundError as error:
        raise ProvenanceError("git is not installed; it is needed to name the agent-lab commit") from error


def lane_provenance(agentlab_root: Path, workflow: str, sums: dict) -> dict:
    """{workflow_path, workflow_sha256, agentlab_commit} for committed, vendored workflow bytes."""
    path = agentlab_root / workflow
    if not path.is_file():
        raise ProvenanceError(f"workflow {workflow} not found under {agentlab_root}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    name = Path(workflow).name
    if sums.get(name) != digest:
        raise ProvenanceError(f"{workflow} sha256 {digest} is not the vendored SHA256SUMS entry for {name} "
                              f"({sums.get(name)}); vendor the new bytes into the catalog first")
    head = git(agentlab_root, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise ProvenanceError(f"{agentlab_root} is not a git checkout: {head.stderr.strip()}")
    if git(agentlab_root, "diff", "--quiet", "HEAD", "--", workflow).returncode != 0:
        raise ProvenanceError(f"{workflow} differs from HEAD in {agentlab_root}; commit it before recording")
    return {"workflow_path": workflow, "workflow_sha256": digest, "agentlab_commit": head.stdout.strip()}


def lane_return(layer: dict, provenance: dict, resolved_model=None) -> dict:
    data = dict(layer["final"])
    data["lane"] = "claude"
    model = dict(data.get("model") or {})
    if resolved_model:
        model["name"] = resolved_model
    model["family"] = LANE_FAMILY
    data["model"] = model
    data["provenance"] = dict(provenance)
    return data


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--result", type=Path, required=True, help="The workflow's returned JSON object.")
    parser.add_argument("--work-dir", type=Path, required=True, help="The lane_packets.py work dir.")
    parser.add_argument("--agentlab-root", type=Path, required=True, help="The agent-lab checkout the lane ran from.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow path relative to --agentlab-root.")
    parser.add_argument("--resolved-model", default=None,
                        help="Resolved child model name (e.g. claude-opus-5-5); default keeps the bound alias.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        provenance = lane_provenance(args.agentlab_root.resolve(), args.workflow, vendored_sums())
    except ProvenanceError as error:
        print(error, file=sys.stderr)
        return 2
    result = json.loads(args.result.read_text(encoding="utf-8"))
    out_dir = args.work_dir / "claude"
    out_dir.mkdir(parents=True, exist_ok=True)
    written, without_final = [], []
    for layer in result.get("layers") or []:
        name = f"{layer['catalog']}__{layer['layer_id']}.json"
        if not isinstance(layer.get("final"), dict):
            without_final.append(name)
            continue
        data = lane_return(layer, provenance, args.resolved_model)
        (out_dir / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        written.append(name)
    print(json.dumps({"written": len(written), "without_final": without_final,
                      "lost": list(result.get("lost") or []), "provenance": provenance}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
