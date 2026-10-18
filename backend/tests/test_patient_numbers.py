"""Allocation must use a real multi-connection database, never a process lock."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os,re,subprocess,sys,uuid
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.models import Patient,AssessmentSession
from app.schemas.patient import PatientCreate
from app.services.patient_service import create_patient,soft_delete_patient

def test_automatic_number_api_and_old_clients_remain_compatible(app_client,auth_headers,patient_payload):
    legacy=app_client.post('/api/patients',headers=auth_headers,json=patient_payload).json()
    reply=app_client.post('/api/patients',headers=auth_headers,json={'name':'自动编号（虚拟）'})
    assert reply.status_code==201,reply.text
    auto=reply.json();assert re.fullmatch(r'P\d{6,}',auto['hospital_number'])
    assert str(uuid.UUID(auto['id']))==auto['id']
    found=app_client.get('/api/patients',headers=auth_headers,params={'q':auto['hospital_number']}).json()
    assert [r['id'] for r in found['items']]==[auto['id']]
    assert app_client.get('/api/patients/'+legacy['id'],headers=auth_headers).json()['hospital_number']==patient_payload['hospital_number']
    assert app_client.patch('/api/patients/'+auto['id'],headers=auth_headers,json={'hospital_number':'CHANGED'}).status_code==409

def test_concurrent_allocations_skip_collisions_and_never_reuse_deleted_numbers(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'allocation.db'),connect_args={'check_same_thread':False,'timeout':30})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        old=create_patient(db,PatientCreate(name='保留旧档案',hospital_number='P000001'))
        old_id=old.id
    def create(index):
        with Session(engine) as db:
            p=create_patient(db,PatientCreate(name=f'虚拟并发{index}'))
            return p.id,p.hospital_number
    with ThreadPoolExecutor(max_workers=8) as pool:
        result=list(pool.map(create,range(24)))
    assert len({n for _,n in result})==24
    assert 'P000001' not in {n for _,n in result}
    with Session(engine) as db:
        soft_delete_patient(db,result[-1][0])
        new=create_patient(db,PatientCreate(name='删除后新增'))
        assert new.hospital_number not in {n for _,n in result}
        assert db.get(Patient,old_id).hospital_number=='P000001'
    engine.dispose()

def test_additive_migration_preserves_identifiers_and_reserves_legacy_high_water(tmp_path):
    backend=Path(__file__).resolve().parents[1];url='sqlite:///'+str(tmp_path/'migration.db')
    env={**os.environ,'DATABASE_URL':url,'APP_ENV':'test','JWT_SECRET':'migration-qa-only'}
    def migrate(revision):
        run=subprocess.run([sys.executable,'-m','alembic','upgrade',revision],cwd=backend,env=env,capture_output=True,text=True)
        assert run.returncode==0,run.stderr
    migrate('h4c6d8e0f2a3')
    engine=create_engine(url)
    with Session(engine) as db:
        p=Patient(hospital_number='P000042',name='迁移保留');db.add(p);db.flush();identity=p.id
        history=AssessmentSession(patient_id=identity,session_type='FINGER_TAPPING_ONLY',status='COMPLETED');db.add(history);db.commit();history_id=history.id
    migrate('head')
    with Session(engine) as db:
        assert db.get(Patient,identity).hospital_number=='P000042'
        assert db.get(AssessmentSession,history_id).patient_id==identity
        new=create_patient(db,PatientCreate(name='新分配'))
        assert int(new.hospital_number[1:])>42
        new_id=new.id;new_number=new.hospital_number
    rollback=subprocess.run([sys.executable,'-m','alembic','downgrade','h4c6d8e0f2a3'],cwd=backend,env=env,capture_output=True,text=True)
    assert rollback.returncode==0,rollback.stderr
    with Session(engine) as db:
        assert db.get(Patient,new_id).hospital_number==new_number
        assert db.get(AssessmentSession,history_id).patient_id==identity
    migrate('head')
    engine.dispose()

def test_allocator_ddl_uses_database_native_identity_for_sqlite_and_mysql():
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql,sqlite
    from app.db.models.patient_number import PatientNumberAllocation
    assert 'AUTOINCREMENT' in str(CreateTable(PatientNumberAllocation.__table__).compile(dialect=sqlite.dialect()))
    assert 'AUTO_INCREMENT' in str(CreateTable(PatientNumberAllocation.__table__).compile(dialect=mysql.dialect()))
