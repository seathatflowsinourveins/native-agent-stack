changes-needed

1. **P1 — [tests/test_osv_lockfile_coverage.py:203](<worktree>/tests/test_osv_lockfile_coverage.py:203): pnpm still accepts partial parses.** Original P1-1’s quoted-key mutant is caught, but package metadata can hide the affected version. Tarball entries, scoped/renamed entries with `name: next`, and `next@16.3.6` with `version: 16.3.5` escape detection. Injecting these into the live lock leaves all 34 coverage tests passing.

   This matters for plausible tarball or local-package dependencies: the scanner’s pinned [scalibr source at 3090dbb7aaa2](https://github.com/google/osv-scalibr/blob/3090dbb7aaa2/extractor/filesystem/language/javascript/pnpmlock/pnpmlock.go#L184) gives explicit `name` and `version` precedence over the key.

   Command run:
   ```bash
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; print(t.pnpm_next_pins("lockfileVersion: 9.0\npackages:\n  next@https://registry.npmjs.org/next/-/next-16.3.5.tgz:\n    name: next\n    version: 16.3.5\n"))'
   ```
   Returned `[]`, exit 0.

2. **P1 — [tests/test_osv_lockfile_coverage.py:242](<worktree>/tests/test_osv_lockfile_coverage.py:242) and [line 272](<worktree>/tests/test_osv_lockfile_coverage.py:272): npm and Yarn aliases bypass the guard.** Original P1-2 is only partially repaired. Berry `"foo@npm:next@16.3.5"`, its scoped equivalent, classic Yarn aliases, and package-lock/npm-shrinkwrap v1 aliases return `[]`. The npm v1 mutant also passes all 34 coverage tests.

   These are plausible future locks. The pinned extractor explicitly normalizes [npm aliases](https://github.com/google/osv-scalibr/blob/3090dbb7aaa2/extractor/filesystem/language/javascript/packagelockjson/packagelockjson.go#L113) and [Yarn aliases](https://github.com/google/osv-scalibr/blob/3090dbb7aaa2/extractor/filesystem/language/javascript/yarnlock/yarnlock.go#L128) to npm `next`.

   Commands run:
   ```bash
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; import json; print(t.package_lock_next_pins(json.dumps({"lockfileVersion":1,"dependencies":{"foo":{"version":"npm:next@16.3.5"}}})))'
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; print(t.yarn_lock_next_pins("__metadata:\n  version: 8\n\n\"foo@npm:next@16.3.5\":\n  version: 16.3.5\n  resolution: \"next@npm:16.3.5\"\n"))'
   ```
   Both returned `[]`, exit 0. Additional package-lock divergences: `node_modules/next` with an empty `name`, and `vendor/next` without an explicit name, also escape while OSV’s basename fallback identifies `next`. These are less common workspace/imported-lock cases.

3. **P2 — [tests/test_osv_lockfile_coverage.py:192](<worktree>/tests/test_osv_lockfile_coverage.py:192): the dependency-block regex backtracks badly.** Three whitespace-heavy mapping lines after `next:` cause rapidly increasing runtime: approximately 0.027 seconds at 40-space indentation, 0.466 seconds at 80, and over two seconds at 160. A 604-byte input exhausted the bounded probe. No large lock is necessary.

   Command run:
   ```bash
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; import signal; s="lockfileVersion: 9.0\npackages:\n  foo@1.0.0:\n    peerDependenciesMeta:\n      next:\n"+" "*160+"optional: true\n"+" "*160+"injected: true\n"+" "*160+"other: true\n"; print("bytes",len(s),flush=True); signal.alarm(2); print(t.pnpm_next_pins(s))'
   ```
   Printed `bytes 604`; terminated by signal 14, exit 142.

4. **P2 — [tests/test_osv_lockfile_coverage.py:201](<worktree>/tests/test_osv_lockfile_coverage.py:201) and [line 330](<worktree>/tests/test_osv_lockfile_coverage.py:330): legitimate unaffected locks are rejected.** Integer `lockfileVersion: 9` returns `None`, although OSV parses that version numerically. Fixed `16.3.6+build.1` and above-fix `16.4.0-canary.1` are classified as affected. The latter matters for plausible Next canary adoption. These are future false positives; none occurs in the current inventory.

   Command run:
   ```bash
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; print(t.pnpm_next_pins("lockfileVersion: 9\npackages:\n  next@16.3.6: {}\n")); s=t.IGNORE_SCOPES[t.NEXT_ADVISORY]; print({v:t.affected(v,s["fixed"],s["introduced"]) for v in ("16.3.6+build.1","16.4.0-canary.1")})'
   ```
   Returned `None` and `True` for both versions, exit 0.

5. **P2 — [receipt:7](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:7): unsupported historical assertions remain.** P2-5 is partially repaired: the ownership statement is now bounded to inspected records, and the original first-scan assertion was removed. Retained observations still do not establish:

   - The c5 request, PR #540 failure, run `36733726923`, or job `109949820112`—lines 7 and 15–22 explicitly acknowledge missing evidence.
   - That the advisory set grew **while this change was being built**, line 13; the retained scans already contain all four.
   - The urllib3 tag object and commit hashes, line 83, explicitly described as unretained.
   - Current issue #518 ownership or PR #535’s current draft status; the tree contains narrative assertions and an earlier PR-head observation.

   Commands run:
   ```bash
   rtk git grep -l -E '36733726923|109949820112|sota-default-harness-setup' -- .
   rtk git grep -n -E '2f980b433a89399ad5efd72e7f6da04e667ea287|b1d30ab61fe0db8f11092805e8c5ac43e091064a' -- .
   ```
   The first found only the receipt and decision; the second only the receipt’s assertion. Both exited 0.

6. **P2 — [decision:325](<worktree>/docs/decisions/2026-09-22-github-automation-closure.md:325), [osv-scanner.toml:49](<worktree>/.github/osv-scanner.toml:49), and [receipt:78](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:78): GitHub’s first-listing date remains unsupported.** P2-7’s field attribution is corrected, but “listed … since” still turns a review timestamp into a first-listing date. The retained record establishes OSV publication and GitHub review, not when GitHub first listed it.

   Command run:
   ```bash
   rtk proxy jq '[.results[].packages[].vulnerabilities[] | select(.id == "GHSA-vcvr-r3jv-pc5j") | {published, github_reviewed_at: .database_specific.github_reviewed_at, github_published_at: .database_specific.github_published_at}]' blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.osv-main.json
   ```
   Returned publication/review `2026-09-30T14:48:30Z` and `github_published_at: null`, exit 0.

   Also, [the reason at line 58](<worktree>/.github/osv-scanner.toml:58) incorrectly says the live lock is scanned “without an ignore.” The workflow applies the same global config to every lock; that lock currently has no affected version. Verified with `rtk git grep -n -E 'osv-scanner|ca69b3d3|mapfile -t lockfiles|scan source' -- .github/workflows/security-scan.yml`.

7. **nit — [transcript:3](<worktree>/blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.txt:3): the exact-command header still overclaims.** P2-4’s reports, wrapper, hashes and unabridged snapshot keys are repaired. However, line 95 remains `diff <(committed lock without hashes) <(new lock without hashes)`, without the producing commands.

   Command run:
   ```bash
   rtk rg -n '^# A line|committed lock without hashes' blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.txt
   ```
   Returned lines 3 and 95, exit 0.

8. **nit — [receipt:85](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:85) and [line 141](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:141): two numerical descriptions need correction.** The exact seven-day cutoff is `2026-09-22T19:29:36.253420Z`, not `19:29:36Z`; rounding conservatively gives `19:29:37Z`. The script exercises **14 failing mutants plus one boundary assertion**, not 15 mutants each failing a rule: R3 directly checks the repaired predicate.

   Commands run:
   ```bash
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; from datetime import datetime,timedelta; print((datetime.fromisoformat("2026-09-15T19:29:36.253420+00:00")+timedelta(days=7)).isoformat())'
   rtk python3 -B blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.guard-mutants.py.txt
   ```
   Both exited 0.

Other mutant results:

| Mutants | Result and significance |
|---|---|
| Standard pnpm catalogs/overrides, importer aliases, tabs, CRLF, unquoted `9.0`, affected build/prerelease versions, exact peer pin | Detected. |
| Package-lock v2 containing only legacy `dependencies` | Fails closed with `None`; no bypass. |
| V2 legacy dependencies alongside empty `packages` | Passes, but OSV also selects the empty map; not an additional suppression bypass. |
| Qualified/selected overrides, quoted `version`, flow-style importer entries without package records | Missed; OSV reads package records rather than these declarations. Complete conventional locks expose the resolved package separately. |
| Malformed pnpm input | Passes this guard, contradicting the strict-parse claim; OSV parsing is a separate failure path. |
| Unknown npm filename | Skipped by `npm_next_findings`; current inventory/parser checks reject it. |
| V3 scoped alias with `name: next` | Detected. A genuine differently named package correctly passes. |

**First-review disposition:** P2-3 and P2-6 are repaired. P1-1, P1-2, P2-4, P2-5 and P2-7 retain the residuals above.

Executed `rtk python3 -B -m unittest tests.test_osv_lockfile_coverage tests.test_runtime_worker_openhands`: **155 tests, exit 0**. `rtk python3 scripts/validate.py`: **exit 0**. All 49 inventory locks pass; the pnpm versions are exactly **16.3.5** and **16.3.6**. Retained report hashes and summaries match, including 49 scanned paths and eight filtered vulnerabilities. No active stale helper reference or mismatched failure message was found; remaining old references belong to the preserved first review.