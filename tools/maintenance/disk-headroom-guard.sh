#!/usr/bin/env bash
# Transfer source: NativeStack ops/disk-headroom-guard.sh, read 2026-10-06,
# SHA256 b2e0515c01ec385118f0d3c8a40b4102932ed05784085d13bc488074bceba58c.
# Preserve two-minute sampling, local alerts <60 GiB and uv cache prune <30 GiB.
# No deletion beyond upstream regenerable-cache pruning; no process arguments.
set -uo pipefail
umask 077
state="${NATIVE_DISK_GUARD_STATE_DIR:-$HOME/.local/state/native-agent-stack/ops}"
csv="$state/disk-headroom.csv"
alert="$state/ALERT-disk-headroom.log"
status=0
safe_log() {
  [[ ! -L "$state" && ( ! -e "$state" || -d "$state" ) \
      && ! -L "$1" && ( ! -e "$1" || -f "$1" ) ]]
}

# Retain the source's GNU df whole-GiB display and threshold semantics.
if ! free="$(df --output=avail -B1G / | tail -1 | tr -d '[:space:]')" \
    || [[ ! "$free" =~ ^[0-9]+$ ]]; then
  printf 'disk-headroom-guard: root free-space sample is unavailable\n' >&2
  exit 1
fi
if ! now="$(date -u +%FT%TZ)"; then
  printf 'disk-headroom-guard: UTC timestamp is unavailable\n' >&2
  exit 1
fi
if ! safe_log "$csv"; then
  printf 'disk-headroom-guard: CSV must be a regular nonsymlink file\n' >&2
  status=1
else
  mkdir -p -- "$state" || status=1
  [[ -s "$csv" ]] || printf 'utc,free_gib\n' > "$csv" || status=1
  printf '%s,%s\n' "$now" "$free" >> "$csv" || status=1
fi

if (( 10#$free < 60 )); then
  # The source used args, which can contain credential values. comm is metadata.
  if process_rows="$(ps -eo pid,etimes,comm --sort=-etimes 2>/dev/null)"; then
    top="$(printf '%s\n' "$process_rows" | awk \
      '$3 ~ /docker|harbor|uv|pip|npm|git|tar|qmd|ollama|huggingface/ { if (++found <= 5) printf "%s;", substr($0,1,120) }')"
    [[ -n "$top" ]] || top='none'
  else
    top='unavailable'
  fi
  if safe_log "$alert"; then
    printf '%s free=%sGiB below 60 GiB; candidates: %s\n' "$now" "$free" "$top" >> "$alert" || status=1
  else
    printf 'disk-headroom-guard: alert log must be a regular nonsymlink file\n' >&2
    status=1
  fi
fi
if (( 10#$free < 30 )); then
  # uv@70fe1196: cache_prune.rs:31-43; locked_file.rs:17-28,41-47.
  # The unit bounds the lock wait; never bypass an active cache with --force.
  if command -v uv >/dev/null && prune_output="$(uv cache prune 2>&1)"; then
    # A full root may prevent logging; do not stop cache mitigation before it.
    if safe_log "$alert"; then
      printf '%s free=%sGiB: uv cache prune ran\n' "$now" "$free" >> "$alert" || status=1
    else
      status=1
    fi
  else
    if [[ "${prune_output:-}" == *'Cache is currently in-use'* \
        && "$prune_output" == *'Timeout ('* && "$prune_output" == *'when waiting for lock'* ]]; then
      message='uv cache in use; safe prune deferred after lock timeout'
    else
      message='required uv cache prune failed or is unavailable'
    fi
    printf 'disk-headroom-guard: %s\n' "$message" >&2
    if safe_log "$alert"; then
      printf '%s free=%sGiB: %s\n' "$now" "$free" "$message" >> "$alert" || status=1
    fi
    status=1
  fi
fi
exit "$status"
