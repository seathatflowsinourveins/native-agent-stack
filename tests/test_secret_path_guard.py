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
# The OpenHands runtime-worker session-key directory (PR #425's host driver); the run id and arm in the file names
# below are illustrative.
OH_SECRETS = "~/.local/state/native-agent-stack/runtime-workers/openhands/secrets"

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
    # The text rules read the command after the shell's quote removal and with every backslash-newline
    # joined: the inner shell of `sh -c 'echo $GH_TO''KEN'` runs `echo $GH_TOKEN`.
    "sh -c 'echo $GH_TO''KEN'": "secret_variable_reference",
    "echo \"$TAVILY_API_\\\nKEY\"": "secret_variable_reference",
    "ls \"$HOME/.config/native-agent-\"stack": "credential_store_path",
    # Output redirections before the command, and launcher options as getopt reads them (`-iu root`:
    # -u takes the next word), never hide the program.
    "> /tmp/out tvly auth": "native_token_print",
    "2>/dev/null cat .env": "dotenv_read",
    "2>&1 cat .env": "dotenv_read",
    "sudo -iu root cat .env": "dotenv_read",
    "nice -n 5 cat .env": "dotenv_read",
    "stdbuf -o0 cat .env": "dotenv_read",
    # Home credential stores as a reader's operand (2026-09-27, synthesis PR-A row A1): an SSH private key (a glob
    # too), the AWS, Docker, kube, git-credential, netrc, npm and PyPI files, an option's `=` value, and Codex shell
    # snapshots, which record every exported value. The rest of each store follows further down.
    "cat ~/.ssh/id_ed25519": "credential_file_read",
    "cp ~/.ssh/id_rsa /tmp/key": "credential_file_read",
    "base64 \"$HOME/.ssh/id_ecdsa\"": "credential_file_read",
    "cat ~/.ssh/id_*": "credential_file_read",
    "cat ~/.aws/credentials": "credential_file_read",
    "jq . ~/.docker/config.json": "credential_file_read",
    "grep token ~/.kube/config": "credential_file_read",
    "cat ~/.git-credentials": "credential_file_read",
    "cat ~/.netrc": "credential_file_read",
    "curl --netrc-file=/home/example/.netrc https://example.invalid": "credential_file_read",
    "head -5 ~/.npmrc": "credential_file_read",
    "cat ~/.pypirc": "credential_file_read",
    "grep -r OMNIROUTE ~/.codex/shell_snapshots/": "credential_file_read",
    "cat \"$CODEX_HOME\"/shell_snapshots/*.sh": "credential_file_read",
    "dd if=/home/example/.npmrc of=/tmp/npmrc": "credential_file_read",
    # GNU cp -t/--target-directory names the destination first, so every other operand is a source (cp(1)).
    "cp -t /tmp /tmp/lane/shell_snapshots/example.sh": "credential_file_read",
    "cp -vt /tmp ~/.netrc": "credential_file_read",
    "cp --target-directory /tmp ~/.pypirc": "credential_file_read",
    # A search keeps every argument when -e/-f supply the patterns or an option that can take a file or glob
    # comes before the pattern (`--include .netrc` and rg's `-g .netrc` select that file).
    "grep -r --include .netrc token ~": "credential_file_read",
    "rg --hidden -g .netrc token ~": "credential_file_read",
    "grep -e token ~/.netrc": "credential_file_read",
    "grep -f ~/.git-credentials notes.txt": "credential_file_read",
    "grep -A 2 token ~/.netrc": "credential_file_read",
    # rtk 0.50.0 runs these (`rtk --help`): `read`, `smart`, `json` and `log` read their files, `run` hands its
    # command to `sh -c`, `proxy`/`summary`/`err`/`test` run the command after them, and `env` prints the
    # environment. Every rule reads that command (test_every_rule_applies_behind_rtk_proxy).
    "rtk read ~/.ssh/id_ed25519": "credential_file_read",
    "rtk grep token ~/.kube/config": "credential_file_read",
    "rtk json ~/.docker/config.json": "credential_file_read",
    "rtk run -c 'cat ~/.netrc'": "credential_file_read",
    "rtk run --skip-env cat ~/.git-credentials": "credential_file_read",
    "rtk -v summary --ultra-compact cat ~/.aws/credentials": "credential_file_read",
    "rtk proxy cat .env": "dotenv_read",
    "rtk env": "environment_dump",
    # OmniRoute keeps its secrets in .env layers and server.env in its data directory: dotenv files there, now
    # reported as reads of the data directory, which the store rule checks first.
    "cat ~/.omniroute/.env": "credential_file_read",
    "cat ~/.config/omniroute/server.env": "credential_file_read",
    "cat /srv/omniroute-data/.env": "dotenv_read",
    # Every path the template's credential-store Read denies cover (2026-09-27 independent verification). rtk 0.50.0
    # rewrites `cat`, `head` and `tail -n` of them to `rtk read` before Claude Code checks its rules, so on an RTK
    # host the guard is what stops those readers (test_every_template_read_deny_has_a_blocked_bash_reader). Anything
    # in the SSH, GnuPG, AWS, Azure, kube and OmniRoute directories counts, `.pub`, `config` and a key under any name
    # included, because the template denies all of ~/.ssh (a carve-out is an open user decision that would change
    # both); so do each directory itself and a glob in it, and the Docker home as a whole.
    "cat ~/.ssh/config": "credential_file_read",
    "cat ~/.ssh/id_ed25519.pub": "credential_file_read",
    "cp ~/.ssh/id_*.pub /tmp/keys/": "credential_file_read",
    "cp -t /tmp/keys ~/.ssh/id_ed25519.pub": "credential_file_read",
    "cat ~/.ssh/github_deploy_key": "credential_file_read",
    "cat ~/.aws/config": "credential_file_read",
    "cat ~/.azure/msal_token_cache.json": "credential_file_read",
    "cat ~/.omniroute/storage.sqlite": "credential_file_read",
    "cat ~/.config/omniroute/storage.sqlite": "credential_file_read",
    "cat /mnt/c/Users/example/AppData/Roaming/omniroute/storage.sqlite": "credential_file_read",
    "cat ~/.gnupg/private-keys-v1.d/ABCD.key": "credential_file_read",
    "tail ~/.kube/cache/discovery/example/servergroups.json": "credential_file_read",
    "cat ~/.ssh/*": "credential_file_read",
    "head -n 100 ~/.ssh/*": "credential_file_read",
    "base64 ~/.ssh/*": "credential_file_read",
    "cp -r ~/.ssh /tmp/k": "credential_file_read",
    "rsync -a ~/.ssh/ /tmp/k/": "credential_file_read",
    "grep -r BEGIN ~/.ssh": "credential_file_read",
    "grep -r -A 40 PRIVATE ~/.ssh/": "credential_file_read",
    "cat ~/.aws/*": "credential_file_read",
    "cp -r ~/.aws /tmp/a": "credential_file_read",
    "cat ~/.kube/*": "credential_file_read",
    "find ~/.ssh -type f -exec cat {} +": "credential_file_read",
    "find ~/.aws -name credentials -exec cat {} \\;": "credential_file_read",
    "rtk read ~/.aws/*": "credential_file_read",
    "cat ~/.docker/*": "credential_file_read",
    "cp -r ~/.docker /tmp/d": "credential_file_read",
    "cat ~/.config/nativestack/example.key": "credential_file_read",
    # Erring toward blocking (docs/secret-storage.md): a client whose key or home option names a store as the
    # operand of a program the guard treats as a reader. A key named in ~/.ssh/config or loaded with ssh-add, and
    # gpg without --homedir, pass.
    "scp -i ~/.ssh/nas_key build.tgz nas:/volume1/": "credential_file_read",
    "rsync -a -e 'ssh -i ~/.ssh/nas_key' dist/ nas:/volume1/dist/": "credential_file_read",
    "gpg --homedir ~/.gnupg --list-keys": "credential_file_read",
    # OpenHands runtime-worker session keys (2026-09-28): for each attempt the host driver writes the agent-server
    # key to <run-id>-<arm>.server.env (Docker env-file syntax) and <run-id>-<arm>.headers (a `curl -H @file` header
    # line) in a 0700 secrets directory, and deletes both once the attempt's containers are removed. A reader, copy or
    # search of either file, of the directory itself and of a glob in it is blocked. The .server.env file, which the
    # dotenv rule already caught, is now reported as a read of the directory, which the store rule checks first; curl
    # is one of the guard's readers, so a curl that reads the header file is blocked too, as `curl --netrc-file` is.
    f"cat {OH_SECRETS}/rw-1-engines-on.headers": "credential_file_read",
    f"head -c 80 {OH_SECRETS}/rw-1-engines-on.headers": "credential_file_read",
    f"cp {OH_SECRETS}/rw-1-engines-on.headers /tmp/h": "credential_file_read",
    f"grep -r X-Session-API-Key {OH_SECRETS}": "credential_file_read",
    f"rg -uu . {OH_SECRETS}/": "credential_file_read",
    f"rg Key {OH_SECRETS}/*.headers": "credential_file_read",
    f"cat {OH_SECRETS}/*": "credential_file_read",
    f"cp -r {OH_SECRETS} /tmp/s": "credential_file_read",
    f"cat {OH_SECRETS}/rw-1-engines-on.server.env": "credential_file_read",
    "cat \"$HOME/.local/state/native-agent-stack/runtime-workers/openhands/secrets/rw-1-engines-on.headers\"":
        "credential_file_read",
    "tail -n 1 \"${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/runtime-workers/openhands/secrets\"/*":
        "credential_file_read",
    "curl -H @\"$HOME/.local/state/native-agent-stack/runtime-workers/openhands/secrets/rw-1-engines-on.headers\" "
    "http://127.0.0.1:8000/alive": "credential_file_read",
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
    # keyctl list and rlist print any key's payload as integers: they do not check that the target is a
    # keyring (keyctl(1); keyutils act_keyctl_list/rlist). A serial, a `%user:` key and @a (the
    # request_key authorisation key) are not unambiguous keyrings (ALLOWED has those that are).
    "keyctl rlist %user:native-agent-stack:tavily_api_key": "keyring_payload_read",
    "keyctl list %user:native-agent-stack:tavily_api_key": "keyring_payload_read",
    "keyctl rlist 123456789": "keyring_payload_read",
    "keyctl list 123456789": "keyring_payload_read",
    "keyctl rlist @a": "keyring_payload_read",
    # GPT-6 re-check of 74508203: a key id before a redirection was read as its descriptor.
    "keyctl rlist 123456789 </dev/null": "keyring_payload_read",
    "keyctl list -4": "keyring_payload_read",
    "keyctl list %keyring:native-agent-stack": "keyring_payload_read",
    "keyctl list": "keyring_payload_read",
    "keyctl list @u": "keyring_payload_read",
    "keyctl rlist @u 2>/dev/null": "keyring_payload_read",
    "keyctl list %:native-agent-stack": "keyring_payload_read",
    # The same re-check: quote removal merged "$KK_DEMO_TOKEN"x into another name.
    "python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TOKEN -- sh -c 'echo \"$KK_DEMO_TOKEN\"x'": "keyring_variable_reference",
    "keyctl rlist 2>/dev/null %user:native-agent-stack:tavily_api_key": "keyring_payload_read",
    "sudo keyctl rlist 123456789": "keyring_payload_read",
    "python3 -c 'import subprocess; subprocess.run([\"keyctl\", \"rlist\", \"123\"])'": "keyring_payload_read",
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
    # However exec's own argument is spelled (split by quotes, a backslash or a line continuation) and
    # however often the guard's parse repeats it (env, eval, a nested sh -c), only that argument's span
    # is exempt; the reference in the started command still counts.
    "python3 scripts/kernel_keyring.py exec tavily_api_key KK_DEMO_TO\"KEN\" -- sh -c 'echo \"$KK_DEMO_TOKEN\"'":
        "keyring_variable_reference",
    "python3 scripts/kernel_keyring.py exec kk_demo 'KK_DEMO'_TOKEN -- sh -c 'echo $KK_DEMO_TOKEN'":
        "keyring_variable_reference",
    "python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TO\\KEN -- sh -c 'echo $KK_DEMO_TOKEN'":
        "keyring_variable_reference",
    "python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TO\\\nKEN -- sh -c 'echo $KK_DEMO_TOKEN'":
        "keyring_variable_reference",
    "sh -c 'python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TO\"KEN\" -- sh -c \"echo \\$KK_DEMO_TOKEN\"'":
        "keyring_variable_reference",
    f"env LC_ALL=C {DEMO_EXEC} sh -c 'echo $KK_DEMO_TOKEN'": "keyring_variable_reference",
    f"eval {DEMO_EXEC} printenv KK_DEMO_TOKEN": "keyring_variable_reference",
    f"{DEMO_EXEC} sh -c 'echo \"$KK_DEMO_TO\"\"KEN\"'": "keyring_variable_reference",
    # A line continuation cannot hide the separator, and quotes cannot hide a keyword from the code check.
    "python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY \\\n-- env": "environment_dump_in_keyring_exec",
    f"{EXEC} python3 -c 'import os; print(os.envi''ron)'": "environment_dump_in_keyring_exec",
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
    # A launcher's options (getopt: glued `-o0`, separate `-o 0`, `-I {}`; xargs -i and -l take only a
    # glued value) never hide the program it starts.
    f"{EXEC} stdbuf -o0 python3 -c 'from os import environb; print(environb)'": "environment_dump_in_keyring_exec",
    f"{EXEC} stdbuf -o 0 python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} nice -n 5 python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} timeout -s KILL 5 python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"printf x | {EXEC} xargs -I {{}} python3 -c 'import os; print(os.environ)' {{}}": "environment_dump_in_keyring_exec",
    f"printf x | {EXEC} xargs -i python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"printf x | {EXEC} xargs -l python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} stdbuf -oL awk 'BEGIN {{ for (k in ENVIRON) print k, ENVIRON[k] }}'": "environment_dump_in_keyring_exec",
    f"{EXEC} stdbuf -o0 bash -c 'for v in ${{!TAV*}}; do echo \"${{!v}}\"; done'": "environment_dump_in_keyring_exec",
    # Launchers the guard does not model: every argument that names a shell, an interpreter, awk, jq,
    # env, printenv, ps or a shell builtin that prints variables is read as a command from there on.
    f"{EXEC} find /tmp -maxdepth 0 -exec env ';'": "environment_dump_in_keyring_exec",
    f"{EXEC} find . -maxdepth 0 -exec python3 -c 'import os; print(os.environ)' ';'": "environment_dump_in_keyring_exec",
    f"{EXEC} stdbuf -o0 printenv": "environment_dump_in_keyring_exec",
    f"{EXEC} watch -n 5 /usr/bin/env": "environment_dump_in_keyring_exec",
    f"{EXEC} watch -n1 python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} flock /tmp/lock python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} taskset -c 0 python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} /usr/bin/time -f %e python3 -c 'import os; print(os.environ)'": "environment_dump_in_keyring_exec",
    f"{EXEC} watch -n 5 export -p": "environment_dump_in_keyring_exec",
    f"{EXEC} flock /tmp/lock sh -c set": "environment_dump_in_keyring_exec",
    # The price of that rule: a one-word query `env` is blocked too, and `set` as the last word; a longer
    # query, or `set --json`, passes (ALLOWED).
    f"{EXEC} tvly search env --json": "environment_dump_in_keyring_exec",
    f"{EXEC} tvly search set": "environment_dump_in_keyring_exec",
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
    # A named-descriptor redirection is not the --json flag (GPT-6 re-check of 74508203).
    "tvly-keyring {fd}>--json auth": "native_token_print",
    "~/.local/bin/tvly auth > /tmp/auth.txt": "native_token_print",
    f"{EXEC} tvly auth": "native_token_print",
    "tvly-keyring auth": "native_token_print",
    "sh adoption/tools/tvly-keyring auth": "native_token_print",
    # A redirection's target or a here-document delimiter is not a flag: each runs plain `tvly auth`.
    f"{EXEC} tvly auth > --json; cat -- --json": "native_token_print",
    "tvly auth >> --json": "native_token_print",
    "tvly auth 2> --json": "native_token_print",
    "tvly auth &> --json": "native_token_print",
    "tvly auth <<< --json": "native_token_print",
    "tvly auth < --help": "native_token_print",
    "tvly auth << --json\n--json": "native_token_print",
    "tvly auth <<- --json\n--json": "native_token_print",
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
    "tvly --json auth",
    # A query word that names a builtin, followed by long options, is data (re-check false block).
    "tvly-keyring search \"export\" --depth basic --max-results 5 --json",
    # A URL whose last path segment is env or printenv is an argument, not a launched program.
    "tvly-keyring extract \"https://www.gnu.org/software/coreutils/env\" --json",
    "python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly extract https://man7.org/linux/man-pages/man1/printenv.1.html/printenv --json",
    "tvly auth --json",
    "tvly auth --help",
    "tvly --status",
    "keyctl show @u",
    "keyctl describe %user:native-agent-stack:tavily_api_key",
    "keyctl request user native-agent-stack:tavily_api_key",
    "keyctl request2 user native-agent-stack:tavily_api_key callout-info",
    # keyctl list and rlist on an unambiguous keyring (special ID, -1 to -6, or a keyring by name), and
    # without a target (a usage error that reads nothing).
    "python3 -c 'import subprocess; subprocess.run([\"keyctl\", \"list\", \"@u\"])'",
    # The documented exec inside a shell, eval or env, twice, with a quoted or split-quoted argument, and
    # behind launchers: exec's own argument, parsed more than once, is still exempt.
    "sh -c 'python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly search x --json'",
    "bash -lc \"python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TOKEN -- python3 run.py\"",
    f"eval {DEMO_EXEC} python3 run.py",
    f"env LC_ALL=C {DEMO_EXEC} python3 run.py",
    f"{DEMO_EXEC} python3 run.py && {DEMO_EXEC} python3 run.py --again",
    "python3 scripts/kernel_keyring.py exec kk_demo \"KK_DEMO_TOKEN\" -- python3 run.py",
    "python3 scripts/kernel_keyring.py exec kk_demo KK_DEMO_TO\"KEN\" -- python3 run.py",
    f"{EXEC} stdbuf -o0 tvly search x --json",
    f"{EXEC} nice -n 5 tvly research run \"q\" --model pro --json",
    f"{EXEC} timeout 600 tvly research run \"q\" --model pro --json",
    f"{EXEC} tvly search python --json",
    f"{EXEC} tvly search set --json",
    "tvly auth --json > auth.json",
    "tvly auth --json 2>&1",
    # Commands that live lanes schedule (2026-09-28 non-regression): the paper lane's key wrapper starting a command,
    # keyring status without a name, and exec's own help. The documented exec forms, `kernel_keyring.py exec <name>
    # <ENV_VAR> -- <command>`, are above ({EXEC} and {DEMO_EXEC}) and in test_documented_keyring_commands_pass.
    "sh ~/.local/state/native-agent-stack/alpaca-paper/paperkeys.sh run 1 -- echo ok",
    "python3 scripts/kernel_keyring.py status",
    "python3 scripts/kernel_keyring.py exec --help",
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
    "timeout -s KILL 30 python3 scripts/landscape.py --root .",
    "nice -n 10 make test",
    "stdbuf -oL python3 -m unittest tests.test_secret_path_guard",
    "find . -name '*.py' -print0 | xargs -0 -n 20 wc -l",
    "printf 'a\\n' | xargs --max-lines echo",
    "/usr/bin/time -f %e make test",
    "sudo -u postgres psql -c 'select 1'",
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
    # The home credential-store rule blocks readers only: clients that use a key or a store, listings, status
    # and mode changes pass (the H4 chmod of Codex snapshots included), and so do the Docker and Codex files that
    # hold no credential.
    "ssh-add",
    "ssh-add ~/.ssh/id_ed25519",
    "ssh -i ~/.ssh/id_ed25519 git@github.com",
    "ssh-keygen -y -f ~/.ssh/id_ed25519",
    "ls -la ~/.ssh",
    "ls -la ~/.aws ~/.kube ~/.gnupg",
    "chmod 700 ~/.ssh",
    "stat -c '%a %U' ~/.ssh/id_ed25519",
    "gh ssh-key add ~/.ssh/id_ed25519.pub --title example",
    "kubectl --kubeconfig ~/.kube/config get pods",
    "curl --netrc https://example.invalid",
    "chmod 600 ~/.codex/shell_snapshots/*.sh",
    "ls ~/.codex/shell_snapshots",
    "cat ~/.docker/buildx/current",
    "cat ~/.codex/config.toml",
    # A search's own pattern is not a file it reads (grep(1): PATTERNS before FILE), when only plain flags
    # come before it; dd writes its of= file; cp -t copies into the directory it names.
    "rg shell_snapshots docs",
    "grep -nF '.ssh/id_ed25519' README.md",
    "rg -n '\\.aws/credentials' docs",
    "git grep -n '.kube/config' -- docs",
    "grep -- ~/.netrc README.md",
    "dd of=/home/example/.npmrc if=template.npmrc",
    "cp -t /tmp/out docs/secret-storage.md",
    # Ordinary rtk use: filtered git, raw re-runs through `rtk proxy`, reading a repository file, a listing.
    "rtk git status",
    "rtk proxy git show HEAD:README.md",
    "rtk proxy python3 -m unittest tests.test_secret_path_guard",
    "rtk read README.md",
    "rtk grep -n shell_snapshots docs",
    "rtk ls ~/.ssh",
    "rtk hook check 'git push origin HEAD'",
    "rtk --version",
    # The OpenHands session-key rule blocks readers only (2026-09-28): a listing, status, mode changes, an existence
    # check after cleanup, a `docker run --env-file` that hands the file to Docker, the rest of the runtime-worker
    # state and a search whose pattern names the directory pass. So does a code search of OH_SESSION_API_KEYS_0,
    # which is not one of the guard's secret names (docs/secret-storage.md, "Home and tool credential stores").
    f"ls -la {OH_SECRETS}",
    f"stat -c '%a %U' {OH_SECRETS}/rw-1-engines-on.headers",
    f"chmod 700 {OH_SECRETS}",
    f"chmod 600 {OH_SECRETS}/rw-1-engines-on.headers",
    f"test ! -e {OH_SECRETS}/rw-1-engines-on.headers && echo deleted",
    f"docker run --rm --env-file {OH_SECRETS}/rw-1-engines-on.server.env example/agent-server",
    "cat ~/.local/state/native-agent-stack/runtime-workers/openhands/runs/rw-1/engines-on/status.json",
    "rg -n 'runtime-workers/openhands/secrets' docs",
    "rg -n OH_SESSION_API_KEYS_0 docs",
    "grep -n OH_SESSION_API_KEYS_0 docs/secret-storage.md",
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
    # A variable name the started command assembles at run time; a launcher that takes its command as
    # one string (`script -c`); and a reader behind a launcher the guard does not model, which only
    # the keyring checks read through.
    f"{DEMO_EXEC} sh -c 'eval echo \\$KK_DEMO_TOK$0' EN",
    f"{EXEC} script -qc 'export -p' /dev/null",
    "watch -n 5 cat .env",
    # Home credential stores: a relative read after `cd`, a client that prints its own store, a program that
    # opens a store itself (the database file name is illustrative), an archiver on a store, a glob that names a
    # store only after the shell expands it, a copy or search of an ancestor of a store (~/.config, the Codex
    # home that holds shell_snapshots) or of a directory that holds an older store file (~/.claude, whose
    # .credentials.json the mention rule covers only by name), and an OmniRoute DATA_DIR elsewhere.
    "cd ~/.aws && cat credentials",
    "kubectl config view --raw",
    "gpg --export-secret-keys --armor",
    "sqlite3 ~/.omniroute/gateway.sqlite .dump",
    "tar czf /tmp/k.tgz ~/.ssh",
    "cat ~/.n*rc",
    "cp -r ~/.config /tmp/c",
    "cp -r ~/.codex /tmp/c",
    "grep -r token ~/.claude",
    "cat /srv/omniroute-data/storage.sqlite",
    # OpenHands session keys (2026-09-28): the agent-server holds its key in its container environment, and the guard
    # does not model docker subcommands, so printenv or a shell in the container and a full inspect, whose
    # Config.Env holds the key, pass (the container name is illustrative). The variable name is not a listed secret
    # name, so a shell in the container expanding it passes too. A search of the state directory that holds
    # secrets/, and a relative read after `cd`, pass as for the home stores.
    "docker exec rw-1-engines-on-server printenv",
    "docker exec rw-1-engines-on-server printenv OH_SESSION_API_KEYS_0",
    "docker exec rw-1-engines-on-server sh -c 'echo \"$OH_SESSION_API_KEYS_0\"'",
    "docker inspect rw-1-engines-on-server",
    "grep -r X-Session-API-Key ~/.local/state/native-agent-stack/runtime-workers/openhands",
    "cd ~/.local/state/native-agent-stack/runtime-workers/openhands && cat secrets/rw-1-engines-on.headers",
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

    def test_every_rule_applies_behind_rtk_proxy(self):
        # rtk 0.50.0's `proxy` runs the command after it unfiltered, and agents are told to re-run a command
        # that way (`rtk proxy <command>`), so every blocked command stays blocked, for the same reason, behind
        # it and behind rtk's own flags. Found by the 2026-09-27 cross-family review: `rtk proxy cat F` passed.
        for command, reason in BLOCKED.items():
            for prefix in ("rtk proxy ", "rtk -v proxy --skip-env "):
                with self.subTest(command=command, prefix=prefix):
                    self.assertEqual(guard.check(prefix + command), reason)

    def test_every_template_read_deny_has_a_blocked_bash_reader(self):
        # The settings template registers `rtk hook claude`. rtk 0.50.0 rewrites `cat`, `head` and `tail -n` of a file
        # to `rtk read` (src/discover/rules.rs), Claude Code evaluates its permission rules against the command a hook
        # returns (hooks, PreToolUse `updatedInput`), and RTK leaves a command alone only when a Bash(...) deny rule
        # matches it (src/hooks/permissions.rs, append_bash_rules), so on such a host the Read denies do not stop
        # those readers. The guard reads the command as written, so for every anchored Read deny of the template and
        # the project settings (the `**/` twins and `!` carve-outs aside) a concrete path under it must be blocked
        # for each reader and for the rewritten form. Found by the 2026-09-27 independent verification; a probe
        # project holding the template's deny rules showed `rtk hook check 'cat ~/.ssh/config'` -> `rtk read`.
        rules = set()
        for settings in ("adoption/templates/claude.settings.template.json", ".claude/settings.json"):
            deny = json.loads((ROOT / settings).read_text(encoding="utf-8"))["permissions"]["deny"]
            rules.update(match.group(1) for rule in deny
                         if (match := re.fullmatch(r"Read\(((?:~/|//|\.env).*)\)", rule)))
        self.assertGreaterEqual(len(rules), 26)
        for pattern in sorted(rules):
            path = re.sub(r"^//", "/", pattern).replace("**", "sample.txt").replace("*", "sample")
            for command in (f"cat {path}", f"head -n 5 {path}", f"tail -n 3 {path}", f"rtk read {path}"):
                with self.subTest(rule=pattern, command=command):
                    self.assertIsNotNone(guard.check(command))

    def test_template_denies_the_openhands_session_key_directory(self):
        # The template reaches every session on a host, so it denies Claude's file tools the directory that holds
        # each OpenHands runtime-worker attempt's session key (2026-09-28), with its Context Mode twin right after it;
        # test_every_template_read_deny_has_a_blocked_bash_reader then expects the guard to block its readers.
        deny = json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))[
            "permissions"]["deny"]
        rule = f"Read({OH_SECRETS}/**)"
        self.assertEqual(rule, "Read(~/.local/state/native-agent-stack/runtime-workers/openhands/secrets/**)")
        self.assertIn(rule, deny)
        self.assertEqual(deny[deny.index(rule) + 1], "Read(**/" + rule[len("Read(~/"):])

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
                     "Bash(git credential fill*)", "Bash(gh auth git-credential *)",
                     # Context Mode twins (docs/secret-storage.md, "User-level guards"): 1.0.169 compiles a
                     # Read glob literally, without expanding `~/` or `//`, and matches it against absolute
                     # paths, while Claude Code bounds `**/` to the current directory.
                     "Read(**/.config/native-agent-stack/**)", "Read(**/.config/ecosystem-observability/*.env)",
                     "Read(**/.config/nativestack/*.key)", "Read(**/.claude/.credentials.json)",
                     "Read(**/.codex/auth.json)", "Read(**/.config/gh/hosts.yml)",
                     "Read(**/.cache/huggingface/token)", "Read(**/.cache/huggingface/stored_tokens)",
                     "Read(**/proc/*/environ)", "Read(**/.env)", "Read(**/.env.*)",
                     # Home credential stores (2026-09-27, synthesis H6 and PR-A): SSH, GnuPG, cloud, kube,
                     # Docker, git-credential, netrc, npm and PyPI files, the OmniRoute data directories
                     # and Codex's shell snapshots, each with its twin.
                     "Read(~/.ssh/**)", "Read(**/.ssh/**)", "Read(~/.gnupg/**)", "Read(~/.aws/**)",
                     "Read(~/.azure/**)", "Read(~/.kube/**)", "Read(~/.docker/config.json)",
                     "Read(~/.git-credentials)", "Read(~/.netrc)", "Read(~/.npmrc)", "Read(~/.pypirc)",
                     "Read(~/.omniroute/**)", "Read(~/.config/omniroute/**)",
                     "Read(~/.codex/shell_snapshots/**)", "Read(**/.codex/shell_snapshots/**)"):
            self.assertIn(rule, deny)
        # A `!` carve-out reaches only the rules listed before it in the same file, so every `.env` rule,
        # twins included, precedes both carve-outs (a twin appended after them would re-deny .env.example).
        for rule in ("Read(.env)", "Read(.env.*)", "Read(**/.env)", "Read(**/.env.*)"):
            for carve_out in ("Read(!.env.example)", "Read(!.env.*.example)"):
                self.assertLess(deny.index(rule), deny.index(carve_out), (rule, carve_out))
        hooks = settings["hooks"]["PreToolUse"]
        self.assertEqual(hooks[0]["matcher"], "Bash")
        self.assertIn("scripts/hooks/secret_path_guard.py", hooks[0]["hooks"][0]["command"])
        self.assertNotIn("/home/", json.dumps(settings))

    def test_every_anchored_read_deny_has_a_context_mode_twin(self):
        # Each `Read(~/X)` or `Read(//X)` deny needs `Read(**/X)` beside it: Claude Code honours the anchored
        # form, Context Mode's server-side path check only the `**/` form (docs/secret-storage.md). The
        # hand-merge block for hosts without the template carries the same twins.
        deny = json.loads((ROOT / ".claude/settings.json").read_text())["permissions"]["deny"]
        anchored = [rule for rule in deny if re.fullmatch(r"Read\((?:~/|//)[^)]+\)", rule)]
        self.assertGreaterEqual(len(anchored), 9)
        block = (ROOT / "docs/secret-storage.md").read_text(encoding="utf-8").split(
            "## User-level guards (deployed by the Claude profile)", 1)[1].split("```json", 1)[1].split("```", 1)[0]
        for rule in anchored:
            twin = "Read(**/" + re.sub(r"^Read\((?:~/|//)", "", rule)
            with self.subTest(rule=rule):
                self.assertIn(twin, deny)
                self.assertEqual(deny.index(twin), deny.index(rule) + 1, "the twin sits right after its original")
                self.assertIn(f'"{rule}"', block)
                self.assertIn(f'"{twin}"', block)


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
