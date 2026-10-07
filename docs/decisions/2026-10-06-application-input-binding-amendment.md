---
status: accepted
date: 2026-10-06
decision-makers: command center
---

# Preserve application trial inputs when production locks are relocked

The exact-head review of PR #765 at 67c6594d2 found two required-check blockers:
the application convergence records still bound the old UV bytes at the live
path, and the recipe ledger's PNPM current binding still named the old digest.
The original local relock checks omitted these downstream checks. This repair
serves the north-star action of unblocking the landing queue while retaining
the original trial's evidence and input bytes.

Follow the existing path-only amendment and recipe-supersession conventions.
Retain the original UV and PNPM bytes from ecfa1127 under suffixed history
filenames; retain both pre-amendment experiment files byte-for-byte as dated
non-executable source snapshots. Amend only each canonical convergence record's
UV source path. Its frozen digest, observations, commands, outputs and usage
remain unchanged. The ledger dates the amendment and protects original/current
bindings, ordered path relocations, the pre-amendment snapshot and superseded
recipe revisions with hashes. The experiment's earlier PNPM relocation remains.

This is a metadata/input-storage amendment. It does not qualify the original
full-stack run against Mako 1.4.2 or source-map-js 1.2.2. Their production-lock
qualifications remain the separately recorded package/install/build checks in
the relock receipts. Original receipt.json, freeze.json, prior experiment
history, macOS lock and captured trial locks remain byte-identical.

Updating old frozen digests to the new production lock was rejected: it would
attribute dependencies to a trial that did not use them. Removing a declared
record, weakening the convergence validator or adding a validation exception
was also rejected. Both canonical records remain declared and validated; their
retained original inputs supply exactly the original bytes.

The historical lock filenames follow existing frozen-history conventions and
are not normal installer/scanner basenames. No new scanner inventory exception
or advisory ignore is introduced. They are archival input bytes, not current
runtime dependencies. Full required-check acceptance remains separate from
local integrity/fixture checks.

Overturn this binding amendment if the original snapshot/input hashes cannot
be reproduced, the path-only byte comparison changes anything else, or a
future independently accepted trial intentionally adopts the newer inputs.
That future trial needs its own record rather than a historical receipt edit.

Sources:

- [Original path-only relocation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c96c2555c2d84683d9e519623354c814aeb6a584/blueprints/convergence-practice/application-delivery/history/recipe-revisions.json#L121), PR #252.
- [Recipe supersession](https://github.com/seathatflowsinourveins/native-agent-stack/blob/798ac445307e2cd8eba6e74d7722ac0e16da02c7/blueprints/convergence-practice/application-delivery/history/recipe-revisions.json#L99), PR #587.
- `native-agent-stack@c1300c15b42f1a6643f3dc4172f40c01d99abdcd:blueprints/convergence-practice/application-delivery/test_portability.py:100-143` checks original/current mappings and path-only byte equality.
- Same pin, `scripts/validate_convergence.py:60-71,203-243` checks every declared frozen input; `contract.schema.json:6` in the convergence blueprint preserves the existing schema.
- Same pin, `tests/test_osv_lockfile_coverage.py:36-43` defines tracked active lockfile names; `tests/test_frozen_macos_variant_no_use.py:30` preserves the captured macOS boundary.
