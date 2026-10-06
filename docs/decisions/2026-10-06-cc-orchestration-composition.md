# Command-center orchestration composition (2026-10-06)

The command center (`wsl-architecture-design`) decided this composition at
1:10 AM EDT (05:10Z). This record implements round-2 step 11 and includes the
co-op's subsequent measured launch-and-close gate. The north-star action is one
view and one control path over Claude Code and Codex lanes, SDK jobs and framework
runs supporting US-equities research and historical simulation, followed by
independently qualified broker paper operation. It does not qualify a strategy
or broker operation.

## Sources and evidence boundary

The original records remain in the host's private coordination state under
`~/.local/state/native-agent-stack/coordination/`:

- `e2e-truth-20261006/orchestration-round2-wf_1c0bf756-c9d.json`: `decision.decision`,
  `decision.steps` (especially step 11), `decision.overturn_if`,
  `decision.decision_critical_claims`, `refutations` and `critic`.
- `ns2604-coop/orchestration-round2-20261006/receipt.md`: measured local integration
  checks on NativeStack2604, including failed attempts and corrected judgments.
- `ns2604-coop/lessons/2026-10-06-script-e-pipe-stdin.md` and
  `ns2604-coop/lessons/2026-10-06-hcom-codex-first-turn.md`: the two live-test lessons.
- `e2e-truth-20261006/e2e-truth-sweep-wf_6f2c775d-293.json`: the gateway sweep,
  its OmniRoute unit and synthesis. Token-save status belongs to that record;
  round-2 critic finding 3 requires removing the superseded token claims here.

The measured summary below covers receipt entries through 6:00:21 AM EDT
(10:00:21Z), when this lane launched. Later stopper tests added by the co-op are
separate owner-run observations, not part of this gate summary.

This PR records prior host execution; it runs no new lane lifecycle test and
changes no host configuration. The receipt's local integration checks are not
unchanged upstream tests. Source review, launch-and-close acceptance, OTel
attribution, terminal experience and full lifecycle qualification remain separate.

Pinned primary sources:

| Source | Pin and relevant interface |
| --- | --- |
| [aannoo/hcom](https://github.com/aannoo/hcom/tree/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b) | v0.7.27, `2c5f343b`; `src/config.rs`, `src/terminal.rs`, `src/launcher.rs`, `src/commands/kill.rs`, `src/hooks/codex.rs` |
| [tmux/tmux](https://github.com/tmux/tmux/tree/cc117b5048f77a4842820f8ebbe3a86e5c077224) | 3.6a, `cc117b50`; `server-fn.c`, `server-client.c`, `server.c`, `client.c`, `tmux.1` |
| [kenn-io/agentsview](https://github.com/kenn-io/agentsview/tree/9be7745ad1906ee24e04eb05bb86c872ef0939a1) | v0.43.0, `9be7745a`; configuration/command docs and supervised `serve --replace` |
| [MicrosoftDocs/terminal](https://github.com/MicrosoftDocs/terminal/tree/c341a6362f9f0346a17ecc5e1e74d2cd9372c8f9) | `c341a636`; profile `closeOnExit` and command-line tab launch |
| [systemd/systemd](https://github.com/systemd/systemd/tree/9ca433482f2281d71718718705ca8cd3bf562ad6) | v259; `man/systemd.service.xml` (`Type=simple`, `Restart=always`, `RestartSec`) |

The source pin for tmux is 3.6a. The installed executable's read-only version
query during this records task reports `tmux 3.6`; the historical receipt is
host acceptance, not evidence that the installed binary equals the reviewed pin.

## Decision and alternatives

Use hcom v0.7.27's user preset `wt-tmux` to launch one Windows Terminal tab and
one tmux session per lane, on the private `-L hcom` server. The preset's close argv
runs `tmux kill-pane`. With the recorded defaults, the attached client exits 0
and the profile's existing `closeOnExit="graceful"` closes the tab. The corrected
live gate passed; fallback A was not needed. The co-op set the terminal default
to `wt-tmux` at 5:59:29 AM EDT (09:59:29Z), exit 0, and read back that active preset.
The first real lane was `orch-records`, generated name `mika`, batch `73c44a40`,
launched at 6:00:21 AM EDT (10:00:21Z), exit 0, with an initial `--hcom-prompt`.

| Choice | Alternative and reason for retaining the choice |
| --- | --- |
| `wt-tmux`, one session per lane | Fallback A is `wt-tab` with a dedicated `closeOnExit="always"` lane profile. It remains the fallback if the controlled exit probe or tab-close check fails. Round 1's exit-0 wrapper with a stop marker is the final fallback if A also fails. |
| hcom launch/message/close | Bare tmux per lane, without hcom's PTY, is the fallback for degraded input/rendering or a delivery stall. Keep hcom messaging only where delivery is demonstrated. |
| Supervised agentsview HTTP monitor | Detached CLI/MCP auto-start can produce an unsupervised daemon and idle exits. MCP/skill adoption waits for an archive-content decision and measured startup cost. Framework-tracing alternatives have not been compared by this gate. |
| Codex writer locks plus rollout events and process scan | A short-lived standalone `codex app-server` reports live state for its own loaded threads, not other embedded lane processes. A shared daemon/proxy can report threads it hosts; that is a different deployment. |
| Grafana live overview, agentsview session drill-down, OmniRoute gateway dashboard | A single monitor has not been demonstrated to cover every lane, SDK job and container/framework run. The source critic keeps that comparison open. |

The CC uses hcom for its new lanes after the gate, each in an owned worktree.
Registry lanes migrate one at a time only after their stop/relaunch/tier paths
understand hcom and the old thread's writer lock is released. This receipt does
not prove completion of that migration. Codex locks are per thread, including
subagent threads, and may be taken briefly by other operations; inspect the held
lock and rollout state without acquiring the lock, and scan for processes with
no held thread lock. The primary implementation is
[writer_lock.rs at Codex rust-v0.160.0](https://github.com/openai/codex/blob/a956835d/codex-rs/rollout/src/writer_lock.rs).

Claude liveness uses `claude agents --json --all`; hcom adds its own instance
rows; SDK jobs retain their job-directory state; Inspect uses its native started
log list; OpenHands and paper jobs use their units. CC-to-co-op direction retains
the ledger and SendMessage path; CC-to-hcom direction requires a matching ledger
send row and `[cc-msg v1]` envelope. Co-op registry messaging remains its own
`codex queue` path. A hook-delivered message alone does not establish delegated
authority. The CC's per-reply graph remains a bounded read of these sources;
continuous change notification and complete framework/container coverage remain
critic follow-up work.

Job/framework attribution is intended to use a conversation-specific
`x-omniroute-session-id`, `X-Correlation-Id` on chat-completions routes, and launch
OTel identity. That attribution is not accepted by this launch-and-close gate.
Gateway compression changes, the separately authorized runtime-worker gateway
and its promptfoo A/B belong to their owners; this PR does not amend them or
restate the refuted token measurements. See the e2e-truth sweep identified above.

## Passwordless agentsview divergence

Keep agentsview v0.43.0 as the session monitor and analytics owner, with supervised
foreground `serve --replace`, `Restart=always`, `RestartSec=10`,
`daemon_idle_timeout="0s"` and the ten selected worker CODEX_HOMEs. The recorded
repository launcher sets the data directory, disables telemetry/update checking
and selects usage-only archival. HTTP reads do not auto-start a daemon.

NativeStack2604 stays passwordless under the user's rule. This diverges from the
workstation's `--require-auth` unit and
[authenticated archive example](../../examples/agentsview-archive.service.example).
The CC's rationale is that the selected local callers already have permission
to start programs. Evidence that a caller lacking that permission can reach the
listener overturns this choice; the Host/Origin boundary remains part of that
assessment. This is a scoped deployment decision, not a general passwordless
recommendation or a new security acceptance claim.

The receipt records unit verification/start exit 0 at 2:25:26 AM EDT (06:25:26Z),
the listener in the unit's cgroup and HTTP 200 at 2:25:45 AM EDT (06:25:45Z), no
listener after stop at 2:25:50 AM EDT (06:25:50Z), no auto-start after an HTTP read
at 2:25:56 AM EDT (06:25:56Z), and an active unit after restart at 2:25:59 AM EDT
(06:25:59Z). The due idle-survival check is not recorded as passed.

## Partial reversal of the tmux decision

The [2026-09-28 terminal decision](2026-09-28-terminal-experience.md) validated
tmux configuration but did not adopt tmux. This decision reverses that rejection
for lane tabs only, to meet the later close-tab requirement. It does not adopt
the old block with `detach-on-destroy off` and `set-titles on`. The lane config
keeps `detach-on-destroy on`, `set-titles off`, `remain-on-exit off` and
`exit-empty on`; the tab keeps hcom's title. `prefix None` leaves Ctrl+B available
to Codex, and `destroy-unattached on` makes tab closure end the lane. Terminal
experience under this composition remains unmeasured.

## Measured live-test results

All timestamps below are on 2026-10-06. These are the receipt's local integration
observations. Where no command exit is retained, the cell says so instead of
inventing one. The deciding gate was steps **0, 3, 4, 8, 9 and 10**; step 7 was
separately re-judged as a transport pass in substance.

| Step / attempt | Local time (UTC) | Returned exit / observation |
| --- | --- | --- |
| 0, original piped-stdin `script -e` probe | 2:27:13 AM EDT (06:27:13Z); 2:27:43 AM EDT (06:27:43Z) | `kill-pane` command/client 0/0; `kill-server` command/client 0/0 although client 1 was expected. Both judgments void because the propagation harness was wrong. |
| 0, corrected pty harness and controls | 2:30:58 AM EDT (06:30:58Z) | Same-harness `exit 3` control → 3; kill-pane client → 0 with `[exited]` and no server; kill-server → 1 with `[server exited]`; client SIGTERM → 1 with `[terminated]`. PASS. |
| 3/4, run 1 without initial prompt | 2:31:39 AM EDT (06:31:39Z); 2:31:54 AM EDT (06:31:54Z); 2:32:05 AM EDT (06:32:05Z) | Launch 0, `zumi`, batch `69f2bf80`; tab count 16 → 17; attached pane `%0`; new Codex PID 139030, no new writer lock before first turn. Observation commands' exits not retained. |
| 7, run 1 | 2:32:36 AM EDT (06:32:36Z) | Send 0, event 4 delivered to `zumi`; wait 1/timed out; message never read. No rollout and hooks unbound. |
| 3/4, run 2 with initial prompt | 5:56:37 AM EDT (09:56:37Z); 5:56:41 AM EDT (09:56:41Z) | Launch 0, `solo`, batch `98bda62d`; ready 0.5 s; tab 17; new PID 1063056 holds its thread lock; hooks bound and session set. Observation exits not retained. |
| 7, run 2 premature wait | 5:56:41 AM EDT (09:56:41Z); 5:56:42 AM EDT (09:56:42Z) | Send 0/event 15; wait 0 matched an old event; transcript 0 but no PONG and unread count 1. FAIL; not delivery acceptance. |
| 8/9/10, run 2 | 5:56:42 AM EDT (09:56:42Z); 5:56:50 AM EDT (09:56:50Z) | Kill 0, `Sent SIGTERM to 'solo' (closed wt-tmux pane %0)`; no server/client chain/tab; tab count 16; no sampled descendants; Codex count 14 equals baseline; thread lock unheld; hcom rows 0. PASS; observation exits not retained. |
| 3, run 3 with initial prompt | 5:57:40 AM EDT (09:57:40Z); 5:57:45 AM EDT (09:57:45Z); 5:57:46 AM EDT (09:57:46Z) | Launch 0, `zulu`, batch `f0bb258a`; ready 0.4 s; READY reply after 5.6 s; hooks bound/session set; tab 17 with `◉ hcomtest-zulu [codex]`. PASS. |
| 4, run 3 | 5:57:46 AM EDT (09:57:46Z) | New PID 1086307 holds the session's writer lock; preset `wt-tmux`, pane `%0`. PASS; observation exit not retained. |
| 7, run 3 and corrected oracle | 5:57:46 AM EDT (09:57:46Z); 5:57:57 AM EDT (09:57:57Z); 5:58:00 AM EDT (09:58:00Z); re-judged 5:58:56 AM EDT (09:58:56Z) | Send 0/event 22; PONG after 11.2 s; transcript 0; unread count 0. Initially marked FAIL for absent literal message body; exchange 2 user text is `<hcom>` and reply is `Sending PONG.`. PASS in substance. |
| 8, run 3 | 5:58:00 AM EDT (09:58:00Z) | Kill 0, `Sent SIGTERM to 'zulu' (closed wt-tmux pane %0)`. PASS. |
| 9, run 3 | 5:58:08 AM EDT (09:58:08Z) | No server, client chain or matching tab; 16 tabs, back to baseline. PASS; observation exit not retained. |
| 10, run 3 | 5:58:09 AM EDT (09:58:09Z) | S alive `[]`; Codex count 14 equals baseline; lock unheld; hcom rows 0. PASS; observation exit not retained. |
| Gate decision | 5:58:56 AM EDT (09:58:56Z) | Corrected step 0 and steps 3/4/8/9/10 pass; close/orphan checks passed twice, runs 2 and 3. Adopt `wt-tmux`; fallback A not needed. |

Not run: live-test **step 6** (typing, multiline keys, Ctrl+B, paste,
bell/title/scrollback); **step 5's Loki and Prometheus OTel queries** (process
snapshots were taken); **11a–11f, 11h and 11i** (warm server, hand-close, crash,
hook coexistence, interop, agentsview state transitions, ledger-authenticated
delivery and Claude). Only the co-op-caller half of **11g** ran; the systemd-caller
half did not. No completed CC graph EXIT observation is retained. This gate
therefore does not establish OTel lane attribution, terminal parity, CC-envelope
handling, Claude acceptance or full migration/recovery.

## Corrections and verification paths

1. **Use a propagation control in the same exit-code harness.** On this host,
   util-linux 2.41.3 `script -e` with piped stdin returned 0 even for `exit 3`;
   stdin `/dev/null` returned 3. The receipt's corrected `pty.fork()` / `waitpid`
   probe (`live0-ptyprobe.py` in its private receipt directory) retained that
   control, kill-pane 0, kill-server 1 and SIGTERM 1. The original probe cannot
   accept or reject tmux's close behavior.
2. **Step 8 prints the bare generated name.** Verify
   [kill.rs:557–569](https://github.com/aannoo/hcom/blob/2c5f343b/src/commands/kill.rs#L557-L569)
   resolves the bare name; [lines 677–679](https://github.com/aannoo/hcom/blob/2c5f343b/src/commands/kill.rs#L677-L679)
   print it.
   Exit 0 and `Sent SIGTERM to '<bare-name>' (closed wt-tmux pane %N)` match the
   measured result. Reject pane-close failure/timeouts; tab/process absence is
   still the deciding observation.
3. **The lane label is `--tag`; record the generated name at every launch.**
   [launcher.rs:1991–2044](https://github.com/aannoo/hcom/blob/2c5f343b/src/launcher.rs#L1991-L2044)
   substitutes the bare generated name for `{instance_name}`, not the tag.
   The exact host preset below retains `ecosystem.lane={instance_name}` as
   evidence of the deployed configuration. It does not prove semantic OTel lane
   labels; the tag/name mapping is required, and the unrun OTel check stays open.
4. **Every hcom launch carries `--hcom-prompt`.** Before Codex's first turn there
   was no session/rollout and no bound hooks. Runs 2 and 3 supplied an initial
   prompt; run 3 demonstrated the reply. The transcript's delivered user turn
   is `<hcom>` because the body arrives as hook context. Judge transport by the
   requested reply and unread count, and poll after the send or scope the event
   query with `--after`; an old idle event is insufficient.
5. **Apply the source refutations before relaying the composition.** User preset
   fields merge with built-in fields; they do not replace the entire preset.
   `server.c` at the tmux pin resolves the exit-empty ordering question. There
   are additional client exit-1 paths, and launch readiness can fail even after
   a terminal spawn succeeds. hcom's runner sidecar can re-export launch
   environment values over tmux `-e`; OTel propagation must be measured. See
   refutations 1–3 and critic finding 3 in the original round-2 record.
6. **Keep step-11's earlier corrections.** Codex's documented app-server protocol
   lists stored threads but standalone live state is in-process; a user hcom
   preset can close a WT tab; agentsview v0.43.0 SDK entrypoints are Claude-only;
   `X-Correlation-Id` is also retained on chat-completions; the CC's organic-e2e
   observation sets `ecosystem.lane`; and the user overruled the hcom deny list.
   Verification paths are the original round-1 refutations, round-2 critical
   sources/refutations, and the measured user-preset gate above. Primary
   corroboration includes [Codex's NotLoaded fallback](https://github.com/openai/codex/blob/a956835d/codex-rs/app-server/src/thread_status.rs#L385-L450),
   [the chat route's caller correlation ID](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b76/src/app/api/v1/chat/completions/route.ts#L287-L322),
   and [agentsview's Claude entrypoint parser](https://github.com/kenn-io/agentsview/blob/9be7745a/internal/parser/claude.go#L219-L222).
   The organic-e2e and user-override notes retain their original observation
   provenance rather than claiming a fresh run here. A one-hour
   observation window cannot establish absence for an entire day.

The five general lessons are contiguous rows in
[the anti-pattern log](../harness-defaults.md#anti-pattern-log). The existing
consistency test checks the table's shape and links; it is not a behavioral
regression test for hcom, script or Codex transport.

## Examples and owner handoff

- [wt-tmux TOML snippet](../../examples/hcom-wt-tmux.toml.example): the host's
  `[terminal.presets.wt-tmux]` table, with only personal user/path substitutions.
- [hcom-lanes.conf](../../examples/hcom-lanes.conf): byte-for-byte host copy.
- [agentsview user unit](../../examples/agentsview.service.example): byte-for-byte
  host copy except `%h` replaces the personal home in `ExecStart`. That launcher
  is required; this is not the authenticated workstation unit.

The TOML snippet uses `<WINDOWS_USER>` and `<WSL_USER>` placeholders; `%h` is a
systemd specifier, not hcom interpolation. These are examples, not an install
or activation instruction. The install-plan owner holds the plan/config through
[#723](https://github.com/seathatflowsinourveins/native-agent-stack/pull/723).
Exact proposed amendments are in this PR's **Handoff to the install-plan owner**
section; neither the install plan nor its config/hash is edited here.

## Overturn conditions

- Controlled step 0 produces a nonzero kill-pane client exit, or step 9 leaves
  the lane tab/process-exit screen: use fallback A, then the round-1 stop-marker
  wrapper if A also fails.
- Input/rendering degrades or delivery stalls: use per-lane tmux without hcom's
  PTY. If hcom's per-run hooks suppress ai-memory/context-mode, try upstream's
  caller-hook merge; drop hcom for those lanes if it fails.
- Windows Terminal releases tmux control mode (tracked PRs #18928/#20639), a
  close/list-tab CLI, or hcom ships a WSL/WT preset with close support or fixes
  #151/#153/#154: rerun the launch/close and migration comparison and replace
  local composition where the maintained interface wins.
- Codex changes writer-lock path/type/release or documents stable cross-process
  status: recheck liveness on upgrade and switch to the better-supported read.
- agentsview ships session names/labels/external parents (#2039/#2124) and passes
  the recorded requalification: replace ledger/lock-derived edges and labels.
  Its newer-release HTTP-only qualification remains open.
- A local caller without program-start permission can reach agentsview:
  enable authentication. Resolve archive content/startup cost before MCP/skill
  adoption, and compare framework tracing on actual framework runs.
- The runtime-worker promptfoo A/B fails saving, exact-value retention or task
  behavior: leave that gateway unpromoted. Codex compression reopens only under
  its separate decision. An OmniRoute call-log session filter or agent_sessions
  interface can replace client-side attribution paging.
- The user requests Codex routing through OmniRoute: require the recorded
  same-task parity run and restored web-search/defect mitigations. The user
  rejects tmux inside lane tabs: use fallback A.

## Open questions and next completeness sweep

Run 1's `zumi`, launched without `--hcom-prompt`, stopped `by pty, closed` after
about 2m12s, despite never reading the delivered message (`last_event_id=0`,
hooks unbound, no rollout). `dani`, also without an initial prompt but with no
message pending, stayed listening for more than three minutes. The cause of the
different lifetimes is unexplained; supplying an initial prompt explains the
delivery failure, not the spontaneous close. The receipt and original hcom
events 2, 4 and 5 are the verification path: READY at 2:31:40.661703 AM EDT
(06:31:40.661703Z), send at 2:32:36.236406 AM EDT (06:32:36.236406Z), stop at
2:33:52.123370 AM EDT (06:33:52.123370Z). READY-to-stop was 131.461667 s;
send-to-stop was 75.886964 s. The receipt's 2:31:39 AM EDT (06:31:39Z) launch
timestamp is the command start, before the ready event.

The source completeness critic's follow-up remains: Grafana MCP; framework
tracing with Langfuse/Phoenix/OpenLIT; remote-control candidates; WT control mode;
a measured event/status carrier; zellij/herdr if tabs are revisited; container
gateway reachability; conversation attribution across subagents; hook
coexistence; systemd callers, resume/warm-server/restart/crash cases; and
agentsview requalification and reproducible config coverage. These are gaps for
the next scoped sweep, not accepted capabilities of this records PR.
