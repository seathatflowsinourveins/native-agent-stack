#!/usr/bin/env python3
"""Build the R02 gateway A/B inputs: the two promptfoo run configs and the 60-filing subset.

Glue only. Every piece configures an upstream component and names it:
- promptfoo 0.123.1's HTTP provider (site/docs/providers/http.md), one provider per arm. Its header
  templates are rendered with Nunjucks over the step's vars in getHeaders (src/providers/http.ts:2394,
  2409), and those vars carry the evaluator's per-step `__evalId`, `__evalStepId` and `__repeatIndex`
  (src/evaluator.ts:744-763, 1646-1653);
- the strict response schema is derived from the tiering run's committed response.schema.json (its
  per-filing object without `accession`), never hand-copied;
- li26's own code loads the acquisition (eval_arm.load_inputs) and builds each filing's prompt
  (eval_arm.prompt_template and MARKER). The prompt's sha256 goes into the private tests file, so the
  prompt function and the assertion can check each call against it;
- strict-schema validity is promptfoo's own is-json assertion with the same schema the request sends
  (promptfoo@0.123.1 dist/src/evaluator-DlYW7Rgb.js:2509-2545, registered at :5523), at its default weight: a
  weight of 0 would turn its pass into true (:5790-5793).

`frozen` hashes the harness and every repository file the harness executes, and fails when the frozen code loads
a repository module outside that set (module_closure: every file passed to importlib.util.spec_from_file_location
and every imported module file inside the repository, from a fresh interpreter). `promptfoo` records or checks the
installed promptfoo build that `promptfoo` on PATH runs: its version, a digest of the package files outside
node_modules and the Node version. Standard library only.

  build_r02.py configs [--check]
  build_r02.py subset --acquisition DIR --state-dir DIR [--update-plan | --check]
  build_r02.py frozen [--update-plan | --check]
  build_r02.py promptfoo [--update-plan | --check]
"""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REL = HERE.relative_to(REPO).as_posix()
LI26 = REPO / "blueprints/convergence-practice/local-inference-latest-20260926"
TIERING_SCHEMA = REPO / "blueprints/convergence-practice/gpt6-family-tiering-20260926/response.schema.json"
PLAN = HERE / "plan.json"

GATEWAY_URL = "http://127.0.0.1:20128/v1/chat/completions"
INPUTS_SHA256 = "2a5c8c9bd1650bc20a3e7364defef2d725904f6eb1ef509a511a49526a32bfe0"
ARMS = {"A": {"model": "cx/gpt-6-astra", "key": "a"}, "B": {"model": "cx/gpt-6-astra-max", "key": "b"}}
ORDERS = {"ab": ("A", "B"), "ba": ("B", "A")}
SCHEMA_NAME = "li26_filing_items"
SUBSET_SIZE = 60
SUBSET_SEED = 20260927
TOP_STRATUM = 4  # filings with 4 or more items share one stratum
# promptfoo renders a function prompt's returned text as a Nunjucks template (src/evaluatorHelpers.ts:396-419,
# 505-542), so a prompt holding one of these would not reach the gateway unchanged.
NUNJUCKS_OPENERS = ("{{", "{%", "{#")
# The harness files whose bytes the plan freezes, relative to the repository root.
HARNESS = ("build_r02.py", "prompt_r02.py", "assert_r02.py", "transform_r02.js", "call_logs_by_correlation.py",
           "analyze_r02.py", "promptfooconfig.ab.json", "promptfooconfig.ba.json")
UPSTREAM_INPUTS = ("blueprints/convergence-practice/local-inference-latest-20260926/eval_arm.py",
                   "blueprints/convergence-practice/local-inference-latest-20260926/analyze.py",
                   "blueprints/convergence-practice/local-inference-latest-20260926/prompt.txt",
                   "blueprints/convergence-practice/local-inference-latest-20260926/plan.json",
                   "blueprints/convergence-practice/gpt6-family-tiering-20260926/response.schema.json",
                   # li26's eval_arm.py executes it (eval_arm.py:54-56); it imports only pathlib and stat.
                   "scripts/path_safety.py")
# Each Python entry point of the harness and the function that loads its lazily loaded li26 module.
ENTRY_POINTS = (("prompt_r02.py", "_eval_arm"), ("assert_r02.py", "_analyze"), ("analyze_r02.py", "li26"),
                ("build_r02.py", "load_li26"), ("call_logs_by_correlation.py", None))
CLOSURE_PROBE = """
import importlib.util, json, sys
from pathlib import Path
repo, entries = Path(sys.argv[1]).resolve(), json.loads(sys.argv[2])
seen, original = set(), importlib.util.spec_from_file_location
def recording(name, location=None, *args, **kwargs):
    if location is not None:
        seen.add(Path(location).resolve())
    return original(name, location, *args, **kwargs)
importlib.util.spec_from_file_location = recording
for path, loader in entries:
    spec = importlib.util.spec_from_file_location("r02_closure_" + Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if loader:
        getattr(module, loader)()
seen |= {Path(module.__file__).resolve() for module in list(sys.modules.values())
         if isinstance(getattr(module, "__file__", None), str)}
print(json.dumps(sorted(path.relative_to(repo).as_posix() for path in seen if path.is_relative_to(repo))))
"""
PROMPTFOO_SCOPE = ("files of the promptfoo package that `promptfoo` on PATH runs, outside node_modules (its dist "
                   "build and package metadata), as sha256 over the sorted '<relative path>\\0<file sha256>\\n' "
                   "lines; node_modules is not hashed")


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def load_li26():
    spec = importlib.util.spec_from_file_location("r02_build_li26_eval_arm", LI26 / "eval_arm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_schema(tiering):
    """The tiering run's per-filing object (properties.filings.items) with `accession` removed."""
    item = copy.deepcopy(tiering["properties"]["filings"]["items"])
    del item["properties"]["accession"]
    item["required"] = [name for name in item["required"] if name != "accession"]
    if item.get("additionalProperties") is not False or item["required"] != ["items"] or \
            set(item["properties"]) != {"items"} or not item["properties"]["items"]["items"].get("enum"):
        raise ValueError("unexpected tiering schema shape")
    return item


def tiering_schema():
    return derive_schema(json.loads(TIERING_SCHEMA.read_text()))


def response_format(schema):
    # Strict structured output, never json_object: the reviewed R02 design records that through the gateway
    # json_object needs the word "json" in the input messages, because the Responses translation moves the
    # first system message into `instructions` (OmniRoute@dd6e9607e:open-sse/translator/request/
    # openai-responses/toResponses.ts:120-137, read from the pinned commit).
    return {"type": "json_schema", "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": schema}}


def provider(arm, schema, url=GATEWAY_URL):
    """promptfoo HTTP provider for one arm. No sampling fields, no reasoning_effort, no Authorization."""
    key = ARMS[arm]["key"]
    return {
        "id": "http",
        "label": f"r02-{arm}",
        "config": {
            "url": url,
            "method": "POST",
            # The default is 4 silent retries (site/docs/providers/http.md:1699, 1814); 0 also caps the
            # scheduler's own retries (src/scheduler/rateLimitRegistry.ts:54, 80, 166).
            "maxRetries": 0,
            "headers": {
                "Content-Type": "application/json",
                # One session key per conversation (filing, repeat, arm, run), never an arm-wide constant.
                "x-omniroute-session": f"r02-{key}-{{{{accession}}}}-r{{{{__repeatIndex}}}}-{{{{__evalId}}}}",
                # __evalStepId has no provider index; the static arm prefix separates the arms.
                "Idempotency-Key": f"r02-{key}-{{{{__evalId}}}}-{{{{__evalStepId}}}}",
                # The same per-call value as the gateway's request id. A caller X-Correlation-Id is trimmed, has
                # CR/LF removed and is kept when 1-256 characters long (OmniRoute@dd6e9607e:src/app/api/v1/chat/
                # completions/route.ts:292-298, 322; src/shared/utils/correlationPreserve.ts:6-12) as the request
                # id (src/sse/handlers/chat.ts:436) that call_logs stores as correlation_id, one row per gateway
                # attempt (open-sse/handlers/chatCore/attemptLogging.ts:549-557, 611), and it is returned as the
                # response header (src/sse/handlers/chatHelpers.ts:1172-1187; route.ts:313-314).
                # analyze_r02.py rebuilds it for every call, including calls that fail before the transform.
                "X-Correlation-Id": f"r02-{key}-{{{{__evalId}}}}-{{{{__evalStepId}}}}",
                "X-OmniRoute-No-Cache": "true",
            },
            "body": {
                "model": ARMS[arm]["model"],
                "messages": [{"role": "user", "content": "{{prompt}}"}],
                "stream": True,
                "stream_options": {"include_usage": True},
                "response_format": response_format(schema),
            },
            "transformResponse": "file://transform_r02.js",
        },
    }


def config(order, schema, url=GATEWAY_URL):
    arms = ORDERS[order]
    return {
        "description": f"R02 gateway A/B (FW effort), arm order {'-'.join(arms)} per filing",
        "prompts": ["file://prompt_r02.py:build_prompt"],
        "providers": [provider(arm, schema, url) for arm in arms],
        # li26's scorer, then the sent schema checked by promptfoo's is-json; analyze_r02.py reads both per row.
        "defaultTest": {"assert": [{"type": "python", "value": "file://assert_r02.py:get_assert"},
                                   {"type": "is-json", "value": schema}]},
    }


def config_text(order, schema, url=GATEWAY_URL):
    return json.dumps(config(order, schema, url), indent=2) + "\n"


def config_path(order):
    return HERE / f"promptfooconfig.{order}.json"


def stratum(row):
    return min(len(row["labels"]), TOP_STRATUM)


def rank(accession, seed=SUBSET_SEED):
    return hashlib.sha256(f"{seed}:{accession}".encode()).hexdigest()


def allocate(sizes, total):
    """Largest-remainder (Hamilton) proportional allocation in exact fractions; ties go to the lower stratum."""
    population = sum(sizes.values())
    quotas = {key: Fraction(total * size, population) for key, size in sizes.items()}
    counts = {key: quota.numerator // quota.denominator for key, quota in quotas.items()}
    remaining = total - sum(counts.values())
    for key in sorted(sizes, key=lambda key: (-(quotas[key] - counts[key]), key))[:remaining]:
        counts[key] += 1
    return counts


def select(rows, size=SUBSET_SIZE, seed=SUBSET_SEED):
    """Stratified by item count (4 or more pooled), proportional allocation, and within each stratum the
    accessions with the smallest sha256("<seed>:<accession>"). In (stratum, rank) order the selection
    alternates between the AB run and the BA run, starting with AB."""
    strata = {}
    for row in rows:
        strata.setdefault(stratum(row), []).append(row)
    counts = allocate({key: len(members) for key, members in strata.items()}, size)
    chosen = []
    for key in sorted(strata):
        members = sorted(strata[key], key=lambda row: rank(row["accession"], seed))
        chosen += [(key, row) for row in members[:counts[key]]]
    selection = [{"accession": row["accession"], "stratum": key, "run": "ab" if index % 2 == 0 else "ba", "row": row}
                 for index, (key, row) in enumerate(chosen)]
    population = {key: len(members) for key, members in strata.items()}
    return selection, population, counts


def test_case(row, template, marker):
    prompt = template.replace(marker, row["input"], 1)
    if any(opener in prompt for opener in NUNJUCKS_OPENERS):
        raise ValueError(f"{row['accession']}: promptfoo would render a Nunjucks tag inside this prompt")
    # labels travel as a JSON string: promptfoo expands a list-of-strings var into one test per value
    # (src/evaluator.ts:1941-1975).
    return {"description": row["accession"],
            "vars": {"accession": row["accession"], "document": row["input"],
                     "labels_json": json.dumps(row["labels"]), "prompt_sha256": sha256_bytes(prompt.encode())}}


def tests_bytes(selection, run, template, marker):
    lines = [json.dumps(test_case(item["row"], template, marker), sort_keys=True)
             for item in selection if item["run"] == run]
    return ("\n".join(lines) + "\n").encode()


def write_private(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        os.fchmod(target.fileno(), 0o600)
        target.write(raw)


def subset_record(selection, population, counts, tests):
    return {
        "size": SUBSET_SIZE,
        "seed": SUBSET_SEED,
        "source": {"acquisition": "~/.local/state/native-agent-stack/local-inference-latest-20260926/sec/acq-20260926",
                   "inputs_sha256": INPUTS_SHA256, "rows": sum(population.values()),
                   "loader": "li26 eval_arm.load_inputs(acquisition, inputs_sha256)"},
        "algorithm": ("Stratum = min(number of labelled items, 4). Allocation: largest-remainder proportional "
                      "allocation of the 60 filings in exact fractions, ties to the lower stratum. Within a "
                      "stratum, the filings with the smallest sha256('<seed>:<accession>') hex digest. The "
                      "selection, ordered by (stratum, digest), alternates between the AB run and the BA run, "
                      "starting with AB. Code: build_r02.py select()."),
        "strata": {str(key): {"population": population[key], "selected": counts[key]} for key in sorted(population)},
        "runs": {run: [item["accession"] for item in selection if item["run"] == run] for run in ORDERS},
        "tests_files": tests,
    }


def build_subset(acquisition, state_dir, write=True):
    """Select the subset and build both tests files; write them (0600, directory 0700) or, with write=False,
    require the existing files to hold exactly the rebuilt bytes."""
    eval_arm = load_li26()
    rows = eval_arm.load_inputs(acquisition, INPUTS_SHA256)
    template = eval_arm.prompt_template(eval_arm.load_plan())
    selection, population, counts = select(rows)
    state_dir = Path(state_dir).expanduser()
    if write:
        state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(state_dir, 0o700)
    tests = {}
    for run in ORDERS:
        raw = tests_bytes(selection, run, template, eval_arm.MARKER)
        name = f"tests-{run}.jsonl"
        if write:
            write_private(state_dir / name, raw)
        elif not (state_dir / name).is_file() or (state_dir / name).read_bytes() != raw:
            raise SystemExit(f"{name} is missing or differs from the rebuilt tests file")
        tests[run] = {"name": name, "sha256": sha256_bytes(raw), "tests": raw.count(b"\n")}
    return subset_record(selection, population, counts, tests)


def frozen_record():
    record = {f"{REL}/{name}": sha256_file(HERE / name) for name in HARNESS}
    record.update({relative: sha256_file(REPO / relative) for relative in UPSTREAM_INPUTS})
    return record


def module_closure():
    """Repository-relative paths of every file the harness's Python entry points load, from a fresh interpreter."""
    entries = [[str(HERE / name), loader] for name, loader in ENTRY_POINTS]
    completed = subprocess.run([sys.executable, "-c", CLOSURE_PROBE, str(REPO), json.dumps(entries)],
                               capture_output=True, text=True, check=True, timeout=120)
    return json.loads(completed.stdout)


def closure_problems(closure, record):
    return [path for path in closure if path not in record]


def promptfoo_package(executable=None):
    """The root of the promptfoo package that `promptfoo` on PATH (or `executable`) runs."""
    executable = shutil.which("promptfoo") if executable is None else executable
    if executable is None:
        raise SystemExit("promptfoo is not on PATH")
    for parent in Path(executable).resolve().parents:
        manifest = parent / "package.json"
        if manifest.is_file() and json.loads(manifest.read_text()).get("name") == "promptfoo":
            return parent
    raise SystemExit("the promptfoo on PATH does not resolve into a promptfoo package")


def tree_digest(root, excluded=("node_modules",)):
    """sha256 over sorted '<relative path>\\0<file sha256>\\n' lines of the files under root, skipping the excluded
    top-level directories; and the number of files."""
    lines = sorted(f"{path.relative_to(root).as_posix()}\0{sha256_file(path)}\n" for path in root.rglob("*")
                   if path.relative_to(root).parts[0] not in excluded and path.is_file())
    return sha256_bytes("".join(lines).encode()), len(lines)


def promptfoo_record(executable=None, node=None):
    root = promptfoo_package(executable)
    node = shutil.which("node") if node is None else node
    if node is None:
        raise SystemExit("node is not on PATH")
    digest, files = tree_digest(root)
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True, timeout=60)
    return {"version": json.loads((root / "package.json").read_text())["version"], "node": version.stdout.strip(),
            "package_tree_sha256": digest, "package_files": files, "scope": PROMPTFOO_SCOPE}


def update_plan(key, value):
    plan = json.loads(PLAN.read_text())
    plan[key] = value
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")


def check_plan(key, value):
    recorded = json.loads(PLAN.read_text()).get(key)
    if recorded != value:
        raise SystemExit(f"plan.json {key} differs from the rebuilt value")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    configs = commands.add_parser("configs", help="write or check promptfooconfig.ab.json and promptfooconfig.ba.json")
    configs.add_argument("--check", action="store_true")
    subset = commands.add_parser("subset", help="select the subset and write the private tests files")
    subset.add_argument("--acquisition", required=True)
    subset.add_argument("--state-dir", required=True)
    subset_mode = subset.add_mutually_exclusive_group()
    subset_mode.add_argument("--update-plan", action="store_true")
    subset_mode.add_argument("--check", action="store_true")
    frozen = commands.add_parser("frozen", help="hash the harness and upstream inputs")
    frozen_mode = frozen.add_mutually_exclusive_group()
    frozen_mode.add_argument("--update-plan", action="store_true")
    frozen_mode.add_argument("--check", action="store_true")
    build = commands.add_parser("promptfoo", help="record or check the installed promptfoo build and Node version")
    build_mode = build.add_mutually_exclusive_group()
    build_mode.add_argument("--update-plan", action="store_true")
    build_mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "configs":
        schema = tiering_schema()
        for order in ORDERS:
            text = config_text(order, schema)
            if args.check:
                if config_path(order).read_text() != text:
                    raise SystemExit(f"{config_path(order).name} differs from the generated config")
            else:
                config_path(order).write_text(text)
        print(json.dumps({"schema_sha256": sha256_bytes(canonical(schema).encode()),
                          "configs": {order: sha256_file(config_path(order)) for order in ORDERS}}, indent=2))
    elif args.command == "subset":
        record = build_subset(Path(args.acquisition).expanduser(), args.state_dir, write=not args.check)
        if args.update_plan:
            update_plan("subset", record)
        elif args.check:
            check_plan("subset", record)
        print(json.dumps({"strata": record["strata"], "tests_files": record["tests_files"]}, indent=2))
    elif args.command == "promptfoo":
        record = promptfoo_record()
        if args.update_plan:
            update_plan("promptfoo_build", record)
        elif args.check:
            check_plan("promptfoo_build", record)
        print(json.dumps(record, indent=2))
    else:
        record = frozen_record()
        outside = closure_problems(module_closure(), record)
        if outside:
            raise SystemExit("the harness loads repository files outside the frozen inputs: " + ", ".join(outside))
        if args.update_plan:
            update_plan("frozen_inputs", record)
        elif args.check:
            check_plan("frozen_inputs", record)
        print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
