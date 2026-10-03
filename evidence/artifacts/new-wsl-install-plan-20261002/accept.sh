#!/usr/bin/env bash
# Revised staged acceptance for the merged definitive manifest (64 foundation rows). This revision ran on 2026-10-02 in a throwaway distribution (real-distribution-validation.json), and later that day, as merged to main (6652b78e), once on the destination distribution; the record of that run is private, and its public receipt comes with that distribution's acceptance.
# Five rows were added after the throwaway run, from the layer consensus of 2026-10-02 (69 foundation rows). The checks of skill-discovery and skill-authoring have not run anywhere; research-skill, credential-custody and cross-family-review install nothing and have nothing to check.
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
  ''|claude-code|codex|claude-agent-sdk|codex-sdk-and-codex-exec-app-server|trail-of-bits-security-skills-trailofbits-skills|engineering-process-skills|skill-discovery|skill-authoring|research-skill|mcporter|mcp-inspector|agent-messaging|sandbox-runtime-srt|isolation-container-boundary|serena|claude-plugins-official-code-intelligence-lsp-pl|structural-search|code-search|embedding-model|reranker-model|tobi-qmd|mineru|trafilatura|playwright-cli|web-search-provider|memory-owner|ccusage|context-supply|otel-collector-contrib|prometheus|loki|grafana|phoenix|local-model-server|alerting|local-generation-model|session-analytics|inspect-ai|harbor-containerized-agent-e2e-runner|promptfoo|zizmor|attest|syft|dependabot|codeql-sarif|actionlint-kjanat|dagu|docker-compose|container-engine|gpu-container-runtime|betterleaks|trufflehog|credential-custody|git|gh-github-cli|worktrunk|difftastic|claude-code-action|agent-structural-diff|cross-family-review|mise|restic|chezmoi|base-distribution|gpt-gateway|agent-runtime-worker|research-harnesses|credential-guard|convergence-validators) ;;
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
  # mattpocock/skills (selected skills, not the bundle); https://github.com/mattpocock/skills
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/README.md#L164
      check engineering-process-skills smoke 'declare -A want=([tdd]=423f3cc2bccf3b0ed426fb35eeb4b38d9188a343 [diagnosing-bugs]=463c81def888fefa77b894837d301d9ed70e0994 [codebase-design]=20b7cd1dd1fe5b0bd37ba72649f3a29375574b5b [domain-modeling]=959e63161ff78b4b1cd553b2c0e09e0c68418e5f [writing-for-agents]=bd9c9c4762db0a9a094fd419316ebd4b0444d06e [setup-matt-pocock-skills]=abf20c04a4aa8a37ff20aa7286f28857150f8b8d)
lock="${XDG_STATE_HOME:+$XDG_STATE_HOME/skills/.skill-lock.json}"
lock="${lock:-$HOME/.agents/.skill-lock.json}"
listing="$(npx --yes skills@1.7.0 list -g -a claude-code codex --json)"
for skill in tdd diagnosing-bugs codebase-design domain-modeling writing-for-agents setup-matt-pocock-skills; do
  for agent in '"'"'Claude Code'"'"' Codex; do
    jq -e --arg skill "$skill" --arg agent "$agent" '"'"'any(.[]; .name == $skill and (.agents | index($agent) != null))'"'"' <<<"$listing" >/dev/null
  done
  jq -e --arg skill "$skill" --arg hash "${want[$skill]}" '"'"'.skills[$skill].skillFolderHash == $hash'"'"' "$lock" >/dev/null
done'
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

tobi-qmd() {
  # tobi/qmd; https://github.com/tobi/qmd
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L671
      check tobi-qmd smoke 'qmd status'
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
      # Kind: smoke; Source: https://raw.githubusercontent.com/ollama/ollama/v0.35.0/docs/cli.mdx#L73
      check local-model-server smoke 'OLLAMA_HOST=127.0.0.1:21434 ollama run embeddinggemma "Hello world"'
      ;;
    *) skipped local-model-server ;;
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
      # Source: https://raw.githubusercontent.com/docker/compose/5f94fb0aa42a2cd1248c6e6c7fafb87546b9c8de/docs/reference/compose_config.md#L27 (DeerFlow Compose configuration, second part)
      check research-harnesses smoke 'cd "$tool_root/gpt-researcher"
.venv/bin/python -c '"'"'import tomllib; from gpt_researcher import GPTResearcher; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'"'"'
cd "$tool_root/deer-flow/docker"
DEER_FLOW_ROOT="$tool_root/deer-flow" docker compose -p deer-flow-dev -f docker-compose-dev.yaml config --quiet'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose.yaml#L152
      check research-harnesses health 'curl -fsS http://127.0.0.1:2026/health/ready'
      ;;
    after_sign_in)
      # Kind: smoke; Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/v3.7.0/docs/docs/gpt-researcher/gptr/pip-package.md#L32
      check research-harnesses smoke 'cd "$tool_root/gpt-researcher"
.venv/bin/python - <<'"'"'PY'"'"'
from gpt_researcher import GPTResearcher
import asyncio

async def get_report(query: str, report_type: str):
    researcher = GPTResearcher(query, report_type)
    research_result = await researcher.conduct_research()
    report = await researcher.write_report()
    research_context = researcher.get_research_context()
    research_costs = researcher.get_costs()
    research_images = researcher.get_research_images()
    research_sources = researcher.get_research_sources()
    return report, research_context, research_costs, research_images, research_sources

if __name__ == "__main__":
    query = "what team may win the NBA finals?"
    report_type = "research_report"
    report, context, costs, images, sources = asyncio.run(get_report(query, report_type))
    print("Report:")
    print(report)
    print("\nResearch Costs:")
    print(costs)
    print("\nNumber of Research Images:")
    print(len(images))
    print("\nNumber of Research Sources:")
    print(len(sources))
PY'
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
if [[ -z "$only" || "$only" == tobi-qmd ]]; then tobi-qmd; fi
if [[ -z "$only" || "$only" == mineru ]]; then mineru; fi
if [[ "$only" == playwright-cli ]]; then playwright-cli; elif [[ -z "$only" ]]; then skipped playwright-cli; fi
if [[ -z "$only" || "$only" == otel-collector-contrib ]]; then otel-collector-contrib; fi
if [[ -z "$only" || "$only" == prometheus ]]; then prometheus; fi
if [[ "$only" == loki ]]; then loki; elif [[ -z "$only" ]]; then skipped loki; fi
if [[ "$only" == grafana ]]; then grafana; elif [[ -z "$only" ]]; then skipped grafana; fi
if [[ -z "$only" || "$only" == local-model-server ]]; then local-model-server; fi
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
for slot in 'research-skill' 'mcp-inspector' 'agent-messaging' 'isolation-container-boundary' 'claude-plugins-official-code-intelligence-lsp-pl' 'code-search' 'embedding-model' 'reranker-model' 'trafilatura' 'web-search-provider' 'memory-owner' 'ccusage' 'context-supply' 'phoenix' 'local-generation-model' 'session-analytics' 'promptfoo' 'attest' 'dependabot' 'codeql-sarif' 'gpu-container-runtime' 'trufflehog' 'credential-custody' 'claude-code-action' 'agent-structural-diff' 'cross-family-review' 'chezmoi' 'base-distribution'; do
  if [[ -z "$only" || "$only" == "$slot" ]]; then skipped "$slot"; fi
done
exit "$failed"
