# Decision: the new distribution's Claude Code and Codex configuration comes from the definitive manifest (2026-10-02)

**Decided by:** the isolated builder of the client-configuration contract of 2026-10-02, on branch
`foundation/new-wsl-client-config-20261002`, for the coordinator, who integrates it. The coordinator's second-round
instruction of the same day changed the order of F9, the host template's ports, the two instruction blocks and the two
Codex role carriers, and let the builder edit the files that carried F9's old text; the third round replaced the refusal
of an existing Codex `config.toml` by a merge, kept a person's theme, declared one dependent sentence and asked where the
guard runs for Codex. The fourth round, after the cross-family review of the pull request, made the four authorization
settings opt-in, put the running-Codex refusal before both writes of `config.toml`, corrected F9's sentence about the
instruction blocks and moved the scan of the rendered files into `--check`. The fifth round, after the first hosted macOS
run of the new tests, made the two that assumed Linux portable (the display width of a conflicting value, and the reading of
a process's command line). The sixth, the last repair round, answers an independent read of the fourth and fifth: it
corrected F9's sentence about the instruction blocks again (the filter's names come from the map and from the manifest rows
that install nothing, so a unit that names a skill is still left out when it also names such a tool), told every outcome of
the line `--apply` prints about the authorization settings apart in the code and the documents (adding `partly applied`, and
a skipped step from a failed one), put the tool approval modes of an MCP server into the authorization class, made a
`pgrep` that fails stop the Codex `config.toml` step, and fixed the strings and the records that lagged the code. This
record states the result of the six rounds. Every web page named below was read on 2026-10-02.

**Scope:** `tools/adoption/new_wsl_client_config.py`, `adoption/new-wsl/client-config-map.json`, the two generated blocks
`adoption/new-wsl/claude-user-instructions.md` and `adoption/new-wsl/codex-user-instructions.md`, and
`tests/test_new_wsl_client_config.py` (all new); this record; F7 to F9 and F11 of
[`adoption/platforms/linux-wsl2-new-distro.md`](../../adoption/platforms/linux-wsl2-new-distro.md) and its placeholder
table; the ports of `adoption/templates/wsl/host.new-distro.json.template`; the command table and a dated section of
[`2026-10-01-new-wsl-distro-recipe.md`](2026-10-01-new-wsl-distro-recipe.md); the F8 and F9 rows and the `authorization_settings`
field of `adoption/templates/wsl/stage1-receipt.example.json`; the F9 line of `adoption/templates/wsl/first-boot-checklist.md`;
`tests/test_wsl_new_distro_recipe.py`; and options added to two existing tools, each with its default unchanged:
`--hook`, `--agent` and `--mcp-template` in `tools/adoption/install_claude_profile.py`, and `profile-path --extra-dir`
and `codex-md --template` in `tools/adoption/managed_block.py`. Not touched: `manifests/evidence.json`, the generated
handbook, any convergence record, and every step of the recipe except F7 to F9 and F11.

## Decision

1. **The rule.** A client is wired to a tool only if the
   [definitive manifest](../../evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json) installs
   that tool, or if the piece is repository practice that needs no tool outside the repository. A manifest row installs
   by the install plan's own rule (`check_plan.py` L149-160 in
   [`evidence/artifacts/new-wsl-install-plan-20261002/`](../../evidence/artifacts/new-wsl-install-plan-20261002/README.md)):
   it names a default, installs something extra, is not split and is not resolved as not installed. A slot that is split,
   waits for a measurement or is resolved as not installed wires nothing. What the old workstation has decides nothing.
2. **A map of every piece.** `adoption/new-wsl/client-config-map.json` names each piece of the client templates and gives
   it one wiring: `slot:<manifest slot>` with the owner the entry means, `practice`, `not_wired:<reason>` or
   `authorization:<reason>` (Decision 14). The pieces
   are each hook entry, plugin, marketplace, permission rule, variable and setting of the Claude settings template and the
   WSL overlay; each server of `adoption/mcp/claude-user.json`; each hook file and project agent that
   `install_claude_profile.py` copies; each key of the three Codex TOML templates, the Codex hooks template and the two
   role carriers; the new distribution's additions to the Claude settings, the Claude user MCP servers and the Codex user
   config (`adoption/new-wsl/templates/`, the 2026-10-03 addendum); the two instruction blocks; and six steps of the tool
   itself (the launcher, the login-shell PATH block, the skills step, the two PATH directories and the remote plugin
   rules). A piece goes to the first entry that matches it. A piece no entry
   matches, and an entry no piece reaches, fail the check. Today: 397 pieces, 357 wired (207 practice, 150 through a slot),
   24 not wired (0 through a slot that does not install, 24 by their own entry) and 16 authorization pieces (the five
   settings, the main checkout's Codex trust grant of the 2026-10-04 addendum, the seven tool approval modes of Decision 14
   and semble's two allow rules, which also wait for their slots),
   each listed below; a slot whose install is another owner (an interim install, the 2026-10-03 addendum) counts as one
   that does not install the piece's owner. On 2026-10-04 the counts moved from 385 pieces, 293 wired and 93 through a
   slot because #674 adds Serena's `required = true` key to the stack-worker profile, a piece the serena slot wires.
   On 2026-10-04 the counts moved again because #687 adds the `gpt-6.1-sol` notice key under
   `tui.model_availability_nux`, a piece that is not wired.
3. **A piece follows its slot.** A piece mapped to a slot that does not install is not wired; it is wired when the manifest
   says the slot installs the owner its entry names. So the memory slot, once its head-to-head returns with ai-memory,
   wires the ai-memory pieces, and brings back the sentences of the instruction blocks that name it, without an edit to the
   map (a test changes the manifest and shows it); a slot that installs a different owner (the code-search slot
   installing semble) leaves the SocratiCode pieces out. `--check` reports a slot id the manifest lacks as an error and a
   slot that installs another owner as a warning.
4. **The tool**, `tools/adoption/new_wsl_client_config.py`: `--check` reads the manifest, the map, the templates and the
   plan, prints one line per piece and fails on an unmapped piece, an entry that matches nothing, an unknown slot, a
   practice piece that runs a tool outside the repository, a wired hook whose file is not a wired hook file, a name the
   map lists that no text holds, a port that the plan states twice with two answers, a committed instruction block that
   is stale or missing, an authorization setting classed practice or slot, or a file of the example host's render, made
   without and with the authorization settings, that names a tool that is not wired (the scan is the tool's `name_hits`,
   which the tests call too, with the names the tests derive on their own). It prints the authorization settings apart.
   `--render --host NAME --out DIR [--with-authorization-settings]` writes `settings.json`, the WSL overlay, `mcp-servers.json`,
   `codex.config.toml`, `codex.hooks.json`, the two Codex profiles and the two instruction blocks with wired pieces only,
   filling placeholders through `render_config.render_one`. `--write-blocks` writes the two filtered blocks, and
   `--dropped` prints every unit the filter left out, in full. `--apply --host NAME` puts the render in place in eleven
   steps, each its own repository tool, each skippable with `--skip`, and each reported as applied, current, planned, left
   out, skipped, failed, verified or, for a Codex `config.toml` that exists, `merged with conflicts kept` (Decision 11); a
   line before the summary says whether the authorization settings were applied, kept or left to the clients' own
   defaults. It installs no tool and no pinned client, backs up what it changes, and a second run changes nothing. `--dry-run` runs no
   client and writes nothing.
5. **F9** now runs, from the clone:

   ```sh
   cd ~/code/native-agent-stack
   bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh
   bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh
   python3 -B tools/adoption/new_wsl_client_config.py --check
   python3 -B tools/adoption/new_wsl_client_config.py --apply --host '<host>'
   ```

   then, by hand, `codex login` and `claude`, then `accept.sh --only <slot> --stage after_sign_in` for the six owners
   whose plan row has that stage (`codex`, `claude-agent-sdk`, `codex-sdk-and-codex-exec-app-server`,
   `local-model-server`, `agent-runtime-worker`, `research-harnesses`). **The configuration comes before the sign-ins**,
   as the coordinator decided, so that the guard hooks are active in the first session a person starts. (The first reason
   given for the order, that `codex_home.py` never rewrites an existing `config.toml`, was incomplete: the install plan
   leaves one in either order, see Decision 11.) **No step of `--apply` needs a signed-in client.** Checked with the real
   clients, not the stubs, in temporary homes that held no credential file: Claude Code 2.1.287 ran `mcp add` and `mcp get`
   and every step applied; the one Codex call, `codex features disable daemon_auto_start` for an existing `config.toml`
   that lacks the key, exited 0 and wrote it; no credential file existed before or after. On an empty Codex home `--apply`
   starts Codex not at all, because the render carries the key; on the destination it starts it once, for that key,
   because the plan leaves a `config.toml` without it (`test_apply_runs_no_client_subcommand_that_needs_a_signed_in_client`
   and the Codex merge tests record the stubs' calls). The command block keeps the plain `--apply`: it writes no
   authorization setting, and the prose after the block names the option for a host whose owner asked (Decision 14).
6. **One port truth.** The render takes the collector's OTLP/HTTP port (21318) from the plan's `config/otel.yaml` and the
   gateway's port (21128) from `install-plan.json`, and refuses a plan whose two statements of a port differ (the
   collector's in `otel.yaml` and in the plan row, the gateway's in the plan row and in `config/omniroute.env.example`).
   The Claude settings endpoint, both Codex OTLP exporters and the `omniroute` profile's `base_url` carry those ports; the
   workstation's literals (14318, 24318, 20128) do not appear in the render. The host template now agrees: its
   `OTEL_ENDPOINT` is `127.0.0.1:21318` and its `QDRANT_URL` `127.0.0.1:21633`, F8's `ss` probe checks `21318`, `29374`,
   `21633` and `28231`, and F8 excludes the workstation's own collector and Qdrant ports, `24318` and `26333` (observed
   listening 2026-10-02, when the first real run of the recipe failed F8's proof on them). A test in
   `tests/test_wsl_new_distro_recipe.py` reads the plan's `otel.yaml` and requires the template's collector port to equal
   its OTLP/HTTP port and the template's other ports to be neither the plan's nor the workstation's; another renders the
   template's `OTEL_ENDPOINT` and the settings from one run and requires both to carry the same port.
7. **The max-effort launcher.** The launcher is the text of `install_native` in `adoption/bootstrap-linux.sh`, cut out of
   the script and run in a scratch directory beside a stub client with a version floor of 0.0.0, so it keeps the client
   it finds and its download branch is never reached (the stub `fetch` fails if anything asks). The tool writes the
   result to the `bin` directory of the host file's `ECO_ROOT`, with a backup of a differing file. It is not written to
   `~/.local/bin/claude`: the text ends in `exec "$HOME/.local/bin/claude" "$@"`, so there it would run itself, and
   `install_native` refuses that placement for the same reason (`adoption/bootstrap-linux.sh` L470-475).
   [Claude Code's setup page](https://code.claude.com/docs/en/setup) (L205-209) says that auto-update leaves a custom
   launcher at `~/.local/bin/claude` in place and that `claude doctor` reports one the installer did not create; neither
   applies to a launcher in another directory.
8. **PATH for a login shell.** `managed_block.py profile-path` gains `--extra-dir`. The block puts the ecosystem's `bin`
   first, then `~/.local/bin` (Claude Code's and Codex's native installers, `uv tool install`, the release binaries) and
   mise's shims directory (`~/.local/share/mise/shims`), each added only if it is not on PATH yet, in `~/.profile`
   between the markers. The plan prescribes no shell change and installs its npm tools through mise's Node, whose
   `npm` wrapper reshims after `npm install -g` by default at the commit the plan cites. The same directories lead the
   `PATH` of the Claude settings and of the Codex config, because both replace the session's PATH.
9. **The instruction blocks are filtered, never rewritten.** Each block of the repository (`examples/claude-native/CLAUDE.md`,
   `adoption/templates/codex.AGENTS.template.md`) goes through one filter, and the result is committed as
   `adoption/new-wsl/claude-user-instructions.md` and `adoption/new-wsl/codex-user-instructions.md`; `--apply` installs
   those through `managed_block.py` (`claude-md --example`, `codex-md --template`), which keeps every line outside its
   markers. The filter takes the names of every tool that is not wired (the names the map lists for unwired pieces, and
   the former defaults of the manifest rows that install nothing) and leaves out: a single-line bullet whose first sentence
   names one (the bullet would lose its marker) or whose every sentence does; any other sentence of a single-line
   paragraph or bullet that names one; a paragraph or bullet wrapped over several lines that names one, whole (a sentence
   cannot leave wrapped lines without cutting a line); a heading or comment line that names one; and then each heading
   with nothing kept under it. It writes no new text. Every other line is kept byte for byte, a line that loses a
   sentence keeps the others word for word, and a numbered item that goes leaves the other numbers as the source has
   them. Tests: the committed files equal what the filter makes of the
   sources, the map and the manifest (`--check` fails on a stale or missing file, and `--apply` refuses); every kept line
   is in the source verbatim (a whole line, or whole sentences of one in order); no name of an unwired tool, derived
   again independently of the tool, remains in either file; the kept and the dropped text together are the whole source
   (a word count); and each dropped unit names a tool, or is a heading left with nothing. **The units left out are listed
   in full at the end of this record, and `new_wsl_client_config.py --check --dropped` prints them.** Two things the list
   shows. The filter is by name, so a sentence that names a wired tool beside an unwired one goes too: the Codex "Token
   lanes" sentence names `serena` and `qmd` (wired) with `socraticode`, `codebase-memory`, `ai-memory`, `context-mode` and
   `headroom`, and the Promptfoo bullet also names Harbor, Inspect and `skill-creator`. And a sentence that only made
   sense with the one before it goes with it, when the map declares that (`dependent_sentences`, never inferred): `Check
   relevance; retry without pin priority or widen if needed...` refines the ai-memory query before it, so it is dropped in
   both blocks and listed with its reason; a test shows it stays where the sentence before it stays, and that it comes
   back with the ai-memory sentence when the memory slot installs. F9's sentence about what the blocks lose, which a
   test holds against the dropped list below, reads: a unit is left out when it names a tool that is not wired, which is a name the map lists for an unwired piece or the former default of a manifest row that installs nothing; a unit is not left out merely for naming a skill or timer that neither lists, and whether those skills exist on the host is not established by this step. The Promptfoo unit shows why the second source is named: no map
   entry lists Promptfoo, it is the former default of the manifest row `promptfoo`, and its unit (line 17 of the Claude
   source, line 11 of the Codex source) also names `skill-creator` and is left out of both blocks. The units that stay and
   name a skill or a timer name no tool that is not wired; they are the skills `search-first`, `find-skills` and
   `skill-creator` (line 5 of the Claude file, line 10 of the Codex file) and the "daily currency timer" (line 30 of the
   Claude file, line 15 of the Codex file). The plan installs six skills for both clients (`install.sh` L180: `tdd`,
   `diagnosing-bugs`, `codebase-design`, `domain-modeling`, `writing-for-agents`, `setup-matt-pocock-skills`) and adds the
   Trail of Bits marketplace to each client without installing a plugin from it (L171 and L173), so the plan installs none
   of the three on either client. `skill-creator` differs by client. **Codex:** the source at `rust-v0.160.0` (commit
   `a956835d020762cb2b570053af06f643a11c0ecc`, the plan's Codex release; read 2026-10-02) embeds a directory of sample
   skills and installs it under `CODEX_HOME/skills/.system`: `codex-rs/skills/src/lib.rs` L55,
   `include_dir!("$CARGO_MANIFEST_DIR/src/assets/samples")`, L57 and L62-67 (the `.system` directory name and
   `system_cache_root_dir`) and L69-101 (`install_system_skills`: its doc comment, L69, reads "Installs embedded system
   skills into `CODEX_HOME/skills/.system`", and L97 writes the embedded directory there), and the directory
   `codex-rs/skills/src/assets/samples/` at that commit holds `imagegen`, `openai-docs`, `review-agent`, `skill-creator`
   and `skill-installer`. That is source evidence, not activation on the host: no Codex 0.160.0 ran here, and the
   repository's own note (`adoption/skills/lifecycle.md` L132 and L168-170) records the same bundled skill for
   `rust-v0.159.2`. **Claude Code:** its skills page (`https://code.claude.com/docs/en/skills.md`, read 2026-10-02)
   documents `skill-creator` as a plugin, installed with `/plugin install skill-creator@claude-plugins-official`
   (L900-906), apart from its bundled skills (L21-35), and the commands reference
   (`https://code.claude.com/docs/en/commands.md`, read 2026-10-02) marks 20 rows as bundled skills, none of them
   `skill-creator` (the name appears nowhere on that page). The plan installs no plugin (`install.sh` L171 adds a
   marketplace and L180 installs the six skills), so nothing the plan does provides a `skill-creator` for Claude Code. That
   is read from the plan and those two pages: no destination host was built here, so it is not observed. The settings
   template's `"skill-creator": "on"` (`adoption/templates/claude.settings.template.json` L417) then names a skill the plan
   does not provide; the
   settings reference (read 2026-10-02) describes `skillOverrides` as hiding or collapsing a skill and says nothing of a
   name with no skill. The repository's own Claude-side record is a pinned trial copy of `anthropics/skills`
   (`adoption/skills/manifest.json` L720-744), which the plan does not install.
10. **The two Codex role carriers are not wired.** `adoption/agents/codex/stack-researcher.toml` and
    `stack-verifier.toml` name context-mode, ai-memory and qmd tools and carry the RTK block. They are byte-pinned in
    `adoption/agents/codex/SHA256SUMS` and ruled by `tools/adoption/codex_roles.py`. The filter was run on each carrier's
    `developer_instructions` (`CarrierTests`): it leaves out 29 and 26 units, among them each carrier's own working-rule
    bullets (large output, exact command shapes, and for the verifier its acceptance commands), and the filtered text
    fails three of the repository's own rules for the carrier (`cwd_rule`, `exact_shapes` and `f4_block`, which require
    the context-mode working-directory bullet, the exact-command-shapes bullet and the RTK block) and no longer matches
    its hash. A carrier could be installed only whole, with the tools it names missing, so the map leaves both out
    (`not_wired`, one entry), and `~/.codex/agents` is not created.
11. **An existing Codex `config.toml` is merged, never rewritten.** The install plan itself leaves one: its line
    `codex plugin marketplace add trailofbits/skills --ref <commit>` (row `trail-of-bits-security-skills-trailofbits-skills`
    of `install-plan.json`, `install.sh` L173) writes `[marketplaces.trailofbits]`. On the destination, after the plan and
    the sign-ins, the file is 192 bytes with that table (`source_type`, `source`, `ref`) and `[tui]` with
    `screen_reader_detection_done`; the tests rebuild that file from the plan's own command and it is exactly 192 bytes.
    With a `config.toml` present, the `codex-config` step merges: every key and table the file has stays as it is; each
    top-level key and each table the render has and the file lacks is added; where a table exists on both sides only the
    missing keys are added (`[tui]` gains `notifications`); a value that differs stays as the file has it, is printed
    beside the render's (a key whose name looks like a secret is hidden; each value is cut to 300 characters, the last three
    being `...`, in the display only and never in the file), and the step ends `merged with conflicts kept`
    with exit 0, again on every later run while the difference stays. The file is backed up first; the merge is a text edit
    that adds lines and changes none (a key goes after the last statement of its table, a missing table at the end, a line
    that looks like a table inside a multi-line string or array is not taken for one, an inline table or dotted keys that
    would need a new key are refused); the result is parsed before it is written and the file is read back with `tomllib`
    after, and put back from the original bytes, with the step failed, when it is not exactly the expected merge.
    The declared one-time [`service_tier` migration](2026-10-05-codex-service-tier-migration.md) changes only the previous
    managed `fast` to `default`; its completion marker preserves later `/fast` choices, and marker-only completion
    makes no config write, process check or backup.
    `features.daemon_auto_start` goes through Codex's own writer (`codex features disable daemon_auto_start`) when a
    `codex` binary is at hand, as `codex_home.py` does, and by the text edit when none is. A second `--apply` changes
    nothing and makes no second backup. The running-Codex refusal comes before either write of `config.toml`: while a process named
    `codex` runs (`--codex-process-name`), nothing is written and the step says `close the Codex sessions, then run
    --apply again` (naming the app-server daemon and `codex app-server daemon stop` when one runs). The running processes are `pgrep -x`'s
    finding (`running_codex_pids`, below); the daemon is found by reading
    the command line of each, from `/proc/<pid>/cmdline` where Linux has one (the arguments as passed, as before) and from
    `ps -ww -o command= -p <pid>` where there is none (macOS), whose words are the arguments joined by spaces, so an
    argument that holds a space is split, which does not matter for the word `app-server`. Neither reads the environment of
    a process, and a command line that cannot be read leaves only that hint out, never the refusal. It covers the merge of
    an existing file and the creation of an absent one; `codex_home.py`'s own creation of a missing file has no such check,
    so the tool makes it first and `codex_home.py` is unchanged for its other callers (the first rounds checked only the
    merge). A file that needs nothing is not held up by it. An empty Codex home still gets the render through
    `codex_home.py`, once the check has passed. A `pgrep` that cannot run, or that exits with a status other than 0 (matched)
    or 1 (none matched), is a failed check and not an empty list: `apply_codex_lane.codex_processes`, which this tool called
    until the sixth round, drops the status, so a failing `pgrep` read as no Codex running and switched the refusal off. The
    tool now makes the call itself (`running_codex_pids`), and any other status, or a `pgrep` that cannot be run, fails the
    `codex-config` step before anything is written, with the status in the message, in a dry run too; a file that needs
    nothing is still not held up. Both manuals document the statuses 0, 1, 2 and 3: procps-ng's `man/pgrep.1` (L294-311:
    matched, none, syntax error, fatal error) and Apple's `pkill.1`, which documents `pgrep` as well (L258-273: matched,
    none, invalid options, internal error), both read 2026-10-02.
    Evidence: unit tests (the destination's shape, a conflict, a trailing comment and no final newline, a comment-only
    file, look-alike lines, 80 seeded partial renders each completed to the whole and again to nothing, a failed writer, an
    unexpected writer result, a running Codex before the merge and before the creation of an absent file, a dry run, and a
    `pgrep` that fails: stand-ins that exit 2, 3 and by a signal, in both write paths, and one that cannot be run) and a
    run with the real Codex 0.159.3 in a temporary home with no
    credential: the destination's file merged, `codex mcp list` read the result and listed `qmd` and `serena`, the second run
    changed nothing.
12. **A Claude `settings.json` that exists keeps its keys, and the theme.** On the destination `~/.claude/settings.json`
    is 194 bytes with `extraKnownMarketplaces` (one entry, from the plan's `claude plugin marketplace add`) and `theme`;
    the test rebuilds that from the plan's command. `apply_claude_settings.py` merges by its own rule: keys the template
    does not mention stay, objects merge, lists union, and a scalar of the template wins. So the marketplace stays, and the
    wired settings are added, but the template's `theme` ("dark") would have replaced a person's choice. The map now marks
    that one piece `keep_existing`: the template's value is written only when the file has none, and the step says
    `kept your theme: "auto" (the render has "dark")` when they differ. The four authorization settings get the same treatment
    (Decision 14). Every other scalar of the template still wins, as
    before (a change from the first round: the theme of an existing file was replaced).
13. **Codex hooks and the secret-path guard.** (a) In this design the guard runs for Codex **nowhere**: not in user-level
    hooks, not in a project `.codex/hooks.json`, not in an exec-policy rule. `adoption/templates/codex.hooks.template.json`
    carries one SessionStart group, the currency notice, and says "a template only, not applied by any installer; B1
    applies no Codex hook" (L2); `docs/secret-storage.md` L185-187 says "K4's guard hook inspects the runner's started
    command in Claude's Bash tool. Codex, OmniRoute lanes and units do not automatically run this hook", and its guard
    table (L1610-1611) puts `secret_path_guard.py` under "project settings and, through the profile installer, user
    settings" of Claude, and gives Codex only `[shell_environment_policy] inherit = "none"`, which no template carries (a
    search of the three Codex templates finds no `inherit` key; `credential_status.py --client-guards` counts it); the
    repository tracks no `.codex/hooks.json` (the history of that path is empty) and no Codex rules file; and
    `docs/token-session-handbook.md` L372 and `recipes/README.md` L158 decline the one Codex PreToolUse hook on offer
    (`rtk init --global --codex`). So a Codex session has no guard hook inside the repository or outside it, and the
    secret-path hook of Claude's user settings is the only copy. (b) Whether the trust of a wired Codex hook can be
    rendered for a new host: **yes, for a hook whose definition is the same on every host.** At `rust-v0.160.0` the
    recorded `trusted_hash` is `version_for_toml` of a normalized identity of the hook, its event name, matcher and handler
    (`codex-rs/hooks/src/engine/discovery.rs` L766-792, `codex-rs/config/src/fingerprint.rs` L54-79: SHA-256 over canonical
    JSON with sorted keys), not of the file's path or the host; a hook is run only when its recorded hash equals the
    current one (`discovery.rs` L794-811 and L713-718). The key it is recorded under, `[hooks.state."<key>"]`, is
    `<source>:<event>:<group>:<handler>` (`codex-rs/hooks/src/lib.rs` L112-123) with the absolute path of the hooks file as
    `<source>` for a user or project file (`discovery.rs` L174 and L229), which is why the template's keys carry `${HOME}`,
    and `<plugin id>:<relative path>` for a plugin's hook (`codex-rs/hooks/src/declarations.rs` L35-37), which is host
    independent. Run with the installed Codex 0.159.3 in temporary homes (`app-server`, `hooks/list`): the same group in
    homes at three different paths gave the same `currentHash` (`sha256:f5bab0c6…`) and a key that differed only by the
    path; a changed timeout gave another hash; the same group as the second group kept its hash and became
    `…:session_start:1:0`; and a `trusted_hash` rendered from the first home's hash under the third home's own key made
    Codex report that hook `trusted`. So nothing stops a trust entry being rendered for a wired hook (new home path in the
    key, the hash of the definition as the value), but **no Codex hook is wired in this design**: the guard is not a Codex
    hook, the currency notice stays unwired (its timer is not installed), the ai-memory and context-mode hooks that the
    template's `[hooks.state]` entries approve belong to tools the manifest does not install, and the template's
    `${PROJECT_ROOT}/.codex/hooks.json:pre_tool_use:0:0` entry approves a hook file that the repository does not carry. Nothing
    is invented: `codex.hooks.json` renders empty and the `[hooks.state]` and `[projects]` entries stay unwired, and F9 says
    so in one sentence. A Codex-side guard would be a new decision (a hook in Codex's own protocol, and the repository's
    `secret_path_guard.py` reads Claude's), which this record does not take.
14. **The authorization settings are written only on request.** Four pieces grant a permission or suppress a confirmation:
    Claude Code's `permissions.defaultMode` (the template's `bypassPermissions`, which "runs everything without asking" (L1676);
    Claude Code settings reference, the section is L1665-1679) and `skipDangerousModePermissionPrompt` (skips the dialog before
    `bypassPermissions` mode; Claude Code writes it itself when the person accepts that dialog, same page L1726-1734), and
    Codex's `approval_policy` (`never`: "Never ask the user to approve commands", `codex-rs/core/config.schema.json` at
    `rust-v0.160.0`, definition `AskForApproval` from L307, the sentence at L331) and `sandbox_mode`
    (`danger-full-access`, definition `SandboxMode` L3963-3970). The first rounds wired them as practice, so `--apply`
    wrote them on a fresh host; the review of the pull request held that a tool must not do that by default. The sixth
    round added a second kind of piece to the class: Codex's tool approval modes. `default_tools_approval_mode = "approve"`
    stands in the templates of four MCP servers (`context-mode`, `ai-memory`, `socraticode`, `headroom`) and makes Codex run
    every tool of a server without asking; its values are `AppToolApproval` (`auto`, `prompt`, `writes`, `approve`, schema
    L210-218), the key is on `RawMcpServerConfig` (L3641) and the per-tool `approval_mode` on `McpServerToolConfig`
    (L2430), both read at `rust-v0.160.0`. The four servers' slots install nothing today, so nothing wrote the key, but a
    plain `--apply` would have written it, with no check, the day one of those slots installed, and likewise for a wired
    server such as `serena` whose template gained the key.
    - **The class.** Two map entries give the five their own wiring, `authorization:<reason>` (the fifth, `crossSessionInbound`,
      since the 2026-10-04 changelog-parity record, `docs/decisions/2026-10-04-new-wsl-changelog-parity.md`). The tool knows which pieces
      they are (`is_authorization_piece`: `AUTHORIZATION_PIECES`, any `permission/allow` rule, which would grant too, any
      `default_tools_approval_mode` whatever its value, and any `approval_mode` whose value is `approve`), so a map that
      classes one as practice or as a slot fails `--check`, and a map that classes another piece as authorization fails it
      too; a piece classed `not_wired` is allowed (it is never written, with or without the option). The deny list stays
      practice: it only restricts. An entry of this class may also name a `slot` and its `owner`, and the piece is then
      written only with the option and only while that slot installs the owner (`slot_verdict`, the rule of every slot
      piece): a bare `default_tools_approval_mode` would otherwise create half of a server's table for a server that is not
      wired. The tool approval modes and semble's allow rules have such entries and carry no `names` (a piece held back
      only by the option must not add its server's name to the tools that are not wired while the slot installs it).
      Since the wave-2 records (the 2026-10-03 addendum), the option writes the approval modes of ai-memory (in the user
      config and the stack-worker profile), semble and context-mode and semble's two allow rules, because their slots
      install those owners as interim installs; SocratiCode's and headroom's wait, because their slots install another
      owner. Since the 2026-10-04 addendum the option also writes the main checkout's Codex trust grant, and since the
      changelog-parity record Claude Code's `crossSessionInbound = "accept"`. Fifteen pieces
      are in the class (`--check` counts `authorization: 16`, and 24 pieces are not wired).
    - **The default.** `--render` and `--apply` neither render nor write the five, and an existing value of those keys in a
      person's files is never touched: the render lacks the keys, so the Claude merge leaves the file's keys as they are,
      and so does the Codex merge.
    - **The option.** `--with-authorization-settings`, on `--render` and `--apply`, renders and applies them. Even then an
      existing differing value is kept and printed with both values, for Claude as for Codex: the Claude step handles the
      four like the theme (written only when the file has no value for the key, the nested `permissions.defaultMode`
      included), and the Codex merge keeps a differing value as a conflict. The option adds a missing grant and never
      changes a person's choice.
    - **What is shown.** `--check` lists them apart, with the value the option would write (and, for a tool approval mode,
      the slot it also waits for), in its text, its JSON table (wiring `authorization`) and the generated tables of this
      record (the second table has a fifth column, `Also needs`); its counts line has a fourth number. `--apply` prints
      a line before the summary that starts `authorization settings:` and says `left to the clients' own defaults` when the option was not given and, when it was, `applied`, `partly applied`, `kept` or `not applied` (`would be applied` or `would be partly applied` in a dry run), followed by what it added, kept, found already the same and did not reach, a skipped step and a failed step told apart. The head word is one of seven: `left to the clients' own defaults` (the option was not given); with the option,
      `applied` (every wired setting was reached and one was added), `partly applied` (one was added and one was not
      reached), `kept` (every one was reached and none was added) and `not applied` (none was added and one was not
      reached, or none is wired), with `would be applied` and `would be partly applied` for a dry run. A setting is not
      reached when the step that would write it did not finish: the line says `its step codex-config was skipped` or `its
      step codex-config failed`, which are not the same thing. A test runs the seven and holds the code's list of them
      (`AUTHORIZATION_OUTCOMES`) against the recipe, this record, the receipt example and the tool's docstring.
    - **F9 and the receipt.** The command block keeps the plain `--apply`. Its prose says the operator adds the option only
      on a host whose owner asked for the repository's permission practice, and that the receipt's `authorization_settings`
      records who asked: a new field of the receipt example, with its checklist line and a test that pins all three. That is
      why the receipt matters: with the option the tool writes `skipDangerousModePermissionPrompt`, a value Claude Code
      itself writes when a person accepts its dialog, so the owner's request stands in for that acceptance.
    - **Tests.** The default render has none of the four keys, the option's render has all four and differs in nothing
      else; an existing `defaultMode` or `approval_policy` survives a default apply and one with the option, with both
      values printed; a file with one setting and not the other gets only the missing one; the map refuses an
      authorization piece classed practice or slot (for each of the eight); a wired server whose template gains an approving
      mode (`serena`, whose slot installs) is caught, and with the entry the key is the option's; a server whose slot
      installs (`ai-memory` in a scratch manifest) still has the key written only with the option, in the render and in a
      plain and an optioned `--apply`; and six deliberate breaks of the tool (the four
      wired by default, no check before the creation of an absent file, no scan in `--check`, Claude not keeping its value,
      the option ignored, the class refusal removed) each fail the tests.
    No other wired piece grants: a scan of the default render finds only the `permissions` object that holds the deny
    list, the overlay's `permission_prompt` bell matcher and Codex's `approval-requested` notification kind, and the wired
    Codex servers (`serena`, `qmd`) carry no `default_tools_approval_mode`.
15. **Project agents are installed as repository practice** (the contract's call). Six of the eleven name MCP tools of
    servers that are not wired, or skills the plan does not install; the second table below lists them. Nothing is
    installed to fill the gap and no agent file is edited.

## Alternatives not taken

- **`adoption/bootstrap-linux.sh --profile <id>` and `--configure-full-profile`.** Every profile of `adoption/manifest.json`
  names components the manifest does not install: `foundation-cpu` has `context-mode`, `rtk` and `ai-memory`;
  `token-efficiency` adds `repomix`, `headroom`, `toon` and `ccusage`; `semantic-rag` has `vllm`, `qdrant` and
  `socraticode`; the others name further tools. The profile's client pins would also sit beside the clients the plan
  installs with their native installers. `--configure-full-profile` then wires the whole old profile: the settings
  template's `rtk`, `ai-memory`, context-mode and token-lane hooks, the `context-mode`, `claude-hud` and `codex`
  plugins, the status line, and Codex entries for `context-mode` and `ai-memory`, and `apply_codex_lane.py` (its owned
  edits are the context-mode entry). The tool does not run it.
- **A new profile id in `adoption/manifest.json`.** It would copy the manifest's install decisions into a third file next
  to the manifest and the plan, with pins and platform fields to keep in step with both. The map derives the wiring from
  the manifest on every run instead.
- **`apply_codex_lane.py` as the Codex step.** Its configuration write is the `[mcp_servers.context-mode]` entry and the
  plugin's server switch, which this distribution does not wire. The tool uses the lane's create-only write and
  `codex_roles.py`'s source checks for the profiles, and `codex_home.py` for `config.toml`.
- **A launcher at `~/.local/bin/claude`.** See Decision 7.
- **Instruction blocks written for this distribution.** The coordinator's rule is to filter and not to rewrite, so that
  no sentence reaches a client that the repository's blocks do not hold.
- **Sign in first, then configure.** The first version of F9 did, with the tool last. The guard hooks would be missing
  from the first session; the Codex `config.toml` does not decide the order, since the plan leaves one either way.
- **A filtered role carrier.** See Decision 10.
- **Codex's own writer for every key.** `codex features enable|disable`, `codex mcp add` and `codex plugin marketplace add`
  each write some keys, but not the rest (`model`, `otel`, `shell_environment_policy.set`, the profiles), so the merge
  would still need a text edit; the one key `codex_home.py` already hands to Codex's writer, `features.daemon_auto_start`,
  stays with it. A round-trip TOML library (`tomlkit`) was not used: the tools under `tools/adoption/` are stdlib only,
  and the read-back proves the text edit.
- **Keeping the first round's behaviour for the theme.** The template's `dark` would replace a person's choice.
- **Authorization settings written by default, with a note.** What the first rounds did. Writing a grant is a decision of
  the host's owner, so the option decides, and the receipt records who asked.
- **A prompt at run time for the four.** The recipe is meant to be followed end to end without prompts, so a flag decides.
- **The tool approval modes in the class without their slot.** With the option the key would be written under
  `[mcp_servers.<id>]` for a server that is not wired, a table with no command, and Codex would read half a server. The
  entries name the slot and the owner, so the key waits for both the option and the server.
- **Editing `apply_codex_lane.codex_processes` to raise on a failing `pgrep`.** The instruction was to leave that file as it
  is, and its other callers keep the behavior they have; the tool makes the same call itself and checks the status.
- **Merging Codex trust state, or wiring a Codex hook, so that the first session asks nothing.** Decision 13: there is no
  Codex hook in the design to wire.

## What would overturn it

- A real run on the destination distribution in which `serena` or `qmd` does not resolve from the settings `PATH`, or in
  which a login shell does not find `claude`, `codex` or a mise tool after `--apply`: the PATH design would change.
- A real run in which a step of `--apply` fails because a client is not signed in: F9 would put the sign-ins first again.
- The memory head-to-head, the code-search measurement or the context-supply decision returning a default: the pieces
  of the slot's owner wire themselves and the blocks regain the sentences that name it; a different owner needs entries
  in the map.
- A measured gain from wiring a piece listed below as not wired (for example the context-mode pieces) that the manifest
  records: the manifest row changes first, then the tool follows.
- Claude Code or Codex changing how a user-scope MCP server, a settings `env.PATH` or a custom launcher is read.
- A change of `codex_roles.py` that lets a carrier be installed in a filtered form: Decision 10 would be taken again.
- A decision of the repository's owner that its permission practice is the default of every new distribution: the entry's
  class moves back to practice and `AUTHORIZATION_PIECES` changes with it.
- A real run on the destination in which the merge's read-back fails on a file Codex itself wrote (a layout the scanner
  misreads): the merge would move to Codex's writers for the keys that have one, or to a round-trip library.
- A Codex hook added to the templates (a guard in Codex's protocol): its trust entry can then be rendered (Decision 13).

## Evidence

Sources read (line numbers are those of the `.md` form of each page or file as fetched; the repository's own
implementation is the reference: `adoption/bootstrap.md` steps 2, 4 and 4a,
`adoption/bootstrap-linux.sh`'s `full_profile_*` functions and `install_native`, and the tools named in the scope):

- Claude Code, read 2026-10-02: [settings](https://code.claude.com/docs/en/settings) (L405: the user file is
  `~/.claude/settings.json`), [settings reference](https://code.claude.com/docs/en/settings-reference) (`env` L2873,
  `statusLine` L3523, `hooks` L4099, `skillOverrides` L4229, `enabledPlugins` L4620, `extraKnownMarketplaces` L4651),
  [hooks](https://code.claude.com/docs/en/hooks) (command hooks, `timeout` L426),
  [MCP](https://code.claude.com/docs/en/mcp) (L135 the `--` separator, L535 local scope is the default, L598-604 user
  scope is stored in `~/.claude.json`), [setup](https://code.claude.com/docs/en/setup) (L205-209 the launcher) and
  [environment variables](https://code.claude.com/docs/en/env-vars).
- Codex at tag `rust-v0.160.0` (the tag, not `main`): `docs/config.md` and `docs/example-config.md` are pointers to
  developers.openai.com (726 and 134 bytes), and `codex-rs/hooks/` holds `schema/` and `src/` with no prose, so the
  reference read is `codex-rs/core/config.schema.json`; `scripts/install/install.sh` L16 (the binary goes to
  `~/.local/bin`) and L597-630 (it edits a shell profile only when its directory is not on PATH, which the plan's
  `export PATH` prevents).
- Serena `v1.7.0`: `docs/02-usage/030_clients.md` L134 (Claude Code: `claude mcp add --scope user serena -- serena
  start-mcp-server --context claude-code --project-from-cwd`) and L308-313 (Codex: `command = "serena"`), and
  `src/serena/cli.py` L233-317 (every flag of the template's entry is an option of `start-mcp-server`).
- QMD `v2.8.3`: `README.md` L99-130 (`command` `qmd`, `args` `["mcp"]`) and `src/cli/qmd.ts` L3022, L3645 and L4739
  (`--index` is a global option read before the `mcp` command; the template's `--index native-agent-stack-catalog`
  is that option).
- uv 0.12.22 `docs/reference/storage.md` L87-96 and L160-164 (tool executables go to `$XDG_BIN_HOME`, else
  `$XDG_DATA_HOME/../bin`, else `~/.local/bin`); mise at the plan's commit `bc11f90c`: `docs/dev-tools/shims.md` L60-80
  and L242-254, `settings.toml` L2112-2115 (`node.npm_shim`, true by default); MCP Inspector 2.9.0
  `clients/web/server/web-server-config.ts` L530-542 (`MCP_AUTO_OPEN_ENABLED=false` never opens the browser).
- The install plan's own files (`install-plan.json`, `accept.sh` L12-30 and its `README.md` L30-36): the six rows whose
  acceptance has an `after_sign_in` stage, the `--only` and `--stage` options, and the stage's description (native-client
  diagnostics that need credentials and upstream model examples; the local model server needs no remote account).
- `tools/adoption/codex_home.py` (L181-211: the only place a Codex binary is run, `codex features disable
  daemon_auto_start`, only for an existing `config.toml` that lacks the key, and only when no Codex process runs) and
  `tools/adoption/managed_block.py` L104-179 (what the two block installs keep and refuse).
- Codex at tag `rust-v0.160.0`, fetched with `curl` from raw.githubusercontent.com on 2026-10-02 (the third round, hook
  trust): `codex-rs/hooks/src/engine/discovery.rs` (L174 and L229 `key_source` is the hooks file's path, L279-282 a plugin's
  `plugin_id:relative path`, L664-679 the hash, the key and the trust status of each handler, L713-718 only a trusted or
  managed handler runs, L766-811 `hook_hash` and `hook_trust_status`), `codex-rs/hooks/src/lib.rs` L95-110 and L112-123
  (`hook_event_key_label`, `hook_key`), `codex-rs/hooks/src/declarations.rs` L35-37, `codex-rs/config/src/fingerprint.rs`
  L54-79 (`version_for_toml`, `canonical_json`) and `codex-rs/core/config.schema.json` L2125-2135 (`HookStateToml`:
  `enabled`, `trusted_hash`).
- Repository files read for the same question: `adoption/templates/codex.hooks.template.json`;
  `adoption/templates/codex.config.template.toml` L144-200 (the `[projects]` grants and the `[hooks.state]` approvals of
  the source host); `docs/secret-storage.md` L185-187, L1610-1611 and L2014-2056; `docs/token-session-handbook.md` L372;
  `recipes/README.md` L158; `adoption/bootstrap.md` L366-385 (the trust-state warning); and for the files the plan leaves,
  `install.sh` L171-173 and the row `trail-of-bits-security-skills-trailofbits-skills` of `install-plan.json`.

- For the fourth round (read 2026-10-02): the Claude Code settings reference, `permissions.defaultMode` (L1665-1679) and
  `skipDangerousModePermissionPrompt` (L1726-1734); the Claude Code skills page (`https://code.claude.com/docs/en/skills.md`),
  the bundled skills (L21-35) and the `skill-creator` plugin (L900-906); the commands reference
  (`https://code.claude.com/docs/en/commands.md`, 20 rows marked as bundled skills, none `skill-creator`); the Codex config
  schema at `rust-v0.160.0`
  (`AskForApproval` from L307, its `never` sentence L331, `SandboxMode` L3963-3970); and, at commit
  `a956835d020762cb2b570053af06f643a11c0ecc` (the commit `rust-v0.160.0` points to, checked through the GitHub tag and commit
  endpoints), `codex-rs/skills/src/lib.rs` L55, L57, L62-67 and L69-101 and the listing of
  `codex-rs/skills/src/assets/samples/` from the contents API.

- For the fifth round (read 2026-10-02): the source of Apple's `ps(1)` manual,
  `https://raw.githubusercontent.com/apple-oss-distributions/adv_cmds/main/ps/ps.1` (L195-196 `-p`, L181-194 `-o` with
  empty headers writes no header line, L224-233 a repeated `-w` uses as many columns as necessary and an output that is not
  a terminal is never cut, L441-442 the keyword `command` is "command and arguments"), for the flags of the `ps` reading.
  It is documentation of the flags; no `ps` ran on macOS.

- For the sixth round (read 2026-10-02): the manuals of `pgrep`, procps-ng's
  `https://gitlab.com/procps-ng/procps/-/raw/master/man/pgrep.1` (L294-311, the exit statuses) and Apple's
  `https://raw.githubusercontent.com/apple-oss-distributions/adv_cmds/main/pkill/pkill.1` (L258-273); the Codex config
  schema at `rust-v0.160.0`, `AppToolApproval` L210-218, `default_tools_approval_mode` on `RawMcpServerConfig` L3641 (also
  `AppConfig` L129, `AppLinkConfig` L192, `AppsDefaultConfig` L283, `PluginMcpServerConfig` L3505) and `approval_mode` on
  `McpServerToolConfig` L2430 (and `AppToolConfig` L223).

What I ran, by evidence class. Unchanged upstream tests and my own checks are different things:

- **Commands, run from the worktree with `nice -n 19` and a temporary directory under the scratch area** (exit code and last line of each):
  - `python3 -B -m unittest tests.test_new_wsl_client_config`: exit 0 (Ran 145 tests in 34.731s); last line `OK`
  - `python3 -B tools/adoption/new_wsl_client_config.py --check`: exit 0; last line `check passed`
  - `python3 -B tools/adoption/new_wsl_client_config.py --render --host example --out <temporary dir>`: exit 0; last line `wrote <temporary dir>/wiring.json`
  - `python3 -B tools/adoption/new_wsl_client_config.py --apply --host example --home <empty temporary dir> --dry-run`: exit 0; last line `summary: claude-hooks planned; claude-agents planned; claude-mcp planned; claude-settings planned; claude-launcher planned; claude-md planned; codex-c`
  - `python3 -B -m unittest tests.test_adoption_docs_consistency tests.test_install_claude_profile tests.test_render_config tests.test_wsl_new_distro_recipe`: exit 0 (Ran 253 tests in 14.579s); last line `OK (skipped=5)`
  - `python3 -B scripts/validate.py`: exit 1; last line `tests/test_wsl_new_distro_recipe.py: byte count mismatch`

  `scripts/validate.py` printed `Publication validation failed:` and 8 more lines, each a SHA-256 or byte-count mismatch,
  for the 4 registered files that the sixth round changed: `adoption/platforms/linux-wsl2-new-distro.md`,
  `adoption/templates/wsl/stage1-receipt.example.json`, `docs/decisions/2026-10-01-new-wsl-distro-recipe.md`,
  `tests/test_wsl_new_distro_recipe.py`, and nothing else. The coordinator registers the new hashes.

- **Real client binaries against a temporary home** (a fresh directory as `HOME`; the native Claude Code 2.1.287 and the
  workstation's Codex 0.159.x, not the 0.160.0 of the plan). `install_claude_profile.py --only mcp` registered `serena` and
  `qmd` through `claude mcp add --scope user`, and `claude mcp get` printed each back with its bare command. In the
  default environment the client behaved as if it launched the stdio servers with the `env.PATH` of the rendered
  `settings.json`: `serena`, which exists nowhere in the temporary home, printed `ENOENT: Executable not found in $PATH`,
  and `qmd`, a stub that exits at once, placed only in the temporary home's mise shims directory, was found and started
  and printed `CONNECTION_CLOSED`. With `CLAUDE_CONFIG_DIR` set to an empty string the outcome was the shell's own PATH:
  both printed `Connected`, answered by copies installed on this workstation whose versions were not read. So the runs
  show how the command is resolved; they do not show that Serena 1.7.0 or QMD 2.8.3 start. Codex, run with `CODEX_HOME`
  in the temporary home, printed `qmd` and `serena` as `enabled` in `codex mcp list` from the rendered `config.toml`.
- **`--apply` with the real clients and no credential** (the second round). A full `--apply --host example --home <empty
  temporary home>` with the native Claude Code and a Codex binary: every step applied (hooks, agents, `mcp add` of the two
  servers, settings, launcher, both instruction blocks, the two Codex profiles, the PATH block) and `verify` resolved
  `claude` to the launcher (the other tools are not installed in a bare home, and it said so); `codex-config` was refused
  on this workstation because two Codex processes run here, which is the guard of `codex_home.py` and not a need for a
  sign-in; no `auth.json` or `.credentials.json` existed before or after. The Codex path that does run the binary was run separately with that guard's process name pointed at
  nothing: `codex features disable daemon_auto_start` exited 0, wrote the key and one backup, and no credential file
  appeared.
- **The Codex merge with the real binary** (the third round; Codex 0.159.3, a temporary home with no credential): a
  `config.toml` rebuilt from the plan's `codex plugin marketplace add` line, 192 bytes, then `--apply` with only the
  `codex-config` step. The first run added seven tables, six top-level keys and `tui.notifications`, took one backup, and
  `features.daemon_auto_start = false` came from `codex features disable daemon_auto_start` (Codex's own writer, exit 0);
  the second run printed `current` and changed nothing; `codex mcp list` read the file and listed `qmd` and `serena` as
  `enabled`; no credential file existed. The guard of a running Codex was exercised against this workstation's real process list: with its three `codex`
  processes the same run stopped at the step with `close the Codex sessions, then run `--apply` again`, wrote nothing and
  made no backup (the unit tests start a `sleep` and name it).
- **Both merges and every other step together, with the real clients** (the third round; Claude Code 2.1.287 and Codex
  0.159.3, one temporary home with no credential, seeded with the destination's two files rebuilt from the plan's
  commands: `config.toml` 192 bytes and `settings.json` 194 bytes with the theme "auto", and the Codex process guard
  pointed at no process because `codex` runs on this workstation). `--apply` exited 0 and every step applied: the
  Claude settings kept the marketplace and the theme (`kept your theme: "auto" (the render has "dark")`) and gained the
  wired settings, the Codex config kept its marketplace table and `screen_reader_detection_done` and gained the render
  (`features.daemon_auto_start` through Codex's writer), each file with one backup, `claude mcp add` registered `serena`
  and `qmd`. The second run reported every step `current`; no file under `~/.claude`, `~/.codex` or the profile changed (the
  only new files were Claude Code's own MCP log files, written by its `mcp get`); `codex mcp list` read the merged file.
  No credential file existed before or after.
- **The authorization settings with the real clients** (the fourth round; Claude Code 2.1.287 and Codex 0.159.3, three
  temporary homes with no credential, the Codex process guard pointed at no process because `codex` runs on this
  workstation). Home A, the destination's two files and the plain `--apply`: none of the four keys was written
  (`defaultMode`, `skipDangerousModePermissionPrompt`, `approval_policy` and `sandbox_mode` absent), the 127 deny rules
  were, and the line said `left to the clients' own defaults`. Home B, the same files and the option: all four were added
  (`bypassPermissions`, `true`, `never`, `danger-full-access`) and the line said `applied`. Home C, files that held
  `defaultMode: "default"`, `skipDangerousModePermissionPrompt: false`, `approval_policy = "on-request"` and
  `sandbox_mode = "workspace-write"`, with the option: all four values stayed, each was printed beside the render's, the
  Codex step ended `merged with conflicts kept` and the line said `kept`; a plain `--apply` of the same home then changed
  nothing. `codex mcp list` read both merged files. No credential file existed.
- **Negative controls on the tool** (the fourth round): six deliberate breaks, one at a time, each against the new tests,
  with the file put back and its hash checked afterwards: the four wired by default (7 tests fail), no check before the
  creation of an absent file (2 fail), no scan of the render in `--check` (2 fail), the Claude step not keeping its value
  (3 fail), the option ignored by `--render` (1 fails) and the refusal of an authorization piece classed practice removed
  (1 fails).
- **Portability of the tests** (the fifth round: the hosted macOS run of `a372ab3b2` failed two tests of
  `tests/test_new_wsl_client_config.py`; macOS itself was not available here). One compared the whole rendered `PATH`
  with the conflict line, and the display is cut at 300 characters (Decision 11): the render holds the home three times, so
  where a temporary directory is longer the value is cut. A temporary directory of 92 characters, which gives a home of 109,
  reproduced the failure on Linux with the old assertion (it failed there, and passed with the usual directory of 25
  characters, a home of 42). The assertion now works out the expected display
  from the render's value and holds on either side of the width; a second test makes the cut certain on any host (a home
  with a long name) and checks that a value that is added is written whole; a third pins the boundary (a text of exactly 300
  characters is whole, one of 301 is cut). The other read `/proc/<pid>/cmdline`, which macOS has not: the tool now reads a
  command line through `ps` where there is no `/proc` (Decision 11), the tests that name the daemon run on both, and the
  one that needs `pgrep -x` to match a `#!` script by its file name is Linux-only, with that reason in its skip message. On
  Linux the whole module (127 tests) passes with the usual temporary directory, with the one of 92 characters and with one reached through a symlink (the
  shape of macOS's, where `/var` is a link); and, with
  the tool's `/proc` pointed at nothing so that every command line is read through `ps`, 126 tests pass (one test that is
  Linux-only by its own condition is left out, as a platform without `/proc` skips it). The Linux reading is the old one: a
  test compares the new function with a copy of the old on a running daemon, a quiet process, pid 1, the test's own pid, an
  absent pid, a word and an empty string. Nine deliberate breaks of the new code each fail the new tests (`ps` asked for
  the wrong column, `ps` asked to show the environment, the program counted as an argument, the NUL that ends the last
  argument kept, a pid that is no number handed to `ps`, the hint never given, the display cut at 200 and one character
  early, `/proc` taken for absent where it exists), with the file put back and its hash checked afterwards. A first draft of
  the reader reused the name `command_words`, which the tool already uses for the practice-piece check: the module's tests
  failed on it (the practice-piece test and the new ones), and the function is now `process_command_line`.
- **The sixth round's checks** (Linux; the clients are the stubs of the tests, and no real client ran in this round). Two
  dry runs of `--apply --host example` into an empty temporary home, each of which created nothing and exited 0. With
  `--with-authorization-settings` the line was `authorization settings: would be applied (--with-authorization-settings;
  added: Claude Code permissions.defaultMode, Claude Code skipDangerousModePermissionPrompt, Codex approval_policy, Codex
  sandbox_mode)`; with `--with-authorization-settings --skip codex-config` it was `authorization settings: would be
  partly applied (--with-authorization-settings; added: Claude Code permissions.defaultMode, Claude Code
  skipDangerousModePermissionPrompt; not reached, its step codex-config was skipped: Codex approval_policy, Codex
  sandbox_mode)`. The tests run each of the seven outcomes in a home of its own, a failed Codex step (a `config.toml` that
  is not TOML) beside a skipped one, and values that are kept beside a step that is not reached. The tool approval modes
  were run three ways in scratch catalogs: a template that gives the wired `serena` an approving mode is refused until its
  key is classed authorization and tied to the slot, and then it is written only with the option, in the render and in a
  plain and an optioned `--apply`; a per-tool `approval_mode` is caught when it approves and left alone when it asks; and a
  manifest in which `memory-owner` installs `ai-memory` wires the server and still writes `default_tools_approval_mode`
  into `stack-worker.config.toml` only with the option (the line then says `applied` and names the key). The failed check
  was run with stand-in `pgrep` programs that exit 2 and 3 and one that kills itself, and with no `pgrep` on `PATH`, in
  the merge and in the creation of an absent file, with a file that needs nothing and with a dry run. Ten deliberate breaks
  of the new code each fail the new tests (a `pgrep` status never a failed check, status 3 let through, the guard calling
  the helper that drops the status, `default_tools_approval_mode` not a key of the class, an `approval_mode` that counts
  whatever its value, an authorization piece that ignores its slot, the profile's settings never recorded, a partial result
  that still starts with `applied`, a skipped step and a failed step read alike, and six outcomes in the code's list), with
  the file put back and its hash checked afterwards. The sentences that F9 shares with the records and the tool are searched
  for with their line breaks ignored and read the same in every place (the blocks sentence in the recipe, this record, the
  2026-10-01 record and the recipe test; the sentence about the authorization line in the recipe, this record, the tool's
  docstring and the recipe test), and the seven outcome words are in all four places that name them.
- **Codex's hook trust with the installed client** (the third round; Codex 0.159.3, `app-server` over stdio, `hooks/list`,
  temporary homes at different paths): the repository's currency-notice group in a user `hooks.json` gave the key
  `<home>/.codex/hooks.json:session_start:0:0` and one `currentHash` in two homes at different paths; a timeout of 6 for
  5 gave another hash; the same group as the second group kept the hash and took the key `…:session_start:1:0`; a
  `trusted_hash` equal to the first home's hash, written under another home's own key, made Codex list that hook as
  `trusted`. This is the installed client at 0.159.3; the source read for the same logic is at `rust-v0.160.0`.
- **Launcher.** The generated launcher is 1,810 bytes with sha256 `f48eb134…`, byte for byte the file that
  `docs/decisions/2026-09-29-max-default-effort.md` records for the workstation's launcher (`f48eb134…0a2cd5`) and the one
  installed there. It passes the repository's own 27-case pseudo-terminal table
  (`tests/test_adoption_bootstrap.py`, `InteractiveEffortLauncherTests.CASES`), run against it in the new tests.
- **Codex keys.** Every key of the three rendered Codex files exists in `codex-rs/core/config.schema.json` at
  `rust-v0.160.0`, and the words `never`, `danger-full-access`, `live` and `file` are in the schema's lists. This is a
  read of the schema, not a Codex 0.160.0 run.
- **The filter's own checks** (round 2): the committed blocks, the kept-lines test, the name scan, the word-count
  partition and the dropped-unit test run against the real sources; synthetic texts show each rule (a sentence, a bullet
  whose first sentence names a tool, a wrapped paragraph, a heading left empty, a numbered item, a comment line, a code
  fence refused, a declared dependent sentence that goes with the one before it and one that stays) and that a second
  pass changes nothing. A bug the numbered-item test found is fixed: the item's own number was taken for a sentence, so
  `2. Second names beta.` would have left `2.` behind.
- **The merge's own checks** (the third round): the pure functions (`plan_merge`, `scan_toml`, `merge_toml_text`) on 80
  seeded partial renders, with and without a final newline, each completed to the whole render and, planned again, to
  nothing; the destination's shape; conflicts; a comment-only file; look-alike lines inside arrays and multi-line
  strings; an inline table and dotted keys refused; a writer that fails and one that writes more than it should (the file
  is put back and the step fails); a running Codex (a real `sleep` named as the process); a dry run; and a first run found
  a real defect that is fixed: keys that belong to the file's last table came after a table added at the end, and landed
  under the wrong header.
- **Synthetic stub clients** stand in for `claude` and `codex` in the unit tests; they answer in the shape of Claude Code
  2.1.287's `claude mcp get`. A real bash login shell, started as a Windows Terminal profile's `bash -lc` starts one,
  found `claude` (the launcher), `codex`, `serena`, `qmd` and `mise` in the temporary home after `--apply` and none of
  them before it.

Not verified: the authorization option with a Codex 0.160.0 binary and with the Claude Code of the destination (the runs
above used Codex 0.159.3 and Claude Code 2.1.287); which of the four a host's owner wants, since that is the owner's call;
`model_reasoning_effort = "ultra"` against the schema (it lists no words for that key; the template
keeps the value its own comments source); any tool of the install plan installed or ran (the plan has not run on the
destination distribution); Serena 1.7.0's or QMD 2.8.3's own start-up (the flags are read from their source at the tags);
Codex 0.160.0; a real interactive session of either client on a new distribution, so that a client reads the filtered
blocks or that a model follows them; whether `npm install -g` through mise's Node reshims `qmd` on the destination; the
F10 proof from Windows; the launcher in a real terminal on the new distribution; that a model uses any wired piece; the
after-sign-in checks of `agent-runtime-worker` and `research-harnesses`, which run upstream model examples (the plan's
README, L34), so whether the two native sign-ins suffice for them was not read from their sources and not run; and F8's
proof on the destination distribution; the merge with a Codex 0.160.0 binary and on a `config.toml` that a Codex of that
version wrote itself after an interactive start (the 192 and 194 bytes are rebuilt from the plan's two commands, with the
sizes the coordinator observed, not copied from the destination; the Claude theme in the test is "auto", a four-character
value like the destination's, which is not the template's "dark"); and any Codex hook run or trusted on a new host (none
is wired). F8's `ss` command was run once on this host (2026-10-02T16:42Z, the shared
network namespace): no listener on `21318`, `29374`, `21633` or `28231`, and listeners on `24318` and `26333`.

Not verified on macOS: that the two repaired tests and the new `CommandLineTests` pass on a macOS runner. The `ps` reading ran
through Linux's `ps` (procps), not BSD's. The flags are the ones Apple's manual source documents (see the sources read for
the fifth round), but what `ps -ww -o command= -p <pid>` prints on macOS for a process with an argument that holds a space,
and what `pgrep -x` makes of a `#!` script's name, were not observed (the one test that depends on the
second is Linux-only, and says why). The first macOS hosted run after this change is the evidence.

Not verified in the sixth round: a real `pgrep` that exits 2 or 3 (the stand-ins are programs of the tests; neither procps's nor
Apple's `pgrep` can be made to fail that way on demand here, and the manuals above are what says they do); the tool approval
modes with a Codex binary (the keys come from the schema at `rust-v0.160.0`, and Codex 0.159.3 was not asked to read a
profile that carries them); and the authorization line on a real destination run.

## Contradictions met

- **`slot:` targets** (accepted by the coordinator). The contract says `--check` fails when a `slot:` target "is not a row
  that installs", and also says the pieces of ai-memory, SocratiCode and the others are not wired because their slots are
  open, split or resolved as not installed, and asks for a test in which a split slot becomes installing and wires its
  piece. The three cannot all hold on one map. I followed the second and third: a piece mapped to a slot that does not
  install is reported as not wired, and `--check` fails only on a slot id that the manifest does not have.
- **The launcher's place** (accepted). The contract cites the setup page for a custom launcher at `~/.local/bin/claude`
  and asks to reuse the bootstrap's text. The text would run itself there (Decision 7), so the launcher is in `ECO_ROOT/bin`,
  as the bootstrap and `scripts/adoption_status.py --launcher-resolution` already have it.
- **The collector port and the host template** (resolved in the second round). The template carried `OTEL_ENDPOINT`
  127.0.0.1:24318 and the plan's collector listens on 127.0.0.1:21318. The template, F8's probe and its exclusion set now
  agree with the plan (Decision 6). The tool still takes the plan's port when a host file names another, and `--check`
  prints a note that names both when the template and the plan differ.
- **A refusal where a merge was needed** (resolved in the third round). The second round decided that no merge path was
  needed, on the premise that `codex login` or a first start might leave a `config.toml` and that configuring first
  would avoid it. The install plan itself leaves one (`codex plugin marketplace add`), so the file exists in either
  order; Decision 11 is the merge, and the order of F9 rests on the guard hooks alone.
- **F9 was pinned outside its section** (resolved). The command table and prose of the 2026-10-01 record, the receipt
  example and the checklist held the old bootstrap commands, and the tests compared them with the recipe. The three files
  now carry the new rows and both comparisons read F9 again.
- **The Codex references.** The contract names `docs/config.md` and a hooks documentation in the repository at the tag;
  at `rust-v0.160.0` they are the pointers and the schema folder described above.
- **The handbook builder** (changed by the merge of main). The first contract named `scripts/build_new_wsl_handbook.py` and
  `docs/new-wsl-handbook.*`, which were not on the base then. They are on the branch now, and `docs/new-wsl-handbook.json`
  records the recipe page by SHA-256 among its sources, so every edit of F9 makes the handbook stale until the coordinator
  regenerates it; the rules of this work forbid regenerating it here.
- **Authorization settings as practice** (resolved in the fourth round). The first rounds classed Claude Code's
  `permissions.defaultMode` and `skipDangerousModePermissionPrompt` and Codex's `approval_policy` and `sandbox_mode` as
  repository practice, which is true of the repository's own workstation and not a reason to write them on a host whose
  owner has not asked. Decision 14.
- **F9's sentence about the instruction blocks** (resolved in the fourth round, corrected in the sixth). F9 said every
  unit that names a tool the manifest does not install is left out, and this record said that sentences naming
  `search-first`, `find-skills`, `skill-creator` and the daily currency timer stay. The fourth round's replacement, a tool
  "the map declares as not wired" and skills or timers "the map does not list", was contradicted by the dropped list
  itself: the filter's names are the map's names for unwired pieces plus the former defaults of the manifest rows that
  install nothing, and the Promptfoo unit (in no map entry; the manifest row `promptfoo`) also names `skill-creator` and is
  left out of both blocks. F9 now says what the list shows (Decision 9), and a test holds the sentence against it.
- **A path in the plan.** The `credential-guard` row of `install-plan.json` lists `adoption/codex.config.template.toml`,
  which does not exist (the template is `adoption/templates/codex.config.template.toml`).
- **`jq`** (accepted). A practice hook may run python3 and `jq` besides the files the repository copies, because F4 installs
  `jq` and the bootstrap requires it. The Windows Terminal bell hook of the overlay runs `jq`; it is wired on that reading.
  Moving it to `not_wired` is one map entry.
- **`MCP_AUTO_OPEN_ENABLED`** (accepted). The manifest installs MCP Inspector (the variable is its) but the plan runs it on
  demand with `npx`, so `--check` warns that the manifest installs the slot and the plan does not; the variable is wired.
- **The Claude begin marker.** `managed_block.py` writes the marker line of the Claude block itself, and that line says
  the block was written by `adoption/bootstrap-linux.sh --configure-full-profile`. On this distribution `--apply` writes
  it. I did not change the marker (it is a constant of an existing tool, and the block's text is the point of the rule);
  changing it is one additive option of `managed_block.py`. The Codex block's begin marker comes from the template and
  names the template. The login-shell PATH block's marker says the same of the bootstrap.

## Left for the coordinator

- Regenerate the new WSL handbook (`scripts/build_new_wsl_handbook.py --write`) and the receipt that records its output
  digests (`evidence/artifacts/new-wsl-handbook-20261001/receipt.json`): `docs/new-wsl-handbook.json` records the recipe
  page by SHA-256, and the sixth round changed F9 again, so the handbook and its test are stale until then (not done here).
- Re-freeze the convergence record that pins the changed files (`blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json`
  holds the SHA-256 of the recipe page, the host template, the receipt example, the checklist, the 2026-10-01 record and
  its test), and register the changed files in `manifests/evidence.json` (the ones `scripts/validate.py` names in the run
  above).
- An observation outside this change: the Codex `projects.<path>.trust_level` and `hooks.state.<key>.trusted_hash` pieces
  are `not_wired` (never carried over from another host) and `is_authorization_piece` does not name them, so a map that
  later classed one of them practice or slot would write a trust grant by default. Adding them to the class is one pattern
  each; I did not, because nothing writes them today and the instruction was exact.
- Decide whether the filtered blocks are what the user wants. The list below is the whole difference from the source blocks. If a
  dropped sentence should stay, the way is a wired entry in the map (or a name removed from an unwired entry) and
  `--write-blocks`; if a kept sentence should go, the way is a name added to an unwired entry.
- Decide whether the two Codex role carriers stay out (Decision 10), and whether the Claude block's begin marker should name
  this tool (see Contradictions).
- Decision 14 asks the coordinator one question it cannot settle alone: whether the repository's permission practice
  (`bypassPermissions`, `never`, `danger-full-access`) should ever be the default of a new distribution. The tool now
  writes it only on request, so a host that wants it needs the option on the `--apply` line and a receipt that names who
  asked.
- Decision 12 reads "keeps both" as keeping the theme's value too; every other scalar of the Claude template still wins
  over a file's value, as in the first round. If the Claude merge should also keep and report every differing value, as the
  Codex merge does, that is a larger change to `apply_claude_settings.py`'s rule and was not made.
- Decision 13 found no Codex guard hook in the design and wired none. If a guard for Codex is wanted it is a new decision
  (a hook in Codex's protocol; its trust entry can be rendered, as the decision shows). Also seen while reading: no
  template sets `[shell_environment_policy] inherit = "none"`, the one Codex-side measure `docs/secret-storage.md` names
  and `credential_status.py --client-guards` checks, so the rendered Codex config does not have it either. (Since the
  2026-10-03 addendum the new distribution's render has it, from `adoption/new-wsl/templates/codex.config.additions.toml`;
  the shared templates still do not.)
- An observation outside this change: at the `ss` run named under "Not verified", 127.0.0.1:21434, the port of the plan's `local-model-server` row
  (`OLLAMA_HOST=127.0.0.1:21434`), had a listener on this host. F8 checks only the template's four ports, not the plan's
  own, and WSL 2 distributions share one network namespace.
- Nothing is committed. `tests/test_adoption_docs_consistency.py` reads `git ls-files` and F9 names the new tool, so the
  new files carry `git add --intent-to-add` in the worktree's index (no content staged, no commit); commit them with the
  rest.
- The upstream-recommended Serena hooks (`serena-hooks`, Serena `docs/02-usage/030_clients.md` L149-226 and L321-387) are
  not in any template and are not wired.

## Addendum 2026-10-03: the wave-2 records

Branch `foundation/new-wsl-wave2-records-20261003`, phase 0.3 of the wave-2 synthesis
(`wsl-architecture-design-wave2-final-architecture-20261003.md`, sha256 3b512613…; its dossiers and rulings are in
`evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json`). The rule of Decision 1 is unchanged; the
manifest changed under it.

- **What now wires.** Amendment 3 of the manifest's decision rule gives three slots an interim install: memory-owner
  (ai-memory 2.5.2), code-search (semble 0.6.1) and context-supply (context-mode 1.0.169); the layer consensus adds the
  statusline row (claude-hud 0.10.0 and Codex's own footer). Their pieces are wired by Decision 3's rule. The entries of
  the owners those slots do not install (rtk, headroom, SocratiCode) stay slot entries, so they wire again if the manifest
  names their owner, and `--check` warns about each.
- **ai-memory** (memory ruling, change 13; synthesis X5). The hooks run `AI_MEMORY_BIN`, which the tool now takes from the
  plan's memory-owner row (the link it makes, `~/.local/bin/ai-memory`); `render_config.py` would derive the platform
  pin's path, `${ECO_ROOT}/tools/ai-memory-2.4.1/ai-memory`, which this plan does not install. The Claude MCP entry takes
  the host file's `AI_MEMORY_URL` through its override (this tool fills host values in an MCP override;
  `install_claude_profile.py` fills only `${HOME}` and `${ECO_ROOT}`), as the Codex entry and the hooks do, so the host
  template's 127.0.0.1:29374 is the one port. `--apply`'s login-shell probe no longer assumes every server is stdio.
- **semble** (code-search ruling, changes 2-5 and 7). The Claude and Codex entries name the uv tool's `semble`, the pinned
  model's local snapshot as `SEMBLE_MODEL_NAME` and a cache of each client's own; the Codex approval mode `approve` and two
  exact-name Claude allow rules are authorization pieces tied to the slot (Decision 14).
- **The new distribution's additions, not the shared templates** (review of the branch, 2026-10-03). The keys only this
  distribution takes are in `adoption/new-wsl/templates/` (`codex.config.additions.toml`, `claude-user.mcp.additions.json`,
  `claude.settings.additions.json`), which only this tool reads and merges into their templates; a key a template and its
  additions both define is refused. They hold Codex's `inherit = "none"` with its set table, both semble servers,
  semble's two allow rules and ai-memory's Codex approval mode. The shared templates are again what `render_config.py`,
  `install_claude_profile.py` and the bootstrap's full profile give every other host, so Decision 5 of
  `2026-09-26-codex-worker-lane.md` (tool settings in the stack-worker profile, not at user scope) stands for those hosts
  unamended, and no host registers a semble server it has not installed.
- **Status line** (usage ruling, changes 3-5, 8 and 9). The marketplace at v0.10.0 and the command `setup.mjs` writes at
  jarrodwatts/claude-hud@75683c6d (L21-32, L69-80) are overrides, so the shared template keeps the workstation's v0.8.0
  and its wrapper; `statusLine` is `keep_existing`, because `setup.mjs` writes the runtime that ran it. Codex gets the
  six-item `[tui] status_line`.
- **context-mode** (context ruling, changes 7-9). The plan installs the npm copy under the template's prefix (form a), so
  no override is needed. The six `[hooks.state]` entries of the plugin are wired; on the destination their hashes are
  read back and compared before an apply. `codex_home.py --keep-hook-trust` keeps them in a `config.toml` it creates, so
  a new home and a merge end the same. The cache-heal hook stays unwired: the plugin writes it and the file it runs (X11).
- **Codex shells** (custody ruling, change 7). `[shell_environment_policy] inherit = "none"` with `HOME`, `LANG`, `TERM`,
  `TMPDIR`, `XDG_RUNTIME_DIR` and `DOCKER_HOST` beside `PATH` (docs/secret-storage.md, Codex), from the additions file.
  `XDG_RUNTIME_DIR` is `/run/user/<uid>` of the user the tool runs as (user@.service(5)), which the tool fills unless the
  host value file names one, so `systemctl --user` and the messaging courier work in Codex shells (synthesis X12);
  `DOCKER_HOST` is `unix://${XDG_RUNTIME_DIR}/docker.sock`, the rootless socket the install plan exports, wired through
  the container-engine slot. A test holds both in the rendered table.
- **Instruction lines.** Both sources gain the context-mode lane sentence, the semble ownership line, the GPT Researcher
  line (research ruling, step 8 with changes 4-5) and the messaging lines (messaging dossier, wiring 6, with ruling
  changes 1, 2, 3 and 11), each phrased to hold on a host without those tools. On Codex, the research script and the
  courier run as long commands: `yield_time_ms` 30000, then `write_stdin` polls with empty `chars` until the process exits
  (messaging ruling, change 1: the interactive `exec_command` of rust-v0.160.0 has no `timeout_ms`, and `yield_time_ms`
  caps at 30000, codex-rs/core/src/unified_exec/mod.rs L73-77 and tools/handlers/shell_spec.rs L117-154).
- **Codex's ai-memory hooks** (memory ruling, changes 12-13; synthesis X10 and X11). This tool writes no
  `~/.codex/hooks.json`, so ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes its seven Codex hooks once
  (the install plan's memory-owner row): the one exception X11 allows, after which `--check` must pass. Their trust takes
  X10's route: the destination reads the seven hashes back through `codex app-server` `hooks/list`, the reviewed values
  replace the 2.4.x hashes in the template, and the map then wires those `[hooks.state]` entries; the `/hooks` review is
  the fallback until then (recipes/README.md, amended the same day).
- **Remote plugins** (skills ruling, change 5). `--apply` reads the account's remote plugin cache and adds one
  `[[skills.config]]` name rule per plugin skill and an off switch per plugin MCP server (the map's
  `step/codex-remote-plugin-rules`). A plugin that ships an MCP server also gets `enabled = false` on its own table, which
  the ruling does not name: at rust-v0.160.0 a local `[plugins."<id>"]` table defaults `enabled` to true
  (config/src/types.rs L1004-1006), a local entry the account's synced list lacks stays as configured, and an enabled
  entry whose bundle is cached loads (core-plugins/src/loader.rs, `merge_configured_plugins_with_remote_installed` and
  `load_plugin`), so a table holding only the server switch would turn on a cached plugin the account no longer
  installs; while the account installs it, the synced entry replaces the local one and keeps only its `mcp_servers`. Codex's rule lists are arrays of tables, so the render writes them as `[[...]]` items
  and the merge adds the render's rules a file lacks after the file's own, instead of keeping the file's list as a
  conflict; a list a file writes inline is refused with nothing written. An empty `config = []` is such a list: TOML
  writes an empty array only inline and forbids adding `[[...]]` items to it, so it is refused too, never kept as a
  conflict that would leave the rules out, and the line `--apply` prints when it reads the cache calls the rules
  planned, because they hold only after the step's write and read-back (both added after the Codex root lane's source
  read of `b6828c7d`, finding 2).
- **The acknowledgement gate** (code-search ruling, change 1). While the layer consensus's wave-2 batch owes an
  acknowledgement (`consensus.json` `wave2.acknowledgements_owed`), a real `--apply` refuses to write a render that wires an
  interim install, and a dry run says so; `install.sh`'s `interim_acknowledged` holds the plan's side (the layer-consensus
  record, section Wave 2).
- **Smaller corrections.** The agents' gaps count a wired plugin's own tools and skills (context ruling, change 14); an
  allow rule a settings file already has counts as already the same; the default authorization line names the approval
  modes and allow rules; a profile's approval mode is labelled with its profile. The stack-worker profile is still created
  only when absent, so a host whose profile predates these rows keeps it until the file is moved aside.

What would overturn it: the deciding measurement of each interim slot (amendment 3 names it), and the usage overturn for
the statusline row.

## Addendum 2026-10-04: the main checkout's Codex trust grant and the model

Branch `c5/new-wsl-codex-0160`, the coordinator's follow-up to PR #626 (Codex 0.160.0). The rule of Decision 1 is
unchanged.

- **The trust grant.** Codex 0.160.0 asks whether to trust a folder when a session moves into a project that has no
  saved answer (openai/codex PR #49160, merged 2026-09-29 and in `rust-v0.160.0`, lets `/cd` request folder trust). The
  coordinator's decision of 2026-10-04 (R16 review) keeps that dialog, with the repository's own root pre-trusted and
  unknown projects still asked about. The shared template's `projects."${PROJECT_ROOT}".trust_level` piece is now wired
  as an authorization setting: `is_authorization_piece` names `codex/*/projects.*.trust_level`, the one pattern the
  observation under "Left for the coordinator" asked for, so the grant is rendered and written only with
  `--with-authorization-settings`, and a file's own answer stays. The publication checkout's grant and every other
  `projects.*` piece stay not wired.
- **Why one entry.** At `rust-v0.160.0`, `codex-rs/tui/src/config_update.rs` L264-279 finds a project's entry by its
  exact key (case-insensitively only for a Windows path), and L305-337 tries the working directory, the project root and
  then the git trust root, which `codex-rs/git-utils/src/trust.rs` L12-24 resolves to the main repository's root for a
  linked worktree (upstream tests `codex-rs/core/src/git_info_tests.rs` L829-968, which also refuse a worktree whose
  back-link or common directory does not match). A trusted project's `.codex/config.toml` layers load instead of loading
  disabled (`codex-rs/config/src/loader/mod.rs` L131-133), and the TUI asks nothing for it (`config_update.rs`
  L338-366). So the entry for the main checkout covers it and every linked worktree, and an entry for a parent directory
  covers neither. On the new distribution `${PROJECT_ROOT}` is the main checkout:
  `adoption/templates/wsl/host.new-distro.json.template` sets it to the `native-agent-stack` checkout in the home, and no
  committed file holds the rendered path.
- **A new Codex home.** `codex_home.py` drops every `[projects]` table from a `config.toml` it creates. It gains
  `--keep-project-trust`, which this tool passes beside `--keep-hook-trust`, so a new home and a later merge end with the
  same file and the authorization line's `added` is true. The bootstrap passes neither flag and is unchanged.
- **The merge's report.** The merge looked an authorization piece up under its template path. A key that names a
  placeholder is now looked up as the render filled it, so a grant the file already has is reported as already the same,
  or as kept when the file's answer differs.
- **The model.** The user chose Opus 5.5 on 2026-10-04 (question tool) as the new distribution's main model. The map's
  own entry for `claude/settings/setting/model` overrides the shared template's `opus[1m]` with `claude-opus-5-5`, the
  full model name the model-config page gives for pinning a version (https://code.claude.com/docs/en/model-config, read
  2026-10-04: `opus` resolves to Opus 5.5 on the Anthropic API today, and Opus 4.7 and later run with the 1M window
  without a suffix). Claude Code resolves the same model as before; what changes is that the new distribution keeps it
  when the shared template moves. `advisorModel` stays the template's `fable`.
  2026-10-04 (~15:10Z): the user changed the advisor to Opus 5.5; the template now carries `advisorModel: "opus"` (see [Advisor model](2026-10-04-coordinator-dispatch-and-spend.md#advisor-model)).
  when the shared template moves. `advisorModel` is `opus` (Opus 5.5) too, by its own override entry: the user's decision of
  2026-10-04 and the value NativeStack carries (`docs/decisions/2026-10-04-new-wsl-changelog-parity.md`).
- **Counts.** 393 pieces, 354 wired, 24 not wired and 16 authorization pieces (Decisions 2 and 14 above).

What would overturn it: Codex matching a project's trust by a parent directory or by another key form; a decision that
the repository's root should ask again (the entry returns to `not_wired`); the user choosing another main model, or the
floating `opus` alias, for the new distribution.

## Addendum 2026-10-04: the token layer

[The 2026-10-04 record](2026-10-04-new-wsl-token-layer-default.md) applies the owner's directive of that day. It supersedes this record's
not-wired rulings for rtk (through the map's new `directive` field), the SubagentStart token-lane carrier and the Claude Code
currency notice, and it adds agent teams. Where the text above says that those pieces stay unwired, the 2026-10-04 record
governs. Decision 2's counts sentence and the tables below are recounted.

## Pieces that are not wired

`python3 -B tools/adoption/new_wsl_client_config.py --check --markdown` prints these three tables (the pieces that are not wired, the authorization
settings and the project agents' gaps) and the list of dropped units after them; the test `test_the_record_holds_the_tables_the_tool_prints` fails when this section and the tool disagree.

| Piece | Wiring | Why it is not wired |
| --- | --- | --- |
| `claude/settings/permission/deny/Agent(codex:codex-rescue)` | `not_wired` | the manifest has no slot whose repository is openai/codex-plugin-cc (the nearest rows, codex and codex-sdk-and-codex-exec-app-server, are openai/codex), so no installed owner supplies the plugin |
| `claude/settings/hook/SessionStart/matcher=-/"${HOME}/.claude/hooks/context-mode-cache-heal.mjs"` | `not_wired` | context-mode writes this SessionStart hook into settings.json itself and deploys the file it runs, ~/.claude/hooks/context-mode-cache-heal.mjs (start.mjs L166-183 at mksglu/context-mode@6f0cc684; evidence/artifacts/context-mode-codex-binding-20260926/README.md L207-217), and its self-heal runs on every start from either client and on npm postinstall (start.mjs L227-427 and L237-239, scripts/heal-installed-plugins.mjs L202-205); the repository does not copy that file, and a second writer of the entry would compete with the plugin's own (wave-2 synthesis X11; context ruling, change 8) |
| `claude/settings/plugin/codex@openai-codex` | `not_wired` | the manifest has no slot whose repository is openai/codex-plugin-cc (the nearest rows, codex and codex-sdk-and-codex-exec-app-server, are openai/codex), so no installed owner supplies the plugin |
| `claude/settings/marketplace/openai-codex` | `not_wired` | the manifest has no slot whose repository is openai/codex-plugin-cc (the nearest rows, codex and codex-sdk-and-codex-exec-app-server, are openai/codex), so no installed owner supplies the plugin |
| `codex/config/check_for_update_on_startup` | `not_wired` | the template sets it false because the client is pinned and updated by the stack, and the install plan installs Codex with its self-updating native installer, so Codex keeps its own update check |
| `codex/config/projects."${HOME}/code/native-agent-stack-publication".trust_level` | `not_wired` | trust grants belong to one host; adoption/bootstrap.md step 4 and tools/adoption/codex_home.py leave them out, and Codex asks on this host |
| `codex/config/tui.model_availability_nux.gpt-6-astra` | `not_wired` | a counter of how often Codex showed a model notice on the source host, which is client state and not configuration |
| `codex/config/tui.model_availability_nux."gpt-6.1-sol"` | `not_wired` | a counter of how often Codex showed a model notice on the source host, which is client state and not configuration |
| `codex/config/hooks.state."${PROJECT_ROOT}/.codex/hooks.json:pre_tool_use:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:pre_tool_use:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:post_tool_use:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:pre_compact:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:session_start:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:session_end:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:user_prompt_submit:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:stop:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/hooks/setting/description` | `not_wired` | ~/.codex/hooks.json is written by ai-memory 2.5.2's own install-hooks (the hooks.state entry below), so this tool would be a second writer of that file, and the template's handler has no reviewed trust hash; the Claude Code notice is wired |
| `codex/hooks/hook/SessionStart/matcher=startup/python3 "$HOME/.claude/hooks/currency-due-notice.py" 2>/dev/null \|\| true` | `not_wired` | ~/.codex/hooks.json is written by ai-memory 2.5.2's own install-hooks (the hooks.state entry below), so this tool would be a second writer of that file, and the template's handler has no reviewed trust hash; the Claude Code notice is wired |
| `codex/role/stack-researcher.toml` | `not_wired` | the carriers are byte-pinned in adoption/agents/codex/SHA256SUMS and ruled by tools/adoption/codex_roles.py (cwd_rule, exact_shapes, f4_block); stack-researcher.toml names jCodeMunch, which this distribution does not install, so a copy without that sentence keeps the three rules but not its pinned hash; stack-verifier.toml names no tool that is not wired, and the 2026-10-04 token-layer record leaves both roles to its follow-up, the carriers filtered to the installed lanes |
| `codex/role/stack-verifier.toml` | `not_wired` | the carriers are byte-pinned in adoption/agents/codex/SHA256SUMS and ruled by tools/adoption/codex_roles.py (cwd_rule, exact_shapes, f4_block); stack-researcher.toml names jCodeMunch, which this distribution does not install, so a copy without that sentence keeps the three rules but not its pinned hash; stack-verifier.toml names no tool that is not wired, and the 2026-10-04 token-layer record leaves both roles to its follow-up, the carriers filtered to the installed lanes |
| `codex/worker-role/evidence-reviewer.toml` | `not_wired` | installed only by apply_codex_lane.py --worker-roles, which adds every role's description to every parent's spawn text and which the lane keeps off while the token-adoption E2E's Gate A window is open |
| `codex/worker-role/isolated-builder.toml` | `not_wired` | installed only by apply_codex_lane.py --worker-roles, which adds every role's description to every parent's spawn text and which the lane keeps off while the token-adoption E2E's Gate A window is open |
| `codex/worker-role/semantic-evidence-reviewer.toml` | `not_wired` | installed only by apply_codex_lane.py --worker-roles, which adds every role's description to every parent's spawn text and which the lane keeps off while the token-adoption E2E's Gate A window is open |
| `step/skills` | `not_wired` | the install plan installs the six mattpocock skills and adds the Trail of Bits marketplace; this tool runs no skills installer |

| Authorization setting | Value --with-authorization-settings writes | Written by default | Why it needs the option | Also needs |
| --- | --- | --- | --- | --- |
| `claude/settings/setting/permissions.defaultMode` | `"bypassPermissions"` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `claude/settings/permission/allow/mcp__semble__search` | `"mcp__semble__search"` | no | an allow rule lets Claude Code call the tool without asking outside bypass mode; the rules name each tool exactly, so an upstream upgrade cannot add an allowed tool silently (wave-2 code-search ruling, change 3) | slot `code-search` installing `semble` |
| `claude/settings/permission/allow/mcp__semble__find_related` | `"mcp__semble__find_related"` | no | an allow rule lets Claude Code call the tool without asking outside bypass mode; the rules name each tool exactly, so an upstream upgrade cannot add an allowed tool silently (wave-2 code-search ruling, change 3) | slot `code-search` installing `semble` |
| `claude/settings/setting/skipDangerousModePermissionPrompt` | `true` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `claude/settings/setting/crossSessionInbound` | `"accept"` | no | "accept" delivers messages from the user's other sessions to Claude without the approval hold that otherwise applies to a sender that is not in bypass mode, so it is written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/config/approval_policy` | `"never"` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/config/sandbox_mode` | `"danger-full-access"` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/config/mcp_servers.ai-memory.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `memory-owner` installing `ai-memory` |
| `codex/config/mcp_servers.context-mode.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `context-supply` installing `context-mode` |
| `codex/config/mcp_servers.jcodemunch.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `code-index` installing `jcodemunch` |
| `codex/config/mcp_servers.semble.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `code-search` installing `semble` |
| `codex/config/mcp_servers.chrome-devtools.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of the chrome-devtools MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `playwright-cli` installing `Chrome DevTools MCP 1.10.1 (one stdio MCP server, chrome-devtools, in both clients; it also serves browser diagnostics)` |
| `codex/config/projects."${PROJECT_ROOT}".trust_level` | `"trusted"` | no | a trusted project's own .codex/config.toml layers load and Codex asks nothing about the folder, so the grant is written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/stack-worker/mcp_servers.ai-memory.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `memory-owner` installing `ai-memory` |
| `codex/stack-worker/mcp_servers.socraticode.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `code-search` installing `SocratiCode` |
| `codex/stack-worker/mcp_servers.headroom.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `output-compression` installing `headroom` |

| Project agent | MCP servers of its tools that are not wired | Skills the plan does not install |
| --- | --- | --- |

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

## Amendment (2026-10-07): current instruction line inventory after CI8

The shared top rule is unchanged. Moving the catalog rule outside its marker adds one current Codex instruction line. The native `new_wsl_client_config.py --check --markdown` render (exit 0) supplies this generated line inventory; previous tables and observations above are retained. This is source/render consistency, not a host apply.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 71 of 71 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 65 of 65 lines stay):

```text
```

## Addendum 2026-10-04: integrated Promptfoo owner default

The [fix-wave integration](2026-10-04-2604-e2e-fix-wave.md) canonicalizes the wave-4 owner-default Promptfoo recipe (the owner's repository-quality rule) with the supported owner-batch format. The generated native instruction carriers now retain the upstream harness sentence. This projection establishes no new destination runtime acceptance. The current dropped-unit projection follows.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 65 of 65 lines stay):

```text
```

## Addendum 2026-10-05: round-2 browser registration

The wave-5 browser owner adds one chrome-devtools stdio registration to each
native client, with --headless --isolated --no-usage-statistics --no-performance-crux and pin 1.10.1.
The Codex approval mode remains a scoped authorization piece. The map is the
sole writer; install-row CLI registration commands are removed. The generated
tables and the counts above include these four pieces (three wired and one
authorization). Source: this PR:docs/decisions/2026-10-04-final-architecture-round2.md:24;
ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df:
docs/client-configurations.md:71,109. No destination runtime acceptance is
claimed by this projection.

## Addendum 2026-10-05: official upstream rule projection

The [official-upstream rule decision](2026-10-05-official-upstream-never-rebuild.md) adds the requested standing sentence to both client sources and compresses only the Codex source's session-lane wording to keep its byte budget. The generated instruction carriers retain every unit. The current projection below is the output of `new_wsl_client_config.py --check --markdown`; earlier dated projections retain their original counts. This is instruction projection evidence, not a new host installation or runtime qualification.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 66 of 66 lines stay):

```text
```


## Addendum 2026-10-05: fixed startup context and native RTK layout

The [context-budget decision](2026-10-05-harness-context-budget.md) moves specialized rules behind pointers, removes the skill-listing fraction override (superseded by repair round 3 below: NativeStack2604 keeps `skillListingBudgetFraction: 0.05`), and wires the native RTK global initializer to create RTK.md and its import. The current instruction projection follows; earlier dated projections keep their original counts. This is repository rendering evidence, with RTK init separately exercised in an isolated temporary home, and establishes no destination client or provider acceptance.

Today: 393 pieces, 354 wired (206 practice, 148 through a slot), 24 not wired (0 through a slot that does not install, 24 by their own entry) and 15 authorization pieces.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 52 of 52 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 66 of 66 lines stay):

```text
```

## Addendum 2026-10-05: PR #726 required startup restorations

The [context-budget repair](2026-10-05-harness-context-budget.md) restores the
user-level StructuredOutput guard and common cross-family sentence, carries the
uniform discovery and pinned-glue wording, and makes the existing settings apply
retire the owned listing fraction with absence read-back (superseded by repair round 3 below: the fraction is kept, not retired). Root routing remains
until both hosts pass the post-landing render gate. This current projection is
the generator's dropped-unit output; earlier projections remain historical.
These are repository integration changes, not a new destination installation.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 56 of 56 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 67 of 67 lines stay):

```text
```

## Addendum 2026-10-05: PR #726 repair round 2 contract literals

The [round 2 budget addendum](2026-10-05-harness-context-budget.md#addendum-2026-10-05-pr-726-repair-round-2)
restores the portable effort and unrestricted-size clauses that the checksum-locked
workflow contract reads. The carrier retains both clauses. Existing projections
remain historical; the current generator output follows. This is local repository
projection and workflow-contract evidence, not a new destination host acceptance.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 67 of 67 lines stay):

```text
```


## 2026-10-05 repair round 3: full skill listing and native RTK awareness

The user's [September 30 LLM-native invocation directive](2026-09-30-skills-llm-native-listing.md) governs skill visibility independently of startup file bytes. All nine audit listings return to `on`, and NativeStack2604 keeps `skillListingBudgetFraction: 0.05`. Main's ordinary settings merge preserves unmentioned host keys and applies the configured fraction. Codex carriers now inline the complete pinned RTK 0.51.0 awareness source; the compact template holds only its include marker. See the [round 3 budget comparison](2026-10-05-harness-context-budget.md#2026-10-05-repair-round-3-user-directed-listing-and-verbatim-rtk) for sources and byte ceilings.

After the refresh onto main 9e9553277, which carries wave 5's four browser-registration pieces: Today: 398 pieces, 358 wired (207 practice, 151 through a slot), 24 not wired (0 through a slot that does not install, 24 by their own entry) and 16 authorization pieces. The check prints `authorization: 16`, and 24 pieces are not wired. Earlier dated tables and counts remain historical.

| Piece | Wiring | Why it is not wired |
| --- | --- | --- |
| `claude/settings/permission/deny/Agent(codex:codex-rescue)` | `not_wired` | the manifest has no slot whose repository is openai/codex-plugin-cc (the nearest rows, codex and codex-sdk-and-codex-exec-app-server, are openai/codex), so no installed owner supplies the plugin |
| `claude/settings/hook/SessionStart/matcher=-/"${HOME}/.claude/hooks/context-mode-cache-heal.mjs"` | `not_wired` | context-mode writes this SessionStart hook into settings.json itself and deploys the file it runs, ~/.claude/hooks/context-mode-cache-heal.mjs (start.mjs L166-183 at mksglu/context-mode@6f0cc684; evidence/artifacts/context-mode-codex-binding-20260926/README.md L207-217), and its self-heal runs on every start from either client and on npm postinstall (start.mjs L227-427 and L237-239, scripts/heal-installed-plugins.mjs L202-205); the repository does not copy that file, and a second writer of the entry would compete with the plugin's own (wave-2 synthesis X11; context ruling, change 8) |
| `claude/settings/plugin/codex@openai-codex` | `not_wired` | the manifest has no slot whose repository is openai/codex-plugin-cc (the nearest rows, codex and codex-sdk-and-codex-exec-app-server, are openai/codex), so no installed owner supplies the plugin |
| `claude/settings/marketplace/openai-codex` | `not_wired` | the manifest has no slot whose repository is openai/codex-plugin-cc (the nearest rows, codex and codex-sdk-and-codex-exec-app-server, are openai/codex), so no installed owner supplies the plugin |
| `codex/config/check_for_update_on_startup` | `not_wired` | the template sets it false because the client is pinned and updated by the stack, and the install plan installs Codex with its self-updating native installer, so Codex keeps its own update check |
| `codex/config/projects."${HOME}/code/native-agent-stack-publication".trust_level` | `not_wired` | trust grants belong to one host; adoption/bootstrap.md step 4 and tools/adoption/codex_home.py leave them out, and Codex asks on this host |
| `codex/config/tui.model_availability_nux.gpt-6-astra` | `not_wired` | a counter of how often Codex showed a model notice on the source host, which is client state and not configuration |
| `codex/config/tui.model_availability_nux."gpt-6.1-sol"` | `not_wired` | a counter of how often Codex showed a model notice on the source host, which is client state and not configuration |
| `codex/config/hooks.state."${PROJECT_ROOT}/.codex/hooks.json:pre_tool_use:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:pre_tool_use:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:post_tool_use:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:pre_compact:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:session_start:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:session_end:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:user_prompt_submit:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/config/hooks.state."${HOME}/.codex/hooks.json:stop:0:0".trusted_hash` | `not_wired` | each remaining entry approves the hash of a hook file this tool does not write: the project's own .codex/hooks.json, which the repository does not track, and ai-memory's seven Codex hooks in ~/.codex/hooks.json, which ai-memory 2.5.2's own `install-hooks --agent codex --apply` writes once (the install plan's memory-owner row, the exception synthesis X11 allows) and whose template hashes were taken from ai-memory 2.4.x on another host; their 2.5.2 hashes are read back through `codex app-server` hooks/list on the destination, the reviewed values are recorded in the template, and these entries are then wired so the apply renders them, the one trust route of synthesis X10 (context ruling, change 9); the /hooks review is the fallback until then |
| `codex/hooks/setting/description` | `not_wired` | ~/.codex/hooks.json is written by ai-memory 2.5.2's own install-hooks (the hooks.state entry below), so this tool would be a second writer of that file, and the template's handler has no reviewed trust hash; the Claude Code notice is wired |
| `codex/hooks/hook/SessionStart/matcher=startup/python3 "$HOME/.claude/hooks/currency-due-notice.py" 2>/dev/null \|\| true` | `not_wired` | ~/.codex/hooks.json is written by ai-memory 2.5.2's own install-hooks (the hooks.state entry below), so this tool would be a second writer of that file, and the template's handler has no reviewed trust hash; the Claude Code notice is wired |
| `codex/role/stack-researcher.toml` | `not_wired` | the carriers are byte-pinned in adoption/agents/codex/SHA256SUMS and ruled by tools/adoption/codex_roles.py (cwd_rule, exact_shapes, f4_block); stack-researcher.toml names jCodeMunch, which this distribution does not install, so a copy without that sentence keeps the three rules but not its pinned hash; stack-verifier.toml names no tool that is not wired, and the 2026-10-04 token-layer record leaves both roles to its follow-up, the carriers filtered to the installed lanes |
| `codex/role/stack-verifier.toml` | `not_wired` | the carriers are byte-pinned in adoption/agents/codex/SHA256SUMS and ruled by tools/adoption/codex_roles.py (cwd_rule, exact_shapes, f4_block); stack-researcher.toml names jCodeMunch, which this distribution does not install, so a copy without that sentence keeps the three rules but not its pinned hash; stack-verifier.toml names no tool that is not wired, and the 2026-10-04 token-layer record leaves both roles to its follow-up, the carriers filtered to the installed lanes |
| `codex/worker-role/evidence-reviewer.toml` | `not_wired` | installed only by apply_codex_lane.py --worker-roles, which adds every role's description to every parent's spawn text and which the lane keeps off while the token-adoption E2E's Gate A window is open |
| `codex/worker-role/isolated-builder.toml` | `not_wired` | installed only by apply_codex_lane.py --worker-roles, which adds every role's description to every parent's spawn text and which the lane keeps off while the token-adoption E2E's Gate A window is open |
| `codex/worker-role/semantic-evidence-reviewer.toml` | `not_wired` | installed only by apply_codex_lane.py --worker-roles, which adds every role's description to every parent's spawn text and which the lane keeps off while the token-adoption E2E's Gate A window is open |
| `step/skills` | `not_wired` | the install plan installs the six mattpocock skills and adds the Trail of Bits marketplace; this tool runs no skills installer |

| Authorization setting | Value --with-authorization-settings writes | Written by default | Why it needs the option | Also needs |
| --- | --- | --- | --- | --- |
| `claude/settings/setting/permissions.defaultMode` | `"bypassPermissions"` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `claude/settings/permission/allow/mcp__semble__search` | `"mcp__semble__search"` | no | an allow rule lets Claude Code call the tool without asking outside bypass mode; the rules name each tool exactly, so an upstream upgrade cannot add an allowed tool silently (wave-2 code-search ruling, change 3) | slot `code-search` installing `semble` |
| `claude/settings/permission/allow/mcp__semble__find_related` | `"mcp__semble__find_related"` | no | an allow rule lets Claude Code call the tool without asking outside bypass mode; the rules name each tool exactly, so an upstream upgrade cannot add an allowed tool silently (wave-2 code-search ruling, change 3) | slot `code-search` installing `semble` |
| `claude/settings/setting/skipDangerousModePermissionPrompt` | `true` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `claude/settings/setting/crossSessionInbound` | `"accept"` | no | "accept" delivers messages from the user's other sessions to Claude without the approval hold that otherwise applies to a sender that is not in bypass mode, so it is written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/config/approval_policy` | `"never"` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/config/sandbox_mode` | `"danger-full-access"` | no | they grant permissions and suppress confirmation prompts (bypassPermissions, never, danger-full-access), so they are written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/config/mcp_servers.ai-memory.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `memory-owner` installing `ai-memory` |
| `codex/config/mcp_servers.context-mode.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `context-supply` installing `context-mode` |
| `codex/config/mcp_servers.jcodemunch.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `code-index` installing `jcodemunch` |
| `codex/config/mcp_servers.semble.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `code-search` installing `semble` |
| `codex/config/mcp_servers.chrome-devtools.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of the chrome-devtools MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `playwright-cli` installing `Chrome DevTools MCP 1.10.1 (one stdio MCP server, chrome-devtools, in both clients; it also serves browser diagnostics)` |
| `codex/config/projects."${PROJECT_ROOT}".trust_level` | `"trusted"` | no | a trusted project's own .codex/config.toml layers load and Codex asks nothing about the folder, so the grant is written only with --with-authorization-settings and never over a value the file already has | - |
| `codex/stack-worker/mcp_servers.ai-memory.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `memory-owner` installing `ai-memory` |
| `codex/stack-worker/mcp_servers.socraticode.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `code-search` installing `SocratiCode` |
| `codex/stack-worker/mcp_servers.headroom.default_tools_approval_mode` | `"approve"` | no | a tool approval mode of "approve" makes Codex run every tool of that MCP server without asking, so it is written only with --with-authorization-settings, only while the slot that wires the server installs it, and never over a value the file already has | slot `output-compression` installing `headroom` |

| Project agent | MCP servers of its tools that are not wired | Skills the plan does not install |
| --- | --- | --- |

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 70 of 70 lines stay):

```text
```

## Addendum 2026-10-05: user-facing local time

The [local-time decision](2026-10-05-user-facing-local-time.md) adds one sentence to the portable Claude block (a Core rule bullet) and to the Codex block's `session-lanes` lines. The piece tables above are unchanged. The current instruction projection follows; earlier dated projections keep their own counts.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 59 of 59 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 70 of 70 lines stay):

```text
```

## Amendment 2026-10-07: #803 landing projection

The one authorized landing rebase combines the existing local-time instruction with the SKILL.md
RTK exception. The native managed-block renderer measures 7,798 compact bytes and 8,864 rendered
bytes; the protected pre-RTK prefix and its local-time provenance stay as main pinned them.
The current source-only `new_wsl_client_config.py --check --markdown` inventory follows.
All earlier decided text, local-time addendum and historical projections remain intact.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 59 of 59 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 71 of 71 lines stay):

```text
```

### Amendment 2026-10-07 — J819e current instruction inventory

The native `new_wsl_client_config.py --check --markdown` now counts the two navigation lines
outside the unchanged top-rule block. This current generated inventory supersedes earlier
line-count projections. The decided configuration policy and historical inventories remain intact.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 58 of 58 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 73 of 73 lines stay):

```text
```

### Amendment 2026-10-07 — #819 landing current instruction inventory

The authorized landing composition preserves main's local-time addendum and every earlier
decided projection. The native source-only formatter below reflects the accepted
post-exception trim and unchanged navigation guidance; it supplies no host apply.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 59 of 59 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 74 of 74 lines stay):

```text
```

### Amendment 2026-10-07 — instruction-core current instruction inventory

The [instruction-core decision](2026-10-07-instruction-core.md) trims both instruction
sources, so `new_wsl_client_config.py --write-blocks` rewrote both carriers. The native
`new_wsl_client_config.py --check --markdown` inventory below supersedes the earlier
line-count projections. The three tables above are unchanged and no unit is left out.
That decision also supersedes part of the "Instruction lines" item above: the GPT
Researcher line leaves both sources, and the Codex messaging lines move to the
workflow README behind a pointer. The rest of the decided configuration policy and
the historical inventories remain intact; this amendment supplies no host apply.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 55 of 55 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 72 of 72 lines stay):

```text
```

### Amendment 2026-10-08 — philosophy-only current instruction inventory

On 2026-10-08 the owner directed that both instruction sources keep only the
research-convergence philosophy, so `new_wsl_client_config.py --write-blocks` rewrote
both carriers. The Claude source keeps one evidence-backed line beside it (the
StructuredOutput sentence), and the Codex source's RTK text is now rtk-ai/rtk v0.51.0's
default awareness paragraph ([philosophy-only record](2026-10-08-philosophy-only-rules.md)).
The native `new_wsl_client_config.py --check --markdown` inventory below supersedes the
2026-10-07 one. The three tables above are unchanged and no unit is left out. The rest
of the "Instruction lines" item above, the context-mode and semble lines, also leaves
both sources. The ai-memory routing sentence leaves them too, so the map's
`dependent_sentences` list is empty. The same change adds two wired pieces:
`codex/config/features.tool_suggest` (practice, `false`) and
`codex/omniroute/model_context_window` (through the gateway slot). Today: 400 pieces,
360 wired (208 practice, 152 through a slot), 24 not wired (0 through a slot that does not
install, 24 by their own entry) and 16 authorization pieces. The historical inventories
remain intact; this amendment supplies no host apply.

`examples/claude-native/CLAUDE.md`, written to `adoption/new-wsl/claude-user-instructions.md` (0 unit(s) left out; 10 of 10 lines stay):

```text
```

`adoption/templates/codex.AGENTS.template.md`, written to `adoption/new-wsl/codex-user-instructions.md` (0 unit(s) left out; 21 of 21 lines stay):

```text
```
### Amendment 2026-10-08 — NativeStack2604 shell identity

CC065432Z adds `WSL_DISTRO_NAME = "NativeStack2604"` to the explicit Codex
environment so host-guarded scripts retain the distribution identity under
`inherit = "none"`. The native `new_wsl_client_config.py --check --json`
command returned 0 and supplies these current counts: Today: 401 pieces,
361 wired (209 practice, 152 through a slot), 24 not wired (0 through a slot that does not
install, 24 by their own entry) and 16 authorization pieces. Earlier dated
counts remain historical. This is render consistency, without a host apply.

### Declared test changes — PR #846 (2026-10-08)

CC115648Z (2026-10-08 11:56:48Z) rules these two changed expectations under
[`docs/command-center.md`, Landing](../command-center.md#landing). The old
contracts are from PR base `7a3637f5`; the new contracts are present at
`20e52faf`. This declaration records the existing changes.

1. `tests.test_adoption_bootstrap_macos.TokenEfficiencyPlanTests.test_the_headroom_plan_line_names_the_wheel_install_uv_tool_verifies`

   The expected plan line follows the Headroom version, macOS arm64 wheel and
   SHA256 in [`adoption/pins-macos-arm64.json`](../../adoption/pins-macos-arm64.json).
   The test accepts whitespace between plan columns. Old expected line:

   ```text
   plan headroom 0.37.0 uv-tool headroom_ai-0.37.0-cp310-abi3-macosx_11_0_arm64.whl sha256=b4392f68a8d02d74c62c1734cf5bf327511dcc72678f01669f44f0612944d59c
   ```

   New expected line:

   ```text
   plan headroom 0.40.0 uv-tool headroom_ai-0.40.0-cp310-abi3-macosx_11_0_arm64.whl sha256=f7b0186ad5e76d5c8f75e5de6c57e001637258ead75481575ccca4d57557f5fb
   ```

   This matches the Headroom 0.40.0 upgrade in Window U, the vendor's
   [0.40.0 release](https://pypi.org/project/headroom-ai/0.40.0/), and the
   [recorded native version readback](../../evidence/receipts/2604-drift-version-readback-20261008.json).
   The wheel suffix, exact digest, successful plan and no-download assertions
   remain required.

2. `tests.test_new_wsl_client_config.RenderTests.test_the_codex_config_meets_what_the_codex_home_tool_requires`

   The old sorted `shell_environment_policy.set` key list was
   `DOCKER_HOST, HOME, LANG, MCP_AUTO_OPEN_ENABLED, PATH, RTK_TELEMETRY_DISABLED, TERM, TMPDIR, XDG_RUNTIME_DIR`.
   The new list is
   `DOCKER_HOST, HOME, LANG, MCP_AUTO_OPEN_ENABLED, PATH, RTK_TELEMETRY_DISABLED, TERM, TMPDIR, WSL_DISTRO_NAME, XDG_RUNTIME_DIR`,
   with the added assertion `WSL_DISTRO_NAME == "NativeStack2604"`.
   `inherit == "none"` remains required. The new contract follows
   [`adoption/new-wsl/templates/codex.config.additions.toml`](../../adoption/new-wsl/templates/codex.config.additions.toml)
   and preserves the distribution identity checked by
   [`accept-trading-2604.sh:49`](../../blueprints/us-equities/runtime-2604/accept-trading-2604.sh#L49).
   CC115648Z records that the host fix was applied on 2026-10-08, confirmed
   HOST-OK in a fresh session, and closes readiness-runner's host-guard gap.
   That confirmation is CC-recorded host evidence; this amendment is source review.

## Addendum 2026-10-08: coordinator research-routing hook

CC correction #76 adds three wired practice pieces: the research-routing guard's
PreToolUse handler, its UserPromptSubmit reset handler and its checksum-bound
copied hook file. The native `new_wsl_client_config.py --check` at the reviewed
integration reports this updated projection; earlier dated counts above remain
historical observations. The hook scope, producer adapter, test contracts and
post-landing application are in
[the coordinator research-routing decision](2026-10-08-coordinator-research-routing.md).

Today: 404 pieces, 364 wired (212 practice, 152 through a slot), 24 not wired
(0 through a slot that does not install, 24 by their own entry) and 16 authorization
pieces. The existing `authorization: 16`, and 24 pieces are not wired, remain
unchanged. This is the repository wiring projection, not fresh host acceptance.

## Addendum 2026-10-08: QMD native shared HTTP projection

Both portable client specifications follow QMD 2.8.3's supported shared HTTP
transport at `facd35e01359e59d938bc9418e93fb9318addee3`. The practice, native
two-Codex pilot, service-owned lexical index, lifecycle and inverse are in
[the QMD transport decision](2026-10-08-qmd-shared-mcp.md). The CLI registration
contract follows the installed Claude 2.1.294 HTTP commands and Codex 0.161.0
native URL registration; no live user configuration is written by this projection.

The map keeps the complete Claude QMD server in its existing QMD slot, removes
the obsolete stdio command override, and uses the existing Codex QMD wildcard
for its URL. The unused Codex command-leaf rule is retired. Every other map entry,
server and generated instruction carrier keeps its prior scope. Native
`new_wsl_client_config.py --check --json` reproduces the following dated counts;
earlier projections above remain historical observations.

Today: 403 pieces, 363 wired (212 practice, 151 through a slot), 24 not wired
(0 through a slot that does not install, 24 by their own entry) and 16 authorization
pieces. This is repository source consistency, not fresh native-client, model or
provider acceptance. The existing Inspector plan warnings remain separate.

## Addendum 2026-10-08: Claude native SocratiCode pairing

The same-command Claude user/plugin projection follows SocratiCode v1.16.0's
Claude-specific MCP file and version setting. The settings pin, plugin and
marketplace share the code-search owner gate; the manual registration keeps its
socraticode identity and the complete seventeen-setting carrier. Portable
namespace, startup-resume and temporary-directory defaults remain explicit.
Codex retains its independently selected platform version through the shared
template rather than a fixed map argument override. The folded code-graph
registration alias is codebase-memory-mcp while its slot owner remains
codebase-memory. Earlier dated projections above remain historical.

The native repository-only check reports: Today: 409 pieces, 369 wired
(212 practice, 157 through a slot), 24 not wired (0 through a slot that does not
install, 24 by their own entry) and 16 authorization pieces. The existing
`authorization: 16`, and 24 pieces are not wired, remain unchanged. This is
source consistency, not a fresh client session or native installation. The
same-command contract, source pins, pending direct log citation and draft-hunk
reconciliation are recorded in
[the dated alignment decision](2026-10-08-claude-mcp-template-alignment.md).
