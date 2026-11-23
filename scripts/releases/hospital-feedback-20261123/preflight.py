"""Isolated database plus one real-provider call; never reads patient records."""
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base,utcnow
from app.db.models import StaffUser,Patient,PianoSession
from app.services.training_review import summary,answer
from app.api.integration import _ask_llm
from app.core.config import settings
engine=create_engine('sqlite://')
Base.metadata.create_all(engine)
with Session(engine) as db:
 nurse=StaffUser(username='release-nurse',display_name='Isolated QA',role='NURSE',is_active=True,password_hash='not-used')
 patient=Patient(name='ISOLATED-NOT-A-PATIENT',hospital_number='ISOLATED-RELEASE',doctor_notes='DO-NOT-SEND')
 db.add_all([nurse,patient]);db.flush()
 row=PianoSession(patient_id=patient.id,mode='SINGLE_KEY_RHYTHM',accuracy=.8,mean_response_latency_ms=320,input_source='SYNTHETIC_SELFTEST',completed_at=utcnow(),difficulty_before_json=json.dumps({'completion_status':'COMPLETED'}))
 db.add(row);db.commit()
 _,data=summary(db,nurse,'piano',row.id)
 assert all(x not in json.dumps(data) for x in [patient.id,row.id,patient.name,patient.doctor_notes])
 text=answer(data,'发布验收：这是无患者身份的自动化自测数据。请解释这次记录，并说明不是临床结论。',_ask_llm)
 assert text.strip()
 print(json.dumps({'isolatedDatabase':True,'realProvider':True,'model':settings.expert_llm_model,'answerCharacters':len(text),'whiteListOnly':True}))
