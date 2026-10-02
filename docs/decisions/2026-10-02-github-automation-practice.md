# GitHub automation practice, reconciled with the live settings and the final catalog (2026-10-02)

Lane: foundation. North-star action served: a reliable landing path for every unit that moves the stack toward the
north star (each one lands as a squash-merged pull request behind the required checks). Status: a practice record. It
changes no workflow, ruleset, required check, gate or selection.

## Decision

`docs/github-automation.md` gains a "Current practice (2026-10-02)" section, and `catalogs/foundation/automation.json`
a `current_practice_20261002` block. Both record the live state read with `gh api` GETs on 2026-10-02 and mark the
drifted sections as superseded:

- 8 required checks (`validate`, `token-report`, `secret-scan`, `dependency-review`, `osv-scanner`,
  `verdict-review-gate`, `validate-macos`, `sota-sources`), strict up-to-date checks off. The 2026-09-23 snapshot
  listed 3.
- Squash merges only. The 2026-09-23 snapshot allowed squash and rebase.
- `sota-sources` is live. The 2026-09-25 note said it was not yet live.
- The PR template's Lane line and `### SOTA sources` section, which the earlier description omitted.
- The merge guard lives in `docs/lanes.md`, "Labels and PRs", and the doc links it rather than restating the commands.
- Secret scanning: gitleaks stays the required gate; betterleaks runs as a report-only trial; GitHub push protection is
  on.

Against the final catalog of 2026-10-01 (`docs/final-catalog-20261001.md`, from the final-catalog pull request), the
three layers this practice touches keep their selections of record. A standing pick becomes final only after
new-host acceptance and the layer's preregistered comparison.

| Layer | Standing picks (both families) | Challengers (one family) | In use here |
| --- | --- | --- | --- |
| git-github-automation | git, gh (cli/cli), Worktrunk, sem | difftastic, claude-code-action | git, gh, Worktrunk, difftastic; claude-code-action unadopted (M45); sem not adopted |
| ci-supply-chain | actions/attest, Syft, Dependabot, actionlint (kjanat), zizmor | github/codeql-action | all five standing picks; the challenger is the `upload-sarif` step already in use |
| secrets-credentials | betterleaks | trufflehog | gitleaks 8.30.1 as the required gate; betterleaks v1.8.1 as a report-only trial |

## Preregistered comparisons

Each comparison is frozen in its own preregistration before any arm runs, and each verdict lands in its own pull request.

- **P1, the secret-scan gate.**
  - Arms: gitleaks 8.30.1 (the selection of record and required gate) against betterleaks 1.9.0 (the standing pick)
    and trufflehog at its latest release when the comparison is frozen (the challenger), with verification on and off.
  - Corpus:
    - the pinned Samsung/CredData benchmark through its upstream harness;
    - this repository's history, for blocking false positives;
    - network calls, runner time and memory.
  - Scoring:
    - Findings are matched by location, not by rule ID.
    - The unprefixed 40-hex class is reported separately; it is the class behind the trial's failing fixture tests d2,
      d4 and d5 (`evidence/artifacts/betterleaks-parity-20260927/`).
  - Decision rule:
    - betterleaks replaces gitleaks inside the `secret-scan` job, with the check name unchanged, only if it shows no
      unaccepted class loss and no extra blocking false positives.
    - trufflehog joins the new-WSL install only on a measured gain.
    - The gate swap is its own `lane:shared` pull request.
- **P2, structural diffs.**
  - Arms: sem 0.25.0 (standing pick) against difftastic 0.71.0 (challenger and selection of record) and plain
    `git diff`.
  - Corpus: difftastic's sample files plus a frozen set of this repository's PR diffs.
  - Agent-answer quality is scored with promptfoo, the upstream harness AGENTS.md names for LLM A/B.
  - Decision rule:
    - difftastic stays the selection of record unless sem shows a measured gain.
    - On a tie, the frozen agreement rule would keep sem standing while the Claude pick keeps it "only if the
      structural-diff comparison shows a gain", so a tie goes to the user.
- **P3, review automation.**
  - anthropics/claude-code-action stays unadopted under decision M45 (`docs/decisions/2026-09-28-community-sweep.md`,
    M45 and its auto-merge note).
  - It becomes an arm of the seeded-defect review comparison only after its prerequisites land:
    - the action is in both the live allow-list and `.github/actions-permissions.json`;
    - it is pinned to a full SHA;
    - it has a secret with a documented owner;
    - its allowed tools are least privilege;
    - the question of a nested `oven-sh/setup-bun` allow-list entry is answered.
  - No workflow may hold `pull-requests: write` except the catalog-freshness `propose` job
    (`test_pull_requests_write_is_granted_only_to_the_propose_job`).
- **Not compared:**
  - `github/codeql-action`: its `upload-sarif` step is already in use, and CodeQL default setup stays on the `default`
    suite (`docs/decisions/2026-09-27-codeql-quality-suites.md`).
  - Scanners that no family picked.

## Pins not moved here

| Pin | Recorded | Upstream | Owner |
| --- | --- | --- | --- |
| betterleaks (trial job) | v1.8.1 (`validate.yml`) | v1.9.0 (2026-09-29) | the automation maintainer, with P1 |
| gh | 2.101.0 | 2.102.0 | adoption, at the new-host install; re-check the merge guard in `docs/lanes.md` at the new tag first |
| Worktrunk | 0.79.0 (`manifests/stack.json`), 0.78.0 (`blueprints/convergence-practice/wsl-native-tools/pins.json`) | 0.80.0 | the workers owner |
| `github/codeql-action/upload-sarif` | v4.38.1 | v4.38.2 | Dependabot |

## Alternatives

- **Switch the gates now.** That means making betterleaks the required secret gate and starting a claude-code-action
  trial. Rejected because a selection changes only on measured evidence plus blind cross-family convergence, and
  betterleaks' fixture tests d2, d4 and d5 fail on every run today.
- **Leave the doc as it was.** Rejected because it understated the required checks and merge methods that every
  session relies on to land work.

## Overturn

Revisit this record when any of these happens:
- a P1, P2 or P3 result;
- a change to the live ruleset or the repository settings (re-read with `gh api`);
- a new final-catalog edition that changes these three layers.

## Evidence class

The current-practice facts are configuration observations from read-only `gh api` GETs on 2026-10-02 (the ruleset and
the repository settings). The standing picks come from the final catalog (`source_review` in two model families).
Nothing here was installed or measured.

## SOTA sources

- GitHub rulesets and required status checks:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- Secret-scanner benchmark: https://github.com/Samsung/CredData. Scanners: https://github.com/gitleaks/gitleaks,
  https://github.com/betterleaks/betterleaks, https://github.com/trufflesecurity/trufflehog.
- Structural diffs: https://github.com/Wilfred/difftastic, https://github.com/Ataraxy-Labs/sem.
- LLM A/B harness: https://github.com/promptfoo/promptfoo.
- In-repository records: `docs/decisions/2026-09-22-github-automation-closure.md`,
  `docs/decisions/2026-09-28-community-sweep.md` (M45), `evidence/artifacts/betterleaks-parity-20260927/`.
