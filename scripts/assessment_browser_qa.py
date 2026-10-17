"""Disposable browser QA: fictional patients and explicitly synthetic stored results.

Run with the project Python; listens on 127.0.0.1:8013 and never opens the live DB.
Login: browserqa / browser-qa-only (local test account only).
"""
import json
from pathlib import Path

import numpy as np
import ui_piano_test_server as qa
from app.db.base import utcnow
from app.db.models import AssessmentSession, FingerTappingResult

root = Path(__file__).resolve().parents[1] / '_deploy' / 'assessment-qa'
root.mkdir(parents=True, exist_ok=True)
with qa.maker() as db:
    db.add_all([
        AssessmentSession(id='qa-completed',patient_id='browser-qa',session_type='COMPREHENSIVE',
            status='COMPLETED',started_at=utcnow(),completed_at=utcnow(),notes='虚拟验收数据；面部模型不可用，本次跳过。'),
        AssessmentSession(id='qa-open',patient_id='browser-qa',session_type='COMPREHENSIVE',status='IN_PROGRESS',started_at=utcnow()),
        AssessmentSession(id='qa-other-open',patient_id='browser-qa',session_type='FINGER_TAPPING_ONLY',status='IN_PROGRESS',started_at=utcnow()),
    ]);db.flush()
    for hand,frequency in [('LEFT',2.5),('RIGHT',2.0)]:
        frames=np.arange(120);aperture=.3+.2*np.sin(frames/30*2*np.pi*frequency)
        path=root/f'qa-{hand.lower()}.npz'
        np.savez_compressed(path,frame_index=frames,timestamp_ms=frames/30*1000,aperture_raw=aperture,aperture_filtered=aperture)
        db.add(FingerTappingResult(assessment_session_id='qa-completed',hand=hand,input_source='SYNTHETIC_SELFTEST',
            tapping_frequency=frequency,avg_amplitude=.4,avg_speed=1.2,avg_cycle_duration=1/frequency,
            amplitude_cv=.1,speed_cv=.12,cycle_cv=.08,amplitude_slope=-.002,speed_slope=-.001,cycle_slope=.001,
            interruptions=0,valid_frame_ratio=.98,avg_landmark_confidence=.95,analyzer_version='QA_FIXTURE_ONLY',
            raw_features_json=json.dumps({'peak_frames':[6,18,30,42,54,66,78,90,102,114],'provenance':'SYNTHETIC_SELFTEST'}),raw_timeseries_path=str(path)))
    db.commit()

if __name__=='__main__':
    import uvicorn
    uvicorn.run(qa.app,host='127.0.0.1',port=8013,log_level='warning')
