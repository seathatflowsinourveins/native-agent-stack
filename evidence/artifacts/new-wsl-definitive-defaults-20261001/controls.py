#!/usr/bin/env python3
"""Mutate one input at a time, regenerate, and require the named unittest assertion to fail.

Usage: controls.py [<worktree root>]   (default: the checkout that holds this file)
Uses Python's unittest CLI (python/cpython v3.13.15, Lib/unittest/__main__.py), as the test module does.
Each case restores the inputs, manifest and record byte for byte, including when a command fails.
A case named "generated output: ..." plants its defect in the assembler's result instead of an input: it shows that the
test sees the defect, not that the assembler refuses it. The older cases that add a line after apply_convergence work the same way.
A case named "consensus: ..." mutates the layer-consensus record: the assembler's consensus step must refuse it with the
named message, so the manifest stays as it was and the currency test fails.
"""
import json
import subprocess
import sys
from pathlib import Path

ART = Path("evidence/artifacts/new-wsl-definitive-defaults-20261001")
CONSENSUS = Path("evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json")
RECORD = Path("docs/decisions/2026-10-01-new-wsl-definitive-defaults.md")
MODULE = "tests.test_new_wsl_definitive_defaults"
CASES = [
    ("a settled row marked definitive", "test_settled_rows_are_measurements_with_verified_receipts", None),
    ("a settlement with a wrong receipt sha256", "test_manifest_is_current", "receipt sha256 mismatch"),
    ("a settlement for a slot that is not split", "test_manifest_is_current", "not a split or measurement row"),
    ("a converged slot not marked definitive", "test_converged_slots_are_definitive_except_the_known_trading_slot", None),
    ("a row without state", "test_every_row_has_state_and_measurement", None),
    ("the memory row marked as returned", "test_memory_and_code_search_measurements_have_not_returned", None),
    ("an empty settlements file", "test_settled_rows_are_measurements_with_verified_receipts", None),
    ("a final outcome for a Claude-only repository", "test_manifest_is_current", "final repository not in combined.json"),
    ("two installed rows with one job", "test_manifest_is_current", "installed job also owned by"),
    ("a slot without a decision", "test_manifest_is_current", "codex: missing decision"),
    ("a critic install with a wrong evidence sha256", "test_manifest_is_current", "prometheus: evidence sha256 mismatch"),
    ("a covering slot that installs nothing", "test_manifest_is_current", "covered_by memory-owner installs nothing"),
    ("a split row that keeps a repository", "test_pending_measurements_install_nothing", None),
    ("generated output: a final row whose GPT status is put back to the pending text", "test_no_family_status_is_stale", None),
    ("generated output: the decision rule put back to the earlier text", "test_decision_rule_states_the_current_rule", None),
    ("generated output: a resolved row without its first-round record", "test_resolved_rows_keep_their_first_round_record", None),
]


def added(doc, slot_id):
    return next(row for row in doc["add_rows"] if row["slot_id"] == slot_id)


def amendment(doc, slot_id):
    return next(entry for entry in doc["amend_rows"] if entry["slot_id"] == slot_id)["amendment"]


# One case per refusal of the assembler's consensus step: (case, the refusal it must print, the mutation of consensus.json).
# The first ten are the refusals the step was specified with. The others hold the record to its own shape and the added
# rows to the invariants that apply_convergence() enforces for the rows of the rounds.
CONSENSUS_CASES = [
    ("consensus: a slot to add that already exists", "consensus codex: slot already exists",
     lambda doc: added(doc, "skill-discovery").update(slot_id="codex")),
    ("consensus: an amendment for an unknown slot", "consensus no-such-slot: amendment for unknown slot",
     lambda doc: doc["amend_rows"][0].update(slot_id="no-such-slot")),
    ("consensus: an added row of another row kind", "consensus skill-discovery: an added row must have row_kind consensus, not added",
     lambda doc: added(doc, "skill-discovery").update(row_kind="added")),
    ("consensus: an added row marked definitive", "consensus skill-discovery: a consensus row is never definitive",
     lambda doc: added(doc, "skill-discovery").update(definitive=True)),
    ("consensus: an added row in a state the manifest does not know", "consensus skill-discovery: unknown state: accepted",
     lambda doc: added(doc, "skill-discovery").update(state="accepted")),
    ("consensus: an added row in a catalog the manifest does not know", "consensus skill-discovery: unknown catalog: tooling",
     lambda doc: added(doc, "skill-discovery").update(catalog="tooling")),
    ("consensus: an added row in a layer the manifest does not know", "consensus skill-discovery: unknown layer: skills",
     lambda doc: added(doc, "skill-discovery").update(layer_id="skills")),
    ("consensus: an amendment that carries every field the rounds decided",
     "consensus claude-code: an amendment cannot replace default, definitive, installs_nothing_extra, repository, row_kind, state",
     lambda doc: amendment(doc, "claude-code").update(default="pi", state="resolved", definitive=False, repository="",
                                                      installs_nothing_extra=True, row_kind="consensus")),
    ("consensus: a records file that is missing", "consensus records.claude_request: evidence missing",
     lambda doc: doc["records"]["claude_request"].update(path=doc["records"]["claude_request"]["path"] + ".missing")),
    ("consensus: a records file whose hash differs", "consensus records.codex_decisions: evidence sha256 mismatch",
     lambda doc: doc["records"]["codex_decisions"].update(sha256="0" * 64)),
    ("consensus: a record without one family's acknowledgement",
     "consensus records: the exchanged notes and an acknowledgement of each family are required",
     lambda doc: doc["records"].update(acknowledgements=[ack for ack in doc["records"]["acknowledgements"] if ack["family"] != "gpt"])),
    ("consensus: an added row without one of the manifest's row fields",
     "consensus skill-discovery: an added row carries the manifest's row fields: missing ['job']",
     lambda doc: added(doc, "skill-discovery").pop("job")),
    ("consensus: an added row with an outcome of the rounds", "consensus skill-discovery: an added row needs a job and an outcome that no round uses",
     lambda doc: added(doc, "skill-discovery")["resolution"].update(outcome="final")),
    ("consensus: an added row whose state and measurement disagree", "consensus research-skill: state and measurement disagree",
     lambda doc: added(doc, "research-skill").update(measurement=None)),
    ("consensus: an added row that waits for a measurement and names a repository",
     "consensus credential-custody: pending measurement installs something",
     lambda doc: added(doc, "credential-custody").update(repository="https://github.com/gethasp/hasp")),
    ("consensus: an added row whose job an installed row owns",
     "consensus skill-discovery: installed job also owned by engineering-process-skills",
     lambda doc: added(doc, "skill-discovery").update(job="engineering-process skills in both clients, installed per skill")),
    ("consensus: an amendment without its decision", "consensus claude-code: an amendment needs date_utc, by and decision",
     lambda doc: amendment(doc, "claude-code").pop("decision")),
    ("consensus: a record without its rule", "consensus: the record needs its rule, records, add_rows and amend_rows",
     lambda doc: doc.pop("rule")),
    ("consensus: a records file named without its hash", "consensus records.claude_proposals: evidence path and sha256 required",
     lambda doc: doc["records"]["claude_proposals"].pop("sha256")),
]
CASES += [(case, "test_manifest_is_current", refusal) for case, refusal, _ in CONSENSUS_CASES]


def run(root, *args):
    return subprocess.run([sys.executable, "-B", *map(str, args)], cwd=root, capture_output=True, text=True)


def mutate(root, case):
    consensus = {entry[0]: entry[2] for entry in CONSENSUS_CASES}
    if case in consensus:
        path = root / CONSENSUS
        doc = json.loads(path.read_text(encoding="utf-8"))
        consensus[case](doc)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif case in {entry[0] for entry in CASES[7:12]}:
        path = root / ART / "convergence.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        decisions = {d["slot_id"]: d for d in doc["decisions"]}
        if case == CASES[7][0]:
            decisions["claude-plugins-official-code-intelligence-lsp-pl"]["outcome"] = "final"
        elif case == CASES[8][0]:
            doc["jobs"]["codex"] = doc["jobs"]["claude-code"]
        elif case == CASES[9][0]:
            doc["decisions"] = [d for d in doc["decisions"] if d["slot_id"] != "codex"]
        elif case == CASES[10][0]:
            decisions["prometheus"]["critic"]["sha256"] = "0" * 64
        else:
            decisions["claude-plugins-official-code-intelligence-lsp-pl"]["covered_by"] = ["memory-owner"]
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif case in (CASES[1][0], CASES[2][0], CASES[6][0]):
        path = root / ART / "settlements.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if case == CASES[1][0]:
            doc[0]["receipts"][0]["sha256"] = "0" * 64
        elif case == CASES[2][0]:
            doc[0]["slot_id"] = "container-engine"
        else:
            doc = []
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    else:
        path = root / ART / "assemble_manifest.py"
        text = path.read_text(encoding="utf-8")
        # The decision rule is written into the document after the rows are final, so its defect goes in just before the return.
        before_return = case == CASES[14][0]
        anchor = ('    return json.dumps(doc, ensure_ascii=False, indent=1) + "\\n"\n' if before_return
                  else "    convergence = apply_convergence(rows, layers)\n")
        if text.count(anchor) != 1:
            raise ValueError("the assembler's mutation anchor is missing or ambiguous")
        defect = {
            CASES[0][0]: '    next(row for row in rows if row["slot_id"] == "local-model-server")["definitive"] = True\n',
            CASES[3][0]: '    next(row for row in rows if row["slot_id"] == "container-engine")["definitive"] = False\n',
            CASES[4][0]: '    del rows[0]["state"]\n',
            CASES[5][0]: '    next(row for row in rows if row["slot_id"] == "memory-owner")["measurement"]["returned"] = True\n',
            CASES[12][0]: '    next(row for row in rows if row["slot_id"] == "playwright-cli")["repository"] = "https://github.com/microsoft/playwright-cli"\n',
            CASES[13][0]: '    next(row for row in rows if row["slot_id"] == "serena")["gpt"] = "pending: the blind GPT-6.1 Sol run over the 21 first-round packets is in progress"\n',
            CASES[14][0]: '    doc["decision_rule"] = foundation["decision_rule"]\n',
            CASES[15][0]: '    del next(row for row in rows if row["slot_id"] == "codex")["resolution"]["first_round_record"]\n',
        }[case]
        path.write_text(text.replace(anchor, defect + anchor if before_return else anchor + defect), encoding="utf-8")


def main():
    if len(sys.argv) > 2:
        print("usage: controls.py [<worktree root>]")
        return 2
    root = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else Path(__file__).resolve().parents[3]
    paths = [root / ART / name for name in ("assemble_manifest.py", "settlements.json", "convergence.json", "definitive-manifest.json")]
    paths += [root / CONSENSUS, root / RECORD]
    originals = {path: path.read_bytes() for path in paths}

    def restore():
        for path, data in originals.items():
            if path.read_bytes() != data:
                path.write_bytes(data)

    baseline = run(root, "-m", "unittest", MODULE)
    if baseline.returncode:
        print("baseline tests failed")
        print(baseline.stdout + baseline.stderr)
        return 1
    failed = False
    for case, test, refusal in CASES:
        try:
            mutate(root, case)
            assembled = run(root, ART / "assemble_manifest.py")
            rendered = run(root, ART / "render_tables.py", "--write", RECORD)
            result = run(root, "-m", "unittest", "-v", MODULE)
            output = result.stdout + result.stderr
            generation_ok = rendered.returncode == 0 and (
                assembled.returncode == 0 if refusal is None else
                assembled.returncode != 0 and refusal in assembled.stdout + assembled.stderr)
            named_failure = f"FAIL: {test} ({MODULE}.Manifest.{test})"
            killed = generation_ok and result.returncode != 0 and named_failure in output
            print(f"{case}: {'killed' if killed else 'survived'} ({test})")
            if not killed:
                print(assembled.stdout + assembled.stderr + rendered.stdout + rendered.stderr + output)
            failed |= not killed
        except (OSError, ValueError) as error:
            print(f"{case}: survived ({error})")
            failed = True
        finally:
            restore()
        if any(path.read_bytes() != data for path, data in originals.items()):
            print("restoration failed")
            return 1
    final = run(root, "-m", "unittest", MODULE)
    print(final.stdout + final.stderr, end="")
    restored = all(path.read_bytes() == data for path, data in originals.items())
    print("all files restored" if restored else "restoration failed")
    return int(failed or final.returncode != 0 or not restored)


if __name__ == "__main__":
    sys.exit(main())
