# Round 1 install-plan repair

The coordinator ran 34 slots as uid 1000 in a disposable `ubuntu:26.04` container (Ubuntu 26.04.1 LTS), with passwordless sudo, no systemd/user bus, no bubblewrap user namespaces, no service started by the validation procedure and no sign-in. The repository was read-only at `/repo`; the mounted worktree's Git metadata was outside the container. This file quotes only nonprivate evidence. Log locations below are relative to the supplied read-only `round1/` results directory.

Results: 16 passed both checks; 18 failed. Cause counts among failing slots: **5 plan defects, 5 checks needing a running service, 4 checks needing sign-in/provider configuration, 4 container limits**. Mise, chezmoi and Codex acceptance logs retain only exit 1 because the old runner suppressed stdout. Their assignments use the recorded fresh-host conditions plus the pinned upstream implementations; the exact diagnostic rows are unknown. These are source-supported explanations, not reconstructed output or a claim of successful retesting.

In the result column, `I/A` means aggregate install/accept exit codes from `results.tsv`. A command's own status can differ: Git reports 78 inside an aggregate install exit 1; curl health commands report 7 inside acceptance exit 1; Harbor reports successful owner installation before the Docker dependency fails. Each quoted log location names the actual line carrying evidence. Sources for changes and retained checks are in [SOURCES.md](SOURCES.md#round-1-repairs-and-staged-acceptance) and each JSON check's `source`.

| slot | round 1 result | cause class | what changed |
| --- | --- | --- | --- |
| mise | I/A 0/1; `mise.accept.log:1`: `mise \| smoke \| 1`; install log:83 recommends doctor | plan defect | Keep full doctor with mise shims on this process's PATH, in the owned global tool directory so the optional inventory manifest is not selected. The original runner used `mise env`, which does not supply activation or the required shims. Exact original doctor failure row was suppressed. Pins stay unchanged. |
| git | I/A 1/skipped; `git.install.log:1` says no suitable route; :2 reports install 78. `mise.install.log:11`: Git is already Ubuntu's `1:2.53.0-1ubuntu1` package | plan defect | Declare `apt` and idempotently install Ubuntu's own Git package. Remove the exit-78 refusal and add `git --version`. Do not claim the upstream v2.56.0 pin was installed. |
| claude-code | I/A 0/0 | passed | Retain the documented local doctor as post-install. |
| codex | I/A 0/1; `codex.accept.log:1`: `codex \| smoke \| 1`; install log:27 records 0.160.0 | check needs a sign-in or a provider | Use version at post-install; retain full doctor after sign-in. Pinned doctor marks missing credentials FAIL. Doctor is a valid command; the exact original failing rows are unknown. |
| gh-github-cli | I/A 0/0 | passed | Retain version at post-install. |
| betterleaks | I/A 0/0 | passed | Retain the directory scan at post-install. |
| zizmor | I/A 0/0 | passed | Retain the documented local check at post-install. |
| syft | I/A 0/0 | passed | Retain the upstream image smoke at post-install. It uses network access but no sign-in. |
| actionlint-kjanat | I/A 0/0 | passed | Retain version at post-install. |
| worktrunk | I/A 0/1; `worktrunk.accept.log:1`: `git rev-parse --git-common-dir failed (exit 128)`; :2 says the Git directory is not a repository | container limit | Retain `wt list` in the real checkout as post-install. The read-only worktree mount omitted its Git metadata; do not replace this smoke with a version check. |
| difftastic | I/A 0/0 | passed | Retain version at post-install. |
| restic | I/A 0/0 | passed | Retain version at post-install. |
| chezmoi | I/A 0/1; `chezmoi.accept.log:1`: `chezmoi \| smoke \| 1`; install log:41 records package 2.73.0 | plan defect | Retain the full doctor, using its documented config/source/destination/working-tree flags and fresh owned directories. Upstream makes nonexistent directories an error. Keep all diagnostics, including network/version checks. Exact original row was suppressed. |
| mcporter | I/A 0/0 | passed | Retain local MCP inventory at post-install. |
| sandbox-runtime-srt | I/A 0/1; `sandbox-runtime-srt.accept.log:1`: `bwrap: No permissions to create a new namespace` | container limit | Retain the actual `srt echo` smoke at post-install. No namespace bypass or unsandboxed replacement. |
| tobi-qmd | I/A 0/0 | passed | Retain status at post-install. |
| playwright-cli | I/A 0/1; `playwright-cli.accept.log:6`: `Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome`; install log:658 confirms bundled Chromium build 1247 | plan defect | Install Chromium through the pinned CLI's own `install-browser --with-deps chromium`; explicitly pass `--browser=chromium` to the real open/close smoke. The previous Playwright dependency version was correct. |
| ccusage | I/A 0/0 | passed | Retain daily usage smoke at post-install. |
| promptfoo | I/A 0/0 | passed | Retain version at post-install. |
| gpt-gateway | I/A 0/1; `gpt-gateway.accept.log:2`: `error: unknown option '--json'`; :9 advertises `--no-liveness` | plan defect | Replace the incorrect subcommand flag with global `--output json`. Use upstream doctor `--no-liveness` at post-install. Service-health requires upstream `/readyz` success before full doctor, which otherwise only warns about an unreachable service. |
| serena | I/A 0/0 | passed | Retain upstream init in its owned acceptance directory at post-install. |
| trafilatura | I/A 0/0 | passed | Retain upstream URL extraction at post-install. It uses network access but no sign-in. |
| inspect-ai | I/A 0/0 | passed | Retain version at post-install. |
| harbor-containerized-agent-e2e-runner | I/A 1/skipped; `harbor-containerized-agent-e2e-runner.install.log:342–343`: three executables installed and owner install 0; :497–505 requests missing `nf_tables`/`modprobe`; :508–509 reports Docker failure and refusal | container limit | Keep the Harbor pin/uv route and its version check. Preserve the real rootless Docker prerequisite gate; this was a later dependency failure, not a Harbor resolver failure. |
| claude-agent-sdk | I/A 0/1; `claude-agent-sdk.accept.log:44`: `Not logged in · Please run /login` | check needs a sign-in or a provider | Report the SDK's public version at post-install; retain the original query after native/provider sign-in. |
| codex-sdk-and-codex-exec-app-server | I/A 0/1; `codex-sdk-and-codex-exec-app-server.accept.log:5`: `401 Unauthorized: Missing bearer or basic authentication in header` | check needs a sign-in or a provider | Check the installed local npm package version at post-install; retain the original SDK model call after authentication. |
| agent-runtime-worker | I/A 0/1; `agent-runtime-worker.accept.log:54`: `401 Unauthorized`; :95 records `invalid_api_key` | check needs a sign-in or a provider | Report both OpenHands package versions at post-install; retain the original hello-world agent example after provider configuration. |
| otel-collector-contrib | I/A 0/1; `otel-collector-contrib.accept.log:1`: curl could not connect on 21333; :2 reports health 7 | check needs a running service | Use upstream `validate --config` at post-install; retain the original health endpoint in service-health. |
| prometheus | I/A 0/1; `prometheus.accept.log:1`: curl could not connect on 21090; :2 reports health 7 | check needs a running service | Use the extracted upstream `promtool check config` at post-install; retain `/-/ready` in service-health. |
| loki | I/A 0/1; `loki.accept.log:1`: curl could not connect on 21300; :2 reports health 7 | check needs a running service | Use upstream `-verify-config=true` at post-install; retain `/ready` in service-health. |
| grafana | I/A 0/1; `grafana.accept.log:1`: curl could not connect on 21301; :2 reports health 7 | check needs a running service | Use documented `grafana cli -v` at post-install; retain `/api/health` in service-health. |
| dagu | I/A 1/skipped; `dagu.install.log:35`: `Failed to connect to user scope bus via local transport` because its session/runtime variables were not defined | container limit | Retain the upstream user-service installer. Add native `dagu version` at post-install; keep health after the real user service starts. No switch to another service scope. |
| local-model-server | I/A 0/1; `local-model-server.accept.log:1`: `could not connect to ollama server, run 'ollama serve' to start it` | check needs a running service | Use client version at post-install, model inventory in service-health and the original model smoke after provisioning its local model route. The model smoke remains unverified after connection. |
| mineru | I/A 0/0 | passed | Retain upstream local CLI check at post-install. |

The container cannot establish these conditions; check them on the real distribution:

- Systemd user sessions, Dagu startup and rootless Docker's kernel/network/user-unit prerequisites, restart and persistence.
- Bubblewrap namespace/permission support and the real sandbox smoke; browser smoke after selecting the installed Chromium.
- Worktrunk against a checkout with accessible Git/worktree metadata.
- Running service readiness at the recorded loopback endpoints, including Docker runtime smoke and Compose image/app readiness.
- Native sign-ins, configured model/search providers, local model provisioning, inference and WSL GPU passthrough.

Unresolved evidence limits: the suppressed original mise/chezmoi/Codex diagnostic rows cannot be recovered from these logs. Five workflow/adoption rows have no source-backed host executable check, so their explicit unavailable entries are skipped. Neither a skip, source review, configuration validation nor a version proves provider/GPU/service acceptance. All revised target-distribution commands remain unrun; no upstream failure was waived.

Executed checks for this revision: the requested Python JSON load, `bash -n` on both scripts and `bash install.sh --list` all returned 0. The list retained all 53 rows. TOML parsing, stage/schema/source agreement, all 156 slot/stage combinations, default/all-owner stages, unavailable/excluded skips, nonzero failure propagation and invalid arguments passed local fixtures. Additional Bash fixtures caught the original caller-directory and doctor-only false-pass patterns and verified the repairs. All 16 passing acceptance objects, original model/research examples, original HTTP endpoints and all seven exclusions were compared with the original plan and retained. The entire plan folder passed a personal-path/user-name scan; `git diff --check` passed. The fixtures ran no native owner programs, stack services or models. Independent Astra/Max source review confirmed the two review fixes and reported no remaining follow-up findings.
