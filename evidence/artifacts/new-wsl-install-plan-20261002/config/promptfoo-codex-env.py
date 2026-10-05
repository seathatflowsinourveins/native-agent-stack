#!/usr/bin/env python3
"""Forward the gateway credential's name to Promptfoo; never copy its value.

Codex rust-v0.159.3:codex-rs/rmcp-client/src/utils.rs:16-26 and the official
https://developers.openai.com/codex/mcp document the native env_vars allowlist.
The text-preserving merge and compare-and-swap writer are reused unchanged from
this PR: tools/adoption/new_wsl_client_config.py:1623,1735
and tools/adoption/apply_codex_lane.py:271.
"""
import os
from pathlib import Path
import stat
import sys
import tomllib

sys.path.insert(0, os.environ["repo_root"])
from tools.adoption import new_wsl_client_config as client_config

target = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
if target.is_symlink() or not target.is_file():
    raise SystemExit("Promptfoo needs a regular native Codex config.toml; nothing was changed.")
original = target.read_bytes()
existing = tomllib.loads(original.decode("utf-8"))
rendered = {"mcp_servers": {"promptfoo": {"env_vars": ["GATEWAY_API_KEY"]}}}
merge = client_config.plan_merge(existing, rendered)
if merge.conflicts:
    raise SystemExit("Promptfoo's existing Codex env_vars differs; retained for the owner to reconcile.")
updated = client_config.merge_toml_text(original.decode("utf-8"), merge)
if client_config.first_difference(tomllib.loads(updated), merge.expected) is not None:
    raise SystemExit("Promptfoo Codex env_vars did not read back as the preserving merge.")
if updated.encode("utf-8") != original:
    client_config.lane.atomic_write(
        target, updated.encode("utf-8"), stat.S_IMODE(target.stat().st_mode),
        client_config.lane.sha256_bytes(original),
    )
