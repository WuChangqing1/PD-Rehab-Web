"""Target-only ASR release. Usage: sudo python3 deploy.py STAGE. No migration."""
import hashlib,json,os,pwd,shutil,sqlite3,subprocess,sys,tarfile,time,urllib.request
from pathlib import Path
STAGE=Path('/opt/pd-rehab/releases/asr-api-20261123')
stage=Path(sys.argv[1]).resolve();assert stage==STAGE
repo=Path('/opt/pd-rehab/app/PD-Rehab-Web');web=Path('/var/www/pd-rehab')
config=Path('/opt/pd-rehab/config/asr.env')
dropin=Path('/etc/systemd/system/pd-rehab-backend.service.d/zzzz-asr.conf')
nginx=[Path('/etc/nginx/conf.d/pd-rehab.conf'),Path('/etc/nginx/snippets/pd-rehab-locations.conf')]
units=['nginx','exercises','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api','motion-atlas-341']
def cmd(*a):return subprocess.check_output(a,text=True).strip()
def run(*a,**kw):return subprocess.run(a,check=True,**kw)
def git(*a):return cmd('git','-c','safe.directory='+str(repo),'-C',str(repo),*a)
def digest(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def states():return {u:cmd('systemctl','show',u,'-p','MainPID','-p','ActiveState') for u in units}
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:18086/api/'+path,timeout=10) as r:return json.load(r)
def ready(expected):
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        try:
            models=get('system/models')['summary']['models']
            if get('system/health')['status']=='ok' and all(any(m['name']==name and m['is_ready'] and m['version']==version for m in models) for name,version in expected.items()):return
        except Exception:pass
        time.sleep(2)
    raise RuntimeError('Target readiness timeout')
def extract(path,target):
    target.mkdir(mode=0o700)
    with tarfile.open(path) as t:
        assert all(not m.issym() and not m.islnk() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in t.getmembers())
        t.extractall(target,filter='data')
def atomic(source,target,mode=0o644):
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.asr-pending');shutil.copyfile(source,temp);temp.chmod(mode);os.replace(temp,target)
def proxy_block(source,path):
    text=source.read_text();start=text.index('location = '+path+' {');end=text.index('}',start)+1
    return text[start:end]+'\n\n'
manifest=json.loads((stage/'manifest.json').read_text());old=manifest['old'];new=manifest['new']
assert git('rev-parse','HEAD')==old and not git('status','--porcelain')
for name,sha in manifest['files'].items():assert digest(stage/name)==sha,name
before=states();models={m['name']:m['version'] for m in get('system/models')['summary']['models'] if m['is_ready']};assert len(models)==4
pid=cmd('systemctl','show','pd-rehab-backend','--value','-p','MainPID')
env=dict(x.decode().split('=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x)
assert env.get('DATABASE_URL')=='sqlite:////opt/pd-rehab/data/pd.db'
argv=Path('/proc/'+pid+'/cmdline').read_bytes().split(b'\0');assert b'--workers' in argv and argv[argv.index(b'--workers')+1]==b'1'
assert cmd('/opt/pd-rehab/venv/bin/python','-c','import websockets; print(websockets.__version__)')=='17.1'
for d in ['dist','dist-under-path']:assert (web/d/'assets/app-releases').resolve()==web/'app-releases'
apk=web/'app-releases/0.1.73-75/qinban-0.1.73-android-universal.apk';apk_sha=digest(apk)
git('fetch',str(stage/'release.bundle'),'HEAD');assert git('rev-parse','FETCH_HEAD')==new
extract(stage/'backend.tar.gz',stage/'candidate');extract(stage/'frontend.tar.gz',stage/'builds')
testenv={**env,'DATABASE_URL':'sqlite://','PYTHONPATH':str(stage/'candidate/backend'),'ASR_CONFIG_FILE':str(stage/'incoming-asr.env')}
with (stage/'preflight.log').open('w') as log:run('/opt/pd-rehab/venv/bin/python',str(stage/'preflight.py'),cwd=stage/'candidate/backend',env=testenv,stdout=log,stderr=subprocess.STDOUT)
backup=stage/'backup';backup.mkdir(mode=0o700)
for d in ['dist','dist-under-path']:shutil.copy2(web/d/'index.html',backup/(d+'.html'))
paths=[*nginx,dropin,config];saved={str(p):p.exists() for p in paths}
for p in paths:
    if p.exists():
        dest=backup/'config'/p.relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
state={'old':old,'new':new,'models':models,'services':before,'configurationExisted':saved,'apkSha256':apk_sha}
(backup/'state.json').write_text(json.dumps(state,indent=2))
changed=False;proxy_changed=False
try:
    # Append only this project's exact routes; preserve every existing directive.
    sources=[stage/'candidate/deploy/nginx/pd-rehab.conf',stage/'candidate/deploy/nginx/pd-rehab-locations.conf']
    for dest,source,path,marker in zip(nginx,sources,['/api/asr/stream','/pd-rehab/api/asr/stream'],['    location /api/ {','location /pd-rehab/api/ {']):
        text=dest.read_text();assert 'location = '+path+' {' not in text and marker in text
        temp=stage/(dest.name+'.pending');temp.write_text(text.replace(marker,proxy_block(source,path)+marker,1));atomic(temp,dest)
    proxy_changed=True
    run('nginx','-t')
    run('systemctl','stop','pd-rehab-backend')
    dbpath=Path('/opt/pd-rehab/data/pd.db');db_before=digest(dbpath)
    fd=os.open(backup/'pd.sqlite',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    with sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True) as src,sqlite3.connect(backup/'pd.sqlite') as dst:src.backup(dst)
    git('merge','--ff-only',new);changed=True
    assert digest(dbpath)==db_before
    config.parent.mkdir(mode=0o750,exist_ok=True)
    account=pwd.getpwnam('ubuntu');os.chown(config.parent,0,account.pw_gid)
    atomic(stage/'incoming-asr.env',config,0o600);os.chown(config,account.pw_uid,account.pw_gid)
    temp=stage/'asr-dropin.conf';temp.write_text('[Service]\nEnvironment=ASR_CONFIG_FILE=/opt/pd-rehab/config/asr.env\n');atomic(temp,dropin)
    run('systemctl','daemon-reload');run('systemctl','start','pd-rehab-backend');ready(models)
    for kind,d in [('root','dist'),('under','dist-under-path')]:
        source=stage/'builds'/kind;assert (source/'index.html').is_file()
        for file in source.rglob('*'):
            if not file.is_file() or file==source/'index.html':continue
            rel=file.relative_to(source);assert rel.parts[:2] not in [('assets','app-releases'),('assets','dance')]
            dest=web/d/rel;assert dest.resolve().is_relative_to(web.resolve()) and not dest.is_symlink()
            if dest.is_file() and digest(dest)==digest(file):continue
            if dest.exists():
                oldfile=backup/'static'/d/rel;oldfile.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,oldfile)
            atomic(file,dest)
        atomic(source/'index.html',web/d/'index.html')
    run('systemctl','reload','nginx')
    assert states()==before,'Unrelated service state or master PID changed'
    assert digest(apk)==apk_sha
    with sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro',uri=True) as db:
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert not db.execute('pragma foreign_key_check').fetchall()
        assert db.execute('select version_num from alembic_version').fetchone()[0]=='p2e4f6a8b0c2'
    assert not git('status','--porcelain')
    result={'commit':new,'modelsReady':4,'otherServicesUnchanged':True,'databaseMigration':False,'databaseIntegrity':'ok','apkUnchanged':True,'keyPermissions':'0600 ubuntu','backup':str(backup),'servicesBefore':before,'servicesAfter':states()}
    (stage/'deployment-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except BaseException:
    run('systemctl','stop','pd-rehab-backend')
    if changed:
        assert not git('status','--porcelain');git('switch','--detach',old)
    for path,existed in saved.items():
        p=Path(path)
        if existed:shutil.copy2(backup/'config'/p.relative_to('/'),p)
        elif p.exists():p.unlink()
    for d in ['dist','dist-under-path']:shutil.copy2(backup/(d+'.html'),web/d/'index.html')
    for p in (backup/'static').rglob('*'):
        if p.is_file():shutil.copy2(p,web/p.relative_to(backup/'static'))
    run('systemctl','daemon-reload');run('nginx','-t')
    if proxy_changed:run('systemctl','reload','nginx')
    run('systemctl','start','pd-rehab-backend');ready(models)
    raise
