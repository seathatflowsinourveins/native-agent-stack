# Decision: the new-WSL architecture edition of the ecosystem guide (2026-10-01)

**Decided by:** units W1 and W3 of the 2026-10-01 new-distribution wave, on branch
`claude/new-wsl-architecture-topic-20261001`, written at `origin/main@5597f9fa` (the merge of #511). Every
`path:line` below is that revision's line unless the text names another revision.

## Context

The generated guide (`docs/ecosystem/index.html`, built by `scripts/build_ecosystem.py` from
`docs/ecosystem/template.html`) had one hard-wired topic edition, the token-efficiency stack
(`docs/token-efficiency-stack.json`, keyed on stack components). It had no single manifest that says, for
every catalog layer, what a session installs on a new WSL distribution, at which pin, under which verdict and
on what evidence.

The inputs already existed in the repository, spread over several records:

- the five `close_only_when` items of `catalogs/landscape/research-state.json` (`saturation.close_only_when`)
  and its per-layer status (`comparison_required`, `new_host_required`, `on_requirement_change`);
- the 20 foundation layers of `catalogs/foundation/manifest.json` and the 12 us-equities layers of the
  research state;
- the 2026-09-22 layer verdicts in `catalogs/landscape/foundation.json` and `catalogs/landscape/us-equities.json`,
  and the sweep ledger `catalogs/saturation/ledger.json`;
- the pins of record in `manifests/stack.json` and `adoption/pins-linux-x86_64.json`, the engine and broker
  boundaries in `catalogs/us-equities/runtime-target.json`, and the profiles and recipes of
  `adoption/manifest.json`;
- the acceptance classes of `docs/acceptance-evidence-policy.md:26-33`.

A closure assessment of the 20 foundation layers (2026-10-01, at `3361b342`, each assessment refuted and
corrected by a second reviewer), a closure assessment of the 12 us-equities layers (2026-10-01, at PR
#358's head `4d11709c`, same method) and the Gate A owner's draft for three layers fed this edition as working
input. The foundation assessment lands as `evidence/artifacts/layer-closure-assessment-20261001/` with PR #573; the
trading one stays with the trading lane owner. The edition therefore carries only the facts that a repository path
or a URL read on 2026-10-01 supports, each cited where it is used. Item statuses are one assessor and refuter
pair's judgment: where a layer ran twice, the border between met and partial or between partial and unmet moved in
some cells, and no run makes a layer final. The foundation rows use the first complete result per layer and the
us-equities rows the last, which is the basis of that assessment's synthesis. The core files those assessments cite
(`catalogs/landscape/foundation.json`, `catalogs/saturation/ledger.json`, `manifests/stack.json`,
`adoption/pins-linux-x86_64.json`, `catalogs/foundation/manifest.json`) are unchanged between `3361b342` and
this edition's base. Seven pull requests carried sources that were not on main at that base. Five have merged
since: the new-distribution recipe (PR #569, merged as `ad7d645b`), the Harbor E2E receipt (PR #570, `000aae77`),
the trading convergence record (PR #358, `326dc84b`), the program record with the foundation assessment
(PR #573, `25098f8a`) and the trading lane's verdict record (PR #578, `65a7b030`). Two are open: the Codex lane's
layer reviews and crosswalk (PR #575, head `51cb79ba`) and the runtime-workers blueprint README (PR #535, head
`1195e212`).

## Alternatives

1. **Extend the token topic.** Rejected: it keys on selected stack components and three groups, and its
   validator forbids row-level pins; catalog layers, `cross:` rows and per-layer closure do not fit it.
2. **A separate static report page**, like `docs/ecosystem/claude-upstream-checks.html`. Rejected: it would
   leave the single offline page, the input hashes the generator records and the publish workflow's
   private-content scan, which all act on `index.html`.
3. **A Markdown table.** Rejected: nothing would check that a pin matches the stack, that a cited file exists
   or that a "closed" row really meets the five items.
4. **Data-model choices inside the selected path.** `closure` is flat, as the unit brief specifies
   (`c1`..`c5` plus one `missing` string naming each open item); a per-item object was considered and
   dropped. `upstream_currency` sits on each winner rather than on the row, because most rows have several
   winners with separate release pages. A source not yet on main is a structured `pending_source`
   (path, pull request, optional commit), linked through the pull request and not hashed, rather than free
   text in `notes`, so a later edition can move it to `source_path` mechanically.

## Decision

Add a second hard-wired topic to `scripts/build_ecosystem.py` (`ARCHITECTURE_TOPIC`, loader
`build_architecture`, row validator `architecture_row`, page key `data.architecture`) and a tab
"05 Final architecture" to the template, hidden when the edition file is absent. The edition file is
`catalogs/foundation/new-wsl-architecture-20261001.json`.

**What the page shows.** The edition header (date 2026-10-01, base commit, scope, verdict rules verbatim,
the meaning of each verdict and evidence class, the five closure items read from the research state, the
sources) and a line that counts closed rows from the data. One table per catalog (foundation, us-equities,
cross) with columns Layer, Winners (pin), Verdict, Evidence class, Reasons and Install on the new distro; each
row expands into the closure items with what is missing, each winner's pin locator, install and acceptance
commands and upstream currency, the alternatives, the ordered new-host steps and the gates.

**Verdict rules (recorded verbatim in the edition).** A layer is "closed" only when all five close_only_when
items of research-state.json hold; otherwise "selection_of_record_open" with the missing items named. The
winner cell carries the pin of record only (manifests/stack.json or adoption/pins-linux-x86_64.json for stack
components; catalogs/us-equities/runtime-target.json for the engine and brokers; the adoption profile recipes
for install commands). The evidence class is stated per row. Paper results count only as fills and passed
trials. Upstream and user-side gates are gates.

**Verdict values.** `closed`, `selection_of_record_open`, `provisional` (the owner keeps the selection as the
install default but marks it contested), `comparison_required` (from the research state or the row's owner),
`new_host_required` (the remaining evidence needs another host) and `no_selection` (no pin of record exists).
The research-state status maps directly; `on_requirement_change` becomes `selection_of_record_open`.
Token efficiency is `provisional` on the Gate A owner's call. Scheduling and supervision is
`comparison_required` on the program record's call (PR #573, decision 1): its selected Dagu 2.16.6 failed the
preregistered SIGKILL case.

**Evidence classes.** The six classes of `docs/acceptance-evidence-policy.md:26-33`, plus `source_review` and
`none_recorded`, two levels below the table: AGENTS.md keeps metadata, pinned source review and native
execution apart. A winner's acceptance class describes a run that the cited source, or one file that source
links, shows was run on a host and what it returned. A check that is only prescribed, planned, not run or failed
is `none_recorded`. Schema, pin, hash and contract-test checks are `structural_validation`. A version print is
metadata, not an acceptance. The `command` names the check the record is about; on a `none_recorded` entry it
names the check to run on the new host, of which no run is recorded. An independent review on 2026-10-01 found 32
of the 119 winner acceptance classes overstated, 13 commands that were only version or status prints and 6 entries
it could not settle; this revision corrects them. 55 of the 119 entries changed (32 classes, 48 commands and 31
cited sources); the lane owners re-cited their winners to the files that record the runs; 13 `none_recorded`
entries got their check to run back; restic is cited to its off-host receipt in four rows; and three rows that had
no winner gained six. The edition now has 125 winner entries: 72 `upstream_example_or_native_operation`, 24
`local_integration_check`, 14 `structural_validation`, 1 `independent_observation` and 14 `none_recorded`, 11 of
which name the check to run. Row classes: 13 `local_integration_check`, 10 `none_recorded`, 7
`structural_validation`, 6 `upstream_example_or_native_operation` and 1 `independent_observation`. The six policy
classes have no defined order, so the build enforces what can be enforced:
when any winner's acceptance is `none_recorded`, the row's class is `none_recorded`; otherwise the row's class is
one that at least one winner's acceptance carries, and where the winners carry several, the edition records the
one listed last in the policy table. A row without winners keeps its owner's class. Stronger evidence for one
winner stays in the reasons. Every class describes source-host history; a new distribution collects its own
evidence.

**Validation the build enforces.** Known layer ids or `cross:<name>`, a layer's identity being its
`(catalog, layer_id)` pair; the row catalog matches its layer; exactly one of `component_id` (a
`manifests/stack.json` component) or `name`; when a component's recorded version in the stack differs from the
winner's pin, the build passes, the page notes the drift on that winner ("the stack now records <version>") and
the `--check` JSON lists it under `architecture_pin_drift`, the token topic's precedent for a dated edition; an
optional `role` per winner (non-empty, at most 120 characters), rendered beside its name, because winners are the
components of the selection of record and some are not its destination; public HTTPS repositories and currency
links; a `pin_source` of one repository file with an optional line range inside it; every `source_path` a
repository file, hashed into the page inputs and linked at the publication ref; a `pending_source` whose path
exists as a repository file is treated as landed, hashed and linked like a `source_path` with the label "landed
after this edition's base (pull request #N)", so a later merge never fails the build; enums for verdicts, evidence
classes, closure states, install kinds and gate kinds; `closed` if and only if all five items are `met`; a
non-empty `missing` for every open row and an empty one for a closed row; a `missing` that starts with one
`cN: ...` segment for each item that is not `met` (segments separated by `; cN:`) and has none for a `met` item,
a trailing sentence without a `cN:` prefix staying allowed; the row's evidence class rule above;
`no_selection` if and only if there are no winners; and the sha256 of the five `close_only_when` texts (joined in
order with newlines, no trailing newline), recorded as the edition's `close_only_when_sha256`, so a reworded or
reordered research state fails the build instead of showing each row's states beside other texts. A catalog layer
without a row is listed on the page, not a build failure, so adding a layer elsewhere never breaks the page.

**This edition's rows.** 37 rows: 20 foundation, 12 us-equities, 5 cross. Closed: none. 20
`selection_of_record_open`, 14 `comparison_required`, 2 `new_host_required`, 1 `provisional` and no
`no_selection`. Every assessed row has at least one closure item unmet or partial, and no review item
(c4) is met. The twelve us-equities rows follow the trading closure assessment: their winners are the components
the layer's current choice names that have a pin of record (runtime-target.json for the engine, the brokers
and the adaptive paper engine; stack pins for profile components), while the 2026-09-22 verdict winners
without such a pin (DVC, pandera, agent-retrieval-bench, Inspect AI, MLflow) stay alternatives.
The trading lane owner's verdicts of 2026-10-01 call every trading layer "selection of record, open". Two
layers had no selection of record for the layer itself (research-factors-ml and security-supply-chain). After a
cross-family adjudication in the Codex lane's reviews, the owner recorded one for each the same day (PR #578):
EdgarTools and skfolio for the first, which reads `comparison_required`, and Syft, Gitleaks and Grype for the
second, which reads `selection_of_record_open`, with Grype pinned by the foundation automation catalog. Neither
decision closes anything. The other rows read `comparison_required` where the research state asks for a
comparison and `selection_of_record_open` otherwise. The owner corrected the trading winners' acceptance sources
in this change's pull request (#574) and re-read the twelve rows there, and each row's notes carry the owner's
verdict and blocking item verbatim. The keys lane corrected the credential-practice row and worded it again
after its canary proof merged (PR #579, the first update of this edition under overturn condition 5), and the
Gate A owner decided the acceptance entries of its three rows the same way. The backtesting-engine row carries
the dispute recorded at PR #358's head `b0eb7a11`.
Paper results appear only as fills and passed trials (the 2026-09-29 Alpaca series: 11 of 13 trials passed,
41 entries and 39 exits filled). The cross row for the distribution is `new_host_required`: its image, hash
and creation path are on main since PR #569, selected by source review, and nothing has run on a host; the
recipe's follow-up with the completeness critic's pre-checks is open, and stage 1 waits for it.

**Install order on the new distribution** (row `cross:wsl-distro`, each step citing the recipe of PR #569):
stage 1 on Windows; first boot (systemd, linger, user bus, packages, subordinate ids, the login hand-off);
a clone of origin/main and the host file on free ports; credentials before any keyed tool; stage 2 with the
token-efficiency profile, native sign-in, the Context Mode plugin started once before the settings step
(its start script writes the SessionStart cache-heal hook that the settings template runs), then
`--configure-full-profile`; then the layers outside the profile; observability last.

**Residual gaps.**
- Upstream currency is one read per pinned winner on 2026-10-01 (GitHub releases, or the named registry
  page); it was not repeated. Serena, ECC, the guard and the convergence practice carry `unknown`.
- `pin_source` content is not checked: validation checks the file and the line bounds, not the line's content;
  the content was checked when the edition was written. Two winners cite a file that cannot establish their
  pin: the adaptive-paper engine is pinned to a merge commit (`dca821cc`), which no file in that merge can
  record, and the convergence practice is pinned to this edition's base commit, cited from this edition's own
  `base_commit` line.
- The cross rows had no closure assessment; their closure items rest on this edition's reading, and items it
  cannot establish are `unknown`.
- The acceptance review of 2026-10-01 read one hop from each cited file (a receipt or artifact the cited file
  links directly) and no further, and it rated part of its corrections below high confidence: by entry, 10 of
  the 32 medium, 9 medium-high and 3 low.
- Item 4 for the layer rows: the Codex lane's cross-family review of all 32 layers (PR #575 at `51cb79ba`,
  gpt-6.1-sol) was performed on 2026-10-01 and names remaining gaps in every layer. Each foundation and
  us-equities row cites its review; the item cells keep the closure assessment's reading until the layer records
  are re-recorded. Those reviews select different component sets from this edition's winners in 20 of the 32
  layers (by a name match, 39 names only here and 41 only there, for example the scanners of ci-supply-chain and
  the observability components of observation-inference). This edition keeps the catalogs' selections of record
  and the owners' decisions; the re-record pass of the program record (unit U4) reconciles the two. The same
  pull request carries the crosswalk from the guide's ten themes to the 32 layers, which this edition references
  and does not duplicate, and each repository's upstream-documented install command, none of them run.
- Subordinate ids for the Harbor harness: the recipe allocates 65,536, Docker's documented minimum. A wider
  range is an image-set need, added only when a pull fails with `lchown <FILE>: invalid argument`; the
  workstation's 262,144 for six matplotlib SWE-bench images is recorded in the Harbor receipt of PR #570.
- Hindsight's stale and paused pages and held cold seed, and the held automatic Codex PTY submission through
  AgentRelay, are carried as gates on the word of the production program; its receipts are not published.
- The token topic's cards still record socraticode 1.14.0 and ccusage 20.0.24 against stack pins 1.15.0 and
  20.0.26; this change does not touch that topic.
- The research state (5 foundation layers `comparison_required`) and the layer records (9 `keep_but_compare`)
  disagree on which layers need a comparison; this edition follows the research state, with the one exception
  the program record makes for scheduling and supervision.
- Rows do not carry the themed explorer layer as `theme`; cross-linking the explorer is left out.

## Overturn condition

Write a new edition, or update this one in the change that causes it, when any of these happens:

1. **A layer closure.** All five items hold for a row; the build then requires `closed`.
2. **A pin move.** A winner's version changes in `manifests/stack.json`: the build still passes, the page
   notes the drift on that winner and `--check` lists it under `architecture_pin_drift`; re-read the row and
   record the new pin in the next edition. A `component_id` that leaves the stack still fails the build. A move
   in the Linux pins file or runtime-target.json is caught by the line-bounds check only when the line
   disappears, so re-read those rows.
3. **A new upstream release** of a winner, or a qualification that moves a pin (Codex 0.159.3 first).
4. **A pending source lands.** PR #575 or #535 merges: the build hashes the landed file and labels it as
   landed after this edition's base. PR #569, #570, #358, #573 and #578 have landed: their citations are plain
   `source_path` entries now, and `cross:wsl-distro` was re-rated when #569 did.
5. **A lane owner changes a verdict or its wording** for one of its rows.
6. **The Gate A multi-agent E2E runs** on the new distribution: it decides the token-efficiency verdict.
7. **A new catalog layer** appears in the foundation manifest or the research state: the page lists it as a
   gap until a row is added.

## Sources

- `catalogs/landscape/research-state.json` (`saturation.close_only_when`; per-layer status)
- `catalogs/foundation/manifest.json`, `catalogs/landscape/foundation.json`, `catalogs/landscape/us-equities.json`,
  `catalogs/saturation/ledger.json`
- `manifests/stack.json`, `adoption/pins-linux-x86_64.json`, `adoption/manifest.json`, `adoption/bootstrap.md`,
  `adoption/bootstrap-linux.sh` (fail-closed on unpinned profile components; node, uv and gh always installed)
- `catalogs/us-equities/runtime-target.json`
- `docs/acceptance-evidence-policy.md:26-33`; AGENTS.md (evidence levels)
- `docs/decisions/2026-09-30-task-model-routing.md:9-12` (the accepted token-efficiency profile, #540)
- `scripts/host_receipts.py` (a receipt binds only to a version that matches a winner pin)
- PR #569 (merged as `ad7d645b`): `adoption/platforms/linux-wsl2-new-distro.md`,
  `docs/decisions/2026-10-01-new-wsl-distro-recipe.md`, `adoption/templates/wsl/`
- PR #570 (merged as `000aae77`): `evidence/receipts/harbor-e2e-token-tools-20260930.json`
- PR #573 (merged as `25098f8a`): `docs/decisions/2026-10-01-definitive-sota-wsl-program.md`,
  `evidence/artifacts/layer-closure-assessment-20261001/`
- PR #575 at `51cb79ba`: `evidence/artifacts/new-wsl-layer-reviews-20261001/` (the 32 layer reviews and the
  selection-gap follow-up),
  `catalogs/foundation/new-wsl-layer-crosswalk-20261001.json`
- Docker Engine documentation, rootless mode, prerequisites and troubleshooting (read 2026-10-01); the Next.js
  v16.3.8 release page (read 2026-10-01)
- PR #358 (merged as `326dc84b`): `catalogs/us-equities/convergence-20260926.json`
- PR #578 (merged as `65a7b030`): `docs/decisions/2026-10-01-trading-layer-verdicts.md` (the trading lane
  owner's verdicts and the two selections of 2026-10-01)
- Upstream release pages read on 2026-10-01 (07:41Z to 08:06Z), each cited on its winner; the
  nautilus_trader issue #4983 and pull request #5041 states; the gitleaks README; the Harbor README
  (`uv tool install harbor`)
