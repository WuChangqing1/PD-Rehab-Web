import json,os,shutil,subprocess,tarfile,time,urllib.request,sqlite3,hashlib,sys
from pathlib import Path
STAGE=Path('/opt/pd-rehab/releases/patient-experience-20261113');WEB=Path('/opt/pd-rehab/app/PD-Rehab-Web');ROOT=Path('/var/www/pd-rehab');DB=Path('/opt/pd-rehab/data/pd.db');OLD='ecb8323931d307aef9bee4bf1f99949f142884c0';NEW=sys.argv[1]
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
assert git('diff','--name-only',OLD,NEW,'--','backend/alembic','backend/requirements.txt')=='','Unexpected migration/dependencies'
builds=STAGE/'builds';assert not builds.exists();builds.mkdir(mode=0o700)
with tarfile.open(STAGE/'web-builds.tar') as archive:
 for m in archive.getmembers():assert (builds/m.name).resolve().is_relative_to(builds.resolve()) and not m.issym() and not m.islnk()
 archive.extractall(builds)
indexes={d:(ROOT/d/'index.html').read_bytes() for d in ['dist','dist-under-path']}
for d,data in indexes.items():(STAGE/(d+'-before.html')).write_bytes(data)
changed=False
try:
 subprocess.run(['systemctl','stop','pd-rehab-backend'],check=True);data_before=snapshot()
 git('merge','--ff-only',NEW);changed=True
 assert snapshot()==data_before,'Code switch changed database'
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
 with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as c:assert c.execute('select version_num from alembic_version').fetchone()[0]=='o1d3e5f7a9b1'
 result={'oldSha':OLD,'newSha':NEW,'migration':'o1d3e5f7a9b1','migrationExecuted':False,'databasePreservedDuringCodeSwitch':True,'tablesChecked':len(data_before),'modelsReady':4,'smsEnabled':providers['sms_enabled'],'onlyPdRestarted':True,'servicesBefore':before,'servicesAfter':after}
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
