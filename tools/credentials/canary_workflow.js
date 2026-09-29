export const meta = {
  name: 'canary-workflow-child',
  description: 'Key-management canary proof, workflow-child consumer: a probe stage runs the id-only probe through the key runner, then an independent verify stage checks its nonce-bound tag',
  whenToUse: 'Only inside a canary proof window, while `python3 tools/credentials/canary_e2e.py consume workflow-child --run <id>` waits (it arms the run and removes the store file afterwards): args = {run: "<id>"}',
  phases: [
    { title: 'Probe', detail: 'Sonnet/max source-scout: fetch and echo its own decoy, then run the probe through credential_run.py', model: 'sonnet' },
    { title: 'Verify', detail: 'Sonnet/max source-scout: canary_e2e.py verify for workflow-child', model: 'sonnet' },
  ],
}

// A unit plus its independent verification, so this is not a single agent wrapped in a workflow. Both stages take the
// command-wrapper role of the role table (examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26):
// source-scout runs the commands a task names and makes no edits. The decoy is fetched by the child itself, so the
// coordinator's transcript never holds it and cannot satisfy the workflow journals' control in its place.
const a = args && typeof args === 'object' ? args : {}
const RUN = /^canary-[0-9]{8}t[0-9]{6}z-[0-9a-f]{6}$/
if (typeof a.run !== 'string' || !RUN.test(a.run)) {
  return { status: 'refused', reason: 'args.run must be the run id that canary_e2e.py prepare printed' }
}
const run = a.run
const DECOY = 'python3 tools/credentials/canary_e2e.py decoy --run ' + run + ' --consumer workflow-child'
const PROBE = 'python3 -I tools/credentials/credential_run.py canary-e2e -- python3 -I tools/credentials/canary_probe.py --run ' + run + ' --consumer workflow-child'
const VERIFY = 'python3 tools/credentials/canary_e2e.py verify --run ' + run + ' --consumer workflow-child'

const PROBE_RESULT = {
  type: 'object',
  properties: { probe_line: { type: 'string' }, decoy_exit: { type: 'string' }, echo_exit: { type: 'string' }, probe_exit: { type: 'string' } },
  required: ['probe_line', 'decoy_exit', 'echo_exit', 'probe_exit'],
}
const VERIFY_RESULT = {
  type: 'object',
  properties: { verify_line: { type: 'string' }, verify_exit: { type: 'string' } },
  required: ['verify_line', 'verify_exit'],
}

phase('Probe')
const probed = await agent(
  'Automated canary probe of the key-management proof. From the repository root, run these Bash commands exactly, one at a time, and report only what the schema asks. Never print, search for or ask about any key or environment value.\n' +
  '1. ' + DECOY + '\n   It prints one line, "decoy workflow-child: <value>", and exits 1 on purpose.\n' +
  '2. echo <the value that command 1 printed after the colon> && false\n   This exits 1 on purpose too.\n' +
  '3. ' + PROBE + '\n' +
  'Return probe_line: the line that command 3 printed that starts with canary-probe; decoy_exit, echo_exit and probe_exit: the exit codes of commands 1, 2 and 3.',
  { label: 'probe', phase: 'Probe', schema: PROBE_RESULT, agentType: 'source-scout', model: 'sonnet', effort: 'max' },
)
if (!probed) return { status: 'incomplete', reason: 'probe stage returned null' }

phase('Verify')
const verified = await agent(
  'Independent check of a canary probe tag. From the repository root, run this Bash command exactly and report only what the schema asks:\n' + VERIFY + '\n' +
  'Return verify_line: its output line, and verify_exit: its exit code.',
  { label: 'verify', phase: 'Verify', schema: VERIFY_RESULT, agentType: 'source-scout', model: 'sonnet', effort: 'max' },
)
if (!verified) return { status: 'incomplete', reason: 'verify stage returned null', probe_exit: probed.probe_exit }
// Exit codes and the verify line only: the probe's tag line stays in the probe stage's own records.
return {
  status: verified.verify_exit === '0' ? 'verified' : 'not_verified',
  decoy_exit: probed.decoy_exit,
  echo_exit: probed.echo_exit,
  probe_exit: probed.probe_exit,
  verify_exit: verified.verify_exit,
  verify_line: verified.verify_line,
}
