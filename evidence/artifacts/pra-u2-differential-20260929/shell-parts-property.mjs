#!/usr/bin/env node
// Property check of child-usage.mjs shellParts (binding decision B8) on generated commands whose parts are known by construction.
// Each command joins synthetic segments (simple commands, commands holding "$( )", backquotes, arithmetic, redirections, comments and
// here-documents in and out of substitutions) with control operators; a top-level here-document's body follows the next newline. GNU bash
// (`bash -n`, which reads here-document bodies without running anything) must accept a command before it counts, so the expected parts
// are those of valid shell text. A second pass feeds random strings over the shell's metacharacters and checks that shellParts returns
// null or parts without throwing, within a time bound. Prints counts only; the commands are synthetic, never host data.
//   node shell-parts-property.mjs <child-usage.mjs> [commands] [seed]
import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const [kernelPath, countArg = '600', seedArg = '20260929'] = process.argv.slice(2)
if (!kernelPath) { console.error('usage: shell-parts-property.mjs <child-usage.mjs> [commands] [seed]'); process.exit(2) }
const { shellParts } = await import(pathToFileURL(resolve(kernelPath)).href)
let state = Number(seedArg) >>> 0
const rand = () => { // mulberry32
  state = (state + 0x6D2B79F5) >>> 0
  let t = state
  t = Math.imul(t ^ (t >>> 15), t | 1)
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}
const pick = (list) => list[Math.floor(rand() * list.length)]

// Segments with no top-level control operator: [text, class]. A here-document inside a segment ends inside it.
const SIMPLE = [
  ['git status', 'plain'], ['git log -3', 'plain'], ['ls -la', 'plain'], ['echo "a; b | c && d"', 'double_quotes'],
  ["echo 'x && y; z | w'", 'single_quotes'], ['echo a\\;b\\&\\&c', 'escapes'], ['echo $((1 + 2))', 'arithmetic'],
  ['(( n = 1 << 2 ))', 'arithmetic_command'], ['x=$(printf "%s" "a;b")', 'substitution'], ['echo `ls; pwd`', 'backquotes'],
  ['{ ls; pwd; }', 'brace_group'], ['( cd sub && make )', 'subshell'], ['git status 2>&1', 'fd_duplication'],
  ['git status &> /dev/null', 'and_greater'], ['git status >| out.txt', 'clobber'], ['cat < in.txt 2<&0', 'less_and'],
  ['echo "$(echo ")")"', 'quote_in_substitution'], ['echo ${HOME}', 'parameter_braces'], ['echo {a,b}', 'brace_expansion'],
  ['printf "%s\\n" "$( (echo a; echo b) )"', 'nested_subshell'], ['git log \\\n  --oneline -3', 'line_continuation'],
  ["x=$(cat <<'EOF'\nbody; x && y | z\nEOF\n)", 'heredoc_in_substitution'],
  ["git commit -m \"$(cat <<'EOF'\nmsg | x; y\nEOF\n)\"", 'heredoc_in_quoted_substitution'],
  ['cat <<< "here; string"', 'here_string'], ["grep -n '<<EOF' notes.txt", 'quoted_heredoc_operator'],
  ['echo "#not a comment"', 'quoted_hash'], ['echo a#b', 'word_hash'], ['x=$(echo a\necho b)', 'newline_in_substitution'],
  ['x=$(cat <<EOF)', 'heredoc_left_open_by_its_substitution'],
]
// Lines a here-document body may hold; none is a delimiter used below, with or without leading tabs.
const BODY = ['a; b && c | d', "'unbalanced quote", '"double', '$(unclosed', ' EOF', 'EOF ', 'EOF2', '<<X', '$((1 +', '# comment', '`', ')', '}', '{',
  'git status', 'rtk git log -3', 'PY2', '\tEND', 'x=$(date); echo "$x"', '']
// Here-document openers: [text before the operator, operator word, delimiter, strip tabs]
const OPENERS = [['cat ', "<<'EOF'", 'EOF', false], ['cat ', '<<EOF', 'EOF', false], ['cat ', '<<"EOF"', 'EOF', false], ['cat ', "<<-'EOF'", 'EOF', true],
  ['python3 - ', "<<'PY'", 'PY', false], ['cat ', "<<'END-JSON'", 'END-JSON', false], ['cat ', '<<\\EOF', 'EOF', false], ['sort ', '<< EOF', 'EOF', false],
  ['cat > out.txt ', "<<'EOF'", 'EOF', false], ['bash ', "<<'SH'", 'SH', false], ['cat ', '<<E"O"F', 'EOF', false], ['wc -l ', '<<123', '123', false]]
const OPS = [';', '&&', '||', '|', '&', '\n', '|&']
const body = (strip) => Array.from({ length: 1 + Math.floor(rand() * 3) }, () => (strip && rand() < 0.5 ? '\t' : '') + pick(BODY))

function generate() {
  const parts = 1 + Math.floor(rand() * 5), expected = [], classes = new Set()
  let text = '', pending = [], leftOpen = false
  for (let i = 0; i < parts; i++) {
    let segment
    if (rand() < 0.3) {
      const [head, word, delimiter, strip] = pick(OPENERS)
      segment = head + word
      pending.push({ delimiter, strip })
      classes.add('heredoc')
    } else {
      // A segment may hold newlines of its own (inside "$( )"): a top-level body still follows the next top-level newline, as bash reads it.
      // A here-document a substitution leaves open is read after the enclosing line (bash 5.2.21 and dash agree when it is the line's only
      // one). Beside another pending body on the same line the shells disagree (bash reads the substitution's first, dash gives it none), so
      // the generator never puts it beside one: it is picked only with nothing pending, and its line ends right after it.
      let s, c
      do [s, c] = pick(SIMPLE); while (pending.length && c === 'heredoc_left_open_by_its_substitution')
      segment = s
      classes.add(c)
      if (pending.length && s.includes('\n') && c !== 'line_continuation') classes.add('newline_in_substitution_before_a_body')
      if (c === 'heredoc_left_open_by_its_substitution') { pending.push({ delimiter: 'EOF', strip: false }); leftOpen = true }
    }
    const comment = rand() < 0.1
    let op = i === parts - 1 ? '' : pick(OPS)
    if (comment) { segment += ' # note; with | ops && more'; classes.add('comment'); if (op !== '') op = '\n' }
    if (pending.length && op === '' || leftOpen) op = '\n' // a body needs the newline that ends its line
    expected.push([segment, op === '|&' ? '|' : op])
    text += segment
    if (op === '\n') {
      text += '\n'
      for (const h of pending) text += body(h.strip).join('\n') + '\n' + (h.strip && rand() < 0.5 ? '\t' : '') + h.delimiter + '\n'
      pending = []
      leftOpen = false
    } else if (op) text += ' ' + op + ' '
  }
  if (expected.length && expected[expected.length - 1][1] === '\n' && !text.endsWith('\n')) text += '\n'
  return { text, expected, classes }
}

const count = Number(countArg), out = { generated: 0, bash_valid: 0, bash_rejected: 0, agree: 0, disagree: 0, threw: 0,
  disagree_by_class: {}, agree_by_class: {}, max_ms: 0 }
for (let n = 0; n < count; n++) {
  const g = generate()
  out.generated++
  const bash = spawnSync('bash', ['-n'], { input: g.text, encoding: 'utf8' })
  if (bash.status !== 0) { out.bash_rejected++; continue }
  out.bash_valid++
  let got
  const t = process.hrtime.bigint()
  try { got = shellParts(g.text) } catch { out.threw++; continue }
  out.max_ms = Math.max(out.max_ms, Number(process.hrtime.bigint() - t) / 1e6)
  const same = JSON.stringify(got?.map((p) => [p.text, p.op]) ?? null) === JSON.stringify(g.expected)
  out[same ? 'agree' : 'disagree']++
  for (const c of g.classes) { const key = same ? 'agree_by_class' : 'disagree_by_class'; out[key][c] = (out[key][c] || 0) + 1 }
}
// Robustness: random strings over the metacharacters never throw; the slowest of them is reported.
const ALPHABET = [..."'\"`$(){}<>|&;#\\\n\t -EOFab0"]
const random = { strings: 0, null: 0, parts: 0, threw: 0, max_ms: 0 }
for (let n = 0; n < count; n++) {
  const s = Array.from({ length: 1 + Math.floor(rand() * 200) }, () => pick(ALPHABET)).join('')
  random.strings++
  const t = process.hrtime.bigint()
  try { const p = shellParts(s); random[p ? 'parts' : 'null']++ } catch { random.threw++ }
  random.max_ms = Math.max(random.max_ms, Number(process.hrtime.bigint() - t) / 1e6)
}
// Scaling: one generated command of many parts, doubled; the time per doubling should stay near twice.
const scaling = [], closed = SIMPLE.filter(([, c]) => c !== 'heredoc_left_open_by_its_substitution').map(([s]) => s)
for (const parts of [2000, 4000, 8000, 16000]) {
  let text = ''
  for (let i = 0; i < parts; i++) text += (i % 3 === 0 ? "cat <<'EOF'\nbody; x\nEOF\n" : closed[i % closed.length] + ' && ')
  text += 'git status'
  let best = Infinity
  for (let r = 0; r < 3; r++) { const t = process.hrtime.bigint(); shellParts(text); best = Math.min(best, Number(process.hrtime.bigint() - t) / 1e6) }
  scaling.push({ parts, characters: text.length, ms: Math.round(best * 10) / 10 })
}
out.max_ms = Math.round(out.max_ms * 100) / 100
random.max_ms = Math.round(random.max_ms * 100) / 100
console.log(JSON.stringify({ kind: 'pra_u2_shell_parts_property', seed: Number(seedArg), bash: spawnSync('bash', ['--version'], { encoding: 'utf8' }).stdout.split('\n')[0].replace(/\s*\(.*$/, ''),
  generated: out, random, scaling }, null, 1))
process.exitCode = out.disagree || out.threw || random.threw ? 1 : 0
