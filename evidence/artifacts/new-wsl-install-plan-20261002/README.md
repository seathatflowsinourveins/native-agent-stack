# New WSL install plan

**Run the plan from a checkout of the repository** (step F7, "Clone origin/main", of `adoption/platforms/linux-wsl2-new-distro.md`). `worktrunk` and the convergence validators change into `repo_root`, the checkout three levels above this folder, so `install.sh` and `accept.sh` stop with a clear message when `repo_root` is not a git checkout (`install.sh --list` needs none).

Revised to the merged definitive manifest (`evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`) and to what the plan did on a real distribution. The inventory has one row per foundation row of that manifest: 64 rows, of which 36 are installed by the default run, three are measurement-only (installed only by `--only <slot>`, for the measurement that decides them) and 25 are not installed. [VALIDATION.md](VALIDATION.md) keeps three results apart: the round 1 container run of the first plan (historical), the run of the previous revision in a throwaway distribution, and the clean run of this revision in a fresh throwaway distribution on 2026-10-02 (12:54Z to 13:17Z), recorded in [real-distribution-validation.json](real-distribution-validation.json). Both distribution runs were on one host, in distributions that were removed afterwards. Nothing has run on the destination distribution, the one meant to stay: that remains UNRUN. `python3 -B check_plan.py` checks that `install-plan.json`, `owners.json`, both scripts, `mise.toml`, `config/` and the manifest agree.

The target remains a clean Ubuntu 26.04.1 WSL 2 distribution with systemd, one non-root user, passwordless sudo and existing RTX 4090 passthrough.

## Installation and acceptance

```sh
python3 -B check_plan.py
bash install.sh --list
bash install.sh --only <slot>
bash accept.sh --only <slot>
bash accept.sh --only <slot> --stage service_health
bash accept.sh --only <slot> --stage after_sign_in
```

Both scripts refuse root. Installation selects dependencies, isolates owner failures and retains existing operator configuration. No default-shell or Windows-side change is prescribed. `--list` is read-only and prints `slot | owner | route | status` for every row; the status is `planned`, `measurement-only` or `excluded`.

A row is installed by the default run only when the manifest row says it installs something, its outcome is not `not_installed` and its state is not `split`. Two rows the manifest marks as installing are not: MCP Inspector (run on demand with `npx`; mcporter owns MCP calls from scripts) and the base distribution (the image the plan runs on).

- 36 rows are installed by default.
- Loki, Grafana and Playwright CLI are measurement-only (manifest state `split`). The default run and the default acceptance skip them and print `skipped`. `bash install.sh --only loki` (likewise `grafana`, `playwright-cli`) installs one for the measurement, and `bash accept.sh --only <slot>` checks it.
- 25 rows are not installed and keep a row with `installed: false`, `route: none` and the manifest's reason in `notes`: 14 with manifest outcome `not_installed` (the LSP plugins, reranker model, trafilatura, web search provider, ccusage, Phoenix, session analytics, Promptfoo, CodeQL SARIF, GPU container runtime, trufflehog, Claude Code Action, structural diff and chezmoi); agent messaging, code search, the embedding model and the local generation model (split, waiting for a measurement); durable memory (waits for the memory head-to-head); the container-boundary and context-supply decisions (nothing extra); attest and Dependabot (GitHub-hosted features: nothing is installed on the host); MCP Inspector and the base distribution.

An excluded row has no install or acceptance function; `accept.sh` prints `slot | stage | skipped` for it, and `install.sh` prints nothing.

`install-plan.json` schema version 2 stores acceptance as an object with up to three stage keys. Each check retains `command`, `kind` and `source`:

- `post_install` is the default. It checks the fresh installation with no stack service running and no sign-in. Prefer the documented local diagnostic/configuration validator; use a version command when no applicable self-test is documented.
- `service_health` retains the readiness/runtime checks and runs after the corresponding service starts. It does not perform sign-in or configure a provider.
- `after_sign_in` retains native-client diagnostics that need credentials and upstream model examples. Local Ollama also belongs here once its server and model route are provisioned; it needs no remote account.

Output is `slot | stage | exit-code`. An excluded or measurement-only row in the default run, an absent stage or an unavailable host check prints `slot | stage | skipped`; a skip does not certify acceptance and does not fail the script. A selected executable check failing with any nonzero status makes the script exit 1. Application stdout stays suppressed to avoid printing private diagnostic/model data; stderr and status are retained.

All 36 installed rows have a `post_install` entry: 20 smoke/configuration checks, 15 version checks and one explicit unavailable check, the credential guard, a repository practice with no installed host executable (`command: null`, `kind: unavailable`, a cited source and a reason). Eight installed rows have a service check and six have a check after sign-in or model provisioning. The three measurement-only rows add three post-install checks and two service checks.

Version-only post-install checks: Codex; Claude Agent SDK; Codex SDK; Ollama; Inspect AI; Harbor; actionlint (kjanat); Dagu; Docker Compose; Docker Engine; Git; gh; difftastic; Restic; OpenHands SDK/tools (and Grafana, measurement-only). SDK checks report package versions. GPT Researcher is checked by importing the source checkout and reporting its declared package version, because this route installs requirements rather than distribution metadata; its row is one row with DeerFlow (the manifest's `research-harnesses` slot), and the post-install check runs the GPT Researcher check and then DeerFlow's Compose configuration check in one shell, so a failure in the first stops the second. The DeerFlow Compose check validates configuration preparation only; it does not prove image availability or application readiness.

## Routes and lifecycle

Ubuntu's own `apt` package is Git's route. The base image/prerequisite installation already supplies it; rerunning this owner is idempotent. The Ubuntu candidate is not pinned to upstream Git v2.56.0. There is no PPA or source build.

Installed route counts: native-installer 4; none 6; npm-global 4; uv-tool 4; mise 10; release-binary 3; apt-repo 2; apt 1; repository-recipe 2. The measurement-only rows add one npm-global and two release-binary. The enum still lacks precise library/venv, local npm, skills-installer and marketplace labels; existing classification notes remain.

`mise.toml` retains the exact global tools (ten: ast-grep 0.45.3 is new, chezmoi is gone) and Node 24.21.0, Python 3.13.16 and uv 0.12.22 pins. `install.sh` merges them through `mise use -g`. Noninteractive diagnostics add mise shims to the process PATH without changing the shell. Doctor runs in the owned global tool directory so selecting only mise does not require the inventory's optional tools. Playwright's pinned CLI (measurement-only) installs its own bundled Chromium; the real browser open/close smoke explicitly selects that browser. OmniRoute service-health requires `/readyz` to succeed before its full doctor; doctor alone can warn about a stopped service and return zero.

Docker requires uidmap, dbus-user-session, kernel/rootless prerequisites and its upstream user unit. Exact Engine 29.8.2/Compose 5.5.1 apt revisions come from repository metadata; missing versions fail. Harbor's CLI installed in round 1; its overall installer failed later in Docker setup. Keep this prerequisite gate for the real distribution.

Upstream Docker and Dagu user setup start their services during installation. Other documented foreground/daemon starts, including Alertmanager's, are in [SOURCES.md](SOURCES.md#service-starts--separate-from-installation); the install does not run them, so those services' health checks fail until they are started (as the real-distribution run showed). Post-install checks do not require them. Dagu's user-bus setup, rootless Docker, sandbox namespaces and Git worktree access were checked on the real distribution (VALIDATION.md).

GPT Researcher's example performs model/search research. DeerFlow's `make docker-init` prepares the development workflow and can tolerate a sandbox image pull failure. Its post-install check validates that development Compose configuration with `DEER_FLOW_ROOT`; the retained production readiness probe applies to the separately documented `make up` start. Image builds, app model configuration and readiness are distinct checks.

Native self-updating Claude/Codex installers remain preferred over npm; reviewed releases are not runtime locks. Existing loopback service configuration, supported isolated Python environments and excluded overlaps remain in the JSON and [SOURCES.md](SOURCES.md). No new user unit was invented. No credentials or provider values are filled in.

## This revision

- **Rows follow the manifest.** Trafilatura, ccusage, Phoenix, Promptfoo and chezmoi lost their install and acceptance functions, mise tools, config files (`config/phoenix-compose.yaml`) and source entries; so did the rows that never had a host install (Claude Code Action, the CodeQL slot, trufflehog, the LSP plugins, the structural-diff row). attest and Dependabot became `installed: false`, with their reviewed workflow pointers kept in `notes`. Loki, Grafana and Playwright CLI keep their functions behind `--only`.
- **Added.** ast-grep 0.45.3 through mise (`structural-search`); Alertmanager v0.34.1 as a checksum-verified release binary with `config/alertmanager.yaml` (one receiver that sends nothing), port 21093 on loopback and clustering off (`alerting`); mattpocock/skills per skill for both agents, through the `skills` installer pinned to 1.7.0, source tag v1.2.3 and telemetry off (`engineering-process-skills`). `setup-matt-pocock-skills` is included because the upstream README asks that it be one of the selected skills.
- **Three repairs from the real run** (VALIDATION.md, findings 1 to 3): the Codex installer line sets `CODEX_NON_INTERACTIVE=1`, which the installer documents as skipping prompts; the Claude marketplace line for Trail of Bits adds the repository by its HTTPS clone URL, unpinned (the client takes a branch or tag there, not a commit, and the repository has no tag), and the acceptance prints the clone's `HEAD` beside the reviewed commit and fails when they differ; and the scripts stop with a clear message when `repo_root` is not a git checkout. The mattpocock row needs no such comparison: the installer clones the pinned tag. Its acceptance compares the `skillFolderHash` values that the installer recorded in its lock file with the expected git tree hashes of the six skill folders at the tag; it does not hash the installed directories. The clean run's record reports that the lock it returned had no `ref` field; the installer at v1.7.0 supports that optional field, and why it was absent in that run is unresolved.
- **`check_plan.py`** fails and names each problem when a selected row has no install function or no post-install acceptance, a function exists for a row that is neither selected nor measurement-only, `install.sh --list` does not print exactly the rows of `install-plan.json`, a `mise.toml` tool belongs to no selected or measurement-only row, a selected row's manifest counterpart is missing, `not_installed` or `split`, two rows claim one port, or a command has no source URL. It also checks that the rows are the manifest's foundation rows, that `owners.json` agrees, that the `run_command` lines and `check` calls in the scripts are the commands in the JSON, and that every `config/` file is copied.

The original [validation.json](validation.json) records the earlier source/static review and [container-validation.json](container-validation.json) the round 1 container run. The clean run of 2026-10-02 claims installation, post-install acceptance and the health of six services in a throwaway distribution, and nothing more: no provider call, model run, GPU use or sign-in, and no run on the destination distribution. After that run the header comments of both scripts and the plan's `status` text were corrected to say so; no command changed, and the record names the executed commits and file hashes.
