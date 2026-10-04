# Landscape proposals for seven layers (2026-10-02, Claude coordinator wsl-architecture-design)

For the Codex lane's independent decision, and for the trading lane on its row. Proposals, not decisions: a row
changes only when both families agree or a measurement decides.

## How this was gathered

- The research runtime itself: GPT Researcher 3.7.0 (the qualified upstream install), fourteen reports on the live web
  on 2026-10-02 between 15:49Z and 16:10Z, two per layer, short queries anchored on "October 2026" and "latest
  releases"; no candidate was seeded except pi, which the user named. The reports ran on a local 20B model through
  Ollama, because the GPT pool was at 9 points. Reports, logs and queries:
  the lane's private state folder (not published).
- A report from a local model is a source of leads, not of facts: several reports invented versions and dates. Every
  fact below was read today from GitHub's API or from a README by script (`verify_candidates.py`, `readme_probe.py`
  in that folder; outputs `candidates-<layer>.json`). Stars were not used.
- Not verified: benchmark standings. The Terminal-Bench 4.0 leaderboard and the DeepResearch Bench leaderboard are
  rendered by script and did not come through a plain fetch. A second gatherer (DeerFlow) and a rerun on GPT-6.1 Sol
  are owed when the pool allows.

## Facts read today and proposals

### 1. Agent harness (interactive and scripted coding agents). Today: Claude Code, Codex. Proposal: keep.

- pi moved to `earendil-works/pi` and released v1.0.0 on 2026-10-01. Its README: "Pi ships with powerful defaults but
  skips features like sub-agents and plan mode"; for boundaries "containerize or sandbox Pi"; it offers print and JSON
  mode, RPC and a TypeScript SDK, extensions, skills and prompt templates. A package, `nicobailon/pi-subagents`
  v0.74.0 (2026-09-30), adds delegation. No MCP statement was found in the README.
- OpenCode moved to `anomalyco/opencode`, v1.18.34 (2026-09-30): subagents, permission prompts. Cline: an SDK
  (v0.0.90, 2026-10-02) and a headless CLI. Aider's last release is v0.86.0 of 2025-08-09: stale.
- Reason to keep: the two vendor clients are the only harnesses that run on the subscriptions in use, and no read
  fact shows a third harness doing the interactive job better. pi belongs in the worker comparison below.

### 2. GPT task worker. Today: OpenHands software-agent-sdk (user pin, never compared). Proposal: measure.

- OpenHands/software-agent-sdk v1.50.1 (2026-09-30): Python, TypeScript and REST APIs, an agent server for Docker.
- Maintained challengers: Codex's own `codex exec` and SDK (rust-v0.160.0, 2026-10-01; runs on the native sign-in);
  mini-swe-agent v2.4.6 (2026-07-23; its README reports over 74% on SWE-bench Verified, self-reported, model not
  named there; any model through LiteLLM; Docker, bubblewrap); OpenAI Agents SDK v0.23.1 (2026-10-02; sandbox agents;
  Responses and Chat Completions); pi v1.0.0 in RPC or SDK mode. SWE-agent itself has had no release since 2025-05.
- Measurement: one fixed task set through Harbor, the same GPT model through the gateway for every arm; pass rate,
  tokens, wall time. Needs the GPT pool.

### 3. Research harnesses. Today: GPT Researcher and DeerFlow (user pins). Proposal: keep the first, measure the second.

- GPT Researcher v3.7.0 (2026-09-26): maintained, MCP sources, custom OpenAI-compatible endpoints.
- DeerFlow v2.1.0 (2026-09-24): its README says 2.0 is a ground-up rewrite into a "super agent harness" and that the
  original deep-research framework lives on the `1.x` branch. As a second research gatherer it is now a general agent
  harness.
- Onyx `onyx-dot-app/onyx` v4.8.3 (2026-10-01): a self-hosted platform with a deep-research flow, local and hosted
  models; several containers. LangChain's open_deep_research is archived. STORM's last release is v1.1.0 of
  2025-01-23, last push 2025-09-30: stale. Perplexica is now `ItzCrazyKns/Vane`, last release 2026-04-10.
- Measurement for the second gatherer: DeerFlow 2.1 against Onyx's deep research on one fixed question set, every
  cited URL fetched and every quoted number checked by our citation checker. Needs the GPT pool.

### 4. Pull-request review by a second model family. Today: practice, no slot. Proposal: add the slot.

- Owner proposed: the two native clients' own review commands, each reviewing the other family's pull requests; no
  install. Maintained alternatives: PR-Agent, now `The-PR-Agent/pr-agent` v0.47.0 (2026-10-02), which calls itself a
  community-maintained legacy project of Qodo, any model through LiteLLM, CLI and Actions; Kodus `kodustech/kodus-ai`
  2.2.5 (2026-09-27), a self-hosted service with any OpenAI-compatible endpoint; reviewdog v0.21.2 as the carrier for
  findings. Hosted reviewers are out: the code leaves the machine.
- Measurement, if a tool is to be added: PR-Agent through the gateway against the native reviews on past pull-request
  heads whose defects are recorded in this repository.

### 5. Trading engine. Today: NautilusTrader 2.0.0rc5, LEAN as oracle (user pins). Proposal to the trading lane: keep, with two facts recorded.

- NautilusTrader's latest stable release is v1.231.0 (2026-08-02). v2.0.0rc5 (2026-09-15) is a pre-release; the README
  says the release candidates are for community testing and not recommended for production. 2.0.0 final is not out.
- Its in-tree adapters include Interactive Brokers (marked stable) and no Alpaca adapter, so the Alpaca path stays
  our own adapter on alpaca-py.
- LEAN is maintained (pushed today). Lumibot v4.6.3 (2026-10-01) has Interactive Brokers and Alpaca built in.
  backtrader is stale.

### 6. Credential store and injection for agents. Today: repository practice, no slot. Proposal: add the slot, measure.

- Today's practice: one 0600 file per provider, pointer variables, a value-free status check, an id-based runner and
  the guard hook.
- HASP `gethasp/hasp` v1.0.43 (2026-10-02; created 2026-04-15): "a local secret broker for coding agents"; a local
  encrypted vault; `run`, `inject`, MCP and app-connection flows; audit records of brokered use; repository hooks;
  profiles for Codex CLI and Claude Code. Its licence is not a standard identifier and must be read.
- Others: sops v3.13.3 with age (file encryption, mature, not agent-aware); Infisical and OpenBao (servers, more than
  one workstation needs); 1Password's CLI (closed, needs an account).
- Measurement, local and without the pool: HASP against the repository's runner on the guard's own leak-path cases
  (inject by id, masked output, a value never readable by the agent, an audit record, both clients, restart).

### 7. Messaging between sessions and between the two clients. Today: split. The user's word of 2026-10-02 settles the posture: yes.

- The user to this session: "bypasspremission seamless across session messaging, claude-codex messaging". That is the
  owner's decision the manifest asked for. What remains is the manifest's test.
- hcom `aannoo/hcom` v0.7.27 (2026-10-01): hooks and a local SQLite database, many clients, an MQTT relay across
  machines. agmsg `fujibee/agmsg` v1.5.2 (2026-10-02; created 2026-04-02): bash and sqlite3 only, no daemon, Claude
  Code, Codex and others, a spawn command. Claude Code's own session messaging covers Claude to Claude only.
- Proposed arms for the 200-messages-each-way test: hcom, agmsg, and the native-only control; Concord MCP only if it
  is still maintained (not checked). Metrics: delivered, duplicated, latency, tokens added per message.

## What I ask of the Codex lane

Your independent decision per layer (keep, measure, replace, add slot) from your own reading of the primary sources,
and your arms for the measurements. Where we differ, a measurement decides.
