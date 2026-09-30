export const meta = {
  name: 'frozen-check-judge',
  description: 'Judge the class D clauses of the #381 token E2E frozen checks for the Codex-family answers: for every packet (one answer with its clauses, source excerpts and extraction requests, scrubbed of identities) a blind judge decides each clause on verbatim quotes, then a refuter tries to refute every passing judgment; the script writes nothing and never grades anything - grade.py judge collect verifies the quotes, audits the transcripts and assembles the judgments',
  whenToUse: 'After grade.py judge packets and judge claude-args: args = {repo: "<judge export root>", items: [{name, path, packet_sha256}], prompt: "<judge-template.md text with its <!-- refuter --> section>", snapshot_id: "<claude-args snapshot>"}; feed the return to grade.py judge collect',
  phases: [
    { title: 'Judge', detail: 'blind reviewer per packet, Opus at max effort, leak check first, then one verdict per clause and the requested extractions' },
    { title: 'Refute', detail: 'blind reviewer per passing judgment, Opus at max effort, leak check first, then tries to refute the pass with a verbatim quote' },
  ],
}
const a = args && typeof args === 'object' ? args : {}
const issues = []
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const REPO = nonblank(a.repo) ? a.repo : '.'
const MARKER = '<!-- refuter -->'
const PROMPT = nonblank(a.prompt) && a.prompt.includes(MARKER) ? a.prompt : null
if (!PROMPT) issues.push('prompt must be the judge-template.md text, with its ' + MARKER + ' section')
const validItem = (i) => i && typeof i === 'object' && nonblank(i.name) && nonblank(i.path) && /^[0-9a-f]{64}$/.test(i.packet_sha256 || '')
const items = Array.isArray(a.items) ? a.items.filter(validItem) : []
if (!items.length) issues.push('items must be a nonempty array of {name, path, packet_sha256}')
if (issues.length) { for (const i of issues) log('argument issue: ' + i); return { status: 'incomplete', argument_issues: issues } }
const [JUDGE_TEMPLATE, REFUTE_TEMPLATE] = [PROMPT.split(MARKER)[0].trim(), PROMPT.split(MARKER).slice(1).join(MARKER).trim()]
// Every agent() call below names its role, model and effort literally; collect records this pair, which is what the
// calls bind, not a resolved child model.
const MODEL = { name: "opus", effort: "max" }
// The same properties as judgment.schema.json and judge.REFUTATION_SCHEMA, every field typed and every object closed,
// so the schemas also satisfy strict structured output.
const STR = { type: 'string' }
const BOOL = { type: 'boolean' }
const STRS = { type: 'array', items: STR }
const CLAUSE = { type: 'object', properties: { id: STR, holds: BOOL, answer_quote: STR, source_quote: STR }, required: ['id', 'holds', 'answer_quote', 'source_quote'], additionalProperties: false }
const EXTRACTION = { type: 'object', properties: { component: STR, values: STRS, answer_quotes: STRS }, required: ['component', 'values', 'answer_quotes'], additionalProperties: false }
const JUDGE = { type: 'object', properties: { clauses: { type: 'array', items: CLAUSE }, extractions: { type: 'array', items: EXTRACTION }, leak: BOOL, leak_text: STR }, required: ['clauses', 'extractions', 'leak', 'leak_text'], additionalProperties: false }
const REFUTE = { type: 'object', properties: { refuted: BOOL, reason: STR, quote: STR, leak: BOOL, leak_text: STR }, required: ['refuted', 'reason', 'quote', 'leak', 'leak_text'], additionalProperties: false }
const BLIND = 'Blind rule: read only the packet file named in the labelled line below, with the Read tool. Do not open any other file, checkout, work directory, memory store, code index, session history or web page, and do not try to identify which model, tool or arm wrote the answer. Do the leak check first.'
// The labelled line is what transcript_audit maps each agent to its packet by.
const block = (i) => 'Packet file: ' + i.path + '\nRepository root: ' + REPO
const fill = (t, i, judgment) => t.split('{PACKET_BLOCK}').join(block(i)).split('{JUDGMENT}').join(judgment ? JSON.stringify(judgment) : '')
// A leak answer is never a judgment: collect records it as unknown(judge_leak).
const leakOf = (v, stage) => v && typeof v === 'object' && v.leak === true ? { stage, text: typeof v.leak_text === 'string' && v.leak_text.trim() ? v.leak_text : '(no leak text given)' } : null
const judgeOk = (v) => v && typeof v === 'object' && Array.isArray(v.clauses) && Array.isArray(v.extractions) && typeof v.leak === 'boolean' && typeof v.leak_text === 'string'
const refuteOk = (v) => v && typeof v === 'object' && typeof v.refuted === 'boolean' && typeof v.reason === 'string' && typeof v.quote === 'string'
// A pass has at least one clause and holds every one. Only a pass is refuted (the grading block's refute setting is passes_only).
const passed = (v) => v.clauses.length > 0 && v.clauses.every((c) => c && c.holds === true)
// Every returned item echoes the path and packet hash it consumed: collect requires them to be the ones claude-args gave,
// so edited arguments cannot pass under the snapshot.
const echo = (i) => ({ name: i.name, packet_sha256: i.packet_sha256, path: i.path })
const chain = async (i) => {
  const got = await agent(BLIND + '\n' + fill(JUDGE_TEMPLATE, i), { label: 'judge:' + i.name, phase: 'Judge', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'max', schema: JUDGE }).catch(() => null)
  const judgeLeak = leakOf(got, 'judge')
  if (judgeLeak) return { ...echo(i), judge: null, refuter: null, leak: judgeLeak }
  const judge = judgeOk(got) ? { clauses: got.clauses, extractions: got.extractions, leak: false, leak_text: '' } : null
  if (!judge || !passed(judge)) return { ...echo(i), judge, refuter: null }
  const vote = await agent(BLIND + '\n' + fill(REFUTE_TEMPLATE, i, judge), { label: 'refute:' + i.name, phase: 'Refute', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'max', schema: REFUTE }).catch(() => null)
  const refuteLeak = leakOf(vote, 'refuter')
  if (refuteLeak) return { ...echo(i), judge, refuter: null, leak: refuteLeak }
  const refuter = refuteOk(vote) ? { refuted: vote.refuted, reason: vote.reason, quote: vote.quote, leak: false, leak_text: '' } : null
  return { ...echo(i), judge, refuter }
}
// One chain per packet (judge, then refuter) through parallel(): no barrier between packets. A lost or malformed agent
// leaves null, and collect records that item as unavailable, never as unrefuted.
const results = await parallel(items.map((i) => () => chain(i).catch(() => null)))
const out = items.map((i, n) => (Array.isArray(results) && results[n]) || { ...echo(i), judge: null, refuter: null })
log(`items: ${out.length}, ${out.filter((r) => r.judge).length} judged, ${out.filter((r) => r.refuter).length} refuter votes, ${out.filter((r) => r.refuter && r.refuter.refuted).length} refuted, ${out.filter((r) => r.leak).length} leak refusals`)
// The claude-args snapshot these items came from and the prompt text they consumed, echoed so collect binds this result to them.
return { family: 'anthropic', model: MODEL, repo: REPO, prompt: PROMPT, snapshot_id: typeof a.snapshot_id === 'string' ? a.snapshot_id : null, items: out }
