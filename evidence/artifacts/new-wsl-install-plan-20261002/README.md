# New WSL install plan

Revised after the coordinator's first run of 34 user-level slots in a disposable Ubuntu 26.04.1 container. Sixteen passed installation and acceptance; eighteen failed installation or acceptance. [VALIDATION.md](VALIDATION.md) classifies the failures with log locations and records the repairs. The revised installation and native acceptance commands have not been rerun on the target distribution. Local JSON, shell syntax, inventory and stage-dispatch checks are separate evidence.

The target remains a clean Ubuntu 26.04.1 WSL 2 distribution with systemd, one non-root user, passwordless sudo and existing RTX 4090 passthrough. The inventory retains all 53 owner rows: 46 selected and seven exclusions with their original reasons. GPT Researcher and DeerFlow share the `research-harnesses` slot and retain independent checks.

## Installation and acceptance

```sh
bash install.sh --list
bash install.sh --only <slot>
bash accept.sh --only <slot>
bash accept.sh --only <slot> --stage service_health
bash accept.sh --only <slot> --stage after_sign_in
```

Both scripts refuse root. Installation selects dependencies, isolates owner failures and retains existing operator configuration. No default-shell or Windows-side change is prescribed. `--list` is read-only and still lists every owner, including exclusions and both research owners.

`install-plan.json` schema version 2 stores acceptance as an object with up to three stage keys. Each check retains `command`, `kind` and `source`:

- `post_install` is the default. It checks the fresh installation with no stack service running and no sign-in. Prefer the documented local diagnostic/configuration validator; use a version command when no applicable self-test is documented.
- `service_health` retains the readiness/runtime checks and runs after the corresponding service starts. It does not perform sign-in or configure a provider.
- `after_sign_in` retains native-client diagnostics that need credentials and upstream model examples. Local Ollama also belongs here once its server and model route are provisioned; it needs no remote account.

Output is `slot | stage | exit-code`. An excluded owner, absent stage or unavailable host check prints `slot | stage | skipped`; a skip does not certify acceptance and does not fail the script. A selected executable check failing with any nonzero status makes the script exit 1. Application stdout stays suppressed to avoid printing private diagnostic/model data; stderr and status are retained.

All 46 selected rows have a `post_install` entry: 23 smoke/configuration checks, 18 version checks and five explicit unavailable checks. There are ten service checks and six checks after sign-in or model provisioning. The five unavailable entries have `command: null`, `kind: unavailable`, a cited source and a reason. They are workflow/adoption pointers with no installed host executable: attest, Dependabot, CodeQL SARIF, Claude Code Action and credential guard. No passing host check was invented for them.

Version-only post-install checks: Codex; Claude Agent SDK; Codex SDK; Grafana; Ollama; Inspect AI; Harbor; Promptfoo; actionlint (kjanat); Dagu; Docker Compose; Docker Engine; Git; gh; difftastic; Restic; OpenHands SDK/tools; GPT Researcher. SDK checks report package versions. GPT Researcher imports the source checkout and reports its declared package version, because this route installs requirements rather than distribution metadata. Compose checks for Phoenix and DeerFlow validate configuration preparation only; they do not prove image availability or application readiness.

## Routes and lifecycle

Ubuntu's own `apt` package is Git's route. The base image/prerequisite installation already supplies it; rerunning this owner is idempotent. The Ubuntu candidate is not pinned to upstream Git v2.56.0. There is no PPA or source build.

Selected route counts: native-installer 4; none 5; npm-global 7; uv-tool 5; release-binary 4; compose 2; mise 10; github-action 4; apt-repo 2; apt 1; repository-recipe 2. Including exclusions adds seven to `none`. The enum still lacks precise library/venv, local npm and marketplace labels; existing classification notes remain.

`mise.toml` retains the exact global tools and Node 24.21.0, Python 3.13.16 and uv 0.12.22 pins. `install.sh` merges them through `mise use -g`. Noninteractive diagnostics add mise shims to the process PATH without changing the shell. Doctor runs in the owned global tool directory so selecting only mise does not require the inventory's optional tools. Playwright's pinned CLI now installs its own bundled Chromium; the real browser open/close smoke explicitly selects that browser. OmniRoute service-health requires `/readyz` to succeed before its full doctor; doctor alone can warn about a stopped service and return zero.

Docker requires uidmap, dbus-user-session, kernel/rootless prerequisites and its upstream user unit. Exact Engine 29.8.2/Compose 5.5.1 apt revisions come from repository metadata; missing versions fail. Harbor's CLI installed in round 1; its overall installer failed later in Docker setup. Keep this prerequisite gate for the real distribution.

Upstream Docker/Dagu user setup and Phoenix Compose can start services during installation. Other documented foreground/daemon starts are in [SOURCES.md](SOURCES.md#service-starts--separate-from-installation-all-unrun). Post-install checks do not require those services. Dagu's user-bus setup, rootless Docker, sandbox namespaces and Git worktree access still need real-distribution acceptance.

GPT Researcher's example performs model/search research. DeerFlow's `make docker-init` prepares the development workflow and can tolerate a sandbox image pull failure. Its post-install check validates that development Compose configuration with `DEER_FLOW_ROOT`; the retained production readiness probe applies to the separately documented `make up` start. Image builds, app model configuration and readiness are distinct checks.

Native self-updating Claude/Codex installers remain preferred over npm; reviewed releases are not runtime locks. Existing loopback service configuration, supported isolated Python environments, exact action references and excluded overlaps remain in the JSON and [SOURCES.md](SOURCES.md). No new user unit was invented. No credentials or provider values are filled in.

The original [validation.json](validation.json) records the earlier source/static review. Round 1 results are historical container evidence; this revision does not claim a new provider, GPU, service or target-distribution run. The coordinator owns commits; this repair does not push or commit.
