"""End-to-end staging evidence using a non-patient media file supplied by QA."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

import httpx

base = 'http://127.0.0.1:18193'
video = Path(sys.argv[1]).read_bytes()
duration_ms = int(sys.argv[2])
assert os.environ['BOOTSTRAP_ADMIN_USERNAME'] == 'stageqa'
capture = str(uuid.uuid4())
with httpx.Client(base_url=base, timeout=35, trust_env=False) as http:
    def request(method, path, code=200, **kwargs):
        response = http.request(method, '/api' + path, **kwargs)
        assert response.status_code == code, (method, path, response.status_code, response.text[:300])
        return response

    assert request('GET', '/system/health').json()['env'] == 'staging'
    auth = request('POST', '/auth/login', json={'username': os.environ['BOOTSTRAP_ADMIN_USERNAME'],
        'password': os.environ['BOOTSTRAP_ADMIN_PASSWORD']}).json()
    http.headers['Authorization'] = 'Bearer ' + auth['access_token']
    def api(method, path, code=200, **kwargs):
        return request(method, '/integration/v1' + path, code, **kwargs).json()

    cap = api('GET', '/capabilities')
    print('capabilities', {key: cap[key] for key in ('face_recordings_ready', 'face_model_ready', 'protocol_revision')}, flush=True)
    assert cap['face_recordings_ready'] and cap['face_model_ready'] and cap['protocol_revision'] == '1.2'
    patient = request('POST', '/patients', 201, json={'name': 'Training video staging QA', 'sex': 'UNKNOWN'}).json()
    binding = {'patient_id': patient['id'], 'device_id': capture, 'local_profile_id': capture}
    api('POST', '/bindings', json=binding)
    practice = api('POST', '/records', 201, json={**binding, 'source_record_id': 'qa-practice',
        'record_type': 'PIANO_SESSION', 'schema_version': 'staging-qa', 'payload': {'qa_metric': 42}})
    for revision, units in ((2, 2), (1, 1), (None, 0)):
        payload = {'record': {'plan_id': 'qa-plan', 'plan_json': {'title': 'QA count', 'start': '2026-11-01'}},
            'daily_progress': [{'local_date': '2026-11-04', 'completed_units': units, 'target': 3, 'target_type': 'count'}]}
        if revision is not None:
            payload['snapshot_revision'] = revision
        api('POST', '/records', 201, json={**binding, 'source_record_id': 'qa-plan-' + str(revision),
            'record_type': 'TRAINING_PLAN', 'schema_version': 'staging-qa', 'payload': payload})
    chosen = api('GET', '/plans', params={'patient_id': patient['id'], 'on_date': '2026-11-04'})['items']
    assert len(chosen) == 1 and chosen[0]['progress']['completed_units'] == 2 and chosen[0]['version_count'] == 3
    assert api('GET', '/plans', params={'patient_id': patient['id'], 'on_date': '2026-11-03'})['items'][0]['progress'] is None
    print('daily_progress 2/3; absent date remains unknown; three versions retained', flush=True)
    face = '/face/recordings'
    file_id = str(uuid.uuid4())
    size = cap['face_recording_chunk_bytes']
    parts = [video[i:i + size] for i in range(0, len(video), size)]
    sha = lambda value: hashlib.sha256(value).hexdigest()
    manifest = {**binding, 'external_record_id': practice['id'], 'client_capture_id': capture,
        'agreed_at_ms': int(time.time() * 1000), 'consent_version': 'face-capture-v1',
        'files': [{'file_id': file_id, 'sequence': 0, 'size_bytes': len(video), 'sha256': sha(video),
            'chunk_count': len(parts), 'duration_ms': duration_ms, 'mime_type': 'video/mp4'}]}
    parent = api('POST', face, 201, json=manifest)['recording_id']
    path = face + '/' + parent
    assert api('POST', face, 201, json=manifest)['recording_id'] == parent
    for i, part in enumerate(parts):
        args = {'headers': {'X-Chunk-SHA256': sha(part), 'Content-Type': 'application/octet-stream'}, 'content': part}
        url = f'{path}/files/{file_id}/chunks/{i}'
        api('PUT', url, **args)
        api('PUT', url, **args)
    assert api('GET', path)['uploaded_chunks'][file_id] == list(range(len(parts)))
    api('POST', path + '/complete', 202)
    api('POST', path + '/complete', 202)
    def wait_for(states, seconds=220):
        for _ in range(seconds // 2):
            item = api('GET', path)
            if item['status'] in states:
                return item
            time.sleep(2)
        raise TimeoutError('stage recording remained nonterminal')
    selection = wait_for({'REVIEW_REQUIRED', 'NO_VALID_SEGMENTS', 'FAILED'})
    print('real spotting status', selection['status'], 'uploaded chunks', len(parts), flush=True)
    try:
        if selection['status'] == 'REVIEW_REQUIRED':
            segments = api('GET', path + '/segments')['items']
            segment = next(item for item in segments if item['status'] == 'REVIEW_REQUIRED')
            candidate = segment['candidates'][0]
            review_path = f"{path}/segments/{segment['id']}"
            api('POST', review_path + '/review', 422, json={'candidate_id': candidate['id']})
            for kind in ('onset', 'apex', 'offset'):
                preview = request('GET', '/integration/v1' + review_path + '/frames/' + kind,
                    params={'candidate_id': candidate['id']})
                assert preview.content[:2] == b'\xff\xd8' and 'no-store' in preview.headers['cache-control']
            api('POST', review_path + '/review', 202, json={'candidate_id': candidate['id'], 'review_confirmed': True})
            api('POST', review_path + '/review', 409, json={'candidate_id': candidate['id'], 'review_confirmed': True})
            result = wait_for({'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED'})
            print('real inference status', result['status'], flush=True)
            assert result['results'] and result['results'][0]['model_name'] == 'CausalNet'
            assert result['results'][0]['tag_distribution']
            print('persisted model version', result['results'][0]['model_version'], flush=True)
        else:
            raise AssertionError('No reviewable candidate: actual model result not exercised')
    finally:
        api('DELETE', path)
        erased = api('GET', path)
        assert erased['status'] == 'DELETED' and erased['media_deleted'] and not erased['results']
        rows = api('GET', '/records', params={'patient_id': patient['id']})['items']
        assert any(item['id'] == practice['id'] and item['payload_sha256'] == practice['payload_sha256'] for item in rows)
        detail = api('GET', '/records/' + practice['id'], params={'patient_id': patient['id']})
        assert detail['payload'] == {'qa_metric': 42}
        print('video and result cleared; original practice payload unchanged', flush=True)
