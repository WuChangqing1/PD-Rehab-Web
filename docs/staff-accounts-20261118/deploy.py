import json,os,shutil,subprocess,tarfile,time,urllib.request,sqlite3,hashlib,sys
from pathlib import Path
from pd_common import env,backup,snapshot as business_snapshot
STAGE=Path('/opt/pd-rehab/releases/staff-accounts-20261118');WEB=Path('/opt/pd-rehab/app/PD-Rehab-Web');ROOT=Path('/var/www/pd-rehab');DB=Path('/opt/pd-rehab/data/pd.db');OLD='1c15a6304557e320748c7a511d54b1d2d4f1ace2';NEW=sys.argv[1]
assert len(NEW)==40 and all(c in '0123456789abcdef' for c in NEW)
UNITS=['pd-rehab-backend','nginx','exercises','foodcircle-api','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api']
def cmd(*a):return subprocess.check_output(a,text=True).strip()
def git(*a):return cmd('sudo','-u','ubuntu','git','-C',str(WEB),*a)
def states():return {u:cmd('systemctl','show',u,'-p','ActiveState','-p','MainPID') for u in UNITS}
def request(path):
 with urllib.request.urlopen('http://127.0.0.1:18086/api/'+path,timeout=10) as r:return json.load(r)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def snapshot():
 with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as c:
  assert c.execute('pragma integrity_check').fetchone()[0]=='ok';assert not c.execute('pragma foreign_key_check').fetchall();assert c.execute('select version_num from alembic_version').fetchall()==[('o1d3e5f7a9b1',)]
  result={}
  for name,sql in c.execute("select name,sql from sqlite_master where type='table' order by name").fetchall():
   q='"'+name.replace('"','""')+'"';h=hashlib.sha256();n=0
   for row in c.execute('select * from '+q+' order by rowid'):
    h.update(json.dumps(row,ensure_ascii=False,default=lambda v:v.hex() if isinstance(v,bytes) else str(v)).encode());n+=1
   result[name]={'schema':sql,'count':n,'sha':h.hexdigest()}
  return result

def start():
 subprocess.run(['systemctl','start','pd-rehab-backend'],check=True)
 for _ in range(30):
  try:
   if request('system/health')['status']=='ok' and request('system/models')['summary']['ready']==4:return
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('PD readiness failed')
assert git('rev-parse','HEAD')==OLD and not git('status','--porcelain')
assert request('system/models')['summary']['ready']==4
for line in (STAGE/'SHA256SUMS.txt').read_text().splitlines():
 sha,name=line.split('  ',1);assert digest(STAGE/name)==sha,name
before=states();git('fetch',str(STAGE/'web-source.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==NEW
assert git('diff','--name-only',OLD,NEW,'--','backend/requirements.txt')=='','Unexpected dependencies'
rehearsal=json.loads((STAGE/'rehearsal-result.json').read_text());assert rehearsal['sourceSha']==NEW and rehearsal['addedTables']==['staff_applications']
production_env=env()
builds=STAGE/'builds';assert not builds.exists();builds.mkdir(mode=0o700)
with tarfile.open(STAGE/'web-builds.tar') as archive:
 for m in archive.getmembers():assert (builds/m.name).resolve().is_relative_to(builds.resolve()) and not m.issym() and not m.islnk()
 archive.extractall(builds)
indexes={d:(ROOT/d/'index.html').read_bytes() for d in ['dist','dist-under-path']}
for d,data in indexes.items():(STAGE/(d+'-before.html')).write_bytes(data)
changed=False
try:
 subprocess.run(['systemctl','stop','pd-rehab-backend'],check=True);backup(STAGE/'database-before.sqlite');data_before=business_snapshot()
 git('merge','--ff-only',NEW);changed=True
 migration_env=dict(production_env);migration_env['PYTHONPATH']=str(WEB/'backend')
 migration=subprocess.run(['/opt/pd-rehab/venv/bin/python','-m','alembic','upgrade','head'],cwd=WEB/'backend',env=migration_env,capture_output=True,text=True)
 if migration.returncode:raise RuntimeError(migration.stderr[-2000:])
 data_after=business_snapshot();assert all(data_after.get(t)==v for t,v in data_before.items()),'Migration changed old tables'
 assert set(data_after)-set(data_before)=={'staff_applications'}
 for suffix in ['', '-wal','-shm']:
  f=Path(str(DB)+suffix)
  if f.exists():os.chown(f,1000,1000)
 start();providers=request('mobile/auth/providers');assert providers['sms_enabled'] and not providers['wechat_enabled']
 for kind,destname in [('web-root','dist'),('web-subpath','dist-under-path')]:
  src=builds/kind;dest=ROOT/destname;assert (src/'index.html').is_file()
  for item in src.rglob('*'):
   rel=item.relative_to(src);assert rel.parts[:2] not in [('assets','dance'),('assets','app-releases')]
   out=dest/rel
   if item.is_dir():assert not out.is_symlink();out.mkdir(parents=True,exist_ok=True);continue
   if rel.as_posix()=='index.html':continue
   out.parent.mkdir(parents=True,exist_ok=True);assert not out.is_symlink()
   if out.exists():
    if out.read_bytes()==item.read_bytes():continue
    backup=STAGE/'mutable-backup'/destname/rel;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(out,backup)
   tmp=out.with_name(out.name+'.patient-pace-pending');shutil.copyfile(item,tmp);tmp.chmod(0o644);os.replace(tmp,out)
  tmp=dest/'index.patient-pace-pending.html';tmp.write_bytes((src/'index.html').read_bytes());tmp.chmod(0o644);os.replace(tmp,dest/'index.html')
 after=states();assert all(before[u]==after[u] for u in UNITS if u!='pd-rehab-backend');assert not git('status','--porcelain')
 with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as c:assert c.execute('select version_num from alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
 result={'oldSha':OLD,'newSha':NEW,'oldMigration':'o1d3e5f7a9b1','migration':'p2e4f6a8b0c2','migrationExecuted':True,'addedTables':['staff_applications'],'oldTablesPreserved':True,'tablesChecked':len(data_before),'modelsReady':4,'smsEnabled':providers['sms_enabled'],'onlyPdRestarted':True,'servicesBefore':before,'servicesAfter':after}
 (STAGE/'web-deployment-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except Exception:
 subprocess.run(['systemctl','stop','pd-rehab-backend'],check=True)
 if changed and not git('status','--porcelain'):git('switch','--detach',OLD)
 for d,data in indexes.items():
  tmp=ROOT/d/'index.rollback-pending.html';tmp.write_bytes(data);tmp.chmod(0o644);os.replace(tmp,ROOT/d/'index.html')
 if (STAGE/'mutable-backup').exists():
  for item in (STAGE/'mutable-backup').rglob('*'):
   if item.is_file():shutil.copyfile(item,ROOT/item.relative_to(STAGE/'mutable-backup'))
 start();raise
