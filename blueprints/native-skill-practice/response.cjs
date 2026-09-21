'use strict';

const labels = ['supported', 'contradicted', 'insufficient'];

// promptfoo 0.123.1 HTTP response transform. No fixture labels enter this parser.
module.exports = (json, _text, context) => {
  const answer = json?.answers?.verdict;
  if (json?.model !== 'jev-1.13.0' || answer?.type !== 'choice' ||
      !labels.includes(answer.choice) ||
      !Number.isFinite(answer.confidence) || answer.confidence < 0 || answer.confidence > 1) {
    throw new Error('Unexpected TypeSafe model or answer contract');
  }
  const probabilities = answer.probabilities;
  if (!probabilities || Object.keys(probabilities).sort().join(',') !== [...labels].sort().join(',') ||
      labels.some((key) => !Number.isFinite(probabilities[key]) || probabilities[key] < 0 || probabilities[key] > 1) ||
      Math.abs(labels.reduce((sum, key) => sum + probabilities[key], 0) - 1) > 0.03) {
    throw new Error('Invalid TypeSafe probability distribution');
  }
  const usage = json.usage;
  if (!Number.isSafeInteger(usage?.input_tokens) || usage.input_tokens < 0 ||
      !Number.isSafeInteger(usage?.output_tokens) || usage.output_tokens < 0) {
    throw new Error('Missing or invalid TypeSafe provider usage');
  }
  const cached = context?.response?.cached === true;
  return {
    output: answer.choice,
    tokenUsage: {
      prompt: cached ? 0 : usage.input_tokens,
      completion: cached ? 0 : usage.output_tokens,
      total: cached ? 0 : usage.input_tokens + usage.output_tokens,
      numRequests: cached ? 0 : 1,
    },
    metadata: {
      model: json.model,
      confidence: answer.confidence,
      probabilities,
      inference: cached ? 'cache' : 'live',
      request_id: context?.response?.headers?.['x-typesafe-request-id'] || null,
    },
  };
};
