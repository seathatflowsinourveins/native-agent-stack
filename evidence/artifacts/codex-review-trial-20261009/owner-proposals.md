# Unapplied owner and command-center proposals

Sources: [Codex rust-v0.162.0](https://github.com/openai/codex/tree/c1382380de69521303b416720a52f42d51af6248),
`codex-rs/config/src/types.rs:133–146` and `codex-rs/login/src/auth/storage.rs`;
[codex-plugin-cc v1.0.6](https://github.com/openai/codex-plugin-cc/tree/db52e28f4d9ded852ab3942cea316258ae4ef346),
`README.md`, `plugins/codex/commands/review.md` and its session lifecycle hooks.
These fragments are schematic; no owner configuration file was read to
construct them. They are not patches against inspected effective settings.

## Credential-store fragment: owner decision only

```diff
--- owner-controlled Codex config.toml (schematic)
+++ proposed setting, not applied
@@
+cli_auth_credentials_store = "keyring"
```

Replace an existing key if present. This strict mode requires qualifying the
host's secure backend, planning supported reauthentication and verifying
cleanup without reading credential contents. A mode change alone does not
migrate a file. Reverting this line does not export an OS-store entry or
restore a removed file. The lane does not execute the switch, login, logout,
keyring probe or any credential-file operation.

## Bridge-disable fragment: held, not recommended by this trial

The trial verdict is `retain-bridge`. A direct Codex caller can use its native
review command, but the required Claude integration and automatic routing
parity are open. If a later owner decision authorizes removal after those
gates, the corresponding settings fragment would be:

```diff
--- owner-controlled Claude settings.json enabledPlugins entry (schematic)
+++ conditional command-center proposal, not applied
@@
-"codex@openai-codex": true
+"codex@openai-codex": false
```

The installed Claude client exposes the vendor `plugin disable` and `plugin
enable` commands. These are the supported configuration operation and its
inverse; neither was executed. The current plugin, its registrations, the
PATH identity launcher and all user-level client files remain unchanged.
