# U11: merit-neutral selection rules (design for review, 2026-10-01)

Status: proposed, revision 5 (2026-10-01): revision 4 plus the amendments in "Revision 5" below. Revision 4 was the
repair round over the two reviews of revision 1, the wording repair after the
second reads of revision 2, and the last qualifier and clarifications after the delta-reads of revision 3 (see Review
history).
Revisions 1 to 4 implemented nothing. Revision 5's item 1 records a round that has already run (the decision round of
2026-10-01); it changed no sweep prompt, verdict or acceptance record. Its other items are policy for the
implementing parts. Owner of the files
and of the implementing pull requests: the foundation lane's coordinator (session `sota-default-harness-setup`).

## Why

The user's rule of 2026-10-01 (decision 5 of `docs/decisions/2026-10-01-definitive-sota-wsl-program.md`) says a
layer's winner on the new distribution is what the repositories' own quality supports, and that the source host's pins,
installed state and integration holds are not evidence for or against a repository. The user then asked twice why the
architecture still showed a biased list. These rules in this repository's tooling give the selection of record an
advantage that the repositories' quality does not:

1. **Discovery is written relative to the winners.** The discovery task asks for candidates that "could beat, replace
   or usefully complement this layer's winners", caps a layer at six proposals, and requires a `demonstrated_gap` ("the
   specific requirement gap versus the current winners") and a `comparison_that_would_overturn` for each
   (`tools/sota-convergence/landscape-sweep/templates.json`, `discover`; `landscape-sweep/schemas/discover.json`).
2. **The fit refuter is relative to the winners and refutes when in doubt.** It refutes a proposal with "no concrete,
   evidence-backed gap versus the current winners for THIS requirement (a plausible advantage in measured quality,
   SOTA-ness, maintenance or fit counts; incumbency does not count for the winner)". The bar is a plausible advantage,
   not a proven one, but it is measured against the winners. It also refutes a proposal that "duplicates a winner or an
   already-known alternative without new evidence" and one that "requires a paid SaaS or new credentials without a gap
   that justifies it", and it says "Default to refuted=true when uncertain". The facts refuter has the same default for
   a material claim it cannot verify inside its budget.
3. **Aggregation and absence count against the challenger.** Either family refuting refutes (`convert.py`, `FIT_RULE`);
   a missing or malformed vote refutes (`convert.py`, `is_refuted`); every proposal is projected onto survived or
   refuted; and the saturation ledger has no state for an unresolved candidate (`scripts/saturation_ledger.py`). The
   ledger's own vote records: in the 2026-09-26 and 2026-09-29 sweeps 352 of 382 refutations came from the fit refuter
   alone, 42 of them only because a vote was missing; the 352 rows cover 321 distinct layer and repository keys.
4. **Entry is not symmetric.** The selection of record enters every later step without a vote; a newcomer must clear
   all of the above. A proposal the sweep refuted never reaches a verdict packet. Verdict packets do list manifest
   newcomers and keep-but-compare entries (`lane_packets.py`, `manifest_layer_candidates`), but those can never win.
5. **Verdicts crown adopted candidates and accept weak evidence.** A winner key must be an adopted candidate
   (`lane_packets.py` `build_candidate`, a disposition of `selected` or `conditional`; `record_verdicts.py`
   `validate_lane_return`; `scripts/landscape.py` `lane_winner_components`); the lane prompt's rules 1 to 4 read the
   evidence of adopted candidates and choose among them (`tools/sota-convergence/lane-prompt.md`); a winner may rest on
   `source_review`, `synthetic` or `local_integration` (`scripts/landscape.py`, `WINNER_EVIDENCE_CLASSES`); and the
   `challenger_preferred` label exists only for non-adopted candidates. A lane return has no "undetermined" form,
   although `verdict_status` already allows `no_selection`.
6. **Evidence and prose lean to the incumbent.** Native runs exist mostly for what the source host installed, and its
   receipts and records name its selection; v1 measures the leak as `prose_exposed` (`scripts/landscape.py`).
7. **Which layers get a comparison follows the same shape.** The layer statuses are maintained by hand
   (`scripts/landscape.py` checks only the value set). In `catalogs/landscape/research-state.json` the `next_action`
   texts of six `on_requirement_change` layers (native-clients, web-research, ci-supply-chain, agent-sdks, mcp-surfaces,
   secrets-credentials) say to compare only against a concrete gap or need, the same shape as the v1 fit bar; isolation,
   code-navigation and semantic-rag call for a comparison unconditionally.

## Design

**A. One field per layer.**
- One frozen set and one hash, used by units U4, U5, U6 and U11 alike: the eligible field. Members: every candidate on
  record (the selection of record, the verdict selections, the alternatives, the catalog candidates, the second-family
  review's selections, the seeds) and every proposal any repository sweep returned, survived or refuted. A proposal
  refuted under the v1 rules enters as `pending` unless it is re-voted under B; "refuted under v1" is not an exclusion.
- The exclusion list is closed and applies to every member, the selection of record included, and is deterministic
  where it can be: (i) archived, or stale under the maintenance rule, decided by script from the API fact; (ii) cannot
  run on the target hosts; (iii) outside the frozen requirement; (iv) cannot meet the requirement without a paid
  service; (v) the same repository as another member, kept once. Each exclusion records which criterion and the fact.
- One screen for every member: the same facts check (identity, maintenance, platform). A claim that cannot be verified
  inside the budget makes the member `pending`, never excluded. Adoption is a recorded fact about the source host and
  decides nothing.
- Discovery keeps its novelty purpose and changes its contract. The task and schema ask for admission against the frozen
  requirement: `requirement_fit` (how the candidate meets the requirement, with evidence) replaces `demonstrated_gap`,
  `frozen_tasks` (which frozen tasks would measure it) replaces `comparison_that_would_overturn`, and the labels become
  `admit`, `admit_pending` and `not_admitted` with a closed reason. A `not_admitted` label does not exclude: the
  discoverer sees the winners, so such a member enters the field as `pending` and takes the same screen as every other.
  The six-proposal cap stays a discovery budget, not an eligibility limit. Credentials or a paid service are recorded as a cost and feasibility fact. The `known_repositories`
  filter stays for novelty only, because every known candidate is already in the field.

**B. The screens, version 2, and `pending` end to end.** New template versions; the current templates and their pinned
hashes stay for every sweep already started (`tests/test_landscape_sweep_harness.py` pins both).
- The fit refuter reads a blind input projection: the candidates and the requirement, without the winners, their pins,
  the alternatives' dispositions or any adopted flag. Discovery keeps the winners for its winner-health notes.
  (`build_inputs.py` copies `winners` and `alternatives` with `disposition` into every input today.)
- Votes: `credible`, `not_credible` with a criterion from A's closed list and the fact, or `pending`. A missing,
  unavailable or malformed vote is `pending`. The duplicate rule becomes A's repository-identity dedupe; the paid rule
  becomes A's criterion (iv).
- Aggregation, named: for A's criteria (ii) to (iv) a member is excluded only when both families vote `not_credible` on
  the same criterion and the facts support it; otherwise it stays, `credible` when both say so and `pending` in every
  other case. Criteria (i) and (v) are decided by script.
- `pending` survives every stage with the member's identity and reason: the vote file, the converter (which stops the
  binary projection), the frozen field and the saturation ledger, which gains a pending predicate. A pending material
  member is not clean: the layer's clean-sweep count does not advance, and merit cannot close, until the member is
  resolved by evidence or excluded under A.
- The proposals the v1 sweeps refuted are re-voted under these rules in a neutral seeded order over layer and repository
  keys, never ordered by doubt about the incumbent, until the re-vote's budget ends; members past that cutoff stay
  `pending`, and their layers carry D's provisional install, not a merit result.

**C. Verdict lane contract, version 2.** A new contract version; the sealed 2026-09-22 wave and its rules stay.
- Eligible winner keys are the field's members. `adopted` is sealed in the packet-keys document like the other
  `SEALED_CANDIDATE_FIELDS`, not left as a packet field.
- The lane prompt reads the evidence of every field member, writes one status line per member, and has no adopted-only
  clause; `challenger_preferred` is retired, since `open_gaps` already carries the deciding comparison.
- Blinding is partial, and the record labels it accurately. Packet labels are sealed; the judges read a blind evidence
  bundle built like the blind checkout (`tools/sota-convergence/blind_checkout.py`), with neutral candidate labels and
  selection-bearing prose reduced as `lane_packets.py` already reduces packet prose, and every candidate gets the same
  bundle types and reading budget. The incumbent's records still name it, and `prose_exposed` still measures that.
- Where a model judgment affects a deciding score or the selection, adoption information is withheld along that whole
  path: its inputs, the prose it can open and its aggregation. An exposure is material when `prose_exposed` is true for
  any file of the judges' bundle after reduction; a material exposure that cannot be resolved leaves the layer's merit
  `undetermined`. An objective fixed oracle, a frozen task set scored by tests or exact checks, can support
  a selection independently of exposed narrative, and the record states which deciding evidence came from an oracle
  and which from judgments. Consistency is not accuracy: judges who saw the incumbent's records and prefer it in every
  order and family are still biased (Zheng et al. 2023, section 3.4: high consistency may not imply high accuracy).
- One evidence bar, enforced by the validators: a v2 winner needs `winner_evidence_class` `measured_comparison` and refs
  that resolve to a registered receipt covering that winner and the field's hash. The receipt cites the hash of the
  comparison's preregistration, which predates its first trial, and the validator recomputes the preregistered decision
  rule's outcome from the receipt's per-arm results: the lane's winner must equal that outcome, otherwise the layer is
  `undetermined`. A member that was compared and lost gets a `why_not_default` that cites the receipt; a member that was
  not compared is listed `undetermined` with the deciding comparison and gets none. Without such a receipt the lane
  returns `undetermined`, recorded as `verdict_status` `no_selection` with `open_gaps` naming the comparison.
- Order: each lane gets its own candidate-order seed, and a winner that depends on the order is recorded
  `undetermined`. Pairwise judgments run in both orders and count a win only when the same candidate is preferred in both,
  otherwise a tie (Zheng et al. 2023, section 3.4); scored judgments average both orders (Wang et al. 2023, section 3.2);
  judgments vote by a function declared in the preregistration, max voting (the majority label) for binary judgments and
  average pooling for scores (Verga et al. 2024, section 3.1, where the panel spans three model families). The tooling
  routes two families today (Claude and Codex), so each family gives two judgments under different seeds, and a result
  stands only when both families' own majorities agree, as B requires for exclusions; otherwise it is `undetermined`.
  When a third family has a route, the record names it. A missing judgment is pending. These controls apply to every model judgment in this design, including D's.
- The selection of record carries no precedence in selection, ties or arm order. What installs before a comparison is
  set in D.

**D. The comparisons that decide (program unit U5).**
- Frozen before any run, with the field's hash: the tasks, the oracle, the resource budget, the quality criteria, the
  same retry budget for every arm, and the decision rule: the effect that matters, the tie-break and what a tie installs
  (a preregistered cost or footprint tie-break, both arms behind a selector, or no selection). The choice among those is
  the owners' and the user's; a silent default to the incumbent is not an option.
- The arm set is a preregistered function of a closed list of inputs: the field's members and their requirement-fit
  evidence, the budget and a seed; adoption, installed state and receipt counts are not among them. The same blind
  screen produces the requirement-fit evidence for every member, known members included, before the function runs, so
  no member enters with evidence that only its history gave it. The decision rule's effect threshold applies to every
  pair of arms, and no pair names the selection of record as the reference. For example, a cheap
  screen on a shared task subset, then the full comparison on the members that pass it. A member that fails the screen
  is `undetermined`, not compared-and-lost, unless the screen itself meets the decision rule's power. Members that are
  not run are `undetermined`, never excluded. A comparison decides only among the arms it ran and records a disposition
  for every other member.
- Closure: a member is material when A does not exclude it and it is `credible` or `pending`. A layer's closure record
  lists every material member that was not compared, with its reason (the arm cap, pending), and states that the layer's
  merit is decided only among the compared arms.
- Run order and time windows are counterbalanced across arms. No arm gets the source host's wiring beyond the
  upstream-documented integration, or every arm gets the same.
- What installs on the new distribution, in this order:
  - A layer that needs a comparison installs one default: the pick of the blind decision round (revision 5, item 1;
    program decision 6). Its arms run beforehand, on the current workstation or on a rehearsal distribution, each
    installed fresh and isolated. No arm is installed on the new distribution, and the source host's recorded
    selection has no precedence in the round. (Revision 4 read: arms install on the new distribution with no default
    precedence.)
  - Every other layer, and a layer past the re-vote cutoff, installs the blind first round's pick as its default
    (program decision 6), labeled as not a merit result, with its pending set recorded and a reopening trigger: a
    `credible` challenger after the re-vote moves it to `comparison_required` (F). The source host's selection of
    record is not what installs; it is one member of the field. (Revision 4 read: installs its selection of record
    provisionally.)
  - A no-selection outcome, a split between the families and a slot the user hands to a measurement all install
    nothing: the layer's function is left to the clients' built-in tools until the measurement returns. (Revision 4
    also allowed both arms behind a selector.)
- Tasks come from the layer's real workload. A named external benchmark is allowed with a recorded reason; unless that
  reason shows it represents the workload, its run is a pilot, not the deciding comparison.
- Each arm runs fresh at its current release, installed by its upstream commands, on the current workstation or on a
  rehearsal distribution of the target host, never on the clean install (program decision 6, which amends decision
  5); the recorded incumbent has no precedence among the arms. Partial native evidence counts
  only for the operation it observed (`docs/acceptance-evidence-policy.md`, the claim boundary of each class); it neither
  disqualifies a member that lacks it nor replaces the comparison.
- Uncertainty: paired differences on the shared tasks, clustered standard errors where tasks share a source, and a power
  estimate for the effect in the decision rule (Anthropic, "A statistical approach to model evaluations"). An underpowered
  or indecisive run is `undetermined`. Failures are kept with their usage. Inspect's eval sets are cited for the retry and
  reuse pattern only; the runner is the user's choice in the Gate A harness question.

**E. Inputs and pinned requirements.** A sweep or verdict input carries the field. `catalogs/us-equities/runtime-target.json`
`next_acceptance` is split: the gate, what any candidate must show, goes to every member; the incumbent's executed status
and evidence refs stay sealed. A requirement text that names a candidate is reduced in sweep inputs as `lane_packets.py`
(`reduce_prose`) already reduces verdict-packet prose, or rewritten as capabilities; a name that is a user pin or a fixture
(LEAN as the parity oracle) is recorded as that. Four trading layers name NautilusTrader and LEAN in their requirement
(research-factors-ml, backtesting-engine, execution-broker, portfolio-risk); by a name or repository-slug match, none of
the twenty foundation layers names a candidate. The trading lane owner's answer on the pinned destination, sent to this
record's owner by cross-session message at about 17:35Z on 2026-10-01, verbatim:

> The destination is a requirement of its layer, not a selection that a comparison can change. The user selected
> NautilusTrader with the IBKR destination and a separate Alpaca adapter path (AGENTS.md, north star;
> catalogs/us-equities/runtime-target.json engine.decision selected_destination). The north star also says that dated LEAN
> and Alpaca receipts remain comparison evidence rather than overriding that destination. So no tooling pass may override
> it. A comparison that favours another engine is reported to the user as a decision, with its evidence, and only the user
> changes the destination. The comparisons still run under the merit rule of 2026-10-01: the destination's comparative
> merit is undetermined until they do, and they inform the user's choice without overriding it. Two parts stay
> selections. First, the release pin: 2.0.0rc5 is the pin of record, and a newer NautilusTrader release replaces it only
> through a dated version-selection record after its own qualification (unchanged upstream tests, then the acceptance
> plan's steps). Second, every component around the destination (data, storage, research, risk, evaluation,
> observability) follows the merit rule like any other selection.

The rule this design takes from it: a requirement the user pinned stays out of every tooling decision; comparisons that
involve it still run, and a result that favours another candidate is reported to the user as a decision. This carve-out
rests on the trading lane owner's reading of AGENTS.md; decision 5 does not mention the pin. Overturn: the user says the
merit rule governs the pinned destination too.

**F. Re-triage.** After the field, the version 2 screens and the re-vote, the layers are triaged again: a layer with a
`credible` challenger in its field becomes `comparison_required`. This is a landing condition of the implementation.

**G. Sequence.** Field construction, the version 2 screens and the re-vote do not wait for any comparison. The verdict
lane version 2 has nothing to crown before the first U5 receipt and lands after it.

**H. The Gate A arms.** Amendment 4's sealed arms (Claude B, A, A0 and Codex B, A, N) measure wiring, which role
dispatch the carrier uses; they are not repository candidates and the field rules do not apply to them. The
token-efficiency layer's merit question uses the field and D: the lean base as the control, arms drawn from the field
within the budget, then one confirmatory run of the selected set. The Gate A owner rebases Amendment 4 on that after the
user's answer on the harness.

## Files the implementations touch (after review)

Screens and field: `tools/sota-convergence/landscape-sweep/templates.json` (discover, common, fit and facts),
`landscape-sweep/schemas/discover.json` and the vote schemas, `convert.py`, `scripts/saturation_ledger.py`,
`build_inputs.py` (the field, the blind fit projection, the acceptance gate), `tests/test_landscape_sweep_harness.py`
(new pinned hashes). Verdicts: `tools/sota-convergence/lane_packets.py` (seal `adopted`, per-lane seeds),
`tools/sota-convergence/lane-prompt.md`, `tools/sota-convergence/record_verdicts.py`, `scripts/landscape.py`
(`WINNER_EVIDENCE_CLASSES` for version 2), `tools/sota-convergence/blind_checkout.py`, the lane contract in
`tools/sota-convergence/README.md`, and their tests. Receipts: a comparison receipt schema with per-arm results and the
preregistration's hash and time, checked by `scripts/validate.py` (`RECEIPT_KINDS`), `scripts/validate_catalogs.py` and
`scripts/validate_foundation.py`, with failing tests first: a receipt whose preregistration postdates its first trial, or
whose per-arm results contradict the lane's winner, is rejected. Each lands with failing tests first, the Gate A owner's
script check and the trading lane owner's acknowledgement, because the tooling covers the trading rows.

## What stays untouched

The active workflow `wf_85f3021d-b4d` and its frozen inputs; the sealed 2026-09-22 verdict wave; the pinned prompt
hashes of sweeps already started; every acceptance contract and receipt. No candidate wins or loses by this record.

## Review history

- Revision 1: `def6989c4c75e272f0a9364d08058877412430f4`, design sha256
  `2ed54b5a1f06613b55baa604f5f0be27a75f1a97fcff255c2d75ae26e406195e`.
- Cross-family review (the Codex catalog lane, gpt-6.1 Astra at max, 2026-10-01): repair required. Discovery still
  demanded winner-relative gaps before a neutral judge saw a candidate (now A and B); `pending` did not survive the
  converter and the ledger (now B); blinding covered packet fields but not the prose judges open, and aggregation across
  orders, disagreement and missing judgments was not frozen (now C); a comparison was not bound to the full field and
  decision 5 was not carried (now D). Sound as written: full-field eligibility, the single evidence bar, `no_selection`
  without a comparison, and the immutability of history.
- Claude review (the Gate A owner, 2026-10-01): not yet. The field inherited v1 fit refutations (now A); two v1 fit
  grounds stayed winner-relative (now A and B); entry was not symmetric and the aggregation was not named (now A and B);
  the fit refuter still saw the incumbent (now B); the evidence bar was not enforced by the validators (now C); the lane
  prompt, the order, ties, the install default, the layer triage and `next_acceptance` needed rules (now C to F); the Gate
  A arms are wiring arms (now H). It also corrected this record's Why: v1 fit's bar is a plausible advantage, not a proven
  gap, and verdict packets do list non-adopted candidates; the gap is that sweep-refuted proposals never reach them.

- Second reads of revision 2 (`51e6fcfbb1cb5f0d27c066c85e8f4f1279ff4b22`, sha256
  `7a5f5371c219a5389552aade004a1074f826b8840ea76cbb941a01ebb85ef4b8`). The Codex catalog lane: scope pass on neutral
  discovery, pending and the full field; one material blinding repair, now in C (no unconditional claim that the
  evidence bar makes a leak harmless; the winner must satisfy the preregistered decision rule; adoption withheld along any
  judgment path that affects a deciding score; oracle and judgment evidence labelled apart; consistency is not
  accuracy); it verified 352 fit-only rows over 321 distinct keys (now in Why 3). The Gate A owner: revision 2 closes the
  revision 1 boundaries; four paths remained (the validator recomputes the decision rule, now C; the provisional install
  for layers with pending members, now C and D; requirement texts that name a candidate, now E; three judgments from two
  routed families, now C) with residual rules (now A, B, C and D) and two corrections (Why 3 and Why 7). The trading lane
  owner answered E's question (now quoted in E). Revision 3 was the wording repair.
- Delta-reads of revision 3 (`2440cf8f08770942a38a03c3281934ab02279472`, sha256
  `1cd4da1f90f093ce3ea32dae0f03f3d8f986cfad9780bc01bcbaa7627470efa0`). The Codex catalog lane: C's blinding, R1, R3, R4, the
  trading requirement and the earlier bounds pass; one qualifier repaired in D: before a comparison, an incumbent install
  on a comparison layer is an isolated arm with no default precedence, as decision 5 requires. The Gate A owner: no new
  path where adoption decides eligibility, burden, order or a tie; six clarifications applied (the receipt schema in the
  files list, D's install order, two judgments per family with agreeing majorities, the same blind screen for every
  member's requirement-fit evidence and no reference pair, E's carve-out overturn and the answer's source, the exposure
  measure and Why 7's six layers). This is revision 4.

## Review question

Do these repairs close the boundaries both reviews named? Name any remaining path where adoption status changes
eligibility, the burden of proof, the order of judgment or a tie, and any rule that would let a merit claim stand
without an executed comparison.

## Sources

- The user's rule: decision 5 of `docs/decisions/2026-10-01-definitive-sota-wsl-program.md`.
- Zheng et al. 2023, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", arXiv:2306.05685v4, section 3.4:
  swap the two answers, declare a win only when one is preferred in both orders, otherwise a tie.
- Wang et al. 2023, "Large Language Models are not Fair Evaluators", arXiv:2305.17926v2, section 3.2: balanced position
  calibration, the final score is the average over both orders.
- Verga et al. 2024, "Replacing Judges with Juries", arXiv:2404.18796v2, section 3.1: three judges from disjoint model
  families; max voting for binary judgments, average pooling for scores. The voting function is a design choice.
- OpenAI, "Evaluation best practices", https://developers.openai.com/api/docs/guides/evaluation-best-practices: position
  and verbosity bias, pairwise comparison, the "biased design" anti-pattern.
- Anthropic, "A statistical approach to model evaluations" (2024-11-19),
  https://www.anthropic.com/research/statistical-approach-to-model-evals, and arXiv:2411.00640: clustered standard
  errors, paired differences, power analysis.
- Inspect, `docs/eval-sets.qmd` at commit 0321960a92aa52390413ce011d67ffb5962a2b11: retries and reuse across an
  evaluation set.
- This repository: `docs/convergence-architecture.md`, `docs/acceptance-evidence-policy.md`, and the tooling files named
  above, read at `a2c22b26`.
- Every external source was read on 2026-10-01 before it was cited. The Codex catalog lane's root named the OpenAI,
  Anthropic and Inspect sources and the paper sections; the Gate A owner's review named the tooling anchors and the
  ledger counts.

## Revision 5 (2026-10-01)

Two things prompted it: the user's directive for one default per slot (program decision 6), and the Gate A owner's review
of the first implementing pull request (part 1). Each item is frozen policy for the implementing parts.

1. **One default per slot.** Where the first blind round leaves several finalists, or the ownership map leaves two
   tools for one job, a decision round names exactly one
   default: per slot and per model family, two deciders with the finalists in different seeded orders, then one
   adversarial critic. A default is definitive when both deciders of both families name it and both critics return
   converged; a split is settled by the measurement the critics name, and until it returns nothing is installed for the
   slot. Measured against measured, the evidence bar is the same in both directions (C). A default decided on documented
   fit did not have to show a measured gain, while a challenger replaces it only with one (an interval that excludes
   zero, plus the slot's gates): the bar to replace such a default is higher than the one it faced, and its row says
   that it rests on documented fit. An option that installs nothing extra is the default unless a challenger shows a
   gain on the requirement's own metric with an interval that excludes zero; this rule was stated before the round.
   Where a documented-fit default is also the source host's selection of record, the asymmetry may not protect it:
   its replacement is decided by a symmetric measurement (identical gates, the higher primary score on an interval,
   measured secondaries in an order fixed before the data), and the blind round's pick decides only a tie that the
   measurement leaves. Judges of later rounds run outside the project's agent environment, whose instructions and
   tool lists name the source host's tools. A definitive default is an install decision. It does not meet C's bar
   for a merit winner and is never recorded as one.
2. **Equal facts for every member.** The blind fit input takes each member's upstream facts from one deterministic API
   pull, the same pull the maintenance screen uses, never from whichever record names the member. Stars and license are
   not in the blind input. (Measured on part 1: facts were populated for 74%, 30% and 81% of the foundation's adopted,
   catalog and sweep-only members.)
3. **Criterion (i), archived or stale,** is decided by script from the API fact for every member. Until that screen
   exists no V2 run launches, and the implementing part says so.
4. **Criterion (iv), paid service.** Each layer carries `paid_service_allowed`, set by the layer's owner, false by
   default and bound into the frozen scope hash; a later change makes a new frozen field. Where it is false, a member
   that cannot meet the requirement without a paid service is excluded with the fact. Where it is true, the member stays
   and carries a user purchase gate. Until the field exists, a `paid_service_required` vote never excludes and is
   recorded pending.
5. **Which role may exclude on what.** The facts role may exclude only on the target-host and paid-service criteria. An
   outside-the-requirement exclusion stands only when the fit role returns it, or when both roles agree. Every exclusion
   needs both families' majorities within one role, with the criterion and the fact recorded.
6. **A proposal the tooling cannot identify** (a repository outside the supported hosts, a documentation page, a null or
   malformed identity) stays pending with its raw return and a failure record. It never aborts the conversion of the
   other layers.
7. **Acceptance summaries.** Where the tooling restates a plan's acceptance requirement, a test pins the sha256 of the
   plan section it summarizes, and the owning lane confirms the text.

## Overturn

A review finds a rule that still gives adoption an advantage, or one that lets a merit claim stand without an executed
comparison; or a comparison shows that a rule here selects worse than the current one on the same frozen tasks.
