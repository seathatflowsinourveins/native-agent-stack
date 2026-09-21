#!/usr/bin/env node
// Syntax check for Workflow scripts. The Workflow runtime wraps the script body in
// an async function with agent/parallel/pipeline/phase/log/args/budget/workflow in
// scope, so top-level `return`/`await` are valid there but fail a plain module
// check. This reproduces that wrapping without executing anything.
import { readFileSync } from 'node:fs'
let failed = 0
for (const file of process.argv.slice(2)) {
  const src = readFileSync(file, 'utf8')
  if (!/^export const meta = \{/m.test(src)) { console.error('FAIL ' + file + ': missing `export const meta = {` literal'); failed++; continue }
  const body = src.replace(/^export const meta/m, 'const meta')
  try {
    new Function('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', 'workflow', 'return (async () => {\n' + body + '\n})()')
    console.log('SYNTAX_OK ' + file)
  } catch (e) { console.error('FAIL ' + file + ': ' + e.message); failed++ }
}
process.exit(failed ? 1 : 0)
