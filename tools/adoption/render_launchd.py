#!/usr/bin/env python3
"""Render adoption/launchd/*.plist.template for a selected host, stdlib only.

Drafted, not run: rendering a plist here is not launchd acceptance. See
adoption/platforms/macos-arm64.md's "What a hosted run proves" for the exact
limits of what has actually executed on a Mac.

Reuses tools/adoption/render_config.py's ``adoption/hosts/<host>.json``
value-file convention (``load_host_values``, ``parse_set_values``,
``RenderError``) so the same host files that render the Claude/Codex client
configs also render these launchd plists, but NOT its ``render_one``: that
function does a raw ``string.Template`` substitution on template TEXT, which
is correct for the JSON/TOML client configs it renders but not here. A plist
is XML, and a substituted value containing an XML metacharacter -- an ``&``
in a real path such as ``/Volumes/R&D/eco`` is the realistic case -- would
corrupt the document if substituted into raw text (`&D/eco` is not a valid
XML entity). Rendering here instead parses the template as a plist first
(plistlib tolerates the still-literal ``${NAME}`` placeholders as ordinary
string content), substitutes inside every string leaf of the resulting
Python structure, and re-serializes with ``plistlib.dumps``, so plistlib's
own XML escaping covers every substituted value. This script never installs,
bootstraps, or edits a live LaunchAgents plist; it only renders template text
to an explicitly chosen ``--out`` directory. Use
adoption/launchd/launchd-agents.sh for lint/install/status/remove.
"""

from __future__ import annotations

import argparse
import plistlib
import string
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_config import RenderError, load_host_values, parse_set_values  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LAUNCHD_DIR = ROOT / "adoption" / "launchd"
TEMPLATE_SUFFIX = ".plist.template"


def discover_templates() -> dict[str, Path]:
    """Map each rendered plist's filename to its source template path."""
    return {
        path.name[: -len(TEMPLATE_SUFFIX)] + ".plist": path
        for path in sorted(LAUNCHD_DIR.glob(f"*{TEMPLATE_SUFFIX}"))
    }


def _substitute(node: Any, values: dict[str, str]) -> Any:
    """Walk a parsed plist structure, substituting ${NAME} in every string leaf."""
    if isinstance(node, str):
        return string.Template(node).substitute(values)
    if isinstance(node, list):
        return [_substitute(item, values) for item in node]
    if isinstance(node, dict):
        return {key: _substitute(item, values) for key, item in node.items()}
    return node


def render_plist(template_path: Path, values: dict[str, str]) -> bytes:
    raw = template_path.read_bytes()
    try:
        data = plistlib.loads(raw)
    except Exception as error:  # plistlib raises several distinct types
        raise RenderError(f"{template_path.name}: not a well-formed plist template ({error})") from None
    try:
        substituted = _substitute(data, values)
    except KeyError as error:
        raise RenderError(f"{template_path.name}: missing template value {error}") from None
    except ValueError as error:
        # string.Template.substitute raises ValueError (not KeyError) for a
        # malformed placeholder, e.g. a bare trailing "$" or "$" followed by
        # a character that cannot start an identifier.
        raise RenderError(f"{template_path.name}: invalid placeholder ({error})") from None
    return plistlib.dumps(substituted, fmt=plistlib.FMT_XML)


def collect_values(args: argparse.Namespace) -> dict[str, str]:
    values: dict[str, str] = {}
    if args.host:
        values.update(load_host_values(args.host))
    values.update(parse_set_values(args.set or []))
    return values


def render_all(values: dict[str, str]) -> dict[str, bytes]:
    return {name: render_plist(path, values) for name, path in discover_templates().items()}


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
    for name, content in rendered.items():
        (out_dir / name).write_bytes(content)
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
