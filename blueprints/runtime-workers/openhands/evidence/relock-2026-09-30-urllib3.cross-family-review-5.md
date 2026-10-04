changes-needed — retained mutants and `validate.py` exit 0; all 157 unit tests pass.

1. **P1 — [tests/test_osv_lockfile_coverage.py:370](<worktree>/tests/test_osv_lockfile_coverage.py:370): git dependencies still violate the exact-result-or-None contract.** The legacy dependency reader returns the URL or stated version. The pinned Go extractor clears the version when `version` or `resolved` identifies a commit (`packagelockjson.go:125–151`). Its reported `''` is therefore omitted. Reject these entries with `None` or reproduce that normalization.

   Command run; returned the git URL and `['16.3.6']`, respectively:
   ```sh
   rtk python3 -B - <<'PY'
   import json
   from tests import test_osv_lockfile_coverage as t
   url = 'git+https://github.com/vercel/next.js.git#0123456789abcdef0123456789abcdef01234567'
   for dependency in ({'version': url}, {'version': '16.3.6', 'resolved': url}):
       print(t.package_lock_next_pins(json.dumps({'lockfileVersion': 1, 'dependencies': {'next': dependency}})))
   PY
   ```
   Source command:
   ```sh
   rtk proxy git -C <scratch-relock>/scalibr show 3090dbb7aaa2:extractor/filesystem/language/javascript/packagelockjson/packagelockjson.go
   ```

2. **P2 — [evidence/receipts/osv-urllib3-next-20260930.json:170](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:170): the blanket malformed-input rejection claim is false.** Both readers below return `[]`, not `None`. Qualify this claim and the corresponding “canonical-only” claim at [decision line 351](<worktree>/docs/decisions/2026-09-22-github-automation-closure.md:351). These examples establish a documentation error; they do not establish an advisory bypass.

   Command run; output `[]` twice:
   ```sh
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; print(t.pnpm_next_pins("lockfileVersion: 9\ninvalid [\n")); print(t.yarn_lock_next_pins("# yarn lockfile v1\ninvalid [\n"))'
   ```

3. **P2 — [receipt:98](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:98), [receipt:159](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:159), [research.md:432](<worktree>/blueprints/runtime-workers/openhands/research.md:432): retained PyJWT output does not support three details.** Section J omits the continuation lines establishing the **non-object JWKS** condition and **non-numeric exp/nbf/iat** behavior. Its importer search expressly excludes `google`, so it also cannot establish the broader assertion that the module “has no importer in the venv,” or that this is the advisory’s only call path.

   Command run:
   ```sh
   rtk rg -n 'fetch_data|Raise the documented|importers of google' blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.txt
   ```
   Output retains only “now raises,” “instead of leaking a,” and the search heading “outside the google package.”

4. **P2 — [receipt:4](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:4), [receipt:100](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:100), [receipt:176](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:176): additional provenance claims lack retained support.** These are PyJWT joining at **16:57Z**; the SDK setting being specifically at **pyproject.toml line 8** and `exclude-newer-span P7D` appearing in its lock; and the precise reviewer invocation, model/effort and native-login route. Section B supports the seven-day setting, and the review files support their findings, but neither establishes these additional details. The model/effort assertion is repeated at [decision line 349](<worktree>/docs/decisions/2026-09-22-github-automation-closure.md:349).

   Command run; exit 1, no matches:
   ```sh
   rtk rg -n '16:57|exclude-newer-span|P7D|non-object|non-numeric|codex exec|native Codex login' blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3*
   ```

5. **nit — [receipt:8](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:8) and [receipt:171](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:171): stale count and test name.** There are **four**, not two, retained reviews. `test_the_readers_run_in_linear_time_on_whitespace_heavy_input` does not exist; the current name ends in `_on_large_input`.

   Command run:
   ```sh
   rtk python3 -B - <<'PY'
   import json, re
   from pathlib import Path
   from tests import test_osv_lockfile_coverage as t
   r = json.loads(Path('evidence/receipts/osv-urllib3-next-20260930.json').read_text())
   print('reviews:', len([k for k in r['independent_review'] if re.fullmatch(r'review_\d+', k)]))
   print('stated two:', 'two read-only' in r['evidence_class'])
   print('missing tests:', [n for n in re.findall(r'test_[a-z_]+', r['next_pin_guard']['tests']) if not hasattr(t.AllowedLockTests, n)])
   PY
   ```

6. **nit — [.github/osv-scanner.toml:58](<worktree>/.github/osv-scanner.toml:58): qualify the reference-search claim.** “git grep finds it only” describes the retained search at `11227bfd`, excluding the artifact directory. At HEAD, additional matches include the guard, mutant script, receipt and ignore itself. State that revision and exclusion explicitly.

   Command run:
   ```sh
   rtk proxy git grep -l -F macos-application-20260924/variant/pnpm-lock HEAD -- . ':(exclude)evidence/artifacts/macos-application-20260924'
   ```