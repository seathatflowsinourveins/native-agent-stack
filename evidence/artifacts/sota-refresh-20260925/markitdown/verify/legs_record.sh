#!/usr/bin/env bash
# Non-fail-fast recorder of the corrected-check legs for one arm (read-only on the arm's env).
# Usage: legs_record.sh ARM M PIP_PY RUN_DIR REPO CHECKER
set -u
ARM=$1 M=$2 PIP_PY=$3 RUN_DIR=$4 REPO=$5 CHECKER=$6
export PYTHONDONTWRITEBYTECODE=1 UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="${UV_CACHE_DIR:?}"
test ! -e "$RUN_DIR" || { echo "RUN_DIR exists"; exit 2; }
mkdir -p "$RUN_DIR"
K="$REPO/blueprints/us-equities/catalyst-provenance/upstream-8k.html"
echo "ARM $ARM at $(date -u +%FT%TZ)"
v=$("$M" --version); echo "L1 rc=$? version='$v'"
"$M" "$REPO/fixtures/greeting.html" -o "$RUN_DIR/greeting.md"; echo "L2 rc=$? greeting.md sha256=$(sha256sum < "$RUN_DIR/greeting.md" | cut -d' ' -f1) bytes=$(stat -c %s "$RUN_DIR/greeting.md")"
"$M" "$K" -o "$RUN_DIR/8k.md"; echo "L3 rc=$? 8k.md sha256=$(sha256sum < "$RUN_DIR/8k.md" | cut -d' ' -f1) bytes=$(stat -c %s "$RUN_DIR/8k.md")"
"$M" "$K" > "$RUN_DIR/8k.stdout.md"; echo "L4 rc=$? 8k stdout sha256=$(sha256sum < "$RUN_DIR/8k.stdout.md" | cut -d' ' -f1) bytes=$(stat -c %s "$RUN_DIR/8k.stdout.md")"
printf '%s\n' '<!doctype html><html><body>' '<p>First<u>word</u>Last</p>' '<p><a href="https://example.com/items/a%2Fb">example</a></p>' '<p><strike>gone</strike></p>' '<p><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBTAA7" data-src="https://example.com/photo.jpg" alt="A photo"></p>' '</body></html>' > "$RUN_DIR/disc.html"
echo "L5 disc.html sha256=$(sha256sum < "$RUN_DIR/disc.html" | cut -d' ' -f1) bytes=$(stat -c %s "$RUN_DIR/disc.html")"
"$M" "$RUN_DIR/disc.html" -o "$RUN_DIR/disc.md"; echo "L6 rc=$? disc.md sha256=$(sha256sum < "$RUN_DIR/disc.md" | cut -d' ' -f1)"; printf 'L6 content=%q\n' "$(cat "$RUN_DIR/disc.md")"
"$M" "$REPO/blueprints/convergence-practice/document-ingestion/corpus/lumen-qualification.pdf" -o "$RUN_DIR/pdf.md" 2>"$RUN_DIR/pdf.err"; prc=$?
grep -q 'markitdown\[pdf\]' "$RUN_DIR/pdf.err"; grc=$?
echo "L7 pdf rc=$prc grep_markitdown_pdf_rc=$grc pdf.md_exists=$(test -e "$RUN_DIR/pdf.md" && echo yes || echo no) exception_line='$(grep -m1 -o 'MissingDependencyException[^.]*' "$RUN_DIR/pdf.err" | head -c 160)'"
python3 "$CHECKER" "$RUN_DIR" > "$RUN_DIR/checker.out"; crc=$?
echo "L8 checker rc=$crc PASS=$(grep -c '^PASS ' "$RUN_DIR/checker.out") FAIL=$(grep -c '^FAIL ' "$RUN_DIR/checker.out") failed=[$(grep '^FAIL ' "$RUN_DIR/checker.out" | cut -d' ' -f2 | paste -sd, -)]"
uv pip list --python "$PIP_PY" > "$RUN_DIR/pip-list.txt"; urc=$?
grep -qiE '^(pdfminer-six|pdfplumber|mammoth|lxml|openpyxl|python-pptx|pandas|olefile|xlrd) ' "$RUN_DIR/pip-list.txt"; xrc=$?
echo "L9 uv pip list rc=$urc packages=$(($(wc -l < "$RUN_DIR/pip-list.txt") - 2)) extras_grep_rc=$xrc (1 = no extras) sha256=$(sha256sum < "$RUN_DIR/pip-list.txt" | cut -d' ' -f1)"
D=$HOME/.local/state/nativestack/final-acceptance/document.html
dh=$("$M" "$D" | sha256sum | cut -d' ' -f1); drc=${PIPESTATUS[0]}
db=$("$M" "$D" | wc -c)
h=no; s=no
"$M" "$D" | grep -qF '# NativeStack evidence' && h=yes
"$M" "$D" | grep -qF 'Scoped memory' && s=yes
echo "L10 rc=$drc has_heading=$h has_scoped_memory=$s stdout_sha256=$dh bytes=$db input_sha256=$(sha256sum < "$D" | cut -d' ' -f1)"
echo "END $ARM at $(date -u +%FT%TZ)"
