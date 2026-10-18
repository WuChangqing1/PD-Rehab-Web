"""The deployment fingerprint supports nullable foreign keys and detects renumbering."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

def test_release_guard_nullable_relationships_and_identity_changes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = Path(os.environ.get('RELEASE_GUARD_BASELINE', root / 'scripts/defect01_database_guard.py'))
    database = tmp_path / 'pd.db'
    backup = tmp_path / 'backup'
    backup.mkdir()
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE patients(id TEXT PRIMARY KEY,hospital_number TEXT UNIQUE,name TEXT);
            CREATE TABLE assessments(id TEXT PRIMARY KEY,patient_id TEXT REFERENCES patients(id));
            CREATE TABLE events(id TEXT PRIMARY KEY,assessment_id TEXT REFERENCES assessments(id));
            CREATE TABLE alembic_version(version_num TEXT PRIMARY KEY);
            INSERT INTO patients VALUES('virtual-id','P000042','virtual-only');
            INSERT INTO assessments VALUES('history-id','virtual-id');
            INSERT INTO events VALUES('event-1',NULL),('event-2','history-id');
            INSERT INTO alembic_version VALUES('h4c6d8e0f2a3');
        """)
    text = source.read_text(encoding='utf-8')
    # Baseline and retry scripts use fixed, separate production staging names.
    for suffix in ['-r2','']:
        text = text.replace('/tmp/pd-defect01-20261018' + suffix, tmp_path.as_posix())
        text = text.replace('/opt/pd-rehab/backups/defect01-20261018' + suffix, backup.as_posix())
    text = text.replace('/opt/pd-rehab/data/pd.db', database.as_posix())
    runner = tmp_path / 'guard.py'
    runner.write_text(text, encoding='utf-8')
    def run(mode):
        return subprocess.run([sys.executable,str(runner),mode],capture_output=True,text=True)
    before = run('before')
    assert before.returncode == 0, before.stderr
    assert (backup / 'pd.db').is_file()
    with sqlite3.connect(database) as db:
        db.executescript("CREATE TABLE patient_number_allocations(id INTEGER PRIMARY KEY AUTOINCREMENT); UPDATE alembic_version SET version_num='i5d7e9f1a3b4';")
    after = run('after')
    assert after.returncode == 0, after.stderr
    with sqlite3.connect(database) as db:
        db.execute("UPDATE patients SET hospital_number='WRONG'")
    assert run('after').returncode != 0
