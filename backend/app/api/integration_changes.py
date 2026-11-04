"""Authorized incremental feed, separate from the recording upload protocol."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, Response
from jose import JWTError, jwt
from sqlalchemy import select, text

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import APIError
from app.db.base import Base
from app.services import integration_access as access
from app.services.sync_changes import CHILD, INDEX

router = APIRouter(prefix='/integration/v1', tags=['Cross-client synchronization'])
PRIVATE_FIELDS = {'stored_path', 'raw_timeseries_path', 'original_filename', 'raw_output_json',
                  'source_video_path', 'password_hash', 'video_path'}


def supported(db):
    return db.bind.dialect.name == 'sqlite' and bool(db.scalar(text(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"), {'name': INDEX}))


@router.get('/changes')
def changes(patient_id: UUID, device_id: str, local_profile_id: str,
            db: DbSession, user: CurrentUser, response: Response,
            cursor: str | None = Query(None, max_length=2048), limit: int = Query(25, ge=1, le=50)):
    pid = str(patient_id)
    binding = access.bound(db, device_id, local_profile_id, pid, user)
    if not supported(db):
        raise APIError(501, 'SYNC_FEED_UNAVAILABLE', '此服务器未启用增量同步。')
    response.headers['Cache-Control'] = 'private, no-store'
    scope = f'{user.id}:{binding.id}:{pid}'
    generation = db.scalar(text(f"SELECT entity_id FROM {INDEX} WHERE patient_id='' AND kind=''"))
    after = 0
    if cursor:
        try:
            token = jwt.decode(cursor, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            if token.get('purpose') != 'sync-changes-v1' or token.get('scope') != scope or token.get('generation') != generation:
                raise ValueError
            after = token['seq']
            if type(after) is not int or after < 0:
                raise ValueError
            if after > db.scalar(text(f'SELECT MAX(seq) FROM {INDEX}')):
                raise ValueError
        except (JWTError, ValueError, KeyError):
            raise APIError(409, 'SYNC_CURSOR_INVALID', '同步游标已失效，请重新加载。')
    events = db.execute(text(f'SELECT seq,kind,entity_id FROM {INDEX} '
        'WHERE patient_id=:pid AND seq>:after ORDER BY seq LIMIT :count'),
        {'pid': pid, 'after': after, 'count': limit + 1}).all()
    items = []
    for seq, kind, ident in events[:limit]:
        table = Base.metadata.tables[kind]
        if kind in CHILD:
            parent = Base.metadata.tables['assessment_sessions']
            query = select(table).join(parent, table.c.assessment_session_id == parent.c.id).where(parent.c.patient_id == pid)
        else:
            query = select(table).where(table.c.patient_id == pid)
        row = db.execute(query.where(table.c.id == ident)).mappings().first()
        item = {'kind': kind, 'id': ident, 'deleted': row is None or bool(row.get('is_deleted'))}
        if not item['deleted']:
            item['data'] = {key: value.isoformat() if isinstance(value, date) else value
                            for key, value in row.items() if key not in PRIVATE_FIELDS and not key.endswith('_path')}
        items.append(item)
        after = seq
    return {'items': items, 'has_more': len(events) > limit,
        'next_cursor': jwt.encode({'purpose': 'sync-changes-v1', 'scope': scope, 'seq': after, 'generation': generation},
                                  settings.jwt_secret, algorithm=settings.jwt_algorithm),
        'patient': {'id': pid, 'name': access.patient(db, pid, user).name},
        'staff': {'id': user.id, 'display_name': user.display_name}}
