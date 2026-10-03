# omniroute@3.8.51 from npm: install, boot smoke and provenance, 2026-09-30

Qualification of the published npm package (not of the running gateways) as a candidate for the `omniroute` pin of `manifests/stack.json`. Claim, limitations and
values: [`evidence/receipts/omniroute-3851-npm-qualification-20260930.json`](../../../evidence/receipts/omniroute-3851-npm-qualification-20260930.json). The pin is not moved here. Every file under `checks/` is an output as returned, except for the edits listed below;
`scripts/*.txt` are the scripts as they ran, with host paths replaced by named placeholders.

| File | What it is | Class |
| --- | --- | --- |
| `checks/npm-view-20260930.json` | `npm view` of the version: integrity, shasum, tarball URL, engines (no `gitHead` was returned) | registry read |
| `checks/npm-pack-summary-20260930.json` | the JSON `npm pack --json` returned, without its 26,761-entry file list | registry read |
| `checks/tarball-digests-20260930.txt` | sha1, sha256 and sha512 of the file `npm pack` wrote, recomputed at the printed time, and the comparison with the registry's values | our check |
| `checks/install-steps-20260930.txt` | the install script's stamped lines and its directory listings as printed (the two JSON bodies are replaced by a line naming where they are published) | our check |
| `checks/npm-install.log.txt`, `checks/npm-rebuild.log.txt` | the outputs of `npm install` (ERESOLVE peer-dependency warnings, one deprecation notice for `prebuild-install@7.1.3`, a notice that seven packages' install scripts were not run because `allow-scripts` did not cover them, and `added 1153 packages in 2m`) and of the recipe's `npm rebuild` with its allowlist, which ran them (`rebuilt dependencies successfully`) | our check |
| `checks/smoke-summary-20260930.txt`, `checks/smoke-serve-1-excerpt-20260930.txt` | the boot, restart and stop smoke's summary and the first start's matching log lines (long tokens masked by the script); the second start's excerpt was empty and is not published | our check |
| `checks/npm-attestation-20260930.json` | the two attestation statements the registry serves for the version, decoded (no signature or certificate), with the subject digest compared to the tarball's (the probe's argument is the sha512 of `checks/tarball-digests-20260930.txt` in hex) | our check (a read, not a verification) |
| `checks/audit-signatures-20260930.txt` | the output of the audit script: `npm audit signatures` (text) on a throwaway project that installed the package as a dependency | npm's own verification |
| `checks/audit-signatures-summary-20260930.json` | the counts and omniroute's own entry from `npm audit signatures --json --include-attestations` (certificates and log data left out), run once more in the same project | npm's own verification, summarized by our script |
| `checks/audit-signatures-global-refused-20260930.txt` | `npm audit signatures --global` on the smoke-tested prefix: refused (`EAUDITGLOBAL`, exit 1), which is why the audit ran in a throwaway project | npm's own behavior |
| `checks/carry-presence-20260930.json` | counts of the alpha/search route files and of the affinity function in the installed package | our check |
| `scripts/` | `install_npm.sh.txt`, `smoke_npm.sh.txt`, `smoke_inner.sh.txt`, `npm_attestation_probe.py.txt`, `carry_presence_check.py.txt`, `audit_signatures.sh.txt`, `audit_json_summary.py.txt`, `audit_global_refused.sh.txt` | our tools, not upstream |

**Edits to returned outputs** (nothing else differs): the user and group name in directory listings is `<user> <group>`; the smoke's `cwd=` path is `<throwaway directory>/cwd`;
the two JSON bodies inside the install steps are omitted with their line ranges stated; the npm pack JSON lost its file list (its `entryCount` stays). The long-token masking in the
serve excerpt was done by the smoke script itself.

**First smoke run.** A first run of `scripts/smoke_npm.sh.txt` with a wrong prefix argument failed (serve exit 127, an sqlite open error) and its throwaway directory and logs were
deleted, so nothing of it is published; the receipt says so.
