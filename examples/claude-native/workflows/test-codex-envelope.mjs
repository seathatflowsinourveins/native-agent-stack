#!/usr/bin/env node
// OFFLINE parser check for the Codex bridge (no provider call). Verifies the
// { job, storedJob } result envelope shape from companion 1.0.6 handleResult.
import { parseResultPayload, projectEnvelope } from './codex-cross-review.mjs'
import { readFileSync } from 'node:fs'
let failed = 0
const expect = (n, c) => { console.log((c ? 'PASS ' : 'FAIL ') + n); if (!c) failed++ }
const ok = parseResultPayload({ job: { id: 'j1', status: 'completed', threadId: 't1', turnId: 'u1' }, storedJob: { result: { status: 0, rawOutput: 'findings', touchedFiles: [] } } })
expect('completed job + payload status 0 is success with ids', ok.success && ok.thread_id === 't1' && ok.turn_id === 'u1' && ok.raw_output === 'findings')
const failedJob = parseResultPayload({ job: { id: 'j2', status: 'failed', threadId: 't2' }, storedJob: { result: { status: 1, rawOutput: '' } } })
expect('failed job keeps ids and is not success', !failedJob.success && failedJob.thread_id === 't2' && failedJob.job_status === 'failed')
const cancelled = parseResultPayload({ job: { id: 'j3', status: 'cancelled' }, storedJob: {} })
expect('cancelled job without payload is not success, result_status null', !cancelled.success && cancelled.result_status === null)
const flat = parseResultPayload({ status: 'completed', threadId: 'x', rawOutput: 'y' })
expect('old flat shape is not mistaken for success', !flat.success && flat.job_status === null)
expect('null input is handled', parseResultPayload(null).success === false)
const proj = projectEnvelope({ outcome: 'completed:success', thread_id: 't', job_status: 'completed', result_status: 0, elapsed_ms: 5 }, 'j', '/out')
expect('projection keeps numeric 0 result_status', proj.result_status === 0 && proj.job_status === 'completed')
expect('projection nulls absent fields', projectEnvelope({ outcome: 'x' }, null, '/o').result_status === null && projectEnvelope({ outcome: 'x' }, null, '/o').thread_id === null)
for (const f of process.argv.slice(2)) {
  const raw = readFileSync(f, 'utf8'); const i = raw.indexOf('{')
  const r = parseResultPayload(JSON.parse(raw.slice(i)))
  console.log('FILE ' + f + ' -> ' + JSON.stringify({ job_status: r.job_status, result_status: r.result_status, thread_id: r.thread_id, success: r.success, raw_output_chars: r.raw_output_chars }))
}
process.exit(failed ? 1 : 0)
