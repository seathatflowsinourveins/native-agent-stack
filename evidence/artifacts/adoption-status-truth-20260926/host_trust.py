#!/usr/bin/env python3
"""local_integration, read-only: this host's Codex ai-memory hook trust as the fixed checker reads it, value-free.

    host_trust.py REPO CROSSCHECK_JSON

Reads the user Codex home (CODEX_HOME, else ~/.codex) the way REPO's scripts/adoption_status.py --client-wiring
does, in-process, and prints per hook only booleans: whether Codex loads it, whether it runs ai-memory's hook,
whether its [hooks.state] entry records a trusted_hash, whether that hash equals the hook's current hash, and
whether it is enabled. It starts no Codex. CROSSCHECK_JSON is the value-free summary of Codex 0.157.1's own
app-server hooks/list taken earlier on this host (its per-hook trust verdicts and whether the checker's hash
equalled Codex's currentHash); this script adds the time it was taken (the file's mtime) and the last-write
times of hooks.json and config.toml, so a reader can see whether Codex's verdict still covers the current files.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

repo, crosscheck = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(repo / "scripts"))
import adoption_status  # noqa: E402


def utc(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


home = os.environ.get("HOME") or str(Path.home())
codex_home = os.environ.get("CODEX_HOME")
codex_dir = Path(codex_home or f"{home}/.codex")
key_root = os.path.realpath(codex_home) if codex_home else os.path.normpath(f"{home}/.codex")
events = adoption_status.codex_hooks_json((codex_dir / "hooks.json").read_text(encoding="utf-8"))
hooks = adoption_status.codex_hook_hashes(f"{key_root}/hooks.json", events)
states = adoption_status.codex_hook_states(adoption_status.read_client_file(codex_dir / "config.toml", "toml"))
wiring = adoption_status.codex_wiring(codex_dir, key_root)
observed = json.loads(crosscheck.read_text(encoding="utf-8"))
print(json.dumps({
    "codex_hooks_list": {
        "taken_at_utc": utc(crosscheck.stat().st_mtime), "codex": "codex-cli 0.157.1",
        "hooks": [{key: hook[key] for key in ("event", "source", "plugin", "ai_memory", "enabled", "trust",
                                              "checker_hash_equals_codex") if key in hook}
                  for entry in observed["entries"][:1] for hook in entry["hooks"]],
        "ai_memory_user_hooks": observed["ai_memory_user_hooks"],
        "ai_memory_user_hooks_trusted": observed["ai_memory_user_hooks_trusted"]},
    "hook_files_last_written_utc": {name: utc((codex_dir / name).stat().st_mtime)
                                    for name in ("hooks.json", "config.toml")},
    "fixed_checker": {
        "run_at_utc": utc(time.time()),
        "hooks": [{"event": event, "loads": loads, "ai_memory": ai_memory,
                   "trusted_hash_recorded": "trusted_hash" in states.get(key, {}),
                   "current_hash_equals_trusted_hash": states.get(key, {}).get("trusted_hash") == digest,
                   "enabled": states.get(key, {}).get("enabled") is not False}
                  for key, (event, loads, digest, ai_memory) in sorted(hooks.items(), key=lambda item: item[1][0])],
        "codex_client_wiring": wiring},
}, indent=1))
