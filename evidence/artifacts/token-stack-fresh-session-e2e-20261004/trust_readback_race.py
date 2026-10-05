#!/usr/bin/env python3
"""Reproduce, on the real codex app-server, a hook whose definition changes right after the trust write, and print what
tools/adoption/codex_hook_trust.py reports (one JSON object).

    python3 trust_readback_race.py [TOOL_FILE]   # default: tools/adoption/codex_hook_trust.py of this checkout

expectedVersion guards config.toml, not the file a hook is defined in, so the hooks file can change between the listing and
the write. Here the tool runs against the installed codex app-server in a scratch Codex home with one hook (`echo named-hook`),
and the hooks file is rewritten to `echo different-hook` as soon as config/batchWrite has returned. A correct read-back reports
the hook as changed (Codex lists it `modified`: trusted_hash was written for the old definition) and exits 3; a read-back that
searches for the command again finds nothing to complain about and reports success. Pass the file of an earlier revision
(`git show c8613fe16:tools/adoption/codex_hook_trust.py`) to see the second. Nothing outside the scratch home is written, and the
live ~/.codex is not read.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import apply_codex_lane as lane  # noqa: E402


def main() -> int:
    tool_file = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "tools" / "adoption" / "codex_hook_trust.py"
    codex = shutil.which("codex")
    if not codex:
        print("needs codex on PATH", file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("trust_under_test", tool_file)
    trust = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trust)
    with tempfile.TemporaryDirectory(prefix="trust-race-") as scratch:
        base = Path(scratch)
        home, project = base / "codex-home", base / "project"
        home.mkdir()
        project.mkdir()
        (home / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
        hooks_file = home / "hooks.json"

        def write_hooks(command: str) -> None:
            hooks_file.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": command}]}]}}), encoding="utf-8")

        write_hooks("echo named-hook")

        class Racing(lane.AppServer):
            """The real app-server, with the hooks file changed as soon as config/batchWrite has returned."""

            def request(self, method, params):
                result = super().request(method, params)
                if method == "config/batchWrite":
                    write_hooks("echo different-hook")
                return result

        out, err = io.StringIO(), io.StringIO()
        original, lane.AppServer = lane.AppServer, Racing
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = trust.main(["--codex", codex, "--codex-home", str(home), "--cwd", str(project), "--command", "echo named-hook",
                                   "--apply", "--codex-process-name", "no-such-process-name"])
        finally:
            lane.AppServer = original
        version = subprocess.run([codex, "--version"], capture_output=True, text=True, timeout=60, check=False).stdout.strip()

    def clean(text: str) -> str:
        text = text.replace(scratch, "<scratch>")
        return re.sub(r"\.bak\.\d{8}T\d{6}Z(\.\d+)?", ".bak.<stamp>", text).strip()

    print(json.dumps({"tool": tool_file.name, "codex": version, "exit": code, "stdout": clean(out.getvalue()),
                      "stderr": clean(err.getvalue())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
