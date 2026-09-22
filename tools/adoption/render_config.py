#!/usr/bin/env python3
"""Render adoption/templates/*.template.{json,toml} for a selected host, stdlib only.

Templates use ``string.Template`` placeholders (``${NAME}``). Every literal
personal home path, ``/mnt/c/...`` PATH segment and ``127.0.0.1:<port>`` in the
live configs this project actually uses was replaced with one of nine
placeholders: ``HOME``, ``ECO_ROOT``, ``PROJECT_ROOT``, ``HOST_PATH``,
``CODE_INDEX_PATH``, ``OTEL_ENDPOINT``, ``AI_MEMORY_URL``, ``QDRANT_URL``,
``EMBED_URL``. Everything else, including per-host accumulated Codex project
trust entries and hook trusted-hash state, is preserved byte-for-byte inside
the template text (escaped as ``$$`` where the source already used a literal
``$`` for shell syntax such as ``$HOME`` inside a status-line script).

This script never edits a live client config. It only reads templates and a
selected host's value file, then writes to an explicitly chosen ``--out``
directory, or compares (``--check``) against explicitly chosen live paths, or
runs read-only ``--verify`` commands.
"""

from __future__ import annotations

import argparse
import difflib
import json
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "adoption" / "templates"
HOSTS = ROOT / "adoption" / "hosts"

TEMPLATE_FILES = {
    "settings.json": TEMPLATES / "claude.settings.template.json",
    "codex.config.toml": TEMPLATES / "codex.config.template.toml",
    "project.codex.config.toml": TEMPLATES / "project.codex.config.template.toml",
}

DEFAULT_LIVE_PATHS = {
    "settings.json": Path.home() / ".claude" / "settings.json",
    "codex.config.toml": Path.home() / ".codex" / "config.toml",
    "project.codex.config.toml": ROOT / ".codex" / "config.toml",
}

REQUIRED_KEYS = (
    "HOME", "ECO_ROOT", "PROJECT_ROOT", "HOST_PATH", "CODE_INDEX_PATH",
    "OTEL_ENDPOINT", "AI_MEMORY_URL", "QDRANT_URL", "EMBED_URL",
)


class RenderError(ValueError):
    """A template could not be rendered from the given values."""


def load_host_values(host: str) -> dict[str, str]:
    path = HOSTS / f"{host}.json"
    if not path.is_file():
        raise RenderError(f"no host value file at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise RenderError(f"{path} must be a flat JSON object of string values")
    return data


def parse_set_values(pairs: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise RenderError(f"--set expects KEY=VALUE, got {pair!r}")
        key, _, value = pair.partition("=")
        if not key:
            raise RenderError(f"--set expects a nonempty KEY in {pair!r}")
        values[key] = value
    return values


def render_one(template_path: Path, values: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    try:
        return string.Template(text).substitute(values)
    except KeyError as error:
        raise RenderError(f"{template_path.name}: missing template value {error}") from None


def render_all(values: dict[str, str]) -> dict[str, str]:
    return {name: render_one(path, values) for name, path in TEMPLATE_FILES.items()}


def collect_values(args: argparse.Namespace) -> dict[str, str]:
    values: dict[str, str] = {}
    if args.host:
        values.update(load_host_values(args.host))
    values.update(parse_set_values(args.set or []))
    return values


def cmd_out(args: argparse.Namespace) -> int:
    values = collect_values(args)
    try:
        rendered = render_all(values)
    except RenderError as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 1
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in rendered.items():
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"wrote {out_dir / name}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    values = collect_values(args)
    try:
        rendered = render_all(values)
    except RenderError as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 1
    live_paths = dict(DEFAULT_LIVE_PATHS)
    if args.live_settings:
        live_paths["settings.json"] = Path(args.live_settings)
    if args.live_codex_user:
        live_paths["codex.config.toml"] = Path(args.live_codex_user)
    if args.live_codex_project:
        live_paths["project.codex.config.toml"] = Path(args.live_codex_project)

    exit_code = 0
    for name, rendered_text in rendered.items():
        live_path = live_paths[name]
        if not live_path.is_file():
            print(f"{name}: live file not found at {live_path}", file=sys.stderr)
            exit_code = 1
            continue
        live_text = live_path.read_text(encoding="utf-8")
        if rendered_text == live_text:
            print(f"{name}: byte-identical to {live_path}")
            continue
        exit_code = 1
        # If the only difference is JSON formatting, say so explicitly and
        # still report the diff so the record shows the actual bytes differ.
        note = ""
        if name.endswith(".json"):
            try:
                if json.loads(rendered_text) == json.loads(live_text):
                    note = " (json.tool-normalised content is identical; only formatting differs)"
            except json.JSONDecodeError:
                pass
        print(f"{name}: differs from {live_path}{note}")
        diff = difflib.unified_diff(
            live_text.splitlines(keepends=True),
            rendered_text.splitlines(keepends=True),
            fromfile=f"live/{name}", tofile=f"rendered/{name}",
        )
        sys.stdout.writelines(diff)
    return exit_code


def cmd_verify(_args: argparse.Namespace) -> int:
    commands = [
        ["codex", "--version"],
        ["claude", "--version"],
        ["codex", "mcp", "list"],
    ]
    overall = 0
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            code = result.returncode
            output = (result.stdout or result.stderr or "").strip().splitlines()
            first_line = output[0] if output else ""
        except (OSError, subprocess.TimeoutExpired) as error:
            code = 127
            first_line = str(error)
        overall = overall or (code if code != 0 else 0)
        print(f"{' '.join(command)}: exit {code}{f' -- {first_line}' if first_line else ''}")
    return 0 if overall == 0 else overall


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Read adoption/hosts/<host>.json for template values")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE",
                         help="Override or supply a template value; repeatable")
    parser.add_argument("--out", metavar="DIR",
                         help="Write settings.json, codex.config.toml, project.codex.config.toml here")
    parser.add_argument("--check", action="store_true",
                         help="Diff rendered configs against live files instead of writing --out")
    parser.add_argument("--live-settings", help="Override the live Claude settings.json path for --check")
    parser.add_argument("--live-codex-user", help="Override the live user-level codex config.toml path for --check")
    parser.add_argument("--live-codex-project", help="Override the live project codex config.toml path for --check")
    parser.add_argument("--verify", action="store_true",
                         help="Run codex --version, claude --version, codex mcp list and report exit codes")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verify:
        return cmd_verify(args)
    if args.check:
        return cmd_check(args)
    if args.out:
        return cmd_out(args)
    parser.error("one of --out, --check, or --verify is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
