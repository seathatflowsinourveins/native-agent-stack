#!/usr/bin/env node
// LOCAL INTEGRATION TEST (not a native Workflow run): executes the workflow
// script bodies with stub agent/parallel/phase/log hooks to check envelope
// semantics for missing stages, source/claim coverage, and negative evidence.
// Stubs replace model calls entirely; these are not provider E2E observations.
import { readFileSync } from 'node:fs'
function load(file, stubs) {
  const body = readFileSync(new URL(file.split('/').pop(), import.meta.url), 'utf8').replace(/^export const meta/m, 'const meta')
  const fn = new Function('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', 'workflow', 'return (async () => {\n' + body + '\n})()')
  return fn(stubs.args, stubs.agent, stubs.parallel, stubs.pipeline, stubs.phase, stubs.log, stubs.budget, stubs.workflow)
}
const logs = []
const base = { phase: () => {}, log: (m) => logs.push(m), budget: { total: null, spent: () => 0, remaining: () => Infinity }, workflow: async () => { throw new Error('nested') }, pipeline: async () => [] }
const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
let passed = 0, failed = 0
function expect(name, cond) { console.log((cond ? 'PASS ' : 'FAIL ') + name); if (cond) passed++; else failed++ }

// readiness-audit: second reader packet returns null
{
  let n = 0
  const agent = async (prompt, opts) => {
    if (opts.label.startsWith('read:')) { n++; return n === 2 ? null : { summary: 's', claims: [{ claim: 'c' + n, source: 'doc', confidence: 'high' }], open_gates: [], not_found: [] } }
    if (opts.label === 'verify') return { verdicts: [], missing: [], readiness_verdict: 'stub' }
    return null
  }
  const r = await load('.claude/workflows/readiness-audit.js', { ...base, parallel, agent, args: { docs: ['a.md', 'b.md', 'c.md', 'd.md', 'e.md', 'f.md'], question: 'q' } })
  expect('readiness: status is incomplete when a packet is unread', r.status === 'incomplete')
  expect('readiness: unread sources are named in the envelope', Array.isArray(r.unread_sources) && r.unread_sources.length === 2)
  expect('readiness: every packet identity is retained including null result', r.packets.length === 3 && r.packets.filter((p) => p.result === null).length === 1)
  // verifier gets null too
  const r2 = await load('.claude/workflows/readiness-audit.js', { ...base, parallel, agent: async (p, o) => (o.label === 'verify' ? null : { summary: 's', claims: [], open_gates: [], not_found: [] }), args: { docs: ['a.md'] } })
  expect('readiness: status is unverified when the verifier returns null', r2.status === 'unverified')
}
// review-changes: review stage null, and failed check
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const inv = { summary: 's', files: [], changed_behavior: [claim], checks_run: [{ command: 'true', exit: '0', result: 'exited successfully without output' }] }
  const reviewed = { verdicts: [{ claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }], defects: [], gaps: [] }
  const r = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv : null), args: { base: 'HEAD' } })
  expect('review: null review yields incomplete, accepted=false', r.status === 'incomplete' && r.accepted === false)
  const r2 = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async () => null, args: {} })
  expect('review: null inventory yields incomplete, accepted=false', r2.status === 'incomplete' && r2.accepted === false)
  const inv2 = { ...inv, checks_run: [{ command: 'false', exit: '1', result: 'failed' }] }
  const r3 = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv2 : reviewed), args: {} })
  expect('review: failed check yields rejected', r3.status === 'rejected' && r3.accepted === false)
  const r4 = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv : reviewed), args: {} })
  expect('review: clean inventory+review+checks yields accepted', r4.status === 'accepted' && r4.accepted === true)
  const invNone = { ...inv, checks_run: [] }
  const r5 = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? invNone : reviewed), args: { checks: ['required-check-not-executed'] } })
  expect('review: requested check with no returned result yields incomplete, accepted=false', r5.status === 'incomplete' && r5.accepted === false && r5.missing_checks.length === 1)
  const r6 = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv : reviewed), args: { checks: ['true'] } })
  expect('review: requested check with returned exit 0 yields accepted', r6.status === 'accepted' && r6.missing_checks.length === 0)
  const noop = await load('.claude/workflows/review-changes.js', { ...base, parallel, agent: async (p, o) => o.label === 'inventory' ? { ...inv, changed_behavior: [] } : { verdicts: [], defects: [], gaps: [] }, args: {} })
  expect('review: empty claims and verdicts are an incomplete no-op even with a passed check', noop.status === 'incomplete' && noop.accepted === false && noop.reason.includes('no source-cited changed behavior'))
}
// Requested checks require one exact command identity and returned evidence.
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const reviewed = { verdicts: [{ claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }], defects: [], gaps: [] }
  const command = 'node checks/reconcile.mjs'
  const checked = { command, exit: '0', result: '42 reconciliation assertions passed' }
  const run = (checks_run, checks = [command]) => load('.claude/workflows/review-changes.js', { ...base, parallel, args: { paths: ['source.js'], checks }, agent: async (p, o) => o.label === 'inventory' ? { summary: 'reconciliation change', files: [], changed_behavior: [claim], checks_run } : reviewed })
  expect('review: exact requested check with returned evidence is accepted', (await run([checked])).accepted === true)
  for (const [name, results, checks] of [
    ['blank result', [{ ...checked, result: '' }]],
    ['whitespace result', [{ ...checked, result: ' \n ' }]],
    ['missing result', [{ command, exit: '0' }]],
    ['duplicate returned results', [checked, checked]],
    ['blank returned command', [{ ...checked, command: '' }]],
    ['near-match returned command', [{ ...checked, command: command + ' ' }]],
    ['blank exit code', [{ ...checked, exit: ' ' }]],
    ['blank requested command', [{ ...checked, command: ' ' }], [' ']],
    ['duplicate requested command', [checked], [command, command]],
    ['blank supplemental command', [checked, { ...checked, command: '' }]],
  ]) {
    const r = await run(results, checks)
    expect('review: ' + name + ' cannot satisfy check acceptance', r.status === 'incomplete' && r.accepted === false)
  }
  const conflict = await run([checked, { ...checked, exit: '1', result: 'one assertion failed' }])
  expect('review: conflicting duplicate result retains failure and cannot be accepted', conflict.status === 'rejected' && conflict.accepted === false && conflict.evidence_issues.some((x) => x.includes('duplicate returned')))
}
// A returned review must cover every claim exactly once with actual evidence.
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const inv = { summary: 'one change', files: [], changed_behavior: [claim], checks_run: [] }
  const confirmed = { claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }
  const clean = { verdicts: [confirmed], defects: [], gaps: [] }
  const run = (review, inventory = inv) => load('.claude/workflows/review-changes.js', { ...base, parallel, args: {}, agent: async (p, o) => o.label === 'inventory' ? inventory : review })
  expect('review: complete exact claim coverage with evidence is accepted', (await run(clean)).accepted === true)
  const cases = [
    ['missing verdict', { ...clean, verdicts: [] }, 'incomplete'],
    ['unverifiable claim', { ...clean, verdicts: [{ ...confirmed, verdict: 'unverifiable' }] }, 'incomplete'],
    ['refuted claim without separate defect', { ...clean, verdicts: [{ ...confirmed, verdict: 'refuted' }] }, 'rejected'],
    ['corrected claim requires resolution', { ...clean, verdicts: [{ ...confirmed, verdict: 'corrected', correction: 'only some requests are reconciled' }] }, 'rejected'],
    ['non-empty verification gaps', { ...clean, gaps: ['reconciliation has not run'] }, 'incomplete'],
    ['duplicate verdict', { ...clean, verdicts: [confirmed, confirmed] }, 'incomplete'],
    ['blank evidence', { ...clean, verdicts: [{ ...confirmed, evidence: '  ' }] }, 'incomplete'],
    ['near-match claim is not exact coverage', { ...clean, verdicts: [{ ...confirmed, claim: claim.claim + ' ' }] }, 'incomplete'],
    ['extra unrelated verdict', { ...clean, verdicts: [confirmed, { ...confirmed, claim: 'unrelated claim' }] }, 'incomplete'],
    ['invalid verdict value', { ...clean, verdicts: [{ ...confirmed, verdict: 'looks good' }] }, 'incomplete'],
    ['invalid review envelope', { verdicts: [] }, 'incomplete'],
  ]
  for (const [name, review, status] of cases) {
    const r = await run(review)
    expect('review: ' + name + ' fails closed', r.accepted === false && r.status === status)
  }
  for (const [name, changed_behavior] of [
    ['duplicate inventory claims', [claim, claim]],
    ['blank inventory source', [{ ...claim, source: ' ' }]],
    ['blank inventory claim', [{ ...claim, claim: ' ' }]],
  ]) {
    const r = await run(clean, { ...inv, changed_behavior })
    expect('review: ' + name + ' fails closed', r.accepted === false && r.status === 'incomplete')
  }
}
// Readiness completion means a fully evidenced audit, including a negative one.
{
  const claim = { claim: 'paper operation is ready', source: 'readiness.md:8', confidence: 'high' }
  const source = { source: 'readiness.md', outcome: 'observed', evidence: 'readiness.md:8 records the readiness result', exit_code: null }
  const reader = { summary: 'one claim', claims: [claim], open_gates: [], not_found: [], sources: [source] }
  const confirmed = { claim: claim.claim, verdict: 'confirmed', evidence: 'readiness.md:8 documents the result' }
  const sourceConfirmed = { packet_id: 'docs-1', source: source.source, verdict: 'confirmed', evidence: source.evidence }
  const clean = { verdicts: [confirmed], source_verdicts: [sourceConfirmed], missing: [], readiness_verdict: 'Ready within the cited scope' }
  const run = (verify, packet = reader, args = { docs: ['readiness.md'] }) => load('.claude/workflows/readiness-audit.js', { ...base, parallel, args, agent: async (p, o) => o.label === 'verify' ? verify : packet })
  expect('readiness: complete coverage completes the audit', (await run(clean)).status === 'complete')
  expect('readiness: independently established additional facts in conclusion are not missing sources', (await run({ ...clean, readiness_verdict: 'Not ready: independently inspected readiness.md:9 also establishes an unclosed risk gate that the reader omitted.' })).status === 'complete')
  for (const verdict of ['refuted', 'corrected']) {
    const r = await run({ ...clean, verdicts: [{ ...confirmed, verdict, correction: 'paper reconciliation is missing' }], readiness_verdict: 'Not ready: reconciliation is missing' }, { ...reader, open_gates: ['paper reconciliation'] })
    expect('readiness: evidenced ' + verdict + ' claim and open gate complete a negative audit', r.status === 'complete')
  }
  const cases = [
    ['missing claim verdict', { ...clean, verdicts: [] }, 'incomplete'],
    ['missing verifier source', { ...clean, missing: ['readiness.md'] }, 'incomplete'],
    ['unverifiable claim', { ...clean, verdicts: [{ ...confirmed, verdict: 'unverifiable' }] }, 'unverified'],
    ['duplicate verdict', { ...clean, verdicts: [confirmed, confirmed] }, 'incomplete'],
    ['blank evidence', { ...clean, verdicts: [{ ...confirmed, evidence: '\n ' }] }, 'incomplete'],
    ['correction without corrected evidence statement', { ...clean, verdicts: [{ ...confirmed, verdict: 'corrected', correction: '' }] }, 'incomplete'],
    ['non-exact claim', { ...clean, verdicts: [{ ...confirmed, claim: claim.claim + ' ' }] }, 'incomplete'],
    ['extra unrelated verdict', { ...clean, verdicts: [confirmed, { ...confirmed, claim: 'unrelated' }] }, 'incomplete'],
    ['blank readiness conclusion', { ...clean, readiness_verdict: ' ' }, 'unverified'],
    ['invalid verifier envelope', { verdicts: [] }, 'unverified'],
  ]
  for (const [name, verify, status] of cases) expect('readiness: ' + name + ' fails closed', (await run(verify)).status === status)
  for (const [name, packet] of [
    ['reader missing source', { ...reader, not_found: ['readiness.md'] }],
    ['duplicate reader claims', { ...reader, claims: [claim, claim] }],
    ['blank reader source', { ...reader, claims: [{ ...claim, source: ' ' }] }],
    ['blank reader claim', { ...reader, claims: [{ ...claim, claim: ' ' }] }],
    ['omitted document source result', { ...reader, sources: [] }],
    ['legacy packet without source coverage', { ...reader, sources: undefined }],
    ['source not found', { ...reader, sources: [{ ...source, outcome: 'not_found' }] }],
    ['blank returned source evidence', { ...reader, sources: [{ ...source, evidence: ' ' }] }],
    ['duplicate returned source result', { ...reader, sources: [source, source] }],
    ['near-match source identifier', { ...reader, sources: [{ ...source, source: 'readiness.md ' }] }],
    ['extra unrequested source result', { ...reader, sources: [source, { ...source, source: 'other.md' }] }],
  ]) expect('readiness: ' + name + ' fails closed', (await run(clean, packet)).status === 'incomplete')
  for (const [name, source_verdicts] of [
    ['missing source confirmation', []],
    ['legacy verifier without source confirmation', undefined],
    ['duplicate source confirmation', [sourceConfirmed, sourceConfirmed]],
    ['blank source confirmation evidence', [{ ...sourceConfirmed, evidence: ' ' }]],
    ['source confirmation wrong packet', [{ ...sourceConfirmed, packet_id: 'docs-2' }]],
    ['source confirmation wrong identifier', [{ ...sourceConfirmed, source: 'readiness.md ' }]],
    ['refuted source observation', [{ ...sourceConfirmed, verdict: 'refuted' }]],
    ['unverifiable source observation', [{ ...sourceConfirmed, verdict: 'unverifiable' }]],
  ]) expect('readiness: ' + name + ' fails closed', (await run({ ...clean, source_verdicts })).status === 'incomplete')
  expect('readiness: no requested sources is incomplete', (await run(clean, reader, {})).status === 'incomplete')
}
// Source accounting is per requested item, even when another packet has claims.
{
  const docs = ['ready.md', 'gate.md', 'limits.md', 'brokers.md']
  const command = 'check-paper-reconciliation'
  const resultFor = (source, commands) => ({ source, outcome: 'observed', evidence: commands ? 'Returned exit 1: one unreconciled order' : source + ':1 was read', exit_code: commands ? 1 : null })
  const run = (omit, commandOverride = {}, omitClaim = false) => {
    const items = [['docs-1', docs.slice(0, 2)], ['docs-2', docs.slice(2)], ['commands-3', [command]]]
    const sources = items.flatMap(([packet_id, inputs]) => inputs.map((source) => ({ packet_id, source, verdict: 'confirmed', evidence: resultFor(source, packet_id.startsWith('commands')).evidence })))
    return load('.claude/workflows/readiness-audit.js', { ...base, parallel, args: { docs, commands: [command] }, agent: async (p, o) => {
      if (o.label === 'verify') return { verdicts: omitClaim ? [] : [{ claim: 'reconciliation failed', verdict: 'confirmed', evidence: 'check-paper-reconciliation returned 1 with an unreconciled order' }], source_verdicts: sources, missing: [], readiness_verdict: 'Not ready: one unreconciled order' }
      const [packet_id, inputs] = items.find(([id]) => o.label === 'read:' + id)
      const commands = packet_id.startsWith('commands')
      return { summary: 'bounded evidence', claims: commands && !omitClaim ? [{ claim: 'reconciliation failed', source: command, confidence: 'high' }] : [], open_gates: commands ? ['reconciliation failed'] : [], not_found: [], sources: inputs.filter((source) => source !== omit).map((source) => ({ ...resultFor(source, commands), ...(commands ? commandOverride : {}) })) }
    } })
  }
  expect('readiness: executed nonzero command with independently confirmed evidence completes a negative audit', (await run()).status === 'complete')
  for (const source of [...docs, command]) expect('readiness: omitted requested source cannot complete: ' + source, (await run(source)).status === 'incomplete')
  expect('readiness: empty-claim command packet still needs a returned source result', (await run(command, {}, true)).status === 'incomplete')
  expect('readiness: non-executed command cannot complete', (await run(undefined, { outcome: 'not_executed', exit_code: null })).status === 'incomplete')
  expect('readiness: observed command without an integer exit cannot complete', (await run(undefined, { exit_code: null })).status === 'incomplete')
}
// An overall question naming both sources must not expand either reader packet.
{
  const doc = '.claude/settings.json', command = 'node --version'
  const calls = []
  const result = await load('.claude/workflows/readiness-audit.js', { ...base, parallel, args: { docs: [doc], commands: [command], question: 'Check ' + doc + ' and ' + command }, agent: async (prompt, opts) => {
    calls.push({ prompt, opts })
    if (opts.label === 'verify') return { verdicts: [], missing: [], readiness_verdict: 'Both requested sources were observed', source_verdicts: [{ packet_id: 'docs-1', source: doc, verdict: 'confirmed', evidence: 'settings file was read' }, { packet_id: 'commands-2', source: command, verdict: 'confirmed', evidence: 'version command returned v24.21.0 with exit 0' }] }
    const isDoc = opts.label === 'read:docs-1'
    return { summary: 'one source observed', claims: [], open_gates: [], not_found: [], sources: [{ source: isDoc ? doc : command, outcome: 'observed', evidence: isDoc ? 'settings file was read' : 'v24.21.0', exit_code: isDoc ? null : 0 }] }
  } })
  for (const [label, source] of [['read:docs-1', doc], ['read:commands-2', command]]) {
    const { prompt, opts } = calls.find((c) => c.opts.label === label)
    const schema = opts.schema.properties.sources
    expect('readiness: ' + label + ' schema allows only its exact source identifier', JSON.stringify(schema.items.properties.source.enum) === JSON.stringify([source]))
    expect('readiness: ' + label + ' schema requires exactly one source result', schema.minItems === 1 && schema.maxItems === 1)
    expect('readiness: ' + label + ' not_found cannot name another packet source', JSON.stringify(opts.schema.properties.not_found.items.enum) === JSON.stringify([source]))
    expect('readiness: ' + label + ' prompt restricts access despite shared question', prompt.includes('Authorized source identifiers: ' + JSON.stringify([source])) && prompt.includes('relevance context, not permission'))
  }
  expect('readiness: verifier prompt restricts exact packet/item pairings', calls.find((c) => c.opts.label === 'verify').prompt.includes('Emit only the exact (packet.id, item) pairs listed in each packet.items'))
  expect('readiness: correctly partitioned source results complete the audit', result.status === 'complete')
}
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
