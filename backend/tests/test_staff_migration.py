"""Rehearse the additive migration on empty and populated isolated SQLite."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_staff_additive_migration_preserves_all_business_rows(tmp_path):
    backend=Path(__file__).resolve().parents[1]
    def migrate(path,version):
        env={**os.environ,'APP_ENV':'test','DATABASE_URL':'sqlite:///'+path.as_posix()}
        r=subprocess.run([sys.executable,'-m','alembic','upgrade',version],cwd=backend,env=env,capture_output=True,text=True,timeout=90)
        assert r.returncode==0,r.stderr
    empty=tmp_path/'fresh.db';migrate(empty,'head')
    with sqlite3.connect(empty) as c:
        assert c.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    old=tmp_path/'old.db';migrate(old,'o1d3e5f7a9b1')
    with sqlite3.connect(old) as c:
        c.execute("INSERT INTO staff_users (id,username,password_hash,display_name,role,is_active,created_at,updated_at) VALUES ('old-admin','oldadmin','hashed-original','Admin','ADMIN',1,'2026-11-18','2026-11-18')")
        c.execute("INSERT INTO patients (id,hospital_number,name,sex,dominant_hand,affected_side,medication_state,is_deleted,created_at,updated_at) VALUES ('old-patient','P123','Original patient','UNKNOWN','UNKNOWN','UNKNOWN','UNKNOWN',0,'2026-11-18','2026-11-18')")
        c.execute("INSERT INTO assessment_sessions (id,patient_id,session_type,status,medication_state,created_by,created_at,updated_at) VALUES ('old-assessment','old-patient','COMPREHENSIVE','COMPLETED','UNKNOWN','old-admin','2026-11-18','2026-11-18')")
        c.commit()
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence')")]
        rows={t:c.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
    migrate(old,'head')
    with sqlite3.connect(old) as c:
        for table,before in rows.items():assert c.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()==before,table
        assert c.execute('SELECT count(*) FROM staff_applications').fetchone()[0]==0
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
