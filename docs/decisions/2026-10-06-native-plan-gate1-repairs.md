# Gate-1 installation and conformance repairs

These repairs serve reliable foundation acceptance before the north-star research and independently qualified broker paper operation. They follow the co-op's J-713 apply failures, J-MCPCONF direction, and A44/A45 rulings. The co-op remains the sole plan writer on the shared host. This lane changes the reproducible plan and runs isolated qualification; it does not apply the plan, change credentials or land its draft PR.

## Dependency and identity contracts

hcom 0.7.27 prints its identity marker twice during bootstrap. Follow its own first-line parser and base-name grammar instead of combining both markers into a receiver name: [start.rs:840](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/commands/start.rs#L840), [tests/support/mod.rs:949](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/tests/support/mod.rs#L949), [identity.rs:14](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/identity.rs#L14). The send, receiver, unread and client-posture gates remain independent. The isolated native post-install reaches the final missing mapped hcom config.toml gate and exits 1. Quiet install and posture apply remain owed to the co-op after landing.

Use three independent uv environments: Inspect with OpenAI 3.24.0; the unchanged Harbor owner; and Scout 0.5.3 with verified Inspect 0.3.273/Harbor 0.23.0 wheels, LiteLLM 1.92.0 and OpenAI >=2.20,<3. The shared environment is unsatisfiable: [Inspect requirements:12](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/requirements.txt#L12), [Scout dependency:24](https://github.com/meridianlabs-ai/inspect_scout/blob/0e8fc055a3cebba1a14c11bc35856767b6405173/pyproject.toml#L24), [Harbor LiteLLM dependency:20](https://github.com/laude-institute/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/pyproject.toml#L20), [LiteLLM SDK range:19](https://github.com/BerriAI/litellm/blob/b3086ccd74553565c9a39716e72303ae985555f9/pyproject.toml#L19). Follow [uv's isolated tool environments](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/concepts/tools.md#L38), use published wheels with --no-build, retain only recognized Scout alias symlinks, and keep the manifest's historical owner identity. Require the actual Harbor Trajectory import before the unchanged ATIF tests, so importorskip cannot hide a missing modality. All Scout consumers use its own interpreter; selecting Scout cannot reinstall Inspect. Removing Harbor or relaxing its SDK constraint was rejected because it would hide owed coverage or violate upstream requirements. A future release with compatible constraints and the same native tests can overturn this split.

SkillSpector's native Codex provider needs an explicit nonempty model. Read that model from canonical gateway topology and preserve both malicious and safe scan completion gates. Its adapter ignores user configuration and forwards the model; the source does not establish profile or effort forwarding. Therefore this repair makes no gateway-profile or effort qualification claim. The exact native adapter locators are [model resolution:90](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/providers/_agent_cli_base.py#L90) and [Codex argv:319](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/providers/_agent_cli.py#L319). DeerFlow metadata separately follows [landed #744's route](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0fb32ee583589f1a0809b20d18dff40ce2f65a1c/docs/decisions/2026-10-05-omniroute-gateway-composition.md#L36): cx/gpt-6.1-sol-max, supports_reasoning_effort=false and no explicit reasoning_effort field. This is metadata, not delivered wire effort. The keyless DDG custody ruling and every endpoint/provider mismatch negative remain.

## Unchanged conformance tests with bounded lifecycle

The released package supplies its native executable, while a same-name/version source checkout can cause npm to select the local package without its installed bin. Resolve exact-version npx from a neutral directory and disable lifecycle builds: [conformance package.json:13](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/package.json#L13), [npm local-package resolution:49](https://github.com/npm/cli/blob/bfacd33ccbcd908480610703b60455d2da5b57a9/workspaces/libnpmexec/lib/index.js#L49). Keep unchanged npm ci/check/test at the pinned source; the runtime comes from the published package.

All six tagged TypeScript examples expose PORT only. Three explicitly bind 127.0.0.1. The [everything server:2465](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/examples/servers/typescript/everything-server.ts#L2465), [no-caching server:99](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/examples/servers/typescript/sep-2549-no-caching-hints.ts#L99), [MRTR server:168](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/examples/servers/typescript/sep-2322-mrtr-broken-server.ts#L168), and several in-process test mocks omit host. No supported host setting fixes the entire suite. Do not patch upstream files or invent a HOST setting.

Contain the entire unchanged test suite and release CLI in an unprivileged user/PID/private-network namespace with only loopback up. A wildcard bind there is unreachable from the host or LAN. Native [unshare's fork/kill-child contract:81](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/unshare.1.adoc#L81), [unprivileged mapping:118](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/unshare.1.adoc#L118) and [setsid:21](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/setsid.1.adoc#L21) fill the demonstrated lifecycle gap. Source installation and npm check run before private network entry; the full suite and offline release CLI run after it. Keep short owned-cache TMPDIR paths under [Node's Linux IPC limit:46](https://github.com/nodejs/node/blob/v24.21.0/doc/api/net.md#L46).

The acceptance-only helper follows the upstream SDK runner's [TERM then bounded KILL:102](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/src/sdk-runner/index.ts#L102). EXIT/INT/TERM cleanup verifies leader start time, process group and session before each signal. PID namespace closure also removes detached descendants. Require independent absence of owned namespace/group processes and observed run-port listeners. Missing listener observations stay unknown and fail success; coincident foreign host services are recorded separately. Never signal by a command-name pattern. Test failure cleanup signals its exact owned helper and lets that helper perform guarded group teardown.

The external on-demand after target remains unqualified. Exit 78 for a missing target means needs_user; the generic outer exit 0 is not a protocol pass. An owner must supply an in-namespace native SDK startup command or fixture before qualification. Any bridge to an outside host or internet-dependent client needs its own upstream-evidence decision. A45 rejects host-network fallback. An upstream release with complete host binding and correct descendant cleanup can replace this mitigation after the same lifecycle controls pass.

## Evidence and completeness

The first isolated uncontained run passed 524 upstream tests but leaked 18 owned processes, including three wildcard listeners. Its lifecycle failed. The first contained run failed because this lane's long TMPDIR produced a 161-byte Unix IPC path. Both failures and their actual outputs remain private. Short-path contained runs pass all 44 upstream files and 524 tests; the latest actual plan post-install returns 0 with independent zero remaining owned namespace/group processes and run listeners. Scout's three unchanged upstream test files pass 93 tests without skips. These unchanged-upstream results remain separate from local environment, namespace, alias and fixture checks, and from full shared-host or provider acceptance.

Local regression controls cover duplicated/invalid hcom identities, typed canonical model validation and both scan gates, neutral npm resolution, Scout selection/alias preservation/wrong SDK environment, metadata mismatch, detached wildcard servers, command failure, INT, TERM, startup cancellation and missing listener snapshots. The critic's ownership and unknown-observation findings changed the cleanup implementation and fixture teardown. The next lifecycle sweep must retain detached descendants, startup interruption, reused numeric identities, missing observations and outside-target adapters as distinct cases. No new whole cross-family or research allowance was consumed.

## Native SkillSpector corrections

Actual stage reruns exposed three candidate gaps: the installed topology file is absent; the native JSON emits issues instead of findings; and zero-issue safe reports legitimately skip meta-analysis. Read checked-out canonical topology, validate the native field, and require positive integer attempted/succeeded model-call counters with every call successful and no degraded flag. Preserve complete/execution/requested/available gates, malicious issues and a zero-issue safe report. Sources: [report.py:1334](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1334), [meta_analyzer.py:616](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/meta_analyzer.py#L616), [report.py:1124,1173,1240](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1124). The corrected actual whole stage exits0; three earlier native1 attempts remain failures. Native completion is not gateway-profile or delivered-effort qualification. Fixture controls now model the upstream schema, no installed topology, static-only/partial/boolean/degraded counters and the no-meta safe path.

## Atomic landed gateway composition

J-744 adopts the supplied prebuilt composition at the exact deployed prefix, wrapper and shim, and repeats that identity in install and all three acceptance stages. The four directed rows agree: install plan, architecture step, client map and a dated verdict supersession note; original verdict fields are unchanged. Source: [landed decision:31-38](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0fb32ee583589f1a0809b20d18dff40ce2f65a1c/docs/decisions/2026-10-05-omniroute-gateway-composition.md#L31). Package sha256 d3fda90c297ed1ecbaa82ca42298735ce0b393db9a07bad0b4b79efce118ebe2 combines published3.8.51 with upstream PR15167 at0585aba5589d5a1f49243a13a8db249558e7c9e3 and affinity patch045aa81f30cb9a1fc4f6b426ed940c1956cceda2; removal conditions remain PR15167 released and issue8940 fixed. This lane does not rebuild the package or install it on the host. The source wrapper/shim are byte-identical to the supplied artifacts, including the wrapper stale20128 comment and actual21128 execution.

The new render-only service drop-in enables the native OMNIROUTE_SHOW_LOG flag: [processSupervisor.mjs:77,89-106](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/bin/cli/runtime/processSupervisor.mjs#L77). Alias follows the deployed prefix; client map/topology select explicit Sol max, standalone search stays held out, and the Claude route remains owner-pending. Host Astra/max/live drift belongs to the command center. Unknown assets and symlinks remain needs_owner; only exact known previous plan bytes may migrate. Loaded service identity must precede native client acceptance. Co-op readback artifacts remain historical INTEGRATION evidence: original header/effort checks false and one exact-joined Sol-max row, not native-profile qualification. Tarball rehash/archive inspection and repository fixtures are source/artifact/local integration checks; no new live wire-effort acceptance follows. A future clean upstream release satisfying the two removal conditions and the same lifecycle/profile checks can replace the composition.

The directed verdict supersession note changes the file byte digest while every original field remains equal. Refresh only consensus.wave5.records.round2_extract.sha256 for the current note-bearing file; retain the original44ac761 digest in the gate-1 receipt. Regenerate the definitive manifest and handbook through the maintained [assembler](https://github.com/seathatflowsinourveins/native-agent-stack/blob/44ac761b9b0542cb75f9b7529d223c0ef4d40b35/evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py#L199) and [handbook render](https://github.com/seathatflowsinourveins/native-agent-stack/blob/44ac761b9b0542cb75f9b7529d223c0ef4d40b35/scripts/build_new_wsl_handbook.py#L1203). No historical verdict or test oracle is weakened. The corrected final444-test suite passes with3 existing skips; stale-binding, bytecode and interrupted attempts remain distinct failures or unknown outcomes.

## Addendum (2026-10-06): rebased verdict corrections and current apply

The original decision text and recorded observations above remain unchanged. This addendum supersedes its quiet/posture apply, citation and evidence-class wording after landed #771 and the exact-head verdict. Current source repairs and the owner-custody runbook follow; no prior native result is rewritten.


These repairs serve reliable foundation acceptance before the north-star research and independently qualified broker paper operation. They follow the co-op's J-713 apply failures, J-MCPCONF direction, and A44/A45 rulings. The co-op remains the sole plan writer on the shared host. This lane changes the reproducible plan and runs isolated qualification; it does not apply the plan, change credentials or land its draft PR.

## Dependency and identity contracts

hcom 0.7.27 prints its identity marker twice during bootstrap. Follow its own first-line parser and base-name grammar instead of combining both markers into a receiver name: [start.rs:840](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/commands/start.rs#L840), [tests/support/mod.rs:949](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/tests/support/mod.rs#L949), [identity.rs:14](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/identity.rs#L14). The send, receiver and unread gates remain independent. The earlier isolated attempt at the pre-relaxation head reached the final missing mapped hcom config.toml gate and exited 1; that retained failure is historical. Landed #771 (e28d0eec) supplies the relaxed operational adapter and native after-sign-in rules smoke. The co-op applies the verified vendor installer and the relaxed mapped configuration after landing; no custom deny list or quiet posture is reapplied.

Use three independent uv environments: Inspect with OpenAI 3.24.0; the unchanged Harbor owner; and Scout 0.5.3 with verified Inspect 0.3.273/Harbor 0.23.0 wheels, LiteLLM 1.92.0 and OpenAI >=2.20,<3. The shared environment is unsatisfiable: [Inspect requirements:12](https://github.com/UKGovernmentBEIS/inspect_ai/blob/9e44f1b77ed7c912bf58baf30db8560937e7ce53/requirements.txt#L12), [Scout dependency:24](https://github.com/meridianlabs-ai/inspect_scout/blob/0e8fc055a3cebba1a14c11bc35856767b6405173/pyproject.toml#L24), [Harbor LiteLLM dependency:20](https://github.com/laude-institute/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/pyproject.toml#L20), [LiteLLM SDK range:19](https://github.com/BerriAI/litellm/blob/b3086ccd74553565c9a39716e72303ae985555f9/pyproject.toml#L19). Follow [uv's isolated tool environments](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/concepts/tools.md#L38), use published wheels with --no-build, retain only recognized Scout alias symlinks, and keep the manifest's historical owner identity. Require the actual Harbor Trajectory import before the unchanged ATIF tests, so importorskip cannot hide a missing modality. All Scout consumers use its own interpreter; selecting Scout cannot reinstall Inspect. Removing Harbor or relaxing its SDK constraint was rejected because it would hide owed coverage or violate upstream requirements. A future release with compatible constraints and the same native tests can overturn this split.

SkillSpector's native Codex provider needs an explicit nonempty model. Read that model from canonical gateway topology and preserve both malicious and safe scan completion gates. Its adapter ignores user configuration and forwards the model; the source does not establish profile or effort forwarding. Therefore this repair makes no gateway-profile or effort qualification claim. The exact native adapter locators are [model resolution:90](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/providers/_agent_cli_base.py#L90) and [Codex argv:319](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/providers/_agent_cli.py#L319). DeerFlow's cx/gpt-6.1-sol-max suffix choice follows [landed #744's route](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0fb32ee583589f1a0809b20d18dff40ce2f65a1c/docs/decisions/2026-10-05-omniroute-gateway-composition.md#L36). The false supports_reasoning_effort flag and omitted reasoning_effort are derived plan configuration choices through [DeerFlow v2.1.0's explicit false configuration](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L225); #744 does not mention DeerFlow. This is metadata, not delivered wire effort. The keyless DDG custody ruling and every endpoint/provider mismatch negative remain.

## Unchanged conformance tests with bounded lifecycle

The released package supplies its native executable, while a same-name/version source checkout can cause npm to select the local package without its installed bin. Resolve exact-version npx from a neutral directory and disable lifecycle builds: [conformance package.json:13](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/package.json#L13), [npm local-package resolution:49](https://github.com/npm/cli/blob/bfacd33ccbcd908480610703b60455d2da5b57a9/workspaces/libnpmexec/lib/index.js#L49). Keep unchanged npm ci/check/test at the pinned source; the runtime comes from the published package.

All six tagged TypeScript examples expose PORT only. Three explicitly bind 127.0.0.1. The [everything server:2465](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/examples/servers/typescript/everything-server.ts#L2465), [no-caching server:99](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/examples/servers/typescript/sep-2549-no-caching-hints.ts#L99), [MRTR server:168](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/examples/servers/typescript/sep-2322-mrtr-broken-server.ts#L168), and several in-process test mocks omit host. No supported host setting fixes the entire suite. Do not patch upstream files or invent a HOST setting.

Contain the entire unchanged test suite and release CLI in an unprivileged user/PID/private-network namespace with only loopback up. A wildcard bind there is unreachable from the host or LAN. Native [unshare's fork/kill-child contract:81](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/unshare.1.adoc#L81), [unprivileged mapping:118](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/unshare.1.adoc#L118) and [setsid:21](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/setsid.1.adoc#L21) fill the demonstrated lifecycle gap. Source installation and npm check run before private network entry; the full suite and offline release CLI run after it. Keep short owned-cache TMPDIR paths under [Node's Linux IPC limit:46](https://github.com/nodejs/node/blob/v24.21.0/doc/api/net.md#L46).

The acceptance-only helper follows the upstream SDK runner's [TERM then bounded KILL:102](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/src/sdk-runner/index.ts#L102). EXIT/INT/TERM cleanup verifies leader start time, process group and session before each signal. PID namespace closure also removes detached descendants. Require the helper's absence gates for owned namespace/group processes and observed run-port listeners. These gates are helper-derived local integration, not an independent observer receipt. Missing listener observations stay unknown and fail success; coincident foreign host services are recorded separately. Never signal by a command-name pattern. Test failure cleanup signals its exact owned helper and lets that helper perform guarded group teardown.

The external on-demand after target remains unqualified. Exit 78 for a missing target means needs_user; the generic outer exit 0 is not a protocol pass. An owner must supply an in-namespace native SDK startup command or fixture before qualification. Any bridge to an outside host or internet-dependent client needs its own upstream-evidence decision. A45 rejects host-network fallback. An upstream release with complete host binding and correct descendant cleanup can replace this mitigation after the same lifecycle controls pass.

## Evidence and completeness

The first isolated uncontained run passed 524 upstream tests but leaked 18 owned processes, including three wildcard listeners. Its lifecycle failed. The first contained run failed because this lane's long TMPDIR produced a 161-byte Unix IPC path. Both failures and their actual outputs remain private. Short-path contained runs pass all 44 upstream files and 524 tests; the latest actual plan post-install returns 0 with helper-derived zero remaining owned namespace/group processes and run listeners (LOCAL INTEGRATION observation). Scout's three unchanged upstream test files pass 93 tests without skips. These unchanged-upstream results remain separate from local environment, namespace, alias and fixture checks, and from full shared-host or provider acceptance.

Local regression controls cover duplicated/invalid hcom identities, typed canonical model validation and both scan gates, neutral npm resolution, Scout selection/alias preservation/wrong SDK environment, metadata mismatch, detached wildcard servers, command failure, INT, TERM, startup cancellation and missing listener snapshots. The critic's ownership and unknown-observation findings changed the cleanup implementation and fixture teardown. The next lifecycle sweep must retain detached descendants, startup interruption, reused numeric identities, missing observations and outside-target adapters as distinct cases. No new whole cross-family or research allowance was consumed.

## Native SkillSpector corrections

Actual stage reruns exposed three candidate gaps: the installed topology file is absent; the native JSON emits issues instead of findings; and zero-issue safe reports legitimately skip meta-analysis. Read checked-out canonical topology, validate the native field, and require positive integer attempted/succeeded model-call counters with every call successful and no degraded flag. Preserve complete/execution/requested/available gates, malicious issues and a zero-issue safe report. Sources: [report.py:1334](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1334), [meta_analyzer.py:616](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/meta_analyzer.py#L616), [report.py:1124,1173,1240](https://github.com/NVIDIA/skillspector/blob/c7958a3268d9498644b22edb75d0f051bbc8cbfc/src/skillspector/nodes/report.py#L1124). The corrected actual whole stage exits0; three earlier native1 attempts remain failures. Native completion is not gateway-profile or delivered-effort qualification. Fixture controls now model the upstream schema, no installed topology, static-only/partial/boolean/degraded counters and the no-meta safe path.

## Atomic landed gateway composition

J-744 adopts the supplied prebuilt composition at the exact deployed prefix, wrapper and shim, and repeats that identity in install and all three acceptance stages. The four directed rows agree: install plan, architecture step, client map and a dated verdict supersession note; original verdict fields are unchanged. Source: [landed decision:31-38](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0fb32ee583589f1a0809b20d18dff40ce2f65a1c/docs/decisions/2026-10-05-omniroute-gateway-composition.md#L31). Package sha256 d3fda90c297ed1ecbaa82ca42298735ce0b393db9a07bad0b4b79efce118ebe2 combines published3.8.51 with upstream PR15167 at0585aba5589d5a1f49243a13a8db249558e7c9e3 and affinity patch045aa81f30cb9a1fc4f6b426ed940c1956cceda2; removal conditions remain PR15167 released and [issue #8939](https://github.com/diegosouzapw/OmniRoute/issues/8939) fixed through [PR #8940](https://github.com/diegosouzapw/OmniRoute/pull/8940), with the pinned affinity patch's regression test passing. PR #8940 is not an issue number. This lane does not rebuild the package or install it on the host. The source wrapper/shim are byte-identical to the supplied artifacts, including the wrapper stale20128 comment and actual21128 execution.

The new render-only service drop-in enables the native OMNIROUTE_SHOW_LOG flag: [processSupervisor.mjs:77,89-106](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/bin/cli/runtime/processSupervisor.mjs#L77). Alias follows the deployed prefix; client map/topology select explicit Sol max, standalone search stays held out, and the Claude route remains owner-pending. Host Astra/max/live drift belongs to the command center. Unknown assets and symlinks remain needs_owner; only exact known previous plan bytes may migrate. Loaded service identity must precede native client acceptance. Co-op readback artifacts remain historical INTEGRATION evidence: original header/effort checks false and one exact-joined Sol-max row, not native-profile qualification. Tarball rehash/archive inspection and repository fixtures are source/artifact/local integration checks; no new live wire-effort acceptance follows. A future clean upstream release satisfying the two removal conditions and the same lifecycle/profile checks can replace the composition.

The directed verdict supersession note changes the file byte digest while every original field remains equal. Refresh only consensus.wave5.records.round2_extract.sha256 for the current note-bearing file; retain the original44ac761 digest in the gate-1 receipt. Regenerate the definitive manifest and handbook through the maintained [assembler](https://github.com/seathatflowsinourveins/native-agent-stack/blob/44ac761b9b0542cb75f9b7529d223c0ef4d40b35/evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py#L199) and [handbook render](https://github.com/seathatflowsinourveins/native-agent-stack/blob/44ac761b9b0542cb75f9b7529d223c0ef4d40b35/scripts/build_new_wsl_handbook.py#L1203). No historical verdict or test oracle is weakened. The corrected final444-test suite passes with3 existing skips; stale-binding, bytecode and interrupted attempts remain distinct failures or unknown outcomes.


## After-landing gateway custody on NativeStack2604

Required P2-6 uses the explicit owner-custody alternative. No earlier live digest is guessed or added to the installer's known set. This is an UNRUN co-op apply recipe after the approved source lands, outside the paper windows and at a quiet point on 21128. A lane runs no host command here. The installer continues to reject unknown unit/helper/topology/wrapper/drop-in bytes. A regular differing `omniroute.env.example` is retained by the existing [copy_config contract at 84c79f7f:82-126](https://github.com/seathatflowsinourveins/native-agent-stack/blob/84c79f7f92f61972a46aa470a4f299017bc82768/evidence/artifacts/new-wsl-install-plan-20261002/install.sh#L82); a symlink or nonregular example fails before any installation.

The co-op supplies `GATEWAY_APPROVED_HEAD` from the command center's landed-head approval. It first records custody of each differing **non-secret plan asset**, including the co-op's earlier stand-in unit and `10-show-log.conf`. An unclassified file, unexpected symlink or extra drop-in is `needs_owner`; preserve it and stop. Never back up, read or copy `omniroute.env`, a credential store, the gateway database or client sign-in files. The example file is left in place. Neither the previous gateway prefix nor its data is removed.

Start one owner shell with strict failure handling and a private durable packet:

```bash
set -euo pipefail
umask 077
: "${GATEWAY_APPROVED_HEAD:?set the exact landed head approved for this apply}"
gateway_checkout="$HOME/code/native-agent-stack"
[[ "$(git -C "$gateway_checkout" rev-parse HEAD)" == "$GATEWAY_APPROVED_HEAD" ]]
gateway_plan_dir="$gateway_checkout/evidence/artifacts/new-wsl-install-plan-20261002"
gateway_config_root="$HOME/.config/new-wsl-native-stack"
gateway_prefix="$HOME/.local/share/omniroute-builds/omniroute-3.8.51-5f4b3d577-affinity-pr15167"
gateway_packet="$HOME/.local/state/native-agent-stack/coordination/ns2604-coop/gateway-reapply-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 -- "$gateway_packet/files"
printf '%s\n' "$GATEWAY_APPROVED_HEAD" > "$gateway_packet/approved-head"
printf '%s\n' "$gateway_prefix" > "$gateway_packet/candidate-prefix"
if systemctl --user is-active --quiet omniroute.service; then
  printf 'active\n' > "$gateway_packet/prior-state"
else
  printf 'inactive\n' > "$gateway_packet/prior-state"
fi
systemctl --user show omniroute.service -p ExecStart -p FragmentPath -p DropInPaths \
  > "$gateway_packet/prior-layout"
```

The owner records its custody decision in `custody-approved.txt` in that packet **before** copying. It names every differing path and any extra drop-in, and confirms that each backed-up asset is non-secret. Record the previous prefix from the prior `ExecStart` and alias in that decision; keep that prefix for rollback. Do not infer ownership from a filename or digest. Check all loaded user units' keyed `NeedDaemonReload` values before staging. If any is `yes`, return `needs_owner` without reloading; the paper owner settles its pending changes first.

```bash
systemctl --user list-units --all --plain --no-legend --no-pager \
  > "$gateway_packet/units-before"
while read -r gateway_unit _; do
  systemctl --user show "$gateway_unit" -p Id -p NeedDaemonReload
done < "$gateway_packet/units-before" > "$gateway_packet/reload-before"
if grep -q '^NeedDaemonReload=yes$' "$gateway_packet/reload-before"; then
  printf 'needs_owner: pending user-unit reload; no gateway apply.\n' >&2
  exit 1
fi
[[ -s "$gateway_packet/custody-approved.txt" ]]
: > "$gateway_packet/paths.tsv"
: > "$gateway_packet/backup-assets.sha256"
for gateway_asset in gpt-gateway-topology.json gpt-gateway-client-accept.sh \
  omniroute.service omniroute-serve.sh omniroute-lsof-shim-v2.sh \
  omniroute.service.d/10-show-log.conf; do
  printf '%s\n' "$gateway_config_root/$gateway_asset"
done > "$gateway_packet/paths"
printf '%s\n' "$HOME/.config/systemd/user/omniroute.service" \
  "$HOME/.config/systemd/user/omniroute.service.d/10-show-log.conf" \
  "$gateway_prefix/omniroute-serve.sh" "$gateway_prefix/shim/lsof" \
  "$HOME/.local/bin/omniroute" >> "$gateway_packet/paths"
while IFS= read -r gateway_path; do
  if [[ -e "$gateway_path" || -L "$gateway_path" ]]; then
    cp -a --parents -- "$gateway_path" "$gateway_packet/files/"
    if [[ -f "$gateway_path" && ! -L "$gateway_path" ]]; then
      sha256sum "$gateway_packet/files$gateway_path" >> "$gateway_packet/backup-assets.sha256"
    fi
    printf 'present\t%s\n' "$gateway_path" >> "$gateway_packet/paths.tsv"
  else
    printf 'absent\t%s\n' "$gateway_path" >> "$gateway_packet/paths.tsv"
  fi
done < "$gateway_packet/paths"
# Preserve every owner-approved drop-in as a tree; do not remove it automatically.
if [[ -d "$HOME/.config/systemd/user/omniroute.service.d" && \
      ! -L "$HOME/.config/systemd/user/omniroute.service.d" ]]; then
  cp -a --parents -- "$HOME/.config/systemd/user/omniroute.service.d" "$gateway_packet/files/"
fi
sha256sum "$gateway_packet/approved-head" "$gateway_packet/paths.tsv" \
  "$gateway_packet/custody-approved.txt" "$gateway_packet/prior-state" \
  "$gateway_packet/prior-layout" "$gateway_packet/backup-assets.sha256" > "$gateway_packet/packet.sha256"
```

Before proceeding, the co-op compares each copied regular file with its original using `cmp -s`, and each saved symlink's `readlink` with the original. Record those rc values and each non-secret asset's actual sha256. For the saved drop-in tree, compare every owner-approved file; an extra unclassified file stops the apply. This measures actual bytes and grants no new automatic ownership. The backup remains even if the apply fails.

Stage only the approved repository assets below. Existing destination assets must be regular non-symlink files or absent; otherwise stop. Unexpected drop-ins remain preserved and `needs_owner` until their owner gives an explicit retirement/adoption decision. The ordinary installer keeps its unknown-byte refusal; owner staging makes the recognized destinations exactly the landed plan bytes first.

```bash
# Check every destination directory before the first staging write.
for gateway_dir in "$gateway_config_root" "$gateway_config_root/omniroute.service.d" \
  "$HOME/.config/systemd/user" "$HOME/.config/systemd/user/omniroute.service.d" \
  "$gateway_prefix" "$gateway_prefix/shim"; do
  [[ ! -L "$gateway_dir" && ( ! -e "$gateway_dir" || -d "$gateway_dir" ) ]]
done
[[ -d "$gateway_prefix" ]]
# The custodian verifies all listed non-alias assets are regular or absent first.
while IFS= read -r gateway_path; do
  [[ "$gateway_path" == "$HOME/.local/bin/omniroute" ]] && continue
  [[ ! -L "$gateway_path" && ( ! -e "$gateway_path" || -f "$gateway_path" ) ]]
done < "$gateway_packet/paths"
for gateway_asset in gpt-gateway-topology.json gpt-gateway-client-accept.sh \
  omniroute.service omniroute-serve.sh omniroute-lsof-shim-v2.sh \
  omniroute.service.d/10-show-log.conf; do
  gateway_target="$gateway_config_root/$gateway_asset"
  [[ ! -L "$gateway_target" && ( ! -e "$gateway_target" || -f "$gateway_target" ) ]]
  install -d -m 0700 -- "$(dirname -- "$gateway_target")"
  install -m 0600 -- "$gateway_plan_dir/config/$gateway_asset" "$gateway_target"
done
for gateway_asset in omniroute.service omniroute.service.d/10-show-log.conf; do
  gateway_target="$HOME/.config/systemd/user/$gateway_asset"
  [[ ! -L "$gateway_target" && ( ! -e "$gateway_target" || -f "$gateway_target" ) ]]
  install -d -m 0700 -- "$(dirname -- "$gateway_target")"
  install -m 0600 -- "$gateway_plan_dir/config/$gateway_asset" "$gateway_target"
done
[[ -d "$gateway_prefix" && ! -L "$gateway_prefix" ]]
[[ ! -L "$gateway_prefix/omniroute-serve.sh" && ! -L "$gateway_prefix/shim/lsof" ]]
install -d -m 0700 -- "$gateway_prefix/shim"
install -m 0755 -- "$gateway_plan_dir/config/omniroute-serve.sh" "$gateway_prefix/omniroute-serve.sh"
install -m 0755 -- "$gateway_plan_dir/config/omniroute-lsof-shim-v2.sh" "$gateway_prefix/shim/lsof"
```

Repeat the keyed reload census immediately before the installer. Only `omniroute.service` may now need a reload from this owner's staged changes; any other pending unit or paper drop-in stops the apply. Outside the paper window, run the existing plan installer and its native reload, then restart just the gateway unit. Sources: [systemd@v259 reload:1317-1327](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L1317) and [restart:421-433](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L421). No manager re-execution is used.

```bash
systemctl --user list-units --all --plain --no-legend --no-pager \
  > "$gateway_packet/units-before-install"
while read -r gateway_unit _; do
  [[ "$gateway_unit" == omniroute.service ]] && continue
  systemctl --user show "$gateway_unit" -p Id -p NeedDaemonReload
done < "$gateway_packet/units-before-install" > "$gateway_packet/reload-before-install"
if grep -q '^NeedDaemonReload=yes$' "$gateway_packet/reload-before-install"; then
  printf 'needs_owner: another unit/drop-in needs reload; gateway not restarted.\n' >&2
  exit 1
fi
# The installer performs daemon-reload after this owner gate.
nice -n 19 bash "$gateway_plan_dir/install.sh" --only gpt-gateway
systemctl --user restart omniroute.service
systemctl --user is-active --quiet omniroute.service
systemctl --user show omniroute.service -p ActiveState -p SubState -p ExecStart \
  -p FragmentPath -p DropInPaths -p NeedDaemonReload > "$gateway_packet/readback"
readlink -f -- "$HOME/.local/bin/omniroute" > "$gateway_packet/alias-readback"
for gateway_stage in post_install service_health after_sign_in; do
  if nice -n 19 bash "$gateway_plan_dir/accept.sh" --only gpt-gateway \
    --stage "$gateway_stage" </dev/null > "$gateway_packet/$gateway_stage.out" \
    2> "$gateway_packet/$gateway_stage.err"; then
    printf '0\n' > "$gateway_packet/$gateway_stage.rc"
  else
    gateway_rc=$?
    printf '%s\n' "$gateway_rc" > "$gateway_packet/$gateway_stage.rc"
    exit "$gateway_rc"
  fi
done
```

Record each argv and rc separately. Require the wrapper/prefix and shim identities, exactly the intended drop-ins, `NeedDaemonReload=no`, active/running service, alias to the candidate prefix and each existing native acceptance gate. Keep every failed attempt. These owner read-backs are integration evidence; they do not supply a new native-profile or delivered-wire-effort qualification.

Rollback runs in a fresh strict shell using the exact packet path reported by the co-op, not variables left in the apply shell. Before restoring, verify `packet.sha256`, the saved-byte comparisons, and that every current destination is still the approved staged asset or the recorded alias. A foreign concurrent change is `needs_owner` and remains untouched. The owner then restores recorded present paths byte-for-byte and removes **only** recorded absent paths that this apply created; empty parent directories, the candidate prefix, previous prefix, gateway data and credentials remain.

```bash
set -euo pipefail
umask 077
: "${GATEWAY_CUSTODY_PACKET:?set the exact durable packet recorded for this apply}"
[[ -d "$GATEWAY_CUSTODY_PACKET" && ! -L "$GATEWAY_CUSTODY_PACKET" ]]
sha256sum --check --status "$GATEWAY_CUSTODY_PACKET/packet.sha256"
sha256sum --check --status "$GATEWAY_CUSTODY_PACKET/backup-assets.sha256"
# Owner completes the current-byte and pending-other-unit reload gates above first.
systemctl --user stop omniroute.service
while IFS=$'\t' read -r gateway_presence gateway_path; do
  case "$gateway_presence" in
    present) cp -a --remove-destination -- \
      "$GATEWAY_CUSTODY_PACKET/files$gateway_path" "$gateway_path" ;;
    absent) [[ ! -d "$gateway_path" ]] && rm -f -- "$gateway_path" ;;
    *) printf 'needs_owner: invalid custody manifest.\n' >&2; exit 1 ;;
  esac
done < "$GATEWAY_CUSTODY_PACKET/paths.tsv"
systemctl --user daemon-reload
systemctl --user reset-failed omniroute.service
if [[ "$(cat "$GATEWAY_CUSTODY_PACKET/prior-state")" == active ]]; then
  systemctl --user start omniroute.service
  systemctl --user is-active --quiet omniroute.service
fi
systemctl --user show omniroute.service -p ActiveState -p ExecStart -p DropInPaths \
  -p NeedDaemonReload > "$GATEWAY_CUSTODY_PACKET/rollback-readback"
```

Compare restored files/symlinks and the effective previous prefix/drop-ins with the saved prior layout. A rollback is complete only after that read-back; restoring a symlink alone is not a service rollback. Preserve the packet and both prefixes for the command center's review.

## Addendum (2026-10-06): exact-head J723 delta

The exact-head review found a stale handbook publication binding, permissive Promptfoo URL validation, and gateway checks that could pass before the running process loaded the rendered drop-in. The bounded repair keeps the maintained receipt guard's exact assertions, retains the former output bindings, validates the parsed loopback hostname and recorded port, and classifies the explicitly pending Claude route as needs_owner/78 before loading the evaluator config. Malformed supplied routes still fail; no Claude route is invented.

Both gateway stages now require the keyed, microsecond UTC ActiveEnterTimestamp to be strictly later than the unit and drop-in mtimes, preserving all identity, health and client-result gates. Research clones also assert the official GPT Researcher and DeerFlow tag commits. Sources and pins are in the J723 section of the install plan's SOURCES.md. Synthetic URL, pending-owner and stale-process controls are local integration evidence; host re-apply and delivered provider behavior remain owed to the command center.

The command center's J723b ruling withdraws restoration of the unlanded A50 draft amendment. Its observed native-messaging smoke receipt is retained byte-identically in private lane state, mode0600, with its digest disclosed in the PR body. #771 governs the relaxed operational posture. No retired policy or enforcement test is restored.

The J723c CI repair reads nested configuration files recursively while skipping directories, retains exact port and script-inventory assertions, and explicitly lists the frozen Inspector probe. The AgentsView repin registry classifies predecessor launcher fixtures as dated inputs, preserving their versions and all original search observations. Review and worker commands use native Git/Python/env directly; optional normalization of historical RTK-shaped events remains. These changes repair the CI contract without adding a skip or weakening the completion, bus-binding or migration predicates. Source references are appended to the J723 section of SOURCES.md.
