// A random differential of yaml.parse between two installs of the yaml package (here 2.9.0, the version skills-yaml.pin.json
// pins, and 2.9.1, the one a fresh install of skills@1.7.0 resolves on 2026-09-30), aimed at what 2.9.1 changed: line
// unfolding in multi-line plain and single-quoted scalars (eemeli/yaml #714, dist/compose/resolve-flow-scalar.js).
//
//   node yaml_versions.mjs <install A> <install B> <count> <seed>
//
// Each case is a one-key document whose value is a single-quoted scalar, a plain scalar, or a plain scalar on indented
// lines, built from pieces that exercise the folding (spaces, tabs, blank and whitespace-only lines, '', #, ': ', -).
// Prints the number of cases, of differing results (value or error code) and of error/no-error flips, and the first
// differing cases; exit 1 when any differs.
import { createRequire } from 'node:module'
import { join } from 'node:path'

const [installA, installB, count, seedArg] = process.argv.slice(2)
const load = (dir) => createRequire(join(dir, 'x.js'))('yaml')
const [a, b] = [load(installA), load(installB)]
const versions = [installA, installB].map((dir) => createRequire(join(dir, 'x.js'))('yaml/package.json').version)
let seed = Number(seedArg)
const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648
const pieces = [' ', '\t', 'a', 'b', ' x ', '\n', '\n ', '\n  ', '\n\t', '\n\n', '\n \n', "''", '#', ': ', '-']
const run = (yaml, src) => { try { return JSON.stringify(yaml.parse(src)) } catch (err) { return `ERR ${err.code || err.name}` } }
let differing = 0, flips = 0
const shown = []
for (let i = 0; i < Number(count); i++) {
  let body = ''
  const n = 1 + Math.floor(rnd() * 12)
  for (let j = 0; j < n; j++) body += pieces[Math.floor(rnd() * pieces.length)]
  const kind = Math.floor(rnd() * 3)
  const src = kind === 0 ? `d: 'x${body}y'\n` : kind === 1 ? `d: x${body}y\n` : `d:\n  x${body.replace(/\n/g, '\n  ')}y\n`
  const [x, y] = [run(a, src), run(b, src)]
  if (x !== y) {
    differing++
    if (x.startsWith('ERR') !== y.startsWith('ERR')) flips++
    if (shown.length < 5) shown.push({ src, [versions[0]]: x, [versions[1]]: y })
  }
}
console.log(JSON.stringify({ versions, cases: Number(count), seed: Number(seedArg), differing, error_flips: flips, first: shown }))
process.exitCode = differing ? 1 : 0
