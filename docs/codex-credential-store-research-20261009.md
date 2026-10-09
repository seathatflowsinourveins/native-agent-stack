# Codex OS credential-store mode: source research

This is research-only at `openai/codex` rust-v0.162.0, commit
`c1382380de69521303b416720a52f42d51af6248`. The owner's effective store,
credential file, keyring availability and authentication were not inspected
or changed. The keyless review trial does not qualify an OS credential store.

[Official OpenAI authentication documentation](https://developers.openai.com/codex/auth/#credential-storage)
names `cli_auth_credentials_store`. The pinned
[enum](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/config/src/types.rs#L133)
defaults to `file` and supports four modes:

| Mode | Behavior established by pinned source |
| --- | --- |
| `file` | Persist under `CODEX_HOME`; this is the enum default. |
| `keyring` | Use the secure backend and propagate its failures. Direct-backend loading does not import the credential file. |
| `auto` | Try secure storage, then read the file on a missing entry or read error; a secure-save error falls back to a file save. |
| `ephemeral` | Use process-local memory storage. |

The backend selection is explicit in
[login/src/auth/storage.rs:596–626](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/login/src/auth/storage.rs#L596).
The `auto` implementation at
[478–527](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/login/src/auth/storage.rs#L478)
returns a file fallback without performing a secure save. A setting edit alone
therefore does not migrate an existing file. Strict `keyring` requires a
supported owner-operated login/save after the backend is qualified.

A successful direct secure save precedes a best-effort fallback-file removal.
Removal failure emits a warning while save returns success
([315–331](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/login/src/auth/storage.rs#L315)).
Consequently, secure-save success does not prove that a prior plaintext file
was removed. Secure deletion attempts the keyring first, then the file;
a keyring error short-circuits the file step
([334–344](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/login/src/auth/storage.rs#L334)).

Reverting the mode to `file` is not a credential rollback. The former file may
have been removed, and file mode does not export a secure entry. A file-mode
login/save creates a file without cleaning the secure entry. The owner must
plan reauthentication and cleanup in each direction rather than copy tokens.

On the Linux build, the pinned
[keyring-store/Cargo.toml:12–18](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/keyring-store/Cargo.toml#L12)
selects `linux-native-async-persistent` and `crypto-rust`. Its locked dependency
is keyring 3.6.3. That dependency documents
[kernel keyutils plus D-Bus Secret Service](https://docs.rs/keyring/3.6.3/keyring/keyutils_persistent/index.html),
with Secret Service supplying persistence beyond reboot. Its
[headless guidance](https://docs.rs/keyring/3.6.3/keyring/secret_service/index.html#headless-usage)
describes setup constraints. A usable service and unlocked collection require
host qualification by the owner; this note supplies none. A Linux-target
binary under WSL follows this branch, rather than automatically using Windows
Credential Manager.

Secure storage also has two payload layouts: directly in the OS keyring, or
in an encrypted local secrets file with its encryption key in the keyring.
The enum's platform default and effective feature-controlled selection are
distinct: see
[types.rs:165–183](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/config/src/types.rs#L165)
and [config/auth_keyring.rs](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/core/src/config/auth_keyring.rs#L14).
This research does not invent an `auth_keyring_backend` user setting or infer
the owner's active feature state. Enforced configuration requirements can
also constrain the effective mode.

The schematic owner-only proposal is `cli_auth_credentials_store = "keyring"`
after qualifying the backend and planning a supported login/save and cleanup
verification. Existing keys must be replaced rather than duplicated. Choosing
`auto` is a different decision because its fallback permits file credentials.
The [proposal fragment](../evidence/artifacts/codex-review-trial-20261009/owner-proposals.md)
is unapplied. No sign-in file or credential value was read, copied, moved or
printed, and no store or login probe ran.
