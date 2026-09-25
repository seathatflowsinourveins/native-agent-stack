export const meta = {
  name: 'readiness-audit',
  description: 'Extract source-cited claims from named documents and commands with Sonnet readers, then adversarially verify them with an Opus verifier',
  whenToUse: 'Status or readiness questions over project records: args = {docs: ["path", ...], commands: ["read-only command", ...], question: "what to judge"}',
  phases: [
    { title: 'Read', detail: 'Sonnet/max readers, one per document group', model: 'sonnet' },
    { title: 'Verify', detail: 'Opus/max verifier refutes or confirms every claim', model: 'opus' },
  ],
}

const a = args && typeof args === 'object' ? args : {}
const docs = Array.isArray(a.docs) ? a.docs.filter((d) => typeof d === 'string') : []
const commands = Array.isArray(a.commands) ? a.commands.filter((c) => typeof c === 'string') : []
const question = typeof a.question === 'string' && a.question ? a.question : 'How ready is the described work, and what is the single blocking gate?'
if (!docs.length && !commands.length) {
  log('readiness-audit needs args.docs or args.commands; nothing to read')
  return { status: 'incomplete', reason: 'no source documents or commands supplied', claims: [], verify: null, question }
}

// Shared worker packet: byte-identical in every saved workflow (test-envelope.mjs asserts it).
const PACKET = [
  'Worker packet contract: bounded objective, only the listed sources, no writes except what an acceptance command named in your task itself produces, return only the schema.',
  'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
].join(' ')

const CLAIMS = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    claims: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, source: { type: 'string' }, confidence: { type: 'string', enum: ['high', 'medium', 'low'] } }, required: ['claim', 'source', 'confidence'] } },
    open_gates: { type: 'array', items: { type: 'string' } },
    not_found: { type: 'array', items: { type: 'string' } },
    sources: { type: 'array', items: { type: 'object', properties: { source: { type: 'string' }, outcome: { type: 'string', enum: ['observed', 'not_found', 'not_executed'] }, evidence: { type: 'string' }, exit_code: { type: ['integer', 'null'] } }, required: ['source', 'outcome', 'evidence', 'exit_code'] } },
  },
  required: ['summary', 'claims', 'open_gates', 'not_found', 'sources'],
}
// Each reader can report only its assigned identifiers, even when the overall
// question mentions sources owned by another packet. Runtime coverage checks
// still reject duplicates or omitted evidence after structured output returns.
const claimsForPacket = (items) => ({
  ...CLAIMS,
  properties: {
    ...CLAIMS.properties,
    not_found: { ...CLAIMS.properties.not_found, items: { type: 'string', enum: items } },
    sources: {
      ...CLAIMS.properties.sources,
      minItems: items.length,
      maxItems: items.length,
      items: {
        ...CLAIMS.properties.sources.items,
        properties: { ...CLAIMS.properties.sources.items.properties, source: { type: 'string', enum: items } },
      },
    },
  },
})

const VERIFY = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'refuted', 'corrected', 'unverifiable'] }, evidence: { type: 'string' }, correction: { type: 'string' } }, required: ['claim', 'verdict', 'evidence'] } },
    missing: { type: 'array', description: 'Only exact requested source identifiers that are unavailable or unverified; independently established extra facts belong in readiness_verdict.', items: { type: 'string' } },
    readiness_verdict: { type: 'string' },
    source_verdicts: { type: 'array', items: { type: 'object', properties: { packet_id: { type: 'string' }, source: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'refuted', 'unverifiable'] }, evidence: { type: 'string' } }, required: ['packet_id', 'source', 'verdict', 'evidence'] } },
  },
  required: ['verdicts', 'missing', 'readiness_verdict', 'source_verdicts'],
}

// Group documents into at most three reader packets; commands form their own packet.
const groups = []
const perGroup = Math.max(1, Math.ceil(docs.length / 3))
for (let i = 0; i < docs.length; i += perGroup) groups.push({ kind: 'docs', items: docs.slice(i, i + perGroup) })
if (commands.length) groups.push({ kind: 'commands', items: commands })
if (groups.length > 3) log('more than three reader packets requested; running ' + groups.length + ' with the concurrency cap')

phase('Read')
const readers = await parallel(groups.map((g, i) => () => agent(
  PACKET + '\nCurrent packet: ' + g.kind + '-' + (i + 1) + '. Authorized source identifiers: ' + JSON.stringify(g.items) + '. Access and report only this packet\'s sources. The overall question is relevance context, not permission to access or report sources assigned to another packet.\nOverall question (relevance context only): ' + question + '\n' +
  (g.kind === 'docs'
    ? 'Read these documents fully and extract every claim relevant to the question: ' + g.items.join(', ')
    : 'Run these read-only commands exactly and report their returned results as claims: ' + g.items.join(' ; ')) +
  '\nReturn exactly one sources entry for each listed document or command, copying its identifier exactly into source. Mark observed only after reading the document or receiving the command result, with nonblank returned evidence; observed command failures are evidence and must retain their integer exit_code. Use null exit_code for documents or commands not executed. Record unavailable documents as not_found and commands you did not run as not_executed. Never silently omit a requested source.',
  { label: 'read:' + g.kind + '-' + (i + 1), phase: 'Read', schema: claimsForPacket(g.items), agentType: 'source-scout', model: 'sonnet', effort: 'max' },
)))
// Preserve every packet identity, including failed/null readers, so an unread
// source cannot vanish from the verdict.
const packets = groups.map((g, i) => ({ id: g.kind + '-' + (i + 1), kind: g.kind, items: g.items, result: readers[i] || null }))
const unread = packets.filter((p) => p.result === null)
if (unread.length) log(unread.length + ' reader packet(s) returned null; unread sources: ' + unread.map((p) => p.items.join(', ')).join(' | '))
const claims = packets.flatMap((p) => (p.result ? p.result.claims : []))
log('claims extracted: ' + claims.length + ' from ' + (packets.length - unread.length) + '/' + packets.length + ' packets')

phase('Verify')
const verify = await agent(
  PACKET + '\nYou are an adversarial verifier. Open every cited source yourself and try to REFUTE each claim; default to unverifiable when you cannot. Return exactly one verdict for every reader claim, copying its claim string exactly, with nonblank evidence. Include a nonblank correction for corrected claims. Also return one source_verdicts entry for each requested packet item, copying packet_id and source exactly: independently confirm the returned source evidence and command outcome, including nonzero exits; use unverifiable if you cannot establish it. Emit only the exact (packet.id, item) pairs listed in each packet.items; never copy extra result.sources entries or combine one packet id with another packet\'s item. Packets whose result is null were NOT read: list their sources under missing and do not treat the audit as complete. The missing field is only for exact requested source identifiers that are unavailable or unverified. Put independently established additional facts the readers missed, with their evidence, in readiness_verdict; these are not missing sources. Then answer the question in readiness_verdict with the single most blocking gate and its evidence. A complete audit may conclude that the project is not ready.\nQuestion: ' + question + '\nReader packets (result null = unread): ' + JSON.stringify(packets),
  { label: 'verify', phase: 'Verify', schema: VERIFY, model: 'opus', effort: 'max' },
)
if (!verify) log('verifier returned null; claims are unverified')
const evidenceIssues = []
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const claimCounts = new Map()
for (const item of claims) {
  if (!item || !nonblank(item.claim) || !nonblank(item.source)) {
    evidenceIssues.push('reader claim or source is blank')
    continue
  }
  claimCounts.set(item.claim, (claimCounts.get(item.claim) || 0) + 1)
}
for (const [claim, count] of claimCounts) if (count !== 1) evidenceIssues.push('duplicate reader claim: ' + claim)
const validVerify = verify && Array.isArray(verify.verdicts) && Array.isArray(verify.missing) && nonblank(verify.readiness_verdict)
if (!validVerify) evidenceIssues.push('verifier returned null or an invalid envelope')
const verdicts = validVerify ? verify.verdicts : []
const verdictCounts = new Map()
for (const verdict of verdicts) {
  if (!verdict || !nonblank(verdict.claim) || !nonblank(verdict.evidence) || !['confirmed', 'refuted', 'corrected', 'unverifiable'].includes(verdict.verdict) || (verdict.verdict === 'corrected' && !nonblank(verdict.correction))) {
    evidenceIssues.push('verdict has a blank claim/evidence/correction or invalid decision')
    continue
  }
  if (!claimCounts.has(verdict.claim)) evidenceIssues.push('verdict does not exactly match a reader claim: ' + verdict.claim)
  verdictCounts.set(verdict.claim, (verdictCounts.get(verdict.claim) || 0) + 1)
}
for (const [claim] of claimCounts) if (verdictCounts.get(claim) !== 1) evidenceIssues.push('claim needs exactly one valid verdict: ' + claim)
for (const [claim, count] of verdictCounts) if (count !== 1) evidenceIssues.push('duplicate verdict: ' + claim)
const missingSources = [
  ...unread.flatMap((p) => p.items),
  ...packets.flatMap((p) => p.result && Array.isArray(p.result.not_found) ? p.result.not_found : []),
  ...(validVerify ? verify.missing : []),
]
// A nonnull packet can still omit a document or command. Account for every
// requested identifier and independently verify the returned source evidence.
const sourceKey = (packetId, source) => JSON.stringify([packetId, source])
const expectedSources = new Set()
for (const packet of packets) {
  const returned = packet.result && Array.isArray(packet.result.sources) ? packet.result.sources : []
  for (const source of packet.items) {
    const key = sourceKey(packet.id, source)
    if (expectedSources.has(key)) evidenceIssues.push('duplicate requested source: ' + key)
    expectedSources.add(key)
    const entries = returned.filter((r) => r && r.source === source)
    if (!nonblank(source) || entries.length !== 1 || !nonblank(entries[0].evidence) || entries[0].outcome !== 'observed' || (packet.kind === 'commands' && !Number.isInteger(entries[0].exit_code))) {
      missingSources.push(source)
      evidenceIssues.push('source needs exactly one observed result with evidence and a command exit code where applicable: ' + key)
    }
  }
  for (const entry of returned) if (!entry || !packet.items.includes(entry.source)) evidenceIssues.push('returned source is not a requested packet item: ' + packet.id)
}
const sourceVerdicts = verify && Array.isArray(verify.source_verdicts) ? verify.source_verdicts : []
const sourceVerdictCounts = new Map()
for (const verdict of sourceVerdicts) {
  const key = verdict && sourceKey(verdict.packet_id, verdict.source)
  if (!verdict || !expectedSources.has(key) || !nonblank(verdict.evidence) || verdict.verdict !== 'confirmed') {
    evidenceIssues.push('source verification is missing, mismatched, refuted or unverifiable: ' + key)
    continue
  }
  sourceVerdictCounts.set(key, (sourceVerdictCounts.get(key) || 0) + 1)
}
for (const key of expectedSources) if (sourceVerdictCounts.get(key) !== 1) evidenceIssues.push('source needs exactly one evidenced confirmation: ' + key)
// "Complete" describes the audit's evidence coverage, never project readiness.
// Supported refutations, corrections and open gates may complete a negative audit.
const status = !validVerify ? 'unverified' : missingSources.length || evidenceIssues.length ? 'incomplete' : verdicts.some((v) => v.verdict === 'unverifiable') ? 'unverified' : 'complete'
return { question, status, unread_sources: unread.flatMap((p) => p.items), missing_sources: missingSources, evidence_issues: evidenceIssues, packets, verify }
