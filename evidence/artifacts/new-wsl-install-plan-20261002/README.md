# New WSL install plan
Source-only plan for a clean Ubuntu 26.04.1 WSL 2 distribution with systemd, one non-root user, passwordless sudo, and existing RTX 4090 passthrough. **Every install, service-start, and acceptance command is UNRUN.** No installer or model/GPU check was executed.
The input selects 46 of 53 owners. All seven exclusions retain their original reason and have no command.
Route counts (selected owners): native-installer 4; none 6; npm-global 7; uv-tool 5; release-binary 4; compose 2; mise 10; github-action 4; apt-repo 2; repository-recipe 2. Including exclusions: none 13; other counts unchanged.
Acceptance counts (selected owners): smoke 25; health 7; version only 8; unavailable 6. Seven excluded owners have no check.
`install-plan.json` holds sources, pins, dependencies, configuration, and commands. `mise.toml` declares the global tool set plus Node 24.21.0, Python 3.13.16, and uv 0.12.22.
`install.sh --list`, `install.sh --only <slot>`, and `accept.sh --only <slot>` are **UNRUN** usage forms. Scripts refuse root. Both research tools share `research-harnesses`; selecting that slot retains both.
The installer orders system packages, mise/runtimes, user CLIs, rootless Docker/Compose, then services. Owner functions isolate failures; existing configuration is retained. No default-shell or Windows-side change is prescribed.
Only the upstream Dagu user-service installer and Phoenix Compose start services during a future install. Other foreground/daemon starts are separate in SOURCES.md; their health checks require a running service.
Docker requires uidmap/dbus-user-session and its upstream user unit. Exact 29.8.2/5.5.1 apt revisions are selected from repository metadata at execution; missing versions fail rather than silently upgrade. User-session startup is distinct from boot lingering.
SDK/research examples require native/provider configuration and can make model calls; Ollama's smoke downloads a model. These are planned checks, not installation acceptance already obtained.
## Gaps
Git documents source building, outside the permitted route enum; its owner has no install command. The system prerequisite Git is Ubuntu-managed.
The enum lacks library/venv, local npm, and marketplace labels. Claude Agent SDK, Codex SDK, OpenHands, GPT Researcher, and Trail of Bits use `none` with accurate commands and explicit classification notes.
Trail of Bits registers both pinned marketplaces; individual security plugin names were not selected, so registration does not claim every skill installed.
No host check exists here for attest, Dependabot, CodeQL SARIF, Claude Code Action, Git, or credential guard. `accept.sh` reports unavailable/77 and fails instead of inventing a pass. Repository recipes remain manual adoption pointers.
Dependabot Core has no action entrypoint, so there is no valid `uses:` reference; its tag SHA is provenance. CodeQL uses `upload-sarif` because its root action deliberately fails.
Upstream checks limited here to a version: Inspect AI; Harbor (containerized agent E2E runner); Promptfoo; actionlint (kjanat); Docker Compose; gh (GitHub CLI); difftastic; Restic.
Systemd user units are documented for Docker and Dagu only. OTel, Prometheus, Loki, Grafana, Ollama, OmniRoute, and Phoenix have the recorded service-form limitation; no new unit was invented.
Prometheus documents a release download in prose and quotes tar extraction; its HTTPS/checksum transport helper is separately sourced, not claimed as a Prometheus quotation.
## Route choices
Claude/Codex use native self-updating installers over npm; their reviewed releases are not runtime locks.
mise replaces system packages, alternate managers, and ad-hoc binaries where the registry supports the exact owner. Chez­moi/restic document mise; zizmor has Homebrew/PyPI alternatives. Dagu's first user-level installer wins over mise.
actionlint uses the documented `github:kjanat/actionlint` backend; the short registry name selects rhysd. Docker/Compose use the required official apt/rootless special case rather than mise.
Python CLIs documented with pip (Trafilatura/Inspect) use uv's documented isolated-tool command forms. Python libraries use dedicated uv environments; Codex SDK stays a local npm library.
GPT Researcher uses tagged source requirements because v3.7.0 declares package 0.16.0. DeerFlow uses noninteractive config/Compose preparation and Compose readiness instead of interactive `make setup` or host-only `make doctor`; model configuration remains native.
Phoenix uses documented Compose because native gRPC binds a wildcard even when its HTTP host is loopback. Only loopback HTTP/gRPC ports are published. Other auxiliary ports and settings are recorded in JSON/SOURCES.md.
MinerU's sample Python 3.12 becomes 3.13 within its documented supported range. Playwright's browser installation matches the CLI's pinned Playwright dependency; runtime WSL/browser compatibility is unrun.
## Review
Static/source check results are recorded in `validation.json`; none is a new installed-client, provider, GPU, or service acceptance run. SOURCES.md records quotations, adaptations, corrections, and the completeness critic.
Commit is blocked in this session: shared Git worktree metadata is read-only; staging failed with exit128. No commit hash exists for this plan.
UNRUN commit commands: `git add evidence/artifacts/new-wsl-install-plan-20261002 manifests/evidence.json`, then `git commit -m "New WSL install plan: one upstream install and acceptance command per owner (source-only, unrun)"`.
