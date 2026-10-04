#!/usr/bin/env bash
# Revised to the merged definitive manifest (64 foundation rows) and after the real-distribution run of the previous revision.
# This revision ran once, on 2026-10-02, in a throwaway distribution (real-distribution-validation.json), and later that day, as merged to
# main (6652b78e), once on the destination distribution; the record of that run is private, and its public receipt comes with that
# distribution's acceptance.
# Five rows were added after the throwaway run, from the layer consensus of 2026-10-02 (69 foundation rows). The commands of skill-discovery
# and skill-authoring have not run anywhere; research-skill, credential-custody and cross-family-review install nothing.
# On 2026-10-03 the two local-model rows (local-generation-model, embedding-model) became installable after their measurement.
# They create their models through the running model server, so they install only with --only; as plan rows they have not run.
# Wave 2 (2026-10-03): memory-owner, code-search and context-supply install as interim installs (amendment 3 of the
# manifest's decision rule), statusline is added, and research-harnesses, tobi-qmd and gpt-gateway are revised; none of
# these has run anywhere.
# Wave 3 (2026-10-04, the owner's decision, amendment 4): ten token-efficiency owner rows are added, ccusage and
# session-analytics install their owner defaults, context-supply installs without the interim gate, and code-search
# adds SocratiCode; none of these has run anywhere.
# Baseline results and limitations: VALIDATION.md.
# Upstream command quotations and parameterizations: install-plan.json and SOURCES.md. Consistency check: check_plan.py.
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
# Planned. Slots the merged manifest leaves split install only when named: the deciding measurement installs them on purpose.
named() { [[ "$only" == "$1" ]]; }
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
interim_acknowledged() {
  # Planned. The gate of amendment 3 of the manifest's decision rule (the wave-2 code-search ruling, change 1: until
  # both families have acknowledged the rule amendment on the pull request, nothing is installed). An interim row's
  # install function calls this first; check_plan.py requires the call. It reads every batch of the layer consensus
  # (wave2, wave3, ...) and refuses while any of them owes an acknowledgement, or when one cannot be read, a key that
  # starts with wave is not wave<n> (the assembler refuses such a key too), or there is none
  # (docs/decisions/2026-10-02-new-wsl-layer-consensus.md, section Wave 2); an owner batch (amendment 4) owes none.
  local consensus="$repo_root/evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json" owed
  owed="$(jq -r '[to_entries[] | select(.key | startswith("wave"))] | if length == 0 then error("no wave batch") elif any(.[]; .key | test("^wave[0-9]+$") | not) then error("a batch is named wave<n>") else . end | map(.key as $batch | .value.acknowledgements_owed | if type == "array" and all(.[]; type == "string" and length > 0) then (if length > 0 then "\($batch): \(join(", "))" else empty end) else error("not a list of names") end) | join("; ")' "$consensus")" || {
    printf '%s: refused: the acknowledgements of the wave batches cannot be read from %s\n' "$1" "$consensus" >&2
    return 1
  }
  if [[ -n "$owed" ]]; then
    printf '%s: refused: an interim install waits for the acknowledgements still owed by the wave batches: %s (%s)\n' \
      "$1" "$owed" "$consensus" >&2
    return 1
  fi
}
model_server_answers() {
  # Planned. The two model rows create their models through the running model server; this plan starts no service (README.md).
  if ! OLLAMA_HOST=127.0.0.1:21434 ollama ls >/dev/null 2>&1; then
    printf 'The model server does not answer on 127.0.0.1:21434: start it (README.md, "The two local-model rows"), then run this row again.\n' >&2
    return 1
  fi
  # Planned. Both rows install what was measured on Ollama 0.35.0, so nothing is pulled or created unless the server that
  # answers reports that version; GET /api/version answers the running server's own version (server/routes.go:2023).
  # Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1824
  local version
  version="$(curl -fsS http://127.0.0.1:21434/api/version | jq -r '.version')" || version=''
  if [[ "$version" != 0.35.0 ]]; then
    printf 'The model server on 127.0.0.1:21434 reports version %s, not 0.35.0, the version both model rows were measured on: run the local-model-server row'\''s Ollama 0.35.0 there, then run this row again.\n' "${version:-unknown}" >&2
    return 1
  fi
}
export -f ensure_venv checkout_tag fetch_verified link_grafana docker_repository apt_release_version \
  docker_engine_packages docker_compose_package

# Planned. One function per installed or measurement-only slot; the research slot retains both owners under one dispatcher.
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
  # Planned. Source: https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/scripts/install/install.sh#L100 (CODEX_NON_INTERACTIVE skips the prompt that hangs on a terminal)
  run_command 'curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh' || return "$?"
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
  # Planned. Source: https://raw.githubusercontent.com/trailofbits/skills/82fe8226252622fa807643bdca1710901198553a/README.md#L12
  # Planned. Source: https://code.claude.com/docs/en/plugins/cli-reference.md#L649 (full https clone URL; no pin: the client takes a branch or tag after #, and this repository has no tag)
  run_command 'claude plugin marketplace add https://github.com/trailofbits/skills.git' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/trailofbits/skills/82fe8226252622fa807643bdca1710901198553a/README.md#L28
  run_command 'codex plugin marketplace add trailofbits/skills --ref 82fe8226252622fa807643bdca1710901198553a' || return "$?"
}

engineering-process-skills() {
  # mattpocock/skills (selected skills, not the bundle) | none | planned
  # UNRUN on every distribution: revised from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L20 (the skills CLI is the npm package skills); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix)
  run_command 'npm install --global --prefix "$tool_root/skills-1.7.0" skills@1.7.0' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L44 (add from a tree URL, the form the installer runs); https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L111 (non-interactive flags)
  # The repository's installer over adoption/skills/manifest.json (wave-2 skills ruling, change 7).
  run_command 'python3 -B "$repo_root/tools/adoption/install_skills.py" --skills-bin "$tool_root/skills-1.7.0/bin/skills" --json' || return "$?"
}

skill-discovery() {
  # find-skills (vercel-labs/skills) | none | planned
  # UNRUN on every distribution: revised from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L20 (the skills CLI is the npm package skills); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix)
  run_command 'npm install --global --prefix "$tool_root/skills-1.7.0" skills@1.7.0' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L44 (add from a tree URL); https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L89 (one named skill)
  run_command 'python3 -B "$repo_root/tools/adoption/install_skills.py" --skills-bin "$tool_root/skills-1.7.0/bin/skills" --json --only find-skills' || return "$?"
}

skill-authoring() {
  # skill-creator (embedded in Codex; anthropics/skills for Claude Code) | none | planned
  # UNRUN on every distribution: revised from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # For Claude Code only. Nothing is installed for Codex, which embeds its own skill-creator, and --copy keeps a same-name copy out of the shared $HOME/.agents/skills.
  # Planned. Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L20 (the skills CLI is the npm package skills); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix)
  run_command 'npm install --global --prefix "$tool_root/skills-1.7.0" skills@1.7.0' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L91 (--copy), https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L89 (one named skill); the manifest entry is a copy for Claude Code only
  run_command 'python3 -B "$repo_root/tools/adoption/install_skills.py" --skills-bin "$tool_root/skills-1.7.0/bin/skills" --json --only skill-creator' || return "$?"
}

mcporter() {
  # mcporter | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/openclaw/mcporter/v0.14.2/README.md#L28
  run_command 'npm install -g mcporter@0.14.2' || return "$?"
}

sandbox-runtime-srt() {
  # sandbox-runtime (srt) | npm-global | planned
  # Planned. Source: https://raw.githubusercontent.com/anthropics/sandbox-runtime/v0.0.78/README.md#L14
  run_command 'npm install -g @anthropic-ai/sandbox-runtime@0.0.78' || return "$?"
}

serena() {
  # Serena | uv-tool | planned
  # Planned. Source: https://raw.githubusercontent.com/oraios/serena/v1.7.0/README.md#L229
  run_command 'uv tool install -p 3.13 serena-agent==1.7.0' || return "$?"
}

structural-search() {
  # ast-grep | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/ast-grep.toml#L1
  run_command 'mise use -g ast-grep@0.45.3' || return "$?"
  refresh_path || return "$?"
}

embedding-model() {
  # Qwen3-Embedding-0.6B through Ollama (qwen3-embedding:0.6b, Q8_0, as qwen3-embedding-8k, context 8,192) | model-server | planned
  refresh_path || return "$?"
  model_server_answers || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/cli.mdx#L85
  run_command 'OLLAMA_HOST=127.0.0.1:21434 ollama pull qwen3-embedding:0.6b' || return "$?"
  # Planned. The pin: the library manifest's digest as the server reports it (server/model_list.go:64).
  # Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1351
  run_command 'curl -fsS http://127.0.0.1:21434/api/tags | jq -e '\''.models[] | select(.name == "qwen3-embedding:0.6b") | .digest == "ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d"'\'' >/dev/null' || return "$?"
  # Planned. The context belongs to the model, never to the server (models/qwen3-embedding-8k.Modelfile).
  # Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L2422
  run_command 'OLLAMA_HOST=127.0.0.1:21434 ollama create qwen3-embedding-8k -f "$plan_dir/models/qwen3-embedding-8k.Modelfile"' || return "$?"
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

playwright-cli() {
  # Playwright CLI | npm-global | measurement-only
  # Planned. Source: https://raw.githubusercontent.com/microsoft/playwright-cli/v0.1.22/README.md#L26
  run_command 'npm install -g @playwright/cli@0.1.22' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/microsoft/playwright/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/cli-client/program.ts#L346
  run_command 'playwright-cli install-browser --with-deps chromium' || return "$?"
}

memory-owner() {
  # ai-memory 2.5.2 | release-binary | planned
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # Planned. An interim install (amendment 3): refused while an acknowledgement of the wave-2 batch is owed.
  interim_acknowledged memory-owner || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L1634 (the release archive and its .sha256 sidecar; the digest is the wave-2 memory dossier's)
  run_command 'fetch_verified https://github.com/akitaonrails/ai-memory/releases/download/v2.5.2/ai-memory-linux-x86_64.tar.gz acbf6ee84e744a9ab0a8e133a3eefbbb77811d6b4d0ca9a281e664358c1a1fc8 "$HOME/.local/opt/ai-memory-2.5.2/ai-memory-linux-x86_64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L1636 (extract and put ai-memory on PATH; the archive's hooks/ stay beside the binary)
  run_command 'tar -xzf "$HOME/.local/opt/ai-memory-2.5.2/ai-memory-linux-x86_64.tar.gz" -C "$HOME/.local/opt/ai-memory-2.5.2" && ln -sfn "$HOME/.local/opt/ai-memory-2.5.2/ai-memory" "$HOME/.local/bin/ai-memory"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L254 (user-level config and data layout)
  run_command 'if [[ ! -e "$HOME/.config/ai-memory/config.toml" ]]; then mkdir -p "$HOME/.config/ai-memory" "$HOME/.local/share/ai-memory" && ai-memory --data-dir "$HOME/.local/share/ai-memory" --config "$HOME/.config/ai-memory/config.toml" init; fi' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/templates/config.default.toml#L10 (bind; embedding_provider at L99-106); port 29374 per the wave-2 synthesis X5
  run_command 'f="$HOME/.config/ai-memory/config.toml"; if grep -qx '\''bind = "127.0.0.1:49374"'\'' "$f"; then sed -i '\''s|^bind = "127.0.0.1:49374"$|bind = "127.0.0.1:29374"\nembedding_provider = "local"|'\'' "$f"; fi; grep -qx '\''bind = "127.0.0.1:29374"'\'' "$f"; grep -qx '\''embedding_provider = "local"'\'' "$f"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L277 (systemctl --user enable --now; the unit is packaging/systemd/ai-memory-user.service)
  run_command 'mkdir -p "$HOME/.config/systemd/user" && sed '\''s|^ExecStart=/usr/bin/ai-memory |ExecStart=%h/.local/bin/ai-memory |'\'' "$HOME/.local/opt/ai-memory-2.5.2/packaging/systemd/ai-memory-user.service" > "$HOME/.config/systemd/user/ai-memory.service" && systemctl --user daemon-reload && systemctl --user enable --now ai-memory.service' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L595 (install-hooks --agent codex --apply; with AI_MEMORY_SERVER_URL set it takes the bare origin, L118-121); https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/install_hooks.rs#L2071 (writes only the Codex hooks.json, with a backup)
  # Codex's seven hooks, written once by ai-memory's own installer: the exception synthesis X11 allows, since the client configuration writes no ~/.codex/hooks.json.
  run_command 'AI_MEMORY_SERVER_URL=http://127.0.0.1:29374 ai-memory install-hooks --agent codex --apply' || return "$?"
}

code-search() {
  # semble 0.6.1 + SocratiCode 1.15.0 | uv-tool | planned
  # Wave 3 (2026-10-04, amendment 4): SocratiCode, the other arm of the slot's frozen confirmatory, beside semble; UNRUN.
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # Planned. An interim install (amendment 3): refused while an acknowledgement of the wave-2 batch is owed.
  interim_acknowledged code-search || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/README.md#L41 (uv tool install semble); https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/docs/installation.md#L44 (the semble[mcp]==X.Y.Z pin)
  run_command 'uv tool install -p 3.13 '\''semble[mcp]==0.6.1'\''' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/README.md#L285 (SEMBLE_MODEL_NAME may name a local path); https://huggingface.co/docs/huggingface_hub/guides/download (snapshot_download, revision, local_dir)
  run_command '"$(uv tool dir)/semble/bin/python" -c "from huggingface_hub import snapshot_download; print(snapshot_download('\''minishlab/potion-code-16M-v2'\'', revision='\''e9d2a44ca6a05ac6685f3b23709ea57eb7352d5b'\'', local_dir='\''$HOME/.local/share/semble/potion-code-16M-v2-e9d2a44c'\''))"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L112 (socraticode@1.15.0 into its own prefix with --ignore-scripts and --before=2026-09-24T12:00:00Z, which reproduces the qualified dependency tree); https://registry.npmjs.org/socraticode/-/socraticode-1.15.0.tgz (its sha256, adoption/pins-linux-x86_64.json)
  run_command 'fetch_verified https://registry.npmjs.org/socraticode/-/socraticode-1.15.0.tgz f1ec039e58013863c6e736d1c17876386b9fec1daf9abf72960fcc51c3e364d1 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/socraticode-1.15.0/socraticode-1.15.0.tgz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L770 (the verified registry tarball installed with npm install --global --prefix into the tool's own prefix under the ecosystem root); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix, a local tarball); the client templates run node on ${ECO_ROOT}/tools/socraticode-1.15.0/lib/node_modules/socraticode/dist/index.js, so no command is linked
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; npm install --global --prefix "$e/tools/socraticode-1.15.0" --ignore-scripts --before=2026-09-24T12:00:00Z "$e/downloads/socraticode-1.15.0/socraticode-1.15.0.tgz"' || return "$?"
}

context-supply() {
  # context-mode 1.0.169 | none | planned
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # Planned. The owner default of amendment 4 (wave 3, 2026-10-04): its install does not wait for the wave-2
  # acknowledgements, because its authority is the owner's decision (docs/decisions/2026-10-04-token-full-stack-owner-default.md).
  # Planned. Source: https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L72 (marketplace add); https://code.claude.com/docs/en/discover-plugins (the CLI form, --scope user)
  run_command 'claude plugin marketplace add mksglu/context-mode --scope user' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L73 (plugin install)
  run_command 'claude plugin install context-mode@context-mode --scope user' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L593 (Codex marketplace); https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/marketplace_cmd.rs#L70 (--ref takes the reviewed commit)
  run_command 'codex plugin marketplace add mksglu/context-mode --ref 6f0cc6841c687e754059f36714a11233fda1a02b --json' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/plugin_cmd.rs#L61 (plugin add PLUGIN@MARKETPLACE)
  run_command 'codex plugin add context-mode@context-mode --json' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L315 (the plugin's MCP server runs the npm package); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix, a local tarball)
  run_command 'p="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/context-mode-1.0.169"; d="$(mktemp -d)"; (cd "$d" && npm pack context-mode@1.0.169 >/dev/null && printf '\''%s  %s\n'\'' 09c41e4cf77b21566c76b8ea2fdbd7f3d823055fee2f02c2166fd5bb575daf2c context-mode-1.0.169.tgz | sha256sum --check --status && npm install --global --prefix "$p" ./context-mode-1.0.169.tgz); rc=$?; rm -rf -- "$d"; exit "$rc"' || return "$?"
}

statusline() {
  # claude-hud 0.10.0 (Claude Code status line plugin); Codex shows its native footer, tui.status_line | none | planned
  # UNRUN on every distribution: added from the wave-2 records of 2026-10-03, after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/README.md#L29 (marketplace add); https://code.claude.com/docs/en/discover-plugins (#ref pins a tag; --scope user)
  run_command 'claude plugin marketplace add jarrodwatts/claude-hud#v0.10.0 --scope user' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/README.md#L30 (plugin install)
  run_command 'claude plugin install claude-hud@claude-hud --scope user' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/commands/setup.md#L24 (the runtime; inspect at L35, install at L58); https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs#L69 (install copies the launcher the status line runs to <config dir>/plugins/claude-hud/statusline.mjs and writes statusLine, L69-101); wave-2 usage ruling, change 3 (the helper, without prompts)
  run_command 'c="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; set -- "$c"/plugins/cache/*/claude-hud/0.10.0; [[ $# == 1 && -f "$1/scripts/setup.mjs" ]] || { printf "claude-hud 0.10.0 is not in exactly one marketplace cache under %s\n" "$c" >&2; exit 1; }; rt="$(command -v bun 2>/dev/null || command -v node 2>/dev/null)" || { printf "no node or bun for the claude-hud helper\n" >&2; exit 1; }; "$rt" "$1/scripts/setup.mjs" inspect --shell posix; "$rt" "$1/scripts/setup.mjs" install --shell posix' || return "$?"
  # Planned. Source: https://code.claude.com/docs/en/statusline.md#L69 (refreshInterval); https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs#L94 (install keeps earlier statusLine keys only when they were claude-hud's); wave-2 usage ruling, change 4 (refreshInterval 5 when absent: a temporary file in the same folder, then mv)
  run_command 's="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"; t="$(readlink -f -- "$s")"; if jq -e ".statusLine.refreshInterval == null" "$t" >/dev/null; then n="$(mktemp "$t.XXXXXX")"; jq ".statusLine.refreshInterval = 5" "$t" > "$n" && chmod --reference="$t" -- "$n" && mv -f -- "$n" "$t" || { rm -f -- "$n"; exit 1; }; fi' || return "$?"
}

ccusage() {
  # ccusage 20.0.26 | none | planned
  # UNRUN on every distribution: changed by the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/ccusage/ccusage/d9821088b98aa536c7a385aa1a4579d6fa02269b/apps/ccusage/README.md#L62 (ccusage reads local usage data); https://registry.npmjs.org/ccusage/-/ccusage-20.0.26.tgz (its sha256, adoption/pins-linux-x86_64.json)
  run_command 'fetch_verified https://registry.npmjs.org/ccusage/-/ccusage-20.0.26.tgz b8d59c191f357d5e847c109f306cf522e60496fc9219be2ab72d201fd59eb1f2 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/ccusage-20.0.26/ccusage-20.0.26.tgz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L770 (the verified registry tarball installed with npm install --global --prefix into the tool's own prefix under the ecosystem root); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix, a local tarball)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; npm install --global --prefix "$e/tools/ccusage-20.0.26" "$e/downloads/ccusage-20.0.26/ccusage-20.0.26.tgz"; mkdir -p "$e/bin"; ln -sfn "$e/tools/ccusage-20.0.26/bin/ccusage" "$e/bin/ccusage"' || return "$?"
}

command-output() {
  # RTK 0.50.0 | release-binary | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/rtk-ai/rtk/v0.50.0/README.md#L113 (the Linux release asset); https://github.com/rtk-ai/rtk/releases/tag/v0.50.0 (its sha256: the release's checksums.txt line, adoption/pins-linux-x86_64.json)
  run_command 'fetch_verified https://github.com/rtk-ai/rtk/releases/download/v0.50.0/rtk-x86_64-unknown-linux-musl.tar.gz bc2b8902b0d9c796c82ef45f16ae2307e17757afeca5ee156235a3dc7bda5f89 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/rtk-0.50.0/rtk-x86_64-unknown-linux-musl.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L59 (extract into the empty versioned prefix); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L414 (the link into the ecosystem root's bin, where the client templates run ${ECO_ROOT}/bin)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; mkdir -p "$e/tools/rtk-0.50.0" "$e/bin"; tar -xf "$e/downloads/rtk-0.50.0/rtk-x86_64-unknown-linux-musl.tar.gz" -C "$e/tools/rtk-0.50.0"; [[ -x "$e/tools/rtk-0.50.0/rtk" ]]; ln -sfn "$e/tools/rtk-0.50.0/rtk" "$e/bin/rtk"' || return "$?"
}

output-compression() {
  # Headroom 0.37.0 (headroom-ai[mcp], MCP server only) | uv-tool | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/headroomlabs-ai/headroom/v0.37.0/README.md#L92 (uv tool install --python 3.13; the [mcp] extra of adoption/pins-linux-x86_64.json instead of [all]); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L988 (UV_TOOL_DIR and UV_TOOL_BIN_DIR in the ecosystem root, where the client templates run ${ECO_ROOT}/bin)
  run_command 'UV_TOOL_DIR="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/python-tools" UV_TOOL_BIN_DIR="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin" uv tool install --python 3.13 '\''headroom-ai[mcp]==0.37.0'\''' || return "$?"
}

code-index() {
  # jcodemunch-mcp 1.108.319 | uv-tool | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/8f7b34abe16fb459e0bf1c04747d584216dfe32e/README.md#L91 (uv tool install jcodemunch-mcp); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L521 (the pin, --python 3.13 and the ecosystem root)
  run_command 'UV_TOOL_DIR="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/python-tools" UV_TOOL_BIN_DIR="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin" uv tool install --python 3.13 jcodemunch-mcp==1.108.319' || return "$?"
}

code-graph() {
  # codebase-memory-mcp 0.11.0 | release-binary | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/v0.11.0/README.md#L88 (the Linux archive of the release); https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0 (the asset; recipes/README.md records its sha256)
  run_command 'fetch_verified https://github.com/DeusData/codebase-memory-mcp/releases/download/v0.11.0/codebase-memory-mcp-linux-amd64.tar.gz 032b33c1833919a2d1de67ff6367fa6ea46aee8689c86ef223c88fae3b6e4536 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/codebase-memory-mcp-0.11.0/codebase-memory-mcp-linux-amd64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/v0.11.0/README.md#L94 (extract; the archive's install.sh on the next line of that README is not run); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L59 (extract into the empty versioned prefix); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L414 (the link into the ecosystem root's bin, where the client templates run ${ECO_ROOT}/bin)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; mkdir -p "$e/tools/codebase-memory-mcp-0.11.0" "$e/bin"; tar -xf "$e/downloads/codebase-memory-mcp-0.11.0/codebase-memory-mcp-linux-amd64.tar.gz" -C "$e/tools/codebase-memory-mcp-0.11.0"; [[ -x "$e/tools/codebase-memory-mcp-0.11.0/codebase-memory-mcp" ]]; ln -sfn "$e/tools/codebase-memory-mcp-0.11.0/codebase-memory-mcp" "$e/bin/codebase-memory-mcp"' || return "$?"
}

repo-packing() {
  # Repomix 1.18.1 | none | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L109 (npm install -g repomix); https://registry.npmjs.org/repomix/-/repomix-1.18.1.tgz (its sha256, adoption/pins-linux-x86_64.json)
  run_command 'fetch_verified https://registry.npmjs.org/repomix/-/repomix-1.18.1.tgz d4d278310b33f245d4abbc7f757cc3815ff362f6d69225692f837c7dcee83c8f "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/repomix-1.18.1/repomix-1.18.1.tgz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L770 (the verified registry tarball installed with npm install --global --prefix into the tool's own prefix under the ecosystem root); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix, a local tarball)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; npm install --global --prefix "$e/tools/repomix-1.18.1" "$e/downloads/repomix-1.18.1/repomix-1.18.1.tgz"; mkdir -p "$e/bin"; ln -sfn "$e/tools/repomix-1.18.1/bin/repomix" "$e/bin/repomix"' || return "$?"
}

structured-data() {
  # TOON 4.1.1 (@toon-format/cli) | none | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L11 (npm install -g @toon-format/cli); https://registry.npmjs.org/@toon-format/cli/-/cli-4.1.1.tgz (its sha256, adoption/pins-linux-x86_64.json)
  run_command 'fetch_verified https://registry.npmjs.org/@toon-format/cli/-/cli-4.1.1.tgz 93ec1d3f44a608332d6f1fa811adda4237983841baec9b165e40252f20d83ca6 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/toon-4.1.1/cli-4.1.1.tgz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L770 (the verified registry tarball installed with npm install --global --prefix into the tool's own prefix under the ecosystem root); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix, a local tarball)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; npm install --global --prefix "$e/tools/toon-4.1.1" "$e/downloads/toon-4.1.1/cli-4.1.1.tgz"; mkdir -p "$e/bin"; ln -sfn "$e/tools/toon-4.1.1/bin/toon" "$e/bin/toon"' || return "$?"
}

doc-conversion() {
  # MarkItDown 0.1.8 | uv-tool | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/README.md#L62 (the package; the base converter of adoption/pins-linux-x86_64.json instead of [all]); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L988 (UV_TOOL_DIR and UV_TOOL_BIN_DIR in the ecosystem root, where the client templates run ${ECO_ROOT}/bin)
  run_command 'UV_TOOL_DIR="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/python-tools" UV_TOOL_BIN_DIR="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/bin" uv tool install --python 3.13 markitdown==0.1.8' || return "$?"
}

api-docs() {
  # Context Hub 0.1.4 (context-hub, the chub CLI) | none | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/andrewyng/context-hub/v0.1.4/README.md#L12 (npm install -g @aisuite/chub); https://registry.npmjs.org/@aisuite/chub/-/chub-0.1.4.tgz (its sha256, adoption/pins-linux-x86_64.json)
  run_command 'fetch_verified https://registry.npmjs.org/@aisuite/chub/-/chub-0.1.4.tgz ca9fb94a21d3b5ae3025923ded305dd11f189626da5adab48a8b947bc523888f "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/context-hub-0.1.4/chub-0.1.4.tgz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L770 (the verified registry tarball installed with npm install --global --prefix into the tool's own prefix under the ecosystem root); https://docs.npmjs.com/cli/v11/commands/npm-install (--prefix, a local tarball)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; npm install --global --prefix "$e/tools/context-hub-0.1.4" "$e/downloads/context-hub-0.1.4/chub-0.1.4.tgz"; mkdir -p "$e/bin"; ln -sfn "$e/tools/context-hub-0.1.4/bin/chub" "$e/bin/chub"' || return "$?"
}

trace-viewer() {
  # otel-tui 0.7.5 | release-binary | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/ymtdzzz/otel-tui/3b25779a083469b732e3c628b4a412ee05cf9948/README.md#L131 (the release assets); https://github.com/ymtdzzz/otel-tui/releases/tag/v0.7.5 (the asset; recipes/README.md records its sha256)
  run_command 'fetch_verified https://github.com/ymtdzzz/otel-tui/releases/download/v0.7.5/otel-tui_Linux_x86_64.tar.gz dd10bfa12b6713a2d51d7a094644ff61a2467856fc93d3acecfe741a124ca896 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/otel-tui-0.7.5/otel-tui_Linux_x86_64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L59 (extract into the empty versioned prefix); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L414 (the link into the ecosystem root's bin, where the client templates run ${ECO_ROOT}/bin)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; mkdir -p "$e/tools/otel-tui-0.7.5" "$e/bin"; tar -xf "$e/downloads/otel-tui-0.7.5/otel-tui_Linux_x86_64.tar.gz" -C "$e/tools/otel-tui-0.7.5"; [[ -x "$e/tools/otel-tui-0.7.5/otel-tui" ]]; ln -sfn "$e/tools/otel-tui-0.7.5/otel-tui" "$e/bin/otel-tui"' || return "$?"
}

token-lane-carriers() {
  # token-lanes carriers: the SubagentStart block and a SessionStart main-session block (Claude Code hooks) | repository-recipe | planned
  # UNRUN on every distribution: added from the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  printf '%s\n' 'UNRUN. The client configuration writes the carriers after this plan runs (tools/adoption/new_wsl_client_config.py, then its --check); this plan installs nothing for them and has nothing to check. Recipe/source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/docs/token-session-handbook.md#L197'
}

session-analytics() {
  # agentsview 0.43.0 (local archive only) | release-binary | planned
  # UNRUN on every distribution: changed by the wave-3 batch of 2026-10-04 (the owner's decision, amendment 4), after every recorded run of this plan.
  # Planned. Source: https://raw.githubusercontent.com/kenn-io/agentsview/v0.43.0/README.md#L25 (GitHub Releases); https://github.com/kenn-io/agentsview/releases/tag/v0.43.0 (the asset and its GitHub digest, read 2026-10-04)
  run_command 'fetch_verified https://github.com/kenn-io/agentsview/releases/download/v0.43.0/agentsview_0.43.0_linux_amd64.tar.gz 4520c6698772d2db7220212abf58d7d58c0966d7435f0a5ab134371f874df6d9 "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/downloads/agentsview-0.43.0/agentsview_0.43.0_linux_amd64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L59 (extract into the empty versioned prefix); https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L414 (the link into the ecosystem root's bin, where the client templates run ${ECO_ROOT}/bin)
  run_command 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; mkdir -p "$e/tools/agentsview-0.43.0" "$e/bin"; tar -xf "$e/downloads/agentsview-0.43.0/agentsview_0.43.0_linux_amd64.tar.gz" -C "$e/tools/agentsview-0.43.0"; [[ -x "$e/tools/agentsview-0.43.0/agentsview" ]]; ln -sfn "$e/tools/agentsview-0.43.0/agentsview" "$e/bin/agentsview"' || return "$?"
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

alerting() {
  # Alertmanager | release-binary | planned
  # Planned. Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L14
  run_command 'fetch_verified '\''https://github.com/prometheus/alertmanager/releases/download/v0.34.1/alertmanager-0.34.1.linux-amd64.tar.gz'\'' '\''265b9d1e55ef0d5306a436018af6d2b686c2ce051f03d968f7464ecb1372a7e8'\'' "$tool_root/alertmanager/alertmanager-0.34.1.linux-amd64.tar.gz"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L14
  run_command '(cd "$tool_root/alertmanager" && tar xvfz '\''alertmanager-0.34.1.linux-amd64.tar.gz'\'')' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L14
  run_command 'install -m 0755 "$tool_root/alertmanager/alertmanager-0.34.1.linux-amd64/alertmanager" "$HOME/.local/bin/alertmanager"' || return "$?"
  copy_config 'alertmanager.yaml' || return "$?"
}

loki() {
  # Loki | release-binary | measurement-only
  # Planned. Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24
  run_command 'fetch_verified '\''https://github.com/grafana/loki/releases/download/v3.7.8/loki-linux-amd64.zip'\'' '\''62aea42c9cba52cd1642b3666ab37019a0ce4c24ab50b07e85dccc8d812f7d61'\'' "$tool_root/loki/loki-linux-amd64.zip"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24
  run_command '(cd "$tool_root/loki" && unzip -o '\''loki-linux-amd64.zip'\'')' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24
  run_command 'install -m 0755 "$tool_root/loki/loki-linux-amd64" "$HOME/.local/bin/loki"' || return "$?"
  copy_config 'loki.yaml' || return "$?"
}

grafana() {
  # Grafana | release-binary | measurement-only
  # Planned. Source: https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux
  run_command 'fetch_verified '\''https://dl.grafana.com/grafana/release/13.2.3/grafana_13.2.3_36482603486_linux_amd64.tar.gz'\'' '\''6107ad27016296aac38e0d7ffa8753ab540b5541ad27e94790f771289d733235'\'' "$tool_root/grafana/grafana_13.2.3_36482603486_linux_amd64.tar.gz"' || return "$?"
  # Planned. Source: https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux
  run_command '(cd "$tool_root/grafana" && tar -zxvf '\''grafana_13.2.3_36482603486_linux_amd64.tar.gz'\'')' || return "$?"
  # Planned. Source: https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux
  run_command 'link_grafana' || return "$?"
  copy_config 'grafana.ini' || return "$?"
}

local-model-server() {
  # Ollama | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/ollama.toml#L1
  run_command 'mise use -g ollama@0.35.0' || return "$?"
  refresh_path || return "$?"
  copy_config 'ollama.env.example' || return "$?"
}

local-generation-model() {
  # Swift-1.5-Qwen3.8-27B IQ3_S through Ollama (swift-iq3s-s2o-64k, context 64,000) | model-server | planned
  refresh_path || return "$?"
  model_server_answers || return "$?"
  # Planned. The file at the pinned revision and its sha256 (the Hugging Face file page lists both).
  # Source: https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF/blob/d74895bbe5db4bec1e0024e7cc87d59c02d7631a/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf
  run_command 'fetch_verified '\''https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF/resolve/d74895bbe5db4bec1e0024e7cc87d59c02d7631a/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf'\'' '\''1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786'\'' "$tool_root/ollama-models/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf"' || return "$?"
  # Planned. A Modelfile's GGUF path is absolute or relative to the Modelfile, so both Modelfiles go beside the file.
  # Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/modelfile.mdx#L126
  run_command 'install -m 0644 -t "$tool_root/ollama-models" "$plan_dir/models/swift-iq3s-s2o.Modelfile" "$plan_dir/models/swift-iq3s-s2o-64k.Modelfile"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L2422
  run_command 'OLLAMA_HOST=127.0.0.1:21434 ollama create swift-iq3s-s2o -f "$tool_root/ollama-models/swift-iq3s-s2o.Modelfile"' || return "$?"
  # Planned. The context belongs to the model, never to the server (models/swift-iq3s-s2o-64k.Modelfile).
  # Source: https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/modelfile.mdx#L146
  run_command 'OLLAMA_HOST=127.0.0.1:21434 ollama create swift-iq3s-s2o-64k -f "$tool_root/ollama-models/swift-iq3s-s2o-64k.Modelfile"' || return "$?"
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

zizmor() {
  # zizmor | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/zizmor.toml#L1
  run_command 'mise use -g zizmor@1.30.1' || return "$?"
  refresh_path || return "$?"
}

syft() {
  # Syft | mise | planned
  # Planned. Source: https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/syft.toml#L1
  run_command 'mise use -g syft@1.54.0' || return "$?"
  refresh_path || return "$?"
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
  # GPT Researcher and DeerFlow, kept as two independent evidence gatherers | none | planned
  # Revised by the wave-2 research ruling (changes 9 and 10): the embedded DeerFlowClient, no HTTP service, port or Compose.
  # Planned. Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Install.md#L38
  run_command 'checkout_tag https://github.com/bytedance/deer-flow.git v2.1.0 "$tool_root/deer-flow"' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Install.md#L38 (make config writes config.yaml, which embedded runs read)
  run_command '(cd "$tool_root/deer-flow" && if [[ ! -e config.yaml && ! -e .env && ! -e frontend/.env ]]; then make config; elif [[ ! -e config.yaml || ! -e .env || ! -e frontend/.env ]]; then printf "Partial DeerFlow config; repair from upstream recipe.\n" >&2; exit 1; fi)' || return "$?"
  # Planned. Source: https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Makefile#L96 (the backend's locked environment); https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/README.md#L1658 (the embedded client)
  run_command '(cd "$tool_root/deer-flow/backend" && uv sync --locked)' || return "$?"
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
  printf '%s\n' 'engineering-process-skills | mattpocock/skills (selected skills, not the bundle) | none | planned'
  printf '%s\n' 'skill-discovery | find-skills (vercel-labs/skills) | none | planned'
  printf '%s\n' 'skill-authoring | skill-creator (embedded in Codex; anthropics/skills for Claude Code) | none | planned'
  printf '%s\n' 'research-skill | Not installed until its activation gate returns (GPT Researcher'\''s own skill with its MCP server) | none | excluded'
  printf '%s\n' 'mcporter | mcporter | npm-global | planned'
  printf '%s\n' 'mcp-inspector | MCP Inspector | none | excluded'
  printf '%s\n' 'agent-messaging | Not installed until the deciding measurement returns | none | excluded'
  printf '%s\n' 'sandbox-runtime-srt | sandbox-runtime (srt) | npm-global | planned'
  printf '%s\n' 'isolation-container-boundary | No additional component: rootless containers on the container engine that the hosting layer installs | none | excluded'
  printf '%s\n' 'serena | Serena | uv-tool | planned'
  printf '%s\n' 'claude-plugins-official-code-intelligence-lsp-pl | Not installed: the same job as Serena, for Claude Code only, with no measured gain; neither blind Sol-ultra order picked it | none | excluded'
  printf '%s\n' 'structural-search | ast-grep | mise | planned'
  printf '%s\n' 'code-search | semble 0.6.1 + SocratiCode 1.15.0 | uv-tool | planned'
  printf '%s\n' 'embedding-model | Qwen3-Embedding-0.6B through Ollama (qwen3-embedding:0.6b, Q8_0, as qwen3-embedding-8k, context 8,192) | model-server | planned'
  printf '%s\n' 'reranker-model | Not installed: no installed retrieval owner can call an external reranker: QMD reranks in-process with its bundled model, the research harness exposes no reranker setting and the model server has no rerank endpoint; both blind GPT orders picked BGE rerankers and NeMo Retriever | none | excluded'
  printf '%s\n' 'tobi-qmd | tobi/qmd | npm-global | planned'
  printf '%s\n' 'mineru | MinerU | uv-tool | planned'
  printf '%s\n' 'trafilatura | Not installed: text extraction is a sub-step of retrieval that the two agents'\'' native web tools (or the one browser tool) already own; neither blind Sol-ultra order picked it | none | excluded'
  printf '%s\n' 'playwright-cli | Playwright CLI | npm-global | measurement-only'
  printf '%s\n' 'web-search-provider | Not installed: both research harnesses ship a keyless search provider as a declared dependency; SearXNG (picked by both blind GPT orders with two MCP bridges) is the named challenger, decided by a measurement on 30 frozen queries | none | excluded'
  printf '%s\n' 'memory-owner | ai-memory 2.5.2 | release-binary | planned'
  printf '%s\n' 'ccusage | ccusage 20.0.26 | none | planned'
  printf '%s\n' 'context-supply | context-mode 1.0.169 | none | planned'
  printf '%s\n' 'statusline | claude-hud 0.10.0 (Claude Code status line plugin); Codex shows its native footer, tui.status_line | none | planned'
  printf '%s\n' 'command-output | RTK 0.50.0 | release-binary | planned'
  printf '%s\n' 'output-compression | Headroom 0.37.0 (headroom-ai[mcp], MCP server only) | uv-tool | planned'
  printf '%s\n' 'code-index | jcodemunch-mcp 1.108.319 | uv-tool | planned'
  printf '%s\n' 'code-graph | codebase-memory-mcp 0.11.0 | release-binary | planned'
  printf '%s\n' 'repo-packing | Repomix 1.18.1 | none | planned'
  printf '%s\n' 'structured-data | TOON 4.1.1 (@toon-format/cli) | none | planned'
  printf '%s\n' 'doc-conversion | MarkItDown 0.1.8 | uv-tool | planned'
  printf '%s\n' 'api-docs | Context Hub 0.1.4 (context-hub, the chub CLI) | none | planned'
  printf '%s\n' 'trace-viewer | otel-tui 0.7.5 | release-binary | planned'
  printf '%s\n' 'token-lane-carriers | token-lanes carriers: the SubagentStart block and a SessionStart main-session block (Claude Code hooks) | repository-recipe | planned'
  printf '%s\n' 'otel-collector-contrib | OTel Collector Contrib | release-binary | planned'
  printf '%s\n' 'prometheus | Prometheus | release-binary | planned'
  printf '%s\n' 'loki | Loki | release-binary | measurement-only'
  printf '%s\n' 'grafana | Grafana | release-binary | measurement-only'
  printf '%s\n' 'phoenix | Not installed: qualifying a model route is evaluation, owned by Inspect AI and Harbor; the layer'\''s requirement has no trace-store job; no blind GPT sample picked it | none | excluded'
  printf '%s\n' 'local-model-server | Ollama | mise | planned'
  printf '%s\n' 'alerting | Alertmanager | release-binary | planned'
  printf '%s\n' 'local-generation-model | Swift-1.5-Qwen3.8-27B IQ3_S through Ollama (swift-iq3s-s2o-64k, context 64,000) | model-server | planned'
  printf '%s\n' 'session-analytics | agentsview 0.43.0 (local archive only) | release-binary | planned'
  printf '%s\n' 'inspect-ai | Inspect AI | uv-tool | planned'
  printf '%s\n' 'harbor-containerized-agent-e2e-runner | Harbor (containerized agent E2E runner) | uv-tool | planned'
  printf '%s\n' 'promptfoo | Not installed: prompt and provider evaluation is owned by Inspect AI; neither blind Sol-ultra order picked it | none | excluded'
  printf '%s\n' 'zizmor | zizmor | mise | planned'
  printf '%s\n' 'attest | attest | none | excluded'
  printf '%s\n' 'syft | Syft | mise | planned'
  printf '%s\n' 'dependabot | Dependabot | none | excluded'
  printf '%s\n' 'codeql-sarif | Not installed: a transport, not a scanner: zizmor'\''s own action carries the pinned upload step; no blind GPT sample picked it as a slot | none | excluded'
  printf '%s\n' 'actionlint-kjanat | actionlint (kjanat) | mise | planned'
  printf '%s\n' 'dagu | Dagu | native-installer | planned'
  printf '%s\n' 'docker-compose | Docker Compose | apt-repo | planned'
  printf '%s\n' 'container-engine | Docker Engine / Moby | apt-repo | planned'
  printf '%s\n' 'gpu-container-runtime | Not installed: no settled owner runs GPU work in a container (the model server and the document parser install natively); NVIDIA Container Toolkit, picked by both blind GPT orders, passes every gate and becomes the default the moment one does | none | excluded'
  printf '%s\n' 'betterleaks | betterleaks | mise | planned'
  printf '%s\n' 'trufflehog | Not installed: no blind GPT sample picked it; betterleaks owns secret scanning, and trufflehog'\''s verification against live services is a separate audit job that the layer'\''s requirement does not ask for | none | excluded'
  printf '%s\n' 'credential-custody | Not installed until the deciding measurement returns (the repository'\''s runner and guard stay the practice) | none | excluded'
  printf '%s\n' 'git | git | apt | planned'
  printf '%s\n' 'gh-github-cli | gh (GitHub CLI) | mise | planned'
  printf '%s\n' 'worktrunk | worktrunk | mise | planned'
  printf '%s\n' 'difftastic | difftastic | mise | planned'
  printf '%s\n' 'claude-code-action | Not installed: it runs on GitHub-hosted runners and is a per-repository choice, not part of the machine; no blind GPT sample picked it | none | excluded'
  printf '%s\n' 'agent-structural-diff | Not installed: git diff and difftastic cover diff; all three blind GPT samples picked sem, and the critic found it the same job as difftastic (noting that difftastic'\''s JSON output is still behind DFT_UNSTABLE=yes) | none | excluded'
  printf '%s\n' 'cross-family-review | No additional component: the two clients'\'' native review commands, each family on the other'\''s work | none | excluded'
  printf '%s\n' 'mise | mise | native-installer | planned'
  printf '%s\n' 'restic | Restic | mise | planned'
  printf '%s\n' 'chezmoi | Not installed: mise and the repository-carried bootstrap already own the reproduction of configuration; no blind GPT sample picked it | none | excluded'
  printf '%s\n' 'base-distribution | Ubuntu 26.04.1 LTS (Canonical WSL image), primary | none | excluded'
  printf '%s\n' 'gpt-gateway | OmniRoute | npm-global | planned'
  printf '%s\n' 'agent-runtime-worker | OpenHands software-agent-sdk | none | planned'
  printf '%s\n' 'research-harnesses | GPT Researcher and DeerFlow, kept as two independent evidence gatherers | none | planned'
  printf '%s\n' 'credential-guard | Command and secret-path guard (K4) | repository-recipe | planned'
  printf '%s\n' 'convergence-validators | Convergence practice and its validators | repository-recipe | planned'
  exit 0
fi
case "$only" in
  ''|claude-code|codex|claude-agent-sdk|codex-sdk-and-codex-exec-app-server|trail-of-bits-security-skills-trailofbits-skills|engineering-process-skills|skill-discovery|skill-authoring|research-skill|mcporter|mcp-inspector|agent-messaging|sandbox-runtime-srt|isolation-container-boundary|serena|claude-plugins-official-code-intelligence-lsp-pl|structural-search|code-search|embedding-model|reranker-model|tobi-qmd|mineru|trafilatura|playwright-cli|web-search-provider|memory-owner|ccusage|context-supply|statusline|command-output|output-compression|code-index|code-graph|repo-packing|structured-data|doc-conversion|api-docs|trace-viewer|token-lane-carriers|otel-collector-contrib|prometheus|loki|grafana|phoenix|local-model-server|alerting|local-generation-model|session-analytics|inspect-ai|harbor-containerized-agent-e2e-runner|promptfoo|zizmor|attest|syft|dependabot|codeql-sarif|actionlint-kjanat|dagu|docker-compose|container-engine|gpu-container-runtime|betterleaks|trufflehog|credential-custody|git|gh-github-cli|worktrunk|difftastic|claude-code-action|agent-structural-diff|cross-family-review|mise|restic|chezmoi|base-distribution|gpt-gateway|agent-runtime-worker|research-harnesses|credential-guard|convergence-validators) ;;
  *) printf 'Unknown slot: %s\n' "$only" >&2; exit 2 ;;
esac
# Planned. Two acceptance checks change into repo_root, so the plan runs from a checkout of the repository (README.md); --list needs none.
[[ -e "$repo_root/.git" ]] || { printf 'Run this plan from a checkout of the repository: %s is not a git checkout (see README.md).\n' "$repo_root" >&2; exit 1; }

# Planned. Package prerequisites, then mise/runtimes, user CLIs, containers, services.
needs_execution=false
needs_runtime=false
needs_docker=false
for slot in 'claude-code' 'codex' 'claude-agent-sdk' 'codex-sdk-and-codex-exec-app-server' 'trail-of-bits-security-skills-trailofbits-skills' 'engineering-process-skills' 'skill-discovery' 'skill-authoring' 'mcporter' 'sandbox-runtime-srt' 'serena' 'structural-search' 'code-search' 'tobi-qmd' 'mineru' 'memory-owner' 'context-supply' 'statusline' 'ccusage' 'command-output' 'output-compression' 'code-index' 'code-graph' 'repo-packing' 'structured-data' 'doc-conversion' 'api-docs' 'trace-viewer' 'session-analytics' 'otel-collector-contrib' 'prometheus' 'local-model-server' 'alerting' 'inspect-ai' 'harbor-containerized-agent-e2e-runner' 'zizmor' 'syft' 'actionlint-kjanat' 'dagu' 'docker-compose' 'container-engine' 'betterleaks' 'git' 'gh-github-cli' 'worktrunk' 'difftastic' 'mise' 'restic' 'gpt-gateway' 'agent-runtime-worker' 'research-harnesses'; do selected "$slot" && needs_execution=true; done
for slot in 'playwright-cli' 'loki' 'grafana' 'local-generation-model' 'embedding-model'; do named "$slot" && needs_execution=true; done
for slot in 'claude-agent-sdk' 'codex-sdk-and-codex-exec-app-server' 'trail-of-bits-security-skills-trailofbits-skills' 'engineering-process-skills' 'skill-discovery' 'skill-authoring' 'mcporter' 'sandbox-runtime-srt' 'serena' 'structural-search' 'code-search' 'tobi-qmd' 'mineru' 'context-supply' 'statusline' 'ccusage' 'output-compression' 'code-index' 'repo-packing' 'structured-data' 'doc-conversion' 'api-docs' 'local-model-server' 'inspect-ai' 'harbor-containerized-agent-e2e-runner' 'zizmor' 'syft' 'actionlint-kjanat' 'betterleaks' 'gh-github-cli' 'worktrunk' 'difftastic' 'restic' 'gpt-gateway' 'agent-runtime-worker' 'research-harnesses'; do selected "$slot" && needs_runtime=true; done
for slot in 'playwright-cli'; do named "$slot" && needs_runtime=true; done
for slot in 'harbor-containerized-agent-e2e-runner' 'docker-compose'; do selected "$slot" && needs_docker=true; done

if $needs_execution; then
  # Planned. Repository bootstrap-linux.sh:206-216; selected owner prereqs extend its package list.
  packages=(ca-certificates curl git tar gzip xz-utils jq)
  if selected research-harnesses; then packages+=(make); fi
  if selected sandbox-runtime-srt; then packages+=(bubblewrap socat ripgrep gcc libseccomp-dev); fi
  if named loki; then packages+=(unzip); fi
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
measured_slot() {
  # Planned. A split slot installs only when named; the default run skips it.
  if named "$1"; then run_slot "$1"; elif selected "$1"; then printf '%s | install | skipped\n' "$1"; fi
}
# Planned. Selective installs include the native clients required by their integration.
if [[ "$only" == trail-of-bits-security-skills-trailofbits-skills || "$only" == context-supply || "$only" == statusline ]]; then
  run_slot claude-code
  run_slot codex
fi
if [[ "$only" == codex-sdk-and-codex-exec-app-server ]]; then run_slot codex; fi
if selected 'claude-code'; then run_slot 'claude-code'; fi
if selected 'codex'; then run_slot 'codex'; fi
if selected 'claude-agent-sdk'; then run_slot 'claude-agent-sdk'; fi
if selected 'codex-sdk-and-codex-exec-app-server'; then run_slot 'codex-sdk-and-codex-exec-app-server'; fi
if selected 'trail-of-bits-security-skills-trailofbits-skills'; then run_slot 'trail-of-bits-security-skills-trailofbits-skills'; fi
if selected 'engineering-process-skills'; then run_slot 'engineering-process-skills'; fi
if selected 'skill-discovery'; then run_slot 'skill-discovery'; fi
if selected 'skill-authoring'; then run_slot 'skill-authoring'; fi
if selected 'mcporter'; then run_slot 'mcporter'; fi
if selected 'sandbox-runtime-srt'; then run_slot 'sandbox-runtime-srt'; fi
if selected 'serena'; then run_slot 'serena'; fi
if selected 'structural-search'; then run_slot 'structural-search'; fi
if selected 'tobi-qmd'; then run_slot 'tobi-qmd'; fi
if selected 'mineru'; then run_slot 'mineru'; fi
if selected 'memory-owner'; then run_slot 'memory-owner'; fi
if selected 'code-search'; then run_slot 'code-search'; fi
if selected 'context-supply'; then run_slot 'context-supply'; fi
if selected 'statusline'; then run_slot 'statusline'; fi
if selected 'ccusage'; then run_slot 'ccusage'; fi
if selected 'command-output'; then run_slot 'command-output'; fi
if selected 'output-compression'; then run_slot 'output-compression'; fi
if selected 'code-index'; then run_slot 'code-index'; fi
if selected 'code-graph'; then run_slot 'code-graph'; fi
if selected 'repo-packing'; then run_slot 'repo-packing'; fi
if selected 'structured-data'; then run_slot 'structured-data'; fi
if selected 'doc-conversion'; then run_slot 'doc-conversion'; fi
if selected 'api-docs'; then run_slot 'api-docs'; fi
if selected 'trace-viewer'; then run_slot 'trace-viewer'; fi
if selected 'token-lane-carriers'; then run_slot 'token-lane-carriers'; fi
if selected 'session-analytics'; then run_slot 'session-analytics'; fi
measured_slot 'playwright-cli'
if selected 'inspect-ai'; then run_slot 'inspect-ai'; fi
if selected 'harbor-containerized-agent-e2e-runner'; then run_slot 'harbor-containerized-agent-e2e-runner'; fi
if selected 'zizmor'; then run_slot 'zizmor'; fi
if selected 'syft'; then run_slot 'syft'; fi
if selected 'actionlint-kjanat'; then run_slot 'actionlint-kjanat'; fi
if selected 'betterleaks'; then run_slot 'betterleaks'; fi
if selected 'git'; then run_slot 'git'; fi
if selected 'gh-github-cli'; then run_slot 'gh-github-cli'; fi
if selected 'worktrunk'; then run_slot 'worktrunk'; fi
if selected 'difftastic'; then run_slot 'difftastic'; fi
if selected 'restic'; then run_slot 'restic'; fi
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
if selected 'alerting'; then run_slot 'alerting'; fi
measured_slot 'loki'
measured_slot 'grafana'
if selected 'local-model-server'; then run_slot 'local-model-server'; fi
# Planned. The two model rows create their models through the running model server, which this plan does not start: the
# default run skips them, and --only installs one once the server answers (README.md, "The two local-model rows").
if named 'local-generation-model'; then run_slot 'local-generation-model'; elif selected 'local-generation-model'; then printf '%s | install | skipped\n' 'local-generation-model'; fi
if named 'embedding-model'; then run_slot 'embedding-model'; elif selected 'embedding-model'; then printf '%s | install | skipped\n' 'embedding-model'; fi
if selected 'dagu'; then run_slot 'dagu'; fi
if selected 'gpt-gateway'; then run_slot 'gpt-gateway'; fi
if selected 'research-harnesses'; then run_slot 'research-harnesses'; fi
exit "$failed"
