# New-machine bootstrap (ordered)

One page, one order. Each step names the [manifest](manifest.json) `recipe_map`
entry or component it uses instead of repeating its command. Read
[the adoption reference](README.md) first for profile selection and the four
native verification tiers; this page only sequences the steps for a machine
that has never run this stack. Read the platform page for the chosen
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

2. **Run the platform bootstrap script.** `adoption/bootstrap-linux.sh --profile <id>`
   (added by a sibling worker in this same integration branch; not present in
   this unit's owned paths) installs the selected profile's components using
   each entry's `recipe_map` path. Inspect the script before running it on a
   new host; it installs only what the chosen `--profile` selects.

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
   python3 tools/adoption/render_config.py --host <host> --check   # compare against live configs before overwriting them
   ```
   Templates are in [`adoption/templates/`](templates/): `claude.settings.template.json`,
   `codex.config.template.toml` (user-level `~/.codex/config.toml`), and
   `project.codex.config.template.toml` (project-level `.codex/config.toml`).
   `--check` prints a unified diff and exits 1 on any byte difference; a pure
   JSON-formatting difference is called out explicitly in its output.

5. **Services.** Start only the selected profile's services using the native
   process-lifecycle guide in [`adoption/lifecycle.md`](lifecycle.md#native-client-integration-and-process-lifecycle):
   `systemctl --user` on Linux/WSL2 (owned units only; never stop the shared
   MCPorter daemon to "clean up" another component), `launchctl` on macOS
   (table in [the macOS page](platforms/macos-arm64.md#launchd-services); not
   yet exercised on a Mac).

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
   has neither.

Every step above is guidance; running or validating this page does not itself
execute anything (`adoption/lifecycle.md`, "This guide supplies future-host
commands; reading or validating it does not run those commands").
