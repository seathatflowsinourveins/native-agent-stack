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

| Gate | Retained result and practical limit |
| --- | --- |
| G1: fewer manual cues | PASS for the two feedback handoffs: two native automatic deliveries and zero operator feedback-send commands. The vendor manual-cue counter and a separate manual baseline were not measured. |
| G2: fresh owner, head and check visibility | PASS through AO's native owner/PR/check view, with the check and persisted signature bound to head `9613571b4419a1dd0535d476d1e9b5eb5e44235b`. The assistant could not independently inspect the head because its command runner was unavailable. |
| G3: exactly-once, head-bound feedback | PASS for this process and head: two native automation messages, one send attempt and one matching-turn acknowledgement per item. Restart, persistence-failure duplication, changed-head delivery and a control receiver were not exercised. |

Three native provider turns completed. Poll count remains UNKNOWN; elapsed time
divided by 30 seconds is not a measurement. This result qualifies the bounded
feedback loop. It does not establish a pushed coding fix, a new-head acceptance,
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
STOP remain distinct.

## Adopted bounds

- Through `2026-10-14T03:28Z`, at most three concurrent AO sessions, on small
  PRs only, using the approved native sign-in route. This is a CC dispatch
  limit; it is not claimed as a tested daemon enforcement feature.
- AO-managed PRs have one poller: their lanes stop their own PR polling. AO's
  fixed 30-second PR/CI poll receives the CC's dated exception to the usual
  120-second interval. The next live run must measure attributable polling.
- The CC's guard uses `gh api rate_limit` and runs native `ao stop` when core
  remaining falls below 500. The prepared unit does not establish a running
  budget guard or measured poll usage; the CC supplies the guard at deployment.
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

AO replaces only the measured handoffs above. hcom/agentsview/worktrunk remain
the Codex lane tools; Omnigent stays excluded after its credential-copy and
missing CI-ingress findings. Re-qualify AO for the gateway pool when upstream
ships provider-aware/no-import Codex admission and profile forwarding. Remove
the poll exception when upstream ships a configurable interval of at least
120 seconds. Coding, restart and changed-head behavior retain their untested
boundaries until an authorized native run measures them.
