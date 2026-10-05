# Native stack gaps — 2026-10-01

The selected Claude/Codex→OmniRoute workflow has its required SDK and base CLI tools. Docker and Compose are installed, the public repository is hosted, and native request/dashboard timers are active. The material gaps concern current provider execution, broader lifecycle acceptance, maintained tool updates and a portable release containing the current setup. The [dated evidence manifest](../evidence/artifacts/native-stack-gap-audit-20261001/manifest.json) separates native observations, retained runtime tests, upstream release review and conditional additions.

| Layer | Present | Missing acceptance or maintenance |
| --- | --- | --- |
| SDK / GPT worker | Official Codex Python SDK/app-server; accepted0.159.2 and staged0.159.3 | New real Sol/Max turn failed HTTP429. Real tool execution, selected MCP and resume remain open for0.159.3. |
| Repository CLI | GitHub repository/API/CI; gh2.101.0 | Qualify2.102.0 first: upstream fixes four issues in downloads, attestations and interactive skill search. |
| Portable clean host | Supported bootstrap/profile/release workflow | Current source is ahead of published adoption pinv2026.09.26.2; run the maintained validated release/re-pin procedure. |
| Worker lifecycle | Retained same-thread resume and recovery after interruption, deadline, selected MCP and Dagu graph | Provider-side cancellation, production descendant cleanup, broader writing effects and independent-host recovery. |
| Request automation | Existing watcher, live-clone and dashboard timers active/enabled | Complete request→native worker→independent result plus interruption/duplicate recovery. Add no duplicate watcher. |
| Graph automation | Dagu2.16.6 native acceptance retained | Qualify2.18.1;2.18.0 changed abort/timeout propagation. Server readiness alone does not establish scheduled model execution. |
| Docker | Client/server29.8.1; Compose5.5.1; rootless engine reachable | Qualify the chosen workload's mounts/network, restart, volume restore, rollback and cleanup. |
| Agent sandbox | KVM device present; current Docker `sbx` source reviewed | `sbx` is absent on PATH and KVM access/group prerequisites are unmet. OS setup/sign-in precedes local microVM acceptance if selected. |
| WSL containers | HostWSL2.7.13.0 | Upstream3.0.1 makes WSL containers GA; no adoption or workload lifecycle run here. |
| Runtime hosting | Public repository and local service readiness | Actual production/cloud target, authentication and offhost recovery remain separate scoped choices. |
| Package/runtime freshness | uv0.12.17; published OmniRoute CLI3.8.51 | Qualifyuv0.12.21 separately. Fresh startup of the published gateway package remains unqualified after npm lifecycle-script warnings. |

Additional SDKs are conditional: Codex TypeScript for Node callers; OpenAI Agents SDK for application handoffs/guardrails; Claude Agent SDK for programmatic Claude; LangGraph for checkpointed graphs; OpenHands for a separate worker runtime; Temporal for persistent workflow history and separately operated workers/services. These capabilities do not establish a missing mandatory SDK in the native Python coding path.

Microsoft Agent Framework was omitted from the earlier17-candidate runtime review. Its Python1.19.0 source has a Claude SDK package and OpenAI/application orchestration support. It is a credible conditional candidate, with pinned-source architecture review; it has no installation or OmniRoute/native workload acceptance here. No universal framework or complete-cost winner is claimed.

Root retained fresh original prerequisite, repository, Docker-version and timer outputs privately and published only hashes and bounded facts. These metadata checks submitted no model inference. Existing acceptance receipts are dated executions, not new runs. Paid hosting, new schedules, OS group changes, credential use changes and new installations were not performed in this audit.

A separate native Claude cross-session relay attempt exited1 at the account usage limit before `ListAgents` or `SendMessage` ran. No messages were sent. The failed relay's client-reported usage was0; complete audit usage remains unknown. It was not retried, and no quota reset or provider repair is claimed. Its original stream was lost when the context-mode sandbox was cleaned; root verified the surviving private derived digest, which does not replace retained original execution evidence.

Sources: [CodexSDK0.159.3](https://github.com/openai/codex/tree/01fc69f4026735edfdf6789820549727a4867b11/sdk/python), [GitHubCLI2.102.0](https://github.com/cli/cli/releases/tag/v2.102.0), [Dagu2.18.1](https://github.com/dagucloud/dagu/releases/tag/v2.18.1), [Docker29.8.1](https://docs.docker.com/engine/release-notes/29/#2981), [Docker sbx0.46.0](https://github.com/docker/sbx-releases/releases/tag/v0.46.0), [pinned sbx requirements](https://github.com/docker/docs/blob/3de2f99327a1dfb76389e211157f0a963c37640e/content/manuals/ai/sandboxes/install.md#L9), [WSL3.0.1](https://github.com/microsoft/WSL/releases/tag/3.0.1), [MicrosoftAgentFramework1.19.0](https://github.com/microsoft/agent-framework/releases/tag/python-1.19.0), [TemporalSDK1.34.0](https://github.com/temporalio/sdk-python/releases/tag/1.34.0).
