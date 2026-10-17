"""Idempotent independent example dataset, never a patient's measurement.

Only the reserved DEMO-FOLLOWUP-20261017 identity is writable. Existing records
are not updated or deleted. Raw synthetic inputs and authoritative arithmetic
are retained; face predictions and clinical/display scores are never invented.
CLI defaults to no writes; --write-demo explicitly enables this dataset only.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import date,datetime,time,timedelta
import json,math,random,sys,uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import numpy as np
from sqlalchemy import select
from app.db.models import Patient,PianoSession,PianoEvent,PoseSession,AssessmentSession,FingerTappingResult,StaffUser,AuditLog
from app.db.models.guided_song import GuidedSongSession
from app.db.base import utcnow
from app.services.followup_service import SHOWCASE_NUMBER
from app.services.piano_service import PIANO_EVENT_COLUMNS,EVENT_EXTRA_FIELDS
from app.utils.piano_metrics import compute_metrics
from app.ml.pose.metrics import analyse_series
from app.ml.finger_tapping.features import extract_features
from app.ml.finger_tapping.signal import DistanceSignal
from app.services.guided_song_service import analyze_events,MELODY

DATASET='followup-showcase-v1'
NAMESPACE=uuid.UUID('610c38d7-4853-4dbd-b5a0-73d7f008db64')
PRACTICES=[('SINGLE_KEY_RHYTHM',None),('ALTERNATING_HANDS',None),('MAPPED_SEQUENCE',None),('FOLLOW_THE_BEAT',None),('MEMORY_RHYTHM',None),
 ('SINGLE_KEY_RHYTHM','SFT_CUE_SYNC'),('FOLLOW_THE_BEAT','CFT_RHYTHM_HOLD'),('SINGLE_KEY_RHYTHM','BIMANUAL_SYNC'),('FOLLOW_THE_BEAT','ACCENT_GROUPING'),
 ('SINGLE_KEY_RHYTHM','TEMPO_RAMP'),('SINGLE_KEY_RHYTHM','HOLD_RELEASE'),('SINGLE_KEY_RHYTHM','BIMANUAL_OFFSET'),('MEMORY_RHYTHM','REVERSE_SEQUENCE'),('SINGLE_KEY_RHYTHM','GO_NO_GO')]
EXERCISES=['BALLET_PORT_DE_BRAS','BALLET_FIRST_POSITION','BALLET_TENDU','BALLET_DEMI_PLIE','BALLET_WEIGHT_SHIFT']
OFFSETS=[24,20,16,12,9,6,3,1]
def identifier(key):return str(uuid.uuid5(NAMESPACE,key))
def dump(value):return json.dumps(value,ensure_ascii=False,allow_nan=False)


def piano_events(mode,recipe,run):
    rng=random.Random(20261017+run*97+sum(map(ord,recipe or mode)))
    rows=[];target=1200
    for i in range(24):
        segment=i//6;target+=([1000,850,650,1000][segment] if recipe=='TEMPO_RAMP' else 1000)
        missed=rng.random()<.10+(.03 if run%3==1 else 0)
        no_go=recipe=='GO_NO_GO' and i%4==3
        commission=no_go and rng.random()<.18
        actual=None if (missed and not no_go) or (no_go and not commission) else target+rng.randint(-95,145)
        hold=250 if i%2==0 else 750
        duration=max(50,hold+rng.randint(-80,100)) if recipe=='HOLD_RELEASE' else rng.randint(180,330)
        cue=None if recipe=='CFT_RHYTHM_HOLD' and i>=12 else target-300
        row=dict(event_index=i,cue_index=i,cue_onset_time_ms=cue,target_time_ms=target,actual_time_ms=actual,
            response_latency_ms=actual-cue if actual is not None and cue is not None else None,
            timing_error_ms=actual-target if actual is not None else None,
            key_code='KeyA' if i%2==0 else 'KeyJ',note='C',hand='LEFT' if i%2==0 else 'RIGHT',finger_hint='INDEX',
            key_down_time_ms=actual,key_up_time_ms=actual+duration if actual is not None else None,
            hold_duration_ms=duration if actual is not None else None,is_correct=(not commission if no_go else actual is not None),
            is_missed=actual is None and not no_go,is_wrong_key=False,is_prompt=False,recipe_id=recipe,
            sequence_position=i%4+1,sequence_length=4,memory_group=i//4,
            beat_in_bar=i%4+1,is_accent=i%4==0,cue_type='NO_GO' if no_go else 'GO' if recipe=='GO_NO_GO' else None)
        if recipe=='TEMPO_RAMP':row['tempo_segment']=segment
        if recipe=='HOLD_RELEASE':row['target_hold_ms']=hold
        if recipe in ['BIMANUAL_SYNC','BIMANUAL_OFFSET']:
            row['pair_role']='PRIMARY' if i%2==0 else 'SECONDARY'
            if recipe=='BIMANUAL_OFFSET':
                row.update(pair_id=i//2,target_offset_ms=500)
                row['target_time_ms']=rows[-1]['target_time_ms']+500 if i%2 else row['target_time_ms']
                if actual is not None:
                    row['actual_time_ms']=row['target_time_ms']+rng.randint(-65,95)
            else:row['inter_hand_onset_diff_ms']=rng.randint(20,120) if i%2==0 and actual is not None else None
            if recipe=='BIMANUAL_SYNC' and i%2:
                row['target_time_ms']=rows[-1]['target_time_ms']
                if actual is not None:row['actual_time_ms']=row['target_time_ms']+rng.randint(-65,95)
            row['cue_onset_time_ms']=row['target_time_ms']-300
        rows.append(row)
    # Bimanual target changes must also be reflected in every raw timestamp.
    for r in rows:
        actual=r['actual_time_ms']
        if actual is not None:
            r['key_down_time_ms']=actual;r['key_up_time_ms']=actual+r['hold_duration_ms']
            r['timing_error_ms']=actual-r['target_time_ms']
            r['response_latency_ms']=actual-r['cue_onset_time_ms'] if r['cue_onset_time_ms'] is not None else None
    if recipe=='BIMANUAL_SYNC':
        for i in range(0,len(rows),2):
            left,right=rows[i]['actual_time_ms'],rows[i+1]['actual_time_ms']
            rows[i]['inter_hand_onset_diff_ms']=abs(left-right) if left is not None and right is not None else None
    if mode=='MEMORY_RHYTHM':
        expanded=[]
        for i in range(0,len(rows),4):
            for pos in range(4):
                target=rows[i]['target_time_ms']-1500+pos*200
                expanded.append(dict(rows[i],is_prompt=True,is_correct=False,is_missed=False,
                    sequence_position=pos+1,target_time_ms=target,cue_onset_time_ms=target,
                    actual_time_ms=None,key_down_time_ms=None,key_up_time_ms=None,hold_duration_ms=None,
                    response_latency_ms=None,timing_error_ms=None))
            expanded.extend(rows[i:i+4])
        rows=expanded
    for index,r in enumerate(rows):r['event_index']=index
    return rows


def seed_showcase(db,owner_ids,*,anchor:date|None=None,output_root:Path):
    anchor=anchor or date.today()
    person=db.scalar(select(Patient).where(Patient.hospital_number==SHOWCASE_NUMBER))
    if person:
        try:marker=json.loads(person.doctor_notes or '{}')
        except ValueError:marker={}
        if person.id!=identifier('patient') or marker.get('demo_dataset')!=DATASET:
            raise ValueError('reserved 演示编号已被其他患者占用，未修改任何数据。')
        anchor=date.fromisoformat(marker['anchor'])
    else:
        person=Patient(id=identifier('patient'),hospital_number=SHOWCASE_NUMBER,name='随访演示（虚拟）',
            sex='UNKNOWN',doctor_notes=dump({'demo_dataset':DATASET,'anchor':anchor.isoformat(),'clinical_data':False}))
        db.add(person);db.flush()
    created=0
    def absent(model,key):
        existing=db.get(model,identifier(key))
        if existing is not None and getattr(existing,'patient_id',person.id)!=person.id:
            raise ValueError('reserved 演示记录标识冲突，拒绝写入。')
        return existing is None
    output_root=Path(output_root).resolve()
    for run,offset in enumerate(OFFSETS):
        started=datetime.combine(anchor-timedelta(days=offset),time(1)) # 09:00 Beijing
        for index,(mode,recipe) in enumerate(PRACTICES):
            key=f'piano/{run}/{recipe or mode}'
            if not absent(PianoSession,key):continue
            events=piano_events(mode,recipe,run);metrics=compute_metrics(events,planned_cues=24)
            audit={'demo_dataset':DATASET,'completion_status':'COMPLETED','planned_cues':24,
                'server_metrics':metrics.to_dict(),'raw_input_kind':'synthetic_key_events',
                'recipe_algorithm_version':'followup-synthetic-cues-v1' if recipe else None,
                'tempo_ceiling_bpm':60000/650 if recipe=='TEMPO_RAMP' else None,
                'events_extra_json':dump([{'event_index':e['event_index'],**{k:e.get(k) for k in EVENT_EXTRA_FIELDS}} for e in events])}
            record=PianoSession(id=identifier(key),patient_id=person.id,mode=mode,recipe_id=recipe,input_source='SEED_DEMO',
                bpm=60,judgement_window_ms=250,sequence_length=4,note_density=1,hand_mode='BOTH' if recipe in ['BIMANUAL_SYNC','BIMANUAL_OFFSET'] else 'ALTERNATING' if mode=='ALTERNATING_HANDS' else 'SINGLE',
                session_duration_sec=30,started_at=started+timedelta(minutes=index*3),completed_at=started+timedelta(minutes=index*3,seconds=30),
                difficulty_before_json=dump(audit),metrics_version='piano-example-arithmetic-v1',**metrics.to_db_fields())
            db.add(record);db.flush()
            for e in events:db.add(PianoEvent(session_id=record.id,**{k:e.get(k) for k in PIANO_EVENT_COLUMNS if k!='session_id'}))
            created+=1
        for index,exercise in enumerate(EXERCISES):
            key=f'pose/{run}/{exercise}'
            if not absent(PoseSession,key):continue
            phase=np.arange(600)/30*2*math.pi/(2.4+.12*(run%3))
            wave=(1-np.cos(phase))/2
            left=10+(65+(run%4)*4)*wave;right=10+(61+(run%3)*5)*wave
            if exercise=='BALLET_FIRST_POSITION':
                count=450+(run%4)*60
                left=np.full(count,2+(run%3)*.2);right=left.copy()
            elif exercise=='BALLET_DEMI_PLIE':left=170-35*wave;right=170-33*wave
            elif exercise in ['BALLET_TENDU','BALLET_WEIGHT_SHIFT']:left=5+25*wave;right=5+23*wave
            stats=analyse_series(left.tolist(),30);other=analyse_series(right.tolist(),30)
            raw={'demo_dataset':DATASET,'raw_input_kind':'synthetic_joint_angles','fps':30,'left_angle_series':left.tolist(),'right_angle_series':right.tolist(),
                'angle_std_deg':stats.angle_std_deg,
                'repetition_interval_ms':stats.repetition_interval_ms}
            joint='trunk' if exercise=='BALLET_FIRST_POSITION' else 'knee' if exercise=='BALLET_DEMI_PLIE' else 'hip' if exercise in ['BALLET_TENDU','BALLET_WEIGHT_SHIFT'] else 'shoulder'
            raw['drive_joint']=joint
            shoulder_peaks=[]
            for name,rest in [('shoulder',15),('knee',175),('hip',3)]:
                for side,active in [('left',left),('right',right)]:
                    values=active if joint==name else np.full(len(left),rest-(1 if side=='right' else 0))
                    measured=analyse_series(values.tolist(),30)
                    raw[f'{side}_{name}_series']=values.tolist()
                    raw[f'{side}_hip_abduction_deg' if name=='hip' else f'{side}_{name}_max_angle_deg']=measured.peak_deg
                    if name=='shoulder':shoulder_peaks.append(measured.peak_deg)
            raw['left_right_angle_difference_deg']=abs(shoulder_peaks[0]-shoulder_peaks[1])
            trunk=left if joint=='trunk' else np.full(len(left),2+(run%3)*.2)
            raw['trunk_angle_series']=trunk.tolist();raw['trunk_angle_deg']=analyse_series(trunk.tolist(),30).peak_deg
            db.add(PoseSession(id=identifier(key),patient_id=person.id,exercise_type=exercise,execution_mode='STANDING_SUPPORTED',input_source='SEED_DEMO',
                difficulty_json=dump({'bpm':40,'demo_dataset':DATASET}),started_at=started+timedelta(hours=1,minutes=index*3),
                completed_at=started+timedelta(hours=1,minutes=index*3,seconds=20),hold_time_sec=stats.hold_time_sec,
                repetition_count=stats.repetition_count,movement_speed=stats.movement_speed_deg_per_sec,valid_pose_frame_ratio=stats.valid_sample_ratio,
                raw_metrics_json=dump(raw),algorithm_version='pose-example-arithmetic-v1',exercise_definition_version='ballet-exercises-v1.1.0'))
            created+=1
        assessment_key=f'assessment/{run}'
        if absent(AssessmentSession,assessment_key):
            db.add(AssessmentSession(id=identifier(assessment_key),patient_id=person.id,session_type='FINGER_TAPPING_ONLY',status='COMPLETED',
                started_at=started-timedelta(minutes=10),completed_at=started-timedelta(minutes=9),notes='独立示例数据；未运行面部模型。'))
            db.flush();created+=1
        for hand in ['LEFT','RIGHT']:
            key=f'tapping/{run}/{hand}'
            if db.get(FingerTappingResult,identifier(key)):continue
            frames=np.arange(450);values=.24+.2*np.sin(frames/30*2*math.pi*(2.1+.12*(run%4)+(.15 if hand=='RIGHT' else 0)))
            signal=DistanceSignal(values=values,frame_indices=frames,timestamps_ms=frames/30*1000)
            features=extract_features(signal,30)
            folder=output_root/'followup-showcase'/person.id
            folder.mkdir(parents=True,exist_ok=True);path=folder/f'{identifier(key)}.npz'
            if not path.resolve().is_relative_to(output_root):raise ValueError('Invalid example output path')
            if not path.exists():np.savez_compressed(path,frame_index=frames,timestamp_ms=frames/30*1000,aperture_raw=values,aperture_filtered=values)
            raw=asdict(features);raw.update(demo_dataset=DATASET,raw_input_kind='synthetic_aperture_signal')
            db.add(FingerTappingResult(id=identifier(key),assessment_session_id=identifier(assessment_key),hand=hand,input_source='SEED_DEMO',
                created_at=started-timedelta(minutes=9),raw_features_json=dump(raw),raw_timeseries_path=str(path),
                analyzer_version='finger-example-arithmetic-v1',**features.to_features()))
            created+=1
        for owner in owner_ids:
            key=f'guided/{owner}/{run}'
            if not absent(GuidedSongSession,key):continue
            events=[];clock=0;rng=random.Random(900+run)
            for i,midi in enumerate(MELODY):
                segment=1 if i<14 else 2
                def add(kind,t,**extra):events.append(dict(seq=len(events),type=kind,segment_index=segment,note_index=i,time_ms=t,**extra))
                add('CUE',clock)
                if i%9==run%9:
                    add('DOWN',clock+210,midi=62 if midi!=62 else 60,press_id=f'wrong-{i}')
                    add('UP',clock+350,midi=62 if midi!=62 else 60,press_id=f'wrong-{i}')
                latency=rng.randint(360,680)
                add('DOWN',clock+latency,midi=midi,press_id=f'note-{i}');add('UP',clock+latency+260,midi=midi,press_id=f'note-{i}');clock+=1100
            notes,metrics=analyze_events(events)
            db.add(GuidedSongSession(id=identifier(key),patient_id=person.id,owner_id=owner,client_request_id=key,status='COMPLETED',
                created_at=started+timedelta(hours=2),completed_at=started+timedelta(hours=2,seconds=36),events=events,result={'notes':notes,'metrics':metrics},
                config={'demo_dataset':DATASET,'is_simulation':True,'input_source':'SYNTHETIC_SELFTEST','song_id':'two_tigers','song_version':'1',
                    'selected_hand':'LEFT','initial_difficulty':'BEGINNER','segment_1_bpm':60,'segment_2_bpm':60,'baseline_id':None,'difficulty_adjustment':{'policy_version':'guided-song-1'}}))
            created+=1
    if created:db.add(AuditLog(staff_user_id=owner_ids[0] if owner_ids else None,action='DEMO_FOLLOWUP_SEED',entity_type='patient',entity_id=person.id,detail_json=dump({'demo_dataset':DATASET,'created_records':created}),created_at=utcnow()))
    db.commit()
    return {'patient_id':person.id,'hospital_number':SHOWCASE_NUMBER,'created_records':created,'input_source':'SEED_DEMO','anchor':anchor.isoformat()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-demo',action='store_true');args=parser.parse_args()
    if not args.write_demo:
        print('No writes. Use --write-demo to add only the independent reserved example patient.');raise SystemExit(0)
    from app.db.session import SessionLocal
    from app.core.config import settings
    if settings.database_url=='sqlite:///./data/pd.db':raise SystemExit('Refusing unconfigured default database')
    with SessionLocal() as db:
        owners=list(db.scalars(select(StaffUser.id).where(StaffUser.is_active.is_(True))))
        print(dump(seed_showcase(db,owners,output_root=settings.output_path)))
