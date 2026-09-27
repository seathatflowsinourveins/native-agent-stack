'use strict';
// promptfoo HTTP provider transformResponse for R02 (promptfoo@0.123.1:site/docs/providers/http.md:550-567,
// 1730-1796): parses the OpenAI chat-completions SSE stream the gateway returns for `stream: true`.
//
// - Output: the concatenated choices[0].delta.content.
// - tokenUsage: from the last chunk that carries `usage`, whatever its choices hold; the gateway attaches
//   usage to the final chunk with finish_reason, and writes completion_tokens_details and
//   prompt_tokens_details only when their counts are above 0 (OmniRoute@dd6e9607e:open-sse/translator/
//   response/openai-responses.ts:1375-1419, 1450-1453, read from the pinned commit; first relayed by the
//   gateway owner). Fields follow promptfoo's own OpenAI mapping (src/providers/openai/util.ts:998-1044;
//   src/contracts/shared.ts:4-21): provider-cached prompt tokens go to completionDetails.cacheReadInputTokens
//   and reasoning tokens to completionDetails.reasoning. TokenUsage.cached stays unset: it counts promptfoo's
//   own cache hits. The raw usage object is kept in metadata for the analysis.
// - A failure after the gateway committed a 200 stream arrives as a data-only chunk with an `error` key
//   (OmniRoute@dd6e9607e:open-sse/utils/earlyStreamKeepalive.ts:70-79, 664-685); its keepalive chunks have
//   empty deltas and no finish_reason (:43-48), so they add nothing to the output.
// - Metadata: the resolved model, finish_reason, the raw usage object and the gateway's X-Correlation-Id.
//   promptfoo keeps response headers in metadata.http.headers in memory, but redacts x-correlation-id when
//   it writes results (src/models/evalResult.ts:199-213), so the id is copied to metadata.r02.correlation_id
//   from the documented third argument (context.response.headers, src/providers/http.ts:2784-2786).
// - Failures return {error, metadata} rather than throwing. promptfoo records either as an error result
//   (src/evaluator.ts:1342-1346), but only a returned error keeps the metadata (src/evaluator.ts:1212-1271
//   versus 1799-1830), which is what joins a failed call to call_logs by its correlation id.
// - Non-200 statuses reach this function because validateStatus is unset (src/providers/http.ts:1488-1493,
//   2716), except 429: with maxRetries 0, promptfoo throws before any transform (src/util/fetch/index.ts:
//   681-714, 768-770), so a 429 is recorded from the thrown error's text and carries no correlation id.

const CORRELATION_HEADER = 'x-correlation-id';
const MAX_ERROR_CHARS = 500;

function headerValue(headers, name) {
  if (!headers || typeof headers !== 'object') return null;
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === name) {
      const text = Array.isArray(value) ? value.join(',') : value;
      return typeof text === 'string' && text.length > 0 ? text : null;
    }
  }
  return null;
}

function bounded(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return text === undefined ? '' : text.slice(0, MAX_ERROR_CHARS);
}

function finite(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function parseStream(text) {
  const stream = {
    content: '', models: [], finishReason: null, usage: null, usageChunkHasChoices: null,
    done: false, chunks: 0, dataAfterDone: 0, malformed: 0, errorEvent: null,
  };
  let eventName = null;
  for (const line of String(text || '').split(/\r?\n/)) {
    if (line === '') {
      eventName = null; // a blank line ends one SSE event
      continue;
    }
    if (line.startsWith(':')) continue; // SSE comment or keep-alive
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
      continue;
    }
    if (!line.startsWith('data:')) continue;
    const payload = line.slice(5).trim();
    if (payload === '[DONE]') {
      stream.done = true;
      continue;
    }
    if (stream.done) stream.dataAfterDone += 1;
    let chunk;
    try {
      chunk = JSON.parse(payload);
    } catch {
      stream.malformed += 1;
      continue;
    }
    stream.chunks += 1;
    if (!chunk || typeof chunk !== 'object') {
      stream.malformed += 1;
      continue;
    }
    if (eventName === 'error' || chunk.error) {
      stream.errorEvent = chunk.error || chunk;
      continue;
    }
    if (typeof chunk.model === 'string' && !stream.models.includes(chunk.model)) stream.models.push(chunk.model);
    const choices = Array.isArray(chunk.choices) ? chunk.choices : [];
    for (const choice of choices) {
      if (!choice || (choice.index !== undefined && choice.index !== 0)) continue;
      const delta = choice.delta || {};
      if (typeof delta.content === 'string') stream.content += delta.content;
      if (choice.finish_reason) stream.finishReason = choice.finish_reason;
    }
    if (chunk.usage && typeof chunk.usage === 'object') {
      stream.usage = chunk.usage;
      stream.usageChunkHasChoices = choices.length > 0;
    }
  }
  return stream;
}

function tokenUsage(usage) {
  const result = {
    prompt: finite(usage.prompt_tokens),
    completion: finite(usage.completion_tokens),
    total: finite(usage.total_tokens),
    numRequests: 1,
  };
  const details = {};
  const reasoning = finite(usage.completion_tokens_details && usage.completion_tokens_details.reasoning_tokens);
  if (reasoning !== undefined) details.reasoning = reasoning;
  const cachedInput = finite(usage.prompt_tokens_details && usage.prompt_tokens_details.cached_tokens);
  if (cachedInput !== undefined) details.cacheReadInputTokens = cachedInput;
  if (Object.keys(details).length > 0) result.completionDetails = details;
  return result;
}

module.exports = (json, text, context) => {
  const response = (context && context.response) || {};
  const correlationId = headerValue(response.headers, CORRELATION_HEADER);
  const r02 = { correlation_id: correlationId };
  const metadata = {
    http: { status: response.status, statusText: response.statusText, headers: { [CORRELATION_HEADER]: correlationId } },
    r02,
  };
  if (response.status !== 200) {
    return { error: `http_status_${response.status}: ${bounded(json || text)}`, metadata };
  }
  if (json && typeof json === 'object') {
    return { error: `not_an_sse_stream: ${bounded(json)}`, metadata };
  }
  const stream = parseStream(text);
  Object.assign(r02, {
    model: stream.models.length > 0 ? stream.models[stream.models.length - 1] : null,
    models: stream.models,
    finish_reason: stream.finishReason,
    done_sentinel: stream.done,
    chunks: stream.chunks,
    data_after_done: stream.dataAfterDone,
    usage_chunk_has_choices: stream.usageChunkHasChoices,
    usage: stream.usage,
  });
  if (stream.errorEvent) return { error: `sse_error_event: ${bounded(stream.errorEvent)}`, metadata };
  if (stream.malformed > 0) return { error: `malformed_sse_chunks: ${stream.malformed}`, metadata };
  if (!stream.finishReason) return { error: 'missing_terminal_chunk', metadata };
  if (!stream.usage) return { error: 'missing_usage', metadata };
  return { output: stream.content, tokenUsage: tokenUsage(stream.usage), metadata };
};
