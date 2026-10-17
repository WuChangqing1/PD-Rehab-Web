"""Seed and verify only the approved independent demo identity on deployment.

No real patient records, model predictions, credentials or raw inputs are read.
Run with the configured application environment and PYTHONPATH=backend.
"""
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.db.models import StaffUser
from app.db.session import SessionLocal, engine
from app.services.followup_service import activity_feed


def run():
    assert Path(engine.url.database).resolve()==Path('/opt/pd-rehab/data/pd.db')
    path=Path(__file__).with_name('seed_followup_showcase.py')
    spec=importlib.util.spec_from_file_location('showcase',path)
    seed=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    with SessionLocal() as db:
        owners=list(db.scalars(select(StaffUser.id).where(StaffUser.is_active.is_(True))))
        assert owners, 'No active staff owner'
        created=seed.seed_showcase(db,owners,output_root=settings.output_path)
        repeat=seed.seed_showcase(db,owners,output_root=settings.output_path)
        assert repeat['created_records']==0
        anchor=date.fromisoformat(created['anchor'])
        feeds=[activity_feed(db,created['patient_id'],owner,anchor-timedelta(days=30),anchor,480) for owner in owners]
        for feed in feeds:
            assert feed.is_showcase
            assert len(feed.piano)==112 and len(feed.pose)==40 and len(feed.assessments)==8
            assert len(feed.tapping)==16 and len(feed.guided)==8
            assert len({r.recipe_id or r.mode for r in feed.piano})==14
            assert len({r.exercise_type for r in feed.pose})==5
            assert all(r.input_source=='SEED_DEMO' for r in [*feed.piano,*feed.pose,*feed.tapping])
            assert all(r.source=='SEED_DEMO' and r.version=='guided-song-1' for r in feed.guided)
            assert all('raw_presses' not in (r.difficulty_before_json or {}) and 'events_extra_json' not in (r.difficulty_before_json or {}) for r in feed.piano)
        return {**created,'owner_views_verified':len(owners),'idempotent':True,
                'piano':112,'ballet':40,'assessments':8,'tapping':16,'guided_per_owner':8,
                'real_patient_records_read':False,'real_patient_records_mutated':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-demo',action='store_true')
    if not parser.parse_args().write_demo:
        raise SystemExit('No writes. Pass --write-demo for the reserved independent example identity only.')
    print(json.dumps(run(),ensure_ascii=False))
