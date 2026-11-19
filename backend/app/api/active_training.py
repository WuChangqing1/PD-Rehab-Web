from fastapi import APIRouter
from app.api.deps import CurrentUser,DbSession
from app.services import active_training_service as service,audit_service

router=APIRouter(tags=['Training'])

@router.get('/patients/{patient_id}/training/active')
def active(patient_id:str,db:DbSession,user:CurrentUser):
    service.lock_patient(db,patient_id)
    rows=service.pending(db,patient_id)
    def can_clear(row):
        if row['kind']=='guided':return row['owner_id']==user.id
        if user.role!='NURSE':return True
        return service.training_owner(db,row['id'],row['kind'])==user.id
    return [{k:v for k,v in row.items() if k!='owner_id'}|{'can_clear':can_clear(row)} for row in rows]

@router.delete('/patients/{patient_id}/training/active/{kind}/{session_id}')
def clear(patient_id:str,kind:str,session_id:str,db:DbSession,user:CurrentUser):
    service.clear_pending(db,patient_id,kind,session_id,owner_id=user.id)
    audit_service.record(db,staff_user_id=user.id,action='TRAINING_PENDING_CLEAR',entity_type=kind,entity_id=session_id,detail={'patient_id':patient_id})
    return {'cleared':True}
