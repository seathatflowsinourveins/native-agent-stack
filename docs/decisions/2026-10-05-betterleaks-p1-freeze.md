# Freeze P1 without changing the required scanner

P1 qualifies a swap of the existing required CI secret scanner, following
the [original preregistration](2026-10-02-github-automation-practice.md).
The interim is CI secret scanning only, with no local hook. This foundation
change freezes inputs and records evidence; a gate swap remains a separate
shared-lane decision. It serves dependable CI integrity for north-star R&D.

The immutable experiment inputs are in
[`preregistration.json`](../../evidence/artifacts/betterleaks-p1-20261005/preregistration.json).
Arms are release Gitleaks8.30.1 and Betterleaks1.9.0. Use their published,
checksum-verified binaries in an isolated tool root, not a rebuilt release or
the shared host installer. Retain native scanner JSON privately with explicit
`--redact=100`; only location/count metadata enters public evidence. Betterleaks
defaults redaction to zero and validation off; neither its help wording nor
the disabled validation setting establishes observed network behavior.
Sources: [Betterleaks root.go:94](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/root.go#L94-L112),
[release1.9.0](https://github.com/betterleaks/betterleaks/releases/tag/v1.9.0),
[Gitleaks8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1).

## Native scoring prerequisite

Current CredData offers `python -m benchmark --scanner ... --load REPORT`,
but its legacy Gitleaks adapter passes an empty rule while the current scorer
requires a matching metadata category. Converting modern `File`/`StartLine`
fields into that adapter's old JSON cannot produce valid quality scores.
The scorer matches exact spans; unknown/lost detections do not enter its FP
total, and category expansion affects denominators. Unmatched diagnostics can
print source lines, so raw harness stdout also stays private. Sources:
[CLI:18](https://github.com/Samsung/CredData/blob/0b1940e171725ad8937311120b191602608a4801/benchmark/__main__.py#L18-L20),
[Gitleaks adapter:36](https://github.com/Samsung/CredData/blob/0b1940e171725ad8937311120b191602608a4801/benchmark/scanner/gitleaks.py#L36-L39),
[scorer:276](https://github.com/Samsung/CredData/blob/0b1940e171725ad8937311120b191602608a4801/benchmark/scanner/scanner.py#L276-L396),
[denominators:80](https://github.com/Samsung/CredData/blob/0b1940e171725ad8937311120b191602608a4801/benchmark/scanner/scanner.py#L80-L92).

The minimal adapter validates/projects native JSON into location metadata,
preserving multiline positions, columns and history commits. It neither
executes scanners nor implements a scorer, assigns categories from labels,
or changes upstream code. Column units remain native, without an asserted
CredData offset conversion. Invalid/incomplete shapes fail closed; duplicate
positions are counted separately from unique line spans. Same-span value/label
ambiguity remains a scoring prerequisite, rather than a passing result.
Source contracts: native scanner reports and
[CredData MetaKey:7](https://github.com/Samsung/CredData/blob/0b1940e171725ad8937311120b191602608a4801/meta_key.py#L7-L18).

The original frozen input file remains unchanged. The separately recorded
[`envelope-clarifications.json`](../../evidence/artifacts/betterleaks-p1-20261005/envelope-clarifications.json)
distinguishes the unchanged fixtures' default flags from explicit history
flags, and keeps size/archive skips and merge-resolution coverage as acceptance
prerequisites. Native `--log-opts` replaces the scanner's default log options;
the pinned revision's939 nonmerge patches cannot establish coverage of all100
merge resolutions. Sources:
[Gitleaks sources/git.go:74](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/sources/git.go#L74-L95),
[Betterleaks sources/git.go:110](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/git.go#L110-L124).

CredData quality execution stays pending a supported native scoring contract,
requested through lane Q5, before2026-10-20. No partial dataset or substitute
runner is acceptance. Native `download_data.py --jobs1 --noise0` prepares337
pinned repositories, without an internal byte/time cap; acquisition needs an
outer bound outside paper windows and is held until scoring is settled.
Source: [downloader:249](https://github.com/Samsung/CredData/blob/0b1940e171725ad8937311120b191602608a4801/download_data.py#L249-L280).

## Observed partial execution

The retained [run record](../../evidence/artifacts/betterleaks-p1-20261005/run-record.json)
shows zero Gitleaks history findings and99 Betterleaks locations under the
frozen native options. The latter remain unreviewed detections. Gitleaks passes
all23 unchanged control methods; Betterleaks records four assertion failures
in d2, d4 twice, and d5, retaining the unprefixed40-hex class loss. Both history
process trees and both control process trees have no observed network syscall
under the isolated observer. This partial execution supports retaining the
required scanner, without declaring complete CredData or upstream acceptance.

## Published results and alternatives

Betterleaks's author publishes a full-scanner CredData F1 of.8922 using a
modified configuration and his replacement scorer. This is useful prior
evidence, distinct from earlier candidate-classifier results. The post pins
the filter implementation, but does not identify the executed binary and
dataset checkout. It does not qualify release1.9.0 defaults under Samsung's
native harness. Sources: [author's publication](https://lookingatcomputer.substack.com/p/rare-not-random),
[official employer mirror](https://www.aikido.dev/blog/token-efficiency-secrets-scan),
[helper README:15](https://github.com/zricethezav/creddata_helpers/blob/b2a59742ba746bdae2ddde251fd356f4914bf8d6/README.md#L15-L24).

Alternatives held out are the author's replacement scorer; metadata-category
projection, which changes the measurement contract; and the historical
May2024 rule-free scorer, whose old corpus, acquisition behavior and single-line
adapter cannot silently stand for the current experiment. A semantic rule-to-
category crosswalk also needs verified source semantics before acceptance.
The project's [closed adapter issue213](https://github.com/Samsung/CredData/issues/213)
supports adapting reports generally, without validating these alternatives.

The decision can be overturned by a supported, pinned, current native route
that meets the frozen location/class contract, complete-corpus scoring with
unknown/ambiguous findings accounted for, no unaccepted class loss and no
additional blocking false positives. Repository-history differences alone
are not truth labels, and fixture failures are synthetic integration evidence,
not unchanged upstream tests. No merge, host apply or required-gate swap follows
from this draft.
