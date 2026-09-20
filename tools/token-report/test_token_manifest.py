"""Accounting invariants; offline and independent of native authentication."""
import importlib.util
import json
from pathlib import Path
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

    def test_relative_config_paths_resolve_beside_config_not_current_directory(self):
        path=self.root/"config.json"
        path.write_text(json.dumps({"state_dir":"state","project":".","context_roots":[{"name":"Chosen","path":"stats"}]}))
        config=m.load_config(path)
        self.assertEqual(config["state_dir"],str(self.root/"state"))
        self.assertEqual(config["context_roots"][0]["path"],str(self.root/"stats"))
        self.assertEqual(config["output_json"],str(self.root/"state/manifest.json"))

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

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
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
        import sqlite3
        home=self.root/".codex";sessions=home/"context-mode/sessions";sessions.mkdir(parents=True)
        (home/"config.toml").write_text('[features]\nhooks=true\nplugin_hooks=true\n[plugins."context-mode@context-mode"]\nenabled=true\n[private]\nsecret="do-not-export"\n')
        hooks=home/"plugins/cache/context-mode/context-mode/1.0.169/.codex-plugin/hooks.json"
        hooks.parent.mkdir(parents=True);hooks.write_text(json.dumps({"hooks":{"PreCompact":[],"PostToolUse":[]}}))
        with sqlite3.connect(sessions/"session.db") as db:
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

if __name__=="__main__":
    unittest.main()
