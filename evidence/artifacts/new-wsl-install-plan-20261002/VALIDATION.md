# Install-plan validation

The sections are kept in the order they were written. The first two describe the 64-row revision and its clean run, and their counts are that revision's. The plan now has 70 rows: the section "Rows added from the layer consensus" covers the five added afterwards, whose two install commands and two acceptance checks have not run anywhere; the section "The two local-model rows" covers the two rows that became installable on 2026-10-03, whose commands and checks have not run as plan rows anywhere either; and the section "Wave 2" covers the wave-2 batch's interim installs, its added `statusline` row and its revised rows, whose commands and checks have not run anywhere.

## Revision to the merged manifest, after the real-distribution run

### Evidence class

The result below is one run on one host: a throwaway Ubuntu 26.04.1 distribution on WSL 3.0.1, on 2026-10-02, executing this plan as it stood before this revision (branch `foundation/new-wsl-install-plan-20261002`, commit `bf5a08e2`). The coordinator recorded it in a findings note kept outside the repository. It is a historical host execution of the previous revision. It says nothing about the commands this revision changed or added. When this section was written they had not run on a distribution; their run in a throwaway distribution since then is the section "Clean run of this revision" below, and their one run on the destination distribution is named in that section, after its list of results. The round 1 container run below is a separate, earlier class of evidence.

### Result of that run

- Install: 42 owners exit 0; `codex` 143 (finding 1); `trail-of-bits-security-skills-trailofbits-skills` 1 (finding 2).
- `post_install` acceptance: 39 exit 0, 12 skipped (excluded or no host install), worktrunk 1 and convergence-validators 2 (finding 3). After the three repairs, applied by hand on that host: 41 of 41.
- The four owners the container could not show (Dagu, Harbor, sandbox-runtime, worktrunk) pass on the real distribution.
- `service_health`: container-engine, Dagu (port 21080) and Phoenix (21606, 21617) pass because the install starts them. The gateway, Grafana, Loki, the OTel collector, Prometheus and the research harnesses return curl's 28 and the local model server 1, because the install does not start their services.
- The 21xxx port band does not collide with the host's listeners in the shared network namespace.

### Findings and what changed

1. The `codex` slot hung for ten minutes: the native installer asks "Start Codex now? [y/N]" on /dev/tty when a terminal exists, and a WSL launch has a pty (the container run had none). The installer documents `CODEX_NON_INTERACTIVE` ("Set to 1, true, or yes to skip prompts"). **Changed:** the line is now `curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh`. On the host, with the variable set, no prompt appeared and the installer exited 0 (Codex 0.160.0), which is finding 4.
2. `claude plugin marketplace add trailofbits/skills@<commit>` failed twice over: the shorthand clones over SSH ("No ED25519 host key is known for github.com"), and `@<ref>`, like `#<ref>`, is a branch or tag, not a commit ("Remote branch <sha> not found"); the repository has no tags. `claude plugin marketplace add https://github.com/trailofbits/skills.git` works. **Changed:** that line, unpinned. The acceptance prints `git -C "$HOME/.claude/plugins/marketplaces/trailofbits" rev-parse HEAD` beside the reviewed commit `82fe8226252622fa807643bdca1710901198553a` and fails when they differ (the head was `82fe8226` on the day of the run). The Codex line, `codex plugin marketplace add trailofbits/skills --ref <commit>`, worked as written and is unchanged.
3. The acceptance checks of worktrunk and the convergence validators change into `repo_root`; from a copy outside a checkout they failed, and from the clone both exit 0. **Changed:** the README says first that the plan runs from a checkout (recipe step F7), and both scripts stop with a clear message when `repo_root` is not a git checkout (`install.sh --list` needs none).

### Rows

The inventory is the merged manifest's 64 foundation rows (the previous revision had 53 owner rows, 46 of them selected): 36 installed by default, three measurement-only (Loki, Grafana, Playwright CLI) and 25 not installed. Trafilatura, ccusage, Phoenix, Promptfoo, chezmoi, Claude Code Action, CodeQL SARIF, trufflehog, the LSP plugins, the structural-diff row, attest and Dependabot left the installed set; ast-grep, Alertmanager and mattpocock/skills joined it, and GPT Researcher and DeerFlow became one row. The round 1 table below keeps its rows for owners that left the plan: it records what that run did.

### Static checks run for this revision, before its clean run

All static; none installs anything, and in these checks `install.sh` and `accept.sh` were not run except `install.sh --list`. Their run on a distribution is the next section.

- `bash -n` on `install.sh` and on `accept.sh`: exit 0 each.
- `bash install.sh --list`: exit 0, 64 lines.
- `python3 -B check_plan.py`: exit 0, "OK: 64 rows: 36 installed by default, 3 measurement-only, 25 not installed; 65 commands and 55 acceptance entries agree with the scripts".
- Python `json.load` of the four JSON files of this folder: exit 0.
- `check_plan.py` against defects planted one at a time in scratch copies (our own mutations, not an upstream test): deleting the `serena` install function, adding an unknown mise tool and giving two rows one port each exit 1 and name the problem; so do an orphan function for an excluded row, a drifting install command, a dropped `--list` line, a split row marked installed, a `run_command` without a source comment, a missing post-install acceptance, a removed row, a stray config file, a command without a source URL, a `not_installed` row marked installed and a drifting acceptance command. The unmodified copy exits 0.
- `python3 -B scripts/validate.py`: exit 1; it reports only that the changed files differ from the hashes registered in `manifests/evidence.json`, that `check_plan.py` and `config/alertmanager.yaml` are not hash-listed and that `config/phoenix-compose.yaml` is gone, all to be re-registered by the coordinator.

Observations from upstream release archives run in a scratch directory (Alertmanager's `amtool check-config` on `config/alertmanager.yaml`, its readiness endpoint, the ast-grep probe) and fixtures for the skills and Trail of Bits acceptance programs are described in [SOURCES.md](SOURCES.md), last section; they are not acceptance.

## Clean run of this revision on a real distribution (2026-10-02T12:54Z to 13:17Z)

Record: [real-distribution-validation.json](real-distribution-validation.json), built by a script from the
coordinator's private raw outputs (counts, exit codes and the raw files' hashes only).

Evidence class: native execution on one host, in a throwaway Ubuntu 26.04.1 distribution on WSL 3.0.1.0 created by the
merged new-distribution recipe (main `3a8dc31a`), with the plan run from a clone of this branch inside it. No sign-in,
no provider call, no model run. The distribution was removed afterwards.

- Stage 1 and first boot of the recipe passed (P1 to P3, W1 to W5, W7, F1 to F5), with the two-distribution proof.
- Install at `b48321ea`, counted in result lines, one per owner that `install.sh` handles as a slot: 38 lines, 35
  exit 0 and the three measurement-only owners reported as skipped; none failed. Two of the 35 run no install
  command and print the repository recipe (`credential-guard`, `convergence-validators`). `mise`, the 36th default
  owner, is installed by the script's first step, which prints no result line.
- Post-install acceptance at `b48321ea`, first pass, counted in result lines, one per plan row (64): 34 exit 0, 29
  skipped and one exit 1 (`engineering-process-skills`). The 29 are the 25 rows that are not installed, the three
  measurement-only owners and `credential-guard`, which has no host-executable check. The check failed because
  the lock that this run returned had no `ref` field; the installer at v1.7.0 supports that field as an optional
  branch or tag, and why it was absent here is unresolved. Each of the six skills' recorded `skillFolderHash` equals
  the git tree hash of its folder at tag `v1.2.3` and differs from main's.
- Post-install acceptance at `1b290218`, final: the acceptance now compares those recorded hashes with the expected
  ones; it does not hash the installed directories, and it says nothing about a client loading a skill. `accept.sh --only
  engineering-process-skills` returned exit 0, and one full `accept.sh` run returned 35 exit 0 and 29 skipped. Of
  that full run only the counts were kept, not its per-owner lines, so the record's `per_owner` table is the first
  pass and still shows this owner's failure; `per_owner_final` holds the one line that was kept.
- Service health: Docker and Dagu pass as installed; the OTel collector, Prometheus, Alertmanager and Ollama pass after
  being started with the commands in [SOURCES.md](SOURCES.md) on ports 21317, 21318, 21333, 21888, 21090, 21093 and
  21434. The gateway and the research harnesses were not started.
- The plan's port band did not collide with the workstation's listeners in the shared network namespace, and no 21xxx
  listener was left after the distribution was removed.

Not established by this run: a signed-in client, a pulled or running model, the GPU, the gateway and the research
harnesses as services, the three measurement-only owners, and a distribution that stays. Later on 2026-10-02 the plan
at this revision, as merged to main (`6652b78e`), ran once on the destination distribution, the one meant to stay. The
record of that run is private, its public receipt comes with that distribution's acceptance, and this file records no
result of it.

The record binds each phase to the commit that ran and to the SHA-256 of each plan file at that commit
(`executed_files`). After both commits had run, the header comments of `install.sh` (lines 2 and 3) and of
`accept.sh` (line 2) and the `status` text of `install-plan.json` were corrected, because they still said that this
revision was unrun. No command, row or check changed and the corrected files were not run again in a throwaway
distribution, so the files merged to main (`6652b78e`) differ from the executed ones in those lines only; those merged
files are the revision that ran once on the destination distribution. The raw outputs behind the record are private
files; the record carries their hashes, and no reviewer has inspected them.

## Rows added from the layer consensus (2026-10-02): static checks only

### Evidence class

Static checks of the plan's files and synthetic fixtures, on the workstation that holds the checkout. Nothing was
installed, no installer command ran, no client loaded a skill and no distribution was used. Three read-only GitHub API
reads supplied the tree hashes and the installer's source lines ([SOURCES.md](SOURCES.md), last section).

The clean run above was made before these rows existed. Its record binds the files it executed by hash; `install.sh`,
`accept.sh`, `install-plan.json` and `owners.json` have changed since, in more than their header lines, so the record
describes the earlier files. No result of that run, of the previous revision's run or of round 1 applies to the rows
below.

### What changed

Five rows, from the definitive manifest's five rows of kind `consensus`: 69 rows, 38 installed by default, three
measurement-only and 28 not installed.

- `skill-discovery` and `skill-authoring` install one skill folder each through the `skills` installer at 1.7.0, each
  pinned to the commit in the consensus record. Both have one install command and one `post_install` check.
- `research-skill`, `credential-custody` and `cross-family-review` are not installed: no command, no acceptance, no
  function in either script, and the gate or measurement from the record in `notes`.

### Checks run

- `python3 -B check_plan.py`: exit 0, "OK: 69 rows: 38 installed by default, 3 measurement-only, 28 not installed; 67
  commands and 57 acceptance entries agree with the scripts".
- `bash -n` on `install.sh` and on `accept.sh`: exit 0 each.
- `bash install.sh --list`: exit 0, 69 lines.
- Python `json.loads` of `install-plan.json` and `owners.json`: exit 0; both files equal their own re-serialisation.
- `check_plan.py` against defects planted one at a time in scratch copies (our own mutations, not an upstream test):
  deleting the `skill-discovery` install function, dropping `--copy` from the `skill-authoring` command in `install.sh`
  only, dropping the `cross-family-review` line from `--list`, marking `research-skill` installed, adding an acceptance
  function for `credential-custody`, dropping the shared-copy line from the `skill-authoring` acceptance in the JSON
  only, dropping `credential-custody` from the skipped-slot loop and removing `skill-discovery` from `owners.json` each
  exit 1 and name the problem. The unmodified copy exits 0.
- The two new acceptance programs against stand-ins (a stub `npx` that prints a canned `list --json` output, a canned
  lock file and a scratch `HOME`; our own fixtures, with jq 1.7): the matching case exits 0 for both. A missing agent,
  another tree hash and an absent skill each exit 1 for `skill-discovery`. Another tree hash, a listing without Claude
  Code and a `skill-creator` folder under `$HOME/.agents/skills` each exit 1 for `skill-authoring`; another skill in
  that shared directory does not fail it.
- Then the `skill-authoring` acceptance was tightened, and its stand-ins became a committed test. The program also fails
  on `skill-creator` in Codex's own global skills directory, `${CODEX_HOME:-$HOME/.codex}/skills` (the installer's
  README, line 298), counts a dangling symbolic link as a copy in either directory, and requires the installer's
  listing, now run without an agent filter, to name Claude Code as the only agent of `skill-creator`; Codex's embedded
  skills under `skills/.system` are left alone. Both directories are tested in one `[[ ]]` as the program's last
  command, so that its status is the program's on bash before 4.1 too (macOS `/bin/bash` is 3.2), where a failing
  `[[ ]]` does not stop a `set -e` script (bash NEWS, bash-4.1, item j). The class `SkillAuthoringAcceptance` in
  `tests/test_new_wsl_definitive_defaults.py` checks that its program is the one `accept.sh` runs and runs it as
  `accept.sh` does, with a stub `npx` that records its arguments and prints a canned listing, a canned lock file and a
  scratch `HOME` (our own fixtures, with jq 1.7 on the workstation). The expected state exits 0, with another skill in
  the shared directory and Codex's embedded copy present, and the stub receives the unfiltered `list -g --json`. Each
  condition planted on its own exits 1: a listing that also names Codex, names Codex alone or lacks the skill, another
  tree hash, a folder or a dangling link in either directory, and a folder under a set `CODEX_HOME`. Each planted
  folder or link also exits 1 with `-e` taken away; the earlier form, one `[[ ]]` per directory, exited 0 there for
  both shared-directory cases (bash 5.2; no bash before 4.1 was run). Removing any one condition from the program,
  in a scratch run of the test, made its planted case pass. The stub does not exercise the installer's own listing
  logic.
- `python3 -B scripts/validate.py`: exit 1; for this folder it reports only that the seven changed files differ from
  the hashes and byte counts registered in `manifests/evidence.json`, to be re-registered by the coordinator.

### Not established

- That either install command works. The commit after `#` relies on the installer's fallback from a branch clone to a
  fetch of the commit, which is read from its source and has never run under this plan.
- That the installer records the folder's git tree hash in its lock file for an install pinned to a commit, and that
  its listing shows the agents as the acceptance expects. The clean run showed both for `engineering-process-skills`,
  which is pinned to a tag and installed for two agents.
- That `--copy` with one agent leaves `$HOME/.agents/skills` without a `skill-creator` folder, and that the installer's
  unfiltered listing then names Claude Code alone for it. Both are read from the installer's bundled code
  (`installSkillForAgent`, `listInstalledSkills`).
- That the embedded Codex `skill-creator` is available on the destination, and that any client loads or usefully
  invokes either skill. Those are open gates of the consensus record.
- Anything on the destination distribution for these rows. The plan's one run there was the 64-row revision (main
  `6652b78e`), whose record is private and whose public receipt comes with that distribution's acceptance; it did not
  include these rows, and none of the five has run there or anywhere else.

## The two local-model rows (2026-10-03): static checks only

### Evidence class

Static checks of the plan's files, our own mutations and synthetic fixtures, on the workstation that holds the checkout.
No command of either row ran, no model was created, no model server was started and no distribution was used. Reads:
the registry's manifest for `qwen3-embedding:0.6b`, the Hugging Face Hub's model information and model-card files, and
Ollama's sources at v0.35.0 ([SOURCES.md](SOURCES.md), section "The two local-model rows").

The measurement that settled the two rows (`evidence/artifacts/new-wsl-local-models-20261002/`) created and ran the
same models in a throwaway distribution, from the same file and library digest, by its own scripts. That is evidence for
the systems measured; it is not a run of these plan rows' commands.

### What changed

69 rows: 40 installed (38 by the default run and two only when named), three measurement-only and 26 not installed.

- `local-generation-model` has four commands (the GGUF at the pinned Hugging Face revision through `fetch_verified`
  with its sha256, the placement of the two Modelfiles from `models/`, two `ollama create`) and two checks (`post_install`
  on files, `service_health` through the server).
- `embedding-model` has three commands (`ollama pull`, the pinned manifest digest as `/api/tags` reports it, one
  `ollama create`) and the same two stages.
- Both install only with `--only`, after the model server answers, and `accept.sh` gates both the same way.
- `check_plan.py` checks the dispatch of such rows in both directions: a row that `install.sh` installs only when named
  fails when `accept.sh` checks it in the default run, and a row that `install.sh` installs in the default run fails
  when `accept.sh` skips it there.
- Two repairs after the pull request's review (2026-10-03). `model_server_answers` in `install.sh`, which both rows run
  before their first command, accepted any server that answered `ollama ls`; it now also stops the row unless
  `GET /api/version` reports `0.35.0`, the measured server. The `local-model-server` row's `after_sign_in` check failed
  every time in step F9, which runs that stage without any model row; it now prints `skipped`, which is not a pass,
  until the `embedding-model` row's model is in the store. Neither repair changes a command or an acceptance entry of
  `install-plan.json`.

### Checks run

- `python3 -B check_plan.py`: exit 0, "OK: 69 rows: 40 installed (38 by the default run, 2 only when named),
  3 measurement-only, 26 not installed; 74 commands and 61 acceptance entries agree with the scripts".
- `bash -n` on `install.sh` and on `accept.sh`: exit 0 each.
- `bash install.sh --list`: exit 0, 69 lines; both rows print as `model-server | planned`.
- Python `json.loads` of `install-plan.json` and `owners.json`: exit 0; both files equal their own re-serialisation
  (`owners.json` at indent 1 without a final newline, as before this change).
- `check_plan.py` against defects planted one at a time in scratch copies (our own mutations, not an upstream test):
  `accept.sh` checking `embedding-model` in the default run; `install.sh` installing `local-generation-model` in the
  default run; another GGUF sha256 in `install.sh` only; the server-wide context (`num_ctx` 64000) in the JSON's
  embedding check only; no `Source:` comment above the 64k `ollama create`; the `--list` line of `embedding-model`
  dropped; `owners.json` marking `local-generation-model` not installed; `local-generation-model` back in the
  skipped-slot loop; no acceptance function for `embedding-model`; no post-install check for `local-generation-model`
  in the JSON; and another owner for `embedding-model` than the manifest's default. Each exits 1 and names the problem.
  The unmodified copy exits 0. With the second dispatch check taken out of a scratch copy of the checker, the defect
  "`install.sh` installs `local-generation-model` in the default run" exited 0, which is why that check was added.
- The four acceptance programs against stand-ins: the committed class `LocalModelAcceptance` in
  `tests/test_new_wsl_definitive_defaults.py` checks that its programs are the ones `accept.sh` runs and runs them as
  `accept.sh` does (`bash -euo pipefail -c`), with stub `ollama` and `curl` programs that print canned answers, a
  scratch `HOME` and model store (our own fixtures, with jq on the workstation). The expected states exit 0. Each
  planted condition exits 1: another 64k Modelfile, another model layer and no created model (generation files);
  another library manifest and another derived layer (embedding files); another context, another quantization and an
  empty answer (generation service); the server-wide context and 512 dimensions (embedding service). Taking any one of
  the nine conditions out of its program, in a scratch run of the test, made its planted case pass.
- The `local-model-server` row's `after_sign_in` check, repaired on 2026-10-03: it ran upstream's example
  `ollama run embeddinggemma "Hello world"`, which would pull EmbeddingGemma, the embedding arm that lost; it is now one
  `/api/embed` call to `qwen3-embedding-8k` that must return one vector, and the endpoint downloads nothing
  (SOURCES.md, "The service checks"). `check_plan.py` exit 0 with the counts above (the entry was replaced, not added);
  `bash -n accept.sh` exit 0. `LocalModelAcceptance.test_the_server_smoke_check` checks that the program names the settled
  embedder and no other model and runs it against the stub `curl`: one vector exits 0, no vector and an error answer
  exit 1. With the `jq -e` condition taken out in a scratch run, the no-vector case exited 0.
- The two review repairs: `check_plan.py` exit 0 with the counts above (no command or acceptance entry changed) and
  `bash -n` exit 0 on both scripts. `LocalModelAcceptance.test_the_server_smoke_check_waits_for_the_embedding_row` runs
  `accept.sh --only local-model-server --stage after_sign_in` itself, with a scratch `HOME` and the stub `curl`: without
  the embedder's manifest in the store it prints `skipped` and exits 0; with it, one vector prints 0 and exits 0, and no
  vector prints 1 and exits 1. `ModelServerGuard` runs `model_server_answers`, read from `install.sh`, with stub
  `ollama` and `curl`: version 0.35.0 exits 0; version 0.36.0, an answer without a version, a failed version request and
  no server exit 1; and it checks that both rows run the guard before their first command. In scratch copies of this
  folder (our own mutations, not an upstream test), the gate taken out of `accept.sh`, the version condition taken out,
  the version written as a constant and `embedding-model`'s guard moved after its pull each failed its test; the
  unmodified copy passed.
- The `ollama show` table that the service checks read is rendered by a table writer with an empty first column and
  space padding (`cmd/cmd.go:1362-1368`, parameter rows at `:1474-1480`, at v0.35.0); the measurement's record of that
  output squeezes the spaces (`raw/M15-a2-setup.txt` in the private measurement folder, listed by sha256 in that
  evidence folder's `files.json`), so the stand-ins imitate the layout read from the source.
- The Swift Modelfile: `reconstruct_s2o_modelfile.py --check` exit 0, and with the measurement's own `FROM` line the
  rebuilt file hashes to the recorded `8911245e…` (SOURCES.md, section "The two local-model rows").

### Not established

- That any command of the two rows works as a plan row: the 11.8 GB download through `fetch_verified`, the placement,
  the two creates, the pull and the digest check have not run under this plan.
- That the models the rows create carry the manifest digests the measurement recorded. Those digests are in `notes`
  for comparison; no check reads them.
- That the checks read the real `ollama show` table and the real answers as the stand-ins do, and that the guard reads
  a real server's `/api/version` answer as it reads the stub's (the measurement's own calls returned `0.35.0`, SOURCES.md).
  The stubs do not exercise the server.
- That acceptance notices a server replaced after the rows were installed: the version guard runs when a row installs,
  and no acceptance check compares the running server's version.
- That the server reads the same model store as the user who runs the checks: the post-install checks read
  `${OLLAMA_MODELS:-$HOME/.ollama/models}` and assume the server runs as that user with the same `OLLAMA_MODELS`.
- GPU residency on the destination, and which distribution's model server holds the card. The measured co-residency
  held under the preregistration's condition N (no other WSL process holding GPU memory, the workstation's two model
  services stopped first); the README leaves GPU ownership to the lifecycle design.
- Anything on the destination distribution for these rows.

## Wave 2 (2026-10-03): static checks only

### Evidence class

Repository checks of the plan's files, run on the coordinating workstation from the branch's worktree; no command of the plan ran, nothing was installed and no distribution was touched. They show that the files agree with each other and with the manifest, not that an install or an acceptance check works.

### What changed

The wave-2 batch of the layer consensus made `memory-owner`, `code-search` and `context-supply` interim installs (amendment 3), added `statusline`, and revised `research-harnesses`, `tobi-qmd`, `gpt-gateway` and the three skills rows (README.md, section "Wave 2"; sources in SOURCES.md, section "Wave 2"). After the branch review of 2026-10-03: each interim row's install function calls `interim_acknowledged` first, and `check_plan.py` requires that; `memory-owner` runs ai-memory's own `install-hooks --agent codex --apply` once and checks its seven Codex events in `hooks.json`; `context-supply` checks that marketplace auto-update is off for context-mode. After the pull-request review of 2026-10-03: `statusline` runs upstream's helper (`scripts/setup.mjs inspect`, then `install --shell posix`), which copies the launcher that the configured status line runs, and adds `refreshInterval` 5 when absent; its acceptance runs the configured command instead of the cached launcher, which had passed with that copy missing. After the review of `99a2e3c6`: the acceptance takes any positive-integer `refreshInterval` (the settings schema's integer, minimum 1) instead of exactly 5, since the helper keeps an earlier claude-hud value and the install adds 5 only when absent; the exact-5 check had rejected such an installed configuration. After the review of `06f6259f` (macOS CI run 37141171758, at `2f5d8b01`): the acceptance's exact-one check of the cached versions compares the `wc -l` count as a number (`-eq 1`) instead of the string `1`, which the padded count of BSD and macOS `wc` failed; its other conditions are unchanged.

### Checks run

- `python3 -B check_plan.py`: exit 0, `OK: 70 rows: 42 installed by default, 3 measurement-only, 25 not installed; 87 commands and 62 acceptance entries agree with the scripts`.
- `bash -n install.sh` and `bash -n accept.sh`: exit 0.
- `tests/test_new_wsl_definitive_defaults.py`, class `InterimPlanChecks`: `check_plan.py` over a scratch copy of the plan fails, with its message, for an interim row set to `installed: false`, a plan owner that is not the interim's, an interim install function without the gate call first (each of the three rows) and a script without the gate function; the unchanged copy passes. The gate function itself, cut from `install.sh` and run with `bash` and `jq` against scratch `consensus.json` files, refuses while a family is owed, refuses a list it cannot read and passes an empty list; against the committed batch it refuses today, since both acknowledgements are owed.
- The `jq` filter of `memory-owner`'s new acceptance line, against two scratch `hooks.json` files: false (exit 1) when an event has no ai-memory command, true when each named event has one.
- `tests/test_new_wsl_definitive_defaults.py`, class `StatuslineInstallAndAcceptance` (our own fixtures: a scratch `HOME`, links to the system tools and a stand-in runtime; upstream's helper and launcher do not run): the helper command calls `setup.mjs inspect`, then `install`, with `--shell posix`, from the one cached 0.10.0, and refuses with no cached 0.10.0, with 0.10.0 in two marketplaces and with no `node` or `bun`; the `refreshInterval` command adds 5 only when absent, in the real file behind a link, with its mode kept; install, then the acceptance, on one scratch home (the helper's writes planted, then the helper and `refreshInterval` commands run): the acceptance passes the file the install leaves, with 5 added when absent and with an earlier 3 kept unchanged; the acceptance passes the wired state with a `refreshInterval` of 5, 1 or 3 and fails each planted condition: the copied launcher missing, a `refreshInterval` that is absent, non-numeric (`"five"`), quoted (`"5"`), zero, negative or fractional, another version's launcher copy, a second cached version, and a command that runs the cached launcher. Against the same missing-copy fixture, the acceptance as it was before the review exits 0. Negative control, kept as a test: in the install-then-acceptance run with an earlier 3, the acceptance as it was at `99a2e3c6` (exactly 5) exits 1; it exits 0 when the install added 5.
- After main at `54a96ff3d` (the two local-model rows, section above) was merged into this branch: `python3 -B check_plan.py`: exit 0, `OK: 70 rows: 44 installed (42 by the default run, 2 only when named), 3 measurement-only, 23 not installed; 94 commands and 66 acceptance entries agree with the scripts`; `bash -n` on `install.sh` and on `accept.sh`: exit 0 each.
- After the review of `06f6259f`: `python3 -B check_plan.py`: exit 0, the same summary line; `bash -n` on `install.sh` and on `accept.sh`: exit 0 each. `tests/test_new_wsl_definitive_defaults.py`, class `StatuslineInstallAndAcceptance`: with a stand-in `wc` that counts with the system one and prints the count either bare (GNU) or as `" %7d"` (BSD and macOS), the acceptance passes the wired state with a `refreshInterval` of 5, 1 or 3 in both formats and fails a second cached version in both. Negative control, kept as a test: the acceptance as it was at `06f6259f` (string `== 1`) exits 0 on the wired state with the bare count and nonzero with the padded one. No macOS host ran these; the padded format is the stand-in's.

### Not established

- Whether ai-memory 2.5.2's installer writes the seven events with commands that name `ai-memory`, as the acceptance expects: read in its source (SOURCES.md), not run.
- Whether claude-hud 0.10.0's helper, run through mise's `node` shim, records the runtime path the client configuration renders (`process.execPath`, setup.mjs line 32), and whether its launcher prints two lines on the destination: read in its source, not run.
- Anything about a client: no Claude Code or Codex session ran, no hook was trusted and no marketplace was added.

## Wave 3 (2026-10-04): static checks and artifact checks only

### Evidence class

Repository checks of the plan's files, plus artifact checks in a scratch folder on the coordinating workstation (NativeStack), from the branch's worktree. No install command of the plan ran, nothing was installed on any host and no distribution was touched. The artifact checks show that the recorded downloads are the published ones and that four version checks hold against those archives' own binaries, not that an install or an acceptance check works on the destination.

### What changed

The wave-3 batch of the layer consensus, on the owner's decision of 2026-10-04 (amendment 4), added ten owner rows in token-efficiency, gave `ccusage`, `session-analytics` and `context-supply` owner defaults, and widened the `code-search` interim to semble and SocratiCode (README.md, section "Wave 3"; sources in SOURCES.md, section "Wave 3"). `interim_acknowledged` reads every wave batch; `context-supply` no longer calls it; `check_plan.py` refuses a gate call on a row without an interim.

### Checks run

- `python3 -B check_plan.py`: exit 0, `OK: 80 rows: 56 installed (54 by the default run, 2 only when named), 3 measurement-only, 21 not installed; 115 commands and 78 acceptance entries agree with the scripts`.
- `bash -n install.sh` and `bash -n accept.sh`: exit 0 each; `bash -n -c` on every command and acceptance program of the new and changed rows: exit 0 each. `bash install.sh --list`: exit 0, 80 lines, 21 of them `excluded` (`ccusage` and `session-analytics` no longer).
- Downloads, 2026-10-04: the four release archives (RTK 0.50.0, codebase-memory-mcp 0.11.0, otel-tui 0.7.5, agentsview 0.43.0) and the five npm tarballs (Repomix 1.18.1, TOON 4.1.1, Context Hub 0.1.4, ccusage 20.0.26, SocratiCode 1.15.0), fetched into a scratch folder: each matched the sha256 the plan records. The agentsview digest also equals the GitHub asset digest of its release (API, read 2026-10-04). Each archive's member list is the one the rows' notes give.
- Version checks against the archives' binaries, with a scratch `HOME`: `rtk --version` printed `rtk 0.50.0`, `codebase-memory-mcp --version` `codebase-memory-mcp 0.11.0`, `otel-tui --version` `otel-tui version 0.7.5` and `agentsview --version` `agentsview v0.43.0 (commit 9be7745ad1906ee24e04eb05bb86c872ef0939a1, ...)`, exit 0 each. The four acceptance programs of `command-output`, `code-graph`, `trace-viewer` and `session-analytics`, run with `ECO_ROOT` on a scratch folder whose `bin` links to those binaries: exit 0 each; the `command-output` program with an expected version of 0.51.0: exit 1 (negative control). The extraction command of each of the four rows, run with the downloaded archive in a scratch `ECO_ROOT`: exit 0, the link points into the versioned prefix; with an archive that lacks the binary: exit 1 and no link.
- `tests/test_new_wsl_definitive_defaults.py`, class `InterimPlanChecks`: the gate function, cut from `install.sh` and run with `bash` and `jq` against scratch `consensus.json` files, refuses while any wave batch owes an acknowledgement (naming each batch), passes when none does, and refuses a batch that cannot be read, a key that starts with `wave` and is not `wave<n>`, and a missing file; `check_plan.py` refuses a gate call put on `context-supply` or on an owner row.

### Not established

- Any install: no `fetch_verified`, `npm install`, `uv tool install` or extraction into a real ecosystem root ran, and the npm and uv routes resolve dependencies at install time that no recorded digest pins.
- The acceptance programs of the npm and uv rows: their packages were not installed here, so their version lines and probes are read in the packages' sources (SOURCES.md), not run.
- Anything about a client: no MCP server was registered or started, no hook was written, and SocratiCode has no Qdrant store or embedding endpoint on the destination.

## Round 1 install-plan repair (historical)

The coordinator ran 34 slots as uid 1000 in a disposable `ubuntu:26.04` container (Ubuntu 26.04.1 LTS), with passwordless sudo, no systemd/user bus, no bubblewrap user namespaces, no service started by the validation procedure and no sign-in. The repository was read-only at `/repo`; the mounted worktree's Git metadata was outside the container. This file quotes only nonprivate evidence. Log locations below are relative to the supplied read-only `round1/` results directory.

Results: 16 passed both checks; 18 failed. Cause counts among failing slots: **5 plan defects, 5 checks needing a running service, 4 checks needing sign-in/provider configuration, 4 container limits**. Mise, chezmoi and Codex acceptance logs retain only exit 1 because the old runner suppressed stdout. Their assignments use the recorded fresh-host conditions plus the pinned upstream implementations; the exact diagnostic rows are unknown. These are source-supported explanations, not reconstructed output or a claim of successful retesting.

In the result column, `I/A` means aggregate install/accept exit codes from `results.tsv`. A command's own status can differ: Git reports 78 inside an aggregate install exit 1; curl health commands report 7 inside acceptance exit 1; Harbor reports successful owner installation before the Docker dependency fails. Each quoted log location names the actual line carrying evidence. Sources for changes and retained checks are in [SOURCES.md](SOURCES.md#round-1-repairs-and-staged-acceptance) and each JSON check's `source`.

| slot | round 1 result | cause class | what changed |
| --- | --- | --- | --- |
| mise | I/A 0/1; `mise.accept.log:1`: `mise \| smoke \| 1`; install log:83 recommends doctor | plan defect | Keep full doctor with mise shims on this process's PATH, in the owned global tool directory so the optional inventory manifest is not selected. The original runner used `mise env`, which does not supply activation or the required shims. Exact original doctor failure row was suppressed. Pins stay unchanged. |
| git | I/A 1/skipped; `git.install.log:1` says no suitable route; :2 reports install 78. `mise.install.log:11`: Git is already Ubuntu's `1:2.53.0-1ubuntu1` package | plan defect | Declare `apt` and idempotently install Ubuntu's own Git package. Remove the exit-78 refusal and add `git --version`. Do not claim the upstream v2.56.0 pin was installed. |
| claude-code | I/A 0/0 | passed | Retain the documented local doctor as post-install. |
| codex | I/A 0/1; `codex.accept.log:1`: `codex \| smoke \| 1`; install log:27 records 0.160.0 | check needs a sign-in or a provider | Use version at post-install; retain full doctor after sign-in. Pinned doctor marks missing credentials FAIL. Doctor is a valid command; the exact original failing rows are unknown. |
| gh-github-cli | I/A 0/0 | passed | Retain version at post-install. |
| betterleaks | I/A 0/0 | passed | Retain the directory scan at post-install. |
| zizmor | I/A 0/0 | passed | Retain the documented local check at post-install. |
| syft | I/A 0/0 | passed | Retain the upstream image smoke at post-install. It uses network access but no sign-in. |
| actionlint-kjanat | I/A 0/0 | passed | Retain version at post-install. |
| worktrunk | I/A 0/1; `worktrunk.accept.log:1`: `git rev-parse --git-common-dir failed (exit 128)`; :2 says the Git directory is not a repository | container limit | Retain `wt list` in the real checkout as post-install. The read-only worktree mount omitted its Git metadata; do not replace this smoke with a version check. |
| difftastic | I/A 0/0 | passed | Retain version at post-install. |
| restic | I/A 0/0 | passed | Retain version at post-install. |
| chezmoi | I/A 0/1; `chezmoi.accept.log:1`: `chezmoi \| smoke \| 1`; install log:41 records package 2.73.0 | plan defect | Retain the full doctor, using its documented config/source/destination/working-tree flags and fresh owned directories. Upstream makes nonexistent directories an error. Keep all diagnostics, including network/version checks. Exact original row was suppressed. |
| mcporter | I/A 0/0 | passed | Retain local MCP inventory at post-install. |
| sandbox-runtime-srt | I/A 0/1; `sandbox-runtime-srt.accept.log:1`: `bwrap: No permissions to create a new namespace` | container limit | Retain the actual `srt echo` smoke at post-install. No namespace bypass or unsandboxed replacement. |
| tobi-qmd | I/A 0/0 | passed | Retain status at post-install. |
| playwright-cli | I/A 0/1; `playwright-cli.accept.log:6`: `Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome`; install log:658 confirms bundled Chromium build 1247 | plan defect | Install Chromium through the pinned CLI's own `install-browser --with-deps chromium`; explicitly pass `--browser=chromium` to the real open/close smoke. The previous Playwright dependency version was correct. |
| ccusage | I/A 0/0 | passed | Retain daily usage smoke at post-install. |
| promptfoo | I/A 0/0 | passed | Retain version at post-install. |
| gpt-gateway | I/A 0/1; `gpt-gateway.accept.log:2`: `error: unknown option '--json'`; :9 advertises `--no-liveness` | plan defect | Replace the incorrect subcommand flag with global `--output json`. Use upstream doctor `--no-liveness` at post-install. Service-health requires upstream `/readyz` success before full doctor, which otherwise only warns about an unreachable service. |
| serena | I/A 0/0 | passed | Retain upstream init in its owned acceptance directory at post-install. |
| trafilatura | I/A 0/0 | passed | Retain upstream URL extraction at post-install. It uses network access but no sign-in. |
| inspect-ai | I/A 0/0 | passed | Retain version at post-install. |
| harbor-containerized-agent-e2e-runner | I/A 1/skipped; `harbor-containerized-agent-e2e-runner.install.log:342–343`: three executables installed and owner install 0; :497–505 requests missing `nf_tables`/`modprobe`; :508–509 reports Docker failure and refusal | container limit | Keep the Harbor pin/uv route and its version check. Preserve the real rootless Docker prerequisite gate; this was a later dependency failure, not a Harbor resolver failure. |
| claude-agent-sdk | I/A 0/1; `claude-agent-sdk.accept.log:44`: `Not logged in · Please run /login` | check needs a sign-in or a provider | Report the SDK's public version at post-install; retain the original query after native/provider sign-in. |
| codex-sdk-and-codex-exec-app-server | I/A 0/1; `codex-sdk-and-codex-exec-app-server.accept.log:5`: `401 Unauthorized: Missing bearer or basic authentication in header` | check needs a sign-in or a provider | Check the installed local npm package version at post-install; retain the original SDK model call after authentication. |
| agent-runtime-worker | I/A 0/1; `agent-runtime-worker.accept.log:54`: `401 Unauthorized`; :95 records `invalid_api_key` | check needs a sign-in or a provider | Report both OpenHands package versions at post-install; retain the original hello-world agent example after provider configuration. |
| otel-collector-contrib | I/A 0/1; `otel-collector-contrib.accept.log:1`: curl could not connect on 21333; :2 reports health 7 | check needs a running service | Use upstream `validate --config` at post-install; retain the original health endpoint in service-health. |
| prometheus | I/A 0/1; `prometheus.accept.log:1`: curl could not connect on 21090; :2 reports health 7 | check needs a running service | Use the extracted upstream `promtool check config` at post-install; retain `/-/ready` in service-health. |
| loki | I/A 0/1; `loki.accept.log:1`: curl could not connect on 21300; :2 reports health 7 | check needs a running service | Use upstream `-verify-config=true` at post-install; retain `/ready` in service-health. |
| grafana | I/A 0/1; `grafana.accept.log:1`: curl could not connect on 21301; :2 reports health 7 | check needs a running service | Use documented `grafana cli -v` at post-install; retain `/api/health` in service-health. |
| dagu | I/A 1/skipped; `dagu.install.log:35`: `Failed to connect to user scope bus via local transport` because its session/runtime variables were not defined | container limit | Retain the upstream user-service installer. Add native `dagu version` at post-install; keep health after the real user service starts. No switch to another service scope. |
| local-model-server | I/A 0/1; `local-model-server.accept.log:1`: `could not connect to ollama server, run 'ollama serve' to start it` | check needs a running service | Use client version at post-install, model inventory in service-health and the original model smoke after provisioning its local model route. The model smoke remains unverified after connection. |
| mineru | I/A 0/0 | passed | Retain upstream local CLI check at post-install. |

The container cannot establish these conditions; check them on the real distribution:

- Systemd user sessions, Dagu startup and rootless Docker's kernel/network/user-unit prerequisites, restart and persistence.
- Bubblewrap namespace/permission support and the real sandbox smoke; browser smoke after selecting the installed Chromium.
- Worktrunk against a checkout with accessible Git/worktree metadata.
- Running service readiness at the recorded loopback endpoints, including Docker runtime smoke and Compose image/app readiness.
- Native sign-ins, configured model/search providers, local model provisioning, inference and WSL GPU passthrough.

Unresolved evidence limits: the suppressed original mise/chezmoi/Codex diagnostic rows cannot be recovered from these logs. Five workflow/adoption rows have no source-backed host executable check, so their explicit unavailable entries are skipped. Neither a skip, source review, configuration validation nor a version proves provider/GPU/service acceptance. All revised target-distribution commands remain unrun; no upstream failure was waived.

Historical: executed checks for the round 1 revision (the first plan, 53 rows; the current plan has 69 rows: the checks of its 64-row revision are in the first two sections above, and those of the five rows added from the layer consensus, which have not run anywhere, are in the third): the requested Python JSON load, `bash -n` on both scripts and `bash install.sh --list` all returned 0. The list retained all 53 rows. TOML parsing, stage/schema/source agreement, all 156 slot/stage combinations, default/all-owner stages, unavailable/excluded skips, nonzero failure propagation and invalid arguments passed local fixtures. Additional Bash fixtures caught the original caller-directory and doctor-only false-pass patterns and verified the repairs. All 16 passing acceptance objects, original model/research examples, original HTTP endpoints and all seven exclusions were compared with the original plan and retained. The entire plan folder passed a personal-path/user-name scan; `git diff --check` passed. The fixtures ran no native owner programs, stack services or models. Independent Astra/Max source review confirmed the two review fixes and reported no remaining follow-up findings.
