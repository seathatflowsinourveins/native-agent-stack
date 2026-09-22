#!/usr/bin/env node
// Bridge to the installed official Codex companion (Claude plugin openai-codex)
// for one bounded READ-ONLY Codex task from a Workflow stage or the coordinator.
// Uses the companion's tracked-job lifecycle (task --background --json, status
// --wait, result --json, cancel --json) instead of a synchronous wrapper, so the
// job's status, rendered output, threadId and turnId persist independently of
// this process. Bash tool calls expose CLAUDE_PLUGIN_DATA but not
// CLAUDE_PLUGIN_ROOT, so the companion path is resolved by globbing the newest
// installed version. No dependencies. Never passes --write.
// Accounting boundary: the companion JSON omits usage/model/effort; retrieve
// those only from scoped native Codex records via the returned threadId.
import { readdirSync, existsSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir } from 'node:os'
import { spawnSync } from 'node:child_process'

function semverKey(v) { return v.split('.').map((n) => parseInt(n, 10) || 0) }
function resolveCompanion() {
  const root = process.env.CODEX_COMPANION_CACHE || join(homedir(), '.claude', 'plugins', 'cache', 'openai-codex', 'codex')
  if (!existsSync(root)) return null
  const versions = readdirSync(root).filter((d) => /^\d+\.\d+\.\d+$/.test(d)).sort((x, y) => {
    const a = semverKey(x), b = semverKey(y)
    for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] - b[i]
    return 0
  })
  for (let i = versions.length - 1; i >= 0; i--) {
    const p = join(root, versions[i], 'scripts', 'codex-companion.mjs')
    if (existsSync(p)) return { version: versions[i], path: p }
  }
  return null
}
function opt(argv, flag, dflt) { const i = argv.indexOf(flag); return i !== -1 && argv[i + 1] !== undefined ? argv[i + 1] : dflt }
function runJson(companion, args, timeoutMs) {
  const res = spawnSync(process.execPath, [companion.path, ...args], { encoding: 'utf8', timeout: timeoutMs, maxBuffer: 64 * 1024 * 1024, env: process.env })
  let json = null
  const text = res.stdout || ''
  const start = text.indexOf('{')
  if (start !== -1) { try { json = JSON.parse(text.slice(start)) } catch { json = null } }
  return { status: res.status, signal: res.signal, error: res.error ? String(res.error.code || res.error.message) : null, stdout: text, stderr: res.stderr || '', json }
}

// Parse the companion's result envelope without launching anything. Exported
// for offline verification against a saved result.json.
export function parseResultPayload(json) {
  const job = json && typeof json === 'object' && json.job && typeof json.job === 'object' ? json.job : null
  const stored = json && typeof json === 'object' && json.storedJob && typeof json.storedJob === 'object' ? json.storedJob : null
  const payload = stored && stored.result && typeof stored.result === 'object' ? stored.result : null
  const jobStatus = job && typeof job.status === 'string' ? job.status : null
  const resultStatus = payload && payload.status !== undefined ? payload.status : null
  return {
    job_status: jobStatus,
    result_status: resultStatus,
    thread_id: (job && job.threadId) || (stored && stored.threadId) || (payload && payload.threadId) || null,
    turn_id: (job && job.turnId) || (stored && stored.turnId) || null,
    touched_files: payload ? payload.touchedFiles || null : null,
    raw_output: payload && typeof payload.rawOutput === 'string' ? payload.rawOutput : null,
    raw_output_chars: payload && typeof payload.rawOutput === 'string' ? payload.rawOutput.length : null,
    success: jobStatus === 'completed' && resultStatus === 0,
  }
}

// Compact stdout projection. `??` keeps a successful numeric 0 result_status;
// `||` would turn it into null.
export function projectEnvelope(envelope, jobId, outDir) {
  return {
    outcome: envelope.outcome,
    job_id: jobId ?? null,
    thread_id: envelope.thread_id ?? null,
    job_status: envelope.job_status ?? null,
    result_status: envelope.result_status ?? null,
    touched_files: envelope.touched_files ?? null,
    elapsed_ms: envelope.elapsed_ms ?? null,
    out_dir: outDir,
  }
}

function main(argv) {
  const companion = resolveCompanion()
  if (argv.includes('--print-companion')) { console.log(companion ? JSON.stringify(companion) : 'null'); process.exit(companion ? 0 : 2) }
  if (!companion) { console.error('codex companion not found'); process.exit(2) }
  if (argv.includes('--write')) { console.error('refusing --write: this lane is read-only'); process.exit(2) }
  const promptFile = opt(argv, '--prompt-file', null)
  if (!promptFile) {
    console.error('usage: codex-cross-review.mjs --print-companion | --prompt-file <file> --out-dir <dir> [--timeout-sec N] [--model M] [--effort E]')
    process.exit(2)
  }
  const outDir = resolve(opt(argv, '--out-dir', '.'))
  mkdirSync(outDir, { recursive: true })
  const timeoutSec = parseInt(opt(argv, '--timeout-sec', '600'), 10) || 600
  const passthrough = []
  for (const flag of ['--model', '--effort']) { const v = opt(argv, flag, null); if (v) passthrough.push(flag, v) }
  const started = Date.now()
  const envelope = { companion, prompt_file: resolve(promptFile), out_dir: outDir, timeout_sec: timeoutSec, steps: {} }

  // 1. start a tracked background task (read-only: no --write)
  const start = runJson(companion, ['task', '--background', '--json', '--fresh', ...passthrough, '--prompt-file', resolve(promptFile)], 120000)
  envelope.steps.start = { status: start.status, error: start.error, stderr_head: start.stderr.slice(0, 300) }
  const jobId = start.json && (start.json.jobId || (start.json.job && start.json.job.id))
  if (!jobId) {
    envelope.steps.start.stdout_head = start.stdout.slice(0, 500)
    envelope.outcome = 'start_failed'
    writeFileSync(join(outDir, 'envelope.json'), JSON.stringify(envelope, null, 2) + '\n')
    process.stdout.write(JSON.stringify({ outcome: envelope.outcome, job_id: null, out_dir: outDir }) + '\n')
    process.exit(1)
  }
  envelope.job_id = jobId

  // 2. wait for a terminal state through the companion's own poller
  const wait = runJson(companion, ['status', jobId, '--wait', '--timeout-ms', String(timeoutSec * 1000), '--json'], timeoutSec * 1000 + 30000)
  envelope.steps.wait = { status: wait.status, error: wait.error, wait_timed_out: wait.json ? wait.json.waitTimedOut === true : null, job_status: wait.json && wait.json.job ? wait.json.job.status : null }
  writeFileSync(join(outDir, 'status.json'), wait.stdout || '')

  // 3. on timeout, request native cancel and record the terminal snapshot; never claim cleanup credit from the timeout itself
  if (!wait.json || wait.json.waitTimedOut === true) {
    const cancel = runJson(companion, ['cancel', jobId, '--json'], 60000)
    envelope.steps.cancel = { status: cancel.status, error: cancel.error, stdout_head: cancel.stdout.slice(0, 300) }
    const after = runJson(companion, ['status', jobId, '--json'], 60000)
    envelope.steps.after_cancel = { job_status: after.json && after.json.job ? after.json.job.status : null }
    envelope.outcome = 'timed_out_cancel_requested'
  } else {
    // 4. retrieve the persisted result. Companion 1.0.6 `result --json` returns
    // { job, storedJob }; the task payload lives at storedJob.result
    // ({ status, threadId, rawOutput, touchedFiles, reasoningSummary }).
    const result = runJson(companion, ['result', jobId, '--json'], 120000)
    envelope.steps.result = { status: result.status, error: result.error }
    writeFileSync(join(outDir, 'result.json'), result.stdout || '')
    const parsed = parseResultPayload(result.json)
    Object.assign(envelope, parsed)
    if (typeof parsed.raw_output === 'string') writeFileSync(join(outDir, 'codex-output.md'), parsed.raw_output)
    delete envelope.raw_output
    envelope.outcome = result.status === 0 && parsed.success ? 'completed:success' : 'unsuccessful:' + (parsed.job_status || 'unknown') + ':' + (parsed.result_status === null ? 'no-payload' : String(parsed.result_status))
  }
  envelope.elapsed_ms = Date.now() - started
  writeFileSync(join(outDir, 'envelope.json'), JSON.stringify(envelope, null, 2) + '\n')
  process.stdout.write(JSON.stringify(projectEnvelope(envelope, jobId, outDir)) + '\n')
  process.exit(envelope.outcome.startsWith('completed:') ? 0 : 1)
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])
if (isMain) main(process.argv.slice(2))
