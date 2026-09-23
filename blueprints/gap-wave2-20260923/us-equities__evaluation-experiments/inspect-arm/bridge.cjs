'use strict';
// Arm-2 bridge: evaluates the frozen promptfoo echo transform and the frozen
// gate.cjs plus the three promptfoo assertion expressions, byte-for-byte as
// read from blueprints/native-skill-practice/promptfooconfig.yaml by the caller.
// stdin: {"mode": "baseline"|"score", "expr": str, "vars": {...},
//         "output": str, "asserts": [str, ...]}
const path = require('node:path');
const gate = require(path.join(__dirname, '../../../native-skill-practice/gate.cjs'));
let raw = '';
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  const req = JSON.parse(raw);
  const context = { vars: req.vars };
  if (req.mode === 'baseline') {
    // Same evaluation shape as promptfoo: new Function('output','context','process', 'return ' + expr).
    const fn = new Function('output', 'context', 'process', 'return ' + req.expr);
    process.stdout.write(JSON.stringify({ output: fn('', context, process) }));
    return;
  }
  let gated;
  try {
    gated = gate(req.output, context);
  } catch (error) {
    process.stdout.write(JSON.stringify({ gate_error: String(error && error.message) }));
    return;
  }
  const results = req.asserts.map((value) => {
    const fn = new Function('output', 'context', 'return ' + value);
    let pass = false; let error = null;
    try { pass = fn(gated, context) === true; } catch (e) { error = String(e && e.message); }
    return { value, pass, error };
  });
  process.stdout.write(JSON.stringify({ gated, results }));
});
