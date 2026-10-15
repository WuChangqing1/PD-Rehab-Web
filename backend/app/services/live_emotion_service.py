"""Optional temporal video transport. No verified temporal model is supplied.

FPS, window, image size, optical flow, label mapping and latency remain unknown.
MediaRecorder chunks are a continuous container stream, not independent movies;
an eventual adapter must retain decoder state and validate these requirements.
"""
from __future__ import annotations
import math
import time
from collections import OrderedDict
from app.core.config import settings

LABELS = ['sadness', 'other', 'disgust', 'happiness', 'fear', 'surprise', 'anger']
MAX_BYTES = 2 * 1024 * 1024
_latest: OrderedDict[str, dict] = OrderedDict()

def capabilities():
    return dict(status='MODEL_NOT_CONFIGURED', capture_required=False,
                model_name='micro_expression_model', model_version='unknown',
                requirements=dict(fps=None, window_ms=None, width=None, height=None,
                                  optical_flow=None, continuous=True), labels=LABELS)

def simulation_enabled():
    return settings.emotion_simulation_mode and settings.app_env in ('development', 'test')

def simulation_result(session_id, patient_id, now_ms=None):
    now = int(time.time()*1000) if now_ms is None else now_ms
    return dict(type='result', session_id=session_id, patient_id=patient_id,
                capture_timestamp_ms=None, result_timestamp_ms=now, seq=0,
                model_name='development-fixture', model_version='1', labels=LABELS.copy(),
                probabilities=[.05,.35,.05,.35,.05,.10,.05], quality='GOOD',
                source='SIMULATED', inference_latency_ms=None, clinical_eligible=False)

def remember_result(result):
    previous=(_latest.get(result['session_id']) or {}).get('quality_statistics',{})
    result={**result,'quality_statistics':{'results':previous.get('results',0)+1,'low_quality':previous.get('low_quality',0)+(0 if result.get('quality')=='GOOD' else 1),'last_latency_ms':result.get('inference_latency_ms')}}
    _latest[result['session_id']] = result
    _latest.move_to_end(result['session_id'])
    while len(_latest) > 128: _latest.popitem(last=False)

def get_latest_result(session_id):
    result = _latest.get(session_id)
    if result and 0 <= time.time()*1000-result['result_timestamp_ms'] <= 30000:
        return result.copy()
    _latest.pop(session_id, None)
    return None

class SongDifficultyPolicy:
    @staticmethod
    def decide(bpm, segment_1_completed, result=None, simulation_mode=False, now_ms=None):
        now = time.time()*1000 if now_ms is None else now_ms
        probabilities = (result or {}).get('probabilities')
        valid = bool(result and result.get('source') == 'SIMULATED' and result.get('quality') == 'GOOD'
                     and result.get('labels') == LABELS and isinstance(probabilities, list) and len(probabilities) == 7
                     and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and 0 <= x <= 1 for x in probabilities)
                     and abs(sum(probabilities)-1) <= .001
                     and isinstance(result.get('result_timestamp_ms'), (int,float))
                     and 0 <= now-result['result_timestamp_ms'] <= 30000)
        upgrade = simulation_mode and segment_1_completed and valid and probabilities[1]+probabilities[3] > .5
        after = min(120, 80 if bpm < 80 else 100 if bpm < 100 else bpm+10) if upgrade else bpm
        return dict(bpm_after=after, difficulty_before=bpm, difficulty_after=after,
                    trigger_source='SIMULATED' if upgrade else 'NONE',
                    emotion_probability_snapshot=probabilities if upgrade else None,
                    adjustment_reason='DEVELOPMENT_SIMULATION_ONLY' if upgrade else 'NO_VALID_SIMULATION',
                    policy_version='song-difficulty-v1')

class StreamGuard:
    """Exactly one declared binary message before ACK; never buffer a queue."""
    def __init__(self):
        self.pending = None
        self.seq = -1
        self.last = -math.inf

    def begin(self, metadata, now=None):
        now = time.monotonic() if now is None else now
        if self.pending is not None: raise ValueError('BACKPRESSURE')
        if now-self.last < .5: raise ValueError('RATE_LIMIT')
        if metadata.get('seq') != self.seq+1: raise ValueError('SEQUENCE')
        size, duration, stamp = (metadata.get(k) for k in ('byte_length','duration_ms','capture_timestamp_ms'))
        if not isinstance(size,int) or not 0 < size <= MAX_BYTES: raise ValueError('SIZE_LIMIT')
        if not isinstance(duration,(int,float)) or not 100 <= duration <= 5000: raise ValueError('DURATION_LIMIT')
        if not isinstance(stamp,(int,float)) or not math.isfinite(stamp): raise ValueError('TIMESTAMP')
        self.pending, self.last = metadata, now

    def finish(self, size):
        if self.pending is None or size != self.pending['byte_length']: raise ValueError('SIZE_MISMATCH')
        self.seq = self.pending['seq']
        self.pending = None

# An integrator must supply a verified, stateful continuous-container adapter.
# No adapter is inferred from the presence of checkpoint files.
temporal_adapter = None


def verified_adapter():
    adapter = temporal_adapter
    if adapter is None:
        return None
    requirements = adapter.requirements
    if (adapter.labels != LABELS or requirements.get('continuous') is not True
            or not isinstance(requirements.get('optical_flow'), bool)
            or any(not isinstance(requirements.get(key), (int, float))
                   or not math.isfinite(requirements[key]) or not low <= requirements[key] <= high
                   for key, low, high in [('fps',1,240),('window_ms',100,10000),('width',16,1920),('height',16,1080)])):
        raise ValueError('UNVERIFIED_TEMPORAL_CONTRACT')
    return adapter


def infer_chunk(adapter, state, chunk, metadata):
    from app.jobs.gpu_inference import inference_manager
    started = time.perf_counter()
    with inference_manager.acquire_sync():
        raw = adapter.infer(state, chunk, metadata)
    probabilities = raw.get('probabilities')
    quality = raw.get('quality', 'UNKNOWN')
    if probabilities is not None and (not isinstance(probabilities,list) or len(probabilities)!=7
            or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or not 0<=x<=1 for x in probabilities)
            or abs(sum(probabilities)-1)>.001):
        raise ValueError('INVALID_MODEL_OUTPUT')
    if quality != 'GOOD':
        probabilities = None
    return dict(probabilities=probabilities, quality=quality,
                inference_latency_ms=round((time.perf_counter()-started)*1000))
