import json,os,shutil,subprocess,tarfile,time,urllib.request,sys
from pathlib import Path
from migration_common import *
WEB=Path('/opt/pd-rehab/app/PD-Rehab-Web');OLD='90d5e53162f9e673c931334dabb885daef46b272'
NEW=sys.argv[1];assert len(NEW)==40 and all(c in '0123456789abcdef' for c in NEW)
ROOT=Path('/var/www/pd-rehab')
def git(*a):return command('sudo','-u','ubuntu','git','-C',str(WEB),*a)
def request(path):
 with urllib.request.urlopen('http://127.0.0.1:18086/api/'+path,timeout=10) as r:return json.load(r)
def start_and_wait():
 subprocess.run(['systemctl','start','pd-rehab-backend'],check=True)
 for n in range(25):
  try:
   if request('system/health').get('status')=='ok' and request('system/models')['summary']['ready']==4:return
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('Target service failed readiness')
assert git('rev-parse','HEAD')==OLD and not git('status','--porcelain')
rehearsal=json.loads((STAGE/'rehearsal-result.json').read_text());assert rehearsal['oldDataAndSchemasIdentical']
assert request('system/models')['summary']['ready']==4
git('fetch',str(STAGE/'web-source.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==NEW
env=service_environment();before_services=states();builds=STAGE/'web-builds';assert not builds.exists();builds.mkdir(mode=0o700)
with tarfile.open(STAGE/'web-builds.tar') as t:
 for m in t.getmembers():
  assert (builds/m.name).resolve().is_relative_to(builds.resolve()) and not m.issym() and not m.islnk()
 t.extractall(builds)
for kind in ['web-root','web-subpath']:assert (builds/kind/'index.html').is_file()
indexes={d:(ROOT/d/'index.html').read_bytes() for d in ['dist','dist-under-path']}
for d,data in indexes.items():(STAGE/(d+'-index-before.html')).write_bytes(data)
source_changed=False
try:
 subprocess.run(['systemctl','stop','pd-rehab-backend'],check=True)
 backup(STAGE/'database-before-production-migration.sqlite')
 before=snapshot(DB)
 git('merge','--ff-only',NEW);source_changed=True
 log=migrate(WEB/'backend',DB,env)
 after=snapshot(DB);compare(before,after)
 for suffix in ['', '-wal','-shm']:
  f=Path(str(DB)+suffix)
  if f.exists():os.chown(f,1000,1000)
 start_and_wait()
 providers=request('mobile/auth/providers');assert providers['sms_enabled'] and not providers['wechat_enabled']
 for kind,destname in [('web-root','dist'),('web-subpath','dist-under-path')]:
  src=builds/kind;dest=ROOT/destname
  for item in src.rglob('*'):
   rel=item.relative_to(src)
   assert rel.parts[:2] not in [('assets','dance'),('assets','app-releases')]
   out=dest/rel
   if item.is_dir():
    assert not out.is_symlink();out.mkdir(exist_ok=True,parents=True);continue
   if rel.as_posix()=='index.html':continue
   out.parent.mkdir(exist_ok=True,parents=True)
   if out.exists() and out.read_bytes()==item.read_bytes():continue
   assert not out.is_symlink()
   if out.exists():
    copy=STAGE/'mutable-static-backup'/destname/rel;copy.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(out,copy)
   temp=out.with_name(out.name+'.media-sms-pending');shutil.copyfile(item,temp);temp.chmod(0o644);os.replace(temp,out)
  tmp=dest/'index.media-sms-pending.html';tmp.write_bytes((src/'index.html').read_bytes());tmp.chmod(0o644);os.replace(tmp,dest/'index.html')
 final_services=states();assert all(final_services[u]==before_services[u] for u in UNITS if u!='pd-rehab-backend')
 assert 'ActiveState=active' in final_services['pd-rehab-backend']
 assert not git('status','--porcelain')
 result={'oldSha':OLD,'newSha':NEW,'oldMigration':'n0c2d4e6f8a0','newMigration':'o1d3e5f7a9b1','oldTablesUnchanged':len(before),'newTables':sorted(set(after)-set(before)),'integrity':'ok','foreignKeys':'ok','providers':providers,'modelsReady':4,'onlyTargetRestarted':True,'servicesBefore':before_services,'servicesAfter':final_services}
 (STAGE/'web-deployment-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except Exception:
 subprocess.run(['systemctl','stop','pd-rehab-backend'],check=True)
 if source_changed and not git('status','--porcelain'):git('switch','--detach',OLD)
 for d,data in indexes.items():
  tmp=ROOT/d/'index.rollback-pending.html';tmp.write_bytes(data);tmp.chmod(0o644);os.replace(tmp,ROOT/d/'index.html')
 backupdir=STAGE/'mutable-static-backup'
 if backupdir.exists():
  for item in backupdir.rglob('*'):
   if item.is_file():shutil.copyfile(item,ROOT/item.relative_to(backupdir))
 start_and_wait()
 raise
