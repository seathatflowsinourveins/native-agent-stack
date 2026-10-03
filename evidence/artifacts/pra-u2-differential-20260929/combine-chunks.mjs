#!/usr/bin/env node
// Sums the outputs of differential.mjs over adjacent windows that partition one window (W_AA in twelve parts, run at once because a
// --rtk-check sweep spends its time in one rtk subprocess per command and part). A call counts in the window of its first row, so the
// rtk_parts counters of the parts add up to the whole window's, except a Bash call whose hook row falls in the next part (its rewrite is
// then not read). The shares and B8's status are computed again from the sums. Counts only.
//   node combine-chunks.mjs <diff-1.json> [<diff-2.json> ...]
import { readFileSync } from 'node:fs'

const runs = process.argv.slice(2).map((f) => JSON.parse(readFileSync(f, 'utf8')))
const sum = (key) => runs.reduce((n, r) => n + r[key], 0)
const merge = (key) => { const out = {}; for (const r of runs) for (const [k, v] of Object.entries(r[key])) out[k] = (out[k] || 0) + v; return out }
const COUNTERS = ['calls', 'unknown_calls', 'eligible_parts', 'ineligible_parts', 'eligible_calls', 'observed_covered_parts', 'replayed_covered_parts',
  'explicit_rtk_on_excluded_or_sensitive', 'proxy_parts', 'observed_covered_succeeded_calls']
const share = (a, b) => b ? Math.round((a / b) * 10000) / 10000 : null
function rtk(scope, side) {
  const out = Object.fromEntries(COUNTERS.map((k) => [k, runs.reduce((n, r) => n + (r.effects[scope][side][k] ?? 0), 0)]))
  const states = {}
  for (const r of runs) for (const [k, v] of Object.entries(r.effects[scope][side].eligible_call_states || {})) states[k] = (states[k] || 0) + v
  if (side === 'base') { delete out.observed_covered_succeeded_calls } else out.eligible_call_states = states
  out.unknown_call_share = share(out.unknown_calls, out.calls)
  out.coverage = share(out.observed_covered_parts, out.eligible_parts)
  out.b8_status = out.unknown_calls * 100 > out.calls * 5 ? 'incomplete' : 'measured'
  out.statuses_of_parts = runs.map((r) => r.effects[scope][side].status)
  return out
}
const unexpected = sum('unexpected')
console.log(JSON.stringify({ kind: 'pra_u2_differential_combined', parts: runs.length, paths: sum('paths'), equal: sum('equal'), changed_allowed: sum('changed_allowed'),
  new_paths: sum('new_paths'), added_allowed: sum('added_allowed'), unexpected, unexpected_changed: merge('unexpected_changed'), unexpected_added: merge('unexpected_added'),
  unexpected_removed: merge('unexpected_removed'), exit_codes: runs.flatMap((r) => r.exit_codes), allowed_by_entry: merge('allowed_by_entry'),
  effects: { children_in_window: runs.map((r) => r.effects.children_in_window[1]), main_sessions_in_window: runs.map((r) => r.effects.main_sessions_in_window[1]),
    rtk_parts_children: { base: rtk('rtk_parts_children', 'base'), new: rtk('rtk_parts_children', 'new') },
    rtk_parts_main: { base: rtk('rtk_parts_main', 'base'), new: rtk('rtk_parts_main', 'new') },
    actors_unknown_calls_moved: Object.fromEntries(['unknown_to_known_calls', 'known_to_unknown_calls'].map((k) => [k, runs.reduce((n, r) => n + r.effects.actors_unknown_calls_moved[k], 0)])) } }, null, 1))
process.exitCode = unexpected ? 1 : 0
