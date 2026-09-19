#!/usr/bin/env node
// Selected-text measurement using an upstream tokenizer, never provider accounting.
const { readFileSync } = require('node:fs');
const { createRequire } = require('node:module');
const { createHash } = require('node:crypto');
const path = require('node:path');
const [results, packet] = process.argv.slice(2);
if (!results || !packet || !path.isAbsolute(process.env.TOKENIZER_PREFIX || '')) {
  throw new Error('Usage: TOKENIZER_PREFIX=<isolated npm prefix> node measure_packet.cjs <LEAN results> <packet.json>');
}
const upstream = createRequire(path.join(process.env.TOKENIZER_PREFIX, 'package.json'));
const version = upstream('gpt-tokenizer/package.json').version;
if (version !== '3.4.0') throw new Error('This receipt pins gpt-tokenizer 3.4.0');
const { encode } = upstream('gpt-tokenizer/encoding/o200k_base');
const names = ['BasicTemplateFrameworkAlgorithm-summary.json',
  'BasicTemplateFrameworkAlgorithm-order-events.json', 'stdout.txt'];
const baseline = names.map(name => readFileSync(path.join(results, name), 'utf8')).join('\n');
const selected = readFileSync(packet, 'utf8');
const measure = text => ({ bytes: Buffer.byteLength(text), tokens: encode(text).length,
  sha256: createHash('sha256').update(text).digest('hex') });
const raw = measure(baseline), focused = measure(selected);
console.log(JSON.stringify({ tokenizer: 'gpt-tokenizer', version, encoding: 'o200k_base',
  scope: 'Lossy selection for the engine-summary question; not equal-information compression or provider savings',
  baseline_files: names, baseline_join: 'one newline between files', baseline: raw, packet: focused,
  fewer_selected_text_tokens: raw.tokens - focused.tokens,
  selected_text_reduction_percent: Number(((raw.tokens - focused.tokens) * 100 / raw.tokens).toFixed(2)),
  net_provider_tokens_saved: null }, null, 2));
