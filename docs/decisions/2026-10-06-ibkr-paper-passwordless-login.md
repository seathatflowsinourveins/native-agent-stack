# Decision: the IBKR paper gateway signs in by itself (2026-10-06)

**Status:** decided by the user at about 01:50Z on 2026-10-06 (9:50 PM EDT on
2026-10-05). The command center applied it on NativeStack2604 the same night.
This record, the inventory rows, the checker rule and the adopted recreate
script bring the repository in line with that host.

**The user's decision, described.** The user prefers a passwordless,
LLM-native and frictionless workflow, and on 2026-10-06 extended that
preference to the IBKR paper login: the paper gateway should sign in without
anyone typing the login. By the user's standing rule, this record describes
the decision and does not quote it.

**North-star action served:** unattended, broker-specific paper operation for
IBKR, the NautilusTrader 2.0.0rc5/IBKR destination selected in
[`catalogs/us-equities/runtime-target.json`](../../catalogs/us-equities/runtime-target.json),
under [`docs/paper-lane-policy.md`](../paper-lane-policy.md).

**Supersedes, for the IBKR paper gateway only:**
- the `ibkr-gateway` row of [`docs/secret-storage.md`](../secret-storage.md),
  which said the login is typed in at login and nothing is stored (line 28 at
  `ecfa1127`);
- the matching `interactive_login` row of
  [`adoption/credential-inventory.json`](../../adoption/credential-inventory.json);
- the IB Gateway part of item 1 of
  [`2026-09-24-secret-storage.md`](2026-09-24-secret-storage.md), which keeps
  native sign-ins "in each tool's own store".

Everything else in that decision stands, including its threat model.

## Decision

1. **The paper login is stored.** Three files sit in the store
   (`${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`, mode `0700`,
   outside every worktree). Each file is mode `0600` with one link, and
   commands reach it through its pointer:

   | Pointer | Inventory id | Holds |
   | --- | --- | --- |
   | `IBKR_PAPER_LOGIN_ENV` | `ibkr-gateway` | the paper user ID: one `TWS_USERID=` line in docker env-file syntax |
   | `IBKR_PAPER_TWS_FILE` | `ibkr-gateway-tws-password` | the paper password alone |
   | `IBKR_PAPER_VNC_FILE` | `ibkr-gateway-vnc-password` | the password of the gateway's VNC screen (127.0.0.1:5900) |

   The user typed each value at a private prompt in their own terminal, the
   two passwords at hidden prompts and the user ID at a visible one, so no
   value went through an agent, a chat or a command line. The shell startup
   file exports the three pointers, which hold paths only.
2. **The container loads them; no agent does.**
   [`ibkr-gateway-recreate-durable.sh`](../../blueprints/us-equities/runtime-2604/ibkr-gateway-recreate-durable.sh)
   runs the digest-pinned `ghcr.io/gnzsnz/ib-gateway:10.51.1b` image (IBC
   3.24.2) with `--env-file "$IBKR_PAPER_LOGIN_ENV"`. It mounts the two
   password files read-only at the paths that `TWS_PASSWORD_FILE` and
   `VNC_SERVER_PASSWORD_FILE` name inside the container.
3. **The owner under rootless Docker.** The image runs as uid 1000, and
   rootless Docker maps the user to container root, so a `0600` file the user
   owns is unreadable inside the container. The script chowns the two
   password files to `1000:1000` inside the user namespace and leaves their
   mode at `0600`. Their host owner is then the user's first `/etc/subuid`
   start plus 999. `scripts/credential_status.py` accepts that owner only for
   the two rows that declare `rootless_container_uid: 1000`. It derives the
   start from `/etc/subuid` at run time, still requires mode `0600` and one
   link, and never opens the files. The login env file stays the user's,
   because the docker CLI reads it on the host.
4. **A weekly second factor.** The script sets `AUTO_RESTART_TIME` to
   11:00 PM New York time, with `TWOFA_TIMEOUT_ACTION=restart`,
   `RELOGIN_AFTER_TWOFA_TIMEOUT=yes` and
   `EXISTING_SESSION_DETECTED_ACTION=primary`. IBC's AutoRestart restarts the
   gateway each night without re-authentication, so one session runs all
   week. The user approves IBKR's second-factor prompt on their phone about
   once a week, and again after a cold start of the gateway.
5. **Values never reach workers.**
   - `tools/credentials/credential_run.py` never injects the three rows
     (`private_file`), and strips the three pointers from every command it
     starts.
   - `tools/credentials/set_credential.py` never writes them.
   - `scripts/hooks/secret_path_guard.py` refuses a reader on each pointer
     and any `TWS_USERID` reference. `TWS_USERID` joins `must_not_be_set`.
   - Codex shells keep `inherit = "none"`.
6. **Pointer names.** The `IBKR_PAPER_*` names are kept as documented pointer
   names. No rename is needed, and the user has no shell startup change to
   make.
   - [`docs/secret-storage.md`](../secret-storage.md) lists the names that
     stay unset as `TWS_*` and `IBKR_ACCOUNT_ID` ("These should stay unset on
     the host"), and pointers as file paths that the shell startup file
     exports ("Picking up in a new session"). The three names match neither
     unset rule.
   - `credential_status.py` compares `must_not_be_set` by exact name
     (`TWS_USERNAME`, `TWS_PASSWORD`, `TWS_ACCOUNT`, `IBKR_ACCOUNT_ID`, and
     now `TWS_USERID`), so it never flagged them.
   - The only prefix rule is the gap-wave2 probe
     `blueprints/gap-wave2-20260923/us-equities__security-supply-chain/worker_env_check.sh`
     (lines 24, 49 and 61). It lists `^(APCA|ALPACA|TWS|IBKR)_` names by
     name only and asserts nothing. It is the recorded command of that
     wave's receipts 8 and 14, so it stays unchanged. A rerun lists these
     three paths among its names.
   - The inventory row now states the exemption.
7. **Records stay private.** Full `docker inspect` output holds the user ID.
   Each run writes its records into a new `0700` directory of `0600` files
   under `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/ibkr-gateway/`.
   The script refuses, before any change, when that directory would be
   inside a Git worktree, while an API client is connected to
   127.0.0.1:4002, when `ss` is missing, or under a rootful daemon. It keeps
   the previous container stopped for rollback under a
   `-pre-durable-<stamp>` name.

## SOTA sources

- **gnzsnz/ib-gateway-docker** at `8a22deaa6cab86f9ad5c86ff4f0d6efbef718f10`,
  the `ibgateway-latest@10.51.1b` release tag (`gh api
  repos/gnzsnz/ib-gateway-docker/git/matching-refs/tags/ibgateway-latest@10.51`,
  2026-10-06). From
  [README.md](https://github.com/gnzsnz/ib-gateway-docker/blob/8a22deaa6cab86f9ad5c86ff4f0d6efbef718f10/README.md):
  - "Configuration" (L175-L203): `TWS_USERID` L181, `TWS_PASSWORD_FILE`
    L183, `VNC_SERVER_PASSWORD_FILE` L190, `TWOFA_TIMEOUT_ACTION` L191,
    `AUTO_RESTART_TIME` L195 ("does not require daily 2FA validation"),
    `RELOGIN_AFTER_TWOFA_TIMEOUT` L199, `EXISTING_SESSION_DETECTED_ACTION`
    L200 and `TWS_SETTINGS_PATH` L203.
  - "Credentials" (L511-L545): the image stores no credentials, and a
    defined `_FILE` variable names the file a credential is read from.

  `latest/Dockerfile`: `IBC_VERSION=3.24.2` (L13) and `USER_ID` 1000 (L67).
- **IbcAlpha/IBC** `3.24.2`, at `2be2ecd05d7707f97479fda9ad098fdcc15ab807`.
  [userguide.md L586-L601](https://github.com/IbcAlpha/IBC/blob/2be2ecd05d7707f97479fda9ad098fdcc15ab807/userguide.md#L586-L601):
  AutoRestart restarts "without requiring re-authentication", giving "a
  single authentication at the start of the week", and the session
  credentials expire on Sunday. Its "Second Factor Authentication" section
  (L508-L551) covers the relogin and timeout settings.
- **rootless-containers/rootlesskit** `v3.1.0`, at
  `62d2101fbbe4f79bc845a337c4e868d27ff602c9`. This host's rootless Docker
  Engine 29.8.2 reports rootlesskit 3.1.0.
  - [`pkg/parent/parent.go` L401-L432](https://github.com/rootless-containers/rootlesskit/blob/62d2101fbbe4f79bc845a337c4e868d27ff602c9/pkg/parent/parent.go#L401-L432):
    container uid 0 maps to the user, and the user's subordinate ranges
    follow from container uid 1. Container uid 1000 therefore maps to the
    first range's start plus 999.
  - L363-L385: the default source tries `getsubids`, then `/etc/subuid`.
  - [`pkg/parent/idtools/idtools.go` L48-L85](https://github.com/rootless-containers/rootlesskit/blob/62d2101fbbe4f79bc845a337c4e868d27ff602c9/pkg/parent/idtools/idtools.go#L48-L85):
    a line matches by uid or name, and a malformed line fails the whole file.

  The checker mirrors that parser.
- **ShellCheck** 0.11.0 (the `shellcheck-py` wheel) found nothing in the
  adopted script.

## Evidence

| Claim | Evidence class | Command / source |
| --- | --- | --- |
| After the cold boot, the gateway signed in by itself at 02:25:37Z on 2026-10-06 (IBC log: "Login has completed") | reported by the command center; not observed again for this record | the command center's handover of 2026-10-06 |
| On NativeStack2604 at 03:16:58Z, all three rows are `ok`; the two password files report `owner=rootless_container_user`, and the three files are no longer undeclared store files (at `ecfa1127` they were) | host execution, output in the pull request, no receipt file | `python3 scripts/credential_status.py --json`, exit 0 |
| The mapped owner is accepted only for the two declared rows; any other owner, a wrong mode or a second link is refused; no credential file is opened | synthetic fixtures | `python3 -m unittest tests.test_credential_status` |
| The recreate script refuses before any change, and keeps its records 0600 outside every worktree | synthetic stubs; the real Docker daemon is never reached | `python3 -m unittest tests.test_ibkr_gateway_recreate` |
| The guard refuses readers on the pointers and is a superset of its pinned baselines | local integration | `python3 -m unittest tests.test_secret_path_guard`: 90 tests, exit 1 on NativeStack2604. The one failure, `test_host_profile_copy_is_verbatim`, compares this host's installed user-scope guard (still the base pin `fd516d8b`) with the changed guard; CI skips it, and it passes once the host reinstalls the guard |

## Accepted risk, paper only

- The guard stops accidental exposure and is not a boundary
  ([2026-09-24 threat model](2026-09-24-secret-storage.md#threat-model-stated-plainly)).
  Docker is not a modelled reader, so these pass the guard and are recorded
  as expected pass-throughs:
  - a container that mounts a pointer's file;
  - `docker exec` into the gateway;
  - a bare `docker inspect` of the gateway container, whose `Config.Env`
    holds `TWS_USERID`.

  The login env file is readable by the user's own uid. This record accepts
  that residual for the paper account, as the 2026-09-24 decision accepts it
  for paper keys. No live login is ever stored under this decision.
- A host's user-level guard is a frozen copy. Until its profile is
  reinstalled from a checkout with this change, readers on the IBKR pointers
  pass there. The two password files stay unreadable to the user's uid, but
  the login env file does not.
- The weekly approval is manual by design. If it is missed, the gateway
  retries (`TWOFA_TIMEOUT_ACTION=restart`, `RELOGIN_AFTER_TWOFA_TIMEOUT=yes`)
  and stays signed out until it is approved.
- Some hosts take subordinate ranges from an NSS provider instead of
  `/etc/subuid`. There the checker fails closed and reports
  `foreign_owner`; it never accepts a wrong owner.

## Alternatives considered

- **Keep typing the login at each sign-in over VNC,** the previous policy.
  The user's decision replaces it: an unattended gateway could not recover
  after a restart.
- **Pass the password as `TWS_PASSWORD` in the environment.** That puts it
  in the container's `Config.Env` and every `docker inspect`. The `_FILE`
  form keeps it out, as the upstream "Credentials" section recommends. The
  image has no `_FILE` form for `TWS_USERID`, so the user ID stays an
  environment value.
- **Compose `secrets:`,** the README's sample. It uses the same read-only
  file mounts. The host runs one container through the recreate script, so
  Compose adds nothing.
- **The kernel keyring.** It is memory only and lost at every restart
  ([2026-09-29-key-management.md](2026-09-29-key-management.md)), which
  defeats an unattended restart.
- **Rename the pointers to drop the broker prefix,** as `PAPER_ENV_FILE`
  does. No documented rule asks for that, and a rename would mean a shell
  startup edit for the user and a host that no longer matches the
  repository. Kept as documented pointer names.

## What would overturn it

- A stored value appears in a transcript, log, receipt, chat or worker
  environment. Rotate at once, then revisit this decision.
- IBKR's second-factor or session rules change, so that AutoRestart no
  longer holds a week-long session or the stored login no longer suffices.
- A live account comes into scope. A live login needs its own decision and
  is never stored under this one.
- The gateway runs on a rootful daemon, where container uid 1000 is a real
  host account. The chown rule and the mapped-owner rule then no longer hold,
  and the script refuses.
- An upstream image or IBC release changes `TWS_PASSWORD_FILE`,
  `VNC_SERVER_PASSWORD_FILE` or `AUTO_RESTART_TIME`, or adds a file form for
  `TWS_USERID`. A file form would keep the user ID out of the container
  environment, so adopt it.
- The user withdraws the preference.

## Residuals and follow-ups

- The two private-prompt scripts that wrote the files live outside the
  repository. Adopting them would make rotation reproducible on a new host.
- The host check above has no receipt file.
- The trading lane acknowledges this `lane:shared` change after the
  NativeStack relaunch.
