# Serena exact-response correction (2026-09-30)

The native integration gate rejected the immutable Serena pin's Claude tool list.
The historical golden `d2e22bce…` has no retained response preimage; its origin
remains unknown. This repair corrects that reference to `22be876d…` while retaining
the existing exact-byte comparison, context discrimination and scoped-state checks.
Initialize and Codex references are unchanged.

The selected source is [oraios/serena at
c6fbd1c5932df2494ffa0020af5a9fbe80b82143](https://github.com/oraios/serena/tree/c6fbd1c5932df2494ffa0020af5a9fbe80b82143):

- [Claude context](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/resources/config/contexts/claude-code.yml)
  and [Codex context](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/resources/config/contexts/codex.yml)
  define distinct tool exclusions.
- [Tool definitions](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/tools/file_tools.py)
  and [schema generation](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/mcp.py#L55)
  supply the observed descriptions, parameter schemas and JSON tool responses.
- The [commit's changelog](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/CHANGELOG.md)
  and the installed native `start-mcp-server --help` were inspected before the
  pinned source. This repair introduces no capability or upgrade claim.

[Source identity](source-identity.json) compares 128 installed Python/resource
files under `src/serena` and `src/interprompt` against the immutable Git tree's
blob identities: no missing files and no mismatches. It records resolved dependency
versions without claiming a dependency caused the historical difference.

[The separate stdio observer](independent/observation.json) imports neither
`native_token_ci.Run` nor its MCP parser. Both native processes exited 0. Its
retained [Claude](independent/claude-code.stdout.txt) and [Codex](independent/codex.stdout.txt)
response preimages are exact unsanitized stdout bytes; these responses contain no
local paths. Logs replace local paths, and retain their hashes before replacement.

| Response | Bytes | SHA-256 |
| --- | ---: | --- |
| Initialize, both contexts | 465 | `5277f280d5eeb79d76c620b8676144aab4d33b83dd1d89c7c222a853c676e494` |
| Claude tools/list | 25360 | `22be876d89f3e90c780f5ca31b6af290a509b6c34e3628d736d7e9b0a5a9c2b0` |
| Codex tools/list | 30083 | `2fe0460cd748ae5df612496585404a47f282ad90747a94d3c17a1149ee0f194f` |

## Returned red and green checks

Commands run from the checkout; every output directory is new. The coordinator's
separate whole-stack clean-prefix run already provides the fresh-install
observation at this exact pin; this bounded repair reruns only Serena.

| Command | Exit | Retained result |
| --- | ---: | --- |
| `rtk python3 evidence/artifacts/token-lifecycle-resolution-20260930/serena-repair/run_fixture.py --output evidence/artifacts/token-lifecycle-resolution-20260930/serena-repair/red-existing` | 1 | [Original failing native receipt](red-existing/receipt.json): 3 commands, init passed, exact tools-list gate failed |
| `rtk python3 -m unittest discover -s tests -p test_native_token_ci.py -k verified_native_preimages` before correction | 1 | [Failing regression](red-regression.txt) against the old golden |
| Same regression after correction | 0 | [Passing regression](green-regression.txt), including schema faults for both contexts |
| `rtk python3 -m unittest discover -s tests -p test_native_token_ci.py` | 0 | [48 passing tests](green-unit-suite.txt) |
| `rtk python3 evidence/artifacts/token-lifecycle-resolution-20260930/serena-repair/run_fixture.py --output evidence/artifacts/token-lifecycle-resolution-20260930/serena-repair/green-existing` | 0 | [New native receipt](green-existing/receipt.json): 3 commands, all 4 checks passed |
| Same fixture with output `changed-schema-claude` and `--changed-schema-context claude-code` | 1 | [Claude live fault](changed-schema-claude/receipt.json), exact tools-list gate rejected |
| Same fixture with output `changed-schema-codex` and `--changed-schema-context codex` | 1 | [Codex live fault](changed-schema-codex/receipt.json), exact tools-list gate rejected |

The live faults use run-owned `sitecustomize.py` to alter one generated schema
type at the pinned [`make_mcp_tool` seam](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/mcp.py#L281).
Installed files and frozen expectations are untouched. The native server processes
still exit 0; the integration wrapper exits 1 because the unchanged parity gate
rejects the changed bytes. [Independent artifact inspection](controls-observation.json)
confirms one schema field changes, tool names and initialize bytes remain equal,
the other context stays byte-identical, and only the targeted context emits the
runtime fault marker. These are local fault controls, not unchanged upstream tests.

The regression replays the native preimages through the existing fixture and
changes a schema type without patching the expected hashes. It is a local
regression with synthetic faults, not another native execution.
The [final 48-test run](final-unit-suite.txt) also passes after naming the exact
stdout files `.stdout.txt` so the repository tracks and hash-lists them normally.

`rtk python3 scripts/validate.py` [returned exit 1](validation.txt) before shared
manifest integration: the two edited files have stale hash/byte entries and the
new evidence is not listed yet. The coordinator owns that manifest update.

## Correction record

The disproven assertion was that the previous Claude hash represented the current
immutable pinned server's exact native response. Verification proceeds from native
red output, independent original-source blob comparison, independent native stdout,
red regression, corrected reference, native green and deliberately failing live
schema controls. A copied opaque golden with no response preimage cannot establish
source parity. Retain the complete preimage and source identity beside future
goldens. No specific dependency, serialization or configuration cause is asserted.

No language server, active project, credentials, model or provider runs in this
repair. All temporary state is removed. This evidence covers Serena's scoped native
MCP operation and local integration gate; full-stack acceptance remains the
coordinator's separate rerun.
