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
- ``provenance`` is ``{workflow_path, workflow_sha256, agentlab_commit, agent_sha256}``:
  the workflow path relative to the agent-lab checkout, the sha256 of those
  bytes, and that checkout's ``HEAD``. The script refuses (exit 2) when the
  workflow file differs from ``HEAD`` or its sha256 is not the vendored
  ``examples/claude-native/workflows/SHA256SUMS`` entry, so a return always
  names bytes a catalog-only host can rerun.

The workflow's per-layer ``refutation`` summary ({status, final_source,
proposal_status, revision_status, votes}) is copied into the return as
``refutation``; ``record_verdicts.py`` rejects a new-wave Claude return without it
or whose final was not sealed unrefuted by both lens votes (2026-09-23 review of
catalog #122, finding 5).

A layer whose workflow chain produced no ``final`` object (its proposal or
revision was refuted, or a vote or the proposal never returned), and every
``lost`` packet, gets no return file; it is listed on stdout and in
``<work-dir>/claude/failures.json`` with its reason, which ``record_verdicts.py``
records as the lane's ``failed`` outcome in the run manifest. Stdlib only.
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
# The role every lane stage runs as (layer-verdict-lane.js agentType); its definition carries the blinding
# (Read/Glob/Grep, no skills, omitClaudeMd), so a return names the role bytes it ran with (Codex review of #145).
LANE_AGENT = "blind-lane-reviewer"
VENDORED_AGENT = CATALOG_ROOT / "examples" / "claude-native" / "agents" / f"{LANE_AGENT}.md"
DEFAULT_AGENT_FILE = Path.home() / ".claude" / "agents" / f"{LANE_AGENT}.md"
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


def agent_sha256(agent_file: Path, vendored: Path = VENDORED_AGENT) -> str:
    """The sha256 of the role definition the lane loaded, which must equal the catalog's vendored copy: a stale
    or locally edited same-named role could load incumbent-revealing instructions or broader tools."""
    if not agent_file.is_file():
        raise ProvenanceError(f"role definition {agent_file} not found; install the vendored {LANE_AGENT}.md")
    digest = hashlib.sha256(agent_file.read_bytes()).hexdigest()
    expected = hashlib.sha256(vendored.read_bytes()).hexdigest() if vendored.is_file() else None
    if digest != expected:
        raise ProvenanceError(f"{agent_file} sha256 {digest} is not the vendored {vendored.name} ({expected}); "
                              "install the vendored role before recording")
    return digest


def lane_provenance(agentlab_root: Path, workflow: str, sums: dict, agent_file: Path = DEFAULT_AGENT_FILE) -> dict:
    """{workflow_path, workflow_sha256, agentlab_commit, agent_sha256} for committed, vendored workflow bytes and
    the vendored role definition the lane ran as."""
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
    role_sha256 = agent_sha256(agent_file)  # a missing or unvendored file is a ProvenanceError first
    project_role = agentlab_root / ".claude" / "agents" / f"{LANE_AGENT}.md"
    if project_role.is_file() and project_role.read_bytes() != Path(agent_file).read_bytes():
        # A lane run from the agent-lab checkout loads this copy, not the one named.
        raise ProvenanceError(f"{project_role} differs from {agent_file}; name the definition the lane loaded")
    return {"workflow_path": workflow, "workflow_sha256": digest, "agentlab_commit": head.stdout.strip(),
            "agent_sha256": role_sha256}


def lane_return(layer: dict, provenance: dict, resolved_model=None) -> dict:
    data = dict(layer["final"])
    data["lane"] = "claude"
    model = dict(data.get("model") or {})
    if resolved_model:
        model["name"] = resolved_model
    model["family"] = LANE_FAMILY
    data["model"] = model
    data["provenance"] = dict(provenance)
    if isinstance(layer.get("refutation"), dict):
        data["refutation"] = layer["refutation"]
    return data


FAILURES_NAME = "failures.json"


def failure_reason(layer: dict) -> str:
    """Why a layer produced no final: its refutation status and the deciding votes' reasons."""
    refutation = layer.get("refutation") if isinstance(layer.get("refutation"), dict) else {}
    status = refutation.get("status") or "unknown"
    if not layer.get("proposal") and "proposal" in layer:
        return "no final: the proposal never returned (refutation status unknown)"
    reasons = [f"{vote.get('round')}/{vote.get('lens')}: "
               + ("refuted" if vote.get("refuted") is True else "no vote" if vote.get("refuted") is None else "unrefuted")
               + f" ({vote.get('reason')})"
               for vote in refutation.get("votes") or [] if isinstance(vote, dict) and vote.get("refuted") is not False]
    return f"no final: refutation status {status}" + (f"; {'; '.join(reasons)}" if reasons else "")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--result", type=Path, required=True, help="The workflow's returned JSON object.")
    parser.add_argument("--work-dir", type=Path, required=True, help="The lane_packets.py work dir.")
    parser.add_argument("--agentlab-root", type=Path, required=True, help="The agent-lab checkout the lane ran from.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow path relative to --agentlab-root.")
    parser.add_argument("--agent-file", type=Path, required=True,
                        help=f"The {LANE_AGENT} definition the lane actually loaded: a project-level copy in the "
                             "directory the lane ran from wins over the user-level one, so name the loaded file "
                             "(Codex review of #145).")
    parser.add_argument("--resolved-model", default=None,
                        help="Resolved child model name (e.g. claude-opus-5-5); default keeps the bound alias.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        provenance = lane_provenance(args.agentlab_root.resolve(), args.workflow, vendored_sums(), args.agent_file)
    except ProvenanceError as error:
        print(error, file=sys.stderr)
        return 2
    result = json.loads(args.result.read_text(encoding="utf-8"))
    out_dir = args.work_dir / "claude"
    out_dir.mkdir(parents=True, exist_ok=True)
    written, without_final, failures = [], [], []
    for layer in result.get("layers") or []:
        name = f"{layer['catalog']}__{layer['layer_id']}.json"
        if not isinstance(layer.get("final"), dict):
            # A prior run's return for this layer must not survive this run's
            # failure, or record_verdicts.py would seal the stale return.
            (out_dir / name).unlink(missing_ok=True)
            without_final.append(name)
            failures.append({"catalog": layer["catalog"], "layer_id": layer["layer_id"],
                             "reason": failure_reason(layer)})
            continue
        data = lane_return(layer, provenance, args.resolved_model)
        (out_dir / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        written.append(name)
    for lost in result.get("lost") or []:
        catalog, _, layer_id = str(lost).partition("/")
        if catalog and layer_id:
            (out_dir / f"{catalog}__{layer_id}.json").unlink(missing_ok=True)
            failures.append({"catalog": catalog, "layer_id": layer_id,
                             "reason": "lost: the workflow returned no result for this packet"})
    failures_path = out_dir / FAILURES_NAME
    if failures:
        failures_path.write_text(json.dumps({"lane": "claude", "failures": failures}, indent=1, sort_keys=True)
                                 + "\n", encoding="utf-8")
    else:
        failures_path.unlink(missing_ok=True)
    print(json.dumps({"written": len(written), "without_final": without_final,
                      "lost": list(result.get("lost") or []), "provenance": provenance}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
