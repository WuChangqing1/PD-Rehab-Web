"""Persistent CPU model process. JSON lines on stdin/stdout; logs on stderr."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def send(value):
    print(json.dumps(value,ensure_ascii=False,allow_nan=False),flush=True)


def main():
    manifest_path=Path(sys.argv[1]).resolve()
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    def resource(key):
        value=Path(manifest[key])
        return value if value.is_absolute() else manifest_path.parent/value
    if manifest.get('dependency_path'):
        sys.path.insert(0,str(resource('dependency_path')))
    import torch
    from causalnet_preprocess import FaceAligner,VideoInputError,prepare_video,PREPROCESS_VERSION
    torch.set_num_threads(min(max(int(manifest.get('threads',4)),1),8))
    checkpoint,source=resource('checkpoint'),resource('source_model')
    if sha256(checkpoint)!=manifest['checkpoint_sha256'] or sha256(source)!=manifest['source_sha256']:
        raise ValueError('CausalNet source/checkpoint hash mismatch')
    spec=importlib.util.spec_from_file_location('_pd_causalnet_'+manifest['source_sha256'][:12],source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Strict assignment supplies every parameter/buffer before any forward.
    # Skip filling large CPU tensors with random values. The supplied model
    # constructs tiny masks using Python scalar conditions, so meta-device
    # construction is incompatible with that unchanged upstream source.
    initializers={name:getattr(torch.nn.init,name) for name in ('kaiming_uniform_','uniform_')}
    try:
        for name in initializers:
            setattr(torch.nn.init,name,lambda tensor,*args,**kwargs:tensor)
        model=module.CausalNet(image_size=28,patch_size=7,dim=256,heads=3,num_hierarchies=3,
            block_repeats=(3,3,7),num_classes=3,gamma=.3)
    finally:
        for name,initializer in initializers.items():
            setattr(torch.nn.init,name,initializer)
    state=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
    model.load_state_dict(state,strict=True,assign=True)
    if not all(torch.isfinite(value).all() for value in state.values()):
        raise ValueError('Non-finite checkpoint')
    model.eval()
    with torch.inference_mode():
        baseline=model(torch.zeros(1,4,3,28,28))
        different=model(torch.arange(4*3*28*28).remainder(256).float().reshape(1,4,3,28,28))
        if not torch.isfinite(baseline).all() or torch.allclose(baseline,different):
            raise ValueError('Model input response check failed')
    aligner=FaceAligner()
    send({'ready':True,'model_version':'causalnet-'+manifest['checkpoint_sha256'][:12],
          'preprocessing_version':PREPROCESS_VERSION,'torch':torch.__version__})
    try:
        for line in sys.stdin:
            request={}
            try:
                if len(line)>8192:
                    raise ValueError('Request too large')
                request=json.loads(line)
                if request.get('operation')=='close':
                    break
                video=Path(request['video'])
                inputs,quality=prepare_video(video,*request['frames'],aligner)
                with torch.inference_mode():
                    logits=model(torch.from_numpy(inputs).unsqueeze(0))
                    if logits.shape!=(1,3) or not torch.isfinite(logits).all():
                        raise ValueError('Invalid logits')
                    probabilities=logits.softmax(-1)[0].tolist()
                send({'id':request['id'],'probabilities':probabilities,'quality':quality})
            except VideoInputError as exc:
                send({'id':request.get('id'),'error':str(exc),'input_error':True})
            except Exception as exc:
                print(f'CausalNet inference error: {type(exc).__name__}',file=sys.stderr,flush=True)
                send({'id':request.get('id'),'error':'视频模型推理失败，未生成分析结果。','input_error':False})
    finally:
        aligner.close()


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(f'CausalNet startup failed: {type(exc).__name__}: {exc}',file=sys.stderr,flush=True)
        send({'ready':False,'error':f'{type(exc).__name__}: {exc}'})
        sys.exit(1)
