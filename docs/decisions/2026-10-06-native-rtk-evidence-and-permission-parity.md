# Diagnose native RTK observability and launcher matching (2026-10-06)

Decision: retain unknown Codex RTK firing/rewrite totals until a native
attributed observation exists, and propose an upstream wildcard-free matcher
repair for Claude launcher friction. Carry both in the existing foundation
draft #749, alongside the owned #779/#775 countability repairs. No host trust,
permission, client configuration or executable changes are authorized here.

North-star action served: fresh native sessions use adequate token tools for
complex engineering and research with accurate counters and the native
client's intended permission behavior. Coordinator: overlap-token; inherited
bounded workers verified primary source and separate worktree repairs. Their
conclusions are leads, verified against the exact upstream paths in the
[proposal](../proposals/2026-10-06-native-rtk-hook-observability-and-env-parity.md).

The maintained native trust check returns 0 for the installed RTK hook. RTK
0.51.0's Codex handler does not write its SQLite hook-decision table. Codex
0.160.1 excludes live hook-start/completion events from persisted rollouts.
These source facts invalidate treating zero SQLite matches as zero firings.
The original 24-hour before census remains 8,062 command items and 6,947 RTK
prefixes; prefixes and absent raw request/result pairs do not prove rewrites.
Older scratch-client qualification and the independently scoped command-center
census are not added to this population or promoted to current acceptance.

Selected upstream lever for RTK decisions: reuse RTK's existing best-effort
SQLite logger in run_codex Rewrite/Skip, where it is currently omitted.
Pinned Codex already emits session_id/tool_use_id/cwd matching its extraction.
Upstream native tracker regressions and a reviewed release gate adoption;
Ignore is not logged, so rows do not become all firings. Native app-server
notifications are the secondary broader-hook evidence owner. Their SDK stream
cannot be observed in parallel with unchanged high-level run; #773 owns any
public-API implementation and it does not cover current CLI lanes by itself.
A stable per-hook run ID is not an invocation dedup key. The P0 lifecycle
counter cannot alone identify RTK. Configuration-nonmutating discovery and
source review are complete; the trust helper can create normal app-server
state files. Actual organic every-lane proof remains open, with explicit
observer coverage/epochs/gaps/reload boundaries required for every AFTER row.

The installed RTK dry-run reproduces Claude's `env -u FOO python3 -V` denial
while the official client reference specifies exact wildcard-free matching.
The pinned RTK matcher implements equality or a word-boundary prefix instead.
Choose a maintained upstream Claude-origin parity fix with native permission
regressions and release evidence. The shared matcher also serves other hosts;
do not change their contracts without each host's native parity evidence.
Bare `env` denial, explicit wildcard scope and
deny precedence remain gates. Do not replace unsetting with assignment or
remove a permission guard locally. The command center reviews rule intent
and applies any configuration change after review/ACK.

Alternatives and comparisons: no blind trust reinstall after a green check;
no retrospective firing reconstruction from SQLite, prefixes or lifecycle
metrics; no private SDK API or competing stream consumer; no local RTK fork,
blanket permission allow or Codex-policy fix for a Claude matcher. A current
native wiring failure would reopen the trust proposal. Complete existing
attributed capture would replace the secondary observer proposal. A maintained
Codex logger already covering the adopted pin or an upstream behavior regression
would overturn the logger proposal. Version-matched client
evidence or upstream regression tests disproving exact parity would overturn
the matcher proposal. Promptfoo/Inspect can compare task impact when owner
quality is contested; native-arm organic evidence still decides exclusions.

The before/after and evidence-class gates are detailed in the proposal.
The paper-window boundary defers full validation and model probes; it does
not convert pending checks into passes. Keep all three PRs draft until the
command center's cross-family read. Register changed evidence in the takeover
branches last; no registry change is required for these proposal documents.

Completeness critic found three material refinements, incorporated in the
proposal: disclose app-server state writes in trust discovery, scope exact
matching to Claude before touching a shared multi-host matcher, and require
lane/launcher observer coverage rather than promoting SDK capture to CLI proof.
The next scoped sweep checks maintained RTK Codex logger parity and upstream
client permission contracts. Primary payload/source reads also identified the
simpler logger lever after the first observer proposal; it is a source-backed
proposal, not measured native acceptance.

The final critic also identified the existing five-second SQLite busy timeout
and Codex's wait for hook-process completion. The proposal now requires native
contention/timeout latency evidence before adoption; early stdout alone cannot
prove unchanged speed. A measured material delay would reopen the capture
alternative. This is an adoption gate, not an observed current regression.

Post-restart validation (2026-10-06): the complete repository integrity/scope
validator returned0 with69components,10184hashed files,4profiles,204receipts;
staged whitespace check returned0. Installed native version reads still give
Codex0.160.1, RTK0.51.0 and Claude2.1.291. These checks validate the proposal
publication, not organic hook decisions, a deployed fix or the pending
upstream contention/permission regressions. Durable validation and handoff
records survived separately from disposable scratch; lost unpublished/tmp
PR bodies were rebuilt after the reboot before publication.
