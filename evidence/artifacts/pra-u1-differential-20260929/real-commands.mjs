// Extract every distinct shell text from the local Claude Code transcripts into ONE private file (a JSON array of strings, mode 0600) and print
// counts only. The file holds the commands themselves: keep it out of every checkout and never quote it.
//
//   node real-commands.mjs <out.json> [<transcript root> ...] [--until <ISO 8601 instant>]     (default root: ~/.claude/projects)
//
// A shell text is a Bash call's `command`, the `code` of a shell ctx_execute(_file) call, and each `command` of ctx_batch_execute.
// With --until only the rows stamped at or before the instant count, so a later run rebuilds the corpus of an earlier one: the transcript
// store only grows, and a row is never restamped. A transcript that was deleted since cannot be rebuilt.
// The cutoff of the corpus of counts.json was not recorded when that corpus was extracted (the extraction had no such option). It is
// RECONSTRUCTED: `--until 2026-09-29T07:08:07Z` gives 136,361 distinct shell texts, 15,128 of them with a heredoc operator, and the
// shape counts of shape-counts.mjs on it equal all 18 recorded ones. Every instant from 07:08:06.392Z to just before 07:08:08.754Z gives
// the same texts (no first sighting lies between); an earlier instant gives fewer texts and a later one more.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

const [out, ...rest] = process.argv.slice(2)
let until = null
const untilAt = rest.indexOf('--until')
if (untilAt >= 0) {
  until = rest[untilAt + 1] ?? ''
  rest.splice(untilAt, 2)
  if (!Number.isFinite(Date.parse(until))) { console.error('--until needs an ISO 8601 instant such as 2026-09-29T07:08:07Z'); process.exit(2) }
}
const cutoff = until === null ? null : Date.parse(until)
const roots = rest.length ? rest : [join(homedir(), '.claude/projects')]
const files = []
const walk = (dir) => {
  let entries
  try { entries = readdirSync(dir, { withFileTypes: true }) } catch { return }
  for (const entry of entries) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) walk(path)
    else if (entry.name.endsWith('.jsonl')) files.push(path)
  }
}
for (const root of roots) walk(root)
const seen = new Set(), texts = []
let lines = 0, toolUses = 0, unparsable = 0
for (const file of files) {
  let text
  try { text = readFileSync(file, 'utf8') } catch { continue }
  for (const line of text.split('\n')) {
    if (!line.includes('"tool_use"')) continue
    lines++
    let row
    try { row = JSON.parse(line) } catch { unparsable++; continue }
    if (cutoff !== null && !(Date.parse(row?.timestamp) <= cutoff)) continue // a row with no readable stamp cannot be shown to be earlier
    const content = row?.message?.content
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (block?.type !== 'tool_use') continue
      toolUses++
      const name = String(block.name || ''), input = block.input || {}
      const found = []
      if (name === 'Bash' && typeof input.command === 'string') found.push(input.command)
      else if (/__ctx_execute(_file)?$/.test(name) && input.language === 'shell' && typeof input.code === 'string') found.push(input.code)
      else if (name.endsWith('__ctx_batch_execute') && Array.isArray(input.commands)) for (const c of input.commands) if (typeof c?.command === 'string') found.push(c.command)
      for (const text of found) if (!seen.has(text)) { seen.add(text); texts.push(text) }
    }
  }
}
writeFileSync(out, JSON.stringify(texts), { mode: 0o600 })
const size = texts.map((t) => t.length).sort((a, b) => a - b)
console.log(JSON.stringify({ until, files: files.length, tool_use_lines: lines, tool_uses: toolUses, unparsable_lines: unparsable, distinct_shell_texts: texts.length,
  with_heredoc_operator: texts.filter((t) => t.includes('<<')).length, characters: size.reduce((x, y) => x + y, 0), median: size[size.length >> 1], p99: size[Math.floor(size.length * 0.99)], largest: size[size.length - 1] }))
