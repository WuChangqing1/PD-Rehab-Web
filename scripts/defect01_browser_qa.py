"""Disposable local UI fixtures. No production database or real identities."""
from datetime import datetime
import ui_piano_test_server as qa
from app.db.models import Patient,StaffUser,AssessmentSession
from sqlalchemy import select

with qa.maker() as db:
    db.scalar(select(StaffUser).where(StaffUser.username=='browserqa')).id='defect01-browser-staff'
    person=db.get(Patient,'browser-qa')
    person.hospital_number='DEMO-0001';person.sex='OTHER';person.medication_state='OFF'
    person.disease_duration_years=0;person.last_medication_time=datetime(2026,10,17,1,30)
    person.doctor_notes='已有备注，请保留';person.name='档案验收（虚拟）'
    db.get(Patient,'browser-second').hospital_number='0001'
    db.add(Patient(id='qa-deleted',hospital_number='QA-DELETED',name='已删除验收（虚拟）',is_deleted=True))
    db.add(AssessmentSession(id='qa-assessment',patient_id='browser-qa',session_type='FINGER_TAPPING_ONLY',status='COMPLETED',notes='虚拟界面验收，无测量数据'))
    db.commit()

if __name__=='__main__':
    import uvicorn
    uvicorn.run(qa.app,host='127.0.0.1',port=8013,log_level='warning')
