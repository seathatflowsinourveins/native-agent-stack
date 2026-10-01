# Generate the new WSL handbook from its published inputs

## Decision and sources

W-BOOK is a deterministic projection into `docs/new-wsl-handbook.md` and
`docs/new-wsl-handbook.json`. Its default inputs are the published
[ownership](../../evidence/artifacts/new-wsl-clean-install-selection-20261001/ownership.json),
[selection](../../evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json),
their preregistered packets, the separately owned W-PROF profile when published,
and explicit packet-bound family verdict files when supplied. The older
[edition](../../catalogs/foundation/new-wsl-architecture-20261001.json) provides
the 37-row inventory and titles: 20 foundation layers, 12 trading layers and
five cross rows. It supplies no new-install winners, pins or closure claims.

The implementation extends the maintained reference in
[`scripts/build_ecosystem.py` at `20ea4ae23a18565676823b9e3a23541c2100bb39`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/20ea4ae23a18565676823b9e3a23541c2100bb39/scripts/build_ecosystem.py),
reusing its deterministic JSON, digest and validation helpers and its confined
source reader. That exact fetched `origin/main` was checked with the GitHub
commit API. Existing precedents are
[`tests/test_handbook_summary.py`](../../tests/test_handbook_summary.py),
[`docs/grand-catalog-handbook.md`](../grand-catalog-handbook.md), and the
[packet builder](../../evidence/artifacts/new-wsl-clean-install-selection-20261001/build_packets.py).
The missing function was a projection joining the newly published ownership and
selection packet to W-PROF; the existing HTML builder does not perform that join.
No new package or orchestration runtime is needed.

The search-first, context-mode and modern-python skills informed discovery,
bounded output handling and reuse of the existing dependency-free Python setup.
Repository and GitHub source discovery were used; no claim of a package-registry
or ecosystem-wide tool search is made. The coordinator supplied the Astra
escalation trigger: consequential shared architecture and actual quota exhaustion
of the bounded Sol worker. Independent acceptance remains the coordinator's
review; passing these tests is not that review.

## Input and generation contract

```sh
python3 scripts/build_new_wsl_handbook.py --write
python3 scripts/build_new_wsl_handbook.py --check
python3 -m unittest discover -s tests -p test_new_wsl_handbook.py
```

`--root` selects a checkout. `--profile` can read a staged W-PROF file; its
public `source_path` is recorded with the hash of the bytes actually read.
Private paths never enter the output. The default profile path is
`adoption/new-wsl-profile.json`; absence is an explicit blocking publication gap.
The generator also reads `adoption/manifest.json` to state whether the profile ID
is registered for native bootstrap. It does not register or activate a profile.

W-PROF supplies `profile_id`, `source_path`, and `entries`. Each entry has `name`,
`layer_id`, `owner_layer_id`, `status` (`picked` or `head-to-head-arm`),
`repository`, `pin`, `checksum`, `install`, `acceptance`, `stage`, `position`, and
`blocking_gaps`. `checksum` carries `algorithm: sha256`, a 64-digit `value`,
`kind` (`artifact`, `lock`, or `source`), and `source`; a source checksum remains
a blocking gap for installation integrity. `install` and `acceptance` each
carry `command` and `source`. An acceptance version print is a gap. Optional
`provisioning_status` and `evidence_refs` preserve the profile's distinctions.
Stage/position describe order; this generator executes none of those commands.

External profile and verdict payloads are checked recursively before projection,
including fields the renderer does not otherwise use. Personal paths under root
and WSL-mounted Windows home directories are rejected alongside the existing
home-path checks. A narrow exception covers individual named-volume destinations
before the image argument of a simple `docker run` or `podman run` command.
The allowed forms are `--volume`/`-v` with a named source and `--mount` with
`type=volume`, a named source and one destination. Host mount sources, workdirs,
echo text and later command arguments remain checked. System executable and
configuration paths remain valid.

This uses Python's installed `shlex` tokenizer with `punctuation_chars=True`,
following the [Python 3.13 shlex documentation](https://docs.python.org/3.13/library/shlex.html),
and the argument boundaries in the official
[Docker run](https://docs.docker.com/engine/containers/run/),
[Docker volumes](https://docs.docker.com/engine/storage/volumes/) and
[Podman run](https://docs.podman.io/en/latest/markdown/podman-run.1.html) references.
It does not implement general shell parsing: command chains, shell expansions,
unknown option arities and multiline text receive the ordinary path check.
Only the exact published Hindsight multiline template has a separate exception:
its entire command SHA-256 must be
`349e199f6163d419fbd1fb362e2159a77381f0d9acae27651cfa4fbad015f276`
before its one declared `hindsight-data` volume destination is exempted. The
source is the durable-memory/Hindsight `install_command` in the selection JSON
at `20ea4ae23a18565676823b9e3a23541c2100bb39`; altered copies lose that exception.

Selected tools with several users share one inventory entry and one owner.
The small alias map encodes only uses stated in ownership.json: native clients,
Worktrunk, Podman, Ollama and systemd. Conflicting profile ownership or pin,
checksum, install and acceptance metadata fails generation. Ownership-only
comparison groups remain explicit enumeration gaps until the profile names
their individual arms and baselines. The profile may add those structured arms;
the generator does not manufacture metadata for them.
Blockers from every shared-tool entry are unioned in source order; an empty
blocker list from a user of the tool cannot erase its owner's blockers.
Canonical npm and PyPI metadata sources can supply a `package_id` in addition
to the owner and repository. Distinct packages in one repository retain their
own facts. A selection alias without its own profile entry can share the sole
identified package. Explicit entries need their own supported package binding;
an unresolved entry or aggregate keeps a package-binding gap when that
repository has identified packages.
Package identity never comes from parsing an install command. The source forms
and integration correction are recorded below.

`--claude-verdicts` and `--codex-verdicts` accept JSON with `family`,
`selection_sha256`, and `layers`, each keyed by `layer_id`. An external file must
also carry a public `source_path`. Each layer record binds `packet_sha256` to the
exact bytes of the judged packet, and `requirement_sha256` to the UTF-8 bytes of
its requirement text (a supplied literal `requirement` is also checked). Its
`release_pins` maps the tool names shown in the inventory to their current pins.
The packet must independently match its preregistration. Updating a packet and
that preregistration does not update an old verdict's binding.

Missing selection, packet, explicit requirement or release bindings keep the
record `pending`, with visible binding gaps and its actual source link. A
supplied binding that conflicts with the current input fails generation. A
layer-level `selection_sha256`, when supplied, is checked as well as the file's
binding. Historical reviews of the source host cannot be substituted for
judgments of these new packets. No guessed verdict filename is linked. The six
new default-round slots have a distinct packet shape; this adapter does not
invent a mapping from those slots to the initial 21 layer packets.

`final` is derived, never accepted as a profile tool status. For a layer it
requires all five `profile.finality[layer_id].c1` through `.c5` gates to be `met`
with evidence sources, both fully bound current verdicts to be `confirmed`
with explicit empty `material_gaps`, complete tool metadata, and a
`profile.comparisons[layer_id]` record carrying `selection_sha256` and
`preregistration_source`. The optional comparison `overturn_condition` is shown
verbatim with its source. This is consistency checking of supplied evidence,
not independent verification that a trial or review happened. The five gate
definitions come from the live research-state source. Packet-judging
preregistration and target-host experiment preregistration remain distinct.

## Evidence and limitations

Before W-PROF publication, the generated result had 37 unique layers and 56 tool
identities: 16 layers are picked recommendations, five are comparison arms and
16 await publication from their owning lane. No layer was final. The profile and
the two packet-specific family verdict inputs were pending, so every tool had
named installation/acceptance gaps. A reported but unpublished defaults
amendment is not an input or a completed gate; regenerate against its maintained
published source when the owner supplies it. The integrated W-PROF result is
recorded separately below.

The initial public-contract run returned exit 1 because the generator module
did not exist. The first implementation passed 22 tests; the independent
verifier then reproduced three adapter defects despite that result. The first
repair passed 32 tests; the subsequent container-scope repair passes 39. They cover
row coverage, unique tool owners and shared uses, per-tool metadata gaps,
rejection of edition winner inheritance, profile conflicts, source-versus-
artifact checksums, version-only acceptance, changed packet hashes, historical
verdict bindings, all five finality gates, stage ordering, host-path rejection,
stale output detection and identical bytes across separate process writes.
The finality-positive fixture is synthetic and claims no real final layer.
These are local integration checks under the
[acceptance evidence policy](../acceptance-evidence-policy.md), not upstream
tool tests, provider runs, GPU checks or new-distribution lifecycle acceptance.
The following returned evidence belongs to that earlier profile-absent snapshot;
the central validator was not rerun by this bounded repair worker.

| Command | Returned evidence |
| --- | --- |
| `python3 scripts/build_new_wsl_handbook.py --check` | Exit 0; `status: passed` for both output hashes. |
| `python3 -m unittest discover -s tests -p test_new_wsl_handbook.py` | Exit 0; 39 tests, `OK`. |
| `python3 -m unittest discover -s tests -p test_handbook_summary.py` | Exit 0; one test, `OK`. |
| `python3 scripts/validate.py` | Exit 0; `components: 69`, `hashed_files: 8939`, `profiles: 4`, `receipts: 184`, `status: passed`. Integrity and scope checks only; no live provider or GPU execution. |

## Independent-verifier repair

The three findings were reproduced against generator SHA-256
`1319e1676254d5ab75e3d7ef035cbbc6051cde2b3a54f8ca8d817f652496b45d`.
The public-CLI regression suite returned exit 1: `Ran 32 tests in 3.996s`,
`FAILED (failures=11)`; the 11 failures include variants of the three findings.
The owner-blocker probe showed its blocker disappearing after a shared entry
with an empty list. Root and WSL Windows home paths passed through the adapter,
including ignored external metadata. A changed requirement and updated packet
preregistration still reused a verdict's old packet hash and produced `final`.
Additional negative cases exposed unchecked requirement and release bindings.

After the bounded repairs, the same suite returned exit 0:
`Ran 32 tests in 7.230s`, `OK`. The shared-blocker probe also passed separately
(one test), as did both path forms, ignored external fields, private mount sources
and the valid container/system-path controls (five tests with subcases). These
are synthetic adapter mutations through the real CLI; none is a model review,
an upstream install test, or a new-host lifecycle trial. The independent verifier
must review the frozen repair before its acceptance is claimed.

## Container exception scope repair

The targeted verifier confirmed the previous three repairs, then reproduced two
remaining publication bypasses against generator SHA-256
`2eaa1c0c3998b70d813f46d011abf9129d038d1be45dd05c1faa5de1a3c28268`:
echo text containing `docker --workdir` and a `helper --workdir` command after
`docker pull ... &&` both inherited the container exception. The payloads were
never executed. The public-CLI regressions returned exit 1:
`Ran 38 tests in 11.628s`, `FAILED (failures=10)`, including operator and
after-image variants.

The repair requires a real run-command prefix and confines exemptions to the
named-volume flags before its image. Shell chains, other commands and ordinary
workdir flags no longer receive an exception. Colon-prefixed path text is also
checked, so an echo of a volume argument does not acquire a container namespace.
The first stricter pass exposed the legitimate published Hindsight template
(`FAILED (failures=11, errors=12)`); the complete-template digest binding above
preserves that source reference without interpreting its provider placeholders.
Appending a private-path command to the template fails the new mutation test.

The repaired suite returned exit 0: `Ran 39 tests in 6.714s`, `OK`. Its positive
controls cover the original named-volume destination, mount aliases, equals
syntax, system tool paths and the exact multiline source reference. All prior
owner-blocker, packet-binding and direct-path probes remain in the suite.
These are local synthetic adapter checks. Independent acceptance was pending at
that scope-repair handoff.

## Package identity integration repair

The real frozen W-PROF file has 69 entries and SHA-256
`d316e29413ee927122fa8cdb55d74427bb9a646421ae401f1c5e26e314b474fa`.
With generator SHA-256
`7f3cd3dc74c01e74b0a0ef6169f9400c12ceadeb4b14bea2daac956c58fa4f72`,
the default public `--write` returned exit 1:
`new-wsl-handbook: conflicting profile checksum for Codex Python SDK`.
The SDK entries shared an owner and repository, but they describe different
installable packages. Repository identity alone was too coarse. The original
failed integration output was retained, and the scoped reproduction returned
the same exit and error before any generator change.

Research checked the installed Codex CLI (`0.159.3`), its
[`rust-v0.159.3` release through the GitHub API](https://github.com/openai/codex/releases/tag/rust-v0.159.3),
and the tagged
[CLI README](https://github.com/openai/codex/blob/rust-v0.159.3/README.md),
[TypeScript package manifest](https://github.com/openai/codex/blob/rust-v0.159.3/sdk/typescript/package.json)
and [Python package manifest](https://github.com/openai/codex/blob/rust-v0.159.3/sdk/python/pyproject.toml).
The live registry responses independently returned these three names at
version `0.159.3`:

| Package identity | Metadata source |
| --- | --- |
| `npm:@openai/codex` | [npm CLI release metadata](https://registry.npmjs.org/%40openai%2Fcodex/0.159.3) |
| `npm:@openai/codex-sdk` | [npm TypeScript SDK release metadata](https://registry.npmjs.org/%40openai%2Fcodex-sdk/0.159.3) |
| `pypi:openai-codex` | [PyPI Python SDK release metadata](https://pypi.org/pypi/openai-codex/0.159.3/json) |

The maintained builder at
[`85543efe5abcddb7b7cddb14e8774e83b6758616`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/85543efe5abcddb7b7cddb14e8774e83b6758616/scripts/build_ecosystem.py)
already keeps explicit component IDs separate from repository URLs; its
`component_ids` join and named-winner adapter were inspected alongside the
earlier `20ea4ae` reference. W-PROF has no maintained component reference for
either SDK, so this correction uses their supplied checksum metadata URLs.
No profile entry, pin, checksum, command or acceptance status was edited.

The implementation reuses
[`urllib.parse.urlsplit` and `unquote` in installed CPython `v3.13.15`](https://github.com/python/cpython/blob/v3.13.15/Lib/urllib/parse.py),
the [`npm/registry` API at `ae49abf1bac0ec1a3f3f1fceea1cca6fe2dc00e1`](https://github.com/npm/registry/blob/ae49abf1bac0ec1a3f3f1fceea1cca6fe2dc00e1/docs/REGISTRY-API.md),
the [PyPI JSON API](https://docs.pypi.org/api/json/) and
[PyPA name normalization](https://packaging.python.org/en/latest/specifications/name-normalization/).
It accepts the exact HTTPS registry authorities and their supported metadata
paths, with no query or fragment, and includes the normalized package name in
the owner/repository identity. Unknown URL forms supply no package identity.
Selection aliases without their own profile entry remain deduplicated when
only one package is known; the explicit-entry correction below narrows this
fallback after an independent counterexample. The
unbound selection `Codex SDK and codex exec/app-server` stays pending because
the profile names two SDK packages without binding that aggregate to either.
Conflicting pin, checksum, install and acceptance facts for the same package
still fail; shared blockers are still unioned. The generator performs no network
request or command execution to derive this identity.

The coordinator requested Astra/max for the actual integration failure after
the bounded Sol repair and its consequential identity decision. The actual
serving backend and token usage are not exposed in this worker's evidence and
remain unknown. Independent acceptance of this new frozen repair belongs to
the coordinator's subsequent review.

Five new public-CLI checks cover the real profile, a three-package fixture,
same-package checksum conflicts including normalized aliases, shared blocker
union, and unsupported metadata URL controls. Before the correction they
returned exit 1: `Ran 5 tests in 1.019s`, `FAILED (failures=9)`.
Afterward they returned exit 0: `Ran 5 tests in 1.642s`, `OK`.
Because inventory assembly changed, the previous 39 privacy, verdict and
generation checks were rerun together with those five: exit 0,
`Ran 44 tests in 6.181s`, `OK`. The exact Hindsight template exception and all
private-path bypass regressions remain intact.

The real profile's default `--write` and then `--check` both returned exit 0.
The current generated artifacts have 37 layers, 73 tool records and 20 package
identities: 16 layers are picked, five are comparison arms, 16 are pending and
none is final. Each of the three Codex packages retains its own pin, checksum,
install, acceptance and provisioning fields. The Python SDK's documented
example does not populate the TypeScript SDK's missing acceptance. Reviewed
commands remain unexecuted and `new_host_acceptance_claimed` remains `false`.

| Generated output | Returned SHA-256 |
| --- | --- |
| `docs/new-wsl-handbook.md` | `5a443fa223aa356f8723f3c467cbc0a3bb1d23dd67481cb9989309eae8e4c5b7` |
| `docs/new-wsl-handbook.json` | `a3411297d8b33bd7363a9b99d659252585c5d7119b6586c7ce1b5c6cdb1ec687` |

A separate comparison reconstructed every original profile-absent input by its
published SHA-256, using `85543efe` for the pre-registration adoption manifest.
The repaired generator reproduces the original Markdown hash
`265e7097d44dd95b05a85a2ee5fa3b8ae5874ed61955d98151419d1317ff855a`
and JSON hash
`9840022888881bdf60c989947aff83f005bb236095e97d580b73f3f5105b394d`
byte for byte. These are local projection and integration results, not unchanged
upstream tests, executed SDK examples, provider/GPU runs or new-host acceptance.

## Explicit-entry alias correction

Independent Astra acceptance reproduced a counterexample against generator
`cbdd360755324518d10dcd8f88fe100a353d0b202514c4691b7c9bb8f56fea6c`
and frozen patch
`809451671798da018d829c137f73d6685c7346d0d0a376b67b35a488c43cb24e`.
The real 69-entry profile still passed, but the broader guarantee about
unsupported package sources was false. The probe kept the TypeScript SDK,
omitted its Python sibling, and added an explicit unresolved entry whose
metadata URL used `registry.npmjs.org.example.org`. The parser returned no
identity, but the sole-package repository fallback assigned the TypeScript
package anyway and triggered a checksum conflict. The previous unknown-source
controls always supplied two canonical SDK siblings and missed that branch.

The exact new public-CLI regression returned exit 1 before the correction:
`Ran 1 test in 0.088s`, `FAILED (failures=1)`, with
`new-wsl-handbook: conflicting profile checksum for Unresolved SDK package`.
The failed output is retained with this repair's private integration receipts.

The correction applies the already cited registry-source contract to explicit
profile entries: an unsupported source cannot inherit a sibling's identity.
Such an entry stays separate with its original metadata and a visible pending
package-binding gap. A selection alias with no profile entry may still reuse
the sole identified package in its owner/repository. Canonically identified
same-package aliases still undergo strict fact-conflict checks and blocker
union. No installer parsing or new component identity was added.

The six affected package checks returned exit 0:
`Ran 6 tests in 1.835s`, `OK`. The real-profile default `--write` and `--check`
both returned exit 0 with the same output hashes recorded above. The profile
hash remains `d316e29413ee927122fa8cdb55d74427bb9a646421ae401f1c5e26e314b474fa`.
The earlier 44-test result belongs to the previous revision; this iteration
reran the affected package checks and actual generation only. Privacy guards,
the exact Hindsight exception and verdict-binding code were not changed.
These results remain local integration evidence with no execution of the
profile's provider or hardware commands. The continued failure triggered the
requested Astra/max route; actual backend identity and usage remain unknown.
Independent acceptance of this new frozen correction remains pending.

## Task correction log

| Mistake | Correction and verification | Prevention |
| --- | --- | --- |
| The initial status update called the 21st packet `agent-engine`. | The actual 21st layer is `cross:wsl-distro`; read the IDs in both published ownership and selection JSON. The status update was corrected immediately. | The coverage test binds all 37 edition IDs and the source packet IDs. |
| Treating a layer ID as its packet filename failed on the cross row. | The maintained packet builder uses `lid.replace(':', '_')`; the generator now uses that exact mapping. | The real-source generation test failed, then passed after the correction. |
| The first Windows host-path regex also matched the tail of HTTPS URLs. | A drive letter must begin at a non-alphanumeric boundary. | The real-source suite failed on ordinary URLs, then passed; private-path rejection remains tested. |
| A literal private-path negative fixture tripped the publication validator. | Construct the forbidden path at test runtime so it is tested without publishing a home path. | `scripts/validate.py` rejected the literal fixture before the correction. |
| Shared-tool merging replaced the owner's blocker list with the last user's list. | Union every entry's blockers before deriving tool or layer status. | The public-CLI owner/shared-entry mutation failed before the repair and passes with the blocker in both artifacts and no final layer. |
| The privacy guard omitted root and WSL Windows home paths and checked only projected fields. | Validate complete external payloads before projection; distinguish explicit container destinations from host sources. | Both reported path probes, ignored-metadata probes and the private mount-source probe failed before the repair and now reject publication; container/system-path controls pass. |
| A selection hash was treated as enough to bind a verdict to a packet. | Check the exact judged packet hash, explicit requirement and release bindings; retain unknown bindings as pending. | The public-CLI packet mutation plus updated preregistration succeeded incorrectly before the repair; it now fails against the retained verdict hash. Missing bindings remain pending. |
| Any Docker/Podman token enabled path exceptions across an entire payload. | Require the run prefix and a bounded named-volume option before the image; give unrelated shell text no exception. Preserve the one published multiline template only by its complete digest. | Both exact verifier payloads and the echo/operator/after-image mutations failed before the repair and now reject publication; the actual source reference and its altered-copy rejection are tested. |
| Repository/owner identity collapsed the TypeScript and Python Codex packages and rejected their different checksums. | Use supported npm/PyPI metadata URLs to retain separate package identities; preserve unresolved aggregates, alias deduplication and strict same-package conflicts. | The real 69-entry profile and five new public-CLI controls failed before the correction and pass afterward; all 44 handbook checks pass, and the original profile-absent bytes are unchanged. |
| The sole-package repository fallback assigned a canonical package to an explicit entry with an unsupported metadata URL. | Permit that fallback only for selection aliases without their own profile entry; retain an explicit unresolved entry separately with a package-binding gap. | The independent single-sibling probe was reproduced through the public CLI, failed before repair and passes afterward; all six affected package checks and actual-profile write/check pass. |

These corrections are recorded here because this bounded worker does not own
the shared harness-defaults log. The coordinator can carry them into that log
and shared memory without competing edits.
