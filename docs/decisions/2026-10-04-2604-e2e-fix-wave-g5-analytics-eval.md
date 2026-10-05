# G5 analytics and evaluation install-plan repair — 2026-10-04

The bounded builder owns `observation-inference/session-analytics`,
`quality-evaluation/harbor-containerized-agent-e2e-runner` and
`quality-evaluation/inspect-ai`, stacked on `PR #684's head`. The north-star action
is to qualify the observation and evaluation foundation used to build complex
systems and conduct US-equities research and historical simulation. These
changes supply executable acceptance recipes; they record no new host READY
result or model run.

The independent session-analytics review remains applicable because it has no
slot-specific adjudication. The Opus adjudications govern Harbor and Inspect:
Harbor's credential-free oracle/nop trials are the functional READY gate,
and Inspect needs its optional provider SDK and a provider-backed scored
upstream example. Fresh Claude/Codex invocation and model-backed Harbor
native-agent trials are later checks for those unwired CLIs. Native session
roots and fresh imported sessions are part of the analytics repair.

The private `fixes.json` input was absent when inspected. The executor,
independent review and relevant adjudications were available. The earlier
install-repair patch has no hunks for these slots. No credential file was read,
no WSL execution was launched, no service was started, and no commit was made.
The attempted scoped ai-memory query (`pin_first=true`, `limit=2`) returned
`MCP tool call requires approval, but approval policy is never`; pinned source
and canonical repository inputs supplied the evidence instead.

The retained primary pins are agentsview 0.43.0 at
`9be7745ad1906ee24e04eb05bb86c872ef0939a1`, Harbor 0.23.0 at
`1e5c5c6db929a10a140d05e606882c671ae20729`, and Inspect AI 0.3.273 at
`9e44f1b77ed7c912bf58baf30db8560937e7ce53`. The explicit Inspect provider
dependency is `openai==3.24.0`, upstream tag commit
`637f1b8b2e9fdc3220fd4edbb8602cc89dc489c8`: current non-yanked PyPI release
on the research date, satisfying Inspect's 3.1.0 minimum. No primary pin moved,
so stack/profile/architecture pin records need no changes. All source locators
and line references are retained in
[the G5 source section](../../evidence/artifacts/new-wsl-install-plan-20261002/SOURCES.md#g5-analytics-and-evaluation-sources-2026-10-04).

Agentsview's launcher uses the supported data-directory and native source-root
variables, usage-only retention, telemetry off and updates off on every call.
Both CLI search paths point to the pinned executable through that launcher.
The loopback daemon and archive configuration are owned by this slot. Native
sync/list/daily operations must return real data for both clients; the fresh
stage checks exact IDs, agent identity, messages and the pre-session UTC
boundary, then retains a failed absent-ID lookup. Daily fallback costs remain
estimates. Installation preserves an existing archive configuration and starts
no daemon.

Harbor and Inspect install their unchanged fixture/example source at the exact
release commits. Harbor runs the upstream `hello-user` fixture through its
native harness, requiring oracle reward 1.0 and nop reward 0.0, no trial
exception, and matching verifier output. The same positive reward gate must
reject nop. Inspect evaluates the unchanged theory-of-mind example through the
existing gateway route, reads the native log through `inspect log dump`, and
requires success, one completed sample and nonempty scores. An absent model
through that same gateway must produce an error log rejected by the same
positive predicate. Keep all actual logs, failures and exit codes privately.
Those artifact predicates are local integration assertions over upstream
operations; the builder did not run the upstream suites or native operations.

The alternatives were retaining version-only checks, using locally authored
mock tasks, making provider-backed Harbor native-agent trials mandatory, or
upgrading the primary releases. Version-only checks do not qualify behavior;
mock tasks do not substitute for the selected unchanged upstream examples;
the mandatory provider tier conflicts with adjudication; and no demonstrated
compatibility gap requires an unrelated primary re-pin. A clean native run of
these exact fixtures that exposes a pinned-release defect, or a maintained
upstream release with evidence that fixes that defect, would overturn the
choice. A gateway that accepts the absent model must fail this recipe's
negative-control gate and needs a discriminating provider failure condition
before provider acceptance can be recorded.

Corrections: oracle/nop does not require provider authentication; the Inspect
ZIP helper failed on unsupported compression rather than a missing header;
the provider minimum is at the fetched tag's `providers.py:382`; the installed
agentsview 0.44.0 help was only a lead for the selected 0.43.0 source. An initial
edit command had a colliding heredoc delimiter and failed before repository
edits; the corrected edit used distinct delimiters, and all embedded shell and
Python programs were checked afterward.

Completeness critic: source integrity, native source roots, retention, lifecycle,
functional native output and absent-condition controls are now specified.
Fresh native analytics receipts remain required from the E2E coordinator.
Harbor container-to-gateway access, native-agent trials and fresh-client Inspect
invocations remain distinct later evidence. This builder is limited to plan
and structural acceptance, with no independent live-host observation. Shared
historical status/count paragraphs were left for the coordinator as requested.

Structural validation: `check_plan.py` and both scripts' `bash -n` checks pass;
all 14 owned inner shell programs and both embedded Python programs also parse.
The handbook `--check` passes without regeneration because its recipe inputs
did not change. The requested four-module unittest suite returned exit 1:
324 tests, 84 failures and 12 errors. A clean local clone of the exact base
`PR #684's head`, using the same TMPDIR outside
`/tmp`, returned the identical totals and the same 96 failure/error identities.
The causes are outside G5: the owner RTK 0.50.0 row disagrees with the stack's
0.51.0 pin, and the generated Codex instruction block is already stale.
The base clone's publication validator passes. This patch changes five
registered artifacts and adds two configuration files, so its registry hashes,
byte counts and new-file registration remain the coordinator's update in
`manifests/evidence.json`. Raw returned outputs and pinned research checkouts
are retained outside the publication worktree; the compact verification record
is in the job's TMPDIR. Only the three owned JSON rows and shell functions
changed; shared plan metadata and row order match the exact base.
