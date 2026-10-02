# Clean replacement WSL source profile

W-PROF is the source contract in [new-wsl-profile.json](new-wsl-profile.json),
reconciled with accepted main `85543efe5abcddb7b7cddb14e8774e83b6758616`. It records source-review
recommendations and isolated comparison arms. It establishes no merit winner,
provider/model/GPU result or replacement-host acceptance.

The native manifest profile is `new-wsl-clean-foundation`. Its component list is
only Codex and Claude Code; the existing bootstrap adds its pinned Node, uv and
gh prerequisites. CPython 3.13.15 is supplied through uv without replacing the
OS Python. Git and the OS utilities remain prerequisites. Codex CLI and the
Python SDK pin are **0.159.3**, following the accepted merge of
[PR #580](https://github.com/seathatflowsinourveins/native-agent-stack/pull/580).
The TypeScript SDK's **0.159.3** pin remains an independent source-review
recommendation; PR #580 did not qualify that SDK. Both SDK rows remain
unprovisioned and outside the default install. The
[takeover snapshot](../evidence/artifacts/new-wsl-profile-20261001/astramax-takeover-baseline.json)
preserves the prior profile and receipt hashes; the earlier PR-open observation
remains historical in the source review, with an appended correction.

Each JSON entry has one owning layer. `boundary.layer_uses` preserves other
layers' uses. recovery-portability retains mise's reproduction ownership; uv
supplies the requested Python distribution and package/lock operations. The
minimal bootstrap extracts the pinned official Node archive directly, so its
upstream mise reproduction example adds no default mise dependency.

Comparison positions are display/dependency order. Every arm has
`default_install: false` and `default_precedence: null`. The Ubuntu 26.04.1 and
24.04.5 images are symmetric provisional arms. Canonical publishes a separate
checksum for each; the dual-image recipe owner supplies their install/acceptance
steps. The engine comparison precedes container-boundary qualification, and
code retrieval precedes the one embedding-server comparison. Do not install by
iterating over entries. Optional services, hosted workflows, paid services and
task-specific choices remain unprovisioned with reasons. Trading's twelve
layers await their owner's report after October 3.

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
The core paths are [Codex's tagged README](https://github.com/openai/codex/blob/rust-v0.159.3/README.md),
[Claude's specific-version installer](https://code.claude.com/docs/en/setup#install-a-specific-version),
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
| Codex | 0.159.3 | [reviewed install source](https://github.com/openai/codex/blob/rust-v0.159.3/README.md), [npm version syntax](https://docs.npmjs.com/cli/v11/commands/npm-install) |
| Claude Code | 2.1.284 | [reviewed install source](https://code.claude.com/docs/en/setup#install-a-specific-version) |
| mcporter | 0.14.1 | [reviewed install source](https://github.com/openclaw/mcporter/blob/93e0916cafe2d624b94271e31b75ca681a016514/README.md) |
| MCP Inspector | 2.9.0 | [reviewed install source](https://github.com/modelcontextprotocol/inspector/blob/ae865a19178ddf6f375780a02e9c77c4cf4da184/README.md) |
| sandbox-runtime | 0.0.77 | [reviewed install source](https://github.com/anthropics/sandbox-runtime/blob/6fa731368807419ee157f9a3fac955fefe1019c6/README.md) |
| Worktrunk | 0.80.0 | [exact release installer and shell setup](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0) |
| Serena | c6fbd1c5932df2494ffa0020af5a9fbe80b82143 | [local install from the exact source checkout](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/CONTRIBUTING.md#L70) |
| trafilatura | 2.2.0 | [tagged installation guide](https://github.com/adbar/trafilatura/blob/v2.2.0/docs/installation.rst#L73) |
| Playwright CLI | 0.1.21 | [reviewed install source](https://github.com/microsoft/playwright-cli/blob/74354ecc7a43da16d91a9bc54fa8db8283a3fcf5/README.md) |
| Inspect AI | 0321960a92aa52390413ce011d67ffb5962a2b11 | [reviewed install source](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0321960a92aa52390413ce011d67ffb5962a2b11/README.md) |
| Harbor | 0.23.0 | [reviewed install source](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md) |
| promptfoo | 0.123.1 | [reviewed install source](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/README.md) |
| Claude Agent SDK | 0.2.163 | [reviewed install source](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/README.md) |
| Codex TypeScript SDK | 0.159.3 | [reviewed install source](https://github.com/openai/codex/blob/rust-v0.159.3/sdk/typescript/README.md) |
| Codex Python SDK | 0.159.3 | [reviewed install source](https://github.com/openai/codex/blob/rust-v0.159.3/sdk/python/README.md), [pip version syntax](https://pip.pypa.io/en/stable/cli/pip_install/) |
| QMD | 2.8.3 | [reviewed install source](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md) |
| semble | 0.6.1 | [reviewed install source](https://github.com/MinishLab/semble/blob/24497845460960db1839c8485319df189a889225/README.md) |
| ColGREP | 1.7.0 | [reviewed install source](https://github.com/lightonai/next-plaid/blob/00e26aae0006b322727db277672211d9a0e3ccec/README.md) |
| ripgrep | 15.2.0 | [reviewed install source](https://github.com/BurntSushi/ripgrep/blob/e89fff89ac9af12e8d4ce9d5fd07beb408ca730f/README.md) |
| boxlite | 0.10.5 | [reviewed install source](https://github.com/boxlite-ai/boxlite/blob/4fbf2aeded7520fe77bc724468c831a29684f2cb/README.md) |
| ai-memory | 2.5.2 | [upstream mise example](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/install.md#L1622), [GitHub backend version syntax](https://mise.jdx.dev/dev-tools/backends/github.html) |
| Hindsight | 0.10.2 | [reviewed install source](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/README.md) |
| agentmemory | 0.9.29 | [reviewed install source](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/README.md) |
| RTK | 0.50.0 | [upstream Git install](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/README.md#L106), [Cargo tag/lock syntax](https://doc.rust-lang.org/cargo/commands/cargo-install.html) |
| sqz | 1.9.0 | [reviewed install source](https://github.com/ojuschugh1/sqz/blob/726e77bd7e9d6ae7529e2750da69d86e622ca699/README.md) |
| Headroom | 0.37.0 | [reviewed install source](https://github.com/headroomlabs-ai/headroom/blob/32d7ca4577d599b8a5f811ada74cf31504302c9d/README.md) |
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
