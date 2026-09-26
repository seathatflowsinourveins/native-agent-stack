#!/usr/bin/env node
// OFFLINE check of child-usage.mjs against SYNTHETIC transcript rows (no provider
// call, not native evidence). Real runs are checked by passing their directory;
// stored receipts from real runs are bound to the documentation by test-usage-receipts.mjs.
import { summarizeChild, summarizeRun, latestRunDir, effortMismatches, modelGeneration, expectedModel, webSearch, childLanes, aggregateLanes, sweepLanes, fetchKind, mcpServer, safeKey, tokenStats, parseArgs, loadRtkDecisions, DEFAULT_MARKER } from './child-usage.mjs'
import { mkdtempSync, writeFileSync, rmSync, mkdirSync, utimesSync, readFileSync, chmodSync } from 'node:fs'
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

// WebSearch session cap (tools-reference, "Session search limit"): a capped call returns a notice right after the
// result header instead of results; page text that quotes the notice is not a capped call.
const search = (id, ts) => ({ type: 'assistant', timestamp: ts, effort: 'max', message: { id: 'ws-' + id, model: 'claude-opus-5-5', usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 }, content: [{ type: 'tool_use', id, name: 'WebSearch', input: { query: 'q ' + id } }] } })
const answer = (id, content, ts) => ({ type: 'user', timestamp: ts, message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: id, content }] } })
const header = (id) => 'Web search results for query: "q ' + id + '"\n\n'
const cappedText = 'Web search was not performed: this session has used its web search budget (200 of 200 WebSearch calls). Continue with the information already gathered instead of issuing more searches.'
const searchRows = [
  search('t1', '2026-09-26T04:08:00Z'), answer('t1', header('t1') + 'Links: [{"title":"x","url":"https://example.com"}]', '2026-09-26T04:08:01Z'),
  search('t2', '2026-09-26T04:12:00Z'), answer('t2', [{ type: 'text', text: header('t2') + cappedText }], '2026-09-26T04:12:01Z'),
  search('t3', '2026-09-26T04:10:13Z'), answer('t3', header('t3') + cappedText, '2026-09-26T04:10:13Z'),
  search('t4', '2026-09-26T04:11:00Z'), answer('t4', header('t4') + 'Links: []\n\nA page quoting: ' + cappedText, '2026-09-26T04:11:01Z'),
  search('t5', '2026-09-26T04:13:00Z'),
]
const ws = summarizeChild(started, done, { model: 'opus' }, searchRows)
expect('web search: calls, capped calls (string or text-block results) and the earliest capped time are counted', ws.web_search.calls === 5 && ws.web_search.capped === 2 && ws.web_search.first_capped_at === '2026-09-26T04:10:13Z')
expect('web search: a capped call leaves the child complete', ws.complete)
expect('web search: a child without WebSearch calls reports zero', JSON.stringify(dup.web_search) === JSON.stringify({ calls: 0, capped: 0, first_capped_at: null }))
expect('web search: a repeated tool_use row counts once', webSearch([search('t1', 'a'), search('t1', 'a'), answer('t1', header('t1') + cappedText, 'b')]).calls === 1)

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
  // A superseded attempt keeps its usage-integrity failures (GPT-6 review of the 2026-09-26 record): usage the per-model
  // totals cannot count or attribute leaves the run incomplete, although the re-run call returned. The attempt's other
  // issues (no result entry, the <synthetic> usage-limit row outside the family) are expected and do not.
  const rerunWith = (name, firstRows) => {
    const d = join(dir, name); mkdirSync(d)
    writeFileSync(join(d, 'journal.jsonl'), [{ type: 'launched' }, { ...started, key: 'v2:k1' }, { ...started, agentId: 'a3', label: 'review', key: 'v2:k2' },
      { ...started, agentId: 'a2', key: 'v2:k1' }, { type: 'result', agentId: 'a2', result: { ok: true } }, { type: 'result', agentId: 'a3', result: { ok: true } }].map((e) => JSON.stringify(e)).join('\n') + '\n')
    for (const id of ['a1', 'a2', 'a3']) writeFileSync(join(d, 'agent-' + id + '.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' }))
    if (firstRows) writeFileSync(join(d, 'agent-a1.jsonl'), firstRows.map((e) => JSON.stringify(e)).join('\n') + '\n')
    writeFileSync(join(d, 'agent-a2.jsonl'), JSON.stringify(msg('m2', 'claude-sonnet-5', 11, 100, 0, 'max')) + '\n')
    writeFileSync(join(d, 'agent-a3.jsonl'), JSON.stringify(msg('m3', 'claude-sonnet-5', 5, 100, 0, 'max')) + '\n')
    return d
  }
  const uncountedRow = { type: 'assistant', effort: 'max', message: { id: 'm0', model: 'claude-sonnet-5' } }
  const gap = rerunWith('rerun-missing-usage', [msg('m1', 'claude-sonnet-5', 7, 100, 0, 'max'), uncountedRow, limitRow])
  const gr = summarizeRun(gap)
  const gsup = (gr.superseded_attempts || [])[0] || {}
  expect('rerun: a superseded attempt with an assistant message without provider usage leaves the run incomplete', gr.status === 'incomplete' && gr.children.length === 2 && gr.children.every((c) => c.complete) && gsup.superseded_by === 'a2' && (gsup.usage_issues || []).some((i) => i.includes('without provider usage')) && gr.reason.includes('1 superseded attempt(s) with usage'))
  expect('rerun: the cli exits 1 for a superseded attempt whose usage was not counted', cli(gap, '--require-effort', 'max') === 1)
  expect('rerun: a superseded attempt with usage but no resolved model leaves the run incomplete', summarizeRun(rerunWith('rerun-unresolved', [msg('m1', undefined, 7, 100, 0, 'max'), limitRow])).status === 'incomplete')
  const noLog = summarizeRun(rerunWith('rerun-no-transcript', null))
  expect('rerun: a superseded attempt without a transcript has unknown usage, so the run is incomplete', noLog.status === 'incomplete' && ((noLog.superseded_attempts || [])[0] || {}).usage_issues.some((i) => i.includes('no transcript')))
  const quiet = summarizeRun(rerunWith('rerun-no-request', [{ type: 'user', message: { role: 'user', content: 'go' } }]))
  expect('rerun: a superseded attempt that made no request (zero usage) leaves the run complete', quiet.status === 'complete' && !((quiet.superseded_attempts || [])[0] || {}).usage_issues)
  const capRun = join(dir, 'cap'); mkdirSync(capRun)
  writeFileSync(join(capRun, 'journal.jsonl'), [started, done, { ...started, agentId: 'a2', label: 'review' }, { type: 'result', agentId: 'a2', result: { ok: true } }].map((e) => JSON.stringify(e)).join('\n') + '\n')
  for (const id of ['a1', 'a2']) writeFileSync(join(capRun, 'agent-' + id + '.meta.json'), JSON.stringify({ model: 'opus', agentType: 'workflow' }))
  writeFileSync(join(capRun, 'agent-a1.jsonl'), searchRows.map((e) => JSON.stringify(e)).join('\n') + '\n')
  writeFileSync(join(capRun, 'agent-a2.jsonl'), JSON.stringify(msg('m9', 'claude-opus-5-5', 3, 0, 0, 'max')) + '\n')
  const capped = summarizeRun(capRun)
  expect('web search: the run totals calls and capped calls and names the capped children; usage stays complete', capped.status === 'complete' && JSON.stringify(capped.web_search) === JSON.stringify({ calls: 5, capped: 2, capped_children: ['inventory'] }))
  expect('web search: capped calls do not change the exit code', cli(capRun, '--require-effort', 'max') === 0)
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

// Lanes: synthetic rows shaped like Claude Code 2.1.283 child transcripts (tool_use blocks, tool_result
// tool_reference blocks, hook_success / hook_additional_context attachments); not native evidence.
const T = (minute, day = 25) => '2026-09-' + day + 'T18:' + String(minute).padStart(2, '0') + ':00.000Z'
const tokens = (input, read, write) => ({ input_tokens: input, output_tokens: 5, cache_read_input_tokens: read, cache_creation_input_tokens: write })
const ask = (text, minute) => ({ type: 'user', timestamp: T(minute), message: { role: 'user', content: text } })
const call = (id, name, input, minute, usage) => ({ type: 'assistant', timestamp: T(minute), message: { id: 'msg-' + id, model: 'claude-sonnet-5', content: [{ type: 'tool_use', id, name, input }], ...(usage ? { usage } : {}) } })
const toolResult = (id, content, minute) => ({ type: 'user', timestamp: T(minute), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: id, content }] } })
const attach = (attachment, minute) => ({ type: 'attachment', timestamp: T(minute), attachment })
const bashHook = (id, command, stdout, minute) => attach({ type: 'hook_success', hookName: 'PreToolUse:Bash', hookEvent: 'PreToolUse', toolUseID: id, command, stdout, stderr: '', exitCode: 0 }, minute)
const rewrite = JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', updatedInput: { command: 'rtk git status' } } })
const agentTool = [
  ask('Task packet.\n' + DEFAULT_MARKER + '\nrouting text', 0),
  attach({ type: 'hook_success', hookName: 'SubagentStart:general-purpose', hookEvent: 'SubagentStart', toolUseID: 'start', command: 'memory-hook subagent-start', stdout: '{}', stderr: '', exitCode: 0 }, 1),
  call('t1', 'Bash', { command: 'git status' }, 2, tokens(10, 1000, 200)),
  bashHook('t1', '/opt/tools/rtk hook claude', rewrite, 2),
  call('t1', 'Bash', { command: 'git status' }, 2),
  call('t2', 'Bash', { command: 'rtk ls -la' }, 3),
  bashHook('t2', 'python3 other-hook.py', rewrite, 3),
  call('t3', 'Bash', { command: 'cd work && curl -sS https://example.com/a | head' }, 4),
  call('t4', 'Bash', { command: 'curl -s http://127.0.0.1:9090/api/v1/query' }, 5),
  call('t5', 'Bash', { command: 'echo curl is not run; grep -c wget notes.txt' }, 6),
  bashHook('t5', 'rtk hook claude', '', 6),
  call('t6', 'mcp__plugin_context-mode_context-mode__ctx_execute', { language: 'shell', code: 'ls' }, 7),
  call('t7', 'mcp__plugin_context-mode_context-mode__ctx_fetch_and_index', { url: 'https://example.com/doc' }, 8),
  call('t8', 'mcp__qmd__query', { searches: [] }, 9),
  call('t9', 'Skill', { skill: 'tdd' }, 10),
  call('t10', 'ToolSearch', { query: 'select:mcp__qmd__query,WebFetch', max_results: 5 }, 11),
  toolResult('t10', [{ type: 'tool_reference', tool_name: 'mcp__qmd__query' }, { type: 'tool_reference', tool_name: 'WebFetch' }], 11),
  call('t11', 'WebFetch', { url: 'https://example.com/b' }, 12),
]
const lanesA = childLanes(agentTool)
expect('lanes: tool_use blocks count once per id, Bash and MCP calls per server prefix', lanesA.tool_calls === 11 && lanesA.bash_calls === 5 && JSON.stringify(lanesA.mcp_calls) === JSON.stringify({ 'plugin_context-mode_context-mode': 2, qmd: 1 }))
expect('lanes: Skill calls by skill and ToolSearch loads grouped by server or built-in', JSON.stringify(lanesA.skill_calls) === '{"tdd":1}' && lanesA.tool_search.calls === 1 && lanesA.tool_search.loaded.qmd === 1 && lanesA.tool_search.loaded['built-in'] === 1)
expect('lanes: only an `rtk hook` row whose stdout carries updatedInput is a rewrite; a typed rtk prefix is counted apart', lanesA.rtk.hook_rewrites === 1 && lanesA.rtk.model_typed === 1 && lanesA.rtk.decisions === null)
expect('lanes: fetch routing counts WebFetch, ctx_fetch_and_index, remote and loopback-only curl/wget', JSON.stringify(lanesA.fetch) === JSON.stringify({ webfetch: 1, ctx_fetch_and_index: 1, bash_curl_wget: 1, bash_curl_wget_loopback: 1 }))
expect('lanes: the marker in the first prompt is found, the SubagentStart type is recorded and an empty hook stdout is no context', lanesA.injected_block.in_first_prompt && !lanesA.injected_block.in_subagent_start_context && JSON.stringify(lanesA.subagent_start) === '{"types":["general-purpose"],"additional_context":false}')
expect('lanes: first_prompt_tokens is the first request prompt and equals first_request_prompt_tokens', lanesA.first_prompt_tokens === 1210 && summarizeChild(started, done, { model: 'sonnet' }, agentTool).first_request_prompt_tokens === 1210 && summarizeChild(started, done, { model: 'sonnet' }, agentTool).lanes.first_prompt_tokens === 1210)
const decisions = new Map([['t1', 'ask'], ['t2', 'defer'], ['t3', 'deny'], ['t4', 'allow'], ['elsewhere', 'ask']])
expect('lanes: hook_decisions join by tool_use_id counts each Bash call once, unlogged calls as not_logged', JSON.stringify(childLanes(agentTool, { rtkDecisions: decisions }).rtk.decisions) === JSON.stringify({ allow: 1, ask: 1, defer: 1, deny: 1, not_logged: 1, other: 0 }))
expect('lanes: an unknown decision value is kept as other', childLanes(agentTool, { rtkDecisions: new Map([['t1', 'bypass']]) }).rtk.decisions.other === 1)
const injected = childLanes([ask('plain workflow packet', 0), attach({ type: 'hook_additional_context', hookName: 'SubagentStart:workflow-subagent', hookEvent: 'SubagentStart', toolUseID: 'start', content: ['lanes\n' + DEFAULT_MARKER] }, 0), call('b1', 'Read', { file_path: 'a' }, 1, tokens(5, 0, 100))])
expect('lanes: SubagentStart hook_additional_context carrying the marker is an injected block', !injected.injected_block.in_first_prompt && injected.injected_block.in_subagent_start_context && injected.subagent_start.additional_context && injected.subagent_start.types.join() === 'workflow-subagent')
const viaStdout = childLanes([ask('packet', 0), attach({ type: 'hook_success', hookName: 'SubagentStart:general-purpose', hookEvent: 'SubagentStart', toolUseID: 'start', command: 'lanes-hook', stdout: JSON.stringify({ hookSpecificOutput: { hookEventName: 'SubagentStart', additionalContext: 'block ' + DEFAULT_MARKER } }), stderr: '', exitCode: 0 }, 0)])
expect('lanes: SubagentStart additionalContext in hook stdout is an injected block too', viaStdout.injected_block.in_subagent_start_context && viaStdout.subagent_start.additional_context)
const quoted = childLanes([ask('no block here', 0), call('d1', 'Bash', { command: 'grep -c "' + DEFAULT_MARKER + '" hooks.mjs' }, 1), toolResult('d1', 'match ' + DEFAULT_MARKER, 1)])
expect('lanes: the marker in tool input or output is never an injected block', !quoted.injected_block.in_first_prompt && !quoted.injected_block.in_subagent_start_context)
expect('lanes: another marker is looked for when given', childLanes([ask('nonce-7f3', 0)], { marker: 'nonce-7f3' }).injected_block.in_first_prompt && !childLanes([ask('nonce-7f3', 0)]).injected_block.in_first_prompt)
const windowed = childLanes(agentTool, { window: { since: Date.parse(T(3)), until: Date.parse(T(9)) } })
expect('window: only rows inside [since, until) are counted', windowed.tool_calls === 6 && windowed.bash_calls === 4 && windowed.rtk.hook_rewrites === 0 && windowed.rtk.model_typed === 1 && windowed.mcp_calls['plugin_context-mode_context-mode'] === 2 && !windowed.mcp_calls.qmd)
expect('window: a first request before since has no first_prompt_tokens, while first-prompt properties still hold', windowed.first_prompt_tokens === null && windowed.injected_block.in_first_prompt && windowed.subagent_start.types.join() === 'general-purpose')
expect('window: rows at or after until are never read, properties included', !childLanes(agentTool, { window: { since: -Infinity, until: Date.parse(T(0)) } }).injected_block.in_first_prompt)
expect('fetch: curl/wget only in command position, loopback-only apart', JSON.stringify(['curl -s https://x.org', 'rtk curl https://x.org', 'timeout 5 wget http://localhost:8080/', 'curl "$URL"', 'echo curl', 'grep curl f', 'x=$(curl -s http://[::1]:9/)', 'curl http://127.0.0.1/ https://example.org', 'ls\ncurl -I https://x.org'].map(fetchKind)) === JSON.stringify(['fetch', 'fetch', 'loopback', 'fetch', null, null, 'loopback', 'fetch', 'fetch']))
expect('fetch: quoted strings and heredoc bodies are data unless a shell runs them', JSON.stringify([
  "echo 'hello; curl https://example.com'", 'printf "%s" "curl https://x.org"', "bash -c 'curl -s https://x.org'", 'sh -lc "wget http://localhost/"',
  "ssh host 'curl https://x.org'", "cat > s.sh <<'EOF'\ncurl https://x.org\nEOF\nls", "bash <<'EOF'\ncurl https://x.org\nEOF", 'x="$(curl -s https://x.org)"',
  'cat <<< "curl https://x.org"', 'curl "http://127.0.0.1:9090/api"', "python3 - <<'PY'\nos.system('curl https://x.org')\nPY", 'grep -c "curl" notes.txt; curl -s https://x.org',
].map(fetchKind)) === JSON.stringify([null, null, 'fetch', 'loopback', 'fetch', null, 'fetch', 'fetch', null, 'loopback', null, 'fetch']))
// Review finding 8 (2026-09-26): 52 Bash calls in the baseline window ran curl/wget after a shell keyword, 50 after `do`.
expect('fetch: curl/wget after a shell keyword or time/nice/nohup is in command position; the same word as an argument is not', JSON.stringify([
  'for u in a b; do curl -s "$u"; done', 'if curl -s https://x.org; then echo ok; fi', 'if true; then wget -q https://x.org; fi',
  'if false; then :; else curl https://x.org; fi', 'while ! curl -s http://localhost:9/; do sleep 1; done', 'until wget -q http://127.0.0.1:8080/; do sleep 1; done',
  '{ curl -s https://x.org; }', 'time curl -s https://x.org', 'nohup curl -s https://x.org &',
  'echo do curl https://x.org', 'git commit -m "then curl https://x.org"', 'printf "%s\\n" if curl',
].map(fetchKind)) === JSON.stringify(['fetch', 'fetch', 'fetch', 'fetch', 'loopback', 'loopback', 'fetch', 'fetch', 'fetch', null, null, null]))
expect('mcp: the server is the segment between mcp__ and the next __', mcpServer('mcp__plugin_context-mode_context-mode__ctx_execute') === 'plugin_context-mode_context-mode' && mcpServer('mcp__qmd__query') === 'qmd' && mcpServer('Bash') === null && mcpServer('mcp__') === null)
{
  const odd = childLanes([ask('packet', 0), call('p1', 'mcp__constructor__query', {}, 1), call('p2', 'Skill', { skill: '/home/example/private/SKILL.md' }, 2), call('p3', 'Skill', { skill: 'tdd' }, 3), attach({ type: 'hook_success', hookName: 'SubagentStart:has space', hookEvent: 'SubagentStart', toolUseID: 's', command: 'x', stdout: '', stderr: '', exitCode: 0 }, 0)])
  expect('keys: a prototype name is an ordinary counter, and a path or text in a name is counted as (other)', JSON.stringify(odd.mcp_calls) === '{"constructor":1}' && JSON.stringify(odd.skill_calls) === '{"(other)":1,"tdd":1}' && odd.subagent_start.types.join() === '(other)' && safeKey('codex:codex-cli-runtime') === 'codex:codex-cli-runtime' && safeKey('user@example.com') === '(other)')
}
{
  // A streamed duplicate straddling since, and a ToolSearch whose result lands after since.
  const straddle = [ask('packet', 0), call('s1', 'Bash', { command: 'ls' }, 2), call('s1', 'Bash', { command: 'ls' }, 4), call('q1', 'ToolSearch', { query: 'select:mcp__qmd__query' }, 2), toolResult('q1', [{ type: 'tool_reference', tool_name: 'mcp__qmd__query' }], 4)]
  const early = childLanes(straddle, { window: { since: Date.parse(T(0)), until: Date.parse(T(3)) } })
  const late = childLanes(straddle, { window: { since: Date.parse(T(3)), until: Date.parse(T(9)) } })
  const whole = childLanes(straddle, { window: { since: Date.parse(T(0)), until: Date.parse(T(9)) } })
  expect('window: adjacent windows partition calls and loads the way one window over both counts them', early.bash_calls + late.bash_calls === whole.bash_calls && whole.bash_calls === 1 && early.tool_search.calls === 1 && late.tool_search.calls === 0 && late.tool_search.loaded.qmd === 1 && !early.tool_search.loaded.qmd && whole.tool_search.loaded.qmd === 1)
}
{
  // Review finding 6 (2026-09-26): a Bash call's tool_use row before a cut and its `rtk hook` row after it (observed:
  // 13:59:59.646Z and 14:00:00.134Z) was lost from both windows. The rewrite counts in the window of its hook row;
  // the hook_decisions join still counts each call once, in the window of the call.
  const cut = [ask('packet', 0), call('r1', 'Bash', { command: 'git status' }, 2), bashHook('r1', 'rtk hook claude', rewrite, 4), call('r2', 'Bash', { command: 'git log' }, 5), bashHook('r2', 'rtk hook claude', rewrite, 5)]
  const joined = new Map([['r1', 'ask'], ['r2', 'ask']])
  const lanesIn = (since, until) => childLanes(cut, { rtkDecisions: joined, window: { since: Date.parse(T(since)), until: Date.parse(T(until)) } })
  const [early, late, whole] = [lanesIn(0, 3), lanesIn(3, 9), lanesIn(0, 9)]
  expect('window: an RTK rewrite whose hook row follows the cut counts in the window of that row, so adjacent windows add up', early.rtk.hook_rewrites + late.rtk.hook_rewrites === whole.rtk.hook_rewrites && whole.rtk.hook_rewrites === 2 && late.rtk.hook_rewrites === 2)
  expect('window: the hook_decisions join still counts each Bash call once, in the window of the call', early.rtk.decisions.ask === 1 && late.rtk.decisions.ask === 1 && whole.rtk.decisions.ask === 2 && early.bash_calls === 1 && late.bash_calls === 1)
}
expect('stats: nearest-rank percentiles, null ignored', JSON.stringify(tokenStats([100, null, 90, 80, 70, 60, 50, 40, 30, 20, 10])) === JSON.stringify({ n: 10, min: 10, p10: 10, median: 50, p90: 90, max: 100 }) && tokenStats([null]).n === 0)
const agg = aggregateLanes([{ lanes: lanesA }, { lanes: injected }])
expect('aggregate: children using a lane, marker positions and SubagentStart types are counted per child', agg.children === 2 && agg.children_using_bash === 1 && agg.children_using_mcp_server.qmd === 1 && JSON.stringify(agg.injected_block) === '{"in_first_prompt":1,"in_subagent_start_context":1,"either":2}' && JSON.stringify(agg.subagent_start.types) === '{"general-purpose":1,"workflow-subagent":1}')
expect('aggregate: shares use named denominators and stay null without data', agg.fetch.ctx_fetch_and_index_share === 0.3333 && agg.rtk.hook_rewrite_share_of_bash === 0.2 && agg.rtk.decisions === null && agg.rtk.covered_share_of_bash === null && aggregateLanes([]).fetch.ctx_fetch_and_index_share === null)
{
  const withDecisions = aggregateLanes([{ lanes: childLanes(agentTool, { rtkDecisions: decisions }) }])
  expect('aggregate: covered share is (allow + ask) / Bash calls', withDecisions.rtk.covered_share_of_bash === 0.4 && withDecisions.rtk.decisions.not_logged === 1)
}
const sweepRoot = mkdtempSync(join(tmpdir(), 'child-lanes-'))
try {
  // Each file's mtime is set after the window, as a real transcript's is after its own rows, so the
  // sweep's skip of files not modified since the window start does not depend on today's date.
  const written = new Date('2026-09-27T00:00:00Z')
  const put = (rel, rows, meta) => {
    const file = join(sweepRoot, rel)
    mkdirSync(join(file, '..'), { recursive: true })
    writeFileSync(file, rows.map((r) => typeof r === 'string' ? r : JSON.stringify(r)).join('\n') + '\n')
    utimesSync(file, written, written)
    if (meta) writeFileSync(file.replace(/\.jsonl$/, '.meta.json'), JSON.stringify(meta))
    return file
  }
  put('proj/sess-one/subagents/agent-a1.jsonl', agentTool, { agentType: 'general-purpose', description: 'secret task text' })
  put('proj/sess-one/subagents/workflows/wf_run1/agent-b1.jsonl', [ask('packet', 20), call('w1', 'Bash', { command: 'ls' }, 21, tokens(3, 40, 0)), 'not json'], { agentType: 'workflow-subagent', model: 'sonnet' })
  put('proj/sess-one/subagents/workflows/wf_run1/journal.jsonl', [{ type: 'started', agentId: 'b1' }])
  put('proj/sess-two/subagents/workflows/wf_run2/agent-c1.jsonl', [ask('verdict packet', 30), call('c1', 'Bash', { command: 'cat x' }, 31, tokens(1, 1, 1))], { agentType: 'blind-lane-reviewer' })
  put('proj/sess-two/subagents/agent-before.jsonl', [{ ...ask('earlier', 0), timestamp: '2026-09-24T10:00:00.000Z' }], { agentType: 'Explore' })
  const stale = put('proj/sess-two/subagents/agent-stale.jsonl', [ask('stale', 40)], { agentType: 'Explore' })
  utimesSync(stale, new Date('2026-09-01T00:00:00Z'), new Date('2026-09-01T00:00:00Z'))
  put('proj/sess-one.jsonl', [ask('top-level session, not a child', 0)])
  const window = { since: Date.parse('2026-09-25T17:18:00Z'), until: Date.parse('2026-09-26T15:05:00Z') }
  const report = sweepLanes([sweepRoot], window)
  expect('sweep: every child transcript under the root is found, a stale one is skipped unread and a top-level session is not a child', report.transcripts_found === 5 && report.transcripts_skipped_unmodified === 1 && report.children_in_window === 3 && report.parse_errors === 1)
  expect('sweep: groups by spawn path and agent type, blind-* children are negative controls outside workers', report.groups.all.children === 3 && report.groups.workers.children === 2 && report.groups.negative_controls.children === 1 && report.groups.negative_controls.bash_calls === 1 && JSON.stringify(Object.keys(report.groups.by_spawn)) === '["agent_tool","workflow"]' && JSON.stringify(Object.keys(report.groups.by_agent_type)) === '["blind-lane-reviewer","general-purpose","workflow-subagent"]')
  expect('sweep: sessions are ordinals by earliest child row, never ids', report.sessions_in_window === 2 && JSON.stringify(Object.keys(report.groups.by_session)) === '["session-01","session-02"]' && report.groups.by_session['session-01'].children === 2)
  // Review finding 7 (2026-09-26): spawn-path totals mix agent types, so a lane is compared within one agent type.
  const nested = Object.fromEntries(Object.entries(report.groups.by_spawn_and_agent_type || {}).map(([spawn, types]) => [spawn, Object.fromEntries(Object.entries(types).map(([type, g]) => [type, g.children]))]))
  expect('sweep: groups by spawn path within agent type', JSON.stringify(nested) === JSON.stringify({ agent_tool: { 'general-purpose': 1 }, workflow: { 'blind-lane-reviewer': 1, 'workflow-subagent': 1 } }))
  const text = JSON.stringify(report)
  expect('sweep: the report carries no path, session, run or agent id, label, meta description or prompt text', !['child-lanes-', sweepRoot, 'sess-one', 'sess-two', 'wf_run', 'agent-a1', 'a1"', 'secret task', 'Task packet', 'verdict packet'].some((s) => text.includes(s)))
  const script = fileURLToPath(new URL('./child-usage.mjs', import.meta.url))
  const run = (...a) => spawnSync(process.execPath, [script, ...a], { encoding: 'utf8' })
  const ok = run('--lanes-sweep', '--root', sweepRoot, '--since', '2026-09-25T17:18:00Z', '--until', '2026-09-26T15:05:00Z')
  const parsed = ok.status === 0 ? JSON.parse(ok.stdout) : null
  expect('cli: --lanes-sweep prints key-sorted JSON and exits 0', parsed && parsed.kind === 'claude_child_lane_usage' && parsed.children_in_window === 3 && JSON.stringify(Object.keys(parsed)) === JSON.stringify(Object.keys(parsed).sort()))
  expect('cli: a sweep without --root, with a transcript dir, with --require-effort, or --root without --lanes-sweep exits 2', [run('--lanes-sweep'), run('--lanes-sweep', '--root', sweepRoot, 'extra'), run('--lanes-sweep', '--root', sweepRoot, '--require-effort', 'max'), run('--root', sweepRoot, 'dir')].every((r) => r.status === 2))
  expect('cli: a bad or reversed window, an unknown option, a blank marker, a missing --rtk-db or a missing --root exits 2', [run('--lanes-sweep', '--root', sweepRoot, '--since', 'yesterday'), run('--lanes-sweep', '--root', sweepRoot, '--since', '2026-09-26T00:00:00Z', '--until', '2026-09-25T00:00:00Z'), run('--lanes-sweep', '--root', sweepRoot, '--bogus'), run('--lanes-sweep', '--root', sweepRoot, '--marker', ' '), run('--lanes-sweep', '--root', sweepRoot, '--rtk-db', join(sweepRoot, 'missing.db')), run('--lanes-sweep', '--root', join(sweepRoot, 'no-such-dir'))].every((r) => r.status === 2))
  {
    // Review finding 1 (2026-09-26): a sweep report larger than a pipe buffer (64 KiB on Linux) lost everything past
    // it when the sweep called process.exit() after console.log, so a piped reader got invalid JSON.
    const wide = mkdtempSync(join(tmpdir(), 'child-lanes-wide-'))
    try {
      for (let i = 0; i < 120; i++) {
        const file = join(wide, 'proj', 'sess-' + i, 'subagents', 'agent-w' + i + '.jsonl')
        mkdirSync(join(file, '..'), { recursive: true })
        writeFileSync(file, [ask('packet', 20), call('w' + i, 'Bash', { command: 'ls' }, 21, tokens(3, 40, 0))].map((r) => JSON.stringify(r)).join('\n') + '\n')
        utimesSync(file, written, written)
        writeFileSync(file.replace(/\.jsonl$/, '.meta.json'), JSON.stringify({ agentType: 'type-' + i }))
      }
      const piped = spawnSync(process.execPath, [script, '--lanes-sweep', '--root', wide, '--since', '2026-09-25T17:18:00Z', '--until', '2026-09-26T15:05:00Z'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
      let whole = null
      try { whole = JSON.parse(piped.stdout) } catch { whole = null }
      expect('cli: a --lanes-sweep report larger than a pipe buffer arrives whole through a pipe and exits 0', piped.stdout.length > 65536 && piped.status === 0 && whole !== null && whole.children_in_window === 120)
    } finally { rmSync(wide, { recursive: true, force: true }) }
  }
  if (typeof process.getuid === 'function' && process.getuid() !== 0) {
    const locked = join(sweepRoot, 'proj', 'locked')
    mkdirSync(locked)
    chmodSync(locked, 0o000)
    try {
      const partial = sweepLanes([sweepRoot], window)
      expect('sweep: an unreadable directory is counted, and the readable ones are still swept', partial.unreadable_directories === 1 && partial.children_in_window === 3)
    } finally { chmodSync(locked, 0o700) }
  } else console.log('SKIP sweep: unreadable-directory check needs a non-root user')
  expect('args: repeated single-value options are refused, --root repeats', parseArgs(['--lanes-sweep', '--root', 'a', '--root', 'b']).roots.length === 2 && Boolean(parseArgs(['x', '--marker', 'a', '--marker', 'b']).error) && Boolean(parseArgs(['--lanes-sweep', '--lanes-sweep', '--root', 'a']).error))
  let sqlite = null
  try { sqlite = await import('node:sqlite') } catch { sqlite = null }
  if (!sqlite) console.log('SKIP rtk-db: node:sqlite is not available in this Node (' + process.version + '); the join logic is covered above')
  else {
    // The upstream table (rtk v0.50.0 src/core/tracking.rs), filled with synthetic rows.
    const db = join(sweepRoot, 'history.db')
    const w = new sqlite.DatabaseSync(db)
    w.exec("CREATE TABLE hook_decisions (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, session_id TEXT NOT NULL, tool_use_id TEXT NOT NULL, project_path TEXT DEFAULT '', raw_cmd TEXT NOT NULL, decision TEXT NOT NULL, rewritten_cmd TEXT, rtk_version TEXT NOT NULL)")
    const insert = w.prepare('INSERT INTO hook_decisions (timestamp, session_id, tool_use_id, raw_cmd, decision, rewritten_cmd, rtk_version) VALUES (?, ?, ?, ?, ?, ?, ?)')
    for (const [id, decision] of [['t1', 'defer'], ['t1', 'ask'], ['t2', 'defer'], ['t3', 'deny'], ['w1', 'allow']]) insert.run(T(2), 's', id, 'cmd', decision, decision === 'ask' || decision === 'allow' ? 'rtk cmd' : null, '0.50.0')
    w.close()
    const before = readFileSync(db)
    const loaded = await loadRtkDecisions(db)
    expect('rtk-db: rows load read-only, the latest row per tool_use_id wins and duplicates are counted', loaded.rows === 5 && loaded.duplicates === 1 && loaded.map.get('t1') === 'ask' && readFileSync(db).equals(before))
    const joined = run('--lanes-sweep', '--root', sweepRoot, '--since', '2026-09-25T17:18:00Z', '--until', '2026-09-26T15:05:00Z', '--rtk-db', db)
    const all = joined.status === 0 ? JSON.parse(joined.stdout).groups.all : null
    expect('rtk-db: the sweep joins every Bash call in the window, and the database is unchanged', all && JSON.stringify(all.rtk.decisions) === JSON.stringify({ allow: 1, ask: 1, defer: 1, deny: 1, not_logged: 3, other: 0 }) && all.rtk.covered_share_of_bash === 0.2857 && readFileSync(db).equals(before))
  }
} finally { rmSync(sweepRoot, { recursive: true, force: true }) }
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
