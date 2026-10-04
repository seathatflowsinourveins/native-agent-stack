#!/usr/bin/env bash
# Revised staged acceptance for the merged definitive manifest (64 foundation rows). This revision ran on 2026-10-02 in a throwaway distribution (real-distribution-validation.json), and later that day, as merged to main (6652b78e), once on the destination distribution; the record of that run is private, and its public receipt comes with that distribution's acceptance.
# Five rows were added after the throwaway run, from the layer consensus of 2026-10-02 (69 foundation rows). The checks of skill-discovery and skill-authoring have not run anywhere; research-skill, credential-custody and cross-family-review install nothing and have nothing to check.
# On 2026-10-03 the two local-model rows (local-generation-model, embedding-model) became installable after their measurement; like their installation, their checks run only with --only, and as plan rows they have not run anywhere.
# Wave 2 (2026-10-03): memory-owner, code-search, context-supply and statusline gained checks, and research-harnesses
# and tobi-qmd were revised; none of these checks has run anywhere.
# Wave 3 (2026-10-04, the owner's decision, amendment 4): the ten token-efficiency owner rows, ccusage and
# session-analytics gained checks, and code-search checks SocratiCode's installed version; none of these checks has run anywhere.
# Checks are quoted upstream commands/parameterizations from install-plan.json and SOURCES.md.
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
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/npm/cli/bfacd33ccbcd908480610703b60455d2da5b57a9/docs/lib/content/commands/npm-ls.md#L13
      check codex-sdk-and-codex-exec-app-server 'version only' 'cd "$tool_root/codex-sdk"
npm ls --depth=0 @openai/codex-sdk'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/sdk/typescript/README.md#L15
      check codex-sdk-and-codex-exec-app-server smoke 'cd "$tool_root/codex-sdk"
node --input-type=module - <<'"'"'JS'"'"'
import { Codex } from "@openai/codex-sdk";

const codex = new Codex();
const thread = codex.startThread({ skipGitRepoCheck: true });
const turn = await thread.run("Diagnose the test failure and propose a fix");

console.log(turn.finalResponse);
console.log(turn.items);
JS'
      ;;
    *) skipped codex-sdk-and-codex-exec-app-server ;;
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
  # mattpocock/skills (selected skills, not the bundle), with the rest of adoption/skills/manifest.json; https://github.com/mattpocock/skills
  # UNRUN on every distribution: revised from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/fd111e59a7480c7910907e5cdc9a32a9e42ec42e/tools/adoption/install_skills.py#L554 (--check-only: the read-only check of every selected skill)
      check engineering-process-skills smoke 'python3 -B "$repo_root/tools/adoption/install_skills.py" --skills-bin "$tool_root/skills-1.7.0/bin/skills" --check-only --json'
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
  # UNRUN on every distribution: added from the layer consensus of 2026-10-02, after the clean run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L164
      # The listing has no agent filter, so it reports every agent the installer detects, and it must name Claude Code as
      # the only agent of skill-creator. No same-name copy, and no dangling link, may sit in the installer's shared
      # directory, which it uses for Codex's global skills, or in Codex's own global skills directory (README.md#L298);
      # Codex keeps its embedded skills under skills/.system, which these lines leave alone. Both directories are tested
      # in one [[ ]] as the last command, so its status is the program's on any bash: before 4.1 (macOS /bin/bash is 3.2)
      # a failing [[ ]] does not stop a set -e script (bash NEWS, bash-4.1, item j).
      check skill-authoring smoke 'want=3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6
lock="${XDG_STATE_HOME:+$XDG_STATE_HOME/skills/.skill-lock.json}"
lock="${lock:-$HOME/.agents/.skill-lock.json}"
listing="$(npx --yes skills@1.7.0 list -g --json)"
jq -e '"'"'[.[] | select(.name == "skill-creator") | .agents] == [["Claude Code"]]'"'"' <<<"$listing" >/dev/null
jq -e --arg hash "$want" '"'"'.skills["skill-creator"].skillFolderHash == $hash'"'"' "$lock" >/dev/null
shared_copy="$HOME/.agents/skills/skill-creator"
codex_copy="${CODEX_HOME:-$HOME/.codex}/skills/skill-creator"
[[ ! -e "$shared_copy" && ! -L "$shared_copy" && ! -e "$codex_copy" && ! -L "$codex_copy" ]]'
      ;;
    *) skipped skill-authoring ;;
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
    *) skipped sandbox-runtime-srt ;;
  esac
}

serena() {
  # Serena; https://github.com/oraios/serena
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/oraios/serena/v1.7.0/README.md#L237
      check serena smoke 'serena init'
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
ast-grep -p '"'"'$A && $A()'"'"' -l ts "$ast_grep_probe/probe.ts"'
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
      # Kind: smoke; Source: https://raw.githubusercontent.com/opendatalab/mineru/mineru-4.0.10-released/README.md#L365
      check mineru smoke 'mineru --help'
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
      # Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/pins-linux-x86_64.json#L334 (the socraticode pin's version_probe, npm-metadata)
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
  # ccusage 20.0.26 (owner default, amendment 4); https://github.com/ccusage/ccusage
  # UNRUN on every distribution: changed by the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/pins-linux-x86_64.json#L282 (ccusage --version prints ccusage 20.0.26)
      check ccusage smoke '[[ "$("${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/ccusage" --version)" == "ccusage 20.0.26" ]]'
      ;;
    *) skipped ccusage ;;
  esac
}
command-output() {
  # RTK 0.50.0 (owner row, amendment 4); https://github.com/rtk-ai/rtk
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/rtk-ai/rtk/v0.50.0/README.md#L121 (--version); https://raw.githubusercontent.com/rtk-ai/rtk/v0.50.0/README.md#L193 (rtk git log); https://raw.githubusercontent.com/rtk-ai/rtk/v0.50.0/README.md#L309 (rtk proxy, the raw passthrough); https://raw.githubusercontent.com/rtk-ai/rtk/v0.50.0/README.md#L524 (RTK_TELEMETRY_DISABLED)
      # The version line is exact as the archive's binary printed it on 2026-10-04; the two log lines run in this checkout.
      # Planned. Source: https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L2940-L2952 (excluded commands exit 1 with No rewrite; the positive control exits 0 with its rewrite).
      check command-output smoke 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$("$e/bin/rtk" --version)" == "rtk 0.50.0" ]]
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
[[ "$decision" == "rtk git status" ]]'
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
      # Kind: smoke; Source: https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/8f7b34abe16fb459e0bf1c04747d584216dfe32e/README.md#L113 (jcodemunch-mcp --version); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L523 (its output at the pin)
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
      # Kind: smoke; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/pins-linux-x86_64.json#L267 (toon --version prints only the version); https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L63 (-o); https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L65 (--decode)
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
      check api-docs smoke '[[ "$(CHUB_TELEMETRY=0 CHUB_FEEDBACK=0 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/chub" --cli-version)" == 0.1.4 ]]
e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"
chub_source_config="${CHUB_DIR:-$HOME/.chub}/config.yaml"
chub_check_dir=$(mktemp -d "${TMPDIR:-/tmp}/new-wsl-chub-check.XXXXXX")
trap '"'"'rm -rf -- "$chub_check_dir"'"'"' EXIT
install -m 0600 -- "$chub_source_config" "$chub_check_dir/config.yaml"
env -u CHUB_TELEMETRY -u CHUB_FEEDBACK CHUB_DIR="$chub_check_dir" "$e/bin/node" --input-type=module -e '"'"'const { pathToFileURL } = await import("node:url"); const { isTelemetryEnabled, isFeedbackEnabled } = await import(pathToFileURL(process.argv[1]).href); const telemetry = isTelemetryEnabled(); const feedback = isFeedbackEnabled(); console.log("telemetry=" + telemetry + " feedback=" + feedback); if (telemetry !== false || feedback !== false) process.exit(1);'"'"' "$e/tools/context-hub-0.1.4/lib/node_modules/@aisuite/chub/src/lib/telemetry.js"'
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
  # agentsview 0.43.0 (local archive only) (owner default, amendment 4); https://github.com/kenn-io/agentsview
  # UNRUN on every distribution: changed by the wave-3 batch of 2026-10-04, after every recorded run of this plan.
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/kenn-io/agentsview/v0.43.0/README.md#L695 (AGENTSVIEW_TELEMETRY_ENABLED=0); docs/token-efficiency-stack.json (AGENTSVIEW_DISABLE_UPDATE_CHECK=1 in the agentsview use commands)
      # The --version line starts as the archive's binary printed it on 2026-10-04 (agentsview v0.43.0, then its commit); this project's integration check.
      check session-analytics smoke 'v="$(AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/agentsview" --version)"
[[ "$v" == "agentsview v0.43.0 "* ]]'
      ;;
    *) skipped session-analytics ;;
  esac
}
otel-collector-contrib() {
  # OTel Collector Contrib; https://github.com/open-telemetry/opentelemetry-collector-contrib
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector/62cdad2ea133239380b44d20d84eb26e114779b6/otelcol/command_validate.go#L15
      check otel-collector-contrib smoke 'otelcol-contrib validate --config="$config_root/otel.yaml"'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-contrib/v0.162.0/extension/healthcheckextension/README.md#L96
      check otel-collector-contrib health 'curl -fsS http://127.0.0.1:21333/health/status'
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
  # Alertmanager; https://github.com/prometheus/alertmanager
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/configuration.md#L620
      check alerting smoke '"$tool_root/alertmanager/alertmanager-0.34.1.linux-amd64/amtool" check-config "$config_root/alertmanager.yaml"'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/management_api.md#L22
      check alerting health 'curl -fsS http://127.0.0.1:21093/-/ready'
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
  # Grafana; https://github.com/grafana/grafana
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/grafana/grafana/6193dc03311b631b9727b560d24369e683dc396e/docs/sources/administration/cli.md#L69
      check grafana 'version only' 'grafana cli -v'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/developer-resources/api-reference/http-api/api-legacy/other.md#L99
      check grafana health 'curl -fsS http://127.0.0.1:21301/api/health'
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
  # Inspect AI; https://github.com/UKGovernmentBEIS/inspect_ai
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/0.3.273/src/inspect_ai/_cli/main.py#L23
      check inspect-ai 'version only' 'inspect --version'
      ;;
    *) skipped inspect-ai ;;
  esac
}

harbor-containerized-agent-e2e-runner() {
  # Harbor (containerized agent E2E runner); https://github.com/harbor-framework/harbor
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/harbor-framework/harbor/v0.23.0/skills/create-adapter/SKILL.md#L30
      check harbor-containerized-agent-e2e-runner 'version only' 'harbor --version'
      ;;
    *) skipped harbor-containerized-agent-e2e-runner ;;
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
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/anchore/syft/v1.54.0/README.md#L48
      check syft smoke 'syft alpine:latest'
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
      # Kind: smoke; Source: https://raw.githubusercontent.com/betterleaks/betterleaks/v1.9.0/README.md#L57
      check betterleaks smoke 'betterleaks dir "$plan_dir" -v'
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
  # worktrunk; https://github.com/max-sixty/worktrunk
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/max-sixty/worktrunk/v0.80.0/README.md#L166
      check worktrunk smoke 'cd "$repo_root"
wt list'
      ;;
    *) skipped worktrunk ;;
  esac
}

difftastic() {
  # difftastic; https://github.com/Wilfred/difftastic
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/Wilfred/difftastic/0.71.0/.github/ISSUE_TEMPLATE/bug_report.md#L16
      check difftastic 'version only' 'difft --version'
      ;;
    *) skipped difftastic ;;
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

gpt-gateway() {
  # OmniRoute; https://github.com/diegosouzapw/OmniRoute
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/diegosouzapw/OmniRoute/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/commands/doctor.mjs#L630
      check gpt-gateway smoke 'omniroute --output json doctor --no-liveness'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/diegosouzapw/OmniRoute/c1e30b7676975feb298b49eff6ff58923c04b89e/src/app/healthz/route.ts#L17
      # /readyz aliases /healthz. Doctor warns rather than fails for unreachable HTTP.
      check gpt-gateway health 'curl -fsS http://127.0.0.1:21128/readyz
omniroute --output json doctor --liveness-url http://127.0.0.1:21128/api/monitoring/health'
      ;;
    *) skipped gpt-gateway ;;
  esac
}

agent-runtime-worker() {
  # OpenHands software-agent-sdk; https://github.com/OpenHands/software-agent-sdk
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/OpenHands/software-agent-sdk/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/__init__.py#L113
      check agent-runtime-worker 'version only' '"$tool_root/agent-runtime-worker/bin/python" -c '"'"'from importlib.metadata import version; print(version("openhands-sdk")); print(version("openhands-tools"))'"'"''
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/OpenHands/docs/832ad1635431c7711cbfdc9d1f52c2dab9ee7e61/sdk/getting-started.mdx#L149
      check agent-runtime-worker smoke 'cd "$tool_root/openhands-source"
"$tool_root/agent-runtime-worker/bin/python" examples/01_standalone_sdk/01_hello_world.py'
      ;;
    *) skipped agent-runtime-worker ;;
  esac
}

research-harnesses() {
  # GPT Researcher and DeerFlow, kept as two independent evidence gatherers; https://github.com/assafelovic/gpt-researcher and https://github.com/bytedance/deer-flow
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/pyproject.toml#L23
      # Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/config/config.py#L158 (the preflight reads upstream's Config; wave-2 research ruling, change 4)
      # Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/README.md#L1658 (the embedded DeerFlowClient)
      check research-harnesses smoke 'cd "$tool_root/gpt-researcher"
.venv/bin/python -c '\''import tomllib; from gpt_researcher import GPTResearcher; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'\''
bash "$repo_root/tools/research/gpt_researcher.sh" --preflight-only
"$tool_root/deer-flow/backend/.venv/bin/python" -c '\''from deerflow.client import DeerFlowClient'\'''
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/cli.py#L336 (the success line)
      # One short current-month run through the destination gateway, research_report only (wave-2 research ruling, changes 5 and 6; synthesis X18). UNRUN.
      check research-harnesses smoke 'out="$(bash "$repo_root/tools/research/gpt_researcher.sh" "Ubuntu 26.04 WSL news this month")"
grep -q "^Report written to '\''outputs/" <<<"$out"
run="$(sed -n '\''s/^run directory: //p'\'' <<<"$out")"
refs="$(awk '\''/^#+ *References/{f=1} f'\'' "$run"/outputs/*.md | grep -oE '\''https?://[^) >]+'\'' | sort -u | wc -l)"
[[ "$refs" -ge 5 ]]'
      ;;
    *) skipped research-harnesses ;;
  esac
}

credential-guard() {
  # Command and secret-path guard (K4); https://github.com/seathatflowsinourveins/native-agent-stack
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/8b51946ee16e542e544936e19bb793114fea948e/adoption/bootstrap.md#L400
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
if [[ -z "$only" || "$only" == mise ]]; then mise; fi
if [[ -z "$only" || "$only" == restic ]]; then restic; fi
if [[ -z "$only" || "$only" == gpt-gateway ]]; then gpt-gateway; fi
if [[ -z "$only" || "$only" == agent-runtime-worker ]]; then agent-runtime-worker; fi
if [[ -z "$only" || "$only" == research-harnesses ]]; then research-harnesses; fi
if [[ -z "$only" || "$only" == credential-guard ]]; then credential-guard; fi
if [[ -z "$only" || "$only" == convergence-validators ]]; then convergence-validators; fi
# Planned. Rows the plan does not install (merged manifest): nothing to check, so each prints its skip.
for slot in 'research-skill' 'mcp-inspector' 'agent-messaging' 'isolation-container-boundary' 'claude-plugins-official-code-intelligence-lsp-pl' 'reranker-model' 'trafilatura' 'web-search-provider' 'phoenix' 'promptfoo' 'attest' 'dependabot' 'codeql-sarif' 'gpu-container-runtime' 'trufflehog' 'credential-custody' 'claude-code-action' 'agent-structural-diff' 'cross-family-review' 'chezmoi' 'base-distribution'; do
  if [[ -z "$only" || "$only" == "$slot" ]]; then skipped "$slot"; fi
done
exit "$failed"
