#!/usr/bin/env bash
# Independent exact-source integration verification. Runs no model, public fetch,
# external browser, host installation, merge or deployment.
set -euo pipefail
: "${MERLIN_EXPECTED_SHA:?exact source commit required}"
: "${MERLIN_CI_EVIDENCE_DIR:?output location required}"
test "$(git rev-parse HEAD)" = "$MERLIN_EXPECTED_SHA"
mkdir -p "$MERLIN_CI_EVIDENCE_DIR"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/python:$PWD/portable"
printf '%s\n' "$MERLIN_EXPECTED_SHA" > "$MERLIN_CI_EVIDENCE_DIR/source-commit.txt"
python3 -B - <<'PY' > "$MERLIN_CI_EVIDENCE_DIR/python-ast-check.json"
import ast, json, pathlib
locations = ["python/merlin", "python/dot_ai_os", "portable/merlin_studio", "scripts"]
checked = 0
for base in locations:
    for path in pathlib.Path(base).rglob("*.py"):
        if "__pycache__" in path.parts: continue
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        checked += 1
assert checked > 30, checked
print(json.dumps({"python_sources_parsed":checked,"source_kind":"AST-only; not execution",
                  "production_qualified":False}))
PY
run_suite () {
  local pattern="$1"
  local folder="$2"
  local label="$3"
  echo "RUN $label $folder/$pattern"
  python3 -B -m unittest discover -s "$folder" -p "$pattern" -v > "$MERLIN_CI_EVIDENCE_DIR/$label.log" 2>&1 || {
    tail -n 90 "$MERLIN_CI_EVIDENCE_DIR/$label.log"
    exit 1
  }
  tail -n 5 "$MERLIN_CI_EVIDENCE_DIR/$label.log"
}
run_suite test_merlin_release_gate.py tests release
run_suite test_merlin_studio_output_budget.py tests studio_budget
run_suite test_merlin_studio_tool_compatibility.py tests studio_tools
run_suite test_merlin_bundled_model_launcher.py tests bundled_model
run_suite test_merlin_offline_profile.py tests offline_profile
run_suite test_merlin_studio_browser_bridge.py tests studio_browser_bridge
run_suite test_merlin_public_primary_sources.py tests primary_source_receipts
run_suite test_public_browser.py tests browser_contracts
run_suite test_browser_research_handoff.py tests research_handoff
run_suite test_browser_service_lifecycle.py tests browser_lifecycle
run_suite test_browser_service_lifecycle_controls.py tests lifecycle_controls
run_suite test_studio.py portable/merlin_studio/tests studio_integration
run_suite test_model_deadline.py portable/tests model_deadline
run_suite test_public_web.py portable/tests public_https
run_suite test_airllm_openbot_integration.py tests optional_airllm_openbot
run_suite test_opensandbox_zai_integration.py tests optional_opensandbox_zai
run_suite test_merlin_optional_actions_provenance.py tests optional_actions_provenance
run_suite test_merlin_obsidian_vault_bridge.py tests obsidian_vault
python3 -B scripts/run_merlin_release_checks.py --repo . --output "$MERLIN_CI_EVIDENCE_DIR/release-negative-control.json" > "$MERLIN_CI_EVIDENCE_DIR/release-negative-control.log" 2>&1 || {
  cat "$MERLIN_CI_EVIDENCE_DIR/release-negative-control.log"
  exit 1
}
python3 -B tests/browser_research_wire_compatibility.py --private-source . --browser-source . --program config/merlin/research-program.json --output "$MERLIN_CI_EVIDENCE_DIR/browser-wire.json" > "$MERLIN_CI_EVIDENCE_DIR/browser-wire.log" 2>&1 || {
  cat "$MERLIN_CI_EVIDENCE_DIR/browser-wire.log"
  exit 1
}
build_dir="$(dirname "$MERLIN_CI_EVIDENCE_DIR")/merlin-offline-build"
cmake -S . -B "$build_dir" -G Ninja -DCMAKE_BUILD_TYPE=Release > "$MERLIN_CI_EVIDENCE_DIR/cmake-configure.log" 2>&1 || {
  tail -n 90 "$MERLIN_CI_EVIDENCE_DIR/cmake-configure.log"
  exit 1
}
cmake --build "$build_dir" --parallel 2 > "$MERLIN_CI_EVIDENCE_DIR/cmake-build.log" 2>&1 || {
  tail -n 90 "$MERLIN_CI_EVIDENCE_DIR/cmake-build.log"
  exit 1
}
ctest --test-dir "$build_dir" --output-on-failure > "$MERLIN_CI_EVIDENCE_DIR/ctest.log" 2>&1 || {
  tail -n 110 "$MERLIN_CI_EVIDENCE_DIR/ctest.log"
  exit 1
}
tail -n 12 "$MERLIN_CI_EVIDENCE_DIR/ctest.log"
python3 -B - <<'PY'
import json, os, pathlib, re
folder=pathlib.Path(os.environ['MERLIN_CI_EVIDENCE_DIR'])
labels=['release','studio_budget','studio_tools','bundled_model','offline_profile','studio_browser_bridge','primary_source_receipts','browser_contracts','research_handoff',
        'browser_lifecycle','lifecycle_controls','studio_integration','model_deadline','public_https',
        'optional_airllm_openbot','optional_opensandbox_zai','optional_actions_provenance','obsidian_vault']
counts={}
for label in labels:
    raw=(folder/(label+'.log')).read_text()
    assert "FAILED (" not in raw and "Traceback" not in raw
    matches=re.findall(r'Ran (\d+) tests? in ',raw)
    assert len(matches)==1, (label,matches)
    counts[label]=int(matches[0])
assert '100% tests passed' in (folder/'ctest.log').read_text(), 'native C++ CTest not fully passed'
release=json.loads((folder/'release-negative-control.json').read_text())
wire=json.loads((folder/'browser-wire.json').read_text())
assert release['passed'] is True
assert wire['status']=='passed' and wire['actual_browser_executed'] is False and wire['model_calls']==0
report={'schema':'merlin-integrated-offline-ci/1','status':'passed','source_commit':os.environ['MERLIN_EXPECTED_SHA'],
        'python_unittest_counts':counts,'total_python_unittest_cases':sum(counts.values()),
        'native_cpp_ctest':'all_passed','browser_wire_fixture':'passed',
        'real_model_calls':0,'native_chromium_calls':0,'production_qualified':False}
(folder/'summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':'passed','python_cases':sum(counts.values()),'cpp':'all_passed',
                  'native_browser':False,'real_model':False,'production_qualified':False}))
PY
