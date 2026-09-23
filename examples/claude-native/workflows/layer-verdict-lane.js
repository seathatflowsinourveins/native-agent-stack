export const meta = {
  name: 'layer-verdict-lane',
  description: 'Run the Claude lane of the layer-verdict convergence: for every stripped layer packet an Opus proposer selects the winner set on retained evidence, two Opus refuters (evidence lens, challenger lens) attack it, one revision round follows any refutation; the script writes nothing and never promotes a candidate - the record tool applies the rules',
  whenToUse: 'After tools/sota-convergence/lane_packets.py wrote the packets: args = {repo: "<catalog checkout>", packets: [{catalog, layer_id, path, sha256}], prompt: "<lane-prompt.md text with {PACKET_PATH} {REPO_ROOT} {LANE} placeholders>", model?: {name: "opus", effort: "high"} (optional; a different value is logged and returned as caller_model, never applied, because every agent() call binds that literal)}',
  phases: [
    { title: 'Propose', detail: 'semantic-evidence-reviewer per packet, Opus high, Read/Glob/Grep only', model: 'opus' },
    { title: 'Refute', detail: 'evidence lens + challenger lens per proposal, Opus high', model: 'opus' },
    { title: 'Revise', detail: 'one revision when any lens refutes, Opus high', model: 'opus' },
  ],
}
const a = args && typeof args === 'object' ? args : {}
const issues = []
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const REPO = nonblank(a.repo) ? a.repo : '.'
const PROMPT = nonblank(a.prompt) ? a.prompt : 'You are the {LANE} lane. Read the packet at {PACKET_PATH} under {REPO_ROOT} and return the schema object.'
const validPacket = (p) => p && typeof p === 'object' && nonblank(p.catalog) && nonblank(p.layer_id) && nonblank(p.path) && /^[0-9a-f]{64}$/.test(p.sha256 || '')
const docs = Array.isArray(a.docs) ? a.docs.filter((d) => typeof d === 'string' && d.trim()) : []
// Degenerate mode (envelope/contract runs): with no packets, each given doc is treated as a foundation packet with a zero hash; the record tool rejects such a return by its packet hash.
const packets = Array.isArray(a.packets) && a.packets.length ? a.packets.filter(validPacket) : docs.map((d, i) => ({ catalog: 'foundation', layer_id: 'unnamed-' + i, path: d, sha256: '0'.repeat(64) }))
if (!packets.length) issues.push('packets must be a nonempty array of {catalog, layer_id, path, sha256}')
// Every agent() call below binds the literal model 'opus' / effort 'high' (the contract suite requires inline alias
// literals), so the recorded model is that same literal and args.model cannot re-route the lane.
const MODEL = { name: 'opus', effort: 'high' }
// A caller-supplied model is not applied (it cannot be); it is logged and returned as caller_model so the record stays truthful.
const CALLER_MODEL = a.model !== undefined && !(a.model && typeof a.model === 'object' && a.model.name === MODEL.name && a.model.effort === MODEL.effort) ? a.model : null
if (CALLER_MODEL) log('args.model ' + JSON.stringify(CALLER_MODEL) + ' is not applied: every agent() call binds ' + JSON.stringify(MODEL))
if (issues.length) { for (const i of issues) log('argument issue: ' + i); return { status: 'incomplete', argument_issues: issues } }
const PACKET = [
  'Worker packet contract: bounded objective, only the listed sources, no writes except what an acceptance command named in your task itself produces, return only the schema.',
  'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
].join(' ')
const ALT = { type: 'object', properties: { key: { type: ['string', 'null'] }, name: { type: 'string' }, repository: { type: 'string', pattern: '^https://[^ ;,]+$' }, disposition: { type: 'string', enum: ['selected', 'observed_failure', 'measured_tradeoff', 'overlap', 'out_of_scope', 'unqualified', 'conditional'] }, why_not_default: { type: 'string' }, evidence_class: { type: 'string', enum: ['native_proven', 'local_integration', 'synthetic', 'source_review', 'measured_comparison'] }, evidence_refs: { type: 'array', items: { type: 'string' } } }, required: ['key', 'name', 'repository', 'disposition', 'why_not_default', 'evidence_class', 'evidence_refs'] }
const LANE_RETURN = { type: 'object', properties: {
  schema_version: { type: 'integer', enum: [1] }, lane: { type: 'string', enum: ['claude'] }, catalog: { type: 'string', enum: ['foundation', 'us-equities'] }, layer_id: { type: 'string' }, packet_sha256: { type: 'string' },
  model: { type: 'object', properties: { name: { type: 'string' }, effort: { type: 'string' } }, required: ['name', 'effort'] },
  winner_keys: { type: 'array', items: { type: 'string' }, minItems: 1, maxItems: 3 },
  why_selected: { type: 'string' }, winner_evidence_class: { type: 'string', enum: ['native_proven', 'local_integration', 'synthetic', 'source_review', 'measured_comparison'] }, winner_evidence_refs: { type: 'array', items: { type: 'string' } },
  alternatives: { type: 'array', items: ALT, minItems: 1 },
  challenger_preferred: { type: ['object', 'null'], properties: { key: { type: ['string', 'null'] }, name: { type: 'string' }, repository: { type: 'string', pattern: '^https://[^ ;,]+$' }, why: { type: 'string' }, required_comparison: { type: 'string' } }, required: ['key', 'name', 'repository', 'why', 'required_comparison'] },
  overturn_when: { type: 'string' }, overturn_protocol: { type: 'object', properties: { fixture_paths: { type: 'array', items: { type: 'string' } }, metric: { type: 'string' }, arms: { type: 'array', items: { type: 'string' } } }, required: ['fixture_paths', 'metric', 'arms'] },
  open_gaps: { type: 'array', items: { type: 'string' } }, sources_read: { type: 'array', items: { type: 'string' } }, limits: { type: 'array', items: { type: 'string' } } },
  required: ['schema_version', 'lane', 'catalog', 'layer_id', 'packet_sha256', 'model', 'winner_keys', 'why_selected', 'winner_evidence_class', 'winner_evidence_refs', 'alternatives', 'challenger_preferred', 'overturn_when', 'overturn_protocol', 'open_gaps', 'sources_read', 'limits'] }
const VOTE = { type: 'object', properties: { refuted: { type: 'boolean' }, findings: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, evidence: { type: 'string' }, severity: { type: 'string', enum: ['blocking', 'major', 'minor'] } }, required: ['claim', 'evidence', 'severity'] } }, paths_checked: { type: 'array', items: { type: 'string' } } }, required: ['refuted', 'findings', 'paths_checked'] }
const fill = (p) => PROMPT.split('{PACKET_PATH}').join(p.path).split('{REPO_ROOT}').join(REPO).split('{LANE}').join('claude')
const fixed = (p) => `\nFixed values you must copy exactly: schema_version 1, lane "claude", catalog "${p.catalog}", layer_id "${p.layer_id}", packet_sha256 "${p.sha256}", model {"name": "${MODEL.name}", "effort": "${MODEL.effort}"}. Read files only under ${REPO}; you cannot run commands, so verify a path exists by opening it. winner_keys, alternatives[].key and challenger_preferred.key are the packet's candidate keys (c1, c2, ...).`
const lensPrompt = (p, proposal, lens) => PACKET + '\n' + (lens === 'evidence'
  ? `Evidence lens. Try to refute this layer-verdict proposal for packet ${p.path} (repository root ${REPO}): ${JSON.stringify(proposal)}. Open every path in winner_evidence_refs, alternatives[].evidence_refs and sources_read; a path that does not exist or does not support the claim made about it is a blocking finding. Check that every packet candidate with adopted == true that is not a winner appears in alternatives (missing one is blocking), that every winner key is adopted (else blocking), that why_selected reports an observed result rather than a project claim, that overturn_when names a fixtures/, blueprints/ or tests/ path or a python3/node command that exists or is runnable, and that no number or result is stated without a cited path. refuted = true if any blocking finding. Do not edit anything.`
  : `Challenger lens. Try to refute this layer-verdict proposal for packet ${p.path} (repository root ${REPO}): ${JSON.stringify(proposal)}. Read the packet's requirement and the evidence_refs of the strongest non-winner candidate(s), adopted or not. Argue that one of them satisfies the requirement at least as well as the winner set on the retained evidence. refuted = true only when the cited evidence shows that (name the paths), or when a stated why_not_default is contradicted by its own evidence; a stronger candidate that is not adopted must have been recorded in challenger_preferred (its absence is a major finding, not a refutation of the winner). Do not edit anything.`)
// One chain per packet (propose -> refute -> revise), run through parallel(): no barrier between
// packets, and the contract suite's parallel stub reaches every stage.
const chain = async (p) => {
  const proposal = await agent(PACKET + '\n' + fill(p) + fixed(p), { label: `propose:${p.catalog}/${p.layer_id}`, phase: 'Propose', agentType: 'semantic-evidence-reviewer', model: 'opus', effort: 'high', schema: LANE_RETURN })
  if (!proposal) return { catalog: p.catalog, layer_id: p.layer_id, packet_sha256: p.sha256, proposal: null, votes: [], revised: null, final: null }
  const votes = (await parallel(['evidence', 'challenger'].map((lens) => () =>
    agent(lensPrompt(p, proposal, lens), { label: `refute:${lens}:${p.catalog}/${p.layer_id}`, phase: 'Refute', agentType: 'evidence-reviewer', model: 'opus', effort: 'high', schema: VOTE }).then((v) => v && { lens, ...v })))).filter(Boolean)
  const refuted = votes.filter((v) => v.refuted)
  const majors = votes.flatMap((v) => (v.findings || []).filter((f) => f.severity !== 'minor'))
  if (!refuted.length && !majors.length) return { catalog: p.catalog, layer_id: p.layer_id, packet_sha256: p.sha256, proposal, votes, revised: null, final: proposal }
  const revised = await agent(PACKET + '\n' + fill(p) + fixed(p) + `\nThis is the revision round. Your earlier proposal was: ${JSON.stringify(proposal)}. Independent refuters found: ${JSON.stringify(votes)}. Resolve every blocking and major finding by re-reading the cited evidence; keep what the evidence supports, drop or correct what it does not, and add what was missing. Return the complete revised object.`, { label: `propose:revise:${p.catalog}/${p.layer_id}`, phase: 'Revise', agentType: 'semantic-evidence-reviewer', model: 'opus', effort: 'high', schema: LANE_RETURN })
  return { catalog: p.catalog, layer_id: p.layer_id, packet_sha256: p.sha256, proposal, votes, revised, final: revised || proposal }
}
const results = await parallel(packets.map((p) => () => chain(p)))
const out = results.filter(Boolean)
const lost = packets.filter((p) => !out.find((r) => r.catalog === p.catalog && r.layer_id === p.layer_id)).map((p) => `${p.catalog}/${p.layer_id}`)
log(`layers: ${out.length} returned, ${out.filter((r) => r.revised).length} revised, ${out.filter((r) => !r.final).length} without a proposal, ${lost.length} lost`)
return { lane: 'claude', model: MODEL, caller_model: CALLER_MODEL, model_note: 'model is the literal alias/effort bound by every agent() call in this lane, not an observed identity; read the resolved model per child from node .claude/workflows/child-usage.mjs --latest (on Claude Code >= 2.1.280 the opus alias resolves to claude-opus-5-5)', layers: out, lost }
