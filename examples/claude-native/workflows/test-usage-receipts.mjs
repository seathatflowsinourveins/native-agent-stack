#!/usr/bin/env node
// RECEIPTS from real provider runs (sanitized child-usage.mjs output and stored
// verifier, builder, recheck, hook and lane-check results): every figure the routing
// documentation quotes must be re-derivable from them. Paths come from the sibling
// contract.config.json (usage_receipts_dir, routing_doc, task_record); a missing
// configured path is a failure, never a skip.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const HERE = dirname(fileURLToPath(import.meta.url))
const CONFIG = JSON.parse(readFileSync(join(HERE, 'contract.config.json'), 'utf8'))
const configured = (key) => resolve(HERE, typeof CONFIG[key] === 'string' ? CONFIG[key] : '\0missing-' + key)
const kindOf = (p) => { try { return statSync(p).isDirectory() ? 'directory' : 'file' } catch { return 'missing' } }
let passed = 0, failed = 0
const expect = (n, c) => { console.log((c ? 'PASS ' : 'FAIL ') + n); if (c) passed++; else failed++ }
for (const key of ['usage_receipts_dir', 'routing_doc', 'task_record']) expect('config: ' + key + ' resolves to an existing ' + (key.endsWith('_dir') ? 'directory' : 'file'), kindOf(configured(key)) === (key.endsWith('_dir') ? 'directory' : 'file'))
// The receipt assertions read those paths directly; stop here, with the SUMMARY line, when any is wrong.
if (failed) { console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed)); process.exit(1) }
{
  const dir = configured('usage_receipts_dir')
  const runs = readdirSync(dir).filter((n) => /^child-usage-wf_.*\.json$/.test(n)).map((n) => JSON.parse(readFileSync(dir + '/' + n, 'utf8')))
  const doc = readFileSync(configured('routing_doc'), 'utf8')
  const first = (run, label, agentId) => runs.find((r) => r.run_id === run).children.find((c) => c.label === label && (!agentId || c.agent_id === agentId)).first_request_prompt_tokens
  // [start of the doc table row, receipt value]: each figure must sit in its own row.
  const quoted = [
    ['| default workflow subagent (no `agentType`) |', first('wf_c9b03b9e-30e', 'probe:default')],
    ['| `evidence-reviewer` with bare `mcp__server` grants (previous) |', first('wf_c9b03b9e-30e', 'probe:evidence-reviewer', 'ab0ba6c6c2397b9d3')],
    ['| named MCP tools, no `ToolSearch` (probe) |', first('wf_1e1d818f-7fd', 'probe-reviewer-a')],
    ['| named MCP tools plus `ToolSearch` (probe of the shape the reviewer and builder adopted) |', first('wf_1e1d818f-7fd', 'probe-reviewer-b')],
    ['| `source-scout` (four built-ins, `omitClaudeMd`) |', first('wf_c9b03b9e-30e', 'probe:source-scout')],
  ]
  const rowOf = (marker) => doc.split('\n').filter((l) => l.startsWith(marker))
  expect('receipts: no host path or transcript directory is stored', runs.every((r) => !JSON.stringify(r).includes('/home/') && !('transcript_dir' in r)))
  expect('receipts: the five first-prompt figures are 42396, 42220, 21565, 12164, 8048', JSON.stringify(quoted.map((q) => q[1])) === JSON.stringify([42396, 42220, 21565, 12164, 8048]))
  expect('receipts: each first-prompt table row exists once and carries its own receipt figure', quoted.every((q) => rowOf(q[0]).length === 1 && rowOf(q[0])[0].startsWith(q[0] + ' ' + q[1].toLocaleString('en-US') + ' |')))
  const trial = runs.find((r) => r.run_id === 'wf_d0d741b1-9c6').children
  const by = (label) => trial.find((c) => c.label === label)
  expect('receipts: Haiku trial counters match the doc (22 vs 17 requests, Haiku effort not applied)', by('inventory:haiku').requests === 22 && by('inventory:sonnet').requests === 17 && by('inventory:haiku').efforts.length === 0 && doc.includes('22 vs 17'))
  // Every native run the task record lists as provider evidence has a usage receipt here.
  const record = readFileSync(configured('task_record'), 'utf8')
  const listed = [...new Set((record.split('## Evidence classes')[1] || '').split('\n## ')[0].match(/wf_[0-9a-f]{8}-[0-9a-f]{3}/g) || [])]
  expect('receipts: every run the task record lists as provider evidence has a usage receipt', listed.length >= 9 && listed.every((id) => runs.some((r) => r.run_id === id)))
  expect('receipts: real-run first prompts of the adopted reviewer and builder match the doc (17,535 and 17,864)', first('wf_75df8af9-d78', 'review') === 17535 && first('wf_0de00432-c16', 'build:prometheus-token-probe') === 17864 && doc.includes('17,535') && doc.includes('17,864'))
  const lane = JSON.parse(readFileSync(dir + '/deferred-lane-check-wf_bf62b2b7-d6e.json', 'utf8')).returned
  expect('receipts: the deferred reviewer shape loaded its granted lanes and no write tool', lane.find_symbol_loaded === 'yes' && lane.codebase_search_loaded === 'yes' && lane.replace_content_loaded === 'no' && lane.ctx_purge_loaded === 'no')
  const hooks = JSON.parse(readFileSync(dir + '/hooks-observed-wf_d0d741b1-9c6.json', 'utf8')).hook_success_counts_by_child
  expect('receipts: the RTK Bash hook fired inside workflow children and no Context Mode hook did', Object.values(hooks).some((c) => (c['PreToolUse:Bash :: rtk hook claude'] || 0) > 0) && !Object.values(hooks).some((c) => Object.keys(c).some((k) => /context-mode/i.test(k.split(' :: ')[1] || ''))))
  const respawn = runs.find((r) => r.run_id === 'wf_c9b03b9e-30e').children.find((c) => c.agent_id === 'abf328fa25888d471')
  expect('receipts: the repeat-spawn cache figures match the doc (34,591 read of 42,091)', respawn.first_request_cache_read === 34591 && respawn.first_request_prompt_tokens === 42091 && doc.includes('34,591 of 42,091'))
  const build = runs.find((r) => r.run_id === 'wf_0de00432-c16').children[0]
  expect('receipts: the edited isolated-builder completed a real task as itself on Sonnet/medium', build.complete && build.agent_type === 'isolated-builder' && build.resolved_models[0] === 'claude-sonnet-5' && build.efforts[0] === 'medium')
  const three = runs.find((r) => r.run_id === 'wf_b9c9290d-081').children
  const pair = JSON.parse(readFileSync(dir + '/recheck-run-wf_b9c9290d-081.json', 'utf8'))
  expect('receipts: the three-stage review ran natively with an independent recheck on source-scout, and both runs agree on every exit code', three.length === 3 && three.every((c) => c.complete) && three.find((c) => c.label === 'recheck').agent_type === 'source-scout' && three.find((c) => c.label === 'review').agent_type === 'evidence-reviewer' && pair.recheck_checks_run.length === 7 && pair.recheck_checks_run.every((r) => r.exit === '0' && pair.inventory_checks_run.find((i) => i.command === r.command).exit === '0'))
  const builderRun = JSON.parse(readFileSync(dir + '/builder-run-wf_0de00432-c16.json', 'utf8'))
  expect('receipts: the builder transcript shows only its own worktree as cwd and the handoff names its commit', builderRun.observed_in_transcript.assistant_cwds.length === 1 && builderRun.observed_in_transcript.assistant_cwds[0].endsWith('.claude/worktrees/wf_0de00432-c16-1') && builderRun.returned_handoff.commit === 'e7e0b58' && builderRun.observed_in_transcript.tool_use_counts.mcp__serena__find_symbol === 2 && record.includes('e7e0b58'))
  const verdict = JSON.parse(readFileSync(dir + '/audit-verifier-wf_d0d741b1-9c6.json', 'utf8')).haiku_trial
  expect('receipts: the Haiku routing decision quotes the stored Opus verifier scoring (14/14, 9/14, not adequate)', verdict.lane_rows_correct_sonnet === '14/14' && verdict.lane_rows_correct_haiku === '9/14' && verdict.haiku_adequate_for_exact_extraction === 'no' && doc.includes('14/14') && doc.includes('9/14'))
  const probes = ['probe-reviewer-a', 'probe-reviewer-b'].map((n) => readFileSync(dir + '/' + n + '.agent.md', 'utf8'))
  expect('receipts: the two probe agent definitions are retained and differ only by ToolSearch', probes[0].replace('probe-reviewer-a', 'probe-reviewer-b').replace('without ToolSearch', 'with ToolSearch').replace('tools: Read, Glob, Grep,', 'tools: Read, Glob, Grep, ToolSearch,') === probes[1])
  expect('receipts: lean stages ran as the named project agents on the requested models', runs.find((r) => r.run_id === 'wf_75df8af9-d78').children.every((c) => c.complete && ((c.label === 'inventory' && c.agent_type === 'source-scout' && c.resolved_models[0] === 'claude-sonnet-5') || (c.label === 'review' && c.agent_type === 'evidence-reviewer' && c.resolved_models[0] === 'claude-opus-5'))))
}
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
