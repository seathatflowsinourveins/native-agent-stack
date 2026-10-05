# Native practice finalization, 2026-09-30

The current Linux/WSL host now uses the maintained selected skill sources through
the upstream installer. Three additional source changes were installed and the
upstream-removed merge-conflict skill was retired. Codex 0.159.2 package and native
configuration lifecycle qualification passed. This is a dated acceptance record
for this host and these capabilities; the user deferred second-machine checks.

The predeclared [plan](../../evidence/artifacts/sota-finalization-20260930/plan.json)
defines the scope. The [source review](../../evidence/artifacts/sota-finalization-20260930/source-review.json),
[native returned results](../../evidence/artifacts/sota-finalization-20260930/native-actions.json)
and [native skill evaluations](../../evidence/artifacts/native-skill-finalization-20260930/results.json)
retain the evidence and failures. The [final receipt](../../evidence/artifacts/sota-finalization-20260930/receipt.json)
records `qualified_with_pending_idle_activation`: installed selected skills and
source qualification are accepted; global Codex activation remains pending.

## Selected source convergence

The selected foundation inventory is 27 skills: Claude has 19 on, five name-only
and three manual; Codex has 11 enabled. Catalog description sums are 7,114 and
3,016 characters respectively. These are listing budgets, not provider tokens.
The trial gates and explicit invocation choices remain in the manifest.

| Change | Maintained source |
| --- | --- |
| Architecture support reference refresh | [codebase-design and improve-codebase-architecture](https://github.com/mattpocock/skills/tree/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/skills/engineering) |
| Semgrep target size limit and omission reporting | [Semgrep skill and native scan script](https://github.com/trailofbits/skills/tree/82fe8226252622fa807643bdca1710901198553a/plugins/static-analysis/skills/semgrep) |
| Retired merge-conflict skill | [Upstream removal changeset](https://github.com/mattpocock/skills/blob/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/.changeset/remove-resolving-merge-conflicts.md) |
| Supported install, lock and remove lifecycle | [Skills 1.7.0 source](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73/src) |

The remaining selected directories were unchanged in the source review; unchanged
directory bytes can remain at their reviewed immutable pins. Semgrep is installed
from its source pin with its CC-BY-SA-4.0 license preserved. Catalog inclusion
continues to carry no installation authority for the 136-entry runtime catalog.

Native status reports 27 passing metadata/link/listing checks and 26 exact folder
trees. The remaining supply-chain auditor difference is the previously allowed
`scripts/uv.lock`; a fresh upstream per-blob comparison confirms 12 of 13 blobs
match, with no difference outside that path. The upstream-removed skill has no
canonical directory, agent links or lock entry, and its native Claude override is
off. The scoped settings merge preserved every other setting.

The first installation failed because root changed identity fields without
changing the install URLs. The installer rejected the mismatch. After updating
the immutable URLs, the unchanged installer recovered all three skills. Local
consumer checks initially exposed stale derived source notes/counts and a README
matrix; those were corrected. All 66 relevant integration tests then passed.
These failures remain in the returned-results artifact and anti-pattern log.

## Native skill outcomes

A frozen initial suite produced 25 native model runs. Four separately predeclared
follow-ups produced four further runs. All 29 outer client exits were zero,
while task grading and observed activation remain separate outcomes.

The original suite had 23 passing outcome grades and two format failures.
Claude's replacement section met its 90-word limit, but added prose made the
frozen whole-output grader fail. A JSON lookup returned Markdown fences instead
of directly parseable JSON. The latter passed a follow-up using Claude's native
`--json-schema` and actual `structured_output`; the original failure remains.

Four original implicit Claude writing cases invoked the native Skill tool and
returned the complete selected skill body. Two original implicit Codex
read-only proposal cases had no observed skill load despite correct outcomes.
Separately predeclared actual edits to disposable AGENTS.md and CLAUDE.md fixtures
loaded the complete writing skill and produced only the requested changes.
Three explicit cases have a full-load observation limit; a name or expansion
alone is not promoted into proof. All 12 adjacent negative cases had no selected
skill invocation or read.

A matched Claude writing case passed both with discovery enabled and with native
`--disable-slash-commands`. The disabled run exposed no skill discovery or Skill
tool. This establishes a working native baseline, **not a measured quality gain**.
Prompt bytes and effective controls match after normalizing the per-run debug
destination; literal argv bytes differ at that diagnostic path.
Original prompts, controls, outcomes, tool failures, file diffs and load hashes
are retained. No automatic invocation claim extends to every selected skill.

Counter scopes stay in the [usage summary](../../evidence/artifacts/native-skill-finalization-20260930/usage-summary.json):
one final cumulative native result per run, 14 Codex and 15 Claude runs.
Cache and reasoning subsets stay separate; Claude advisor/model buckets are not
added to main usage. These counters exclude coordinator and worker sessions.
No efficiency gain is claimed.

Evaluation references: [OpenAI native skill eval guidance](https://developers.openai.com/blog/eval-skills),
[Anthropic skill-creator reference](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md),
[Claude native skills](https://code.claude.com/docs/en/skills) and
[native headless structured output](https://code.claude.com/docs/en/headless).
These are locally authored integration fixtures, not unchanged upstream tests.

## Current-client lifecycle

[Codex 0.159.2 qualification](../../evidence/artifacts/codex-01592-qualification-20260930/qualification.json)
checks installed help, the stable release, immutable source, package provenance,
native scratch config writes/readback/version conflicts, invalid-type rejection,
null deletion, updater idempotence and rollback. The reviewed package binary
matches this host's installed client. Its automatic app-server start remains off.

The original invalid-effort fixture was wrong: the pinned protocol supports custom
effort strings. The accepted write, stale-version rollback failure and recovery
are retained; a type-invalid fixture supplies the actual rejection check.
Sources: [installed-version release](https://github.com/openai/codex/releases/tag/rust-v0.159.2),
[config writer](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/config_manager_service.rs)
and [effort parser](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/protocol/src/openai_models.rs).

The production Codex updater preserves its exact-version and idle guards. The
existing worker file matches the previous owned template with exactly its
authorized Astra-to-Sol model substitution. The qualified migration recognizes
that exact source-derived digest, retains private backup/provenance and restores
only bytes still owned by that run. Custom profiles and later writers stay
protected. Production activation is recorded separately from scratch acceptance.

The native user-manager retry was queued with a 24-hour expiry and returned exit 2
while clients were active; all three production file hashes remained unchanged.
The final native Claude review found that upstream main had changed overlapping
code and that the checksum guard omitted imported `scripts/codex_quota.py`.
Both owned timers were stopped and independently observed inactive/dead. Production
activation remains pending source integration and the complete dependency guard.
The [native handoff](../../evidence/artifacts/sota-finalization-20260930/idle-rollout.json)
retains the original queue attempts and current disarmed state.
Source: [systemd v255 oneshot and post-start contract](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.service.xml)
and [native transient timers](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd-run.xml).

A final real rehearsal exposed an incomplete suggested apply command, despite
the initial test matching an earlier diagnostic. The bounded correction calls
the profile-state method and checks the actual command line. The narrowed
regression failed on prior source, passed on corrected source, and actual native
rehearsal returned the required profile digest. The
[additive correction](../../evidence/artifacts/codex-01592-qualification-20260930/profile-command-correction.json)
preserves the original incorrect claim and its verification path.

The upstream Semgrep suites ran unchanged at the selected revision: the scan
suite returned 104 passed, zero failed; workflow output returned 65 baseline
assertions and 66 mutation assertions. The [exact outputs and file hashes](../../evidence/artifacts/sota-finalization-20260930/upstream-tests.json)
show hermetic upstream acceptance with stubs and dry runs. No real scan or full
model workflow is claimed. Codex cargo tests were not run.

## Review, acceptance and next gate

Native Claude 2.1.285 resolved `opus` to `claude-opus-5-5` at explicit max and
returned exit 0 with `changes_required`. The [original review](../../evidence/artifacts/sota-finalization-20260930/claude-review.json)
and [primary-source verification](../../evidence/artifacts/sota-finalization-20260930/claude-source-verification.json)
retain both blockers and its one final cumulative usage record. This was one
additional review call, separate from the 29 native skill evaluations.

The reviewed upstream main snapshot `cc1f6ce1f983721ecb42c7da27e58f0649c132f5` had changed the
same updater and tests after the original base. An isolated integration keeps
upstream role installation, doctor checks and create-only ownership together with
the source-backed profile migration. This host receipt now has the distinct id
`codex-01592-host-finalization-20260930`; the other owner's same-id historical
receipt is untouched, and the three original native artifacts remain byte-exact.
The omitted dependency closure and the disarmed timers are separate repair gates.
Window-W activity remains unknown: a documented freeze snapshot check validates
an owner-provided capture and seal, and does not establish live activity.

The [integrated source checks](../../evidence/artifacts/sota-finalization-20260930/upstream-codex-integration.json)
passed 173 repository tests with 11 native-gated skips. Separate two-test groups
passed current-client config, doctor/link and repaired role/profile lifecycle
acceptance. Their groups overlap source-defined cases and are not added into a
single independent case count. The first native fixture failure remains: its
synthetic host omitted a required MCP command. One bounded repair reused the
already accepted native fixture definitions and passed the unchanged oracles.

[Independent verification](../../evidence/artifacts/sota-finalization-20260930/repair-verification.json)
confirmed the source mirrors and unchanged role oracles, passed the exact
generated-command and role invariant checks, and matched all 16 local module and
resource hashes. Both timers have no loaded unit or next activation, and all
three production hashes remain unchanged. Passing runner captures were retained;
their underlying passing native command streams were consumed by the oracles
and were not separately persisted. The original Claude verdict remains; these
bounded checks do not establish a second Claude approval or production activation.

The [catalog scope observation](../../evidence/artifacts/sota-finalization-20260930/catalog-scope.json)
shows the adopted named QMD index points to a separate live clone. Current working
checkout changes use bounded original-source reads; no index freshness for this
checkout is claimed. Publication checks verify artifact integrity and generated
guide consistency, and do not rerun model or GPU acceptance.

Remaining decisions concern measured outcomes: extend only a concrete failing
skill task, retain the original baselines, and promote a trial skill only after
its native outcome and recovery gates pass. Review upstream source changes before
replacement. Second-host acceptance remains deferred by the user's instruction;
GPU/provider-wide, trading and live-hosting gates retain their separate records.
