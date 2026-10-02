# Source research and review
Status: source-only, unrun. No installer, service start, benchmark, or model call was executed; no target-distribution install/acceptance was run. Existing-host read-only native help/version corroborated command syntax only.
North-star action served: a reproducible foundation installation plan for subsequent US-equities research and historical simulation. No trading readiness or live/paper operation is claimed.
Discovery was bounded to the supplied owners/pins, selected upstream READMEs/docs, mise registry entries, release assets/checksums, and the existing repository adoption recipes. search-first and context-mode were used; researchers were read-only.
The specialized stack-researcher role retained its defined Astra/Max model. Consequential source judgment trigger: native-versus-Compose host listener boundaries and SDK route/package classification. Acceptance result: coordinator accepted the pinned primary-source conclusions only; runtime acceptance remains unrun.
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
- Dagu native installer options/unit: [source, line 109](https://raw.githubusercontent.com/dagucloud/dagu/v2.18.1/scripts/installer.sh#L109).
- Dagu coordinator defaults: [source, line 2017](https://raw.githubusercontent.com/dagucloud/dagu/v2.18.1/internal/cmn/config/loader.go#L2017).
- Rootless Docker install: [source, line 75](https://raw.githubusercontent.com/docker/docs/2d7809c7a74ba1e99609a44f421a15cbf8a4a4bc/content/manuals/engine/security/rootless/_index.md#L75).
- Rootless Docker user unit: [source, line 15](https://raw.githubusercontent.com/docker/docs/a20e3585feaf72f0be0ca0177e3bbb523f372ff2/content/manuals/engine/security/rootless/tips.md#L15).
- Rootless dbus prerequisite: [source, line 219](https://raw.githubusercontent.com/docker/docs/0571430b6a9c6ff1742baede7c265c3c5e9e3322/content/manuals/engine/security/rootless/troubleshoot.md#L219).
- OmniRoute loopback and WS: [source, line 158](https://raw.githubusercontent.com/diegosouzapw/OmniRoute/v3.8.51/docs/reference/ENVIRONMENT.md#L158).
- OmniRoute detached daemon: [source, line 56](https://raw.githubusercontent.com/diegosouzapw/OmniRoute/v3.8.51/bin/cli/commands/serve.mjs#L56).
- Phoenix native bind limitation: [source, line 107](https://raw.githubusercontent.com/Arize-ai/phoenix/arize-phoenix-v20.19.0/src/phoenix/server/grpc_server.py#L107).
- DeerFlow production publication: [source, line 45](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose.yaml#L45).
- Claude native version check: [source, line 23](https://raw.githubusercontent.com/anthropics/claude-code/v2.1.287/README.md#L23).
- Codex native version/doctor flags: [source, line 116](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/cli/src/main.rs#L116).

## Binary quotation boundary
Transport/checksum/user-prefix placement is thin script glue around the selected upstream binary routes, adapted from the quoted OTel HTTPS transport recipe and published release checksums. No constructed download wrapper is represented as a verbatim owner installer. Versions, filenames, destinations, noninteractive extraction flags, and loopback endpoints are explicit parameters.
Prometheus has a prose download link plus a quoted tar command; that transport quotation gap is retained. Loki's release-note template supplies curl/unzip/chmod commands. Grafana's versioned official page supplies wget/tar commands and checksum.

### OTel Collector Contrib — source quotation, UNRUN
[source](https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/9f912d59a165ded5dec82d0e1a94c2aef54e5c57/content/en/docs/collector/install/binary/linux.md#L87)
```sh
curl --proto '=https' --tlsv1.2 -fOL https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v{{% param vers %}}/otelcol_{{% param vers %}}_linux_amd64.tar.gz
tar -xvf otelcol_{{% param vers %}}_linux_amd64.tar.gz
```
Published artifact: https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.162.0/otelcol-contrib_0.162.0_linux_amd64.tar.gz; SHA256 `fcc063749f730f8c21fe29f2d340ff174f5f1c5885bd3156fb6c985a3036fcc3`.

### Prometheus — source quotation, UNRUN
[source](https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/getting_started.md#L18)
```sh
tar xvfz prometheus-*.tar.gz
```
Published artifact: https://github.com/prometheus/prometheus/releases/download/v3.15.0/prometheus-3.15.0.linux-amd64.tar.gz; SHA256 `2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0`.

### Loki — source quotation, UNRUN
[source](https://raw.githubusercontent.com/grafana/loki/v3.7.8/tools/release-note.md#L24)
```sh
curl -O -L "https://github.com/grafana/loki/releases/download/${DRONE_TAG}/loki-linux-amd64.zip"
unzip "loki-linux-amd64.zip"
chmod a+x "loki-linux-amd64"
```
Published artifact: https://github.com/grafana/loki/releases/download/v3.7.8/loki-linux-amd64.zip; SHA256 `62aea42c9cba52cd1642b3666ab37019a0ce4c24ab50b07e85dccc8d812f7d61`.

### Grafana — source quotation, UNRUN
[source](https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux#L2819)
```sh
wget https://dl.grafana.com/grafana/release/13.2.3/grafana_13.2.3_36482603486_linux_amd64.tar.gz
tar -zxvf grafana_13.2.3_36482603486_linux_amd64.tar.gz
```
Published artifact: https://dl.grafana.com/grafana/release/13.2.3/grafana_13.2.3_36482603486_linux_amd64.tar.gz; SHA256 `6107ad27016296aac38e0d7ffa8753ab540b5541ad27e94790f771289d733235`.

## Service starts — separate from installation, all UNRUN
These invoke documented upstream foreground/daemon forms. No systemd user unit was created except those installed upstream by Docker and Dagu.
The shell variables below are the portable prefixes defined in install.sh/accept.sh; run foreground services in their own terminals. Configuration is installed from config/ without overwriting existing files.
- OTel: `otelcol-contrib --config "$config_root/otel.yaml"`. Only OTLP grpc21317/http21318, health21333, and metrics21888 bind loopback; optional pprof/zpages/Jaeger/Zipkin are omitted from the upstream distribution template.
- Prometheus: `prometheus --config.file="$config_root/prometheus.yaml" --web.listen-address=127.0.0.1:21090 --storage.tsdb.path="$tool_root/prometheus/data"`. [CLI flags](https://raw.githubusercontent.com/prometheus/prometheus/v3.15.0/docs/command-line/prometheus.md#L17).
- Loki: `cd "$tool_root/loki"`, then `loki -config.file="$config_root/loki.yaml"`. [Upstream foreground invocation](https://raw.githubusercontent.com/grafana/loki/v3.7.8/docs/sources/setup/install/local.md#L74). HTTP21300/grpc21396 bind loopback; persistent paths are relative to this owned directory.
- Grafana: change to the extracted Grafana directory, then `./bin/grafana server --config "$config_root/grafana.ini"`. [Upstream tar/foreground command](https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/setup-grafana/start-restart-grafana.md#L107), [custom config option](https://raw.githubusercontent.com/grafana/grafana/v13.2.3/docs/sources/setup-grafana/configure-grafana/_index.md#L39). HTTP21301 and optional gRPC21302 bind loopback; default system-wide service is not installed.
- Ollama: source the plan's ollama.env.example, then `ollama serve`. [Native Linux command](https://raw.githubusercontent.com/ollama/ollama/v0.35.0/docs/linux.mdx#L30). HTTP21434 binds loopback.
- OmniRoute: source the plan's omniroute.env.example, then `omniroute serve --port 21128 --no-open --daemon`. HTTP21128/WS21129 bind loopback. Provider configuration stays native.
- Phoenix: the documented Compose form publishes HTTP21606 and gRPC21617 only on loopback; native wildcard gRPC stays inside the container network. No optional metrics port is published.
- Dagu: upstream installer starts user dagu.service at HTTP21080, coordinator127.0.0.1:50055. start-all disables coordinator/scheduler auxiliary health listeners.
- DeerFlow: after configuring models[].base_url and OPENAI_API_KEY, `cd "$tool_root/deer-flow"` then `BIND_HOST=127.0.0.1 PORT=2026 make up`. [Upstream production start](https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/README.md#L330). Production Compose publishes only loopback2026; no systemd user unit is proposed.
Rootless Docker exposes a Unix socket, no host TCP port. All assigned host ports avoid the supplied collision set.
## Anti-pattern corrections and verification path
- Incorrect assumption: root registry.toml exists at mise v2026.10.0. gh contents API returned404; tagged tree and registry/<tool>.toml reads establish the split registry. No tag was substituted.
- Wrong-owner risk: short mise actionlint selects rhysd/actionlint. Tagged registry and kjanat/docs/install.md:208,223 establish the qualified github backend.
- Wrong package pin: GPT tag v3.7.0 is not a pip version3.7.0. Tagged pyproject.toml:23 declares0.16.0; tagged requirements/source installation was selected.
- Wrong action reference: Dependabot Core is a GitHub service/repository, not a root Action. Tagged tree lacks an entrypoint; tagged README:42 supplies the supported configuration form. CodeQL root action is a failing stub; upload-sarif/action.yml supplies the real subaction.
- Wrong host-bind claim: Phoenix PHOENIX_HOST changes HTTP, while tagged grpc_server.py:107 hardcodes [::]. Tagged Docker Compose recipe confines its listeners to container networking with explicit loopback host publications.
- Earlier Claude marketplace shell gap resolved: official CLI reference:634,647 plus pinned v2.1.287 CHANGELOG:50 and installed value-free help prove command/ref support. Re-registration is documented idempotent. No plugin installation was attempted.
- Codex unchanged marketplace source/ref is idempotent: [rust-v0.160.0 implementation](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/core-plugins/src/marketplace_add.rs#L114) returns already_added successfully. A different existing source/ref remains an explicit failure.
- Static script review corrected missing make/native-client selective dependencies, masked mise env failure, caller-dependent Worktrunk cwd, and grouped research early returns. Each independent research install is now attempted and failures remain nonzero; no generated script was executed to test this.
- Supplemental Grafana citation correction: the guessed start-restart-grafana/index.md path returned404; the tagged tree and raw read establish start-restart-grafana.md. The install source itself returned200 on its first required fetch.
## Completeness critic
Reviewed omitted modalities/classes: native self-updating clients, SDK libraries, CLI tools, marketplaces, workflow-only owners, rootless containers, services/auxiliary listeners, repository practices, and excluded overlaps.
Remaining limits: route enum has no precise library/marketplace labels; individual security plugins are unselected; Dependabot has no uses reference; host acceptance is unavailable for workflow-only/guard/Git rows; most services ship no documented user unit; Prometheus has no quoted transport command; model/account setup, WSL GPU execution, browser binaries, rootless compatibility, apt package availability, and every acceptance command remain unrun.
DeerFlow's make doctor is documented but requires host pnpm/nginx/backend environment, inapplicable to the selected Compose install. Its shipped /health/ready probe is used instead; no alternative runtime manager or passed container check is claimed.
No benchmark, convergence/SOTA superiority, billing saving, new model run, or E2E acceptance is claimed. This record feeds the next foundation lifecycle/source sweep.
