# Codex currency upgrade checklist

Run this checklist at **every Codex upgrade** before reusing the opt-in
`omniroute-search` profile. The main workhorse continues using the bundled
catalog and Lite. The designated client-configuration owner applies profile
and catalog changes; a currency lane prepares evidence and a review packet.
See the [2026-10-06 decision](decisions/2026-10-06-codex-omniroute-opt-in-search.md).

Every currency run also checks [active hosted-model selectors](active-model-currency.md):
refresh the three native catalog observations when due, generate the latest-family
manifest, then run `python3 scripts/active_model_currency.py check --root . --host`.
The daily currency collector invokes this check automatically. Keep dated records
unchanged and leave user configuration/hook application to the CC.

1. Check and record capability evidence in this order: **FIRST, installed
   client** version (`rtk codex --version`), relevant help (including
   `rtk codex debug models --help`) and the relevant non-secret settings it
   reads; **SECOND, that installed version's changelog or official release
   notes**; **THIRD, upstream source at the installed tag**; **FOURTH, official
   documentation**. Retain commands, returned observations and dated source
   locators in the upgrade record; never record credential values. Confirm the
   installed help still documents `--bundled` and verify the implementation
   before using a changed command. An absence claim must name at least the
   installed-client and version-changelog checks, or be limited to what the
   cited source shows. At 0.160.1, the inspected implementation directly
   serializes the embedded catalog without loading client config/auth
   ([openai/codex@rust-v0.160.1: cli/src/main.rs:2068-2095](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/cli/src/main.rs#L2068-L2095)).
2. Export the newly installed binary's catalog and record its SHA256. Do not
   reuse the old projection or manually change model metadata. The native
   export is normalized by upstream's serializer, so its byte hash differs
   from the embedded source-file hash
   ([protocol/src/openai_models.rs:840-943](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/protocol/src/openai_models.rs#L840-L943)).
3. Regenerate the projection using the exact procedure below. Compare it to
   that export and require equality after restoring only the original Lite
   flags. Preserve all models and every other value. Record model count,
   changed-flag count, CLI version, source tag and both output hashes. Inspect
   the version's transport changes before accepting the projection.
4. Have the designated owner make the new catalog available at the profile's
   **absolute** `model_catalog_json` path and retain the prior artifact for
   rollback. Keep `web_search = "live"` and both standalone switches false in
   the opt-in profile. Do not add that catalog path to the workhorse or base
   config. In the cited a956835d implementation, the startup catalog replaces
   the default and the static manager's refresh methods are no-ops
   ([core/src/config/mod.rs:2143-2171 at a956835d](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/config/mod.rs#L2143-L2171),
   [models-manager/src/manager.rs:757-827](https://github.com/openai/codex/blob/a956835d/codex-rs/models-manager/src/manager.rs#L757-L827)).
5. Start a fresh opt-in session after application. Under the coordinator's
   authorized acceptance scope, retain the native known-answer search result
   and usage. Record any error before a bounded repair. Check the latest
   official OmniRoute release for `/v1/alpha/search`; reopening the workhorse's
   standalone gate additionally requires the decision's matched quality
   comparison against hosted search.

The commands below prepare public model metadata in an owned cache. They do
not apply client configuration, inspect credentials or run a model. Run them
from a non-Git scratch directory, outside any prohibited heavy-work window.
`TASK_CACHE` is a task variable; it does not replace a system directory variable.

```sh
TASK_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/native-agent-stack/codex-search"
rtk mkdir -p "$TASK_CACHE"
rtk codex --version
rtk proxy codex debug models --bundled > "$TASK_CACHE/bundled.json"
rtk proxy sha256sum "$TASK_CACHE/bundled.json"
rtk proxy python3 - "$TASK_CACHE/bundled.json" "$TASK_CACHE/omniroute-search.models.json" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

source_path, output_path = map(Path, sys.argv[1:])
original = json.loads(source_path.read_text(encoding="utf-8"))
assert isinstance(original.get("models"), list) and original["models"]
projection = copy.deepcopy(original)
changed = 0
for model in projection["models"]:
    assert isinstance(model.get("use_responses_lite"), bool)
    changed += model["use_responses_lite"]
    model["use_responses_lite"] = False
restored = copy.deepcopy(projection)
for old, new in zip(original["models"], restored["models"], strict=True):
    new["use_responses_lite"] = old["use_responses_lite"]
assert restored == original
output_path.write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
assert json.loads(output_path.read_text(encoding="utf-8")) == projection
print("models", len(projection["models"]), "changed_lite_flags", changed)
for path in (source_path, output_path):
    print(hashlib.sha256(path.read_bytes()).hexdigest(), path)
PY
```

At the initial 0.160.1 qualification, the embedded raw JSON hash is
`fd219bd9f061278275f528939f82f54d2eb97df4b25c23b022adbe48813d920b`,
the native export hash is
`262dc36e0e7beb290aef8196bd59f42acf51647b8f7b68dafa533ae7742019e6`,
and the projection hash is
`252a88f068e37d646281fce36982876274c0c483012cba83b048c11dde463419`.
These identify the dated artifacts; future upgrades must record their own hashes.
