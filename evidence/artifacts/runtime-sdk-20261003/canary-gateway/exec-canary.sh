#!/usr/bin/env bash
export CODEX_HOME='<PRIVATE_RUN_DIR>/canary-gateway/home'
KV=$(python3 -c 'import tomllib,os;print(tomllib.load(open(os.path.expanduser("~/.codex/omniroute.config.toml"),"rb"))["model_providers"]["omniroute"]["env_key"])')
[ -z "${!KV:-}" ] && export "$KV=keyless-gateway-placeholder"
mkdir -p '<PRIVATE_RUN_DIR>/canary-gateway/empty'; cd '<PRIVATE_RUN_DIR>/canary-gateway/empty'
'<PRIVATE_RUN_DIR>/prefix/bin/codex' exec --skip-git-repo-check -s read-only -m cx/gpt-6.1-sol -c model_provider='"omniroute"' -c model_reasoning_effort='"max"' -c web_search='"disabled"' -o '<PRIVATE_RUN_DIR>/canary-gateway/exec-last.txt' --json "Reply with exactly this text and nothing else: CLI_01600_GATEWAY_CANARY_OK" < /dev/null > '<PRIVATE_RUN_DIR>/canary-gateway/exec-events.jsonl' 2> '<PRIVATE_RUN_DIR>/canary-gateway/exec-stderr.txt'
echo "exit=$?"
