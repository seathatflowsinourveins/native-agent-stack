The E2E task is selected from Inspect Evals GAIA v0.22.0, validation split,
`gaia-benchmark/GAIA` revision `682dd723ee1e1697e00360edccf2366dc8418dd9`.
Source: https://github.com/UKGovernmentBEIS/inspect_evals/blob/v0.22.0/src/inspect_evals/gaia/gaia.py

Before a host run, freeze an actual no-attachment validation ID and retain the
permitted dataset bytes. `run-e2e.sh ID` supplies Inspect's formatted question
unchanged to the native DeerFlow embedded client. The adapter does not see the
answer target. Asset-bearing or absent IDs fail before worker launch.

Inspect's unchanged `gaia_scorer` provides the verdict and metrics. Native tool
calls/results prove skills activation separately: successful reads of both
listed `search-first` and `verification-before-completion` SKILL.md files are
required for skills acceptance. Mere listing or describe_skill metadata does not
prove activation. Missing activation stays false even when GAIA answers correctly.

The previous round-1 release-diff task is retired. `expected.json` is retained only
as historical input to the round-1 evidence; neither the worker nor grader reads
it in this recipe. New quality claims must reference Inspect's native .eval log.
