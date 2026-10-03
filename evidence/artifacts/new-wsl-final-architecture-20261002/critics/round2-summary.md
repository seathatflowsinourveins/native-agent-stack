# Contested slots, round 2: critics' verdicts, by session 80 (written 2026-10-02T05:03:52Z from date -u)

Method as in round 1, with each packet carrying the layer's requirement text: eight Opus critics with page access, blind record labels (workflow wf_e7d7f49b-459, all eight returned, 2,140,600 subagent tokens). Two critics with swapped labels for observation-inference and web-research; one critic for each other layer or pair. Full returns with URLs, quotes and each verdict's overturn measurement: session-80-20261002/critic/critics-round2-result.json.

## Settled

| Layer | Item | Verdict | Reason in one line |
|---|---|---|---|
| observation-inference | OpenLIT | do not install (2 of 2) | its jobs are metric and log storage plus a view; two containers with ClickHouse pinned at 24.4.1 (outside ClickHouse's supported versions) and its own older Collector v0.142.0; no measured gain |
| observation-inference | Prometheus | install (2 of 2) | metric storage is in the requirement and has no other owner; one process, embedded store, native OTLP ingest |
| observation-inference | Phoenix | do not install (2 of 2) | route qualification is evaluation, owned by Harbor and Inspect AI; no trace-store job in the requirement |
| web-research | trafilatura | do not install (2 of 2) | text extraction is a sub-step of retrieval that the agents' native web tools (or the one browser tool) already own |
| web-research | number of browser tools | one, not two (2 of 2) | agent-browser and Playwright CLI are the same job |
| quality-evaluation | Playwright test framework | do not install (1 critic, medium) | no host-level browser-test job in the requirement |
| quality-evaluation | Promptfoo | do not install (1 critic, high) | prompt and provider evaluation is owned by Inspect AI |
| instructions-skills | mattpocock/skills | install (1 critic, medium) | engineering-process skills; no name collision with Trail of Bits skills (empty intersection, checked on clones at d81f3a18 and 82fe8226); install per skill, not the bundle |
| git-github-automation | ataraxy-labs/sem | do not install (1 critic, medium) | same job as difftastic; one fact favours sem for agents: difftastic's JSON output is gated behind DFT_UNSTABLE=yes |
| git-github-automation | claude-code-action | do not install as a slot (1 critic, high) | runs on GitHub-hosted runners; a per-repository choice, not part of the machine |
| hosting-services | PostgreSQL | do not install (1 critic, high) | arrives as a service in the Compose file of whichever application needs it |
| recovery-portability | chezmoi | do not install (1 critic, high) | mise plus the repository-carried bootstrap already own configuration reproduction |
| token-efficiency | ccusage | do not install (1 critic, high) | the two agents' own usage commands and their OpenTelemetry token data own it |

Resulting layers where settled: quality-evaluation = Inspect AI, Harbor; instructions-skills = Trail of Bits skills, mattpocock/skills; git-github-automation = git, gh, worktrunk, difftastic; hosting-services = Docker Engine rootless, Compose; recovery-portability = mise, Restic; token-efficiency = nothing installed.

## Split between the two critics: needs a measurement (plan section 4.4)

**1. Loki and Grafana (observation-inference).** Critic 1: install both (tool results and API errors exist only as log events, so outcome observation needs an event store, and Loki ships no display). Critic 2: install neither (the requirement names usage and outcomes, not log search; the Collector's count and signal-to-metrics connectors turn events into counters for Prometheus, whose expression browser and HTTP API are the read path; journald holds unit logs). Both critics name the same comparison, so it is the deciding measurement: ten fixed observation questions (tokens and cost per session and agent, API errors by type, tool failure rate by tool, which injected failure happened in which session, service-run outcomes) answered on the same real task set, arm A = Collector connectors into Prometheus only, arm B = the same plus Loki and Grafana; metric: questions answered correctly, then operator minutes. Under the no-install rule the default until that run is arm A. The connectors are alpha for logs at v0.162.0 (both critics note it). It can run on the workstation today: Collector, Prometheus, Loki and Grafana are installed there with real telemetry.

**2. Which browser tool (web-research).** Critic 1: Playwright CLI (agent-browser's WSL2 gate is not cleared upstream: launch issues 1791 and 316 are open, the fix pull requests 1793 and 1796 are unmerged, v0.38.2 keeps the implicated --remote-debugging-port=0 launch; Playwright documents WSL and Ubuntu 26.04). Critic 2: agent-browser (one binary owns bounded page reads and interaction, no Node at run time, one skill command names both agents; it treated WSL2 as Linux x64). The gate decides first and is cheap: on the target WSL build, after the documented install, 20 consecutive default launches (close --all, open about:blank, snapshot) from a Claude Code shell and from a Codex shell with no connect-port workaround. If any fails: Playwright CLI. If all pass: the 20-task Harbor comparison both critics describe (static page, redirect, JavaScript-rendered page, form fill, login fixture, long page; both agents; same budgets), arm A agent-browser, arm B Playwright CLI. I can run the launch gate right after the WSL update; say if you want it.

## Notes for the manifest

- Serena's Claude Code call rate (round 1) and this round's "one browser tool" both become acceptance checks, not slots.
- One-vote extras were noted, not decided: ShellCheck and MCP Inspector (quality-evaluation), affaan-m/ecc (skills), Podman/Quadlet and Dev Containers CLI (hosting), Devbox (recovery), sqz and agent-console (token). None was recommended by a critic.
- If a project adopts Playwright Test later, that is the project's choice; the critic's note: run it with --trace on.
