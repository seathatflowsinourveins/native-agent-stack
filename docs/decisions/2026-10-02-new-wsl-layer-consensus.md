# The new WSL's layers after a direct consensus of the two model families (2026-10-02)

## Decision

Five rows are added to the definitive manifest of the new WSL distribution, and six existing rows carry an amendment.
Both come from one record of a direct consensus of the two model families,
`evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`. The manifest's assembler reads that record in a
last step, after the rounds' decisions.

A row added this way has the row kind `consensus`. It is not a result of a blind round and not a measurement, and it is
never definitive. An amendment is recorded beside its row, in a list named `amendments`, and changes no field that the
rounds decided: the default, the state, the definitive flag, the repository, the install flag and the row kind stay as
they were.

The assembler prints, for the regenerated manifest:

```
layers 37 | slots 89 {'foundation': 69, 'us-equities': 20} | definitive 31 | installed 56 | {'first_round': 53, 'added': 10, 'consensus': 5, 'judged': 11, 'pinned': 6, 'project_practice': 2, 'no_blind_default_today': 2} | {'definitive': 31, 'resolved': 22, 'measurement': 4, 'split': 7, 'open': 25} | amendments 6 on 6 rows
```

The two groups in braces are the row kinds and the states; the empty state is counted as open. These counts describe
decisions, not an installation run.

The tables of all rows, with the consensus rows and a table of the amendments, are generated into
[the definitive-defaults record](2026-10-01-new-wsl-definitive-defaults.md).

## The owner's sentence and the rule

The owner said, on 2026-10-02, shortly before 17:59:40Z (the time stamp of the request note that relays it), verbatim:

> you can reseach  consensus wit hlive codex session, we need frictionless seamless llm native workflow

The record reads it this way: the two lanes settle research results between themselves and bring the owner only what
needs a sign-in, a grant or capacity. It grants no permission, sign-in or capacity to either lane.

The rule, verbatim from the record. The assembler appends it to the manifest's `decision_rule`:

> A manifest row may be added or amended by a recorded direct consensus: one family's sourced proposal, the other family's independent primary-source review, and both acknowledgements on record. Such a row has row_kind consensus and is never definitive. Its label names the direct consensus of both families and says either that the row is neither a blind result nor a measurement or, for a row whose install waits for a gate or a comparison, that the gate or the measurement decides and that nothing is installed until it returns. Acceptance gates that an installed or resolved row still has to pass on the destination are listed as its open acceptance gates and do not hold its install. A direct consensus never replaces a blind definitive default or a measured result; where the families differ, or where the consensus itself names a comparison, the measurement decides.

The labels say it in their own words: "not a blind round, not a measurement" for a row that is resolved, and "decides ...,
nothing installed until it returns" for the two rows whose install waits; three rows carry `open_acceptance_gates`.

A resolved selection is not a native qualification, and the Codex lane's comment 5959996494 asks that the record keep
the two apart. The state `resolved` says that the source selection is settled. The native qualification on the
destination is what a resolved row's open acceptance gates still ask for, and the record counts none of those gates as
passed.

What the assembler holds the record to: each file that the record names under `records` (the three exchanged notes and
the Claude lane's review of the scoped dispositions) exists with the recorded SHA-256, at least one such file is named,
and an acknowledgement of each family is on record; a slot to add does not exist yet; an added row has the kind
`consensus`, is not definitive, uses a state, a catalog and a layer the manifest knows, carries the manifest's row
fields and no outcome of the rounds, installs nothing while it waits for a measurement and takes no job that an
installed row owns; an amendment names an existing slot, has a date, an author and a decision, and carries none of the
six fields the rounds decided. It stops with a message and a non-zero exit otherwise. The acknowledgements are links to
pull-request comments; the build checks that they are present, not what they say.

## Method

The method is the record's own account. Leads came from the research runtime on the live web (GPT Researcher 3.7.0 on
a local model); those reports are leads, not facts. The Claude lane re-read every fact it used from GitHub by script
and wrote proposals for seven layers and for the skills rows. The Codex lane decided each one independently from its
own reading of the primary sources and corrected two statements of the proposals. The acknowledgements are public
comments on pull request 608, and the record says what each one covers.

Who acknowledged what, from the comments as read again on 2026-10-03; none covers more than its words:

- Comment 5958766754, the Claude lane, 2026-10-02T18:29:20Z: its acknowledgement of the Codex lane's decisions, which
  the Codex lane's comment 5959059286 received as agreeing all seven layer decisions and the three skills capabilities.
- Comment 5959059286, the Codex lane, 2026-10-02T18:45:13Z: its acknowledgement of the seven layer decisions and the
  three skills rows, in its words "Actual Claude acknowledgement received at PR608 comment 5958766754: all seven layer
  decisions and the three skills capabilities are agreed."
- Comment 5959205007, the Codex lane, 2026-10-02T18:51:56Z: its root takes the standing freshness and notice unit;
  Updatecli 0.122.0 offers no extra closure, so no new dependency is taken; and its verdict on the research skill's
  dependency (gptr-mcp at 63884773, MIT; activation in both clients held until a pinned environment, a handshake,
  discovery and a useful result). It says that the Astra/max review of HOL Guard, AgentCompass and the Compose delta
  continues, so it is not an acknowledgement of those dispositions.
- The Codex lane's note, version of 2026-10-02T18:57:10Z (the published copy `codex-decisions.md`), writes the scoped
  dispositions: the `credential-guard` amendment and the three topics held without a row change.
- Comment 5959684384, the Claude lane, 2026-10-02T19:16:53Z: its agreement to those scoped dispositions, given from the
  note before its own review of their sources.
- Comment 5959996494, the Codex lane, 2026-10-02T19:35:35Z: "Actual acknowledgement 5959684384 received." It states that
  its Astra/max review has no immediate substantive objection to the additive consensus rule as supplied to it ("never
  definitive or measured, explicit labels, no replacement of default/state/definitive or measured results"), asks that
  a resolved selection be kept distinct from native qualification, and says that the throwaway installs remain unrun
  until their actual receipts return and that cross-family review stays a source selection with its destination task
  gate open.

The exchanged notes are published as copies in the evidence folder (`claude-proposals.md`, `claude-request.md`,
`codex-decisions.md`). `copy-notes.json` gives each copy's hash, the original's hash and every difference between
them: two paths in a private state folder and one distribution name were replaced, and one operational paragraph
without a decision was left out. A fourth record, `claude-review-held-topics.md`, is not a copy of an exchanged note:
it is the Claude lane's independent primary-source review of the claims behind the Codex lane's scoped dispositions,
written in the folder from the review as that lane returned it, with host paths replaced as the file lists at its end.

## The five added rows

Each row names its alternatives and what would overturn it. Under the rule a direct consensus never replaces a blind
definitive default or a measured result, and where it names a comparison the measurement decides. The record's own
limit applies to the two rows that install: a new row that installs something is installed and accepted only through
the install plan, and the client configuration wires it only after that.

- **`skill-discovery`** (layer `instructions-skills`, state `resolved`, installs). Default: `find-skills` from
  `vercel-labs/skills`, release `v1.7.0`, commit `7407f3893ad4dceab546ac002c3ef806e4000c73`, with
  `skills/find-skills/SKILL.md` at blob `a41bdd074bb587afd861332cf2f473f3154de4d7`. Job: finding and adding a skill from
  inside a session, in both clients. Reason: discovery, authoring and research are three distinct capabilities with
  different dependencies and activation, so each has its own row; the skills installer's own repository carries the
  discovery skill, and only that named folder is installed, never the bundle; popularity counts serve discovery only.
  Alternatives: one row for all three capabilities, which the Codex lane's review rejected, and the whole bundle, which
  is not installed. The record names no competing discovery skill and no comparison. What would overturn the row is
  one of its open acceptance gates, which do not hold its install: listing, hash and read-back of the installed folder
  on the destination, and a useful invocation in each client.
- **`skill-authoring`** (layer `instructions-skills`, state `resolved`, installs). Default: `skill-creator`, embedded in
  Codex and taken from `anthropics/skills` for Claude Code, at commit `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`, with
  `skills/skill-creator/SKILL.md` at blob `65b3a402dbd09b8e83f9d637c6b553875189085c`. Job: writing and evaluating a new
  skill, in both clients. Reason: Codex ships its own authoring skill embedded at the selected tag (the record cites
  `codex-rs/skills/src/lib.rs` of `openai/codex` at `a956835d020762cb2b570053af06f643a11c0ecc`), so nothing is installed
  for Codex and no same-name copy is placed beside it; Claude Code takes the maintained authoring folder, which carries
  its own evaluation workflow. Alternative: the same folder for both clients, which would place a same-name copy beside
  Codex's own skill. What would overturn the row is one of its open acceptance gates, which do not hold its install:
  that the embedded Codex skill is available on the destination (source availability is not target availability), listing, hash and read-back of the
  installed Claude Code folder on the destination, and a useful invocation in each client.
- **`research-skill`** (layer `instructions-skills`, state `measurement`, installs nothing). Default: not installed
  until its activation gate returns. Job: starting a research run on the research runtime from inside a session, in both
  clients. Candidate: the GPT Researcher skill, `skills/gpt-researcher/SKILL.md` of `assafelovic/gpt-researcher` at
  `0957c301ed06c2a5857b834358c7227c739041d4` (blob `828782a6ffd842634fbffc267c61207009585df0`). It drives the research
  runtime through an MCP server, `assafelovic/gptr-mcp` at `63884773685b1f12c7f0d9e283b3d71a5b9b5fda`. The record's
  notes on that server: ranges in its requirements are not pinned; a direct STDIO start prints text that is not
  protocol output; the server needs a provider key of its own and its default search needs a second credential, so a
  native client sign-in is not that readiness; its SSE tester does not prove STDIO acceptance. The skill is an entry
  point, not a convergence procedure, so the validation duties of the repository's search-first practice stay where
  they are. Alternative and comparison source: DeerFlow's deep-research skill at `v2.1.0`. What decides the install,
  verbatim: "An activation gate, not a comparison: a resolved and pinned environment for the MCP server, a native
  protocol handshake over STDIO, discovery of its five tools, a useful research result returned in each client, and a
  bounded lifecycle (start, stop, removal)."
- **`cross-family-review`** (layer `git-github-automation`, state `resolved`, nothing additional installed). Default:
  the two clients' native review commands, each family on the other's work. Job: review of a change by the other model
  family before merge. Reason: the practice becomes an explicit capability. A review binds the author and reviewer
  families, the model and effort, an immutable base and head, source-located findings, independent dispositions and a
  later verification; a local review neither implies local inference nor authorizes publication by itself. Alternative:
  PR-Agent 0.47.0, a comparison only for an identified gap; its own README describes a community-maintained legacy
  project. What would overturn the row: its open acceptance gate, the qualification of the Codex 0.160 review command
  on the destination, which the Codex lane owns; or an identified gap that the native commands leave, which calls for the
  comparison with PR-Agent.
- **`credential-custody`** (layer `secrets-credentials`, state `measurement`, installs nothing). Default: not installed
  until the deciding measurement returns; the repository's practice stays (one 0600 file per provider, pointer
  variables, the value-free status check, the id-based runner and the guard hook). Job: custody and injection of
  provider keys for agents. Reason: a local secret broker built for coding agents exists and is maintained, but nothing
  measured shows a gain over the practice in use, so the practice stays and the comparison decides. Challenger arm: HASP
  1.0.43, `gethasp/hasp` at `624b3b38ac4f7a267e6925c545768c95945d781a`; its licence file says FCL-1.0-ALv2 and GitHub
  reports no standard identifier; nothing of it is installed or accepted. What decides, verbatim: "HASP against the
  repository's runner and guard on the existing synthetic leak-path fixtures: output and trace checks, audit records,
  client boundaries, restart and removal. A claim that an agent can never read a value needs direct controls and a
  stated isolation scope. Native client sign-ins stay native: no import or copy of an authentication store, no real
  secret, no operating-system grant and no provider call is part of the comparison." The practice is kept unless the
  challenger shows a measured gain.

## The six amendments

An amendment records a later decision on a row and leaves the row's fields as the rounds decided them. Each names the
alternatives it admits and the comparison that would overturn the row.

- **`claude-code`: keep.** No comparison establishes a better outcome for the interactive job. pi 1.0.0 (released
  2026-10-01) is admitted as a comparison lead, with its own native sign-in and no credential copying. A comparison that
  shows a better outcome for the interactive job would overturn the row; none has run.
- **`codex`: keep.** No comparison establishes a better outcome for the interactive job. The native CLI at 0.160 is
  also an agent arm of the task-worker comparison; the Codex SDK is a consumer surface of the CLI, not an arm of its
  own. The same overturn condition as for `claude-code` applies.
- **`agent-runtime-worker`: keep the selection meanwhile; measure the alternatives.** The owner's pin was never
  compared. OpenHands software-agent-sdk 1.50.1 stays the selection and is the baseline of a comparison. Arms: that
  baseline; Codex CLI 0.160 (native) as an agent arm; pi 1.0.0 as a challenger; mini-swe-agent 2.4.6 only for an
  identified remaining gap. The contract, verbatim: "Tasks, base, model, route, effort, tools, attempt budget,
  environment and independent graders are frozen through the existing owner of the runtime qualification, and failed
  attempts are preserved. Sealed tasks, questions, model, routes, metrics and arms of the earlier gate are kept unless an
  amendment declares the change. A subscription route that cannot match the model and gateway contract is a separate
  operational control, not an arm." The comparison's result decides the row.
- **`research-harnesses`: keep GPT Researcher 3.7.0; measure the second gatherer.** GPT Researcher stays and is the
  baseline. DeerFlow 2 is a ground-up rewrite into a general harness, with the older research behaviour on another
  branch; it stays the selected second gatherer until the comparison returns. Arms: DeerFlow 2.1.0, the selected second
  gatherer, and Onyx 4.8.3, a challenger. The contract, verbatim: "Questions, as-of date, model, search and budgets
  match across arms. Judged on claim-to-source support, numeric units and denominators, accessible citations and
  coverage, plus usage, time and footprint. Fetching a citation is not an entailment verdict." The comparison's result
  decides the second gatherer.
- **`agent-messaging`: the owner wants messaging between sessions and between the two clients; the transport is
  measured before one is selected.** This amendment is by the owner's decision, then by direct consensus on the arms.
  The owner's sentence, verbatim:
  "need to be passwardless seamless workflow,passwardmangement and llm native is a must,bypasspremission seamless across session messaging, claude-codex messaging etc".
  The row's first condition, the owner's decision on the permission posture, is answered. Native Claude Code covers
  Claude to Claude; cross-vendor delivery was not established by the reviewed native sources. Concord MCP, an arm of the
  earlier text, is not among the agreed arms. The earlier message-count contract is amended with the owner before a
  run. Arms: the clients' native facilities only, as the control; hcom 0.7.27; agmsg 1.5.2, each delivery mode named
  separately. agmsg's Codex monitor adds an app-server bridge, startup priming and cleanup limits, so it is not
  described as daemon-free. The contract, verbatim: "Persisted, delivered and acknowledged are counted separately;
  duplicates and order; latency, nudges and context added; orphan cleanup; across idle, busy, restart, interruption and
  project isolation. Existing daemon and session ownership is preserved." The row stays split and installs nothing
  until that measurement returns. Its `resolution` keeps the earlier arms (hcom and the native-only control) and the
  earlier measurement text, which names Concord MCP and a test of 200 messages each way, because an amendment changes
  no field of its row.
- **`credential-guard`: keep the guard; hold one enforcement comparison.** HOL Guard 3.17.1
  (`hashgraph-online/hol-guard` at `85090ce61ed5bb5457104b5a73cb2bbc9443fda0`, Apache-2.0) declares native interception
  and managed launches beyond the guard's text check of Claude Code shell commands; the managed launch is declared for
  Codex only, and for Claude Code it declares hooks alone, in the project's local settings file. Its support matrix is
  a source claim: native client compatibility, failure behaviour and the preservation of existing hooks are not
  qualified. The comparison is about enforcement and stays separate from the custody comparison; the two are not merged
  into one winner. That scoped enforcement comparison would overturn the row. Proposal: the Codex lane's, in its note
  (`codex-decisions.md`, version of 2026-10-02T18:57:10Z, "Scoped novelty source dispositions"). Independent review:
  the Claude lane's, in `claude-review-held-topics.md`, topic 1: eight claims confirmed and two qualified, the managed
  launches (for Codex only, now in the text above) and, for the review's brief, whether 3.17.1 is the current release
  (3.17.2 followed on the same day). Qualification: the comparison pins HOL Guard 3.17.2 or later, released on
  2026-10-02 at 21:12:17Z. Acknowledgements: the Claude lane's comment 5959684384 (2026-10-02T19:16:53Z)
  agreed to this amendment and the held topics below, from the note and before that review, and the Codex lane's
  comment 5959996494 (2026-10-02T19:35:35Z) recorded receipt of that agreement.

## Held without a row change

Each of the first three topics, like the `credential-guard` amendment above, is the Codex lane's proposal in its note
(`codex-decisions.md`, version of 2026-10-02T18:57:10Z, "Scoped novelty source dispositions") and has the Claude lane's
independent review in `claude-review-held-topics.md`. The Claude lane agreed to it in comment 5959684384
(2026-10-02T19:16:53Z), from the note and before that review, and the Codex lane recorded receipt of that agreement in
comment 5959996494 (2026-10-02T19:35:35Z).

- **Evaluation harness.** Keep Inspect AI 0.3.273 and Harbor 0.23; AgentCompass 1.0.0 only for an identified unmet
  evaluation requirement. AgentCompass supplies composable harness, environment, trajectory and resume machinery; a
  comparative advantage is unmeasured. Its Codex and Claude adapters turn permission bypass on by default, and both
  supply provider API configuration (each needs an API key and a base URL and writes its own client configuration, so
  neither runs on a native sign-in as shipped), so equivalence with the native account route is not established. No
  adapter or permission change is adopted. Qualification: the Claude adapter writes its API key in plaintext into a
  settings file, by default under /tmp (its file mode was not verified), which conflicts with the repository's rule
  that a provider key stays in a 0600 env file passed by pointer. Proposal: the Codex lane's note. Independent review: the Claude lane's,
  topic 2: ten claims confirmed and one qualified, that only the Claude adapter supplies provider configuration (the
  Codex adapter does too, as the text above now says). Acknowledgements: comments 5959684384 (the Claude lane,
  19:16:53Z) and 5959996494 (the Codex lane, 19:35:35Z), on the note's version of 18:57:10Z.
- **Docker Compose 5.6.0.** Qualify the update; the selected 5.5.1 stays until the owner of that review accepts it. It
  is the same incumbent at a newer release: dry-run, config-hash, watch, monitor and log fixes, and more than those,
  among them manually triggered jobs, provider-service relay networks, warnings for unsupported Compose-file
  attributes, --parallel across all bulk engine calls, and docker/cli 29.8.2 with newer moby, containerd and buildkit
  libraries. The Codex lane holds the isolated version and help binding review; no daemon, container, global or
  destination installation is part of it. This record moves no pin. Qualification: Docker's apt channel for Ubuntu
  26.04 already carries Compose 5.6.0 and nothing in the install plan holds the package, so 5.5.1 is held only at
  install time, and a later apt upgrade would move to 5.6.0 without the review. Proposal: the Codex lane's note.
  Independent review: the Claude lane's, topic 4: four claims confirmed and two qualified, the list of changes
  (incomplete in the note; the text above names the main further ones, and the review lists more) and, for the review's
  brief, that nothing in the release changes what the install plan or the rootless engine relies on (no rootless change
  and preserved configuration hashes upstream, not checked on a host). Acknowledgements: comments 5959684384 (the
  Claude lane, 19:16:53Z) and 5959996494 (the Codex lane, 19:35:35Z), on the note's version of 18:57:10Z.
- **Catalog freshness and the session-start notice.** Keep the existing automation; the Codex lane owns a daily
  report-only cadence and the notice documentation. The existing freshness workflow, weekly at the revision the note
  cites and daily since pull request 613 (merged 2026-10-02), already supplies metadata and drift reports with guarded
  evidence-only proposal pull requests (on a manual dispatch, or on its schedule only where the repository opts in).
  Updatecli 0.122.0 overlaps that mechanism in detection, through its sources and conditions; its targets, which edit
  pinned files and open pull requests with the edits, are the stage the workflow withholds, because the separate
  convergence review owns the pins. It shows no extra closure, so no new dependency is adopted. Proposal: the Codex
  lane's note. Independent review: the Claude lane's, topic 3: five claims confirmed and four qualified, the cadence
  and the overlap (both now in the text above), that the cadence change sits on a separate branch (it has merged as
  pull request 613), and that a historical 48-hour statement needs a dated correction (the correction has landed).
  Acknowledgements: comments 5959684384 (the Claude lane, 19:16:53Z) and 5959996494 (the Codex lane, 19:35:35Z), on the
  note's version of 18:57:10Z.
- **Local generation and embedding models.** Not part of this record. The first trial's result and the arms chosen
  again from the newest releases follow in their own record.

## A note to the trading lane

The record changes no row of the trading lane and keeps the trading destination. It hands that lane these facts:

- NautilusTrader's latest non-prerelease release on GitHub is 1.231.0 (27a8e54e), and its title says Beta.
- The selected 2.0.0rc5 (1b0a49d2) is a prerelease; its README frames release candidates as community testing and discourages production use. A lookup of a final v2.0.0 release returned 404.
- The pinned README labels the Interactive Brokers adapter stable and the tree contains it; host and broker acceptance are separate.
- No Alpaca adapter was found in the reviewed 2.0.0rc5 tree and integration list.
- LEAN shows recent regression and code activity (0ebc2fc4); that is not a superiority result. Lumibot 4.6.3 (fc05c8ed) includes Alpaca and Interactive Brokers implementations, with no account-connectivity acceptance.

## Corrections the review made to the proposals

- The proposal's reason for keeping the two native clients said they are the only harnesses that run on the
  subscriptions in use. The Codex lane's source reading withdraws that: OpenAI's announcement of 2026-09-28 supports
  eligible third-party local and open-source use of a ChatGPT sign-in, and pi 1.0.0 ships its own provider for it.
  Neither source proves this owner's entitlement or pi's execution on the destination.
- The proposal called NautilusTrader 1.231.0 the latest stable release. GitHub's latest non-prerelease release is
  1.231.0, and its title says Beta. The proposal's statement that the tree has no Alpaca adapter is narrowed to: none
  was found in the reviewed 2.0.0rc5 tree and integration list. The proposal's word stale for backtrader is dropped: its
  maintenance was not verified.

The published copy of the proposals keeps the original wording.

## What is not established

The record's own list, verbatim:

- No comparison named here has run: no arm was installed, no model was called and no host was changed for these decisions.
- No row here is a merit acceptance, a host acceptance or a useful-task result on the destination distribution.
- A new row that installs something is installed and accepted only through the install plan; the client configuration wires it only after that.
- Benchmark standings were not used: the public leaderboards the reports name did not come through a plain fetch.
- The reports that supplied the leads ran on a local model; a second gatherer and a rerun on the GPT route are owed.

Beyond that list:

- This is not a blind round: the Codex lane decided with the Claude lane's proposals in front of it.
- The two install commands and the two acceptance checks that the install plan gained for `skill-discovery` and
  `skill-authoring` have not run anywhere. The plan says so in its status, in the notes of both rows and in its
  validation file, and no earlier run of the plan covers them.
- The acknowledgements are comments on a pull request. The manifest's build checks that the record lists them; it does
  not fetch or hash them, and it does not check what the record says each one covers.
- For the scoped dispositions, the Codex lane's side is its note of 2026-10-02T18:57:10Z, which writes them, and its
  receipt of the Claude lane's agreement (comment 5959996494); none of the Codex lane's comments listed here
  acknowledges them by name. Its comment 5959205007 (18:51:56Z), which came before that version of the note, says that
  the review of HOL Guard, AgentCompass and the Compose delta continues.
- The Claude lane acknowledged the Codex lane's scoped dispositions and the `credential-guard` amendment (comment
  5959684384) from the note, before it read their sources. Its review, `claude-review-held-topics.md`, came afterwards:
  of 36 claims it confirms 27, qualifies 9 and refutes none. Where this record states a qualified claim, its text now
  carries the qualification; no decision changed. Three further facts of the review are carried as `qualifications` in
  `consensus.json`, again without a change of decision or label: the `credential-guard` comparison pins HOL Guard 3.17.2
  or later; AgentCompass's Claude adapter writes its API key in plaintext into a settings file under /tmp by default;
  Docker's apt channel already carries Compose 5.6.0 and nothing holds the package. One fact is reported here but not
  carried into `consensus.json`, which states no claim it bears on: the record's link for AgentCompass's metadata
  points to line 5 of its `pyproject.toml`, while the values are on lines 7, 10 and 11. The review's other findings
  that this record does not carry are in the review only.
- The request note says 99 reports; the folder held 103 report folders when it was counted later the same day. The
  count is discovery metadata and no decision rests on it (`copy-notes.json`).

## Where the change lands

- **Manifest.** `evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py` gains the consensus
  step; `definitive-manifest.json` names the record under `sources.consensus` by path and SHA-256. `controls.py` holds
  one failing control for each refusal of that step.
- **Install plan.** `evidence/artifacts/new-wsl-install-plan-20261002/` gains the five rows: two install one skill
  folder each, pinned to the record's commits, and three install nothing. Its checker prints `OK: 69 rows: 38 installed
  by default, 3 measurement-only, 28 not installed; 67 commands and 57 acceptance entries agree with the scripts`.
- **Handbook.** `docs/new-wsl-handbook.md` and its JSON are regenerated; the generator accepts the row kind
  `consensus` only for a row that the consensus record adds, and lists each amendment under its layer's table.

## The public dashboard checkpoint

The checkpoint `observability/grand-dashboard/state.json` gains one gate, `new-wsl-distribution-20261002`, whose
evidence reference is this record. It states two things apart.

Source selection, on main, in four files:

- the manifest, `evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`;
- the recipe, `adoption/platforms/linux-wsl2-new-distro.md`;
- the install plan, `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json`;
- the handbook, `docs/new-wsl-handbook.md`.

Host qualification, which is open. A useful task per client, the roles and the lifecycle are unqualified on the
destination distribution, the one meant to stay. The install plan's scripts, at the revision with 64 rows as merged to
main (`6652b78e`), ran once on that distribution on 2026-10-02. The record of that run is private; its public receipt
comes with the destination's acceptance, and the checkpoint names the run without counting it as qualification. The
five rows of this change have not run there or anywhere else. A source selection is not an acceptance of the Codex
0.160 client, of its configuration or of an SDK on that host.

## Sources

- The record: `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`, with `claude-proposals.md`,
  `claude-request.md`, `codex-decisions.md`, `claude-review-held-topics.md` and `copy-notes.json` in the same folder.
- The acknowledgements, each described under Method: [Claude, 18:29:20Z](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5958766754),
  [GPT, 18:45:13Z](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5959059286),
  [GPT, 18:51:56Z](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5959205007),
  [Claude, 19:16:53Z](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5959684384) and
  [GPT, 19:35:35Z](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5959996494);
  the last two for the scoped dispositions and the `credential-guard` amendment, as the Codex lane's note of
  18:57:10Z writes them.
- The Claude lane's review of the scoped dispositions: `claude-review-held-topics.md`, which gives each claim's sources,
  each at a pinned commit where one is cited.
- `skill-discovery`: [find-skills at the pinned commit](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/skills/find-skills/SKILL.md).
- `skill-authoring`: [Codex's embedded skills](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/skills/src/lib.rs#L55),
  [skill-creator at the pinned commit](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md).
- `research-skill`: [the GPT Researcher skill](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/skills/gpt-researcher/SKILL.md),
  [gptr-mcp](https://github.com/assafelovic/gptr-mcp/tree/63884773685b1f12c7f0d9e283b3d71a5b9b5fda),
  [DeerFlow's deep-research skill](https://github.com/bytedance/deer-flow/blob/v2.1.0/skills/public/deep-research/SKILL.md).
- `cross-family-review`: [Claude Code's local review](https://code.claude.com/docs/en/code-review.md#review-a-diff-locally),
  [the Codex CLI source](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli),
  [PR-Agent's README](https://github.com/The-PR-Agent/pr-agent/blob/v0.47.0/README.md).
- `credential-custody`: [the HASP release](https://github.com/gethasp/hasp/releases/tag/v1.0.43),
  [its licence](https://github.com/gethasp/hasp/blob/624b3b38ac4f7a267e6925c545768c95945d781a/LICENSE),
  [its commands](https://github.com/gethasp/hasp/blob/624b3b38ac4f7a267e6925c545768c95945d781a/README.md#L44).
- `claude-code`: [pi's OpenAI provider](https://github.com/earendil-works/pi/blob/v1.0.0/packages/ai/src/providers/openai.ts).
- `codex`: [the Codex SDK's README](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/typescript/README.md).
- `agent-runtime-worker`: [the OpenHands example](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/examples/01_standalone_sdk/01_hello_world.py),
  [mini-swe-agent's README](https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/README.md).
- `research-harnesses`: [GPT Researcher](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/README.md),
  [DeerFlow](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md),
  [Onyx](https://github.com/onyx-dot-app/onyx/blob/v4.8.3/README.md).
- `agent-messaging`: [Claude Code's cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging.md),
  [hcom](https://github.com/aannoo/hcom/blob/v0.7.27/README.md),
  [agmsg's Codex monitor](https://github.com/fujibee/agmsg/blob/v1.5.2/docs/codex-monitor-beta.md),
  [Codex's app-server daemon](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/app-server-daemon/README.md).
- `credential-guard`: [HOL Guard's support matrix](https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md#L9).
- Held topics: [AgentCompass](https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/pyproject.toml#L5),
  [Docker Compose 5.6.0](https://github.com/docker/compose/releases/tag/v5.6.0),
  [Updatecli](https://github.com/updatecli/updatecli/blob/20e57d1b35190c25e41f3e2a8339621027484c0c/README.md).
- Trading facts: [the 1.231.0 release](https://github.com/nautechsystems/nautilus_trader/releases/tag/v1.231.0),
  the pinned README at [line 276](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/README.md#L276)
  and [line 120](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/README.md#L120),
  [the LEAN commit](https://github.com/QuantConnect/Lean/commit/0ebc2fc44fd4754ff66bdc7ef6cb42c5003f8fc1),
  [the Lumibot release](https://github.com/Lumiwealth/lumibot/releases/tag/v4.6.3).

These are the record's sources. This change opened none of them again except the two pinned skill folders, whose tree
and blob hashes the install plan's `SOURCES.md` reports; the sources of the scoped dispositions were read again by the
Claude lane's review, which names each one.

## Overturn

- For an added row: its gate fails or its named measurement returns against it. A blind definitive default or a
  measured result for the same slot takes precedence under the rule.
- For an amendment: the comparison it names returns. The amended row itself is overturned as its own record says.
- For the rule: the owner withdraws the sentence that allows it. A consensus row that is found to replace a blind
  definitive default or a measured result breaks the rule's last sentence and does not stand.
