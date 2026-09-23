# Preregistration timing correction (fix round, 2026-09-23)

A review finding on this unit's original six receipts showed that none of them
has a `preregistered` field that can be shown to predate its own results:
every receipt, including its `preregistered` text, was first written to disk
*after* the raw command output it describes already existed.

## What the timestamps show

Raw artifact mtimes under `~/codex-ecosystem/state/gap-wave2-20260923/secrets-credentials/`:

- `openbao-fixture/*`, `html-chunks/*`: 21:52 (2026-09-22)
- `gitleaks-runs/gap2-head-ancestry.*`, `gap8-allrefs*`, `gap9-html-chunks*`,
  `gap6-*-commit.log`: 22:01-22:05

Receipt file mtimes in the working tree (all six files):

- earliest 22:04:29 (`gitleaks-headancestry-and-ci-pipeline.json`'s first draft),
  ranging up to 22:17

First commit on this branch (`e932de5`, containing the original six receipts):
22:10:51. No preregistration file existed in the shared state directory, and
no earlier commit records one, before any of this unit's raw command output
was produced.

## What this means

The `preregistered` fields in the original six receipts describe expectations
that were written with the actual results already available to the person
(and, in several cases, the raw output files themselves) writing them. This is
not a blind, ex-ante prediction in the sense the receipt schema and AGENTS.md
science section call for ("write each check's preregistered expectation ...
into the receipt BEFORE running it"). Two of the six read as noticeably fitted
to the already-known outcome:

- `credential-path-containment.json` (gap 0): the original prereg text
  predicts, by name, exactly which `.gitignore` entries are and are not
  covered -- a level of specificity only available after inspecting the
  actual `.gitignore` contents and running `git check-ignore` at least once.
- `gitleaks-html-chunk-coverage.json` (gap 9): the original prereg states in
  advance that any findings will be "classified only by ... statistical
  similarity to the closed set of digest/commit-id JSON key names," which is
  the exact classification method the result section then applies -- i.e. the
  method was described as a prediction after it had already been used to
  produce the result being predicted.

## Correction applied

This is a process/labelling defect in how these six receipts were produced,
not a defect in the underlying commands or their exit codes/output, which are
retained unmodified (per the fix-round rule against re-running a check to
obtain a different outcome). Each of the six receipts now carries an explicit
limitation entry pointing to this file and stating that its `preregistered`
field should be read as a documented expectation/method description written
in the same working session as its results, not as a blind ex-ante prediction.
The two receipts named above additionally have a one-line caveat prepended to
their `preregistered` field noting the specific fitted-to-outcome concern.

No receipt's `preregistered` text itself was rewritten to *pretend* it
predated the results; doing so would replace one false claim with another.
The gap 2 receipt (`gitleaks-headancestry-and-ci-pipeline.json`) is the one
exception where a corrected procedure was run once, with a genuine prereg
(`gap2-fixround-prereg.txt`, written and hashed before the corrected command
executed) -- that was authorized because the underlying finding said the
*procedure itself* (using `-v` instead of `--log-level`) was wrong, not merely
that the prereg's timing was wrong.
