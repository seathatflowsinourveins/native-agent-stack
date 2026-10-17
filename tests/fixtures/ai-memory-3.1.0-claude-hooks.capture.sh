#!/usr/bin/env bash
# Print-mode capture of the Claude Code hooks ai-memory 3.1.0's own installer writes, for
# tests/test_new_wsl_client_config.py OneHookWriterTests (the CC's ruling D1 for PR (b) condition 4).
#
# Usage: ai-memory-3.1.0-claude-hooks.capture.sh <ai-memory binary> <empty scratch dir> <fixture out>
#
# It runs `install-hooks --agent claude-code --no-capture-prompts` WITHOUT --apply, which prints the hook payload and
# writes no agent config, credential or capture mode (akitaonrails/ai-memory@11ca7c5b
# crates/ai-memory-cli/src/commands/install_hooks.rs:704-708 and 1020-1060, render_claude_code 6464-6540). The run is
# isolated: a scratch --data-dir with no config, a scratch HOME and CLAUDE_CONFIG_DIR (so the installer infers nothing
# from a live ~/.claude.json, install_hooks.rs:668-673), and an empty environment (no AI_MEMORY_AUTH_TOKEN). With no
# config the server URL is upstream's default bind, http://127.0.0.1:49374 (templates/config.default.toml:10), which is
# also adoption/hosts/example.json's AI_MEMORY_URL.
#
# The payload embeds the running binary's resolved path (render_shared.rs:2094-2125) and the scratch data dir, both of
# which name this host's user. The fixture replaces exactly those two strings, and the binary's directory, with the
# example host's paths (/home/example/...), so the committed file names no personal path. The raw stdout is not
# recorded, not even by digest: it held those host paths, so no reader could recompute its digest from public bytes.
set -euo pipefail
bin="$(readlink -f -- "$1")"; scratch="$2"; out="$3"
expected=bac68e5122614913e447dd7286a9092ea2237f2d6a0f684f334e907002164872   # run pin: outputs/release-binary-sha256.txt
actual="$(sha256sum -- "$bin" | cut -d' ' -f1)"
[[ "$actual" == "$expected" ]] || { echo "binary sha256 $actual is not the run pin's $expected" >&2; exit 1; }
[[ -d "$scratch" && -z "$(ls -A -- "$scratch")" ]] || { echo "scratch dir must exist and be empty" >&2; exit 1; }
mkdir -m 0700 "$scratch/sandbox-home" "$scratch/data"
version="$(env -i PATH=/usr/bin:/bin HOME="$scratch/sandbox-home" "$bin" --version)"
captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
env -i PATH=/usr/bin:/bin HOME="$scratch/sandbox-home" CLAUDE_CONFIG_DIR="$scratch/sandbox-home/.claude" \
  "$bin" --data-dir "$scratch/data" install-hooks --agent claude-code --no-capture-prompts \
  > "$scratch/raw.stdout" 2> "$scratch/raw.stderr"
if grep -Eq 'Auth:|AI_MEMORY_AUTH_TOKEN' "$scratch/raw.stdout"; then
  echo "the payload carries a credential line; nothing written" >&2; exit 1
fi
python3 - "$bin" "$scratch" "$out" "$version" "$actual" "$captured" <<'PY'
import json, os, sys
bin_path, scratch, out, version, digest, captured = sys.argv[1:]
raw = open(os.path.join(scratch, "raw.stdout"), encoding="utf-8").read()
start = raw.index("\n{")   # the payload follows the '#' header lines and one blank line
payload_text = raw[start + 1:]
replacements = [(bin_path, "/home/example/.local/lib/ai-memory/ai-memory"),
                (os.path.dirname(bin_path), "/home/example/.local/lib/ai-memory"),
                (os.path.join(scratch, "data"), "/home/example/.local/share/ai-memory")]
for old, new in replacements:
    payload_text = payload_text.replace(old, new)
payload = json.loads(payload_text)
text = json.dumps(payload)
for leftover in (scratch, os.path.dirname(bin_path), os.path.expanduser("~")):
    if leftover in text:
        sys.exit("a host path survived the replacements; nothing written")
fixture = {
    "schema": "native-agent-stack/ai-memory-print-mode-fixture/v1",
    "captured_utc": captured,
    "command": ("env -i PATH=/usr/bin:/bin HOME=<scratch>/sandbox-home CLAUDE_CONFIG_DIR=<scratch>/sandbox-home/.claude "
                "<bin> --data-dir <scratch>/data install-hooks --agent claude-code --no-capture-prompts"),
    "capture_script": "tests/fixtures/ai-memory-3.1.0-claude-hooks.capture.sh",
    "binary": {"version": version, "sha256": digest,
               "run_pin": "evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017/run-pin.json"},
    "upstream": "akitaonrails/ai-memory@11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea (tag v3.1.0)",
    "server_url": "http://127.0.0.1:49374",
    "replacements": ["<bin> -> /home/example/.local/lib/ai-memory/ai-memory",
                     "<bin directory> -> /home/example/.local/lib/ai-memory",
                     "<scratch>/data -> /home/example/.local/share/ai-memory"],
    "settings": payload,
}
with open(out, "w", encoding="utf-8") as stream:
    json.dump(fixture, stream, indent=2, ensure_ascii=False)
    stream.write("\n")
PY
