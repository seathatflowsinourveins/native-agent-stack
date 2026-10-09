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

The role-to-lane mappings come from the supplied lane launches/dispatch, not
from those JSON keys: rumi is current memory-h2h, voni its separate historical
identity, dove the context/token lane, and lise the code-intelligence lane.
The named Claude architecture role is a consumer; an unattributed bucket does
not prove an owning lane. Organic use remains unresolved without a native task
observation. Native Claude memory is outside this MCP metric; Graphiti is
unmeasured. No namespace absence is promoted to a measured zero.

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
