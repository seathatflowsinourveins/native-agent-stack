# Native token profile, memory and lifetime accounting

The selected profile is qualified on this host through native installation,
useful operations in both client families, isolated state and recoverable
lifecycle checks. This is a composed acceptance record, not a new-machine
sign-in or an equal-quality provider-saving experiment. The twelve tools remain
task-selected; installing the profile does not load every tool into each prompt.

The detailed records are [profile acceptance](../../evidence/receipts/token-profile-completion-20260930.json),
[fresh Codex returns](../../evidence/artifacts/token-profile-codex-20260930/native-tool-returns.json),
[Claude returns and counter scopes](../../evidence/artifacts/token-profile-completion-20260930/claude-native.json),
[the per-tool dated mapping](../../evidence/artifacts/token-profile-completion-20260930/composed-acceptance.json),
and [the earlier native lifecycle qualification](2026-09-30-token-lifecycle-resolution.md).
[Draft PR561](https://github.com/seathatflowsinourveins/native-agent-stack/pull/561) records these artifacts and their hashes; review and merging remain separate.

| Layer | Selected upstream | Qualified use |
| --- | --- | --- |
| Clients | Claude Code 2.1.285; Codex 0.159.2 | Native executable installation, supported CLI/RPC, existing sign-ins |
| Output filtering | RTK 0.50.0 | Contract-limited compact output; original recovery when filtering loses required detail |
| Outside-context processing | Context Mode 1.0.169 | Native execution and focused answers; release, npm and plugin identities kept separate |
| Bundling | Repomix 1.18.1 | Selected XML files with original bodies verified |
| Recoverable compression | Headroom 0.37.0 | Actual compression and exact retrieval across server processes |
| Structured encoding | TOON 4.1.1 | Strict JSON-value round trip |
| Usage accounting | ccusage 20.0.26 | Native aggregation of the public synthetic Claude fixture |
| Document retrieval | QMD 2.8.3 | Scoped BM25 search, returned URI, fresh-process exact body and owned collection removal |
| Document conversion | MarkItDown 0.1.8 | Native HTML conversion and source-answer checks |
| Semantic navigation | Serena c6fbd1c5932df2494ffa0020af5a9fbe80b82143 | Actual symbol results; strict Claude/Codex schema parity and fault rejection |
| Code retrieval | SocratiCode 1.15.0 | Native indexed code search and owned index/watcher cleanup |
| Durable memory | ai-memory 2.4.2 | Scoped write/query/read, empty negative query, restart and binary rollback |
| MCP bridge | MCPorter 0.14.1 | Useful native calls returning the same underlying content |

Codex has fresh useful-operation evidence for all twelve tools. Claude has
fresh RTK, Context Mode, Repomix, Headroom, ccusage, QMD, ai-memory and MCPorter
operations. Its TOON, MarkItDown, Serena and SocratiCode positive operations
reuse the dated [Ultracode subagent record](../../evidence/artifacts/token-e2e-ultracode-20260925/receipt.json)
at unchanged tool pins, with current native installation/parity fixtures.
That record's missing discriminating controls remain missing; its later
retracted QMD and Repomix claims are replaced by the fresh operations here.
This does not claim a fresh twelve-tool Claude provider run.

Claude retains Ultracode, experimental native Workflow and ordinary Agent
lifecycle, role-specific SubagentStart lanes and native caching/compaction.
The coordinator uses explicit Opus/max; the checked extraction unit uses
Sonnet/max. Codex retains Sol/ultra coordination and supported native V2
subagent lifecycle. The earlier saved-workflow continuation reused completed
readers, and the ordinary Agent continuation completed through native handback.
Neither restarting a caller nor replaying a receipt counts as a new model run.

The clients subsequently advanced concurrently to Claude Code 2.1.286 and
Codex 0.159.3. The table above retains the versions actually qualified by those
operations. Codex's [exact release delta](https://github.com/openai/codex/compare/rust-v0.159.2...rust-v0.159.3)
leaves the selected core, hook and app-server protocol files unchanged; this is
source compatibility, not another provider run. Claude's
[2.1.286 changelog](https://github.com/anthropics/claude-code/blob/f5f60250a032caa72d1eb47f9ca5f29becc7066f/CHANGELOG.md#L32)
changes Workflow recovery and foreground task behavior. Its first two fresh
probes completed reader results and an ordinary Agent tool handback, but both
parent processes reached their 300-second limits (native exit -15).
Complete Workflow recovery and the role-specific carrier are not accepted by
those attempts. The [current revision evidence](../../evidence/artifacts/token-profile-completion-20260930/ci-repair.json)
keeps partial returns, source compatibility and bounded repairs separate.

The fresh probe found a real host gap: the source-identical carrier files were
installed, but the user SubagentStart event registered only ai-memory. The
canonical carrier entry, including its five-second timeout, was restored with
the existing `tools/adoption/apply_claude_settings.py` merge command. A value-free
comparison verifies one carrier entry, all earlier hooks and other settings
preserved, and the native backup and original file mode retained. File presence
and installer success alone do not establish hook delivery; a fresh process must
observe the role block.

The bounded 2.1.286 repair then passed both native parents (153.538 and 27.507
seconds, exit 0). The unchanged small fixture completed its Sonnet/max scout and
Opus/max verifier; normal saved recovery reused both completed results without
restarting children. A foreground source-scout Agent handed back its actual
successful Python tool result. All three fresh children ran the persistent
carrier successfully and received their corresponding role blocks byte-for-byte,
without a settings override. The specific network-stall restart and unavailable
task-tracking-tool conditions remain unqualified. These synthetic operations do
not establish provider quality or billing savings.

Native hook refresh exposed another lifecycle failure. The settings merger had
combined the carrier with ai-memory because both used the same matcher, while
[ai-memory's pinned ownership classifier](https://github.com/akitaonrails/ai-memory/blob/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/crates/ai-memory-cli/src/commands/install_hooks.rs#L1513)
replaces the whole outer entry when any command belongs to it. An isolated native
refresh reproduced the loss. The merger now preserves canonical entry boundaries
and splits existing mixed entries into contiguous runs without changing hook
values or order. Its 25 integration tests pass; the repaired fixture retained the
exact carrier through two unchanged native ai-memory refreshes, with the repeated
cycle byte-identical. The host received that structural repair through the same
supported settings merge command. This proves the reproduced condition; the
historical disappearance remains unattributed.

## Memory selection and activation

Adopt [ai-memory 2.4.2](https://github.com/akitaonrails/ai-memory/tree/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1)
for its supported native Claude/Codex lifecycle and correctness fixes. The
release archive and published checksum agree; the active service's executable
matches the staged binary. The store tree is identical to 2.4.1 at Git object
`69f067017fe325c0485f5d03559c78285d2642e3`, with the same V67 migration set.
An isolated persisted record survived 2.4.1 → 2.4.2 → 2.4.1. Activation retained
the prior executable, changed only the owned executable selection, restarted
the service, checked native MCP status and refreshed both clients' hooks through
`ai-memory install-hooks --agent <client> --apply`.

The changed Codex commands required renewed native trust: `hooks/list` supplied
the seven current hashes, `config/batchWrite` persisted them with an upsert, and
a new app-server process reported all seven trusted while preserving the other
six hooks. See [the native trust record](../../evidence/artifacts/token-profile-completion-20260930/codex-native-hook-trust.json)
and the pinned [Codex writer](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/tui/src/hooks_rpc.rs#L58).

No production store or authentication data was copied. Upstream's full backup
includes authentication tables and config; omitting the config alone would not
meet this session's boundary. Binary rollback restores executable behavior, not
logical writes. See the pinned [store](https://github.com/akitaonrails/ai-memory/tree/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/crates/ai-memory-store),
[backup implementation](https://github.com/akitaonrails/ai-memory/blob/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/crates/ai-memory-mcp/src/admin.rs#L817),
and [deployment rollback](https://github.com/akitaonrails/ai-memory/blob/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/docs/deploy.md#L388).

Keep QMD for documents, SocratiCode for semantic code, and Serena/jCodeMunch/
codebase-memory for their distinct navigation and structural tasks. Select one
retrieval lane for the information contract rather than issuing overlapping
queries to all of them. SocratiCode 1.16's optional Git refresh is a candidate;
it does not replace explicit updates for ordinary uncommitted changes.

[Hindsight coding integration 0.8.0](https://github.com/vectorize-io/hindsight/tree/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents)
is the selected isolated trial, not a production replacement. Its unchanged
installer tests passed 203 tests with two upstream sqlite3-dependent skips.
Runtime presence and `stats` do not establish backend health. At this pin,
the container suite marks Claude unsupported and copies Codex authentication,
so it cannot establish acceptance under this session's boundaries. A live trial
needs an explicitly identified backend/authentication route, opt-in project and
bank, and disabled automatic seeding, surveys, synthesis and updates until their
costs are deliberately measured. Published [Hindsight research](https://arxiv.org/abs/2512.12818)
and [AMB](https://github.com/vectorize-io/agent-memory-benchmark/tree/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150)
justify comparison, not a host-specific winner.

Cognee, Graphiti, Mem0 and Letta remain comparison candidates. Their maintained
repositories and native integrations are recorded in the receipt; backend cost,
scope isolation, contradiction handling and deletion must be matched before
replacing the accepted memory lane. Installing several capture systems would
add unmeasured ingestion and synthesis work.

## Native lifetime record

The existing reporter retains original native returns privately, appends
snapshots/events to SQLite, and renders local JSON/HTML. The installed systemd
refresh service returned exit 0 and its timer remains active. Its canonical
reporter is the live checkout at upstream revision
`8fc86119eacfd5be9b8a139e1ed167d85748091b`, using the already qualified
gpt-tokenizer 4.0.0. The stale 3.4.0 checkout/manual-run mismatch and the failed
scheduled attempt are retained; private configuration was restored to 4.0.0.

RTK global retained history includes the project subset. Headroom is a 30-day
ledger. Context Mode's latest selected snapshots use upstream event/byte
estimates; they are not a fresh MCP stats call or a complete provider lifetime.
jCodeMunch has its own cumulative native estimate. Never add these overlapping
scopes or cumulative snapshots. ccusage consumption, cache subsets, exact
artifact comparisons and provider usage remain separate.

The native refresh at `2026-10-01T02:15:27.984655+00:00` recorded **84,314,061**
estimated RTK tokens saved across retained global history; its **55,390,889**
project subset is already included. Collection issues were empty. The
[snapshot evidence](../../evidence/artifacts/token-profile-completion-20260930/ci-repair.json)
retains the service return and original report hashes. Context Mode, Headroom,
jCodeMunch and the 25 exact artifact comparisons remain separate counters;
none establishes a measured provider-billing reduction.

The small lossless Repomix fixture grew from 102 to 289 bytes. This is accepted
fidelity with no saving claim. Headroom's fixture reduced its own native count
from 826 to 511 tokens and recovered every original byte. Neither number is a
measured reduction in provider-billed tokens. Failed attempts retain unknown
usage where the native caller supplied no final result.

Context Mode's official tag resolves to
`589d8214d56740a28b5f7bf63167743d586b0b40`; installed Codex plugin bundles match
`6f0cc6841c687e754059f36714a11233fda1a02b`. The source formulas match both.
The npm archive is identified by registry integrity, not an invented gitHead;
current MCP process binding remains unverified. This distinction prevents a
same-version label from becoming a false source-identity claim.

## Reproducible commands and acceptance scope

Use the supported install commands in the component recipes. Selected upgrades:

```sh
rtk npm install -g @openai/codex@0.159.2
rtk proxy claude install 2.1.285
rtk gh release download v2.4.2 --repo akitaonrails/ai-memory --pattern 'ai-memory-linux-x86_64.tar.gz*' --dir "$TOKEN_MEMORY_PREFIX"
rtk proxy sha256sum -c ai-memory-linux-x86_64.tar.gz.sha256
rtk tar -xzf ai-memory-linux-x86_64.tar.gz -C "$TOKEN_MEMORY_PREFIX"
rtk python3 tools/adoption/install_claude_profile.py --help
rtk python3 scripts/native_token_ci.py --install --output "$TOKEN_CHECK_OUTPUT"
rtk python3 tools/token-report/token_manifest.py refresh --config "$TOKEN_REPORT_CONFIG"
```

Run checksum verification in the owned download directory. Existing-store
activation follows the source-backed compatibility/rollback procedure above;
new hosts retain their own native sign-ins. The earlier full sixteen-tool clean
prefix passed 259 commands and 82 integration checks at ai-memory 2.4.1. The
2.4.2 delta has fresh clean-release, restart, rollback and native-client evidence;
the updated sixteen-tool recipe has not been relabeled as a fresh 259-command
run. Upstream RTK inline tests and unchanged Hindsight installer tests remain
distinct from locally authored integration checks.

Clean Linux CI subsequently exposed an inherited-project assumption in Serena
(the earlier Claude preimage had 21 tools). Explicit no-project runs expose 23 tools
with all shared schemas unchanged and retain the complete byte oracle.
The [native correction and rejected controls](../../evidence/artifacts/token-profile-completion-20260930/serena-no-project/README.md)
and [failed CI returns](../../evidence/artifacts/token-profile-completion-20260930/ci-repair.json)
preserve that correction. Independent Astra review accepted the source and byte
verification. Paired catalog dates and the generated host guide were also repaired
through their maintained validator and generator contracts.

The fresh [current-pin Linux native E2E](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36780366887/job/110108806860)
then passed **259 commands and 82 checks** across 16 pins, including ai-memory 2.4.2,
and removed owned temporary installation state. The unchanged
[original receipt](../../evidence/artifacts/token-profile-completion-20260930/native-ci-1ac1f7d2/README.md)
is retained independently of the older 2.4.1 run and client/provider trials.
Linux bootstrap also passed. Global validation revealed a missing declaration for
the already hashed experiment; declaring that existing record now passes all 26
records/142 observations locally without changing any historical hash or oracle.
