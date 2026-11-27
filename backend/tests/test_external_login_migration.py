import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def _head(backend, env):
    result = subprocess.run([sys.executable, '-m', 'alembic', 'heads'], cwd=backend,
                            env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    return result.stdout.split()[0]


def test_clean_full_alembic_chain_roundtrip(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    path = tmp_path / 'clean-roundtrip.db'
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + path.as_posix(), 'APP_ENV': 'test'}
    for action, revision in [('upgrade', 'head'), ('downgrade', 'base'), ('upgrade', 'head')]:
        result = subprocess.run([sys.executable, '-m', 'alembic', action, revision], cwd=backend,
                                env=env, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr
        with sqlite3.connect(path) as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            if revision == 'base':
                assert db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                  "AND name NOT IN ('sqlite_sequence', 'alembic_version')").fetchall() == []
            else:
                assert db.execute('SELECT version_num FROM alembic_version').fetchone() == (_head(backend, env),)


def test_external_login_upgrade_preserves_every_existing_table_row(tmp_path):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from app.core.security import hash_password
    from app.db.base import new_uuid, utcnow
    from app.db.models import ExternalPracticeRecord, StaffUser
    from app.db.models.mobile_account import MobileAccount
    backend = Path(__file__).resolve().parents[1]
    path = tmp_path/'existing-accounts.db'
    env = {**os.environ, 'DATABASE_URL':'sqlite:///'+path.as_posix(), 'APP_ENV':'test'}
    def migrate(revision):
        result = subprocess.run([sys.executable,'-m','alembic','upgrade',revision],cwd=backend,
            env=env,capture_output=True,text=True,timeout=90)
        assert result.returncode == 0, result.stderr
    migrate('n0c2d4e6f8a0')
    engine = create_engine(env['DATABASE_URL'])
    with Session(engine) as db:
        user = StaffUser(username='old_patient', password_hash=hash_password('test-password-12'),
                         display_name='原账号', role='PATIENT', is_active=True)
        db.add(user); db.flush()
        # The live ORM maps patient columns added after n0c2d4e6f8a0, so insert
        # the legacy column set directly to rehearse a real historical upgrade.
        now = utcnow(); patient_id = new_uuid()
        db.execute(text("INSERT INTO patients (id,hospital_number,name,sex,dominant_hand,affected_side,"
                        "medication_state,is_deleted,created_at,updated_at) VALUES "
                        "(:id,'P000001','原账号','UNKNOWN','UNKNOWN','UNKNOWN','UNKNOWN',0,:now,:now)"),
                   {'id':patient_id,'now':now})
        db.add(MobileAccount(user_id=user.id, patient_id=patient_id,
                             recovery_hash='a'*64, sync_consent_version='account-sync-v1'))
        db.add(ExternalPracticeRecord(patient_id=patient_id,operator_id=user.id,
            device_id='old-device',local_profile_id='old-profile',source_record_id='old-record',
            record_type='PIANO_SESSION',schema_version='old',payload_sha256='a'*64,payload_json='{"original":true}'))
        db.commit()
    engine.dispose()
    def snapshot():
        with sqlite3.connect(path) as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='alembic_version'")]
            result = {}
            for table in tables:
                columns = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
                rows = db.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
                result[table] = {column: [row[index] for row in rows]
                                 for index, column in enumerate(columns)}
            return result
    original = snapshot()
    assert 'mobile_identities' not in original
    migrate('head')
    updated = snapshot()
    assert set(updated)-set(original) == {'mobile_identities','mobile_login_challenges','mobile_auth_limits','staff_applications'}
    assert {t:{c:updated[t][c] for c in original[t]} for t in original} == original
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == (_head(backend, env),)
        db.execute("INSERT INTO mobile_identities (id,user_id,provider,app_id,subject,created_at,updated_at) "
                   "SELECT 'binding-id',user_id,'sms','','13800138000',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP "
                   "FROM mobile_accounts LIMIT 1")
    bound = snapshot()
    rollback = subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', 'n0c2d4e6f8a0'],
        cwd=backend, env=env, capture_output=True, text=True, timeout=90)
    assert rollback.returncode != 0
    assert 'preserve identity bindings' in rollback.stderr
    # The newer empty application table rolls back before the older identity
    # migration refuses destructive removal of live identity bindings.
    assert not any(bound['staff_applications'].values())
    current = snapshot()
    # The failed rollback stops at n0c2d4e6f8a0, so columns added by later
    # revisions are gone again; every surviving column must still match.
    assert {t:{c:current[t][c] for c in columns if c in current[t]}
            for t,columns in bound.items() if t!='staff_applications' and t in current} == \
           {t:{c:columns[c] for c in columns if c in current[t]}
            for t,columns in bound.items() if t!='staff_applications' and t in current}
