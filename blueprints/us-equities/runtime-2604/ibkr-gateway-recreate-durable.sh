#!/usr/bin/env bash
# Recreates the NativeStack2604 IB Gateway (IBKR paper account, orders enabled) so that it signs in by itself and the
# sign-in lasts all week. Run it from an interactive shell (`bash -i <this file>`), by the user or an agent, so that
# ~/.bashrc supplies the three IBKR_PAPER_* path pointers. It never reads or prints a credential value: the docker CLI
# reads the login env file through --env-file, and the two password files are mounted read-only. Only typing the stored
# values, once, at the user's private prompt is the user's own step.
# Decision: docs/decisions/2026-10-06-ibkr-paper-passwordless-login.md (the user's decision of 2026-10-06, about 01:50Z,
# for a passwordless, frictionless gateway sign-in; paper only). Inventory rows ibkr-gateway, ibkr-gateway-tws-password
# and ibkr-gateway-vnc-password (adoption/credential-inventory.json); check them with python3 scripts/credential_status.py.
# Adopted from the command center's host script of 2026-10-06 that recreated the live container; this copy runs every
# refusal before the first change and keeps its records outside every Git worktree.
# Sources:
# - gnzsnz/ib-gateway-docker release ibgateway-latest@10.51.1b (commit 8a22deaa6cab), README "Configuration" table:
#   TWS_USERID, TWS_PASSWORD_FILE; AUTO_RESTART_TIME ("does not require daily 2FA validation"); TWOFA_TIMEOUT_ACTION
#   ("set to 'restart' if you set AUTO_RESTART_TIME"); RELOGIN_AFTER_TWOFA_TIMEOUT; EXISTING_SESSION_DETECTED_ACTION;
#   TWS_SETTINGS_PATH plus a volume to keep settings; VNC_SERVER_PASSWORD_FILE. README "Credentials": a defined _FILE
#   variable names the file a credential is read from.
# - IBC 3.24.2 (2be2ecd05d77) userguide.md:586-601: AutoRestart gives "a single authentication at the start of the
#   week"; IBKR expires the session on Sunday.
# - rootlesskit v3.1.0 (62d2101f) pkg/parent/parent.go:401-432: rootless Docker maps container uid 0 to the user and
#   container uid 1000 to the first /etc/subuid start plus 999, the owner scripts/credential_status.py then accepts.
# Records: the full `docker inspect` output holds TWS_USERID. Each run writes its records 0600 into a new 0700 directory
# under ${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/ibkr-gateway/ and refuses a record directory inside
# any Git worktree, so a record can never be committed.
set -euo pipefail
umask 077
NAME=native-trading-ibkr-paper-20261005
IMAGE='ghcr.io/gnzsnz/ib-gateway:10.51.1b@sha256:69db6310cd75d5d0aca3a70c05dc5ad77b2be29ad75360a3f1e393454f2efa59'
VOL=native-trading-ibkr-paper-20261005-settings-rw
IMAGE_USER=ibgateway                  # the image's user, uid 1000
SETTINGS=/home/${IMAGE_USER}/Jts      # inside the container: the settings volume and TWS_SETTINGS_PATH
RESTART_AT='11:00 PM'   # daily, America/New_York; outside every paper session (latest unit RuntimeMaxSec ends about 8:05 PM ET)

: "${IBKR_PAPER_LOGIN_ENV:?pointer not set: store the paper login first, then run this from an interactive shell}"
: "${IBKR_PAPER_TWS_FILE:?pointer not set: store the paper login first, then run this from an interactive shell}"
: "${IBKR_PAPER_VNC_FILE:?pointer not set: store the VNC password first, then run this from an interactive shell}"
# -s needs only the file's metadata, so it also works on the two files already handed to the container user.
[ -s "$IBKR_PAPER_LOGIN_ENV" ] && [ -s "$IBKR_PAPER_TWS_FILE" ] || { echo "the IBKR login pointer targets are missing or empty"; exit 3; }
[ -s "$IBKR_PAPER_VNC_FILE" ] || { echo "the VNC password pointer target is missing or empty"; exit 3; }

# The nearest ancestor holding a .git entry (a directory, or a linked worktree's file), as git_worktree_of() in
# scripts/credential_status.py finds it.
inside_git_worktree() {
  local dir=$1
  while :; do
    if [ -e "$dir/.git" ] || [ -L "$dir/.git" ]; then return 0; fi
    if [ "$dir" = / ]; then return 1; fi
    dir=$(dirname -- "$dir")
  done
}
state=${XDG_STATE_HOME:-}
case $state in /*) ;; *) state=$HOME/.local/state ;; esac   # an unset, empty or relative value means the default (XDG)
RECORDS=$state/native-agent-stack/ibkr-gateway
nearest=$RECORDS
while [ ! -e "$nearest" ]; do nearest=$(dirname -- "$nearest"); done
if inside_git_worktree "$(realpath -- "$nearest")"; then
  echo "refused: the record directory would be inside a Git worktree, where a record holding the user ID could be committed; nothing changed"
  exit 6
fi

# The chown below is right only under rootless Docker, where container uid 1000 is one of the user's subordinate uids. Under
# a rootful daemon it would be host uid 1000, possibly another account.
security_options=$(docker info --format '{{.SecurityOptions}}')
case $security_options in
  *name=rootless*) ;;
  *) echo "refused: the Docker daemon is not rootless, so the container user is not a subordinate uid of yours; nothing changed"; exit 7 ;;
esac

existing=no
if docker inspect "$NAME" >/dev/null 2>&1; then
  existing=yes
  # API clients connect from this host to the published port 127.0.0.1:4002 (the image has no ss inside).
  command -v ss >/dev/null || { echo "refused: ss is missing on this host, so client connections can't be checked; nothing changed"; exit 5; }
  live=$(ss -Htn state established '( dport = :4002 )' | wc -l)
  echo "established API client connections to 127.0.0.1:4002 before the stop: $live"
  [ "$live" -eq 0 ] || { echo "refused: an API client is connected; nothing changed"; exit 4; }
fi

# Rootless Docker maps the host user to container root, and the image runs as 1000:1000 (ibgateway). A 0600 file owned by
# the host user is therefore unreadable in the container ("common.sh: line 57: /run/secrets/vnc_password: Permission
# denied", seen 2026-10-06 01:54Z, a crash loop). Hand the two password files to the container user without widening
# their 0600 mode: chown inside the user namespace, from the same pinned image. The docker CLI reads the --env-file on the
# host, so that file stays the host user's.
for f in "$IBKR_PAPER_VNC_FILE" "$IBKR_PAPER_TWS_FILE"; do
  docker run --rm --user 0 --entrypoint chown -v "$f":/s "$IMAGE" 1000:1000 /s
done

stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$RECORDS"
OUT=$RECORDS/recreate-$stamp
mkdir -m 700 "$OUT"
if [ "$existing" = yes ]; then
  docker inspect "$NAME" > "$OUT/before-inspect.json"
  chmod 600 "$OUT/before-inspect.json"
  docker stop -t 30 "$NAME" >/dev/null
  docker rename "$NAME" "$NAME-pre-durable-$stamp"
  echo "kept for rollback: $NAME-pre-durable-$stamp (stopped)"
  # Printed before the new container starts, so a failed start (set -e ends the run) still shows the way back. Each step
  # tolerates a new container that was never created, or created and never started.
  rollback="docker stop $NAME 2>/dev/null; docker rename $NAME $NAME-durable-failed-$stamp 2>/dev/null; docker rename $NAME-pre-durable-$stamp $NAME && docker start $NAME"
  echo "rollback, if the new container does not come up: $rollback"
fi
docker run -d --name "$NAME" --restart unless-stopped \
  -p 127.0.0.1:4002:4004 -p 127.0.0.1:5900:5900 \
  -v "$VOL:$SETTINGS" \
  -v "$IBKR_PAPER_VNC_FILE":/run/secrets/vnc_password:ro \
  -v "$IBKR_PAPER_TWS_FILE":/run/secrets/tws_password:ro \
  --env-file "$IBKR_PAPER_LOGIN_ENV" -e TWS_PASSWORD_FILE=/run/secrets/tws_password \
  -e TRADING_MODE=paper -e READ_ONLY_API=no -e TIME_ZONE=America/New_York \
  -e TWS_SETTINGS_PATH="$SETTINGS" -e VNC_SERVER_PASSWORD_FILE=/run/secrets/vnc_password \
  -e AUTO_RESTART_TIME="$RESTART_AT" -e TWOFA_TIMEOUT_ACTION=restart -e RELOGIN_AFTER_TWOFA_TIMEOUT=yes \
  -e EXISTING_SESSION_DETECTED_ACTION=primary \
  "$IMAGE" > "$OUT/container-id.txt"
sleep 8
docker inspect "$NAME" > "$OUT/after-inspect.json"
chmod 600 "$OUT/after-inspect.json"
echo "rollback record: $OUT"
docker inspect "$NAME" --format 'state={{.State.Status}} started={{.State.StartedAt}} restart={{.HostConfig.RestartPolicy.Name}}'
# Only these non-secret settings are printed; TWS_USERID stays in the 0600 records.
docker inspect "$NAME" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E '^(TRADING_MODE|READ_ONLY_API|TIME_ZONE|AUTO_RESTART_TIME|TWOFA_TIMEOUT_ACTION|RELOGIN_AFTER_TWOFA_TIMEOUT|EXISTING_SESSION_DETECTED_ACTION)=' \
  || echo "none of the expected settings were found in the new container's environment"
if [ "$existing" = yes ]; then
  echo "rollback: $rollback"
fi
