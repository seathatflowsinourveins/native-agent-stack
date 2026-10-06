"""Focused checks for round 4 of #786 (the harness's own module, run at nice 19, no model call):

  cd evidence/artifacts/organic-e2e-20261005/harness && nice -n 19 python3 -B -m unittest -v test_isolation

- The structural G13 (CC item task-ns2604-coop-20261006T132948Z): in a synthetic trial's namespace, `cat` on a real file
  in each hidden location fails with ENOENT or EACCES (the check fails if it can read one), its own inputs stay
  readable, the receipt carries the hidden list with its sha256s, G13 rejects a receipt that leaves a location out,
  binds an answer source back or ran outside the namespace, and the launcher's wrapped run records the namespace and
  ends the client gracefully. ISOLATION_SKIP_CLIENTS=1 leaves out the client start checks (claude, codex, the SDKs,
  codex app-server through the CL7b wrapper).
- The GPT micro-check of 1f81d645, P3: the deadline and completion decisions read the unrounded offsets, so a result
  that arrived before T is never held.
- Round 5 (CC items task-ns2604-coop-20261006T143846Z, 144256Z and 151719Z):
  - private /tmp, /var/tmp, /dev/shm and IPC;
  - the per-trial ai-memory scope and the grader's scope checks;
  - the gateway's cache and log readings, from allowlisted routes only;
  - the normal service tier;
  - G13's bind triples, ordering and options checks, with their negative cases;
  - the public receipt;
  - CL7b's census.
- P2-2, in its own commit (HostBrokers): inside a trial's namespace, the user manager (`systemd-run --user`), rootless
  Docker's socket and WSL interop are unreachable, and the runtime folder is private.
- Round 6e (GPT read of b2d44f73, two P2s):
  - the forward's access log counts every admitted model call at admission, and a call without a request id fails G11
    and the calibration (netfilter's own Filter in front of a stand-in gateway, then collection and grading);
  - stage 2's control flow in pilot.py, driven through pilot.main with a recording step (PilotStage2): the calibration
    is run, collected and checked before any other cell or retry. These start no client and no process.
  - in a commit of its own: the collection listing is read and filtered when the client asks for compression, as
    Node's fetch does (a stand-in Qdrant behind the Filter, and the two-trial test against this host's Qdrant).
These are local integration checks of this harness, not upstream acceptance."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# The structural checks need this host's bubblewrap and the experiment's roots; elsewhere (a CI runner) they skip.
HOST_READY = os.access("/usr/bin/bwrap", os.X_OK) and \
    (Path.home() / ".local/state/native-agent-stack/coordination").is_dir()
# P2-2's paths, named here rather than read from isolation.py, so the negative tests also run (and fail) on a harness
# that binds the host's runtime folder in.
READING = {"semantic_cache": {"hits": 0, "misses": 0, "dbEntries": 0, "memoryEntries": 0}}
RUNTIME = Path(f"/run/user/{os.getuid()}")
WSL_RUN = Path("/run/WSL")
WINDOWS_CMD = Path("/mnt/c/Windows/System32/cmd.exe")


def _wsl_interop_socket():
    value = os.environ.get("WSL_INTEROP")
    if value and Path(value).is_socket():
        return Path(value)
    return next((p for p in sorted(WSL_RUN.glob("*_interop")) if p.is_socket()), None) if WSL_RUN.is_dir() else None


def _synthetic_plan(client: str = "claude"):
    import isolation
    trial_id = str(uuid.uuid4())
    work = isolation.TRIAL_ROOT_BASE / f"ut{trial_id[:8]}"
    fixture = isolation.NEUTRAL_ROOT / f"ut{trial_id[:8]}"
    cfg = {"trial_root": str(work), "suite": {"path": str(isolation.SUITE_DEFAULT)},
           "fixture": {"oracles_path": str(isolation.FIXTURE_CACHE / "oracles.json")}}
    clone = work / "clones" / trial_id if client == "codex" else None
    settings = work / "settings" / f"{trial_id}.json" if client == "claude" else None
    plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, client, fixture, clone=clone, settings=settings,
                          prompt=work / "prompts" / f"{trial_id}.txt")
    return isolation, cfg, plan, trial_id, fixture, work


def _relay_log(tmp: Path, answers) -> Path:
    """netfilter's own Filter in front of a stand-in gateway on this host's loopback, one POST /v1/responses per entry
    of answers; returns the access log. An entry is the X-OmniRoute-Request-Id its response carries, None for a
    response without that header, "hang" for a call still in flight when its handler is stopped (as when the forwarder
    ends), or "down" for a gateway that no longer listens."""
    import asyncio
    import isolation
    import netfilter
    log, sock = tmp / "access.jsonl", tmp / "gateway.sock"

    async def scenario():
        async def gateway(reader, writer):
            try:
                head = await reader.readuntil(b"\r\n\r\n")
                answer = head.split(b"X-Answer: ", 1)[1].split(b"\r\n", 1)[0].decode()
                if answer == "hang":
                    await reader.read()   # until the filter closes the connection
                    return
                await reader.readexactly(2)
                extra = b"" if answer == "none" else f"X-OmniRoute-Request-Id: {answer}\r\n".encode()
                writer.write(b"HTTP/1.1 200 OK\r\n" + extra + b"Content-Length: 2\r\nConnection: close\r\n\r\n{}")
                await writer.drain()
            finally:
                writer.close()

        upstream = await asyncio.start_server(gateway, "127.0.0.1", 0)
        port = upstream.sockets[0].getsockname()[1]
        forward = {**isolation.network_for("codex", str(uuid.uuid4()))["forwards"]["gateway"],
                   "upstream": ["127.0.0.1", port]}
        filt = netfilter.Filter({"access_log": str(log), "scope": {}})
        tasks = []

        def handler(reader, writer):
            tasks.append(asyncio.ensure_future(filt.handle("gateway", forward, reader, writer)))

        front = await asyncio.start_unix_server(handler, path=str(sock), limit=netfilter.MAX_HEAD)
        for number, answer in enumerate(answers, 1):
            if answer == "down" and upstream.is_serving():
                upstream.close()
            reader, writer = await asyncio.open_unix_connection(str(sock))
            writer.write((f"POST /v1/responses HTTP/1.1\r\nHost: gateway\r\nX-Answer: {answer or 'none'}\r\n"
                          "Content-Length: 2\r\n\r\n{}").encode())
            await writer.drain()
            if answer == "hang":
                for _ in range(300):   # until this call's admission row is written
                    if log.read_text().count('"admitted"') >= number:
                        break
                    await asyncio.sleep(0.01)
                tasks[-1].cancel()
            else:
                await reader.read()
            writer.close()
        await asyncio.gather(*tasks, return_exceptions=True)
        front.close()
        upstream.close()
        filt.log.close()

    asyncio.run(scenario())
    return log


def _relay_qdrant(tmp: Path, prefix: str, requests_, always_compressed: bool = False) -> list:
    """netfilter's own Filter in front of a stand-in Qdrant on this host's loopback. The stand-in compresses its answer
    when the request it receives asks for gzip (as Qdrant 1.19.1 does), or always. Each (method, path, headers) is
    sent in turn; returns each answer's status, headers (lower-case names) and body, and the request head the
    stand-in received (None when the filter contacted no upstream)."""
    import asyncio
    import gzip
    import isolation
    import netfilter
    names = [prefix + "own", "ns2604_trial_other_x", "socraticode_metadata"]
    listing = json.dumps({"result": {"collections": [{"name": n} for n in names]}, "status": "ok", "time": 0.001}).encode()
    single = json.dumps({"result": {"status": "green"}, "status": "ok", "time": 0.001}).encode()
    received, answers = [], []

    async def scenario():
        async def qdrant(reader, writer):
            try:
                head = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1")
                received.append(head)
                body, extra = (listing if head.split(" ", 2)[1] == "/collections" else single), b""
                if always_compressed or "accept-encoding: gzip" in head.lower():
                    body, extra = gzip.compress(body), b"Content-Encoding: gzip\r\n"
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" + extra
                             + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
                await writer.drain()
            finally:
                writer.close()

        upstream = await asyncio.start_server(qdrant, "127.0.0.1", 0)
        forward = {**isolation.NET_FORWARDS["qdrant"], "qdrant_prefix": prefix,
                   "upstream": ["127.0.0.1", upstream.sockets[0].getsockname()[1]]}
        filt = netfilter.Filter({"access_log": str(tmp / "access.jsonl"), "scope": {}})
        tasks = []

        def handler(reader, writer):
            tasks.append(asyncio.ensure_future(filt.handle("qdrant", forward, reader, writer)))

        front = await asyncio.start_unix_server(handler, path=str(tmp / "qdrant.sock"), limit=netfilter.MAX_HEAD)
        for method, path, headers in requests_:
            before = len(received)
            reader, writer = await asyncio.open_unix_connection(str(tmp / "qdrant.sock"))
            writer.write((f"{method} {path} HTTP/1.1\r\nHost: qdrant\r\n"
                          + "".join(f"{k}: {v}\r\n" for k, v in headers) + "\r\n").encode())
            await writer.drain()
            head, _, body = (await reader.read()).partition(b"\r\n\r\n")
            writer.close()
            lines = head.decode("latin-1").split("\r\n")
            answers.append({"status": int(lines[0].split(" ")[1]), "body": body,
                            "headers": {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])},
                            "received": received[-1] if len(received) > before else None})
        await asyncio.gather(*tasks, return_exceptions=True)
        front.close()
        upstream.close()
        filt.log.close()

    asyncio.run(scenario())
    return answers


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class StructuralG13(unittest.TestCase):
    report: dict | None = None

    @classmethod
    def setUpClass(cls):
        import isolation
        cls.report = isolation.selftest(clients=os.environ.get("ISOLATION_SKIP_CLIENTS") != "1")

    def test_every_hidden_location_refuses_cat(self):
        hidden = self.report["hidden"]
        self.assertGreaterEqual(len({h["location"] for h in hidden}), 10, "too few hidden locations probed")
        readable = [h for h in hidden if h["inside"] == "READABLE"]
        self.assertEqual(readable, [], "a hidden location was readable inside the namespace")
        self.assertTrue(all(h["inside"] in ("ENOENT", "EACCES") for h in hidden), hidden)
        for client in ("claude", "codex"):
            locations = {h["location"] for h in hidden if h["client"] == client}
            for needed in ("suite cards", "the fixture cache's oracles.json", "another trial's fixture",
                           "another trial's Claude transcript", "the shared Codex transcripts"):
                self.assertIn(needed, locations, f"{client}: no probe for {needed}")
        self.assertIn("the shared sessions alias in the trial's clone",
                      {h["location"] for h in hidden if h["client"] == "codex"})
        for client in ("claude", "codex"):
            siblings = {h["location"] for h in hidden if h["client"] == client and h["location"].startswith("this run's sibling")}
            self.assertEqual(len(siblings), 6, f"{client}: the same-run sibling's files were not all probed: {siblings}")

    def test_own_inputs_and_native_config_stay_readable(self):
        for group in ("own", "native"):
            for client, verdicts in self.report[group].items():
                self.assertTrue(verdicts, f"{group} {client}: nothing checked")
                self.assertTrue(all(v == "READABLE" for v in verdicts.values()), (group, client, verdicts))

    def test_writes_land_in_the_trials_own_folders(self):
        for client, writes in self.report["writes"].items():
            self.assertEqual(writes["rc"], 0, writes)
            self.assertTrue(writes["sessions_write_in_private_folder"], writes)
            self.assertTrue(writes["sessions_write_not_in_native_folder"], writes)
            self.assertTrue(writes["last_write_in_private_folder"], writes)
            self.assertTrue(writes["pid1_argv_shows_no_option_or_hidden_path"], writes)

    def test_tmp_and_shm_are_private(self):
        """Round 5 (CC item task-ns2604-coop-20261006T143846Z, (a)): another trial's scratch file in the host's /tmp,
        /var/tmp or /dev/shm cannot be read, the trial's own writes there never reach the host, and Claude's /tmp area
        still lands in the trial's own folder."""
        for client in ("claude", "codex"):
            scratch = [h for h in self.report["hidden"] if h["client"] == client and "scratch file" in h["location"]]
            self.assertEqual(len(scratch), 3, scratch)
            self.assertTrue(all(h["inside"] in ("ENOENT", "EACCES") for h in scratch), scratch)
            writes = self.report["writes"][client]
            self.assertTrue(writes["tmp_shm_writes_stay_in_the_namespace"], writes)
            self.assertTrue(writes["claude_tmp_write_in_private_folder"], writes)

    def test_ai_memory_scope_is_the_trials(self):
        """Round 5: the marker above the fixture names workspace organic-e2e and the trial's own id, in the namespace
        only."""
        for client in ("claude", "codex"):
            memory = self.report["ai_memory"][client]
            self.assertTrue(memory["ok"], memory)
            self.assertFalse(memory["marker_on_host"], memory)
            self.assertIn(f'project = "{self.report["trial_id"]}"', memory["marker_in_namespace"])

    def test_namespace_is_the_trials_own(self):
        for client, ns in self.report["namespaces"].items():
            self.assertTrue(ns["namespace"], ns)
            self.assertNotEqual(ns["namespace"], ns["host_namespace"], ns)
            # GPT read of 2044b2ab, residual channels: an IPC namespace of its own (--unshare-ipc).
            self.assertTrue(ns["ipc_namespace"], ns)
            self.assertNotEqual(ns["ipc_namespace"], ns["host_ipc_namespace"], ns)

    def test_host_brokers_are_unreachable(self):
        """P2-2 (CC item task-ns2604-coop-20261006T151719Z, C1): the stage-1 self-test's own probes. Every broker socket
        that exists on the host is absent in the namespace, each connection attempt fails there, and the runtime
        folder is private, empty and 0700."""
        brokers = self.report["host_brokers"]
        self.assertTrue(brokers["ok"], brokers)
        self.assertTrue(brokers["sockets"], brokers)
        self.assertTrue(all(s["inside"] == "ABSENT" for s in brokers["sockets"].values()), brokers)
        self.assertTrue(all(a["unreachable"] for a in brokers["attempts"].values()), brokers)
        # The folder holds only what the plan mounts there: the forwards' socket folder (round 6).
        self.assertEqual(brokers["runtime_dir"]["mode"], "700", brokers)
        self.assertEqual(brokers["runtime_dir"]["entries"], brokers["runtime_dir"]["expected_entries"], brokers)

    def test_the_network_probe_set_passes(self):
        """Round 6 (CC item task-ns2604-coop-20261006T155742Z, (B)): the stage-1 self-test's network probes, in each
        client's own network namespace with its forwards served. /v1 answers; the gateway's management routes, its
        dashboard and the detours to them are refused by the filter; every sampled local listener and direct egress
        are unreachable; Claude's egress reaches only its listed hosts."""
        network = self.report["network"]
        self.assertTrue(network["ok"], json.dumps(network["expect"], indent=1))
        self.assertGreaterEqual(len(network["listeners_sampled"]), 3, network["listeners_sampled"])
        for client, ns in self.report["namespaces"].items():
            self.assertTrue(ns["net_namespace"], ns)
            self.assertNotEqual(ns["net_namespace"], ns["host_net_namespace"], ns)

    def test_launch_paths_start_under_the_wrapper(self):
        if os.environ.get("ISOLATION_SKIP_CLIENTS") == "1":
            self.skipTest("ISOLATION_SKIP_CLIENTS=1")
        self.assertGreaterEqual(len(self.report["clients"]), 7)
        failing = {k: v for k, v in self.report["clients"].items() if not v.get("ok")}
        self.assertEqual(failing, {})

    def test_selftest_passes(self):
        self.assertTrue(self.report["pass"], json.dumps(self.report, default=str)[:2000])

    def test_selftest_report_is_plain_json(self):
        """prepare.py writes it with common.write_json, which has no default= for a stray Path or set."""
        json.dumps(self.report)


class Receipt(unittest.TestCase):
    def test_receipt_carries_the_hidden_list(self):
        isolation, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        rec = isolation.receipt(plan, ["bash", "-lc", "<line>"])
        self.assertEqual(rec["decision"], isolation.ISOLATION_DECISION)
        self.assertTrue(rec["version"] and rec["version"].startswith("bubblewrap"), rec["version"])
        self.assertEqual(rec["argv"][0], isolation.BWRAP)
        self.assertEqual(rec["argv_visible"][:2], [isolation.BWRAP, "--args"])
        locations = {h["location"]: h for h in rec["hidden"]}
        for needed in ("run roots: oracle runs, other trials' drafts, grades", "run roots: this run", "suite cards",
                       "the fixture cache's oracles.json", "other trials' fixtures (and their drafts)",
                       "other trials' Claude transcripts", "the shared Codex transcripts",
                       "the shared sessions alias in the trial's clone"):
            self.assertIn(needed, locations)
        for entry in rec["hidden"]:
            self.assertEqual(entry["path_sha256"], isolation.sha256_text(isolation.untilde(entry["path"])))
            if entry["kind"] == "file":
                self.assertEqual(len(entry.get("content_sha256") or ""), 64, entry)
        argv = " ".join(rec["argv"])
        for root in isolation.HIDDEN_ROOTS:
            self.assertIn(f"--tmpfs {isolation.tilde(root)}", argv)
        self.assertIn(f"--bind {isolation.tilde(plan['private'] / 'codex-sessions')} {isolation.tilde(isolation.CODEX_SESSIONS)}", argv)
        for folder in isolation.PRIVATE_TMP:
            self.assertIn(f"--tmpfs {folder}", argv)
        self.assertIn(f"--ro-bind {isolation.tilde(plan['private'] / 'ai-memory.toml')} "
                      f"{isolation.tilde(isolation.NEUTRAL_ROOT / '.ai-memory.toml')}", argv)
        self.assertEqual(rec["ai_memory_scope"]["project"], trial_id)
        self.assertEqual(rec["ai_memory_scope"]["workspace"], "organic-e2e")
        # P2-2: a private runtime folder (mode 0700) and, on WSL, no interop sockets; nothing passed through.
        self.assertIn(f"--perms 0700 --tmpfs {RUNTIME}", argv)
        self.assertNotIn(f"--bind-try {RUNTIME} ", argv)
        self.assertIn("the host's runtime folder: the user manager's, the session bus's and Docker's sockets (host "
                      "execution brokers)", locations)
        if WSL_RUN.is_dir():
            self.assertIn(f"--tmpfs {WSL_RUN}", argv)
        self.assertEqual((rec.get("runtime_dir") or {}).get("passed_through"), [])
        json.dumps(rec)   # the launched row is written with plain json.dumps

    def test_a_published_receipt_keeps_only_the_count_and_hash_of_kept_projects(self):
        """Round 5, (b): a published receipt names no project folder (a name encodes its cwd, the home path included);
        the projects outside the experiment become their count and the sha256 of their sorted names."""
        isolation, cfg, plan, trial_id, fixture, work = _synthetic_plan("claude")
        rec = isolation.receipt(plan, ["bash", "-lc", "<line>"])
        public = isolation.public_receipt(rec)
        text = json.dumps(public)
        for name in plan["kept_projects"]:
            self.assertNotIn(f"~/.claude/projects/{name}", text)
        self.assertNotIn(isolation.claude_slug(isolation.HOME), text)
        self.assertEqual(public["kept_projects"], len(plan["kept_projects"]))
        self.assertEqual(public["kept_projects_sha256"], isolation.sha256_json(plan["kept_projects"]))
        if plan["kept_projects"]:
            self.assertIn(rec["kept_projects_sha256"], text)
        self.assertTrue(public["own_project"].startswith("~/.claude/projects/sha256-"), public["own_project"])
        self.assertTrue(public["public"])

    def test_a_published_receipt_hashes_every_home_derived_name(self):
        """GPT read of 2044b2ab, P3: tilde() alone leaves Claude's `-home-<user>-...` slugs; the public representation
        hashes them wherever they sit (argv, operations, the visible argv, the hidden list), and leaves no home path."""
        import isolation
        slug = isolation.claude_slug(isolation.HOME / "code" / "some-project")
        rec = {"ops": [["bind-try", f"~/.claude/projects/{slug}", f"~/.claude/projects/{slug}"],
                       ["bind", f"~/.cache/x/{slug}.jsonl", "/tmp/y"]],
               "argv": [isolation.BWRAP, "--bind", f"~/.cache/x/{slug}.jsonl", "/tmp/y"],
               "argv_visible": [isolation.BWRAP, "--args", "<fd>", "--", "cat", f"{isolation.HOME}/notes/{slug}"],
               "hidden": [{"location": "x", "path": f"~/.claude/projects/{slug}/a.jsonl", "path_sha256": "0"}],
               "own_project": f"~/.claude/projects/{slug}", "kept_projects": 0, "kept_projects_sha256": "h"}
        text = json.dumps(isolation.public_receipt(rec))
        self.assertNotIn(isolation.HOME_SLUG, text)
        self.assertNotIn(str(isolation.HOME), text)
        self.assertIn("sha256-", text)

    def test_the_exact_mount_operations_stay_private(self):
        """P3: the raw receipt sits in the ledger, appended with mode 0600; CL7b's options file is 0600 in a 0700
        folder."""
        import common
        import isolation
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.jsonl"
            common.append_jsonl(ledger, {"isolation": {"ops": []}})
            self.assertEqual(ledger.stat().st_mode & 0o777, 0o600)
        if not HOST_READY:
            self.skipTest("the CL7b wrapper needs the experiment's roots")
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        try:
            wrapper = isolation.write_app_server_wrapper(plan, "/usr/bin/true")
            self.assertEqual((plan["private"] / "args").stat().st_mode & 0o777, 0o600)
            self.assertEqual(plan["private"].stat().st_mode & 0o777, 0o700)
            self.assertTrue(os.access(wrapper, os.X_OK))
        finally:
            import shutil
            shutil.rmtree(work, ignore_errors=True)

    def test_finish_moves_the_answer_file_and_publishes_rollouts(self):
        """finish() after the client exits, against a temporary sessions folder (never the real one), twice."""
        import isolation
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            work, private, sessions = base / "work", base / "work" / "iso" / "t1", base / "sessions"
            (private / "last").mkdir(parents=True)
            (private / "last" / "t1.txt").write_text("answer\n")
            rollout = private / "codex-sessions" / "2026" / "10" / "06" / "rollout-2026-10-06T10-00-00-abc.jsonl"
            rollout.parent.mkdir(parents=True)
            rollout.write_text("{}\n")
            saved = isolation.CODEX_SESSIONS
            isolation.CODEX_SESSIONS = sessions
            try:
                plan = {"work": work, "private": private}
                first = isolation.safe_finish(plan)
                second = isolation.safe_finish(plan)
            finally:
                isolation.CODEX_SESSIONS = saved
            self.assertEqual(first, {"last_moved": ["t1.txt"],
                                     "rollouts_published": ["2026/10/06/rollout-2026-10-06T10-00-00-abc.jsonl"]})
            self.assertEqual((work / "last" / "t1.txt").read_text(), "answer\n")
            self.assertTrue((sessions / "2026" / "10" / "06" / rollout.name).exists())
            self.assertEqual(second, {"last_moved": [], "rollouts_published": []})

    def test_app_server_runtime_reads_the_wrappers_record(self):
        """CL7b's exit row: the namespace record bwrap wrote through the wrapper's fd 4, read back without raising."""
        import isolation
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            private = base / "work" / "iso" / "t2"
            private.mkdir(parents=True)
            (private / "info.json").write_text(json.dumps({"child-pid": 7, "mnt-namespace": 4026532999}))
            saved = isolation.CODEX_SESSIONS
            isolation.CODEX_SESSIONS = base / "sessions"
            try:
                runtime = isolation.app_server_runtime({"work": base / "work", "private": private})
            finally:
                isolation.CODEX_SESSIONS = saved
            self.assertEqual(runtime["namespace"], "mnt:[4026532999]")
            self.assertNotIn("finish_error", runtime)
            self.assertNotIn("runtime_error", runtime)
            json.dumps(runtime)


class G13Check(unittest.TestCase):
    def _rows(self, client="claude", cfg_extra=None):
        isolation, cfg, plan, trial_id, fixture, work = _synthetic_plan(client)
        if cfg_extra:
            cfg.update(cfg_extra)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, client, fixture,
                                  clone=plan["clone"], settings=plan["settings"], prompt=plan["prompt"])
        rec = isolation.receipt(plan, ["bash", "-lc", "<line>"])
        reading = {"semantic_cache": {"hits": 0, "misses": 0, "dbEntries": 0, "memoryEntries": 0}}
        rows = {"prepared": {"fixture_private": str(fixture)},
                "launched": {"isolation": rec, "gateway_cache": json.loads(json.dumps(reading))},
                "exit": {"isolation_runtime": {"namespace": "mnt:[1]", "host_namespace": "mnt:[2]",
                                               "info": {"mnt-namespace": 1, "ipc-namespace": 11, "net-namespace": 21},
                                               "host_ipc_namespace": "ipc:[12]", "host_net_namespace": "net:[22]",
                                               "tree": {"processes_seen": 4, "in_trial_namespace": 4, "outside": []}},
                         "network_runtime": {"started": True, "requests": 3, "denied": []},
                         "gateway_cache": json.loads(json.dumps(reading))}}
        return isolation, cfg, trial_id, rows

    def _check(self, isolation, cfg, trial_id, rows, client="claude"):
        return isolation.check(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, client, rows)

    def _reseal(self, isolation, rows):
        """Recompute the options sha256 after a test edits the operations, so only the edit itself is judged."""
        rec = rows["launched"]["isolation"]
        ops = [(op, isolation.untilde(src), isolation.untilde(dest)) for op, src, dest in rec["ops"]]
        rec["options_sha256"] = isolation.sha256_text("\0".join(isolation.options(
            {"ops": ops, "fixture": rows["prepared"]["fixture_private"], "network": rec.get("network")})))

    def _swap_source(self, isolation, rows, dest, new_src):
        rec = rows["launched"]["isolation"]
        hits = [op for op in rec["ops"] if op[2] == isolation.tilde(dest)]
        self.assertEqual(len(hits), 1, hits)
        hits[0][1] = isolation.tilde(new_src)
        self._reseal(isolation, rows)

    def test_a_permitted_destination_from_a_shared_source_fails(self):
        """GPT read of 2044b2ab, P2-1: the shared -o folder bound onto the trial's own -o destination."""
        isolation, cfg, trial_id, rows = self._rows("codex")
        work = isolation.trial_dir(cfg, isolation.RUNS_ROOT / "unit-run")
        self._swap_source(isolation, rows, work / "last", work / "last")
        result = self._check(isolation, cfg, trial_id, rows, "codex")
        self.assertFalse(result["ok"])
        self.assertTrue(any("onto" in f and "/last" in f and "the plan binds it only as" in f for f in result["failures"]),
                        result["failures"])

    def test_a_private_store_from_the_shared_store_fails(self):
        isolation, cfg, trial_id, rows = self._rows("codex")
        self._swap_source(isolation, rows, isolation.CODEX_SESSIONS, isolation.CODEX_SESSIONS)
        result = self._check(isolation, cfg, trial_id, rows, "codex")
        self.assertFalse(result["ok"])
        self.assertTrue(any("no private folder over" in f for f in result["failures"]), result["failures"])

    def test_a_receipt_naming_another_private_folder_fails(self):
        """The private folder comes from the trial id: a receipt that names the trial root as its private folder (so
        its -o bind would read work/last onto work/last) fails."""
        isolation, cfg, trial_id, rows = self._rows("codex")
        rec = rows["launched"]["isolation"]
        work = isolation.trial_dir(cfg, isolation.RUNS_ROOT / "unit-run")
        private = isolation.tilde(isolation.private_dir(cfg, isolation.RUNS_ROOT / "unit-run", trial_id))
        rec["private_dir"] = isolation.tilde(work)
        for op in rec["ops"]:
            if op[1] and op[1].startswith(private):
                op[1] = isolation.tilde(work) + op[1][len(private):]
        self._reseal(isolation, rows)
        result = self._check(isolation, cfg, trial_id, rows, "codex")
        self.assertFalse(result["ok"])
        self.assertTrue(any("private folder is not the trial's" in f for f in result["failures"]), result["failures"])

    def test_a_declared_answer_source_keeps_its_cover(self):
        """P2-1: a declared answer source outside the hidden roots gets the inaccessible file; the same destination
        bound from the file itself, or a parent bound after the cover, fails."""
        with tempfile.TemporaryDirectory(dir=Path.home() / ".cache") as tmp:
            answer = Path(tmp) / "answers" / "key.txt"
            answer.parent.mkdir()
            answer.write_text("the answer\n")
            extra = {"answer_source_paths": [str(answer)]}
            isolation, cfg, trial_id, rows = self._rows("claude", extra)
            self.assertTrue(self._check(isolation, cfg, trial_id, rows)["ok"])
            # The inaccessible destination bound from the answer itself.
            isolation, cfg, trial_id, rows = self._rows("claude", extra)
            self._swap_source(isolation, rows, answer, answer)
            result = self._check(isolation, cfg, trial_id, rows)
            self.assertFalse(result["ok"])
            self.assertTrue(any("no inaccessible bind" in f for f in result["failures"]), result["failures"])
            # A parent of the declared source bound back after its cover.
            isolation, cfg, trial_id, rows = self._rows("claude", extra)
            parent = isolation.tilde(answer.parent)
            rows["launched"]["isolation"]["ops"].append(["bind", parent, parent])
            self._reseal(isolation, rows)
            result = self._check(isolation, cfg, trial_id, rows)
            self.assertFalse(result["ok"])
            self.assertTrue(any("re-exposes" in f and "key.txt" in f for f in result["failures"]), result["failures"])

    def test_a_permitted_bind_in_the_wrong_place_fails(self):
        """P2-1, ordering: the home's own bind is permitted, but after the covers it would put the host's view back."""
        isolation, cfg, trial_id, rows = self._rows()
        rec = rows["launched"]["isolation"]
        home = [op for op in rec["ops"] if op[1:] == ["~", "~"]]
        self.assertEqual(len(home), 1)
        rec["ops"] = [op for op in rec["ops"] if op[1:] != ["~", "~"]] + home
        self._reseal(isolation, rows)
        result = self._check(isolation, cfg, trial_id, rows)
        self.assertFalse(result["ok"])
        self.assertTrue(any(f.startswith(f"{home[0][0]} ~ after the cover") for f in result["failures"]), result["failures"])

    def test_the_hosts_runtime_folder_bound_in_fails(self):
        """P2-2: the round-4 plan bound the host's runtime folder (its brokers' sockets) into the namespace."""
        isolation, cfg, trial_id, rows = self._rows()
        rec = rows["launched"]["isolation"]
        runtime = str(RUNTIME)
        rec["ops"] = [["bind-try", runtime, runtime] if op == ["tmpfs", "0700", runtime] else op for op in rec["ops"]]
        self._reseal(isolation, rows)
        failures = self._check(isolation, cfg, trial_id, rows)["failures"]
        self.assertTrue(any(f.startswith(f"no tmpfs over {runtime}") for f in failures), failures)
        self.assertIn(f"a bind outside the trial's plan: bind-try {runtime} -> {runtime}", failures)

    def test_options_that_differ_from_the_operations_fail(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["launched"]["isolation"]["options_sha256"] = "0" * 64
        result = self._check(isolation, cfg, trial_id, rows)
        self.assertFalse(result["ok"])
        self.assertIn("the receipt's options sha256 is not the one its operations give", result["failures"])

    def test_the_ipc_namespace_must_be_the_trials_own(self):
        isolation, cfg, trial_id, rows = self._rows()
        runtime = rows["exit"]["isolation_runtime"]
        runtime["info"] = {"mnt-namespace": 1}
        self.assertIn("no IPC namespace of its own (--unshare-ipc)", self._check(isolation, cfg, trial_id, rows)["failures"])
        runtime["info"] = {"mnt-namespace": 1, "ipc-namespace": 12}
        self.assertIn("the client shared the host's IPC namespace", self._check(isolation, cfg, trial_id, rows)["failures"])

    def test_a_complete_receipt_passes(self):
        for client in ("claude", "codex"):
            isolation, cfg, trial_id, rows = self._rows(client)
            result = self._check(isolation, cfg, trial_id, rows, client)
            self.assertTrue(result["ok"], (client, result["failures"]))

    def test_a_missing_location_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["launched"]["isolation"]["hidden"] = [h for h in rows["launched"]["isolation"]["hidden"]
                                                  if h["location"] != "suite cards"]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_a_tmpfs_left_out_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        ops = rows["launched"]["isolation"]["ops"]
        rows["launched"]["isolation"]["ops"] = [op for op in ops if op[2] != isolation.tilde(isolation.FIXTURE_CACHE_ROOT)]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_another_fixture_bound_back_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        other = isolation.tilde(isolation.NEUTRAL_ROOT / "0123abcd")
        rows["launched"]["isolation"]["ops"].append(["bind", other, other])
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_an_experiment_project_bound_back_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        name = isolation.claude_slug(isolation.NEUTRAL_ROOT / "0123abcd")
        path = isolation.tilde(isolation.CLAUDE_PROJECTS / name)
        rows["launched"]["isolation"]["ops"].append(["bind", path, path])
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_home_rebound_after_the_tmpfs_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        home = isolation.tilde(isolation.HOME)
        rows["launched"]["isolation"]["ops"].append(["bind", home, home])
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_a_tree_outside_the_namespace_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["exit"]["isolation_runtime"]["tree"]["outside"] = [{"exe": "claude", "namespace": "mnt:[2]"}]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])
        rows["exit"]["isolation_runtime"]["tree"]["outside"] = []
        rows["exit"]["isolation_runtime"]["namespace"] = "mnt:[2]"
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_no_receipt_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["launched"].pop("isolation")
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_a_missing_ai_memory_marker_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        marker = isolation.tilde(isolation.NEUTRAL_ROOT / ".ai-memory.toml")
        rows["launched"]["isolation"]["ops"] = [op for op in rows["launched"]["isolation"]["ops"] if op[2] != marker]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_a_shared_tmp_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        ops = rows["launched"]["isolation"]["ops"]
        rows["launched"]["isolation"]["ops"] = [op for op in ops if not (op[0] == "tmpfs" and op[2] == "/tmp")]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_the_cache_rule_voids_a_trial(self):
        """Round 6 (A), the Gate 0 amendment: every trial needs both readings of GET /api/cache, with 0 hits at both and
        unchanged entries. A hit, an entry change, or a missing or failed reading voids it."""
        for client in ("claude", "codex"):
            isolation, cfg, trial_id, rows = self._rows(client)
            self.assertTrue(self._check(isolation, cfg, trial_id, rows, client)["ok"])
            cases = {"a hit after": ("exit", {"semantic_cache": {"hits": 1, "misses": 0, "dbEntries": 0, "memoryEntries": 0}}),
                     "a hit before": ("launched", {"semantic_cache": {"hits": 2, "misses": 0, "dbEntries": 0,
                                                                      "memoryEntries": 0}}),
                     "entries changed": ("exit", {"semantic_cache": {"hits": 0, "misses": 0, "dbEntries": 1,
                                                                     "memoryEntries": 0}}),
                     "a failed reading": ("exit", {"error": "URLError"}),
                     "no reading": ("launched", None),
                     "a reading without its counts": ("exit", {"semantic_cache": {"hits": 0}})}
            for label, (row, value) in cases.items():
                isolation, cfg, trial_id, rows = self._rows(client)
                rows[row]["gateway_cache"] = value
                result = self._check(isolation, cfg, trial_id, rows, client)
                self.assertFalse(result["ok"], (client, label))
                self.assertTrue(result["gateway_cache_window"]["void"], (client, label))
                self.assertTrue(any(f.startswith("the gateway cache rule") for f in result["failures"]), (client, label))

    def test_the_network_must_be_the_plans(self):
        """Round 6 (B): a receipt with no network record, an extra forward, a forward with another filter, the host's
        network namespace, or no record that the forwards ran fails."""
        isolation, cfg, trial_id, rows = self._rows("codex")
        rows["launched"]["isolation"]["network"] = None
        self._reseal(isolation, rows)
        self.assertIn("no network record: the trial ran without a network namespace of its own (round 6)",
                      self._check(isolation, cfg, trial_id, rows, "codex")["failures"])
        for edit in ("extra forward", "wider rule", "egress for codex"):
            isolation, cfg, trial_id, rows = self._rows("codex")
            network = rows["launched"]["isolation"]["network"]
            if edit == "extra forward":
                network["forwards"]["dagu"] = {"listen": 21080, "kind": "http", "upstream": ["127.0.0.1", 21080],
                                               "rules": [{"prefix": "/", "methods": ["GET"]}]}
            elif edit == "wider rule":
                network["forwards"]["gateway"]["rules"] = [{"prefix": "/", "methods": ["GET", "POST"]}]
            else:
                network["setenv"] = [["HTTPS_PROXY", "http://127.0.0.1:3128"]]
            self._reseal(isolation, rows)
            self.assertIn("the receipt's network (forwards, environment or scope) is not the plan's for this client",
                          self._check(isolation, cfg, trial_id, rows, "codex")["failures"], edit)
        isolation, cfg, trial_id, rows = self._rows("codex")
        rows["exit"]["isolation_runtime"]["info"]["net-namespace"] = 22
        self.assertIn("the client shared the host's network namespace",
                      self._check(isolation, cfg, trial_id, rows, "codex")["failures"])
        rows["exit"]["isolation_runtime"]["info"].pop("net-namespace")
        self.assertIn("no network namespace of its own (--unshare-net)",
                      self._check(isolation, cfg, trial_id, rows, "codex")["failures"])
        isolation, cfg, trial_id, rows = self._rows("codex")
        rows["exit"]["network_runtime"] = {"started": False}
        self.assertIn("no record that the trial's forwards ran (network_runtime)",
                      self._check(isolation, cfg, trial_id, rows, "codex")["failures"])

    def test_each_client_gets_only_its_forwards(self):
        import isolation
        codex = isolation.network_for("codex", "t")
        claude = isolation.network_for("claude", "t")
        self.assertEqual(sorted(codex["forwards"]), ["ai-memory", "gateway", "otlp", "qdrant", "vllm"])
        self.assertEqual(sorted(claude["forwards"]), ["ai-memory", "model-egress", "otlp", "qdrant", "vllm"])
        self.assertNotIn("HTTPS_PROXY", [k for k, _ in codex["setenv"]])
        self.assertEqual(sorted(k for k, _ in codex["setenv"]), ["QDRANT_COLLECTION_PREFIX", "npm_config_offline"])
        self.assertIn(["HTTPS_PROXY", "http://127.0.0.1:3128"], claude["setenv"])
        self.assertEqual(codex["forwards"]["gateway"]["rules"][0]["prefix"], "/v1/")
        self.assertEqual(claude["forwards"]["model-egress"]["allow"], [["api.anthropic.com", 443],
                                                                       ["platform.claude.com", 443]])
        for name, forward in isolation.NET_FORWARDS.items():
            self.assertTrue(forward["reason"], name)


class NetFilterRules(unittest.TestCase):
    """Round 6 (B): netfilter.py's decisions, with no network: what each forward admits and what it refuses."""

    def setUp(self):
        import isolation
        import netfilter
        self.nf = netfilter
        self.scope = {"workspace": "organic-e2e", "project": "t1"}
        self.gateway = isolation.NET_FORWARDS["gateway"]
        self.memory = isolation.NET_FORWARDS["ai-memory"]
        self.otlp = isolation.NET_FORWARDS["otlp"]

    def admits(self, forward, method, target, headers=()):
        try:
            self.nf.judge(forward, self.scope, method, target, list(headers))
            return True
        except self.nf.Denied:
            return False

    def test_the_gateway_admits_v1_only(self):
        for target in ("/v1/responses", "/v1/models", "/v1/models?client_version=0.160.1"):
            self.assertTrue(self.admits(self.gateway, "POST" if target == "/v1/responses" else "GET", target), target)
        for target in ("/api/health", "/api/usage/call-logs?limit=1", "/", "/dashboard", "/v1", "/v1/../api/health",
                       "/v1/./x", "/v1//x", "/v1/%2e%2e/api/health", "/V1/models", "http://127.0.0.1:21128/v1/models",
                       "/v1/models#x", "*"):
            self.assertFalse(self.admits(self.gateway, "GET", target), target)
        self.assertFalse(self.admits(self.gateway, "CONNECT", "/v1/x"))
        self.assertFalse(self.admits(self.gateway, "TRACE", "/v1/x"))
        self.assertFalse(self.admits(self.gateway, "GET", "/v1/models", [("Upgrade", "websocket")]))
        self.assertFalse(self.admits(self.gateway, "POST", "/v1/responses",
                                     [("Content-Length", "5"), ("Transfer-Encoding", "chunked")]))
        self.assertFalse(self.admits(self.gateway, "POST", "/v1/responses", [("Transfer-Encoding", "gzip, chunked")]))
        self.assertFalse(self.admits(self.gateway, "POST", "/v1/responses", [("Content-Length", "5"),
                                                                            ("Content-Length", "6")]))

    def test_ai_memory_admits_mcp_and_the_trials_own_hook_scope(self):
        own = "workspace=organic-e2e&project=t1"
        self.assertTrue(self.admits(self.memory, "POST", "/mcp"))
        self.assertTrue(self.admits(self.memory, "GET", "/mcp"))
        self.assertTrue(self.admits(self.memory, "POST", f"/hook?event=stop&agent=codex&cwd=%2Fx&{own}"))
        self.assertTrue(self.admits(self.memory, "GET", f"/handoff?agent=codex&{own}"))
        for target in ("/", "/w/organic-e2e/t2", "/search?q=x", "/admin/status", "/wiki", "/healthz",
                       "/hook?event=stop&agent=codex&workspace=organic-e2e&project=t2",
                       "/hook?event=stop&agent=codex", "/handoff?agent=codex&workspace=organic-e2e&project=t1&project=t2",
                       "/handoff?agent=codex&workspace=default&project=t1"):
            self.assertFalse(self.admits(self.memory, "GET" if not target.startswith("/hook") else "POST", target), target)
        self.assertFalse(self.admits(self.memory, "GET", f"/hook?{own}"))   # /hook is POST only

    def test_a_hook_batch_must_name_the_trials_scope_in_every_item(self):
        own = "http://127.0.0.1:29374/hook?event=stop&agent=codex&workspace=organic-e2e&project=t1"
        other = "http://127.0.0.1:29374/hook?event=stop&agent=codex&workspace=organic-e2e&project=t2"
        self.assertTrue(self.nf.batch_ok(json.dumps([{"url": own, "body": {}}]).encode(), self.scope))
        self.assertFalse(self.nf.batch_ok(json.dumps([{"url": own, "body": {}}, {"url": other, "body": {}}]).encode(),
                                          self.scope))
        self.assertFalse(self.nf.batch_ok(b"[]", self.scope))
        self.assertFalse(self.nf.batch_ok(b"{}", self.scope))

    def test_otlp_admits_post_exports_only(self):
        for path in ("/v1/logs", "/v1/metrics", "/v1/traces"):
            self.assertTrue(self.admits(self.otlp, "POST", path))
            self.assertFalse(self.admits(self.otlp, "GET", path))
        self.assertFalse(self.admits(self.otlp, "POST", "/"))

    def test_the_egress_proxy_tunnels_to_listed_hosts_only(self):
        import isolation
        allow = isolation.NET_FORWARDS["model-egress"]["allow"]
        self.assertEqual(self.nf.connect_target("api.anthropic.com:443", allow), ("api.anthropic.com", 443))
        self.assertEqual(self.nf.connect_target("API.Anthropic.com:443", allow), ("api.anthropic.com", 443))
        for target in ("api.anthropic.com:80", "example.com:443", "127.0.0.1:21128", "api.anthropic.com", ":443",
                       "evil.api.anthropic.com:443"):
            with self.assertRaises(self.nf.Denied, msg=target):
                self.nf.connect_target(target, allow)

    def test_qdrant_admits_only_the_trials_own_collections(self):
        """Round 6b (CC item task-ns2604-coop-20261006T170607Z, (1)): health, the collection names (socraticode 1.15.0
        lists them before creating its own), and data operations on the trial's own prefixed collections only."""
        import isolation
        trial, other_trial = str(uuid.uuid4()), str(uuid.uuid4())
        qdrant = isolation.network_for("codex", trial)["forwards"]["qdrant"]
        own = isolation.qdrant_prefix(trial)
        other = isolation.qdrant_prefix(other_trial)
        for method, target in (("GET", "/healthz"), ("GET", "/collections"), ("PUT", f"/collections/{own}codebase_x"),
                               ("POST", f"/collections/{own}codebase_x/points/query"),
                               ("PUT", f"/collections/{own}codebase_x/points?wait=true"),
                               ("GET", f"/collections/{own}socraticode_metadata"),
                               ("DELETE", f"/collections/{own}codegraph_x")):
            self.assertTrue(self.admits(qdrant, method, target), (method, target))
        for method, target in (("GET", f"/collections/{other}codebase_x"),
                               ("POST", f"/collections/{other}codebase_x/points/scroll"),
                               ("GET", "/collections/socraticode_metadata"), ("GET", "/collections/codebase_abc"),
                               ("POST", "/collections"), ("GET", "/telemetry"), ("GET", "/cluster"), ("GET", "/aliases"),
                               ("GET", f"/collections/{own[:-1]}"), ("GET", f"/collections/{own}x/../../{other}x")):
            self.assertFalse(self.admits(qdrant, method, target), (method, target))

    def test_qdrant_admits_only_socraticodes_operations(self):
        """Round 6d (GPT read of 50752dde, P1): only the operations socraticode 1.15.0 performs; grouped, batch,
        search, recommend, discover, snapshot and alias routes are refused even on the trial's own collection."""
        import isolation
        trial = str(uuid.uuid4())
        qdrant = isolation.network_for("codex", trial)["forwards"]["qdrant"]
        own = isolation.qdrant_prefix(trial) + "codebase_x"
        for method, suffix in (("GET", ""), ("PUT", ""), ("DELETE", ""), ("PUT", "/index"), ("PUT", "/points"),
                               ("POST", "/points"), ("POST", "/points/delete"), ("POST", "/points/scroll"),
                               ("POST", "/points/query")):
            self.assertTrue(self.admits(qdrant, method, f"/collections/{own}{suffix}"), (method, suffix))
        for method, suffix in (("POST", "/points/query/groups"), ("POST", "/points/search/groups"),
                               ("POST", "/points/query/batch"), ("POST", "/points/search"),
                               ("POST", "/points/search/batch"), ("POST", "/points/recommend"),
                               ("POST", "/points/recommend/groups"), ("POST", "/points/discover"),
                               ("POST", "/points/batch"), ("POST", "/points/count"), ("GET", "/snapshots"),
                               ("POST", "/snapshots"), ("GET", "/aliases"), ("PATCH", ""), ("POST", "/points/payload"),
                               ("GET", "/points/1"), ("PUT", "/points/vectors")):
            self.assertFalse(self.admits(qdrant, method, f"/collections/{own}{suffix}"), (method, suffix))

    def test_qdrant_bodies_may_name_only_the_trials_collections(self):
        """P1: every collection a body names (with_lookup as a string or an object, lookup_from at any depth) must carry
        the trial's prefix."""
        import netfilter
        own, other = "ns2604_trial_a_", "ns2604_trial_b_"
        ok = netfilter.qdrant_selectors_ok
        self.assertTrue(ok({"query": [0.1], "limit": 3, "prefetch": [{"query": [0.1], "using": "dense"}]}, own))
        self.assertTrue(ok({"query": [0.1], "lookup_from": {"collection": own + "x"}}, own))
        for body in ({"with_lookup": other + "x"}, {"with_lookup": {"collection": other + "x", "with_payload": True}},
                     {"lookup_from": {"collection": other + "x"}}, {"lookup_from": {"vector": "dense"}},
                     {"prefetch": [{"prefetch": [{"lookup_from": {"collection": "socraticode_metadata"}}]}]},
                     {"searches": [{"query": [0.1], "lookup_from": {"collection": other + "x"}}]},
                     {"with_lookup": None}):
            self.assertFalse(ok(body, own), body)

    def test_the_collection_listing_names_only_the_trials_own(self):
        """P2: the envelope is kept and foreign names are dropped."""
        import netfilter
        body = json.dumps({"result": {"collections": [{"name": "ns2604_trial_a_codebase_1"}, {"name": "ns2604_trial_b_x"},
                                                      {"name": "socraticode_metadata"}]},
                           "status": "ok", "time": 0.001}).encode()
        out = json.loads(netfilter.filter_collection_list(body, "ns2604_trial_a_"))
        self.assertEqual(out["result"]["collections"], [{"name": "ns2604_trial_a_codebase_1"}])
        self.assertEqual((out["status"], out["time"]), ("ok", 0.001))
        with self.assertRaises(ValueError):
            netfilter.filter_collection_list(b'{"result": []}', "x")
        # A compressed listing cannot be filtered: the function refuses it instead of passing it on unread.
        import gzip
        with self.assertRaises(ValueError):
            netfilter.filter_collection_list(gzip.compress(body), "ns2604_trial_a_")

    def test_the_listing_is_read_and_filtered_when_the_client_asks_for_compression(self):
        """Round 6e: Qdrant 1.19.1 compresses when asked, and Node's fetch asks by default. Through netfilter's own
        Filter and a stand-in Qdrant: the listing request goes upstream without Accept-Encoding, so the answer is read
        and filtered. Another admitted route keeps the header. A listing that arrives compressed anyway is refused."""
        import gzip
        prefix = "ns2604_trial_a_"
        ask = [("Accept-Encoding", "gzip, deflate")]
        with tempfile.TemporaryDirectory() as tmp:
            listing, single = _relay_qdrant(Path(tmp), prefix, [("GET", "/collections", ask),
                                                                ("GET", f"/collections/{prefix}own", ask)])
        self.assertEqual(listing["status"], 200, listing)
        self.assertNotIn("content-encoding", listing["headers"])
        self.assertEqual([c["name"] for c in json.loads(listing["body"])["result"]["collections"]], [prefix + "own"])
        self.assertEqual(int(listing["headers"]["content-length"]), len(listing["body"]))
        self.assertNotIn("accept-encoding", listing["received"].lower())
        self.assertIn("accept-encoding: gzip, deflate", single["received"].lower())
        self.assertEqual((single["status"], single["headers"].get("content-encoding")), (200, "gzip"))
        self.assertEqual(json.loads(gzip.decompress(single["body"]))["status"], "ok")
        with tempfile.TemporaryDirectory() as tmp:
            forced, = _relay_qdrant(Path(tmp), prefix, [("GET", "/collections", ask)], always_compressed=True)
        self.assertEqual((forced["status"], forced["body"]), (502, b"502 Bad Gateway\n"), forced)

    def test_vllm_admits_embeddings_and_models_only(self):
        import isolation
        vllm = isolation.NET_FORWARDS["vllm"]
        self.assertTrue(self.admits(vllm, "POST", "/v1/embeddings"))
        self.assertTrue(self.admits(vllm, "GET", "/v1/models"))
        for method, target in (("POST", "/v1/chat/completions"), ("POST", "/v1/completions"), ("GET", "/metrics"),
                               ("GET", "/v1/embeddings"), ("POST", "/v1/models"), ("GET", "/health")):
            self.assertFalse(self.admits(vllm, method, target), (method, target))

    def test_each_trial_gets_its_own_collection_prefix(self):
        import isolation
        first, second = isolation.network_for("claude", "a" * 8 + "-1"), isolation.network_for("codex", "b" * 8 + "-2")
        self.assertNotEqual(first["qdrant_prefix"], second["qdrant_prefix"])
        self.assertIn(["QDRANT_COLLECTION_PREFIX", first["qdrant_prefix"]], first["setenv"])
        self.assertIn(["npm_config_offline", "true"], second["setenv"])
        self.assertRegex(first["qdrant_prefix"], r"\A[A-Za-z0-9_-]+\Z")   # socraticode's own check (constants.js:61)

    def test_a_request_head_is_parsed_strictly(self):
        nf = self.nf
        self.assertEqual(nf.parse_head(b"GET /v1/models HTTP/1.1\r\nHost: x")[0:3], ("GET", "/v1/models", "HTTP/1.1"))
        for head in (b"GET /v1/models HTTP/2.0", b"GET /v1/models", b"GET  /v1/models HTTP/1.1",
                     b"GET /v1/models HTTP/1.1\r\n folded: x", b"GET /v1/models HTTP/1.1\r\nbad header",
                     b"G\xc3T /v1/models HTTP/1.1"):
            with self.assertRaises(nf.Denied, msg=head):
                nf.parse_head(head)


class Round5Grading(unittest.TestCase):
    """CC item task-ns2604-coop-20261006T143846Z, (a), and item task-ns2604-coop-20261006T144256Z."""

    @classmethod
    def setUpClass(cls):
        import grade
        grade.skill_usage()   # the shell-text rules (tools/skill-usage) for segments()

    def _claude_call(self, cid, args, result):
        return {"id": cid, "name": "mcp__ai-memory__memory_query", "input": args, "status": "ok",
                "result": {"text": json.dumps(result)}}

    def test_ai_memory_scopes(self):
        import grade
        own, other, fixture = str(uuid.uuid4()), str(uuid.uuid4()), "0a1b2c3d"
        calls = [self._claude_call("own", {"query": "x", "workspace": "organic-e2e", "project": own},
                                   {"hits": [{"path": "notes/a.md"}]}),
                 self._claude_call("global", {"query": "x", "global": True},
                                   {"hits": [{"workspace": "organic-e2e", "project": other, "path": "b.md"}]}),
                 self._claude_call("asked", {"query": "x", "workspace": "organic-e2e", "project": other},
                                   {"hits": [{"path": "c.md"}]}),
                 self._claude_call("legacy", {"query": "x", "global": True},
                                   {"hits": [{"workspace": "default", "project": fixture, "path": "d.md"}]}),
                 self._claude_call("empty", {"query": "x", "workspace": "organic-e2e", "project": other}, {"hits": []}),
                 self._claude_call("implicit", {"query": "x"}, {"hits": []}),
                 # ai-memory 2.5.2 returns an implicit query's hits without their scope (id, path, title, snippet, rank).
                 self._claude_call("implicit-hits", {"query": "x"},
                                   {"hits": [{"id": "p1", "path": "sessions/s.md", "title": "t", "snippet": "s", "rank": -1}]})]
        result = grade.ai_memory_check(grade.ai_memory_calls({"calls": calls}, "claude"), own, {fixture})
        self.assertEqual(sorted(result["global_queries"]), ["global", "legacy"])
        self.assertEqual(sorted(result["implicit_scope_calls"]), ["implicit", "implicit-hits"])
        self.assertEqual(sorted(b["call_id"] for b in result["foreign_scope_pages"]), ["asked", "global", "legacy"])
        self.assertEqual([u["call_id"] for u in result["unverifiable_scope_pages"]], ["implicit-hits"])

    def test_ai_memory_codex_items(self):
        import grade
        own, other = str(uuid.uuid4()), str(uuid.uuid4())
        items = [{"id": "i1", "type": "mcp_tool_call", "server": "ai-memory", "tool": "memory_query", "status": "completed",
                  "arguments": json.dumps({"query": "x", "global": True}),
                  "result": {"content": [{"type": "text", "text": json.dumps(
                      {"hits": [{"workspace": "organic-e2e", "project": other}]})}]}}]
        calls = grade.ai_memory_calls({"all_items": items}, "codex")
        self.assertEqual(len(calls), 1)
        result = grade.ai_memory_check(calls, own, set())
        self.assertEqual(result["global_queries"], ["i1"])
        self.assertEqual([b["call_id"] for b in result["foreign_scope_pages"]], ["i1"])

    def test_host_service_tags(self):
        import grade
        calls = [{"id": "a", "name": "Bash", "input": {"command": "systemctl --user status app.service"}},
                 {"id": "b", "name": "Bash", "input": {"command": "systemd-run --user --scope true"}},
                 {"id": "c", "name": "Bash", "input": {"command": "docker ps && podman images"}},
                 {"id": "d", "name": "Bash", "input": {"command": "curl -s http://127.0.0.1:29374/api/health"}},
                 {"id": "e", "name": "Bash", "input": {"command": "systemctl status ssh"}}]
        tags = grade.host_service_tags({"calls": calls}, "claude")
        self.assertEqual(tags, {"user-systemd": ["a", "b"], "docker": ["c"], "ai-memory-http": ["d"]})

    def test_residual_channel_tags(self):
        """GPT read of 2044b2ab: WSL interop, the gateway's management routes and other loopback services are tagged
        (diagnostic only); the ai-memory server keeps its own tag."""
        import grade
        calls = [{"id": "w", "name": "Bash", "input": {"command": "/mnt/c/Windows/System32/cmd.exe /c type x"}},
                 {"id": "p", "name": "Bash", "input": {"command": "powershell.exe -c Get-Content y"}},
                 {"id": "g", "name": "Bash", "input": {"command": "curl -s http://127.0.0.1:21128/api/usage/call-logs"}},
                 {"id": "l", "name": "Bash", "input": {"command": "curl -s localhost:21808/api/sessions"}},
                 {"id": "m", "name": "Bash", "input": {"command": "curl -s http://127.0.0.1:29374/api/health"}},
                 {"id": "n", "name": "Bash", "input": {"command": "ls -la"}}]
        tags = grade.host_service_tags({"calls": calls}, "claude")
        self.assertEqual(tags, {"wsl-interop": ["p", "w"], "gateway-management-api": ["g"], "local-service-http": ["l"],
                                "ai-memory-http": ["m"]})

    def _collect(self, rows, details, request_ids=("req-a", "req-b"), forward=None):
        """common.gateway_calls_for_trial against a stand-in gateway: the list answers rows; a detail answers from
        details, or fails when details holds an exception. forward is the trial's gateway forward record."""
        import common

        def fake(path, timeout=30):
            if path.startswith("/api/usage/call-logs?"):
                return rows if "offset=0" in path else []
            answer = details[path.rsplit("/", 1)[1]]
            if isinstance(answer, Exception):
                raise answer
            return answer

        saved = common.gateway_get
        common.gateway_get = fake
        try:
            return common.gateway_calls_for_trial(list(request_ids), "2026-10-06T12:00:00Z", "2026-10-06T13:00:00Z",
                                                  **({} if forward is None else {"forward": forward}))
        finally:
            common.gateway_get = saved

    def test_g11_requires_every_required_call(self):
        """GPT read of 80be1483, P2-1: G11 fails closed unless every required call (the trial's own model-call request
        ids) has collected tier and effort evidence. Collection to grading: A good and B's detail failed; A good and B
        unmatched; and a required call from another thread, which is kept (no thread filter drops it)."""
        import grade
        good = {"requestBody": {"client_metadata": {"thread_id": "t1"}, "reasoning": {"effort": "max"}},
                "pipelinePayloads": {"providerRequest": {"service_tier": "default", "reasoning": {"effort": "max"}}}}
        other_thread = json.loads(json.dumps(good))
        other_thread["requestBody"]["client_metadata"]["thread_id"] = "t-child"
        base = {"requested_turn_context": "max", "gateway_build": "b", "gateway_calls": 2, "gateway_forwarded": ["max"]}
        # Round 6d: the call log's own id equals the request id (strict); the correlation id is a different value.
        row = lambda rid: {"id": rid, "correlationId": "c-" + rid, "timestamp": "2026-10-06T12:00:01Z",
                           "path": "/v1/responses"}

        # Round 6e: the forward counted two admitted model calls, each with a request id.
        counted = {"gateway_model_requests": 2, "gateway_model_calls_without_id": [], "unparsed_rows": 0}

        def judge(out):
            calls = [c for v in out["by_thread"].values() for c in v]
            effort = {**base, "tier_calls": [{"id": c["id"], "forwarded": c.get("forwarded_service_tier")} for c in calls]}
            coverage = grade.call_coverage(["req-a", "req-b"], grade.evidence_calls(calls), counted)
            return coverage, grade.g11_trial_ok(effort, "default", coverage)

        both = self._collect([row("req-a"), row("req-b")], {"req-a": good, "req-b": other_thread})
        coverage, ok = judge(both)
        self.assertTrue(ok, coverage)   # the call from another thread is kept and counted
        failed = self._collect([row("req-a"), row("req-b")], {"req-a": good, "req-b": TimeoutError()})
        coverage, ok = judge(failed)
        self.assertFalse(ok)
        self.assertEqual((coverage["missing"], coverage["incomplete"]), ([], ["req-b"]))
        unmatched = self._collect([row("req-a")], {"req-a": good})
        coverage, ok = judge(unmatched)
        self.assertFalse(ok)
        self.assertEqual(coverage["missing"], ["req-b"])
        self.assertEqual(unmatched["unresolved_request_ids"], ["req-b"])
        self.assertFalse(grade.call_coverage([], [])["ok"])   # no required call recorded: nothing to establish
        # Round 6e (GPT read of b2d44f73, P2): the admitted model calls must be counted, each with an id of its own.
        evidence = grade.evidence_calls([c for v in both["by_thread"].values() for c in v])
        ids = ["req-a", "req-b"]
        self.assertTrue(grade.call_coverage(ids, evidence, counted)["ok"])
        self.assertFalse(grade.call_coverage(ids, evidence)["ok"])   # no count in the record: absent is not empty
        without_list = {k: v for k, v in counted.items() if k != "gateway_model_calls_without_id"}
        self.assertFalse(grade.call_coverage(ids, evidence, without_list)["ok"])
        self.assertFalse(grade.call_coverage(ids, evidence, {**counted, "gateway_model_requests": 3})["ok"])
        self.assertFalse(grade.call_coverage(ids, evidence, {**counted, "unparsed_rows": 1})["ok"])
        self.assertFalse(grade.call_coverage(ids, evidence, {**counted, "unparsed_rows": None})["ok"])
        shared = grade.call_coverage(["req-a", "req-a"], evidence, counted)
        self.assertFalse(shared["ok"])
        self.assertEqual(shared["duplicate_ids"], ["req-a"])

    def test_only_model_calls_are_required(self):
        """The gateway forward's required calls are the model calls (each leaves a call-log row); a model-list read is
        kept apart. Round 6e (GPT read of b2d44f73, P2): they are counted from their admission rows, so a model call
        whose response carried no request id, or that has no outcome row, is listed and never dropped."""
        import netfilter

        def summarize(rows, tail=""):
            with tempfile.TemporaryDirectory() as tmp:
                log = Path(tmp) / "access.jsonl"
                log.write_text("\n".join(json.dumps(r) for r in rows) + "\n" + tail)
                return netfilter.summarize(log)

        def pair(conn, path, method="POST", forward="gateway", **outcome):
            base = {"forward": forward, "method": method, "path": path, "conn": conn}
            return [{**base, "decision": "admitted"}, {**base, "decision": "allowed", "status": 200, **outcome}]

        rows = (pair("1-1", "/v1/responses", request_id="r1") + pair("1-2", "/v1/responses/compact", request_id="r2")
                + pair("1-3", "/v1/models", "GET", request_id="m1")
                + pair("1-4", "/v1/responses")                          # answered without a request id
                + pair("1-5", "/v1/chat/completions")[:1]              # admitted, and no outcome row
                + pair("1-6", "/v1/logs", forward="otlp")
                + [{"forward": "gateway", "method": "GET", "path": "/api/health", "decision": "denied", "reason": "x"}])
        summary = summarize(rows)
        self.assertEqual(len(summary["gateway_request_ids"]) + len(summary.get("gateway_model_calls_without_id") or []), 4,
                         "an admitted model call is missing from the summary")
        self.assertEqual(summary["gateway_request_ids"], ["r1", "r2"])
        self.assertEqual(summary["gateway_other_request_ids"], ["m1"])
        self.assertEqual(summary["gateway_model_requests"], 4)
        self.assertEqual([(c["conn"], c["method"], c["path"], c["outcome"], c["status"])
                          for c in summary["gateway_model_calls_without_id"]],
                         [("1-4", "POST", "/v1/responses", "allowed", 200),
                          ("1-5", "POST", "/v1/chat/completions", None, None)])
        # An admission is not a second request: requests and by_forward count outcomes.
        self.assertEqual((summary["requests"], summary["admitted"], summary["unparsed_rows"]), (6, 6, 0))
        self.assertEqual(summary["by_forward"], {"gateway": {"allowed": 4, "denied": 1}, "otlp": {"allowed": 1}})
        # A log without admission rows (written before round 6e): an allowed model row without an id is still a call.
        earlier = summarize([{"forward": "gateway", "decision": "allowed", "path": "/v1/responses", "request_id": "r1"},
                             {"forward": "gateway", "decision": "allowed", "path": "/v1/responses"}])
        self.assertEqual((earlier["gateway_model_requests"], earlier["gateway_request_ids"],
                          len(earlier["gateway_model_calls_without_id"])), (2, ["r1"], 1))
        # A row that cannot be read is counted; a missing log counts nothing, which is unknown and never zero.
        self.assertEqual(summarize(pair("1-1", "/v1/responses", request_id="r1"), '{"forward": "gatew')["unparsed_rows"], 1)
        missing = netfilter.summarize(Path("/nonexistent/access.jsonl"))
        self.assertEqual((missing["log"], missing["gateway_model_requests"], missing["gateway_model_calls_without_id"]),
                         ("missing", None, None))

    def test_the_access_log_counts_a_model_call_at_admission(self):
        """Round 6e (GPT read of b2d44f73, P2): netfilter's own Filter in front of a stand-in gateway. Every admitted
        model call is in the log from its admission, whatever its response carries: with its id, or listed without
        one (a response without the header, a call in flight when the forwarder stops, a gateway that is down)."""
        import netfilter
        with tempfile.TemporaryDirectory() as tmp:
            log = _relay_log(Path(tmp), ["req-a", None, "hang", "down"])
            text = log.read_text()
            summary = netfilter.summarize(log)
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual(len(summary["gateway_request_ids"]) + len(summary.get("gateway_model_calls_without_id") or []), 4,
                         "an admitted model call is missing from the summary")
        self.assertEqual(summary["gateway_model_requests"], 4)
        self.assertEqual(summary["gateway_request_ids"], ["req-a"])
        without = summary["gateway_model_calls_without_id"]
        self.assertEqual([(c["outcome"], c["status"]) for c in without],
                         [("allowed", 200), (None, None), ("upstream-unreachable", None)])
        for call in without:
            self.assertTrue(call["conn"] and call["at"], call)
            self.assertEqual((call["method"], call["path"]), ("POST", "/v1/responses"))
        # Each admission row comes before its connection's outcome row, and the log keeps no header or body.
        order = [(r["decision"], r.get("conn")) for r in rows]
        self.assertEqual(len({conn for decision, conn in order if decision == "admitted"}), 4, order)
        for decision, conn in order:
            if decision != "admitted":
                self.assertLess(order.index(("admitted", conn)), order.index((decision, conn)), order)
        self.assertEqual((summary["requests"], summary["admitted"]), (3, 4))
        self.assertNotIn("X-Answer", text)
        self.assertEqual({key for row in rows for key in row} - {"at", "forward", "method", "path", "decision", "conn",
                                                                 "status", "request_id"}, set())

    def test_a_model_call_without_a_request_id_fails_g11_and_the_calibration(self):
        """Round 6e (GPT read of b2d44f73, P2), the regression through summarization, collection and grading: call A's
        response carries its request id and its call-log row holds full evidence, and call B's response carries no id.
        B is listed, G11 fails for the trial and the calibration fails. With both ids present, all three pass."""
        import grade
        import netfilter
        good = {"requestBody": {"client_metadata": {"thread_id": "t1"}, "reasoning": {"effort": "max"}},
                "pipelinePayloads": {"providerRequest": {"service_tier": "default", "reasoning": {"effort": "max"}}}}
        base = {"requested_turn_context": "max", "gateway_build": "b", "gateway_forwarded": ["max"]}
        row = lambda rid: {"id": rid, "correlationId": "c-" + rid, "timestamp": "2026-10-06T12:00:01Z",
                           "path": "/v1/responses"}

        def chain(answers, log_rows):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                summary = netfilter.summarize(_relay_log(root, answers))                          # summarization
                record = self._collect([row(r) for r in log_rows], {r: good for r in log_rows},   # collection
                                       summary["gateway_request_ids"], summary)
                (root / "gateway").mkdir()
                (root / "gateway" / "t1.json").write_text(json.dumps(record))
                calls = [c for v in record["by_thread"].values() for c in v]                      # grading
                effort = {**base, "gateway_calls": len(calls),
                          "tier_calls": [{"id": c["id"], "forwarded": c.get("forwarded_service_tier")} for c in calls]}
                coverage = grade.call_coverage(summary["gateway_request_ids"], grade.evidence_calls(calls), summary)
                return (summary, record, coverage, grade.g11_trial_ok(effort, "default", coverage),
                        grade.call_id_calibration(root, "t1"))

        summary, record, coverage, g11, calibration = chain(["req-a", None], ["req-a"])
        self.assertFalse(g11, coverage)
        self.assertFalse(coverage["ok"])
        self.assertEqual((coverage["required"], coverage["model_requests"], coverage["missing"], coverage["incomplete"]),
                         (1, 2, [], []))   # A's own evidence is complete: only the call without an id fails
        self.assertEqual([(c["path"], c["outcome"], c["status"]) for c in coverage["without_id"]],
                         [("/v1/responses", "allowed", 200)])
        self.assertIn("no request id", coverage["uncounted"])
        self.assertEqual((record["request_ids"], record["unmatched_request_ids"], record["model_requests"]), (1, 0, 2))
        self.assertEqual(record["model_calls_without_id"], summary["gateway_model_calls_without_id"])
        self.assertEqual(record["detail_requests"], ["req-a"])   # nothing is looked up for the call without an id
        self.assertFalse(calibration["pass"])
        self.assertIn("no request id", calibration["cause"])
        self.assertEqual(calibration["model_calls_without_id"], summary["gateway_model_calls_without_id"])
        # The same chain with both responses carrying their ids passes, so the failure above is B's missing id.
        summary, record, coverage, g11, calibration = chain(["req-a", "req-b"], ["req-a", "req-b"])
        self.assertTrue(g11, coverage)
        self.assertEqual((coverage["model_requests"], coverage["without_id"], coverage["uncounted"]), (2, [], None))
        self.assertTrue(calibration["pass"], calibration)

    def test_a_tool_that_cannot_run_is_not_testable(self):
        """Round 6b (1): a tool under test that cannot run inside a trial has its cells marked NOT-TESTABLE with the
        cause, never NOT-READY; the others are testable."""
        import grade
        oir = {"socraticode|claude-native": {}, "socraticode|codex-native": {}, "chrome-devtools|codex-env": {},
               "jcodemunch|claude-env": {}}
        selftest = {"tools_under_test": {
            "socraticode": {"claude": {"testable": False, "cause": "QDRANT_URL points at 127.0.0.1:16333"},
                            "codex": {"testable": True, "cause": None}},
            "chrome-devtools": {"codex": {"testable": False, "cause": "does not start offline"}}}}
        grade.mark_testability(oir, selftest)
        self.assertEqual(oir["socraticode|claude-native"]["testability"], "NOT-TESTABLE")
        self.assertIn("16333", oir["socraticode|claude-native"]["testability_cause"])
        self.assertEqual(oir["socraticode|codex-native"]["testability"], "testable")
        self.assertEqual(oir["chrome-devtools|codex-env"]["testability"], "NOT-TESTABLE")
        self.assertEqual(oir["jcodemunch|claude-env"]["testability"], "testable")
        self.assertNotIn("NOT-READY", json.dumps(oir))

    def test_the_calibration_cell_runs_first_and_its_check_fails_closed(self):
        """Round 6d (P2): codex-native-gate0 is the first stage-2 cell, and `grade.py calibration` exits non-zero
        unless the calibration passed (pilot.py stops before any other cell)."""
        import grade
        import pilot
        self.assertEqual(pilot.CODEX_STAGE2[0], pilot.CALIBRATION_CELL)
        self.assertEqual(pilot.CALIBRATION_CELL, "codex-native-gate0")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gateway").mkdir()
            (root / "run.json").write_text(json.dumps({"tests_by_ref": {"r1": {"gate_trial": True, "stage": 2}}}))
            (root / "ledger.jsonl").write_text(json.dumps({"phase": "launched", "ref": "r1", "trial_id": "t1"}) + "\n")
            counted = {"model_requests": 2, "model_calls_without_id": [], "access_log_unparsed_rows": 0}
            (root / "gateway" / "t1.json").write_text(json.dumps(
                {"request_ids": 2, "unmatched_request_ids": 1, "by_thread": {"x": [{"id": "a"}]}, **counted}))
            self.assertEqual(grade.main(["calibration", "--run-root", str(root)]), 1)
            (root / "gateway" / "t1.json").write_text(json.dumps(
                {"request_ids": 2, "unmatched_request_ids": 0, "by_thread": {"x": [{"id": "a"}, {"id": "b"}]}, **counted}))
            self.assertEqual(grade.main(["calibration", "--run-root", str(root)]), 0)
            self.assertEqual(oct((root / "calibration.json").stat().st_mode & 0o777), "0o600")

    def test_the_calibration_cell_passes_only_on_a_matched_key(self):
        """Round 6b (2): the gate-0 CL3 G1 trial calibrates the call-id key; any unmatched id, no id or no record
        fails it (and so G11)."""
        import grade
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gateway").mkdir()
            def write(tid, data):
                (root / "gateway" / f"{tid}.json").write_text(json.dumps(data))
            counted = {"model_requests": 3, "model_calls_without_id": [], "access_log_unparsed_rows": 0}
            matched = {"request_ids": 3, "unmatched_request_ids": 0, "by_thread": {"t": [{"id": "a"}, {"id": "b"}]}}
            write("ok", {**matched, **counted})
            write("unmatched", {"request_ids": 3, "unmatched_request_ids": 1, "by_thread": {"t": [{"id": "a"}]}, **counted})
            write("none", {"request_ids": 0, "unmatched_request_ids": 0, "by_thread": {}, **counted, "model_requests": 0})
            # Round 6e (GPT read of b2d44f73, P2): a model call without a request id fails the calibration, and so does
            # a record that does not establish there was none.
            no_id = {"conn": "1-4", "at": "2026-10-06T12:00:02Z", "method": "POST", "path": "/v1/responses",
                     "outcome": "allowed", "status": 200}
            write("no-id", {**matched, **counted, "model_requests": 4, "model_calls_without_id": [no_id]})
            write("uncounted", matched)                                           # a record from before round 6e
            write("unread", {**matched, **counted, "access_log_unparsed_rows": 1})
            write("shared-id", {**matched, **counted, "model_requests": 4})        # four calls, three distinct ids
            self.assertTrue(grade.call_id_calibration(root, "ok")["pass"])
            for tid in ("unmatched", "none", "missing", None, "no-id", "uncounted", "unread", "shared-id"):
                result = grade.call_id_calibration(root, tid)
                self.assertFalse(result["pass"], tid)
                self.assertTrue(result["cause"], tid)
            listed = grade.call_id_calibration(root, "no-id")
            self.assertIn("no request id", listed["cause"])
            self.assertEqual(listed["model_calls_without_id"], [no_id])

    def test_g11_fails_closed_on_tier_evidence(self):
        """GPT read of a513616d, P2: the launch tier must be default and every call's forwarded tier normal. A missing
        tier, a partly missing one, an unrecognized one or a non-default launch fails, with the call ids reported."""
        import grade
        base = {"requested_turn_context": "max", "gateway_build": "b", "gateway_calls": 2, "gateway_forwarded": ["max"]}
        full = {**base, "tier_calls": [{"id": "c1", "forwarded": "default"}, {"id": "c2", "forwarded": "(unset)"}]}
        self.assertTrue(grade.g11_trial_ok(full, "default", {"ok": True}))
        self.assertFalse(grade.g11_trial_ok(full, "default"))   # no coverage record: fail closed
        cases = {"all tiers missing": ({**base, "tier_calls": [{"id": "c1", "forwarded": None},
                                                               {"id": "c2", "forwarded": None}]}, "default", ["c1", "c2"]),
                 "one tier missing": ({**base, "tier_calls": [{"id": "c1", "forwarded": "default"},
                                                              {"id": "c2", "forwarded": None}]}, "default", ["c2"]),
                 "no calls recorded": ({**base, "tier_calls": []}, "default", []),
                 "priority forwarded": ({**base, "tier_calls": [{"id": "c1", "forwarded": "priority"}]}, "default", []),
                 "auto forwarded": ({**base, "tier_calls": [{"id": "c1", "forwarded": "auto"}]}, "default", []),
                 "launch tier unrecorded": (full, None, []),
                 "launch tier priority": (full, "priority", [])}
        for label, (effort, launch, missing) in cases.items():
            self.assertFalse(grade.g11_trial_ok(effort, launch, {"ok": True}), label)
            evidence = grade.tier_evidence(effort, launch)
            self.assertFalse(evidence["ok"], label)
            self.assertEqual(evidence["missing_calls"], missing, label)
        self.assertEqual(grade.tier_evidence(cases["priority forwarded"][0], "default")["unrecognized_calls"], ["c1"])

    def _codex_item(self, cid, tool, args, payload):
        return {"id": cid, "type": "mcp_tool_call", "server": "ai-memory", "tool": tool, "status": "completed",
                "arguments": json.dumps(args), "result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}

    def _claude_tool(self, cid, tool, args, payload):
        return {"id": cid, "name": f"mcp__ai-memory__{tool}", "input": args, "status": "ok",
                "result": {"text": json.dumps(payload)}}

    def test_ai_memory_scalar_reads_and_empty_queries(self):
        """GPT read of a513616d, P2: page detection by each tool's response contract, in both clients. A scalar
        memory_read_page of another trial's scope (its scope only in the arguments) invalidates the trial; an empty
        implicit query does not; an implicit read that returned a page is unverifiable. The validity and G13 decision
        is grade.ai_memory_invalidates, which both use."""
        import grade
        own, other = str(uuid.uuid4()), str(uuid.uuid4())
        page = {"path": "notes/a.md", "body": "the answer", "frontmatter": {}}
        foreign_args = {"path": "notes/a.md", "workspace": "organic-e2e", "project": other}
        own_args = {"path": "notes/a.md", "workspace": "organic-e2e", "project": own}
        for client, make in (("claude", self._claude_tool), ("codex", self._codex_item)):
            def check(*calls):
                graded = {"calls": list(calls)} if client == "claude" else {"all_items": list(calls)}
                return grade.ai_memory_check(grade.ai_memory_calls(graded, client), own, set())
            scalar_foreign = check(make("r1", "memory_read_page", foreign_args, page))
            self.assertEqual([b["call_id"] for b in scalar_foreign["foreign_scope_pages"]], ["r1"], client)
            self.assertTrue(grade.ai_memory_invalidates(scalar_foreign), client)
            scalar_own = check(make("r2", "memory_read_page", own_args, page))
            self.assertFalse(grade.ai_memory_invalidates(scalar_own), client)
            empty_implicit = check(make("q1", "memory_query", {"query": "x"}, {"hits": []}))
            self.assertEqual(empty_implicit["implicit_scope_calls"], ["q1"], client)
            self.assertEqual(empty_implicit["unverifiable_scope_pages"], [], client)
            self.assertFalse(grade.ai_memory_invalidates(empty_implicit), client)
            empty_foreign = check(make("q2", "memory_query", {"query": "x", "workspace": "organic-e2e", "project": other},
                                       {"hits": []}))
            self.assertFalse(grade.ai_memory_invalidates(empty_foreign), client)
            implicit_read = check(make("r3", "memory_read_page", {"path": "notes/a.md"}, page))
            self.assertEqual([u["call_id"] for u in implicit_read["unverifiable_scope_pages"]], ["r3"], client)
            self.assertTrue(grade.ai_memory_invalidates(implicit_read), client)
            empty_read = check(make("r4", "memory_read_page", foreign_args, {"path": "notes/a.md", "body": ""}))
            self.assertFalse(grade.ai_memory_invalidates(empty_read), client)

    def test_every_codex_launch_sets_the_normal_tier(self):
        import common
        import launcher
        import prepare
        cfg = {"binaries": {"codex": {"path": "/x/codex"}, "node": "/x/node", "codex_sdk_dir": "/x/sdk"},
               "gh_config_dir": "/x/gh", "codex_profile_layer": {"file": "/x/c.json", "config": {}}}
        line = launcher.codex_line(cfg, "tid", Path("/f"), Path("/c"), Path("/p"), Path("/l"), "read-only", "max",
                                   "organic-e2e", 1800)
        self.assertEqual(launcher.codex_service_tier(cfg, "cli", line), "default")
        self.assertIsNone(launcher.codex_service_tier(cfg, "cli", line.replace("-c service_tier=default ", "")))
        self.assertEqual(launcher.codex_service_tier(cfg, "sdk", ""), "default")   # sdk_codex.mjs's configOverrides
        test = {"lane": "organic-e2e", "sandbox": "read-only", "ref": "r1", "task_text": "t"}
        text = prepare.app_server_config("c", "tid", test, Path("/f"), Path("/c"), Path("/gh"), "/usr/bin", 1800, {},
                                         "/x/wrapper")
        self.assertEqual(common.app_server_service_tier(text), "default")
        self.assertIn("codex_path_override: '/x/wrapper'", text.replace('"', "'"))


class GatewayCacheReading(unittest.TestCase):
    def _read(self, payload):
        """gateway_cache_state() against a stand-in gateway that answers only the allowlisted GET /api/cache; any
        other route (the secret-bearing settings routes among them) fails the test."""
        import common
        asked = []

        def fake(path, timeout=30):
            asked.append(path)
            if path != "/api/cache":
                raise AssertionError(f"a route outside the guard's allowlist was read: {path}")
            return payload

        saved = common.gateway_get
        common.gateway_get = fake
        try:
            return common.gateway_cache_state(), asked
        finally:
            common.gateway_get = saved

    def test_only_the_allowlisted_route_and_named_keys(self):
        """Round 5, (a): the reading keeps the cache switch and counters from GET /api/cache, and nothing else."""
        state, asked = self._read({"config": {"semanticCacheEnabled": True, "other": "x"},
                                   "semanticCache": {"hits": 0, "misses": 0, "dbEntries": 0, "memoryEntries": 0},
                                   "idempotency": {"windowMs": 5000, "activeKeys": 0},
                                   "promptCache": {"tokensSaved": 1}})
        self.assertEqual(asked, ["/api/cache"])
        self.assertEqual(state["verdict"], "semantic cache on")
        self.assertEqual(state["cache_config"], {"semanticCacheEnabled": True})
        self.assertNotIn("promptCache", json.dumps(state))
        off, _ = self._read({"config": {"semanticCacheEnabled": False}, "semanticCache": {"hits": 0}})
        self.assertEqual(off["verdict"], "semantic cache off")

    def test_the_amended_gate0_cache_check(self):
        """Gate 0 amendment (CC item task-ns2604-coop-20261006T155742Z (A)), by behaviour: the cache may stay on; the
        stage-1 reading must show 0 hits and its counts, at the gateway build and Codex version the evidence was read
        at. Anything else fails."""
        import grade
        good = {"gateway_cache": {"verdict": "semantic cache on", "semantic_cache": {"hits": 0, "misses": 0,
                                                                                     "dbEntries": 0, "memoryEntries": 0}},
                "gateway_build": "omniroute-3.8.51-5f4b3d577-affinity-pr15167",
                "binaries": {"codex": {"version": "codex-cli 0.160.1"}}}
        self.assertTrue(grade.gateway_cache_gate(good)["pass"])
        bad = {"a hit": {"gateway_cache": {"semantic_cache": {"hits": 1, "dbEntries": 0, "memoryEntries": 0}}},
               "no reading": {"gateway_cache": None},
               "a failed reading": {"gateway_cache": {"error": "URLError"}},
               "another gateway build": {"gateway_build": "omniroute-3.8.52-abc"},
               "another Codex": {"binaries": {"codex": {"version": "codex-cli 0.161.0"}}},
               "no counts": {"gateway_cache": {"semantic_cache": {"hits": 0}}}}
        for label, change in bad.items():
            cfg = json.loads(json.dumps(good))
            cfg.update(change)
            self.assertFalse(grade.gateway_cache_gate(cfg)["pass"], label)

    def test_closure_evidence_is_required(self):
        """GPT read of a513616d, P2: gate 0 and G13 require every verified denial; a missing or failed probe fails."""
        import grade
        full = {"network": {"expect": {k: True for k in grade.CLOSURE_EXPECTATIONS}}}
        self.assertTrue(grade.closure_evidence(full)["pass"])
        self.assertFalse(grade.closure_evidence(None)["pass"])
        self.assertFalse(grade.closure_evidence({"network": {}})["pass"])
        for key in grade.CLOSURE_EXPECTATIONS:
            missing = {"network": {"expect": {k: True for k in grade.CLOSURE_EXPECTATIONS if k != key}}}
            failed = {"network": {"expect": {k: (k != key) for k in grade.CLOSURE_EXPECTATIONS}}}
            self.assertFalse(grade.closure_evidence(missing)["pass"], key)
            self.assertFalse(grade.closure_evidence(failed)["pass"], key)
        # Payload-flag counts alone never establish closure.
        self.assertFalse(grade.closure_evidence({"gateway_logs": {"with_request_body": 0}})["pass"])

    def test_the_collector_requests_only_the_trials_own_ids(self):
        """GPT read of a513616d, P1 (CC 16:43Z): the detail GET is made only for call ids the trial's own responses
        carried; a foreign id is never requested, and with no own id nothing is requested at all."""
        import common
        rows = [{"id": "own-1", "correlationId": "c-own-1", "timestamp": "2026-10-06T12:00:01Z", "path": "/v1/responses"},
                {"id": "foreign-1", "correlationId": "c-foreign-1", "timestamp": "2026-10-06T12:00:02Z",
                 "path": "/v1/responses"},
                {"id": "own-2", "correlationId": "c-own-2", "timestamp": "2026-10-06T12:00:03Z", "path": "/v1/responses"}]
        asked = []

        def fake(path, timeout=30):
            asked.append(path)
            if path.startswith("/api/usage/call-logs?"):
                return rows if "offset=0" in path else []
            return {"requestBody": {"client_metadata": {"thread_id": "t1"}, "reasoning": {"effort": "max"},
                                    "input": "a prompt that must not be kept"},
                    "pipelinePayloads": {"providerRequest": {"service_tier": "default", "reasoning": {"effort": "max"}}}}

        saved = common.gateway_get
        common.gateway_get = fake
        try:
            out = common.gateway_calls_for_trial(["own-1", "own-2"], "2026-10-06T12:00:00Z", "2026-10-06T12:10:00Z")
            details = [p for p in asked if not p.startswith("/api/usage/call-logs?")]
            asked.clear()
            nothing = common.gateway_calls_for_trial([], "2026-10-06T12:00:00Z", "2026-10-06T12:10:00Z")
            asked.clear()
            # Round 6d (GPT read of 50752dde, P2): a request id equal only to a row's correlationId matches nothing.
            correlation_only = common.gateway_calls_for_trial(["c-own-1"], "2026-10-06T12:00:00Z",
                                                              "2026-10-06T12:10:00Z")
            correlation_details = [p for p in asked if not p.startswith("/api/usage/call-logs?")]
        finally:
            common.gateway_get = saved
        self.assertEqual(details, ["/api/usage/call-logs/own-1", "/api/usage/call-logs/own-2"])
        self.assertEqual(out["unmatched_request_ids"], 0)
        self.assertNotIn("a prompt that must not be kept", json.dumps(out))
        self.assertEqual(sorted(c["id"] for c in out["by_thread"]["t1"]), ["own-1", "own-2"])
        self.assertEqual(nothing["detail_requests"], [])
        self.assertEqual(correlation_details, [])
        self.assertEqual(correlation_only["unresolved_request_ids"], ["c-own-1"])

    def test_the_harness_calls_only_allowlisted_gateway_routes(self):
        """The allowlist rule (CC 15:57Z): every /api route the harness's code names is one the repository's command
        guard admits (scripts/hooks/secret_path_guard.py, K4_GW_ROWS and its call-log id exception)."""
        import re as _re
        allowed = {"/api/health", "/api/settings/compression", "/api/context/combos", "/api/model-capability-overrides",
                   "/api/resilience", "/api/settings/feature-flags", "/api/cache", "/api/analytics/compression",
                   "/api/usage/call-logs", "/api/usage/provider-limits"}
        found = set()
        for path in HERE.glob("*.py"):
            if path.name == "test_isolation.py":
                continue
            for line in path.read_text().splitlines():
                code = line.split("#", 1)[0]
                for match in _re.finditer(r'gateway_get\(f?"(/api/[^"?{]*)', code):
                    found.add(match.group(1).rstrip("/"))
        self.assertTrue(found)
        for route in found:
            self.assertTrue(route in allowed or route == "/api/usage/call-logs", route)

    def test_the_log_exposure_reading_keeps_only_flag_counts(self):
        """GPT read of 2044b2ab: whether call-log payloads are stored, from the allowlisted list route (limit only);
        no payload field reaches the record."""
        import common
        asked = []
        rows = [{"id": "a", "hasRequestBody": True, "hasResponseBody": True, "hasPipelineDetails": False,
                 "requestBody": {"input": "a trial's prompt"}},
                {"id": "b", "hasRequestBody": True, "hasResponseBody": False, "hasPipelineDetails": True}]

        def fake(path, timeout=30):
            asked.append(path)
            if path != "/api/usage/call-logs?limit=20":
                raise AssertionError(f"unexpected route: {path}")
            return rows

        saved = common.gateway_get
        common.gateway_get = fake
        try:
            state = common.gateway_log_exposure()
        finally:
            common.gateway_get = saved
        self.assertEqual(asked, ["/api/usage/call-logs?limit=20"])
        self.assertEqual((state["rows"], state["with_request_body"], state["with_response_body"],
                          state["with_pipeline_details"]), (2, 2, 1, 1))
        self.assertFalse(state["credentials_sent"])
        self.assertNotIn("a trial's prompt", json.dumps(state))

    def test_a_call_answered_by_the_semantic_cache_is_counted(self):
        import common
        pipeline = {"providerRequest": {"service_tier": "priority", "reasoning": {"effort": "max"}}}
        self.assertEqual(common.forwarded_service_tier(pipeline), "priority")
        self.assertEqual(common.forwarded_service_tier({"providerRequest": {"model": "m"}}), "(unset)")
        self.assertIsNone(common.forwarded_service_tier(None))


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class WrappedLaunch(unittest.TestCase):
    def test_a_nested_namespace_is_no_escape(self):
        """Codex's own sandbox, a nested bwrap or `unshare -rm` puts a process in a namespace below the trial's: counted
        apart, never as outside, and its locked mounts cannot be unmounted to reveal a hidden root."""
        import isolation
        import launcher
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        try:
            fixture.mkdir(parents=True)
            (work / "prompts").mkdir(parents=True)
            (work / "prompts" / f"{trial_id}.txt").write_text("prompt\n")
            (work / "clones" / trial_id).mkdir(parents=True)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", fixture,
                                  clone=work / "clones" / trial_id, prompt=work / "prompts" / f"{trial_id}.txt")
            isolation.prepare_dirs(plan)
            probe = isolation.COORDINATION_ROOT / "command-center" / "ledger.jsonl"
            line = (f"unshare -rm sh -c 'umount {isolation.COORDINATION_ROOT} 2>/dev/null; "
                    f"if cat {probe} >/dev/null 2>&1; then echo REVEALED > {fixture}/verdict; "
                    f"else echo hidden > {fixture}/verdict; fi; sleep 4'")
            run_cfg = {"binaries": {"claude": {"realpath": "/nonexistent/claude"}, "codex": {"realpath": "/nonexistent/codex"}},
                       "claude_completion": {"policy": "complete-at-result", "t_seconds": 60}}
            forwarder = isolation.NetworkForwarder(plan).start()
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    outcome = launcher.run_client(root, run_cfg, "codex", line, fixture, root / "s.jsonl",
                                                  root / "e.err", None, plan)
            finally:
                network_runtime = forwarder.stop()
            tree = outcome["isolation_runtime"]["tree"]
            self.assertEqual((fixture / "verdict").read_text().strip(), "hidden")
            self.assertGreaterEqual(tree["in_nested_namespaces"], 1, tree)
            self.assertEqual(tree["outside"], [], tree)
            rows = {"prepared": {"fixture_private": str(fixture)},
                    "launched": {"isolation": isolation.receipt(plan, ["bash", "-lc", "<line>"])},
                    "exit": {"isolation_runtime": outcome["isolation_runtime"], "network_runtime": network_runtime,
                             "gateway_cache": dict(READING)}}
            rows["launched"]["gateway_cache"] = dict(READING)
            result = isolation.check(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", rows)
            self.assertTrue(result["ok"], result["failures"])
        finally:
            import shutil
            shutil.rmtree(fixture, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)

    def test_run_client_records_the_namespace(self):
        import isolation
        import launcher
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        try:
            fixture.mkdir(parents=True)
            (work / "bin").mkdir(parents=True)
            (work / "prompts").mkdir(parents=True)
            (work / "prompts" / f"{trial_id}.txt").write_text("prompt\n")
            (work / "clones" / trial_id).mkdir(parents=True)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", fixture,
                                  clone=work / "clones" / trial_id, prompt=work / "prompts" / f"{trial_id}.txt")
            isolation.prepare_dirs(plan)
            events = [{"type": "thread.started", "thread_id": "t"},
                      {"type": "item.completed", "item": {"type": "agent_message", "id": "i1", "text": "done"}},
                      {"type": "turn.completed", "usage": {"input_tokens": 1}}]
            line = "sleep 2; printf '%s\\n' " + " ".join("'" + json.dumps(e) + "'" for e in events) + "; sleep 3"
            run_cfg = {"binaries": {"claude": {"realpath": "/nonexistent/claude"}, "codex": {"realpath": "/nonexistent/codex"}},
                       "claude_completion": {"policy": "complete-at-result", "t_seconds": 60}}
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outcome = launcher.run_client(root, run_cfg, "codex", line, fixture, root / "s.jsonl", root / "e.err", None,
                                              plan)
            runtime = outcome["isolation_runtime"]
            self.assertEqual(outcome["rc"], 0, outcome)
            self.assertTrue(runtime["namespace"], runtime)
            self.assertNotEqual(runtime["namespace"], runtime["host_namespace"])
            self.assertGreaterEqual(runtime["tree"]["processes_seen"], 1, runtime)
            self.assertEqual(runtime["tree"]["outside"], [], runtime)
            self.assertIsInstance(outcome["duration_exact_s"], float)
            self.assertIsNotNone(outcome["time_to_result_exact_s"])
        finally:
            import shutil
            shutil.rmtree(fixture, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)

    def test_the_cl7b_census_sees_the_tree_in_the_namespace(self):
        """GPT read of 2044b2ab (verification gap): CL7b's wrapper, run as promptfoo runs it, is sampled while it runs;
        its tree is in the trial's namespace, none outside, and G13 passes on the runtime record."""
        import isolation
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        try:
            fixture.mkdir(parents=True)
            (work / "prompts").mkdir(parents=True)
            (work / "prompts" / f"{trial_id}.txt").write_text("prompt\n")
            (work / "clones" / trial_id).mkdir(parents=True)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", fixture,
                                  clone=work / "clones" / trial_id, prompt=work / "prompts" / f"{trial_id}.txt")
            wrapper = isolation.write_app_server_wrapper(plan, "/usr/bin/sleep")
            forwarder = isolation.NetworkForwarder(plan).start()
            census = isolation.AppServerCensus(plan, interval=0.5).start()
            try:
                subprocess.run([str(wrapper), "3"], timeout=60, stdin=subprocess.DEVNULL, check=True)
            finally:
                tree = census.stop()
                network_runtime = forwarder.stop()
            self.assertGreaterEqual(tree["processes_seen"], 1, tree)
            self.assertEqual(tree["in_trial_namespace"], tree["processes_seen"], tree)
            self.assertEqual(tree["outside"], [], tree)
            self.assertGreaterEqual(tree["samples"], 2, tree)
            with tempfile.TemporaryDirectory() as tmp:
                saved = isolation.CODEX_SESSIONS
                isolation.CODEX_SESSIONS = Path(tmp)
                try:
                    runtime = isolation.app_server_runtime(plan, tree)
                finally:
                    isolation.CODEX_SESSIONS = saved
            rows = {"prepared": {"fixture_private": str(fixture)},
                    "launched": {"isolation": isolation.receipt(plan, ["/usr/bin/sleep", "app-server"])},
                    "exit": {"isolation_runtime": runtime, "network_runtime": network_runtime,
                             "gateway_cache": dict(READING)}}
            rows["launched"]["gateway_cache"] = dict(READING)
            result = isolation.check(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", rows)
            self.assertTrue(result["ok"], result["failures"])
            self.assertTrue(result["ipc_namespace"])
        finally:
            import shutil
            shutil.rmtree(fixture, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)

    def test_kill_reaches_the_client_gracefully(self):
        import isolation
        import launcher
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("claude")
        try:
            fixture.mkdir(parents=True)
            for path in (plan["settings"], plan["prompt"]):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n")
            isolation.prepare_dirs(plan)
            marker = fixture / "graceful"
            inner = f"trap 'sleep 1; echo graceful > {marker}; exit 0' TERM; while :; do sleep 0.2; done"
            line = f"timeout --signal=TERM --kill-after=30s 60 bash -c {json.dumps(inner)}"
            proc, info_fd = isolation.spawn(plan, ["bash", "-lc", line], start_new_session=True,
                                            stdin=subprocess.DEVNULL)
            isolation.read_info(info_fd)
            time.sleep(1.5)
            launcher._kill_group(proc, True)
            proc.wait(timeout=60)
            self.assertTrue(marker.exists(), "the client's TERM handler did not run before the namespace ended")
        finally:
            import shutil
            for path in (fixture, work, plan["own_project"]):
                if path:
                    shutil.rmtree(path, ignore_errors=True)


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class HostBrokers(unittest.TestCase):
    """P2-2, upheld by CC item task-ns2604-coop-20261006T151719Z (C1): negative tests. Each attempts, inside a trial's
    namespace, the connection that would let a process outside it read a hidden answer, and expects it to fail. Each
    runs only where the broker exists on the host (its socket outside is the control). A broker that did answer would
    run `true` as a transient unit, answer Docker's /_ping, or print cmd.exe's version: harmless."""

    @classmethod
    def setUpClass(cls):
        isolation, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        fixture.mkdir(parents=True)
        (work / "prompts").mkdir(parents=True)
        (work / "prompts" / f"{trial_id}.txt").write_text("prompt\n")
        (work / "clones" / trial_id).mkdir(parents=True)
        cls.isolation, cls.fixture, cls.work = isolation, fixture, work
        cls.plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", fixture,
                                  clone=work / "clones" / trial_id, prompt=work / "prompts" / f"{trial_id}.txt")
        isolation.prepare_dirs(cls.plan)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.fixture, ignore_errors=True)
        shutil.rmtree(cls.work, ignore_errors=True)

    def _inside(self, argv):
        result, _ = self.isolation.run_wrapped(self.plan, argv, timeout=90)
        return result

    def _absent_inside(self, path):
        result = self._inside(["sh", "-c", 'if [ -e "$1" ]; then echo PRESENT; else echo ABSENT; fi', "p", str(path)])
        return result.stdout.strip()

    def test_systemd_run_user_cannot_reach_the_user_manager(self):
        manager = RUNTIME / "systemd" / "private"
        bus = RUNTIME / "bus"
        if not (manager.is_socket() or bus.is_socket()):
            self.skipTest("no user manager socket on this host")
        self.assertEqual(self._absent_inside(manager), "ABSENT")
        self.assertEqual(self._absent_inside(bus), "ABSENT")
        result = self._inside(["systemd-run", "--user", "--pipe", "--wait", "--quiet", "true"])
        self.assertNotEqual(result.returncode, 0, (result.stdout, result.stderr))
        self.assertIn("connect", result.stderr.lower(), result.stderr)

    def test_docker_sock_is_unreachable(self):
        sock = RUNTIME / "docker.sock"
        if not sock.is_socket():
            self.skipTest("no rootless Docker socket on this host")
        self.assertEqual(self._absent_inside(sock), "ABSENT")
        result = self._inside(["curl", "-s", "-m", "10", "--unix-socket", str(sock), "http://localhost/_ping"])
        self.assertEqual(result.returncode, 7, (result.stdout, result.stderr))   # curl: failed to connect
        docker = shutil_which("docker")
        if docker:
            result = self._inside([docker, "-H", f"unix://{sock}", "version", "--format", "{{.Server.Version}}"])
            self.assertNotEqual(result.returncode, 0, (result.stdout, result.stderr))

    def test_wsl_interop_is_unreachable(self):
        interop = _wsl_interop_socket()
        if not interop or not WINDOWS_CMD.exists():
            self.skipTest("not a WSL host with interop")
        self.assertEqual(self._absent_inside(interop), "ABSENT")
        result = self._inside([str(WINDOWS_CMD), "/c", "ver"])
        self.assertNotEqual(result.returncode, 0, (result.stdout, result.stderr))
        self.assertNotIn("Microsoft Windows", result.stdout)

    def test_the_runtime_folder_is_private(self):
        runtime = RUNTIME
        marker = f"ut-{uuid.uuid4().hex[:8]}"
        try:
            result = self._inside(["sh", "-c", f'stat -c %a {runtime}; ls -A {runtime}; echo x > {runtime}/{marker}'])
            reached_host = (runtime / marker).exists()
        finally:
            (runtime / marker).unlink(missing_ok=True)   # a harness that binds the host's folder in would leave it there
        self.assertEqual(result.returncode, 0, result.stderr)
        # Round 6: the folder holds only the forwards' socket folder (empty otherwise).
        self.assertEqual(result.stdout.split(), ["700", "net"])
        self.assertFalse(reached_host, "a write to the private runtime folder reached the host's")

    def test_ssh_agent_socket_is_absent(self):
        agent = RUNTIME / "openssh_agent"
        if not agent.is_socket():
            self.skipTest("no ssh-agent socket in the runtime folder")
        self.assertEqual(self._absent_inside(agent), "ABSENT")


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class NetworkNamespace(unittest.TestCase):
    """Round 6 (CC item task-ns2604-coop-20261006T155742Z, (B)): negative tests from inside a trial's own network
    namespace, with its forwards served as a launch serves them. /api/usage/call-logs and /api/health on 21128 are
    unreachable (refused by the filter, never reaching the gateway), a sample of other local listeners refuses the
    connection, and /v1 still answers. A Claude trial has no route to 21128 at all."""

    @classmethod
    def setUpClass(cls):
        import isolation
        cls.isolation, cls.plans, cls.paths, cls.forwarders = isolation, {}, [], []
        try:
            cls._set_up()
        except BaseException:
            cls.tearDownClass()   # a failed set-up leaves no forwarder or synthetic folder behind
            raise

    @classmethod
    def _set_up(cls):
        isolation = cls.isolation
        for client in ("codex", "claude"):
            isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan(client)
            fixture.mkdir(parents=True)
            for path in (plan["prompt"], plan["settings"]):
                if path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}\n")
            if plan["clone"]:
                plan["clone"].mkdir(parents=True, exist_ok=True)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, client, fixture, clone=plan["clone"],
                                  settings=plan["settings"], prompt=plan["prompt"])
            isolation.prepare_dirs(plan)
            cls.paths += [fixture, work] + ([plan["own_project"]] if plan["own_project"] else [])
            cls.forwarders.append(isolation.NetworkForwarder(plan).start())
            cls.plans[client] = plan
        cls.listeners = [(name, port) for name, port in isolation.LISTENER_SAMPLE if isolation._listening(port)]

    @classmethod
    def tearDownClass(cls):
        import shutil
        cls.records = [f.stop() for f in cls.forwarders]
        for path in cls.paths:
            shutil.rmtree(path, ignore_errors=True)

    def probe(self, client, probes):
        return self.isolation._run_probes(self.plans[client], probes)

    def test_v1_still_answers(self):
        result = self.probe("codex", [("v1", ["http://127.0.0.1:21128/v1/models"])])["v1"]
        self.assertEqual((result["rc"], result["status"], result["denied"]), (0, "200", False), result)

    def test_call_logs_and_health_are_unreachable(self):
        out = self.probe("codex", [("logs", ["http://127.0.0.1:21128/api/usage/call-logs?limit=1"]),
                                   ("logs_offset", ["http://127.0.0.1:21128/api/usage/call-logs?limit=500&offset=0"]),
                                   ("detail", [f"http://127.0.0.1:21128/api/usage/call-logs/{uuid.uuid4()}"]),
                                   ("health", ["http://127.0.0.1:21128/api/health"]),
                                   ("cache", ["http://127.0.0.1:21128/api/cache"])])
        for label, result in out.items():
            self.assertEqual((result["status"], result["denied"]), ("403", True), (label, result))
        log = Path(self.plans["codex"]["private"]) / "net" / "codex" / "access.jsonl"
        decisions = [json.loads(line) for line in log.read_text().splitlines()]
        api = [d for d in decisions if str(d.get("path", "")).startswith("/api/")]
        self.assertTrue(api)
        self.assertTrue(all(d["decision"] == "denied" for d in api), api)

    def test_a_claude_trial_has_no_route_to_the_gateway(self):
        out = self.probe("claude", [("v1", ["--noproxy", "*", "http://127.0.0.1:21128/v1/models"]),
                                    ("logs", ["--noproxy", "*", "http://127.0.0.1:21128/api/usage/call-logs?limit=1"])])
        for label, result in out.items():
            self.assertEqual(result["rc"], 7, (label, result))   # curl: could not connect

    def test_qdrant_and_vllm_forwards_are_path_filtered(self):
        """Round 6b (1): another trial's collection and every unprefixed collection are refused by the filter; the
        trial's own collections reach Qdrant; vLLM answers embeddings and models only."""
        import isolation
        own = self.plans["codex"]["network"]["qdrant_prefix"]
        other = isolation.qdrant_prefix(str(uuid.uuid4()))
        qd, vl = "http://127.0.0.1:21633", "http://127.0.0.1:28231"
        out = self.probe("codex", [("other", [f"{qd}/collections/{other}codebase_x"]),
                                   ("unprefixed", [f"{qd}/collections/socraticode_metadata"]),
                                   ("own", [f"{qd}/collections/{own}codebase_x"]),
                                   ("health", [f"{qd}/healthz"]),
                                   ("chat", ["-X", "POST", "--data", "{}", f"{vl}/v1/chat/completions"]),
                                   ("models", [f"{vl}/v1/models"])])
        for label in ("other", "unprefixed", "chat"):
            self.assertEqual((out[label]["status"], out[label]["denied"]), ("403", True), (label, out[label]))
        for label in ("own", "health", "models"):
            self.assertFalse(out[label]["denied"], (label, out[label]))
            self.assertEqual(out[label]["rc"], 0, (label, out[label]))

    def test_two_trials_never_see_each_others_collections(self):
        """Round 6d (P2), two trials: a collection trial A creates is in A's listing and absent from B's, and B's
        listing names only B's prefix. P1: a foreign collection in an owned route's body, and a grouped query, are
        refused."""
        import isolation
        a, b = self.plans["codex"], self.plans["claude"]
        qd = "http://127.0.0.1:21633"
        name = a["network"]["qdrant_prefix"] + "listprobe"
        create = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT", "-H",
                  "Content-Type: application/json", "--data", json.dumps({"vectors": {"size": 1, "distance": "Cosine"}}),
                  f"{qd}/collections/{name}"]
        try:
            made, _ = isolation.run_wrapped(a, create, timeout=60)
            self.assertEqual(made.stdout.strip(), "200", made.stdout)

            def listing(plan_):
                # Round 6e: asked as SocratiCode's client asks (Node's fetch sends Accept-Encoding by default). Qdrant
                # compresses on request, and the filter must still answer with a listing it has read and filtered.
                out, _ = isolation.run_wrapped(plan_, ["curl", "-s", "-m", "20", "-H", "Accept-Encoding: gzip, deflate",
                                                       f"{qd}/collections"], timeout=60)
                return [c["name"] for c in json.loads(out.stdout)["result"]["collections"]]

            self.assertIn(name, listing(a))
            seen_by_b = listing(b)
            self.assertNotIn(name, seen_by_b)
            self.assertTrue(all(n.startswith(b["network"]["qdrant_prefix"]) for n in seen_by_b), seen_by_b)
            other = isolation.qdrant_prefix(str(uuid.uuid4()))
            out = self.probe("codex", [
                ("lookup", ["-X", "POST", "-H", "Content-Type: application/json", "--data",
                            json.dumps({"query": [0.1], "lookup_from": {"collection": other + "x"}}),
                            f"{qd}/collections/{name}/points/query"]),
                ("groups", ["-X", "POST", "-H", "Content-Type: application/json", "--data",
                            json.dumps({"group_by": "k", "with_lookup": other + "x"}),
                            f"{qd}/collections/{name}/points/query/groups"])])
            for label, result in out.items():
                self.assertEqual((result["status"], result["denied"]), ("403", True), (label, result))
        finally:
            isolation.run_wrapped(a, ["curl", "-s", "-o", "/dev/null", "-X", "DELETE", f"{qd}/collections/{name}"],
                                  timeout=60)
            subprocess.run(["curl", "-s", "-o", "/dev/null", "-X", "DELETE", f"{qd}/collections/{name}"],
                           capture_output=True, timeout=60)

    def test_other_local_listeners_are_unreachable(self):
        self.assertGreaterEqual(len(self.listeners), 3, self.listeners)
        for client in ("codex", "claude"):
            out = self.probe(client, [(f"p{port}", ["--noproxy", "*", f"http://127.0.0.1:{port}/"])
                                      for _, port in self.listeners])
            for label, result in out.items():
                self.assertEqual(result["rc"], 7, (client, label, result))


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class ChannelClosure(unittest.TestCase):
    """The answer-channel closure (CC item task-ns2604-coop-20261006T164313Z, section 3 (c)): one negative test per
    closed channel. Each reads, inside a trial's namespace, a real file the host holds in that channel, and requires
    it gone (ENOENT), or empty for a closed file. The same read outside is the control; a channel with no file on this
    host is skipped. Home writes must not outlive the trial, and a project outside the experiment is read-only."""

    @classmethod
    def setUpClass(cls):
        import isolation
        cls.isolation = isolation
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("claude")
        fixture.mkdir(parents=True)
        for path in (plan["prompt"], plan["settings"]):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n")
        isolation.prepare_dirs(plan)
        cls.plan, cls.paths = plan, [fixture, work, plan["own_project"]]

    @classmethod
    def tearDownClass(cls):
        import shutil
        for path in cls.paths:
            if path:
                shutil.rmtree(path, ignore_errors=True)

    def closed(self, store: Path, depth: int = 4, names=()):
        files = [store / n for n in names if (store / n).is_file()] or \
            [f for f in [self.isolation._first_file(store, depth)] if f]
        if not files:
            self.skipTest(f"nothing in {store} on this host")
        outside = self.isolation.cat_outside(files)
        inside, _ = self.isolation.cat_inside(self.plan, files)
        for path in files:
            self.assertEqual(outside[str(path)], "READABLE", path)
            self.assertEqual(inside[str(path)], "ENOENT", path)

    def test_ai_memory_store_is_closed(self):
        store = HOME_ / ".local" / "share" / "ai-memory"
        self.closed(store, names=("db/memory.sqlite", "db/memory.sqlite-wal"))
        self.closed(store / "wiki", 3)

    def test_agentsview_archive_is_closed(self):
        self.closed(HOME_ / ".agentsview", names=("sessions.db", "sessions.db-wal"))

    def test_codebase_memory_indexes_are_closed(self):
        self.closed(HOME_ / ".cache" / "codebase-memory-mcp", 2)

    def test_jcodemunch_index_is_closed(self):
        self.closed(HOME_ / ".code-index", 3)

    def test_serena_logs_are_closed(self):
        self.closed(HOME_ / ".serena" / "logs", 3)

    def test_claude_plans_tasks_and_paste_cache_are_closed(self):
        found = 0
        for name in ("plans", "tasks", "paste-cache"):
            store = HOME_ / ".claude" / name
            if self.isolation._first_file(store, 4):
                self.closed(store)
                found += 1
        if not found:
            self.skipTest("no Claude plans, tasks or paste cache on this host")

    def test_claude_history_reads_empty(self):
        history = HOME_ / ".claude" / "history.jsonl"
        if not history.is_file() or not history.stat().st_size:
            self.skipTest("no Claude history on this host")
        probes = self.isolation.closed_file_probes(self.plan)
        self.assertEqual(probes["Claude's prompt history"]["inside_bytes"], 0, probes)

    def test_codex_state_is_closed(self):
        self.closed(self.isolation.CODEX_HOME_REAL, names=self.isolation.CODEX_STATE_PROBES)
        self.closed(self.isolation.CODEX_HOME_REAL / "log", 2)

    def test_home_writes_do_not_persist(self):
        marker = f"ut-{uuid.uuid4().hex[:8]}"
        targets = [HOME_ / marker, HOME_ / ".claude" / marker, HOME_ / ".local" / "share" / marker]
        try:
            result, _ = self.isolation.run_wrapped(self.plan, ["sh", "-c", " && ".join(
                f'echo x > "{t}" && cat "{t}" >/dev/null' for t in targets)])
            leaked = [str(t) for t in targets if t.exists()]
        finally:
            for target in targets:
                target.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr)   # writable inside...
        self.assertEqual(leaked, [])                              # ...and gone with the trial

    def test_a_project_outside_the_experiment_is_read_only(self):
        kept = next((self.isolation.CLAUDE_PROJECTS / n for n in self.plan["kept_projects"]
                     if (self.isolation.CLAUDE_PROJECTS / n).is_dir()), None)
        if not kept:
            self.skipTest("no project outside the experiment on this host")
        marker = kept / f"ut-{uuid.uuid4().hex[:8]}"
        try:
            result, _ = self.isolation.run_wrapped(self.plan, ["sh", "-c", f'echo x > "{marker}"'])
            leaked = marker.exists()
        finally:
            marker.unlink(missing_ok=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(leaked)

    def test_g13_requires_every_closure(self):
        """A receipt without the home overlay, a closed store's tmpfs or the private history file fails G13."""
        isolation = self.isolation
        for drop in ("overlay", isolation.HOME / ".agentsview", isolation.CODEX_HOME_REAL,
                     HOME_ / ".local" / "share" / "ai-memory", HOME_ / ".claude" / "history.jsonl"):
            check = G13Check()
            iso, cfg, trial_id, rows = check._rows()
            rec = rows["launched"]["isolation"]
            if drop == "overlay":
                rec["ops"] = [op for op in rec["ops"] if op[0] != "overlay" or op[2] != "~"]
            else:
                rec["ops"] = [op for op in rec["ops"] if op[2] != iso.tilde(drop)]
            check._reseal(iso, rows)
            result = check._check(iso, cfg, trial_id, rows)
            self.assertFalse(result["ok"], drop)


HOME_ = Path.home()


def shutil_which(name):
    import shutil
    return shutil.which(name)


class PilotStage2(unittest.TestCase):
    """Round 6e (GPT read of b2d44f73, P2): stage 2's control flow, through pilot.main itself. pilot.step is replaced by
    a recorder that answers with scripted exit codes, and starting any process fails the test, so no block, collector
    or grader runs. The prompted test's reference sorts before G1's, as a random reference can."""

    GATE, PROBE = "zz-gate", "aa-probe"
    RERUN_G1, RERUN_PROBE = "stage 2 rerun gate0-G1", "stage 2 rerun probe-codex-native"
    CELL_G1, CELL_PROBE = "stage 2 calibration codex-native-gate0", "stage 2 prompted-codex-native"
    COLLECT, CHECK = "stage 2 calibration collect", "stage 2 calibration check"
    END = ["stage 2 collect", "stage 2 gate0"]
    BOTH = ("gate0-G1", "probe-codex-native")

    def _run(self, failed=None, codes=None, ran_before=True, flag=True):
        """(exit code, step labels in order, each step's command) of `pilot.py --from-stage 2 --to-stage 2`.
        failed: the gate-0 checks that failed in an earlier pass (None: no gate0.json yet). codes: a step's exit code
        by label, or its exit codes in order (0 unless named). ran_before: both tests ran once already, and G1's
        attempt was collected."""
        import contextlib
        import io
        from unittest import mock
        import pilot
        codes, steps, cmds = codes or {}, [], {}
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp)
            root = runs / "r1"
            (root / "gateway").mkdir(parents=True)
            cfg = {"trial_root": str(runs / "work"), "binaries": {},
                   "cells": {"codex-native-gate0": {"code": "c0", "repeat": 1, "refs": [self.GATE]},
                             "prompted-codex-native": {"code": "c1", "repeat": 1, "refs": [self.PROBE]}},
                   "tests_by_ref": {
                       self.PROBE: {"stage": 2, "cell": "prompted-codex-native", "probe_key": "probe-codex-native"},
                       self.GATE: {"stage": 2, "cell": "codex-native-gate0", "gate_trial": True, "test_key": "G1|c"}}}
            (root / "run.json").write_text(json.dumps(cfg, sort_keys=True))
            ledger = root / "ledger.jsonl"
            ledger.write_text("")

            def attempt(ref, trial_id):
                with open(ledger, "a") as handle:
                    for row in ({"phase": "launched", "ref": ref, "trial_id": trial_id},
                                {"phase": "exit", "trial_id": trial_id, "reason": "completed"}):
                        handle.write(json.dumps(row) + "\n")

            if ran_before:
                attempt(self.GATE, "gate-1")
                attempt(self.PROBE, "probe-1")
                (root / "gateway" / "gate-1.json").write_text("{}")
            if failed is not None:
                (root / "gate0.json").write_text(json.dumps({"checks": {key: {"pass": key not in failed}
                                                                         for key in self.BOTH}}))

            def step(label, cmd, log):
                steps.append(label)
                cmds[label] = cmd
                code = codes.get(label, 0)
                if isinstance(code, list):
                    code = code.pop(0) if code else 0
                if label in (self.RERUN_G1, self.CELL_G1) and not code:
                    attempt(self.GATE, "gate-2")   # the rows the block writes for the new attempt
                log.append({"step": label})
                return code

            argv = ["--run-id", "r1", "--from-stage", "2", "--to-stage", "2", "--no-reexec"]
            with mock.patch.object(pilot, "RUNS_ROOT", runs), mock.patch.object(pilot, "step", step), \
                    mock.patch.object(pilot.subprocess, "run", side_effect=AssertionError("a process was started")), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = pilot.main(argv + (["--rerun-gate0-failures"] if flag else []))
        return code, steps, cmds

    def test_a_retry_runs_the_calibration_first_and_stops_when_it_fails(self):
        """G1 and a prompted check both failed, and the calibration check fails again: only G1 runs again, its new
        attempt is collected and checked, and the prompted test is not retried."""
        code, steps, cmds = self._run(failed=self.BOTH, codes={self.CHECK: 1})
        self.assertEqual(steps, [self.RERUN_G1, self.COLLECT, self.CHECK])
        self.assertEqual(code, 2)
        self.assertEqual(cmds[self.RERUN_G1][cmds[self.RERUN_G1].index("--ref") + 1], self.GATE)
        self.assertEqual(cmds[self.COLLECT][-1], "gate-2")   # the new attempt; the earlier record is left as it is
        self.assertEqual(cmds[self.CHECK][-3:-2], ["calibration"])

    def test_a_retry_goes_on_only_after_the_calibration_passed(self):
        """The same two failures with the calibration passing: the prompted retry follows the check, then stage 2's
        collection and gate 0."""
        code, steps, _ = self._run(failed=self.BOTH)
        self.assertEqual(steps, [self.RERUN_G1, self.COLLECT, self.CHECK, self.RERUN_PROBE] + self.END)
        self.assertEqual(code, 0)

    def test_a_retry_of_another_check_still_needs_the_calibration(self):
        """Only the prompted check failed. The calibration is checked from its collected record before the retry, with
        nothing launched and a passing record not read again. A check that fails stops before the retry."""
        self.assertEqual(self._run(failed=("probe-codex-native",))[:2],
                         (0, [self.CHECK, self.RERUN_PROBE] + self.END))
        self.assertEqual(self._run(failed=("probe-codex-native",), codes={self.CHECK: 1})[:2],
                         (2, [self.CHECK, self.COLLECT, self.CHECK]))

    def test_a_refused_calibration_rerun_stops_the_retries(self):
        self.assertEqual(self._run(failed=self.BOTH, codes={self.RERUN_G1: 1})[:2], (2, [self.RERUN_G1]))

    def test_a_record_that_does_not_pass_gets_one_fresh_read(self):
        """A calibration record from an earlier run that does not pass is read again once, then checked again, on the
        retry path and on a resume of the initial path. A new attempt's record is read once."""
        code, steps, cmds = self._run(failed=("probe-codex-native",), codes={self.CHECK: [1, 0]})
        self.assertEqual((code, steps), (0, [self.CHECK, self.COLLECT, self.CHECK, self.RERUN_PROBE] + self.END))
        self.assertEqual(cmds[self.COLLECT][-1], "gate-1")
        self.assertEqual(self._run(flag=False, codes={self.CHECK: [1, 0]})[:2],
                         (0, [self.CHECK, self.COLLECT, self.CHECK] + self.END))
        self.assertEqual(self._run(failed=self.BOTH, codes={self.CHECK: [1, 0]})[:2],
                         (2, [self.RERUN_G1, self.COLLECT, self.CHECK]))

    def test_the_initial_path_shares_the_sequence(self):
        """Without an earlier gate0.json (with or without the retry flag), the calibration cell runs first, and no other
        cell runs unless its check passed."""
        for flag in (False, True):
            self.assertEqual(self._run(ran_before=False, flag=flag, codes={self.CHECK: 1})[:2],
                             (2, [self.CELL_G1, self.COLLECT, self.CHECK]))
        self.assertEqual(self._run(ran_before=False, flag=False)[:2],
                         (0, [self.CELL_G1, self.COLLECT, self.CHECK, self.CELL_PROBE] + self.END))


class UnroundedDeadline(unittest.TestCase):
    """GPT micro-check of 1f81d645, P3 (T = 1800): a result at 1799.96 s in a session that ran 1800.02 s is a result
    before T, not a hold, although both one-decimal presentation fields read 1800.0."""

    outcome = {"duration_s": 1800.0, "time_to_result_s": 1800.0, "duration_exact_s": 1800.02,
               "time_to_result_exact_s": 1799.96, "result_at": "2026-10-06T14:00:00.000Z", "result_before_kill": True,
               "kill_reason": "post_result_grace", "rc": -15}

    def test_hold_reads_the_unrounded_offsets(self):
        import launcher
        self.assertFalse(launcher.holds_cell("claude", dict(self.outcome), 1800))

    def test_completion_reads_the_unrounded_offsets(self):
        import launcher
        policy = {"policy": "complete-at-result", "t_seconds": 1800, "grace_s": 30}
        self.assertTrue(launcher.result_before_t(policy, dict(self.outcome)))
        reason, terminated = launcher.trial_reason("claude", policy, dict(self.outcome), True)
        self.assertIsNone(reason)

    def test_rounded_rows_of_earlier_runs_keep_their_reading(self):
        import launcher
        earlier = {k: v for k, v in self.outcome.items() if not k.endswith("_exact_s")}
        self.assertTrue(launcher.holds_cell("claude", earlier, 1800))

    def test_the_grader_reads_the_unrounded_offsets(self):
        import common
        self.assertEqual(common.decision_times(dict(self.outcome)), (1800.02, 1799.96))
        self.assertFalse(common.deadline_without_result(*common.decision_times(dict(self.outcome)), 1800))

    def test_the_graders_completion_check_reads_the_unrounded_arrival(self):
        import grade
        row = {**self.outcome, "completion_policy": "complete-at-result", "censored": False, "reason": None,
               "t_seconds": 1800}
        self.assertIs(grade.effective_exit(row), row, "a result at 1799.96 s was overridden as one at or after T")


if __name__ == "__main__":
    unittest.main()
