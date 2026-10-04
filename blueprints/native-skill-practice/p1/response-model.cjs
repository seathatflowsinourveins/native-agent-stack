'use strict';

// P1's response transform for arm J: ../response.cjs, unchanged, plus the response's model field on its
// error path. When the contract check throws, the error names the model the service returned, so scoring
// can tell a moved alias or version from any other failed call (report r1 section 5.0: check the
// response model field on every call; p1_scoring.calls_from_promptfoo reads it back). promptfoo 0.123.1
// records a provider error as String(error) plus the stack (evaluator buildProviderErrorContext), so
// the bracketed suffix reaches the --output file. A successful call returns exactly what
// ../response.cjs returns.
const contract = require('../response.cjs');

module.exports = (json, text, context) => {
  try {
    return contract(json, text, context);
  } catch (error) {
    const model = typeof json?.model === 'string' ? json.model : null;
    throw new Error(`${error.message} [response model: ${JSON.stringify(model)}]`);
  }
};
