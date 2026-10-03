changes-needed

1. **P1 — [tests/test_osv_lockfile_coverage.py:210](<worktree>/tests/test_osv_lockfile_coverage.py:210): valid pnpm YAML can hide affected packages.** Inline records return `[]`; quoted `packages`/field keys, different indentation and trailing field comments also bypass detection. SCALIBR decodes YAML and applies the record’s own name/version, reporting `next@16.3.5`. Unsupported syntax must return `None`, not an empty result. [Pinned Go source](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/pnpmlock/pnpmlock.go#L184)

   Command run; output: `[] []`:

   ```bash
   rtk python3 -B - <<'PY'
   from pathlib import Path
   from unittest.mock import patch
   from tests import test_osv_lockfile_coverage as t
   s = "lockfileVersion: 9.0\npackages:\n  file:vendor/next: {name: next, version: 16.3.5}\n"
   with patch.object(Path, "read_text", return_value=s):
       print(t.npm_next_pins("pnpm-lock.yaml"), t.npm_next_findings([{"path": "pnpm-lock.yaml"}], allowed={}))
   PY
   ```

2. **P1 — [tests/test_osv_lockfile_coverage.py:294](<worktree>/tests/test_osv_lockfile_coverage.py:294): JSON decoding differences silently discard affected packages.** Go’s `json.Unmarshal` merges repeated map fields and matches struct fields case-insensitively. Python discards the earlier duplicate object and ignores `Packages`. Both mutants below return `[]`; Go reports `next@16.3.5`. Repeated `dependencies` objects have the same bypass. [Go decoder call](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/packagelockjson/packagelockjson.go#L337), [destination map fields](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/internal/dependencyfile/packagelockjson/packagelockjson.go#L19)

   ```bash
   rtk python3 -B - <<'PY'
   from tests import test_osv_lockfile_coverage as t
   for s in [
       '{"lockfileVersion":3,"packages":{"node_modules/next":{"version":"16.3.5"}},"packages":{}}',
       '{"lockfileVersion":3,"Packages":{"node_modules/next":{"version":"16.3.5"}}}'
   ]:
       print(t.package_lock_next_pins(s))
   PY
   ```

3. **P2 — [tests/test_osv_lockfile_coverage.py:407](<worktree>/tests/test_osv_lockfile_coverage.py:407): the introduced boundary mishandles prereleases.** `16.2.0-canary.1` precedes `16.2.0`, but the guard reports it as affected. The comparison handles prereleases only at the fixed boundary.

   Command run; output incorrectly says the ignore hides this version:

   ```bash
   rtk python3 -B - <<'PY'
   from pathlib import Path
   from unittest.mock import patch
   from tests import test_osv_lockfile_coverage as t
   s = "lockfileVersion: 9.0\npackages:\n  next@16.2.0-canary.1: {}\n"
   with patch.object(Path, "read_text", return_value=s):
       print(t.npm_next_findings([{"path": "pnpm-lock.yaml"}], allowed={}))
   PY
   ```

4. **P2 — [tests/test_osv_lockfile_coverage.py:272](<worktree>/tests/test_osv_lockfile_coverage.py:272): an uninstalled optional peer becomes an affected pin.** The global dependency regex returns `['16.3.5']` below and causes an inventory finding. Go reports only `plugin@1.0.0`: it iterates package records, not their peer declarations. [Pinned Go source](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/pnpmlock/pnpmlock.go#L172)

   ```bash
   rtk python3 -B - <<'PY'
   from tests import test_osv_lockfile_coverage as t
   s = "lockfileVersion: 9.0\npackages:\n  plugin@1.0.0:\n    peerDependencies:\n      next: 16.3.5\n    peerDependenciesMeta:\n      next:\n        optional: true\n"
   print(t.pnpm_next_pins(s))
   PY
   ```

5. **P2 — [tests/test_osv_lockfile_coverage.py:373](<worktree>/tests/test_osv_lockfile_coverage.py:373): Yarn’s root-workspace exclusion was dropped.** This returns `['16.3.5']` and triggers a finding for the project itself. Go explicitly skips headers ending in `@workspace:.":`, so it reports no `next` here. [Pinned Go source](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/yarnlock/yarnlock.go#L234)

   ```bash
   rtk python3 -B - <<'PY'
   from tests import test_osv_lockfile_coverage as t
   s = '__metadata:\n  version: 8\n"next@workspace:.":\n  version: 16.3.5\n'
   print(t.yarn_lock_next_pins(s))
   PY
   ```

6. **P2 — [tests/test_osv_lockfile_coverage.py:330](<worktree>/tests/test_osv_lockfile_coverage.py:330), [line 350](<worktree>/tests/test_osv_lockfile_coverage.py:350): nesting raises uncaught `RecursionError`.** Both readers crash at 1,200 levels instead of returning `None`. The corresponding Go traversal follows nested dependencies and aliases to `next@16.3.5`. [Go dependency traversal](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/packagelockjson/packagelockjson.go#L95), [Go alias traversal](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/yarnlock/yarnlock.go#L115)

   Command run; both outputs are `RecursionError`:

   ```bash
   rtk python3 -B - <<'PY'
   from tests import test_osv_lockfile_coverage as t
   cases = {
       "package-lock.json": '{"lockfileVersion":1,"dependencies":' + '{"p":{"dependencies":' * 1200 + '{"next":{"version":"16.3.5"}}' + '}}' * 1200 + '}',
       "yarn.lock": '# yarn lockfile v1\n' + 'alias@npm:' * 1200 + 'next@^16.3.0:\n  version "16.3.5"\n',
   }
   for name, s in cases.items():
       try:
           print(name, t.NPM_NEXT_READERS[name](s))
       except RecursionError:
           print(name, "RecursionError")
   PY
   ```

Execution checks: the retained mutant script exits at its stale three-argument `affected` call. Redirecting only its two R3 calls to `npm_affected` in memory lets every retained mutant complete; all 17 `AllowedLockTests` pass. The earlier quoted-key, package-record, alias, name/path, integer-version, whitespace, canary and build-metadata cases were exercised.

The 49-entry real inventory returns `[]` in **0.0046 s**. Synthetic locks containing 100,000 packages correctly distinguish fixed and affected pins: approximately **0.39 s pnpm**, **0.09 s package-lock**, **0.10 s Yarn**. The 12 MB whitespace case takes **0.95 s**. Other executed probes—including multiple `@`, intermediate 9.x versions, link/bundled records, file/git versions, Yarn header/version variants and empty keys—found no additional escape beyond those above.