# Current foundation convergence: September 21, 2026

Keep the accepted native Codex/Claude foundation. This review checks selected
current upstream releases and community changes, collects a real native Claude
research Workflow, and reconciles catalog entries with already completed
acceptance. It does not install redundant alternatives or declare the evolving
ecosystem permanently complete.

The working checkout began at `86952998d3372dcf26cfc6f94782b4e03d097b8a` and
incorporated the independently published persistent-profile update at
`06ee9ccfa81823c94b03903e39ee7bb012ff5514`. Historical receipts keep their original
pins, inputs and failures. The [full foundation catalog](../catalogs/foundation/manifest.json)
still covers sixteen layers; this update does not recertify unchanged layers.

## Current upstream checks

| Selected component | Installed / current stable | Decision |
| --- | --- | --- |
| [Codex](https://github.com/openai/codex/releases/tag/rust-v0.155.1) | 0.155.1 | Retain; the stable reasoning-summary compatibility fix is installed. |
| [Claude Code](https://github.com/anthropics/claude-code/releases/tag/v2.1.278) | 2.1.278 | Retain; supported native workflows, workers and recovery remain the default. |
| [Context Mode](https://github.com/mksglu/context-mode/releases/tag/v1.0.169) | 1.0.169 | Retain; native Codex, Desktop and Claude package roots match. |
| [RTK](https://github.com/rtk-ai/rtk/releases/tag/v0.49.0) | 0.49.0 | Retain explicit supported routing and raw-output recovery. |
| [Headroom](https://github.com/headroomlabs-ai/headroom/releases/tag/v0.37.0) | 0.37.0 | Retain guarded, on-demand use. Update upstream links to the canonical organization. |
| [TOON](https://github.com/toon-format/toon/releases/tag/v4.1.1) | 4.1.1 | Retain conditional use; prefer compact JSON when smaller and adequate. |

The selected stable versions match current release metadata. Observed newer
Codex and RTK tags are prereleases; no demonstrated task gap justifies adopting
them. The Headroom repository's old identity remains a historical catalog alias;
its current source links now point to `headroomlabs-ai/headroom`.

ECC's observed HEAD remains `2b6e839771e53096d8451a213d40dc64ec8acac0`.
Independent byte comparison against pinned upstream files confirms that the
installed `search-first` and `iterative-retrieval` skills match in the shared
Codex and project Claude roots. Shan's practice repository advanced to
`5372d67bc098b25c4a4c875bc20d57e3c375ba2b`. The examined skills, commands and
subagent changes are version/date maintenance plus an output-style argument
label correction; they do not change the selected memory, routing or worker
acceptance practice. Retain the accepted installation and record the newer
source observation separately.

## Native cooperation and SDK choice

The [returned evidence](../evidence/receipts/foundation-convergence-20260921.json)
records the native Claude invocation, worker results, source observations,
actual models and usage boundaries. Current [Workflow documentation](https://code.claude.com/docs/en/workflows)
supports the native profile; the [portable recipe](../recipes/claude-native-ultracode.md)
retains explicit worker ownership, model selection and a concurrency ceiling.

The native Fable coordinator completed one Workflow with Sonnet and Opus
research workers. Both returned results; original child messages confirmed the
models. The invocation took 466.792 seconds and reported 2,078,181 cumulative
tokens, counting cache categories once. No matched savings baseline was run.
Persisted Opus worker output differs from the cumulative entry by 315 tokens;
complete reconciliation remains open.
The [adjudication](../evidence/artifacts/foundation-convergence-20260921/review-adjudication.md)
corrects unsupported claims about SDK isolation, missing source provenance and
authentication, and retains the failed/empty source lookups.

Use the native clients for engineering tasks. The [official Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
and [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview) are
application dependencies when programmatic sessions, events or tools are needed.
Installing another SDK does not strengthen the existing native worker evidence.
Claude SDK settings and account scope require explicit qualification for the
intended application; this review does not claim SDK execution or alter accounts.

## Completed evidence now visible in the catalog

- **Native Workflow recovery:** the separate decision now links selected-worker
  stop, failed/null results, replay of the accepted implementation, graceful
  exit, same-session resume, cleanup and integration. Its fixture passed the
  unchanged visible suite and independent held-out checks. The earlier writing
  comparison's procedure failures remain recorded.
- **Selective context policy:** the decision now includes all six accepted
  amended attempts and the rejected initial attempt. Each selective run used
  native computation and made zero Context Mode calls. The observed +2.42%
  aggregate token difference cannot measure Context Mode's causal effect.
- **Memory/RAG:** reuse the [fresh cross-client lifecycle evidence](native-memory-rag-lifecycle.md),
  including actual retrieval, stored Claude output and native monitoring. Keep
  vLLM 0.25.0 on this host: the newer runtime has a retained compatibility
  failure. Alternative memory repositories remain task-qualified candidates.

The dashboard gains separate Workflow recovery and selective-context entries;
older research, child-process and trading records keep their original scopes.
Dashboard freshness establishes publication, not task acceptance.

## Remaining boundaries

Native Workflow hard crash, physical-host reboot, remote provider cancellation
and external exactly-once effects remain unqualified. Its recovery usage views
still differ by 205,701 tokens. The next genuine daily maintenance trigger and
restart persistence need actual scheduler/restart observations; this manual
review supplies neither. Exact whole-session and lifetime token savings remain
unknown where upstream tools do not return them.

For future work, keep the [persistent native profile](../recipes/claude-native-ultracode.md),
load only the relevant layer, reuse matching acceptance, and evaluate a newer
candidate only against a concrete requirement. A future PC must establish its
own native sign-in, installation and useful behavior through the
[adoption handbook](../adoption/README.md).
