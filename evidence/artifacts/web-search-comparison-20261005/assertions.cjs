// Native promptfoo JavaScript assertions, not an evaluation runner.
// promptfoo@34f74d34:site/docs/configuration/expected-outputs/javascript.md:50-75,203-240.
function results(output) {
  try {
    const value = typeof output === 'string' ? JSON.parse(output) : output;
    const rows = Array.isArray(value) ? value : value?.results;
    if (!Array.isArray(rows) || rows.length > 5 || value?.error) return null;
    for (const row of rows) {
      if (!row || typeof row.title !== 'string' || typeof row.url !== 'string' || !row.title.trim()) return null;
      if (typeof (row.content ?? row.snippet) !== 'string' || !(row.content ?? row.snippet).trim()) return null;
      const url = new URL(row.url);
      if (!['http:', 'https:'].includes(url.protocol)) return null;
    }
    return rows;
  } catch { return null; }
}
function grade(pass, score, reason) { return { pass, score, reason }; }
function firstPrimary(rows, context) {
  if (!rows) return -1;
  // Promptfoo expands top-level array variables into separate cases. Freeze
  // the oracle as one JSON-string variable, preserving multiple URL families.
  const patterns = JSON.parse(context.vars.primary_patterns).map((pattern) => new RegExp(pattern));
  return rows.findIndex((row) => {
    const url = new URL(row.url);
    const canonical = `${url.protocol}//${url.host}${url.pathname}`;
    return patterns.some((pattern) => pattern.test(canonical));
  });
}
exports.contract = (output) => grade(results(output) !== null, results(output) !== null ? 1 : 0, 'Native top-five JSON contract');
exports.usable = (output) => {
  const rows = results(output); const ok = rows !== null && rows.length > 0;
  return grade(ok, ok ? 1 : 0, 'Nonempty usable native search results');
};
exports.primaryHit = (output, context) => {
  const hit = firstPrimary(results(output), context) >= 0;
  return grade(hit, hit ? 1 : 0, 'Preregistered primary URL hit within top five');
};
exports.primaryMrr = (output, context) => {
  const rows = results(output); const rank = firstPrimary(rows, context);
  return grade(rows !== null && rows.length > 0, rank < 0 ? 0 : 1 / (rank + 1), 'Reciprocal first primary rank within top five');
};
exports.unique = (output) => {
  const rows = results(output);
  const score = rows?.length ? new Set(rows.map((row) => row.url)).size / rows.length : 0;
  return grade(rows !== null && rows.length > 0, score, 'Distinct URL fraction; duplicate hits never add credit');
};
