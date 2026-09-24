#!/usr/bin/env python3
"""Print the layer-verdict-lane.js args for a blind Claude lane run.

The Claude lane is a saved agent-lab workflow run from the blind export's root (headless, hooks disabled). Its
args name the export, the lane_packets.py packets with their sha256, this catalog's lane-prompt.md text, and a
``launch`` identity that the workflow echoes back: ``{repo, repo_tree_sha256, agent_sha256}``. claude_lane.py
refuses a result whose launch does not name its ``--repo``, that tree's current digest and the vendored
blind-lane-reviewer role, or whose echoed prompt is not lane-prompt.md (independent review of #145, O1).

Usage:
  python3 tools/sota-convergence/claude_lane_args.py --work-dir W --repo <blind export> \
    --agent-file ~/.claude/agents/blind-lane-reviewer.md --agentlab-root <agent-lab checkout> > claude-args.json

Exit 2 when the export fails the blind root rule, sits inside a git repository, or the role file is not the
vendored one. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claude_lane  # noqa: E402
from codex_lane import tree_sha256  # noqa: E402


def lane_args(work_dir: Path, repo: Path, agent_file: Path, agentlab_root: Path = None) -> dict:
    given = Path(os.path.abspath(repo))
    repo = repo.resolve()
    if not repo.is_dir():
        raise claude_lane.ProvenanceError(f"--repo {repo} is not an existing directory")
    # The path as given and its resolved form both pass the blind root rule: on macOS /home is a symlink whose
    # target is deep enough to pass (Codex review of #145), as the other blind entry points check.
    for candidate in (given, repo):
        issue = claude_lane.repo_issue(candidate)
        if issue:
            raise claude_lane.ProvenanceError(issue)
    role = claude_lane.agent_sha256(agent_file)
    if agentlab_root is not None:
        # The collector's checks, before the costly run (re-review N1): the agent-lab workflow is committed and
        # vendored, and its project-level role, if any, is the vendored one.
        claude_lane.lane_provenance(Path(agentlab_root).resolve(), claude_lane.DEFAULT_WORKFLOW,
                                    claude_lane.vendored_sums(), agent_file)
    packets = []
    for path in sorted((Path(work_dir).resolve() / "packets").glob("*__*.json")):
        catalog, layer_id = path.stem.split("__", 1)
        packets.append({"catalog": catalog, "layer_id": layer_id, "path": str(path),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if not packets:
        raise claude_lane.ProvenanceError(f"{work_dir}/packets has no packets; run lane_packets.py first")
    return {"repo": str(repo), "packets": packets, "prompt": claude_lane.LANE_PROMPT.read_text(encoding="utf-8"),
            "launch": {"repo": str(repo), "repo_tree_sha256": tree_digest(repo), "agent_sha256": role}}


def tree_digest(repo: Path) -> str:
    try:
        return tree_sha256(repo)
    except ValueError as error:  # an escaping symlink: not a blind export
        raise claude_lane.ProvenanceError(str(error)) from error


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", type=Path, required=True, help="The lane_packets.py work dir.")
    parser.add_argument("--repo", type=Path, required=True, help="The blind export the lane reads.")
    parser.add_argument("--agent-file", type=Path, required=True,
                        help="The blind-lane-reviewer definition the headless session will load.")
    parser.add_argument("--agentlab-root", type=Path, required=True,
                        help="The clean agent-lab checkout whose .claude/workflows/layer-verdict-lane.js the lane runs; "
                             "checked as claude_lane.py will check it, before launch.")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(lane_args(args.work_dir, args.repo, args.agent_file, args.agentlab_root), indent=1))
    except claude_lane.ProvenanceError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
