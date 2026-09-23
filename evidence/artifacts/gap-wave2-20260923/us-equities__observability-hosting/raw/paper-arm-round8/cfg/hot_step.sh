sleep 12
export RESTIC_PASSWORD=gap-wave2-local-throwaway HOME="<temp-home>"
"$HOME/.local/share/codex-ecosystem/bin/restic" -r "$HOME/.cache/gap-wave2-20260923/observability-hosting/paper-arm-8/restic-hot" init && "$HOME/.local/share/codex-ecosystem/bin/restic" -r "$HOME/.cache/gap-wave2-20260923/observability-hosting/paper-arm-8/restic-hot" backup "$HOME/.cache/gap-wave2-20260923/observability-hosting/paper-arm-8/work" --tag hot && echo HOT_BACKUP_OK
