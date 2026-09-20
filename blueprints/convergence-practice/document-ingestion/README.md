# Qualified document ingestion and bounded retrieval

The Mac qualification uses **Poppler 26.09.0**, the current upstream release
checked on September 20, 2026. One native extraction attempt passed a frozen
three-page corpus: exact text on each page, two tables containing 24 data cells,
eight positive retrieval queries with source/page/coordinate references, and four
queries that must return no evidence. Invalid PDF input was also refused.
The retained [receipt](accepted/receipt.json) records the execution; running the
[audit](audit.py) verifies its artifacts without pretending to repeat that run.

This closes the small born-digital document ingestion gate on the observed Mac.
It does not qualify arbitrary PDFs, OCR, semantic search, a trading dataset or
other machines. The [source review](source-review.json) selects one sufficient
native extractor; current Docling 2.129.0 and MarkItDown 0.1.7 remain candidates for
specific unmet needs, without adding their dependencies or services here.

## Source to evidence packet

1. Select documents explicitly and establish copying rights. The original
   [Lumen qualification packet](corpus/lumen-qualification.pdf) is synthetic MIT
   material; the unchanged W3C one-page dummy PDF is a format smoke check with
   its [source and notice](corpus/NOTICE.md). No user directories are scanned.
2. Freeze source bytes, revision, layout and expected answers before extraction.
   [freeze.json](freeze.json), [oracle.json](oracle.json) and [plan.json](plan.json)
   were recorded first. The authored PDF was visually checked with the existing
   renderer. Its paragraph values and table cells were not derived from the
   candidate's output. Rebuilding the authored source uses recorded ReportLab
   4.4.9 with deterministic PDF metadata; checked-in PDF bytes are sufficient for
   normal validation.
3. Run upstream `pdftotext -bbox-layout -enc UTF-8` on only the frozen source list.
   The extractor preserves the source hash, page dimensions and word positions.
   Original XML remains beside [parsed output](accepted/extraction.json).
4. Map known table regions and columns to cells. [layout.json](layout.json) is an
   explicit document template, **not an inferred layout detector**. In each
   table record the extracted column headers accompany its values; its page and
   table bounds remain attached. Pages intentionally reuse names and IDs with
   different values to test wrong-page selection.
5. Retrieve exact phrases within one named source and optional page. Results are
   capped at three records and 240 characters per record. Too many or oversized
   matches fail closed and require a narrower query. Zero matches means no
   evidence in that scope; it is not proof the fact is false. The
   [retained answers](accepted/retrieval.json) are evidence excerpts, not model
   answers to arbitrary natural-language questions.
6. Give a worker just the selected excerpt and its citation, with a pointer to
   retained original evidence. No embeddings, provider calls, automatic memory,
   transcript capture or broad document index are added. These architectural
   bounds do not establish a measured token or monetary saving.

## Run the offline artifact checks

From the repository root:

```sh
python3 blueprints/convergence-practice/document-ingestion/audit.py
python3 -m unittest discover -s tests -p test_document_ingestion.py -v
python3 scripts/validate_convergence.py blueprints/convergence-practice/document-ingestion/experiment.json --root . --json
```

These checks verify retained native output, exact oracle answers, integrity,
geometry and rejection behavior. They do not invoke a model or install a parser.
They preserve the broader [convergence contract](../contract-reference.md).

## Build and qualify another explicit Mac prefix

[build-pins.json](build-pins.json) fixes the official source archive, its
independently matched checksum, the Kitware CMake 4.4.3 archive, native pkgconf,
matching FreeType headers and the three reused dylib hashes. Only the runtime
binaries and copied libraries are required after building: the observed prefix
was 7,638,176 bytes before adding license notices. This size excludes build tools,
source, SDK, caches and evidence, and is not a token measure.

Use a **new private directory outside Documents and the repository**. The same
verified CMake binary stalled under Documents and returned immediately from the
separate directory; [preflight.json](preflight.json) retains that location failure
and the failed first configure. No security attributes, global permissions or
system installation were changed. This is a host observation, not a diagnosis of
macOS generally.

The [bootstrap recipe](bootstrap.py) requires Python 3.14, Apple developer tools,
and an existing exact dependency prefix with `lib/`. Supply that prefix explicitly;
the script verifies its hashes before copying. It does not silently download a
replacement dependency tree if another host differs. `QUAL_DIR` and
`BUNDLED_POPPLER_PREFIX` below are paths you select for that host.

```sh
python3 blueprints/convergence-practice/document-ingestion/bootstrap.py \
  --workspace "$QUAL_DIR" --bundle "$BUNDLED_POPPLER_PREFIX"
python3 "$QUAL_DIR/fixture/ingest.py" \
  --pdftotext "$QUAL_DIR/prefix/bin/pdftotext" \
  --output "$QUAL_DIR/attempt-1"
```

The bootstrap is reconstructed from the successful native command sequence;
its offline review is separate from the original build receipt. It produces
`built_not_yet_qualified`, and extraction acceptance remains required. New output
folders preserve prior attempts. Review native errors and the private logs before
changing a pin. Native result hashes can differ with compiler, SDK and build path;
the artifact and answer checks establish the semantic contract on a new host.

Keep the existing bundled parser intact for rollback. Remove only an owned
qualification prefix when its evidence is retained and it is no longer in use.
This recipe neither promotes a global default nor changes a client configuration.
No binary is redistributed in this repository; source and dependency licenses
remain applicable to any future binary packaging.

## Limits and the next decision

The minimal native build disables network access, image codecs, signatures,
font subsetting, OCR and language wrappers. Extra Poppler CMap data is absent.
The accepted corpus uses Latin born-digital text, one font size per line and known
table geometry. PDF rendering and extraction are distinct checks. The upstream
full Poppler test corpus was not installed or executed.

The next useful qualification is a separately frozen, license-permitted corpus
of real multi-column reports, difficult tables and scanned pages. Record its
failures first. Adopt Docling or another specialized pipeline only when it passes
that task's provenance and answer checks with justified local inference/runtime
costs. The current small designed corpus is not a held-out general retrieval
benchmark, and existing held-out retrieval experiments were not repeated.
