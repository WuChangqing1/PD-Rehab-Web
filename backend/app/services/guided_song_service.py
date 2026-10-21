"""Authoritative score replay and append-only snapshot persistence."""
import io
import json
import wave
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.errors import conflict, not_found, forbidden, bad_request
from app.db.base import utcnow
from app.db.models import Patient, Baseline
from app.db.models.guided_song import GuidedSongSession

MELODY = [60,62,64,60,60,62,64,60,64,65,67,64,65,67,67,69,67,65,64,60,67,69,67,65,64,60,60,67,60,60,67,60]
BPM = {'BEGINNER':60,'INTERMEDIATE':80,'ADVANCED':100}


def analyze_events(events):
    notes=[]
    current=None
    active={}
    used=set()
    paused=False
    last=-1
    next_note=0
    for seq,e in enumerate(events):
        kind=e['type']; idx=e['note_index']; t=e['time_ms']
        if e['seq'] != seq or t < last or e['segment_index'] != (1 if idx<14 else 2):
            raise conflict('事件序号、时钟或段落不合法。')
        last=t
        if kind=='UP':
            down=active.pop(e.get('press_id'),None)
            if down is None or down['midi']!=e['midi'] or down['note_index']!=idx:
                raise conflict('松键必须与原始按键匹配。')
            note=notes[idx]
            if note.get('correct_press_id')==e['press_id']:
                note.update(key_up_time_ms=t,hold_duration_ms=t-down['time_ms'])
            continue
        if kind=='CUE':
            if paused or current is not None or idx!=next_note:
                raise conflict('提示必须严格按曲谱逐音前进。')
            current=dict(note_index=idx,segment_index=e['segment_index'],expected_midi=MELODY[idx],
                expected_note={60:'C',62:'D',64:'E',65:'F',67:'G',69:'A',71:'B'}[MELODY[idx]],
                cue_onset_time_ms=t,first_attempt_time_ms=None,correct_press_time_ms=None,
                response_latency_ms=None,first_attempt_latency_ms=None,attempt_count=0,wrong_attempt_count=0,
                is_first_attempt_correct=False,was_skipped=False,key_down_time_ms=None,key_up_time_ms=None,hold_duration_ms=None)
            notes.append(current)
            continue
        if current is None or idx!=current['note_index']:
            raise conflict('事件没有对应的当前提示。')
        if kind=='PAUSE':
            if paused: raise conflict('不能重复暂停。')
            paused=True
        elif kind=='RESUME':
            if not paused: raise conflict('当前没有暂停。')
            paused=False
        elif paused:
            raise conflict('暂停期间不能按键或跳过。')
        elif kind=='SKIP':
            current['was_skipped']=True
            current['resolved_time_ms']=t
            current=None; next_note+=1
        elif kind=='DOWN':
            pid=e.get('press_id')
            if not pid or pid in used or any(x['midi']==e['midi'] for x in active.values()):
                raise conflict('重复按下或复用按键标识。')
            used.add(pid); active[pid]=e
            correct=e['midi']==MELODY[idx]
            current['attempt_count']+=1
            if current['attempt_count']==1:
                current.update(first_attempt_time_ms=t,first_attempt_latency_ms=t-current['cue_onset_time_ms'],is_first_attempt_correct=correct)
            if correct:
                current.update(correct_press_time_ms=t,response_latency_ms=t-current['cue_onset_time_ms'],key_down_time_ms=t,correct_press_id=pid,resolved_time_ms=t)
                current=None; next_note+=1
            else: current['wrong_attempt_count']+=1
        else: raise conflict('未知事件。')
    attempted=sum(n['attempt_count']>0 for n in notes)
    attempts=sum(n['attempt_count'] for n in notes)
    complete=sum(n['correct_press_time_ms'] is not None for n in notes)
    metrics=dict(first_attempt_accuracy=sum(n['is_first_attempt_correct'] for n in notes)/attempted if attempted else None,
        total_attempt_accuracy=complete/attempts if attempts else None,wrong_press_count=sum(n['wrong_attempt_count'] for n in notes),
        skip_count=sum(n['was_skipped'] for n in notes),completed_notes=complete,total_notes=32,
        completion_rate=complete/32,attempted_notes=attempted,total_attempts=attempts,
        resolved_notes=next_note,active_press_count=len(active),paused=paused,metrics_version='guided-song-1')
    latencies=[n['response_latency_ms'] for n in notes if n['response_latency_ms'] is not None]
    metrics['mean_response_latency_ms']=sum(latencies)/len(latencies) if latencies else None
    return notes,metrics


def get_session(db, session_id, owner_id, lock=False):
    if lock:
        # Actual write serializes SQLite too; SELECT FOR UPDATE alone is a no-op there.
        db.execute(update(GuidedSongSession).where(GuidedSongSession.id==session_id,GuidedSongSession.owner_id==owner_id).values(status=GuidedSongSession.status))
    row=db.get(GuidedSongSession,session_id, populate_existing=True)
    if not row: raise not_found('曲目训练不存在。')
    if row.owner_id!=owner_id: raise forbidden('无权访问此训练。')
    return row


def create_session(db, payload, owner_id):
    from app.services.active_training_service import lock_patient,ensure_free
    lock_patient(db,payload.patient_id)
    patient=db.get(Patient,payload.patient_id)
    if not patient or patient.is_deleted: raise not_found('患者不存在。')
    requested=payload.model_dump()
    existing=db.scalar(select(GuidedSongSession).where(GuidedSongSession.owner_id==owner_id,GuidedSongSession.client_request_id==payload.client_request_id).with_for_update().execution_options(populate_existing=True))
    if existing:
        if existing.config['request']!=requested: raise conflict('重试请求参数不同。')
        return existing
    if payload.is_simulation:
        from app.core.config import get_settings
        settings=get_settings()
        if not getattr(settings,'emotion_simulation_mode',False) or settings.app_env not in ('development','test') or payload.input_source!='SYNTHETIC_SELFTEST':
            raise forbidden('模拟仅限明确标记的开发自测。')
    ensure_free(db,payload.patient_id)
    bpm=BPM[payload.initial_difficulty]
    baseline=db.scalar(select(Baseline).where(Baseline.patient_id==patient.id,Baseline.baseline_type=='PIANO_CALIBRATION',Baseline.is_active.is_(True)).order_by(Baseline.created_at.desc()))
    baseline_id=None
    if baseline and payload.input_source=='HUMAN_KEYBOARD':
        snap=json.loads(baseline.snapshot_json)
        if (snap.get('quality_metadata') or {}).get('input_source')=='HUMAN_KEYBOARD':
            baseline_id=baseline.id
            if isinstance(snap.get('baseline_accuracy'),(int,float)) and snap['baseline_accuracy']<0.7:
                bpm=60
    difficulty=next(k for k,v in BPM.items() if v==bpm)
    config={**requested,'request':requested,'segment_1_difficulty':difficulty,'segment_2_difficulty':None,'final_difficulty':difficulty,
        'segment_1_bpm':bpm,'segment_2_bpm':None,'baseline_id':baseline_id,'difficulty_adjustment':None}
    row=GuidedSongSession(patient_id=patient.id,owner_id=owner_id,client_request_id=payload.client_request_id,config=config)
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        return create_session(db,payload,owner_id)
    db.refresh(row)
    return row


def store_events(db,row,payload):
    raw=[e.model_dump(exclude_none=True) for e in payload.events]
    if raw==row.events: return row
    if row.status!='ACTIVE': raise conflict('已结束的训练不可修改事件。')
    if raw[:len(row.events)]!=row.events: raise conflict('原始事件只能追加，不得覆盖。')
    notes,metrics=analyze_events(raw)
    if any(e['segment_index']==2 for e in raw) and row.config['segment_2_bpm'] is None:
        raise conflict('第二段必须先完成段间策略。')
    row.events=raw
    row.result={'notes':notes,'metrics':metrics}
    db.commit(); db.refresh(row)
    return row


def segment_two(db,row):
    if row.config['segment_2_bpm'] is not None: return row
    notes,metrics=analyze_events(row.events)
    if row.status!='ACTIVE' or metrics['resolved_notes']!=14 or metrics['active_press_count'] or metrics['paused']:
        raise conflict('请先完成第一段并松开所有琴键。')
    before=row.config['segment_1_bpm']; after=before
    if metrics['skip_count'] or (metrics['total_attempt_accuracy'] or 0)<0.7:
        after=max(60,before-20)
    adjustment=dict(difficulty_before=row.config['segment_1_difficulty'],difficulty_after=next(k for k,v in BPM.items() if v==after),
        bpm_before=before,bpm_after=after,trigger_source='KEY_PERFORMANCE',emotion_probability_snapshot=None,
        adjustment_reason='PERFORMANCE_SLOW_DOWN' if after<before else 'MAINTAIN_NO_VALIDATED_EMOTION_POLICY',policy_version='guided-song-1')
    from app.services.live_emotion_service import simulation_enabled
    if row.is_simulation and simulation_enabled():
        from app.services.live_emotion_service import SongDifficultyPolicy, simulation_result
        decision=SongDifficultyPolicy.decide(before,segment_1_completed=True,result=simulation_result(row.id,row.patient_id),simulation_mode=True)
        adjustment=decision
        after=min(120,decision['bpm_after'])
    difficulty='BEGINNER' if after<80 else 'INTERMEDIATE' if after<100 else 'ADVANCED'
    row.config={**row.config,'segment_2_bpm':after,'segment_2_difficulty':difficulty,'final_difficulty':difficulty,'difficulty_adjustment':adjustment}
    db.commit(); db.refresh(row)
    return row


def finish(db,row,cancel=False):
    target='CANCELLED' if cancel else 'COMPLETED'
    if row.status==target: return row
    if row.status!='ACTIVE': raise conflict('训练已结束。')
    notes,metrics=analyze_events(row.events)
    if not cancel and (metrics['resolved_notes']!=32 or metrics['active_press_count'] or metrics['paused']):
        raise conflict('请完成两段并松开所有琴键。')
    row.result={'notes':notes,'metrics':metrics}
    from app.services.live_emotion_service import get_latest_result
    latest=get_latest_result(row.id)
    if latest:
        row.config={**row.config,'emotion_audit':{**latest,'clinical_eligible':False}}
    row.status=target; row.completed_at=utcnow()
    db.commit(); db.refresh(row)
    return row


def save_audio(db,row,data,render_version):
    if row.status!='COMPLETED': raise conflict('请先保存完整演奏记录。')
    try:
        with wave.open(io.BytesIO(data),'rb') as wav:
            if wav.getnchannels() not in (1,2) or wav.getsampwidth()!=2 or wav.getframerate() not in (22050,24000,44100,48000):
                raise ValueError('Unsupported PCM')
            frames=wav.getnframes()
            if frames<=0 or len(wav.readframes(frames))!=frames*wav.getnchannels()*2: raise ValueError('Truncated WAV')
            duration=frames/wav.getframerate()*1000
    except (wave.Error,EOFError,ValueError): raise bad_request('INVALID_AUDIO','需要有效的16位PCM WAV音频。')
    row.audio=data
    row.audio_metadata={'audio_duration_ms':duration,'duration_ms':duration,'audio_format':'wav','audio_source':'SYNTHESIZED_FROM_KEY_EVENTS','render_version':render_version}
    db.commit(); db.refresh(row)
    return row


def detail(row,include_events=True):
    if include_events:
        notes,metrics=analyze_events(row.events)
    else:
        notes=row.result.get('notes',[])
        metrics=row.result.get('metrics') or analyze_events([])[1]
    epoch_ms=row.config.get('client_clock_origin_epoch_ms')
    origin=datetime.fromtimestamp(epoch_ms/1000,timezone.utc).replace(tzinfo=None) if epoch_ms is not None else row.created_at
    result={**row.config,'id':row.id,'patient_id':row.patient_id,'owner_id':row.owner_id,'status':row.status,
        'started_at':origin,'bpm':row.config['segment_2_bpm'] or row.config['segment_1_bpm'],'metadata':{'baseline_id':row.config['baseline_id'],'hand_is_task_assignment':True,'input_source':row.config['input_source'],'camera_consent':row.config.get('camera_consent',False),'camera_transport_status':row.config.get('camera_transport_status','IDLE'),'clock_origin_source':'CLIENT_WALL_CLOCK' if epoch_ms is not None else 'SERVER_CREATED_AT'},
        'events':row.events if include_events else [],'notes':notes,'metrics':metrics,**metrics,'created_at':row.created_at,'completed_at':row.completed_at,
        'audio_url':f'/api/guided-song/sessions/{row.id}/audio' if row.audio_metadata else None,
        'audio_duration_ms':None,'audio_format':None,'audio_source':None,'render_version':None,
        'emotion_analysis_status':row.config.get('camera_transport_status','MODEL_NOT_CONFIGURED'),'emotion_source':'SIMULATED' if row.is_simulation else (row.config.get('emotion_audit') or {}).get('source'),**row.audio_metadata}
    result.pop('request',None)
    for segment in (1,2):
        subset=[n for n in notes if n['segment_index']==segment]
        result[f'segment_{segment}_started_at']=origin+timedelta(milliseconds=min(n['cue_onset_time_ms'] for n in subset)) if subset else None
        resolved=[n for n in subset if 'resolved_time_ms' in n]
        result[f'segment_{segment}_completed_at']=origin+timedelta(milliseconds=max(n['resolved_time_ms'] for n in resolved)) if len(resolved)==(14 if segment==1 else 18) else None
    return result
