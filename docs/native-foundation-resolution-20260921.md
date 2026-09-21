# Native foundation qualification — September 21, 2026 UTC

The selected foundation now has additional clean-installation, repeated native
retrieval and native writing/recovery evidence. The observed results support
task-specific tool and worker selection. They do not support forcing every tool
into each task, a universal token-saving rate, or an “all SOTA” certification.

| Requested move | Observed result | Evidence and boundary |
| --- | --- | --- |
| Publish the dashboard foundation | PR 37 merged at `8ddfc6a0785944955d8c75740057a64ce015133b`; all five PR checks passed | [Published change](https://github.com/seathatflowsinourveins/native-agent-stack/pull/37), [native dashboard data](native-dashboard-data.md). CI is separate from native model execution. |
| Recheck Claude token efficiency | Six amended attempts passed independent source, visible, held-out and scope checks; selective policy used 2.42% more aggregate tokens | [Retrieval pilot](claude-selective-context-pilot-20260921.md). All selective runs chose native computation, so there was no Context Mode treatment. |
| Qualify writing workers and recovery | Both writing arms produced accepted repairs; native failed-worker replay and coordinator exit/resume preserved work | [Writing/recovery report](native-workflow-writing-recovery-20260921.md). The comparison retained process-contract failures; graceful native exit is not a hard-crash or reboot test. |
| Replay upstream installation | Fresh Ubuntu userspace passed the existing four-tool fixture, native client installation/reinstallation, selected skill checks and removal | [Portable installation](portable-userspace-install-20260921.md). No host credentials were copied; both clients remained signed out. This qualifies the named subset on the existing WSL kernel. |
| Open useful dashboards | Grafana, scoped memory, graph, token report, Dagu and AgentsView rendered; Windows HTTP checks for Grafana and memory returned 200 | [Dashboard entry points](native-dashboards.md). Browser launch requests and page rendering are distinct observations. |
| Qualify future scheduled operation | Existing daily 9 a.m. maintenance was preserved and its next actual scheduled-wake evidence requirement added | Registration is complete; a new genuine scheduled wake and app/host restart remain unobserved in this qualification. No duplicate maintenance timer was created. |

## What the token evidence says

The three corrected retrieval pairs reported **947,493 tokens** for the native
policy and **970,380** for selective routing. Native subprocess time totaled
88.106 versus 79.182 seconds. The differences are observations from one fixture
with uncontrolled cache warmth, not causal estimates. A rejected initial attempt
used another 612,381 tokens. All seven task attempts therefore total **2,530,254
reported tokens**; coordinator, audit and report-production usage are outside
that total. Subscription billing remains unknown.

The small writing repair used **194,781 reported tokens** with one agent and
**753,508** with Fable plus two workers. Both repairs passed independent unpiped
verification, but the model-run test pipelines masked exit status, and the
Workflow arm skipped a required skill invocation and exceeded its literal read
scope. A reviewer also retried a rejected output schema. These deviations are
retained; this is not a fully compliant comparison or a general model ranking.

The recovery experiment used the native `/workflow-authoring` entry. The
implementation ran once across three Workflow launches, while the reviewer was
selected for failure, stopped with the coordinator, then completed after native
resume. The observed effects were one implementation and one review. Unrelated
tracked and untracked edits survived. Repeated cumulative usage events are not
added as new consumption. The recovery client's reported cumulative total of
2,143,696 differs from the retained unique-message total of 1,937,995 by 205,701;
the cause is not established. Full accounting reconciliation is therefore not
qualified. These are actual native operations on a local fixture, not an
upstream test suite or a guarantee for arbitrary external side effects.

## Default practice and upstream commands

Keep the existing [native harness defaults](harness-defaults.md): focused source
reads for known locations, one sufficient retrieval lane, bounded workers for
useful independent work, original-source verification, and complete accounting
of failures and retries. The evidence does not justify a global model change or
another orchestration runtime.

Use the [native Ultracode recipe](../recipes/claude-native-ultracode.md) for
Claude's own authoring, Workflow, agent dashboard and resume controls. Define
permitted native metadata reads separately from owned code writes, and run
acceptance commands with preserved exit codes. On a new environment, use the
upstream install commands and recorded pins in the
[clean-userspace guide](portable-userspace-install-20260921.md). The four-tool
fixture is the repository's existing integration check; it is not represented
as the complete upstream test suites.

The directly exercised installation sources include
[Claude Code](https://github.com/anthropics/claude-code),
[Codex](https://github.com/openai/codex),
[RTK](https://github.com/rtk-ai/rtk),
[QMD](https://github.com/tobi/qmd),
[Repomix](https://github.com/yamadashy/repomix),
[TOON](https://github.com/toon-format/toon), and the selected
[ECC](https://github.com/affaan-m/ECC) skills. Existing context, memory and
observability selections remain in the [foundation catalog](../catalogs/foundation/README.md).
The [community review](community-native-practice.md) explains selective adoption
of ECC, Shan's Claude practices and discovery lists. A catalog entry does not
mean that every feature was executed in this wave.

Independent reviews checked the native experiments and this integration's
claims. Publication validation covers 68 components, 113 receipt registrations
and 1,276 file hashes. Catalog, foundation and generated-page checks passed;
the repository suite ran 686 tests with 41 skips. These structural checks are
separate from the native operations above. Initial integration checks caught
stale generated-page hashes and missing lifecycle receipt references; those
were synchronized and the affected checks rerun successfully.

On the authoring PC, the populated entry points are:

- [Grafana foundation dashboard](http://127.0.0.1:13000/d/native-foundation-data/253abf9)
- [Scoped ai-memory](http://127.0.0.1:49374/web/w/agent-lab/agent-lab)
- [SocratiCode graph snapshot](http://127.0.0.1:17500/socraticode-graph.html)
- [Full native token report](http://127.0.0.1:17500/token-savings.html)
- [Scoped session archive](http://127.0.0.1:17384/)
- [Dagu history](http://127.0.0.1:18525/)

These loopback URLs belong to that PC. The native Claude agent dashboard is
also available through its installed terminal profile. Other PCs resolve their
own paths, ports, native sign-ins and selected integrations and collect their own
evidence. A real scheduled wake and a physical-host restart are future
observations, not conditions silently marked passed here.
