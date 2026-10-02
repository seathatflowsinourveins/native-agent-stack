# Decision: daily catalog reports and the implemented currency notice (2026-10-02)

The existing catalog-freshness workflow provides the report and guarded evidence
proposal mechanism. Change its schedule from Monday at 06:17 UTC to every day at
06:17 UTC (`17 6 * * *`). GitHub schedules use UTC when no timezone is specified
and run the default branch's latest commit; this source change takes effect there
after integration. It is not evidence of a newly executed scheduled run.

## Bounded choice

Keep the existing read-only freshness job and its selections. The optional
`propose` job retains its guard: main branch, detected drift, an unbounded fetch,
zero full and partial upstream errors, and either an explicit manual `open_pr`
request or the existing scheduled `CATALOG_FRESHNESS_PROPOSE` opt-in. That job
continues to propose evidence only. This change neither sets the opt-in nor
enables the separate landscape sweep.

Search-first review selects the existing workflow, GitHub's supported cron
interface, and the repository's pinned `kjanat/actionlint` v1.17.0 validation.
`updatecli/updatecli` v0.122.0 was reviewed as an upstream alternative; the gap is
the cadence of an existing report, so no additional updater is adopted or
installed. Existing report/proposal code needs no new implementation.

## Current notice and correction

At baseline `18eea2c1de992b46c266d79ef0cc40f93c9fb943`,
[`currency-due-notice.py`](../../adoption/hooks/claude/currency-due-notice.py)
already sets `MAX_AGE = timedelta(days=8)`. Its age comparison rejects a record
older than eight days or more than one day ahead. It validates the existing
due-file and emits only its summary as SessionStart `additionalContext`; it
runs no freshness check, process or network request.

The [September 30 decision](2026-09-30-session-currency-notice.md) described an
earlier 48-hour proposal and plain stdout contract. Treating that proposal as
current behavior was wrong. This decision and its linked correction identify
the implemented eight-day contract without changing notice code or claiming
a new latency or model-token measurement. The host due-file, daily timer and
GitHub catalog artifact remain separate paths.

The [Codex hook file](../../adoption/templates/codex.hooks.template.json) remains
a template only. Its description now bases the handler key on the actual
discovered source path and group/handler indexes, rather than assuming an ai-memory group. Any future
explicit adoption uses native `/hooks` to inspect and review the actual hook.
The command, matcher, timeout and shipped trust configuration are unchanged;
this change registers or trusts no hook.

**Review correction (2026-10-02):** the earlier unpublished template wording
called bare `session_start:G:H` examples keys. They are suffixes; the full
persisted key is `<source-path>:session_start:G:H`. The selected Codex 0.160.0
source at `a956835d020762cb2b570053af06f643a11c0ecc` builds that key from
`key_source`, event, group and handler, and discovery assigns `key_source` from
the actual source path. The corrected template directs review to the actual
native `/hooks` entry without guessing its namespace. This is a wording repair
only, with no registration or trust change.

## Verification boundary and overturn condition

Use the pinned native actionlint binary for the changed workflow, the existing
notice/template and documentation checks for the prose correction, and
`python3 scripts/validate.py` for repository integrity. These are local source
and integration checks, not unchanged upstream tests, provider acceptance or
a remote workflow execution. Reuse unchanged baseline evidence for the notice
implementation; no synthetic test is added for a schedule or wording change.

The local checks returned actionlint exit 0, `test_currency_due_notice.py`:
22 tests, `OK`, and `test_adoption_docs_consistency.py`: 39 tests,
`OK (skipped=1)`. Repository validation returned `status: passed` with 69
components, 9,315 hashed files, four profiles and 186 receipts. Independent
source comparison found only the cron changed in the workflow, only the
description changed in the Codex hook template, and only the workflow and
anti-pattern log hash entries changed in the evidence registry. All unrelated
registry entries and the notice implementation were retained.

For the subsequent hook-key wording correction, three existing Codex template
checks and two anti-pattern log checks reran with exit 0 and `OK`. The workflow
and notice implementation still match the previously checked bytes; their
passing evidence is reused.

Reconsider the cadence if observed daily runs cause a concrete cost, quota or
reliability problem. An upstream scheduler change or an explicitly reviewed
notice-contract change must be checked against native behavior before the
documentation changes again.

## 2026-10-02 integration with the accepted PR metadata update

The source statements above describe the daily-cadence unit before its rebase.
Main commit `5803017249ad2a5e90ace4ab4e33e443ae00b66e` merged
[PR #611](https://github.com/seathatflowsinourveins/native-agent-stack/pull/611),
which supplies the guarded proposal job's required lane label and SOTA-source
section, preserves an existing supported lane, handles create races and explains
the source-gate event migration. This integration preserves those metadata
changes and changes only the workflow's unique weekly cron to daily. The other
previously reviewed notice/template/harness source changes remain intact.

PR #611's pinned metadata source is `cli/cli` v2.102.0 at
`fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd`:
[create.go](https://github.com/cli/cli/blob/fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd/pkg/cmd/pr/create/create.go)
and [edit.go](https://github.com/cli/cli/blob/fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd/pkg/cmd/pr/edit/edit.go)
support the adopted `--label`, `--add-label` and `--body-file` flags. Its source
review and local integration receipts remain historical evidence. Neither the
rebase nor a passing source regression check is a new scheduled Actions run,
hosted bot proposal, target installation or provider acceptance.

## Sources

- Existing workflow and its guarded proposal job:
  [`native-agent-stack@18eea2c1`, `catalog-freshness.yml`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/.github/workflows/catalog-freshness.yml).
- Existing notice constant, age check and output:
  [`native-agent-stack@18eea2c1`, `currency-due-notice.py`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/adoption/hooks/claude/currency-due-notice.py#L39).
- Claude profile installation map:
  [`native-agent-stack@18eea2c1`, `install_claude_profile.py`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/tools/adoption/install_claude_profile.py#L49).
- [GitHub Actions `on.schedule`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule).
- [`kjanat/actionlint` v1.17.0 release](https://github.com/kjanat/actionlint/releases/tag/v1.17.0)
  and [tagged installation guide](https://github.com/kjanat/actionlint/blob/v1.17.0/docs/install.md).
  The existing CI download method pins the Linux amd64 archive SHA-256 to
  `620abd485a12b6ab1125b844a876414e1d5bd2af8a3125b27f82b01d0d9d6e5a`.
- [`updatecli/updatecli` v0.122.0 release](https://github.com/updatecli/updatecli/releases/tag/v0.122.0),
  resolved through its annotated tag to commit
  [`20e57d1b35190c25e41f3e2a8339621027484c0c`](https://github.com/updatecli/updatecli/tree/20e57d1b35190c25e41f3e2a8339621027484c0c),
  considered without installation.
- Installed `codex --version` reported `codex-cli 0.159.3`; its help exposes hook
  trust controls. The [matching release notes](https://github.com/openai/codex/releases/tag/rust-v0.159.3)
  were checked, then tagged source settled the key and review claims:
  [group/handler indexing and trust](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/hooks/src/engine/discovery.rs#L487)
  and [the native `/hooks` command](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/tui/src/slash_command.rs#L115).
  [Official OpenAI hook review documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
  supports that review path.
- Selected Codex 0.160.0, commit
  [`a956835d020762cb2b570053af06f643a11c0ecc`](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc),
  resolved from the annotated `rust-v0.160.0` tag:
  [full persisted key construction](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/hooks/src/lib.rs#L113)
  and [discovered source-path namespace](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/hooks/src/engine/discovery.rs#L172)
  settle the scoped review correction.
