#!/usr/bin/env node
// Per-child requested/resolved model, effort and provider usage for one native
// Workflow run. Reads the run's transcript directory (journal.jsonl,
// agent-<id>.meta.json, agent-<id>.jsonl) and changes nothing.
//   node .claude/workflows/child-usage.mjs <transcriptDir>   (the "Transcript dir" the Workflow tool prints)
//   node .claude/workflows/child-usage.mjs --latest          (newest run recorded for this working directory)
// Streamed assistant lines repeat a message id, so usage is counted once per id
// (largest output_tokens wins). Counters are provider-returned and kept per type;
// they are not comparable to RTK/Context Mode/jCodeMunch/Headroom estimates.
// Exit 1 when any child is incomplete (null result, no transcript, no usage, or a
// resolved model outside the requested family).
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const COUNTERS = ['input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']
const lines = (file) => readFileSync(file, 'utf8').split('\n').filter((l) => l.trim()).map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean)

export function summarizeChild(started, result, meta, transcript) {
  const byId = new Map()
  const counted = (u) => u && typeof u === 'object' && COUNTERS.some((k) => typeof u[k] === 'number')
  const withoutUsage = new Set()
  for (const row of transcript) {
    if (!row || row.type !== 'assistant' || !row.message) continue
    // An assistant message with no numeric counter would silently undercount the child.
    if (!counted(row.message.usage)) { withoutUsage.add(row.message.id || row.uuid); continue }
    const id = row.message.id || row.uuid
    const prev = byId.get(id)
    if (!prev || (row.message.usage.output_tokens || 0) >= (prev.message.usage.output_tokens || 0)) byId.set(id, row)
  }
  const messages = [...byId.values()]
  const sum = (rows) => Object.fromEntries(COUNTERS.map((k) => [k, rows.reduce((n, r) => n + (r.message.usage[k] || 0), 0)]))
  const usage = sum(messages)
  const usageByModel = {}
  for (const m of new Set(messages.map((r) => r.message.model || '(unresolved)'))) usageByModel[m] = sum(messages.filter((r) => (r.message.model || '(unresolved)') === m))
  const resolved = [...new Set(messages.map((r) => r.message.model).filter(Boolean))]
  const efforts = [...new Set(messages.map((r) => r.effort).filter(Boolean))]
  const requested = meta && typeof meta.model === 'string' && meta.model ? meta.model : null
  const issues = []
  if (!result) issues.push('no result entry in journal')
  else if (result.result === null || result.result === undefined) issues.push('null result')
  if (!meta) issues.push('missing meta.json')
  if (!messages.length) issues.push('no assistant usage in transcript')
  const neverCounted = [...withoutUsage].filter((id) => !byId.has(id)).length
  if (neverCounted) issues.push(neverCounted + ' assistant message(s) without provider usage')
  const unresolved = messages.filter((r) => !r.message.model).length
  if (unresolved) issues.push(unresolved + ' assistant message(s) without a resolved model')
  if (!requested) issues.push('model not requested explicitly (inherits the coordinator model)')
  else if (!resolved.length || resolved.some((m) => !m.toLowerCase().includes(requested.toLowerCase()))) issues.push('resolved model outside requested family: ' + (resolved.join(',') || '(none resolved)'))
  return {
    agent_id: started.agentId, label: started.label ?? null, phase: started.phase ?? null,
    agent_type: meta ? meta.agentType ?? null : null,
    requested_model: requested, resolved_models: resolved, efforts,
    requests: messages.length, usage, usage_by_model: usageByModel,
    // Provider-returned cache read on the first request: evidence that the shared
    // prefix was served from cache for this child. Zero is not proof of a miss policy.
    first_request_cache_read: messages.length ? messages[0].message.usage.cache_read_input_tokens || 0 : null,
    // Whole first prompt (system, tool definitions, injected instructions, packet):
    // the fixed cost of spawning this child before it does any work.
    first_request_prompt_tokens: messages.length ? ['input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'].reduce((n, k) => n + (messages[0].message.usage[k] || 0), 0) : null,
    complete: issues.length === 0, issues,
  }
}

export function summarizeRun(dir) {
  const journalPath = join(dir, 'journal.jsonl')
  if (!existsSync(journalPath)) return { status: 'incomplete', reason: 'journal.jsonl not found in ' + dir, children: [] }
  const journal = lines(journalPath)
  const results = new Map(journal.filter((e) => e.type === 'result').map((e) => [e.agentId, e]))
  const children = journal.filter((e) => e.type === 'started' && e.agentId).map((s) => {
    const metaPath = join(dir, 'agent-' + s.agentId + '.meta.json')
    const logPath = join(dir, 'agent-' + s.agentId + '.jsonl')
    let meta = null
    try { meta = existsSync(metaPath) ? JSON.parse(readFileSync(metaPath, 'utf8')) : null } catch { meta = null }
    return summarizeChild(s, results.get(s.agentId) || null, meta, existsSync(logPath) ? lines(logPath) : [])
  })
  const byModel = {}
  for (const c of children) for (const [m, u] of Object.entries(c.usage_by_model)) {
    byModel[m] = byModel[m] || { children: 0, ...Object.fromEntries(COUNTERS.map((k) => [k, 0])) }
    byModel[m].children++
    for (const k of COUNTERS) byModel[m][k] += u[k]
  }
  const incomplete = children.filter((c) => !c.complete)
  return {
    status: !children.length ? 'incomplete' : incomplete.length ? 'incomplete' : 'complete',
    reason: !children.length ? 'journal has no started children' : incomplete.length ? incomplete.length + ' child(ren) incomplete' : 'every child has an explicit requested model, a matching resolved model, returned usage and a non-null result',
    multi_model_children: children.filter((c) => c.resolved_models.length > 1).map((c) => c.label || c.agent_id),
    children, by_resolved_model: byModel,
  }
}

// Newest native Workflow transcript directory for a working directory. The projects
// layout (<config>/projects/<cwd with non-alphanumerics as '-'>/<session>/subagents/workflows/wf_*)
// is observed native behavior, not a documented interface: return null rather than guess.
export function latestRunDir(cwd, configDir) {
  const root = join(configDir, 'projects', cwd.replace(/[^A-Za-z0-9]/g, '-'))
  if (!existsSync(root)) return null
  let best = null
  for (const session of readdirSync(root)) {
    const wf = join(root, session, 'subagents', 'workflows')
    if (!existsSync(wf)) continue
    for (const run of readdirSync(wf)) {
      const journal = join(wf, run, 'journal.jsonl')
      if (!run.startsWith('wf_') || !existsSync(journal)) continue
      const mtime = statSync(journal).mtimeMs
      if (!best || mtime > best.mtime) best = { dir: join(wf, run), mtime }
    }
  }
  return best ? best.dir : null
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const dir = process.argv[2] === '--latest' ? latestRunDir(process.cwd(), process.env.CLAUDE_CONFIG_DIR || join(homedir(), '.claude')) : process.argv[2]
  if (process.argv[2] === '--latest' && !dir) { console.error('no native Workflow run found for ' + process.cwd()); process.exit(2) }
  if (!dir) { console.error('usage: child-usage.mjs <workflow transcript dir>'); process.exit(2) }
  const out = { transcript_dir: dir, ...summarizeRun(dir) }
  console.log(JSON.stringify(out, null, 2))
  process.exit(out.status === 'complete' ? 0 : 1)
}
