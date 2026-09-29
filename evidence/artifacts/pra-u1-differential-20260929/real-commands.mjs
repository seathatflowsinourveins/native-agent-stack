// Extract every distinct shell text from the local Claude Code transcripts into ONE private file (a JSON array of strings, mode 0600) and print
// counts only. The file holds the commands themselves: keep it out of every checkout and never quote it.
//
//   node real-commands.mjs <out.json> [<transcript root> ...]     (default root: ~/.claude/projects)
//
// A shell text is a Bash call's `command`, the `code` of a shell ctx_execute(_file) call, and each `command` of ctx_batch_execute.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

const [out, ...rest] = process.argv.slice(2)
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
console.log(JSON.stringify({ files: files.length, tool_use_lines: lines, tool_uses: toolUses, unparsable_lines: unparsable, distinct_shell_texts: texts.length,
  with_heredoc_operator: texts.filter((t) => t.includes('<<')).length, characters: size.reduce((x, y) => x + y, 0), median: size[size.length >> 1], p99: size[Math.floor(size.length * 0.99)], largest: size[size.length - 1] }))
