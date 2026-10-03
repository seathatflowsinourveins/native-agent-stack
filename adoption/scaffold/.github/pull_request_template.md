<!--
Keep every heading. The sota-sources check fails a description whose "## SOTA sources" section is empty.
-->
## Scope

- What this pull request changes, in one or two sentences:
- Base commit: `<sha>`
- Lane or area label, if this repository uses them (exactly one):
- Paths touched:

## SOTA sources

<!-- Required. For every change: the maintained repository or published reference it installs or follows, with the repository URL, the pin (tag or commit), and the file, section or paper. A change without a SOTA source is not mergeable. -->

## Evidence

List each material claim with its evidence class. Classes: `native_proven`
(actual execution on a host, record retained), `local_integration`,
`synthetic` (fixture), `source_review`. Never label a claim a class stronger
than what was actually run.

| Claim | Evidence class | Command / record |
| --- | --- | --- |
| | | |

## Local commands run

```
$ <exact command>
<exit code / key output>
```

## Decision record

Path to the dated decision record for this change (if any), naming the
evidence, alternatives considered and the comparison that would overturn it:
