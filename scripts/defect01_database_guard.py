"""Release guard: read identifiers/relationships only, never clinical fields."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

database = Path('/opt/pd-rehab/data/pd.db')
work = Path('/tmp/pd-defect01-20261018-r2')
backup = Path('/opt/pd-rehab/backups/defect01-20261018-r2')

def snapshot(db):
    result = {}
    for (table,) in db.execute("select name from sqlite_master where type='table' order by name"):
        if table.startswith('sqlite_') or table in {'alembic_version', 'patient_number_allocations'}:
            continue
        quote = lambda s: '"' + s.replace('"', '""') + '"'
        columns = [r[1] for r in db.execute('pragma table_info(' + quote(table) + ')') if r[5]]
        columns += [r[3] for r in db.execute('pragma foreign_key_list(' + quote(table) + ')')]
        if table == 'patients':
            columns.append('hospital_number')
        columns = sorted(set(columns))
        rows = sorted(db.execute('select ' + ','.join(map(quote, columns)) + ' from ' + quote(table)).fetchall(),
                      key=lambda row: json.dumps(row, ensure_ascii=True)) if columns else []
        result[table] = {'count': db.execute('select count(*) from ' + quote(table)).fetchone()[0],
                         'identity_digest': hashlib.sha256(json.dumps(rows, ensure_ascii=True).encode()).hexdigest()}
    return result

with sqlite3.connect('file:' + database.as_posix() + '?mode=ro', uri=True) as db:
    assert db.execute('pragma quick_check').fetchone()[0] == 'ok'
    assert not db.execute('pragma foreign_key_check').fetchall()
    revision = db.execute('select version_num from alembic_version').fetchone()[0]
    if sys.argv[1] == 'before':
        assert revision == 'h4c6d8e0f2a3'
        with sqlite3.connect(backup / 'pd.db') as destination:
            db.backup(destination)
        (backup / 'identity-before.json').write_text(json.dumps(snapshot(db), sort_keys=True))
        print('Database backed up; baseline identity digests recorded without clinical fields')
    else:
        assert revision == 'i5d7e9f1a3b4', revision
        assert snapshot(db) == json.loads((backup / 'identity-before.json').read_text())
        assert db.execute("select sql from sqlite_master where name='patient_number_allocations'").fetchone()
        result = {'migration': revision, 'identities_and_relationships_unchanged': True,
                  'existing_table_counts_unchanged': True, 'foreign_key_check': 'ok', 'quick_check': 'ok',
                  'clinical_fields_read': False}
        (work / 'database-verification.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
