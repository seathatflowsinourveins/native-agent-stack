// Contract tests for tools/compare/closure.mjs: closure is computed by script from sealed protocol + judgments.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const here = dirname(fileURLToPath(import.meta.url))
const script = join(here, '..', '..', 'tools', 'compare', 'closure.mjs')
const run = (protocol, judgments) => {
  const d = mkdtempSync(join(tmpdir(), 'closure-'))
  writeFileSync(join(d, 'p.json'), JSON.stringify(protocol)); writeFileSync(join(d, 'j.json'), JSON.stringify(judgments))
  return JSON.parse(execFileSync(process.execPath, [script, join(d, 'p.json'), join(d, 'j.json')], { encoding: 'utf8' }))
}
const protocol = { layer_id: 'x', protocol_id: 'x-v1', closure_rule: { overturn_if_all: [
  { metric: 'hit', arm: 'B', cmp: '>=', reference: { arm: 'A' }, delta: 0.1 },
  { metric: 'restore', arm: 'B', cmp: '>=', reference: { value: 1 } } ] } }
const refuters = [{ refuted: false, leak: false }, { refuted: false, leak: false }, { refuted: true, leak: false }]
test('flat scores: failed conjunction retains the incumbent', () => {
  const r = run(protocol, { scores: { A: { hit: 0.8, restore: 1 }, B: { hit: 0.5, restore: 1 } }, refuters })
  assert.equal(r.status, 'retain'); assert.equal(r.publication_gate.blocks_publication, false)
})
test('flat scores: satisfied conjunction overturns', () => {
  const r = run(protocol, { scores: { A: { hit: 0.5, restore: 1 }, B: { hit: 0.7, restore: 1 } }, refuters })
  assert.equal(r.status, 'overturn')
})
test('a null on the incumbent side is unresolved even when the condition compares against a constant', () => {
  const r = run(protocol, { scores: { A: { hit: 0.5, restore: null }, B: { hit: 0.7, restore: 1 } }, refuters })
  assert.equal(r.status, 'unresolved'); assert.ok(r.reasons.some((x) => x === 'missing metric restore for A'))
})
test('scores nested under metrics are read and the nested read is reported', () => {
  const r = run(protocol, { scores: { A: { metrics: { hit: 0.5, restore: 1 } }, B: { metrics: { hit: 0.7, restore: 1 } } }, refuters })
  assert.equal(r.status, 'overturn'); assert.ok(r.reasons.includes('scores read from scores[arm].metrics'))
})
test('refuters gate publication only and never change the status', () => {
  const r = run(protocol, { scores: { A: { hit: 0.5, restore: 1 }, B: { hit: 0.7, restore: 1 } }, refuters: [] })
  assert.equal(r.status, 'overturn'); assert.equal(r.publication_gate.blocks_publication, true)
})
test('a judge-reported leak is unresolved', () => {
  const r = run(protocol, { leak: true, scores: { A: { hit: 0.5, restore: 1 }, B: { hit: 0.7, restore: 1 } }, refuters })
  assert.equal(r.status, 'unresolved')
})

// Codex cross-family review (2026-09-22, synthetic_verification cases): a leaking refuter and schema-less refuters
// must block publication; the mechanical status stays independent of the gate.
const gateProtocol = { layer_id: 'synthetic-practice-check', protocol_id: 'synthetic-practice-check-20260922', closure_rule: { overturn_if_all: [
  { metric: 'quality', arm: 'challenger', cmp: '>', reference: { arm: 'incumbent' } } ] } }
const gateScores = { incumbent: { quality: 1 }, challenger: { quality: 2 } }
test('valid control: three boolean verdicts, two not refuted, publishes', () => {
  const r = run(gateProtocol, { scores: gateScores, refuters: [{ refuted: false, leak: false }, { refuted: false, leak: false }, { refuted: true, leak: false }] })
  assert.equal(r.status, 'overturn'); assert.equal(r.publication_gate.blocks_publication, false)
})
test('a refuter reporting a leak blocks publication even when the votes would pass', () => {
  const r = run(gateProtocol, { scores: gateScores, refuters: [{ refuted: false, leak: true }, { refuted: false, leak: false }, { refuted: true, leak: false }] })
  assert.equal(r.status, 'overturn'); assert.equal(r.publication_gate.blocks_publication, true); assert.equal(r.publication_gate.leak_votes, 1)
})
test('refuters without boolean refuted/leak are invalid and block publication', () => {
  const r = run(gateProtocol, { scores: gateScores, refuters: [{}, {}, {}] })
  assert.equal(r.status, 'overturn'); assert.equal(r.publication_gate.blocks_publication, true); assert.equal(r.publication_gate.invalid_refuters, 3); assert.equal(r.publication_gate.valid_refuters, 0)
})
test('a judge leak blocks publication', () => {
  const r = run(gateProtocol, { scores: gateScores, judge_leak: true, refuters: [{ refuted: false, leak: false }, { refuted: false, leak: false }, { refuted: false, leak: false }] })
  assert.equal(r.publication_gate.blocks_publication, true); assert.equal(r.publication_gate.judge_leak, true)
})
