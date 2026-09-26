"""PreToolUse secret guard: blocked and allowed Bash command strings.

Local integration class. The guard is a text heuristic; the expected
pass-through cases below record known bypasses so no reader mistakes the
hook for a security boundary.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

from scripts.hooks import secret_path_guard as guard

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/hooks/secret_path_guard.py"
HOST_HOOK = Path.home() / ".claude" / "hooks" / "secret_path_guard.py"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true"

BLOCKED = {
    "cat ~/.config/native-agent-stack/alpaca-paper.env": "credential_store_path",
    "ls -l \"$HOME/.config/native-agent-stack\"": "credential_store_path",
    "python3 -c \"open('/home/example/.config/native-agent-stack/alpaca-paper.env').read()\"": "credential_store_path",
    "head -c 40 ~/.claude/.credentials.json": "native_store_path",
    "jq . \"${CODEX_HOME}/auth.json\"": "native_store_path",
    "grep oauth ~/.config/gh/hosts.yml": "native_store_path",
    "cat /proc/self/environ": "process_environment",
    "tr '\\0' '\\n' < /proc/1234/environ": "process_environment",
    "gh auth token": "native_token_print",
    "gh auth status --show-token": "native_token_print",
    "gh auth status -t": "native_token_print",
    # After `gh auth setup-git` a credential helper prints the same token.
    "printf 'protocol=https\\nhost=github.com\\n\\n' | git credential fill": "native_token_print",
    "git -c credential.helper= credential fill <<< 'url=https://github.com'": "native_token_print",
    "echo host=github.com | gh auth git-credential get": "native_token_print",
    "gh auth git-credential get < request.txt": "native_token_print",
    "echo host=github.com | git credential-store get": "native_token_print",
    "git credential-cache --timeout 60 get < request.txt": "native_token_print",
    "git-credential-libsecret get < request.txt": "native_token_print",
    "bash -c 'git credential fill < request.txt'": "native_token_print",
    "echo \"$OPENROUTER_API_KEY\"": "secret_variable_reference",
    "echo $MISTRAL_API_KEY": "secret_variable_reference",
    "python3 -c 'import os;print(os.environ[\"MASSIVE_API_KEY\"])'": "secret_variable_reference",
    "printf '%s' \"$TWS_USERNAME\"": "secret_variable_reference",
    "security find-generic-password -s x -w": "keychain_read",
    "echo $APCA_API_SECRET_KEY": "secret_variable_reference",
    "printf '%s' \"${DATABENTO_API_KEY}\"": "secret_variable_reference",
    "python3 -c 'import os; print(os.environ[\"APCA_API_KEY_ID\"])'": "secret_variable_reference",
    "env": "environment_dump",
    "env | sort": "environment_dump",
    "env -u HOME": "environment_dump",
    "FOO=1 printenv PATH": "environment_dump",
    "set": "environment_dump",
    "export -p": "environment_dump",
    "declare -x": "environment_dump",
    "declare -p": "environment_dump",
    "ps eww 1234": "environment_dump",
    "ps auxe": "environment_dump",
    "echo `printenv`": "environment_dump",
    "echo $(env)": "environment_dump",
    "bash -c 'printenv'": "environment_dump",
    "strace -f -e trace=read python3 runner.py": "process_trace",
    "cat \"$PAPER_ENV_FILE\"": "credential_file_read",
    "base64 < \"$SEC_CONTACT_ENV\"": "credential_file_read",
    "cp \"${ENV_FILE}\" /tmp/x": "credential_file_read",
    "cat .env": "dotenv_read",
    "cat .env.probe": "dotenv_read",
    "cp .env /tmp/backup": "dotenv_read",
    "cat .env > /tmp/copy.txt": "dotenv_read",
    "diff .env.example .env": "dotenv_read",
    "grep KEY ../other/.env.local": "dotenv_read",
    # Readers and searches on a secret variable name, a credential file or the store directory.
    "grep -n APCA_API_KEY_ID blueprints/us-equities/adaptive-paper/runner.py": "secret_name_search",
    "grep -r APCA_API_SECRET_KEY ~": "secret_name_search",
    "rg -n 'DATABENTO_API_KEY|TYPESAFE_API_KEY' /srv": "secret_name_search",
    "ag GF_SECURITY_ADMIN_PASSWORD /etc": "secret_name_search",
    "ack --hidden OPENAI_API_KEY": "secret_name_search",
    "git grep -n GH_TOKEN": "secret_name_search",
    "git -C ../other --no-pager grep HF_TOKEN": "secret_name_search",
    "find ~ -type f -exec grep -H ALPACA_SECRET_KEY {} +": "secret_name_search",
    "find ~ -name '*.env' -exec cat {} \\;": "dotenv_read",
    "find . -name .env -execdir head -n 3 {} +": "dotenv_read",
    "awk -F= '$1==\"APCA_API_SECRET_KEY\"{print $2}' paper.cfg": "secret_name_search",
    "sed -n '/TWS_PASSWORD/p' gateway.ini": "secret_name_search",
    "sed -n 1,5p alpaca-paper.env": "dotenv_read",
    "rg --hidden -g '*.env' KEY ~": "dotenv_read",
    "git log -p | grep ANTHROPIC_API_KEY": "secret_name_search",
    "ls ${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack": "credential_store_path",
    "rg KEY \"$XDG_CONFIG_HOME/native-agent-stack/\"": "credential_store_path",
    "while read -r line; do :; done < \"$PAPER_ENV_FILE\"": "credential_file_read",
    # Shell tracing or verbose mode while sourcing a credential file prints its assignments.
    "set -x; . \"$PAPER_ENV_FILE\"": "trace_while_sourcing",
    "set -euxo pipefail; set -a; . \"$SEC_CONTACT_ENV\"; set +a": "trace_while_sourcing",
    "set -o xtrace; source \"${PAPER_ENV_FILE}\"": "trace_while_sourcing",
    "set -v; . ./alpaca-paper.env": "trace_while_sourcing",
    "bash -x -c '. \"$PAPER_ENV_FILE\"; python3 run.py'": "trace_while_sourcing",
    "sh -xc 'set -a; . \"$SEC_CONTACT_ENV\"'": "trace_while_sourcing",
    "bash -o xtrace -c 'source \"$PAPER_ENV_FILE\"'": "trace_while_sourcing",
    "SHELLOPTS=xtrace bash -c '. \"$PAPER_ENV_FILE\"'": "trace_while_sourcing",
    # Environment dumps after sourcing, including name-filtered forms.
    "set -a; . \"$PAPER_ENV_FILE\"; set +a; env": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\" && printenv APCA_API_BASE_URL": "environment_dump_after_source",
    "source \"$PAPER_ENV_FILE\"; export -p": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\"; declare -x": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\"; declare -p APCA_API_KEY_ID": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\"; env | grep APCA": "environment_dump_after_source",
    "bash -c '. \"$PAPER_ENV_FILE\"; env'": "environment_dump_after_source",
    "( . \"$PAPER_ENV_FILE\"; python3 -c 'import os; print(dict(os.environ))' )": "environment_dump_after_source",
    "eval '. \"$PAPER_ENV_FILE\"; typeset -p'": "environment_dump_after_source",
    "bash -lc 'printenv'": "environment_dump",
    "env -u HOME env": "environment_dump",
    # /proc/<pid>/environ in any spelling.
    "grep -a -z APCA /proc/*/environ": "process_environment",
    "xargs -0 -n1 < /proc/self/task/42/environ": "process_environment",
    "cat '/proc/'\"$pid\"'/environ'": "process_environment",
    "cd /proc/1234 && tr '\\0' '\\n' < environ": "process_environment",
    "find /proc -maxdepth 2 -name environ": "process_environment",
    # Hugging Face: both token files in every spelling of their directory, `hf auth token`
    # (also inside a substitution or a pipe), HF_TOKEN_PATH as a pointer, a read or copy of
    # the whole Hugging Face home, and the legacy token variable.
    "cat ~/.cache/huggingface/token": "native_store_path",
    "head -c 8 ~/.cache/huggingface/stored_tokens": "native_store_path",
    "ls -l ~/.cache/huggingface/token": "native_store_path",
    "cat \"$HF_HOME/token\"": "native_store_path",
    "cat \"$HF_HOME\"/token": "native_store_path",
    "cat \"${HF_HOME}\"/stored_tokens": "native_store_path",
    "jq -R . ${HF_HOME:-$HOME/.cache/huggingface}/token": "native_store_path",
    "cat \"${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}/token\"": "native_store_path",
    "cat \"${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token\"": "native_store_path",
    "cp ~/.cache/huggingface/token ~/.cache/huggingface/token.bak": "native_store_path",
    "python3 -c \"print(open('/home/example/.cache/huggingface/token').read())\"": "native_store_path",
    "hf auth token": "native_token_print",
    "~/.local/bin/hf auth token": "native_token_print",
    "hf auth token | xargs curl -H 'Authorization: Bearer {}' https://huggingface.co/api/whoami-v2":
        "native_token_print",
    "curl -H \"Authorization: Bearer $(hf auth token)\" https://huggingface.co/api/whoami-v2": "native_token_print",
    "uvx hf auth token": "native_token_print",
    "huggingface-cli auth token": "native_token_print",
    "huggingface-cli token": "native_token_print",
    "cat \"$HF_TOKEN_PATH\"": "credential_file_read",
    "base64 < \"${HF_TOKEN_PATH}\"": "credential_file_read",
    "grep -r hf_ ~/.cache/huggingface": "native_store_path",
    "rg -uu . \"$HF_HOME\"": "native_store_path",
    "grep -r x \"$XDG_CACHE_HOME/huggingface/\"": "native_store_path",
    "cp -r ~/.cache/huggingface /tmp/backup": "native_store_path",
    "rsync -a ~/.cache/huggingface/ /mnt/backup/hf/": "native_store_path",
    "cat ~/.cache/huggingface/*": "native_store_path",
    "find ~/.cache/huggingface -type f -exec cat {} +": "native_store_path",
    "echo \"$HUGGING_FACE_HUB_TOKEN\"": "secret_variable_reference",
    "hf auth login --token $HF_TOKEN": "secret_variable_reference",
}

# The documented kernel keyring form (docs/secret-storage.md, recipes/tavily.md), and the same with a
# variable that is not one of the guard's secret names, so only the keyring rules can catch it.
EXEC = "python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY --"
DEMO_EXEC = "python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TOKEN --"

KEYRING_BLOCKED = {
    # keyctl(1) subcommands that print a payload, in every position the other rules cover.
    "keyctl print %user:native-agent-stack:tavily_api_key": "keyring_payload_read",
    "keyctl pipe %user:native-agent-stack:tavily_api_key | base64": "keyring_payload_read",
    "keyctl read 123456789": "keyring_payload_read",
    "keyctl dh_compute 11 22 33": "keyring_payload_read",
    "sudo keyctl print 123456789": "keyring_payload_read",
    "bash -c 'keyctl pipe %user:native-agent-stack:tavily_api_key'": "keyring_payload_read",
    "echo $(keyctl pipe %user:native-agent-stack:tavily_api_key)": "keyring_payload_read",
    "echo `keyctl print 123456789`": "keyring_payload_read",
    # A payload read in inline interpreter code: a raw keyctl system call with KEYCTL_READ (11), the
    # constant's name, libkeyutils' or python-keyutils' reader, or this repository's keyring module.
    "python3 -c 'import ctypes; l = ctypes.CDLL(None); print(l.syscall(250, 11, 123, None, 0))'": "keyring_payload_read",
    "python3 -c 'import ctypes as c; c.CDLL(None).syscall(c.c_long(250), c.c_long(11), 1, None, 0)'":
        "keyring_payload_read",
    "python3 - <<'EOF'\nKEYCTL_READ = 11\nEOF": "keyring_payload_read",
    "perl -e 'syscall(250, 11, $id, $buf, 64)'": "keyring_payload_read",
    "python3 -c 'import keyutils; print(keyutils.read_key(123))'": "keyring_payload_read",
    "uv run python -c 'import ctypes; ctypes.CDLL(\"libkeyutils.so.1\").keyctl_read_alloc(1, None)'":
        "keyring_payload_read",
    "python3 -c 'from kernel_keyring import Keyring; print(Keyring().read(1))'": "keyring_payload_read",
    "python3 -c 'import scripts.kernel_keyring as k'": "keyring_payload_read",
    "python3 -c 'import subprocess; subprocess.run([\"keyctl\", \"print\", \"123\"])'": "keyring_payload_read",
    # The command that exec starts names the injected variable: any mention beyond exec's own.
    f"{EXEC} printenv TAVILY_API_KEY": "keyring_variable_reference",
    f"{EXEC} tvly search \"TAVILY_API_KEY rotation\" --json": "keyring_variable_reference",
    f"{EXEC} sh -c 'echo $TAVILY_API_KEY'": "secret_variable_reference",
    f"{DEMO_EXEC} sh -c 'echo \"$KK_DEMO_TOKEN\"'": "keyring_variable_reference",
    f"{DEMO_EXEC} sh -c 'echo ${{KK_DEMO_TOKEN}}'": "keyring_variable_reference",
    f"{DEMO_EXEC} python3 -c 'import os; print(os.environ[\"KK_DEMO_TOKEN\"])'": "keyring_variable_reference",
    f"{DEMO_EXEC} python3 -c 'import os; print(os.getenv(\"KK_DEMO_TOKEN\"))'": "keyring_variable_reference",
    f"{DEMO_EXEC} cmd.exe /c echo %KK_DEMO_TOKEN%": "keyring_variable_reference",
    f"echo 'import os; print(os.environ[\"KK_DEMO_TOKEN\"])' | {DEMO_EXEC} python3 -": "keyring_variable_reference",
    # The command that exec starts dumps the environment it inherits.
    f"{EXEC} env": "environment_dump_in_keyring_exec",
    f"{EXEC} env -0": "environment_dump_in_keyring_exec",
    f"{EXEC} nohup env": "environment_dump_in_keyring_exec",
    f"{EXEC} printenv": "environment_dump_in_keyring_exec",
    f"{EXEC} ps eww": "environment_dump_in_keyring_exec",
    f"{EXEC} bash -c 'set'": "environment_dump_in_keyring_exec",
    f"{EXEC} bash -c 'export -p'": "environment_dump_in_keyring_exec",
    f"{EXEC} bash -c 'declare -p'": "environment_dump_in_keyring_exec",
    f"{EXEC} bash -c 'tvly search x && env'": "environment_dump_in_keyring_exec",
    f"{EXEC} bash -c 'for v in ${{!TAV*}}; do echo \"${{!v}}\"; done'": "environment_dump_in_keyring_exec",
    f"{EXEC} python3 -c 'import os; print(dict(os.environ))'": "environment_dump_in_keyring_exec",
    f"{EXEC} python3 -c 'import subprocess; subprocess.run([\"env\"])'": "environment_dump_in_keyring_exec",
    f"{DEMO_EXEC} python3 - <<'EOF'\nimport os\nprint(os.environ)\nEOF": "environment_dump_in_keyring_exec",
    f"{DEMO_EXEC} node -e 'console.log(process.env)'": "environment_dump_in_keyring_exec",
    f"{EXEC} perl -e 'print map {{\"$_=$ENV{{$_}}\\n\"}} keys %ENV'": "environment_dump_in_keyring_exec",
    f"{EXEC} ruby -e 'p ENV.to_h'": "environment_dump_in_keyring_exec",
    f"{EXEC} php -r 'print_r($_ENV);'": "environment_dump_in_keyring_exec",
    f"{EXEC} awk 'BEGIN {{ for (k in ENVIRON) print k, ENVIRON[k] }}'": "environment_dump_in_keyring_exec",
    f"{EXEC} jq -n env": "environment_dump_in_keyring_exec",
    f"{EXEC} jq -n '$ENV'": "environment_dump_in_keyring_exec",
    f"{EXEC} python3 -c 'import os; print(os.environb)'": "environment_dump_in_keyring_exec",
    f"{EXEC} python3 -c 'import os; os.system(\"set\")'": "environment_dump_in_keyring_exec",
    f"{EXEC} ruby -e 'p ENV'": "environment_dump_in_keyring_exec",
    f"{EXEC} deno eval 'console.log(Deno.env.toObject())'": "environment_dump_in_keyring_exec",
    f"{EXEC} pwsh -c 'Get-ChildItem Env:'": "environment_dump_in_keyring_exec",
    # env or printenv as another program's argument: launchers the guard does not model.
    f"{EXEC} find /tmp -maxdepth 0 -exec env ';'": "environment_dump_in_keyring_exec",
    f"{EXEC} stdbuf -o0 printenv": "environment_dump_in_keyring_exec",
    f"{EXEC} watch -n 5 /usr/bin/env": "environment_dump_in_keyring_exec",
    # The price of that rule: a one-word query `env` is blocked too; a longer query passes (ALLOWED).
    f"{EXEC} tvly search env --json": "environment_dump_in_keyring_exec",
    # Any path to the script, any launcher, and an exec inside a shell.
    "python3 -I ~/.local/share/codex-ecosystem/bin/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- env":
        "environment_dump_in_keyring_exec",
    "uv run python scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- env":
        "environment_dump_in_keyring_exec",
    "timeout 60 python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- env":
        "environment_dump_in_keyring_exec",
    "bash -c 'python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- printenv'":
        "environment_dump_in_keyring_exec",
    # Every other rule applies to the started command (test_every_rule_applies_to_a_keyring_exec
    # repeats this for all of BLOCKED).
    f"{EXEC} cat .env": "dotenv_read",
    f"{EXEC} strace -f tvly search x": "process_trace",
    f"{EXEC} cat /proc/self/environ": "process_environment",
    # tvly auth without JSON output prints the key's first eight and last four characters.
    "tvly auth": "native_token_print",
    "~/.local/bin/tvly auth > /tmp/auth.txt": "native_token_print",
    f"{EXEC} tvly auth": "native_token_print",
    "tvly-keyring auth": "native_token_print",
    "sh adoption/tools/tvly-keyring auth": "native_token_print",
    # tavily-cli's own credential file, and the variable name as a secret name.
    "cat ~/.tavily/config.json": "native_store_path",
    f"{EXEC} jq . ~/.tavily/config.json": "native_store_path",
    "rg -n TAVILY_API_KEY": "secret_name_search",
    "echo \"$TAVILY_API_KEY\"": "secret_variable_reference",
    "python3 -c 'import os; print(os.environ[\"TAVILY_API_KEY\"])'": "secret_variable_reference",
}

ALLOWED = [
    "python3 runner.py paper --env-file \"$PAPER_ENV_FILE\" --output out.json",
    "python3 scripts/credential_status.py --json",
    "env -u HF_TOKEN python3 run.py",
    "env -i PATH=/usr/bin python3 -V",
    "unset TYPESAFE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY",
    "set -euo pipefail; set -a; . \"$SEC_CONTACT_ENV\"; set +a",
    "export EDGAR_IDENTITY=\"${EDGAR_IDENTITY:-$SEC_USER_AGENT}\"",
    "ps -ef | grep runner",
    "ps -o pid,command -p 123",
    "declare -a items=(a b)",
    "git status && git diff --stat",
    "cat .env.example",
    "cat docs/examples/alpaca-paper.env.example",
    "wc -c \"$PAPER_ENV_FILE\"",
    "stat -c '%a %U' \"$PAPER_ENV_FILE\"",
    "( set -a; . \"$PAPER_ENV_FILE\"; set +a; exec python3 blueprints/us-equities/alpaca-paper/paper_runner.py --once )",
    # Hugging Face: hf reads its own store, so checking the sign-in, the operator's interactive
    # login, revision-pinned downloads and checksum verification never expose the token.
    "hf auth whoami",
    "hf auth login",
    "hf auth login --force",
    "hf download nvidia/Nemotron-3-Embed-1B-BF16 --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 "
    "--local-dir /srv/models/nemotron",
    "hf cache verify nvidia/Nemotron-3-Embed-1B-BF16 --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 "
    "--local-dir /srv/models/nemotron",
    "hf cache ls",
    "hf cache ls --revisions",
    "stat -c '%a %U' \"$HF_TOKEN_PATH\"",
    "env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN python3 run.py",
    # The kernel keyring: store, status and revoke, and the documented exec and tvly-keyring forms.
    "python3 scripts/kernel_keyring.py store tavily_api_key",
    "python3 scripts/kernel_keyring.py store --replace tavily_api_key",
    "python3 scripts/kernel_keyring.py status tavily_api_key",
    "python3 scripts/kernel_keyring.py revoke tavily_api_key",
    "( set +x; read -rs K && printf %s \"$K\" | python3 scripts/kernel_keyring.py store tavily_api_key )",
    f"{EXEC} tvly auth --json",
    f"{EXEC} tvly --json auth",
    f"{EXEC} tvly search \"<query>\" --depth basic --max-results 5 --json",
    f"{EXEC} tvly extract \"<url>\" --extract-depth basic --json",
    f"{EXEC} tvly research run \"<question>\" --model pro --json",
    f"{EXEC} tvly research poll \"<request_id>\" --json",
    f"{EXEC} tvly search \"python os.environ versus getenv\" --json",
    f"{EXEC} tvly search \"env var best practice\" --json",
    f"{EXEC} env -u OTHER_TOKEN tvly search x --json",
    f"{EXEC} tvly research run \"q\" --model pro --json "
    "| python3 -c 'import json, sys; print(json.load(sys.stdin)[\"status\"])'",
    "python3 \"$SP/kernel_keyring.py\" exec tavily_api_key TAVILY_API_KEY -- tvly research run --model pro --json "
    "--citation-format numbered --timeout 1500 --client-name native-agent-stack -o \"$out\" \"$q\" < /dev/null "
    "> \"$S/tavily/$lid.stdout\" 2> \"$S/tavily/$lid.stderr\"",
    f"{DEMO_EXEC} python3 run.py",
    "tvly-keyring search \"<query>\" --json",
    "tvly-keyring research run \"<question>\" --model pro --json",
    "tvly-keyring auth --json",
    "tvly auth --json",
    "tvly auth --help",
    "tvly --status",
    "keyctl show @u",
    "keyctl describe %user:native-agent-stack:tavily_api_key",
    "keyctl request user native-agent-stack:tavily_api_key",
    "keyctl request2 user native-agent-stack:tavily_api_key callout-info",
]

# Negative corpus: ordinary repository and shell work that must never be blocked.
SAFE_CORPUS = [
    "ls -la",
    "pwd",
    "git status --short",
    "git log --oneline -5",
    "git diff origin/main...HEAD --stat",
    "git grep -n shell_environment_policy -- docs",
    "git -C ../other grep -n TODO",
    "git commit -m 'Tighten the secret guard'",
    "git push origin HEAD:feature",
    "gh pr view 12 --json title",
    "gh auth status",
    "gh auth setup-git",
    "git config --get credential.helper",
    "git credential-cache exit",
    "git commit -m 'Block git credential fill in the guard'",
    "grep -rn TODO docs",
    "grep -rn 'def check' scripts/hooks",
    "grep -n OTEL_LOG_TOOL_CONTENT docs/secret-storage.md",
    "grep -rn environ scripts/credential_status.py",
    "grep -c SECRET_NAMES scripts/hooks/secret_path_guard.py",
    "rg -n 'shell_environment_policy' docs adoption",
    "rg --files | wc -l",
    "ag --python parse_args tools",
    "ack -l shlex scripts",
    "sed -n '1,80p' scripts/credential_status.py",
    "sed -i 's/foo/bar/' README.md",
    "awk -F, '{print $2}' data.csv",
    "awk 'NR<=5' manifests/stack.json",
    "cat README.md | head -20",
    "head -n 40 docs/secret-storage.md",
    "tail -f logs/app.log",
    "jq '.files | length' manifests/evidence.json",
    "diff -u a.txt b.txt",
    "sort -u names.txt | uniq -c",
    "find . -name '*.py' -newer setup.cfg -print",
    "find . -name '*.py' -exec wc -l {} +",
    "find . -name '*.py' -exec grep -l shlex {} +",
    "find . -type f -name '*.md' | xargs grep -l 'secret storage'",
    "python3 -m unittest tests.test_secret_path_guard",
    "uv run -q --no-project --with pyyaml python -m unittest tests.test_credential_status",
    "python3 scripts/validate.py",
    "python3 -c 'import os; print(os.environ.get(\"HOME\"))'",
    "make -j4 test",
    "npm test",
    "set -x; make test",
    "bash -x scripts/build.sh",
    "bash -lc 'git status'",
    "sh -c 'echo hello'",
    "set -euo pipefail; python3 run.py",
    "source .venv/bin/activate && set -x && pytest -q",
    ". ~/.bashrc; env -u HF_TOKEN python3 x.py",
    "export PATH=\"$HOME/.local/bin:$PATH\"",
    "declare -a arr=(1 2 3)",
    "printf '%s\\n' \"$PATH\"",
    "echo \"$HOME\"",
    "cat /proc/cpuinfo",
    "wc -l /proc/self/status",
    "ls /proc/self/fd",
    "ps -ef | grep python",
    "docker ps --format '{{.Names}}'",
    "cp docs/examples/alpaca-paper.env.example /tmp/template.txt",
    "sed -n 1,10p docs/examples/sec-contact.env.example",
    "eval \"$(ssh-agent -s)\"",
    "timeout 30 python3 scripts/landscape.py --root .",
    "cp .env.example .env",
    "cp -n docs/examples/alpaca-paper.env.example ./local.env",
    "cat docs/examples/sec-contact.env.example > .env.local",
    "echo 'PORT=3000' | tee -a .env",
    "set -a; source .env; set +a; npm run dev",
    "ls -la .env",
    # The Hugging Face cache beside the token files stays usable.
    "ls -la ~/.cache/huggingface",
    "du -sh ~/.cache/huggingface/hub",
    "rg -n tokenizer ~/.cache/huggingface/hub/models--x/snapshots",
    "cat ~/.cache/huggingface/hub/models--x/refs/main",
    "find ~/.cache/huggingface -name '*.incomplete' -delete",
    "rsync -a /mnt/backup/hf/hub ~/.cache/huggingface/",
    "HF_HUB_OFFLINE=1 python3 serve.py",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN=1 python3 worker.py",
    "git clone https://github.com/huggingface/tokenizers",
    "hf download huggingface/token-classification-demo --local-dir demo",
    "pip download huggingface_hub",
    # Work on the keyring code itself: a search or a commit message that names KEYCTL_READ or keyctl
    # print runs no interpreter, and tvly without a key or through the wrapper's install.
    "grep -n KEYCTL_READ scripts/kernel_keyring.py",
    "git commit -m 'Block keyctl print and KEYCTL_READ in the guard'",
    "git commit -m 'Guard: tvly auth prints part of the key'",
    "python3 -m unittest tests.test_kernel_keyring tests.test_tvly_keyring",
    "python3 -m pytest -k keyctl_read",
    "install -m 0755 adoption/tools/tvly-keyring scripts/kernel_keyring.py \"$HOME/.local/share/codex-ecosystem/bin/\"",
    "sh -n adoption/tools/tvly-keyring",
    "cat adoption/tools/tvly-keyring",
    "tvly search \"agent harness\" --depth basic --max-results 4 --json",
    "tvly --version",
    "ls ~/.tavily",
]

# Known heuristic gaps, asserted so a change that closes one is noticed.
EXPECTED_PASS_THROUGH = [
    "python3 -c \"import runner; print(runner.credentials(__import__('os').path.expandvars('$PAPER_ENV_FILE')))\"",
    "python3 -c 'import os;print(dict(os.environ))'",
    # huggingface_hub's own loader, and an archiver on the whole Hugging Face home.
    "python3 -c 'from huggingface_hub import get_token; print(get_token())'",
    "tar czf /tmp/hf.tgz -C ~/.cache huggingface",
    # An inline interpreter that opens $HF_TOKEN_PATH itself never spells a literal
    # `$HF_TOKEN_PATH`, so POINTER_VARIABLE never sees it.
    "python3 -c \"import os; print(open(os.environ['HF_TOKEN_PATH']).read())\"",
    # A recursive read or copy of an ancestor of the Hugging Face home (~, $HOME, ~/.cache,
    # $XDG_CACHE_HOME with a trailing / or /*) reaches it without ever naming it, so
    # HF_HOME_ROOT never matches the operand.
    "cp -r ~ /tmp/exfil",
    "cp -r \"$HOME\" /tmp/exfil",
    "cp -r ~/.cache /tmp/exfil",
    "cp -r \"$XDG_CACHE_HOME/\" /tmp/exfil",
    "cp -r \"$XDG_CACHE_HOME\"/* /tmp/exfil",
    # A relative read after `cd` into the Hugging Face home never spells the path in the
    # reader's own segment.
    "cd ~/.cache/huggingface && cat token",
    # A trailing `/.` on $HF_HOME copies its contents but does not match HF_HOME_ROOT's
    # anchored `(?:/\\**)?$` suffix.
    "cp -r \"$HF_HOME/.\" /tmp/exfil",
    # Kernel keyring: a shell or interpreter that exec starts reads its commands from a pipe or a
    # file the guard never sees; a copy of kernel_keyring.py under another name is not recognised;
    # and a raw keyctl system call whose number is held in a variable is not KEYRING_READ_CODE.
    f"printf 'env\\n' | {EXEC} sh",
    f"{EXEC} python3 run_report.py",
    "cp scripts/kernel_keyring.py /tmp/kk.py && python3 /tmp/kk.py exec tavily_api_key TAVILY_API_KEY -- env",
    "python3 -c 'import ctypes; n = 250; ctypes.CDLL(None).syscall(n, 11, 1, None, 0)'",
]


def run_hook(payload):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)


def fenced_lines(path):
    """Lines of the fenced code blocks of a Markdown file."""
    return [line for block in re.findall(r"^```[^\n]*\n(.*?)^```", path.read_text(encoding="utf-8"), re.M | re.S)
            for line in block.splitlines()]


class SecretPathGuardTests(unittest.TestCase):
    def test_blocked_commands(self):
        for command, reason in {**BLOCKED, **KEYRING_BLOCKED}.items():
            with self.subTest(command=command):
                self.assertEqual(guard.check(command), reason)

    def test_every_rule_applies_to_a_keyring_exec(self):
        # Every blocked command stays blocked, for the same reason, when kernel_keyring.py exec starts
        # its first segment. An environment dump in the started command gets the keyring's own reason,
        # because the key is in that environment; one in a later segment keeps its own.
        for command, reason in BLOCKED.items():
            with self.subTest(command=command):
                expected = {reason, "environment_dump_in_keyring_exec"} if reason.startswith("environment_dump") \
                    else {reason}
                self.assertIn(guard.check(f"{EXEC} {command}"), expected)

    def test_documented_keyring_commands_pass(self):
        # The keyring commands in the fenced blocks of the pages that document them.
        documented = [line for page in ("recipes/tavily.md", "docs/secret-storage.md", "adoption/tools/README.md")
                      for line in fenced_lines(ROOT / page)
                      if "kernel_keyring.py" in line or "tvly-keyring" in line]
        self.assertGreaterEqual(len(documented), 10)
        for command in documented:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_allowed_commands(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_safe_corpus_is_never_blocked(self):
        for command in SAFE_CORPUS:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_every_secret_name_is_caught_by_a_search(self):
        for name in guard.SECRET_NAMES:
            with self.subTest(name=name):
                self.assertEqual(guard.check(f"rg -n {name}"), "secret_name_search")
                self.assertIsNone(guard.check(f"rg -n MY_{name}_HINT"))

    def test_inventory_secret_names_are_all_guarded(self):
        # Contact identities (SEC_USER_AGENT) are private data that recipes pass to
        # curl by reference, and CI secrets live only in GitHub Actions; neither is
        # an agent-side authentication value, so both stay out of the hook's list.
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        names = set(inventory["must_not_be_set"])
        for entry in inventory["entries"]:
            if entry["class"] not in {"contact_identity", "ci_secret"}:
                names.update(entry.get("variables", []))
        self.assertTrue(names)
        self.assertEqual(sorted(names - set(guard.SECRET_NAMES)), [])
        self.assertEqual(len(guard.SECRET_NAMES), len(set(guard.SECRET_NAMES)))

    def test_inventory_pointer_variables_are_guarded(self):
        # A pointer variable (PAPER_ENV_FILE, or huggingface_hub's own HF_TOKEN_PATH) names a
        # credential file, so a reader on it is blocked for every inventory entry.
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        pointers = {name for entry in inventory["entries"] for name in entry["pointer_variables"]}
        self.assertIn("HF_TOKEN_PATH", pointers)
        for name in sorted(pointers):
            with self.subTest(name=name):
                self.assertEqual(guard.check(f"cat \"${name}\""), "credential_file_read")
                self.assertEqual(guard.check(f"cat \"${{{name}}}\""), "credential_file_read")

    def test_known_bypasses_are_recorded_not_claimed(self):
        for command in EXPECTED_PASS_THROUGH:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_hook_protocol_exit_codes_and_no_echo(self):
        command = "cat ~/.config/native-agent-stack/alpaca-paper.env # SENTINEL-4f1d"
        blocked = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("credential_store_path", blocked.stderr)
        self.assertNotIn("SENTINEL-4f1d", blocked.stderr + blocked.stdout)
        self.assertEqual(blocked.stderr.count("\n"), 1)
        allowed = run_hook({"tool_name": "Bash", "tool_input": {"command": "git status"}})
        self.assertEqual((allowed.returncode, allowed.stdout, allowed.stderr), (0, "", ""))
        keyring = run_hook({"tool_name": "Bash", "tool_input": {"command": f"{EXEC} env # SENTINEL-9c2e"}})
        self.assertEqual(keyring.returncode, 2)
        self.assertIn("environment_dump_in_keyring_exec", keyring.stderr)
        self.assertNotIn("SENTINEL-9c2e", keyring.stderr + keyring.stdout)
        self.assertEqual(keyring.stderr.count("\n"), 1)
        other_tool = run_hook({"tool_name": "Read", "tool_input": {"file_path": "x"}})
        self.assertEqual(other_tool.returncode, 0)
        malformed = subprocess.run([sys.executable, str(HOOK)], input="not json",
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(malformed.returncode, 1)

    def test_project_settings_register_hook_and_deny_rules(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        self.assertNotIn("allow", settings["permissions"])
        deny = settings["permissions"]["deny"]
        for rule in ("Read(~/.config/native-agent-stack/**)", "Edit(~/.config/native-agent-stack/**)",
                     "Read(~/.claude/.credentials.json)", "Read(~/.codex/auth.json)",
                     "Read(~/.config/gh/hosts.yml)", "Read(//proc/*/environ)",
                     "Read(~/.cache/huggingface/token)", "Read(~/.cache/huggingface/stored_tokens)",
                     "Bash(printenv *)", "Bash(env)", "Bash(gh auth token *)",
                     "Bash(hf auth token)", "Bash(hf auth token *)",
                     "Bash(git credential fill*)", "Bash(gh auth git-credential *)"):
            self.assertIn(rule, deny)
        self.assertLess(deny.index("Read(.env.*)"), deny.index("Read(!.env.example)"))
        hooks = settings["hooks"]["PreToolUse"]
        self.assertEqual(hooks[0]["matcher"], "Bash")
        self.assertIn("scripts/hooks/secret_path_guard.py", hooks[0]["hooks"][0]["command"])
        self.assertNotIn("/home/", json.dumps(settings))


    def test_host_profile_copy_is_verbatim(self):
        if IN_CI:
            self.skipTest("running in CI: a runner has no host install of the guard to compare")
        if not HOST_HOOK.is_file():
            self.skipTest(f"no host guard at {HOST_HOOK}; "
                          "tools/adoption/install_claude_profile.py --only guard installs it")
        self.assertEqual(HOOK.read_bytes(), HOST_HOOK.read_bytes(),
                         "the installed user-scope guard must be a verbatim copy of scripts/hooks/secret_path_guard.py")


if __name__ == "__main__":
    unittest.main()
