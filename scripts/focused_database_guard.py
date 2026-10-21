"""Release-local backup and row digests. No patient fields leave the server."""
import hashlib,json,sqlite3,sys
from pathlib import Path

DB=Path('/opt/pd-rehab/data/pd.db')
BACKUP=Path('/opt/pd-rehab/backups/focused-polish-20261021')
RESERVED='abfd9bed-4644-5fd2-812f-3a7eaca11a84'
PROFILE={'name','sex','birthday','dominant_hand','affected_side','medication_state','diagnosis_date','disease_duration_years','current_stage','updated_at'}
quote=lambda value:'"'+value.replace('"','""')+'"'

def snapshot(db):
    result={}
    for (table,) in db.execute("select name from sqlite_master where type='table' order by name"):
        if table.startswith('sqlite_'):continue
        info=list(db.execute('pragma table_info('+quote(table)+')'))
        columns=[r[1] for r in info];keys=[r[1] for r in info if r[5]] or columns
        rows={}
        for values in db.execute('select * from '+quote(table)):
            row=dict(zip(columns,values))
            key=json.dumps([row[k] for k in keys],ensure_ascii=True,default=str)
            # Only the explicitly reserved fictional profile may change.
            if table=='patients' and row.get('id')==RESERVED:
                row={k:v for k,v in row.items() if k not in PROFILE}
            digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=True,default=str).encode()).hexdigest()
            rows[key]=digest
        result[table]=rows
    return result

with sqlite3.connect('file:'+DB.as_posix()+'?mode=ro',uri=True) as db:
    assert db.execute('pragma quick_check').fetchone()[0]=='ok'
    assert not db.execute('pragma foreign_key_check').fetchall()
    assert db.execute('select version_num from alembic_version').fetchone()[0]=='i5d7e9f1a3b4'
    if sys.argv[1]=='before':
        # Current deployment audit found zero empty patients. Fail safely on drift.
        active=[r[0] for r in db.execute('select id from patients where is_deleted=0')]
        for pid in active:
            references=0
            for (table,) in db.execute("select name from sqlite_master where type='table'"):
                if table=='patient_number_allocations':continue
                for fk in db.execute('pragma foreign_key_list('+quote(table)+')'):
                    if fk[2]=='patients':references+=db.execute('select count(*) from '+quote(table)+' where '+quote(fk[3])+'=?',(pid,)).fetchone()[0]
            assert references>0,'Patient set changed; review empty patient preview before release'
        with sqlite3.connect(BACKUP/'pd.db') as dest:db.backup(dest)
        (BACKUP/'rows-before.json').write_text(json.dumps(snapshot(db)),encoding='utf-8')
        print('Backup verified; existing row digests retained only on server')
    else:
        before=json.loads((BACKUP/'rows-before.json').read_text())
        after=snapshot(db)
        for table,rows in before.items():
            assert table in after,table
            assert all(after[table].get(k)==v for k,v in rows.items()),'Existing row changed: '+table
        print('Existing records and identities preserved; only additions and reserved profile changes')
