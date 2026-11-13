import sys,hashlib,os,shutil,tarfile,json,subprocess
from pathlib import Path
from migration_common import STAGE,states,command
WEB=Path('/opt/pd-rehab/app/PD-Rehab-Web');ROOT=Path('/var/www/pd-rehab')
OLD='e2ad3f5d9b13340b9f1f39e758c687475c4fa1bb';NEW=sys.argv[1];expected=sys.argv[2]
def git(*a):return command('sudo','-u','ubuntu','git','-C',str(WEB),*a)
assert git('rev-parse','HEAD')==OLD and not git('status','--porcelain')
h=hashlib.sha256()
with (STAGE/'frontend-context.tar').open('rb') as f:
 for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
assert h.hexdigest()==expected
git('fetch',str(STAGE/'frontend-context.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==NEW
names=git('diff','--name-only',OLD,NEW).splitlines();assert all(n=='README.md' or n.startswith(('frontend/','docs/','deploy/media-sms-20261113/')) for n in names)
source=STAGE/'frontend-context-build';assert not source.exists();source.mkdir(mode=0o700)
with tarfile.open(STAGE/'frontend-context.tar') as t:
 for m in t.getmembers():assert (source/m.name).resolve().is_relative_to(source.resolve()) and not m.issym() and not m.islnk()
 t.extractall(source)
before=states();indexes={d:(ROOT/d/'index.html').read_bytes() for d in ['dist','dist-under-path']}
for d,data in indexes.items():(STAGE/('frontend-context-'+d+'-before.html')).write_bytes(data)
try:
 git('merge','--ff-only',NEW)
 for kind,d in [('web-root','dist'),('web-subpath','dist-under-path')]:
  src=source/kind;dest=ROOT/d
  for p in src.rglob('*'):
   rel=p.relative_to(src);assert rel.parts[:2] not in [('assets','dance'),('assets','app-releases')]
   out=dest/rel;assert out.resolve().is_relative_to(ROOT.resolve()) and not out.is_symlink()
   if p.is_dir():out.mkdir(exist_ok=True,parents=True);continue
   if rel.as_posix()=='index.html':continue
   if out.exists() and out.read_bytes()==p.read_bytes():continue
   assert not out.exists(),'Unexpected mutable asset change in navigation-only patch'
   out.parent.mkdir(exist_ok=True,parents=True);tmp=out.with_name(out.name+'.patient-context-pending');shutil.copyfile(p,tmp);tmp.chmod(0o644);os.replace(tmp,out)
  tmp=dest/'index.patient-context-pending.html';tmp.write_bytes((src/'index.html').read_bytes());tmp.chmod(0o644);os.replace(tmp,dest/'index.html')
 assert states()==before
 result={'oldSha':OLD,'newSha':NEW,'frontendOnly':True,'databaseUntouched':True,'restartedServices':[],'allServicePidsUnchanged':True}
 (STAGE/'frontend-context-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except Exception:
 for d,data in indexes.items():
  tmp=ROOT/d/'index.patient-context-rollback.html';tmp.write_bytes(data);tmp.chmod(0o644);os.replace(tmp,ROOT/d/'index.html')
 if not git('status','--porcelain'):git('switch','--detach',OLD)
 raise
