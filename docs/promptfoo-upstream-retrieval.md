# Promptfoo: a real upstream retrieval example

The current [native report](http://127.0.0.1:17500/promptfoo.html) executes
NVIDIA's published Nemotron retrieval example against the installed local model.
It replaces the former two-case echo report as the served view. The prior export
is retained privately for rollback; historical receipts are unchanged.

Promptfoo 0.123.1's native `exec:` provider runs the upstream Python program,
which owns its four queries, four documents and similarity calculation. Its
only modification is replacing NVIDIA's example endpoint with this host's
loopback endpoint. A separate, local JavaScript assertion checks that each
printed row has four finite scores and uniquely ranks the published paired
document first. No test data or provider responses were invented.

The September 21 execution returned **4/4 paired documents first**, one passing
Promptfoo case, zero failures and zero errors. The report displays the complete
returned matrix. The detail drawer, search and failure filter were exercised,
and the screenshot was inspected. Served bytes match the native HTML export.

This is upstream-example compatibility, not MTEB, a held-out benchmark or
evidence of general retrieval superiority. The assertion operates on NVIDIA's
rounded printed scores. The native report remains a static captured export.

## Repeat on a configured host

Use the existing Python environment for the installed embedding server; it needs
NumPy and requests. Keep the selected model and its local endpoint explicit.
Create an isolated working directory and use the
[Promptfoo config](../examples/promptfoo-nemotron-upstream/promptfooconfig.yaml).

Fetch NVIDIA's pinned model card with its native HF command:

```sh
hf download nvidia/Nemotron-3-Embed-1B-BF16 README.md \
  --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 \
  --local-dir ./model-card --format json
```

Copy the first Python block under **Recommended Retrieval Endpoint** into
`upstream-example.py` beside the configuration. Preserve the original copy;
change only `URL` when your local service uses another port. Do not substitute
private prompts or generated fixtures. The observed execution used the existing
vLLM 0.25.0 environment and `http://127.0.0.1:8231/v2/embed`.

Use a task-specific `PROMPTFOO_CONFIG_DIR` for the evaluation database and set
`PROMPTFOO_DISABLE_TELEMETRY=1`. Ensure `python` resolves to the selected existing
environment, then run the unchanged native command:

```sh
promptfoo eval -c promptfooconfig.yaml --no-cache -j 1 \
  -o results.json report.html
```

The official exports preserve native output and metadata. `promptfoo view -n`
can display the same scoped evaluation database when a native interactive server
is wanted; that optional server was not started by this qualification.

## Accounting and recovery

The upstream script prints a matrix, not token usage. Promptfoo therefore emits
zero token/cost placeholders. These mean **unreported**, not zero consumption or
savings; the test description says so inside the native detail drawer.

Separate vLLM metric snapshots increased by 336 prompt tokens and eight completed
sequences during the final evaluation window, consistent with the example's
eight texts in two HTTP requests. This is model-scoped observation, not exclusive
per-evaluation billing or a lifetime-savings figure. Do not sum the two repeated
successful evaluations as independent quality evidence.

The first successful run was retained before adding the clearer usage label and
rerunning. Browser automation initially used a stale ref and then an incorrect
row-count text expectation; those failures remain in private evidence. Fresh
refs and direct rendered-result visibility verified the recovered checks.

Restore the prior captured HTML if rolling back this served view. No model,
service, provider account, memory page or shared catalog manifest was changed by
the Promptfoo integration.

## Sources and returned results

- [NVIDIA pinned example](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/blob/c0c9fea93ea424587517f2c59e20db9f1d6bf615/README.md)
- [Promptfoo native script provider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/providers/custom-script.md)
- [Promptfoo JavaScript assertion contract](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/configuration/expected-outputs/javascript.md)
- [Qualification manifest](../evidence/artifacts/promptfoo-nemotron-upstream-20260921/qualification.json)
- [Returned JSON, with the local result UUID replaced](../evidence/artifacts/promptfoo-nemotron-upstream-20260921/results.public.json); the untouched native export is retained privately and its hash is in the qualification manifest.
- [Native HTML export](../evidence/artifacts/promptfoo-nemotron-upstream-20260921/report.html)
- [Returned command stdout](../evidence/artifacts/promptfoo-nemotron-upstream-20260921/promptfoo-eval.stdout)
- [Returned command stderr](../evidence/artifacts/promptfoo-nemotron-upstream-20260921/promptfoo-eval.stderr)
- [Inspected native report screenshot](../evidence/artifacts/promptfoo-nemotron-upstream-20260921/native-report-detail-final.png)
