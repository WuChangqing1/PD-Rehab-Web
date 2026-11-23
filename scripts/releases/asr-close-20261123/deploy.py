"""Static-only connection-finalization fix. No backend restart, migration or proxy reload."""
import hashlib,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
stage=Path(sys.argv[1]).resolve();assert stage==Path('/opt/pd-rehab/releases/asr-close-20261123')
repo=Path('/opt/pd-rehab/app/PD-Rehab-Web');web=Path('/var/www/pd-rehab')
def cmd(*a):return subprocess.check_output(a,text=True).strip()
def git(*a):return cmd('git','-c','safe.directory='+str(repo),'-C',str(repo),*a)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
units=['pd-rehab-backend','nginx','exercises','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api','motion-atlas-341']
def states():return{u:cmd('systemctl','show',u,'-p','MainPID','-p','ActiveState') for u in units}
def atomic(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_name(dest.name+'.asr-close-pending');shutil.copyfile(src,temp);temp.chmod(0o644);os.replace(temp,dest)
m=json.loads((stage/'manifest.json').read_text());assert git('rev-parse','HEAD')==m['old'] and not git('status','--porcelain')
for name,value in m['files'].items():assert sha(stage/name)==value
before=states();git('fetch',str(stage/'release.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==m['new']
assert not any(p.startswith(('backend/','deploy/')) for p in git('diff','--name-only',m['old'],m['new']).splitlines())
with tarfile.open(stage/'frontend.tar.gz') as archive:
 assert all(not f.issym() and not f.islnk() and not Path(f.name).is_absolute() and '..' not in Path(f.name).parts for f in archive.getmembers())
 archive.extractall(stage/'builds',filter='data')
backup=stage/'backup';backup.mkdir(mode=0o700)
for d in ['dist','dist-under-path']:shutil.copy2(web/d/'index.html',backup/(d+'.html'))
changed=False
try:
 git('merge','--ff-only',m['new']);changed=True
 for kind,d in [('root','dist'),('under','dist-under-path')]:
  source=stage/'builds'/kind
  assert (source/'index.html').is_file()
  for f in source.rglob('*'):
   if not f.is_file() or f==source/'index.html':continue
   rel=f.relative_to(source);assert rel.parts[:2] not in [('assets','app-releases'),('assets','dance')]
   dest=web/d/rel;assert dest.resolve().is_relative_to(web.resolve()) and not dest.is_symlink()
   if dest.is_file() and sha(dest)==sha(f):continue
   if dest.exists():
    copy=backup/'static'/d/rel;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,copy)
   atomic(f,dest)
  atomic(source/'index.html',web/d/'index.html')
 assert states()==before
 assert not git('status','--porcelain')
 result={'commit':m['new'],'backendRestarted':False,'databaseMigration':False,'proxyReloaded':False,'servicesBefore':before,'servicesAfter':states()}
 (stage/'deployment-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except BaseException:
 if changed:
  assert not git('status','--porcelain');git('switch','--detach',m['old'])
 for d in ['dist','dist-under-path']:shutil.copy2(backup/(d+'.html'),web/d/'index.html')
 for f in (backup/'static').rglob('*'):
  if f.is_file():shutil.copy2(f,web/f.relative_to(backup/'static'))
 raise
