import sys
from pathlib import Path
from datetime import date
import pytest
from sqlalchemy import select,func
from app.db.models import Patient,PianoSession
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from polish_patient_data import maintain
from seed_followup_showcase import SHOWCASE_NUMBER

def test_preview_and_reserved_guard_do_not_modify_empty_patients(db,staff_user,tmp_path):
    empty=Patient(hospital_number='EMPTY',name='Empty')
    conflict=Patient(hospital_number=SHOWCASE_NUMBER,name='Existing')
    db.add_all([empty,conflict]);db.commit()
    preview=maintain(db,output_root=tmp_path)
    assert preview['empty_patients']==2 and not empty.is_deleted
    with pytest.raises(ValueError,match='identity mismatch'):
        maintain(db,apply=True,output_root=tmp_path)
    db.refresh(empty)
    assert not empty.is_deleted and conflict.name=='Existing'

def test_fill_is_idempotent_preserves_actual_records_and_sources(db,staff_user,tmp_path):
    actual=Patient(hospital_number='ACTUAL',name='Preserved')
    empty=Patient(hospital_number='EMPTY',name='Empty')
    db.add_all([actual,empty]);db.commit()
    record=PianoSession(patient_id=actual.id,mode='SINGLE_KEY_RHYTHM',accuracy=.7123,input_source='HUMAN')
    db.add(record);db.commit();original=(record.id,record.accuracy,record.input_source,record.started_at)
    first=maintain(db,apply=True,output_root=tmp_path,anchor=date(2026,10,21))
    assert first['created_records']>0 and empty.is_deleted
    db.refresh(record)
    assert original==(record.id,record.accuracy,record.input_source,record.started_at)
    assert actual.name=='Preserved'
    seeded=list(db.scalars(select(PianoSession).where(PianoSession.id!=record.id)))
    assert seeded and all(r.input_source=='SEED_DEMO' and r.completed_at for r in seeded)
    other=Patient(hospital_number='OTHER',name='Other');db.add(other);db.commit()
    db.add(PianoSession(patient_id=other.id,mode='SINGLE_KEY_RHYTHM'));db.commit()
    assert maintain(db,apply=True,output_root=tmp_path,anchor=date(2026,10,21))['created_records']>0
    count=db.scalar(select(func.count()).select_from(PianoSession))
    second=maintain(db,apply=True,output_root=tmp_path,anchor=date(2026,10,22))
    assert second['created_records']==0
    assert db.scalar(select(func.count()).select_from(PianoSession))==count
