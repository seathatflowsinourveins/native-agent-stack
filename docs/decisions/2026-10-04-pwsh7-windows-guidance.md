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

The two changed regression cases passed (2 tests, exit 0), and the final
recipe/document-consistency run passed (139 tests, 1 skip, exit 0). The required combined suite
ran 342 tests with 6 failures and 9 skips (exit 1): the existing ledger-path
guard rejects temporary fixture paths inside any Git worktree. The requested
sibling temporary directory is outside this job's writable roots, so the
temporary files were confined to the owned worktree instead. The classifier
was verified without changing its implementation or that guard.

The related modules ran 324 tests with 2 failures (exit 1). The unchanged
Windows Terminal notification test finds `auth_storage_failure` in the native
Codex schema without a decision in its existing map. The handbook check
detects the changed recipe's source hash. Regenerating the handbook would
also require changing its binding dated receipt under
`evidence/artifacts/new-wsl-handbook-20261001/`; this job preserves dated
evidence, so those files remain unchanged and that failure remains explicit.

Publication validation initially rejected personal workspace paths in two
captured test logs. Redacted those paths and retained the sanitized output;
the repeat `python3 scripts/validate.py` passed (exit 0).
`python3 scripts/build_ecosystem.py --check` and `git diff --check` also passed
(exit 0). These checks do not close the failed suite conditions above.
