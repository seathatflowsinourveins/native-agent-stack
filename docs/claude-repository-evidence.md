# Live Claude: per-repository evidence for every selected component, September 21

The [per-repository report](ecosystem/claude-repository-evidence.html) gives every
selected catalog component one row: the upstream commands that ran natively on the
source host, their returned results and declared assertions, the dashboard views that
were opened and reviewed, the component's lifetime token figures where a native
counter exists, and the selection evidence recorded for it. It extends the
[38-row report](claude-upstream-checks.md), which stays as published.

It covers **70 rows: the 68 selected components plus two supporting rows** (`uv` and
the TypeSafe skill). **47 rows are functional**: a functional-class command exited 0
**and** its declared assertion passed. **Ten are readiness** (version, sign-in,
import, listing, health or a pinned checkout only), **three are version/help only**, and **ten have no
local execution evidence** (seven not installed on this host, one macOS-only, one
removed, one source-only reference). Exit 0 alone is never counted as a functional
check. One command is retained as failing: `dagu validate` rejects the equity
research DAG under 2.16.6. The [compact summary](../evidence/artifacts/claude-repository-evidence-20260921/summary.json)
lists every row; the [structured results](../evidence/artifacts/claude-repository-evidence-20260921/results.json)
keep each command's arguments, exit status, duration, bounded displayed excerpt,
assertion with expected and observed values, and both hashes.

## Upstream commands and assertions

Probes are declared in a linted spec: a functional command must name the capability
it exercises and carry an assertion; shapes that mask failure (`|| echo`, a trailing
`echo` without an explicit exit, `| head`) and verbs that change state (service
lifecycle, provider model calls, repository writes, notifications) are rejected
before anything runs. Live counts are asserted with `>=` and the observed value is
recorded; equality is reserved for deterministic results. Scanners also run against a
known-bad fixture, because zero findings alone proves nothing. Serena and Beads ran
against disposable projects. No probe made a provider model call or changed a
service; exactly one spent an account credit (one Tavily search).

A check that does not invoke the component is labelled a local integration check and
never counts toward a row. The publication review found two such checks counted as
functional: LEAN's was the catalog's unit test over retained outputs, and alpaca-py's
was an order-contract script that imports nothing from the SDK. LEAN is now a readiness
row (pinned checkout, built launcher; no LEAN backtest was run by this report) and
alpaca-py rests on a real offline SDK request-model call.

Seven rows keep earlier observations as superseded rather than overwritten, including
the author's own errors: a replay pointed at the wrong input (the launcher refused it
on a receipt-hash mismatch), an assertion that read stdout while the tool printed to
stderr, a rerun that omitted two cost allowances, the two miscounted local checks, and a
live Qdrant count that grew from 396 to 465 while another session re-indexed.

## Dashboards

Twenty-one loopback views were captured in a real browser and every image was opened
and described; each review is bound to the image by sha256 and names one value
checked against that component's command result. Fourteen public screenshots are in
the [artifact directory](../evidence/artifacts/claude-repository-evidence-20260921/);
seven private views (memory, session archive, notifications, gateway, tool surfaces)
stay on the source host. Recorded anomalies remain visible: Dagu's Executions list
shows no runs while its own API returns nine and the CLI returns two (the per-DAG
page shows the run); the static SocratiCode graph page is a stale export (29 files
against 77 in the live graph); Grafana's SDK panels render at 72 hours, Loki's
lookback.

## Lifetime figures and selection evidence

Seven native estimate scopes and 46 exact artifact comparisons are shown as recorded,
with 13 comparisons rendered as losses. They are each tool's own non-additive
estimate: there is no combined figure, and provider-token savings are not measured.

Selection evidence is shown per row as a chain (audit, adversarial verifier, second
model family) with a comparison tier. Only three rows have a local measurement (QMD,
TOON and jCodeMunch); 14 rest on a recorded feature comparison, 24 have no comparison,
four are not contestable (Qdrant is kept because its consumer supports no other
store), and 25 rows have no audit record. Ten earlier "keep" stamps remain overturned
to keep-but-compare. The report makes no universal claim about any repository.

## Review and provenance

Before publication the source was reviewed three ways: a saved review workflow
(one corrected claim, three defects), a native Codex review (one finding) and a
three-reviewer content audit of all selection rows, all screenshots and the
convergence text (30 findings). The publication branch was then reviewed again by a
native Codex review and two evidence reviewers. Every supported finding was fixed and is listed in
the report's Convergence and Method tabs. The
[projection provenance](../evidence/artifacts/claude-repository-evidence-20260921/provenance.json)
records the source commit and file hashes, the names, sizes and hashes of all 266
privately retained output streams (all 115 current stdout hashes match a retained
stream), and each change made for this public projection. The page carries a
Content-Security-Policy that admits only its own script by hash; its data block is
not executable and every displayed string is escaped.

This is dated source-host evidence. It is not an installation certificate for another
PC, a lifecycle acceptance, or a measurement of provider usage.
