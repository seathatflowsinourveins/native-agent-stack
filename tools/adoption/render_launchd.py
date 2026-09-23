#!/usr/bin/env python3
"""Render adoption/launchd/*.plist.template for a selected host, stdlib only.

Drafted, not run: rendering a plist here is not launchd acceptance. See
adoption/platforms/macos-arm64.md's "What a hosted run proves" for the exact
limits of what has actually executed on a Mac.

Reuses tools/adoption/render_config.py's ``string.Template`` substitution
(``render_one``, ``RenderError``) and its ``adoption/hosts/<host>.json``
value-file convention (``load_host_values``, ``parse_set_values``), so the
same host files and ``${NAME}`` placeholders that render the Claude/Codex
client configs also render these launchd plists. This script never installs,
bootstraps, or edits a live LaunchAgents plist; it only renders template text
to an explicitly chosen ``--out`` directory. Use
adoption/launchd/launchd-agents.sh for lint/install/status/remove.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_config import RenderError, load_host_values, parse_set_values, render_one  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LAUNCHD_DIR = ROOT / "adoption" / "launchd"
TEMPLATE_SUFFIX = ".plist.template"


def discover_templates() -> dict[str, Path]:
    """Map each rendered plist's filename to its source template path."""
    return {
        path.name[: -len(TEMPLATE_SUFFIX)] + ".plist": path
        for path in sorted(LAUNCHD_DIR.glob(f"*{TEMPLATE_SUFFIX}"))
    }


def collect_values(args: argparse.Namespace) -> dict[str, str]:
    values: dict[str, str] = {}
    if args.host:
        values.update(load_host_values(args.host))
    values.update(parse_set_values(args.set or []))
    return values


def render_all(values: dict[str, str]) -> dict[str, str]:
    return {name: render_one(path, values) for name, path in discover_templates().items()}


def cmd_out(args: argparse.Namespace) -> int:
    values = collect_values(args)
    try:
        rendered = render_all(values)
    except RenderError as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 1
    if not rendered:
        print(f"no {TEMPLATE_SUFFIX} files found under {LAUNCHD_DIR}", file=sys.stderr)
        return 1
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in rendered.items():
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"wrote {out_dir / name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Read adoption/hosts/<host>.json for template values")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE",
                         help="Override or supply a template value; repeatable")
    parser.add_argument("--out", metavar="DIR", required=True,
                         help="Write each rendered <label>.plist here")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return cmd_out(args)


if __name__ == "__main__":
    raise SystemExit(main())
