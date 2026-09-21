export const meta = {
  name: 'review-changes',
  description: 'Inventory a diff with a Sonnet worker, then have an Opus reviewer independently verify correctness against original source',
  whenToUse: 'Before integrating a bounded change: args = {base: "<git ref>", paths: ["optional", "scope"], checks: ["optional acceptance commands"]}',
  phases: [
    { title: 'Inventory', detail: 'Sonnet/medium: changed files, behavior, checks run', model: 'sonnet' },
    { title: 'Review', detail: 'Opus/high: refute or confirm each claimed behavior from source', model: 'opus' },
  ],
}

const a = args && typeof args === 'object' ? args : {}
const base = typeof a.base === 'string' && a.base ? a.base : 'HEAD'
const paths = Array.isArray(a.paths) ? a.paths.filter((p) => typeof p === 'string') : []
const checks = Array.isArray(a.checks) ? a.checks.filter((c) => typeof c === 'string') : []
const scope = paths.length ? paths.join(' ') : '(whole working tree)'

const PACKET = [
  'Worker packet contract: bounded objective, the listed source paths only, read-only effects, return only the schema.',
  'Cite every claim with file path and line or the exact command. Copy numbers exactly. Never claim token savings.',
  'Preserve failures, empty results and uncertainty as such; do not restate them as passes.',
  'Context lanes (MCP tools are inherited by workflow agents; call them directly, or load a schema with ToolSearch when it is deferred): Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact.',
].join(' ')

const INVENTORY = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    files: { type: 'array', items: { type: 'object', properties: { path: { type: 'string' }, change: { type: 'string' } }, required: ['path', 'change'] } },
    changed_behavior: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, source: { type: 'string' } }, required: ['claim', 'source'] } },
    checks_run: { type: 'array', items: { type: 'object', properties: { command: { type: 'string' }, exit: { type: 'string' }, result: { type: 'string' } }, required: ['command', 'exit', 'result'] } },
  },
  required: ['summary', 'files', 'changed_behavior', 'checks_run'],
}

const REVIEW = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'refuted', 'corrected', 'unverifiable'] }, evidence: { type: 'string' }, correction: { type: 'string' } }, required: ['claim', 'verdict', 'evidence'] } },
    defects: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, line: { type: 'string' }, defect: { type: 'string' }, evidence: { type: 'string' } }, required: ['file', 'defect', 'evidence'] } },
    gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdicts', 'defects', 'gaps'],
}

phase('Inventory')
const inventory = await agent(
  PACKET + '\nInventory the change in the current repository. Base ref: ' + base + '. Scope: ' + scope + '.\n' +
  'Run: git status --short; git diff --stat ' + base + ' -- ' + (paths.length ? paths.join(' ') : '.') + '; git diff ' + base + ' -- ' + (paths.length ? paths.join(' ') : '.') + ' (read what changed, including untracked files in scope).\n' +
  (checks.length ? 'Then run each acceptance command exactly as given, without pipelines that mask exit status, and record exactly one checks_run entry per command with the command string copied verbatim, its exit code and concise exact output quoted in result. Copy deterministic passed/failed summaries verbatim; never eyeball or recount test totals. Explicitly record if a command produced no output: ' + checks.join(' ; ') + '\n' : 'No acceptance commands were supplied; record checks_run as empty.\n') +
  'Describe the in-scope changed behavior with source-cited claims. If there is no change to review, return no claims rather than inventing one; the coordinator will mark the no-op incomplete. Return the schema only.',
  { label: 'inventory', phase: 'Inventory', schema: INVENTORY, model: 'sonnet', effort: 'medium' },
)
if (!inventory) {
  log('inventory worker returned null; stopping without a review')
  return { status: 'incomplete', accepted: false, reason: 'inventory stage returned null', inventory: null, review: null, base, scope }
}
log('inventory: ' + inventory.files.length + ' files, ' + inventory.changed_behavior.length + ' behavior claims, ' + inventory.checks_run.length + ' checks')

phase('Review')
const review = await agent(
  PACKET + '\nYou are an independent reviewer. Try to REFUTE each behavior claim below by reading the original source and the diff against ' + base + ' yourself. Return exactly one verdict for every changed_behavior claim, copying its claim string exactly, with nonblank evidence. Default to unverifiable when you cannot open the cited source. Report concrete defects with file and line. List verification gaps. A corrected or refuted behavior claim requires coordinator resolution before acceptance.\n' +
  'Requested scope: ' + scope + '. Requested acceptance commands: ' + JSON.stringify(checks) + '. Independently inspect the evidence for these commands. Record material unresolved gaps affecting the in-scope behavior or required checks, including missing evidence. Excluded files and disclosed general limitations are not themselves gaps; explain a concrete effect on this requested scope before treating them as one. Preserve every supported in-scope finding.\n' +
  'Inventory: ' + JSON.stringify(inventory),
  { label: 'review', phase: 'Review', schema: REVIEW, model: 'opus', effort: 'high' },
)
if (!review) log('review worker returned null; inventory is unreviewed')
// Acceptance requires complete claim coverage as well as checks and review.
// A completed model call, empty defects list, or corrected claim is not acceptance.
const evidenceIssues = []
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const failedChecks = inventory.checks_run.filter((c) => c && nonblank(c.exit) && c.exit.trim() !== '0')
// Exact, unique command identity and nonblank returned evidence are required;
// duplicate or empty results cannot satisfy a requested check.
const requestedCheckCounts = new Map()
for (const command of checks) {
  if (!nonblank(command)) evidenceIssues.push('requested check command is blank')
  requestedCheckCounts.set(command, (requestedCheckCounts.get(command) || 0) + 1)
}
for (const [command, count] of requestedCheckCounts) if (count !== 1) evidenceIssues.push('duplicate requested check: ' + command)
const returnedCheckCounts = new Map()
for (const check of inventory.checks_run) {
  if (!check || !nonblank(check.command) || !nonblank(check.exit) || !nonblank(check.result)) evidenceIssues.push('returned check needs a nonblank command, exit and result')
  if (check && nonblank(check.command)) returnedCheckCounts.set(check.command, (returnedCheckCounts.get(check.command) || 0) + 1)
}
for (const [command, count] of returnedCheckCounts) if (count !== 1) evidenceIssues.push('duplicate returned check result: ' + command)
const missingChecks = checks.filter((command) => {
  const matches = inventory.checks_run.filter((r) => r && r.command === command)
  return !nonblank(command) || matches.length !== 1 || !nonblank(matches[0].exit) || !nonblank(matches[0].result)
})
if (!inventory.changed_behavior.length) evidenceIssues.push('no source-cited changed behavior was supplied; a no-op is not an accepted change review')
const claimCounts = new Map()
for (const item of inventory.changed_behavior) {
  if (!item || !nonblank(item.claim) || !nonblank(item.source)) {
    evidenceIssues.push('inventory claim or source is blank')
    continue
  }
  claimCounts.set(item.claim, (claimCounts.get(item.claim) || 0) + 1)
}
for (const [claim, count] of claimCounts) if (count !== 1) evidenceIssues.push('duplicate inventory claim: ' + claim)
const validReview = review && Array.isArray(review.verdicts) && Array.isArray(review.defects) && Array.isArray(review.gaps)
if (!validReview) evidenceIssues.push('review stage returned null or an invalid envelope')
const verdicts = validReview ? review.verdicts : []
const verdictCounts = new Map()
for (const verdict of verdicts) {
  if (!verdict || !nonblank(verdict.claim) || !nonblank(verdict.evidence) || !['confirmed', 'refuted', 'corrected', 'unverifiable'].includes(verdict.verdict)) {
    evidenceIssues.push('verdict has a blank claim/evidence or invalid decision')
    continue
  }
  if (!claimCounts.has(verdict.claim)) evidenceIssues.push('verdict does not exactly match an inventory claim: ' + verdict.claim)
  verdictCounts.set(verdict.claim, (verdictCounts.get(verdict.claim) || 0) + 1)
}
for (const [claim] of claimCounts) if (verdictCounts.get(claim) !== 1) evidenceIssues.push('claim needs exactly one valid verdict: ' + claim)
for (const [claim, count] of verdictCounts) if (count !== 1) evidenceIssues.push('duplicate verdict: ' + claim)
const unresolvedClaims = verdicts.filter((v) => v && v.verdict !== 'confirmed')
const rejectedClaims = unresolvedClaims.filter((v) => ['refuted', 'corrected'].includes(v.verdict))
const gaps = validReview ? review.gaps : []
const defects = validReview ? review.defects : []
const status = failedChecks.length || defects.length || rejectedClaims.length ? 'rejected' : missingChecks.length || evidenceIssues.length || unresolvedClaims.length || gaps.length ? 'incomplete' : 'accepted'
const reasons = [
  ...failedChecks.map((c) => 'failed check: ' + c.command),
  ...missingChecks.map((c) => 'requested check without exactly one evidenced result: ' + c),
  ...evidenceIssues,
  ...unresolvedClaims.map((v) => 'unresolved ' + v.verdict + ' claim: ' + v.claim),
  ...(defects.length ? [defects.length + ' defect(s) reported'] : []),
  ...(gaps.length ? [gaps.length + ' verification gap(s) reported'] : []),
]
const reason = reasons.length ? reasons.join(' ; ') : 'every behavior claim independently confirmed with evidence, all requested checks returned exit 0, no defects or verification gaps'
log('review-changes status: ' + status + ' (' + reason + ')')
return { status, accepted: status === 'accepted', reason, requested_checks: checks, missing_checks: missingChecks, evidence_issues: evidenceIssues, unresolved_claims: unresolvedClaims, inventory, review, base, scope }
