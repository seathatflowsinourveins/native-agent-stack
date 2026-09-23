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
python3 scripts/release_due.py   # on the default branch (added after v2026.09.23): steps main documents that the pinned release lacks
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
was added after `v2026.09.23`, so it runs here, on the default branch, before
the checkout. After checkout, follow the documents in your checkout.

The pages here name the release a step was written against. "Added after
`vT`" means release `vT` lacks the file that step uses (a path in
`release_due.py`'s `due` list); "changed after `vT`" means the file exists at
`vT` but behaves as the note says there, not as main documents it. If your
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

If downloading the release archive from an Actions run instead of
`git clone` (e.g. no local git), verify its attested provenance before use:
```sh
gh attestation verify native-agent-stack-<release_commit>.tar.gz \
  --repo seathatflowsinourveins/native-agent-stack \
  --signer-workflow seathatflowsinourveins/native-agent-stack/.github/workflows/publish-catalog.yml
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
   [--configure-claude-user-profile]` on Linux/WSL2, or
   `adoption/bootstrap-macos.sh --profile <id> [--skip-system-packages]
   [--allow-unpinned <id,id,...>] [--plan] [--configure-claude-user-profile]`
   on macOS (`ECO_INSTALL_ROOT` env,
   default `$HOME/.local/share/codex-ecosystem`; writes
   `$ECO_INSTALL_ROOT/installed-versions.txt`; both scripts exit 2 usage,
   1 guard/refusal, 0 success, 3 when a selected component has no pin and was
   not named in `--allow-unpinned`, and 4 when a prerequisite is still missing
   after the system-package step — with `--skip-system-packages` no
   `apt-get`/`brew install` is attempted and the check lists what is missing;
   `--plan` resolves the profile's pins with no network and still exits 1 on a
   null `sha256`) — installs the selected profile's components
   using each entry's `recipe_map` path. Inspect the script before running it
   on a new host; it installs only what the chosen `--profile` selects.

   The scripts install only components that have a pin in
   [`pins-linux-x86_64.json`](pins-linux-x86_64.json) or
   [`pins-macos-arm64.json`](pins-macos-arm64.json). On main that covers
   `foundation-cpu` on Linux/WSL2 and `macos-arm64-foundation` on macOS in
   full; every other profile is partly or wholly unpinned (the "Linux pins" and
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

   The macOS script and pins changed after `v2026.09.23`. At `v2026.09.23`,
   `adoption/bootstrap-macos.sh` installs only a missing `jq` through Homebrew
   (install the other formulae on
   [the macOS page](platforms/macos-arm64.md#prerequisites) yourself first),
   `adoption/pins-macos-arm64.json` has no `socraticode` pin (the script skips
   it by default, so `macos-arm64-foundation` installs 7 of 8), no pinned
   darwin binary for Codex or Claude Code (npm resolves those unverified) and
   no embedding-model pin. Linux/WSL2's script and pins are the same at
   `v2026.09.23` as on main.

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
   `--check`'s `project.codex.config.toml` comparison targets the project
   being onboarded (`$PROJECT_ROOT`, e.g. `agent-lab`), never this catalog
   checkout, which has no `.codex/config.toml` of its own and will always
   report "live file not found" if `--live-codex-project` is omitted; pass it
   explicitly, or export `ADOPTION_PROJECT_ROOT` before running (see
   `tools/adoption/render_config.py --help`). `--check` prints a unified diff
   and exits 1 on any byte difference; a pure JSON-formatting difference is
   called out explicitly in its output.

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
   do not apply; `adoption/manifest.json` `policy.historical_acceptance_transfers:
   false` means none of that state should be read as re-qualifying the new
   host's own acceptance evidence.

4a. **Claude user-scope profile.** After step 3's native `claude` sign-in
   (this step is a no-op, not a failure, without it -- the MCP registration
   sub-step below needs a working `claude` binary), install this catalog's
   Claude Code user-scope assets with
   [`tools/adoption/install_claude_profile.py`](../tools/adoption/install_claude_profile.py):
   ```sh
   python3 tools/adoption/install_claude_profile.py            # guard + agents + MCP servers
   python3 tools/adoption/install_claude_profile.py --dry-run   # report only, write/register nothing
   python3 tools/adoption/install_claude_profile.py --only mcp  # just the MCP step
   ```
   Both platform bootstrap scripts also accept
   `--configure-claude-user-profile` to run this automatically as their own
   last step (still only meaningful after sign-in; run it manually
   afterward otherwise, exactly as the script's own closing message says).
   Three idempotent sub-steps, each safe to re-run:
   - **guard hook**: copies [`adoption/hooks/claude/effort-default-guard.py`](hooks/claude/effort-default-guard.py)
     to `~/.claude/hooks/effort-default-guard.py`, refusing to install unless
     its sha256 matches [`adoption/hooks/claude/SHA256SUMS`](hooks/claude/SHA256SUMS);
     skipped if the installed copy already matches.
   - **agents**: copies the five [`adoption/agents/claude/*.md`](agents/claude/)
     files verbatim to `~/.claude/agents/`; skipped per-file when already
     byte-identical.
   - **MCP servers**: for each entry in
     [`adoption/mcp/claude-user.json`](mcp/claude-user.json) (`ai-memory`
     http, `jcodemunch` and `serena` stdio), runs `claude mcp add --scope
     user`; skipped when `claude mcp get <name>` already reports a matching
     transport, command/URL, args and env variable names (values are not
     compared -- the running host owns them).
   Then apply the settings template itself (model, effort, ultracode,
   workflow env, hooks) into the live `~/.claude/settings.json` with
   [`tools/adoption/apply_claude_settings.py`](../tools/adoption/apply_claude_settings.py),
   after rendering it for this host with step 4's `render_config.py --out`:
   ```sh
   python3 tools/adoption/apply_claude_settings.py --template "$RUN_DIR/rendered/settings.json"
   python3 tools/adoption/apply_claude_settings.py --template "$RUN_DIR/rendered/settings.json" --dry-run
   ```
   Backs up the current file (`settings.json.bak.<UTC timestamp>`) before
   writing, refuses to operate through a symlink, deep-merges (template
   scalars win; `modelSettings` merges per-model; `hooks` combine per event,
   de-duplicated by each entry's own `command`; everything else in the live
   file that the template does not mention is kept), writes atomically and
   preserves the original file's mode bits. Never touches `~/.claude.json`
   or any credential store.

5. **Services.** Start only the selected profile's services using the native
   process-lifecycle guide in [`adoption/lifecycle.md`](lifecycle.md#native-client-integration-and-process-lifecycle):
   `systemctl --user` on Linux/WSL2 (owned units only; never stop the shared
   MCPorter daemon to "clean up" another component), `launchctl` on macOS
   (table in [the macOS page](platforms/macos-arm64.md#launchd-services); run
   only on a hosted runner, not yet on a Mac workstation; its launchd
   templates were added after `v2026.09.23`). For the portable guarded runner wrappers used by
   these services, see `adoption/tools/README.md`.

6. **Prerequisite report.** `python3 scripts/adoption_status.py --profile <id> --json`
   reports command presence and recipe-path presence only; it never logs in,
   edits configuration, starts services, or certifies functional acceptance
   (see its own docstring and `adoption/README.md`'s "Native verification
   tiers" table).

7. **Per-host receipt.** Record `evidence/receipts/adoption-<host>-<date>.json`
   using the [`adoption/receipt.json`](receipt.json) schema: `schema_version`,
   `id`, `kind`, `component_ids`, `observed_at_utc`, `status`, `claim`, `scope`,
   `data`. Distinguish `native_cli_e2e` (an actual command ran on this host)
   from `source_review` (documented, not executed) and from a candidate that
   has neither. `scripts/host_receipts.py` (this same step's own recording
   tool, plus `scripts/component_matrix.py`, `scripts/new_host_grand_list.py`,
   `tools/sota-convergence/build_verdicts.py`,
   `scripts/validate_convergence.py` and `scripts/release_due.py`, which was
   added after `v2026.09.23`) needs
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
