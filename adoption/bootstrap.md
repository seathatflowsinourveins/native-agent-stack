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
   - **guard hooks**: copies [`adoption/hooks/claude/effort-default-guard.py`](hooks/claude/effort-default-guard.py)
     to `~/.claude/hooks/effort-default-guard.py` and the secret guard
     [`scripts/hooks/secret_path_guard.py`](../scripts/hooks/secret_path_guard.py)
     to `~/.claude/hooks/secret_path_guard.py` (the secret guard and its
     settings entries were added after `v2026.09.24.1`), refusing to install either unless
     every sha256 matches [`adoption/hooks/claude/SHA256SUMS`](hooks/claude/SHA256SUMS)
     (paths relative to that file); skipped per file if the installed copy
     already matches.
   - **agents**: copies the seven [`adoption/agents/claude/*.md`](agents/claude/)
     files verbatim to `~/.claude/agents/`; skipped per-file when already
     byte-identical.
   - **MCP servers**: for each entry in
     [`adoption/mcp/claude-user.json`](mcp/claude-user.json) (`ai-memory`
     http, `jcodemunch` and `serena` stdio), renders its `${HOME}` and
     `${ECO_ROOT}` placeholders (`--eco-root`, default `$ECO_INSTALL_ROOT` or
     `~/.local/share/codex-ecosystem`), then runs `claude mcp add --scope user
     <name> [-e KEY=VALUE ...] -- <command> [args...]`; skipped when `claude
     mcp get <name>` already reports a matching transport, command/URL, args
     and env variable names (values are not compared -- the running host owns
     them). A same-named server with a different config is reported and left
     unchanged unless `--replace-mcp` is given.
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
   or any credential store.
   The agent definitions in `adoption/agents/claude/` changed after `v2026.09.23.1`:
   at that tag they declare `effort: medium` (`source-scout`,
   `isolated-builder`) or `effort: high` (`evidence-reviewer`,
   `semantic-evidence-reviewer`, `blind-judge`) instead of `effort: max`
   ([decision](../docs/decisions/2026-09-23-max-effort-default.md)). The
   installer replaces a differing agent file, so rerunning its agents step
   from a checkout that has the change installs the `max` definitions.

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
   Code does):
   ```sh
   python3 - <<'EOF'
   import json, os, pathlib
   reviewed = {  # recipes/README.md rows: context-mode, claude-hud (tag v0.8.0), codex-for-claude
       "context-mode@context-mode": "6f0cc6841c687e754059f36714a11233fda1a02b",
       "claude-hud@claude-hud": "ef5f1c8b167572ad1443c70629763ea8780af96b",
       "codex@openai-codex": "db52e28f4d9ded852ab3942cea316258ae4ef346",
   }
   config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or pathlib.Path.home() / ".claude")
   registry = json.loads((config / "plugins/installed_plugins.json").read_text())
   for key, sha in reviewed.items():
       found = [entry.get("gitCommitSha") for entry in registry.get("plugins", {}).get(key, [])]
       print("ok" if found and set(found) == {sha} else "MISMATCH", key, found or "not installed")
   EOF
   ```
   A `MISMATCH` means this host runs a plugin revision the catalog has not
   reviewed: record the installed `gitCommitSha` in the step 7 receipt instead
   of the recipe's revision, and review it before relying on the plugin.

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
