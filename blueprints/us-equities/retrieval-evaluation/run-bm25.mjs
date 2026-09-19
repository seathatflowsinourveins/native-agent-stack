#!/usr/bin/env node
// Invoke the pinned upstream benchmark on a disposable SQLite snapshot only.
import { parseArgs } from 'node:util';
import { readFileSync, writeFileSync, existsSync, realpathSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const { values } = parseArgs({ options: {
  package: { type: 'string' }, snapshot: { type: 'string' },
  fixture: { type: 'string' }, output: { type: 'string' },
} });
for (const key of ['package', 'snapshot', 'fixture', 'output']) {
  if (!values[key]) throw new Error(`--${key} is required`);
}
const pkg = realpathSync(values.package);
const snapshot = realpathSync(values.snapshot);
const fixturePath = realpathSync(values.fixture);
const output = resolve(values.output);
if (existsSync(output)) throw new Error('Choose a new output path; existing evidence is preserved');
if (!snapshot.endsWith('/catalog-snapshot.sqlite')) throw new Error('Use a disposable catalog-snapshot.sqlite');
const version = JSON.parse(readFileSync(join(pkg, 'package.json'), 'utf8')).version;
if (version !== '2.8.3') throw new Error('Review a changed upstream version before running this recipe');
const fixtureBytes = readFileSync(fixturePath);
const fixture = JSON.parse(fixtureBytes);
if (fixture.collection !== 'us-equities-foundation' || fixture.queries.length !== 12) {
  throw new Error('This acceptance is scoped to the reviewed 12-query foundation fixture');
}
const sha = value => createHash('sha256').update(value).digest('hex');
const moduleHashes = Object.fromEntries([
  'dist/bench/bench.js', 'dist/bench/score.js', 'dist/index.js', 'dist/store.js',
].map(name => [name, sha(readFileSync(join(pkg, name)))]));
const { runBenchmark } = await import(pathToFileURL(join(pkg, 'dist/bench/bench.js')).href);
const { createStore } = await import(pathToFileURL(join(pkg, 'dist/index.js')).href);

// The CLI does not forward the backend selector in this pinned version.
// Do not call the all-backend CLI or createStore on the active index.
const native = await runBenchmark(fixturePath, {
  dbPath: snapshot, collection: fixture.collection, backends: ['bm25'], json: true,
});
const audit = [];
const store = await createStore({ dbPath: snapshot });
try {
  for (const query of fixture.queries) {
    const expected = query.expected_files.map(path => `qmd://${fixture.collection}/${path}`);
    let recovered = [], error = null;
    try {
      // Upstream benchmark catches backend errors as zero scores. This direct
      // lexical replay preserves whether an empty result was a real miss.
      recovered = (await store.searchLex(query.query, {
        collection: fixture.collection, limit: Math.max(query.expected_in_top_k, 10),
      })).map(result => result.filepath);
    } catch (cause) {
      error = { name: cause.name, message: String(cause.message).slice(0, 1000) };
    }
    const result = native.results.find(row => row.id === query.id).backends.bm25;
    const sameResults = JSON.stringify(result.top_files) === JSON.stringify(recovered);
    const matched = k => expected.filter(id => recovered.slice(0, k).includes(id));
    const first = recovered.findIndex(id => expected.includes(id));
    const exact = {
      recall_at_1: matched(1).length / expected.length,
      recall_at_3: matched(3).length / expected.length,
      recall_at_5: matched(5).length / expected.length,
      reciprocal_rank: first < 0 ? 0 : 1 / (first + 1),
      matched_at_3: matched(3), missing_at_3: expected.filter(id => !matched(3).includes(id)),
    };
    audit.push({ id: query.id, question: query.question, query: query.query,
      expected_ids: expected, retrieved_ids: recovered, direct_search_error: error,
      native_replay_identical: sameResults, exact_path_audit: exact,
      native_recall_at_3: result.recall_at_3,
      native_and_exact_recall_at_3_agree: result.recall_at_3 === exact.recall_at_3 });
  }
} finally {
  await store.close();
}
const failed = audit.some(row => row.direct_search_error || !row.native_replay_identical);
const mean = key => audit.reduce((total, row) => total + row.exact_path_audit[key], 0) / audit.length;
const receipt = {
  schema_version: 1, observed_at_utc: new Date().toISOString(),
  status: failed ? 'retrieval_execution_error' : 'completed_with_scores_and_misses_preserved',
  qmd_version: version, collection: fixture.collection, query_count: audit.length,
  fixture_sha256: sha(fixtureBytes), upstream_module_sha256: moduleHashes,
  native_summary: native.summary, native_results: native.results,
  exact_path_audit_summary: {
    mean_recall_at_1: mean('recall_at_1'), mean_recall_at_3: mean('recall_at_3'),
    mean_recall_at_5: mean('recall_at_5'), mean_reciprocal_rank: mean('reciprocal_rank'),
    queries_with_gold_at_3: audit.filter(row => row.exact_path_audit.matched_at_3.length).length,
    queries_without_gold_at_3: audit.filter(row => !row.exact_path_audit.matched_at_3.length).length,
    native_recall_at_3_disagreements: audit.filter(row => !row.native_and_exact_recall_at_3_agree).length,
  },
  per_query_audit: audit,
  model_calls: 0, embedding_downloads_requested: false,
  active_index_passed_to_qmd: false, net_provider_tokens_saved: null,
};
writeFileSync(output, JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
if (failed) process.exitCode = 1;
