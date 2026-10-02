# Install-plan validation

## Revision to the merged manifest, after the real-distribution run

### Evidence class

The result below is one run on one host: a throwaway Ubuntu 26.04.1 distribution on WSL 3.0.1, on 2026-10-02, executing this plan as it stood before this revision (branch `foundation/new-wsl-install-plan-20261002`, commit `bf5a08e2`). The coordinator recorded it in a findings note kept outside the repository. It is a historical host execution of the previous revision. It says nothing about the commands this revision changed or added, which have not run on a distribution. The round 1 container run below is a separate, earlier class of evidence.

### Result of that run

- Install: 42 owners exit 0; `codex` 143 (finding 1); `trail-of-bits-security-skills-trailofbits-skills` 1 (finding 2).
- `post_install` acceptance: 39 exit 0, 12 skipped (excluded or no host install), worktrunk 1 and convergence-validators 2 (finding 3). After the three repairs, applied by hand on that host: 41 of 41.
- The four owners the container could not show (Dagu, Harbor, sandbox-runtime, worktrunk) pass on the real distribution.
- `service_health`: container-engine, Dagu (port 21080) and Phoenix (21606, 21617) pass because the install starts them. The gateway, Grafana, Loki, the OTel collector, Prometheus and the research harnesses return curl's 28 and the local model server 1, because the install does not start their services.
- The 21xxx port band does not collide with the host's listeners in the shared network namespace.

### Findings and what changed

1. The `codex` slot hung for ten minutes: the native installer asks "Start Codex now? [y/N]" on /dev/tty when a terminal exists, and a WSL launch has a pty (the container run had none). The installer documents `CODEX_NON_INTERACTIVE` ("Set to 1, true, or yes to skip prompts"). **Changed:** the line is now `curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh`. On the host, with the variable set, no prompt appeared and the installer exited 0 (Codex 0.160.0), which is finding 4.
2. `claude plugin marketplace add trailofbits/skills@<commit>` failed twice over: the shorthand clones over SSH ("No ED25519 host key is known for github.com"), and `@<ref>`, like `#<ref>`, is a branch or tag, not a commit ("Remote branch <sha> not found"); the repository has no tags. `claude plugin marketplace add https://github.com/trailofbits/skills.git` works. **Changed:** that line, unpinned. The acceptance prints `git -C "$HOME/.claude/plugins/marketplaces/trailofbits" rev-parse HEAD` beside the reviewed commit `82fe8226252622fa807643bdca1710901198553a` and fails when they differ (the head was `82fe8226` on the day of the run). The Codex line, `codex plugin marketplace add trailofbits/skills --ref <commit>`, worked as written and is unchanged.
3. The acceptance checks of worktrunk and the convergence validators change into `repo_root`; from a copy outside a checkout they failed, and from the clone both exit 0. **Changed:** the README says first that the plan runs from a checkout (recipe step F7), and both scripts stop with a clear message when `repo_root` is not a git checkout (`install.sh --list` needs none).

### Rows

The inventory is the merged manifest's 64 foundation rows (the previous revision had 53 owner rows, 46 of them selected): 36 installed by default, three measurement-only (Loki, Grafana, Playwright CLI) and 25 not installed. Trafilatura, ccusage, Phoenix, Promptfoo, chezmoi, Claude Code Action, CodeQL SARIF, trufflehog, the LSP plugins, the structural-diff row, attest and Dependabot left the installed set; ast-grep, Alertmanager and mattpocock/skills joined it, and GPT Researcher and DeerFlow became one row. The round 1 table below keeps its rows for owners that left the plan: it records what that run did.

### Checks run for this revision

All static; none installs anything, and `install.sh` and `accept.sh` were not run except `install.sh --list`.

- `bash -n` on `install.sh` and on `accept.sh`: exit 0 each.
- `bash install.sh --list`: exit 0, 64 lines.
- `python3 -B check_plan.py`: exit 0, "OK: 64 rows: 36 installed by default, 3 measurement-only, 25 not installed; 65 commands and 55 acceptance entries agree with the scripts".
- Python `json.load` of the four JSON files of this folder: exit 0.
- `check_plan.py` against defects planted one at a time in scratch copies (our own mutations, not an upstream test): deleting the `serena` install function, adding an unknown mise tool and giving two rows one port each exit 1 and name the problem; so do an orphan function for an excluded row, a drifting install command, a dropped `--list` line, a split row marked installed, a `run_command` without a source comment, a missing post-install acceptance, a removed row, a stray config file, a command without a source URL, a `not_installed` row marked installed and a drifting acceptance command. The unmodified copy exits 0.
- `python3 -B scripts/validate.py`: exit 1; it reports only that the changed files differ from the hashes registered in `manifests/evidence.json`, that `check_plan.py` and `config/alertmanager.yaml` are not hash-listed and that `config/phoenix-compose.yaml` is gone, all to be re-registered by the coordinator.

Observations from upstream release archives run in a scratch directory (Alertmanager's `amtool check-config` on `config/alertmanager.yaml`, its readiness endpoint, the ast-grep probe) and fixtures for the skills and Trail of Bits acceptance programs are described in [SOURCES.md](SOURCES.md), last section; they are not acceptance.

## Clean run of this revision on a real distribution (2026-10-02T12:54Z to 13:17Z)

Record: [real-distribution-validation.json](real-distribution-validation.json), built by a script from the
coordinator's private raw outputs (counts, exit codes and the raw files' hashes only).

Evidence class: native execution on one host, in a throwaway Ubuntu 26.04.1 distribution on WSL 3.0.1.0 created by the
merged new-distribution recipe (main `3a8dc31a`), with the plan run from a clone of this branch inside it. No sign-in,
no provider call, no model run. The distribution was removed afterwards.

- Stage 1 and first boot of the recipe passed (P1 to P3, W1 to W5, W7, F1 to F5), with the two-distribution proof.
- Install at `b48321ea`: 35 owners exit 0, the three measurement-only owners skipped, none failed.
- Post-install acceptance at `b48321ea`: 34 exit 0, 29 skipped, one exit 1 (`engineering-process-skills`). The install
  was right and the check was wrong: the installer's lock file records no `ref`. Each of the six skills'
  `skillFolderHash` equals the git tree hash of its folder at tag `v1.2.3` and differs from main's, so the pin had been
  honoured. The acceptance now compares those hashes (`1b290218`), and the full acceptance at that commit returns 35
  exit 0 and 29 skipped.
- Service health: Docker and Dagu pass as installed; the OTel collector, Prometheus, Alertmanager and Ollama pass after
  being started with the commands in [SOURCES.md](SOURCES.md) on ports 21317, 21318, 21333, 21888, 21090, 21093 and
  21434. The gateway and the research harnesses were not started.
- The plan's port band did not collide with the workstation's listeners in the shared network namespace, and no 21xxx
  listener was left after the distribution was removed.

Not established by this run: a signed-in client, a pulled or running model, the GPU, the gateway and the research
harnesses as services, the three measurement-only owners, and a distribution that stays.

## Round 1 install-plan repair (historical)

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
