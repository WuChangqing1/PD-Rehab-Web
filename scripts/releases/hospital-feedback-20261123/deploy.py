"""Usage as root: deploy.py STAGE. No migration or shared-service restart."""
import hashlib,json,os,shutil,sqlite3,subprocess,tarfile,time,urllib.request
from pathlib import Path
import sys
stage=Path(sys.argv[1]).resolve()
assert stage==Path('/opt/pd-rehab/releases/hospital-feedback-20261123')
repo=Path('/opt/pd-rehab/app/PD-Rehab-Web');web=Path('/var/www/pd-rehab');database=Path('/opt/pd-rehab/data/pd.db')
units=['nginx','exercises','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api','motion-atlas-341']
def cmd(*args):return subprocess.check_output(args,text=True).strip()
def run(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def git(*args):return cmd('git','-c','safe.directory='+str(repo),'-C',str(repo),*args)
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def states():return {u:cmd('systemctl','show',u,'-p','MainPID','-p','ActiveState') for u in units}
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:18086/api/'+path,timeout=10) as response:return json.load(response)
def ready(expected):
 deadline=time.monotonic()+120
 while time.monotonic()<deadline:
  try:
   if get('system/health')['status']=='ok':
    models=get('system/models')['summary']['models']
    if all(any(m['name']==name and m['is_ready'] and m['version']==version for m in models) for name,version in expected.items()):return
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('Target readiness timeout')
def extract(path,target):
 target.mkdir(mode=0o700)
 with tarfile.open(path) as archive:
  assert all(not m.issym() and not m.islnk() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in archive.getmembers())
  archive.extractall(target,filter='data')
m=json.loads((stage/'manifest.json').read_text());old=m['old'];new=m['new']
assert git('rev-parse','HEAD')==old and not git('status','--porcelain')
for name,expected in m['files'].items():assert digest(stage/name)==expected,name
models={x['name']:x['version'] for x in get('system/models')['summary']['models'] if x['is_ready']};assert len(models)==4
before=states();pid=cmd('systemctl','show','pd-rehab-backend','--value','-p','MainPID')
env=dict(x.decode().split('=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x)
assert env.get('DATABASE_URL')=='sqlite:////opt/pd-rehab/data/pd.db'
argv=Path('/proc/'+pid+'/cmdline').read_bytes().split(b'\0');assert b'--workers' in argv and argv[argv.index(b'--workers')+1]==b'1'
for d in ['dist','dist-under-path']:assert (web/d/'assets/app-releases').resolve()==web/'app-releases'
apk=web/'app-releases/0.1.73-75/qinban-0.1.73-android-universal.apk';apk_before=digest(apk)
git('fetch',str(stage/'release.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==new
extract(stage/'frontend.tar.gz',stage/'builds')
extract(stage/'backend.tar.gz',stage/'candidate')
testenv={**env,'DATABASE_URL':'sqlite://','PYTHONPATH':str(stage/'candidate/backend')}
with (stage/'preflight.log').open('w') as log:run('/opt/pd-rehab/venv/bin/python',str(stage/'preflight.py'),cwd=stage/'candidate/backend',env=testenv,stdout=log,stderr=subprocess.STDOUT)
backup=stage/'backup';backup.mkdir(mode=0o700)
for d in ['dist','dist-under-path']:shutil.copy2(web/d/'index.html',backup/(d+'.html'))
(backup/'state.json').write_text(json.dumps({'old':old,'new':new,'models':models,'services':before},indent=2))
changed=False
try:
 run('systemctl','stop','pd-rehab-backend')
 fd=os.open(backup/'pd.sqlite',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
 with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as source,sqlite3.connect(backup/'pd.sqlite') as dest:source.backup(dest)
 db_before=digest(database)
 with sqlite3.connect(database) as db:assert db.execute('select version_num from alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
 git('merge','--ff-only',new);changed=True
 assert digest(database)==db_before,'Unexpected database write while stopped'
 run('systemctl','start','pd-rehab-backend');ready(models)
 for kind,d in [('root','dist'),('under','dist-under-path')]:
  source=stage/'builds'/kind
  assert (source/'index.html').is_file()
  for file in source.rglob('*'):
   if not file.is_file() or file==source/'index.html':continue
   rel=file.relative_to(source)
   assert rel.parts[:2] not in [('assets','app-releases'),('assets','dance')]
   dest=web/d/rel
   assert dest.resolve().is_relative_to(web.resolve()) and not dest.is_symlink()
   if dest.is_file() and digest(dest)==digest(file):continue
   if dest.exists():
    copy=backup/'static'/d/rel;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,copy)
   dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_name(dest.name+'.hospital-pending');shutil.copyfile(file,temp);temp.chmod(0o644);os.replace(temp,dest)
  temp=web/d/'index.html.hospital-pending';shutil.copyfile(source/'index.html',temp);temp.chmod(0o644);os.replace(temp,web/d/'index.html')
 assert states()==before,'Unrelated service changed'
 assert digest(apk)==apk_before
 with sqlite3.connect(database) as db:
  assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
  assert not db.execute('pragma foreign_key_check').fetchall()
  assert db.execute('select version_num from alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
 assert not git('status','--porcelain')
 result={'old':old,'new':git('rev-parse','HEAD'),'modelsReady':len(models),'otherServicesUnchanged':True,'databaseMigration':False,'databaseUnchangedDuringUpdate':True,'databaseIntegrity':'ok','apkUnchanged':True,'backup':str(backup),'servicesBefore':before,'servicesAfter':states()}
 (stage/'deployment-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except BaseException:
 run('systemctl','stop','pd-rehab-backend')
 if changed:
  assert not git('status','--porcelain');git('switch','--detach',old)
 for d in ['dist','dist-under-path']:shutil.copyfile(backup/(d+'.html'),web/d/'index.html')
 for file in (backup/'static').rglob('*'):
  if file.is_file():shutil.copy2(file,web/file.relative_to(backup/'static'))
 run('systemctl','start','pd-rehab-backend');ready(models)
 raise
