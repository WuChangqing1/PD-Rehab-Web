"""SQLite change index: only the latest event per patient/entity is retained."""
from sqlalchemy import text
from uuid import uuid4

DIRECT = ('assessment_sessions', 'piano_sessions', 'pose_sessions',
          'guided_song_sessions', 'training_plans', 'external_practice_records')
CHILD = ('micro_expression_results', 'finger_tapping_results', 'functional_assessments')
TABLES = DIRECT + CHILD
INDEX = 'integration_change_index'


def install(conn):
    if conn.dialect.name != 'sqlite':
        return
    conn.execute(text(f"""CREATE TABLE {INDEX} (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
        kind TEXT NOT NULL, entity_id TEXT NOT NULL,
        UNIQUE(patient_id, kind, entity_id))"""))
    conn.execute(text(f'CREATE INDEX ix_sync_patient_seq ON {INDEX}(patient_id, seq)'))
    conn.execute(text(f"INSERT INTO {INDEX}(patient_id,kind,entity_id) VALUES ('','','' || :id)"),
                 {'id': uuid4().hex})
    for table in TABLES:
        for event in ('INSERT', 'UPDATE', 'DELETE'):
            aliases = ('OLD', 'NEW') if event == 'UPDATE' else ('OLD',) if event == 'DELETE' else ('NEW',)
            statements = []
            for row in aliases:
                pid = (f'{row}.patient_id' if table in DIRECT else
                       f'(SELECT patient_id FROM assessment_sessions WHERE id={row}.assessment_session_id)')
                statements.append(f"""INSERT OR REPLACE INTO {INDEX}(patient_id, kind, entity_id)
                    SELECT {pid}, '{table}', {row}.id WHERE {pid} IS NOT NULL;""")
            conn.execute(text(f"CREATE TRIGGER sync_{table}_{event.lower()} AFTER {event} ON {table} "
                              f"BEGIN {' '.join(statements)} END"))
        patient = 'r.patient_id' if table in DIRECT else 'a.patient_id'
        join = '' if table in DIRECT else 'JOIN assessment_sessions a ON a.id=r.assessment_session_id'
        conn.execute(text(f"INSERT INTO {INDEX}(patient_id,kind,entity_id) "
                          f"SELECT {patient}, '{table}', r.id FROM {table} r {join}"))
    children = ' '.join(f"""INSERT OR REPLACE INTO {INDEX}(patient_id,kind,entity_id)
        SELECT OLD.patient_id, '{table}', id FROM {table} WHERE assessment_session_id=OLD.id;"""
        for table in CHILD)
    conn.execute(text('CREATE TRIGGER sync_assessment_children_delete BEFORE DELETE ON assessment_sessions '
                      f'BEGIN {children} END'))


def uninstall(conn):
    if conn.dialect.name != 'sqlite':
        return
    conn.execute(text('DROP TRIGGER sync_assessment_children_delete'))
    for table in TABLES:
        for event in ('insert', 'update', 'delete'):
            conn.execute(text(f'DROP TRIGGER sync_{table}_{event}'))
    conn.execute(text(f'DROP TABLE {INDEX}'))
