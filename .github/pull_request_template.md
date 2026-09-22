<!--
Scope and base commit
-->
### Scope

- What this PR changes, in one or two sentences:
- Base commit: `<sha>`
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
