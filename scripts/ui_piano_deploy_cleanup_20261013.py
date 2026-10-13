"""Verify production data, then remove only this authorized release's backup."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import urllib.request

backup = Path('/opt/pd-rehab/backups/ui-piano-20261013-19dba0f')
assert backup.resolve() == backup and backup.parent == Path('/opt/pd-rehab/backups')
assert not backup.is_symlink() and (backup/'pd.db').is_file()
old = sqlite3.connect(f'file:{backup}/pd.db?mode=ro', uri=True)
live = sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro', uri=True)
live.execute('BEGIN')
tables = [r[0] for r in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
def digest(db, table):
    rows = db.execute('select * from "'+table+'" order by rowid').fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(',', ':'), default=str).encode()).hexdigest()
verified = []
for table in tables:
    if table == 'audit_logs':
        continue
    assert digest(old, table) == digest(live, table), f'Content changed in {table}'
    verified.append(table)
audit_before = old.execute('select count(*) from audit_logs').fetchone()[0]
audit_after = live.execute('select count(*) from audit_logs').fetchone()[0]
assert audit_after == audit_before + 1, (audit_before, audit_after)
assert live.execute('select action from audit_logs order by rowid desc limit 1').fetchone()[0] == 'LOGIN_SUCCESS'
assert live.execute('pragma quick_check').fetchone()[0] == 'ok'
with urllib.request.urlopen('http://127.0.0.1:18086/openapi.json') as response:
    spec = json.load(response)
recipe_enum = spec['components']['schemas']['PianoSessionCreate']['properties']['recipe_id']
assert all(recipe in json.dumps(recipe_enum) for recipe in ['TEMPO_RAMP','HOLD_RELEASE','BIMANUAL_OFFSET','REVERSE_SEQUENCE','GO_NO_GO'])
live.close(); old.close()
released = sum(p.stat().st_size for p in backup.rglob('*') if p.is_file())
shutil.rmtree(backup)
assert not backup.exists()
print(json.dumps({'unchangedContentTables':verified,'auditBefore':audit_before,'auditAfter':audit_after,
                  'auditReason':'one real verification login','liveNewRecipeSchemas':True,
                  'backupRemoved':str(backup),'backupFileBytesReleased':released}))
