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
Independent acceptance was pending at that frozen-correction handoff.

## Project the owner's slot default states

The separate default-state protocol is consumed from
[`definitive-manifest.json` at reviewed source `f565764972a65554bd8968f6205957989c6ab3a7`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f565764972a65554bd8968f6205957989c6ab3a7/evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json).
Its exact fetched bytes have SHA-256
`16eaf725e0bb616fcf2e4dc838f2482ebb272e2b3fcb585b3b4e01437edef42f`.
The schema and state meanings come from the same revision's
[`assemble_manifest.py`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f565764972a65554bd8968f6205957989c6ab3a7/evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py),
especially `rows_of()` and `build()`. This extends the maintained handbook at
[`18d9308cff5761c65cd36967db58020f5e40b6c8`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/18d9308cff5761c65cd36967db58020f5e40b6c8/scripts/build_new_wsl_handbook.py)
using its existing confined reader, complete-payload privacy check, hashing and
rendering functions. No new runtime or decision procedure was added.

The canonical optional input is
`evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`.
When present, it is read with the repository's confined `safe_file` path check.
`--defaults-manifest` accepts an explicit file as a `supplied-preview`; its full
bytes are hashed under the public canonical source path, and its complete
payload is checked before projection. The external filesystem location never
enters the handbook. The default path is labelled `published-source` when it
exists. An explicit missing input fails instead of silently dropping the source.

Each layer gains a separate default-slot table and JSON `default_slots`, joined
by exact `layer_id`. The original slot row is retained under `record`; the
displayed `state` maps an empty or omitted state to `pending`. The source has
37 layers and 74 slots: three definitive, two split, one measurement, 65 with
empty states and three pinned requirement rows with no state field. Thus 68
display as pending. The original missing-versus-empty distinction survives in
the retained records. The memory slot remains a measurement decision, and
both split rows retain their exact deciding text.

The producer emits no separate candidate-ID array. Its exact `default`,
`repository`, `label`, `row_kind` and family-status fields supply the
recommendation/candidate and provenance columns; the adapter does not parse
candidate identities from prose. Manifest ownership is retained separately as
`default_ownership`. The owner catalogues all five cross rows under foundation;
the handbook keeps its conceptual cross inventory and preserves that source
catalogue in provenance. Invalid states, missing or duplicate layers, unknown
slot layers, inconsistent slot catalogues, duplicate slot IDs, duplicate
ownership declarations and inconsistent declared counts fail generation.

Top-level `default_decisions` retains the source's meaning, rules, limitations,
counts and upstream source-file hashes. Those hashes remain the producer's
provenance statements. The input provenance table separately hashes the compact
sources used to bind the slot inventory. Reading them does not re-run the model
rounds or certify the producer's claims. The handbook introduces no decision
rule and changes none of the existing tool picks, pins, provisioning statuses,
acceptance examples, finality gates or `new_host_acceptance_claimed` flag.
A source-fit default therefore cannot create host readiness or a live-provider
claim. The coordinator requested Astra/max for this consequential separation
of decision state from measured acceptance; actual backend identity and usage
are not exposed by these integration checks.

Six new local controls cover the exact reviewed manifest, invalid state/layer/
ownership mutations, complete external source hashes and payload privacy,
canonical-path confinement, source-fit/host-acceptance separation, and explicit
missing inputs. Their initial run returned exit 1: `Ran 6 tests in 5.125s`,
`FAILED (failures=11, errors=2)`. After implementation, the same scoped suite
returned exit 0: `Ran 6 tests in 4.965s`, `OK`, with no skipped tests.
`NEW_WSL_DEFAULTS_FIXTURE` supplied the exact reviewed manifest for the actual
source test while its canonical repository path was unpublished. That test also
exercises canonical-path loading inside an isolated fixture; it does not assert
that the owner PR has merged. All 45 prior test bodies remain unchanged; their
earlier evidence was retained rather than rerunning unrelated checks.

The real source preview's `--write` and `--check` both returned exit 0 in a
separate fixture checkout, with 37 layers, 74 projected slots, 73 existing tools,
zero final layers and `new_host_acceptance_claimed: false`. The preview hashes
are `6c824993b85541c3febc26efc3ff13dd24d9a6f743beb91bff35cee59c5681ec`
for Markdown and
`5daf91b58d846a61070e1f5ca0605394fb2b8c25bee93684fd971ee06812439a`
for JSON. The worktree's manifest-absent `--check` also returned exit 0 and
preserved its previous Markdown/JSON hashes `5a443fa223aa356f8723f3c467cbc0a3bb1d23dd67481cb9989309eae8e4c5b7`
and `a3411297d8b33bd7363a9b99d659252585c5d7119b6586c7ce1b5c6cdb1ec687`
byte for byte. Profile SHA-256 remains
`d316e29413ee927122fa8cdb55d74427bb9a646421ae401f1c5e26e314b474fa`.

At this source-preview checkpoint the reviewed owner PR was still awaiting
accepted-main confirmation. The two generated files in the worker checkout
therefore retain the manifest-absent output; the preview artifacts are separate
private integration evidence. Publication must regenerate against the accepted
canonical source. These results are local adapter checks, not upstream model
tests, new measurements, installations, provider calls or new-host acceptance.

## Repairs after the two reviews

The publication guard now reuses `validate.PRIVATE_CONTENT`, following
[`scripts/new_host_grand_list.py` at `0d3893630c258696eed60f4431654f94471e8e3a`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d3893630c258696eed60f4431654f94471e8e3a/scripts/new_host_grand_list.py).
Both rendered outputs are scanned before any write or successful `--check`.
The recursive input check also applies the shared patterns. A refusal names
only the pattern label and never the matched value. Synthetic install-command
and rendered-output controls cover both publication modes and preserve existing
files when publication is refused.

Slot identifiers are bound to the compact catalog inventories named by the
definitive manifest. The identifier expansion follows the already cited
producer's `rows_of()` and `build()`: nested roles, multiple defaults and pinned
requirements retain their exact identifiers. Unknown or omitted identifiers
fail with the offending IDs even when counts remain consistent. The projected
layer tables must cover the complete inventory. This reads and hashes the
compact sources without changing their recommendations or evidence classes.

The profile adapter and handbook refuse default installation of comparison arms
whose owning slot remains `split` or `measurement`. This check uses the manifest
state and comparison group even if an arm's profile status is changed to
`picked`. Memory is included alongside retrieval and model-server arms. A
returned measurement must resolve the source decision before it supplies an
install default.

Claude Code uses one version rule in its source entry, overview, bootstrap and
generated handbook. The pin is the last qualified release and a floor; the
install takes the release current at install time; the receipt records the
installed version; a release newer than the pin counts as installed and not yet
qualified until its acceptance command has passed on that host. The official
[native installer documentation](https://code.claude.com/docs/en/setup#install-a-specific-version)
supports the `latest` channel. The source entry retains the pinned artifact and
checksum as the qualified-release reference. The older observed ai-memory and
Worktrunk releases remain below their selected releases; their source-test
commands retain their original scope and are still unexecuted. The profile
rejects text that contradicts an entry's version floor rule.

Docker Engine and the rootless boundary now share an unexecuted acceptance
pair: `docker info` must report rootless in the daemon's security options, then
`docker run --rm hello-world` must exit 0 through the user-level daemon. Docker's
[rootless documentation](https://docs.docker.com/engine/security/rootless/) tells
the user to confirm that daemon with `docker info`; its
[troubleshooting example](https://docs.docker.com/engine/security/rootless/troubleshoot/#docker-run-errors)
runs `hello-world` without sudo. The
[run reference](https://docs.docker.com/engine/containers/run/) supplies `--rm`.
The paired exit requirement is this recipe's acceptance formulation. Both
entries remain excluded from the minimal default install, and the pair remains
`UNRUN`, owed on the first run on the new host. It checks daemon mode and startup;
[resource-limit enforcement](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources)
still needs its own acceptance.

The profile's host prerequisite requires WSL 3.0.1 or later with per-distribution
cgroup isolation enabled before a second systemd distribution starts. On 2.7.x,
distributions share the user cgroup tree and only one can start that user
manager. [microsoft/WSL PR 40519](https://github.com/microsoft/WSL/pull/40519)
documents that conflict and adds per-distribution cgroups;
[PR 41512](https://github.com/microsoft/WSL/pull/41512) adds their cgroup namespaces
and reports a manual rootless Docker success. The
[3.0.1 release](https://github.com/microsoft/WSL/releases/tag/3.0.1), at
[`91f161fa240dc355c1a88daabc8aac4273e35ba5`](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L2291),
contains the namespace repair and its follow-up. These repairs appeared in
earlier prereleases; 3.0.1 is the stable-release floor used by this recipe.
[Issue 41492](https://github.com/microsoft/WSL/issues/41492) records the known
rootless-container risk after the hierarchy change. Its historical report is
not proof that built-in systemd remains broken on 3.0.1, and the upstream manual
success is not acceptance on the new host. The gate is executed in the separately
owned [distribution recipe](../../adoption/platforms/linux-wsl2-new-distro.md);
this profile links that gate without copying its commands.

The search-first source review used cached primary upstream documents and
source snapshots. Live refreshes of the GitHub, Docker and Claude sources
returned curl exit 6 because DNS was unavailable. No installation, host-service
query or acceptance command was performed. The completeness critic retained
the separate package-integrity, user-manager and resource-limit acceptance gaps.

Seven focused regression tests first returned exit 1 with nine failures and two
errors: secret-shaped install commands and rendered outputs were published,
unknown and omitted slots passed, ai-memory could become a default before its
measurement, and the version rule and rootless acceptance fields were missing.
After repair the same seven tests returned exit 0. The Windows ordering check
now inspects `first_boot_prerequisites`, requires F1 through F8 in order before
stage 2, and places F10 and F11 afterward. Isolated negative controls reject F9
in that prerequisite list, a swapped prerequisite order, an unmeasured memory
default, an unknown slot, a secret-shaped value and a book left stale after one
manifest default changes. These remain local synthetic integration checks.
Earlier receipts retain their historical validation and evidence scope.

The requested verification order returned exit 0 for handbook `--write`,
handbook `--check`, the two test modules together (`Ran 72 tests`, `OK`, no
skips), and `new_host_grand_list.py --check` (`status: passed`, 32 layers and
66 winners). The handbook receipt's generator, profile and output hashes were
refreshed; its earlier validation records remain historical. Profile review
and freeze receipts retain their original snapshot hashes and counts.
The publication validator returned exit 1 only for registered hash and byte
count mismatches on changed files. It reported no other failure; the coordinator
owns re-registration in the evidence manifest.

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
| Initial manifest inspection assumed every slot had a `state` field and returned `KeyError: 'state'`. | The reviewed producer's `build()` emits three pinned requirement rows without that field. Preserve their raw records and display the missing states as pending, alongside the 65 explicit empty states. | The actual 74-slot projection control checks all original records and the exact 3 definitive / 2 split / 1 measurement / 68 pending display counts. |
| The payload path guard was treated as enough to protect publication. | Apply the shared private-content patterns to inputs and both rendered outputs before write or check success. | The synthetic install and per-output controls reject secret-shaped values, report only labels and preserve existing outputs. |
| Unique nonempty slot IDs were treated as a complete inventory binding. | Compare IDs and owners with the manifest producer's compact catalog inventories and require complete projection coverage. | Unknown-ID and omitted-ID mutations reject with the offending IDs even when counts stay consistent. |
| The first-boot boundary assertion searched the Windows steps, and the default-arm assertions omitted memory. | Check the F1 through F8 prerequisite collection and order; bind unresolved comparison defaults to the manifest states. | Separate F9, order and ai-memory mutations fail the corrected checks. |

These corrections are recorded here because this bounded worker does not own
the shared harness-defaults log. The coordinator can carry them into that log
and shared memory without competing edits.

## Repair for the merged manifest and the platform review (2026-10-02)

Main moved under pull request 592. The definitive manifest has its next version
(84 rows, each with a job, a state and a resolution, ten of them added by the
decision rounds), produced by `assemble_manifest.py` at
`675bdd51c96af28aa98012d9e4ff772a77a38f3d`, and the new-distribution recipe was
repaired and rehearsed (`3a8dc31a67115f85b69709d7ad8c2c5f6ea9f40e`). On the
merged tree `python3 -B scripts/build_new_wsl_handbook.py --check` printed
`new-wsl-handbook: 'file'` and exited 1, and the two test modules ran 72 tests
with 2 failures and 59 errors, nearly all of them `KeyError: 'file'` in the test
setup. The pull request's reviewers also left three comments that the source
owner accepted: two platform points, the owner's acceptance of both, and the
fresh-install version policy (pull request 592, comments 5945871425,
5946244282 and 5947019967).

Earlier sections stay as written. Where they say that the install takes the release
current at install time, or that the profile requires WSL 3.0.1 or later, this
section governs.

**Cause of the `KeyError`.** The manifest's `sources` now has six entries.
`foundation` and `us-equities` are the two compact catalogs and `settlements` and
`convergence` are decision files; all four carry `file`, relative to the
manifest's folder. `rule` and `combined` are the convergence rule and its combined
results that `convergence.json` cites, and they carry `path`, relative to the
repository root, with no `file`. The generator and the test setup read every entry
as a catalog with a `file`, and `rule` is the first entry without one. Repairing
only that read would still have failed three more ways: the closed sets refused
the `resolved` state and the `added` row kind, the ten added rows came from
`convergence.json`'s `added_slots` and not from a catalog, so the inventory
reported them as unknown ids, and the counts check lacked the producer's new
`by_state` and `installed` counts.

**Generator.** Each source is resolved by its `file` or its `path` and read through
the confined reader, and its SHA-256 must equal the manifest's declared value.
Only the layers' catalogs are parsed as catalogs; the inventory adds the added
slots from `convergence.json` as the producer's `apply_convergence()` does. The
closed sets follow the producer. Every count is computed from the rows and must
equal the manifest's own, and the computed counts are projected to both outputs.
Each row shows its layer, slot, state (an empty state is shown as `open`, as the
producer's counts name it), job, default, repository and outcome. The invariants
that the producer enforces for a split, an unreturned measurement and a
`not_installed` row are checked before display. A row that installs nothing by the
producer's rule (a default, and not `installs_nothing_extra`) is shown as not
installed with the manifest's reason. The W5 paired record, its pass rule and the
getty mask proof are read from the recipe page, and so is F9's command block,
which replaces the three stage-2 steps that carried their commands as typed text.
No command is typed into the generator.

**Platform review, point 1.** The release is a selected target. The profile and the
handbook say that this launch adopts stable WSL 3.0.1 or later for a second systemd
distribution; that the 2.9.8 and 2.9.13 pre-releases carried the cgroup fixes first
(pull requests 40519 and 41512) and are not adopted; that a single-distribution
install has its own, lower install-only minimum, which the recipe page gives; and
that the observations (the 2026-10-02 rehearsal on 2.7.13 failed on shared cgroups,
and the host was updated to 3.0.1.0 that day) stay apart from the policy. The
wording and the sources come from the page's host-wide rules, and the single-
distribution sources come from the recipe's decision record. A test refuses any
version in the policy text that the page's host-wide rules do not hold.

**Platform review, point 2.** The paired proof is named. The executable gate for two
systemd distributions is the recipe's W5: five observations from both running
distributions (uid, system state, failed units, user manager, cgroup namespace),
the pass rule the page states and the getty mask proof. It was observed on one host
in rehearsals on throwaway distributions, and run 3 of 2026-10-02 passed it
(`evidence/artifacts/new-wsl-rehearsal-20261002/runs-on-wsl-3.0.1.json`). A
rehearsal is not acceptance of the real distribution, so the status for the real
distribution stays `UNRUN`; a version check or one healthy user bus does not
satisfy the gate. The profile validator rejects a profile that declares the proof
passed or leaves it out.

**Fresh-install versions.** The bootstrap stays as it is. Its `install_native()`
(`adoption/bootstrap-linux.sh` at `b9c27644cc61a9a6a96773f6a272d28625f7835e`)
installs Claude Code's pin and keeps a newer existing launcher, so the shared rule
now says that, and the sentence in `adoption/bootstrap.md` that said the install
takes the release current at install time is corrected. The profile adds the step
the bootstrap does not perform: each client moves to the current release with its
own native command, `claude install latest` and `codex update`. Both commands are in
the installed clients' help (`claude install --help` on client 2.1.287 and
`codex update --help` on codex-cli 0.159.3, read-only, exit 0 each). Claude's
command is also in the official CLI reference, whose command table gives
`claude install [version]` as accepting a version number, `stable` or `latest`
(<https://code.claude.com/docs/en/cli-reference>, read 2026-10-02); the profile
cites that page for the command. An updater
that refuses is recorded with its error and the version actually on PATH; the
anti-pattern log in `docs/harness-defaults.md` records why that version is read
and never assumed (`codex update` did not establish that a versioned launcher's
target had changed). The client's target acceptance then runs on the version that
results, the receipt records per client the floor, the version after the native
update and the acceptance result on that version, and a newer release counts as
installed and not yet qualified until that acceptance has passed on that host. The
step is `UNRUN`.

| Choice | Alternative not taken | What would overturn it |
| --- | --- | --- |
| Installation follows the producer's own rule, so the one measurement row whose measurement returned (`local-model-server`, default Ollama, counted among the manifest's 54 installs) is shown as installed. | Show every row in the `measurement` state as not installed, as the brief words it. That would contradict the manifest's count and the merged decision that settled the local model server. | The producer marks that row as installing nothing, or the owner's record for the local model server changes. |
| Commands come from the page and the generator copies them. | Type them into the generator, or copy them into the profile. | The page stops carrying a block: generation then refuses and names the missing block. |
| Claude's install command in the profile is the documented specific-version form with the pin as its operand. | Keep `bash -s latest`, which contradicts the bootstrap. | The bootstrap is changed to install the current release directly, as the owner's decision says. |
| Every manifest source is bound to its declared SHA-256. | The shape check of the earlier generator. | None; a bound hash only refuses a stale manifest. |
| The shared version rule names Claude Code, whose bootstrap path is a native installer. Codex's receipt floor is the pin that the bootstrap installs. | Say that the bootstrap keeps a newer Codex too: `install_npm` installs the exact pin and Codex's version probe is exact. | The bootstrap gains a keep-newer rule for npm clients. |

**Verification.** The tests grew from 72 to 87. Fifteen are new, and each fails on
the pre-change tree: the old generator exits 1 with `new-wsl-handbook: 'file'`, and
the old profile, outputs and generator lack the new text. In order: `--write` and
then `--check` returned exit 0; the two test modules returned exit 0 (`Ran 87 tests`, `OK`); the
adoption docs-consistency and contract modules returned exit 0 (`Ran 52 tests`,
`OK`, one skip); the reviewer's four mutants (a secret-shaped install command, an
unknown slot id, a changed manifest default and ai-memory picked before its
measurement) were all killed and the files restored. The publication validator
returned exit 1 only for the registered hash and byte count of each changed file,
which the coordinator re-registers. These are local integration checks of
projections of source documents; none is host acceptance, and no install, service
or `wsl.exe` command was run.

| Mistake | Correction | Prevention |
| --- | --- | --- |
| The generator and the test setup read every manifest source as a catalog with a `file`. | Resolve `file` or `path`, build the inventory from the catalogs and the added slots, and bind every source to its declared hash. | A test changes each of the six sources by one byte and expects a refusal that names it; the inventory test holds all 84 rows and the ten added ones. |
| Stage 2's steps carried bootstrap, sign-in and configure commands as typed text. | The steps point at F9 and the commands are F9's block, read from the page. | A test fails when the generator source types those commands or any command line of the page. |
| The version rule said that the install takes the release current at install time, which the bootstrap does not do. | The rule says what the bootstrap does, and the profile adds the native update step. | The rule is byte-enforced across the profile, the overview and the bootstrap page, and a test fails if the old sentence returns. |
| A handbook receipt named frozen hashes that nothing checked. | The receipt's generator, profile and output hashes follow the regenerated files. | The test that the committed outputs are current also compares each frozen hash with its file. |

## Rows and amendments by direct consensus (2026-10-02)

The definitive manifest has its next version: 89 rows, five of them of the row
kind `consensus`, and six rows with an `amendments` list. Both come from the
layer-consensus record, which the manifest names under `sources.consensus` by
`path` and SHA-256; the decision is in
[its own record](2026-10-02-new-wsl-layer-consensus.md). The generator of the
base commit, run on that manifest with `--check`, printed
`new-wsl-handbook: unknown defaults manifest row kind` and exited 1.

Earlier sections stay as written. Their counts (84 rows, 54 installs) describe
the manifest of their day.

**Generator.** The closed set of row kinds gains `consensus`. The
layer-consensus record is parsed as the convergence decisions are, and the rows
it adds join the slot inventory as the producer's `apply_consensus()` adds them.
A row is of kind `consensus` exactly when that record adds it. Such a row is
never definitive and its outcome is none of the rounds' outcomes, which is the
producer's rule. An `amendments` list on a row is accepted when every item has a
date, an author and a decision. Each amendment is printed as one line under its
layer's slot table, and the row's cells stay as the manifest gives them. The
inventory gains the number of amendments, and the slot-decision preamble says
what a consensus row and an amendment are when the manifest has either. A
manifest that names no consensus record is read as before.

| Choice | Alternative not taken | What would overturn it |
| --- | --- | --- |
| An amendment is a line under its layer's table. | Merge it into its row's cells, which would show a decision the rounds did not make as the row's own. | The producer starts to change a row's fields from an amendment. |
| A consensus row must be one that the record adds, and every row the record adds must be a consensus row. | Accept any row that calls itself `consensus`. | None; the check only refuses a manifest that disagrees with its own source. |
| Any outcome that is none of the rounds' outcomes is accepted on a consensus row. | Fix the three outcomes of today's record in the generator. | The producer closes that set. |

**Verification.** In order: `--write` and then `--check` returned exit 0
(`written`, then `passed`); the handbook module returned exit 0
(`Ran 72 tests`, `OK`) and the profile module returned exit 0 (`Ran 17 tests`,
`OK`). The handbook module has two tests more than before: one holds the
consensus rows, the amendment lines and the hashed consensus source against
the manifest, and one changes the real manifest four ways (a row that calls
itself `consensus`, a consensus row relabelled, a consensus row with an outcome
of the rounds, an amendment without its decision) and expects each refusal. The
inventory test now holds 89 rows, the ten added ones and the five consensus
ones. The receipt's generator and output hashes follow the regenerated files;
the profile and its hash did not change. These are local integration checks of
projections of source documents; none is host acceptance, and no install,
service or `wsl.exe` command was run.

A repair of 2026-10-02 adds a fifth change to that test: a consensus row that
calls itself definitive, with its state set to match so that the flag check
passes, which only the rule that a consensus row is never definitive refuses.
With that clause removed from a scratch copy of the generator, the test failed
on that change alone.
