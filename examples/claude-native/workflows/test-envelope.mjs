#!/usr/bin/env node
// LOCAL INTEGRATION TEST (not a native Workflow run): executes the workflow
// script bodies with stub agent/parallel/phase/log hooks to check envelope
// semantics for missing stages, source/claim coverage, and negative evidence.
// Stubs replace model calls entirely; these are not provider E2E observations.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
// Every path is resolved from this file, so the same file runs in a project's
// .claude/{agents,workflows} and in a portable examples/{agents,workflows} tree.
// Project bindings (settings, instructions, contract doc) come from the sibling
// contract.config.json; a configured file that is missing is a failure, never a skip.
const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const CONFIG = JSON.parse(readFileSync(join(HERE, 'contract.config.json'), 'utf8'))
const configured = (key) => resolve(HERE, typeof CONFIG[key] === 'string' ? CONFIG[key] : '\0missing-' + key)
// A missing configured file is reported by the config assertions and reads as empty
// afterwards, so the suite always reaches its SUMMARY line.
const readOr = (path) => { try { return readFileSync(path, 'utf8') } catch { return '' } }
const WF = { review: 'workflows/review-changes.js', readiness: 'workflows/readiness-audit.js' }
// The one effort every saved workflow stage and project agent binds (since 2026-09-23; decision
// docs/decisions/2026-09-23-max-effort-default.md in the catalog). The coordinator stays at xhigh under
// ultracode: a stage with no effort of its own and no agent frontmatter effort inherits that xhigh, and
// CLAUDE_CODE_EFFORT_LEVEL overrides every child's effort, so max is bound per stage and per agent and the
// settings leave that variable unset.
const STAGE_EFFORT = 'max'
function load(file, stubs) {
  const body = readFileSync(join(ROOT, file), 'utf8').replace(/^export const meta/m, 'const meta')
  const fn = new Function('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', 'workflow', 'return (async () => {\n' + body + '\n})()')
  return fn(stubs.args, stubs.agent, stubs.parallel, stubs.pipeline, stubs.phase, stubs.log, stubs.budget, stubs.workflow)
}
const logs = []
const base = { phase: () => {}, log: (m) => logs.push(m), budget: { total: null, spent: () => 0, remaining: () => Infinity }, workflow: async () => { throw new Error('nested') }, pipeline: async () => [] }
const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
let passed = 0, failed = 0
function expect(name, cond) { console.log((cond ? 'PASS ' : 'FAIL ') + name); if (cond) passed++; else failed++ }
// A file binding must name a file and a *_dir binding a directory; a bare existence check accepts either.
const kindOf = (p) => { try { return statSync(p).isDirectory() ? 'directory' : 'file' } catch { return 'missing' } }
for (const key of Object.keys(CONFIG).filter((k) => k !== 'contract_heading')) expect('config: ' + key + ' resolves to an existing ' + (key.endsWith('_dir') ? 'directory' : 'file'), typeof CONFIG[key] === 'string' && kindOf(configured(key)) === (key.endsWith('_dir') ? 'directory' : 'file'))
expect('config: contract_heading names the documented contract section', typeof CONFIG.contract_heading === 'string' && CONFIG.contract_heading.startsWith('## ') && readOr(configured('contract_doc')).includes('\n' + CONFIG.contract_heading + '\n'))

// readiness-audit: second reader packet returns null
{
  let n = 0
  const agent = async (prompt, opts) => {
    if (opts.label.startsWith('read:')) { n++; return n === 2 ? null : { summary: 's', claims: [{ claim: 'c' + n, source: 'doc', confidence: 'high' }], open_gates: [], not_found: [] } }
    if (opts.label === 'verify') return { verdicts: [], missing: [], readiness_verdict: 'stub' }
    return null
  }
  const r = await load(WF.readiness, { ...base, parallel, agent, args: { docs: ['a.md', 'b.md', 'c.md', 'd.md', 'e.md', 'f.md'], question: 'q' } })
  expect('readiness: status is incomplete when a packet is unread', r.status === 'incomplete')
  expect('readiness: unread sources are named in the envelope', Array.isArray(r.unread_sources) && r.unread_sources.length === 2)
  expect('readiness: every packet identity is retained including null result', r.packets.length === 3 && r.packets.filter((p) => p.result === null).length === 1)
  // verifier gets null too
  const r2 = await load(WF.readiness, { ...base, parallel, agent: async (p, o) => (o.label === 'verify' ? null : { summary: 's', claims: [], open_gates: [], not_found: [] }), args: { docs: ['a.md'] } })
  expect('readiness: status is unverified when the verifier returns null', r2.status === 'unverified')
}
// review-changes: review stage null, and failed check
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const inv = { summary: 's', files: [], changed_behavior: [claim], checks_run: [{ command: 'true', exit: '0', result: 'exited successfully without output' }] }
  const reviewed = { verdicts: [{ claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }], defects: [], gaps: [] }
  const r = await load(WF.review, { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv : null), args: { base: 'HEAD' } })
  expect('review: null review yields incomplete, accepted=false', r.status === 'incomplete' && r.accepted === false)
  const r2 = await load(WF.review, { ...base, parallel, agent: async () => null, args: {} })
  expect('review: null inventory yields incomplete, accepted=false', r2.status === 'incomplete' && r2.accepted === false)
  const inv2 = { ...inv, checks_run: [{ command: 'false', exit: '1', result: 'failed' }] }
  const r3 = await load(WF.review, { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv2 : o.label === 'recheck' ? { checks_run: inv2.checks_run } : reviewed), args: {} })
  expect('review: failed check yields rejected', r3.status === 'rejected' && r3.accepted === false)
  const r4 = await load(WF.review, { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv : o.label === 'recheck' ? { checks_run: inv.checks_run } : reviewed), args: {} })
  expect('review: clean inventory+review+checks yields accepted', r4.status === 'accepted' && r4.accepted === true)
  const invNone = { ...inv, checks_run: [] }
  const r5 = await load(WF.review, { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? invNone : o.label === 'recheck' ? { checks_run: invNone.checks_run } : reviewed), args: { checks: ['required-check-not-executed'] } })
  expect('review: requested check with no returned result yields incomplete, accepted=false', r5.status === 'incomplete' && r5.accepted === false && r5.missing_checks.length === 1)
  const r6 = await load(WF.review, { ...base, parallel, agent: async (p, o) => (o.label === 'inventory' ? inv : o.label === 'recheck' ? { checks_run: inv.checks_run } : reviewed), args: { checks: ['true'] } })
  expect('review: requested check with returned exit 0 yields accepted', r6.status === 'accepted' && r6.missing_checks.length === 0)
  const noop = await load(WF.review, { ...base, parallel, agent: async (p, o) => o.label === 'inventory' ? { ...inv, changed_behavior: [] } : { verdicts: [], defects: [], gaps: [] }, args: {} })
  expect('review: empty claims and verdicts are an incomplete no-op even with a passed check', noop.status === 'incomplete' && noop.accepted === false && noop.reason.includes('no source-cited changed behavior'))
}
// Requested checks require one exact command identity and returned evidence.
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const reviewed = { verdicts: [{ claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }], defects: [], gaps: [] }
  const command = 'node checks/reconcile.mjs'
  const checked = { command, exit: '0', result: '42 reconciliation assertions passed' }
  const run = (checks_run, checks = [command]) => load(WF.review, { ...base, parallel, args: { paths: ['source.js'], checks }, agent: async (p, o) => o.label === 'inventory' ? { summary: 'reconciliation change', files: [{ path: 'source.js', change: 'reconciles each request' }], changed_behavior: [claim], checks_run } : o.label === 'recheck' ? { checks_run } : reviewed })
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
// Acceptance commands are reproduced by a second worker and compared in code.
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const reviewed = { verdicts: [{ claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }], defects: [], gaps: [] }
  const command = 'node checks/reconcile.mjs'
  const first = { command, exit: '0', result: '42 reconciliation assertions passed' }
  const labels = []
  let inventoriedFiles = [{ path: './source.js', change: 'reconciles each request' }]
  const run = (recheck, checks = [command]) => load(WF.review, { ...base, parallel, args: { paths: ['source.js'], checks }, agent: async (p, o) => { labels.push(o.label); return o.label === 'inventory' ? { summary: 's', files: inventoriedFiles, changed_behavior: [claim], checks_run: checks.length ? [first] : [] } : o.label === 'recheck' ? recheck : reviewed } })
  const same = await run({ checks_run: [first] })
  expect('recheck: the same exit in two independent runs is accepted and says so', same.accepted === true && same.reason.includes('two independent runs') && same.recheck.checks_run.length === 1)
  const none = await run(null)
  expect('recheck: a null recheck cannot be accepted', none.status === 'incomplete' && none.evidence_issues.some((x) => x.includes('not independently re-run')))
  const missing = await run({ checks_run: [] })
  expect('recheck: a command missing from the recheck cannot be accepted', missing.status === 'incomplete' && missing.evidence_issues.some((x) => x.includes('not independently reproduced')))
  const differs = await run({ checks_run: [{ ...first, exit: '1', result: 'one assertion failed' }] })
  expect('recheck: a failing re-run rejects and names the differing exit', differs.status === 'rejected' && differs.reason.includes('failed check on independent re-run') && differs.evidence_issues.some((x) => x.includes('differs between the two runs (0 vs 1)')))
  inventoriedFiles = [{ path: 'other.js', change: 'unrelated' }]
  const uncovered = await run({ checks_run: [first] })
  expect('coverage: a requested path with no inventory entry cannot be accepted', uncovered.status === 'incomplete' && uncovered.evidence_issues.some((x) => x === 'requested path has no repository-relative inventory entry: source.js'))
  inventoriedFiles = [{ path: 'vendor/source.js', change: 'a different file with the same tail' }]
  expect('coverage: a different relative file with the same tail does not cover the requested path', (await run({ checks_run: [first] })).evidence_issues.includes('requested path has no repository-relative inventory entry: source.js'))
  inventoriedFiles = [{ path: './source.js', change: 'reconciles each request' }]
  const stale = await run({ checks_run: [{ ...first, result: '41 reconciliation assertions passed' }] })
  expect('recheck: the same exit with a different quoted total cannot be accepted', stale.status === 'incomplete' && stale.evidence_issues.some((x) => x.includes('check summary differs between the two runs (42 reconciliation assertions passed quoted by the first run but absent from the second (41 reconciliation assertions passed))')))
  const extra = await run({ checks_run: [first, { command: 'rm -rf build', exit: '0', result: 'done' }] })
  expect('recheck: an entry for a command that was never requested cannot be accepted', extra.status === 'incomplete' && extra.evidence_issues.some((x) => x.includes('was not requested')))
  const twice = await run({ checks_run: [first, first] })
  expect('recheck: a duplicated recheck result cannot be accepted', twice.status === 'incomplete' && twice.evidence_issues.some((x) => x.includes('duplicate recheck result')))
  inventoriedFiles = [{ path: '/repo/source.js', change: 'absolute path from some checkout' }]
  expect('coverage: an absolute inventory path never covers a requested path', (await run({ checks_run: [first] })).evidence_issues.includes('requested path has no repository-relative inventory entry: source.js'))
  inventoriedFiles = [{ path: './source.js', change: 'dot-relative' }]
  expect('coverage: a ./ path for the requested file counts as covered', (await run({ checks_run: [first] })).accepted === true)
  const dot = await load(WF.review, { ...base, parallel, args: { paths: ['.'], checks: [command] }, agent: async (p, o) => o.label === 'inventory' ? { summary: 's', files: [{ path: 'source.js', change: 'x' }], changed_behavior: [claim], checks_run: [first] } : o.label === 'recheck' ? { checks_run: [first] } : reviewed })
  expect('coverage: requesting "." is covered by any repository-relative entry', dot.accepted === true)
  const badArgs = await load(WF.review, { ...base, parallel, args: { paths: ['source.js'], checks: 'node checks/reconcile.mjs' }, agent: async (p, o) => o.label === 'inventory' ? { summary: 's', files: [{ path: 'source.js', change: 'x' }], changed_behavior: [claim], checks_run: [] } : reviewed })
  expect('arguments: a malformed checks argument blocks acceptance instead of dropping the requirement', badArgs.accepted === false && badArgs.evidence_issues.includes('checks must be an array of nonblank strings'))
  const omitted = await run({ checks_run: [{ ...first, result: 'exit 0, no output' }] })
  expect('recheck: a re-run that omits the deterministic total the first run quoted cannot be accepted', omitted.status === 'incomplete' && omitted.evidence_issues.some((x) => x.includes('check summary differs')))
  const twoTotals = await load(WF.review, { ...base, parallel, args: { paths: ['source.js'], checks: [command] }, agent: async (p, o) => o.label === 'inventory' ? { summary: 's', files: [{ path: 'source.js', change: 'x' }], changed_behavior: [claim], checks_run: [{ ...first, result: '42 reconciliation assertions passed; 3 checks failed' }] } : o.label === 'recheck' ? { checks_run: [{ ...first, result: '42 reconciliation assertions passed; 2 checks failed' }] } : reviewed })
  expect('recheck: every quoted total is compared, not only the first', twoTotals.status === 'incomplete' && twoTotals.evidence_issues.some((x) => x.includes('check summary differs')))
  const moreOutput = await load(WF.review, { ...base, parallel, args: { paths: ['source.js'], checks: [command] }, agent: async (p, o) => o.label === 'inventory' ? { summary: 's', files: [{ path: 'source.js', change: 'x' }], changed_behavior: [claim], checks_run: [first] } : o.label === 'recheck' ? { checks_run: [{ ...first, result: first.result + '; SUMMARY passed=3 failed=0 total=3' }] } : reviewed })
  expect('recheck: a second run that quotes more totals than the first is still accepted', moreOutput.accepted === true)
  const slash = await load(WF.review, { ...base, parallel, args: { paths: ['/'], checks: [command] }, agent: async (p, o) => o.label === 'inventory' ? { summary: 's', files: [{ path: 'source.js', change: 'x' }], changed_behavior: [claim], checks_run: [first] } : o.label === 'recheck' ? { checks_run: [first] } : reviewed })
  expect('arguments: an absolute requested path is rejected instead of covering everything', slash.accepted === false && slash.evidence_issues.includes('paths must be repository-relative, not absolute'))
  labels.length = 0
  const noChecks = await run({ checks_run: [] }, [])
  expect('recheck: no recheck worker is spawned when no acceptance command was requested', !labels.includes('recheck') && noChecks.accepted === true && noChecks.reason.includes('no acceptance commands were requested'))
}
// A returned review must cover every claim exactly once with actual evidence.
{
  const claim = { claim: 'each request is reconciled', source: 'source.js:10' }
  const inv = { summary: 'one change', files: [], changed_behavior: [claim], checks_run: [] }
  const confirmed = { claim: claim.claim, verdict: 'confirmed', evidence: 'source.js:10 reconciles each request' }
  const clean = { verdicts: [confirmed], defects: [], gaps: [] }
  const run = (review, inventory = inv) => load(WF.review, { ...base, parallel, args: {}, agent: async (p, o) => o.label === 'inventory' ? inventory : review })
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
  const run = (verify, packet = reader, args = { docs: ['readiness.md'] }) => load(WF.readiness, { ...base, parallel, args, agent: async (p, o) => o.label === 'verify' ? verify : packet })
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
    return load(WF.readiness, { ...base, parallel, args: { docs, commands: [command] }, agent: async (p, o) => {
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
  const doc = 'settings.json', command = 'node --version'
  const calls = []
  const result = await load(WF.readiness, { ...base, parallel, args: { docs: [doc], commands: [command], question: 'Check ' + doc + ' and ' + command }, agent: async (prompt, opts) => {
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
// Source scanning for the static contract. `structure` blanks comments and string
// contents at equal length so brackets can be matched without being fooled by text
// (a `/` after an operator, opener or comma opens a regex literal; a `/` inside a
// regex character class is not handled; template-literal contents are blanked, so the
// contract separately rejects an agent( written inside one). `agentOptionLiterals` returns, per agent()
// call site, the top level of its last inline object argument with nested braces
// removed, or null when the call has no inline object.
const nameOf = (frontmatter) => ((frontmatter || '').match(/^name: (.*)$/m) || [null, null])[1]
function structure(src, keepTemplates = false) {
  let out = '', mode = null
  for (let i = 0; i < src.length; i++) {
    const c = src[i], n = src[i + 1]
    if (mode === null) {
      if (c === '/' && (n === '/' || n === '*')) { mode = n === '/' ? 'line' : 'block'; out += '  '; i++ }
      else if (c === '/' && /(^|[(,=:\[!&|?{};\n])\s*$/.test(out.slice(-40))) { mode = 'regex'; out += c }
      else { if (c === "'" || c === '"' || c === '`') mode = c; out += c }
    } else if (mode === 'line') { if (c === '\n') mode = null; out += c === '\n' ? c : ' ' }
    else if (mode === 'block') { if (c === '*' && n === '/') { mode = null; out += '  '; i++ } else out += c === '\n' ? c : ' ' }
    else if (c === '\\') { out += '  '; i++ }
    else if (mode === 'regex') { if (c === '/') mode = null; out += c === '/' || c === '\n' ? c : ' ' }
    else { const tpl = mode === '`'; if (c === mode) mode = null; out += mode === null || c === '\n' || (tpl && keepTemplates) ? c : ' ' }
  }
  return out
}
// A key counts only where the blanked code shows it (so text inside a string value cannot
// fake it); its value is then read from the source at the same offset.
function optionValue(lit, key) {
  const m = lit && new RegExp('\\b' + key + ": '").exec(lit.code)
  return m ? (new RegExp('^' + key + ": '([^']*)'").exec(lit.src.slice(m.index)) || [null, null])[1] : null
}
function agentOptionLiterals(src) {
  const code = structure(src), found = []
  for (const m of code.matchAll(/\bagent\s*\(/g)) {
    let depth = 0, open = -1, last = null
    for (let i = m.index + m[0].length - 1; i < code.length; i++) {
      const c = code[i]
      if ('([{'.includes(c)) { if (c === '{' && depth === 1) open = i; depth++ }
      else if (')]}'.includes(c)) { depth--; if (c === '}' && depth === 1 && open >= 0) { last = [open, i + 1]; open = -1 } if (depth === 0) break }
    }
    if (!last) { found.push(null); continue }
    let flatSrc = '', flatCode = '', d = 0
    for (let i = last[0]; i < last[1]; i++) { if (code[i] === '{') d++; if (d === 1) { flatSrc += src[i]; flatCode += code[i] } if (code[i] === '}') d-- }
    found.push({ src: flatSrc, code: flatCode })
  }
  return found
}
// Static contract shared by every saved workflow: one worker packet text, and an
// explicit task-matched model and effort on every agent() call (an omitted model
// inherits the coordinator's model).
{
  const sample = "// agent( in a comment\nconst s = 'agent( in a string {'\nawait agent('p {' + x, { label: 'a', schema: { type: 'object', properties: { model: { type: 'string' } } }, model: 'sonnet', effort: 'low' })\nawait agent(p, opts)\nawait agent(p, { label: 'b', schema: S, effort: 'high' })\n"
  const lits = agentOptionLiterals(sample)
  expect('scanner: comments and strings are not call sites', lits.length === 3)
  const hidden = 'const p = `x ${await agent(q, { label: "h" })}`\n'
  expect('scanner: an agent( inside a template literal is visible to the fail-closed count only', agentOptionLiterals(hidden).length === 0 && (structure(hidden, true).match(/\bagent\(/g) || []).length === 1)
  expect('scanner: a regex literal holding a quote or agent( does not derail the scan', agentOptionLiterals("const r = x.match(/agent\\('/)\nconst q = a / b\nawait agent(p, { label: 'c', model: 'opus', effort: 'high' })\n").length === 1)
  expect('scanner: a nested inline schema does not hide or fake top-level model and effort', optionValue(lits[0], 'model') === 'sonnet' && optionValue(lits[0], 'effort') === 'low' && !/type: 'string'/.test(lits[0].src))
  expect('scanner: options passed as a variable yield null, and a literal without model is visible as such', lits[1] === null && optionValue(lits[2], 'model') === null)
  expect('scanner: a string value that merely contains model text does not bind a model', optionValue(agentOptionLiterals("await agent(p, { label: \"x model: 'opus' y\", effort: 'high' })\n")[0], 'model') === null)
  // Every saved workflow (a .js or .mjs file with a meta literal) is covered, so a new script cannot skip the contract.
  const files = readdirSync(join(ROOT, 'workflows')).filter((n) => /\.m?js$/.test(n)).map((n) => 'workflows/' + n).filter((f) => /^\s*export\s+const\s+meta\s*=/m.test(readFileSync(join(ROOT, f), 'utf8'))).sort()
  expect('contract: the saved workflows are discovered', files.length >= 2 && files.includes(WF.review) && files.includes(WF.readiness))
  const packets = files.map((f) => (readFileSync(join(ROOT, f), 'utf8').match(/const PACKET = \[[\s\S]*?\]\.join\(' '\)/) || [''])[0])
  expect('contract: every saved workflow defines a PACKET', packets.every((p) => p.length > 0))
  expect('contract: PACKET text is byte-identical across saved workflows', new Set(packets).size === 1)
  const contractDoc = ((readOr(configured('contract_doc')).split('\n' + CONFIG.contract_heading + '\n')[1] || '').split('\n## ')[0]).toLowerCase()
  expect('contract: every lane the PACKET names is described in the documented Workflow contract', ['serena', 'socraticode', 'jcodemunch', 'qmd', 'ai-memory', 'context mode', 'toolsearch'].every((lane) => packets[0].toLowerCase().includes(lane) && contractDoc.includes(lane)))
  for (const f of files) {
    const calls = []
    // Return a minimal instance of each stage's schema so later stages are reached;
    // a null-returning stub stops review-changes after its first stage.
    const minimal = (sc) => !sc ? null : sc.enum ? sc.enum[0] : sc.type === 'object' ? Object.fromEntries((sc.required || []).map((k) => [k, minimal(sc.properties[k])])) : sc.type === 'array' ? Array.from({ length: sc.minItems || 0 }, () => minimal(sc.items)) : sc.type === 'string' ? 'x' : sc.type === 'boolean' ? false : sc.type === 'number' || sc.type === 'integer' ? 0 : null
    const stub = async (prompt, opts) => { calls.push({ prompt, opts: opts || {} }); return minimal((opts || {}).schema) }
    await load(f, { ...base, parallel, args: { base: 'HEAD', docs: ['a.md'], commands: ['true'], checks: ['true'] }, agent: stub })
    const allowed = { model: ['haiku', 'sonnet', 'opus'], effort: ['low', 'medium', 'high', 'xhigh', 'max'] }
    const src = readFileSync(join(ROOT, f), 'utf8')
    const literals = agentOptionLiterals(src)
    const sites = literals.length
    expect('contract: ' + f + ' reached at least as many agent() calls as it has call sites', sites > 0 && calls.length >= sites)
    expect('contract: ' + f + ' sets an explicit model and effort on every reached agent() call', calls.every((c) => allowed.model.includes(c.opts.model) && allowed.effort.includes(c.opts.effort)))
    const packetText = new Function(packets[files.indexOf(f)] + '; return PACKET')()
    expect('contract: ' + f + ' starts every worker prompt with the full shared packet', packetText.length > 200 && calls.every((c) => c.prompt.startsWith(packetText + '\n')))
    // Reviewed routing, by stage label prefix: [agentType, model, effort]. A new saved workflow
    // or a rerouted stage fails here until the routing is reviewed and listed. Models stay task-matched
    // (Sonnet scouts, Opus reviewers and judges); every stage runs at effort max since 2026-09-23.
    const ROUTING = {
      [WF.review]: { inventory: ['source-scout', 'sonnet', 'max'], review: ['evidence-reviewer', 'opus', 'max'], recheck: ['source-scout', 'sonnet', 'max'] },
      [WF.readiness]: { 'read:': ['source-scout', 'sonnet', 'max'], verify: [undefined, 'opus', 'max'] },
      'workflows/layer-verdict-lane.js': { 'propose:': ['blind-lane-reviewer', 'opus', 'max'], 'refute:': ['blind-lane-reviewer', 'opus', 'max'] },
    }
    const routes = ROUTING[f] || {}
    const routeOf = (label) => Object.keys(routes).find((k) => String(label).startsWith(k))
    expect('contract: ' + f + ' routes each stage to its reviewed agent, model and effort', Object.keys(routes).length > 0 && calls.every((c) => { const r = routes[routeOf(c.opts.label)]; return r && c.opts.agentType === r[0] && c.opts.model === r[1] && c.opts.effort === r[2] }) && Object.keys(routes).every((k) => calls.some((c) => routeOf(c.opts.label) === k)))
    // A stage that names a project agent must name one that exists and that declares
    // its own model and effort; a missing agent type fails the native agent() call.
    const front = (name) => { try { return (readFileSync(join(ROOT, 'agents', name + '.md'), 'utf8').match(/^---\n([\s\S]*?)\n---/) || [null, ''])[1] } catch { return '' } }
    expect('contract: ' + f + ' names only existing project agents with explicit model and effort', calls.filter((c) => c.opts.agentType).every((c) => { const fm = front(c.opts.agentType); return nameOf(fm) === c.opts.agentType && /^model: (haiku|sonnet|opus)$/m.test(fm) && /^effort: (low|medium|high|xhigh|max)$/m.test(fm) }))
    // Static and independent of which stages the stub reached: the inline options
    // literal of every agent() call must itself hold model and effort at its top
    // level, and any agentType it names must be a valid project agent. Passing the
    // options as a variable is rejected on purpose: the pairing must be readable here.
    // Template-literal contents are blanked by the scanner, so an agent() call inside a
    // `${...}` interpolation would be invisible to it: reject that shape outright.
    expect('contract: ' + f + ' has no agent( inside a template literal', (structure(src, true).match(/\bagent\s*\(/g) || []).length === sites)
    expect('contract: ' + f + ' passes an inline options literal to every agent() call', literals.every((o) => o !== null))
    expect('contract: ' + f + ' binds model and effort inside every options literal', literals.every((o) => ['haiku', 'sonnet', 'opus'].includes(optionValue(o, 'model')) && ['low', 'medium', 'high', 'xhigh', 'max'].includes(optionValue(o, 'effort'))))
    // Policy, separate from validity: every call site, reached by the stub or not, binds the one stage effort.
    expect('contract: ' + f + ' binds effort ' + STAGE_EFFORT + ' in every options literal', sites > 0 && literals.every((o) => optionValue(o, 'effort') === STAGE_EFFORT))
    // A workflow that records its model in a MODEL literal (the layer-verdict lane returns it) must record, in one
    // strict single-line form, the same model and effort that every options literal binds.
    const modelDecls = src.match(/^\s*(?:export\s+)?(?:const|let|var)\s+MODEL\s*=/mg) || []
    const declared = src.match(/^\s*(?:export\s+)?const\s+MODEL\s*=\s*\{\s*name:\s*'([^']+)',\s*effort:\s*'([^']+)'\s*\}\s*;?\s*$/m)
    expect('contract: ' + f + ' records in MODEL, when declared, the same model and effort it binds in every options literal', modelDecls.length === 0 || (modelDecls.length === 1 && declared !== null && literals.every((o) => optionValue(o, 'model') === declared[1] && optionValue(o, 'effort') === declared[2])))
    const times = (lit, key) => (lit ? lit.code.match(new RegExp('\\b' + key + ':', 'g')) || [] : []).length
    expect('contract: ' + f + ' declares model and effort exactly once per options literal and spreads nothing into it', literals.every((o) => o !== null && times(o, 'model') === 1 && times(o, 'effort') === 1 && times(o, 'agentType') <= 1 && !o.code.includes('...')))
    const namedAgents = literals.map((o) => optionValue(o, 'agentType')).filter(Boolean)
    expect('contract: ' + f + ' names only valid project agents in every stage, reached or not', namedAgents.every((name) => { const fm = front(name); return nameOf(fm) === name && /^model: (haiku|sonnet|opus)$/m.test(fm) && /^effort: (low|medium|high|xhigh|max)$/m.test(fm) }))
  }
}
// Project agent definitions: an omitted model or effort silently inherits the
// coordinator's, and a bare `mcp__server` grant loads every schema of that server
// eagerly (write tools included) instead of the named, deferred read lanes.
{
  const dir = join(ROOT, 'agents')
  const names = readdirSync(dir).filter((n) => n.endsWith('.md')).sort()
  expect('agents: project agent definitions exist', names.length >= 3)
  for (const n of names) {
    const fm = (readFileSync(join(dir, n), 'utf8').match(/^---\n([\s\S]*?)\n---/) || [null, ''])[1]
    const tools = ((fm.match(/^tools: (.*)$/m) || [null, ''])[1]).split(',').map((t) => t.trim()).filter(Boolean)
    expect('agents: ' + n + ' name matches its file', nameOf(fm) === n.replace(/\.md$/, ''))
    expect('agents: ' + n + ' declares an explicit model and effort', /^model: (haiku|sonnet|opus)$/m.test(fm) && /^effort: (low|medium|high|xhigh|max)$/m.test(fm))
    // One effort line, and it is the stage effort: a second, lower line cannot hide behind the first.
    expect('agents: ' + n + ' runs at effort ' + STAGE_EFFORT + ' on a single effort line', (fm.match(/^effort:/mg) || []).length === 1 && new RegExp('^effort: ' + STAGE_EFFORT + '$', 'm').test(fm))
    expect('agents: ' + n + ' declares a tools allowlist', tools.length > 0)
    expect('agents: ' + n + ' runs in its own worktree when it can edit files', !tools.some((t) => ['Edit', 'Write', 'NotebookEdit'].includes(t)) || /^isolation: worktree$/m.test(fm))
    expect('agents: ' + n + ' grants MCP tools by full name, never a bare server prefix', tools.filter((t) => t.startsWith('mcp__')).every((t) => /^mcp__.+__[A-Za-z0-9_]+$/.test(t) && !t.endsWith('__*')))
    expect('agents: ' + n + ' keeps granted MCP tools deferred behind ToolSearch', !tools.some((t) => t.startsWith('mcp__')) || tools.includes('ToolSearch'))
  }
  // The role routing table in the routing doc restates what the agent files and saved stages bind: one
  // row per project agent carrying the model and effort its file declares, default-child rows at the stage
  // effort, and the coordinator row at xhigh under ultracode. Drift on either side fails here.
  const routingLines = readOr(configured('routing_doc')).split('\n')
  const head = routingLines.findIndex((l) => l.startsWith('| Task class | Agent / stage | Model, effort |'))
  const roleRows = []
  for (let i = head + 2; head >= 0 && i < routingLines.length && routingLines[i].startsWith('|'); i++) roleRows.push(routingLines[i].split('|').slice(1, -1).map((c) => c.trim()))
  const title = { haiku: 'Haiku', sonnet: 'Sonnet', opus: 'Opus' }
  expect('routing doc: the role routing table lists every project agent once with the model and effort its file declares', roleRows.length > 0 && names.every((n) => {
    const fm = (readFileSync(join(dir, n), 'utf8').match(/^---\n([\s\S]*?)\n---/) || [null, ''])[1]
    const rows = roleRows.filter((r) => (r[1] || '').startsWith('`' + n.replace(/\.md$/, '') + '`'))
    return rows.length === 1 && rows[0][2] === title[(fm.match(/^model: (\w+)$/m) || [])[1]] + ', ' + (fm.match(/^effort: (\w+)$/m) || [])[1]
  }))
  const defaultRows = roleRows.filter((r) => r[1] === 'default workflow subagent')
  expect('routing doc: every default workflow subagent row binds a model at effort ' + STAGE_EFFORT, defaultRows.length > 0 && defaultRows.every((r) => new RegExp('^(Sonnet|Opus), ' + STAGE_EFFORT + '$').test(r[2])))
  const coordinatorRows = roleRows.filter((r) => r[1] === 'coordinator')
  expect('routing doc: the coordinator row stays at xhigh under ultracode', coordinatorRows.length === 1 && coordinatorRows[0][2].includes('xhigh under `ultracode`'))
  // Effort profile: the coordinator keeps ultracode at xhigh, so the settings must not set
  // CLAUDE_CODE_EFFORT_LEVEL (any value overrides every stage's and agent's own effort, and a value other than
  // xhigh also leaves ultracode's orchestration inactive) and must not cap effort below the stage effort, either
  // with a top-level maxEffortLevel or with one inside a modelSettings entry.
  let settingsJson = {}
  try { settingsJson = JSON.parse(readOr(configured('settings'))) || {} } catch { settingsJson = {} }
  const settingsEnv = settingsJson.env && typeof settingsJson.env === 'object' ? settingsJson.env : {}
  const effortCaps = [settingsJson.maxEffortLevel, ...Object.values(settingsJson.modelSettings && typeof settingsJson.modelSettings === 'object' ? settingsJson.modelSettings : {}).map((m) => (m && typeof m === 'object' ? m.maxEffortLevel : undefined))].filter((v) => v !== undefined)
  expect('settings: CLAUDE_CODE_EFFORT_LEVEL stays unset and no maxEffortLevel caps the stage effort', !Object.prototype.hasOwnProperty.call(settingsEnv, 'CLAUDE_CODE_EFFORT_LEVEL') && effortCaps.every((v) => v === STAGE_EFFORT))
  expect('instructions: the project instructions state the effort literal every stage binds', readOr(configured('instructions')).includes("`effort: '" + STAGE_EFFORT + "'`"))
  const reviewer = (readFileSync(join(dir, 'evidence-reviewer.md'), 'utf8').match(/^tools: (.*)$/m) || [null, ''])[1]
  // The reviewer's surface is pinned exactly, so any added tool (for example a Serena
  // create_/replace_ tool) fails here until it is reviewed and listed. Two grants stay
  // instruction-bound rather than name-bound: Context Mode ctx_execute* can run commands
  // in the working tree, and jCodeMunch `order` dispatches an action named in its
  // arguments (state changes need its explicit allow_state_change flag).
  const reviewerTools = reviewer.split(',').map((t) => t.trim()).filter(Boolean).sort()
  const expectedReviewerTools = ['Read', 'Glob', 'Grep', 'ToolSearch',
    'mcp__serena__find_symbol', 'mcp__serena__find_referencing_symbols', 'mcp__serena__find_declaration', 'mcp__serena__find_implementations', 'mcp__serena__get_symbols_overview', 'mcp__serena__get_diagnostics_for_file',
    'mcp__socraticode__codebase_search', 'mcp__socraticode__codebase_symbol', 'mcp__socraticode__codebase_impact', 'mcp__socraticode__codebase_flow',
    'mcp__jcodemunch__route', 'mcp__jcodemunch__order',
    'mcp__plugin_context-mode_context-mode__ctx_execute', 'mcp__plugin_context-mode_context-mode__ctx_execute_file', 'mcp__plugin_context-mode_context-mode__ctx_batch_execute', 'mcp__plugin_context-mode_context-mode__ctx_search',
    'mcp__ai-memory__memory_query', 'mcp__ai-memory__memory_read_page', 'mcp__ai-memory__memory_read_session_observations'].sort()
  expect('agents: evidence-reviewer tool surface is exactly the reviewed list', JSON.stringify(reviewerTools) === JSON.stringify(expectedReviewerTools))
  // source-scout needs Bash for acceptance commands, so its read-only rule is likewise
  // an instruction; the check pins the smallest built-in surface and no MCP grant.
  const reviewerBody = readFileSync(join(dir, 'evidence-reviewer.md'), 'utf8').split(/^---$/m)[2] || ''
  expect('agents: evidence-reviewer body and the review stage agree that it never runs acceptance commands', /never to run acceptance commands/.test(reviewerBody) && !/re-run/.test(reviewerBody) && /Do not execute acceptance commands/.test(readFileSync(join(ROOT, WF.review), 'utf8')))
  let size = null
  try { size = JSON.parse(readOr(configured('settings'))).workflowSizeGuideline } catch { size = null }
  expect('settings: workflowSizeGuideline is a documented value and the project instructions name the same one', ['unrestricted', 'small', 'medium', 'large'].includes(size) && readOr(configured('instructions')).includes('`' + size + '` size guideline'))
  const scout = readFileSync(join(dir, 'source-scout.md'), 'utf8')
  expect('agents: source-scout is read-only built-ins without project instructions', /^tools: Read, Grep, Glob, Bash$/m.test(scout) && /^omitClaudeMd: true$/m.test(scout))
}
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
