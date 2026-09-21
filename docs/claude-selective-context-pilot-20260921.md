# Selective Context Mode pilot for native Claude

This pilot compares a focused native retrieval policy with a selective Context
Mode policy on the existing accepted retry-policy coding fixture. It is a local
integration experiment, not an upstream product benchmark or a test of every
installed tool. No global default is changed.

## Frozen protocol

The fixture is revision `c0bb7561a9c88a98ceaa06d6fcc153f35f55dd69`, the same
revision used by the [earlier native pairs](../evidence/receipts/token-practice-native-pairs-20260920.json).
Its synthetic diagnostic log contains 25,000 records and 5,445,636 bytes. The
task repairs case-insensitive Retry-After lookup while preserving numeric delay
semantics and produces an exact incident summary. The unchanged visible suite
starts with three failures and eight passes; acceptance requires all eleven
tests and the independent existing oracle's nine held-out behavior checks plus
the exact incident summary. Only `retry_policy.py` and `incident-summary.json`
may change.

Six fresh native Claude sessions use separate Git worktrees from that revision.
The fixed order is native/selective, selective/native, native/selective. This
partly counterbalances order; three pairs cannot balance both orders equally.
All request Opus with its 1M context setting and high effort. Both expose the
same Context Mode 1.0.169 MCP server and native tools. Hooks are disabled equally
per invocation, following the earlier accepted experiment; native accounts,
subscription routing and existing global configuration are retained.

The first attempted baseline exposed an environment defect: the native shell
did not retain the runner's prepended test-environment PATH. It searched outside
the fixture, used an offline cached pytest entry point and wrote a temporary
summary outside the allowed directory. Its solution passed product tests, but
the attempt failed the workflow/scope contract. The attempt remains in the
experiment totals and is excluded from the quality-equivalent paired sample.
Before further model calls, a recorded amendment fixed the common test command
to the already-installed pytest executable's absolute path and verified its
expected failing result through the login shell. Six new attempts were frozen;
each runs once, and a failing arm invalidates that pair rather than being retried
until passing. No installation or global configuration repair was needed.

The native arm uses focused source reads and local computation. The selective
arm may choose Context Mode for the large diagnostic aggregation, while small
source reads, editing and standalone raw pytest calls stay native. It may choose
a sufficient native computation instead; that is recorded as a routing-policy
result rather than forcing an unnecessary tool invocation.

Native caches remain enabled, and cache warmth is uncontrolled. Models are not
seeded. The trial records exact private commands, raw streams, result categories,
elapsed time, tool choices, source diffs, visible/held-out acceptance and file
scope. Native final cumulative `modelUsage` is counted once per fresh session;
cached input and thinking are not counted twice. These task totals exclude the
coordinator, independent audit and report production, and cannot reveal requests
the native client does not report. Subscription billing is unknown.

## Results

All six amended attempts passed the visible suite, held-out oracle and final
file-scope checks. An independent reviewer inspected the original source and
six solution diffs, reran all six visible suites and held-out oracles, and checked
that immutable fixture files still matched the source. No actionable findings
remained. The actual native response model was `claude-opus-5`, with high effort
recorded in each persisted session. No rate-limit failures or API retries were
observed.

| Pair and order | Native tokens | Selective tokens | Selective change | Native seconds | Selective seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1: native, selective | 352,047 | 348,811 | -0.92% | 30.368 | 29.265 |
| 2: selective, native | 311,952 | 342,691 | +9.85% | 31.419 | 23.755 |
| 3: native, selective | 283,494 | 278,878 | -1.63% | 26.319 | 26.162 |
| Amended totals | 947,493 | 970,380 | +2.42% | 88.106 | 79.182 |

Every selective run chose native computation and made **zero Context Mode
calls**. The policies therefore produced equivalent accepted results through
native tools, with mixed observed token differences. This is a routing-policy
pilot; it does not measure Context Mode's causal effect or establish policy
superiority. Its shorter aggregate selective runtime is also an observation,
not an attributable speedup.

| Accounting boundary | Attempts | Native-reported tokens | Native process seconds |
| --- | ---: | ---: | ---: |
| Frozen amended comparison | 6 | 1,917,873 | 167.288 |
| Rejected original attempt | 1 | 612,381 | 54.413 |
| All task attempts | 7 | 2,530,254 | 221.701 |

Totals include ordinary input, cache creation, cache reads and output exactly
once; thinking is already part of output. The amended native arm used 60 ordinary
input, 68,473 cache-creation, 863,544 cache-read and 15,416 output tokens. The
selective arm used 62, 66,724, 889,677 and 13,917 respectively. Each amended
session's four categories reconcile exactly to its unique persisted native
response IDs. Wall time measures the native subprocess, excluding preparation,
acceptance tests and reporting.

The [sanitized receipt](../evidence/receipts/claude-selective-context-pilot-20260921.json)
retains complete native final usage fields, source and artifact hashes, policy
text, order, per-attempt results and the rejected attempt. Exact commands,
prompts, streams, persisted sessions, test output and diffs remain in private
local state. Hashes bind those retained artifacts; they are not independent
provider attestation. This bounded test used equal hook suppression and strict
MCP selection, so it does not replace the separate normal-hook workflow E2E.

## Routing decision

Keep the existing smallest-fitting-lane practice: focused native reads and
computation for a known bounded task, with Context Mode available when the
actual retrieval need justifies it. This fixture did not require its use. Do
not mandate Context Mode on file size alone or adopt a new global default from
these results. The earlier one-pair Claude increase of 25.83% remains separate
evidence: this follow-up neither reproduces nor overturns it because no
selective arm used Context Mode. A causal comparison would require a suitable
task where the selective policy actually chooses that tool, alongside equivalent
acceptance and more controlled repeated trials.
