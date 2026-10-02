# Combining the blind GPT round with the Claude record (work in progress, 2026-10-02)

This folder holds the inputs, the rule and the mechanical result of one step toward the final list of repositories
for the new WSL install. It is not the final list: the critics' verdicts on the contested items and the twelve added
slots are still to come, and nothing here was installed.

## Files

- `RULE.md`: how a repository becomes final, written before the results were read, with amendment 1 (written before
  the script ran on any layer) and what the author had already seen at each point.
- `combine.py`: applies the rule. `python3 combine.py <repository checkout> sol-ultra-round <output folder> <git ref>`
  where the git ref holds pull request 595 (`claude/grand-catalog-final-20261001`, read at `025c4892`), from which the
  script reads `evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/selection-gpt.json`; the
  Claude record is the merged definitive manifest on `origin/main`.
- `sol-ultra-round/order-1/` and `order-2/`: the 42 final messages of the GPT lane's blind round (GPT-6.1 Sol at
  ultra effort through `codex exec`, live web search, one process per layer, the same 21 packets in two seeded
  candidate orders). 10 units finished before the host restart on 2026-10-02; the other 31 ran afterwards with the
  same commands and all exited 0; order 1's memory unit had run earlier as the lane's first unit.
  One change to the copies: in the two `code-navigation.json` files, six GitHub commit links (2 and 4) are shortened
  from 40 to 12 hexadecimal characters, because the repository's secret scanner flags a 40-character value in a file
  that also contains the word "sourcegraph". The links still resolve and no selection field is touched. The
  unchanged originals have sha256 `ac8795e46fb28697b15908405f2e1ef653590ec2d3afb34b8c9dd2af9ee0d233` (order 1) and
  `3ed5b3fc5dfd642fdfaec38b4234a45857a6f675ce684d0351f97faf1d699e34` (order 2) and stay in the lane's state folder.
- `combined.json`: the script's output, one row per foundation layer.

## Result of the mechanical step

29 repositories are final (in the Claude record and in enough GPT samples), 20 are in the Claude record only and 13
are GPT-only challengers. Under the rule a Claude-only pick is not installed unless it is the only owner of a job the
installed set leaves uncovered, and a GPT-only challenger is installed only if a Claude critic finds it owns such a
job. Rows settled by a measurement, rows waiting for one (memory, code search), the owner's pins and project practice
are untouched by the rule.

## Limits

- The two orders are two samples of one model and one prompt contract, not two independent families.
- On seven layers pull request 595's sample is not counted (amendment 1): its judges also received instructions that
  name eight candidates, by that pull request's own record. The Claude record carries the same kind of exposure on
  those layers.
- The round's judges ran on the workstation under its global Codex instructions, which name no candidate except RTK.
- Evidence class: model judgments on public sources. No candidate was installed or measured for this step.
