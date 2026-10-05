#!/usr/bin/env bash
# Canonical ubuntu/wsl-setup@73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8:
# test/basic-assertions.sh:2-7,22-30; test/systemd-assertions.sh:6-33.
# Integration exception: adoption/platforms/linux-wsl2-new-distro.md, F1.
# Run only on the target, as its configured default user. This installs nothing.
set -euo pipefail

wsl_expected_user="${WSL_USER:-$(python3 - <<'PY'
import configparser
config = configparser.ConfigParser()
config.read('/etc/wsl.conf')
print(config.get('user', 'default', fallback=''))
PY
)}"
[[ "$wsl_expected_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || {
  printf 'base-distribution: set WSL_USER or configure [user] default in /etc/wsl.conf.\n' >&2
  exit 1
}
wsl_setup_probe="$(mktemp -d)"
trap 'rm -rf -- "$wsl_setup_probe"' EXIT
wsl_setup_pin=73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8
for assertion in basic systemd; do
  curl --proto '=https' --tlsv1.2 -fsSL \
    "https://raw.githubusercontent.com/ubuntu/wsl-setup/$wsl_setup_pin/test/$assertion-assertions.sh" \
    -o "$wsl_setup_probe/$assertion.sh"
done
# Hashes bind the unchanged upstream scripts; SOURCES.md records the read-back.
printf '%s  %s\n' \
  c6e966a2e6041f2e91f4cccc146ee86042af1c052768944927394e23de947fd0 "$wsl_setup_probe/basic.sh" \
  83f2d89c00e70e994218ed3bed4ae19aee3539934dbe109aff76f9c57cfd2e83 "$wsl_setup_probe/systemd.sh" | sha256sum --check --status
wsl_basic_rc=0
bash "$wsl_setup_probe/basic.sh" "$wsl_expected_user" || wsl_basic_rc=$?
printf 'base-distribution | upstream-basic-exit=%s\n' "$wsl_basic_rc" >&2
wsl_systemd_rc=0
bash "$wsl_setup_probe/systemd.sh" || wsl_systemd_rc=$?
printf 'base-distribution | upstream-systemd-exit=%s\n' "$wsl_systemd_rc" >&2
(( wsl_basic_rc == 0 )) || exit "$wsl_basic_rc"

wsl_system_state="$(LANG=C systemctl is-system-running --wait)" || true
wsl_failed_units="$(systemctl --failed --no-legend --plain)"
if (( wsl_systemd_rc == 0 )); then
  [[ "$wsl_system_state" == running && -z "$wsl_failed_units" ]]
  printf 'base-distribution | F1=running | upstream-systemd=passed\n' >&2
else
  # Never relabel the upstream exit 1 as an upstream pass. F1 accepts one case.
  [[ "$wsl_systemd_rc" == 1 && "$wsl_system_state" == degraded ]]
  [[ "$(awk '{print $1}' <<< "$wsl_failed_units")" == systemd-binfmt.service ]]
  wsl_journal_rc=0
  wsl_binfmt_log="$(journalctl -b 0 -t systemd-binfmt --no-pager -n 4 2>&1)" || wsl_journal_rc=$?
  printf 'base-distribution | F1-journal-exit=%s\n' "$wsl_journal_rc" >&2
  if [[ "$wsl_binfmt_log" == *'You are currently not seeing messages'* ||
        "$wsl_binfmt_log" == *'-- No entries --'* ]]; then
    printf 'base-distribution | F1-journal=unreadable | retry=sudo-n\n' >&2
    wsl_binfmt_log="$(sudo -n journalctl -b 0 -t systemd-binfmt --no-pager -n 4)"
  fi
  [[ "$wsl_binfmt_log" == *'Failed to flush binfmt_misc rules, ignoring: Read-only file system'* ]]
  printf 'base-distribution | F1=binfmt-read-only-exception | upstream-systemd=failed:%s\n' "$wsl_systemd_rc" >&2
  # The upstream script stops at assertion 1. Evaluate its remaining assertions
  # unchanged in meaning, and report them separately as integration checks.
  wsl_multipath_state="$(LANG=C systemctl is-active multipathd.service)" || true
  [[ "$wsl_multipath_state" == inactive ]]
  printf 'base-distribution | remaining-multipathd=inactive\n' >&2
  if systemctl is-enabled systemd-timesyncd.service; then
    wsl_timesync_state="$(LANG=C systemctl is-active systemd-timesyncd.service)" || true
    [[ "$wsl_timesync_state" == inactive ]]
    printf 'base-distribution | remaining-timesyncd=inactive\n' >&2
  else
    printf 'base-distribution | remaining-timesyncd=not-enabled\n' >&2
  fi
  test -r /etc/cloud/cloud-init.disabled
  printf 'base-distribution | remaining-cloud-init-disabled=readable\n' >&2
fi
systemctl list-unit-files --type=service --no-pager >/dev/null

# Preserve cmd.exe's own exit code; filtering its returned text happens later.
test -e /proc/sys/fs/binfmt_misc/WSLInterop
wsl_interop_rc=0
wsl_interop_output="$(cd /mnt/c/Windows/System32 && ./cmd.exe /d /c ver)" || wsl_interop_rc=$?
printf 'base-distribution | cmd-exit=%s\n' "$wsl_interop_rc" >&2
printf '%s\n' "$wsl_interop_output" | tr -d '\r' | sed -n '/^Microsoft Windows/p' >&2
(( wsl_interop_rc == 0 ))
