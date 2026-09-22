#!/usr/bin/env node
// NEGATIVE EVIDENCE for test-envelope.mjs: copies the agents/ and workflows/ trees beside this
// file plus every file its contract.config.json names into a temp tree at the same relative depth, applies one defect at a time and requires the
// suite to fail on the assertion that names it. A harmless edit must still pass.
import { cpSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const CONFIG = JSON.parse(readFileSync(join(HERE, 'contract.config.json'), 'utf8'))
// Deepest '..' the config climbs above the workflows dir decides where the copied tree sits.
// Every binding must be a relative path (or the heading string) so the temp copy is
// self-contained; an absolute binding would make the spawned suite read the real file.
const BINDINGS = Object.entries(CONFIG).filter(([key]) => key !== 'contract_heading')
const relativeBindings = BINDINGS.filter(([, v]) => typeof v === 'string' && !v.startsWith('/'))
// Two spare levels: a mutation may climb one level beyond the deepest binding and must
// still resolve inside the temp root; anything outside it is a harness failure.
const DEPTH = Math.max(0, ...relativeBindings.map(([, v]) => v.split('/').filter((seg) => seg === '..').length - 1)) + 2
let passed = 0, failed = 0
const expect = (n, c) => { console.log((c ? 'PASS ' : 'FAIL ') + n); if (c) passed++; else failed++ }
const MUTATIONS = [
  ['a later stage names a nonexistent agent', 'workflows/review-changes.js', "agentType: 'evidence-reviewer'", "agentType: 'evidence-reviwer'", 'names only valid project agents in every stage'],
  ['a later stage drops its model', 'workflows/review-changes.js', "agentType: 'evidence-reviewer', model: 'opus', effort: 'high'", "agentType: 'evidence-reviewer', effort: 'high'", 'binds model and effort inside every options literal'],
  ['the packet drifts by one space', 'workflows/readiness-audit.js', 'only the listed sources, no writes', 'only the listed sources,  no writes', 'PACKET text is byte-identical'],
  ['the reviewer regains a bare server grant', 'agents/evidence-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, ToolSearch, mcp__serena, ', 'never a bare server prefix'],
  ['the reviewer gains a file-creating tool', 'agents/evidence-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, ToolSearch, mcp__serena__create_text_file, ', 'tool surface is exactly the reviewed list'],
  ['an agent drops its effort', 'agents/source-scout.md', 'effort: medium\n', '', 'declares an explicit model and effort'],
  ['an agent( hides inside a template literal', 'workflows/readiness-audit.js', "phase('Verify')", "phase('Verify')\nconst never = () => `${agent('x', { label: 'h', model: 'opus', effort: 'high' })}`", 'has no agent( inside a template literal'],
  ['a stage drops the shared packet but keeps its label', 'workflows/review-changes.js', "PACKET + '\\nYou are an independent reviewer.", "'Worker packet contract:' + '\\nYou are an independent reviewer.", 'starts every worker prompt with the full shared packet'],
  ['the review stage is routed to the builder', 'workflows/review-changes.js', "agentType: 'evidence-reviewer'", "agentType: 'isolated-builder'", 'routes each stage to its reviewed agent, model and effort'],
  ['a stage loses its agentType', 'workflows/readiness-audit.js', "agentType: 'source-scout', ", '', 'routes each stage to its reviewed agent, model and effort'],
  ['a call is written as agent (', 'workflows/review-changes.js', "phase('Inventory')", "phase('Inventory')\nif (a.extraStage) await agent ('extra', { label: 'extra' })", 'binds model and effort inside every options literal'],
  ['a later duplicate key overrides the model', 'workflows/review-changes.js', "agentType: 'evidence-reviewer', model: 'opus', effort: 'high' }", "agentType: 'evidence-reviewer', model: 'opus', effort: 'high', model: undefined }", 'declares model and effort exactly once'],
  ['the builder loses worktree isolation', 'agents/isolated-builder.md', 'isolation: worktree\n', '', 'runs in its own worktree'],
  // Config mutations are applied as JSON edits (key, new value) so they hold in every
  // layout the config may describe, not only the one whose strings appear here.
  ['the configured contract heading is absent from the contract doc', 'workflows/contract.config.json', 'contract_heading', '## Workflow contrac', 'contract_heading names the documented contract section'],
  ['the configured settings path points at a missing file', 'workflows/contract.config.json', 'settings', '../settings.missing.json', 'settings resolves to an existing file'],
  ['the configured settings path names a directory instead of a file', 'workflows/contract.config.json', 'settings', '../agents', 'settings resolves to an existing file'],
  ['a binding is not a string', 'workflows/contract.config.json', 'routing_doc', 7, 'routing_doc resolves to an existing file'],
  ['a binding names a file the tree does not hold', 'workflows/contract.config.json', 'extra_doc', '../missing.md', 'extra_doc resolves to an existing file'],
  ['a harmless comment mentions agent(', 'workflows/review-changes.js', "phase('Review')", "phase('Review') // next: agent( review", null],
]
// The unmutated copy must pass; each mutation must then add a failure that names its
// assertion, so an unrelated failure can neither mask nor fake a mutation result.
// Pure placement: where each binding lands in the copy and which would escape the root.
function placeBindings(root, copyRoot, bindings) {
  const copies = [], escaped = []
  for (const [key, rel] of bindings) {
    const target = resolve(join(copyRoot, 'workflows'), rel)
    if (target.startsWith(root + '/')) copies.push({ key, source: resolve(HERE, rel), target }); else escaped.push(key)
  }
  return { copies, escaped }
}
expect('config: every binding in contract.config.json is a relative path', relativeBindings.length === BINDINGS.length)
{
  // Negative evidence for the placement guard without touching the filesystem.
  const fakeRoot = '/virtual/root', fakeCopy = join(fakeRoot, 'level0', 'level1', 'tree')
  const inside = placeBindings(fakeRoot, fakeCopy, [['settings', '../settings.json'], ['doc', '../../../x.md']])
  const outside = placeBindings(fakeRoot, fakeCopy, [['deep', '../../../../../../escape.md']])
  expect('placement: bindings within the spare levels stay inside the root', inside.escaped.length === 0 && inside.copies.every((c) => c.target.startsWith(fakeRoot + '/')))
  expect('placement: a binding that climbs past the root is refused, never copied', outside.escaped.length === 1 && outside.copies.length === 0)
}
let baseline = null
for (const [name, file, from, to, expectFail] of [['(baseline, no mutation)', null, '', '', undefined], ...MUTATIONS]) {
  const root = mkdtempSync(join(tmpdir(), 'contract-mutation-'))
  try {
    const copyRoot = join(root, ...Array.from({ length: DEPTH }, (_, i) => 'level' + i), 'tree')
    cpSync(join(ROOT, 'agents'), join(copyRoot, 'agents'), { recursive: true }); cpSync(join(ROOT, 'workflows'), join(copyRoot, 'workflows'), { recursive: true })
    // A binding whose source is missing is left out of the copy so the spawned suite
    // reports it as a missing configured file instead of the harness aborting here.
    const placed = placeBindings(root, copyRoot, relativeBindings)
    if (placed.escaped.length) { expect('mutation tree stays inside its temporary root: ' + name, false); continue }
    for (const { source, target } of placed.copies) {
      if (!existsSync(source)) continue
      mkdirSync(dirname(target), { recursive: true }); cpSync(source, target, { recursive: true })
    }
    if (file && file.endsWith('.json')) {
      const cfg = JSON.parse(readFileSync(join(copyRoot, file), 'utf8'))
      cfg[from] = to
      writeFileSync(join(copyRoot, file), JSON.stringify(cfg, null, 2) + '\n')
    } else if (file) {
      const src = readFileSync(join(copyRoot, file), 'utf8')
      if (!src.includes(from)) { expect('mutation applies: ' + name, false); continue }
      writeFileSync(join(copyRoot, file), src.replace(from, to))
    }
    const run = spawnSync(process.execPath, [join(copyRoot, 'workflows/test-envelope.mjs')], { cwd: copyRoot, encoding: 'utf8' })
    const fails = run.stdout.split('\n').filter((l) => l.startsWith('FAIL '))
    if (!file) { baseline = fails; expect('baseline copy passes cleanly (any failure here belongs to the tree, not to a mutation)', run.status === 0 && fails.length === 0 && /SUMMARY passed=\d+ failed=0 /.test(run.stdout)); continue }
    const added = fails.filter((l) => !baseline.includes(l))
    const summarized = /SUMMARY passed=\d+ failed=\d+/.test(run.stdout)
    if (expectFail === null) expect('no new failure when ' + name, added.length === 0 && summarized)
    else expect('suite newly fails on its SUMMARY line when ' + name, run.status === 1 && summarized && added.some((l) => l.includes(expectFail)))
  } finally { rmSync(root, { recursive: true, force: true }) }
}
console.log('SUMMARY passed=' + passed + ' failed=' + failed + ' total=' + (passed + failed))
process.exit(failed ? 1 : 0)
