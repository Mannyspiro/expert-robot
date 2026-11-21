"""Local retained-byte review; produces no host or repository publication.

The pinned draft recovery helper is inspected source. Only its pure inspection
and derivation functions execute, with all writes in a TemporaryDirectory.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_ROOT = Path('/workspace/scratch/abed42219434/browser-operations/activation-44946846703')
ORIGINAL = ORIGINAL_ROOT/'artifact/root-evidence/database-arxiv-18106dfc-0a56-4b68-9d30-5d334d7d6a69/result'
SOURCE_HELPER = Path('/workspace/scratch/abed42219434/browser-operations/ops/merlin_browser/recover_capture.py')
HELPER = ROOT/'review-evidence-20261121/recover_capture_canonical_candidate.py'
sys.path.insert(0, str(ROOT/'python'))
from merlin.browser_ingest import publish_episode, validate_episode
from merlin.browser_policy import BrowserPolicyError
from merlin.project_registry import MerlinRegistry


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(directory):
    return [{'path':str(path.relative_to(directory)), 'bytes':len(path.read_bytes()),
             'sha256':sha(path.read_bytes())}
            for path in sorted(directory.rglob('*')) if path.is_file()]


original_spec = importlib.util.spec_from_file_location('original_recovery_helper', SOURCE_HELPER)
original_helper = importlib.util.module_from_spec(original_spec)
original_spec.loader.exec_module(original_helper)
try:
    original_helper.inspect_original(ORIGINAL)
except original_helper.RecoveryError as error:
    original_helper_error=str(error)
else:
    raise AssertionError('Original helper serialization defect no longer reproduced')
assert original_helper_error=='canonical original manifest required'

spec = importlib.util.spec_from_file_location('reviewed_recovery_helper', HELPER)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
before = inventory(ORIGINAL)
assert sha((ORIGINAL_ROOT/'artifact.zip').read_bytes()) == recovery.SOURCE_ARTIFACT
assert sha((ORIGINAL.parent/'launch-receipt.json').read_bytes()) == recovery.SOURCE_LAUNCH
try:
    validate_episode(ORIGINAL)
except BrowserPolicyError as error:
    original_error = str(error)
else:
    raise AssertionError('Original semantically invalid ledger unexpectedly accepted')
assert original_error == 'resource byte ledger differs'

checked = recovery.inspect_original(ORIGINAL)
resources = [event['event'] for event in checked['events'] if event['event']['kind']=='resource']
prefixes = [0]
for resource in resources:
    prefixes.append(prefixes[-1]+resource['body_bytes'])
assert len(resources)==31 and prefixes[-1]==738314
for index, resource in enumerate(resources):
    assert resource['episode_response_body_bytes']-resource['consumed_body_bytes']==prefixes[index]
    assert resource['episode_response_body_bytes'] in prefixes[index+1:]

negative_results = []
with tempfile.TemporaryDirectory(prefix='retained-recovery-review-') as temporary:
    temporary = Path(temporary)
    derived = recovery.write_derived(checked, temporary/'derived')
    validated = validate_episode(temporary/'derived')
    assert validated['manifest']['counts']['requests']==31
    assert validated['manifest']['counts']['response_body_bytes']==738314
    assert validated['manifest']['episode_id']==recovery.DERIVED_EPISODE
    provenance = derived['provenance']
    assert provenance['new_browser_execution'] is False
    assert provenance['network_reacquired'] is False
    assert provenance['original_bytes_modified'] is False
    for name, raw in checked['files'].items():
        if not name.startswith('events/'):
            assert derived['files'][name]==raw
    publication = publish_episode(temporary/'derived', MerlinRegistry(temporary/'registry'))
    source = publication['sources'][0]['source_ref']
    expected_text = (ORIGINAL/'observations/o0001/text.txt').read_bytes()
    assert MerlinRegistry(temporary/'registry').read_artifact_ref(source)['content']==expected_text
    fresh_process = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
        'from merlin.browser_ingest import publish_episode; '
        'from merlin.project_registry import MerlinRegistry; '
        'print(json.dumps(publish_episode(Path(sys.argv[2]),MerlinRegistry(Path(sys.argv[3]))),sort_keys=True))',
        str(ROOT/'python'), str(temporary/'derived'), str(temporary/'registry')],
        check=True, capture_output=True, text=True)
    assert json.loads(fresh_process.stdout)==publication
    for mode in ('changed_manifest','changed_body','unlisted_file','symlink_body'):
        target = temporary/mode
        shutil.copytree(ORIGINAL,target)
        if mode=='changed_manifest':
            (target/'episode.json').write_bytes((target/'episode.json').read_bytes()+b' ')
        elif mode=='changed_body':
            (target/'observations/o0001/text.txt').write_bytes(b'changed original')
        elif mode=='unlisted_file':
            (target/'unlisted.txt').write_bytes(b'not original')
        else:
            body=target/'observations/o0001/text.txt'
            body.unlink();body.symlink_to(ORIGINAL/'observations/o0001/text.txt')
        try:
            recovery.inspect_original(target)
        except (recovery.RecoveryError,OSError) as error:
            negative_results.append({'case':mode,'rejected':True,'error_type':type(error).__name__})
        else:
            raise AssertionError('Invalid original admitted: '+mode)
    for mode in ('wrong_interval_start','wrong_terminal_total','failed_resource','missing_resource'):
        changed=copy.deepcopy(resources)
        if mode=='wrong_interval_start': changed[0]['consumed_body_bytes']+=1
        elif mode=='wrong_terminal_total': changed[-1]['body_bytes']+=1
        elif mode=='failed_resource': changed[0]['outcome']='denied'
        else: changed.pop()
        try:
            recovery.ledger_proof(changed)
        except recovery.RecoveryError as error:
            negative_results.append({'case':mode,'rejected':True,'error_type':type(error).__name__})
        else:
            raise AssertionError('Invalid reconstruction admitted: '+mode)

after=inventory(ORIGINAL)
assert before==after
report = {
    'schema':'merlin-local-retained-recovery-review/1',
    'source_run_id':recovery.SOURCE_RUN,
    'source_artifact_sha256':recovery.SOURCE_ARTIFACT,
    'source_manifest_sha256':recovery.SOURCE_MANIFEST,
    'source_launch_receipt_sha256':recovery.SOURCE_LAUNCH,
    'original_helper_sha256':sha(SOURCE_HELPER.read_bytes()),
    'original_helper_rejection':original_helper_error,
    'reviewed_helper_sha256':sha(HELPER.read_bytes()),
    'strict_importer_sha256':sha((ROOT/'python/merlin/browser_ingest.py').read_bytes()),
    'original_importer_rejection':original_error,
    'raw_files_verified_unchanged':len(before),
    'original_inventory_sha256':sha(json.dumps(before,sort_keys=True,separators=(',',':')).encode()),
    'resources':31,
    'response_body_bytes':738314,
    'derived_manifest_sha256':derived['manifest_sha256'],
    'derivation_provenance_sha256':derived['provenance_sha256'],
    'derived_episode_id':recovery.DERIVED_EPISODE,
    'strict_importer_accepted_derivative':True,
    'canonical_publication_and_fresh_process_replay':'local_temporary_registry_only',
    'rendered_text_sha256':sha(expected_text),
    'negative_cases':negative_results,
    'model_calls':0,
    'network_calls':0,
    'native_browser_execution':False,
    'host_mutation':False,
    'qualification':False,
    'promotion_authority':False,
    'limitations':[
        'Derived accounting is a separately identified reconstruction, not original renderer evidence.',
        'This checks one pinned legacy trace and cannot recover arbitrary missing or failed events.',
        'Host recovery/deployment, native successor acceptance and remote publication remain unexecuted.',
    ],
}
destination=ROOT/'review-evidence-20261121/retained-recovery-review.json'
destination.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps(report,sort_keys=True))
