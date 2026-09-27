export const meta = {
  name: 'token-e2e-run',
  description: 'Frozen PR-H Claude arm; launch only after the merge and capability gates.',
  phases: ['Frozen child tasks'],
};

// Sources: AA 8.1/8.2 (roles/routes); official Workflow reference:
// https://code.claude.com/docs/en/workflows
// args: supplied snapshot lines 230-238; API/schema: 292-334;
// cache prefix: 348-355; runtime constraints: 358-368.
// A Workflow-tool script, not a Node CLI. Node is used only for --check.
// Runtime has no filesystem, shell or imports. The coordinator supplies the
// exact parsed committed manifest in args.frozen_tasks (RUNBOOK.md).
// Amendment 2 (2026-09-27): stack-verifier and isolated-builder run on Opus, as
// #402's definitions declare; each call's explicit model decides the route.
const routes = {
  'stack-researcher': { agentType: 'stack-researcher', model: 'opus' },
  'stack-verifier': { agentType: 'stack-verifier', model: 'opus' },
  'isolated-builder': { agentType: 'isolated-builder', model: 'opus' },
  'evidence-reviewer': { agentType: 'evidence-reviewer', model: 'opus' },
  'source-scout': { agentType: 'source-scout', model: 'sonnet' },
  'blind-lane-reviewer': { agentType: 'blind-lane-reviewer', model: 'opus' },
  'blind-judge': { agentType: 'blind-judge', model: 'opus' },
};
const expectedIds = [
  "reuse-296-00",
  "reuse-296-01",
  "reuse-296-02",
  "reuse-296-03",
  "reuse-296-04",
  "reuse-296-05",
  "reuse-296-06",
  "reuse-296-07",
  "reuse-296-08",
  "reuse-296-09",
  "reuse-296-10",
  "reuse-296-11",
  "reuse-296-12",
  "reuse-296-13",
  "reuse-296-14",
  "reuse-296-15",
  "seed-web-table-1",
  "seed-web-table-2",
  "seed-web-table-3",
  "seed-web-table-4",
  "seed-web-table-5",
  "seed-catalog-history-1",
  "seed-catalog-history-2",
  "seed-catalog-history-3",
  "seed-catalog-history-4",
  "seed-catalog-history-5",
  "seed-log-symbol-1",
  "seed-acceptance-1",
  "seed-log-symbol-2",
  "seed-acceptance-2",
  "seed-log-symbol-3",
  "seed-acceptance-3",
  "seed-log-symbol-4",
  "seed-acceptance-4",
  "seed-log-symbol-5",
  "seed-acceptance-5",
  "seed-review-diff",
  "seed-scout-inventory",
  "seed-scout-acceptance",
  "seed-builder-1",
  "seed-builder-2",
  "seed-blind-1",
  "seed-blind-2",
  "seed-blind-3",
  "seed-blind-4",
  "seed-blind-5",
  "seed-blind-positive",
  "seed-overview",
  "seed-conversion"
];
const responseSchema = {
  type: 'object',
  required: ['answer', 'evidence'],
  additionalProperties: false,
  properties: {
    answer: { type: 'string' },
    evidence: { type: 'array', items: { type: 'string' } },
  },
};
if (!args || !['B', 'A', 'A0'].includes(args.arm)) {
  throw new Error('args.arm must be B, A or A0');
}
if (typeof args.run !== 'string' || !args.run || args.run.includes('.') ||
    !Number.isInteger(args.attempt) || args.attempt < 1) {
  throw new Error('Supply a run token without dots and a positive attempt number');
}
if (!args.preregistration_commit || args.gates_verified !== true) {
  throw new Error('Merge and native capability evidence must be verified before launch');
}
const manifest = args.frozen_tasks;
if (!manifest || manifest.schema_version !== 1 ||
    !Array.isArray(manifest.tasks) ||
    !Array.isArray(manifest.no_tool_names_denylist)) {
  throw new Error('Supply the exact parsed committed preregistration.json');
}
const candidates = manifest.tasks.filter(
  task => task.family === 'claude' && task.dispatch === 'workflow',
);
if (JSON.stringify(candidates.map(task => task.id)) !== JSON.stringify(expectedIds)) {
  throw new Error('Frozen task inventory or order changed');
}
const selected = candidates.filter(task => task.arms.includes(args.arm));
const expectedCount = args.arm === 'B' ? 49 : 43;
if (selected.length !== expectedCount) throw new Error('Frozen arm count changed');
// Preserve all planned slots, including #296's receiver information need.
// source-scout.md:11 forbids network; only a merged role amendment can unblock it.
const blocked = selected.filter(task => task.opportunity === 'blocked' || task.blocked_by);
if (blocked.length) {
  throw new Error('Frozen tasks blocked pending qualification/amendment: ' +
    blocked.map(task => task.id).join(', '));
}
const prompts = new Map();
for (const task of selected) {
  const route = routes[task.role];
  if (!route || task.model !== route.model || task.effort !== 'max' ||
      typeof task.task_text !== 'string' || !task.task_text.trim()) {
    throw new Error('Frozen task route or text is invalid: ' + task.id);
  }
  let prompt = task.task_text;
  if (task.worktree_check &&
      (task.worktree_check !== 'actual_child_worktree' ||
       manifest.builder_worktree_policy?.id !== task.worktree_check)) {
    throw new Error('Missing frozen actual-child-worktree check: ' + task.id);
  }
  if (task.worktree_required) {
    const path = args.worktree_paths?.[task.id];
    if (typeof path !== 'string' || !path.startsWith('/') || /[\r\n<>]/.test(path) ||
        !prompt.includes('<assigned-worktree>')) {
      throw new Error('Supply the frozen per-arm worktree binding: ' + task.id);
    }
    prompt = prompt.replaceAll('<assigned-worktree>', path);
  }
  if (task.input_required) {
    const path = args.input_paths?.[task.id];
    if (typeof path !== 'string' || !path.startsWith('/') || /[\r\n<>]/.test(path) ||
        !prompt.includes('<retained-input>')) {
      throw new Error('Supply the frozen input binding: ' + task.id);
    }
    prompt = prompt.replaceAll('<retained-input>', path);
  }
  if (task.run_binding) {
    if (!prompt.includes('<run-token>')) throw new Error('Missing run placeholder');
    prompt = prompt.replaceAll('<run-token>', args.run);
  }
  for (const name of manifest.no_tool_names_denylist) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (new RegExp('(?<![A-Za-z0-9])' + escaped + '(?![A-Za-z0-9])', 'i').test(prompt)) {
      throw new Error('Task text contains a forbidden name: ' + task.id);
    }
  }
  prompts.set(task.id, prompt);
}
// One active child at a time: bounded and deterministic. Native cache behavior
// remains intact; the same model/type/schema/cwd siblings may reuse the prefix.
// Never alter the coordinator's environment or effort from this script.
phase('Frozen child tasks');
const results = [];
for (const task of selected) {
  const route = routes[task.role];
  const identity = [args.run, args.arm, task.id, args.attempt].join('.');
  let response = null;
  let error = null;
  try {
    if (args.arm === 'B') {
      response = await agent(prompts.get(task.id), {
        agentType: route.agentType, model: route.model, effort: 'max',
        label: identity, schema: responseSchema,
      });
    } else if (args.arm === 'A') {
      // dispatch: preregistered general-purpose control on the identical task.
      response = await agent(prompts.get(task.id), {
        agentType: 'general-purpose', model: route.model, effort: 'max',
        label: identity, schema: responseSchema,
      });
    } else {
      // AA 8.1 A0 deliberately omits agentType; the route remains explicit.
      response = await agent(prompts.get(task.id), {
        model: route.model, effort: 'max',
        label: identity, schema: responseSchema,
      });
    }
  } catch (failure) {
    error = String(failure);
  }
  // A return is not a correctness verdict. Preserve null/error and all attempts
  // for independent frozen checks and transcript/usage reconciliation.
  // Workflow has no filesystem. The grader reads the native child transcript
  // and meta.json after return (RUNBOOK builder section), checks starting HEAD,
  // and diffs that observed tree, which must be the brief's prepared path: since
  // #402 the builder declares no frontmatter isolation (Amendment 2). The
  // supplied path is a binding, not proof. Never invent an actual path.
  const worktreeEvidence = task.worktree_check ? {
    prepared_path: args.worktree_paths[task.id], actual_path: null,
    identity_sources: ['child_transcript', 'meta.json'],
    status: 'pending_independent_readback',
  } : null;
  results.push({ identity, response, error, worktreeEvidence });
  log(JSON.stringify(results[results.length - 1]));
}
log(JSON.stringify({ arm: args.arm, scheduled: selected.length,
  returned: results.filter(item => item.response !== null).length }));
