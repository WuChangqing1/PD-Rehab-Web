import sqlite3,subprocess,sys
from pathlib import Path

def test_guard_allows_appended_records_but_rejects_modified_existing_result(tmp_path):
    root=Path(__file__).resolve().parents[2]
    database=tmp_path/'pd.db';backup=tmp_path/'backup';backup.mkdir()
    with sqlite3.connect(database) as db:
        db.executescript("""
        CREATE TABLE patients(id TEXT PRIMARY KEY,name TEXT,is_deleted INTEGER,hospital_number TEXT);
        CREATE TABLE results(id TEXT PRIMARY KEY,patient_id TEXT REFERENCES patients(id),value REAL);
        CREATE TABLE alembic_version(version_num TEXT PRIMARY KEY);
        INSERT INTO patients VALUES('abfd9bed-4644-5fd2-812f-3a7eaca11a84','Before',0,'RESERVED');
        INSERT INTO results VALUES('existing','abfd9bed-4644-5fd2-812f-3a7eaca11a84',0.7);
        INSERT INTO alembic_version VALUES('i5d7e9f1a3b4');
        """)
    source=(root/'scripts/focused_database_guard.py').read_text(encoding='utf-8')
    source=source.replace('/opt/pd-rehab/data/pd.db',database.as_posix()).replace('/opt/pd-rehab/backups/focused-polish-20261021',backup.as_posix())
    runner=tmp_path/'guard.py';runner.write_text(source,encoding='utf-8')
    def run(mode):return subprocess.run([sys.executable,str(runner),mode],capture_output=True,text=True)
    before=run('before');assert before.returncode==0,before.stderr
    with sqlite3.connect(database) as db:
        db.execute("UPDATE patients SET name='小明'")
        db.execute("INSERT INTO results VALUES('appended','abfd9bed-4644-5fd2-812f-3a7eaca11a84',0.9)")
    after=run('after');assert after.returncode==0,after.stderr
    with sqlite3.connect(database) as db:db.execute("UPDATE results SET value=0.1 WHERE id='existing'")
    assert run('after').returncode!=0
