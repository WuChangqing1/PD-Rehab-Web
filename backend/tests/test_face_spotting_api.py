import hashlib
from pathlib import Path
import pytest
from pydantic import ValidationError
from sqlalchemy import select,func
from app.db.models import AssessmentSession,MediaFile,MicroExpressionResult
from app.schemas.assessment import MicroExpressionAnalyzeRequest


def test_spotting_requires_auth_and_never_creates_rows(app_client,auth_headers,db,monkeypatch,tmp_path):
    from app.core.config import settings
    from app.services.assessment_service import micro_expression_analyzer
    monkeypatch.setattr(settings,'output_dir',str(tmp_path/'outputs'))
    observed=[]
    def spot(path):
        observed.append(Path(path))
        assert Path(path).read_bytes()==b'local-only-video'
        return dict(algorithm_version='face-displacement-multiscale-v1',review_required=True,
            status='REVIEW_REQUIRED',candidates=[dict(id='candidate-1',onset_frame=2,apex_frame=4,offset_frame=8,
                onset_time=.04,apex_time=.12,offset_time=.28)],video_info={'frame_count':10},quality={})
    monkeypatch.setattr(micro_expression_analyzer,'spot',spot,raising=False)
    assert app_client.post('/api/micro-expression/keyframes').status_code==401
    response=app_client.post('/api/micro-expression/keyframes',headers=auth_headers,
        files={'video':('phone.mp4',b'local-only-video','video/mp4')})
    assert response.status_code==200,response.text
    value=response.json()
    assert value['review_required'] and value['candidates'][0]['selection_token']
    assert not observed[0].exists()
    for model in (AssessmentSession,MediaFile,MicroExpressionResult):
        assert db.scalar(select(func.count()).select_from(model))==0


def test_spotting_failure_also_removes_temporary_upload(app_client,auth_headers,monkeypatch,tmp_path):
    from app.core.config import settings
    from app.core.errors import APIError,ErrorCode
    from app.services.assessment_service import micro_expression_analyzer
    monkeypatch.setattr(settings,'output_dir',str(tmp_path/'outputs'))
    observed=[]
    def fail(path):
        observed.append(Path(path))
        raise APIError(400,ErrorCode.VIDEO_UNREADABLE,'bad video')
    monkeypatch.setattr(micro_expression_analyzer,'spot',fail,raising=False)
    response=app_client.post('/api/micro-expression/keyframes',headers=auth_headers,
        files={'video':('bad.mp4',b'broken','video/mp4')})
    assert response.status_code==400
    assert not observed[0].exists()


def test_spotting_rejects_suffix_and_size_before_inference(app_client,auth_headers,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'max_upload_size_mb',0)
    assert app_client.post('/api/micro-expression/keyframes',headers=auth_headers,
        files={'video':('x.txt',b'x','text/plain')}).status_code==422
    assert app_client.post('/api/micro-expression/keyframes',headers=auth_headers,
        files={'video':('x.mp4',b'x','video/mp4')}).status_code==413


def test_automatic_provenance_requires_confirmation_and_token():
    for extras in ({},{'review_confirmed':True},{'selection_token':'x'}):
        with pytest.raises(ValidationError):
            MicroExpressionAnalyzeRequest(onset_frame=2,apex_frame=4,offset_frame=8,
                selection_source='AUTO_REVIEWED',**extras)
    manual=MicroExpressionAnalyzeRequest(onset_frame=2,apex_frame=4,offset_frame=8)
    assert manual.selection_source=='MANUAL'


def test_selection_receipt_is_bound_to_video_frames_user_and_expiry(monkeypatch):
    from app.ml.micro_expression import selection_token as tokens
    from app.core.errors import APIError
    candidate=dict(onset_frame=2,apex_frame=4,offset_frame=8)
    digest=hashlib.sha256(b'video').hexdigest()
    token=tokens.issue_selection(candidate,digest,'operator',now=100)
    assert tokens.verify_selection(token,digest,[2,4,8],'operator',now=101)['algorithm_version']=='face-displacement-multiscale-v1'
    for args in [(digest,[2,5,8],'operator',101),('different',[2,4,8],'operator',101),
                 (digest,[2,4,8],'someone',101),(digest,[2,4,8],'operator',4000)]:
        with pytest.raises(APIError):tokens.verify_selection(token,*args[:3],now=args[3])
    with pytest.raises(APIError):tokens.verify_selection(token+'x',digest,[2,4,8],'operator',now=101)
