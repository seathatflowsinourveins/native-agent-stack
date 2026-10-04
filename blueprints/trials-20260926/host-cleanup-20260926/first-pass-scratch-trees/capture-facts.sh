#!/bin/sh
# Capture, before the first trial pass's scratch trees are deleted, the facts that retained
# evidence of the 2026-09-26 P1 trial batch still needs from them. Read-only: runs only
# `--version` of the pgserver-bundled PostgreSQL binaries, reads files, and stats paths.
#
# Usage: SCRATCH=<session scratch dir> sh capture-facts.sh <out-dir>
# Writes: pgserver-bundled-versions.txt, mirix-0.1.7-wheel-contents.txt, host-state-attribution.txt,
#         trees-before.txt
set -u
out=${1:?out dir}
SCRATCH=${SCRATCH:?set SCRATCH to the session scratch directory}
mkdir -p "$out"
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
MIRIX="$SCRATCH/trial-mirix"
SITE="$MIRIX/venv/lib/python3.11/site-packages"
PG="$SITE/pgserver/pginstall"
COLPALI_SITE="$SCRATCH/trial-colpali/.venv/lib/python3.11/site-packages"

{
  echo "# pgserver-bundled PostgreSQL and pgvector used by the MIRIX trial ($(stamp))"
  echo "# The MIRIX v0.1.6 venv's pgserver package; the trial's PostgreSQL cluster ran from these binaries."
  echo "\$ ls <venv site-packages> | grep -E '^(pgserver|pgvector)-'"
  ls "$SITE" | grep -E '^(pgserver|pgvector)-'
  echo "\$ <venv site-packages>/pgserver/pginstall/bin/postgres --version"
  "$PG/bin/postgres" --version
  echo "\$ <venv site-packages>/pgserver/pginstall/bin/pg_config --version"
  "$PG/bin/pg_config" --version
  echo "\$ grep default_version <venv site-packages>/pgserver/pginstall/share/postgresql/extension/vector.control"
  grep default_version "$PG/share/postgresql/extension/vector.control"
  echo "\$ cat <scratch>/trial-mirix/pgdata/PG_VERSION"
  cat "$MIRIX/pgdata/PG_VERSION"
  echo "# Note: pgvector-0.5.0 above is the Python client binding (the 'pgvector' PyPI package);"
  echo "# the server-side extension version is the vector.control default_version."
} > "$out/pgserver-bundled-versions.txt" 2>&1

{
  echo "# PyPI mirix 0.1.7 wheel contents ($(stamp))"
  echo "# The wheel the first pass downloaded from PyPI on 2026-09-26 01:24Z into <scratch>/trial-mirix."
  echo "\$ sha256sum mirix-0.1.7-py3-none-any.whl"
  (cd "$MIRIX" && sha256sum mirix-0.1.7-py3-none-any.whl)
  python3 - "$MIRIX/mirix-0.1.7-py3-none-any.whl" <<'PY'
import sys, zipfile
wheel = zipfile.ZipFile(sys.argv[1])
metadata = wheel.read("mirix-0.1.7.dist-info/METADATA").decode("utf-8")
print("$ METADATA fields (Name, Version, Summary, Requires-Dist)")
for line in metadata.splitlines():
    if line.startswith(("Name:", "Version:", "Summary:", "Requires-Dist:")):
        print(line)
names = wheel.namelist()
print(f"$ file listing ({len(names)} entries; size in bytes)")
for info in wheel.infolist():
    print(info.file_size, info.filename)
top = sorted({name.split("/")[1] for name in names if name.startswith("mirix/") and "/" in name[6:]})
print("$ subpackages under mirix/:", ", ".join(top))
print("server or agent modules present:", any(name.startswith(("mirix/server/", "mirix/agent/", "mirix/services/", "mirix/orm/")) for name in names))
PY
} > "$out/mirix-0.1.7-wheel-contents.txt" 2>&1

{
  echo "# Attribution facts for trial-owned host state outside the scratch directory ($(stamp))"
  echo "## ~/.cache/mteb"
  echo "\$ stat -c '%w (birth) %y (mtime)' ~/.cache/mteb"
  stat -c '%w (birth) %y (mtime)' "$HOME/.cache/mteb"
  echo "\$ ls <scratch>/trial-colpali/.venv/lib/python3.11/site-packages | grep '^mteb-'"
  ls "$COLPALI_SITE" | grep '^mteb-'
  echo "\$ stat -c '%w (birth) %n' of the mteb bytecode written when that venv first imported mteb"
  for file in mteb/__pycache__/__init__.cpython-311.pyc mteb/__pycache__/evaluate.cpython-311.pyc mteb/cache/__pycache__/result_cache.cpython-311.pyc; do
    stat -c "%w (birth) $file" "$COLPALI_SITE/$file"
  done
  echo "\$ grep -n of the import-time cache creation in that installed mteb 2.21.8 (file sha256 first)"
  for file in mteb/evaluate.py mteb/cache/result_cache.py; do
    printf '%s  %s\n' "$(sha256sum < "$COLPALI_SITE/$file" | cut -d' ' -f1)" "$file"
  done
  grep -n '^_DEFAULT_CACHE = ResultCache()' "$COLPALI_SITE/mteb/evaluate.py"
  grep -n 'self.cache_path.mkdir(parents=True, exist_ok=True)\|default_cache_directory = Path.home() / ".cache" / "mteb"' "$COLPALI_SITE/mteb/cache/result_cache.py"
  echo "## /run/user/<uid>/python_PostgresServer"
  echo "\$ stat -c '%w (birth) %y (mtime) %F %n' of the runtime directory, its lock file and its entries"
  for path in "/run/user/$(id -u)/python_PostgresServer" "/run/user/$(id -u)/python_PostgresServer/.lockfile" "/run/user/$(id -u)/python_PostgresServer"/*; do
    stat -c '%w (birth) %y (mtime) %F %n' "$path" | sed "s#/run/user/$(id -u)/#/run/user/<uid>/#"
  done
  echo "\$ grep -n of pgserver 0.1.4's runtime and socket paths (file sha256 first)"
  for file in pgserver/postgres_server.py pgserver/utils.py; do
    printf '%s  %s\n' "$(sha256sum < "$SITE/$file" | cut -d' ' -f1)" "$file"
  done
  grep -n "user_runtime_path('python_PostgresServer')" "$SITE/pgserver/postgres_server.py"
  grep -n "string_identifier = \|path_hash = \|runtime_path / path_hash" "$SITE/pgserver/utils.py"
  echo "\$ sha256('<scratch>/trial-mirix/pgdata-' + str(st_ino))[:10], pgserver's socket-directory name for the trial cluster"
  python3 -c 'import hashlib, os, sys; p = sys.argv[1]; print(hashlib.sha256(f"{p}-{os.stat(p).st_ino}".encode()).hexdigest()[:10])' "$MIRIX/pgdata"
} > "$out/host-state-attribution.txt" 2>&1

{
  echo "# First-pass scratch trees before deletion ($(stamp)): apparent bytes (du -sb) and allocated size (du -sh)"
  for name in trial-colpali trial-mirix trial-byterover exec; do
    printf '%s\t%s\t%s\n' "$(du -sb "$SCRATCH/$name" | cut -f1)" "$(du -sh "$SCRATCH/$name" | cut -f1)" "<scratch>/$name"
  done
  echo "# Top-level entries of each (names, types, apparent bytes)"
  for name in trial-colpali trial-mirix trial-byterover exec; do
    for entry in "$SCRATCH/$name"/* "$SCRATCH/$name"/.[!.]*; do
      [ -e "$entry" ] || continue
      printf '%s\t%s\t%s\n' "$(stat -c %F "$entry")" "$(du -sb "$entry" | cut -f1)" "<scratch>/$name/$(basename "$entry")"
    done
  done
} > "$out/trees-before.txt" 2>&1
echo "captured into $out"
