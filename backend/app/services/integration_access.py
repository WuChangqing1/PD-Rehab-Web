"""Object authorization for the cross-client API; no implicit UUID access."""
from sqlalchemy import select, or_
from app.db.models import Patient, StaffUser, AuditLog, PatientAccessGrant, DevicePatientLink
from app.core.errors import APIError,ErrorCode,not_found

def scope(db,user,*,include_deleted=False):
    alive=True if include_deleted else Patient.is_deleted.is_(False)
    if user.role=='ADMIN': return alive
    grants=select(PatientAccessGrant.patient_id).where(PatientAccessGrant.staff_user_id==user.id,PatientAccessGrant.active.is_(True))
    explicit=select(PatientAccessGrant.patient_id).where(PatientAccessGrant.staff_user_id==user.id)
    created=select(AuditLog.entity_id).where(AuditLog.staff_user_id==user.id,AuditLog.action=='PATIENT_CREATE',AuditLog.entity_type=='patient')
    from app.db.models import AssessmentSession,GuidedSongSession
    history=select(AssessmentSession.__table__.c.patient_id).where(AssessmentSession.__table__.c.created_by==user.id)
    guided=select(GuidedSongSession.__table__.c.patient_id).where(GuidedSongSession.__table__.c.owner_id==user.id)
    original=or_(Patient.id.in_(created),Patient.id.in_(history),Patient.id.in_(guided))
    return or_(Patient.id.in_(grants),original & Patient.id.not_in(explicit)) & alive

def patient(db,patient_id,user):
    row=db.scalar(select(Patient).where(Patient.id==patient_id,scope(db,user)))
    if row is None: raise APIError(403,ErrorCode.FORBIDDEN,'没有此患者的跨端访问权限或患者已停用。')
    return row

def bound(db,device,profile,patient_id,user):
    patient(db,patient_id,user)
    link=db.scalar(select(DevicePatientLink).where(DevicePatientLink.device_id==device,DevicePatientLink.local_profile_id==profile,DevicePatientLink.patient_id==patient_id,DevicePatientLink.bound_by==user.id,DevicePatientLink.active.is_(True)).execution_options(populate_existing=True))
    if link is None or not link.active or link.patient_id!=patient_id or link.bound_by!=user.id:
        raise APIError(403,ErrorCode.FORBIDDEN,'当前账号没有该设备档案的有效绑定。')
    return link

def job(db,job_id,user):
    from app.db.models import MobileFaceJob
    row=db.get(MobileFaceJob,job_id)
    if row is None: raise not_found('分析任务不存在。')
    patient(db,row.patient_id,user)
    if row.device_id and row.local_profile_id:
        owner=db.get(StaffUser,row.operator_id)
        if owner is None or not owner.is_active:raise APIError(403,ErrorCode.FORBIDDEN,'任务所属账号已停用。')
        bound(db,row.device_id,row.local_profile_id,row.patient_id,owner)
    if row.operator_id!=user.id and user.role!='ADMIN':
        raise APIError(403,ErrorCode.FORBIDDEN,'无权读取其他账号的分析任务。')
    return row


def install_request_scope(db,user):
    """One policy for both legacy Web and mobile API; no JWT path bypass.

    No application background/migration session is changed. Account ADMIN sees
    all patients, DOCTOR sees explicit grants or patients they created. A revoked
    explicit grant overrides creator access. No per-request permissions in JWT.
    """
    if user.role=='ADMIN':return
    ids=tuple(db.scalars(select(Patient.id).where(scope(db,user,include_deleted=True))))
    db.info['authorized_patient_ids']=ids

from sqlalchemy import event
from sqlalchemy.orm import Session,with_loader_criteria

@event.listens_for(Session,'do_orm_execute')
def _filter_patient_reads(execute_state):
    ids=execute_state.session.info.get('authorized_patient_ids')
    if ids is None or not execute_state.is_select or execute_state.is_column_load:return
    from app.db.base import Base
    from app.db.models import AssessmentSession,PianoSession
    assessment_ids=select(AssessmentSession.__table__.c.id).where(AssessmentSession.__table__.c.patient_id.in_(ids))
    piano_ids=select(PianoSession.__table__.c.id).where(PianoSession.__table__.c.patient_id.in_(ids))
    options=[]
    for mapper in Base.registry.mappers:
        cls=mapper.class_
        if cls is Patient:criterion=cls.id.in_(ids)
        elif hasattr(cls,'patient_id'):criterion=cls.patient_id.in_(ids)
        elif hasattr(cls,'assessment_session_id'):criterion=cls.assessment_session_id.in_(assessment_ids)
        elif hasattr(cls,'piano_session_id'):criterion=cls.piano_session_id.in_(piano_ids)
        elif cls.__tablename__=='piano_events':criterion=cls.session_id.in_(piano_ids)
        else:continue
        options.append(with_loader_criteria(cls,criterion,include_aliases=True))
    execute_state.statement=execute_state.statement.options(*options)
