"""One-release production checks. Never print patient data or credentials."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

APP=Path('/opt/pd-rehab/app/PD-Rehab-Web')
DB=Path('/opt/pd-rehab/data/pd.db')
WORK=Path('/tmp/pd-guided-song-20261016')
BACKUP=Path('/opt/pd-rehab/backups/guided-song-20261016')
CONFIGS=[('/etc/nginx/snippets/pd-rehab-locations.conf','pd-rehab-locations.conf','location /pd-rehab/api/ {','/pd-rehab/api/live-emotion/stream',''),('/etc/nginx/conf.d/pd-rehab.conf','pd-rehab.conf','    location /api/ {','/api/live-emotion/stream','    ')]

def summary(db):
    tables=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
    result={}
    for table in tables:
        rows=db.execute('select * from "'+table+'"').fetchall()
        digest=hashlib.sha256('\n'.join(sorted(map(repr,rows))).encode()).hexdigest()
        result[table]={'count':len(rows),'sha256':digest}
    return result

mode=sys.argv[1]
if mode=='snapshot':
    with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as source:
        with sqlite3.connect(BACKUP/'pd.db') as copy:
            source.backup(copy)
            assert copy.execute('pragma quick_check').fetchone()[0]=='ok'
            before=summary(copy)
    (BACKUP/'before.json').write_text(json.dumps(before,indent=2))
    print('Consistent database backup created; table counts:',json.dumps({k:v['count'] for k,v in before.items()}))
elif mode=='verify-data':
    before=json.loads((BACKUP/'before.json').read_text())
    with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as db:
        assert db.execute('pragma quick_check').fetchone()[0]=='ok'
        after=summary(db)
        for name,entry in before.items():
            if name!='alembic_version':assert after[name]==entry,'Existing table changed: '+name
        assert db.execute('select version_num from alembic_version').fetchone()[0]=='h4c6d8e0f2a3'
        assert 'guided_song_sessions' in after
    evidence={'old_table_content_unchanged':True,'integrity':'ok','schema':'h4c6d8e0f2a3','counts':{k:v['count'] for k,v in after.items()}}
    (WORK/'data-check.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence))
elif mode=='stage-nginx':
    for target,name,anchor,location,indent in CONFIGS:
        actual=Path(target).read_text()
        template=(APP/'deploy/nginx'/name).read_text()
        begin=template.index(indent+'# Continuous video stream:')
        end=template.index(anchor,begin)
        block=template[begin:end]
        assert 'location = '+location+' {' in block
        assert location not in actual,'Existing streaming route requires manual inspection'
        assert actual.count(anchor)==1
        (WORK/name).write_text(actual.replace(anchor,block+anchor))
elif mode=='verify-assets':
    expected=json.loads((WORK/'asset-manifest.json').read_text())
    for name,digest in expected.items():
        file=Path('/var/www/pd-rehab')/name
        assert file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==digest,name
    print('Verified deployed static files:',len(expected))
elif mode=='cleanup':
    released=(WORK/'release-ok.json')
    assert released.is_file(),'Release not verified'
    assert (WORK/'data-check.json').is_file()
    removed=0
    for target,parent in [(BACKUP,Path('/opt/pd-rehab/backups')),(WORK,Path('/tmp'))]:
        assert target.is_dir() and not target.is_symlink()
        assert target.resolve()==target and target.parent.resolve()==parent
        removed+=sum(p.stat().st_size for p in target.rglob('*') if p.is_file() and not p.is_symlink())
        shutil.rmtree(target)
    print(json.dumps({'backup_and_staging_deleted':True,'removed_bytes':removed}))
else:raise SystemExit('Unknown check mode')
