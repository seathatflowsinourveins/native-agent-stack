// Count-only timing of each reading of a shell call over a corpus of shell texts, with the parser loaded (milliseconds per call).
//
//   node timing.mjs --kernel <kernel.mjs> --inputs <inputs.json>
//
// executedText (plain and inline-HTTP), fetchKind and commandInvocations are the readings of a shell call; measureTranscript of one Bash
// call runs all of them (the M4 text machinery runs three times per call), so its time is the cost of the repeated reading.
import { readFileSync } from 'node:fs'

const args = process.argv.slice(2)
const opt = (name) => { const i = args.indexOf('--' + name); return i < 0 ? null : args[i + 1] }
const kernel = await import(opt('kernel'))
const parser = await kernel.loadShellParser()
if (!parser.ok) throw new Error('no verified tree-sitter-bash install: ' + parser.reason)
const commands = JSON.parse(readFileSync(opt('inputs'), 'utf8'))
const stat = (name, ms) => {
  const sorted = [...ms].sort((a, b) => a - b), sum = sorted.reduce((x, y) => x + y, 0)
  return { name, calls: sorted.length, total_s: +(sum / 1000).toFixed(2), mean_ms: +(sum / sorted.length).toFixed(3), p50_ms: +sorted[sorted.length >> 1].toFixed(3),
    p99_ms: +sorted[Math.floor(sorted.length * 0.99)].toFixed(2), max_ms: +sorted[sorted.length - 1].toFixed(1) }
}
const time = (read) => {
  const out = new Float64Array(commands.length)
  commands.forEach((command, i) => { const start = performance.now(); read(command); out[i] = performance.now() - start })
  return out
}
for (let i = 0; i < Math.min(2000, commands.length); i++) { kernel.executedText(commands[i]); kernel.commandInvocations(commands[i]) } // warm up
const call = (command) => [{ type: 'assistant', timestamp: '2026-09-26T01:00:00Z', message: { content: [{ type: 'tool_use', id: 'c', name: 'Bash', input: { command } }] } }]
console.log(JSON.stringify([
  stat('executedText plain', time((c) => kernel.executedText(c))),
  stat('executedText inlineHttp', time((c) => kernel.executedText(c, { inlineHttp: true }))),
  stat('fetchKind', time((c) => kernel.fetchKind(c))),
  stat('commandInvocations', time((c) => kernel.commandInvocations(c))),
  stat('measureTranscript (one Bash call)', time((c) => kernel.measureTranscript(call(c)))),
]))
