// Count-only comparison of U1's not-executed rule (callState at ebcca292, copied verbatim below because that revision did not export it)
// with the U2 kernel's exported callState, over every Claude Code transcript under the root: calls the two readings mark differently, and
// the U2 cause of every call that did not run, by tool kind (Bash, an MCP tool, another built-in tool). Prints counts and fixed names only.
//   node not-executed-delta.mjs <U2 child-usage.mjs> <root>
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const kernel = await import(pathToFileURL(resolve(process.argv[2])).href)
const resultText = (content) => typeof content === 'string' ? content : Array.isArray(content) ? content.map((b) => (b && typeof b.text === 'string' ? b.text : '')).join('\n') : ''
// U1's rule, examples/claude-native/workflows/child-usage.mjs at ebcca292 (callState), not_executed only.
const NOT_EXECUTED_RESULT = ['PreToolUse:', 'Permission for', 'User rejected tool use']
const NOT_EXECUTED_CONTENT = ['<tool_use_error>', "The user doesn't want to proceed", 'The server-side auto mode classifier gave no verdict']
function u1NotExecuted(call, result) {
  if (!result) return call?.native_status === 'declined'
  const native = result.native_state ?? call?.native_state, said = result.row?.toolUseResult
  if (!result.is_error) return false
  const reason = typeof said === 'string' ? (said.startsWith('Error: ') ? said.slice(7) : said) : '', content = resultText(result.content)
  return Boolean(result.row?.toolDenialKind) || NOT_EXECUTED_CONTENT.some((m) => content.startsWith(m))
    || NOT_EXECUTED_RESULT.some((m) => reason.startsWith(m)) || native === 'declined'
}
const kind = (name) => name === 'Bash' ? 'Bash' : String(name || '').startsWith('mcp__') ? 'mcp' : 'other_builtin'
const out = { transcript_files: 0, calls: 0, calls_with_result: 0, u1_not_executed: 0, u2_not_executed: 0, only_u2: {}, only_u1: {}, causes: {} }
const bump = (o, k) => { o[k] = (o[k] || 0) + 1 }
const walk = (dir) => {
  let entries
  try { entries = readdirSync(dir, { withFileTypes: true }) } catch { return }
  for (const e of entries) {
    const full = join(dir, e.name)
    if (e.isDirectory()) walk(full)
    else if (e.isFile() && e.name.endsWith('.jsonl')) file(full)
  }
}
function file(path) {
  out.transcript_files++
  const calls = new Map(), results = new Map()
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    if (!line.includes('"tool_use"') && !line.includes('"tool_result"')) continue
    let row
    try { row = JSON.parse(line) } catch { continue }
    const blocks = Array.isArray(row?.message?.content) ? row.message.content : []
    for (const b of blocks) {
      if (!b || typeof b !== 'object') continue
      if (row.type === 'assistant' && b.type === 'tool_use' && !calls.has(b.id)) calls.set(b.id, b)
      if (row.type === 'user' && b.type === 'tool_result' && !results.has(b.tool_use_id)) results.set(b.tool_use_id, { ...b, row })
    }
  }
  for (const [id, c] of calls) {
    const r = results.get(id) || null
    out.calls++
    if (r) out.calls_with_result++
    const a = u1NotExecuted(c, r), s = kernel.callState(c, r), b = s.not_executed === true
    if (a) out.u1_not_executed++
    if (b) { out.u2_not_executed++; bump(out.causes, kind(c.name) + ' ' + s.cause) }
    if (b && !a) bump(out.only_u2, kind(c.name) + ' ' + s.cause)
    if (a && !b) bump(out.only_u1, kind(c.name))
  }
}
walk(resolve(process.argv[3]))
for (const k of ['only_u2', 'only_u1', 'causes']) out[k] = Object.fromEntries(Object.entries(out[k]).sort())
process.stdout.write(JSON.stringify(out, null, 1) + '\n')
