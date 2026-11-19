import json,os,sqlite3,subprocess,tarfile,sys
from pathlib import Path
from pd_common import *
NEW=sys.argv[1];assert len(NEW)==40
assert git('rev-parse','HEAD')==OLD and not git('status','--porcelain')
git('fetch',str(STAGE/'web-source.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==NEW
source=STAGE/'source';assert not source.exists();source.mkdir(mode=0o700)
archive=STAGE/'backend-source.tar'
with archive.open('wb') as out:subprocess.run(['sudo','-u','ubuntu','git','-C',str(WEB),'archive',NEW,'backend'],stdout=out,check=True)
with tarfile.open(archive) as t:
 for item in t.getmembers():assert (source/item.name).resolve().is_relative_to(source.resolve()) and not item.issym() and not item.islnk()
 t.extractall(source)
db=STAGE/'rehearsal.sqlite';before=snapshot(db);e=env();e['DATABASE_URL']='sqlite:///'+str(db);e['PYTHONPATH']=str(source/'backend')
r=subprocess.run(['/opt/pd-rehab/venv/bin/python','-m','alembic','upgrade','head'],cwd=source/'backend',env=e,capture_output=True,text=True)
if r.returncode:raise RuntimeError(r.stderr[-2000:])
after=snapshot(db);assert all(after[t]==v for t,v in before.items());assert set(after)-set(before)=={'staff_applications'}
with sqlite3.connect(db) as c:assert c.execute('select version_num from alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
result={'sourceSha':NEW,'oldVersion':'o1d3e5f7a9b1','newVersion':'p2e4f6a8b0c2','businessTablesUnchanged':len(before),'addedTables':['staff_applications'],'integrity':'ok','foreignKeys':'ok','productionUnchanged':git('rev-parse','HEAD')==OLD,'servicesUnchanged':states()==json.loads((STAGE/'baseline.json').read_text())['services']}
assert result['servicesUnchanged'];(STAGE/'rehearsal-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
