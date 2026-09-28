# AN-13 M4 and M5: two-family lanes and M5's adjudication (2026-09-28)

This package holds the evidence for [`docs/decisions/2026-09-28-an13-m4-m5.md`](../../../docs/decisions/2026-09-28-an13-m4-m5.md).
- **M4:** both lanes rejected the report's rewrite of the vendored skill, so it gets no edit.
- **M5:** the lanes amended with different texts, and the blind adjudication split. The lines stay unchanged, and both
  texts are recorded.

## Layout

- **`round1/`: both lanes on one frozen packet.**
  - `packet.md` was frozen at `9f8db582` and `packet.sha256` holds its hash. It quotes the report's findings and
    rewrites verbatim.
  - `sources.json` holds the 13 dated sources.
  - The schema is in `schemas/`.
  - `prompts/` holds the GPT-6 probe, the GPT-6 lane's prompt (`audit-judge-m45.txt`) and the Claude lane's brief.
  - `returns/` holds both lanes' returns and `round1-tally.json`.
  - `runner/` holds the packaged runner's records of the probe and the GPT-6 lane.
- **`adjudication/`: M5's blind round.**
  - The inputs and packets as sent to the judges are in `adjudication-inputs/` and `packets/`.
  - `prompts/` holds `judge-{AB,BA}.txt` for the GPT-6 runner jobs and `claude-task-{AB,BA}.txt` for the
    `blind-adjudicator` agents. The judge schema is in `schemas/`.
  - `sent-sha256.json` holds the hashes of what was sent.
  - `runner/` holds the runner's records of the two GPT-6 judgments.
  - The four judgments are `{gpt6,claude}.{AB,BA}.json`, and `m45-mapping.json` holds each order's assignment of
    returns to lanes.
  - The audit and the tally:
    - `audit-m45.json` holds each hit's pattern, scope and match;
    - `audit-m45-windows.json` holds each hit's window, with host details replaced;
    - `tally-m45.json` is the tally.
  - Two checks ran after the judges:
    - `audit-control-m45.json` reproduces the audit and voids planted accesses;
    - `template-checks-m45.json` applies the lane-A template's self-test payloads, and a root scan like the
      template's, to this round's audit and patterns, without running the template's own scripts.
- **`scripts/`: the scripts as run, with host paths replaced.**
  - `frozen-sha256.txt` holds the hashes taken before dispatch. The package keeps no record of when.
  - `isolation.log` records the steps taken before dispatch.
- **`usage.json`:** each run's provider usage, one provider at a time and never added up.
- **`tool-counts.json`:** the tools each Claude run called, by name.
- **`review/`:** the two reviews of this change, their prompts and usage, and what happened to each finding.

The published copies replace host paths with these placeholders:

| Placeholder | Stands for |
| --- | --- |
| `<work>` | the private work directory |
| `<base>` | the read-only base worktree the lanes read, since removed |
| `<adj>` | the adjudication directory |
| `<runs>` | the adjudication runner's directory |
| `<scratch>` | any other scratch path |
| `<worktree>` | the reviewed worktree |
| `~` | the home directory |
| `<user>` | the host user name |
| `<uuid>` | a session or agent UUID |

## Evidence classes

- **Model judgments.** These are the two lanes' returns and the four adjudications.
  - The GPT-6 returns are the runner's final messages.
  - `save_claude_return.py` and `save_claude_judgment.py` extracted the Claude returns from the agents'
    transcripts. They refuse a return without the expected ids or choice.
  - These are judgments on a frozen packet, not measurements of model behavior.
- **Runner records.** These are the packaged runner's own records of each GPT-6 job: model, effort, codex-cli version,
  status, exit, limit and usage.
- **Scripted checks on local files:**
  - the packet hash and the frozen hashes;
  - the audit, its windows and the reproduction after the fact;
  - the template checks;
  - the tally and the tool counts.
- **Not published:** the transcripts and the private work directory. The transcripts carry the host's session
  context.

## Repeatable checks

From this directory:

```sh
(cd round1 && sha256sum -c packet.sha256)
(cd scripts && sha256sum -c frozen-sha256.txt)
python3 -B scripts/reproduce_template_checks_m45.py <clone holding 9f8db582> 9f8db582 <empty dir> <out.json>
```

- **The frozen hashes.** The first two commands print `OK` for every file. The frozen scripts contain no host paths,
  so their published copies still match.
- **The template checks.** The third command exits 0 when both of the lane-A template's checks, applied to this
  round's audit and patterns, fail, as they do.
- **What was sent.** The inputs, packets and judge schema match `adjudication/sent-sha256.json`. The four prompts
  differ from their sent hashes only by the host-path placeholders.
- **The tally.** Check it by hand. For each judgment, map its `choice` through `m45-mapping.json` for its order, then
  drop the judgments that `audit-m45.json` marks `void`.
  - The two valid judgments name different lanes' texts, so no text has the four votes the rule needs.
  - The other scripts as run read the private work layout, so they do not run from this package unchanged.

## What is not claimed

- **No behavior was measured.** Neither the M5 texts nor the skill's wording was tested.
- **The audit was not built from the log's template, and its checks ran after the judges.** `docs/harness-defaults.md`
  records the lapse. Both Claude judgments are void on false positives, and the decision record explains why the
  outcome does not depend on them.
- **The adjudication packet stated a wrong premise.** Its round-1 summary says `receipt.json:88` credits the
  installer, and the decision record's limitations explain it.
- **The two lanes had different access.** The Claude lane had no web tool and relied on the packet's sources.
- **Usage leaves two things out.** It excludes the coordinator session and the server-side advisor's own usage.
- **Earlier work lives in #444.**
  - `audit_m45.py` adapts the X9 round-3 audit, `evidence/artifacts/prompt-audit-20260927/x9-round3/audit_r3.py`.
  - The AN-13 record is `evidence/artifacts/prompt-audit-20260927/an13/`.
  - Neither is on `main` until #444 merges.
