1. **Major — receipt 8 should be `advanced`.** [mlflow_bind.py:47]($HOME/code/nas-wt-g2-evaluation-experiments/blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/mlflow_bind.py:47) logs `evaluate_exit_code`, but the readback comparison excludes it and reports the subprocess value instead. A small synthetic check with stored exit code `999` still returned zero mismatches, violating the preregistered “every logged param/metric” criterion. Under the requested all-clauses rule, the original gap’s “project-local code, not an upstream candidate” clause also remains open.

2. **Minor — receipt generation depends on unpublished state.** [build_receipts.py:217]($HOME/code/nas-wt-g2-evaluation-experiments/blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/build_receipts.py:217) reads stdout from the private home cache instead of published `raw/8/work/evaluate.stdout.txt`. This prevents regeneration from the checkout alone. The published file’s hash does match the quoted result.

3. **Minor — misleading first-run chronology field.** [Receipt 3:37]($HOME/code/nas-wt-g2-evaluation-experiments/evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/3-inspect-fixture-authored-frozen.json:37) calls attempt 4’s `07:26:39` event `first_scored_run_timeline`, while line 52 identifies the first scored run as `07:23:39`. Both follow the freeze; rename the field to distinguish retained from first execution.

4. **Minor — overly broad absence claim.** [README.md:30]($HOME/code/nas-wt-g2-evaluation-experiments/evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/README.md:30) asserts that no credentials were read and no existing configuration changed, without retaining a detection method for those blanket claims. The provider-call, River and ordinary MLflow mismatch checks do have explicit detection methods.

5. **Minor — residual host path.** [mlflow-snippet.txt:5]($HOME/code/nas-wt-g2-evaluation-experiments/evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/raw/1/mlflow-snippet.txt:5) retains `sqlite:////tmp/<tmpdir>/mlflow.db`.

Other classifications are supported: **0/1/2/3/7 settled; 4/5 advanced**. Numeric spot-checks agree, including recomputed bootstrap CIs; ARB details hashes agree with the retained hash listing, although the detail files themselves are unpublished. `results.json` matches all eight receipts.

Commit order is preregistration `20fbeb6` → inspect freeze `11d1e6c` → fixture-v2 freeze `2dbd582` → results `40decf7`. Frozen files remain unchanged. No secrets, unsanitized UUIDs, or model-quality/trading overclaims found.

no further issues