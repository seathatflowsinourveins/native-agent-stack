// The M4 reading is unchanged by the command-position layer: two kernels' executed text (plain and inline-HTTP), fetch kind and complete m4
// object over the same inputs, as counts.
//
//   node m4-identity.mjs --a <kernel.mjs> --b <kernel.mjs> --inputs <inputs.json> [--valid <valid.json>] [--fields text]
//
// --a is the kernel before the AST layer replaced the scanner (its M4 helpers are the ones kept), --b the kernel under test. Neither needs
// the parser for M4; the input may be any list of shell texts. `--fields text` compares only executedText (both modes) and fetchKind, not the
// complete m4 object (the object's by_carrier follows the carrier rule, which a change of the lane layer may move on purpose).
import { readFileSync } from 'node:fs'

const args = process.argv.slice(2)
const opt = (name) => { const i = args.indexOf('--' + name); return i < 0 ? null : args[i + 1] }
const a = await import(opt('a')), b = await import(opt('b'))
const inputs = JSON.parse(readFileSync(opt('inputs'), 'utf8'))
const valid = opt('valid') ? JSON.parse(readFileSync(opt('valid'), 'utf8')) : inputs.map(() => true)
const row = (command) => [{ type: 'assistant', timestamp: '2026-09-26T01:00:00Z', message: { content: [{ type: 'tool_use', id: 'c', name: 'Bash', input: { command } }] } }]
const textOnly = opt('fields') === 'text'
const view = (kernel, text) => JSON.stringify([kernel.executedText(text), kernel.executedText(text, { inlineHttp: true }), kernel.fetchKind(text), textOnly ? null : kernel.measureTranscript(row(text)).m4])
const totals = { inputs: inputs.length, analysed: 0, identical: 0, different: 0, a_throws: 0, b_throws: 0 }
inputs.forEach((text, i) => {
  if (!valid[i]) return
  totals.analysed++
  let x, y
  try { x = view(a, text) } catch { totals.a_throws++; return }
  try { y = view(b, text) } catch { totals.b_throws++; return }
  if (x === y) totals.identical++; else totals.different++
})
console.log(JSON.stringify(totals))
