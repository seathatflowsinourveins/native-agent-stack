# Decision: retire PR #320's Loki denominator and host receipt explorer changes (2026-10-03)

**Decided under:** Claude session `native-agent-stack-0c`'s custody, after the
[two-hour objection window](https://github.com/seathatflowsinourveins/native-agent-stack/pull/320#issuecomment-5967134057)
ended on 2026-10-03 at 10:21:52Z without a reply.

**Scope:** [PR #320](https://github.com/seathatflowsinourveins/native-agent-stack/pull/320),
A20 (Loki provider-usage denominator) and A22 (host receipts in the explorer).
The north-star action is to keep token accounting and portable evidence usable for
complex-system research while the selected target's observation owner completes
the deciding measurement.

## Decision

Retire #320 unmerged on 2026-10-03 under 0c's custody. Preserve its proposal and
review as recovery evidence; do not carry its implementation onto main.

- Proposal head: `d59d0fca32a820bc19a58dc78f27148ddeb9c142`.
- Proposal branch: `claude/token-practice-reporting-20260925`.
- Record base: `9b0b8d6d25f9e3fb8f71770500e774170423315e` (origin/main).
- Record branch: `foundation/retire-pr320-20261003`.
- Recovery: `git fetch origin pull/320/head`. The proposal branch and
  `refs/pull/320/head` remain available; the coordinator closes #320 after merging
  this record, without deleting its branch.

All proposal source lines below refer to the pinned proposal head. All main source
lines refer to the record base above. This is a repository-record and source-review
decision, not a new host execution or a savings measurement.

## What #320 proposed (A20)

The exact LogQL instant query was:

```logql
sum by (query_source) (sum_over_time({service_name="claude-code"} | event_name="api_request" | unwrap cache_read_tokens[24h]))
```

It selects the `api_request` event's `cache_read_tokens` and sums by `query_source`.
`loki_last_completed_day()` finds the last UTC midnight and the midnight 24 hours
earlier. The request is `GET /loki/api/v1/query`, evaluated at that last midnight,
with `time = int(at.timestamp()) * 1_000_000_000`, `direction=forward` and a
20 s socket timeout. Its intended window is the last completed UTC calendar day.
The timeout was not an overall deadline or a response-size cap, as the review below
records. [Source: tools/token-report/token_manifest.py, L592–650.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/token_manifest.py#L592-L650)

The raw `by_query_source` breakdown remains visible. `total_all_sources` is its sum;
`excluded_total` sums the configured `loki_excluded_query_sources`, defaulting to
`["agent_summary"]`; `net_total = total_all_sources - excluded_total`. Other helper
sources remain in that net. `loki_reference_totals` maps UTC `YYYY-MM-DD` dates to
nonnegative integers. The matching day's reference is the `cacheReadTokens` value
of `ccusage daily --timezone UTC -O -j`, supplied by the operator; this hook does
not execute ccusage. `loki_reconciliation_tolerance_pct` defaults to `1.0` percent.
[Source: token_manifest.py, L715–789](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/token_manifest.py#L715-L789),
[and tools/token-report/README.md, L142–163.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/README.md#L142-L163)

`refresh()` invokes `provider_usage_denominator()` with its capture directory.
Raw responses and request receipts are saved under
`captures/<run>/loki-provider-usage/`. Without `loki_url`, it returns
`configured: false` and makes no request. These are one host's retained usage
figures, never a savings counter, never written to the savings ledger, and never
added across tools, hosts or days. A later refresh replaces the manifest section;
the separate captures retain the earlier response.
[Source: token_manifest.py, L703–714](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/token_manifest.py#L703-L714),
[L745–770](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/token_manifest.py#L745-L770),
[L1006–1016](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/token_manifest.py#L1006-L1016),
[and README.md, L129–140.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/tools/token-report/README.md#L129-L140)

## What #320 proposed (A22)

`build_host_token_receipts()` filters to `review_state(receipt) == "agree"`
**before** selecting the latest `observed_at_utc` per (host, selected token
component, lifecycle stage). A newer unreviewed or dissented receipt is omitted,
so the displayed row can be an older agreed receipt. Install and use stages remain
separate. The hard-coded two-host allowlist is
`("nativestack-5975wx-20260925", "wsl-authoring-20260923")`.
[Source: scripts/build_ecosystem.py, L66–83](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/scripts/build_ecosystem.py#L66-L83),
[L364–435.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/scripts/build_ecosystem.py#L364-L435)

`build_host_subagent_e2e_receipts()` separately selects the latest
`token_stack_subagent_e2e` receipt per allowlisted host from
`evidence/artifacts/token-e2e-*/receipt.json`. That kind has no per-receipt
independent-review gate; the allowlist is its inclusion gate. Each row carries
only the tools in that receipt, its counters, evidence-class notes and retained
gaps. Host receipt and whole-stack receipt links resolve at `publication_ref`,
rather than the older immutable `source_revision`. The template displays the
row's own date, claim and limitations and links the complete original receipt.
[Source: build_ecosystem.py, L438–516](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/scripts/build_ecosystem.py#L438-L516),
[L551–569](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/scripts/build_ecosystem.py#L551-L569),
[and docs/ecosystem/template.html, L500–513](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/docs/ecosystem/template.html#L500-L513),
[L669–675.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/docs/ecosystem/template.html#L669-L675)

The proposed page's boundary text is preserved verbatim here. Its claim about a
missing component describes that filtered display, not all receipts in the tree:

> Each host_acceptance row below is the latest independently reviewed (review_state agree) evidence/hosts/ receipt for one host, one token-efficiency component and one lifecycle stage (adoption/host-receipt.schema.json, recorded by scripts/host_receipts.py); a newer receipt for that same host/component/stage that is unreviewed or carries a standing dissent is simply not shown here. An install-stage receipt observed later than a use-stage receipt for the same component never hides the use-stage row, because they are different lifecycle stages. Never sum a row's counters across hosts, components/tools or stages: a host's own claim and limitations text states what its numbers do and do not cover, and a component missing here simply has no independently reviewed receipt on that host yet. A separate whole-stack subagent E2E row (kind token_stack_subagent_e2e) covers only the tools actually listed in that specific receipt for one host in a single file, not necessarily every selected token-efficiency component, each with its own counters and scope note; that row's own limitations state whether each counter is scoped to the run or host-wide (a missing note is not evidence either way), and its figures are never summed across tools, across hosts, or with the per-component host_acceptance rows above.

[Source: build_ecosystem.py, L346–361.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d59d0fca32a820bc19a58dc78f27148ddeb9c142/scripts/build_ecosystem.py#L346-L361)

## Evidence state

The [PR body](https://github.com/seathatflowsinourveins/native-agent-stack/pull/320)
classifies A20's fixture tests and A22's build/tests as `local_integration`.
It leaves the live 1.0% Loki reconciliation and the publish-catalog / attestation
checks **not established**. The green checks at this head completed on
2026-09-26; they are history, not a current pass or retained proof of the body’s
local commands.

The [2026-09-29 hold comment](https://github.com/seathatflowsinourveins/native-agent-stack/pull/320#issuecomment-5883993124)
reports that GPT-6 (`gpt-6-astra`, requested at max) returned `needs_changes`,
with five major and three minor findings. The comment distinguishes the requested
model from an observed resolution. Its private local review file is not evidence
of record here. The findings below reproduce the comment's wording verbatim.

Major findings:

1. “the Loki response body has no size cap or overall deadline, so a streaming response stalls the refresh or exhausts memory despite the socket timeout (`token_manifest.py` near L650)”
2. “`RecursionError` from a deeply nested JSON body escapes both query paths and aborts the refresh (near L790)”
3. “a JSON-escaped lone surrogate in a response label reaches `render_reports` and raises an uncaught `UnicodeEncodeError` (near L696)”
4. “URL credentials are accepted and retained verbatim, and a password can enter `issues`, which `refresh` prints (near L752)”
5. “the body's validator, full-suite, token-report and gitleaks passes have no retained output.”

Minor findings:

1. “default urllib redirects can change host and drop the query, so another endpoint's response is attributed to the original URL and window”
2. “a base URL with a query or fragment is concatenated wrongly”
3. “malformed limitation fields in `build_ecosystem.py` are transformed rather than rejected.”

The same hold says a Claude-family review **of this head**, a repair round and a
rebase were not done. The body claims three earlier Opus evidence-review rounds;
that earlier claim does not establish the missing head review. No completed
Claude-family review of this head is established by the later hold. These findings
are carried as rebuild requirements, not repaired in this retirement.

## Why retired

The alternatives are to merge the frozen proposal, repair and rebase both halves,
or retire it while preserving recovery. The current sources favor retirement:

- **A20's target baseline changed.** At the record base,
  `docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`, L78–83, assigns usage
  metering to the clients and OpenTelemetry, drops ccusage from the target, selects
  no context-supply layer and leaves Loki and Grafana uninstalled pending
  `event-store-and-dashboards`. L523–529 preserves the disagreement and the
  comparison: Collector connectors into Prometheus alone versus that set plus
  Loki and Grafana, judged on ten fixed observation questions and then operator
  minutes. The deciding observation measurement remains unreturned there. Retirement does not
  decide that owner's measurement.
  [Defaults, L78–83](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-new-wsl-definitive-defaults.md#L78-L83),
  [L523–529.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-new-wsl-definitive-defaults.md#L523-L529)
- **Target and legacy evidence are separate.**
  `docs/decisions/2026-10-02-clean-resolution-goal.md`, L23–27, explicitly separates
  the selected target's clients/OTel metering and no additional context-supply
  layer from legacy-host qualification. Legacy ccusage or RTK evidence therefore
  does not require either component on the new target.
  [Source, L23–27.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-02-clean-resolution-goal.md#L23-L27)
- **The legacy accounting question already has a recorded answer and a report
  path.** `docs/token-practice.md`, L345–350, records a transcript scan matching
  ccusage 20.0.26 on input, output, cache-read and cache-creation totals within
  0.001% for its stated historical UTC dates. `tools/token-report/README.md`,
  L206–215 and L242–250, provides explicit `report_sources`, retained returned
  output and separate consumption/status/cache reporting with no savings value;
  the ccusage reports select each agent separately. Neither source establishes
  #320's missing live Loki reconciliation.
  [Run shape and accounting, L345–350](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/token-practice.md#L345-L350),
  [optional reports, L206–215](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/tools/token-report/README.md#L206-L215),
  [L242–250.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/tools/token-report/README.md#L242-L250)
- **A22 duplicates an evidence view while losing dissent and binding.**
  `docs/component-evidence-matrix.md`, L19 and L40, already publishes the
  token-efficiency winners' per-platform host receipt counts, independently
  reviewed counts and standing dissent. Counts deliberately ignore pins; the
  JSON's derived status binds receipts to the current winner pin.
  `scripts/platform_status.py`, L12–27, defines schema/platform/pin/layer binding,
  supersession, reviewed use-stage qualification and failures that remain
  blocking. `scripts/receipt_staleness.py`, L2–39, separately reports age, moved
  pins, missing binding and aliases without modifying the deterministic matrix.
  A22 filters away dissent and selects by date without those binding rules.
  [Matrix, L19–40](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/component-evidence-matrix.md#L19-L40),
  [platform-status docstring, L12–27](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/scripts/platform_status.py#L12-L27),
  [receipt-staleness docstring, L2–39.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/scripts/receipt_staleness.py#L2-L39)
- **Malformed evidence must be rejected.** The 2026-09-27 anti-pattern
  “Silently filtering malformed rows from a measured denominator” requires
  failing closed with the source path and item location. Silently filtering A22's
  limitation strings repeats that class of mistake; it is not evidence cleanup.
  [docs/harness-defaults.md, L136.](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/harness-defaults.md#L136)

## Reopen conditions

**A20:** reopen if `event-store-and-dashboards` retains Loki on the selected target
and a token question cannot be answered from the clients' own usage commands plus
the Collector-to-Prometheus path. Rebuild from current upstream documentation at
the installed versions; re-derive the `query_source` values and exclusions instead
of inheriting `agent_summary`. Prefer a `report_sources` entry using a maintained
upstream client with an overall deadline and a response-size cap. Every finding
listed above needs a red-first test for any implementation that carries that
behavior, including retained check output. A source read or version check cannot
replace the live reconciliation or publication acceptance.

**A22:** reopen if the explorer needs per-receipt host claims the component
evidence matrix does not carry. Build on `platform_status` binding and
`receipt_staleness` flags. Show standing dissent instead of hiding it; take hosts
from validated `evidence/hosts/` rather than a hard-coded list. Reject malformed
limitation fields rather than filtering them. Keep each receipt's scope and review
state visible and keep counters separate across hosts, tools and lifecycle stages.

## Sources and completeness

This record follows the repository's dated retirement style at
[`docs/decisions/2026-09-25-retire-vela-velanext.md`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-25-retire-vela-velanext.md)
and the existing evidence-registration/report commands; it adds no runtime or
test harness. Proposal reads include the pinned source and the diff from the PR's
stated base `5d8bd611` to `d59d0fca` for the builder and template.

The current primary
[Loki HTTP API reference](https://grafana.com/docs/loki/latest/reference/loki-http-api/)
and [Claude Code monitoring reference](https://code.claude.com/docs/en/monitoring-usage)
were read on 2026-10-03 as reopen leads, not version-bound acceptance. The
completeness critic considered both proposal halves, current versus legacy
targets, live versus fixture evidence, receipt review/binding, and recovery.
One source class to include in a reopened observation sweep is Desktop sessions:
the current monitoring reference gives them `service.name=claude-code-desktop`,
distinct from terminal sessions' `claude-code`. Recheck the selected client's
resource-to-Loki-label mapping and intended session coverage along with the
source labels and exclusions. This observation does not alter the frozen query
or the architecture owner's measurement.

## Not changed

Existing main implementation, configuration, receipts and historical decisions
remain byte-for-byte unchanged. This change adds this record and registers its
hash in `manifests/evidence.json`; generated reports are only rewritten through
their native `--write` commands. PR #320, its pinned head and its branch are
preserved until the coordinator closes the PR after the record merges. No finding
is repaired in token-report or the explorer, no observation measurement is
pre-empted, and no other lane's PR is changed.

## Privacy

This record uses repository paths, public receipt host identifiers and GitHub
URLs. It includes no host filesystem paths, user names, coordination-folder
paths or private review-file locator. The published hold comment is the review
evidence of record.
