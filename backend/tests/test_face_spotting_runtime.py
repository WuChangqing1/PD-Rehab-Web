import io,json
from types import SimpleNamespace
from app.ml.micro_expression.causalnet import CausalNetRuntime
from app.ml.registry import ModelState


def test_spotting_worker_protocol_is_serialized_and_keeps_classifier_contract(tmp_path,monkeypatch):
    from app.ml.micro_expression import causalnet
    runtime=CausalNetRuntime(tmp_path)
    runtime.process=SimpleNamespace(stdin=io.StringIO(),poll=lambda:None)
    monkeypatch.setattr(causalnet,'uuid4',lambda:SimpleNamespace(hex='request-test'))
    candidate=dict(onset_frame=2,apex_frame=4,offset_frame=8)
    runtime.messages.put(dict(id='request-test',spotting=dict(candidates=[candidate],review_required=True)))
    result=runtime.spot(tmp_path/'video.mp4')
    request=json.loads(runtime.process.stdin.getvalue())
    assert request['operation']=='spot'
    assert request['id']=='request-test'
    assert result['candidates'][0]==candidate
    assert result['review_required']
