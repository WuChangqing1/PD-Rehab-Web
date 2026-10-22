from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.core.errors import APIError
from app.ml.micro_expression.adapter import MicroExpressionAnalyzer
from app.ml.registry import ModelState
from app.schemas.assessment import MicroExpressionAnalyzeRequest


@pytest.fixture
def configured_source(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    for name in ['recognition/fglgl.py', 'recognition/dataset.py', 'recognition/__init__.py',
                 'recognition/flow_branch.py', 'recognition/magnet.py', 'recognition/vit_da.py',
                 'recognition/au_local_global.py', 'recognition/config.yaml',
                 'common/optical_flow.py', 'common/au_regions.py']:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# provided source', encoding='utf-8')
    monkeypatch.setattr(settings, 'micro_expression_model_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'micro_expression_entry', 'microflow_da')
    monkeypatch.setattr(settings, 'micro_expression_checkpoint', '')
    return tmp_path


def test_source_without_weights_is_connected_but_never_ready(configured_source):
    analyzer = MicroExpressionAnalyzer()
    status = analyzer.load()
    assert status.state is ModelState.MODEL_NOT_CONFIGURED
    assert status.extra['adapter'] == 'microflow_da'
    assert status.extra['labels'] == ['negative', 'positive', 'surprise']
    assert status.extra['source_present'] is True
    assert status.extra['live_supported'] is False
    assert 'checkpoint' in status.extra['missing']


def test_installed_checkpoint_without_verified_resources_is_not_reported_as_missing(configured_source):
    from app.ml.micro_expression.microflow import MicroFlowRuntime
    # Inspecting file presence must not unpickle an unverified checkpoint.
    (configured_source/'recognition.pth').write_bytes(b'not-a-loadable-checkpoint')
    status=MicroFlowRuntime(configured_source).inspect()
    assert status.state is ModelState.MODEL_NOT_CONFIGURED
    assert status.extra['checkpoint_present'] is True
    assert 'checkpoint' not in status.extra['missing']
    assert '权重已安置' in status.detail
    assert '等待训练权重' not in status.detail


def test_missing_weights_refuses_analysis_without_probabilities(configured_source, tmp_path):
    video = tmp_path / 'clip.mp4'
    video.write_bytes(b'not-a-video')
    analyzer = MicroExpressionAnalyzer()
    with pytest.raises(APIError) as error:
        analyzer.analyze(str(video))
    assert error.value.code == 'MODEL_NOT_CONFIGURED'
    assert 'probabilities' not in str(error.value.detail)


@pytest.mark.parametrize('frames', [dict(onset_frame=0, apex_frame=2),
    dict(onset_frame=1, apex_frame=1), dict(onset_frame=3, apex_frame=2),
    dict(onset_frame=1), dict(apex_frame=3)])
def test_keyframes_require_ordered_one_based_pair(frames):
    with pytest.raises(ValidationError):
        MicroExpressionAnalyzeRequest(**frames)


def test_keyframes_reach_schema_without_silent_discard():
    value = MicroExpressionAnalyzeRequest(onset_frame=2, apex_frame=8)
    assert value.model_dump()['onset_frame'] == 2
    assert value.model_dump()['apex_frame'] == 8


def test_status_probe_never_resets_a_loaded_model_to_unavailable(configured_source):
    # A missing model is stable across health/status probes.
    analyzer = MicroExpressionAnalyzer()
    assert analyzer.load().state is analyzer.refresh_status().state


def test_reversed_keyframes_return_validation_error_not_server_error(app_client, auth_headers):
    patient = app_client.post('/api/patients', headers=auth_headers,
        json=dict(hospital_number='micro-test', name='虚拟验收', sex='FEMALE')).json()
    session = app_client.post(f"/api/patients/{patient['id']}/assessment-sessions",
        headers=auth_headers, json=dict(session_type='MICRO_EXPRESSION_ONLY')).json()
    reply = app_client.post(f"/api/assessment-sessions/{session['id']}/micro-expression",
        headers=auth_headers, data=dict(onset_frame=3, apex_frame=2),
        files=dict(video=('test.mp4', b'test', 'video/mp4')))
    assert reply.status_code == 422


def test_missing_microflow_weights_never_persist_upload(configured_source, app_client, auth_headers, db):
    from sqlalchemy import select, func
    from app.db.models import MediaFile, MicroExpressionResult
    patient = app_client.post('/api/patients', headers=auth_headers,
        json=dict(hospital_number='missing-model', name='虚拟验收', sex='FEMALE')).json()
    session = app_client.post(f"/api/patients/{patient['id']}/assessment-sessions",
        headers=auth_headers, json=dict(session_type='MICRO_EXPRESSION_ONLY')).json()
    reply = app_client.post(f"/api/assessment-sessions/{session['id']}/micro-expression",
        headers=auth_headers, data=dict(onset_frame=1, apex_frame=2),
        files=dict(video=('test.mp4', b'test', 'video/mp4')))
    assert reply.status_code == 503
    assert reply.json()['error']['code'] == 'MODEL_NOT_CONFIGURED'
    assert db.scalar(select(func.count()).select_from(MediaFile)) == 0
    assert db.scalar(select(func.count()).select_from(MicroExpressionResult)) == 0


def test_keyframes_and_three_class_results_roundtrip_through_api(app_client, auth_headers, monkeypatch, tmp_path):
    from app.services import assessment_service as service
    seen = {}
    video = tmp_path/'test-only.mp4';video.write_bytes(b'test-only-video')
    monkeypatch.setattr(settings,'micro_expression_entry','')
    monkeypatch.setattr(service,'store_upload',lambda **kwargs:(video,'test-sha',str(video)))
    def inference(path, **kwargs):
        seen.update(kwargs)
        return dict(model_name='TEST_ONLY',model_version='contract-fixture',pd_probability=None,
            predicted_class='positive',dominant_tag='positive',
            tag_distribution=[dict(name='negative',score=.1),dict(name='positive',score=.7),dict(name='surprise',score=.2)],
            raw_output_json=dict(source='TEST_ONLY',clinical_eligible=False,**kwargs),quality_json={},inference_time_ms=1)
    monkeypatch.setattr(service.micro_expression_analyzer,'analyze',inference)
    patient = app_client.post('/api/patients',headers=auth_headers,
        json=dict(hospital_number='keyframe-contract',name='虚拟验收',sex='FEMALE')).json()
    session = app_client.post(f"/api/patients/{patient['id']}/assessment-sessions",headers=auth_headers,
        json=dict(session_type='MICRO_EXPRESSION_ONLY')).json()
    url=f"/api/assessment-sessions/{session['id']}/micro-expression"
    reply=app_client.post(url,headers=auth_headers,data=dict(onset_frame=2,apex_frame=8),
        files=dict(video=('test.mp4',b'test-only-video','video/mp4')))
    assert reply.status_code==200
    assert seen==dict(onset_frame=2,apex_frame=8)
    saved=app_client.get(url,headers=auth_headers).json()[0]
    assert saved['tag_distribution']==reply.json()['tag_distribution']
    assert saved['pd_probability'] is None
    assert saved['raw_output_json']['source']=='TEST_ONLY'


def test_three_class_result_retains_semantics_and_has_no_pd_probability():
    from app.ml.micro_expression.microflow import normalize_probabilities
    raw = normalize_probabilities([.1, .7, .2])
    normalized = MicroExpressionAnalyzer()._normalize(raw, 123)
    assert normalized['predicted_class'] == 'positive'
    assert normalized['pd_probability'] is None
    assert normalized['tag_distribution'] == [dict(name='negative', score=.1),
        dict(name='positive', score=.7), dict(name='surprise', score=.2)]
    assert normalized['raw_output_json']['clinical_eligible'] is False


@pytest.mark.parametrize('probabilities', [[.1]*7, [.1,.2,.3], [float('nan'),.2,.8],
                                         [True,0,0], [-.1,.5,.6]])
def test_invalid_or_seven_class_output_is_rejected(probabilities):
    from app.ml.micro_expression.microflow import normalize_probabilities
    with pytest.raises(ValueError): normalize_probabilities(probabilities)


def test_video_frame_indices_decode_actual_requested_frames(tmp_path):
    import cv2
    import numpy as np
    from app.ml.micro_expression.microflow import read_keyframes
    path = tmp_path/'frames.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64,64))
    assert writer.isOpened()
    for value in [30,80,130,180]: writer.write(np.full((64,64,3), value, dtype=np.uint8))
    writer.release()
    first, peak, fps = read_keyframes(path, 1, 3)
    assert abs(first.mean()-30) < 3
    assert abs(peak.mean()-130) < 3
    assert fps == 10
    with pytest.raises(APIError) as error: read_keyframes(path,1,5)
    assert error.value.code == 'VIDEO_TOO_SHORT'


def test_microflow_live_capabilities_never_request_continuous_video(configured_source):
    from app.services.live_emotion_service import capabilities
    result = capabilities()
    assert result['capture_required'] is False
    assert result['labels'] == ['negative','positive','surprise']
    assert result['live_supported'] is False
    assert 'probabilities' not in result


@pytest.mark.parametrize('patch', [dict(training_verified=False),
    dict(labels=['positive','negative','surprise']), dict(channel_order='RGB'),
    dict(flow_method='unknown'), dict(checkpoint_sha256='wrong')])
def test_manifest_refuses_unverified_training_and_mismatched_resources(configured_source, patch):
    import json
    from app.ml.micro_expression.microflow import MicroFlowRuntime,sha256,source_digest
    root=configured_source
    for name in ['recognition.pth','shape_predictor_68_face_landmarks.dat','model-config.yaml']:
        (root/name).write_bytes(b'contract-test-only')
    manifest=dict(schema_version=1,training_verified=True,labels=['negative','positive','surprise'],
        channel_order='BGR',flow_method='farneback',checkpoint_sha256=sha256(root/'recognition.pth'),
        landmark_sha256=sha256(root/'shape_predictor_68_face_landmarks.dat'),
        config_sha256=sha256(root/'model-config.yaml'),source_sha256=source_digest(root/'source'))
    (root/'deployment.json').write_text(json.dumps(manifest|patch),encoding='utf-8')
    with pytest.raises(ValueError): MicroFlowRuntime(root).verify_manifest()


SOURCE = Path(__file__).resolve().parents[2]/'models/microflow_da/source'


@pytest.mark.skipif(not SOURCE.is_dir(), reason='user-supplied private source not present')
def test_supplied_fglgl_source_forward_and_strict_weight_reload(tmp_path):
    torch=pytest.importorskip('torch')
    from app.ml.micro_expression.microflow import load_source
    # Tiny architecture and generated tensors are test-only structural checks,
    # not trained weights, predictions, accuracy measurements or deployment data.
    cfg=dict(img_size=32,in_channels=3,flow_hidden=8,magnet_latent=8,
        vitda_dim=16,vitda_depth=1,vitda_heads=2,patch_size=16,drop_key=0.,drop_path=0.,
        num_regions=9,region_size=16,region_patch=16,vit_shared_depth=1,
        vit_global_depth=1,num_classes=3,feat_dim=16)
    torch.set_num_threads(2)
    model=load_source(SOURCE)(cfg).eval()
    path=tmp_path/'test-only.pth';torch.save(model.state_dict(),path)
    state=torch.load(path,weights_only=True,map_location='cpu')
    reloaded=load_source(SOURCE)(cfg).eval();reloaded.load_state_dict(state,strict=True)
    args=[torch.zeros(1,3,32,32) for _ in range(3)]+[torch.zeros(1,9,3,16,16)]
    with torch.inference_mode():
        a=model(*args)[0];b=reloaded(*args)[0]
    assert a.shape == (1,3) and torch.isfinite(a).all()
    assert torch.equal(a,b)
    state.pop('classifier.weight')
    with pytest.raises(RuntimeError): reloaded.load_state_dict(state,strict=True)
    from app.ml.micro_expression.microflow import verify_temporal_response
    with pytest.raises(ValueError, match='TEMPORAL_BRANCH_DISCONNECTED'):
        verify_temporal_response(model, cfg, 'cpu')


@pytest.mark.skipif(not SOURCE.is_dir(), reason='user-supplied private source not present')
def test_supplied_transforms_are_used_without_dummy_landmarks():
    import numpy as np
    from app.ml.micro_expression.microflow import preprocessing_functions
    transforms=preprocessing_functions(SOURCE)
    sample=np.full((4,4,3),255,dtype=np.uint8)
    assert np.array_equal(transforms['to_chw_normalized'](sample),np.ones((3,4,4)))
    assert 'DummyLandmarkProvider' not in transforms
