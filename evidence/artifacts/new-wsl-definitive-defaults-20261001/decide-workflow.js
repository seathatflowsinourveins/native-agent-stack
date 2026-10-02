export const meta = {
  name: 'definitive-defaults-decision-round',
  description: 'Two blind deciders per contested slot name exactly one default for the new WSL; an adversarial critic re-checks the deciding facts',
  phases: [
    { title: 'Decide', detail: 'two independent stack-researchers (Opus, max) per slot, finalists in two seeded orders' },
    { title: 'Critique', detail: 'one adversarial stack-researcher (Opus, max) per slot re-checks deciding facts and agreement' },
  ],
}

const A = args
const packetPath = (slot, n) => `${A.packets_dir}/${slot}.order-${n}.json`

const DECISION = {
  type: 'object',
  properties: {
    slot_id: { type: 'string' },
    default: {
      type: 'object',
      properties: {
        key: { type: 'string' }, name: { type: 'string' }, repository: { type: 'string' },
        install_command: { type: 'string' }, install_source: { type: 'string' },
      },
      required: ['key', 'name', 'repository', 'install_command', 'install_source'],
    },
    decided_by_criterion: { type: 'string' },
    decided_on: { type: 'string', enum: ['measured_like_for_like', 'independent_evaluation', 'documented_fit', 'platform_and_install_fit', 'upstream_documented_dependency', 'no_install_baseline'] },
    could_not_separate: { type: 'boolean' },
    deciding_facts: { type: 'array', items: { type: 'object', properties: { fact: { type: 'string' }, url: { type: 'string' }, rechecked_now: { type: 'boolean' } }, required: ['fact', 'url', 'rechecked_now'] } },
    alternatives: { type: 'array', items: { type: 'object', properties: { key: { type: 'string' }, name: { type: 'string' }, reason: { type: 'string' } }, required: ['key', 'name', 'reason'] } },
    overturn_check: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    evidence_gaps: { type: 'array', items: { type: 'string' } },
    sources_read: { type: 'array', items: { type: 'string' } },
  },
  required: ['slot_id', 'default', 'decided_by_criterion', 'decided_on', 'could_not_separate', 'deciding_facts', 'alternatives', 'overturn_check', 'confidence', 'evidence_gaps', 'sources_read'],
}
const CRITIQUE = {
  type: 'object',
  properties: {
    slot_id: { type: 'string' },
    verdict: { type: 'string', enum: ['converged', 'revised', 'split'] },
    deciders_agree: { type: 'boolean' },
    default_after_review: { type: 'object', properties: { name: { type: 'string' }, repository: { type: 'string' } }, required: ['name', 'repository'] },
    checked_facts: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, url: { type: 'string' }, holds: { type: 'boolean' } }, required: ['claim', 'url', 'holds'] } },
    findings: { type: 'array', items: { type: 'string' } },
    popularity_or_current_use_reasoning_found: { type: 'boolean' },
    overturn_check: { type: 'string' },
    deciding_measurement_if_split: { type: 'string' },
  },
  required: ['slot_id', 'verdict', 'deciders_agree', 'default_after_review', 'checked_facts', 'findings', 'popularity_or_current_use_reasoning_found', 'overturn_check', 'deciding_measurement_if_split'],
}

const decidePrompt = (slot, n) => A.decide_prompt.replace('__CRITERIA__', A.criteria).replace('__PACKET__', packetPath(slot, n))
const criticPrompt = (slot, decisions) => A.critic_prompt
  .replace('__CRITERIA__', A.criteria)
  .replace('__DECISIONS__', JSON.stringify(decisions))
  .replace('__PACKET__', packetPath(slot, 1))

log(`slots ${A.slots.length}; deciders ${A.slots.length * 2}; critics ${A.slots.length}`)

const results = await pipeline(
  A.slots,
  // Both decisions are needed together by the slot's critic, so the two deciders form one barrier per slot.
  (slot) => parallel([1, 2].map((n) => () =>
    agent(decidePrompt(slot, n), {
      label: `decide:${slot}:order-${n}`, phase: 'Decide', schema: DECISION,
      agentType: 'stack-researcher', model: 'opus', effort: 'max',
    }).then((d) => (d ? { order: n, decision: d } : null)))),
  (decisions, slot) => {
    const got = decisions.filter(Boolean)
    if (got.length < 2) log(`${slot}: only ${got.length} of 2 decisions returned`)
    if (!got.length) return { slot_id: slot, decisions: [], critique: null }
    return agent(criticPrompt(slot, got), {
      label: `critic:${slot}`, phase: 'Critique', schema: CRITIQUE,
      agentType: 'stack-researcher', model: 'opus', effort: 'max',
    }).then((critique) => ({ slot_id: slot, decisions: got, critique }))
  },
)
return { slots: results.filter(Boolean) }
