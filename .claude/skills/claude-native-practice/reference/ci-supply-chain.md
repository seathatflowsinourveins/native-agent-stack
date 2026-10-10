# CI and release tracking (`ci-supply-chain`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## release-tracking

**Status:** default. **Default:** Scheduled trackers: catalog-freshness.yml (daily read-only report plus a Monday proposal PR), practice-references-freshness.yml (weekly, report-only), the host's upstream surface watch (six sources: npm dist-tags, the Agent SDK settings types, the settings reference, env vars and mods, the Codex release, the CHANGELOG delta), plus Dependabot for action versions

- **Route:** 147 of 148 adopted repositories have a declared tracker (pandas has none); the weekly practice pass reads these reports
- **Alternatives, ranked:** 1. renovatebot/renovate, adopted only if the 2026-10-02 overturn test passes on current Renovate; 2. `autoUpdatesChannel: stable` for the client
- **Rejected:** updatecli/updatecli (failed the 2026-10-02 trial); lilydjwg/nvchecker; Dependabot for catalog and runtime pins; Hosted trackers
- **Evidence:** 2026-10-02 local trial (Renovate 44.132.2, updatecli v0.122.0, nvchecker 2.22) kept the stdlib trackers; L3 R7 tracker map
- **Notes:** Adjudicated: the incumbent stands; the refuter upheld it. Native client floor if the channel ever moves to stable: `minimumVersion` (any settings file); `requiredMinimumVersion` and `requiredMaximumVersion` are the managed startup gates. Dependabot is claude-code-action's only release tracker. Integrity: the opt-in Monday propose job is model-free but holds contents and pull-requests write; schedules on a public repository pause after 60 days without activity.
- **Overturn when:** Current Renovate passes the 2026-10-02 overturn test: seven daily runs on the same runtime rows plus deliberately outdated canaries, with fewer missed pins and no lost archived or renamed flags.
