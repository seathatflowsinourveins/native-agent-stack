# Currency sweep of 2026-10-17: the plan rows follow the versions the host runs

The A2 stage-1 audit (G3-01, G3-05, G3-09 to G3-12) listed stale tools on the NativeHorizonNY host. This record re-pins seven rows of the new-WSL plan to the versions the host runs after that list
was worked, moves the claude-hud marketplace tag to the newest release, v0.11.3 (the host itself runs v0.11.2 until the command center applies it), and keeps what was verified, switched, left and
found. It applies [the zero-tolerance record](2026-10-17-zero-tolerance-currency.md): a stale pick starts replacement at once, and only an upstream's own documented cooldown window still applies
(`:27`, `:52-57`). No age buffer of ours applied, and the one the SocratiCode row carried, an install command with `--before=` set 24 hours ahead of the install, is dropped; the exact command without it was run in a scratch prefix and resolves the same 188 package versions as the `--before` command, with `npm audit signatures` clean on both (the receipt's `no_buffer_command_scratch_run` block; the host's install and the receipt's first audit ran the `--before` command). For each upstream the
release notes and README were read for such a window, and its SECURITY file where it has one (Serena and semble have none); none documents one for consumers (the two hits are
vulnerability-disclosure embargoes).

The private receipts are kept on the host; their public copies, with the account, home paths and private locators replaced by placeholders and with only digests of public bytes, are in
[`evidence/artifacts/currency-sweep-20261017/`](../../evidence/artifacts/currency-sweep-20261017/). The fold that answered the review of this change added to the public receipt of each re-pinned tool a `digest_comparison` and a `source_commit_resolution` block, taken from a
new private addendum, and added the receipts of the claude-hud v0.11.3 route, the Headroom recheck and the codebase-memory-mcp measurement. A second fold answered the review of that fold (F1 to F12): the RTK receipt's private script and log names are placeholders, the SocratiCode no-buffer command was run in scratch, the claude-hud route record gained its settings-edit step and a reproduced cause for the failed marketplace update, and the carriers and wording named below were corrected or listed as left.

## What moved

| Row | Plan pin before | Plan pin now | Release (UTC) | Pinned artifact | Switched on the host |
| --- | --- | --- | --- | --- | --- |
| RTK | 0.51.0 | **1.0.1, the rtk-oss edition** | 2026-10-14T13:31:42Z | `rtk-oss-x86_64-unknown-linux-musl.tar.gz` sha256 `a44e8ffc43981100b4ddf1710399a1649a6c874591aa6d0c0727fe6cbd983c41` | 2026-10-17T04:21:11Z by the lane builder, on the command center's go (tracker lines 847-848 and the lane builder's receipt sections G6 and G6b, both private and cited in the record's `switch_record`); [record](../../evidence/artifacts/currency-sweep-20261017/currency-rtk-20261017T081134Z.json) |
| Serena | `c6fbd1c5` (2.0.0.dev0 source) | **2.0.0** (PyPI) | 2026-10-13T12:25:45Z | `serena_agent-2.0.0-py3-none-any.whl` sha256 `910e1df8cf634e58997afb5f4ada0062a8f7be8339526afed4f5fb2f609162be` | 2026-10-17T00:02Z-00:05Z by the lane builder; [record](../../evidence/artifacts/currency-sweep-20261017/currency-serena-20261017T081640Z.json) |
| Chrome DevTools MCP | 1.10.1 | **1.11.0** | 2026-10-15T14:01:41Z | `chrome-devtools-mcp-1.11.0.tgz` sha256 `e9f0ab97ad9515927c7d9f0a3dfbdb9ea485d2810d572e4a64eb84b192c8bf0c` | 2026-10-17T00:33Z-00:35Z (both client args) by the lane builder; [record](../../evidence/artifacts/currency-sweep-20261017/currency-chrome-devtools-mcp-20261017T083216Z.json) |
| jcodemunch-mcp | 1.108.327 | **1.108.374** | 2026-10-17T04:34:14Z | tag commit `de0a67e5cf63c49930b79777ba2c314d58060e77` (the row keeps its source-identity form); wheel sha256 `e36752c27a7db86bb3b511e1f96b711f78a316ef487b3a07b47578731df04cae` and sdist sha256 `f4b9ad75f700e05b4429a29902d4aef6cbcbd286e15aab560f88c63a2dd789cb` are in the receipt | 2026-10-17T08:25:55Z by this sweep, side by side; [record](../../evidence/artifacts/currency-sweep-20261017/currency-jcodemunch-mcp-20261017T082641Z.json) |
| promptfoo | 0.123.1 | **0.124.1** | npm 2026-10-08T14:48:50Z | `promptfoo-0.124.1.tgz` sha256 `be3fe4dd4cd78e61a2fc81a8bcaaad1c8f29b63ebed16f08e629a5856f0c270f` | 2026-10-17T00:10Z-00:12Z by the lane builder; [record](../../evidence/artifacts/currency-sweep-20261017/currency-promptfoo-20261017T083212Z.json) |
| SocratiCode | 1.15.0 | **1.16.1** (install command without the `--before=` buffer) | npm 2026-10-15T22:23:41Z | `socraticode-1.16.1.tgz` sha256 `870dd285999984e217b5144b6a3abfae0499f1a618d751eb47f0c47d2a16ba24` | 2026-10-17T02:44Z-02:48Z by the lane builder; [record](../../evidence/artifacts/currency-sweep-20261017/currency-socraticode-20261017T083215Z.json) |
| semble | 0.6.1 | **0.7.0** | PyPI 2026-10-16T12:16:18Z | `semble-0.7.0-py3-none-any.whl` sha256 `06c568d5a06f3a5352f22357d5a7ab17525d4404fddde8f1ae1405e3e87ac4a7` | 2026-10-17T08:28:04Z by this sweep, side by side; [record](../../evidence/artifacts/currency-sweep-20261017/currency-semble-20261017T082840Z.json) |
| claude-hud marketplace tag | v0.10.0 | **v0.11.3** (a lightweight tag, commit `5621429b84ea2503185221244c43a06797bfd05e`) | 2026-10-17T00:42:18Z | tagged marketplace add | not yet: the host runs v0.11.2 (the command center's update of 2026-10-17T07:28:49Z, [record](../../evidence/artifacts/currency-sweep-20261017/claude-hud-0.11.2-20261017T072723Z.json)); the route to v0.11.3 ran in an isolated config directory, [record](../../evidence/artifacts/currency-sweep-20261017/claude-hud-0.11.3-20261017T144817Z.json) |

The files changed are `adoption/new-wsl-profile.json` (with its generated handbook and the handbook receipt, whose hashes follow the regenerated files), `adoption/new-wsl-profile.md`,
`adoption/new-wsl/client-config-map.json` (its promptfoo, RTK and claude-hud entries; the Chrome DevTools MCP and SocratiCode entries stay, see below), the prose of the two
`adoption/new-wsl/templates/` additions (the versions of semble and promptfoo; their `chrome-devtools-mcp` arguments stay), `adoption/templates/claude.settings.template.json`,
`adoption/bootstrap.md`, `recipes/README.md` (the claude-hud row that bootstrap's reviewed dict is checked against), `docs/community-native-practice.md`, the claude-hud sentence of
`adoption/pins-linux-x86_64.json` and `adoption/pins-macos-arm64.json`, plus the tests that hard-code these pins.

## How each was verified

Release facts are tool reads at the upstream (GitHub releases API, PyPI JSON, the npm registry), not memory. What was compared with what depends on what the registry publishes, and each public
receipt records both sides in its `digest_comparison` block (read again for the fold, with the exact bytes downloaded again):

- **PyPI files** (Serena, jcodemunch-mcp, semble): PyPI publishes a sha256 for every file. Each file of the release, wheel and sdist, was downloaded and its sha256 computed locally; each equals PyPI's
  published sha256. Where a profile row pins a sha256 it is the wheel's and equals the local one. The jcodemunch-mcp row records only the tag commit (source-identity form); the wheel and sdist digests
  above and in its receipt are what its install was compared with, and the row cites the receipt.
- **npm tarballs** (Chrome DevTools MCP, promptfoo, SocratiCode): npm publishes a sha512 SRI string and a sha1 for each version and no sha256. The tarball was downloaded and its sha512 and sha1 computed
  locally; both equal the published values. The sha256 in the profile row is computed locally over the same bytes; it has no registry counterpart. The three rows now carry the registry's sha512 beside it.
- **GitHub release asset** (RTK): the asset's API digest and the `checksums.txt` line for it were read; the asset was downloaded and its sha256 computed locally; all three are equal, and equal to the row's.

The installed copy of each was then compared with the artifact (PyPI: the wheel's RECORD hashes against the installed files, all matching; npm: the packed tarball's files against the installed package, all
matching). Provenance published by the upstream was verified with the ecosystem's own verifier: `pypi-attestations` 0.0.30 for the PyPI files of semble, jcodemunch-mcp (1.108.367 and 1.108.374) and
headroom-ai (attestations pass for wheel and sdist), `npm audit signatures` for chrome-devtools-mcp 1.11.0 (registry signature and attestation), promptfoo 0.124.1 (612 registry
signatures, 152 attestations over the installed tree) and SocratiCode 1.16.1 (188 registry signatures, 19 attestations; the package
itself publishes none). serena-agent 2.0.0 and rtk publish no attestation (PyPI integrity API 404; no GitHub attestation), so checksums and the byte comparison are their provenance. Each server answered the
MCP handshake (`initialize`, `notifications/initialized`, `tools/list`) with the clients' own arguments in an isolated HOME; tool names were compared with the previous version's, and no tool was renamed or
removed.

## Source commits

The source commits the rows cite were resolved by `git ls-remote https://github.com/<repo>.git refs/tags/<tag> refs/tags/<tag>^{}` (an annotated tag lists its object and, peeled, its commit; a
lightweight tag lists only the commit, which is then the commit the release was cut from) and, for npm packages, by the version document's `gitHead` and the GitHub compare API where it differs from the tag commit. Each
public receipt holds the lines in its `source_commit_resolution` block.

| Upstream | Tag | Tag kind | Commit | npm `gitHead` |
| --- | --- | --- | --- | --- |
| rtk-ai/rtk | `v1.0.1` | lightweight | `4ef8730cf3a0dea11c8d64a9b90bc0616fe52100` | not applicable (no npm document) |
| oraios/serena | `v2.0.0` | lightweight | `4c4268f9c0adf8743a75e6dda2ef1fa635f34cc3` | not applicable (no npm document) |
| ChromeDevTools/chrome-devtools-mcp | `chrome-devtools-mcp-v1.11.0` | lightweight | `a878bcad39584337e055778353246820deafa7c0` | `a878bcad`, equal to the tag commit |
| jgravelle/jcodemunch-mcp | `v1.108.374` | annotated (tag object `f76dae0d`) | `de0a67e5cf63c49930b79777ba2c314d58060e77` | not applicable (no npm document) |
| promptfoo/promptfoo | `0.124.1` | lightweight | `421e7959642c5d4cc1c983259a268de1c6f847b9` | none in the registry's version document |
| giancarloerra/SocratiCode | `v1.16.1` | annotated (tag object `152db329`) | `eb94e073cb8aa80d08fd56c8aecfe7f2fa065be8` | `520247be`, the parent of the tag commit (the compare lists 1 commit, `chore: release v1.16.1`: 10 files of versions, changelog and manifests; `README.md` is not among them) |
| MinishLab/semble | `v0.7.0` | lightweight | `8ee6463efbb1ff755c339e965c7298b7afd7db5b` | not applicable (no npm document) |
| jarrodwatts/claude-hud | `v0.11.3` | lightweight | `5621429b84ea2503185221244c43a06797bfd05e` | not applicable (a plugin repository) |

The README and source anchors of each row are read at those commits. SocratiCode's package was published from the parent of its tag commit; the two differ only in release bookkeeping, and the README the row cites is
the same at both.

## RTK 1.0.1: the three-way comparison

The plan row was at 0.51.0 while the host had moved to the rtk-oss edition (v1.0.0 split the default binary into an Apache-2.0 plus BUSL-1.1 edition and an Apache-2.0-only `rtk-oss` edition, README
`:127-:129` at v1.0.1; `rtk proxy` stays an alias of `rtk bypass`). The recorded hook cases were run against 0.51.0, 0.52.0 (the only 0.52.x release) and 1.0.1 under the same rtk config:

- the recorded hook acceptance ([`rtk-hook-acceptance-v3.1.sh`](../../evidence/artifacts/sota-refresh-20260925/rtk/rtk-hook-acceptance-v3.1.sh), run unchanged):
  87 pass, 1 fail and 3 notes in all three versions (the counts are identical, and no case changed status); the one failing case is the `git show <ref>:<path>` blob window,
  which the live exclusions correctly keep native in every version. One note's text differs: on 0.51.0 and 0.52.0 the hook wrote a one-line stderr warning (`No hook installed`, a pointer to `rtk init -g`) in 1 of 45
  payload calls, on 1.0.1 in 0 of 45 (`note_differences` in the receipt);
- the recorded exclusion checks ([`hook-check.txt`](../../evidence/artifacts/rtk-exclude-widen-20260926/hook-check.txt)) and the recorded behaviour probe
  ([`rtk_behaviour_probe.py`](../../evidence/artifacts/token-stack-fresh-session-e2e-20261004/rtk_behaviour_probe.py), whose 0.51.0 output this run reproduced exactly):
  identical in all three versions except one documented 0.52.0 feature, the rewrite of the inner command of quoted `sh`/`bash`/`zsh -c` wrappers;
- targeted cases for rtk PR #4129's three permission-gate holes and the wrapper-deny deferrals: 18 cases; the cases that differ from 0.51.0 are
  `G1-ansi-c-quote, G2b-redirect-second-segment-deny, G4b-redirect-second-segment-allow, G13-ansi-c-quote-deny, G3-brace-residue, G7-inner-rewrite-feature`, each a documented change (for the ANSI-C quote case 0.51.0 auto-allows while 0.52.0 and 1.0.1 defer); 0.52.0 and 1.0.1 are identical on every case. The case named for hole 2's leading
  redirect, `G2-leading-redirect`, shows no difference for its exact command (all three versions defer); the difference of hole 2 shows in `G2b` and `G4b`.

A history database written by 1.0.1 is read and appended by 0.51.0 and read back by 1.0.1, so the rollback (`ln -sfn` of `tools/rtk-0.51.0/rtk` onto `bin/rtk`) keeps the history.

## Left where it is, and why

- **codebase-memory-mcp** stays at 0.11.0. 0.12.1 is staged and verified (hashes agree four ways; `gh release verify` and `verify-asset` pass for the immutable release; smoke clean in isolation).
  Upstream's README at v0.12.1 `:155` requires every active CBM process to run the exact same version, build, coordination ABI and cache root, and a conflicting process fails at admission: switching
  `bin/codebase-memory-mcp` now makes every new Claude or Codex session's MCP server exit rc=1 against the live 0.11.0 daemon until the last 0.11.0 session closes. `:157-159` documents the exception:
  the native `install`, `update` and `uninstall` commands drain running sessions (a 15 s deadline, `restart_required`), and package-manager setups do not replace the active installation. That route does
  coordinate, and [the measurement](../../evidence/artifacts/currency-sweep-20261017/currency-codebase-memory-mcp-native-route-20261017T144817Z.json) (an isolated user, mount and PID namespace on copies of both binaries, a stand-in 0.11.0 session) shows what it does here: on this host's layout, where
  `bin/codebase-memory-mcp` is a symlink into `tools/codebase-memory-mcp-0.11.0/`, the install refuses at staging, before touching any session (`failed to stage install candidate: activation transaction I/O
  failed: target-entry-snapshot`; the transaction accepts only a regular file owned by the user, with one link and no group or world write, at the target: `src/cli/activation_transaction.c:1324-1340` at
  the tag); on a regular-file layout it drained the running session (exit 0 in about 2.8 s, `cohort drained`), activated 0.12.1 and appended the install directory to the user's `~/.profile`
  (also with the directory already on `PATH` and with `--skip-config`). Switching by that route here therefore means converting the active entry from a versioned link to a regular file, stopping every
  running CBM session of every agent, and editing a user shell profile. None of that is within a builder's remit (it may not stop processes it did not start or edit user configuration), so the
  switch stays with the command center, which has the verified command and its rollback in the receipt. That is a remit reading, not a failed condition: the native route's coordination condition (it drains running sessions) held on a regular-file layout. The older route needs no layout change: once no codebase-memory process runs, `ln -s` and `mv -T` relink `bin/codebase-memory-mcp` to `tools/codebase-memory-mcp-0.12.1/` ([the older receipt's `switch_when_ready`](../../evidence/artifacts/currency-sweep-20261017/currency-codebase-memory-mcp-20261017T080146Z.json)); only the native route needs the regular-file layout. Index format moves 1 to 2: each existing project index is rebuilt in full once at its next index; the old graph keeps answering until then. Live indexes: _config.db 0 MB, native-agent-stack.db 1741 MB, us-equities-trading.db 476 MB.
- **Headroom** stays at 0.37.0 under the [W1b hold](2026-10-03-currency-wave-w1b.md), while the repository carries three pins: this row 0.37.0, `adoption/pins-linux-x86_64.json:319-320` and
  `manifests/stack.json:521-523` 0.40.0 (the 2026-10-08 drift refresh; what `bootstrap-linux.sh` installs) and the host 0.41.0. The hold's overturn condition names a release containing the #3828 fix; PR #3828
  (merged 2026-09-29T04:11:36Z) is an ancestor of v0.40.0 and v0.41.0 and not of v0.39.1, and it changes how pytest short-summary failures are kept, not how the omission notice is counted. The owed recheck
  (omitted-line counts, required facts, exact retrieval) was run for this change on 0.40.0 (a side-by-side scratch install) and on 0.41.0 (the host's) with the recorded harness ([receipt](../../evidence/artifacts/currency-sweep-20261017/currency-headroom-recheck-20261017T144817Z.json)):
  required facts, exact retrieval, hashes and the tool list pass on both, and the omission notice does not: it still reads `[593 lines omitted: 1 ERROR]` for 593 omitted rows none of which is an error, as in 0.39.0 (v0.41.0's
  `log_compressor.rs` counts levels over all input lines, `:1523-1529`, and prints them in the notice, `:1564-1569`). The hold's first overturn criterion is therefore unmet on both, so the host and the pins
  files run ahead of the hold's own condition; its second criterion, a measured log-input answer-quality comparison, was not run. Overturning the hold or holding the host and pins back is the command
  center's decision.
- **Install-plan carriers and the pins files.** `evidence/artifacts/new-wsl-install-plan-20261002/` (install.sh, accept.sh, install-plan.json, owners.json and its configs),
  `adoption/pins-linux-x86_64.json`, `adoption/pins-macos-arm64.json` (no macOS asset checksums were read) and the platform pages still carry the earlier versions, and each re-pinned
  row's blocking gaps say so. For SocratiCode that includes the age buffer the row's command drops: `install.sh` and `install-plan.json` of the plan install SocratiCode 1.15.0 with `--before=2026-09-24T12:00:00Z`, so a fresh install through the plan still uses the buffer, at the old version, until they are amended. Amend them in their own change, with the hash-bound receipts, before a fresh install uses this profile.
- **The client map's Chrome DevTools MCP owner strings and SocratiCode path entries, and the two client template additions** (`adoption/new-wsl/templates/`) stay at the plan's 1.10.1 and 1.15.0 in their
  arguments and paths. They were first re-pinned in this change and put back when the tests showed the coupling: the plan's own checker (`evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py`,
  `browser_contract`) requires the template arguments and the map's owner string to equal the plan row's (a re-pin there failed `tests.test_new_wsl_definitive_defaults`, and the render then dropped the
  `chrome-devtools` server, which failed tests of `tests.test_new_wsl_client_config` and `tests.test_mcp_template_drift`), and `tests/test_new_wsl_client_config.py` asserts the plan's SocratiCode prefix. A
  re-render at the live pins would also point a fresh install at a pin and a prefix the plan does not install. The repository's own rule for a live-versus-template version difference is an
  acknowledgement row ("versions stay with the version owner"; finding 7). The prose of the two additions that named semble 0.6.1 and promptfoo 0.123.1 and 0.124.0 now names the current versions.
- **Recipe rows.** `recipes/README.md` keeps its other rows (promptfoo, SocratiCode, serena, jcodemunch-mcp and the RTK archive procedure) at the pins `manifests/stack.json` records; only the claude-hud row moved,
  because bootstrap's reviewed dict is checked against it.
- **Where the docs now differ from the pins files.** `adoption/bootstrap.md`'s uv-tool block (Serena, jcodemunch-mcp) and its RTK hook note name the live versions, while
  `adoption/pins-linux-x86_64.json` (what `bootstrap-linux.sh` installs) and `recipes/README.md`'s jCodeMunch block keep the earlier pins until those carriers are amended in their own change.
- **The RTK awareness text.** `adoption/templates/codex.AGENTS.template.md:12-20` embeds upstream's `hooks/rtk-awareness.md` at v0.51.0 verbatim, and `adoption/new-wsl/codex-user-instructions.md` is its
  rendering (`tools/adoption/new_wsl_client_config.py`; the scaffold copy is bound byte for byte by `tests/test_scaffold_repo.py`). The file at v1.0.1 differs in one word, `proxy` for `bypass` (compared
  here at both tags); `rtk proxy` remains an alias of `rtk bypass` in 1.0.1, so the text stays accurate. The repository's own agent and skill text says `rtk proxy` as well (`adoption/agents/`,
  `.claude/agents/`, `.claude/skills/omniroute-runtime-worker/SKILL.md`) and the full-awareness variants embed v0.51.0's `rtk-awareness-full.md`; renaming them is one coordinated change of the rendered
  carriers, left to its own change.
- **The handbook's dated layer tables.** `docs/new-wsl-handbook.md` and `.json` are generated, and their slot-default tables (RTK 0.51.0, jcodemunch-mcp 1.108.327, promptfoo 0.123.1, semble 0.6.1,
  Chrome DevTools MCP 1.10.1, claude-hud 0.10.0) come from the dated definitive manifest of 2026-10-01 and the layer consensus of 2026-10-02 (`evidence/artifacts/new-wsl-definitive-defaults-20261001/`,
  `evidence/artifacts/new-wsl-layer-consensus-20261002/`); the tool rows of the same handbook follow the profile and carry the new pins.
- **SocratiCode 1.15.0 in the handbook.** `docs/new-wsl-handbook.json`'s dated layer table (and the handbook page's two mentions of SocratiCode 1.15.0) still say that 1.15.0 is installed with `--ignore-scripts --before=2026-09-24T12:00:00Z`; they come from the same dated layer tables as above, and the SocratiCode row of the same handbook carries 1.16.1 and no `--before`.
- **The jcodemunch-mcp row's two previous-pin references.** Its `evidence_refs` still list `manifests/stack.json` (`components[id=jcodemunch-mcp]`, version 1.108.327) and `evidence/receipts/jcodemunch-1108327-qualification-20261003.json`; both describe the previous pin 1.108.327, not 1.108.374. The row's blocking gap says that this row does not inherit that qualification, and the references stay because the catalog snapshot and the W1 receipt are the row's lineage; the evidence of 1.108.374 is the public receipt cited last.
- **Catalog snapshots** (`manifests/stack.json`, `docs/token-efficiency-stack.json`, `catalogs/`, dated decision records and evidence) are records of their own date and stay.

## Findings that need a decision

1. **RTK's Codex hook trust step refuses 1.0.1** until the exec rules are re-reviewed (or `--allow-exec-rules` is passed): `tools/adoption/codex_hook_trust.py` compares `rtk --version` with the version
   `tools/adoption/exec_rules_reviewed.json` was reviewed for (0.51.0), and the derive script's own header says a pin move must re-derive `rtk-rewrite-heads.json` and re-review that entry. Measured in the
   public RTK receipt: 0.52.0 and 1.0.1 rewrite `bash -c 'git status'` to the `rtk` form of the inner command; the receipt's rows for `bash -c 'git log --oneline -3'` and `env FOO=1 bash -c 'git log --oneline -3'` defer in every version under the deny-log configuration. Wrapper cases such as `sh -c`, and the non-rewrite of `hcom ...` and `uvx ...`, are
   not in any public receipt: they come from the lane builder's trial runs, which are private, and are unverified here. Also owed: `tools/adoption/runtime_profiles.py:562` (the pi and opencode profile build) requires `rtk 0.51.0` and its source commit and raises `RTK installer/source version mismatch` for the 1.0.1 pin; it is routed with this review, as its own change. The review is owed and is recorded as a blocking gap on the RTK row.
2. **Serena 2.0.0 defaults a fresh configuration to the REPL interface** (`agent_interface: REPL`, two or three tools); this host's `serena_config.yml` carries `agent_interface: tools` (21 tools in the
   claude-code context, 23 in codex, the same names as before). The plan seeds no `agent_interface` anywhere (`serena init` at `install.sh:432`), so a fresh install would expose only the REPL set unless
   the plan seeds `tools` or adopts the REPL deliberately; this is now the Serena row's blocking gap. The seeding is the plan owner's change (the install plan is a hash-bound carrier).
3. **codebase-memory-mcp 0.12.1**: the switch needs the command center's decision on the moment and the layout. The command, its prerequisites and its rollback are in the
   [measurement receipt](../../evidence/artifacts/currency-sweep-20261017/currency-codebase-memory-mcp-native-route-20261017T144817Z.json); the alternative needs no layout change: once the last 0.11.0 session closes (no codebase-memory process running), move the link as before with `ln -s` and `mv -T` (an index rebuilt by 0.12.1 may not be readable by 0.11.0).
4. **Headroom**: the host (0.41.0) and the pins files (0.40.0) run ahead of the W1b hold, whose first overturn criterion the recheck finds unmet; see above.
5. **claude-hud v0.11.3 is pinned in the plan, not yet on the host.** The host runs v0.11.2. The commands for the host are in the [route record](../../evidence/artifacts/currency-sweep-20261017/claude-hud-0.11.3-20261017T144817Z.json); they edit the user's
   `~/.claude/settings.json` declared pin and run the three tagged-route commands, which this change's builder does not do. `claude plugin marketplace update claude-hud` is not one of them: after the settings edit it fails with "Marketplace 'claude-hud' not found" (reproduced in a second isolated run; the receipt's `smoke.b0_cause_reproduction`).
6. **Python tool layout.** jcodemunch-mcp and semble were installed side by side (`tools/jcodemunch-mcp-1.108.374/`, `tools/semble-0.7.0/`, each a `uv tool` directory) and their entrypoints repointed,
   because live sessions import from the old venvs. The old directories' `uv-receipt.toml` files (`python-tools/jcodemunch-mcp`, `~/.local/share/uv/tools/semble`) still name the old versions and no longer
   describe what is live.
7. **semble's plan form differs from the host's.** The row keeps upstream's documented `uv tool install semble==0.7.0 && semble install` (README `:41`; `semble install` writes MCP entries that run
   `uvx --from semble[mcp]==X.Y.Z`, `docs/installation.md` at v0.7.0), while this host runs the installed tool's console script, whose uv receipt carries the `mcp` extra (`semble[mcp]==0.7.0`), behind a bare
   `semble` command in both clients. The pin and the host's version agree; the install form is a difference that existed at 0.6.1 and that this change does not settle.
8. **Drift acknowledgements owed.** `adoption/new-wsl/mcp-drift-acknowledged.json` records where a live client entry may differ from the templates. The templates keep the plan's pins, so two
   version differences are not yet said there. `chrome-devtools`: the templates name `chrome-devtools-mcp@1.10.1`; both live clients run `chrome-devtools-mcp@1.11.0` (the Claude Code row is missing;
   the Codex row lists only `enabled`, and should list `args` too). `socraticode`: the template and both live entries name a `dist/index.js` path, 1.15.0 against `tools/socraticode-1.16.1`;
   the two existing rows' reasons describe the entry of 2026-10-12 (1.16.0 through npx, with an auto-resume and a collection prefix), so which fields still differ needs a fresh drift run. Each row would
   cite `docs/decisions/2026-10-12-mcp-template-live-reconciliation.md#values-that-differ`. Not applied in this change.

## Alternatives considered

- Re-pin the client map's Chrome DevTools MCP and SocratiCode entries and the two client templates together with the profile rows: tried, and reverted after the tests failed on the plan coupling described above.
- Leave the plan rows at the audited pins: rejected, the plan would describe a host that no longer exists and a re-render would regress live pins (the claude-hud receipt's own follow-up says so).
- Move RTK to the 0.52.0 line only: rejected by the command center's ruling once the live link was found at 1.0.1; the comparison shows 0.52.0 and 1.0.1 identical on every hook case.
- Amend the install-plan evidence and the pins files in this change: rejected, they are hash-bound or platform-specific carriers that need their own review, and the profile rows say where they still lag.
- Re-pin Headroom now: rejected, the W1b hold's criterion is unmet on the recheck. Re-pin codebase-memory-mcp now: rejected for the reasons above (one build per account; the native route refuses this layout and
  stops every session).
- Keep the SocratiCode `--before=` buffer: rejected, it is an age buffer of ours, which the zero-tolerance record forbids; the row's command without it was run in scratch and resolves the same tree, audited clean (the receipt's `no_buffer_command_scratch_run`).
- Pin claude-hud at v0.11.2 and disclose v0.11.3: rejected by the review; v0.11.3 was published before the host's v0.11.2 move and no advisory names it.

## Inverse

Per tool, one command, each recorded in its private receipt and in the public copy: relink `bin/<tool>` to the previous `tools/<tool>-<version>` (RTK, promptfoo, jcodemunch-mcp's three entrypoints), re-point `~/.local/bin/semble`
at the 0.6.1 tool directory, reinstall the previous exact pin with `uv tool install` (Serena, Headroom), re-add the previous client argument (chrome-devtools-mcp, SocratiCode), or put the settings ref and the tagged
add back to v0.11.2 (claude-hud). The plan rows revert with this change.

## Overturn condition

A publisher digest or attestation mismatch for any pinned artifact; a reproducible regression on the documented recipe at the pinned version; or a better-evidenced successor that passes the same screen.
