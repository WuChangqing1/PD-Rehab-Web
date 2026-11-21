"""Target-only static release. Run as root: deploy.py STAGE NEW_COMMIT BUNDLE_SHA256."""
import hashlib,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
stage=Path(sys.argv[1]).resolve();new=sys.argv[2];bundle_sha=sys.argv[3]
assert stage.parent==Path('/opt/pd-rehab/releases') and stage.name=='app-download-20261121'
repo=Path('/opt/pd-rehab/app/PD-Rehab-Web');web=Path('/var/www/pd-rehab')
old='4794609ad37dcc77d4421af2d7f7a3a39650b7c6'
apk_sha='88079438cc9f191a995fc438427929a0aad5ba422159f378fdb87323fde64986'
def cmd(*args):return subprocess.check_output(args,text=True).strip()
def git(*args):return cmd('git','-c','safe.directory='+str(repo),'-C',str(repo),*args)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def states():return {s:cmd('systemctl','show',s,'-p','MainPID','-p','ActiveState') for s in ['pd-rehab-backend','nginx','exercises']}
assert git('rev-parse','HEAD')==old and not git('status','--porcelain')
assert digest(stage/'frontend.tar.gz')==bundle_sha
assert (stage/'app.apk').stat().st_size==102942933 and digest(stage/'app.apk')==apk_sha
for d in ['dist','dist-under-path']:assert (web/d/'assets/app-releases').resolve()==web/'app-releases'
with tarfile.open(stage/'frontend.tar.gz') as t:
 assert all(not m.issym() and not m.islnk() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in t.getmembers())
 t.extractall(stage/'bundle',filter='data')
before=states();backup=stage/'backup';backup.mkdir(mode=0o700,exist_ok=True)
for d in ['dist','dist-under-path']:shutil.copy2(web/d/'index.html',backup/(d+'.html'))
(backup/'state.json').write_text(json.dumps({'old':old,'new':new,'services':before},indent=2))
git('fetch',str(stage/'release.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==new
try:
 version=web/'app-releases/0.1.73-75';version.mkdir(mode=0o755,exist_ok=True)
 target=version/'qinban-0.1.73-android-universal.apk'
 if target.exists():assert digest(target)==apk_sha
 else:shutil.copyfile(stage/'app.apk',target);target.chmod(0o644)
 (version/'SHA256SUMS.txt').write_text(apk_sha+'  '+target.name+'\n')
 for src,d in [('root','dist'),('under','dist-under-path')]:
  source=stage/'bundle'/src
  for f in source.rglob('*'):
   if not f.is_file() or f==source/'index.html':continue
   dest=web/d/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest);dest.chmod(0o644)
  temp=web/d/'index.html.app-download';shutil.copyfile(source/'index.html',temp);temp.chmod(0o644);os.replace(temp,web/d/'index.html')
 git('merge','--ff-only',new)
 assert states()==before
except BaseException:
 for d in ['dist','dist-under-path']:shutil.copyfile(backup/(d+'.html'),web/d/'index.html')
 raise
print(json.dumps({'commit':git('rev-parse','HEAD'),'servicesUnchanged':states()==before,'databaseChanged':False,'backup':str(backup),'apkSha256':digest(target)}))
