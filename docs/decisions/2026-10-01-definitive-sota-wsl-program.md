# Definitive SOTA WSL program: finalize every layer, then build the clean runtime (2026-10-01)

**Status:** program record, opened 2026-10-01. The foundation table landed on 2026-10-01 (20 layers, none final for
install); the us-equities table follows when its assessment completes.

## Decision

The definitive runtime is a new WSL 2 distro, imported from an official upstream image and bootstrapped from this
repository at a recorded revision (decision 4), in which each layer's selected repositories are installed cleanly with
their upstream-supported commands by an LLM-native session. Gate A's token-adoption E2E re-aims at the new distro (the
user's decision of 2026-10-01 03:33Z): the measurement host is the new distro, which collects its own evidence; the
current workstation distro's Gate A freeze is lifted and keeps whatever the production program runs there. The
production program's composition (Codex 0.159.3, AgentRelay 13.0.0, Relaycast 8.14.0, Hindsight 0.10.2 with the 0.8.0
coding integration, NautilusTrader 2.0.0rc5) is a candidate composition for the new distro, not a selection. A
component with a catalog layer enters through that layer's closure: durable-memory is `comparison_required`, with
ai-memory the selection of record and Hindsight a fit target whose holds the production program reports and has not
published here yet; Codex 0.159.3 is unqualified against the 0.159.2 pin of record. AgentRelay and Relaycast have no
catalog layer, so they enter only once a layer or a cross row with its own decision record names them. An install on
the new distro counts as final only for a layer whose selection is final; until then it is a provisional install
under decision 3. Every install leaves a per-layer receipt registered through the hot-file protocol
(`docs/lanes.md`).

## Source of the decision

The user, 2026-10-01 ~03:20Z: finalize each layer and start the definitive SOTA WSL with the full SOTA architecture for
each layer's repositories, resolving cleanly for a new advanced runtime that culminates in the final architecture
repositories with evidence for each layer, paving the way to complex projects, system building and the north star;
~03:30Z: resolve with each repository installed cleanly with upstream commands in the new WSL by an LLM-native session.
The Gate A owner's earlier ruling A (03:17Z: measure on the current distro, revert its drift, build the new distro
after the last window) is superseded by that decision; see "Gate A re-aim". WSL 2 distros still share one virtual
machine (CPU, memory, disk and network namespace), so a window needs a load check on the shared machine.

## Closure criterion per layer

A layer is final only when every item of `catalogs/landscape/research-state.json` `saturation.close_only_when` holds:

1. a selected choice, named alternatives and recoverable primary evidence;
2. the frozen candidate and source set recorded, including failed access and explicit omitted or out-of-scope reasons;
3. the required representative comparisons and target-host lifecycle checks meet preregistered acceptance, with
   missing evidence left open;
4. a second independent review finds no unresolved material gap in that bounded set;
5. a dated closure record lists residual risks, untested boundaries and exact reopening triggers.

Evidence classes follow `docs/acceptance-evidence-policy.md`: unchanged upstream tests, local integration checks,
synthetic fixtures and live provider execution are distinct; a new host collects its own evidence, and a receipt from
the workstation never certifies the new distro. Closure is therefore staged: a layer's selection is final before its
install when items 1, 2, 4 and 5 hold and the preregistered comparisons of item 3 are done; the target-host lifecycle
checks of item 3 are collected on the new distro as the install receipt, and the layer is closed only when that receipt
is registered. Workstation receipts never substitute for them.

## Program decisions on the criterion (2026-10-01)

The foundation assessment (see "Per-layer gap tables") raised four questions the tables depend on. Three are the
coordinator's. One is the user's and carries a default until it is answered.

1. **Which record says a layer needs a comparison.** `catalogs/landscape/research-state.json` governs, because it
   holds the criterion. It marks 13 layers `comparison_required` (5 foundation, 8 us-equities) and 1
   `new_host_required`. `catalogs/landscape/foundation.json` disagrees on six foundation layers: semantic-rag,
   scheduling-supervision, recovery-portability, observation-inference and secrets-credentials are `keep_but_compare`
   there without `comparison_required` here, and quality-evaluation is `comparison_required` here and `retain` there.
   The re-record pass (unit U4) reconciles each of the six with a reason, in one direction or the other. One
   exception applies at once: scheduling-supervision is treated as `comparison_required`, because its selected Dagu
   2.16.6 failed the preregistered 150 s SIGKILL case that Temporal passed
   (`evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/6-executed-challenger-comparison.json`:
   "under the preregistered protocol and 150 s bound Dagu sigkill is false"). The Temporal arm ran the native
   development server, which `catalogs/us-equities/hosting-source-review.json:60` calls developer evidence only, so
   the exception reopens the comparison and selects nothing.
2. **What "frozen" means in item 2 (the user's decision; the default applies until answered).** Default: a candidate
   and source set recorded at a named revision, with a disposition or an omission reason for every proposal of the
   2026-09-23, 09-26 and 09-29 sweeps and the failed access listed. The default rests on item 2's own wording, which
   asks for a recorded frozen set and not for a number of sweeps. Neither repository source settles whether a
   saturation candidate (the policy of `catalogs/saturation/ledger.json`: 3 clean sweeps at least 7 days apart) must
   come first. `scripts/saturation_ledger.py:28-31` says "A saturation candidate is only an input to closure", which
   makes a candidate insufficient and is silent on whether one is necessary. `recipes/saturation-sweep.md:179-180`
   says "When a layer reaches `saturation_candidate`, the landscape owners decide whether to add `closure_refs`", an
   ordering the stricter reading rests on. Six assessments take the stricter reading; under it no layer closes for
   at least 14 days. Overturn: the user asks for the stricter reading.
3. **Where a comparison runs.** A preregistered comparison runs on the current distro or another named host and
   carries that host's evidence class. Only the lifecycle check is collected on the new distro, as the install
   receipt. A comparison that can only run on the target host is a provisional install there: preregistered,
   receipted, behind the exported checkpoint of "Baseline, checkpoint and rollback on the new distro", and rolled
   back or left uninstalled when it misses its metric. recovery-portability, the one `new_host_required` layer, is
   such an install by definition. The stage-2 bootstrap is itself a provisional install: an adoption profile
   installs the selections of record of layers that are not final, so each of its components stays provisional until
   its layer closes, and a selection that changes at closure is replaced through the layer's lifecycle steps
   (`adoption/lifecycle.md`) or by a rebuild from the checkpoint. A layer with neither a finished comparison nor a
   provisional install stays uninstalled, and its row of the install manifest says so. This answers the first finding
   of the Codex lane's review below. Overturn: the user wants no install on the new distro before a layer is final;
   stage 2 then waits for units U1 to U7.
4. **Which revision stage 2 installs.** `origin/main` at a recorded commit, as an interim: the pinned release
   `v2026.09.26.2` carries codex 0.155.1 and claude-code 2.1.281 in `adoption/pins-linux-x86_64.json`, behind the pins
   of record (0.159.2 and the 2.1.284 floor), and `adoption/bootstrap-linux.sh:186-199` refuses
   `--configure-full-profile` unless the checkout's HEAD equals `origin/main`. A new release tag is cut after the
   merge train lands, and each receipt names the commit it installed from. Overturn: a release tag at the pins of
   record exists and the bootstrap accepts it.

## Phases

| Phase | Content | Gate | Owner |
| --- | --- | --- | --- |
| 0 | Merge train (the freeze-list and lane PRs); the per-layer closure assessments start in parallel | eight required checks and the owner's script check per merge | the coordinator for the train; lane owners for their PRs |
| 1 | Per-layer closure assessment (read-only, source-cited, refuted, synthesized) for the 20 foundation and 12 us-equities layers; bounded comparisons with frozen inputs where item 3 is unmet; closure records | the criterion above, with a second independent review | foundation lane (coordinator); trading lane keeps the trading decisions and records |
| 2 | WSL import recipe (upstream image, `wsl --import` or `--install --from-file`, first boot, systemd, user services, terminal profile) researched from Microsoft and Canonical sources and recorded under `adoption/` | source-cited recipe; no host change before the last Gate A window closes | foundation lane; WSL package version stays with the keys lane |
| 3 | Import the distro (the stage-1 recipe); capture the pre-install baseline; bootstrap from the revision of decision 4 (`adoption/bootstrap-linux.sh --profile <id> --configure-full-profile --host <host>`); install each layer's selection of record with upstream commands, as final where the selection is final (items 1, 2, 4 and 5 of the criterion, with the preregistered comparisons of item 3 done) and otherwise as a provisional install under decision 3, collecting the target-host lifecycle checks of item 3 as the install receipt; native sign-ins on the destination; a recoverable checkpoint before stage 2 and an owned rollback | the baseline capture, `scripts/adoption_status.py --login-shell --client-wiring --pinned-versions`, `scripts/skills_status.py`, the layer receipts, `scripts/validate.py` | the LLM-native session on the new distro, under the coordinator |
| 3b | Gate A re-aimed on the new distro: the harness pilot, the re-aim amendment, the windows, the report | the Gate A owner's gates (the preregistration, the opening rules of the Claude and Codex families, the announcement of at least six hours) | Gate A owner |
| 4 | Complex projects and system building on the new runtime (general engineering) | the convergence loop of `docs/convergence-architecture.md` per project | the foundation lane and each project's owner |
| 5 | The trading north star on the new runtime | the north star's own gates (`catalogs/us-equities/runtime-target.json`) | trading lane |

## The grand HTML: the final architecture per layer, with reasons and verdicts

The user asked (2026-10-01 ~03:43Z) for the final architecture of each layer manifested into the generated ecosystem
guide with reasons and verdicts, for the new distro's Claude and Codex clients, the SOTA GPT-6 runtime workers and
SDKs, repository hosting, the rootless Docker CLI driven through the OmniRoute gateway on GPT-6.1 Sol, the token-save
practice, the foundation, memory and RAG, and beyond. The deliverable is a dated architecture topic edition of
`docs/ecosystem/` (built by `scripts/build_ecosystem.py`; precedent: the token topic's dated per-tool cards from
`docs/token-efficiency-stack.json`): one row per catalog layer with the winner repositories and pins, the reasons
(decision rationale, convergence votes, comparisons with their evidence classes), the verdict (selected, provisional,
comparison required, new host required) and the new-WSL install commands, each statement traceable to a decision
record, a receipt or a closure assessment. Its JSON source is the new-WSL install manifest. The generated page is
published as the `publish-catalog.yml` workflow artifact and, for the user, as a private page. The Codex runtime lane's
additive runtime-workers panel in the same build is referenced, not duplicated.

The edition is pull request #574: `catalogs/foundation/new-wsl-architecture-20261001.json` (37 rows: 20 foundation,
12 us-equities and 5 cross-cutting; none closed) and the tab "05 Final architecture". Each lane owner confirmed or
corrected its rows there.

## Baseline, checkpoint and rollback on the new distro

Before stage 2 the session captures the pre-install inventory (`wsl.exe --version`, the distro's package list,
`scripts/adoption_status.py --json` from the clean clone, the stage-1 receipt) and the operator exports the distro
(`wsl --export <Name> <file.tar>`, Microsoft's documented backup) as the recoverable checkpoint; every later layer
install captures `adoption_status.py --json` before and after and names the checkpoint it can return to. Rollback is
`wsl --unregister <Name>` followed by `wsl --import` of the checkpoint, owned by the coordinator; no rollback touches
the current distro.

## Ownership split

- Coordinator (SOTA-defaults lane): the merge train, the per-layer closure assessments, the WSL recipe, this record,
  the single host apply (B1) re-targeted at the new distro.
- Gate A owner: the harness pilot, Amendment 4 as the re-aim amendment, the windows on the new distro and the Gate A
  report.
- Production program: the runtime composition and its isolated package, daemon and memory qualifications; no shared
  client mutation on the current distro.
- Trading lane: the 12 us-equities layers' decisions and closure records; the paper units; the north star.
- Keys lane: credentials on the new distro (`docs/secret-storage.md`, "Setting up a new host"); the WSL package.
- Memory lane: the durable-memory selection (Hindsight 0.10.2 fit target; ai-memory scopes) and its evidence.

## Gaps recorded so far

- Release and re-pin: the pinned release `v2026.09.26.2` lacks five terminal-lane files and carries older copies of
  five others (`scripts/release_due.py` lists them), so a distro that follows the pinned release misses them.
- The Windows-side terminal steps (profile fragment, `settings.json`, the login-shell proof) are outside
  `--configure-full-profile` and form the operator checklist of the new distro.
- No evidence from a fresh distro exists yet for the terminal defaults, the bootstrap or any layer.
- Zero of the 32 layer targets were confirmed on 2026-09-28; 18 layers are `on_requirement_change`, 13
  `comparison_required`, 1 `new_host_required` in `catalogs/landscape/research-state.json` as of this record. The
  foundation catalog's own labels disagree on six layers (decision 1 of "Program decisions on the criterion").

## Per-layer gap tables

### Foundation, 20 layers (assessed 2026-10-01 at `3361b342`)

Source: `evidence/artifacts/layer-closure-assessment-20261001/foundation.json` (per layer an assessor's return as
corrected by an adversarial refuter; all 20 were corrected) and `foundation-synthesis.md` beside it. Evidence class: a
model-authored source review of the repository at that revision. It is not acceptance evidence, it certifies nothing
about the new distro, and its upstream "latest" values are the assessors' reads on that date, which the coordinator
did not fetch again. The coordinator checked at `3361b342` the sources of the statements this record relies on: the
criterion, the two catalog records' labels, the ledger policy, the receipt recorder's pin rule, the release tag's
pins, the Dagu comparison, the workers arms and the three manifest lines named under "Contradictions".

Result: no foundation layer is final for install. Item 1 is met in 9 layers and partial in 11. Item 2 is partial in
all 20. Item 3 is partial in 12 and unmet in 8. Item 4 is unmet in 17 and partial in 3. Item 5 is partial in 19 and
unmet in durable-memory. Columns 1 to 5 are the criterion's items. "Blocking item first" is the synthesis's pick of
the gap to close first from each corrected assessment; it is not the only gap and not a field of the artifact. The
verdict follows two rules: "closed" only when all five items hold, otherwise the selection of record stays open with
its gaps named.

Run-to-run variance. The workflow was resumed after a sign-in and ran seven layers a second time before it was
stopped; the table uses the first complete result per layer. In five of the seven the second result differs in one
or two cells (`foundation-run-variance.json` in the artifact folder): code-navigation (item 1 met, item 4 partial),
document-retrieval (item 1 partial, item 3 partial), durable-memory (item 1 partial), isolation (item 3 partial)
and semantic-rag (item 3 unmet). No difference makes a layer final for install: item 2 is partial and item 5 is
not met in every result. The item counts above are therefore one reading, and the border between met and partial
or between partial and unmet moves by a cell or two per layer between runs. Unit U6's reviews settle the cells.

| Layer | Status of record | Catalog label | 1 | 2 | 3 | 4 | 5 | Install command recorded | Pin is latest | Blocking item first | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| native-clients | on_requirement_change | retain | met | partial | partial | unmet | partial | partial | no | item 2: ten sweep proposals are not folded into the layer record, and four contested campaign proposals are not adjudicated | selection of record, open |
| instructions-skills | on_requirement_change | adjust | partial | partial | partial | partial | partial | partial | yes | item 1: the verdict stands at stale pins (ECC `dd6ee538` against `c70874fa`), and skills-ref is unclassified | selection of record, open |
| workers | comparison_required | keep_but_compare | met | partial | unmet | unmet | partial | partial | no | item 3: of the six preregistered arms (`catalogs/landscape/foundation.json:938-951`) only the executed baseline ran | comparison required |
| isolation | on_requirement_change | retain | met | partial | unmet | partial | partial | partial | no | item 2: no disposition for boxlite, microsandbox, brig, OpenSandbox, Lima and nsjail; the bubblewrap omission is open | selection of record, open |
| code-navigation | on_requirement_change | retain | partial | partial | partial | unmet | partial | yes | no | item 1: no public receipt for Serena's `find_referencing_symbols` | selection of record, open |
| document-retrieval | comparison_required | keep_but_compare | met | partial | unmet | unmet | partial | partial | yes | item 3: the sealed-corpus retrieval comparison and the layout and OCR comparison never ran | comparison required |
| semantic-rag | on_requirement_change | keep_but_compare | partial | partial | partial | unmet | partial | yes | no | item 1: winner pins 1.14.0 and 0.25.0 against installed 1.15.0 and 0.30.0 | selection of record, open; label to reconcile |
| durable-memory | comparison_required | keep_but_compare | met | partial | unmet | unmet | unmet | yes | no | item 3: the preregistered comparison on a host named in a new amendment; an operator decision on the live-store isolation breach is open | comparison required |
| web-research | on_requirement_change | retain | partial | partial | unmet | unmet | partial | partial | no | item 1: the selection predates the 2026-09-26 free-native-lanes decision | selection of record, open |
| token-efficiency | comparison_required | keep_but_compare | partial | partial | unmet | unmet | partial | yes | no | item 3: a repeated, counterbalanced matched comparison at equal correctness (`catalogs/landscape/foundation.json:2737-2750`). The Harbor E2E covers four of that protocol's five arms in the short single-session regime (the receipt of PR #570, block `catalog_protocol_metric`); the Repomix outline arm and the multi-agent regime are open. The re-aimed Gate A E2E tests the accepted profile in the multi-agent regime, not the per-tool protocol | comparison required; the install profile is provisional |
| quality-evaluation | comparison_required | retain | partial | partial | partial | unmet | partial | partial | yes | item 3: a comparison on fresh, independently labelled cases | comparison required; label to reconcile |
| ci-supply-chain | on_requirement_change | retain | met | partial | partial | partial | partial | partial | yes | item 2: the candidate set is not re-recorded (the tools in use, the 09-26 and 09-29 survivors, the 09-30 verdicts) | selection of record, open |
| scheduling-supervision | on_requirement_change | keep_but_compare | met | partial | partial | unmet | partial | partial | no | item 3: Dagu 2.16.6 failed the preregistered 150 s SIGKILL case, which Temporal passed | reopen candidate; treated as comparison required |
| hosting-services | on_requirement_change | retain | partial | partial | partial | unmet | partial | partial | no | item 1: Next.js winner 16.3.5 against lock 16.3.6, both behind a High-severity fix in 16.3.8 (assessor read) | selection of record, open |
| recovery-portability | new_host_required | keep_but_compare | partial | partial | unmet | unmet | partial | partial | no | item 1: the uv winner is `unpinned`, which the receipt recorder refuses (`scripts/host_receipts.py:882-886`) | new host required; label to reconcile |
| observation-inference | on_requirement_change | keep_but_compare | met | partial | partial | unmet | partial | partial | no | item 2: the 09-26 survivors have no disposition, and eight proposals lack the fit vote | selection of record, open; label to reconcile |
| agent-sdks | on_requirement_change | retain | partial | partial | unmet | unmet | partial | partial | no | item 1: the Python SDK half rests on a private prompt and sealed receipts | selection of record, open |
| mcp-surfaces | on_requirement_change | retain | met | partial | partial | unmet | partial | yes | no | item 2: no consolidated candidate set at the served pins | selection of record, open |
| secrets-credentials | on_requirement_change | keep_but_compare | partial | partial | partial | unmet | partial | yes | yes | item 1: the alternatives omit betterleaks, and two decision records are not linked | selection of record, open; label to reconcile |
| git-github-automation | on_requirement_change | retain | partial | partial | partial | unmet | partial | partial | no | item 1: the gh verdict pin is `unpinned` (2.101.0 installed), and the layer names no alternative | selection of record, open |

Patterns across the layers (from the synthesis; the counts are the artifact's):

- No second independent review. The reviews on record are lane adjudications or per-gap receipts, and each names
  open gaps.
- No closure record. Only the 2026-09-22 verdict rows exist, and they predate the later sweeps and host receipts.
- No frozen candidate set. The layer lists were checked on 2026-09-22 and never took in the proposals of the
  2026-09-23, 09-26 and 09-29 sweeps. Twelve assessments cite a host-private campaign list of 2026-09-30, which this
  repository does not hold.
- Verdict pins differ from installed pins in 14 layers. The receipt recorder refuses a version that matches no
  winner pin (`scripts/host_receipts.py:887-892`), so a receipt collected on the new distro before the re-record
  pass would not count.
- No fresh-distro evidence. `adoption/manifest.json:51` still reads "second-machine acceptance pending".
- The profiles cannot install the selections. In 16 layers a selected component is in no adoption profile, has no
  Linux pin, or sits behind a profile that exits 3.

### Program units, in dependency order

Owners are proposed from the path ownership of `docs/lanes.md` and are confirmed with each owner before dispatch. U8
and U9 run beside U3 to U7 and finish before U10.

| Unit | Layers | Action | Acceptance | Where | Proposed owner |
| --- | --- | --- | --- | --- | --- |
| U1 Program decisions | 20 | The four decisions of "Program decisions on the criterion" | this record, with an overturn condition per decision; `python3 scripts/validate.py` | source only | coordinator; decision 2 the user |
| U2 Pin-currency triage | 15 with a selected pin behind its latest release | Per pin: a dated hold with a reason, or a move after qualification, once per shared component; Next.js first | every behind pin has a hold or a qualification receipt | holds source only; moves on the current host | foundation; memory lane; trading lane for its recipes |
| U3 Campaign verdicts | 12 citing the private list; 8 with a proposal decided by a missing vote (ci-supply-chain, document-retrieval, durable-memory, observation-inference, recovery-portability, semantic-rag, token-efficiency, web-research, recomputed from `catalogs/saturation/ledger.json` by this record's reviewer) | Publish the 2026-09-30 campaign verdicts as a sanitized receipt at a main commit, or drop the citations; rerun the missing discovery and fit votes | every cited status resolves to a committed file; no proposal is decided by a missing vote | source only (model calls on the gateway pool) | foundation |
| U4 Re-record pass (items 1 and 2) | 20 | One `tools/sota-convergence/record_verdicts.py` pass per layer: winners at the U2 pins, alternatives, the frozen candidate set with dispositions, failed access, the six label reconciliations | `scripts/host_receipts.py` accepts each installed version without `--allow-unbound-version`; a check fails on a proposal without a disposition | source only | foundation; `manifests/stack.json` edits through the hot-file protocol |
| U5 Preregistered comparisons | the 5 `comparison_required` layers and scheduling-supervision | Run the frozen arms; keep failures and complete usage | the preregistered metric, independently reviewed | the current distro or a named host; a provisional install on the new distro where only the target host can run it | Gate A (workers, token-efficiency); memory lane (durable-memory); foundation (document-retrieval, quality-evaluation, scheduling-supervision) |
| U6 Second independent review (item 4) | 20, and the 12 us-equities layers | One cross-family source review per layer over the U4 and U5 output, listing the target-host checks as declared install-receipt items | no unresolved material gap except the declared install checks | source only | the Codex catalog lane; its first delivery is PR #575 (the 20 foundation layers reviewed on 2026-10-01, remaining gaps in every layer) |
| U7 Stage-1 closure record (item 5) | 20 | A dated record per layer: bound pins, residual risks, untested boundaries, reopening triggers, pending install checks; registered in `closure_refs` | the landscape checks pass; the layer is final for install | source only | foundation (landscape owners) |
| U8 Profile and pin coverage | 16 | Add the selections to the adoption profiles and `adoption/pins-linux-x86_64.json`; script the prose-only installs; provision CPython 3.13.15, procps and the sandbox prerequisites; fix the `orx` and `openresearch` id mismatch; give `jcodemunch-mcp` a Linux pin or stop the carrier naming it | each profile bootstraps on the hosted runner without `--allow-unpinned`; `scripts/adoption_status.py` is clean | source only | foundation; trading lane for the research-runtime profile |
| U9 Port and unit map for the shared virtual machine | durable-memory, quality-evaluation, scheduling-supervision, observation-inference, semantic-rag | Assign the ports and the systemd user units that two distros on one network namespace need | a committed map; on the new distro no port conflict, and the units survive a restart | decided now; verified on the new distro | foundation; memory lane |
| U10 Install receipts (the host part of item 3) | 20 | Bootstrap from the decision-4 revision; native sign-ins and the 0600 store; lifecycle stages through `scripts/host_receipts.py` with negative controls; append to the U7 record | receipts bind to the winner pins and pass the host checks; an independent receipt review; the layer is closed | the new distro | the LLM-native session there, under the coordinator; lane owners for their layers |

### Selected pins behind their latest release

These are the assessors' reads of upstream release pages on 2026-10-01. The coordinator did not fetch them again;
unit U2 does, pin by pin. One item is security-relevant and goes first: Next.js 16.3.8 fixes a High-severity advisory
above both recorded pins.

| Component | Pin of record | Latest per the assessor | Layers |
| --- | --- | --- | --- |
| claude-code | 2.1.284 floor (auto-updates) | v2.1.286 | native-clients, workers |
| codex CLI | 0.159.2 | rust-v0.159.3 | native-clients, agent-sdks |
| openai-codex and openai-codex-cli-bin | 0.154.0 | 0.159.3 | agent-sdks |
| worktrunk | 0.79.0 | v0.80.0 | workers, isolation, git-github-automation |
| sandbox-runtime | 0.0.77 | v0.0.78 (one assessor read) | isolation |
| jcodemunch-mcp | 1.108.319 | v1.108.320 | code-navigation |
| SocratiCode | 1.15.0 | v1.16.0 | semantic-rag |
| huggingface_hub | 1.32.0 | v2.0.0 (a major release) | semantic-rag |
| ai-memory | 2.4.1 | v2.5.0 | durable-memory |
| OpenResearch | 0.2.7 | v0.2.14 | web-research |
| headroom | 0.37.0 (a deliberate hold) | v0.39.1 | token-efficiency |
| Dagu | 2.16.6 | v2.18.1 | scheduling-supervision |
| FastAPI | 0.141.1 | 0.142.2 | hosting-services |
| Next.js | 16.3.5 and 16.3.6 | v16.3.8 (fixes GHSA-cjq9-62q9-8jv4, High) | hosting-services |
| uv | 0.12.17 | 0.12.21 | recovery-portability |
| otelcol-contrib | 0.161.0 | v0.162.0 | observation-inference |
| MCP Inspector | 2.8.0 served | 2.9.0 | mcp-surfaces |
| gh | 2.101.0 | v2.102.0 | git-github-automation |

Verdict-record pins also lag where the installed pin is current: rtk 0.49.0 and ccusage 20.0.24 (token-efficiency),
markitdown 0.1.7 (document-retrieval), vLLM 0.25.0 (semantic-rag), mcporter 0.13.13 (mcp-surfaces), Prometheus 3.14.0
(observation-inference) and ECC `dd6ee538` (instructions-skills). Inspector's verdict pin 2.7.0 lags too, and its
served 2.8.0 is itself behind.

### Install readiness

An upstream install command is fully recorded for 6 layers (code-navigation, semantic-rag, durable-memory,
token-efficiency, mcp-surfaces, secrets-credentials) and partly for the other 14. The six still miss steps on a new
host: a port held by another distro on the shared network namespace, a profile that exits 3 without
`--allow-unpinned`, components outside every profile, a hand-written marketplace file. The artifact lists the missing
new-host steps per layer (6 to 11 each). The synthesis groups them by kind: no upstream command recorded, a recipe
outside every profile, a native sign-in or user step, a service or port decision on the shared virtual machine, and
drift between a pin and its recipe. These lists feed U8, U9 and the install manifest's new-host steps. One gap
found outside the assessment joins them: no script runs the per-project jCodeMunch registration, and no adoption
profile installs `jcodemunch-mcp` (it has no Linux pin; only a manual line of `adoption/bootstrap.md` installs it),
although four of the six SubagentStart carrier blocks name its tools (PR #548's review and PR #569's follow-up,
2026-10-01). The registration is a recorded step of the new-distro recipe; the install belongs to U8.

### Contradictions the re-record pass resolves

- The foundation manifest's selection text differs from the landscape winners. token-efficiency:
  `catalogs/foundation/manifest.json:104` names jCodeMunch and Context Mode and omits ccusage, while the winners are
  rtk, headroom and ccusage. ci-supply-chain: `:122` names seven tools against three winners. native-clients: `:23`
  records the user's 2026-09-27 adoption of the OmniRoute gateway, which no landscape verdict selects.
- Seven layers select a practice with no repository pin: instructions-skills, code-navigation, web-research,
  quality-evaluation, recovery-portability, mcp-surfaces and secrets-credentials.
- Five winners are unpinned in the record (`catalogs/landscape/foundation.json:421,444,3224,4045,5085`): the TypeSafe
  and OpenAI skills of instructions-skills, actions/attest, uv and gh. The receipt recorder refuses each of them.
- Upstream signals on selected components, as the assessors read them: gitleaks is feature complete and takes
  security patches only; Context Hub has had no default-branch commit since 2026-07-01.
- Evidence outside the repository: twelve assessments cite the host-private campaign list, and the native-clients
  and agent-sdks prompts are private. Unit U3 publishes or drops them.

### us-equities, 12 layers

The assessment reads `4d11709c`, an earlier head of PR #358, because that pull request carries the trading lane's
current records. All 12 layers are assessed and refuted, and none is final for install: no layer meets item 4 or
item 5 in any run. The trading lane owner's verdicts of 2026-10-01 call all 12 "selection of record, open", two of
them (research-factors-ml and security-supply-chain) with no selection of record for the layer itself; later the same
day the owner recorded a selection for each, which closes nothing, and corrected and re-read the 12 trading rows of
the architecture edition in PR #574. The sanitized trading assessment and the owner's records are PR #578
(lane:trading); the decisions, the verdict wording and the closure records stay with that lane.

## Gate A re-aim (decided by the user, 2026-10-01 03:33Z)

The user decided: re-aim Gate A at the new WSL, with all the SOTA runtime workers and GPT-6 framework harnesses;
manifest the final winner repositories for the new WSL clean install into the native workflow and the foundation
catalog; include the seamless passwordless LLM-native workflow and the harness-convergence practice. The Gate A
owner's ruling A of ~03:17Z is superseded: the token-adoption E2E runs on the new distro after its clean install, the
current distro's drift revert is withdrawn for Gate A's sake, and the new distro's build waits only for the WSL
recipe and the winner manifest. The program gains one deliverable, the new-WSL install manifest: per layer the
selected repositories with pins, upstream install commands and evidence references, plus the runtime workers
(`blueprints/runtime-workers/`), the GPT-6 harnesses (the OmniRoute gateway, the Codex SDK lane, the sweep runner,
promptfoo, Harbor, Inspect), the key lane's passwordless practice (`docs/secret-storage.md`) and the convergence
practice (`docs/harness-defaults.md`, `docs/convergence-architecture.md`), consumed by the bootstrap and recorded
in the foundation catalog.

### Harness for the re-aimed E2E (open, 2026-10-01 03:36Z)

The Gate A owner's independent audit found that the merged top rule (`AGENTS.md:3`, recorded in
`docs/decisions/2026-09-30-rule-text-every-layer.md`: A/B and E2E use upstream harnesses, never a self-written runner)
covers the token-adoption E2E's custom runner, with no recorded exception. The owner therefore recommends path R:
re-scope the adoption E2E onto an upstream harness (Harbor or Inspect) on the new distro, with a pilot as step zero:
the Gate A owner's receipt of the 2026-09-29 Harbor E2E (`evidence/receipts/harbor-e2e-token-tools-20260930.json`,
published by PR #570: 308 claude-code logs scanned, the 288 trials plus 20 smoke logs of a spare task, 0 Agent or Task
tool calls, 0 subagent directories) shows that none of the
trials spawned a subagent, so per-subagent attribution through Harbor is untested; the pilot forces subagent use and
confirms that each trial's saved session directory carries per-subagent transcripts, after which the merged Gate A
kernel serves as analysis code over those directories (analysis, not a runner). The pilot passes when, for at least
one trial that used a subagent, the saved session tree holds per-subagent transcripts and the dispatch-to-worker join (Agent tool_use ids,
the returned agent id, the child file names, the forwarded parent_tool_use_id where present, task lifecycle ids)
attributes each subagent tool call; otherwise the owner reports it and the fallback routes
(Inspect, or native OpenTelemetry) are compared before any preregistration. A source-cited feasibility read on the
pool (2026-10-01, verdict feasible with a pilot: Harbor v0.23.0 at 1e5c5c6d keeps the whole agent log tree including
subagent directories, trial.py:572-614, claude_code.py:1836 and 1058-1062; its trajectory.json is a derived view, so the
analysis reads the saved session tree; the Inspect fallback attributes subagents by prompt matching; native OTel needs
explicit settings on the Claude side while Codex 0.159.3 tool results carry agent and conversation ids) proposes an
eight-trial pilot (two SWE-bench tasks, two arms, two repetitions, the same client in both arms, two named workers
through project agents and a delegation rule, `harbor run --config`, one trial at a time, no retries) accepted only if
every trial launches both workers, keeps the child transcripts, attributes distinct per-worker canaries and reconciles
tokens and cost; the Gate A owner's record of that read is cited when it is published; the eight merged Gate A packages stay in main as
analysis tooling and the seven unfinished ones stay paused. The alternatives are A (run the custom toolchain on the new distro under a user-recorded exception to the rule) and
N (drop the adoption E2E and rely on the Harbor result); no path requires a revert on the current distro. Nothing is settled until the user answers; the install manifest therefore carries
the harness's needs under R (Harbor: rootless Docker, the egress allowlist, a native Claude OAuth token) and the Gate
A toolchain's needs only if A is chosen.

### Amendment 4 as the re-aim amendment (the Gate A owner's plan, 2026-10-01 ~03:45Z)

Amendment 4 stays the append-only dated vehicle; nothing in the sealed Amendment 3 files is edited. It is written
after the install manifest is final and (a) supersedes Amendment 3's host clauses with the new distro's baseline
(pinned clients and tool set captured at install, frozen rows re-captured there); (b) supersedes the custom runner and
kernel clauses with an upstream harness (Harbor, Inspect as fallback) unless the user records an exception for the
custom toolchain; (c) keeps the sealed question, tasks, metrics, gates and arms as the inputs ported into the harness's
task format unless it lists a change; (d) re-qualifies the Codex arms on the new runtime (Codex 0.159.3 with the
Sol/Astra routing; the SDK qualification so far covers 0.159.2 only). The Codex arms' route is decided in Amendment 4
before the announcement: either the native login, in which case the Codex window opens only if, at the preflight, the
native used percent plus 1.5 times the estimated cost is at most 90 percent, or the OmniRoute pool with the Sol/Astra
routing under the pool's launch rule (a live read first, at most 75 percent used before a run); the amendment records
the route and the preflight reading, and a change of route between arms or windows is a protocol deviation; (e) states the new host's freeze and window
rules. The current distro's Gate A freeze is lifted. Timing: after the WSL recipe and the winner manifest, the clean
install with its baseline capture, the harness task port and preregistration, a pilot, then an announcement with at
least six hours' notice: days, not hours.

Install needs for the manifest: under R, Harbor v0.23.0 (pinned), rootless Docker with the 65,536 subordinate ids of
stage 1 (see "Subordinate ids"), the egress allowlist, a Node v22.23.3 tarball pre-step for the arms, and the user's
Claude OAuth token for the harness. That token is a separate long-lived credential that the user mints with
`claude setup-token`; the native sign-in (`claude-native` in `adoption/credential-inventory.json`, a `native_store`
entry) is never read or copied. The inventory has no entry for the minted token yet, so the credential runner cannot
provision it: K4 (#567) adds the `claude-oauth-token` entry, after which `set_credential.py` writes its 0600 provider
file, the store of record, and the kernel keyring stays the transport and per-boot spare. On the current workstation
the token is held only in the keyring today. Until that entry is on main this is a stated gap of path R, not an
install requirement the repository can meet. Under A only: Node 22.13 or later, Python 3.12 or 3.13 standard library,
the pinned shell parser (`examples/claude-native/workflows/shell-parser.pin.json`), rtk, qmd and both clients on PATH;
the toolchain opens no ports and runs no service.

Subordinate ids. Docker's rootless prerequisites ask for at least 65,536 subordinate uids and gids
(https://docs.docker.com/engine/security/rootless/#prerequisites), and that is the recipe's stage-1 value. Its
troubleshooting page says the pull error `lchown <FILE>: invalid argument` "occurs when the number of available
entries in `/etc/subuid` or `/etc/subgid` is not sufficient. The number of entries required vary across images.
However, 65,536 entries are sufficient for most images"
(https://docs.docker.com/engine/security/rootless/troubleshoot/, fetched 2026-10-01). The current workstation has run
with 262,144 since the 2026-09-29 Harbor run: the images of six matplotlib SWE-bench tasks logged that error at
65,536, and the four of them in the final task set ran after the widening. The Gate A owner published the observation
on 2026-10-01 in
`evidence/receipts/harbor-e2e-token-tools-20260930.json` (block
`host_prerequisite_observations.rootless_docker_subordinate_ids`), published by PR #570.
It is the workstation's value for one image set, not a default. On the new distro the range is widened only when
that error appears, by the harness unit's owner (Gate A), who records the image, the error and the range chosen. An
earlier text of this record stated 262,144 as a requirement; the independent review's third finding removed it.

### Timing estimate on the recipe basis (the Gate A owner, 2026-10-01 ~04:45Z; an estimate, not a commitment)

Critical path on the new distro: stage 1 (the PowerShell steps and the first boot, about an hour, run by the user), the
two interactive sign-ins, stage 2 (the full-profile bootstrap, one to three hours), a clean baseline capture and the
Harbor pilot (about half a day; a wider subordinate id range only if an image needs it), the re-aim
amendment or preregistration with its review (half a day to a day, overlapping), then the announcement with at least
six hours' notice. Task porting is the swing factor: the sealed 60-task table ported into harness tasks with oracle
checks is a day or more; a lighter first E2E on the 36 oracle-verified Harbor tasks with a subagent-forcing arm is about
half a day. If stage 1 starts on the morning of 2026-10-02 UTC, the earliest announcement is the morning of 10-03 and
the first window the evening of 10-03 to 10-04, with results by 10-06; the sealed port adds a day. All of it waits for
the user's answer on the harness (R, A or N) and is shaped by the Claude window and the Codex arms' route. Levers:
the user runs stage 1 and both sign-ins as soon as the recipe is readable; the lighter first E2E; the Codex arms on
the gateway. Recipe notes: the new distro's host file stays free of the current distro's ports, and a window needs a
load check on the shared WSL virtual machine, not only on the distro.

### Earlier option text (superseded)

The Gate A owner paused its builders and recommended re-aiming the token-adoption E2E (#381) at the new distro after
the clean install, since a new host collects its own evidence and the measurement toolchain is reusable. If the user
agrees, the current distro's drift revert is no longer required for Gate A's sake and the new distro's build no longer
waits for a window on the current distro; the windows then run on the new distro after its layers are installed.

The token-efficiency layer is marked provisional until that E2E runs: what exists is the Harbor E2E of 2026-09-29 (288 trials of
short single-session tasks: context-mode x1.34, jcodemunch x1.39, the full stack x1.30 against the base arm; headroom,
rtk and serena inconclusive; MCP use 0 of 36 trials for context-mode and 1 of 36 for the full stack; receipt
`evidence/receipts/harbor-e2e-token-tools-20260930.json`, PR #570) and the accepted
14-component profile of #540 (`docs/decisions/2026-09-30-task-model-routing.md`) with jCodeMunch, codebase-memory-mcp
and ast-grep as task-appended lanes.

## Independent review of this record (2026-10-01)

The Codex catalog lane commissioned an independent source review of this record and of the new-distro recipe (a
Claude Opus researcher at effort max). Its findings were relayed to the coordinator at 07:46Z, and the review's own
output is not in this repository, so they are recorded as relayed, each with the check made here.

| Finding | Check made here | Resolution |
| --- | --- | --- |
| The selection and install cycle: the 13 `comparison_required` layers and the `new_host_required` layer cannot pass a host comparison before they are installed | A defect of the staged rule as first written | Decision 3 of "Program decisions on the criterion" |
| The Hindsight stale and paused pages, its held cold seed and AgentRelay's held automatic Codex PTY submission belong in the manifest rows; a new distro fixes neither a provider-route timeout nor an adapter's semantics | The Codex lane's own host observations; its receipts are not published yet | Gates on the durable-memory row and the cross rows of the install manifest, cited once the receipts are on that lane's branch |
| The record required 262,144 subordinate ids while the recipe proves 65,536 | Docker's two pages, fetched 2026-10-01, and the Harbor receipt published by PR #570 | "Subordinate ids"; the requirement is withdrawn |

The same lane took the second independent review of item 4 for all 32 layers (unit U6), the crosswalk from the
guide's ten themes to the 32 layers, and sanitized receipts for what it qualified on the current host. Its first
packet is pull request #575 at `bbee2a8e`: gpt-6.1-sol reviewed the 20 foundation layers on 2026-10-01, with 26
corrections to the layer records and remaining gaps in every layer. A performed review that names gaps does not
satisfy item 4, so the item-4 cells of the foundation table keep the assessment's reading until the re-record pass.

A second reviewer (the repository's evidence-reviewer role, Claude Opus 5.5 at effort max, so the same model family
as the assessors) read the sections added on 2026-10-01 against the artifact and the cited sources. It found no high
finding, 5 medium and 12 low. The 200 cells of the foundation table from "Layer" to "Pin is latest" matched the
artifact and the two catalog files, and the counts of the result paragraph were recomputed. All 17 findings are
repaired in this text: the provisional status of the stage-2 bootstrap, what the two saturation sources do and do
not say, five unpinned winners instead of three, the workers baseline arm, the receipt citation for the subordinate
ids, and twelve smaller corrections. Three counts rest on the synthesis alone and were not recomputed: the 16 layers
of the profile-coverage pattern, the seven practice layers, and the 14 layers whose verdict pin differs from the
installed pin (the reviewer reproduces that one as 12 version mismatches plus 2 unpinned winners). A cross-family
read of this record is queued for the gateway pool's next reset.

## Open decisions for the user

- The harness for the re-aimed Gate A E2E: R (recommended), A or N ("Harness for the re-aimed E2E").
- The meaning of "frozen" in item 2 (decision 2; the default applies until answered).
- Running stage 1 of the new distro and the two native sign-ins (the recipe of PR #569).
- Whether stage 2 may run on the new distro before the layers are final (decision 3; the default is yes, as a
  provisional install).
- The live ai-memory store's isolation breach of 2026-09-23 on the current workstation: whether to rewrite or collect
  the live wiki history and to compact the database again
  (`evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/README.md:20-48`). The new distro starts with a
  fresh store.
- Routing the default-home Codex terminals through the gateway while the native weekly allowance matters for the
  Codex arms.

## Overturn

This program record is superseded if the user moves the Gate A measurement back to the current distro, if the WSL
recipe research shows that a new distro cannot be built without a host WSL package change that the keys lane has not
qualified, or if the pilot shows that neither Harbor's saved logs nor native OpenTelemetry carry per-subagent tool
calls. Decision 1 is overturned layer by layer by the re-record pass's result for each of the six layers.
Decisions 2, 3 and 4 state their overturn conditions where they are made.
