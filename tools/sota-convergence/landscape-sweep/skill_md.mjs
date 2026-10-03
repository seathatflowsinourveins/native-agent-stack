#!/usr/bin/env node
// Whether the pinned skills CLI takes a SKILL.md, decided by the CLI's own code and parser: the functions of
// vercel-labs/skills v1.7.0 (tag commit 7407f3893ad4dceab546ac002c3ef806e4000c73) that decide it, ported line by line
// below, run with the yaml package that skills-yaml.pin.json pins (source_reviews.py calls this for every SKILL.md copy
// it reads; landscape sweep, skills modality).
//
//   node skill_md.mjs [--install <dir>] < request.json > response.json
//
// request:  {"items": [{"id": <string>, "path": <the SKILL.md's path in the repository>, "base64": <its bytes>}]}
// response: {"reader": {"ok": true, "package", "integrity", "pin_sha256"} or {"ok": false, "reason"}, "results": [...]},
//           one result per item: {id, verdict, name, description, display_name, reason, license,
//           disable_model_invocation}.
// verdict "take": parseSkillMd returns the skill (name and description as sanitizeMetadata records them, display_name as
// getSkillDisplayName gives it, license and disable-model-invocation as the yaml package types them when a string, a
// number, a boolean or null). "skip": parseSkillMd returns null, and reason is the warning the CLI prints. "error": no
// verdict is given, and reason says why: a line break other than LF or CRLF in the frontmatter (below), or an exception
// of this script's own. The caller treats that copy as unverified.
//
// The yaml install is not vendored: skills-yaml.pin.json names the package with its npm integrity, the sha256 of every
// file that runs, and the install command. Each pinned file is read once and checked against its sha256, the install's
// package-lock.json must record the pinned version and integrity, and only those verified bytes run (they are written to
// a private directory and required from there, so a file the pin does not list cannot load). Without a verified install
// nothing is parsed: reader is {"ok": false, "reason": not_installed | hash_mismatch | load_error}, results is empty and
// the exit status is 3. Directory order: --install, then LANDSCAPE_SWEEP_SKILLS_YAML, then the pin's default directory
// under HOME. Nothing is installed or fetched at run time.

import { createHash } from 'node:crypto'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir, tmpdir } from 'node:os'
import { dirname, join, posix } from 'node:path'

const ENV_NAME = 'LANDSCAPE_SWEEP_SKILLS_YAML'
const sha256Hex = (bytes) => createHash('sha256').update(bytes).digest('hex')
const missingFile = (e) => e && (e.code === 'ENOENT' || e.code === 'ENOTDIR')
let parseYaml = null // the pinned yaml package's parse, once verified

function readPin() {
  try {
    const bytes = readFileSync(new URL('./skills-yaml.pin.json', import.meta.url))
    const pin = JSON.parse(bytes.toString('utf8'))
    const ok = pin && typeof pin === 'object' && typeof pin.package?.name === 'string'
      && typeof pin.package.version === 'string' && typeof pin.package.integrity === 'string'
      && pin.files && typeof pin.files === 'object' && typeof pin.entry === 'string' && pin.entry in pin.files
      && Object.values(pin.files).every((file) => /^[0-9a-f]{64}$/.test(file?.sha256 ?? ''))
      && typeof pin.install?.default_directory === 'string'
    return ok ? { pin, sha256: sha256Hex(bytes) } : null
  } catch { return null }
}

function loadYaml(dir) {
  const read = readPin()
  if (!read) return { ok: false, reason: 'load_error' }
  const { pin } = read
  const root = dir || process.env[ENV_NAME] || join(homedir(), pin.install.default_directory)
  const bytes = {}
  let lock
  try {
    for (const rel of Object.keys(pin.files)) bytes[rel] = readFileSync(join(root, rel))
    lock = readFileSync(join(root, pin.install.lockfile || 'package-lock.json'))
  } catch (e) { return { ok: false, reason: missingFile(e) ? 'not_installed' : 'load_error' } }
  if (Object.entries(pin.files).some(([rel, want]) => sha256Hex(bytes[rel]) !== want.sha256)) return { ok: false, reason: 'hash_mismatch' }
  let entry
  try { entry = JSON.parse(lock.toString('utf8')).packages?.['node_modules/' + pin.package.name] } catch { return { ok: false, reason: 'hash_mismatch' } }
  if (!entry || entry.version !== pin.package.version || entry.integrity !== pin.package.integrity) return { ok: false, reason: 'hash_mismatch' }
  const scratch = mkdtempSync(join(tmpdir(), 'skills-yaml-'))
  process.on('exit', () => rmSync(scratch, { recursive: true, force: true }))
  for (const [rel, data] of Object.entries(bytes)) {
    mkdirSync(dirname(join(scratch, rel)), { recursive: true })
    writeFileSync(join(scratch, rel), data, { mode: 0o600 })
  }
  const yaml = createRequire(import.meta.url)(join(scratch, pin.entry))
  if (typeof yaml?.parse !== 'function') return { ok: false, reason: 'load_error' }
  return { ok: true, parse: yaml.parse,
    record: { package: `${pin.package.name}@${pin.package.version}`, integrity: pin.package.integrity, pin_sha256: read.sha256 } }
}

// ------------------------------------------------------------------ vercel-labs/skills v1.7.0, ported line by line
// src/sanitize.ts lines 18-36.
const CSI_RE = /\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]/g
const OSC_RE = /\x1b\][\s\S]*?(?:\x07|\x1b\\)/g
const DCS_PM_APC_RE = /\x1b[P^_][\s\S]*?(?:\x1b\\)/g
const SIMPLE_ESC_RE = /\x1b[\x20-\x7e]/g
const C1_RE = /[\x80-\x9f]/g
const CONTROL_RE = /[\x00-\x06\x07\x08\x0b\x0c\x0d-\x1a\x1c-\x1f\x7f]/g

// src/sanitize.ts lines 44-52.
function stripTerminalEscapes(str) {
  return str
    .replace(OSC_RE, '') // OSC first (longest match)
    .replace(DCS_PM_APC_RE, '') // DCS/PM/APC
    .replace(CSI_RE, '') // CSI sequences
    .replace(SIMPLE_ESC_RE, '') // Simple ESC+char
    .replace(C1_RE, '') // C1 control codes
    .replace(CONTROL_RE, '') // Raw control chars (keep \t \n)
}

// src/sanitize.ts lines 61-65.
function sanitizeMetadata(str) {
  return stripTerminalEscapes(str)
    .replace(/[\r\n]+/g, ' ')
    .trim()
}

// src/frontmatter.ts lines 8-16.
function parseFrontmatter(raw) {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!match) return { data: {}, content: raw }
  const data = parseYaml(match[1]) ?? {}
  return { data, content: match[2] ?? '' }
}

// src/skills.ts lines 53-55.
function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

// src/skills.ts lines 61-64.
function shouldInstallInternalSkills() {
  const envValue = process.env.INSTALL_INTERNAL_SKILLS
  return envValue === '1' || envValue === 'true'
}

// src/skills.ts lines 80-133. The file's bytes stand for readFile(skillMdPath, 'utf-8'), which decodes them with the same
// Buffer#toString; warnSkippedSkill (lines 76-78) prints stripTerminalEscapes(reason), which is returned as the reason.
function parseSkillMd(bytes, skillMdPath, options) {
  const content = bytes.toString('utf-8')

  let data
  try {
    ({ data } = parseFrontmatter(content))
  } catch (err) {
    return { skill: null, reason: stripTerminalEscapes(`YAML parse error: ${err.message}`) }
  }

  if (!data.name || !data.description) {
    const missing = []
    if (!data.name) missing.push('name')
    if (!data.description) missing.push('description')
    return { skill: null, reason: stripTerminalEscapes(`missing required frontmatter field(s): ${missing.join(', ')}`) }
  }

  // Ensure name and description are strings (YAML can parse numbers, booleans, etc.)
  if (typeof data.name !== 'string' || typeof data.description !== 'string') {
    return { skill: null, reason: stripTerminalEscapes(
      `frontmatter "name" and "description" must be strings (got ${typeof data.name} and ${typeof data.description})`) }
  }

  const metadata = isRecord(data.metadata) ? data.metadata : undefined
  const isInternal = metadata?.internal === true
  if (isInternal && !shouldInstallInternalSkills() && !options?.includeInternal) {
    return { skill: null, reason: 'an internal skill (metadata.internal: true), which the CLI skips without a warning' }
  }

  return {
    skill: { name: sanitizeMetadata(data.name), description: sanitizeMetadata(data.description), path: posix.dirname(skillMdPath), metadata },
    data,
  }
}

// src/skills.ts lines 331-333. For a root SKILL.md the CLI's skill.path is its clone directory, whose name no review can
// know, so an empty name there gives no display name (null).
function getSkillDisplayName(skill) {
  return skill.name || posix.basename(skill.path)
}

// ------------------------------------------------------------------ this reader's own limit
// The yaml package breaks lines only at LF and CRLF (a lone CR is content: eemeli/yaml src/parse/lexer.ts), and so does the
// CLI's frontmatter pattern, while libyaml, which Codex's serde_yaml parses with, also breaks them at a lone CR, U+0085,
// U+2028 and U+2029 (unsafe-libyaml 0.2.11 src/macros.rs IS_BREAK_AT). With one of those in the frontmatter the clients
// that load the installed skill read another frontmatter than the CLI, so this reader gives no verdict for the copy. The
// frontmatter is what the CLI's pattern takes up to the body, or, when the pattern does not match a file that starts with
// ---, the whole file (another reader may find a frontmatter there that the CLI does not).
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/
const [NEL, LS, PS] = [0x85, 0x2028, 0x2029].map((code) => String.fromCharCode(code))
const OTHER_BREAK = new RegExp(`\\r(?!\\n)|[${NEL}${LS}${PS}]`)
const BREAK_NAMES = { '\r': 'a CR without LF', [NEL]: 'U+0085', [LS]: 'U+2028', [PS]: 'U+2029' }

function otherBreak(content) {
  const match = content.match(FRONTMATTER)
  const region = match ? content.slice(0, content.length - match[2].length) : content.startsWith('---') ? content : ''
  const found = OTHER_BREAK.exec(region)
  if (!found) return null
  const line = region.slice(0, found.index).split(/\r?\n/).length
  return `frontmatter line ${line}: ${BREAK_NAMES[found[0]]}, a line break to libyaml (Codex's serde_yaml) but not to the `
    + 'yaml package or the CLI\'s frontmatter pattern, so the clients that load the skill read another frontmatter than the CLI'
}

const primitive = (value) => value === null || ['string', 'number', 'boolean'].includes(typeof value) ? value : null

function readOne(item) {
  const bytes = Buffer.from(item.base64, 'base64')
  const out = { id: item.id, verdict: 'error', name: null, description: null, display_name: null, reason: null, license: null,
    disable_model_invocation: null }
  try {
    const parsed = parseSkillMd(bytes, item.path, { includeInternal: true }) // add --skill <name> (src/add.ts lines 1330-1338)
    const other = otherBreak(bytes.toString('utf-8'))
    if (other) {
      out.reason = `${other} (the CLI alone ${parsed.skill ? 'takes it' : `skips it: ${parsed.reason}`})`
      return out
    }
    if (!parsed.skill) return { ...out, verdict: 'skip', reason: parsed.reason }
    const root = parsed.skill.path === '.'
    return { ...out, verdict: 'take', name: parsed.skill.name, description: parsed.skill.description,
      display_name: root && !parsed.skill.name ? null : getSkillDisplayName(parsed.skill),
      license: primitive(parsed.data.license), disable_model_invocation: primitive(parsed.data['disable-model-invocation']) }
  } catch (err) {
    out.reason = `this reader failed: ${String(err && err.message || err).split('\n')[0]}`
    return out
  }
}

function main() {
  const args = process.argv.slice(2)
  let install = null
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--install' && i + 1 < args.length) install = args[++i]
    else {
      process.stderr.write('usage: node skill_md.mjs [--install <dir>] < request.json\n')
      return 2
    }
  }
  let items
  try {
    items = JSON.parse(readFileSync(0).toString('utf8')).items
    if (!Array.isArray(items) || !items.every((item) => item && ['id', 'path', 'base64'].every((key) => typeof item[key] === 'string'))) {
      throw new Error('items')
    }
  } catch {
    process.stderr.write('skill_md.mjs: the request must be {"items": [{"id", "path", "base64"}, ...]} (strings)\n')
    return 2
  }
  let loaded
  try { loaded = loadYaml(install) } catch { loaded = { ok: false, reason: 'load_error' } }
  if (!loaded.ok) {
    process.stdout.write(JSON.stringify({ reader: { ok: false, reason: loaded.reason }, results: [] }) + '\n')
    return 3
  }
  parseYaml = loaded.parse
  process.stdout.write(JSON.stringify({ reader: { ok: true, ...loaded.record }, results: items.map(readOne) }) + '\n')
  return 0
}

process.exitCode = main()
