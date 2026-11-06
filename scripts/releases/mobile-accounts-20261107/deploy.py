import hashlib,json,os,sqlite3,subprocess as sp,time,urllib.request as u,urllib.error as e
from pathlib import Path
def snapshot(path):
    with sqlite3.connect(str(path)) as db:
        names=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' and name!='alembic_version' order by name")]
        result={}
        for name in names:
            h=hashlib.sha256();n=0
            for row in db.execute('select * from "'+name+'" order by rowid'):
                h.update(json.dumps(row,ensure_ascii=True,default=str,separators=(',',':')).encode());h.update(b'\n');n+=1
            result[name]={'rows':n,'sha256':h.hexdigest()}
        return result
W=Path('/opt/pd-rehab/releases/mobile-accounts-20261107')
A=Path('/opt/pd-rehab/app/PD-Rehab-Web')
B=Path('/opt/pd-rehab/backups/mobile-accounts-20261107')
OLD='7e1c73153fc5de63a28c2def883dddb8402bd3f3'
UNITS=['nginx.service','exercises.service','his-18092-tls.service','llm-api-platform.service','smoking-monitor-api.service','smoking-monitoring-system-api.service']
def out(*a):return sp.check_output(a,text=True).strip()
def run(*a,**kw):sp.run(a,check=True,**kw)
def get(url):
    with u.urlopen(url,timeout=15) as response:return response.read()
def others():return {n:out('systemctl','show',n,'-p','MainPID','-p','ActiveState') for n in UNITS}
def models():return json.loads(get('http://127.0.0.1:18086/api/system/models'))['models']
def restart(ready):
    run('sudo','-n','systemctl','start','pd-rehab-backend.service')
    for _ in range(110):
        try:
            current=models()
            if ready.issubset({k for k,v in current.items() if v.get('is_ready')}):return
        except (OSError,ValueError):pass
        time.sleep(1)
    raise RuntimeError('Models/health readiness timeout')
manifest=json.loads((W/'manifest.json').read_text());NEW=manifest['revision']
assert out('git','-C',str(A),'rev-parse','HEAD')==OLD and not out('git','-C',str(A),'status','--porcelain')
for name,h in manifest['files'].items():assert hashlib.sha256((W/name).read_bytes()).hexdigest()==h,name
assert json.loads((W/'rehearsal-evidence.json').read_text())['all_original_rows_equal']
assert all(json.loads((W/'staging-result.json').read_text()).values())
assert not B.exists(),'Release backup already exists; do not overwrite'
before_other=others();ready={k for k,v in models().items() if v.get('is_ready')}
assert 'micro_expression_model' in ready
html={name:hashlib.sha256((Path('/var/www/pd-rehab')/name/'index.html').read_bytes()).hexdigest() for name in ['dist','dist-under-path']}
run('git','-C',str(A),'fetch',str(W/'release.bundle'),'refs/heads/codex/mobile-accounts-20261106')
assert out('git','-C',str(A),'rev-parse','FETCH_HEAD')==NEW
B.mkdir(mode=0o700)
result={'old_revision':OLD,'revision':NEW,'backup':str(B),'models_ready_before':sorted(ready),'other_services_before':before_other,'frontend_unchanged':html}
(B/'baseline.json').write_text(json.dumps(result,indent=2));(B/'baseline.json').chmod(0o600)
run('sudo','-n','systemctl','stop','pd-rehab-backend.service')
try:
    database=Path('/opt/pd-rehab/data/pd.db')
    with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as original,sqlite3.connect(B/'pd.sqlite') as target:original.backup(target)
    (B/'pd.sqlite').chmod(0o600)
    before=snapshot(B/'pd.sqlite')
    with sqlite3.connect(database) as db:
        assert db.execute('select version_num from alembic_version').fetchone()[0]=='m9b1c3d5e7f9'
    run('git','-C',str(A),'merge','--ff-only','FETCH_HEAD')
    env=os.environ.copy();env['DATABASE_URL']='sqlite:////opt/pd-rehab/data/pd.db'
    with (W/'production-migration.log').open('w') as log:
        run('/opt/pd-rehab/venv/bin/python','-m','alembic','upgrade','head',cwd=A/'backend',env=env,stdout=log,stderr=sp.STDOUT)
    after=snapshot(database)
    assert all(after[name]==item for name,item in before.items()),'Old rows changed during migration'
    assert set(after)-set(before)=={'mobile_accounts','mobile_sessions'}
    with sqlite3.connect(database) as db:
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert db.execute('pragma foreign_key_check').fetchall()==[]
        assert db.execute('select version_num from alembic_version').fetchone()[0]=='n0c2d4e6f8a0'
    result.update(migration='n0c2d4e6f8a0',old_rows_unchanged=True,original_tables=len(before),integrity='ok',foreign_keys=0)
    restart(ready)
    routes=['/api/mobile/auth/register','/api/mobile/auth/login','/api/mobile/auth/refresh','/api/mobile/auth/me','/api/mobile/auth/logout','/api/mobile/auth/reset-password','/api/mobile/auth/change-password']
    for base in ['http://127.0.0.1:18085/','https://ccqspace.site/pd-rehab/']:
        assert json.loads(get(base+'api/system/health'))['status']=='ok'
        paths=json.loads(get(base+'api/openapi.json'))['paths']
        assert all(route in paths for route in routes)
        for path in ['mobile/auth/me','integration/v1/plans?patient_id=00000000-0000-0000-0000-000000000001&on_date=2026-11-07','integration/v1/face/recordings/00000000-0000-0000-0000-000000000001/files/00000000-0000-0000-0000-000000000002/playback?download=true']:
            try:get(base+'api/'+path)
            except e.HTTPError as err:assert err.code==401,(path,err.code)
            else:raise AssertionError('Unauthorized request accepted')
    for name,h in html.items():assert hashlib.sha256((Path('/var/www/pd-rehab')/name/'index.html').read_bytes()).hexdigest()==h
    assert before_other==others(),'Unrelated service changed'
    result.update(other_services_unchanged=True,models_ready_after=sorted(k for k,v in models().items() if v.get('is_ready')),both_api_entries_verified=True,unauthenticated_access_denied=True)
    (W/'release-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
except BaseException:
    run('sudo','-n','systemctl','stop','pd-rehab-backend.service')
    # Preserve new data; older staff code must not authenticate PATIENT users.
    with sqlite3.connect('/opt/pd-rehab/data/pd.db') as db:
        db.execute("update staff_users set is_active=0 where role='PATIENT'")
        if db.execute("select 1 from sqlite_master where type='table' and name='mobile_sessions'").fetchone():db.execute('update mobile_sessions set revoked=1')
    assert not out('git','-C',str(A),'status','--porcelain')
    run('git','-C',str(A),'checkout','--detach',OLD)
    restart(ready)
    raise
