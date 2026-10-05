# Round-2 adoption repair after the independent four-lens read (2026-10-05)

This PR repairs the clean-install and acceptance contracts for the six wave-5
owners. It serves the north-star action of reproducible native research and
build coordination for complex systems before the separately authorized broker
paper lane. The user pins this one repair round to GPT Sol at max; that pin is
preserved. The 39 verified findings and all dispositions are recorded under
`repair_round` in
[the integration ledger](../../evidence/artifacts/final-architecture-round2-20261004/integration-resolutions.json).
The four refuted proposals are not adopted.

## Install, authorization and producer identity

hcom now has its own selector and prerequisites. Its adapter never writes
`crossSessionInbound`; only the shared mapper's
`--apply --with-authorization-settings` writes that authorization key. A missing
key or a differing existing user choice does not fail messaging acceptance.
The adapter checks Codex policy only in check mode. Original source inspection
found an unconditional source-policy subprocess before apply, despite the
review's narrower description; removing that call avoids adding a Codex
installation prerequisite.

The dispatch checker requires a matching selected/named/measured slot, with
three explicit native bootstrap/dependency forms for mise, container-engine and
docker-compose. Applying the proposed blanket quoted-selector regex would
reject those existing guards and miss their prerequisite semantics. The real
checker negative control rejects the original hcom-under-srt defect. Source:
this PR, `install.sh:1083,1120,1161,1170` and `check_plan.py:499` in
`evidence/artifacts/new-wsl-install-plan-20261002/`.

Conformance's initial no-checkout clone checks cleanliness only when its index
exists. It remains named-only. Inspect AI alone writes the complete
Inspect/Scout/Harbor/pytest environment; the trajectory row selects that owner
first. These retain the existing upstream install formats and pins.

Harbor reads the installed OpenHands producer's `openhands-sdk` package
metadata, then requires both its adapter and returned trial version to match.
The worker pin remains 1.50.1. A future 1.51.0 move is an explicit handoff to
that owner. Auth-store upload variables are refused, and the containerized
native-openai Codex leg requires an OpenAI key injected by the existing external
per-provider runner. ChatGPT-only sign-in leaves this leg `needs_user`.
[Pinned Harbor adapter](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py),
[telemetry contract](../../evidence/artifacts/new-wsl-install-plan-20261002/config/harbor-worker-telemetry-contract.md).

## Delivered effort and browser integrity

The conflicting research and topology verdicts are reconciled through main
#637's [published OmniRoute 3.8.51 record](2026-10-03-omniroute-3851-pin.md).
Smart/strategic GPT Researcher and DeerFlow use plain `cx/gpt-6.1-sol` at xhigh;
FAST retains the high suffix. OpenHands uses the supported xhigh suffix.
Native Codex supplies Sol/max. The acceptance predicate joins each fresh run to
native call logs and requires the actual serialized provider model and effort,
successful calls and no embeddings route. A model label alone cannot qualify
the binding.
[Reasoning aliases](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts),
[actual prepared provider body](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/utils/providerRequestLogging.ts#L269).

Source review found a second effort path: DeerFlow v2.1.0 defaults
`supports_reasoning_effort` to false and removes the configured effort in that
case. The configuration now enables that supported flag, and effective
configuration read-back asserts it before live acceptance.
[Model capability default](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/config/model_config.py#L36),
[factory removal](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/models/factory.py#L283).

Chrome installation uses Google's signed HTTPS apt repository with active
primary fingerprint `EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796`, restricted
Signed-By and exact `google-chrome-stable=154.0.8037.97-1` selection from verified
metadata. A missing pin fails. The pinned Chrome MCP npm artifact's downloaded
SHA256 is recorded alongside its SRI. Both client registrations disable usage
statistics and CrUX, and acceptance checks both exact argument arrays.
[Google's published key](https://www.google.com/linuxrepositories/),
[Signed-By semantics](https://manpages.debian.org/bookworm/apt/sources.list.5.en.html),
[Chrome MCP 1.10.1](https://registry.npmjs.org/chrome-devtools-mcp/1.10.1).

## Source records and executable checks

The operative hcom authority quotes the user only from the original public
[Q11 record](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5972022684).
It names no tool. Sanitized verifier text remains intact with corrections that
identify its glosses. The four new removal checks explicitly report to the
owner and remove nothing by themselves. Amendment 4 remains byte-identical
across waves and is assembled once. The coordinator's regeneration rehashes
the changed wave records.

All five missing owners now have architecture cells using only allowed winner
fields, `name` for non-stack tools, actual decision-table pin lines and
`none_recorded` destination acceptance. The handbook suppresses the historical
Playwright pick only when the explicit profile binding and owner amendment
establish its Chrome replacement. A negative control keeps the old unresolved
pick visible without that binding.

hcom's smoke now parameterizes its unchanged upstream message roundtrip and
no-identity refusal with an empty inherited identity environment. After its
first Codex launch, acceptance loads the actual allow and deny files together
and requires terminal injection and configuration to remain forbidden. G1
records the per-run hook/hash/allow-list trust and the supplied RTK 0.51.0
measurement: RTK rewrites none of the commands forbidden by this deny set, so
its Codex hook cannot bypass them. The separate PR #705 guard refinement stays
with its owner, and `hcom-deny.rules` remains unchanged.
[hcom roundtrip](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/tests/cli_smoke.rs#L330),
[hcom Codex hook source](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/codex.rs#L314),
[G1 measurement record](2026-10-04-round2-plan-g1-messaging.md#repair-2026-10-05-transport-trust-and-measured-rtk-interaction).

Every `codex exec` and `claude -p` closes stdin. Scanner acceptance exercises a
known-bad upstream fixture as well as the safe control, and DSPy tests require
the installed environment's module under safe-path/importlib execution.
Prerequisite exit 78 is reported as `needs_user`, separately from failure.
The scholarly expansion is explicitly owed to the research owner because its
retriever/email requirements conflict with the current keyless `env -i` route.

## Alternatives and overturn

Retaining the old default would keep an authorization bypass, nonfunctional
named installs and label-only gateway acceptance. Moving OpenHands to 1.51.0
would change an unqualified producer owned by another lane. Extending the hcom
deny set would violate this repair's explicit policy boundary. These alternatives
are rejected in favour of the bounded source-backed repairs above.

P3 R2-19's deny-header reconciliation, R2-20's qualified transitive locks and
install-script routes, and R2-27's exact original user-record provenance remain
explicitly left with reasons. This repair would be overturned by a source-backed
contradiction in these bindings or a failed native destination acceptance that
the supported configurations cannot express. New adoption choices need their
owners' qualification and comparisons.

## Verification and completeness critic

The ledger retains the actual command exits, test counts and failed attempts.
The first full suite exposed an invalid architecture enum, stale generated
client tables, the intentional handbook replacement, test-created bytecode and
the new hcom after-sign-in entry missing from F9. Each was repaired without
weakening the remaining inventory or authorization contracts. Final checks are
local integration evidence; destination provider/GPU and unchanged upstream
runtime acceptance remain separate.

The completeness critic accounts for all 39 findings and checks the install,
authorization, provenance, consumer factory, delivered wire, transport and
native-client modalities. Its new missed modality was factory removal of a
configured effort, now repaired for DeerFlow. The next sweeps are keyed to
messaging activation/recovery, installation updates and qualification, research
configuration, skill vetting/removal, and decision-record provenance. Existing
owner handoffs and the three deferred P3s remain explicit; no new tool selection
or local model trial is claimed.
