You are an independent reviewer. Read-only. Review the wave-2 gap receipts in
evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/
(the numbered *.json receipts, results.json, README.md and the raw/ files they cite)
and the helper scripts in blueprints/gap-wave2-20260923/us-equities__data-quality-orchestration/.
Also review the diff of commit range 41d39b3..HEAD for blueprints/us-equities/data/,
blueprints/us-equities/hosting/README.md and tests/test_promotion_gate.py.

For each receipt check:
1. Does each claimed result appear in the cited raw file (quote it)? Flag any number or status that the raw file does not support.
2. Is the outcome (settled / advanced / covered_elsewhere / not_settled / deferred) justified? "settled" requires every clause of gap_text closed and every arm of next_check (or a stronger check) executed. Flag overclaims.
3. Is preregistration.written_at earlier than checked_at and than the raw outputs' timestamps?
4. Could each probe detect the failure it reports as absent?
5. Any personal paths, secrets or UUIDs committed?
For the code diff: any bug in the new DuckdbInputRuns test, the lock change, or the helper scripts that would make a reported result wrong?

Reply with a numbered list of findings, each with file, severity (blocking / should-fix / nit) and the exact evidence. If none, say "no findings". Keep it under 600 words.
