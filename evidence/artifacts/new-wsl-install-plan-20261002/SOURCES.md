# Source research and review
Status: revised to the merged definitive manifest after the real-distribution run of the previous revision (64 foundation rows), then by the layer consensus of 2026-10-02 to 69 foundation rows. The earlier research below was source-only; its historical static checks remain in validation.json. Round 1 outcomes and log evidence, and the real-distribution result, are in VALIDATION.md. When this file was written, this revision's installation, service and provider/GPU commands were unrun. On 2026-10-02 (12:54Z to 13:17Z) the installation and acceptance commands of the 64-row revision and four service starts ran once in a throwaway distribution (VALIDATION.md, "Clean run of this revision"), and later that day the 64-row revision, as merged to main (6652b78e), ran once on the destination distribution; the record of that run is private, and its public receipt comes with that distribution's acceptance. An UNRUN label in a heading below gives the status at the source review and is dated where the throwaway run changed it. The install and acceptance commands of the five rows added from the layer consensus have not run anywhere. In the throwaway distribution no provider, model or GPU command ran. Local syntax/inventory/dispatch/consistency checks do not certify native runtime acceptance. Rows that left the plan lost their source entries here; their round 1 results stay in VALIDATION.md, and the sources of this revision's repairs and additions are in the last two sections (the 64-row revision's, then the five rows' from the layer consensus).
North-star action served: a reproducible foundation installation plan for subsequent US-equities research and historical simulation. No trading readiness or live/paper operation is claimed.
Discovery was bounded to the supplied owners/pins, selected upstream READMEs/docs, mise registry entries, release assets/checksums, and the existing repository adoption recipes. search-first and context-mode were used; researchers were read-only.
The specialized stack-researcher role retained its defined Astra/Max model. Consequential source judgment trigger: native-versus-Compose host listener boundaries and SDK route/package classification. Acceptance result: coordinator accepted the pinned primary-source conclusions only; runtime acceptance remains unrun.
## Git fix wave sources (2026-10-04)

North-star action served: native Git isolation, syntax-aware change inspection
and review by the other model family before subsequent US-equities research and
historical simulation. This is a bounded plan repair, not a new WSL E2E result.

- **Worktrunk install and release:** `max-sixty/worktrunk@v0.80.0`, source
  `b49ca7eea9b03145791a5b94eccaf9c59412ed37`; the
  [release](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0) publishes
  the installer and shell-integration step. The existing supported mise route is
  [jdx/mise@v2026.10.0:registry/worktrunk.toml:1](https://github.com/jdx/mise/blob/v2026.10.0/registry/worktrunk.toml#L1).
  Bash integration:
  [docs/src/content/docs/shell-integration.md:16](https://github.com/max-sixty/worktrunk/blob/v0.80.0/docs/src/content/docs/shell-integration.md#L16).
  Client plugin installation and the Claude-only isolation boundary:
  [docs/src/content/docs/claude-code.md:7](https://github.com/max-sixty/worktrunk/blob/v0.80.0/docs/src/content/docs/claude-code.md#L7),
  [Claude installation:21](https://github.com/max-sixty/worktrunk/blob/v0.80.0/docs/src/content/docs/claude-code.md#L21),
  [Codex installation:37](https://github.com/max-sixty/worktrunk/blob/v0.80.0/docs/src/content/docs/claude-code.md#L37).
  The `--yes` parameter is implemented in
  [src/commands/config/plugins.rs:23](https://github.com/max-sixty/worktrunk/blob/v0.80.0/src/commands/config/plugins.rs#L23)
  and [src/commands/config/codex.rs:16](https://github.com/max-sixty/worktrunk/blob/v0.80.0/src/commands/config/codex.rs#L16).
- **Worktrunk acceptance:** the unchanged native command examples in
  [docs/src/content/docs/switch.md:20](https://github.com/max-sixty/worktrunk/blob/v0.80.0/docs/src/content/docs/switch.md#L20),
  [README.md:153](https://github.com/max-sixty/worktrunk/blob/v0.80.0/README.md#L153)
  and [docs/src/content/docs/remove.md:11](https://github.com/max-sixty/worktrunk/blob/v0.80.0/docs/src/content/docs/remove.md#L11).
  Their disposable repository, state assertions and dirty-removal control are
  local integration checks. `cargo test` is separately documented at
  [README.md:237](https://github.com/max-sixty/worktrunk/blob/v0.80.0/README.md#L237);
  this plan does not replace or claim to execute that Rust suite. Native Claude
  listing semantics:
  [src/commands/config/plugins.rs:173](https://github.com/max-sixty/worktrunk/blob/v0.80.0/src/commands/config/plugins.rs#L173).
  Codex's installed/enabled JSON fields:
  [openai/codex@rust-v0.160.0:codex-rs/cli/src/plugin_cmd.rs:481](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/plugin_cmd.rs#L481).
- **Difftastic install and acceptance:**
  [Wilfred/difftastic@0.71.0 release](https://github.com/Wilfred/difftastic/releases/tag/0.71.0),
  [jdx/mise@v2026.10.0:registry/difftastic.toml:1](https://github.com/jdx/mise/blob/v2026.10.0/registry/difftastic.toml#L1),
  [manual/src/usage.md:10](https://github.com/Wilfred/difftastic/blob/0.71.0/manual/src/usage.md#L10).
  The unchanged fixtures are
  [sample_files/simple_1.js:1](https://github.com/Wilfred/difftastic/blob/0.71.0/sample_files/simple_1.js#L1)
  (SHA256 `106256fcefb82debbc83be06ceeec073e35a4a1bfa4b22bd3530e2d97314d1db`) and
  [sample_files/simple_2.js:1](https://github.com/Wilfred/difftastic/blob/0.71.0/sample_files/simple_2.js#L1)
  (SHA256 `bd078aaecc828327c5b21ceb14a5f40e2e853f0468fb70b1b77d1aa08017ae31`).
  The upstream assertions are
  [tests/cli.rs:85](https://github.com/Wilfred/difftastic/blob/0.71.0/tests/cli.rs#L85)
  (`has_changes_requested_exit_code`) and
  [tests/cli.rs:106](https://github.com/Wilfred/difftastic/blob/0.71.0/tests/cli.rs#L106)
  (`check_only`). JavaScript language detection and an identical-input exit-0
  control are additional integration assertions. A Markdown Text fallback does
  not establish structural diffing.
- **Native fresh sessions and cross-family review:** installed `codex-cli
  0.159.3` and Claude Code `2.1.289` help were checked locally; the plan uses the
  selected Codex `rust-v0.160.0` source. Its
  [exec CLI:35](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/cli.rs#L35)
  documents ephemeral sessions, [CLI:60](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/cli.rs#L60)
  JSONL/final-message output, and
  [CLI:273](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/cli.rs#L273)
  enforces the review target/prompt conflicts. The fetched
  [official Codex noninteractive page](https://developers.openai.com/codex/noninteractive/)
  supports `codex exec` and complete JSONL output. Anthropic's headless route is
  [documented here](https://code.claude.com/docs/en/headless#add-claude-to-a-build-script);
  this network returned HTTP 403 for that page, so the actual command flags were
  verified against installed Claude Code `--help`, the original executor's
  successful native stream and the already-fetched upstream SDK command builder:
  [anthropics/claude-agent-sdk-python@v0.2.163:src/claude_agent_sdk/_internal/transport/subprocess_cli.py:574](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.163/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L574)
  supplies `--output-format stream-json --verbose`,
  [line 611](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.163/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L611)
  supplies `--max-turns`,
  [line 623](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.163/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L623)
  supplies `--model`,
  [line 637](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.163/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L637)
  supplies `--permission-mode`, and
  [line 778](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.163/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L778)
  supplies `--effort`. No unavailable page is treated as newly fetched.
  Named profile resolution comes from
  [codex-rs/core/src/config/mod.rs:2025](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/config/mod.rs#L2025):
  it resolves `<profile>.config.toml` under `CODEX_HOME`, so absence of legacy
  profile tables is not evidence of a missing named file. The optional command
  form is `codex exec -p omniroute review ...`.
  Codex JSONL intentionally emits only the thread ID at initialization:
  [event_processor_with_jsonl_output.rs:403](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L403).
  Preserve actual model/effort as a separate independent observation; requested
  flags do not supply it. The immutable review inputs are public repository
  commits [8c32a84b](https://github.com/seathatflowsinourveins/native-agent-stack/commit/8c32a84b246da66e43a6188c973741b09329e223)
  (Claude Opus trailer) and
  [b9dbe3c5](https://github.com/seathatflowsinourveins/native-agent-stack/commit/b9dbe3c5a09cdefca435cd78c7f3dad46ca883a4)
  (Codex trailer); local original commit objects verified those bindings.

Completeness critic: distinguish plugin installation from live hook execution,
Claude isolation from Codex guidance/activity, parsed diffing from the Text
fallback, complete native streams from a model's final summary, requested model
flags from observed route metadata, and local plan checks from destination
qualification. These distinctions feed the next Git capability sweep. The
existing claude-hud statusline and optional OmniRoute route are separate selected
capabilities; no new competing review service or global diff setting is adopted.

## Supporting upstream sources
Each owner's install and acceptance source is in install-plan.json. The following sources explain script glue, runtime pins, and service configuration.
- system prerequisites (plan wrapper adapts package list): [source, line 206](https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/8b51946ee16e542e544936e19bb793114fea948e/adoption/bootstrap-linux.sh#L206).
- runtime selection/global tool pins: [source, line 116](https://raw.githubusercontent.com/jdx/mise/v2026.10.0/docs/cli/use.md#L116).
- noninteractive mise: [source, line 4118](https://raw.githubusercontent.com/jdx/mise/v2026.10.0/settings.toml#L4118).
- process-scoped PATH without shell activation: [source, line 40](https://raw.githubusercontent.com/jdx/mise/v2026.10.0/docs/cli/env.md#L40).
- Node 24 exact runtime: [source, line 1](https://raw.githubusercontent.com/nodejs/node/v24.21.0/CHANGELOG.md#L1).
- Python 3.13 exact runtime: [source, line 1](https://raw.githubusercontent.com/python/cpython/v3.13.16/README.rst#L1).
- uv exact runtime: [source, line 1](https://raw.githubusercontent.com/astral-sh/uv/0.12.22/README.md#L1).
- Python CLI package isolation, version and interpreter selection: [source, line 172](https://raw.githubusercontent.com/astral-sh/uv/0.12.22/docs/guides/tools.md#L172).
- Playwright browser plus Ubuntu system dependencies: [source, line 122](https://raw.githubusercontent.com/microsoft/playwright/b630e71fcda7885885c459bcbb88e5bfa7c0a1ac/docs/src/browsers.md#L122).
- SDK/library isolated virtual environments: [source, line 21](https://raw.githubusercontent.com/astral-sh/uv/0.12.22/docs/pip/environments.md#L21).
- SDK published version: [source, line 1](https://registry.npmjs.org/@openai%2fcodex-sdk/0.160.0).
- Claude marketplace shell commands and idempotent registration: [source, line 634](https://code.claude.com/docs/en/plugins/cli-reference.md#L634).
- OTel config: [source, line 4](https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-releases/v0.162.0/distributions/otelcol-contrib/config.yaml#L4).
- OTel internal metrics: [source, line 1](https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector/v0.162.0/service/telemetry/otelconftelemetry/internal/migration/testdata/v0.3.0_metrics_prom_explicit.yaml#L1).
- Prometheus config: [source, line 1](https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/documentation/examples/prometheus.yml#L1).
- Loki config: [source, line 1](https://raw.githubusercontent.com/grafana/loki/v3.7.8/cmd/loki/loki-local-config.yaml#L1).
- Loki bind configuration: [source, line 6196](https://raw.githubusercontent.com/grafana/loki/v3.7.8/docs/sources/shared/configuration.md#L6196).
- Grafana bind configuration: [source, line 50](https://raw.githubusercontent.com/grafana/grafana/v13.2.3/conf/defaults.ini#L50).
- Dagu native installer options/unit: [source, line 109](https://raw.githubusercontent.com/dagucloud/dagu/v2.18.2/scripts/installer.sh#L109).
- Dagu coordinator defaults: [source, line 2029](https://raw.githubusercontent.com/dagucloud/dagu/v2.18.2/internal/cmn/config/loader.go#L2029).
- Rootless Docker install: [source, line 75](https://raw.githubusercontent.com/docker/docs/2d7809c7a74ba1e99609a44f421a15cbf8a4a4bc/content/manuals/engine/security/rootless/_index.md#L75).
- Rootless Docker user unit: [source, line 15](https://raw.githubusercontent.com/docker/docs/a20e3585feaf72f0be0ca0177e3bbb523f372ff2/content/manuals/engine/security/rootless/tips.md#L15).
- Rootless dbus prerequisite: [source, line 219](https://raw.githubusercontent.com/docker/docs/0571430b6a9c6ff1742baede7c265c3c5e9e3322/content/manuals/engine/security/rootless/troubleshoot.md#L219).
- OmniRoute loopback and WS: [source, line 158](https://raw.githubusercontent.com/diegosouzapw/OmniRoute/v3.8.51/docs/reference/ENVIRONMENT.md#L158).
- OmniRoute detached daemon: [source, line 56](https://raw.githubusercontent.com/diegosouzapw/OmniRoute/v3.8.51/bin/cli/commands/serve.mjs#L56).
- DeerFlow production publication: [source, line 45](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose.yaml#L45).
- Claude native version check: [source, line 23](https://raw.githubusercontent.com/anthropics/claude-code/v2.1.287/README.md#L23).
- Codex native version flag: [source, line 110](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/cli/src/main.rs#L110); native doctor command: [source, line 185](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/cli/src/main.rs#L185).
- Codex installer prompt variable: [source, line 100](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/scripts/install/install.sh#L100); prompt skipped when it is set: [source, line 845](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/scripts/install/install.sh#L845).
- Claude marketplace add from a git URL: [source, line 649](https://code.claude.com/docs/en/plugins/cli-reference.md#L649); marketplace clone directory: [source, line 171](https://code.claude.com/docs/en/plugins/loading.md#L171). Git `-C` and `rev-parse`: [source, line 63](https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/git.adoc#L63), [source, line 12](https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/git-rev-parse.adoc#L12).
- ast-grep through mise: [registry entry](https://raw.githubusercontent.com/jdx/mise/v2026.10.0/registry/ast-grep.toml#L1), [README, line 61](https://raw.githubusercontent.com/ast-grep/ast-grep/0.45.3/README.md#L61); structural-match form: [README, line 84](https://raw.githubusercontent.com/ast-grep/ast-grep/0.45.3/README.md#L84); exit status 1 without a match: [run.rs, line 349](https://raw.githubusercontent.com/ast-grep/ast-grep/0.45.3/crates/cli/src/run.rs#L349).
- Alertmanager: precompiled binaries [README, line 14](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L14); receiver fields [configuration.md, line 821](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/configuration.md#L821); upstream fixture with an integration-less receiver [conf.nil-match_re-route.yml, line 1](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/config/testdata/conf.nil-match_re-route.yml#L1); root route receiver [README, line 59](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L59); clustering off [README, line 394](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L394); web listen address [Procfile, line 1](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/Procfile#L1) and [main.go, line 63](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/cmd/alertmanager/main.go#L63); configuration check [configuration.md, line 620](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/configuration.md#L620); readiness [management_api.md, line 22](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/management_api.md#L22).
- mattpocock/skills: install command [README, line 52](https://raw.githubusercontent.com/mattpocock/skills/v1.2.3/README.md#L52), setup skill in every selection [README, line 55](https://raw.githubusercontent.com/mattpocock/skills/v1.2.3/README.md#L55) and its role [README, line 198](https://raw.githubusercontent.com/mattpocock/skills/v1.2.3/README.md#L198). The `skills` installer 1.7.0 (tag v1.7.0): agents and flags [README, line 88](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/README.md#L88), non-interactive form [README, line 111](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/README.md#L111), list [README, line 164](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/README.md#L164), telemetry variable [README, line 540](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/README.md#L540); agent names [agents.ts, line 155](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/agents.ts#L155) and [line 224](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/agents.ts#L224); `owner/repo#ref` [source-parser.ts, line 284](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/source-parser.ts#L284) with its unit test [line 129](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/source-parser.test.ts#L129); clone with `--branch` [git.ts, line 295](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/git.ts#L295); lock entry `ref` [skill-lock.ts, line 20](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/skill-lock.ts#L20); `list --json` fields [list.ts, line 113](https://raw.githubusercontent.com/vercel-labs/skills/v1.7.0/src/list.ts#L113).

## Binary quotation boundary
Transport/checksum/user-prefix placement is thin script glue around the selected upstream binary routes, adapted from the quoted OTel HTTPS transport recipe and published release checksums. No constructed download wrapper is represented as a verbatim owner installer. Versions, filenames, destinations, noninteractive extraction flags, and loopback endpoints are explicit parameters.
Prometheus has a prose download link plus a quoted tar command; that transport quotation gap is retained. Alertmanager's README describes the precompiled binaries in prose only (README.md:14-19) and quotes no tar command: its `tar xvfz` and `install` steps are the Prometheus row's form applied to Alertmanager's archive, script glue, with the sha256 taken from the release's own `sha256sums.txt`. Loki's release-note template supplies curl/unzip/chmod commands. Grafana's versioned official page supplies wget/tar commands and checksum. Loki and Grafana are measurement-only.

### OTel Collector Contrib — source quotation (UNRUN at the source review; installed and started in the clean run of 2026-10-02)
[source](https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/9f912d59a165ded5dec82d0e1a94c2aef54e5c57/content/en/docs/collector/install/binary/linux.md#L87)
```sh
curl --proto '=https' --tlsv1.2 -fOL https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v{{% param vers %}}/otelcol_{{% param vers %}}_linux_amd64.tar.gz
tar -xvf otelcol_{{% param vers %}}_linux_amd64.tar.gz
```
Published artifact: https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.162.0/otelcol-contrib_0.162.0_linux_amd64.tar.gz; SHA256 `fcc063749f730f8c21fe29f2d340ff174f5f1c5885bd3156fb6c985a3036fcc3`.

### Prometheus — source quotation (UNRUN at the source review; installed and started in the clean run of 2026-10-02)
[source](https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/getting_started.md#L18)
```sh
tar xvfz prometheus-*.tar.gz
```
Published artifact: https://github.com/prometheus/prometheus/releases/download/v3.15.0/prometheus-3.15.0.linux-amd64.tar.gz; SHA256 `2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0`.

### Alertmanager — source description (UNRUN at the source review; installed and started in the clean run of 2026-10-02)
[source](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L14)
```text
Precompiled binaries for released versions are available in the download section on prometheus.io. Using the latest production release binary is the recommended way of installing Alertmanager.
```
Published artifact: https://github.com/prometheus/alertmanager/releases/download/v0.34.1/alertmanager-0.34.1.linux-amd64.tar.gz; SHA256 `265b9d1e55ef0d5306a436018af6d2b686c2ce051f03d968f7464ecb1372a7e8` (the line for this archive in the release's `sha256sums.txt`, equal to the digest GitHub reports for the asset). The archive holds `alertmanager`, `amtool`, a sample `alertmanager.yml`, `NOTICE` and `LICENSE`.

### Loki (measurement-only) — source quotation, UNRUN
[source](https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24)
```sh
curl -O -L "https://github.com/grafana/loki/releases/download/${DRONE_TAG}/loki-linux-amd64.zip"
unzip "loki-linux-amd64.zip"
chmod a+x "loki-linux-amd64"
```
Published artifact: https://github.com/grafana/loki/releases/download/v3.7.8/loki-linux-amd64.zip; SHA256 `62aea42c9cba52cd1642b3666ab37019a0ce4c24ab50b07e85dccc8d812f7d61`.

### Grafana (measurement-only) — source quotation, UNRUN
[source](https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux#L2819)
```sh
wget https://dl.grafana.com/grafana/release/13.2.3/grafana_13.2.3_36482603486_linux_amd64.tar.gz
tar -zxvf grafana_13.2.3_36482603486_linux_amd64.tar.gz
```
Published artifact: https://dl.grafana.com/grafana/release/13.2.3/grafana_13.2.3_36482603486_linux_amd64.tar.gz; SHA256 `6107ad27016296aac38e0d7ffa8753ab540b5541ad27e94790f771289d733235`.

## Service starts — separate from installation
Status: all UNRUN at the source review. In the clean run of 2026-10-02 the OTel collector, Prometheus, Alertmanager and Ollama were started once with the commands below in a throwaway distribution and passed their health checks, and Docker and Dagu were started by their installers. The gateway and the research harnesses were not started; Loki and Grafana are measurement-only and were not installed.
These invoke documented upstream foreground/daemon forms. No systemd user unit was created except those installed upstream by Docker and Dagu.
The shell variables below are the portable prefixes defined in install.sh/accept.sh; run foreground services in their own terminals. Configuration is installed from config/ without overwriting existing files.
- OTel: `NS2604_OBSERVABILITY_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/observability" otelcol-contrib --config "$config_root/otel.yaml"`. Only OTLP grpc21317/http21318, health21333, and metrics21888 bind loopback; optional pprof/zpages/Jaeger/Zipkin are omitted from the upstream distribution template.
- Prometheus: `prometheus --config.file="$config_root/prometheus.yaml" --web.listen-address=127.0.0.1:21090 --storage.tsdb.path="$tool_root/prometheus/data"`. [CLI flags](https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/command-line/prometheus.md#L17).
- Alertmanager: `alertmanager --config.file="$config_root/alertmanager.yaml" --web.listen-address=127.0.0.1:21093 --cluster.listen-address= --storage.path="$tool_root/alertmanager/data"`. [Flags used together upstream, Procfile line 1](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/Procfile#L1); [flag definitions, main.go lines 51-52, 63](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/cmd/alertmanager/main.go#L51); an empty `--cluster.listen-address=` turns clustering off ([README, line 396](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/README.md#L396)); readiness is `GET /-/ready` ([management API, line 22](https://raw.githubusercontent.com/prometheus/alertmanager/v0.34.1/docs/management_api.md#L22)). HTTP21093 binds loopback; no cluster listener is bound.
- Loki (measurement-only): `cd "$tool_root/loki"`, then `loki -config.file="$config_root/loki.yaml"`. [Upstream foreground invocation](https://raw.githubusercontent.com/grafana/loki/v3.7.8/docs/sources/setup/install/local.md#L74). HTTP21300/grpc21396 bind loopback; persistent paths are relative to this owned directory.
- Grafana (measurement-only): change to the extracted Grafana directory, then `./bin/grafana server --config "$config_root/grafana.ini"`. [Upstream tar/foreground command](https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/setup-grafana/start-restart-grafana.md#L107), [custom config option](https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/setup-grafana/configure-grafana/_index.md#L39). HTTP21301 and optional gRPC21302 bind loopback; default system-wide service is not installed.
- Ollama: D-ollama-2 places only the updated owner-approved on-demand user unit, then uses native user daemon-reload/enable --now; the exact warmup is historical and unreferenced. The earlier manual ollama serve recipe is superseded. [Ollama0.35.0 native system-unit form](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/linux.mdx#L57) supplies the source for this explicit user adaptation; HTTP21434 remains loopback and only the co-op applies it on the shared host.
- OmniRoute: export the plan's omniroute.env.example with `set -a; . <file>; set +a` (since wave 2 its lines are plain `NAME=value` lines, which a plain `.` does not export; a systemd unit reads them through `EnvironmentFile=`), then `omniroute serve --port 21128 --no-open --daemon`. HTTP21128/WS21129, and the embed proxy on 21131, bind loopback. Provider configuration stays native.
- Dagu: upstream installer starts user dagu.service at HTTP21080, coordinator127.0.0.1:50055. start-all disables coordinator/scheduler auxiliary health listeners.
- DeerFlow (superseded in wave 2, 2026-10-03: DeerFlow now runs as the embedded `DeerFlowClient`, with no service, port or Compose stack; section "Wave 2" below): after configuring models[].base_url and OPENAI_API_KEY, `cd "$tool_root/deer-flow"` then `BIND_HOST=127.0.0.1 PORT=2026 make up`. [Upstream production start](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/README.md#L330). Production Compose publishes only loopback2026; no systemd user unit is proposed.
Rootless Docker exposes a Unix socket, no host TCP port. All assigned host ports avoid the supplied collision set.
## Anti-pattern corrections and verification path
- Incorrect assumption: root registry.toml exists at mise v2026.10.0. gh contents API returned404; tagged tree and registry/<tool>.toml reads establish the split registry. No tag was substituted.
- Wrong-owner risk: short mise actionlint selects rhysd/actionlint. Tagged registry and kjanat/docs/install.md:208,223 establish the qualified github backend.
- Wrong package pin: GPT tag v3.7.0 is not a pip version3.7.0. Tagged pyproject.toml:23 declares0.16.0; tagged requirements/source installation was selected.
- Wrong action reference: Dependabot Core is a GitHub service/repository, not a root Action. Tagged tree lacks an entrypoint; tagged README:42 supplies the supported configuration form (the row is a reviewed pointer for repository workflows, not a host installation).
- Earlier Claude marketplace shell gap resolved: official CLI reference:634,647 plus pinned v2.1.287 CHANGELOG:50 and installed value-free help prove command/ref support. Re-registration is documented idempotent. No plugin installation was attempted. Corrected by the real-distribution run: the `@<ref>` form takes a branch or tag, not a commit, and the shorthand cloned over SSH, so the plan now registers the HTTPS clone URL, unpinned (last section).
- Codex unchanged marketplace source/ref is idempotent: [rust-v0.160.0 implementation](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/core-plugins/src/marketplace_add.rs#L114) returns already_added successfully. A different existing source/ref remains an explicit failure.
- Static script review corrected missing make/native-client selective dependencies, masked mise env failure, caller-dependent Worktrunk cwd, and grouped research early returns. Each independent research install is now attempted and failures remain nonzero; no generated script was executed to test this.
- Supplemental Grafana citation correction: the guessed start-restart-grafana/index.md path returned404; the tagged tree and raw read establish start-restart-grafana.md. The install source itself returned200 on its first required fetch.
## Completeness critic
Reviewed omitted modalities/classes: native self-updating clients, SDK libraries, CLI tools, marketplaces, workflow-only owners, rootless containers, services/auxiliary listeners, repository practices, and excluded overlaps.

Original review limits, updated after round 1: route enum has no precise library/marketplace labels; individual security plugins are unselected; Dependabot has no uses reference; host acceptance is unavailable for workflow-only/guard rows; most services ship no documented user unit; Prometheus has no quoted transport command. At the source review, revised commands, model/account setup, WSL GPU execution and real-distribution rootless/systemd/browser acceptance were unrun. The clean run of 2026-10-02 then exercised the revised commands, and both throwaway-distribution runs of that day exercised the rootless Docker and systemd user-session acceptance (VALIDATION.md). Model/account setup, GPU execution and the browser check (its owner is measurement-only and was not installed) remain unrun in the throwaway distributions. On the destination distribution the 64-row revision ran once (main 6652b78e); the record of that run is private, and its public receipt comes with that distribution's acceptance. Git's former route gap is resolved below.
DeerFlow's make doctor is documented but requires host pnpm/nginx/backend environment, inapplicable to the selected Compose install. Its shipped /health/ready probe is used instead; no alternative runtime manager or passed container check is claimed.
No benchmark, convergence/SOTA superiority, billing saving, new model run, or E2E acceptance is claimed. This record feeds the next foundation lifecycle/source sweep.

## Round 1 repairs and staged acceptance

This repair is bounded to the supplied owners, existing pins and coordinator logs. The coordinator invoked search-first; read-only Sol/Max researchers supplied leads, and their relevant pinned primary source was fetched before integration. The available local diagnosis/search/OpenAI documentation skills cover this repair; no new installer, runtime manager, test framework or dependency was selected. Shell network reads and public GitHub release/source metadata were used; no credential files, active client configuration or environment values were read or printed by the coordinator. Large archive listings and tracebacks were processed outside the model; VALIDATION.md retains the lines that carry each failure.

The Bash owner-function dispatcher is the existing plan wrapper. The new stage selection extends it; native tests stay upstream commands. Every selected row has a sourced post-install entry, with up to two additional service/model checks. Five workflow/adoption pointers had no installed host executable (this revision keeps one of them, the credential guard, as an installed row; attest, Dependabot, CodeQL SARIF and Claude Code Action are no longer installed rows); the unavailable entry preserves the gap and is skipped rather than inventing success. The original sandbox and Worktrunk smokes remain unchanged. All original service endpoints and SDK/model examples remain available in their appropriate stages.

### Plan defect sources and fixes

- **Git:** round1 `git.install.log:1–2` refuses the route and reports 78, while `mise.install.log:11` already records Ubuntu Git `1:2.53.0-1ubuntu1`. Git's own maintained website recommends the distribution package manager and explicitly quotes `apt-get install git`: [git/git-scm.com @ 422e163b, content/install/linux.html:14–19](https://github.com/git/git-scm.com/blob/422e163b96cdcff929cd63028657597752d4b9d7/content/install/linux.html#L14). The plan now declares `apt`, runs the idempotent Ubuntu package command, marks the release as Ubuntu's apt candidate and uses the documented [Git version option](https://github.com/git/git/blob/v2.56.0/Documentation/git.adoc#L44). The installer prerequisite list includes this slot; neither a PPA nor the reviewed upstream v2.56.0 is claimed as an installed lock.
- **Mise:** round1 `mise.accept.log:1` records only smoke exit 1. The wrapper imported `mise env` without activation or shims. At v2026.10.0/`bc11f90c`, [doctor/mod.rs:532–549](https://github.com/jdx/mise/blob/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/src/cli/doctor/mod.rs#L532) declares that condition an error and prefers shims for noninteractive setup. [shims.md:70–80](https://github.com/jdx/mise/blob/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/docs/dev-tools/shims.md#L70) documents process PATH setup; [directories.md:53–58](https://github.com/jdx/mise/blob/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/docs/directories.md#L53) and [98–106](https://github.com/jdx/mise/blob/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/docs/directories.md#L98) establish the data/shim directories. Install and acceptance add the default shim path, respecting environment overrides. The full doctor remains; all mise.toml pins stay unchanged and its instructions match this route. [shims.md:101–102](https://github.com/jdx/mise/blob/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/docs/dev-tools/shims.md#L101) says `mise use` rebuilds shims. The exact historical diagnostic row remains unknown.
- **Playwright:** round1 `playwright-cli.accept.log:6–7` requests missing system Chrome, while install log:658 records bundled Chromium build 1247. v0.1.22's [package.json:24–26](https://github.com/microsoft/playwright-cli/blob/b85c7a736bb473bf55b584e54a09ffa698d6d871/package.json#L24) confirms the original dependency pin was correct. Its bundled Playwright revision `e8149b82` [config.ts:224–230](https://github.com/microsoft/playwright/blob/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/mcp/config.ts#L224) defaults unspecified selection to system Chrome; [285–286](https://github.com/microsoft/playwright/blob/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/mcp/config.ts#L285) maps explicit `chromium` to the installed Chrome for Testing. JSON/script now install through the [native install-browser command](https://github.com/microsoft/playwright/blob/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/cli-client/program.ts#L346) with [documented browser/dependency arguments](https://github.com/microsoft/playwright/blob/e8149b8257d32dcf8f72573ecc43e72439da7080/packages/playwright-core/src/tools/cli-daemon/commands.ts#L1247). The real open/close smoke selects `--browser=chromium`; it has not been replaced by a help/version check.
- **OmniRoute:** round1 `gpt-gateway.accept.log:2,9` rejects `--json` and advertises `--no-liveness`. v3.8.51/`c1e30b76` [program.mjs:18–22](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/program.mjs#L18) defines global `--output json`; [doctor.mjs:630–655](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/commands/doctor.mjs#L630) supplies the actual flags and output propagation. This takes precedence over the incorrect [CLI-TOOLS.md:653–655](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/docs/reference/CLI-TOOLS.md#L653) example. Post-install uses the full local diagnostic mode; [doctor.mjs:597–600](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/commands/doctor.mjs#L597) excludes only the service HTTP/machine-token checks when liveness is disabled. The unchanged upstream [fresh-database test:74–82](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/tests/unit/cli-doctor-command.test.ts#L74) expects no failures with that option. Full liveness remains in service-health. Neither diagnostic was run against the active private host.

### Additional stage sources and limitations

Each version fallback has its source in the JSON. The new local service checks are stronger than a version where upstream supplies a validator: [OTel command_validate.go:15–26](https://github.com/open-telemetry/opentelemetry-collector/blob/62cdad2ea133239380b44d20d84eb26e114779b6/otelcol/command_validate.go#L15) explicitly validates without running the collector; [Prometheus promtool.md:91](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/command-line/promtool.md#L91) checks configuration using the binary already extracted by this installer; [Loki config_wrapper.go:54](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/pkg/loki/config_wrapper.go#L54) and [main.go:108–110](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/cmd/loki/main.go#L108) verify configuration before service construction. The original HTTP probes stay in service-health.

Codex doctor exists at the exact target pin: [rust-v0.160.0 main.rs:185–186](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/main.rs#L185). Its [doctor.rs:1287–1294](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/doctor.rs#L1287) marks absent credentials FAIL; [319–350](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/doctor.rs#L319) propagates failure. No authentication-free diagnostic mode was found in the installed help, exact-release notes or [pinned command definition:154–186](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/doctor.rs#L154). Post-install is version-only; the full doctor remains after sign-in. Official [noninteractive documentation](https://developers.openai.com/codex/noninteractive/) confirms that SDK/exec use native authentication or explicitly configured credentials. The bare historical doctor exit 1 does not identify which other diagnostic rows also failed.

SDK version checks do not run models. Claude's [public version export](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/src/claude_agent_sdk/__init__.py#L68) and OpenHands' own [metadata-version use](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/__init__.py#L113) establish the Python forms. [npm ls](https://github.com/npm/cli/blob/bfacd33ccbcd908480610703b60455d2da5b57a9/docs/lib/content/commands/npm-ls.md#L13) checks the local SDK package/version and invalid or missing dependencies. GPT Researcher imports the source checkout and reads its [declared version](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/pyproject.toml#L23), because this route installs requirements and does not install distribution metadata. Every original model/research example is retained after native/provider configuration.

Ollama's [version handler](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L2181) prints the client version with a connection warning when the daemon is absent, without starting it or downloading a model. Its [model inventory command](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/cli.mdx#L94) now checks the running local server separately. The original embeddinggemma smoke is retained after model provisioning. Its behavior after connecting remains unverified; the recorded failure establishes only the missing daemon.

DeerFlow uses upstream [Compose config --quiet](https://github.com/docker/compose/blob/5f94fb0aa42a2cd1248c6e6c7fafb87546b9c8de/docs/reference/compose_config.md#L27) for preparation acceptance (Phoenix, which shared it, left the plan). This is explicitly an integration check of configuration, not an upstream app self-test, installed-image evidence or service health. DeerFlow `make docker-init` selects the dev file/project in [scripts/docker.sh:18–24](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/scripts/docker.sh#L18); [122–129](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/scripts/docker.sh#L122) requires DEER_FLOW_ROOT. [Install.md:44–47](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/Install.md#L44) distinguishes preparation from validation/build success; [docker.sh:278](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/scripts/docker.sh#L278) can tolerate an image pull failure. This revision corrects the previous prose conflation: the post-install config check matches dev preparation, while the retained production readiness probe applies only to the separately documented production `make up` start. Actual image/app readiness remains a separate unrun boundary.

Harbor's successful installation at log:342–343 precedes rootless Docker's missing-kernel-requirement refusal. At the exact Engine revision, [dockerd-rootless-setuptool.sh:197–207](https://github.com/moby/moby/blob/8af9fe3a36bab3e039862a2ab1cef1880c9b4d03/contrib/dockerd-rootless-setuptool.sh#L197) checks the iptables kernel module; [211–213](https://github.com/moby/moby/blob/8af9fe3a36bab3e039862a2ab1cef1880c9b4d03/contrib/dockerd-rootless-setuptool.sh#L211) shows that bypassing it would disable daemon iptables. The gate is retained. Upstream [nested-rootless guidance](https://github.com/docker/docs/blob/0571430b6a9c6ff1742baede7c265c3c5e9e3322/content/manuals/engine/security/rootless/tips.md#L82) needs a privileged rootless-in-Docker container; the supplied container is not that environment. Dagu's user-service installation and sandbox/worktree smokes likewise remain real-distribution checks, with no bypass substituted.

### Corrections recorded this turn

- The research lead that Codex doctor was invalid was disproven by installed `doctor --help` and the pinned target's main.rs/doctor.rs above. The locally inspected client was 0.159.3, whereas round1 installed 0.160.0; only exact-target source supports the target behavior. No local doctor report or native configuration/credential store was read. That helper's initial temporary HOME/CODEX_HOME override was stopped after the developer restriction was identified; no further override was used. Its help results are supporting syntax evidence, not target acceptance.
- The initial Harbor lead that Docker failed before its uv install was wrong. Exact round1 log:342–343 verifies that Harbor installed, and :508–509 identifies the later Docker failure. No Harbor package/pin repair is supported by this evidence.
- The Playwright lead about a dependency version mismatch was disproven by the pinned package.json and installed-browser log. Browser selection was the actual mismatch; native browser installation removes the duplicated dependency pin without changing the reviewed CLI release.
- The initial Ollama inventory citation guessed a nonexistent `ollama list` example. The fetched exact CLI document names `ollama ls` at line 97; JSON and shell now use that command and citation.

### Independent source review and acceptance

Astra/Max trigger: the pinned OmniRoute documentation's `--json` example conflicts with the installed help and implementation; the Codex unsupported-command lead also conflicted with primary evidence. A read-only stack-verifier checked original logs/source and reran the specified JSON, Bash syntax, owner inventory, skip, invalid-stage and synthetic dispatcher checks. All structural checks returned the expected status. It confirmed all 53 rows, seven exclusions, sixteen unchanged passing checks, the five explicit unavailable entries and the cause counts; it found two applicability/false-pass defects, both repaired:

- Mise doctor reads the current-directory toolset: [doctor/mod.rs:1107–1121](https://github.com/jdx/mise/blob/bc11f90c74eba23bf0d7350efb540e62fb7d9ffd/src/cli/doctor/mod.rs#L1107) errors when selected tools are missing. Running from the plan folder would select the complete inventory mise.toml after a selective install. Its post-install command now changes to the owned global tool directory, matching `mise use -g` and the PATH loader. The full doctor and global pins remain intact.
- OmniRoute [doctor.mjs:482–486](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/commands/doctor.mjs#L482) warns about unreachable HTTP; [668](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/commands/doctor.mjs#L668) returns zero with warnings alone. Service-health now first requires a successful HTTP probe of the dedicated upstream [readiness alias](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/app/readyz/route.ts#L1). [healthz/route.ts:12–28](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/app/healthz/route.ts#L12) returns 200 only when the server lifecycle is ready, otherwise 503; no sign-in or provider call is required. The full doctor remains after this strict HTTP gate. The curl form is the existing plan's native HTTP integration-check pattern, parameterized with this sourced endpoint.

Acceptance result: the verifier confirmed both repairs from the exact sources and reran Bash syntax plus the expanded dispatch/regression fixtures with exit 0; no findings remained within its follow-up scope. The upstream [proxy matcher](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/proxy.ts#L35) excludes the readiness path from authentication. Native runtime/service/provider acceptance is still unrun. The local fixture checks only real Bash command selection, working-directory selection, readiness-before-doctor sequencing and failure propagation, using stubbed owner calls; it is not upstream acceptance.

### Repair completeness critic

The review covers all 18 failures, preserves all 16 passed owner commands, retains every inventory row/exclusion and both independent research owners, separates local configuration checks from service/model work, and leaves sandbox/worktree/runtime smokes intact. Remaining limits are explicit: three opaque historical doctor reports, five workflow/adoption checks without a host executable, Compose image/build/app readiness, private sign-ins/provider routes and real WSL systemd/kernel/GPU behavior. No broader pin update, provider call, service start, install sweep, commit or push was performed by this repair.

## Revision after the real-distribution run and the merged manifest

Pins opened for this revision, each read at its pin: ast-grep tag `0.45.3` (commit `979c143639e3588c31f563091e69398683ed34f0`, release of 2026-08-31); Alertmanager tag `v0.34.1` (commit `73c6bfe7393929211294c1954f30d8ed78e4d0ad`, release of 2026-09-17); mattpocock/skills tag `v1.2.3` (commit `6acc160e4e0cd062dbbbd7a1b26ae92855edf07e`, release of 2026-08-06); the `skills` installer tag `v1.7.0` (the npm package's `gitHead` and the tag's commit are both `7407f3893ad4dceab546ac002c3ef806e4000c73`); the mise `v2026.10.0` registry; Codex `rust-v0.160.0` (commit `a956835d020762cb2b570053af06f643a11c0ecc`); Trail of Bits commit `82fe8226252622fa807643bdca1710901198553a`. The Codex installer served at the documented URL is byte-identical to `scripts/install/install.sh` at `rust-v0.160.0` (sha256 `150e3cf675682efeaac115aa3747add3f27887896d04ce6d0b56478d8b428bf6`), so the line numbers below describe what a run executes.

### Repairs from the real run

- **Codex installer prompt (finding 1).** The installer reads `CODEX_NON_INTERACTIVE` ([install.sh:6](https://github.com/openai/codex/blob/rust-v0.160.0/scripts/install/install.sh#L6)), documents it in its help as "Set to 1, true, or yes to skip prompts" ([:100](https://github.com/openai/codex/blob/rust-v0.160.0/scripts/install/install.sh#L100)), and returns before the `/dev/tty` prompt when it is set ([:842–856](https://github.com/openai/codex/blob/rust-v0.160.0/scripts/install/install.sh#L842), [:899–904](https://github.com/openai/codex/blob/rust-v0.160.0/scripts/install/install.sh#L899)). The line is README.md:19's command with the variable on `sh`: `curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh`.
- **Trail of Bits marketplace (finding 2).** The Claude CLI reference lists an `https://` URL ending in `.git[#ref]` as a `git` source that is cloned as given ([cli-reference.md:649](https://code.claude.com/docs/en/plugins/cli-reference.md#L649)) and speaks of a marketplace "added with a branch or tag `ref`" as the pinned kind ([:745](https://code.claude.com/docs/en/plugins/cli-reference.md#L745)); the clone lands in `marketplaces/<name>/` under the plugins root ([loading.md:171](https://code.claude.com/docs/en/plugins/loading.md#L171)), and the marketplace's name at the reviewed commit is `trailofbits` (`.claude-plugin/marketplace.json`). The repository has no tag, so the Claude line is unpinned and the acceptance compares `git -C <clone> rev-parse HEAD` ([git.adoc:63](https://github.com/git/git/blob/v2.56.0/Documentation/git.adoc#L63), [git-rev-parse.adoc:12](https://github.com/git/git/blob/v2.56.0/Documentation/git-rev-parse.adoc#L12)) with the reviewed commit; at lookup that commit was the head of `main`. The real run's failure, a missing SSH host key for the shorthand, is an observation. The client documentation instead says the shorthand tries SSH and falls back to HTTPS ([discover-plugins.md:241](https://code.claude.com/docs/en/discover-plugins.md#L241)); the full HTTPS URL avoids that check either way. The Codex registration, `--ref <commit>`, worked as written and is unchanged.
- **Checkout (finding 3).** Two acceptance checks (`wt list`, `python3 scripts/validate.py`) change into `repo_root`; the new-distribution recipe's step F7 (`adoption/platforms/linux-wsl2-new-distro.md`, "Clone origin/main") clones the repository. The scripts test `[[ -e "$repo_root/.git" ]]` rather than call `git`, because `install.sh` and `accept.sh` define a `git` function for the Git row.

### Rows added

- **ast-grep (`structural-search`).** mise's registry entry lists `aqua:ast-grep/ast-grep` first and tests `sg --version` ([registry/ast-grep.toml:1,3](https://github.com/jdx/mise/blob/v2026.10.0/registry/ast-grep.toml#L1)); ast-grep's README documents `mise use -g ast-grep` ([:61](https://github.com/ast-grep/ast-grep/blob/0.45.3/README.md#L61)) and the form `ast-grep -p '$A && $A()' -l ts -r '$A?.()'` ([:84](https://github.com/ast-grep/ast-grep/blob/0.45.3/README.md#L84)); a pattern search exits 1 when nothing matches ([run.rs:349](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/run.rs#L349)). The acceptance uses the complete README rewrite-preview form on a temporary file, asserts the replacement, and requires exit 1 on a nonmatching control, and runs `ast-grep`, not the registry test's `sg`: on Ubuntu `/usr/bin/sg` is `newgrp` from the `login` package, which a mise shim hides only while the shims directory comes first on `PATH`.
- **Alertmanager (`alerting`).** Release-binary form as for Prometheus (see the quotation boundary above). The configuration is `route: {receiver: sink}` and `receivers: [{name: sink}]`: a receiver is a name plus optional integration lists ([configuration.md:821–829](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L821)), upstream's own test fixture uses a receiver with none ([conf.nil-match_re-route.yml:1–8](https://github.com/prometheus/alertmanager/blob/v0.34.1/config/testdata/conf.nil-match_re-route.yml#L1)), and the root route must name a receiver ([README.md:59–62](https://github.com/prometheus/alertmanager/blob/v0.34.1/README.md#L59)). Port 21093 is in the plan's 21xxx band beside Prometheus's 21090, and no other row or config file uses it (`check_plan.py` checks that no row or config file claims a port twice). `--web.listen-address` appears upstream only in the HA example `Procfile` and in the flag registration in `main.go`, not in documentation prose. `amtool` stays in the extracted directory, as `promtool` does.
- **mattpocock/skills (`engineering-process-skills`).** The five skills of the critic's verdict exist at `v1.2.3` under `skills/engineering/` (`tdd`, `diagnosing-bugs`, `codebase-design`, `domain-modeling`) and `skills/productivity/` (`writing-for-agents`), with `setup-matt-pocock-skills` under `skills/engineering/`. The README asks that the setup skill be one of the selected skills ([:55](https://github.com/mattpocock/skills/blob/v1.2.3/README.md#L55)); it is user-invoked and run once per repository ([:198](https://github.com/mattpocock/skills/blob/v1.2.3/README.md#L198)), which is not part of this plan. The installer at `v1.7.0` accepts `-g`, `-a <agents>`, `-s <skills>` and `-y` as its non-interactive form ([README:110–111](https://github.com/vercel-labs/skills/blob/v1.7.0/README.md#L110)), names the agents `claude-code` and `codex` ([agents.ts:155, 224](https://github.com/vercel-labs/skills/blob/v1.7.0/src/agents.ts#L155)), disables telemetry through `DISABLE_TELEMETRY` ([README:540, 554](https://github.com/vercel-labs/skills/blob/v1.7.0/README.md#L540), [telemetry.ts:86–88](https://github.com/vercel-labs/skills/blob/v1.7.0/src/telemetry.ts#L86)), parses `owner/repo#ref` ([source-parser.ts:284–314, 540–549](https://github.com/vercel-labs/skills/blob/v1.7.0/src/source-parser.ts#L284), unit test [source-parser.test.ts:129](https://github.com/vercel-labs/skills/blob/v1.7.0/src/source-parser.test.ts#L129)), clones with `git clone --depth 1 --branch <ref>` ([git.ts:295–302](https://github.com/vercel-labs/skills/blob/v1.7.0/src/git.ts#L295)) and records the ref in its global lock file at `$XDG_STATE_HOME/skills/.skill-lock.json` or `$HOME/.agents/.skill-lock.json` ([skill-lock.ts:20–21, 63–72](https://github.com/vercel-labs/skills/blob/v1.7.0/src/skill-lock.ts#L20)). The `#ref` pin is not in the installer's README; it rests on the source and its unit test and is first exercised by the target-distribution run. The acceptance reads `list --json` ([list.ts:113–127](https://github.com/vercel-labs/skills/blob/v1.7.0/src/list.ts#L113)), whose `agents` field holds display names (`Claude Code`, `Codex`), and the lock's `ref`; `jq` comes with the plan's prerequisite packages.

### Observations made while writing this revision

These are scratch observations, not acceptance and not target-distribution runs. The upstream `v0.34.1` Alertmanager archive (sha256 as above) and the `0.45.3` ast-grep release asset were extracted in a scratch directory outside the home directory and run with a scratch `HOME`; nothing was installed. `amtool check-config` accepted `config/alertmanager.yaml` (exit 0). `alertmanager` with `--config.file`, `--web.listen-address=127.0.0.1:21093`, `--cluster.listen-address=` and `--storage.path` answered `GET /-/ready` and `GET /-/healthy` with 200, bound no cluster listener, and was stopped. `ast-grep --version` printed `ast-grep 0.45.3`; the probe pattern on a matching temporary file exited 0 and on a non-matching one exited 1. The skills acceptance program and the Trail of Bits comparison were run against stand-ins (a canned `list --json` output and lock file, and a scratch git repository), with each planted variation failing as intended; those fixtures are our own, not upstream tests. `npx --yes skills@1.7.0 add --help` and `list` flags were read from the installer's own help. The installer's `add` was not run.

## Rows added from the layer consensus (2026-10-02)

Two of the five rows install, both through the `skills` installer that the plan already pins to 1.7.0. The pins are the commits of the consensus record (`evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`). Sources opened for them on 2026-10-02:

- **The two folders.** The GitHub tree API at `vercel-labs/skills` commit `7407f3893ad4dceab546ac002c3ef806e4000c73` (the record's release `v1.7.0`, and the installer's own commit, see above) gives `skills/find-skills` the tree hash `76a98a285cb0434f3d39e1a873823556330e398b` and its `SKILL.md` the blob `a41bdd074bb587afd861332cf2f473f3154de4d7`; the folder holds that one file, and it is the only skill folder of the repository. At `anthropics/skills` commit `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` the tree API gives `skills/skill-creator` the tree hash `3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6` and its `SKILL.md` the blob `65b3a402dbd09b8e83f9d637c6b553875189085c`; the folder holds 18 files in five subfolders, beside 18 other skill folders. Both blobs are the ones the record names. Line 2 of each `SKILL.md` is its `name` (`find-skills`, `skill-creator`), read from local files whose git blob hashes equal those two blobs.
- **One named skill, no prompt, telemetry off.** `-s` installs specific skills by name ([README:89](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L89)), `-g -a <agent> -y` is the documented non-interactive form ([:110–111](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L110)) and `DISABLE_TELEMETRY` turns telemetry off ([:540](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L540)). The README inside the npm package 1.7.0 has the git blob hash `ac7372a0d64b1731ef331f991a480704bfe6cbfb`, which is the README blob of the tree at that commit, so these line numbers are the commit's.
- **A commit as the ref.** `cloneRepo` first runs `git clone --depth 1 --branch <ref>`. When the ref is 40 hexadecimal characters and the clone fails with a missing-ref error, it fetches that commit with `--depth 1` and checks out `FETCH_HEAD` ([git.ts:295–322](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/git.ts#L295), `isCommitSha` at [:30](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/git.ts#L30), `isMissingRefError` at [:47](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/git.ts#L47), `cloneAtSha` at [:65–77](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/git.ts#L65)); the comment above the fallback says that `--branch` cannot target a bare commit. `git.ts` was fetched at that commit and its git blob hash equals the tree's (`5605bc7e7c673e0459d345a1c6bb885e06bb2cc9`). The rest of this entry is read in the bundled `dist/cli.mjs` of the npm package 1.7.0, not in the TypeScript source: with a ref the installer skips its download path and clones (`tryBlobInstall` returns nothing when a ref is set), and for a global install from GitHub it records as `skillFolderHash` the folder's tree hash from the GitHub tree API for that ref (`fetchRepoTree`, `getSkillFolderHashFromTree`). When that API read fails it records a hash of the files instead (`computeSkillFolderHash`), and the acceptance, which expects the tree hash, then fails.
- **Claude Code only (`skill-authoring`).** `--copy` copies files "instead of symlinking to agent directories" ([README:91](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L91)); the symlink method keeps "a canonical copy" that each agent links to ([:141–142](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L141)). In the bundled `dist/cli.mjs` the canonical directory of a global install is `$HOME/.agents/skills` (`getCanonicalSkillsDir`), an agent whose project path is `.agents/skills` uses that directory for its global skills too (`getAgentBaseDir`; Codex is such an agent, [README:298](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L298)), and a copy-mode install writes only into the target agent's own directory (`installSkillForAgent`). The same README line gives `~/.codex/skills/` as Codex's global path, and the bundled agent entry reads it as `${CODEX_HOME:-$HOME/.codex}/skills` (`globalSkillsDir`). `list` scans that directory as Codex's even when another agent is asked for, but for a skill in the shared directory it names only the agents it is asked about (`listInstalledSkills`, `agentsToCheck`). The acceptance therefore lists without an agent filter, requires Claude Code as the only agent of `skill-creator`, and checks both directories for a same-name folder or a dangling link. Codex keeps its embedded skills in `skills/.system` there; `list` reads a `SKILL.md` only one level down, so it does not report them, and the check leaves that folder alone. The same code selects copy mode by itself when one agent is the only target; the command passes `--copy` so that it does not rest on that. The consensus record's source for the embedded Codex skill is `codex-rs/skills/src/lib.rs` at `a956835d020762cb2b570053af06f643a11c0ecc` (tag `rust-v0.160.0`). Read as the git object at that commit (blob `7b19d3278864ff7fff0cfc3db087914c0652d4c1`), it embeds `src/assets/samples`, whose folders include `skill-creator` ([:55](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/skills/src/lib.rs#L55)), and `install_system_skills` writes them to `CODEX_HOME/skills/.system` ([:57–97](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/skills/src/lib.rs#L57)); `find_codex_home` takes a non-empty `CODEX_HOME` from the environment and otherwise `~/.codex` ([`codex-rs/utils/home-dir/src/lib.rs:5–17`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/utils/home-dir/src/lib.rs#L5)). That is the location the check leaves alone; no Codex was run to observe it.
- **Acceptance.** As for `engineering-process-skills`: `list --json` ([README:164](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L164)), whose `agents` field holds display names, and the lock's `skillFolderHash`.

### Observations for these rows

These are scratch observations, not acceptance and not target-distribution runs. The two acceptance programs were run against stand-ins in a scratch directory: a stub `npx` that prints a canned `list --json` output, a canned lock file and a scratch `HOME`. The matching case exited 0 for both programs, and each planted variation exited 1 (VALIDATION.md lists them); those fixtures are our own, not upstream tests. For `skill-authoring` they are now a committed test, `SkillAuthoringAcceptance` in `tests/test_new_wsl_definitive_defaults.py` (VALIDATION.md, the bullet after that list). The installer's `add` and `list` were not run, nothing was installed and no client loaded a skill.

## The two local-model rows (2026-10-03)

Both rows run through the model server of the `local-model-server` row, Ollama v0.35.0, which is the version the measurement ran. The tag `v0.35.0` is a lightweight tag on commit `cc4069396f3ad2c370c53eed2e4a42ac13adab84` (`git ls-remote https://github.com/ollama/ollama refs/tags/v0.35.0`, 2026-10-03), and every Ollama line below is read at that commit. Sources opened for the two rows on 2026-10-03:

- **Pull, and the pinned digest.** `ollama pull` is the documented download ([docs/cli.mdx:85](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/cli.mdx#L85)). After downloading, the pull verifies each layer's blob against its digest and stops on a mismatch ([server/images.go:1082](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/images.go#L1082)). The list of local models ([docs/api.md:1351](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1351)) reports each model's `digest`, which is the manifest's digest ([server/model_list.go:64](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/model_list.go#L64)); the row's second command stops unless that digest is the one the measurement recorded for `qwen3-embedding:0.6b`. The manifest that `registry.ollama.ai` served for that tag on 2026-10-03 hashes to the same digest, `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`, and names one model layer, `sha256:06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439` (639,150,592 bytes). That layer entry carries a `from` field with the publisher's build path, so the manifest is not copied into the repository.
- **The Swift file.** The Hugging Face Hub's model information for `ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF` at revision `d74895bbe5db4bec1e0024e7cc87d59c02d7631a` lists `Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf` with LFS sha256 `1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786` and 11,771,546,912 bytes, the file and digest the measurement ran. `fetch_verified` (the plan's download glue, above) keeps it only when its sha256 matches.
- **Create from a GGUF file.** `ollama create MODEL -f <Modelfile>` ([cmd/cmd.go:2422](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L2422)). A Modelfile builds from a GGUF file with `FROM <file>` ([docs/modelfile.mdx:120](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/modelfile.mdx#L120)), whose location "should be specified as an absolute path or relative to the `Modelfile` location" ([:126](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/modelfile.mdx#L126)); the plan therefore places the Modelfiles beside the file. On a loopback host the client asks whether the server sees its model store and then writes the blob itself; otherwise it uploads it ([cmd/cmd.go:385](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L385), `sharedBlobStore` at [:523](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L523)). Either way the server makes the file a layer under its digest ([server/create.go:905](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/create.go#L905)), which is why the post-install check finds the file's own sha256 in the created model's manifest, and why the row needs the file's size twice on disk while the download is kept.
- **The context as the model's parameter.** `num_ctx` is a Modelfile parameter ([docs/modelfile.mdx:146](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/modelfile.mdx#L146)); the two derived Modelfiles are the measurement's own (`steps/M15-a2-setup.sh` line 31 and `steps/M21-partb-prep.sh` line 32 in the private measurement folder, listed by sha256 in `evidence/artifacts/new-wsl-local-models-20261002/files.json`), byte for byte.
- **The Swift Modelfile.** `evidence/artifacts/new-wsl-local-models-20261002/reconstruct_s2o_modelfile.py` rebuilds the measured Modelfile from the library `qwen3.8:27b` model's blobs at the digests the measurement recorded. On 2026-10-03 `--check` returned 0 (the plan's `models/swift-iq3s-s2o.Modelfile`, sha256 `f6522bf4934aaa4f60231a042a8dfb781a7f5b3b1abc5053757f37169772ea9e`, equals the reconstruction), and with the measurement's own `FROM` line it hashed to the recorded `8911245e6678ee1fac043d31d20de14ea9ed3d8834ccee5beb92e726b769e8f6`.
- **The model store the checks read.** The store is `OLLAMA_MODELS`, by default `$HOME/.ollama/models` ([envconfig/config.go:112](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/envconfig/config.go#L112)), with manifests under `manifests/` ([manifest/paths.go:29](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/manifest/paths.go#L29)), by registry host, namespace, model and tag.
- **The service checks.** Generation with `think` set to false ([docs/api.md:48](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L48)) and embeddings through `/api/embed` ([docs/api.md:1659](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1659)). The model card of Qwen3-Embedding-0.6B gives its embedding dimension as "Up to 1024" ([README.md:36 at 97b0c614](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/blob/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/README.md#L36)) and its configuration a hidden size of 1024 ([config.json:11](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/blob/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/config.json#L11)). The check sends no `dimensions` option ([docs/api.md:1677](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1677)) and expects 1,024 values. That expectation is read from the card and the configuration: the measurement's records do not state the size of the vectors it received. The `local-model-server` row's `after_sign_in` check makes one such call to `qwen3-embedding-8k`; for a model the server does not have, `GetModel` fails with a not-found error and the handler answers 404 ([server/routes.go:981-984](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L981-L984), [:3226-3227](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L3226-L3227)), and the handler ([:928-1151](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L928-L1151)) calls no pull, so it downloads nothing. `accept.sh` makes that call only once the `embedding-model` row has created the model (its manifest in the store above); before then it prints `skipped` for the stage, so step F9's after-sign-in checks, which install no model row, do not fail on it.
- **The server's version.** Both rows install what was measured on Ollama 0.35.0; the measurement's own `GET /api/version` calls returned `0.35.0` (its records `raw/M6-a1.txt`, `raw/M6-a1b.txt` and `raw/M14-a1-swift-iq3s-s2o.txt`, listed by sha256 in that `files.json`). The endpoint retrieves the Ollama version ([docs/api.md:1821-1843](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1824)), and the route answers the running server's own build version, `{"version": version.Version}` ([server/routes.go:2023](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L2023)). `install.sh` therefore stops either row, before anything is downloaded, pulled or created, unless the server that answers on 127.0.0.1:21434 reports `0.35.0`.
- **The server's defaults.** The measurement's server ran with `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_KEEP_ALIVE=-1` (`steps/M12-reprepare.sh` lines 11-12, listed by sha256 in that `files.json`); the earlier plan set neither; D-ollama first carried both, and D-ollama-2 retains parallelism1 while replacing infinite keep-alive with30m and removing boot warmup. `OLLAMA_NUM_PARALLEL` defaults to 1 ([envconfig/config.go:277](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/envconfig/config.go#L277)), and the memory a loaded model needs scales with it ([docs/faq.mdx:335](https://raw.githubusercontent.com/ollama/ollama/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/faq.mdx#L335)); the keep-alive defaults to five minutes ([envconfig/config.go:130](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/envconfig/config.go#L130)).

### Observations for these rows

These are scratch observations, not acceptance and not target-distribution runs. No `ollama` command of either row was run for the plan, no model was created and no server was started. The four acceptance programs, and the `local-model-server` row's `after_sign_in` check, ran against stand-ins (stub `ollama` and `curl` programs with canned answers, a scratch `HOME` and model store): the committed test `LocalModelAcceptance` in `tests/test_new_wsl_definitive_defaults.py`, described in VALIDATION.md. `install.sh`'s server guard ran the same way (`ModelServerGuard`, same file). The registry manifest, the Hub's model information and the Swift Modelfile's reconstruction above are reads, not runs of the rows. On 2026-10-03, after the first publication, the registry's manifest for `qwen3-embedding:0.6b` still hashed to `ac6da0df…` with the same model layer, the Hub still listed the IQ3_S file at the pinned revision with the same LFS sha256 and size, and every Ollama line cited for the two rows and for the server's defaults was read again at `cc4069396f`.

## Wave 2 (2026-10-03)

The rows the wave-2 batch of the layer consensus added, turned into interim installs or revised (README.md, section "Wave 2"). Status: UNRUN on every distribution. The pins and line references are the wave-2 dossiers' and rulings' (`evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json`); those this revision opened again are marked "read again 2026-10-03".

### Superseded statements above

- The DeerFlow Compose route: the production publication (section "Supporting upstream sources", `docker/docker-compose.yaml` line 45), `make docker-init`, the `make up` start on port 2026 (section "Service starts", marked there), the `/health/ready` probe and the `compose config --quiet` preparation check. DeerFlow now runs as the embedded `DeerFlowClient` (research ruling, changes 9 and 10).
- The mattpocock v1.2.3 install command (sections "Supporting upstream sources" and "Rows added"): the three skills rows now run `tools/adoption/install_skills.py` against `adoption/skills/manifest.json` (skills ruling, change 7), which installs only the manifest's selected skills; `domain-modeling` and `setup-matt-pocock-skills` are not among them.
- The OmniRoute start's `source` of the env file, corrected in place above.

### Interim installs (amendment 3 of the manifest's decision rule)

Each install function first calls `interim_acknowledged`, which reads `wave2.acknowledgements_owed` from `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json` with `jq` and refuses while it names a family (code-search ruling, change 1: "Until all of that exists, nothing is installed").

- **ai-memory 2.5.2 (`memory-owner`)**, tag v2.5.2 = `7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83`.
  - Archive and sidecar: [docs/install.md, lines 1634-1636](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L1634); the sha256 is the memory dossier's, equal to the sidecar on 2026-10-03.
  - Configuration and data layout: [`init`, lines 254-261](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L254); bind and embedder: [config.default.toml, line 10](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/templates/config.default.toml#L10) and lines 99-106; user unit: `packaging/systemd/ai-memory-user.service` of the archive and [docs/install.md, lines 277-283](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L277).
  - Codex's seven hooks, written once by ai-memory's installer (read again 2026-10-03): with `AI_MEMORY_SERVER_URL` set, `install-hooks` takes the bare server origin ([lines 118-121](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L118)), and `install-hooks --agent codex --apply` is the Codex form ([lines 593-595](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L593)); it merges its events into `$CODEX_HOME/hooks.json` or `~/.codex/hooks.json`, writes a backup of a file it changes, touches no `config.toml` and prints that Codex must trust the new hooks ([install_hooks.rs, lines 2071-2093](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/install_hooks.rs#L2071), 2152-2181 and 2211-2229); the seven events are [render_shared.rs, lines 907-915](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/render_shared.rs#L907). The client configuration writes no `~/.codex/hooks.json`, so this is the one writer synthesis X11 allows; trust follows X10 (the row's notes).
  - Acceptance: [`--version`, cli.rs line 11](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/cli.rs#L11) and a `hooks.json` line that is this project's integration check; [`/healthz`, serve.rs line 2712](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/serve.rs#L2712) and `status` ([docs/install.md, line 2149](https://raw.githubusercontent.com/akitaonrails/ai-memory/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L2149)).
- **semble 0.6.1 (`code-search`)**, tag v0.6.1 = `24497845460960db1839c8485319df189a889225`: [README, line 41](https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/README.md#L41) (`uv tool install`), [docs/installation.md, line 44](https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/docs/installation.md#L44) (the `semble[mcp]==X.Y.Z` pin), [README, line 285](https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/README.md#L285) (`SEMBLE_MODEL_NAME` may name a local path) and huggingface_hub's [`snapshot_download`](https://huggingface.co/docs/huggingface_hub/guides/download) for `minishlab/potion-code-16M-v2` at `e9d2a44ca6a05ac6685f3b23709ea57eb7352d5b`. Acceptance: [`--version`, cli.py line 269](https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/src/semble/cli.py#L269) and `search` ([README, line 114](https://raw.githubusercontent.com/MinishLab/semble/24497845460960db1839c8485319df189a889225/README.md#L114)); the probe search is this project's integration check.
- **context-mode 1.0.169 (`context-supply`)**, commit `6f0cc6841c687e754059f36714a11233fda1a02b`: the Claude Code marketplace and install ([README, lines 72-73](https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L72)), the Codex marketplace ([line 593](https://raw.githubusercontent.com/mksglu/context-mode/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L593)) with `--ref` ([codex-rs/cli/src/marketplace_cmd.rs, lines 70-72](https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/marketplace_cmd.rs#L70)) and `plugin add` ([plugin_cmd.rs, line 61](https://raw.githubusercontent.com/openai/codex/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/plugin_cmd.rs#L61)), and the npm tarball whose sha256 `adoption/pins-linux-x86_64.json` pins. Auto-update (read again 2026-10-03): a third-party marketplace updates its plugins only when `autoUpdate` is set on its `extraKnownMarketplaces` entry or its `known_marketplaces.json` entry ([plugins/loading, "Which marketplaces and plugins auto-update"](https://code.claude.com/docs/en/plugins/loading)); the acceptance's last lines check that neither sets it.

### Added row

- **claude-hud 0.10.0 (`statusline`)**, tag v0.10.0 = `75683c6de1ac07f6bbef00d739001679dba0740c`: [README, lines 29-30](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/README.md#L29) (marketplace and install), [commands/setup.md, lines 69-77](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/commands/setup.md#L69) (the sample-input test), [scripts/statusline.mjs, lines 29-39](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/statusline.mjs#L29) (the highest cached version runs) and [scripts/setup.mjs, lines 19-32](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs#L19) (the status-line command the client configuration renders).
  - The helper, run without prompts (wave-2 usage ruling, changes 3 and 4; read again 2026-10-03 after review): the runtime is the first of `bun` and `node` on PATH ([commands/setup.md, line 24](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/commands/setup.md#L24)), then `setup.mjs inspect --shell posix` (line 35) and `install --shell posix` (line 58). `install` copies the launcher to `<config dir>/plugins/claude-hud/statusline.mjs`, the path the configured command runs, backs up `settings.json` and writes `statusLine` ([scripts/setup.mjs, lines 69-101](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs#L69)); it keeps the earlier `statusLine` keys only when they were claude-hud's (line 94), so the next command adds `refreshInterval` 5 when absent ([statusline.md, line 69](https://code.claude.com/docs/en/statusline.md#L69)). Without the helper the configured command named a launcher that no step wrote.
  - Acceptance: the configured command, run through bash as Claude Code runs it ([commands/setup.md, line 10](https://raw.githubusercontent.com/jarrodwatts/claude-hud/75683c6de1ac07f6bbef00d739001679dba0740c/commands/setup.md#L10)), with the sample input; a positive-integer `refreshInterval`, the command naming the copied launcher and that copy equal to 0.10.0's `scripts/statusline.mjs` are this project's integration checks. The interval check takes any integer of at least 1, not only 5, because `install` keeps an earlier claude-hud value (line 94); the bound is the type and minimum of `statusLine.refreshInterval` in the settings schema that the Claude Code settings page names ([SchemaStore `claude-code-settings.json` at `de76181a`, line 2454](https://raw.githubusercontent.com/SchemaStore/schemastore/de76181a2ab215431d3e9314bc14f83cc3b01ad2/src/schemas/json/claude-code-settings.json#L2454); [statusline.md, line 69](https://code.claude.com/docs/en/statusline.md#L69): "The minimum is `1`"), read 2026-10-03 after the review of `99a2e3c6`. Both `wc -l` counts, the cached versions (exactly one) and the printed lines (at least two), are compared as numbers, because BSD and macOS `wc` print the count padded, `" %7ju"` ([apple-oss-distributions/text_cmds `wc/wc.c` at `592aaf8a`, lines 214-215](https://raw.githubusercontent.com/apple-oss-distributions/text_cmds/592aaf8a50aa5810ee8183df20f0ba48bb23aa7e/wc/wc.c#L214)), read 2026-10-03 after the review of `06f6259f`; the exact-one check had compared the count as a string.

### Revised rows

- **research-harnesses**: DeerFlow v2.1.0 [README, line 1658](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/README.md#L1658) (the embedded client, lines 1639-1686), [Makefile, line 96](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Makefile#L96) (`uv sync --locked`) and [Install.md, line 38](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/Install.md#L38); GPT Researcher at `0957c301ed06c2a5857b834358c7227c739041d4`: [pyproject.toml, line 23](https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/pyproject.toml#L23), [cli.py, line 336](https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/cli.py#L336) and [config.py, line 158](https://raw.githubusercontent.com/assafelovic/gpt-researcher/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/config/config.py#L158); runs go through `tools/research/gpt_researcher.sh` (synthesis X18), including the byte-identical installed copy and public config. G2 adds the active model from [config.example.yaml:250-278](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L250), the upstream [DuckDuckGo tool:802](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L802), unchanged [client tests](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/tests/test_client.py), and functional [chat():1193](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/client.py#L1193). Native-session and reference checks are repository integration assertions.
- **tobi-qmd**: v2.8.3 [README, line 32](https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L32), [line 671](https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L671) and [line 1021](https://raw.githubusercontent.com/tobi/qmd/v2.8.3/README.md#L1021); `src/llm.ts` at `facd35e` for GPU auto (retrieval ruling, change 16).
- **gpt-gateway**: OmniRoute v3.8.51 `docs/reference/ENVIRONMENT.md` lines 158-190, with `EMBED_WS_PROXY_PORT=21131` and plain lines for systemd's `EnvironmentFile=` (gateway ruling, change 12).
- **engineering-process-skills, skill-discovery and skill-authoring**: the `skills` installer at `vercel-labs/skills` `7407f3893ad4dceab546ac002c3ef806e4000c73` ([README, line 44](https://raw.githubusercontent.com/vercel-labs/skills/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L44)), run through the repository's `tools/adoption/install_skills.py`.

## Wave 3 (2026-10-04)

The rows the wave-3 batch of the layer consensus added or changed, on the owner's decision of 2026-10-04 (amendment 4; README.md, section "Wave 3"). Status: UNRUN on every distribution. Versions and digests follow `manifests/stack.json` and `adoption/pins-linux-x86_64.json`: RTK was refreshed to 0.51.0 from main `14048b840` after PR #693, and mcporter follows main's 0.14.2 selection; jcodemunch-mcp moved after `f77a35eb` to 1.108.327 through PR #642 W1, source `6d5ae86c130f96624e2ca2d797fa3b853c210b9d`; the other wave-3 assets retain the `f77a35eb` source, or `recipes/README.md` where the pins file has no row. The 2026-10-04 source reads remain historical; the jcodemunch README read at its selected 6d5ae86c pin is recorded below on 2026-10-05. The ecosystem-root layout follows the repository's own bootstrap: [`install_single_binary_tarball`, line 414](https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L414) (the link into `bin`), [`install_npm`, line 770](https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L770) (`npm install --global --prefix` from the verified registry tarball) and [`install_uv_tool`, line 988](https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/adoption/bootstrap-linux.sh#L988) (`UV_TOOL_DIR` and `UV_TOOL_BIN_DIR`), and archives are extracted whole as [recipes/README.md, line 59](https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/recipes/README.md#L59) does.

### Departures from the recorded upstream commands

`docs/token-efficiency-stack.json` (`upstream_commands.install`) records `gh release download` for RTK, codebase-memory-mcp and otel-tui, `gh release view --json assets` for agentsview, and plain `npm install --global --prefix` for the npm packages. The plan downloads the same release assets and registry tarballs with `fetch_verified` against the recorded sha256 instead, so it needs no GitHub sign-in and refuses a changed artifact before anything is extracted or installed. The session-analytics operational asset and its digest now come from published v0.44.0; see the dated B2 source preparation below. The earlier v0.43.0 asset metadata (read 2026-10-04) remains G5 historical evidence.

### Added rows

- **RTK 0.51.0 (`command-output`)**: the Linux asset ([README, line 113](https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L113)); checks: [`--version`, line 121](https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L121), [`rtk git log`, line 193](https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L193), [`rtk proxy`, line 313](https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L313) and [`RTK_TELEMETRY_DISABLED`, line 551](https://raw.githubusercontent.com/rtk-ai/rtk/v0.51.0/README.md#L551). The archive holds only `rtk`. Its freshly downloaded SHA-256 `5028d3b19a8f0990d30fec9fbb07e32782bc5698e618fb1861aad8a9ccba4eb5` matches the [v0.51.0 checksums file](https://github.com/rtk-ai/rtk/releases/download/v0.51.0/checksums.txt) and GitHub asset digest. The [release notes](https://github.com/rtk-ai/rtk/releases/tag/v0.51.0) require `--shell` for executable positional scripts that need shell expansion; this plan uses direct arguments. The persisted `config/rtk-config.toml` retains one `[hooks]` table and the exact five exclusions required by [main bootstrap](https://github.com/seathatflowsinourveins/native-agent-stack/blob/14048b840425c2569e0df60a6596e94e601da15b/adoption/bootstrap.md#L551); [config.rs, lines 119-123](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/core/config.rs#L119-L123) declares `exclude_commands`.
- **Headroom 0.37.0 (`output-compression`)**: [README, line 92](https://raw.githubusercontent.com/headroomlabs-ai/headroom/v0.37.0/README.md#L92) (`uv tool install --python 3.13`, with the pins file's `[mcp]` extra instead of the README's `[all]`); [`headroom --version`, line 437](https://raw.githubusercontent.com/headroomlabs-ai/headroom/v0.37.0/README.md#L437).
- **jcodemunch-mcp 1.108.327 (`code-index`)**, source `6d5ae86c130f96624e2ca2d797fa3b853c210b9d`: [README, line 91](https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/6d5ae86c130f96624e2ca2d797fa3b853c210b9d/README.md#L91) (`uv tool install`) and [line 113](https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/6d5ae86c130f96624e2ca2d797fa3b853c210b9d/README.md#L113) (`--version`); the ecosystem root, `--python 3.13` and `==1.108.327`: [recipes/README.md:554-559 at the merged commit](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f640b53094ed4de5a526cda44d6341de9598df30/recipes/README.md#L554-L559), with the version assertion at [line 560](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f640b53094ed4de5a526cda44d6341de9598df30/recipes/README.md#L560). The selected .327 pin is in `manifests/stack.json`; its recorded W1 qualification and limitations are in `evidence/receipts/jcodemunch-1108327-qualification-20261003.json`. Read on 2026-10-05 at 2026-10-05T04:17:40Z: the README at `6d5ae86c130f96624e2ca2d797fa3b853c210b9d` and prior pin `8f7b34abe16fb459e0bf1c04747d584216dfe32e` has identical lines 91 (`uv tool install`), 113 (`--version`) and 141 ([session-stats confirmation](https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/6d5ae86c130f96624e2ca2d797fa3b853c210b9d/README.md#L141)); these anchors did not move.
- **codebase-memory-mcp 0.11.0 (`code-graph`)**: [README, lines 88-95](https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/v0.11.0/README.md#L88) (the archive, then its `install.sh`, which the plan does not run); [`--version`, src/main.c line 1236](https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/v0.11.0/src/main.c#L1236). The archive holds the executable, `LICENSE`, `THIRD_PARTY_NOTICES.md` and `install.sh`.
- **Repomix 1.18.1 (`repo-packing`)**, source `80b4280a9196feace092fc672dfe2b5fac62ef08`: [README, line 109](https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L109) (`npm install -g repomix`); checks: [`--version`, line 609](https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L609), [`--include`, line 204](https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L204) and [`--style`, line 628](https://raw.githubusercontent.com/yamadashy/repomix/80b4280a9196feace092fc672dfe2b5fac62ef08/README.md#L628); the two-file pack is this project's integration check.
- **TOON 4.1.1 (`structured-data`)**: [packages/cli/README.md, line 11](https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L11) (`npm install -g @toon-format/cli`), [line 63](https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L63) (`-o`) and [line 65](https://raw.githubusercontent.com/toon-format/toon/v4.1.1/packages/cli/README.md#L65) (`--decode`); `--version` prints only the version (adoption/pins-linux-x86_64.json, line 267). The round trip is this project's integration check.
- **MarkItDown 0.1.8 (`doc-conversion`)**: [README, line 62](https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/README.md#L62) (the package; the base converter of the pins file, not `[all]`) and [line 81](https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/README.md#L81) (`-o`); [`--version`, `__main__.py` line 53](https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/packages/markitdown/src/markitdown/__main__.py#L53) and [`-x`, line 66](https://raw.githubusercontent.com/microsoft/markitdown/v0.1.8/packages/markitdown/src/markitdown/__main__.py#L66). The HTML conversion is this project's integration check.
- **Context Hub 0.1.4 (`api-docs`)**: [README, line 12](https://raw.githubusercontent.com/andrewyng/context-hub/v0.1.4/README.md#L12) (`npm install -g @aisuite/chub`); the version flag is `-V, --cli-version` ([cli/src/index.js, line 53](https://raw.githubusercontent.com/andrewyng/context-hub/v0.1.4/cli/src/index.js#L53)), although `docs/cli-reference.md` line 10 lists `--version`: the code decides, and the pins file's probe agrees with it.
- **otel-tui 0.7.5 (`trace-viewer`)**, source `3b25779a083469b732e3c628b4a412ee05cf9948`: [README, line 131](https://raw.githubusercontent.com/ymtdzzz/otel-tui/3b25779a083469b732e3c628b4a412ee05cf9948/README.md#L131) (the release assets) and [line 46](https://raw.githubusercontent.com/ymtdzzz/otel-tui/3b25779a083469b732e3c628b4a412ee05cf9948/README.md#L46) (`-v, --version`). The archive holds the executable, `LICENSE` and `README.md`.
- **token-lane-carriers**: [docs/token-session-handbook.md, line 197](https://raw.githubusercontent.com/seathatflowsinourveins/native-agent-stack/f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5/docs/token-session-handbook.md#L197) (the SubagentStart carrier); written by the client configuration, so no command and no check here.

### Owner defaults and the widened interim

- **ccusage 20.0.26 (`ccusage`)**, source `d9821088b98aa536c7a385aa1a4579d6fa02269b`: [apps/ccusage/README.md, line 62](https://raw.githubusercontent.com/ccusage/ccusage/d9821088b98aa536c7a385aa1a4579d6fa02269b/apps/ccusage/README.md#L62); `--version` prints `ccusage 20.0.26` (adoption/pins-linux-x86_64.json, line 282).
- **agentsview 0.43.0 (`session-analytics`)**: [README, line 25](https://raw.githubusercontent.com/kenn-io/agentsview/v0.43.0/README.md#L25) (GitHub Releases) and [line 695](https://raw.githubusercontent.com/kenn-io/agentsview/v0.43.0/README.md#L695) (`AGENTSVIEW_TELEMETRY_ENABLED=0`); `AGENTSVIEW_DISABLE_UPDATE_CHECK=1` is from the agentsview use commands of `docs/token-efficiency-stack.json`, and the README at that tag does not name it.
- **context-mode 1.0.169 (`context-supply`)**: the wave-2 sources above, unchanged; only the gate call is gone.
- **SocratiCode 1.15.0 (`code-search`)**, source `f6191f076a42405f0d5508139f3a8b505cfef93a`: the recipes/README.md socraticode row (`--ignore-scripts --before=2026-09-24T12:00:00Z`); its version is read from `package.json`, because every invocation starts its MCP server (adoption/pins-linux-x86_64.json, line 334).

## G1 client plan repairs (2026-10-04)

These sources were read at the selected pins for the three owned rows. The
commands are planned destination operations; source review and scratch checks
are distinct from a new host run.

- **SDK and app-server.** `openai/codex@rust-v0.160.0` (commit
  `a956835d020762cb2b570053af06f643a11c0ecc`):
  [sdk/typescript/README.md:10,15,110](https://github.com/openai/codex/blob/rust-v0.160.0/sdk/typescript/README.md#L15)
  supplies the local npm installation, unchanged quickstart and skipGitRepoCheck
  option. [codex-rs/cli/src/main.rs:923](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L923)
  dispatches `debug app-server send-message-v2` to the native test client.
  [codex-rs/app-server-test-client/src/lib.rs:1072](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1072)
  performs initialize, thread/start and turn/start;
  [:1624](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1624)
  starts the stdio child; and
  [:1994](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1994)
  prints turn status but also returns success after Failed. The Completed/reply
  predicates are local integration checks of these upstream outputs. Official
  [SDK](https://developers.openai.com/codex/sdk) and
  [app-server](https://developers.openai.com/codex/app-server) pages were fetched.
- **Engineering cleanup and listings.** `vercel-labs/skills@1.7.0`, commit
  `7407f3893ad4dceab546ac002c3ef806e4000c73`:
  [src/remove.ts:40,182,209,247,323](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/remove.ts#L182)
  resolves only requested installed names, removes client placements and updates
  the lock. No-match cleanup returns without error, supporting a clean rerun.
  [src/list.ts:113](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/list.ts#L113)
  supplies JSON listing names and agent display names. The three-name settings
  fragment uses Claude's native
  [skillOverrides](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)
  and the repository's existing merge implementation,
  `seathatflowsinourveins/native-agent-stack@PR #684's head`:
  [tools/adoption/apply_claude_settings.py:191](../../../tools/adoption/apply_claude_settings.py).
  Exact per-skill pins remain in adoption/skills/manifest.json. In particular,
  writing-for-agents is `mattpocock/skills@c55ee46073ed923f86ce59a5eb3b6d895095d1b7`:
  `skills/productivity/writing-for-agents/SKILL.md:1`; the other three selected
  engineering skills use `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`.
- **Authoring dependency and upstream acceptance.**
  `anthropics/skills@8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`:
  [skills/skill-creator/scripts/quick_validate.py:9,96](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/quick_validate.py#L9)
  imports yaml and returns failure for an invalid skill;
  [scripts/package_skill.py:17](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/package_skill.py#L17)
  imports that validator. `openai/codex@rust-v0.160.0`:
  [codex-rs/skills/src/assets/samples/skill-creator/scripts/quick_validate.py:10,120](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/skills/src/assets/samples/skill-creator/scripts/quick_validate.py#L10)
  has the same runtime dependency and native exit-status contract. Native
  [codex-rs/cli/src/main.rs:2044](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L2044)
  installs the skills extension for `debug prompt-input`;
  [codex-rs/ext/skills/src/host_service.rs:125](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/host_service.rs#L125)
  initializes the embedded cache through
  [codex-rs/skills/src/lib.rs:69](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/skills/src/lib.rs#L69).
  This native initialization precedes the validators on a clean Codex home.
  `astral-sh/uv@0.12.22`:
  [docs/pip/environments.md:100](https://github.com/astral-sh/uv/blob/0.12.22/docs/pip/environments.md#L100)
  supports installation into a selected interpreter with --python.
  [PyYAML 6.0.3](https://pypi.org/project/PyYAML/6.0.3/) is the pinned dependency.
  The creator's native paired evaluation is in the pinned
  [SKILL.md](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#running-and-evaluating-test-cases).
- **Listing capture.** Skills' [src/cli.ts:419](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L419)
  forces process exit. `nodejs/node@v24.21.0`:
  [doc/api/process.md:4228](https://github.com/nodejs/node/blob/v24.21.0/doc/api/process.md#L4228)
  documents synchronous writes to files and asynchronous POSIX pipe writes.
  The earlier install-repair patch supplied this lead; only its skill-authoring
  file-capture hunk was ported by hand.

### G2 MCP and worker plan repair (2026-10-04)

- Repository wiring sources are `this PR: adoption/new-wsl/client-config-map.json:27` and `this PR: tools/research/gpt_researcher.sh:27`, read from [PR #684's head](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files). The branch-local pre-rebase hash is deliberately omitted from these citations.
- **mcp-inspector**: `modelcontextprotocol/inspector@2.9.0` (`ae865a19178ddf6f375780a02e9c77c4cf4da184`), [README:9-26](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/README.md#L9), [publishing.md:16-18](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/docs/publishing.md#L16), [package.json:84-90](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/package.json#L84), [launcher README:15-25](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/clients/launcher/README.md#L15) and [memory-only secret store:148](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/docs/secret-storage.md#L148). `pack:verify` builds and packs a publishable tarball from the tagged source; `smoke:web:tabs` runs the source build. QMD calls, inherited client environment and fresh-client Web probes remain separate local integration checks.
- **agent-runtime-worker**: `OpenHands/software-agent-sdk@v1.50.1` (`1e1390acc8788346ba4804c34323284009bf3f5e`), [release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.1), [SDK/tool dependencies](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-tools/pyproject.toml), [frozen lock](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/uv.lock), [unchanged CI test setup:94-123](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/.github/workflows/tests.yml#L94), [unchanged hello-world:9-28](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/examples/01_standalone_sdk/01_hello_world.py#L9), [preset tools:37-171](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-tools/openhands/tools/preset/default.py#L37) and [successful-response metrics:113-129](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-sdk/openhands/sdk/llm/utils/metrics.py#L113). [uv export](https://docs.astral.sh/uv/reference/cli/#uv-export) and `uv pip install --python -c` parameterize the pinned upstream lock. The copied phase-1 dispatcher, per-job unit, sandbox rendering and report assertions are repository glue, not upstream tests. The separate frozen 1.49.6 container grader retains its pin.
- **native wiring for these worker slots**: [Codex user skill root at rust-v0.160.0:103](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/host_roots.rs#L103), [Claude skill directories](https://code.claude.com/docs/en/skills#where-skills-live), [Codex native completed command schema:159](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L159) and [Claude streaming JSON](https://code.claude.com/docs/en/cli-reference). Fresh-session checks use the installed native CLIs and preserve their original JSONL. The srt composition follows [sandbox-runtime@v0.0.78 README](https://github.com/anthropic-experimental/sandbox-runtime/blob/v0.0.78/README.md); unit registration/dispatch follows [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html). No WSL, provider or native-client execution is claimed by this source-only repair.


## G3 code and document plan repairs (2026-10-04)

Sources below were re-read at the exact selected revisions. These are sources for recipe commands and integration assertions; no distribution acceptance or native model run was executed by this builder.

### Serena

- The plan now matches the pre-existing development pin in `manifests/stack.json`, `adoption/new-wsl-profile.json` and `catalogs/foundation/new-wsl-architecture-20261001.json`. The commit identity is [oraios/serena@c6fbd1c5932df2494ffa0020af5a9fbe80b82143](https://api.github.com/repos/oraios/serena/commits/c6fbd1c5932df2494ffa0020af5a9fbe80b82143). Its PyPI predecessor remains [release v1.7.0](https://api.github.com/repos/oraios/serena/releases/tags/v1.7.0); that release does not supply the selected development code. The Git tool-install route is [uv's tools guide](https://docs.astral.sh/uv/guides/tools/), with the selected commit passed as the Git requirement and `--force` for reconciliation.
- Upstream install verification is [README.md:229-237](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/README.md#L229). [serena_config.py:66](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/config/serena_config.py#L66) supports `SERENA_HOME`, so the initialization check isolates Serena's state without changing HOME.
- Python is a published identifier in [project.template.yml:40](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/resources/project.template.yml#L40). The project-local override is loaded in [serena_config.py:723](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/config/serena_config.py#L723). The thin configuration merge adopts upstream's comment-preserving [load_yaml:75 and atomic save_yaml:214](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/util/yaml.py#L75); the only key it changes is `language_servers`, retaining existing languages while adding Python.
- Indexing is [cli.py:803](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L803). The unchanged upstream [project health-check:957](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L957) exercises symbols and reference queries; [cli.py:1035-1087](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L1035) makes empty symbol results or a reference-query exception fail the command.
- Native MCP command and contexts are [Claude Code clients.md:134](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/docs/02-usage/030_clients.md#L134) and [Codex clients.md:302-315](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/docs/02-usage/030_clients.md#L302). The existing F8 writer already implements them: [this PR: client-config-map.json:371](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files), and [:555](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files). The fresh-session checks verify returned tool results after F8; they are project integration checks.

### Structural search

- Installation remains [mise@v2026.10.0:registry/ast-grep.toml:1](https://github.com/jdx/mise/blob/v2026.10.0/registry/ast-grep.toml#L1) and [ast-grep@0.45.3:README.md:61](https://github.com/ast-grep/ast-grep/blob/0.45.3/README.md#L61). The [0.45.3 release notes](https://api.github.com/repos/ast-grep/ast-grep/releases/tags/0.45.3) were read.
- The acceptance restores the unchanged published preview [README.md:84](https://github.com/ast-grep/ast-grep/blob/0.45.3/README.md#L84), `ast-grep -p '$A && $A()' -l ts -r '$A?.()'`, with a temporary input file as the parameter. It asserts the replacement in returned output. A separate no-match file must exit exactly 1, as [crates/cli/src/run.rs:349](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/run.rs#L349) defines. The conditional catches the expected failure under `bash -e`; command substitution exposes the preview command's own status. Without `-U` or `-i`, this is a preview and writes no source. The source-build coverage proposal was rejected by the Opus adjudication; no cargo acceptance is adopted.

### MinerU

- Package installation remains the pinned [README.md:307](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L307); [README.md:365](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L365) calls `mineru --help` installation verification. The [4.0.10 release notes](https://api.github.com/repos/opendatalab/MinerU/releases/tags/mineru-4.0.10-released) and [pyproject.toml:10,39-87](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/pyproject.toml#L10) were read. [README.md:448,458](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L448) documents the base ONNX plus llama.cpp Standard option on CPU, with at least 8 GB RAM; the row therefore requires no GPU. [README.md:397](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L397) supplies telemetry disable.
- Agent wiring is upstream's [README.md:66](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L66) and unchanged [skills/mineru/SKILL.md](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/skills/mineru/SKILL.md). At that peeled commit the skill directory's Git tree is `38d108595980854f65640d46ab27ecea002b549d` ([Git Trees API](https://api.github.com/repos/opendatalab/MinerU/git/trees/d222e58396e1cfc6668f6ad5922e649b5f5d3e50)); SKILL.md SHA256 is `dec330a3549d232fed44db2b0c9bc0b64505a11d2526008ddf044b3f94681d96`, calculated from the exact downloaded source. `config/mineru-skills-manifest.json` supplies those pins to the existing [tools/adoption/install_skills.py:622 --manifest](../../../tools/adoption/install_skills.py) route. Its [process_skill:460](../../../tools/adoption/install_skills.py) runs the pinned CLI's native `add` for both agents. No unpinned npx add is introduced, and the shared adoption manifest is untouched.
- The CLI remains [vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73:README.md:44](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md#L44), version 1.7.0 from the existing manifest. Its native structured listing is [src/list.ts:113](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/list.ts#L113). It is captured to a regular file before jq; JSON pipes are not needed. The repository installer independently checks SKILL.md and the lock tree, and the post-install check verifies both native agent listings and Claude's link to the canonical skill.
- Standard setup uses the unchanged command sequence in [README.md:559-575](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L559): download, verify, managed tier, then managed mode. [README.md:467](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L467) supplies `mineru server start`. [docs/next/cli/mineru-server.md:38](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/docs/next/cli/mineru-server.md#L38) describes UDS with loopback TCP fallback; [:103-120](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/docs/next/cli/mineru-server.md#L103) defines the health and tier fields used by the readiness assertion. The bounded poll implements the README:576 requirement to wait for a healthy target tier.
- The public source fixture is [demo/pdfs/demo1.pdf at c221cc41](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/demo/pdfs/demo1.pdf), SHA256 `f3b3be345bf2df8979f2491ca9466e078e4fd1d6a216611faa8566e4c44d474b`, calculated from downloaded bytes; its first-page title contains `afforestation`. Parse/read are [README.md:223-224](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L223). The integration check uses the returned content scope/range locator at page granularity, defined by [mineru/doclib/types.py:266-291](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/doclib/types.py#L266). Parse's envelope is [mineru/cli/commands/parse.py:388](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/cli/commands/parse.py#L388), and read's response is [docs/next/cli/mineru-read.md:143](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/docs/next/cli/mineru-read.md#L143). These content assertions are project integration checks, with no inference result claimed here. [README.md:372-375](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L372) requires explicit remote permission; every new command stays local.

### Native fresh-session contracts

Both rows use [Claude Code's documented headless CLI](https://code.claude.com/docs/en/headless), `claude -p --output-format stream-json --verbose`, and [Codex's documented noninteractive CLI](https://developers.openai.com/codex/noninteractive), `codex exec --json -C`. There is no resume flag or provider/model override. The upstream Codex event definitions are [openai/codex@rust-v0.160.0:codex-rs/exec/src/exec_events.rs:9-37](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L9), [command execution:161](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L161) and [MCP results/calls:263-296](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L263). jq checks actual successful native tool responses and completed turns, rather than accepting the model's final declaration. Those assertions are explicitly project integration checks. Native sign-in and application of the existing F8 client writer precede the stage.

## G4 observability repair (2026-10-04)

The selected release/source pins and original sources were re-read for this
bounded repair. The staged commands were not run on a distribution. The full
comparison and completeness critic are in
`docs/decisions/2026-10-04-2604-e2e-fix-wave-g4-observability.md`.

- Collector Contrib **v0.162.0**, tag commit
  `ae8c507510f48f433ab47dd1c6b01a59d6c388b5`: the release tar route/checksum already
  in this plan is retained. [validate/DryRun](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.162.0/otelcol/command_validate.go#L15)
  and [file_storage directory validation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/extension/storage/filestorage/config.go#L69)
  establish the missing environment and directory conditions. The upstream
  [create_directory option](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/extension/storage/filestorage/README.md#L39)
  is used by the clean template; the earlier repair's exact container-path
  migration preserves retained pipelines. Original integration reference:
  `this PR: observability/collector/collector.yaml:1`.
  Native metrics scrape **21889**, collector telemetry **21888**, OTLP HTTP
  **21318** and gRPC **21317**, health **21333**; Loki **21300** is an outgoing
  reference. The validator and foreground service both receive
  `NS2604_OBSERVABILITY_DATA` with the same resolved data root. Native aliases and
  exporter formats follow the tagged [file receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/filelogreceiver/README.md#L164)
  and [Prometheus exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/exporter/prometheusexporter/README.md#L20).
- Grafana OSS **v13.2.3**, tag commit
  `6193dc03311b631b9727b560d24369e683dc396e`: the same OSS archive and SHA256
  were found on the [official download page](https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux).
  [native provisioning](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/administration/provisioning/index.md#L324)
  supplies file providers and datasource YAML; [minimum step](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/datasources/prometheus/query-editor/_index.md#L47)
  separates `1m` evaluation from the retained `[1h]` lookback. Dashboard form:
  `this PR: observability/backends/templates/ecosystem-dashboard.json.example:1`.
  The original E2E's 29 token-layer query records supply the expressions and
  the six failing hourly targets; no metric values enter the new source.
  Native functional checks use [POST /api/ds/query](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/developer-resources/api-reference/http-api/api-legacy/data_source.md#L657),
  [dashboard GET](https://github.com/grafana/grafana/blob/v13.2.3/pkg/api/dashboard.go#L52),
  and the frontend Alertmanager plugin's own
  [testDatasource /api/v2/status request](https://github.com/grafana/grafana/blob/v13.2.3/public/app/plugins/datasource/alertmanager/DataSource.ts#L48).
  Its generic backend health endpoint is not the acceptance oracle. Fresh
  SDK production reuses
  `this PR: examples/omniroute-codex-sdk/worker.py:395,596`,
  which invokes the native SDK with a Sol/max route; its real result metadata is
  sanitized into the file receiver's spool, without cumulative numeric usage.
  Static archive/JSON checks remain repository integration checks, separate from
  the running native APIs and observed panel data.
- Alertmanager **v0.34.1**: retain the existing published tar SHA256 and native
  [amtool check-config](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L620).
  Native receiver wiring uses [webhook url_file](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L1939)
  or [Telegram bot_token_file/chat_id_file](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L1862).
  The native [expiring alert command](https://github.com/prometheus/alertmanager/blob/v0.34.1/cli/alert_add.go#L46)
  is parameterized with a fresh public acceptance ID and RFC3339 expiry.
  Alertmanager's [native readiness API](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/management_api.md#L22)
  is retained. Private files are metadata-checked only, per
  `this PR: docs/secret-storage.md:31,95-97`.
- Prometheus **v3.15.0** native [alert rules](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/alerting_rules.md#L15),
  [promtool rule unit tests](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/unit_testing_rules.md#L6),
  [file-SD/Alertmanager configuration](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/configuration.md),
  and [rules/alerts/Alertmanager discovery APIs](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/querying/api.md)
  are the native oracles. Local adaptation references:
  `this PR: observability/backends/templates/ecosystem-prometheus-rules.yml.example:1`
  and `observability/backends/README.md:214-249`. Synthetic unit inputs do not
  establish delivered alerts; future selected delivery acceptance also requires
  real firing/resolution, increased native notification counters and the user's
  independently confirmed receipt. Loki ruler qualification is deferred.

Configuration transport is adapted from
`this PR: observability/backends/configure.py:76-96`; the helper
is a renderer/migration, not an alternative agent or E2E runner. It creates no
service and reads no private destination values. The original alerting
adjudication corrects the unit assignment to observe-eval-2. The user chooses
webhook, Telegram or on-host delivery; the sink remains until safe files exist.

Receiver support is restored from main `f946c6d4c` / `77d7516d8`:
`config/observability_config.py:65-78` selects the native webhook or Telegram
pointer files, and `accept.sh` selects the matching native notification counters.
The upstream Alertmanager v0.34.1 file fields are documented at
`docs/configuration.md:1875-1882,1947-1950`. The round-2 handling of exit 78 as
`needs_user` remains.

The coordinator's 2026-10-05 round-3 brief corrects the choice record: ntfy.sh
was the coordinator's delegated pick on 2026-10-04; the user personally configured
and accepted Telegram on NativeStack2604 at about 06:58Z on 2026-10-05. The user
supplied firing and resolved messages for acceptance
`9e6f4a70b5874573aff1d22b40e87a32`; main `4c897418f`'s unmodified
`accept.sh --only alerting --stage after_sign_in` returned 0 with
`receiver_evidence=user_attestation`. The plan supports webhook/ntfy, Telegram
and on-host; nothing was overturned. These are coordinator-supplied host facts,
not a new live run by this PR. Only pointer names are retained.

## Repair round 4: CI portability and research configuration (2026-10-05)

The measured research baseline is retained in
`this PR: evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json`,
`layers.gpt-runtimes.ruling`: its default names the high/max request aliases,
and change 2 binds the profile to session 80's configuration, including the
12000-token budget, scraper bounds, 4096-character chunks, 1500-word report and
600-second timeout. The credential-bearing session file is not opened or copied.

Option (b), a dated source compatibility amendment, is recorded in
`this PR: evidence/artifacts/final-architecture-round2-20261004/integration-resolutions.json`,
`repair_round_4.research_configuration_amendment`. It binds the exact committed
configuration hash and the retained baseline record hash, lists the preserved
measured values and names each compatibility change. It is not a new measurement.
Restoring the historical max aliases alone would not establish compatibility
with the clean 3.8.51 pin: its
[max-alias set and suffix parser](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts#L11)
do not include `gpt-6.1-sol` in that set. The
[unlisted-model cap](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex.ts#L315)
is xhigh for the unsuffixed smart/strategic routes in that dated record.
FAST uses cx/gpt-6.1-sol-high and requests high through the pinned suffix parser;
it does not request xhigh. Keep the historical #637 configuration record; neither
an alias label nor that source reading supplies delivered-effort evidence.

The per-run correlation header remains `x-omniroute-session-id`, as the pinned
[chat handler reads](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore.ts#L1084)
before assigning `call_logs.session_tag`. Chrome Signed-By and Claude MCP
registration checks use `grep -E`, with `[[:space:]]` and a literal `[.]` where
needed; their positive and negative controls run with ripgrep absent from PATH.
Other ripgrep checks are unchanged. All checks here are repository integration
evidence, separate from a fresh research or provider run.

## G5 analytics and evaluation sources (2026-10-04)

The bounded builder re-read the original pinned source. The private `review-observe-eval-2.json` supplies the session-analytics repair; `adjudication.json` overrides the two evaluation reviews. The supplied `fixes.json` was absent at the input location when checked. The earlier install-repair patch contains no hunks for these three slots. The existing primary tool pins remain unchanged.

- **agentsview 0.43.0**, tag commit `9be7745ad1906ee24e04eb05bb86c872ef0939a1`: [SHA256SUMS, line 32](https://github.com/kenn-io/agentsview/releases/download/v0.43.0/SHA256SUMS) matches the existing Linux archive digest `4520c6698772d2db7220212abf58d7d58c0966d7435f0a5ab134371f874df6d9`. [README.md:40-89](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/README.md#L40) documents daemon lifecycle, session listing, usage reporting and sync. The installed client was 0.44.0, so its help was a lead; the 0.43.0 release notes and tag source were re-read before choosing the commands.
- **agentsview configuration and native roots**: [internal/config/config.go:688-713](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/config/config.go#L688) defines the local configuration, [600-641](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/config/config.go#L600) defines usage-only retention, and [1920-1944,1997-2002](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/config/config.go#L1920) implements directory, update and retention environment overrides. The launcher is local placement glue over those supported variables, with telemetry off as [README.md:695](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/README.md#L695) documents.
- **agentsview artifact assertions**: [cmd/agentsview/session_list.go:129-168](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/session_list.go#L129) supports JSON, per-agent filtering and inclusion of headless/automated sessions. [session_get.go:21-53](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/session_get.go#L21) provides exact lookup and a missing-session error. [internal/db/sessions.go:295](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/db/sessions.go#L295) supplies ID, agent, start time and message counts. [cmd/agentsview/cli.go:538-557](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/cli.go#L538) supports offline per-agent daily reports; [internal/db/usage.go:1886-1912](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/db/usage.go#L1886) defines their token totals. Timestamp, nonempty-data and absent-ID assertions are local integration checks.
- **Harbor 0.23.0**, tag commit `1e5c5c6db929a10a140d05e606882c671ae20729`: [README.md:22](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md#L22) supplies the uv tool route. [tests/integration/test_hello_user_e2e.py:25-54](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/tests/integration/test_hello_user_e2e.py#L25) defines oracle=1.0, nop=0.0, no exception and completed verification. The plan runs the unchanged task through the native CLI, rather than claiming the unchanged pytest test ran. [src/harbor/cli/jobs.py:436-446,539,593,799-838,1054](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/cli/jobs.py#L436) supplies job names/directories, concurrency, agents, Docker, force-build and local task flags. [models/trial/paths.py:278,291](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/models/trial/paths.py#L278) names the native reward and result artifacts. Reading those artifacts and applying the positive gate to nop are local integration assertions.
- **Inspect AI 0.3.273**, tag commit `9e44f1b77ed7c912bf58baf30db8560937e7ce53`: [docs/index.qmd:38](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/docs/index.qmd#L38) supplies package installation. [examples/theory_of_mind.py:7-18](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/examples/theory_of_mind.py#L7) is the unchanged scored example. [model/_providers/providers.py:379-391](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/src/inspect_ai/model/_providers/providers.py#L379) requires the optional `openai` package at least 3.1.0. [openai_compatible.py:98-136](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/src/inspect_ai/model/_providers/openai_compatible.py#L98) implements the service prefix and derives `OMNIROUTE_API_KEY` from `omniroute`. [cli/eval.py:288,965](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/src/inspect_ai/_cli/eval.py#L288) supports the provider base URL and native log format. [cli/log.py:138-163](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/src/inspect_ai/_cli/log.py#L138) provides the supported header reader; [log/_log.py:851-894,1228](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/src/inspect_ai/log/_log.py#L851) defines sample totals, scores and status. Success/error predicates and the absent-model control are local integration checks over native output.
- **Provider dependency**: [PyPI openai 3.24.0 metadata](https://pypi.org/pypi/openai/3.24.0/json) identified a non-yanked release uploaded 2026-10-02 and Python >=3.10. The [v3.24.0 release](https://github.com/openai/openai-python/releases/tag/v3.24.0) and [openai/openai-python@637f1b8b:README.md:20](https://github.com/openai/openai-python/blob/637f1b8b2e9fdc3220fd4edbb8602cc89dc489c8/README.md#L20) confirm the SDK package. The [uv tool guide](https://docs.astral.sh/uv/guides/tools/) supports installing an additional dependency with `--with`; this adds it to Inspect's tool environment. [Official OpenAI SDK documentation](https://developers.openai.com/api/docs/libraries/) was fetched; official-domain search was unavailable, so the exact upstream release and PyPI metadata supplied version evidence.

Corrections verified in original source: Harbor oracle/nop needs Docker and network, not a provider credential; model-backed native-agent trials are a later tier under the adjudication. Inspect's prior direct-ZIP traceback concerned unsupported compression, not missing `header.json`, and its bare wheel does not guarantee a provider SDK. Fresh-session invocation is further acceptance for the two unwired CLIs, rather than their READY gate. Session analytics requires native roots, actual imported sessions and usage; a blank archive or passing version line cannot prove it.

Completeness critic: the plan now covers release integrity, fixture availability, native source roots, local daemon lifecycle, private retained native results, scored provider output, positive and negative controls, and fresh analytics sessions. Full upstream suites, container access to the gateway, native-agent Harbor trials and independent observation on the target distribution remain for the host/coordinator lane. The builder's syntax, consistency and repository tests are structural evidence only.


## Verified E2E fix: Promptfoo, ccusage and Syft (2026-10-04)

All commands remain planned for WSL. The fix-wave decision separates the bounded
Linux observations from destination acceptance and from unchanged source suites.

- **Promptfoo install:** `promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8:site/docs/installation.md:19`
  ([source](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/installation.md#L19));
  [npm install parameters](https://docs.npmjs.com/cli/v11/commands/npm-install)
  supply the owned prefix, local verified tarball and `--include=optional`.
  The tarball SHA256 `53471b239132b5e7a270fda458f78a1f1b920abb617ef4dc2b096608d480ee2f`
  is retained from the source profile. The optional MCP SDK and STDIO command
  are at `site/docs/integrations/mcp-server.md:13-35` at the same pin.
- **Promptfoo evaluator acceptance:** `test/smoke/eval.test.ts:65-88`
  ([source](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/test/smoke/eval.test.ts#L65))
  uses `eval -c ... --no-cache`. `config/promptfoo-0.123.1-basic.yaml` and
  `config/promptfoo-0.123.1-failing.yaml` are byte-for-byte copies of upstream
  `test/smoke/fixtures/configs/basic.yaml:1` and `failing-assertion.yaml:1`.
  Invoking the installed CLI with those fixtures is an integration check,
  separate from `npm run test:smoke` in a built upstream checkout.
- **Promptfoo real gateway acceptance:**
  `examples/openai-compatible-gateway/promptfooconfig.yaml:1-24` and
  [README, line 22](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/examples/openai-compatible-gateway/README.md#L22).
  The config is parameterized for two owner-selected model IDs, the existing
  gateway on 21128 and `apiKeyEnvar: GATEWAY_API_KEY`. CLI flags are at
  `site/docs/usage/command-line.md:105-139`; MCP `cache`, `write`, `share` and
  returned statistics are at `src/commands/mcp/tools/runEvaluation.ts:103-115,433-478`.
- **Native wiring:** installed Claude Code 2.1.289 `mcp add --help` and
  [Claude MCP documentation](https://code.claude.com/docs/en/mcp);
  installed Codex 0.159.3 `mcp add --help` and
  [Codex MCP documentation](https://developers.openai.com/codex/mcp).
  `openai/codex@rust-v0.159.3:codex-rs/rmcp-client/src/utils.rs:16-26`
  verifies name-only credential forwarding via `env_vars`; `mcp add` alone
  does not forward it. `config/promptfoo-codex-env.py` reuses
  `this PR: tools/adoption/new_wsl_client_config.py:1623,1735`
  and `tools/adoption/apply_codex_lane.py:271`, preserving settings with a
  compare-and-swap write. Fresh CLI flags were checked in the installed clients;
  Codex event fields are at `codex-rs/exec/src/exec_events.rs:161,263-293`.
- **ccusage:** `ccusage/ccusage@d9821088b98aa536c7a385aa1a4579d6fa02269b:docs/guide/installation.md:58,133-148`
  ([source](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/docs/guide/installation.md#L133))
  and `apps/ccusage/README.md:65-67` document install verification and the two
  native daily reports. The three copied JSONL files are unchanged from
  `apps/ccusage/test/fixtures/claude/projects/project-alpha/session-alpha/chat.jsonl:1`,
  `project-beta/session-beta/chat.jsonl:1` and
  `apps/ccusage/test/fixtures/codex/sessions/project-alpha/session-alpha.jsonl:1`.
  The scoped-home native CLI test pattern is at
  `rust/crates/ccusage/tests/claude_cli.rs:63-86` and `codex_cli.rs:130-146`.
  The reports hide cost and remain offline; expected totals are numeric fixture
  observations, not native provider runs. PR #684's verified install is retained.
- **Syft:** `anchore/syft@cc326e45a6213360266dda4b30cc68095946d676:README.md:48-61`
  ([source](https://github.com/anchore/syft/blob/cc326e45a6213360266dda4b30cc68095946d676/README.md#L48))
  documents the actual public-container scan and JSON output.
  `jdx/mise@v2026.10.0:registry/syft.toml:1` supports the retained user install.
  [Release checksums](https://github.com/anchore/syft/releases/download/v1.54.0/syft_1.54.0_checksums.txt)
  supply the Linux archive SHA256
  `54a87372498168b2d033e876fd41fa4e8035b872699e525a57046e1f2f09c860`.
  Historical 1.52.0 evidence is kept separate from the new clean-install pin.


## Fix wave g8: base, srt, destination gateway and Betterleaks (2026-10-04)

These sources were re-read for the bounded plan repair on `PR #684's head`.
Upstream acceptance commands below are planned target checks, not new builder executions. Native metadata/help reads,
source/tarball inspection, syntax checks and project unittests are distinct from WSL/provider acceptance.

- **Canonical base image:**
  [ubuntu/wsl-setup@73418e32:test/basic-assertions.sh:2-7,22-30](https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/test/basic-assertions.sh#L2)
  accepts the expected default user as argument; the script SHA-256 is
  `c6e966a2e6041f2e91f4cccc146ee86042af1c052768944927394e23de947fd0`.
  [test/systemd-assertions.sh:6-33](https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/test/systemd-assertions.sh#L6)
  requires `running` before its multipathd, conditional timesyncd and cloud-init assertions; its SHA-256 is
  `83f2d89c00e70e994218ed3bed4ae19aee3539934dbe109aff76f9c57cfd2e83`.
  Both original raw files were fetched and hashed. The separate F1 exception and identifier journal query follow
  [this PR: adoption/platforms/linux-wsl2-new-distro.md:836-873](../../../adoption/platforms/linux-wsl2-new-distro.md),
  with the WSL change at [microsoft/WSL PR40621](https://github.com/microsoft/WSL/pull/40621).
  The image install stays that recipe's W2-W6, separate from Linux acceptance.
- **srt install and native use:**
  [anthropics/sandbox-runtime@v0.0.78:README.md:14](https://github.com/anthropics/sandbox-runtime/blob/v0.0.78/README.md#L14),
  [README.md:166-179](https://github.com/anthropics/sandbox-runtime/blob/v0.0.78/README.md#L166) and
  [src/cli.ts:276-324](https://github.com/anthropics/sandbox-runtime/blob/v0.0.78/src/cli.ts#L276)
  supply installation, the unchanged smoke, the settings interface and refusal when an explicit policy cannot load.
  GitHub's tag API resolves v0.0.78 to `6f0ce155ccb136bda33a8a72201fe7f54fe47d9b`; its
  [release notes](https://github.com/anthropics/sandbox-runtime/releases/tag/v0.0.78) were checked.
  The [npm metadata](https://registry.npmjs.org/%40anthropic-ai%2Fsandbox-runtime/0.0.78) and downloaded archive agree on
  SHA-512 integrity; its independently computed SHA-256 is
  `a9cf9e35068a4c71d2d94de8b0abe8de51c7d44daef537cc92906848ccc67240`.
  Fresh-session controls are local integration checks on the executor's existing synthetic fixtures, not unchanged
  upstream tests. Native Claude Code 2.1.289 help and the original host-1 tool events establish the headless lane;
  [headless docs](https://code.claude.com/docs/en/headless) are a locator (the worker's direct fetch returned 403).
  The [2.1.289 changelog](https://github.com/anthropics/claude-code/releases/tag/v2.1.289) was fetched via `gh api`.
- **Canary composition and unchanged gates:**
  [OmniRoute@23a11484:package.json:119,134-135,181,253](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/package.json#L119)
  and [scripts/build/validate-pack-artifact.ts:215-225](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/scripts/build/validate-pack-artifact.ts#L215)
  supply the native test/build/typecheck/pack commands and explicit canary override.
  [PR13788@6c799005:tests/unit/issue-8674-alpha-search.test.ts](https://github.com/diegosouzapw/OmniRoute/blob/6c7990058c4ce9677de79452c8cefb10b4bf1b3d/tests/unit/issue-8674-alpha-search.test.ts) and
  [PR15167@0585aba5:tests/unit/codex-gpt6-sol-luna.test.ts:65](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/tests/unit/codex-gpt6-sol-luna.test.ts#L65)
  were fetched; the five-file runner is exactly the recorded B5a upstream runner, with no authored tests substituted.
  The recorded canary (base plus three exact carries) and rollback are in
  [this PR: wave2-records.json:279-300](../new-wsl-layer-consensus-20261002/wave2-records.json).
  `config/omniroute-canary-evidence.json` retains sanitized original gate lines, original input hashes and independent
  historical read-back. It records test counts as null because the original output has no counts.
- **Gateway state, unit and clients:**
  [OmniRoute@23a11484:bin/cli/data-dir.mjs:51](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/bin/cli/data-dir.mjs#L51),
  [bin/cli/commands/doctor.mjs:630-652](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/bin/cli/commands/doctor.mjs#L630),
  [src/app/healthz/route.ts:17](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/src/app/healthz/route.ts#L17) and
  [docs/reference/ENVIRONMENT.md:89,158-190,225,1188](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/docs/reference/ENVIRONMENT.md#L158)
  were fetched. The plan's unit is an explicit destination adaptation of
  [this PR: adoption/templates/systemd/omniroute.service:65-97](../../../adoption/templates/systemd/omniroute.service),
  with the supported foreground CLI, global mise shims, DATA_DIR and separate loopback ports. Native user-manager wiring
  follows [systemctl daemon-reload](https://www.freedesktop.org/software/systemd/man/259/systemctl.html#daemon-reload).
  [Codex@rust-v0.160.0:codex-rs/exec/src/cli.rs:36,65](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/cli.rs#L36),
  the installed Codex 0.159.3 `exec --help`, both installed/target release notes, and the fetched
  [official noninteractive docs](https://developers.openai.com/codex/noninteractive) establish JSONL and ephemeral
  native turns. The recorded clients-2 turn already passed with the destination profile and keyless placeholder;
  its original event-count summary is line 18, not the adjudication's line 17. The fixed-prompt check is new and unrun.
  [PR13788@6c799005:alpha/search/route.ts:136-172](https://github.com/diegosouzapw/OmniRoute/blob/6c7990058c4ce9677de79452c8cefb10b4bf1b3d/src/app/api/v1/alpha/search/route.ts#L136)
  confirms the search_query-only adapter; open/click/find/screenshot remain unsupported in this carried revision.
- **Betterleaks installation acceptance and retained gate:**
  [betterleaks/betterleaks@v1.9.0:Makefile:15-16](https://github.com/betterleaks/betterleaks/blob/v1.9.0/Makefile#L15),
  [go.mod:3-5](https://github.com/betterleaks/betterleaks/blob/v1.9.0/go.mod#L3),
  [README.md:57](https://github.com/betterleaks/betterleaks/blob/v1.9.0/README.md#L57) and
  [release notes](https://github.com/betterleaks/betterleaks/releases/tag/v1.9.0) were read.
  GitHub's v1.9.0 tag API resolves to `81aff7a638638aae3a659845d089043e1d8fe9ac`.
  [jdx/mise@v2026.10.0:docs/cli/exec.md:8-15](https://github.com/jdx/mise/blob/v2026.10.0/docs/cli/exec.md#L8)
  supports supplying the toolchain for one command without moving the global Go configuration.
  Betterleaks was not found on this builder's PATH; no binary acceptance or credential scan is claimed.
  An Opus check the coordinator relayed (not a user statement) keeps gitleaks 8.30.1 required until
  [this PR: 2026-10-02-github-automation-practice.md:40-57](../../../docs/decisions/2026-10-02-github-automation-practice.md)
  P1 passes; the review's immediate hook/CI migration is deliberately not implemented. P1 is due before 2026-10-20.

The provided `fixes.json` was absent from the read-only input directory. The original adjudication, host-1 and
GPT-runtime executor/review records plus an Opus check the coordinator relayed for Betterleaks (not a user statement) supplied this wave's instructions.
The earlier job-030 patch/report was inspected; its changed slots do not include these four, so no unrelated hunk was ported.
Scoped ai-memory retrieval with pin priority and limit two was unavailable because the MCP call required approval under
this job's never-approval policy. Context Mode tools were not exposed in this session's enabled tool list; bounded native reads and RTK handled output.

## 2026-10-05 Dagu/mise pin move

The current Dagu installation row selects [v2.18.2](https://github.com/dagucloud/dagu/releases/tag/v2.18.2), commit `5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4`; its native installer reads the release archive and [checksums.txt](https://github.com/dagucloud/dagu/releases/download/v2.18.2/checksums.txt). The Linux amd64 archive's published sha256 is `5a84c093b9ba9d02b7a60e106bb91d46f9383fd01c62bd51560e41193f05792b`. Version-command and installer health locators were re-read at that pin (version.go:13, installer.sh:1989); coordinator binding defaults are loader.go:2029-2031, and effective enabled=true is loader.go:1314-1321.

The current mise installation row selects [v2026.10.1](https://github.com/jdx/mise/releases/tag/v2026.10.1), annotated tag `b752bdc18b1b5961e4f9ba01a63bc3c11a0a1f79` / peeled commit `050ce5a20287a0aafd872b1191699a5fdafff5ac`. Its Linux x64 tar.gz sha256 from [SHASUMS256.txt](https://github.com/jdx/mise/releases/download/v2026.10.1/SHASUMS256.txt) is `9b92aa39b8fde54b28c8f974a68f2501925a1523d6c05a52719145df3acdd75a`; the current [installing guide](https://github.com/jdx/mise/blob/v2026.10.1/docs/installing-mise.md) documents the version pin and checksums, and doctor/mod.rs:532 still requires activation or shims. Other registry citations and prior source-read/repair observations above retain their reviewed revisions.

Only the verified release assets were installed in a disposable root for version/validation/start-all/doctor qualification. No target-WSL install-plan run is added: the original validation/host receipts keep their bytes. The waiver, reader classification and qualification scope are in [the pin decision](../../../docs/decisions/2026-10-05-dagu-mise-pin-move.md); actual sanitized results are in [the new receipt](../../receipts/dagu-mise-pin-qualification-20261005.json).

### Existing-home Dagu upgrade and conditional rollback (dagu-pin-r3)

The current new-WSL row carries its own Dagu 2.18.2 pin. The workstation/trading stack remains held at 2.16.6; its hosting cutover belongs to the trading lane. [v2.17.0 release notes](https://github.com/dagucloud/dagu/releases/tag/v2.17.0) describe #2784 (default suspend flags under data_dir) and #2776 (partitioned/indexed artifacts); [v2.17.2](https://github.com/dagucloud/dagu/releases/tag/v2.17.2) describes #2858 (DAG definition index under data_dir). The [standing hold](../../../docs/decisions/2026-09-25-workstation-sota-refresh.md#held-by-the-trading-lane) records that 2.17.2 opening a DAG repository removes legacy dags/.dag.index.

For a future upgrade of any existing owned installation, stop its owned unit and retain a complete pre-upgrade DAGU_HOME copy, together with the old checksum-verified binary, unit and environment. Keep newer commands away from the saved copy. Conditional rollback stops the new unit, preserves post-upgrade state separately, restores the saved home and prior binary/unit/environment together, then verifies the native version and owned workflow. A fresh empty installation has no prior home to restore. NativeStack2604 is already on 2.18.2 with no pre-upgrade copy, so its rollback is re-provisioning; its unit-file backups restore the unit, not the data. See [Command center correction and NativeStack2604 state](../../../docs/decisions/2026-10-05-dagu-mise-pin-move.md#command-center-correction-and-nativestack2604-state-2026-10-05-r2b). No host rollback or legacy-index rebuild was executed in this builder round.

## Round 2: hcom transport and client posture (2026-10-04)

- **Owner:** the `workers/agent-messaging` verdict in
  `evidence/artifacts/final-architecture-round2-20261004/verdicts.json` and
  `docs/decisions/2026-10-04-final-architecture-round2.md`; adopted by wave5.
- **Install:** https://github.com/aannoo/hcom/releases/tag/v0.7.27;
  release commit `2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b`.
  https://api.github.com/repos/aannoo/hcom/releases/tags/v0.7.27 publishes
  installer SHA-256 `3bc057fcd763748c32fae0ae25e150abf2b1df0d4c9451432c28f4ddde176a98`.
  https://github.com/aannoo/hcom/releases/download/v0.7.27/hcom-installer.sh:51-54,313,374-375,777-783
  supplies HCOM_NO_MODIFY_PATH/HCOM_INSTALL_DIR and checks the downloaded archive.
  The archive's published checksum is
  https://github.com/aannoo/hcom/releases/download/v0.7.27/hcom-x86_64-unknown-linux-gnu.tar.gz.sha256
  (`8ae97ff6fef63c637d66ddf882651aadd035bd74ae26c0787743869c20a5391d`).
- **Posture** (its deny list and Codex forbidden rules are superseded on 2026-10-06; see the relaxation below): accepted r1 at
  https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5972504465;
  aannoo/hcom@2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b:src/config.rs:126-152;
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/common.rs#L46.
  Native Claude deny and inbound keys:
  https://code.claude.com/docs/en/permissions and
  https://code.claude.com/docs/en/cross-session-messaging.
  Native Codex forbidden rules and checker:
  https://developers.openai.com/codex/rules;
  openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:codex-rs/core/src/exec_policy.rs:394-406,645.
- **CLI acceptance:**
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/tests/cli_smoke.rs#L129
  (`status_json_in_fresh_dir`, `list_json_empty`). The Bash commands parameterize
  those assertions against the installed binary; they are upstream-derived smoke
  integration, not an execution of the unchanged Cargo test suite.
- **Repository quality:**
  https://github.com/aannoo/hcom/actions/runs/36803903267;
  Linux real-tool jobs 110183965480 (Claude) and 110183965493 (Codex), steps 8/13
  successful. Native command and pins:
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/.github/workflows/ci.yml#L121.
  This builder ran no hcom install, model session, messaging E2E or new local trial.
- **Configuration glue:** this PR, tools/adoption/new_wsl_client_config.py:549,577,1623,2289;
  tools/adoption/apply_claude_settings.py:191; tools/adoption/managed_block.py:104.
  `config/hcom-client-config.py` reads the slot's map extension because the shared
  mapper enumerates existing template pieces only. It reuses those merge/block
  writers, preserving native authorization classification and existing inbound choices.
- **Known plain-Claude gap:**
  https://github.com/aannoo/hcom/releases/tag/v0.7.27;
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/claude.rs#L135
  returns silently without HCOM_PROCESS_ID. The no-wrapper posture uses start/listen
  and does not establish idle Claude wake. No global hook is authored to claim it.

The bounded source sweep reused the adopted candidate comparison and read the
selected release, installer, native formats, CLI assertions and tag CI. Scoped
ai-memory retrieval was unavailable under this job's tool approval policy; the
exact supplied posture and current source originals were read directly. Official
Claude doc fetches returned HTTP 403, so their native format references reuse the
source-accepted posture rather than claiming a new successful fetch. The builder's
Codex 0.159.3 native policy check returned forbidden; 0.160.0 remains the plan pin.
The accepted OS-sandbox boundary and prefix limitations remain explicit in the
[decision](../../../docs/decisions/2026-10-04-round2-plan-g1-messaging.md).

### Relaxation (2026-10-06)

- **Decision:** [hcom relaxation](../../../docs/decisions/2026-10-06-hcom-relaxation.md),
  on the user's decision of 2026-10-06T03:03:10Z (11:03 PM EDT on October 5). It
  removes the Claude hcom deny list, `config/hcom-deny.rules`, the adapter's
  running-Codex refusal and the forbidden-decision acceptance. Peer text stays
  data, never the user's approval.
- **Only Codex hcom policy:** upstream `hcom.rules`, which `hcom codex` writes
  with `auto_approve=true`:
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/codex.rs#L1538
  (build_codex_rules :1538-1563; written to `<codex home>/rules/hcom.rules` at
  :1566-1579), with the command list at
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/common.rs#L46
  (:46-72).
- **After-sign-in check, revised after the read at 3b6ea9d1e:**
  - **Codex home.** It derives the Codex home as hcom does: `CODEX_HOME`, else the parent of `HCOM_DIR`.
    https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/codex.rs#L72 (:72-75);
    https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/paths.rs#L26 (:26-53).
  - **Effective policy.** It passes every `*.rules` file there to `codex execpolicy check --rules`
    (https://developers.openai.com/codex/rules), the set Codex loads:
    https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/exec_policy.rs#L662 (:662-700, :1121-1170).
  - **Leftovers.** A stricter leftover file, or a retired Claude hcom deny entry, reports needs_user.
  - **Retained probe.** `../hcom-relaxation-20261006/probe-receipt.json` (synthetic; codex-cli 0.160.1, whose exec-policy code equals rust-v0.160.0).
- **Current release:** v0.7.27 at `2c5f343b` is still aannoo/hcom's latest
  release (`gh api repos/aannoo/hcom/releases/latest`, read 2026-10-06). Its
  plain-Claude hook guard is unchanged:
  https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/claude.rs#L135
  (:135-140).

## Round-2 G3 sources (2026-10-04)

North-star action: reproduce optimization, advisory skill vetting, local
trajectory analysis and MCP qualification for complex engineering and the
US-equities research/historical-simulation foundation. The owner selection is
`this PR: docs/decisions/2026-10-04-final-architecture-round2.md` and
`this PR: evidence/artifacts/final-architecture-round2-20261004/verdicts.json`.
No candidate or destination acceptance was executed by this builder.

- DSPy: [installation](https://github.com/stanfordnlp/dspy/blob/3.4.0/README.md#L31),
  `stanfordnlp/dspy@3.4.0:pyproject.toml:37` (exact GEPA dependency),
  [GEPA acceptance](https://github.com/stanfordnlp/dspy/blob/3.4.0/tests/teleprompt/test_gepa.py#L632),
  [Predict tests](https://github.com/stanfordnlp/dspy/blob/3.4.0/tests/predict/test_predict.py#L1),
  and [OpenAI-compatible LM configuration/call](https://github.com/stanfordnlp/dspy/blob/3.4.0/docs/docs/learn/programming/language_models.md#L139).
  Tag commit: `2413b67a4d08a476e4bc6f40b9f8f42f87711ee7`.
  [DSPy wheel hashes](https://pypi.org/pypi/dspy/3.4.0/json) and
  [GEPA wheel hashes](https://pypi.org/pypi/gepa/0.1.4/json) are checked before
  installing those artifacts. The resolved host lock is acceptance evidence for
  dependency identity, not an upstream lock or a model-quality result.
- SkillSpector: [uv-tool installation](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/README.md#L45),
  [CLI test entry point](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/tests/unit/test_cli.py#L17),
  `NVIDIA/skillspector@c7958a3268d9498644b22edb75d0f051bbc8cbfc:tests/unit/test_agent_cli.py:1`,
  [CI test command](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/.github/workflows/ci.yml#L97),
  [native Codex provider](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/cli.py#L560),
  and [actual JSON report schema](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1306).
  [v2.12.0 release-asset SHA-256 metadata](https://api.github.com/repos/NVIDIA/skillspector/releases/tags/v2.12.0)
  is recorded as publication evidence distinct from this Git-source install.
  There is no release signature/provenance claim.
- Scout: [installation](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/docs/index.qmd#L28),
  [Inspect AI dependency](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/pyproject.toml#L24),
  [Claude and ATIF import](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/docs/db_importing.qmd#L238),
  [upstream grep tests](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/tests/grep_scanner/test_grep_scanner.py#L1),
  [ATIF fixture acceptance](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/tests/sources/atif_source/test_integration.py#L44),
  [native import CLI](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/src/inspect_scout/_cli/import_command.py#L317),
  [tool-event scanner example](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/examples/scanner/grep_examples.py#L102),
  and [native result reader](https://github.com/meridianlabs-ai/inspect_scout/blob/0.5.3/src/inspect_scout/_scanresults.py#L83).
  Tag commit: `0e8fc055a3cebba1a14c11bc35856767b6405173`.
  [Scout hashes](https://pypi.org/pypi/inspect-scout/0.5.3/json) and
  [Harbor 0.23.0 hashes](https://pypi.org/pypi/harbor/0.23.0/json) are checked
  before installing their wheels in Scout's separate environment (the 2026-10-06 correction below supersedes the previous shared-runtime recipe). The grep config
  parameterizes upstream `grep_scanner`; import/scan still run through Scout.
  Current-session positive-control predicates are local integration checks.
- MCP: `modelcontextprotocol/conformance@c321dd32035556e6769d3724a8ee97d87c3faaac:README.md:12,23,147,188`
  ([npx and protocol requirements](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/README.md#L147)),
  [unchanged CI acceptance](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/.github/workflows/ci.yml#L33),
  [alpha.11 npm integrity](https://registry.npmjs.org/@modelcontextprotocol%2Fconformance/0.2.0-alpha.11),
  and [SLSA provenance](https://registry.npmjs.org/-/npm/v1/attestations/@modelcontextprotocol%2fconformance@0.2.0-alpha.11).
  The source is the published main-ancestor commit, not alpha.12's publication
  branch. The verdict's alpha.12 cooldown ends 2026-10-08T12:07:36Z.
- uv integration: `astral-sh/uv@0.12.22:docs/guides/projects.md:139`,
  [project dependency management](https://github.com/astral-sh/uv/blob/0.12.22/docs/guides/projects.md#L139),
  [file sources](https://github.com/astral-sh/uv/blob/0.12.22/docs/concepts/projects/dependencies.md#L412),
  and [shared tool dependencies/executable export](https://github.com/astral-sh/uv/blob/0.12.22/docs/guides/tools.md#L225).
  Installed uv 0.12.17 help confirmed the used init/add and
  `--with-executables-from` forms; the destination plan retains uv 0.12.22.

## Wave 5 browser owner (2026-10-04)

Owner authority: `docs/decisions/2026-10-04-final-architecture-round2.md` and
`evidence/artifacts/final-architecture-round2-20261004/verdicts.json`, verdicts
`web-research/playwright-cli` and `browser-debugging`. Their merge selects one
stdio MCP server, never the experimental CLI or a second diagnostics install.
The preceding Playwright fix-wave observations remain historical predecessor
evidence and do not accept this owner.

Every Chrome source below was read at
ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df
(`chrome-devtools-mcp-v1.10.1`, npm 1.10.1). The [release changelog](https://github.com/ChromeDevTools/chrome-devtools-mcp/releases/tag/chrome-devtools-mcp-v1.10.1)
reports the bundle export-conditions fix; its target commit and the npm gitHead
match the pin.

- [Linux-side WSL Chrome install, docs/troubleshooting.md:99-105](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/troubleshooting.md#L99) identifies Linux-side stable amd64 Chrome. [README.md:64-65](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/README.md#L64) requires Node LTS and current stable Chrome or newer. The recipe uses [Google's signed apt repository and published key](https://www.google.com/linuxrepositories/) with pinned primary fingerprint EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796, restricted Signed-By and current-stable installation. It records the installed version; acceptance checks Google repository origin and minimum 154.0.8037.97-1, permitting later builds. The downloaded package digest and postinst source locators in [the sanitized receipt](../final-architecture-round2-20261004/repair-round2-sources-20261005.json) verify why repo_add_once=false and a separate source filename prevent package-managed Signed-By conflicts.
- [Claude CLI setup, docs/client-configurations.md:71](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/client-configurations.md#L71) and [Codex CLI setup, :109](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/client-configurations.md#L109). Parameterization replaces `@latest` with 1.10.1, adds the documented `-y`, and forwards the required server flags with the native `--` separator. Installed `claude mcp add --help` and `codex mcp add --help` confirm that syntax without registering anything on this builder host.
- [Flags, docs/configuration.md:79,88](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/configuration.md#L79), [independent sessions, docs/advanced-usage.md:22-25](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/advanced-usage.md#L22), [telemetry opt-out, README.md:45](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/README.md#L45). `--headless --isolated --no-usage-statistics` are mandatory here. [README.md:35-39](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/README.md#L35) documents the independent optional CrUX opt-out.
- [npm release metadata and published SHA512 SRI](https://registry.npmjs.org/chrome-devtools-mcp/1.10.1): `sha512-Klw6HWDqHC/XS1JwZldd2r49aUhbUJN9m9Mvcx4SEueIPXtzuQX+QelxAViobv8YUkDZ7HWDrmViR6LeYK0wAw==`; hex `2a5c3a1d60ea1c2fd74b527066575ddabe3d69485b50937d9bd32f731e1212e7883d7b73b905fe41e9710158a86eff185240d9ec7583ae656247a2de60ad3003`. The digest is base64-decoded from upstream metadata, not a locally invented checksum. `package.json:104-105` sets engines `^20.19.0 || ^22.12.0 || >=23`; the plan's Node 24.21.0 satisfies it.
- [Release CI preparation and test invocation, .github/workflows/run-tests.yml:30-74](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/.github/workflows/run-tests.yml#L30) and [scripts/test.js:28-38](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/scripts/test.js#L28). The upstream runner accepts explicit original test filenames. This row selects `tests/index.test.ts` and `tests/tools/{pages,snapshot,console,network,performance}.test.ts`; unchanged files, no invented E2E runner. [tests/index.test.ts:38-48](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/tests/index.test.ts#L38) starts the MCP server headless/isolated. This row selects installed Linux-side Chrome stable through the supported `PUPPETEER_EXECUTABLE_PATH`; it downloads no additional Chrome for Testing browser.
- [First client prompt, README.md:105-116](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/README.md#L105), [navigate_page, docs/tool-reference.md:223](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L223), [list_console_messages, :431](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L431), [take_snapshot, :462](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L462). `after_sign_in` adapts those native operations to this PR's local synthetic fixture and native event assertions. It is project integration, not an unchanged upstream test, a model trial or a selection result.
- Native Codex configuration source: [official MCP guide](https://developers.openai.com/codex/mcp), and [openai/codex@rust-v0.160.0:codex-rs/cli/src/mcp_cmd.rs:937-980](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/mcp_cmd.rs#L937). The pinned implementation returns the `transport.type`, `transport.command` and `transport.args` JSON fields used by the targeted registration check. The existing `serena` acceptance in this plan is the main-source reference for Claude and Codex event/result correlation; this PR changes its tool names and oracle to the browser fixture.
- Native signed-source and dependency handling use [Debian's Signed-By semantics](https://manpages.debian.org/bookworm/apt/sources.list.5.en.html) and [Ubuntu 26.04 apt-get(8)](https://manpages.ubuntu.com/manpages/resolute/en/man8/apt-get.8.html); these are OS integration, not a Chrome upstream test or an observed destination pass.

No install, Chrome launch, upstream browser test, native model invocation or
comparative trial was executed for this browser owner by this builder.

- Explicit installed-browser test selection: [puppeteer/puppeteer@puppeteer-v25.11.0:packages/puppeteer/src/getConfiguration.ts:140-145](https://github.com/puppeteer/puppeteer/blob/puppeteer-v25.11.0/packages/puppeteer/src/getConfiguration.ts#L140) reads `PUPPETEER_EXECUTABLE_PATH` into executable configuration. The pinned MCP [tests/utils.ts:89-92](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/tests/utils.ts#L89) also passes that environment directly to browser launch. The row does not copy the CI's host-wide AppArmor-disable operation into destination setup.

## Round-2 G4 existing-owner configuration (2026-10-04)

This section records the bounded `r2-g4-config` source checks. The earlier
canary sections describe historical fix-wave recipes; the round-2 clean gateway
row proposes published 3.8.51 with native Codex as the only Sol/max route.
Stack and architecture pin changes are deferred pending the saturation audit
and qualification receipt required by `this PR:tests/test_stack_lifecycle.py:21-37`.
No upstream install, provider inference, gateway request or new local trial ran
in this builder.

- **Promptfoo providers and skills:** `promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8:site/docs/guides/test-agent-skills.md:204`
  ([guide](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/guides/test-agent-skills.md#L204));
  `:site/docs/providers/claude-agent-sdk.md:45` documents native sign-in with
  `apiKeyRequired=false`, and `:890` documents the custom CLI path
  ([provider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/providers/claude-agent-sdk.md#L45));
  `:site/docs/providers/openai-codex-sdk.md:62` documents native ChatGPT sign-in
  and the authentication boundary of an overridden CODEX_HOME; `:232` documents
  `codex_path_override`
  ([provider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/providers/openai-codex-sdk.md#L62)).
  Retain the existing published 0.123.1 tarball SHA256 and unchanged upstream
  echo fixtures documented above. `npm ls --global --prefix <owned-prefix>
  --all @anthropic-ai/claude-agent-sdk @openai/codex-sdk` checks both optional
  providers, as the verdict's install note requires. Native provider execution
  remains owed. The config explicitly selects both host binaries and native
  sign-ins; the paired project fixtures and inverted skill assertion are
  supported-harness integration, not unchanged upstream test acceptance.
- **Research configuration:** `assafelovic/gpt-researcher@0957c301ed06c2a5857b834358c7227c739041d4:gpt_researcher/config/config.py:63`
  and `:158`
  ([config](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/config/config.py#L63));
  `bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e:backend/packages/harness/deerflow/config/app_config.py:681`
  ([effective config](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/config/app_config.py#L681));
  `:backend/packages/harness/deerflow/client.py:1229`
  ([model read-back](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/client.py#L1229)).
  The existing pinned keyless configs and upstream `tests/test_client.py` are
  retained. Read-back adds endpoint/model/tool checks without printing keys.
  [This PR](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files)
  carries `tools/research/gpt_researcher.sh:27`: the installed runner starts
  from `env -i`, with its per-run CONFIG_PATH and literal keyless-loopback
  placeholder. Consumer runs and independent gateway zero-embeddings
  observation remain owed.
- **Clean gateway installation and effort boundary:**
  `diegosouzapw/OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:docs/guides/SETUP_GUIDE.md:28`
  ([npm installation](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/docs/guides/SETUP_GUIDE.md#L28));
  `:open-sse/executors/codex/reasoningSuffix.ts:11`
  ([alias sets](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts#L11));
  `:open-sse/executors/codex.ts:331`
  ([clamp](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex.ts#L331));
  `:bin/cli/commands/doctor.mjs:632`
  ([upstream acceptance command](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/bin/cli/commands/doctor.mjs#L632)).
  [The registry](https://registry.npmjs.org/omniroute/3.8.51) publishes
  `sha512-VwwSt+bP9lJiPJXFJMz0nNGGuoewPZU3nFe1SLuO11ADgdSwTegGCxhg8Ov75+31m/cocPxHiO63zygn1XQ0MQ==`.
  The recipe compares that SRI before native npm install, which enforces
  downloaded package integrity. Published SLSA provenance is a source record,
  not a verified attestation here. [PR #15167](https://github.com/diegosouzapw/OmniRoute/pull/15167)
  was queried through `gh api` on 2026-10-04 and is open/unmerged.
  The map overrides the destination pool/fallback profile to Sol/xhigh and
  disables the standalone-search settings whose previous source was the
  PR #13788 carry. Re-pin only to a release with both Sol alias entries and a
  separately observed max-effort wire request.
- **Native Codex routing:** installed `codex --version` and `codex exec --help`
  report the builder's 0.159.3 CLI; the clean host's separate selected pin is
  rust-v0.160.0. Its
  [release record](https://github.com/openai/codex/releases/tag/rust-v0.160.0),
  [SDK documentation](https://developers.openai.com/codex/sdk/),
  [config reference](https://developers.openai.com/codex/config-reference/)
  and [noninteractive events](https://developers.openai.com/codex/noninteractive/)
  were retrieved. Path discovery and native flags do not claim a new model run.
- **Harbor installation integrity:**
  [PyPI 0.23.0](https://pypi.org/pypi/harbor/0.23.0/json) publishes wheel
  `harbor-0.23.0-py3-none-any.whl` SHA256
  `8747400dbb2a5e2298e1338e17e88eba38433c0433fd700f34d1a9021bba5c37`.
  `fetch_verified` verifies that exact wheel before the supported
  `uv tool install --python 3.13 <wheel>` invocation. This does not establish
  PyPI attestations or hashes of the wheel's dependency tree.
  [uv's native install reference](https://docs.astral.sh/uv/reference/cli/#uv-tool-install)
  and installed `uv tool install --help` were read.
- **Harbor qualification:**
  `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:tests/unit/test_trajectory_validator.py:1`
  ([unchanged unit acceptance](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/tests/unit/test_trajectory_validator.py#L1));
  `:docs-mintlify/core-concepts/jobs/configs.mdx:6`
  ([native job configs](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/docs-mintlify/core-concepts/jobs/configs.mdx#L6));
  `:docs-mintlify/core-concepts/agents/atif.mdx:121`
  ([upstream trajectory validator](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/docs-mintlify/core-concepts/agents/atif.mdx#L121));
  `:src/harbor/agents/installed/base.py:560`,
  `:src/harbor/agents/installed/codex.py:328`,
  `:src/harbor/agents/installed/openhands_sdk.py:150`,
  `:src/harbor/agents/installed/deerflow.py:181` establish documented native
  adapter pinning. `:src/harbor/models/trial/result.py:76` describes retained native
  trial receipts. `:tests/integration/test_hello_user_e2e.py:25`
  remains the source for the unchanged hello-user controls and the qualified
  verifier reward/exception assertions. The new shell recipe only invokes the
  upstream runner/validator; the maintained native-verifier corpus is
  `needs_user` and no trial is invented. ATIF schema acceptance is separate from
  the native telemetry-contract assertions described in
  `config/harbor-worker-telemetry-contract.md`.

## Currency qualification source scope (2026-10-05)

Selected 0.162.0; qualified on scratch/synthetic validation only (evidence/receipts/otelcol-contrib-0162-qualification-20261003.json:11-15); host acceptance pending. NativeStack2604 release hold: the release-tag build-and-test failed (docs/decisions/2026-10-04-2604-e2e-fix-wave.md:117).

Selected 13.2.3 in the WSL profile/install plan; qualified on scratch/synthetic validation only (W1b receipt:11-14, https://github.com/seathatflowsinourveins/native-agent-stack/blob/748f701e1ac871dca378f9ef41bfd81e457cb3f7/evidence/receipts/grafana-1323-qualification-20261003.json#L11-L14); host acceptance pending. NativeStack2604 release hold: open regression reports grafana/grafana#133835 and #133856 (docs/decisions/2026-10-04-2604-e2e-fix-wave.md:117). The host stack remains 13.2.2 at this head.

The W1b receipt was read from local Git commit `748f701e1`; it is not a tracked file at this PR head. Source and qualification records were read without network access; no historical commands were replayed.

## NativeStack2604 acceptance defect repairs (2026-10-05)

[The dated decision](../../../docs/decisions/2026-10-05-ns2604-acceptance-defect-repairs.md)
maps every changed behavior to its installed-client help, release, pinned source or official documentation.
The selected sources are Claude Code 2.1.289 native headless flags and incremental skill announcements;
Codex 0.160.0 native configuration, custom review and JSON event schema; Inspector 2.9.0 CLI/Web
workflow and Playwright 1.62.1 host-library installation; inspect_ai 0.3.273 task resolution;
agentsview 9be7745 archive installation and the plan's own 3e343ba6 predecessor; SocratiCode
f6191f0 endpoint configuration; Git 2.53.0 raw working-tree/index diff controls; context-mode
6f0cc684 bounded file-output routing and partial-result semantics; Linux ip-sysctl allocation
rules and iproute2 v6.19.0 all-state local source-port filtering; and the superseding
2026-10-04 carrier holdout decisions. The decision gives exact source locators and limits.
The native CLI's 48-turn budget and integration predicates are local choices qualified through native
reruns, not upstream recommendations. Native upstream smokes, native client integration, local
tests, synthetic fixtures and historical co-op evidence remain separate.

The official-upstream rule removed the duplicate fresh-session launcher. Anthropic's own
[migration guide at 2988cbe14a98691d372924b88adf410a9c52b221:22–26](https://github.com/anthropics/claude-code-action/blob/2988cbe14a98691d372924b88adf410a9c52b221/docs/migration-guide.md#L22)
uses native CLI arguments for instructions, turn limits and tool selection. The plan now invokes
Claude directly while preserving those arguments; it does not rebuild or replace the client.

## Additional acceptance defects 11–12 (2026-10-05)

- DeerFlow v2.1.0, pin `345f08be00c8a9495079b732a39b46aa9af1584e`: [native headless CLI:1837–1846](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1837), [JSON streaming:274–285](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/tui/cli.py#L274), [checkpointed session:84–98](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/tui/session.py#L84), [native final-message contract:1193–1223](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/client.py#L1193), [documented search tools:801–927](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L801), [Tavily adapter:18–45](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/community/tavily/tools.py#L18), and [DDGS empty-result handling:134–191](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/community/ddg_search/tools.py#L134). Keep the default keyless and use the shipped CLI with native recursion 100 and explicit public config. The measured Tavily adapter remains a ready-to-apply proposal through the existing masked credential pointer; it requires a command-center ruling before adoption. Private artifacts and matched search/final-citation assertions are local integration, not a new agent runtime. The separate thirty-query owner gate remains unchanged.
- OpenHands SDK v1.50.1, pin `1e1390acc8788346ba4804c34323284009bf3f5e`: [supported subprocess terminal:283–306](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-tools/openhands/tools/terminal/definition.py#L283), [unchanged forced-terminal execution test:69–86](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/tests/tools/terminal/test_terminal_tool_auto_detection.py#L69). Select this one real terminal-action test under the per-job sandbox, then retain the closed-port negative and both actual model-backed worker jobs. Default-tmux, autodetection, other tool and provider suites are omitted from the focused selection; no whole-suite claim follows.
- SRT v0.0.77 (`6fa731368807419ee157f9a3fac955fefe1019c6`) and v0.0.78 (`6f0ce155ccb136bda33a8a72201fe7f54fe47d9b`): [Unix-socket settings:391–399](https://github.com/anthropics/sandbox-runtime/blob/v0.0.78/README.md#L391). allowUnixSockets is macOS-only; allowAllUnixSockets broadens Linux seccomp and stays unset. Isolated native controls retain default-tmux/AF_UNIX failures and unchanged subprocess-test passes at both pins. The host worker already selects subprocess; no sandbox, unit, worker or host pin is changed.
- Currency qualification: [mise v2026.10.1 directories:13–23](https://github.com/jdx/mise/blob/v2026.10.1/docs/directories.md#L13), [installer path/version controls:127–128](https://github.com/jdx/mise/blob/v2026.10.1/docs/installing-mise.md#L127). The anti-pattern describes likely shared-plan contention and an unattributed writer; competing revisions belong in isolated executable/config/data/state/cache roots or a throwaway measurement distribution.

Detailed alternatives, repeated native observations, omissions and the completeness critic are in
[the repair decision](../../../docs/decisions/2026-10-05-ns2604-acceptance-defect-repairs.md#additional-defects-1112-and-shared-host-qualification).

- Foreground worker command: [RTK v0.51.0 e001f77 argv preservation:3205–3221](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/main.rs#L3205), [direct spawn:3275–3281](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/main.rs#L3275), [Unix argument forwarding:575–580](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/core/utils.rs#L575); [systemd v259.5 private user-manager bus:273–300](https://github.com/systemd/systemd/blob/v259.5/src/shared/bus-util.c#L273), [user-bus fallback:510–540](https://github.com/systemd/systemd/blob/v259.5/src/shared/bus-util.c#L510). Separately quoted native arguments and public per-command bus locators preserve Codex's environment policy. Source review does not establish the cause of the retained nested-shell escaping failure.

- Fresh-session foreground control: installed Claude 2.1.289 and [anthropics/claude-code@2bfb629 CHANGELOG.md:6865](https://github.com/anthropics/claude-code/blob/2bfb629dfaff0c8318047a4beb93cf1dc5b58b18/CHANGELOG.md#L6865), [official environment variables](https://code.claude.com/docs/en/env-vars#variables), [background commands](https://code.claude.com/docs/en/interactive-mode#background-bash-commands). Five original repaired callers keep native 48-turn execution, add explicit foreground/wait instructions and use the per-invocation background-disable control. Linked-result oracles cover MCP results independently.
- Keyless availability and usage: [DeerFlow@345f08be DDGS empty/caught-error contract:128–153,190–191](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/ddg_search/tools.py#L128), [deduplicated native usage:989–1021](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/client.py#L989), [terminal end:1191](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/client.py#L1191). Preserve the keyless owner ruling; availability-only and incomplete gatherer outputs fail acceptance, retain both status axes, and leave terminal usage unknown when no unique end exists.

- SRT scratch under Codex inherit=none: [sandbox-runtime@6f0ce155 Linux empty mount:452](https://github.com/anthropics/sandbox-runtime/blob/6f0ce155ccb136bda33a8a72201fe7f54fe47d9b/src/sandbox/linux-sandbox-utils.ts#L452), [HTTP/SOCKS bridge sockets:1189–1192](https://github.com/anthropics/sandbox-runtime/blob/6f0ce155ccb136bda33a8a72201fe7f54fe47d9b/src/sandbox/linux-sandbox-utils.ts#L1189), [Node v24.21.0 tmpdir precedence:418–420](https://github.com/nodejs/node/blob/v24.21.0/doc/api/os.md#L418). Shell-quote and export the already validated allow-write fixture directory as TMPDIR. Native bridge socket basenames require short owned paths; this changes neither client inheritance nor the policy's allowed scope.

- Review completion versus command success: [official linked tool-result error semantics](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error). Installed Claude 2.1.289 native artifact SHA256 a186b99e4a9c88366cd49df2f7dad56c61fc306ef0140b19ee64b7c42a8d1348: zero-based byte208923207 formats terminal Bash exit headers; byte207598656 defines interruption137/timeout143; byte211587666 begins the native Bash result formatter and includes the abort diagnostic. Only the cross-review completion oracle allows verified ordinary failed Bash analysis commands; mandatory native session-success/report/snapshot gates remain strict. The retained native session-limit failures are not acceptance.
## Additional acceptance defect 13 (2026-10-05)

- Promptfoo 0.123.1, tag pin `34f74d34e140b5e17d23770dfb2340057b1936b8`: installed `--version`, `--help` and `eval --help` all returned 0; [release](https://github.com/promptfoo/promptfoo/releases/tag/0.123.1), [native CommonJS config import:383–405](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/util/config/load.ts#L383), [OpenAI-compatible endpoint and key-name options:233–251](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/providers/openai.md#L233), [native gateway example:1–24](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/examples/openai-compatible-gateway/promptfooconfig.yaml#L1). Read nonsecret endpoint/IDs from the plan topology in the supported config module; `apiKeyEnvar` carries only the inventory key's name. No custom renderer, evaluator, provider or upstream rebuild is added.
- Model selection is unresolved in the initial source unit: [prospective #713 topology at cde8a0de](https://github.com/seathatflowsinourveins/native-agent-stack/blob/cde8a0de060ca37fee6a2353f494f15a4bbdede1/evidence/artifacts/new-wsl-install-plan-20261002/config/gpt-gateway-topology.json) has no Claude route. Native model-catalog metadata is discovery, not binding or acceptance. The [decision](../../../docs/decisions/2026-10-05-ns2604-acceptance-defect-repairs.md#defect-13-canonical-promptfoo-gateway-configuration) records the pending governing route, alternatives and completeness critic.
## Shared native execution instructions and observability repairs (2026-10-05)

- Claude uses one check-data text through its native [append-system-prompt-file flag](https://code.claude.com/docs/en/cli-reference#system-prompt-flags). Check-specific restrictions remain in the task prompt; no execution wrapper is added. Installed2.1.289 supports the flag in its public parser (binary digest recorded above). Its help omits max-turns; [v2.1.285 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.285) and [v2.1.281 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.281) document that native limit. Earlier help-source wording was corrected in the anti-pattern log.
- Closed-port acceptance follows [CPython v3.13.16 connect_ex:1497–1504](https://github.com/python/cpython/blob/v3.13.16/Doc/library/socket.rst#L1497): zero means success; other values are errno. Combine a failed connection with [iproute2 v6.19.0 ss LISTEN and sport filters](https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/man/man8/ss.8?h=v6.19.0#n497). The co-op observed EAGAIN on mirrored WSL; that host observation is separate from these API semantics. Reject an observed listener even when a connect fails.
- Superseded observability render recognition is repository custody glue, extended from the plan publisher with two exact co-op-designated historical SHA256 digests per filename. Historical render inputs have not been reconstructed. Operator migration custody overrides every digest match; unknown configs and retained OTel configs return nonzero needs_owner. Keep [OTel v0.162.0 validate](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.162.0/otelcol/command_validate.go#L15) and [Promtool v3.15.0 check config](https://github.com/prometheus/prometheus/blob/v3.15.0/cmd/promtool/main.go#L128) as the native configuration validators. Synthetic transition/refusal tests are local integration evidence, separate from native acceptance.
## Shared Claude budget and delivered cross-review (2026-10-05)

- Per-direction deadlines reuse installed [uutils/coreutils 0.10.0 timeout.rs:280–308](https://github.com/uutils/coreutils/blob/0.10.0/src/uu/timeout/src/timeout.rs#L280), verified by timeout --version and --help. Each sequential native review has 1200 seconds of observation and 15 seconds of kill grace; the combined observation budget is 2400 seconds. Claude lock wait is included. The frozen prompts and 48-turn budget are unchanged.
- Retain the exact invoked argument arrays. Ordinary native Codex persistence replaces [ephemeral suppression:31–33](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/cli.rs#L31) so [reviewer turn_context model/effort:3335,3352](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/protocol/src/protocol.rs#L3335) can be bound to those arguments. The private metadata receipt records the custom target and successful immutable git show, native Claude init model, and unknown native effort when absent. It requires a separate gateway observation before qualification; argv is a requested setting, not proof of provider behavior.

- The co-op's account-budget instruction serializes every fresh Claude call with native [util-linuxv2.41.3 flock command/timeout mode](https://github.com/util-linux/util-linux/blob/v2.41.3/sys-utils/flock.1.adoc). The default is the single co-op lock; a private fixture override prevents synthetic tests from holding the live account lock. No wrapper, account change or Codex/GPT lock is added. Existing stage timeouts still bound waiting and execution; paper windows bound the entire invocation.
- Native Claude [JSON Schema delivery](https://code.claude.com/docs/en/headless#get-structured-output) emits structured_output in the terminal result. Installed2.1.289 public binary SHA256a186b99e4a9c88366cd49df2f7dad56c61fc306ef0140b19ee64b7c42a8d1348: byte205736331 returns the structured payload/endsTurn; byte215938533 attaches it to the result; byte226386984 preserves that stream result. Native [disallowedTools and json-schema flags](https://code.claude.com/docs/en/cli-reference#cli-flags) block Workflow/Agent handoff and request the report shape. Require a single successful terminal, exact frozen head, consistent findings/no_findings verdict, typed locations and a substantive summary; retain the delivered JSON privately. Reject status-only success, background termination and uncompleted shell calls. These delivery gates do not establish finding correctness or cross-family qualification.
## Prometheus required startup-feature observation (2026-10-05)

- D-ollama2026-10-05/task-ns2604-coop-20261005T142343Z point1 carries the user's2026-10-03 lasting destination GPU-owner ruling. It supersedes the historical startup/ownership limitation in docs/decisions/2026-10-03-new-wsl-local-models.md:254–257. Unit form follows [Ollama v0.35.0 docs/linux.mdx:57–89](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/linux.mdx#L57); docs/linux.md is absent at this tag. The initial owner-approved user adaptation and warmup had SHA25694e03d7b35b57327086b74a1ea7b189bf362c970e756703dc8a1f42340618c50 and2236dc865fde718d7cd44a9182b17fb55dcd36a0bbd601e9f4bd81d1c35892e5, historical bytes at64f11b1069455e7c3a6483974524896c62cb4281. D-ollama-2 supersedes the unit and removes the warmup from the current plan. Native user-unit daemon-reload/enable follows the plan's maintained ai-memory pattern at ff9ff041 install.sh:368. [systemctl native enabled/active queries](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html) accept boot/runtime state without activating anything. Host apply is exclusively co-op/readiness-runner; source and hash checks are not GPU/model acceptance.

- A27's render-only unit extends the existing config publisher from [native-agent-stack@f946c6d4 configure.py:100,107–110](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f946c6d4ca988a17b6fa4392ecb488909f147883/observability/backends/configure.py#L100), governed by [G4:103–109](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f946c6d4ca988a17b6fa4392ecb488909f147883/docs/decisions/2026-10-04-2604-e2e-fix-wave-g4-observability.md#L103). Plan release/port/features render the candidate under config_root; existing digest custody rejects operator edits or symlinks with nonzero needs_owner. No active unit or service state is changed; runtime-data creation and activation remain with the shared-host plan-apply owner. The native flags guard remains the observation of effective running configuration.

- Prometheusv3.15.0 pin5241a27fe3c6983549fccc32f6e65917408c63cd: [zero-sample ingestion dispatch:270–280](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/cmd/prometheus/main.go#L270), [extended-range selector dispatch:314–316](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/cmd/prometheus/main.go#L314), [native status/flags API:1447](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/querying/api.md#L1447). The plan stores both required names and service_health retains the returned JSON privately before checking exact membership. Readiness alone is insufficient.
- Governing repository decision docs/decisions/2026-10-04-2604-e2e-fix-wave-g4-observability.md:103–109 points to observability/backends/configure.py:100. That maintained producer already emits both flags for ecosystem-prometheus.service. The initial search found no public ns2604 producer; A27 settles the render-only adaptation above. No unit hand-edit, restart or claim of complete D16 repair is made. [Feature documentation:64–84](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/feature_flags.md#L64) also requires exposed start timestamps; flags alone do not establish corrected counter accounting.

## Read-only review surface after the retained turn-limit failure (2026-10-05)

- A31 keeps the frozen prompt, fixture, schema,48turns and1200-second direction bound. Native [tools and permission-mode flags](https://code.claude.com/docs/en/cli-reference#cli-flags) select Read/Glob/Grep with dontAsk; [MCP tool-name wildcards](https://code.claude.com/docs/en/permissions#tool-name-wildcards) deny mcp__* alongside Workflow/Agent. No execution wrapper or upstream rebuild is added.
- Installed anthropics/claude-code2.1.289 binary SHA256a186b99e4a9c88366cd49df2f7dad56c61fc306ef0140b19ee64b7c42a8d1348: byte102561956 defines --tools; byte217226707 parses selection. Bytes216934252-216934596 append the generated-schema tool after built-in selection; bytes205735635-205736331 mark it enabled/read-only and return structured_output with endsTurn. [Pinned changelog:4008](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md#L4008) documents dedicated Glob/Grep in v2.1.162. Compatibility proof is distinct from fresh-session delivery.
- Attribution correction: the failed run's retained argv explicitly passed --permission-mode plan; native init agrees and the stream contains no EnterPlanMode call. Its error_max_turns and planning artifact remain failure evidence. [Plan-mode workflow](https://code.claude.com/docs/en/permission-modes#analyze-before-you-edit-with-plan-mode) explains the surface, not a proven cause.

## Codex native gatherer polling after a retained MCP deadline (2026-10-05)

- [Official MCP timeout configuration](https://learn.chatgpt.com/docs/config-file/config-reference) documents a separate per-tool cap. Its current60-second default differs from the pinned client: openai/codex rust-v0.160.0 pin a956835d020762cb2b570053af06f643a11c0ecc [rmcp_client.rs:106](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/codex-mcp/src/rmcp_client.rs#L106) defaults to300seconds; [connection_manager.rs:360–363,1014–1018](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/codex-mcp/src/connection_manager.rs#L1014) selects the configured/default cap and takes the smaller client/requested deadline. A600000ms server argument cannot extend that cap.
- Codex-only execution data uses the unchanged upstream [exec_command yield contract:30–34](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/tools/handlers/shell_spec.rs#L30), [empty write_stdin polling:117–134](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/tools/handlers/shell_spec.rs#L117), and [session/exit output:210–216](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/tools/handlers/shell_spec.rs#L210). [Native process_manager.rs:1013–1021,1068–1081](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/unified_exec/process_manager.rs#L1068) keeps the same session while alive and returns its final exit when finished. Commands, queries, isolated state, keyless provider and execute-once rules remain unchanged; Claude's prompt is byte-identical.
- The task's direct native long-command instruction takes precedence over the context-mode skill's external-service routing. Gatherer stdout/stderr are already redirected; only completion markers return through the native executor. Large retained-file analysis still uses the token-processing lane. No wrapper, hook bypass, broad inheritance, install or host config edit is introduced. The original300-second failed call remains failed even though its later artifact completed.

## Post-#713 source reconciliation (2026-10-05)

- Actual #713 merge1796303f957c522e78b92667e553c06840fae3a2, replayed onto mainbea3d7f24f091ca19fcf264f5bce32a8e476c936. Keep main's additional rows, production OpenHands/SRT assets and plain Sol/xhigh consumer settings while preserving the lane's native CLI/completion/readonly review repairs. Git's [native interactive fixup/drop protocol](https://git-scm.com/docs/git-rebase#_interactive_mode) omits only verified registry-only commits; main's registry is rebuilt with the maintained register_file interface and committed last.
- Reuse main's [DeerFlow per-run header producer:14–24](https://github.com/seathatflowsinourveins/native-agent-stack/blob/bea3d7f24f091ca19fcf264f5bce32a8e476c936/evidence/artifacts/new-wsl-install-plan-20261002/config/deer-flow-research.sh#L14) before the pinned native CLI. Its selected public config is retained and a per-run copy receives x-omniroute-session-id. DeerFlow@345f08be [extra model options:26](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/config/model_config.py#L26) and [provider settings passthrough:209–227,343](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/models/factory.py#L209) support the same settings through that CLI.
- The existing [metadata observer:92–108](https://github.com/seathatflowsinourveins/native-agent-stack/blob/bea3d7f24f091ca19fcf264f5bce32a8e476c936/evidence/artifacts/new-wsl-install-plan-20261002/config/gateway-effort-accept.py#L92) distinguishes source-expected effort from delivered wire effort. A window/model fallback cannot prove attribution or whole-run zero embeddings. Preserve that limitation; fresh completion and broader provider qualification remain separate.
- Inspector's qualified source SHA256 is2f82b600dcebf957cfbec84bd85ba64b5abbafde20283392b03ff5dfa150f811; its Git blob is a478d7557b40e68a0774b1cad8fabdc6a9236eca. The prefix was initially mistaken for a Git object in a worker lead; exact hashing/object inspection corrected it. The newly merged Chrome fresh caller uses the same [native flock](https://github.com/util-linux/util-linux/blob/v2.41.3/sys-utils/flock.1.adoc) required by the co-op, with its original arguments unchanged.

## Native stream metadata receiver (2026-10-05)

- Installed Claude2.1.289 returned two system/permission_denied records with string-valued message during the frozen post-rebase review. Python/cpython@v3.13.16 [JSON conversion:383–389](https://github.com/python/cpython/blob/v3.13.16/Doc/library/json.rst#L383) maps strings to str and objects to dict. Guard message before content lookup, following repository@70989367:tools/token-e2e/evidence.py:130, tools/token-e2e/judge.py:1187 and tools/sota-convergence/transcript_audit.py:134. Native [permissions](https://code.claude.com/docs/en/permissions) remain upstream-owned; notices do not count as completed tool calls.
- The bounded variant scan covers exact/variable/quote/escaped-JSON/indexed/alias forms and the unfiltered Inspector/worker/research receivers. Preserve terminal, linked command/result, frozen recipe, independent artifact and no-background gates. Two trading-owned callers are handed off; historical exports are retained. Synthetic malformed-metadata fixtures and original-stream replay are local integration, distinct from the native stage's exit1.
- Successful num_turns and maxTurns enforcement use distinct counters in the installed binary SHA256a186b99e4a9c88366cd49df2f7dad56c61fc306ef0140b19ee64b7c42a8d1348: success-counter initialization/increment/emission at bytes215929957/215930226/215938395; guard read/comparison at215805078/215865311. Returned num_turns62 and argv48 do not establish a budget increase; the actual guard count is unobserved.

## Ready roadmap jobs3–5 (2026-10-05)

- Skills uses native mktemp/EXIT-trap redirection, already present in seathatflowsinourveins/native-agent-stack@dd9b06ba69c77a62f5553cdc119061082c783564:evidence/artifacts/new-wsl-install-plan-20261002/accept.sh:256–260. vercel-labs/skills@v1.7.0 [CLI listing:419](https://github.com/vercel-labs/skills/blob/v1.7.0/src/cli.ts#L419) and src/list.ts:127 emit JSON; Node v24.21.0 [process.exit:4228](https://github.com/nodejs/node/blob/v24.21.0/doc/api/process.md#L4228) documents possible truncation of pending stdout. Preserve both agent and pinned-folder-hash checks. Native post_install0 and synthetic producer/parse/agent/hash/cleanup controls are separate.
- Betterleaks@v1.9.0 pin81aff7a638638aae3a659845d089043e1d8fe9ac [Makefile:15–16](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/Makefile#L15) supplies unchanged make test. Redirect only that command's stdout to stderr because seathatflowsinourveins/native-agent-stack@dd9b06ba69c77a62f5553cdc119061082c783564:evidence/artifacts/new-wsl-install-plan-20261002/accept.sh:61 discards ordinary stdout. A stand-in verifies preservation and native-exit propagation; it is not an upstream test. P1 and required gitleaks gate remain unchanged.
- SRT@v0.0.78 [README:166–179](https://github.com/anthropics/sandbox-runtime/blob/v0.0.78/README.md#L166) supplies the native smoke and --settings interface; deny/allow controls compose that interface as local integration. Explicit native Bash exits preserve nested read/hash failures; unique marker validation accompanies exact foreground recipe and linked returned output. Reuse seathatflowsinourveins/native-agent-stack@dd9b06ba69c77a62f5553cdc119061082c783564:evidence/artifacts/new-wsl-install-plan-20261002/accept.sh:2117–2122,2229 completion/decoder patterns and Codex@rust-v0.160.0 [event status:159](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L159). Synthetic reader/hash stdout+exit42, malformed denial values, background/incomplete/native-error cases are local controls; no AF_UNIX or inheritance relaxation.
- AgentsView@v0.43.0 pin9be7745a: [configuration:326–337](https://github.com/kenn-io/agentsview/blob/9be7745a/docs/configuration.md#L326) documents idle exit and native restart. README.md:77–90/cmd/agentsview/daemon.go:589 govern sync/status behavior. Run sync before status, then retain both session and usage gates. Native service_health0 is host integration; synthetic stopped/unresponsive/missing-data negatives are separate.
- D05 has no upstream equivalent: preserve and repair seathatflowsinourveins/native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:tools/adoption/new_wsl_client_config.py:2309–2318,2380–2408. Existing create-only profiles report differs, not written; parse authorization keys exactly as the established merger does. Formatting and unrelated model drift leave equal authorization values same, differing values stay kept, absent values are not reached, malformed TOML/UTF-8 fails before creation. Native byte preservation and create-only/dry behavior remain intact. No active client configuration is written.

## Documented provider ID and alias in returned metadata (2026-10-05)

- OmniRoute@v3.8.51 pin c1e30b7676975feb298b49eff6ff58923c04b89e [codex registry:9–13](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/config/providers/registry/codex/index.ts#L9) declares ID codex, alias cx and executor codex; [model parser:484–490](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/model.ts#L484) resolves either spelling while retaining the suffix. Accept only those two namespaces for the two existing exact models; reject suffix mismatch or a different supplied provider. Existing completion, session/window join and endpoint gates remain.
- [Request setup:48–50](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore/requestSetup.ts#L48) takes requestedModel from current body.model; [attempt logging:565–573](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore/attemptLogging.ts#L565) and [callLogs:613–619](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/lib/usage/callLogs.ts#L613) carry it separately from model/provider. This proves alias equivalence, not where a spelling changed or wire effort. No gateway composition or canonical route is changed.
- The direct GPT Researcher report completed, but the whole post-rebase stage returned1 at this metadata gate before DeerFlow/fresh clients. A bounded exact-session metadata diagnostic found four successful codex calls with the two allowed models. Candidate metadata replay0 and synthetic namespace/provider/suffix/status/endpoint negatives are local integration. The sole plan writer must apply the updated observer before another authorized whole native stage; original failure is retained.

## Post-rebase serial native observations

At frozen source b3969b21a1079f7bb441f003123acb1d07a9e29c, the existing native accept.sh stages passed for Difftastic, Worktrunk, SRT (both clients), Inspector (both clients), Inspect AI and the worker. The unchanged Inspector probe matches 2f82b600dcebf957cfbec84bd85ba64b5abbafde20283392b03ff5dfa150f811. Inspect's upstream relative example completed one sample; the absent-model CLI returned0 but its native error log failed the positive predicate1. Worker negatives made zero requests and both positive jobs produced55; the unchanged focused subprocess test's stdout is suppressed by check(), so no new detailed upstream test-count claim is made. Production AF_UNIX policy stays unchanged.

Betterleaks first ran the old installed helper0; that result does not qualify candidate output retention. The subsequent existing XDG_CONFIG_HOME binding selected an exact candidate helper copy in an ignored private tool root, and the same native stage returned0 with unchanged upstream make test output retained. Go result lines include nested subtests; they are not independently enumerated tests. Shared helper and gitleaks/P1 gates are unchanged. Sources remain the pinned upstream commands cited above.

The followup receipt's post713_serial_native_stage_followup binds the then-current command/helper hashes to sanitized outcomes and private raw-artifact digests. At that receipt's earlier head, Inspector post_install and AgentsView v0.43.0 post_install hashes matched their prior passed execution; those were historical reuse, not new runs. The operational v0.44.0 version/launcher gate now has different inputs and does not inherit that v0.43.0 acceptance. Full local316-test success and native host acceptance remain separate. Actual cross/research whole-stage failures, successful local replays and the owner's next retry/apply boundary remain distinct. No shared host plan apply was performed by this lane.

## Exact legacy Grafana path custody (A30, 2026-10-05)

Grafana@v13.2.3 pin6193dc03311b631b9727b560d24369e683dc396e provisions each datasource YAML ([reader:27–34](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/pkg/services/provisioning/datasources/config_reader.go#L27)) and dashboard provider YAML; its [file reader:181](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/pkg/services/provisioning/dashboards/file_reader.go#L181) recursively scans configured dashboard folders. The [native provisioning reference:90,339,371](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/docs/sources/administration/provisioning/index.md#L90) shows why parallel legacy names are not accepted by checking only the new names.

The user-queued co-op A30 report establishes backup custody and absent live paths; its three reported hashes in the followup receipt are provenance only. Add the exact-path metadata preflight at the existing publisher/checker seam, seathatflowsinourveins/native-agent-stack@86268eb193700714fe4b6df5eb956f485b91bbe6:evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py:98,115–141,227–247. CPython@v3.13.16 [lstat:432–437](https://github.com/python/cpython/blob/v3.13.16/Lib/pathlib/_abc.py#L432) inspects the symlink rather than its target. Catch only FileNotFoundError as absent; successful lstat and other inspection errors require the owner. No automatic migration/retirement or digest-based exception is provided.

All three stage recipes call the current plan checker first, avoiding a stale installed helper, then preserve native prompts/workloads/API oracles. Synthetic42presence controls, metadata denial, unrelated-path positive and three caller controls preserve bytes/metadata and forbid subsequent work. The native Grafana post_install/service_health/after_sign_in stages each returned0; the new actual sanitized SDK receipt is hashed separately. Native stdout suppression limits detailed stream/usage claims. Publisher/checker preservation starts at their entry; the installer transports the helper beforehand. No install.sh, host configuration apply or backup retirement occurred in this lane.

## D-ollama-2: native on-demand loading (2026-10-05)

The user's decision at about11:05 AM EDT (15:05Z), described by the queued co-op direction, replaces indefinite boot preload with native30m idle expiry. Reported zero organic calls, about19GiB pinned VRAM and scarce Windows VRAM are decision inputs, not remeasured here. The explicitly authorized noncredential host unit read matched SHA2565e8e8bc42306f2d1ebc6da912e34daa28c6ce73eccf793d3155851733dccc6db/1369bytes. Its header's approximate15:08Z remains byte-identical. Old94e03d7b/2236dc86 bytes remain historical; no host file was applied or removed.

- Installed Ollama0.35.0 serve --help returns built-in KEEP_ALIVE default5m. [envconfig/config.go:126–143](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/envconfig/config.go#L126) implements duration overrides and infinite negative values. The user selects30m, with organic-use/reload-cost comparison as the overturn condition.
- [docs/api.md:1659–1704](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1659) defines native embeddings. [server/routes.go:1143–1145](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L1143) echoes the request model; [server/sched.go:517–519](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/sched.go#L517) uses environment keep-alive unless overridden. This request sends no keep_alive override.
- [docs/api.md:1736–1771](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/api.md#L1736) defines /api/ps size/VRAM fields. [server/routes.go:2422–2440](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/server/routes.go#L2422) and [types/model/name.go:230–247](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/types/model/name.go#L230) produce canonical names including :latest. [cmd/cmd.go:1217–1220](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/cmd/cmd.go#L1217) classifies positive size_vram==size as100%GPU. Require exactly one matching model with positive numeric size, rejecting CPU/partial/null/zero/string/duplicate controls.
- [docs/linux.mdx:57–89](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/linux.mdx#L57) supplies the user adaptation's unit form. Existing copy_config custody and native enabled/active queries remain. Only the co-op applies the shared-host plan.

The321touched tests, two focused methods and all3native local-model-server stages returned0. These are LOCAL INTEGRATION controls, not unchanged upstream tests or full host acceptance. Service health made one embed then ps; separate unchanged after_sign_in made its own embed. Independent GET observed size=size_vram=2857191341. No cold-start, timed unload, throughput, future-residency or organic-use claim follows. Source/recipe/log digests and retained failures are in the followup receipt.

## Gate-1 and conformance lifecycle corrections (2026-10-06)

The [dated decision](../../../docs/decisions/2026-10-06-native-plan-gate1-repairs.md) links the exact source for every repair and names the alternatives, limits and overturn comparisons.

- hcom 0.7.27: aannoo/hcom@2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b:src/commands/start.rs:840 repeats the marker; tests/support/mod.rs:949 selects its first line; src/identity.rs:14 supplies the base-name grammar.
- Independent environments follow astral-sh/uv@70fe1196a546e49148a73b1c592b2f74c33af80e:docs/concepts/tools.md:38,177. Inspect's OpenAI3 requirements conflict with the pinned Harbor/LiteLLM OpenAI2 range. The three verified published wheel installs use --no-build. Scout's historical owner identity remains; its interpreter and alias resolve separately. Required Harbor Trajectory import prevents ATIF importorskip from hiding missing coverage. Sources: UKGovernmentBEIS/inspect_ai@9e44f1b77ed7c912bf58baf30db8560937e7ce53:requirements.txt:12; meridianlabs-ai/inspect_scout@0e8fc055a3cebba1a14c11bc35856767b6405173:pyproject.toml:24; laude-institute/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:pyproject.toml:20; BerriAI/litellm@b3086ccd74553565c9a39716e72303ae985555f9:pyproject.toml:19.
- SkillSpector model forwarding follows [the resolver:90](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/providers/_agent_cli_base.py#L90) and [native Codex argv:319](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/providers/_agent_cli.py#L319). It ignores user config; no gateway-profile or effort qualification follows from the model carrier.
- The cx/gpt-6.1-sol-max suffix choice follows [landed #744:36](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0fb32ee583589f1a0809b20d18dff40ce2f65a1c/docs/decisions/2026-10-05-omniroute-gateway-composition.md#L36). DeerFlow's supports_reasoning_effort=false and omitted reasoning_effort are this plan's configuration choices through [DeerFlow v2.1.0's explicit false configuration](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L225); #744 does not mention DeerFlow. Keyless DDG stays; metadata does not prove delivered effort.
- MCP conformance@c321dd32035556e6769d3724a8ee97d87c3faaac:package.json:13 supplies the release executable; npm/cli@bfacd33ccbcd908480610703b60455d2da5b57a9:workspaces/libnpmexec/lib/index.js:49 explains same-package local resolution. Resolve exact release npx from neutral plan_dir, disable scripts and keep unchanged npm ci/check/test with no runtime source build.
- All six TypeScript examples expose PORT only. Three bind 127.0.0.1; everything-server.ts:2465, sep-2549-no-caching-hints.ts:99 and sep-2322-mrtr-broken-server.ts:168 omit host. Full-suite test mocks also omit host. Preserve upstream files and contain full tests/release CLI with private network loopback. Native util-linux@5305e6c70b274f679329b79c0e1ef5a07e9dc1a6:sys-utils/unshare.1.adoc:81,118 and sys-utils/setsid.1.adoc:21 supply user/PID/network namespace and owned session cleanup. The SDK's src/sdk-runner/index.ts:102 supplies bounded TERM/KILL. Node@v24.21.0:doc/api/net.md:46 explains the short Linux Unix-IPC path requirement.

The initial uncontained 524-test pass leaked 18 processes and three wildcard listeners, so its lifecycle failed. The first contained run failed on a 161-byte IPC path. The corrected native plan post-install passes 44 upstream files/524 unchanged tests, with helper-derived zero owned namespace/group processes and run listeners. The cleanup observation is LOCAL INTEGRATION; it is not an independent observer receipt. These upstream results are distinct from LOCAL INTEGRATION environment/alias/namespace fixtures and from full host/provider acceptance. All attempts remain. External on-demand after targets are unqualified; missing target 78 is needs_user, never protocol acceptance. A45 requires an owner-supplied in-namespace native SDK startup command or fixture; no host-network fallback or outside bridge.

SkillSpector native follow-up: [report.py:1334](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1334) emits issues. [meta_analyzer.py:616](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/meta_analyzer.py#L616) skips zero findings; [report.py:1173](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1173) says this is not failure. [native counters:1124,1240](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1124) distinguish actual successful semantic calls from static-only or degraded output. The actual whole stage exits0 after the canonical plan-path, native-field and safe-completion fixes; all three intermediate native1 attempts remain.

- Required P2-6 owner-custody alternative: [native-agent-stack@84c79f7f:install.sh:82-126](https://github.com/seathatflowsinourveins/native-agent-stack/blob/84c79f7f92f61972a46aa470a4f299017bc82768/evidence/artifacts/new-wsl-install-plan-20261002/install.sh#L82) supplies regular-example retention. [systemd/systemd@v259:man/systemctl.xml:1317-1327](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L1317) and [restart:421-433](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L421) supply native reload and restart. The [dated owner-custody runbook](../../../docs/decisions/2026-10-06-native-plan-gate1-repairs.md#after-landing-gateway-custody-on-nativestack2604) keeps actual prior bytes and prefix without fabricating a historical known digest. Its filesystem fixtures and host recipe are UNRUN; these source contracts are not new host/provider acceptance.

## B2 AgentsView v0.44.0 source preparation (2026-10-06)

- Official [kenn-io/agentsview v0.44.0 release](https://github.com/kenn-io/agentsview/releases/tag/v0.44.0),
  published 2026-09-21T13:56:12Z, stable/non-draft. Native gh api --cache 120s
  metadata peels tag 24ac704b3468386dbddc333853f81bc1cdb3a1b9 to commit
  413a87f7bfbd67b2815b1119ac51abc1efbeeaba.
- Published [Linux amd64 archive](https://github.com/kenn-io/agentsview/releases/download/v0.44.0/agentsview_0.44.0_linux_amd64.tar.gz)
  SHA256: 037ea7a46d52e06b20363b4aa7cd7f28e32f31d8215803d6e9a0c96bac5818e3.
  SHA256SUMS, signature, provenance and SPDX are separate release assets;
  publication metadata is distinct from an actual download/hash observation.
- At kenn-io/agentsview@413a87f7bfbd67b2815b1119ac51abc1efbeeaba,
  [scripts/install.sh:142](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/scripts/install.sh#L142)
  verifies checksum before extraction/placement at 151-160. Standard directories
  are selected at 35-41 and latest at 121; no version/private-prefix selector
  exists. The plan retains owned placement glue and the explicit release archive.
- The same pin's [internal/config/config.go:2051](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/internal/config/config.go#L2051),
  2136 and 2139 support data directory, disabled updates and archive-content
  policy. [cmd/agentsview/cli.go:831](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/cmd/agentsview/cli.go#L831)
  supplies native version output; session_get.go:21 retains the existing interface.
- Counter sources at that pin:
  [internal/db/usage.go:1802](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/internal/db/usage.go#L1802)
  and 1879 define daily token/cache/cost totals.
  [internal/service/direct.go:377](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/internal/service/direct.go#L377)
  and service.go:440 flatten named-session recorded calls and define count/name/category.
  internal/parser/codex.go:627 preserves native names; taxonomy.go:172 maps generic
  exec to Bash and 318-325 maps unmatched names to Other. These are not a
  dedicated code-mode/savings counter. cmd/agentsview/session_usage.go:37-50
  distinguishes descendant-inclusive usage, --own-only and archived --no-sync.
- Tagged docs/changelog.md:6 still labels 0.43.0 latest/Unreleased; published
  v0.44.0 release notes govern. Earlier G5 v0.43.0 records remain historical.
  Local migration fixtures are integration evidence; native host observations,
  whole-host acceptance and measured code-mode improvement remain separate.

This #723 source integration reuses the prior B2 metadata and preserves its failed attempts and code-mode attribution gap at native-stack@946158c163d6cb17ee1c0e3c653f7b869262215b:evidence/artifacts/agentsview-044-b2-20261006/receipt.json. It runs no new CLI probe or whole acceptance. Shared stack/profile pin alignment remains the separate monitoring pin PR #807; this change updates only the operational install-plan artifact and keeps the historical G5 owner identity.

### J723 exact-head review delta (2026-10-06)

- Promptfoo's native config still follows promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8:examples/openai-compatible-gateway/promptfooconfig.yaml:1-24. Endpoint validation uses Node's supported [WHATWG URL hostname](https://nodejs.org/api/url.html#urlhostname) and [port](https://nodejs.org/api/url.html#urlport) properties, compared exactly with the plan-owned `127.0.0.1:21128`. Raw topology ownership is checked before requiring the CommonJS config; the explicitly pending Claude route returns needs_owner/78, while malformed supplied routes remain failures.
- Gateway freshness uses systemd/systemd@v259:[systemctl-show.c:1120](https://github.com/systemd/systemd/blob/v259/src/systemctl/systemctl-show.c#L1120), [systemctl.xml:2486](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L2486) and [org.freedesktop.systemd1.xml:2418](https://github.com/systemd/systemd/blob/v259/man/org.freedesktop.systemd1.xml#L2418). `--timestamp=us+utc` preserves the activation's microseconds; the keyed activation value must be strictly later than both installed file mtimes. Installed `date` and `stat` both report uutils coreutils0.10.0. Its [date.rs:596](https://github.com/uutils/coreutils/blob/0.10.0/src/uu/date/src/date.rs#L596) documents the date-input option, date.rs:300-318,537,884-892 preserves custom nanosecond formats, and [stat.rs:1117](https://github.com/uutils/coreutils/blob/0.10.0/src/uu/stat/src/stat.rs#L1117),1350-1362 supplies nanosecond modification times. GNU's manual describes the compatible format semantics, not the installed implementation. This adds a configuration-freshness gate; destination process loading and provider wire effort remain unqualified.
- Research checkouts enforce the official tag targets: [GPT Researcher v3.7.0 at 0957c301ed06c2a5857b834358c7227c739041d4](https://github.com/assafelovic/gpt-researcher/tree/0957c301ed06c2a5857b834358c7227c739041d4) and [DeerFlow v2.1.0 at 345f08be00c8a9495079b732a39b46aa9af1584e](https://github.com/bytedance/deer-flow/tree/345f08be00c8a9495079b732a39b46aa9af1584e). Each assertion shares its existing checkout command, preserving failure propagation and command counts.
- The handbook's maintained current-output contract is native-stack@4e07a17d55860d3ae15c7437a348d59ff2fc40a1:docs/decisions/2026-10-01-new-wsl-handbook-generator.md:665 and tests/test_new_wsl_handbook.py:1672-1689. The generator-owned receipt retains the previous pair while binding its current outputs exactly; all prior validation observations remain unchanged.

J723c extends the existing test contracts, using CPython3.13's [Path.rglob](https://docs.python.org/3.13/library/pathlib.html#pathlib.Path.rglob) and [Path.is_file](https://docs.python.org/3.13/library/pathlib.html#pathlib.Path.is_file), matching this repository's check_plan.py recursive config reader at native-stack@4e07a17d55860d3ae15c7437a348d59ff2fc40a1:649. Nested drop-in contents remain part of port checks, and the exact root script set explicitly includes the frozen Inspector probe. The AgentsView current repin classification follows tests/test_agentsview_qualification.py:50-76,292-347; the older launcher fixtures remain dated predecessor inputs, not current pins. Native Git/Python/env commands no longer require RTK in CI or at runtime; optional parsing of earlier RTK-shaped client events remains supported. The already-landed currency update supplies the native git-grep registry recipe. Historical RTK observations and component-specific tests are retained.

## Retrieval-first plan parity (2026-10-07)

The seven plan/manifest incompatibilities are recorded in grand-catalog's unchanged-copy check of 2026-10-06: one embedding identity mismatch and three identity/install-state mismatches for each retired Ollama row. The selection source is native-agent-stack@db930144:docs/decisions/2026-10-06-retrieval-first-local-models.md:27-33,58-61,115-118, implementing the command center's final local-model ruling. This changes the executable plan and its necessary mirrors; it does not change the settlement, historical verdicts or observed results.

The kept embedding provider is the existing Nemotron 8B endpoint. [NVIDIA's model card at d1f2f257](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16/blob/d1f2f25730bbd775b99b29185134bc86653bf2d1/README.md) specifies full 4096-dimensional, L2-normalized embeddings and the exact `query: ` and `passage: ` prefixes, and demonstrates serving the named model through vLLM. [vLLM v0.31.0's native HTTP API](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/docs/serving/online_serving/openai_compatible_server.md) supports `/v1/embeddings`. The model card's installation example uses vLLM 0.25.0; it is not evidence that 0.31.0 was installed or accepted. The CURRENT 0.31 provider and loopback 28231 are owner-kept state from the ruling, checked through their native HTTP surface. Missing or mismatched state is nonzero needs_owner; this row adds no server, environment, model download, rebuild or fresh-host bootstrap.

Local generation and its Ollama server are explicitly excluded. The prior owner-approved unit remains byte-identical historical data (native-agent-stack@979291de:evidence/artifacts/new-wsl-install-plan-20261002/config/ollama.service:1, SHA256 5e8e8bc4…), alongside its existing environment example; neither is installed. The checker rejects installation prerequisites, operational commands, services, config placement and implicit mise Ollama installation for the retired rows. QMD 2.8.3 keeps its native lexical role under the selected named index with `QMD_FORCE_CPU=1` and inherited `INDEX_PATH` removed; its compulsory 0.6B GGUF/vector prerequisite is retired, without downloading or selecting a replacement embedding model. Native package/SDK execution is distinct from our synthetic API/retirement controls. These source changes and fixtures qualify plan integration only; the command center owns the host apply and smoke.
