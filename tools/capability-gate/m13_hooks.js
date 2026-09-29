// beforeEach extension hook for m13.yaml (promptfoo 0.123.1, site/docs/configuration/reference.md "Extension Hooks": a
// function named exactly `beforeEach` runs only for that hook, is called as (context, { hookName }), and a returned
// { test } replaces the step's test). promptfoo runs it per eval step just before that step's provider call
// (src/evaluator.ts:3587, runEvalStepAfterBeforeEach), and the step's vars are cloned from the returned test
// (createRunEvalState, src/evaluator.ts:710), so the prompt and the assertions see vars.sentinel.
//
// The var is `sentinel`, not `token`: promptfoo 0.123.1's sanitizer (src/util/sanitizer.ts) writes secret-named vars,
// `token` among them, to the results file as [REDACTED], and the retained results must carry each row's value for
// its class verdicts to be checked again.
//
// Each row writes a fresh random token into its own tree only, under .cg/<rep>/: two rows of one tree may overlap in
// time at maxConcurrency 2, and distinct paths keep one row from overwriting another's files. A wrong-root read then
// returns the other tree's token or nothing, and a stale index or search result returns an earlier repetition's token.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const FILES = {
  'sentinel-shell.txt': (token) => `${token}\n`,
  'sentinel-ctx-execute.txt': (token) => `${token}\n`,
  'sentinel-ctx-file.txt': (token) => `${token}\n`,
  'sentinel-index.md': (token) => `# CG sentinel token\n\nCG sentinel token: ${token}\n`,
  // serena's find_symbol body for a one-line constant is only its name, so the token is a function's return value.
  'cg_sentinel.py': (token) => `def cg_sentinel():\n    return "${token}"\n`,
};

async function beforeEach(context) {
  const test = context.test;
  const vars = test.vars || {};
  if (!/^[ab]$/.test(String(vars.tree)) || !/^r\d{2}$/.test(String(vars.rep))) {
    throw new Error('an m13 row needs vars tree (a or b) and rep (rNN)');
  }
  const root = process.env[vars.tree === 'a' ? 'CAPABILITY_GATE_WT_A' : 'CAPABILITY_GATE_WT_B'];
  if (!root || !path.isAbsolute(root) || !fs.existsSync(path.join(root, '.git'))) {
    throw new Error('CAPABILITY_GATE_WT_A and CAPABILITY_GATE_WT_B must name the two worktrees run_gate.py created');
  }
  const dir = path.join(root, '.cg', vars.rep);
  fs.mkdirSync(dir, { recursive: true });
  const token = `CGTOK-${vars.tree}-${vars.rep}-${crypto.randomBytes(8).toString('hex')}`;
  for (const [name, body] of Object.entries(FILES)) {
    fs.writeFileSync(path.join(dir, name), body(token));
  }
  return { test: { ...test, vars: { ...vars, sentinel: token } } };
}

module.exports = { beforeEach };
