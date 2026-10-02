#!/usr/bin/env python3
"""Re-create sanitized auxiliary copies; usage: rebuild_20261002.py STATE [FIRST_ARTIFACT].

Sources: retained setup outputs and the three named scratch Codex config files.
For the confirmatory folder, also repeat the original sed timeout substitution.
This recovery helper starts no service and performs no network requests.
"""
from pathlib import Path
import subprocess
import sys

state = Path(sys.argv[1]).expanduser().resolve()
here = Path(__file__).resolve().parent
home = Path.home()
user = home.name


def copy_sanitized(source, destination):
    text = source.read_text(encoding="utf-8")
    text = text.replace(str(state), "<STATE>").replace(str(home), "~")
    text = text.replace(user, "<user>")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


copy_sanitized(state / "setup" / "Modelfile", here / "Modelfile")
for name in ("ollama-launch.config.toml", "llamacpp-gate.config.toml", "model.json"):
    copy_sanitized(state / "scratch-home" / ".codex" / name, here / "codex-config" / name)
for source in sorted((state / "setup").iterdir()):
    if source.is_file() and not source.name.endswith(".log"):
        copy_sanitized(source, here / "setup" / source.name)
freeze = state / "research" / "mcp-venv-freeze.txt"
if freeze.is_file():
    copy_sanitized(freeze, here / "setup" / freeze.name)
if len(sys.argv) == 3:
    first = Path(sys.argv[2]).resolve()
    result = subprocess.run(
        ["rtk", "proxy", "sed", "s/^RUN_TIMEOUT_SEC=300$/RUN_TIMEOUT_SEC=1200/", str(first / "gate_env.sh")],
        check=True, capture_output=True,
    )
    (here / "gate_env.sh").write_bytes(result.stdout)
print("Re-created sanitized auxiliary files.")
