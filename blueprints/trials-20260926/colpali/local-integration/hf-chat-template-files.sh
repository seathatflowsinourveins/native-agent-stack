#!/bin/sh
# Hugging Face Hub API observation behind the ColQwen processor-load diagnosis: which revisions of
# vidore/colqwen2-v1.0 and vidore/colqwen2.5-v0.2 carry additional_chat_templates/*.jinja, and the
# commits that added them. Unauthenticated public API reads only.
# Usage: sh hf-chat-template-files.sh > hf-chat-template-files.txt
set -u
api=https://huggingface.co/api/models
echo "# Hub API observation, $(date -u +%Y-%m-%dT%H:%M:%SZ) (unauthenticated)"
for repo in vidore/colqwen2-v1.0 vidore/colqwen2.5-v0.2; do
  echo "## $repo: latest commits on main (id, date, title)"
  echo "\$ curl -sS $api/$repo/commits/main"
  curl -sS -m 60 "$api/$repo/commits/main" | python3 -c '
import json, sys
for commit in json.load(sys.stdin)[:6]:
    print(commit["id"], commit["date"], commit["title"])'
  case "$repo" in
    vidore/colqwen2-v1.0) revisions="main 2b6ac8fb37f46a49e4841e599583d00ae8a20117 730ed5b80e31fa73731d8e74449fb0e6536ac4fb 83a0134c8f274b3688d8dbde26de8a5b109ad8b4 530094e83a40ca4edcb5c9e5ddfa61a4b5ea0d2f" ;;
    *) revisions="main dcbe8d9cede518bce830488364ba0e40c873645b 11fee7270dcb48f07f3e54cef600619125da60fe 6f6fcdfd1a114dfe365f529701b33d66b9349014" ;;
  esac
  for revision in $revisions; do
    echo "\$ curl -sS $api/$repo/tree/$revision/additional_chat_templates"
    curl -sS -m 60 "$api/$repo/tree/$revision/additional_chat_templates"
    echo
  done
done
