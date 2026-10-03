// Count-only check of the B9 reading on real transcripts: runs the kernel's transcriptUsage (no window) over every .jsonl file under the
// roots and prints aggregate counts only (no ids, paths or text). Usage: node real_usage_check.mjs <kernel.mjs> <root> [<root> ...]
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const [kernelPath, ...roots] = process.argv.slice(2)
const kernel = await import(pathToFileURL(resolve(kernelPath)).href)
const out = { files: 0, files_with_messages: 0, messages: 0, complete_files: 0, incomplete_files: 0, advisor_iterations: 0, advisor_models: {},
  unread_entries: {}, inconsistent_messages: 0, advisor_results_without_usage: 0, advisor_calls_without_result: 0,
  files_incomplete_by_iteration_issue: 0, messages_split_known: 0, messages_split_equals_combined: 0, messages_split_differs: 0,
  speed: {}, service_tier: {}, inference_geo: {}, advisor_split_equals_combined: 0, advisor_split_differs: 0 }
const bump = (o, k, n = 1) => { o[k] = (o[k] || 0) + n }
const walk = (dir) => {
  let entries
  try { entries = readdirSync(dir, { withFileTypes: true }) } catch { return }
  for (const e of entries) {
    const full = join(dir, e.name)
    if (e.isDirectory()) walk(full)
    else if (e.isFile() && e.name.endsWith('.jsonl')) {
      out.files++
      const rows = []
      for (const line of readFileSync(full, 'utf8').split('\n')) { if (!line.trim()) continue; try { rows.push(JSON.parse(line)) } catch { /* skip */ } }
      const u = kernel.transcriptUsage(rows)
      if (!u.messages.length) continue
      out.files_with_messages++
      out.messages += u.messages.length
      bump(out, u.complete ? 'complete_files' : 'incomplete_files')
      const issues = u.iteration_issues
      const anyIssue = Object.keys(issues.unread_entries).length || issues.inconsistent_messages || issues.advisor_results_without_usage || issues.advisor_calls_without_result
      if (anyIssue) out.files_incomplete_by_iteration_issue++
      for (const [t, n] of Object.entries(issues.unread_entries)) bump(out.unread_entries, t, n)
      for (const k of ['inconsistent_messages', 'advisor_results_without_usage', 'advisor_calls_without_result']) out[k] += issues[k]
      out.advisor_iterations += u.advisor_iterations.length
      for (const a of u.advisor_iterations) {
        bump(out.advisor_models, a.model)
        if (a.cache_creation_5m !== null && a.cache_creation_1h !== null) bump(out, a.cache_creation_5m + a.cache_creation_1h === a.usage.cache_creation_input_tokens ? 'advisor_split_equals_combined' : 'advisor_split_differs')
      }
      for (const m of u.messages) {
        for (const k of ['speed', 'service_tier', 'inference_geo']) bump(out[k], String(m[k]))
        if (m.cache_creation_5m === null || m.cache_creation_1h === null || m.usage.cache_creation_input_tokens === null) continue
        out.messages_split_known++
        bump(out, m.cache_creation_5m + m.cache_creation_1h === m.usage.cache_creation_input_tokens ? 'messages_split_equals_combined' : 'messages_split_differs')
      }
    }
  }
}
for (const r of roots) walk(resolve(r))
console.log(JSON.stringify(out, null, 1))
