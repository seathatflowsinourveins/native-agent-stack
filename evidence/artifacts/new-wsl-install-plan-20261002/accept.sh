#!/usr/bin/env bash
# Current integration: 98 primary acceptance stages and two additional checks, from the merged 80-row plan.
# Historical 64-row revision ran on 2026-10-02 in a throwaway distribution (real-distribution-validation.json), and later that day, as merged to main (6652b78e), once on the destination distribution; the record of that run is private, and its public receipt comes with that distribution's acceptance.
# Five rows were added after the throwaway run, from the layer consensus of 2026-10-02 (69 foundation rows). The checks of skill-discovery and skill-authoring have not run anywhere; research-skill and credential-custody install nothing and have nothing to check; the fix-wave adds native review checks.
# On 2026-10-03 the two local-model rows (local-generation-model, embedding-model) became installable after their measurement; like their installation, their checks run only with --only, and as plan rows they have not run anywhere.
# Wave 2 (2026-10-03): memory-owner, code-search, context-supply and statusline gained checks, and research-harnesses
# and tobi-qmd were revised; none of these checks has run anywhere.
# Wave 3 (2026-10-04, the owner's decision, amendment 4): the ten token-efficiency owner rows, ccusage and
# session-analytics gained checks, and code-search checks SocratiCode's installed version; none of these checks has run anywhere.
# Checks are quoted upstream commands/parameterizations from install-plan.json and SOURCES.md.
# Fix-wave (2026-10-04): all eight builders integrated; revised destination commands remain UNRUN.
# Sources and remaining gates: docs/decisions/2026-10-04-2604-e2e-fix-wave.md.
set -euo pipefail
if (( EUID == 0 )); then printf 'Refusing to run as root.\n' >&2; exit 1; fi
plan_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$plan_dir/../../.." && pwd)"
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack"
export plan_dir repo_root tool_root config_root
export PATH="$HOME/.local/bin:$PATH"
only=''
stage=post_install
usage() { printf 'Usage: %s [--only <slot>] [--stage post_install|service_health|after_sign_in]\n' "$0" >&2; }
while (( $# )); do
  case "$1" in
    --only) (( $# >= 2 )) || { printf 'Missing --only slot.\n' >&2; exit 2; }; only="$2"; shift 2 ;;
    --stage) (( $# >= 2 )) || { printf 'Missing --stage value.\n' >&2; exit 2; }; stage="$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done
case "$stage" in
  post_install|service_health|after_sign_in) ;;
  *) printf 'Unknown stage: %s\n' "$stage" >&2; usage; exit 2 ;;
esac
case "$only" in
  ''|claude-code|codex|claude-agent-sdk|codex-sdk-and-codex-exec-app-server|trail-of-bits-security-skills-trailofbits-skills|engineering-process-skills|skill-discovery|skill-authoring|research-skill|mcporter|mcp-inspector|agent-messaging|sandbox-runtime-srt|isolation-container-boundary|serena|claude-plugins-official-code-intelligence-lsp-pl|structural-search|code-search|embedding-model|reranker-model|tobi-qmd|mineru|trafilatura|playwright-cli|web-search-provider|memory-owner|ccusage|context-supply|statusline|command-output|output-compression|code-index|code-graph|repo-packing|structured-data|doc-conversion|api-docs|trace-viewer|token-lane-carriers|otel-collector-contrib|prometheus|loki|grafana|phoenix|local-model-server|alerting|local-generation-model|session-analytics|inspect-ai|harbor-containerized-agent-e2e-runner|promptfoo|zizmor|attest|syft|dependabot|codeql-sarif|actionlint-kjanat|dagu|docker-compose|container-engine|gpu-container-runtime|betterleaks|trufflehog|credential-custody|git|gh-github-cli|worktrunk|difftastic|claude-code-action|agent-structural-diff|cross-family-review|mise|restic|chezmoi|base-distribution|gpt-gateway|agent-runtime-worker|research-harnesses|credential-guard|convergence-validators) ;;
  *) printf 'Unknown slot: %s\n' "$only" >&2; exit 2 ;;
esac
# Planned. Two checks change into repo_root, so the plan runs from a checkout of the repository (README.md).
[[ -e "$repo_root/.git" ]] || { printf 'Run this plan from a checkout of the repository: %s is not a git checkout (see README.md).\n' "$repo_root" >&2; exit 1; }

failed=0
path_ready=false
prepare_path() {
  if $path_ready; then return; fi
  # Only prepare the environment when an actual check is selected; skips run no tools.
  if command -v mise >/dev/null && [[ -d "$tool_root" ]]; then
    local mise_environment
    mise_environment="$(cd -- "$tool_root" && command mise env -s bash)" || return "$?"
    eval "$mise_environment"
  fi
  # Source: https://raw.githubusercontent.com/jdx/mise/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/docs/dev-tools/shims.md#L70
  export PATH="${MISE_SHIMS_DIR:-${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims}:$PATH"
  if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"; fi
  path_ready=true
}
check() {
  local slot="$1" program="$3" rc=0
  # Kind/source remain in JSON and beside each command. Suppress stdout, which
  # diagnostics/model examples can fill with private config; retain stderr/status.
  if prepare_path && bash -euo pipefail -c "$program" >/dev/null; then rc=0; else rc=$?; failed=1; fi
  printf '%s | %s | %s\n' "$slot" "$stage" "$rc"
}
skipped() { printf '%s | %s | skipped\n' "$1" "$stage"; }

claude-code() {
  # Claude Code; https://github.com/anthropics/claude-code
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://code.claude.com/docs/en/setup.md#L184
      check claude-code smoke 'claude doctor'
      ;;
    *) skipped claude-code ;;
  esac
}

codex() {
  # Codex; https://github.com/openai/codex
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/main.rs#L110
      check codex 'version only' 'codex --version'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/doctor.rs#L1287
      check codex smoke 'codex doctor'
      ;;
    *) skipped codex ;;
  esac
}

claude-agent-sdk() {
  # Claude Agent SDK; https://github.com/anthropics/claude-agent-sdk-python
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/src/claude_agent_sdk/__init__.py#L68
      check claude-agent-sdk 'version only' '"$tool_root/claude-agent-sdk/bin/python" -c '"'"'from claude_agent_sdk import __version__; print(__version__)'"'"''
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/v0.2.163/README.md#L22
      check claude-agent-sdk smoke '"$tool_root/claude-agent-sdk/bin/python" - <<'"'"'PY'"'"'
import anyio
from claude_agent_sdk import query

async def main():
    async for message in query(prompt="What is 2 + 2?"):
        print(message)

anyio.run(main)
PY'
      ;;
    *) skipped claude-agent-sdk ;;
  esac
}

codex-sdk-and-codex-exec-app-server() {
  # Codex SDK and codex exec/app-server; https://github.com/openai/codex
  # Revised 2026-10-04; no WSL run is claimed.
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/npm/cli/bfacd33ccbcd908480610703b60455d2da5b57a9/docs/lib/content/commands/npm-ls.md#L13
      check codex-sdk-and-codex-exec-app-server 'version only' 'cd "$tool_root/codex-sdk"
npm ls --depth=0 @openai/codex-sdk'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/sdk/typescript/README.md#L15
      # Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1072
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L923
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1624
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1994
      check codex-sdk-and-codex-exec-app-server smoke 'cd "$tool_root/codex-sdk"
sdk_work="$(mktemp -d)"
trap '"'"'rm -rf -- "$sdk_work"'"'"' EXIT
SDK_ACCEPT_WORKDIR="$sdk_work" node --input-type=module - <<'"'"'JS'"'"'
import { Codex } from "@openai/codex-sdk";

const codex = new Codex();
const thread = codex.startThread({ skipGitRepoCheck: true, sandboxMode: "read-only", approvalPolicy: "never", workingDirectory: process.env.SDK_ACCEPT_WORKDIR });
const turn = await thread.run("Diagnose the test failure and propose a fix");

console.log(turn.finalResponse);
console.log(turn.items);
JS'
      codex-sdk-and-codex-exec-app-server-protocol
      ;;
    *) skipped codex-sdk-and-codex-exec-app-server ;;
  esac
}

codex-sdk-and-codex-exec-app-server-protocol() {
  # Separate native upstream operation; inventory fixtures cover the primary check.
  case "$stage" in
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1072
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L923
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1624
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1994
      check codex-sdk-and-codex-exec-app-server smoke 'cd "$tool_root/codex-sdk"
out="$(codex debug app-server send-message-v2 '"'"'Reply with exactly 4. Do not use tools or modify files.'"'"' </dev/null)"
grep -q '"'"'^< initialize response:'"'"' <<<"$out"
grep -q '"'"'^< thread/start response:'"'"' <<<"$out"
grep -q '"'"'^< turn/start response:'"'"' <<<"$out"
grep -qx '"'"'< turn/completed notification: Completed'"'"' <<<"$out"
grep -qF '"'"'text: "4"'"'"' <<<"$out"'
      ;;
  esac
}

trail-of-bits-security-skills-trailofbits-skills() {
  # Trail of Bits security skills (trailofbits/skills); https://github.com/trailofbits/skills
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/trailofbits/skills/82fe8226252622fa807643bdca1710901198553a/README.md#L28
      # Source: https://code.claude.com/docs/en/plugins/loading.md#L171 (marketplace clone directory), https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/git.adoc#L63 (-C)
      check trail-of-bits-security-skills-trailofbits-skills smoke 'reviewed=82fe8226252622fa807643bdca1710901198553a
actual="$(git -C "$HOME/.claude/plugins/marketplaces/trailofbits" rev-parse HEAD)"
printf '"'"'trailofbits marketplace HEAD %s, reviewed %s\n'"'"' "$actual" "$reviewed" >&2
[[ "$actual" == "$reviewed" ]]
claude plugin list && codex plugin list'
      ;;
    *) skipped trail-of-bits-security-skills-trailofbits-skills ;;
  esac
}

engineering-process-skills() {
  # mattpocock/skills (selected skills, not the bundle); https://github.com/mattpocock/skills
  # Revised 2026-10-04; no WSL run is claimed.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/fd111e59a7480c7910907e5cdc9a32a9e42ec42e/tools/adoption/install_skills.py#L554
      # Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/src/list.ts#L113
      # Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/src/remove.ts#L182
      # Source: https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L419
      # Source: https://github.com/nodejs/node/blob/v24.21.0/doc/api/process.md#L4228
      # Source: https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/skill-lock.ts#L63
      check engineering-process-skills smoke 'python3 -B "$repo_root/tools/adoption/install_skills.py" --skills-bin "$tool_root/skills-1.7.0/bin/skills" --check-only --json
listing="$(mktemp)"
trap '"'"'rm -f -- "$listing"'"'"' EXIT
DISABLE_TELEMETRY=1 "$tool_root/skills-1.7.0/bin/skills" list -g -a claude-code codex --json > "$listing"
jq -e '"'"'type == "array" and length > 0 and all(.[]; .name as $name | ["domain-modeling", "setup-matt-pocock-skills", "grill-me", "improve-codebase-architecture", "semgrep"] | index($name) == null)'"'"' "$listing" >/dev/null
for skill in domain-modeling setup-matt-pocock-skills grill-me improve-codebase-architecture semgrep; do
  for root in "$HOME/.agents/skills" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills" "${CODEX_HOME:-$HOME/.codex}/skills"; do
    if [[ -e "$root/$skill" || -L "$root/$skill" ]]; then
      printf '"'"'Excluded skill remains: %s\n'"'"' "$skill" >&2
      exit 1
    fi
  done
done
lock="${XDG_STATE_HOME:+$XDG_STATE_HOME/skills/.skill-lock.json}"
lock="${lock:-$HOME/.agents/.skill-lock.json}"
jq -e '"'"'.skills | has("domain-modeling") or has("setup-matt-pocock-skills") or has("grill-me") or has("improve-codebase-architecture") or has("semgrep") | not'"'"' "$lock" >/dev/null
jq -e '"'"'.skillOverrides.semgrep == "off" and .skillOverrides["grill-me"] == "off" and .skillOverrides["improve-codebase-architecture"] == "off"'"'"' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json" >/dev/null'
      ;;
    *) skipped engineering-process-skills ;;
  esac
}

skill-discovery() {
  # find-skills (vercel-labs/skills); https://github.com/vercel-labs/skills
  # UNRUN on every distribution: added from the layer consensus of 2026-10-02, after the clean run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L164
      check skill-discovery smoke 'want=76a98a285cb0434f3d39e1a873823556330e398b
lock="${XDG_STATE_HOME:+$XDG_STATE_HOME/skills/.skill-lock.json}"
lock="${lock:-$HOME/.agents/.skill-lock.json}"
listing="$(npx --yes skills@1.7.0 list -g -a claude-code codex --json)"
for agent in '"'"'Claude Code'"'"' Codex; do
  jq -e --arg agent "$agent" '"'"'any(.[]; .name == "find-skills" and (.agents | index($agent) != null))'"'"' <<<"$listing" >/dev/null
done
jq -e --arg hash "$want" '"'"'.skills["find-skills"].skillFolderHash == $hash'"'"' "$lock" >/dev/null'
      ;;
    *) skipped skill-discovery ;;
  esac
}

skill-authoring() {
  # skill-creator (embedded in Codex; anthropics/skills for Claude Code); https://github.com/anthropics/skills
  # Revised 2026-10-04; no WSL run is claimed.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L164
      # Source: https://raw.githubusercontent.com/anthropics/skills/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/quick_validate.py#L9
      # Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/skills/src/assets/samples/skill-creator/scripts/quick_validate.py#L10
      # Source: https://raw.githubusercontent.com/astral-sh/uv/0.12.22/docs/pip/environments.md#L100
      # Source: https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L419
      # Source: https://github.com/nodejs/node/blob/v24.21.0/doc/api/process.md#L4228
      check skill-authoring smoke 'want=3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6
lock="${XDG_STATE_HOME:+$XDG_STATE_HOME/skills/.skill-lock.json}"
lock="${lock:-$HOME/.agents/.skill-lock.json}"
listing="$(mktemp)"
trap '"'"'rm -f -- "$listing"'"'"' EXIT
npx --yes skills@1.7.0 list -g --json > "$listing"
jq -e '"'"'[.[] | select(.name == "skill-creator") | .agents] == [["Claude Code"]]'"'"' "$listing" >/dev/null
jq -e --arg hash "$want" '"'"'.skills["skill-creator"].skillFolderHash == $hash'"'"' "$lock" >/dev/null
shared_copy="$HOME/.agents/skills/skill-creator"
codex_copy="${CODEX_HOME:-$HOME/.codex}/skills/skill-creator"
[[ ! -e "$shared_copy" && ! -L "$shared_copy" && ! -e "$codex_copy" && ! -L "$codex_copy" ]]'
      skill-authoring-upstream
      ;;
    *) skipped skill-authoring ;;
  esac
}

skill-authoring-upstream() {
  # Native loader initializes the embedded cache before the unchanged upstream validators.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/anthropics/skills/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/quick_validate.py#L9
      # Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/skills/src/assets/samples/skill-creator/scripts/quick_validate.py#L10
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L2044
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/host_service.rs#L125
      # Source: https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/skills/src/lib.rs#L69
      check skill-authoring smoke 'codex debug prompt-input >/dev/null
python -B "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/skill-creator/scripts/quick_validate.py" "$HOME/.agents/skills/find-skills" || exit 1
python -B "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" "$HOME/.agents/skills/find-skills" || exit 1'
      ;;
  esac
}

mcporter() {
  # mcporter; https://github.com/openclaw/mcporter
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/openclaw/mcporter/v0.14.2/docs/install.md#L52
      check mcporter smoke 'mcporter list'
      ;;
    *) skipped mcporter ;;
  esac
}

sandbox-runtime-srt() {
  # sandbox-runtime (srt); https://github.com/anthropics/sandbox-runtime
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/anthropics/sandbox-runtime/v0.0.78/README.md#L168
      check sandbox-runtime-srt smoke 'srt echo "hello world"'
      ;;
    after_sign_in)
      # Kind: native client integration; Source: https://raw.githubusercontent.com/anthropics/sandbox-runtime/v0.0.78/README.md#L168
      check sandbox-runtime-srt 'native client integration' 'bash "$config_root/srt-client-accept.sh"'
      ;;
    *) skipped sandbox-runtime-srt ;;
  esac
}
serena() {
  # Serena; https://github.com/oraios/serena
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/oraios/serena/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L957
      check serena smoke 'serena_probe="$(mktemp -d)"
trap '"'"'rm -rf -- "$serena_probe"'"'"' EXIT
SERENA_HOME="$serena_probe" serena init
test -s "$serena_probe/serena_config.yml"
serena project health-check "$repo_root"'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/oraios/serena/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/docs/02-usage/030_clients.md#L134
      check serena smoke 'umask 077
native_receipts="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance"
mkdir -p -- "$native_receipts"
native_probe="$(mktemp -d "$native_receipts/serena.XXXXXX")"
cd "$repo_root"
prompt='"'"'Use the configured Serena MCP server. Activate the current directory as the project and follow its session initialization if required. Call find_symbol with name_path_pattern register_file, relative_path scripts/host_receipts.py and include_body true. Then call find_referencing_symbols with name_path register_file and the same relative_path. Both calls must succeed and return the definition and real callers. Do not substitute shell or file-reading tools. Report a failure if either call fails.'"'"'
claude -p "$prompt" --output-format stream-json --verbose --allowedTools mcp__serena__activate_project,mcp__serena__initial_instructions,mcp__serena__check_onboarding_performed,mcp__serena__find_symbol,mcp__serena__find_referencing_symbols > "$native_probe/claude.jsonl"
jq -s -e '"'"'def returned($tool):
  [ .[] | select(.type == "assistant") | .message.content[]? |
    select(.type == "tool_use" and .name == $tool) | .id ] as $ids |
  any(.[] | select(.type == "user") | .message.content[]?;
    .type == "tool_result" and (.tool_use_id as $id | $ids | index($id) != null) and
    (.is_error != true) and (.content | tostring | contains("register_file")) and
    (.content | tostring | test("Error executing|No language servers") | not));
any(.[]; .type == "result" and .is_error == false) and
returned("mcp__serena__find_symbol") and returned("mcp__serena__find_referencing_symbols")'"'"' "$native_probe/claude.jsonl" >/dev/null
codex exec --json -C "$repo_root" "$prompt" </dev/null > "$native_probe/codex.jsonl"
jq -s -e '"'"'def returned($tool):
  any(.[]; .type == "item.completed" and .item.type == "mcp_tool_call" and
    .item.server == "serena" and .item.tool == $tool and .item.status == "completed" and
    .item.error == null and (.item.result.content | tostring | contains("register_file")) and
    (.item.result.content | tostring | test("Error executing|No language servers") | not));
any(.[]; .type == "turn.completed") and
(all(.[]; .type != "turn.failed" and .type != "error")) and
returned("find_symbol") and returned("find_referencing_symbols")'"'"' "$native_probe/codex.jsonl" >/dev/null'
      ;;
    *) skipped serena ;;
  esac
}

structural-search() {
  # ast-grep; https://github.com/ast-grep/ast-grep
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/ast-grep/ast-grep/0.45.3/README.md#L84
      check structural-search smoke 'ast-grep --version
ast_grep_probe="$(mktemp -d)"
trap '"'"'rm -rf -- "$ast_grep_probe"'"'"' EXIT
printf '"'"'callback && callback();\n'"'"' > "$ast_grep_probe/probe.ts"
ast-grep -p '"'"'$A && $A()'"'"' -l ts "$ast_grep_probe/probe.ts"
printf '"'"'callback();\n'"'"' > "$ast_grep_probe/control.ts"
out="$(ast-grep -p '"'"'$A && $A()'"'"' -l ts -r '"'"'$A?.()'"'"' "$ast_grep_probe/probe.ts")"
printf '"'"'%s\n'"'"' "$out" | grep -F '"'"'callback?.()'"'"' >/dev/null
if ast-grep -p '"'"'$A && $A()'"'"' -l ts -r '"'"'$A?.()'"'"' "$ast_grep_probe/control.ts"; then
  exit 1
else
  control_rc=$?
  test "$control_rc" -eq 1
fi'
      ;;
    *) skipped structural-search ;;
  esac
}

embedding-model() {
  # Qwen3-Embedding-0.6B through Ollama (qwen3-embedding:0.6b, Q8_0, as qwen3-embedding-8k); https://github.com/QwenLM/Qwen3-Embedding
  case "$stage" in
    post_install)
      # Files only: the pinned library manifest and the derived model's layer, in the server's model store.
      # Store: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/envconfig/config.go#L112
      # Kind: smoke; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/manifest/paths.go#L29
      check embedding-model smoke 'printf '"'"'%s  %s\n'"'"' ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d "${OLLAMA_MODELS:-$HOME/.ollama/models}/manifests/registry.ollama.ai/library/qwen3-embedding/0.6b" | sha256sum --check --status && grep -F sha256:06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439 "${OLLAMA_MODELS:-$HOME/.ollama/models}/manifests/registry.ollama.ai/library/qwen3-embedding-8k/latest" >/dev/null'
      ;;
    service_health)
      # The model's own context, then one embedding call of the model card's 1,024 dimensions
      # (https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/blob/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/README.md#L36).
      # Kind: smoke; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1659
      check embedding-model smoke 'out="$(OLLAMA_HOST=127.0.0.1:21434 ollama show qwen3-embedding-8k)" && grep -E '"'"'^ +num_ctx +8192 *$'"'"' <<<"$out" >/dev/null && curl -fsS http://127.0.0.1:21434/api/embed -d '"'"'{"model":"qwen3-embedding-8k","input":"Why is the sky blue?"}'"'"' | jq -e '"'"'(.embeddings | length) == 1 and (.embeddings[0] | length) == 1024'"'"' >/dev/null'
      ;;
    *) skipped embedding-model ;;
  esac
}

tobi-qmd() {
  # tobi/qmd; https://github.com/tobi/qmd
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L671
      check tobi-qmd smoke 'qmd status'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L1021 (doctor: runtime, embedding fingerprints, GPU probe); https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L1014 (status)
      # Needs the interim embedder provisioned and the index embedded (embed -f); the wave-2 retrieval ruling, change 16. UNRUN.
      check tobi-qmd smoke 'f="$HOME/.local/share/qmd/models/Qwen3-Embedding-0.6B-Q8_0.gguf"
printf '\''%s  %s\n'\'' 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439 "$f" | sha256sum --check --status
grep -qxF "  embed: $f" "$HOME/.config/qmd/native-agent-stack-catalog.yml"
qmd --index native-agent-stack-catalog status
qmd --index native-agent-stack-catalog doctor'
      ;;
    *) skipped tobi-qmd ;;
  esac
}

mineru() {
  # MinerU; https://github.com/opendatalab/mineru
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/opendatalab/MinerU/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L365
      check mineru smoke 'mineru --help
python3 -B "$repo_root/tools/adoption/install_skills.py" --manifest "$plan_dir/config/mineru-skills-manifest.json" --skills-bin "$tool_root/skills-1.7.0/bin/skills" --check-only --json --only mineru
skill_probe="$(mktemp -d)"
trap '"'"'rm -rf -- "$skill_probe"'"'"' EXIT
DISABLE_TELEMETRY=1 "$tool_root/skills-1.7.0/bin/skills" list -g -a claude-code codex --json > "$skill_probe/list.json"
for agent in '"'"'Claude Code'"'"' Codex; do
  jq -e --arg agent "$agent" '"'"'any(.[]; .name == "mineru" and (.agents | index($agent) != null))'"'"' "$skill_probe/list.json" >/dev/null
done
test "$(readlink -f "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/mineru")" = "$(readlink -f "$HOME/.agents/skills/mineru")"
mineru-kit models verify --tier standard
printf '"'"'%s  %s\n'"'"' f3b3be345bf2df8979f2491ca9466e078e4fd1d6a216611faa8566e4c44d474b "$tool_root/mineru/demo1.pdf" | sha256sum --check --status'
      ;;
    service_health)
      # Kind: smoke; Source: https://raw.githubusercontent.com/opendatalab/MinerU/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L559
      check mineru smoke 'umask 077
native_receipts="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance"
mkdir -p -- "$native_receipts"
mineru_probe="$(mktemp -d "$native_receipts/mineru.XXXXXX")"
for attempt in {1..60}; do
  mineru server status --json > "$mineru_probe/status.json"
  if jq -e '"'"'.running == true and .parse_server.local.healthy == true and .parse_server.local.managed_tier == "standard" and (.parse_server.local.supported_tiers | index("standard") != null)'"'"' "$mineru_probe/status.json" >/dev/null; then break; fi
  sleep 5
done
jq -e '"'"'.running == true and .parse_server.local.healthy == true and .parse_server.local.managed_tier == "standard" and (.parse_server.local.supported_tiers | index("standard") != null)'"'"' "$mineru_probe/status.json" >/dev/null
mineru parse "$tool_root/mineru/demo1.pdf" --tier standard --pages 1 --wait 600 --json > "$mineru_probe/parse.json"
jq -e '"'"'.error == null and .parse.status == "done" and .parse.tier == "standard" and (.content.content | test("afforestation"; "i"))'"'"' "$mineru_probe/parse.json" >/dev/null
locator="$(jq -er '"'"'(.content.request_scope.locator // .content.content_ranges[0].start) | select(startswith("doc:")) | split("/block:")[0] | split("/char:")[0]'"'"' "$mineru_probe/parse.json")"
mineru read "$locator" --json > "$mineru_probe/read.json"
jq -e '"'"'.tier == "standard" and (.content | test("afforestation"; "i"))'"'"' "$mineru_probe/read.json" >/dev/null'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/opendatalab/MinerU/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/skills/mineru/SKILL.md#L236
      check mineru smoke 'umask 077
native_receipts="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance"
mkdir -p -- "$native_receipts"
native_probe="$(mktemp -d "$native_receipts/mineru-native.XXXXXX")"
cd "$repo_root"
prompt="Use the installed mineru skill to read the public fixture $tool_root/mineru/demo1.pdf locally. Run mineru parse on that absolute path with --tier standard --pages 1 --wait 600 --json in one tool call. Then use a returned doc locator (choose page 1) in a separate mineru read call with --json. Both tool results must contain the first-page text about afforestation. Do not use --remote, another parser, a pipeline, or a model-written summary as a substitute. Report failure if either command fails."
claude -p "$prompt" --output-format stream-json --verbose --allowedTools Skill,Bash > "$native_probe/claude.jsonl"
jq -s -e '"'"'def returned($operation):
  [ .[] | select(.type == "assistant") | .message.content[]? |
    select(.type == "tool_use" and .name == "Bash" and (.input.command | contains($operation))) | .id ] as $ids |
  any(.[] | select(.type == "user") | .message.content[]?;
    .type == "tool_result" and (.tool_use_id as $id | $ids | index($id) != null) and
    .is_error != true and (.content | tostring | test("afforestation"; "i")));
any(.[]; .type == "result" and .is_error == false) and
returned("mineru parse") and returned("mineru read")'"'"' "$native_probe/claude.jsonl" >/dev/null
codex exec --json -C "$repo_root" "$prompt" </dev/null > "$native_probe/codex.jsonl"
jq -s -e '"'"'def returned($operation):
  any(.[]; .type == "item.completed" and .item.type == "command_execution" and
    (.item.command | contains($operation)) and .item.status == "completed" and .item.exit_code == 0 and
    (.item.aggregated_output | test("afforestation"; "i")));
any(.[]; .type == "turn.completed") and
(all(.[]; .type != "turn.failed" and .type != "error")) and
returned("mineru parse") and returned("mineru read")'"'"' "$native_probe/codex.jsonl" >/dev/null'
      ;;
    *) skipped mineru ;;
  esac
}

playwright-cli() {
  # Playwright CLI; https://github.com/microsoft/playwright-cli
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/microsoft/playwright/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/mcp/config.ts#L285
      check playwright-cli smoke 'playwright-cli open https://playwright.dev --browser=chromium && playwright-cli close'
      ;;
    *) skipped playwright-cli ;;
  esac
}

memory-owner() {
  # ai-memory 2.5.2 (interim, amendment 3); https://github.com/akitaonrails/ai-memory
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/cli.rs#L11 (--version); https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/render_shared.rs#L907 (the seven Codex events install-hooks writes)
      # The hooks.json line is this project's integration check, not upstream acceptance.
      check memory-owner smoke 'ai-memory --version
jq -e '\''[("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd") as $event | any(.hooks[$event][]?.hooks[]?; (.command // "") | contains("ai-memory"))] | all'\'' "${CODEX_HOME:-$HOME/.codex}/hooks.json" >/dev/null'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/serve.rs#L2712 (/healthz); status: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L2149
      check memory-owner health 'curl -fsS http://127.0.0.1:29374/healthz
AI_MEMORY_SERVER_URL=http://127.0.0.1:29374 ai-memory status --json'
      ;;
    *) skipped memory-owner ;;
  esac
}
code-search() {
  # semble 0.6.1 + SocratiCode 1.15.0 (interim, amendments 3 and 4); https://github.com/MinishLab/semble; https://github.com/giancarloerra/SocratiCode
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/src/semble/cli.py#L269 (--version); https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/README.md#L114 (search, path, --format)
      # The probe search after the version line is this project's integration check, not upstream acceptance.
      # The last line reads SocratiCode's installed version from its package.json, never by running it: every invocation starts its MCP server.
      # Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/14048b840425c2569e0df60a6596e94e601da15b/adoption/pins-linux-x86_64.json#L361 (the socraticode pin's version_probe, npm-metadata)
      check code-search smoke 'semble --version
probe="$(mktemp -d)"
trap '\''rm -rf -- "$probe"'\'' EXIT
printf '\''%s\n'\'' '\''def parse_invoice_total(lines):'\'' '\''    return sum(float(line.split(",")[2]) for line in lines)'\'' > "$probe/invoice_probe.py"
SEMBLE_MODEL_NAME="$HOME/.local/share/semble/potion-code-16M-v2-e9d2a44c" SEMBLE_CACHE_LOCATION="$probe/cache" semble search "sum the invoice totals" "$probe" --format text | grep -q invoice_probe.py
[[ "$(jq -r .version "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/socraticode-1.15.0/lib/node_modules/socraticode/package.json")" == 1.15.0 ]]'
      ;;
    *) skipped code-search ;;
  esac
}
context-supply() {
  # context-mode 1.0.169 (owner default, amendment 4; the wave-2 interim it replaces had the same checks); https://github.com/mksglu/context-mode
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L78 (verify the install); https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/plugin_cmd.rs#L447 (plugin list --json); https://code.claude.com/docs/en/plugins/loading (autoUpdate on the extraKnownMarketplaces or known_marketplaces.json entry, read 2026-10-03)
      # The last three lines are this project's integration check that marketplace auto-update stays off for context-mode.
      check context-supply smoke 'want=6f0cc6841c687e754059f36714a11233fda1a02b
sha="$(jq -r '\''[.plugins["context-mode@context-mode"][] | select(.scope == "user") | .gitCommitSha][0]'\'' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json")"
[[ "$sha" == "$want" ]] || [[ "$(curl -fsSL "https://api.github.com/repos/mksglu/context-mode/compare/$want...$sha" | jq -r '\''[.files[].filename] | unique | join(",")'\'')" == stats.json ]]
codex plugin list --json | jq -e '\''any(.installed[]; .pluginId == "context-mode@context-mode" and .enabled)'\'' >/dev/null
[[ "$(jq -r .version "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/context-mode-1.0.169/lib/node_modules/context-mode/package.json")" == 1.0.169 ]]
config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
jq -e '\''(.extraKnownMarketplaces["context-mode"].autoUpdate // false) == false'\'' "$config_dir/settings.json" >/dev/null
jq -e '\''(.["context-mode"].autoUpdate // false) == false'\'' "$config_dir/plugins/known_marketplaces.json" >/dev/null'
      ;;
    *) skipped context-supply ;;
  esac
}
statusline() {
  # claude-hud 0.10.0 and the Codex footer; https://github.com/jarrodwatts/claude-hud
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/commands/setup.md#L72 (sample input through the configured command, run through bash as Claude Code runs it, L10: two HUD lines); https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs#L79 (the launcher copy the command runs); https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/statusline.mjs#L29 (the launcher runs the highest cached version); https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs#L94 (install keeps an earlier claude-hud statusLine with its refreshInterval, and the install adds 5 only when absent, so any valid interval passes); https://raw.githubusercontent.com/SchemaStore/schemastore/de76181a2ab215431d3e9314bc14f83cc3b01ad2/src/schemas/json/claude-code-settings.json#L2454 (refreshInterval: an integer, minimum 1, in the settings schema https://code.claude.com/docs/en/settings.md names); https://raw.githubusercontent.com/apple-oss-distributions/text_cmds/592aaf8a50aa5810ee8183df20f0ba48bb23aa7e/wc/wc.c#L214 (BSD and macOS wc print the line count as " %7ju", padded, so both wc -l counts are compared as numbers)
      check statusline smoke 'config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
jq -e '\''[.plugins["claude-hud@claude-hud"][] | select(.scope == "user") | .version] == ["0.10.0"]'\'' "$config_dir/plugins/installed_plugins.json" >/dev/null
versions="$(ls -d "$config_dir"/plugins/cache/*/claude-hud/*/ | wc -l)"
cmp -s "$config_dir/plugins/claude-hud/statusline.mjs" "$(ls -d "$config_dir"/plugins/cache/*/claude-hud/0.10.0)/scripts/statusline.mjs"
jq -e '\''.statusLine.type == "command" and (.statusLine.refreshInterval | type == "number" and . >= 1 and . == floor)'\'' "$config_dir/settings.json" >/dev/null
configured="$(jq -r '\''.statusLine.command'\'' "$config_dir/settings.json")"
lines="$(echo '\''{"model":{"display_name":"Opus"},"context_window":{"used_percentage":12,"context_window_size":200000}}'\'' | bash -c "$configured" | wc -l)"
[[ "$versions" -eq 1 && "$lines" -ge 2 && "$configured" == *"$config_dir/plugins/claude-hud/statusline.mjs"* ]]'
      ;;
    *) skipped statusline ;;
  esac
}
ccusage() {
  # ccusage 20.0.26; https://github.com/ccusage/ccusage
  # UNRUN on every distribution: the 2026-10-04 verified-E2E plan fix.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/ccusage/ccusage/d9821088b98aa536c7a385aa1a4579d6fa02269b/docs/guide/installation.md#L133
      check ccusage smoke 'meter="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/ccusage"
[[ "$("$meter" --version)" == "ccusage 20.0.26" ]]
"$meter" --help >/dev/null
fixture="$(mktemp -d "${TMPDIR:-/tmp}/new-wsl-ccusage.XXXXXX")"
trap '"'"'rm -rf -- "$fixture"'"'"' EXIT
mkdir -p "$fixture/claude/projects/project-alpha/session-alpha" "$fixture/claude/projects/project-beta/session-beta" "$fixture/codex/sessions/project-alpha"
cp -- "$config_root/ccusage-20.0.26-claude-alpha.jsonl.fixture" "$fixture/claude/projects/project-alpha/session-alpha/chat.jsonl"
cp -- "$config_root/ccusage-20.0.26-claude-beta.jsonl.fixture" "$fixture/claude/projects/project-beta/session-beta/chat.jsonl"
cp -- "$config_root/ccusage-20.0.26-codex-alpha.jsonl.fixture" "$fixture/codex/sessions/project-alpha/session-alpha.jsonl"
CLAUDE_CONFIG_DIR="$fixture/claude" "$meter" claude daily --offline --no-cost --json --timezone UTC > "$fixture/claude.json"
CODEX_HOME="$fixture/codex" "$meter" codex daily --offline --no-cost --speed standard --json --timezone UTC > "$fixture/codex.json"
jq -e '"'"'.totals | .totalTokens == 1240 and .inputTokens == 730 and .outputTokens == 310 and .cacheCreationTokens == 90 and .cacheReadTokens == 110 and (has("totalCost") | not)'"'"' "$fixture/claude.json" >/dev/null
jq -e '"'"'.totals | .totalTokens == 4200 and .inputTokens == 2750 and .cacheReadTokens == 750 and .outputTokens == 425 and .reasoningOutputTokens == 275 and (has("totalCost") | not)'"'"' "$fixture/codex.json" >/dev/null'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/ccusage/ccusage/d9821088b98aa536c7a385aa1a4579d6fa02269b/apps/ccusage/README.md#L65
      check ccusage smoke 'meter="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/ccusage"
day="$(date -u +%Y%m%d)"
run="$config_root/ccusage-acceptance/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p -- "$run"
chmod 0700 "$run"
printf -v claude_cmd '"'"'set -o pipefail; %q claude daily --since %q --timezone UTC --offline --no-cost --json | jq -c .totals'"'"' "$meter" "$day"
printf -v codex_cmd '"'"'set -o pipefail; %q codex daily --since %q --timezone UTC --offline --no-cost --speed standard --json | jq -c .totals'"'"' "$meter" "$day"
claude -p --effort max --max-turns 4 --tools Bash --allowedTools Bash --verbose --output-format stream-json "Run this exact read-only meter command once: $claude_cmd. Report only its numeric totals; read no authentication or credential files." > "$run/claude.jsonl" 2> "$run/claude.stderr"
codex exec --json -c '"'"'model_reasoning_effort="max"'"'"' --skip-git-repo-check "Run this exact read-only meter command once: $codex_cmd. Report only its numeric totals; read no authentication or credential files." </dev/null > "$run/codex.jsonl" 2> "$run/codex.stderr"
jq -s -e --arg client claude --arg meter "$meter" -f "$config_root/ccusage-session.jq" "$run/claude.jsonl" >/dev/null
jq -s -e --arg client codex --arg meter "$meter" -f "$config_root/ccusage-session.jq" "$run/codex.jsonl" >/dev/null
"$meter" claude daily --since "$day" --timezone UTC --offline --no-cost --json > "$run/claude-usage.json"
"$meter" codex daily --since "$day" --timezone UTC --offline --no-cost --speed standard --json > "$run/codex-usage.json"
jq -e '"'"'.totals.totalTokens > 0'"'"' "$run/claude-usage.json" >/dev/null
jq -e '"'"'.totals.totalTokens > 0'"'"' "$run/codex-usage.json" >/dev/null'
      ;;
    *) skipped ccusage ;;
  esac
}
command-output() {
  # RTK 0.51.0 (owner row, amendment 4); https://github.com/rtk-ai/rtk
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L121 (--version); https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L193 (rtk git log); https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L313 (rtk proxy, the raw passthrough); https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L551 (RTK_TELEMETRY_DISABLED)
      # Planned exact 0.51.0 version; the archive digest was verified separately; the two log lines run in this checkout.
      # Planned. Source: https://github.com/rtk-ai/rtk/blob/v0.51.0/src/main.rs#L3072-L3100 (excluded commands exit 1 with No rewrite; the positive control exits 0 with its rewrite).
      # Planned. Source: https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L133 (rtk init --show --codex: the Global hook and RTK.md lines are [ok]); codex_hook_trust.py --check exits 0 only when the named hook is trusted at its current hash and no execution rule of the user layer would be bypassed by the rewrite (exit 5: not trusted; exit 6: trusted beside such a rule, which catches a rule added after the grant).
      check command-output smoke 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$("$e/bin/rtk" --version)" == "rtk 0.51.0" ]]
cd "$repo_root"
RTK_TELEMETRY_DISABLED=1 "$e/bin/rtk" git log -n 3
RTK_TELEMETRY_DISABLED=1 "$e/bin/rtk" proxy git log -n 3
e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
for command in "git show HEAD:README.md | tail -20" "diff a b" "jq . x.json" "git branch -a"; do
  rc=0
  decision=$(RTK_TELEMETRY_DISABLED=1 "$e/bin/rtk" hook check "$command" 2>&1) || rc=$?
  [[ "$rc" -eq 1 && "$decision" == "No rewrite for: $command" ]]
done
decision=$(RTK_TELEMETRY_DISABLED=1 "$e/bin/rtk" hook check "git status" 2>&1)
[[ "$decision" == "rtk git status" ]]
codex_home="${CODEX_HOME:-$HOME/.codex}"
shown=$(RTK_TELEMETRY_DISABLED=1 "$e/bin/rtk" init --show --codex 2>&1)
[[ "$shown" == *"[ok] Global hook: $codex_home/hooks.json"* ]]
[[ "$shown" == *"[ok] Global RTK.md: $codex_home/RTK.md"* ]]
python3 "$repo_root/tools/adoption/codex_hook_trust.py" --command "rtk hook codex" --rtk "$e/bin/rtk" --check'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L133
      # Planned. Source: https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L133 (the Codex hook rewrites the command: Codex reports the rewritten command it executed); a fresh codex exec session told to add no prefix runs git status through the hook, so the executed command carries rtk, and it must have completed with exit status 0: Codex's JSONL command item carries exit_code and status (https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L161-L166), and a rewritten command that failed (for example rtk not on the launcher's PATH) must not pass.
      check command-output smoke 'probe=$(mktemp -d)
trap '\''rm -rf "$probe"'\'' EXIT
cd "$probe"
git init -q .
timeout 300 codex exec --json --ephemeral --skip-git-repo-check -c model_reasoning_effort='\''"low"'\'' '\''Run exactly this one shell command and nothing else, adding no prefix of any kind: git status --short'\'' > "$probe/out.jsonl" < /dev/null
ran=$(jq -rs '\''map(select(.type=="item.completed" and .item.type=="command_execution" and ((.item.command // "") | contains("rtk git status")))) | (.[0].item // {}) | (.exit_code == 0 and .status == "completed")'\'' "$probe/out.jsonl")
[[ "$ran" == "true" ]]'
      ;;
    *) skipped command-output ;;
  esac
}
output-compression() {
  # Headroom 0.37.0 (headroom-ai[mcp], MCP server only) (owner row, amendment 4); https://github.com/headroomlabs-ai/headroom
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/headroomlabs-ai/headroom/v0.37.0/README.md#L437 (headroom --version), with the offline variables of the client templates
      check output-compression smoke 'HEADROOM_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DO_NOT_TRACK=1 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/headroom" --version | grep -F 0.37.0 >/dev/null'
      ;;
    *) skipped output-compression ;;
  esac
}
code-index() {
  # jcodemunch-mcp 1.108.319 (owner row, amendment 4); https://github.com/jgravelle/jcodemunch-mcp
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/8f7b34abe16fb459e0bf1c04747d584216dfe32e/README.md#L113 (jcodemunch-mcp --version); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/14048b840425c2569e0df60a6596e94e601da15b/recipes/README.md#L525 (its output at the pin)
      check code-index smoke '[[ "$("${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp" --version)" == "jcodemunch-mcp 1.108.319" ]]'
      ;;
    *) skipped code-index ;;
  esac
}
code-graph() {
  # codebase-memory-mcp 0.11.0 (owner row, amendment 4); https://github.com/DeusData/codebase-memory-mcp
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/v0.11.0/src/main.c#L1236 (--version)
      # The version line is exact as the archive's binary printed it on 2026-10-04.
      check code-graph smoke '[[ "$("${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/codebase-memory-mcp" --version)" == "codebase-memory-mcp 0.11.0" ]]'
      ;;
    *) skipped code-graph ;;
  esac
}
repo-packing() {
  # Repomix 1.18.1 (owner row, amendment 4); https://github.com/yamadashy/repomix
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L609 (-v, --version); https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L204 (--include); https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L628 (--style)
      # The two-file pack after the version line is this project's integration check, not upstream acceptance.
      check repo-packing smoke 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$("$e/bin/repomix" --version)" == 1.18.1 ]]
probe="$(mktemp -d)"
trap '\''rm -rf -- "$probe"'\'' EXIT
printf '\''%s\n'\'' '\''print(1)'\'' > "$probe/a.py"
printf '\''%s\n'\'' '\''print(2)'\'' > "$probe/b.py"
"$e/bin/repomix" "$probe" --include "a.py,b.py" --style xml --output "$probe/pack.xml"
grep -F a.py "$probe/pack.xml" >/dev/null
grep -F b.py "$probe/pack.xml" >/dev/null'
      ;;
    *) skipped repo-packing ;;
  esac
}
structured-data() {
  # TOON 4.1.1 (@toon-format/cli) (owner row, amendment 4); https://github.com/toon-format/toon
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/14048b840425c2569e0df60a6596e94e601da15b/adoption/pins-linux-x86_64.json#L294 (toon --version prints only the version); https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L63 (-o); https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L65 (--decode)
      # The round trip of a uniform two-record array after the version line is this project's integration check, not upstream acceptance.
      check structured-data smoke 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$("$e/bin/toon" --version)" == 4.1.1 ]]
probe="$(mktemp -d)"
trap '\''rm -rf -- "$probe"'\'' EXIT
printf '\''%s\n'\'' '\''[{"id":1,"name":"a"},{"id":2,"name":"b"}]'\'' > "$probe/records.json"
"$e/bin/toon" "$probe/records.json" -o "$probe/records.toon"
"$e/bin/toon" "$probe/records.toon" --decode --strict -o "$probe/recovered.json"
jq -e --slurpfile a "$probe/records.json" --slurpfile b "$probe/recovered.json" -n '\''$a == $b'\'' >/dev/null'
      ;;
    *) skipped structured-data ;;
  esac
}
doc-conversion() {
  # MarkItDown 0.1.8 (owner row, amendment 4); https://github.com/microsoft/markitdown
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/packages/markitdown/src/markitdown/__main__.py#L53 (--version); https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/packages/markitdown/src/markitdown/__main__.py#L66 (-x); https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/README.md#L81 (-o)
      # The conversion of a small HTML file after the version line is this project's integration check, not upstream acceptance.
      check doc-conversion smoke 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
"$e/bin/markitdown" --version | grep -F 0.1.8 >/dev/null
probe="$(mktemp -d)"
trap '\''rm -rf -- "$probe"'\'' EXIT
printf '\''%s\n'\'' '\''<html><body><h1>Probe heading</h1><p>probe text</p></body></html>'\'' > "$probe/probe.html"
"$e/bin/markitdown" "$probe/probe.html" -x html -o "$probe/probe.md"
grep -F "Probe heading" "$probe/probe.md" >/dev/null
! grep -F "<h1>" "$probe/probe.md"'
      ;;
    *) skipped doc-conversion ;;
  esac
}
api-docs() {
  # Context Hub 0.1.4 (context-hub, the chub CLI) (owner row, amendment 4); https://github.com/andrewyng/context-hub
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/andrewyng/context-hub/v0.1.4/cli/src/index.js#L53 (the version flag, -V, --cli-version)
      # Planned. Source: https://github.com/andrewyng/context-hub/blob/v0.1.4/cli/src/lib/telemetry.js#L5-L14 (the runtime functions); https://github.com/andrewyng/context-hub/blob/v0.1.4/cli/src/lib/config.js#L23-L40 (the persisted config). Keep the version probe, then unset both environment overrides in a scratch CHUB_DIR.
      # node is the one the plan installs through mise and this script puts on PATH (refresh_path); no plan command links it into ${ECO_ROOT}/bin.
      check api-docs smoke '[[ "$(CHUB_TELEMETRY=0 CHUB_FEEDBACK=0 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/chub" --cli-version)" == 0.1.4 ]]
e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
chub_source_config="${CHUB_DIR:-$HOME/.chub}/config.yaml"
chub_check_dir=$(mktemp -d "${TMPDIR:-/tmp}/new-wsl-chub-check.XXXXXX")
trap '"'"'rm -rf -- "$chub_check_dir"'"'"' EXIT
install -m 0600 -- "$chub_source_config" "$chub_check_dir/config.yaml"
env -u CHUB_TELEMETRY -u CHUB_FEEDBACK CHUB_DIR="$chub_check_dir" node --input-type=module -e '"'"'const { pathToFileURL } = await import("node:url"); const { isTelemetryEnabled, isFeedbackEnabled } = await import(pathToFileURL(process.argv[1]).href); const telemetry = isTelemetryEnabled(); const feedback = isFeedbackEnabled(); console.log("telemetry=" + telemetry + " feedback=" + feedback); if (telemetry !== false || feedback !== false) process.exit(1);'"'"' "$e/tools/context-hub-0.1.4/lib/node_modules/@aisuite/chub/src/lib/telemetry.js"'
      ;;
    *) skipped api-docs ;;
  esac
}
trace-viewer() {
  # otel-tui 0.7.5 (owner row, amendment 4); https://github.com/ymtdzzz/otel-tui
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/ymtdzzz/otel-tui/3b25779a083469b732e3c628b4a412ee05cf9948/README.md#L46 (-v, --version)
      # The version line is exact as the archive's binary printed it on 2026-10-04.
      check trace-viewer smoke '[[ "$("${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/otel-tui" --version)" == "otel-tui version 0.7.5" ]]'
      ;;
    *) skipped trace-viewer ;;
  esac
}
token-lane-carriers() {
  # token-lanes carriers: the SubagentStart block and a SessionStart main-session block (Claude Code hooks) (owner row, amendment 4); https://github.com/seathatflowsinourveins/native-agent-stack
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/docs/token-session-handbook.md#L197
      # Unavailable: The client configuration writes the carriers after this plan runs (tools/adoption/new_wsl_client_config.py, then its --check); this plan installs nothing for them and has nothing to check.
      skipped token-lane-carriers
      ;;
    *) skipped token-lane-carriers ;;
  esac
}
session-analytics() {
  # G5 plan repair 2026-10-04; upstream operations with local artifact assertions.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/cli.go#L870
      check session-analytics smoke 'a="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/agentsview"
v="$("$a" --version)"
[[ "$v" == "agentsview v0.43.0 "* ]]
cmp -s "$plan_dir/config/agentsview.sh" "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/agentsview-0.43.0/launcher"
[[ "$(readlink -f "$HOME/.local/bin/agentsview")" == "$(readlink -f "$a")" ]]'
      ;;
    service_health)
      # Kind: smoke; Source: https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/README.md#L40
      check session-analytics smoke 'a="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/agentsview"
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/session-analytics"
mkdir -p "$state_root"
run_dir="$(mktemp -d "$state_root/service.XXXXXX")"
"$a" daemon status > "$run_dir/daemon.txt"
grep -Eq '"'"'^agentsview running at '"'"' "$run_dir/daemon.txt"
if grep -Eqi '"'"'not responding|incompatible|multiple writable'"'"' "$run_dir/daemon.txt"; then exit 1; fi
"$a" sync > "$run_dir/sync.txt"
for agent in claude codex; do
  "$a" session list --agent "$agent" --include-one-shot --include-automated --limit 1 --json > "$run_dir/$agent-sessions.json"
  jq -e --arg agent "$agent" '"'"'(.sessions | length) > 0 and all(.sessions[]; .agent == $agent and .message_count > 0)'"'"' "$run_dir/$agent-sessions.json"
  "$a" usage daily --all --agent "$agent" --offline --no-sync --json > "$run_dir/$agent-usage.json"
  jq -e '"'"'(.daily | length) > 0 and ((.totals.inputTokens + .totals.outputTokens + .totals.cacheReadTokens + .totals.cacheCreationTokens) > 0)'"'"' "$run_dir/$agent-usage.json"
done'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/session_get.go#L21
      check session-analytics smoke 'a="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/agentsview"
: "${AGENTSVIEW_ACCEPT_CLAUDE_ID:?Supply the canonical ID of the fresh Claude session}"
: "${AGENTSVIEW_ACCEPT_CODEX_ID:?Supply the canonical ID of the fresh Codex session}"
: "${AGENTSVIEW_ACCEPT_STARTED_AT:?Supply the RFC3339 UTC time recorded before both fresh sessions}"
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/session-analytics"
mkdir -p "$state_root"
run_dir="$(mktemp -d "$state_root/fresh.XXXXXX")"
"$a" sync > "$run_dir/sync.txt"
"$a" session get "$AGENTSVIEW_ACCEPT_CLAUDE_ID" --json > "$run_dir/claude.json"
"$a" session get "$AGENTSVIEW_ACCEPT_CODEX_ID" --json > "$run_dir/codex.json"
python3 - "$run_dir" "$AGENTSVIEW_ACCEPT_STARTED_AT" "$AGENTSVIEW_ACCEPT_CLAUDE_ID" "$AGENTSVIEW_ACCEPT_CODEX_ID" <<'"'"'PY'"'"'
import datetime as dt
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
started = dt.datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
assert started.utcoffset() == dt.timedelta(0), "fresh-session start must be UTC"
for agent, session_id in zip(("claude", "codex"), sys.argv[3:]):
    session = json.loads((root / (agent + ".json")).read_text())
    assert session["id"] == session_id and session["agent"] == agent
    assert session["message_count"] > 0
    observed = dt.datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
    assert observed >= started, "historical session cannot satisfy fresh-session acceptance"
PY
if "$a" session get "ns2604-absent-$(basename "$run_dir")" --json > "$run_dir/absent.json" 2> "$run_dir/absent.stderr"; then
  printf "Absent-session control unexpectedly succeeded\n" >&2
  exit 1
else
  printf "%s\n" "$?" > "$run_dir/absent-exit.txt"
fi'
      ;;
    *) skipped session-analytics ;;
  esac
}
otel-collector-contrib() {
  # G4: native operations and explicitly labeled repository integration assertions.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector/v0.162.0/otelcol/command_validate.go#L15
      check otel-collector-contrib 'smoke' 'NS2604_OBSERVABILITY_DATA="${NS2604_OBSERVABILITY_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/observability}" otelcol-contrib validate --config="$config_root/otel.yaml"'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-contrib/v0.162.0/extension/healthcheckextension/README.md#L96
      check otel-collector-contrib 'health' 'curl -fsS http://127.0.0.1:21333/health/status'
      ;;
    *) skipped otel-collector-contrib ;;
  esac
}

prometheus() {
  # Prometheus; https://github.com/prometheus/prometheus
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/prometheus/prometheus/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/command-line/promtool.md#L91
      check prometheus smoke '"$tool_root/prometheus/prometheus-3.15.0.linux-amd64/promtool" check config "$config_root/prometheus.yaml"'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/management_api.md#L22
      check prometheus health 'curl -fsS http://127.0.0.1:21090/-/ready'
      ;;
    *) skipped prometheus ;;
  esac
}

alerting() {
  # G4: native operations and explicitly labeled repository integration assertions.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/configuration.md#L620
      check alerting 'smoke' '"$tool_root/alertmanager/alertmanager-0.34.1.linux-amd64/amtool" check-config "$config_root/alertmanager.yaml"
"$tool_root/prometheus/prometheus-3.15.0.linux-amd64/promtool" check rules "$config_root/prometheus-alerts.yaml"
cd "$config_root"
"$tool_root/prometheus/prometheus-3.15.0.linux-amd64/promtool" test rules prometheus-alerts.test.yaml'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/management_api.md#L22
      check alerting 'health' 'curl -fsS http://127.0.0.1:21093/-/ready
curl -fsS http://127.0.0.1:21090/api/v1/alertmanagers | jq -e '\''any(.data.activeAlertmanagers[]; .url == "http://127.0.0.1:21093/api/v2/alerts")'\'' >/dev/null
curl -fsS http://127.0.0.1:21090/api/v1/rules | jq -e '\''any(.data.groups[]; .name == "nativestack2604-services" and all(.rules[]; .health == "ok"))'\'' >/dev/null'
      ;;
    after_sign_in)
      local destination_rc=0
      python3 "$config_root/observability_config.py" alerting-ready --config-root "$config_root" --source-root "$plan_dir/config" >/dev/null || destination_rc=$?
      if [[ "$destination_rc" == 3 ]]; then skipped alerting; return; fi
      if [[ "$destination_rc" != 0 ]]; then failed=1; printf "alerting | %s | %s\n" "$stage" "$destination_rc"; return; fi
      # Kind: smoke; Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/cli/alert_add.go#L46
      check alerting 'smoke' 'python3 "$config_root/observability_config.py" alerting-ready --config-root "$config_root" --source-root "$plan_dir/config"
receipt="$config_root/alerting-delivery-receipt.json"
confirmation="$config_root/alerting-receiver-confirmation.json"
if [[ -f "$receipt" && -f "$confirmation" ]]; then
  if python3 - "$receipt" "$confirmation" "$config_root" <<'"'"'PY'"'"'
import hashlib, json, pathlib, sys, time
receipt, confirmation = [json.load(open(p)) for p in sys.argv[1:3]]
assert 0 <= time.time() - receipt["observed_unix"] < 1800
root = pathlib.Path(sys.argv[3])
current = hashlib.sha256(b"".join((root / name).read_bytes() for name in ("alertmanager.yaml", "prometheus.yaml", "prometheus-alerts.yaml"))).hexdigest()
assert receipt["config_sha256"] == current
assert receipt["acceptance_id"] == confirmation["acceptance_id"]
assert receipt["rule_fired"] and receipt["rule_resolved"] and receipt["notification_delta"] > 0
assert confirmation.get("firing_received") is True and confirmation.get("resolved_received") is True
assert confirmation.get("confirmed_by") == "user"
print("alerting | receiver_evidence=user_attestation; provenance_not_verified")
PY
  then
    exit 0
  else
    archive="$(mktemp -d "$config_root/alerting-stale.XXXXXXXX")"
    mv -- "$receipt" "$confirmation" "$archive/"
    printf "Stale or mismatched alert attestation retained; running a fresh delivery test.\n" >&2
  fi
fi
fixture="$config_root/acceptance-targets.json"
jq -e '"'"'. == []'"'"' "$fixture" >/dev/null
python3 - <<'"'"'PY'"'"'
import socket
with socket.socket() as s:
    s.settimeout(1)
    assert s.connect_ex(("127.0.0.1", 21997)) == 111, "fixture requires a confirmed closed loopback port"
PY
before="$(mktemp)"
after="$(mktemp)"
trap '"'"'printf "[]\n" > "$fixture"; rm -f -- "$before" "$after"'"'"' EXIT
integration=webhook
[[ "${NATIVE_STACK_ALERT_RECEIVER:-webhook}" != telegram ]] || integration=telegram
curl -fsS http://127.0.0.1:21093/metrics > "$before"
acceptance_id="$(python3 -c '"'"'import uuid; print(uuid.uuid4().hex)'"'"')"
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
expiry="$(date -u -d '"'"'+3 minutes'"'"' +%Y-%m-%dT%H:%M:%SZ)"
"$tool_root/alertmanager/alertmanager-0.34.1.linux-amd64/amtool" --alertmanager.url=http://127.0.0.1:21093 alert add --start="$started" --end="$expiry" alertname=NativeStack2604E2E severity=page acceptance_id="$acceptance_id"
printf '"'"'[{"targets":["127.0.0.1:21997"],"labels":{"acceptance_id":"%s"}}]\n'"'"' "$acceptance_id" > "$fixture"
fired=false
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:21090/api/v1/alerts | jq -e --arg id "$acceptance_id" '"'"'any(.data.alerts[]; .labels.alertname == "EcosystemAcceptanceTargetDown" and .labels.acceptance_id == $id and .state == "firing")'"'"' >/dev/null; then fired=true; break; fi
  sleep 2
done
$fired
printf '"'"'[]\n'"'"' > "$fixture"
resolved=false
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:21090/api/v1/alerts | jq -e --arg id "$acceptance_id" '"'"'all(.data.alerts[]; .labels.alertname != "EcosystemAcceptanceTargetDown" or .labels.acceptance_id != $id)'"'"' >/dev/null; then resolved=true; break; fi
  sleep 2
done
$resolved
"$tool_root/alertmanager/alertmanager-0.34.1.linux-amd64/amtool" --alertmanager.url=http://127.0.0.1:21093 alert add --start="$started" --end="$(date -u +%Y-%m-%dT%H:%M:%SZ)" alertname=NativeStack2604E2E severity=page acceptance_id="$acceptance_id"
sleep 15
curl -fsS http://127.0.0.1:21093/metrics > "$after"
python3 - "$before" "$after" "$integration" "$acceptance_id" "$receipt" <<'"'"'PY'"'"'
import hashlib, json, os, pathlib, re, sys, time
def counters(path):
    values = {}
    for line in open(path):
        match = re.match(r'"'"'(alertmanager_notifications(?:_failed)?_total)\{([^}]+)\} (\S+)'"'"', line)
        if match and '"'"'integration="'"'"' + sys.argv[3] + '"'"'"'"'"' in match[2]:
            values[match[1]] = values.get(match[1], 0) + float(match[3])
    return values
before, after = map(counters, sys.argv[1:3])
delta = after.get("alertmanager_notifications_total", 0) - before.get("alertmanager_notifications_total", 0)
assert delta > 0
assert after.get("alertmanager_notifications_failed_total", 0) == before.get("alertmanager_notifications_failed_total", 0)
root = pathlib.Path(sys.argv[5]).parent
config_sha256 = hashlib.sha256(b"".join((root / name).read_bytes() for name in ("alertmanager.yaml", "prometheus.yaml", "prometheus-alerts.yaml"))).hexdigest()
fd = os.open(sys.argv[5], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump({"acceptance_id": sys.argv[4], "observed_unix": time.time(), "rule_fired": True, "rule_resolved": True, "notification_delta": delta, "config_sha256": config_sha256}, f)
print("needs_user: confirm receipt of firing and resolved notifications for acceptance_id=" + sys.argv[4], file=sys.stderr)
PY
exit 3'
      ;;
    *) skipped alerting ;;
  esac
}

loki() {
  # Loki; https://github.com/grafana/loki
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/grafana/loki/09e6ce2ff1bdc19763a10265b870c86f51c98655/pkg/loki/config_wrapper.go#L54
      check loki smoke 'cd "$tool_root/loki"
loki -config.file="$config_root/loki.yaml" -verify-config=true'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/docs/sources/reference/loki-http-api.md#L1204
      check loki health 'curl -fsS http://127.0.0.1:21300/ready'
      ;;
    *) skipped loki ;;
  esac
}

grafana() {
  # G4: native operations and explicitly labeled repository integration assertions.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/administration/provisioning/index.md#L324
      check grafana 'smoke' 'grafana cli -v
python3 "$config_root/observability_config.py" grafana-check --config-root "$config_root"'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/developer-resources/api-reference/http-api/api-legacy/data_source.md#L657
      check grafana 'health' 'curl -fsS http://127.0.0.1:21301/api/health | jq -e '\''.database == "ok"'\'' >/dev/null
curl -fsS http://127.0.0.1:21301/api/dashboards/uid/token-layer | jq -e '\''.dashboard.uid == "token-layer" and (.meta.provisioned == true)'\'' >/dev/null
curl -fsS http://127.0.0.1:21301/api/datasources/proxy/uid/ns2604-alertmanager/api/v2/status | jq -e '\''.versionInfo.version == "0.34.1"'\'' >/dev/null
curl -fsS -H '\''Content-Type: application/json'\'' --data '\''{"from":"now-5m","to":"now","queries":[{"refId":"A","datasource":{"uid":"ns2604-prometheus"},"expr":"up{job=\"prometheus\"}","instant":true}]}'\'' http://127.0.0.1:21301/api/ds/query | jq -e '\''.results.A.status == 200 and (.results.A.frames | length > 0)'\'' >/dev/null'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/developer-resources/api-reference/http-api/api-legacy/data_source.md#L657
      check grafana 'smoke' 'export NS2604_OBSERVABILITY_DATA="${NS2604_OBSERVABILITY_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/observability}"
claude -p --effort max "Reply exactly NS2604_GRAFANA_NATIVE_ACCEPTANCE" >/dev/null
uv run --locked --script "$repo_root/examples/omniroute-codex-sdk/worker.py" --workspace "$repo_root" --sandbox read-only --prompt "Reply exactly NS2604_GRAFANA_SDK_ACCEPTANCE" | python3 -c '\''
import json, os, pathlib, sys, uuid
rows = [json.loads(line) for line in sys.stdin if line.strip()]
row = next(r for r in reversed(rows) if r.get("event") == "result")
assert row.get("status") == "completed" and row.get("cleanup_status") == "closed"
receipt = {k: row.get(k) for k in ("status", "usage_status", "usage_scope")}
receipt["configured_model"] = row["requested_model"]
receipt["observation_id"] = "grafana-acceptance-" + uuid.uuid4().hex
root = pathlib.Path(os.environ["NS2604_OBSERVABILITY_DATA"]) / "sdk-receipts"
root.mkdir(parents=True, exist_ok=True, mode=0o700)
fd = os.open(root / (receipt["observation_id"] + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f: json.dump(receipt, f, indent=2); f.write("\n")
'\''
request="$(mktemp)"
response="$(mktemp)"
trap '\''rm -f -- "$request" "$response"'\'' EXIT
python3 - "$config_root/grafana-dashboards/token-layer.json" > "$request" <<'\''PY'\''
import json, sys
queries = []
for panel in json.load(open(sys.argv[1]))["panels"]:
    for target in panel.get("targets", []):
        expr = target["expr"]
        if ("claude_code_" in expr and "[1h]" in expr) or "codex-sdk-receipt" in expr:
            q = dict(target, refId=str(panel["id"]), intervalMs=60000, maxDataPoints=360)
            q["expr"] = expr.replace("$__range", "6h")
            queries.append(q)
assert len(queries) == 9
print(json.dumps({"from": "now-6h", "to": "now", "queries": queries}))
PY
for attempt in $(seq 1 60); do
  curl -fsS -H '\''Content-Type: application/json'\'' --data-binary "@$request" http://127.0.0.1:21301/api/ds/query > "$response"
  if python3 - "$response" <<'\''PY'\''
import json, sys
results = json.load(open(sys.argv[1]))["results"]
def observed(result):
    return result.get("status") == 200 and not result.get("error") and any(
        value is not None for frame in result.get("frames", [])
        for field, values in zip(frame["schema"]["fields"], frame["data"]["values"])
        if field["type"] == "number" for value in values)
raise SystemExit(0 if len(results) == 9 and all(map(observed, results.values())) else 1)
PY
  then exit 0; fi
  sleep 3
done
printf '\''Grafana: hourly Claude or exercised SDK receipt panels still lack observations.\n'\'' >&2
exit 1'
      ;;
    *) skipped grafana ;;
  esac
}

local-model-server() {
  # Ollama; https://github.com/ollama/ollama
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L2181
      check local-model-server 'version only' 'OLLAMA_HOST=127.0.0.1:21434 ollama --version'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/cli.mdx#L97
      check local-model-server health 'OLLAMA_HOST=127.0.0.1:21434 ollama ls'
      ;;
    after_sign_in)
      # The embedding-model row, which installs only when named, creates the model this check calls. Until that model's
      # manifest is in the store its post_install check reads, this check prints skipped, which is not a pass (README.md).
      if [[ ! -e "${OLLAMA_MODELS:-$HOME/.ollama/models}/manifests/registry.ollama.ai/library/qwen3-embedding-8k/latest" ]]; then
        printf 'local-model-server: qwen3-embedding-8k is not in the model store; install the embedding-model row first (README.md, "The two local-model rows").\n' >&2
        skipped local-model-server
        return
      fi
      # One embedding call to the settled embedder, which the embedding-model row creates. /api/embed answers 404 for a
      # missing model (GetModel's not-found error, routes.go:981-984 and :3226-3227) and its handler pulls nothing:
      # https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L981-L984
      # https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L3226-L3227
      # Kind: smoke; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1659
      check local-model-server smoke 'curl -fsS http://127.0.0.1:21434/api/embed -d '"'"'{"model":"qwen3-embedding-8k","input":"Hello world"}'"'"' | jq -e '"'"'(.embeddings | length) == 1'"'"' >/dev/null'
      ;;
    *) skipped local-model-server ;;
  esac
}

local-generation-model() {
  # Swift-1.5-Qwen3.8-27B IQ3_S through Ollama (swift-iq3s-s2o-64k); https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF
  case "$stage" in
    post_install)
      # Files only: the placed Modelfiles are the repository's, and the created model names the pinned file as its layer,
      # whose digest is the file's own sha256. Store: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/envconfig/config.go#L112
      # Kind: smoke; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/create.go#L905
      check local-generation-model smoke 'printf '"'"'%s  %s\n'"'"' f6522bf4934aaa4f60231a042a8dfb781a7f5b3b1abc5053757f37169772ea9e "$tool_root/ollama-models/swift-iq3s-s2o.Modelfile" 6d15fee40e089b73961262647352c3443a03fa643122a92ca7a0b59376793d8e "$tool_root/ollama-models/swift-iq3s-s2o-64k.Modelfile" | sha256sum --check --status && grep -F sha256:1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786 "${OLLAMA_MODELS:-$HOME/.ollama/models}/manifests/registry.ollama.ai/library/swift-iq3s-s2o-64k/latest" >/dev/null'
      ;;
    service_health)
      # The model's own context and quantization, then one short generation with thinking off (not the measured effort).
      # Kind: smoke; Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L48
      check local-generation-model smoke 'out="$(OLLAMA_HOST=127.0.0.1:21434 ollama show swift-iq3s-s2o-64k)" && grep -E '"'"'^ +num_ctx +64000 *$'"'"' <<<"$out" >/dev/null && grep -E '"'"'^ +quantization +IQ3_S *$'"'"' <<<"$out" >/dev/null && curl -fsS http://127.0.0.1:21434/api/generate -d '"'"'{"model":"swift-iq3s-s2o-64k","prompt":"Reply with the word ready.","stream":false,"think":false,"options":{"num_predict":32}}'"'"' | jq -e '"'"'.done == true and (.response | length > 0)'"'"' >/dev/null'
      ;;
    *) skipped local-generation-model ;;
  esac
}

inspect-ai() {
  # G5 plan repair 2026-10-04; upstream operations with local artifact assertions.
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/0.3.273/src/inspect_ai/_cli/main.py#L23
      check inspect-ai 'version only' 'inspect --version'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/examples/theory_of_mind.py#L7
      check inspect-ai smoke 'export OMNIROUTE_API_KEY="${OMNIROUTE_API_KEY:-ns2604-keyless-loopback}"
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/inspect-ai"
mkdir -p "$state_root"
run_dir="$(mktemp -d "$state_root/eval.XXXXXX")"
example="$tool_root/inspect-ai-0.3.273/examples/theory_of_mind.py"
model="openai-api/omniroute/cx/gpt-6.1-sol"
base_url="http://127.0.0.1:21128/v1"
inspect eval "$example" --model "$model" --model-base-url "$base_url" --limit 1 --max-retries 0 --log-format eval --log-dir "$run_dir/positive"
shopt -s nullglob
logs=("$run_dir/positive/"*.eval)
[[ ${#logs[@]} == 1 ]]
inspect log dump "${logs[0]}" --header-only > "$run_dir/positive-header.json"
predicate='"'"'.status == "success" and .results.total_samples == 1 and .results.completed_samples == 1 and (.results.scores | length) > 0'"'"'
jq -e "$predicate" "$run_dir/positive-header.json"
control_rc=0
inspect eval "$example" --model "openai-api/omniroute/cx/__ns2604_absent_$(basename "$run_dir")__" --model-base-url "$base_url" --limit 1 --max-retries 0 --log-format eval --log-dir "$run_dir/negative" > "$run_dir/negative.stdout" 2> "$run_dir/negative.stderr" || control_rc=$?
printf "%s\n" "$control_rc" > "$run_dir/negative-cli-exit.txt"
logs=("$run_dir/negative/"*.eval)
[[ ${#logs[@]} == 1 ]]
inspect log dump "${logs[0]}" --header-only > "$run_dir/negative-header.json"
jq -e '"'"'.status == "error" and .error != null'"'"' "$run_dir/negative-header.json"
if jq -e "$predicate" "$run_dir/negative-header.json" > /dev/null; then
  printf "Absent-model control unexpectedly passed the positive log gate\n" >&2
  exit 1
else
  gate_rc=$?
  [[ "$gate_rc" == 1 ]]
  printf "%s\n" "$gate_rc" > "$run_dir/negative-gate-exit.txt"
fi'
      ;;
    *) skipped inspect-ai ;;
  esac
}

harbor-containerized-agent-e2e-runner() {
  # G5 plan repair 2026-10-04; upstream operations with local artifact assertions.
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/harbor-framework/harbor/v0.23.0/skills/create-adapter/SKILL.md#L30
      check harbor-containerized-agent-e2e-runner 'version only' 'export HARBOR_TELEMETRY=off
harbor --version'
      ;;
    service_health)
      # Kind: smoke; Source: https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/tests/integration/test_hello_user_e2e.py#L25
      check harbor-containerized-agent-e2e-runner smoke 'export HARBOR_TELEMETRY=off
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR:?Rootless Docker runtime directory is required}/docker.sock"
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/harbor"
mkdir -p "$state_root"
run_dir="$(mktemp -d "$state_root/hello-user.XXXXXX")"
for agent in oracle nop; do
  harbor run -p "$tool_root/harbor-v0.23.0/examples/tasks/hello-user" -a "$agent" -e docker --force-build -n 1 -o "$run_dir" --job-name "$agent"
done
python3 - "$run_dir" <<'"'"'PY'"'"'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
def require_reward(agent, expected):
    trials = list((root / agent).glob("*/result.json"))
    assert len(trials) == 1, "expected exactly one retained trial result"
    result = json.loads(trials[0].read_text())
    assert result["exception_info"] is None
    assert result["verifier_result"] is not None
    assert result["verifier_result"]["rewards"] is not None
    assert result["verifier_result"]["rewards"].get("reward") == expected
    reward = trials[0].parent / "verifier" / "reward.txt"
    assert float(reward.read_text().strip()) == expected
require_reward("oracle", 1.0)
require_reward("nop", 0.0)
try:
    require_reward("nop", 1.0)
except AssertionError:
    (root / "negative-gate.json").write_text(json.dumps({"positive_gate_rejects_nop": True}) + "\n")
else:
    raise AssertionError("nop must fail the same positive reward gate")
PY'
      ;;
    *) skipped harbor-containerized-agent-e2e-runner ;;
  esac
}

promptfoo() {
  # Promptfoo 0.123.1; https://github.com/promptfoo/promptfoo
  # UNRUN on every distribution: the 2026-10-04 verified-E2E plan fix.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/promptfoo/promptfoo/34f74d34e140b5e17d23770dfb2340057b1936b8/test/smoke/eval.test.ts#L65
      check promptfoo smoke 'pf="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/promptfoo"
export PROMPTFOO_CONFIG_DIR="$config_root/promptfoo-state" PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1
[[ "$("$pf" --version)" == "0.123.1" ]]
"$pf" mcp --help >/dev/null
receipt="$(mktemp -d "${TMPDIR:-/tmp}/new-wsl-promptfoo.XXXXXX")"
trap '"'"'rm -rf -- "$receipt"'"'"' EXIT
"$pf" eval --config "$config_root/promptfoo-0.123.1-basic.yaml" --no-cache --no-share --no-write --no-table --no-progress-bar --output "$receipt/pass.json"
jq -e '"'"'.results.stats | .successes == 1 and .failures == 0 and .errors == 0'"'"' "$receipt/pass.json" >/dev/null
rc=0
"$pf" eval --config "$config_root/promptfoo-0.123.1-failing.yaml" --no-cache --no-share --no-write --no-table --no-progress-bar --output "$receipt/fail.json" || rc=$?
[[ "$rc" == 100 ]]
jq -e '"'"'.results.stats | .successes == 0 and .failures == 1 and .errors == 0'"'"' "$receipt/fail.json" >/dev/null
claude mcp get promptfoo > "$receipt/claude-wiring.txt"
rg -Fq "Scope: User config" "$receipt/claude-wiring.txt"
rg -Fq "Type: stdio" "$receipt/claude-wiring.txt"
rg -Fq -- "$pf mcp --transport stdio" "$receipt/claude-wiring.txt"
codex mcp get promptfoo --json | jq -e --arg pf "$pf" '"'"'.transport.command == $pf and .transport.args == ["mcp", "--transport", "stdio"] and (.transport.env_vars | index("GATEWAY_API_KEY")) != null'"'"' >/dev/null'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/promptfoo/promptfoo/34f74d34e140b5e17d23770dfb2340057b1936b8/examples/openai-compatible-gateway/README.md#L22
      check promptfoo smoke 'pf="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/promptfoo"
gateway="${PROMPTFOO_GATEWAY_CONFIG:-$config_root/promptfoo-gateway.yaml}"
export GATEWAY_API_KEY="${GATEWAY_API_KEY:-keyless-loopback}"
if rg -q '"'"'your-gpt-model-id|your-claude-model-id|your-model-id|gateway.example.com'"'"' "$gateway"; then
  printf '"'"'needs_user: select the two exact existing GPT/Claude gateway model IDs and its apiBaseUrl in %s.\n'"'"' "$gateway" >&2
  exit 1
fi
export PROMPTFOO_CONFIG_DIR="$config_root/promptfoo-state" PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1
run="$config_root/promptfoo-acceptance/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p -- "$run"
chmod 0700 "$run"
"$pf" eval --config "$gateway" --no-cache --no-share --no-table --no-progress-bar --output "$run/gateway.json"
jq -e '"'"'.results.stats.successes == 2 and .results.stats.failures == 0 and .results.stats.errors == 0 and ([.results.results[].provider.id] | unique | length) == 2 and all(.results.results[]; .success == true and (.provider.id | startswith("openai:chat:")))'"'"' "$run/gateway.json" >/dev/null
# Supported Promptfoo SDK harness, with unchanged pinned fixtures in paired on/off workspaces.
python3 - "$config_root/promptfoo-skills.json" "$run/skills" "$tool_root/promptfoo-skill-fixtures" <<'"'"'PY'"'"'
import json, shutil, sys
from pathlib import Path
root, fixtures = Path(sys.argv[2]), Path(sys.argv[3])
root.mkdir(mode=0o700)
for name in ("home", "codex-home"):
    (root / name).mkdir(mode=0o700)
for client, skill_dir in (("claude", ".claude"), ("codex", ".agents")):
    for arm in ("on", "off"):
        work = root / f"{client}-{arm}"
        (work / "src").mkdir(parents=True)
        shutil.copyfile(fixtures / "auth.ts", work / "src/auth.ts")
        if arm == "on":
            skill = work / skill_dir / "skills/review-standards"
            skill.mkdir(parents=True)
            shutil.copyfile(fixtures / "SKILL.md", skill / "SKILL.md")
config = Path(sys.argv[1]).read_text().replace("@RUN_DIR@", str(root)).replace("@CODEX_BIN@", shutil.which("codex"))
positive = json.loads(config)
(root / "config.json").write_text(json.dumps(positive))
# The failure control applies the disabled-skill assertion to both enabled arms.
negative = json.loads(config)
negative["tests"] = [negative["tests"][0]]
negative["tests"][0]["assert"] = [{"type": "not-skill-used", "value": "review-standards"}]
(root / "negative.json").write_text(json.dumps(negative))
PY
"$pf" eval --config "$run/skills/config.json" --max-concurrency 1 --no-cache --no-share --no-write --no-table --no-progress-bar --output "$run/skills/pass.json"
jq -e '"'"'.results.stats | .successes == 4 and .failures == 0 and .errors == 0'"'"' "$run/skills/pass.json" >/dev/null
skill_rc=0
"$pf" eval --config "$run/skills/negative.json" --max-concurrency 1 --no-cache --no-share --no-write --no-table --no-progress-bar --output "$run/skills/fail.json" || skill_rc=$?
[[ "$skill_rc" == 100 ]]
jq -e '"'"'.results.stats | .successes == 0 and .failures == 2 and .errors == 0'"'"' "$run/skills/fail.json" >/dev/null
args="$(jq -cn --arg path "$gateway" '"'"'{configPath:$path,cache:false,write:false,share:false,maxConcurrency:1,resultLimit:20}'"'"')"
prompt="Call the promptfoo MCP run_evaluation tool once with these exact arguments: $args. Report only the evaluation ID and pass/fail counts. Read no authentication or credential files; use the inherited gateway environment."
claude -p --effort max --max-turns 4 --allowedTools mcp__promptfoo__run_evaluation --verbose --output-format stream-json "$prompt" > "$run/claude.jsonl" 2> "$run/claude.stderr"
codex exec --json --sandbox workspace-write -C "$run" -c '"'"'mcp_servers.promptfoo.tools.run_evaluation.approval_mode="approve"'"'"' -c '"'"'model_reasoning_effort="max"'"'"' --skip-git-repo-check "$prompt" </dev/null > "$run/codex.jsonl" 2> "$run/codex.stderr"
jq -s -e --arg client claude -f "$config_root/promptfoo-session.jq" "$run/claude.jsonl" >/dev/null
jq -s -e --arg client codex -f "$config_root/promptfoo-session.jq" "$run/codex.jsonl" >/dev/null'
      ;;
    *) skipped promptfoo ;;
  esac
}

zizmor() {
  # zizmor; https://github.com/zizmorcore/zizmor
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/zizmorcore/zizmor/v1.30.1/docs/quickstart.md#L3
      check zizmor smoke 'zizmor -h'
      ;;
    *) skipped zizmor ;;
  esac
}

syft() {
  # Syft; https://github.com/anchore/syft
  # UNRUN on every distribution: the 2026-10-04 verified-E2E plan fix.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/anchore/syft/cc326e45a6213360266dda4b30cc68095946d676/README.md#L48
      check syft smoke 'syft version -o json | jq -e '"'"'.version == "1.54.0" and .gitCommit == "cc326e45a6213360266dda4b30cc68095946d676"'"'"' >/dev/null
receipt="$(mktemp "${TMPDIR:-/tmp}/new-wsl-syft.XXXXXX.json")"
trap '"'"'rm -f -- "$receipt"'"'"' EXIT
syft alpine:latest -o "syft-json=$receipt"
jq -e '"'"'.source.type == "image" and (.artifacts | length) > 0 and any(.artifacts[]; .name == "alpine-baselayout")'"'"' "$receipt" >/dev/null'
      ;;
    *) skipped syft ;;
  esac
}

actionlint-kjanat() {
  # actionlint (kjanat); https://github.com/kjanat/actionlint
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/kjanat/actionlint/v1.17.0/docs/install.md#L127
      check actionlint-kjanat 'version only' 'actionlint -version'
      ;;
    *) skipped actionlint-kjanat ;;
  esac
}

dagu() {
  # Dagu; https://github.com/dagucloud/dagu
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/dagucloud/dagu/3bb5b23d2b0b3b924dd6eafc4c04107baa9cafc7/internal/cmd/version.go#L15
      check dagu 'version only' 'dagu version'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/dagucloud/dagu/v2.18.1/scripts/installer.sh#L1997
      check dagu health 'curl -fsS http://127.0.0.1:21080/api/v1/health'
      ;;
    *) skipped dagu ;;
  esac
}

docker-compose() {
  # Docker Compose; https://github.com/docker/compose
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/docker/docs/f0e4e4790191aaee83f9375dce56ada3971c6773/content/manuals/compose/install/linux.md#L51
      check docker-compose 'version only' 'docker compose version'
      ;;
    *) skipped docker-compose ;;
  esac
}

container-engine() {
  # Docker Engine / Moby; https://github.com/moby/moby
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/moby/moby/8af9fe3a36bab3e039862a2ab1cef1880c9b4d03/daemon/command/docker.go#L51
      check container-engine 'version only' 'dockerd --version'
      ;;
    service_health)
      # Kind: smoke; Source: https://raw.githubusercontent.com/docker/docs/0571430b6a9c6ff1742baede7c265c3c5e9e3322/content/manuals/engine/security/rootless/troubleshoot.md#L212
      check container-engine smoke 'docker run hello-world'
      ;;
    *) skipped container-engine ;;
  esac
}

betterleaks() {
  # betterleaks; https://github.com/betterleaks/betterleaks
  case "$stage" in
    post_install)
      # Kind: upstream tests + native smoke; Source: https://raw.githubusercontent.com/betterleaks/betterleaks/v1.9.0/Makefile#L15
      check betterleaks 'upstream tests + native smoke' 'bash "$config_root/betterleaks-accept.sh"'
      ;;
    *) skipped betterleaks ;;
  esac
}
git() {
  # git; https://github.com/git/git
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/git.adoc#L44
      check git 'version only' 'git --version'
      ;;
    *) skipped git ;;
  esac
}

gh-github-cli() {
  # gh (GitHub CLI); https://github.com/cli/cli
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/github-cli.toml#L4
      check gh-github-cli 'version only' 'gh --version'
      ;;
    *) skipped gh-github-cli ;;
  esac
}

worktrunk() {
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/max-sixty/worktrunk/v0.80.0/docs/src/content/docs/switch.md#L20
      check worktrunk smoke 'cd "$repo_root"
test "$(wt --version)" = '"'"'wt v0.80.0'"'"'
claude plugin list --json | python3 -c '"'"'import json,sys; assert any(p.get("id") == "worktrunk@worktrunk" and p.get("enabled") is True for p in json.load(sys.stdin))'"'"'
codex plugin list --json | python3 -c '"'"'import json,sys; assert any(p.get("pluginId") == "worktrunk@worktrunk" and p.get("installed") is True and p.get("enabled") is True for p in json.load(sys.stdin)["installed"])'"'"'
bash -ic '"'"'test "$(type -t wt)" = function'"'"'
wt list
fixture="$(mktemp -d)"
trap '"'"'cd "$repo_root"; rm -rf -- "$fixture"'"'"' EXIT
export GIT_CONFIG_GLOBAL="$fixture/gitconfig" GIT_CONFIG_NOSYSTEM=1
: > "$GIT_CONFIG_GLOBAL"
printf '"'"'%s\n'"'"' '"'"'worktree-path = "{{ repo_path }}/../{{ branch }}"'"'"' > "$fixture/worktrunk.toml"
git -c init.templateDir= init --quiet --initial-branch=main "$fixture/repo"
git -C "$fixture/repo" -c user.name='"'"'Worktrunk upstream-example acceptance'"'"' -c user.email=acceptance@example.invalid -c commit.gpgsign=false -c core.hooksPath=/dev/null commit --quiet --allow-empty -m '"'"'Disposable worktrunk example'"'"'
cd "$fixture/repo"
eval "$(wt config shell init bash)"
wt --config "$fixture/worktrunk.toml" switch --create native-stack-acceptance --yes
test "$PWD" = "$fixture/native-stack-acceptance"
test "$(git branch --show-current)" = native-stack-acceptance
wt --config "$fixture/worktrunk.toml" list --format=json
wt --config "$fixture/worktrunk.toml" switch main --yes
test "$PWD" = "$fixture/repo"
printf '"'"'%s\n'"'"' '"'"'dirty-removal control'"'"' > "$fixture/native-stack-acceptance/untracked-control"
rc=0
wt --config "$fixture/worktrunk.toml" remove native-stack-acceptance --foreground --yes || rc=$?
test "$rc" -ne 0
test -f "$fixture/native-stack-acceptance/untracked-control"
rm -- "$fixture/native-stack-acceptance/untracked-control"
wt --config "$fixture/worktrunk.toml" remove native-stack-acceptance --foreground --yes
test ! -e "$fixture/native-stack-acceptance"
if git show-ref --verify --quiet refs/heads/native-stack-acceptance; then exit 1; fi'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://developers.openai.com/codex/noninteractive/
      check worktrunk smoke 'cd "$repo_root"
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/worktrunk"
mkdir -p -- "$state_root"
run_dir="$(mktemp -d "$state_root/run.XXXXXX")"
printf -v task '"'"'Use your shell tool to run exactly: bash %q --only %q --stage post_install. This must execute the functional upstream examples and controls; a version report or a final answer without a tool call is insufficient. Report the command exit status. Modify only the disposable fixture this acceptance program owns.'"'"' "$plan_dir/accept.sh" worktrunk
claude -p --model sonnet --effort max --max-turns 6 --output-format stream-json --verbose --allowedTools '"'"'Bash(bash *),Bash(rtk bash *)'"'"' "$task" > "$run_dir/claude.jsonl" 2> "$run_dir/claude.stderr"
codex exec -m gpt-6.1-sol -c '"'"'model_reasoning_effort="max"'"'"' --sandbox workspace-write --ephemeral --json -o "$run_dir/codex-last.txt" "$task" < /dev/null > "$run_dir/codex.jsonl" 2> "$run_dir/codex.stderr"
python3 - "$run_dir" worktrunk <<'"'"'PY'"'"'
import json, pathlib, sys
directory, slot = pathlib.Path(sys.argv[1]), sys.argv[2]
def events(name):
    return [json.loads(line) for line in (directory / name).read_text().splitlines() if line.strip()]
c, g = events("claude.jsonl"), events("codex.jsonl")
uses = {block["id"] for e in c if e.get("type") == "assistant" for block in e.get("message", {}).get("content", []) if block.get("type") == "tool_use" and block.get("name") == "Bash" and "accept.sh" in block.get("input", {}).get("command", "") and slot in block.get("input", {}).get("command", "")}
assert uses, "Claude did not execute the acceptance command"
assert any(block.get("type") == "tool_result" and block.get("tool_use_id") in uses and not block.get("is_error", False) and f"{slot} | post_install | 0" in str(block.get("content", "")) for e in c if e.get("type") == "user" for block in e.get("message", {}).get("content", [])), "Claude'"'"'s functional tool result is missing or failed"
assert any(e.get("type") == "result" and e.get("subtype") == "success" and not e.get("is_error", False) for e in c), "Claude stream did not complete"
assert any(e.get("type") == "item.completed" and e.get("item", {}).get("type") == "command_execution" and "accept.sh" in e["item"].get("command", "") and slot in e["item"].get("command", "") and e["item"].get("exit_code") == 0 and f"{slot} | post_install | 0" in e["item"].get("aggregated_output", "") for e in g), "Codex'"'"'s functional command result is missing or failed"
assert any(e.get("type") == "turn.completed" for e in g), "Codex stream did not complete"
assert not any(e.get("type") in ("error", "turn.failed") for e in g), "Codex reported an error"
PY
printf '"'"'Complete native event streams retained in %s\n'"'"' "$run_dir" >&2'
      ;;
    *) skipped worktrunk ;;
  esac
}

difftastic() {
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/Wilfred/difftastic/0.71.0/tests/cli.rs#L85
      check difftastic smoke 'cd "$repo_root"
fixture_dir="$tool_root/difftastic-fixtures"
cd "$fixture_dir"
sha256sum -c <<'"'"'SHA256'"'"'
106256fcefb82debbc83be06ceeec073e35a4a1bfa4b22bd3530e2d97314d1db  simple_1.js
bd078aaecc828327c5b21ceb14a5f40e2e853f0468fb70b1b77d1aa08017ae31  simple_2.js
SHA256
summary="$(difft --color never --check-only simple_1.js simple_2.js)"
printf '"'"'%s\n'"'"' "$summary" | grep -F -- '"'"'Has syntactic changes'"'"'
printf '"'"'%s\n'"'"' "$summary" | grep -F -- '"'"'--- JavaScript'"'"'
rc=0
changed="$(difft --color never --exit-code simple_1.js simple_2.js)" || rc=$?
test "$rc" -eq 1
printf '"'"'%s\n'"'"' "$changed" | grep -F -- '"'"'--- JavaScript'"'"'
if printf '"'"'%s\n'"'"' "$changed" | grep -F -- '"'"'--- Text'"'"'; then exit 1; fi
difft --color never --exit-code simple_1.js simple_1.js'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://developers.openai.com/codex/noninteractive/
      check difftastic smoke 'cd "$repo_root"
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/difftastic"
mkdir -p -- "$state_root"
run_dir="$(mktemp -d "$state_root/run.XXXXXX")"
printf -v task '"'"'Use your shell tool to run exactly: bash %q --only %q --stage post_install. This must execute the functional upstream examples and controls; a version report or a final answer without a tool call is insufficient. Report the command exit status. Modify only the disposable fixture this acceptance program owns.'"'"' "$plan_dir/accept.sh" difftastic
claude -p --model sonnet --effort max --max-turns 6 --output-format stream-json --verbose --allowedTools '"'"'Bash(bash *),Bash(rtk bash *)'"'"' "$task" > "$run_dir/claude.jsonl" 2> "$run_dir/claude.stderr"
codex exec -m gpt-6.1-sol -c '"'"'model_reasoning_effort="max"'"'"' --sandbox workspace-write --ephemeral --json -o "$run_dir/codex-last.txt" "$task" < /dev/null > "$run_dir/codex.jsonl" 2> "$run_dir/codex.stderr"
python3 - "$run_dir" difftastic <<'"'"'PY'"'"'
import json, pathlib, sys
directory, slot = pathlib.Path(sys.argv[1]), sys.argv[2]
def events(name):
    return [json.loads(line) for line in (directory / name).read_text().splitlines() if line.strip()]
c, g = events("claude.jsonl"), events("codex.jsonl")
uses = {block["id"] for e in c if e.get("type") == "assistant" for block in e.get("message", {}).get("content", []) if block.get("type") == "tool_use" and block.get("name") == "Bash" and "accept.sh" in block.get("input", {}).get("command", "") and slot in block.get("input", {}).get("command", "")}
assert uses, "Claude did not execute the acceptance command"
assert any(block.get("type") == "tool_result" and block.get("tool_use_id") in uses and not block.get("is_error", False) and f"{slot} | post_install | 0" in str(block.get("content", "")) for e in c if e.get("type") == "user" for block in e.get("message", {}).get("content", [])), "Claude'"'"'s functional tool result is missing or failed"
assert any(e.get("type") == "result" and e.get("subtype") == "success" and not e.get("is_error", False) for e in c), "Claude stream did not complete"
assert any(e.get("type") == "item.completed" and e.get("item", {}).get("type") == "command_execution" and "accept.sh" in e["item"].get("command", "") and slot in e["item"].get("command", "") and e["item"].get("exit_code") == 0 and f"{slot} | post_install | 0" in e["item"].get("aggregated_output", "") for e in g), "Codex'"'"'s functional command result is missing or failed"
assert any(e.get("type") == "turn.completed" for e in g), "Codex stream did not complete"
assert not any(e.get("type") in ("error", "turn.failed") for e in g), "Codex reported an error"
PY
printf '"'"'Complete native event streams retained in %s\n'"'"' "$run_dir" >&2'
      ;;
    *) skipped difftastic ;;
  esac
}

cross-family-review() {
  case "$stage" in
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/exec/src/cli.rs#L273
      check cross-family-review smoke 'cd "$repo_root"
claude_head=8c32a84b246da66e43a6188c973741b09329e223
gpt_head=b9dbe3c5a09cdefca435cd78c7f3dad46ca883a4
claude_base="$(git rev-parse "$claude_head^")"
gpt_base="$(git rev-parse "$gpt_head^")"
git show -s --format=%B "$claude_head" | grep -iE '"'"'^Co-authored-by:.*Claude'"'"'
git show -s --format=%B "$gpt_head" | grep -iE '"'"'^Co-authored-by:.*Codex'"'"'
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/cross-family-review"
mkdir -p -- "$state_root"
run_dir="$(mktemp -d "$state_root/run.XXXXXX")"
git status --porcelain=v1 -z > "$run_dir/status-before"
printf '"'"'%s\n'"'"' "$claude_base" "$claude_head" "$gpt_base" "$gpt_head" > "$run_dir/commits.txt"
codex exec review --commit "$claude_head" -m gpt-6.1-sol -c '"'"'model_reasoning_effort="max"'"'"' -c '"'"'sandbox_mode="read-only"'"'"' --ephemeral --json -o "$run_dir/gpt-review.txt" < /dev/null > "$run_dir/gpt-review.jsonl" 2> "$run_dir/gpt-review.stderr"
git diff "$gpt_base" "$gpt_head" > "$run_dir/gpt-authored.diff"
test -s "$run_dir/gpt-authored.diff"
claude -p --model opus --effort max --permission-mode plan --max-turns 14 --output-format stream-json --verbose "Review this GPT-authored diff read-only; report file:line correctness findings. The immutable base is $gpt_base and head is $gpt_head. Read the original repository files for each finding. Do not edit or publish." < "$run_dir/gpt-authored.diff" > "$run_dir/claude-review.jsonl" 2> "$run_dir/claude-review.stderr"
git status --porcelain=v1 -z > "$run_dir/status-after"
cmp -- "$run_dir/status-before" "$run_dir/status-after"
test -s "$run_dir/gpt-review.txt"
python3 - "$run_dir" <<'"'"'PY'"'"'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
g = [json.loads(s) for s in (d / "gpt-review.jsonl").read_text().splitlines() if s.strip()]
c = [json.loads(s) for s in (d / "claude-review.jsonl").read_text().splitlines() if s.strip()]
assert any(e.get("type") == "turn.completed" for e in g), "GPT review stream did not complete"
assert not any(e.get("type") in ("error", "turn.failed") for e in g), "GPT review failed"
assert any(e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message" and e["item"].get("text") for e in g), "GPT returned no review"
assert any(e.get("type") == "result" and e.get("subtype") == "success" and not e.get("is_error", False) and e.get("result") for e in c), "Claude returned no completed review"
PY
printf '"'"'Both native reviews completed; retain %s for independent findings, dispositions, actual model/effort binding and later verification before closing the qualification gate.\n'"'"' "$run_dir" >&2'
      ;;
    *) skipped cross-family-review ;;
  esac
}

mise() {
  # mise; https://github.com/jdx/mise
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/jdx/mise/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/src/cli/doctor/mod.rs#L532
      check mise smoke 'cd "$tool_root"
PATH="${MISE_SHIMS_DIR:-${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims}:$PATH" mise doctor'
      ;;
    *) skipped mise ;;
  esac
}

restic() {
  # Restic; https://github.com/restic/restic
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/restic/restic/v0.19.1/doc/man/restic-version.1#L9
      check restic 'version only' 'restic version'
      ;;
    *) skipped restic ;;
  esac
}

base-distribution() {
  # Environment prerequisite: Canonical WSL image, no extra installation.
  case "$stage" in
    post_install)
      # Kind: upstream tests + integration exception; Source: https://raw.githubusercontent.com/ubuntu/wsl-setup/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/test/basic-assertions.sh#L2
      check base-distribution 'upstream tests + integration exception' 'bash "$plan_dir/config/base-distribution-accept.sh"'
      ;;
    *) skipped base-distribution ;;
  esac
}

gpt-gateway() {
  # OmniRoute; https://github.com/diegosouzapw/OmniRoute
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/diegosouzapw/OmniRoute/23a11484862b3bb589a55e85b00e4ac53ffeb234/bin/cli/commands/doctor.mjs#L630
      check gpt-gateway smoke 'python3 "$plan_dir/config/omniroute-canary-check.py" "$HOME/.local/bin/omniroute" "$plan_dir/config/omniroute-canary-evidence.json" "$tool_root"
test -x "$HOME/.local/bin/omniroute"
DATA_DIR="$HOME/.local/share/omniroute" PORT=21128 OMNIROUTE_SERVER_HOST=127.0.0.1 "$HOME/.local/bin/omniroute" --output json doctor --no-liveness'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/diegosouzapw/OmniRoute/23a11484862b3bb589a55e85b00e4ac53ffeb234/src/app/healthz/route.ts#L17
      check gpt-gateway health 'python3 "$plan_dir/config/omniroute-canary-check.py" "$HOME/.local/bin/omniroute" "$plan_dir/config/omniroute-canary-evidence.json" "$tool_root"
curl -fsS http://127.0.0.1:21128/readyz
DATA_DIR="$HOME/.local/share/omniroute" PORT=21128 OMNIROUTE_SERVER_HOST=127.0.0.1 "$HOME/.local/bin/omniroute" --output json doctor --liveness-url http://127.0.0.1:21128/api/monitoring/health'
      ;;
    after_sign_in)
      # Kind: native client integration; Source: https://developers.openai.com/codex/noninteractive
      check gpt-gateway 'native client integration' 'python3 "$plan_dir/config/omniroute-canary-check.py" "$HOME/.local/bin/omniroute" "$plan_dir/config/omniroute-canary-evidence.json" "$tool_root"
bash "$config_root/gpt-gateway-client-accept.sh"'
      ;;
    *) skipped gpt-gateway ;;
  esac
}

mcp-inspector() {
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://github.com/modelcontextprotocol/inspector/blob/2.9.0/docs/publishing.md#L16
      check mcp-inspector smoke 'state="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/mcp-inspector"
install -d -m 0700 -- "$state"
scratch="$(mktemp -d "$state/pack.XXXXXXXX")"
trap '"'"'rm -rf -- "$scratch/source"'"'"' EXIT
git clone --depth 1 --branch 2.9.0 https://github.com/modelcontextprotocol/inspector.git "$scratch/source"
cd "$scratch/source"
npm install
MCP_AUTO_OPEN_ENABLED=false MCP_INSPECTOR_SECRET_STORE=memory npm run pack:verify
MCP_AUTO_OPEN_ENABLED=false MCP_INSPECTOR_SECRET_STORE=memory npm run smoke:web:tabs
cd "$scratch"
# QMD is our separate real-server integration check; pack:verify above is upstream acceptance.
MCP_INSPECTOR_SECRET_STORE=memory npx -y @modelcontextprotocol/inspector@2.9.0 --cli qmd --index native-agent-stack-catalog mcp -- --method tools/list >"$scratch/qmd-tools.json"
python3 - "$scratch/qmd-tools.json" <<'"'"'PY'"'"'
import json, sys
data = json.load(open(sys.argv[1]))
assert data.get("tools") or data.get("result", {}).get("tools")
PY'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://github.com/modelcontextprotocol/inspector/blob/2.9.0/clients/launcher/README.md#L15
      check mcp-inspector smoke 'state="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/mcp-inspector"
install -d -m 0700 -- "$state"
session="$(mktemp -d "$state/clients.XXXXXXXX")"
for client in claude codex; do
  prompt="Use your native shell to assert the inherited MCP_AUTO_OPEN_ENABLED is exactly false. Run MCP_INSPECTOR_SECRET_STORE=memory npx -y @modelcontextprotocol/inspector@2.9.0 --cli qmd --index native-agent-stack-catalog mcp -- --method tools/list and save its actual JSON as $session/$client-tools.json. Then boot the published Inspector Web mode with the same QMD positional command: MCP_INSPECTOR_SECRET_STORE=memory HOST=127.0.0.1 CLIENT_PORT=26399 setsid npx -y @modelcontextprotocol/inspector@2.9.0 --web -- qmd --index native-agent-stack-catalog mcp. Poll http://127.0.0.1:26399/ with curl and save the served page to $session/$client-page.html. Stop its process group in a shell trap and wait for it before finishing. Keep its authentication enabled. Write $session/$client-env.txt with the inherited MCP_AUTO_OPEN_ENABLED after the assertion succeeds."
  if [[ "$client" == claude ]]; then
    (cd "$session" && timeout 600 claude -p --model opus --effort max --max-turns 12 --permission-mode bypassPermissions --output-format stream-json --verbose "$prompt") >"$session/claude.jsonl"
  else
    OMNIROUTE_API_KEY=local-loopback timeout 600 codex exec -p omniroute -m gpt-6.1-sol -c model_reasoning_effort=max \
      --sandbox workspace-write -c sandbox_workspace_write.network_access=true \
      -c "shell_environment_policy.set.npm_config_cache=\"$session/npm-cache\"" \
      -c "sandbox_workspace_write.writable_roots=[\"$state\"]" \
      --skip-git-repo-check -C "$session" --json "$prompt" </dev/null >"$session/codex.jsonl"
  fi
  python3 - "$session" "$client" <<'"'"'PY'"'"'
import json, sys
from pathlib import Path

def native_commands(path, client):
    # Original native JSONL is retained. Match completed tool calls, not a model'"'"'s verdict.
    events = [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    if client == "codex":
        return [e["item"]["command"] for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "command_execution"
                and e["item"].get("exit_code") == 0 and e["item"].get("status") == "completed"]
    calls, done = {}, set()
    for event in events:
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                calls[block["id"]] = block.get("input", {}).get("command", "")
            elif block.get("type") == "tool_result" and not block.get("is_error", False):
                done.add(block.get("tool_use_id"))
    return [command for key, command in calls.items() if key in done]

root, client = Path(sys.argv[1]), sys.argv[2]
calls = native_commands(root / f"{client}.jsonl", client)
assert any("@modelcontextprotocol/inspector@2.9.0" in cmd and "tools/list" in cmd for cmd in calls), "No completed native Inspector CLI call"
assert any("@modelcontextprotocol/inspector@2.9.0" in cmd and "--web" in cmd and "MCP_AUTO_OPEN_ENABLED" in "\n".join(calls) for cmd in calls), "No completed native Web launch/environment probe"
data = json.loads((root / f"{client}-tools.json").read_text())
assert data.get("tools") or data.get("result", {}).get("tools")
assert "<html" in (root / f"{client}-page.html").read_text().lower()
assert (root / f"{client}-env.txt").read_text().strip() == "false"
PY
  if ss -H -ltn | awk '"'"'{print $4}'"'"' | grep -Eq '"'"':26399$'"'"'; then
    printf '"'"'Inspector Web process was not stopped by the native session\n'"'"' >&2; exit 1
  fi
done'
      ;;
    *) skipped mcp-inspector ;;
  esac
}


agent-runtime-worker() {
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/.github/workflows/tests.yml#L94
      check agent-runtime-worker smoke 'uv pip check --python "$tool_root/agent-runtime-worker/bin/python"
"$tool_root/agent-runtime-worker/bin/python" - <<'"'"'PY'"'"'
from importlib.metadata import version
assert version("openhands-sdk") == version("openhands-tools") == "1.50.1"
PY
cd "$tool_root/openhands-source"
uv sync --frozen --group dev
CI=true uv run --frozen python -m pytest -q tests/sdk tests/cross
systemctl --user cat openhands-job@.service >/dev/null
test -s "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/native-stack-worker/SKILL.md"
test -s "$HOME/.agents/skills/native-stack-worker/SKILL.md"'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/examples/01_standalone_sdk/01_hello_world.py#L9
      check agent-runtime-worker smoke 'cfg="$config_root/openhands"
worker_state="$HOME/.local/state/native-agent-stack/runtime-workers/openhands"
install -d -m 0700 -- "$worker_state"
run="$(mktemp -d "$worker_state/accept.XXXXXXXX")"
stamp="${run##*/}"
stamp="${stamp//./-}"
# Unchanged upstream example under the same per-job srt boundary.
mkdir -m 0700 -- "$run/home" "$run/openhands-home"
python3 - "$cfg/srt-template.json" "$run" <<'"'"'PY'"'"'
import json, sys
from pathlib import Path
root = Path(sys.argv[2])
policy = json.loads(Path(sys.argv[1]).read_text())
policy["filesystem"]["denyRead"] = [str(Path(p).expanduser()) for p in policy["filesystem"]["denyRead"]]
policy["filesystem"]["allowWrite"] = [str(root)]
policy["network"]["allowedDomains"] = ["127.0.0.1:21128"]
(root / "hello-srt.json").write_text(json.dumps(policy))
PY
(cd "$run" && HOME="$run/home" OH_PERSISTENCE_DIR="$run/openhands-home" NO_PROXY= no_proxy= LLM_BASE_URL=http://127.0.0.1:21128/v1 LLM_MODEL=openai/cx/gpt-6.1-sol-max LLM_API_KEY=local-loopback \
  srt --settings "$run/hello-srt.json" -- env NO_PROXY= no_proxy= "$tool_root/agent-runtime-worker/bin/python" "$tool_root/openhands-source/examples/01_standalone_sdk/01_hello_world.py")
test -s "$run/FACTS.txt"
# The closed-port negative preserves its journal and proves no model request occurred.
negative="negative-$stamp"
python3 "$cfg/worker.py" --prepare "$negative" --negative
if systemctl --user start --wait "openhands-job@$negative.service"; then
  printf '"'"'Closed-port control unexpectedly succeeded\n'"'"' >&2; exit 1
fi
python3 - "$worker_state/$negative/run-report.json" <<'"'"'PY'"'"'
import json, sys
report = json.load(open(sys.argv[1]))
assert report["requests_to_model"] == 0 and report["reason"] == "preflight_failed"
PY
systemctl --user reset-failed "openhands-job@$negative.service"
# Fresh native sessions discover the installed skill and dispatch separate positive jobs.
for client in claude codex; do
  id="$client-$stamp"
  prompt="Use the native-stack-worker skill to prepare job $id with its default Python sum(range(1,11)) task and default owned workspace. Dispatch it with systemctl --user start --wait openhands-job@$id.service, then inspect its run-report.json and result.txt. Complete the real job; a preflight is insufficient."
  if [[ "$client" == claude ]]; then
    (cd "$run" && timeout 1800 claude -p --model opus --effort max --max-turns 12 --permission-mode bypassPermissions --output-format stream-json --verbose "$prompt") >"$run/claude.jsonl"
  else
    OMNIROUTE_API_KEY=local-loopback timeout 1800 codex exec -p omniroute -m gpt-6.1-sol -c model_reasoning_effort=max \
      --sandbox workspace-write -c sandbox_workspace_write.network_access=true \
      -c "sandbox_workspace_write.writable_roots=[\"$cfg\",\"$worker_state\"]" \
      --skip-git-repo-check -C "$run" --json "$prompt" </dev/null >"$run/codex.jsonl"
  fi
  python3 - "$worker_state/$id" "$run/$client.jsonl" "$client" <<'"'"'PY'"'"'
import json, sys
from pathlib import Path

def native_commands(path, client):
    # Original native JSONL is retained. Match completed tool calls, not a model'"'"'s verdict.
    events = [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    if client == "codex":
        return [e["item"]["command"] for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "command_execution"
                and e["item"].get("exit_code") == 0 and e["item"].get("status") == "completed"]
    calls, done = {}, set()
    for event in events:
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                calls[block["id"]] = block.get("input", {}).get("command", "")
            elif block.get("type") == "tool_result" and not block.get("is_error", False):
                done.add(block.get("tool_use_id"))
    return [command for key, command in calls.items() if key in done]

root = Path(sys.argv[1])
calls = native_commands(Path(sys.argv[2]), sys.argv[3])
assert any("systemctl" in cmd and "openhands-job@" in cmd and "start" in cmd for cmd in calls), "No completed native worker dispatch"
report = json.loads((root / "run-report.json").read_text())
assert report["success"] and report["requests_to_model"] > 0
assert (root / "workspace/result.txt").read_text().strip() == "55"
PY
  [[ "$(systemctl --user show -p Result --value "openhands-job@$id.service")" == success ]]
done'
      ;;
    *) skipped agent-runtime-worker ;;
  esac
}

research-harnesses() {
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/tests/test_client.py
      check research-harnesses smoke 'cd "$tool_root/gpt-researcher"
.venv/bin/python -c '"'"'import tomllib; from gpt_researcher import GPTResearcher; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'"'"'
bash "$repo_root/tools/research/gpt_researcher.sh" --preflight-only
"$tool_root/deer-flow/backend/.venv/bin/python" -c '"'"'from deerflow.client import DeerFlowClient'"'"'
cd "$tool_root/deer-flow/backend"
uv run --frozen --group dev python -m pytest -q tests/test_client.py
DEER_FLOW_CONFIG_PATH="$config_root/deer-flow-config.yaml" .venv/bin/python - <<'"'"'PY'"'"'
import os
from deerflow.client import DeerFlowClient
client = DeerFlowClient(config_path=os.environ["DEER_FLOW_CONFIG_PATH"], model_name="gpt-runtime")
assert any(m["name"] == "gpt-runtime" for m in client.list_models()["models"])
PY
test -s "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/native-stack-research/SKILL.md"
test -s "$HOME/.agents/skills/native-stack-research/SKILL.md"'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1658
      check research-harnesses smoke 'out="$(bash "$repo_root/tools/research/gpt_researcher.sh" "Ubuntu 26.04 WSL news this month")"
grep -q "^Report written to '"'"'outputs/" <<<"$out"
run="$(sed -n '"'"'s/^run directory: //p'"'"' <<<"$out")"
refs="$(awk '"'"'/^#+ *References/{f=1} f'"'"' "$run"/outputs/*.md | grep -oE '"'"'https?://[^) >]+'"'"' | sort -u | wc -l)"
[[ "$refs" -ge 5 ]]
bash "$config_root/deer-flow-research.sh" "Research Ubuntu 26.04 WSL news this month; return a short answer with primary source URLs."
# Both gatherers are exercised by each fresh native session, with actual outputs observed outside it.
state="${XDG_STATE_HOME:-$HOME/.local/state}"
install -d -m 0700 -- "$state/native-agent-stack/research/client-checks"
session="$(mktemp -d "$state/native-agent-stack/research/client-checks/run.XXXXXXXX")"
for client in claude codex; do
  marker="$session/$client.started"
  touch "$marker"
  prompt="Use native-stack-research to complete a short public research query about Ubuntu 26.04 WSL this month through BOTH installed gatherers: bash $config_root/gpt-researcher.sh and bash $config_root/deer-flow-research.sh. Include source URLs. Complete both real calls; preflight/import checks do not qualify. Inspect the two resulting reports and print their run directories."
  if [[ "$client" == claude ]]; then
    (cd "$session" && timeout 3300 claude -p --model opus --effort max --max-turns 16 --permission-mode bypassPermissions --output-format stream-json --verbose "$prompt") >"$session/claude.jsonl"
  else
    OMNIROUTE_API_KEY=local-loopback timeout 3300 codex exec -p omniroute -m gpt-6.1-sol -c model_reasoning_effort=max \
      --sandbox workspace-write -c sandbox_workspace_write.network_access=true \
      -c "sandbox_workspace_write.writable_roots=[\"$state/new-wsl-native-stack/research\",\"$state/native-agent-stack/research\"]" \
      --skip-git-repo-check -C "$session" --json "$prompt" </dev/null >"$session/codex.jsonl"
  fi
  python3 - "$state" "$marker" "$session/$client.jsonl" "$client" <<'"'"'PY'"'"'
import json, re, sys
from pathlib import Path

def native_commands(path, client):
    # Original native JSONL is retained. Match completed tool calls, not a model'"'"'s verdict.
    events = [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    if client == "codex":
        return [e["item"]["command"] for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "command_execution"
                and e["item"].get("exit_code") == 0 and e["item"].get("status") == "completed"]
    calls, done = {}, set()
    for event in events:
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                calls[block["id"]] = block.get("input", {}).get("command", "")
            elif block.get("type") == "tool_result" and not block.get("is_error", False):
                done.add(block.get("tool_use_id"))
    return [command for key, command in calls.items() if key in done]

calls = native_commands(Path(sys.argv[3]), sys.argv[4])
assert any("gpt-researcher.sh" in cmd and "--preflight-only" not in cmd for cmd in calls), "No completed native GPT Researcher call"
assert any("deer-flow-research.sh" in cmd for cmd in calls), "No completed native DeerFlow call"
state, marker = map(Path, sys.argv[1:3])
since = marker.stat().st_mtime_ns
gpt = [p for p in (state / "new-wsl-native-stack/research/gptr").glob("*/outputs/*.md") if p.stat().st_mtime_ns > since]
deer = [p for p in (state / "native-agent-stack/research/deer-flow").glob("*/answer.md") if p.stat().st_mtime_ns > since]
def has_references(path):
    parts = re.split(r"(?m)^#+ *References", path.read_text())
    return len(parts) > 1 and len(set(re.findall(r"https?://[^\s)>]+", parts[-1]))) >= 5
assert any(has_references(p) for p in gpt), "No completed new GPT Researcher report"
assert any(p.read_text().strip() and re.search(r"https?://", p.read_text()) for p in deer), "No completed new cited DeerFlow answer"
PY
done
# Embedded acceptance starts no DeerFlow HTTP stack.
if ss -H -ltn | awk '"'"'{print $4}'"'"' | grep -Eq '"'"':(2026|8001|3000)$'"'"'; then
  printf '"'"'An embedded-only DeerFlow acceptance port is listening; inspect its owner\n'"'"' >&2; exit 1
fi'
      ;;
    *) skipped research-harnesses ;;
  esac
}

credential-guard() {
  # Command and secret-path guard (K4); https://github.com/seathatflowsinourveins/native-agent-stack
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/14048b840425c2569e0df60a6596e94e601da15b/adoption/bootstrap.md#L412
      # Unavailable: Repository adoption practice; no standalone host self-test or version command was found in the cited recipe.
      skipped credential-guard
      ;;
    *) skipped credential-guard ;;
  esac
}

convergence-validators() {
  # Convergence practice and its validators; https://github.com/seathatflowsinourveins/native-agent-stack
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/8b51946ee16e542e544936e19bb793114fea948e/adoption/README.md#L68
      check convergence-validators smoke 'cd "$repo_root"
python3 scripts/validate.py'
      ;;
    *) skipped convergence-validators ;;
  esac
}

if [[ -z "$only" || "$only" == claude-code ]]; then claude-code; fi
if [[ -z "$only" || "$only" == codex ]]; then codex; fi
if [[ -z "$only" || "$only" == claude-agent-sdk ]]; then claude-agent-sdk; fi
if [[ -z "$only" || "$only" == codex-sdk-and-codex-exec-app-server ]]; then codex-sdk-and-codex-exec-app-server; fi
if [[ -z "$only" || "$only" == trail-of-bits-security-skills-trailofbits-skills ]]; then trail-of-bits-security-skills-trailofbits-skills; fi
if [[ -z "$only" || "$only" == engineering-process-skills ]]; then engineering-process-skills; fi
if [[ -z "$only" || "$only" == skill-discovery ]]; then skill-discovery; fi
if [[ -z "$only" || "$only" == skill-authoring ]]; then skill-authoring; fi
if [[ -z "$only" || "$only" == mcporter ]]; then mcporter; fi
if [[ -z "$only" || "$only" == sandbox-runtime-srt ]]; then sandbox-runtime-srt; fi
if [[ -z "$only" || "$only" == serena ]]; then serena; fi
if [[ -z "$only" || "$only" == structural-search ]]; then structural-search; fi
# Planned. The two model rows install only with --only (their models are created through the running model server).
if [[ "$only" == embedding-model ]]; then embedding-model; elif [[ -z "$only" ]]; then skipped embedding-model; fi
if [[ -z "$only" || "$only" == tobi-qmd ]]; then tobi-qmd; fi
if [[ -z "$only" || "$only" == mineru ]]; then mineru; fi
if [[ -z "$only" || "$only" == memory-owner ]]; then memory-owner; fi
if [[ -z "$only" || "$only" == code-search ]]; then code-search; fi
if [[ -z "$only" || "$only" == context-supply ]]; then context-supply; fi
if [[ -z "$only" || "$only" == statusline ]]; then statusline; fi
if [[ -z "$only" || "$only" == ccusage ]]; then ccusage; fi
if [[ -z "$only" || "$only" == command-output ]]; then command-output; fi
if [[ -z "$only" || "$only" == output-compression ]]; then output-compression; fi
if [[ -z "$only" || "$only" == code-index ]]; then code-index; fi
if [[ -z "$only" || "$only" == code-graph ]]; then code-graph; fi
if [[ -z "$only" || "$only" == repo-packing ]]; then repo-packing; fi
if [[ -z "$only" || "$only" == structured-data ]]; then structured-data; fi
if [[ -z "$only" || "$only" == doc-conversion ]]; then doc-conversion; fi
if [[ -z "$only" || "$only" == api-docs ]]; then api-docs; fi
if [[ -z "$only" || "$only" == trace-viewer ]]; then trace-viewer; fi
if [[ -z "$only" || "$only" == token-lane-carriers ]]; then token-lane-carriers; fi
if [[ -z "$only" || "$only" == session-analytics ]]; then session-analytics; fi
if [[ "$only" == playwright-cli ]]; then playwright-cli; elif [[ -z "$only" ]]; then skipped playwright-cli; fi
if [[ -z "$only" || "$only" == otel-collector-contrib ]]; then otel-collector-contrib; fi
if [[ -z "$only" || "$only" == prometheus ]]; then prometheus; fi
if [[ "$only" == loki ]]; then loki; elif [[ -z "$only" ]]; then skipped loki; fi
if [[ "$only" == grafana ]]; then grafana; elif [[ -z "$only" ]]; then skipped grafana; fi
if [[ -z "$only" || "$only" == local-model-server ]]; then local-model-server; fi
if [[ "$only" == local-generation-model ]]; then local-generation-model; elif [[ -z "$only" ]]; then skipped local-generation-model; fi
if [[ -z "$only" || "$only" == alerting ]]; then alerting; fi
if [[ -z "$only" || "$only" == inspect-ai ]]; then inspect-ai; fi
if [[ -z "$only" || "$only" == harbor-containerized-agent-e2e-runner ]]; then harbor-containerized-agent-e2e-runner; fi
if [[ -z "$only" || "$only" == promptfoo ]]; then promptfoo; fi
if [[ -z "$only" || "$only" == zizmor ]]; then zizmor; fi
if [[ -z "$only" || "$only" == syft ]]; then syft; fi
if [[ -z "$only" || "$only" == actionlint-kjanat ]]; then actionlint-kjanat; fi
if [[ -z "$only" || "$only" == dagu ]]; then dagu; fi
if [[ -z "$only" || "$only" == docker-compose ]]; then docker-compose; fi
if [[ -z "$only" || "$only" == container-engine ]]; then container-engine; fi
if [[ -z "$only" || "$only" == betterleaks ]]; then betterleaks; fi
if [[ -z "$only" || "$only" == git ]]; then git; fi
if [[ -z "$only" || "$only" == gh-github-cli ]]; then gh-github-cli; fi
if [[ -z "$only" || "$only" == worktrunk ]]; then worktrunk; fi
if [[ -z "$only" || "$only" == difftastic ]]; then difftastic; fi
if [[ -z "$only" || "$only" == cross-family-review ]]; then cross-family-review; fi
if [[ -z "$only" || "$only" == mise ]]; then mise; fi
if [[ -z "$only" || "$only" == restic ]]; then restic; fi
if [[ -z "$only" || "$only" == base-distribution ]]; then base-distribution; fi
if [[ -z "$only" || "$only" == gpt-gateway ]]; then gpt-gateway; fi
if [[ "$only" == mcp-inspector ]]; then mcp-inspector; elif [[ -z "$only" ]]; then skipped mcp-inspector; fi
if [[ -z "$only" || "$only" == agent-runtime-worker ]]; then agent-runtime-worker; fi
if [[ -z "$only" || "$only" == research-harnesses ]]; then research-harnesses; fi
if [[ -z "$only" || "$only" == credential-guard ]]; then credential-guard; fi
if [[ -z "$only" || "$only" == convergence-validators ]]; then convergence-validators; fi
# Planned. Rows the plan does not install (merged manifest): nothing to check, so each prints its skip.
for slot in 'research-skill' 'agent-messaging' 'isolation-container-boundary' 'claude-plugins-official-code-intelligence-lsp-pl' 'reranker-model' 'trafilatura' 'web-search-provider' 'phoenix' 'attest' 'dependabot' 'codeql-sarif' 'gpu-container-runtime' 'trufflehog' 'credential-custody' 'claude-code-action' 'agent-structural-diff' 'chezmoi'; do
  if [[ -z "$only" || "$only" == "$slot" ]]; then skipped "$slot"; fi
done
exit "$failed"
