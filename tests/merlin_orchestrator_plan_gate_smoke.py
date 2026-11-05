#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    tmp=Path(td)
    fake=tmp/"fake_runtime.py"
    fake.write_text("#!/usr/bin/env python3\\nimport sys,json\\nfor line in sys.stdin:\\n req=json.loads(line)\\n print(json.dumps({'id':req['id'],'ok':True,'result':req['task']}),flush=True)\\n")
    fake.chmod(0o755)
    task=[sys.executable,str(root/"python/orchestrator.py"),"--runtime",str(fake),"--task","create a bounded test artifact"]
    denied=subprocess.run(task,capture_output=True,text=True)
    assert denied.returncode != 0 and "--plan is required" in denied.stderr
    plan={
      "plan_version":1,"task_id":"dispatch-gate-smoke","objective":"Test plan enforcement",
      "domain_scope":{"primary_domain":"computer-information","subsystems":["orchestration"],"secondary_domains":[],"excluded_domains":[],"scope_rationale":"Test"},
      "requirements":[{"id":"R1","statement":"A task must have a valid plan","acceptance":"Dispatch rejects missing plans and accepts this plan."}],
      "assumptions":[],"reasoning_plan":{"inductive":"Not applicable for this deterministic contract test.","deductive":"A missing plan fails the gate.","abductive":"No competing explanation is needed.","disconfirmation":"A planless task succeeding would fail the test."},
      "design":{"method":"Deterministic subprocess contract test","alternatives":["Static inspection"],"limitations":"Tests Python dispatch only.","bias_review":{"possible_biases":[],"possible_fallacies":[],"checks":["repeat in CI"]}},
      "resource_budget":{"max_runtime_seconds":30,"max_memory_mb":128,"max_disk_bytes":1048576,"max_input_bytes":1048576},
      "verification":{"tests":["planless rejection","planned dispatch"],"independent_check":"Avrea CI runner."},
      "rollback":"Temporary directory is removed after test."
    }
    plan_path=tmp/"plan.json"; plan_path.write_text(json.dumps(plan))
    accepted=subprocess.run(task+["--plan",str(plan_path)],capture_output=True,text=True,timeout=20)
    assert accepted.returncode==0, accepted.stderr
    response=json.loads(accepted.stdout)
    assert response["ok"] is True and "MANDATORY MERLIN ENGINEERING PLAN" in response["result"]
print("Merlin orchestrator mandatory engineering-plan gate smoke passed.")
