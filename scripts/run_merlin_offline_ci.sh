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
: > "$MERLIN_CI_EVIDENCE_DIR/python-suite-labels.txt"
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
  printf '%s\n' "$label" >> "$MERLIN_CI_EVIDENCE_DIR/python-suite-labels.txt"
  tail -n 5 "$MERLIN_CI_EVIDENCE_DIR/$label.log"
}
run_suite test_merlin_release_gate.py tests release
run_suite test_merlin_studio_output_budget.py tests studio_budget
run_suite test_merlin_studio_streaming.py tests studio_streaming
run_suite test_merlin_studio_web_contract.py tests studio_web_contract
run_suite test_merlin_studio_live_trace.py tests studio_live_trace
run_suite test_merlin_studio_resources.py tests studio_resources
run_suite test_merlin_studio_model_restart.py tests studio_model_restart
run_suite test_merlin_linux_preflight.py tests linux_preflight
run_suite test_merlin_studio_restart.py tests studio_restart
run_suite test_merlin_studio_tool_compatibility.py tests studio_tools
run_suite test_merlin_bundled_model_launcher.py tests bundled_model
run_suite test_merlin_offline_profile.py tests offline_profile
run_suite test_merlin_offline_delivery.py tests offline_delivery
run_suite test_profile.py scripts/merlin/parallax_cpu_disk parallax_profile_boundaries
run_suite test_merlin_native_smoke_diagnostics.py tests native_smoke_diagnostics
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
run_suite test_merlin_obsidian_fts5.py tests obsidian_fts5
run_suite test_merlin_obsidian_promotion.py tests obsidian_promotion
run_suite test_project_registry.py tests project_registry
run_suite test_merlin_second_brain_studio.py tests second_brain_studio
run_suite test_merlin_second_brain_portable.py tests second_brain_portable
run_suite test_merlin_skeptical_research_loops.py tests skeptical_research_loops
run_suite test_merlin_simulated_parallax.py tests simulated_parallax
run_suite test_merlin_research_episode.py tests research_episode
run_suite test_merlin_research_supervisor.py tests research_supervisor
run_suite test_merlin_common_input_reference_benchmark.py tests common_input_reference
run_suite test_merlin_second_brain_research_review.py tests second_brain_research_review
run_suite test_merlin_real_local_inference_acceptance.py tests real_local_inference_negative
run_suite test_merlin_real_model_probe_timeout.py tests real_model_probe_timeout
run_suite test_merlin_real_weight_runner.py tests real_weight_runner_negative
run_suite test_merlin_model_secret_isolation.py tests model_secret_isolation
# Cross-process resumability (three separate Python processes with an exact
# on-disk checkpoint). Synthetic data only; no model inference or background work.
research_checkpoint="$MERLIN_CI_EVIDENCE_DIR/simulated-research-checkpoint.json"
for episode in 1 2 3; do
  python3 -B scripts/merlin_research_episode.py --checkpoint "$research_checkpoint" --steps 1 > "$MERLIN_CI_EVIDENCE_DIR/simulated-research-episode-$episode.json"
done
python3 -B - <<'PY' > "$MERLIN_CI_EVIDENCE_DIR/simulated-research-summary.json"
import json, os, pathlib, sys
sys.path.insert(0, 'python')
from merlin.bounded_research_loop import ResearchSubloops
folder=pathlib.Path(os.environ['MERLIN_CI_EVIDENCE_DIR'])
x=ResearchSubloops.restore(json.loads((folder/'simulated-research-checkpoint.json').read_text()))
assert x.summary()['steps_used']==3 and not x.queue
assert all(r['status']=='checked' and r['observation_sha256'] for r in x.receipts)
assert all(r['observation'] for r in x.receipts)
assert x.summary()['background_worker_running'] is False
print(json.dumps({'schema':'merlin-cross-process-research-restart/1','status':'passed','steps':3,
                  'native_process_starts':3,'model_calls':0,'physical_gain_proven':False,
                  'production_qualified':False},sort_keys=True))
PY
run_suite test_merlin_paradox_preflight.py tests paradox_preflight
run_suite test_merlin_parallax_local_linear_reference.py tests parallax_reference
run_suite test_merlin_mamba_complex_state_reference.py tests mamba_complex_state
run_suite test_merlin_ssd_parallax_reference.py tests ssd_parallax_reference
python3 -B scripts/merlin_ssd_parallax_benchmark.py --output "$MERLIN_CI_EVIDENCE_DIR/ssd-parallax-benchmark.json" > "$MERLIN_CI_EVIDENCE_DIR/ssd-parallax-benchmark.log" 2>&1 || {
  cat "$MERLIN_CI_EVIDENCE_DIR/ssd-parallax-benchmark.log"
  exit 1
}
python3 -B scripts/merlin_simulated_benchmark.py --output "$MERLIN_CI_EVIDENCE_DIR/simulated-benchmark.json" > "$MERLIN_CI_EVIDENCE_DIR/simulated-benchmark.log" 2>&1 || {
  cat "$MERLIN_CI_EVIDENCE_DIR/simulated-benchmark.log"
  exit 1
}
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
import hashlib, json, math, os, pathlib, re
folder=pathlib.Path(os.environ['MERLIN_CI_EVIDENCE_DIR'])
labels=(folder/'python-suite-labels.txt').read_text().splitlines()
assert labels and len(labels)==len(set(labels)), 'missing or duplicate executed suite labels'
assert all(re.fullmatch(r'[a-z][a-z0-9_]{0,63}', label) for label in labels), 'invalid suite label'
counts={}
for label in labels:
    raw=(folder/(label+'.log')).read_text()
    assert "FAILED (" not in raw and "Traceback" not in raw
    matches=re.findall(r'Ran (\d+) tests? in ',raw)
    assert len(matches)==1, (label,matches)
    counts[label]=int(matches[0])
assert '100% tests passed' in (folder/'ctest.log').read_text(), 'native C++ CTest not fully passed'
simulated=json.loads((folder/'simulated-benchmark.json').read_text())
assert simulated['schema']=='merlin-virtual-substrate-host-benchmark/1'
assert simulated['source_commit']==os.environ['MERLIN_EXPECTED_SHA']
assert simulated['sequence_lengths']==[64,128,256,512] and simulated['samples_per_size']==5
assert simulated['trained_mamba_or_parallax_executed'] is False
assert simulated['production_qualified'] is False
ssd=json.loads((folder/'ssd-parallax-benchmark.json').read_text())
assert ssd['schema']=='merlin-ssd-parallax-attention-benchmark/1'
assert ssd['source_commit']==os.environ['MERLIN_EXPECTED_SHA']
assert ssd['source_tree_clean'] is True and ssd['expected_source_matches_head'] is True
assert ssd['source_files_unchanged_during_measurement'] is True
assert ssd['protocol']['default_protocol_used'] is True
assert ssd['protocol']['sizes']==[512,2048,8192] and ssd['protocol']['repeats']==5
assert ssd['protocol']['block_sizes']==[32,128] and ssd['protocol']['dimension']==8
assert ssd['real_parallax_formula_executed'] is True
for field in ('trained_model_evaluated','gpu_used','physical_ssd_verified',
              'cold_storage_benchmark','process_rss_measured','production_qualified'):
    assert ssd[field] is False, field
source_files={'python/merlin/ssd_parallax_reference.py','scripts/merlin_ssd_parallax_benchmark.py',
              'tests/test_merlin_ssd_parallax_reference.py',
              'docs/merlin/SSD_PARALLAX_EXPERIMENT_PROTOCOL_20261124.md'}
assert set(ssd['source_files_sha256'])==source_files
for name in source_files:
    assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==ssd['source_files_sha256'][name]
observations=[]
for row in ssd['observations']:
    assert row['numerical_agreement'] is True
    assert row['store']['payload_bytes']==row['rows']*16*8
    for block in (32,128):
        variant=row['variants']['file_block_'+str(block)]
        assert variant['max_abs_error_vs_resident'] <= 1e-10
        assert len(variant['trial_seconds'])==5
        assert all(math.isfinite(x) and x>0 for x in variant['trial_seconds'])
        io=variant['io']
        assert io['payload_passes']==1
        assert io['payload_bytes_read']==row['store']['payload_bytes']
        assert io['bytes_read']==row['store']['file_bytes']
        assert io['peak_read_buffer_bytes']<=block*16*8
        assert io['read_calls']==1+math.ceil(row['rows']/block)
    observations.append({'rows':row['rows'],'input_sha256':row['input_sha256'],
                         'max_abs_error':max(v['max_abs_error_vs_resident'] for v in row['variants'].values())})
assert [row['rows'] for row in observations]==[512,2048,8192]
# This is a post-experiment evidence review, not an additional physical trial.
# The separate Decimal/invariant/negative tests ran above, before this admission.
from merlin.bounded_research_loop import Question, ResearchSubloops
loop=ResearchSubloops(max_steps=1,max_tasks=1,max_depth=1)
loop.add(Question('ssd_parallax_evidence',
    'File-backed Parallax preserves the resident operator on the fixed synthetic workload',
    'Resident normalized probabilities/covariance and separate Decimal control tests',
    'Numerical disagreement, changed source, invalid integrity or unbounded read receipt',
    'Separate Decimal/invariant tests plus exact source, protocol and IO receipt checks'))
observation={'kind':'post_experiment_evidence_review','observations':observations,
    'benchmark_sha256':hashlib.sha256((folder/'ssd-parallax-benchmark.json').read_bytes()).hexdigest(),
    'independent_tests':counts['ssd_parallax_reference'],
    'test_log_sha256':hashlib.sha256((folder/'ssd_parallax_reference.log').read_bytes()).hexdigest(),
    'trained_model_evaluated':False,'physical_ssd_verified':False,'production_qualified':False}
def verify_review(question, observed):
    log=(folder/'ssd_parallax_reference.log').read_bytes()
    accepted=(observed.get('kind')=='post_experiment_evidence_review'
        and observed.get('independent_tests')==counts['ssd_parallax_reference']
        and counts['ssd_parallax_reference']>=30
        and observed.get('test_log_sha256')==hashlib.sha256(log).hexdigest()
        and observed.get('benchmark_sha256')==hashlib.sha256((folder/'ssd-parallax-benchmark.json').read_bytes()).hexdigest()
        and observed.get('trained_model_evaluated') is False
        and observed.get('physical_ssd_verified') is False
        and observed.get('production_qualified') is False)
    return {'accepted':accepted,
        'checker':'completed_independent_decimal_suite_and_source_protocol_io_checks',
        'reason':'Component evidence only; timings and allocation peaks do not qualify physical storage or models'}
receipt=loop.step(lambda question:{'observation':observation,'children':[]}, verify_review)
assert receipt['status']=='checked'
(folder/'ssd-parallax-research-checkpoint.json').write_text(json.dumps(loop.snapshot(),indent=2,sort_keys=True)+'\n')
release=json.loads((folder/'release-negative-control.json').read_text())
wire=json.loads((folder/'browser-wire.json').read_text())
assert release['passed'] is True
assert wire['status']=='passed' and wire['actual_browser_executed'] is False and wire['model_calls']==0
report={'schema':'merlin-integrated-offline-ci/1','status':'passed','source_commit':os.environ['MERLIN_EXPECTED_SHA'],
        'python_unittest_counts':counts,'total_python_unittest_cases':sum(counts.values()),
        'native_cpp_ctest':'all_passed','browser_wire_fixture':'passed',
        'real_model_calls':0,'native_chromium_calls':0,'simulated_host_benchmark':'recorded_not_model_evidence',
        'ssd_parallax_component_benchmark':'matched_attention_with_synthetic_tensors',
        'ssd_parallax_research_checkpoint':'post_experiment_evidence_review','production_qualified':False}
(folder/'summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':'passed','python_cases':sum(counts.values()),'cpp':'all_passed',
                  'native_browser':False,'real_model':False,'production_qualified':False}))
PY
