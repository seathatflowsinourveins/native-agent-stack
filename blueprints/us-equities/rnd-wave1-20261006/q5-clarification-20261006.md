# R1 Q5 minimal clarification — 2026-10-06

Draft; requires GPT read and CC ACK. No R1 registry or rerun is authorized by this document alone.

The command center's refined ruling, task-ns2604-coop-20261006T204552Z section 2, replaces the earlier all-fields proposal. D6 remains an independent oracle. This record derives only the table's 15 date ranges; all three other authoritative fields of all 57 D6 entries are unknown under D1 unless an earlier frozen, source-cited rule applies. No new mapping rule is introduced.

Source base: ecfa112764c664d35377dd66b8cfcb67e5a94d60. Preregistration/stack base: b253161a480f8369283e4661e36e737792765891. Earlier files and D4 fixtures stay byte-identical. The superseded draft and its failures remain retained; its mappings are not inputs to this rerun.

## Fifteen date bindings

The table identifies 15 authorized date fields, not 15 proven complete data-read intervals. C06's recorded session supplies the upper date; its same cited span reports older/stale bars without an earliest date, so its lower bound stays unknown. Other displayed dates come from the date-only source check, never retyped oracle values. The JSON record holds exact file/span hashes and field paths or named-capture date patterns. Every parser checks its source hash first and never uses a D6 value to choose a date.

| Entry | Source span | Source-derived date range |
| --- | --- | --- |
| D6-C04 | blueprints/us-equities/incentive-monitor/README.md:113-115 | 2026-07-09 .. 2026-09-24 |
| D6-C06 | blueprints/us-equities/broad-universe/README.md:133-153 | unknown .. 2026-09-21 |
| D6-C08 | blueprints/us-equities/data-lake/README.md:55-57 | 2015-01-01 .. 2026-09-23 |
| D6-C11 | blueprints/us-equities/pit-availability/README.md:136-142 | 2016-01-01 .. 2026-09-22 |
| D6-C13-w1 | blueprints/us-equities/adaptive-paper/corporate-actions-native-check-20260924.json:9-26 | 2024-06-01 .. 2024-06-15 |
| D6-I04 | blueprints/us-equities/engine-nautilus/ibkr-paper-orders/evidence/receipt-20260923-passed.json:4-4 | 2026-09-23 .. 2026-09-23 |
| D6-I05 | blueprints/us-equities/engine-nautilus/ibkr-paper-orders/evidence/receipt-20260923-post-incomplete.json:4-4 | 2026-09-23 .. 2026-09-23 |
| D6-N01 | blueprints/us-equities/adaptive-paper/native-faults/receipt-20260923.json:170-170, 160-160 | 2026-09-23 .. 2026-09-23 |
| D6-N02 | blueprints/us-equities/adaptive-paper/native-faults/receipt-20260924t143905.json:191-191, 181-181 | 2026-09-24 .. 2026-09-24 |
| D6-N03 | blueprints/us-equities/adaptive-paper/native-faults/receipt-20260924t185811.json:192-192, 182-182 | 2026-09-24 .. 2026-09-24 |
| D6-N04 | blueprints/us-equities/adaptive-paper/native-faults/receipt-20260925t182513.json:192-192, 182-182 | 2026-09-25 .. 2026-09-25 |
| D6-P01 | blueprints/us-equities/order-throughput/evidence/index-20260924.json:3-7 | 2026-09-24 .. 2026-09-24 |
| D6-S02 | blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json:1467-1470 | 2026-09-23 .. 2026-09-23 |
| D6-T14 | blueprints/us-equities/adaptive-paper/trials/mac-2026-09-24-native-faults/README.md:1-8 | 2026-09-24 .. 2026-09-24 |
| D6-O-N01 | blueprints/us-equities/pit-availability/README.md:35-47 | 2016-01-01 .. 2026-09-22 |

## Unknowns and comparison

The remaining 42 date fields receive no new rule here. Preserve any already applicable frozen source rule; otherwise emit unknown under D1. The same applies to scope_kind, identifiers_or_universe and access_kind across all 57 entries. This draft adds no classifier, identity renderer, code lookback, extra source, timestamp-unit inference or range projection.

D6's C02 and C10 pins remain as frozen. Pins are not derivations. Strict source-versus-pin comparison remains mandatory, and a mismatch remains REJECTED_DERIVATION (11). Unknown case/security/date state conservatively refuses under D1; the record does not declare a future success or type eligibility into a gate.

## Expected rerun result under the unknowns

D1 makes unknown entries cover every case that could lie in their potential scope; an unbounded unknown covers every case. Lookup yields no record for relevant unknown or unresolvable scope/security/date, so reserved_access refuses. Unknown fields count as present for D2 completeness: retain all 57 D6 entries, existing known reads and critic-cited reads rather than dropping an unknown or unmatched entry.

Eligibility is already 0 per v1 segment in frozen D6. Report and recompute those counts deterministically; they are not a new gate. With prerequisites met and no lower-numbered rejection, the expected completed rerun is REJECTED_DERIVATION (11): required unknown fields differ from D6's known pins, including C01. Unknown by itself creates no new rejection rule. A missing required entry instead gives completeness rejection (10).

Prerequisites and D5.3/D6 record handling are unchanged: an unmet prerequisite or missing required record means NOT_STARTED (30) and no wave command runs; a D5.3 external hash mismatch also means NOT_STARTED. D6 citation/hash mismatch remains derivation rejection. Preserve every command's native and sanitizer exits, stdout/stderr, both builder outputs and failed/refused artifacts. D4 keeps lowest-numbered rejection precedence and lists all failures; a command that reaches no verdict retains ERROR (2).

C06's partial-bound source semantics are explicitly submitted for the scoped CC adjudication requested in J808. Its lower endpoint remains unknown in this proposal; neither the old singleton assumption nor a D6 value replaces that absence.

## Decision and review

The selected alternative follows form (a), minimal: explicit source-derived dates and honest unknowns. Reading D6 values as binding input conflicts with D1. New per-source mapping proposals are out of this rerun's scope. An already frozen source-cited rule may resolve a field within its actual scope; a missing rule never licenses inference.

The north-star action served is truthful runtime qualification before prospective US-equities R&D. This record starts no new research wave, strategy, data acquisition or paper operation. The GPT read and CC ACK must pin the dated record before any registry; the actual rerun remains after the paper exclusion and follows D1's computed status.

## Sources

- Frozen D1, D4, D5.3 and D6 at b253161a480f8369283e4661e36e737792765891 in this deviation series.
- The original retained records at ecfa112764c664d35377dd66b8cfcb67e5a94d60, bound by file and exact original span hashes in the JSON record.
- CC RULING-Q5-MINIMAL, task-ns2604-coop-20261006T204552Z section 2, received as queued user direction.
