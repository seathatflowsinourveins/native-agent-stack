# Owner apply and read-back

This is an unexecuted host procedure for the co-op after this PR and the IBKR owner's inventory/security changes land. The lane changes repository files only. Use the user's existing F9 apply authorization; wait for the F9 Codex quiet window before the config writer. Stop on any failed command or reported conflict. Do not override operator values to make the checks pass.

The source and readers follow systemd v259.5 (`b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a`: `man/environment.d.xml:59-74`, `man/systemd.environment-generator.xml:116-121`), Bash's native login startup, and Codex rust-v0.160.0 (`a956835d020762cb2b570053af06f643a11c0ecc`: `codex-rs/protocol/src/shell_environment.rs:100-147`). File installation, backup and exact-name cleanup use the installed GNU coreutils 9.7, grep 3.12 and sed 4.9 commands; their native `--help` options were checked on 2026-10-06. Reference formats are GNU's [cp](https://www.gnu.org/software/coreutils/manual/html_node/cp-invocation.html), [grep](https://www.gnu.org/software/grep/manual/grep.html) and [sed address](https://www.gnu.org/software/sed/manual/sed.html#Addresses) manuals; the remote fetch timed out, so the qualification here rests on the installed commands and synthetic stdin results. Shell sourcing and service restarts are native operations, not a replacement runner. Dagu's adopted unit is `dagu.service` (`native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json:3282,3305`).

The supported scope is conventional HOME/.config and base Codex config. The owner must supply its existing private `adoption/hosts/nativestack2604.json` in the landed checkout: it is deliberately absent from this branch. Do not create a competing host profile. Its HOME must equal the selected login HOME, because `--render` uses that profile while `--apply` and `--check-login-env` rebase to the actual HOME (`native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:tools/adoption/new_wsl_client_config.py:1080-1104,1524-1548`, `tools/adoption/render_config.py:108-115`). The check rejects Bash shadow files and incompatible Codex filters conservatively. Neither active profiles nor custom XDG/CODEX homes are qualified. No credential file is part of the backup or cleanup.

## Apply

Run these commands from the owner's landed checkout, with no credential values in the command or output. The dedicated backup preserves only the four configuration files this procedure may change. Keep `p1_backup` for rollback; it is not a credential backup. A symlink target is a stop condition.

```sh
set -e
p1_repo="$PWD"
p1_work="$HOME/.cache/ns2604-p1-env-apply"
p1_backup="$p1_work/backup-$(date -u +%Y%m%dT%H%M%SZ)"
test "${XDG_CONFIG_HOME:-$HOME/.config}" = "$HOME/.config"
test -z "${CODEX_HOME:-}"
test -z "${CLAUDE_CONFIG_DIR:-}"
python3 -B -c 'import sys; from pathlib import Path; sys.path.insert(0, "tools/adoption"); import render_config; ok = render_config.load_host_values("nativestack2604")["HOME"] == str(Path.home()); print("host_home_matches=" + str(ok).lower()); sys.exit(0 if ok else 1)'
install -d -m 700 "$p1_work" "$p1_backup"
for p1_rel in .config/environment.d/60-native-agent-stack.conf .profile .codex/config.toml .bashrc; do
    test ! -L "$HOME/$p1_rel"
    install -d -m 700 "$p1_backup/$(dirname "$p1_rel")"
    if test -f "$HOME/$p1_rel"; then
        cp -a -- "$HOME/$p1_rel" "$p1_backup/$p1_rel"
    else
        test ! -e "$HOME/$p1_rel"
        touch "$p1_backup/$p1_rel.absent"
    fi
done

# 1. Render the one source and install only its pointer configuration.
python3 -B tools/adoption/new_wsl_client_config.py --render --host nativestack2604 --out "$p1_work/render"
install -D -m 600 "$p1_work/render/60-native-agent-stack.conf" "$HOME/.config/environment.d/60-native-agent-stack.conf"

# 2-3. Refresh the user manager, then restart Dagu once.
systemctl --user daemon-reload
systemctl --user restart dagu.service

# 4. Add the native login reader; the writer preserves operator text.
python3 -B tools/adoption/managed_block.py profile-env --env-file "$HOME/.config/environment.d/60-native-agent-stack.conf"

# 5. F9 adopts the base Codex table and verifies the login-env write.
# Config merge conflicts are preserved; no overwrite flag is passed.
python3 -B tools/adoption/new_wsl_client_config.py --apply --host nativestack2604 \
    --skip claude-hooks --skip claude-agents --skip claude-mcp \
    --skip claude-settings --skip claude-launcher --skip rtk-claude-init \
    --skip claude-md --skip codex-files --skip codex-md --skip login-path --skip verify

# 6. Read back configuration, then require every pointer in a new login.
python3 -B tools/adoption/new_wsl_client_config.py --check-login-env --host nativestack2604
env -u PAPER_ENV_FILE -u PAPER_ENV_FILE_2 -u SEC_CONTACT_ENV \
    -u PIT_ALPACA_ENV_PATH -u PIT_SEC_ENV_PATH -u IBKR_PAPER_LOGIN_ENV \
    -u IBKR_PAPER_TWS_FILE -u IBKR_PAPER_VNC_FILE -u RTK_TELEMETRY_DISABLED \
    bash --login -c 'test "$RTK_TELEMETRY_DISABLED" = 1 && exec python3 -B "$1/scripts/credential_status.py" --require-pointers' p1-env "$p1_repo"
```

Step 7 removes only the four single-export lines confirmed by the co-op: `PAPER_ENV_FILE_2`, `IBKR_PAPER_LOGIN_ENV`, `IBKR_PAPER_TWS_FILE` and `IBKR_PAPER_VNC_FILE`. The guard requires exactly one simple, optionally double-quoted path assignment for each exact name; compound shell commands, single-quoted forms, comments or other layouts stop the operation for owner review. It prints no assigned values and never uses a line number. Run only after step 6 passes.

```sh
p1_path='[-/A-Za-z0-9_.$}{]+'
for p1_name in PAPER_ENV_FILE_2 IBKR_PAPER_LOGIN_ENV IBKR_PAPER_TWS_FILE IBKR_PAPER_VNC_FILE; do
    p1_pattern="^[[:space:]]*export[[:space:]]+${p1_name}=(\"${p1_path}\"|${p1_path})[[:space:]]*$"
    test "$(grep -Ec "$p1_pattern" "$HOME/.bashrc")" = 1
    test "$(grep -Ec "^[[:space:]]*export[[:space:]]+${p1_name}=" "$HOME/.bashrc")" = 1
done
for p1_name in PAPER_ENV_FILE_2 IBKR_PAPER_LOGIN_ENV IBKR_PAPER_TWS_FILE IBKR_PAPER_VNC_FILE; do
    p1_pattern="^[[:space:]]*export[[:space:]]+${p1_name}=(\"${p1_path}\"|${p1_path})[[:space:]]*$"
    sed -i -E "\\@${p1_pattern}@d" "$HOME/.bashrc"
done
```

## Read back

Step 8 repeats the fresh login check after cleanup and checks a new user-manager child. The latter verifies the manager reload rather than inheriting the owner's terminal environment. Keep the returned boolean reports as new host evidence. Do not print `systemctl show-environment`, an `env` dump or credential-file contents.

```sh
python3 -B tools/adoption/new_wsl_client_config.py --check-login-env --host nativestack2604
env -u PAPER_ENV_FILE -u PAPER_ENV_FILE_2 -u SEC_CONTACT_ENV \
    -u PIT_ALPACA_ENV_PATH -u PIT_SEC_ENV_PATH -u IBKR_PAPER_LOGIN_ENV \
    -u IBKR_PAPER_TWS_FILE -u IBKR_PAPER_VNC_FILE -u RTK_TELEMETRY_DISABLED \
    bash --login -c 'test "$RTK_TELEMETRY_DISABLED" = 1 && exec python3 -B "$1/scripts/credential_status.py" --require-pointers' p1-env "$p1_repo"
systemd-run --user --wait --pipe --collect /bin/sh -c \
    'test "$RTK_TELEMETRY_DISABLED" = 1 && exec /usr/bin/python3 -B "$1/scripts/credential_status.py" --require-pointers' p1-env "$p1_repo"
systemctl --user is-active dagu.service
curl -fsS http://127.0.0.1:21080/api/v1/health
```

Fresh Claude and Codex sessions also need their own value-free pointer check after the owner reloads them; an existing client process is not evidence of new-session adoption. A future paper unit on or after 2026-10-07 passes its selected runner's existing `--env-file` argument directly in `ExecStart=`. The 2026-10-06 units stay untouched. Generation-key and firewall-lane stores remain conditional on the approved service/route decisions; this procedure creates neither.

## Rollback

The source, profile and Codex writes are separate transactions. Before restoring, stop concurrent configuration writers and ensure no later operator change would be overwritten. If one exists, the owner restores only the reviewed change. Select the exact saved `p1_backup` from above; do not infer it from the newest directory.

For each failed or reverted step, restore its corresponding configuration file with the loop below: source installation/login-env -> `.config/environment.d/60-native-agent-stack.conf`; profile reader -> `.profile`; F9 Codex merge -> `.codex/config.toml`; legacy cleanup -> `.bashrc`. The native F9/managed-block backup names remain additional recovery evidence.

```sh
# Set p1_restore to only the affected relative paths, or all four for full rollback.
p1_restore='.config/environment.d/60-native-agent-stack.conf .profile .codex/config.toml .bashrc'
for p1_rel in $p1_restore; do
    test ! -L "$HOME/$p1_rel"
    if test -f "$p1_backup/$p1_rel.absent"; then
        rm -f -- "$HOME/$p1_rel"
    else
        test -f "$p1_backup/$p1_rel"
        cp -a -- "$p1_backup/$p1_rel" "$HOME/$p1_rel"
    fi
done
```

If the source or manager refresh is rolled back, restore the manager's prior pointer values by reloading a restored source. When the source was originally absent, clear only these nine new names, then reload: `systemctl --user unset-environment PAPER_ENV_FILE PAPER_ENV_FILE_2 SEC_CONTACT_ENV PIT_ALPACA_ENV_PATH PIT_SEC_ENV_PATH IBKR_PAPER_LOGIN_ENV IBKR_PAPER_TWS_FILE IBKR_PAPER_VNC_FILE RTK_TELEMETRY_DISABLED`. This absent-source rollback is appropriate only when the owner confirms those manager names were not independently managed before adoption; otherwise retain their owner's prior values. Finally run `systemctl --user daemon-reload`, `systemctl --user restart dagu.service` and the Dagu health/readiness commands above. New login/client sessions are required after profile/config restoration. Never restart the operating system or rotate/copy a credential for rollback.
