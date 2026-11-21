"""EGM-inspired continuity and review packets on the existing canonical store.

Inspiration: google/elephant-goldfish-model, 8e2a5ed781b5704735ccbbf5abf524b6db847190.
Original adapter; no upstream plugin or model runtime is installed. Host-owned
callbacks authorize source access and authenticate actual native review evidence.
Hashes and synthetic tests alone establish neither isolation nor independence.
"""
from __future__ import annotations
from copy import deepcopy
import json
import re
from typing import Callable, Mapping
from dot_ai_os.bridge import DotContextBridge, canonical, digest, integer, text_value, session_path, POLICY
from .artifact_ref import ArtifactRef
from .logos_review import validate_reviewer_provenance

MAX_PACKET = 65536
FLAGS = {'qualification': False, 'promotion_authority': False}


def source_identity(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('exact source commit required')
    return value


class ReviewContext:
    def __init__(self, bridge: DotContextBridge, *, authorize: Callable):
        if not isinstance(bridge, DotContextBridge) or not callable(authorize):
            raise ValueError('existing context bridge and host authorization required')
        self.bridge, self.registry, self.authorize = bridge, bridge.registry, authorize

    def _admit(self, role, value):
        ref = ArtifactRef.from_mapping(value).to_dict()
        if ref['project_id'] != self.bridge.project_id:
            raise ValueError('cross-project context rejected')
        if self.authorize(role, deepcopy(ref)) is not True:
            raise PermissionError('exact context reference not admitted by host')
        return ref

    def _read(self, role, value):
        ref = self._admit(role, value)
        return ref, self.registry.read_artifact_ref(ref, max_bytes=MAX_PACKET)['content']

    def _store(self, kind, body):
        raw = canonical(body)
        if len(raw) > MAX_PACKET:
            raise ValueError('complete packet byte ceiling exceeded')
        path = 'review-context/' + kind + '/' + digest(raw) + '.json'
        old = self.registry.artifact_history(self.bridge.project_id, path)
        if not old:
            self.registry.put_artifact(self.bridge.project_id, path, raw, 'application/json')
        history = self.registry.artifact_history(self.bridge.project_id, path)
        if len(history) != 1:
            raise RuntimeError('immutable context path has multiple versions')
        ref = self.registry.artifact_ref(self.bridge.project_id, path, version=1)
        if self.registry.read_artifact_ref(ref, max_bytes=MAX_PACKET)['content'] != raw:
            raise RuntimeError('context packet bytes differ')
        return {'packet_ref': ref, 'packet': body}

    def elephant(self, session_id, *, source_commit, query, pinned_records, known_gaps, budget_bytes=32000):
        """Historical source pins are intentional; no account-wide memory access."""
        source_identity(source_commit)
        integer(budget_bytes, 'budget_bytes', 4000, MAX_PACKET)
        if (not isinstance(known_gaps, list) or len(known_gaps) > 30
                or any(not isinstance(x, str) or not x.strip() or len(x) > 500 for x in known_gaps)):
            raise ValueError('bounded explicit coverage gaps required')
        if not isinstance(pinned_records, list) or not 1 <= len(pinned_records) <= 50:
            raise ValueError('one to 50 explicit record/source pairs required')
        pins = deepcopy(pinned_records)
        for pin in pins:
            if not isinstance(pin, dict) or set(pin) != {'record_ref', 'source_ref'}:
                raise ValueError('exact record/source pair required')
            pin['record_ref'] = self._admit('elephant_record', pin['record_ref'])
            pin['source_ref'] = self._admit('elephant_source', pin['source_ref'])
        ref = self.registry.artifact_ref(self.bridge.project_id, session_path(session_id))
        ref, raw = self._read('elephant_handoff', ref)
        sources = json.loads(raw).get('source_refs')
        admitted = {canonical(p['source_ref']) for p in pins}
        if not isinstance(sources, list) or not sources or any(canonical(r) not in admitted for r in sources):
            raise PermissionError('handoff contains a source outside admitted pins')
        loaded = self.bridge.load_handoff(session_id)
        if canonical(loaded['handoff_ref']) != canonical(ref):
            raise RuntimeError('handoff advanced during packet construction')
        body = {'schema': 'merlin-elephant-context/1', 'source_commit': source_commit,
            'handoff_ref': ref, 'handoff': loaded['handoff'], 'policy': POLICY,
            'coverage': {'all_chat_history_available': False, 'scope': 'explicit_source_pairs_only',
                'source_pair_count': len(pins), 'known_gaps': deepcopy(known_gaps)}, 'retrieval': None, **FLAGS}
        remaining = budget_bytes - len(canonical(body)) - 64
        if remaining < 2000:
            raise ValueError('handoff and coverage exceed complete packet budget')
        body['retrieval'] = self.bridge.search(query, pinned_records=pins,
            budget_bytes=min(64000, remaining), limit=30)
        if len(canonical(body)) > budget_bytes:
            raise ValueError('complete context budget exceeded')
        return self._store('elephant', body)

    def goldfish(self, *, source_commit, persona_ref, target_ref, standard_refs, source_refs, budget_bytes=MAX_PACKET):
        """Explicit whole documents only; never reads a parent handoff or memory.

        Host authorization must also classify/minimize content: path exclusions
        alone cannot detect a transcript disguised as a specification.
        """
        source_identity(source_commit)
        integer(budget_bytes, 'budget_bytes', 4000, MAX_PACKET)
        if (not isinstance(standard_refs, list) or not 1 <= len(standard_refs) <= 8
                or not isinstance(source_refs, list) or len(source_refs) > 20):
            raise ValueError('bounded explicit standards and sources required')
        selected = [('persona', persona_ref), ('target', target_ref)]
        selected += [('standard', r) for r in standard_refs] + [('source', r) for r in source_refs]
        documents, seen = [], set()
        for role, value in selected:
            ref = ArtifactRef.from_mapping(value).to_dict()
            if ref['logical_path'].startswith(('handoffs/', 'review-context/')):
                raise ValueError('parent handoff/context cannot be a reviewer document')
            key = canonical(ref)
            if key in seen:
                raise ValueError('duplicate review document')
            seen.add(key)
            ref, raw = self._read('goldfish_' + role, ref)
            text = raw.decode('utf-8')
            if not text.strip():
                raise ValueError('empty review document')
            documents.append({'role': role, 'ref': ref, 'text': text})
        body = {'schema': 'merlin-goldfish-packet/1', 'source_commit': source_commit,
            'documents': documents, 'parent_transcript_supplied': False,
            'runtime_isolation': 'not_established_by_packet', 'review_state': 'not_run', 'policy': POLICY, **FLAGS}
        if len(canonical(body)) > budget_bytes:
            raise ValueError('whole selected documents exceed budget; no silent truncation')
        return self._store('goldfish', body)

    def _packet(self, value):
        ref, raw = self._read('review_packet', value)
        body = json.loads(raw)
        if (not isinstance(body, dict) or canonical(body) != raw or ref['version'] != 1
                or ref['logical_path'] != 'review-context/goldfish/' + digest(raw) + '.json'):
            raise ValueError('exact immutable reviewer packet required')
        docs = body.get('documents')
        if (not isinstance(docs, list) or not 3 <= len(docs) <= 30
                or any(not isinstance(d, dict) or set(d) != {'role', 'ref', 'text'} for d in docs)):
            raise ValueError('complete document list required')
        roles = {role: [d['ref'] for d in docs if d['role'] == role] for role in ('persona', 'target', 'standard', 'source')}
        if len(roles['persona']) != 1 or len(roles['target']) != 1 or any(d['role'] not in roles for d in docs):
            raise ValueError('review document roles differ')
        rebuilt = self.goldfish(source_commit=body.get('source_commit'), persona_ref=roles['persona'][0],
            target_ref=roles['target'][0], standard_refs=roles['standard'], source_refs=roles['source'])
        if canonical(rebuilt['packet_ref']) != canonical(ref):
            raise ValueError('packet differs from exact authorized source bytes and policy')
        return ref, body

    def blocked_review(self, packet_ref):
        ref, _ = self._packet(packet_ref)
        return self._store('review', {'schema': 'merlin-goldfish-review/1', 'packet_ref': ref,
            'status': 'blocked_missing_fresh_context_runtime', 'model_review_performed': False,
            'independent_verification': False, 'merge_authorized': False, 'deployment_authorized': False, **FLAGS})

    def record_review(self, packet_ref, *, request_id, parent_session_id, trace: Mapping, findings: list, authenticate: Callable):
        """Admit authenticated native traces, not parent-written completion claims.

        No model is invoked here. Authentication is a host trust boundary, not
        something established by a matching hash or a test fixture returning True.
        """
        ref, body = self._packet(packet_ref)
        text_value(request_id, 'request_id', 200); text_value(parent_session_id, 'parent_session_id', 200)
        if not callable(authenticate) or not isinstance(trace, Mapping):
            raise ValueError('native trace and host authenticator required')
        observed = deepcopy(dict(trace))
        keys = {'request_id', 'packet_sha256', 'child_session_id', 'parent_session_id', 'reviewer',
            'evidence_kind', 'status', 'parent_context_inherited', 'memory_access_disabled',
            'instruction_isolation_observed', 'read_refs'}
        if (set(observed) != keys or observed['request_id'] != request_id
                or observed['packet_sha256'] != ref['sha256'] or observed['parent_session_id'] != parent_session_id
                or observed['child_session_id'] == parent_session_id or observed['evidence_kind'] != 'native_runtime_trace'
                or observed['status'] != 'completed' or observed['parent_context_inherited'] is not False
                or observed['memory_access_disabled'] is not True or observed['instruction_isolation_observed'] is not True):
            raise ValueError('complete fresh exact-request native review not established')
        text_value(observed['child_session_id'], 'child_session_id', 200)
        validate_reviewer_provenance(observed['reviewer'])
        documents = {canonical(d['ref']): d for d in body['documents']}
        reads = observed['read_refs']
        if (not isinstance(reads, list) or len(reads) != len(documents)
                or {canonical(ArtifactRef.from_mapping(r).to_dict()) for r in reads} != set(documents)):
            raise ValueError('native reviewer must read every selected document exactly once')
        if not isinstance(findings, list) or len(findings) > 30:
            raise ValueError('bounded findings required')
        normalized = deepcopy(findings)
        for f in normalized:
            if not isinstance(f, dict) or set(f) != {'ref', 'line_start', 'line_end', 'severity', 'detail'}:
                raise ValueError('source-located finding required')
            key = canonical(ArtifactRef.from_mapping(f['ref']).to_dict())
            if key not in documents or f['severity'] not in {'question', 'risk', 'blocking'}:
                raise ValueError('finding source or severity differs')
            integer(f['line_start'], 'line_start', 1, len(documents[key]['text'].splitlines()))
            integer(f['line_end'], 'line_end', f['line_start'], len(documents[key]['text'].splitlines()))
            text_value(f['detail'], 'detail', 2000)
        data = {'packet_ref': ref, 'trace': observed, 'findings': normalized}
        if authenticate(deepcopy(data), digest(canonical(data))) is not True:
            raise PermissionError('native review evidence not authenticated by host')
        return self._store('review', {'schema': 'merlin-goldfish-review/1', **data, 'status': 'review_observed',
            'model_review_performed': True, 'independent_verification': False,
            'merge_authorized': False, 'deployment_authorized': False, **FLAGS})
