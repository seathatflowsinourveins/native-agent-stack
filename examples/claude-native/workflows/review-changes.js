export const meta = {
  name: 'review-changes',
  description: 'Inventory a diff with a Sonnet worker, have an Opus reviewer independently verify it against original source, and reproduce the acceptance commands with a second worker',
  whenToUse: 'Before integrating a bounded change: args = {base: "<git ref>", paths: ["optional", "scope"], checks: ["optional acceptance commands"]}',
  phases: [
    { title: 'Inventory', detail: 'Sonnet/medium: changed files, behavior, checks run', model: 'sonnet' },
    { title: 'Review', detail: 'Opus/high: refute or confirm each claimed behavior from source', model: 'opus' },
    { title: 'Recheck', detail: 'Sonnet/medium: a second worker re-runs the acceptance commands; the script compares exit codes', model: 'sonnet' },
  ],
}

const a = args && typeof args === 'object' ? args : {}
const base = typeof a.base === 'string' && a.base ? a.base : 'HEAD'
const stringList = (v) => Array.isArray(v) && v.every((x) => typeof x === 'string' && x.trim())
const paths = stringList(a.paths) ? a.paths : []
const checks = stringList(a.checks) ? a.checks : []
// An argument that is present but malformed must not silently shrink the requirements.
const argumentIssues = []
if (a.paths !== undefined && !stringList(a.paths)) argumentIssues.push('paths must be an array of nonblank strings')
if (paths.some((p) => p.trim().startsWith('/'))) argumentIssues.push('paths must be repository-relative, not absolute')
if (a.checks !== undefined && !stringList(a.checks)) argumentIssues.push('checks must be an array of nonblank strings')
const scope = paths.length ? paths.join(' ') : '(whole working tree)'

// Shared worker packet: byte-identical in every saved workflow (test-envelope.mjs asserts it).
const PACKET = [
  'Worker packet contract: bounded objective, only the listed sources, no writes except what an acceptance command named in your task itself produces, return only the schema.',
  'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
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
  'Run: git status --short --untracked-files=all -- ' + (paths.length ? paths.join(' ') : '.') + '; git diff --stat ' + base + ' -- ' + (paths.length ? paths.join(' ') : '.') + '; git diff ' + base + ' -- ' + (paths.length ? paths.join(' ') : '.') + ' (read what changed, and Read every untracked in-scope file the status lists, since git diff does not show them; give each one a files entry and source-cited claims; every files[].path is repository-relative, never absolute).\n' +
  (checks.length ? 'Acceptance commands to run, ' + checks.length + ' in total, one per line below. Run each exactly as written, without pipelines that mask exit status, and record exactly one checks_run entry per command with the command string copied verbatim, its exit code and concise exact output quoted in result. Copy deterministic passed/failed summaries verbatim; never eyeball or recount test totals; record explicitly when a command produced no output.\n' + checks.map((c) => '- ' + c).join('\n') + '\n' : 'No acceptance commands were supplied; record checks_run as empty.\n') +
  'Describe the in-scope changed behavior with source-cited claims. If there is no change to review, return no claims rather than inventing one; the coordinator will mark the no-op incomplete. Return the schema only.',
  { label: 'inventory', phase: 'Inventory', schema: INVENTORY, agentType: 'source-scout', model: 'sonnet', effort: 'medium' },
)
if (!inventory) {
  log('inventory worker returned null; stopping without a review')
  return { status: 'incomplete', accepted: false, reason: 'inventory stage returned null', inventory: null, review: null, base, scope }
}
log('inventory: ' + inventory.files.length + ' files, ' + inventory.changed_behavior.length + ' behavior claims, ' + inventory.checks_run.length + ' checks')

const RECHECK = { type: 'object', properties: { checks_run: INVENTORY.properties.checks_run }, required: ['checks_run'] }
// The reviewer is read-only, so a second worker reproduces the acceptance commands and the
// script compares the two runs; one worker's self-report is never accepted on its own.
phase('Review')
const [review, recheck] = await parallel([() => agent(
  PACKET + '\nYou are an independent reviewer. Try to REFUTE each behavior claim below by reading the original source and the diff against ' + base + ' yourself (your role has no Bash: open changed files with Read, and obtain the diff with Context Mode ctx_execute, language shell, with cwd set to the repository root, running git diff ' + base + ' -- ' + (paths.length ? paths.join(' ') : '.') + ' and printing only the hunks you need; that diff omits untracked files, so also run git status --short --untracked-files=all -- ' + (paths.length ? paths.join(' ') : '.') + ' the same way (it lists each file inside a new directory) and Read every untracked in-scope file in full). When Context Mode is not among your tools, Read every file the inventory lists in full and judge each claim from that source; a claim that can only be settled by the diff is then unverifiable. Return exactly one verdict for every changed_behavior claim, copying its claim string exactly, with nonblank evidence. Default to unverifiable when you cannot open the cited source. Report concrete defects with file and line. List verification gaps. A corrected or refuted behavior claim requires coordinator resolution before acceptance.\n' +
  'Requested scope: ' + scope + '. Requested acceptance commands: ' + JSON.stringify(checks) + '. Inspect the recorded evidence for these commands against the source (for example that a quoted total is consistent with the test file it came from) and report any inconsistency as a defect. Do not execute acceptance commands: they are caller-supplied and may write, your role is read-only, and a separate recheck stage re-runs them and the script compares both runs, so not having re-run them is not a gap. Use ctx_execute only for the git diff and git status reads named above. Record material unresolved gaps affecting the in-scope behavior or required checks, including missing evidence. Excluded files and disclosed general limitations are not themselves gaps; explain a concrete effect on this requested scope before treating them as one. Preserve every supported in-scope finding.\n' +
  'Inventory: ' + JSON.stringify(inventory),
  { label: 'review', phase: 'Review', schema: REVIEW, agentType: 'evidence-reviewer', model: 'opus', effort: 'high' },
), () => (checks.length ? agent(
  PACKET + '\nIndependent reproduction of acceptance commands for the change in scope ' + scope + '. You have not seen any earlier result and must not look for one. From the repository root run each command below exactly as given, without pipelines that mask exit status, and record exactly one checks_run entry per command with the command string copied verbatim, its exit code and the concise exact summary output quoted in result. Copy deterministic passed/failed summaries verbatim; never recount totals. Record explicitly when a command produced no output. Commands, ' + checks.length + ' in total, one per line:\n' + checks.map((c) => '- ' + c).join('\n'),
  { label: 'recheck', phase: 'Recheck', schema: RECHECK, agentType: 'source-scout', model: 'sonnet', effort: 'medium' },
) : Promise.resolve(null))])
if (!review) log('review worker returned null; inventory is unreviewed')
// Acceptance requires complete claim coverage as well as checks and review.
// A completed model call, empty defects list, or corrected claim is not acceptance.
const evidenceIssues = [...argumentIssues]
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const failedChecks = inventory.checks_run.filter((c) => c && nonblank(c.exit) && c.exit.trim() !== '0')
// Exact, unique command identity and nonblank returned evidence are required;
// duplicate or empty results cannot satisfy a requested check.
const requestedCheckCounts = new Map()
for (const command of checks) requestedCheckCounts.set(command, (requestedCheckCounts.get(command) || 0) + 1)
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
// Independent reproduction: every requested command must appear exactly once in the recheck
// with the same exit code as the inventory run.
const recheckRuns = recheck && Array.isArray(recheck.checks_run) ? recheck.checks_run : null
if (checks.length && !recheckRuns) evidenceIssues.push('acceptance commands were not independently re-run (recheck stage returned null or an invalid envelope)')
const recheckCounts = new Map()
for (const entry of recheckRuns || []) {
  if (!entry || !nonblank(entry.command) || !nonblank(entry.exit) || !nonblank(entry.result)) { evidenceIssues.push('recheck entry needs a nonblank command, exit and result'); continue }
  if (!checks.includes(entry.command)) evidenceIssues.push('recheck entry for a command that was not requested: ' + entry.command)
  recheckCounts.set(entry.command, (recheckCounts.get(entry.command) || 0) + 1)
}
for (const [command, count] of recheckCounts) if (count !== 1) evidenceIssues.push('duplicate recheck result: ' + command)
// Deterministic totals quoted by both runs must agree; timings and free text are not compared.
const SUMMARIES = [/SUMMARY passed=\d+ failed=\d+ total=\d+/, /Ran \d+ tests?/, /\b\d+ (?:[a-z]+ ){0,4}passed\b/, /\b\d+ (?:[a-z]+ ){0,4}failed\b/]
const totals = (text) => SUMMARIES.flatMap((re) => [...String(text).matchAll(new RegExp(re.source, 'g'))].map((m) => m[0])).sort()
const summaryDiff = (a, b) => { const x = totals(a), y = totals(b); const missing = x.filter((t) => !y.includes(t)); return missing.length ? [missing.join(' | ') + ' quoted by the first run but absent from the second (' + (y.join(' | ') || 'none') + ')'] : [] }
for (const command of recheckRuns ? checks : []) {
  const again = recheckRuns.filter((r) => r && r.command === command)
  const first = inventory.checks_run.filter((r) => r && r.command === command)
  if (again.length !== 1 || !nonblank(again[0].exit) || !nonblank(again[0].result)) evidenceIssues.push('check not independently reproduced exactly once with evidence: ' + command)
  else if (first.length === 1 && nonblank(first[0].exit) && first[0].exit.trim() !== again[0].exit.trim()) evidenceIssues.push('check exit differs between the two runs (' + first[0].exit.trim() + ' vs ' + again[0].exit.trim() + '): ' + command)
  else if (first.length === 1 && summaryDiff(first[0].result, again[0].result).length) evidenceIssues.push('check summary differs between the two runs (' + summaryDiff(first[0].result, again[0].result).join(', ') + '): ' + command)
}
const failedRechecks = (recheckRuns || []).filter((c) => c && nonblank(c.exit) && c.exit.trim() !== '0')
// Every requested path needs at least one inventory entry at or under it, so a file the
// worker skipped (an untracked one, for instance) cannot be accepted unseen.
// Inventory paths must be repository-relative (the prompt asks for that); an absolute
// path could belong to another checkout, so it never counts as coverage.
const norm = (p) => String(p || '').replace(/^\.\//, '').replace(/\/+$/, '')
const inventoried = inventory.files.map((file) => norm(file && file.path)).filter((p) => p && !p.startsWith('/'))
const covers = (p, requested) => requested === '.' || p === requested || p.startsWith(requested + '/')
for (const requested of paths.filter((p) => !p.trim().startsWith('/')).map(norm)) if (!inventoried.some((p) => covers(p, requested))) evidenceIssues.push('requested path has no repository-relative inventory entry: ' + requested)
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
const status = failedChecks.length || failedRechecks.length || defects.length || rejectedClaims.length ? 'rejected' : missingChecks.length || evidenceIssues.length || unresolvedClaims.length || gaps.length ? 'incomplete' : 'accepted'
const reasons = [
  ...failedChecks.map((c) => 'failed check: ' + c.command),
  ...failedRechecks.map((c) => 'failed check on independent re-run: ' + c.command),
  ...missingChecks.map((c) => 'requested check without exactly one evidenced result: ' + c),
  ...evidenceIssues,
  ...unresolvedClaims.map((v) => 'unresolved ' + v.verdict + ' claim: ' + v.claim),
  ...(defects.length ? [defects.length + ' defect(s) reported'] : []),
  ...(gaps.length ? [gaps.length + ' verification gap(s) reported'] : []),
]
const reason = reasons.length ? reasons.join(' ; ') : 'every behavior claim independently confirmed with evidence, ' + (checks.length ? 'all requested checks returned exit 0 in two independent runs' : 'no acceptance commands were requested') + ', no defects or verification gaps'
log('review-changes status: ' + status + ' (' + reason + ')')
return { status, accepted: status === 'accepted', reason, requested_checks: checks, missing_checks: missingChecks, evidence_issues: evidenceIssues, unresolved_claims: unresolvedClaims, inventory, review, recheck, base, scope }
