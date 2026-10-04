# PowerShell 7 for maintained Windows-side WSL guidance

Date: 2026-10-04. Lane: foundation. Scope: the maintained WSL platform pages
and their launcher/classification tests. North-star action: make Windows-side
WSL setup reproducible for the research and historical-simulation workstation.

Use the upstream PowerShell 7 executable directly for Windows-side `.ps1`
blocks. The WSL launcher is the quoted absolute MSI path
`'/mnt/c/Program Files/PowerShell/7/pwsh.exe'`, followed by `-NoProfile`,
`-NonInteractive`, `-ExecutionPolicy Bypass` and `-File "$(wslpath -w step.ps1)"`.
NativeStack disables `appendWindowsPath`, so a bare executable name is
insufficient. Each recipe requires PowerShell 7 on the Windows host and tells
the reader to stop and install it when that path is absent.

The documented command is
`winget install --id Microsoft.PowerShell --source winget --installer-type wix`.
Microsoft's default WinGet package since 7.6 is MSIX, so selecting MSI is
necessary for this recipe's fixed path. When WinGet is unavailable, follow
Microsoft's manual stable-MSI download and installer prompts, retaining the
default directory, and verify the executable path before resuming. A missing
PowerShell 7 installation does not select Windows PowerShell 5.1.

Primary sources checked on 2026-10-04:

- [PowerShell/PowerShell v7.6.6 release](https://github.com/PowerShell/PowerShell/releases/tag/v7.6.6):
  GitHub's `releases/latest` returned `v7.6.6`, published `2026-09-08T20:28:01Z`.
  Its annotated tag resolves to commit `f260eb9c31ec72c5282f98e5ea24d9be4f8d7536`.
- [The v7.6.6 command-line parser](https://github.com/PowerShell/PowerShell/blob/f260eb9c31ec72c5282f98e5ea24d9be4f8d7536/src/Microsoft.PowerShell.ConsoleHost/host/msh/CommandLineParameterParser.cs#L955-L968)
  accepts `-NoProfile` and `-NonInteractive`; [lines 1141–1148](https://github.com/PowerShell/PowerShell/blob/f260eb9c31ec72c5282f98e5ea24d9be4f8d7536/src/Microsoft.PowerShell.ConsoleHost/host/msh/CommandLineParameterParser.cs#L1141-L1148)
  select `-File`, and [lines 1592–1611](https://github.com/PowerShell/PowerShell/blob/f260eb9c31ec72c5282f98e5ea24d9be4f8d7536/src/Microsoft.PowerShell.ConsoleHost/host/msh/CommandLineParameterParser.cs#L1592-L1611)
  require redirected stdin for `-Command -`.
- [Microsoft's Windows install documentation](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.6),
  source `MicrosoftDocs/PowerShell-Docs@a3de8f22552170e70852470d46cd52cd9ca471ec`,
  `reference/docs-conceptual/install/install-powershell-on-windows.md`:
  [lines 57–71](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/docs-conceptual/install/install-powershell-on-windows.md#L57-L71)
  distinguish MSIX from the explicit WinGet MSI command;
  [lines 84–92](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/docs-conceptual/install/install-powershell-on-windows.md#L84-L92)
  document manual MSI installation;
  [lines 124–128](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/docs-conceptual/install/install-powershell-on-windows.md#L124-L128)
  establish the default versioned installation directory.
- [about_pwsh for PowerShell 7.6](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_pwsh?view=powershell-7.6),
  at the same documentation commit, `reference/7.6/Microsoft.PowerShell.Core/About/about_Pwsh.md`:
  [lines 61–70](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/7.6/Microsoft.PowerShell.Core/About/about_Pwsh.md#L61-L70)
  document `-File` and its ordering;
  [lines 167–194](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/7.6/Microsoft.PowerShell.Core/About/about_Pwsh.md#L167-L194)
  still document statement-by-statement stdin execution and skipped statements that fail parsing;
  [lines 361–366](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/7.6/Microsoft.PowerShell.Core/About/about_Pwsh.md#L361-L366)
  document noninteractive prompt errors. Retain the `.ps1` file advice.

| Alternative | Decision and comparison |
| --- | --- |
| PowerShell 7 MSI with a quoted absolute path | Adopt for the maintained guidance: matches the required path and Microsoft's supported installation and CLI. |
| Default WinGet/MSIX, Store or ZIP installation | Different packaging/locations need their own path qualification; do not assume they provide the required MSI executable path. |
| A bare executable name | Reject for WSL launchers: `appendWindowsPath` is disabled. |
| Windows PowerShell 5.1 or an automatic fallback | Reject for maintained launchers; retain intentional historical records and the legacy classifier fixture. |

Completeness critic: a case-insensitive search of the tracked tree found the
two maintained platform pages, two test modules and the seven historical
files named by this job. Launcher guards cover both executable names in
inline and `sh` commands, and the classifier already recognises `pwsh.exe`.
The packaging check found the MSIX default and added `--installer-type wix`.
The next Windows recipe sweep must review packaging and WSL interop together:
[Microsoft's lines 79–80](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/a3de8f22552170e70852470d46cd52cd9ca471ec/reference/docs-conceptual/install/install-powershell-on-windows.md#L79-L80)
announce that 7.7 has no MSI. A supported replacement with a qualified WSL
path, or a demonstrated PowerShell 7 incompatibility in these scripts, would
overturn the present installation/path choice.

Acceptance is repository integration checking, not upstream PowerShell tests
or a new Windows installation. The installed Windows executable was present,
but its native version probe exited 1 with `UtilBindVsockAnyPort: socket failed 1`
in this bounded environment. Host PowerShell 7.6.6 remains supplied context;
the release metadata and upstream sources above were independently read.

The coordinator's completed-head validation report for `91ec598e1` is
**LANDABLE** for repository integration.
The handbook and its receipt output digests were regenerated under the
[2026-10-01 generator contract](2026-10-01-new-wsl-handbook-generator.md).
The recipe, skill-usage, docs-consistency and handbook tests pass.
`python3 scripts/validate.py` passes (exit 0), and
`python3 scripts/build_ecosystem.py --check` passes (exit 0).
These results supersede the earlier attempts below; the native Windows probe
retains the limitation stated above. This repair independently reran both
validation commands against the unchanged incoming head, each with exit 0.

**Superseded attempt — combined suite:** the two changed regression cases
passed (2 tests, exit 0), and the recipe/document-consistency run passed
(139 tests, 1 skip, exit 0). The combined suite ran 342 tests with 6 failures
and 9 skips (exit 1): the ledger-path guard rejected temporary fixture paths
inside a Git worktree. The requested sibling temporary directory was outside
that attempt's writable roots, so its temporary files were confined to the
owned worktree. The classifier was verified without changing its implementation
or that guard.

**Superseded attempt — related modules:** 324 tests ran with 2 failures
(exit 1). The Windows Terminal notification test found `auth_storage_failure`
in the native Codex schema without a decision in its map, and the handbook
check detected the changed recipe's source hash. At that attempt, handbook
regeneration and the accompanying receipt digest update were deferred.
The completed head regenerated both under the existing generator contract.

**Superseded attempt — publication validation:** validation initially rejected
personal workspace paths in two captured test logs. Those paths were redacted
and the sanitized output retained; the repeat `python3 scripts/validate.py`
passed (exit 0). The ecosystem and diff checks also passed (exit 0).

The bounded review repair of 2026-10-04 independently recomputed the supplied
head's recipe SHA-256 as
`5c7995822a80f8ca5e006c24de67497f0f3d7a5809b02f74dfc852028597633d`
and test SHA-256 as
`a05c758abd049d8d5f50459b39b223ad0d96bd5960b2dccc50bfc1ab7d09e8f3`.
The convergence check reproduced exactly the two stale frozen-input pins
(exit 1). Following the recipe record's re-freezes in `ad7d645ba`,
`b8dd81ddc`, `3a8dc31a6`, `99d5b122c` and `ee4ece2e8`, the repair updates
`frozen_inputs.base_revision` to `91ec598e170db3257a72322a21b6f920ad5b6094`
and recomputes every affected pin from the final file bytes. The recipe now
labels the quote convention's PowerShell 5.1 origin as historical, and the
checklist includes the PowerShell 7 MSI executable prerequisite. Microsoft's
pinned installation source above was re-read for that prerequisite. The
supported handbook generator's `--write` command refreshed its outputs, and
their receipt digests were updated again for these recipe edits.

The repair's local rerun uses `TMPDIR=.bounded-job-029/tmp` throughout.
The explicit repaired convergence record passes (exit 0), the handbook check
passes (exit 0), and `git diff --check` passes (exit 0). The required
`--all-recorded --root . --json` check exits 1 at record discovery because the
coordinator's evidence registry still contains the prior JSON file hashes;
the registry is reserved for the coordinator's final commit. The combined
recipe, handbook, docs-consistency and skill-usage suite ran 414 tests with
6 failures and 9 skips (exit 1). All six failures are in the skill-usage
call-ledger cases: their temporary fixtures inherit this job's Git worktree,
while the ledger requires a path outside every Git worktree. Those environment
failures remain explicit and need a coordinator rerun with eligible fixture
paths. They are separate from the completed-head validation report above.

Repair completeness critic: the quote annotation and prerequisite tick also
affect the recipe and checklist hashes, so both join the unchanged test's
new pin in the convergence record. The generated handbook and its receipt
digests remain bound to those final inputs. The next Windows recipe lifecycle
sweep must retain the packaging and interop checks identified above. Native
Windows installation and host acceptance retain their separate evidence scope.
The coordinator re-registers the repaired files in `manifests/evidence.json`
last.
