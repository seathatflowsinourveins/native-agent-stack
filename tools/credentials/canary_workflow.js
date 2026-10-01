export const meta = {
  name: 'canary-workflow-child',
  description: 'Canary proof workflow-child consumer: one child runs the id-only probe command through the credential runner, a second checks the entry state by id',
  whenToUse: 'Only in the canary proof window, after `canary_proof.py arm --run RUN workflow-child`; args = {run: "cp-...", attempt: N}',
  phases: [
    { title: 'Probe', detail: 'Sonnet/max child runs the emitted probe command once', model: 'sonnet' },
    { title: 'Status', detail: 'Sonnet/max child checks the entry state by id, value-free', model: 'sonnet' },
  ],
}

const a = args && typeof args === 'object' ? args : {}
const run = typeof a.run === 'string' && /^cp-\d{8}t\d{6}z-[0-9a-f]{6}$/.test(a.run) ? a.run : null
const attempt = Number.isInteger(a.attempt) && a.attempt > 0 ? a.attempt : null
const RESULT = { type: 'object', properties: { exit_code: { type: ['integer', 'null'] }, printed_tag_line: { type: 'boolean' } }, required: ['exit_code', 'printed_tag_line'] }
const RULES = '\nRun nothing else, write no file, and never print or echo an environment value.'
if (run && attempt) {
  const probe = 'python3 -I tools/credentials/credential_run.py canary-e2e -- python3 -I tools/credentials/canary_probe.py --run ' + run + ' --consumer workflow-child --attempt ' + attempt
  phase('Probe')
  // The scout role runs the one command a task names (examples/claude-native/workflows/README.md, dispatch by role).
  const first = await agent('Run exactly this command once with the Bash tool from the repository root, then report its exit code and whether it printed a line that starts "canary-probe workflow-child": ' + probe + RULES,
    { label: 'probe', phase: 'Probe', schema: RESULT, agentType: 'source-scout', model: 'sonnet', effort: 'max' })
  phase('Status')
  const second = await agent('Run exactly this command once with the Bash tool from the repository root, then report its exit code and set printed_tag_line to false: python3 -I tools/credentials/credential_run.py canary-e2e --check' + RULES,
    { label: 'status', phase: 'Status', schema: RESULT, agentType: 'source-scout', model: 'sonnet', effort: 'max' })
  log('probe exit ' + (first ? first.exit_code : 'null') + '; status exit ' + (second ? second.exit_code : 'null'))
} else {
  log('canary-workflow-child needs args.run (a cp- run id) and args.attempt (a positive integer); nothing ran')
}
