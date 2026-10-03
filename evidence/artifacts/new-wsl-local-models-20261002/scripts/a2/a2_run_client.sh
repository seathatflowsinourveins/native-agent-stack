#!/usr/bin/env bash
# A2's client part (amendment 3b): one fixed repository task, once, with one real client against the measurement
# Ollama server. Codex runs with its built-in local-provider option; Claude Code runs through the server's documented
# launch entry. Each client gets an emptied environment and its own scratch home, so nothing of a user's own
# configuration reaches it. One attempt, wall limit 900 seconds, then the task's fixed file check. A label that
# exists is refused. usage: a2_run_client.sh <codex|claude> <ollama model> <task> <label>
set -u
CLIENT="${1:?client}"; MODEL="${2:?model}"; TASK="${3:?task}"; LABEL="${4:?label}"
A="$HOME/measure/a2"; H="$A/harness"; RUN="$A/client/$LABEL/$CLIENT-$TASK"; W="$RUN/repo"; SCR="$RUN/home"
[ ! -e "$RUN" ] || { echo "run $LABEL/$CLIENT-$TASK already exists"; exit 2; }
mkdir -p "$RUN" "$SCR/.codex" "$A/bin"
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:/usr/lib/wsl/lib:$PATH"
[ -e "$A/bin/codex" ] || ln -s "$(readlink -f "$(command -v codex)")" "$A/bin/codex"
[ -e "$A/bin/claude" ] || ln -s "$(readlink -f "$(command -v claude)")" "$A/bin/claude"
OLLAMA_REAL=$(mise which ollama 2>/dev/null || command -v ollama)
python3 -B "$H/a2_tasks.py" make "$TASK" "$W" || exit 1
PROMPT=$(python3 -B "$H/a2_tasks.py" prompt "$TASK")
printf 'approval_policy = "never"\nmodel_reasoning_effort = "medium"\nweb_search = "disabled"\n\n[analytics]\nenabled = false\n' > "$SCR/.codex/config.toml"
BASE=http://127.0.0.1:21434
echo "label=$LABEL client=$CLIENT model=$MODEL task=$TASK started=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN/run-meta.txt"
start=$SECONDS
# Deviation 2 of the preregistration: Codex's local-provider setup looks the model up by the exact name the server
# lists, which carries its tag; without the tag it tries to pull the model from the registry and stops.
CODEX_MODEL="$MODEL"; case "$MODEL" in *:*) ;; *) CODEX_MODEL="$MODEL:latest" ;; esac
case "$CLIENT" in
  codex)
    ( cd "$W" && env -i PATH="$A/bin:/usr/bin:/bin" HOME="$SCR" CODEX_HOME="$SCR/.codex" LANG=C.UTF-8 TZ=UTC \
        CODEX_OSS_BASE_URL="$BASE/v1" timeout --signal=TERM --kill-after=20 900 \
        "$A/bin/codex" exec --oss --local-provider ollama -m "$CODEX_MODEL" --sandbox workspace-write --skip-git-repo-check --json \
        -C "$W" "$PROMPT" < /dev/null > "$RUN/events.jsonl" 2> "$RUN/stderr.txt" ); rc=$? ;;
  claude)
    ( cd "$W" && env -i PATH="$A/bin:$(dirname "$OLLAMA_REAL"):/usr/bin:/bin" HOME="$SCR" LANG=C.UTF-8 TZ=UTC \
        OLLAMA_HOST=127.0.0.1:21434 timeout --signal=TERM --kill-after=20 900 \
        "$OLLAMA_REAL" launch claude --model "$MODEL" --yes -- -p "$PROMPT" --permission-mode bypassPermissions --output-format json \
        < /dev/null > "$RUN/events.jsonl" 2> "$RUN/stderr.txt" ); rc=$? ;;
  *) echo "unknown client $CLIENT"; exit 2 ;;
esac
result=$(python3 -B "$H/a2_tasks.py" check "$TASK" "$W")
{
  echo "client_exit=$rc seconds=$((SECONDS - start)) finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "check=$result"
  echo "changed_files=$(git -C "$W" status --porcelain | wc -l)"
} >> "$RUN/run-meta.txt"
cat "$RUN/run-meta.txt"
tail -n 2 "$RUN/stderr.txt" 2>/dev/null | sed "s#$HOME#<HOME>#g" | cut -c1-240
