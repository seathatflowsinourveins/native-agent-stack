# New-machine bootstrap (ordered)

One page, one order. Each step names the [manifest](manifest.json) `recipe_map`
entry or component it uses instead of repeating its command. Read
[the adoption reference](README.md) first for profile selection and the four
native verification tiers; this page only sequences the steps for a machine
that has never run this stack.

**Step 0, before anything below: get the catalog at its attested release tag.**
Read the pin and run the release check on the default branch, before the
checkout: the release's own `adoption/manifest.json` names the release before
it (a commit cannot contain its own hash), and the pinned tag may predate
`scripts/release_due.py` itself.
```sh
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git
cd native-agent-stack
python3 scripts/release_due.py   # on the default branch: steps main documents that the pinned release lacks
tag="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_tag'])")"
commit="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_commit'])")"
git checkout "$tag"
if test "$(git rev-parse HEAD)" = "$commit"; then echo "at $tag ($commit)"; else echo "error: $tag is not the pinned release commit $commit" >&2; false; fi
```
This checks out `adoption/manifest.json` `source.release_tag` (or a later tag)
and confirms it resolves to `source.release_commit` (read from the manifest you actually
cloned, never from a commit pasted into prose, which a later re-pin would leave
stale), published with SLSA build
provenance by `.github/workflows/publish-catalog.yml`. `scripts/release_due.py`
runs here, on the default branch, before the checkout. After checkout, follow
the documents in your checkout.

The pages here name the release a step was written against. "Added after
`vT`" means release `vT` lacks the file that step uses (a path in
`release_due.py`'s `due` list); "changed after `vT`" means the file exists at
`vT` but behaves as the note says there, not as main documents it (its
`changed` list names every new-machine file whose content differs from `vT`). If your
checkout is `vT`, follow the note: run that step from a separate clone of the
default branch (never the pinned one you install from; a result from it is
main-only evidence) or wait for the next re-pin. If your checkout is a later
release, the note is history and the step is in your checkout (`test -e
<path>` confirms). See
[moving a host to a new release](update.md#moving-a-host-to-a-new-release).

Do **not** check out
`source.baseline_commit`: that field records the parent publication
immediately *before* this `adoption/` directory (and `tools/adoption/`) were
added, so every step below it on this page would fail with a missing file
(Codex cross-family review finding, `codex-review-72`); `baseline_commit`
remains meaningful only as the comparison point `scripts/adoption_status.py`
uses for its `baseline_matches`/`baseline_differs` `git` result, not as a
checkout target.

If installing from the release archive instead of `git clone` (e.g. no local
git), download it from the GitHub Release and verify it before use. Both checks
bind the file to this release: `verify-asset` to the immutable release's asset
digest, and `--source-ref`/`--source-digest` to the tagged commit. Without them
the attestation check also passes for an attested archive of any other commit
(a `workflow_dispatch` run of `publish-catalog.yml`) saved under this name.
`verify-asset` and `attestation verify` need a signed-in `gh` (`gh auth login`;
without it both exit 4). Without a clone, read the pin from the default branch:
```sh
gh api -H 'Accept: application/vnd.github.raw+json' \
  repos/seathatflowsinourveins/native-agent-stack/contents/adoption/manifest.json \
  | python3 -c "import json,sys; s=json.load(sys.stdin)['source']; print(s['release_tag'], s['release_commit'])"
gh release download <release_tag> --repo seathatflowsinourveins/native-agent-stack \
  --pattern 'native-agent-stack-<release_commit>.tar.gz'
gh release verify-asset <release_tag> native-agent-stack-<release_commit>.tar.gz \
  --repo seathatflowsinourveins/native-agent-stack
gh attestation verify native-agent-stack-<release_commit>.tar.gz \
  --repo seathatflowsinourveins/native-agent-stack \
  --signer-workflow seathatflowsinourveins/native-agent-stack/.github/workflows/publish-catalog.yml \
  --source-ref refs/tags/<release_tag> --source-digest <release_commit>
```

Read the platform page for the chosen
[`platform_profiles`](manifest.json) entry before starting:
[Linux/WSL2 x86_64](platforms/linux-wsl2.md) (`status: accepted`) or
[macOS arm64](platforms/macos-arm64.md) (`status: drafted_not_accepted` —
nothing on that page has been executed on a Mac workstation, only on a
GitHub-hosted macOS runner; see
[the acceptance evidence policy](../docs/acceptance-evidence-policy.md)).

1. **Host prerequisites.** Confirm the OS/architecture matches a
   `platform_profiles` entry. Linux/WSL2 needs the packages listed in
   [`recipes/README.md`](../recipes/README.md#paths-pins-and-installation-conventions)
   (`git`, `python3`, `node`, `uv`, and the archive/checksum conventions used by
   every component recipe). macOS needs the Homebrew prerequisites on
   [the macOS page](platforms/macos-arm64.md#prerequisites); that page is
   drafted, not accepted.

2. **Run the platform bootstrap script.** `adoption/bootstrap-linux.sh --profile <id>
   [--skip-system-packages] [--allow-unpinned <id,id,...>]
   [--configure-claude-user-profile | --configure-full-profile --host <name> [--skip <step>]...]` on Linux/WSL2, or
   `adoption/bootstrap-macos.sh --profile <id> [--skip-system-packages]
   [--allow-unpinned <id,id,...>] [--plan] [--configure-claude-user-profile]`
   on macOS (`ECO_INSTALL_ROOT` env,
   default `$HOME/.local/share/codex-ecosystem`; writes
   `$ECO_INSTALL_ROOT/installed-versions.txt`; both scripts exit 2 usage,
   1 guard/refusal, 0 success, 3 when a selected component has no pin and was
   not named in `--allow-unpinned`, 4 when a prerequisite is still missing
   after the system-package step — with `--skip-system-packages` no
   `apt-get`/`brew install` is attempted and the check lists what is missing;
   `--plan` resolves the profile's pins with no network and still exits 1 on a
   null `sha256` — and 5 when a version probe fails) — installs the selected
   profile's components using each entry's `recipe_map` path. Inspect the
   script before running it on a new host; it installs only what the chosen
   `--profile` selects.

   `installed-versions.txt` checks each pin the run installed with the
   `version_probe` its pin entry declares: the declared command, run with
   stdin from `/dev/null` in its own process group and killed after 30 s (or the
   longer `timeout_seconds` its pin declares), must
   report the pinned version (Claude Code's pin is a floor, so any later
   version passes); `context-mode` and `socraticode` have no version flag and
   start their MCP stdio server on any other argument, so npm reads their
   package version instead (those probes run only `bin/npm`). Every other
   executable in `$ECO_INSTALL_ROOT/bin` is listed with its link target and
   not run. A probe that fails, times out or reports another version makes
   the script exit 5 once the report is written, before its closing
   next-steps message and `--configure-claude-user-profile`; nothing is
   removed. This report changed after `v2026.09.24.1`: at that release, and at
   every earlier one, both scripts run `--version` on every file in `$ECO_INSTALL_ROOT/bin` with the terminal's stdin and no
   bound, so they
   block on `context-mode` and `socraticode` (run them with `</dev/null` to
   avoid that) and on a recipe-installed `mcp-inspector`, which has no version
   flag and serves its web UI with `--version` as the server command; stop
   that process if the report stops after `-- mcp-inspector --`.

   The scripts install only components that have a pin in
   [`pins-linux-x86_64.json`](pins-linux-x86_64.json) or
   [`pins-macos-arm64.json`](pins-macos-arm64.json). On main that covers
   `foundation-cpu` and `token-efficiency` on both platforms and
   `macos-arm64-foundation` on macOS in full; every other profile is partly or
   wholly unpinned (the "Linux pins" and
   "macOS pins" columns of [the profile table](README.md#choose-a-small-starting-profile),
   which also give the pinned release's coverage where it differs).
   For a partly pinned profile the script first exits 3 and prints the
   unpinned ids. Rerun it as `bootstrap-<os>.sh --profile <id> --allow-unpinned
   <the ids it printed>`: that installs the pinned components with SHA-256
   verification (plus the `node`, `uv` and `gh` every run installs) and skips
   the named ones. Then install each skipped id through
   its `recipe_map` page (the SDK lock for `research-runtime`). A profile with
   "none of N" pinned installs none of its own components through the script
   (only the `node`, `uv` and `gh` every run installs); use the recipes.
   `pins-linux-x86_64.json` changed after `v2026.09.24.1` in `install_note`
   text and in its `claude-code` pin (2.1.280 at that tag, 2.1.284 on main; the
   Claude Code paragraph below has the details). The text changes: the
   markitdown, tavily-cli, orx and agent-browser notes attribute their
   installed-state observations to the 2026-09-23 recording host. Apart from
   Claude Code, versions, URLs and hashes are unchanged, so a host at that tag
   installs the same artifacts except Claude Code.
   It changed after `v2026.09.25.2` again: rtk
   moves from 0.49.0 to 0.50.0 and markitdown from 0.1.7 to 0.1.8 (URLs,
   hashes and notes), so a host at that tag installs the earlier two. A host
   that runs the Claude RTK hook at 0.50.0 also needs the `exclude_commands`
   config in [the RTK hook recipe](../recipes/README.md#native-context-mode-and-hooks),
   which the script does not write.
   It also changed after `v2026.09.25.2` in its `ai-memory` (2.3.2 to 2.4.1)
   and `mcporter` (0.13.13 to 0.14.1) entries, so a host at that tag installs
   the earlier two of those as well; on a host with an existing ai-memory
   store, 2.4.1 migrates it forward-only at the next service start, so take
   the at-rest copy in [the recipe's upgrade steps](../recipes/README.md#upgrading-an-existing-store) first.
   `pins-linux-x86_64.json` (the rtk and headroom `install_note` text and its `claude-code` entry, 2.1.281 at that tag and 2.1.284 on main) and `adoption/bootstrap-linux.sh` changed after `v2026.09.26`: its rtk config reminder now also asks the installed `rtk hook check`; `install_npm` now adds `--ignore-scripts` for a pin with `ignore_scripts: true` (socraticode), a field the tag's script ignores, so there npm runs every install script in socraticode's dependency tree; and `install_uv_tool` now downloads a uv-tool pin's wheel `url` (headroom), verifies its `sha256` before uv runs and installs that file as `'headroom-ai[mcp] @ file://<percent-encoded path>'`, where the tag's script resolves `headroom-ai[mcp]==0.37.0` from the index and never reads the wheel or its hash (the markitdown and tavily-cli sdist hashes stay cross-checks).
   `pins-linux-x86_64.json` changed after `v2026.09.26.2` in its `codex` entry: 0.155.1 moves to 0.159.2 (URL, hashes and note; 0.157.1 from 2026-09-26, 0.159.2 from 2026-09-30), so a host at that tag installs 0.155.1, and in its `claude-code` entry: 2.1.281 moves to 2.1.284 (URL, hashes and note), so a host at that tag installs 2.1.281. `adoption/templates/codex.config.template.toml` changed after the same tag to set `daemon_auto_start = false`: 0.157.1's first interactive launch otherwise installs a self-updating app-server daemon (see `evidence/receipts/codex-01571-qualification-20260926.json`; 0.159.2 still lists the feature as stable and on, `evidence/receipts/codex-01592-qualification-20260930.json`). It changed again on 2026-09-30 to default to `gpt-6.1-sol`, which Codex's bundled model catalog carries from `rust-v0.159.1` on (0.157.1's has no such entry). The macOS pin stays at 0.155.1: macOS needs its own 0.159.x qualification before the template default applies there.

   `pins-linux-x86_64.json` and `adoption/bootstrap-linux.sh` changed after `v2026.09.25.2`.
   The Linux pins file gained `repomix`, `toon`,
   `headroom`, `ccusage`, `serena` and `socraticode`, taking the `token-efficiency` row's
   "Linux pins" column from 8 of 14 to all 14. `install_pin`'s `*-uv-tool` case now reads an
   optional pin `package` field
   (falling back to its own `id` for every other uv-tool pin, unchanged) so a
   PyPI distribution name that differs from the component id, like headroom's
   `headroom-ai[mcp]`, installs correctly; a new `uv-tool-from-git` kind
   installs Serena from its exact pinned commit (no released version exists
   to pin a sha256 against) and re-verifies that commit against the
   resulting `uv-receipt.toml`. At that tag and every earlier one, the Linux
   pins file has no entry for any of those six ids.
   `adoption/pins-macos-arm64.json` and `adoption/bootstrap-macos.sh` changed after `v2026.09.26`:
   the macOS pins file gained `rtk`, `qmd`, `repomix`, `toon`, `ccusage`, `headroom`,
   `markitdown` and `serena` at their Linux versions, taking the "macOS pins" column from
   6 of 14 to all 14 for `token-efficiency` and from 5 of 7 to all 7 for `foundation-cpu`
   ([the profile table](README.md#choose-a-small-starting-profile)), and the macOS script
   gained the Linux script's `uv-tool` and `uv-tool-from-git` kinds and shared checksum/download
   helpers, copied verbatim (`adoption/bootstrap-macos.sh` changed after `v2026.09.26`, so its
   `install_uv_tool` downloads headroom's `macosx_11_0_arm64` wheel, verifies its sha256 with
   `shasum -a 256` before uv runs and installs that file, as the Linux one above does), and,
   after installing rtk, prints a reminder unless `~/Library/Application Support/rtk/config.toml`,
   the only config file rtk 0.50.0 reads on macOS (it ignores `XDG_CONFIG_HOME` there;
   `evidence/artifacts/macos-token-pins-20260926/rtk-config-path.txt`), holds step
   4a's five-entry `exclude_commands` key exactly once; its `--plan` prints serena's pinned
   commit instead of a sha256. At that tag and every earlier one, the macOS pins file has no entry
   for any of those eight ids, so on macOS either profile exits 3 and names them; pass them
   in `--allow-unpinned` and install them through their recipes, or wait for the next
   re-pin. The digests were re-checked against fresh upstream downloads on 2026-09-26
   (`evidence/artifacts/macos-token-pins-20260926/digest-check.txt`).

   Both scripts and both claude-code pins changed after `v2026.09.24.1`: at
   that tag the pins are 2.1.280 and `adoption/bootstrap-linux.sh` and
   `adoption/bootstrap-macos.sh` reinstall the pin even over a newer Claude
   Code; on main the pins are 2.1.284 and both scripts keep an installed
   `~/.local/bin/claude` at or above the pin (logging `Kept installed
   claude-code <version>`), running the checksum-verified install only when
   that launcher is missing, older or unreadable. Both pins also changed after `v2026.09.26.2`,
   where both are 2.1.281: 2.1.284 is the first Claude Code release whose
   `sonnet` alias resolves to Sonnet 5.5 (on the Anthropic API; an older client routes it to Sonnet 5; [model-config](https://code.claude.com/docs/en/model-config)),
   so on main a launcher reporting 2.1.281 to 2.1.283 no longer counts as at
   or above the pin and takes the checksum-verified install.

   Both scripts also write the ecosystem `claude` launcher (`$eco/bin/claude`;
   none is written when that directory is `~/.local/bin`, where the native
   installer's own launcher serves). On main that launcher starts an
   interactive terminal launch at effort max: it adds `--effort max` only when
   stdin and stdout are a terminal, none of `-p`/`--print` (also as a cluster
   such as `-pc`), `--effort` or `CLAUDE_CODE_EFFORT_LEVEL` has chosen an
   effort, nothing follows a `--`, and the client reports 2.1.284 or newer (on
   2.1.281 a `max` session turned Ultracode's orchestration off). Claude Code
   cannot save max in settings, and the variable would override every child's
   effort, so the documented flag is the mechanism
   ([decision](../docs/decisions/2026-09-29-max-default-effort.md)). Headless
   runs, an explicit `--effort`, the IDE extensions, the desktop app and the
   web keep the saved per-model level; bypass with `--effort <level>` or by
   running `~/.local/bin/claude` directly.

   **The whole user profile in one run** (Linux/WSL2; `--configure-full-profile`,
   `tools/adoption/managed_block.py`, `tools/adoption/codex_home.py` and
   `scripts/adoption_status.py --launcher-resolution` added after `v2026.09.26.2`, so a
   checkout at that tag runs steps 4 and 4a by hand).
   After native sign-in (step 3), `adoption/bootstrap-linux.sh --profile <id>
   --configure-full-profile --host <name>` replaces the hand steps with the
   repository's own tools, in this order, each skippable with `--skip <step>`
   (repeat it, or give a comma-separated list):

   | Step | What runs |
   | --- | --- |
   | `claude-profile` | `tools/adoption/install_claude_profile.py` (guard hooks, agents, MCP servers; step 4a) |
   | `claude-settings` | `tools/adoption/render_config.py --host <name> --out` into the run's staging directory, then `tools/adoption/apply_claude_settings.py` with the rendered `settings.json`, then with `adoption/templates/claude.settings.linux-wsl2.overlay.json` when `WSL_DISTRO_NAME` is set (step 4a; [WSL page](platforms/linux-wsl2.md#windows-terminal-profiles-and-the-login-shell)) |
   | `claude-md` | `tools/adoption/managed_block.py claude-md`: `examples/claude-native/CLAUDE.md` as a managed block in `~/.claude/CLAUDE.md` |
   | `skills` | the skills CLI pinned in `adoption/skills/manifest.json` (its npm tarball and sha256, through the script's own checksum-verified npm install) when missing, then `tools/adoption/install_skills.py` ([skills manifest](update.md#apply-the-skills-manifest)) |
   | `codex-lane` | `tools/adoption/codex_home.py`, which meets the lane's preconditions: a Codex home without `config.toml` gets the rendered `codex.config.toml` (the template's own model, approval and sandbox policy, servers and `features.daemon_auto_start = false`) without the source host's `[projects.*]` trust grants and `[hooks.state.*]` hook approvals, created only when absent, `0600`; an existing `config.toml` is never replaced, and gets `features.daemon_auto_start = false` through `codex features disable daemon_auto_start` when it lacks it, only while no `codex` process runs (as `--apply` requires) and after a backup beside it, the only undo for that key. Then `tools/adoption/apply_codex_lane.py` with `--codex $ECO_INSTALL_ROOT/bin/codex` and the host file's `HOST_PATH` as `--host-path`: its dry run, then `--apply` with the two `--expect-*-sha256` hashes that dry run printed. It installs the two role carriers and never the worker roles, which only `--worker-roles` installs (step 4) |
   | `path-block` | `tools/adoption/managed_block.py profile-path`: a managed block in `~/.profile` that puts `$ECO_INSTALL_ROOT/bin` first on `PATH` |
   | `login-shell` | `scripts/adoption_status.py --login-shell --launcher-resolution` under Python 3.13 (step 6's form); the step fails unless `claude` in a login shell is the ecosystem launcher |

   `--host <name>` names `adoption/hosts/<name>.json` (step 4); it is required
   unless both `claude-settings` and `codex-lane` are skipped. The flag applies
   what main documents, so it runs only from a clone at `origin/main` (a release
   checkout follows steps 4 and 4a by hand, as the note above says). Its checks
   come first, in this order, and the script installs and writes nothing until
   they pass: the usage checks (exit 2); the platform checks (x86_64 Linux, not
   root, Ubuntu or Debian; exit 1); `git` on `PATH`; and `git rev-parse HEAD`
   equal to `git ls-remote origin refs/heads/main`, with both commits printed.
   Only then does the script install the missing system packages (the `sudo
   apt-get` step), check the prerequisites, install the pins, write the version
   report and run the steps above. A checkout that is not at `origin/main`, or
   whose origin cannot be read, is refused with exit 1 and the host unchanged.
   So is a host without `git`: the package step that would install it comes
   after this check, so the refusal names `sudo apt-get install -y git`, and a
   run of the script without the flag installs it as well. Without the flag the
   order is unchanged: system packages first, and git is never asked. A failed
   step is reported and the rest still run; the script then exits 6. Every step
   is idempotent: fix the cause and re-run, skipping what is done.

   Both managed blocks work alike. The begin and end markers must appear exactly
   once and in order, or the file is refused; without them the block is appended
   after the existing text; every line outside them is kept; the file is backed
   up beside itself first (`<name>.bak.<UTC stamp>`, never overwriting an earlier
   backup) and replaced atomically with its mode kept; a file already up to date
   is not touched. In `~/.claude/CLAUDE.md`, rtk's `@RTK.md` import stays outside
   the block, and a hand-merged copy of the example with no markers is replaced
   only when it equals the current example ([the recipe's rule](../recipes/claude-native-profile.md#small-persistent-contract-selected-upstream-skills));
   any other copy is refused, so remove it or wrap it in the markers first. The
   `~/.profile` block is the only shell startup file this script writes. A login
   shell reads `~/.profile` only when no `~/.bash_profile` or `~/.bash_login`
   exists, which is why the last step checks where `claude` resolves. The
   user-level `codex.config.toml` that `render_config.py` renders is installed
   only into a Codex home that has none, and never with the source host's trust
   state (step 4's warning): Codex asks about project trust and hooks on this
   host instead. A host that already has a `config.toml` keeps it; compare it
   with the render (`render_config.py --host <name> --check`, step 4) and merge
   by hand. The run's rendered copies go with its staging directory.

3. **Native sign-in.** Neither client's credentials transfer between machines
   (`adoption/manifest.json` `policy.authentication_transfer: native_login_on_target_only`).
   Use each client's own device flow:
   ```sh
   codex login   # or: CODEX_HOME="$NATIVE_CODEX_HOME" "$NATIVE_CODEX_BIN" login --device-auth
   claude        # first run walks through the device flow; see recipes/README.md
   ```
   Then confirm discovery with `codex mcp list` and `claude mcp list` before any
   scoped task (native verification tier "Client activation" in
   [`adoption/README.md`](README.md#native-verification-tiers)).
   Provider keys (Alpaca paper, SEC contact, optional paid keys) go in
   per-provider `0600` files outside the checkout; follow
   [`docs/secret-storage.md`](../docs/secret-storage.md) and check with
   `python3 scripts/credential_status.py` (both added after `v2026.09.24.1`).

4. **Render configs.** Use [`tools/adoption/render_config.py`](../tools/adoption/render_config.py)
   with the selected host's `adoption/hosts/<host>.json` (gitignored; copy
   [`adoption/hosts/example.json`](hosts/example.json) and fill in this host's
   `HOME`, `ECO_ROOT`, `PROJECT_ROOT`, `HOST_PATH`, `CODE_INDEX_PATH`,
   `OTEL_ENDPOINT`, `AI_MEMORY_URL`, `QDRANT_URL`, `EMBED_URL`):
   ```sh
   python3 tools/adoption/render_config.py --host <host> --out "$RUN_DIR/rendered"
   python3 tools/adoption/render_config.py --host <host> --check \
     --live-codex-project "$PROJECT_ROOT/.codex/config.toml"   # compare against live configs before overwriting them
   ```
   Templates are in [`adoption/templates/`](templates/): `claude.settings.template.json`,
   `codex.config.template.toml` (user-level `~/.codex/config.toml`), and
   `project.codex.config.template.toml` (project-level `.codex/config.toml`).
   A new repository gets its `.codex/config.toml` from
   `tools/adoption/scaffold_repo.py` (added after `v2026.09.26.2`), which renders
   that template with the same renderer for this host instead of a hand copy
   ([new repositories](#new-repositories)).
   `--check`'s `project.codex.config.toml` comparison targets the project
   being onboarded (`$PROJECT_ROOT`, e.g. `agent-lab`), never this catalog
   checkout, which has no `.codex/config.toml` of its own and will always
   report "live file not found" if `--live-codex-project` is omitted; pass it
   explicitly, or export `ADOPTION_PROJECT_ROOT` before running (see
   `tools/adoption/render_config.py --help`). `--check` prints a unified diff
   and exits 1 on any byte difference; a pure JSON-formatting difference is
   called out explicitly in its output. `project.codex.config.template.toml`
   changed after `v2026.09.24.1`: its `serena` server runs
   `${ECO_ROOT}/bin/serena` (installed in step 4a), where the tag's copy names
   `${ECO_ROOT}/bin/serena-context`, a wrapper nothing in this catalog installs.
   `claude.settings.template.json` changed after `v2026.09.25.2`: its eight
   ai-memory hook commands name `tools/ai-memory-2.4.1`, the Linux pin; on
   macOS, whose pin is still 2.3.2, see
   [ai-memory hook paths on macOS](platforms/macos-arm64.md#ai-memory-hook-paths-on-macos).
   Since 2026-09-27 the eight commands run `${AI_MEMORY_BIN}`: `render_config.py`
   renders `${ECO_ROOT}/tools/ai-memory-<version>/ai-memory` from the pins file of
   the machine it runs on (`--platform linux-x86_64` or `--platform macos-arm64`
   chooses another), and `--set AI_MEMORY_BIN=<path>` names a binary installed
   elsewhere; a platform without a pins file fails until one of the two is given.
   `claude.settings.template.json` changed after `v2026.09.26.2` again: it sets `syncClaudeAiSkills` to `false` and `ENABLE_CLAUDEAI_MCP_SERVERS` to `"false"`, so Claude Code neither syncs the claude.ai account's skills nor loads its claude.ai MCP servers ([decision](../docs/decisions/2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-claudeai-skill-sync-and-mcp-servers-off)), and it adds a `Read(**/…)` twin after each `~/`, `//` and `.env` credential deny rule, the `.env` twins ahead of the `!` carve-outs, because Context Mode's server-side path check does not expand `~/` or `//` ([secret storage](../docs/secret-storage.md#user-level-guards-deployed-by-the-claude-profile)).
   `claude.settings.template.json` also changed after `v2026.09.26.2`: it sets
   `OTEL_METRICS_INCLUDE_SESSION_ID` to `true` (Claude Code's default), so each
   session gets its own Prometheus series
   ([writer identity](../observability/collector/README.md#writer-identity-and-counter-integrity)),
   and `OTEL_LOG_TOOL_DETAILS` to `"1"`, a dated user exception whose Collector
   filter exports only tool, MCP server, skill and agent names
   ([tool details](../docs/secret-storage.md#telemetry-and-pasted-values)).
   `claude.settings.template.json` also changed after `v2026.09.26.2`: it adds a
   `SubagentStart` group that runs `~/.claude/hooks/token-lanes-subagent-start.py`,
   installed by the **guard hooks** step of `install_claude_profile.py` below, so
   every non-blind subagent except `semantic-evidence-reviewer` receives the token-lanes block matched to its role
   ([decision](../docs/decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-role-matched-blocks)); while that
   file is absent the command exits 0 and adds nothing.
   `claude.settings.template.json` also changed after `v2026.09.26.2`: it sets `MCP_TIMEOUT` to `"120000"`, the startup timeout of every MCP server (default 30 s, [environment variables](https://code.claude.com/docs/en/env-vars)); the value is global because Claude Code 2.1.285 and 2.1.286 have no per-server startup setting (`claude mcp add --help` lists no timeout option, and a server's `timeout` field bounds tool calls only), and 120 s matches the Codex template's slowest `startup_timeout_sec` ([decision](../docs/decisions/2026-09-30-mcp-startup-timeout.md)). It also denies, in every session, the Skills CLI's install, remove and update commands and `Edit(~/.agents/**)`, so skills install only through `tools/adoption/install_skills.py` ([lifecycle](skills/lifecycle.md#install-and-inspect)).
   `codex.config.template.toml` changed after `v2026.09.26`: it turns the context-mode plugin's own MCP server off and registers context-mode at user scope with no `cwd`, running the pinned npm install's `start.mjs`, so each Codex session's server binds that session's own directory ([recipe](../recipes/README.md#retained-context-mode)), and its `headroom` entry adds `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE`; `project.codex.config.template.toml` changed after `v2026.09.26` in its comments only.
   The recipe's project-scoped alternative changed after `v2026.09.26.2`: it adds `default_tools_approval_mode = "approve"` and a `CLAUDE_PROJECT_DIR` equal to its project directory, as upstream `start.mjs` sets, so a project entry keeps Codex tool approvals and the server-side project `Bash(...)` denies ([recipe](../recipes/README.md#retained-context-mode)).
   `codex.config.template.toml` changed after `v2026.09.26.2` again: it sets `web_search = "live"`, `check_for_update_on_startup = false`, `[features] shell_snapshot = false` and `[agents] default_subagent_reasoning_effort = "max"`, and it no longer trusts four dated validation directories. Its SocratiCode server now runs `${ECO_ROOT}/tools/socraticode-${SOCRATICODE_VERSION}/`, which `render_config.py` renders from the selected platform's pin like `${AI_MEMORY_BIN}` (1.15.0 on Linux and 1.14.0 on macOS since 2026-09-27); `--set SOCRATICODE_VERSION=<version>` names another install. Since 2026-09-30 its `model` and `[agents] default_subagent_model` are `${CODEX_MODEL}`, which `render_config.py` renders from the selected platform's Codex pin: `gpt-6.1-sol` from Codex 0.159.1, which added it to the bundled catalog (the Linux pin), and `gpt-6-astra` before it (the macOS pin, 0.155.1); `--set CODEX_MODEL=<model>` names another model. The opt-in gateway profile `codex.omniroute.config.toml` (added after that tag) is not rendered here; `tools/adoption/apply_codex_lane.py --omniroute-profile` installs it ([recipe](../recipes/README.md#codex-through-omniroute)).
   The Codex worker lane's installer, `tools/adoption/apply_codex_lane.py` (added after `v2026.09.26.2`; [recipe](../recipes/README.md#codex-worker-lane)), puts the two role carriers of `adoption/agents/codex/` under `$CODEX_HOME/agents/`. Its `--worker-roles` flag, added after `v2026.09.26.2`, also installs `evidence-reviewer`, `isolated-builder` and `semantic-evidence-reviewer` from `adoption/agents/codex/workers/`: the Codex counterparts of the Claude roles of the same names, pinned at `gpt-6-astra` and `max`, each checked against that folder's `SHA256SUMS` and the rules of `tools/adoption/codex_roles.py` before anything is copied, and rolled back like the carriers ([F4 Codex roles](../docs/decisions/2026-09-26-stack-agents-role-dispatch.md#addendum-2026-09-30-f4-codex-roles)). Every installed role's description enters every Codex parent's `spawn_agent` text, so leave the flag off while the token-adoption E2E's Gate A window is open. Step 2's `--configure-full-profile` never passes the flag: its `codex-lane` step installs the two carriers only, and the worker roles reach a host only through a run of `apply_codex_lane.py --worker-roles` by hand (its dry run, then the `--apply` command that dry run prints). A later run without the flag, the `codex-lane` step's included, keeps a host's installed worker roles and does not count them as extra role files.
   `codex.config.template.toml` changed after `v2026.09.26.2` once more: it sets `[tui] notifications` to the needed-action kinds (`approval-requested`, `plan-mode-prompt`, `async-question`), so Codex asks for a notification on an approval, a plan-mode prompt or a question and not when a turn finishes. Codex keeps its own per-terminal channel, so a macOS host still gets native notifications for those kinds and stops getting the turn-complete one; at the macOS pin a `request_user_input` question already notifies as `plan-mode-prompt` and `async-question` (asynchronous questions added later) is inert, so no notification that release emits is lost ([decision](../docs/decisions/2026-09-28-terminal-experience.md#repository-carried-defaults-and-the-second-distros-profiles-2026-09-29)).
   The rendered `codex.config.toml` keeps the source host's `trusted_hash`
   entries for the ai-memory commands in `~/.codex/hooks.json`, recorded before
   those commands moved to 2.4.x; Codex treats the changed commands as
   untrusted until they are reviewed in `/hooks`.

   **Trust-state warning.** The rendered `codex.config.toml` (user-level)
   carries this source host's accumulated Codex `[projects."..."]
   trust_level = "trusted"` grants and `[hooks.state...] trusted_hash` MCP/hook
   approvals byte-for-byte (only the nine `${...}` placeholders above are
   substituted; see the template's own top-of-file docstring in
   `tools/adoption/render_config.py`). None of those grants or hashes have
   been reviewed on the target machine. This does not itself transfer
   authentication (`adoption/manifest.json` `policy.authentication_transfer:
   native_login_on_target_only`, step 3 above), but it does pre-approve
   project trust and hook execution state that a fresh Codex install would
   otherwise ask about. Review the rendered file's `[projects.*]` and
   `[hooks.state.*]` sections before use on a new host and drop entries that
   do not apply (the `codex-lane` step of step 2's `--configure-full-profile`
   drops all of them when it installs the file); `adoption/manifest.json` `policy.historical_acceptance_transfers:
   false` means none of that state should be read as re-qualifying the new
   host's own acceptance evidence.

4a. **Claude user-scope profile.** After step 3's native `claude` sign-in
   (this step is a no-op, not a failure, without it -- the MCP registration
   sub-step below needs a working `claude` binary), install this catalog's
   Claude Code user-scope assets with
   [`tools/adoption/install_claude_profile.py`](../tools/adoption/install_claude_profile.py).
   Its MCP sub-step registers the template's commands but installs none of
   them, so first install Serena (the MCP sub-step below names where the
   template's other stdio servers come from) and
   jCodeMunch, which the per-project opt-in below uses, at their pins, with the
   uv-tool layout `bootstrap-linux.sh` uses for its uv-tool pins
   (`python-tools/` and `bin/` under the ecosystem prefix, on either
   platform). That puts `serena` and `jcodemunch-mcp` in `${ECO_ROOT}/bin`,
   where the template and the opt-in point (changed after `v2026.09.24.1`,
   whose template names a `serena-context` wrapper instead of `serena` and
   also registers `jcodemunch` at user scope):
   ```sh
   eco="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
   UV_TOOL_DIR="$eco/python-tools" UV_TOOL_BIN_DIR="$eco/bin" \
     uv tool install --python 3.13 git+https://github.com/oraios/serena@c6fbd1c5932df2494ffa0020af5a9fbe80b82143
   UV_TOOL_DIR="$eco/python-tools" UV_TOOL_BIN_DIR="$eco/bin" \
     uv tool install --python 3.13 jcodemunch-mcp==1.108.319
   "$eco/bin/serena" --version           # Serena 2.0.0.dev0
   "$eco/bin/jcodemunch-mcp" --version   # jcodemunch-mcp 1.108.319
   ```
   Then run the installer:
   ```sh
   python3 tools/adoption/install_claude_profile.py            # guard + agents + MCP servers
   python3 tools/adoption/install_claude_profile.py --dry-run   # report only, write/register nothing
   python3 tools/adoption/install_claude_profile.py --only mcp  # just the MCP step
   ```
   Both platform bootstrap scripts also accept
   `--configure-claude-user-profile` to run this automatically as their own
   last step (still only meaningful after sign-in; run it manually
   afterward otherwise, exactly as the script's own closing message says; a
   run that exits 5 stops before that step and that message).
   Three idempotent sub-steps, each safe to re-run:
   - **guard hooks**: copies [`adoption/hooks/claude/effort-default-guard.py`](hooks/claude/effort-default-guard.py)
     to `~/.claude/hooks/effort-default-guard.py` and the secret guard
     [`scripts/hooks/secret_path_guard.py`](../scripts/hooks/secret_path_guard.py)
     to `~/.claude/hooks/secret_path_guard.py` (the secret guard and its
     settings entries were added after `v2026.09.24.1`). This step **changed after `v2026.09.26.2`**:
     it also copies [`adoption/hooks/claude/token-lanes-subagent-start.py`](hooks/claude/token-lanes-subagent-start.py)
     and its sibling [`adoption/hooks/claude/token-lanes-block.md`](hooks/claude/token-lanes-block.md)
     with the five role blocks `adoption/hooks/claude/token-lanes-block.<role>.md`
     (`builder`, `researcher`, `reviewer`, `scout`, `verifier`)
     into `~/.claude/hooks/` (all seven files added after `v2026.09.26.2`).
     The hook supplies token-lane guidance before each non-blind subagent's first prompt
     through the [SubagentStart context contract](https://code.claude.com/docs/en/hooks#subagentstart):
     a shipped role with a `tools:` allowlist receives the role block that names only the lanes it grants,
     and other types receive the full block
     ([agent-type table](../docs/token-session-handbook.md#token-lanes-carried-into-subagents));
     `blind-*` roles and `semantic-evidence-reviewer` receive no context from this hook.
     It refuses to install any file unless
     every sha256 matches [`adoption/hooks/claude/SHA256SUMS`](hooks/claude/SHA256SUMS)
     (paths relative to that file); skipped per file if the installed copy
     already matches.
   - **agents**: copies the eleven [`adoption/agents/claude/*.md`](agents/claude/)
     files verbatim to `~/.claude/agents/`; skipped per-file when already
     byte-identical. They changed after `v2026.09.26`: `stack-researcher`,
     `stack-verifier` and `security-reviewer` were added (the security role
     preloads `security-best-practices`), and `isolated-builder` preloads
     `context-mode:context-mode` (its `verification-before-completion` preload was
     removed on 2026-09-28 with that skill's trial) and lost Serena's
     symbol-edit tools, which would edit the parent session's checkout rather
     than the builder's worktree.
   - **MCP servers**: for each entry in
     [`adoption/mcp/claude-user.json`](mcp/claude-user.json) (`ai-memory`
     over http; `serena`, `socraticode`, `headroom`, `codebase-memory` and
     `qmd` over stdio), renders its `${HOME}` and
     `${ECO_ROOT}` placeholders (`--eco-root`, default `$ECO_INSTALL_ROOT` or
     `~/.local/share/codex-ecosystem`), then runs `claude mcp add --scope user
     <name> [-e KEY=VALUE ...] -- <command> [args...]`; skipped when `claude
     mcp get <name>` already reports a matching transport, command/URL, args
     and env variable names (values are not compared -- the running host owns
     them). A same-named server with a different config is reported and left
     unchanged unless `--replace-mcp` is given. That flag re-registers every
     differing server, including an `ai-memory` entry that names this host's
     own port. To change one server, remove it and rerun without the flag:
     `claude mcp remove <name> -s user`, then
     `python3 tools/adoption/install_claude_profile.py --only mcp`. The
     template's `ai-memory` URL is this catalog's default, `127.0.0.1:49374`;
     the registration must name the port this host's ai-memory unit binds
     (`AI_MEMORY_URL` in step 4). `claude mcp add` refuses a name that already
     exists, so for another port run `claude mcp remove ai-memory -s user`,
     then
     `claude mcp add --scope user --transport http ai-memory http://127.0.0.1:<port>/mcp`.
     The template changed after `v2026.09.26.2`: `socraticode`, `headroom`,
     `codebase-memory` and `qmd` joined, so a new host registers every server
     the SubagentStart token-lanes carrier names except `jcodemunch` (below)
     and context-mode, which its plugin supplies. Each entry runs the command,
     arguments and environment of its entry in the Codex user template; the
     template's `_comment` gives the three Claude-side differences and the
     repository-default SocratiCode endpoints (`QDRANT_URL` and `EMBED_URL` in
     `adoption/hosts/example.json`), which a host with other endpoints
     registers by hand. The sub-step installs none of them: SocratiCode,
     Headroom and QMD come from the `token-efficiency` profile's pins, and
     codebase-memory-mcp, which no pins file installs yet, from its v0.11.0
     release by hand
     ([catalog row](../recipes/README.md#component-catalog-install-and-check)),
     never through a bounded runner, because every session's frontend shares
     one daemon. The record is the 2026-09-30 addendum, added after
     `v2026.09.26.2`
     ([F4 Codex roles](../docs/decisions/2026-09-26-stack-agents-role-dispatch.md#addendum-2026-09-30-f4-codex-roles)).
     A host that registered one of these servers by hand keeps its entry: the
     installer reports it as matching (same command, arguments and variable
     names) or as differing, and replaces it only with `--replace-mcp`.

   **jCodeMunch, per project.** The template leaves `jcodemunch` out (changed
   after `v2026.09.24.1`). At user scope its server instruction ("Prefer it
   over Read/Grep/Glob/Bash for code navigation") loaded into every session
   and contradicted agent-lab's routing (`rg` for discovery, Serena for
   symbols). On 2026-09-25 the recording host's 5,076 retained Claude Code
   transcripts, the oldest from 2026-09-18, held 15 jCodeMunch tool calls
   (Serena 33, SocratiCode 7), and in a retrieval comparison it scored hit@5
   0.25 against SocratiCode's 0.85
   ([addendum](../docs/decisions/2026-09-23-claude-user-profile.md#addendum-2026-09-25-jcodemunch-registers-per-project-not-at-user-scope)).
   A project that wants it registers it from the project root, privately:
   ```sh
   claude mcp add --scope local jcodemunch \
     -e "CODE_INDEX_PATH=$HOME/.code-index" -e JCODEMUNCH_SHARE_SAVINGS=0 \
     -- "${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp"
   ```
   or for everyone who opens it, with this entry in the project's checked-in
   `.mcp.json`. Claude Code expands `${HOME}` in it, and starts the server
   only after the workspace is trusted and the server approved:
   ```json
   {"mcpServers": {"jcodemunch": {"type": "stdio",
     "command": "${HOME}/.local/share/codex-ecosystem/bin/jcodemunch-mcp", "args": [],
     "env": {"CODE_INDEX_PATH": "${HOME}/.code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"}}}}
   ```
   A nested default such as `${ECO_INSTALL_ROOT:-${HOME}/...}` does not
   expand there, so a host with another ecosystem prefix uses the local form,
   which takes precedence over the project entry. The
   [jCodeMunch recipe](../recipes/README.md#focused-jcodemunch-retrieval)
   covers indexing and the native statistics.

   Then apply the settings template itself (model, effort, ultracode,
   workflow env, hooks, and the credential deny rules plus the `PreToolUse`
   secret-guard hook from [`docs/secret-storage.md`](../docs/secret-storage.md#user-level-guards-deployed-by-the-claude-profile)) into the live `~/.claude/settings.json` with
   [`tools/adoption/apply_claude_settings.py`](../tools/adoption/apply_claude_settings.py),
   after rendering it for this host with step 4's `render_config.py --out`:
   ```sh
   python3 tools/adoption/apply_claude_settings.py --template "$RUN_DIR/rendered/settings.json"
   python3 tools/adoption/apply_claude_settings.py --template "$RUN_DIR/rendered/settings.json" --dry-run
   ```
   Backs up the current file (`settings.json.bak.<UTC timestamp>`, with a
   counter suffix rather than overwriting an earlier backup) before
   writing, refuses to operate through a symlink, deep-merges (template
   scalars win; nested objects such as `modelSettings`, `env`, `permissions`
   and `enabledPlugins` merge per key and lists union, so host-only rules
   are kept; `hooks` combine per event, de-duplicated across the event by
   each command's shell words; everything else in the live file that the
   template does not mention is kept), writes atomically and
   preserves the original file's mode bits. Never touches `~/.claude.json`
   or any credential store. `tools/adoption/apply_claude_settings.py`
   changed after `v2026.09.26.2`: a template list entry the live list lacks
   now joins right after its template neighbour instead of at the end, so a
   deny rule stays ahead of the `!` carve-outs a host file already holds (a
   carve-out reaches only the rules before it). The tag's applier appends a
   missing entry at the end, so it would put the template's Context Mode
   twins after `Read(!.env.example)` and deny that file again; apply the
   template from a checkout that has both changes.
   The template registers the `rtk hook claude` Bash hook, so with the rtk 0.50.0 pin also make the `[hooks]` table of rtk's config file (`~/.config/rtk/config.toml` on Linux, or `$XDG_CONFIG_HOME/rtk/config.toml` when that is set to an absolute path; `~/Library/Application Support/rtk/config.toml` on macOS, where rtk ignores `XDG_CONFIG_HOME`; `rtk config` prints the file on its first line, `evidence/artifacts/macos-token-pins-20260926/rtk-config-path.txt`) hold `exclude_commands = ["^git show [^ ]*:", "diff", '^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*show\s+(?:[^\n]*\s)?[^\s]*:', '^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*branch(?:\s|$)', "jq"]`: inside the existing `[hooks]` table, **replace** the key's whole value, from `exclude_commands =` through its closing `]` (or add the key when the table lacks it), and add a `[hooks]` header line only when the file has no `[hooks]` table (a second `[hooks]` header or `exclude_commands` key is invalid TOML, and rtk then silently falls back to defaults, `src/core/config.rs:278-281`, rather than erroring): 0.50.0's hook windows `git show <rev>:<path>` blobs, so a piped `| tail` reads the window instead of the file's end, and a rewritten `diff` exits 1 instead of 2 on a missing file; the bare `"^git show [^ ]*:"` pattern misses a `git -C <dir> show HEAD:path` form, which is still windowed (8,261 of 22,907 bytes in one fixture), so the third entry anchors to the git subcommand position, matching `git show REV:path` in a bare, `-C`/`-c`/`--git-dir`/`--work-tree` or other `--flag` global-option form (the same global options rtk's own discovery strips, `GIT_GLOBAL_OPT`, `src/discover/registry.rs:78`) without also excluding a command that merely mentions "show" as an ordinary argument; and `git branch -a`'s branch-name compaction keeps git's local-worktree `+ ` prefix unconditionally ([`src/cmds/git/git_cmd.rs:3185-3244`](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/src/cmds/git/git_cmd.rs#L3185-L3244), specifically `git_cmd.rs:3209-3211`, unchanged on `develop`), but only misreports that branch as remote-only when a remote-tracking branch of the same name also exists (`git_cmd.rs:3224-3227`) -- 31 vs 6 real in one fixture -- so the fourth entry similarly anchors `git branch` to native git ([RTK hook recipe](../recipes/README.md#native-context-mode-and-hooks); retained check `evidence/artifacts/rtk-exclude-widen-20260926/hook-check.txt`); the fifth, plain `"jq"`, keeps a standalone `jq` command native, because rtk's `jq` rewrite truncated structured output (the recipe's fifth-entry paragraph). At `v2026.09.25.2` rtk was pinned at 0.49.0 and `adoption/bootstrap-linux.sh` printed no reminder at all -- the reminder was added after that tag (#291). It changed after `v2026.09.26`, which already pins rtk 0.50.0 but still checks only for the original two-entry key and does not detect a duplicate `exclude_commands` line; here it requires every entry of that value, exactly once, to be present (five since F2 added `"jq"`). It also changed after `v2026.09.26` in a second way (#314): once the text matches, it runs the installed `rtk hook check` on `git show HEAD:x | tail -n 5`, `git -C . show --no-color HEAD:x | tail -n 5`, `diff a missing`, `git branch -a`, `git -C . branch` and `jq -r .x f.json`, and still reminds unless each answers `No rewrite for: ...` with exit 1, because rtk can ignore a TOML-valid file with the exact text (a `[tracking]` table without `history_days` fails `TrackingConfig`, `src/core/config.rs:152-158`); check the file the same way after any edit. A single-regex alternative tested on 2026-09-26 is retained as evidence only; the adopted recipe is the five-entry set.
   The agent definitions in `adoption/agents/claude/` changed after `v2026.09.26.2` in `blind-adjudicator.md`, whose
   leak check now names the GPT-6 and Claude families (astra, gpt-6-sol, gpt-6-luna, gpt-5.6-terra, fable, mythos);
   a host at that tag installs the earlier list. They changed after `v2026.09.24.1`:
   at that tag `source-scout` and `isolated-builder` declare `effort: medium`
   (`source-scout` also `maxTurns: 40`), `evidence-reviewer`,
   `semantic-evidence-reviewer` and `blind-judge` declare `effort: high`, and the
   two blind lane roles are absent; here all ten declare `effort: max`
   ([decision](../docs/decisions/2026-09-23-max-effort-default.md)). The guard
   hooks' `adoption/hooks/claude/` also changed after `v2026.09.24.1` (its
   `SHA256SUMS` gained the secret-path guard entry), and it changed after `v2026.09.25.1` again:
   its secret-path guard hash now covers the Hugging Face store rules (#268), so
   rerun the guard step from a checkout that has them. The installer replaces a
   differing agent file, so rerunning its agents step from a checkout that has
   the change installs the `max` definitions. The MCP template
   `adoption/mcp/claude-user.json` also changed after `v2026.09.24.1`: at that
   tag its `serena` entry runs `${ECO_ROOT}/bin/serena-context`, a wrapper
   nothing in this catalog installs, so a host at the tag registers a `serena`
   server that cannot start. Here it runs `${ECO_ROOT}/bin/serena`, installed
   above. On a host already registered from the tag the installer reports
   `serena` as differing; run `claude mcp remove serena -s user`, then
   `python3 tools/adoption/install_claude_profile.py --only mcp`. The tag's
   template also registers `jcodemunch` at user scope. This one has no
   `jcodemunch` entry, and the installer only visits the servers the template
   names, so it neither adds nor removes one: a host registered from the tag
   runs `claude mcp remove jcodemunch -s user` and opts in per project as
   above.

   **Plugin revision check** (added after `v2026.09.23.1`; it reads only this
   host's plugin registry, so it runs the same from any checkout). A Claude
   marketplace source takes a branch or tag and never a commit
   ([plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)):
   an `owner/repo@<commit>` source fails to add (measured on Claude Code
   2.1.281, [recipe](../recipes/README.md#native-context-mode-and-hooks)). The
   template's `extraKnownMarketplaces` and the commands below therefore hold
   `claude-hud` and `openai-codex` to a tag and give `context-mode` no ref, so
   `context-mode` installs whatever its default branch holds. Install the three
   plugins with their [recipe rows'](../recipes/README.md#component-catalog-install-and-check)
   commands:
   ```sh
   claude plugin marketplace add mksglu/context-mode --scope user
   claude plugin install context-mode@context-mode --scope user --json
   claude plugin marketplace add jarrodwatts/claude-hud@v0.8.0 --scope user
   claude plugin install claude-hud@claude-hud --scope user --json
   claude plugin marketplace add openai/codex-plugin-cc@v1.0.6 --scope user
   claude plugin install codex@openai-codex --scope user --json
   ```
   Then compare the `gitCommitSha` that landed with the reviewed revisions in
   those rows (the check reads `$CLAUDE_CONFIG_DIR` when it is set, as Claude
   Code does). `context-mode`, installed from the default branch, also passes
   by content: GitHub's compare API (`gh api`, signed in at step 3) must report
   the installed revision `ahead` of the reviewed one with `stats.json` as the
   only changed file (changed after `v2026.09.26.2`, whose check prints
   `MISMATCH` for any revision other than the reviewed one):
   ```sh
   python3 - <<'EOF'
   import json, os, pathlib, re, subprocess
   reviewed = {  # recipes/README.md rows: context-mode, claude-hud (tag v0.8.0), codex-for-claude
       "context-mode@context-mode": "6f0cc6841c687e754059f36714a11233fda1a02b",
       "claude-hud@claude-hud": "ef5f1c8b167572ad1443c70629763ea8780af96b",
       "codex@openai-codex": "db52e28f4d9ded852ab3942cea316258ae4ef346",
   }
   by_content = {"context-mode@context-mode": "mksglu/context-mode"}  # default-branch install, no ref

   def same_content(repo, base, head):
       """GitHub's compare API reports head ahead of base with stats.json as the only changed file."""
       if not re.fullmatch(r"[0-9a-f]{40}", str(head)):
           return False
       result = subprocess.run(["gh", "api", f"repos/{repo}/compare/{base}...{head}",
                                "--jq", "{status, files: [.files[].filename]}"], capture_output=True, text=True)
       try:
           return result.returncode == 0 and json.loads(result.stdout) == {"status": "ahead", "files": ["stats.json"]}
       except ValueError:
           return False

   config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or pathlib.Path.home() / ".claude")
   registry = json.loads((config / "plugins/installed_plugins.json").read_text())
   for key, sha in reviewed.items():
       found = [entry.get("gitCommitSha") for entry in registry.get("plugins", {}).get(key, [])]
       if found and set(found) == {sha}:
           print("ok", key, found)
       elif key in by_content and len(set(found)) == 1 and same_content(by_content[key], sha, found[0]):
           print("ok", key, found, "(ahead of the reviewed revision in stats.json only)")
       else:
           print("MISMATCH", key, found or "not installed")
   EOF
   ```
   Record each installed `gitCommitSha` in the step 7 receipt, with the
   recipe's revision beside it when they differ. A `MISMATCH` means this host
   runs a plugin revision the catalog has not reviewed, or the compare could
   not run: review it before relying on the plugin.

5. **Services.** Start only the selected profile's services using the native
   process-lifecycle guide in [`adoption/lifecycle.md`](lifecycle.md#native-client-integration-and-process-lifecycle):
   `systemctl --user` on Linux/WSL2 (owned units only; never stop the shared
   MCPorter daemon to "clean up" another component), `launchctl` on macOS
   (table in [the macOS page](platforms/macos-arm64.md#launchd-services); run
   only on a hosted runner, not yet on a Mac workstation). For the portable guarded runner wrappers used by
   these services, see `adoption/tools/README.md`.

6. **Prerequisite report.** `uv run --no-project --python 3.13 python scripts/adoption_status.py --profile <id> --json`
   (changed after `v2026.09.23.1`, whose step 6 runs plain `python3`: the manifest
   supports Python 3.13 only, so a `python3` that is 3.12, as on Ubuntu 24.04,
   reports `prerequisites_missing` and exits 2; on a checkout of that release, run
   this form instead) reports command presence and recipe-path presence only; it never logs in,
   edits configuration, starts services, or certifies functional acceptance
   (see its own docstring and `adoption/README.md`'s "Native verification
   tiers" table).

   `--login-shell` adds the static check of `~/.bash_profile`, `~/.bash_login` and `~/.profile`
   (file metadata only; none is opened or run). Where `claude` resolves in a login shell is known only
   by running one, so that report carries `"launcher_resolution": {"status": "not_run", "flag":
   "--launcher-resolution"}`. `--launcher-resolution` (added after `v2026.09.26.2`) runs one bounded
   Bash login shell from a fixed environment, never `claude` itself, and reports the resolved path,
   whether it is the ecosystem launcher `$ECO_INSTALL_ROOT/bin/claude` and that launcher's sha256
   ([WSL page](platforms/linux-wsl2.md#windows-terminal-profiles-and-the-login-shell)); the
   `login-shell` step of `--configure-full-profile` passes both flags.

7. **Per-host receipt.** Record `evidence/receipts/adoption-<host>-<date>.json`
   using the [`adoption/receipt.json`](receipt.json) schema: `schema_version`,
   `id`, `kind`, `component_ids`, `observed_at_utc`, `status`, `claim`, `scope`,
   `data`. Distinguish `native_cli_e2e` (an actual command ran on this host)
   from `source_review` (documented, not executed) and from a candidate that
   has neither. `scripts/host_receipts.py` (this same step's own recording
   tool, plus `scripts/component_matrix.py`, `scripts/new_host_grand_list.py`,
   `tools/sota-convergence/build_verdicts.py`,
   `scripts/validate_convergence.py` and `scripts/release_due.py`) needs
   **Python 3.9 or newer**: every one of those scripts parses under the
   Python 3.9 grammar and uses `from __future__ import annotations`, and this
   is exercised directly, not merely declared -- a macOS CI job runs the
   recording smoke below against both the manifest-pinned Python line and the
   host's own system `/usr/bin/python3` (macOS ships 3.9.6 there by default,
   the same floor this bullet declares; see
   [the macOS page](platforms/macos-arm64.md#recording-and-verdict-scripts)).
   Linux/WSL2 hosts use the manifest-pinned line (`python@3.13` on macOS,
   already required by step 1's prerequisites); this floor exists so a host
   that has not yet installed the pinned line -- or one recording a receipt
   with only the OS-bundled interpreter -- still has a working
   `host_receipts.py`.

Every step above is guidance; running or validating this page does not itself
execute anything (`adoption/lifecycle.md`, "This guide supplies future-host
commands; reading or validating it does not run those commands").

## New repositories

Added after `v2026.09.26.2`: `tools/adoption/scaffold_repo.py`, `adoption/scaffold/` and
`.github/workflows/sota-sources-gate.yml`. Every new repository starts from the scaffold
instead of hand copies, so it carries the standing rule from its first commit:

```sh
python3 tools/adoption/scaffold_repo.py --target <repo> --dry-run   # the plan; writes nothing, even before git init
git init <repo>
python3 tools/adoption/scaffold_repo.py --target <repo>             # writes it; <repo> must exist
```

| File in the new repository | From |
| --- | --- |
| `AGENTS.md` | `adoption/scaffold/AGENTS.md`: the top rule, byte for byte the block after the `native-agent-stack:top-rule` marker of `adoption/templates/codex.AGENTS.template.md` (a test binds the two), and a repository-expectations section to fill in |
| `CLAUDE.md` | `@AGENTS.md` and one comment line: Claude Code reads the shared file through the import ([memory docs](https://code.claude.com/docs/en/memory), "Share one file with other coding tools") |
| `.agents/skills/README.md` | where skills only this repository needs go; skills every repository uses stay global (`adoption/skills/manifest.json`) |
| `.github/pull_request_template.md` | scope, lane, `## SOTA sources` and the evidence classes of this repository's own template |
| `.github/workflows/sota-sources.yml` | `sota-sources.yml.template` with `<sha>` filled in: it calls this repository's reusable `sota-sources-gate.yml` at that main commit |
| `.codex/config.toml` | `adoption/templates/project.codex.config.template.toml`, rendered for this host |

The gate is `validate.yml`'s required `sota-sources` job made reusable (`on: workflow_call`), the same
check byte for byte (`tests/test_sota_sources_gate.py`); a called workflow runs in its caller's
context, so it reads the new repository's pull request
([reusing workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations),
"`github` context"). `<sha>` is `--main-sha`, else what `git ls-remote origin refs/heads/main` reports;
when that commit is in this checkout it must carry `.github/workflows/sota-sources-gate.yml`, or nothing
is written (exit 2), and a commit this checkout lacks is used as given and reported unchecked. GitHub
resolves the reusable workflow when the check runs, so the new repository's check works only once that
commit, pushed to this repository on GitHub, carries the gate file. The caller is kept as a `.template` file because zizmor also audits nested
`.github/workflows` directories, where an unfilled `<sha>` is an unpinned `uses:`. In the new repository,
make the check the workflow reports a required status check, and if its Actions settings allow only
selected actions, allow this reusable workflow and `step-security/harden-runner`, which it runs
(`actions/github-script` is GitHub-owned).

`.codex/config.toml` takes `ECO_ROOT` from `ECO_INSTALL_ROOT` (default `~/.local/share/codex-ecosystem`),
`CODE_INDEX_PATH` from its variable (default `~/.code-index`) and `HOST_PATH` from
`adoption/hosts/example.json`'s system directories, never this shell's `PATH`; `--host <name>` reads
`adoption/hosts/<name>.json` instead and `--set KEY=VALUE` overrides one value. It holds this host's
paths, so each host renders its own. Each file is created when absent and left alone when identical; one
whose content differs is skipped and the run exits 3 unless `--force <path>` names it (the path as the
table prints it, repeatable; no backup is kept, so commit first). Only the named files are overwritten:
every other file that differs is still skipped, a bare `--force` or a path outside the scaffold is a usage
error (exit 2), and a symlink is never written through. `--dry-run` also plans a `--target` that does
not exist yet; a real run refuses one. The tool prints one line per file (`created`, `unchanged`,
`skipped`, `overwritten`) and a summary; [update](update.md#start-a-new-repository) has the recipe
that moves an existing repository's workflow to a newer gate.
