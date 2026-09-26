#!/usr/bin/env node
// OFFLINE check of child-usage.mjs against SYNTHETIC transcript rows (no provider
// call, not native evidence). Real runs are checked by passing their directory;
// stored receipts from real runs are bound to the documentation by test-usage-receipts.mjs.
import { summarizeChild, summarizeRun, latestRunDir, effortMismatches, modelGeneration, expectedModel } from './child-usage.mjs'
import { mkdtempSync, writeFileSync, rmSync, mkdirSync, utimesSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
let passed = 0, failed = 0
const expect = (n, c) => { console.log((c ? 'PASS ' : 'FAIL ') + n); if (c) passed++; else failed++ }
const msg = (id, model, out, read = 0, write = 0, effort = 'medium') => ({ type: 'assistant', effort, message: { id, model, usage: { input_tokens: 2, output_tokens: out, cache_read_input_tokens: read, cache_creation_input_tokens: write } } })
const started = { type: 'started', agentId: 'a1', label: 'inventory', phase: 'Audit' }
const done = { type: 'result', agentId: 'a1', result: { ok: true } }

const dup = summarizeChild(started, done, { model: 'sonnet', agentType: 'workflow' }, [msg('m1', 'claude-sonnet-5', 1, 500), msg('m1', 'claude-sonnet-5', 40, 500), msg('m1', 'claude-sonnet-5', 40, 500), msg('m2', 'claude-sonnet-5', 10, 900, 30)])
expect('streamed duplicates of one message id count once with the largest output', dup.requests === 2 && dup.usage.output_tokens === 50 && dup.usage.input_tokens === 4 && dup.usage.cache_read_input_tokens === 1400)
expect('first request cache read and effort are reported', dup.first_request_cache_read === 500 && dup.efforts.join() === 'medium' && dup.complete)
expect('first request prompt size is input plus cache read plus cache creation', dup.first_request_prompt_tokens === 502)
expect('null result is incomplete', !summarizeChild(started, { ...done, result: null }, { model: 'sonnet' }, [msg('m1', 'claude-sonnet-5', 5)]).complete)
expect('missing journal result is incomplete', !summarizeChild(started, null, { model: 'sonnet' }, [msg('m1', 'claude-sonnet-5', 5)]).complete)
const inherited = summarizeChild(started, done, { agentType: 'workflow' }, [msg('m1', 'claude-fable-5-1', 5)])
expect('omitted model is flagged as coordinator inheritance', !inherited.complete && inherited.requested_model === null && inherited.issues.some((i) => i.includes('inherits')))
const swapped = summarizeChild(started, done, { model: 'haiku' }, [msg('m1', 'claude-haiku-4-5-20251001', 5), msg('m2', 'claude-sonnet-5', 7)])
expect('model substitution is incomplete and usage stays split per resolved model', !swapped.complete && swapped.usage_by_model['claude-sonnet-5'].output_tokens === 7 && swapped.usage_by_model['claude-haiku-4-5-20251001'].output_tokens === 5)
const noUsageMsg = { type: 'assistant', message: { id: 'm9', model: 'claude-sonnet-5' } }
expect('an assistant message without usage makes the child incomplete instead of undercounting it', !summarizeChild(started, done, { model: 'sonnet' }, [msg('m1', 'claude-sonnet-5', 5), noUsageMsg]).complete)
expect('an empty usage object is not counted as zero usage', !summarizeChild(started, done, { model: 'sonnet' }, [{ type: 'assistant', message: { id: 'm1', model: 'claude-sonnet-5', usage: {} } }]).complete)
const noModel = summarizeChild(started, done, { model: 'sonnet' }, [{ ...msg('m1', undefined, 5) }])
expect('usage without a resolved model is incomplete, not vacuously matching', !noModel.complete && noModel.issues.some((i) => i.includes('without a resolved model')))
expect('no assistant usage is incomplete', !summarizeChild(started, done, { model: 'opus' }, [{ type: 'user' }]).complete)

// Classifier fallback (model-config doc, "Automatic model fallback"): a flagged request re-runs on an
// older model and the child continues there. Rows carry the client version that wrote them.
const vmsg = (id, model, version) => ({ ...msg(id, model, 5, 0, 0, 'max'), version })
const synthetic = (id, version) => ({ type: 'assistant', version, isApiErrorMessage: true, effort: null, message: { id, model: '<synthetic>', usage: { input_tokens: 0, output_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } })
const has = (child, text) => child.issues.some((i) => i.includes(text))
const switched = summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-5-5', '2.1.281'), vmsg('m2', 'claude-opus-4-8', '2.1.281'), vmsg('m3', 'claude-opus-4-8', '2.1.281')])
expect('fallback: a resolved model that changes within the child is incomplete and names the change once', !switched.complete && switched.issues.some((i) => i.endsWith('changed within the child: claude-opus-5-5 -> claude-opus-4-8')))
expect('fallback: the substring family check alone would have accepted claude-opus-4-8 for opus', !has(switched, 'outside requested family'))
const wholeChild = summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-5', '2.1.281'), vmsg('m2', 'claude-opus-5', '2.1.281')])
expect('fallback: a child that ran entirely on an older model than its version documents is incomplete', !wholeChild.complete && !has(wholeChild, 'changed within') && has(wholeChild, 'claude-opus-5 on 2.1.281 (documented opus: claude-opus-5-5)'))
expect('fallback: opus on claude-opus-5 under 2.1.278 is the documented resolution, not a fallback', summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-5', '2.1.278'), vmsg('m2', 'claude-opus-5', '2.1.278')]).complete)
expect('fallback: opus on claude-opus-5-5 under 2.1.280 and 2.1.281 is complete', summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-5-5', '2.1.280'), vmsg('m2', 'claude-opus-5-5', '2.1.281')]).complete)
expect('fallback: a cybersecurity fallback to claude-opus-4-8 under 2.1.278 is older than claude-opus-5', has(summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-4-8', '2.1.278')]), 'older than the documented alias resolution'))
const withError = summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-5-5', '2.1.281'), synthetic('s1', '2.1.281'), vmsg('m2', 'claude-opus-5-5', '2.1.281')])
expect('fallback: a <synthetic> API-error row is not a model change or an older model; the family check still reports it', !has(withError, 'changed within') && !has(withError, 'older than') && has(withError, 'outside requested family: claude-opus-5-5,<synthetic>'))
expect('fallback: an entry older than the first documented row has no expectation', summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-opus-4-8', '2.1.100')]).complete)
expect('fallback: an alias without documented rows (sonnet) is checked for changes only', summarizeChild(started, done, { model: 'sonnet' }, [vmsg('m1', 'claude-sonnet-5', '2.1.281')]).complete && !summarizeChild(started, done, { model: 'sonnet' }, [vmsg('m1', 'claude-sonnet-5', '2.1.281'), vmsg('m2', 'claude-haiku-4-5-20251001', '2.1.281')]).complete)
expect('fallback: an opus model name that cannot be compared fails closed', has(summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-3-opus-20240229', '2.1.281')]), 'older than the documented alias resolution'))
expect('fallback: model names parse to family and version, ignoring date and [1m] suffixes', JSON.stringify([modelGeneration('claude-opus-5-5'), modelGeneration('claude-opus-5'), modelGeneration('claude-haiku-4-5-20251001'), modelGeneration('claude-opus-5-5[1m]'), modelGeneration('claude-3-opus-20240229')]) === JSON.stringify([{ family: 'opus', version: [5, 5] }, { family: 'opus', version: [5] }, { family: 'haiku', version: [4, 5] }, { family: 'opus', version: [5, 5] }, null]))
expect('fallback: the opus version table matches the documented boundaries', JSON.stringify(['2.1.153', '2.1.154', '2.1.218', '2.1.219', '2.1.279', '2.1.280', '2.1.281'].map((v) => expectedModel('opus', v))) === JSON.stringify([null, 'claude-opus-4-8', 'claude-opus-4-8', 'claude-opus-5', 'claude-opus-5', 'claude-opus-5-5', 'claude-opus-5-5']) && expectedModel('sonnet', '2.1.281') === null && expectedModel('opus', undefined) === null)

const dir = mkdtempSync(join(tmpdir(), 'child-usage-'))
try {
  expect('missing journal fails closed', summarizeRun(dir).status === 'incomplete')
  writeFileSync(join(dir, 'journal.jsonl'), [{ type: 'launched' }, started, { ...started, agentId: 'a2', label: 'review', phase: 'Review' }, done].map((e) => JSON.stringify(e)).join('\n') + '\nnot json\n')
  writeFileSync(join(dir, 'agent-a1.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' }))
  writeFileSync(join(dir, 'agent-a1.jsonl'), JSON.stringify(msg('m1', 'claude-sonnet-5', 9, 100)) + '\n')
  const run = summarizeRun(dir)
  expect('run keeps every started child and is incomplete when one has no result, meta or transcript', run.status === 'incomplete' && run.children.length === 2 && run.children[0].complete && !run.children[1].complete)
  const efforts = { children: [{ label: 'max', efforts: ['max'] }, { label: 'inherit', efforts: ['xhigh'] }, { label: 'mixed', efforts: ['max', 'high'] }, { label: 'none', efforts: [] }] }
  expect('require-effort flags every child not exactly at the level, including none recorded', JSON.stringify(effortMismatches(efforts, 'max').map((m) => m.child)) === '["inherit","mixed","none"]')
  expect('require-effort passes a run whose children all ran at the level', effortMismatches({ children: [{ label: 'a', efforts: ['max'] }] }, 'max').length === 0)
  expect('per-model totals come from returned usage only', run.by_resolved_model['claude-sonnet-5'].output_tokens === 9 && run.by_resolved_model['claude-sonnet-5'].children === 1)
  // CLI: --require-effort on a complete one-child run (either argument order), and bad levels exit 2
  const cli = (...a) => spawnSync(process.execPath, [fileURLToPath(new URL('./child-usage.mjs', import.meta.url)), ...a], { encoding: 'utf8' }).status
  const one = join(dir, 'one'); mkdirSync(one)
  writeFileSync(join(one, 'journal.jsonl'), [started, done].map((e) => JSON.stringify(e)).join('\n') + '\n')
  writeFileSync(join(one, 'agent-a1.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' }))
  writeFileSync(join(one, 'agent-a1.jsonl'), JSON.stringify(msg('m1', 'claude-sonnet-5', 9, 100, 0, 'max')) + '\n')
  expect('cli: a max-only run passes --require-effort max in either argument order', cli(one, '--require-effort', 'max') === 0 && cli('--require-effort', 'max', one) === 0)
  expect('cli: the same run fails --require-effort high', cli(one, '--require-effort', 'high') === 1)
  expect('cli: a missing, flag-like, unknown or repeated level exits 2', cli(one, '--require-effort') === 2 && cli('--require-effort', '--latest', one) === 2 && cli(one, '--require-effort', 'MAX') === 2 && cli('--require-effort', 'max', '--require-effort', 'max', one) === 2)
  // A run whose one opus child fell back mid-child exits 1 even when every row is at the required effort.
  const fell = join(dir, 'fell'); mkdirSync(fell)
  writeFileSync(join(fell, 'journal.jsonl'), [started, done].map((e) => JSON.stringify(e)).join('\n') + '\n')
  writeFileSync(join(fell, 'agent-a1.meta.json'), JSON.stringify({ model: 'opus', agentType: 'evidence-reviewer' }))
  writeFileSync(join(fell, 'agent-a1.jsonl'), [vmsg('m1', 'claude-opus-5-5', '2.1.281'), vmsg('m2', 'claude-opus-4-8', '2.1.281')].map((e) => JSON.stringify(e)).join('\n') + '\n')
  expect('cli: a run with a fallback child exits 1 and reports the run incomplete', cli(fell, '--require-effort', 'max') === 1 && summarizeRun(fell).status === 'incomplete')
  // A call the runtime re-ran under the same journal key (a Workflow pauses at a usage limit and re-runs its waiting
  // agents after the reset): the attempt that returned nothing is superseded, not lost, and its usage still counts.
  const limitRow = { type: 'assistant', isApiErrorMessage: true, effort: 'max', message: { id: 'syn1', model: '<synthetic>', usage: { input_tokens: 0, output_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } }
  const rerun = join(dir, 'rerun'); mkdirSync(rerun)
  writeFileSync(join(rerun, 'journal.jsonl'), [{ type: 'launched' }, { ...started, key: 'v2:k1' }, { ...started, agentId: 'a3', label: 'review', key: 'v2:k2' },
    { ...started, agentId: 'a2', key: 'v2:k1' }, { type: 'result', agentId: 'a2', result: { ok: true } }, { type: 'result', agentId: 'a3', result: { ok: true } }].map((e) => JSON.stringify(e)).join('\n') + '\n')
  for (const id of ['a1', 'a2', 'a3']) writeFileSync(join(rerun, 'agent-' + id + '.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' }))
  writeFileSync(join(rerun, 'agent-a1.jsonl'), [msg('m1', 'claude-sonnet-5', 7, 100, 0, 'max'), limitRow].map((e) => JSON.stringify(e)).join('\n') + '\n')
  writeFileSync(join(rerun, 'agent-a2.jsonl'), JSON.stringify(msg('m2', 'claude-sonnet-5', 11, 100, 0, 'max')) + '\n')
  writeFileSync(join(rerun, 'agent-a3.jsonl'), JSON.stringify(msg('m3', 'claude-sonnet-5', 5, 100, 0, 'max')) + '\n')
  const re = summarizeRun(rerun)
  const sup = (re.superseded_attempts || [])[0] || {}
  expect('rerun: a no-result attempt whose call key started again is superseded and the run is complete', re.status === 'complete' && re.children.length === 2 && re.children.every((c) => c.complete) && (re.superseded_attempts || []).length === 1 && sup.agent_id === 'a1' && sup.superseded_by === 'a2' && sup.complete === false)
  expect('rerun: the superseded attempt keeps its issues and its usage counts in the per-model totals', (sup.issues || []).includes('no result entry in journal') && re.by_resolved_model['claude-sonnet-5'].output_tokens === 23 && re.by_resolved_model['<synthetic>'].children === 1)
  expect('rerun: the cli passes --require-effort max for a re-run call', cli(rerun, '--require-effort', 'max') === 0)
  expect('rerun: --require-effort also checks superseded attempts', JSON.stringify(effortMismatches({ children: [{ label: 'a', efforts: ['max'] }], superseded_attempts: [{ label: 'a', agent_id: 'x1', superseded_by: 'x2', efforts: ['max', 'low'] }] }, 'max')) === JSON.stringify([{ child: 'a', efforts: ['max', 'low'], superseded_by: 'x2' }]))
  // Without a later attempt of its key, a no-result attempt stays an incomplete child; an attempt that returned is
  // never superseded, even when its key starts again.
  const lone = join(dir, 'lone'); mkdirSync(lone)
  writeFileSync(join(lone, 'journal.jsonl'), [{ ...started, key: 'v2:k1' }, { ...started, agentId: 'a2', key: 'v2:k2' }, { type: 'result', agentId: 'a2', result: { ok: true } },
    { ...started, agentId: 'a3', key: 'v2:k2' }].map((e) => JSON.stringify(e)).join('\n') + '\n')
  for (const id of ['a1', 'a2', 'a3']) { writeFileSync(join(lone, 'agent-' + id + '.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' })); writeFileSync(join(lone, 'agent-' + id + '.jsonl'), JSON.stringify(msg('m' + id, 'claude-sonnet-5', 3, 100, 0, 'max')) + '\n') }
  const lr = summarizeRun(lone)
  expect('rerun: an unrepeated no-result attempt and a re-started returned call are not superseded', lr.status === 'incomplete' && lr.children.length === 3 && !lr.superseded_attempts && !lr.children[0].complete && lr.children[1].complete && !lr.children[2].complete)
  // Output larger than a pipe buffer (64 KiB on Linux) arrives whole: process.exit() right after console.log dropped
  // the pending stdout writes when stdout was a pipe (Node.js process.exit() documentation).
  const big = join(dir, 'big'); mkdirSync(big)
  const many = 400
  writeFileSync(join(big, 'journal.jsonl'), Array.from({ length: many }, (_, i) => [{ type: 'started', agentId: 'b' + i, label: 'stage-' + i, phase: 'Audit', key: 'v2:' + i }, { type: 'result', agentId: 'b' + i, result: { ok: true } }]).flat().map((e) => JSON.stringify(e)).join('\n') + '\n')
  for (let i = 0; i < many; i++) { writeFileSync(join(big, 'agent-b' + i + '.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' })); writeFileSync(join(big, 'agent-b' + i + '.jsonl'), JSON.stringify(msg('m' + i, 'claude-sonnet-5', 3, 100, 0, 'max')) + '\n') }
  const piped = spawnSync(process.execPath, [fileURLToPath(new URL('./child-usage.mjs', import.meta.url)), big, '--require-effort', 'max'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  let whole = null
  try { whole = JSON.parse(piped.stdout) } catch { whole = null }
  expect('cli: output larger than a pipe buffer arrives whole through a pipe', piped.stdout.length > 65536 && piped.status === 0 && whole !== null && whole.children.length === many)
  // --latest: newest journal under <config>/projects/<slug>/<session>/subagents/workflows/
  const cfg = join(dir, 'cfg'), cwd = '/work/agent-lab.x'
  expect('latest: unknown working directory returns null', latestRunDir(cwd, cfg) === null)
  const runs = ['s1/subagents/workflows/wf_old', 's2/subagents/workflows/wf_new', 's2/subagents/workflows/not-a-run'].map((r) => join(cfg, 'projects', '-work-agent-lab-x', r))
  for (const r of runs) { mkdirSync(r, { recursive: true }); writeFileSync(join(r, 'journal.jsonl'), '') }
  utimesSync(join(runs[0], 'journal.jsonl'), 1000, 1000); utimesSync(join(runs[1], 'journal.jsonl'), 2000, 2000); utimesSync(join(runs[2], 'journal.jsonl'), 3000, 3000)
  expect('latest: newest wf_ run with a journal is selected', latestRunDir(cwd, cfg) === runs[1])
} finally { rmSync(dir, { recursive: true, force: true }) }
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
