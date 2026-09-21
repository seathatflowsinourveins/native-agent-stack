# Native patch upgrades qualified September 21

Use the matching upstream installation on a new host, preserve the previous
prefix on an existing host, run the useful capability, then promote only its
owned launcher. These four releases were qualified on the source Linux/WSL host;
new hosts still need their own acceptance. The native Claude/Codex account,
model, hook and service settings were not changed by these upgrades.

| Component | Accepted pin / official source | Native acceptance |
| --- | --- | --- |
| ccusage | [20.0.24](https://github.com/ccusage/ccusage/releases/tag/v20.0.24), ecb676cce27cb5dd0090c7804a5cecc35e8ba805 | Offline Claude/Codex reports; 34 unchanged upstream Node tests |
| Repomix | [1.18.1](https://github.com/yamadashy/repomix/releases/tag/v1.18.1), 80b4280a9196feace092fc672dfe2b5fac62ef08 | Selected source pack and 148 unchanged tests across five files |
| OpenResearch | [0.2.7](https://github.com/alphaXiv/OpenResearch/releases/tag/v0.2.7), 24e404ecbe19cb9184ea8177e8e9f90d4f3205b0 | Three-paper discovery, complete selected paper retrieval, seven unchanged Markdown tests |
| Worktrunk | [0.79.0](https://github.com/max-sixty/worktrunk/releases/tag/v0.79.0), 5ba6f148e8505c20794f2d8bc706aa4f26335c95 | Disposable worktree create/list/remove and source-backed child-directory comparison |

## Installation

Choose an explicit user-owned `NATIVE_TOOLS` prefix. Preserve lockfiles and
verify native npm's resolved integrity against the selected official registry
metadata; the recorded source tests do not constitute reproducible binary attestation.

```sh
NATIVE_TOOLS="$HOME/.local/share/native-agent-stack/tools"
npm install --prefix "$NATIVE_TOOLS/ccusage-20.0.24" --save-exact --no-audit --no-fund ccusage@20.0.24
npm install --prefix "$NATIVE_TOOLS/repomix-1.18.1" --save-exact --no-audit --no-fund repomix@1.18.1
CCUSAGE_BIN="$NATIVE_TOOLS/ccusage-20.0.24/node_modules/.bin/ccusage"
REPOMIX_BIN="$NATIVE_TOOLS/repomix-1.18.1/node_modules/.bin/repomix"
"$CCUSAGE_BIN" --version
"$REPOMIX_BIN" --version
```

For OpenResearch and Worktrunk use the official Linux musl release archive and
its checksum asset. Inspect `gh release view TAG --repo REPOSITORY --json assets`
to select the actual asset names, download both with `gh release download`, and
run `sha256sum -c` before extracting into separate versioned prefixes. The
accepted archives are `openresearch-cli-x86_64-unknown-linux-musl.tar.xz` and
`worktrunk-x86_64-unknown-linux-musl.tar.xz`; their complete checksums and exact
native invocations are retained in the [public upgrade receipt](../evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json).
Other architectures require matching upstream assets and new acceptance.
Set `ORX_BIN` and `WT_BIN` to the absolute executable paths inside the inspected,
extracted candidate archives. Use these explicit candidate paths during acceptance;
an existing bare command on PATH may still resolve an older installation. After
acceptance, update only an owned launcher and preserve its previous target.

## Useful native commands

```sh
"$CCUSAGE_BIN" daily --offline --no-cost --json
"$CCUSAGE_BIN" codex daily --offline --no-cost --json
"$REPOMIX_BIN" --include 'SELECTED_SOURCE,SELECTED_TEST' --style xml --output "$EVIDENCE_DIR/selected-pack.xml"
"$ORX_BIN" --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3
"$ORX_BIN" --no-telemetry paper 2609.05760 --full
"$WT_BIN" --config "$FIXTURE_CONFIG" -C "$OWNED_FIXTURE" switch --create codex/qualification --base main --no-cd --no-hooks --format json
"$WT_BIN" --config "$FIXTURE_CONFIG" -C "$OWNED_FIXTURE" list --format json
"$WT_BIN" --config "$FIXTURE_CONFIG" -C "$OWNED_FIXTURE" remove codex/qualification --foreground --no-hooks --format json
```

The Worktrunk commands require an explicitly owned disposable Git repository and
isolated configuration. Their cleanup authorization does not cover user branches.
The tested 0.78.0 `--no-cd -x pwd` ran in the invoking repository; 0.79.0 correctly
ran in the selected worktree, matching the upstream test's directory oracle.
This is a native behavioral comparison, not an executed Rust test or token saving.

Repomix trims a final newline from each selected source block. Strict byte
equality failed and remains recorded; restoring that final LF recovered the two
selected source files exactly. Compressed packs can omit implementation details;
inspect originals before edits or correctness decisions. Ccusage reports local
consumption; its totals do not measure avoided tokens or subscription bills.

## Tests, persistence and rollback

[Ccusage/Repomix evidence](../evidence/artifacts/full-stack-convergence-20260921/ccusage-repomix-upgrades.json)
retains source commits, commands, results, exact package integrity and limitations.
Ccusage's selected tests ran with `TZ=UTC node --test`; Repomix's selected five
files ran through its unchanged `npm test -- --run` command, including real Git
security fixtures and positive controls. OpenResearch's seven unchanged
`ui/tests/markdownTarget.test.mjs` tests passed with native Node. Cargo and rustc
were unavailable, so relevant Rust suites remain unrun; no toolchain/OS upgrade
was silently substituted for that limitation.

The installed native launchers resolve the new prefixes on subsequent calls.
Existing memory, native caches, history and services are retained. Rollback
restores the previous wrapper/symlink to preserved ccusage 20.0.23, Repomix 1.18.0,
OpenResearch 0.2.4 or Worktrunk 0.78.0. Do not delete the previous prefix until
matching local acceptance and normal work justify cleanup. No recurring job or
new remote hosting was installed.
