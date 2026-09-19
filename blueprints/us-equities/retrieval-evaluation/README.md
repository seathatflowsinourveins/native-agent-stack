# Measured lexical retrieval — September 19, 2026

QMD **2.8.3** evaluated twelve fixed research questions against a snapshot of the
existing `us-equities-foundation` collection. **Eight of twelve questions retrieved
their intended source in the top three; four did not.** This establishes a measured baseline
and a retrieval gap, not robust general RAG or complete financial research.

The [fixture](fixture.json) records the actual query, underlying question,
reviewed intended source and source hash. Its queries were frozen before the
first execution and were not rewritten to improve the displayed scores.
All 18 collection documents match their repository bytes at commit
`bfd03bc`, and all indexed content hashes verify. See the
[source manifest](source-manifest.json) and [full bounded receipt](receipt.json).

QMD applies its collection filter after BM25 scoring against the shared FTS
index. The eligible results are the 18 foundation documents, while document-frequency
and length statistics include **all 33 documents across three collections**.
The [full corpus manifest](full-corpus-manifest.json) pins all 33 repository
sources, indexed bodies, FTS titles and paths. Every source matches `bfd03bc`.
Recreating only the 18 eligible documents would change this scoring corpus.
The native candidate limit is 100, larger than this entire index, so candidate
starvation is not a concern in this recorded run.

| Measurement | Actual result |
| --- | ---: |
| Native benchmark and direct lexical replay | 12/12 identical; no replay errors |
| Exact intended-source recall@1 | 5/12 = 41.67% |
| Exact intended-source recall@3 | 8/12 = 66.67% |
| Exact intended-source recall@5 | 9/12 = 75.00% |
| Exact mean reciprocal rank, at most 10 returned documents | 0.56875 |
| Native reported recall@1 | 0.50000 |
| Native reported recall@3 | 0.6666666666666666 |
| Native reported MRR | 0.6104166666666667 |
| Native mean lexical search latency | 0.8333333333333334 ms |
| New model calls / embedding downloads | 0 / 0 |

These are small, warm, local-document measurements. Search latency excludes
process startup and is not a production latency benchmark. Every query has one
intended source; the gold list does not judge every potentially relevant summary.
The fixed queries mix natural wording and terse keywords. This tests raw lexical
retrieval, not an agent's complete query-crafting workflow.

## Upstream scoring requires care

The native benchmark's `precision_at_k` divides hits by
`min(k, expected_file_count)`, **not the conventional precision denominator k**.
Its path matcher lowercases paths and accepts suffixes in either direction.
Consequently root `README.md` can match `deerflow/README.md`: for the ACP query,
native recall@1 is 1 while the exact intended source is at rank 2. The receipt
preserves native results and presents a separately labelled, case-sensitive,
full-`qmd://`-identifier audit. No upstream code was patched.

The native benchmark also catches backend exceptions and returns zero scores.
Every query was replayed directly through upstream `store.searchLex` to expose
that ambiguity. The two empty result sets were genuine empty lexical results;
none of the twelve replays raised an error. An exit code alone is not a quality
pass, and the four top-three misses remain visible.

## Misses and the fallback workflow

| Fixed query | Intended source | Observed rank |
| --- | --- | --- |
| `machine failure recover backup key` | `hosting/backup/README.md` | No results |
| `cached reasoning tokens included` | `workers/README.md` | 5 |
| `stop worker orphan subprocess` | `research-runtime/README.md` | No results |
| `selected text provider savings` | `research-runtime/README.md` | 8 |

The empty queries are consistent with lexical vocabulary mismatch: the guides
use host/password and cancellation/descendants. The other misses are ranking
gaps; their intended sources exist in the index. Do not interpret any miss as
evidence that the underlying capability or document is absent.

For real tasks, keep the explicit collection, inspect up to ten candidates, then
read the selected source. When no candidate answers the question, preserve the
original miss and make one deliberate lexical reformulation using domain terms.
These are supported fallback commands, **not an executed improvement experiment**:

```sh
qmd --index native-agent-stack-catalog search "$LEXICAL_QUERY" \
  -c us-equities-foundation -n 10 --format json
qmd --index native-agent-stack-catalog get "$SELECTED_QMD_URI"
```

The installed upstream `qmd skill show` recommends agent-authored `intent:` plus
`lex:`, `vec:` and `hyde:` fields for conceptual retrieval, and BM25 for exact
anchors. It explicitly supports stronger lexical terms when model-backed search
is unavailable. This collection currently uses that lexical lane. Start with
domain keywords, search, read the source, and reformulate once if needed; preserve
the original miss. Neither structured hybrid retrieval nor the effectiveness of
this fallback was measured by this baseline.

Do not answer from a snippet alone or claim the reformulation fixes general
retrieval. A future comparison needs new held-out questions and fixed relevance
judgments. Hybrid search/expansion/reranking requires separate model and quality
acceptance; none was enabled here.

## Exact native API workflow

The shipped CLI exposes `qmd bench`, but this version does **not** forward its
module's `backends` selector. Plain `qmd bench` selects all four backends and can
request models. There is no supported `--backends bm25` CLI flag in this pin.
The small [invocation](run-bm25.mjs) calls the shipped upstream function with
`backends: ['bm25']`, explicit database and collection. This is an upstream
module API invocation; the module path is internal and must be reviewed on upgrade.

Opening a QMD store runs schema initialization and can migrate an older database.
Therefore **do not point this benchmark at the active index**. Use Python's
SQLite online backup through a read-only source connection, with a fresh private
directory. Set `ACTIVE_QMD_DB`, `NEW_PRIVATE_DIR`, `QMD_PACKAGE` and `STACK_REPO`
to explicit absolute paths; the package is the installed `@tobilu/qmd` directory.

```sh
python3 - "$ACTIVE_QMD_DB" "$NEW_PRIVATE_DIR" <<'PY'
import pathlib, sqlite3, sys, os
source = pathlib.Path(sys.argv[1]).resolve(strict=True)
directory = pathlib.Path(sys.argv[2])
directory.mkdir(mode=0o700)  # Existing directories are deliberately refused.
destination = directory / 'catalog-snapshot.sqlite'
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
    with sqlite3.connect(destination) as copied:
        original.backup(copied)
os.chmod(destination, 0o600)
PY

CI=true node "$STACK_REPO/blueprints/us-equities/retrieval-evaluation/run-bm25.mjs" \
  --package "$QMD_PACKAGE" \
  --snapshot "$NEW_PRIVATE_DIR/catalog-snapshot.sqlite" \
  --fixture "$STACK_REPO/blueprints/us-equities/retrieval-evaluation/fixture.json" \
  --output "$NEW_PRIVATE_DIR/results.json" \
  > "$NEW_PRIVATE_DIR/native.stdout.json" 2> "$NEW_PRIVATE_DIR/native.stderr"
```

The accepted command used a minimal environment and the installed native Node.
`CI=true` additionally disables real LLM operations in QMD's LlamaCpp layer; only lexical
search is selected. No external configuration is synchronized, no collections
are rebuilt and no `qmd update`, `embed` or `pull` command runs. The copied database
remained byte-identical before and after this accepted run. The raw native stdout
includes a local fixture path and stays private. Public results retain exact
source identifiers and scores without that host path.

This does not evaluate SocratiCode embeddings, memory isolation, answer accuracy,
full agent outcomes or token savings. Provider tokens saved remain unknown.

## Reviewed upstream implementation

Latest stable identity was checked on September 19: QMD `v2.8.3`, released
August 16, 2026; commit `facd35e01359e59d938bc9418e93fb9318addee3`; MIT.
Installed module hashes are retained in the receipt.

- [CLI benchmark dispatch](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/cli/qmd.ts#L4715): no backend selector forwarded.
- [Benchmark implementation](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/bench.ts#L325): explicit backend option and database selection.
- [Scoring implementation](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/score.ts#L26): suffix matching and score denominators.
- [Store initialization](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/index.ts#L352): schema initialization, optional config synchronization and lazy models.
- [FTS search and collection filtering](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts): BM25 statistics span the shared FTS table before eligible result filtering.
- [Fixture contract](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/types.ts): expected files, query classes and result fields.
