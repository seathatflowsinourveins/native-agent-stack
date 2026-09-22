#!/usr/bin/env node
// Compute a comparison's closure from its sealed protocol and judgments; agents never decide closure.
// Usage: node closure.mjs <protocol.json> <judgments.json> [out.json]
// protocol.closure_rule = { overturn_if_all | overturn_or_admit_if_all: [{metric, arm, cmp, reference: {arm}|{value}, delta?}], insufficient_evidence_rule? }
// Refuter verdicts never enter closure; they are reported as a separate publication_gate.
// judgments = { scores: {"arm-x": {metric: number|null}}, refuters: [{refuted: bool}], leak: bool }
import { readFileSync, writeFileSync } from 'node:fs'
const [pp, jp, out] = process.argv.slice(2)
if (!pp || !jp) { console.error('usage: closure.mjs <protocol.json> <judgments.json> [out.json]'); process.exit(1) }
const P = JSON.parse(readFileSync(pp, 'utf8')), J = JSON.parse(readFileSync(jp, 'utf8'))
const rule = P.closure_rule || {}; const reasons = []; let status = 'retain'
if (J.leak) { status = 'unresolved'; reasons.push('judge reported a label leak') }
// scores may be flat ({arm: {metric: value}}) or nested under a `metrics` key ({arm: {metrics: {metric: value}}}); a nested read is reported.
const nested = !!(J.scores && Object.values(J.scores).some((s) => s && typeof s === 'object' && s.metrics && typeof s.metrics === 'object'))
const val = (arm, m) => { const s = J.scores && J.scores[arm]; if (!s) return null; const src = nested && s.metrics ? s.metrics : s; return src[m] !== undefined ? src[m] : null }
if (nested) reasons.push('scores read from scores[arm].metrics')
const cmp = { '>=': (a, b) => a >= b, '<=': (a, b) => a <= b, '>': (a, b) => a > b, '<': (a, b) => a < b }
let all = true, missing = false
const conditions = rule.overturn_if_all || rule.overturn_or_admit_if_all || []
// Every arm named anywhere in the rule must report every conjunction metric: a null on either side is
// insufficient evidence for that metric, even when the condition compares one arm against a constant.
const arms = [...new Set(conditions.flatMap((c) => [c.arm, c.reference && c.reference.arm].filter((x) => x !== undefined && x !== null)))]
for (const c of conditions) {
  const a = val(c.arm, c.metric); const ref = c.reference && c.reference.arm !== undefined ? val(c.reference.arm, c.metric) : (c.reference ? c.reference.value : null)
  const nullArms = arms.filter((arm) => val(arm, c.metric) === null)
  if (a === null || ref === null || nullArms.length) { missing = true; reasons.push(`missing metric ${c.metric} for ${nullArms.length ? nullArms.join(',') : c.arm + ' or its reference'}`); continue }
  const ok = cmp[c.cmp || '>='](a, ref + (c.delta || 0)); reasons.push(`${c.metric}: ${c.arm}=${a} ${c.cmp || '>='} ${ref}${c.delta ? '+' + c.delta : ''} -> ${ok}`); if (!ok) all = false
}
if (rule.refuter_survival) reasons.push('closure_rule.refuter_survival is ignored: refuters gate publication, not closure')
const conds = conditions.length
if (status !== 'unresolved') status = missing ? 'unresolved' : (conds === 0 ? 'unresolved' : (all ? (P.kind === 'candidate_establishment' ? 'admit' : 'overturn') : 'retain'))
if (conds === 0) reasons.push('no closure conditions declared')
const notRef = (J.refuters || []).filter((r) => !r.refuted).length
const publication_gate = { refuters_reported: (J.refuters || []).length, not_refuted: notRef, blocks_publication: (J.refuters || []).length < 3 || notRef < 2, note: 'publication gate only; closure status above is independent of refuter votes' }
const result = { layer_id: P.layer_id, protocol_id: P.protocol_id, kind: P.kind || 'overturn_comparison', status, reasons, publication_gate, computed_by: 'tools/compare/closure.mjs' }
if (out) writeFileSync(out, JSON.stringify(result, null, 1) + '\n')
console.log(JSON.stringify(result))
