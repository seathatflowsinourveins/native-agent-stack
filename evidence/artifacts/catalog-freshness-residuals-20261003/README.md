# Catalog freshness residual corrections

`pr613-source-review.json` is the original retained, already-sanitized review
checkpoint for PR #613 head `26f09b021e5da36f15cb15ada9032d69d26a238c`, copied
byte-for-byte. Its SHA-256 is
`ca7cc90d94684da52b3b952ecb84c2c15565dcf3ba832a1e09f36bcc7021febc`, matching
the locator previously recorded in that PR's description. It is a bounded
structural/source review of the main reconciliation, not a new run or evidence
that the later eight residual findings were closed. Its original limitations,
failed rebase and worker-observation distinctions remain intact.

The residual implementation follows GitHub's pinned
[multiple-schedule/event.schedule example](https://github.com/github/docs/blob/2bd66de8cea336061c9ea060c9b37385136e6ab3/data/reusables/repositories/actions-scheduled-workflow-example.md#L34)
and the existing workflow at base `56473e4b840f0e6940c031801d866e7e9bf29baf`.
Daily reports use separate Monday/other-day triggers; scheduled proposals keep
the existing opt-in and safety gates and add Monday selection. Manual proposals
remain available. Source and local checks do not prove a future scheduled run.

Correction during preparation: the shared working directory was at
`5cfa2400e3ebb4aefb8419135345c1fa92b05409`, despite its `origin/main` ref naming
the intended base. Its weekly workflow and missing newer files were not current
main. No edit used those stale reads; all edits use an isolated checkout at the
exact base above. The source intake also guessed `scripts/practice_references.py`;
the actual source is `tools/sota-convergence/practice_references.py`, found by
`rg --files` and read before editing. Failed path lookups are not absence claims.

## Actual bounded checks on the integration checkout

Base `56473e4b840f0e6940c031801d866e7e9bf29baf`; the coordinator applied the
worker's retained two-file patch to the separate integration checkout. Its
workflow and test bytes matched the worker snapshot, respectively SHA256
`5c05254b9697920813e84203e58a8e690a8fc1022d67b48ebb9206e19e3a94df`
and `8b47c2850f86d2ac3d6fbf6f83aff5679d8f185011065c0b3f18579a92417229`.
The worker's checkout was not edited. Registration uses the repository's
`scripts/host_receipts.py:register_file`, with only existing changed bindings
and new evidence files selected through `docs/lanes.md`'s protocol.

Native kjanat/actionlint **1.17.0** ran on catalog-freshness,
practice-references-freshness and security-scan: exit0, empty stdout/stderr.
The scoped official Linux amd64 archive matched the release's full SHA256
`620abd485a12b6ab1125b844a876414e1d5bd2af8a3125b27f82b01d0d9d6e5a`.
Version output named1.17.0, go1.27.1 and linux/amd64. The earlier PATH probe
returned1; this proves no global absence. No production installation changed.

Coordinator-observed original commands, each with
`PYTHONDONTWRITEBYTECODE=1` for unittest:

```text
python3 -m unittest tests.test_catalog_freshness_propose tests.test_catalog_freshness_pins tests.test_catalog_freshness_trading
exit0;128tests/OK;57.592s
python3 -m unittest tests.test_adoption_docs_consistency tests.test_github_automation_practice tests.test_practice_references
exit0;79tests/OK;1skip;14.201s
python3 scripts/validate.py
exit0;69components/9319hashedfiles/4profiles/186receipts
git diff --check
exit0
```

These are repository source-contract, synthetic integration and structural
checks. They are not unchanged upstream suites, native GitHub expression
execution, a scheduled Actions run, new provider trials or host acceptance.
The public integration/docs output files retain the exact original native
stdout/stderr bytes; lint output was empty. Registry validation is repeated
after this evidence publication changes its inputs.

The worker's earlier RED had26tests/two source-contract failures; its later
128-test attempt exited1 on publication validation while registration was
outside its ownership; its35-test workflow subset exited0. The initial gh
source fetch returned4 before pinned public curl fetch returned0; actionlint
lookup1, scoped filename discovery2 with inaccessible directories, and Git
commit128 from read-only shared Git metadata remain retained failures. No
tests or evidence were weakened. Original worker outputs remain private with
their recorded hashes; its terminal completion/usage is not inferred from
the delivered patch or a handoff file.

Claude owns the template/position-zero distinction, handbook cadence and
anti-pattern row correction. The coordinator's PR608 handoff requests those
in the pin-move PR. This bounded source change closes the owned residuals;
closure of all eight requires those owner edits and the corrected PR613 body.
