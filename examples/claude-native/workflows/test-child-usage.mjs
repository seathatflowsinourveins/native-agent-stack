#!/usr/bin/env node
// OFFLINE check of child-usage.mjs against SYNTHETIC transcript rows (no provider
// call, not native evidence). Real runs are checked by passing their directory;
// stored receipts from real runs are bound to the documentation by test-usage-receipts.mjs.
import { summarizeChild, summarizeRun, latestRunDir } from './child-usage.mjs'
import { mkdtempSync, writeFileSync, rmSync, mkdirSync, utimesSync } from 'node:fs'
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

const dir = mkdtempSync(join(tmpdir(), 'child-usage-'))
try {
  expect('missing journal fails closed', summarizeRun(dir).status === 'incomplete')
  writeFileSync(join(dir, 'journal.jsonl'), [{ type: 'launched' }, started, { ...started, agentId: 'a2', label: 'review', phase: 'Review' }, done].map((e) => JSON.stringify(e)).join('\n') + '\nnot json\n')
  writeFileSync(join(dir, 'agent-a1.meta.json'), JSON.stringify({ model: 'sonnet', agentType: 'workflow' }))
  writeFileSync(join(dir, 'agent-a1.jsonl'), JSON.stringify(msg('m1', 'claude-sonnet-5', 9, 100)) + '\n')
  const run = summarizeRun(dir)
  expect('run keeps every started child and is incomplete when one has no result, meta or transcript', run.status === 'incomplete' && run.children.length === 2 && run.children[0].complete && !run.children[1].complete)
  expect('per-model totals come from returned usage only', run.by_resolved_model['claude-sonnet-5'].output_tokens === 9 && run.by_resolved_model['claude-sonnet-5'].children === 1)
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
