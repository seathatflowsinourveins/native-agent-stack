#!/usr/bin/env node
// Per-child requested/resolved model, effort, provider usage and lane use for one native
// Workflow run. Reads the run's transcript directory (journal.jsonl,
// agent-<id>.meta.json, agent-<id>.jsonl) and changes nothing.
//   node .claude/workflows/child-usage.mjs <transcriptDir>   (the "Transcript dir" the Workflow tool prints)
//   node .claude/workflows/child-usage.mjs --latest          (newest run recorded for this working directory)
//   add --require-effort max to also fail (exit 1) when any child ran at another effort
//   (docs/tasks/2026-09-23-max-effort-default.md: a stage without effort inherits the
//   coordinator's xhigh, and CLAUDE_CODE_EFFORT_LEVEL overrides every stage).
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
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const COUNTERS = ['input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']
const PROMPT_COUNTERS = ['input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']
const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']
const readRows = (file) => {
  let errors = 0
  const rows = []
  for (const l of readFileSync(file, 'utf8').split('\n')) {
    if (!l.trim()) continue
    try { rows.push(JSON.parse(l)) } catch { errors++ }
  }
  return { rows, errors }
}
const lines = (file) => readRows(file).rows.filter(Boolean)
// Client-written rows (an API error such as a usage-limit notice) carry this model; the
// family check still reports them, and the two fallback checks below ignore them.
const SYNTHETIC = '<synthetic>'
// Documented resolution of an alias on the Anthropic API by the client version that wrote the
// transcript entry, as [first client version, model] rows in ascending order (model-config doc,
// fetched 2026-09-24: opus is Opus 5.5 from v2.1.280, Opus 5 from v2.1.219, Opus 4.8 from v2.1.154).
// An entry older than the first row, and an alias without rows (sonnet, haiku, fable), has no
// expectation. An ANTHROPIC_DEFAULT_OPUS_MODEL pin to an older model would be flagged; none is set here.
export const ALIAS_RESOLUTION = { opus: [['2.1.154', 'claude-opus-4-8'], ['2.1.219', 'claude-opus-5'], ['2.1.280', 'claude-opus-5-5']] }
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
// A quoted string a shell runs: the argument of sh/bash/zsh/dash/ksh/su ... -c, of eval, or of ssh <host>.
const RUN_QUOTED = /(?:^|[\s;&|(])(?:(?:(?:ba|z|da|k)?sh|su)(?:\s+-[A-Za-z]+)*\s+-[A-Za-z]*c|eval|ssh(?:\s+-\S+)*\s+\S+)\s*$/
const SHELL_WORD = /^(?:(?:ba|z|da|k)?sh|ssh)$/
const HEREDOC = /(?<!<)<<(?!<)-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1/
const WRAPPERS = new Set(['sudo', 'env', 'command', 'exec', 'nice', 'nohup', 'time', 'rtk'])
// The program of the last simple command in `prefix`: assignments, options, wrappers and a timeout duration skipped.
const programOf = (prefix) => {
  const words = prefix.split(/[;&|(]/).pop().trim().split(/\s+/).filter(Boolean)
  for (let i = 0; i < words.length; i++) {
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[i]) || words[i].startsWith('-') || WRAPPERS.has(words[i])) continue
    if (words[i] === 'timeout') { i++; continue }
    return words[i].split('/').pop()
  }
  return ''
}
// The command text a shell would run: a heredoc body is data unless the heredoc feeds a shell, and a quoted
// string is data unless a shell runs it (RUN_QUOTED); inside double quotes, $(...) and `...` still run.
// Data keeps its words (so URL arguments stay) but loses the separators that would put a word in command position.
export function executedText(command) {
  const lines = String(command || '').split('\n'), kept = []
  for (let i = 0; i < lines.length; i++) {
    kept.push(lines[i])
    const m = HEREDOC.exec(lines[i])
    if (!m || SHELL_WORD.test(programOf(lines[i].slice(0, m.index)))) continue
    while (i + 1 < lines.length && lines[i + 1].replace(/^\t+/, '') !== m[2]) { i++; kept.push('') }
  }
  const text = kept.join('\n')
  let out = ''
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '\\') { out += text.slice(i, i + 2); i++; continue }
    if (ch !== "'" && ch !== '"') { out += ch; continue }
    let j = i + 1
    while (j < text.length && text[j] !== ch) j += ch === '"' && text[j] === '\\' ? 2 : 1
    const inner = text.slice(i + 1, j)
    if (RUN_QUOTED.test(out)) out += ';' + inner + ';'
    else if (ch === '"') out += '"' + inner.replace(/\$\([^()]*\)|`[^`]*`|[;&|()`\n]/g, (s) => s.length > 1 ? s : ' ') + '"'
    else out += "'" + inner.replace(/[;&|()`$\n]/g, ' ') + "'"
    i = j
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
export function childLanes(transcript, { marker = DEFAULT_MARKER, rtkDecisions = null, window = null } = {}) {
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
        else if (a.type === 'hook_success') {
          try { const out = JSON.parse(a.stdout || ''); const c = out && out.hookSpecificOutput && out.hookSpecificOutput.additionalContext; context = typeof c === 'string' ? c : '' } catch { context = '' }
        }
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
  out.fetch.ctx_fetch_and_index_share = share(out.fetch.ctx_fetch_and_index, out.fetch.webfetch + out.fetch.ctx_fetch_and_index + out.fetch.bash_curl_wget)
  out.first_prompt_tokens = tokenStats(children.map((c) => c.lanes.first_prompt_tokens))
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
export function findChildTranscripts(roots, unreadable = { count: 0 }) {
  const found = new Map()
  const walk = (dir) => {
    let entries
    try { entries = readdirSync(dir, { withFileTypes: true }) } catch { unreadable.count++; return }
    for (const entry of entries) {
      const full = join(dir, entry.name)
      if (entry.isDirectory()) { walk(full); continue }
      const m = entry.isFile() && /\/subagents\/(workflows\/wf_[^/]+\/)?agent-[^/]+\.jsonl$/.exec(full.split('\\').join('/'))
      if (m && !found.has(full)) found.set(full, m[1] ? 'workflow' : 'agent_tool')
    }
  }
  for (const root of roots) walk(resolve(root))
  return [...found].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([path, spawn]) => ({ path, spawn }))
}

const LANES_LIMITS = 'Counts come from native transcript rows inside [since, until); rows at or after until are never read. A tool call (tool_use blocks deduplicated by id) counts in the window of its first row, a ToolSearch load (tool_reference blocks in its result) in the window of the result row, and an RTK rewrite (a PreToolUse:Bash row from `rtk hook` whose stdout carries updatedInput, for a Bash call whose tool_use row came before until) in the window of its hook row, so adjacent windows add up. RTK decisions (with --rtk-db) are hook_decisions rows joined 1:1 by tool_use_id to the Bash calls counted in the window; covered = allow + ask. A call whose hook row falls on the other side of a window edge therefore counts in hook_rewrites and in decisions of different windows. The marker is looked for only in the first prompt and in SubagentStart hook context, never in tool input or output. first_prompt_tokens is provider-returned (input + cache read + cache creation) and counted only for children whose first request is inside the window. curl/wget counts only in command position of the text a shell runs (quoted strings and heredoc bodies are data unless sh -c, eval, ssh or a shell heredoc runs them), optionally behind the shell keywords do, then, else, elif, if, while, until, ! and { and behind rtk, sudo, env, command, exec, time, nice, nohup or timeout N; a call whose literal URLs are all loopback is counted apart. ctx_fetch_and_index_share is ctx_fetch_and_index / (WebFetch + ctx_fetch_and_index + remote curl/wget): a fetch run inside a Context Mode sandbox (ctx_execute or ctx_batch_execute code), a gh api call and fetch() or an HTTP library in a script are in no lane. Names that are not name-shaped are counted under (other). Transcripts not modified since the window start are skipped unread. Every child transcript is a child, so a Workflow call the runtime re-ran under the same key (superseded_attempts in the per-run report) is one child per attempt. Children whose agent type starts with blind- are negative controls and are left out of workers; by_spawn_and_agent_type compares spawn paths within one agent type.'

// Lane use of every child transcript under the roots that has a row inside [since, until).
export function sweepLanes(roots, { since = null, until = null, marker = DEFAULT_MARKER, rtk = null } = {}) {
  const window = { since: since ?? -Infinity, until: until ?? Infinity }
  const unreadable = { count: 0 }
  const files = findChildTranscripts(roots, unreadable)
  const children = []
  let parseErrors = 0, skipped = 0
  for (const file of files) {
    if (Number.isFinite(window.since)) {
      try { if (statSync(file.path).mtimeMs < window.since) { skipped++; continue } } catch { continue }
    }
    const { rows, errors } = readRows(file.path)
    parseErrors += errors
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
    children.push({
      spawn: file.spawn, session: file.path.split('\\').join('/').replace(/\/subagents\/.*$/, ''), first,
      agent_type: meta && typeof meta.agentType === 'string' && meta.agentType ? safeKey(meta.agentType) : '(none)',
      started_before_window: first < window.since, ran_past_window_end: last >= window.until,
      lanes: childLanes(rows, { marker, rtkDecisions: rtk ? rtk.map : null, window }),
    })
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
  return {
    kind: 'claude_child_lane_usage', schema_version: 1,
    window: { since: iso(window.since), until: iso(window.until) }, marker,
    roots_count: roots.length, unreadable_directories: unreadable.count,
    transcripts_found: files.length, transcripts_skipped_unmodified: skipped,
    children_in_window: children.length, sessions_in_window: ordinal.size, parse_errors: parseErrors,
    children_started_before_window: children.filter((c) => c.started_before_window).length,
    children_ran_past_window_end: children.filter((c) => c.ran_past_window_end).length,
    rtk_db: rtk ? { joined: true, rows: rtk.rows, duplicate_tool_use_ids: rtk.duplicates } : { joined: false },
    groups: {
      all: group(() => true), workers: group((c) => !blind(c)), negative_controls: group(blind),
      by_spawn: byKey('spawn'), by_agent_type: byKey('agent_type'), by_spawn_and_agent_type: bySpawnAndType, by_session: byKey('session_ordinal'),
    },
    limits: LANES_LIMITS,
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
  if (!requested) issues.push('model not requested explicitly (inherits the coordinator model)')
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
    const child = summarizeChild(s, results.get(s.agentId) || null, meta, found ? lines(logPath) : [], found, lanesOptions)
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
  '       child-usage.mjs --lanes-sweep --root <dir> [--root <dir> ...] [--since <ISO>] [--until <ISO>] [--rtk-db <history.db>] [--marker <text>]'
// { error } or the parsed options. An option value may not start with "--"; each option but --root is given once.
export function parseArgs(argv) {
  const o = { positional: [], roots: [], sweep: false }
  const valued = { '--require-effort': 'required', '--rtk-db': 'rtkDb', '--marker': 'marker', '--since': 'since', '--until': 'until' }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--root' || Object.hasOwn(valued, a)) {
      const v = argv[i + 1]
      if (v === undefined || v.startsWith('--')) return { error: a === '--require-effort' ? '--require-effort needs one of ' + EFFORTS.join(', ') : a + ' needs a value' }
      if (a === '--root') o.roots.push(v)
      else if (o[valued[a]] !== undefined) return { error: a + ' may be given once' }
      else o[valued[a]] = v
      i++
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
  // Output goes out through stdout.write and process.exitCode, never process.exit(): process.exit() drops stdout
  // writes still pending, and a pipe takes 64 KiB at once. Only the short error messages above exit directly.
  if (o.sweep) {
    const notDirs = o.roots.filter((r) => { try { return !statSync(r).isDirectory() } catch { return true } })
    if (notDirs.length) { console.error('--root is not a readable directory: ' + notDirs.join(', ')); process.exit(2) }
    process.stdout.write(sortedJson(sweepLanes(o.roots, { since: o.since === undefined ? null : Date.parse(o.since), until: o.until === undefined ? null : Date.parse(o.until), marker, rtk })) + '\n')
    process.exitCode = 0
  } else {
    const target = o.positional[0]
    const required = o.required ?? null
    const dir = target === '--latest' ? latestRunDir(process.cwd(), process.env.CLAUDE_CONFIG_DIR || join(homedir(), '.claude')) : target
    if (target === '--latest' && !dir) { console.error('no native Workflow run found for ' + process.cwd()); process.exit(2) }
    const out = { transcript_dir: dir, ...summarizeRun(dir, { marker, rtkDecisions: rtk ? rtk.map : null }) }
    if (rtk) out.rtk_db = { joined: true, rows: rtk.rows, duplicate_tool_use_ids: rtk.duplicates }
    if (required) out.effort_mismatches = effortMismatches(out, required)
    process.stdout.write(JSON.stringify(out, null, 2) + '\n')
    process.exitCode = out.status === 'complete' && !(required && out.effort_mismatches.length) ? 0 : 1
  }
}
