# Decision: bounded harness startup context (2026-10-05)

Keep common rules at startup and move client-specific or task-specific reference
behind a trigger and pointer. Preserve each relocated passage verbatim. Use native
skill visibility and RTK installation, with fixed byte ceilings for the repository's
rendered startup files. This serves the foundation's north-star action: carry complex
systems work and US-equities research through reproducible native workflows with
enough context for the actual task.

The user's October 5 requirement is a maintained harness that stays aligned with
upstream research convergence and avoids bloat. Bounded builder job 075 authorizes
these repository changes at `2e681ae5c8f7dfd5d92c7ee9f7b8205ed077f710`.
The coordinator owns host re-rendering and the commit. Standing delegation,
`manifests/stack.json` and `manifests/evidence.json` are outside this edit.

## Measurement and scope

The October 5 read-only harness audit measured real transcripts and rollouts on two
hosts. It reported approximately 88 KB and 78 KB of Claude startup context and 41 KB
and 48 KB of Codex startup context. Those are historical host totals, including
skill listings, memory, hook output and other surfaces; its token estimates use
bytes divided by four. There is no new after-host measurement in this job.

The initial-completion comparison below measures UTF-8 bytes at the job's base and
the job 075 completion. The PR #726 repair addendum below records the current bytes
and amended ceilings. It follows the audit's renderer/carrier discovery; it is not a replay
of those host totals. Claude's scope is the rendered user block, repository
`CLAUDE.md` and the repository `AGENTS.md` that it imports. Codex's scope is its
rendered user block and repository `AGENTS.md`. The existing managed-block merger
includes marker bytes. Count each repository file once.

| File or rendered client scope | Before bytes | After bytes |
| --- | ---: | ---: |
| `AGENTS.md` | 13,986 | 10,101 |
| Repository `CLAUDE.md` | 766 | 766 |
| `examples/claude-native/CLAUDE.md` | 13,776 | 10,830 |
| `adoption/templates/codex.AGENTS.template.md` | 8,190 | 8,091 |
| Claude rendered startup scope | 28,794 | 21,963 |
| Codex rendered startup scope | 22,176 | 18,192 |

The Claude and Codex carriers in `adoption/new-wsl/` equal their respective source
templates at this revision. The scoped reductions are 6,831 bytes and 3,984 bytes.
They establish an instruction-file reduction, not a model-quality, token-usage or
billing result. Native RTK's imported awareness file, host text outside the managed
block, MEMORY.md, plugin injections, skill/agent listings, MCP instructions and
client built-in prompts are separate measurement surfaces.

## Relocated passage contracts (amended by PR #726)

Source line numbers refer to the job's base. Passage bytes exclude the separating
newline; this explains the audit's one-byte differences for individual lines.
Each surviving passage exists byte-for-byte at its named section. The repair
removes only two redundant self-pointers and the Codex dispatch-contract path,
restores root routing pending the two-host gate, and restores the schema bullet
at startup. These exceptions amend the original all-verbatim claim explicitly.
The frozen fixtures in `tests/fixtures/harness-context-moves/` bind each section;
the tests do not look for phrases elsewhere in a guide.

| From | Destination | Passage bytes |
| --- | --- | ---: |
| `AGENTS.md:38`, Codex routing and pinned launches | Codex template retains the 782-byte portable form; original 868-byte paragraph restored in root pending the host gate | 782 |
| `AGENTS.md:39`, Claude effort and Ultracode rules | `docs/decisions/2026-09-29-max-default-effort.md` | 1,564 |
| `AGENTS.md:53`, trading north star and paper authorization | `blueprints/us-equities/AGENTS.md#trading-north-star`; redundant 275-byte self-pointer removed | 1,077 |
| `AGENTS.md:33`, QMD catalog lookup | `docs/token-session-handbook.md#catalog-lookup` | 499 |
| `AGENTS.md:49`, dashboard checkpoint | `observability/grand-dashboard/README.md#checkpoint-and-observation-rules`; redundant 81-byte self-pointer removed | 213 |
| `AGENTS.md:50`, Grafana observation and Dagu authentication | Same dashboard section | 239 |
| `AGENTS.md:51`, generated ecosystem HTML | `docs/token-session-handbook.md#offline-ecosystem-guide` | 282 |
| Portable Claude `CLAUDE.md:48`, duplicate Codex routing | Canonical Codex template above | 782 |
| Portable Claude `CLAUDE.md:45`, named teammate mechanics | `examples/claude-native/workflows/README.md#native-workflow-mechanics-relocated-2026-10-05` | 385 |
| Portable Claude `CLAUDE.md:50`, effort, inheritance, limits and concurrency | Same workflow section | 1,668 |
| Portable Claude `CLAUDE.md:55`, messaging, StructuredOutput and incomplete returns | Same workflow section; schema bullet also restored verbatim to portable user block | 872 |

The portable Claude file retains its solo, subagent, workflow and team dispatch
rules. The relocated workflow details remain explicitly dated, with the existing
source references in that workflow guide. The trading file now carries the original
north star and paper authorization rather than instructing readers to return to
the root for them. The portable Claude pointer leads to the Codex instruction
block, with cross-family dispatch inline. Root routing stays inline until both
hosts pass the recorded render gate. The Codex/scaffold dispatch-contract path
was 86 bytes including its leading space; its exact removal leaves the
782-byte canonical routing form.

## Native defaults and corrected claims

**Amended by repair round 3 (2026-10-05):** the initial audit item 8
recommendation to remove the fraction override and make nine audit skills
`name-only` is overturned by the user's September 30 LLM-native invocation
directive. Keep `skillListingBudgetFraction: 0.05` and every eligible local skill
`on`, including `security-best-practices`, `security-threat-model`, `codeql`,
`supply-chain-risk-auditor`, `agentic-actions-auditor`, `sarif-parsing`, `fp-check`,
`variant-analysis` and `security-audit`. The initial name-only rationale cited
2026-10-05T05:58:36Z (quoted below); that workflow-quality directive does not revoke
the more specific standing skill-invocation directive. All entries, pins, statuses
and Codex eligibility remain in place. The listed-description sum returns from
5,357 to 9,484 Unicode code points; this is a manifest calculation, not a live
skill-listing byte measurement. Skill listing is governed independently of the
startup instruction-file budget. Native `/skill-doctor` remains the host check;
plugin skills ignore `skillOverrides`.
[Claude skills documentation](https://code.claude.com/docs/en/skills) and the
[accepted September 30 record](2026-09-30-skills-llm-native-listing.md) provide the
native settings and evidence. The dated round 3 addendum below records the
restoration and alternatives.

**Amended by [Required startup behavior and accepted-record amendments](#required-startup-behavior-and-accepted-record-amendments):**
the following paragraph describes the initial job 075 wording. The common repair
conditional delegates the client-copy and user-only details to the lifecycle guide.

The initial root skill-discovery instruction names installed `find-skills` or Skills
CLI `find`, and installed `skill-creator`, while distinguishing Codex's bundled
copy from Claude's selected Anthropic copy. Check actual client exposure, including
user-only invocation, and follow `adoption/skills/lifecycle.md` when a capability
is missing. The audit found that one host did not have Claude's copy installed;
the new wording does not assume installation. The official
[skill-creator integration](https://code.claude.com/docs/en/skills#run-evals-with-skill-creator)
names Claude's maintained plugin.

Our own SessionStart notices stay within one line of at most 160 characters. Upstream
plugins may provide their documented native injection blocks, whose bytes must be
measured separately. Context Mode's selected `v1.0.169` README documents its
SessionStart routing injection; using an earlier `v1.0.65` discovery lead here
would have cited the wrong selected pin. This correction is recorded with the
verification path in the harness anti-pattern log.
[Context Mode source](https://github.com/mksglu/context-mode/blob/v1.0.169/README.md)
and [Claude plugin hooks](https://code.claude.com/docs/en/plugins-reference#hooks)
support this distinction. Startup remains free of our audits, trials and network
checks.

RTK uses its native 0.51.0 global installer default: RTK.md plus an `@RTK.md` import.
The client-config map previously installed its hook without wiring that native
instruction-file initialization. The existing apply tool now calls
`rtk init -g --no-patch` before adopting the Claude block, then checks both files.
`--no-patch` leaves settings to the map's hook configuration; RTK itself writes
its awareness file and import. This closes an integration gap without a local RTK
renderer. Two executions of the actual installed binary in an isolated temporary
home each exited 0, wrote a 452-byte RTK.md and retained exactly one import. That
is native installation evidence, not a provider or model run.
[RTK 0.51.0 installer source](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/claude.rs#L305)
and [README](https://github.com/rtk-ai/rtk/blob/v0.51.0/README.md) document the layout.

**Amended by repair round 3 (2026-10-05):** Codex carries the entire native
RTK 0.51.0 awareness file verbatim. The earlier qualified excerpt and the status
checker's two-omission tolerance are superseded. The separately marked local
exceptions qualify the upstream blanket assurances without rewriting its text.
The compact template includes `adoption/templates/rtk-awareness-full.md`; the
existing managed-block writer expands that include into the carrier and native
lane instructions. All five Codex role projections and their mirrors carry the
same complete F4 block with current checksums. The full 1,121-byte source has
SHA-256 `278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc`, identical
to the existing worker-lane fixture and
[the pinned native source](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/hooks/rtk-awareness-full.md).
The round 3 addendum records the template fallback and measured rendered bytes.

## Fixed byte budget and review procedure

`tests.test_install_claude_profile.PortableTopRuleTests` measures the rendered
managed blocks and repository files above, instead of raising a word baseline
whenever text is added. Freeze the trimmed sizes plus 5% rounded upward:

| Client | Trimmed bytes | Fixed ceiling | Headroom |
| --- | ---: | ---: | ---: |
| Claude | 21,963 | 23,062 | 1,099 |
| Codex | 18,192 | 19,102 | 910 |

The ceilings are constants, not a calculation from current file size at test
runtime. Boundary controls exercise growth in every loaded file and a multibyte
character. Keep the separate 8,192-byte Codex template test. A future change first
tries a task pointer, existing native skill or maintained upstream feature. If a
ceiling must change, add a dated decision with old/new rendered bytes, the required
behavior, alternatives, primary sources and the comparison that would overturn
it. Change the constant in the same reviewed diff; do not silently re-baseline it.
Regenerate carriers and run these tests after the decision.

The local gate fills a specific native automation gap. Installed Claude 2.1.289's
`claude doctor --help` exits 0 and lists only `-h, --help`; no machine-readable
prompt-audit CLI form is found there or in the reviewed changelog through 2.1.289.
The upstream 2.1.283 changelog introduces the interactive `/doctor prompt-audit`
slash command. Keep using that native audit for semantic review; this byte test
does not reproduce it.
[Upstream Claude changelog](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md)
and [memory documentation](https://code.claude.com/docs/en/memory) are the source
checks. Claude recommends concise instruction files, warns that conflicting rules
may be chosen arbitrarily, and loads imported files at launch. Codex concatenates
project instruction files and imposes a configurable project-document limit;
the client-specific byte scope follows its native loader, not Claude imports.
[Codex AGENTS guide](https://developers.openai.com/codex/guides/agents-md) and
[installed-version loader source](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/core/src/agents_md.rs)
support this distinction.

## Freshness, alternatives and overturn conditions

The existing upstream-surface watch previously observed versioned setting and tool
surfaces, without watching these instruction documents. Extend its existing bounded
fetch/cache path, rather than adding a watcher or runner. Three enabled dispositions
track the exact memory, skills and Codex AGENTS guide URLs cited above. Their reviewed
body digests and the carrier for this audit are in
`catalogs/foundation/upstream-surface-dispositions.json`. A body change reopens its
row in `unreviewed` even when its name was already reviewed. Writing a surface
baseline cannot clear it. Re-read the primary document and repeat this audit before
changing the reviewed digest. Offline replay preserves the cached observation date;
a required missing source fails the watch. Request Markdown where supported; an
HTML response's markup changes can also trigger review. See
`docs/upstream-surface-watch.md` for this existing tool's native operation.

The alternatives were retaining the inline rules and rising word baseline,
deleting/rephrasing rules to save bytes, and adding a separate prompt-audit runner.
Verbatim disclosure, native settings/installers and a narrow gate preserve the
behavior while bounding the owned surface. Overturn this choice when:

- An upstream machine-readable audit supplies the same rendered-file byte contract;
  adopt it and remove the redundant local gate.
- A document watch or client update changes file discovery, imports, skill listing
  or native RTK initialization; verify the new source and remeasure before adoption.
- The user revises the standing LLM-native invocation directive or an upstream
  change supplies better native discovery while preserving proactive invocation;
  compare host listings and invocation evidence in a dated listing decision.
  Startup file savings alone do not justify hiding a skill's description.
- Real task evidence shows a relocated rule is not reached through its pointer;
  sharpen the trigger or restore only the required common instruction, with a
  dated byte comparison and quality evidence.

## Completeness review and evidence limits

This bounded review covers both clients' repository-owned instruction surfaces,
skill visibility, RTK layout and the three upstream document classes. It preserves
workflow dispatch, trading authorization and each moved rule. The next coordinator
sweep should measure the remaining host surfaces: standing delegation, MEMORY.md,
upstream hook output, imported native RTK text, skill/agent listings and MCP
instructions. Key the skill follow-up by lifecycle task (audit, triage, scan and
threat-model work), then use native `/skill-doctor` and upstream skill evals where
behavioral comparison is needed. Avoid treating smaller files as proof of better
research or agent output. No new model or billing experiment was performed.

A scoped ai-memory query with `pin_first=true, limit=2` was attempted; the installed
tool required approval while this builder's approval policy is never. The exact
audit, current repository sources and canonical upstream sources supplied the
evidence instead. Initial `.md` Claude documentation URLs returned 403 and two
guessed source paths returned 404; canonical document URLs and tag source paths
resolved those leads. Failed check attempts and the original source snapshots are
retained outside the checkout in the authorized builder temporary directory.
Compact move and byte measurements are in `.bounded-job-075/`. They remain
separate from upstream execution and live-provider acceptance.

## Acceptance (resumed completion)

Only the seven requested test modules were run for resumed acceptance:
`tests.test_install_claude_profile`, `tests.test_codex_worker_lane`,
`tests.test_scaffold_repo`, `tests.test_new_wsl_client_config`,
`tests.test_new_wsl_handbook`, `tests.test_managed_block` and
`tests.test_upstream_surface_watch`.

| Command | Exit | Returned result |
| --- | ---: | --- |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | Carriers regenerated |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | Current; two existing MCP_AUTO_OPEN_ENABLED manifest/install-plan warnings |
| `python3 scripts/build_new_wsl_handbook.py --write` | 0 | JSON and Markdown regenerated |
| `python3 -m unittest` with the seven modules above | 0 | Ran 645 tests in 152.325s; OK (skipped=22) |
| `python3 scripts/validate.py` | 1 | Registry drift only: 79 SHA-256/byte-count mismatches; no other findings |
| `wc -c adoption/templates/codex.AGENTS.template.md` | 0 | 8,091 bytes, below 8,192 |
| `git diff --check` | 0 | No whitespace errors |

All eleven preserved passages were read back at their destinations and compared
with the original snapshots. The three requested file byte comparisons remain
13,986 to 10,101, 13,776 to 10,830 and 8,190 to 8,091. These checks are local
integration and synthetic-fixture evidence, alongside the separate native RTK
installation execution recorded above. They are not unchanged upstream test runs.

Earlier acceptance attempts exposed stale RTK marker/checksum/location assertions,
synthetic native-install coverage gaps for alternate temporary homes, and a moved
README citation. Corrected projections and read-back assertions preserve the
source contracts; the citation now names the actual `otel.environment` line.
Raw-source examples and temporary paths initially triggered publication scanning
while stored in the checkout; preserving those originals outside it resolved that
storage error. Failed logs remain retained as failed attempts. Protected stack and
evidence manifests are unchanged, and no commit or host re-render was performed.
The coordinator's commit message is `.bounded-job-075/msg.txt`.

## Addendum (2026-10-05): PR #726 Claude cross-family repair

The coordinator accepts the cross-family read against the original source records
and supplies the following user directives verbatim:

2026-10-05T05:51:21Z:

> we can update all the sota convergence practice into github and sota local file practice,make sure the new session are clean sota with the sota repos upstream practice rather than inherited our without sota convergence, the new wsl need to stay clean sota itself

2026-10-05T05:58:36Z:

> safty is never our main focus, no security over enginnering is needed,focuing on the real tasksm the quality of workflow etc is the main

The latter directive was cited for the initial nine name-only selections. Repair
round 3 restores their full descriptions under the more specific September 30
standing directive quoted below. The Skills-CLI/local installation route remains
in the manifest; plugin skills ignore this setting. Actual installation and
`/skill-doctor` read-back on 2604 remain coordinator observations. No selected
skill is deleted or newly disabled here.

### Required startup behavior and accepted-record amendments

Restore the exact StructuredOutput bullet to the portable Claude user block. The
[September 25 model-fallback/schema record](2026-09-25-model-fallback-guard.md)
reports 5/30 versus 0/30 schema errors and a user-level-only 0/30 sequential check;
reference-file presence does not overturn that A/B evidence. Keep its complete
relocated workflow group for byte preservation, and use the portable pointer for
messaging and incomplete returns. The new dated addendum in that record identifies
the mistaken move and retains the original comparison's limits.

Cross-family gateway dispatch stays inline on root AGENTS.md, Codex and portable
Claude. The full original 868-byte Codex paragraph also stays in root AGENTS.md
until the host gate below. Remove only its 86-byte repository dispatch-contract
suffix from the Codex template and scaffold, where other projects lack that path.
The surviving 782-byte form is byte-bound in the Codex top-rule section. This
corrects the original 868-byte destination claim in the move table.

The [September 30 three-surface record](2026-09-30-rule-text-every-layer.md) and
[September 26 cleanup record](2026-09-26-harness-rules-cleanup.md) receive dated
addenda for the departure from their no-pointers and root-north-star decisions.
One discovery conditional now applies on root, portable Claude, Codex, scaffold
and both carriers: when no skill fits, use installed `find-skills` or Skills CLI
`find` and `skill-creator` for verification or A/B; check client exposure and the
skills lifecycle. Its on-demand guide is `adoption/skills/lifecycle.md`; Codex's
bounded-worker coordinator prefix remains the recorded client variant. The
Vercel Skills CLI pin and Anthropic skill-creator source in the September 30
record establish the installed equivalents; availability is checked per client.

The never-rebuild clause now says "never rebuild or fork what an upstream already
ships; glue only fills a demonstrated gap, cited at a pin." The
[official-upstream record](2026-10-05-official-upstream-never-rebuild.md) preserves
the full 2026-10-05T04:26:41Z user quote and attributes only those verbatim words to
the user. The earlier fork/wrap ban was our interpretation. It now defines a clean
release as the maintainer's published release or tag installed by its documented
installer; a prerelease counts only where the selected lane names it, as rc5 does.

The supplied co-op directive is "my prompt many times are just a starting point a
inspriation… improve my prompt to latest sota convergence practice". S1 therefore
reads identically on the three sources and their projections: "Prompts fix the
objective, scope and authorization; improve the approach from current evidence."
S2 changes only root AGENTS.md's material-decision stop condition to one that a
cross-family review leaves unresolved. S3 is the root-only 124-byte pointer to
[the repository-quality rule](2026-10-04-repository-quality-rule.md), preserving
that record's actual criteria rather than inventing additional ones.

The trading and dashboard self-pointers are removed as the read requested; their
remaining 1,077/213-byte passages and all other moves are frozen in heading-scoped
fixtures. Root's trading trigger now includes paper/broker operation and naming a
coordinator unit's north-star action. `build_inputs.py` now cites
`blueprints/us-equities/AGENTS.md#trading-north-star`. Standing delegation is untouched.

### Preserving the accepted listing fraction (amended 2026-10-05, round 3)

[deep_merge_dict](../../tools/adoption/apply_claude_settings.py) preserves host
keys that the template does not mention. Repair round 4 restores this settings
writer byte for byte from main and uses its ordinary merge contract.

[step_claude_settings](../../tools/adoption/new_wsl_client_config.py) follows the
accepted September 30 practice: merge `skillListingBudgetFraction: 0.05` and full
eligible `skillOverrides: on`, while retaining unrelated host keys. The regression
seeds 0.05 and an unrelated host key, proves dry-run preservation, checks both
after apply, and checks the backup and identical second apply. Actual 2604
read-back of 0.05 and the native Skills row remain a coordinator host gate. The
native 1% default documented by [Claude](https://code.claude.com/docs/en/skills)
does not supersede the user's invocation directive.

### Expanded byte scope and fixed amended ceilings

The gate discovers Claude `@` imports outside inline code spans and fenced blocks,
resolves paths relative to the importing file, supports escaped spaces, counts
once and follows the documented four-hop maximum. Missing imports fail rather
than silently disappearing from the count. It includes recursively discovered
`.claude/rules/*.md` without a clear nonempty frontmatter `paths` list; ambiguous
frontmatter counts conservatively. Codex prefers root `AGENTS.override.md` over
`AGENTS.md` and leaves `@` references literal. These are file-discovery checks,
not a duplicate prompt renderer. The native docs and pinned Codex loader cited
above establish those loading distinctions.

The rendered user block's relative imports use its projected native `.claude`
directory in the fixture. Host-added imports such as RTK's independently installed
RTK.md are a separate host measurement surface; the owned portable source names
that import inside a code span and does not recreate it. This repository currently
has no unconditional rules directory or root override. Future additions and
repository imports are measured by the gate rather than hidden from it.

The repository-owned **`adoption/hooks/claude/token-lanes-block.md` (4,099 bytes)**
SubagentStart carrier is explicitly exempt from the main startup ceiling: its hook
injects it at child launch, so adding it to every coordinator startup would mix
scopes. Its child-role alternatives measure builder 2,888, researcher 3,086,
reviewer 2,099, scout 1,089 and verifier 2,186 bytes. Measure the selected block in
the child receipt. The separate held-out SessionStart main block is 1,842 bytes;
enabling it requires a measured main-session hook decision. `docs/token-practice.md`
now applies the 160-character cap to our own SessionStart notices and names the
scoped child carrier. Upstream plugin blocks remain allowed, separately measured
native injections. These exemptions do not exclude any repository instruction
file or unconditional rule from the instruction-file gate.

| File/scope | Job 075 completion bytes | PR #726 repaired bytes |
| --- | ---: | ---: |
| Root `AGENTS.md` | 10,101 | 10,959 |
| Repository `CLAUDE.md` | 766 | 766 |
| Portable Claude source and carrier | 10,830 | 11,302 |
| Codex template and carrier | 8,091 | 8,186 |
| Claude rendered block | 11,096 | 11,568 |
| Claude rendered startup scope | 21,963 | 23,293 |
| Codex rendered startup scope | 18,192 | 19,145 |

| Client | Old fixed ceiling | Required repaired bytes | New fixed ceiling | Headroom |
| --- | ---: | ---: | ---: | ---: |
| Claude | 23,062 | 23,293 | 24,458 | 1,165 |
| Codex | 19,102 | 19,145 | 20,103 | 958 |

The first repair's ceiling raise is caused by adopted co-op sentences S1–S3,
which add 350 Claude bytes and 349 Codex bytes. Without them, the restored scopes
are 22,943/18,796 bytes, inside the old 23,062/19,102 ceilings with 119/306 bytes
to spare. The StructuredOutput and routing restorations therefore do not cause
that raise. The actual alternative at that decision was to put S1 and S3 on
demand and keep the old ceilings. The coordinator instead adopted S1–S3 at their
specified startup locations; the A/B-backed guard does not need to be dropped.
This dated amendment freezes that first repaired scope plus 5%, rounded upward.
The tests use constants 24,458/20,103 and never recompute them from current file
size. Repair round 2 adds the literal clauses under these existing ceilings, as
recorded below, without another ceiling increase.
The first-repair comparison with the original baseline shows reductions of
5,501 Claude bytes and 3,031 Codex bytes. The Codex template remains 8,186 bytes, strictly below 8,192 with five usable
bytes. Its top-rule/lanes pin is now
`568ee365aeef3455fc901e648eb72d28cc3b49c39f1bfba7f5e39beed20479a8`.
Future budget changes still require the dated comparison procedure above. When
both hosts pass the gate, replace the temporary full root routing with its
188-byte task pointer, removing 680 bytes. In that same reviewed diff, record
the post-gate scopes and reduce both fixed constants to those measured sizes
plus 5%, rounded upward. Freed routing bytes cannot become permanent headroom.
With round 2's 273-byte Claude clauses and no other scope change, the post-gate
scopes are 22,886 Claude and 18,465 Codex bytes; the required tightened ceilings
are 24,031 and 19,389. A different measured scope needs its own dated comparison.

The installed `claude doctor --help` was read again on 2.1.289: exit 0, only
`-h, --help`, no machine-readable prompt-audit option. The reviewed upstream
changelog still supplies only the interactive slash-command form. The existing
local byte gate fills that cited automation gap; native `/doctor prompt-audit`
and `/context` remain the host's semantic and actual-startup checks.

### Recorded rollout gate, alternatives and evidence limits

**Pending coordinator gate after landing:** re-render the current blocks on both
hosts through `tools/adoption/new_wsl_client_config.py`; read back `gpt-6.1-sol`,
"spawn call names neither" and "starts a cross-family lane" in each actual
Codex-home AGENTS.md (including the bounded SDK jobs' codex-home-full). Read back
the StructuredOutput and cross-family sentences in each actual Claude user block,
and `skillListingBudgetFraction: 0.05` in 2604 settings, followed by the
native `/context` Skills row. Until both host reads pass, keep root routing inline.
No host files, credentials or sign-ins are changed by this repository repair.

The four regression tests failed before repair (exit 1, four failures in 1.134s),
then passed through the corrected paths (exit 0, four tests in 1.539s). Heading and
byte contracts, code-span/import controls, filtered-rule controls and override
preference are local integration evidence. They establish file and settings
behavior, not vendor model quality or provider acceptance. The final seven-module
acceptance results are recorded below after execution.

Completeness review: the repairs cover startup guards, shared wording, accepted
records, owned settings migration, both client loaders, child-carrier scope, all
pointer branches and the supplied user quotes. The remaining evidence class is
host observation, explicitly assigned to the coordinator gate. A changed native
loader/doc watch, a missed rule at its trigger, an evidenced client schema fix,
or an upstream machine-readable byte audit reopens the corresponding choice and
feeds the next lifecycle-task sweep. Upstream closing a demonstrated glue gap
removes that glue. No new security ceremony, service, model run or custom runner
is added.

#### Amendment 2026-10-06: B3 read-back scope

**Decision.** NativeStack's part of the two-host read-back requirement above is
waived until its retirement. NativeStack2604 has a recorded measured read-back
pass; the owner's `/context` observation supplies the Skills row: **64 skills,
7.8k tokens**. The bounded SDK jobs' `codex-home-full` read-back remains due at
the first bounded SDK job after the night of 2026-10-06, owned by the SDK kit
owner (the co-op). The remaining read-back requirement still governs replacement
of the inline root routing; this amendment changes no client configuration.

**Evidence and authority.** The measured observations are recorded in
`coordination/session-d91d55ad-20261006/IMPROVEMENT-MANIFEST.md`, B3. The waiver
and deferred SDK check follow `task-ns2604-coop-20261006T203515Z`, section 5, B3.
These are retained observations and a dated ruling, rather than a new read-back
performed by this amendment. The Skills figure describes the displayed context
row and establishes no provider-token saving or comparative benchmark.

**Alternative and overturn.** Re-rendering and checking the retiring host was
the alternative to the waiver. A dated decision to retain it as an ongoing
target would reopen its read-back requirement. Compare any continuing target's
actual client blocks with the phrases and settings required above; an SDK
read-back failure remains a wiring issue for the kit owner to resolve.

### PR #726 repair acceptance

| Command | Exit | Actual returned result |
| --- | ---: | --- |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | Both carriers regenerated; zero units dropped |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | `check passed`; the two existing MCP_AUTO_OPEN_ENABLED plan warnings remain |
| `python3 scripts/build_new_wsl_handbook.py --write` | 0 | `written`; handbook outputs stay identical to the repair base |
| `python3 -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_scaffold_repo tests.test_new_wsl_client_config tests.test_new_wsl_handbook tests.test_managed_block tests.test_upstream_surface_watch` | 0 | Ran 653 tests in 144.981s; OK (skipped=22) |
| `python3 scripts/validate.py` | 1 | Registry drift only: 36 SHA-256/byte-count mismatches across 18 changed registered files; no other findings |
| `wc -c adoption/templates/codex.AGENTS.template.md` | 0 | 8,186 bytes; strictly below 8,192 |
| `git diff --check` | 0 | No whitespace errors |

The focused four-test regression changed from four failures to passing; the
34-test instruction/loader/move-contract check also passed (0.072s). Full logs
remain in the repair's authorized external TMPDIR. Protected stack and evidence
manifests remain unchanged; the coordinator refreshes the evidence registry last.
The commit message is `.bounded-job-075/msg-repair.txt`. The pending two-host
re-render and actual-context read-back gate above remains open.

## Addendum (2026-10-05): PR #726 repair round 2

The Claude recheck identifies two local contract regressions and two record defects
at `5096e547c47b052db287c1268c55a6569ab7fcc2`. Both executable failures were
reproduced before changing their inputs. This serves the foundation north-star
workflow: preserve executable dispatch contracts while reducing startup context.

The workflow envelope suite returned exit 1, `SUMMARY passed=252 failed=2 total=254`:
the portable instructions lacked the effort literal and unrestricted-size guideline.
Its [test-envelope.mjs](../../examples/claude-native/workflows/test-envelope.mjs)
reads the portable source named by
[contract.config.json](../../examples/claude-native/workflows/contract.config.json).
That config is checksum-locked by the example's SHA256SUMS. Restore only the two
literal-bearing clauses from frozen passage 10, adding 273 UTF-8 bytes including
newlines to the portable source and its carrier. The complete 1,668-byte reference
passage remains unchanged in its relocated workflow section. Repointing the config
or restoring the entire 1,131-byte pair of original lines is unnecessary for these
two contracts. The existing workflow README, original pinned effort decisions and
unchanged contract suites remain the sources; no new workflow runner is added.

With TMPDIR under a symlink, the 12 PortableTopRuleTests returned exit 1 with three
failures and one error: four relative-key checks received absolute paths. `add()`
resolved the imported paths while the mocked ROOT remained unresolved. Each of the
five scratch tests now uses `Path(tmp).resolve()`, and startup_files resolves its
root once before discovery and relative-key comparison. The existing CI gotcha's
macOS `/var` to `/private/var` example prescribes exactly this Linux reproduction.
The same command through the same symlink then returned exit 0: 12 tests in 0.028s,
OK. This is evidence for the path-layout failure on Linux; no macOS CI result or
full Python-suite result is claimed. Production filesystem policy is unchanged.

The prior ceiling explanation was wrong. Removing S1–S3 from the first repaired
scope removes 350 Claude bytes and 349 Codex bytes, yielding 22,943/18,796 under
23,062/19,102. Direct replacement of the three adopted clauses reproduces that
arithmetic: root contributes 253 bytes, plus 97 Claude or 96 Codex S1 bytes.
The first raise was the explicit decision to carry co-op guidance at startup,
not a requirement of the A/B-backed schema and routing restorations. Its real
alternative was S1 and S3 on demand with the old ceilings kept. That alternative
is now named in the amended first-repair paragraph; the chosen startup locations
remain the coordinator's instruction. Round 2's distinct 273-byte literal restore
fits the already accepted ceilings and does not increase them. The first-repair
counterfactual predates this literal restore; with the restore but without S1–S3,
Claude would be 23,216 bytes and Codex 18,796 bytes.

| File/scope | First repair bytes | Round 2 bytes |
| --- | ---: | ---: |
| Root AGENTS.md | 10,959 | 10,959 |
| Repository CLAUDE.md | 766 | 766 |
| Portable Claude source and carrier | 11,302 | 11,575 |
| Claude rendered user block | 11,568 | 11,841 |
| Codex template and carrier | 8,186 | 8,186 |
| Claude startup scope | 23,293 | 23,566 |
| Codex startup scope | 19,145 | 19,145 |

The constants remain 24,458/20,103, leaving 892/958 bytes. After both hosts pass
the recorded routing gate, replacing the 868-byte root paragraph with its 188-byte
pointer removes 680 bytes from both scopes. Re-tightening is mandatory in the same
reviewed diff: measure the actual scopes, record the comparison, and lower each
constant to post-gate bytes plus 5%, rounded upward. With current inputs that means
22,886/18,465-byte scopes and 24,031/19,389-byte ceilings. Further additions require
an independently reviewed dated comparison; the removed routing bytes cannot be
absorbed into a permanent growth allowance. This corrects the earlier omission of
a required reduction after the gate.

The initial discovery paragraph above is explicitly marked as amended by
[Required startup behavior and accepted-record amendments](#required-startup-behavior-and-accepted-record-amendments).
The common conditional stays on all current instruction surfaces, with client-copy
and user-only exposure details in `adoption/skills/lifecycle.md`. This change does
not rewrite the accepted historical discovery wording as if it were current.

The post-fix Node suites return `SUMMARY passed=254 failed=0 total=254` and
`SUMMARY passed=74 failed=0 total=74`, both exit 0. These are the same local workflow
contract and mutation checks used by CI, not live model execution. A scoped
ai-memory query with pin_first and limit 2 was again rejected by the approval-never
policy; canonical tests, frozen original clauses, the gotcha snapshot and direct
reproduction supplied the evidence. Failed and passing logs remain in the repair's
authorized external TMPDIR. The config/checksum lock, stack and evidence manifests,
standing delegation and host user files are unchanged.

Completeness check: both executable failure classes and both record findings are
fixed without new trimming, runner code or a ceiling raise. The next verification
remains the coordinator's host render/read-back gate and registry refresh; when the
gate passes, its reviewed change must also tighten the constants. An upstream change
to the workflow literals, import discovery or native byte-audit capabilities reopens
the corresponding contract through the existing surface watch and dated comparison.
The commit message is `.bounded-job-075/msg-repair2.txt`.

### Repair round 2 acceptance

| Command | Exit | Actual returned result |
| --- | ---: | --- |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | Both carriers current; zero units dropped |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | `check passed`; the two existing MCP_AUTO_OPEN_ENABLED plan warnings remain |
| `python3 scripts/build_new_wsl_handbook.py --check` | 0 | `passed`; regeneration unnecessary |
| `python3 -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_scaffold_repo tests.test_new_wsl_client_config tests.test_new_wsl_handbook tests.test_managed_block tests.test_upstream_surface_watch` | 0 | Ran 654 tests in 152.912s; OK (skipped=22) |
| `TMPDIR=<symlinked temporary directory> python3 -m unittest tests.test_install_claude_profile.PortableTopRuleTests` | 0 | Ran 12 tests in 0.028s; OK; the same directory reproduced three failures and one error before repair |
| From `examples/claude-native/workflows`: `node test-envelope.mjs` | 0 | `SUMMARY passed=254 failed=0 total=254` |
| From that directory: `node test-contract-mutations.mjs` | 0 | `SUMMARY passed=74 failed=0 total=74` |
| `python3 scripts/validate.py` | 1 | Registry drift only: 8 SHA-256/byte-count mismatches across 4 registered files; no other findings |
| `wc -c adoption/templates/codex.AGENTS.template.md` | 0 | 8,186 bytes; strictly below 8,192 |
| `git diff --check` | 0 | No whitespace errors |

Only the seven requested Python modules and focused path reproduction were run;
no full-repository Python acceptance is claimed. The unchanged workflow config and
checksum lock were read back through git diff. Full returned outputs, including
the failed reproductions, remain in the authorized repair TMPDIR. The coordinator
commits and refreshes the registry last; both protected manifests remain unchanged.

## 2026-10-05 repair round 3: user-directed listing and verbatim RTK

CI run 37283231657, job 111676262001 at `ee37894af`, reported three failures
among 11,047 tests. The same three failures were reproduced locally before this
repair. They identify a conflict with an accepted user directive and a native
source-preservation regression, rather than a new upstream recommendation.

The coordinator supplies the user's September 30 standing directive verbatim:

> make sure all the skills can invoke seamlessly with llm native end, rather than user end

The [accepted listing record](2026-09-30-skills-llm-native-listing.md) records that
`name-only` depresses proactive invocation. All nine changed skills therefore
return to `claude_listing: on` and template `skillOverrides: on`; existing Codex
eligibility is preserved, including its native `skill-creator` copy exception.
The map restores `skillListingBudgetFraction: 0.05`, also kept on NativeStack2604.
Main's ordinary settings merge preserves unmentioned host keys. Related tests
require full eligible descriptions and preservation of the fraction. Audit item 8's name-only/default-fraction proposal
is overturned by this directive. The October 5 workflow-quality quote above does
not revoke it. The rejected alternative is hiding descriptions to save startup
context; the skill catalog is governed by the user directive and measured as a
separate client surface, independently of the instruction-file byte gate.

At base `77d7516d8`, the upstream awareness body lived inline in both the Codex
template and new-WSL carrier (8,187 bytes each), under a v0.50.0 verbatim marker.
At `ee37894af`, both were 8,186 bytes with a v0.51.0 qualified excerpt. Read-only
`manifests/stack.json` inspection pins RTK 0.51.0 to
`e001f773f80b22b7dc4c7a79521b30e35aaef026`; `gh api
repos/rtk-ai/rtk/git/ref/tags/v0.51.0` confirms that tag resolves to the same commit.
Its [hooks/rtk-awareness-full.md](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/hooks/rtk-awareness-full.md)
exists and is byte-identical to the existing fixture: 1,121 bytes and SHA-256
`278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc`.

Restoring that complete body inside the template would make it 8,287 bytes before
any local qualification, exceeding the strict 8,192-byte ceiling. Use the
coordinator's carrier fallback: vendor those unchanged upstream bytes at
`adoption/templates/rtk-awareness-full.md`, with a single include marker in the
compact template. The existing managed-block writer expands it for the new-WSL
carrier, its CLI and the native/gateway worker lanes. No Codex `@` import is used.
The demonstrated gap is that RTK's
[native Codex installer](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/codex.rs)
writes RTK.md and a reference, while Codex's
[pinned instruction loader](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agents_md.rs)
does not expand that reference. This is assembly in the existing writer, not a
replacement of either upstream's installer. The native text is unchanged; local
exceptions follow it in a separate block and explicitly qualify its blanket
prefix and output/exit-status assurances. All role projections carry the same
verbatim awareness body; their source/mirror checksums and independent literal
checks are updated. The lane test now checks v0.51.0 and the complete native body.
The status checker again requires the entire native text; it rejects the earlier
two omissions.

| File/scope | Round 2 / ee37894af bytes | Round 3 bytes |
| --- | ---: | ---: |
| Root AGENTS.md | 10,959 | 10,959 |
| Repo CLAUDE.md | 766 | 766 |
| Portable Claude source and carrier | 11,575 | 11,575 |
| Claude rendered user block | 11,841 | 11,841 |
| Codex compact template | 8,186 | 7,307 |
| Codex vendored native awareness | — | 1,121 |
| Codex new-WSL rendered carrier | 8,186 | 8,373 |
| Codex native/gateway lane rendered block | 8,186 | 8,373 |
| Codex full inline source before local qualification | — | 8,287 |
| Claude startup scope | 23,566 | 23,566 |
| Codex startup scope (new-WSL carrier plus root) | 19,145 | 19,332 |

Both the new-WSL and native/gateway writers produce 8,373-byte Codex carriers:
7,307 compact-source bytes minus the 55-byte include marker plus the 1,121-byte
native awareness file. Before the separate 86-byte local qualification, the full
inline source is 8,287 bytes. Its upstream awareness body remains byte-identical.
The 8,192-byte local check applies only to the compact source; the startup gate
counts the complete rendered carrier, including all native RTK bytes. Repair
round 4 verifies each output with `wc -c`; the earlier four-byte discrepancy was
an incorrect measurement.

This is the dated measurement and alternative comparison required by the change
procedure above. The accepted fixed ceilings stay 24,458 Claude and 20,103 Codex,
with 892/771 bytes of headroom in the measured new-WSL scopes. No automatic
re-baseline or ceiling increase is made. The first ceiling raise remains caused
by S1–S3, as corrected in round 2; this source restoration fits the existing
ceilings. The rejected RTK alternatives are rewriting its text again, keeping a
bare Codex reference, or exceeding the template limit. Replace the assembly only
when upstream Codex expands the native reference or RTK provides equivalent
native inline installation, then verify the exact pinned content and remeasure.

**The coordinator's host gate remains pending.** Re-render both hosts and read
back the existing routing/schema sentences, the complete pinned RTK body in
Codex and NativeStack2604's 0.05 fraction and native Skills row. After that gate,
the 868-byte root routing paragraph becomes the 188-byte pointer, removing
680 bytes from both startup scopes. In the same reviewed diff, remeasure and
lower the fixed ceilings to those actual scopes plus 5%, rounded upward. For
these new-WSL inputs, that means 22,886/18,652-byte scopes and 24,031/19,585-byte
ceilings, superseding round 2's projected Codex 19,389 ceiling. The standalone
native block produces the same 18,652-byte post-gate Codex scope and 19,585-byte
plus-5% ceiling. The coordinator records the actual host carrier after read-back.
Freed routing bytes cannot become permanent growth headroom. No host
user file or protected stack/evidence manifest is changed by this repair.

### Round 3 local acceptance

| Command | Exit | Result |
| --- | ---: | --- |
| `python3 -m unittest tests.test_landscape_sweep_harness tests.test_landscape_sweep_skills tests.test_runtime_worker_skills` | 0 | 421 tests, 7 skipped |
| `python3 -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_scaffold_repo tests.test_new_wsl_client_config tests.test_new_wsl_handbook tests.test_managed_block tests.test_upstream_surface_watch` | 0 | 655 tests, 22 skipped |
| `python3 -m unittest tests.test_codex_agents tests.test_codex_roles tests.test_skills_manifest` | 0 | 90 checks of the updated projections, checksums and listing policy |
| `node test-envelope.mjs` from `examples/claude-native/workflows` | 0 | `SUMMARY passed=254 failed=0 total=254` |
| `node test-contract-mutations.mjs` from the same directory | 0 | `SUMMARY passed=74 failed=0 total=74` |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | carriers regenerated with no source units dropped |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | current carriers and wiring |
| `python3 scripts/build_new_wsl_handbook.py --check` | 0 | generated handbook is current; no regeneration needed |
| `python3 scripts/validate.py` | 1 | registry SHA-256 and byte-count drift only; coordinator refreshes registry last |
| `wc -c adoption/templates/codex.AGENTS.template.md` | 0 | 7,307 bytes, strictly below 8,192 |
| `git diff --check` | 0 | clean |

The first seven-module pass found one incorrect generated-record count (0 rather
than 24 pieces not wired by their own entry). Correcting the dated counts and
rerunning the record checks and the full seven-module group gave the passing
result above. The initial writer run also refused a `directive` field on a
practice entry; that field is for slot-owner selection. The practice's user
source belongs in its `source` and `note` fields, where it now stays; the rerun
passed. These are local integration and synthetic-fixture checks. No full CI
suite, macOS run, provider/model trial or host rollout is claimed here. The
protected manifests are unchanged; rebase, host rollout and registry refresh
remain the coordinator's work.

## 2026-10-05 repair round 4: main settings surfaces and measured writer bytes

The Opus gate read of `4f490d3ab` found one adoption-state conflict and three
remaining inconsistencies. Restore main's two skill-setting disposition rows
exactly from `origin/main@c148e049efee75f8ea8a9a009e7b96b1e97f5c28`; they are also
byte-identical at this PR's recorded main base `a11dc5ff3`. Both rows stay
`adopt-pending`: the October 4 observation records that 2604 has the 0.05 fraction,
NativeStack lacks it, and both hosts trail the template's overrides. Repository
unit tests do not turn those historical host observations into completed adoption.
The coordinator's host render/read-back gate remains pending.

The [September 30 user directive](2026-09-30-skills-llm-native-listing.md) keeps
every eligible skill listed; the 0.05 fraction prevents listing truncation. Amend
the remaining anti-pattern row to distinguish unbounded startup instructions
from that accepted listing setting. Keep listing governed independently of the
startup byte gate. Restore `tools/adoption/apply_claude_settings.py` byte for byte
from the same main commit and use its ordinary settings merge, consistent with
the client-config map and its existing apply-settings tests. The simpler choice
is direct restoration of maintained main surfaces; adding another settings
mechanism supplies no required behavior for this accepted design.

Render through `new_wsl_client_config.generate_blocks`, `managed_block.merged_codex_md`
and `apply_codex_lane.agents_block`, then measure the resulting files with native
`wc -c`. Both Codex writers produce the same 8,373 bytes. The inline counterfactual
below removes only the separate 86-byte local qualification; the 1,121-byte
upstream awareness body remains unchanged. The post-gate projection replaces the
869-byte routing line (including newline) with the original 189-byte pointer,
removing exactly 680 bytes. These are temporary measurement outputs, not host
writes or removal of the pending routing guard.

| Measured output | UTF-8 bytes from `wc -c` |
| --- | ---: |
| Compact Codex source | 7,307 |
| Include marker | 55 |
| Verbatim RTK awareness | 1,121 |
| New-WSL rendered Codex carrier | 8,373 |
| Standalone native/gateway rendered Codex carrier | 8,373 |
| Full inline source before local qualification | 8,287 |
| Separate local qualification | 86 |
| Root AGENTS.md | 10,959 |
| Repo CLAUDE.md | 766 |
| Portable Claude source and carrier | 11,575 |
| Current Claude startup scope | 23,566 |
| Current Codex startup scope | 19,332 |
| Root AGENTS.md after the pending host gate | 10,279 |
| Standalone Codex startup scope after that gate | 18,652 |

The rendered carrier is `7,307 - 55 + 1,121 = 8,373` bytes. It exceeds the local
8,192-byte check, which covers only the compact source; the fixed startup gate
counts the complete rendered carrier. The tests and renderer comments now say
this explicitly. Round 3's inline-size and four-byte normalization claims were
incorrect; the corresponding comparison and projection paragraphs above
are corrected from these writer outputs. There is no runtime byte change.

Keep the current ceilings at 24,458 Claude and 20,103 Codex. After the pending
host gate, the standalone and new-WSL Codex projections both require the same
19,585-byte ceiling: `ceil(18,652 * 1.05)`. Claude's projected ceiling remains
24,031. Remeasure the actual host carriers and tighten in the same reviewed diff
as required above; this correction does not make freed routing bytes permanent
headroom or authorize a silent re-baseline. No protected manifest or host user
file is edited by this round.

### Round 4 local acceptance

| Command/group | Exit | Result |
| --- | ---: | --- |
| Three regression modules from round 3 | 0 | 421 tests, 7 skipped |
| Seven harness modules from round 3 | 0 | 655 tests, 22 skipped |
| `python3 -m unittest tests.test_upstream_surface_watch tests.test_apply_claude_settings` | 0 | 167 tests, 6 skipped; includes the separately requested watch rerun |
| `node test-envelope.mjs` | 0 | 254 passed, 0 failed |
| `node test-contract-mutations.mjs` | 0 | 74 passed, 0 failed |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | both current carriers retained |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | passed |
| `python3 scripts/build_new_wsl_handbook.py --check` | 0 | current outputs; no regeneration needed |
| `python3 scripts/validate.py` | 1 | registry drift only: 8 SHA-256 and 8 byte-count mismatches |
| `wc -c` on the rendered measurement files above | 0 | carrier 8,373; inline source 8,287; projected scope 18,652 |
| `git diff --check` | 0 | clean |

The first comparison reproduced all four gate findings against canonical main
and the existing writer outputs. After repair, the two disposition entries and
settings writer match main exactly; the active code, tests and documentation
follow its ordinary merge contract. This is local
integration and fixture acceptance, with no full CI suite, host rollout or
provider/model trial claimed. The coordinator commits, refreshes the registry
last and owns the pending host read-back and subsequent ceiling tightening.

## Addendum (2026-10-05): user-facing local time

[The local-time record](2026-10-05-user-facing-local-time.md) adds one 227-byte
sentence to the portable Claude block (+230 bytes with its bullet marker and
newline) and to the Codex `session-lanes` block (+228). `startup_files` measures
Claude 23,566 → 23,796 and Codex 19,332 → 19,560 startup bytes, under the
unchanged 24,458/20,103 constants (662/543 bytes of headroom); the compact Codex
source is 7,535 bytes. For these inputs the post-gate projection above becomes
23,116/18,880-byte scopes and 24,272/19,824-byte ceilings. The gate's reviewed
diff still lowers the constants to the measured post-gate scopes plus 5%. No
constant changes here. The top-rule/lanes pin named above moves from
`568ee365aeef3455fc901e648eb72d28cc3b49c39f1bfba7f5e39beed20479a8` to
`82e23b68466ed8b96566a229582f0c99fa1456a393e635f18cc5e65f601f4d09`: the pinned
segment runs to the RTK marker, so it includes the `session-lanes` lines.

## Addendum (2026-10-06): local-time review repair

The 2026-10-05 addendum's figures precede the local-time record's review
repair, which grew its sentence from 227 to 327 bytes. Against main, the
portable Claude block now gains 330 bytes and the Codex `session-lanes` block
328. `startup_files` measures Claude 23,896 and Codex 19,660 startup bytes,
under the unchanged 24,458/20,103 constants (562/443 bytes of headroom); the
compact Codex source is 7,635 bytes. For these inputs the post-gate projection
becomes 23,216/18,980-byte scopes and 24,377/19,929-byte ceilings. No constant
changes here. The top-rule/lanes pin moves from
`82e23b68466ed8b96566a229582f0c99fa1456a393e635f18cc5e65f601f4d09` to
`d21bb3bc0a2e68fb362af1d085da3761a08cc5ccec18ebd7ed16dd83d80bb3cd`. The
[local-time record](2026-10-05-user-facing-local-time.md)'s 2026-10-06
addendum holds the measurement table and the checks.

## Addendum (2026-10-07): instruction core

The [instruction-core decision](2026-10-07-instruction-core.md) trims the three
startup sources and lowers both fixed ceilings by the procedure above.

| Client | Scope before | Old ceiling | Scope after | New ceiling |
| --- | ---: | ---: | ---: | ---: |
| Claude | 23,896 | 24,458 | 19,471 | 20,445 |
| Codex | 20,101 | 20,103 | 15,778 | 16,567 |

Each new ceiling is the measured scope plus 5%, rounded upward, and the constants
change in the same diff. The compact Codex template is 7,418 bytes, below the
unchanged 8,192-byte bound, and its rendered block is 8,484 bytes.

That decision supersedes the root copies named in "Required startup behavior and
accepted-record amendments" above: cross-family dispatch and the full routing
paragraph inline in root `AGENTS.md`, the discovery conditional and S1 on root,
and the root trading trigger. Both user-level blocks keep those sentences, and
the trading trigger now sits in `.claude/rules/trading.md` with a root pointer.
The StructuredOutput restoration, the verbatim RTK block, S2, S3 and the
8,192-byte bound stand.

Root's routing copy is now a 141-byte pointer. The rollout gate above, as amended
on 2026-10-06, still required a read-back before that replacement. The command
center waived that condition for this change on 2026-10-07: the routing text
itself stays byte-identical in the Codex template, and only the root copy becomes
a pointer. The measured values above replace the 188-byte pointer and the 24,031
and 19,389 ceilings that were projected for the replacement.

Passage contract 01 leaves the active contracts, and `01.txt` stays as its
October 5 snapshot. Contracts 12 and 13 bind the courier recipe and the
upstream-practice citation sentence to the workflow README's mechanics section.
No host file changes with this addendum.
