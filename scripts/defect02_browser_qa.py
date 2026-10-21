"""Disposable UI verification only; never opens a production database."""
from datetime import date, datetime
from pathlib import Path
import ui_piano_test_server as qa
from sqlalchemy import delete,select
from app.db.models import Patient,StaffUser,AssessmentSession,Baseline
from seed_followup_showcase import seed_showcase

with qa.maker() as db:
    staff=db.scalar(select(StaffUser).where(StaffUser.username=='browserqa'))
    staff.id='defect02-browser-staff'
    person=db.get(Patient,'browser-qa')
    person.hospital_number='DEMO-0001';person.sex='OTHER';person.medication_state='OFF'
    person.last_medication_time=datetime(2026,10,20,1,30);person.doctor_notes='已有虚拟备注'
    db.execute(delete(Baseline).where(Baseline.patient_id==person.id))
    db.add_all([Patient(id=f'qa-{i}',hospital_number=f'QA-{i:03d}',name=f'验收样本{i}（虚拟）',sex='MALE') for i in range(1,28)])
    db.add(AssessmentSession(id='qa-history',patient_id='browser-qa',session_type='FINGER_TAPPING_ONLY',status='COMPLETED',started_at=datetime(2026,10,20,1)))
    db.commit()
    seed_showcase(db,[staff.id],anchor=date(2026,10,21),output_root=Path(__file__).resolve().parents[1]/'_deploy/defect02-20261021/fixtures')

if __name__=='__main__':
    import uvicorn
    uvicorn.run(qa.app,host='127.0.0.1',port=8014,log_level='warning')
