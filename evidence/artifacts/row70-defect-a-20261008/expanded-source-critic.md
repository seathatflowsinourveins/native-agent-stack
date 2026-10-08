# Row70 Defect A expanded independent source critic

Observed 2026-10-08T17:29:38Z. Evidence class: independent source/metadata observation. Reviewed the current expanded working-tree bytes above prior public head `d159831f6a019a745bd3d1dc8879fb115829c1f3`, with original Defect A scope based on `8c1428d222f2bb815a742f6a80715573f8971a15`.

**Outcome: the eight CC171625Z site classifications are satisfied at the recorded source tuple. No additional publish-blocking source defect was found.** This report is the actual retained expanded critique; the earlier three-file critique was not substituted for it. Parent receipt binding, registry refresh, final publication validation, review-thread disposition and exact-head hosted gates remain separate and pending.

## Authority and exact scope

CC171625Z, relayed 2026-10-08T17:16:53Z, supplies eight classification rows. The first narrow scope omitted live owner/helper/citation sites; the current review includes those sites and protects the named history-kept bytes. The reviewed source changes do not supply new installation, native client/model execution, policy acceptance or an upstream test-suite result.

| CC site | Class | Independently observed result |
| --- | --- | --- |
| `evidence/artifacts/new-wsl-install-plan-20261002/owners.json:139-141` | live | Tag is v0.0.79; publication is 2026-10-07T17:12:35Z. The old pushed_at value 2026-10-01T14:23:34Z is unchanged. Exactly two owner metadata leaves differ from prior head. |
| `evidence/artifacts/new-wsl-install-plan-20261002/accept.sh:369,373` | live | Both SRT source comments use d9aac209 README line168. All noncomment bytes are unchanged. |
| `evidence/artifacts/new-wsl-install-plan-20261002/install.sh:327,948` | live | Actual SRT install command selects 0.0.79. OpenHands settings citation uses d9aac209 README line174. No other executable command differs from prior head. |
| `evidence/artifacts/new-wsl-install-plan-20261002/config/openhands-job@.service:2` | live | Settings citation uses d9aac209 README line174; all noncomment unit bytes are unchanged. |
| `evidence/artifacts/new-wsl-install-plan-20261002/config/openhands-worker-skill.md:28` | live | Source link uses d9aac209 README line174. Instruction/frontmatter prefix before Sources is unchanged. |
| `evidence/artifacts/new-wsl-install-plan-20261002/config/srt-client-accept.sh:2` | live | Source header uses d9aac209 README166-179 and CLI274-341. The entire noncomment helper body is unchanged. |
| `evidence/artifacts/new-wsl-install-plan-20261002/SOURCES.md:682-690,1054,1122` | mixed | Current install/source/archive block moved to0.0.79 and d9aac209. Dated lines1054 and1122 are exactly equal to prior HEAD, including their old v0.0.77/v0.0.78 scopes. |
| `evidence/artifacts/new-wsl-install-plan-20261002/validation.json:94` | history-kept | Whole file is byte-identical to prior HEAD; SHA256 `3e45b756af99d7683eb329af5672d48b14c2cac35e058f1900a87d6c19532552`. |

## Actual execution-path and protection observations

The function `sandbox-runtime-srt()` in the living installer still has the same selector and dispatch path. Its executable line is:

```sh
run_command 'npm install -g @anthropic-ai/sandbox-runtime@0.0.79' || return "$?"
```

The JSON slot agrees on `v0.0.79`, `npm-global` and `npm install -g @anthropic-ai/sandbox-runtime@0.0.79`. Install, smoke and settings sources use immutable commit `d9aac2098351ca17f3743fbaf6ecbd0051b7e00e` at README lines14,168 and174.

Derived from current JSON plus `git show` at the recorded base: 84 plan rows; only `sandbox-runtime-srt` differs; the other83 rows and nonrow plan fields remain equivalent. Acceptance command/kind values stay unchanged. Derived from current files plus prior HEAD: installer, acceptor, SRT helper and OpenHands unit noncomment bytes stay identical; worker instruction prefix stays identical. Thus no policy controls, fresh-client instruction or service behavior was changed by the expanded citation patch.

The frozen earlier `evidence/receipts/native-sandbox-smoke-20261008.json` remains SHA256 `28aa0c7d0f4df1f8048c2b3478ac063dc2ef5b9aadc427714f6fe6d8f7081405`, with its prior pending field and native observations preserved. Records B-E, catalogue/profile/handbook changes, workflows, credentials and always-loaded rule surfaces are outside this edit. This review did not modify or reclassify them.

## Primary source reads made by this critic

All four read-only source requests returned rc0, empty stderr, at 2026-10-08T17:26:23Z:

- `gh api --cache 120s repos/anthropics/sandbox-runtime/releases/tags/v0.0.79 --jq '{tag_name,published_at,prerelease,draft,html_url}'` returned clean v0.0.79, published2026-10-07T17:12:35Z; draft=false and prerelease=false. Native stdout SHA256 `fe3f132f89f0aa4ac2f7eea952b96b0fbdf88ce2c2f0246306becb3c60f3351e`.
- `gh api --cache 120s repos/anthropics/sandbox-runtime/commits/v0.0.79 --jq '{sha,html_url}'` returned `d9aac2098351ca17f3743fbaf6ecbd0051b7e00e`. Native stdout SHA256 `185c39c271c8ce367307242f6fda90c76448cd9b57a507912263c3d05292036b`.
- `curl --fail --silent --show-error --max-time 25 https://raw.githubusercontent.com/anthropics/sandbox-runtime/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md` returned78382bytes, SHA256 `2b18ce30672734247519435d5755875ed5f962ef9d0dbfe00994f6097bbe4b93`. Actual lines14,168 and174 name npm install, hello-world smoke and explicit settings.
- `curl --fail --silent --show-error --max-time 25 https://raw.githubusercontent.com/anthropics/sandbox-runtime/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/src/cli.ts` returned23557bytes, SHA256 `b4a509dc9ec253f7f66459f0dc6fc2ad9a000bbd95e5cf72e436d9c9f445085a`. Lines274-341 declare settings, load it and refuse explicitly missing, empty, unreadable or invalid settings; the reanchored range supports the stated source contract.

The current SOURCES block's npm archive SHA256 `5a730e4367c264ccc4b592af01dab038a6c39db7c184efbd132841688fa854f1` agrees with the retained downloaded/rehash observation in `evidence/artifacts/row70-codex-binding-20261008/source-binding.json`. This critic did not download or rehash that archive again; the integrity result remains its original dated read-only observation, separate from native acceptance.

## Retained worker checks independently inspected

`evidence/artifacts/row70-defect-a-20261008/live-site-review.json` has9160bytes and SHA256 `db1dbcd46415d8a61dabe733b5b726c2d083100e6a793ae9f32d37f172a78ee8`. Its eight site rows agree with the classification above. All seven listed current source hashes/byte counts and both dated SOURCES line hashes match actual files.

The record retains the worker's actual native checker invocation at17:23:00Z:

```text
nice -n 10 ionice -c2 -n7 python3 -B evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py
rc=0
OK: 84 rows: 63 installed (60 by the default run, 3 only when named), 2 measurement-only, 19 not installed; 193 commands and 113 acceptance entries agree with the scripts (2 additional checks included)
stderr=""
```

It separately records rc0 and empty stdout/stderr for each `bash -n` invocation on `install.sh`, `accept.sh` and `config/srt-client-accept.sh`, plus `git diff --check` rc0. These are retained worker source checks; this critic did not rerun them. `check_plan.py` is the available maintained checker. README's original `gen_plan.py` reference remains historical; no unavailable-generator execution is claimed.

## Reviewed source tuple

| Repo-relative file | Bytes | SHA256 |
| --- | --- | --- |
| `evidence/artifacts/new-wsl-install-plan-20261002/install.sh` | 134397 | `4b29a0a0ef8675c1a472f08cf829a7bc071c5146ea25d55eee634aa58bab96b6` |
| `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json` | 487688 | `a12ef9e9fe82bd016ef977ba4f06a576cda8516febdb1156e69fa9602d85ee87` |
| `evidence/artifacts/new-wsl-install-plan-20261002/README.md` | 97988 | `f399735ce298ce3644f3516e526b0c9edd0b7324e72723b38dda1ee428080919` |
| `evidence/artifacts/new-wsl-install-plan-20261002/owners.json` | 35189 | `a75511675f56df573e2700b04c40db69f35f2c44225f5eff304d1521d15369ab` |
| `evidence/artifacts/new-wsl-install-plan-20261002/accept.sh` | 199902 | `01ed1c58366004111f68923550d6ef7240fbfd25feb7176f01a94359d638412d` |
| `evidence/artifacts/new-wsl-install-plan-20261002/config/openhands-job@.service` | 1114 | `89628798b1a147a5f2173539cc919712a3eeb08e06bc1a3a423806119deeb24b` |
| `evidence/artifacts/new-wsl-install-plan-20261002/config/openhands-worker-skill.md` | 1763 | `5c9c225171ee83e8a4146e1419f7030e11e0c8d57c13c2f6e153e5e171571784` |
| `evidence/artifacts/new-wsl-install-plan-20261002/config/srt-client-accept.sh` | 12192 | `877e8c4ddc2d1dd7d66551e3fc027b8c578a21e0e74c21297eac7d356f00f8d9` |
| `evidence/artifacts/new-wsl-install-plan-20261002/SOURCES.md` | 227759 | `26f8bdf84cb49332a08dbfe686b21eb0b3e477601cba1642e2abd120cc2b2a1c` |

The tuple includes the original three Defect A source files and the expanded live citation/owner files. It is an as-observed working-tree tuple, not a claim that a future commit or merged head has identical bytes.

## Remaining gates, limits and completeness

No missing live site remains in the eight-row CC table. The publisher release identity, explicit npm execution path, README/CLI source anchors, mixed current/history block and whole frozen validation file were covered. The original pre-registration hash-mismatch check remains a failure and cannot be promoted into publication PASS.

For the second P2, parent must copy this exact actual report into its public evidence artifact, hash those bytes, and bind that artifact before recording the independent critic check as passed. Parent still owns registry-last refresh, final validate.py and exact-head hosted/review gates. The report itself does not establish those results.

The inverse is a repository-source/evidence revert only. No install, native smoke, policy test, provider/model request, GPU/runtime/broker operation, private configuration/credential read or host service action was performed by this review. The next modality beyond this defect is the separately owned native client/policy acceptance at its declared version and inputs; current source consistency is not that acceptance.
