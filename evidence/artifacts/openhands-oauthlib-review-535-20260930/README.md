# Independent OAuthlib reachability review of draft PR 535, candidate lock `8d257833a90ad409...`

Review of draft PR #535 at the immutable head `bb3d00dc1ed493726481d0d3d746f6b0b46ed8bd` (base `f03f41c7f3601532b8635f8f112a3d2731454375`), lane `lane:shared`: the OpenHands SDK 1.50.0 wheel lock
`blueprints/runtime-workers/openhands/requirements.lock` with sha256 `8d257833a90ad4096858d108a427e908a54850dee24d1036d37bd7b5e5d86676`, Linux x86_64, CPython 3.13.15. Claims, findings, controls and residuals: `receipt.json`.
This is a **historical scoped proof for that exact head and lock**; it approves no merge, exception, pin or promotion and is not acceptance of any later closure.

| Files | What they are |
| --- | --- |
| `checks/pr535-identity.txt` | head, base, lock hashes, pins, the exact-lock test entry, the OSV config diff |
| `checks/install-log.txt`, `checks/independent-scan.txt` | the reproduced hashed installs (exit 0, pip check clean) and the independent metadata and raw-text OAuthlib sweep |
| `checks/advisory-files-and-helper.txt` | the four advisory-related oauthlib files against the candidate's recorded hashes; the Python 2 helper |
| `checks/osv-exit-codes-and-findings.txt`, `checks/osv-*.json`, `checks/osv-scanner-identity.txt` | OSV-Scanner 2.6.0 (the CI pin): CI form exit 0, the empty-config control exit 1 with exactly the two ids, the base lock with the same two ids |
| `checks/closure-diff-base-vs-head.txt`, `checks/pin-sources.txt` | the closure difference against the base's lock, and what constrains click, pypdf and soupsieve |
| `checks/commands-as-typed.txt` | the commands as typed, with times |
| `scripts/` | the scripts as run (`.txt` copies) |

Host paths are masks (`<REVIEW-SCRATCH>`, `<PR535-WORKTREE>`, `<OSV-BIN>`, `<HOME>`, `<REPO>`); colour codes are removed; nothing else in an output is edited.
