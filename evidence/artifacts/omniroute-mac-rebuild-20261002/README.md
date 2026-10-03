# OmniRoute gateway rebuild on the Mac coordinator, 2026-10-02

The record of rebuilding the Mac's gateway (launchd `com.native-stack.omniroute`, loopback port 20128) on upstream
`release/v3.8.52` with upstream PRs 13788 and 15167, the launch agent's Codex-following wrapper, and the daily update
check. The decision is [`docs/decisions/2026-10-02-omniroute-mac-rebuild.md`](../../../docs/decisions/2026-10-02-omniroute-mac-rebuild.md).

| File | What it is |
| --- | --- |
| `receipt.json` | Claims, results and limits, with evidence classes |
| `build-manifest.json` | Base commit, carried PRs and commits, build steps, BUILD_SHA and the tarball's sha256 |
| `checks/probe-before.json`, `checks/probe-after.json` | The probe gate before the switch and on the passing attempt (usage blocks removed) |
| `checks/switch-1.log`, `checks/switch-2.log` | The first switch (rolled back) and the second (passed) |
| `launchd/*.plist.json` | The gateway's launch agent before and after, and the update-check agent (home paths masked) |
| `scripts/*.txt` | The build, switch, probe, wrapper and update-check scripts as they ran (paths masked) |

Paths are masked as `<HOME>` and `<build-dir>`. The gateway's data directory and every credential were left
unopened; the placeholder key in the launch agent is the documented non-secret loopback value.
