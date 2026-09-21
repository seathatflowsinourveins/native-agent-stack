'use strict';

const { createHash } = require('node:crypto');

// This deterministic transform applies equally to both evaluated providers.
module.exports = (output, context) => {
  if (!['supported', 'contradicted', 'insufficient'].includes(output)) {
    throw new Error('Invalid semantic verdict');
  }
  const vars = context?.vars || {};
  const parse = (value) => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return NaN;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) && new Date(parsed).toISOString() === value.replace('Z', '.000Z')
      ? parsed : NaN;
  };
  const available = parse(vars.source_available_at);
  const cutoff = parse(vars.decision_at);
  const eligible = Number.isFinite(available) && Number.isFinite(cutoff) && available <= cutoff;
  if (typeof vars.source !== 'string' || !vars.source.trim()) {
    throw new Error('Missing source evidence');
  }
  return JSON.stringify({
    verdict: output,
    eligible,
    disposition: eligible ? `advisory_${output}` : 'reject_evidence',
    source_sha256: createHash('sha256').update(vars.source).digest('hex'),
    schema_version: 1,
  });
};
