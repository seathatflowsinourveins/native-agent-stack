# Blind comparison evidence (2026-09-23)

Comparison artifacts for the blind evaluation recorded in
[`docs/decisions/2026-09-22-github-automation-closure.md`](../../../docs/decisions/2026-09-22-github-automation-closure.md#blind-comparison-2026-09-23)
("Blind comparison (2026-09-23)"). Every file below is copied unchanged from
the coordinator's comparison run except `judgments-cmp-a-20260923.redacted.json`,
whose every absolute path under `/tmp` or `/home` was replaced with the literal
`<scratch>`. `SEALED-KEY.json`, arm checkouts, `*.diff` files and battery JSON
files are deliberately not copied here.

| File | sha256 |
| --- | --- |
| `PREREGISTRATION.md` | `6ef62ccf8c72c2f7405ea6af872693efb0f2af6b3f55307b248444f0e257749b` |
| `battery_catalog.py` | `84c2ae1c0f7aa5eb21e9b16c501fcdc6217fdbd08b2a8360b60e94922fe96145` |
| `closure-cmp-a-20260923.json` | `0c5ce0ce49aa9a2dc6d718e74f21518bd00c3b31bb309f33f3a72e35c42a2fcf` |
| `judgments-cmp-a-20260923.redacted.json` | `cbf106603380b661755964724366a8225adfa8127b8ade98a9de27839377e886` |
| `packet-cmp-a-20260923.json` | `43a48b2ef0f3b86c55bd65ddca48aebe91c51ff0e84367ddfc8a61a6f195a91f` |
| `protocol-cmp-a.json` | `804349c9de90426727afcbf32a7899c588db55efe6cdc59f0be0bae8e8a5b246` |
| `spec-catalog.md` | `7d70f7a6e36b6ef252946317c7e8b3a3b7e0906a17cae9f2bbb4bf69469f259b` |
| `wfemu.py` | `4765600792da23c3e9c3efe598a2052a7e0fa27ff9da4a2b2dbbb45f8d6b7719` |

`judgments-cmp-a-20260923.redacted.json`'s original, unredacted file (not
committed here) has sha256
`d170656cbd42c216de3c0de8ea196cab4ca0935908a9a7433500b381bc732bb3`.
