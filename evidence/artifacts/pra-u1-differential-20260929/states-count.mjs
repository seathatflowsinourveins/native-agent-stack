// Count-only scan of the transcripts of Claude Code under ~/.claude/projects for the shapes that decide a call's state (not executed, interrupted):
// a row-level toolDenialKind, a result whose content opens with a known refusal text, and toolUseResult.interrupted. Prints numbers and fixed
// vocabulary only, never row text.
//   node states-count.mjs
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'
const files = []
const walk = (d) => { let es; try { es = readdirSync(d, { withFileTypes: true }) } catch { return } for (const e of es) { const f = join(d, e.name); if (e.isDirectory()) walk(f); else if (e.name.endsWith('.jsonl')) files.push(f) } }
walk(join(homedir(), '.claude/projects'))
const MARK = /toolDenialKind|"interrupted":true|This agent is isolated|doesn't want to proceed|classifier gave no verdict/
const textOf = (c) => typeof c === 'string' ? c : Array.isArray(c) ? c.map((b) => typeof b === 'string' ? b : b?.text ?? '').join('\n') : ''
const KNOWN_KINDS = new Set(['permission-rule', 'user-rejected', 'cancelled', 'automode-unavailable'])
const out = { files: files.length, files_scanned_deeply: 0, denial_kind: {}, isolated: { rows: 0, with_denial_kind: 0, is_error_true: 0, tools: {} }, wont_proceed: { rows: 0, with_denial_kind: 0, toolUseResult: {} }, classifier: { rows: 0, with_denial_kind: 0 }, bash_interrupted_true: 0, marked_bash_rows: 0 }
const bump = (m, k) => { m[k] = (m[k] || 0) + 1 }
for (const f of files) {
  let text; try { text = readFileSync(f, 'utf8') } catch { continue }
  const deep = MARK.test(text)
  if (!deep) continue
  if (deep) out.files_scanned_deeply++
  const names = new Map(), rows = []
  for (const line of text.split('\n')) {
    if (!line.includes('"tool_use"') && !line.includes('"tool_result"')) continue
    const marked = MARK.test(line)
    if (!marked && !line.includes('"type":"tool_use"')) continue
    let row; try { row = JSON.parse(line) } catch { continue }
    const c = row?.message?.content
    if (row.type === 'assistant' && Array.isArray(c)) { for (const b of c) { if (b?.type === 'tool_use') names.set(b.id, b.name) } }
    else if (marked && row.type === 'user' && Array.isArray(c)) rows.push(row)
  }
  for (const row of rows) for (const b of row.message.content) {
    if (b?.type !== 'tool_result') continue
    const name = names.get(b.tool_use_id), content = textOf(b.content).trimStart(), said = row.toolUseResult
    const kind = 'toolDenialKind' in row ? row.toolDenialKind : undefined
    if (name === 'Bash') { out.marked_bash_rows++; if (said && typeof said === 'object' && said.interrupted === true) out.bash_interrupted_true++ }
    if (kind !== undefined) bump(out.denial_kind, KNOWN_KINDS.has(kind) ? kind : '(other)')
    if (content.startsWith('This agent is isolated')) { out.isolated.rows++; if (kind !== undefined) out.isolated.with_denial_kind++; if (b.is_error === true) out.isolated.is_error_true++; bump(out.isolated.tools, name === 'Bash' ? 'Bash' : '(other tool)') }
    if (content.startsWith("The user doesn't want to proceed")) { out.wont_proceed.rows++; if (kind !== undefined) out.wont_proceed.with_denial_kind++; bump(out.wont_proceed.toolUseResult, typeof said === 'string' ? (said === 'User rejected tool use' ? 'User rejected tool use' : '(other string)') : said === undefined ? '(absent)' : '(object)') }
    if (content.startsWith('The server-side auto mode classifier gave no verdict')) { out.classifier.rows++; if (kind !== undefined) out.classifier.with_denial_kind++ }
  }
}
console.log(JSON.stringify(out))
