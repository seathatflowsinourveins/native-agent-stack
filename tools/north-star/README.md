# North-star readiness receipts

`build_readiness.py` produces `catalogs/north-star/readiness.json` from the explicit
retained sources in `sources.json`. It reads local files and hashes their exact
bytes before extracting values. It performs no installations, SDK calls, broker
operations, gate adjudications or publication.

Each factual field contains a value, a status and a receipt root/path/SHA-256 plus
an exact JSON Pointer or text locator. `RECORDED` means that the named bytes contain
the value. `UNVERIFIED` covers missing, changed, malformed, ambiguous or insufficient
evidence. Neither status grants a new designated-reader approval. Source labels,
section identifiers, titles in the source specification and computed counts are
view metadata; their source specification has its own complete digest.

The layers retain the foundation catalog's many-to-many tool selection. Selection
pins and recorded stack pins remain separate, and a disagreement is visible.
Documented install/acceptance commands are examples, with their original execution
status. Supporting registered receipts carry their own measured digest and kind;
their presence does not establish a current pin-bound installation or a fresh
session. Missing installation and invocation proof stays `UNVERIFIED`.

The SDK producer supplies normalized item receipts. Each row must bind a complete
item digest, identify the same item, and copy the immutable receipt fields exactly.
The builder also checks a raw receipt binding when the normalized receipt supplies
one. Native checks, fresh-client operations, evidence classes, limits and pending
designated-reader fields remain separate. A matching digest authenticates no signer
and does not turn a probe into comparative, broker or strategy acceptance.

## Generate and check

From the repository root, on the host holding the retained receipts:

```sh
nice -n 10 ionice -c2 -n7 python3 -I tools/north-star/build_readiness.py --write
nice -n 10 ionice -c2 -n7 python3 -I tools/north-star/build_readiness.py --check
```

`--root` and `--state-root` select the checkout and durable state directory. The
default state root is `~/.local/state/native-agent-stack`. Paths in the source
specification are relative to one of those two roots. A checkout without the host
receipts renders the corresponding claims `UNVERIFIED`; it cannot inherit that
host's readiness. No wall-clock timestamp is injected into generated JSON, so
unchanged receipt bytes and selectors produce identical output.

To produce a reviewable HTML fragment for the existing readiness page:

```sh
nice -n 10 ionice -c2 -n7 python3 -I tools/north-star/build_readiness.py --check \
  --html-fragment ~/.local/state/native-agent-stack/research/fullspeed-20261008/ns-readiness-manifest/readiness-fragment.html
```

The fragment uses the existing page's section/table elements. Its generation does
not edit the command center's durable page. The page custodian inserts or refreshes
that section through its own publication route.

The finite publisher is prepared for that custodian. Preview its output hashes
against the exact approved page bytes:

```sh
nice -n 10 ionice -c2 -n7 python3 -I tools/north-star/build_readiness.py --check \
  --publish-page ~/.local/state/native-agent-stack/coordination/command-center/pages/north-star-readiness.html \
  --expected-page-sha256 <approved-page-sha256> --dry-run
```

After the custodian's publication cue, the same command without `--dry-run` adds
or replaces one managed fragment, keeps surrounding markup, and retains a byte
backup named with the preceding page hash. It refuses changed page bytes, ambiguous
anchors, malformed managed markers and symlink targets. A repeated refresh replaces
the same block. It creates no service or watcher. The hash guard checks the input
bytes; it is not a concurrent multi-writer lock. The CC remains the sole page
custodian. Older narrative/card material outside the managed block keeps its dated
scope until that custodian reconciles it.

## Refresh on a gate change

After the accepted gate-change receipt arrives, update that gate's source path,
complete digest and exact selector in `sources.json`, then run `--write` and
`--check`. Rehash the resulting JSON and publish the lane's READY record with its
new digest. Immutable receipt changes invalidate their bound claims rather than
silently granting a new pass. SDK `rows.json` is bound to the producer's sealed
handoff digest. A replacement handoff cue updates that binding before rebuilding;
each item remains individually pinned to its immutable normalized receipt.

The existing command-center status/ledger notification consumer is the integration
point for calling this sequence. Deployment of that external handler and insertion
of the HTML fragment are separate custodian actions; this repository change does
not claim they have occurred. There is no additional polling daemon or GitHub API
call. A new receipt outside the declared source set needs an explicit source-index
update; rebuilding alone cannot select or accept that receipt.

The generated view reads `manifests/evidence.json` as an input. Registering this
same output's digest inside that input would create a circular hash dependency;
the view therefore records its own digest in the lane's publication receipt.
Existing registered supporting receipt hashes are checked against their retained
bytes. Run `python3 scripts/validate.py` before committing manifest/evidence changes.

Exported receipt values represent personal home prefixes as `${USER_HOME}` while
preserving their source digests and locators. This is an explicit display
representation; expanding the placeholder uses the receipt host's own home path.
Local session/task identifiers use `${LOCAL_SESSION_ID}`/`${LOCAL_TASK_HANDLE}`
placeholders. Missing-file reasons contain no absolute host path. Original
immutable bytes remain in their retained receipt rather than the exported view.

Focused adapter tests:

```sh
nice -n 10 ionice -c2 -n7 python3 -I -m unittest discover -s tests -p test_north_star_readiness.py
```

## SOTA sources

- The repository reference adapter is
  `native-agent-stack@a484989a43f70ff2575b6fb054cf00c9834e7679:scripts/component_matrix.py:1231`
  (`--check`/`--write`, deterministic receipt joins). Strict JSON input follows
  `scripts/validate_convergence.py:22` at that same revision. This adapter adds the
  repository-specific readiness selectors rather than replacing either implementation.
- Installed Python 3.13.16 and its maintained library documentation:
  [json](https://docs.python.org/3.13/library/json.html),
  [hashlib](https://docs.python.org/3.13/library/hashlib.html),
  [pathlib](https://docs.python.org/3.13/library/pathlib.html), and
  [html](https://docs.python.org/3.13/library/html.html).
  Duplicate-key hooks, non-JSON constant rejection and `allow_nan=False` use the
  supported standard-library interfaces.
- [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901) defines JSON Pointer, including
  valid array indices and `~0`/`~1` escapes. The adapter rejects negative indices
  and leading-zero array indices rather than applying Python indexing semantics.
- [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
  and [ResourceDescriptor](https://github.com/in-toto/attestation/blob/main/spec/v1/resource_descriptor.md)
  document artifact identity by digest. This local view is not a signed in-toto statement.
- [SLSA v1.2 provenance](https://slsa.dev/spec/v1.2/provenance) and
  [artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts) distinguish
  declared input identity from verification and trust policy. Deterministic
  `sort_keys` JSON here is not an RFC 8785 canonicalization claim.

Live source inspection and installed-library probes are retained in
`research/fullspeed-20261008/ns-readiness-manifest/upstream-research.md` under the
durable state root. Adapter tests and publication validation are recorded separately.
