#!/usr/bin/env bash
# Revised staged acceptance after round1. Target-distribution execution remains unrun.
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
  ''|claude-code|codex|claude-agent-sdk|codex-sdk-and-codex-exec-app-server|trail-of-bits-security-skills-trailofbits-skills|mcporter|mcp-inspector|sandbox-runtime-srt|isolation-container-boundary|serena|claude-plugins-official-code-intelligence-lsp-pl|tobi-qmd|mineru|trafilatura|playwright-cli|ccusage|context-supply|otel-collector-contrib|prometheus|loki|grafana|phoenix|local-model-server|inspect-ai|harbor-containerized-agent-e2e-runner|promptfoo|zizmor|attest|syft|dependabot|codeql-sarif|actionlint-kjanat|dagu|docker-compose|container-engine|betterleaks|trufflehog|git|gh-github-cli|worktrunk|difftastic|claude-code-action|agent-structural-diff|mise|restic|chezmoi|base-distribution|gpt-gateway|agent-runtime-worker|research-harnesses|credential-guard|convergence-validators) ;;
  *) printf 'Unknown slot: %s\n' "$only" >&2; exit 2 ;;
esac

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
      check trail-of-bits-security-skills-trailofbits-skills smoke 'claude plugin list && codex plugin list'
      ;;
    *) skipped trail-of-bits-security-skills-trailofbits-skills ;;
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

mcp-inspector() {
  # MCP Inspector; https://github.com/modelcontextprotocol/inspector
  case "$stage" in
    *) skipped mcp-inspector ;;
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

isolation-container-boundary() {
  # No additional component: rootless containers on the container engine that the hosting layer installs; excluded
  case "$stage" in
    *) skipped isolation-container-boundary ;;
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

claude-plugins-official-code-intelligence-lsp-pl() {
  # claude-plugins-official (code-intelligence LSP plugins); https://github.com/anthropics/claude-plugins-official
  case "$stage" in
    *) skipped claude-plugins-official-code-intelligence-lsp-pl ;;
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

trafilatura() {
  # trafilatura; https://github.com/adbar/trafilatura
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/adbar/trafilatura/v2.2.0/docs/quickstart.rst#L102
      check trafilatura smoke 'trafilatura -u "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"'
      ;;
    *) skipped trafilatura ;;
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

ccusage() {
  # ccusage; https://github.com/ccusage/ccusage
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/ccusage/ccusage/v20.0.26/docs/guide/installation.md#L144
      check ccusage smoke 'ccusage daily'
      ;;
    *) skipped ccusage ;;
  esac
}

context-supply() {
  # No context-supply layer: the usage meter only; excluded
  case "$stage" in
    *) skipped context-supply ;;
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

phoenix() {
  # Phoenix; https://github.com/Arize-ai/phoenix
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/docker/compose/5f94fb0aa42a2cd1248c6e6c7fafb87546b9c8de/docs/reference/compose_config.md#L27
      check phoenix smoke 'docker compose -f "$plan_dir/config/phoenix-compose.yaml" config --quiet'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/Arize-ai/phoenix/arize-phoenix-v20.19.0/helm/templates/phoenix/deployment.yaml#L72
      check phoenix health 'curl -fsS http://127.0.0.1:21606/readyz'
      ;;
    *) skipped phoenix ;;
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

promptfoo() {
  # Promptfoo; https://github.com/promptfoo/promptfoo
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/promptfoo/promptfoo/0.123.1/site/docs/installation.md#L80
      check promptfoo 'version only' 'promptfoo --version'
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

attest() {
  # attest; https://github.com/actions/attest
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/actions/attest/1e69f48acb82d1966a394da916b4c1698aa569d6/README.md#L80
      # Unavailable: Workflow/repository adoption pointer; no host executable is installed. No post-install host self-test or version command is supplied by this route.
      skipped attest
      ;;
    *) skipped attest ;;
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

dependabot() {
  # Dependabot; https://github.com/dependabot/dependabot-core
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/dependabot/dependabot-core/a1750051287d1f3786081d3aa3e6e2b04a72edde/README.md#L42
      # Unavailable: Workflow/repository adoption pointer; no host executable is installed. No post-install host self-test or version command is supplied by this route.
      skipped dependabot
      ;;
    *) skipped dependabot ;;
  esac
}

codeql-sarif() {
  # codeql-sarif; https://github.com/github/codeql-action
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/github/codeql-action/416ff0dea110f80f0f56f0046500dbf7420e4bb0/upload-sarif/action.yml#L1
      # Unavailable: Workflow/repository adoption pointer; no host executable is installed. No post-install host self-test or version command is supplied by this route.
      skipped codeql-sarif
      ;;
    *) skipped codeql-sarif ;;
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

trufflehog() {
  # trufflehog; https://github.com/trufflesecurity/trufflehog
  case "$stage" in
    *) skipped trufflehog ;;
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

claude-code-action() {
  # claude-code-action; https://github.com/anthropics/claude-code-action
  case "$stage" in
    post_install)
      # Kind: unavailable; Source: https://raw.githubusercontent.com/anthropics/claude-code-action/97c53473391bff1901034d4b454b5bac7ab7a029/docs/usage.md#L17
      # Unavailable: Workflow/repository adoption pointer; no host executable is installed. No post-install host self-test or version command is supplied by this route.
      skipped claude-code-action
      ;;
    *) skipped claude-code-action ;;
  esac
}

agent-structural-diff() {
  # Not installed: git diff and difftastic cover diffs; excluded
  case "$stage" in
    *) skipped agent-structural-diff ;;
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

chezmoi() {
  # chezmoi; https://github.com/twpayne/chezmoi
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/twpayne/chezmoi/24b71e4cf9d98cce0801cfc68e7553355efeaff7/internal/cmd/doctorcmd.go#L613
      check chezmoi smoke 'chezmoi_probe="$(mktemp -d)"
trap '"'"'rm -rf -- "$chezmoi_probe"'"'"' EXIT
mkdir -p -- "$chezmoi_probe/source" "$chezmoi_probe/destination"
chezmoi --config "$chezmoi_probe/chezmoi.toml" --source "$chezmoi_probe/source" --destination "$chezmoi_probe/destination" --working-tree "$chezmoi_probe/source" doctor'
      ;;
    *) skipped chezmoi ;;
  esac
}

base-distribution() {
  # Ubuntu 26.04.1 LTS (Canonical WSL image), primary; https://ubuntu.com/download/server
  case "$stage" in
    *) skipped base-distribution ;;
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
  # GPT Researcher and DeerFlow, kept as two independent evidence gatherers; https://github.com/assafelovic/gpt-researcher
  case "$stage" in
    post_install)
      # Kind: version only; Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/pyproject.toml#L23
      check research-harnesses 'version only' 'cd "$tool_root/gpt-researcher"
.venv/bin/python -c '"'"'import tomllib; from gpt_researcher import GPTResearcher; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'"'"''
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
  # GPT Researcher and DeerFlow, kept as two independent evidence gatherers; https://github.com/bytedance/deer-flow
  case "$stage" in
    post_install)
      # Kind: smoke; Source: https://raw.githubusercontent.com/docker/compose/5f94fb0aa42a2cd1248c6e6c7fafb87546b9c8de/docs/reference/compose_config.md#L27
      check research-harnesses smoke 'cd "$tool_root/deer-flow/docker"
DEER_FLOW_ROOT="$tool_root/deer-flow" docker compose -p deer-flow-dev -f docker-compose-dev.yaml config --quiet'
      ;;
    service_health)
      # Kind: health; Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose.yaml#L152
      check research-harnesses health 'curl -fsS http://127.0.0.1:2026/health/ready'
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
if [[ -z "$only" || "$only" == mcporter ]]; then mcporter; fi
if [[ -z "$only" || "$only" == mcp-inspector ]]; then mcp-inspector; fi
if [[ -z "$only" || "$only" == sandbox-runtime-srt ]]; then sandbox-runtime-srt; fi
if [[ -z "$only" || "$only" == isolation-container-boundary ]]; then isolation-container-boundary; fi
if [[ -z "$only" || "$only" == serena ]]; then serena; fi
if [[ -z "$only" || "$only" == claude-plugins-official-code-intelligence-lsp-pl ]]; then claude-plugins-official-code-intelligence-lsp-pl; fi
if [[ -z "$only" || "$only" == tobi-qmd ]]; then tobi-qmd; fi
if [[ -z "$only" || "$only" == mineru ]]; then mineru; fi
if [[ -z "$only" || "$only" == trafilatura ]]; then trafilatura; fi
if [[ -z "$only" || "$only" == playwright-cli ]]; then playwright-cli; fi
if [[ -z "$only" || "$only" == ccusage ]]; then ccusage; fi
if [[ -z "$only" || "$only" == context-supply ]]; then context-supply; fi
if [[ -z "$only" || "$only" == otel-collector-contrib ]]; then otel-collector-contrib; fi
if [[ -z "$only" || "$only" == prometheus ]]; then prometheus; fi
if [[ -z "$only" || "$only" == loki ]]; then loki; fi
if [[ -z "$only" || "$only" == grafana ]]; then grafana; fi
if [[ -z "$only" || "$only" == phoenix ]]; then phoenix; fi
if [[ -z "$only" || "$only" == local-model-server ]]; then local-model-server; fi
if [[ -z "$only" || "$only" == inspect-ai ]]; then inspect-ai; fi
if [[ -z "$only" || "$only" == harbor-containerized-agent-e2e-runner ]]; then harbor-containerized-agent-e2e-runner; fi
if [[ -z "$only" || "$only" == promptfoo ]]; then promptfoo; fi
if [[ -z "$only" || "$only" == zizmor ]]; then zizmor; fi
if [[ -z "$only" || "$only" == attest ]]; then attest; fi
if [[ -z "$only" || "$only" == syft ]]; then syft; fi
if [[ -z "$only" || "$only" == dependabot ]]; then dependabot; fi
if [[ -z "$only" || "$only" == codeql-sarif ]]; then codeql-sarif; fi
if [[ -z "$only" || "$only" == actionlint-kjanat ]]; then actionlint-kjanat; fi
if [[ -z "$only" || "$only" == dagu ]]; then dagu; fi
if [[ -z "$only" || "$only" == docker-compose ]]; then docker-compose; fi
if [[ -z "$only" || "$only" == container-engine ]]; then container-engine; fi
if [[ -z "$only" || "$only" == betterleaks ]]; then betterleaks; fi
if [[ -z "$only" || "$only" == trufflehog ]]; then trufflehog; fi
if [[ -z "$only" || "$only" == git ]]; then git; fi
if [[ -z "$only" || "$only" == gh-github-cli ]]; then gh-github-cli; fi
if [[ -z "$only" || "$only" == worktrunk ]]; then worktrunk; fi
if [[ -z "$only" || "$only" == difftastic ]]; then difftastic; fi
if [[ -z "$only" || "$only" == claude-code-action ]]; then claude-code-action; fi
if [[ -z "$only" || "$only" == agent-structural-diff ]]; then agent-structural-diff; fi
if [[ -z "$only" || "$only" == mise ]]; then mise; fi
if [[ -z "$only" || "$only" == restic ]]; then restic; fi
if [[ -z "$only" || "$only" == chezmoi ]]; then chezmoi; fi
if [[ -z "$only" || "$only" == base-distribution ]]; then base-distribution; fi
if [[ -z "$only" || "$only" == gpt-gateway ]]; then gpt-gateway; fi
if [[ -z "$only" || "$only" == agent-runtime-worker ]]; then agent-runtime-worker; fi
if [[ -z "$only" || "$only" == research-harnesses ]]; then research-harnesses; fi
if [[ -z "$only" || "$only" == credential-guard ]]; then credential-guard; fi
if [[ -z "$only" || "$only" == convergence-validators ]]; then convergence-validators; fi
exit "$failed"
