export const meta = {
  name: 'landscape-sweep',
  description: 'Saturation sweep of the due landscape layers: Claude Opus + GPT-6-Astra discovery, facts/fit refuters (two-family fit), completeness critic, one bounded follow-up round',
  whenToUse: 'recipes/saturation-sweep.md, run as tools/sota-convergence/landscape-sweep/README.md describes: launch the embedded-args copy build_args.py writes (or this file with its args.json), then convert the run with convert.py',
  phases: [
    { title: 'Discover', detail: 'discover:<layer> (Claude Opus max) + gpt6-discover:<layer> (gpt-6-astra max, web search)' },
    { title: 'Refute', detail: 'refute-facts:<layer> (Sonnet max), refute-fit:<layer> (Opus max), gpt6-refute-fit:<layer>' },
    { title: 'Critic', detail: 'completeness critic (Opus max), at most 8 follow-up layers' },
    { title: 'Follow-up', detail: 'bounded follow-up round with the same roles' },
  ],
}

// args, as build_args.py writes them (W/args.json, or embedded in W/sweep.embedded.js in place of the line below):
//   S         absolute work directory, outside every repository: inputs/<layer_id>.json (build_inputs.py), the
//             staged codex_call.sh, codex_job.py, make_prompt.py, templates.json and schemas/, prompts/, gpt6/
//   stars     absolute path of extract_layers.py's star-candidates.json, or null (no stars note)
//   sweep_id  lane name, e.g. 'landscape-sweep-20260926'; returned as `sweep` ('<sweep_id>-smoke' when test)
//   T         the frozen, dated templates {common, discover, facts, fit, critic, followup}; the run's prompts_sha256
//             is sha256(json.dumps(T, sort_keys=True, ensure_ascii=False)), written to W/prompts_sha256.txt
//   schemas   {discover, votes, critic}: the strict return schemas (skills_used included)
//   layers    [{layer_id, catalog}] in sweep order; the first-round GPT-6 prompts W/prompts/gpt6-discover-<id>.txt
//             are already written
//   test      optional; true returns after the first round (the one-layer smoke run)
// Worker labels follow recipes/saturation-sweep.md, so scripts/saturation_ledger.py --check reconciles them with
// the child-usage output: discover:<layer>, refute-facts:<layer>, refute-fit:<layer> (':followup' appended in the
// follow-up round); the GPT-6 wrappers are gpt6-discover:<layer> and gpt6-refute-fit:<layer>; the critic is critic.
const A = args
const MAX_PROPOSALS = 8
const MAX_FOLLOWUPS = 8
const TEMPLATE_KEYS = ['common', 'discover', 'facts', 'fit', 'critic', 'followup']
const WRAP_SCHEMA = { type: 'object', additionalProperties: false, required: ['result_json'], properties: { result_json: { type: 'string' } } }
const LABEL_RANK = { targeted_candidate: 0, keep_but_compare: 1, not_adopted: 2 }

const nonblank = (v) => typeof v === 'string' && v.length > 0
const issues = []
if (!A || typeof A !== 'object') issues.push('args must be the object build_args.py writes')
else {
  if (!nonblank(A.S) || !A.S.startsWith('/')) issues.push('S must be the absolute work directory')
  if (!nonblank(A.sweep_id)) issues.push('sweep_id is required')
  if (A.stars != null && !nonblank(A.stars)) issues.push('stars must be a path or null')
  if (!A.T || TEMPLATE_KEYS.some((k) => !nonblank(A.T[k]))) issues.push('T must hold the templates ' + TEMPLATE_KEYS.join(', '))
  if (!A.schemas || ['discover', 'votes', 'critic'].some((k) => !A.schemas[k] || typeof A.schemas[k] !== 'object')) issues.push('schemas must hold discover, votes and critic')
  const ids = Array.isArray(A.layers) ? A.layers.map((L) => (L && nonblank(L.layer_id) && nonblank(L.catalog) ? L.layer_id : null)) : []
  if (!ids.length || ids.includes(null) || new Set(ids).size !== ids.length) issues.push('layers must be a nonempty list of distinct {layer_id, catalog}')
}
if (issues.length) { for (const i of issues) log('argument issue: ' + i); return { status: 'incomplete', argument_issues: issues } }
const T = A.T
const S = A.S

// One pass over <<NAME>> placeholders; a function replacement, so '$&' or '<<X>>' inside a value is never expanded.
function fill(template, values) {
  return template.replace(/<<([A-Z_]+)>>/g, (m, k) => (Object.prototype.hasOwnProperty.call(values, k) ? String(values[k]) : m))
}
function slug(u) {
  const m = /github\.com\/([^/#?\s]+\/[^/#?\s]+)/i.exec(u || '')
  return m ? m[1].replace(/\.git$/i, '').toLowerCase() : String(u || '').toLowerCase()
}
function inputPath(lid) { return `${S}/inputs/${lid}.json` }

function claudeDiscoverPrompt(L, fu) {
  const stars = A.stars ? `Also scan the user's GitHub stars, classified in ${A.stars} (star_candidates[] with repository, role, decision, layers; beyond_stars[]), for anything relevant to this layer. Use gh api (Bash) for GitHub facts and WebSearch/WebFetch (load them via ToolSearch) for docs and changelogs.` : ''
  let body = fill(T.discover, { LAYER_INPUT: `Read the layer input JSON file with the Read tool: ${inputPath(L.layer_id)}`, STARS_NOTE: stars, LAYER_ID: L.layer_id })
  if (fu) body += '\n' + fill(T.followup, { CRITIC_REASON: fu.reason, DIRECTIONS: fu.search_directions.join('; '), ALREADY: fu.already.join(', ') })
  return T.common + '\n\n' + body
}

function wrapperPrompt(job, steps, promptFile, schema) {
  return `You run one GPT-6 (Codex CLI) job for a sweep and return its raw result. Do exactly these steps and nothing else; do not interpret the output.\n${steps}\nThen run: bash ${S}/codex_call.sh start ${job} ${promptFile} ${S}/schemas/${schema}.json\n` +
    `Then run \`bash ${S}/codex_call.sh wait ${job} 540\` with the Bash tool (timeout 600000 ms) repeatedly until it prints a line starting with "done" (at most 8 times).\n` +
    `Then run \`bash ${S}/codex_call.sh result ${job}\` and return its complete stdout, unmodified, as result_json. If any step fails, still run the result command and return its stdout.`
}

async function gpt6Discover(L, suffix, fu, phaseName) {
  const job = `gpt6-discover-${L.layer_id}${suffix}`
  let steps, promptFile
  if (fu) {
    promptFile = `${S}/prompts/${job}.txt`
    steps = `1. Use the Write tool to create ${S}/gpt6/fu-${L.layer_id}.json with exactly this content:\n${JSON.stringify(fu)}\n` +
      `2. Run: python3 ${S}/make_prompt.py discover ${inputPath(L.layer_id)} - ${S}/gpt6/fu-${L.layer_id}.json > ${promptFile}\n` +
      `Prompt file: ${promptFile} ; schema: discover`
  } else {
    promptFile = `${S}/prompts/gpt6-discover-${L.layer_id}.txt`
    steps = `Prompt file: ${promptFile} ; schema: discover (no preparation step).`
  }
  const r = await agent(wrapperPrompt(job, steps, promptFile, 'discover'),
    { label: `gpt6-discover:${L.layer_id}${suffix ? ':followup' : ''}`, phase: phaseName, model: 'sonnet', effort: 'max', schema: WRAP_SCHEMA })
  return parseWrapped(r)
}

async function gpt6Fit(L, suffix, proposals, phaseName) {
  const job = `gpt6-fit-${L.layer_id}${suffix}`
  const promptFile = `${S}/prompts/${job}.txt`
  const steps = `1. Use the Write tool to create ${S}/gpt6/props-${L.layer_id}${suffix}.json with exactly this content:\n${JSON.stringify(proposals)}\n` +
    `2. Run: python3 ${S}/make_prompt.py fit ${inputPath(L.layer_id)} ${S}/gpt6/props-${L.layer_id}${suffix}.json > ${promptFile}\n` +
    `Prompt file: ${promptFile} ; schema: votes`
  const r = await agent(wrapperPrompt(job, steps, promptFile, 'votes'),
    { label: `gpt6-refute-fit:${L.layer_id}${suffix ? ':followup' : ''}`, phase: phaseName, model: 'sonnet', effort: 'max', schema: WRAP_SCHEMA })
  return parseWrapped(r)
}

function parseWrapped(r) {
  if (!r || typeof r.result_json !== 'string') return { status: 'lost', output: null }
  let meta
  try { meta = JSON.parse(r.result_json) } catch (e) { return { status: 'unparseable_wrapper', output: null, raw: r.result_json.slice(0, 2000) } }
  let output = null
  if (meta.output_text) { try { output = JSON.parse(meta.output_text) } catch (e) { output = null } }
  const out = { status: meta.exit === 0 && output ? 'ok' : `failed_exit_${meta.exit}`, output, usage: meta.usage, started: meta.started, finished: meta.finished, stderr_tail: output ? null : meta.stderr_tail }
  for (const k of ['model', 'effort', 'codex_version', 'limit']) if (meta[k] !== undefined) out[k] = meta[k]
  return out
}

// Merge both families' proposals by canonical repository; two-family proposals first, then by label. The full
// per-family returns stay in claude_discover / gpt6_discover, so a merged row keeps only the first family's fields.
function mergeProposals(claudeD, gptD) {
  const bySlug = new Map()
  const add = (p, fam) => {
    const k = slug(p.repository)
    if (!k) return
    if (!bySlug.has(k)) bySlug.set(k, { ...p, families: [fam] })
    else { const e = bySlug.get(k); if (!e.families.includes(fam)) e.families.push(fam) }
  }
  for (const p of (claudeD && claudeD.proposed) || []) add(p, 'claude')
  for (const p of (gptD && gptD.proposed) || []) add(p, 'gpt6')
  const all = [...bySlug.values()].sort((a, b) =>
    (b.families.length - a.families.length) || ((LABEL_RANK[a.proposed_label] ?? 3) - (LABEL_RANK[b.proposed_label] ?? 3)))
  return { kept: all.slice(0, MAX_PROPOSALS), dropped: all.slice(MAX_PROPOSALS).map((p) => ({ repository: p.repository, families: p.families, proposed_label: p.proposed_label })) }
}

function forRefuters(kept) {
  return kept.map((p) => ({ repository: p.repository, proposed_label: p.proposed_label, demonstrated_gap: p.demonstrated_gap,
    comparison_that_would_overturn: p.comparison_that_would_overturn, evidence: p.evidence, upstream_now: p.upstream_now, proposed_by: p.families }))
}

async function runLayer(L, fu, phaseD, phaseR) {
  const suffix = fu ? '-followup' : ''
  const lsuf = fu ? ':followup' : ''
  const [cd, gd] = await parallel([
    () => agent(claudeDiscoverPrompt(L, fu), { label: `discover:${L.layer_id}${lsuf}`, phase: phaseD, model: 'opus', effort: 'max', schema: A.schemas.discover }),
    () => gpt6Discover(L, suffix, fu, phaseD),
  ])
  const { kept, dropped } = mergeProposals(cd, gd && gd.output)
  if (dropped.length) log(`${L.layer_id}${lsuf}: ${dropped.length} proposal(s) beyond the cap of ${MAX_PROPOSALS} dropped: ${dropped.map((d) => d.repository).join(', ')}`)
  let facts = null, fitC = null, fitG = null
  if (kept.length) {
    const props = JSON.stringify(forRefuters(kept), null, 1)
    ;[facts, fitC, fitG] = await parallel([
      () => agent(T.common + '\n\n' + fill(T.facts, { LAYER_ID: L.layer_id, REQUIREMENT: `see ${inputPath(L.layer_id)} (Read tool)`, PROPOSALS: props }) + '\nUse gh api (Bash) for GitHub facts and WebFetch/WebSearch (via ToolSearch) for docs.',
        { label: `refute-facts:${L.layer_id}${lsuf}`, phase: phaseR, model: 'sonnet', effort: 'max', schema: A.schemas.votes }),
      () => agent(T.common + '\n\n' + fill(T.fit, { LAYER_INPUT: `Read the layer input JSON file with the Read tool: ${inputPath(L.layer_id)}`, PROPOSALS: props, LAYER_ID: L.layer_id }) + '\nUse gh api (Bash) and WebFetch/WebSearch (via ToolSearch) as needed.',
        { label: `refute-fit:${L.layer_id}${lsuf}`, phase: phaseR, model: 'opus', effort: 'max', schema: A.schemas.votes }),
      () => gpt6Fit(L, suffix, forRefuters(kept), phaseR),
    ])
  }
  return { layer_id: L.layer_id, catalog: L.catalog, round: fu ? 'followup' : 'first', followup_reason: fu || null,
    claude_discover: cd, gpt6_discover: gd, merged: kept, dropped, facts, fit_claude: fitC, fit_gpt6: fitG }
}

phase('Discover')
const first = await pipeline(A.layers, (L) => runLayer(L, null, 'Discover', 'Refute'))
const firstOk = first.map((r, i) => r || { layer_id: A.layers[i].layer_id, catalog: A.layers[i].catalog, round: 'first', lost: true })
const lostFirst = firstOk.filter((r) => r.lost).map((r) => r.layer_id)
if (lostFirst.length) log(`first round lost layers: ${lostFirst.join(', ')}`)
if (A.test) return { sweep: `${A.sweep_id}-smoke`, first: firstOk, lost_first: lostFirst }

phase('Critic')
const summary = firstOk.map((r) => ({ layer_id: r.layer_id, catalog: r.catalog, lost: !!r.lost,
  proposed: (r.merged || []).map((p) => `${p.repository} [${p.proposed_label}; by ${p.families.join('+')}]`),
  facts_refuted: ((r.facts && r.facts.votes) || []).filter((v) => v.refuted).map((v) => v.repository),
  fit_refuted_claude: ((r.fit_claude && r.fit_claude.votes) || []).filter((v) => v.refuted).map((v) => v.repository),
  fit_refuted_gpt6: ((r.fit_gpt6 && r.fit_gpt6.output && r.fit_gpt6.output.votes) || []).filter((v) => v.refuted).map((v) => v.repository),
  gpt6_discover_status: r.gpt6_discover ? r.gpt6_discover.status : 'none' }))
const critic = await agent(T.common + '\n\n' + fill(T.critic, { SUMMARY: `Layer inputs are files ${S}/inputs/<layer_id>.json (Read tool). Summary JSON:\n` + JSON.stringify(summary, null, 1) }),
  { label: 'critic', phase: 'Critic', model: 'opus', effort: 'max', schema: A.schemas.critic })
const named = (critic && critic.followup_layers) || []
const unknown = named.filter((f) => !A.layers.some((x) => x.layer_id === f.layer_id)).map((f) => String(f.layer_id))
if (unknown.length) log(`critic named layers outside this sweep, ignored: ${unknown.join(', ')}`)
const known = named.filter((f) => A.layers.some((x) => x.layer_id === f.layer_id))
const flagged = known.slice(0, MAX_FOLLOWUPS)
if (known.length > MAX_FOLLOWUPS) log(`critic flagged ${known.length} layers; only the first ${MAX_FOLLOWUPS} get a follow-up round: ${known.slice(MAX_FOLLOWUPS).map((f) => f.layer_id).join(', ')} dropped`)
log(`follow-up layers: ${flagged.map((f) => f.layer_id).join(', ') || 'none'}`)

phase('Follow-up')
const follow = await pipeline(flagged, (f) => {
  const L = A.layers.find((x) => x.layer_id === f.layer_id)
  const r0 = firstOk.find((x) => x.layer_id === f.layer_id)
  const fu = { reason: f.reason, search_directions: f.search_directions, already: ((r0 && r0.merged) || []).map((p) => p.repository) }
  return runLayer(L, fu, 'Follow-up', 'Follow-up')
})

return { sweep: A.sweep_id, first: firstOk, critic, followups: follow, lost_first: lostFirst }
