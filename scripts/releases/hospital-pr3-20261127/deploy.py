"""Additive migration release with protected-copy rehearsal. Target service only."""
import hashlib,json,os,shutil,sqlite3,subprocess,sys,tarfile,time,urllib.request
from pathlib import Path
stage=Path(sys.argv[1]).resolve();assert stage==Path('/opt/pd-rehab/releases/hospital-pr3-20261127')
repo=Path('/opt/pd-rehab/app/PD-Rehab-Web');web=Path('/var/www/pd-rehab');database=Path('/opt/pd-rehab/data/pd.db')
units=['nginx','exercises','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api','motion-atlas-341']
def cmd(*a):return subprocess.check_output(a,text=True).strip()
def run(*a,**kw):return subprocess.run(a,check=True,**kw)
def git(*a):return cmd('git','-c','safe.directory='+str(repo),'-C',str(repo),*a)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def states():return{u:cmd('systemctl','show',u,'-p','MainPID','-p','ActiveState') for u in units}
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:18086/api/'+path,timeout=10) as r:return json.load(r)
def ready(models):
 end=time.monotonic()+120
 while time.monotonic()<end:
  try:
   rows=get('system/models')['summary']['models']
   if get('system/health')['status']=='ok' and all(any(x['name']==n and x['version']==v and x['is_ready'] for x in rows) for n,v in models.items()):return
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('Target model readiness timeout')
def extract(path,target):
 target.mkdir(mode=0o700)
 with tarfile.open(path) as a:
  assert all(not m.issym() and not m.islnk() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in a.getmembers());a.extractall(target,filter='data')
def backup_db(dest):
 fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
 with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as src,sqlite3.connect(dest) as dst:src.backup(dst)
def snapshot(path,previous=None):
 result={}
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  tables=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' and name!='alembic_version' order by name")]
  if previous is not None:assert set(tables)==set(previous)
  for table in tables:
   quoted='"'+table.replace('"','""')+'"'
   info=db.execute('pragma table_info('+quoted+')').fetchall()
   columns=previous[table]['columns'] if previous is not None else [r[1] for r in info]
   schema=[r for r in info if r[1] in columns]
   projection=','.join('"'+c.replace('"','""')+'"' for c in columns)
   digest=hashlib.sha256();count=0
   for row in db.execute('select '+projection+' from '+quoted+' order by rowid'):
    digest.update(json.dumps(row,ensure_ascii=False,default=repr,separators=(',',':')).encode());digest.update(b'\n');count+=1
   result[table]={'columns':columns,'schema':schema,'rows':count,'digest':digest.hexdigest(),'foreignKeys':db.execute('pragma foreign_key_list('+quoted+')').fetchall(),'indexes':db.execute('select name,sql from sqlite_master where type=\'index\' and tbl_name=? order by name',(table,)).fetchall()}
 return result
def verify(path,before):
 assert snapshot(path,before)==before,'Old columns or rows changed'
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  assert {r[1] for r in db.execute('pragma table_info(patients)')} == set(before['patients']['columns'])|{'onset_side','medication_use_status','age_years','age_recorded_on'}
  assert db.execute('pragma integrity_check').fetchone()[0]=='ok';assert not db.execute('pragma foreign_key_check').fetchall()
  assert db.execute('select version_num from alembic_version').fetchone()[0]=='t5b7c9d1e3f5'
  assert db.execute("select count(*) from patients where onset_side!='UNKNOWN' or medication_use_status!='UNKNOWN' or age_years is not null or age_recorded_on is not null").fetchone()[0]==0
 return {'tablesPreserved':len(before),'oldColumnsAndRowsPreserved':True,'integrity':'ok','head':'t5b7c9d1e3f5'}
def migrate(root,url,env,log):
 with log.open('w') as out:run('/opt/pd-rehab/venv/bin/python','-m','alembic','upgrade','head',cwd=root/'backend',env={**env,'DATABASE_URL':url,'PYTHONPATH':str(root/'backend')},stdout=out,stderr=subprocess.STDOUT)
def atomic(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);t=dest.with_name(dest.name+'.pr3-pending');shutil.copyfile(src,t);t.chmod(0o644);os.replace(t,dest)
m=json.loads((stage/'manifest.json').read_text());old=m['old'];new=m['new'];assert git('rev-parse','HEAD')==old and not git('status','--porcelain')
for name,value in m['files'].items():assert sha(stage/name)==value
before_services=states();models={x['name']:x['version'] for x in get('system/models')['summary']['models'] if x['is_ready']};assert len(models)==4
pid=cmd('systemctl','show','pd-rehab-backend','--value','-p','MainPID');env=dict(x.decode().split('=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x)
assert env['DATABASE_URL']=='sqlite:////opt/pd-rehab/data/pd.db'
assert env.get('ASR_CONFIG_FILE')=='/opt/pd-rehab/config/asr.env'
argv=Path('/proc/'+pid+'/cmdline').read_bytes().split(b'\0');assert argv[argv.index(b'--workers')+1]==b'1'
protected=[Path('/etc/nginx/conf.d/pd-rehab.conf'),Path('/etc/nginx/snippets/pd-rehab-locations.conf'),Path('/opt/pd-rehab/config/asr.env')]
protected_sha={str(p):sha(p) for p in protected}
apk=web/'app-releases/0.1.73-75/qinban-0.1.73-android-universal.apk';apk_sha=sha(apk)
git('fetch',str(stage/'release.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==new
extract(stage/'backend.tar.gz',stage/'candidate');extract(stage/'frontend.tar.gz',stage/'builds')
with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as db:assert db.execute('select version_num from alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
backup_db(stage/'rehearsal.sqlite');baseline=snapshot(stage/'rehearsal.sqlite')
migrate(stage/'candidate','sqlite:///'+str(stage/'rehearsal.sqlite'),env,stage/'rehearsal.log');rehearsal=verify(stage/'rehearsal.sqlite',baseline)
(stage/'rehearsal-result.json').write_text(json.dumps(rehearsal,indent=2))
backup=stage/'backup';backup.mkdir(mode=0o700)
for d in ['dist','dist-under-path']:shutil.copy2(web/d/'index.html',backup/(d+'.html'))
(backup/'state.json').write_text(json.dumps({'old':old,'new':new,'models':models,'services':before_services}))
changed=False
try:
 run('systemctl','stop','pd-rehab-backend');backup_db(backup/'pd.sqlite');baseline=snapshot(database)
 git('merge','--ff-only',new);changed=True
 migrate(repo,env['DATABASE_URL'],env,stage/'production-migration.log');production=verify(database,baseline)
 run('systemctl','start','pd-rehab-backend');ready(models)
 for kind,d in [('root','dist'),('under','dist-under-path')]:
  source=stage/'builds'/kind;assert(source/'index.html').is_file()
  for f in source.rglob('*'):
   if not f.is_file() or f==source/'index.html':continue
   rel=f.relative_to(source);assert rel.parts[:2] not in [('assets','app-releases'),('assets','dance')]
   dest=web/d/rel;assert dest.resolve().is_relative_to(web.resolve()) and not dest.is_symlink()
   if dest.is_file() and sha(dest)==sha(f):continue
   if dest.exists():
    copy=backup/'static'/d/rel;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,copy)
   atomic(f,dest)
  atomic(source/'index.html',web/d/'index.html')
 assert states()==before_services;assert sha(apk)==apk_sha
 assert {str(p):sha(p) for p in protected}==protected_sha
 assert not git('status','--porcelain')
 result={'commit':new,'rehearsal':rehearsal,'productionMigration':production,'modelsReady':4,'otherServicesUnchanged':True,'proxyAndAsrConfigUnchanged':True,'apkUnchanged':True,'backup':str(backup)}
 (stage/'deployment-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except BaseException:
 run('systemctl','stop','pd-rehab-backend')
 if changed:
  assert not git('status','--porcelain');git('switch','--detach',old)
 for d in ['dist','dist-under-path']:atomic(backup/(d+'.html'),web/d/'index.html')
 for f in (backup/'static').rglob('*'):
  if f.is_file():shutil.copy2(f,web/f.relative_to(backup/'static'))
 # Keep additive columns; never overwrite newer business writes or drop columns.
 run('systemctl','start','pd-rehab-backend');ready(models)
 raise
