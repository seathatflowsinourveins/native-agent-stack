# Scheduling (`scheduling-supervision`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## scheduled-tasks

**Status:** default. **Default:** systemd --user timers with oneshot services for durable host-local runs (a bounded headless command, `claude -p` with explicit settings when a model is needed)

- **Route:** Session `/loop` and the Cron tools only for temporary in-session polling (7-day expiry, no catch-up); GitHub Actions schedules for repository jobs
- **Alternatives, ranked:** 1. Session `/loop` and Cron tools; 2. Cloud routines; 3. dagucloud/dagu for multi-step local workflows; 4. GitHub Actions schedule
- **Rejected:** Session tasks as the durable scheduler; Saved scheduled tasks as reboot-durable state; 'Recurring tasks last 3 days'
- **Evidence:** scheduled-tasks docs; scheduling-O7, O8, O10
- **Notes:** Adjudicated: systemd stands (refuter pending at writing). Owed: a `claude -p` run started by a systemd timer across a WSL restart. Verified: on WSL2 the timers outlast sessions and terminal closes but not the distro; after a shutdown nothing fires until the distro starts, and missed runs catch up only with `Persistent=true` (token-report-refresh lacks it).
- **Overturn when:** A native scheduler survives a host restart with catch-up, or the systemd run fails where a native one passes.
- **Primary sources** (read 2026-10-09; 1 of 1 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/) (2026-02-11; asserted; extends): Fight agent-replicated drift with garbage collection: encode 'golden principles' in the repository and run recurring background agent tasks that scan for deviations, update quality grades and open small, targeted refactoring PRs. A recurring doc-gardening agent likewise fixes docs that no longer match the code.
