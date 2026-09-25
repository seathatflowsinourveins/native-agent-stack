"""Accounting invariants; offline and independent of native authentication."""
from contextlib import closing, contextmanager
import base64
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location("token_manifest",Path(__file__).with_name("token_manifest.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LedgerContract(unittest.TestCase):
    def portable_config(self):
        path=self.root/"config.json"
        m.initialize_config(path,self.root/"state",self.root)
        return m.load_config(path)

    def test_portable_empty_host_needs_no_private_history_or_tokenizer(self):
        from unittest.mock import patch
        config=self.portable_config()
        with patch.object(m,"capture",side_effect=AssertionError("Unselected command executed")), \
             patch.object(m,"native_hook_inventory",side_effect=AssertionError("Unselected history inspected")):
            result=m.refresh(config)
        self.assertEqual(result["issues"],[])
        data=json.loads(Path(config["output_json"]).read_text())
        self.assertEqual(data["native"],[])
        self.assertEqual(data["audit"]["provider_runs"],[])
        self.assertEqual(data["project_counters"],[])
        self.assertEqual(data["hook_inventory"]["runtimes"],[])
        self.assertFalse(data["toon"]["enabled"])
        for row in data["coverage_matrix"]:
            if row["id"] in {"codex","claude-code","context-mode","headroom"}:
                self.assertEqual(row["baseline_status"],"No matched token baseline")
        self.assertNotIn("__DATA__",Path(config["output_html"]).read_text())

    def test_explicit_counter_scopes_reuse_existing_ledger_groups(self):
        from unittest.mock import patch
        config=self.portable_config()
        config.update(rtk="selected-rtk",headroom="selected-headroom",counter_scopes={
            "rtk_global":"Linux / all retained projects","rtk_project":"Linux / project "+str(self.root),
            "headroom":"Linux / native last 30 days"})
        def returned(argv,cwd,root,label):
            return {"argv":argv,"exit_code":0,"stdout_text":'{"summary":{"total_saved":40},"lifetime":{"tokens_saved":0}}',
                    "stderr_text":"","completed_at":m.now()}
        with patch.object(m,"capture",side_effect=returned):
            self.assertEqual(m.refresh(config)["issues"],[])
            self.assertEqual(m.refresh(config)["issues"],[])
        rows=json.loads(Path(config["output_json"]).read_text())["native"]
        self.assertEqual({r["scope"] for r in rows},set(config["counter_scopes"].values()))
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r["snapshot_count"]==2 for r in rows))

    def test_relative_config_paths_resolve_beside_config_not_current_directory(self):
        path=self.root/"config.json"
        path.write_text(json.dumps({"state_dir":"state","project":".","context_roots":[{"name":"Chosen","path":"stats"}],"returned_results_json":"evidence.json","html_template":"local.html.in"}))
        config=m.load_config(path)
        self.assertEqual(config["state_dir"],str(self.root/"state"))
        self.assertEqual(config["context_roots"][0]["path"],str(self.root/"stats"))
        self.assertEqual(config["output_json"],str(self.root/"state/manifest.json"))
        self.assertEqual(config["returned_results_json"],str(self.root/"evidence.json"))
        self.assertEqual(config["html_template"],str(self.root/"local.html.in"))

    def test_symlink_config_paths_resolve_beside_target(self):
        target=self.root/"configuration";target.mkdir()
        path=target/"config.json"
        path.write_text(json.dumps({"state_dir":"state","project":".","context_roots":[{"name":"Chosen","path":"stats"}]}))
        entrypoints=self.root/"entrypoints";entrypoints.mkdir()
        alias=entrypoints/"config.json";alias.symlink_to(path)
        config=m.load_config(alias)
        self.assertEqual(config["project"],str(target))
        self.assertEqual(config["state_dir"],str(target/"state"))
        self.assertEqual(config["context_roots"][0]["path"],str(target/"stats"))
        self.assertEqual(config["output_json"],str(target/"state/manifest.json"))

    def test_initializer_preserves_existing_configuration(self):
        path=self.root/"config.json"
        m.initialize_config(path,self.root/"state",self.root)
        original=path.read_bytes()
        with self.assertRaisesRegex(ValueError,"already exists"):
            m.initialize_config(path,self.root/"other-state",self.root)
        self.assertEqual(path.read_bytes(),original)

    def test_explicit_context_root_reads_stats_without_adjacent_client_history(self):
        from unittest.mock import patch
        config=self.portable_config();stats=self.root/"stats";stats.mkdir()
        (stats/"stats-one.json").write_text(json.dumps({"schemaVersion":1,"tokens_saved_lifetime":512,"tokens_saved":20}))
        config["context_roots"]=[{"name":"Explicit scope","path":str(stats)}]
        with patch.object(m,"native_hook_inventory",side_effect=AssertionError("Unselected history inspected")):
            result=m.refresh(config)
        self.assertEqual(result["issues"],[])
        data=json.loads(Path(config["output_json"]).read_text())
        self.assertEqual(data["native"][0]["latest_success"]["metrics"]["saved"],512)
        self.assertEqual(data["hook_inventory"]["runtimes"],[])

    def test_failed_native_refresh_keeps_raw_error_and_previous_good_value(self):
        from unittest.mock import patch
        config=self.portable_config();config["rtk"]="selected-rtk"
        def capture_good(argv,cwd,root,label):
            return {"argv":argv,"exit_code":0,"stdout_text":'{"summary":{"total_saved":40}}',"stderr_text":"","completed_at":m.now()}
        def capture_bad(argv,cwd,root,label):
            return {"argv":argv,"exit_code":1,"stdout_text":'{"summary":{"total_saved":999}}',"stderr_text":"source failed","completed_at":m.now()}
        with patch.object(m,"capture",side_effect=capture_good):m.refresh(config)
        with patch.object(m,"capture",side_effect=capture_bad):result=m.refresh(config)
        self.assertEqual(len(result["issues"]),2)
        data=json.loads(Path(config["output_json"]).read_text())
        self.assertEqual(len(data["native"]),2)
        for row in data["native"]:
            self.assertFalse(row["latest"]["success"])
            self.assertEqual(row["latest_success"]["metrics"]["saved"],40)
            self.assertEqual(row["snapshot_count"],2)
        self.assertTrue(all(x["stderr_text"]=="source failed" for x in data["commands"]))

    def test_compare_retains_inputs_deduplicates_and_keeps_expansion_negative(self):
        from unittest.mock import patch
        config=self.portable_config();a=self.root/"before.txt";b=self.root/"after.txt"
        a.write_bytes(b"small\r\n");b.write_bytes(b"larger result\r\n")
        def count(config,paths):return [m.artifact(paths[0],2),m.artifact(paths[1],3)]
        with patch.object(m,"count_files",side_effect=count):
            first=m.compare_artifacts(config,"selected",a,b,"same task; retained fixture acceptance")
            second=m.compare_artifacts(config,"selected",a,b,"same task; retained fixture acceptance")
        self.assertEqual(first["comparison_id"],second["comparison_id"])
        self.assertEqual(first["tokens_removed"],-1)
        a.write_text("changed live source")
        self.assertEqual(Path(first["baseline"]["path"]).read_bytes(),b"small\r\n")
        ledger=m.Ledger(Path(config["state_dir"])/"ledger.sqlite3")
        try:self.assertEqual(len(ledger.comparisons()),1)
        finally:ledger.close()

    def test_jcodemunch_counter_snapshots_keep_scope_and_do_not_sum(self):
        from unittest.mock import patch
        commands=[];issues=[]
        config={"jcodemunch_stats_argv":["upstream","stats"],"project":str(self.root)}
        for saved in (100,120):
            result={"exit_code":0,"stdout_text":json.dumps({"total_tokens_saved":saved,"total_tokens_saved_basis":{"generation":2},"lifetime_by_tool":{"get_symbol_source":saved}}),"completed_at":str(saved)}
            with patch.object(m,"capture",return_value=result):
                m.capture_jcodemunch(config,self.db,self.root,commands,issues)
        row=self.db.native_views()[0]
        self.assertEqual(row["latest_success"]["metrics"]["saved"],120)
        self.assertEqual(row["snapshot_count"],2)
        self.assertIn("not measured provider",row["latest_success"]["metrics"]["boundary"])
        self.assertEqual(issues,[])

    def test_jcodemunch_invalid_or_failed_result_is_not_good_counter(self):
        from unittest.mock import patch
        config={"jcodemunch_stats_argv":["upstream","stats"],"project":str(self.root)}
        for raw,code in [("{}",0),("[]",0),('{"total_tokens_saved":true}',0),('{"total_tokens_saved":-1}',0),('{"total_tokens_saved":40}',1)]:
            issues=[]
            with patch.object(m,"capture",return_value={"exit_code":code,"stdout_text":raw,"completed_at":raw}):
                m.capture_jcodemunch(config,self.db,self.root,[],issues)
            self.assertTrue(issues)
        self.assertIsNone(self.db.native_views()[0]["latest_success"])

    def test_narrative_dollar_line_does_not_invent_session_or_lifetime_footer(self):
        line="$1.18 of Opus 4.7 tokens your team didn't burn."
        d=m.dollar_explanation({'runtime':'Unresolved storage root','result':{'content':[{'type':'text','text':line}]}})
        self.assertIsNone(d['current_footer'])
        self.assertEqual(d['current_dollar_line'],line)

    def test_choice_receipt_retains_exact_streams_and_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);stream=root/'stream.txt';stream.write_text('native returned text\n')
            source=root/'source.json'
            source.write_text(json.dumps({'operations':[{'stdout':m.artifact(stream),'stderr':m.artifact(stream)}],'comparisons':[]}))
            result=m.capture_choice_source(source,root,'choice')
            self.assertEqual(result['result']['operations'][0]['stdout_text'],'native returned text\n')
            stream.write_text('changed bytes')
            with self.assertRaisesRegex(ValueError,'Evidence changed'):
                m.capture_choice_source(source,root,'changed')

    def returned_manifest(self,raw=b"complete native result\n"):
        stream=self.root/"upstream.bin";stream.write_bytes(raw)
        payload={"schema_version":1,"captured_at":"2026-09-20T01:00:00Z","scope":"Selected native observations only",
                 "records":[{"id":"codex-run","component_ids":["codex"],"runtime":"Native Codex",
                   "kind":"native_client","command":["codex","exec","--json"],
                   "started_at":"2026-09-19T01:00:00Z","completed_at":"2026-09-19T01:01:00Z",
                   "status":"failed","observation":{"exit_code":1},"boundary":"Functional run; no savings claim",
                   "attachments":[dict(m.artifact(stream),label="Native stdout",path=stream.name)]}]}
        source=self.root/"returned.json";source.write_text(json.dumps(payload))
        return source,payload,stream

    def test_returned_results_preserve_exact_original_bytes_and_source_dates(self):
        raw="Unicode λ result\r\n".encode()
        source,payload,stream=self.returned_manifest(raw)
        result=m.capture_returned_results(source,self.root,"returned-results")
        imported=result["result"]["records"][0];item=imported["attachments"][0]
        stream.write_bytes(b"changed upstream")
        source.write_text('{}')
        self.assertEqual(Path(result["artifact"]["path"]).read_text(),json.dumps(payload))
        self.assertEqual(result["result"]["captured_at"],payload["captured_at"])
        self.assertEqual(imported["started_at"],payload["records"][0]["started_at"])
        self.assertEqual(imported["completed_at"],payload["records"][0]["completed_at"])
        self.assertEqual(imported["status"],"failed")
        self.assertEqual(item["origin"],str(stream))
        self.assertEqual(Path(item["path"]).parent,self.root/"returned-results-artifacts")
        self.assertEqual(Path(item["path"]).read_bytes(),raw)
        self.assertEqual(base64.b64decode(item["content_base64"]),raw)
        self.assertEqual(item["sha256"],m.digest(raw))
        self.assertEqual(item["text"],raw.decode())
        self.assertTrue(result["imported_at"])

    def test_returned_results_binary_download_is_lossless_without_a_fabricated_preview(self):
        raw=b"\x00\xff\xfe\x80\r\n"
        source,payload,_=self.returned_manifest(raw)
        payload["records"][0]["attachments"][0].update(text="untrusted preview",content_base64="not the source",mime_type="application/octet-stream")
        source.write_text(json.dumps(payload))
        result=m.capture_returned_results(source,self.root,"returned-results")
        item=result["result"]["records"][0]["attachments"][0]
        self.assertNotIn("text",item)
        self.assertEqual(base64.b64decode(item["content_base64"]),raw)
        self.assertEqual(item["bytes"],len(raw))

    def test_returned_results_reject_missing_changed_and_oversized_sources(self):
        for defect in ("missing","changed","oversized_actual","oversized_declared"):
            with self.subTest(defect=defect):
                source,payload,stream=self.returned_manifest()
                run=self.root/defect;run.mkdir()
                if defect=="missing":stream.unlink()
                elif defect=="changed":stream.write_bytes(b"wrong")
                elif defect=="oversized_actual":stream.write_bytes(b"x"*(m.RETURNED_RESULTS_FILE_LIMIT+1))
                else:
                    payload["records"][0]["attachments"][0]["bytes"]=m.RETURNED_RESULTS_FILE_LIMIT+1
                    source.write_text(json.dumps(payload))
                original=source.read_bytes()
                with self.assertRaises(ValueError):
                    m.capture_returned_results(source,run,"returned-results")
                self.assertEqual((run/"returned-results.json").read_bytes(),original)
                self.assertFalse((run/"returned-results-artifacts").exists())

    def test_returned_results_validate_schema_and_duplicate_identities(self):
        source,valid,_=self.returned_manifest()
        cases=[]
        for key,value in (("schema_version",True),("captured_at",None),("scope",[]),("records",{})):
            payload=copy.deepcopy(valid);payload[key]=value;cases.append(payload)
        for key,value in (("component_ids","codex"),("command",{"tool":"ctx_stats"}),
                          ("started_at",False),("status",True),("observation",[]),("attachments",{})):
            payload=copy.deepcopy(valid);payload["records"][0][key]=value;cases.append(payload)
        payload=copy.deepcopy(valid);payload["records"].append(copy.deepcopy(payload["records"][0]));cases.append(payload)
        payload=copy.deepcopy(valid);attachments=payload["records"][0]["attachments"];attachments.append(copy.deepcopy(attachments[0]));cases.append(payload)
        for key,value in (("bytes",True),("sha256","bad"),("mime_type",{})):
            payload=copy.deepcopy(valid);payload["records"][0]["attachments"][0][key]=value;cases.append(payload)
        for number,payload in enumerate(cases):
            with self.subTest(number=number):
                source.write_text(json.dumps(payload));run=self.root/str(number);run.mkdir()
                with self.assertRaisesRegex(ValueError,"Returned results:"):
                    m.capture_returned_results(source,run,"returned-results")
                self.assertFalse((run/"returned-results-artifacts").exists())

    def test_returned_results_enforce_total_limit_and_preserve_malformed_json(self):
        from unittest.mock import patch
        source,payload,stream=self.returned_manifest(b"1234")
        second=copy.deepcopy(payload["records"][0]["attachments"][0]);second["label"]="Other selected result"
        payload["records"][0]["attachments"].append(second);source.write_text(json.dumps(payload))
        with patch.object(m,"RETURNED_RESULTS_TOTAL_LIMIT",7):
            with self.assertRaisesRegex(ValueError,"16 MiB"):
                m.capture_returned_results(source,self.root,"over-total")
        self.assertFalse((self.root/"returned-results-artifacts").exists())
        source.write_bytes(b'{"records":not json}')
        with self.assertRaises(ValueError):
            m.capture_returned_results(source,self.root,"malformed")
        self.assertEqual((self.root/"malformed.json").read_bytes(),source.read_bytes())

    def test_returned_results_import_has_no_execution_and_no_previous_success_fallback(self):
        from unittest.mock import patch
        source,payload,stream=self.returned_manifest(b'</script><script>alert("untrusted")</script>')
        payload["records"][0]["command"]={"tool":"ctx_stats","arguments":{"value":"$(touch unrequested)"}}
        payload["records"][0]["unselected_path"]="/file/which/must/not/be/read"
        source.write_text(json.dumps(payload))
        config=self.portable_config();config["returned_results_json"]=str(source)
        with patch.object(m,"capture",side_effect=AssertionError("Native command executed")), \
             patch.object(m.subprocess,"run",side_effect=AssertionError("Subprocess executed")):
            result=m.refresh(config)
            self.assertEqual(result["issues"],[])
            data=json.loads(Path(config["output_json"]).read_text())
            item=data["additional_evidence"]["returned_results"]["result"]["records"][0]["attachments"][0]
            rendered=Path(config["output_html"]).read_text()
            self.assertNotIn('</script><script>alert("untrusted")</script>',rendered)
            self.assertEqual(item["text"],stream.read_text())
            self.assertEqual(base64.b64decode(item["content_base64"]),stream.read_bytes())
            stream.write_bytes(b"altered")
            failed=m.refresh(config)
        self.assertTrue(any("returned-results: Returned results: evidence changed" in issue for issue in failed["issues"]))
        data=json.loads(Path(config["output_json"]).read_text())
        self.assertNotIn("returned_results",data["additional_evidence"])
        self.assertEqual((Path(failed["capture"])/"returned-results.json").read_bytes(),source.read_bytes())

    def test_returned_results_accept_empty_selection_and_argv_object(self):
        source,payload,_=self.returned_manifest()
        payload["records"][0]["command"]={"argv":["curl","--version"]}
        payload["records"][0].update(started_at=None,completed_at=None,attachments=[])
        source.write_text(json.dumps(payload))
        result=m.capture_returned_results(source,self.root,"empty-attachments")
        self.assertEqual(result["result"]["records"][0]["attachments"],[])
        self.assertFalse((self.root/"returned-results-artifacts").exists())
        payload["records"]=[];source.write_text(json.dumps(payload))
        self.assertEqual(m.capture_returned_results(source,self.root,"empty-records")["result"]["records"],[])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.db=m.Ledger(self.root/"ledger.sqlite3")
        self.addCleanup(self.db.close)
    def snapshot(self, saved, scope="linux/global", success=True, stamp="2026-09-20T01:00:00Z"):
        return self.db.snapshot("rtk",scope,{"saved":saved},success,stamp,{"stdout":"native output","argv":["rtk","gain"]})
    def test_cumulative_snapshots_are_not_summed(self):
        self.snapshot(100)
        self.snapshot(120,stamp="2026-09-20T02:00:00Z")
        row=self.db.native_views()[0]
        self.assertEqual(row["latest_success"]["metrics"]["saved"],120)
        self.assertEqual(row["snapshot_count"],2)
    def test_failed_refresh_preserves_last_good_and_marks_failure(self):
        self.snapshot(100)
        self.snapshot(None,success=False,stamp="2026-09-20T02:00:00Z")
        row=self.db.native_views()[0]
        self.assertFalse(row["latest"]["success"])
        self.assertEqual(row["latest_success"]["metrics"]["saved"],100)
    def test_counter_decrease_is_visible_not_added_as_new_savings(self):
        self.snapshot(100)
        self.snapshot(20,stamp="2026-09-20T02:00:00Z")
        row=self.db.native_views()[0]
        self.assertTrue(row["counter_decreased"])
        self.assertEqual(row["latest_success"]["metrics"]["saved"],20)
    def test_project_and_global_scopes_stay_separate(self):
        self.snapshot(100)
        self.snapshot(20,scope="linux/project/example")
        self.assertEqual(len(self.db.native_views()),2)
    def test_identical_artifact_pair_is_not_counted_twice(self):
        a=self.root/"a.txt";b=self.root/"b.txt"
        a.write_text("long baseline");b.write_text("short")
        args=("toon",m.artifact(a,11),m.artifact(b,3),"o200k_base","same selected records")
        self.db.comparison(*args)
        self.db.comparison(*args)
        rows=self.db.comparisons()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["tokens_removed"],8)
    def test_changed_evidence_rejected(self):
        a=self.root/"a.txt";b=self.root/"b.txt"
        a.write_text("before");b.write_text("after")
        before=m.artifact(a,3);after=m.artifact(b,2)
        a.write_text("tampered")
        with self.assertRaises(ValueError):
            self.db.comparison("toon",before,after,"o200k_base","fixture")
        self.assertEqual(self.db.comparisons(),[])
    def test_expansion_stays_negative(self):
        a=self.root/"a.txt";b=self.root/"b.txt"
        a.write_text("small");b.write_text("large")
        self.db.comparison("toon",m.artifact(a,2),m.artifact(b,7),"o200k_base","fixture")
        self.assertEqual(self.db.comparisons()[0]["tokens_removed"],-5)
    def test_unmeasured_token_count_rejected(self):
        a=self.root/"a.txt";b=self.root/"b.txt"
        a.write_text("before");b.write_text("after")
        with self.assertRaises(ValueError):
            self.db.comparison("toon",m.artifact(a,None),m.artifact(b,2),"o200k_base","fixture")
    def test_context_missing_counter_marks_failed_and_preserves_prior(self):
        source=self.root/"stats-1.json"
        source.write_text(json.dumps({"schemaVersion":2,"tokens_saved_lifetime":256,"tokens_saved":4}))
        entry={"name":"runtime","path":str(self.root)}
        m.capture_context(entry,self.db,self.root,[])
        source.write_text(json.dumps({"schemaVersion":2}))
        issues=[]
        m.capture_context(entry,self.db,self.root,issues)
        row=self.db.native_views()[0]
        self.assertFalse(row["latest"]["success"])
        self.assertEqual(row["latest_success"]["metrics"]["saved"],256)
        self.assertEqual(row["latest_success"]["evidence"]["schema"],2)
        self.assertTrue(issues)
    def test_context_malformed_json_is_failed(self):
        (self.root/"stats-1.json").write_text("{broken")
        issues=[]
        m.capture_context({"name":"runtime","path":str(self.root)},self.db,self.root,issues)
        self.assertFalse(self.db.native_views()[0]["latest"]["success"])
        self.assertIsNone(self.db.native_views()[0]["latest_success"])
    def test_live_context_change_does_not_change_captured_evidence(self):
        from unittest.mock import patch
        source=self.root/"stats-1.json"
        original=json.dumps({"schemaVersion":2,"tokens_saved_lifetime":256}).encode()
        source.write_bytes(original)
        read=Path.read_bytes
        def changing(path):
            raw=read(path)
            if path==source:
                source.write_text(json.dumps({"schemaVersion":2,"tokens_saved_lifetime":512}))
            return raw
        with patch.object(Path,"read_bytes",changing):
            m.capture_context({"name":"runtime","path":str(self.root)},self.db,self.root,[])
        row=self.db.native_views()[0]["latest_success"]
        self.assertEqual(row["metrics"]["saved"],256)
        self.assertEqual(row["evidence"]["source"]["sha256"],m.digest(original))
        self.assertEqual(Path(row["evidence"]["captured_source"]["path"]).read_bytes(),original)
    def test_context_nonobject_json_records_failure(self):
        (self.root/"stats-1.json").write_text("[]")
        issues=[]
        m.capture_context({"name":"runtime","path":str(self.root)},self.db,self.root,issues)
        self.assertFalse(self.db.native_views()[0]["latest"]["success"])
        self.assertTrue(issues)
    def test_native_event_archive_deduplicates_without_combining_scopes(self):
        self.db.event("rtk","native","2026-01-01",20,["db",1,"time"],{})
        self.db.event("rtk","native","2026-01-01",20,["db",1,"time"],{})
        self.db.event("rtk","another-runtime","2026-01-01",3,["db",1,"time"],{})
        totals=self.db.event_totals()
        self.assertEqual(sum(x["events"] for x in totals),2)
        self.assertEqual({x["scope"]:x["estimated_saved"] for x in totals},{"native":20,"another-runtime":3})
    def test_installed_symlink_resolves_template_beside_source(self):
        from unittest.mock import patch
        alias=self.root/"ecosystem-token-report"
        alias.symlink_to(Path(m.__file__).resolve())
        with patch.object(m,"__file__",str(alias)):
            self.assertEqual(m.template_path(),Path(spec.origin).resolve().with_name("token_manifest.html.in"))
            self.assertTrue(m.template_path().is_file())
    def test_every_html_entrypoint_contains_parseable_rendered_data(self):
        from unittest.mock import patch
        template=self.root/"template.html.in"
        template.write_text('<script id="data" type="application/json">__DATA__</script>')
        config={"output_json":str(self.root/"report.json"),"output_html":str(self.root/"report.html"),"output_aliases":[str(self.root/"tools/token_manifest.html")]}
        with patch.object(m,"template_path",return_value=template):
            m.render_reports(config,{"verified":True})
        for path in [config["output_html"]]+config["output_aliases"]:
            content=Path(path).read_text()
            self.assertNotIn("__DATA__",content)
            self.assertEqual(json.loads(content.split('>')[1].split('</script')[0]),{"verified":True})
        self.assertIn("__DATA__",template.read_text())
    def test_selected_template_uses_reporter_sidecar_only_when_requested(self):
        from unittest.mock import patch
        template=self.root/"selected.html.in"
        template.write_text('<script id="data" type="application/json">__DATA__</script><script>__RETURNED_RESULTS_JS__</script>')
        sidecar=self.root/"returned_results.js";sidecar.write_text('window.returnedResultsLoaded = true;')
        config={"html_template":str(template),"output_json":str(self.root/"report.json"),"output_html":str(self.root/"report.html")}
        with patch.object(m,"__file__",str(self.root/"token_manifest.py")), \
             patch.object(m,"template_path",side_effect=AssertionError("Configured template ignored")):
            m.render_reports(config,{"text":"</script><script>bad()</script>"})
            rendered=Path(config["output_html"]).read_text()
            self.assertIn(sidecar.read_text(),rendered)
            self.assertNotIn("__RETURNED_RESULTS_JS__",rendered)
            self.assertNotIn("</script><script>bad()",rendered)
            with self.assertRaisesRegex(ValueError,"script source"):
                m.render_reports(dict(config,output_aliases=[str(sidecar)]),{})
        self.assertIn("__RETURNED_RESULTS_JS__",template.read_text())
        self.assertEqual(sidecar.read_text(),'window.returnedResultsLoaded = true;')
    def test_render_targets_cannot_overwrite_template_or_json(self):
        from unittest.mock import patch
        template=self.root/"template.html.in";template.write_text('__DATA__')
        config={"output_json":str(self.root/"report.json"),"output_html":str(self.root/"report.html")}
        for alias in [template,Path(config["output_json"])]:
            with patch.object(m,"template_path",return_value=template):
                with self.assertRaises(ValueError):
                    m.render_reports(dict(config,output_aliases=[str(alias)]),{})
        self.assertEqual(template.read_text(),'__DATA__')
        self.assertFalse(Path(config["output_json"]).exists())
    def test_safe_json_embedding(self):
        embedded=m.json_script({"text":"</script><script>alert(1)</script>"})
        self.assertNotIn("</script>",embedded)
        self.assertEqual(json.loads(embedded)["text"],"</script><script>alert(1)</script>")

    def test_money_footer_is_scoped_and_preserves_upstream_formula(self):
        d=m.dollar_explanation({"runtime":"Test client","result":{"content":[{"type":"text","text":"$0.65 this session  ·  $0.85 lifetime"}]}})
        self.assertEqual(d["current_footer"],"$0.65 this session  ·  $0.85 lifetime")
        self.assertIn("cache bytes saved",d["session_formula"])
        self.assertIn("round(",d["session_formula"])
        self.assertIn("+ current session",d["footer_lifetime_formula"])
        self.assertIn("excludes",d["persisted_lifetime_formula"])
        self.assertIn("unknown",d["quoted_source"])

    def test_unmatched_catalog_repository_is_not_marked_adopted_or_zero_saved(self):
        matrix=[dict(id="x",repository="https://github.com/org/x",adoption_status="Functional",native_lifetime_kind="no counter",baseline_status="No matched baseline")]
        catalog={"records":[{"repository":"https://github.com/ORG/X.git/","record_types":["component_record"]},{"repository":"https://github.com/org/y","record_types":["catalog_card","public_star"]}]}
        rows=m.repository_coverage(catalog,matrix)
        self.assertEqual(rows[0]["component_id"],"x")
        self.assertEqual(rows[1]["classification"],"Other catalog card")
        self.assertIsNone(rows[1]["exact_lifetime_provider_saved"])
        self.assertIsNone(rows[1]["component_id"])

    def test_gap_acceptance_and_fresh_failure_remain_distinct(self):
        stack={"components":[{"id":"playwright-cli","repository":"https://github.com/microsoft/playwright-cli"}]}
        audit={"coverage":[{"id":"playwright-cli","status":"Host blocked"}],"operations":[]}
        gap={"components":[{"id":"playwright-cli","status":"Functional","scope":"Prior HTTP fixture"}],"operations":[{"id":"prior","components":["playwright-cli"],"passed":True}]}
        fresh={"components":[{"id":"playwright-cli","status":"Failed","scope":"Fresh timeout"}],"operations":[{"id":"fresh","components":["playwright-cli"],"passed":False}]}
        row=m.coverage_matrix(stack,audit,gap,fresh,[])[0]
        self.assertEqual(row["adoption_status"],"Functional")
        self.assertEqual(row["latest_pass"]["status"],"Failed")
        self.assertEqual((row["passed_operations"],row["failed_operations"]),(1,1))
        self.assertIsNone(row["exact_lifetime_provider_saved"])

    def test_release_pin_and_renamed_short_alias_match_canonical_repository(self):
        fields=dict(adoption_status="Functional",native_lifetime_kind="retained estimate",baseline_status="Exact pair")
        matrix=[dict(fields,id="rtk",repository="https://github.com/rtk-ai/rtk/releases/tag/v0.49.0"),dict(fields,id="headroom",repository="https://github.com/chopratejas/headroom")]
        catalog={"records":[{"repository":"https://github.com/rtk-ai/rtk"},{"repository":"https://github.com/headroomlabs-ai/headroom","aliases":["chopratejas/headroom"]}]}
        self.assertEqual([r["component_id"] for r in m.repository_coverage(catalog,matrix)],["rtk","headroom"])

    def test_usage_only_component_does_not_get_savings_counter(self):
        stack={"components":[{"id":"ccusage","repository":"https://github.com/ryoppippi/ccusage"}]}
        row=m.coverage_matrix(stack,{},None,None,[])[0]
        self.assertEqual(row["native_lifetime_kind"],"usage only")
        self.assertEqual(row["native_command"],"")
        self.assertIsNone(row["exact_lifetime_provider_saved"])

    def test_jcodemunch_component_alias_preserves_native_ledger_identity(self):
        stack={"components":[{"id":"jcodemunch-mcp","repository":"https://github.com/jgravelle/jcodemunch-mcp"}]}
        comparisons=[{"id":"retained-pair","tool":"jcodemunch"}]
        row=m.coverage_matrix(stack,m.empty_audit(),None,None,comparisons)[0]
        self.assertEqual(row["native_lifetime_kind"],"cumulative estimate")
        self.assertIn("get_session_stats",row["native_command"])
        self.assertEqual(row["baseline_status"],"Exact retained-output pair")
        self.assertEqual(row["comparison_ids"],["retained-pair"])
        self.assertEqual(comparisons[0]["tool"],"jcodemunch")

    def test_jcodemunch_component_attaches_its_existing_native_counter(self):
        from unittest.mock import patch
        config=self.portable_config()
        stack=self.root/"stack.json"
        stack.write_text(json.dumps({"components":[{"id":"jcodemunch-mcp","repository":"https://github.com/jgravelle/jcodemunch-mcp"}]}))
        config["stack_manifest"]=str(stack)
        config["jcodemunch_stats_argv"]=["selected-upstream","stats"]
        result={"exit_code":0,"stdout_text":'{"total_tokens_saved":120}',"completed_at":m.now()}
        with patch.object(m,"capture",return_value=result):m.refresh(config)
        data=json.loads(Path(config["output_json"]).read_text())
        reports=data["coverage_matrix"][0]["native_reports"]
        self.assertEqual(len(reports),1)
        self.assertEqual(reports[0]["tool"],"jcodemunch")
        self.assertEqual(reports[0]["latest_success"]["metrics"]["saved"],120)
        self.assertEqual(len(data["native"]),1)

    def test_disabled_or_nonexecuting_rtk_hook_is_not_enabled(self):
        config={"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"/bin/rtk hook claude"}]}]}}
        self.assertTrue(m.claude_rtk_hook_enabled(config))
        config["disableAllHooks"]=True
        self.assertFalse(m.claude_rtk_hook_enabled(config))
        config["disableAllHooks"]=False
        config["hooks"]["PreToolUse"][0]["matcher"]="Read"
        self.assertFalse(m.claude_rtk_hook_enabled(config))
        self.assertFalse(m.claude_rtk_hook_enabled({"description":"rtk hook claude"}))

    def test_imported_study_preserves_source_bytes_after_source_changes(self):
        source=self.root/"study.json";source.write_text('{"comparisons":[]}')
        run=self.root/"run";run.mkdir()
        receipt=m.capture_json_source(source,run,"copy")
        source.write_text('{"comparisons":["changed"]}')
        copied=Path(receipt["artifact"]["path"])
        self.assertEqual(json.loads(copied.read_text()),{"comparisons":[]})
        self.assertEqual(receipt["artifact"]["sha256"],m.artifact(copied)["sha256"])

    def test_enabled_hooks_do_not_imply_observed_hooks_and_private_values_not_exported(self):
        home=self.root/".codex";sessions=home/"context-mode/sessions";sessions.mkdir(parents=True)
        (home/"config.toml").write_text('[features]\nhooks=true\nplugin_hooks=true\n[plugins."context-mode@context-mode"]\nenabled=true\n[private]\nsecret="do-not-export"\n')
        hooks=home/"plugins/cache/context-mode/context-mode/1.0.169/.codex-plugin/hooks.json"
        hooks.parent.mkdir(parents=True);hooks.write_text(json.dumps({"hooks":{"PreCompact":[],"PostToolUse":[]}}))
        with closing(sqlite3.connect(sessions/"session.db")) as db, db:
            db.execute("CREATE TABLE session_events(id INTEGER,session_id TEXT,source_hook TEXT,created_at TEXT,project_dir TEXT,data TEXT)")
            db.execute("INSERT INTO session_events VALUES(1,'test','PostToolUse','2026-09-20','/fixture','private prompt content')")
        run=self.root/"observed";run.mkdir();issues=[]
        config={"context_roots":[{"name":"Test","path":str(sessions)}]}
        result=m.native_hook_inventory(config,run,issues,self.db)
        m.native_hook_inventory(config,run,issues,self.db)
        row=result["runtimes"][0]
        self.assertTrue(row["context_mode_enabled"])
        self.assertEqual(row["retained_events"],1)
        self.assertEqual(row["unobserved_hooks"],["PreCompact"])
        self.assertFalse(row["rtk_automatic_configured"])
        self.assertNotIn("do-not-export",json.dumps(result))
        self.assertNotIn("private prompt content",json.dumps(result))
        self.assertNotIn("private prompt content",str(self.db.db.execute("SELECT payload FROM native_events").fetchall()))
        self.assertEqual(self.db.event_totals()[0]["events"],1)
        self.assertEqual(self.db.event_totals()[0]["estimated_saved"],256)
        self.assertEqual(issues,[])

    def test_codex_hook_engine_follows_the_stable_hooks_flag_not_removed_plugin_hooks(self):
        cases=[({},True),({"features":{}},True),({"features":{"hooks":True}},True),
               ({"features":{"hooks":False,"plugin_hooks":True}},False),
               ({"features":{"hooks":True,"plugin_hooks":False}},True),
               ({"features":{"plugin_hooks":True}},True),({"features":{"codex_hooks":False}},False),
               ({"features":{"hooks":True,"codex_hooks":False}},True),
               ({"features":{"hooks":"true"}},False),({"features":"hooks"},True)]
        for config,expected in cases:
            with self.subTest(config=config):
                self.assertIs(m.codex_hooks_enabled(config),expected)

    @contextmanager
    def assert_connections_closed(self):
        from unittest.mock import patch
        connect=sqlite3.connect;connections=[]
        def tracked(*args,**kwargs):
            db=connect(*args,**kwargs)
            connections.append(db)
            return db
        try:
            with patch.object(m.sqlite3,"connect",side_effect=tracked):
                yield
            self.assertTrue(connections)
            for db in connections:
                with self.assertRaisesRegex(sqlite3.ProgrammingError,"closed database"):
                    db.execute("SELECT 1")
        finally:
            for db in connections:
                db.close()

    def test_ledger_initialization_errors_close_connection(self):
        from unittest.mock import patch
        with self.assert_connections_closed():
            with patch.object(m.os,"chmod",side_effect=OSError("permission fixture")):
                with self.assertRaisesRegex(OSError,"permission fixture"):
                    m.Ledger(self.root/"permission.sqlite3")
        malformed=self.root/"malformed.sqlite3";malformed.write_bytes(b"not a sqlite database")
        with self.assert_connections_closed():
            with self.assertRaises(sqlite3.DatabaseError):
                m.Ledger(malformed)

    def test_native_source_connections_close_after_success_and_query_errors(self):
        for reader in ("archive","projects","hooks"):
            for valid in (True,False):
                with self.subTest(reader=reader,valid=valid):
                    home=self.root/(reader+str(valid));sessions=home/"context-mode/sessions"
                    sessions.mkdir(parents=True)
                    (home/"config.toml").write_text("")
                    hooks=home/"plugins/cache/context-mode/context-mode/fixture/.codex-plugin/hooks.json"
                    hooks.parent.mkdir(parents=True);hooks.write_text('{"hooks":{}}')
                    source=sessions/"source.db"
                    with closing(sqlite3.connect(source)) as db, db:
                        if valid:
                            db.execute("CREATE TABLE commands(id INTEGER,timestamp TEXT,input_tokens INTEGER,output_tokens INTEGER,saved_tokens INTEGER,project_path TEXT)")
                            db.execute("CREATE TABLE session_events(id INTEGER,session_id TEXT,source_hook TEXT,created_at TEXT,project_dir TEXT)")
                    issues=[]
                    config={"rtk_database":str(source),"context_roots":[{"name":"Fixture","path":str(sessions)}]}
                    with self.assert_connections_closed():
                        if reader=="archive":
                            m.archive_native_events(config,self.db,issues)
                        elif reader=="projects":
                            m.retained_projects(config,home,[],issues)
                        else:
                            m.native_hook_inventory(config,home,issues,self.db)
                    self.assertEqual(bool(issues),not valid)

    def test_report_operations_close_ledger_after_success_and_errors(self):
        from unittest.mock import patch
        config=self.portable_config();before=self.root/"before.txt";after=self.root/"after.txt"
        before.write_text("before");after.write_text("after")
        counts=[m.artifact(before,2),m.artifact(after,1)]
        for fails in (False,True):
            with self.subTest(operation="compare",fails=fails):
                with self.assert_connections_closed(), patch.object(m,"count_files",return_value=counts):
                    if fails:
                        with patch.object(m.Ledger,"comparison",side_effect=ValueError("comparison fixture")):
                            with self.assertRaisesRegex(ValueError,"comparison fixture"):
                                m.compare_artifacts(config,"fixture",before,after,"fixture")
                    else:
                        m.compare_artifacts(config,"fixture",before,after,"fixture")
            with self.subTest(operation="refresh",fails=fails):
                with self.assert_connections_closed():
                    if fails:
                        with patch.object(m,"render_reports",side_effect=ValueError("render fixture")):
                            with self.assertRaisesRegex(ValueError,"render fixture"):
                                m.refresh(config)
                    else:
                        m.refresh(config)

if __name__=="__main__":
    unittest.main()
