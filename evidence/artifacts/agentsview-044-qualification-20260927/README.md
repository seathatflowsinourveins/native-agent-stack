# AgentsView 0.44.0 qualification — 2026-09-27

**Hold the 0.43.0 pin.** The live release check still identifies v0.44.0 as
the latest published stable release. Its official Linux amd64 asset passed the
published checksum check and several archive checks, but the complete
qualification procedure did not pass. No pin, production recipe, PATH, host
configuration or installed AgentsView archive changed.

This record follows the full-save plan's qualification steps 2–5. The host switch
(step 6) was outside the unit's scope. [qualification.json](qualification.json)
contains the gate decision, [native-checks.json](native-checks.json) the sanitized
observations, and [upstream-tests.json](upstream-tests.json) the distinct upstream
test attempts. [returned-output.txt](returned-output.txt) retains selected actual
returned lines; it is not a generated replacement for the failed test record.

## Source and installation

The candidate is [kenn-io/agentsview v0.44.0](https://github.com/kenn-io/agentsview/releases/tag/v0.44.0),
commit `413a87f7bfbd67b2815b1119ac51abc1efbeeaba`. The installed baseline reports
v0.43.0, commit `9be7745ad1906ee24e04eb05bb86c872ef0939a1`.

The release asset and SHA256SUMS were downloaded with upstream's GitHub release
channel into a new unit prefix, then extracted there. The archive SHA-256 is
`037ea7a46d52e06b20363b4aa7cd7f28e32f31d8215803d6e9a0c96bac5818e3`.
The verification used `sha256sum --ignore-missing --check SHA256SUMS`.
The [tagged installer](https://github.com/kenn-io/agentsview/blob/v0.44.0/scripts/install.sh)
documents the same release archive and checksum channel. No installer was allowed
to select a host bin directory.

Go 1.27.0 was installed into that prefix and verified against the
[official Go download digest](https://go.dev/dl/?mode=json&include=all), matching
the candidate's [go.mod](https://github.com/kenn-io/agentsview/blob/v0.44.0/go.mod).
Test commands used its explicit executable with isolated GOPATH/GOCACHE. The
upstream tracked source was unchanged.

## Evidence classes and results

| Evidence class | Observation | Limit |
| --- | --- | --- |
| Unchanged upstream tests | MCP: 97 passing test/subtest events, 3 skipped. DB: 3,365 passing events, 17 skipped. The #1855 selectors pass all 4 top-level tests, 13 events. | Selected package scope; no full `./...`, frontend or cross-platform acceptance. |
| Unchanged upstream tests, failed | The first runnable MCP/parser/DB attempt has 21 failing top-level parser tests, 25 failing events. A second subprocess run reproduces the same failures. | The failures remain unresolved. Pass counts from overlapping attempts are never summed. |
| Local integration over copied historical logs | Two exact authorized log copies, 381,416 bytes: one Claude session and one Codex session. Both pins preserve 2 inclusive sessions, 1 project and 2 bounded FTS hits. | No child sessions in these retained inputs; no new provider run. |
| Local integration, usage | Both pins' inclusive CLI totals agree with ccusage 20.0.24: 20,965 uncached input + 58,752 cache read + 556 output = 80,273 tokens. | Reasoning output 64 is a subset of output. No cost-parity claim. |
| Synthetic fixture | Five controlled populations, including both child types and an interactive control, are visible with all three inclusion flags. Codex automated classification changes as expected. | The local fixture's ccusage report is zero; fixture usage parity failed and remains recorded. |
| Local integration, port control | With an owned listener occupying 17384, baseline succeeds on 17385; candidate exits 1. The candidate gives an explicit choose-another-port diagnostic. | Only the owned scratch listeners and daemons were used. |
| Local measurement | One full sync over the same two copied logs: 0.407672 seconds on baseline; 0.358587 seconds on candidate. | Too small and unreplicated for an efficiency or throughput conclusion. |
| Provider execution / review | Native Codex review initialization fails in both normal and ephemeral modes. Claude review was interrupted without a returned report; usage is unknown. | Four fresh native lanes and the independent Claude review remain unaccepted. |
| Independent source/result review | Delegated GPT-6 review independently confirmed the release, source filters, port behavior and copied-archive counters; recommendation: hold. | No tests run by that reviewer; not a native lane replay. |

The initial upstream test attempts failed to build because the generated pricing
snapshot was absent. The supported
[CI prerequisite](https://github.com/kenn-io/agentsview/blob/v0.44.0/.github/workflows/ci.yml#L233),
`go run ./internal/pricing/cmd/litellm-snapshot -restore`, resolved that build
prerequisite. Later parser failures are separate: project inference repeatedly
returns `tmp` where tests expect a different project. A `/tmp/.git` marker seen
by native subprocesses is an environment lead; it has not been established as
the cause. Tests were not modified or waived.

## MCP usage decision and required future recipe

Use inclusive `agentsview usage daily` and native ccusage over identical selected
source logs for accounting. MCP `get_usage_summary` cannot include automated
sessions: its [input type and request](https://github.com/kenn-io/agentsview/blob/v0.44.0/internal/mcp/tools.go#L705)
lack that option, whereas the [CLI filter](https://github.com/kenn-io/agentsview/blob/v0.44.0/cmd/agentsview/usage.go#L163)
includes them. On the two copied logs, candidate MCP returns zero Codex usage
while CLI and ccusage agree. The chosen accounting boundary accommodates this
known limitation; it does not fix the MCP tool.

A future qualifying pin PR must rewire `recipes/README.md` together with its
pins. The current commands are at lines 762–768, shifted from the plan's older
range. Search/list intended to include workers must use
`--include-automated --include-one-shot --include-children`, preserving selected
source roots and the cwd allowlist. Sources:
[tagged command reference](https://github.com/kenn-io/agentsview/blob/v0.44.0/docs/commands.md)
and [#1855](https://github.com/kenn-io/agentsview/pull/1855).

Treat an occupied explicit port as a startup failure and stop dependent reads.
Choose another free explicit port or the supported `--port 0` deliberately.
The [tagged implementation](https://github.com/kenn-io/agentsview/blob/v0.44.0/cmd/agentsview/serve_runtime.go#L57)
makes this behavior intentional. Successful scratch recipe sequences used a
free explicit port; the occupied control used the recipe's literal 17384.

The native sync/serve/projects/search/usage/stop sequence was exercised against
both versions using isolated scratch data. The legacy RR runner itself was not
executed: it hardcodes writable locations outside this unit and direct native
source roots. Its command sequence was adapted, not presented as unchanged
upstream tests.

## Dated corrections and residuals

The unit research log retains the failed setup/probe attempts. Corrections on
2026-09-27: the upstream installer is `scripts/install.sh`; unsupported provider
`homes`/`dirs` entries were removed before any successful sync; synthetic child
identities were corrected to the upstream layout; versioned capture filenames
now append extensions rather than replacing them. Attempt 3's overwritten raw
captures are not used as accepted evidence.

The platform pins files currently have no AgentsView entry. Existing version
references are in `manifests/stack.json`, `scripts/native_token_ci.py` and the
recipe; all remain at 0.43.0. The upstream ccusage source is
[ccusage/ccusage at ecb676cc](https://github.com/ccusage/ccusage/tree/ecb676cce27cb5dd0090c7804a5cecc35e8ba805/rust/adapters/codex),
whose maintained adapter is Rust. The guessed older TypeScript path was a 404,
not evidence of a missing capability.

Requalification needs resolved upstream failures, four fresh native lanes,
a completed independent Claude review and the final recipe controls in the
same pin PR. No complete-history, savings, model-run or performance claim is
made. Full private logs and scratch binaries remain in the unit. Only aggregate
whitelist projections are published; native identities and transcript content
are excluded. Historical repository receipts were not rewritten.

Evidence registration, generated reports and repository-wide validation belong
to the coordinator harness. Recommended label: `lane:foundation`.
