# Source and native-result adjudication

The retained Claude responses are original worker claims, not accepted facts by
default. Codex independently checked the relevant source and persisted behavior.
The two native workers returned non-null results. No replacement worker ran.

## Accepted findings

- Installed Codex, Claude Code, Context Mode, RTK, Headroom and TOON match the
  sampled current stable release labels. Version equality is a release check;
  reuse the separate unchanged behavioral evidence within its scope.
- Independent native GitHub queries confirm ECC's unchanged HEAD, Shan's
  observed newer revision and the selected-file diff, both SDK release labels,
  and Headroom's canonical repository redirect. Direct byte comparisons confirm
  both installed ECC skills in both sampled skill roots.
- The native Workflow journal records two starts and two returned results.
  Original assistant messages identify `claude-sonnet-5` and `claude-opus-5`;
  the coordinator identifies `claude-fable-5-1`. The script requests Sonnet
  medium and Opus high; twenty Sonnet and thirty-four Opus assistant records
  confirm those native effort settings. Native metadata is not provider attestation.
- The SDK remains conditional on an application need. No SDK was installed or
  tested by this review. The unchanged upstream Python test/example references
  are future qualification handles, not passing results.

## Corrections and unresolved observations

| Returned claim or observation | Adjudication |
| --- | --- |
| Python registry 0.2.157 has “no source SHA” because its Git tag lookup returned 404 | The lookup establishes only the missing requested tag and a release/registry discrepancy. It does not prove no source revision or provenance exists for the registry artifact. Reviewed source is explicitly the older v0.2.156 revision. |
| `settingSources: []` provides isolation | It suppresses user/project/local settings. Managed policy, global configuration and other documented inputs remain; it is not a filesystem or tenant isolation boundary. |
| SDK authentication is “the concrete foundation gap” | The existing native sign-in already supports this task. Official restrictions address offering third-party products with claude.ai login. Personal local SDK authentication was not qualified; that unknown does not establish a missing native foundation capability. |
| SDK lacks Workflow/other capabilities after an empty field search | The narrow empty grep is inconclusive. No blanket unavailability claim is accepted. Select the documented native CLI path already exercised here. |
| Default SDK settings automatically load AGENTS.md | The cited feature documentation establishes CLAUDE.md and supported Claude settings/rules. AGENTS.md discovery cannot be generalized from this project's possible instruction links. |
| “No provider call made” during source research | The SDK examples/tests made no provider calls because they did not run. The Claude coordinator and workers did use model inference, accounted separately below. |
| Worker output token totals in the narrative | They describe a narrower message/phase view. The final cumulative native modelUsage is the retained accounting view; no child output total is added to it. |
| Source lookup shells returned success despite a missing tag or empty extraction | Preserve the inner HTTP 404/empty outputs. A final shell exit of zero does not turn those searches into successful source findings. |
| Initial discovery matched the generated catalog HTML | Native output clipping retained the oversized result privately. This is an observed efficiency defect, not evidence of optimal context use. |

The settings and authentication boundaries above are supported by the current
[SDK feature documentation](https://code.claude.com/docs/en/agent-sdk/claude-code-features)
and [SDK overview](https://code.claude.com/docs/en/agent-sdk/overview). No accounts,
permissions or provider configuration were changed to resolve these wording
issues.

## Accounting and evidence boundary

The native process exited zero, without timeout, from 15:44:16.244799 to
15:52:03.036388 UTC (466.792 seconds). Two native result events share the same
cumulative modelUsage. Count the last once: **2,078,181 reported tokens** across
ordinary input, cache creation, cache reads and output. Thinking is already a
subset of output. Auxiliary Haiku activity remains included as reported.

The retained native API-equivalent estimate is not a subscription charge.
The Sonnet worker's deduplicated usage matches its cumulative model entry.
The Opus worker's input/cache categories match, but persisted output reconstructs
22,766 tokens versus 23,081 in the cumulative entry: a 315-token difference
remains unresolved. Retain the reported total without claiming exact reconciliation.
Codex coordination, independent reviewers and publication are outside this
native invocation's denominator. There was no matched baseline, so session and
lifetime tokens saved are null. A completed research Workflow establishes
source-review execution, not the correctness of every finding or whole-stack E2E.

Existing writing/recovery and selective-context receipts are reused without
changing their bytes or turning local fixtures into upstream test suites. New
catalog validation checks establish structural consistency only.

An independent read-only reviewer inspected the original streams, child records,
source responses and this patch. Supported findings were the stale recovery
priority, encoded project-path redaction, recorded effort fields and the
315-token accounting difference; the changes above address each. Agreement
alone does not replace the source and native observations.
