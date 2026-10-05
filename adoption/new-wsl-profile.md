# Clean replacement WSL source profile

W-PROF is the source contract in [new-wsl-profile.json](new-wsl-profile.json),
reconciled with accepted main `85543efe5abcddb7b7cddb14e8774e83b6758616`; its Codex CLI and Python SDK pins follow the accepted merge of [PR #626](https://github.com/seathatflowsinourveins/native-agent-stack/pull/626) at main `f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5`. It records source-review
recommendations and isolated comparison arms. It establishes no merit winner,
provider/model/GPU result or replacement-host acceptance.

The RTK and mcporter source rows follow [PR #693](https://github.com/seathatflowsinourveins/native-agent-stack/pull/693), main `14048b840425c2569e0df60a6596e94e601da15b`: **RTK 0.51.0** and **mcporter 0.14.2**. The RTK archive SHA-256 is checked against the [release checksums](https://github.com/rtk-ai/rtk/releases/download/v0.51.0/checksums.txt); the mcporter tarball is rehashed and checked against [npm integrity](https://registry.npmjs.org/mcporter/0.14.2). This source refresh establishes no new host acceptance.

The native manifest profile is `new-wsl-clean-foundation`. Its component list is
only Codex and Claude Code; the existing bootstrap adds its pinned Node, uv and
gh prerequisites. CPython 3.13.15 is supplied through uv without replacing the
OS Python. Git and the OS utilities remain prerequisites. Codex CLI and the
Python SDK pin are **0.160.0**, following the accepted merge of [PR #626](https://github.com/seathatflowsinourveins/native-agent-stack/pull/626); 0.159.3 followed the accepted merge of
[PR #580](https://github.com/seathatflowsinourveins/native-agent-stack/pull/580).
The TypeScript SDK's **0.159.3** pin remains an independent source-review
recommendation; PR #580 did not qualify that SDK. Both SDK rows remain
unprovisioned and outside the default install. The
[takeover snapshot](../evidence/artifacts/new-wsl-profile-20261001/astramax-takeover-baseline.json)
preserves the prior profile and receipt hashes; the earlier PR-open observation
remains historical in the source review, with an appended correction.

Claude Code uses this version rule. The pin is the last qualified release and a
floor; the bootstrap installs the pin and keeps a newer existing install; the receipt records
the installed version; a release newer than the pin counts as installed and not
yet qualified until its acceptance command has passed on that host. The profile's install
command is the documented specific-version form with the pin as its operand, which is the
floor the bootstrap installs. The pinned artifact checksum describes the qualified release;
the receipt records the release actually installed.

The profile adds the step the bootstrap does not perform. Each client moves to the
current release with its own native command, `claude install latest` for Claude Code
and `codex update` for Codex; both appear in the installed clients' help. An updater
that refuses is recorded with its error and the version actually on PATH, and the
client's target acceptance then runs on the version that results. The receipt records,
per client, the floor, the version after the native update and the acceptance result on
that version. A newer release counts as installed and not yet qualified until that
acceptance has passed on that host. The step is **UNRUN**. The anti-pattern log in
[docs/harness-defaults.md](../docs/harness-defaults.md) records that `codex update` did
not establish that a versioned launcher's target had changed, which is why the version
that `PATH` resolves to is read after the update.

This launch adopts stable WSL 3.0.1 or later for a second systemd distribution. The
2.9.8 and 2.9.13 pre-releases carried the fixes first and are not adopted. Their release
notes name [PR 40519](https://github.com/microsoft/WSL/pull/40519), which isolates
distribution cgroups, and [PR 41512](https://github.com/microsoft/WSL/pull/41512), which
creates their namespaces, and the
[3.0.1 release](https://github.com/microsoft/WSL/releases/tag/3.0.1) is the first stable
one with both. An install with a single systemd distribution has its own, lower
install-only minimum, which the recipe page gives. Observations are kept apart from that
policy: the 2026-10-02 rehearsal on 2.7.13 failed on shared cgroups, and the host was
updated to 3.0.1.0 that day.

The gate for two systemd distributions is the recipe's W5 paired record, not a version
check. It takes five observations from both running distributions at once (the uid, the
system state, the failed units, the user manager and the cgroup namespace), applies the
pass rule the page states in W5 and adds the getty mask proof for the new distribution.
It was observed on one host in rehearsals on throwaway distributions, and run 3 of
2026-10-02 passed it
([the record](../evidence/artifacts/new-wsl-rehearsal-20261002/runs-on-wsl-3.0.1.json)).
A rehearsal is not acceptance of the real distribution, so the gate is **UNRUN** for the
real one. The gate is executed in the [new-distribution recipe](platforms/linux-wsl2-new-distro.md).

Each JSON entry has one owning layer. `boundary.layer_uses` preserves other
layers' uses. recovery-portability retains mise's reproduction ownership; uv
supplies the requested Python distribution and package/lock operations. The
minimal bootstrap extracts the pinned official Node archive directly, so its
upstream mise reproduction example adds no default mise dependency.

Comparison positions are display/dependency order. Every arm has
`default_install: false` and `default_precedence: null`. On 2026-10-04 the owner's
decision ([record](../docs/decisions/2026-10-04-token-full-stack-owner-default.md),
amendment 4 of the definitive manifest's rule) made the token-efficiency tools default
installs: RTK and Headroom are no longer comparison arms, ccusage gained its install and
acceptance, and context-mode, jcodemunch-mcp, codebase-memory-mcp, Repomix, TOON,
MarkItDown, Context Hub, otel-tui and agentsview have rows. They install through the
[install plan](../evidence/artifacts/new-wsl-install-plan-20261002/README.md)'s slot rows,
not by iterating over entries; SocratiCode stays an arm of the split code-search slot,
which the plan's interim installs beside semble. The Ubuntu 26.04.1 and
24.04.5 images are symmetric provisional arms. Canonical publishes a separate
checksum for each; the dual-image recipe owner supplies their install/acceptance
steps. The engine comparison precedes container-boundary qualification, and
code retrieval precedes the one embedding-server comparison. Do not install by
iterating over entries. Optional services, hosted workflows, paid services and
task-specific choices remain unprovisioned with reasons. Trading's twelve
layers await their owner's report after October 3.

The 2026-10-04 G4 observability plan repair synchronizes the Collector's **0.162.0**
pin and Grafana OSS **13.2.3**, including the plan's published tar-archive SHA256s.
Their entries now name the staged install and native acceptance commands in the
[install plan](../evidence/artifacts/new-wsl-install-plan-20261002/README.md).
The [G4 decision](../docs/decisions/2026-10-04-2604-e2e-fix-wave-g4-observability.md)
records the native data-directory environment, Grafana provisioning and the alert
receiver's pending user choice. The changed recipes are **UNRUN** on a distribution.
Historical source-review gaps remain in their original receipts. Grafana's
canonical selection remains split; explicit `--only grafana` installs the display
for finalization, pending the coordinator's selection reconciliation.

The generator owner can import `load_profile(root)` from
[scripts/new_wsl_profile.py](../scripts/new_wsl_profile.py), or consume its public
JSON CLI. It returns the original contract and preserves explicit null fields
and blocking gaps. The native manifest's `source_profile` pointer also survives
the existing `scripts/build_ecosystem.py` adapter. This unit does not edit that
generator or the generated handbook.

```sh
rtk python3 scripts/new_wsl_profile.py --json
rtk python3 scripts/adoption_status.py --profile new-wsl-clean-foundation --json
```

A zero exit from the first command validates the contract's structure. The
second reports local executable/recipe prerequisites and the source-review
gap count; `runtime_acceptance_verified` stays false. Run through the pinned
uv Python on a future host whose system interpreter is a different version.
Neither command reads authentication stores or live client configuration.

The native bootstrap at this revision has no supported `--dry-run` option.
It was not executed. Its documented per-step Claude installer supports
`--dry-run --only guard --only agents`; this unit exercises those steps against
a disposable target. No install, account activation or global WSL change is
part of this artifact.

Install and acceptance primary citations are retained per entry in the JSON.
The core paths are [Codex's tagged README](https://github.com/openai/codex/blob/rust-v0.160.0/README.md),
[Claude's version and channel installer](https://code.claude.com/docs/en/setup#install-a-specific-version),
[uv 0.12.17](https://github.com/astral-sh/uv/releases/tag/0.12.17),
[uv's tagged Python guide](https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/install-python.md),
the [Node 24.21.0 distribution](https://nodejs.org/dist/v24.21.0/SHASUMS256.txt),
and [gh's tagged native installation reference](https://github.com/cli/cli/blob/v2.101.0/docs/install_linux.md).
Node/gh's native adapter is the maintained
[bootstrap reference](https://github.com/seathatflowsinourveins/native-agent-stack/blob/20ea4ae23a18565676823b9e3a23541c2100bb39/adoption/bootstrap-linux.sh).

[The source-review record](../evidence/artifacts/new-wsl-profile-20261001/source-review.json)
distinguishes downloaded npm archive hashes, published artifact digests and
Git source identity. It retains failed lookups, rejected artifact candidates,
fact corrections, the red-to-green CLI results and the completeness critic.
Unverified pin-matching install or functional acceptance fields remain null;
version checks never substitute for functional acceptance.

The [first command review](../evidence/artifacts/new-wsl-profile-20261001/upstream-gap-closure.json)
closed ten exact command/merged-PR gaps. At that checkpoint, **51 of 69 entries** retained **128 gaps**,
and all **23 comparison arms** remain isolated. An empty gap list means the
recorded source fields are populated; it establishes no installation,
prerequisite readiness, merit winner or acceptance. The seven reviewed tool
fragments and gh's tagged API example remain **UNRUN**. Codex and the Python
SDK need native authentication and repository context; Claude's example needs
actual function context. QMD's example requires a populated isolated index and
tests BM25 only. RTK's `cargo test`, ai-memory's `cargo t` nextest alias, and
Worktrunk's default `cargo test` are source-test commands: they establish no
daemon, hook, model/backend, shell-integration or replacement-host acceptance.

The Codex npm launcher archive was independently rehashed against npm's SRI;
the Python SDK wheel was rehashed against PyPI's SHA256. Codex's complete native
package and standalone executable retain their distinct GitHub release digests
as published metadata. None was installed. Current host versions differ from
the selected Claude, ai-memory and Worktrunk pins, so their help probes supply
only host-interface observations.

The [core native recipe wave 1](../evidence/artifacts/new-wsl-profile-20261001/core-native-recipe-wave-1.json)
adds source-backed install/test examples for Serena, trafilatura, Playwright CLI,
Claude Agent SDK, Codex TypeScript SDK, Harbor, promptfoo and mise. The current
profile has **45 entries with 117 gaps**, **35 null install-command fields** and
**40 null acceptance-command fields**. Nineteen populated acceptance fields name
source-test commands; none is evidence of an installed functional run. All 69
entries retain their prior provisioning status, and all 23 comparison arms
retain their prior ownership and default-install exclusions.

The Docker Engine and rootless boundary entries now carry the same source-backed
acceptance pair: the daemon's security options report rootless mode, and
`docker run --rm hello-world` exits 0 through the user-level daemon. Docker's
[rootless documentation](https://docs.docker.com/engine/security/rootless/) and
[startup troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/#docker-run-errors)
supply the examples. Both pairs remain **UNRUN** and are owed on the first run
on the new host. The known cgroup risk is recorded in
[microsoft/WSL issue 41492](https://github.com/microsoft/WSL/issues/41492).
The current profile has **38 null acceptance-command fields**. These source
examples establish no new-host result or resource-limit enforcement.

Every added command is **UNRUN**. Serena's local install and source suite require
the exact retained checkout and its Python 3.13 developer environment; PyPI
equivalence remains unresolved. The trafilatura workflow's `--system` operand
belongs to an owned disposable CI environment, and its non-minimal arm has extra
native/dependency setup. Playwright's CI uses Node 20 and its data-URL fixture
needs a working browser runtime. Claude's `tests/` suite excludes its separate
authenticated E2E suite. The Codex TypeScript workflow needs Node 22, pnpm, its
Bazel-built CLI and matching code-mode host staged together, and
`CODEX_EXEC_PATH` pointing to that CLI. Its source tests do not inherit Python
SDK qualification.

Harbor's selected Linux source test requires its upstream developer setup,
including Python 3.13, Docker/Compose and Deno, and excludes the runtime suite.
Its wheel digest is **published PyPI metadata only**; the wheel was not downloaded
or rehashed, and the profile's integrity gap is unchanged. promptfoo's `npm test`
maps to `vitest run`; provider evaluations remain separate. mise requires its
upstream development setup, and the selected E2E regex runs only `test_use`.
The receipt retains the prior mise source-fetch 404 and researcher capacity
retry with the actual backend unknown. This wave preserves the historical
freeze and first command-review files byte for byte.

The following primary citations cover every non-null `install.command` in the
contract. The commands themselves, integrity kind and unresolved fields remain
in the JSON. Inclusion here records a reviewed source; none of these commands
was run. The SDK recommendations remain unprovisioned, and comparison/optional rows
have no default-install precedence.

| Entry | Source pin | Install citation |
|---|---|---|
| Node 24 | 24.21.0 | [reviewed install source](https://github.com/seathatflowsinourveins/native-agent-stack/blob/20ea4ae23a18565676823b9e3a23541c2100bb39/adoption/bootstrap-linux.sh), [upstream reproduction source](https://github.com/jdx/mise/blob/v2026.9.18/docs/cli/install.md), [official distribution integrity](https://nodejs.org/dist/v24.21.0/SHASUMS256.txt) |
| uv | 0.12.17 | [reviewed install source](https://github.com/astral-sh/uv/releases/tag/0.12.17) |
| gh | 2.101.0 | [reviewed install source](https://github.com/seathatflowsinourveins/native-agent-stack/blob/20ea4ae23a18565676823b9e3a23541c2100bb39/adoption/bootstrap-linux.sh), [upstream Linux installation](https://github.com/cli/cli/blob/v2.101.0/docs/install_linux.md) |
| CPython 3.13 | 3.13.15 | [reviewed install source](https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/install-python.md) |
| Codex | 0.160.0 | [reviewed install source](https://github.com/openai/codex/blob/rust-v0.160.0/README.md), [npm version syntax](https://docs.npmjs.com/cli/v11/commands/npm-install) |
| Claude Code | 2.1.284 | [reviewed install source](https://code.claude.com/docs/en/setup#install-a-specific-version) |
| mcporter | 0.14.2 | [reviewed install source](https://github.com/openclaw/mcporter/blob/aa0f55f9bffcde9d2070c86145f37d4dd3525f6c/README.md) |
| MCP Inspector | 2.9.0 | [reviewed install source](https://github.com/modelcontextprotocol/inspector/blob/ae865a19178ddf6f375780a02e9c77c4cf4da184/README.md) |
| sandbox-runtime | 0.0.78 | [reviewed install source](https://github.com/anthropics/sandbox-runtime/blob/v0.0.78/README.md) |
| Worktrunk | 0.80.0 | [exact release installer and shell setup](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0) |
| Serena | c6fbd1c5932df2494ffa0020af5a9fbe80b82143 | [local install from the exact source checkout](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/CONTRIBUTING.md#L70) |
| trafilatura | 2.2.0 | [tagged installation guide](https://github.com/adbar/trafilatura/blob/v2.2.0/docs/installation.rst#L73) |
| Playwright CLI | 0.1.21 | [reviewed install source](https://github.com/microsoft/playwright-cli/blob/74354ecc7a43da16d91a9bc54fa8db8283a3fcf5/README.md) |
| Inspect AI | 0321960a92aa52390413ce011d67ffb5962a2b11 | [reviewed install source](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0321960a92aa52390413ce011d67ffb5962a2b11/README.md) |
| Harbor | 0.23.0 | [reviewed install source](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md) |
| promptfoo | 0.123.1 | [reviewed install source](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/README.md) |
| Claude Agent SDK | 0.2.163 | [reviewed install source](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/README.md) |
| Codex TypeScript SDK | 0.159.3 | [reviewed install source](https://github.com/openai/codex/blob/rust-v0.159.3/sdk/typescript/README.md) |
| Codex Python SDK | 0.160.0 | [reviewed install source](https://github.com/openai/codex/blob/rust-v0.160.0/sdk/python/README.md), [pip version syntax](https://pip.pypa.io/en/stable/cli/pip_install/) |
| QMD | 2.8.3 | [reviewed install source](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md) |
| semble | 0.6.1 | [reviewed install source](https://github.com/MinishLab/semble/blob/24497845460960db1839c8485319df189a889225/README.md) |
| ColGREP | 1.7.0 | [reviewed install source](https://github.com/lightonai/next-plaid/blob/00e26aae0006b322727db277672211d9a0e3ccec/README.md) |
| ripgrep | 15.2.0 | [reviewed install source](https://github.com/BurntSushi/ripgrep/blob/e89fff89ac9af12e8d4ce9d5fd07beb408ca730f/README.md) |
| boxlite | 0.10.5 | [reviewed install source](https://github.com/boxlite-ai/boxlite/blob/4fbf2aeded7520fe77bc724468c831a29684f2cb/README.md) |
| ai-memory | 2.5.2 | [upstream mise example](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L1622), [GitHub backend version syntax](https://mise.jdx.dev/dev-tools/backends/github.html) |
| Hindsight | 0.10.2 | [reviewed install source](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/README.md) |
| agentmemory | 0.9.29 | [reviewed install source](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/README.md) |
| RTK | 0.51.0 | [release asset](https://github.com/rtk-ai/rtk/blob/v0.51.0/README.md#L113) through the [archive procedure](../recipes/README.md#official-release-archives) (0.50.0 until the #693 refresh of 2026-10-04) |
| sqz | 1.9.0 | [reviewed install source](https://github.com/ojuschugh1/sqz/blob/726e77bd7e9d6ae7529e2750da69d86e622ca699/README.md) |
| Headroom | 0.37.0 | [reviewed install source](https://github.com/headroomlabs-ai/headroom/blob/32d7ca4577d599b8a5f811ada74cf31504302c9d/README.md); since 2026-10-04 the [uv tool form](https://github.com/headroomlabs-ai/headroom/blob/v0.37.0/README.md#L92) with the `[mcp]` extra, not `[all]` |
| Phoenix | 20.18.0 | [reviewed install source](https://github.com/Arize-ai/phoenix/blob/d2ad1d916fa8afa21ea218ef7918ef7e4df6ab60/README.md) |
| Dagu | 2.16.6 | [reviewed install source](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/README.md) |
| mise | 2026.9.18 | [tagged installation guide](https://github.com/jdx/mise/blob/v2026.9.18/docs/installing-mise.md), [version normalization in the selected installer source](https://github.com/jdx/mise/blob/v2026.9.18/packaging/standalone/install.envsubst#L300) |
| betterleaks | 1.9.0 | [reviewed install source](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/README.md) |

The inherited review retains the eight public CLI tests' initial red result,
the later 171-test passing suite, the profile status output and the documented
per-step dry run. After reconciliation, the scoped CLI/adoption/profile-table
suite passed **172 tests (exit 0)**. Both public profile/status commands and
`git diff --check` returned exit 0; the profile CLI output matched the source
JSON byte for byte, with runtime/new-host acceptance false. The previous
per-step dry run is reused because the selected installer inputs are unchanged.
The first command review retains these historical checks separately. It deferred
the tracked-script publication check to coordinator staging; the adapter is now
tracked at the wave-1 base. The wave-1 receipt records its own scoped profile
checks. Central validation, registry inventory and regeneration of the book
after integrating the parallel patches remain with their owner.
The wave-1 profile adapter and prerequisite-status commands returned exit 0,
and the existing eight `NewWslProfileCliTests` passed. These are local contract
checks; the upstream install and source-test examples remain unrun.

## G2 runtime-worker plan pin (2026-10-04)

The clean-host install plan keeps its isolated OpenHands SDK/tools/dispatcher at
v1.50.1 (`1e1390acc8788346ba4804c34323284009bf3f5e`), the definitive manifest's
selection and comparison baseline, using constraints exported from the upstream frozen lock; the move to
v1.51.0 is a currency follow-up with its own declared amendment. [The release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.1)
and [the dated G2 decision](../docs/decisions/2026-10-04-2604-e2e-fix-wave-g2-mcp-workers.md)
record the source and acceptance boundary. The architecture's
`cross:runtime-workers` winner now records this SDK plan pin; the separate frozen
1.49.6 container/SWE-bench recipe retains its original pin in the blueprint. This profile has no OpenHands
component entry, so the repair adds no inventory row or shared count.

Inspector already has a 2.9.0 on-demand entry here. Its pinned Web launch,
published-package acceptance and fresh-session checks now live in the install
plan's own row. GPT Researcher v3.7.0 and embedded DeerFlow v2.1.0 retain their
plan pins and now have an active second-gatherer configuration and functional
checks through both native clients. These are unexecuted plan commands; the
coordinator's destination-host E2E must qualify them.


## Syft clean-install pin correction (2026-10-04)

The bounded [verified-E2E fix-wave decision](../docs/decisions/2026-10-04-2604-e2e-fix-wave-g6-eval-supply.md)
moves this profile's Syft row from historical 1.52.0 to the install plan's
**1.54.0**, source `cc326e45a6213360266dda4b30cc68095946d676`. The owned install
is `mise use -g syft@1.54.0`, supported by
[jdx/mise@v2026.10.0:registry/syft.toml:1](https://github.com/jdx/mise/blob/v2026.10.0/registry/syft.toml#L1).
The upstream acceptance is `syft alpine:latest`, from
[anchore/syft@cc326e45a6213360266dda4b30cc68095946d676:README.md:48](https://github.com/anchore/syft/blob/cc326e45a6213360266dda4b30cc68095946d676/README.md#L48).
The Linux archive and its published SHA256 were rehashed in this bounded Linux
job; that observation is separate from the still-UNRUN destination profile.
The historical source-review references and trading receipts are retained.
The row's two source-review command gaps are now filled. Shared aggregate counts
and registry receipts are the coordinator's integration work.
