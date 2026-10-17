from datetime import date
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, DbSession
from app.schemas.followup import FollowUpRead
from app.services.followup_service import activity_feed

router=APIRouter(tags=['Follow-up'])


@router.get('/patients/{patient_id}/follow-up',response_model=FollowUpRead,summary='按本地日期读取评估与全部训练记录')
def read_followup(patient_id:str,db:DbSession,user:CurrentUser,
                  start_date:date=Query(),end_date:date=Query(),
                  offset_minutes:int=Query(480,ge=-720,le=840)) -> FollowUpRead:
    return activity_feed(db,patient_id,user.id,start_date,end_date,offset_minutes)
