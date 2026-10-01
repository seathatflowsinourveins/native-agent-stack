# Layer closure assessment, 2026-10-01

Per-layer assessments of the catalog layers against the closure criterion of
`catalogs/landscape/research-state.json` (`saturation.close_only_when`, five items), made for the program record
`docs/decisions/2026-10-01-definitive-sota-wsl-program.md`.

## Files

| File | Content |
| --- | --- |
| `foundation.json` | The 20 foundation layers at repository revision `3361b342aa6a8e4ec8fac8d3d980bfc4e7020f4a`, `as_of` 2026-10-01T03:50Z. Per layer: `corrected` (the assessor's return as corrected by the refuter: selected components with pins and pin sources, alternatives, evidence class, upstream currency, the five closure items each with a status and its evidence, install readiness with the missing new-host steps, the next unit), `corrections` (the refuter's corrections, 8 to 18 per layer), `verdict` (`corrected` for all 20) and `runs`. |
| `foundation-synthesis.md` | One reviewer's synthesis of the 20 assessments: ranking, cross-layer patterns, program units, pins behind their latest release, install-readiness gaps and contradictions. |
| `foundation-run-variance.json` | The item statuses of the seven layers that ran twice (the workflow was resumed after a sign-in). Five of them differ in one or two items between the two runs; none becomes final for install in either. |

The us-equities assessment (12 layers, same method) lands with the trading lane owner's records in that lane's own
pull request.

## How it was produced

A workflow ran one read-only assessor per layer (the `stack-researcher` role, Claude Opus 5.5, effort max) and then
one adversarial refuter per layer (the `evidence-reviewer` role, Claude Opus 5.5, effort max) against the original
source. A third agent of the reviewer role wrote the synthesis from the 20 corrected assessments and spot-checked
the statements it marks "(checked)". The file holds the first complete refuted result per layer.

## Evidence class and limits

- Model-authored source review of the repository at the named revision. It is not acceptance evidence, it is not a
  second independent review in the sense of item 4 (assessor, refuter and synthesis are one model family), and it
  certifies nothing about a new host.
- The item statuses are one assessor and refuter pair's judgment per layer. Where a second run exists, the border
  between met and partial, or between partial and unmet, moved in five of seven layers
  (`foundation-run-variance.json`). Treat a single cell as good to about one step; the conclusion that no layer is
  final for install holds in every run.
- The upstream "latest release" values are the assessors' reads of release pages on 2026-10-01. Most rest on one
  read that the refuter did not repeat, and the coordinator did not fetch them again.
- Citations of `<host-private campaign list 2026-09-30>` point to a record that this repository does not hold, so
  the statements resting on them are not recoverable from here. The program record's unit U3 publishes that record
  as a sanitized receipt or drops the citations.
- Line numbers refer to the named revision and drift afterwards; several assessments report drifted line references
  themselves.
- `as_of` is the workflow's launch stamp. The assessments' own `checked_at` times run later, to about 05:31Z.
- Usage: the workflow was interrupted by a sign-in and resumed, and the resumed segment ran agents again that had
  already returned. The last segment recorded 3,612,716 tokens across 20 agents; the first segment's total was not
  retained, so the complete usage is unknown.

## Corrections found in review

The assessment file is frozen: the item-4 reviews bind to its hash. Corrections to it are recorded here and applied
where the steps are carried forward (the architecture manifest's new-host steps).

- token-efficiency, next unit: `python3 scripts/adoption_status.py --json` alone cannot show that client wiring is
  complete. The script reports `client_wiring` only with its opt-in `--client-wiring` flag, so the step is
  `python3 scripts/adoption_status.py --client-wiring --pinned-versions --json` (review of PR #573, 2026-10-01).
- instructions-skills, new-host steps: the Codex `[[skills.config]]` tables come from a separate renderer call,
  `python3 tools/adoption/install_skills.py --print-codex-config` (`adoption/update.md`), which the listed install
  commands do not include; without it the pinned `skill-creator` copy stays enabled beside Codex's bundled one
  (same review).

## Sanitization

The assessors' absolute paths were replaced by placeholders before this copy was written: `<worktree>` for the
read-only worktree at the named revision, `<checkout>` for the main checkout, `<host-private campaign list
2026-09-30>` and `<host-private state>` for paths under the host's private state folder. Repository-relative paths,
the published host id of the receipts under `evidence/hosts/` and loopback addresses are unchanged. A scan of the
written files for scratch paths, home paths, private-state paths, session identifiers, e-mail addresses,
non-loopback addresses and Windows paths found none.
