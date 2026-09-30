// Count-only: for each message whose 5m+1h split differs from its combined counter, is its file's usage marked inconsistent?
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
const [kernelPath, ...roots] = process.argv.slice(2)
const kernel = await import(pathToFileURL(resolve(kernelPath)).href)
const out = { differs: 0, differs_in_file_with_inconsistent: 0, differs_top_combined_zero: 0 }
const walk = (dir) => { for (const e of readdirSync(dir, { withFileTypes: true })) { const full = join(dir, e.name)
  if (e.isDirectory()) walk(full)
  else if (e.name.endsWith('.jsonl')) {
    const rows = readFileSync(full, 'utf8').split('\n').filter((l) => l.trim()).map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean)
    const u = kernel.transcriptUsage(rows)
    for (const m of u.messages) if (m.cache_creation_5m !== null && m.cache_creation_1h !== null && m.usage.cache_creation_input_tokens !== null && m.cache_creation_5m + m.cache_creation_1h !== m.usage.cache_creation_input_tokens) {
      out.differs++; if (u.iteration_issues.inconsistent_messages) out.differs_in_file_with_inconsistent++; if (m.usage.cache_creation_input_tokens === 0) out.differs_top_combined_zero++ } } } }
for (const r of roots) walk(resolve(r))
console.log(JSON.stringify(out))
