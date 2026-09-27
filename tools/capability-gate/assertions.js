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
const CLASSES = {
  shell: (item) => item.type === 'command_execution' && /sentinel-shell\.txt/.test(item.command || ''),
  ctx_execute: (item) => item.type === 'mcp_tool_call' && item.server === 'context-mode' && item.tool === 'ctx_execute',
  ctx_execute_file: (item) => item.type === 'mcp_tool_call' && item.server === 'context-mode' && item.tool === 'ctx_execute_file',
  ctx_index_search: (item) => item.type === 'mcp_tool_call' && item.server === 'context-mode' && item.tool === 'ctx_search',
  serena: (item) => item.type === 'mcp_tool_call' && item.server === 'serena' && item.tool === 'find_symbol',
};

function itemText(item) {
  return item.type === 'command_execution' ? String(item.aggregated_output || '') : resultText(item.result);
}

function classify(texts, own) {
  const joined = texts.join('\n');
  const others = (joined.match(TOKEN) || []).filter((token) => token !== own);
  if (others.length > 0) return 'wrong_root_or_stale';
  return joined.includes(own) ? 'own' : 'miss';
}

// Verdict for config.cls: own, wrong_root_or_stale, miss (no call) or error_only (only failed calls, no token).
function m13Class(output, context) {
  const cls = (context.config || {}).cls;
  const own = context.vars.token;
  if (!CLASSES[cls] || typeof own !== 'string' || !own) {
    return { pass: false, score: 0, reason: 'misconfigured: unknown class or no token' };
  }
  if ((context.prompt || '').includes(own)) {
    return { pass: false, score: 0, reason: 'the token is present in the prompt' };
  }
  const hits = rawItems(context).filter(CLASSES[cls]);
  let verdict;
  if (hits.length === 0) {
    verdict = 'miss';
  } else {
    const good = hits.filter((item) => item.status === 'completed' && !item.error && !(item.type === 'command_execution' && item.exit_code));
    if (good.length === 0) {
      verdict = classify(hits.map(itemText), own);
      if (verdict === 'miss') verdict = 'error_only';
    } else {
      verdict = classify(good.map(itemText), own);
    }
  }
  return { pass: verdict === 'own', score: verdict === 'own' ? 1 : 0, reason: verdict };
}

module.exports = { completedResult, m13Class, classify, TOKEN };
