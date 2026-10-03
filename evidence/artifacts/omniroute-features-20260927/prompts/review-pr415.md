Cross-family code review of pull request #415 in seathatflowsinourveins/native-agent-stack ("Token report: retain selected upstream usage, status and cache reports beside each tool's row"). The PR head is checked out read-only at $SCRATCH/wt-report (branch claude/token-report-upstream-reports-20260927). Inspect the change with `git -C $SCRATCH/wt-report diff origin/main...HEAD` and read the surrounding code in tools/token-report/token_manifest.py, test_token_manifest.py and README.md.

Review for:
- correctness bugs: validation gaps, refresh-flow ordering, how coverage_matrix rows are annotated, snapshot semantics in Ledger.native_views, counter_decreased with a null saved;
- the invariant that a report never carries a savings value and is never summed;
- failure handling: nonzero exit, parse errors, timeouts;
- security and privacy: argv from private config, curl to loopback, the README's warning about per-account routes;
- consistency with the file's existing style and accounting rules;
- test adequacy: do the 4 new tests fail without the change, and does anything important go untested?

You may run the tests in the shell, which is read-only: `python3 -m unittest discover -s $SCRATCH/wt-report/tools/token-report -p 'test_*.py'` (the tests write only into temporary directories). Cite file:line for every finding. Rate each finding high/medium/low/nit. Return only the JSON object.