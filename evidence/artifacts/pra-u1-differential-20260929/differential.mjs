// Command-position differential: what two kernels' commandInvocations read from the same inputs, compared by a projection.
//
//   node differential.mjs --old <kernel.mjs> --new <kernel.mjs> --inputs <inputs.json> [--valid <valid.json>] [--reduce | --reduce-text] [--out <file.jsonl>]
//                         [--profile <name> --seed <n>]   (needed for --reduce: the token sequences of make-inputs.mjs)
//
// --old is a kernel whose commandInvocations needs no parser (the scanner reading of commit 0c421c66); --new is the kernel under test, which
// needs the verified tree-sitter-bash install (loadShellParser). The projection compares what the lane accounting counts: the local lane
// invocations (a lane name, `!` when excluded as --version/--help, mcporter as mcporter:<op>[@server] with the server key mapped through
// the closed vocabulary of GPT-6 finding 10), the number of remote lane invocations, and the number of unresolved programs. A `program`
// name is not part of it: the old reading emitted any name-shaped basename, the new one only a fixed vocabulary (counted separately).
// Only bash-valid inputs (--valid: bash -n) are analysed; with no validity file every input is analysed and `bash_valid` is null (not checked). With --reduce each difference is cut to a minimal token witness (ddmin: still
// bash-valid, projections still different). Output is counts, or with --out one JSON line per difference (private: it holds command text).
import { readFileSync, writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { sequences } from './make-inputs.mjs'

const args = process.argv.slice(2)
const opt = (name) => { const i = args.indexOf('--' + name); return i < 0 ? null : args[i + 1] }
const oldK = await import(opt('old')), newK = await import(opt('new'))
// The old kernel may be one that reads with the parser too (an earlier commit of the AST reading): load it when it can.
if (typeof oldK.loadShellParser === 'function') await oldK.loadShellParser()
const parser = await newK.loadShellParser()
if (!parser.ok) throw new Error('the new kernel found no verified tree-sitter-bash install: ' + parser.reason)

const SERVERS = new Set(['codebase-memory', 'context-mode', 'jcodemunch', 'serena', 'socraticode', 'qmd', 'headroom', 'ai-memory'])
const key = (s) => s == null ? null : s.startsWith('(') ? s : SERVERS.has(s) ? s : '(other)'
// The token a stub logs when the lane runs (tests/test_command_position_oracle.py): the lane, `!` when excluded, mcporter by operation.
export const tokenOf = (i) => i.lane === 'mcporter' ? (i.excluded ? 'mcporter!' : 'mcporter:' + i.op + (i.op === 'call' ? '@' + key(i.server) : '')) : i.lane + (i.excluded ? '!' : '')
export const project = (records) => ({
  lanes: records.filter((i) => i.lane && !i.remote && !i.unresolved).map(tokenOf).sort(),
  remote: records.filter((i) => i.lane && i.remote).length,
  unresolved: records.filter((i) => i.unresolved && !i.remote).length,
})
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)
// Whether the new reading met a parse error anywhere (the text or a script it read again): cli_lanes.parse_errors of one Bash call.
const call = (command) => [{ type: 'assistant', timestamp: '2026-09-26T01:00:00Z', message: { content: [{ type: 'tool_use', id: 'c', name: 'Bash', input: { command } }] } }]
const parseError = (text) => (newK.measureTranscript(call(text)).cli_lanes?.parse_errors ?? 0) > 0
const programsOf = (kernel, text) => kernel.commandInvocations(text).map((i) => i.program).filter(Boolean)
const read = (kernel, text) => project(kernel.commandInvocations(text))
// The signature of a difference: which lane tokens only the old reading has, which only the new one has, and the sign of the change in the
// number of remote lanes and of unresolved programs. A reduction keeps the signature of the input's own difference, so a witness stands
// for the same observable difference (the same lanes, the same direction), not for a different mechanism that a smaller text happens to show.
const minus = (a, b) => { const left = [...b]; return a.filter((t) => { const i = left.indexOf(t); if (i < 0) return true; left.splice(i, 1); return false }) }
const signatureOf = (a, b) => JSON.stringify({ only_old: minus(a.lanes, b.lanes), only_new: minus(b.lanes, a.lanes), remote: Math.sign(b.remote - a.remote), unresolved: Math.sign(b.unresolved - a.unresolved) })
const hasSignature = (signature, text) => { try { return signatureOf(read(oldK, text), read(newK, text)) === signature } catch { return false } }
const bashValid = (text) => spawnSync('bash', ['-n', '-c', text], { stdio: 'ignore' }).status === 0

// The closed vocabulary of a `program` name in the new reading: a lane executable, a wrapper, a shell, eval, ssh and rtk.
const PROGRAMS = new Set(['toon', 'repomix', 'markitdown', 'qmd', 'headroom', 'jcodemunch-mcp', 'codebase-memory-mcp', 'ai-memory', 'serena', 'serena-agent', 'context-mode', 'mcporter',
  'time', 'nohup', 'exec', 'nice', 'stdbuf', 'timeout', 'command', 'xargs', 'sudo', 'env', 'rtk', 'eval', 'ssh', 'sh', 'bash', 'dash', 'zsh', 'ksh'])

const inputs = JSON.parse(readFileSync(opt('inputs'), 'utf8'))
const valid = opt('valid') ? JSON.parse(readFileSync(opt('valid'), 'utf8')) : inputs.map(() => true)
const totals = { inputs: inputs.length, bash_valid: opt('valid') ? valid.filter(Boolean).length : null, same: 0, differ: 0, old_throws: 0, new_throws: 0, new_program_outside_vocabulary: 0,
  old_program_outside_vocabulary: 0, differ_new_parse_error: 0, differ_kinds: {} }
const rows = []
inputs.forEach((text, index) => {
  if (!valid[index]) return
  let a, b
  try { a = read(oldK, text) } catch { totals.old_throws++; return }
  try { b = read(newK, text) } catch { totals.new_throws++; return }
  const oldRecords = oldK.commandInvocations(text), newRecords = newK.commandInvocations(text)
  if (oldRecords.some((i) => i.program && !PROGRAMS.has(i.program) && !i.lane)) totals.old_program_outside_vocabulary++
  if (newRecords.some((i) => i.program && !PROGRAMS.has(i.program) && !i.lane)) totals.new_program_outside_vocabulary++
  if (same(a, b)) { totals.same++; return }
  totals.differ++
  const kinds = [!same(a.lanes, b.lanes) && 'lanes', a.remote !== b.remote && 'remote', a.unresolved !== b.unresolved && 'unresolved'].filter(Boolean).join('+')
  totals.differ_kinds[kinds] = (totals.differ_kinds[kinds] || 0) + 1
  const error = parseError(text)
  if (error) totals.differ_new_parse_error++
  rows.push({ index, text, old: a, new: b, error, signature: signatureOf(a, b) })
})

// ddmin over `units` (token strings whose concatenation is the text): a minimal subsequence for which `keeps` still holds.
const ddmin = (units, keeps) => {
  const test = (t) => t.length > 0 && keeps(t.join(''))
  let n = 2
  while (units.length >= 2) {
    const size = Math.ceil(units.length / n)
    let reduced = false
    for (let start = 0; start < units.length; start += size) {
      const rest = [...units.slice(0, start), ...units.slice(start + size)]
      if (rest.length && test(rest)) { units = rest; n = Math.max(n - 1, 2); reduced = true; break }
    }
    if (!reduced) { if (n >= units.length) break; n = Math.min(units.length, n * 2) }
  }
  return units
}
if (args.includes('--reduce-text')) {
  // Inputs with no token sequence (real commands): lines first, then whitespace-separated words. A text bash accepts keeps being one.
  for (const row of rows) {
    const keep = bashValid(row.text) ? (t) => bashValid(t) && hasSignature(row.signature, t) : (t) => hasSignature(row.signature, t)
    const lines = ddmin(row.text.split(/(?<=\n)/), keep)
    row.witness = ddmin(lines.join('').match(/^\s+|\S+\s*/g) ?? [], keep).join('') // a word keeps its trailing blanks, so no unit merges two words
    row.witness_old = read(oldK, row.witness)
    row.witness_new = read(newK, row.witness)
    row.witness_error = parseError(row.witness)
    row.witness_new_programs = programsOf(newK, row.witness)
  }
  totals.distinct_witnesses = new Set(rows.map((r) => r.witness)).size
}
if (args.includes('--reduce')) {
  const seqs = sequences(opt('profile'), Number(opt('seed')), inputs.length)
  for (const row of rows) {
    row.witness = ddmin(seqs[row.index], (t) => bashValid(t) && hasSignature(row.signature, t)).join('')
    row.witness_old = read(oldK, row.witness)
    row.witness_new = read(newK, row.witness)
    row.witness_error = parseError(row.witness)
    row.witness_new_programs = programsOf(newK, row.witness)
  }
  totals.distinct_witnesses = new Set(rows.map((r) => r.witness)).size
}
console.log(JSON.stringify(totals))
if (opt('out')) writeFileSync(opt('out'), rows.map((r) => JSON.stringify(r)).join('\n') + (rows.length ? '\n' : ''), { mode: 0o600 })
