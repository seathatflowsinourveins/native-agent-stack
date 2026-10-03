# The new WSL's definitive defaults (2026-10-01)

One default per slot for the clean install of the new WSL distribution. The decision and its limits are in
`docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`. The blind rounds' evidence class is source review by model
judges in two families, plus the published evaluations they cite. The local model server's settlement adds measured
function gates on one workstation, recorded in the first and confirmatory receipts linked from `settlements.json`.

## Files

| File | What it is |
| --- | --- |
| `definitive-manifest.json` | One row per slot across both catalogs: layer, slot, row kind, default, whether it is definitive, each family's status. Built by `assemble_manifest.py`; `--check` fails when it is stale |
| `foundation-definitive.compact.json` | The foundation's 21 layers and 4 cross rows: per slot the default, its label, alternatives, the Claude deciders' deciding facts, both critics' findings and corrections, the overturn checks and each family's status |
| `trading/trading-definitive.compact.json` | The 12 us-equities layers, in the same shape. The trading lane's work, with its builder, its one-owner map and both rounds' preregistrations |
| `settlements.json` | The model-server settlement's default, basis, scope, receipt paths and hashes, verbatim limits and overturn condition; read by `assemble_manifest.py` |
| `../new-wsl-layer-consensus-20261002/consensus.json` | The layer-consensus record of 2026-10-02, in its own folder: five rows to add and six amendments by a direct consensus of the two model families. `assemble_manifest.py` reads it in its last step, hashes the notes it names and changes no field that the rounds decided |
| `criteria.txt` | The seven criteria of the first round, unchanged |
| `decide-prompt.txt`, `decide-critic-prompt.txt` | The decision round's prompts, with the rules frozen before the round |
| `decide-workflow.js` | The Claude family's workflow script (run `wf_c0e29ea4-90f`), with both output schemas inline |
| `build_decide_packets.py`, `packets/` | The builder and the 12 packets it wrote: six slots, each in two seeded finalist orders |
| `preregistration.json` | Hashes of the criteria, prompts, packets and first-round returns, written before launch |
| `save_claude_returns.py`, `assemble_foundation_definitive.py` | Saves the Claude returns from the workflow journal; assembles the foundation documents from both families' returns |
| `render_tables.py` | Writes the decision record's tables from the manifest; `--check` fails when they are stale |
| `controls.py` | Negative controls that mutate inputs, regenerate the manifest and tables, require their named unittest failure and restore changed files. One control per refusal of the consensus step mutates the layer-consensus record |
| `claude-decision-round-run.json` | Counts and times of the Claude family's decision round, read from its private journal |
| `gpt-memory-first-round-units.json` | Counts, exit codes and usage of the GPT family's two first-round units for the memory layer (the first ran without shell network), read from their private event logs |

## Row kinds

- `judged`: decided in the decision round, by two deciders per family in seeded orders and one critic per family.
- `first_round`: the first blind round's pick (one judge and one critic). It is the slot's default until the second
  family's first-round verdict returns.
- `pinned`: a requirement the user selected. It is carried, not judged.
- `project_practice`: the project's own code or practice, settled by its closure record.
- `no_blind_default_today`: a slot that cannot be decided blind today, with the reason.
- `consensus`: a row added by the layer-consensus record of 2026-10-02, a recorded direct consensus of the two model
  families. It is not a blind result and not a measurement, and it is never definitive.

A row is `definitive` only when both deciders of both families named the default and both critics returned converged.

An `amendments` list on a row holds later decisions by direct consensus. It stands beside the row's fields and changes
none of them.

## A known leak in one packet

The memory packet (`packets/memory-owner.order-1.json` and `.order-2.json`) carries the second first-round reviewer's
evidence gaps verbatim, and two of those sentences contain routing wording (an "Astra/Max arbitration" attempt and an
approval-policy note) from which a decider could infer which model family wrote the notes. Reviewer names were removed
everywhere else. The packets are frozen inputs and are published as they were used. Both first-round reviewers had kept
the same three finalists, and the memory slot is now decided by a measurement, so the leak changes no row.

## What is kept private

The full returns of both families (the Claude returns' sha256 is in `foundation-definitive.compact.json` under
`sources`, with each GPT return's) and the full foundation document (its sha256 is `full_document_sha256` there). The
trading lane's full document, returns and packets are likewise private and cited by hash in its preregistrations. The
decision directory's host path appears in the documents as `<definitive-defaults-20261001>/`.

## Rebuilding

```
python3 assemble_foundation_definitive.py <repository> <decision-directory> <output-directory>   # needs the private returns
python3 assemble_manifest.py            # from the two committed compact documents, settlements.json, convergence.json and the layer-consensus record
python3 render_tables.py --write ../../../docs/decisions/2026-10-01-new-wsl-definitive-defaults.md
python3 -B controls.py ../../..         # regenerate and require each named unittest failure; without an argument it uses this checkout
```
