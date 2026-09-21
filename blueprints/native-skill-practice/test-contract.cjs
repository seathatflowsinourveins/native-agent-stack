'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const gate = require('./gate.cjs');
const parseResponse = require('./response.cjs');
const cases = require('./cases.json');
const vars = {
  source: 'A source.',
  source_available_at: '2026-09-20T10:00:00Z',
  decision_at: '2026-09-20T11:00:00Z',
};
const response = () => ({
  model: 'jev-1.13.0',
  answers: { verdict: {type: 'choice', choice: 'supported', confidence: 0.9,
    probabilities: {supported: 0.95, contradicted: 0.02, insufficient: 0.03}} },
  usage: {input_tokens: 100, output_tokens: 20},
});

test('late, missing and impossible timestamps cannot become eligible advice', () => {
  for (const source_available_at of [undefined, '', '2026-02-30T10:00:00Z',
    '2026-09-20T12:00:00Z', '2026-09-20T10:00:00', '2026-09-20T25:00:00Z']) {
    const result = JSON.parse(gate('supported', {vars: {...vars, source_available_at}}));
    assert.equal(result.verdict, 'supported');
    assert.equal(result.eligible, false);
    assert.equal(result.disposition, 'reject_evidence');
  }
});

test('the cutoff boundary is inclusive; malformed cutoff fails closed', () => {
  assert.equal(JSON.parse(gate('supported', {vars: {...vars, decision_at: vars.source_available_at}})).eligible, true);
  assert.equal(JSON.parse(gate('supported', {vars: {...vars, decision_at: 'bad'}})).eligible, false);
});

test('gate rejects malformed verdict and absent evidence', () => {
  assert.throws(() => gate('approved', {vars}));
  assert.throws(() => gate('supported', {vars: {...vars, source: ''}}));
});

test('parser refuses drift, missing answers, malformed distributions and unknown usage', () => {
  const mutations = [
    (r) => { r.model = 'jev-latest'; },
    (r) => { delete r.answers.verdict; },
    (r) => { r.answers.verdict.choice = 'trade'; },
    (r) => { r.answers.verdict.confidence = NaN; },
    (r) => { r.answers.verdict.probabilities.supported = -0.2; },
    (r) => { r.answers.verdict.probabilities.supported = 0.1; },
    (r) => { r.answers.verdict.probabilities.unknown = 0; },
    (r) => { delete r.usage; },
    (r) => { r.usage.input_tokens = -1; },
  ];
  for (const mutate of mutations) {
    const data = response(); mutate(data);
    assert.throws(() => parseResponse(data, '', {response: {cached: false}}));
  }
});

test('cached response usage is not counted as new inference', () => {
  assert.equal(parseResponse(response(), '', {response: {cached: false}}).tokenUsage.total, 120);
  const cached = parseResponse(response(), '', {response: {cached: true}});
  assert.equal(cached.tokenUsage.total, 0);
  assert.equal(cached.tokenUsage.numRequests, 0);
  assert.equal(cached.metadata.inference, 'cache');
});

test('frozen fixture labels and future-evidence case are explicit', () => {
  assert.equal(cases.length, 16);
  assert.equal(new Set(cases.map(c => c.description)).size, cases.length);
  for (const c of cases) {
    assert.ok(c.vars.source.trim()); assert.ok(c.vars.claim.trim());
    assert.ok(['supported', 'contradicted', 'insufficient'].includes(c.vars.expected));
    assert.ok(c.metadata.label_origin.includes('before inference'));
  }
  const future = cases.find(c => c.description.startsWith('S6'));
  assert.equal(future.vars.expected, 'supported');
  assert.equal(JSON.parse(gate('supported', {vars: future.vars})).disposition, 'reject_evidence');
});
