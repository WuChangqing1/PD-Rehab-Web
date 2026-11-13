import os
from pathlib import Path
import sqlite3
import subprocess
import sys


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
                assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('o1d3e5f7a9b1',)


def test_external_login_upgrade_preserves_every_existing_table_row(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.api.mobile_auth import create_patient_account
    from app.db.models import ExternalPracticeRecord
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
        user, _ = create_patient_account(db,'old_patient','test-password-12','原账号','account-sync-v1')
        from app.db.models.mobile_account import MobileAccount
        account = db.get(MobileAccount,user.id)
        db.add(ExternalPracticeRecord(patient_id=account.patient_id,operator_id=user.id,
            device_id='old-device',local_profile_id='old-profile',source_record_id='old-record',
            record_type='PIANO_SESSION',schema_version='old',payload_sha256='a'*64,payload_json='{"original":true}'))
        db.commit()
    engine.dispose()
    def snapshot():
        with sqlite3.connect(path) as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='alembic_version'")]
            return {t:db.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
    original = snapshot()
    assert 'mobile_identities' not in original
    migrate('head')
    updated = snapshot()
    assert set(updated)-set(original) == {'mobile_identities','mobile_login_challenges','mobile_auth_limits'}
    assert {t:updated[t] for t in original} == original
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('o1d3e5f7a9b1',)
        db.execute("INSERT INTO mobile_identities (id,user_id,provider,app_id,subject,created_at,updated_at) "
                   "SELECT 'binding-id',user_id,'sms','','13800138000',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP "
                   "FROM mobile_accounts LIMIT 1")
    bound = snapshot()
    rollback = subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', 'n0c2d4e6f8a0'],
        cwd=backend, env=env, capture_output=True, text=True, timeout=90)
    assert rollback.returncode != 0
    assert 'preserve identity bindings' in rollback.stderr
    assert snapshot() == bound
