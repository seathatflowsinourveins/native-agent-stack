# Native WSL document ingestion

A fresh Ubuntu 24.04 x86-64 WSL prefix built Poppler **26.09.0** and executed the
unchanged [frozen ingestion protocol](../document-ingestion/README.md) from
`76f839249f78482ead10ad700a268009d091aad5`. All three pages, two tables with 24 data
cells, eight positive queries and four absent-answer queries passed. Both original
XHTML files, the parsed extraction and the retrieval answers are byte-identical to
the retained Mac output. These are new native WSL results, recorded in
[receipt.json](receipt.json), rather than replay of the Mac receipt.

The source PDFs, authored answers, table geometry and ingestion code remain
unchanged. [freeze.json](freeze.json) identifies those inputs and the private
pre-execution manifest: 972 selected source, fixture, header, archive and build-tool
files, plus 12 runtime libraries. Every recorded hash still matched after the run.
The designed corpus remains a narrow born-digital Latin-text fixture, not a
held-out general PDF or retrieval benchmark.

## Source and dependency boundary

[Poppler's official release page](https://poppler.freedesktop.org/) still selected
26.09.0, released September 3, 2026. The source archive matches the prior pin's
SHA-256 and its detached signature verifies against the publisher fingerprint on
that page. The first public-key service response lacked a usable identity;
its failed verification is retained, and successful verification preceded native
configuration and execution. Source COPYING and per-file GPL notices remain with
the private build. No binaries are redistributed here.

[sources.json](sources.json) contains exact URLs, hashes, licenses, native library
versions and the executed configuration. Kitware's Linux CMake 4.4.3 archive
matches its publisher checksum. The existing GCC 13.3, GNU Make 4.3, pkgconf 1.8.1,
Python 3.13.15, FreeType 2.13.2 and zlib satisfy the selected native build. Poppler's
source requires CMake 3.28+, C++23 and FreeType 2.13+; its official CI includes
Ubuntu 24.04/GCC. This run additionally establishes the selected workload's actual
compatibility on WSL.

Five exact Ubuntu development payloads supply FreeType, Brotli, bzip2, PNG and
zlib headers. Their signed Ubuntu InRelease → Packages → archive hashes were
verified before `dpkg-deb -x` extracted them into `tools/sysroot`. No package
installation, maintainer scripts or system database changes occurred. Existing
runtime files matched native package checksum records, and their SHA-256 values
and copyright notices were retained. Source/runtime licenses apply to any later
binary packaging.

## Repeat in a new owned prefix

Use an explicit new `QUAL_DIR` outside canonical projects. Fetch only the pinned
public fixture at the revision above, preserving its directory beneath
`$QUAL_DIR/reference`. Place the verified source and CMake archives under
`$QUAL_DIR/tools` and extract the verified development payloads into
`$QUAL_DIR/tools/sysroot`. Retain the archive, signature, package authentication
and copyright evidence. Read-only system libraries must match the hashes in
`sources.json`; another dependency set needs its own qualification.

Set `RECIPE` to this published directory. With the exact sources and dependencies
prepared, the recorded configure arguments can be applied without editing pins:

```sh
python3.13 - "$RECIPE/sources.json" "$QUAL_DIR" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

pins = json.loads(Path(sys.argv[1]).read_text())
root = str(Path(sys.argv[2]).resolve())
command = [arg.replace('<QUAL_DIR>', root) for arg in pins['configure_argv']]
subprocess.run(['taskset', '-c', '0-3', *command], check=True)
PY

CMAKE="$QUAL_DIR/tools/cmake-4.4.3-linux-x86_64/bin/cmake"
taskset -c 0-3 "$CMAKE" --build "$QUAL_DIR/build" \
  --target pdftotext pdfinfo --parallel 4
mkdir -p "$QUAL_DIR/prefix/bin"
cp "$QUAL_DIR/build/utils/pdftotext" "$QUAL_DIR/prefix/bin/"
cp "$QUAL_DIR/build/utils/pdfinfo" "$QUAL_DIR/prefix/bin/"
```

Retain the source and dependency notices beside these private binaries. Use at
most four permitted CPU IDs if the host's affinity differs. The static Poppler
core links to the explicitly recorded native shared-library closure. It disables
network support, image codecs, cryptographic backends, font subsetting, language
wrappers and optional tests; upstream decoder/performance warnings are retained.
PNG remains a dependency of the reused FreeType library even though Poppler's
own PNG output is disabled. No global PATH or loader setting is changed.

Execute the original runner, which performs both real native extractions and the
invalid-PDF refusal itself:

```sh
FIXTURE="$QUAL_DIR/reference/blueprints/convergence-practice/document-ingestion"
mkdir -p "$QUAL_DIR/tmp"
TMPDIR="$QUAL_DIR/tmp" PYTHONDONTWRITEBYTECODE=1 python3.13 "$FIXTURE/ingest.py" \
  --pdftotext "$QUAL_DIR/prefix/bin/pdftotext" \
  --output "$QUAL_DIR/attempt-1" --attempt 1
```

The output directory must be new. The eight positive queries retain correct
source hashes, page numbers and coordinate bounds; the four absence queries
return no evidence within their requested scope. Results are limited to three
records and 240 characters per excerpt. A separately modified copy of one input
was rejected before any native subprocess or output directory was created. The
original fixture remained untouched.

## Retention and limits

All owned processes and scratch directories were gone at completion. Native
source/build logs, authentication failures, exact archives, dependencies,
negative controls and extraction outputs remain in the private task prefix. No
listener, service, account, system package, model, GPU workload or document scan
was introduced. Keep needed evidence, then remove only that new prefix to roll
back; no shared host rollback is required.

The next unresolved gate remains a separately frozen, permitted corpus of real
multi-column reports, difficult tables and scanned pages. This acceptance does
not cover OCR, inferred layout, non-Latin CMaps, arbitrary semantic questions,
images, signatures or the broad upstream test corpus. No renderer was qualified
in this wave; the source PDFs are the same previously inspected bytes. Model and
embedding calls in the deterministic runner are zero; whole-task model usage is
unknown, and no token-saving claim is made.
