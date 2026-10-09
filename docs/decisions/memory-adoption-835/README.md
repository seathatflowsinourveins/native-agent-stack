# Source bytes for the #835 adoption correction

These are unchanged private-host-state counter captures and a public pinned G5
source for the decision and JSON evidence record
one directory above. They support reproducible counter/binding checks, not a
new Loki query, organic-use observation, product benchmark or catalog adoption.
The repository copies are sanitized metadata bytes, not a portable host's
acceptance. The two adoption snapshots remain separate rolling windows. The old Markdown
capture is dated history and does not support the current dispositions.

| Source | Exact SHA256 | Scope |
| --- | --- | --- |
| `adoption-now-5de97cf238b3d28a.json` | `5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36` | Producer snapshot at 2026-10-08T23:42:51Z, 24-hour window |
| `adoption-now-8682d1d326f29798.json` | `8682d1d326f2979802efa32d156d9db14dba3ce04273328b6b48a0e227533ac7` | Producer snapshot at 2026-10-09T00:31:25Z, separate 24-hour window |
| `INVOKE-RATES-24H-20261008T2330Z.md` | `86e8a4e0db11846eed1c4e99d5e89321b576cab087aa07676188705de593e541` | Exact 2,438-byte dated historical capture; different populations/query time |
| `g5-grand-catalog-ae6cc228.json` | `ff3b593c34b5f27caba29a915d3ed5443cb3a3d3ebb7e46937277529f0637dc9` | Exact 118-row G5 draft catalog at ae6cc2286643822d3a0218136722c69d0127fcd4 |
| `ROLE-MCP-TRIAL-REPORT-20261009.md` | `f0afc2c734b3ad1b70e68cd38d3c844c7f4b1338cc030c8fc40fc88db1e53989` | Private host-state whole-arm memory observations; not component PSS or paired savings |

The snapshots' method is the retained native Loki count described by
`docs/decisions/2026-09-26-tool-invoke-rates.md`. Source counters use exact
snapshot role/bucket keys. Calls, identities and denominators are distinct:
Codex identities are conversations, Claude identities are sessions, and
bucket populations include sessions/threads without a call to the selected
server. No real session identifier, raw conversation or credential is added.

Role-to-lane mappings now come from the SHA256-pinned registry/history excerpt `registry-role-identities.json`, including every observed current/historical alias and source hash. The original source snapshots remain unchanged. Named Claude consumers stay separate; unattributed context proves no owner. Native memory and Graphiti remain unmeasured. The successor correction and machine-checked summary below supersede the earlier one-name-per-lane selection.

The JSON record stores all changed relevant scalar fields, preserving old/new
presence and exact pointer values. Roll-ups check consistency within each
snapshot. They do not combine windows, clients, aliases or namespace identities.
The fresh snapshot's orchestration section is retained in its source bytes but
does not enter this memory decision.

G5 source: [catalog at the exact PR #878 pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ae6cc2286643822d3a0218136722c69d0127fcd4/catalogs/landscape/grand-catalog-20261008.json).
Every decision has an individual pending binding. Only `/rows/7` and `/rows/32`
are present; the other five remain `PENDING — row absent at this G5 pin`, with
the G5 catalog-owner dependency recorded. None resolves until publication and
matching identity/pointer verification.

Local integrity tests use the repository's existing native Python unittest
format and these immutable source bytes. They are structural regression checks
for the two review findings, not upstream component acceptance or proof that
the producer's measurements are true.

## Combined delta correction — 2026-10-09

This successor correction carries the CC delta at
`c5ce6546da699ca08ecd8a3f83ec52fd2d5802232d8922b35abd5e8acd961e31`
and GPT delta at
`6041041dd85cb7854b9e3ca8cd9389de57cdfb1415acd96965947cda8c45ec0c`
for `7f2dc865cc1ead227621bb23fce8d0c771f22440`. No prior source capture,
whole-arm trial, G5 draft or historical host observation was replayed.

The [registry excerpt](registry-role-identities.json) is
pinned at SHA256 `03abf51ca7477c6b40c03e5f60a64177730fc838495b9bc174062555fc7f8cf6`.
It covers memory-h2h `voni/zimu/rumi/revi`, context owner
codex-token-parity `novu/dove/zonu`, and code-intelligence owner overlap-token
`vuru/luva/lise`, including names absent from one or both source captures.
Voni is joined through its canonical thread-registry row and supported stopped
hcom metadata; raw thread identity is hashed. Current relaunch names do not
replace earlier buckets. Context-owner whole-lane sums reproduce
**205 calls / 4 bucket identities / 4 denominator → 276 / 6 / 6**.
Each alias stays separately inspectable; no event-level deduplication is claimed.
Named Claude architecture consumers and `other Claude sessions` context are
now present uniformly for all seven components. Context never proves ownership.

The [Hindsight wiring diff](hindsight-wire.diff.md), SHA256
`d55fcbd57147fe76e124cbc942591cb3d850eb7b11c084fcbcd26702f81208fb`,
records the pinned vendor CLI installer, Claude manual Skills + MCP route,
Codex `$HOME/.agents/skills` root, transaction-specific inverse and one
vendor smoke per client, including the shipped vendor harness boundary.
Every host addition, smoke, organic fresh-session retain/recall and +24 h role
follow-up remains **OUTSTANDING**. The CC selects research scopes, reviews the
concrete diff and applies user-level client changes. The wiring inverse only
reverses reviewed additions/preimages; it preserves the existing service, bank,
registrations, 15-tool allowlist and accepted research job.

The [ai-memory/QMD packet](wire-inverses-smokes.md), SHA256
`31ab5d5c5d8986df30bd367c5428423f2b18c1cad98fc39d5de78e33bb30e5bd`,
records upstream inverses, preview/application commands and client checks.
Shell commands use `$HOME`; `%h` appears only in systemd directives. The two
ai-memory maintenance drafts now name the live optional
`EnvironmentFile=-%h/.config/ai-memory/env`. Only the unit property's path and
ignore-errors flag were inspected; no environment-file content was read.

The JSON now records stage 1 candidate/G5 status, stage 2 install/routing/pin/
inverse/PSS/load scope, stage 3 natural fresh tasks per owning lane and named
consumer, and stage 4 hourly capture/role comparisons from T0 to T0+24 h.
All seven candidates remain **PENDING until G5**. Native memory, context-mode
and codebase-memory are **KEEP proposed** because stage 3/4 organic observations
are unexecuted. Accepted KEEP requires a returned role/session/source-bound
organic-use observation in one of those stages. Smoke/inventory counts do not
supply it. This condition leaves the separate #833 READY rule and retention
rule intact; sparse counters do not authorize removal.

SocratiCode impact/flow/dependency queries and Serena references overlap the
structural-graph slot. The proposed default is codebase-memory, SocratiCode is
scoped to semantic/context search, and Serena to source editing/refactoring.
That routing split is a proposal pending owner review and comparative role
observations. No host change or parallel structural default is accepted here.

The canonical JSON `outstanding` array has **50** unique steps: 16 packet steps,
seven each for component PSS, natural-task observations, hourly follow-ups and
G5 bindings, plus Claude-owner binding, both micro reads, current CI, the required
pre-cue tool and explicit CC cue/owner decisions. All are unexecuted. The fix head
is record qualification; it is not host installation or upstream acceptance.

### Machine-checked lane summary

Bucket identities are summed across every registry-bound alias; these sums are
not deduplicated lane identities. Each source window stays separate. The null
native-memory/Graphiti calls do not represent zero use. Exact per-alias counters,
denominators, registry pointers and absent names remain in the JSON record.

| Component | Lane | Baseline calls / identities sum / denominator sum | Reconciled calls / identities sum / denominator sum |
| --- | --- | --- | --- |
| claude_native_memory | native Claude feature; no named native-memory counter | null / null / null | null / null / null |
| ai_memory | memory-h2h | 13 / 2 / 8 | 13 / 2 / 8 |
| hindsight | memory-h2h | 5 / 2 / 8 | 5 / 2 / 8 |
| context_mode | codex-token-parity | 205 / 4 / 4 | 276 / 6 / 6 |
| codebase_memory | overlap-token | 8 / 2 / 5 | 8 / 2 / 5 |
| qmd | memory-h2h | 1 / 1 / 8 | 1 / 1 / 8 |
| graphiti | memory-h2h | null / null / 8 | null / null / 8 |
