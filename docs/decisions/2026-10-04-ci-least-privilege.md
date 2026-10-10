# Decision: least-privilege GitHub Actions for agent-authored pull requests (2026-10-04)

**Decided by:** the coordinator's bounded CI-hardening package (branch `c5/ci-hardening`, base `1a64e8f3e`), from the
cross-family consensus of bounded job 004 and the repository's top rule (AGENTS.md: current upstream practice, by
research convergence, is the source of truth).

**Scope:** all 21 files under `.github/workflows/`; the new tripwire `tests/test_workflow_policy.py`; the existing
workflow tests that pinned the old workflow-level `contents: read` or the combined cache action; the sentences of
`docs/github-automation.md` and the checklist line of `.github/pull_request_template.md` that described the old
top-level `contents: read`; this record.

## Consensus

The OpenHands resolver pushes an agent-written commit to a branch of this repository and opens a draft pull request,
so the repository's `pull_request` workflows run that code on GitHub-hosted runners. Bounded job 004 (GPT-6.1 Sol at
max effort, read-only, 2026-10-04T03:03Z) judged the plan "accept CI execution within read-only bounds, enforced by a
tripwire test and zizmor in CI". It voted **disagree with that plan's sufficiency**: a check that runs inside pull
request CI runs on the commit under test, which can change the check, so it cannot be the boundary. The vote accepted
the architecture once a trusted gate validates every commit **before** the push. Session 0c builds that gate in the
resolver (#489). This change is the defense-in-depth layer for `main`, which the job asked for in its
`extra_enforcement` list:

- `permissions: {}` by default and only the needed scope per job; reject write scopes and `id-token: write`;
- a pinned zizmor with protected configuration whose excessive-permissions, dangerous-triggers, cache-poisoning,
  artipacked and template-injection findings fail, with the tripwire kept as a regression check;
- runner, cache, credential-persistence and execution-limit policies (GitHub-hosted labels, no dynamic runner,
  timeouts, concurrency);
- `cache-mode: none` for agent execution where feasible, with privileged jobs kept from restoring untrusted state.

The job's five residual risks are restated, with what this change does about each, under "Residuals" below.

## Decision

### 1. No token scope by default

Every workflow except the two hash-bound ones (section 5) now sets `permissions: {}` at the top level, and every job
that checks out or reads this repository grants `contents: read` itself. GitHub sets every unspecified scope to none
once any scope is given, and `{}` disables them all (workflow syntax, `permissions`); zizmor's excessive-permissions
remediation says workflows "should almost always set `permissions: {}` at the workflow level ... and then set specific
job-level permissions as needed". Jobs that use no token keep none: `action-compatibility.yml`'s `python` and `go` jobs
(no checkout; their setup actions read public manifests) and both copies of the `sota-sources` job (they read the event
payload only).

The existing write grants stay on their own jobs, and none runs on `pull_request`:

| Job | Grant | Why it is not reachable from a pull request |
| --- | --- | --- |
| `catalog-freshness.yml:propose` | `contents: write`, `pull-requests: write` | schedule and dispatch only |
| `claude-pr-review.yml:review` (2026-10-08) | `id-token: write` | dispatch only, on `main`, by the owner; federation, not attestation (addendum below) |
| `harness-audit.yml:audit` (2026-10-08) | `id-token: write` (`issues: write` removed 2026-10-08, see the addendum below) | schedule and dispatch only, on `main`; federation, not attestation ("Federation exemption (2026-10-08)") |
| `publish-catalog.yml:publish` | `id-token: write`, `attestations: write` | tag push and dispatch only; attests provenance |
| `publish-catalog.yml:release` | `contents: write` | tag push only |
| `saturation-tracking.yml:issue` | `issues: write` | schedule and dispatch only |
| `scorecard.yml:analysis` | `security-events: write` | schedule, push to main and dispatch only |
| `security-scan.yml:osv-sarif-upload`, `zizmor-sarif-upload` | `security-events: write` | `if: ... github.event_name != 'pull_request'` |

### 2. Checkout credentials

Every `actions/checkout` step already had `persist-credentials: false`; the tripwire now requires it. One job pushes:
`catalog-freshness.yml:propose` sends the token for its single `git push` through `GIT_CONFIG_*` environment variables
and masks it, so its checkout also keeps `persist-credentials: false`. No job uses `persist-credentials: true`.

### 3. Caches

Pull request runs get no cache access: every workflow a pull request triggers sets `cache-mode: none` (workflow or job
level), the value job 004 named. GitHub enforces the mode with scoped cache tokens, and a skipped restore or save
never fails a step (workflow syntax, `cache-mode`; dependency caching, "Controlling cache access with `cache-mode`").
`publish-catalog.yml` sets it as well, so the attested archive can never restore cached state (zizmor cache-poisoning).

The one cache in use, `adoption-bootstrap.yml:bootstrap-macos`'s pinned embedding model, changed from the combined
`actions/cache` (which saves in its post step on every event) to `actions/cache/restore` before the bootstrap and
`actions/cache/save` after it, with `if: github.event_name != 'pull_request' && steps.embed-model-cache.outputs.cache-hit != 'true'`
and the restore step's `cache-primary-key` (actions/cache v6.1.0, `save/README.md`, "Always save cache"). A pull
request run restores the default branch's entry read-only, and bootstrap's `fetch()` re-verifies its SHA-256 before
use, as before. That job keeps GitHub's trigger default instead of a `cache-mode`: the key takes no expression
(kjanat/actionlint 1.17.0 rejects one), and `read` would also block the trusted-event save. Even so, a pull request's
cache entries are scoped to its merge ref and cannot reach `main`'s scope (dependency caching, "Restrictions for
accessing a cache"). No cache holds a secret.

### 4. Runners, timeouts, concurrency

Every job already ran on a literal `ubuntu-24.04` or `macos-15` label with a `timeout-minutes`; the tripwire now
requires one literal label from an exact allowlist of GitHub's documented standard hosted-runner labels in the ubuntu,
windows and macos families (20 labels; repair round 1) and an integer timeout from 1 to 360. Six workflows gained a top-level concurrency group: `native-foundation-e2e.yml` and `native-token-e2e.yml` use
the repository's pull-request pattern (cancel superseded pull request runs, never push or schedule runs), and
`native-service-reboot.yml`, `practice-references-freshness.yml`, `runtime-worker-skills-freshness.yml` and
`publish-catalog.yml` queue one run at a time and never cancel (per ref for `publish-catalog.yml`, so a started
publish and release always finish). Four workflows have no top-level group, by design:

- `catalog-freshness.yml` keeps its job-scoped group on `propose`: a workflow-level group would let a scheduled run
  replace a pending manual `open_pr: true` request (tests/test_catalog_freshness_propose.py,
  `test_no_top_level_workflow_concurrency_group`);
- `sota-sources-gate.yml` is a reusable workflow, whose `${{ github.workflow }}` is the caller's name;
- the two hash-bound workflows (section 5).

### 5. Two workflows stay byte-for-byte unchanged

`native-offhost-app-state.yml` and `native-offhost-restore.yml` are bound by SHA-256 in their recovery plans
(`offhost-app-state/plan.json`, `offhost-restore/hosted-plan.json`), which `tests/test_active_recovery_plans.py` checks
against the checkout. Refreshing those prospective bindings, as
[the 2026-09-26 hardening](2026-09-26-token-workflow-hardening.md) did, lies outside this package's paths. Both run on
`workflow_dispatch` only, keep a workflow-level `contents: read`, and meet every pull-request rule. The tripwire names
them in `HASH_BOUND` with the file that binds each, and `test_hash_bound_exemptions_are_still_bound` fails as soon as a
binding moves on, so the exemption cannot outlive it.

### 6. zizmor

zizmor 1.30.1 runs in two CI jobs: `validate.yml:validate` (the required check, with online audits and a read-only
token) and `security-scan.yml:zizmor-online` (SARIF off pull requests). It is installed from
`.github/requirements-ci.txt` with `--require-hashes`. The repository has no zizmor configuration file, and both
invocations pass `--no-config --no-ignores`, so neither a `zizmor.yml` nor an inline ignore comment in the commit under
test can suppress a finding. That is stronger than a protected configuration file, which the commit could edit. Under
the regular persona every finding fails the gate (exit 11 to 14). The five audits the consensus names also run at the
pedantic persona in `tests/test_workflow_policy.py`, inside the same required job's unittest step, because the regular
persona misses some shapes: a single job under a workflow-level `write-all` is reported only at pedantic (measured with
zizmor 1.30.1 on 2026-10-04). Each of the five has a planted fixture that must fire. The tripwire also fails on a zizmor
invocation without `--no-config` and `--no-ignores`, on a configuration file, an ignore comment or a `ZIZMOR_*`
environment override in a workflow, and on an unpinned analyzer.

Measured offline (`zizmor --offline --no-config --no-ignores --strict-collection .`), base commit to this change:
regular persona 0 to 0 findings; pedantic 45 to 39. All 39 that remain are informational or low code smells, and none
comes from the five audits:

- 36 `anonymous-definition`: unnamed jobs. A job's `name:` becomes its check context, and the main ruleset requires
  eight contexts by job id.
- 3 `concurrency-limits`: `catalog-freshness.yml` and the two hash-bound workflows (section 4; zizmor does not flag
  the reusable `sota-sources-gate.yml`).

They are recorded here rather than in a configuration file, which the gate does not read.

### 7. The tripwire

`tests/test_workflow_policy.py` parses every `*.yml` and `*.yaml` workflow with a strict YAML-subset loader that needs
no third-party package (CI's interpreters do not all carry PyYAML). A construct outside the subset is an `unparseable`
violation, never a guess: anchors, aliases, tags, flow mappings other than `{}`, duplicate keys, tabs, document markers
and multi-line flow scalars. PyYAML 6.0.3 accepts five of the six planted constructs; GitHub's own parser may as well,
so failing closed matters. Where PyYAML is importable the loader is cross-checked against it. Locally both agree on all
21 workflows and on all 39 parseable planted and accepted variants. The rules:

| Rule | Fails on |
| --- | --- |
| `workflow-permissions-missing` | no top-level `permissions` |
| `workflow-permissions-not-empty` | top-level permissions other than `{}` |
| `pull-request-write-scope` | a job that runs on `pull_request` (or `workflow_call`) holding a write scope or `id-token: write` |
| `id-token-write` | `id-token: write` outside a job that attests provenance off pull requests |
| `dangerous-trigger` | `pull_request_target` or `workflow_run` |
| `pull-request-secret` | a secret other than `GITHUB_TOKEN`, `secrets: inherit` or the whole `secrets` context in a pull request workflow, found in the decoded values (YAML escapes resolved, block scalars folded) with the raw text, comments included, as a second net |
| `checkout-persist-credentials` | `actions/checkout` without `persist-credentials: false` |
| `runner-label` | a `runs-on` that is not one literal label from the exact allowlist of GitHub's documented hosted-runner labels |
| `job-timeout` | a missing or non-integer `timeout-minutes` |
| `pull-request-cache-write` | a cache write or a write-capable `cache-mode` in a pull request job |
| `pull-request-cache-mode` | a pull request job without `cache-mode` `none` or `read` |
| `workflow-concurrency` | no top-level concurrency (reusable workflows excepted) |
| `unparseable` | anything outside the strict subset |

A job counts as off pull requests only when its `if:` is one whole `${{ ... }}` expression or a bare expression, and a
top-level `&&` operand of it is exactly `github.event_name != 'pull_request'`. A value that mixes literal text with
`${{ }}` never counts: actions/runner evaluates it as a `format()` string, which is truthy. Each rule has at least one
planted workflow, 39 in all, written to a temporary directory, which must fail with exactly that rule and nothing else.
Six accepted variants must pass, one for each guard the rules allow. Exemptions are keyed by file (and job) name. A test fails once an exemption no longer suppresses anything, and
the same bytes under another file name fail. The write grants, and the one job that pushes, are pinned as reviewed
inventories.

## Changes per workflow

| Workflow | Top-level `permissions` | Job grants added | `cache-mode` | Concurrency | Other |
| --- | --- | --- | --- | --- | --- |
| `action-compatibility.yml` | `{}` | none (no checkout) | `none` | kept | |
| `adoption-bootstrap.yml` | `{}` | `contents: read` on all 5 jobs | `none` on 4 jobs | kept | restore/save cache split |
| `catalog-freshness.yml` | `{}` | `freshness: contents: read` | | job-scoped (kept) | |
| `claude-pr-review.yml` (added 2026-10-08) | `{}` | `review`: `contents: read`, `pull-requests: read`, `id-token: write` | | added | `id-token-write` exemption |
| `dependency-review.yml` | `{}` | `contents: read` | `none` | kept | |
| `hardware-profile-smoke.yml` | `{}` | `contents: read` on both jobs | `none` | kept | |
| `harness-audit.yml` (added 2026-10-08) | `{}` | `audit`: `contents: read`, `id-token: write` (`issues: write` removed 2026-10-08, addendum below) | | added | `id-token-write` exemption |
| `native-foundation-e2e.yml` | `{}` | `contents: read` | `none` | added | |
| `native-offhost-app-state.yml` | unchanged (`contents: read`) | | | | hash-bound |
| `native-offhost-restore.yml` | unchanged (`contents: read`) | | | | hash-bound |
| `native-service-reboot.yml` | `{}` | `contents: read` on both jobs | | added | |
| `native-token-e2e.yml` | `{}` | `contents: read` | `none` | added | |
| `practice-references-freshness.yml` | `{}` | `contents: read` | | added | |
| `pr-metadata.yml` (added 2026-10-09, PR #706) | `{}` | `verdict-review-gate`: `contents: read`, `pull-requests: read`; `sota-sources`: `pull-requests: read` | `none` | added, `queue: max` | current PR body and base read through REST |
| `publish-catalog.yml` | `{}` | (already job-scoped) | `none` | added, never cancels | |
| `receipt-staleness.yml` | `{}` | (already `contents: read`) | `none` | kept | |
| `runtime-worker-skills-freshness.yml` | `{}` | `contents: read` | | added | |
| `saturation-tracking.yml` | `{}` | (already job-scoped) | | kept | |
| `scorecard.yml` | `{}` | (already job-scoped) | | kept | |
| `security-scan.yml` | `{}` | (already job-scoped) | `none` | kept | |
| `sota-sources-gate.yml` | `{}` | `sota-sources`: `pull-requests: read` (PR #706) | `none` | none (reusable) | current PR body read through REST |
| `supply-chain.yml` | `{}` | `contents: read` | `none` | kept | |
| `token-report.yml` | `{}` | `contents: read` | `none` | kept | |
| `validate.yml` | `{}` | `contents: read` on all 4 jobs | `none` | kept | metadata gates move to `pr-metadata.yml` in PR #706 |

Tests changed to follow the new layout, without loosening any assertion: `tests/test_workflow_hardening.py` (top-level
`{}` instead of `contents: read` in five classes, and `{}` accepted as the one inline permissions form),
`tests/test_workflow_security_coverage.py` (the dropped-permissions control now drops both entries, and the measured
effect of dropping each alone is in a comment and covered by the tripwire), `tests/test_sota_sources_gate.py`,
`tests/test_saturation_ledger.py`, `tests/test_catalog_freshness_propose.py`, `tests/test_practice_references.py`, and
`tests/test_adoption_bootstrap_macos.py` (restore only, plus a new test for the guarded save).

## Residuals

Job 004's residual risks, and what this change does about them:

1. **The commit under test can edit the workflows and this tripwire.** Unchanged by design: the trusted pre-push gate
   (#489) is the control. This layer catches regressions on `main` and in human pull requests, and the required checks
   still gate merging.
2. **Network-enabled test code can read the checkout and whatever credentials a job holds.** Narrowed: no pull request
   job holds a secret or a write scope; tokens grant read scopes or none and are never persisted to disk. Egress
   stays audit-only (harden-runner); confidentiality of public-repository source is not at stake.
3. **Caches.** Closed for pull request jobs (`cache-mode: none`, or restore-only with the save step guarded off pull
   requests), and the attested release restores nothing. A job-level `cache-mode` override on a pull request job fails
   the tripwire.
4. **Artifacts, logs and the PR body stay attacker-controlled.** No workflow uses `workflow_run`, and the tripwire
   rejects it; the PR body reaches only `actions/github-script` as data. The release job rebuilds nothing from pull
   request artifacts (tag push only).
5. **Runner policy.** GitHub-hosted labels only, no dynamic `runs-on`, timeouts on every job, concurrency where it
   fits. The label check is an exact allowlist of documented hosted labels, so a hosted-style name such as
   `ubuntu-owned-private` fails. It still checks names only, and cannot prove where a job runs if a self-hosted runner
   were registered under one of those exact labels. The repository registers no self-hosted runner; the repository
   settings are the control there.

Also not covered here: the two hash-bound workflows keep a workflow-level `contents: read` and no concurrency until
their bindings are refreshed (section 5); `bootstrap-macos` keeps GitHub's trigger cache default (section 3); no hosted
run of the changed workflows exists yet. Their first pull request runs, `action-compatibility.yml` included (its path
filter covers itself), are the first evidence that `{}` jobs and `cache-mode` behave as documented on this repository.

## Repair round 1 (2026-10-04)

The cross-family review of `deea517e` (job-005, GPT-6.1 Sol at max) returned REJECT, with one P1 and two P2 findings in
`tests/test_workflow_policy.py`. All three are fixed, each with planted controls that must fail with the rule named:

1. **P1: the secrets rule read only the raw text.** A reference written with YAML escapes, such as
   `TOKEN: "${{ secrets.NPM_TOKEN }}"`, decodes to `${{ secrets.NPM_TOKEN }}`, which GitHub evaluates. The raw
   scan saw nothing, and all 24 policy tests passed with that fixture in `token-report.yml`. The rule now reads every
   decoded key, value and sequence item the loader returns (`decoded_strings`, `inherited_secrets`) and keeps the raw
   scan, which also covers comments, as a second net. New controls cover a `\u` escape, a `\x` escape, a folded block
   scalar, a literal block scalar, and `secrets: inherit` under a quoted and under an escaped key.
2. **P2: the runner check was a prefix pattern.** `runs-on: ubuntu-owned-private` passed. It is now an exact allowlist
   of the 20 standard hosted labels GitHub documents in the three families (section 4). New control:
   `ubuntu-owned-private`.
3. **P2: `excludes_pull_request` accepted a mixed value.** `${{ !cancelled() }} && github.event_name != 'pull_request'`
   counted as excluding pull requests. But actions/runner's `TemplateReader.ParseScalar` turns a value with literal
   text and an expression into a `format()` string, which is truthy. Now only a whole `${{ ... }}` expression or a bare
   expression can exclude pull requests. New controls: the reviewer's job-level case, and the same shape on a cache
   save step.

## Reachability rules and repair round 2 (2026-10-04, superseding #682)

#682 (held at `6e166809`) proposed a second, text-based tripwire in `tests/test_workflow_hardening.py` for the jobs a
pull request can start. The coordinator chose to fold its assertions into this module instead, as rules on the parsed
workflows with planted controls, so the repository keeps one workflow reader. Most of #682's checks were rules here
already; three were not, and now are:

| Rule | Fails on |
| --- | --- |
| `pull-request-environment` | an `environment:` on a job that a pull_request-family event reaches, whatever its `if:` |
| `pull-request-remote-workflow` | such a job calling a reusable workflow by anything but `./.github/workflows/{file}` or `$/.github/workflows/{file}` |
| `comment-event-secret` | a secret other than `GITHUB_TOKEN`, `secrets: inherit` or the whole `secrets` context in a workflow that `issue_comment`, `pull_request_review` or `pull_request_review_comment` triggers, read as `pull-request-secret` reads it |

**Reachability** (`reachable()`, over the directory as a whole). The pull_request family is #682's event set: each
`pull_request*` event, `issue_comment` and `workflow_run`. A workflow is reached by one of those triggers, then through
each `./` or `$/` call a reached job makes, transitively and whatever the callee's own triggers, since a called
workflow runs in its caller's event context. Last, a `workflow_call` trigger alone counts, as `PULL_REQUEST_EVENTS`
already counts it: the scaffold's `sota-sources.yml.template` calls `sota-sources-gate.yml` from other repositories'
`pull_request` workflows. That last step is stricter than #682, which reached a reusable workflow only through a
caller in the same directory. The two job rules do not credit `if:`: `github.event_name != 'pull_request'` still lets
`issue_comment` and review runs through, and in a called workflow `github.event_name` is the caller's.

**Why these three.** Environment secrets "are only available to workflow jobs that reference the environment", an
`environment` on a reusable workflow's job uses that environment's secret "and not the secret passed from the caller
workflow", and an environment's required reviewers can release its secrets to the job they approve. A remote reusable
workflow's file is never read here, so neither can be checked in it; zizmor's `unpinned-uses` only asks for a SHA pin,
which the planted remote call has. An `issue_comment` run uses the default branch's workflow, and a review run from a
same-repository branch gets the repository's secrets (a fork's run gets none); both run on text that outside users
write. `GITHUB_TOKEN` stays allowed in those workflows, by property or by index, as in `pull-request-secret`: it is
also `github.token`, and its scopes are what `pull-request-write-scope` and the reviewed write inventory bound. On
`6af8e55b` no workflow declares an environment, calls a reusable workflow from a job, or has a comment or review
trigger, so all three rules pass.

**Repair round 2: the coordinator's P2 residuals on #681** (from the cross-family review of `de0b0043`).

1. `excludes_pull_request` stripped whitespace before deciding whether one expression filled the value, so
   `" ${{ github.event_name != 'pull_request' }}"`, the same with a trailing space, and the line break a `|` block
   scalar keeps all counted as excluding pull requests. `ParseScalar` keeps each as a literal segment of a truthy
   `format()` string.
2. Its `}}` substring check refused valid guards such as
   `github.event_name != 'pull_request' && contains('a}}b', 'a')`. `ParseScalar` closes an expression only at a `}}`
   outside a single-quoted string literal.

The helper now follows `ParseScalar`: a value either holds no `${{` (a bare expression, where whitespace does not
matter) or opens one at its first character and closes it, quote-aware, at its last. A `${{` anywhere else, even
quoted in a bare value, starts a segment, and the expression's text outside string literals may hold no delimiter.
New planted controls: a leading and a trailing space at job and at cache-step level, and the block scalar. New accepted
variants: a quoted `}}` in a job guard and in a cache-step guard.

**Cross-family review of #686 at `aeb5ba25`** (one repair round). The secrets scan that `pull-request-secret`,
`comment-event-secret` and `test_pull_request_jobs_hold_no_secret_and_no_write` share delimited expressions with the
regex `\$\{\{(.*?)\}\}`, which stops at the first `}}` even inside a string literal.

1. **P1.** `TOKEN: "${{ format('a}}b{0}', toJSON(secrets)) }}"` in a step's `env`, and
   `${{ format('a}}b{0}', secrets['NPM_TOKEN']) }}` in a reusable workflow's `secrets` mapping, gave no violation for
   any of the three comment and review events, nor `pull-request-secret` on `pull_request` (reproduced). Both are
   valid: `format()` reads a doubled brace as one brace (Expressions, `format`), and `ParseScalar` does not close an
   expression inside a literal. `secret_references()` now reads each expression as `expressions()` delimits it, with
   `expression_end()`, the scan repair round 2 introduced; an expression that never closes is read to the end.
2. **P2.** `secrets['GITHUB_TOKEN']` was a violation while `secrets.GITHUB_TOKEN` passed, although index and property
   syntax access the same value (Contexts reference, "Available contexts"). Index access by one string literal now
   names the secret it indexes (`SECRET_INDEX`; a `''` escape is unescaped, and a double-quoted key, which GitHub's
   parser rejects, is read the same way), so the token passes in both forms. The whole context and an index that is
   not one literal, such as `secrets[format('{0}_TOKEN', 'GITHUB')]`, stay violations whatever they compute.

New planted controls: the reviewer's `env` form under `issue_comment`, `pull_request_review` and
`pull_request_review_comment`; the indexed secret after a quoted `}}` in a called workflow's `secrets` mapping; the
computed index; and the `env` form under `pull_request` for `pull-request-secret`. New accepted variants: the token by
single-quoted and by double-quoted index. A unit test covers both access forms, both kinds of whole-context access and
an unclosed expression.

**Controls.** 59 planted entries (20 new: 4, 2 and 8 for the new rules, 5 for repair round 2, 1 for
`pull-request-secret`), 15 accepted variants (9 new), and a reachability test that checks the caller is named and that
a call is followed through a `$/` hop to a callee without `workflow_call`. In a scratch copy, breaking each new rule's
predicate fails exactly that rule's planted controls (plus the reachability test for the environment rule); restoring
#681's helper fails the 5 repair-round-2 planted controls, the 2 accepted variants that go with them and 7 unit cases;
disabling call-following fails only the reachability test, because the `workflow_call` step still reaches the planted
callee. Restoring the old expression regex fails the 5 quoted-marker controls and 3 unit cases, and reading every index
as the whole context fails the 2 index-form variants and 5 unit cases. PyYAML 6.0.3 agrees with the loader on all 92
texts.

**Dependabot wording.** `2026-09-22-github-automation-closure.md` said fork and Dependabot pull requests get a
read-only token. A Dependabot run's token is read-only by default (it can be raised): GitHub documents raising it with
`permissions`. That sentence is qualified in place.

**Not carried from #682.** Its text-subset and job-layout checks: this module's loader parses every job, decodes
escapes and fails closed outside its subset. Its ban on `secrets.GITHUB_TOKEN` (above). Its check that a `./` callee is
a file in this directory: a `./` or `$/` path names a file at the caller's commit, and every file present is checked on
its own. Its pull-request write-scope allowlist, which ignored `if:`: `pull-request-write-scope` and `WRITE_GRANTS`
cover it here, crediting only the `github.event_name != 'pull_request'` conjunct. The pull request that supersedes
#682 maps each of its assertions.

**Alternatives.** zizmor 1.30.1's overlapping audits are general. `dangerous-triggers` flags `pull_request_target` and
`workflow_run`, as this module's `dangerous-trigger` rule does. `secrets-inherit` flags `secrets: inherit` wherever it
appears. `unpinned-uses` flags a remote call by branch or tag but passes one pinned by SHA. `self-repository` (new in
1.30.0) asks for `$/` instead of `./`, which is why both forms are local here. None flags an environment on a pull
request job or a secret in a comment-triggered workflow, and `secrets-outside-env` pulls the other way, toward
environment-scoped secrets, which these rules allow off the pull_request family.

**Overturn.**

- A job that a pull_request-family event reaches needs an environment or a remote reusable workflow: move it to a
  workflow no such event starts, or add an `EXEMPTIONS` entry with its reason (`test_each_exemption_is_still_needed`
  fails once the entry suppresses nothing).
- A reusable workflow here needs an environment and no pull_request workflow calls it, here or elsewhere: exempt it by
  name, or drop `reachable()`'s `workflow_call` step, which leaves #682's computation.
- The coordinator decides `comment-event-secret` must refuse `secrets.GITHUB_TOKEN` too: give that rule a scan that
  keeps it.
- GitHub adds or changes a same-repository call form (`LOCAL_WORKFLOW_PREFIXES`), or actions/runner changes
  `ParseScalar`'s scan (`expression_end`, `excludes_pull_request`): re-read the source and follow it.

**Evidence class.** `local_integration`: `tests.test_workflow_policy` and `tests.test_workflow_hardening` with the
system Python (no PyYAML), and the loader cross-check with PyYAML 6.0.3 through uv. `synthetic`: the planted controls
and the scratch-copy mutations. `source_review`: the sources below. No workflow changed, and no hosted run exercises a
new rule yet.

**Sources** (read 2026-10-04 at 08:18Z):

- GitHub, Secure use reference (formerly "Security hardening for GitHub Actions"; the old URL redirects here):
  <https://docs.github.com/en/actions/reference/security/secure-use>: untrusted input, `pull_request_target` and
  `workflow_run`, required reviewers for environment secrets.
- GitHub, Using secrets in GitHub Actions:
  <https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets>.
- GitHub, Reuse workflows, "Using inputs and secrets in a reusable workflow" (`secrets: inherit`, environment secrets):
  <https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows>; Reusing workflow configurations,
  "`github` context": <https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations>;
  Workflow syntax, `jobs.<job_id>.uses` and `jobs.<job_id>.secrets.inherit`:
  <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>.
- GitHub, Managing environments for deployment:
  <https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments>; Deployments
  and environments, "Environment secrets":
  <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>.
- GitHub, Events that trigger workflows (`issue_comment`, `pull_request_review`, `pull_request_review_comment`,
  `workflow_run`): <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>.
- GitHub, Troubleshooting Dependabot on GitHub Actions, "Changing `GITHUB_TOKEN` permissions":
  <https://docs.github.com/en/code-security/reference/supply-chain-security/troubleshoot-dependabot/dependabot-on-actions#changing-github_token-permissions>.
- zizmor `docs/audits.md` at `v1.30.1` (`99a054ed9283c90abdd2d5b9fb5101d27dde9783`): `dangerous-triggers`,
  `secrets-inherit`, `unpinned-uses`, `self-repository`, `secrets-outside-env` (<https://docs.zizmor.sh/audits/>).
- actions/runner `src/Sdk/DTObjectTemplating/ObjectTemplating/TemplateReader.cs` (`ParseScalar`) at
  `d7bc179baf11a02110b46cfbbc4040f74ac3f60a`.
- GitHub, Contexts reference, "Available contexts" (index and property dereference syntax):
  <https://docs.github.com/en/actions/reference/workflows-and-actions/contexts>; Evaluate expressions in workflows and
  actions, "Literals" (single-quoted strings only) and `format` (doubled braces):
  <https://docs.github.com/en/actions/reference/workflows-and-actions/expressions> (both read 2026-10-04 at 14:15Z).

## Federation exemption (2026-10-08)

`harness-audit.yml` runs anthropics/claude-code-action v1.0.245 weekly and on dispatch, authenticated by Anthropic
workload identity federation: the action exchanges the job's GitHub OIDC token for a short-lived Claude API token, so
no Anthropic key is stored in this repository. That needs `id-token: write` on a job that attests nothing, which
`id-token-write` refuses, so `EXEMPTIONS` names the one job (`harness-audit.yml:audit`) with its reason and
`test_each_exemption_is_still_needed` drops the entry once it suppresses nothing. The job's write grant,
`id-token: write`, is in the reviewed inventory (it also held `issues: write` for its scorecard issue until the
bounded audit removed it on 2026-10-08; addendum below).

The federation rule accepts workflows on this repository's `main` and never pull requests: it matches the OIDC subject
of a run on `main`, and a pull request run's subject ends in `:pull_request` instead (GitHub's OpenID Connect reference,
"Filtering for pull_request events" and "Filtering for a specific branch"). It has no `workflow_ref` condition, by
design, so other workflows on `main` may use it later. Which workflows may request an OIDC token is therefore governed
by the reviewed write-grant inventory (`id-token: write`) that `tests/test_workflow_policy.py` enforces, and the
`id-token-write` exemptions name each job that may request a token without an attestation (`harness-audit.yml:audit`,
and `claude-pr-review.yml:review` by the addendum below).

This repository was created on 2026-09-19, after GitHub's 2026-07-15 move to immutable subject claims, and
`GET repos/seathatflowsinourveins/native-agent-stack/actions/oidc/customization/sub` returned
`use_immutable_subject: true` on 2026-10-08 (03:37Z). A run on `main` therefore presents
`repo:seathatflowsinourveins@234074349/native-agent-stack@1376766892:ref:refs/heads/main`, and the rule's subject must
be that string: Anthropic matches `subject_prefix` exactly unless it ends in `*` (Workload identity federation,
"Match"), so the name-only form `repo:seathatflowsinourveins/native-agent-stack:ref:refs/heads/main` never matches.

**Overturn.** The audit moves to a flow that needs no OIDC token, or the workflow is removed: drop the exemption and
the `id-token: write` grant together (the inventory test and `test_each_exemption_is_still_needed` force both). A
second workflow that requests a token for this rule needs its own reviewed inventory entry and exemption.

Sources: anthropics/claude-code-action `action.yml` at `6fed3ca145920b639991cb756090506e1bcaf515` (v1.0.245: the four
federation inputs, and `anthropic_oidc_audience` defaulting to `https://api.anthropic.com`); GitHub, OpenID Connect
reference, <https://docs.github.com/en/actions/reference/security/oidc> (subject formats, the `workflow_ref` claim and
"Immutable subject claims"); Anthropic, Workload identity federation,
<https://platform.claude.com/docs/en/manage-claude/workload-identity-federation> ("Match"); all read 2026-10-08.

### Addendum (2026-10-08): a second job on the federation rule

`claude-pr-review.yml:review` requests a token for the same rule, so, as the Overturn paragraph above requires, it
has its own entry in the reviewed inventory (`id-token: write`, its only write grant) and its own `id-token-write`
exemption in `tests/test_workflow_policy.py`. It is not reachable from a pull request: its only trigger is a manual
dispatch, and its job requires `refs/heads/main` and the owner
([2026-10-08-claude-actions-pr-review.md](2026-10-08-claude-actions-pr-review.md)).

### Addendum (2026-10-09): the toolkit read on the federation rule

`claude-pr-toolkit-review.yml:review` requests a token for the same rule, so, as the Overturn paragraph above
requires, it has its own entry in the reviewed inventory (`id-token: write`, its only write grant) and its own
`id-token-write` exemption in `tests/test_workflow_policy.py`. Its only trigger is a manual dispatch, and its job
requires `refs/heads/main` and the owner
([2026-10-09-claude-actions-pr-toolkit-review.md](2026-10-09-claude-actions-pr-toolkit-review.md)).

### Addendum (2026-10-08): the audit job gives up `issues: write`

The two tables above listed `harness-audit.yml:audit` with `id-token: write` and `issues: write`, as it was added;
they now show the grant as removed. The
bounded audit ([2026-10-08-claude-actions-harness-audit-bounds.md](2026-10-08-claude-actions-harness-audit-bounds.md))
removes the model's `gh issue create` tool and the `issues: write` grant: the report goes to the job summary from a
model-free step. The job's only write grant is now `id-token: write`, the reviewed inventory in
`tests/test_workflow_policy.py` says so, and this exemption is unchanged. The action pin moves to v1.0.247
(`2dca132ff0e0c4094ce6048b422c6915a071210b`), whose federation inputs are the four named above.

## Alternatives considered

- **Keep workflow-level `contents: read`.** It already met OpenSSF Scorecard's Token-Permissions top score (read-only
  top level, writes declared per job). Rejected: every new job would inherit a scope it may not need, and the
  consensus and zizmor's remediation both name `{}`. Scorecard loses nothing: it records a top-level `{}` as the
  `none` level and logs it without a score reduction (`checks/raw/permissions.go`, `validatePermissions`;
  `checks/evaluation/permissions.go`, at the commit cited below).
- **A protected `zizmor.yml`.** Rejected: any configuration file in the repository is a suppression channel the commit
  under test can edit; `--no-config --no-ignores` has none.
- **A second, pedantic zizmor invocation in the `validate` step.** Rejected for the unittest pass: the existing gate
  tests pin exactly one zizmor invocation per job (`zizmor_step`), and the unittest step runs in the same required job.
- **PyYAML for the tripwire.** Rejected as the only parser: `validate-macos` runs the suite on a setup-python
  interpreter and installs no package, and a skipped tripwire is a silent pass. It stays the cross-check.
- **Fork-based isolation (job 004's option 2).** Not taken here: it changes the resolver, not these workflows, and the
  consensus accepted option 1's architecture once the pre-push gate exists.
- **Refreshing the two recovery-plan bindings here.** Outside this package's paths; recorded as the follow-up.

## Comparison that would overturn it

- A hosted run fails because a job lost a scope it used under the old workflow-level `contents: read` (most likely
  `action-compatibility.yml`'s setup actions, or a `sota-sources` job). Grant that job `contents: read`, cite the run
  and add the grant to the tripwire's reviewed inventory.
- GitHub rejects or changes `cache-mode` on this repository (a workflow parse error, or a cache operation skipped
  where the job needed it). Remove the key from the affected workflows and replace `pull-request-cache-mode` with a
  check that no pull request job runs a cache action.
- The trusted pre-push gate (#489) enforces these rules on every agent commit outside the commit's reach. This module
  then stays as the regression check for `main`, and duplicate rules may be dropped from whichever layer is weaker.
- The two recovery-plan bindings are refreshed or re-pinned by a dispatch. Move both workflows to `permissions: {}`
  with a concurrency group in that change and empty `HASH_BOUND`; the binding test forces it.
- zizmor or Scorecard changes how these audits classify the layout (for example a regular-persona finding for
  `permissions: {}` or for `cache-mode`). Re-measure, and follow the tool's current documented remediation.

## Evidence class

`local_static_analysis`: kjanat/actionlint 1.17.0 (the archive `validate.yml` verifies, SHA-256 `620abd48…`) with
ShellCheck 0.9.0 (Ubuntu 24.04 `shellcheck_0.9.0-1`, the runner image's version, its archive checked against the
signed `noble` index), and zizmor 1.30.1 offline at the regular and pedantic personas. `local_integration`: the
unittest modules that parse workflows, run with the system Python (no PyYAML) and with PyYAML 6.0.3 through uv.
`documented_api_check`: the `gh api` lookups below. No hosted run of the changed workflows is part of this record.

## Primary sources

- Bounded job 004 verdict (coordinator state, 2026-10-04T03:03Z; vote, residual risks and extra enforcement summarized
  above).
- GitHub, Secure use reference (least-privilege `GITHUB_TOKEN`, `pull_request_target`/`workflow_run`, self-hosted
  runners): <https://docs.github.com/en/actions/reference/security/secure-use>.
- GitHub, Workflow syntax (`permissions`, `cache-mode`, `concurrency`, `timeout-minutes`):
  <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>.
- GitHub, Dependency caching (cache scope restrictions, low-trust triggers, `cache-mode` defaults, secure use):
  <https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching>; source read at github/docs
  `2bd66de8cea336061c9ea060c9b37385136e6ab3`, where `cache-mode` was documented on 2026-09-10 (`be60fe442256`).
- GitHub, Events that trigger workflows:
  <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>.
- GitHub, GitHub-hosted runners ("Standard GitHub-hosted runners for public repositories", the runner allowlist):
  <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>; source github/docs
  `data/reusables/actions/supported-github-runners.md` and `single-cpu-table-row.md` at `2bd66de8`, last changed
  2026-09-17 (`eb8f32b5dd88`), read 2026-10-04.
- actions/runner `src/Sdk/DTObjectTemplating/ObjectTemplating/TemplateReader.cs` (`ParseScalar`: literal and
  expression segments become a `format()` expression) at `d7bc179baf11a02110b46cfbbc4040f74ac3f60a`.
- OpenSSF Scorecard checks, Token-Permissions and Dangerous-Workflow:
  <https://github.com/ossf/scorecard/blob/main/docs/checks.md> (read at `f1ebd76756593c0454d782b4ba36ebc33ad131b6`).
- zizmor audits (excessive-permissions, dangerous-triggers, cache-poisoning, artipacked, template-injection,
  concurrency-limits, secrets-outside-env): <https://docs.zizmor.sh/audits/>; usage (personas, exit codes,
  `--no-ignores`) and configuration discovery: <https://docs.zizmor.sh/usage/>,
  <https://docs.zizmor.sh/configuration/>; read at tag `v1.30.1`.
- actions/cache v6.1.0 (`55cc8345863c7cc4c66a329aec7e433d2d1c52a9`): `restore/action.yml` (`cache-hit`,
  `cache-primary-key`), `save/README.md`.
- actions/setup-go `b7ad1dad31e0` and actions/setup-node `820762786026` `action.yml` (cache defaults the tripwire
  encodes).
- kjanat/actionlint v1.17.0 `CHANGELOG.md` (`cache-mode` values, cache safety policies).
- Adoption on github.com: curl/curl `.github/workflows/checkurls.yml` sets `permissions: {}` and `cache-mode: none`
  (commit `58df614c86`, 2026-09-10), and its `pull_request` runs succeeded on 2026-10-04 (run 37171996464); GitHub code
  search listed 553 workflow files with `cache-mode: none`.
