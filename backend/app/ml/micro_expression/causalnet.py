"""Web-facing CausalNet runtime; optional ML libraries stay in a worker."""
from __future__ import annotations

import atexit
from collections import deque
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from uuid import uuid4

from app.core.errors import APIError,ErrorCode
from app.ml.registry import ModelStatus,ModelState
from app.ml.micro_expression.microflow import normalize_probabilities,sha256


class CausalNetRuntime:
    def __init__(self,directory:Path,checkpoint:str=''):
        self.directory=directory
        self.checkpoint_override=checkpoint
        self.manifest_path=directory/'causalnet.json'
        self.lock=threading.Lock()
        self.process=None
        self.messages=queue.Queue()
        self.logs=deque(maxlen=20)
        self.status=self.inspect()

    def inspect(self):
        missing=[]
        if not self.manifest_path.is_file():
            missing.append('causalnet.json')
        return ModelStatus(name='micro_expression_model',version='causalnet-pending',
            state=ModelState.MODEL_NOT_CONFIGURED if missing else ModelState.UNAVAILABLE,
            detail='CausalNet 尚未加载或资源未齐备。',extra=dict(adapter='causalnet',
            live_supported=False,keyframes_required=True,offset_required=True,
            automatic_keyframes_supported=True,automatic_keyframes_review_required=True,
            labels=['negative','positive','surprise'],research_only=True,
            training_contract_verified=False,missing=missing))

    def close(self):
        atexit.unregister(self.close)
        process,self.process=self.process,None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=3)
        if process is not None:
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream:
                    stream.close()

    def _receive(self,timeout):
        try:
            response=self.messages.get(timeout=timeout)
            if response is None:
                self.status.state=ModelState.LOAD_FAILED
                self.close()
                raise RuntimeError('模型工作进程已退出。')
            return response
        except queue.Empty:
            self.close()
            self.status.state=ModelState.LOAD_FAILED
            self.status.detail='CausalNet 工作进程超时，请重新加载。'
            raise RuntimeError(self.status.detail)

    def load(self):
        self.status=self.inspect()
        if self.status.extra['missing']:
            return self.status
        try:
            manifest=json.loads(self.manifest_path.read_text(encoding='utf-8-sig'))
            if manifest.get('schema_version')!=1 or manifest.get('labels')!=['negative','positive','surprise']:
                raise ValueError('Invalid CausalNet manifest')
            if self.checkpoint_override:
                raise ValueError('Set checkpoint and hash together in causalnet.json')
            def resource(key):
                path=Path(manifest[key]);return path if path.is_absolute() else self.directory/path
            for key,hash_key in [('source_model','source_sha256'),('checkpoint','checkpoint_sha256')]:
                if sha256(resource(key))!=manifest[hash_key]:
                    raise ValueError('Resource hash mismatch: '+key)
            executable=str(resource('python_executable')) if manifest.get('python_executable') else sys.executable
            worker=Path(__file__).with_name('causalnet_worker.py')
            self.process=subprocess.Popen([executable,'-u',str(worker),str(self.manifest_path)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',bufsize=1,
                env=os.environ|{'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'},
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            process=self.process
            def read_stdout():
                try:
                    for line in process.stdout:
                        if len(line)>65536:
                            break
                        try:self.messages.put(json.loads(line))
                        except ValueError:break
                finally:self.messages.put(None)
            def read_stderr():
                try:
                    for line in process.stderr:
                        self.logs.append(line.rstrip()[:1024])
                except (ValueError,OSError):
                    pass
            threading.Thread(target=read_stdout,daemon=True).start()
            threading.Thread(target=read_stderr,daemon=True).start()
            reply=self._receive(90)
            if reply.get('ready') is not True:
                raise ValueError(reply.get('error','Worker startup failed'))
            self.status.state=ModelState.READY
            self.status.version=reply['model_version'];self.status.device='cpu'
            self.status.detail='CausalNet 三分类视频分析已加载。'
            self.status.extra.update(checkpoint_present=True,checkpoint_sha256=manifest['checkpoint_sha256'],
                source_sha256=manifest['source_sha256'],preprocessing_version=reply['preprocessing_version'],
                worker_torch_version=reply.get('torch'))
            atexit.register(self.close)
        except Exception as exc:
            self.close()
            self.status.state=ModelState.LOAD_FAILED
            self.status.detail=f'CausalNet 加载失败：{type(exc).__name__}: {exc}'
        return self.status

    def _exchange(self,video:Path,operation,frames=None):
        from app.jobs.gpu_inference import inference_manager
        with self.lock,inference_manager.acquire_sync():
            if self.process is None or self.process.poll() is not None:
                self.status.state=ModelState.LOAD_FAILED
                raise APIError(503,ErrorCode.MODEL_UNAVAILABLE,'模型工作进程已退出，请重新加载。')
            ident=uuid4().hex
            try:
                request=dict(id=ident,operation=operation,video=str(video.resolve()))
                if frames is not None:request['frames']=frames
                self.process.stdin.write(json.dumps(request)+'\n')
                self.process.stdin.flush()
            except (BrokenPipeError,OSError,ValueError) as exc:
                self.status.state=ModelState.LOAD_FAILED
                self.close()
                raise APIError(503,ErrorCode.MODEL_UNAVAILABLE,'模型工作进程已退出，请重新加载。') from exc
            reply=self._receive(120)
            if reply.get('id')!=ident:
                self.close();self.status.state=ModelState.LOAD_FAILED
                raise ValueError('CausalNet worker response mismatch')
            if 'error' in reply:
                raise APIError(400 if reply.get('input_error') else 503,ErrorCode.INFERENCE_FAILED,reply['error'])
            return reply

    def spot(self,video:Path):
        return self._exchange(video,'spot')['spotting']

    def infer(self,video:Path,onset,apex,offset=None):
        from app.ml.micro_expression.causalnet_preprocess import validate_frames,VideoInputError
        try:validate_frames(onset,apex,offset)
        except VideoInputError as exc:raise APIError(400,ErrorCode.VALIDATION_ERROR,str(exc)) from exc
        reply=self._exchange(video,'infer',[onset,apex,offset])
        raw=normalize_probabilities(reply['probabilities'])
        return raw|dict(model_name='CausalNet',model_version=self.status.version,
            quality_json=reply['quality']|dict(checkpoint_sha256=self.status.extra['checkpoint_sha256'],
            source_sha256=self.status.extra['source_sha256'],training_contract_verified=False))
