// Seeded token-soup shell inputs and their bash -n validity, for the command-position differential.
//
//   node make-inputs.mjs <profile> <seed> <count> <out-dir> [--jobs N]
//
// Profiles (a profile is a token vocabulary; each input concatenates 1..24 tokens drawn with a mulberry32 generator):
//   soup     the vocabulary of the first U1 differential (fetch tools, quotes, separators, substitutions, shell strings), no `<<` anywhere;
//            seed 432 with 40000 inputs is that differential's corpus exactly.
//   heredoc  soup plus here-document and here-string tokens (`<<EOF`, `<<'EOF'`, `<<-EOF`, `<<"E"`, a delimiter line, `<<<`).
//   lanes    the shell structure of soup plus lane executables, wrappers, mcporter calls and `rtk proxy`, so the lanes a text runs are nonempty.
// Validity is `bash -n -c <text>` (GNU bash reads the text and runs nothing); only valid inputs are analysed, since a text bash rejects
// runs nothing and no reading of it is claimed.
import { writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'

// The first differential's vocabulary, in its order and multiplicities (a repeated token is drawn more often), so seed 432 reproduces its corpus.
const SOUP = ["curl", "wget", " https://example.org", " http://127.0.0.1:9/", "echo", "git commit -m ", "gh api repos/x/y", "x", "a", "cat", "rtk proxy ", "python3 -c ", "node -e ", "requests.get(u)", "fetch(u)", "do ", "then ", "if ", "timeout 5 ", "x=", "bash -c ", "sh -c ", "sh -lc ", "ssh host ", "eval ", " ", " ", " ", ";", "&&", "||", "|", "&", "\n", "(", ")", "$(", "$((", "))", "`", "{", "}", ">", "2>&1", "<", "#", "'", "'", "\"", "\"", "\"", "\\", "\\\"", "\\$", "\\`", "\\\n", "\\\\", "\"$(", "$(curl ", ")\"", "\"`", "`\""]
const HEREDOC = ['<<EOF', "<<'EOF'", '<<-EOF', '<<"EOF"', '\nEOF\n', '\nEOF', '\n\tEOF\n', '<<<', 'bash <<EOF\n', "bash <<'EOF'\n", 'cat <<EOF\n', 'sh <<-EOF\n', ...SOUP]
const STRUCTURE = SOUP.slice(SOUP.indexOf(' '), SOUP.indexOf('$(curl '))
const LANES = ['qmd ', 'toon ', 'repomix ', 'markitdown ', 'rtk proxy ', 'mcporter call serena.x ', 'mcporter list ', 'nohup ', 'nice -n 5 ', 'env A=1 ', 'env -u X ',
  'timeout 5 ', 'xargs ', 'command ', 'exec ', 'time ', '! ', 'bash -c ', 'sh -c ', 'eval ', 'ssh host ', '--help ', '--version ', 'proxy ', 'x=(', 'declare -a a=(',
  '<<EOF\n', "<<'EOF'\n", '\nEOF\n', 'bash <<EOF\n', ...STRUCTURE]
const PROFILES = { soup: SOUP, heredoc: HEREDOC, lanes: LANES }

const rng = (seed) => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296 }
// The token sequences of the inputs, in order (the input is their concatenation): a reduction removes tokens, not characters.
export function sequences(profile, seed, count) {
  const tokens = PROFILES[profile]
  if (!tokens) throw new Error('unknown profile ' + profile)
  const rand = rng(seed), out = []
  while (out.length < count) {
    const parts = []
    for (let k = 1 + Math.floor(rand() * 24); k > 0; k--) parts.push(tokens[Math.floor(rand() * tokens.length)])
    if (profile === 'soup' && parts.join('').includes('<<')) continue
    out.push(parts)
  }
  return out
}
export const inputs = (profile, seed, count) => sequences(profile, seed, count).map((parts) => parts.join(''))
export const bashValid = (text) => spawnSync('bash', ['-n', '-c', text], { stdio: 'ignore' }).status === 0

if (import.meta.url === new URL(process.argv[1], 'file://' + process.cwd() + '/').href) {
  const [profile, seed, count, dir] = process.argv.slice(2)
  const list = inputs(profile, Number(seed), Number(count))
  const valid = list.map(bashValid)
  const name = `${profile}-${seed}`
  writeFileSync(join(dir, name + '-inputs.json'), JSON.stringify(list))
  writeFileSync(join(dir, name + '-valid.json'), JSON.stringify(valid))
  console.log(JSON.stringify({ profile, seed: Number(seed), inputs: list.length, bash_valid: valid.filter(Boolean).length }))
}
