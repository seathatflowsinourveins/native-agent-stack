#!/usr/bin/env node
'use strict';
// Install upstream gpt-tokenizer@3.4.0 into an isolated prefix first.
const { createRequire } = require('node:module');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const prefix = process.env.TOKENIZER_PREFIX;
if (!prefix || !path.isAbsolute(prefix)) {
  throw new Error('Set TOKENIZER_PREFIX to the absolute isolated npm prefix containing gpt-tokenizer@3.4.0.');
}
const nativeRequire = createRequire(path.join(prefix, 'package.json'));
const version = nativeRequire('gpt-tokenizer/package.json').version;
if (version !== '3.4.0') throw new Error(`Expected tokenizer3.4.0, found ${version}`);
const { encode } = nativeRequire('gpt-tokenizer/encoding/o200k_base');
const files = process.argv.includes('--observability')
  ? ['evidence/artifacts/observability-metrics.source.json', 'evidence/artifacts/observability-metrics.selected.json']
  : process.argv.includes('--catalog')
  ? ['evidence/artifacts/catalog-models.full.txt', 'evidence/artifacts/catalog-models.selected.txt']
  : ['evidence/artifacts/usage-report.source.txt', 'evidence/artifacts/retrieved-code.txt'];
const counts = files.map(file => ({ file, tokens: encode(readFileSync(path.join(root, file), 'utf8')).length }));
console.log(JSON.stringify({ tokenizer: 'gpt-tokenizer', version, encoding: 'o200k_base', counts,
  removed: counts[0].tokens - counts[1].tokens,
  reduction_percent: 100 * (counts[0].tokens - counts[1].tokens) / counts[0].tokens,
  scope: 'Public sanitized artifact selection only; not a provider savings measurement.' }, null, 2));
