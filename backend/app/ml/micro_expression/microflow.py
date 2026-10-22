"""Adapter for the user-supplied MicroFlow-DA FG-LGL recognition source.

This is an onset/apex, three-class recognizer, not a seven-emotion temporal
model or PD classifier. Source is kept outside Git. No dummy landmarks,
random weights, automatic apex guesses or flow-method fallback are allowed.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import math
import sys
import types
from pathlib import Path

from app.core.config import settings
from app.core.errors import APIError, ErrorCode
from app.ml.registry import ModelState, ModelStatus

LABELS = ['negative', 'positive', 'surprise']
# Diagnostic tied to the exact supplied source, not to future corrected models.
DISCONNECTED_SOURCE_SHA256 = '797b82bb842e505ad464fdb8bba12ac4aa9261a13e46d859cc3891a4866bafa6'
SOURCE_FILES = ['recognition/__init__.py', 'recognition/fglgl.py',
    'recognition/flow_branch.py', 'recognition/magnet.py', 'recognition/vit_da.py',
    'recognition/au_local_global.py', 'recognition/dataset.py',
    'common/optical_flow.py', 'common/au_regions.py']


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_digest(source: Path) -> str:
    return hashlib.sha256(''.join(f'{name}:{sha256(source/name)}\n'
        for name in SOURCE_FILES).encode()).hexdigest()


def load_source(source: Path):
    """Isolate relative model imports; never add generic common to sys.path."""
    namespace = '_pd_microflow_' + source_digest(source)[:16]
    if namespace not in sys.modules:
        package = types.ModuleType(namespace)
        package.__path__ = [str(source)]
        sys.modules[namespace] = package
    return importlib.import_module(namespace + '.recognition.fglgl').FGLGL


def preprocessing_functions(source: Path) -> dict:
    """Reuse the supplied training transforms, excluding dataset/dummy code.

    Only the four pure transforms are compiled from the inspected source;
    dataset I/O and the upstream silent dummy-landmark fallback are never run.
    """
    import cv2
    import numpy as np
    namespace = '_pd_microflow_' + source_digest(source)[:16]
    if namespace not in sys.modules:
        package = types.ModuleType(namespace)
        package.__path__ = [str(source)]
        sys.modules[namespace] = package
    regions = importlib.import_module(namespace + '.common.au_regions')
    optical = importlib.import_module(namespace + '.common.optical_flow')
    names = {'align_face_by_eyes', 'crop_face', 'crop_au_regions', 'to_chw_normalized'}
    path = source / 'recognition/dataset.py'
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in functions} != names:
        raise ValueError('Unsupported MicroFlow preprocessing source')
    scope = dict(cv2=cv2, np=np, math=math, AU_REGION_9=regions.AU_REGION_9,
                 region_bbox_from_landmarks=regions.region_bbox_from_landmarks)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
    scope['optical'] = optical
    return scope


def read_keyframes(video: Path, onset: int | None, apex: int | None):
    import cv2
    if (isinstance(onset, bool) or isinstance(apex, bool)
            or not isinstance(onset, int) or not isinstance(apex, int)
            or not 1 <= onset < apex <= 1800):
        raise APIError(400, ErrorCode.VALIDATION_ERROR,
                       '请选择有效的起始帧与峰值帧（从 1 开始，峰值晚于起始帧，最多第 1800 帧）。')
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise APIError(400, ErrorCode.VIDEO_UNREADABLE, '视频不可解码。')
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(fps) or not 1 <= fps <= 240:
            raise APIError(400, ErrorCode.VIDEO_FPS_INVALID, '视频帧率无效。')
        selected = []
        # Decode sequentially: container keyframe seeking can return the wrong
        # frame. The 1800-frame bound also limits work on malformed containers.
        for index in range(1, apex + 1):
            ok, frame = capture.read()
            if not ok:
                raise APIError(400, ErrorCode.VIDEO_TOO_SHORT, '所选关键帧超过视频实际长度。')
            if frame.shape[0] > 2160 or frame.shape[1] > 3840:
                raise APIError(400, ErrorCode.VALIDATION_ERROR, '视频分辨率最高支持 3840×2160。')
            if index in (onset, apex): selected.append(frame)
        return selected[0], selected[1], fps
    finally:
        capture.release()


def normalize_probabilities(values) -> dict:
    if (not isinstance(values, list) or len(values) != 3
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) or not 0 <= x <= 1 for x in values)
            or abs(sum(values) - 1) > .001):
        raise ValueError('Invalid MicroFlow three-class probabilities')
    label = LABELS[max(range(3), key=values.__getitem__)]
    return dict(predicted_class=label, dominant_tag=label, pd_probability=None,
        labels=LABELS.copy(), probabilities=values,
        tag_distribution=[dict(name=name, score=values[i]) for i, name in enumerate(LABELS)],
        source='MODEL', clinical_eligible=False, task='MICRO_EXPRESSION_RECOGNITION')


def verify_temporal_response(model, cfg, device):
    """Load-time structural diagnostic only, never a clinical prediction.

    Supplied FGLGL prepends CLS after the last transformer and pools only CLS;
    its classifier consequently ignores both apex and flow. Reject a model
    whose output remains identical when those inputs change. The user's model
    source/architecture is never silently rewritten by this adapter.
    """
    import torch
    size, region = cfg['img_size'], cfg['region_size']
    onset = torch.zeros(1,3,size,size,device=device)
    regions = torch.zeros(1,9,3,region,region,device=device)
    with torch.inference_mode():
        baseline = model(onset,onset,onset,regions)[0]
        alternatives = [torch.ones_like(onset),
            torch.linspace(0,1,size,device=device).view(1,1,1,size).expand_as(onset)]
        responsive = any(not torch.allclose(baseline, model(onset,x,x,regions)[0],atol=1e-7,rtol=1e-5)
                         for x in alternatives)
    if not responsive: raise ValueError('TEMPORAL_BRANCH_DISCONNECTED: 分类器未响应峰值帧/光流变化；需修正并重新训练。')


class MicroFlowRuntime:
    def __init__(self, directory: Path, checkpoint: str = ''):
        self.directory = directory
        self.source = directory / 'source'
        self.checkpoint = settings._resolve(checkpoint) if checkpoint else directory / 'recognition.pth'
        self.manifest_path = directory / 'deployment.json'
        self.landmark_path = directory / 'shape_predictor_68_face_landmarks.dat'
        self.model = None
        self.status = self.inspect()

    def inspect(self) -> ModelStatus:
        source_present = all((self.source/name).is_file() for name in SOURCE_FILES)
        missing = []
        for name, present in [('source', source_present), ('checkpoint', self.checkpoint.is_file()),
            ('deployment_manifest', self.manifest_path.is_file()), ('landmark_68', self.landmark_path.is_file()),
            ('model_config', (self.directory/'model-config.yaml').is_file())]:
            if not present: missing.append(name)
        for module in ('torch', 'dlib', 'cv2', 'yaml'):
            if importlib.util.find_spec(module) is None: missing.append('dependency:' + module)
        extra = dict(adapter='microflow_da', source_present=source_present,
            labels=LABELS.copy(), live_supported=False, keyframes_required=True,
            missing=missing, checkpoint_present=self.checkpoint.is_file(),
            deployment_manifest_present=self.manifest_path.is_file())
        if source_present:
            extra['source_sha256'] = source_digest(self.source)
            extra['known_source_issue'] = ('TEMPORAL_BRANCH_DISCONNECTED'
                if extra['source_sha256'] == DISCONNECTED_SOURCE_SHA256 else None)
        detail = ('MicroFlow-DA 权重已安置，推理资源尚未齐备，暂不可用。'
            if source_present and missing and self.checkpoint.is_file() else
            'MicroFlow-DA 源码已接入，等待训练权重和推理资源。' if source_present and missing else
            'MicroFlow-DA 推理资源需在启动时加载并校验。')
        if self.checkpoint.is_file() and extra.get('known_source_issue'):
            detail += '现有源码的时序分支校验未通过。'
        return ModelStatus(name='micro_expression_model', version='microflow-da-pending',
            state=ModelState.MODEL_NOT_CONFIGURED if missing else ModelState.UNAVAILABLE,
            detail=detail, extra=extra)

    def verify_manifest(self) -> dict:
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        if (manifest.get('schema_version') != 1 or manifest.get('labels') != LABELS
                or manifest.get('training_verified') is not True
                or manifest.get('channel_order') != 'BGR'
                or manifest.get('flow_method') not in ('tvl1', 'farneback')):
            raise ValueError('Unverified MicroFlow training / preprocessing contract')
        for key, path in [('checkpoint_sha256', self.checkpoint),
                          ('landmark_sha256', self.landmark_path),
                          ('config_sha256', self.directory/'model-config.yaml')]:
            if manifest.get(key) != sha256(path): raise ValueError('MicroFlow hash mismatch: ' + key)
        if manifest.get('source_sha256') != source_digest(self.source):
            raise ValueError('MicroFlow source does not match training manifest')
        return manifest

    def load(self) -> ModelStatus:
        self.status = self.inspect()
        if self.status.extra['missing']: return self.status
        try:
            import cv2
            import dlib
            import torch
            import yaml
            self.manifest = self.verify_manifest()
            self.config = yaml.safe_load((self.directory/'model-config.yaml').read_text(encoding='utf-8'))
            cfg = self.config['model']
            if (cfg.get('num_classes') != 3 or cfg.get('in_channels') != 3
                    or cfg.get('num_regions') != 9 or not 32 <= cfg.get('img_size', 0) <= 224
                    or not 16 <= cfg.get('region_size', 0) <= 64):
                raise ValueError('Unsupported FG-LGL dimensions')
            if self.manifest['flow_method'] == 'tvl1' and not hasattr(cv2, 'optflow'):
                raise ValueError('Training requires OpenCV TV-L1; fallback is forbidden')
            requested = settings.micro_expression_device.strip() or 'cpu'
            if requested.startswith('cuda') and not torch.cuda.is_available():
                raise ValueError('Requested CUDA is unavailable')
            self.device = torch.device(requested)
            torch.set_num_threads(settings.torch_num_threads)
            model = load_source(self.source)(cfg)
            state = torch.load(self.checkpoint, map_location='cpu', weights_only=True)
            if isinstance(state, dict) and 'state_dict' in state: state = state['state_dict']
            model.load_state_dict(state, strict=True)
            self.predictor = dlib.shape_predictor(str(self.landmark_path))
            self.detector = dlib.get_frontal_face_detector()
            self.transforms = preprocessing_functions(self.source)
            self.model = model.to(self.device).eval()
            verify_temporal_response(self.model, cfg, self.device)
            self.status.state = ModelState.READY
            self.status.version = 'microflow-da-' + self.manifest['checkpoint_sha256'][:12]
            self.status.device = str(self.device)
            self.status.detail = 'MicroFlow-DA 三分类视频识别已加载；不支持七分类实时情绪或疾病预测。'
            self.status.extra.update(checkpoint_sha256=self.manifest['checkpoint_sha256'],
                source_sha256=self.manifest['source_sha256'], flow_method=self.manifest['flow_method'])
        except Exception as exc:
            self.model = None
            self.status.state = ModelState.LOAD_FAILED
            self.status.detail = f'MicroFlow-DA 加载失败：{type(exc).__name__}: {exc}'
        return self.status

    def landmarks(self, frame):
        import cv2
        import numpy as np
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector(gray, 1)
        if len(faces) != 1:
            raise APIError(400, ErrorCode.INFERENCE_FAILED, '每个关键帧必须清晰检测到且仅包含一张人脸。')
        shape = self.predictor(gray, faces[0])
        points = np.asarray([(p.x, p.y) for p in shape.parts()], dtype=np.float32)
        if points.shape != (68, 2) or not np.isfinite(points).all() or np.ptp(points[:, 0]) < 10 or np.ptp(points[:, 1]) < 10:
            raise APIError(400, ErrorCode.INFERENCE_FAILED, '无法获得有效的 68 点人脸关键点。')
        return points

    def prepare(self, onset, apex):
        import cv2
        import numpy as np
        t, cfg = self.transforms, self.config['model']
        aligned, points = t['align_face_by_eyes'](onset, self.landmarks(onset))
        peak, peak_points = t['align_face_by_eyes'](apex, self.landmarks(apex))
        first, _ = t['crop_face'](aligned, points)
        second, _ = t['crop_face'](peak, peak_points)
        if not first.size or not second.size:
            raise APIError(400, ErrorCode.INFERENCE_FAILED, '人脸裁剪为空，无法分析。')
        size = cfg['img_size']
        first, second = cv2.resize(first, (size, size)), cv2.resize(second, (size, size))
        if self.manifest['flow_method'] == 'tvl1':
            flow = t['optical'].tvl1_optical_flow(first, second)
        else:
            flow = cv2.calcOpticalFlowFarneback(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY).astype(np.float32),
                cv2.cvtColor(second, cv2.COLOR_BGR2GRAY).astype(np.float32), None,
                .5, 5, 15, 3, 5, 1.2, 0)
        representation = np.concatenate([flow, t['optical'].optical_strain(flow)[..., None]], axis=-1)
        for _, _, indices in t['AU_REGION_9']:
            x1,y1,x2,y2 = t['region_bbox_from_landmarks'](points,indices,
                self.config.get('data', {}).get('expand_ratio', .2))
            if min(aligned.shape[1],x2)<=max(0,x1) or min(aligned.shape[0],y2)<=max(0,y1):
                raise APIError(400, ErrorCode.INFERENCE_FAILED, 'AU 区域不完整，无法分析。')
        regions = t['crop_au_regions'](aligned, points, cfg['region_size'],
                                      self.config.get('data', {}).get('expand_ratio', .2))
        arrays = [t['to_chw_normalized'](first), t['to_chw_normalized'](second),
            representation.transpose(2, 0, 1).astype(np.float32),
            np.stack([t['to_chw_normalized'](r) for r in regions])]
        if any(not np.isfinite(a).all() for a in arrays): raise ValueError('Invalid preprocessing values')
        return arrays

    def infer(self, video: Path, onset_frame: int | None, apex_frame: int | None) -> dict:
        import torch
        from app.jobs.gpu_inference import inference_manager
        if self.model is None: raise ValueError('MicroFlow has not been loaded')
        onset, apex, fps = read_keyframes(video, onset_frame, apex_frame)
        with inference_manager.acquire_sync(), torch.inference_mode():
            tensors = [torch.from_numpy(a).unsqueeze(0).to(self.device) for a in self.prepare(onset, apex)]
            logits, _, _ = self.model(*tensors)
            if logits.shape != (1, 3) or not torch.isfinite(logits).all():
                raise ValueError('Invalid FG-LGL logits')
            result = normalize_probabilities(torch.softmax(logits, dim=1)[0].cpu().tolist())
        return result | dict(model_name='MicroFlow-DA/FG-LGL', model_version=self.status.version,
            quality_json=dict(status='VALID_KEYFRAMES', onset_frame=onset_frame, apex_frame=apex_frame,
                fps=fps, landmark_provider='dlib68', flow_method=self.manifest['flow_method'],
                checkpoint_sha256=self.manifest['checkpoint_sha256'], clinical_eligible=False))
