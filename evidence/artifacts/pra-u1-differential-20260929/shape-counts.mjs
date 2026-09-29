// Count-only scan of a corpus of shell texts for the shapes the command-position reading has to know about. Prints numbers only.
//
//   node shape-counts.mjs --kernel <kernel.mjs> --inputs <inputs.json> [--scanner <old-kernel.mjs>]
//
// The inputs are a JSON array of shell texts (the differential's real-command corpus). Every count is the number of texts (commands) with
// the shape, not of occurrences. `lane word` means a whole word equal to a lane executable's name (its basename), anywhere in the text: it
// needs no parser, so it also finds a lane the reading cannot see. --scanner names the scanner reading of commit 0c421c66 (no parser
// needed), a second and independent opinion on which lanes a text holds.
//
// The first overturn condition of docs/decisions/2026-09-29-shell-command-parser.md ("a grammar limit that loses or invents a lane
// call in 0.1% or more of the lane-bearing commands") is evaluated in `overturn_1`. A grammar limit is a parse error the reading met
// (`parse_errors`, after its own heredoc repairs) or a heredoc the grammar ended early. A lane call can be lost only where the reading
// does not look, and invented only where it reads text the grammar structured wrongly, so a limit command counts toward the upper
// bound when: the reading reads a lane in it (the lane of a tree with an error could be invented), or it is a heredoc ended early with
// a lane word, or its only error is in a script the reading read again (a shell string) and it holds a lane word (the word cannot be
// placed), or a lane word that the reading did not read stands where a command name could stand and the tree does not show it to be data.
// The last is decided in two steps, over the tree of the text as given (before the reading's repairs). Where a command name could stand
// (a `slot`) is read from the text alone: the lane word begins its simple command (after ; & | ( ) { } a backquote, a newline or `!`), or
// a wrapper, keyword, assignment or redirection word comes before it in that command (`sudo -u x qmd`, `A=1 qmd`, `2>&1 qmd`); after
// plain words (`echo qmd`, `grep -n qmd`) it is an argument, whatever the tree makes of it. A slot is discharged as data when the tree puts
// it in a comment, heredoc body, string or assignment value, and joins the bound when it lies in an ERROR node (the subtree the reading
// skips, taken as opaque) or anywhere else. `lane_bearing` is the number of commands in which the reading reads a lane invocation,
// the smaller and so the stricter denominator; `lane_bearing_upper` adds the commands with only a lane word. The bound is an upper
// bound of what the reading loses or invents, from the tree's own limits: a silent misparse (no ERROR node) is not in it, and is
// measured by the oracle and the differential instead.
import { readFileSync } from 'node:fs'

const args = process.argv.slice(2)
const opt = (name) => { const i = args.indexOf('--' + name); return i < 0 ? null : args[i + 1] }
const kernel = await import(opt('kernel'))
const parser = await kernel.loadShellParser()
if (!parser.ok) throw new Error('no verified tree-sitter-bash install: ' + parser.reason)
const scanner = opt('scanner') ? await import(opt('scanner')) : null
if (scanner && typeof scanner.loadShellParser === 'function') await scanner.loadShellParser()
const inputs = JSON.parse(readFileSync(opt('inputs'), 'utf8'))
const LANE = new Set(['toon', 'repomix', 'markitdown', 'qmd', 'headroom', 'jcodemunch-mcp', 'codebase-memory-mcp', 'ai-memory', 'serena', 'serena-agent', 'context-mode', 'mcporter', 'rtk'])
const hasLaneWord = (text) => text.split(/[^A-Za-z0-9_./~-]+/).some((w) => w && LANE.has(w.slice(w.lastIndexOf('/') + 1)))
// The [start, end) of every lane word (the same words as hasLaneWord), by a linear scan.
const laneWordSpans = (text) => [...text.matchAll(/[A-Za-z0-9_./~-]+/g)].filter((m) => LANE.has(m[0].slice(m[0].lastIndexOf('/') + 1))).map((m) => [m.index, m.index + m[0].length])
// Where a command name could stand, from the text alone (see the header). Looks back at most 4,000 characters (further: a slot).
const WRAPPER_WORDS = new Set(['then', 'do', 'else', 'elif', 'if', 'while', 'until', 'time', 'exec', 'env', 'nohup', 'sudo', 'xargs', 'timeout', 'nice', 'command', 'stdbuf',
  'proxy', 'eval', 'ssh', 'bash', 'sh', 'dash', 'zsh', 'ksh', 'npx', 'uvx', 'bunx', 'pnpm', 'yarn', 'bun', 'pipx', 'uv', 'python', 'python3', 'rtk'])
const SEPARATOR_CHARS = ';&|(){}`\n!'
function commandSlot(text, at) {
  let start = at
  while (start > 0 && at - start < 4000 && !SEPARATOR_CHARS.includes(text[start - 1])) start--
  if (at - start >= 4000) return true
  const words = text.slice(start, at).split(/[ \t]+/).filter(Boolean)
  return words.length === 0 || words.some((w) => WRAPPER_WORDS.has(w) || /^[A-Za-z_][A-Za-z0-9_]*=/.test(w) || /[<>]/.test(w))
}
const DATA_NODES = new Set(['comment', 'heredoc_body', 'raw_string', 'string', 'ansi_c_string', 'translated_string', 'variable_assignment'])
// Where the tree puts a lane word: in an ERROR node, in data, or elsewhere (the innermost node that spans it, then its ancestors).
function treePosition(root, a, b) {
  let position = null
  for (let n = root.descendantForIndex(a, b); n; n = n.parent) {
    if (n.type === 'ERROR') return 'error'
    if (position === null && DATA_NODES.has(n.type)) position = 'data'
  }
  return position ?? 'elsewhere'
}
const laneTokens = (records) => records.filter((i) => i.lane && !i.remote && !i.unresolved).map((i) => i.lane + (i.excluded ? '!' : '')).sort()
const minus = (a, b) => { const left = [...b]; return a.filter((t) => { const i = left.indexOf(t); if (i < 0) return true; left.splice(i, 1); return false }) }
const call = (command) => [{ type: 'assistant', timestamp: '2026-09-26T01:00:00Z', message: { content: [{ type: 'tool_use', id: 'c', name: 'Bash', input: { command } }] } }]
const SHELL_CS = /(?:\bba?sh|\bsh|\bdash|\bzsh)\s+(?:-[A-Za-z]+\s+)*-[A-Za-z]*c\s+"\$\(\s*cat\s+<<-?\s*['"\\]?[A-Za-z_0-9-]+/
const c = {
  commands: inputs.length, with_a_parse_error: 0, with_a_lane_invocation: 0, with_an_unresolved_program: 0, unresolved_and_a_lane_word: 0,
  named_bang: 0, escaped_backquote_body: 0, folded_redirect_words: 0, folded_redirect_words_lane_word: 0, time_then_assignment_or_bang: 0,
  with_a_heredoc_operator: 0, heredoc_ended_early: 0, heredoc_unterminated: 0, heredoc_operator_begins_a_statement: 0, two_heredoc_operators_with_a_tree_error: 0,
  word_cut_after_an_assignment: 0, word_cut_after_an_assignment_lane_word: 0, shell_c_of_a_cat_heredoc_substitution: 0,
  // the first overturn condition (see the header)
  with_a_lane_word: 0, lane_bearing_upper: 0, grammar_limit: 0, grammar_limit_with_a_lane_word: 0, grammar_limit_lane_read: 0,
  grammar_limit_lane_word_unread: 0, grammar_limit_lane_word_in_an_error_node: 0, grammar_limit_early_with_a_lane_word: 0,
  grammar_limit_error_only_in_a_script_read_again: 0, grammar_limit_error_only_in_a_script_read_again_lane_word: 0,
  grammar_limit_unread_no_command_slot: 0, grammar_limit_unread_slot_in_data: 0, grammar_limit_unread_slot_elsewhere: 0, grammar_limit_unread_unplaced: 0,
  grammar_limit_lost_or_invented_upper: 0, grammar_limit_scanner_reads_more: scanner ? 0 : null, grammar_limit_scanner_throws: scanner ? 0 : null,
}
for (const text of inputs) {
  const m = kernel.measureTranscript(call(text)).cli_lanes
  if (m.parse_errors) c.with_a_parse_error++
  if (m.calls_with_lane_invocation) c.with_a_lane_invocation++
  if (m.unresolved_programs) { c.with_an_unresolved_program++; if (hasLaneWord(text)) c.unresolved_and_a_lane_word++ }
  if (SHELL_CS.test(text)) c.shell_c_of_a_cat_heredoc_substitution++
  if (text.includes('<<')) c.with_a_heredoc_operator++
  const words = laneWordSpans(text), read = m.calls_with_lane_invocation > 0
  const needPositions = words.length > 0 && !read && (m.parse_errors > 0 || text.includes('<<')) // the unread lane words of a possible grammar limit
  const seen = kernel.withShellTree(text, (root) => {
    const s = { bang: false, bq: false, fold: false, foldLane: false, time: false, early: false, open: false, leading: false, cut: false, cutLane: false, tree: root.hasError, errors: [], positions: needPositions ? words.map(([a, b]) => ({ slot: commandSlot(text, a), position: treePosition(root, a, b) })) : null }
    const stack = [root]
    while (stack.length) {
      const n = stack.pop()
      if (n.type === 'ERROR') s.errors.push([n.startIndex, n.endIndex])
      if (n.type === 'command_name' && n.text === '!') s.bang = true
      if (n.type === 'command_substitution' && n.text.startsWith('`') && /\\[$`\\]/.test(n.text)) s.bq = true
      if (n.type === 'file_redirect') {
        const dest = []
        for (let i = 0; i < n.childCount; i++) if (n.fieldNameForChild(i) === 'destination') dest.push(n.child(i))
        const extra = dest.slice(1).filter((d, i) => { const gap = text.slice(dest[i].endIndex, d.startIndex); return !gap.includes('\n') && !gap.includes(';') })
        if (extra.length) { s.fold = true; if (extra.some((d) => LANE.has(d.text.slice(d.text.lastIndexOf('/') + 1)))) s.foldLane = true }
      }
      if (n.type === 'heredoc_end' && text[n.endIndex] !== undefined && text[n.endIndex] !== '\n' && n.endIndex > n.startIndex) s.early = true
      if (n.type === 'heredoc_redirect') { const kinds = n.children.map((x) => x.type); if (kinds.includes('heredoc_start') && !kinds.includes('heredoc_end')) s.open = true }
      if (n.type === 'ERROR' && n.childCount === 1 && n.child(0).type === '<' && text[n.startIndex + 1] === '<') s.leading = true
      if (n.type === 'command') {
        const name = n.childForFieldName('name')?.text, args = []
        for (let i = 0; i < n.childCount; i++) if (n.fieldNameForChild(i) === 'argument') args.push(n.child(i))
        if (name === 'time' && args[0] && (args[0].text === '!' || /^[A-Za-z_][A-Za-z0-9_]*=/.test(args[0].text) || (args[0].text === '-p' && args[1] && (args[1].text === '!' || /^[A-Za-z_][A-Za-z0-9_]*=/.test(args[1].text))))) s.time = true
        let prev = null
        for (let i = 0; i < n.childCount; i++) {
          const ch = n.child(i)
          if (prev && ((prev.type === 'variable_assignment' && ch.type === 'command_name') || (prev.endIndex === ch.startIndex && ['argument', 'name'].includes(n.fieldNameForChild(i)) && ['argument', 'name'].includes(n.fieldNameForChild(i - 1))))) {
            s.cut = true
            for (let j = i + 1; j < n.childCount; j++) { const w = n.child(j).text; if (LANE.has(w.slice(w.lastIndexOf('/') + 1))) s.cutLane = true }
          }
          prev = ch
        }
      }
      for (let i = n.childCount - 1; i >= 0; i--) stack.push(n.child(i))
    }
    return s
  })
  if (seen.bang) c.named_bang++
  if (seen.bq) c.escaped_backquote_body++
  if (seen.fold) { c.folded_redirect_words++; if (seen.foldLane) c.folded_redirect_words_lane_word++ }
  if (seen.time) c.time_then_assignment_or_bang++
  if (seen.early) c.heredoc_ended_early++
  if (seen.open) c.heredoc_unterminated++
  if (seen.leading) c.heredoc_operator_begins_a_statement++
  if (seen.cut) { c.word_cut_after_an_assignment++; if (seen.cutLane) c.word_cut_after_an_assignment_lane_word++ }
  if (seen.tree && text.split('\n').some((l) => (l.match(/<<(?!<)/g) ?? []).length >= 2)) c.two_heredoc_operators_with_a_tree_error++
  // The first overturn condition: lane-bearing commands without the parser's help, and what a grammar limit can lose or invent in them.
  if (words.length) c.with_a_lane_word++
  if (read || words.length) c.lane_bearing_upper++
  if (m.parse_errors || seen.early) {
    c.grammar_limit++
    if (words.length) c.grammar_limit_with_a_lane_word++
    if (read) c.grammar_limit_lane_read++
    else if (words.length) c.grammar_limit_lane_word_unread++
    // The error lies in a script the reading read again (a shell string), not in the text's own tree: a lane word cannot be placed.
    const elsewhere = m.parse_errors > 0 && !seen.tree
    if (elsewhere) { c.grammar_limit_error_only_in_a_script_read_again++; if (words.length) c.grammar_limit_error_only_in_a_script_read_again_lane_word++ }
    if (seen.early && words.length) c.grammar_limit_early_with_a_lane_word++
    // What an unread lane word is: the riskiest of its occurrences (in the order unplaced, slot elsewhere, slot in data, no slot).
    let risk = null
    if (words.length && !read) {
      if (elsewhere) risk = 'unplaced'
      else {
        risk = 'no_command_slot'
        for (const { slot, position } of seen.positions) {
          if (!slot) continue
          if (position === 'data') { if (risk === 'no_command_slot') risk = 'slot_in_data' } else risk = 'slot_elsewhere'
        }
      }
      c['grammar_limit_unread_' + risk]++
    }
    if (words.some(([a, b]) => seen.errors.some(([x, y]) => a < y && b > x))) c.grammar_limit_lane_word_in_an_error_node++
    if (scanner) {
      try { if (minus(laneTokens(scanner.commandInvocations(text)), laneTokens(kernel.commandInvocations(text))).length) c.grammar_limit_scanner_reads_more++ } catch { c.grammar_limit_scanner_throws++ }
    }
    if (read || (seen.early && words.length) || risk === 'unplaced' || risk === 'slot_elsewhere') c.grammar_limit_lost_or_invented_upper++
  }
}
const THRESHOLD = 0.001
const rate = (n, d) => d ? Number((n / d).toFixed(6)) : null
c.overturn_1 = { threshold: THRESHOLD, threshold_commands: Math.ceil(THRESHOLD * c.with_a_lane_invocation), lane_bearing: c.with_a_lane_invocation, lane_bearing_upper: c.lane_bearing_upper,
  lost_or_invented_upper_bound: c.grammar_limit_lost_or_invented_upper, rate_upper_bound: rate(c.grammar_limit_lost_or_invented_upper, c.with_a_lane_invocation),
  rate_lane_word_screen: rate(c.grammar_limit_with_a_lane_word, c.with_a_lane_invocation),
  met_by_the_upper_bound: c.with_a_lane_invocation ? c.grammar_limit_lost_or_invented_upper / c.with_a_lane_invocation >= THRESHOLD : null }
console.log(JSON.stringify(c, null, 1))
