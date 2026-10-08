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
// Bound files as the copied tree places them (relative to its root), so the mutations below hold in every
// layout contract.config.json may describe; settings mutations start from the real env so each drifts one value.
const SETTINGS_FILE = join('workflows', CONFIG.settings)
const INSTRUCTIONS_FILE = join('workflows', CONFIG.instructions)
const ROUTING_DOC_FILE = join('workflows', CONFIG.routing_doc)
const ENV = JSON.parse(readFileSync(resolve(HERE, CONFIG.settings), 'utf8')).env || {}
const MUTATIONS = [
  ['a later stage names a nonexistent agent', 'workflows/review-changes.js', "agentType: 'evidence-reviewer'", "agentType: 'evidence-reviwer'", 'names only valid project agents in every stage'],
  ['a later stage drops its model', 'workflows/review-changes.js', "agentType: 'evidence-reviewer', model: 'opus', effort: 'max'", "agentType: 'evidence-reviewer', effort: 'max'", 'binds model and effort inside every options literal'],
  ['the packet drifts by one space', 'workflows/readiness-audit.js', 'only the listed sources, no writes', 'only the listed sources,  no writes', 'PACKET text is byte-identical'],
  ['the reviewer regains a bare server grant', 'agents/evidence-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, ToolSearch, mcp__serena, ', 'never a bare server prefix'],
  ['the reviewer gains a file-creating tool', 'agents/evidence-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, ToolSearch, mcp__serena__create_text_file, ', 'tool surface is exactly the reviewed list'],
  ['an agent drops its effort', 'agents/source-scout.md', 'effort: max\n', '', 'declares an explicit model and effort'],
  ['an agent( hides inside a template literal', 'workflows/readiness-audit.js', "phase('Verify')", "phase('Verify')\nconst never = () => `${agent('x', { label: 'h', model: 'opus', effort: 'max' })}`", 'has no agent( inside a template literal'],
  ['a stage drops the shared packet but keeps its label', 'workflows/review-changes.js', "PACKET + '\\nYou are an independent reviewer.", "'Worker packet contract:' + '\\nYou are an independent reviewer.", 'starts every worker prompt with the full shared packet'],
  ['the review stage is routed to the builder', 'workflows/review-changes.js', "agentType: 'evidence-reviewer'", "agentType: 'isolated-builder'", 'routes each stage to its reviewed agent, model and effort'],
  ['a stage loses its agentType', 'workflows/readiness-audit.js', "agentType: 'source-scout', ", '', 'routes each stage to its reviewed agent, model and effort'],
  ['a call is written as agent (', 'workflows/review-changes.js', "phase('Inventory')", "phase('Inventory')\nif (a.extraStage) await agent ('extra', { label: 'extra' })", 'binds model and effort inside every options literal'],
  ['a later duplicate key overrides the model', 'workflows/review-changes.js', "agentType: 'evidence-reviewer', model: 'opus', effort: 'max' }", "agentType: 'evidence-reviewer', model: 'opus', effort: 'max', model: undefined }", 'declares model and effort exactly once'],
  // Since 2026-09-27 the builder carries no frontmatter isolation and checks a coordinator-created worktree itself.
  ['the builder regains frontmatter worktree isolation', 'agents/isolated-builder.md', 'effort: max\n', 'effort: max\nisolation: worktree\n', 'declares no frontmatter isolation'],
  ['the builder drops its own-checkout comparison', 'agents/isolated-builder.md', 'compare `git -C <path> rev-parse --show-toplevel`', 'read `git -C <path> rev-parse --show-toplevel`', 'edits only in a coordinator-created worktree'],
  ['the builder stops refusing to edit without a worktree', 'agents/isolated-builder.md', 'stop without editing', 'continue editing', 'edits only in a coordinator-created worktree'],
  // Each refusal condition on its own (the 2026-09-27 cross-family review removed either one and the suite still passed).
  ['the builder drops its no-path refusal', 'agents/isolated-builder.md', 'when the brief names no path, ', '', 'edits only in a coordinator-created worktree'],
  ['the builder drops its own-checkout refusal', 'agents/isolated-builder.md', 'when both commands print the same top level (the coordinator\'s own checkout) or ', '', 'edits only in a coordinator-created worktree'],
  ['the builder drops its wrong-base refusal', 'agents/isolated-builder.md', ' or when HEAD is not the brief\'s base', '', 'edits only in a coordinator-created worktree'],
  ['the builder stops reading its HEAD', 'agents/isolated-builder.md', ', and read `git -C <path> rev-parse HEAD`', '', 'edits only in a coordinator-created worktree'],
  ['the agent table restates the builder on Sonnet', ROUTING_DOC_FILE, '| `isolated-builder` | Opus, max,', '| `isolated-builder` | Sonnet, max,', 'the agent table restates each listed agent'],
  ['the agent table restates the verifier on Sonnet', ROUTING_DOC_FILE, '| `stack-verifier` | Opus, max |', '| `stack-verifier` | Sonnet, max |', 'the agent table restates each listed agent'],
  // Stack agents and dispatch by role (docs/decisions/2026-09-26-stack-agents-role-dispatch.md): a regained fetch,
  // skill, edit or Serena symbol-edit tool, or a role table that reroutes or restates a role, must fail.
  ['the researcher regains WebFetch', 'agents/stack-researcher.md', 'tools: Read, Glob, Grep, Bash, WebSearch, ToolSearch, ', 'tools: Read, Glob, Grep, Bash, WebSearch, WebFetch, ToolSearch, ', 'stack-researcher tool surface is exactly the reviewed list'],
  ['the researcher gains the Skill tool', 'agents/stack-researcher.md', 'tools: Read, Glob, Grep, Bash, WebSearch, ToolSearch, ', 'tools: Read, Glob, Grep, Bash, WebSearch, Skill, ToolSearch, ', 'stack-researcher tool surface is exactly the reviewed list'],
  ['the verifier gains Edit', 'agents/stack-verifier.md', 'tools: Read, Glob, Grep, Bash, ToolSearch, ', 'tools: Read, Edit, Glob, Grep, Bash, ToolSearch, ', 'stack-verifier tool surface is exactly the reviewed list'],
  ['the builder regains a Serena symbol-edit tool', 'agents/isolated-builder.md', 'mcp__serena__get_diagnostics_for_file, ', 'mcp__serena__get_diagnostics_for_file, mcp__serena__replace_symbol_body, ', 'isolated-builder grants only Serena read tools'],
  ['the role table sends the verifier role to the default child', ROUTING_DOC_FILE, '| verifier | `stack-verifier` |', '| verifier | `general-purpose` |', 'the role table maps each dispatch role'],
  ['the role table restates the researcher on Sonnet', ROUTING_DOC_FILE, '| researcher | `stack-researcher` | Opus, max |', '| researcher | `stack-researcher` | Sonnet, max |', 'the role table maps each dispatch role'],
  ['a harmless reordering of the researcher tools', 'agents/stack-researcher.md', 'tools: Read, Glob, Grep, ', 'tools: Glob, Read, Grep, ', null],
  ['the researcher loses catalog search', 'agents/stack-researcher.md', 'mcp__jcodemunch__menu, ', '', 'stack-researcher tool surface is exactly the reviewed list'],
  ['the security reviewer gains Bash', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, Bash, ToolSearch, ', 'security-reviewer tool surface is exactly the reviewed list'],
  ['the security reviewer gains Edit', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, Edit, ToolSearch, ', 'security-reviewer tool surface is exactly the reviewed list'],
  ['the security reviewer gains Write', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, Write, ToolSearch, ', 'security-reviewer tool surface is exactly the reviewed list'],
  ['the security reviewer gains WebFetch', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, WebFetch, ToolSearch, ', 'security-reviewer tool surface is exactly the reviewed list'],
  ['the security reviewer gains Skill invocation', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ToolSearch, ', 'tools: Read, Glob, Grep, Skill, ToolSearch, ', 'security-reviewer tool surface is exactly the reviewed list'],
  ['the security reviewer loses its preload', 'agents/security-reviewer.md', 'skills:\n  - security-best-practices\n', '', 'security-reviewer preloads exactly its reviewed skill'],
  ['the role table sends security to the general reviewer', ROUTING_DOC_FILE, '| security | `security-reviewer` |', '| security | `evidence-reviewer` |', 'the role table maps each dispatch role'],
  ['the builder loses its preload', 'agents/isolated-builder.md', 'skills:\n  - context-mode:context-mode\n', '', 'isolated-builder preloads exactly its reviewed skills'],
  ['the builder substitutes a user-invocable-only skill', 'agents/isolated-builder.md', '  - context-mode:context-mode\n', '  - grill-me\n', 'isolated-builder preloads exactly its reviewed skills'],
  // Removed from the skills trial on 2026-09-28 (docs/decisions/2026-09-25-skills-trial-and-usage.md); with one
  // preload left, the former harmless reordering case has nothing to reorder.
  ['the builder regains the removed skill', 'agents/isolated-builder.md', '  - context-mode:context-mode\n', '  - context-mode:context-mode\n  - verification-before-completion\n', 'isolated-builder preloads exactly its reviewed skills'],
  ['a harmless reordering of the security reviewer tools', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ', 'tools: Glob, Read, Grep, ', null],
  // Effort max (docs/decisions/2026-09-23-max-effort-default.md): a stage or agent that drops its effort, or binds
  // any level other than max, must fail; a stage without effort would run at its agent's frontmatter effort, else at
  // the effort the session was given explicitly (--effort, /effort or the model picker), else at its model's saved level or
  // default (on 2.1.281 the coordinator's xhigh).
  ['a later stage drops its effort', 'workflows/review-changes.js', "agentType: 'evidence-reviewer', model: 'opus', effort: 'max'", "agentType: 'evidence-reviewer', model: 'opus'", 'binds model and effort inside every options literal'],
  ['a default-child stage drops its effort', 'workflows/readiness-audit.js', "schema: VERIFY, model: 'opus', effort: 'max'", "schema: VERIFY, model: 'opus'", 'binds model and effort inside every options literal'],
  ['a review stage runs at effort high', 'workflows/review-changes.js', "agentType: 'evidence-reviewer', model: 'opus', effort: 'max'", "agentType: 'evidence-reviewer', model: 'opus', effort: 'high'", 'binds effort max in every options literal'],
  ['a scout stage runs at effort medium', 'workflows/review-changes.js', "schema: RECHECK, agentType: 'source-scout', model: 'sonnet', effort: 'max'", "schema: RECHECK, agentType: 'source-scout', model: 'sonnet', effort: 'medium'", 'binds effort max in every options literal'],
  ['a default-child stage runs at effort xhigh', 'workflows/readiness-audit.js', "schema: VERIFY, model: 'opus', effort: 'max'", "schema: VERIFY, model: 'opus', effort: 'xhigh'", 'binds effort max in every options literal'],
  ['a reader stage names ultracode as its effort', 'workflows/readiness-audit.js', "agentType: 'source-scout', model: 'sonnet', effort: 'max'", "agentType: 'source-scout', model: 'sonnet', effort: 'ultracode'", 'binds effort max in every options literal'],
  ['a lane stage runs at effort low while MODEL records max', 'workflows/layer-verdict-lane.js', "phase: 'Propose', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'max'", "phase: 'Propose', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'low'", 'records in MODEL, when declared, the same model and effort it binds'],
  ['the lane MODEL literal records high while every call binds max', 'workflows/layer-verdict-lane.js', "const MODEL = { name: 'opus', effort: 'max' }", "const MODEL = { name: 'opus', effort: 'high' }", 'records in MODEL, when declared, the same model and effort it binds'],
  ['the lane MODEL literal records a full model id while the calls bind aliases', 'workflows/layer-verdict-lane.js', "const MODEL = { name: 'opus', effort: 'max' }", "const MODEL = { name: 'claude-opus-5-5', effort: 'max' }", 'records in MODEL, when declared, the same model and effort it binds'],
  ['an agent runs at effort low', 'agents/source-scout.md', 'effort: max\n', 'effort: low\n', 'runs at effort max on a single effort line'],
  ['an agent runs at effort medium', 'agents/isolated-builder.md', 'effort: max\n', 'effort: medium\n', 'runs at effort max on a single effort line'],
  ['an agent runs at effort high', 'agents/evidence-reviewer.md', 'effort: max\n', 'effort: high\n', 'runs at effort max on a single effort line'],
  ['an agent runs at effort xhigh', 'agents/semantic-evidence-reviewer.md', 'effort: max\n', 'effort: xhigh\n', 'runs at effort max on a single effort line'],
  ['an agent gains a second, lower effort line', 'agents/blind-lane-reviewer.md', 'effort: max\n', 'effort: max\neffort: high\n', 'runs at effort max on a single effort line'],
  ['the routing table restates source-scout at medium', ROUTING_DOC_FILE, 'running acceptance commands | `source-scout` | Sonnet, max |', 'running acceptance commands | `source-scout` | Sonnet, medium |', 'lists every project agent once with the model and effort its file declares'],
  ['the routing table restates a default child at high', ROUTING_DOC_FILE, '| default workflow subagent | Opus, max |', '| default workflow subagent | Opus, high |', 'every default workflow subagent row binds a model at effort max'],
  ['the routing table drops the saved xhigh fallback from the coordinator row', ROUTING_DOC_FILE, '| coordinator | Opus 5.5, max from the launcher, else saved xhigh, under `ultracode`', '| coordinator | Opus 5.5, max under `ultracode`', 'the coordinator row states the launcher max and the saved xhigh fallback under ultracode'],
  // A sixth field `true` replaces every occurrence. Since 2026-10-08 the instructions binding is the workflows README,
  // which states the stage effort rule in several sections, so one statement left behind must not hide the defect.
  ['the instructions stop stating the stage effort literal', INSTRUCTIONS_FILE, "`effort: 'max'`", "`effort: 'high'`", 'state the effort literal every stage binds', true],
  ['the instructions stop naming the size guideline the settings select', INSTRUCTIONS_FILE, '`unrestricted` size guideline', '`large` size guideline', 'workflowSizeGuideline is a documented value and the project instructions name the same one', true],
  // CLAUDE_CODE_EFFORT_LEVEL overrides every stage's and agent's effort at any value (docs; probes P6 and P9 at max), and any
  // value other than xhigh also turned ultracode's orchestration off on 2.1.281 (P1); an effort cap below max clamps the stages.
  ['the settings env sets CLAUDE_CODE_EFFORT_LEVEL=max', SETTINGS_FILE, 'env', { ...ENV, CLAUDE_CODE_EFFORT_LEVEL: 'max' }, 'CLAUDE_CODE_EFFORT_LEVEL stays unset and no maxEffortLevel caps the stage effort'],
  ['the settings env sets CLAUDE_CODE_EFFORT_LEVEL=xhigh', SETTINGS_FILE, 'env', { ...ENV, CLAUDE_CODE_EFFORT_LEVEL: 'xhigh' }, 'CLAUDE_CODE_EFFORT_LEVEL stays unset and no maxEffortLevel caps the stage effort'],
  ['the settings cap every model at xhigh', SETTINGS_FILE, 'maxEffortLevel', 'xhigh', 'CLAUDE_CODE_EFFORT_LEVEL stays unset and no maxEffortLevel caps the stage effort'],
  ['a per-model settings entry caps Sonnet at high', SETTINGS_FILE, 'modelSettings', { 'claude-sonnet-5': { maxEffortLevel: 'high' } }, 'CLAUDE_CODE_EFFORT_LEVEL stays unset and no maxEffortLevel caps the stage effort'],
  ['a harmless max cap in the settings', SETTINGS_FILE, 'maxEffortLevel', 'max', null],
  ['a harmless comment mentions a lower effort', 'workflows/review-changes.js', "phase('Review')", "phase('Review') // before 2026-09-23 this stage bound effort: 'high'", null],
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
for (const [name, file, from, to, expectFail, every] of [['(baseline, no mutation)', null, '', '', undefined], ...MUTATIONS]) {
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
      writeFileSync(join(copyRoot, file), every ? src.split(from).join(to) : src.replace(from, to))
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
