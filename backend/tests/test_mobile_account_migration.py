"""Rehearse the actual Alembic upgrade and safe downgrade on populated SQLite."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_mobile_upgrade_and_downgrade_preserve_existing_records(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.security import hash_password
    from app.db.models import Patient, StaffUser, ExternalPracticeRecord
    from app.db.models.mobile_account import MobileAccount, MobileSession
    from app.db.base import utcnow
    from datetime import timedelta

    backend=Path(__file__).resolve().parents[1]
    path=tmp_path/'populated.db'
    url='sqlite:///'+path.as_posix()
    env={**os.environ,'DATABASE_URL':url,'APP_ENV':'test'}
    def migrate(version):
        result=subprocess.run([sys.executable,'-m','alembic','upgrade' if version!='m9b1c3d5e7f9-downgrade' else 'downgrade',
            version.removesuffix('-downgrade')],cwd=backend,env=env,capture_output=True,text=True,timeout=90)
        assert result.returncode==0,result.stderr
    migrate('m9b1c3d5e7f9')
    engine=create_engine(url)
    with Session(engine) as db:
        user=StaffUser(username='existing_staff',password_hash=hash_password('old-staff-password'),display_name='Staff',role='DOCTOR')
        patient=Patient(name='Existing patient',hospital_number='OLD-123')
        db.add_all([user,patient]);db.flush()
        record=ExternalPracticeRecord(patient_id=patient.id,operator_id=user.id,device_id='old-device',
            local_profile_id='old-profile',source_record_id='old-source',record_type='PIANO_SESSION',
            schema_version='old-version',payload_sha256='a'*64,payload_json='{"original":true}')
        db.add(record);db.commit()
    with sqlite3.connect(path) as conn:
        original={table:conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for table in ('staff_users','patients','external_practice_records','patient_number_allocations')}
    migrate('n0c2d4e6f8a0')
    with sqlite3.connect(path) as conn:
        for table,values in original.items():
            assert conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()==values
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='n0c2d4e6f8a0'
    with Session(engine) as db:
        mobile=StaffUser(username='migration_patient',password_hash=hash_password('mobile-password'),display_name='Mobile',role='PATIENT')
        person=Patient(name='Mobile patient',hospital_number='P900000')
        db.add_all([mobile,person]);db.flush()
        db.add(MobileAccount(user_id=mobile.id,patient_id=person.id,recovery_hash='a'*64,sync_consent_version='account-sync-v1'))
        db.flush()
        db.add(MobileSession(user_id=mobile.id,refresh_hash='b'*64,expires_at=utcnow()+timedelta(days=1)))
        db.commit();mobile_id,person_id=mobile.id,person.id
    engine.dispose()
    migrate('m9b1c3d5e7f9-downgrade')
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT is_active FROM staff_users WHERE id=?',(mobile_id,)).fetchone()[0]==0
        assert conn.execute('SELECT id FROM patients WHERE id=?',(person_id,)).fetchone()[0]==person_id
        assert conn.execute('SELECT payload_json FROM external_practice_records').fetchone()[0]=='{"original":true}'
        assert conn.execute('SELECT username,role,is_active FROM staff_users WHERE username=?',('existing_staff',)).fetchone()==('existing_staff','DOCTOR',1)
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
