// The oracle: the skills CLI's own code. Slices parseSkillMd and the functions it calls, byte for byte, out of an
// installed skills@1.7.0 dist/cli.mjs (checked against the sha256 below, the file of the registry tarball whose sha512 is
// the registry's dist.integrity), writes them as a module into <module dir> so that its `import { parse } from "yaml"`
// resolves the yaml that directory's node_modules holds, and runs parseSkillMd on every SKILL.md of the corpus written
// to a scratch folder, capturing the warning the CLI prints for a skipped copy.
//
//   node cli_oracle.mjs <skills package dir> <module dir> <corpus.json> <out.json>
//
// out.json: {"cli_mjs_sha256", "extract_sha256", "yaml_version", "results": {<key>: {verdict, name, description,
// display_name, reason}}}; a symlink entry of the corpus (no bytes) is left out.
import { createHash } from 'node:crypto'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const CLI_MJS_SHA256 = 'fde68534019765fb69510a0038ca7df2810a6ffed4c26fef9beabdcf6cc6701c'
// dist/cli.mjs line ranges (1-based, inclusive): the sanitize expressions and functions, parseFrontmatter, isRecord$1 and
// shouldInstallInternalSkills, warnSkippedSkill and parseSkillMd, getSkillDisplayName.
const RANGES = [[341, 352], [1017, 1027], [1231, 1237], [1245, 1283], [1384, 1386]]
const [packageDir, moduleDir, corpusPath, outPath] = process.argv.slice(2)
const sha256 = (data) => createHash('sha256').update(data).digest('hex')

const cli = readFileSync(join(packageDir, 'dist', 'cli.mjs'))
if (sha256(cli) !== CLI_MJS_SHA256) throw new Error('dist/cli.mjs is not the skills@1.7.0 file')
const lines = cli.toString('utf8').split('\n')
const extract = RANGES.map(([from, to]) => lines.slice(from - 1, to).join('\n')).join('\n')
for (const name of ['function stripTerminalEscapes(', 'function sanitizeMetadata(', 'function parseFrontmatter(',
  'function isRecord$1(', 'function shouldInstallInternalSkills(', 'function warnSkippedSkill(', 'async function parseSkillMd(',
  'function getSkillDisplayName(']) {
  if (!extract.includes(name)) throw new Error(`the extract lacks ${name}`)
}
const source = ['import { parse } from "yaml";', 'import { readFile } from "node:fs/promises";',
  'import { basename, dirname } from "node:path";', extract, 'export { parseSkillMd, getSkillDisplayName };', ''].join('\n')
const modulePath = join(moduleDir, 'cli-oracle-extract.mjs')
writeFileSync(modulePath, source)
const { parseSkillMd, getSkillDisplayName } = await import(pathToFileURL(modulePath).href)
const yamlVersion = JSON.parse(readFileSync(join(moduleDir, 'node_modules', 'yaml', 'package.json'), 'utf8')).version

const corpus = JSON.parse(readFileSync(corpusPath, 'utf8'))
const scratch = mkdtempSync(join(tmpdir(), 'cli-oracle-'))
const results = {}
const warnings = []
const warn = console.warn
console.warn = (message) => warnings.push(String(message))
try {
  let index = 0
  for (const [key, entry] of Object.entries(corpus)) {
    if (!entry.base64) continue
    // The folder is named as in the repository (an edge case stands at skills/find-bugs, as compare.py places it).
    const path = key.startsWith('edge:') ? 'skills/find-bugs/SKILL.md' : key.slice(key.indexOf(':') + 1)
    const folder = join(scratch, String(index++), path.split('/').slice(-2, -1)[0] || 'root')
    mkdirSync(folder, { recursive: true })
    const file = join(folder, 'SKILL.md')
    writeFileSync(file, Buffer.from(entry.base64, 'base64'))
    warnings.length = 0
    const skill = await parseSkillMd(file, { includeInternal: true })
    if (skill) {
      results[key] = { verdict: 'take', name: skill.name, description: skill.description, display_name: getSkillDisplayName(skill), reason: null }
    } else {
      const printed = warnings.join('\n')
      const cut = printed.indexOf(' — ')
      results[key] = { verdict: 'skip', name: null, description: null, display_name: null,
        reason: cut >= 0 ? printed.slice(cut + 3) : printed || 'skipped without a warning' }
    }
  }
} finally {
  console.warn = warn
  rmSync(scratch, { recursive: true, force: true })
}
writeFileSync(outPath, JSON.stringify({ cli_mjs_sha256: CLI_MJS_SHA256, extract_sha256: sha256(extract), yaml_version: yamlVersion,
  results }, null, 1) + '\n')
console.log(`cli oracle: yaml ${yamlVersion}, ${Object.keys(results).length} SKILL.md, extract sha256 ${sha256(extract)}`)
