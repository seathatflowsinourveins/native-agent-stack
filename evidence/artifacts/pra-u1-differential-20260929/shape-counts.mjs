// Count-only scan of a corpus of shell texts for the shapes the command-position reading has to know about. Prints numbers only.
//
//   node shape-counts.mjs --kernel <kernel.mjs> --inputs <inputs.json>
//
// The inputs are a JSON array of shell texts (the differential's real-command corpus). Every count is the number of texts (commands) with
// the shape, not of occurrences. `lane word` means a whole word equal to a lane executable's name (its basename), anywhere in the text.
import { readFileSync } from 'node:fs'

const args = process.argv.slice(2)
const opt = (name) => { const i = args.indexOf('--' + name); return i < 0 ? null : args[i + 1] }
const kernel = await import(opt('kernel'))
const parser = await kernel.loadShellParser()
if (!parser.ok) throw new Error('no verified tree-sitter-bash install: ' + parser.reason)
const inputs = JSON.parse(readFileSync(opt('inputs'), 'utf8'))
const LANE = new Set(['toon', 'repomix', 'markitdown', 'qmd', 'headroom', 'jcodemunch-mcp', 'codebase-memory-mcp', 'ai-memory', 'serena', 'serena-agent', 'context-mode', 'mcporter', 'rtk'])
const hasLaneWord = (text) => text.split(/[^A-Za-z0-9_./~-]+/).some((w) => w && LANE.has(w.slice(w.lastIndexOf('/') + 1)))
const call = (command) => [{ type: 'assistant', timestamp: '2026-09-26T01:00:00Z', message: { content: [{ type: 'tool_use', id: 'c', name: 'Bash', input: { command } }] } }]
const SHELL_CS = /(?:\bba?sh|\bsh|\bdash|\bzsh)\s+(?:-[A-Za-z]+\s+)*-[A-Za-z]*c\s+"\$\(\s*cat\s+<<-?\s*['"\\]?[A-Za-z_0-9-]+/
const c = {
  commands: inputs.length, with_a_parse_error: 0, with_a_lane_invocation: 0, with_an_unresolved_program: 0, unresolved_and_a_lane_word: 0,
  named_bang: 0, escaped_backquote_body: 0, folded_redirect_words: 0, folded_redirect_words_lane_word: 0, time_then_assignment_or_bang: 0,
  with_a_heredoc_operator: 0, heredoc_ended_early: 0, heredoc_unterminated: 0, heredoc_operator_begins_a_statement: 0, two_heredoc_operators_with_a_tree_error: 0,
  word_cut_after_an_assignment: 0, word_cut_after_an_assignment_lane_word: 0, shell_c_of_a_cat_heredoc_substitution: 0,
}
for (const text of inputs) {
  const m = kernel.measureTranscript(call(text)).cli_lanes
  if (m.parse_errors) c.with_a_parse_error++
  if (m.calls_with_lane_invocation) c.with_a_lane_invocation++
  if (m.unresolved_programs) { c.with_an_unresolved_program++; if (hasLaneWord(text)) c.unresolved_and_a_lane_word++ }
  if (SHELL_CS.test(text)) c.shell_c_of_a_cat_heredoc_substitution++
  if (text.includes('<<')) c.with_a_heredoc_operator++
  const seen = kernel.withShellTree(text, (root) => {
    const s = { bang: false, bq: false, fold: false, foldLane: false, time: false, early: false, open: false, leading: false, cut: false, cutLane: false, tree: root.hasError }
    const stack = [root]
    while (stack.length) {
      const n = stack.pop()
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
}
console.log(JSON.stringify(c, null, 1))
