// Node bridge of the frozen-check grader (unit U9): one JSON request on stdin, one JSON answer on stdout.
//
// It exposes the kernel functions the grader consumes from examples/claude-native/workflows/child-usage.mjs and nothing
// else: it reads only the file a request names, runs no command and writes no file. The kernel is imported as a
// namespace so a name that a sibling unit has not merged yet (U1 loadShellParser, shellParserStatus and
// commandInvocations; U2 callLedger and m14State; U4 validateIdentityTable) is reported as unavailable instead of
// failing the link. The Python side maps `available: false` to its own outcome; `capabilities` lists what is real.
//
// Requests: {op: 'capabilities'}, {op: 'measure', path}, {op: 'call_ledger', path},
//           {op: 'invocations', commands: [string]}, {op: 'validate_identity', table, options}.
import * as kernel from '../../examples/claude-native/workflows/child-usage.mjs'
import { readFileSync } from 'node:fs'

const PRESENT = ['measureTranscript', 'childLanes', 'executedText', 'fetchKind', 'DEFAULT_MARKER']
const SIBLINGS = ['loadShellParser', 'shellParserStatus', 'commandInvocations', 'callLedger', 'm14State', 'validateIdentityTable']
const has = (name) => typeof kernel[name] === 'function'

// A transcript is JSON lines; a line that does not parse is counted, never guessed.
function readRows(path) {
  const rows = []
  let errors = 0
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    if (!line.trim()) continue
    try { const row = JSON.parse(line); if (row && typeof row === 'object') rows.push(row); else errors++ } catch { errors++ }
  }
  return { rows, errors }
}

const ops = {
  capabilities() {
    return {
      present: PRESENT.filter((name) => name in kernel),
      sibling_present: SIBLINGS.filter((name) => name in kernel),
      sibling_absent: SIBLINGS.filter((name) => !(name in kernel)),
    }
  },
  measure({ path }) {
    if (typeof path !== 'string' || !has('measureTranscript')) return { available: false }
    const { rows, errors } = readRows(path)
    const measured = kernel.measureTranscript(rows)
    return { available: true, parse_errors: errors, hook_context: measured.hook_context,
      calls_without_result: measured.calls_without_result, mcp_states: measured.mcp_states }
  },
  call_ledger({ path }) {
    if (typeof path !== 'string' || !has('callLedger')) return { available: false }
    const { rows, errors } = readRows(path)
    return { available: true, parse_errors: errors, records: kernel.callLedger(rows, { window: null }) }
  },
  invocations({ commands }) {
    if (!Array.isArray(commands) || !has('commandInvocations')) return { available: false }
    const status = has('shellParserStatus') ? kernel.shellParserStatus() : null
    return { available: true, parser_ok: status ? Boolean(status.ok) : null,
      results: commands.map((command) => kernel.commandInvocations(String(command))) }
  },
  validate_identity({ table, options }) {
    if (!has('validateIdentityTable')) return { available: false }
    try {
      return { available: true, ok: true, result: kernel.validateIdentityTable(table, options || {}) }
    } catch (error) {
      return { available: true, ok: false, code: String(error && error.code || 'E_ROW'), message: String(error && error.message || '') }
    }
  },
}

let request
try {
  request = JSON.parse(readFileSync(0, 'utf8'))
} catch {
  process.stderr.write('node_bridge: the request is not JSON\n')
  process.exit(2)
}
const op = request && ops[request.op]
if (!op) {
  process.stderr.write('node_bridge: unknown op\n')
  process.exit(2)
}
try {
  process.stdout.write(JSON.stringify(op(request)) + '\n')
} catch {
  process.stderr.write('node_bridge: the request failed\n')
  process.exit(2)
}
