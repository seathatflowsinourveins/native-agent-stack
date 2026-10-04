# Independent OAuthlib reachability review of draft PR 535 at its corrected head `6a7b16465e50`, lock `383ccc5b87702174...`

Review of draft PR #535 at the immutable head `6a7b16465e50689334d9dd15ff4fed99a9cd7485` (base `f03f41c7f3601532b8635f8f112a3d2731454375`), lane `lane:shared`: the OpenHands SDK 1.50.0 wheel lock
`blueprints/runtime-workers/openhands/requirements.lock` with sha256 `383ccc5b87702174e471732872f002f1621186710402d048acc2b1910306e106`, Linux x86_64, CPython 3.13.15, after the two corrections requested in the earlier record
([`evidence/artifacts/openhands-oauthlib-review-535-20260930/`](../openhands-oauthlib-review-535-20260930/receipt.json), head `bb3d00dc`, historical). Claims, findings, controls and residuals: `receipt.json`. This is a
**scoped proof for that exact head and lock**; it approves no merge, exception, pin or promotion.

| Files | What they are |
| --- | --- |
| `checks/pr535-identity.txt`, `checks/lock-consumers-and-platform.txt` | head, base, lock hashes, pins, the exact-lock test entry with its scope comment and the OSV config diff; who consumes the lock, and the absence of macOS handling |
| `checks/install-log.txt`, `checks/independent-scan.txt` | the reproduced hashed installs (exit 0, pip check clean) and the independent metadata and raw-text OAuthlib sweep |
| `checks/advisory-files-and-helper.txt` | the four advisory-related oauthlib files against the candidate's recorded hashes; the Python 2 helper |
| `checks/osv-exit-codes-and-findings.txt`, `checks/osv-*.json`, `checks/osv-scanner-identity.txt` | OSV-Scanner 2.6.0 (the CI pin): CI form exit 0, the empty-config control exit 1 with exactly the two ids, the base lock with the same two ids |
| `checks/closure-diff-base-vs-head.txt`, `checks/pin-sources.txt` | the closure difference against the base's lock (only the two SDK wheels change) and what constrains click, pypdf and soupsieve |
| `checks/commands-as-typed.txt` | the commands as typed, with times |
| `scripts/` | the scripts as run (`.txt` copies) |

Host paths are masks (`<REVIEW-SCRATCH>`, `<PR535-WORKTREE>`, `<OSV-BIN>`, `<HOME>`, `<REPO>`); colour codes are removed; nothing else in an output is edited.
