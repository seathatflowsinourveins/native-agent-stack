# The new WSL's layer consensus (2026-10-02)

Rows added to the definitive manifest of the new WSL distribution, and amendments recorded on its rows, by a recorded
direct consensus of the two model families. The decision, its rule and its limits are in
`docs/decisions/2026-10-02-new-wsl-layer-consensus.md`.

## Files

| File | What it is |
| --- | --- |
| `consensus.json` | The record that the manifest's assembler reads: the owner's sentence that allows the method, the rule, five rows to add, six amendments, four topics held without a row change, a note to the trading lane, the two corrections the review made to the proposals, and what is not established. Its `records` name the three notes and the review below by path and SHA-256, and the acknowledgements by link, each with what its comment covers |
| `claude-proposals.md` | Published copy of the Claude lane's proposals for seven layers |
| `claude-request.md` | Published copy of the Claude lane's request to the Codex lane; it relays the owner's sentence |
| `codex-decisions.md` | Published copy of the Codex lane's independent decisions |
| `claude-review-held-topics.md` | The Claude lane's independent primary-source review of the claims behind the Codex lane's scoped dispositions: the `credential-guard` amendment and the three topics held without a row change. Not a copy of an exchanged note: it is written here from the review as that lane returned it, with host paths replaced as it lists at its end |
| `copy-notes.json` | Each copy's hash, its original's hash and every difference between the copy and the original |
| `wave2-records.json` | The records behind the record's wave-2 batch (2026-10-03): per layer the batch uses, the wave-2 dossier's default, the GPT family's check (verdict and model), the Claude ruling's decided default and the ruling's changes that the repository cites, verbatim, each event hashed in canonical JSON; the synthesis items the batch rests on; the GPT family's whole-wave read; and the owner's decisions of 2026-10-03 as the coordinator's records relay them. An extract made by script from the private wave-2 run `wf_18aa601f-b71` (its journal's sha256 is in the file), not a copy of an exchanged note; home-directory paths and session identifiers are replaced as its `method` says |

## The wave-2 batch (2026-10-03)

`consensus.json` carries a second batch under `wave2`: amendment 3 of the decision rule (interim installs on rows whose decided default installs nothing, written to the row's own `interim` field), its exception to the no-install rule, one added row (`statusline`), two amendments (`credential-custody`, `credential-guard`) and three interim installs (`memory-owner`, `code-search`, `context-supply`), each on the owner's decision of 2026-10-03. Its record is `wave2-records.json`. Both families' acknowledgements of the batch are owed: `acknowledgements_owed` names them, and the comments are added when the batch's pull request exists. The decision, the rule text and the limits are in the wave-2 section of `docs/decisions/2026-10-02-new-wsl-layer-consensus.md`.

## Method

Leads came from the research runtime on the live web (GPT Researcher 3.7.0 on a local model); those reports are
leads, not facts. The Claude lane re-read every fact it used from GitHub by script and wrote proposals for seven
layers and for the skills rows. The Codex lane decided each one independently from its own reading of the primary
sources and corrected two statements of the proposals. The acknowledgements are public comments on pull request 608;
`consensus.json` says what each one covers. `consensus.json` is the coordinator's record of what the two lanes agreed;
the three notes are the exchange itself.

| Comment | Lane and time (UTC, 2026-10-02) | What it covers |
| --- | --- | --- |
| 5958766754 | Claude, 18:29:20 | The Claude lane's acknowledgement of the Codex lane's decisions, which comment 5959059286 received as agreeing all seven layer decisions and the three skills capabilities |
| 5959059286 | Codex, 18:45:13 | The Codex lane's acknowledgement of the seven layer decisions and the three skills rows |
| 5959205007 | Codex, 18:51:56 | The Codex lane's statements on catalog freshness (its root takes the standing freshness and notice unit; Updatecli 0.122.0 offers no extra closure, so no new dependency) and its verdict on the research skill's dependency. It says that the review of HOL Guard, AgentCompass and the Compose delta continues, so it acknowledges none of those dispositions |
| 5959684384 | Claude, 19:16:53 | The Claude lane's agreement to the scoped dispositions as the Codex lane's note states them in its version of 18:57:10, given from the note before the review in this folder |
| 5959996494 | Codex, 19:35:35 | The Codex lane's receipt of 5959684384, and no immediate substantive objection from its Astra/max review to the additive consensus rule as supplied to it. It asks that a resolved selection be kept distinct from native qualification |

## The `credential-guard` amendment and the held topics

These four came from the Codex lane's note, section "Scoped novelty source dispositions", in its version of
2026-10-02T18:57:10Z, which is the published copy. The Claude lane agreed to them from the note in comment 5959684384
(2026-10-02T19:16:53Z); its own reading of their sources came afterwards and is the review in this folder. The Codex
lane recorded receipt of that agreement in comment 5959996494 (2026-10-02T19:35:35Z). Its earlier comments,
5959059286 (18:45:13Z) and 5959205007 (18:51:56Z), came before that version and acknowledge none of these four. Of
the 36 claims the review checks, 27 are confirmed, 9 are qualified and none is refuted; where `consensus.json` states a
qualified claim, its text carries the qualification, and no decision changed. Three further facts of the review are
carried as `qualifications` of the amendment, the evaluation harness and Docker Compose 5.6.0: the comparison pins HOL
Guard 3.17.2 or later; AgentCompass's Claude adapter writes its API key in plaintext into a settings file under /tmp by
default; Docker's apt channel already carries Compose 5.6.0 and nothing holds the package, so 5.5.1 is held only at
install time.

| Item | Proposal | Independent review | Acknowledgements |
| --- | --- | --- | --- |
| Amendment to `credential-guard`: keep the guard; hold HOL Guard 3.17.1 for a scoped enforcement comparison | The Codex lane, `codex-decisions.md`, version of 2026-10-02T18:57:10Z | The Claude lane, `claude-review-held-topics.md`, topic 1 | The Claude lane's agreement in comment 5959684384 (2026-10-02T19:16:53Z), given from the note before the review; the Codex lane's receipt of it in comment 5959996494 (2026-10-02T19:35:35Z) |
| Held: evaluation harness (keep Inspect AI and Harbor; AgentCompass only for an identified unmet requirement) | The Codex lane, `codex-decisions.md`, version of 2026-10-02T18:57:10Z | The Claude lane, `claude-review-held-topics.md`, topic 2 | Comments 5959684384 (Claude lane, 19:16:53Z) and 5959996494 (Codex lane, 19:35:35Z), as for the amendment |
| Held: Docker Compose 5.6.0 (qualify the update; 5.5.1 stays meanwhile) | The Codex lane, `codex-decisions.md`, version of 2026-10-02T18:57:10Z | The Claude lane, `claude-review-held-topics.md`, topic 4 | Comments 5959684384 (Claude lane, 19:16:53Z) and 5959996494 (Codex lane, 19:35:35Z), as for the amendment |
| Held: catalog freshness (keep the existing automation; no Updatecli) | The Codex lane, `codex-decisions.md`, version of 2026-10-02T18:57:10Z | The Claude lane, `claude-review-held-topics.md`, topic 3 | Comments 5959684384 (Claude lane, 19:16:53Z) and 5959996494 (Codex lane, 19:35:35Z), as for the amendment |

## What this folder is not

- **Not a blind round.** The Codex lane decided with the Claude lane's proposals in front of it. A row from this
  record has the row kind `consensus` and is never definitive.
- **Not a measurement.** No arm was installed, no model was called and no host was changed for these decisions. Where
  the record names a comparison or a gate, that comparison or gate has not run.
- **No host acceptance.** No row here is a merit acceptance, a host acceptance or a useful-task result on the
  destination distribution. The two rows that install are installed and accepted only through the install plan
  (`evidence/artifacts/new-wsl-install-plan-20261002/`), whose commands for them have not run anywhere. A row in state
  `resolved` is a resolved source selection, not a native qualification, as the Codex lane's comment 5959996494 asks
  the record to keep them: its open acceptance gates are the qualification still owed on the destination.

## What the build verifies

`assemble_manifest.py` reads `consensus.json` in its last step. It checks that each file named under `records` (the
three notes and the review) exists with the SHA-256 that `consensus.json` records, that at least one is named, and
stops with a message when one is missing or differs. For the three notes those hashes are the ones `copy-notes.json`
gives for the copies; the review is no copy and has no entry there. The acknowledgements are links, each with what its
comment covers: the build checks that one of each family is listed and does not fetch them, so it checks neither the
comments nor what the record says they cover. The originals of the notes are private; their hashes in
`copy-notes.json` cannot be checked from this repository. The review as it was returned is private too, and no hash of
it is recorded.

The same step refuses a record that would replace what the rounds decided: a slot that already exists, an added row
that is not of kind `consensus` or is definitive, an unknown state, catalog or layer, and an amendment that names an
unknown slot or carries one of the fields `default`, `state`, `definitive`, `repository`, `installs_nothing_extra` or
`row_kind`. `controls.py` in the manifest's folder plants each of these and requires the refusal.

## Rebuilding

From the repository root:

```
python3 -B evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py
python3 -B evidence/artifacts/new-wsl-definitive-defaults-20261001/render_tables.py --write docs/decisions/2026-10-01-new-wsl-definitive-defaults.md
python3 -B scripts/build_new_wsl_handbook.py --write
```

The first command rebuilds the manifest from its inputs and this record; `--check` instead fails when the committed
manifest is stale. The second regenerates the tables of the decision record, and the third the handbook, which reads
the manifest.
