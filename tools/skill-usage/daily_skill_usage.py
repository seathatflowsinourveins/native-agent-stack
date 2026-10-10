#!/usr/bin/env python3
"""Run the existing native reports and publish only skill names and counts.

The CC installs the rendered user timer after landing. Tests pass a stub runner;
lanes never invoke the real Claude client through this script.
"""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import skill_usage

ROOT = Path(__file__).resolve().parents[2]
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}\Z")
KINDS = ("skill_invoke_rate_report", "codex_lane_usage_report", "claude_child_lane_usage")


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def counts(value):
    if not isinstance(value, dict):
        return []
    return [{"name": name, "count": count(number)} for name, number in sorted(value.items())
            if isinstance(name, str) and NAME.fullmatch(name) and count(number) is not None]


def project_reports(host, codex, claude, *, now, window):
    """Project native aggregates, preserving client/group and measurement meaning."""
    host_rows = None
    baseline = json.loads((ROOT / "adoption/skills/claude-routing/trigger-baseline.json").read_text())
    wiring = {row["name"]: row for row in baseline.get("skills", [])}
    if isinstance(host, dict) and host.get("kind") == KINDS[0] and isinstance(host.get("skills"), list):
        host_rows = []
        for row in host["skills"]:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not NAME.fullmatch(row["name"]):
                continue
            c = row.get("claude") if isinstance(row.get("claude"), dict) else {}
            x = row.get("codex") if isinstance(row.get("codex"), dict) else {}
            days = x.get("counts", {}).get(str(window), {})
            host_rows.append({"name": row["name"], "claude_uses_lifetime": count(c.get("uses")),
                              "wiring": wiring.get(row["name"], {}).get("status"),
                              "codex_use": count(x.get("use_counts", {}).get(str(window))),
                              "codex_skill_md_reads": count(days.get("skill_md_reads")),
                              "codex_name_mentions": count(days.get("name_mentions"))})
    lanes = []
    use_groups = host.get("codex_use_groups", {}).get(str(window), {}) if isinstance(host, dict) and isinstance(host.get("codex_use_groups"), dict) else {}
    def lane(client, name, aggregate, field, use=None):
        if NAME.fullmatch(name) and isinstance(aggregate, dict):
            rows = counts(aggregate.get(field))
            if client == "codex":
                raw = {row["name"]: row["count"] for row in rows}
                rows = [{"name": skill, "count": count(use.get(skill, 0)) if isinstance(use, dict) else None,
                         "raw_reads": raw.get(skill, 0)} for skill in sorted(set(raw) | set(use or {}))
                        if isinstance(skill, str) and NAME.fullmatch(skill)]
            lanes.append({"client": client, "lane": name, "skills": rows,
                          "metric": "use" if client == "codex" else "skill_calls"})
    if isinstance(codex, dict) and codex.get("kind") == KINDS[1]:
        groups = codex.get("groups", {})
        for name in ("workers", "negative_controls", "unclassified"):
            if name in groups:
                lane("codex", name, groups[name], "skill_md_reads", use_groups.get(name))
        for name, group in groups.get("workers_by_role", {}).items():
            lane("codex", "role:" + name, group, "skill_md_reads", use_groups.get("workers_by_role", {}).get(name))
        for name, group in groups.get("workers_by_kind", {}).items():
            lane("codex", "kind:" + name, group, "skill_md_reads", use_groups.get("workers_by_kind", {}).get(name))
    if isinstance(claude, dict) and claude.get("kind") == KINDS[2]:
        for spawn, agents in claude.get("groups", {}).get("by_spawn_and_agent_type", {}).items():
            for name, group in agents.items():
                lane("claude", spawn + ":" + name, group, "skill_calls")
        if isinstance(claude.get("main"), dict):
            lane("claude", "main", claude["main"], "skill_calls")
    return {"schema": "skill-invoke-rate-daily/1", "generated_at": now, "window_days": window,
            "host": host_rows, "lanes": lanes if codex is not None or claude is not None else None,
            "zero_use": {"codex": [row["name"] for row in host_rows or [] if row["codex_use"] == 0],
                         "claude_host_lifetime": [row["name"] for row in host_rows or [] if row["claude_uses_lifetime"] == 0]},
            "codex_bulk_scan_limit": host.get("codex_use_policy", {}).get("max_distinct_skill_reads") if isinstance(host, dict) and isinstance(host.get("codex_use_policy"), dict) else None,
            "measured": {"host": host_rows is not None and host.get("claude", {}).get("measured") is True,
                         "codex": isinstance(codex, dict) and codex.get("kind") == KINDS[1] and bool(use_groups),
                         "claude": isinstance(claude, dict) and claude.get("kind") == KINDS[2]}}


def collect_reports(codex_roots, claude_roots, *, window, now, node="node", runner=subprocess.run):
    since, until = (now - timedelta(days=window)).isoformat(), now.isoformat()
    codex_args = [arg for root in codex_roots for arg in ("--codex-root", str(root))]
    claude_args = [arg for root in claude_roots for arg in ("--root", str(root))]
    commands = [
        [sys.executable, str(ROOT / "tools/skill-usage/skill_usage.py"), "--run-skill-doctor",
         *codex_args, "--window", str(window), "--now", until, "--json"],
        [sys.executable, str(ROOT / "tools/skill-usage/skill_usage.py"), "--lanes", *codex_args,
         "--since", since, "--until", until, "--now", until, "--json"],
        [node, str(ROOT / "examples/claude-native/workflows/child-usage.mjs"), "--lanes-sweep",
         *claude_args, "--since", since, "--until", until],
    ]
    reports = []
    for command, kind in zip(commands, KINDS):
        try:
            result = runner(command, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=1200)
            report = json.loads(result.stdout) if result.returncode == 0 else None
            reports.append(report if isinstance(report, dict) and report.get("kind") == kind else None)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            reports.append(None)  # Native errors and transcript text never become page content.
    return tuple(reports)


def publish(path, report):
    if skill_usage.inside_git_work_tree(path.parent) or path.is_relative_to(ROOT):
        raise ValueError("report destination must be outside git worktrees")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp = tempfile.mkstemp(prefix=".skill-usage-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def render_units(destination, repository, python, node):
    destination.mkdir(parents=True, exist_ok=True)
    values = {"@REPOSITORY@": str(repository), "@PYTHON@": str(python), "@NODE@": str(node)}
    for value in values.values():
        if not Path(value).is_absolute() or any(char in value for char in ('\n', '\r', '"', '\\')):
            raise ValueError("unit values must be absolute paths without unit quoting characters")
    for name in ("skill-invoke-rate.service", "skill-invoke-rate.timer"):
        text = (ROOT / "adoption/templates/systemd" / name).read_text()
        for key, value in values.items():
            text = text.replace(key, value.replace("%", "%%").replace("$", "$$"))
        (destination / name).write_text(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-root", action="append", type=Path, default=[])
    parser.add_argument("--claude-root", action="append", type=Path, default=[])
    parser.add_argument("--window", type=int, default=7)
    parser.add_argument("--now")
    parser.add_argument("--node", default="node")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--host-report", type=Path)
    parser.add_argument("--codex-lanes-report", type=Path)
    parser.add_argument("--claude-lanes-report", type=Path)
    parser.add_argument("--render-units", type=Path)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    try:
        if args.render_units:
            node = shutil.which(args.node)
            if not node:
                raise ValueError("node executable is unavailable")
            render_units(args.render_units, args.repository, args.python, Path(node))
            return 0
        if not 1 <= args.window <= 366:
            raise ValueError("invalid window")
        now = skill_usage.parse_iso(args.now) if args.now else skill_usage.now_utc()
        sources = (args.host_report, args.codex_lanes_report, args.claude_lanes_report)
        if any(sources):
            reports = tuple(json.loads(path.read_text()) if path else None for path in sources)
        else:
            if not args.codex_root or not args.claude_root:
                raise ValueError("both client roots must be explicit")
            branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout.strip()
            if branch != "main":
                raise ValueError("scheduled live collection requires the main clone")
            reports = collect_reports(args.codex_root, args.claude_root, window=args.window, now=now, node=args.node)
        report = project_reports(*reports, now=now.isoformat(), window=args.window)
        if args.out:
            publish(args.out.absolute(), report)
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if all(report["measured"].values()) else 1
    except (OSError, ValueError, subprocess.SubprocessError):
        print("daily skill usage unavailable; inspect the native collector separately", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
