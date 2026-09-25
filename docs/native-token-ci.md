# Native token-tool fixtures in GitHub Actions

The [Linux workflow](../.github/workflows/native-token-e2e.yml) installs and invokes four upstream tools against disposable public inputs. This adds fresh CLI behavior checks to the existing repository-integrity and token-report tests. It does not start Codex/Claude, read account stores, call a provider, download a model or require a GPU. It runs for relevant pull requests/pushes and manual dispatch; publication of the workflow does not itself prove a hosted run passed.

| Pin | Upstream installation | Actual acceptance |
| --- | --- | --- |
| RTK 0.50.0 | Official `rtk-x86_64-unknown-linux-musl.tar.gz` and `checksums.txt`; check the exact asset hash, inspect members, then native `tar -xf` | Two fixture commit subjects survive filtered output; `rtk proxy git log -2` equals original stdout; missing Git reference remains a failure; fixture-local `gain --format json` retained |
| QMD 2.8.3 | `npm install --global --prefix "$PREFIX" @tobilu/qmd@2.8.3` | Named BM25 collection, search/get with exact source body inside the pinned output framing, update and retrieval from fresh CLI processes, then owned collection removal |
| Repomix 1.18.0 | `npm install --global --prefix "$PREFIX" repomix@1.18.0` | Explicit two-file XML contains the complete original source and no extra file; separate compressed pack retains structure, without claiming complete implementation fidelity |
| TOON 4.1.1 | `npm install --global --prefix "$PREFIX" @toon-format/cli@4.1.1` | Encode/statistics, strict decode with equal JSON values/types, and a rejected truncated array |

The [harness](../scripts/native_token_ci.py) checks these versions against [the manifest](../manifests/stack.json). Pins and installer methods come from [native recipes](../recipes/README.md). Node 24 is supplied by SHA-pinned `actions/setup-node`; checkout and upload Actions are also SHA-pinned, checkout retains no credentials, and workflow permissions are `contents: read`. Package-manager caches are disabled across jobs. npm dependency ranges can resolve differently in later fresh installs; the receipt retains installed top-level metadata and does not claim a transitive lock.

The QMD BM25 lane sets the dependency's supported `NODE_LLAMA_CPP_SKIP_DOWNLOAD=true` during installation to skip node-llama-cpp's native build/download hook. Other necessary npm dependency scripts remain enabled. The runtime only uses lexical/document commands, never `query`, `embed`, `pull` or vector search. `QMD_FORCE_CPU=1` alone would not prevent model-enabled operations.

RTK uses `RTK_DB_PATH`, fresh XDG configuration and `RTK_TELEMETRY_DISABLED=1`. QMD has a named index plus explicit `INDEX_PATH`, `QMD_CONFIG_DIR` and `XDG_CACHE_HOME`. Repomix uses an explicit empty configuration and selected files. Child environments exclude inherited provider credentials, routing and tool-state overrides; native `HOME` is preserved. npm receives empty owned user/global config files, and `curl --disable` skips the default curl configuration. No hooks or global client defaults are installed.

## Run a bounded check locally

From the checkout, with matching installed tools on PATH and a **new** result path outside Git:

```sh
python3 -m unittest tests.test_native_token_ci -v
python3 scripts/native_token_ci.py --output /absolute/private/new-native-ci-results
```

This reuses the four native executables and creates fresh fixture state. To exercise the clean upstream installation path too, add `--install`; downloads and npm installations use temporary owned prefixes. Each output directory is exclusive and is never silently replaced.

The script captures every started command's sanitized argv, stdout, stderr, exit, elapsed time and pre-sanitization byte hashes in `receipt.json`. It retains selected public artifacts, fixture/harness source hashes and the scoped environment settings. Expected nonzero Git/TOON results remain present and distinct from unexpected failures. A timeout terminates only that command's owned process group and preserves the failure. Temporary tools, fixture Git repository, QMD/RTK databases and caches are removed in the final cleanup path; retained evidence survives. Interrupted/incomplete execution cannot produce a passing receipt. Cancellation or runner loss may prevent cleanup/report completion, which is not a passing lifecycle result.

GitHub uploads only the sanitized result directory for 14 days, including a failed run's available receipt. It never uploads installation prefixes, home directories or authentication stores. Local paths are replaced with scope markers; raw hashes identify pre-sanitization output bytes. Full terminal streams are retained within this fixture scope, not native user conversations.

RTK's returned counters are local estimates. QMD has no savings counter; Repomix/TOON token reports describe representations. Neither this job nor a smaller fixture output proves reduced provider billing. Follow [the session handbook](token-session-handbook.md) for native adoption and [the lifecycle guide](../adoption/lifecycle.md) for stateful service/new-PC acceptance.

Primary sources: [RTK v0.50.0](https://github.com/rtk-ai/rtk/tree/v0.50.0), [QMD v2.8.3](https://github.com/tobi/qmd/tree/v2.8.3), [node-llama-cpp install controls](https://node-llama-cpp.withcat.ai/guide/building-from-source), [Repomix v1.18.0](https://github.com/yamadashy/repomix/tree/v1.18.0), [TOON v4.1.1](https://github.com/toon-format/toon/tree/v4.1.1).
