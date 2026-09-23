# New-machine bootstrap (ordered)

One page, one order. Each step names the [manifest](manifest.json) `recipe_map`
entry or component it uses instead of repeating its command. Read
[the adoption reference](README.md) first for profile selection and the four
native verification tiers; this page only sequences the steps for a machine
that has never run this stack.

**Step 0, before anything below: get the catalog at its attested release tag.** After checkout, follow the documents in your checkout: main may already describe steps that are not released yet (`python3 scripts/release_due.py` lists them).
```sh
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git
cd native-agent-stack
git checkout "$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_tag'])")"
```
This checks out `adoption/manifest.json` `source.release_tag`
(`v2026.09.23`, or a later tag) at `source.release_commit`
(`bdd04ca50eb781f8366c955f481479b7a7f57cbd`), published with SLSA build
provenance by `.github/workflows/publish-catalog.yml`. Do **not** check out
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
nothing on that page has been executed on a Mac; see
[the acceptance evidence policy](../docs/acceptance-evidence-policy.md)).

1. **Host prerequisites.** Confirm the OS/architecture matches a
   `platform_profiles` entry. Linux/WSL2 needs the packages listed in
   [`recipes/README.md`](../recipes/README.md#paths-pins-and-installation-conventions)
   (`git`, `python3`, `node`, `uv`, and the archive/checksum conventions used by
   every component recipe). macOS needs the Homebrew prerequisites on
   [the macOS page](platforms/macos-arm64.md#prerequisites); that page is
   drafted, not accepted.

2. **Run the platform bootstrap script.** `adoption/bootstrap-linux.sh --profile <id>
   [--skip-system-packages] [--allow-unpinned <id,id,...>]` on Linux/WSL2, or
   `adoption/bootstrap-macos.sh --profile <id> [--skip-system-packages]
   [--allow-unpinned <id,id,...>] [--plan]` on macOS (`ECO_INSTALL_ROOT` env,
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

5. **Services.** Start only the selected profile's services using the native
   process-lifecycle guide in [`adoption/lifecycle.md`](lifecycle.md#native-client-integration-and-process-lifecycle):
   `systemctl --user` on Linux/WSL2 (owned units only; never stop the shared
   MCPorter daemon to "clean up" another component), `launchctl` on macOS
   (table in [the macOS page](platforms/macos-arm64.md#launchd-services); not
   yet exercised on a Mac). For the portable guarded runner wrappers used by
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
