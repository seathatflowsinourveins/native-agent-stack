# Claude Quickstart regression oracle

`utils.py` transcribes the two-function fixture in the official [Claude Agent SDK Quickstart](https://code.claude.com/docs/en/agent-sdk/quickstart), “Create a buggy file,” read on 2026-10-02. Its two documented crashing inputs are an empty number list and a null user. This deliberately broken source remains the baseline.

`test_utils.py` is a local integration oracle using Python's native [unittest](https://docs.python.org/3.13/library/unittest.html). The two edge cases must finish without an exception; ordinary averaging and uppercase-name behavior must remain correct. The documentation specifies no exact return value for empty/null inputs, so the oracle imposes none. These checks are deliberately narrow and do not establish production correctness, SDK upstream-suite acceptance or model quality.

From the repository root, the original fixture must return exit 1 with two errors and two passing tests:

```sh
rtk python3 -m unittest discover -s examples/native-sdk-acceptance/claude-quickstart -p test_utils.py -v
```

For a later authorized SDK run, copy only `utils.py` into that task's isolated workspace. Keep this oracle in the verifier's checkout. Run the same command with `NATIVE_SDK_CANDIDATE` set to the absolute path of the produced `utils.py`; this test imports and executes that candidate, so use the task's approved isolation. Preserve the test output, process status and SHA-256 of both files before and after execution. Require all four checks to pass, an actual native tool result and a successful SDK terminal result. A statement that the model fixed the file is insufficient.

The source-backed candidate task uses the Quickstart's native SDK interface and supported tool loop. No model runner, provider call, new target configuration or comparative evaluation is implemented here. Cross-runtime adaptation and complete result/usage capture remain subject to independent review and the current builder's readiness handoff.
