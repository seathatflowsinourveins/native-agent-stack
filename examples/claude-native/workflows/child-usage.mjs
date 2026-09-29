#!/usr/bin/env node
// Per-child requested/resolved model, effort, provider usage and lane use for one native
// Workflow run. Reads the run's transcript directory (journal.jsonl,
// agent-<id>.meta.json, agent-<id>.jsonl) and changes nothing.
//   node .claude/workflows/child-usage.mjs <transcriptDir>   (the "Transcript dir" the Workflow tool prints)
//   node .claude/workflows/child-usage.mjs --latest          (newest run recorded for this working directory)
//   add --require-effort max to also fail (exit 1) when any child ran at another effort
//   (docs/decisions/2026-09-23-max-effort-default.md and its 2026-09-29 addendum: a stage without effort runs at its
//   agent's frontmatter effort, else at its model's saved level or default in a headless session, or at the
//   coordinator's xhigh on 2.1.281; CLAUDE_CODE_EFFORT_LEVEL overrides every stage).
//   add --rtk-db <RTK history.db> to join each child Bash call to RTK's hook_decisions row by
//   tool_use_id (opened read-only through node:sqlite), and --marker <text> to look for another
//   injected block than Context Mode's routing block (DEFAULT_MARKER below).
// Lane sweep over explicit roots (a Claude config's projects/ directory, one project or one session):
//   node .claude/workflows/child-usage.mjs --lanes-sweep --root <dir> [--root <dir> ...] --since <ISO> --until <ISO>
//   aggregates the lanes of every workflow and Agent-tool child transcript under the roots, counting only
//   rows inside [since, until), and prints names and counts only: no paths, ids, labels or transcript text.
// Streamed assistant lines repeat a message id, so usage is counted once per id
// (largest output_tokens wins). Counters are provider-returned and kept per type;
// they are not comparable to RTK/Context Mode/jCodeMunch/Headroom estimates.
// Exit 1 when any child is incomplete (null result, no transcript, no usage, a resolved
// model outside the requested family, a resolved model that changes within the child,
// or a model older than the requested alias's documented resolution for the client
// version that wrote the entry). The last two catch content-classifier fallback, which
// re-runs a flagged request on an older model and continues the child there; the
// family substring check alone accepts claude-opus-4-8 for a requested opus.
// An attempt that returned nothing and whose journal key the runtime started again (a re-run
// after a usage-limit pause) is listed under superseded_attempts with superseded_by, keeps its
// issues and effort check, and its usage counts in by_resolved_model, whose `children` counter
// counts attempts; `children` holds the final attempt of each call. Its usage-integrity failures
// (usage_issues: an assistant message without provider usage or without a resolved model, or no
// transcript at all) leave the run incomplete, because by_resolved_model cannot count that usage;
// its other issues (no result, the <synthetic> usage-limit row) are expected of such an attempt.
// web_search (per attempt and per run) counts WebSearch calls and the capped ones: a session makes at
// most CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION WebSearch calls (default 200), counted across the main
// conversation and every subagent, and a capped call returns a notice instead of results (tools-reference,
// "Session search limit"). A capped call changes no usage and no exit code; callers decide what it means.
import { readFileSync, existsSync, readdirSync, statSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { homedir, tmpdir } from 'node:os'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'

const COUNTERS = ['input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']
const PROMPT_COUNTERS = ['input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']
const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']
const readRows = (file) => {
  let errors = 0
  const rows = []
  const bytes = readFileSync(file)
  for (const l of bytes.toString('utf8').split('\n')) {
    if (!l.trim()) continue
    try { rows.push(JSON.parse(l)) } catch { errors++ }
  }
  return { rows, errors, digest: createHash('sha256').update(bytes).digest('hex') }
}
const lines = (file) => readRows(file).rows.filter(Boolean)
// Client-written rows (an API error such as a usage-limit notice) carry this model; the
// family check still reports them, and the two fallback checks below ignore them.
const SYNTHETIC = '<synthetic>'
// Documented resolution of an alias on the Anthropic API by the client version that wrote the
// transcript entry, as [first client version, model] rows in ascending order (model-config doc,
// "version history" table, fetched 2026-09-29: opus is Opus 5.5 from v2.1.280, Opus 5 from v2.1.219, Opus 4.8
// from v2.1.154; sonnet is Sonnet 5.5 from v2.1.284, Sonnet 5 from v2.1.197; fable is Fable 5.1 from v2.1.257).
// An entry older than the first row, and an alias without rows (haiku, or any alias not listed here),
// has no expectation. An ANTHROPIC_DEFAULT_OPUS_MODEL pin to an older model would be flagged; none is set here. The sub-agents
// doc ("Choose a model") adds one exception: a family alias resolves to the lead's exact model when the lead belongs to that
// family, so a `sonnet` child under a lead pinned to an older Sonnet is flagged here although the client did as documented.
export const ALIAS_RESOLUTION = { opus: [['2.1.154', 'claude-opus-4-8'], ['2.1.219', 'claude-opus-5'], ['2.1.280', 'claude-opus-5-5']], sonnet: [['2.1.197', 'claude-sonnet-5'], ['2.1.284', 'claude-sonnet-5-5']], fable: [['2.1.257', 'claude-fable-5-1']] }
const semver = (v) => { const m = /^(\d+)\.(\d+)\.(\d+)/.exec(typeof v === 'string' ? v : ''); return m ? m.slice(1).map(Number) : null }
const compareParts = (a, b) => { for (let i = 0; i < Math.max(a.length, b.length); i++) { const d = (a[i] || 0) - (b[i] || 0); if (d) return d < 0 ? -1 : 1 } return 0 }
// claude-opus-5-5 -> { family: 'opus', version: [5, 5] }; a date suffix and a [1m] suffix are ignored; other shapes -> null.
export function modelGeneration(model) {
  const m = /^claude-([a-z]+)-(\d{1,2})(?:-(\d{1,2}))?(?:-\d{8})?(?:\[[^\]]*\])?$/.exec(String(model))
  return m ? { family: m[1], version: [Number(m[2]), ...(m[3] ? [Number(m[3])] : [])] } : null
}
export function expectedModel(alias, clientVersion) {
  const rows = ALIAS_RESOLUTION[String(alias).toLowerCase()], v = semver(clientVersion)
  if (!rows || !v) return null
  let hit = null
  for (const [from, model] of rows) if (compareParts(v, semver(from)) >= 0) hit = model
  return hit
}
// True when `model` cannot be shown to be at least as new as `expected` (a different family or an unparseable name fails closed).
export function olderThan(model, expected) {
  const got = modelGeneration(model), want = modelGeneration(expected)
  return !got || !want || got.family !== want.family || compareParts(got.version, want.version) < 0
}

// The capped-call notice opens the tool result's result section, after the "Web search results for query: ..."
// header line (observed with client 2.1.283: "Web search was not performed: this session has used its web search
// budget (200 of 200 WebSearch calls). ..."). Page text that merely quotes the notice is not a capped call.
export const WEB_SEARCH_CAPPED = 'Web search was not performed'
const WEB_SEARCH_HEADER = 'Web search results for query:'
const resultText = (content) => typeof content === 'string' ? content : Array.isArray(content) ? content.map((b) => (b && typeof b.text === 'string' ? b.text : '')).join('\n') : ''
export function webSearch(transcript) {
  const calls = new Map()
  const blocks = (row) => (row && row.message && Array.isArray(row.message.content) ? row.message.content : []).filter((b) => b && typeof b === 'object')
  for (const row of transcript) for (const b of blocks(row)) if (b.type === 'tool_use' && b.name === 'WebSearch' && typeof b.id === 'string') calls.set(b.id, null)
  const cappedAt = []
  for (const row of transcript) for (const b of blocks(row)) {
    if (b.type !== 'tool_result' || !calls.has(b.tool_use_id) || calls.get(b.tool_use_id) !== null) continue
    const text = resultText(b.content)
    const cut = text.indexOf('\n\n')
    const body = text.startsWith(WEB_SEARCH_HEADER) && cut >= 0 ? text.slice(cut + 2) : text
    const capped = body.startsWith(WEB_SEARCH_CAPPED)
    calls.set(b.tool_use_id, capped)
    if (capped) cappedAt.push(typeof row.timestamp === 'string' ? row.timestamp : null)
  }
  const times = cappedAt.filter(Boolean).sort()
  return { calls: calls.size, capped: cappedAt.length, first_capped_at: times[0] ?? null }
}

// ------------------------------------------------------------------ lanes
// The injected-block marker: the opening tag of Context Mode's routing block (context-mode 1.0.169,
// hooks/routing-block.mjs createRoutingBlock), which its PreToolUse hook writes into Agent-tool prompts.
export const DEFAULT_MARKER = '<context_window_protection>'
// curl or wget in command position: at a line start or after ; & | ( ` or $(, optionally behind the shell
// keywords do, then, else, elif, if, while, until, ! and {, and behind rtk, sudo, env, command, exec, time, nice,
// nohup or `timeout <n>`. Other wrappers (xargs, env VAR=x, nice -n N) are not recognized.
const FETCH_WORD = /(?:^|[;&|(`]|\$\()\s*(?:(?:do|then|else|elif|if|while|until|!|\{|rtk|sudo|env|command|exec|time|nice|nohup|timeout\s+\S+)\s+)*(?:curl|wget)(?=\s|$)/m
const URL_HOST = /\bhttps?:\/\/(\[[^\]\s]*\]|[^\s/:'"`<>)?#\]]+)/gi
const LOOPBACK = /^(?:localhost|127(?:\.\d{1,3}){3}|\[::1\]|0\.0\.0\.0)$/i
// A quoted string a shell runs: the argument of sh/bash/zsh/dash/ksh/su ... -c, of eval, or of ssh <host>. The command name sits at the
// text start, after a blank, ; & | ( or the opening backquote of a `...` substitution.
const RUN_QUOTED = /(?:^|[\s;&|(`])(?:(?:(?:ba|z|da|k)?sh|su)(?:\s+-[A-Za-z]+)*\s+-[A-Za-z]*c|eval|ssh(?:\s+-\S+)*\s+\S+)\s*$/
// Inline interpreter code remains executable despite its shell quoting; all other
// quoted arguments stay data. Extend context-mode v1.0.169 routing.mjs:787-797
// with documented interpreter entrypoints: docs.python.org/3.14/using/cmdline.html,
// nodejs.org/docs/latest-v24.x/api/cli.html, docs.deno.com/runtime/reference/cli/eval/,
// and bun.sh/docs/runtime. HTTP operations remain unclassifiable under #381 M4.
// An option word is -[\w-]+: the same words as --?[\w-]+, which splits '---' two ways and backtracks
// exponentially on repeated option words (CodeQL js/redos).
const RUN_HTTP_CODE = /(?:^|[\s;&|(`])(?:python[\d.]*(?:\s+-[A-Za-z]+)*\s+-[A-Za-z]*c|node(?:js)?(?:\s+-[\w-]+)*\s+(?:-e|--eval|-p|--print)|bun(?:\s+-[\w-]+)*\s+(?:-e|--eval)|deno\s+eval(?:\s+-[\w-]+)*)\s*$/
const SHELL = /^(?:ba|z|da|k)?sh$/
const INTERPRETER_WORD = /^(?:python[\d.]*|node(?:js)?|deno|bun|ruby|perl|php)$/
// A here-document operator and its delimiter word at lastIndex (bash(1) Here Documents).
const HEREDOC = /<<(-?)\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\2/y
const WRAPPERS = new Set(['sudo', 'env', 'command', 'exec', 'nice', 'nohup', 'time', 'rtk'])
const RESERVED = new Set(['!', '{', 'do', 'then', 'else', 'elif', 'if', 'while', 'until']) // bash(1) RESERVED WORDS
// Shell text is read by bash(1) (GNU bash 5.2) QUOTING, COMMENTS and Here Documents: an escaped character is literal and
// \<newline> is a line continuation; a word beginning with # ends the line as a comment; inside double quotes, and in the
// body of a heredoc whose delimiter is unquoted, $(...) and `...` still run, while \$ and \` are literal.
const SUBSTITUTION = /\\[\s\S]|\$\([^()]*\)|`[^`]*`/g
const ESCAPED_DATA = new Set([...' \t;&|()<>`$\'"\\#{}!']) // escaped, these become the data character _
const WORD_BREAK = new Set([...' \t\n;&|()<>']) // bash metacharacters: a # after one begins a comment
const QUOTED_SEPARATOR = new Set([...';&|()`\n']) // in double-quoted data, these become a space
// Nested analyses (a heredoc body a shell reads, a string a shell runs, a "$( )" body inside double quotes) deeper than
// this read as data, which errs toward possible fetches. The limit bounds the recursion; each level scans linearly.
const NESTING_LIMIT = 32
// For each "(" of a text, the index of the ")" that closes it within its line, else -1 (the classic parenthesis matching of
// bash(1) ARITHMETIC EVALUATION's `(( ))` and `$(( ))` look-ahead, which counts every ( and ) up to the end of the line). One
// linear pass per text, so a run of unclosed "((" does not look ahead to the end of its line once per opener (U1 pivot D8,
// GPT-6 #9: n = 8000, 16000 and 32000 took 315, 1100 and 5000 ms). The last few texts stay memoized, which is enough for the
// scans that alternate between a text and its slices; the memo is cleared when a top-level analysis ends (executedTrace).
const PAREN_MEMO = []
function parenClose(s) {
  for (const entry of PAREN_MEMO) if (entry[0] === s) return entry[1]
  const table = new Int32Array(s.length).fill(-1), open = []
  for (let k = 0; k < s.length; k++) {
    const c = s.charCodeAt(k)
    if (c === 10) open.length = 0
    else if (c === 40) open.push(k)
    else if (c === 41 && open.length) table[open.pop()] = k
  }
  if (PAREN_MEMO.length === 8) PAREN_MEMO.shift()
  PAREN_MEMO.push([s, table])
  return table
}
// Whether s[k] is escaped: an odd number of backslashes end just before it (bash(1) QUOTING: a backslash escapes the next
// character, and a backslash-newline is a line continuation). An escaped blank, metacharacter or newline does not end a word,
// so a # after it starts no comment (R3: `x="$(echo a\ #b)"` is one word, and its ) and closing quote still count). Each run of
// backslashes is read once, for the one # that follows its word break, so the scan stays linear.
function escapedAt(s, k) {
  let n = 0
  for (let j = k - 1; j >= 0 && s[j] === '\\'; j--) n++
  return n % 2 === 1
}
// One unit of shell text under a stack of open frames (POSIX.1-2024 XCU 2.2 Quoting and 2.6.3 Command Substitution;
// bash(1) QUOTING, COMMENTS, ARITHMETIC EVALUATION and Here Documents). A frame is "'" (literal up to the next '), '"'
// (a backslash escapes the next unit; "$(" not followed by "(" opens a $( frame, a backquote a ` frame), '`' (up to the
// next unescaped backquote) or a $( frame { depth }. With no frame, or in a $( frame, the command rules apply: quotes
// open frames, a # at a word start comments out the rest of the line, $(( )) and (( )) are skipped within their line,
// <<< is a here-string and << or <<- a here-document operator; in a $( frame "(" adds one to depth and ")" at depth 0
// closes the frame. step() updates `stack` and returns the index after the unit. `on` receives each here-document
// operator and each cut: a control operator (bash(1) DEFINITIONS: || & && ; ;; ( ) | |& and newline; the & and | of
// the redirections >& <& &> >| are not), the ( of a "$(" inside double quotes and the ) that closes it. A cut is made at the
// level of the frame it belongs to (on.cut(i, frame): the $( frame the unit sits in, undefined for the top level; for the ( and
// ) of a "$( )" the frame that ( opens and ) closes), so the cuts of a substitution bound the commands inside it and never the
// command that contains the substitution (U1 pivot R1).
function step(s, i, stack, on) {
  const top = stack[stack.length - 1], ch = s[i]
  if (top === "'") { if (ch === "'") stack.pop(); return i + 1 }
  if (top === '`') { if (ch === '`') stack.pop(); return ch === '\\' ? i + 2 : i + 1 }
  if (top === '"') {
    if (ch === '\\') return i + 2
    if (ch === '"') stack.pop()
    else if (ch === '`') stack.push('`')
    else if (ch === '$' && s[i + 1] === '(' && s[i + 2] !== '(') { const frame = { depth: 0 }; stack.push(frame); on?.cut(i + 1, frame); return i + 2 }
    return i + 1
  }
  if (ch === '\\') return i + 2
  if (ch === "'" || ch === '"') { stack.push(ch); return i + 1 }
  if (ch === '#' && (i === 0 || (WORD_BREAK.has(s[i - 1]) && !escapedAt(s, i - 1)))) { const end = s.indexOf('\n', i); return end < 0 ? s.length : end }
  const arithmetic = ch === '$' && s.startsWith('((', i + 1) ? i + 1 : ch === '(' && s[i + 1] === '(' ? i : -1
  if (arithmetic >= 0) {
    const close = parenClose(s)[arithmetic]
    if (close >= 0) return close + 1
  }
  if (s.startsWith('<<<', i)) return i + 3
  if (ch === '<') { HEREDOC.lastIndex = i; const h = HEREDOC.exec(s); if (h) { on?.heredoc(i, h); return i + h[0].length } }
  if (top && ch === '(') top.depth++
  else if (top && ch === ')' && top.depth-- === 0) stack.pop()
  const prev = s[i - 1], next = s[i + 1]
  if ('|&;()`'.includes(ch) && !(ch === '&' && (prev === '>' || prev === '<' || next === '>')) && !(ch === '|' && prev === '>')) on?.cut(i, top)
  return i + 1
}
// Here-document openers in one kept line outside quotes, comments and $(( )), each with the bounds of the simple command
// that contains it: the text between the nearest cuts of its own level (step), the line start and end bounding every level.
// `stack` holds the frames earlier kept lines left open and is updated in place: a << inside a quote stays with the
// quoted-string analysis, while a << inside a "$( )" that a double-quoted word opens is found here, as in an unquoted $( )
// (POSIX.1-2024 XCU 2.6.3: tokenized recursively). Limit: a command that a quote, backquote or "$( )" carries over lines
// (`x="$(cat <<'A' ... \n)" bash <<'B'`) begins on an earlier line, and this line alone gives the operator no reader, so its
// body reads as data: a possible fetch in the lower bound, never a lost one (measured: reading the tail alone names the wrong
// owner as often as the right one, e.g. `ssh host cat "a\nb" bash <<EOF`).
function openers(line, stack) {
  const found = [], cuts = new Map()
  const on = {
    cut: (i, frame) => { const level = frame ?? null, list = cuts.get(level); if (list) list.push(i); else cuts.set(level, [-1, i]) },
    heredoc: (i, h) => { found.push({ start: i, end: i + h[0].length, strip: h[1] === '-', quoted: h[2] !== '', delimiter: h[3], level: stack[stack.length - 1] ?? null }) },
  }
  for (let i = 0; i < line.length;) i = step(line, i, stack, on)
  return found.map(({ level, ...h }) => {
    const list = cuts.get(level) ?? [-1], before = firstFrom(list, h.start), after = firstFrom(list, h.end) // ascending lists
    return { ...h, from: list[before - 1] + 1, to: after < list.length ? list[after] : line.length }
  })
}
// The index of the first element of the ascending `list` that is at least `x` (binary search), so a line of many cuts and many
// openers is bounded in O(n log n), not once per opener over every cut.
function firstFrom(list, x) {
  let lo = 0, hi = list.length
  while (lo < hi) { const mid = (lo + hi) >> 1; if (list[mid] < x) lo = mid + 1; else hi = mid }
  return lo
}
// Where the frame that `stack` opens at s[i] ends: the index of the unit that pops it (a closing quote or backquote, or
// the ")" of a $( frame), or s.length when the text ends first. One scan, whatever the nesting.
function frameEnd(s, i, stack) {
  for (let next; i < s.length; i = next) { next = step(s, i, stack); if (!stack.length) return i }
  return s.length
}
const closeQuote = (s, i) => frameEnd(s, i + 1, [s[i]]) // s[i] is ', " or `
const matchParen = (s, i) => frameEnd(s, i, [{ depth: 0 }]) // s[i] follows the "$("
// The words of one simple command with quotes removed and every redirection and its target dropped (bash(1)
// REDIRECTION: [n]< [n]> [n]>| [n]>> &> &>> [n]<< [n]<<- [n]<<< [n]<& [n]>& [n]<>). A "$( )" or backquoted span inside double
// quotes is one unit of its word, whatever quotes and blanks it holds (POSIX.1-2024 XCU 2.6.3: its text is tokenized on its own).
const REDIRECTION = /(?:\d*(?:<<-|<<<|<<|<>|<&|>&|>>|>\||<|>)|&>>?)/y
function commandWords(text) {
  const words = []
  let target = false
  for (let i = 0; i < text.length;) {
    if (/\s/.test(text[i])) { i++; continue }
    REDIRECTION.lastIndex = i
    const r = REDIRECTION.exec(text)
    if (r) { i += r[0].length; target = true; continue }
    let word = ''
    while (i < text.length && !/[\s<>]/.test(text[i])) {
      const ch = text[i]
      if (ch === "'") { const end = text.indexOf("'", i + 1) < 0 ? text.length : text.indexOf("'", i + 1); word += text.slice(i + 1, end); i = end + 1 }
      else if (ch === '"') {
        for (i++; i < text.length && text[i] !== '"';) {
          const c = text[i]
          if (c === '\\' && i + 1 < text.length) { word += text[i + 1]; i += 2 }
          else if (c === '$' && text[i + 1] === '(' && text[i + 2] !== '(') { const k = Math.min(matchParen(text, i + 2) + 1, text.length); word += text.slice(i, k); i = k }
          else if (c === '`') { const k = Math.min(closeQuote(text, i) + 1, text.length); word += text.slice(i, k); i = k }
          else { word += c; i++ }
        }
        i++
      }
      else if (ch === '\\') { word += text[i + 1] ?? ''; i += 2 }
      else { word += ch; i++ }
    }
    if (target) target = false
    else words.push(word)
  }
  return words
}
// The invoked program and its arguments: assignments, options before it, wrappers, reserved words and a timeout
// duration skipped.
const invocationOf = (words) => {
  for (let i = 0; i < words.length; i++) {
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[i]) || words[i].startsWith('-') || WRAPPERS.has(words[i]) || RESERVED.has(words[i])) continue
    if (words[i] === 'timeout') { i++; continue }
    return { program: words[i].split('/').pop(), args: words.slice(i + 1) }
  }
  return { program: '', args: [] }
}
// The program that runs a heredoc (its stdin) as source, or '' when stdin stays data.
// Shells, POSIX.1-2024 utilities/sh.html OPTIONS/STDIN and bash(1) 5.2 OPTIONS/ARGUMENTS: stdin is the script unless -c
// supplies a command string or an operand names a script file; -s keeps stdin, a shell's `-` equals `--`, -o/+o/-O/+O
// take a name, --rcfile/--init-file take a file, and -n/-D read commands without executing them.
// ssh, OpenSSH ssh(1) 9.6p1: without a remote command the remote login shell reads stdin; otherwise the command
// (its arguments joined by spaces) must read stdin as source. -n and -f (which implies -n) keep stdin unread, and
// -N, -s, -W, -O, -G, -V and -Q run no remote command. Options may follow the destination (ssh.c parses them again).
// Interpreters, Python 3.13 using/cmdline.html#interface-options and Node v24.21.0 api/cli.html#-: no script operand
// or `-`. Any other invocation keeps the body as data; the raw scan in countFetches still counts the body's
// HTTP_SCRIPT, command-position curl/wget and gh api matches as possible fetches.
const SSH_VALUE = new Set([...'BbcDEeFIiJLlmOoPpQRSWw']), SSH_NO_STDIN = new Set([...'fGNnOQsVW'])
function stdinProgram({ program, args }) {
  if (SHELL.test(program)) {
    let stdin = false
    for (let i = 0; i < args.length; i++) {
      const arg = args[i]
      if (arg === '--' || arg === '-') return stdin || i + 1 === args.length ? program : ''
      if (arg === '--rcfile' || arg === '--init-file') { i++; continue }
      if (arg.startsWith('--')) continue
      if (!/^[-+][A-Za-z]+$/.test(arg)) return stdin ? program : ''
      if (arg[0] === '-' && /[cnD]/.test(arg)) return ''
      stdin ||= arg[0] === '-' && arg.includes('s')
      i += (arg.match(/[oO]/g) || []).length
    }
    return program
  }
  if (program === 'ssh') {
    let destination = null, i = 0
    for (; i < args.length; i++) {
      const arg = args[i]
      if (arg === '--') { if (destination === null) destination = args[++i] ?? null; i++; break }
      if (/^-./.test(arg)) {
        for (let k = 1; k < arg.length; k++) {
          if (SSH_NO_STDIN.has(arg[k])) return ''
          if (SSH_VALUE.has(arg[k])) { if (k === arg.length - 1) i++; break }
        }
        continue
      }
      if (destination !== null) break
      destination = arg
    }
    if (destination === null) return ''
    const remote = args.slice(i).join(' ')
    if (!remote.trim()) return 'sh'
    for (const part of remote.split(/&&|\|\||[;&|()]/)) { const reader = stdinProgram(invocationOf(commandWords(part))); if (reader) return reader }
    return ''
  }
  if (program === 'deno' || program === 'bun') return args.length === 2 && args[0] === 'run' && args[1] === '-' ? program : ''
  if (!INTERPRETER_WORD.test(program)) return ''
  const python = /^python[\d.]*$/.test(program)
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (arg === '--') return i + 1 === args.length || args[i + 1] === '-' ? program : ''
    if (arg === '-') return program
    if (python && /^-[bBdEiIOPqRsSuvx]+$/.test(arg)) continue
    return ''
  }
  return program
}
// Traced text keeps, for every UTF-16 unit, its offset in the raw command (-1 for a separator the analysis inserts),
// so a detector match in executed text can be traced back to the raw match it confirms (countFetches).
const traced = (s) => ({ s, p: Array.from({ length: s.length }, (_, i) => i) })
const slice = (t, a, b) => ({ s: t.s.slice(a, b), p: t.p.slice(a, b) })
const append = (out, t) => { out.s += t.s; for (const n of t.p) out.p.push(n) }
const insert = (out, s) => { out.s += s; for (let i = 0; i < s.length; i++) out.p.push(-1) }
const joined = (parts, separator) => { const out = { s: '', p: [] }; parts.forEach((t, k) => { if (k) insert(out, separator); append(out, t) }); return out }
// The command text a shell would run: a heredoc body is data unless the heredoc's simple command runs its stdin as a
// shell script (or as interpreter source in inlineHttp mode), though with an unquoted delimiter its command
// substitutions still run; a quoted string is data unless a shell runs it (RUN_QUOTED), when it is analyzed as that
// shell's input, though inside double quotes $(...) and `...` still run, and the body of "$( ... )" is analyzed as
// shell text (POSIX.1-2024 XCU 2.6.3); an escaped character and a comment are data, and \<newline> joins lines. Data
// keeps its words (so URL arguments stay) but loses the separators that would put a word in command position.
export function executedText(command, { inlineHttp = false } = {}) {
  return executedTrace(traced(String(command || '')), inlineHttp).s
}
// `resolved` holds the raw offsets of the here-document operators already resolved; every nested analysis shares it.
function executedTrace(src, inlineHttp, resolved = new Set(), depth = 0) {
  try {
    const { text, sources } = resolveHeredocs(src, inlineHttp, resolved, depth)
    return joined([scanQuotes(text, inlineHttp, resolved, depth), ...sources], '\n')
  } finally { if (depth === 0) PAREN_MEMO.length = 0 }
}
// Phase 1, line by line: a here-document body becomes its data (the substitutions an unquoted delimiter still runs) or,
// when a shell (or in inlineHttp mode an interpreter) reads it as source, a separate source. An operator that is already
// resolved is skipped: the outer shell resolves a heredoc inside the "$( )" of a double-quoted string that a shell then
// runs, and the lines after it must not be read as its body a second time.
function resolveHeredocs(src, inlineHttp, resolved, depth) {
  const lines = [], kept = [], sources = [], stack = []
  for (let at = 0; ;) { const end = src.s.indexOf('\n', at); lines.push([at, end < 0 ? src.s.length : end]); if (end < 0) break; at = end + 1 }
  const lineText = (n) => src.s.slice(lines[n][0], lines[n][1])
  for (let n = 0; n < lines.length; n++) {
    const line = lineText(n), found = openers(line, stack)
    kept.push(slice(src, lines[n][0], lines[n][1]))
    for (const h of found) { // bodies follow the opener line in order (bash(1) Here Documents)
      const operator = src.p[lines[n][0] + h.start]
      if (resolved.has(operator)) continue
      resolved.add(operator)
      const command = invocationOf(commandWords(line.slice(h.from, h.to))), reader = stdinProgram(command)
      const source = depth < NESTING_LIMIT && (SHELL.test(reader) || inlineHttp && INTERPRETER_WORD.test(reader))
      const first = n + 1
      while (n + 1 < lines.length && (h.strip ? lineText(n + 1).replace(/^\t+/, '') : lineText(n + 1)) !== h.delimiter) {
        n++
        if (source) continue
        const data = { s: '', p: [] }
        if (!h.quoted) for (const m of lineText(n).matchAll(SUBSTITUTION)) if (m[0][0] !== '\\') {
          if (data.s) insert(data, ' ')
          append(data, slice(src, lines[n][0] + m.index, lines[n][0] + m.index + m[0].length))
        }
        kept.push(data)
      }
      // Keep source boundaries: interpreter quotes/shift syntax must not consume later shell commands or data
      // heredocs. Each source is analyzed independently; missed matches stay possible M4 fetches.
      if (source && n >= first) {
        const body = slice(src, lines[first][0], lines[n][1])
        if (h.quoted) {
          sources.push(executedTrace(body, inlineHttp, resolved, depth + 1))
        } else {
          // Two views, as for a double-quoted string a shell runs (D7; bash(1) Here Documents, POSIX.1-2024 XCU 2.7.4): the shell that
          // read the command line expands an unquoted-delimiter body first (each unescaped $( ) and backquote runs there, whatever
          // its quotes or a comment say), and the shell that reads the heredoc sees the expanded text.
          const spans = outerSpans(body.s, depth), view = withoutSpans(body, spans)
          for (const span of spans) sources.push(outerBody(body, span, inlineHttp, resolved, depth))
          sources.push(executedTrace(heredocText(view), inlineHttp, resolved, depth + 1))
        }
      } else if (source) sources.push({ s: '', p: [] })
      if (n + 1 < lines.length) n++ // closing delimiter
    }
  }
  return { text: joined(kept, '\n'), sources }
}
// Only the end of the text built so far decides whether a quote opens a run string (RUN_QUOTED, RUN_HTTP_CODE), and reading
// out.s for it flattens the whole concatenation and scans it once per quote: quadratic on a long script (a 346 KB script took 2 s
// a scan, and the kernel scans each shell call several times). scanQuotes keeps that end in `tail`, a string of at most 2 * TAIL
// characters cut back to TAIL, and reads only it. Once a cut has been made the detectors run without their start-of-text
// alternative (a cut is no start of text). Work budget (D8): scanQuotes also notes, outside quotes, when a shell, eval, ssh or su
// word has been written since the last command separator; when a cut has left the tail without that word and without a separator,
// the next quote that does not read as a run string is counted once in `windowMisses` (countFetches adds it to unclassifiable, an
// operation of unknown kind) instead of being read as data with no trace. Only a single ssh option word longer than TAIL does this
// (`ssh -oProxyCommand=<1500 characters> host "curl u"`): the words between a shell, eval or ssh and its string are short options and
// one host.
const TAIL = 512
const withoutStart = (re) => new RegExp(re.source.replace('^|', ''))
const RUN_QUOTED_CUT = withoutStart(RUN_QUOTED), RUN_HTTP_CODE_CUT = withoutStart(RUN_HTTP_CODE)
const SEPARATOR = /[;&|(`\n]/
const RUN_WORD_DONE = /(?:^|[\s;&|(`])(?:(?:ba|z|da|k)?sh|su|eval|ssh)\s$/ // the last characters written: a run word, then its blank
const RUN_WORD_END = new Set(['h', 'u', 'l']) // the last letter of sh, bash, zsh, dash, ksh, ssh, su and eval
const RUN_WORD_IN = /[\s;&|(`](?:(?:ba|z|da|k)?sh|su|eval|ssh)(?=\s)/
let windowMisses = 0
// Phase 2 over the kept text: escapes, comments and quoted strings. A quoted string that a shell runs is analyzed as
// that shell's input, with its own heredocs; a double-quoted one first loses the backslashes the outer shell removes.
function scanQuotes(text, inlineHttp, resolved, depth) {
  const out = { s: '', p: [] }
  let tail = '', cut = false, word = false // word: a run word was written outside quotes since the last command separator
  const note = (s) => {
    if (word && SEPARATOR.test(s)) word = false
    tail += s
    if (tail.length > 2 * TAIL) { tail = tail.slice(-TAIL); cut = true }
  }
  const put = (s) => { insert(out, s); note(s) }
  const putTrace = (t) => { append(out, t); note(t.s) }
  for (let i = 0; i < text.s.length; i++) {
    const ch = text.s[i]
    if (ch === '\\') {
      const next = text.s[i + 1]
      if (next !== undefined && next !== '\n') { const c = ESCAPED_DATA.has(next) ? '_' : next; out.s += c; out.p.push(text.p[i + 1]); note(c) }
      i++
      continue
    }
    if (ch === '#' && (out.p.length === 0 || WORD_BREAK.has(tail[tail.length - 1]))) {
      while (i + 1 < text.s.length && text.s[i + 1] !== '\n') i++
      continue
    }
    if (ch !== "'" && ch !== '"') {
      out.s += ch; out.p.push(text.p[i]); note(ch)
      if ((ch === ' ' || ch === '\t' || ch === '\n') && RUN_WORD_END.has(tail[tail.length - 2]) && RUN_WORD_DONE.test(tail.length > 8 ? tail.slice(-8) : tail)) word = true
      continue
    }
    const j = closeQuote(text.s, i), inner = slice(text, i + 1, j)
    const run = depth < NESTING_LIMIT ? (cut ? RUN_QUOTED_CUT : RUN_QUOTED).exec(tail) : null
    if (word && cut && !run && !SEPARATOR.test(tail) && !RUN_WORD_IN.test(tail)) { windowMisses++; word = false }
    if (run) {
      if (ch === '"') {
        // Two views of a double-quoted string a shell runs (POSIX.1-2024 XCU 2.2.3 and 2.6.3; U1 pivot D7, GPT-6 #8): the shell
        // that expands the word runs each unescaped "$( )" and backquoted span itself, before the shell it starts reads anything,
        // whatever that shell then makes of the text; that shell reads the string with each of them replaced by its output,
        // which is unknown, so a placeholder word. The outer bodies come first, as they run, each as commands of their own.
        const spans = outerSpans(inner.s, depth), view = withoutSpans(inner, spans)
        for (const span of spans) { put(';'); putTrace(outerBody(inner, span, inlineHttp, resolved, depth)); put(';') }
        put(';'); putTrace(executedTrace(unquoted(view), inlineHttp, resolved, depth + 1)); put(';')
      } else {
        put(';'); putTrace(executedTrace(inner, inlineHttp, resolved, depth + 1)); put(';')
      }
    } else if (inlineHttp && (cut ? RUN_HTTP_CODE_CUT : RUN_HTTP_CODE).test(tail)) { put(';'); putTrace(inner); put(';') }
    else if (ch === '"') { const data = { s: '', p: [] }; quotedData(data, inner, inlineHttp, resolved, depth); put('"'); putTrace(data); put('"') }
    else { put("'"); putTrace({ s: inner.s.replace(/[;&|()`$\n]/g, ' '), p: inner.p }); put("'") }
    i = j
  }
  return out
}
// The substitutions of a double-quoted string that the shell expanding it runs, in order (POSIX.1-2024 XCU 2.2.3 and 2.6.3):
// each "$( ... )" and each backquoted span outside an escape, as { from, to, body: [start, end), kind }. A "$((" opens an
// arithmetic expansion, not a substitution, though the substitutions inside it are found. A "$(" at NESTING_LIMIT is not
// followed (its text then reads as data), and text that ends first ends the span there. One scanner serves both views of a string.
function outerSpans(s, depth) {
  const spans = []
  for (let i = 0; i < s.length;) {
    const ch = s[i]
    if (ch === '\\' && i + 1 < s.length) i += 2
    else if (ch === '$' && s[i + 1] === '(' && s[i + 2] !== '(' && depth < NESTING_LIMIT) {
      const k = matchParen(s, i + 2)
      spans.push({ from: i, to: Math.min(k + 1, s.length), body: [i + 2, k], kind: '$' })
      i = k + 1
    } else if (ch === '`') {
      const k = closeQuote(s, i)
      spans.push({ from: i, to: Math.min(k + 1, s.length), body: [i + 1, k], kind: '`' })
      i = k + 1
    } else i++
  }
  return spans
}
// `inner` with each span replaced by the placeholder word _ (inserted text: offset -1), the string a shell reads once the
// shell that expanded it has run its substitutions.
function withoutSpans(inner, spans) {
  if (!spans.length) return inner
  const out = { s: '', p: [] }
  let at = 0
  for (const span of spans) { append(out, slice(inner, at, span.from)); insert(out, '_'); at = span.to }
  append(out, slice(inner, at, inner.s.length))
  return out
}
// The text a shell reads from an unquoted-delimiter heredoc body once the shell that expanded it has run: a backslash before $ ` \
// or a newline is removed, and an escaped newline with it (bash(1) Here Documents); quotes are literal in a body, and any other
// backslash stays. Offsets stay raw.
function heredocText(t) {
  const out = { s: '', p: [] }
  for (let i = 0; i < t.s.length; i++) {
    if (t.s[i] === '\\' && i + 1 < t.s.length && '$`\\\n'.includes(t.s[i + 1])) { i++; if (t.s[i] === '\n') continue }
    out.s += t.s[i]; out.p.push(t.p[i])
  }
  return out
}
// The commands one outer substitution runs, as executed text. The body of a "$( )" is shell text as written (double quotes leave
// it alone, 2.6.3); a backquoted span first loses the backslash before $ ` \ and " (2.6.3, and 2.2.3 inside double quotes). Any
// heredoc in a body that an outer phase already resolved is in `resolved` and is skipped.
function outerBody(inner, span, inlineHttp, resolved, depth) {
  const [a, b] = span.body
  let body = slice(inner, a, b)
  if (span.kind === '`') {
    const plain = { s: '', p: [] }
    for (let i = 0; i < body.s.length; i++) {
      if (body.s[i] === '\\' && i + 1 < body.s.length && '$`\\"'.includes(body.s[i + 1])) i++
      plain.s += body.s[i]; plain.p.push(body.p[i])
    }
    body = plain
  }
  return executedTrace(body, inlineHttp, resolved, depth + 1)
}
// Double-quoted data keeps its words and loses the separators that would put a word in command position, while its
// command substitutions still run (POSIX.1-2024 XCU 2.2.3): the body of a "$( ... )" is analyzed as shell text, its
// tokens recognized recursively up to the matching ")" (2.6.3; its heredocs were resolved with its lines), a backquoted
// span is kept as it is, and an escaped character becomes the data character _.
function quotedData(out, inner, inlineHttp, resolved, depth) {
  const s = inner.s
  let at = 0
  const literal = (to) => {
    for (let i = at; i < to;) {
      if (s[i] === '\\' && i + 1 < s.length) { out.s += '_'; out.p.push(inner.p[i + 1]); i += 2 }
      else { out.s += QUOTED_SEPARATOR.has(s[i]) ? ' ' : s[i]; out.p.push(inner.p[i]); i++ }
    }
  }
  for (const span of outerSpans(s, depth)) {
    literal(span.from)
    const [a, b] = span.body
    if (span.kind === '$') { append(out, slice(inner, span.from, a)); append(out, scanQuotes(slice(inner, a, b), inlineHttp, resolved, depth + 1)); append(out, slice(inner, b, b + 1)) }
    else append(out, slice(inner, span.from, span.to))
    at = span.to
  }
  literal(s.length)
}
// The string a shell receives from a double-quoted word: a backslash before $ ` " \ or newline is removed, and an
// escaped newline with it (POSIX.1-2024 XCU 2.2.3), except inside a "$( )" or a backquoted span, whose text the double
// quotes leave alone (2.6.3). Offsets stay raw.
function unquoted(inner) {
  const out = { s: '', p: [] }, stack = ['"'], s = inner.s
  for (let i = 0; i < s.length;) {
    if (stack.length === 1 && s[i] === '\\' && i + 1 < s.length && '$`"\\\n'.includes(s[i + 1])) {
      if (s[i + 1] !== '\n') { out.s += s[i + 1]; out.p.push(inner.p[i + 1]) }
      i += 2
      continue
    }
    for (const end = Math.min(step(s, i, stack), s.length); i < end; i++) { out.s += s[i]; out.p.push(inner.p[i]) }
  }
  return out
}
// 'loopback' when every literal URL in an executed curl/wget command is a loopback host, 'fetch' for any
// other executed curl/wget command (a remote URL, or no literal URL), null when the command runs neither.
export function fetchKind(command) {
  const text = executedText(command)
  if (!FETCH_WORD.test(text)) return null
  const hosts = [...text.matchAll(URL_HOST)].map((m) => m[1])
  return hosts.length && hosts.every((h) => LOOPBACK.test(h)) ? 'loopback' : 'fetch'
}
// Report keys come from transcripts (a model can pass any skill name); only name-shaped strings are kept,
// anything else (a path, text, an address) is counted under '(other)'.
const SAFE_KEY = /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,79}$/
export const safeKey = (value) => SAFE_KEY.test(String(value)) ? String(value) : '(other)'
// mcp__<server>__<tool> -> <server> (plugin servers keep their native plugin_<plugin>_<server> segment).
export const mcpServer = (name) => { const m = /^mcp__(.+?)__./.exec(String(name || '')); return m ? safeKey(m[1]) : null }
const textOf = (content) => typeof content === 'string' ? content
  : Array.isArray(content) ? content.map((b) => typeof b === 'string' ? b : b && typeof b.text === 'string' ? b.text : '').join('\n') : ''
const timeOf = (row) => { const t = Date.parse(row && row.timestamp); return Number.isFinite(t) ? t : null }
// Count maps have no prototype, so a key such as "constructor" is an ordinary counter.
const counter = () => Object.create(null)
const bump = (counts, key) => { counts[key] = (counts[key] || 0) + 1 }

// ------------------------------------------------------------------ shell parser
// The CLI-lane reading parses shell text with tree-sitter-bash (tree-sitter/tree-sitter-bash v0.25.1 through web-tree-sitter
// 0.27.0), the grammar OpenAI Codex uses for the same job (openai/codex rust-v0.157.1 codex-rs/shell-command/src/bash.rs,
// tree-sitter-bash = "0.25" at codex-rs/Cargo.toml:522). The install is not vendored: shell-parser.pin.json names the two npm
// packages with their integrity values, the sha256 of every file read, and the install command. loadShellParser() reads each
// pinned file once, checks its sha256 and the integrity values of the install's package-lock.json, and executes only those
// verified bytes (the runtime module is imported from a private copy of them, the runtime and grammar wasm are handed over as
// bytes), so the code that is hashed is the code that runs. Without a verified install nothing is parsed: commandInvocations()
// returns null and measurement reports cli_lanes as parser_unavailable; the old text scanners never count lanes.
// { ok: true, versions, wasm_sha256 } or { ok: false, reason }: not_installed (the directory, a pinned file or the lockfile is
// missing), hash_mismatch (a byte or an integrity value differs from the pin), load_error (anything else, the pin file included),
// or not_loaded (this process never awaited the loader). Results carry no path.
let shellParser = null // the one module-level Parser, or null
let shellRuntime = null // { Parser, language } once initialized: every successful load verifies the same pinned bytes, so it is reused
let shellParserResult = { ok: false, reason: 'not_loaded' }
let openShellTreeCount = 0
const sha256Hex = (bytes) => createHash('sha256').update(bytes).digest('hex')
const missingFile = (e) => e && (e.code === 'ENOENT' || e.code === 'ENOTDIR')
function readShellParserPin() {
  try {
    const pin = JSON.parse(readFileSync(new URL('./shell-parser.pin.json', import.meta.url), 'utf8'))
    const ok = pin && typeof pin === 'object' && pin.packages?.['web-tree-sitter']?.version && pin.packages['tree-sitter-bash']?.version
      && pin.files && typeof pin.files === 'object' && typeof pin.install?.default_directory === 'string'
      && ['web-tree-sitter', 'tree-sitter-bash'].every((n) => typeof pin.packages[n].integrity === 'string')
    return ok ? pin : null
  } catch { return null }
}
async function verifiedShellParser(dir) {
  const pin = readShellParserPin()
  if (!pin) return { ok: false, reason: 'load_error' }
  const root = dir || process.env.CHILD_USAGE_SHELL_PARSER || join(homedir(), pin.install.default_directory)
  const bytes = {}
  let lock
  try {
    for (const rel of Object.keys(pin.files)) bytes[rel] = readFileSync(join(root, rel))
    lock = readFileSync(join(root, pin.install.lockfile || 'package-lock.json'))
  } catch (e) { return { ok: false, reason: missingFile(e) ? 'not_installed' : 'load_error' } }
  if (Object.entries(pin.files).some(([rel, want]) => sha256Hex(bytes[rel]) !== want)) return { ok: false, reason: 'hash_mismatch' }
  let packages
  try { packages = JSON.parse(lock.toString('utf8')).packages } catch { return { ok: false, reason: 'hash_mismatch' } }
  for (const name of ['web-tree-sitter', 'tree-sitter-bash']) {
    const entry = packages?.['node_modules/' + name]
    if (!entry || entry.version !== pin.packages[name].version || entry.integrity !== pin.packages[name].integrity) return { ok: false, reason: 'hash_mismatch' }
  }
  const runtime = 'node_modules/web-tree-sitter/web-tree-sitter', grammar = 'node_modules/tree-sitter-bash/tree-sitter-bash.wasm'
  if (!shellRuntime) {
    const scratch = mkdtempSync(join(tmpdir(), 'shell-parser-'))
    try {
      const file = join(scratch, 'web-tree-sitter.js')
      writeFileSync(file, bytes[runtime + '.js'], { mode: 0o600 })
      const { Parser, Language } = await import(pathToFileURL(file).href)
      await Parser.init({ wasmBinary: bytes[runtime + '.wasm'], locateFile: (name) => name })
      shellRuntime = { Parser, language: await Language.load(new Uint8Array(bytes[grammar])) }
    } finally { rmSync(scratch, { recursive: true, force: true }) }
  }
  shellParser = new shellRuntime.Parser()
  shellParser.setLanguage(shellRuntime.language)
  return { ok: true, versions: { tree_sitter_bash: pin.packages['tree-sitter-bash'].version, web_tree_sitter: pin.packages['web-tree-sitter'].version },
    wasm_sha256: { tree_sitter_bash: sha256Hex(bytes[grammar]), web_tree_sitter: sha256Hex(bytes[runtime + '.wasm']) } }
}
// Directory order: the argument (the --shell-parser flag of the CLI), then CHILD_USAGE_SHELL_PARSER, then the ecosystem tools
// directory under HOME that the pin names. A failed load leaves no parser loaded, whatever an earlier call did.
export async function loadShellParser(dir) {
  if (shellParser) { shellParser.delete(); shellParser = null }
  try { shellParserResult = await verifiedShellParser(dir) } catch { shellParser = null; shellParserResult = { ok: false, reason: 'load_error' } }
  return shellParserResult
}
// The result of the last loadShellParser() call (not_loaded before the first).
export const shellParserStatus = () => shellParserResult
// Runs `visit` on the root node of the parse tree of `command` and frees the tree when it returns or throws; null when no parser
// is loaded. The visitor must not keep a node or return one: nodes end with their tree.
const parseShell = (text) => { try { return shellParser ? shellParser.parse(text) : null } catch { return null } }
export function withShellTree(command, visit) {
  if (!shellParser) return null
  const tree = parseShell(String(command ?? ''))
  if (!tree) throw new Error('shell parser returned no tree')
  openShellTreeCount++
  try { return visit(tree.rootNode) } finally { tree.delete(); openShellTreeCount-- }
}
export const openShellTrees = () => openShellTreeCount

// ------------------------------------------------------------------ CLI lanes
// #381 AA-PLAN PR-A item 3 (private Gate A spec): count the CLI lanes toon, repomix, markitdown, qmd, headroom, jcodemunch-mcp,
// codebase-memory-mcp, ai-memory, serena, context-mode, `rtk proxy` and mcporter in command position, leaving --version and
// --help calls out; an `mcporter call <server>.<tool>` counts for its downstream server, never for mcporter. A lane is the
// exact basename of its executable (U1 sources S5-S16, at the manifests/stack.json pins): toon-format/toon@a9e6d97e
// packages/cli/package.json:25-26; yamadashy/repomix@80b4280a package.json:21 (a string bin takes the package name);
// microsoft/markitdown@b8f79c57 packages/markitdown/pyproject.toml:74-75; tobi/qmd@facd35e0 package.json:14-15;
// headroomlabs-ai/headroom@32d7ca45 pyproject.toml:333-334; jgravelle/jcodemunch-mcp@8f7b34ab pyproject.toml:87-89 (its gcm
// script is a separate Groq CLI, not this lane); DeusData/codebase-memory-mcp@8972ea69 Makefile.cbm:1077,1103;
// akitaonrails/ai-memory@433a19f3 crates/ai-memory-cli/Cargo.toml:18-20; oraios/serena@c6fbd1c5 pyproject.toml:64-67 (serena
// and serena-agent; serena-hooks is a hook entry point, not this lane); mksglu/context-mode@589d8214 package.json:58-59;
// openclaw/mcporter@93e0916c package.json:16-17; rtk-ai/rtk@1d87b8e7 Cargo.toml:1-3, whose only lane is `rtk proxy`.
const LANE_EXECUTABLES = new Map([['toon', 'toon'], ['repomix', 'repomix'], ['markitdown', 'markitdown'], ['qmd', 'qmd'],
  ['headroom', 'headroom'], ['jcodemunch-mcp', 'jcodemunch-mcp'], ['codebase-memory-mcp', 'codebase-memory-mcp'],
  ['ai-memory', 'ai-memory'], ['serena', 'serena'], ['serena-agent', 'serena'], ['context-mode', 'context-mode'], ['mcporter', 'mcporter']])
// A package runner names a package, mapped to its lane: npm packages for npx, bunx, bun x, pnpm dlx and yarn dlx, PyPI
// projects (PEP 503 names) for uvx, uv tool run and pipx run, and for python -m the markitdown module, whose __main__ entry
// module the console script names (U1 S7; the README shows only the script).
const NPM_LANES = new Map([['@toon-format/cli', 'toon'], ['repomix', 'repomix'], ['@tobilu/qmd', 'qmd'], ['mcporter', 'mcporter'], ['context-mode', 'context-mode']])
const PYPI_LANES = new Map([['jcodemunch-mcp', 'jcodemunch-mcp'], ['headroom-ai', 'headroom'], ['serena-agent', 'serena'],
  ['codebase-memory-mcp', 'codebase-memory-mcp'], ['markitdown', 'markitdown']])
const MODULE_LANES = new Map([['markitdown', 'markitdown']])
// An mcporter call reaches a lane only through these config server names, seeded from manifests/stack.json:280
// (codebase-memory) and :407 (context-mode); every other server is counted in mcporter_downstream only.
const MCPORTER_ALIASES = new Map([['codebase-memory', 'codebase-memory-mcp'], ['context-mode', 'context-mode']])
const nameStart = (c) => c === '_' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
// NAME=value or NAME+=value before the command name (XCU 2.9.1 Rule 7; bash(1) PARAMETERS), unquoted up to the =.
function isAssignment(e) {
  if (!nameStart(e[0])) return false
  for (let k = 1; k < e.length; k++) {
    if (e[k] === '=' || (e[k] === '+' && e[k + 1] === '=')) return true
    if (!nameStart(e[k]) && !(e[k] >= '0' && e[k] <= '9')) return false
  }
  return false
}
const basename = (v) => v.slice(v.lastIndexOf('/') + 1)
const hasBlank = (v) => v.includes(' ') || v.includes('\t') || v.includes('\n')
// Words of one string split with shell quoting and no expansion: blanks separate words, '...' and "..." group, and a
// backslash escapes the next character (inside double quotes only $ ` " \). Used for `rtk proxy '<one string>'` (rtk
// src/main.rs:3023-3033, discover/lexer.rs:590-595 shell_split) and env -S (GNU env(1), which also expands ${NAME}).
function shellWords(text, expands) {
  const out = []
  let v = null
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === ' ' || c === '\t' || c === '\n') { if (v !== null) { out.push(v); v = null } continue }
    v ??= ''
    if (c === "'") { const k = text.indexOf("'", i + 1), end = k < 0 ? text.length : k; v += text.slice(i + 1, end); i = end }
    else if (c === '"') {
      let k = i + 1
      for (; k < text.length && text[k] !== '"'; k++) { if (text[k] === '\\' && '$`"\\'.includes(text[k + 1] || '-')) k++; v += text[k] }
      i = k
    } else if (c === '\\' && i + 1 < text.length) v += text[++i]
    else v += c
  }
  if (v !== null) out.push(v)
  return out.map((s) => ({ v: s, x: expands && s.includes('$'), e: s }))
}
// How many words the option at words[i] takes (1, or 2 with its option-argument in the next word), 0 at an operand, -1
// for an option the spec does not list, null for one after which no utility runs (POSIX.1-2024 XBD 12.2 Utility Syntax
// Guidelines 3-10: grouped flags, an option-argument attached or in the next word; GNU getopt_long adds --name[=value]).
// A long option's kind is 0 (a flag), 1 (a value, attached with = or in the next word) or 2 (a value only with =).
function optionWords(words, i, spec) {
  const v = words[i].v
  if (v.length < 2 || v[0] !== '-') return 0
  if (v[1] === '-') {
    const eq = v.indexOf('='), name = eq < 0 ? v : v.slice(0, eq), kind = spec.long?.get(name)
    if (spec.stop?.has(name)) return null
    if (kind === undefined || (kind === 0 && eq >= 0)) return -1
    return kind === 1 && eq < 0 ? 2 : 1
  }
  for (let k = 1; k < v.length; k++) {
    if (spec.stop?.has('-' + v[k])) return null
    if (spec.flags.includes(v[k])) continue
    if (spec.values.includes(v[k])) return k === v.length - 1 ? 2 : 1
    return -1
  }
  return 1
}
// The index of the first operand after the options at words[i], past one `--`; -1 or null as optionWords.
function afterOptions(words, i, spec) {
  while (i < words.length) {
    if (words[i].v === '--') return i + 1
    const n = optionWords(words, i, spec)
    if (n === null || n < 0) return n
    if (n === 0) return i
    i += n
  }
  return i
}
const optionGiven = (words, from, to, name) => words.slice(from, to).some((w) => w.v === name || w.v.startsWith(name + '='))
// Wrappers run the utility named after their options: POSIX.1-2024 time, nohup, nice, timeout (one duration first),
// command, exec, env and xargs (echo when no utility is named); GNU coreutils 9.4 stdbuf and the GNU long forms of
// timeout, nice and env; sudo 1.9.15p5's run form (`sudo --help`), whose VAR=value words precede the command. An option a
// spec does not list leaves the program unresolved (bash's exec -a/-c/-l, GNU xargs -P, nice -N); command -v/-V and sudo's
// list, edit, validate, version, help and timestamp modes run no utility.
const WRAPPER_OPTIONS = new Map([
  ['time', { flags: 'p', values: '' }], ['nohup', { flags: '', values: '' }], ['exec', { flags: '', values: '' }],
  ['nice', { flags: '', values: 'n', long: new Map([['--adjustment', 1]]) }],
  ['stdbuf', { flags: '', values: 'ioe', long: new Map([['--input', 1], ['--output', 1], ['--error', 1]]) }],
  ['timeout', { flags: 'fpv', values: 'ks', long: new Map([['--preserve-status', 0], ['--foreground', 0], ['--verbose', 0], ['--kill-after', 1], ['--signal', 1]]) }],
  ['command', { flags: 'p', values: '', stop: new Set(['-v', '-V']) }],
  ['xargs', { flags: 'prtx0', values: 'EILns', long: new Map([['--null', 0]]) }],
  ['sudo', { flags: 'ABbEHkNnPSis', values: 'aCcDghpRrTtu', stop: new Set(['-l', '-e', '-v', '-V', '-K', '--list', '--edit', '--validate', '--version', '--help', '--remove-timestamp']),
    long: new Map([['--askpass', 0], ['--bell', 0], ['--background', 0], ['--preserve-env', 2], ['--set-home', 0], ['--non-interactive', 0],
      ['--preserve-groups', 0], ['--stdin', 0], ['--login', 0], ['--shell', 0], ['--reset-timestamp', 0], ['--auth-type', 1], ['--close-from', 1],
      ['--login-class', 1], ['--chdir', 1], ['--group', 1], ['--host', 1], ['--prompt', 1], ['--chroot', 1], ['--role', 1], ['--type', 1],
      ['--command-timeout', 1], ['--user', 1]]) }],
])
const ENV_OPTIONS = { flags: 'i0v', values: 'uC', long: new Map([['--ignore-environment', 0], ['--null', 0], ['--debug', 0], ['--unset', 1], ['--chdir', 1]]) }
// [words, index of the utility], null when no utility runs, or -1 when the wrapper's options are not all known.
function wrapped(name, words, i) {
  if (name === 'env') {
    // env [-i0v] [-u NAME] [-C DIR] [-S STRING] [-] [NAME=value]... [utility]: -S splits its string into arguments read in
    // its place, and a lone - is -i (GNU coreutils 9.4 env(1)).
    for (let splits = 0; i < words.length;) {
      const v = words[i].v, whole = v === '-S' || v === '--split-string'
      if (v === '--') { i++; break }
      if (v === '-') { i++; continue }
      const split = whole ? words[i + 1]?.v : v.startsWith('--split-string=') ? v.slice(15) : v.startsWith('-S') ? v.slice(2) : undefined
      if (split !== undefined) {
        if (++splits > 8) return -1
        words = [...shellWords(split, true), ...words.slice(i + (whole ? 2 : 1))]
        i = 0
        continue
      }
      if (whole) return -1
      const n = optionWords(words, i, ENV_OPTIONS)
      if (n < 0) return -1
      if (n === 0) break
      i += n
    }
    while (i < words.length && isAssignment(words[i].v)) i++
    return i < words.length ? [words, i] : null
  }
  // exec: the POSIX form only. Any word starting with - is unresolved, `--` included: bash 5.2.21 runs the command after
  // it, while dash executes "--" itself.
  if (name === 'exec' && words[i]?.v.startsWith('-')) return -1
  let k = afterOptions(words, i, WRAPPER_OPTIONS.get(name))
  if (k === null || k < 0) return k
  if (name === 'timeout') k++
  // `time` is a reserved word in bash: `time [-p] [!] pipeline` (bash(1) SHELL GRAMMAR, Pipelines), so a `!` and the assignment words of the
  // simple command may follow its options (`time A=1 qmd get`, `time ! qmd get`); the `time` executable of other hosts takes neither.
  if (name === 'time') while (words[k]?.bang) k++
  if (name === 'sudo' || name === 'time') while (k < words.length && isAssignment(words[k].v)) k++
  if (name === 'xargs' && k >= words.length) return [[{ v: 'echo', x: false, e: 'echo' }], 0]
  return k < words.length ? [words, k] : null
}
// Package runners (U1 design 2.2): npx [-y|--yes|--no] [--package SPEC]... [--] PKG, or CMD after --package (npm 11.19.0
// `npx --help`); bunx PKG, bun x PKG, pnpm dlx PKG and yarn dlx PKG, with no option; uvx and uv tool run with the uv
// 0.12.17 `uvx --help` options below, --from naming the command's package; pipx run [--spec SPEC] NAME; python -m MODULE
// behind interface options that take no value (docs.python.org/3.13/using/cmdline.html). Any other option leaves the
// program unresolved, because the runners' full option grammars are not pinned upstream.
const NPX_OPTIONS = { flags: 'y', values: '', long: new Map([['--yes', 0], ['--no', 0], ['--package', 1]]) }
const UV_OPTIONS = { flags: 'Unqv', values: 'wpP', long: new Map([['--from', 1], ['--with', 1], ['--with-editable', 1], ['--with-requirements', 1],
  ['--python', 1], ['--python-platform', 1], ['--directory', 1], ['--project', 1], ['--upgrade-package', 1], ['--reinstall-package', 1],
  ['--refresh-package', 1], ['--isolated', 0], ['--upgrade', 0], ['--reinstall', 0], ['--no-cache', 0], ['--refresh', 0], ['--quiet', 0],
  ['--verbose', 0], ['--offline', 0]]) }
const PIPX_OPTIONS = { flags: '', values: '', long: new Map([['--spec', 1]]) }
const npmName = (spec) => { const at = spec.indexOf('@', 1); return at < 0 ? spec : spec.slice(0, at) }
// A PyPI requirement's project name, PEP 503-normalized: lowercase, each run of - _ . one -, extras and version dropped.
function pypiName(spec) {
  let name = '', dash = false
  for (const c of spec.toLowerCase()) {
    if (c === '-' || c === '_' || c === '.') { dash = true; continue }
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'))) break
    if (dash && name) name += '-'
    dash = false
    name += c
  }
  return name
}
const isPython = (name) => name.startsWith('python') && [...name.slice(6)].every((c) => c === '.' || (c >= '0' && c <= '9'))
const PYTHON_FLAGS = 'bBdEiIOPqRsSuvx'
// { lane, program, k (the first argument), via } for a runner form, null for none, -1 for an unknown runner option.
function runnerTarget(name, words, i) {
  const pkg = (k, map, via) => {
    const w = words[k]
    if (!w) return null
    if (w.x) return -1
    const id = map === NPM_LANES ? npmName(w.v) : pypiName(w.v), lane = map.get(id) ?? null
    return { lane, program: lane ?? id, k: k + 1, via }
  }
  const command = (k, via) => {
    const w = words[k]
    if (!w) return null
    if (w.x) return -1
    const program = basename(w.v)
    return { lane: LANE_EXECUTABLES.get(program) ?? null, program, k: k + 1, via }
  }
  if (name === 'npx') {
    const k = afterOptions(words, i, NPX_OPTIONS)
    return k === null || k < 0 ? -1 : optionGiven(words, i, k, '--package') ? command(k, 'npx') : pkg(k, NPM_LANES, 'npx')
  }
  const dlx = name === 'bunx' ? i : (name === 'bun' && words[i]?.v === 'x') || ((name === 'pnpm' || name === 'yarn') && words[i]?.v === 'dlx') ? i + 1 : -1
  if (dlx >= 0) return words[dlx]?.v.startsWith('-') ? -1 : pkg(dlx, NPM_LANES, name === 'bunx' ? 'bunx' : name + ' ' + words[i].v)
  const uv = name === 'uvx' ? i : name === 'uv' && words[i]?.v === 'tool' && words[i + 1]?.v === 'run' ? i + 2 : -1
  const pipx = name === 'pipx' && words[i]?.v === 'run' ? i + 1 : -1
  if (uv >= 0 || pipx >= 0) {
    const from = uv >= 0 ? uv : pipx, k = afterOptions(words, from, uv >= 0 ? UV_OPTIONS : PIPX_OPTIONS), via = uv < 0 ? 'pipx run' : name === 'uvx' ? 'uvx' : 'uv tool run'
    return k === null || k < 0 ? -1 : optionGiven(words, from, k, uv >= 0 ? '--from' : '--spec') ? command(k, via) : pkg(k, PYPI_LANES, via)
  }
  if (isPython(name)) {
    let k = i
    while (k < words.length && words[k].v.length > 1 && words[k].v[0] === '-' && [...words[k].v.slice(1)].every((c) => PYTHON_FLAGS.includes(c))) k++
    const flag = words[k]?.v
    if (flag === undefined || !flag.startsWith('-m')) return null
    const module = flag === '-m' ? words[k + 1] : { ...words[k], v: flag.slice(2) }
    if (!module) return null
    if (module.x) return -1
    const lane = MODULE_LANES.get(module.v) ?? null
    return { lane, program: lane ?? module.v, k: k + (flag === '-m' ? 2 : 1), via: 'python -m' }
  }
  return null
}
// mcporter (openclaw/mcporter@93e0916c, v0.14.1). Global flags with a value (src/cli/cli-factory.ts:19) are removed before
// `--` (src/cli/flag-utils.ts:4-24) and the next word is the command (src/cli.ts:115-146): none prints help, and so does a
// help token (--help, -h, help), while a version token (--version, -v, -V; src/cli/help-output.ts:200-210) prints the
// version. generate-cli, inspect-cli, serve and emit-ts print help for a help token anywhere, record and replay before
// `--`, daemon and config for their first word (src/cli.ts:149-262; src/cli/daemon-command.ts:28; config-command.ts:14).
// Other commands are inferred (src/cli/command-inference.ts:10-95): describe and list-tools are list; list, call, auth,
// vault, resource and resources are explicit; an HTTP tool selector is a call, a URL a list, a word with . or ( an
// implicit call, and any other word a configured server name, listed (or auto-corrected, or refused). They print help
// for a help token anywhere (src/cli.ts:306-364: consumeMatchingTokens, src/cli/flag-utils.ts:34-40, scans every word).
const MCPORTER_GLOBALS = new Set(['--config', '--root', '--log-level', '--oauth-timeout'])
const MCPORTER_EARLY = new Set(['generate-cli', 'inspect-cli', 'serve', 'emit-ts', 'record', 'replay', 'daemon', 'config'])
const MCPORTER_EXPLICIT = new Set(['list', 'call', 'auth', 'vault', 'resource', 'resources'])
const mcporterHelp = (v) => v === '--help' || v === '-h' || v === 'help'
const mcporterVersion = (v) => v === '--version' || v === '-v' || v === '-V'
function mcporterOp(words) {
  const args = []
  for (let i = 0, literal = false; i < words.length; i++) {
    literal ||= words[i] === '--'
    if (!literal && MCPORTER_GLOBALS.has(words[i])) i++
    else args.push(words[i])
  }
  const [command, ...rest] = args
  if (command === undefined || mcporterHelp(command)) return { op: 'help', excluded: true }
  if (mcporterVersion(command)) return { op: 'version', excluded: true }
  if (MCPORTER_EARLY.has(command)) {
    const separator = rest.indexOf('--')
    return { op: command, excluded: command === 'daemon' ? !rest.length || rest[0] === 'help' || rest[0] === '--help'
      : command === 'config' ? !rest.length || mcporterHelp(rest[0])
        : (separator >= 0 && (command === 'record' || command === 'replay') ? rest.slice(0, separator) : rest).some(mcporterHelp) }
  }
  let op = 'list', target = args
  if (command === 'describe' || command === 'list-tools') target = rest
  else if (MCPORTER_EXPLICIT.has(command)) { op = command; target = rest }
  else if (httpToolSelector(command) || (!httpUrl(command) && (command.includes('.') || command.includes('(')))) op = 'call'
  if (target.some(mcporterHelp)) return { op, excluded: true }
  return op === 'call' ? { op, server: mcporterServer(target), excluded: false } : { op, excluded: false }
}
// mcporter's HTTP forms (src/cli/http-utils.ts:1-69): a URL has an http(s) scheme, or is a bare host[:port] followed by a
// path, which gets https; an HTTP tool selector is such a URL whose last path segment ends in .<tool>.
const digit = (c) => c >= '0' && c <= '9'
const alnum = (c) => digit(c) || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
function httpUrl(value) {
  const s = value.trim(), head = s.slice(0, 8).toLowerCase()
  let candidate = head.startsWith('http://') || head.startsWith('https://') ? s : null
  if (!candidate && alnum(s[0])) {
    let k = 1
    while (k < s.length && (alnum(s[k]) || s[k] === '.' || s[k] === '-')) k++
    if (s[k] === ':') { const port = ++k; while (k < s.length && digit(s[k])) k++; if (k === port) k = -1 }
    if (k >= 0 && s[k] === '/') candidate = 'https://' + s
  }
  if (!candidate) return null
  try { return new URL(candidate) } catch { return null }
}
function httpToolSelector(input) {
  const open = input.indexOf('('), url = httpUrl(open < 0 ? input : input.slice(0, open))
  if (!url) return false
  const segment = url.pathname.slice(url.pathname.lastIndexOf('/') + 1), dot = segment.lastIndexOf('.'), tool = segment.slice(dot + 1)
  return dot > 0 && tool.length > 0 && [...tool].every((c) => alnum(c) || c === '_' || c === '-')
}
// An ad-hoc stdio selector (src/cli/call-argument-values.ts:68-83): a blank, or a path start (./ ../ ~/ / C:\ \\).
const stdioSelector = (s) => hasBlank(s) || s.startsWith('./') || s.startsWith('../') || s.startsWith('~/') || s.startsWith('/')
  || s.startsWith('\\\\') || (s.length > 2 && alnum(s[0]) && !digit(s[0]) && s[1] === ':' && s[2] === '\\')
// A config server name as a report key (U1 pivot D5, GPT-6 #10): only the stack's own MCP servers are emitted by name, so a string that merely
// looks like a name (an id, a host, a person's server) never reaches the output. The closed set is the servers this stack wires:
// manifests/stack.json:280 (codebase-memory), :407 (context-mode), :629 and :966 (socraticode), and jcodemunch, serena, qmd, headroom and
// ai-memory from the coordinator's list in the pivot brief. An HTTP URL or ad-hoc stdio command never reaches here; an expansion is
// (unresolved); any other name is (other).
const MCPORTER_SERVERS = new Set(['codebase-memory', 'context-mode', 'jcodemunch', 'serena', 'socraticode', 'qmd', 'headroom', 'ai-memory'])
const serverKey = (name) => !name || name.includes('$') || name.includes('`') ? '(unresolved)' : MCPORTER_SERVERS.has(name) ? name : '(other)'
// The server an mcporter call reaches. Ephemeral flags anywhere (src/cli/ephemeral-flags.ts:9-128, which does not stop at
// `--`) and --output/--raw (src/cli/output-format.ts:10-59) are removed first; then words up to `--` are read with the call
// flags' arities and the generic --key value rule (src/cli/call-arguments.ts:63-128,249-359). A leading call expression
// (HTTP, or name(...) split at its first dot) gives the server; otherwise --server/--mcp does, and without it the first
// positional is the selector, promoted to an ad-hoc stdio command when it holds a blank or starts as a path, and a later
// server= or server: sets a server not yet set (call-arguments.ts:130-233; call-argument-values.ts:9-39,68-83;
// call-expression-parser.ts:24-29,94-103). A URL server or selector is an ad-hoc HTTP server, an npx command line given as
// the server an ad-hoc stdio server, and other ad-hoc flags without --http-url or --stdio fail
// (src/cli/call-command.ts:114-173; ephemeral-target.ts:26-85,134-158; adhoc-server.ts:32-35). The server is the explicit
// one, else the selector up to its first dot (call-command.ts:309-348). A configured server whose URL matches an HTTP
// selector is reused upstream; statically that is still (http).
const MCPORTER_EPHEMERAL = new Map([['--http-url', 2], ['--sse', 2], ['--allow-http', 1], ['--insecure', 1], ['--stdio', 2], ['--stdio-arg', 2],
  ['--env', 2], ['--header', 2], ['--cwd', 2], ['--name', 2], ['--description', 2], ['--persist', 2]])
const MCPORTER_CALL_FLAGS = new Map([['--server', 2], ['--mcp', 2], ['--tool', 2], ['--timeout', 2], ['--save-images', 2], ['--args', 2], ['--params', 2],
  ['--json', 2], ['--tail-log', 1], ['--no-oauth', 1], ['--yes', 1], ['--raw-strings', 1], ['--no-coerce', 1]])
function mcporterServer(words) {
  let http = false, stdio = false, adhoc = false, server, selector, tool = false
  const kept = [], call = [], positional = []
  for (let i = 0; i < words.length; i++) {
    const width = MCPORTER_EPHEMERAL.get(words[i])
    if (!width) { kept.push(words[i]); continue }
    adhoc = true
    http ||= words[i] === '--http-url' || words[i] === '--sse'
    stdio ||= words[i] === '--stdio'
    i += width - 1
  }
  for (let i = 0; i < kept.length; i++) if (kept[i] === '--output') i++; else if (kept[i] !== '--raw') call.push(kept[i])
  for (let i = 0; i < call.length && call[i] !== '--'; i++) {
    const w = call[i], width = MCPORTER_CALL_FLAGS.get(w)
    if (!w) continue
    if (width) { if (w === '--server' || w === '--mcp') server = call[i + 1]; tool ||= w === '--tool'; i += width - 1 }
    else if (w.startsWith('--')) { if (!w.includes('=')) i++ }
    else positional.push(w)
  }
  let expression = false
  const first = positional[0]?.trim() ?? '', open = first.indexOf('(')
  if (positional.length && httpToolSelector(open < 0 ? first : first.slice(0, open))) { positional.shift(); http = true; expression = tool = true }
  else if (open > 0 && first.endsWith(')')) {
    positional.shift()
    const name = first.slice(0, open).trim(), dot = name.indexOf('.')
    if (dot > 0) { server ??= name.slice(0, dot); expression = true }
    tool = true
  }
  if (positional.length && !expression && server === undefined) selector = positional.shift()
  if (server === undefined && selector !== undefined && !stdio && stdioSelector(selector.trim())) { stdio = true; selector = undefined }
  if (!tool && positional.length && !positional[0].includes('=') && !positional[0].includes(':')) positional.shift()
  for (let i = 0; i < positional.length; i++) {
    const w = positional[i], eq = w.indexOf('='), colon = w.indexOf(':')
    const key = eq >= 0 ? w.slice(0, eq > 0 && w[eq - 1] === ':' ? eq - 1 : eq) : colon >= 0 ? w.slice(0, colon) : null
    const value = eq >= 0 ? w.slice(eq + 1) : colon >= 0 && colon < w.length - 1 ? w.slice(colon + 1) : colon >= 0 ? positional[++i] : undefined
    if (key === 'server' && server === undefined) server = value
  }
  if (server !== undefined && httpUrl(server)) { http = true; server = undefined }
  if (selector !== undefined && httpUrl(selector)) { http = true; selector = undefined }
  if (http) return '(http)'
  if (stdio) return '(stdio)'
  if (adhoc) return '(unresolved)'
  if (server !== undefined) {
    const parts = shellWords(server, false)
    return parts.length > 1 && basename(parts[0].v) === 'npx' ? '(stdio)' : serverKey(server)
  }
  return serverKey(selector === undefined ? undefined : selector.includes('.') ? selector.slice(0, selector.indexOf('.')) : selector)
}
// ------------------------------------------------------------------ the AST reading
// The commands of a shell text are the `command` nodes of its tree-sitter-bash tree (grammar node types: node-types.json of
// tree-sitter-bash 0.25.1; the reference for reading them is openai/codex rust-v0.157.1 codex-rs/shell-command/src/bash.rs:
// parse_shell_lc_literal_commands walks every `command` node, and parse_plain_command_from_node reads a word only from a `word`, `number`,
// `string`, `raw_string` or `concatenation` node, so a word with an expansion is unknown). This reading differs from Codex's in what
// it does with the words: it resolves wrappers, runners and shells to the program they run. Handled node kinds: command (the words of
// its name and arguments; assignment prefixes and redirections are not words, but the words the grammar folds into a redirection's
// targets are its arguments), redirected_statement, heredoc_redirect and
// herestring_redirect (the owner of standard input), and every node that holds statements or words (list, pipeline, subshell,
// compound_statement, negated_command, if, while, for, c-style for, case, function_definition, command_substitution,
// process_substitution, string, concatenation, expansion, arithmetic_expansion, array, subscript, test_command,
// declaration_command, unset_command, variable_assignment(s), do_group, elif and else clauses), all found by descent, so a `command`
// inside any of them counts. A word that is not a `command` never counts: array elements, case patterns, [[ ]] operands, function
// names, for-loop values and the words of any program that is not a lane. Not resolved: an ERROR node and everything under it
// (skipped; the call counts once in parse_errors), the body of a heredoc whose owner is a compound command, and a heredoc that a pipe
// (rather than a redirection) feeds to a shell.
const PLACEHOLDER = '$_U1' // stands for the unknown text of an expansion in a script that is read again
// A word node as { v, x, s, bang }: v its value with the quotes removed (an expansion keeps its own source text), x whether this reading cannot
// know the value (an expansion, a glob, a brace or a tilde expansion), s the text a shell hands on when the word is a script: v with each
// expansion replaced by PLACEHOLDER, or null when a glob, brace or tilde could stand anywhere in it, and bang whether the node is a bare `!`
// (a quoted or escaped one is a program name; an unquoted one is the reserved word wherever a pipeline may begin).
function wordOf(node) {
  const w = { v: '', s: '', x: false, g: false }
  addPart(w, node, true)
  if (!w.x && node.text.includes('{') && braceExpands(node.text)) w.x = w.g = true
  return { v: w.v, x: w.x, s: w.g ? null : w.s, bang: node.text === '!' }
}
// The value of a word node, or null when it is unknown (D3): a `word` after the unquoted escape rules, a `raw_string`, a `string` under
// the double-quote rule (a backslash goes only before $ ` " \ and a newline), an `ansi_c_string` decoded as bash does, a concatenation of
// known parts, a `number`; any expansion, brace expansion, glob or tilde expansion is unknown.
export function wordValue(node) {
  const w = wordOf(node)
  return w.x || w.s === null ? null : w.v
}
function addPart(w, node, first) {
  switch (node.type) {
    case 'word': case 'number':
      if (node.namedChildCount) return addExpansion(w, node)
      return plainText(w, node.text, first)
    case 'raw_string': { const t = node.text; return addLiteral(w, t.length > 1 && t.endsWith("'") ? t.slice(1, -1) : t.slice(1)) }
    case 'string': return doubleQuoted(w, node)
    case 'ansi_c_string': {
      const t = node.text, decoded = ansiC(t.length > 2 && t.endsWith("'") ? t.slice(2, -1) : t.slice(2))
      if (decoded === null) { w.x = w.g = true; w.v += t; return }
      return addLiteral(w, decoded)
    }
    case 'concatenation': {
      const parts = node.children
      for (let i = 0; i < parts.length; i++) addPart(w, parts[i], first && i === 0)
      return
    }
    case 'brace_expression': case 'translated_string': w.x = w.g = true; w.v += node.text; return
    default:
      if (!node.isNamed) return addLiteral(w, node.text) // `$`, `==` and `=~` are argument tokens of their own
      return addExpansion(w, node)
  }
}
const addLiteral = (w, text) => { w.v += text; w.s += text }
const addExpansion = (w, node) => { w.x = true; w.v += node.text; w.s += PLACEHOLDER }
// Unquoted text (bash(1) QUOTING, EXPANSION): a backslash quotes the next character and a backslash-newline is removed; an unescaped * or ?
// or a [ that a ] closes is a pathname pattern, and a ~ that starts the word a tilde prefix. A tilde prefix changes only the directory part of
// a path (`~/.local/bin/qmd`): the value is unknown (g), but the last path segment, which names the program, is not, so the word stays a
// known word (x false) for program identity, as /usr/local/bin/qmd is; the real corpus of this host holds ~30 lane invocations by such a
// path in 136,361 distinct commands. `$HOME/...` is an expansion of another kind (D3): unresolved.
function plainText(w, text, first) {
  if (first) { let k = 0; while (k < text.length && (text[k] === ' ' || text[k] === '\t' || text[k] === '\n')) k++; text = text.slice(k) } // the newline the grammar folded in
  if (first && text[0] === '~') w.g = true
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '\\') {
      if (i + 1 >= text.length) { addLiteral(w, c); break }
      i++
      if (text[i] !== '\n') addLiteral(w, text[i])
    } else {
      if (c === '*' || c === '?' || (c === '[' && text.indexOf(']', i + 1) > i)) w.x = w.g = true
      addLiteral(w, c)
    }
  }
}
// Double-quoted text keeps every backslash except one before $ ` " \ or a newline (bash(1) QUOTING; POSIX.1-2024 XCU 2.2.3).
function doubleText(w, text) {
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '\\' && i + 1 < text.length && '$`"\\\n'.includes(text[i + 1])) { i++; if (text[i] !== '\n') addLiteral(w, text[i]) } else addLiteral(w, c)
  }
}
// The text between the quotes is literal except for the expansion nodes inside it; it is cut at their ranges, not read from string_content
// nodes, because the grammar's content nodes leave out the blank or newline next to an expansion.
function doubleQuoted(w, node) {
  const t = node.text, base = node.startIndex, end = t.length > 1 && t.endsWith('"') ? t.length - 1 : t.length
  let at = t.startsWith('"') ? 1 : 0
  for (const child of node.namedChildren) {
    if (child.type === 'string_content') continue
    doubleText(w, t.slice(at, child.startIndex - base))
    addExpansion(w, child)
    at = child.endIndex - base
  }
  doubleText(w, t.slice(at, end))
}
// The bytes of $'...' (bash(1) QUOTING): \a \b \e \E \f \n \r \t \v \\ \' \" \? \nnn \xHH \uHHHH \UHHHHHHHH \cx; an unknown escape keeps its
// backslash; null for a NUL or an invalid code point (the value is then unknown).
function ansiC(body) {
  const hex = (s, from, max) => { let k = from; while (k < s.length && k - from < max && /[0-9A-Fa-f]/.test(s[k])) k++; return k }
  let out = ''
  for (let i = 0; i < body.length; i++) {
    const c = body[i]
    if (c !== '\\') { out += c; continue }
    const n = body[++i]
    const simple = { a: '\x07', b: '\b', e: '\x1b', E: '\x1b', f: '\f', n: '\n', r: '\r', t: '\t', v: '\v', '\\': '\\', "'": "'", '"': '"', '?': '?' }[n]
    if (simple !== undefined) out += simple
    else if (n === undefined) out += '\\'
    else if (n >= '0' && n <= '7') {
      let k = i; while (k < body.length && k - i < 3 && body[k] >= '0' && body[k] <= '7') k++
      const code = parseInt(body.slice(i, k), 8) & 255
      if (code === 0) return null
      out += String.fromCharCode(code); i = k - 1
    } else if (n === 'x' || n === 'u' || n === 'U') {
      const k = hex(body, i + 1, n === 'x' ? 2 : n === 'u' ? 4 : 8)
      if (k === i + 1) out += '\\' + n
      else {
        const code = parseInt(body.slice(i + 1, k), 16)
        if (code === 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) return null
        out += String.fromCodePoint(code); i = k - 1
      }
    } else if (n === 'c') { const d = body[i + 1]; if (d === undefined) out += '\\c'; else { out += String.fromCharCode(d.charCodeAt(0) & 31); i++ } }
    else out += '\\' + n
  }
  return out
}
// Whether the text of a word holds a brace expansion (bash(1) Brace Expansion): an unquoted { ... } with an unquoted comma or `..` at its own
// level. One pass with a stack of open braces, skipping quoted text and the ${ }, $( ) and backquoted spans, so it stays linear.
function braceExpands(raw) {
  const open = []
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i]
    if (c === '\\') i++
    else if (c === "'") { const k = raw.indexOf("'", i + 1); if (k < 0) return false; i = k }
    else if (c === '"') { for (i++; i < raw.length && raw[i] !== '"'; i++) if (raw[i] === '\\') i++ }
    else if (c === '`') { const k = raw.indexOf('`', i + 1); if (k < 0) return false; i = k }
    else if (c === '$' && (raw[i + 1] === '{' || raw[i + 1] === '(')) {
      let depth = 0
      for (i++; i < raw.length; i++) { if (raw[i] === '{' || raw[i] === '(') depth++; else if (raw[i] === '}' || raw[i] === ')') { if (--depth === 0) break } else if (raw[i] === '\\') i++ }
    } else if (c === '{') open.push(false)
    else if (c === ',' && open.length) open[open.length - 1] = true
    else if (c === '.' && raw[i + 1] === '.' && open.length) { open[open.length - 1] = true; i++ }
    else if (c === '}' && open.length && open.pop()) return true
  }
  return false
}
const SHELLS = new Set(['sh', 'bash', 'dash', 'zsh', 'ksh'])
// The names a record's `program` may hold (U1 pivot D5, GPT-6 #10): a lane executable, or a name this reading interprets itself: the wrappers,
// the shells, eval, ssh and rtk. Any other program (a host, an id, a package, a script) reads null however name-shaped it is.
const PROGRAM_NAMES = new Set([...LANE_EXECUTABLES.keys(), ...WRAPPER_OPTIONS.keys(), 'env', 'rtk', 'eval', 'ssh', ...SHELLS])
const programName = (name) => PROGRAM_NAMES.has(name) ? name : null
// The arguments a here-document operator carries after its delimiter, without the words of its body that tree-sitter-bash 0.25.1 puts among
// them when the first body line begins with a backslash: that line starts with the newline (a word that starts on a new line, and every
// argument after it, is body text).
function operatorArguments(r) {
  const words = []
  let body = false
  for (let i = 0; i < r.childCount; i++) {
    if (r.fieldNameForChild(i) !== 'argument') continue
    const child = r.child(i)
    body ||= startsLine(child.text)
    if (!body) words.push(child)
  }
  return { words, misplaced: body }
}
// A `command` node's words in source order: its name, then its arguments, then any argument a here-document operator carries after its
// delimiter (`cat <<EOF -n` is `cat -n <<EOF`). Assignment prefixes and redirections are not words.
// tree-sitter-bash 0.25.1 sometimes reads what follows a command as more of its arguments: an ERROR node on `;`, `&&` or `|` after an
// unquoted `==` or `=~` word (`echo ==; qmd get a`), the same inside the destinations of a redirection (`<<'EOF' 2>&1 | tail`), and, with
// no error at all, a command that ends its line and whose next line then continues it (`head -20` and `echo ...` read as one command; 732
// such commands, and 163 with an ERROR, among 136,361 real ones). The words of one command never span an unescaped newline (bash(1)
// SHELL GRAMMAR: a newline ends a simple command; a backslash-newline continues it) and never hold a separator, so each is a boundary: the
// words after it are a command of their own. Returns the commands as [{ pos, words }], the first being the node's own.
const SEPARATOR_TOKENS = new Set([';', ';;', '&', '&&', '||', '|', '|&'])
// A line that begins with a backslash (`\ls`, the alias bypass) reaches the grammar as a word that begins with the newline (bash(1) QUOTING).
const startsLine = (text) => { for (let i = 0; i < text.length && (text[i] === ' ' || text[i] === '\t' || text[i] === '\n'); i++) if (text[i] === '\n') return true; return false }
const continues = (gap) => { for (let i = 0; i < gap.length; i++) { if (gap[i] === '\\' && gap[i + 1] === '\n') i++; else if (gap[i] === '\n') return false } return true }
function commandSegments(node, src, fields, extra = [], folded = []) {
  const segments = [{ pos: node.startIndex, words: [], herestrings: [] }]
  let prev = null
  for (let i = 0; i < node.childCount; i++) {
    const child = node.child(i)
    if (child.type === 'ERROR') { if (SEPARATOR_TOKENS.has(child.text.trim())) segments.push({ pos: child.endIndex, words: [], herestrings: [] }); prev = null; continue }
    if (prev && (!continues(src.slice(prev.endIndex, child.startIndex)) || startsLine(child.text))) segments.push({ pos: child.startIndex, words: [], herestrings: [] })
    prev = child
    if (child.type === 'herestring_redirect') segments[segments.length - 1].herestrings.push(child) // a here-string belongs to the command it follows
    const field = node.fieldNameForChild(i)
    if (field === 'name') { const inner = child.namedChild(0); segments[segments.length - 1].words.push(inner ? { ...wordOf(inner), assignment: false } : { v: '', s: null, x: true }) }
    else if (fields.includes(field)) segments[segments.length - 1].words.push({ ...wordOf(child), assignment: (child.type === 'word' || child.type === 'concatenation') && isAssignment(child.text) })
  }
  // The first command's assignment prefixes are already nodes of their own; in a command the grammar had joined they are still words
  // (bash(1) PARAMETERS: NAME=value words before the command name are assignments).
  for (let k = 1; k < segments.length; k++) { const words = segments[k].words; while (words.length && words[0].assignment) words.shift() }
  const last = segments[segments.length - 1].words
  for (const r of extra) for (const child of operatorArguments(r).words) last.push(wordOf(child))
  for (const w of folded) last.push(w)
  return segments
}
// tree-sitter-bash 0.25.1 gives a redirection every word after its target as further targets (grammar.js file_redirect: `repeat1` of
// destination), but bash takes the target from the first word only: the rest are ordinary words of the command the redirection belongs to
// (bash(1) REDIRECTION: a redirection may appear anywhere in a simple command, and the words are read left to right, so `nice 2>&1 qmd`
// runs qmd and `bash >/dev/null -c 'x'` gives -c to bash). A closing redirection (`<&-`, `>&-`) takes no target, so every word after it is
// the command's. Only the words before a boundary (a separator, an unescaped newline) count here; the commands after one are read by
// redirectTail.
function foldedWords(redirect, src) {
  const words = commandSegments(redirect, src, ['destination'])[0].words
  const closing = redirect.children.some((c) => c.type === '<&-' || c.type === '>&-')
  return words.slice(closing ? 0 : 1).map((w) => ({ ...w, assignment: false }))
}
// How a shell uses its arguments (bash(1) OPTIONS and ARGUMENTS; dash(1) and POSIX.1-2024 sh OPTIONS agree on -c, -n, -s): options are the words up
// to the first operand, `--` or `-`; -o, +o, -O and +O take the next word; --rcfile and --init-file take a file; a -c option makes the first operand
// the script, which is read even when options follow -c, and every operand after it data; -n and -D (and -o noexec, --help, --version) read
// without running; with no -c the shell reads its script from standard input when no operand names a file, or with -s. An expansion among the
// options leaves the mode unknown.
const NOEXEC_LONG = new Set(['--help', '--version', '--dump-strings', '--dump-po-strings', '--pretty-print'])
function shellMode(args) {
  let c = false, noexec = false, s = false, i = 0
  for (; i < args.length; i++) {
    const w = args[i], v = w.v
    if (v === '--' || v === '-') { i++; break }
    if (v.length < 2 || (v[0] !== '-' && v[0] !== '+')) break // an operand, an expansion included ("$script", `-c "$cmd"`)
    if (w.x) return { unknown: true } // an option with an expansion in it: which options it holds is unknown
    if (v === '--rcfile' || v === '--init-file') { i++; continue }
    if (v.startsWith('--')) { if (NOEXEC_LONG.has(v)) noexec = true; continue }
    let takes = 0, cluster = true
    for (let k = 1; k < v.length && cluster; k++) {
      const ch = v[k]
      if (!((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z'))) cluster = false
      else if (ch === 'o' || ch === 'O') takes++
      else if (v[0] === '-') { if (ch === 'c') c = true; else if (ch === 'n' || ch === 'D') noexec = true; else if (ch === 's') s = true }
    }
    if (!cluster) break
    for (let t = 1; t <= takes; t++) { const next = args[i + t]; if (next?.x) return { unknown: true }; if (v[0] === '-' && next?.v === 'noexec') noexec = true }
    i += takes
  }
  const operands = args.slice(i)
  return { c, noexec, script: operands[0], reads: !c && (operands.length === 0 || s) }
}
// ssh [options] destination [command [argument ...]] (OpenSSH ssh(1) 9.6p1): the words after the destination are joined by blanks and run by the
// remote login shell, which reads its standard input when there is no command. Options may follow the destination (ssh.c parses them again).
// -N -W -O -G -V -Q and -s run no remote command, and -n and -f keep standard input unread.
const SSH_OPTION_VALUE = new Set([...'BbcDEeFIiJLlmOoPpQRSWw']), SSH_OPTION_NO_COMMAND = new Set([...'NWOGVQs']), SSH_OPTION_NO_STDIN = new Set([...'nf'])
function sshWords(args) {
  let destination = false, noCommand = false, noStdin = false, i = 0
  for (; i < args.length; i++) {
    const w = args[i], v = w.v
    if (v === '--') { i++; if (!destination) { destination = true; i++ } break }
    if (v.length > 1 && v[0] === '-') {
      if (w.x) return { unknown: true }
      for (let k = 1; k < v.length; k++) {
        if (SSH_OPTION_NO_COMMAND.has(v[k])) noCommand = true
        if (SSH_OPTION_NO_STDIN.has(v[k])) noStdin = true
        if (SSH_OPTION_VALUE.has(v[k])) { if (k === v.length - 1) i++; break }
      }
      continue
    }
    if (destination) break
    destination = true
  }
  return { destination, noCommand, noStdin, command: args.slice(i) }
}
const unresolvedRecord = (remote) => ({ lane: null, program: null, op: null, server: null, excluded: false, remote, unresolved: true, via: null })
// The invocations of one command's words, appended to `out`: each wrapper, runner and `rtk proxy` is followed to the program it runs (an
// expansion in program position is unresolved; a program is unresolved behind an option this reading does not know). --version and --help
// among a lane's own words (before `--`) exclude it. `exec` is true after rtk proxy, which resolves its program on PATH and spawns it with no
// shell (rtk-ai/rtk@1d87b8e7 src/main.rs:3060-3066, src/core/utils.rs:615-632): a shell builtin (command, exec) runs nothing there, and time,
// which is a builtin only in a shell, is an executable on hosts that have GNU time, so it is unresolved. A shell with -c, eval and ssh read a
// script: the words are joined as the callee joins them and read again (nested depth <= NESTING_LIMIT). Returns { reads, remote } for a
// shell or ssh that would run its standard input as a script (a here-document or here-string then feeds it), else null.
function resolveWords(words, out, cx, exec) {
  const push = (fields) => { out.push({ lane: null, program: null, op: null, server: null, excluded: false, remote: cx.remote, unresolved: false, via: null, ...fields }) }
  const finish = (lane, program, args, via) => {
    if (lane === 'mcporter') { const m = mcporterOp(args.map((w) => w.v)); return push({ lane, program: programName(program), op: m.op, server: m.server ?? null, excluded: m.excluded, via }) }
    const end = args.findIndex((w) => w.v === '--'), own = end < 0 ? args : args.slice(0, end)
    push({ lane, program: programName(program), excluded: lane !== null && own.some((w) => w.v === '--version' || w.v === '--help'), via })
  }
  const script = (text, remote) => {
    if (text === null) return push({ unresolved: true })
    const a = readScript(text, remote, cx.depth + 1, cx.acc)
    for (const r of a.records) out.push(r)
    return a
  }
  // `!` negates a pipeline (bash(1) SHELL GRAMMAR; bash accepts it twice, `! ! cmd`), and the grammar reads a `!` that is not the first word
  // of its statement as the command's name: a doubled negation, or the line after an array assignment it joined to. An unquoted `!` at the
  // start is never a program, and the assignment words after it (`! ! A=1 qmd`) are the simple command's prefix; after `rtk proxy` a `!`
  // names a program for execvp, so only a shell's reading strips it.
  if (!exec) {
    let k = 0
    while (words[k]?.bang) k++
    if (k) { while (k < words.length && isAssignment(words[k].v)) k++; words = words.slice(k) }
  }
  let i = 0, stdin = true
  for (let hop = 0; hop < 64; hop++) {
    const w = words[i]
    if (!w) return null
    if (w.x) { push({ unresolved: true }); return null }
    const name = basename(w.v)
    if (exec && name === 'time') { push({ unresolved: true }); return null }
    if (name === 'env' || (WRAPPER_OPTIONS.has(name) && !(exec && (name === 'command' || name === 'exec')))) {
      const next = wrapped(name, words, i + 1)
      if (next === null) return null
      if (next === -1) { push({ unresolved: true }); return null }
      if (name === 'xargs') stdin = false // xargs reads its standard input for arguments, so a here-document is its data
      ;[words, i] = next
      continue
    }
    if (name === 'rtk') {
      // rtk-ai/rtk@1d87b8e7 src/main.rs:68-90: -v/--verbose counts (only before the subcommand), --ultra-compact and
      // --skip-env are global, and clap's -V/--version and -h/--help print and exit (observed on the installed rtk 0.50.0).
      let k = i + 1, help = false
      for (; k < words.length; k++) {
        const v = words[k].v
        if (v === '--version' || v === '-V' || v === '--help' || v === '-h') help = true
        else if (v !== '--ultra-compact' && v !== '--skip-env' && v !== '--verbose' && !(v.length > 1 && v[0] === '-' && [...v.slice(1)].every((c) => c === 'v'))) break
      }
      if (help) { push({ lane: 'rtk_proxy', program: 'rtk', excluded: true }); return null }
      if (words[k]?.v !== 'proxy') { push({ program: 'rtk' }); return null }
      // proxy (src/main.rs:708-713, 3008-3042): --ultra-compact, --skip-env and -h/--help still bind before the first argument
      // and one `--` is consumed (observed on rtk 0.50.0); -v or any other word there is already the program. One argument
      // with a blank is shell-split (#388) after the shell has expanded it, so an expansion there names an unknown program.
      for (k++; k < words.length; k++) {
        const v = words[k].v
        if (v === '-h' || v === '--help') help = true
        else if (v !== '--ultra-compact' && v !== '--skip-env') { if (v === '--') k++; break }
      }
      push({ lane: 'rtk_proxy', program: 'rtk', op: 'proxy', excluded: help })
      if (help || k >= words.length) return null
      if (words.length - k === 1) {
        if (words[k].x) { push({ unresolved: true }); return null }
        words = hasBlank(words[k].v) ? shellWords(words[k].v, false) : [words[k]]
      } else words = words.slice(k)
      i = 0
      exec = true
      continue
    }
    if (!exec && name === 'eval') {
      push({ program: 'eval' })
      const rest = words.slice(i + 1)
      if (rest.length) script(rest.some((r) => r.s === null) ? null : rest.map((r) => r.s).join(' '), cx.remote)
      return null
    }
    if (SHELLS.has(name)) {
      push({ program: name })
      const mode = shellMode(words.slice(i + 1))
      if (mode.unknown) { push({ unresolved: true }); return null }
      if (mode.noexec) return null
      if (mode.c) { if (mode.script) script(mode.script.s, cx.remote); return null }
      return stdin && mode.reads ? { reads: true, remote: false } : null
    }
    if (name === 'ssh') {
      push({ program: 'ssh' })
      const ssh = sshWords(words.slice(i + 1))
      if (ssh.unknown) { push({ unresolved: true }); return null }
      if (ssh.noCommand || !ssh.destination) return null
      if (!ssh.command.length) return stdin && !ssh.noStdin ? { reads: true, remote: true } : null
      const a = script(ssh.command.some((r) => r.s === null) ? null : ssh.command.map((r) => r.s).join(' '), true)
      return stdin && !ssh.noStdin && a?.readers > 0 ? { reads: true, remote: true } : null
    }
    const runner = runnerTarget(name, words, i + 1)
    if (runner === -1) { push({ unresolved: true }); return null }
    if (runner) { finish(runner.lane, runner.program, words.slice(runner.k), runner.via); return null }
    finish(LANE_EXECUTABLES.get(name) ?? null, name, words.slice(i + 1), null)
    return null
  }
  push({ unresolved: true })
  return null
}
// The scripts a here-document or here-string body becomes. The shell that expands an unquoted-delimiter body runs each $( ) and backquoted span
// itself (POSIX.1-2024 XCU 2.7.4, bash(1) Here Documents), whatever its quotes say; the shell that reads the body sees the text with each span
// replaced by its unknown output, a backslash before $ ` \ or a newline removed. A quoted delimiter expands nothing.
const withPlaceholders = (raw, spans) => {
  let out = '', at = 0
  for (const span of spans) { out += raw.slice(at, span.from) + PLACEHOLDER; at = span.to }
  return out + raw.slice(at)
}
const backquoted = (body) => {
  let out = ''
  for (let i = 0; i < body.length; i++) { if (body[i] === '\\' && i + 1 < body.length && '$`\\'.includes(body[i + 1])) i++; out += body[i] }
  return out
}
// The unescaped body of a backquoted substitution when the escaping changes it (a backslash before $, ` or \), else null.
function backquoteScript(text) {
  const body = text.length > 1 && text.endsWith('`') ? text.slice(1, -1) : text.slice(1)
  for (let i = 0; i + 1 < body.length; i++) {
    if (body[i] !== '\\') continue
    if ('$`\\'.includes(body[i + 1])) return backquoted(body)
    i++
  }
  return null
}
const stripTabs = (text) => { let out = '', start = true; for (const ch of text) { if (start && ch === '\t') continue; start = ch === '\n'; out += ch } return out }
// The text of a here-document body: the body node's own range when the tree is sound, else the lines between the operator line and the
// delimiter (tree-sitter-bash 0.25.1 leaves an empty body node, and puts the body's words among the operator's arguments, when the first body
// line begins with a backslash).
function heredocRaw(r, start, end, src) {
  const body = r.children.find((c) => c.type === 'heredoc_body')
  if (body && body.endIndex > body.startIndex && !operatorArguments(r).misplaced) return src.slice(body.startIndex, body.endIndex)
  const line = src.indexOf('\n', start.endIndex)
  return line < 0 || line + 1 > end.startIndex ? '' : src.slice(line + 1, end.startIndex)
}
const quotedDelimiter = (text) => { for (const ch of text) if (ch === "'" || ch === '"' || ch === '\\') return true; return false }
// A here-document with no delimiter line is closed by the end of the text: bash warns ("here-document delimited by end-of-file") and runs
// it, its body being everything after the operator's line (bash(1) Here Documents; POSIX.1-2024 XCU 2.7.4 leaves the case undefined).
// tree-sitter-bash 0.25.1 reads that body as an ERROR (its words as commands of the operator's line), or drops it when the text ends with a
// newline, so the missing delimiter lines are appended, one per round, before the text is read. The delimiter is the operator's word with its quotes removed.
function heredocWord(text) {
  let out = ''
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '\\') out += text[++i] ?? ''
    else if (c === "'") { const k = text.indexOf("'", i + 1), end = k < 0 ? text.length : k; out += text.slice(i + 1, end); i = end }
    else if (c === '"') { for (i++; i < text.length && text[i] !== '"'; i++) { if (text[i] === '\\' && '$`"\\'.includes(text[i + 1] ?? '')) i++; out += text[i] ?? '' } }
    else out += c
  }
  return out
}
// The delimiter of the first here-document (in source order) that has no delimiter line, or null. One at a time: while a heredoc is open the
// grammar may read a later body line as a second operator, which is only body text once the first is closed.
function missingDelimiter(root) {
  const stack = [root]
  while (stack.length) {
    const node = stack.pop()
    if (node.type === 'heredoc_start' && !node.parent?.children.some((c) => c.type === 'heredoc_end' && c.endIndex > c.startIndex && c.startIndex > node.startIndex)) return heredocWord(node.text)
    for (let i = node.childCount - 1; i >= 0; i--) stack.push(node.child(i))
  }
  return null
}
// Every command of a script, as { records, readers } (readers: how many of its commands would run their standard input as a script).
function readScript(text, remote, depth, acc) {
  const records = []
  if (depth > NESTING_LIMIT) { records.push(unresolvedRecord(remote)); return { records, readers: 0 } }
  let tree = parseShell(text)
  if (!tree) { acc.errors = true; return { records, readers: 0 } }
  openShellTreeCount++
  try {
    for (let round = 0; round < 8 && tree.rootNode.hasError; round++) {
      const missing = missingDelimiter(tree.rootNode)
      if (missing === null) break
      const closed = text + (text.endsWith('\n') ? '' : '\n') + missing + '\n', again = parseShell(closed)
      if (!again) break
      tree.delete(); tree = again; text = closed
    }
    return { records, readers: walkTree(tree.rootNode, text, { remote, depth, acc, records }) }
  } finally { tree.delete(); openShellTreeCount-- }
}
const STATEMENT_PARENTS = new Set(['program', 'list', 'pipeline', 'compound_statement', 'subshell', 'do_group', 'if_statement', 'elif_clause', 'else_clause',
  'while_statement', 'case_item', 'command_substitution', 'process_substitution', 'negated_command', 'redirected_statement', 'function_definition', 'heredoc_redirect'])
// What counts toward "more than one simple command" (POSIX.1-2024 XCU 2.9.1 simple commands, 2.9.4 compound commands, XCU 2.9.2 pipelines): each
// command, each assignment-only statement, declaration, unset, test and arithmetic command, and each loop, if and case (its body runs zero or more
// times), since the call's one status then does not describe one command.
const COUNTED = new Set(['command', 'declaration_command', 'unset_command', 'test_command', 'variable_assignments', 'for_statement', 'while_statement',
  'if_statement', 'case_statement', 'c_style_for_statement'])
// The last command of a body that a redirection follows: the redirection belongs to it (bash(1) SHELL GRAMMAR: a redirection applies to the
// simple command it is written after). A compound command owns its redirection as a whole, which this reading does not follow.
function lastCommand(node) {
  for (let n = node; n;) {
    if (n.type === 'command') return n
    if (n.type === 'list' || n.type === 'pipeline') n = n.lastNamedChild
    else if (n.type === 'negated_command') n = n.namedChild(0)
    else if (n.type === 'redirected_statement') n = n.childForFieldName('body')
    else return null
  }
  return null
}
// Walks a tree without recursion (a 3,000-deep $( must not throw) and returns how many commands read a script from standard input.
function walkTree(root, src, cx) {
  const entries = [], pending = new Map(), claimed = new Set(), folds = new Map()
  let readers = 0
  if (root.hasError) cx.acc.errors = true
  // The scripts a here-document or here-string feeds: `terminal` is the owner's { reads, remote } or null.
  const feed = (r, terminal, records, asOwner) => {
    const descriptor = r.childForFieldName('descriptor')
    const stdin = !descriptor || descriptor.text === '0', reads = asOwner && stdin && terminal?.reads, remote = terminal?.remote ?? cx.remote
    if (r.type === 'herestring_redirect') {
      // The word's substitutions run once, in the owner's own tree; a shell owner also reads the word's value.
      if (!reads) return
      const word = r.namedChildren.find((c) => c.type !== 'file_descriptor')
      if (!word) return
      const s = wordOf(word).s
      if (s === null) records.push(unresolvedRecord(remote)); else for (const x of readScript(s, remote, cx.depth + 1, cx.acc).records) records.push(x)
      return
    }
    let start = null, end = null
    for (const c of r.children) { if (c.type === 'heredoc_start') start = c; else if (c.type === 'heredoc_end') end = c }
    if (!start || !end) return
    let raw = heredocRaw(r, start, end, src)
    if (r.children.some((c) => c.type === '<<-')) raw = stripTabs(raw)
    if (quotedDelimiter(start.text)) { if (reads) for (const x of readScript(raw, remote, cx.depth + 1, cx.acc).records) records.push(x); return }
    const spans = outerSpans(raw, cx.depth)
    for (const span of spans) {
      const body = span.kind === '`' ? backquoted(raw.slice(span.body[0], span.body[1])) : raw.slice(span.body[0], span.body[1])
      for (const x of readScript(body, cx.remote, cx.depth + 1, cx.acc).records) records.push(x)
    }
    if (reads) for (const x of readScript(heredocText(traced(withPlaceholders(raw, spans))).s, remote, cx.depth + 1, cx.acc).records) records.push(x)
  }
  const command = (node) => {
    const owned = pending.get(node.id) ?? []
    const segments = commandSegments(node, src, ['argument'], owned.filter((r) => r.type === 'heredoc_redirect'), folds.get(node.id) ?? []).filter((sg) => sg.words.length)
    segments.forEach((sg, k) => {
      if (k) cx.acc.simple++ // a command the grammar had joined to the previous one
      const records = []
      const terminal = resolveWords(sg.words, records, cx, false)
      if (terminal?.reads) readers++
      // Only the last redirection of standard input feeds the command; an earlier one is data. The heredocs and here-strings written after the last
      // word of the node belong to its last command.
      const redirects = k === segments.length - 1 ? [...sg.herestrings, ...owned] : sg.herestrings
      const feeds = redirects.filter((r) => { const d = r.childForFieldName('descriptor'); return !d || d.text === '0' }).sort((a, b) => a.startIndex - b.startIndex)
      const last = feeds[feeds.length - 1]
      for (const r of redirects) feed(r, terminal, records, r === last)
      entries.push({ pos: sg.pos, records })
    })
  }
  // The destinations of a redirection that the grammar ran on into the next command (`2>&1 | tail -n 5`): the words after a boundary.
  const redirectTail = (node) => {
    const segments = commandSegments(node, src, ['destination'])
    for (let k = 1; k < segments.length; k++) {
      if (!segments[k].words.length) continue
      cx.acc.simple++
      const records = []
      const terminal = resolveWords(segments[k].words, records, cx, false)
      if (terminal?.reads) readers++
      entries.push({ pos: segments[k].pos, records })
    }
  }
  const stack = [root]
  while (stack.length) {
    const node = stack.pop(), type = node.type
    if (type === 'ERROR' || type === 'comment' || type === 'heredoc_body' || type === 'heredoc_start' || type === 'heredoc_end') continue
    if (type === '&') { cx.acc.async = true; continue }
    if (COUNTED.has(type)) cx.acc.simple++
    else if (type === 'variable_assignment' && STATEMENT_PARENTS.has(node.parent?.type)) cx.acc.simple++
    else if (type === 'compound_statement' && node.child(0)?.type === '((') cx.acc.simple++
    if (type === 'command_substitution' && node.child(0)?.type === '`') {
      // A backquoted body is unescaped before the shell parses it (POSIX.1-2024 XCU 2.6.3, bash(1) Command Substitution): a backslash before
      // $, ` or \ is removed, so an escaped backquote nests a substitution the grammar reads as data. Such a body is read again from its
      // unescaped text (a body with no such backslash is the text the tree already holds).
      const script = backquoteScript(node.text)
      if (script !== null) { entries.push({ pos: node.startIndex, records: readScript(script, cx.remote, cx.depth + 1, cx.acc).records }); continue }
    }
    if (type === 'command') command(node)
    else if (type === 'file_redirect') redirectTail(node)
    else if (type === 'redirected_statement') {
      const body = node.childForFieldName('body'), owner = body ? lastCommand(body) : null
      const redirects = node.childrenForFieldName('redirect')
      const owned = redirects.filter((r) => r.type === 'heredoc_redirect' || r.type === 'herestring_redirect')
      if (owned.length && owner) { pending.set(owner.id, owned); for (const r of owned) claimed.add(r.id) }
      // The words the grammar folded into its file redirections are arguments of the command they follow.
      const folded = owner ? redirects.filter((r) => r.type === 'file_redirect').flatMap((r) => foldedWords(r, src)) : []
      if (folded.length) folds.set(owner.id, [...(folds.get(owner.id) ?? []), ...folded])
    } else if (type === 'heredoc_redirect') {
      // The operator line's own children are walked; the body is handled with its owner (here: none, so its substitutions only).
      if (!claimed.has(node.id)) { const records = []; feed(node, null, records, false); entries.push({ pos: node.startIndex, records }) }
      const kept = new Set(operatorArguments(node).words.map((w) => w.id))
      for (let i = node.childCount - 1; i >= 0; i--) {
        const child = node.child(i)
        if (node.fieldNameForChild(i) === 'argument' && !kept.has(child.id)) continue // body text the grammar put here
        stack.push(child)
      }
      continue
    }
    for (let i = node.childCount - 1; i >= 0; i--) stack.push(node.child(i))
  }
  entries.sort((a, b) => a.pos - b.pos)
  for (const e of entries) for (const r of e.records) cx.records.push(r)
  return readers
}
// Every command of a shell script and its invocations, in tree order. `simple` counts commands (see COUNTED), `async` a background &, and
// `errors` whether any script read has a syntax error (ERROR nodes and everything under them are not read).
function analyzeScript(command) {
  const acc = { simple: 0, async: false, errors: false }
  const { records } = readScript(String(command || ''), false, 0, acc)
  return { invocations: records, simple: acc.simple, async: acc.async, errors: acc.errors }
}
// U1 design 2.6: the invocations of one shell command, in source order, as { lane (a lane name or null), program (the
// name-shaped basename, or null when unresolved), op (proxy, or an mcporter operation), server (an mcporter call's
// downstream key), excluded (a --version or --help call), remote (run on another host by ssh), unresolved (a program
// named by an expansion, or behind an option this reading does not know), via (the package runner) }. No raw text, no ids.
// null when no verified tree-sitter-bash install is loaded (loadShellParser): no lane is ever counted without it.
export function commandInvocations(command) {
  return shellParser ? analyzeScript(command).invocations : null
}
// The shell scripts of a call, as countFetches selects them: the Bash command (also a sandbox-nested Codex command),
// ctx_batch_execute commands and shell ctx_execute(_file) code. Python, JavaScript and Codex code-mode source are not read.
function shellScripts(call) {
  const input = call?.input || {}, name = String(call?.name || '')
  if (name === 'Bash') return [String(input.command || '')]
  if (name.endsWith('__ctx_batch_execute')) return (Array.isArray(input.commands) ? input.commands : []).map((c) => String(c?.command || ''))
  return /__ctx_execute(?:_file)?$/.test(name) && input.language === 'shell' ? [String(input.code || '')] : []
}
function callAnalysis(call) {
  const out = { invocations: [], simple: 0, async: false, proxy: 0, errors: false }
  for (const script of shellScripts(call)) {
    const a = analyzeScript(script)
    for (const invocation of a.invocations) out.invocations.push(invocation)
    out.simple += a.simple
    out.async ||= a.async
    out.errors ||= a.errors
  }
  for (const invocation of out.invocations) if (invocation.lane === 'rtk_proxy' && !invocation.excluded && !invocation.remote) out.proxy++
  return out
}
// Call states (U1 design 4). AA-PLAN: "Successful" means the tool_result is not an error (Messages API is_error); M14
// reconciles attempted, decided, executed, failed and unfinished calls. With no result a persisted native status decides
// (Codex CommandExecutionStatus, openai/codex rust-v0.157.1 protocol/src/items.rs), else the call is unfinished. is_error
// true is failed, and not_executed as well when the call never ran. Where the Claude Code client records that (observed on this
// host's transcripts, 122,648 Bash results; not a documented schema): a row-level toolDenialKind (permission-rule, user-rejected,
// cancelled, automode-unavailable: every client denial, 798 rows, and no failed command); a result content that opens with
// <tool_use_error> (a validation or blocked call; code.claude.com hooks, PostToolUseFailure), with "The user doesn't want to proceed"
// (a rejection: 25 rows, whose toolUseResult reads "User rejected tool use") or with the classifier text "The server-side auto mode
// classifier gave no verdict" (its own text: a failure of the check, not a judgment about the action, and the action may be tried again);
// a toolUseResult string that names a PreToolUse hook denial, a permission denial or a user rejection; or an adapter marking it declined.
// A host hook's own refusal text (209 rows opening "This agent is isolated") carries none of these and stays failed: its meaning is the
// hook's, not the client's. is_error false is succeeded, unknown when an adapter could not read the outcome (native_state), or
// interrupted when toolUseResult.interrupted is true (the command started and was cut short; none of 25,506 observed object results);
// background marks a run that only started (run_in_background, or a toolUseResult backgroundTaskId).
const NOT_EXECUTED_RESULT = ['PreToolUse:', 'Permission for', 'User rejected tool use']
const NOT_EXECUTED_CONTENT = ['<tool_use_error>', "The user doesn't want to proceed", 'The server-side auto mode classifier gave no verdict']
function callState(call, result) {
  if (!result) {
    const status = call?.native_status
    return status === 'completed' ? { state: 'succeeded' } : status === 'failed' ? { state: 'failed' }
      : status === 'declined' ? { state: 'failed', not_executed: true } : { state: 'unfinished' }
  }
  const native = result.native_state ?? call?.native_state, said = result.row?.toolUseResult
  if (result.is_error) {
    const reason = typeof said === 'string' ? (said.startsWith('Error: ') ? said.slice(7) : said) : '', content = resultText(result.content)
    return { state: 'failed', not_executed: Boolean(result.row?.toolDenialKind) || NOT_EXECUTED_CONTENT.some((m) => content.startsWith(m))
      || NOT_EXECUTED_RESULT.some((m) => reason.startsWith(m)) || native === 'declined' }
  }
  if (native === 'unknown') return { state: 'unknown' }
  if (said && typeof said === 'object' && said.interrupted === true) return { state: 'interrupted' }
  return { state: 'succeeded', background: Boolean(call?.input?.run_in_background) || Boolean(said && typeof said === 'object' && said.backgroundTaskId) }
}
const LANE_COUNTERS = ['calls', 'invocations', 'succeeded', 'failed', 'not_executed', 'unfinished', 'unknown', 'interrupted', 'background', 'ambiguous', 'via_mcporter']
const CLI_CARRIERS = ['bash', 'rtk_proxy', 'ctx', 'nested']
const DOWNSTREAM_COUNTERS = ['calls', 'succeeded', 'failed', 'not_executed', 'unfinished', 'unknown', 'interrupted']
const emptyLane = () => ({ ...Object.fromEntries(LANE_COUNTERS.map((k) => [k, 0])), by_carrier: Object.fromEntries(CLI_CARRIERS.map((k) => [k, 0])) })
const emptyCliLanes = () => ({ lanes: counter(), mcporter_downstream: counter(), excluded_version_help: counter(), calls_with_lane_invocation: 0, unresolved_programs: 0, remote_invocations: 0, parse_errors: 0 })
// One call's lane counts (U1 design 5): each lane it invokes locally counts the call once, with its invocations, its state
// and its carrier; a call with more than one simple command or a background & is ambiguous, since its one state covers
// every command. An mcporter call counts for its downstream server, and for a lane only through MCPORTER_ALIASES.
function countLanes(cli, analysis, s, carrier) {
  const lanes = new Map(), servers = new Set()
  const use = (lane, via) => { const e = lanes.get(lane) || { n: 0, via: false }; e.n++; e.via ||= via; lanes.set(lane, e) }
  for (const invocation of analysis.invocations) {
    if (invocation.remote) { if (invocation.lane) cli.remote_invocations++; continue }
    if (invocation.unresolved) { cli.unresolved_programs++; continue }
    if (!invocation.lane) continue
    if (invocation.excluded) bump(cli.excluded_version_help, invocation.lane)
    else if (invocation.lane === 'mcporter' && invocation.op === 'call') {
      servers.add(invocation.server)
      if (MCPORTER_ALIASES.has(invocation.server)) use(MCPORTER_ALIASES.get(invocation.server), true)
    } else use(invocation.lane, false)
  }
  for (const [lane, e] of lanes) {
    const row = cli.lanes[lane] ||= emptyLane()
    row.calls++
    row.invocations += e.n
    row[s.state]++
    if (s.not_executed) row.not_executed++
    if (s.background) row.background++
    if (analysis.simple > 1 || analysis.async) row.ambiguous++
    if (e.via) row.via_mcporter++
    row.by_carrier[carrier]++
  }
  for (const server of servers) {
    const row = cli.mcporter_downstream[server] ||= Object.fromEntries(DOWNSTREAM_COUNTERS.map((k) => [k, 0]))
    row.calls++
    row[s.state]++
    if (s.not_executed) row.not_executed++
  }
  if (lanes.size) cli.calls_with_lane_invocation++
}

// PR-A result accounting. Source: #381 preregistration.json M3/M5,
// mksglu/context-mode v1.0.169 src/session/extract.ts:1060-1069 (UTF-8
// accounting only), and
// https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use
// (`tool_use.id` -> `tool_result.tool_use_id`). Local rule: sum UTF-8 text block
// payloads without wrappers/separators; compact JSON for non-text blocks only.
// This is not hook tool_response serialization or tokenizer/provider usage.
const RESULT_LIMIT = 5120
const contentBytes = (content) => typeof content === 'string' ? Buffer.byteLength(content, 'utf8')
  : Array.isArray(content) ? content.reduce((n, b) => n + contentBytes(b?.type === 'text' && typeof b.text === 'string' ? b.text : b), 0)
    : Buffer.byteLength(JSON.stringify(content), 'utf8')
const emptySizes = () => ({ results: 0, bytes: 0, large_results: 0, large_bytes: 0, max_bytes: 0 })
const addSize = (s, n) => { s.results++; s.bytes += n; if (n > RESULT_LIMIT) { s.large_results++; s.large_bytes += n } s.max_bytes = Math.max(s.max_bytes, n) }
const finishSizes = (s) => ({ ...s, large_result_share: share(s.large_results, s.results), large_byte_share: share(s.large_bytes, s.bytes) })
const isCtx = (name) => /^mcp__.+__ctx_/.test(name)
// A Bash call is carried by rtk proxy when its command invokes `rtk proxy` in command position (commandInvocations, through
// the caller's per-call memo `proxied`); the earlier prefix rule survives only as measurement.proxy.prefix_rule_calls.
// The rule before the command-position reading, kept as the fallback without a parser and as measurement.proxy.prefix_rule_calls.
const rtkProxyPrefix = (call) => call?.name === 'Bash' && /^\s*rtk\s+proxy\b/.test(call.input?.command || '')
const carrierOf = (call, proxied = () => false) => call?.code_mode ? 'code_mode' : call?.name === 'Bash' ? (proxied(call) ? 'rtk_proxy' : 'bash')
  : call?.name === 'WebFetch' ? 'webfetch' : call?.name === 'Read' ? 'read'
    : ['Grep', 'Glob'].includes(call?.name) ? 'grep_glob' : isCtx(call?.name) ? 'ctx'
      : mcpServer(call?.name) ? 'other_mcp' : 'other'
const blocksOf = (row) => Array.isArray(row?.message?.content) ? row.message.content.filter((b) => b && typeof b === 'object') : []
const EXCEPTIONS = ['read_of_subsequently_edited_file', 'original_source_quoted_or_line_cited', 'exact_bytes_required_by_frozen_check']
const validLogFindReview = (r) => Array.isArray(r?.rtk_log_find) && r.rtk_log_find.length > 0
  && r.rtk_log_find.every((p) => Number.isInteger(p?.part) && p.part > 0 && ['permitted', 'requires_raw'].includes(p.disposition))
  && new Set(r.rtk_log_find.map((p) => p.part)).size === r.rtk_log_find.length
// #381 digest-bound review contract: every supplied class must be valid, including
// null values (Object.hasOwn: developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/hasOwn).
const validReview = (r) => typeof r?.witness === 'string' && !!r.witness.trim()
  && ['exception', 'proxy_purpose', 'rtk_log_find'].some((key) => Object.hasOwn(r, key))
  && (!Object.hasOwn(r, 'exception') || EXCEPTIONS.includes(r.exception))
  && (!Object.hasOwn(r, 'proxy_purpose') || r.proxy_purpose === 'acceptance')
  && (!Object.hasOwn(r, 'rtk_log_find') || validLogFindReview(r))
// M4 sources: evidence/artifacts/token-adoption-e2e-20260926/preregistration.json
// thresholds.M4; context-mode v1.0.169 hooks/core/routing.mjs:788-795 and
// src/server.ts tool schemas (`commands`, `code`, `requests`). Confirmed script
// HTTP operations stay unclassifiable; raw matches missed by executed-text
// analysis are possible fetches, kept separately for the gate's lower bound.
// These are statically visible operations, not observed network requests: loops,
// dynamically imported scripts and runtime URL resolution cannot be reconstructed.
const emptyFetches = () => ({ ctx_fetch_and_index: 0, webfetch: 0, shell_fetch: 0, ctx_sandbox_fetch: 0, loopback: 0, unclassifiable: 0, fetch_mentions_unconfirmed: 0 })
const remoteUrl = (url) => { try { return !LOOPBACK.test(new URL(url).hostname) } catch { return null } }
const HTTP_SCRIPT = /\b(?:fetch\s*\(|(?:requests|httpx|urllib\.request|https?|axios)\s*\.\s*(?:get|post|put|request|urlopen)\s*\()/g
const GH_API = /(?:^|[;\n|&])\s*(?:rtk\s+(?:proxy\s+)?)?gh\s+api\b/g
const LITERAL = /\b(?:execSync|exec|execFileSync|run|Popen|check_output)\(\s*(?:(["'])(.*?)\1|\[([^\]]*)\])/dgs
// Possible fetches (#381 M4 lower bound): raw detector matches that no executed-text match traces back to. A match is
// anchored at its operative word (the call name, the four-unit curl/wget word, or gh); an executed match confirms only
// the raw match at its own raw offset, so matches the analysis creates (backslash-newline joins, unescaping, quoted
// strings a shell runs) confirm nothing and cannot offset a raw miss.
const unconfirmed = (code, pattern, confirmed, trace, anchor) => {
  const seen = new Set(confirmed.map((m) => trace.p[anchor(m)]))
  return [...code.matchAll(pattern)].filter((m) => !seen.has(anchor(m))).length
}
const callAnchor = (m) => m.index, wordAnchor = (m) => m.index + m[0].length - 4, ghAnchor = (m) => m.index + m[0].lastIndexOf('gh')
function countFetches(call, counts) {
  const input = call.input || {}, name = call.name || ''
  const url = (u, key) => { const remote = remoteUrl(u); counts[remote === null ? 'unclassifiable' : remote ? key : 'loopback']++ }
  if (name.endsWith('__ctx_fetch_and_index')) {
    if (Array.isArray(input.requests)) for (const r of input.requests) url(r?.url, 'ctx_fetch_and_index')
    else url(input.url, 'ctx_fetch_and_index')
    return
  }
  if (name === 'WebFetch') { url(input.url, 'webfetch'); return }
  const scripts = name === 'Bash' ? [String(input.command || '')]
    : name.endsWith('__ctx_batch_execute') ? (input.commands || []).map((c) => String(c.command || ''))
      : /__ctx_execute(?:_file)?$/.test(name) ? [String(input.code || '')] : []
  for (const code of scripts) {
    const shell = name === 'Bash' || name.endsWith('__ctx_batch_execute') || input.language === 'shell'
    // Supported inline subprocess literals (context-mode routing.mjs:727-804).
    // Inspect literal commands, never execute the code. Arbitrary dynamic code is
    // outside this static detector and cannot be certified as having no fetches.
    const raw = traced(code)
    const literals = shell ? [] : [...code.matchAll(LITERAL)].map((m) => m[2] !== undefined ? slice(raw, ...m.indices[2])
      : joined([...m[3].matchAll(/(["'])(.*?)\1/g)].map((s) => slice(raw, m.indices[3][0] + s.index + 1, m.indices[3][0] + s.index + 1 + s[2].length)), ' '))
    const missesBefore = windowMisses
    const exec = shell ? executedTrace(raw, false) : joined(literals.map((t) => executedTrace(t, false)), '\n'), text = exec.s
    counts.unclassifiable += windowMisses - missesBefore // run strings the scan window lost track of: operations of unknown kind
    const word = new RegExp(FETCH_WORD.source.replace('rtk|', 'rtk|proxy|'), 'gm')
    const matches = [...text.matchAll(word)]
    for (let i = 0; i < matches.length; i++) {
      // Delimiters inside quoted data have already been neutralized by executedText.
      const segment = text.slice(matches[i].index + matches[i][0].length, matches[i + 1]?.index).split(/[;\n|&]/)[0]
      const hosts = [...segment.matchAll(URL_HOST)].map((m) => m[1])
      const key = hosts.length && hosts.every((h) => LOOPBACK.test(h)) ? 'loopback'
        : hosts.length ? (name === 'Bash' && !call.sandbox ? 'shell_fetch' : 'ctx_sandbox_fetch') : 'unclassifiable'
      counts[key]++
    }
    // routing.mjs:228-229,787-797 strips all heredocs before inline-HTTP matching.
    // Retain interpreter-fed bodies for #381 M4, even though upstream cannot route them.
    // Reuse our bash quoting/comment state as well. Only interpreter code (or
    // ctx JS/Python) gets raw scanning; quoted grep patterns are not operations.
    const http = shell ? executedTrace(raw, true) : raw
    const confirmedHttp = [...http.s.matchAll(HTTP_SCRIPT)]
    // GitHub API calls are remote operations even when their endpoint is relative.
    const gh = [...text.matchAll(GH_API)]
    counts.unclassifiable += confirmedHttp.length + gh.length
    counts.fetch_mentions_unconfirmed += unconfirmed(code, HTTP_SCRIPT, confirmedHttp, http, callAnchor)
      + unconfirmed(code, word, matches, exec, wordAnchor) + unconfirmed(code, GH_API, gh, exec, ghAnchor)
  }
}
const finishFetches = (f, carriers = null) => {
  const remote = f.ctx_fetch_and_index + f.webfetch + f.shell_fetch + f.ctx_sandbox_fetch + f.unclassifiable
  return { ...f, remote_fetches: remote, routed_share: share(f.ctx_fetch_and_index, remote),
    routed_share_lower_bound: share(f.ctx_fetch_and_index, remote + f.fetch_mentions_unconfirmed),
    unclassifiable_share: share(f.unclassifiable, remote), status: f.fetch_mentions_unconfirmed ? 'incomplete' : !remote ? 'not_applicable' : f.unclassifiable / remote > .1 ? 'incomplete' : 'measured',
    ...(carriers ? { by_carrier: Object.fromEntries(Object.entries(carriers).map(([k, v]) => [k, finishFetches(v)])) } : {}) }
}
// Reference implementation: rtk-ai/rtk v0.50.0 src/main.rs:2940-2952,
// src/discover/lexer.rs:119-135,488-526; registry.rs:1087-1345,1451-1494.
// Replay accepts a Linux binary on PATH self-reporting rtk 0.50.0 and passing
// the five-exclusion probe; this does not identify its build or binary hash.
// Keep every part (upstream discover stops at its first pipe). Complex shell
// constructs are unknown, never guessed or executed. This is a local adapter.
function shellParts(command) {
  if (/<<|\$\(\(/.test(command)) return null
  const parts = [], syntax = command.split('')
  const part = (end, op) => ({ text: command.slice(start, end).trim(), syntax: syntax.slice(start, end).join('').trim(), op })
  let start = 0, quote = null, depth = 0
  for (let i = 0; i < command.length; i++) {
    const ch = command[i]
    if (ch === '\\' && quote !== "'") { syntax[i] = '_'; if (i + 1 < command.length) syntax[++i] = '_'; continue }
    if (quote) { syntax[i] = '_'; if (ch === quote) quote = null; continue }
    if (ch === "'" || ch === '"' || ch === '`') { syntax[i] = '_'; quote = ch; continue }
    if (ch === '(' || ch === '{') { depth++; continue }
    if (ch === ')' || ch === '}') { depth--; if (depth < 0) return null; continue }
    if (depth) continue
    if (ch === '#' && (i === 0 || /\s/.test(command[i - 1]))) return null
    if (';&|\n'.includes(ch)) {
      const op = command[i + 1] === ch && '&|'.includes(ch) ? ch + ch : ch
      // & in 2>&1 is a redirection, not an asynchronous command boundary.
      if (ch === '&' && command[i - 1] === '>') continue
      parts.push(part(i, op))
      i += op.length - 1; start = i + 1
    }
  }
  if (quote || depth) return null
  parts.push(part(command.length, ''))
  return parts.filter((p) => p.text)
}
// git(1) global options before the subcommand: -C, -c, --git-dir or --work-tree with the next word, or one --option.
const GIT_OPTIONS = String.raw`^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*`
const FIVE_EXCLUSIONS = [String.raw`^git show [^ ]*:`, 'diff',
  GIT_OPTIONS + String.raw`show\s+(?:[^\n]*\s)?[^\s]*:`,
  GIT_OPTIONS + String.raw`branch(?:\s|$)`, 'jq']
// Where GIT_OPTIONS can end. RTK evaluates the patterns with Rust's linear-time regex; in JavaScript the nested
// quantifier backtracks exponentially on repeated '--git-dir --x ' (CodeQL js/redos), so every reading of the
// option words is walked here instead and the rest of the pattern is tried at each word it can reach.
function gitSubcommandStarts(text) {
  if (!/^git\s/.test(text)) return []
  const words = [...text.matchAll(/\S+/g)], reach = new Set([1]), starts = []
  for (let i = 1; i < words.length; i++) {
    if (!reach.has(i)) continue
    starts.push(words[i].index)
    if (/^(?:-C|-c|--git-dir|--work-tree)$/.test(words[i][0]) && i + 2 < words.length) reach.add(i + 2)
    if (/^--\S/.test(words[i][0]) && i + 1 < words.length) reach.add(i + 1)
  }
  return starts
}
const afterGitOptions = (rest, text) => {
  const pattern = new RegExp(rest, 'y')
  return gitSubcommandStarts(text).some((at) => { pattern.lastIndex = at; return pattern.test(text) })
}
let nativeCheck = null
function rtkChecker() {
  if (nativeCheck) return nativeCheck
  const version = spawnSync('rtk', ['--version'], { encoding: 'utf8' })
  if (process.platform !== 'linux' || version.status !== 0 || !/^rtk 0\.50\.0\s*$/.test(version.stdout)) return null
  const dir = mkdtempSync(join(tmpdir(), 'rtk-measure-'))
  mkdirSync(join(dir, 'rtk'))
  writeFileSync(join(dir, 'rtk', 'config.toml'), '[hooks]\nexclude_commands = [\n' + FIVE_EXCLUSIONS.map((p) => "'" + p + "'").join(',\n') + '\n]\n', { mode: 0o600 })
  process.once('exit', () => rmSync(dir, { recursive: true, force: true }))
  const cache = new Map()
  nativeCheck = (command) => {
    if (!cache.has(command)) {
      const p = spawnSync('rtk', ['hook', 'check', '--agent', 'claude', command], {
        encoding: 'utf8', timeout: 10000, maxBuffer: 1024 * 1024,
        env: { ...process.env, XDG_CONFIG_HOME: dir, RTK_DB_PATH: join(dir, 'history.db') },
      })
      cache.set(command, p.status === 0 ? { rewrite: p.stdout.trim() }
        : p.status === 1 && p.stderr.startsWith('No rewrite for:') ? { rewrite: null } : { error: true })
    }
    return cache.get(command)
  }
  // A native behavior probe catches the upstream silent invalid-config fallback.
  if (['jq . f', 'diff a b', 'git branch -a', 'git show HEAD:a', 'git -C . show HEAD:a'].some((c) => nativeCheck(c).rewrite !== null)) { nativeCheck = null; return null }
  return nativeCheck
}
export function sensitivePart(text) {
  if (FIVE_EXCLUSIONS.some((p) => p.startsWith(GIT_OPTIONS) ? afterGitOptions(p.slice(GIT_OPTIONS.length), text)
    : new RegExp(p.startsWith('^') ? p : '^' + p + '(?:\\s|$)').test(text))) return true
  // Deterministic refusals only. Conditional log/find exceptions need a witness
  // (adoption/templates/codex.AGENTS.template.md, RTK exceptions).
  return /^(?:cd|export|source)\b/.test(text)
    || /^gh\s/.test(text) && /(?:^|\s)--(?:json|jq|template)(?:[=\s]|$)/.test(text)
    || /^(?:head|tail)\s/.test(text) && /(?:^|\s)-c|["'$*?\[]/.test(text)
    || /^\S*\/\S*(?:\s|$)/.test(text)
}
export const logFindPart = (text) => /^find\b/.test(text) || afterGitOptions(String.raw`log\b`, text)
const safeConsumer = (part) => /^(?:cat|head)(?:\s|$)/.test(part) || /^tail(?:\s|$)/.test(part) && !/(?:^|\s)(?:-[^-\s]*[fF]|--follow)(?:\S*)/.test(part)
const emptyRtk = () => ({ calls: 0, eligible_parts: 0, eligible_calls: 0, observed_covered_parts: 0, observed_all_covered_calls: 0,
  replayed_covered_parts: 0, replayed_all_covered_calls: 0, explicit_rtk_on_excluded_or_sensitive: 0,
  explicit_rtk_log_find_advisory: 0, log_find_permitted_parts: 0, log_find_requires_raw_parts: 0, log_find_unresolved_parts: 0,
  proxy_parts: 0, ineligible_parts: 0, unknown_calls: 0 })
function rtkParts(calls, rewrites, enabled, exceptions) {
  const out = emptyRtk(), check = enabled ? rtkChecker() : null
  if (!check) return { ...out, status: enabled ? 'unavailable' : 'not_measured', coverage: null, call_coverage: null }
  for (const c of calls) {
    if (c.name !== 'Bash') continue
    out.calls++
    const command = String(c.input?.command || ''), parts = shellParts(command), replay = check(command)
    const executed = shellParts(rewrites.get(c.id) ?? command), predicted = shellParts(replay.rewrite ?? command)
    if (!parts || !executed || !predicted || replay.error || parts.length !== executed.length || parts.length !== predicted.length) { out.unknown_calls++; continue }
    let eligible = 0, observed = 0, covered = 0
    for (const [i, part] of parts.entries()) {
      const explicit = /^rtk\s+/.test(part.text), proxy = /^rtk\s+proxy\s+/.test(part.text)
      const raw = part.text.replace(/^rtk\s+(?:proxy\s+)?/, '')
      // #381 preregistration: acceptance/raw-proxy runs are a separate population.
      // Unclassified proxies still fail the separate M6 adjudication requirement.
      if (proxy) { out.proxy_parts++; continue }
      const downstream = []
      for (let j = i; parts[j]?.op === '|'; j++) downstream.push(parts[j + 1]?.text || '')
      // Native pipeline mode rewrites only supported grep/rg filter stages;
      // stdin consumers such as wc are not standalone command opportunities.
      const pipelineConsumer = i > 0 && parts[i - 1].op === '|' && !/^(?:grep|rg)\b/.test(raw)
      const rawPipeline = downstream.some((s) => !safeConsumer(s))
      // Same quote state as the splitter; quoted/escaped > is argument data.
      // RTK lexer redirect_has_file_target exempts fd duplication and /dev/null.
      const redirected = [...part.syntax.matchAll(/>+\s*([^\s]+)/g)].some((m) => m[1] !== '/dev/null' && !/^&(?:\d+|-)$/.test(m[1]))
      if (explicit && !proxy && (sensitivePart(raw) || redirected || rawPipeline)) out.explicit_rtk_on_excluded_or_sensitive++
      if (explicit && logFindPart(raw)) {
        out.explicit_rtk_log_find_advisory++
        const review = exceptions[c.id]
        const disposition = validReview(review) && validLogFindReview(review)
          ? review.rtk_log_find.find((p) => p.part === i + 1)?.disposition : null
        out[disposition === 'permitted' ? 'log_find_permitted_parts' : disposition === 'requires_raw' ? 'log_find_requires_raw_parts' : 'log_find_unresolved_parts']++
      }
      // Query EVERY standalone part, even exclusions; the native hook decides eligibility.
      const alone = check(raw)
      if (alone.error) { out.unknown_calls++; continue }
      if (rawPipeline || pipelineConsumer || !alone.rewrite) { out.ineligible_parts++; continue }
      eligible++
      if (/^rtk\s+(?!proxy\b)/.test(executed[i].text)) observed++
      if (/^rtk\s+(?!proxy\b)/.test(predicted[i].text)) covered++
    }
    out.eligible_parts += eligible; out.observed_covered_parts += observed; out.replayed_covered_parts += covered
    if (eligible) { out.eligible_calls++; out.observed_all_covered_calls += observed === eligible ? 1 : 0; out.replayed_all_covered_calls += covered === eligible ? 1 : 0 }
  }
  return { ...out, status: out.unknown_calls ? 'incomplete' : 'measured', coverage: share(out.observed_covered_parts, out.eligible_parts), call_coverage: share(out.observed_all_covered_calls, out.eligible_calls) }
}
// ccusage/ccusage v20.0.24 rust/adapters/claude/src/daily.rs:410-458,505-523;
// #381 RUNBOOK mandates per-message deduplication. Keep absent counters unknown.
export function transcriptUsage(transcript, window = null) {
  const messages = new Map()
  const total = (u) => COUNTERS.reduce((n, k) => n + (Number.isFinite(u?.[k]) ? u[k] : 0), 0)
  let unidentified = 0
  for (const [i, row] of transcript.entries()) {
    if (row?.type !== 'assistant' || !row.message || row.message.model === SYNTHETIC) continue
    const at = timeOf(row)
    if (window && (at === null || at >= window.until)) continue
    const id = row.message.id || '(missing-' + i + ')'
    if (!row.message.id) unidentified++
    const prev = messages.get(id) || { current: null, baseline: null }
    if (!prev.current || total(row.message.usage) >= total(prev.current.message.usage)) prev.current = row
    if (window && at < window.since && (!prev.baseline || total(row.message.usage) >= total(prev.baseline.message.usage))) prev.baseline = row
    messages.set(id, prev)
  }
  const rows = []
  for (const { current: row, baseline } of messages.values()) {
    if (row === baseline) continue
    const usage = Object.fromEntries(COUNTERS.map((k) => {
      const n = row.message.usage?.[k], before = baseline ? baseline.message.usage?.[k] : 0
      return [k, Number.isFinite(n) && Number.isFinite(before) && n >= before ? n - before : null]
    }))
    rows.push({ ordinal: rows.length + 1, model: safeKey(row.message.model || '(unresolved)'),
      effort: EFFORTS.includes(row.effort) ? row.effort : null, usage })
  }
  const totals = Object.fromEntries(COUNTERS.map((k) => [k, rows.length && rows.every((r) => r.usage[k] !== null) ? rows.reduce((n, r) => n + r.usage[k], 0) : null]))
  return { messages: rows, totals, unidentified_messages: unidentified,
    complete: rows.length > 0 && !unidentified && Object.values(totals).every((n) => n !== null) && rows.every((r) => r.model !== '(other)' && r.model !== '(unresolved)') }
}
export function measureTranscript(transcript, { window = null, exceptions = {}, rtkCheck = false, marker = DEFAULT_MARKER } = {}) {
  const calls = new Map(), results = new Map(), rewrites = new Map()
  const inside = (row) => !window || (timeOf(row) !== null && timeOf(row) >= window.since && timeOf(row) < window.until)
  for (const [index, row] of transcript.entries()) {
    if (window && (timeOf(row) === null || timeOf(row) >= window.until)) continue
    const a = row?.attachment
    if (a?.type === 'hook_success' && a.hookName === 'PreToolUse:Bash' && /\brtk\s+hook\b/.test(a.command || '')) {
      try { const command = JSON.parse(a.stdout).hookSpecificOutput?.updatedInput?.command; if (typeof command === 'string') rewrites.set(a.toolUseID, command) } catch { /* not a rewrite */ }
    }
    for (const b of blocksOf(row)) {
      if (row.type === 'assistant' && b.type === 'tool_use' && !calls.has(b.id)) calls.set(b.id, { ...b, row, index })
      if (row.type === 'user' && b.type === 'tool_result' && !results.has(b.tool_use_id)) results.set(b.tool_use_id, { ...b, row, index })
    }
  }
  const m3 = emptySizes(), m5 = emptySizes(), carriers = counter(), excluded = counter(), m4 = emptyFetches(), fetchCarriers = counter()
  const hookContext = { inserted: 0, claimed: 0, with_marker: 0, by_hook: counter(), by_event: counter() }
  for (const row of transcript) {
    if (!inside(row)) continue
    const a = row?.attachment
    if (a?.type === 'hook_additional_context') {
      hookContext.inserted++
      bump(hookContext.by_hook, safeKey(a.hookName || '(none)'))
      bump(hookContext.by_event, safeKey(a.hookEvent || '(none)'))
      if (textOf(a.content).includes(marker)) hookContext.with_marker++
    } else if (a?.type === 'hook_success') {
      try { if (JSON.parse(a.stdout).hookSpecificOutput?.additionalContext) hookContext.claimed++ } catch { /* no claim */ }
    }
  }
  // One command-position reading per call (U1 design 2.6): carrierOf, measurement.proxy and cli_lanes all read it. It needs a verified
  // tree-sitter-bash install (loadShellParser); without one nothing is read, cli_lanes says why, and the carrier of an rtk proxy call is
  // the prefix rule of the measurements before this reading (measurement.proxy.rule).
  const parserState = shellParserStatus(), lanesOn = parserState.ok
  const analyses = new Map()
  const analysisOf = (c) => { let a = analyses.get(c); if (!a) analyses.set(c, a = callAnalysis(c)); return a }
  const proxied = lanesOn ? (c) => analysisOf(c).proxy > 0 : rtkProxyPrefix
  for (const c of calls.values()) if (inside(c.row)) countFetches(c, fetchCarriers[carrierOf(c, proxied)] ||= emptyFetches())
  for (const f of Object.values(fetchCarriers)) for (const k of Object.keys(m4)) m4[k] += f[k]
  const mcpStates = counter(), loaded = counter(), cli = emptyCliLanes()
  // measurement.proxy: the M6 population is the Bash calls carried by rtk proxy (sandbox-nested Codex calls included, as
  // before), with its invocations; rtk proxy in ctx shell code is reported apart and left out of M6, and the prefix rule's
  // count is kept for comparison with earlier receipts.
  const proxy = { calls: 0, acceptance: 0, exception: 0, unclassified: 0, invocations: lanesOn ? 0 : null, nested: 0, in_ctx_code: lanesOn ? 0 : null, prefix_rule_calls: 0,
    rule: lanesOn ? 'command_position' : 'prefix_fallback' }
  for (const c of calls.values()) {
    if (!inside(c.row)) continue
    const server = mcpServer(c.name), r = results.get(c.id)
    if (server) {
      const state = mcpStates[server] ||= { attempted: 0, succeeded: 0, failed: 0, unfinished: 0 }
      // Codex UI items can retain status without a model-visible result payload
      // (rust-v0.157.1 app-server-protocol/src/protocol/v2/item.rs McpToolCall).
      const status = r ? (r.is_error ? 'failed' : 'succeeded')
        : c.native_status === 'completed' ? 'succeeded' : c.native_status === 'failed' ? 'failed' : 'unfinished'
      state.attempted++; state[status]++
    }
    const analysis = lanesOn ? analysisOf(c) : null, carrier = carrierOf(c, proxied)
    if (rtkProxyPrefix(c)) proxy.prefix_rule_calls++
    if (carrier === 'rtk_proxy') {
      proxy.calls++
      if (lanesOn) proxy.invocations += analysis.proxy
      if (c.sandbox) proxy.nested++
      const review = exceptions[c.id]
      proxy[validReview(review) && review.proxy_purpose === 'acceptance' ? 'acceptance'
        : validReview(review) && EXCEPTIONS.includes(review.exception) ? 'exception' : 'unclassified']++
    } else if (lanesOn && isCtx(c.name) && analysis.proxy) proxy.in_ctx_code++
    if (lanesOn && analysis.errors) cli.parse_errors++ // calls whose shell text has a syntax error, not nodes
    if (lanesOn && analysis.invocations.length) countLanes(cli, analysis, callState(c, r), c.sandbox ? 'nested' : isCtx(c.name) ? 'ctx' : carrier)
  }
  for (const [id, r] of results) if (inside(r.row) && calls.get(id)?.name === 'ToolSearch' && Array.isArray(r.content)) {
    for (const ref of r.content) if (ref?.type === 'tool_reference') {
      const server = mcpServer(ref.tool_name); if (server && !mcpStates[server]) bump(loaded, server)
    }
  }
  let orphanResults = 0, invalidExceptions = 0, unknownResultBytes = 0
  // Only a later, successful edit of this exact path in this actor's transcript is automatic.
  // Source/line-citation and frozen-check requirements are semantic: a reviewed, digest-bound
  // sidecar supplies them. A command description is never proof of an exception.
  const edits = [...calls.values()].filter((c) => ['Edit', 'Write'].includes(c.name) && c.input?.file_path && results.has(c.id) && !results.get(c.id).is_error)
  for (const [id, r] of results) {
    if (!inside(r.row)) continue
    const c = calls.get(id), carrier = carrierOf(c, proxied)
    if (c?.sandbox) continue // Nested results return to code, not model context.
    if (!c) orphanResults++
    if (r.content === undefined || r.content === null) { unknownResultBytes++; continue }
    const n = contentBytes(r.content)
    addSize(carriers[carrier] ||= emptySizes(), n)
    let exception = null
    if (!r.is_error && c?.name === 'Read' && c.input?.file_path && edits.some((e) => e.index > r.index && e.input.file_path === c.input.file_path && e.row.cwd === c.row.cwd)) exception = EXCEPTIONS[0]
    if (Object.hasOwn(exceptions, id)) {
      const review = exceptions[id]
      if (validReview(review)) exception = EXCEPTIONS.includes(review.exception) ? review.exception : exception
      else invalidExceptions++
    }
    if (exception) addSize(excluded[exception] ||= emptySizes(), n)
    else addSize(m3, n)
    if (carrier === 'ctx') addSize(m5, n)
  }
  const sizes = (items) => Object.fromEntries(Object.entries(items).map(([k, s]) => [k, finishSizes(s)]))
  const unfinished = [...calls.values()].filter((c) => inside(c.row) && !c.sandbox && !results.has(c.id)).length
  return { m3: finishSizes(m3), m4: finishFetches(m4, fetchCarriers), m5: finishSizes(m5), by_carrier: sizes(carriers), exceptions: sizes(excluded),
    rtk_parts: rtkParts([...calls.values()].filter((c) => inside(c.row)), rewrites, rtkCheck, exceptions),
    usage: transcriptUsage(transcript, window),
    hook_context: hookContext,
    mcp_states: mcpStates, loaded_not_called: loaded,
    proxy: { ...proxy, acceptance_or_exception_share: share(proxy.acceptance + proxy.exception, proxy.calls) },
    cli_lanes: lanesOn ? { status: 'measured', parser: { versions: parserState.versions, wasm_sha256: parserState.wasm_sha256 }, ...cli } : { status: 'parser_unavailable', reason: parserState.reason },
    invalid_exceptions: invalidExceptions, orphan_results: orphanResults,
    sandbox_operations: [...calls.values()].filter((c) => inside(c.row) && c.sandbox).length,
    unknown_result_bytes: unknownResultBytes, bytes_complete: !unknownResultBytes && !orphanResults && !unfinished,
    calls_without_result: unfinished }
}

export function aggregateMeasurements(items) {
  const sizes = (rows) => finishSizes(rows.reduce((a, b) => ({ results: a.results + b.results, bytes: a.bytes + b.bytes,
    large_results: a.large_results + b.large_results, large_bytes: a.large_bytes + b.large_bytes, max_bytes: Math.max(a.max_bytes, b.max_bytes) }), emptySizes()))
  const groups = (key) => Object.fromEntries([...new Set(items.flatMap((m) => Object.keys(m[key])))].sort().map((k) => [k, sizes(items.map((m) => m[key][k]).filter(Boolean))]))
  const f = emptyFetches(), fetchCarriers = counter(), rtk = emptyRtk()
  for (const m of items) {
    for (const k of Object.keys(f)) f[k] += m.m4[k]
    for (const [carrier, counts] of Object.entries(m.m4.by_carrier)) {
      const target = fetchCarriers[carrier] ||= emptyFetches()
      for (const k of Object.keys(target)) target[k] += counts[k]
    }
    for (const k of Object.keys(rtk)) rtk[k] += m.rtk_parts[k]
  }
  const rtkStates = [...new Set(items.map((m) => m.rtk_parts.status))]
  const hooks = { inserted: 0, claimed: 0, with_marker: 0, by_hook: counter(), by_event: counter() }, states = counter(), loaded = counter()
  const proxies = { calls: 0, acceptance: 0, exception: 0, unclassified: 0, invocations: 0, nested: 0, in_ctx_code: 0, prefix_rule_calls: 0 }
  // CLI lanes sum their counters over the actors whose lanes were measured; actors_with_success counts the actors with at least one
  // succeeded call of the lane. An actor measured without a parser has no lane counts (cli_lanes.status parser_unavailable), so the
  // sums of a mixed set are lower bounds and say so; a measurement from before the status existed reads as measured.
  const cli = emptyCliLanes(), statusOf = (m) => m.cli_lanes ? (m.cli_lanes.status ?? 'measured') : null
  const measured = items.filter((m) => statusOf(m) === 'measured'), unavailable = items.filter((m) => statusOf(m) === 'parser_unavailable')
  const records = new Set(measured.map((m) => JSON.stringify(m.cli_lanes.parser ?? null)))
  const rules = new Set(items.map((m) => m.proxy.rule ?? 'command_position'))
  for (const m of items) {
    for (const k of ['inserted', 'claimed', 'with_marker']) hooks[k] += m.hook_context[k]
    for (const k of ['by_hook', 'by_event']) for (const [s, n] of Object.entries(m.hook_context[k])) hooks[k][s] = (hooks[k][s] || 0) + n
    for (const [s, row] of Object.entries(m.mcp_states)) for (const [k, n] of Object.entries(row)) { states[s] ||= counter(); states[s][k] = (states[s][k] || 0) + n }
    for (const [s, n] of Object.entries(m.loaded_not_called)) loaded[s] = (loaded[s] || 0) + n
    for (const k of Object.keys(proxies)) proxies[k] = proxies[k] === null || m.proxy[k] === null ? null : proxies[k] + (m.proxy[k] || 0)
    const part = m.cli_lanes
    if (!part || statusOf(m) !== 'measured') continue
    for (const [lane, row] of Object.entries(part.lanes)) {
      const total = cli.lanes[lane] ||= { ...emptyLane(), actors_with_success: 0 }
      for (const k of LANE_COUNTERS) total[k] += row[k] || 0
      for (const k of CLI_CARRIERS) total.by_carrier[k] += row.by_carrier?.[k] || 0
      if (row.succeeded) total.actors_with_success++
    }
    for (const [server, row] of Object.entries(part.mcporter_downstream)) {
      const total = cli.mcporter_downstream[server] ||= Object.fromEntries(DOWNSTREAM_COUNTERS.map((k) => [k, 0]))
      for (const k of DOWNSTREAM_COUNTERS) total[k] += row[k] || 0
    }
    for (const [lane, n] of Object.entries(part.excluded_version_help)) cli.excluded_version_help[lane] = (cli.excluded_version_help[lane] || 0) + n
    for (const k of ['calls_with_lane_invocation', 'unresolved_programs', 'remote_invocations', 'parse_errors']) cli[k] += part[k] || 0
  }
  return { actors: items.length, m3: sizes(items.map((m) => m.m3)), m5: sizes(items.map((m) => m.m5)), m4: finishFetches(f, fetchCarriers),
    hook_context: hooks, mcp_states: states, loaded_not_called: loaded,
    proxy: { ...proxies, rule: rules.size === 1 ? [...rules][0] : 'mixed', acceptance_or_exception_share: share(proxies.acceptance + proxies.exception, proxies.calls) },
    cli_lanes: !items.length ? { status: 'not_measured' }
      : unavailable.length === items.length ? { status: 'parser_unavailable', reason: unavailable[0].cli_lanes.reason }
        : { status: measured.length === items.length && records.size === 1 ? 'measured' : 'incomplete', ...(records.size === 1 ? { parser: JSON.parse([...records][0]) } : {}),
          ...(measured.length === items.length ? {} : { actors_measured: measured.length, actors_unmeasured: items.length - measured.length }), ...cli },
    m3_large_results_per_actor: tokenStats(items.map((m) => m.m3.large_results)),
    by_carrier: groups('by_carrier'), exceptions: groups('exceptions'),
    orphan_results: items.reduce((n, m) => n + m.orphan_results, 0),
    sandbox_operations: items.reduce((n, m) => n + m.sandbox_operations, 0),
    unknown_result_bytes: items.reduce((n, m) => n + m.unknown_result_bytes, 0),
    bytes_complete: items.length > 0 && items.every((m) => m.bytes_complete && !m.parse_errors),
    invalid_exceptions: items.reduce((n, m) => n + m.invalid_exceptions, 0),
    calls_without_result: items.reduce((n, m) => n + m.calls_without_result, 0),
    rtk_parts: { ...rtk, status: rtkStates.length === 1 ? rtkStates[0] : items.length ? 'incomplete' : 'not_measured',
      coverage: share(rtk.observed_covered_parts, rtk.eligible_parts), call_coverage: share(rtk.observed_all_covered_calls, rtk.eligible_calls) },
    ...(items.every((m) => m.usage) ? { usage: { complete: items.length > 0 && items.every((m) => m.usage.complete),
      totals: Object.fromEntries(COUNTERS.map((k) => [k, items.length && items.every((m) => m.usage.totals[k] !== null) ? items.reduce((n, m) => n + m.usage.totals[k], 0) : null])) } } : {}) }
}

// Private adjudications are bound to exact transcript bytes; only the exception's
// enum and counts are published. They are reviewer input, not machine proof of a citation.
export function exceptionsFor(records, digest) {
  return Object.fromEntries(records.filter((r) => r.transcript_sha256 === digest).map((r) => [r.tool_use_id, r]))
}
export function validateExceptions(records) {
  if (!Array.isArray(records) || records.some((r) => !/^[a-f0-9]{64}$/.test(r?.transcript_sha256) || typeof r.tool_use_id !== 'string' || !validReview(r))) throw new Error('invalid exception sidecar')
  if (new Set(records.map((r) => r.transcript_sha256 + ':' + r.tool_use_id)).size !== records.length) throw new Error('duplicate exception sidecar key')
  return records
}
export const loadExceptions = (path) => validateExceptions(JSON.parse(readFileSync(path, 'utf8')))

// One child's lane use. Counted: tool_use blocks (deduplicated by id), the tool_reference blocks a
// ToolSearch result returned, and PreToolUse:Bash hook rows from `rtk hook` whose stdout carries
// hookSpecificOutput.updatedInput (a rewrite). Properties: the marker in the first prompt or in
// SubagentStart hook context (never tool input or output), the SubagentStart hook types, and the
// provider-returned first-request prompt size. With a window, rows at or after until are never read;
// a tool call counts in the window of its first row, a ToolSearch load in the window of its result
// row, and an RTK rewrite in the window of its first hook row when its Bash call's tool_use row came
// before until (the hook row follows the call, so a cut between the two splits no rewrite: adjacent
// windows add up); first_prompt_tokens is null unless the first request is inside. rtkDecisions maps
// tool_use_id -> hook_decisions.decision and is joined to the Bash calls counted in the window;
// covered = allow + ask (rtk v0.50.0 src/core/tracking.rs HookOutcome::is_covered).
export function childLanes(transcript, { marker = DEFAULT_MARKER, rtkDecisions = null, window = null, exceptions = {}, rtkCheck = false } = {}) {
  const lanes = {
    tool_calls: 0, bash_calls: 0, mcp_calls: counter(), skill_calls: counter(),
    tool_search: { calls: 0, loaded: counter() },
    rtk: { hook_rewrites: 0, model_typed: 0, decisions: rtkDecisions ? { allow: 0, ask: 0, defer: 0, deny: 0, not_logged: 0, other: 0 } : null },
    fetch: { webfetch: 0, ctx_fetch_and_index: 0, bash_curl_wget: 0, bash_curl_wget_loopback: 0 },
    injected_block: { marker, in_first_prompt: false, in_subagent_start_context: false },
    subagent_start: { types: [], additional_context: false },
    first_prompt_tokens: null,
  }
  // bash: Bash calls counted in the window (the --rtk-db join); bashSeen: every Bash call before until;
  // rewrites: tool_use_id -> whether its first rewrite hook row is inside the window.
  const seen = new Set(), bash = new Set(), bashSeen = new Set(), searches = new Set(), rewrites = new Map(), types = new Set()
  let prompt = false, firstRequest = false
  for (const row of transcript) {
    if (!row || typeof row !== 'object') continue
    const at = window ? timeOf(row) : null
    if (window && (at === null || at >= window.until)) continue
    const counted = !window || at >= window.since
    if (row.type === 'user') {
      const content = row.message && row.message.content
      if (!prompt && !row.isMeta && (typeof content === 'string' || (Array.isArray(content) && content.some((b) => b && b.type === 'text')))) {
        prompt = true
        if (textOf(content).includes(marker)) lanes.injected_block.in_first_prompt = true
      }
      if (!counted || !Array.isArray(content)) continue
      for (const b of content) {
        if (!b || b.type !== 'tool_result' || !searches.has(b.tool_use_id) || !Array.isArray(b.content)) continue
        for (const ref of b.content) if (ref && ref.type === 'tool_reference' && ref.tool_name) bump(lanes.tool_search.loaded, mcpServer(ref.tool_name) || 'built-in')
      }
    } else if (row.type === 'assistant' && row.message) {
      const usage = row.message.usage
      if (!firstRequest && usage && typeof usage === 'object' && COUNTERS.some((k) => typeof usage[k] === 'number')) {
        firstRequest = true
        if (counted) lanes.first_prompt_tokens = PROMPT_COUNTERS.reduce((n, k) => n + (usage[k] || 0), 0)
      }
      if (!Array.isArray(row.message.content)) continue
      for (const b of row.message.content) {
        // A tool_use id seen before since was counted in an earlier window, never again here.
        if (!b || b.type !== 'tool_use' || seen.has(b.id)) continue
        seen.add(b.id)
        const name = String(b.name || ''), input = b.input && typeof b.input === 'object' ? b.input : {}
        if (name === 'ToolSearch') searches.add(b.id)
        if (name === 'Bash') bashSeen.add(b.id)
        if (!counted) continue
        lanes.tool_calls++
        const server = mcpServer(name)
        if (server) {
          bump(lanes.mcp_calls, server)
          if (name.endsWith('__ctx_fetch_and_index')) lanes.fetch.ctx_fetch_and_index++
        } else if (name === 'Bash') {
          lanes.bash_calls++
          bash.add(b.id)
          const command = String(input.command || '')
          if (/^\s*rtk\s/.test(command)) lanes.rtk.model_typed++
          const kind = fetchKind(command)
          if (kind === 'loopback') lanes.fetch.bash_curl_wget_loopback++
          else if (kind) lanes.fetch.bash_curl_wget++
        } else if (name === 'Skill') bump(lanes.skill_calls, input.skill || input.command ? safeKey(input.skill || input.command) : '(unnamed)')
        else if (name === 'ToolSearch') lanes.tool_search.calls++
        else if (name === 'WebFetch') lanes.fetch.webfetch++
      }
    } else if (row.type === 'attachment' && row.attachment && typeof row.attachment === 'object') {
      const a = row.attachment, hookName = String(a.hookName || '')
      if (a.hookEvent === 'SubagentStart' || hookName.startsWith('SubagentStart')) {
        if (hookName.includes(':')) types.add(safeKey(hookName.slice(hookName.indexOf(':') + 1)))
        let context = ''
        if (a.type === 'hook_additional_context') context = textOf(a.content)
        if (context.trim()) lanes.subagent_start.additional_context = true
        if (context.includes(marker)) lanes.injected_block.in_subagent_start_context = true
      } else if (a.type === 'hook_success' && hookName === 'PreToolUse:Bash' && /\brtk\s+hook\b/.test(String(a.command || ''))) {
        try { const out = JSON.parse(a.stdout || ''); if (out && out.hookSpecificOutput && out.hookSpecificOutput.updatedInput && !rewrites.has(a.toolUseID)) rewrites.set(a.toolUseID, counted) } catch { /* no rewrite */ }
      }
    }
  }
  lanes.rtk.hook_rewrites = [...rewrites].filter(([id, inWindow]) => inWindow && bashSeen.has(id)).length
  if (rtkDecisions) {
    for (const id of bash) {
      const decision = rtkDecisions.get(id)
      lanes.rtk.decisions[decision === undefined ? 'not_logged' : ['allow', 'ask', 'defer', 'deny'].includes(decision) ? decision : 'other']++
    }
  }
  lanes.subagent_start.types = [...types].sort()
  lanes.measurement = measureTranscript(transcript, { window, exceptions, rtkCheck, marker })
  if (lanes.rtk.decisions) lanes.rtk.not_logged_share = share(lanes.rtk.decisions.not_logged, lanes.bash_calls)
  return lanes
}

// Nearest-rank percentiles of the numbers in values (null entries are ignored).
export function tokenStats(values) {
  const v = values.filter((x) => typeof x === 'number').sort((a, b) => a - b)
  const rank = (percent) => v[Math.max(0, Math.ceil((percent * v.length) / 100) - 1)] // the ceil(percent * n / 100)-th smallest
  return v.length ? { n: v.length, min: v[0], p10: rank(10), median: rank(50), p90: rank(90), max: v[v.length - 1] } : { n: 0, min: null, p10: null, median: null, p90: null, max: null }
}
const share = (part, whole) => whole ? Math.round((part / whole) * 10000) / 10000 : null

// Sum of the children's lanes plus the number of children using each lane.
export function aggregateLanes(children) {
  const add = (target, source) => { for (const [k, n] of Object.entries(source)) target[k] = (target[k] || 0) + n }
  const out = {
    children: children.length, tool_calls: 0, bash_calls: 0, children_using_bash: 0,
    mcp_calls: counter(), children_using_mcp_server: counter(), skill_calls: counter(), children_with_skill_call: 0,
    tool_search: { calls: 0, children_calling: 0, loaded: counter() },
    rtk: { hook_rewrites: 0, hook_rewrite_share_of_bash: null, model_typed: 0, decisions: null, covered_share_of_bash: null },
    fetch: { webfetch: 0, ctx_fetch_and_index: 0, bash_curl_wget: 0, bash_curl_wget_loopback: 0, ctx_fetch_and_index_share: null },
    injected_block: { in_first_prompt: 0, in_subagent_start_context: 0, either: 0 },
    subagent_start: { types: counter(), additional_context: 0 },
    first_prompt_tokens: null,
  }
  for (const { lanes: l } of children) {
    out.tool_calls += l.tool_calls
    out.bash_calls += l.bash_calls
    if (l.bash_calls) out.children_using_bash++
    add(out.mcp_calls, l.mcp_calls)
    for (const s of Object.keys(l.mcp_calls)) bump(out.children_using_mcp_server, s)
    add(out.skill_calls, l.skill_calls)
    if (Object.keys(l.skill_calls).length) out.children_with_skill_call++
    out.tool_search.calls += l.tool_search.calls
    if (l.tool_search.calls) out.tool_search.children_calling++
    add(out.tool_search.loaded, l.tool_search.loaded)
    out.rtk.hook_rewrites += l.rtk.hook_rewrites
    out.rtk.model_typed += l.rtk.model_typed
    if (l.rtk.decisions) add(out.rtk.decisions = out.rtk.decisions || counter(), l.rtk.decisions)
    for (const k of ['webfetch', 'ctx_fetch_and_index', 'bash_curl_wget', 'bash_curl_wget_loopback']) out.fetch[k] += l.fetch[k]
    const ib = l.injected_block
    if (ib.in_first_prompt) out.injected_block.in_first_prompt++
    if (ib.in_subagent_start_context) out.injected_block.in_subagent_start_context++
    if (ib.in_first_prompt || ib.in_subagent_start_context) out.injected_block.either++
    for (const t of l.subagent_start.types) bump(out.subagent_start.types, t)
    if (l.subagent_start.additional_context) out.subagent_start.additional_context++
  }
  out.rtk.hook_rewrite_share_of_bash = share(out.rtk.hook_rewrites, out.bash_calls)
  if (out.rtk.decisions) out.rtk.covered_share_of_bash = share((out.rtk.decisions.allow || 0) + (out.rtk.decisions.ask || 0), out.bash_calls)
  out.rtk.not_logged_share = out.rtk.decisions ? share(out.rtk.decisions.not_logged || 0, out.bash_calls) : null
  out.fetch.ctx_fetch_and_index_share = share(out.fetch.ctx_fetch_and_index, out.fetch.webfetch + out.fetch.ctx_fetch_and_index + out.fetch.bash_curl_wget)
  out.first_prompt_tokens = tokenStats(children.map((c) => c.lanes.first_prompt_tokens))
  out.measurement = aggregateMeasurements(children.map((c) => c.lanes.measurement).filter(Boolean))
  return out
}

// RTK's hook_decisions log (tool_use_id -> decision), opened read-only; needs node:sqlite (Node >= 22.13).
export async function loadRtkDecisions(path) {
  if (!existsSync(path) || !statSync(path).isFile()) throw Object.assign(new Error('no such file'), { code: 'ENOENT' })
  const { DatabaseSync } = await import('node:sqlite')
  const db = new DatabaseSync(path, { readOnly: true, timeout: 5000 })
  try {
    const map = new Map()
    let duplicates = 0
    const rows = db.prepare('SELECT tool_use_id, decision FROM hook_decisions ORDER BY id').all()
    for (const r of rows) { if (map.has(r.tool_use_id)) duplicates++; map.set(r.tool_use_id, r.decision) }
    return { map, rows: rows.length, duplicates }
  } finally { db.close() }
}

// Every child transcript (agent-<id>.jsonl under a subagents/ directory) below the roots, with its spawn
// path: a workflow child sits in subagents/workflows/wf_<run>/, an Agent-tool child directly in subagents/.
// Symbolic links are not followed; each directory that cannot be read adds one to unreadable.count.
export function findChildTranscripts(roots, unreadable = { count: 0 }, includeMain = false) {
  const found = new Map()
  const walk = (dir) => {
    let entries
    try { entries = readdirSync(dir, { withFileTypes: true }) } catch { unreadable.count++; return }
    for (const entry of entries) {
      const full = join(dir, entry.name)
      if (entry.isDirectory()) { walk(full); continue }
      const m = entry.isFile() && /\/subagents\/(workflows\/wf_[^/]+\/)?agent-[^/]+\.jsonl$/.exec(full.split('\\').join('/'))
      if (m && !found.has(full)) found.set(full, m[1] ? 'workflow' : 'agent_tool')
      else if (includeMain && entry.isFile() && entry.name.endsWith('.jsonl') && !full.split('\\').join('/').includes('/subagents/') && !['journal.jsonl'].includes(entry.name)) found.set(full, 'main')
    }
  }
  for (const root of roots) walk(resolve(root))
  return [...found].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([path, spawn]) => ({ path, spawn }))
}

const LANES_LIMITS = 'Counts come from native transcript rows inside [since, until); rows at or after until are never read. A tool call (tool_use blocks deduplicated by id) counts in the window of its first row, a ToolSearch load (tool_reference blocks in its result) in the window of the result row, and an RTK rewrite (a PreToolUse:Bash row from `rtk hook` whose stdout carries updatedInput, for a Bash call whose tool_use row came before until) in the window of its hook row, so adjacent windows add up. RTK decisions (with --rtk-db) are hook_decisions rows joined 1:1 by tool_use_id to the Bash calls counted in the window; covered = allow + ask. A call whose hook row falls on the other side of a window edge therefore counts in hook_rewrites and in decisions of different windows. The marker is looked for only in the first prompt and in SubagentStart hook context, never in tool input or output. first_prompt_tokens is provider-returned (input + cache read + cache creation) and counted only for children whose first request is inside the window. curl/wget counts only in command position of the text a shell runs (quoted strings, heredoc bodies, escaped characters and comments are data unless sh -c, eval, ssh or a shell heredoc runs them, though $(...) and `...` inside double quotes or an unquoted heredoc still run: bash(1) QUOTING, COMMENTS and Here Documents), optionally behind the shell keywords do, then, else, elif, if, while, until, ! and { and behind rtk, sudo, env, command, exec, time, nice, nohup or timeout N; a call whose literal URLs are all loopback is counted apart. ctx_fetch_and_index_share is ctx_fetch_and_index / (WebFetch + ctx_fetch_and_index + remote curl/wget): a fetch run inside a Context Mode sandbox (ctx_execute or ctx_batch_execute code), a gh api call and fetch() or an HTTP library in a script are in no lane. Names that are not name-shaped are counted under (other). Transcripts not modified since the window start are skipped unread. Every child transcript is a child, so a Workflow call the runtime re-ran under the same key (superseded_attempts in the per-run report) is one child per attempt. Children whose agent type starts with blind- are negative controls and are left out of workers; by_spawn_and_agent_type compares spawn paths within one agent type.'

const CLI_LANES_LIMITS = 'cli_lanes counts lane executables in command position of the shell text a call runs, read with the pinned tree-sitter-bash install that loadShellParser verified (its versions and wasm sha256 values are in cli_lanes.parser; without it cli_lanes is only { status: parser_unavailable, reason } and measurement.proxy uses the prefix rule, rule prefix_fallback) (Bash commands, shell ctx code, ctx_batch_execute commands and sandbox-nested Codex commands), behind wrappers, package runners and rtk proxy, with rtk proxy calls in ctx code apart from measurement.proxy; it cannot see aliases, shell functions called by name (a function body counts where it is defined), programs a variable names or eval runs, scripts and Makefile or npm targets that call a lane, find -exec, parallel, watch or other unknown wrappers, subprocesses of non-shell code, or how often xargs runs its utility. A call state covers every command of the call (ambiguous marks more than one), and ssh-run lane invocations count only in remote_invocations.'

// Lane use of every child transcript under the roots that has a row inside [since, until).
export function sweepLanes(roots, { since = null, until = null, marker = DEFAULT_MARKER, rtk = null, rtkCheck = false, exceptionRecords = [] } = {}) {
  const window = { since: since ?? -Infinity, until: until ?? Infinity }
  const unreadable = { count: 0 }
  const files = findChildTranscripts(roots, unreadable, true)
  const children = []
  const main = []
  let parseErrors = 0, skipped = 0, mainParseErrors = 0, mainSkipped = 0
  const measuredDigests = new Set()
  for (const file of files) {
    if (Number.isFinite(window.since)) {
      try { if (statSync(file.path).mtimeMs < window.since) { if (file.spawn === 'main') mainSkipped++; else skipped++; continue } } catch { continue }
    }
    const { rows, errors, digest } = readRows(file.path)
    if (file.spawn === 'main') mainParseErrors += errors
    else parseErrors += errors
    let first = Infinity, last = -Infinity, inside = false
    for (const row of rows) {
      const t = timeOf(row)
      if (t === null) continue
      if (t < first) first = t
      if (t > last) last = t
      if (t >= window.since && t < window.until) inside = true
    }
    if (!inside) continue
    let meta = null
    try { meta = JSON.parse(readFileSync(file.path.replace(/\.jsonl$/, '.meta.json'), 'utf8')) } catch { meta = null }
    if (file.spawn === 'main' && !rows.some((r) => ['assistant', 'user'].includes(r?.type))) continue
    measuredDigests.add(digest)
    const actor = {
      spawn: file.spawn, session: file.path.split('\\').join('/').replace(/\/subagents\/.*$/, ''), first,
      agent_type: meta && typeof meta.agentType === 'string' && meta.agentType ? safeKey(meta.agentType) : '(none)',
      started_before_window: first < window.since, ran_past_window_end: last >= window.until,
      lanes: childLanes(rows, { marker, rtkDecisions: rtk ? rtk.map : null, window, rtkCheck, exceptions: exceptionsFor(exceptionRecords, digest) }),
    }
    actor.lanes.measurement.parse_errors = errors
    if (errors) { actor.lanes.measurement.bytes_complete = false; actor.lanes.measurement.usage.complete = false }
    ;(file.spawn === 'main' ? main : children).push(actor)
  }
  // Sessions are reported as session-01, session-02 ... in order of their earliest child row, never by id.
  const firstBySession = new Map()
  for (const c of children) firstBySession.set(c.session, Math.min(firstBySession.get(c.session) ?? Infinity, c.first))
  const ordinal = new Map([...firstBySession].sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1)).map(([s], i) => [s, 'session-' + String(i + 1).padStart(2, '0')]))
  for (const c of children) c.session_ordinal = ordinal.get(c.session)
  const group = (keep) => aggregateLanes(children.filter(keep))
  const byKey = (key, among = children) => Object.fromEntries([...new Set(among.map((c) => c[key]))].sort().map((v) => [v, aggregateLanes(among.filter((c) => c[key] === v))]))
  // Spawn-path totals mix agent types (an Agent-tool Explore child and a workflow general-purpose child differ
  // in their tools), so a lane is compared between spawn paths within one agent type.
  const bySpawnAndType = Object.fromEntries([...new Set(children.map((c) => c.spawn))].sort().map((s) => [s, byKey('agent_type', children.filter((c) => c.spawn === s))]))
  const blind = (c) => c.agent_type.startsWith('blind-')
  const iso = (t) => Number.isFinite(t) ? new Date(t).toISOString() : null
  const bound = exceptionRecords.filter((r) => measuredDigests.has(r.transcript_sha256)).length
  return {
    kind: 'claude_child_lane_usage', schema_version: 1,
    window: { since: iso(window.since), until: iso(window.until) }, marker,
    roots_count: roots.length, unreadable_directories: unreadable.count,
    transcripts_found: files.filter((f) => f.spawn !== 'main').length, all_transcripts_found: files.length, transcripts_skipped_unmodified: skipped,
    main_transcripts_found: files.filter((f) => f.spawn === 'main').length,
    main_transcripts_skipped_unmodified: mainSkipped, main_parse_errors: mainParseErrors,
    children_in_window: children.length, sessions_in_window: ordinal.size, parse_errors: parseErrors,
    sidecar_records: { bound, unbound: exceptionRecords.length - bound },
    children_started_before_window: children.filter((c) => c.started_before_window).length,
    children_ran_past_window_end: children.filter((c) => c.ran_past_window_end).length,
    rtk_db: rtk ? { joined: true, rows: rtk.rows, duplicate_tool_use_ids: rtk.duplicates } : { joined: false },
    groups: {
      all: group(() => true), workers: group((c) => !blind(c)), negative_controls: group(blind),
      by_spawn: byKey('spawn'), by_agent_type: byKey('agent_type'), by_spawn_and_agent_type: bySpawnAndType, by_session: byKey('session_ordinal'),
    },
    main_sessions_in_window: main.length, main: aggregateLanes(main),
    actors: [...children, ...main].map((c, i) => ({ ordinal: i + 1, actor: c.spawn === 'main' ? 'main' : 'child',
      spawn: c.spawn, agent_type: c.agent_type, session_ordinal: c.session_ordinal ?? null, measurement: c.lanes.measurement })),
    limits: 'Legacy lane fields: ' + LANES_LIMITS + ' PR-A measurement fields supersede the legacy fetch share and hook-context interpretation: UTF-8 text payloads and individually serialized non-text blocks across every carrier; nested static fetch operations; all-hook insertions separate from stdout claims. Main actors and file counters are separate from children. Sidecar binding reports counts only. rtk_parts needs --rtk-check and keeps observed command coverage separate from native replay. ' + CLI_LANES_LIMITS + ' Unknown usage and missing results cannot establish acceptance; see workflows/README.md.',
  }
}

// Stable, key-sorted JSON (objects only; array order is kept).
export const sortedJson = (value) => JSON.stringify(value, (k, v) => v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : v, 2)

export function summarizeChild(started, result, meta, transcript, transcriptFound = true, lanesOptions = {}) {
  const byId = new Map()
  const counted = (u) => u && typeof u === 'object' && COUNTERS.some((k) => typeof u[k] === 'number')
  const withoutUsage = new Set()
  for (const row of transcript) {
    if (!row || row.type !== 'assistant' || !row.message) continue
    // An assistant message with no numeric counter would silently undercount the child.
    if (!counted(row.message.usage)) { withoutUsage.add(row.message.id || row.uuid); continue }
    const id = row.message.id || row.uuid
    const prev = byId.get(id)
    if (!prev || (row.message.usage.output_tokens || 0) >= (prev.message.usage.output_tokens || 0)) byId.set(id, row)
  }
  const messages = [...byId.values()]
  const sum = (rows) => Object.fromEntries(COUNTERS.map((k) => [k, rows.reduce((n, r) => n + (r.message.usage[k] || 0), 0)]))
  const usage = sum(messages)
  const usageByModel = {}
  for (const m of new Set(messages.map((r) => r.message.model || '(unresolved)'))) usageByModel[m] = sum(messages.filter((r) => (r.message.model || '(unresolved)') === m))
  const resolved = [...new Set(messages.map((r) => r.message.model).filter(Boolean))]
  const efforts = [...new Set(messages.map((r) => r.effort).filter(Boolean))]
  const requested = meta && typeof meta.model === 'string' && meta.model ? meta.model : null
  const issues = []
  // Usage-integrity failures: provider usage that by_resolved_model cannot count or attribute. They are issues of any
  // attempt, and a superseded attempt keeps them as usage_issues (summarizeRun).
  const usageIssues = []
  if (!result) issues.push('no result entry in journal')
  else if (result.result === null || result.result === undefined) issues.push('null result')
  if (!meta) issues.push('missing meta.json')
  if (!transcriptFound) usageIssues.push('no transcript file (usage unknown)')
  const neverCounted = [...withoutUsage].filter((id) => !byId.has(id)).length
  if (neverCounted) usageIssues.push(neverCounted + ' assistant message(s) without provider usage')
  const unresolved = messages.filter((r) => !r.message.model).length
  if (unresolved) usageIssues.push(unresolved + ' assistant message(s) without a resolved model')
  if (!messages.length) issues.push('no assistant usage in transcript')
  issues.push(...usageIssues)
  if (!requested) issues.push("model not requested explicitly (the child ran its definition's model, CLAUDE_CODE_SUBAGENT_MODEL or the coordinator's model)")
  else if (!resolved.length || resolved.some((m) => !m.toLowerCase().includes(requested.toLowerCase()))) issues.push('resolved model outside requested family: ' + (resolved.join(',') || '(none resolved)'))
  // Classifier fallback (model-config doc, "Automatic model fallback"): after a flagged request the
  // child continues on the fallback model, so a change of resolved model within the child, or a model
  // older than the alias's documented resolution for the entry's client version, is a substitution.
  const real = messages.filter((r) => r.message.model && r.message.model !== SYNTHETIC)
  const runs = real.map((r) => r.message.model).filter((m, i, all) => i === 0 || m !== all[i - 1])
  if (runs.length > 1) issues.push('resolved model changed within the child: ' + runs.join(' -> '))
  if (requested) {
    const older = new Set()
    for (const r of real) {
      const want = expectedModel(requested, r.version)
      if (want && r.message.model.toLowerCase().includes(requested.toLowerCase()) && olderThan(r.message.model, want)) older.add(r.message.model + ' on ' + r.version + ' (documented ' + requested + ': ' + want + ')')
    }
    if (older.size) issues.push('resolved model older than the documented alias resolution: ' + [...older].join(', '))
  }
  return {
    agent_id: started.agentId, label: started.label ?? null, phase: started.phase ?? null,
    agent_type: meta ? meta.agentType ?? null : null,
    requested_model: requested, resolved_models: resolved, efforts, web_search: webSearch(transcript),
    requests: messages.length, usage, usage_by_model: usageByModel,
    // Provider-returned cache read on the first request: evidence that the shared
    // prefix was served from cache for this child. Zero is not proof of a miss policy.
    first_request_cache_read: messages.length ? messages[0].message.usage.cache_read_input_tokens || 0 : null,
    // Whole first prompt (system, tool definitions, injected instructions, packet):
    // the fixed cost of spawning this child before it does any work.
    first_request_prompt_tokens: messages.length ? PROMPT_COUNTERS.reduce((n, k) => n + (messages[0].message.usage[k] || 0), 0) : null,
    complete: issues.length === 0, issues, ...(usageIssues.length ? { usage_issues: usageIssues } : {}),
    // Tool lanes, hook rewrites and the injected-block marker (childLanes above); names and counts only.
    lanes: childLanes(transcript, lanesOptions),
  }
}

export function summarizeRun(dir, lanesOptions = {}) {
  const journalPath = join(dir, 'journal.jsonl')
  if (!existsSync(journalPath)) return { status: 'incomplete', reason: 'journal.jsonl not found in ' + dir, children: [] }
  const journal = lines(journalPath)
  const results = new Map(journal.filter((e) => e.type === 'result').map((e) => [e.agentId, e]))
  const started = journal.filter((e) => e.type === 'started' && e.agentId)
  // The runtime re-runs a call under the same journal key after a pause (observed on 2026-09-26: "Usage limit
  // reached ... Workflow paused; waiting agents re-run shortly after the reset", then "Re-running 8 waiting
  // agents"). An attempt with no result entry whose key started again later was superseded by that later attempt:
  // it is listed in superseded_attempts, not among the children, and its usage still counts in by_resolved_model.
  const supersededBy = new Map()
  started.forEach((s, i) => {
    if (results.has(s.agentId) || typeof s.key !== 'string' || !s.key) return
    const later = started.slice(i + 1).find((t) => t.key === s.key)
    if (later) supersededBy.set(s.agentId, later.agentId)
  })
  const attempts = started.map((s) => {
    const metaPath = join(dir, 'agent-' + s.agentId + '.meta.json')
    const logPath = join(dir, 'agent-' + s.agentId + '.jsonl')
    let meta = null
    try { meta = existsSync(metaPath) ? JSON.parse(readFileSync(metaPath, 'utf8')) : null } catch { meta = null }
    const found = existsSync(logPath)
    const data = found ? readRows(logPath) : { rows: [], errors: 0, digest: '' }
    const child = summarizeChild(s, results.get(s.agentId) || null, meta, data.rows, found,
      { ...lanesOptions, exceptions: exceptionsFor(lanesOptions.exceptionRecords || [], data.digest) })
    return supersededBy.has(s.agentId) ? { ...child, superseded_by: supersededBy.get(s.agentId) } : child
  })
  const children = attempts.filter((c) => !c.superseded_by)
  const superseded = attempts.filter((c) => c.superseded_by)
  const byModel = {}
  for (const c of attempts) for (const [m, u] of Object.entries(c.usage_by_model)) {
    byModel[m] = byModel[m] || { children: 0, ...Object.fromEntries(COUNTERS.map((k) => [k, 0])) }
    byModel[m].children++
    for (const k of COUNTERS) byModel[m][k] += u[k]
  }
  const incomplete = children.filter((c) => !c.complete)
  // A superseded attempt returned nothing by definition, but usage it holds that by_resolved_model cannot count
  // (usage_issues) leaves the run's usage incomplete.
  const uncounted = superseded.filter((c) => c.usage_issues)
  const rerun = superseded.length ? '; ' + superseded.length + ' earlier attempt(s) that returned nothing were re-run under the same call key (superseded_attempts, whose usage by_resolved_model counts)' : ''
  const gaps = [incomplete.length ? incomplete.length + ' child(ren) incomplete' : null,
    uncounted.length ? uncounted.length + ' superseded attempt(s) with usage by_resolved_model cannot count (usage_issues)' : null].filter(Boolean)
  return {
    status: !children.length || gaps.length ? 'incomplete' : 'complete',
    reason: (!children.length ? 'journal has no started children' : gaps.length ? gaps.join('; ') : 'every child has an explicit requested model, one matching resolved model no older than its documented alias resolution, returned usage and a non-null result') + rerun,
    multi_model_children: children.filter((c) => c.resolved_models.length > 1).map((c) => c.label || c.agent_id),
    // Over every attempt (children and superseded attempts), like by_resolved_model.
    web_search: {
      calls: attempts.reduce((n, c) => n + c.web_search.calls, 0),
      capped: attempts.reduce((n, c) => n + c.web_search.capped, 0),
      capped_children: attempts.filter((c) => c.web_search.capped).map((c) => c.label || c.agent_id),
    },
    children, ...(superseded.length ? { superseded_attempts: superseded } : {}), by_resolved_model: byModel,
  }
}

// Children and superseded attempts whose resolved efforts are not exactly [required] (none recorded counts as a mismatch).
export function effortMismatches(run, required) {
  return [...run.children, ...(run.superseded_attempts || [])].filter((c) => c.efforts.length !== 1 || c.efforts[0] !== required).map((c) => ({ child: c.label || c.agent_id, efforts: c.efforts, ...(c.superseded_by ? { superseded_by: c.superseded_by } : {}) }))
}

// Newest native Workflow transcript directory for a working directory. The projects
// layout (<config>/projects/<cwd with non-alphanumerics as '-'>/<session>/subagents/workflows/wf_*)
// is observed native behavior, not a documented interface: return null rather than guess.
export function latestRunDir(cwd, configDir) {
  const root = join(configDir, 'projects', cwd.replace(/[^A-Za-z0-9]/g, '-'))
  if (!existsSync(root)) return null
  let best = null
  for (const session of readdirSync(root)) {
    const wf = join(root, session, 'subagents', 'workflows')
    if (!existsSync(wf)) continue
    for (const run of readdirSync(wf)) {
      const journal = join(wf, run, 'journal.jsonl')
      if (!run.startsWith('wf_') || !existsSync(journal)) continue
      const mtime = statSync(journal).mtimeMs
      if (!best || mtime > best.mtime) best = { dir: join(wf, run), mtime }
    }
  }
  return best ? best.dir : null
}

const USAGE = 'usage: child-usage.mjs <workflow transcript dir> | --latest [--require-effort <level>] [--rtk-db <history.db>] [--marker <text>]\n' +
  '       child-usage.mjs --lanes-sweep --root <dir> [--root <dir> ...] [--since <ISO>] [--until <ISO>] [--rtk-db <history.db>] [--marker <text>]\n' +
  '       both modes: [--rtk-check] [--exceptions <private-json>] [--shell-parser <tree-sitter-bash install dir>]'
// { error } or the parsed options. An option value may not start with "--"; each option but --root is given once.
export function parseArgs(argv) {
  const o = { positional: [], roots: [], sweep: false }
  const valued = { '--require-effort': 'required', '--rtk-db': 'rtkDb', '--marker': 'marker', '--since': 'since', '--until': 'until', '--exceptions': 'exceptionsPath', '--shell-parser': 'shellParser' }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--root' || Object.hasOwn(valued, a)) {
      const v = argv[i + 1]
      if (v === undefined || v.startsWith('--')) return { error: a === '--require-effort' ? '--require-effort needs one of ' + EFFORTS.join(', ') : a + ' needs a value' }
      if (a === '--root') o.roots.push(v)
      else if (o[valued[a]] !== undefined) return { error: a + ' may be given once' }
      else o[valued[a]] = v
      i++
    } else if (a === '--rtk-check') {
      if (o.rtkCheck) return { error: '--rtk-check may be given once' }
      o.rtkCheck = true
    } else if (a === '--lanes-sweep') {
      if (o.sweep) return { error: '--lanes-sweep may be given once' }
      o.sweep = true
    } else if (a.startsWith('--') && a !== '--latest') return { error: 'unknown option ' + a + '\n' + USAGE }
    else o.positional.push(a)
  }
  if (o.required !== undefined && !EFFORTS.includes(o.required)) return { error: '--require-effort needs one of ' + EFFORTS.join(', ') }
  if (o.marker !== undefined && !o.marker.trim()) return { error: '--marker needs non-blank text' }
  for (const k of ['since', 'until']) if (o[k] !== undefined && !Number.isFinite(Date.parse(o[k]))) return { error: '--' + k + ' needs an ISO-8601 time' }
  if (o.since !== undefined && o.until !== undefined && Date.parse(o.since) >= Date.parse(o.until)) return { error: '--since must be earlier than --until' }
  if (o.sweep) {
    if (!o.roots.length) return { error: '--lanes-sweep needs at least one --root' }
    if (o.positional.length) return { error: '--lanes-sweep takes --root directories, not a transcript dir' }
    if (o.required !== undefined) return { error: '--require-effort checks one run; it does not apply to --lanes-sweep' }
  } else {
    if (o.roots.length || o.since !== undefined || o.until !== undefined) return { error: '--root, --since and --until need --lanes-sweep' }
    if (o.positional.length !== 1) return { error: USAGE }
  }
  return o
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const o = parseArgs(process.argv.slice(2))
  if (o.error) { console.error(o.error); process.exit(2) }
  let rtk = null
  if (o.rtkDb) {
    try { rtk = await loadRtkDecisions(o.rtkDb) } catch (e) { console.error('--rtk-db: cannot read the hook_decisions table read-only (' + (e.code || e.message) + ')'); process.exit(2) }
  }
  const marker = o.marker ?? DEFAULT_MARKER
  let exceptionRecords = []
  if (o.exceptionsPath) {
    try { exceptionRecords = loadExceptions(o.exceptionsPath) } catch { console.error('--exceptions: invalid or unreadable sidecar'); process.exit(2) }
  }
  // The verified tree-sitter-bash install that cli_lanes needs (loadShellParser: --shell-parser, CHILD_USAGE_SHELL_PARSER, then the
  // default directory). An install named on the command line that cannot be honored is an error, like --rtk-db; one that is missing
  // by default or by the environment leaves cli_lanes as parser_unavailable, and the rest of the report is unchanged.
  const parserLoad = await loadShellParser(o.shellParser)
  if (o.shellParser !== undefined && !parserLoad.ok) { console.error('--shell-parser: ' + parserLoad.reason); process.exit(2) }
  // Output goes out through stdout.write and process.exitCode, never process.exit(): process.exit() drops stdout
  // writes still pending, and a pipe takes 64 KiB at once. Only the short error messages above exit directly.
  if (o.sweep) {
    const notDirs = o.roots.filter((r) => { try { return !statSync(r).isDirectory() } catch { return true } })
    if (notDirs.length) { console.error('--root is not a readable directory: ' + notDirs.join(', ')); process.exit(2) }
    process.stdout.write(sortedJson(sweepLanes(o.roots, { since: o.since === undefined ? null : Date.parse(o.since), until: o.until === undefined ? null : Date.parse(o.until), marker, rtk, rtkCheck: o.rtkCheck, exceptionRecords })) + '\n')
    process.exitCode = 0
  } else {
    const target = o.positional[0]
    const required = o.required ?? null
    const dir = target === '--latest' ? latestRunDir(process.cwd(), process.env.CLAUDE_CONFIG_DIR || join(homedir(), '.claude')) : target
    if (target === '--latest' && !dir) { console.error('no native Workflow run found for ' + process.cwd()); process.exit(2) }
    const out = { transcript_dir: dir, ...summarizeRun(dir, { marker, rtkDecisions: rtk ? rtk.map : null, rtkCheck: o.rtkCheck, exceptionRecords }) }
    if (rtk) out.rtk_db = { joined: true, rows: rtk.rows, duplicate_tool_use_ids: rtk.duplicates }
    if (required) out.effort_mismatches = effortMismatches(out, required)
    process.stdout.write(JSON.stringify(out, null, 2) + '\n')
    process.exitCode = out.status === 'complete' && !(required && out.effort_mismatches.length) ? 0 : 1
  }
}
