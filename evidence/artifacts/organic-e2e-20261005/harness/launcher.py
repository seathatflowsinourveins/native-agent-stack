#!/usr/bin/env python3
"""promptfoo exec: launcher for one trial (§4.1 launcher contract). Thin: no scheduling, no retries, no deletion.

promptfoo's ScriptCompletionProvider runs `execFile(cmd, [...args, prompt, JSON(options), JSON(context)])` with
cwd = config.basePath (the run root). The shim launchers/<cell> calls this file with the cell name first.

Steps (numbering as in §4.1): read argv; trial_id = uuid4; pre-launch ledger row; extract the hashed fixture to
NEUTRAL_ROOT/<8 hex>/ and build the per-trial settings file (Claude) or CODEX_HOME clone (Codex); Claude takes the shared
lock on a file descriptor and reads the meter inside it; the native line runs from bash -lc under timeout in a clean
login environment; a Claude stream is tailed for rate_limit_event and killed on the §9.1 thresholds; after exit the
fixture is hash-manifested, ./draft/ is copied to the run root, nothing is deleted; exactly one JSON line is printed and
the exit status is always 0, so promptfoo can never relaunch a paid session.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CLAUDE_LOCK, KILL_AFTER, KILL_FIVE_HOUR, KILL_FIVE_HOUR_RISE, KILL_SEVEN_DAY, LANE, LOCK_WAIT_S,  # noqa: E402
                    PRIOR_FIVE_HOUR, PRIOR_SEVEN_DAY, T_SECONDS, append_jsonl, clean_login_env, gateway_build, load_json,
                    manifest_digest, newest_meter_reading, prior_allows, rate_limit_readings, s7_compare, s7_snapshot,
                    sha256_bytes, sha256_file, tree_manifest, utc_now, write_json)

RATE_LIMIT_WORDS = ("rate limit", "rate_limit", "429", "usage limit", "too many requests", "quota")


class Censored(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def run_root() -> Path:
    return HERE.parent


def ledger(root: Path, row: dict) -> None:
    append_jsonl(root / "ledger.jsonl", row)


# ---------------------------------------------------------------------------------------------------------------------
# Process-tree watcher: nested claude or codex sessions (§8.4).

def _proc_table() -> dict[int, tuple[int, str, list[str]]]:
    table = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
            exe = os.path.realpath(f"/proc/{pid}/exe")
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            table[pid] = (ppid, exe, [a.decode(errors="replace")[:64] for a in argv if a][:32])
        except (OSError, IndexError, ValueError):
            continue
    return table


def descendants(root_pid: int) -> list[tuple[int, int, str, list[str]]]:
    table = _proc_table()
    children = {}
    for pid, (ppid, _, _) in table.items():
        children.setdefault(ppid, []).append(pid)
    out, stack = [], [(root_pid, 0)]
    while stack:
        pid, depth = stack.pop()
        for child in children.get(pid, []):
            ppid, exe, argv = table[child]
            out.append((child, depth + 1, exe, argv))
            stack.append((child, depth + 1))
    return out


SESSION_SUBCOMMANDS = {"exec", "e", "app-server", "review", "resume", "mcp-server", "proto", "fork"}


def _claude_session_argv(argv: list[str]) -> bool:
    """A claude process runs a session only in print mode here: -p, --print or a short-flag cluster holding p. A hook or
    plugin calling `claude --version` (the ecosystem wrapper resolves to the same binary) is not a session."""
    for arg in argv[1:]:
        if arg == "--":
            break
        if arg in ("-p", "--print") or arg.startswith("--print=") or (re.fullmatch(r"-[A-Za-z]+", arg) and "p" in arg[1:]):
            return True
    return False


def nested_clients(root_pid: int, claude_bin: str, codex_bin: str) -> tuple[list[dict], list[str]]:
    """Client sessions below the trial's own client. The trial client is the shallowest claude or codex process; a
    deeper claude process in print mode, or a deeper codex process running a session subcommand, is nested. Codex's
    sandbox helper re-executes its own binary without a session subcommand and is not nested."""
    procs = descendants(root_pid)
    clients = [p for p in procs if p[2] in (claude_bin, codex_bin)]
    seen_exes = sorted({os.path.basename(p[2]) for p in procs})
    if not clients:
        return [], seen_exes
    top_depth = min(p[1] for p in clients)
    top = [p for p in clients if p[1] == top_depth][:1]
    nested = []
    for pid, depth, exe, argv in clients:
        if top and pid == top[0][0]:
            continue
        if exe == claude_bin:
            if _claude_session_argv(argv):
                nested.append({"pid": pid, "binary": "claude", "argv0": os.path.basename(argv[0]) if argv else ""})
        else:
            first = next((a for a in argv[1:] if not a.startswith("-")), "")
            if first in SESSION_SUBCOMMANDS:
                nested.append({"pid": pid, "binary": "codex", "subcommand": first})
    return nested, seen_exes


# ---------------------------------------------------------------------------------------------------------------------
# Command lines (§4.4).

def otel_attributes(trial_id: str, lane: str) -> str:
    return f"ecosystem.task.id={trial_id},ecosystem.lane={lane},service.instance.id={trial_id}"


def claude_line(cfg: dict, trial_id: str, prompt_file: Path, settings_file: Path, lane: str) -> str:
    q = shlex.quote
    return (f"OTEL_RESOURCE_ATTRIBUTES={q(otel_attributes(trial_id, lane))} "
            f"GH_CONFIG_DIR={q(cfg['gh_config_dir'])} "
            f"timeout --signal=TERM --kill-after={KILL_AFTER} {T_SECONDS} "
            f"{q(cfg['binaries']['claude']['path'])} -p \"$(cat {q(str(prompt_file))})\" --model opus --effort max "
            f"--session-id {trial_id} -n s-{trial_id.replace('-', '')[:8]} "
            f"--output-format stream-json --verbose --include-hook-events "
            f"--settings {q(str(settings_file))}")


def codex_line(cfg: dict, trial_id: str, fixture: Path, clone: Path, prompt_file: Path, last_file: Path, sandbox: str,
               effort: str, lane: str) -> str:
    q = shlex.quote
    return (f"cd {q(str(fixture))} && CODEX_HOME={q(str(clone))} OMNIROUTE_API_KEY=local-loopback "
            f"OTEL_RESOURCE_ATTRIBUTES={q(otel_attributes(trial_id, lane))} "
            f"timeout --signal=TERM --kill-after={KILL_AFTER} {T_SECONDS} "
            f"{q(cfg['binaries']['codex']['path'])} exec --json -p omniroute -m gpt-6.1-sol "
            f"-c model_reasoning_effort={effort} -c service_tier=default "
            f"-c otel.environment={trial_id} --skip-git-repo-check -s {q(sandbox)} "
            f"-o {q(str(last_file))} - < {q(str(prompt_file))}")


def claude_sdk_line(cfg: dict, trial_id: str, fixture: Path, prompt_file: Path, settings_file: Path, lane: str) -> str:
    q = shlex.quote
    return (f"timeout --signal=TERM --kill-after={KILL_AFTER} {T_SECONDS} "
            f"{q(cfg['binaries']['claude_sdk_python'])} -B {q(str(HERE / 'sdk_claude.py'))} "
            f"--trial-id {trial_id} --cwd {q(str(fixture))} --prompt-file {q(str(prompt_file))} "
            f"--settings {q(str(settings_file))} --cli-path {q(cfg['binaries']['claude']['path'])} "
            f"--otel {q(otel_attributes(trial_id, lane))} --gh-config-dir {q(cfg['gh_config_dir'])}")


def codex_sdk_line(cfg: dict, trial_id: str, fixture: Path, clone: Path, prompt_file: Path, sandbox: str, effort: str,
                   lane: str) -> str:
    q = shlex.quote
    return (f"cd {q(str(fixture))} && timeout --signal=TERM --kill-after={KILL_AFTER} {T_SECONDS} "
            f"{q(cfg['binaries']['node'])} {q(str(HERE / 'sdk_codex.mjs'))} "
            f"--trial-id {trial_id} --cwd {q(str(fixture))} --prompt-file {q(str(prompt_file))} --codex-home {q(str(clone))} "
            f"--codex-path {q(cfg['binaries']['codex']['path'])} --sdk-dir {q(cfg['binaries']['codex_sdk_dir'])} "
            f"--sandbox {q(sandbox)} --effort {effort} --otel {q(otel_attributes(trial_id, lane))}")


# ---------------------------------------------------------------------------------------------------------------------

def _lock(timeout_s: int):
    fd = os.open(CLAUDE_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.time() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.time() >= deadline:
                os.close(fd)
                return None
            time.sleep(2)


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _stop_flag(root: Path, client: str) -> Path | None:
    for name in ("STOP", f"STOP.{client}"):
        if (root / name).exists():
            return root / name
    return None


def run_client(root: Path, cfg: dict, client: str, line: str, fixture: Path, stream_path: Path, err_path: Path,
               meter_source: dict | None) -> dict:
    """Run the line and watch it. Returns rc, the kill reason (if the launcher killed it), meter readings and the
    process-tree observations."""
    env = clean_login_env()
    claude_bin, codex_bin = cfg["binaries"]["claude"]["realpath"], cfg["binaries"]["codex"]["realpath"]
    with open(stream_path, "wb") as out, open(err_path, "wb") as err:
        proc = subprocess.Popen(["bash", "-lc", line], cwd=str(fixture), env=env, stdout=out, stderr=err,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    started = time.time()
    offset, buffer = 0, b""
    first, last, readings = None, None, 0
    kill_reason, nested_seen, exes = None, [], set()
    rate_limit_error = False
    next_tree = 0.0
    while True:
        rc = proc.poll()
        try:
            with open(stream_path, "rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
            offset += len(chunk)
            buffer += chunk
        except OSError:
            chunk = b""
        lines = buffer.split(b"\n")
        buffer = lines.pop()
        for raw in lines:
            raw = raw.strip()
            if not raw.startswith(b"{"):
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if client == "claude":
                for reading in rate_limit_readings([event]):
                    readings += 1
                    last = reading
                    five, seven = reading.get("five_hour"), reading.get("seven_day")
                    if first is None:
                        first = reading
                        if meter_source is None and five is not None and seven is not None and not (
                                five < PRIOR_FIVE_HOUR and seven < PRIOR_SEVEN_DAY):
                            kill_reason = kill_reason or "meter_prior_first_event"
                    if five is not None and five >= KILL_FIVE_HOUR:
                        kill_reason = kill_reason or "meter_kill_five_hour"
                    if seven is not None and seven >= KILL_SEVEN_DAY:
                        kill_reason = kill_reason or "meter_kill_seven_day"
                    if (five is not None and first and first.get("five_hour") is not None
                            and five - first["five_hour"] >= KILL_FIVE_HOUR_RISE):
                        kill_reason = kill_reason or "meter_kill_rise"
            else:
                kind = event.get("type")
                if kind in ("error", "turn.failed"):
                    text = json.dumps(event).lower()
                    if any(word in text for word in RATE_LIMIT_WORDS):
                        rate_limit_error = True
        if time.time() >= next_tree and rc is None:
            nested, seen = nested_clients(proc.pid, claude_bin, codex_bin)
            exes.update(seen)
            if nested:
                nested_seen.extend(nested)
                kill_reason = kill_reason or "nested_client"
            next_tree = time.time() + 2
        if kill_reason and rc is None:
            _kill_group(proc)
            rc = proc.wait()
        if rc is not None:
            break
        if time.time() - started > T_SECONDS + 90:
            kill_reason = kill_reason or "wall_guard"
            _kill_group(proc)
            rc = proc.wait()
            break
        time.sleep(1)
    if kill_reason in ("meter_kill_five_hour", "meter_kill_seven_day", "meter_prior_first_event"):
        (root / f"STOP.{client}").write_text(f"{utc_now()} {kill_reason}\n")
    if rate_limit_error:
        (root / f"STOP.{client}").write_text(f"{utc_now()} rate_limit_error_in_stream\n")
    return {"rc": rc, "kill_reason": kill_reason, "duration_s": round(time.time() - started, 1),
            "meter_first": first, "meter_last": last, "meter_readings": readings, "nested": nested_seen,
            "tree_exes": sorted(exes), "rate_limit_error": rate_limit_error}


def stream_completed(client: str, stream_path: Path) -> bool:
    try:
        text = stream_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if client == "claude" and event.get("type") == "result":
            return True
        if client == "codex" and event.get("type") in ("turn.completed",):
            return True
    return False


def launch(cell: str, prompt: str, options: dict, context: dict) -> dict:
    root = run_root()
    cfg = load_json(root / "run.json")
    cell_cfg = cfg["cells"][cell]
    client, arm, kind = cell_cfg["client"], cell_cfg["arm"], cell_cfg["kind"]
    test_vars = context.get("vars") or {}
    lane = test_vars.get("lane") or LANE
    trial_id = str(uuid.uuid4())
    short = trial_id.replace("-", "")[:8]
    base = {"run_id": cfg["run_id"], "trial_id": trial_id, "cell": cell, "client": client, "arm": arm,
            "task": test_vars.get("task_id"), "instance": test_vars.get("instance"), "lane": lane,
            "repeatIndex": context.get("repeatIndex"), "testIdx": context.get("testIdx"),
            "evaluationId": context.get("evaluationId")}
    prompt_sha = sha256_bytes(prompt.encode())
    frozen_sha = test_vars.get("prompt_sha256")
    ledger(root, {**base, "phase": "pre-launch", "at": utc_now(),
                  "hashes": {"fixture_tar": cfg["fixture"]["tar_sha256"], "prompt": prompt_sha, "prompt_frozen": frozen_sha,
                             "settings_template": cfg["claude_settings_sha256"].get(arm) if client == "claude" else None,
                             "clone_rules": cfg["codex_rules_sha256"] if client == "codex" else None,
                             "label_vector": cfg.get("label_vector_sha256")},
                  "client_version": cfg["binaries"][client]["version"], "model": cell_cfg.get("model"),
                  "requested_effort": cell_cfg["effort"], "tier": cell_cfg.get("tier"), "route": cell_cfg.get("route"),
                  "gateway_build": gateway_build() if client == "codex" else None, "sandbox": test_vars.get("sandbox"),
                  "network": test_vars.get("network")})
    result = {"trial_id": trial_id, "rc": None, "censored": True, "reason": None}
    fixture = None
    lock_fd = None
    try:
        if frozen_sha and frozen_sha != prompt_sha:
            raise Censored("prompt_mismatch")
        if _stop_flag(root, client):
            raise Censored("block_stopped")
        if client == "codex" and test_vars.get("network") not in (None, "", "off"):
            raise Censored("network_on_unsupported_in_pilot")
        from fixture import extract_fixture
        fixture = extract_fixture(Path(cfg["fixture"]["tar_path"]), cfg["fixture"]["tar_sha256"])
        prompt_file = root / "prompts" / f"{trial_id}.txt"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt, encoding="utf-8")
        trial_files = {"fixture_tar": cfg["fixture"]["tar_path"]}
        prepared = {"fixture_private": str(fixture), "session_name": f"s-{short}"}
        settings_file = clone = None
        if client == "claude":
            settings_file = root / "settings" / f"{trial_id}.json"
            prepared["settings_sha256"] = write_json(settings_file, cfg["claude_settings"][arm], 0o600)
            trial_files["settings"] = str(settings_file)
        else:
            from arms import build_clone
            clone = root / "clones" / trial_id
            rules_text = (root / "codex-rules" / "organic-e2e.rules").read_text(encoding="utf-8")
            record = build_clone(clone, arm, Path(cfg["gh_config_dir"]), rules_text)
            prepared["clone"] = record
            trial_files["clone"] = str(clone)
            if not record["gate"]["pass"]:
                raise Censored("clone_gate")
        from suite import lint_text
        lint_hits = lint_text(str(fixture).replace(str(Path.home()), "~") + " " + f"s-{short}", cfg["lexicon"],
                              launch_string=True)
        lint_hits = [h for h in lint_hits if h["check"] in ("a", "f")]
        prepared["lint_f_hits"] = lint_hits
        before = s7_snapshot(trial_files)
        write_json(root / "s7" / f"{trial_id}.before.json", before, 0o600)
        ledger(root, {**base, "phase": "prepared", "at": utc_now(), **prepared})
        if lint_hits:
            raise Censored("lint_f")
        meter_source = None
        if client == "claude":
            lock_fd = _lock(LOCK_WAIT_S)
            if lock_fd is None:
                raise Censored("lock_timeout")
            if _stop_flag(root, client):
                raise Censored("block_stopped")
            meter_source = newest_meter_reading()
            allowed, why = prior_allows(meter_source)
            ledger(root, {**base, "phase": "meter", "at": utc_now(), "allowed": allowed, "why": why,
                          "reading": {k: v for k, v in (meter_source or {}).items() if k != "source_private"}})
            if not allowed:
                raise Censored("meter_prior")
        (root / "raw").mkdir(exist_ok=True)
        (root / "last").mkdir(exist_ok=True)
        stream_path, err_path = root / "raw" / f"{trial_id}.stream.jsonl", root / "raw" / f"{trial_id}.err"
        sandbox = test_vars.get("sandbox") or "read-only"
        if client == "claude" and kind == "cli":
            line = claude_line(cfg, trial_id, prompt_file, settings_file, lane)
        elif client == "claude" and kind == "sdk":
            line = claude_sdk_line(cfg, trial_id, fixture, prompt_file, settings_file, lane)
        elif client == "codex" and kind == "cli":
            line = codex_line(cfg, trial_id, fixture, clone, prompt_file, root / "last" / f"{trial_id}.txt", sandbox,
                              cell_cfg["effort"], lane)
        elif client == "codex" and kind == "sdk":
            line = codex_sdk_line(cfg, trial_id, fixture, clone, prompt_file, sandbox, cell_cfg["effort"], lane)
        else:
            raise Censored(f"unsupported_cell_kind:{kind}")
        ledger(root, {**base, "phase": "launched", "at": utc_now(), "line_sha256": sha256_bytes(line.encode()),
                      "line_shape": line.replace(trial_id, "<trial_id>").replace(str(Path.home()), "~")})
        outcome = run_client(root, cfg, client, line, fixture, stream_path, err_path, meter_source)
        completed = stream_completed(client, stream_path)
        rc = outcome["rc"]
        if outcome["kill_reason"]:
            reason = outcome["kill_reason"]
        elif rc == 124:
            reason = "timeout"
        elif rc in (137, -9, 143, -15):
            reason = "killed"
        elif not completed:
            reason = f"incomplete_stream_rc{rc}"
        else:
            reason = None
        result.update({"rc": rc, "censored": reason is not None, "reason": reason})
        after = s7_snapshot(trial_files)
        write_json(root / "s7" / f"{trial_id}.after.json", after, 0o600)
        host_compare = s7_compare(before, after)
        fixture_manifest = tree_manifest(fixture)
        write_json(root / "manifests" / f"{trial_id}.fixture.json", fixture_manifest, 0o600)
        template_manifest = load_json(cfg["fixture"]["template_manifest_path"])
        changed = sorted(k for k in fixture_manifest if template_manifest.get(k) != fixture_manifest[k])
        removed = sorted(k for k in template_manifest if k not in fixture_manifest)
        draft_src, draft_dst = fixture / "draft", root / "draft" / trial_id
        if draft_src.exists():
            shutil.copytree(draft_src, draft_dst, symlinks=True)
        else:
            draft_dst.mkdir(parents=True, exist_ok=True)
        ledger(root, {**base, "phase": "exit", "at": utc_now(), **result,
                      "completed_stream": completed, "duration_s": outcome["duration_s"],
                      "meter_first": outcome["meter_first"], "meter_last": outcome["meter_last"],
                      "meter_readings": outcome["meter_readings"], "nested_clients": outcome["nested"],
                      "tree_exes": outcome["tree_exes"], "rate_limit_error": outcome["rate_limit_error"],
                      "stream_sha256": sha256_file(stream_path), "stream_bytes": stream_path.stat().st_size,
                      "fixture_manifest_sha256": manifest_digest(fixture_manifest),
                      "fixture_changed": changed[:200], "fixture_changed_count": len(changed),
                      "fixture_removed": removed[:200], "fixture_removed_count": len(removed),
                      "draft_manifest_sha256": manifest_digest(tree_manifest(draft_dst)),
                      "host_s7": {k: v for k, v in host_compare.items() if k != "new_trust_paths_private"},
                      "host_s7_private": host_compare.get("new_trust_paths_private")})
        if not host_compare["equal"] or any(host_compare["new_trust"].values()):
            (root / "STOP").write_text(f"{utc_now()} host exposure or trust changed during {trial_id}: "
                                       f"{host_compare['changed'][:6]} new_trust={host_compare['new_trust']}\n")
        return result
    except Censored as censor:
        result.update({"censored": True, "reason": censor.reason})
        ledger(root, {**base, "phase": "exit", "at": utc_now(), **result, "launched": False,
                      "fixture_private": str(fixture) if fixture else None})
        return result
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def main(argv: list[str]) -> int:
    result = {"trial_id": None, "rc": None, "censored": True, "reason": "launcher_error"}
    try:
        if len(argv) < 5:
            raise ValueError("usage: launcher.py <cell> <prompt> <options-json> <context-json>")
        cell, prompt, options, context = argv[1], argv[-3], json.loads(argv[-2]), json.loads(argv[-1])
        result = launch(cell, prompt, options, context)
    except Exception as error:  # noqa: BLE001 - every failure is a censored trial, never a promptfoo error
        result["reason"] = f"launcher_error:{type(error).__name__}"
        try:
            root = run_root()
            with open(root / "launcher-errors.log", "a") as handle:
                handle.write(f"{utc_now()} {traceback.format_exc()}\n")
        except OSError:
            pass
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
