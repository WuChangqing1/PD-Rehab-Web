"""Preview-first maintenance requested by user. Append provenance-tagged simulation only.

No clinical records are overwritten. Only the reserved fictional profile is renamed.
Empty means no foreign-key business references, excluding retained number allocations.
Never prints patient identity or notes. Run --apply only after preview acceptance.
"""
import argparse,json,sys
from datetime import date
from pathlib import Path
from sqlalchemy import select,func
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'scripts'))
from app.db.models import Patient,StaffUser,AuditLog
from app.db.base import Base,utcnow
from app.services.active_training_service import lock_patient
from seed_followup_showcase import seed_showcase,SHOWCASE_NUMBER,DATASET,identifier,dump

def references(db,patient_id,*,current=False):
    counts={}
    for table in Base.metadata.sorted_tables:
        if table.name=='patient_number_allocations':continue
        for column in table.columns:
            if any(fk.target_fullname=='patients.id' for fk in column.foreign_keys):
                counts[table.name]=(len(db.execute(select(column).where(column==patient_id).with_for_update()).all()) if current else db.scalar(select(func.count()).select_from(table).where(column==patient_id)))
    return counts

def maintain(db,*,apply=False,output_root,anchor=None):
    patients=list(db.scalars(select(Patient).where(Patient.is_deleted.is_(False)).order_by(Patient.id)))
    empty=[p for p in patients if not any(references(db,p.id).values())]
    result={'active_patients':len(patients),'empty_patients':len(empty),'apply':apply,'clinical_records_overwritten':0,'created_records':0}
    if not apply:return result
    owners=list(db.scalars(select(StaffUser.id).where(StaffUser.is_active.is_(True))))
    if not owners:raise ValueError('No active staff account; no changes applied')
    # Validate every reserved profile before any commit, including deletions.
    for p in patients:
        if p.hospital_number==SHOWCASE_NUMBER:
            try:marker=json.loads(p.doctor_notes or '{}')
            except ValueError:marker={}
            if p.id!=identifier('patient') or marker.get('demo_dataset')!=DATASET:
                raise ValueError('Reserved identity mismatch; no changes applied')
    for p in empty:
        # Release maintenance runs with application writes stopped. Recheck under lock.
        lock_patient(db,p.id)
        if not any(references(db,p.id,current=True).values()):p.is_deleted=True
    db.commit()
    for p in patients:
        if p.is_deleted:continue
        if p.hospital_number==SHOWCASE_NUMBER:
            marker=json.loads(p.doctor_notes or '{}')
            if p.id!=identifier('patient') or marker.get('demo_dataset')!=DATASET:
                raise ValueError('Reserved identity mismatch; profile not changed')
            p.name='小明';p.sex='MALE';p.birthday=date(1958,5,16)
            p.dominant_hand='RIGHT';p.affected_side='LEFT';p.medication_state='ON'
            p.diagnosis_date=date(2020,9,1);p.disease_duration_years=6;p.current_stage='Hoehn-Yahr 2期'
            db.commit()
            seeded=seed_showcase(db,owners,anchor=anchor,output_root=output_root)
        else:
            seeded=seed_showcase(db,owners,anchor=anchor,output_root=output_root,target_patient=p)
        result['created_records']+=seeded['created_records']
    db.add(AuditLog(staff_user_id=owners[0],action='PATIENT_SIMULATION_FILL',entity_type='patient_set',detail_json=dump(result),created_at=utcnow()))
    db.commit()
    result['deleted_empty_patients']=sum(p.is_deleted for p in patients)
    result['remaining_patients']=sum(not p.is_deleted for p in patients)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    from app.db.session import SessionLocal
    from app.core.config import settings
    if settings.database_url=='sqlite:///./data/pd.db':raise SystemExit('Refusing unconfigured default database')
    with SessionLocal() as db:print(json.dumps(maintain(db,apply=args.apply,output_root=settings.output_path),ensure_ascii=True))
