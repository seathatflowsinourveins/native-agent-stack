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
- ``provenance`` is ``{workflow_path, workflow_sha256, agentlab_commit, agent_sha256, prompt_sha256,
  repo_tree_sha256}`` (``prompt_sha256``: the echoed prompt, which must be this catalog's lane-prompt.md):
  the workflow path relative to the agent-lab checkout, the sha256 of those
  bytes, that checkout's ``HEAD``, the lane role's sha256, and the digest of the
  evidence tree (``--repo``) the lane read. The workflow echoes the caller's
  ``args.launch`` as ``launch``; the script refuses (exit 2) unless it is
  ``{repo, repo_tree_sha256, agent_sha256}`` naming ``--repo``, that tree's current
  digest and the vendored role digest the launcher checked before launching,
  so a result from another launch, or over a tree changed since launch, is never
  recorded. The script refuses (exit 2) when the
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
sys.path.insert(0, str(HERE))
from codex_lane import root_issue, tree_sha256  # noqa: E402  (one root rule and tree digest for both lanes)
import transcript_audit  # noqa: E402
VENDORED_SUMS = CATALOG_ROOT / "examples" / "claude-native" / "workflows" / "SHA256SUMS"
VENDORED_LANES = CATALOG_ROOT / "examples" / "claude-native" / "workflows" / "vendored-lanes.json"
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


def vendored_agentlab_commit(workflow: str):
    """The agent-lab commit vendored-lanes.json verified ``workflow`` identical at, or None."""
    try:
        files = json.loads(VENDORED_LANES.read_text(encoding="utf-8")).get("files") or []
    except (OSError, ValueError):
        return None
    for entry in files:
        if isinstance(entry, dict) and entry.get("source_path") == workflow:
            return entry.get("verified_identical_at_agentlab_commit") or entry.get("agentlab_commit")
    return None


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
    if git(agentlab_root, "ls-files", "--error-unmatch", "--", workflow).returncode != 0:
        # Untracked bytes are not committed ones, whatever `git diff` says (independent review of #145, BIND-R4-8).
        raise ProvenanceError(f"{workflow} is not tracked in {agentlab_root}; commit it before recording")
    if git(agentlab_root, "diff", "--quiet", "HEAD", "--", workflow).returncode != 0:
        raise ProvenanceError(f"{workflow} differs from HEAD in {agentlab_root}; commit it before recording")
    dirty = git(agentlab_root, "status", "--porcelain", "--", ".claude", "CLAUDE.md", "AGENTS.md")
    if dirty.returncode != 0 or dirty.stdout.strip():
        # An edited role, instruction file or local settings would shape the lane without a trace (BIND-R4-8).
        raise ProvenanceError(f"{agentlab_root} has uncommitted .claude/, CLAUDE.md or AGENTS.md changes; commit or "
                              "remove them before running the lane")
    vendored = vendored_agentlab_commit(workflow)
    if vendored is None or git(agentlab_root, "merge-base", "--is-ancestor", vendored, "HEAD").returncode != 0:
        # The checkout must hold the agent-lab commit the workflow was vendored from, or a descendant (BIND-R4-8).
        raise ProvenanceError(f"{agentlab_root} HEAD does not descend from the vendored agent-lab commit {vendored} "
                              "(examples/claude-native/workflows/vendored-lanes.json); check that commit out")
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
TRANSCRIPT_AUDIT_NAME = "transcript-audit.json"


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


LANE_PROMPT = HERE / "lane-prompt.md"


def consumed_packets_issue(result: dict, work_dir: Path) -> None:
    """Every layer must echo the packet its agents read (Codex review of #145, agent-lab #47): the work dir's
    ``packets/<catalog>__<layer_id>.json``, whose current bytes hash to the layer's packet_sha256."""
    for layer in result.get("layers") or [] if isinstance(result, dict) else []:
        name = f"{layer.get('catalog')}__{layer.get('layer_id')}.json"
        expected = (Path(work_dir).resolve() / "packets" / name)
        if layer.get("packet_path") != str(expected):
            raise ProvenanceError(f"layer {name} was run on packet {layer.get('packet_path')!r}, not {expected}")
        if not expected.is_file() or hashlib.sha256(expected.read_bytes()).hexdigest() != layer.get("packet_sha256"):
            raise ProvenanceError(f"layer {name}: {expected} does not hash to the packet_sha256 the lane ran with")


def consumed_prompt_sha256(result: dict) -> str:
    """sha256 of the prompt the workflow echoes (independent review of #145, M1); it must be this catalog's
    lane-prompt.md, as the Codex lane's prompt_sha256 is, so a run on an edited or built-in prompt is refused."""
    prompt = result.get("prompt") if isinstance(result, dict) else None
    if not isinstance(prompt, str):
        raise ProvenanceError("the workflow result carries no prompt; run a layer-verdict-lane.js that echoes it, "
                              "with args.prompt set to tools/sota-convergence/lane-prompt.md")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    expected = hashlib.sha256(LANE_PROMPT.read_bytes()).hexdigest()
    if digest != expected:
        raise ProvenanceError(f"the workflow ran prompt {digest}, not this catalog's lane-prompt.md {expected}")
    return digest


def repo_issue(repo: Path):
    """Why ``repo`` cannot be a blind export, or None (independent review of #145, O3/O4): it must pass the
    adjudicator's root rule and sit outside every git repository, whose history recovers every stripped label."""
    issue = root_issue(repo)
    if issue:
        # The rule as codex_lane.root_issue applies it (independent review of #145, round 4, OPS-6).
        return (f"--repo {issue}; place the blind export at least four directories deep (not /, /home, /tmp or a home "
                "directory itself) and outside every repository")
    for path in (repo, *repo.parents):
        if (path / ".git").exists():
            return f"--repo {repo} is inside the git repository {path}; the Claude lane must read a blind export"
    return None


def launch_tree(result: dict, repo: Path, role_sha256: str = None) -> str:
    """The evidence-tree digest the result was launched on (Codex review of #145): the workflow echoes the
    caller's args.launch, which prepare wrote as {repo, repo_tree_sha256, agent_sha256}; it must name ``repo``,
    that tree's current digest and ``role_sha256``, the vendored role digest this collector verified (the
    launcher checks the loaded role against the same digest before and after the run)."""
    launch = result.get("launch") if isinstance(result, dict) else None
    if not (isinstance(launch, dict) and isinstance(launch.get("repo"), str)
            and isinstance(launch.get("repo_tree_sha256"), str) and isinstance(launch.get("agent_sha256"), str)):
        raise ProvenanceError("the workflow result carries no launch {repo, repo_tree_sha256, agent_sha256}; launch "
                              "the lane with args.launch so its result names the export and role it ran with")
    if launch["repo"] != str(repo):
        raise ProvenanceError(f"the result was launched on {launch['repo']!r}, not --repo {str(repo)!r}")
    if role_sha256 is not None and launch["agent_sha256"] != role_sha256:
        raise ProvenanceError(f"the result was launched with role {launch['agent_sha256']}, not the vendored "
                              f"{role_sha256}")
    if not repo.is_dir():
        raise ProvenanceError(f"--repo {repo} is not an existing directory")
    export_issue = repo_issue(repo)
    if export_issue:
        raise ProvenanceError(export_issue)
    try:
        current = tree_sha256(repo)
    except ValueError as error:
        raise ProvenanceError(str(error)) from error
    if current != launch["repo_tree_sha256"]:
        raise ProvenanceError(f"the evidence tree under --repo is {current}, not the launch digest "
                              f"{launch['repo_tree_sha256']}; it changed after launch, so rerun on a fixed export")
    return current


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
    parser.add_argument("--repo", type=Path, required=True,
                        help="The blind export the lane read (the workflow args' repo).")
    parser.add_argument("--transcripts", type=Path, required=True,
                        help="The workflow run's agent transcript directory (~/.claude/projects/<export slug>/<session>/"
                             "subagents/workflows/<run id>): each layer's return is audited on what its agents read.")
    parser.add_argument("--resolved-model", default=None,
                        help="Resolved child model name (e.g. claude-opus-5-5); default keeps the bound alias.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        provenance = lane_provenance(args.agentlab_root.resolve(), args.workflow, vendored_sums(), args.agent_file)
        result = json.loads(args.result.read_text(encoding="utf-8"))
        consumed_packets_issue(result, args.work_dir)
        provenance["prompt_sha256"] = consumed_prompt_sha256(result)
        provenance["repo_tree_sha256"] = launch_tree(result, args.repo.resolve(), provenance["agent_sha256"])
    except ProvenanceError as error:
        print(error, file=sys.stderr)
        return 2
    if not transcript_audit.transcript_files(args.transcripts):
        print(f"claude_lane: --transcripts {args.transcripts} holds no agent transcripts; name the workflow run's "
              "subagents/workflows/<run id> directory", file=sys.stderr)
        return 2
    out_dir = args.work_dir / "claude"
    out_dir.mkdir(parents=True, exist_ok=True)
    # The blind rule, checked in what the agents opened (Codex review of #145 at 68e74f2c): Read, Glob and Grep have
    # no path limit, so each layer's agents may read only its packet and the export.
    packets_dir = str((args.work_dir / "packets").resolve())
    export = str(args.repo.resolve())
    audit_items = {f"{layer['catalog']}__{layer['layer_id']}": {
        "marker": str(layer.get("packet_path") or ""), "roots": [export, str(layer.get("packet_path") or "")]}
        for layer in result.get("layers") or [] if isinstance(layer.get("final"), dict)}
    report = transcript_audit.audit(args.transcripts, audit_items, marker_prefix=packets_dir + "/")
    (out_dir / TRANSCRIPT_AUDIT_NAME).write_text(json.dumps({"dir": str(args.transcripts.resolve()), **report},
                                                            indent=1, sort_keys=True) + "\n", encoding="utf-8")
    written, without_final, failures = [], [], []
    for layer in result.get("layers") or []:
        name = f"{layer['catalog']}__{layer['layer_id']}.json"
        if isinstance(layer.get("final"), dict) and name[:-len(".json")] in report["flagged_items"]:
            # Void: a return whose agents read outside the export and its packet is kept only for inspection.
            (out_dir / name).unlink(missing_ok=True)
            (out_dir / f"{name}.audit-flagged").write_text(json.dumps(layer, indent=1, sort_keys=True) + "\n",
                                                           encoding="utf-8")
            failures.append({"catalog": layer["catalog"], "layer_id": layer["layer_id"],
                             "reason": "the transcript audit flagged this layer's agents (a read outside the export "
                                       "and its packet, or a tool other than Read, Glob and Grep)"})
            continue
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
    # Every packet of the work dir must be in layers or lost (Codex review of #145): one dropped from the args before
    # launch is in neither, and its earlier return must not survive to be sealed with this wave.
    accounted = {f"{layer['catalog']}__{layer['layer_id']}" for layer in result.get("layers") or []}
    accounted |= {str(lost).replace("/", "__", 1) for lost in result.get("lost") or []}
    for packet in sorted((args.work_dir / "packets").glob("*__*.json")):
        if packet.stem not in accounted:
            (out_dir / f"{packet.stem}.json").unlink(missing_ok=True)
            catalog, _, layer_id = packet.stem.partition("__")
            failures.append({"catalog": catalog, "layer_id": layer_id,
                             "reason": "missing: the workflow result names this packet in neither layers nor lost"})
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
