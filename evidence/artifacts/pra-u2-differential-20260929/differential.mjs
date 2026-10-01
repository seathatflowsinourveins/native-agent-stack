#!/usr/bin/env node
// The U2 differential (U2 design 10.3 with review-u2's medium finding: an explicit allow-list, equality everywhere else). It runs two
// child-usage.mjs kernels as their own CLIs with identical arguments (a lanes sweep over one root and window, or run mode over workflow
// transcript directories), flattens both JSON outputs to leaf paths, and classifies every path that differs against expected-changes.json:
// a path only the new output has must fall under an `added` entry, a path whose value differs under a `changed` entry, and a path only the
// base output has is always unexpected. Prints counts only: per entry, the number of paths it allowed; for unexpected paths, their shape
// with array positions as [] (the outputs hold names and counts only, never ids, by the kernel's own contract).
//   node differential.mjs --base <child-usage.mjs> --new <child-usage.mjs> --expected <expected-changes.json> [--rtk-check]
//        (--root <dir> --since <ISO> --until <ISO> | --run <workflow transcript dir> [--run <dir> ...])
import { spawn } from 'node:child_process'
import { readFileSync } from 'node:fs'

const argv = process.argv.slice(2)
const one = (name) => { const i = argv.indexOf('--' + name); return i < 0 ? null : argv[i + 1] }
const many = (name) => argv.flatMap((a, i) => a === '--' + name ? [argv[i + 1]] : [])
const base = one('base'), next = one('new'), expected = JSON.parse(readFileSync(one('expected'), 'utf8'))
const rtk = argv.includes('--rtk-check') ? ['--rtk-check'] : []
if (!base || !next) { console.error('usage: see the header'); process.exit(2) }

// Pattern paths: dot-separated segments; <name> is any one segment, {a,b} one of the listed, [] an array position, ['x'] the segment x. A
// pattern allows every path it is a prefix of.
const segmentsOf = (pattern) => {
  const out = []
  for (const raw of pattern.split('.')) {
    let s = raw
    const bracket = s.indexOf('[')
    if (bracket >= 0) {
      if (bracket > 0) out.push(s.slice(0, bracket))
      for (const m of s.slice(bracket).split(']').filter(Boolean)) out.push(m === '[' ? '[]' : m.slice(1).replace(/^'|'$/g, ''))
      continue
    }
    out.push(s)
  }
  return out
}
const segmentMatches = (p, s) => p === s || (p.startsWith('<') && p.endsWith('>')) || (p === '[]' && typeof s === 'number')
  || (p.startsWith('{') && p.endsWith('}') && p.slice(1, -1).split(',').includes(String(s)))
// A pattern allows a path it is a prefix of; an empty object or array leaf is allowed where a pattern continues below it (an empty map
// such as call_states.by_server when an actor has no MCP call).
const prefixOf = (pattern, path, emptyLeaf) => (pattern.length <= path.length && pattern.every((p, i) => segmentMatches(p, path[i])))
  || (emptyLeaf && path.length < pattern.length && path.every((s, i) => segmentMatches(pattern[i], s)))

// Where a path's object starts: [object class, index of its first relative segment]. Classes follow expected-changes.json "objects": actor
// (sweep actors[].measurement; run children[].lanes.measurement and superseded_attempts[].lanes.measurement), aggregate (groups.*
// .measurement and main.measurement), sizes (m3, m5, by_carrier.<carrier> and exceptions.<class> inside either), run_child (the other
// fields of a run-mode child or superseded attempt) and top (the other top-level fields of either output).
const SIZES = new Set(['m3', 'm5'])
function classify(path) {
  const k = path.indexOf('measurement')
  if (k >= 0) {
    const owner = path.slice(0, k), found = []
    const actor = (owner[0] === 'actors' && owner.length === 2) || ((owner[0] === 'children' || owner[0] === 'superseded_attempts') && owner.length === 3 && owner[2] === 'lanes')
    const aggregate = owner[0] === 'groups' || (owner.length === 1 && owner[0] === 'main')
    found.push([actor ? 'actor' : aggregate ? 'aggregate' : 'other_measurement', k + 1])
    const rel = path.slice(k + 1)
    if (SIZES.has(rel[0])) found.push(['sizes', k + 2])
    else if ((rel[0] === 'by_carrier' || rel[0] === 'exceptions') && rel.length > 1) found.push(['sizes', k + 3])
    return found
  }
  if ((path[0] === 'children' || path[0] === 'superseded_attempts') && typeof path[1] === 'number') return [['run_child', 2]]
  return [['top', 0]]
}

const allowList = []
for (const stage of expected.stages) {
  for (const kind of ['added', 'changed']) for (const [n, entry] of (stage[kind] || []).entries()) {
    const classes = entry.in.split(',').map((c) => c.trim())
    const paths = entry.paths || (entry.path ? [entry.path] : [])
    allowList.push({ id: stage.stage.split(':')[0] + ' ' + kind + ' #' + (n + 1), kind, classes, patterns: paths.map(segmentsOf), allowed: 0 })
  }
}
function allowedBy(kind, path, emptyLeaf = false) {
  for (const [cls, from] of classify(path)) {
    const rel = path.slice(from)
    for (const entry of allowList) {
      if (entry.kind !== kind || !entry.classes.includes(cls)) continue
      if (entry.patterns.some((p) => prefixOf(p, rel, emptyLeaf))) return entry
    }
  }
  return null
}

// Leaves of a JSON value as [segments, JSON text]; an empty object or array is a leaf of its own.
function leaves(value, prefix = [], out = new Map()) {
  if (value && typeof value === 'object') {
    const keys = Array.isArray(value) ? value.map((_, i) => i) : Object.keys(value)
    if (!keys.length) out.set(JSON.stringify(prefix), [prefix, JSON.stringify(value)])
    for (const k of keys) leaves(value[k], [...prefix, k], out)
  } else out.set(JSON.stringify(prefix), [prefix, JSON.stringify(value)])
  return out
}
const shapeOf = (path) => path.map((s) => typeof s === 'number' ? '[]' : s).join('.')

function compare(a, b, totals) {
  const left = leaves(a), right = leaves(b)
  // A container that went from empty to filled (an issues list that gains its first issue) or from filled to empty is a change of the
  // container, classified as one; any other path only the base output has is unexpected.
  const filledBelow = (key) => { const stem = key.slice(0, -1) + ','; for (const k of right.keys()) if (k.startsWith(stem)) return true; return false }
  const emptied = new Set([...right.values()].filter(([, v]) => v === '{}' || v === '[]').map(([p]) => JSON.stringify(p)))
  for (const [key, [path, value]] of left) {
    totals.paths++
    if (!right.has(key)) {
      const grew = (value === '{}' || value === '[]') && filledBelow(key)
      const at = grew ? -1 : path.findIndex((_, k) => k > 0 && emptied.has(JSON.stringify(path.slice(0, k))))
      const entry = grew ? allowedBy('changed', path) : at > 0 ? allowedBy('changed', path.slice(0, at)) : null
      if (entry) { entry.allowed++; totals.changed_allowed++ } else totals.unexpected_removed[shapeOf(path)] = (totals.unexpected_removed[shapeOf(path)] || 0) + 1
      continue
    }
    if (right.get(key)[1] === value) { totals.equal++; continue }
    const entry = allowedBy('changed', path)
    if (entry) { entry.allowed++; totals.changed_allowed++ } else totals.unexpected_changed[shapeOf(path)] = (totals.unexpected_changed[shapeOf(path)] || 0) + 1
  }
  for (const [key, [path, value]] of right) {
    if (left.has(key)) continue
    totals.new_paths++
    const entry = allowedBy('added', path, value === '{}' || value === '[]')
    if (entry) { entry.allowed++; totals.added_allowed++ } else totals.unexpected_added[shapeOf(path)] = (totals.unexpected_added[shapeOf(path)] || 0) + 1
  }
}
// Both kernels run at once, each its own process (a --rtk-check sweep spends most of its time in rtk subprocesses).
const run = (kernel, args) => new Promise((done, fail) => {
  const p = spawn(process.execPath, [kernel, ...args], { stdio: ['ignore', 'pipe', 'pipe'] }), out = [], err = []
  p.stdout.on('data', (b) => out.push(b))
  p.stderr.on('data', (b) => err.push(b))
  p.on('close', (status) => {
    if (status !== 0 && status !== 1) fail(new Error('kernel exited ' + status + ': ' + Buffer.concat(err).toString('utf8').slice(0, 300)))
    else done({ status, output: JSON.parse(Buffer.concat(out).toString('utf8')) })
  })
})
const totals = { mode: null, paths: 0, equal: 0, changed_allowed: 0, new_paths: 0, added_allowed: 0, unexpected_changed: {}, unexpected_added: {}, unexpected_removed: {}, exit_codes: [] }
const effects = {}
if (one('root')) {
  totals.mode = 'lanes_sweep'
  const args = ['--lanes-sweep', '--root', one('root'), '--since', one('since'), '--until', one('until'), ...rtk]
  const [a, b] = await Promise.all([run(base, args), run(next, args)])
  compare(a.output, b.output, totals)
  totals.exit_codes.push([a.status, b.status])
  const r = (o) => o.groups.all.measurement.rtk_parts, m = (o) => o.main.measurement.rtk_parts
  const pick = (x) => ({ status: x.status, calls: x.calls, unknown_calls: x.unknown_calls, unknown_call_share: x.unknown_call_share ?? null, eligible_parts: x.eligible_parts,
    ineligible_parts: x.ineligible_parts, eligible_calls: x.eligible_calls, observed_covered_parts: x.observed_covered_parts, replayed_covered_parts: x.replayed_covered_parts,
    coverage: x.coverage, call_coverage: x.call_coverage, explicit_rtk_on_excluded_or_sensitive: x.explicit_rtk_on_excluded_or_sensitive, proxy_parts: x.proxy_parts,
    observed_covered_succeeded_calls: x.observed_covered_succeeded_calls ?? null, eligible_call_states: x.eligible_call_states ?? null })
  effects.children_in_window = [a.output.children_in_window, b.output.children_in_window]
  effects.main_sessions_in_window = [a.output.main_sessions_in_window, b.output.main_sessions_in_window]
  effects.rtk_parts_children = { base: pick(r(a.output)), new: pick(r(b.output)) }
  effects.rtk_parts_main = { base: pick(m(a.output)), new: pick(m(b.output)) }
  effects.final_return_children = b.output.groups.all.measurement.final_return
  effects.final_return_main = b.output.main.measurement.final_return
  const moved = { unknown_to_known_calls: 0, known_to_unknown_calls: 0 }
  a.output.actors.forEach((x, i) => {
    const before = x.measurement.rtk_parts.unknown_calls, after = b.output.actors[i].measurement.rtk_parts.unknown_calls
    if (after < before) moved.unknown_to_known_calls += before - after
    if (after > before) moved.known_to_unknown_calls += after - before
  })
  effects.actors_unknown_calls_moved = moved
} else {
  totals.mode = 'run'
  const children = { base_incomplete: 0, new_incomplete: 0, newly_incomplete: 0, by_new_issue: {} }
  for (const dir of many('run')) {
    const [a, b] = await Promise.all([run(base, [dir, ...rtk]), run(next, [dir, ...rtk])])
    compare(a.output, b.output, totals)
    totals.exit_codes.push([a.status, b.status])
    b.output.children.forEach((c, i) => {
      const old = a.output.children[i]
      if (!old.complete) children.base_incomplete++
      if (!c.complete) children.new_incomplete++
      if (old.complete && !c.complete) children.newly_incomplete++
      for (const issue of c.issues.filter((x) => !old.issues.includes(x))) {
        const key = issue.startsWith('returned with ') ? 'returned with N background task(s) that had no completion notification' : issue
        children.by_new_issue[key] = (children.by_new_issue[key] || 0) + 1
      }
    })
  }
  effects.run_children = children
  effects.runs = many('run').length
  effects.exit_code_changes = totals.exit_codes.filter(([x, y]) => x !== y).length
}
const unexpected = Object.values(totals.unexpected_changed).reduce((n, v) => n + v, 0) + Object.values(totals.unexpected_added).reduce((n, v) => n + v, 0)
  + Object.values(totals.unexpected_removed).reduce((n, v) => n + v, 0)
console.log(JSON.stringify({ kind: 'pra_u2_differential', ...totals, unexpected, allowed_by_entry: Object.fromEntries(allowList.filter((e) => e.allowed).map((e) => [e.id, e.allowed])), effects }, null, 1))
process.exitCode = unexpected ? 1 : 0
