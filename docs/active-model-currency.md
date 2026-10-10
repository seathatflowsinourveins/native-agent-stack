# Hosted model selector currency

The [latest-models manifest](../catalogs/foundation/latest-models.json) is
generated from the native Codex catalog, OmniRoute's `/v1/models` and the
Anthropic model-list API. It selects the greatest stable generation within
the seven required hosted families: GPT Sol, Astra and Luna; Claude Opus,
Sonnet, Haiku and Fable. Additional stable Claude families are retained when
the native source declares them. Availability alone does not mean latest: both native
catalogs retain older models. Gateway `created` values describe catalog
construction and are never used as model release dates.

## Generate and check

Collect all three native JSON catalogs into a dated private snapshot. Use
the installed `codex debug models` command, the configured OmniRoute models
endpoint and Anthropic's paginated `GET /v1/models`. The existing credential
runner supplies the declared Anthropic variable to the metadata-only runtime;
never put a value in commands or records. No Claude process, SDK inference
or model invocation is needed. Preserve the raw captures and their timestamps.

```sh
python3 scripts/active_model_currency.py generate \
  --codex /private/model-snapshot/codex-models.json \
  --omniroute /private/model-snapshot/omniroute-models.json \
  --claude /private/model-snapshot/claude-models.json \
  --recorded-at 2026-10-09T20:31:55Z \
  --output catalogs/foundation/latest-models.json

python3 scripts/active_model_currency.py check --root . --json
```

The recording label describes the bundle; it is not copied into the source
observation times. Source-embedded `fetched_at`, `captured_at` or `observed_at`
values are retained individually. A source without such metadata has a null
observation time and an explicit timestamp origin. The original shared
2026-10-09 label is preserved as a declaration, not an independently attested
capture time. The manifest carries source hashes and counts without claiming
that a new generation or recording label refreshed old input.
Codex 0.162.0's native export uses `OnlineIfUncached`; a successful export
can be cached or a fallback. The manifest explicitly does not certify a
fresh upstream network fetch, a delivered effort tier or routing quality.
OmniRoute's advertised effort aliases are accepted only when observed in
the captured catalog. For v3.8.51, requested Sol `max` is capped at `xhigh`;
the model ID check does not override or qualify that transport behavior.

Check exits **0** for current declared selectors, **1** for stale selectors,
and **2** when the manifest or scan cannot answer. The committed
`versioned_snapshot` is a retained comparison reference and does not expire
after 24 hours. Its `current` result means selectors match that declared
snapshot; it does not certify today's upstream availability. Explicit live
observations retain the 24-hour age limit. Future generated/source times,
missing catalogs and invalid alias targets remain incomplete. No check switches
models, edits user settings or silently substitutes another family.

## Active scope and preserved records

The checker extracts actual model fields, Python/environment/argument
defaults, literal Python argv lists, JSON model fields and pinned
`availableModels` lists, shell launcher flags and structured Markdown agent/template
selectors. JSON command strings and lists of whole command strings use
CPython 3.13.16's [POSIX shell lexer](https://github.com/python/cpython/blob/v3.13.16/Doc/library/shlex.rst).
Keys `command`, `commands`, `command_line` and `exec_start`, plus keys ending
in those names such as `upstream_commands` and `launchCommands`, carry
commands; camel case and hyphens are normalized. Nested command containers
retain that role. `argv`/`args` lists remain literal tokens, including quoted
text within an argument; a command list containing separate model-flag tokens
is also recognized as argv. This is lexical extraction, not shell execution
or evaluation of computed commands. Codex's short `-m` model flag retains its
meaning behind wrapper chains when Codex is the invoked program, following
[Codex rust-v0.162.0's shared option](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/utils/cli/src/shared_options.rs#L22-L23).
The checker resolves executable positions through `env`, `rtk proxy`, `timeout`,
`nice`, `ionice`, `nohup`, `flock`, and shell `command`/`exec`, consuming each
wrapper's option and pathname operands. The `ionice` contract comes from
[util-linux v2.41.3 schedutils/ionice.c:140–157](https://github.com/util-linux/util-linux/blob/v2.41.3/schedutils/ionice.c#L140-L157):
`-c`/`--class` and `-n`/`--classdata` take values; `-t`/`--ignore` is a switch.
Attached short values and clustered ignore flags work. PID, process-group and
user targeting, help and version modes do not invoke a child program.
`hcom [--go] [N] codex` follows
[hcom v0.7.28's launch parser](https://github.com/aannoo/hcom/blob/v0.7.28/src/commands/launch.rs),
consuming launcher operands such as tags and prompts before checking forwarded
Codex arguments. `timeout` requires a literal duration. Unknown launchers,
user-defined shell functions and shell keywords stop the executable walk;
the extractor does not infer a function's argument forwarding from its body.
Claude Code 2.1.296 advertises `--model`, without short `-m`. Git messages,
Python module names and ordinary operands named `codex`/`claude` do not establish
native-client context. Markdown command spans use the matching backtick
delimiters described by [CommonMark 0.31.2 section 6.1](https://spec.commonmark.org/0.31.2/#code-spans);
independent command spans stay separate. Inline formatting of individual command
tokens or a model value preserves surrounding command text. Commands outside
spans are also checked. [Fenced code, section 4.5](https://spec.commonmark.org/0.31.2/#fenced-code-blocks),
stays literal: backticks in shell comments do not suppress the command.
A pending flag can pair with the next code span on that line.
Shell operators create command boundaries in command strings; in literal argv
they remain ordinary argument data and cannot introduce another executable.
Quoted or escaped punctuation remains data in command strings too, following
[CPython v3.13.16's lexer states](https://github.com/python/cpython/blob/v3.13.16/Lib/shlex.py#L163-L218).
Each text selector field contributes only its first lexical value; its
explanatory tail is not scanned for further values and need not be shell syntax.
Structured JSON selector lists and command/argv values retain their own
traversal rules. It covers active lane configuration too; `.md` and `lanes/`
are not blanket exemptions.

The exact dated [G5 compact landscape catalogue](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ff69fc865ce72a6717a36a8f06fdac79038bd515/catalogs/landscape/grand-catalog-20261008.json)
is a comparison record whose model references are source metadata; the full
selector grammar extracts no active selections from that published snapshot.
Its exact path is exempt before the bounded text read. An active copy or another
large model-bearing source retains the ordinary selector and size-gap checks.

`--host` adds the two named user settings files,
agent directories, launcher directories, CC/co-op/API-action tools and the
named `~/code/us-equities-trading` repository when present. There is no
home-directory or disk crawl. Findings contain a locator and model IDs;
other configuration values and source lines are never printed. JSON findings
include an RFC 6901 pointer and the actual source line, so repeated values in
different fields remain separate. Comments are not selectors; sentence
punctuation is separated from prose model names while quoted runtime values
remain exact. Candidate detection streams before applying size/UTF-8 bounds;
an oversized or malformed model candidate remains a coverage gap.

Exemptions identify records by role: evidence/receipts, dated decisions and
research, native timestamped measurement objects, tests/dependencies, and
the explicitly frozen convergence experiments and named research-efficiency
replay programs/receipt listed in the implementation.
Two additional exact paths preserve their dated commands:
[`omniroute-runtime-workers/experiment.json`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a7f411faf6154329ceb592f045b4abae24168a26/blueprints/convergence-practice/omniroute-runtime-workers/experiment.json#L37)
records the September 30 trials, with an October 3 note requiring those
observations and commands to remain historical; and
[`token-efficiency-stack.json`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a7f411faf6154329ceb592f045b4abae24168a26/docs/token-efficiency-stack.json#L6)
is the dated September 27 reference edition, whose `upstream_commands` retain
the observed source-host setup. These files are explicitly exempt as records.
Regressions take both reported old-model commands from those files and require
them to be flagged at active paths, while verifying that the records keep their bytes.
A date in an active config filename does not exempt it. The maintained
new-WSL install-kit configs remain active despite the dated kit directory.
Historical sections of mixed guides are separate from their current
commands. Other lanes' N2, paper-open-e2e and STOP paths are outside this
currency scan's ownership and are not read.

The existing model-age inventory is source-review metadata for
`freshness_propose.py`; it does not select a runtime model. Its October 7
Haiku 4.5 observed-use declaration remains a dated claim requiring separate
reconciliation after owner application/readback. This check does not rewrite
it into evidence that a host switched. Local weights/package age and their
landscape exceptions remain under that existing inventory and validator.

The maintained research supervisor had an actual Opus 5 default. Its current
launch and response check now select Opus 5.5. The September 19 acceptance,
usage records and frozen comparison inputs retain the models they ran with;
this source change makes no new native execution claim.

## Currency and SessionStart wiring

Every `scripts/currency_due.py` collection invokes the offline check. A stale
selector contributes a due notice and returns 1. An incomplete model report
is a coverage gap, preserving other known counts
and any existing due notice. The collector writes known nonzero counts and
otherwise retains the prior due-file when a requested check cannot answer.
It exits 0 for a coverage-only gap and 1 when known stale model selectors exist;
the model CLI itself still returns 2 for an incomplete comparison. The
collector has seven possible counts: its five base counts, the conditional
`surface_unreviewed` count and `stale_models`. An unknown model comparison
adds the coverage message `model check incomplete`, preserving known counts
and any earlier due-file.

The daily systemd units are repository templates, not evidence of installation.
On this host the native systemd 259.5 readback returned `not-found` for
`stack-currency.timer` and an empty timer list. Host adoption remains with the
CC; this change installs or starts no unit. The service's `@REPOSITORY@` must
name the stable live clone when an operator adopts the template.

The model-audit SessionStart template and RFC 6902 user patch are withdrawn.
Startup reads only the existing precomputed `currency-due.json` summary through
the established notice handler. This follows the
[September 30 notice decision](decisions/2026-09-30-session-currency-notice.md)
and token-practice prohibition on startup audits. No user settings, hooks,
trust state or running session is changed by this repair.

The Codex-native routing identities `gpt-reserve` and `codex-auto-review` are
recorded only if present in that native capture. They do not name a model
generation; the manifest does not claim to resolve their selected backend.
An arbitrary old model cannot be declared a routing identity to pass the check.

## Primary sources and existing practice

- Installed Codex 0.162.0 `debug models`; [native CLI source](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/cli/src/main.rs#L2093).
- [Official GPT Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
  [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and
  [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) guidance.
- [Anthropic model-list API](https://platform.claude.com/docs/en/api/models/list),
  [current models](https://platform.claude.com/docs/en/about-claude/models/overview)
  and [native model alias semantics](https://code.claude.com/docs/en/model-config).
- OmniRoute v3.8.51's maintained [models route](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/app/api/v1/models/route.ts)
  and [catalog construction](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/app/api/v1/models/catalog.ts).
- [Native SessionStart hooks](https://developers.openai.com/codex/hooks) and
  this repository's existing currency collector/notice output conventions.
- CPython `v3.13.16`: [AST](https://github.com/python/cpython/blob/v3.13.16/Lib/ast.py),
  [shell lexer](https://github.com/python/cpython/blob/v3.13.16/Lib/shlex.py),
  [JSON decoder](https://github.com/python/cpython/blob/v3.13.16/Lib/json/decoder.py)
  and [subprocess environments](https://github.com/python/cpython/blob/v3.13.16/Lib/subprocess.py).
- Git `v2.53.0` [commit options](https://github.com/git/git/blob/v2.53.0/Documentation/git-commit.adoc):
  `-m` supplies the commit message. CPython `v3.13.16`
  [command-line options](https://github.com/python/cpython/blob/v3.13.16/Doc/using/cmdline.rst)
  define Python's distinct module flag. The model checker uses neither as a model selector.
- Codex `rust-v0.162.0` at `c1382380de69521303b416720a52f42d51af6248`:
  [native cache timestamp/identity](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/models-manager/src/cache.rs)
  and [native refresh strategies](https://github.com/openai/codex/blob/c1382380de69521303b416720a52f42d51af6248/codex-rs/models-manager/src/manager.rs).
- [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901) defines JSON pointer escaping;
   [RFC 6902 section 4.1](https://www.rfc-editor.org/rfc/rfc6902#section-4.1) requires
  an existing parent for array append, supporting withdrawal of the unsafe proposal.
- systemd `v259.5` [systemctl semantics](https://github.com/systemd/systemd/blob/v259.5/man/systemctl.xml)
  distinguish unit state/readback from a proposed unit file. The host absence
  above was measured through the already existing user-manager socket.

The landscape also checked `taygetea/model-currency` at
`d643fcd076f0c7e7d1d5e8dc55e0e6cfe699f4bd` and `anomalyco/models.dev` at
`4b064e049788abeabe24910bb96f260e3c931d92`. Their catalogs provide useful
leads but do not supply this host's three native catalogs or active-selector
policy. This implementation extends the existing stdlib repository workflow
without a new catalog or gateway dependency.
