// Count-only run of the U2 kernel's M14 call states and M15 classes over every Claude Code transcript under the root (each .jsonl file one
// actor, no window, no shell parser: neither measure reads it). Prints totals, invariant checks and per-server M15 rows: counts, class names
// and the MCP server names of the stack's vocabulary (manifests/stack.json servers, with context-mode's plugin names); every other server
// is folded into (other), as U1's closed vocabulary does. No id, path or text.
//   node kernel-m14-m15.mjs <child-usage.mjs> <root>
const PUBLIC_SERVERS = new Set(['ai-memory', 'codebase-memory', 'context-mode', 'headroom', 'jcodemunch', 'plugin_context-mode',
  'plugin_context-mode_context-mode', 'qmd', 'serena', 'socraticode'])
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const kernel = await import(pathToFileURL(resolve(process.argv[2])).href)
const out = { transcript_files: 0, parse_errors: 0, actors_with_calls: 0, invariant_violations: { actor: 0, server: 0, executed: 0, rejected_sources: 0 },
  claude_calls_without_result_equal_cancelled_or_unfinished: { equal: 0, differ: 0 } }
const measurements = []
const walk = (dir) => {
  let entries
  try { entries = readdirSync(dir, { withFileTypes: true }) } catch { return }
  for (const e of entries) {
    const full = join(dir, e.name)
    if (e.isDirectory()) walk(full)
    else if (e.isFile() && e.name.endsWith('.jsonl')) file(full)
  }
}
const check = (row) => row.attempted === row.executed + row.rejected + row.invalid + row.cancelled_with_result + row.cancelled_or_unfinished + row.unknown
function file(path) {
  out.transcript_files++
  const rows = []
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    if (!line.trim()) continue
    try { rows.push(JSON.parse(line)) } catch { out.parse_errors++ }
  }
  const m = kernel.measureTranscript(rows)
  const s = m.call_states
  if (!s.attempted) return
  out.actors_with_calls++
  if (!check(s)) out.invariant_violations.actor++
  for (const row of Object.values(s.by_server)) if (!check(row)) out.invariant_violations.server++
  if (s.executed !== s.succeeded + s.failed + s.interrupted) out.invariant_violations.executed++
  if (Object.values(s.rejected_by_source).reduce((a, b) => a + b, 0) !== s.rejected) out.invariant_violations.rejected_sources++
  // A Claude transcript has no native statuses and no sandbox calls, so its calls without a result are exactly the cancelled_or_unfinished.
  out.claude_calls_without_result_equal_cancelled_or_unfinished[m.calls_without_result === s.cancelled_or_unfinished ? 'equal' : 'differ']++
  delete m.usage // only call_states and m15 are read; the per-message usage records would hold memory for nothing
  // Fold the servers outside the vocabulary: their attempts, successes and classes add up under (other) before aggregation.
  const folded = {}
  for (const [server, row] of Object.entries(m.m15.by_server)) {
    const key = PUBLIC_SERVERS.has(server) ? server : '(other)'
    const t = folded[key] ||= { attempted: 0, succeeded: 0, ctx: false, classes: {} }
    t.attempted += row.attempted
    t.succeeded += row.succeeded
    t.ctx ||= row.ctx
    for (const [k, n] of Object.entries(row.classes)) t.classes[k] = (t.classes[k] || 0) + n
  }
  m.m15.by_server = folded
  measurements.push(m)
}
walk(resolve(process.argv[3]))
const agg = kernel.aggregateMeasurements(measurements)
out.call_states = { ...agg.call_states, by_server: undefined }
out.m15_threshold = agg.m15.threshold
out.m15_by_server = Object.fromEntries(Object.entries(agg.m15.by_server).sort(([a], [b]) => a < b ? -1 : 1)
  .map(([server, row]) => [server, { ...row, classes: Object.fromEntries(Object.entries(row.classes).sort()) }]))
process.stdout.write(JSON.stringify(out, null, 1) + '\n')
