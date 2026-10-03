# Owner delta review of draft PR 535 at head `7c0df369`, lock `83293867247323c4...`

Review of draft PR #535 at the immutable head `7c0df369f6aaeb263fc25576dbedfbfada74b6ab` (13 commits on main `8fc86119`, the merge of #546), lane `lane:shared`: the OpenHands SDK 1.50.0 lock
`blueprints/runtime-workers/openhands/requirements.lock` with sha256 `83293867247323c4d8fc463096e8a9c01dbee2ada5898112bbbb7d1a62a8b47a`, Linux x86_64, CPython 3.13.15, relocked onto urllib3 2.8.0 and PyJWT 2.15.0. It is a **delta review**
of the lock reviewed in [`evidence/artifacts/openhands-oauthlib-review-535-head6a7b16-20260930/`](../openhands-oauthlib-review-535-head6a7b16-20260930/receipt.json) (lock `383ccc5b`, historical): the two locks differ in exactly two entries, which
the record shows by an independent prediction, by the package closure and by the line-level difference. Claims D1-D11, findings and residuals: `receipt.json`. This is a **scoped
statement for that exact head and lock**; it approves no merge, exception, pin, image, trusted observer or task quality.

Verdict: no blocking finding for the OAuthlib reachability scope. Two P2 findings (a stale workflow binding in the requested receipt, and the category of four excluded compile-input
captures) are in `receipt.json` and need no change to the lock.

| Files | What they are |
| --- | --- |
| `checks/pr535-identity.txt`, `checks/prediction.txt` | head, base, lock hashes, pins, the exact-lock row, the `.github` differences, the independent prediction of the lock |
| `checks/closure-diff-vs-reviewed-383ccc.txt`, `checks/closure-diff-vs-main.txt` | the package closure and the changed lines against the previously reviewed lock and against the lock on main |
| `checks/install-log.txt`, `checks/independent-scan.txt`, `checks/pyjwt-surface.txt`, `checks/pin-sources.txt` | the reproduced hashed installs, the OAuthlib sweep, the PyJWT importers and JWKS client callers, the four advisory files' hashes |
| `checks/osv-exit-codes-and-findings.txt`, `checks/osv-*.json` | OSV-Scanner 2.6.0 (the CI pin): ordinary config exit 0, the empty-config control, the previously reviewed lock (advisory `details` prose removed from the JSON) |
| `checks/osv-split-controls.txt`, `checks/osv-two-new-locks.txt`, `checks/excluded-compile-input-captures.txt` | the workflow's own scan step at the head, the native controls, the two new runtime-worker locks, the four excluded captures |
| `checks/receipt-bindings.txt`, `checks/external-hashes.txt`, `checks/repo-checks-at-head.txt` | the receipt's 62 artifact and 53 command bindings, hashes recomputed from PyPI and codeload, the repository's own checks at the head |
| `checks/commands-as-typed.txt` | how the outputs were produced |
| `scripts/` | the scripts as run (`.txt` copies); `run_delta_outputs.sh.txt` regenerates every output |

Host paths are masks (`<REVIEW-SCRATCH>`, `<REPO>`, `<OSV-BIN>`, `<HOME>`); colour codes are removed; nothing else in an output is edited.
