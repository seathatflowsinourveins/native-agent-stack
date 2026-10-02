# Runtime worker coordination — 2026-09-30

This is a sanitized coordination receipt, not new runtime/provider acceptance.
The coordinator branch is `codex/runtime-qualification-20260930`, based on
`origin/main` at `be91e1f860a6cd4c07c9c56555dabc4309ad47cc`. Candidate implementation
stays in `codex/openhands-150-20260930` and `codex/codex-sdk-159-20260930`.

## Native cooperation evidence

Source: installed Claude Code 2.1.285 `--help`, `agents --help`, and `logs --help`;
the [upstream release](https://github.com/anthropics/claude-code/releases/tag/v2.1.285),
[cross-session messaging documentation](https://code.claude.com/docs/en/cross-session-messaging),
and [background-session lifecycle](https://code.claude.com/docs/en/agent-view#from-your-shell).
The maintained native client was used directly; no inbox/socket protocol was authored.

- A durable, owned `--bg` relay named `codex-runtime-native-coordination-20260930`
  was launched through the host execution surface with `--model opus --effort max`:
  exit 0. Native settings, tools, hooks, sign-ins and permissions were inherited.
- `claude agents --json --all` and `claude logs <owned-id>` returned exit 0.
  `ListAgents` established the relay's own native reply address before messaging.
- One initial directed exchange each with `sota-default-harness-setup` and
  `omniroute-token-save-pi-practice` returned `success:true`, queued delivery,
  and successful idle subscriptions. Both peers subsequently replied. An idle
  notice from the OmniRoute/pi peer was also observed.
- Queue acknowledgements establish contact only. Actual peer replies establish
  receipt of the request; their runtime claims remain reported evidence until
  the named original artifacts and gates are independently checked.
- A second, materially new exchange requests D4's SDK handoff through its lead,
  plus direct gateway/control and observer ownership from `native-agent-stack-bc`
  and `native-agent-stack-2d`. All three replied. D4's lead gave a conditional yes;
  neither bc nor 2d supplied a Gate A/P3 acceptance record or an observer owner.
  Both disclaim PR #423 ownership and refer to the other. Its owner/freeze remains
  unresolved. These replies do not authorize promoting defaults or gateways.
- The final ready SDK package and a materially new host-state clarification
  produced native `SendMessage` results rendered as sent to the SOTA-default
  lead and 2d respectively. The lead replied to the ready package; no new reply
  to the last clarification was observed. Prior bc ownership clarification
  remained unanswered at cleanup. No broadcast or GitHub comment was posted.
- Only the owned relay was stopped using native `claude stop`: exit 0. Its
  attached terminal then exited 0. Peer sessions were left under their owners.

## Ownership and handoff

`sota-default-harness-setup` reports no ownership of OpenHands/runtime recipes,
the SDK route adapter, or gateway paths. Its current A/F/D branches are neither
frozen nor accepted; only probes were reported. Preserve these boundaries:

| Owner | Reported owned surface |
| --- | --- |
| F1 | Root `AGENTS.md`, Claude instructions, Codex AGENTS template |
| F2 | Claude hooks and the Codex template's hooks block |
| F3 | Skill manifest/overrides and the Codex template's `[skills]` block |
| F4 | `tools/adoption/apply_codex_lane.py`, Codex role TOMLs, Claude user MCP template |
| D4 | Codex version/pin promotion, qualification receipt, model-currency addendum, and model lines in `adoption/templates/codex.config.template.toml` |
| A4 | Adoption token profile and token-efficiency stack documentation |

The SDK worker's requirements, constraints and lock changes remain isolated;
there is no global promotion. D4 was asked to retain promotion ownership and
accept a cherry-pick with the scoped qualification evidence. Its lead replied
with a conditional yes: provide full commit SHAs and the receipt
path, touch none of D4/F1–F4's owned files, preserve the actual evidence class and
sign-in/provider path, retain exact commands/exit codes, and validate the combined
head. A separate route commit and scoped SDK pin/docs commit can be handed off;
D4 keeps host-client pin and model/default promotion. If D4 opens before the
qualification lands, use a follow-up PR or its later live addendum. No commit has
been accepted or cherry-picked through this coordination exchange.

After receiving the ready package, D4's lead revised the handoff to a separate
follow-up PR rather than folding the SDK/runtime/trading surfaces into D4's
client-pin qualification. It reports no overlap with its unit paths. Its
recommended path is to retain both scoped commits, re-register shared evidence
on the PR head, use `lane:shared`, and base on `origin/main` after D4 merges so
the lock references the merged CLI pin. It requests the trading owner's
acknowledgement and 2d's review, with evidence class `local_integration` through
OmniRoute and gateway attestation/whole-task usage unknown. These are reported
review requirements; no peer freeze, default selection or client promotion is
created by this receipt. D4's lead offers to cite the receipt as related evidence
once that follow-up PR number exists.

The implementation coordinator subsequently supplied the ready package from
`codex/codex-sdk-159-20260930`:

| Surface | Commit |
| --- | --- |
| Route helper and tests | `352437881b76cfa18993a9e09412ae2b269c3778` |
| Isolated SDK lock, pin, docs and sanitized receipt | `580b69c1386d3fe53448f3d8ad28090d4b68ef22` |
| Optional shared evidence hash update | `7bc3b9b1088f782da87fedbc4aea95c142752656` |

D4 should re-register evidence using its current shared manifest instead of
cherry-picking the optional hash update. The handoff names
`evidence/artifacts/runtime-sdk-20260930/receipt.json`: a keyless clean loopback
route, fresh empty native home, and two real dynamic-tool/resume turns without
copying sign-ins. Its evidence class is configured-route native execution;
gateway attestation and whole-task usage remain unknown. The native cumulative
52,286 tokens are counted once. The implementation coordinator reports unchanged
upstream native tests at 266 passed, 38 skipped and one retained root-format
expectation failure; 29 integration/recovery/observation checks passed. Its
publication validation returned exit 0 with 69 components, 8,246 hashed files
and 174 receipts. These are handoff claims tied to the named commits and receipt,
not tests rerun by the coordination relay or complete native-suite acceptance.

The user's updated Codex dispatch preference is Sol/Ultra for the coordinator and
Sol/Max for default workers, preserving explicit models and roles. This receipt
does not alter explicit native Claude roles or the already selected
`cx/gpt-6-astra-max` qualification.

`omniroute-token-save-pi-practice` reports ownership only of
`blueprints/convergence-practice/pi-omni-trial-20260929/**` and its entries in
`manifests/evidence.json`, on PR #524. Shared evidence entries follow
`docs/lanes.md`; neither coordinator nor writing worker takes that peer's entries.
The peer assigns engine acceptance/P3 decisions to bc or 2d, rather than treating
the pi trial as runtime-worker qualification.

## Public source snapshots and gate limits

GitHub reads returned exit 0 for these repository PRs. These are observed heads,
not peer promises that the heads are frozen:

| PR | Observed head | Observed status |
| --- | --- | --- |
| [#423](https://github.com/seathatflowsinourveins/native-agent-stack/pull/423) | `e2e048053b151ac9c2ba269864cb4adf035058d3` | Open; freeze/ownership requested |
| [#425](https://github.com/seathatflowsinourveins/native-agent-stack/pull/425) | `ec229a780516edb18b5ea88f29b2f9c039aea85c` | Merged; recipe description records offline acceptance |
| [#489](https://github.com/seathatflowsinourveins/native-agent-stack/pull/489) | `501bcc9e50bf3ffa3acc82b6ecf20aa4e23c593b` | Open; OpenHands resolver |
| [#524](https://github.com/seathatflowsinourveins/native-agent-stack/pull/524) | `3443ee32a5411091b5aedd0930d7431d6f2003f7` | Open; pi trial |
| [#530](https://github.com/seathatflowsinourveins/native-agent-stack/pull/530) | `20799c058b0da7f32898772567320263303fce3b` | Open; OmniRoute rebuild evidence |
| [#531](https://github.com/seathatflowsinourveins/native-agent-stack/pull/531) | `be65860794897cd9bad47493b209ca9ab7c26603` | Open; stack row explicitly held |

The [pinned PR #524 gateway read-back](https://github.com/seathatflowsinourveins/native-agent-stack/blob/3443ee32a5411091b5aedd0930d7431d6f2003f7/blueprints/convergence-practice/pi-omni-trial-20260929/evidence/gateway-readback-20260930T0159Z.json)
was retrieved through the GitHub contents API with exit 0. It records compression
disabled on 20128 and enabled on 20129. The peer reports the native control remains
unchanged, with `codex/*` excluded from compression, and the 20129 ordered plan is
`session-dedup, ccr, lite`. Compression/combo digests remain provisional according
to its handoff. This is a dated read-back, not a new live observation or P3 pass.

The peer reports its pi trial's validator/convergence/probe checks passed; those
checks were not rerun here and are not promoted to OpenHands/SDK acceptance.
Exact Gate A/P3 acceptance, runtime-recipe ownership/freeze, and observer ownership
remain unresolved. No Gate A instrument was applied to these candidates.
2d's observer instruments belong to Gate A issue #381; this coordinator did
not run them on these inputs or reclassify those instruments.
This corrects the earlier attribution without inferring a freeze or an
acceptance decision.

When asked about frozen host files, the implementation coordinator reported no
Gate A route/config/pool writes: only fresh version-qualified SDK/private home/
workspace prefixes, a model listing and two provider tool turns through existing
20128. No sign-ins were read or copied and no global configuration was changed.
The OpenHands worker built pinned source and ran its tests, without a server,
container or model startup. This is the coordinator's implementation account,
not a new observer attestation. The coordinator also reports no task operation
of `ecosystem-upkeep.timer`, no changes to the root checkout or native Codex
state, and no on-disk `AGENTS.md` edit: the replacement instructions arrived
directly in the user's message. A directed clarification to bc/2d requests the
actual PR #423 owner or an explicit isolated-recipe handoff, without claiming a
freeze on their behalf. 2d replied without taking PR #423 ownership or supplying
gateway acceptance; no owner or frozen head is established at this checkpoint.

## Corrections and retained failures

- A prior one-shot `-p` relay queued both messages but could not subscribe because
  its return address was classified `unreachable-namespace`. Non-bare `-p` does
  support receiving inboxes; it cannot display held-message approval dialogs.
  The original failure is not proof that headless sessions cannot receive.
- An earlier owned background launch was stopped with exit 0 before this durable
  relay. Its post-stop `logs` failed with ENOENT on both context-mode and host
  execution. That does not establish a context-mode namespace cause. The active
  durable relay's logs are reachable from context-mode.
- A non-TTY resume attempt using a short background job ID exited 1: the client
  required a conversation UUID or session title in print mode. No new session was
  created. The supported native `attach` surface then delivered the new owned
  coordination prompt successfully.

No credential values, private session/message IDs, host-specific paths, raw
conversations or machine-specific active configuration are retained here.

## Receipt validation

`rtk python3 scripts/validate.py` returned exit 0 and `status: passed` with
69 components, 8,243 hashed files, four profiles and 174 receipts. Its returned
scope was integrity/scope checks only, with no live provider or GPU execution.

## SDK follow-up coordination checkpoint

The resumed bounded exchange used installed Claude Code 2.1.285 and the native
background, roster, messaging, logs and stop surfaces cited above, preserving
inherited settings, tools, hooks, accounts and permissions. Version/help/roster
and owned logs returned exit 0. The new owned relay ran `opus` at `max`. Exactly
one directed request per recipient used nonce
`codex-sdk-review-followup-20260930`; no broadcast or duplicate qualification was
requested. All three sends returned success/queued, and all three peers actually
replied. No held/refused delivery notice was observed. The relay alone was
stopped with exit 0; its attached terminal exited 0. No peer session was stopped.

| Recipient | Actual reply and remaining limit |
| --- | --- |
| SOTA-default lead, replying for D4 | Confirms separate SDK follow-up after D4 merges; D4 has no PR or URL yet and is reported unpushed |
| Trading owner e0 | No scope objection, with an effort-change correction required; final acknowledgement awaits PR number/head |
| Gate A owner 2d | No Gate A objection to the two-commit, ten-path range; explicitly excludes code review, acceptance and trading-path approval |

D4's lead reports branch `claude/sota-defaults-d4-codex-0159-20260930` at
`893a949635e29daf13b696b0c59444da31ca7f25`, merge base
`f77612b66fb92a7baace31f92e9f9bc3f7f5fb09`, with four commits and pin 0.159.2.
Builder acceptance/handoff and lead verification precede opening. Its reported
review order includes trading-owner acknowledgement and 2d review before the
related Amendment 4 revision. This is an attributed unpublished-branch handoff,
not a merged pin or host promotion. The npm CLI pin and PyPI SDK lock identify
different artifacts at the same version; the requested sequencing does not
assert they share an artifact or an enforced cross-lock dependency.

The public main head was independently read through the GitHub branches API,
exit 0: [7d0189117028907261d06926dee86844c1ae8f1e](https://github.com/seathatflowsinourveins/native-agent-stack/commit/7d0189117028907261d06926dee86844c1ae8f1e).
It supersedes the request's `b4056a3` snapshot. Do not infer a D4 freeze or merge
from that moving main reference.

e0's requested correction concerns `native_worker.py` applying
`model_reasoning_effort="max"` to the default `openai` path as well as the new
route. It previously passed only caller overrides. e0 accepts either documenting
that changed effort in `workers/README.md` or limiting the override to the
OmniRoute path. The requested PR/head acknowledgement has not occurred.

2d reports the SDK range does not overlap its owned or frozen paths and
`tests/test_observability.py` is outside its ownership. Re-registering the shared
evidence file follows `docs/lanes.md`: take current main's copy, register and
regenerate the relevant evidence outputs, then validate; whichever PR merges
second takes main's file again. Its conditions retain scoped homes, no host
configuration/launcher/gateway changes, no gateway traffic or default-home Codex
process during an announced measurement window, version alignment with the
final D4 candidate, unknown usage remaining unknown, and exclusion of the
52,286-token snapshot from Gate A measurements. It requires overall
`local_integration` claims and no `native_proven`, Gate A, P3 or observer
acceptance claim. Reported future window timing and gateway rebuild details were
not independently qualified by this coordinator; the SDK receipt names no
attested gateway build.

Correction: describing the SDK receipt as classified `local_integration` relayed
the requested overall review class, not a literal existing top-level field.
Original-source read at `580b69c1386d3fe53448f3d8ad28090d4b68ef22` using
`rtk proxy git show` returned exit 0. The receipt has no top-level
`evidence_class`; its live-attempt labels are `advertised_model_only` and
`native_provider_execution_configured_route`, with integration-check labels
`local_integration_contract_and_recorded_fixture_replay`. Its recorded timestamp
is `2026-09-30T05:26:01Z`. Preserve those specific returned-evidence scopes when
adding an overall class; publication validation alone does not prove a runtime
claim. No SDK receipt or pin was edited by this coordination task.

A local processing helper initially failed with a JavaScript syntax error,
exit 1, before its GitHub read ran. One bounded correction returned exit 0 for
the [related terminal PR #532](https://github.com/seathatflowsinourveins/native-agent-stack/pull/532);
that PR was not misidentified as D4's promotion PR. This append is left
uncommitted for the coordinator's integration, as requested.

## OpenHands candidate dependency ownership checkpoint

Source: [issue #518](https://github.com/seathatflowsinourveins/native-agent-stack/issues/518),
read directly through the GitHub API with exit 0, and an actual native reply
from `native-agent-stack-bc` to nonce `codex-openhands-lock-owner-20260930`.
Installed Claude Code remained 2.1.285. One directed native send was reported
sent/queued, then bc replied; no held/refused notice was observed. No e0/2d
message, broadcast or duplicate qualification was requested. Only the owned
coordination copy was stopped, using native `claude stop`, exit 0.

bc confirms ownership of the live OpenHands 1.49.6 lock's joint oauthlib/PyJWT
relock. It explicitly does not own the 1.50 candidate, recipe #425 or image
scan, and its reply approves no exception, pin or PR. The reviewed live PyJWT
2.14.0 lock digest is
`14e57b8d947e62ed60e7bbc69c2e6cc55638a86fa8969d528cbdf591cd42ae64`.
Earliest joint relock is `2026-10-05T18:40:43Z`, due October 8 with hard limit
October 13. The issue also assigns bc the September 30, 16:56:01Z PyJWT 2.15.0
decision; bc reports its recorded reasoning currently retains 2.14.0 until the
joint relock. This does not establish a new dependency selection.

The candidate process reported by bc retains PyJWT 2.14.0, not the inherited
2.13 regression, and oauthlib 3.3.1 before the joint relock. A changed closure
needs a new exact-SHA256-bound `IGNORE_ALLOWED_LOCKS` entry with a fresh
reachability receipt for `GHSA-hj66-6f7g-4r5v` and `GHSA-xpv3-w29h-x7cv`.
Its cited method is
`blueprints/runtime-workers/openhands/evidence/relock-2026-09-30.jwt-callers.py.txt`,
including aliases/from-imports and the `RevocationEndpoint` JSONP and PKCE
`code_verifier` call paths. No global advisory ID or expiry is added; the new
entry is removed at the joint relock. No ignore is allowed for the flagged
click, cryptography, pypdf or soupsieve versions; fixed selections retain the
seven-day rule. The issue records oauthlib 4.0.0's window ending October 5 at
06:01:19Z. PyJWT 2.14 is a reviewed fixed selection, not a newly granted ignore.

bc requires the recorded hashed `uv pip compile` method from pinned 1.50 source
to reproduce byte-for-byte in a fresh extraction; native CI OSV Scanner 2.6.0
must exit 0 with only the two digest-bound oauthlib exceptions, or none when
eligible fixed oauthlib is selected. The candidate's `pins.json` requirements
digest, coverage-test entry and receipt change together. The recipe's hashed
installation and SDK import must pass. bc will build its joint relock on the
then-current main lock, avoiding duplicate work. It requests the candidate
lock's SHA256 and PR head for its reachability review; those were not sent or
approved in this exchange.

The handoff attributes the original OSV exit 1, isolated candidate repairs,
unchanged upstream source/`uv.lock`, image findings and pending live quality to
the implementation coordinator. It also relays the separate SDK branch pushed
at `f5f7a517939b0561466defcf56ed772de9e1c96a`, its overall `local_integration`
class and documented default-OpenAI max effort. D4's requested SDK PR sequencing
is preserved. No merge or runtime acceptance follows from this ownership reply,
and this coordination task changed no code, pin, shared evidence hash,
configuration, account or runtime.

Correction: native `--bg --resume` by conversation name started a copy rather
than continuing under the original session ID. A later installed-client probe
also started an owned copy when the full native session UUID was supplied with
explicit flags: background sessions retain their saved options, so a full ID
alone does not guarantee continuation when flags are added. The native launch
guidance distinguishes a no-flags resume from this flagged copy. The earlier
statement that a full ID was sufficient was incomplete. The new owned
coordination copy returned launch exit 0 and was cleaned up.
One local orchestration expression initially had a syntax parse error before
any nested command ran; its bounded repair returned exit 0 for the version and
issue reads. This ownership append was uncommitted at handoff.

## Updated SDK accounting handoff, 2026-09-30

The published SDK follow-up is now at
`404b821cd3af25800ea418dc6145cc5cb6fe33c5`, rebased onto main
`cc1f6ce1f983721ecb42c7da27e58f0649c132f5`. Its additional accounting repair
`aa070a0` changes the Codex observation producer, two SDK receipts, repository
Collector README/YAML and two observation test modules. The earlier
two-commit/ten-path acknowledgements do not cover this expanded scope.
The [usage correction receipt on that branch](https://github.com/seathatflowsinourveins/native-agent-stack/blob/404b821cd3af25800ea418dc6145cc5cb6fe33c5/evidence/artifacts/runtime-sdk-20260930/usage-scope-receipt.json)
retains the native failed aggregate of 78,331, the unavailable additive result
after correction, unchanged private counters and the native Claude OTLP
positive control. The original tool/resume runs had no observation sink.

An owned native Claude 2.1.285 relay sent exactly three directed updates to D4,
e0 and 2d, with explicit Opus/max. All returned success/queued. Actual replies
were observed from e0 and 2d; D4 was still pending when the bounded owned relay
was stopped. Private delivery IDs and raw conversations remain outside this
repository. D4's SDK PR-after-pin-merge sequence remains in force.

e0 confirms receipt, while distinguishing it from final approval. It asks for
the actual PR/head, preserves opt-in OmniRoute, read-only/deny-all behavior,
documented default-OpenAI effort and no order/broker path, paper unit or venv
impact. It identifies the Collector as foundation-owned and requests Gate A
window coordination for final review.

2d confirms the updated head and named paths, with no Gate A objection to
source scope only. This is not code review, PR approval or runtime acceptance.
It states that deployed services use private configuration outside the
checkout, so a source-only Collector merge does not alter a frozen row; the
sealed runbook links an immutable SHA. It requires dated notice to 2d at least
six hours before the seal announcement for any deployment or Collector
restart, and no such operation during open windows. No deployment or restart
was performed here. It retains the shared hot-file protocol and native
counter boundaries, and offers deterministic scope/leak checks on an actual
PR head rather than model review.

The new runtime-candidate PR is also `lane:shared` because it changes the
shared dashboard pending gate/worker checkpoint. A trading-lane acknowledgement
on that actual PR is still required before merge; neither SDK receipt supplies
it. No nonexistent PR was submitted to peers for approval.

Successful native commands, with only private identifiers/prompts redacted:

```text
rtk claude --version
rtk claude agents --json --all
rtk git diff-tree --no-commit-id --name-only -r aa070a0
rtk claude --bg --resume <owned-id> --name codex-runtime-sdk-head-update-20260930 --model opus --effort max <bounded-prompt>
rtk claude logs <owned-relay>
rtk claude stop <owned-relay>
```

Each returned exit 0. The flagged resume created an owned copy as described
above. Only that relay was stopped; no peer session, global setting, account
or source file was changed by the relay. Provider/coordinator usage was not
measured and remains unknown. Root integrates this sanitized handoff record.

## Runtime-candidate PR review checkpoint

The native owned relay sent PR #535 at head
`bb3d00dc1ed493726481d0d3d746f6b0b46ed8bd`, based on
`f03f41c7f3601532b8635f8f112a3d2731454375`, to e0, 2d and bc. All three
actually replied. Launch, logs and owned stop returned exit 0; no peer was
stopped and no source edit, GitHub post or deployment was performed by the
relay. Provider/coordinator usage remains unknown.

e0's [public scope acknowledgement](https://github.com/seathatflowsinourveins/native-agent-stack/pull/535#issuecomment-5907440201)
was independently read through GitHub's API, exit 0. It covers that exact
head's shared paths and preserves the unchanged trading boundary. It is not
merge approval and does not carry to a changed index, dashboard state, OSV
configuration or suppression guard. The reconciliation changes the guard
and index, so final-head acknowledgement is requested again.

2d found no Gate A scope objection or leak in its deterministic source-scope
checks. This is not model review, test acceptance or merge approval. Its
requested correction is applied above: no Gate A instrument was used for
these candidates or reclassified. Original output whitespace is retained
under the evidence policy, with the full-diff failure distinguished from the
passing source/configuration check. Deployed Collector configuration remains
outside this checkout; no deployment or restart is authorized by this review.

bc found the first candidate SHA's two OAuthlib source suppressions sound for
Linux x86_64/CPython 3.13.15 only, while requiring the main-version and platform
corrections before review could finish. The [new reconciliation receipt](../../blueprints/runtime-workers/openhands/evidence/main-reconcile-20260930.json)
retains both baselines, native commands and installer-source trace. Its new
SHA needs a fresh review; the older finding supplies no approval for it.
bc's offered artifact publication was requested, but no publication was
confirmed during the bounded exchange and no scratch output is promoted.

## Source convergence and renewed owner exchange

The earlier publication limit is now resolved by merged
[PR #537](https://github.com/seathatflowsinourveins/native-agent-stack/pull/537)
at `11227bfdf25b55b0481a9e78985c3fed26052472`. The
[final review receipt](../../evidence/artifacts/openhands-oauthlib-review-535-head6a7b16-20260930/receipt.json)
binds published PR #535 head `6a7b16465e50689334d9dd15ff4fed99a9cd7485`
and lock SHA256
`383ccc5b87702174e471732872f002f1621186710402d048acc2b1910306e106`.
Its own SHA256 is
`c7473105255cc38bac1da6c7a490f99d863b58d865e82529d221b2a2e759908f`.
Original review outputs were read from the merged immutable revision and
matched independently. This completes the receipt/citation gap for its
bounded source/install/scanner review, excluding worker/image/provider,
independent observer and task-quality acceptance. It grants no merge,
exception, pin or promotion approval.

A new owned native Claude 2.1.285 Opus/max relay directly contacted the
client-pin owner, bc, e0, 2d and `runtime-omniroute-coop`. All five actually
replied. The other runtime session reports no ownership or overlapping work;
e0 owns the incoming shared-state update and requires a fresh acknowledgement
when this PR changes guard/documentation semantics. 2d reports source-only
cleanup is currently allowed, and keeps deployed Collector configuration
separate from its source review. D4 retains PR #542 and requests its actual
merge before the SDK follow-up. Peer claims do not qualify upstream behavior.

The coordinator's [source-backed follow-up decision](2026-09-30-runtime-convergence-followup.md)
and [planned image experiment](../../blueprints/convergence-practice/runtime-image-browser-20260930/README.md)
retain the full-image/Python gate and use only the supported native builder
composition. One targeted second exchange with D4, bc and 2d supplies the
stable SDK formatter gap, exact lock citation, supported image/grading sources
and source-only/resource boundary. Delivery is not consensus: actual second
replies and final published-head acknowledgements are recorded separately.
No image build, model trial, host/global setting, account, service or deployed
Collector change is performed by this exchange. Provider/coordinator usage
remains unknown, and only the owned relay is eligible for cleanup.

2d actually replied to the second exchange: the source-only operation
boundary is settled. A planned Docker/one-worker/12-iteration/frozen-ID trial
is acceptable now, with no build/run. Eventual preflight requires its host-load
agreement, existing rootless Docker, native Codex capacity, bc's gateway
agreement and start/end notices. No operation starts from the seal announcement
through the last window's close. Collector deployment/restart requires a
separate dated notice, at least six hours before announcement or after every
window closes; source review and source merge do not authorize it. The sealed
Codex arms keep explicit Astra unless amended by the user. 2d reviews source
scope/leaks and does not claim review of the Collector join-path content.
It will use dated U6 PR/README notices as well as live-peer messages, while
requesting a stable Codex coordinator contact. No new notice service is added.
The historical host actor remains unknown and does not block source cleanup.

The subsequent actual bc reply accepts the bounded reconciliation protocol:
wait for its dependency repair to merge; retain main's Next/macOS policy and
the captured-input fixture classifications; preserve this candidate's
SDK/tools 1.50 target-specific closure; change the lock SHA and its allowed
row together; register owned evidence from fresh main last; run native checks;
then request a new artifact-only review on the actual published head. The
old `383ccc…` review does not carry to a new lock, and no advisory ID or
expiry is extended by the candidate relock.

bc's actual 17:00 UTC reply confirms publication of PR #546 head
`bd48d924026635dccc18d30be8f56a2dc476fa89` at 16:59:42Z. The coordinator
also reads that head through the native GitHub client, exit 0, and dispatches
an independent Astra/Max review of the corrected guard and original native
outputs. The owner's reported main-lock digest and scan pass are review
leads until checked; publication is not merge or runtime acceptance. Native
incoming delivery of the candidate-running notice is recorded separately
from that actual reply. No additional service or timer supplies the handoff.

After independent native counterexamples refute the updated reader and a
consequential Astra/Max architecture review recommends the native boundary,
bc actually acknowledges the coordinator's hold decision: it will implement
separate scans inside PR #546 and will not merge the interim reader change.
The ordinary config retains unrelated ignores and contains no Next ignore;
the separate frozen-macOS config contains only the same dated Next exception.
The inventory must partition exhaustively and disjointly, preserving every
parser/path argument, with only the exact frozen artifact/digest assigned to
that config. Either nonzero native scan exit fails the combined check, and
both reports/SARIF categories remain covered. Native negative controls and
partition/digest controls are part of the final acceptance.

bc retains source/workflow ownership and will send the actual final head and
commands for independent review. The former candidate-reconciliation rule
that preserved the interim custom Next readers is superseded by this design;
reconcile only the actual final native split implementation. Obsolete reader
code/tests may be removed, while original failed-condition evidence remains
historical. This is actual implementation consensus, not a published fix,
merged PR, hosted pass or broader runtime acceptance.

The actual published native-split head is
`4a09c9c5f1e5fdb5555d4c916666f12e089cf09f`. Independent unchanged-command
execution confirms the 48+1 partition, both table/SARIF modes and frozen
digest assertions. A missing ordinary config exits 127 through the combined
workflow; altered frozen bytes fail their original test and exact restoration
passes. The bounded review has no outstanding material source defect. These
results were actually sent through native messaging to bc; delivery does not
establish an acknowledgement or merge. The owner still requires its eight
hosted checks and will supply the actual merge SHA.

A separate runtime-enhancement coordinator asks about private Codex homes,
MCP, roles and skills without taking this branch's paths. Its source reading
distinguishes the create-only initializer, opt-in applier and preserved
existing configuration. Those are source leads requiring original-source
verification. No private-home preparation or inheritance qualification is
performed here. The SDK receipt's fresh empty home qualifies only its named
tool/resume execution and supplies no MCP, skill, role or approval-loading
acceptance. The source applier owner and Gate A default-policy owner retain
their respective decisions; no host installation or default change follows.

The coordinator independently observes PR #546 merged at
`8fc86119eacfd5be9b8a139e1ed167d85748091b` through native GitHub reads.
Its isolated runtime branch is reconciled onto that actual revision. This
completes the dependency-source sequencing gate, while the new candidate's
published-head artifact review and broader runtime gates remain separate.

Original-source review corrects the private-home leads: the
[initializer](https://github.com/seathatflowsinourveins/native-agent-stack/blob/46e6d7763686cb49f89cc2e757c1122aa9bd8f9f/tools/adoption/codex_home.py#L181)
can also set `daemon_auto_start=false` in an existing config with backup and
read-back. The [applier](https://github.com/seathatflowsinourveins/native-agent-stack/blob/20616cba5964b46d92adb71e15dfa4b65c178b71/tools/adoption/apply_codex_lane.py#L482)
includes its two carrier roles by default; only its three additional worker
roles are opt-in. Its dry run rehearses a scratch app-server. That immutable
head requires Codex 0.157.1, while installed version/help report 0.159.2 with
exit 0. The live owner actually acknowledges this intentional sequencing gap:
its client-pin PR supplies the version reconciliation, and the applier follows
that merge and the measurement window. No preparation or default flip occurs.

The primary SDK source confirms child environment/config behavior at
[ff6aec9](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py#L250),
and [native home resolution](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/utils/home-dir/src/lib.rs#L13)
requires the supplied directory to exist. The initializer, owned MCP edits,
skill installer and native runtime extensions retain their own installation
and acceptance boundaries. Source review does not establish private-home
MCP reachability, implicit skill discovery, role loading or approval state.

The agreed neutral host attribution remains: pre-existing uncommitted changes
observed in the main checkout; original author not established. The coordinator
does not attribute those changes to itself or another session.
