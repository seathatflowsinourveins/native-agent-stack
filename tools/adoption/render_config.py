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

Two placeholders are derived when neither the host value file nor ``--set``
supplies them. ``AI_MEMORY_BIN`` is the ai-memory executable that the Claude
hook commands run. It defaults to the selected platform's pinned install,
``${ECO_ROOT}/tools/ai-memory-<version>/ai-memory`` with ``<version>`` read
from ``adoption/pins-<os>-<arch>.json`` (``--platform``, default: this
machine, spelled as ``scripts/adoption_status.py`` does), because upstream's
native hook commands invoke the installed binary directly and the Linux and
macOS pins differ. A host whose running ai-memory lives elsewhere passes its
path with ``--set AI_MEMORY_BIN=...``. ``SOCRATICODE_VERSION`` is derived the
same way: the Codex user template's SocratiCode server runs
``${ECO_ROOT}/tools/socraticode-${SOCRATICODE_VERSION}/``, the prefix
``adoption/bootstrap-<os>.sh`` installs from the selected platform's pin
(1.15.0 on linux-x86_64 and 1.14.0 on macos-arm64 since 2026-09-27); ``--set
SOCRATICODE_VERSION=...`` names another installed version.

One placeholder is an explicit opt-in instead of a host value:
``AI_MEMORY_CAPTURE_ASSISTANT`` renders nothing unless the host value file or
``--set`` sets it to ``true``, which appends ai-memory's ``--capture-assistant``
flag to the Claude ``Stop`` hook only (assistant/Stop capture; the ai-memory
server's own ``capture_assistant`` setting must also be enabled). Absent, empty
or ``false`` keeps automatic assistant capture off; any other value is an error.

This script never edits a live client config. It only reads templates and a
selected host's value file, then writes to an explicitly chosen ``--out``
directory, or compares (``--check``) against explicitly chosen live paths, or
runs read-only ``--verify`` commands.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import platform
import re
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


def default_project_root() -> Path:
    """Resolve the project whose `.codex/config.toml` --check compares against.

    The template's `project.codex.config.toml` targets the project being
    onboarded (e.g. agent-lab), never this catalog checkout, which has no
    `.codex/config.toml` of its own. Callers running --check for a real
    project must pass ``--live-codex-project`` or set
    ``ADOPTION_PROJECT_ROOT``; without either, this falls back to the current
    working directory so the default at least reflects "the project you ran
    this from" rather than silently pointing at the catalog repository.
    """
    env_root = os.environ.get("ADOPTION_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    return Path.cwd()


def default_live_paths() -> dict[str, Path]:
    return {
        "settings.json": Path.home() / ".claude" / "settings.json",
        "codex.config.toml": Path.home() / ".codex" / "config.toml",
        "project.codex.config.toml": default_project_root() / ".codex" / "config.toml",
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


CAPTURE_ASSISTANT = "AI_MEMORY_CAPTURE_ASSISTANT"
AI_MEMORY_BIN = "AI_MEMORY_BIN"
SOCRATICODE_VERSION = "SOCRATICODE_VERSION"
# This catalog's pins-<os>-<arch>.json spelling of platform.system().lower() (as PIN_OS_ALIASES in
# scripts/adoption_status.py).
PIN_OS_ALIASES = {"darwin": "macos"}


def current_platform() -> str:
    osname = platform.system().lower()
    return f"{PIN_OS_ALIASES.get(osname, osname)}-{platform.machine().lower()}"


def pinned_version(tool_id: str, platform_id: str, placeholder: str = AI_MEMORY_BIN) -> str:
    """The version adoption/pins-<platform_id>.json pins for one tool; placeholder names the derived value."""
    if not re.fullmatch(r"[a-z0-9_]+-[a-z0-9_]+", platform_id):
        raise RenderError(f"--platform must look like linux-x86_64 or macos-arm64, got {platform_id!r}")
    path = ROOT / "adoption" / f"pins-{platform_id}.json"
    if not path.is_file():
        raise RenderError(f"no pins file for platform {platform_id!r} ({path}); "
                          f"pass --platform or --set {placeholder}=<value for the {tool_id} install>")
    try:
        tools = json.loads(path.read_text(encoding="utf-8"))["tools"]
        return next(tool["version"] for tool in tools if tool.get("id") == tool_id)
    except (ValueError, KeyError, TypeError, StopIteration):
        raise RenderError(f"{path.name} pins no {tool_id!r} version") from None


def resolve_derived(values: dict[str, str], platform_id: str | None = None) -> dict[str, str]:
    """Supply AI_MEMORY_BIN from the platform pin when the caller did not (see the module docstring)."""
    if values.get(AI_MEMORY_BIN) or "ECO_ROOT" not in values:
        return values  # a missing ECO_ROOT is reported by the substitution itself
    version = pinned_version("ai-memory", platform_id or current_platform())
    return {**values, AI_MEMORY_BIN: f"{values['ECO_ROOT']}/tools/ai-memory-{version}/ai-memory"}


def resolve_socraticode_version(values: dict[str, str], platform_id: str | None = None) -> dict[str, str]:
    """Supply SOCRATICODE_VERSION from the platform pin when the caller did not (see the module docstring)."""
    if values.get(SOCRATICODE_VERSION):
        return values
    version = pinned_version("socraticode", platform_id or current_platform(), SOCRATICODE_VERSION)
    return {**values, SOCRATICODE_VERSION: version}


def resolve_opt_ins(values: dict[str, str]) -> dict[str, str]:
    """Replace the explicit opt-in's setting with the text it renders (see the module docstring)."""
    setting = values.get(CAPTURE_ASSISTANT, "")
    if setting not in ("", "false", "true"):
        raise RenderError(f'{CAPTURE_ASSISTANT} must be "true" or "false", got {setting!r}')
    return {**values, CAPTURE_ASSISTANT: " --capture-assistant" if setting == "true" else ""}


def render_one(template_path: Path, values: dict[str, str], platform_id: str | None = None) -> str:
    text = template_path.read_text(encoding="utf-8")
    if "${" + AI_MEMORY_BIN + "}" in text:
        values = resolve_derived(values, platform_id)
    if "${" + SOCRATICODE_VERSION + "}" in text:
        values = resolve_socraticode_version(values, platform_id)
    resolved = resolve_opt_ins(values)
    try:
        return string.Template(text).substitute(resolved)
    except KeyError as error:
        raise RenderError(f"{template_path.name}: missing template value {error}") from None


def render_all(values: dict[str, str], platform_id: str | None = None) -> dict[str, str]:
    return {name: render_one(path, values, platform_id) for name, path in TEMPLATE_FILES.items()}


def collect_values(args: argparse.Namespace) -> dict[str, str]:
    values: dict[str, str] = {}
    if args.host:
        values.update(load_host_values(args.host))
    values.update(parse_set_values(args.set or []))
    return values


def cmd_out(args: argparse.Namespace) -> int:
    values = collect_values(args)
    try:
        rendered = render_all(values, args.platform)
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
        rendered = render_all(values, args.platform)
    except RenderError as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 1
    live_paths = default_live_paths()
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
        # Compare actual bytes, not text.read_text()'s universal-newline
        # normalisation: Path.read_text() silently translates \r\n and \r to
        # \n, so a live file saved with CRLF line endings could otherwise be
        # reported "byte-identical" to an LF-rendered template even though
        # the on-disk bytes differ. "byte-identical" is only ever printed
        # when the raw bytes actually match.
        live_bytes = live_path.read_bytes()
        rendered_bytes = rendered_text.encode("utf-8")
        if rendered_bytes == live_bytes:
            print(f"{name}: byte-identical to {live_path}")
            continue
        exit_code = 1
        live_text = live_bytes.decode("utf-8", errors="replace")
        # If the only difference is newline convention or JSON formatting,
        # say so explicitly and still report the diff so the record shows
        # the actual bytes differ. Checked in this order because a raw
        # bytes.decode() does NOT do read_text()'s universal-newline
        # translation, so a CRLF live file's decoded text still contains
        # literal "\r\n" and needs its own explicit normalised comparison
        # rather than relying on the JSON-equality check to notice it.
        note = ""
        live_text_lf = live_text.replace("\r\n", "\n").replace("\r", "\n")
        if rendered_text == live_text_lf:
            note = " (content is identical after newline normalisation; on-disk newline bytes differ)"
        elif name.endswith(".json"):
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
            # stdin closed like adoption's version probes: a CLI that falls
            # back to reading stdin gets EOF instead of the caller's terminal.
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False,
                                    stdin=subprocess.DEVNULL)
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
    parser.add_argument("--platform", metavar="OS-ARCH",
                         help="Pins file (adoption/pins-<OS-ARCH>.json) whose ai-memory and socraticode versions "
                              "the default AI_MEMORY_BIN and SOCRATICODE_VERSION name, e.g. linux-x86_64 or "
                              "macos-arm64 (default: this machine)")
    parser.add_argument("--out", metavar="DIR",
                         help="Write settings.json, codex.config.toml, project.codex.config.toml here")
    parser.add_argument("--check", action="store_true",
                         help="Diff rendered configs against live files instead of writing --out")
    parser.add_argument("--live-settings", help="Override the live Claude settings.json path for --check")
    parser.add_argument("--live-codex-user", help="Override the live user-level codex config.toml path for --check")
    parser.add_argument("--live-codex-project",
                         help="Live project-level .codex/config.toml path for --check. "
                              "Defaults to $ADOPTION_PROJECT_ROOT/.codex/config.toml, or the "
                              "current working directory's .codex/config.toml if that is unset -- "
                              "never this catalog checkout. Pass the project being onboarded, e.g. "
                              "/home/<host-user>/code/agent-lab/.codex/config.toml.")
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
