changes-needed — retained mutants exit 0; six prior regressions pass; both real pnpm locks parse; 100,000-package probes scale approximately linearly.

1. **P1 — [tests/test_osv_lockfile_coverage.py:370](<worktree>/tests/test_osv_lockfile_coverage.py:370): npm v1 `file:` dependencies violate the exact-result-or-None contract.** The reader returns `['file:vendor/next']`; the [pinned Go extractor](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/packagelockjson/packagelockjson.go#L121-L155) emits `next` with version `''`. That Go-reported version is missing from the non-None result. This example still triggers the guard; reject it with `None` or reproduce Go’s normalization.

   Command run:
   ```sh
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; print(t.package_lock_next_pins("""{"lockfileVersion":1,"dependencies":{"next":{"version":"file:vendor/next"}}}"""))'
   ```

2. **nit — [tests/test_osv_lockfile_coverage.py:358](<worktree>/tests/test_osv_lockfile_coverage.py:358): canonical npm workspace links named `next` return `None`.** This satisfies fail-closed behavior, but answers the coverage question: legitimate npm output remains outside the accepted subset, even when the workspace target supplies its version.

   Command run; output `None`:
   ```sh
   rtk python3 -B -c 'from tests import test_osv_lockfile_coverage as t; print(t.package_lock_next_pins("""{"lockfileVersion":3,"packages":{"node_modules/next":{"resolved":"packages/next","link":true},"packages/next":{"name":"next","version":"16.3.5"}}}"""))'
   ```