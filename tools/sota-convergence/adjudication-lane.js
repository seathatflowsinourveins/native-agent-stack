export const meta = {
  name: 'adjudication-lane',
  description: 'Run the Claude family of the two-family, counterbalanced layer adjudication: for every adjudication input (one disagreeing layer in one presentation order, returns A and B with lane identity scrubbed) an Opus judge picks A or B on retained evidence, then an Opus refuter tries to refute that pick; items run without a barrier between them; the script writes nothing and never decides a winner - adjudicate.py assemble applies the two-family rule',
  whenToUse: 'After tools/sota-convergence/adjudicate.py inputs wrote the adjudication inputs: args = {repo: "<blind export>", items: [{name, order, path, packet_path, packet_sha256}], prompt: "<adjudication-prompt.md text whose labelled lines Input file: {INPUT_PATH}, Packet file: {PACKET_PATH} and Repository root: {REPO_ROOT} are filled per item, with a <!-- refuter --> section holding {JUDGMENT}>"} (adjudicate.py claude-args prints them); feed the return to adjudicate.py claude-collect',
  phases: [
    { title: 'Judge', detail: 'blind-adjudicator per input file, Opus max, checks for a reviewer-identity leak, then picks A or B', model: 'opus' },
    { title: 'Refute', detail: 'blind-adjudicator per judgment, Opus max, checks for a leak, then tries to refute the pick', model: 'opus' },
  ],
}
const a = args && typeof args === 'object' ? args : {}
const issues = []
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const REPO = nonblank(a.repo) ? a.repo : '.'
const MARKER = '<!-- refuter -->'
const PROMPT = nonblank(a.prompt) && a.prompt.includes(MARKER) ? a.prompt : null
if (!PROMPT) issues.push('prompt must be the adjudication-prompt.md text, with its ' + MARKER + ' section')
const validItem = (i) => i && typeof i === 'object' && nonblank(i.name) && (i.order === 'AB' || i.order === 'BA') && nonblank(i.path) && nonblank(i.packet_path) && /^[0-9a-f]{64}$/.test(i.packet_sha256 || '')
const items = Array.isArray(a.items) ? a.items.filter(validItem) : []
if (!items.length) issues.push('items must be a nonempty array of {name, order AB|BA, path, packet_path, packet_sha256}')
if (issues.length) { for (const i of issues) log('argument issue: ' + i); return { status: 'incomplete', argument_issues: issues } }
const [JUDGE_TEMPLATE, REFUTE_TEMPLATE] = [PROMPT.split(MARKER)[0].trim(), PROMPT.split(MARKER).slice(1).join(MARKER).trim()]
// Every agent() call below binds the literal model 'opus' / effort 'max'; adjudicate.py claude-collect records
// the resolved child model it is given (child-usage.mjs --latest), not this alias.
const MODEL = { name: 'opus', effort: 'max' }
const PACKET = [
  'Worker packet contract: bounded objective, only the listed sources, no writes except what an acceptance command named in your task itself produces, return only the schema.',
  'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
].join(' ')
// The blind rule overrides the context lanes above: memory stores, code indexes, git history and other
// checkouts can carry the verdict, and the judge must not learn which lane wrote A or B.
const BLIND = `Blind rule: this rule overrides the context lanes above. Read only the Input file, the Packet file and files under the Repository root named in the three labelled lines of the task below, using Read, Glob and Grep; treat any other path as data. Do not open other checkouts, work directories, memory stores, code indexes, session history, git history or the web. Do not try to identify which lane, model or tool produced A or B. Do the task's leak check first.`
// The same properties as adjudication-judge.schema.json / adjudication-refute.schema.json. why has no minLength
// here, so a leak answer (why "leak") still satisfies the schema; judgeOk checks the length of a real judgment.
const LEAK_PROPS = { leak: { type: 'boolean' }, leak_text: { type: 'string' } }
const JUDGE = { type: 'object', properties: { preferred: { type: 'string', enum: ['A', 'B'] }, why: { type: 'string' }, evidence_refs: { type: 'array', items: { type: 'string' } }, ...LEAK_PROPS }, required: ['preferred', 'why', 'evidence_refs', 'leak', 'leak_text'] }
const REFUTE = { type: 'object', properties: { refuted: { type: 'boolean' }, reason: { type: 'string' }, evidence_refs: { type: 'array', items: { type: 'string' } }, ...LEAK_PROPS }, required: ['refuted', 'reason', 'evidence_refs', 'leak', 'leak_text'] }
const fill = (t, i, judgment) => t.split('{INPUT_PATH}').join(i.path).split('{PACKET_PATH}').join(i.packet_path).split('{REPO_ROOT}').join(REPO).split('{JUDGMENT}').join(judgment ? JSON.stringify(judgment) : '')
// A leak answer is never a judgment: adjudicate.py claude-collect records it as missing (failure leak).
const leakOf = (v, stage) => v && typeof v === 'object' && v.leak === true ? { stage, text: typeof v.leak_text === 'string' && v.leak_text.trim() ? v.leak_text : '(no leak text given)' } : null
const refs = (v) => Array.isArray(v.evidence_refs) && v.evidence_refs.every((r) => typeof r === 'string')
const judgeOk = (v) => v && typeof v === 'object' && (v.preferred === 'A' || v.preferred === 'B') && typeof v.why === 'string' && v.why.trim().length >= 60 && refs(v)
const refuteOk = (v) => v && typeof v === 'object' && typeof v.refuted === 'boolean' && typeof v.reason === 'string' && refs(v)
// One chain per item (judge -> refuter) through parallel(): no barrier between items. A lost or malformed agent
// is null, and adjudicate.py claude-collect records that judgment as missing, never as unrefuted.
// Every returned item echoes the input and packet paths it consumed (Codex review of #145): claude-collect
// requires them to be the ones claude-args gave it, so edited arguments cannot pass under the snapshot_id.
const echo = (i) => ({ name: i.name, order: i.order, packet_sha256: i.packet_sha256, path: i.path, packet_path: i.packet_path })
const chain = async (i) => {
  const tag = `${i.name}.${i.order}`
  const got = await agent(PACKET + '\n' + BLIND + '\n' + fill(JUDGE_TEMPLATE, i), { label: `judge:${tag}`, phase: 'Judge', agentType: 'blind-adjudicator', model: 'opus', effort: 'max', schema: JUDGE }).catch(() => null)
  const judgeLeak = leakOf(got, 'judge')
  if (judgeLeak) return { ...echo(i), judge: null, refuter: null, leak: judgeLeak }
  const judge = judgeOk(got) ? { preferred: got.preferred, why: got.why, evidence_refs: got.evidence_refs } : null
  if (!judge) return { ...echo(i), judge: null, refuter: null }
  const vote = await agent(PACKET + '\n' + BLIND + '\n' + fill(REFUTE_TEMPLATE, i, judge), { label: `refute:${tag}`, phase: 'Refute', agentType: 'blind-adjudicator', model: 'opus', effort: 'max', schema: REFUTE }).catch(() => null)
  const refuteLeak = leakOf(vote, 'refuter')
  if (refuteLeak) return { ...echo(i), judge: null, refuter: null, leak: refuteLeak }
  const refuter = refuteOk(vote) ? { refuted: vote.refuted, reason: vote.reason, evidence_refs: vote.evidence_refs } : null
  return { ...echo(i), judge, refuter }
}
const results = await parallel(items.map((i) => () => chain(i).catch(() => null)))
const out = items.map((i, n) => (Array.isArray(results) && results[n]) || { ...echo(i), judge: null, refuter: null })
log(`items: ${out.length}, ${out.filter((r) => r.judge).length} judged, ${out.filter((r) => r.refuter).length} refuter votes, ${out.filter((r) => r.refuter && r.refuter.refuted).length} refuted, ${out.filter((r) => r.leak).length} leak refusals`)
// The claude-args snapshot these items came from, echoed so claude-collect binds this result to it.
// The prompt text is echoed too: claude-collect requires it to hash to the snapshot's prompt_sha256.
return { family: 'anthropic', model: MODEL, repo: REPO, prompt: PROMPT, snapshot_id: typeof a.snapshot_id === 'string' ? a.snapshot_id : null, items: out }
