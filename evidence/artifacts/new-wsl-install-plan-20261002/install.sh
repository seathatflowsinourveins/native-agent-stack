#!/usr/bin/env bash
# Revised after round1; revised target-distribution installation remains unrun.
# Baseline results and limitations: VALIDATION.md.
# Upstream command quotations and parameterizations: install-plan.json and SOURCES.md.
set -euo pipefail
if (( EUID == 0 )); then
  printf 'Refusing to run as root.\n' >&2
  exit 1
fi
plan_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$plan_dir/../../.." && pwd)"
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack"
export plan_dir repo_root tool_root config_root
export PATH="$HOME/.local/bin:$PATH"
export MISE_YES=1
only=''
list=false
while (( $# )); do
  case "$1" in
    --only) (( $# >= 2 )) || { printf 'Missing --only slot.\n' >&2; exit 2; }; only="$2"; shift 2 ;;
    --list) list=true; shift ;;
    *) printf 'Usage: %s [--only <slot>] [--list]\n' "$0" >&2; exit 2 ;;
  esac
done
selected() { [[ -z "$only" || "$only" == "$1" ]]; }
refresh_path() {
  # Planned. mise v2026.10.0 docs/cli/env.md:40; process-scoped, no shell activation.
  local env_script
  env_script="$(cd -- "$tool_root" && command mise env -s bash)" || return "$?"
  eval "$env_script"
  # mise doctor requires activation or shims; shims are the noninteractive route.
  # Source: https://raw.githubusercontent.com/jdx/mise/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/src/cli/doctor/mod.rs#L532
  export PATH="${MISE_SHIMS_DIR:-${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims}:$PATH"
}
ensure_venv() {
  # Planned. uv 0.12.22 docs/pip/environments.md:21,27; idempotence guard is plan glue.
  if [[ ! -x "$1/bin/python" ]]; then uv venv --python 3.13.16 "$1"; fi
}
checkout_tag() {
  # Planned. Each owner's documented git clone, with tag/depth/destination parameters.
  local url="$1" tag="$2" dir="$3"
  if [[ ! -d "$dir" ]]; then
    git clone --depth 1 --branch "$tag" "$url" "$dir"
  else
    [[ "$(git -C "$dir" config --get remote.origin.url)" == "$url" ]] || return 1
    [[ "$(git -C "$dir" rev-parse HEAD)" == "$(git -C "$dir" rev-parse "$tag^{commit}")" ]] || return 1
    git -C "$dir" diff --quiet
    git -C "$dir" diff --cached --quiet
  fi
}
fetch_verified() {
  # Planned. HTTPS transport from upstream OTel binary recipe; published SHA256 required.
  # Download glue is separate from quoted owner installation commands (SOURCES.md).
  local url="$1" digest="$2" target="$3"
  mkdir -p -- "$(dirname -- "$target")"
  if [[ -f "$target" ]] && printf '%s  %s\n' "$digest" "$target" | sha256sum --check --status; then return; fi
  local temporary
  temporary="$(mktemp "${target}.XXXXXX")"
  if ! curl --proto '=https' --tlsv1.2 -fL "$url" -o "$temporary"; then rm -f -- "$temporary"; return 1; fi
  if ! printf '%s  %s\n' "$digest" "$temporary" | sha256sum --check --status; then rm -f -- "$temporary"; return 1; fi
  mv -- "$temporary" "$target"
}
copy_config() {
  # Planned. Preserve existing operator configuration; never overwrite it on rerun.
  local name="$1"
  mkdir -p -- "$config_root"
  if [[ ! -e "$config_root/$name" ]]; then
    install -m 0600 -- "$plan_dir/config/$name" "$config_root/$name"
  elif ! cmp -s -- "$plan_dir/config/$name" "$config_root/$name"; then
    printf 'Existing %s differs; retained. Review loopback settings before starting.\n' "$name" >&2
  fi
}
link_grafana() {
  # Planned. User-prefix placement around upstream tar install; no system package/service.
  local dir
  for dir in "$tool_root/grafana"/grafana*; do
    if [[ -d "$dir" && -x "$dir/bin/grafana" ]]; then
      ln -sfn -- "$dir/bin/grafana" "$HOME/.local/bin/grafana"
      return
    fi
  done
  printf 'Upstream Grafana archive has no expected bin/grafana.\n' >&2
  return 1
}
docker_repository() {
  # Planned. docker/docs dd2797b... content/manuals/engine/install/ubuntu.md:129-145.
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && printf '%s' "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  sudo apt-get update
}
apt_release_version() {
  # Planned. Native apt metadata selects upstream's documented VERSION_STRING, no guessed revision.
  local package="$1" upstream="$2" answer
  answer="$(apt list --all-versions "$package" 2>/dev/null | awk -v want="$upstream" '
    { v=$2; sub(/^[0-9]+:/, "", v); if (!found && (v == want || index(v, want "-") == 1)) { answer=$2; found=1 } }
    END { if (found) print answer }')"
  [[ -n "$answer" ]] || { printf 'Requested %s release %s unavailable in apt repository.\n' "$package" "$upstream" >&2; return 1; }
  printf '%s' "$answer"
}
docker_engine_packages() {
  # Planned. docker/docs Ubuntu specific-version recipe:176-177; rootless docs:94.
  local engine_version
  engine_version="$(apt_release_version docker-ce 29.8.2)"
  sudo apt-get install -y --no-install-recommends "docker-ce=$engine_version" "docker-ce-cli=$engine_version" \
    "docker-ce-rootless-extras=$engine_version" containerd.io docker-buildx-plugin
}
docker_compose_package() {
  # Planned. Official Compose apt route; exact upstream version selected from apt metadata.
  local compose_version
  compose_version="$(apt_release_version docker-compose-plugin 5.5.1)"
  sudo apt-get install -y --no-install-recommends "docker-compose-plugin=$compose_version"
}
run_command() {
  # Planned. Thin Bash dispatcher preserves pipeline/heredoc failures independently of caller context.
  bash -euo pipefail -c "$1"
}
export -f ensure_venv checkout_tag fetch_verified link_grafana docker_repository apt_release_version \
  docker_engine_packages docker_compose_package

# Planned. One function per input slot; duplicate research slot retains both owners.
claude-code() {
  # Claude Code | native-installer | planned
  # Planned. Source: https://raw.githubusercontent.com/anthropics/claude-code/v2.1.287/README.md#L23
  run_command 'curl -fsSL https://claude.ai/install.sh | bash' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/anthropics/claude-code/v2.1.287/README.md#L23
  run_command 'claude --version' || return "$?"
}

codex() {
  # Codex | native-installer | planned
  # Planned. Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/README.md#L19
  run_command 'curl -fsSL https://chatgpt.com/codex/install.sh | sh' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/README.md#L19
  run_command 'codex --version' || return "$?"
}

claude-agent-sdk() {
  # Claude Agent SDK | none | planned
  # Planned. Source: https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/v0.2.163/README.md#L5
  run_command 'ensure_venv "$tool_root/claude-agent-sdk"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/v0.2.163/README.md#L5
  run_command 'uv pip install --python "$tool_root/claude-agent-sdk/bin/python" claude-agent-sdk==0.2.163' || return "$?"
}

codex-sdk-and-codex-exec-app-server() {
  # Codex SDK and codex exec/app-server | none | planned
  # Planned. Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/sdk/typescript/README.md#L7
  run_command 'mkdir -p "$tool_root/codex-sdk"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/sdk/typescript/README.md#L7
  run_command '(cd "$tool_root/codex-sdk" && npm install @openai/codex-sdk@0.160.0)' || return "$?"
}

trail-of-bits-security-skills-trailofbits-skills() {
  # Trail of Bits security skills (trailofbits/skills) | none | planned
  # Planned. Source: https://raw.githubusercontent.com/trailofbits/skills/82fe8226252622fa807643bdca1710901198553a/README.md#L9
  run_command 'claude plugin marketplace add trailofbits/skills@82fe8226252622fa807643bdca1710901198553a' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/trailofbits/skills/82fe8226252622fa807643bdca1710901198553a/README.md#L9
  run_command 'codex plugin marketplace add trailofbits/skills --ref 82fe8226252622fa807643bdca1710901198553a' || return "$?"
}

mcporter() {
  # mcporter | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/openclaw/mcporter/v0.14.2/README.md#L28
  run_command 'npm install -g mcporter@0.14.2' || return "$?"
}

mcp-inspector() {
  # MCP Inspector | none | planned
  printf '%s\n' 'Excluded: run on demand with npx; mcporter owns MCP calls from scripts'
}

sandbox-runtime-srt() {
  # sandbox-runtime (srt) | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/anthropics/sandbox-runtime/v0.0.78/README.md#L14
  run_command 'npm install -g @anthropic-ai/sandbox-runtime@0.0.78' || return "$?"
}

isolation-container-boundary() {
  # No additional component: rootless containers on the container engine that the hosting layer installs | none | planned
  printf '%s\n' 'Excluded: '
}

serena() {
  # Serena | uv-tool | planned
  # Planned. Source: https://raw.githubusercontent.com/oraios/serena/v1.7.0/README.md#L229
  run_command 'uv tool install -p 3.13 serena-agent==1.7.0' || return "$?"
}

claude-plugins-official-code-intelligence-lsp-pl() {
  # claude-plugins-official (code-intelligence LSP plugins) | none | planned
  printf '%s\n' 'Excluded: Serena owns symbol navigation in both clients'
}

tobi-qmd() {
  # tobi/qmd | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L32
  run_command 'npm install -g @tobilu/qmd@2.8.3' || return "$?"
}

mineru() {
  # MinerU | uv-tool | planned
  # Planned. Source: https://raw.githubusercontent.com/opendatalab/mineru/mineru-4.0.10-released/README.md#L307
  run_command 'uv tool install --python 3.13 "mineru==4.0.10"' || return "$?"
}

trafilatura() {
  # trafilatura | uv-tool | planned
  # Planned. Source: https://raw.githubusercontent.com/adbar/trafilatura/v2.2.0/docs/installation.rst#L73
  run_command 'uv tool install --python 3.13 trafilatura==2.2.0' || return "$?"
}

playwright-cli() {
  # Playwright CLI | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/microsoft/playwright-cli/v0.1.22/README.md#L26
  run_command 'npm install -g @playwright/cli@0.1.22' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/microsoft/playwright/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/cli-client/program.ts#L346
  run_command 'playwright-cli install-browser --with-deps chromium' || return "$?"
}

ccusage() {
  # ccusage | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/ccusage/ccusage/v20.0.26/docs/guide/installation.md#L58
  run_command 'npm install -g ccusage@20.0.26' || return "$?"
}

context-supply() {
  # No context-supply layer: the usage meter only | none | planned
  printf '%s\n' 'Excluded: '
}

otel-collector-contrib() {
  # OTel Collector Contrib | release-binary | planned
  # Planned. Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/9f912d59a165ded5dec82d0e1a94c2aef54e5c57/content/en/docs/collector/install/binary/linux.md#L87
  run_command 'fetch_verified '\''https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.162.0/otelcol-contrib_0.162.0_linux_amd64.tar.gz'\'' '\''fcc063749f730f8c21fe29f2d340ff174f5f1c5885bd3156fb6c985a3036fcc3'\'' "$tool_root/otel-collector-contrib/otelcol-contrib_0.162.0_linux_amd64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/9f912d59a165ded5dec82d0e1a94c2aef54e5c57/content/en/docs/collector/install/binary/linux.md#L87
  run_command '(cd "$tool_root/otel-collector-contrib" && tar -xvf '\''otelcol-contrib_0.162.0_linux_amd64.tar.gz'\'')' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/9f912d59a165ded5dec82d0e1a94c2aef54e5c57/content/en/docs/collector/install/binary/linux.md#L87
  run_command 'install -m 0755 "$tool_root/otel-collector-contrib/otelcol-contrib" "$HOME/.local/bin/otelcol-contrib"' || return "$?"
  copy_config 'otel.yaml' || return "$?"
}

prometheus() {
  # Prometheus | release-binary | planned
  # Planned. Source: https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/getting_started.md#L18
  run_command 'fetch_verified '\''https://github.com/prometheus/prometheus/releases/download/v3.15.0/prometheus-3.15.0.linux-amd64.tar.gz'\'' '\''2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0'\'' "$tool_root/prometheus/prometheus-3.15.0.linux-amd64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/getting_started.md#L18
  run_command '(cd "$tool_root/prometheus" && tar xvfz '\''prometheus-3.15.0.linux-amd64.tar.gz'\'')' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/getting_started.md#L18
  run_command 'install -m 0755 "$tool_root/prometheus/prometheus-3.15.0.linux-amd64/prometheus" "$HOME/.local/bin/prometheus"' || return "$?"
  copy_config 'prometheus.yaml' || return "$?"
}

loki() {
  # Loki | release-binary | planned
  # Planned. Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24
  run_command 'fetch_verified '\''https://github.com/grafana/loki/releases/download/v3.7.8/loki-linux-amd64.zip'\'' '\''62aea42c9cba52cd1642b3666ab37019a0ce4c24ab50b07e85dccc8d812f7d61'\'' "$tool_root/loki/loki-linux-amd64.zip"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24
  run_command '(cd "$tool_root/loki" && unzip -o '\''loki-linux-amd64.zip'\'')' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24
  run_command 'install -m 0755 "$tool_root/loki/loki-linux-amd64" "$HOME/.local/bin/loki"' || return "$?"
  copy_config 'loki.yaml' || return "$?"
}

grafana() {
  # Grafana | release-binary | planned
  # Planned. Source: https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux
  run_command 'fetch_verified '\''https://dl.grafana.com/grafana/release/13.2.3/grafana_13.2.3_36482603486_linux_amd64.tar.gz'\'' '\''6107ad27016296aac38e0d7ffa8753ab540b5541ad27e94790f771289d733235'\'' "$tool_root/grafana/grafana_13.2.3_36482603486_linux_amd64.tar.gz"' || return "$?"
  # Planned. Source: https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux
  run_command '(cd "$tool_root/grafana" && tar -zxvf '\''grafana_13.2.3_36482603486_linux_amd64.tar.gz'\'')' || return "$?"
  # Planned. Source: https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux
  run_command 'link_grafana' || return "$?"
  copy_config 'grafana.ini' || return "$?"
}

phoenix() {
  # Phoenix | compose | planned
  # Planned. Source: https://raw.githubusercontent.com/Arize-ai/phoenix/arize-phoenix-v20.19.0/docs/phoenix/self-hosting/deployment-options/docker.mdx#L156
  run_command 'docker compose -f "$plan_dir/config/phoenix-compose.yaml" up -d' || return "$?"
}

local-model-server() {
  # Ollama | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/ollama.toml#L1
  run_command 'mise use -g ollama@0.35.0' || return "$?"
  refresh_path || return "$?"
  copy_config 'ollama.env.example' || return "$?"
}

inspect-ai() {
  # Inspect AI | uv-tool | planned
  # Planned. Source: https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/0.3.273/docs/index.qmd#L38
  run_command 'uv tool install --python 3.13 inspect-ai==0.3.273' || return "$?"
}

harbor-containerized-agent-e2e-runner() {
  # Harbor (containerized agent E2E runner) | uv-tool | planned
  # Planned. Source: https://raw.githubusercontent.com/harbor-framework/harbor/v0.23.0/README.md#L22
  run_command 'uv tool install --python 3.13 harbor==0.23.0' || return "$?"
}

promptfoo() {
  # Promptfoo | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/promptfoo/promptfoo/0.123.1/README.md#L31
  run_command 'npm install -g promptfoo@0.123.1' || return "$?"
}

zizmor() {
  # zizmor | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/zizmor.toml#L1
  run_command 'mise use -g zizmor@1.30.1' || return "$?"
  refresh_path || return "$?"
}

attest() {
  # attest | github-action | planned
  printf '%s\n' 'UNRUN. uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6. No host installation/acceptance command. Workflows require repository/artifact configuration.  Recipe/source: https://raw.githubusercontent.com/actions/attest/1e69f48acb82d1966a394da916b4c1698aa569d6/README.md#L80'
}

syft() {
  # Syft | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/syft.toml#L1
  run_command 'mise use -g syft@1.54.0' || return "$?"
  refresh_path || return "$?"
}

dependabot() {
  # Dependabot | github-action | planned
  printf '%s\n' 'UNRUN. Tag resolves to a1750051287d1f3786081d3aa3e6e2b04a72edde. No valid uses: reference: upstream repository has no action entrypoint. Enable GitHub Dependabot through .github/dependabot.yml; no host installation. Recipe/source: https://raw.githubusercontent.com/dependabot/dependabot-core/a1750051287d1f3786081d3aa3e6e2b04a72edde/README.md#L42'
}

codeql-sarif() {
  # codeql-sarif | github-action | planned
  printf '%s\n' 'UNRUN. uses: github/codeql-action/upload-sarif@416ff0dea110f80f0f56f0046500dbf7420e4bb0. No host installation/acceptance command. Workflows require repository/artifact configuration. Root action is a deliberate failure stub; use upload-sarif. Recipe/source: https://raw.githubusercontent.com/github/codeql-action/416ff0dea110f80f0f56f0046500dbf7420e4bb0/upload-sarif/action.yml#L1'
}

actionlint-kjanat() {
  # actionlint (kjanat) | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/kjanat/actionlint/v1.17.0/docs/install.md#L223
  run_command 'mise use -g github:kjanat/actionlint@1.17.0' || return "$?"
  refresh_path || return "$?"
}

dagu() {
  # Dagu | native-installer | planned
  # Planned. Source: https://raw.githubusercontent.com/dagucloud/dagu/v2.18.1/README.md#L105
  run_command 'curl -fsSL https://raw.githubusercontent.com/dagucloud/dagu/v2.18.1/scripts/installer.sh | bash -s -- --version v2.18.1 --no-prompt --service yes --service-scope user --host 127.0.0.1 --port 21080 --open-browser no' || return "$?"
}

docker-compose() {
  # Docker Compose | apt-repo | planned
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/f0e4e4790191aaee83f9375dce56ada3971c6773/content/manuals/compose/install/linux.md#L38
  run_command 'docker_repository' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/f0e4e4790191aaee83f9375dce56ada3971c6773/content/manuals/compose/install/linux.md#L38
  run_command 'docker_compose_package' || return "$?"
}

container-engine() {
  # Docker Engine / Moby | apt-repo | planned
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/dd2797b84208848765705a1518aeee7e47907bd7/content/manuals/engine/install/ubuntu.md#L122
  run_command 'docker_repository' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/dd2797b84208848765705a1518aeee7e47907bd7/content/manuals/engine/install/ubuntu.md#L122
  run_command 'docker_engine_packages' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/dd2797b84208848765705a1518aeee7e47907bd7/content/manuals/engine/install/ubuntu.md#L122
  run_command 'sudo systemctl disable --now docker.service docker.socket' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/dd2797b84208848765705a1518aeee7e47907bd7/content/manuals/engine/install/ubuntu.md#L122
  run_command 'if [[ ! -f "$HOME/.config/systemd/user/docker.service" ]]; then dockerd-rootless-setuptool.sh install; fi' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/docker/docs/dd2797b84208848765705a1518aeee7e47907bd7/content/manuals/engine/install/ubuntu.md#L122
  run_command 'systemctl --user enable --now docker.service' || return "$?"
}

betterleaks() {
  # betterleaks | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/betterleaks.toml#L1
  run_command 'mise use -g betterleaks@1.9.0' || return "$?"
  refresh_path || return "$?"
}

trufflehog() {
  # trufflehog | none | planned
  printf '%s\n' 'Excluded: betterleaks owns secret scanning'
}

git() {
  # Ubuntu-managed Git | apt | planned; base/prerequisite packages already supply it.
  # Source: https://raw.githubusercontent.com/git/git-scm.com/422e163b96cdcff929cd63028657597752d4b9d7/content/install/linux.html#L19
  run_command 'sudo apt-get install -y --no-install-recommends git' || return "$?"
}

gh-github-cli() {
  # gh (GitHub CLI) | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/github-cli.toml#L1
  run_command 'mise use -g github-cli@2.102.0' || return "$?"
  refresh_path || return "$?"
}

worktrunk() {
  # worktrunk | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/worktrunk.toml#L1
  run_command 'mise use -g worktrunk@0.80.0' || return "$?"
  refresh_path || return "$?"
}

difftastic() {
  # difftastic | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/difftastic.toml#L1
  run_command 'mise use -g difftastic@0.71.0' || return "$?"
  refresh_path || return "$?"
}

claude-code-action() {
  # claude-code-action | github-action | planned
  printf '%s\n' 'UNRUN. uses: anthropics/claude-code-action@97c53473391bff1901034d4b454b5bac7ab7a029. No host installation/acceptance command. Workflows require repository/artifact configuration.  Recipe/source: https://raw.githubusercontent.com/anthropics/claude-code-action/97c53473391bff1901034d4b454b5bac7ab7a029/docs/usage.md#L17'
}

agent-structural-diff() {
  # Not installed: git diff and difftastic cover diffs | none | planned
  printf '%s\n' 'Excluded: '
}

mise() {
  # mise | native-installer | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/docs/installing-mise.md#L82
  run_command 'curl -fsSL https://mise.run | MISE_VERSION=v2026.10.0 sh' || return "$?"
}

restic() {
  # Restic | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/restic.toml#L1
  run_command 'mise use -g restic@0.19.1' || return "$?"
  refresh_path || return "$?"
}

chezmoi() {
  # chezmoi | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/twpayne/chezmoi/v2.73.0/assets/chezmoi.io/docs/install.md.tmpl#L137
  run_command 'mise use -g chezmoi@2.73.0' || return "$?"
  refresh_path || return "$?"
}

base-distribution() {
  # Ubuntu 26.04.1 LTS (Canonical WSL image), primary | none | planned
  printf '%s\n' 'Excluded: '
}

gpt-gateway() {
  # OmniRoute | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/diegosouzapw/OmniRoute/v3.8.51/README.md#L1005
  run_command 'npm install -g omniroute@3.8.51' || return "$?"
  copy_config 'omniroute.env.example' || return "$?"
}

agent-runtime-worker() {
  # OpenHands software-agent-sdk | none | planned
  # Planned. Source: https://raw.githubusercontent.com/OpenHands/docs/832ad1635431c7711cbfdc9d1f52c2dab9ee7e61/sdk/getting-started.mdx#L80
  run_command 'checkout_tag https://github.com/OpenHands/software-agent-sdk.git v1.50.1 "$tool_root/openhands-source"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/OpenHands/docs/832ad1635431c7711cbfdc9d1f52c2dab9ee7e61/sdk/getting-started.mdx#L80
  run_command 'ensure_venv "$tool_root/agent-runtime-worker"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/OpenHands/docs/832ad1635431c7711cbfdc9d1f52c2dab9ee7e61/sdk/getting-started.mdx#L80
  run_command 'uv pip install --python "$tool_root/agent-runtime-worker/bin/python" "openhands-sdk==1.50.1" "openhands-tools==1.50.1"' || return "$?"
}

research-gpt-researcher() {
  # GPT Researcher and DeerFlow, kept as two independent evidence gatherers | none | planned
  # Planned. Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/v3.7.0/README.md#L99
  run_command 'checkout_tag https://github.com/assafelovic/gpt-researcher.git v3.7.0 "$tool_root/gpt-researcher"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/v3.7.0/README.md#L99
  run_command 'ensure_venv "$tool_root/gpt-researcher/.venv"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/assafelovic/gpt-researcher/v3.7.0/README.md#L99
  run_command '(cd "$tool_root/gpt-researcher" && uv pip install --python .venv/bin/python -r requirements.txt)' || return "$?"
}

research-deer-flow() {
  # GPT Researcher and DeerFlow, kept as two independent evidence gatherers | compose | planned
  # Planned. Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Install.md#L38
  run_command 'checkout_tag https://github.com/bytedance/deer-flow.git v2.1.0 "$tool_root/deer-flow"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Install.md#L38
  run_command '(cd "$tool_root/deer-flow" && if [[ ! -e config.yaml && ! -e .env && ! -e frontend/.env ]]; then make config; elif [[ ! -e config.yaml || ! -e .env || ! -e frontend/.env ]]; then printf "Partial DeerFlow config; repair from upstream recipe.\n" >&2; exit 1; fi)' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Install.md#L38
  run_command '(cd "$tool_root/deer-flow" && make docker-init)' || return "$?"
}

research-harnesses() {
  # Planned. Keep both independent owners even when one installation fails.
  local status=0
  if research-gpt-researcher; then :; else status=1; fi
  if research-deer-flow; then :; else status=1; fi
  return "$status"
}

credential-guard() {
  # Command and secret-path guard (K4) | repository-recipe | planned
  printf '%s\n' 'UNRUN. Follow adoption/bootstrap.md step 4a guard hooks and settings. No new install command. Recipe source is this checkout commit; selected release metadata retained. No isolated upstream smoke/version command for the combined practice. Recipe/source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/8b51946ee16e542e544936e19bb793114fea948e/adoption/bootstrap.md#L400'
}

convergence-validators() {
  # Convergence practice and its validators | repository-recipe | planned
  printf '%s\n' 'UNRUN. Adoption recipe, no new install command. Check verifies repository evidence, not host installation. Scoped convergence experiments require their own records; not generated for this source-only install inventory. Recipe/source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/8b51946ee16e542e544936e19bb793114fea948e/adoption/README.md#L58'
}

if $list; then
  printf '%s\n' 'claude-code | Claude Code | native-installer | planned'
  printf '%s\n' 'codex | Codex | native-installer | planned'
  printf '%s\n' 'claude-agent-sdk | Claude Agent SDK | none | planned'
  printf '%s\n' 'codex-sdk-and-codex-exec-app-server | Codex SDK and codex exec/app-server | none | planned'
  printf '%s\n' 'trail-of-bits-security-skills-trailofbits-skills | Trail of Bits security skills (trailofbits/skills) | none | planned'
  printf '%s\n' 'mcporter | mcporter | npm-global | planned'
  printf '%s\n' 'mcp-inspector | MCP Inspector | none | excluded: run on demand with npx; mcporter owns MCP calls from scripts'
  printf '%s\n' 'sandbox-runtime-srt | sandbox-runtime (srt) | npm-global | planned'
  printf '%s\n' 'isolation-container-boundary | No additional component: rootless containers on the container engine that the hosting layer installs | none | excluded: '
  printf '%s\n' 'serena | Serena | uv-tool | planned'
  printf '%s\n' 'claude-plugins-official-code-intelligence-lsp-pl | claude-plugins-official (code-intelligence LSP plugins) | none | excluded: Serena owns symbol navigation in both clients'
  printf '%s\n' 'tobi-qmd | tobi/qmd | npm-global | planned'
  printf '%s\n' 'mineru | MinerU | uv-tool | planned'
  printf '%s\n' 'trafilatura | trafilatura | uv-tool | planned'
  printf '%s\n' 'playwright-cli | Playwright CLI | npm-global | planned'
  printf '%s\n' 'ccusage | ccusage | npm-global | planned'
  printf '%s\n' 'context-supply | No context-supply layer: the usage meter only | none | excluded: '
  printf '%s\n' 'otel-collector-contrib | OTel Collector Contrib | release-binary | planned'
  printf '%s\n' 'prometheus | Prometheus | release-binary | planned'
  printf '%s\n' 'loki | Loki | release-binary | planned'
  printf '%s\n' 'grafana | Grafana | release-binary | planned'
  printf '%s\n' 'phoenix | Phoenix | compose | planned'
  printf '%s\n' 'local-model-server | Ollama | mise | planned'
  printf '%s\n' 'inspect-ai | Inspect AI | uv-tool | planned'
  printf '%s\n' 'harbor-containerized-agent-e2e-runner | Harbor (containerized agent E2E runner) | uv-tool | planned'
  printf '%s\n' 'promptfoo | Promptfoo | npm-global | planned'
  printf '%s\n' 'zizmor | zizmor | mise | planned'
  printf '%s\n' 'attest | attest | github-action | planned'
  printf '%s\n' 'syft | Syft | mise | planned'
  printf '%s\n' 'dependabot | Dependabot | github-action | planned'
  printf '%s\n' 'codeql-sarif | codeql-sarif | github-action | planned'
  printf '%s\n' 'actionlint-kjanat | actionlint (kjanat) | mise | planned'
  printf '%s\n' 'dagu | Dagu | native-installer | planned'
  printf '%s\n' 'docker-compose | Docker Compose | apt-repo | planned'
  printf '%s\n' 'container-engine | Docker Engine / Moby | apt-repo | planned'
  printf '%s\n' 'betterleaks | betterleaks | mise | planned'
  printf '%s\n' 'trufflehog | trufflehog | none | excluded: betterleaks owns secret scanning'
  printf '%s\n' 'git | git | apt | planned'
  printf '%s\n' 'gh-github-cli | gh (GitHub CLI) | mise | planned'
  printf '%s\n' 'worktrunk | worktrunk | mise | planned'
  printf '%s\n' 'difftastic | difftastic | mise | planned'
  printf '%s\n' 'claude-code-action | claude-code-action | github-action | planned'
  printf '%s\n' 'agent-structural-diff | Not installed: git diff and difftastic cover diffs | none | excluded: '
  printf '%s\n' 'mise | mise | native-installer | planned'
  printf '%s\n' 'restic | Restic | mise | planned'
  printf '%s\n' 'chezmoi | chezmoi | mise | planned'
  printf '%s\n' 'base-distribution | Ubuntu 26.04.1 LTS (Canonical WSL image), primary | none | excluded: '
  printf '%s\n' 'gpt-gateway | OmniRoute | npm-global | planned'
  printf '%s\n' 'agent-runtime-worker | OpenHands software-agent-sdk | none | planned'
  printf '%s\n' 'research-harnesses | GPT Researcher and DeerFlow, kept as two independent evidence gatherers | none | planned'
  printf '%s\n' 'research-harnesses | GPT Researcher and DeerFlow, kept as two independent evidence gatherers | compose | planned'
  printf '%s\n' 'credential-guard | Command and secret-path guard (K4) | repository-recipe | planned'
  printf '%s\n' 'convergence-validators | Convergence practice and its validators | repository-recipe | planned'
  exit 0
fi
case "$only" in
  ''|claude-code|codex|claude-agent-sdk|codex-sdk-and-codex-exec-app-server|trail-of-bits-security-skills-trailofbits-skills|mcporter|mcp-inspector|sandbox-runtime-srt|isolation-container-boundary|serena|claude-plugins-official-code-intelligence-lsp-pl|tobi-qmd|mineru|trafilatura|playwright-cli|ccusage|context-supply|otel-collector-contrib|prometheus|loki|grafana|phoenix|local-model-server|inspect-ai|harbor-containerized-agent-e2e-runner|promptfoo|zizmor|attest|syft|dependabot|codeql-sarif|actionlint-kjanat|dagu|docker-compose|container-engine|betterleaks|trufflehog|git|gh-github-cli|worktrunk|difftastic|claude-code-action|agent-structural-diff|mise|restic|chezmoi|base-distribution|gpt-gateway|agent-runtime-worker|research-harnesses|credential-guard|convergence-validators) ;;
  *) printf 'Unknown slot: %s\n' "$only" >&2; exit 2 ;;
esac

# Planned. Package prerequisites, then mise/runtimes, user CLIs, containers, services.
needs_execution=false
needs_runtime=false
needs_docker=false
for slot in 'claude-code' 'codex' 'claude-agent-sdk' 'codex-sdk-and-codex-exec-app-server' 'trail-of-bits-security-skills-trailofbits-skills' 'mcporter' 'sandbox-runtime-srt' 'serena' 'tobi-qmd' 'mineru' 'trafilatura' 'playwright-cli' 'ccusage' 'otel-collector-contrib' 'prometheus' 'loki' 'grafana' 'phoenix' 'local-model-server' 'inspect-ai' 'harbor-containerized-agent-e2e-runner' 'promptfoo' 'zizmor' 'syft' 'actionlint-kjanat' 'dagu' 'docker-compose' 'container-engine' 'betterleaks' 'git' 'gh-github-cli' 'worktrunk' 'difftastic' 'mise' 'restic' 'chezmoi' 'gpt-gateway' 'agent-runtime-worker' 'research-harnesses'; do selected "$slot" && needs_execution=true; done
for slot in 'claude-agent-sdk' 'codex-sdk-and-codex-exec-app-server' 'trail-of-bits-security-skills-trailofbits-skills' 'mcporter' 'sandbox-runtime-srt' 'serena' 'tobi-qmd' 'mineru' 'trafilatura' 'playwright-cli' 'ccusage' 'local-model-server' 'inspect-ai' 'harbor-containerized-agent-e2e-runner' 'promptfoo' 'zizmor' 'syft' 'actionlint-kjanat' 'betterleaks' 'gh-github-cli' 'worktrunk' 'difftastic' 'restic' 'chezmoi' 'gpt-gateway' 'agent-runtime-worker' 'research-harnesses'; do selected "$slot" && needs_runtime=true; done
for slot in 'phoenix' 'harbor-containerized-agent-e2e-runner' 'docker-compose' 'research-harnesses'; do selected "$slot" && needs_docker=true; done

if $needs_execution; then
  # Planned. Repository bootstrap-linux.sh:206-216; selected owner prereqs extend its package list.
  packages=(ca-certificates curl git tar gzip xz-utils jq)
  if selected research-harnesses; then packages+=(make); fi
  if selected sandbox-runtime-srt; then packages+=(bubblewrap socat ripgrep gcc libseccomp-dev); fi
  if selected loki; then packages+=(unzip); fi
  if $needs_docker || selected container-engine; then packages+=(uidmap dbus-user-session); fi
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends "${packages[@]}"
  mkdir -p -- "$HOME/.local/bin" "$tool_root" "$config_root"
fi
if $needs_runtime || selected mise; then
  # Planned. mise installer owns its release; runtime pins are upstream tag selections.
  mise
  run_command 'mise use -g node@24.21.0'
  run_command 'mise use -g python@3.13.16'
  run_command 'mise use -g uv@0.12.22'
  refresh_path
fi
failed=0
run_slot() {
  local slot="$1" rc=0
  if "$slot"; then rc=0; else rc=$?; failed=1; fi
  last_rc="$rc"
  printf '%s | install | %s\n' "$slot" "$rc"
}
# Planned. Selective installs include the native clients required by their integration.
if [[ "$only" == trail-of-bits-security-skills-trailofbits-skills ]]; then
  run_slot claude-code
  run_slot codex
fi
if [[ "$only" == codex-sdk-and-codex-exec-app-server ]]; then run_slot codex; fi
if selected 'claude-code'; then run_slot 'claude-code'; fi
if selected 'codex'; then run_slot 'codex'; fi
if selected 'claude-agent-sdk'; then run_slot 'claude-agent-sdk'; fi
if selected 'codex-sdk-and-codex-exec-app-server'; then run_slot 'codex-sdk-and-codex-exec-app-server'; fi
if selected 'trail-of-bits-security-skills-trailofbits-skills'; then run_slot 'trail-of-bits-security-skills-trailofbits-skills'; fi
if selected 'mcporter'; then run_slot 'mcporter'; fi
if selected 'sandbox-runtime-srt'; then run_slot 'sandbox-runtime-srt'; fi
if selected 'serena'; then run_slot 'serena'; fi
if selected 'tobi-qmd'; then run_slot 'tobi-qmd'; fi
if selected 'mineru'; then run_slot 'mineru'; fi
if selected 'trafilatura'; then run_slot 'trafilatura'; fi
if selected 'playwright-cli'; then run_slot 'playwright-cli'; fi
if selected 'ccusage'; then run_slot 'ccusage'; fi
if selected 'inspect-ai'; then run_slot 'inspect-ai'; fi
if selected 'harbor-containerized-agent-e2e-runner'; then run_slot 'harbor-containerized-agent-e2e-runner'; fi
if selected 'promptfoo'; then run_slot 'promptfoo'; fi
if selected 'zizmor'; then run_slot 'zizmor'; fi
if selected 'attest'; then run_slot 'attest'; fi
if selected 'syft'; then run_slot 'syft'; fi
if selected 'dependabot'; then run_slot 'dependabot'; fi
if selected 'codeql-sarif'; then run_slot 'codeql-sarif'; fi
if selected 'actionlint-kjanat'; then run_slot 'actionlint-kjanat'; fi
if selected 'betterleaks'; then run_slot 'betterleaks'; fi
if selected 'git'; then run_slot 'git'; fi
if selected 'gh-github-cli'; then run_slot 'gh-github-cli'; fi
if selected 'worktrunk'; then run_slot 'worktrunk'; fi
if selected 'difftastic'; then run_slot 'difftastic'; fi
if selected 'claude-code-action'; then run_slot 'claude-code-action'; fi
if selected 'restic'; then run_slot 'restic'; fi
if selected 'chezmoi'; then run_slot 'chezmoi'; fi
if selected 'agent-runtime-worker'; then run_slot 'agent-runtime-worker'; fi
if selected 'credential-guard'; then run_slot 'credential-guard'; fi
if selected 'convergence-validators'; then run_slot 'convergence-validators'; fi

if $needs_docker || selected container-engine; then
  run_slot container-engine
  if (( last_rc != 0 )); then
    printf 'Rootless Docker prerequisites failed; refusing container/service stages.\n' >&2
    exit 1
  fi
  : "${XDG_RUNTIME_DIR:?systemd user runtime directory is required for rootless Docker}"
  export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
fi
if $needs_docker || selected docker-compose; then run_slot docker-compose; fi
if selected 'otel-collector-contrib'; then run_slot 'otel-collector-contrib'; fi
if selected 'prometheus'; then run_slot 'prometheus'; fi
if selected 'loki'; then run_slot 'loki'; fi
if selected 'grafana'; then run_slot 'grafana'; fi
if selected 'phoenix'; then run_slot 'phoenix'; fi
if selected 'local-model-server'; then run_slot 'local-model-server'; fi
if selected 'dagu'; then run_slot 'dagu'; fi
if selected 'gpt-gateway'; then run_slot 'gpt-gateway'; fi
if selected 'research-harnesses'; then run_slot 'research-harnesses'; fi
exit "$failed"
