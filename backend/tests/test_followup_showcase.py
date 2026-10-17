import importlib.util
from datetime import date
from pathlib import Path
from sqlalchemy import select,func
from app.db.models import Patient,PianoSession,PianoEvent,PoseSession,MicroExpressionResult
from app.db.models.guided_song import GuidedSongSession


def module():
    path=Path(__file__).resolve().parents[2]/'scripts/seed_followup_showcase.py'
    spec=importlib.util.spec_from_file_location('followup_showcase',path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded);return loaded


def test_showcase_is_idempotent_complete_and_always_marked_as_examples(db,staff_user,tmp_path):
    seed=module()
    real=Patient(hospital_number='real-preserved',name='Existing QA');db.add(real);db.commit()
    first=seed.seed_showcase(db,[staff_user.id],anchor=date(2026,10,17),output_root=tmp_path)
    counts=[db.scalar(select(func.count()).select_from(model)) for model in [Patient,PianoSession,PianoEvent,PoseSession,GuidedSongSession]]
    second=seed.seed_showcase(db,[staff_user.id],anchor=date(2026,10,18),output_root=tmp_path)
    assert first['patient_id']==second['patient_id'] and second['created_records']==0
    assert counts==[db.scalar(select(func.count()).select_from(model)) for model in [Patient,PianoSession,PianoEvent,PoseSession,GuidedSongSession]]
    piano=list(db.scalars(select(PianoSession)))
    assert len({r.recipe_id or r.mode for r in piano})>=13
    assert all(r.input_source=='SEED_DEMO' for r in piano)
    assert all(r.completed_at and r.accuracy is not None for r in piano)
    assert len(set(db.scalars(select(PoseSession.exercise_type))))==5
    assert all(r.input_source=='SEED_DEMO' and r.completion_score is None for r in db.scalars(select(PoseSession)))
    assert db.scalar(select(func.count()).select_from(MicroExpressionResult))==0
    assert db.get(Patient,real.id).name=='Existing QA'


def test_showcase_refuses_to_repurpose_an_existing_patient(db,staff_user,tmp_path):
    import pytest
    seed=module()
    db.add(Patient(hospital_number=seed.SHOWCASE_NUMBER,name='Do not overwrite'))
    db.commit()
    with pytest.raises(ValueError,match='reserved|保留'):
        seed.seed_showcase(db,[staff_user.id],anchor=date(2026,10,17),output_root=tmp_path)
    assert db.scalar(select(func.count()).select_from(PianoSession))==0
