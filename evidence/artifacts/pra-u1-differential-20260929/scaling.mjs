// How long commandInvocations takes by input size, for each shape of text. Count-only: text lengths and milliseconds.
//
//   node scaling.mjs --kernel <kernel.mjs> [--sizes 2000,4000,8000,16000] [--shapes name,name] [--runs 3] [--limit-ms 20000]
//
// A text is its shape's unit repeated up to about 2n characters (n is the size), plus the shape's tail. Each size is the best of --runs
// runs; a run over --limit-ms ends that shape (the later sizes are not run). `max_ratio` is the largest growth in time from one size to the
// next where the earlier time is above 5 ms (a linear reading grows by about 2 for twice the text, a quadratic one by about 4), and null
// when no ratio is measurable. The kernel is loaded with its own loadShellParser() when it has one.
//
// The shapes are the texts that made the reading quadratic before the tree was read with a cursor (a flat run of unclosed constructs or of
// comments is one wide node), some ordinary long texts as controls, and two that are quadratic inside tree-sitter-bash's own parse
// (`unclosed_array`, `heredoc_operators`): the parse itself takes the time there, so no reading of the tree changes it.
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

const args = process.argv.slice(2)
const opt = (name, fallback = null) => { const i = args.indexOf('--' + name); return i < 0 ? fallback : args[i + 1] }
const kernelPath = opt('kernel')
const kernel = await import(kernelPath)
if (typeof kernel.loadShellParser === 'function') {
  const loaded = await kernel.loadShellParser()
  if (!loaded.ok) throw new Error('no verified tree-sitter-bash install: ' + loaded.reason)
}
const sizes = opt('sizes', '2000,4000,8000,16000').split(',').map(Number)
const runs = Number(opt('runs', 3)), limitMs = Number(opt('limit-ms', 20000))
const SHAPES = {
  unclosed_double_paren: ['((', 'qmd'], unclosed_dollar_paren: ['$(', 'qmd'], unclosed_dq_dollar_paren: ['"$(', 'qmd'], unclosed_arith: ['$(( ', 'qmd'],
  backquotes: ['`', ''], unclosed_brace: ['{ ', ''], unclosed_if: ['if a; then ', ''], unclosed_case: ['case x in a) ', ''], comments: ['# c\n', ''],
  words: ['a b c ', ''], semicolons: ['a; ', ''], and_list: ['qmd status && ', 'true'], dq_substitutions: ['echo "$(qmd x)" ', ''],
  heredocs: ['cat <<EOF\nqmd\nEOF\n', ''], shell_heredocs: ["bash <<'EOF'\nqmd status\nEOF\n", ''], shell_strings: ["bash -c 'qmd' ", ''],
  pipes: ['x | ', 'qmd'], redirs: ['qmd status 2>&1 >/dev/null ', ''], assignments: ['A=1 ', 'qmd'],
  unclosed_array: ['a=( ', ''], heredoc_operators: ['<<', ''],
}
const names = opt('shapes') ? opt('shapes').split(',') : Object.keys(SHAPES)
for (const name of names) if (!SHAPES[name]) throw new Error('unknown shape: ' + name)
const bestMs = (text) => {
  let best = Infinity
  for (let i = 0; i < runs; i++) {
    const t0 = process.hrtime.bigint()
    kernel.commandInvocations(text)
    best = Math.min(best, Number(process.hrtime.bigint() - t0) / 1e6)
    if (best > limitMs) break
  }
  return best
}
const out = { kernel_sha256: createHash('sha256').update(readFileSync(kernelPath)).digest('hex').slice(0, 12), sizes, shapes: {} }
kernel.commandInvocations('qmd status') // warm-up
for (const name of names) {
  const [unit, tail] = SHAPES[name], chars = [], ms = []
  for (const n of sizes) {
    const text = unit.repeat(Math.ceil((2 * n) / unit.length)) + tail
    const t = bestMs(text)
    chars.push(text.length)
    ms.push(Number(t.toFixed(1)))
    if (t > limitMs) break
  }
  const ratios = ms.slice(1).map((t, i) => (ms[i] > 5 ? t / ms[i] : null)).filter((r) => r !== null)
  out.shapes[name] = { chars, ms, max_ratio: ratios.length ? Number(Math.max(...ratios).toFixed(2)) : null }
}
console.log(JSON.stringify(out))
