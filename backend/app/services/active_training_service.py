"""One unfinished training per patient and Beijing day; no metric fabrication."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from app.db.base import utcnow
from app.db.models import Patient, PianoSession, PoseSession
from app.db.models.guided_song import GuidedSongSession
from app.core.errors import conflict, forbidden, not_found

def metadata(value):
    if isinstance(value,dict): return value
    try: return json.loads(value or '{}')
    except (ValueError,TypeError): return {}

def lock_patient(db,patient_id):
    # The write lock also serializes independent SQLite workers. Retain identity/version.
    if db.get_bind().dialect.name=='sqlite':
        db.execute(update(Patient).where(Patient.id==patient_id).values(id=Patient.id,updated_at=Patient.updated_at))
    else:
        db.execute(select(Patient.id).where(Patient.id==patient_id).with_for_update())
    p=db.get(Patient,patient_id,populate_existing=True)
    if not p or p.is_deleted: raise not_found('患者不存在或已被删除。')

def day(value):
    if isinstance(value,str): value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if not value:return None
    if value.tzinfo: value=value.astimezone(timezone.utc).replace(tzinfo=None)
    return (value+timedelta(hours=8)).date()

def pending(db,patient_id,*,now=None):
    today=day(now or utcnow());result=[]
    for kind,model in [('piano',PianoSession),('pose',PoseSession),('guided',GuidedSongSession)]:
        condition=model.status=='ACTIVE' if kind=='guided' else model.completed_at.is_(None)
        rows=db.scalars(select(model).where(model.patient_id==patient_id,condition).with_for_update().execution_options(populate_existing=True))
        for row in rows:
            data=metadata(row.config if kind=='guided' else row.difficulty_before_json if kind=='piano' else row.difficulty_json)
            at=data.get('opened_at') or (row.created_at if kind=='guided' else row.started_at)
            if data.get('completion_status') in ('CANCELLED','INTERRUPTED') or day(at)!=today:continue
            result.append({'id':row.id,'kind':kind,'started_at':at,'label':'曲目跟弹' if kind=='guided' else '芭蕾动作训练' if kind=='pose' else '钢琴基础测试' if row.mode=='CALIBRATION' else '钢琴节奏训练',
                'owner_id':row.owner_id if kind=='guided' else None})
    return result

def ensure_free(db,patient_id):
    rows=pending(db,patient_id)
    if rows:raise conflict('今天还有进行中的训练，请先完成或清除后再开始。',{'active_training':True})

def clear_pending(db,patient_id,kind,session_id,*,owner_id):
    lock_patient(db,patient_id)
    model={'piano':PianoSession,'pose':PoseSession,'guided':GuidedSongSession}.get(kind)
    row=db.scalar(select(model).where(model.id==session_id).with_for_update().execution_options(populate_existing=True)) if model else None
    if not row or row.patient_id!=patient_id:raise not_found('训练记录不存在。')
    if kind=='guided':
        if row.owner_id!=owner_id:raise forbidden('请由创建该训练的账号清除。')
        if row.status=='ACTIVE':row.status='CANCELLED'
    else:
        if row.completed_at is not None:raise conflict('已完成的记录不能作为进行中的训练清除。')
        field='difficulty_before_json' if kind=='piano' else 'difficulty_json'
        setattr(row,field,json.dumps({**metadata(getattr(row,field)),'completion_status':'CANCELLED','cancelled_at':utcnow().isoformat()},ensure_ascii=False))
    db.commit()

def assert_open(row,kind):
    data=metadata(row.difficulty_before_json if kind=='piano' else row.difficulty_json)
    if data.get('completion_status')=='CANCELLED':raise conflict('本次训练已清除，请重新开始。')
