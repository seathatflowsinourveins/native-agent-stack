# AO adoption for its own sessions — 2026-10-08

CC item `task-ns2604-coop-20261008T082012Z`, sections 1 and 3, adopts
[OrchestratorInc/agent-orchestrator v0.13.4](https://github.com/OrchestratorInc/agent-orchestrator/tree/e8a77577c14b015b947057d67c9171a78cdd5099)
in a bounded role: dispatch, tracking and PR/CI/review feedback for sessions AO
launches itself. Existing hcom Codex lanes keep their gateway route. The CC's
Claude workers use Claude Code's native agent view. Landing still follows the
CC cue and the existing 5f/auto-merge path.

## Evidence and scope

The decision uses the completed attempt-2 native execution, not a new model
run. Its [sanitized receipt](../../evidence/receipts/ao-bounded-feedback-20261008.json)
retains the original private receipt digest
`acc503d994e3e8a5e674d3b7818a93047f8982028682af2c381bf71b2175da88`.
The fixture was one disposable private PR at one head, with one deliberately
failing check and one inline finding. The PR was closed without merging.
The historical receipt reported G1/G2/G3 PASS for its narrowed unit. The current
assessment below corrects the comparative and deduplication claims without
changing that original private receipt or its native observations.

| Gate | Current evidence assessment and practical limit |
| --- | --- |
| G1: fewer manual cues | UNKNOWN. Two native automatic deliveries and zero operator feedback-send commands were observed, but the vendor manual-cue counter and a separate manual baseline were not measured. These counts do not establish a comparative reduction. |
| G2: fresh owner, head and check visibility | PASS through AO's native owner/PR/check view, with the check and persisted signature bound to head `9613571b4419a1dd0535d476d1e9b5eb5e44235b`. The assistant could not independently inspect the head because its command runner was unavailable. |
| G3: exactly-once, head-bound feedback | UNTESTED. Two native automation messages, one send attempt and one matching-turn acknowledgement per item establish delivery at this head. The unknown poll count does not demonstrate a second unresolved-condition evaluation or suppressed duplicate. Replay, restart, persistence-failure duplication, changed-head delivery and a control receiver were not exercised. |

Three native provider turns completed. Poll count remains UNKNOWN; elapsed time
divided by 30 seconds is not a measurement. This execution demonstrates two
feedback deliveries. It does not establish a pushed coding fix, a new-head acceptance,
general exactly-once delivery or full landing acceptance. The earlier fixture
mounted `codex` alone and omitted its sibling `codex-code-mode-host`; including
the complete native runtime is required in the prepared deployment, but no
causal repair or coding acceptance is claimed here.

The clean-home attempt failed with HTTP 409 `CODEX_ACCOUNT_AUTH_UNVERIFIED`.
The owner subsequently approved AO's own native sign-in import. Separately,
CC070938Z's proposed direct daemon route was stopped before launch: setting
daemon `CODEX_HOME` to the shared native home also reaches actual chat workers
unless the project overrides it. The account-service initialization at
`backend/internal/daemon/daemon.go:533` is not a worker-home override; the
actual chain through `session_manager/manager.go:5225`, `chat_spawn.go:229`,
`service/chat/service.go:606`, `codexappserver/driver.go:481`,
`processenv/processenv.go:14` and `persistenthost/host.go:589` preserves the
daemon environment. The isolated-container feedback PASS and this direct-route
STOP remain distinct historical reports; the current G1/G3 assessment above is
not a new run or retrospective baseline/deduplication measurement.

## Current landscape and comparison boundary

The [dated source and execution comparison](../../evidence/receipts/ao-orchestration-landscape-20261008.json)
carries the maintained upstream survey made Oct7/8, its exact primary pins,
current release read-backs for AO/Omnigent, and the already completed native
qualification attempts. The source classes include lane tools, local workflow
orchestrators, issue-driven workers and GitHub-hosted workflows. The original
private survey digest is
`b30f6920810fa692945a52a2400a41d9c6f0fa1b29a809778be30c3eafbdcb15`.

| Candidate / primary pin | Supported role and retained comparison evidence |
| --- | --- |
| AO v0.13.4, `e8a77577` | Latest release read-back still identifies this pin. Clean-home admission failed409; the approved isolated native-import route produced the two feedback deliveries recorded above. Coding, comparative cue reduction and repeated-opportunity deduplication remain unqualified. |
| Omnigent v0.17.0, `12b5f67d` | Latest release/tag read-back agrees with the retained vendor route. Published host-image install failed on the rootless UID mapping; unchanged vendor UBI host build failed on unavailable tmux. Both stopped before runtime, so there are no G measurements. The CC excluded this route; no new build was made. |
| hcom0.7.28 `b2a7c192`, agentsview0.44.0 `413a87f7`, worktrunk0.80.0 `b49ca7ee` | Primary README/CLI sources establish lane transport, observation/archive and worktree roles. They remain the installed Codex lane composition. No matched AO feedback fixture comparison was run against them. |
| OpenAI Symphony `be10a1b7`; DoorDash agentic-orchestrator v0.160.0 | Pinned README/SPEC sources describe an experimental Linear-driven worker reference and a desktop workflow orchestrator respectively. Source review only; no local matched feedback or supported-route execution acceptance. |
| GitHub gh-aw v0.89.21; Dagu v2.18.2 `5ca5c59f` | Pinned READMEs describe hosted agentic workflows and local operations DAGs. They serve those separate functions; no matched native owning-session feedback comparison was run. |

This is the CC's bounded operational adoption based on the recorded source and
qualification evidence. It is not a reproduced head-to-head benchmark, proof of
overall superiority or a new convergence claim. The omitted comparisons and
untested gates remain explicit; no extra model or baseline campaign is added.

## Adopted bounds

- Through `2026-10-14T03:28Z`, at most three concurrent AO sessions, on small
  PRs only, using the approved native sign-in route. This is a CC dispatch
  limit; it is not claimed as a tested daemon enforcement feature.
- AO-managed PRs have one poller: their lanes stop their own PR polling. AO's
  fixed 30-second PR/CI poll receives the CC's dated exception to the usual
  120-second interval. The next live run must measure attributable polling.
- The CC's guard uses `gh api rate_limit` and runs native `ao stop` when core
  remaining falls below 500. This is the REST-core rule. AO also consumes
  separately metered GraphQL points for full PR/check and review reads, so a
  healthy core balance does not establish GraphQL headroom. Observe both native
  `resources.core` and `resources.graphql` fields; GraphQL allowance and
  AO-attributable request/point consumption remain unmeasured boundaries. No new
  threshold or guard rule is introduced. Native returned-error cooldown does not
  replace the core stop control or cover every review path. The prepared unit
  does not establish a running guard; the CC supplies it at deployment.
- The daemon and actual workers use private container state and an isolated
  writable Codex home. The host's shared Codex home is never a worker home.
  Only AO performs its approved sign-in import. No credential is read, printed
  or copied by this records change.
- This PR records the decision and prior evidence. The user service stays in
  the lane's private coordination state, uninstalled; the CC installs it.
  No AO daemon, session or container is started by this PR.

Inverse: stop the owned user service and use native `ao stop --timeout 10s
--json` for the owned daemon, then remove only its dedicated container/state
when withdrawal is directed. The completed trial's container, state, worktree
and branch were already removed; its PR is closed. Native post-undo login status
returned exit 0, `Logged in using ChatGPT`.

## Primary sources and re-qualification

All AO paths below refer to `e8a77577c14b015b947057d67c9171a78cdd5099`:

- `docs/self-hosted-remote.md:77` describes running the unchanged daemon in a
  container; daemon/session and chat-driver files named above establish the
  worker environment boundary.
- The attempt-2 receipt retains native PR/check observations, automatic-message
  identities, persisted signatures, acknowledgements, failed conditions and
  cleanup observations. The public copy omits conversation text and private
  host configuration. These are local integration observations using synthetic
  feedback fixtures, not unchanged upstream acceptance tests.
- [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
  supplies the supported read-only bind semantics used by the isolated route.
  User service lifecycle follows installed systemd's native service interface;
  its syntax check is retained with the private unit, not called runtime proof.
- `backend/internal/adapters/scm/github/observer_provider.go:52` and `:128`
  use REST ETag probes; `:230` and `:287` use GraphQL PR/check/review queries.
  [GitHub's rate-limit API](https://docs.github.com/en/rest/rate-limit/rate-limit)
  exposes core and GraphQL as separate resources. Native client error detection
  at `client.go:422` and observer cooldown at
  `backend/internal/observe/scm/observer.go:462` are not a below500 daemon stop;
  review failure handling at `:1589` retains stale state. Poll ticks, REST calls
  and GraphQL points are not interchangeable counters.

AO replaces only the measured handoffs above. hcom/agentsview/worktrunk remain
the Codex lane tools; Omnigent stays excluded after its credential-copy and
missing CI-ingress findings. Re-qualify AO for the gateway pool when upstream
ships provider-aware/no-import Codex admission and profile forwarding. Remove
the poll exception when upstream ships a configurable interval of at least
120 seconds. Coding, restart and changed-head behavior retain their untested
boundaries until an authorized native run measures them.
