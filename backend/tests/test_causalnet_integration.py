from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.assessment import MicroExpressionAnalyzeRequest


@pytest.mark.parametrize('values', [
    dict(onset_frame=1, apex_frame=4, offset_frame=8),
    dict(onset_frame=2, apex_frame=3),  # Existing MicroFlow contract stays valid.
])
def test_ordered_video_keyframes(values):
    assert MicroExpressionAnalyzeRequest(**values).model_dump()['apex_frame'] == values['apex_frame']


@pytest.mark.parametrize('values', [
    dict(offset_frame=8), dict(onset_frame=1, apex_frame=4, offset_frame=4),
    dict(onset_frame=1, apex_frame=4, offset_frame=3),
    dict(onset_frame=1, apex_frame=4, offset_frame=1801),
])
def test_invalid_triples_are_rejected(values):
    with pytest.raises(ValidationError):
        MicroExpressionAnalyzeRequest(**values)


def test_causalnet_missing_resources_are_never_ready(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.ml.micro_expression.adapter import MicroExpressionAnalyzer
    monkeypatch.setattr(settings, 'micro_expression_entry', 'causalnet')
    monkeypatch.setattr(settings, 'micro_expression_model_dir', str(tmp_path))
    status = MicroExpressionAnalyzer().load()
    assert not status.is_ready
    assert status.extra['adapter'] == 'causalnet'
    assert status.extra['offset_required'] is True


def test_author_feature_protocol_uses_strain_v_u_and_no_clipping():
    import numpy as np
    from app.ml.micro_expression.causalnet_preprocess import encode_flow, optical_strain
    yy, xx = np.mgrid[:224, :224].astype(np.float32)
    flow = np.stack([xx/20, yy/50], axis=-1)
    feature, direction = encode_flow(flow)
    assert feature.shape == direction.shape == (28, 28, 3)
    assert feature.dtype == direction.dtype == np.uint8
    # Constant strain is preserved; U/V vary independently, not clipped to +/-2.
    assert np.ptp(feature[..., 2]) > 200
    assert np.ptp(feature[..., 1]) > 200
    assert np.isfinite(optical_strain(flow[..., 0], flow[..., 1])).all()
    assert direction[..., 0].mean() < 20  # normalized positive u/v -> red/yellow quadrant


def test_four_region_inputs_match_supplied_training_crops():
    import numpy as np
    from app.ml.micro_expression.causalnet_preprocess import pack_regions
    images = np.arange(4*28*28*3, dtype=np.uint16).reshape(4,28,28,3).astype(np.uint8)
    got = pack_regions(list(images))
    expected = np.stack([np.concatenate([
        np.concatenate([im[4:18,2:16], im[14:28,3:17]],axis=1),
        np.concatenate([im[3:17,14:28], im[14:28,13:27]],axis=1)
    ],axis=0).transpose(2,0,1) for im in images]).astype(np.float32)
    np.testing.assert_array_equal(got, expected)


def test_failed_causalnet_analysis_keeps_no_upload_or_result(app_client, auth_headers, db, patient_payload, monkeypatch, tmp_path):
    from sqlalchemy import select, func
    from app.core.config import settings
    from app.core.errors import APIError, ErrorCode
    from app.db.models import MediaFile, MicroExpressionResult
    from app.services import assessment_service as service
    from app.ml.registry import ModelStatus, ModelState
    patient = app_client.post('/api/patients', json=patient_payload, headers=auth_headers).json()
    session = app_client.post(f"/api/patients/{patient['id']}/assessment-sessions",
        json={'session_type':'MICRO_EXPRESSION_ONLY'},headers=auth_headers).json()
    monkeypatch.setattr(settings, 'micro_expression_entry', 'causalnet')
    monkeypatch.setattr(settings, 'upload_dir', str(tmp_path/'uploads'))
    monkeypatch.setattr(service.micro_expression_analyzer, 'refresh_status', lambda:ModelStatus(
        name='micro_expression_model',version='test',state=ModelState.READY))
    def fail(*args, **kwargs):
        raise APIError(400, ErrorCode.INFERENCE_FAILED, '没有检测到人脸。')
    monkeypatch.setattr(service.micro_expression_analyzer, 'analyze', fail)
    result = app_client.post(f"/api/assessment-sessions/{session['id']}/micro-expression",
        headers=auth_headers,data=dict(onset_frame=1,apex_frame=4,offset_frame=8),
        files={'video':('bad.mp4', b'not a real video', 'video/mp4')})
    assert result.status_code == 400
    assert db.scalar(select(func.count()).select_from(MediaFile)) == 0
    assert db.scalar(select(func.count()).select_from(MicroExpressionResult)) == 0
    assert not list((tmp_path/'uploads').rglob('*.mp4'))


def test_database_failure_rolls_back_media_result_and_upload(app_client, auth_headers, db, patient_payload, monkeypatch, tmp_path):
    from sqlalchemy import select,func
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.config import settings
    from app.db.models import MediaFile,MicroExpressionResult
    from app.services import assessment_service as service
    from app.ml.registry import ModelStatus,ModelState
    patient=app_client.post('/api/patients',json=patient_payload,headers=auth_headers).json()
    session=app_client.post(f"/api/patients/{patient['id']}/assessment-sessions",
        json={'session_type':'MICRO_EXPRESSION_ONLY'},headers=auth_headers).json()
    monkeypatch.setattr(settings,'micro_expression_entry','causalnet')
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path/'uploads'))
    monkeypatch.setattr(service.micro_expression_analyzer,'refresh_status',lambda:ModelStatus(name='micro_expression_model',version='test',state=ModelState.READY))
    monkeypatch.setattr(service.micro_expression_analyzer,'analyze',lambda *a,**k:dict(
        model_name='TEST_ONLY',predicted_class='positive',tag_distribution=[dict(name='positive',score=1.)]))
    def fail_commit():raise SQLAlchemyError('test-only database failure')
    monkeypatch.setattr(db,'commit',fail_commit)
    with pytest.raises(SQLAlchemyError):
        service.analyze_micro_expression(db,session['id'],patient_id=patient['id'],
            original_filename='fixture.mp4',content=b'test-only',
            payload=MicroExpressionAnalyzeRequest(onset_frame=1,apex_frame=4,offset_frame=8))
    assert db.scalar(select(func.count()).select_from(MediaFile))==0
    assert db.scalar(select(func.count()).select_from(MicroExpressionResult))==0
    assert not list((tmp_path/'uploads').rglob('*.mp4'))


def test_worker_eof_never_keeps_ready_state(tmp_path):
    from app.ml.micro_expression.causalnet import CausalNetRuntime
    from app.ml.registry import ModelState
    runtime=CausalNetRuntime(tmp_path)
    runtime.status.state=ModelState.READY
    runtime.messages.put(None)
    with pytest.raises(RuntimeError):runtime._receive(.1)
    assert not runtime.status.is_ready


def test_optical_strain_matches_author_shift_and_forward_fill():
    import numpy as np
    import pandas as pd
    from app.ml.micro_expression.causalnet_preprocess import optical_strain
    rng=np.random.default_rng(17)
    u,v=rng.normal(size=(2,32,32)).astype(np.float32)
    ux=u-pd.DataFrame(u).shift(-1,axis=1)
    vy=v-pd.DataFrame(v).shift(-1,axis=0)
    uy=u-pd.DataFrame(u).shift(-1,axis=0)
    vx=v-pd.DataFrame(v).shift(-1,axis=1)
    expected=np.asarray(np.sqrt(ux**2+vy**2+.25*(uy+vx)**2).ffill(axis=1).ffill(axis=0))
    np.testing.assert_allclose(optical_strain(u,v),expected,atol=1e-6)


def test_video_preview_requires_authentication_and_writes_no_records(app_client,auth_headers,tmp_path,monkeypatch,db):
    from app.core.config import settings
    from app.db.models import AssessmentSession,MediaFile
    from sqlalchemy import select,func
    monkeypatch.setattr(settings,'output_dir',str(tmp_path/'outputs'))
    assert app_client.post('/api/micro-expression/video-info').status_code==401
    before=db.scalar(select(func.count()).select_from(AssessmentSession))
    response=app_client.post('/api/micro-expression/video-info',headers=auth_headers,
        files={'video':('invalid.mp4',b'broken','video/mp4')})
    assert response.status_code==400
    assert db.scalar(select(func.count()).select_from(AssessmentSession))==before
    assert db.scalar(select(func.count()).select_from(MediaFile))==0
    assert not list((tmp_path/'outputs').rglob('preview.mp4'))
