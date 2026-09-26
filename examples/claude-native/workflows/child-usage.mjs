#!/usr/bin/env node
// Per-child requested/resolved model, effort and provider usage for one native
// Workflow run. Reads the run's transcript directory (journal.jsonl,
// agent-<id>.meta.json, agent-<id>.jsonl) and changes nothing.
//   node .claude/workflows/child-usage.mjs <transcriptDir>   (the "Transcript dir" the Workflow tool prints)
//   node .claude/workflows/child-usage.mjs --latest          (newest run recorded for this working directory)
//   add --require-effort max to also fail (exit 1) when any child ran at another effort
//   (docs/tasks/2026-09-23-max-effort-default.md: a stage without effort inherits the
//   coordinator's xhigh, and CLAUDE_CODE_EFFORT_LEVEL overrides every stage).
// Streamed assistant lines repeat a message id, so usage is counted once per id
// (largest output_tokens wins). Counters are provider-returned and kept per type;
// they are not comparable to RTK/Context Mode/jCodeMunch/Headroom estimates.
// Exit 1 when any child is incomplete (null result, no transcript, no usage, a resolved
// model outside the requested family, a resolved model that changes within the child,
// or a model older than the requested alias's documented resolution for the client
// version that wrote the entry). The last two catch content-classifier fallback, which
// re-runs a flagged request on an older model and continues the child there; the
// family substring check alone accepts claude-opus-4-8 for a requested opus.
// An attempt that returned nothing and whose journal key the runtime started again (a re-run
// after a usage-limit pause) is listed under superseded_attempts with superseded_by, keeps its
// issues and effort check, and its usage counts in by_resolved_model, whose `children` counter
// counts attempts; `children` holds the final attempt of each call.
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const COUNTERS = ['input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']
const lines = (file) => readFileSync(file, 'utf8').split('\n').filter((l) => l.trim()).map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean)
// Client-written rows (an API error such as a usage-limit notice) carry this model; the
// family check still reports them, and the two fallback checks below ignore them.
const SYNTHETIC = '<synthetic>'
// Documented resolution of an alias on the Anthropic API by the client version that wrote the
// transcript entry, as [first client version, model] rows in ascending order (model-config doc,
// fetched 2026-09-24: opus is Opus 5.5 from v2.1.280, Opus 5 from v2.1.219, Opus 4.8 from v2.1.154).
// An entry older than the first row, and an alias without rows (sonnet, haiku, fable), has no
// expectation. An ANTHROPIC_DEFAULT_OPUS_MODEL pin to an older model would be flagged; none is set here.
export const ALIAS_RESOLUTION = { opus: [['2.1.154', 'claude-opus-4-8'], ['2.1.219', 'claude-opus-5'], ['2.1.280', 'claude-opus-5-5']] }
const semver = (v) => { const m = /^(\d+)\.(\d+)\.(\d+)/.exec(typeof v === 'string' ? v : ''); return m ? m.slice(1).map(Number) : null }
const compareParts = (a, b) => { for (let i = 0; i < Math.max(a.length, b.length); i++) { const d = (a[i] || 0) - (b[i] || 0); if (d) return d < 0 ? -1 : 1 } return 0 }
// claude-opus-5-5 -> { family: 'opus', version: [5, 5] }; a date suffix and a [1m] suffix are ignored; other shapes -> null.
export function modelGeneration(model) {
  const m = /^claude-([a-z]+)-(\d{1,2})(?:-(\d{1,2}))?(?:-\d{8})?(?:\[[^\]]*\])?$/.exec(String(model))
  return m ? { family: m[1], version: [Number(m[2]), ...(m[3] ? [Number(m[3])] : [])] } : null
}
export function expectedModel(alias, clientVersion) {
  const rows = ALIAS_RESOLUTION[String(alias).toLowerCase()], v = semver(clientVersion)
  if (!rows || !v) return null
  let hit = null
  for (const [from, model] of rows) if (compareParts(v, semver(from)) >= 0) hit = model
  return hit
}
// True when `model` cannot be shown to be at least as new as `expected` (a different family or an unparseable name fails closed).
export function olderThan(model, expected) {
  const got = modelGeneration(model), want = modelGeneration(expected)
  return !got || !want || got.family !== want.family || compareParts(got.version, want.version) < 0
}

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
  // Classifier fallback (model-config doc, "Automatic model fallback"): after a flagged request the
  // child continues on the fallback model, so a change of resolved model within the child, or a model
  // older than the alias's documented resolution for the entry's client version, is a substitution.
  const real = messages.filter((r) => r.message.model && r.message.model !== SYNTHETIC)
  const runs = real.map((r) => r.message.model).filter((m, i, all) => i === 0 || m !== all[i - 1])
  if (runs.length > 1) issues.push('resolved model changed within the child: ' + runs.join(' -> '))
  if (requested) {
    const older = new Set()
    for (const r of real) {
      const want = expectedModel(requested, r.version)
      if (want && r.message.model.toLowerCase().includes(requested.toLowerCase()) && olderThan(r.message.model, want)) older.add(r.message.model + ' on ' + r.version + ' (documented ' + requested + ': ' + want + ')')
    }
    if (older.size) issues.push('resolved model older than the documented alias resolution: ' + [...older].join(', '))
  }
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
  const started = journal.filter((e) => e.type === 'started' && e.agentId)
  // The runtime re-runs a call under the same journal key after a pause (observed on 2026-09-26: "Usage limit
  // reached ... Workflow paused; waiting agents re-run shortly after the reset", then "Re-running 8 waiting
  // agents"). An attempt with no result entry whose key started again later was superseded by that later attempt:
  // it is listed in superseded_attempts, not among the children, and its usage still counts in by_resolved_model.
  const supersededBy = new Map()
  started.forEach((s, i) => {
    if (results.has(s.agentId) || typeof s.key !== 'string' || !s.key) return
    const later = started.slice(i + 1).find((t) => t.key === s.key)
    if (later) supersededBy.set(s.agentId, later.agentId)
  })
  const attempts = started.map((s) => {
    const metaPath = join(dir, 'agent-' + s.agentId + '.meta.json')
    const logPath = join(dir, 'agent-' + s.agentId + '.jsonl')
    let meta = null
    try { meta = existsSync(metaPath) ? JSON.parse(readFileSync(metaPath, 'utf8')) : null } catch { meta = null }
    const child = summarizeChild(s, results.get(s.agentId) || null, meta, existsSync(logPath) ? lines(logPath) : [])
    return supersededBy.has(s.agentId) ? { ...child, superseded_by: supersededBy.get(s.agentId) } : child
  })
  const children = attempts.filter((c) => !c.superseded_by)
  const superseded = attempts.filter((c) => c.superseded_by)
  const byModel = {}
  for (const c of attempts) for (const [m, u] of Object.entries(c.usage_by_model)) {
    byModel[m] = byModel[m] || { children: 0, ...Object.fromEntries(COUNTERS.map((k) => [k, 0])) }
    byModel[m].children++
    for (const k of COUNTERS) byModel[m][k] += u[k]
  }
  const incomplete = children.filter((c) => !c.complete)
  const rerun = superseded.length ? '; ' + superseded.length + ' earlier attempt(s) that returned nothing were re-run under the same call key (superseded_attempts, whose usage by_resolved_model counts)' : ''
  return {
    status: !children.length ? 'incomplete' : incomplete.length ? 'incomplete' : 'complete',
    reason: (!children.length ? 'journal has no started children' : incomplete.length ? incomplete.length + ' child(ren) incomplete' : 'every child has an explicit requested model, one matching resolved model no older than its documented alias resolution, returned usage and a non-null result') + rerun,
    multi_model_children: children.filter((c) => c.resolved_models.length > 1).map((c) => c.label || c.agent_id),
    children, ...(superseded.length ? { superseded_attempts: superseded } : {}), by_resolved_model: byModel,
  }
}

// Children and superseded attempts whose resolved efforts are not exactly [required] (none recorded counts as a mismatch).
export function effortMismatches(run, required) {
  return [...run.children, ...(run.superseded_attempts || [])].filter((c) => c.efforts.length !== 1 || c.efforts[0] !== required).map((c) => ({ child: c.label || c.agent_id, efforts: c.efforts, ...(c.superseded_by ? { superseded_by: c.superseded_by } : {}) }))
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
  const argv = process.argv.slice(2)
  const ri = argv.indexOf('--require-effort')
  const required = ri >= 0 ? argv[ri + 1] : null
  if (ri >= 0 && !['low', 'medium', 'high', 'xhigh', 'max'].includes(required)) { console.error('--require-effort needs one of low, medium, high, xhigh, max'); process.exit(2) }
  if (argv.filter((a) => a === '--require-effort').length > 1) { console.error('--require-effort may be given once'); process.exit(2) }
  const target = argv.filter((_, i) => i !== ri && i !== ri + 1 || ri < 0)[0]
  const dir = target === '--latest' ? latestRunDir(process.cwd(), process.env.CLAUDE_CONFIG_DIR || join(homedir(), '.claude')) : target
  if (target === '--latest' && !dir) { console.error('no native Workflow run found for ' + process.cwd()); process.exit(2) }
  if (!dir) { console.error('usage: child-usage.mjs <workflow transcript dir> | --latest [--require-effort <level>]'); process.exit(2) }
  const out = { transcript_dir: dir, ...summarizeRun(dir) }
  if (required) out.effort_mismatches = effortMismatches(out, required)
  console.log(JSON.stringify(out, null, 2))
  // exitCode, not process.exit(): process.exit() drops stdout writes still pending, and a pipe takes 64 KiB at once.
  process.exitCode = out.status === 'complete' && !(required && out.effort_mismatches.length) ? 0 : 1
}
