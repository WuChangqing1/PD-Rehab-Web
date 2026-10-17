"""Read-only bounded patient activity feed. No inference, raw audio or writes."""
from datetime import date, datetime, time, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session, defer
from app.core.errors import APIError, ErrorCode
from app.db.models import AssessmentSession, FingerTappingResult, PianoSession, PoseSession
from app.db.models.guided_song import GuidedSongSession
from app.schemas.followup import FollowUpRead, GuidedTrainingSummary
from app.services.patient_service import get_patient
from app.ml.pose.exercises import EXERCISES

SHOWCASE_NUMBER = 'DEMO-FOLLOWUP-20261017'


def activity_feed(db: Session, patient_id: str, owner_id: str, start_date: date,
                  end_date: date, offset_minutes: int) -> FollowUpRead:
    if end_date.year>=9999 or end_date < start_date or (end_date-start_date).days > 365:
        raise APIError(422, ErrorCode.VALIDATION_ERROR, '请选择不超过 366 天的有效日期范围。')
    patient = get_patient(db, patient_id)
    shift=timedelta(minutes=offset_minutes)
    start=datetime.combine(start_date,time.min)-shift
    end=datetime.combine(end_date+timedelta(days=1),time.min)-shift
    def rows(model, column):
        return list(db.scalars(select(model).where(model.patient_id==patient_id,column>=start,column<end).order_by(column.desc())))
    assessments=rows(AssessmentSession,AssessmentSession.started_at)
    tapping=list(db.scalars(select(FingerTappingResult).join(AssessmentSession).where(
        AssessmentSession.patient_id==patient_id,FingerTappingResult.created_at>=start,
        FingerTappingResult.created_at<end).order_by(FingerTappingResult.created_at.desc())))
    guided_rows=db.scalars(select(GuidedSongSession).options(defer(GuidedSongSession.events)).where(
        GuidedSongSession.patient_id==patient_id,GuidedSongSession.owner_id==owner_id,
        GuidedSongSession.created_at>=start,GuidedSongSession.created_at<end).order_by(GuidedSongSession.created_at.desc()))
    guided=[]
    for row in guided_rows:
        config=row.config or {}
        metrics=(row.result or {}).get('metrics') or {}
        adjustment=config.get('difficulty_adjustment') or {}
        source=config.get('input_source','UNLABELLED')
        if row.is_simulation:
            source='SEED_DEMO' if config.get('demo_dataset')=='followup-showcase-v1' and patient.hospital_number==SHOWCASE_NUMBER else 'SYNTHETIC_SELFTEST'
        guided.append(GuidedTrainingSummary(id=row.id,patient_id=row.patient_id,status=row.status,
            started_at=row.created_at,completed_at=row.completed_at,source=source,
            song_id=config.get('song_id'),selected_hand=config.get('selected_hand'),
            difficulty=config.get('initial_difficulty'),bpm=config.get('segment_2_bpm') or config.get('segment_1_bpm'),
            segment_1_bpm=config.get('segment_1_bpm'),segment_2_bpm=config.get('segment_2_bpm'),
            metrics=metrics,version=metrics.get('metrics_version') or adjustment.get('policy_version') or config.get('policy_version')))
    return FollowUpRead(patient_id=patient_id,start_date=start_date,end_date=end_date,offset_minutes=offset_minutes,
        is_showcase=patient.hospital_number==SHOWCASE_NUMBER,exercise_names={e.key:e.name_zh for e in EXERCISES},assessments=assessments,tapping=tapping,
        piano=rows(PianoSession,PianoSession.started_at),pose=rows(PoseSession,PoseSession.started_at),guided=guided)
