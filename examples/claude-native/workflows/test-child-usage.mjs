#!/usr/bin/env node
// OFFLINE check of child-usage.mjs against SYNTHETIC transcript rows (no provider
// call, not native evidence). Real runs are checked by passing their directory;
// stored receipts from real runs are bound to the documentation by test-usage-receipts.mjs.
import { summarizeChild, summarizeRun, latestRunDir, effortMismatches, modelGeneration, expectedModel, webSearch, childLanes, aggregateLanes, sweepLanes, fetchKind, mcpServer, safeKey, tokenStats, parseArgs, loadRtkDecisions, DEFAULT_MARKER, executedText, logFindPart, sensitivePart } from './child-usage.mjs'
import * as kernel from './child-usage.mjs'
import { mkdtempSync, writeFileSync, rmSync, mkdirSync, utimesSync, readFileSync, chmodSync, copyFileSync, existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { tmpdir, homedir } from 'node:os'
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
expect('an omitted model is flagged as not requested explicitly, without claiming coordinator inheritance', !inherited.complete && inherited.requested_model === null && inherited.issues.some((i) => i.includes('not requested explicitly')) && !inherited.issues.some((i) => i.includes('inherits')))
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
expect('fallback: an alias without documented rows (haiku) is checked for changes only', summarizeChild(started, done, { model: 'haiku' }, [vmsg('m1', 'claude-haiku-4-5-20251001', '2.1.281')]).complete && !summarizeChild(started, done, { model: 'haiku' }, [vmsg('m1', 'claude-haiku-4-5-20251001', '2.1.281'), vmsg('m2', 'claude-sonnet-5', '2.1.281')]).complete)
expect('fallback: an opus model name that cannot be compared fails closed', has(summarizeChild(started, done, { model: 'opus' }, [vmsg('m1', 'claude-3-opus-20240229', '2.1.281')]), 'older than the documented alias resolution'))
expect('fallback: model names parse to family and version, ignoring date and [1m] suffixes', JSON.stringify([modelGeneration('claude-opus-5-5'), modelGeneration('claude-opus-5'), modelGeneration('claude-haiku-4-5-20251001'), modelGeneration('claude-opus-5-5[1m]'), modelGeneration('claude-3-opus-20240229')]) === JSON.stringify([{ family: 'opus', version: [5, 5] }, { family: 'opus', version: [5] }, { family: 'haiku', version: [4, 5] }, { family: 'opus', version: [5, 5] }, null]))
expect('fallback: the opus version table matches the documented boundaries', JSON.stringify(['2.1.153', '2.1.154', '2.1.218', '2.1.219', '2.1.279', '2.1.280', '2.1.281'].map((v) => expectedModel('opus', v))) === JSON.stringify([null, 'claude-opus-4-8', 'claude-opus-4-8', 'claude-opus-5', 'claude-opus-5', 'claude-opus-5-5', 'claude-opus-5-5']) && expectedModel('sonnet', '2.1.281') === 'claude-sonnet-5' && expectedModel('haiku', '2.1.281') === null && expectedModel('opus', undefined) === null)
// The same guards for the sonnet and fable rows (model-config doc, "version history" table, fetched 2026-09-29):
// sonnet is Sonnet 5.5 from v2.1.284 and Sonnet 5 from v2.1.197; fable is Fable 5.1 from v2.1.257.
expect('fallback: the sonnet version table matches the documented boundaries', JSON.stringify(['2.1.196', '2.1.197', '2.1.283', '2.1.284', '2.1.285'].map((v) => expectedModel('sonnet', v))) === JSON.stringify([null, 'claude-sonnet-5', 'claude-sonnet-5', 'claude-sonnet-5-5', 'claude-sonnet-5-5']))
expect('fallback: the fable version table matches the documented boundaries', JSON.stringify(['2.1.256', '2.1.257', '2.1.258', '2.1.284', '2.1.285'].map((v) => expectedModel('fable', v))) === JSON.stringify([null, 'claude-fable-5-1', 'claude-fable-5-1', 'claude-fable-5-1', 'claude-fable-5-1']))
const sonnetWhole = summarizeChild(started, done, { model: 'sonnet' }, [vmsg('m1', 'claude-sonnet-5', '2.1.284'), vmsg('m2', 'claude-sonnet-5', '2.1.284')])
expect('fallback: a sonnet child that ran entirely on claude-sonnet-5 under 2.1.284 is incomplete though the family check accepts it', !sonnetWhole.complete && !has(sonnetWhole, 'changed within') && !has(sonnetWhole, 'outside requested family') && has(sonnetWhole, 'older than the documented alias resolution') && has(sonnetWhole, 'claude-sonnet-5 on 2.1.284 (documented sonnet: claude-sonnet-5-5)'))
expect('fallback: sonnet on claude-sonnet-5-5 under 2.1.284 is complete', summarizeChild(started, done, { model: 'sonnet' }, [vmsg('m1', 'claude-sonnet-5-5', '2.1.284'), vmsg('m2', 'claude-sonnet-5-5', '2.1.284')]).complete)
expect('fallback: sonnet on claude-sonnet-5 under 2.1.283 is the documented resolution, not a fallback', summarizeChild(started, done, { model: 'sonnet' }, [vmsg('m1', 'claude-sonnet-5', '2.1.283'), vmsg('m2', 'claude-sonnet-5', '2.1.283')]).complete)
const sonnetSwitched = summarizeChild(started, done, { model: 'sonnet' }, [vmsg('m1', 'claude-sonnet-5-5', '2.1.284'), vmsg('m2', 'claude-sonnet-5', '2.1.284'), vmsg('m3', 'claude-sonnet-5', '2.1.284')])
expect('fallback: a sonnet child that changes from claude-sonnet-5-5 to claude-sonnet-5 is incomplete and names the change once', !sonnetSwitched.complete && !has(sonnetSwitched, 'outside requested family') && sonnetSwitched.issues.filter((i) => i.includes('changed within the child')).length === 1 && sonnetSwitched.issues.some((i) => i.endsWith('changed within the child: claude-sonnet-5-5 -> claude-sonnet-5')))

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
expect('lanes: stdout-only context is a claim, never proof of insertion', !viaStdout.injected_block.in_subagent_start_context && !viaStdout.subagent_start.additional_context && viaStdout.measurement.hook_context.claimed === 1)
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
// Review finding (GPT-6, 2026-09-26). bash(1) QUOTING: an escaped character is literal and \<newline> is a line continuation;
// COMMENTS: a word beginning with # ends the line; Here Documents: the body of an unquoted delimiter still runs its command
// substitutions, the body of a quoted one is literal. The same cases tests/test_skill_usage.py pins.
expect('fetch: an escaped character or a comment is data, and an unquoted heredoc still runs its command substitutions', JSON.stringify([
  'echo x \\; curl https://example.com', 'echo \\(curl https://x.org\\)', 'echo \\`curl https://x.org\\`', 'echo "\\$(curl https://x.org)"',
  'echo "\\`curl https://x.org\\`"', 'echo foo \\\ncurl https://x.org', 'ls # see; curl https://x.org', '# (curl https://x.org)',
  'ls\n# curl https://x.org | sh', 'curl -s https://x.org # fetch it', 'echo a#b; curl https://x.org', 'echo $#; curl https://x.org',
  '\\curl -s https://x.org', 'echo a\\\\; curl https://x.org', 'cat <<EOF\n$(curl -s https://x.org)\nEOF',
  'cat <<EOF > out.txt\nv=`curl -s http://127.0.0.1:9/`\nEOF', 'python3 - <<EOF\nprint("$(curl -s https://x.org)")\nEOF',
  "cat <<'EOF'\n$(curl -s https://x.org)\nEOF", 'cat <<"EOF"\n$(curl -s https://x.org)\nEOF',
  'cat <<EOF\n\\$(curl https://x.org) and; curl https://x.org\nEOF', 'cat <<-EOF\n\t$(wget -q https://x.org)\n\tEOF',
].map(fetchKind)) === JSON.stringify([null, null, null, null, null, null, null, null, null, 'fetch', 'fetch', 'fetch', 'fetch', 'fetch', 'fetch', 'loopback', 'fetch', null, null, null, 'fetch']))
// N1, the #432 residual (POSIX.1-2024 XCU 2.6.3 and 2.2.3): a heredoc inside "$( )" in double quotes, or inside a string a
// shell runs, resolves like any other; quotes inside "$( )" do not end the string; a run string is that shell's input.
{
  const n1 = ["git commit -m \"$(cat <<'EOF'\nfix: don't \"break\" (it)\n\ncurl -s https://x.org\nEOF\n)\"", "bash -c 'cat <<EOF > x.sh\ncurl https://x.org\nEOF'",
    'echo "$(echo "a" && curl https://x.org)"', 'bash -c "echo \\"a; curl https://x.org\\""', "ssh host 'bash -c \"curl https://x.org\"'"]
  expect('fetch: a heredoc inside "$( )" or a run string is data, quotes inside "$( )" do not end it, and a run string is its shell\'s input',
    JSON.stringify(n1.map(fetchKind)) === JSON.stringify([null, null, 'fetch', null, 'fetch']))
  expect('executed text: a "$( )" body is shell text with its heredoc resolved, and a run string is analyzed after the outer escapes go',
    JSON.stringify(n1.map((c) => executedText(c))) === JSON.stringify(["git commit -m \"$(cat <<'EOF'\n\n\n\n)\"", 'bash -c ;cat <<EOF > x.sh\n;',
      'echo "$(echo "a" && curl https://x.org)"', 'bash -c ;echo "a  curl https://x.org";', 'ssh host ;bash -c ;curl https://x.org;;']))
}
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
// CodeQL js/redos witnesses (2026-09-27): before the repair each took seconds at 28 repetitions, doubling with each one.
const timed = (f) => { const t = process.hrtime.bigint(), r = f(); return { r, ms: Number(process.hrtime.bigint() - t) / 1e6 } }
const gitWitness = 'git ' + '--git-dir --! '.repeat(28) + 'status'
const gitRun = timed(() => [logFindPart(gitWitness), sensitivePart(gitWitness)])
expect('redos: repeated --git-dir option words are read in linear time', gitRun.ms < 1000 && gitRun.r.join() === 'false,false')
const codeRun = timed(() => ['node -', 'bun -', 'deno eval -'].map((p) => executedText(p + '-- -'.repeat(28) + " 'fetch(u)'", { inlineHttp: true })))
expect('redos: repeated interpreter option words are matched in linear time', codeRun.ms < 1000)
// Nesting witnesses (2026-09-28): without NESTING_LIMIT both threw RangeError (maximum call stack size), aborting a sweep.
const deepRun = timed(() => { try { return ['"$('.repeat(3000), Array.from({ length: 3000 }, (_, i) => 'bash <<E' + i).join('\n')].map((c) => executedText(c).length + executedText(c, { inlineHttp: true }).length) } catch (e) { return e } })
expect('nesting: 3,000 nested "$( and a 3,000-deep shell heredoc chain are read without exhausting the stack', Array.isArray(deepRun.r) && deepRun.ms < 1000)
// D8 (GPT-6 #9, Claude review R9): the M4 text scanners read a run of unclosed "((" in linear time. Before the repair each
// unclosed "((" looked ahead to the end of its line, so n = 8000, 16000 and 32000 took about 315, 1100 and 5000 ms (four times
// per doubling). Each size is timed as the best of five runs; a run over 1.5 s ends the doubling (it is far past the bound
// already), and 5 ms of the allowance is timer and GC noise, not growth. The brief's requirement, at most 2.5 times per doubling and
// under 150 ms at 64,000, applies to that input (about 30 ms here); the other shapes below keep the ratio and take an absolute
// bound of 1.5 s at 64,000, since each does real work per unit and a CI runner is slower than this host.
{
  const ratio = (ms) => ms.length === 4 && ms.every((t, i) => i === 0 || t <= 2.5 * ms[i - 1] + 5)
  // Best of five per size; when the ratio fails, up to two more rounds and the elementwise minimum of all rounds, so one pause
  // (a GC or a busy runner) cannot fail a linear scan, while a quadratic one fails every round.
  const doubling = (make, run) => {
    run(make(2000)); run(make(2000)) // warm-up
    let best = []
    for (let round = 0; round < 3 && !ratio(best); round++) {
      const ms = []
      for (const n of [8000, 16000, 32000, 64000]) {
        const input = make(n)
        let t = Infinity
        for (let i = 0; i < 5; i++) { t = Math.min(t, timed(() => run(input)).ms); if (t > 1500) break }
        ms.push(t)
        if (t > 1500) break // far past the bound already
      }
      best = best.length ? ms.map((t, i) => Math.min(t, best[i] ?? Infinity)) : ms
    }
    return best
  }
  const linear = (ms) => ratio(ms) && ms[3] < 150 // the brief's bound, for '(('.repeat(n) + 'qmd'
  const linearWork = (ms) => ratio(ms) && ms[3] < 1500 // every other shape
  const shape = (label, make, reader, run, bound = linearWork) => {
    const ms = doubling(make, run)
    expect('linear: ' + label + ' (' + reader + ') at n = 8000, 16000, 32000, 64000 takes [' + ms.map((t) => t.toFixed(0)).join(', ') + '] ms', bound(ms))
  }
  const dparen = (n) => '(('.repeat(n) + 'qmd'
  shape('a run of unclosed ((', dparen, 'executedText', (c) => executedText(c), linear)
  shape('a run of unclosed ((', dparen, 'executedText inlineHttp', (c) => executedText(c, { inlineHttp: true }), linear)
  shape('a run of unclosed $((', (n) => '$(('.repeat(n) + 'qmd', 'executedText', (c) => executedText(c))
  shape('unclosed (( inside a double-quoted "$( "', (n) => 'echo "$( ' + '(('.repeat(n), 'executedText', (c) => executedText(c))
  shape('a run of heredoc operators after (', (n) => '(<<E'.repeat(n), 'executedText', (c) => executedText(c))
  // The run-string detectors read the text built so far at every quote: on a long script that was one flattening and one scan of the
  // whole prefix per quote, so a script of n quoted words cost n squared (a 346 KB script took 2 s a scan, and the kernel scans each shell
  // call several times).
  shape('a run of quoted words', (n) => "'a'".repeat(n), 'executedText', (c) => executedText(c))
  shape('a run of double-quoted substitutions', (n) => '"$(a)"'.repeat(n), 'executedText, inlineHttp', (c) => executedText(c, { inlineHttp: true }))
  shape('a run of run strings', (n) => 'bash -c "x" '.repeat(n), 'executedText', (c) => executedText(c))
  shape('a run of words with # inside', (n) => 'a#'.repeat(n), 'executedText', (c) => executedText(c))
  shape('a long script of echo, substitution and pipe lines', (n) => Array.from({ length: Math.ceil(n / 8) }, (_, i) => 'echo "step ' + i + ': $(date +%s)" >> log.txt; qmd search "term ' + i + '" -n 2 | head -5').join('\n'), 'fetchKind', (c) => fetchKind(c))
  // D8 for the command-position layer (GPT-6 #9; Claude review R9). The parser reads these texts in linear time, but the walk over a node's
  // children with child(i) and fieldNameForChild(i) cost O(i) per call in web-tree-sitter 0.27.0, so a flat run of unclosed constructs
  // (one wide ERROR node) or of comments (one wide program node) took four times as long for twice the text: '(('.repeat(n) + 'qmd'
  // took 467, 1853 and 7369 ms at n = 8000, 16000 and 32000 (GPT-6 measured 320, 1266 and 4992 ms at 3cb7c4f6). Each text is about
  // 2n characters at most. A run of unclosed `a=(` or of `<<` is not here: the parse itself is quadratic (tree-sitter-bash's error
  // recovery and heredoc scanner), which no reading can change (README, "What the parser costs").
  if ((await kernel.loadShellParser()).ok) {
    const lanes = (c) => kernel.commandInvocations(c)
    const runs = (unit, tail = '') => (n) => unit.repeat(Math.ceil((2 * n) / unit.length)) + tail
    shape('a run of unclosed ((', dparen, 'commandInvocations', lanes)
    shape('a run of unclosed $(', runs('$(', 'qmd'), 'commandInvocations', lanes)
    shape('a run of unclosed "$(', runs('"$(', 'qmd'), 'commandInvocations', lanes)
    shape('a run of unclosed $((', runs('$(( ', 'qmd'), 'commandInvocations', lanes)
    shape('a run of backquotes', runs('`'), 'commandInvocations', lanes)
    shape('a run of unclosed {', runs('{ '), 'commandInvocations', lanes)
    shape('a run of unclosed if', runs('if a; then '), 'commandInvocations', lanes)
    shape('a run of unclosed case', runs('case x in a) '), 'commandInvocations', lanes)
    shape('a run of comment lines', runs('# c\n'), 'commandInvocations', lanes)
  }
}
expect('git options: any reading of the option words reaches the subcommand, as in the RTK exclude_commands',
  logFindPart('git -C repo -c core.pager=cat --no-pager log -3') && logFindPart('git --git-dir .git --work-tree . log') && logFindPart('find . -name x')
  && !logFindPart('git status') && sensitivePart('git -C repo branch -a') && sensitivePart('git --git-dir=.g show HEAD:a') && !sensitivePart('git -C repo status'))
// CLI lanes (#381 AA-PLAN PR-A item 3; U1 design sections 2 and 7). commandInvocations reads every simple command of the text
// a shell runs (POSIX.1-2024 XCU 2.9.1-2.9.4 and 2.6.3) past assignments, reserved words, wrappers, package runners and `rtk
// proxy`, and names lane executables by exact basename; data, lookups and registrations run none. Each invocation is shown
// as lane/program[:op][@server] plus its flags, with '-' for no lane or no program.
{
  // The lane reading needs the verified tree-sitter-bash install (loadShellParser; CHILD_USAGE_SHELL_PARSER or the default directory).
  const laneParser = await kernel.loadShellParser()
  if (!laneParser.ok) console.log('SKIP cli lanes: no verified tree-sitter-bash install (' + laneParser.reason + '); see shell-parser.pin.json for the install command')
  const show = (i) => (i.lane ?? '-') + '/' + (i.program ?? '-') + (i.op ? ':' + i.op : '') + (i.server ? '@' + i.server : '')
    + (i.excluded ? ' excluded' : '') + (i.remote ? ' remote' : '') + (i.unresolved ? ' unresolved' : '')
  const read = (c) => {
    try { return typeof kernel.commandInvocations === 'function' ? kernel.commandInvocations(c).map(show) : ['(not exported)'] } catch (e) { return ['(threw ' + e.name + ')'] }
  }
  const check = (name, cases) => {
    if (!laneParser.ok) return
    const bad = cases.filter(([c, want]) => JSON.stringify(read(c)) !== JSON.stringify(want)).map(([c]) => JSON.stringify(c) + ' => ' + JSON.stringify(read(c)))
    expect(name + (bad.length ? ' [' + bad.join('; ') + ']' : ''), bad.length === 0)
  }
  const qmd = ['qmd/qmd'], proxy = 'rtk_proxy/rtk:proxy'
  check('cli lanes: POSIX, GNU and sudo wrappers are read to the utility they run', [
    ['timeout -k 5 60 qmd search x', qmd], ['timeout --signal=KILL -v 60 qmd search x', qmd], ['env -u X markitdown f.pdf', ['markitdown/markitdown']],
    ['env -C d repomix', ['repomix/repomix']], ['env -i -- FOO=1 qmd status', qmd], ['env -S "qmd search x"', qmd], ['nice -n 10 repomix', ['repomix/repomix']],
    ['sudo -u u ai-memory status', ['ai-memory/ai-memory']], ['sudo -E VAR=1 qmd status', qmd], ['command qmd status', qmd], ['command -p qmd status', qmd],
    ['time -p toon f.json', ['toon/toon']], ['stdbuf -oL qmd search x', qmd], ['nohup qmd update &', qmd], ['exec qmd mcp', qmd], ['FOO=1 BAR=2 qmd status', qmd],
    ['find . -print0 | xargs -0 -n1 markitdown', ['-/-', 'markitdown/markitdown']], ['xargs', ['-/-']],
  ])
  check('cli lanes: an option a wrapper does not document leaves the program unresolved, and a lookup or non-run mode runs none', [
    ['command -v qmd', []], ['command -V qmd', []], ['sudo -l qmd', []], ['exec -a name qmd mcp', ['-/- unresolved']], ['exec -- qmd mcp', ['-/- unresolved']], ['xargs -P 4 qmd get', ['-/- unresolved']],
    ['nice -10 qmd update', ['-/- unresolved']], ['env --bogus qmd', ['-/- unresolved']], ['timeout 60', []],
  ])
  check('cli lanes: compound commands, substitutions, shell strings and shell heredocs', [
    ['for f in *.pdf; do markitdown "$f"; done', ['markitdown/markitdown']], ['if qmd status; then :; fi', ['qmd/qmd', '-/-']],
    ['(cd d && qmd status)', ['-/-', 'qmd/qmd']], ['{ qmd get a; }', qmd], ['! qmd search x', qmd], ['x=$(qmd get a)', qmd],
    ['echo "$(qmd get a)"', ['-/-', 'qmd/qmd']], ['echo `qmd get a`', ['-/-', 'qmd/qmd']], ["bash -c 'qmd search x'", ['-/bash', 'qmd/qmd']],
    ['sh -c "rtk proxy pytest"', ['-/sh', proxy, '-/-']], ["bash <<'EOF'\nqmd search x\nEOF", ['-/bash', 'qmd/qmd']],
    ['cat <<EOF\n$(qmd get a)\nEOF', ['-/-', 'qmd/qmd']], ['qmd search x 2>&1 >/dev/null | head -n 5', ['qmd/qmd', '-/-']],
    ['echo $(date) qmd', ['-/-', '-/-']], ['cat <(qmd get a)', ['-/-', 'qmd/qmd']],
  ])
  check('cli lanes: rtk proxy after global options, its own options and an optional --; one spaced argument is split and no shell runs it', [
    ['rtk proxy qmd search x', [proxy, 'qmd/qmd']], ["rtk proxy 'qmd search x'", [proxy, 'qmd/qmd']], ['rtk --ultra-compact proxy pytest', [proxy, '-/-']],
    ['rtk -v proxy pytest', [proxy, '-/-']], ['rtk -vv --skip-env proxy pytest', [proxy, '-/-']], ['rtk proxy -- qmd status', [proxy, 'qmd/qmd']],
    ['rtk proxy --skip-env qmd status', [proxy, 'qmd/qmd']], ['rtk proxy -v qmd', [proxy, '-/-']], ['rtk proxy', [proxy]],
    ["rtk proxy 'cd repo && qmd x'", [proxy, '-/-']], ['cd repo && rtk proxy pytest -q', ['-/-', proxy, '-/-']], ['FOO=1 rtk proxy pytest', [proxy, '-/-']],
    ['rtk proxy --help', [proxy + ' excluded']], ['rtk --version', ['rtk_proxy/rtk excluded']], ['rtk -V', ['rtk_proxy/rtk excluded']],
    ['rtk proxy qmd --version', [proxy, 'qmd/qmd excluded']], ['rtk git status', ['-/rtk']], ['rtk proxy npx repomix', [proxy, 'repomix/repomix']],
  ])
  check('cli lanes: npm and PyPI runners map their package to the lane; --package and --from name the executable', [
    ['npx -y repomix --mcp', ['repomix/repomix']], ['npx repomix@latest', ['repomix/repomix']], ['npx @toon-format/cli f.json', ['toon/toon']],
    ['npx @tobilu/qmd@2.8.3 search x', qmd], ['npx --package=@tobilu/qmd -- qmd search x', qmd], ['bunx @tobilu/qmd search x', qmd],
    ['bun x repomix', ['repomix/repomix']], ['pnpm dlx repomix', ['repomix/repomix']], ['yarn dlx @toon-format/cli f.json', ['toon/toon']],
    ['uvx jcodemunch-mcp', ['jcodemunch-mcp/jcodemunch-mcp']], ['uvx --from serena-agent serena start-mcp-server', ['serena/serena']],
    ['uvx markitdown==0.1.8 f.pdf', ['markitdown/markitdown']], ['uv tool run markitdown f.pdf', ['markitdown/markitdown']], ['pipx run headroom-ai', ['headroom/headroom']],
    ['python3 -m markitdown f.pdf', ['markitdown/markitdown']], ['npx markitdown f.pdf', ['-/markitdown']], ['npx -c "qmd search x"', ['-/- unresolved']],
    ['uvx --bogus qmd', ['-/- unresolved']], ['npx repomix --version', ['repomix/repomix excluded']],
  ])
  check('cli lanes: lane executables by exact basename; gcm and serena-hooks are not lane executables', [
    ['serena init', ['serena/serena']], ['serena-agent start', ['serena/serena-agent']], ['context-mode doctor', ['context-mode/context-mode']],
    ["codebase-memory-mcp cli search_graph '{}'", ['codebase-memory-mcp/codebase-memory-mcp']], ['/usr/local/bin/qmd search x', qmd],
    ['headroom mcp serve --proxy-url http://127.0.0.1:1', ['headroom/headroom']], ['jcodemunch-mcp', ['jcodemunch-mcp/jcodemunch-mcp']],
    ['gcm chat', ['-/-']], ['serena-hooks pre-tool', ['-/-']], ['qmdx', ['-/-']], ['my-repomix', ['-/-']],
  ])
  check('cli lanes: mcporter operations, and the downstream server of a call (never a host)', [
    ['mcporter call linear.create_comment --issue-id X', ['mcporter/mcporter:call@(other)']],
    [`mcporter call 'linear.create_comment(issueId: "LNR-123", body: "Hi")'`, ['mcporter/mcporter:call@(other)']],
    [`mcporter 'context7.resolve-library-id("React hooks docs", "react")'`, ['mcporter/mcporter:call@(other)']],
    ['mcporter call --server linear --tool create_comment', ['mcporter/mcporter:call@(other)']], ['mcporter call linear create_comment', ['mcporter/mcporter:call@(other)']],
    ['mcporter call create_comment server=linear', ['mcporter/mcporter:call@(other)']], ['mcporter call server=linear tool=create_comment', ['mcporter/mcporter:call@(other)']],
    ['mcporter call --server other linear.create_comment', ['mcporter/mcporter:call@(other)']],
    ['npx mcporter call https://mcp.context7.com/mcp.resolve-library-id', ['mcporter/mcporter:call@(http)']],
    ['mcporter call mcp.context7.com/mcp.resolve-library-id', ['mcporter/mcporter:call@(http)']],
    ['mcporter call --http-url https://mcp.example.org/mcp --server linear create_comment', ['mcporter/mcporter:call@(http)']],
    ['mcporter call --stdio "qmd mcp" query', ['mcporter/mcporter:call@(stdio)']], ['mcporter call "npx -y chrome-devtools-mcp@latest" list_pages', ['mcporter/mcporter:call@(stdio)']],
    ['mcporter call ./server.js tool', ['mcporter/mcporter:call@(stdio)']], ['mcporter call --server mcp.example.org tool', ['mcporter/mcporter:call@(other)']],
    ['mcporter call --server "npx -y some-mcp" tool', ['mcporter/mcporter:call@(stdio)']], ['mcporter call --server "my server" tool', ['mcporter/mcporter:call@(other)']],
    ['mcporter --config c.json --log-level debug call x.y --timeout 5000 --output json -- --literal', ['mcporter/mcporter:call@(other)']],
    ['mcporter call', ['mcporter/mcporter:call@(unresolved)']], ['mcporter list socraticode --brief --no-oauth', ['mcporter/mcporter:list']],
    ['mcporter socraticode', ['mcporter/mcporter:list']], ['mcporter https://mcp.context7.com/mcp', ['mcporter/mcporter:list']], ['mcporter describe linear', ['mcporter/mcporter:list']],
    ['mcporter auth linear', ['mcporter/mcporter:auth']], ['mcporter daemon start', ['mcporter/mcporter:daemon']],
    ['mcporter --version', ['mcporter/mcporter:version excluded']], ['mcporter -v', ['mcporter/mcporter:version excluded']], ['mcporter -V', ['mcporter/mcporter:version excluded']],
    ['mcporter', ['mcporter/mcporter:help excluded']], ['mcporter help', ['mcporter/mcporter:help excluded']], ['mcporter -h', ['mcporter/mcporter:help excluded']],
    ['mcporter call linear.create_comment --help', ['mcporter/mcporter:call excluded']], ['mcporter serve --help', ['mcporter/mcporter:serve excluded']],
  ])
  // openclaw/mcporter@93e0916c (v0.14.1; the installed 0.14.1 binary reads every case below the same way): a global flag is removed only as the
  // exact word --config, --root, --log-level or --oauth-timeout with its value in the next word (src/cli/cli-factory.ts:19; extractFlags matches a
  // token by equality, src/cli/flag-utils.ts:12), and the call and ad-hoc flags are matched by equality too (src/cli/call-arguments.ts:63,115;
  // src/cli/ephemeral-flags.ts:30), so a flag written with = is not one of them: on a call it is the generic --key=value named argument
  // (call-arguments.ts:120-121, :333), and before the command it is the command word itself. `mcporter --config=c.json list x` therefore
  // reads as the implicit call `list.x` (a command word with a dot), and `mcporter call --server=qmd x.y` calls the server x, not qmd.
  check('cli lanes: mcporter takes a flag written with = as a named argument or a command word, never as a global, server or ad-hoc server flag', [
    ['mcporter --config=c.json list x', ['mcporter/mcporter:call@(other)']], ['mcporter --root=. list x', ['mcporter/mcporter:call@(other)']],
    ['mcporter --log-level=debug list', ['mcporter/mcporter:list']], ['mcporter --config c.json list x', ['mcporter/mcporter:list']],
    ['mcporter call --server=qmd x.y', ['mcporter/mcporter:call@(other)']], ['mcporter call --server qmd x.y', ['mcporter/mcporter:call@qmd']],
    ['mcporter call --mcp=qmd x.y', ['mcporter/mcporter:call@(other)']], ['mcporter call --http-url=https://mcp.example.org/mcp x.y', ['mcporter/mcporter:call@(other)']],
    ['mcporter call --http-url https://mcp.example.org/mcp x.y', ['mcporter/mcporter:call@(http)']],
  ])
  // ssh(1) (OpenSSH 9.6p1): the words after the destination are the command the remote host runs, so `ssh host bash -s` runs bash there
  // (a remote invocation of its own) and the heredoc it reads is its script.
  // U1 pivot D5: a server of the stack (manifests/stack.json:280, :407, :629 and :966, and the coordinator's closed set) is emitted by name in
  // every selector form; any other server reads (other), an HTTP or stdio selector (http) or (stdio).
  check('cli lanes: the stack\'s own servers are read by name in every selector form', [
    ['mcporter call socraticode.create_comment --issue-id X', ['mcporter/mcporter:call@socraticode']],
    [`mcporter call 'serena.create_comment(issueId: "LNR-123", body: "Hi")'`, ['mcporter/mcporter:call@serena']],
    [`mcporter 'jcodemunch.resolve-library-id("React hooks docs", "react")'`, ['mcporter/mcporter:call@jcodemunch']],
    ['mcporter call --server ai-memory --tool create_comment', ['mcporter/mcporter:call@ai-memory']], ['mcporter call qmd create_comment', ['mcporter/mcporter:call@qmd']],
    ['mcporter call create_comment server=headroom', ['mcporter/mcporter:call@headroom']],
    ['mcporter --config c.json --log-level debug call context-mode.y --timeout 5000 --output json -- --literal', ['mcporter/mcporter:call@context-mode']],
    ['mcporter call codebase-memory.search_graph', ['mcporter/mcporter:call@codebase-memory']],
  ])
  check('cli lanes: data, lookups, registrations, remote strings, version and help, and programs a variable names', [
    ['type qmd', ['-/-']], ['which qmd', ['-/-']], ['hash qmd', ['-/-']], ['grep -n qmd notes.md', ['-/-']], ['git commit -m "use toon"', ['-/-']],
    ["echo 'rtk proxy ls'", ['-/-']], ['echo "rtk proxy pytest"', ['-/-']], ['git log --grep="rtk proxy"', ['-/-']], ['# qmd search x', []],
    ['cat ~/.qmd/index.sqlite', ['-/-']], ['ls toon/', ['-/-']], ["git commit -m \"$(cat <<'EOF'\nqmd search x\nEOF\n)\"", ['-/-', '-/-']],
    ['cat <<EOF > run.sh\nrtk proxy pytest\nEOF', ['-/-']], ['claude mcp add context-mode -- npx -y context-mode', ['-/-']], ['codex mcp add qmd -- qmd mcp', ['-/-']],
    ["ssh host 'qmd search x'", ['-/ssh', 'qmd/qmd remote']], ['echo `ssh host "qmd get a"`', ['-/-', '-/ssh', 'qmd/qmd remote']], ['ssh host bash -s <<EOF\nqmd search x\nEOF', ['-/ssh', '-/bash remote', 'qmd/qmd remote']],
    ['$QMD search x', ['-/- unresolved']], ['"$QMD" search x', ['-/- unresolved']], ["'$QMD' search x", ['-/-']],
    ['qmd --version', ['qmd/qmd excluded']], ['qmd search x --help', ['qmd/qmd excluded']], ['qmd search -- --help', qmd], ['qmd -h', qmd],
    ['toon --help', ['toon/toon excluded']], ['ai-memory --version', ['ai-memory/ai-memory excluded']],
  ])
  // GPT-6 #10 (U1 pivot D5): `program` is a fixed name, never text from the command: it is set only for a lane executable or a name
  // this reading interprets itself (a wrapper, a shell, eval, ssh, rtk); any other program reads null, however name-shaped it is.
  if (laneParser.ok) {
    const programs = (c) => { try { return kernel.commandInvocations(c).map((i) => i.program) } catch (e) { return ['(threw ' + e.name + ')'] } }
    const want = [['my-private-host.example', [null]], ['call_PRIVATE.search x', [null]], ['git status', [null]], ['./deploy-secret-name --now', [null]],
      ['qmd search x', ['qmd']], ['/usr/local/bin/toon f.json', ['toon']], ['rtk git status', ['rtk']], ["bash -c 'x'", ['bash', null]],
      ['env FOO=1 my-private-host.example', [null]], ['npx some-private-package', [null]], ['npx repomix', ['repomix']], ['uvx private-pkg', [null]],
      ['xargs my-private-host.example', [null]], ['echo $(my-private-host.example)', [null, null]], ["ssh host 'qmd get a'", ['ssh', 'qmd']]]
    const bad = want.filter(([c, p]) => JSON.stringify(programs(c)) !== JSON.stringify(p)).map(([c]) => JSON.stringify(c) + ' => ' + JSON.stringify(programs(c)))
    expect('cli lanes: a program name is emitted only for a lane executable or a name the reading interprets' + (bad.length ? ' [' + bad.join('; ') + ']' : ''), bad.length === 0)
  }
  // D9 (GPT-6 #13, Claude review R2): the earlier assertion read every input through read(), which turns an exception into an
  // array whose length is an integer, so it passed when every stress input threw. The stress reader below lets an exception
  // fail the check, and a mutation control shows that it does. '$('.repeat(3000) is the unquoted nesting that walks past
  // NESTING_LIMIT (the '"$(' input stays inside the quoted-data scan, which never reaches that guard).
  const stressInputs = ['env -u X '.repeat(4000) + 'qmd', 'rtk -v '.repeat(4000) + 'proxy qmd', 'timeout -k 1 '.repeat(3000) + '5 qmd', '"$('.repeat(3000),
    '$('.repeat(3000), 'mcporter call --x '.repeat(4000) + 'a.b', '(('.repeat(4000) + 'qmd', "'".repeat(8001)]
  const stress = (invocations) => {
    const threw = []
    const run = timed(() => stressInputs.map((c) => { try { return invocations(c).length } catch (e) { threw.push(e.name); return -1 } }))
    return { ms: run.ms, threw, lengths: run.r }
  }
  const stressPasses = (s) => s.ms < 1000 && s.threw.length === 0 && s.lengths.every((n) => Number.isInteger(n) && n >= 0)
  const throwing = (c) => { if (c.length > 5000) throw new RangeError('mutation control'); return kernel.commandInvocations(c) }
  // The mutation control needs no parser: the reader below throws for every long input, and the check must fail for it.
  const mutated = stress((c) => { if (c.length > 5000) throw new RangeError('mutation control'); return [] })
  expect('cli lanes: the stress check fails when every long input throws (mutation control) [threw ' + mutated.threw.length + ' of ' + stressInputs.length + ']',
    mutated.threw.length === stressInputs.filter((c) => c.length > 5000).length && !stressPasses(mutated))
  if (laneParser.ok) {
    const real = stress(kernel.commandInvocations)
    expect('cli lanes: long and deeply nested commands are read in linear time without exhausting the stack [' + real.ms.toFixed(0) + ' ms, threw: ' + (real.threw.join() || 'none') + ']', stressPasses(real))
    const partial = stress(throwing)
    expect('cli lanes: the same check fails on the real reader wrapped to throw for long input [threw ' + partial.threw.length + ']', !stressPasses(partial))
    // D4(a): a string that a shell, eval or ssh runs is read again up to NESTING_LIMIT (32) levels; the text of a deeper level is one
    // unresolved record and never a lane, and nothing throws or leaves a tree open (the stress inputs above never reach this guard).
    const nested = (n) => {
      const found = kernel.commandInvocations('eval '.repeat(n) + 'qmd status')
      return { evals: found.filter((i) => i.program === 'eval').length, lanes: found.filter((i) => i.lane === 'qmd').length, unresolved: found.filter((i) => i.unresolved).length }
    }
    const depth = JSON.stringify([nested(31), nested(32), nested(33), nested(3000)])
    expect('cli lanes: 32 levels of eval are read, the 33rd is one unresolved record and never a lane, and 3,000 levels neither throw nor leave a tree open [' + depth + ']',
      depth === JSON.stringify([{ evals: 31, lanes: 1, unresolved: 0 }, { evals: 32, lanes: 1, unresolved: 0 }, { evals: 33, lanes: 0, unresolved: 1 }, { evals: 33, lanes: 0, unresolved: 1 }])
      && kernel.openShellTrees() === 0)
  }
}
// D1 (U1 pivot brief): loadShellParser verifies the pinned tree-sitter-bash install (shell-parser.pin.json: the sha256 of every
// pinned file and both npm integrity values of the install's package-lock.json) before anything loads, and never falls back to the
// text scanners: without the parser commandInvocations returns null and measurement says so (cli_lanes.status
// parser_unavailable, proxy.rule prefix_fallback). The expected values below are the ones the coordinator provisioned and this
// stage re-verified against the npm registry (dist.integrity) and the installed files (sha256sum) on 2026-09-29.
{
  const load = typeof kernel.loadShellParser === 'function' ? kernel.loadShellParser : async () => ({ ok: false, reason: '(loadShellParser is not exported)' })
  const status = typeof kernel.shellParserStatus === 'function' ? kernel.shellParserStatus : () => ({ ok: false, reason: '(shellParserStatus is not exported)' })
  const PACKAGES = {
    'web-tree-sitter': { version: '0.27.0', integrity: 'sha512-XK08gj6RwTMQatAG7uVRP8MunqotL/XC19vHgkSPKmELgbGPBj4ECvB8haHOUnyj6ls2B8t42UTro14zxGgAHg==' },
    'tree-sitter-bash': { version: '0.25.1', integrity: 'sha512-7hMytuYIMoXOq24yRulgIxthE9YmggZIOHCyPTTuJcu6EU54tYD+4G39cUb28kxC6jMf/AbPfWGLQtgPTdh3xw==' },
  }
  const FILES = {
    'node_modules/tree-sitter-bash/package.json': '757d74350c9a8cf2635010326ef3b28b59c392e705906af4d98e5a45fcaff32d',
    'node_modules/tree-sitter-bash/tree-sitter-bash.wasm': '8292919c88a0f7d3fb31d0cd0253ca5a9531bc1ede82b0537f2c63dd8abe6a7a',
    'node_modules/web-tree-sitter/package.json': '707dd14277ba63ca8dcaad6b6df8051e23df78c878b5cbdc27885b3cfd72bfac',
    'node_modules/web-tree-sitter/web-tree-sitter.cjs': '743de33347202f863b6714fc7218c455d93f751943d43500500f6c5c65654dce',
    'node_modules/web-tree-sitter/web-tree-sitter.js': '7c49e3c1d87e24e0bb4c2def909d17154dfde281f5f8280225450090bb4b8110',
    'node_modules/web-tree-sitter/web-tree-sitter.wasm': 'c03bccdc3b448a32848f5ae327e209c982bbb0840d43eec8bc2d5759544a1ed3',
  }
  const same = (a, b) => typeof kernel.sortedJson === 'function' && kernel.sortedJson(a) === kernel.sortedJson(b)
  const RECORD = { versions: { tree_sitter_bash: '0.25.1', web_tree_sitter: '0.27.0' },
    wasm_sha256: { tree_sitter_bash: FILES['node_modules/tree-sitter-bash/tree-sitter-bash.wasm'], web_tree_sitter: FILES['node_modules/web-tree-sitter/web-tree-sitter.wasm'] } }
  let pin = null
  try { pin = JSON.parse(readFileSync(new URL('./shell-parser.pin.json', import.meta.url), 'utf8')) } catch { pin = null }
  expect('parser pin: shell-parser.pin.json pins both packages (version, npm integrity, upstream tag), the six files and the install command',
    pin !== null && Object.entries(PACKAGES).every(([name, p]) => pin.packages?.[name]?.version === p.version && pin.packages[name].integrity === p.integrity
      && typeof pin.packages[name].upstream?.tag === 'string' && /^[0-9a-f]{40}$/.test(pin.packages[name].upstream?.tag_commit ?? ''))
    && same(pin.files, FILES) && typeof pin.install?.command === 'string' && pin.install.command.includes('--ignore-scripts') && pin.install.command.includes('web-tree-sitter@0.27.0 tree-sitter-bash@0.25.1'))
  const home = process.env.CHILD_USAGE_SHELL_PARSER || join(homedir(), '.local', 'share', 'codex-ecosystem', 'tools', 'tree-sitter-bash-0.25.1')
  const installed = existsSync(join(home, 'package-lock.json'))
  const tmp = mkdtempSync(join(tmpdir(), 'shell-parser-'))
  try {
    const missing = await load(join(tmp, 'absent'))
    expect('parser: a directory with no install is not_installed [' + JSON.stringify(missing) + ']', same(missing, { ok: false, reason: 'not_installed' }))
    // An explicit --shell-parser that cannot be honored is an error (exit 2 like --rtk-db and --exceptions), never a silent default.
    const flagRoot = join(tmp, 'flag-sweep'), flagFile = join(flagRoot, 'proj', 'sess', 'subagents', 'agent-a1.jsonl')
    mkdirSync(join(flagFile, '..'), { recursive: true })
    writeFileSync(flagFile, JSON.stringify({ type: 'user', timestamp: T(1), message: { role: 'user', content: 'go' } }) + '\n')
    utimesSync(flagFile, new Date('2026-09-27T00:00:00Z'), new Date('2026-09-27T00:00:00Z'))
    const refused = spawnSync(process.execPath, [fileURLToPath(new URL('./child-usage.mjs', import.meta.url)), '--lanes-sweep', '--root', flagRoot, '--shell-parser', join(tmp, 'absent')],
      { encoding: 'utf8', env: { PATH: process.env.PATH, HOME: tmp } })
    expect('parser: --shell-parser naming a directory with no install exits 2 with the reason and no report [' + refused.status + ', ' + JSON.stringify(refused.stderr.slice(0, 80)) + ']',
      refused.status === 2 && refused.stderr.includes('--shell-parser') && refused.stderr.includes('not_installed') && refused.stdout === '' && !refused.stderr.includes(tmp))
    expect('parser: without the parser commandInvocations returns null (no fallback to the scanners) and the status says why [' + JSON.stringify(status()) + ']',
      kernel.commandInvocations('qmd search x') === null && same(status(), { ok: false, reason: 'not_installed' }))
    const rows = [
      { type: 'assistant', timestamp: T(1), message: { content: [{ type: 'tool_use', id: 'p1', name: 'Bash', input: { command: 'rtk proxy pytest' } }] } },
      { type: 'user', timestamp: T(1), message: { content: [{ type: 'tool_result', tool_use_id: 'p1', content: 'ok', is_error: false }] } },
      { type: 'assistant', timestamp: T(2), message: { content: [{ type: 'tool_use', id: 'p2', name: 'Bash', input: { command: 'cd repo && rtk proxy pytest -q' } }] } },
      { type: 'user', timestamp: T(2), message: { content: [{ type: 'tool_result', tool_use_id: 'p2', content: 'ok', is_error: false }] } },
      { type: 'assistant', timestamp: T(3), message: { content: [{ type: 'tool_use', id: 'p3', name: 'Bash', input: { command: 'qmd search x && curl https://example.org' } }] } },
      { type: 'user', timestamp: T(3), message: { content: [{ type: 'tool_result', tool_use_id: 'p3', content: 'ok', is_error: false }] } },
    ]
    const closed = kernel.measureTranscript(rows)
    expect('parser: cli_lanes reports parser_unavailable with the reason and no lane counts [' + JSON.stringify(closed.cli_lanes) + ']', same(closed.cli_lanes, { status: 'parser_unavailable', reason: 'not_installed' }))
    expect('parser: without the parser proxy uses the prefix rule and says so; the counts that need the parser are unknown [' + JSON.stringify(closed.proxy) + ']',
      closed.proxy.rule === 'prefix_fallback' && closed.proxy.calls === 1 && closed.proxy.prefix_rule_calls === 1 && closed.proxy.invocations === null && closed.proxy.in_ctx_code === null
      && closed.by_carrier.rtk_proxy?.results === 1 && closed.by_carrier.bash?.results === 2)
    expect('parser: M4 stays text-based and is unchanged without the parser [' + JSON.stringify([closed.m4.shell_fetch, closed.m4.fetch_mentions_unconfirmed]) + ']', closed.m4.shell_fetch === 1 && closed.m4.fetch_mentions_unconfirmed === 0)
    expect('parser: withShellTree returns null and opens no tree without the parser', typeof kernel.withShellTree === 'function' && kernel.withShellTree('a=1', () => 1) === null && kernel.openShellTrees?.() === 0)
    const agg = kernel.aggregateMeasurements([closed, closed])
    expect('parser: an aggregate of measurements without the parser says so [' + JSON.stringify(agg.cli_lanes) + ']', agg.cli_lanes?.status === 'parser_unavailable' && agg.cli_lanes.reason === 'not_installed' && agg.proxy.rule === 'prefix_fallback' && agg.proxy.invocations === null)
    expect('parser: an aggregate of no measurements is not_measured [' + JSON.stringify(kernel.aggregateMeasurements([]).cli_lanes) + ']', kernel.aggregateMeasurements([]).cli_lanes?.status === 'not_measured')
    if (!installed) console.log('SKIP parser: no tree-sitter-bash install at the default directory (or CHILD_USAGE_SHELL_PARSER); the installed, hash_mismatch and parse checks need it')
    else {
      const copy = (name, tamper = () => {}) => {
        const dest = join(tmp, name)
        for (const rel of [...Object.keys(FILES), 'package-lock.json']) { mkdirSync(join(dest, rel, '..'), { recursive: true }); copyFileSync(join(home, rel), join(dest, rel)) }
        tamper(dest)
        return dest
      }
      const append = (rel, text) => (dest) => writeFileSync(join(dest, rel), Buffer.concat([readFileSync(join(dest, rel)), Buffer.from(text)]))
      // One byte of the file changed in place (bit 0 of the middle byte): the same length, so only the hash can tell.
      const flip = (rel) => (dest) => { const b = readFileSync(join(dest, rel)); b[b.length >> 1] ^= 1; writeFileSync(join(dest, rel), b) }
      const good = await load(copy('good'))
      expect('parser: the pinned install loads and reports versions and the two wasm sha256 values, never a path [' + JSON.stringify(good) + ']',
        good.ok === true && same({ versions: good.versions, wasm_sha256: good.wasm_sha256 }, RECORD) && !JSON.stringify(good).includes(tmp) && !JSON.stringify(good).includes(homedir()))
      expect('parser: shellParserStatus repeats the loaded record', same(status(), good) && kernel.commandInvocations('qmd search x')?.length === 1)
      const opened = kernel.withShellTree?.('a=( qmd )', (root) => [root.type, root.hasError, root.firstNamedChild?.type])
      expect('parser: withShellTree hands over the tree root and frees the tree [' + JSON.stringify(opened) + ']', same(opened, ['program', false, 'variable_assignment']) && kernel.openShellTrees?.() === 0)
      let threw = null
      try { kernel.withShellTree?.('a=1', () => { throw new RangeError('visitor failed') }) } catch (e) { threw = e.name }
      expect('parser: a visitor that throws still frees the tree [' + threw + ', open ' + kernel.openShellTrees?.() + ']', threw === 'RangeError' && kernel.openShellTrees?.() === 0)
      const cases = [
        ['one flipped byte in the bash grammar wasm', 'wasm', flip('node_modules/tree-sitter-bash/tree-sitter-bash.wasm')],
        ['a modified web-tree-sitter.js, which is never imported', 'js', append('node_modules/web-tree-sitter/web-tree-sitter.js', '\nglobalThis.__shellParserPwned = true\n')],
        ['a modified package.json', 'pkg', append('node_modules/tree-sitter-bash/package.json', ' ')],
        ['another integrity value in package-lock.json', 'lock', (dest) => writeFileSync(join(dest, 'package-lock.json'), readFileSync(join(dest, 'package-lock.json'), 'utf8').replace('sha512-7hMytu', 'sha512-XXXXXX'))],
        ['another version in package-lock.json', 'version', (dest) => writeFileSync(join(dest, 'package-lock.json'), readFileSync(join(dest, 'package-lock.json'), 'utf8').replace('"version": "0.27.0"', '"version": "0.27.1"'))],
      ]
      for (const [what, name, tamper] of cases) {
        const r = await load(copy('bad-' + name, tamper))
        expect('parser: ' + what + ' is hash_mismatch, and the parser stays unavailable [' + JSON.stringify(r) + ']',
          same(r, { ok: false, reason: 'hash_mismatch' }) && status().ok === false && kernel.commandInvocations('qmd') === null && globalThis.__shellParserPwned === undefined)
      }
      if (typeof process.getuid === 'function' && process.getuid() !== 0) {
        const locked = copy('locked', (dest) => chmodSync(join(dest, 'node_modules/tree-sitter-bash/tree-sitter-bash.wasm'), 0o000))
        const denied = await load(locked)
        chmodSync(join(locked, 'node_modules/tree-sitter-bash/tree-sitter-bash.wasm'), 0o600)
        expect('parser: a pinned file that cannot be read is load_error, not a hash mismatch [' + JSON.stringify(denied) + ']', same(denied, { ok: false, reason: 'load_error' }) && kernel.commandInvocations('qmd') === null)
      } else console.log('SKIP parser: the unreadable-file check needs a non-root user')
      for (const rel of Object.keys(FILES)) {
        const r = await load(copy('flip-' + rel.replaceAll('/', '_'), flip(rel)))
        expect('parser: one flipped byte in ' + rel + ' is hash_mismatch and leaves no parser [' + JSON.stringify(r) + ']',
          same(r, { ok: false, reason: 'hash_mismatch' }) && status().ok === false && kernel.commandInvocations('qmd') === null && globalThis.__shellParserPwned === undefined)
      }
      const partial = await load(copy('partial', (dest) => rmSync(join(dest, 'node_modules/web-tree-sitter/web-tree-sitter.wasm'))))
      expect('parser: an install with a pinned file missing is not_installed and leaves no parser [' + JSON.stringify(partial) + ']', same(partial, { ok: false, reason: 'not_installed' }) && kernel.commandInvocations('qmd') === null)
      const noLock = await load(copy('no-lock', (dest) => rmSync(join(dest, 'package-lock.json'))))
      expect('parser: an install without its package-lock.json is not_installed and leaves no parser [' + JSON.stringify(noLock) + ']', same(noLock, { ok: false, reason: 'not_installed' }) && kernel.commandInvocations('qmd') === null)
      const again = await load(copy('good-again'))
      expect('parser: a good install loads again after failures [' + JSON.stringify(again) + ']', again.ok === true && kernel.commandInvocations('qmd search x')?.length === 1)
      const open = kernel.measureTranscript(rows)
      expect('parser: with the parser cli_lanes is measured and records the parser, and proxy follows command position [' + JSON.stringify([open.cli_lanes?.status, open.cli_lanes?.parser, open.proxy.rule, open.proxy.calls]) + ']',
        open.cli_lanes?.status === 'measured' && same(open.cli_lanes.parser, RECORD) && open.proxy.rule === 'command_position' && open.proxy.calls === 2 && open.proxy.prefix_rule_calls === 1)
      const aggOpen = kernel.aggregateMeasurements([open, open])
      expect('parser: an aggregate of measured transcripts keeps the parser record and sums lanes [' + JSON.stringify([aggOpen.cli_lanes?.status, aggOpen.cli_lanes?.parser]) + ']',
        aggOpen.cli_lanes?.status === 'measured' && same(aggOpen.cli_lanes.parser, RECORD) && aggOpen.cli_lanes.lanes.qmd?.calls === 2)
      expect('parser: an aggregate that mixes measured and unavailable transcripts is incomplete [' + JSON.stringify(kernel.aggregateMeasurements([open, closed]).cli_lanes?.status) + ']', kernel.aggregateMeasurements([open, closed]).cli_lanes?.status === 'incomplete')
      // Directory order: an explicit argument, then the environment (CHILD_USAGE_SHELL_PARSER), then the ecosystem default under HOME.
      const emptyHome = join(tmp, 'home'); mkdirSync(emptyHome)
      const goodDir = join(tmp, 'good')
      const probe = (env, ...argument) => {
        const script = 'import * as k from ' + JSON.stringify(new URL('./child-usage.mjs', import.meta.url).href) + '; process.stdout.write(JSON.stringify(await k.loadShellParser(...' + JSON.stringify(argument) + ')))'
        const r = spawnSync(process.execPath, ['--input-type=module', '-e', script], { encoding: 'utf8', env: { PATH: process.env.PATH, ...env } })
        try { return JSON.parse(r.stdout) } catch { return { ok: false, reason: '(no output: ' + r.stderr.slice(0, 120) + ')' } }
      }
      const order = [probe({ HOME: emptyHome }), probe({ HOME: emptyHome, CHILD_USAGE_SHELL_PARSER: goodDir }), probe({ HOME: emptyHome, CHILD_USAGE_SHELL_PARSER: join(tmp, 'absent') }),
        probe({ HOME: emptyHome, CHILD_USAGE_SHELL_PARSER: join(tmp, 'absent') }, goodDir), probe({ HOME: emptyHome, CHILD_USAGE_SHELL_PARSER: '' })]
      expect('parser: directory order is the argument, then CHILD_USAGE_SHELL_PARSER, then the default under HOME [' + order.map((r) => r.ok ? 'ok' : r.reason).join(',') + ']',
        order.map((r) => r.ok ? 'ok' : r.reason).join() === 'not_installed,ok,not_installed,ok,not_installed')
      // The CLI flag, in a sweep over one child transcript with one shell call.
      const root = join(tmp, 'sweep'), file = join(root, 'proj', 'sess', 'subagents', 'agent-a1.jsonl')
      mkdirSync(join(file, '..'), { recursive: true })
      writeFileSync(file, rows.map((r) => JSON.stringify({ ...r, timestamp: r.timestamp })).join('\n') + '\n')
      utimesSync(file, new Date('2026-09-27T00:00:00Z'), new Date('2026-09-27T00:00:00Z'))
      const sweep = (...flags) => {
        const r = spawnSync(process.execPath, [fileURLToPath(new URL('./child-usage.mjs', import.meta.url)), '--lanes-sweep', '--root', root, '--since', '2026-09-25T17:18:00Z', '--until', '2026-09-26T15:05:00Z', ...flags],
          { encoding: 'utf8', env: { PATH: process.env.PATH, HOME: emptyHome } })
        try { return { status: r.status, cli: JSON.parse(r.stdout).groups.all.measurement.cli_lanes } } catch { return { status: r.status, cli: '(no report: ' + r.stderr.slice(0, 120) + ')' } }
      }
      const withFlag = sweep('--shell-parser', goodDir), without = sweep()
      expect('parser: --shell-parser names the install; without it the default under HOME (empty here) is not_installed [' + JSON.stringify([withFlag.cli?.status, without.cli]) + ']',
        withFlag.status === 0 && withFlag.cli?.status === 'measured' && same(withFlag.cli.parser, RECORD) && without.status === 0 && same(without.cli, { status: 'parser_unavailable', reason: 'not_installed' }))
      expect('parser: --shell-parser needs a value and is given once [' + JSON.stringify([parseArgs(['--lanes-sweep', '--root', 'a', '--shell-parser', 'd']).shellParser, parseArgs(['--lanes-sweep', '--root', 'a', '--shell-parser']).error]) + ']',
        parseArgs(['--lanes-sweep', '--root', 'a', '--shell-parser', 'd']).shellParser === 'd' && Boolean(parseArgs(['--lanes-sweep', '--root', 'a', '--shell-parser']).error)
        && Boolean(parseArgs(['--lanes-sweep', '--root', 'a', '--shell-parser', 'd', '--shell-parser', 'e']).error))
    }
  } finally { rmSync(tmp, { recursive: true, force: true }); await load() }
}
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
