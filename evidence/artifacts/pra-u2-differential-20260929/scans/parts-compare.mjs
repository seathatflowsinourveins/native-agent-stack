#!/usr/bin/env node
// Count-only comparison of the base and the U2 part splitters (binding decision B8) over every Bash call in a window: which calls each can
// read, and, where they disagree on whether a call can be read, whether GNU bash accepts the command (`bash -n`, which runs nothing). Also
// counts the calls both read into a different number of parts, by the constructs they hold. Prints counts and construct names only.
//   node parts-compare.mjs <base child-usage.mjs> <U2 child-usage.mjs> <root> <since ISO> <until ISO>
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'

const [basePath, newPath, root, sinceIso, untilIso] = process.argv.slice(2)
// The base kernel does not export its splitter: its self-contained function body is taken from the file as it is.
const src = readFileSync(basePath, 'utf8'), at = src.indexOf('function shellParts(command) {'), end = src.indexOf('\n}\n', at)
const baseParts = new Function('command', src.slice(src.indexOf('{', at) + 1, end + 1))
const { shellParts } = await import(pathToFileURL(resolve(newPath)).href)
const since = Date.parse(sinceIso), until = Date.parse(untilIso)
const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(join(d, e.name)) : e.name.endsWith('.jsonl') ? [join(d, e.name)] : [])
const bashAccepts = (c) => spawnSync('bash', ['-n'], { input: c, encoding: 'utf8' }).status === 0
const constructs = (c) => [c.includes('<<') && 'heredoc_operator', c.includes('$((') && 'arithmetic', /(^|[\s;&|(])#/.test(c) && 'comment', c.includes('&>') && 'and_greater',
  c.includes('>|') && 'clobber', c.includes('<&') && 'less_and', c.includes('|&') && 'pipe_both', /"[^"]*`/.test(c) && 'backquote_in_double_quotes',
  /"[^"]*\$\(/.test(c) && 'substitution_in_double_quotes'].filter(Boolean)
const out = { bash_calls: 0, both_read: 0, both_read_same_parts: 0, both_read_part_count_differs: 0, only_u2_reads: 0, only_base_reads: 0, neither_reads: 0,
  only_u2_reads_bash_accepts: 0, only_base_reads_bash_accepts: 0, neither_reads_bash_accepts: 0, constructs_only_u2_reads: {}, constructs_part_count_differs: {},
  constructs_neither_reads: {} }
const bump = (map, list) => { for (const k of list.length ? list : ['none_of_these']) map[k] = (map[k] || 0) + 1 }
for (const f of walk(root)) for (const line of readFileSync(f, 'utf8').split('\n')) {
  if (!line.includes('"Bash"')) continue
  let row
  try { row = JSON.parse(line) } catch { continue }
  const t = Date.parse(row?.timestamp)
  if (!(t >= since && t < until) || row.type !== 'assistant') continue
  for (const b of row.message?.content || []) {
    if (b?.type !== 'tool_use' || b.name !== 'Bash') continue
    const c = String(b.input?.command || '')
    out.bash_calls++
    const x = baseParts(c), y = shellParts(c)
    if (x && y) {
      out.both_read++
      if (x.length === y.length) out.both_read_same_parts++
      else { out.both_read_part_count_differs++; bump(out.constructs_part_count_differs, constructs(c)) }
    } else if (y) { out.only_u2_reads++; if (bashAccepts(c)) out.only_u2_reads_bash_accepts++; bump(out.constructs_only_u2_reads, constructs(c)) }
    else if (x) { out.only_base_reads++; if (bashAccepts(c)) out.only_base_reads_bash_accepts++ }
    else { out.neither_reads++; if (bashAccepts(c)) out.neither_reads_bash_accepts++; bump(out.constructs_neither_reads, constructs(c)) }
  }
}
console.log(JSON.stringify({ kind: 'pra_u2_parts_compare', window: { since: sinceIso, until: untilIso }, bash: spawnSync('bash', ['--version'], { encoding: 'utf8' }).stdout.split('\n')[0].replace(/\s*\(.*$/, ''), ...out }, null, 1))
