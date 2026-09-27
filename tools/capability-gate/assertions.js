// JavaScript assertions for the capability-gate promptfoo configs (promptfoo 0.123.1,
// site/docs/configuration/expected-outputs/javascript.md: `file://assertions.js:<function>`, assertion-level `config`
// as context.config). They read only tool RESULTS from the provider's raw items, never the model's own text:
// openai:codex-sdk puts the Codex item list in response.raw (src/providers/openai/codex-sdk.ts:2430 at 0.123.1), where
// an MCP call is {type: 'mcp_tool_call', server, tool, status, error, result: {content, structured_content}} and a
// shell call is {type: 'command_execution', command, aggregated_output, status}.
//
// trace-error-spans is not used: codex-sdk.ts:1508-1512 counts an item as failed when `item.error !== undefined`, and
// codex-cli 0.157.1 sends `"error": null` on success, so every completed MCP call becomes an error span. The checks
// below require `status === 'completed'` and a falsy `error` instead.

function rawItems(context) {
  try {
    const raw = context.providerResponse && context.providerResponse.raw;
    return JSON.parse(typeof raw === 'string' ? raw : JSON.stringify(raw || {})).items || [];
  } catch (error) {
    return [];
  }
}

function resultText(result) {
  if (!result) return '';
  const blocks = (result.content || []).map((block) =>
    typeof block.text === 'string' ? block.text : JSON.stringify(block),
  );
  return blocks.join('\n') + '\n' + JSON.stringify(result.structured_content === undefined ? null : result.structured_content);
}

function describe(calls) {
  return calls.map((call) => `${call.tool}:${call.status}${call.error ? ' ' + String(call.error.message || '').slice(0, 120) : ''}`).join(', ') || 'none';
}

// One completed, error-free call to config.server whose result matches vars.detail, a detail the task text does not
// contain (checked against the rendered prompt).
function completedResult(output, context) {
  const server = (context.config || {}).server;
  const detail = new RegExp(context.vars.detail);
  if (detail.test(context.prompt || '')) {
    return { pass: false, score: 0, reason: 'the detail pattern is present in the prompt' };
  }
  const calls = rawItems(context).filter((item) => item.type === 'mcp_tool_call' && item.server === server);
  const hit = calls.find((call) => call.status === 'completed' && !call.error && detail.test(resultText(call.result)));
  return {
    pass: Boolean(hit),
    score: hit ? 1 : 0,
    reason: `${hit ? 'completed result matched' : 'no completed result matched'}; calls: ${describe(calls)}`,
  };
}

// M13 binding: which tree's token did one tool class return? vars.token is this row's own token, written by
// m13_hooks.js into this tree only; every token has the form CGTOK-<tree>-<rep>-<16 hex>, so any other token in a
// result came from the other tree (wrong root) or an earlier repetition (stale).
const TOKEN = /CGTOK-[ab]-r\d{2}-[0-9a-f]{16}/g;

function args(item) {
  return item.arguments && typeof item.arguments === 'object' ? item.arguments : {};
}

function mcpCall(item, server, tool) {
  return item.type === 'mcp_tool_call' && item.server === server && item.tool === tool;
}

function completed(item) {
  return Boolean(item) && item.status === 'completed' && !item.error &&
    !(item.type === 'command_execution' && item.exit_code);
}

// A command or snippet that names the fixture only by its relative path: no absolute path to it, no directory change
// and no token typed in, so a returned token can only come from the session's default binding.
function relativeRead(text, rel) {
  if (typeof text !== 'string') return false;
  const escaped = rel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(^|[\\s'"])${escaped}`).test(text) && !/\/\.cg\//.test(text) && !/\bcd\b/.test(text) &&
    !/CGTOK/.test(text);
}

function noCwd(item) {
  return args(item).cwd === undefined || args(item).cwd === null;
}

function isFixtureIndex(item, rep) {
  return mcpCall(item, 'context-mode', 'ctx_index') && args(item).path === `.cg/${rep}/sentinel-index.md` &&
    args(item).source === `cg-sentinel-${rep}`;
}

// Per class: `calls` selects every call of the class's tools, all of which are checked for foreign tokens;
// `prescribed` accepts only the call the brief prescribes (relative arguments, no cwd, no token in the arguments);
// `done` says whether a prescribed call completed. ctx_search counts only after a ctx_index of the fixture under the
// same source, and completes only when that index also completed.
const CLASSES = {
  shell: {
    calls: (item) => item.type === 'command_execution',
    prescribed: (item, rep) => relativeRead(item.command, `.cg/${rep}/sentinel-shell.txt`),
    done: (item) => completed(item),
  },
  ctx_execute: {
    calls: (item) => mcpCall(item, 'context-mode', 'ctx_execute'),
    prescribed: (item, rep) => noCwd(item) && relativeRead(args(item).code, `.cg/${rep}/sentinel-ctx-execute.txt`),
    done: (item) => completed(item),
  },
  ctx_execute_file: {
    calls: (item) => mcpCall(item, 'context-mode', 'ctx_execute_file'),
    prescribed: (item, rep) => noCwd(item) && args(item).path === `.cg/${rep}/sentinel-ctx-file.txt` &&
      !/CGTOK/.test(String(args(item).code || '')),
    done: (item) => completed(item),
  },
  ctx_index_search: {
    calls: (item) => mcpCall(item, 'context-mode', 'ctx_index') || mcpCall(item, 'context-mode', 'ctx_search'),
    prescribed: (item, rep, before) => mcpCall(item, 'context-mode', 'ctx_search') && noCwd(item) &&
      args(item).source === `cg-sentinel-${rep}` && !/CGTOK/.test(JSON.stringify(args(item))) &&
      before.some((prior) => isFixtureIndex(prior, rep)),
    done: (item, rep, before) => completed(item) && before.some((prior) => isFixtureIndex(prior, rep) && completed(prior)),
  },
  serena: {
    calls: (item) => mcpCall(item, 'serena', 'find_symbol'),
    prescribed: (item, rep) => args(item).relative_path === `.cg/${rep}/cg_sentinel.py`,
    done: (item) => completed(item),
  },
};

function itemText(item) {
  return item.type === 'command_execution' ? String(item.aggregated_output || '') : resultText(item.result);
}

// Verdict for one class, from every call of its tools, in this order:
// - wrong_root_or_stale: any call, completed or failed, returned a token other than this row's own;
// - no_call: no call of the class's tools;
// - not_prescribed: no call with the brief's arguments (for ctx_search: none after a ctx_index of the fixture);
// - own: a completed prescribed call returned this row's token;
// - error_only: no prescribed call completed; miss: one completed without the token.
function classVerdict(items, cls, own, rep) {
  const spec = CLASSES[cls];
  const calls = items.filter(spec.calls);
  const foreign = (calls.map(itemText).join('\n').match(TOKEN) || []).filter((token) => token !== own);
  if (foreign.length > 0) return 'wrong_root_or_stale';
  if (calls.length === 0) return 'no_call';
  const prescribed = [];
  items.forEach((item, index) => {
    if (spec.calls(item) && spec.prescribed(item, rep, items.slice(0, index))) prescribed.push([item, index]);
  });
  if (prescribed.length === 0) return 'not_prescribed';
  const done = prescribed.filter(([item, index]) => spec.done(item, rep, items.slice(0, index)));
  if (done.some(([item]) => itemText(item).includes(own))) return 'own';
  return done.length === 0 ? 'error_only' : 'miss';
}

function m13Class(output, context) {
  const cls = (context.config || {}).cls;
  const own = context.vars.token;
  const rep = context.vars.rep;
  if (!CLASSES[cls] || typeof own !== 'string' || !own || !/^r\d{2}$/.test(String(rep))) {
    return { pass: false, score: 0, reason: 'misconfigured: unknown class, no token or no rep' };
  }
  if ((context.prompt || '').includes(own)) {
    return { pass: false, score: 0, reason: 'the token is present in the prompt' };
  }
  const verdict = classVerdict(rawItems(context), cls, own, rep);
  return { pass: verdict === 'own', score: verdict === 'own' ? 1 : 0, reason: verdict };
}

module.exports = { completedResult, m13Class, classVerdict, relativeRead, TOKEN };
