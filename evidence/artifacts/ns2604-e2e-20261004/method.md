# NS2604 verified foundation E2E method

This publication preserves the historical 2026-10-04 qualification of 80 foundation
slots across 15 executor units. Its north-star action is to make the native
foundation's remaining work recoverable for complex engineering, US-equities
research and historical simulation. Publication performs artifact inspection and
structural validation; it does not repeat host probes or model runs.

## Roles, model records and dates

| Stage | Retained model identifier | Record and scope |
| --- | --- | --- |
| Executors | claude-sonnet-5-5 | Unit evidence metadata, including observe-eval-1.json's executor.model and context-3.json's executor label. Claude Sonnet executors retained native command results and output excerpts. |
| Independent reviewers | cx/gpt-6.1-sol-max; requested_effort=max | All 15 review/<unit>/out.jsonl result records carry this exact requested route, model_inference_submitted=true and status=completed. This is the recorded gateway request identifier; no resolved backend identifier is inferred. |
| Adjudicator | claude-opus-5-5; effort=max; agent_type=evidence-reviewer | Workflow runs wf_8bf450a9-d1e (17 agents) and wf_cdbf70a0-02c (5 agents) retain the resolved model and agent type. The workflow script requests opus at max effort; adjudication.json retains all 22 judgments. |

The host observation window supplied for this run is **2026-10-04 19:10–20:10Z**.
For example, clients-1.json records 19:10:37Z–19:28:37Z. The retained reviewer
driver log records 15 starts between 19:26:33Z and 19:39:33Z; it does not retain
completion timestamps. Each review's own result record reports completion.
The final merge's own as_of is **2026-10-04T20:26:16Z**. Publication is dated
2026-10-04. Adjudication run wf_8bf450a9-d1e started at
2026-10-04T20:06:45Z and completed at 2026-10-04T20:20:30Z;
wf_cdbf70a0-02c started at 2026-10-04T20:08:29Z and completed at
2026-10-04T20:19:31Z. These review times do not extend the host observation window.

## Original procedure and public projection

The supplied e2e_merge.py is the source of the aggregation procedure. units.json
fixes the denominator. Executor labels come from executor-status.json's
schema-checked workflow returns, with unit evidence as the original procedure's
fallback. Each review-<unit>.json supplies the independent reviewed_status.
A matching adjudication.json entry overrides that review's final status and fixes;
the resulting status_source is adjudicated, otherwise reviewer.

The publisher compared all 80 status chains against the original unit lists,
schema-checked executor labels, separate review records and 22 adjudications,
then reproduced the final counts and per-layer table. It did not execute
e2e_merge.py, which writes into its private source directory.

slots.json retains the executor label, review label, final label, final source,
fix, fix_kind and at most four cited sources per slot. Its agree field compares
the executor with the original reviewer, even after adjudication. A false value
therefore need not be an unresolved dispute. All 22 disagreements have
adjudications; zero remain open. Of the 22 adjudications, 14 kept the reviewer's
status and 8 took the executor's status; none selected a third status.

The public reason uses the adjudicator's reason when an adjudication exists,
otherwise the reviewer's. It is sanitized, whitespace-normalized and limited to
60 whitespace-delimited words, including an ellipsis when shortened. Fix text
retains the original merge's 900-character bound before sanitization. Sources
prefer adjudication citations, add reviewer citations, remove duplicates and
retain at most four, prioritizing upstream URLs. Full original source hashes are
in the receipt; the compact text is not the complete underlying command record.

## Status definitions and arithmetic

| Status | Meaning in this qualification | Numerator |
| --- | --- | --- |
| READY | Present at the applicable version, passing the tool's upstream acceptance, wired into the native workflow, and used in a fresh headless session when client-facing. | Yes |
| PARTIAL | Some presence, acceptance, wiring or use is supported; a required part remains incomplete or unsupported. | No |
| FAIL | A required capability is absent, broken or fails the recorded acceptance, without an adjudicated hold explaining its disposition. | No |
| BY_DESIGN | An explicitly documented exclusion or alternative is intentionally outside the deployed scope. This is a disposition, not proof of execution. | Yes |
| INTERIM | Held by design pending agreed work or a gate. An absent or incomplete held tool does not count as ready. | No |
| UNJUDGED | Missing or invalid final judgment. None occur here, but these slots remain in the denominator. | No |

Readiness = (READY + BY_DESIGN) / all 80 slots in scope.
Here (18 + 12) / 80 = 30 / 80 = 37.5%, rounded half up to **38%**.
The original integer calculation is (200 * ready + total) // (2 * total).
The table is a policy readiness measure including designed exclusions, not the
percentage of tools that executed successfully. INTERIM's 17 held slots remain
in the denominator.

## Fix scope and remaining provenance

There are 33 open PARTIAL/FAIL slots. Their merged fix_kind values are 25 plan
and 8 host. Across all 80 slots the raw codes are 30 plan, 8 host and 42 none.
Of 41 nonempty fix texts, three READY/none entries explicitly require no fix;
four INTERIM/plan entries and one READY/plan entry are outside the 33 open slots.

fixes.json ships in this PR and lists the 33 open slots after adjudication:
25 repository-plan and 8 host fixes. The earlier 30 plan / 11 host figure counted
41 PARTIAL/FAIL slots at the reviewer stage, before adjudication.
Four INTERIM token slots are held for PR #684: context-supply, command-output,
output-compression and code-index. PR #684 has not merged. The two open token
slots have separate fixes: ccusage (FAIL, plan) and statusline (PARTIAL, host).

review-prompt.txt is a sanitized copy of the original review template.
adjudication-prompt.md (added by the coordinator) is the prompt template as run, taken from the adjudication
workflow script, with run-specific values as placeholders: Claude Opus 5.5 (`opus`) at effort `max`, agent type
evidence-reviewer, one agent per disputed slot, in runs wf_8bf450a9-d1e (17 agents)
and wf_cdbf70a0-02c (5 agents). Their private record hashes are retained in the
receipt under the run ids, without private host paths.

## Sanitization, evidence limits and coverage

Concrete home and user-profile paths, including ~/ paths, become <host path>;
local user identities become <user>; email addresses become <email>.
The machine label NativeStack2604 is retained consistently and is not masked.
Technical paths, loopback URLs, API routes and portable shell-variable forms
remain intact, including /dev/null, /etc/wsl.conf and
unix://$XDG_RUNTIME_DIR/docker.sock. Private scratch-file citations use
source-relative filenames rather than host locations.
Public upstream repository locators remain citations. Private-content patterns
from scripts/validate.py are applied without printing matched values. No raw
executor transcripts, native session streams, credential files or credential
values are published. Model metadata was extracted from reviewer event records
without copying their responses or streams.

This is native observation by the executors, independent model review of retained
evidence, and adjudication. It is **not an upstream benchmark**, an independent
re-execution on the host, a new provider run or proof that pending fixes landed.
The acceptance-evidence policy's classes and boundaries apply:
[acceptance-evidence-policy.md](../../../docs/acceptance-evidence-policy.md).

The completeness check covers all 15 units, 80 slot chains, 80 reviews, 22
adjudications, the full denominator, failed conditions, designed exclusions and
held slots. The adjudication prompt as run, resolved adjudicator model, run
timestamps and separate fix list are retained. Missing modalities remain fresh
native replication and upstream benchmark acceptance. No new harness, runtime
or dependency is adopted.

## Publication checks

The original publication's private-content scanner passed all eight deliverable
files with zero hits, and its five receipt/validation test modules passed 291
tests with no skips. The repair round scanned all eight files with zero private
content or login-name hits; the four requested test modules passed 277 tests with
no skips. These results are recorded separately in the receipt. The original
source hashes were rechecked unchanged. The required git diff --check returned
exit 0.

Untracked files were also checked with git diff --no-index --check against the
empty file. An initial wrapper treated exit 1 as failure; that classification was
corrected after reading the [official Git diff manual](https://git-scm.com/docs/git-diff):
no-index enables difference exit codes. All eight native checks returned exit 1
for new content with zero whitespace diagnostics. The coordinator registers all
eight published files in the PR's final registry-only commit, and full
repository validation passes at that head. Before that synchronization, the
bounded repair round's validation of its working tree returned exit 1 with 16
expected registry-drift errors: changed hashes/byte counts and mirrored
claim/limitations.
