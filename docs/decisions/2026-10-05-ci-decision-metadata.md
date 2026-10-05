---
status: proposed
date: 2026-10-05
decision-makers: [GitHub estate campaign]
consulted: [Astra baseline and recovery reads]
review_by: 2027-01-03
evidence_class: source_review
overturn_when: A different landing method or native history counterexample invalidates the first-parent landing-tree selector.
---

# Apply decision metadata only after R5 lands

The user's A16 clarification makes every dated decision record in main's R5
landing tree the grandfathered baseline. Only paths introduced afterward require
metadata. No existing record is retrofitted, including records created while the
draft is reviewed. Filename dates never grant an exemption to a later addition.
This supersedes the historical 133/136-count and 2026-10-05 filename-cutoff plan.

This serves reliable, resumable foundation CI for the US-equities research and
broker-specific paper-readiness work. It does not change a trading gate.

## Evidence and alternatives

MADR 4.0.0 supplies the frontmatter format and status, date, decision-makers and
consulted fields: [adr/madr@2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d:template/adr-template.md:1-10](https://github.com/adr/madr/blob/2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d/template/adr-template.md).
The campaign adds review_by (0 through 90 days after date), evidence_class and
overturn_when. Evidence classes follow [.github/pull_request_template.md](../../.github/pull_request_template.md).
Overdue reviews are advisory; malformed required metadata fails the opt-in check.
Additional MADR fields are allowed.

[PyYAML 6.0.3 safe_load](https://github.com/yaml/pyyaml/blob/49790e73684bebad1df05ef8d828fa12f685bffb/lib/yaml/__init__.py#L117-L125)
parses YAML. Its native timestamp constructor can return date or datetime and can
raise ValueError for an invalid date; the policy requires date-only ISO values.
The previously accepted unchanged upstream parser suite passed 2,608 tests on its
clean CPython 3.13 wheel environment. That is parser-only native evidence, reused
here, not acceptance of this validator, the CI 3.12 wheel or hosted wiring.

The immutable baseline uses the first main first-parent commit that introduces
this exact document path, then that commit's native tree. The current repository
allows squash merges only (fresh native GET, 2026-10-05); a squash arrival contains
concurrent main records. See [Git 2.53.0 log](https://git-scm.com/docs/git-log/2.53.0),
[ls-tree](https://git-scm.com/docs/git-ls-tree/2.53.0) and
[rev-parse](https://git-scm.com/docs/git-rev-parse/2.53.0).
Rename detection and log.follow are disabled so introduction means the fixed
path's appearance. Native probing corrected one assumption: --diff-merges enables
patch output even with --format=%H, so --no-patch is also required.

A fixed list captured before review would require retrofitting concurrent records.
A moving main baseline would exempt every later record. A filename cutoff would
allow backdated additions to bypass enforcement. The actual landing tree avoids
these three problems under the current landing contract.

The committed index contains a stable selector and eligible record metadata.
Resolved commit IDs and pending/unknown states belong only in runtime results.
Before this document reaches main, the opt-in returns pending_landing (exit 2),
not successful enforcement. Missing refs, shallow history or native Git failures
return unknown (exit 3); invalid metadata/index returns exit 1.

The write-only native SDK construction attempt timed out after 25 minutes without
edits or a final report. Requests and model usage remain unknown; the attempt is
unfinished. Source-backed coordinator recovery implements repository policy
around the reviewed upstream interfaces. Local Git/metadata fixtures and root
integration checks have separate evidence and do not retroactively accept the SDK
attempt. The [R5 receipt](../../evidence/artifacts/github-ci-r5-20261005.json)
records their actual results.

## Activation and ownership

The Linux CI dependency installer already uses binary-only, hash-locked wheels.
After #735 landed at 095d4fad89c7896c7f1766fdaa9981554a19403a, the user's A17
land-first order authorized rebasing this draft and adding the reviewed PyYAML
6.0.3 stanza to requirements-ci.txt. Official PyPI metadata supplies the Linux
x86_64 CPython 3.12, 3.13 and 3.14 wheel hashes; the existing installer is unchanged.
The A17 follow-up 2 rebase onto main 1796303f957c522e78b92667e553c06840fae3a2
preserves that stanza. A fresh native GET of #706 still reports open/unmerged;
its caller remains held, with the one-line owner wiring step below. The receipt
retains both rebase observations and their separate test results.
See [official wheel metadata](https://pypi.org/pypi/PyYAML/6.0.3/json) and
[pip 26.2.1 install](https://pip.pypa.io/en/stable/cli/pip_install/).
Native pip's binary/hash-checked dry run resolves the combined lock on CPython
3.13. That is lock integration evidence, not an installation or CI 3.12 native
acceptance. The validate.yml caller remains #706-owned and is not edited by this
draft. Default validation and arbitrary-file scanning remain stdlib-only; PyYAML
is loaded only for eligible records in the explicit mode.

After R5 lands, the workflow owner ensures full origin/main history, then replaces
the existing Linux validator invocation with this one line:

```sh
python3 scripts/validate.py --decision-metadata
```

The checkout must fetch full history and origin/main; an absent remote ref or
shallow checkout is not sufficient. Do not add this caller to macOS bootstrap or
the publisher's entry points. This draft does not claim hosted enforcement.

For a new eligible record, refresh the deterministic index before validation:

```sh
python3 scripts/decision_metadata.py --write-index
python3 scripts/validate.py --decision-metadata
```

currency_due reads that JSON with the standard library and reports review_by
dates strictly before the current date separately from component due counts.
The output says indexed_snapshot and enforcement not observed. A missing or
invalid index gives an unknown count; it changes no existing notice or gate.
Sources: [Python JSON](https://docs.python.org/3.13/library/json.html) and
[datetime](https://docs.python.org/3.13/library/datetime.html).

## What overturns this decision

A multi-commit rebase or fast-forward landing could introduce the anchor before
the final R5 tree. Publishing this anchor separately, renaming it, or rewriting
its original introduction also invalidates the premise. Change the selector
before changing that landing contract. Native history fixtures that show an
incorrect landing tree or an eligible path exempted from metadata overturn it.
Successful local fixtures establish integration behavior only; activation needs
the owner wiring and hosted evidence after landing.
