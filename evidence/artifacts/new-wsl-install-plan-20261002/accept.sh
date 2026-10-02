#!/usr/bin/env bash
# SOURCE-ONLY, UNRUN: every acceptance command below is planned, never executed here.
# Smoke examples can use provider access, download models, or create files (see README).
set -euo pipefail
if (( EUID == 0 )); then printf 'Refusing to run as root.\n' >&2; exit 1; fi
plan_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$plan_dir/../../.." && pwd)"
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack"
export plan_dir repo_root tool_root config_root
export PATH="$HOME/.local/bin:$PATH"
only=''
while (( $# )); do
  case "$1" in
    --only) (( $# >= 2 )) || { printf 'Missing --only slot.\n' >&2; exit 2; }; only="$2"; shift 2 ;;
    *) printf 'Usage: %s [--only <slot>]\n' "$0" >&2; exit 2 ;;
  esac
done
case "$only" in
  ''|claude-code|codex|claude-agent-sdk|codex-sdk-and-codex-exec-app-server|trail-of-bits-security-skills-trailofbits-skills|mcporter|mcp-inspector|sandbox-runtime-srt|isolation-container-boundary|serena|claude-plugins-official-code-intelligence-lsp-pl|tobi-qmd|mineru|trafilatura|playwright-cli|ccusage|context-supply|otel-collector-contrib|prometheus|loki|grafana|phoenix|local-model-server|inspect-ai|harbor-containerized-agent-e2e-runner|promptfoo|zizmor|attest|syft|dependabot|codeql-sarif|actionlint-kjanat|dagu|docker-compose|container-engine|betterleaks|trufflehog|git|gh-github-cli|worktrunk|difftastic|claude-code-action|agent-structural-diff|mise|restic|chezmoi|base-distribution|gpt-gateway|agent-runtime-worker|research-harnesses|credential-guard|convergence-validators) ;;
  *) printf 'Unknown slot: %s\n' "$only" >&2; exit 2 ;;
esac

# UNRUN. Load installed global tools without activating or changing a shell.
if command -v mise >/dev/null && [[ -d "$tool_root" ]]; then
  if mise_environment="$(cd -- "$tool_root" && command mise env -s bash)"; then eval "$mise_environment"; fi
fi
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"; fi
failed=0
check() {
  local slot="$1" kind="$2" program="$3" rc=0
  # UNRUN. Discard application output; retain exit status without printing credential values.
  if bash -euo pipefail -c "$program" >/dev/null; then rc=0; else rc=$?; failed=1; fi
  printf '%s | %s | %s\n' "$slot" "$kind" "$rc"
}
unavailable() {
  # UNRUN. 77 records absence of a host check; never synthesize a passing check.
  printf '%s | unavailable | 77\n' "$1"
  failed=1
}
claude-code() {
  # UNRUN. Claude Code
  # Source: https://code.claude.com/docs/en/setup.md#L184
  check 'claude-code' 'smoke' 'claude doctor'
}

codex() {
  # UNRUN. Codex
  # Source: https://developers.openai.com/codex/cli/reference.md#L176
  check 'codex' 'smoke' 'codex doctor'
}

claude-agent-sdk() {
  # UNRUN. Claude Agent SDK
  # Source: https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/v0.2.163/README.md#L22
  check 'claude-agent-sdk' 'smoke' '"$tool_root/claude-agent-sdk/bin/python" - <<'\''PY'\''
import anyio
from claude_agent_sdk import query

async def main():
    async for message in query(prompt="What is 2 + 2?"):
        print(message)

anyio.run(main)
PY'
}

codex-sdk-and-codex-exec-app-server() {
  # UNRUN. Codex SDK and codex exec/app-server
  # Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/sdk/typescript/README.md#L15
  check 'codex-sdk-and-codex-exec-app-server' 'smoke' 'cd "$tool_root/codex-sdk"
node --input-type=module - <<'\''JS'\''
import { Codex } from "@openai/codex-sdk";

const codex = new Codex();
const thread = codex.startThread({ skipGitRepoCheck: true });
const turn = await thread.run("Diagnose the test failure and propose a fix");

console.log(turn.finalResponse);
console.log(turn.items);
JS'
}

trail-of-bits-security-skills-trailofbits-skills() {
  # UNRUN. Trail of Bits security skills (trailofbits/skills)
  # Source: https://raw.githubusercontent.com/trailofbits/skills/82fe8226252622fa807643bdca1710901198553a/README.md#L28
  check 'trail-of-bits-security-skills-trailofbits-skills' 'smoke' 'claude plugin list && codex plugin list'
}

mcporter() {
  # UNRUN. mcporter
  # Source: https://raw.githubusercontent.com/openclaw/mcporter/v0.14.2/docs/install.md#L52
  check 'mcporter' 'smoke' 'mcporter list'
}

mcp-inspector() {
  printf '%s\n' 'mcp-inspector | excluded | 0'
}

sandbox-runtime-srt() {
  # UNRUN. sandbox-runtime (srt)
  # Source: https://raw.githubusercontent.com/anthropics/sandbox-runtime/v0.0.78/README.md#L168
  check 'sandbox-runtime-srt' 'smoke' 'srt echo "hello world"'
}

isolation-container-boundary() {
  printf '%s\n' 'isolation-container-boundary | excluded | 0'
}

serena() {
  # UNRUN. Serena
  # Source: https://raw.githubusercontent.com/oraios/serena/v1.7.0/README.md#L237
  check 'serena' 'smoke' 'mkdir -p "$tool_root/accept-serena"
cd "$tool_root/accept-serena"
serena init'
}

claude-plugins-official-code-intelligence-lsp-pl() {
  printf '%s\n' 'claude-plugins-official-code-intelligence-lsp-pl | excluded | 0'
}

tobi-qmd() {
  # UNRUN. tobi/qmd
  # Source: https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L671
  check 'tobi-qmd' 'smoke' 'qmd status'
}

mineru() {
  # UNRUN. MinerU
  # Source: https://raw.githubusercontent.com/opendatalab/mineru/mineru-4.0.10-released/README.md#L365
  check 'mineru' 'smoke' 'mineru --help'
}

trafilatura() {
  # UNRUN. trafilatura
  # Source: https://raw.githubusercontent.com/adbar/trafilatura/v2.2.0/docs/quickstart.rst#L102
  check 'trafilatura' 'smoke' 'trafilatura -u "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"'
}

playwright-cli() {
  # UNRUN. Playwright CLI
  # Source: https://raw.githubusercontent.com/microsoft/playwright-cli/v0.1.22/README.md#L85
  check 'playwright-cli' 'smoke' 'playwright-cli open https://playwright.dev && playwright-cli close'
}

ccusage() {
  # UNRUN. ccusage
  # Source: https://raw.githubusercontent.com/ccusage/ccusage/v20.0.26/docs/guide/installation.md#L144
  check 'ccusage' 'smoke' 'ccusage daily'
}

context-supply() {
  printf '%s\n' 'context-supply | excluded | 0'
}

otel-collector-contrib() {
  # UNRUN. OTel Collector Contrib
  # Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-contrib/v0.162.0/extension/healthcheckextension/README.md#L96
  check 'otel-collector-contrib' 'health' 'curl -fsS http://127.0.0.1:21333/health/status'
}

prometheus() {
  # UNRUN. Prometheus
  # Source: https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/management_api.md#L22
  check 'prometheus' 'health' 'curl -fsS http://127.0.0.1:21090/-/ready'
}

loki() {
  # UNRUN. Loki
  # Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/docs/sources/reference/loki-http-api.md#L1204
  check 'loki' 'health' 'curl -fsS http://127.0.0.1:21300/ready'
}

grafana() {
  # UNRUN. Grafana
  # Source: https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/developer-resources/api-reference/http-api/api-legacy/other.md#L99
  check 'grafana' 'health' 'curl -fsS http://127.0.0.1:21301/api/health'
}

phoenix() {
  # UNRUN. Phoenix
  # Source: https://raw.githubusercontent.com/Arize-ai/phoenix/arize-phoenix-v20.19.0/helm/templates/phoenix/deployment.yaml#L72
  check 'phoenix' 'health' 'curl -fsS http://127.0.0.1:21606/readyz'
}

local-model-server() {
  # UNRUN. Ollama
  # Source: https://raw.githubusercontent.com/ollama/ollama/v0.35.0/docs/cli.mdx#L73
  check 'local-model-server' 'smoke' 'OLLAMA_HOST=127.0.0.1:21434 ollama run embeddinggemma "Hello world"'
}

inspect-ai() {
  # UNRUN. Inspect AI
  # Source: https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/0.3.273/src/inspect_ai/_cli/main.py#L23
  check 'inspect-ai' 'version only' 'inspect --version'
}

harbor-containerized-agent-e2e-runner() {
  # UNRUN. Harbor (containerized agent E2E runner)
  # Source: https://raw.githubusercontent.com/harbor-framework/harbor/v0.23.0/skills/create-adapter/SKILL.md#L30
  check 'harbor-containerized-agent-e2e-runner' 'version only' 'harbor --version'
}

promptfoo() {
  # UNRUN. Promptfoo
  # Source: https://raw.githubusercontent.com/promptfoo/promptfoo/0.123.1/site/docs/installation.md#L80
  check 'promptfoo' 'version only' 'promptfoo --version'
}

zizmor() {
  # UNRUN. zizmor
  # Source: https://raw.githubusercontent.com/zizmorcore/zizmor/v1.30.1/docs/quickstart.md#L3
  check 'zizmor' 'smoke' 'zizmor -h'
}

attest() {
  # UNRUN. attest
  unavailable 'attest'
}

syft() {
  # UNRUN. Syft
  # Source: https://raw.githubusercontent.com/anchore/syft/v1.54.0/README.md#L48
  check 'syft' 'smoke' 'syft alpine:latest'
}

dependabot() {
  # UNRUN. Dependabot
  unavailable 'dependabot'
}

codeql-sarif() {
  # UNRUN. codeql-sarif
  unavailable 'codeql-sarif'
}

actionlint-kjanat() {
  # UNRUN. actionlint (kjanat)
  # Source: https://raw.githubusercontent.com/kjanat/actionlint/v1.17.0/docs/install.md#L127
  check 'actionlint-kjanat' 'version only' 'actionlint -version'
}

dagu() {
  # UNRUN. Dagu
  # Source: https://raw.githubusercontent.com/dagucloud/dagu/v2.18.1/scripts/installer.sh#L1997
  check 'dagu' 'health' 'curl -fsS http://127.0.0.1:21080/api/v1/health'
}

docker-compose() {
  # UNRUN. Docker Compose
  # Source: https://raw.githubusercontent.com/docker/docs/f0e4e4790191aaee83f9375dce56ada3971c6773/content/manuals/compose/install/linux.md#L51
  check 'docker-compose' 'version only' 'docker compose version'
}

container-engine() {
  # UNRUN. Docker Engine / Moby
  # Source: https://raw.githubusercontent.com/docker/docs/0571430b6a9c6ff1742baede7c265c3c5e9e3322/content/manuals/engine/security/rootless/troubleshoot.md#L212
  check 'container-engine' 'smoke' 'docker run hello-world'
}

betterleaks() {
  # UNRUN. betterleaks
  # Source: https://raw.githubusercontent.com/betterleaks/betterleaks/v1.9.0/README.md#L57
  check 'betterleaks' 'smoke' 'betterleaks dir "$plan_dir" -v'
}

trufflehog() {
  printf '%s\n' 'trufflehog | excluded | 0'
}

git() {
  # UNRUN. git
  unavailable 'git'
}

gh-github-cli() {
  # UNRUN. gh (GitHub CLI)
  # Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/github-cli.toml#L4
  check 'gh-github-cli' 'version only' 'gh --version'
}

worktrunk() {
  # UNRUN. worktrunk
  # Source: https://raw.githubusercontent.com/max-sixty/worktrunk/v0.80.0/README.md#L166
  check 'worktrunk' 'smoke' 'cd "$repo_root"
wt list'
}

difftastic() {
  # UNRUN. difftastic
  # Source: https://raw.githubusercontent.com/Wilfred/difftastic/0.71.0/.github/ISSUE_TEMPLATE/bug_report.md#L16
  check 'difftastic' 'version only' 'difft --version'
}

claude-code-action() {
  # UNRUN. claude-code-action
  unavailable 'claude-code-action'
}

agent-structural-diff() {
  printf '%s\n' 'agent-structural-diff | excluded | 0'
}

mise() {
  # UNRUN. mise
  # Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/docs/installing-mise.md#L511
  check 'mise' 'smoke' 'mise doctor'
}

restic() {
  # UNRUN. Restic
  # Source: https://raw.githubusercontent.com/restic/restic/v0.19.1/doc/man/restic-version.1#L9
  check 'restic' 'version only' 'restic version'
}

chezmoi() {
  # UNRUN. chezmoi
  # Source: https://raw.githubusercontent.com/twpayne/chezmoi/v2.73.0/assets/chezmoi.io/docs/reference/commands/doctor.md#L14
  check 'chezmoi' 'smoke' 'chezmoi doctor'
}

base-distribution() {
  printf '%s\n' 'base-distribution | excluded | 0'
}

gpt-gateway() {
  # UNRUN. OmniRoute
  # Source: https://raw.githubusercontent.com/diegosouzapw/OmniRoute/v3.8.51/docs/reference/CLI-TOOLS.md#L650
  check 'gpt-gateway' 'smoke' 'omniroute doctor --json --liveness-url http://127.0.0.1:21128/api/monitoring/health'
}

agent-runtime-worker() {
  # UNRUN. OpenHands software-agent-sdk
  # Source: https://raw.githubusercontent.com/OpenHands/docs/832ad1635431c7711cbfdc9d1f52c2dab9ee7e61/sdk/getting-started.mdx#L149
  check 'agent-runtime-worker' 'smoke' 'cd "$tool_root/openhands-source"
"$tool_root/agent-runtime-worker/bin/python" examples/01_standalone_sdk/01_hello_world.py'
}

research-harnesses() {
  # UNRUN. GPT Researcher and DeerFlow, kept as two independent evidence gatherers
  # Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/v3.7.0/docs/docs/gpt-researcher/gptr/pip-package.md#L32
  check 'research-harnesses' 'smoke' 'cd "$tool_root/gpt-researcher"
.venv/bin/python - <<'\''PY'\''
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
  # UNRUN. GPT Researcher and DeerFlow, kept as two independent evidence gatherers
  # Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose.yaml#L152
  check 'research-harnesses' 'health' 'curl -fsS http://127.0.0.1:2026/health/ready'
}

credential-guard() {
  # UNRUN. Command and secret-path guard (K4)
  unavailable 'credential-guard'
}

convergence-validators() {
  # UNRUN. Convergence practice and its validators
  # Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/8b51946ee16e542e544936e19bb793114fea948e/adoption/README.md#L68
  check 'convergence-validators' 'smoke' 'cd "$repo_root"
python3 scripts/validate.py'
}

if [[ -z "$only" || "$only" == 'claude-code' ]]; then claude-code; fi
if [[ -z "$only" || "$only" == 'codex' ]]; then codex; fi
if [[ -z "$only" || "$only" == 'claude-agent-sdk' ]]; then claude-agent-sdk; fi
if [[ -z "$only" || "$only" == 'codex-sdk-and-codex-exec-app-server' ]]; then codex-sdk-and-codex-exec-app-server; fi
if [[ -z "$only" || "$only" == 'trail-of-bits-security-skills-trailofbits-skills' ]]; then trail-of-bits-security-skills-trailofbits-skills; fi
if [[ -z "$only" || "$only" == 'mcporter' ]]; then mcporter; fi
if [[ -z "$only" || "$only" == 'mcp-inspector' ]]; then mcp-inspector; fi
if [[ -z "$only" || "$only" == 'sandbox-runtime-srt' ]]; then sandbox-runtime-srt; fi
if [[ -z "$only" || "$only" == 'isolation-container-boundary' ]]; then isolation-container-boundary; fi
if [[ -z "$only" || "$only" == 'serena' ]]; then serena; fi
if [[ -z "$only" || "$only" == 'claude-plugins-official-code-intelligence-lsp-pl' ]]; then claude-plugins-official-code-intelligence-lsp-pl; fi
if [[ -z "$only" || "$only" == 'tobi-qmd' ]]; then tobi-qmd; fi
if [[ -z "$only" || "$only" == 'mineru' ]]; then mineru; fi
if [[ -z "$only" || "$only" == 'trafilatura' ]]; then trafilatura; fi
if [[ -z "$only" || "$only" == 'playwright-cli' ]]; then playwright-cli; fi
if [[ -z "$only" || "$only" == 'ccusage' ]]; then ccusage; fi
if [[ -z "$only" || "$only" == 'context-supply' ]]; then context-supply; fi
if [[ -z "$only" || "$only" == 'otel-collector-contrib' ]]; then otel-collector-contrib; fi
if [[ -z "$only" || "$only" == 'prometheus' ]]; then prometheus; fi
if [[ -z "$only" || "$only" == 'loki' ]]; then loki; fi
if [[ -z "$only" || "$only" == 'grafana' ]]; then grafana; fi
if [[ -z "$only" || "$only" == 'phoenix' ]]; then phoenix; fi
if [[ -z "$only" || "$only" == 'local-model-server' ]]; then local-model-server; fi
if [[ -z "$only" || "$only" == 'inspect-ai' ]]; then inspect-ai; fi
if [[ -z "$only" || "$only" == 'harbor-containerized-agent-e2e-runner' ]]; then harbor-containerized-agent-e2e-runner; fi
if [[ -z "$only" || "$only" == 'promptfoo' ]]; then promptfoo; fi
if [[ -z "$only" || "$only" == 'zizmor' ]]; then zizmor; fi
if [[ -z "$only" || "$only" == 'attest' ]]; then attest; fi
if [[ -z "$only" || "$only" == 'syft' ]]; then syft; fi
if [[ -z "$only" || "$only" == 'dependabot' ]]; then dependabot; fi
if [[ -z "$only" || "$only" == 'codeql-sarif' ]]; then codeql-sarif; fi
if [[ -z "$only" || "$only" == 'actionlint-kjanat' ]]; then actionlint-kjanat; fi
if [[ -z "$only" || "$only" == 'dagu' ]]; then dagu; fi
if [[ -z "$only" || "$only" == 'docker-compose' ]]; then docker-compose; fi
if [[ -z "$only" || "$only" == 'container-engine' ]]; then container-engine; fi
if [[ -z "$only" || "$only" == 'betterleaks' ]]; then betterleaks; fi
if [[ -z "$only" || "$only" == 'trufflehog' ]]; then trufflehog; fi
if [[ -z "$only" || "$only" == 'git' ]]; then git; fi
if [[ -z "$only" || "$only" == 'gh-github-cli' ]]; then gh-github-cli; fi
if [[ -z "$only" || "$only" == 'worktrunk' ]]; then worktrunk; fi
if [[ -z "$only" || "$only" == 'difftastic' ]]; then difftastic; fi
if [[ -z "$only" || "$only" == 'claude-code-action' ]]; then claude-code-action; fi
if [[ -z "$only" || "$only" == 'agent-structural-diff' ]]; then agent-structural-diff; fi
if [[ -z "$only" || "$only" == 'mise' ]]; then mise; fi
if [[ -z "$only" || "$only" == 'restic' ]]; then restic; fi
if [[ -z "$only" || "$only" == 'chezmoi' ]]; then chezmoi; fi
if [[ -z "$only" || "$only" == 'base-distribution' ]]; then base-distribution; fi
if [[ -z "$only" || "$only" == 'gpt-gateway' ]]; then gpt-gateway; fi
if [[ -z "$only" || "$only" == 'agent-runtime-worker' ]]; then agent-runtime-worker; fi
if [[ -z "$only" || "$only" == 'research-harnesses' ]]; then research-harnesses; fi
if [[ -z "$only" || "$only" == 'credential-guard' ]]; then credential-guard; fi
if [[ -z "$only" || "$only" == 'convergence-validators' ]]; then convergence-validators; fi
exit "$failed"
