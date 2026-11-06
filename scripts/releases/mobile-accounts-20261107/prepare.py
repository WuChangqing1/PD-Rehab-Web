import hashlib,json,os,sqlite3,subprocess as sp,tarfile
from pathlib import Path
W=Path('/opt/pd-rehab/releases/mobile-accounts-20261107')
A=Path('/opt/pd-rehab/app/PD-Rehab-Web')
OLD='7e1c73153fc5de63a28c2def883dddb8402bd3f3'
def out(*a):return sp.check_output(a,text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(path):
    with sqlite3.connect(str(path)) as db:
        names=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' and name!='alembic_version' order by name")]
        result={}
        for name in names:
            h=hashlib.sha256();n=0
            for row in db.execute('select * from "'+name+'" order by rowid'):
                h.update(json.dumps(row,ensure_ascii=True,default=str,separators=(',',':')).encode());h.update(b'\n');n+=1
            result[name]={'rows':n,'sha256':h.hexdigest()}
        return result
assert out('git','-C',str(A),'rev-parse','HEAD')==OLD
assert not out('git','-C',str(A),'status','--porcelain')
manifest=json.loads((W/'manifest.json').read_text())
for name,h in manifest['files'].items():assert digest(W/name)==h,name
source=W/'source';source.mkdir(exist_ok=True)
with tarfile.open(W/'source.tar.gz') as tar:
    for entry in tar.getmembers():
        target=(source/entry.name).resolve()
        assert target.is_relative_to(source.resolve()) and not entry.issym() and not entry.islnk()
    tar.extractall(source)
backup=W/'preflight.sqlite'
assert not backup.exists(),'Preserve earlier backup; use unique release directory'
with sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro',uri=True) as original,sqlite3.connect(backup) as target:original.backup(target)
backup.chmod(0o600)
rehearsal=W/'rehearsal.sqlite'
with sqlite3.connect(backup) as original,sqlite3.connect(rehearsal) as target:original.backup(target)
rehearsal.chmod(0o600)
before=snapshot(backup)
env=os.environ.copy();env.update(DATABASE_URL='sqlite:///'+str(rehearsal),APP_ENV='test')
with (W/'rehearsal-migration.log').open('w') as log:
    sp.run(['/opt/pd-rehab/venv/bin/python','-m','alembic','upgrade','head'],cwd=source/'backend',env=env,stdout=log,stderr=sp.STDOUT,check=True)
after=snapshot(rehearsal)
assert all(after[name]==item for name,item in before.items()),'Existing data changed'
assert set(after)-set(before)=={'mobile_accounts','mobile_sessions'}
with sqlite3.connect(rehearsal) as db:
    assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert db.execute('pragma foreign_key_check').fetchall()==[]
    assert db.execute('select version_num from alembic_version').fetchone()[0]=='n0c2d4e6f8a0'
(W/'rehearsal-evidence.json').write_text(json.dumps({'old_revision':OLD,'candidate':manifest['revision'],'old_tables':before,'new_tables':sorted(set(after)-set(before)),'all_original_rows_equal':True,'integrity':'ok','foreign_keys':0},indent=2))
print(json.dumps({'migration_rehearsal':'passed','original_tables_preserved':len(before),'new_tables':sorted(set(after)-set(before)),'integrity':'ok','foreign_keys':0}))
