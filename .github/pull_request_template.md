<!--
Scope and base commit
-->
### Scope

- What this PR changes, in one or two sentences:
- Base commit: `<sha>`
- Lane: exactly one of `lane:foundation`, `lane:trading` or `lane:shared`, matching the PR label; a `lane:shared` PR needs the other lane's acknowledgement before merge ([docs/lanes.md](../docs/lanes.md)):
- Owned paths touched:

### Evidence-class table

List each material claim with its evidence class. Classes: `native_proven`
(actual execution on a host, receipt retained), `local_integration`,
`synthetic` (fixture), `source_review`. Never label a claim a class stronger
than what was actually run.

| Claim | Evidence class | Command / receipt |
| --- | --- | --- |
| | | |

### Local commands run

```
$ <exact command>
<exit code / key output>
```

### Decision record

Path to the dated decision record for this change (if any), naming the
evidence, alternatives considered and the comparison that would overturn it:

### Host evidence

Only relevant when this PR adds or changes files under `evidence/hosts/`. See
[`docs/contributing-evidence.md`](../docs/contributing-evidence.md).

- [ ] `python3 scripts/host_receipts.py validate` passes for every new/changed receipt.
- [ ] Independent review is recorded (`scripts/host_receipts.py review`) or explicitly requested in this PR.
- [ ] No `platform_status` change is made from a host receipt alone; a platform status flip still needs the matrix rule in `docs/component-evidence-matrix.md`.

### Checklist

- [ ] New/changed GitHub Actions are pinned to a full commit SHA with a
      version comment (no floating tags).
- [ ] New/changed workflows declare top-level `permissions: contents: read`
      (or a narrower, explicitly justified addition).
- [ ] No secrets are printed, logged or committed; no new required secret was
      added without a documented owner.
- [ ] No new paid hosting, subscription or billing surface was introduced.
- [ ] Peer-owned untracked files and worktrees were preserved (not deleted,
      moved or overwritten).
