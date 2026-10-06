# One default for each host tool

**Date:** 2026-10-06. **Status:** selected defaults and coordinated owner amendments; executable alignment and destination qualification pending. **Scope:** the NativeStack2604 host-toolchain defaults, selected harness owners and the trading installer's uv gate. The north-star purpose is a reproducible foundation for US-equities research and simulation.

## Decision

Use the install plan's adopted host-toolchain versions as the defaults for a fresh host. The profile summary, executable bootstrap pins, install-plan configuration and exact-version gates must refer to the same selected version. A dated receipt retains the version it actually observed; it is evidence, not a second executable default.

| Logical host tool | One selected default | Official release / publication UTC | Source identity |
| --- | --- | --- | --- |
| Node.js | 24.21.0 | [2026-09-08](https://nodejs.org/en/blog/release/v24.21.0) | nodejs/node@955266bfdd854cd280dffd47548673914484e4c0, v24.21.0 |
| uv | 0.12.22 | [2026-10-02T00:20:42Z](https://github.com/astral-sh/uv/releases/tag/0.12.22) | astral-sh/uv@70fe1196a546e49148a73b1c592b2f74c33af80e |
| GitHub CLI | 2.102.0 | [2026-09-30T02:40:02Z](https://github.com/cli/cli/releases/tag/v2.102.0) | cli/cli@fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd |
| CPython for host tools | 3.13.16 | [2026-09-30](https://www.python.org/downloads/release/python-31316/) | python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91, v3.13.16 |
| Codex CLI | 0.160.1 | [2026-10-05T18:29:37Z](https://github.com/openai/codex/releases/tag/rust-v0.160.1) | openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb |
| Claude Code | 2.1.292 | [2026-10-06T18:59:30Z](https://github.com/anthropics/claude-code/releases/tag/v2.1.292) | release-repository tag fbe20e00e2851fc01506f54f98a8f0b875af3847; proprietary CLI source identity is its published native artifact |
| Harbor | 0.24.0 | [2026-10-05T05:04:52Z](https://github.com/harbor-framework/harbor/releases/tag/v0.24.0) | harbor-framework/harbor@b53b8134e1241686dca7759af188f987ecc48e8b |
| OTel Collector Contrib | 0.162.0 | [2026-09-29T10:11:33Z](https://github.com/open-telemetry/opentelemetry-collector-contrib/releases/tag/v0.162.0); [binary distribution 12:34:07Z](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.162.0) | contrib@ae8c507510f48f433ab47dd1c6b01a59d6c388b5; distribution@f6159a775dad1e21433c49bd8450673dd13ed4d3 |
| vLLM | 0.31.0 | [2026-10-05T06:44:55Z](https://github.com/vllm-project/vllm/releases/tag/v0.31.0) | vllm-project/vllm@db9527a46873454610df6dbedf79a36d6bf1a7f6 |

Selection does not advance installed or accepted status. Claude 2.1.292's ordinary 24-hour promotion gate expires 2026-10-07T18:59:30Z. Harbor 0.24.0 and vLLM 0.31.0 remain qualification targets; the observed host still reports Harbor 0.23.0, and the presence of two vLLM environments does not identify the active server. Codex 0.160.1 and Collector 0.162.0 version observations alone do not replace the owners' native qualification receipts.

The trading project's explicitly pinned interpreter 3.12.3 is a project requirement, separate from the CPython 3.13.16 default for host tools. This decision does not authorize changing its interpreter or dependencies. A future project-interpreter change needs that project's upstream compatibility and native qualification evidence.

## Why one decision needs several owner amendments

At main@0d5e6506434fab598dee861c749a22e628beb75a, the [profile summary:4655](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/adoption/new-wsl-profile.json#L4655) names uv 0.12.17, gh 2.101.0 and Python 3.13.15. The [install-plan mise file:6-15](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/evidence/artifacts/new-wsl-install-plan-20261002/mise.toml#L6-L15) names 0.12.22, 2.102.0 and 3.13.16; fresh installed version probes match the plan.

Updating the summary alone would leave the executable bootstrap unchanged. [bootstrap-linux.sh:233](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/adoption/bootstrap-linux.sh#L233) consumes [pins-linux-x86_64.json:24-39](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/adoption/pins-linux-x86_64.json#L24-L39), whose uv and gh rows still name the old versions. Its Python request is the 3.13 family at :989,:1007,:1450. The bootstrap owner must make the exact default explicit while retaining the supported native installation route. The existing preservation policy applies to a native self-installing client: [bootstrap-linux.sh:843-852](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/adoption/bootstrap-linux.sh#L843-L852) and [:874-876](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/adoption/bootstrap-linux.sh#L874-L876) retain a newer existing version above the installation floor; they do not define a second default.

The amendments below were checked against main@4ce7632b865a19fe806f12442f64d7157f08f18c. Currency's profile/bootstrap follow-up starts after #642 and #645 land, or is folded into an unlanded wave only if 5f requests it; currency does not push to those queued branches.

| File and line | Current pin | Selected pin / amendment | Owner |
| --- | --- | --- | --- |
| adoption/new-wsl-profile.json:226; bootstrap summary:4663 | Node 24.21.0 | Keep 24.21.0 | currency after #642/#645 |
| adoption/new-wsl-profile.json:283; bootstrap summary:4664 | uv 0.12.17 | 0.12.22 | currency after #642/#645 |
| adoption/new-wsl-profile.json:334; bootstrap summary:4665 | gh 2.101.0 | 2.102.0 | currency after #642/#645 |
| adoption/new-wsl-profile.json:396; summary:4657 | Python 3.13.15 | host Python 3.13.16 | currency after #642/#645 |
| adoption/new-wsl-profile.json:448; summary:4655 | Codex 0.160.0 | host CLI 0.160.1; keep the SDK/bundled-CLI exception below separate | currency with codex-token-parity |
| adoption/new-wsl-profile.json:554 | Claude 2.1.284 floor | selected default 2.1.292 after cooldown; keep newer-client preservation | currency with native-client owner |
| adoption/new-wsl-profile.json:1744 | Harbor 0.23.0 | 0.24.0 after native qualification | currency with Harbor owner |
| adoption/new-wsl-profile.json:3460 | Collector 0.162.0 | Keep 0.162.0 | currency with Collector owner |
| adoption/pins-linux-x86_64.json:9,24,39,54,70,106 | Node 24.21.0; uv 0.12.17; gh 2.101.0; Codex 0.160.0 and platform package; Claude 2.1.284 | 24.21.0;0.12.22;2.102.0;host Codex 0.160.1 with its matching platform package;2.1.292. Change version, URL and verified checksum/integrity together | currency after #642/#645 |
| adoption/bootstrap-linux.sh:989,1007,1450 | Python 3.13 family request | Make the host default 3.13.16 explicit through the native uv route | currency bootstrap follow-up |
| evidence/artifacts/new-wsl-install-plan-20261002/mise.toml:6-8,15 | Node 24.21.0; Python 3.13.16; uv 0.12.22; gh 2.102.0 | Keep all four aligned | fixwave-defects (#723) |
| evidence/artifacts/new-wsl-install-plan-20261002/transfer-mise.toml (#776) | No Node/Python/uv/gh entry; named-only Gitleaks/Grype/ntfy/Qdrant transfer | Keep named-only scope; do not introduce a second host-toolchain default | fixwave-defects (#776) |
| evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json:13,47,54,96,2208,2850,2855,2900 | Claude 2.1.287/Codex 0.160.0 reviewed-source references; Collector 0.162.0; Harbor 0.23.0 executable selection | Review client references to 2.1.292/0.160.1 without treating them as runtime locks; keep Collector 0.162.0; qualify Harbor 0.24.0 and regenerate its consumers | fixwave-defects and native component owners |
| manifests/stack.json:192,298,1037,1095 | Claude 2.1.284; Codex 0.160.0;vLLM 0.30.0; Collector 0.161.0 | 2.1.292;0.160.1;0.31.0;0.162.0 with saturation-audit rows and real qualification receipts | currency wave/native component owners; queued branches remain 5f-only |
| .github/workflows/validate.yml:149-151 | uv 0.12.17 and its UV_SHA256 | uv 0.12.22 and the verified selected archive checksum | github-ci-finalize |
| blueprints/us-equities/runtime-2604/sync-trading-2604.sh:9 | uv 0.12.17 | 0.12.22 | 5f |
| blueprints/us-equities/runtime-2604/install-trading-2604.sh:84-112 | Frozen sync-vector digest and exact uv check | Refresh the digest with the changed sync file; retain the exact0.12.22 gate and failure path | 5f |

## Additional operative consumers and generated locations

The J805 residual inventory was checked against this PR's main67c6b6f94 base. Every executable artifact amendment couples the version, URL and verified checksum/integrity. These are owner amendments, not permission to hand-edit generated scripts or run an unqualified new runtime.

| Consumer and exact location | Residual pin | Coordinated amendment | Owner |
| --- | --- | --- | --- |
| tools/adoption/apply_codex_lane.py:134,774-776 | CODEX_VERSION 0.160.0 and exact-equality guard | Qualify the host lane at 0.160.1; amend constant, guard expectation and lane tests with the selected bootstrap pin. SDK-specific pair qualification remains separate | codex-token-parity (#716/#770), with currency bootstrap |
| scripts/native_token_ci.py:112-114,811-813 | uv 0.12.17 download URL and SHA256 | Amend version, URL and verified archive hash to 0.12.22 together; keep prior frozen harness receipts | github-ci-finalize with native-token harness owner |
| Generated install.sh:714,716,726,728 | Harbor 0.23.0 source/wheel and installation paths | Generate 0.24.0 from amended plan, verified source/wheel and qualified environment | fixwave-defects / plan generator |
| Generated accept.sh:1282,1284,1296,2159 | Harbor 0.23.0 assertions and checkout paths | Generate matching qualified 0.24.0 checks; retain failure conditions and evidence scope | fixwave-defects / plan generator |
| install-plan.json:2801,4609,4619-4623 | Harbor 0.23.0 also in Inspect/Scout's single owner environment | Amend pin, wheel filename/URL/hash and environment notes to qualified 0.24.0 together; qualify Scout/ATIF imports without creating a second owner environment | fixwave-defects; acceptance owner via CC |
| Generated install.sh:307,346,452,527,534,568,716,728 | Python 3.13 family requests | Generate host-tool environments using 3.13.16; preserve the separately qualified SDK/project interpreter exceptions below until requalified | fixwave-defects / plan generator |
| config/harbor-worker-telemetry-contract.md:19; install-plan.json:2904 | Container producer Codex 0.160.0 | Coordinate kwargs/observed-version oracle at host 0.160.1 with Harbor adapter/native telemetry qualification; do not alter SDK constraints mechanically | fixwave-defects with codex-token-parity/producer owner |
| recipes/README.md:114,288 | vLLM 0.30.0 install and serving prefix | After serving qualification, update package requirement and matching executable prefix to 0.31.0 together; preserve the dated0.30.0 receipt | vLLM/embedding owner via CC |
| observability/collector/README.md:3-5,12-17 | Collector 0.161.0 release/install URL and archive hash | Update0.162.0 version, matching distribution URL/hash and native validation together; preserve the prior0.161.0 observation | Collector/observability owner via CC |

The generated install/accept/plan/config paths above are under `evidence/artifacts/new-wsl-install-plan-20261002/`; amend the owners' plan/config/generator inputs and regenerate. The lane-guard break is inferred from its exact comparison, not a newly executed failure: host 0.160.1 would fail the unchanged CODEX_VERSION 0.160.0 check. [Guard:134,774-776](https://github.com/seathatflowsinourveins/native-agent-stack/blob/67c6b6f94b456a3a7b5d28bb1fa34625a808d316/tools/adoption/apply_codex_lane.py#L774-L776), [native-token uv:112-114](https://github.com/seathatflowsinourveins/native-agent-stack/blob/67c6b6f94b456a3a7b5d28bb1fa34625a808d316/scripts/native_token_ci.py#L112-L114).

## Classified retained pins and scope exceptions

| Consumer and exact location | Retained pin | Justification / follow-up | Owner |
| --- | --- | --- | --- |
| blueprints/us-equities/workers/requirements.txt:1; adoption/sdk/accepted-constraints.txt:22-23; adoption/sdk/requirements-linux-x86_64-py313.lock:571,577; examples/omniroute-codex-sdk/worker.py:5,39,226-227; worker.py.lock/test_worker.py.lock:6,19,33 | Python SDK and bundled CLI 0.160.0 | Compatibility exception in the isolated SDK runtime. Released metadata requires openai-codex-cli-bin==0.160.0 and the worker enforces that pair. A new pair needs package integrity, regenerated locks and native qualification; do not substitute host CLI 0.160.1 | 5f trading requirements; shared SDK/example owner via CC |
| adoption/sdk/README.md:3,5,7,11,37 | Historical uv 0.12.17 resolution; qualified SDK Python 3.13.15; dated launcher0.159.3 observation | Keep resolution facts and SDK interpreter until requalified under host 3.13.16. Date the launcher observation as the October 3 receipt, not current host state; preserve the receipt | SDK harness owner via CC |
| adoption/pins-linux-x86_64.json:82,91; docs/decisions/2026-10-04-codex-dated-holds.md:15,23,86 | Codex 0.159.3 hold through 2026-11-04 | Dated status-only exception; bootstrap installs the selected row, not the hold. Preserve artifact identities; retire when held hosts switch or the deadline arrives | currency bootstrap follow-up |
| adoption/new-wsl-profile.json:2053,2062,2065-2066; install-plan.json:162,167,177; generated install.sh:231 | Non-default source-only TS SDK 0.159.3 versus plan SDK 0.160.0 | Separate SDK slot: after qualification align source metadata/artifact to TS SDK 0.160.0. This is not host CLI 0.160.1 | currency profile; fixwave-defects generator |
| examples/native-stack-embeddings.service.example:1-2,9; recipes/README.md:114 | Inactive vLLM 0.25.0 template/rollback and dated0.29.0 UVA failure | Legacy inactive/rollback exception, not the current serving default. Label its old qualification scope. Activate a0.31.0 template only after serving qualification; preserve prior failures/rollback | vLLM/embedding template owner via CC |
| adoption/pins-macos-arm64.json:26,43,60,70,86; .github/workflows/hardware-profile-smoke.yml:82-84 | macOS uv 0.12.17,gh 2.101.0,Codex 0.155.1,Claude 2.1.284 | Platform-scope exception outside this Linux decision. macOS promotion needs architecture-specific integrity and acceptance; never reuse Linux hashes | macOS owner via CC; github-ci-finalize workflow |
| blueprints/us-equities/runtime-2604/sync-trading-2604.sh:8 | Project Python 3.12.3 | Separate project interpreter; host 3.13.16 does not qualify its ABI/dependency migration | 5f |

[SDK README:5](https://github.com/seathatflowsinourveins/native-agent-stack/blob/67c6b6f94b456a3a7b5d28bb1fa34625a808d316/adoption/sdk/README.md#L5) records the published exact bundled-CLI requirement; [worker:226-227](https://github.com/seathatflowsinourveins/native-agent-stack/blob/67c6b6f94b456a3a7b5d28bb1fa34625a808d316/examples/omniroute-codex-sdk/worker.py#L226-L227) enforces the qualified pair. Plan Claude 2.1.287/Codex 0.160.0 references at :13, :47, :54 and :96 explicitly allow native self-install/update; they are source-review references, not runtime locks. Review those references while retaining the distinction. Inspect/Scout's active Harbor 0.23.0 package occurrence is an amendment, not a historical exception.

The transfer manifest was read at #776's head8d4f16be8903f313bc96d555cebf4f593a6faf36; it does not declare the four host-toolchain tools. Profile and bootstrap amendments require the native integrity verifier for each changed artifact. The table is an owner handoff, not a new installer or permission to mutate a queued branch.

The trading [installer:84-88](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/blueprints/us-equities/runtime-2604/install-trading-2604.sh#L84-L88) verifies the sync file before sourcing it; its exact uv check at [:112](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/blueprints/us-equities/runtime-2604/install-trading-2604.sh#L112) exits 69 on mismatch. Both edits belong to 5f. Retain the failed 0.12.17 observation as dated evidence.

Harbor's helper does not require a core upgrade:0.23.0 and 0.24.0 have byte-identical export CLI/helper metadata. Use the published harbor-atif2otel 0.1.1 through the native owned-tool dependency route. Export uses `--path`, not a positional path; explicit `--output` avoids the endpoint fallback. Those monitoring amendments stay with their owners and do not qualify the new core release.

## Alternatives and overturn conditions

Keeping the profile and plan as separate active defaults preserves the observed uv-gate failure. Updating only documentary text fails to reconcile actual artifact pins and gates. Changing every project's Python interpreter would broaden a host-toolchain correction into an unqualified project migration. The selected approach names one logical host default and the inventoried operative consumers, with explicit compatibility, historical, inactive and platform-scope exceptions. It includes J805's residual inventory without claiming that unrelated projects/platforms must use the host default.

Reopen a selected default when a newer clean release passes cooldown, integrity and the unchanged upstream/native integration gates for that tool, or when the existing qualification finds a regression. Reopen the consumer split when upstream publishes one maintained pin/install manifest that all consumers can use directly; adopt that format rather than writing another local installer or version resolver.

## Acceptance and evidence

This is the dated decision and owner-amendment map. It does not claim the executable consumers already agree. Completion requires every in-scope host-default consumer to select the table's default, each retained exception to remain explicitly scoped and qualified, the owners' hash/qualification amendments, and passing repository validation. The evidence classes are source review, dated installed-version observation and source-file identity; no new install, provider/GPU run or live configuration application occurred.

The user's paper window defers local `python3 scripts/validate.py` until after 00:10Z; remote CI may review the draft earlier. Keep the PR draft until the command center's cross-family read. Register evidence last, never merge from this lane, and report actual validation results when available.
