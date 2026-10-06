# New WSL install plan

Current structural inventory (2026-10-05): 84 rows, 192 install commands and 113 acceptance entries (including two additional checks). The source includes 66 configuration assets. D-ollama-2 carries the updated owner-approved user unit and removes the warmup asset; #713 supplies the additional rows. These counts describe the source, not host acceptance.

**Run the plan from a checkout of the repository** (step F7, "Clone origin/main", of `adoption/platforms/linux-wsl2-new-distro.md`). `worktrunk` and the convergence validators change into `repo_root`, the checkout three levels above this folder, so `install.sh` and `accept.sh` stop with a clear message when `repo_root` is not a git checkout (`install.sh --list` needs none).

Revised to the merged definitive manifest (`evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`) and to what the plan did on a real distribution. The inventory has one row per foundation row of that manifest: 84 rows, of which 63 are installed (60 by the default run, two of them interim installs, which wait for the wave-2 acknowledgements: section "Wave 2" below; and three only when named with `--only <slot>`), two are measurement-only (installed only by `--only <slot>`, for the measurement that decides them) and 19 are not installed. [VALIDATION.md](VALIDATION.md) keeps three results apart: the round 1 container run of the first plan (historical), the run of the previous revision in a throwaway distribution, and the clean run of this revision in a fresh throwaway distribution on 2026-10-02 (12:54Z to 13:17Z), recorded in [real-distribution-validation.json](real-distribution-validation.json). Both distribution runs were on one host, in distributions that were removed afterwards. Later on 2026-10-02 the plan's 64-row revision, as merged to main (`6652b78e`), ran once on the destination distribution, the one meant to stay; the record of that run is private, its public receipt comes with that distribution's acceptance, and this folder records no result of it. `python3 -B check_plan.py` checks that `install-plan.json`, `owners.json`, both scripts, `mise.toml`, `config/` and the manifest agree.

Six of the 70 rows were added after the clean run: five from the layer consensus of 2026-10-02 (`docs/decisions/2026-10-02-new-wsl-layer-consensus.md`) and `statusline` from its wave-2 batch of 2026-10-03, which also turned three rows into interim installs and revised four more. All three results above are about the 64 rows that existed then. The install and acceptance commands of the rows added or revised since (sections "Rows from the layer consensus" and "Wave 2" below) have not run anywhere, on any distribution; those sections say what was checked instead. Ten more rows came from the wave-3 batch of 2026-10-04, the owner's decision, which also turned `ccusage`, `session-analytics` and `context-supply` into owner defaults and widened `code-search` to both arms of its confirmatory (section "Wave 3" below); their commands have not run anywhere either.

On 2026-10-03 two rows that were not installed at the clean run, `local-generation-model` and `embedding-model`, became installable after the local-model measurement settled them in the manifest (`docs/decisions/2026-10-03-new-wsl-local-models.md`). They create their models through the running model server, which the plan did not start when these rows were added, so the model rows remain named-only and their default install/acceptance is skipped and `--only` installs and checks each. As plan rows, their install and acceptance commands have not run anywhere; the section "The two local-model rows" below says what was checked instead.

The target remains a clean Ubuntu 26.04.1 WSL 2 distribution with systemd, one non-root user, passwordless sudo and existing RTX 4090 passthrough.

## Installation and acceptance

```sh
python3 -B check_plan.py
bash install.sh --list
bash install.sh --only <slot>
bash accept.sh --only <slot>
bash accept.sh --only <slot> --stage service_health
bash accept.sh --only <slot> --stage after_sign_in
```

Both scripts refuse root. Installation selects dependencies, isolates owner failures and retains existing operator configuration. No default-shell or Windows-side change is prescribed. `--list` is read-only and prints `slot | owner | route | status` for every row; the status is `planned`, `measurement-only` or `excluded`.

A row is installed by the default run when the manifest row says it installs something, its outcome is not `not_installed` and its state is not `split`, or when it carries an interim install (amendment 3 of the manifest's decision rule, 2026-10-03): an interim installs beside a decided default that installs nothing, whatever that row's state, so code search (split), durable memory (waiting for its measurement) and context supply (a definitive no-install row) install their interims, while their decided defaults stay as the rounds recorded them. `check_plan.py` requires the plan to install every interim the manifest records, with the interim's owner and repository, and requires each interim row's install function to call `interim_acknowledged` first. Two rows the manifest marks as installing are not: MCP Inspector (run on demand with `npx`; mcporter owns MCP calls from scripts) and the base distribution (the image the plan runs on). Two installed rows are left out of the default run: the local-model creation rows. The separate local-model-server row now carries the lasting-owner boot-enabled unit described below.

- 60 rows are installed by default, two of them interim installs: ai-memory (`memory-owner`) and semble plus SocratiCode (`code-search`). Context-mode (`context-supply`), ccusage and session analytics are wave-3 owner defaults; Promptfoo is the wave-4 owner default from the additive fix-wave integration.
- The two local-model rows (`local-generation-model`, `embedding-model`; manifest state `measurement`, returned) are installed only when named. The default run and the default acceptance skip them and print `skipped`. Once the model server answers on 127.0.0.1:21434 and reports version 0.35.0, `bash install.sh --only local-generation-model` (likewise `embedding-model`) installs one, `bash accept.sh --only <slot>` checks its files and `bash accept.sh --only <slot> --stage service_health` checks the created model through the server.
- Loki and Grafana are measurement-only (manifest state `split`). The default run and the default acceptance skip them and print `skipped`. `bash install.sh --only loki` (likewise `grafana`) installs one for the measurement, and `bash accept.sh --only <slot>` checks it. Wave 5 makes the existing `playwright-cli` slot a default Chrome DevTools MCP install; see its browser section below.
- MCP protocol conformance is a selected, pinned on-demand qualification recipe. Its install and acceptance run only with `--only mcp-protocol-conformance`; the default run skips it.
- 19 rows install no persistent package: `research-skill`, `mcp-inspector`, `isolation-container-boundary`, `claude-plugins-official-code-intelligence-lsp-pl`, `reranker-model`, `trafilatura`, `web-search-provider`, `phoenix`, `attest`, `dependabot`, `codeql-sarif`, `gpu-container-runtime`, `trufflehog`, `credential-custody`, `claude-code-action`, `agent-structural-diff`, `cross-family-review`, `chezmoi`, `base-distribution`. Inspector runs on demand; base-distribution is an environment prerequisite with Canonical checks; cross-family-review executes native after-sign-in checks without another install. The other 16 rows have no acceptance function.

An excluded row without acceptance has no install or acceptance function; `accept.sh` prints `slot | stage | skipped` for it, and `install.sh` prints nothing. MCP Inspector is the on-demand exception: it retains a pinned launch command and a Node prerequisite, has no persistent install function, and runs its acceptance only with `--only mcp-inspector`. The default acceptance still skips it.

`install-plan.json` schema version 2 stores acceptance as an object with up to three stage keys. Each check retains `command`, `kind` and `source`:

- `post_install` is the default. It checks the fresh installation with no stack service running and no sign-in. Prefer the documented local diagnostic/configuration validator; use a version command when no applicable self-test is documented.
- `service_health` retains the readiness/runtime checks and runs after the corresponding service starts. It does not perform sign-in or configure a provider.
- `after_sign_in` retains native-client diagnostics that need credentials and upstream model examples. Local Ollama also belongs here once its server and model route are provisioned; it needs no remote account.

Output is `slot | stage | exit-code`. An excluded or measurement-only row in the default run, an absent stage or an unavailable host check prints `slot | stage | skipped`, and so does the `local-model-server` row's `after_sign_in` check until the `embedding-model` row has created the model it calls; a skip does not certify acceptance and does not fail the script. A selected executable check returning 78 prints needs_user and leaves the prerequisite unresolved; every other nonzero status makes the script exit 1. Application stdout stays suppressed to avoid printing private diagnostic/model data; stderr and status are retained.

All 63 installed rows have a `post_install` entry: 45 smoke/configuration checks, 12 version checks, two unavailable checks (credential guard and token-lane carriers), two unchanged upstream-test subsets (Chrome DevTools MCP and Harbor), one upstream-smoke/native-integration entry and one upstream-tests/native-smoke entry. Thirteen installed rows have a service stage and 25 have an after-sign-in/model-provisioning stage. The two measurement-only rows add two post-install, two service and one after-sign-in stage. Inspector adds two on-demand stages, base-distribution adds one prerequisite stage, and cross-family-review adds one native-client stage. Together these are 110 primary stage entries plus the two G1 additional native checks, 112 checks in total; the JSON carries 183 command entries, including the on-demand Inspector launch.

Version-only post-install checks: codex; claude-agent-sdk; codex-sdk-and-codex-exec-app-server; local-model-server; inspect-ai; actionlint-kjanat; dagu; docker-compose; container-engine; git; gh-github-cli; restic. Harbor runs the unchanged upstream ATIF validator unit tests at post-install; its telemetry-contract qualification remains a separate after-sign-in acceptance. SDK checks report package versions. GPT Researcher is imported from its pinned checkout and performs the fail-closed preflight; the combined research-harnesses row also runs unchanged DeerFlow client tests and checks its configured model. DeerFlow runs as its embedded `DeerFlowClient`, with no service, port or Compose stack; its after-sign-in stage performs actual research alongside GPT Researcher. OpenHands 1.50.1 runs unchanged upstream SDK and cross tests. Difftastic now has a structural fixture and failure control, and Grafana measurement-only acceptance uses native APIs.

## Routes and lifecycle

Ubuntu's own `apt` package is Git's route. The base image/prerequisite installation already supplies it; rerunning this owner is idempotent. The Ubuntu candidate is not pinned to upstream Git v2.56.0. There is no PPA or source build.

Installed route counts: native-installer 5; none 14; npm-global 5; uv-tool 9; mise 10; model-server 2; npm-npx-stdio 1; release-binary 8; repository-recipe 3; apt-repo 2; apt 1; uv-project 1; uv-tool-owner-extension 1; npx-on-demand 1. The two measurement-only rows add two release-binary routes. The enum retains the existing library/venv, local-npm, skills-installer and marketplace classification limitations.

`mise.toml` retains the exact global tools (ten: ast-grep 0.45.3 is new, chezmoi is gone) and Node 24.21.0, Python 3.13.16 and uv 0.12.22 pins. `install.sh` merges them through `mise use -g`. Noninteractive diagnostics add mise shims to the process PATH without changing the shell. Doctor runs in the owned global tool directory so selecting only mise does not require the inventory's optional tools. The selected Chrome DevTools MCP browser owner installs Linux stable Chrome from Google's signed apt repository with a pinned key fingerprint and version; its unchanged upstream subset and native-client smoke use that browser. OmniRoute service-health requires `/readyz` to succeed before its full doctor; doctor alone can warn about a stopped service and return zero.

Docker requires uidmap, dbus-user-session, kernel/rootless prerequisites and its upstream user unit. Exact Engine 29.8.2/Compose 5.5.1 apt revisions come from repository metadata; missing versions fail. Harbor's CLI installed in round 1; its overall installer failed later in Docker setup. Keep this prerequisite gate for the real distribution.

Upstream Docker and Dagu user setup start their services during installation. Other documented foreground/daemon starts, including Alertmanager's, are in [SOURCES.md](SOURCES.md#service-starts--separate-from-installation); the install does not run them, so those services' health checks fail until they are started (as the real-distribution run showed). Post-install checks do not require them. Dagu's user-bus setup, rootless Docker, sandbox namespaces and Git worktree access were checked on the real distribution (VALIDATION.md).

GPT Researcher runs only through `tools/research/gpt_researcher.sh` (a keyless configuration, an `env -i` scrub, a fail-closed preflight and `research_report` only). DeerFlow's backend is installed with `uv sync --locked`; foreground research uses its shipped headless JSON CLI with the native 100-step recursion limit and the tagged keyless DDGS adapter. The scrub leaves Jina and Tavily keys empty, and callers select the current public config explicitly. The run retains original JSON events, unqualified returned AI text and an integration receipt requiring a matched substantive search result, linked final citation and terminal usage. Empty DDGS outcomes remain provider-availability evidence and fail acceptance. The measured Tavily adapter is a ready-to-apply proposal requiring a command-center ruling; it does not decide the separate provider-owner measurement or alter GPT Researcher's keyless route. No HTTP stack is started. Historical embedded-client and Compose recipes remain recorded in [SOURCES.md](SOURCES.md).

Native self-updating Claude/Codex installers remain preferred over npm; reviewed releases are not runtime locks. Existing loopback service configuration, supported isolated Python environments and excluded overlaps remain in the JSON and [SOURCES.md](SOURCES.md). User-unit forms follow the qualified adaptations named below. No credentials or provider values are filled in.

## This revision

- **Rows follow the manifest.** Trafilatura, ccusage, Phoenix, Promptfoo and chezmoi lost their install and acceptance functions, mise tools, config files (`config/phoenix-compose.yaml`) and source entries; so did the rows that never had a host install (Claude Code Action, the CodeQL slot, trufflehog, the LSP plugins, the structural-diff row). attest and Dependabot became `installed: false`, with their reviewed workflow pointers kept in `notes`. Loki, Grafana and Playwright CLI keep their functions behind `--only`.
- **Added.** ast-grep 0.45.3 through mise (`structural-search`); Alertmanager v0.34.1 as a checksum-verified release binary with `config/alertmanager.yaml` (one receiver that sends nothing), port 21093 on loopback and clustering off (`alerting`); mattpocock/skills per skill for both agents, through the `skills` installer pinned to 1.7.0, source tag v1.2.3 and telemetry off (`engineering-process-skills`). `setup-matt-pocock-skills` is included because the upstream README asks that it be one of the selected skills.
- **Three repairs from the real run** (VALIDATION.md, findings 1 to 3): the Codex installer line sets `CODEX_NON_INTERACTIVE=1`, which the installer documents as skipping prompts; the Claude marketplace line for Trail of Bits adds the repository by its HTTPS clone URL, unpinned (the client takes a branch or tag there, not a commit, and the repository has no tag), and the acceptance prints the clone's `HEAD` beside the reviewed commit and fails when they differ; and the scripts stop with a clear message when `repo_root` is not a git checkout. The mattpocock row needs no such comparison: the installer clones the pinned tag. Its acceptance compares the `skillFolderHash` values that the installer recorded in its lock file with the expected git tree hashes of the six skill folders at the tag; it does not hash the installed directories. The clean run's record reports that the lock it returned had no `ref` field; the installer at v1.7.0 supports that optional field, and why it was absent in that run is unresolved.
- **`check_plan.py`** fails and names each problem when a selected row has no install function or no post-install acceptance, a function exists for a row that is neither selected nor measurement-only, `install.sh --list` does not print exactly the rows of `install-plan.json`, a `mise.toml` tool belongs to no selected or measurement-only row, a selected row's manifest counterpart is missing, `not_installed` or `split` (unless the row carries an interim install, which the plan must then install with the interim's owner and repository, and whose install function must call `interim_acknowledged` first; added in wave 2), a row without an interim calls that gate (added in wave 3), two rows claim one port, or a command has no source URL. It also checks that the rows are the manifest's foundation rows, that `owners.json` agrees, that the `run_command` lines and `check` calls in the scripts are the commands in the JSON, and that every `config/` file is copied.

The original [validation.json](validation.json) records the earlier source/static review and [container-validation.json](container-validation.json) the round 1 container run. The clean run of 2026-10-02 claims installation, post-install acceptance and the health of six services in a throwaway distribution, and nothing more: no provider call, model run, GPU use or sign-in, and no run on the destination distribution. After that run the header comments of both scripts and the plan's `status` text were corrected to say so; no command changed, and the record names the executed commits and file hashes.

## Rows from the layer consensus (2026-10-02)

Added after the clean run, from `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json` through the manifest. The decision and its limits are in `docs/decisions/2026-10-02-new-wsl-layer-consensus.md`. The clean run's record binds the files it executed by hash (`executed_files`); the scripts and the plan have changed since, so that record describes the earlier files and none of the rows below.

- **`skill-discovery` installs one folder for both agents.** `find-skills` from `vercel-labs/skills` at the record's commit `7407f3893ad4dceab546ac002c3ef806e4000c73` (its release `v1.7.0`), through the `skills` installer that the plan already pins to 1.7.0, with `-s find-skills` and telemetry off. No other skill of that repository is installed.
- **`skill-authoring` installs one folder for Claude Code only.** `skill-creator` from `anthropics/skills` at the record's commit `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`, with `-a claude-code` and `--copy`. Nothing is installed for Codex and no same-name copy is placed for it: Codex embeds its own `skill-creator`, and the installer's shared directory `$HOME/.agents/skills` is the one it uses for Codex's global skills. The acceptance fails when `skill-creator` exists in that directory or in Codex's own global skills directory, `${CODEX_HOME:-$HOME/.codex}/skills` (the installer's README, line 298), a dangling symbolic link included; Codex keeps its embedded skills under `skills/.system`, which the check leaves alone. It also requires the installer's listing, run without an agent filter so that it reports every agent the installer detects, to name Claude Code as the only agent of `skill-creator`.
- **Both pins are commits.** The installer documents no commit syntax in its README. Its source at the pinned installer commit first tries the ref as a branch or tag and then fetches a 40-character commit directly ([SOURCES.md](SOURCES.md), last section). That path is read from source and has not been exercised by this plan.
- **Their acceptance follows the `engineering-process-skills` row.** The installer's own listing must name the skill for each intended agent (for `skill-authoring`, Claude Code and no other agent), and the `skillFolderHash` in the installer's lock file must equal the git tree hash of the folder at the pinned commit (`76a98a285cb0434f3d39e1a873823556330e398b` and `3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6`, read from the GitHub tree API on 2026-10-02). It does not hash the installed directories and says nothing about a client loading or invoking a skill.
- **`research-skill` and `credential-custody` install nothing.** Each has `installed: false`, no command and no acceptance. Their `notes` give the activation gate and the deciding measurement from the record. The plan carries no install command for a measurement arm.
- **`cross-family-review` installs no additional component.** The native client rows supply it. Its `acceptance_only` row now runs both native review directions after sign-in; the destination qualification gate still requires independent dispositions and later verification (the Git fix wave below).

What was checked for these rows is static, and is listed in [VALIDATION.md](VALIDATION.md): `check_plan.py`, `bash -n`, `install.sh --list` and the two acceptance programs against stand-ins. For `skill-authoring` those stand-ins are now a committed test (`tests/test_new_wsl_definitive_defaults.py`, class `SkillAuthoringAcceptance`) that runs the program `accept.sh` runs and plants each of its conditions on its own. **The two install commands and the two acceptance checks have not run anywhere.** Their first run is owed in a throwaway distribution before the destination.

## Git fix wave (2026-10-04)

These three rows repair the verified E2E's plan gaps. The change is source and
local integration work; it does not rerun acceptance on a WSL distribution.

- **Worktrunk 0.80.0.** The mise pin stays. Installation now runs the upstream
  `wt config shell install bash --yes`, `wt config plugins claude install --yes`
  and `wt config plugins codex install --yes`. The post-install check requires
  enabled native plugin listings and an active `wt` function in fresh Bash, then
  exercises the upstream create/switch/list/remove examples in a disposable
  repository with its own Git identity and configuration. A dirty-removal control
  must fail while preserving the worktree; clean removal must delete its branch
  and directory. The selected claude-hud statusline stays. Worktrunk's Codex plugin
  provides guidance and activity tracking; its automatic worktree isolation is
  Claude-only, so Codex uses the CLI lifecycle directly.
- **Difftastic 0.71.0.** The mise pin stays. Two unchanged upstream JavaScript
  fixtures are installed from `config/`, with their SHA256 checked on every run.
  The installed binary must report `Has syntactic changes`, identify JavaScript,
  return 1 with `--exit-code` on the changed pair and return 0 on the identical
  input. A Text fallback fails the check. These are the inputs/assertions of
  upstream `tests/cli.rs`, parameterized for the installed binary; the Rust suite
  is not executed. No global Git external-diff or difftool setting is selected.
- **Cross-family review.** `installed: false` continues to mean no additional
  package. `acceptance_only: true` makes the existing client capability execute
  instead of being in the skipped-slot loop. After sign-in, GPT Sol at max reviews
  Claude commit `8c32a84b246da66e43a6188c973741b09329e223` using
  `codex exec review --commit` without a positional prompt; Opus at max reviews
  Codex commit `b9dbe3c5a09cdefca435cd78c7f3dad46ca883a4` through native headless diff
  input. Both commits' author-family trailers and their immutable parents are
  checked. The complete event streams, stderr, diff, final GPT review and before/
  after worktree observations stay in private state outside the checkout. Native
  sign-ins remain native. The smoke requires both reviews to complete; the
  coordinator still must bind actual model and effort, independently disposition
  every finding and retain later verification before closing the qualification
  gate. Requested model/effort flags alone do not establish the actual route.

Worktrunk and difftastic also gain `after_sign_in` checks. Each starts fresh
`claude -p` and `codex exec` sessions and requires the actual successful shell-tool
result of its functional post-install program, plus a complete successful turn.
A final answer or a version report alone fails. Complete streams are retained
under `${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/` with
private permissions. These checks need the existing native client sign-ins; they
install no review service and publish nothing. `--stage after_sign_in` executes
these checks, including when running the full stage.

The selected Worktrunk profile already named 0.80.0. The stack and architecture
release cells now agree with it; their historical 0.79.0 receipts keep their
original scope. [SOURCES.md](SOURCES.md) names the exact upstream references, and
the [decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g7-git.md) records
the adjudication corrections, local returned results and remaining host gate.

## The two local-model rows (2026-10-03)

Settled by the preregistered local-model measurement of 2026-10-02 and 2026-10-03 (`evidence/artifacts/new-wsl-local-models-20261002/`; decision `docs/decisions/2026-10-03-new-wsl-local-models.md`; the manifest's settlements in `evidence/artifacts/new-wsl-definitive-defaults-20261001/settlements.json`). Each row installs the system that was measured, from pinned downloads, with the Modelfiles carried in [models/](models/). Sources: [SOURCES.md](SOURCES.md), section "The two local-model rows".

- **`local-generation-model`** downloads `Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf` from `ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF` at revision `d74895bbe5db4bec1e0024e7cc87d59c02d7631a` and keeps it only when its sha256 is `1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786` (11,771,546,912 bytes), into `$tool_root/ollama-models`. It places the two Modelfiles beside the file and creates `swift-iq3s-s2o` (the library `qwen3.8:27b` model's template, renderer, parser, parameters and licence lines with the Swift file as `FROM`: the measured file, whose `FROM` was an absolute path in the throwaway distribution and is written here relative to the Modelfile) and `swift-iq3s-s2o-64k` (`PARAMETER num_ctx 64000`). `ollama create` copies the file into the server's model store as a layer under its own sha256 (written by the client when a loopback server shares its store, uploaded otherwise), so the row needs about 23.5 GB of disk while the download is kept.
- **`embedding-model`** pulls `qwen3-embedding:0.6b` (Q8_0), stops unless the server lists it with the pinned library manifest digest `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`, and creates `qwen3-embedding-8k` (`PARAMETER num_ctx 8192`). The pull checks each layer against the manifest the registry serves for the tag at that moment; if the library republishes the tag, the digest check stops the row instead of installing another model.
- **The context belongs to each model, never to the server.** With a server-wide `OLLAMA_CONTEXT_LENGTH=64000` the embedder loaded at its full context (32,768 tokens) and took 5.78 GB in the measurement (A1b). The derived models carry their own `num_ctx`; `config/ollama.env.example` sets only `OLLAMA_HOST`, and nothing in the plan sets a server-wide context.
- **The measured server's other settings.** The historical measurement used OLLAMA_NUM_PARALLEL=1 and OLLAMA_KEEP_ALIVE=-1 without a server-wide context. D-ollama-2 (the user's decision at about11:05 AM EDT (15:05Z) on2026-10-05) replaces indefinite boot preload with on-demand loading and native30m idle expiry. The exact owner-approved unit retains OLLAMA_NUM_PARALLEL=1 and OLLAMA_NO_CLOUD=1, with no ExecStartPost warmup. Installed Ollama0.35.0 help reports its built-in5m default;30m is the user-approved override. Organic usage/reload-cost measurements can overturn this choice.
- **The model creation rows remain named-only.** Their version/readiness guard is unchanged. The local-model-server installer places the exact owner-approved unit, then runs native systemctl --user daemon-reload and enable --now ollama.service. service_health requires enabled/active, one on-demand embedding of Hello world, then exactly one matching canonical embedder entry with positive numeric size_vram==size. This observes residency after the request; cold loading, boot preload and future residency are separate claims. The embedding-model row must already have created the settled model; nothing is pulled. Only the co-op/readiness-runner applies the plan on the shared host. Existing unreferenced host warmup files remain under their owner's custody.
- **Acceptance.** `post_install` reads files only: for the generation row, the placed Modelfiles hash to the repository's and the created model's manifest names the pinned file's sha256 as a layer; for the embedding row, the library manifest in the server's store hashes to the pinned digest and the derived model's manifest names the library's model layer (`sha256:06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`, read from the registry's manifest at the pinned digest on 2026-10-03). Both read the store at `${OLLAMA_MODELS:-$HOME/.ollama/models}`, which assumes that the server runs as the same user with the same `OLLAMA_MODELS`. `service_health` runs once the server answers: `ollama show` must report the model's own context (and `IQ3_S` for the generation model), then one short generation with thinking off (the measurement ran at effort medium) or one embedding call that must return 1,024 values (the model card's full size; the measurement's records do not state the size of the vectors it received). The `local-model-server` row's `after_sign_in` smoke check is one `/api/embed` call to `qwen3-embedding-8k`, the settled embedder, which must return one vector; it needs the `embedding-model` row installed first and pulls nothing. Until that row has created the model (its manifest in the store above), `accept.sh` prints `skipped` for the stage, which is not a pass, so the after-sign-in checks of step F9, which install no model row, do not fail on it (until 2026-10-03 it ran upstream's example `ollama run embeddinggemma "Hello world"`, which would have pulled EmbeddingGemma, the embedding arm that lost).
- **Destination GPU ownership.** D-ollama (2026-10-05), command-center item task-ns2604-coop-20261005T142343Z point1, carries the user's2026-10-03 lasting NativeStack2604 owner ruling and supersedes the historical undecided limitation in [the local-model decision:254–257](../../../docs/decisions/2026-10-03-new-wsl-local-models.md). The upstream [Ollama0.35.0 Linux system unit:57–89](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/docs/linux.mdx#L57) is the unit-form source; the updated user-unit adaptation retains designated host hash5e8e8bc4. The former94e03d7b unit and2236dc86 warmup hashes are historical, superseded by D-ollama-2. The co-op reports enabling the host unit at10:28:53 AM EDT (14:28:53Z); that report and this lane's independent enabled-state health check remain separate evidence. The cross-distribution listener guard in the exact unit is retained.

Checked for these rows (static, VALIDATION.md, section "The two local-model rows"): `check_plan.py`, now also failing when the default runs of `install.sh` and `accept.sh` disagree about a row in either direction; `bash -n`; `install.sh --list`; the four acceptance programs and the server row's `after_sign_in` check against stand-ins in a committed test (`tests/test_new_wsl_definitive_defaults.py`, class `LocalModelAcceptance`); and `install.sh`'s server guard against stand-ins (class `ModelServerGuard` there). **No command of these two rows has run as a plan row, anywhere.** The measurement created and ran the same models in a throwaway distribution, from the same file and library digest, by its own scripts. The first run of the rows is owed in a throwaway distribution or on the destination once the lifecycle design has settled GPU ownership.

## Wave 2 (2026-10-03)

From the wave-2 batch of the layer consensus (`consensus.json`, key `wave2`, with its hashed records in `evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json`) and the rulings it records. The decision is in `docs/decisions/2026-10-02-new-wsl-layer-consensus.md`, section Wave 2. Sources for every command and check are in [SOURCES.md](SOURCES.md), section "Wave 2", and the static checks in [VALIDATION.md](VALIDATION.md), section "Wave 2".

- **Three interim installs** (amendment 3): ai-memory 2.5.2 (`memory-owner`, the release archive, bound to 127.0.0.1:29374 with the local embedder, and ai-memory's own installer writing its seven Codex hooks once), semble 0.6.1 (`code-search`, a uv tool with its model pinned in a local snapshot) and context-mode 1.0.169 (`context-supply`, both clients' plugins and the Codex session server from the verified npm tarball). Each install function first calls `interim_acknowledged`, which refuses while the batch's `acknowledgements_owed` names a family; the client configuration's `--apply` refuses the same way.
- **One added row**: `statusline`, claude-hud 0.10.0 from its marketplace at the tag, then upstream's helper (`scripts/setup.mjs inspect` and `install --shell posix`), which copies the launcher the status line runs and writes `statusLine`, with `refreshInterval` 5 added when absent; and Codex's own footer.
- **Revised rows**: `research-harnesses` (DeerFlow embedded, GPT Researcher through the repository script), `tobi-qmd` (GPU auto, the interim embedder and a check after provisioning), `gpt-gateway` (plain `NAME=value` lines in `config/omniroute.env.example`, `EMBED_WS_PROXY_PORT=21131`), and the three skills rows, which now run `tools/adoption/install_skills.py` against `adoption/skills/manifest.json`. The lifecycle dossier's duplicate units for the collector, Prometheus, Alertmanager and OmniRoute are dropped (synthesis X1 and X3, in the rows' notes); Ollama's (X2) belongs to the local-model rows, which the local-model evidence change revises.
- **Not run.** None of these commands or checks has run on any distribution.

## Wave 3 (2026-10-04)

From the wave-3 batch of the layer consensus (`consensus.json`, key `wave3`), the owner's decision of 2026-10-04 under amendment 4 of the manifest's decision rule, relayed by `docs/decisions/2026-10-04-token-full-stack-owner-default.md`. The original wave-3 pins came from `manifests/stack.json` and `adoption/pins-linux-x86_64.json` at `f77a35eb`. After main's PR #693 (2026-10-04) those files pin RTK 0.51.0 and mcporter 0.14.2, and this plan follows them. PR #642 W1 also moved jcodemunch-mcp after `f77a35eb` to 1.108.327, source `6d5ae86c130f96624e2ca2d797fa3b853c210b9d`, and this plan follows that selected pin. Its README was read at 6d5ae86c and the prior 8f7b34ab pin on 2026-10-05; install, version and session-stats anchors 91, 113 and 141 are unchanged (SOURCES.md, the code-index row). Every tool installs under the ecosystem root the client templates name, `${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}`: release archives and npm tarballs through `fetch_verified` against the recorded sha256 (no `gh release download`, so no GitHub sign-in), archives extracted whole into `tools/<tool>-<version>` (bundled licenses kept), npm packages with `npm install --global --prefix tools/<tool>-<version>` from the verified tarball, uv tools with `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` in the root, and each command linked into `${ECO_ROOT}/bin`. Sources are in [SOURCES.md](SOURCES.md), section "Wave 3", and the checks that ran in [VALIDATION.md](VALIDATION.md), section "Wave 3".

- **Ten owner rows** in token-efficiency: `command-output` (RTK 0.51.0, the musl release archive; the Claude hook is the client configuration's, and the Codex hook is installed and trusted by this row, on the decision of 2026-10-04), `output-compression` (Headroom 0.37.0 with the `[mcp]` extra, MCP server only), `code-index` (jcodemunch-mcp 1.108.327, selected in `manifests/stack.json`; [W1 qualification](../../receipts/jcodemunch-1108327-qualification-20261003.json)), `code-graph` (codebase-memory-mcp 0.11.0, the release archive; neither its `install.sh` nor its `install` subcommand runs), `repo-packing` (Repomix 1.18.1), `structured-data` (TOON 4.1.1), `doc-conversion` (MarkItDown 0.1.8, the base converter), `api-docs` (Context Hub 0.1.4, telemetry and feedback off), `trace-viewer` (otel-tui 0.7.5, on demand, no service) and `token-lane-carriers` (written by the client configuration; its function only says so).
- **Owner defaults**: `ccusage` (20.0.26, a read-only meter) and `session-analytics` (agentsview 0.43.0, a local archive only, telemetry and the update check off) now install; `context-supply` keeps its commands and checks and no longer calls `interim_acknowledged`, since its authority is the owner's decision and not amendment 3.
- **`code-search`** installs SocratiCode 1.15.0 beside semble (its npm tarball with `--ignore-scripts --before=2026-09-24T12:00:00Z`, into the prefix the client templates run), keeps its gate, and its check reads SocratiCode's version from `package.json`, never by running it. SocratiCode serves nothing until the client configuration names a Qdrant store and an embedding endpoint, which no row installs yet.
- **The gate** `interim_acknowledged` reads every wave batch and refuses while any of them owes an acknowledgement; an owner batch owes none.
- **Not run.** None of these commands has run on any distribution. The four release archives and the five npm tarballs were downloaded to a scratch folder and matched their recorded sha256 on 2026-10-04, and the four archive checks passed against the archives' binaries there (VALIDATION.md); that is no installation.

## G1 client plan repairs (2026-10-04)

The bounded repair covers `codex-sdk-and-codex-exec-app-server`,
`engineering-process-skills` and `skill-authoring`. Pins and owner selections stay
as selected. The source comparisons and remaining host gates are in
[the G1 decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g1-clients.md).
This revision has not run on a WSL distribution.

- **SDK and app-server.** After native Codex sign-in, run
  `accept.sh --only codex-sdk-and-codex-exec-app-server --stage after_sign_in`.
  It runs the documented SDK quickstart with `new Codex()` and its default bundled
  binary, followed by the native `codex debug app-server send-message-v2` client.
  Require two result lines ending in `after_sign_in | 0`. The protocol check
  requires initialize, thread/start, turn/start, a `Completed` notification and
  the requested reply. The client starts a short-lived stdio child. Its exit
  status alone permits a failed turn, so completion is checked explicitly. Output
  is captured before grep to let the client finish writing its trace summary.
- **Engineering skills.** Run the install from the operator shell outside a
  Claude session. Before the existing manifest installer, the upstream Skills
  CLI removes only `domain-modeling`, `setup-matt-pocock-skills`, `grill-me`,
  `improve-codebase-architecture` and `semgrep`. The existing settings writer
  merges the three retired names as `off` from
  `config/engineering-process-skills.settings.json`, retaining other settings.
  Post-install acceptance keeps the selected-skill hash/lock check and rejects
  excluded listing names, remaining folders or dangling client links, stale lock
  entries and incorrect retired-name overrides. Repeat fresh `tdd` invocation
  in both clients and verify that all five excluded names are absent. The held
  `agent-browser` selection keeps its existing gate.
- **Skill authoring.** Install PyYAML 6.0.3 into the selected mise Python through
  upstream `uv pip install --python`. Post-install acceptance has two independent
  result lines: the existing Claude-only listing, tree and placement check, and
  both tools' unchanged upstream `quick_validate.py` scripts through the
  session-default `python -B`, against the pinned installed `find-skills` folder.
  The second check first runs native `codex debug prompt-input` with stdout
  discarded to initialize Codex's embedded cache through its own skills loader
  on a clean home.
  Require both lines ending in `post_install | 0`. Bytecode stays disabled so the
  checks preserve the installed skill trees. A missing validator or Python
  dependency fails the second check. Codex keeps its embedded creator; no shared
  same-name creator is installed.

The Skills CLI listings of the two owned skills rows write to a regular temporary
file before jq reads them. Skills 1.7.0 calls `process.exit` after printing JSON;
Node's POSIX pipe writes can still be pending at exit. A file avoids that
truncation. The earlier repair's `skill-discovery` hunk belongs to another builder.

Additional native checks are declared under a stage's `additional_checks` and
run through a slot-owned helper. `check_plan.py` verifies the helper's stage,
command, source and call from its owning function for these two client slots.
The existing `SkillAuthoringAcceptance` fixtures continue to test the inventory
and placement check; they are separate from the upstream Python validators.

Inventory and validator success establish narrower properties than authoring
quality. Complete creation and evaluation in fresh native sessions in disposable
workspaces. Each client uses its installed skill-creator for authoring and
validation. Promptfoo owns paired skill verification in both clients, with
its upstream SDK harness and the pinned skill-comparison fixture. Retain
actual artifacts and results. This patch adds no model benchmark or destination
READY receipt.

## G3 code and document plan repairs (2026-10-04)

These changes serve code navigation and local document reading for the research and historical-simulation north star. They are recipe changes following the verified E2E's GPT review and the Opus adjudications; this builder performs no distribution installation, model inference or native sign-in. [The decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g3-code-docs.md) and [SOURCES.md](SOURCES.md) retain the sources and remaining live checks.

- **Serena.** The plan now installs commit `c6fbd1c5932df2494ffa0020af5a9fbe80b82143`, the `2.0.0.dev0` source already selected by the stack, profile and architecture. Before indexing, it adds `python` to the project's effective language-server list through `.serena/project.local.yml`, using upstream's YAML load/save helpers and retaining other overrides and languages. The upstream `serena init` check uses an isolated `SERENA_HOME`; `serena project health-check` checks the actual checkout's symbols and references. Step F8's existing client writer supplies the native `serena` MCP command with the Claude Code and Codex contexts. After that wiring and native sign-in, `after_sign_in` starts one fresh session per client and requires successful returned `find_symbol` and `find_referencing_symbols` results for `scripts/host_receipts.py:register_file`.
- **Structural search.** The same mise-installed ast-grep 0.45.3 binary runs the unchanged README's `-r '$A?.()'` preview as well as search. The check requires the replacement text and a no-match control returning exactly 1. It uses neither `-U` nor `-i`, so the preview writes no source file. The Opus adjudication rejected the proposed source-build coverage stage; this recipe adds no Rust toolchain. Existing CLI wiring through PATH stays sufficient under that adjudication.
- **MinerU.** The base 4.0.10 package uses CPU-capable ONNX and llama.cpp, and the row now records `needs.gpu: false`. The installer disables telemetry, installs the pinned upstream `mineru` skill for Claude Code and Codex, downloads and verifies Standard models, sets the managed tier before managed mode, and fetches upstream's public `demo1.pdf` by commit and sha256. The slot's own `config/mineru-skills-manifest.json` uses the existing repository installer's supported `--manifest` route because the shared adoption skills manifest is outside this builder's ownership. `post_install` retains upstream's `mineru --help`, adds pinned skill/list/placement checks and verifies model files. Skills CLI JSON goes to a regular file before parsing. Start the upstream server explicitly, then run `service_health`: healthy local Standard support, successful parse, and a read of the returned page locator must all pass, with first-page text containing `afforestation`. `after_sign_in` repeats parse and read through the skill in fresh sessions of both clients and checks actual successful tool output.

Installation temporarily starts doclib for telemetry and configuration, then stops only the server it started. Run the persistent MinerU lifecycle in this order after installation:

```sh
mineru server start
bash accept.sh --only mineru --stage service_health
bash accept.sh --only mineru --stage after_sign_in
bash accept.sh --only serena --stage after_sign_in
```

The native sessions use the clients' existing configuration and sign-ins. MinerU commands stay local and never add `--remote`. Parser assertions and native JSONL assertions are project integration checks; `init`, `health-check`, `--help`, model verification and the published rewrite example remain identified by their upstream sources. Private returned parse results and native streams are retained under `${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/`, with restrictive permissions, outside this checkout. A fresh host still owes these actual returned results; static recipe validation proves no host is READY.

## G4 observability repair (2026-10-04)

The [G4 decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g4-observability.md)
and [sources](SOURCES.md#g4-observability-repair-2026-10-04) describe the three
bounded plan repairs. Their revised native commands are **UNRUN** on a distribution.
The coordinator has recalculated the shared current inventory above; historical run counts remain dated.

Collector installation and native validation use the same data environment:
`NS2604_OBSERVABILITY_DATA`, defaulting to
`${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/observability`.
The installer creates the owned queue and SDK-receipt directories. A clean
configuration includes native privacy and metric/log export pipelines; the
existing native client configuration map retains both clients' HTTP21318
endpoint. Existing operator pipelines are preserved. Only the exact obsolete
`/otelcol/queue` directory is migrated, with a backup and native validation.
The foreground service must receive that same data environment.

Grafana OSS 13.2.3 gains native datasource/dashboard provisioning and a loopback
anonymous Viewer. Run `install.sh --only grafana` explicitly for finalization
while its canonical selection remains split; Loki must also be installed and
running for the log/receipt views. The six hourly Claude targets keep `[1h]` and
now evaluate at `1m`. `service_health` checks native API operations, including
the Alertmanager frontend plugin's proxied `/api/v2/status`. `after_sign_in`
exercises fresh Claude telemetry and the existing native SDK worker, writes only
a sanitized receipt, then requires observed values from those six Claude and
three SDK receipt queries through `/api/ds/query`. Static post-install checks
alone do not certify dashboard readiness. The maintained Prometheus startup
feature flags for first counter samples are recorded in the G4 decision and
must be carried by the service owner.

Grafana publishing and all three acceptance stages preflight the three retired
wave-1 provisioning paths before reading the ledger or writing Grafana assets.
Any reappearance, including a dangling symlink, returns nonzero `needs_owner`;
no digest grants permission to migrate or retire it. The current plan helper
supplies this check, so an older installed helper cannot bypass it. On
NativeStack2604 the co-op holds the preserved backup until the command-center
soak permits retirement; see the A30 custody record in the followup receipt.

Alerting supports webhook/ntfy, Telegram and an on-host destination, retaining
the disarmed sink until the selected receiver's private files exist. ntfy.sh was
the coordinator's delegated pick on 2026-10-04. The user personally configured
and accepted Telegram on NativeStack2604 at about 06:58Z on 2026-10-05; that live
choice supersedes the delegated pick, and no supported receiver was overturned.
Note: with ntfy.sh or Telegram the alert text leaves the host. Sources:
[main `2d849ba1f`'s receiver note, :7](https://github.com/seathatflowsinourveins/native-agent-stack/blob/2d849ba1f/evidence/artifacts/new-wsl-final-architecture-20261002/critics/added-summary.md#L7)
and [Alertmanager v0.34.1's Telegram receiver, :1862](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L1862).
The plan never reads or prints those private files. The default
webhook pointer is
`${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack/alertmanager-webhook-url`;
`NATIVE_STACK_ALERT_URL_FILE` may supply another absolute pointer. The file must
be owned, regular, singly linked and `0600`, in an owned `0700` directory outside
every worktree. For ntfy, the user writes the URL with `?template=alertmanager` through
their own terminal; do not put a URL/topic value in repository configuration or
an agent prompt. `NATIVE_STACK_ALERT_RECEIVER=telegram` instead uses
`alertmanager-telegram-token` and `alertmanager-telegram-chat-id` in that store,
with optional `NATIVE_STACK_ALERT_BOT_TOKEN_FILE` and
`NATIVE_STACK_ALERT_CHAT_ID_FILE` pointer overrides. `on-host` uses the same native
webhook pointer and an independently qualified local receiver.

After supplying the chosen files, rerun `install.sh --only alerting`, then deploy
the changed Prometheus and Alertmanager configs through the destination's
existing unit owner. The measured destination used `ns2604-*` observability
units; the earlier `ecosystem-*` note was not a deployed unit inventory. Existing
operator configuration that differs from the known source is retained and
reported for its owner to merge. This installer starts no service.

Alerting post-install acceptance uses upstream amtool and native promtool rule
validation/unit tests; install the Prometheus owner before selecting that check.
Native delivery acceptance is `--only alerting --stage after_sign_in`. It prints
`needs_user (78)` when the destination files are absent. Once wired, it
posts an expiring tagged alert, exercises the empty file-SD fixture using a
confirmed closed loopback port, restores the empty target list and observes
notification counters plus rule firing/resolution. It returns pending until
a user attestation reports both received notifications for the emitted
`acceptance_id`. The user may record that nonsecret confirmation in
`$config_root/alerting-receiver-confirmation.json`:

```json
{"acceptance_id":"<the returned test id>","firing_received":true,"resolved_received":true,"confirmed_by":"user"}
```

Rerun the same stage within 30 minutes; it accepts the matching bounded receipt
without sending another test. A local readiness result or notification counter
does not substitute for this receiver attestation. This CLI checks the attestation fields and binding; it cannot independently verify who wrote the file. Stale or mismatched pairs are archived and a fresh delivery test runs automatically. Loki ruler evaluation remains
explicitly deferred to that slot's owner. The synthetic promtool inputs are
separate from these real delivery observations.

The coordinator reports that the user supplied both firing and resolved
Telegram messages for acceptance `9e6f4a70b5874573aff1d22b40e87a32` on
NativeStack2604. Main `4c897418f`'s unmodified delivery check returned 0 with
`receiver_evidence=user_attestation`. This is the reported 2026-10-05 host
acceptance, separate from this PR's local checks; no message contents or
destination values are recorded here.

## G5 analytics and evaluation acceptance (2026-10-04)

The G5 plan repair keeps agentsview 0.43.0, Inspect AI 0.3.273 and Harbor 0.23.0. It follows the independent review for session analytics and the Opus adjudications for the two evaluation CLIs. The source pins, upstream operations and local assertions are in [SOURCES.md](SOURCES.md), section "G5 analytics and evaluation sources", and the decision is [2026-10-04-2604-e2e-fix-wave-g5-analytics-eval.md](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g5-analytics-eval.md). These are plan changes; this builder ran no installation, service, provider evaluation or container trial on a distribution.

- **Session analytics.** The verified release installs behind an owned launcher in both the ecosystem bin and `~/.local/bin`. Every invocation uses the owned archive directory, telemetry off, update checks off and upstream `archive_content=usage`. The supported `CLAUDE_PROJECTS_DIR` and `CODEX_SESSIONS_DIR` variables select the active Claude and Codex homes, including explicit `CLAUDE_CONFIG_DIR` and `CODEX_HOME` overrides. The archive configuration binds to `127.0.0.1:8080`; start it with `agentsview daemon start`, inspect it with `agentsview daemon status`, and stop it with `agentsview daemon stop`. Installation starts no daemon. The service stage runs upstream sync, session listing and daily usage reporting for both clients, requires nonempty session and token data, and retains their actual output privately. `--offline` uses fallback pricing; its costs are estimates.
- **Harbor.** Installation also checks out the unchanged upstream `hello-user` task at the release's exact commit, since the wheel contains no examples. After rootless Docker starts, the service stage runs one oracle and one nop trial through `harbor run`, with `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock` explicit. It requires no model credential: the fixture pulls `ubuntu:24.04`. The upstream test's exception and verifier-reward assertions require 1.0 for oracle and 0.0 for nop; the local artifact checks also read each native `verifier/reward.txt` and require the positive reward gate to reject nop. Fresh run directories retain native job/trial results, verifier output and logs.
- **Inspect AI.** The uv tool environment explicitly includes the optional provider SDK, `openai==3.24.0`. Installation checks out the unchanged `examples/theory_of_mind.py` at Inspect's exact release commit. The stage after sign-in evaluates one sample through the existing loopback gateway and `openai-api/omniroute/cx/gpt-6.1-sol`, then repeats it with an absent model. Inspect's own `inspect log dump --header-only` reads both logs. The positive gate requires success, one completed sample and nonempty scores; the negative run must produce an error log rejected by that same gate. Preserve the native logs and both control exit codes. This checks execution and scoring; no accuracy threshold is imposed. The keyless loopback uses a non-secret placeholder. If gateway authentication was enabled by the operator, provide `OMNIROUTE_API_KEY` through the existing credential runner.

The E2E coordinator must create fresh sessions in both native clients for the session-analytics gate. Record an RFC3339 UTC timestamp before those sessions and retain their native IDs from the client receipts. Export that timestamp as `AGENTSVIEW_ACCEPT_STARTED_AT`, the Claude archive ID as `AGENTSVIEW_ACCEPT_CLAUDE_ID`, and the canonical Codex archive ID (`codex:<native-id>`) as `AGENTSVIEW_ACCEPT_CODEX_ID`. Then run:

```sh
bash accept.sh --only session-analytics
bash accept.sh --only session-analytics --stage service_health
bash accept.sh --only session-analytics --stage after_sign_in
bash accept.sh --only harbor-containerized-agent-e2e-runner
bash accept.sh --only harbor-containerized-agent-e2e-runner --stage service_health
bash accept.sh --only inspect-ai
bash accept.sh --only inspect-ai --stage after_sign_in
```

The fresh-session check requires each exact ID, the expected agent, messages and a start time at or after the recorded boundary. A missing ID, empty archive or historical session fails. An absent-session lookup supplies a retained failing control. Both analytics stages retain their records under the private user state directory; publish only sanitized receipts.

Harbor and Inspect are CLIs with no declared MCP, plugin or hook wiring. Under the adjudication, provider-backed native-agent trials and fresh Claude/Codex shell invocation of Inspect are further E2E work, rather than their READY gates. In particular, a Harbor codex trial through OmniRoute still needs proof that its container reaches the loopback-only gateway. A claude-code arm would need native OAuth setup and is outside the credential-free Harbor gate. Version checks remain prerequisite evidence, and these planned functional stages require actual host execution before READY can be recorded.


## Verified E2E fix: evaluation, usage and supply (2026-10-04)

The bounded `fix-wave-g6-eval-supply` changes only `promptfoo`, `ccusage` and
`syft`, on PR #684's head. The [decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g6-eval-supply.md)
records original evidence, primary sources, alternatives and the remaining
coordinator integration work. These plan changes have not run on any WSL
distribution. Earlier inventory totals and no-install descriptions above are
historical; their shared count/header updates belong to the coordinator.

- **Promptfoo 0.123.1** now installs as the wave-4 owner default (the owner's repository-quality rule; decide round 2 named promptfoo for paired skill verification), also serving gateway/LLM A/B.
  Its npm tarball is verified and its optional MCP SDK is included. The native
  STDIO server is registered with Claude Code in user scope and with Codex.
  Codex's native `env_vars` forwards the name `GATEWAY_API_KEY`, without storing
  its value, using the repository's existing preserving TOML merge/writer.
  Post-install acceptance runs unchanged upstream positive/failing smoke
  fixtures and checks actual results, including the failing control's exit 100.
  The echo fixtures qualify evaluator plumbing only. For real acceptance,
  the native `config/promptfoo-gateway.cjs` reads the active plan's
  `config/gpt-gateway-topology.json`: gateway endpoint, GPT fallback model and
  effort, and the explicit `promptfoo.claude_model`. A missing canonical route
  is a plan dependency for the command center to settle. Model IDs and endpoint
  are not a sign-in task. `apiKeyEnvar: OMNIROUTE_API_KEY` keeps the optional key
  in its environment store; the keyless loopback setting disables vendor-key
  fallback. The fresh Codex call forwards that name through a native per-call
  MCP override, without changing its global config. The retained legacy YAML
  template is not the acceptance input. Run the slot's
  `after_sign_in` stage: it requires an uncached two-provider evaluation plus
  successful `run_evaluation` results observed in fresh Claude/Codex sessions.
  CLI and MCP results must identify the exact frozen topology-derived pair.
  A catalog ID alone does not qualify a model's backing provider or version.
  The plan and `owners.json` now follow the definitive manifest as written.
  The checker rejects a Promptfoo install when the manifest excludes it.
- **ccusage 20.0.26** keeps PR #684's two install commands and pin. Post-install
  acceptance now runs both documented native daily reports on unchanged
  upstream fixtures, checking exact token/cache totals offline with costs
  hidden. The CLI needs no MCP server or hook. Its `after_sign_in` stage requires
  fresh native sessions to invoke the absolute ecosystem executable, native
  successful shell events and non-empty finalized daily reports from both
  clients. The existing client sign-ins are the only account prerequisite.
- **Syft 1.54.0** keeps its supported mise install. The allowed foundation,
  profile and stack pins now match the plan. The documented public-image scan
  must return a real non-empty SBOM containing `alpine-baselayout`; version and
  source identity are checked separately. The slot has no MCP/hook or defined
  fresh-session gate. Its historical trading records and three CI workflows
  are retained for their respective owners to reconcile.

Fresh-session output stays under private `$config_root/*-acceptance` directories
with mode 0700. It is an integration observation, separate from unchanged
upstream source suites and fixture checks. A fixture pass, a version check or
agent prose does not establish live-provider or destination-host readiness.


## Base, per-job isolation, GPT gateway and secret-scan installation acceptance (2026-10-04)

Fix wave `fix-wave-g8-base-gateway` changes only these four slots. Its decision is
[`2026-10-04-2604-e2e-fix-wave-g8-base-gateway.md`](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave-g8-base-gateway.md).
The recipes below require target execution by the coordinator; this builder ran no command on a WSL distribution,
no gateway operation and no credential read. The earlier global counts and run histories above remain historical.

- **`base-distribution`** remains the already installed environment, with no Linux package-install command.
  Canonical's signed-image installation remains the Windows-side W2-W6 recipe in
  [`linux-wsl2-new-distro.md`](../../../adoption/platforms/linux-wsl2-new-distro.md).
  `accept.sh --only base-distribution` now runs both unchanged Canonical `wsl-setup` 0.6.3 assertion scripts at
  `73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8`, with their downloaded bytes bound to SHA-256. It takes the expected
  default user from `WSL_USER` or `[user] default` in `/etc/wsl.conf`, and retains each script's exit code separately.
  The upstream systemd test may exit 1. The F1 integration exception passes only for exactly
  `systemd-binfmt.service` failed and the identifier-selected boot log's read-only binfmt flush diagnostic.
  Its remaining upstream assertions then run separately; the script's exit 1 stays an upstream failure.
  Interop records `cmd.exe`'s own exit and its version line. F3 failed OpenHands user units belong to the runtime-worker
  owner. No extra client-session check applies to an OS image.
- **`sandbox-runtime-srt`** keeps the upstream `npm install -g @anthropic-ai/sandbox-runtime@0.0.78` route and
  `srt echo "hello world"` smoke. The stack, profile, tarball checksum and architecture selectors now match 0.0.78.
  `accept.sh --only sandbox-runtime-srt --stage after_sign_in` adds a fresh Claude native Bash execution of that smoke
  and the documented `srt --settings` policy form. Set `SRT_ACCEPT_FIXTURE_ROOT`, `SRT_ACCEPT_POLICY`,
  `SRT_ACCEPT_DENY_READ`, `SRT_ACCEPT_DENY_WRITE` and `SRT_ACCEPT_ALLOWED_DIR` to existing disposable synthetic fixtures,
  all within the fixture root. `SRT_ACCEPT_DENIED_URL` defaults to `https://example.com` and must be denied by that
  policy. Unsandboxed read/write/network controls and a sandboxed allowed write must succeed; all three denied
  operations must fail. Returned native tool-use/result events must show the successful recipe, rather than a
  version call or model prose. `SRT_ACCEPT_CLIENT=codex` runs the recommended second client proof using native Codex
  command-execution events. The runtime-worker owner must additionally retain a per-job `check_report` or exit 0 under
  srt; a journal start alone is insufficient. Per-job isolation remains the wiring; no global policy or session-wide
  sandbox is introduced.
- **`gpt-gateway`** now installs the recorded canary composition: `release/v3.8.52 @23a11484`, the two pinned
  PR13788 commits and PR15167 `0585aba5`. `config/omniroute-canary-install.sh` uses upstream `npm ci`, the five
  unchanged carried Node test files, `typecheck:core`, `build:release`, the canary-enabled `check:pack-artifact`,
  `npm pack` and user-prefix npm installation. It refuses an unrelated existing alias or a different existing unit.
  It installs `config/omniroute.service` as a user unit with DATA_DIR under `~/.local/share/omniroute` and loopback
  ports 21128/21129/21131, reloads the manager, and leaves startup separate:
  `systemctl --user enable --now omniroute.service`. The existing new-WSL client-config writer renders the Codex
  `omniroute` profile on 21128; it does not render systemd units. Claude keeps native sign-in and invokes GPT lanes
  through that Codex profile. Fresh accounts sign in natively with the absolute canary CLI and
  `--base-url http://127.0.0.1:21128 oauth start --provider codex --no-browser` only when absent.
  Both doctor checks call `~/.local/bin/omniroute` explicitly with the service's DATA_DIR and port; `/readyz` must pass
  before the liveness doctor. `--stage after_sign_in` uses the nonsecret `keyless-loopback` placeholder and requires
  exit 0, native `turn.completed` and the fixed response. `config/omniroute-canary-evidence.json` binds the original
  B5a gate exits, package digest, independent canary read-back and already passing clients-2 Codex turn.
  That turn used a skills task, not this new fixed-prompt recipe. The five-test counts remain unknown.
  npm 3.8.51 remains rollback; the workstation's separately qualified 3.8.50 registry pin stays a separate scope.
- **`betterleaks`** keeps v1.9.0 through mise. `accept.sh --only betterleaks` runs the unchanged upstream
  `make test` target at `81aff7a6` with the upstream Go 1.25.12 toolchain through process-scoped `mise exec`, then
  a redacted native directory smoke limited to the plan. `make` and a C compiler are prerequisites; the default full
  plan supplies them through its research and srt dependencies. This qualifies installation only.
  **Gitleaks 8.30.1 remains the required CI and shared pre-commit scanner.** No hook migration occurs in this wave.
  Preregistered P1 must qualify betterleaks v1.9.0 before 2026-10-20; the parity corpus, class-loss rule and blocking
  false-positive rule remain in `docs/decisions/2026-10-02-github-automation-practice.md`.

Sources and evidence boundaries are in the corresponding fix-wave section of [SOURCES.md](SOURCES.md).
The base row now has acceptance despite installing nothing; `check_plan.py` scopes this exception to that row alone.
The row order, owners table and installation counts are unchanged. The coordinator owns shared narrative/count updates,
evidence-registry digests and the upstream-freshness snapshot following the srt selector move.

## Integrated fix-wave boundary (2026-10-04)

[The coordinator decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave.md) records all 25 slot repairs, conflict resolutions, canonical Promptfoo owner-batch reconciliation, sources and remaining host gates. The revised merged recipes are UNRUN on a distribution. Earlier per-row statements are historical; no static integration check certifies the destination.

## Round 2: agent messaging (2026-10-04, relaxed 2026-10-06)

The `agent-messaging` row installs adopted hcom 0.7.27 with its upstream
checksum-verifying installer. It applies the slot's extension of
`adoption/new-wsl/client-config-map.json`, using the scoped
`config/hcom-client-config.py` adapter and the shared mapper's existing
instruction-block and atomic-write functions. It writes hcom's title/relay/trust
preferences and both clients' peer hints. Since
[the 2026-10-06 relaxation](../../../docs/decisions/2026-10-06-hcom-relaxation.md)
it writes no Claude hcom deny rule and no Codex rule file: upstream `hcom.rules`,
which `hcom codex` writes, is the only Codex hcom policy.

Run `bash install.sh --only agent-messaging`, then
`bash accept.sh --only agent-messaging`. The apply does not wait for Codex to
close; running Claude Code and Codex sessions read the new instruction block
when they next start. Native client sign-ins and each lane folder's trust remain
the user's own inputs. Existing conflicting hcom configuration is retained with
`needs_user`, without printing its values; a different Claude inbound choice is
retained. The installer needs no sudo. Post-install acceptance checks the
installed binary's status/list/send/listen behavior in a disposable HCOM_DIR; it
is separate from upstream repository-quality CI. After the first `hcom codex`
launch, the after-sign-in check takes the Codex home the way hcom does
(`CODEX_HOME`, else the parent of `HCOM_DIR`). It then evaluates every `*.rules`
file there, as Codex loads them, with the native `codex execpolicy check`.
`hcom send` and `hcom term` must both be allowed. A stricter leftover file, such
as the retired `hcom-deny.rules`, reports `needs_user`, and so do the retired
Claude hcom deny entries. The retained probe is in
`../hcom-relaxation-20261006/probe-receipt.json`.

Claude <-> Claude stays on native messaging. Codex transport sessions use
upstream `hcom codex`; this row creates no Claude hcom launch wrapper or global
hooks. Plain Claude uses `hcom start` and `hcom listen`, which does not wake an
idle plain Claude. The OS-sandbox choice is the user's and outside this row.
Adoption sources, evidence classes and the hook-gap correction:
[round-2 messaging decision](../../../docs/decisions/2026-10-04-round2-plan-g1-messaging.md).

The coordinator must refresh shared summary counts and `owners.json` when the
parallel groups integrate; this bounded job leaves those shared headers intact.

## Round-2 G3 tool owners (2026-10-04, UNRUN)

The `wave5` owner batch adds four plan rows. The source review and boundaries are
in [the G3 decision](../../../docs/decisions/2026-10-04-round2-plan-g3-tools.md).
These are planned destination commands; this builder ran no candidate trial.

| Slot | Install and upstream acceptance | User-dependent destination gate |
| --- | --- | --- |
| `lm-program-optimization` | DSPy 3.4.0 and its exact GEPA 0.1.4 wheels, verified against PyPI SHA-256 values, in one dedicated uv project. Preserve the resolved `uv.lock` and installed inventory privately. Run the unchanged upstream GEPA and Predict pytest files. | Existing OmniRoute provider readiness for the documented DSPy LM call. Skill-description optimization remains with skill-creator. |
| `skill-vetting` | SkillSpector CLI from tag commit `c7958a3268d9498644b22edb75d0f051bbc8cbfc`, using upstream `uv tool install` without `[mcp]`. Run its unchanged CLI and native-client adapter tests. Record the actual tool dependency inventory; the upstream project lock does not lock a uv tool. | Native Codex sign-in only for semantic acceptance, with `SKILLSPECTOR_PROVIDER=codex_cli`. Findings remain advisory beside source review and skills.sh audits. |
| `trajectory-analysis` | Use a dedicated Scout0.5.3 uv environment with pinned Inspect0.3.273/Harbor0.23.0 ATIF schemas, OpenAI>=2.20,<3 and LiteLLM1.92.0. Preserve separate Inspect/OpenAI3.24 and Harbor owners. Verified release wheels with --no-build. Run unchanged grep/Claude/ATIF tests with Harbor import required. | Set `SCOUT_CLAUDE_SESSION_FILE` to a current session with a known Agent/Task call and `SCOUT_HARBOR_ATIF_FILE` to one existing trial. Consent to private local storage, including upstream same-slug session merging. The native import/scan must finish without errors and detect the Claude positive control. |
| `mcp-protocol-conformance` | On demand through `npx --yes @modelcontextprotocol/conformance@0.2.0-alpha.11`. Verify published SHA-512 integrity and run the unchanged upstream npm check/build/test commands. `list --requirements` is discovery. | Select an HTTP MCP endpoint with `MCP_CONFORMANCE_SERVER_URL` and/or a scenario client with `MCP_CONFORMANCE_CLIENT_COMMAND`. Supply a reviewed `MCP_CONFORMANCE_EXPECTED_FAILURES` YAML only when needed. |

The conformance row requires `--only mcp-protocol-conformance` in both scripts;
the default run skips it. It installs no global npm executable. Keep alpha.11
until alpha.12 is eligible at 2026-10-08T12:07:36Z; updating the pin requires the
existing release-verification procedure. Inspector keeps its own interactive
and smoke-test slot. The Scout grep check uses the local upstream harness and
requires no model; this plan handles Codex trajectories through Harbor ATIF.

Both native clients can invoke these tools through their existing shell and
PATH wiring. DSPy runs with
`uv run --project "${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools/dspy-3.4.0" --frozen --no-sync`.
Skill vetting uses `skillspector scan <artifact> --no-llm --format json --fail-on-findings`
on demand; a finding never authorizes an install. Scout uses `scout`, exposed
from its own Scout environment; Inspect/OpenAI3.24 and the Harbor owner stay separate. There is no new client setting, hook or
MCP registration for these slots. Tool commands use user scope; `needs.sudo`
declares the existing wrapper's clean-host apt prerequisite.

Full pin, checksum and test citations are in each row and
[SOURCES.md](SOURCES.md). The coordinator integrates `owners.json`, shared
row/stage comments and the evidence registry; this job edits only its rows and
sections.

## Wave 5 browser owner: `playwright-cli` (2026-10-04)

The existing slot now installs Chrome DevTools MCP 1.10.1 from
ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df,
release `chrome-devtools-mcp-v1.10.1`, by default. One `chrome-devtools` stdio
registration in each native client serves browser automation and diagnostics.
Both use `npx -y chrome-devtools-mcp@1.10.1 --headless --isolated
--no-usage-statistics`. The upstream experimental CLI and Claude plugin are not
registered. The former Playwright CLI measurement install is superseded; its
unstarted, 20-task comparison through upstream Harbor remains an owner-reported
removal check. This builder performs source review and the required structural
checks, with no new browser or model trial.

The privileged prerequisite is explicit in the row's `needs.sudo` and
`prerequisite_steps`: the declared program must equal the actual helper.
The helper verifies Google's active primary key fingerprint, installs its public
keyring and a restricted Signed-By in native-stack-google-chrome.sources, and
uses apt-get update/install for current stable and its dependencies. It sets
repo_add_once=false before installing, preserves other defaults and requires
the package-managed google-chrome.sources and google-chrome.list to be absent.
The digest-verified package postinst recreates its own .sources whenever that
file exists, even when repo_add_once is false; the separate filename avoids this
overwrite and a conflicting Signed-By. Existing package sources need operator
review. The package source and exact postinst locators are in
[the source receipt](../final-architecture-round2-20261004/repair-round2-sources-20261005.json).
Both installation and post_install record the installed Chrome version in
private acceptance state. Acceptance requires minimum 154.0.8037.97-1 and the
installed-version entry's Google repository origin, permitting later stable
builds. The MCP package retains its exact npm pin and published SRI check.

`post_install` runs six unchanged upstream test files with the release's own
`npm run test:no-build` runner. Its preparation follows the release CI:
submodules, `PUPPETEER_SKIP_DOWNLOAD=true npm ci` and `npm run bundle`.
CI prepares Chrome for Testing. This row sets the documented
`PUPPETEER_EXECUTABLE_PATH` to the installed Linux-side Google Chrome stable for
its unchanged tests and also exercises that browser through both native clients. Remaining
upstream suites and other CI matrix jobs are omitted, not claimed passed.

`after_sign_in` needs the destination's native Claude Code and Codex sign-ins.
Fresh sessions must each navigate the local synthetic fixture, return its title
through `take_snapshot`, and return its console marker through
`list_console_messages`. The checker matches actual successful tool results
with native invocation events; assistant summaries alone cannot pass. Raw
streams and upstream-test output remain under the private acceptance state,
outside the checkout. READY requires both stages to return success.

The destination map and its template additions own both registrations. Native
CLI read-back asserts their exact arguments, accepting the indentation in
Claude's Command and Args fields. [The browser decision](../../../docs/decisions/2026-10-04-round2-plan-g2-browser.md)
records the single writer and the destination acceptance still owed.

Sources and scope: [SOURCES.md](SOURCES.md), "Wave 5 browser owner". The npm SRI
is an upstream checksum; browser installation is verified by signed apt metadata.
`--no-usage-statistics` does not disable optional CrUX URL lookups;
upstream documents `--no-performance-crux` for that separate choice.

## Round-2 G4 configuration (2026-10-04)

[The bounded decision](../../../docs/decisions/2026-10-04-round2-plan-g4-config.md)
implements four configuration verdicts on the existing owners. Destination
execution remains UNRUN; this builder runs repository checks only.

| Existing owner | Configuration and native acceptance | Remaining input |
| --- | --- | --- |
| Promptfoo 0.123.1 | Its Test Agent Skills providers select the host's Claude and Codex executables through `path_to_claude_code_executable` and `codex_path_override`. Native Codex/openai carries Sol/max and its existing login. Post-install also checks both optional SDK dependencies; the existing upstream echo controls and paired skill controls remain. | Native sign-in if absent; the existing gateway A/B template's two exact provider model IDs. |
| GPT Researcher v3.7.0 and embedded DeerFlow v2.1.0 | Both gatherers use OmniRoute `/v1` with keyless search and per-run x-omniroute-session-id headers. On 3.8.51, smart/strategic GPT Researcher and DeerFlow request plain Sol/xhigh; FAST retains its high alias. DeerFlow enables supports_reasoning_effort. Preflight/configuration read-back and fresh successful logged Sol routes are asserted. Default call-list metadata exposes no delivered-effort field, so wire effort remains unasserted; pipeline capture remains an operator decision. A window/model fallback cannot prove attribution or whole-run zero embeddings. Native Codex uses native Sol/max. | Live cited gatherer runs and independent gateway metadata observation remain owed. Delivered wire effort is not certified by this recipe. |
| OmniRoute 3.8.51 (selected recipe) | The recipe uses the published npm package with its registry SHA512 integrity, upstream doctor/readiness acceptance and a fresh pool/fallback turn. The client-config map renders Sol/xhigh. [The topology record](config/gpt-gateway-topology.json) assigns Sol/max to native Codex until a release includes PR #15167. Historical canary assets remain for historical tests and are not installed by this row. #637 already qualified the stack's 3.8.51 pin; the architecture now cites that existing pin. | Provider sign-in if absent; review a differing existing destination service unit. Start the installed user unit before service-health acceptance. |
| Harbor 0.23.0 | Verify the published wheel SHA256 and run unchanged upstream ATIF unit tests. Retain the hello-user oracle/nop READY gate. Add [the worker telemetry-contract recipe](config/harbor-worker-telemetry-contract.md), using Harbor's native job runner and trajectory validator. | A maintained, commit-pinned native-verifier task corpus, public Harbor job config and container-reachable provider/Collector inputs. The recipe reports `needs_user` while these are absent. |

Harbor remains the containerized task-level A/B owner and skill-creator remains
the authoring owner. Telemetry producers and the Collector retain their own
slots. The research consumers keep the verdict's exact model spelling;
no source or version check establishes gateway Sol/max or a live research run.
Sources, integrity values and the named removal comparisons are in
[SOURCES.md](SOURCES.md) and the bounded decision. Shared row order and headers
are unchanged; the coordinator integrates the other groups and registry digests.

## Round-2 integration, 2026-10-05

Wave 5 adds four owner rows and makes agent-messaging (hcom 0.7.27) and
playwright-cli (Chrome DevTools MCP 1.10.1) owner defaults. The configuration
map owns Chrome's one stdio registration in each native client. OmniRoute
installation and acceptance follow published 3.8.51; retained carried-prefix
composition checks do not substitute for that release's identity. Harbor
qualifies worker telemetry, Promptfoo carries the paired skill-lifecycle
configuration, and both research gatherers keep their documented LLM route.
Source: this PR:docs/decisions/2026-10-04-final-architecture-round2.md:19;
this PR:docs/decisions/2026-10-03-omniroute-3851-pin.md:108.

The shared inventory above comes from the actual final plan rows. owners.json
was regenerated using the original U2 gen_plan.py owner_row export and its
serializer, located with rg; no owner row was hand-written. The host stack,
upstream snapshot, evidence registry and shared gateway template remain under
their owners. Source: this PR:tests/test_stack_lifecycle.py:21. Destination
installation, upstream runtime tests, native model/browser acceptance and
provider/GPU checks have not run in this integration job.

## Currency qualification limits (2026-10-05)

Selected 0.162.0; qualified on scratch/synthetic validation only (evidence/receipts/otelcol-contrib-0162-qualification-20261003.json:11-15); host acceptance pending. NativeStack2604 release hold: the release-tag build-and-test failed (docs/decisions/2026-10-04-2604-e2e-fix-wave.md:117).

Selected 13.2.3 in the WSL profile/install plan; qualified on scratch/synthetic validation only (W1b receipt:11-14, https://github.com/seathatflowsinourveins/native-agent-stack/blob/748f701e1ac871dca378f9ef41bfd81e457cb3f7/evidence/receipts/grafana-1323-qualification-20261003.json#L11-L14); host acceptance pending. NativeStack2604 release hold: open regression reports grafana/grafana#133835 and #133856 (docs/decisions/2026-10-04-2604-e2e-fix-wave.md:117). The host stack remains 13.2.2 at this head.

The staged native acceptance commands remain unrun by this repair. Neither scratch receipt closes the release holds or proves destination service acceptance.

[The coordinator decision](../../../docs/decisions/2026-10-04-2604-e2e-fix-wave.md) records all 25 slot repairs, conflict resolutions, canonical Promptfoo owner-batch reconciliation, sources and remaining host gates. The revised merged recipes were UNRUN when this boundary was recorded. Earlier per-row statements are historical; no static integration check certifies the destination.

## Acceptance defect repairs (2026-10-05)

[The repair decision](../../../docs/decisions/2026-10-05-ns2604-acceptance-defect-repairs.md)
records the NativeStack2604 failures, upstream sources, retained failed attempts and narrowed controls.
Fresh Claude sessions use the upstream CLI directly, keep native settings/hooks, and put the task
before variadic tool flags. The duplicate launcher helper was removed under the official-upstream rule;
native turn limits, appended instructions and caller options remain in the acceptance commands.
Inspector's fresh clients execute [the frozen probe](inspector-client-probe.sh); independent native
completion, hash, artifact and closed-port checks remain required.
Inspector checks all local TCP states before binding its separate port and rejects a host whose
ephemeral allocator includes it; cleanup observes the owned process and listener. Worktrunk keeps
fresh-client cache writes inside its owned run directory. The client-map endpoint parity check, carrier holdout
description and incremental skill-inventory correction are included. This qualifies the repaired
stages only; it does not certify all install-plan rows or close independent review disposition gates.

[The sanitized host receipt](fixwave-20261005-receipt.json) records every repaired stage's final
exit code, retained failed attempts, local checks and independent observations. Earlier passing
evidence is reused only for unchanged stage inputs. Raw streams and actual host paths stay private.


### Follow-up acceptance defects 7, 11 and 12

The worker's default-tmux prerequisite mismatched its already configured subprocess
backend under Linux Unix-socket blocking. The unchanged upstream subprocess execution
test passes under both isolated SRT pins; the final foreground fresh-client worker
stage passes with the block retained. SRT 0.0.78 was already the plan's original pin,
so this does not demonstrate a version regression.

DeerFlow retains keyless DDGS and uses its shipped headless JSON CLI with an explicit
100-step bound. Failed runs retain separate native gatherer and empty-search availability
outcomes; neither availability-only nor partial output qualifies research acceptance.
The measured Tavily adapter remains a conditional proposal requiring the command
center's owner ruling. Five older fresh-session recipes explicitly run commands in
the foreground, wait, and use the upstream per-call background control. Their changed
invocations need new native qualification; the receipt above remains historical for
those earlier inputs. Follow-up host results and final validation are recorded
separately; no whole-plan acceptance or provider-owner selection follows.

### NS2604 follow-up results, 2026-10-05

The [follow-up receipt](fixwave-20261005-followup-receipt.json) records new foreground
Difftastic, Worktrunk, Inspector and both SRT client stages returning zero, plus the
worker's independently observed successful jobs under its unchanged socket policy.
The direct keyless DeerFlow CLI completed with eight substantive searches, two empty
DDGS responses and linked final citations. Availability and gatherer completion stay
separate; Tavily remains a conditional proposal.

The overall research stage returned one when its fresh Claude session hit the native
session limit; its Codex branch did not run. Cross-family review returned outer124
with the same native limit in its Claude branch, while GPT completed. These failures
remain open gates and are not replaced by earlier passing evidence. The original
receipt above retains historical input scopes. Follow-up publication stays draft
until the required rebase after #713 lands and the command center's cross-family read.

D-ollama-2 local integration:321touched tests passed with3existing skips; native local-model-server post_install, service_health and after_sign_in each returned0. Health loads the embedder on demand before exact positive GPU-residency validation; an independent GET observed size=size_vram=2857191341. The separate unchanged after_sign_in makes its own embedding request. These checks do not establish cold loading, later idle expiry or complete host acceptance. Source and result identities are in the followup receipt; no host unit or warmup was changed by this lane.

## Gate-1 row repairs (2026-10-06)

Inspect, Scout and Harbor resolve in independent uv environments. Scout retains its historical manifest owner identity, requires the Harbor Trajectory import before its unchanged tests, and uses its own interpreter and guarded alias. The hcom smoke selects the first native identity marker. SkillSpector receives a validated model from checked-out canonical topology, reads the native issues field and requires actual successful model-call counters even when the safe report skips inapplicable meta-analysis. DeerFlow metadata follows the landed Sol-max composition; the keyless provider remains unchanged.

MCP conformance preserves all upstream tests and contains their server trees in unprivileged user/PID/network namespaces with only loopback up, because several examples provide no host binding setting. The acceptance-only helper retains raw test stdout and fails on remaining owned processes or listeners; EXIT/INT/TERM cleanup revalidates process ownership. The external on-demand target remains unqualified until its owner supplies an in-namespace native SDK startup command or fixture. Missing target 78 means needs_user, not a protocol pass. See [the decision](../../../docs/decisions/2026-10-06-native-plan-gate1-repairs.md), [sources](SOURCES.md) and the separate gate-1 receipt. Local integration does not constitute full host or provider acceptance.
