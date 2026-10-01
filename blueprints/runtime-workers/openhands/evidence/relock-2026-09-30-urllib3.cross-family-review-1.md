changes-needed

1. **P1 — [tests/test_osv_lockfile_coverage.py:189](<worktree>/tests/test_osv_lockfile_coverage.py:189): the pnpm reader accepts partial parses.** An unquoted fixed key masks an affected quoted key: the reader returns only `16.3.6`, and all 32 coverage tests pass. Other mutants passing undetected were mixed indentation, `/next/16.3.5` keys, dependency-only pins—including in an additional lock—and unknown `lockfileVersion` values. Canonical affected keys, a second canonical lock, CRLF, and a sole quoted affected key were caught. This disproves the receipt’s “strictly and fail closed” claims at lines 12 and 109.

   Command:
   `rtk python3 -B -c 'from pathlib import Path; from unittest.mock import patch; from tests.test_osv_lockfile_coverage import pnpm_next_pins; s="lockfileVersion: 9.0\npackages:\n  next@16.3.6: {}\n  \"next@16.3.5\": {}\n"; p=patch.object(Path,"read_text",return_value=s); p.start(); print(pnpm_next_pins(Path("pnpm-lock.yaml")))'`
   Returned `['16.3.6']`.

2. **P1 — [tests/test_osv_lockfile_coverage.py:507](<worktree>/tests/test_osv_lockfile_coverage.py:507): other npm lock formats bypass the guard entirely.** Injecting `next@16.3.5` into the existing WSL `package-lock.json` passes all 32 coverage tests; an additional affected `yarn.lock` also passes the targeted guard. All 49 current inventory locks were checked: there is no additional affected Next pin today, but this global suppression leaves future regressions unchecked. The decision paragraph’s claim at line 338 that the guard protects “any other lock” contradicts both this behavior and receipt line 12.

   Command:
   `rtk python3 -B -c 'from pathlib import Path; from unittest.mock import patch; from tests import test_osv_lockfile_coverage as t; original=Path.read_text; p=patch.object(Path,"read_text",lambda path,*a,**k: "{\"lockfileVersion\":3,\"packages\":{\"node_modules/next\":{\"version\":\"16.3.5\"}}}" if path.name=="package-lock.json" else original(path,*a,**k)); p.start(); t.AllowedLockTests("test_only_the_allowed_pnpm_lock_pins_an_affected_next").debug(); print("affected package-lock: PASSES")'`
   Returned `affected package-lock: PASSES`.

3. **P2 — [tests/test_osv_lockfile_coverage.py:515](<worktree>/tests/test_osv_lockfile_coverage.py:515): the affected-version predicate omits the introduced boundary.** It rejects unaffected Next versions below `16.2.0`; the `16.1.9` lock mutant failed. Check the advisory’s full interval.

   Command:
   `rtk python3 -B -c 'from tests.test_osv_lockfile_coverage import affected,IGNORE_SCOPES; print(affected("16.1.9",IGNORE_SCOPES["GHSA-vcvr-r3jv-pc5j"]["fixed"]))'`
   Returned `True`.

4. **P2 — [relock-2026-09-30-urllib3.txt:100](<worktree>/blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.txt:100): section E lacks the retained reports or producing wrapper needed to substantiate its scan summaries.** Consequently, receipt lines 22 and 91–95 lack auditable command/output support for the exact baseline findings, clean changed scan, and empty-config control. The displayed commands contain placeholders or “the same command”; the JSON summaries and wrapper exits are not output produced by the shown scanner command. The header’s “output as printed” claim is also inaccurate: section F truncates the snapshot keys at lines 132 and 136.

   Commands:
   `rtk git ls-files '*osv-main.json*' '*osv-after.json*' '*osv-after-noconfig.json*'`
   returned nothing.
   `rtk rg -n 'scan source|osv-(main|after)|scan exit|wrapper|as printed|without hashes' blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3*`
   found these representations only in the narrative transcript.

5. **P2 — [osv-urllib3-next-20260930.json:7](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:7): several historical assertions have no retained supporting observation.** These are the c5 request and its contents; “no live owner”/“no session claims it”; the reported PR #540 run/job/failure particulars at lines 17–21; and the first local scan allegedly showing only two urllib3 advisories at line 22. The CI information is explicitly secondhand, but remains unverified. Git history establishes the artifact’s commit history, not current session ownership. The decision repeats the unsupported ownership assertion at lines 336 and 340.

   Command:
   `rtk git grep -n -E 'sota-default-harness-setup|36733726923|109949820112|first local scan' HEAD -- .`
   returned only the new receipt and decision assertions.

6. **P2 — [2026-09-22-github-automation-closure.md:329](<worktree>/docs/decisions/2026-09-22-github-automation-closure.md:329): the exact urllib3 upload date is unsupported.** Neither the receipt nor retained commands report `2026-09-15` as its upload date. Retain the release metadata supporting that date or remove the exact assertion.

   Command:
   `rtk git grep -n -E 'urllib3.*uploaded|uploaded.*urllib3' HEAD -- .`
   returned only this decision sentence.

7. **P2 — [2026-09-22-github-automation-closure.md:326](<worktree>/docs/decisions/2026-09-22-github-automation-closure.md:326): GitHub publication is conflated with the retained OSV timestamp.** Section A records OSV data only. The tree already records verification of this Next advisory on September 25, so it does not support calling September 30 its GitHub publication date. The same attribution appears in [.github/osv-scanner.toml:56](<worktree>/.github/osv-scanner.toml:56).

   Command:
   `rtk git grep -n -E '2026-09-25|2026-09-22T17:15:10Z|GHSA-vcvr-r3jv-pc5j' HEAD -- blueprints/convergence-practice/application-delivery/history/recipe-revisions.json`
   returned the earlier advisory verification and security bump.