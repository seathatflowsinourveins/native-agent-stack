# Independent native evidence review

Read-only review performed during the September 21 convergence wave by a worker
independent of the native trial executor. No historical model/recovery trial was
rerun. Evidence classes are native execution and independently inspected state;
this is not an upstream test suite.

Both raw native streams contain all five requested retrieval checks, with eleven
completed calls each including discovery. No tool-result failures were present.
Claude recorded 44 successful hook responses. The original bootstrap source
confirms checksum validation and four `fetch` call sites; the original validation
document confirms that product application checks are unconfigured.

Codex used GPT-6 Astra at ultra effort. Its native rollout independently matches
251,225 input + 4,110 output = 255,335 consumed tokens. Cached input 214,400 and
reasoning output 1,316 are subsets. Claude used Fable 5.1. Final native usage and
modelUsage agree: 100 ordinary input + 45,916 cache creation + 199,027 cache reads
+ 5,449 output = 250,492 tokens. Thinking 2,742 is an output subset. Intermediate
assistant-message output fields were provisional and do not replace final usage.

Project-status snapshots are byte-identical. Automatic hooks and caches still
write their scoped state; the broader model-generated statement that no memory
changed is unsupported. Codex stderr contains nonfatal keyring/OAuth warnings.
RTK project history changed from 2,337 to 2,371 estimated tokens across 58 to 60
commands; the shared scope does not establish exclusive or provider savings.

Context Mode returned text mixes inconsistent conversation scopes: Codex reports
616 KB / 24.4 KB alongside a 1.7 MB narrative; Claude reports 20.1 KB / 657 B
alongside an 869 KB narrative. Preserve the originals and do not derive precise
new-session/lifetime savings from those combined fields.

Historical lifecycle checks corroborate a bounded native writing-child recovery,
orderly disposable Ubuntu guest reboot and synthetic off-host application-state
restore. Worker artifact hashes match and the action sequence is checkpoint,
cancel-wait, crash-wait, finalize with execution_count 1. Guest boot IDs change
while disk/filesystem/machine/run/checkpoint/claim persist and effects change
0 to 1. Native journal completion occurred at 91.15 seconds before first SSH at
93.39 seconds. Eleven Qdrant source/destination payloads match; retained stdout
shows four ai-memory backup, six restore and four Qdrant upstream cases passing.

These receipts do not establish production/cloud application hosting, physical
power-loss recovery, lost-account/key recovery, cross-application atomicity,
native-client rebinding, remote-provider cancellation/billing, Beads recovery,
outer Codex-for-Claude invocation or interactive Claude HUD acceptance.

| Reviewed original | SHA-256 |
| --- | --- |
| Codex native stream | 81a6953c11b1a38fa311ebc29705c2d48507b9cb807386bd46f8c33ec0c00f6b |
| Claude native stream | c5f040649046979b231d966a852fbb6e2b6274c9eac602ac23b3cc798e1ce744 |
| Codex extracted results | 9b5e07f65d51096aa74d2249df8d0f01068a0214b821e6ead2db62373f6f4c37 |
| Claude extracted results | 9460c51715cf5eff39beb6b266774e17f4fe7ceeb3bac73d1a45bd80ce7cc9db |
| Before and after project status | ffc35eaff427850a401788fce2c6a641c3fa9b21179263aeb6890a7960f3b233 |
| Original bootstrap source | 1e7f1f11bfb04b3d5ad566145a754d659ccd18ecd817d6c8858bc4b86c2e1a55 |
| Original validation document | e5eac94b42570e08c2b25fee3fc764f8cfd667ddeef5e3221d1bcb5116bf977b |
| Worker exact-read receipt | 77e865d9c9618ae1fea0ed68dbe172136131ec8a681bf384df3906f4d184e40d |
| Guest journal excerpts | 9b7d23c1e25ccb910fe9ea0877a0ea27fb603ca7a4cbcfd10c500e2e405fc7b4 |
| Restored memory-query facts | db753997796c6d3edc01c79230213a5f1a235be4c743a0c81dd6069956be0c5a |

## Upgrade and presentation review

A worker independent of the OpenResearch/Worktrunk installer inspected original
release checksum pairs, archive members, installed and previous binaries, source
pins, test output and final Git state. No actionable findings remained. The
owned fixture was clean with one main worktree and branch; the removed directory
was absent. The old/new child-directory observation and seven unchanged Node
tests matched the public record. Rust tests remain explicitly unrun. The
[review result](upgrade-independent-review.json) binds the original public
upgrade receipt by hash; later attachment does not represent another execution.

An independent code review inspected the public builder/template change in
commit `1234855`, then rendered that committed code twice against the current
data without modifying files. Both renders were identical; all 76 then-current
component/receipt associations and 32 embedded artifacts reconstructed exactly,
including ten PNGs. The coordinator's later current-document URL additions and
additional evidence are covered by final repository checks and browser tests.
This is local presentation verification, not an upstream vendor test suite.

Documentation review found stale README counts and old recipe entry-point pins,
plus candidate command paths missing after non-global npm installation. Those
findings were corrected before publication. The live HUD remains unverified;
its unsuccessful native attempts are retained separately.
